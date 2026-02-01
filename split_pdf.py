#!/usr/bin/env python3
import fire
import os
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
from dotenv import load_dotenv

load_dotenv()


def split_pdf(pdf_path: str, pages_per_split: int):
    """Split PDF into chunks of X pages.
    
    Args:
        pdf_path: Path to the PDF file without extension (relative to LOCAL_STORAGE_PATH)
        pages_per_split: Number of pages per split file
    """
    local_storage = os.getenv("LOCAL_STORAGE_PATH")
    pdf_file = Path(local_storage) / f"{pdf_path}.pdf"
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    pdf_name = pdf_file.stem
    output_dir = pdf_file.parent / pdf_name
    output_dir.mkdir(exist_ok=True)
    
    reader = PdfReader(pdf_file)
    total_pages = len(reader.pages)
    
    for start in range(0, total_pages, pages_per_split):
        end = min(start + pages_per_split, total_pages)
        writer = PdfWriter()
        
        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])
        
        part_num = (start // pages_per_split) + 1
        output_file = output_dir / f"p{part_num}.pdf"
        with open(output_file, "wb") as f:
            writer.write(f)
        
        print(f"Created: {output_file}")
    
    # Move original file to zzz folder
    zzz_dir = pdf_file.parent / "zzz"
    zzz_dir.mkdir(exist_ok=True)
    pdf_file.rename(zzz_dir / pdf_file.name)
    print(f"Moved original to: {zzz_dir / pdf_file.name}")


if __name__ == "__main__":
    fire.Fire(split_pdf)
