"""
Generate ground truth data for Marcus Aurelius' Meditations.
"""

from src.content.ground_truth import GoldenDataGenerator
from src.content.reader import GutenbergReader


def generate_mma_ground_truth():
    """Generate ground truth queries for Marcus Aurelius."""

    print("=== Generating Ground Truth for Marcus Aurelius ===\n")

    # Load Marcus Aurelius chunks
    print("Loading Meditations by Marcus Aurelius...")
    reader = GutenbergReader(
        "DATA/meditations_marcus_aurelius.txt",
        slug="mma",
        split_pattern=r"^(?:THE .* BOOK)\s*\n"
    )

    chunks = reader.parse(max_tokens=500, overlap=100)
    print(f"Loaded {len(chunks)} chunks\n")

    # Generate questions
    print("Generating queries using GPT-4o-mini...")
    print("This will take several minutes...\n")

    generator = GoldenDataGenerator()
    generator.bulk_generate(chunks)

    # Save results
    output_path = "DATA/GT/mma_golden_data.json"
    generator.save(output_path)

    print(f"\n✓ Ground truth saved to {output_path}")
    print(f"Total chunk IDs: {len(generator.results)}")

    # Show sample
    sample_id = list(generator.results.keys())[0]
    print(f"\nSample queries for chunk '{sample_id}':")
    for i, query in enumerate(generator.results[sample_id], 1):
        print(f"  {i}. {query}")


if __name__ == "__main__":
    generate_mma_ground_truth()
