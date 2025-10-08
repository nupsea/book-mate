
import asyncio

from collections import defaultdict

from src.content.reader import GutenbergReader
from src.content.store import PgresStore
from src.llm.generator import SummaryGenerator

async def load(chunks, slug: str, title: str, author: str = None, force_update: bool = False):
    """
    Generate summaries and store book metadata.

    Args:
        chunks: Book chunks from reader
        slug: Short identifier (e.g., "ody", "aiw")
        title: Book title
        author: Book author (optional)
        force_update: If True, delete existing book and regenerate everything. Default: False
    """
    store = PgresStore()

    # If force_update, delete existing book and all related data
    if force_update and store.book_exists(slug):
        print(f"force_update=True: Deleting existing book '{slug}' and all related data...")
        store.delete_book(slug)
        print(f"✓ Book '{slug}' deleted.")

    # Check if book already exists (and we're not forcing update)
    if not force_update and store.summaries_exist(slug):
        print(f"Summaries for '{title}' (slug: {slug}) already exist. Skipping summarization.")
        print(f"Use force_update=True to regenerate summaries.")
        return

    # Store book metadata
    num_chunks = len(chunks)
    num_chars = sum(len(c.get("text", "")) for c in chunks)
    book_id = store.store_book_metadata(slug, title, author, num_chunks, num_chars)

    # Generate summaries
    print(f"Generating summaries for '{title}' (slug: {slug})...")
    gen = SummaryGenerator()
    chapter_summaries, book_summary = await gen.summarize_hierarchy(chunks)

    # Store summaries
    store.store_summaries(slug, chapter_summaries, book_summary)

    print(f"✓ Book '{title}' (slug: {slug}, id: {book_id}) loaded into data store.")


books_map = {
    "ody": {
        "title": "The Odyssey",
        "author": "Homer",
        "file_path": "DATA/the_odyssey.txt",
        "split_pattern": r"^(?:BOOK [IVXLCDM]+)\s*\n"
    },
    "aiw": {
        "title": "Alice's Adventures in Wonderland",
        "author": "Lewis Carroll",
        "file_path": "DATA/alice_in_wonderland.txt",
        "split_pattern": r"^(?:CHAPTER [IVXLCDM]+\.)\s*\n"
    },
    "mma": {
        "title": "Meditations",
        "author": "Marcus Aurelius",
        "file_path": "DATA/meditations_marcus_aurelius.txt",
        "split_pattern": r"^(?:[A-Z\s]+BOOK)\s*\n$"  
    },
    "sha": {
        "title": "Sherlock Holmes",
        "author": "Arthur Conan Doyle",
        "file_path": "DATA/sherlock_holmes.txt",
        "split_pattern": r"^(?:[IVXLCDM]+)\.\s+\S.*\n$"
    }

}

if __name__ == "__main__":
    slug = "sha"

    reader = GutenbergReader(books_map[slug]["file_path"], slug, split_pattern=books_map[slug]["split_pattern"])
    chunks = reader.parse(max_tokens=500, overlap=100)
    asyncio.run(load(chunks, slug="sha", title="Sherlock Holmes", author="Arthur Conan Doyle"))
    # asyncio.run(load(chunks, slug="sha", title="Sherlock Holmes", author="Arthur Conan Doyle", force_update=True))  # Force regenerate
    print(f"Total chunks parsed: {len(chunks)}")
    print(f"Total characters: {sum(len(c.get('text', '')) for c in chunks)}")
    print(f"First chunk: {chunks[0]}")
    print(f"Last chunk: {chunks[-1]}")
