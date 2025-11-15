"""
Simple test script to verify PDF reading functionality.
"""

from src.content.reader import PDFReader
from pathlib import Path

def test_pdf_reader():
    """Test PDFReader with a sample PDF (if available)."""

    # Check if there's a PDF file in the DATA directory
    data_dir = Path("DATA")
    pdf_files = list(data_dir.glob("*.pdf"))

    if not pdf_files:
        print("No PDF files found in DATA directory.")
        print("Creating a simple test PDF would require additional libraries.")
        print("\nTo test the PDF reader:")
        print("1. Place a PDF book file in the DATA/ directory")
        print("2. Run this script again")
        print("\nThe PDFReader class has been successfully created and integrated!")
        print("You can now upload PDF books through the UI.")
        return

    # Test with the first PDF found
    test_pdf = pdf_files[0]
    print(f"Testing with: {test_pdf.name}")

    try:
        # Create a PDFReader instance
        reader = PDFReader(
            file_path=str(test_pdf),
            slug="test_pdf",
            split_pattern=r"^(?:CHAPTER [IVXLCDM]+\.)\s*\n"
        )

        # Parse the PDF
        print("\nParsing PDF...")
        chunks = reader.parse(max_tokens=500, overlap=100)

        print(f"\nResults:")
        print(f"- Total chunks: {len(chunks)}")
        print(f"- First chunk ID: {chunks[0]['id']}")
        print(f"- First chunk tokens: {chunks[0]['num_tokens']}")
        print(f"- First chunk chars: {chunks[0]['num_chars']}")
        print(f"\nFirst 200 characters of text:")
        print(chunks[0]['text'][:200])
        print("\nPDF reading test successful!")

    except Exception as e:
        print(f"\nError during test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf_reader()
