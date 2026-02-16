#!/usr/bin/env python3
"""Generate compact exam version from PDF with questions."""
import fire
import fitz  # PyMuPDF
import re
from pathlib import Path


def extract_compact_exam(pdf_path: str):
    """Extract questions, options, and correct answers from PDF."""
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    doc = fitz.open(pdf_path)
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
        
        # Find where options start - look for a pattern of 3-4 consecutive short lines
        # that look like service names (Amazon/AWS prefix or capitalized words)
        question_text = []
        options = []
        options_start_idx = None
        
        # Scan for where options likely start
        for idx in range(len(lines)):
            # Check if this could be the start of options
            # Options are typically 3-4 consecutive lines with AWS/Amazon or short capitalized text
            if idx + 2 < len(lines):
                potential_options = lines[idx:idx+4]
                # Check if these look like options (short, AWS/Amazon pattern)
                if all(len(opt) < 80 and 
                       (opt.startswith('Amazon ') or opt.startswith('AWS ') or 
                        re.match(r'^[A-Z][a-z]+\s+[A-Z]', opt) or
                        re.match(r'^[A-Z][a-zA-Z\s]+$', opt))
                       for opt in potential_options[:3]):
                    options_start_idx = idx
                    break
        
        if options_start_idx is not None:
            question_text = lines[:options_start_idx]
            options = lines[options_start_idx:]
        else:
            # Fallback: last 4 lines are likely options
            question_text = lines[:-4] if len(lines) > 4 else lines
            options = lines[-4:] if len(lines) > 4 else []
        
        # Build output - Version 1: No highlighting
        output_lines.append(f"Question {question_num}:")
        output_lines.append(' '.join(question_text))
        
        # Add options without highlighting
        for option in options:
            output_lines.append(f"- {option}")
        
        output_lines.append("")
        output_lines.append("=" * 70)
        output_lines.append("")
        
        # Build output - Version 2: With correct answer highlighted
        output_lines.append(f"Question {question_num}:")
        output_lines.append(' '.join(question_text))
        
        # Add options with correct answer in bold
        for option in options:
            # Bold the correct answer (check if option contains or matches correct answer)
            is_correct = False
            if correct_answer:
                # Check exact match or if correct answer is contained in option
                if option == correct_answer or correct_answer in option or option in correct_answer:
                    is_correct = True
            
            if is_correct:
                output_lines.append(f"- **{option}**")
            else:
                output_lines.append(f"- {option}")
        
        output_lines.append("")
        output_lines.append("=" * 70)
        output_lines.append("")
    
    # Save to markdown file
    output_file = pdf_file.with_suffix('.md')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    print(f"Compact exam version saved to: {output_file}")
    return str(output_file)


if __name__ == "__main__":
    fire.Fire(extract_compact_exam)
