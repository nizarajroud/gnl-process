#!/usr/bin/env python3
"""Generate Anki flashcards from PDF exam - complete workflow."""
import fire
import fitz  # PyMuPDF
import re
import os
import subprocess
import markdown
from pathlib import Path
from dotenv import load_dotenv
from weasyprint import HTML

load_dotenv()


def generate_anki_cards(filename: str):
    """Complete workflow: PDF → Markdown → PDF compact → Anki cards.
    
    Args:
        filename: Name of the file without extension (e.g., 'exam')
    """
    # Get GNL_PROCESSING_PATH from environment
    gnl_processing_path = os.getenv('GNL_PROCESSING_PATH')
    if not gnl_processing_path:
        raise ValueError("GNL_PROCESSING_PATH not found in .env file")
    
    base_path = Path(gnl_processing_path).parent
    
    # Step 1: Extract from PDF to Markdown
    print(f"Step 1: Extracting questions from PDF...")
    markdown_file, unmatched_questions = extract_to_markdown(filename, base_path)
    print(f"✓ Markdown saved: {markdown_file}")
    
    # Step 2: Generate PDF from Markdown
    print(f"\nStep 2: Generating compact PDF...")
    pdf_file = generate_compact_pdf(filename, base_path, markdown_file)
    print(f"✓ PDF saved: {pdf_file}")
    
    # Step 3: Generate Anki cards from Markdown
    print(f"\nStep 3: Generating Anki flashcards...")
    anki_file = generate_anki_from_markdown(filename, base_path, markdown_file)
    print(f"✓ Anki cards saved: {anki_file}")
    
    print(f"\n{'='*60}")
    print(f"✓ Complete! All files generated:")
    print(f"  - Markdown: {markdown_file}")
    print(f"  - PDF: {pdf_file}")
    print(f"  - Anki: {anki_file}")
    print(f"{'='*60}")
    
    if unmatched_questions:
        pdf_windows_path = str(base_path / 'pdf-formatting' / 'pdf' / f'{filename}.pdf').replace('/mnt/d/', 'D:/')
        print(f"\n⚠ RECAP - Questions with unmatched correct answers:")
        print(f"  File: {filename}.pdf")
        print(f"  Path: {pdf_windows_path}")
        for q_num in unmatched_questions:
            print(f"  - Question {q_num}")
        # print(f"\n  Opening PDF...")
        # subprocess.run(['cmd.exe', '/c', 'start', '', pdf_windows_path], check=False)
        print(f"{'='*60}")


def extract_to_markdown(filename: str, base_path: Path):
    """Extract questions from PDF to Markdown."""
    # Input: PDF
    pdf_path = base_path / "pdf-formatting" / "pdf" / f"{filename}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Output: Markdown
    output_dir = base_path / "Anki-generation" / "markdown"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(str(pdf_path))
    full_text = ""
    
    for page in doc:
        full_text += page.get_text()
    
    doc.close()
    
    # Split by questions
    questions = re.split(r'(Question\s+\d+)', full_text)
    
    output_lines = []
    unmatched_questions = []
    
    for i in range(1, len(questions), 2):
        if i + 1 >= len(questions):
            break
            
        question_header = questions[i].strip()
        question_content = questions[i + 1].strip()
        
        question_num = re.search(r'\d+', question_header).group()
        
        # Find CORRECT answer
        correct_match = re.search(r'CORRECT:\s*(.+?)(?:\n|$)', question_content)
        correct_answer = correct_match.group(1).strip() if correct_match else None
        
        # Split content before CORRECT/INCORRECT
        content_before_answer = re.split(r'CORRECT:|INCORRECT:', question_content)[0]
        
        lines = content_before_answer.split('\n')
        lines = [l.strip() for l in lines if l.strip()]
        
        # Find the last question mark
        last_question_idx = -1
        for idx, line in enumerate(lines):
            if '?' in line:
                last_question_idx = idx
        
        if last_question_idx == -1:
            continue
        
        # Question text
        question_text = lines[:last_question_idx + 1]
        options_lines = lines[last_question_idx + 1:]
        
        # Group options
        options = []
        current_option = []
        
        # Common option-starting patterns
        option_starters = ['Configure', 'Implement', 'Switch', 'Use', 'Create', 'Enable', 'Set', 
                          'Deploy', 'Migrate', 'Apply', 'Standard', 'Semantic', 'Hierarchical', 
                          'Multimodal', 'Fine-tune', 'Amazon ', 'AWS ']
        
        for line in options_lines:
            # Check if line contains multiple options (look for pattern: "text. Word" where Word starts option)
            # Split by ". " followed by capital letter that starts a known pattern
            potential_splits = []
            for starter in option_starters:
                # Find all occurrences of ". Starter" in the line
                pattern = r'\.\s+(' + re.escape(starter) + r'[^.]*)'
                matches = list(re.finditer(pattern, line))
                for match in matches:
                    potential_splits.append(match.start() + 1)  # Position after the period
            
            if potential_splits:
                # Sort split positions
                potential_splits = sorted(set(potential_splits))
                # Split the line at these positions
                parts = []
                last_pos = 0
                for pos in potential_splits:
                    parts.append(line[last_pos:pos].strip())
                    last_pos = pos
                parts.append(line[last_pos:].strip())
                
                # Process each part as a separate option
                for part in parts:
                    if part and len(part) > 5:
                        if current_option:
                            options.append(' '.join(current_option))
                        current_option = [part]
            else:
                # Normal processing
                if line and line[0].isupper() and (
                    any(line.startswith(verb) for verb in option_starters) or
                    (not current_option and len(line) > 5)
                ):
                    if current_option:
                        options.append(' '.join(current_option))
                    current_option = [line]
                else:
                    if current_option:
                        current_option.append(line)
        
        if current_option:
            options.append(' '.join(current_option))
        
        # Build markdown output
        output_lines.append(f"**Question {question_num}:**\n")
        output_lines.append(' '.join(question_text) + "\n\n")
        
        found_correct = False
        for option in options:
            is_correct = False
            if correct_answer and (option == correct_answer or correct_answer in option or option in correct_answer):
                is_correct = True
                found_correct = True
            
            if is_correct:
                output_lines.append(f"- **{option}**\n")
            else:
                output_lines.append(f"- {option}\n")
        
        if correct_answer and not found_correct:
            unmatched_questions.append(question_num)
        
        output_lines.append("\n")
    
    # Save markdown
    output_file = output_dir / f"{filename}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(''.join(output_lines))
    
    return str(output_file), unmatched_questions


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
