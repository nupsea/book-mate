"""
Utility functions for the UI.
"""

import re
from src.content.store import PgresStore


def get_available_books():
    """Fetch list of books from database with slug, title, author, chunks, and added_at."""
    try:
        store = PgresStore()
        with store.conn.cursor() as cur:
            cur.execute(
                """
                SELECT slug, title, author, num_chunks, added_at
                FROM books
                ORDER BY added_at DESC
            """
            )
            books = cur.fetchall()
        return books
    except Exception as e:
        print(f"Error fetching books: {e}")
        return []


def validate_slug(slug: str) -> tuple[bool, str]:
    """
    Validate slug format and check for duplicates.

    Returns:
        (is_valid, error_message)
    """
    if not slug or not slug.strip():
        return False, "Slug cannot be empty"

    slug = slug.strip().lower()

    # Check format (lowercase letters, numbers, hyphens, underscores only)
    if not re.match(r"^[a-z0-9_-]+$", slug):
        return (
            False,
            "Slug must contain only lowercase letters, numbers, hyphens, and underscores",
        )

    # Check length
    if len(slug) < 2 or len(slug) > 20:
        return False, "Slug must be between 2 and 20 characters"

    # Check if slug already exists
    try:
        store = PgresStore()
        with store.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM books WHERE slug = %s", (slug,))
            count = cur.fetchone()[0]
            if count > 0:
                return False, f"Slug '{slug}' already exists. Choose a different one."
    except Exception as e:
        return False, f"Error checking slug: {str(e)}"

    return True, ""


def detect_chapter_pattern(file_path: str) -> tuple[str, str]:
    """
    Try to auto-detect chapter pattern from file.

    Returns:
        (pattern, description)
    """
    patterns = [
        (
            r"^(?:CHAPTER [IVXLCDM]+)\s*\n",
            "CHAPTER + Roman numerals (e.g., CHAPTER I, CHAPTER II)",
        ),
        (r"^(?:BOOK [IVXLCDM]+)\s*\n", "BOOK + Roman numerals (e.g., BOOK I, BOOK II)"),
        (
            r"^(?:[IVXLCDM]+\. [A-Z])",
            "Roman numeral + period + title (e.g., I. TITLE, II. TITLE)",
        ),
        (
            r"^(?:Chapter \d+)\s*\n",
            "Chapter + Arabic numerals (e.g., Chapter 1, Chapter 2)",
        ),
        (r"^(?:PART [IVXLCDM]+)\s*\n", "PART + Roman numerals (e.g., PART I, PART II)"),
        (
            r"^(?:\d+\.\s+[A-Z])",
            "Arabic numeral + period + title (e.g., 1. Title, 2. Title)",
        ),
        (r"^(?:\d+\.)\s*$", "Numbered sections only (e.g., 1., 2., 3.)"),
    ]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read(100000)  # Read first 100KB

        for pattern, description in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            if len(matches) >= 2:  # Found at least 2 chapters
                return (
                    pattern,
                    f"Detected: {description} (found {len(matches)} matches)",
                )

        return "", "No pattern detected. Please provide custom pattern."
    except Exception as e:
        return "", f"Error reading file: {str(e)}"


