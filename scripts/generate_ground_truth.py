"""
Generate ground truth data for any book from the database.

Usage:
    python scripts/generate_ground_truth.py hegel
    python scripts/generate_ground_truth.py mam
    python scripts/generate_ground_truth.py hegel mam  # Multiple books
"""

import sys
from pathlib import Path
from src.content.ground_truth import GoldenDataGenerator
from src.content.store import PgresStore


def generate_ground_truth_for_book(slug: str):
    """
    Generate ground truth queries for a book from the database.

    Args:
        slug: Book identifier (e.g., 'hegel', 'mam')
    """
    print(f"\n{'='*80}")
    print(f"Generating Ground Truth for: {slug}")
    print(f"{'='*80}\n")

    # Check if book exists in database
    store = PgresStore()
    book_id = store._resolve_book_id(slug)

    if not book_id:
        print(f"❌ Error: Book '{slug}' not found in database")
        print("\nAvailable books:")
        with store.conn.cursor() as cur:
            cur.execute('SELECT slug, title FROM books ORDER BY slug')
            for book_slug, title in cur.fetchall():
                print(f"  {book_slug:10s} - {title}")
        return False

    # Get book title
    with store.conn.cursor() as cur:
        cur.execute('SELECT title FROM books WHERE book_id = %s', (book_id,))
        title = cur.fetchone()[0]

    print(f"Book: {title}")
    print(f"Slug: {slug}\n")

    # Load chunks from Qdrant (chunks are stored in vector DB, not PostgreSQL)
    print("Loading chunks from Qdrant...")
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchText

    qdrant = QdrantClient(host='localhost', port=6333)

    if not qdrant.collection_exists('book_chunks'):
        print(f"❌ Error: Qdrant collection 'book_chunks' not found")
        print("Make sure the book has been ingested and Qdrant is running")
        return False

    # Scroll through all chunks for this book
    chunks = []
    offset = None

    while True:
        result = qdrant.scroll(
            collection_name='book_chunks',
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key='id',
                        match=MatchText(text=slug)
                    )
                ]
            ),
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )

        points, next_offset = result

        if not points:
            break

        for point in points:
            payload = point.payload
            chunks.append({
                'id': payload.get('id', 'unknown'),
                'text': payload.get('text', ''),
                'num_tokens': payload.get('num_tokens', 0),
                'num_chars': payload.get('num_chars', 0)
            })

        if next_offset is None:
            break
        offset = next_offset

    print(f"Loaded {len(chunks)} chunks\n")

    if len(chunks) == 0:
        print(f"❌ Error: No chunks found for book '{slug}'")
        return False

    # Generate questions
    print("Generating queries using GPT-4o-mini...")
    print("This will take several minutes...\n")

    generator = GoldenDataGenerator()
    generator.bulk_generate(chunks)

    # Save results
    output_path = f"DATA/GT/{slug}_golden_data.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    generator.save(output_path)

    print(f"\n✓ Ground truth saved to {output_path}")
    print(f"Total chunk IDs: {len(generator.results)}")

    # Show sample
    if generator.results:
        sample_id = list(generator.results.keys())[0]
        print(f"\nSample queries for chunk '{sample_id}':")
        for i, query in enumerate(generator.results[sample_id], 1):
            print(f"  {i}. {query}")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_ground_truth.py <book_slug> [<book_slug2> ...]")
        print("\nExample:")
        print("  python scripts/generate_ground_truth.py hegel")
        print("  python scripts/generate_ground_truth.py mam")
        print("  python scripts/generate_ground_truth.py hegel mam")
        sys.exit(1)

    book_slugs = sys.argv[1:]

    print(f"\nGenerating ground truth for {len(book_slugs)} book(s): {', '.join(book_slugs)}\n")

    success_count = 0
    for slug in book_slugs:
        if generate_ground_truth_for_book(slug):
            success_count += 1

    print(f"\n{'='*80}")
    print(f"Summary: {success_count}/{len(book_slugs)} books completed successfully")
    print(f"{'='*80}")
