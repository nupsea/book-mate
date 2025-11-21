"""
Read-only evaluation that uses existing Qdrant collection.
NO side effects - doesn't delete or modify anything.

Usage:
    python -m src.flows.evaluate_readonly hegel mam
"""

from collections import defaultdict
from src.content.ground_truth import GoldenDataGenerator
from src.search.adaptive import AdaptiveRetriever


def load_combined_ground_truth(book_slugs: list[str]) -> list[dict]:
    """Load and combine ground truth from multiple books."""
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
            print(f"  ⚠ Ground truth not found for {slug}")

    return combined_gt


def calculate_metrics(results, k_values=[5, 7]):
    """Calculate Hit Rate and MRR metrics."""
    if not results:
        return {f"hit_rate_at_{k}": 0.0 for k in k_values} | {
            f"mrr_at_{k}": 0.0 for k in k_values
        }

    metrics = defaultdict(list)

    for result in results:
        res_ids = result.get("chunk_ids")
        gold_id = result.get("gold_id")

        for k in k_values:
            # Hit Rate
            hit = 1.0 if gold_id in res_ids[:k] else 0.0
            metrics[f"hit_rate_at_{k}"].append(hit)

            # MRR
            mrr = 0.0
            for i, res_id in enumerate(res_ids[:k], start=1):
                if res_id == gold_id:
                    mrr = 1.0 / i
                    break
            metrics[f"mrr_at_{k}"].append(mrr)

    avg_metrics = {}
    for metric, values in metrics.items():
        avg_metrics[metric] = sum(values) / len(values) if values else 0.0

    avg_metrics["total_queries"] = len(results)

    return avg_metrics


def evaluate_readonly(book_slugs: list[str]):
    """
    Evaluate using EXISTING Qdrant collection (read-only, no modifications).

    This assumes:
    - Qdrant collection 'book_chunks' already exists with all books
    - Ground truth files exist for the specified books
    """
    print(f"\n{'='*80}")
    print("Read-Only Multi-Book Evaluation")
    print(f"Books: {', '.join(book_slugs)}")
    print(f"{'='*80}\n")

    # Load ground truth
    print("Step 1: Loading Ground Truth")
    print("-" * 80)
    combined_gt = load_combined_ground_truth(book_slugs)

    if not combined_gt:
        print("\n❌ No ground truth found!")
        print("Generate with: python scripts/generate_ground_truth_simple.py hegel mam")
        return None

    print(f"\nTotal queries: {len(combined_gt)}")

    # Show breakdown by book
    from collections import Counter
    book_counts = Counter(item['gold_id'].split('_')[0] for item in combined_gt)
    for slug, count in sorted(book_counts.items()):
        print(f"  {slug:10s}: {count:4d} queries")
    print()

    # Check Qdrant collection exists
    print("Step 2: Checking Qdrant Collection")
    print("-" * 80)
    from qdrant_client import QdrantClient
    qdrant = QdrantClient("localhost", port=6333)

    if not qdrant.collection_exists("book_chunks"):
        print("❌ Error: Qdrant collection 'book_chunks' not found!")
        print("Please ensure books are ingested first.")
        return None

    collection_info = qdrant.get_collection("book_chunks")
    print("Collection 'book_chunks' found")
    print(f"  Total vectors: {collection_info.points_count}")
    print()

    # Evaluate using existing collection (READ-ONLY)
    print("Step 3: Running Evaluation (Read-Only)")
    print("-" * 80)
    print("Using existing Qdrant collection with book_slug filtering")
    print()

    # Initialize retriever (uses existing BM25 index and Qdrant collection)
    retriever = AdaptiveRetriever(
        alpha=0.7,
        bm25_index_path="INDEXES/bm25_index.pkl"  # Use production index
    )

    # Load BM25 index
    try:
        retriever.load_bm25_index()
        print(f"Loaded BM25 index: {retriever.bm25.N} documents")
    except FileNotFoundError:
        print("⚠ BM25 index not found, will use vector-only search")

    # Run evaluation
    results = []
    print(f"\nEvaluating {len(combined_gt)} queries...")

    for item in combined_gt:
        gold_id = item["gold_id"]
        query = item["query"]

        # Extract book slug from gold_id (format: slug_chapter_chunk_hash)
        book_slug = gold_id.split("_")[0]

        # Search with book filtering (uses our new book_slug parameter)
        chunk_ids = retriever.id_search(query, topk=7, book_slug=book_slug)
        results.append({"gold_id": gold_id, "chunk_ids": chunk_ids})

    # Calculate overall metrics
    metrics = calculate_metrics(results, k_values=[5, 7])

    # Calculate per-book metrics
    from collections import defaultdict
    results_by_book = defaultdict(list)
    for result in results:
        book_slug = result["gold_id"].split("_")[0]
        results_by_book[book_slug].append(result)

    per_book_metrics = {}
    for book_slug, book_results in results_by_book.items():
        per_book_metrics[book_slug] = calculate_metrics(book_results, k_values=[5, 7])

    # Print results
    print("\n" + "="*80)
    print("RESULTS - Read-Only Evaluation")
    print("="*80)
    print("\nOVERALL (Combined):")
    print(f"  Total Queries:  {metrics['total_queries']}")
    print(f"  Hit Rate @ 5:   {metrics['hit_rate_at_5']:.3f} ({metrics['hit_rate_at_5']*100:.1f}%)")
    print(f"  MRR @ 5:        {metrics['mrr_at_5']:.3f}")
    print(f"  Hit Rate @ 7:   {metrics['hit_rate_at_7']:.3f} ({metrics['hit_rate_at_7']*100:.1f}%)")
    print(f"  MRR @ 7:        {metrics['mrr_at_7']:.3f}")

    print("\nPER-BOOK BREAKDOWN:")
    for book_slug in sorted(per_book_metrics.keys()):
        book_metrics = per_book_metrics[book_slug]
        print(f"\n  [{book_slug}]:")
        print(f"    Total Queries:  {book_metrics['total_queries']}")
        print(f"    Hit Rate @ 5:   {book_metrics['hit_rate_at_5']:.3f} ({book_metrics['hit_rate_at_5']*100:.1f}%)")
        print(f"    MRR @ 5:        {book_metrics['mrr_at_5']:.3f}")
        print(f"    Hit Rate @ 7:   {book_metrics['hit_rate_at_7']:.3f} ({book_metrics['hit_rate_at_7']*100:.1f}%)")
        print(f"    MRR @ 7:        {book_metrics['mrr_at_7']:.3f}")

    print("\n" + "="*80)
    print("\n✓ Evaluation complete - no changes made to collection\n")

    return {"overall": metrics, "per_book": per_book_metrics}


if __name__ == "__main__":
    import sys

    book_slugs = ["hegel", "mam"] if len(sys.argv) == 1 else sys.argv[1:]

    print(f"\nEvaluating: {', '.join(book_slugs)}")
    print("Note: This is READ-ONLY - uses existing Qdrant collection")
    print("Generate ground truth: python scripts/generate_ground_truth_simple.py hegel mam\n")

    evaluate_readonly(book_slugs)
