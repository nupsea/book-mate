"""
Evaluate search performance using ground truth data.
Compares baseline vs adaptive retriever.
"""

from src.content.ground_truth import GoldenDataGenerator
from src.content.reader import GutenbergReader
from src.search.hybrid import FusionRetriever
from src.search.adaptive import AdaptiveRetriever
from src.search.eval import SearchEvaluator


def load_chunks_for_book(book_slug: str):
    """Load all chunks for a book."""
    book_configs = {
        "ody": {
            "path": "DATA/the_odyssey.txt",
            "pattern": r"^(?:BOOK [IVXLCDM]+)\s*\n",
            "title": "The Odyssey",
        },
        "mma": {
            "path": "DATA/meditations_marcus_aurelius.txt",
            "pattern": r"^(?:THE .* BOOK)\s*\n",
            "title": "Meditations",
        },
        "sha": {
            "path": "DATA/sherlock_holmes.txt",
            "pattern": r"^[IVXLCDM]+\.\s+.*\n",
            "title": "The Adventures of Sherlock Holmes",
        },
        "aiw": {
            "path": "DATA/alice_in_wonderland.txt",
            "pattern": r"^(?:CHAPTER [IVXLCDM]+\.)\s*\n",
            "title": "Alice in Wonderland",
        },
    }

    if book_slug not in book_configs:
        raise ValueError(f"Book configuration not found for '{book_slug}'")

    config = book_configs[book_slug]
    print(f"Loading: {config['title']}")

    reader = GutenbergReader(
        config["path"], slug=book_slug, split_pattern=config["pattern"]
    )

    chunks = reader.parse(max_tokens=500, overlap=100)
    print(f"Loaded {len(chunks)} chunks")
    return chunks


def evaluate_search(book_slug: str, ground_truth_path: str = None):
    """
    Evaluate baseline vs adaptive retriever performance.

    Args:
        book_slug: Book identifier (e.g., 'ody', 'aiw')
        ground_truth_path: Path to ground truth JSON file
    """
    print(f"\n=== Evaluating Search Performance for {book_slug.upper()} ===\n")

    if ground_truth_path is None:
        ground_truth_path = f"DATA/GT/{book_slug}_golden_data.json"

    # Load ground truth
    generator = GoldenDataGenerator()
    generator.load(ground_truth_path)
    golden_data = generator.get_golden_data()

    print(f"Ground truth queries: {len(golden_data)}\n")

    # Load chunks
    chunks = load_chunks_for_book(book_slug)

    # Clear Qdrant collection for fresh start
    from qdrant_client import QdrantClient

    qdrant = QdrantClient("localhost", port=6333)
    if qdrant.collection_exists("book_chunks"):
        print("Clearing Qdrant collection...\n")
        qdrant.delete_collection("book_chunks")

    # Test baseline vs adaptive
    configs = [
        {
            "name": "Baseline (α=0.7, no preprocessing)",
            "retriever": FusionRetriever(
                alpha=0.7, bm25_index_path=f"INDEXES/{book_slug}_baseline.pkl"
            ),
        },
        {
            "name": "Adaptive (α=0.7 + preprocessing)",
            "retriever": AdaptiveRetriever(
                alpha=0.7, bm25_index_path=f"INDEXES/{book_slug}_adaptive.pkl"
            ),
        },
    ]

    results = {}

    for config in configs:
        print(f"Testing: {config['name']}")
        retriever = config["retriever"]
        evaluator = SearchEvaluator(chunks, retriever)
        metrics = evaluator.evaluate(golden_data)
        results[config["name"]] = metrics

        print(f"  Hit@5: {metrics['hit_rate_at_5']:.3f}")
        print(f"  MRR@5: {metrics['mrr_at_5']:.3f}")
        print(f"  Hit@7: {metrics['hit_rate_at_7']:.3f}")
        print(f"  MRR@7: {metrics['mrr_at_7']:.3f}\n")

        # Clear collection for next test
        if qdrant.collection_exists("book_chunks"):
            qdrant.delete_collection("book_chunks")

    # Comparison table
    print("\n" + "=" * 80)
    print(f"RESULTS - {book_slug.upper()}")
    print("=" * 80)
    print(f"{'Configuration':<45} {'Hit@5':<10} {'MRR@5':<10} {'Δ Hit@5':<10}")
    print("-" * 80)

    baseline_hit5 = results["Baseline (α=0.7, no preprocessing)"]["hit_rate_at_5"]

    for name, metrics in results.items():
        delta = metrics["hit_rate_at_5"] - baseline_hit5
        delta_str = f"+{delta:.3f}" if delta > 0 else f"{delta:.3f}"
        print(
            f"{name:<45} {metrics['hit_rate_at_5']:<10.3f} "
            f"{metrics['mrr_at_5']:<10.3f} {delta_str:<10}"
        )

    print("=" * 80)

    improvement = (
        (results["Adaptive (α=0.7 + preprocessing)"]["hit_rate_at_5"] - baseline_hit5)
        / baseline_hit5
        * 100
    )
    print(f"\nImprovement: {improvement:+.1f}%")

    return results


if __name__ == "__main__":
    import sys

    # Configuration
    book_slug = "ody"  # The Odyssey

    if len(sys.argv) > 1:
        book_slug = sys.argv[1]

    # Evaluate search
    evaluate_search(book_slug)
