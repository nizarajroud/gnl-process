#!/usr/bin/env python3
"""Generate Anki flashcards from PDF exam - complete workflow."""
import fire
import fitz  # PyMuPDF
import re
import os
import subprocess
import markdown
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
from weasyprint import HTML

load_dotenv()


def generate_anki_cards(foldername: str, origin: str = 'udemy'):
    """Complete workflow: Use existing markdown → Generate Anki cards.
    
    Args:
        foldername: Name of the markdown file (e.g., 'exam')
        origin: Source of the exam - 'udemy' or 'dojo' (default: 'udemy')
    """
    if origin.lower() not in ['udemy', 'dojo']:
        raise ValueError("origin must be 'udemy' or 'dojo'")
    
    origin = origin.lower()
    
    # Get GNL_PROCESSING_PATH from environment
    gnl_processing_path = os.getenv('GNL_PROCESSING_PATH')
    if not gnl_processing_path:
        raise ValueError("GNL_PROCESSING_PATH not found in .env file")
    
    base_path = Path(gnl_processing_path).parent
    
    # Use existing markdown file (same for both Udemy and Dojo)
    print(f"Using existing markdown file for {origin} mode...")
    
    # Markdown file should already exist
    markdown_file = str(base_path / "Anki-generation" / "markdown" / f"{foldername}.md")
    
    if not Path(markdown_file).exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_file}")
    
    print(f"✓ Using markdown: {markdown_file}")
    
    # Generate Anki cards from Markdown
    print(f"\nGenerating Anki flashcards...")
    anki_file = generate_anki_from_markdown(foldername, base_path, markdown_file)
    print(f"✓ Anki cards saved: {anki_file}")
    
    print(f"\n{'='*60}")
    print(f"✓ Complete! Anki cards generated from markdown")
    print(f"  - Anki: {anki_file}")
    print(f"{'='*60}")


def extract_to_markdown(foldername: str, base_path: Path):
    """Extract questions from PDF splits to Markdown using Bedrock API key."""
    # Input: PDF splits folder
    splits_folder = Path(os.getenv("PDF_PARTS_FOLDER", "PDF-Parts")) / "exam" / foldername
    if not splits_folder.exists():
        raise FileNotFoundError(f"Splits folder not found: {splits_folder}")
    
    # Get all PDF splits (q1.pdf, q2.pdf, etc.) in order
    pdf_splits = sorted(splits_folder.glob("q*.pdf"), key=lambda x: int(x.stem[1:]))
    
    if not pdf_splits:
        raise FileNotFoundError(f"No PDF splits found in: {splits_folder}")
    
    print(f"Found {len(pdf_splits)} PDF splits to process...")
    
    # Output: Markdown
    output_dir = base_path / "Anki-generation" / "markdown"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get Bedrock config
    model_id = os.getenv('MOEDL_INFERENCE_ID', 'global.anthropic.claude-opus-4-5-20251101-v1:0')
    api_key = os.getenv('AWS_BEARER_TOKEN_BEDROCK', '')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    if not api_key:
        raise Exception("AWS_BEARER_TOKEN_BEDROCK not found in .env file")
    
    # Prepare prompt
    prompt = """You are a text extraction tool. Your ONLY job is to find and mark options based on keywords.

STRICT RULES - DO NOT DEVIATE:
1. Search the PDF for the exact keywords "CORRECT:" and "INCORRECT:" before each option
2. Bold EVERY option that has "CORRECT:" before it (use **text** format)
3. Do NOT bold options that have "INCORRECT:" before them
4. Do NOT use your knowledge or reasoning to determine answers
5. Do NOT analyze the question content
6. ONLY look for the literal keywords "CORRECT:" and "INCORRECT:"
7. If a question has multiple options with "CORRECT:", bold ALL of them

Your task is pure keyword matching, not comprehension.

Output format:
**Question N:**
[Question text exactly as written]

- Option text (when you see INCORRECT: before it)
- **Option text** (when you see CORRECT: before it)
- **Another option** (when you see CORRECT: before it)

Extract all questions now using ONLY keyword matching:"""
    
    # Process each split and collect markdown
    all_markdown = []
    
    for i, pdf_split in enumerate(pdf_splits, 1):
        print(f"  Processing {pdf_split.name}...")
        
        # Read PDF as bytes
        with open(pdf_split, 'rb') as f:
            pdf_bytes = f.read()
        
        # Prepare request
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "document": {
                                "format": "pdf",
                                "name": "Exam Questions",
                                "source": {
                                    "bytes": base64.b64encode(pdf_bytes).decode('utf-8')
                                }
                            }
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "inferenceConfig": {
                "maxTokens": 64000,
                "temperature": 0.1
            }
        }
        
        # Call Bedrock API
        import requests
        
        url = f"https://bedrock-runtime.{aws_region}.amazonaws.com/model/{model_id}/converse"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            markdown_content = result['output']['message']['content'][0]['text']
            all_markdown.append(markdown_content)
        else:
            raise Exception(f"Bedrock API error for {pdf_split.name}: {response.status_code} - {response.text}")
    
    # Combine all markdown
    combined_markdown = "\n\n".join(all_markdown)
    
    # Save markdown
    output_file = output_dir / f"{foldername}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(combined_markdown)
    
    return str(output_file), []


