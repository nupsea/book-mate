"""
Book ingestion pipeline - plain Python script.
"""

import asyncio
from pathlib import Path

from src.content.reader import GutenbergReader, PDFReader
from src.content.store import PgresStore
from src.llm.generator import SummaryGenerator
from src.search.hybrid import FusionRetriever


def validate_inputs(slug: str, file_path: str, title: str, force_update: bool = False):
    """Validate inputs before processing."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not slug or not slug.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"Invalid slug format: {slug}")

    store = PgresStore()
    exists = store.book_exists(slug)

    if exists and not force_update:
        raise ValueError(
            f"Book with slug '{slug}' already exists. Use force_update=True to overwrite."
        )

    return {
        "slug": slug,
        "file_path": file_path,
        "title": title,
        "exists": exists,
        "file_size": path.stat().st_size,
    }


def read_and_parse(
    slug: str,
    file_path: str,
    split_pattern: str = None,
    max_tokens: int = 500,
    overlap: int = 100,
):
    """Read file and parse into chunks."""
    path = Path(file_path)
    file_extension = path.suffix.lower()

    # Choose reader based on file extension
    if file_extension == ".pdf":
        reader = PDFReader(file_path, slug, split_pattern=split_pattern)
    else:
        # Default to GutenbergReader for .txt files
        reader = GutenbergReader(file_path, slug, split_pattern=split_pattern)

    chunks = reader.parse(max_tokens=max_tokens, overlap=overlap)

    return {
        "chunks": chunks,
        "num_chunks": len(chunks),
        "num_chars": sum(len(c.get("text", "")) for c in chunks),
        "num_tokens": sum(c.get("num_tokens", 0) for c in chunks),
    }


async def generate_summaries(chunks: list):
    """Generate chapter and book summaries."""
    gen = SummaryGenerator()
    chapter_summaries, book_summary = await gen.summarize_hierarchy(chunks)

    return {
        "chapter_summaries": chapter_summaries,
        "book_summary": book_summary,
        "num_chapters": len(chapter_summaries),
    }


def store_to_db(
    slug: str,
    title: str,
    author: str,
    num_chunks: int,
    num_chars: int,
    chapter_summaries: list,
    book_summary: str,
    force_update: bool = False,
):
    """Store book metadata and summaries to database."""
    store = PgresStore()

    if force_update and store.book_exists(slug):
        store.delete_book(slug)

    book_id = store.store_book_metadata(slug, title, author, num_chunks, num_chars)
    store.store_summaries(slug, chapter_summaries, book_summary)

    return {"book_id": book_id, "slug": slug}


def build_search_indexes(chunks: list):
    """Build BM25 and vector search indexes (append to existing indexes)."""
    retriever = FusionRetriever()

    # Load existing BM25 index (if exists)
    try:
        retriever.load_bm25_index()
        print(f"Loaded existing BM25 index with {retriever.bm25.N} documents")

        # Append new chunks to existing index
        existing_chunks = [
            {"id": retriever.bm25.ids[i], "text": retriever.bm25.raw_docs[i]}
            for i in range(retriever.bm25.N)
        ]
        all_chunks = existing_chunks + chunks
        print(f"Building combined index with {len(all_chunks)} total chunks")

    except FileNotFoundError:
        print("No existing BM25 index found, creating new one")
        all_chunks = chunks

    # Rebuild BM25 with all chunks (existing + new)
    retriever.bm25.build_index(all_chunks)
    retriever.bm25.save_index(retriever.bm25_index_path)

    # Build vector index for new chunks only (Qdrant handles appending)
    retriever.vec.build_index(chunks)

    return {
        "bm25_indexed": len(all_chunks),
        "vector_indexed": len(chunks),
        "new_chunks": len(chunks),
    }


def verify_ingestion(slug: str, expected_chapters: int):
    """Verify book was ingested correctly."""
    store = PgresStore()

    if not store.book_exists(slug):
        raise ValueError(f"Book verification failed: {slug} not found in database")

    if not store.summaries_exist(slug):
        raise ValueError(
            f"Summaries verification failed: no summaries found for {slug}"
        )

    chapters = store.get_all_chapter_summaries(slug)
    actual_chapters = len(chapters)

    if actual_chapters != expected_chapters:
        raise ValueError(
            f"Chapter count mismatch: expected {expected_chapters}, got {actual_chapters}"
        )

    book_summary = store.get_book_summary(slug)

    return {
        "status": "success",
        "slug": slug,
        "chapters_verified": actual_chapters,
        "book_summary_length": len(book_summary) if book_summary else 0,
    }


async def ingest_book(
    slug: str,
    file_path: str,
    title: str,
    author: str = None,
    split_pattern: str = None,
    max_tokens: int = 500,
    overlap: int = 100,
    force_update: bool = False,
):
    """
    Ingest a book: validate -> parse -> summarize -> store -> build indexes -> verify.
    """
    print(f"Starting ingestion for: {title} (slug: {slug})")

    validation = validate_inputs(slug, file_path, title, force_update)
    print(f"Validation passed - File size: {validation['file_size']} bytes")

    parse_result = read_and_parse(slug, file_path, split_pattern, max_tokens, overlap)
    print(
        f"Parsed {parse_result['num_chunks']} chunks, {parse_result['num_chars']} chars"
    )

    summary_result = await generate_summaries(parse_result["chunks"])
    print(
        f"Generated {summary_result['num_chapters']} chapter summaries + book summary"
    )

    db_result = store_to_db(
        slug,
        title,
        author,
        parse_result["num_chunks"],
        parse_result["num_chars"],
        summary_result["chapter_summaries"],
        summary_result["book_summary"],
        force_update,
    )
    print(f"Stored to database - Book ID: {db_result['book_id']}")

    search_result = build_search_indexes(parse_result["chunks"])
    print(
        f"Built search indexes - BM25: {search_result['bm25_indexed']}, Vector: {search_result['vector_indexed']} chunks"
    )

    verify_result = verify_ingestion(slug, summary_result["num_chapters"])
    print(f"Verification complete - Status: {verify_result['status']}")

    return {
        "slug": slug,
        "book_id": db_result["book_id"],
        "title": title,
        "chapters": verify_result["chapters_verified"],
        "chunks": parse_result["num_chunks"],
        "search_indexed": search_result["bm25_indexed"],
        "status": "success",
    }


if __name__ == "__main__":
    result = asyncio.run(
        ingest_book(
            slug="ody",
            file_path="DATA/the_odyssey.txt",
            title="The Odyssey",
            author="Homer",
            split_pattern=r"^(?:BOOK [IVXLCDM]+)\s*\n",
            force_update=False,
        )
    )
    print(f"\nIngestion complete: {result}")
