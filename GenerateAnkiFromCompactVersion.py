#!/usr/bin/env python3
"""Generate Anki flashcards from compact Markdown exam file."""
import fire
import re
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def generate_anki_from_markdown(filename: str):
    """Convert compact Markdown exam to Anki flashcard format.
    
    Args:
        filename: Name of the file without extension (e.g., 'exam' not 'exam.md')
    """
    # Get GNL_PROCESSING_PATH from environment
    gnl_processing_path = os.getenv('GNL_PROCESSING_PATH')
    if not gnl_processing_path:
        raise ValueError("GNL_PROCESSING_PATH not found in .env file")
    
    # Construct input path: GNL_PROCESSING_PATH/../Anki-generation/markdown/filename.md
    base_path = Path(gnl_processing_path).parent
    markdown_path = base_path / "Anki-generation" / "markdown" / f"{filename}.md"
    
    if not markdown_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_path}")
    
    # Construct output path: GNL_PROCESSING_PATH/../Anki-generation/anki/
    output_dir = base_path / "Anki-generation" / "anki"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Read markdown file
    with open(markdown_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by **Question pattern to separate questions
    question_blocks = re.split(r'(\*\*Question\s+\d+:\*\*)', content)
    
    output_lines = []
    
    # Process pairs of (header, content)
    for i in range(1, len(question_blocks), 2):
        if i + 1 >= len(question_blocks):
            break
        
        question_header = question_blocks[i]
        question_content = question_blocks[i + 1]
        
        # Combine header and content
        question_block = question_header + question_content
        
        if not question_block.strip():
            continue
        
        lines = [l.strip() for l in question_block.strip().split('\n') if l.strip()]
        
        if not lines:
            continue
        
        # Extract question number and text
        question_line = lines[0]
        question_match = re.match(r'\*\*Question\s+(\d+):\*\*', question_line)
        if not question_match:
            continue
        
        question_num = question_match.group(1)
        
        # Find where options start (lines starting with -)
        question_text_lines = []
        options = []
        
        in_options = False
        for line in lines[1:]:
            if line.startswith('- '):
                in_options = True
                # Remove markdown bold markers for comparison
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
        
        # Add to Anki format: Front TAB Back
        output_lines.append(f"{front_text}\t{back_text}")
    
    # Save to text file for Anki import
    output_file = output_dir / f"{filename}.txt"
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
    fire.Fire(generate_anki_from_markdown)
