"""Split PDF into chunks."""

import json
import os
import re
import shutil
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter


def split(pdf_path, pages_per_split, name, source_type="LocalStorage", podcast_theme="", podcast_subtheme="", mode="pages"):
    """Split a PDF into chunks. mode='pages' or 'semantic'."""
    podcast_subtheme = podcast_subtheme.lower()
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if mode == "semantic":
        return _split_semantic(pdf_path, name, source_type, podcast_theme, podcast_subtheme)
    return _split_pages(pdf_path, pages_per_split, name, source_type, podcast_theme, podcast_subtheme)


def _split_pages(pdf_path, pages_per_split, name, source_type, podcast_theme, podcast_subtheme):
    """Split by fixed page count."""
    pdf_parts_folder = os.getenv("PDF_PARTS_FOLDER", "PDF-Parts")
    output_dir = Path(pdf_parts_folder) / podcast_subtheme / name

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(pdf_path)
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
    return {
        "mode": "bulk",
        "splitConfiguration": f"{len(files_list)}ck-{pages_per_split}p",
        "files": files_list
    }


def _split_semantic(pdf_path, name, source_type, podcast_theme, podcast_subtheme):
    """Split by semantic sections using Claude via Bedrock."""
    import fitz
    import boto3

    # Extract text with page numbers
    doc = fitz.open(pdf_path)
    pages_text = []
    for i, page in enumerate(doc):
        pages_text.append(f"--- PAGE {i+1} ---\n{page.get_text()}")
    full_text = "\n".join(pages_text)
    total_pages = len(doc)
    doc.close()

    # Ask Claude for split points
    split_pages = _get_split_points_from_bedrock(full_text, total_pages)

    # Create PDF chunks
    pdf_parts_folder = os.getenv("PDF_PARTS_FOLDER", "PDF-Parts")
    output_dir = Path(pdf_parts_folder) / podcast_subtheme / name

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(pdf_path)
    files_list = []

    for part_num, (start, end) in enumerate(split_pages, 1):
        writer = PdfWriter()
        for page_num in range(start - 1, end):  # split_pages is 1-indexed
            writer.add_page(reader.pages[page_num])

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
    return {
        "mode": "bulk",
        "splitConfiguration": f"{len(files_list)}ck-semantic",
        "files": files_list
    }


def _get_split_points_from_bedrock(text, total_pages):
    """Use Claude via Bedrock to identify section boundaries. Returns list of (start_page, end_page) tuples."""
    import boto3, json

    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))

    prompt = f"""Analyze this document and identify the logical section boundaries for splitting into podcast episodes.
Each section should contain one or more complete topics (never cut in the middle of a topic).
Target: 3-8 pages per section. Minimum 2 pages, maximum 10 pages.
Total pages: {total_pages}

Return ONLY a JSON array of objects with "start" and "end" page numbers (1-indexed).
Example: [{{"start": 1, "end": 5}}, {{"start": 6, "end": 12}}]

Document:
{text[:50000]}"""

    response = client.converse(
        modelId=os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 1000}
    )

    result_text = response["output"]["message"]["content"][0]["text"]

    # Extract JSON from response
    match = re.search(r'\[.*\]', result_text, re.DOTALL)
    if match:
        sections = json.loads(match.group())
        return [(s["start"], s["end"]) for s in sections]

    # Fallback: split evenly into ~5-page chunks
    chunks = []
    for i in range(0, total_pages, 5):
        chunks.append((i + 1, min(i + 5, total_pages)))
    return chunks
