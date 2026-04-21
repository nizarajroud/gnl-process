#!/usr/bin/env python3
"""Extract a subset of questions with their explanations from a PDF file.

Usage:
    python extract-subset-of-questions.py <filename> <questions>

Examples:
    python extract-subset-of-questions.py my-exam "3, 8, 10, 15, 16, 17"
    python extract-subset-of-questions.py aws-saa-practice "1, 5, 20"
"""

import fire
import os
import re
import sys
import fitz  # PyMuPDF
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def extract_questions(filename: str, questions: str):
    """Extract specific questions from a PDF and save to a new file.

    Args:
        filename: Name of the PDF file without extension
        questions: Comma-separated question numbers (e.g. "3, 8, 10, 15, 16, 17")
    """
    gnl_processing_path = os.getenv('GNL_PROCESSING_PATH')
    if not gnl_processing_path:
        raise ValueError("GNL_PROCESSING_PATH not found in .env file")

    base_path = Path(gnl_processing_path)
    pdf_file = base_path / ".." / ".." / "exam" / f"{filename}.pdf"

    if not pdf_file.exists():
        print(f"Error: PDF not found: {pdf_file}")
        sys.exit(1)

    # Parse question numbers (fire may pass a tuple or a string)
    if isinstance(questions, (tuple, list)):
        question_nums = sorted(set(int(q) for q in questions))
    else:
        question_nums = sorted(set(int(q.strip()) for q in str(questions).split(",")))
    print(f"Extracting questions: {question_nums}")

    doc = fitz.open(str(pdf_file))

    # Find all question positions
    question_positions = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        for q_num in range(1, 500):
            for search_text in [f"Question {q_num}", f"Question{q_num}", f"Question-{q_num}"]:
                text_instances = page.search_for(search_text)
                if text_instances:
                    question_positions.append((q_num, page_num, text_instances[0].y0))
                    break

    # Deduplicate, keep first occurrence
    seen = set()
    unique_positions = []
    for q_num, page_num, y_coord in question_positions:
        if q_num not in seen:
            seen.add(q_num)
            unique_positions.append((q_num, page_num, y_coord))
    unique_positions.sort()

    if not unique_positions:
        print("Error: No questions found in PDF")
        sys.exit(1)

    print(f"Total questions found in PDF: {len(unique_positions)}")

    # Build a lookup: q_num -> (start_page, start_y, end_page, end_y)
    pos_map = {}
    for idx, (q_num, page_num, y_coord) in enumerate(unique_positions):
        if idx + 1 < len(unique_positions):
            _, end_page, end_y = unique_positions[idx + 1]
        else:
            end_page = len(doc) - 1
            end_y = None  # means end of document
        pos_map[q_num] = (page_num, y_coord, end_page, end_y)

    # Validate requested questions exist
    missing = [q for q in question_nums if q not in pos_map]
    if missing:
        print(f"Warning: Questions not found in PDF: {missing}")
        question_nums = [q for q in question_nums if q in pos_map]

    if not question_nums:
        print("Error: None of the requested questions were found")
        sys.exit(1)

    # Extract each question into the output PDF
    output_doc = fitz.open()

    for q_num in question_nums:
        start_page, start_y, end_page, end_y = pos_map[q_num]

        for page_num in range(start_page, end_page + 1):
            src_page = doc[page_num]

            if page_num == start_page and page_num == end_page and end_y is not None:
                crop_rect = fitz.Rect(0, start_y, src_page.rect.width, end_y)
            elif page_num == start_page:
                crop_rect = fitz.Rect(0, start_y, src_page.rect.width, src_page.rect.height)
            elif page_num == end_page and end_y is not None:
                crop_rect = fitz.Rect(0, 0, src_page.rect.width, end_y)
            else:
                crop_rect = src_page.rect

            new_page = output_doc.new_page(width=src_page.rect.width, height=crop_rect.height)
            new_page.show_pdf_page(new_page.rect, doc, page_num, clip=crop_rect)

    # Save output
    output_dir = base_path / ".." / "subset-questions-extraction"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"extracted questions {pdf_file.name}"
    output_doc.save(str(output_path))
    output_doc.close()
    doc.close()

    print(f"✓ Extracted {len(question_nums)} questions to: {output_path}")


if __name__ == "__main__":
    fire.Fire(extract_questions)
