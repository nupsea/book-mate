"""
Book query script - plain Python.
"""
from src.content.store import PgresStore
from src.search.hybrid import FusionRetriever


def validate_book_exists(book_identifier: str | int):
    """Validate that book exists in database."""
    store = PgresStore()
    book_id = store._resolve_book_id(book_identifier)

    if not book_id:
        raise ValueError(f"Book not found: {book_identifier}")

    return {"book_id": book_id, "identifier": book_identifier}


def search_book_content(query: str, book_identifier: str | int, limit: int = 5):
    """
    Search book content using hybrid search (BM25 + vector).
    Returns chunk IDs and fetches chunk text from Qdrant.
    """
    print(f"Searching for: '{query}' in book: {book_identifier}")

    try:
        # Validate book exists and get book_id
        store = PgresStore()
        book_id = store._resolve_book_id(book_identifier)
        if not book_id:
            return {
                "query": query,
                "book": book_identifier,
                "chunk_ids": [],
                "chunks": [],
                "num_results": 0,
                "error": f"Book not found: {book_identifier}"
            }

        retriever = FusionRetriever()
        chunk_ids = retriever.id_search(query, topk=limit * 3)  # Get more results to filter

        print(f"[DEBUG] Hybrid search returned {len(chunk_ids)} chunk IDs:")
        for i, cid in enumerate(chunk_ids[:10], 1):  # Show first 10
            print(f"  {i}. {cid}")

        # Fetch full chunk details from Qdrant by ID
        chunks_full = retriever.vec.get_chunks_by_ids(chunk_ids)

        print(f"[DEBUG] Filtering for book_identifier: '{book_identifier}'")
        print(f"[DEBUG] Looking for chunks starting with: '{book_identifier}_'")

        # Filter chunks by book_identifier and truncate text
        chunks_with_text = []
        for chunk in chunks_full:
            # Check if chunk belongs to this book (chunk ID format: book_slug_chapter_chunk_hash)
            if chunk["id"].startswith(f"{book_identifier}_"):
                text = chunk["text"]
                chunks_with_text.append({
                    "id": chunk["id"],
                    "text": text[:800] + "..." if len(text) > 800 else text
                })
                if len(chunks_with_text) >= limit:
                    break

        print(f"[DEBUG] After filtering: {len(chunks_with_text)} chunks matched")

        return {
            "query": query,
            "book": book_identifier,
            "chunk_ids": [c["id"] for c in chunks_with_text],
            "chunks": chunks_with_text,
            "num_results": len(chunks_with_text)
        }
    except Exception as e:
        print(f"Search error: {e}")
        return {
            "query": query,
            "book": book_identifier,
            "chunk_ids": [],
            "chunks": [],
            "num_results": 0,
            "error": str(e)
        }


def get_chapter_summaries(book_identifier: str | int):
    """Get all chapter summaries for a book."""
    store = PgresStore()
    chapters = store.get_all_chapter_summaries(book_identifier)

    return {
        "chapters": [{"chapter_id": ch_id, "summary": summary} for ch_id, summary in chapters],
        "num_chapters": len(chapters)
    }


def get_book_summary(book_identifier: str | int):
    """Get overall book summary."""
    store = PgresStore()
    summary = store.get_book_summary(book_identifier)

    return {
        "summary": summary,
        "length": len(summary) if summary else 0
    }


def query_book(
    book_identifier: str | int,
    query: str = None,
    include_chapters: bool = True,
    include_book_summary: bool = True,
    search_limit: int = 5
):
    """
    Query a book with optional search and summary retrieval.
    """
    print(f"Starting query for book: {book_identifier}")

    validation = validate_book_exists(book_identifier)
    print(f"Book validated - ID: {validation['book_id']}")

    results = {"book_id": validation['book_id']}

    if query:
        results["search"] = search_book_content(query, book_identifier, search_limit)
        print(f"Search completed - Found {results['search']['num_results']} results")

    if include_chapters:
        results["chapters"] = get_chapter_summaries(book_identifier)
        print(f"Retrieved {results['chapters']['num_chapters']} chapter summaries")

    if include_book_summary:
        results["book_summary"] = get_book_summary(book_identifier)
        print(f"Retrieved book summary ({results['book_summary']['length']} chars)")

    print("Query complete")
    return results


if __name__ == "__main__":
    # Example 1: Get all summaries
    result1 = query_book(
        book_identifier="mma",
        include_chapters=True,
        include_book_summary=True
    )
    print(f"\nQuery result: Found {result1['chapters']['num_chapters']} chapters")
    print(f"Book summary preview: {result1['book_summary']['summary'][:150]}...")

    # Example 2: Search with summaries
    result2 = query_book(
        book_identifier="ody",
        query="odysseus journey home",
        include_chapters=False,
        include_book_summary=True
    )
    print(f"\nSearch results for: '{result2['search']['query']}'")
    print(f"Found {result2['search']['num_results']} matching chunks:\n")
    for i, chunk in enumerate(result2['search']['chunks'], 1):
        print(f"{i}. [{chunk['id']}]")
        print(f"   {chunk['text']}\n")
