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
    
    gnl_processing_path = os.getenv("GNL_PROCESSING_PATH")
    pdf_name = pdf_file.stem
    
    # Create main folder
    main_folder = Path(gnl_processing_path) / pdf_name
    if main_folder.exists():
        shutil.rmtree(main_folder)
    main_folder.mkdir(exist_ok=True)
    
    # Copy original PDF to main folder
    shutil.copy2(pdf_file, main_folder / pdf_file.name)
    
    # Create subfolders
    pdf_parts_dir = main_folder / "PDF-Parts"
    audio_parts_dir = main_folder / "Audio-Parts"
    pdf_parts_dir.mkdir(exist_ok=True)
    audio_parts_dir.mkdir(exist_ok=True)
    
    output_dir = pdf_parts_dir
    
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
