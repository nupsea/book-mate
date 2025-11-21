"""
Evaluate search performance across multiple books with combined ground truth.
Measures Hit Rate (HR) and Mean Reciprocal Rank (MRR) for multi-book retrieval.

This follows the same evaluation pattern as evaluate_search.py but combines
ground truth and chunks from multiple books.
"""

from src.content.ground_truth import GoldenDataGenerator
from src.content.reader import GutenbergReader
from src.search.adaptive import AdaptiveRetriever
from src.search.eval import SearchEvaluator


BOOK_CONFIGS = {
    "ody": {
        "path": "DATA/the_odyssey.txt",
        "pattern": r"^(?:BOOK [IVXLCDM]+)\s*\n",
        "title": "The Odyssey",
        "use_db": False,  # Load from file
    },
    "mam": {
        "path": "DATA/meditations_marcus_aurelius.txt",
        "pattern": r"^(?:THE .* BOOK)\s*\n",
        "title": "The Meditations",
        "use_db": False,  # Load from file
    },
    "hegel": {
        "path": "DATA/Hegels-Philosophy.pdf",
        "pattern": None,  # PDFs don't use split pattern
        "title": "Hegel's Philosophy of Mind",
        "use_db": True,  # Load from database (already ingested)
    },
    "sha": {
        "path": "DATA/sherlock_holmes.txt",
        "pattern": r"^[IVXLCDM]+\.\s+.*\n",
        "title": "The Adventures of Sherlock Holmes",
        "use_db": False,
    },
    "aiw": {
        "path": "DATA/alice_in_wonderland.txt",
        "pattern": r"^(?:CHAPTER [IVXLCDM]+\.)\s*\n",
        "title": "Alice in Wonderland",
        "use_db": False,
    },
    "gtr": {
        "path": "DATA/gullivers_travels.txt",
        "pattern": r"^(?:CHAPTER|PART [IVXLCDM]+)\s*\n",
        "title": "Gulliver's Travels",
        "use_db": False,
    },
}


def load_chunks_for_books(book_slugs: list[str]) -> list[dict]:
    """
    Load and combine chunks from multiple books.

    Args:
        book_slugs: List of book identifiers (e.g., ['ody', 'mam', 'hegel'])

    Returns:
        Combined list of chunks from all books
    """
    all_chunks = []

    for slug in book_slugs:
        if slug not in BOOK_CONFIGS:
            raise ValueError(f"Book configuration not found for '{slug}'")

        config = BOOK_CONFIGS[slug]
        print(f"Loading: {config['title']} ({slug})")

        if config.get("use_db", False):
            # Load from database (for PDFs and already-ingested books)
            from src.content.store import PgresStore
            store = PgresStore()
            book_id = store._resolve_book_id(slug)

            if not book_id:
                raise ValueError(f"Book '{slug}' not found in database")

            with store.conn.cursor() as cur:
                cur.execute('''
                    SELECT id, text, num_tokens, num_chars
                    FROM chunks
                    WHERE book_id = %s
                    ORDER BY chapter_id, chunk_order
                ''', (book_id,))

                chunks = []
                for chunk_id, text, num_tokens, num_chars in cur.fetchall():
                    chunks.append({
                        'id': chunk_id,
                        'text': text,
                        'num_tokens': num_tokens,
                        'num_chars': num_chars
                    })
        else:
            # Load from file (for .txt books)
            reader = GutenbergReader(
                config["path"],
                slug=slug,
                split_pattern=config["pattern"]
            )
            chunks = reader.parse(max_tokens=500, overlap=100)

        print(f"  → {len(chunks)} chunks")
        all_chunks.extend(chunks)

    return all_chunks


def load_combined_ground_truth(book_slugs: list[str]) -> list[dict]:
    """
    Load and combine ground truth from multiple books.

    Args:
        book_slugs: List of book identifiers (e.g., ['ody', 'mma'])

    Returns:
        Combined ground truth data with gold_id and query pairs
    """
    combined_gt = []

    for slug in book_slugs:
        gt_path = f"DATA/GT/{slug}_golden_data.json"
        print(f"Loading ground truth: {gt_path}")

        try:
            generator = GoldenDataGenerator()
            generator.load(gt_path)
            gt_data = generator.get_golden_data()
            combined_gt.extend(gt_data)
            print(f"  → {len(gt_data)} queries")
        except FileNotFoundError:
            print(f"  ⚠ Warning: Ground truth not found for {slug}")
            print(f"     Generate it with: python scripts/generate_{slug}_ground_truth.py")

    return combined_gt


