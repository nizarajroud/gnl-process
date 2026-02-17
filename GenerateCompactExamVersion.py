#!/usr/bin/env python3
"""Generate compact exam version from PDF with questions."""
import fire
import fitz  # PyMuPDF
import re
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def extract_compact_exam(pdf_filename: str):
    """Extract questions, options, and correct answers from PDF.
    
    Args:
        pdf_filename: Name of the PDF file (without path)
    """
    # Get GNL_PROCESSING_PATH from environment
    gnl_processing_path = os.getenv('GNL_PROCESSING_PATH')
    if not gnl_processing_path:
        raise ValueError("GNL_PROCESSING_PATH not found in .env file")
    
    # Construct input path: GNL_PROCESSING_PATH/../pdf-formatting/pdf/filename
    base_path = Path(gnl_processing_path).parent
    pdf_path = base_path / "pdf-formatting" / "pdf" / pdf_filename
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Construct output path: GNL_PROCESSING_PATH/../Anki-generation/
    output_dir = base_path / "Anki-generation"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(str(pdf_path))
    full_text = ""
    
    # Extract all text from PDF
    for page in doc:
        full_text += page.get_text()
    
    doc.close()
    
    # Split by questions
    questions = re.split(r'(Question\s+\d+)', full_text)
    
    output_lines = []
    
    for i in range(1, len(questions), 2):
        if i + 1 >= len(questions):
            break
            
        question_header = questions[i].strip()
        question_content = questions[i + 1].strip()
        
        # Extract question number
        question_num = re.search(r'\d+', question_header).group()
        
        # Find CORRECT answer first
        correct_match = re.search(r'CORRECT:\s*(.+?)(?:\n|$)', question_content)
        correct_answer = correct_match.group(1).strip() if correct_match else None
        
        # Split content before CORRECT/INCORRECT
        content_before_answer = re.split(r'CORRECT:|INCORRECT:', question_content)[0]
        
        lines = content_before_answer.split('\n')
        lines = [l.strip() for l in lines if l.strip()]
        
        # Find the last question mark - everything before is question, everything after is options
        last_question_idx = -1
        for idx, line in enumerate(lines):
            if '?' in line:
                last_question_idx = idx
        
        if last_question_idx == -1:
            # No question mark found, assume last line is question
            question_text = lines[:-1] if len(lines) > 1 else lines
            options = lines[-1:] if len(lines) > 1 else []
        else:
            # Question is everything up to and including the line with ?
            question_text = lines[:last_question_idx + 1]
            # Options are all remaining lines
            options = lines[last_question_idx + 1:]
        
        # Build question text (front of card)
        front_text = f"<div style='text-align: left;'><b>Question {question_num}:</b><br><br>"
        front_text += ' '.join(question_text) + "<br><br>"
        for option in options:
            front_text += f"- {option}<br>"
        front_text += "</div>"
        
        # Build answer text (back of card - with correct answer highlighted)
        back_text = f"<div style='text-align: left;'><b>Question {question_num}:</b><br><br>"
        back_text += ' '.join(question_text) + "<br><br>"
        for option in options:
            is_correct = False
            if correct_answer:
                if option == correct_answer or correct_answer in option or option in correct_answer:
                    is_correct = True
            
            if is_correct:
                back_text += f"- <b>{option}</b><br>"
            else:
                back_text += f"- {option}<br>"
        back_text += "</div>"
        
        # Add to Anki format: Front TAB Back
        output_lines.append(f"{front_text}\t{back_text}")
    
    # Save to text file for Anki import
    output_file = output_dir / pdf_path.with_suffix('.txt').name
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    print(f"Anki cards saved to: {output_file}")
    print(f"\nImport into Anki:")
    print(f"  1. Create a deck with your desired name")
    print(f"  2. File → Import → Select {output_file.name}")
    print(f"  3. Type: Basic")
    print(f"  4. Deck: Select your created deck")
    print(f"  5. Fields separated by: Tab")
    print(f"  6. Field 1 → Front, Field 2 → Back")
    print(f"  7. Allow HTML in fields: Yes")
    print(f"  8. Import")
    return str(output_file)


if __name__ == "__main__":
    fire.Fire(extract_compact_exam)
