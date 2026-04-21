#!/usr/bin/env python3
"""Merge all extracted question PDFs into a single file.

Usage:
    python merge-pdf-files.py
"""

import fire
import os
import sys
import fitz  # PyMuPDF
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def merge_pdfs():
    """Merge all PDF files in subset-questions-extraction into one file."""
    gnl_processing_path = os.getenv('GNL_PROCESSING_PATH')
    if not gnl_processing_path:
        raise ValueError("GNL_PROCESSING_PATH not found in .env file")

    input_dir = Path(gnl_processing_path) / ".." / "subset-questions-extraction"

    if not input_dir.exists():
        print(f"Error: Directory not found: {input_dir}")
        sys.exit(1)

    pdf_files = sorted(input_dir.glob("*.pdf"))
    # Exclude the output file itself if it already exists
    pdf_files = [f for f in pdf_files if f.name != "all extracted questions.pdf"]

    if not pdf_files:
        print("Error: No PDF files found to merge")
        sys.exit(1)

    print(f"Merging {len(pdf_files)} PDF files:")
    for f in pdf_files:
        print(f"  - {f.name}")

    output_doc = fitz.open()
    for pdf_file in pdf_files:
        doc = fitz.open(str(pdf_file))
        output_doc.insert_pdf(doc)
        doc.close()

    output_path = input_dir / "all extracted questions.pdf"
    output_doc.save(str(output_path))
    output_doc.close()

    print(f"✓ Merged into: {output_path}")


if __name__ == "__main__":
    fire.Fire(merge_pdfs)
