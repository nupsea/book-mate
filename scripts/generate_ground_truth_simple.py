"""
Generate ground truth data by parsing files directly (same as evaluation does).

Usage:
    python scripts/generate_ground_truth_simple.py hegel
    python scripts/generate_ground_truth_simple.py mam
"""

import sys
from pathlib import Path
from src.content.ground_truth import GoldenDataGenerator
from src.content.reader import GutenbergReader, PDFReader


BOOK_CONFIGS = {
    "hegel": {
        "path": "DATA/Hegels-Philosophy.pdf",
        "pattern": None,  # PDFs don't use patterns
        "title": "Hegel's Philosophy of Mind",
        "is_pdf": True,
    },
    "mam": {
        "path": "DATA/meditations_marcus_aurelius.txt",
        "pattern": r"^(?:THE .* BOOK)\s*\n",
        "title": "Meditations by Marcus Aurelius",
        "is_pdf": False,
    },
}


def generate_ground_truth_for_book(slug: str):
    """Generate ground truth by parsing the file directly."""

    if slug not in BOOK_CONFIGS:
        print(f"❌ Error: Book '{slug}' not configured")
        print(f"\nAvailable books: {', '.join(BOOK_CONFIGS.keys())}")
        return False

    config = BOOK_CONFIGS[slug]
    print(f"\n{'='*80}")
    print(f"Generating Ground Truth for: {config['title']}")
    print(f"{'='*80}\n")

    # Parse chunks from file (same as evaluation does)
    print(f"Parsing: {config['path']}")

    if config["is_pdf"]:
        reader = PDFReader(config["path"], slug=slug, split_pattern=config["pattern"])
    else:
        reader = GutenbergReader(config["path"], slug=slug, split_pattern=config["pattern"])

    chunks = reader.parse(max_tokens=500, overlap=100)
    print(f"Loaded {len(chunks)} chunks\n")

    if len(chunks) == 0:
        print(f"❌ Error: No chunks found")
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
    print(f"Total chunks: {len(generator.results)}")

    # Show sample
    if generator.results:
        sample_id = list(generator.results.keys())[0]
        print(f"\nSample queries for chunk '{sample_id}':")
        for i, query in enumerate(generator.results[sample_id], 1):
            print(f"  {i}. {query}")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_ground_truth_simple.py <book_slug>")
        print("\nAvailable books:")
        for slug, config in BOOK_CONFIGS.items():
            print(f"  {slug:10s} - {config['title']}")
        sys.exit(1)

    book_slugs = sys.argv[1:]

    print(f"\nGenerating ground truth for {len(book_slugs)} book(s)\n")

    success_count = 0
    for slug in book_slugs:
        if generate_ground_truth_for_book(slug):
            success_count += 1

    print(f"\n{'='*80}")
    print(f"Summary: {success_count}/{len(book_slugs)} books completed")
    print(f"{'='*80}")