def extract_chapter_info_from_chunks(slug: str):
    """
    Analyze chunk IDs to determine chapter count.

    Chunk format: slug_chapter_chunk_hash (e.g., mma_01_001_abc123)

    Returns:
        dict with chapter info
    """
    try:
        from src.search.hybrid import FusionRetriever

        retriever = FusionRetriever()
        # Get all chunk IDs from BM25 index
        if retriever.bm25.N == 0:
            retriever.load_bm25_index()

        # Filter chunks by slug
        book_chunks = [cid for cid in retriever.bm25.ids if cid.startswith(f"{slug}_")]

        if not book_chunks:
            return {"status": "error", "message": f"No chunks found for book '{slug}'"}

        # Extract chapter numbers
        chapter_numbers = set()
        for chunk_id in book_chunks:
            # chunk_id format: mma_01_001_abc123
            parts = chunk_id.split("_")
            if len(parts) >= 2:
                chapter_num = parts[1]
                chapter_numbers.add(chapter_num)

        sorted_chapters = sorted(chapter_numbers)

        return {
            "status": "success",
            "total_chunks": len(book_chunks),
            "total_chapters": len(sorted_chapters),
            "first_chunk": book_chunks[0] if book_chunks else "N/A",
            "last_chunk": book_chunks[-1] if book_chunks else "N/A",
            "chapter_range": (
                f"{sorted_chapters[0]} to {sorted_chapters[-1]}"
                if sorted_chapters
                else "N/A"
            ),
            "chapters": sorted_chapters,
        }

    except Exception as e:
        return {"status": "error", "message": f"Error analyzing chunks: {str(e)}"}


def format_book_list(books):
    """Format book list as a dataframe (list of lists for Gradio Dataframe)."""
    if not books:
        return []

    data = []
    for slug, title, author, num_chunks, added_at in books:
        # Format date
        if added_at:
            date_str = added_at.strftime("%Y-%m-%d %H:%M")
        else:
            date_str = "Unknown"

        data.append(
            [
                slug,
                title,
                author or "Unknown",
                num_chunks if num_chunks else 0,
                date_str,
            ]
        )

    return data


def delete_book(slug: str) -> tuple[bool, str, int]:
    """
    Delete a book and all its associated data from:
    - PostgreSQL (books table - cascades to chapter_summaries and book_summaries)
    - BM25 index
    - Qdrant vector store

    Returns:
        (success, message, chunks_deleted)
    """
    try:
        from src.search.hybrid import FusionRetriever

        store = PgresStore()
        retriever = FusionRetriever()

        # Check if book exists and get info
        with store.conn.cursor() as cur:
            cur.execute("SELECT title, num_chunks FROM books WHERE slug = %s", (slug,))
            result = cur.fetchone()
            if not result:
                return False, f"Book '{slug}' not found", 0

            book_title = result[0]

        # Delete from PostgreSQL (CASCADE handles summaries)
        with store.conn.cursor() as cur:
            cur.execute("DELETE FROM books WHERE slug = %s", (slug,))
            store.conn.commit()

        # Delete from BM25 index
        deleted_chunks = 0
        if retriever.bm25.N == 0:
            retriever.load_bm25_index()

        # Filter out chunks for this book
        book_chunk_ids = [
            cid for cid in retriever.bm25.ids if cid.startswith(f"{slug}_")
        ]
        deleted_chunks = len(book_chunk_ids)

        if book_chunk_ids:
            # Rebuild BM25 index without this book's chunks
            remaining_chunks = [
                {"id": retriever.bm25.ids[i], "text": retriever.bm25.raw_docs[i]}
                for i in range(retriever.bm25.N)
                if not retriever.bm25.ids[i].startswith(f"{slug}_")
            ]

            # Rebuild and save index
            retriever.bm25.build_index(remaining_chunks)
            retriever.bm25.save_index(retriever.bm25_index_path)

        # Delete from Qdrant
        qdrant_success = True
        qdrant_error = ""
        try:
            retriever.qdrant_client.delete(
                collection_name=retriever.collection_name,
                points_selector={
                    "filter": {"must": [{"key": "book_slug", "match": {"value": slug}}]}
                },
            )
        except Exception as e:
            qdrant_success = False
            qdrant_error = str(e)

        # Build success message
        if qdrant_success:
            return (
                True,
                f"[SUCCESS] Deleted '{book_title}' ({deleted_chunks} chunks)",
                deleted_chunks,
            )
        else:
            return (
                True,
                f"[WARNING] Book '{book_title}' deleted, but Qdrant cleanup failed: {qdrant_error}",
                deleted_chunks,
            )

    except Exception as e:
        return False, f"[ERROR] Failed to delete book: {str(e)}", 0