def evaluate_multibook(book_slugs: list[str]):
    """
    Evaluate search performance across multiple books.

    This follows the same pattern as evaluate_search.py:
    1. Load combined ground truth from all books
    2. Load combined chunks from all books
    3. Use SearchEvaluator to measure Hit Rate and MRR

    Args:
        book_slugs: List of book identifiers (e.g., ['ody', 'mma'])

    Returns:
        Dictionary with evaluation metrics (hit_rate_at_5, mrr_at_5, etc.)
    """
    book_titles = [BOOK_CONFIGS[s]['title'] for s in book_slugs if s in BOOK_CONFIGS]

    print(f"\n{'='*80}")
    print("Multi-Book Search Evaluation")
    print(f"Books: {', '.join(book_titles)}")
    print(f"{'='*80}\n")

    # Load combined ground truth
    print("Step 1: Loading Ground Truth")
    print("-" * 80)
    combined_gt = load_combined_ground_truth(book_slugs)

    if not combined_gt:
        print("\n❌ No ground truth data found for any of the specified books!")
        print("\nGenerate ground truth for Marcus Aurelius:")
        print("  python scripts/generate_mma_ground_truth.py")
        return None

    print(f"\nTotal ground truth queries: {len(combined_gt)}\n")

    # Show breakdown by book
    from collections import Counter
    book_counts = Counter(item['gold_id'].split('_')[0] for item in combined_gt)
    for slug, count in sorted(book_counts.items()):
        book_name = BOOK_CONFIGS.get(slug, {}).get('title', slug)
        print(f"  {slug:6s}: {count:4d} queries ({book_name})")
    print()

    # Load combined chunks
    print("Step 2: Loading Book Chunks")
    print("-" * 80)
    all_chunks = load_chunks_for_books(book_slugs)
    print(f"\nTotal chunks across all books: {len(all_chunks)}\n")

    # Evaluate using SearchEvaluator (same as single-book evaluation)
    print("Step 3: Running Evaluation")
    print("-" * 80)
    print("Testing: Adaptive Retriever (α=0.7 + preprocessing)")
    print()

    retriever = AdaptiveRetriever(
        alpha=0.7,
        bm25_index_path="INDEXES/multibook_adaptive.pkl"
    )

    # Use SearchEvaluator - it will build index and evaluate
    evaluator = SearchEvaluator(all_chunks, retriever)
    metrics = evaluator.evaluate(combined_gt)

    # Print results
    print("\n" + "="*80)
    print("RESULTS - Multi-Book Evaluation")
    print("="*80)
    print(f"Total Queries:  {metrics['total_queries']}")
    print(f"Hit Rate @ 5:   {metrics['hit_rate_at_5']:.3f} ({metrics['hit_rate_at_5']*100:.1f}%)")
    print(f"MRR @ 5:        {metrics['mrr_at_5']:.3f}")
    print(f"Hit Rate @ 7:   {metrics['hit_rate_at_7']:.3f} ({metrics['hit_rate_at_7']*100:.1f}%)")
    print(f"MRR @ 7:        {metrics['mrr_at_7']:.3f}")
    print("="*80)

    return metrics


if __name__ == "__main__":
    import sys

    # Default: Hegel + Marcus Aurelius (as requested)
    # Note: Ground truth needs to be generated first
    book_slugs = ["hegel", "mam"]

    if len(sys.argv) > 1:
        # Allow command line arguments: python evaluate_multibook.py hegel mam
        book_slugs = sys.argv[1:]

    print(f"\nEvaluating books: {', '.join(book_slugs)}")
    print("Note: Make sure ground truth exists for these books!")
    print("Generate missing ground truth with: python scripts/generate_ground_truth.py hegel mam\n")

    # Run evaluation
    evaluate_multibook(book_slugs)