def generate_compact_pdf(filename: str, base_path: Path, markdown_file: str):
    """Generate compact PDF from Markdown."""
    # Read markdown
    with open(markdown_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert to HTML
    html_content = markdown.markdown(md_content)
    
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                margin: 40px;
            }}
            ul {{
                list-style-type: none;
                padding-left: 20px;
            }}
            li::before {{
                content: "• ";
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # Generate PDF
    pdf_output_dir = base_path / "pdf-formatting" / "compact-exam-versions"
    pdf_output_dir.mkdir(parents=True, exist_ok=True)
    output_pdf = pdf_output_dir / f"{filename}.pdf"
    HTML(string=styled_html).write_pdf(output_pdf)
    
    return str(output_pdf)


def generate_anki_from_markdown(filename: str, base_path: Path, markdown_file: str):
    """Generate Anki flashcards from Markdown."""
    # Read markdown
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by **Question pattern
    question_blocks = re.split(r'(\*\*Question\s+\d+:\*\*)', content)
    
    output_lines = []
    
    for i in range(1, len(question_blocks), 2):
        if i + 1 >= len(question_blocks):
            break
        
        question_header = question_blocks[i]
        question_content = question_blocks[i + 1]
        question_block = question_header + question_content
        
        if not question_block.strip():
            continue
        
        lines = [l.strip() for l in question_block.strip().split('\n') if l.strip()]
        
        if not lines:
            continue
        
        # Extract question number
        question_line = lines[0]
        question_match = re.match(r'\*\*Question\s+(\d+):\*\*', question_line)
        if not question_match:
            continue
        
        question_num = question_match.group(1)
        
        # Find options
        question_text_lines = []
        options = []
        
        in_options = False
        for line in lines[1:]:
            if line.startswith('- '):
                in_options = True
                option_text = line[2:].replace('**', '')
                is_bold = '**' in line
                options.append((option_text, is_bold))
            elif not in_options:
                question_text_lines.append(line)
        
        question_text = ' '.join(question_text_lines)
        
        # Build front card (no highlighting)
        front_text = f"<div style='text-align: left;'><b>Question {question_num}:</b><br><br>"
        front_text += question_text + "<br><br>"
        for option_text, _ in options:
            front_text += f"- {option_text}<br>"
        front_text += "</div>"
        
        # Build back card (with correct answer highlighted)
        back_text = f"<div style='text-align: left;'><b>Question {question_num}:</b><br><br>"
        back_text += question_text + "<br><br>"
        for option_text, is_bold in options:
            if is_bold:
                back_text += f"- <b>{option_text}</b><br>"
            else:
                back_text += f"- {option_text}<br>"
        back_text += "</div>"
        
        output_lines.append(f"{front_text}\t{back_text}")
    
    # Save Anki file
    output_dir = base_path / "Anki-generation" / "anki"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{filename}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    return str(output_file)


if __name__ == "__main__":
    fire.Fire(generate_anki_cards)
