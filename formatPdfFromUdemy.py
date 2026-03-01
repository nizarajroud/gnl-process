from docx import Document
import re
import sys
import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def clean_dojo_document(input_path, output_path):
    """Remove References sections from Dojo documents."""
    doc = Document(input_path)
    
    # Extract all text
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    
    text = "\n".join(full_text)
    
    # Remove References sections (from "References:" to next question pattern)
    text = re.sub(r"References:.*?(?=Question|\Z)", "", text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove multiple blank lines
    text = re.sub(r"\n\s*\n", "\n", text)
    
    # Renumber all questions sequentially (handles both patterns and removes duplicates)
    lines = text.split('\n')
    result_lines = []
    question_counter = 0
    seen_questions = set()
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check if line matches "N. Question" pattern
        if re.match(r'^\d+\.\s*Question$', stripped):
            question_counter += 1
            result_lines.append(f"Question {question_counter}:")
            i += 1
        # Check if line matches standalone "Question" pattern
        elif re.match(r'^Question$', stripped):
            question_counter += 1
            result_lines.append(f"Question {question_counter}:")
            i += 1
        # Check if line is already formatted "Question N"
        elif re.match(r'^Question\s+\d+:?$', stripped):
            # Skip duplicates
            if stripped not in seen_questions:
                question_counter += 1
                result_lines.append(f"Question {question_counter}:")
                seen_questions.add(stripped)
            i += 1
        # Check if line contains "Select and order" pattern
        elif re.search(r'Select and order', stripped, re.IGNORECASE):
            result_lines.append(line)
            i += 1
            
            # Collect options until "Incorrect"
            options = []
            seen_options = set()
            while i < len(lines) and not lines[i].strip().startswith("Incorrect"):
                if lines[i].strip():
                    option_text = lines[i].strip()
                    # Only add if not a duplicate
                    if option_text not in seen_options:
                        options.append(option_text)
                        seen_options.add(option_text)
                i += 1
            
            # Add options as list
            for option in options:
                result_lines.append(f"- {option}")
            
            # Add "Explanations:" title
            result_lines.append("Explanations:")
            
            # Skip the "Incorrect" line
            if i < len(lines) and lines[i].strip().startswith("Incorrect"):
                i += 1
        # Check if line is "Incorrect" - format options before it
        elif stripped.startswith("Incorrect"):
            # Find the last question mark before this line
            last_question_idx = -1
            for j in range(len(result_lines) - 1, -1, -1):
                if '?' in result_lines[j]:
                    last_question_idx = j
                    break
            
            if last_question_idx != -1:
                # Extract options (lines between question and "Incorrect")
                options = []
                for j in range(last_question_idx + 1, len(result_lines)):
                    if result_lines[j].strip():
                        options.append(result_lines[j].strip())
                
                # Remove the option lines from result
                result_lines = result_lines[:last_question_idx + 1]
                
                # Add options as list items
                for option in options:
                    result_lines.append(f"- {option}")
                
                # Add "Explanations:" title
                result_lines.append("Explanations:")
            
            # Skip the "Incorrect" line
            i += 1
        else:
            result_lines.append(line)
            i += 1
    
    text = '\n'.join(result_lines)
    
    # Find correct answers and mark them in options
    lines_list = text.split('\n')
    correct_answers = []
    
    # Track if we're in a "Select and order" section
    in_select_section = False
    
    # Extract correct answers from "Hence, the correct answer" patterns
    for i, line in enumerate(lines_list):
        # Check if this is a "Select and order" question
        if re.search(r'Select and order', line, re.IGNORECASE):
            in_select_section = True
        # Reset when we hit a new question
        elif re.match(r'^Question\s+\d+:', line.strip()):
            in_select_section = False
        
        if re.search(r'Hence, the correct answers? (?:are|is):', line, re.IGNORECASE):
            # Extract inline answer if present
            match = re.search(r'Hence, the correct answers? (?:are|is):\s*(.+)', line, re.IGNORECASE)
            if match:
                answer_text = match.group(1).strip()
                if answer_text:
                    # Remove explanation text that starts with common patterns
                    # Stop at phrases like "This is", "It uses", "It provides", etc.
                    explanation_patterns = [
                        r'\.\s+(This|It|The|By|Using|With|For|In|To|As|Because|Since|Therefore|Thus|Hence)\s+',
                        r'\.\s+[A-Z][a-z]+\s+(is|are|provides|ensures|allows|enables|helps|supports)'
                    ]
                    for pattern in explanation_patterns:
                        split_match = re.search(pattern, answer_text)
                        if split_match:
                            answer_text = answer_text[:split_match.start() + 1].strip()
                            break
                    correct_answers.append(answer_text)
            
            # Check following lines for multi-line answers (lines starting with "–" or "-")
            for j in range(i + 1, min(i + 10, len(lines_list))):
                next_line = lines_list[j].strip()
                if re.match(r'^[–-]\s*', next_line) and not next_line.startswith('- '):
                    correct_answers.append(next_line)
                elif next_line and not next_line.startswith(('–', '-', 'The option')):
                    break
    
    # Mark options that match correct answers as bold
    marked_lines = []
    in_select_and_order = False
    
    for line in lines_list:
        # Check if we're in a "Select and order" section
        if re.search(r'Select and order', line, re.IGNORECASE):
            in_select_and_order = True
            marked_lines.append(("normal", line))
        # Check if this is an option line (starts with "- ")
        elif line.strip().startswith("- "):
            option_text = line.strip()[2:]  # Remove "- " prefix
            
            # Check if this option matches any correct answer
            matched_answer = None
            for answer in correct_answers:
                # Clean the answer text (remove "– Step N:" prefix for matching)
                clean_answer = re.sub(r'^[–-]\s*Step\s+\d+:\s*', '', answer).strip()
                # Also remove the "–" prefix if present
                clean_answer = re.sub(r'^[–-]\s*', '', clean_answer).strip()
                
                # Match logic depends on question type
                if clean_answer and option_text:
                    if in_select_and_order:
                        # For Select and order: use partial match (first 50 chars)
                        if clean_answer[:50].lower() in option_text.lower() or option_text[:50].lower() in clean_answer.lower():
                            matched_answer = answer
                            break
                    else:
                        # For regular questions: require very close match (90% similarity)
                        # Normalize whitespace for comparison
                        clean_ans_normalized = ' '.join(clean_answer.split())
                        opt_normalized = ' '.join(option_text.split())
                        
                        # Check if they're nearly identical (allowing for minor differences)
                        if clean_ans_normalized.lower() == opt_normalized.lower():
                            matched_answer = answer
                            break
                        # Or if one is a complete substring of the other with high overlap
                        elif len(clean_ans_normalized) > 50 and len(opt_normalized) > 50:
                            if clean_ans_normalized.lower() in opt_normalized.lower() or opt_normalized.lower() in clean_ans_normalized.lower():
                                # Check overlap percentage
                                shorter = min(len(clean_ans_normalized), len(opt_normalized))
                                longer = max(len(clean_ans_normalized), len(opt_normalized))
                                if shorter / longer > 0.8:  # 80% overlap
                                    matched_answer = answer
                                    break
            
            if matched_answer:
                # Check if we're in a select and order section and extract step number
                if in_select_and_order:
                    step_match = re.search(r'Step\s+(\d+)', matched_answer, re.IGNORECASE)
                    if step_match:
                        step_num = step_match.group(1)
                        # Remove existing "Step N:" prefix if present
                        clean_option = re.sub(r'^Step\s+\d+:\s*', '', option_text, flags=re.IGNORECASE)
                        marked_lines.append(("option_bold", f"- Step {step_num}: {clean_option}"))
                    else:
                        marked_lines.append(("option_bold", line))
                else:
                    marked_lines.append(("option_bold", line))
            else:
                marked_lines.append(("option", line))
        else:
            # Reset flag when we leave the select and order section
            if line.strip() and not line.strip().startswith("- "):
                in_select_and_order = False
            marked_lines.append(("normal", line))
    
    # Save to new document
    new_doc = Document()
    for line_type, line in marked_lines:
        para = new_doc.add_paragraph()
        # Check if line is a question header
        if re.match(r'^Question\s+\d+:$', line.strip()):
            run = para.add_run(line)
            run.bold = True
        # Check if line is "Explanations:"
        elif line.strip() == "Explanations:":
            run = para.add_run(line)
            run.bold = True
        # Check if line contains "Hence, the correct answer" pattern
        elif re.search(r'Hence, the correct answers? (?:are|is):', line, re.IGNORECASE):
            # Split and format only the pattern
            match = re.search(r'(Hence, the correct answers? (?:are|is):)', line, re.IGNORECASE)
            if match:
                before = line[:match.start()]
                pattern = match.group(1)
                after = line[match.end():]
                
                if before:
                    para.add_run(before)
                run = para.add_run(pattern)
                run.bold = True
                run.underline = True
                if after:
                    para.add_run(after)
            else:
                para.add_run(line)
        # Check if this is a bold option
        elif line_type == "option_bold":
            run = para.add_run(line)
            run.bold = True
        else:
            para.add_run(line)
    
    new_doc.save(output_path)


def clean_word_for_anki(input_path, output_path):
    # Charger le document
    doc = Document(input_path)
    
    # Get filename without extension
    filename = Path(input_path).stem
    
    # Extraire tout le texte du document
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    
    text = "\n".join(full_text)

    # 1. Nettoyage (Suppressions par vide)
    # On gère les termes spécifiques et les patterns "via -... retour ligne"
    patterns_to_remove = [
        r"\[ \]", 
        r"Ignoré.*?\n",
        r"Bonne réponse", 
        r"Sélection correcte", 
        r"Explication générale",
        r"via -.*?\n" # Equivalent de via -*^13 (caractères génériques)
    ]
    
    for p in patterns_to_remove:
        text = re.sub(p, "", text)

    # 2. Remplacements complexes (Regex)
    # Replace title section with filename
    text = re.sub(r"\[Unofficial\].*?Tentative \d+\s*\n", filename + "\n", text, flags=re.DOTALL)
    
    # Références:*^13Question -> Question
    text = re.sub(r"References:.*?\nQuestion", "Question", text, flags=re.IGNORECASE)
    text = re.sub(r"Reference:.*?\nQuestion", "Question", text, flags=re.IGNORECASE)
    
    # Remove Ressources/Domaine sections before Question
    text = re.sub(r"Ressources\s*\nDomaine\s*\n.*?\n(?=Question)", "", text, flags=re.IGNORECASE)

    # 3. Formatage final
    # Remplacer double saut de ligne par un simple (^p^p -> ^p)
    text = re.sub(r"\n\s*\n", "\n", text)
    
    # Remove any existing separator lines
    text = re.sub(r"={50,}\n?", "", text)

    # Sauvegarder dans un nouveau document ou fichier texte
    new_doc = Document()
    for i, line in enumerate(text.split('\n')):
        para = new_doc.add_paragraph()
        # First line (filename) - bold and centered
        if i == 0:
            run = para.add_run(line)
            run.bold = True
            para.alignment = 1  # 1 = center
        # Check if line starts with "Question" followed by space and number
        elif re.match(r'^Question\s+\d+', line):
            para.add_run(line).bold = True
        else:
            para.add_run(line)
    
    new_doc.save(output_path)
    print(f"Traitement terminé ! Fichier enregistré sous : {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python formatPdfFromUdemy.py <filename> <origin>")
        print("  origin: 'udemy' or 'dojo'")
        sys.exit(1)
    
    filename = sys.argv[1]
    origin = sys.argv[2].lower()
    
    if origin not in ['udemy', 'dojo']:
        print("Error: origin must be 'udemy' or 'dojo'")
        sys.exit(1)
    
    # Get GNL_PROCESSING_PATH from environment
    gnl_processing_path = os.getenv('GNL_PROCESSING_PATH')
    if not gnl_processing_path:
        raise ValueError("GNL_PROCESSING_PATH not found in .env file")
    
    base_path = Path(gnl_processing_path).parent
    
    # Build input path
    input_file = base_path / "pdf-formatting" / "word" / f"{filename}.docx"
    
    if not input_file.exists():
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    # Process document based on origin
    if origin == 'udemy':
        # Create temporary output file
        temp_file = input_file.with_suffix('.tmp.docx')
        clean_word_for_anki(str(input_file), str(temp_file))
        temp_file.replace(input_file)
        print("Document cleaned for Udemy format")
    else:
        # Clean Dojo document
        temp_file = input_file.with_suffix('.tmp.docx')
        clean_dojo_document(str(input_file), str(temp_file))
        temp_file.replace(input_file)
        print("Document cleaned for Dojo format (References removed)")
    
    # Convert to PDF
    pdf_folder = base_path / "pdf-formatting" / "pdf"
    pdf_folder.mkdir(parents=True, exist_ok=True)
    
    # Use LibreOffice to convert to PDF
    subprocess.run([
        "libreoffice", "--headless", "--convert-to", "pdf",
        "--outdir", str(pdf_folder), str(input_file)
    ], check=True)
    
    pdf_file = pdf_folder / input_file.with_suffix('.pdf').name
    print(f"PDF saved to: {pdf_file}")
    
    # For Dojo mode, copy PDF to exam folder
    if origin == 'dojo':
        exam_folder = Path(gnl_processing_path) / ".." / ".." / "exam"
        
        import shutil
        dest_file = exam_folder / pdf_file.name
        shutil.copy2(pdf_file, dest_file)
        print(f"PDF copied to: {dest_file}")