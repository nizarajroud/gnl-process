#!/usr/bin/env python3
import fire
import os
import json
import shutil
import time
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
from dotenv import load_dotenv

load_dotenv()


def split_pdf(pdf_path: str, pages_per_split: int, source_type: str = "LocalStorage", podcast_theme: str = "", podcast_subfolder: str = ""):
    """Split PDF into chunks of X pages.
    
    Args:
        pdf_path: Full absolute path to the PDF file including extension
        pages_per_split: Number of pages per split file
        source_type: Source type for JSON output
        podcast_theme: Podcast theme for JSON output
        podcast_subfolder: Podcast subfolder for JSON output
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    pdf_name = pdf_file.stem
    output_dir = pdf_file.parent / pdf_name
    
    # Remove existing output directory if it exists
    if output_dir.exists():
        shutil.rmtree(output_dir)
    
    output_dir.mkdir(exist_ok=True)
    
    reader = PdfReader(pdf_file)
    total_pages = len(reader.pages)
    
    files_list = []
    
    for start in range(0, total_pages, pages_per_split):
        end = min(start + pages_per_split, total_pages)
        writer = PdfWriter()
        
        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])
        
        part_num = (start // pages_per_split) + 1
        output_file = output_dir / f"p{part_num}.pdf"
        with open(output_file, "wb") as f:
            writer.write(f)
        
        files_list.append({
            "fullPath": str(output_file),
            "parentDir": pdf_name,
            "fileName": f"p{part_num}.pdf",
            "downloadState": False,
            "sourceType": source_type,
            "podcastTheme": podcast_theme,
            "podcastSubfolder": podcast_subfolder
        })
    
    # Close reader to release file handle
    reader.stream.close()
    
    # Output JSON
    output = {
        "mode": "bulk",
        "files": files_list
    }
    print(json.dumps(output))


if __name__ == "__main__":
    fire.Fire(split_pdf)
