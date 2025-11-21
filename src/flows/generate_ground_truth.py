"""
Generate ground truth evaluation data for a book using LLM as judge.
"""

from src.content.ground_truth import GoldenDataGenerator
from src.content.reader import GutenbergReader


def sample_chunks_for_gt(
    book_slug: str, sample_size: int = 50, skip_preface: bool = True
):
    """
    Sample representative chunks from a book for ground truth generation.

    Args:
        book_slug: Book identifier
        sample_size: Number of chunks to sample (default: 50)
        skip_preface: Skip preface/introduction chunks (default: True)

    Returns:
        List of sampled chunks
    """
    # Map of book slugs to file paths and patterns
    book_configs = {
        "ody": {
            "path": "DATA/the_odyssey.txt",
            "pattern": r"^(?:BOOK [IVXLCDM]+)\s*\n",
            "title": "The Odyssey",
            "skip_first": 11,  # Skip preface chunks (first 11 chunks are preface)
        },
        "mma": {
            "path": "DATA/meditations_marcus_aurelius.txt",
            "pattern": r"^(?:THE .* BOOK)\s*\n",
            "title": "Meditations",
            "skip_first": 5,
        },
        "sha": {
            "path": "DATA/sherlock_holmes.txt",
            "pattern": r"^[IVXLCDM]+\.\s+.*\n",
            "title": "The Adventures of Sherlock Holmes",
            "skip_first": 5,
        },
        "aiw": {
            "path": "DATA/alice_in_wonderland.txt",
            "pattern": r"^(?:CHAPTER [IVXLCDM]+\.)\s*\n",
            "title": "Alice in Wonderland",
            "skip_first": 3,
        },
    }

    if book_slug not in book_configs:
        raise ValueError(f"Book configuration not found for '{book_slug}'")

    config = book_configs[book_slug]
    print(f"\nLoading: {config['title']}")

    reader = GutenbergReader(
        config["path"], slug=book_slug, split_pattern=config["pattern"]
    )

    chunks = reader.parse(max_tokens=500, overlap=100)
    print(f"Total chunks parsed: {len(chunks)}")

    # Skip preface/introduction chunks
    if skip_preface and "skip_first" in config:
        skip_count = config["skip_first"]
        chunks = chunks[skip_count:]
        print(f"Skipped first {skip_count} chunks (preface/introduction)")
        print(f"Remaining chunks for sampling: {len(chunks)}")

    # Sample evenly distributed chunks from story content
    if len(chunks) > sample_size:
        step = len(chunks) // sample_size
        sampled = [chunks[i] for i in range(0, len(chunks), step)][:sample_size]
        print(f"Sampled {len(sampled)} chunks evenly from story content")
        return sampled

    return chunks


def generate_ground_truth(
    book_slug: str, sample_size: int = 50, output_path: str = None
):
    """
    Generate ground truth queries for a book.

    Args:
        book_slug: Book identifier (e.g., 'ody' for The Odyssey)
        sample_size: Number of chunks to sample
        output_path: Optional output path (defaults to DATA/GT/{slug}_golden_data.json)
    """
    print(f"\n=== Generating Ground Truth for {book_slug.upper()} ===\n")

    # Sample chunks
    chunks = sample_chunks_for_gt(book_slug, sample_size)

    # Generate queries
    print(f"\nGenerating queries for {len(chunks)} chunks using LLM...")
    print("This will take a few minutes...\n")

    generator = GoldenDataGenerator()
    generator.bulk_generate(chunks)

    # Save results
    if output_path is None:
        output_path = f"DATA/GT/{book_slug}_golden_data.json"

    generator.save(output_path)

    # Calculate statistics
    total_queries = sum(len(queries) for queries in generator.results.values())
    print(f"\nGenerated {total_queries} queries for {len(generator.results)} chunks")
    print(f"Average {total_queries / len(generator.results):.1f} queries per chunk")
    print(f"Saved to: {output_path}")

    return generator.results


if __name__ == "__main__":
    import sys

    # Configuration
    book_slug = "ody"  # The Odyssey
    sample_size = 50  # Number of chunks to generate GT for

    if len(sys.argv) > 1:
        book_slug = sys.argv[1]

    if len(sys.argv) > 2:
        sample_size = int(sys.argv[2])

    # Generate ground truth
    generate_ground_truth(book_slug, sample_size)
    print("\nComplete!")
