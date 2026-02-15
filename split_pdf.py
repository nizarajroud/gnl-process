#!/usr/bin/env python3
import fire
import os
import json
import shutil
import sys
import time
import re
import fitz  # PyMuPDF
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
from dotenv import load_dotenv

load_dotenv()


def split_pdf(pdf_path: str, pages_per_split: int = 0, name: str = "", split_mode: str = "Pages", question_parSplit: int = 3, source_type: str = "LocalStorage", podcast_theme: str = "", podcast_subtheme: str = ""):
    """Split PDF into chunks.
    
    Args:
        pdf_path: Full absolute path to the PDF file including extension
        pages_per_split: Number of pages per split file (required for Pages mode)
        name: Name for the inner folder
        split_mode: Split mode - "Pages" or "Questions" (default: "Pages")
        question_parSplit: Number of questions per split in Questions mode (default: 3)
        source_type: Source type for JSON output
        podcast_theme: Podcast theme for JSON output
        podcast_subtheme: Podcast subfolder for JSON output
    """
    if split_mode not in ["Pages", "Questions"]:
        raise ValueError(f"Invalid split_mode: {split_mode}. Must be 'Pages' or 'Questions'")
    
    if split_mode == "Pages" and pages_per_split <= 0:
        raise ValueError("pages_per_split must be greater than 0 for Pages mode")
    
    if split_mode == "Questions" and question_parSplit <= 0:
        raise ValueError("question_parSplit must be greater than 0 for Questions mode")
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    gnl_processing_path = os.getenv("GNL_PROCESSING_PATH")
    
    # Use GNL_PROCESSING_PATH/PDF-Parts/podcast_subtheme/name
    output_dir = Path(gnl_processing_path) / "PDF-Parts" / podcast_subtheme / name
    
    # Remove existing folder if it exists
    if output_dir.exists():
        shutil.rmtree(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    reader = PdfReader(pdf_file)
    total_pages = len(reader.pages)
    
    files_list = []
    
    print(f"Split mode: {split_mode}", file=sys.stderr, flush=True)
    
    if split_mode == "Pages":
        print(f"Total pages: {total_pages}", file=sys.stderr, flush=True)
        num_chunks = 0
        for start in range(0, total_pages, pages_per_split):
            end = min(start + pages_per_split, total_pages)
            writer = PdfWriter()
            
            for page_num in range(start, end):
                writer.add_page(reader.pages[page_num])
            
            part_num = (start // pages_per_split) + 1
            num_chunks = part_num
            output_file = output_dir / f"p{part_num}.pdf"
            with open(output_file, "wb") as f:
                writer.write(f)
            
            files_list.append({
                "fullPath": str(output_file),
                "parentDir": name,
                "fileName": f"p{part_num}.pdf",
                "downloadState": False,
                "sourceType": source_type,
                "podcastTheme": podcast_theme,
                "podcastSubfolder": podcast_subtheme
            })
        
        split_configuration = f"{num_chunks}ck-{pages_per_split}p"
    
    elif split_mode == "Questions":
        # Close PyPDF2 reader
        reader.stream.close()
        
        # Use PyMuPDF for content-based extraction
        doc = fitz.open(pdf_path)
        question_pattern = re.compile(r'Question\s*[-\s]?(\d+)', re.IGNORECASE)
        
        # Find all question positions with their text locations
        question_positions = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Search for "Question" followed by number
            for q_num in range(1, 200):  # Assume max 200 questions
                for search_text in [f"Question{q_num}", f"Question {q_num}", f"Question-{q_num}"]:
                    text_instances = page.search_for(search_text)
                    if text_instances:
                        rect = text_instances[0]
                        question_positions.append((q_num, page_num, rect.y0))
                        break
        
        # Remove duplicates, keep first occurrence
        seen = set()
        unique_positions = []
        for q_num, page_num, y_coord in question_positions:
            if q_num not in seen:
                seen.add(q_num)
                unique_positions.append((q_num, page_num, y_coord))
        
        unique_positions.sort()
        
        if not unique_positions:
            raise ValueError("No questions found in PDF")
        
        print(f"Total questions found: {len(unique_positions)}", file=sys.stderr, flush=True)
        
        # Split into chunks
        part_num = 1
        num_chunks = 0
        for i in range(0, len(unique_positions), question_parSplit):
            chunk_questions = unique_positions[i:i + question_parSplit]
            start_q_num, start_page, start_y = chunk_questions[0]
            
            # Determine end position
            if i + question_parSplit < len(unique_positions):
                end_q_num, end_page, end_y = unique_positions[i + question_parSplit]
            else:
                end_page = len(doc) - 1
                end_y = None
            
            # Create new PDF with cropped content
            output_doc = fitz.open()
            
            for page_num in range(start_page, end_page + 1):
                src_page = doc[page_num]
                
                # Determine crop rectangle for this page
                if page_num == start_page and page_num == end_page and end_y is not None:
                    # Same page: crop from start_y to end_y
                    crop_rect = fitz.Rect(0, start_y, src_page.rect.width, end_y)
                elif page_num == start_page:
                    # First page: crop from start_y to bottom
                    crop_rect = fitz.Rect(0, start_y, src_page.rect.width, src_page.rect.height)
                elif page_num == end_page and end_y is not None:
                    # Last page: crop from top to end_y (where next question starts)
                    crop_rect = fitz.Rect(0, 0, src_page.rect.width, end_y)
                else:
                    # Middle pages: include entire page
                    crop_rect = src_page.rect
                
                # Create new page with cropped content
                new_page = output_doc.new_page(width=src_page.rect.width, height=crop_rect.height)
                new_page.show_pdf_page(new_page.rect, doc, page_num, clip=crop_rect)
            
            output_file = output_dir / f"q{part_num}.pdf"
            output_doc.save(str(output_file))
            output_doc.close()
            
            files_list.append({
                "fullPath": str(output_file),
                "parentDir": name,
                "fileName": f"q{part_num}.pdf",
                "downloadState": False,
                "sourceType": source_type,
                "podcastTheme": podcast_theme,
                "podcastSubfolder": podcast_subtheme
            })
            
            num_chunks = part_num
            part_num += 1
        
        split_configuration = f"{num_chunks}ck-{question_parSplit}q"
        doc.close()
    
    # Close reader to release file handle (only for Pages mode)
    if split_mode == "Pages":
        reader.stream.close()
    
    # Output JSON
    output = {
        "mode": "bulk",
        "splitConfiguration": split_configuration,
        "files": files_list
    }
    print(json.dumps(output))


if __name__ == "__main__":
    fire.Fire(split_pdf)
