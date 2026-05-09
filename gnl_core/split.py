"""Split PDF into chunks."""

import json
import os
import re
import shutil
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter


def split(pdf_path, pages_per_split, name, source_type="LocalStorage", podcast_theme="", podcast_subtheme=""):
    """Split a PDF into page-based chunks. Returns list of file dicts."""
    podcast_subtheme = podcast_subtheme.lower()
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pdf_parts_folder = os.getenv("PDF_PARTS_FOLDER", "PDF-Parts")
    output_dir = Path(pdf_parts_folder) / podcast_subtheme / name

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

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
            "parentDir": name,
            "fileName": f"p{part_num}.pdf",
            "sourceType": source_type,
            "podcastTheme": podcast_theme,
            "podcastSubfolder": podcast_subtheme
        })

    reader.stream.close()
    num_chunks = len(files_list)
    return {
        "mode": "bulk",
        "splitConfiguration": f"{num_chunks}ck-{pages_per_split}p",
        "files": files_list
    }
