from docx import Document
import re
import sys
import subprocess
from pathlib import Path

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
    if len(sys.argv) < 2:
        print("Usage: python formatPdfFromUdemy.py <input_file.docx>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # Clean the document
    clean_word_for_anki(input_file, input_file)
    
    # Convert to PDF
    input_path = Path(input_file)
    pdf_folder = input_path.parent.parent / "pdf"
    
    # Use LibreOffice to convert to PDF
    subprocess.run([
        "libreoffice", "--headless", "--convert-to", "pdf",
        "--outdir", str(pdf_folder), str(input_path)
    ], check=True)
    
    print(f"PDF saved to: {pdf_folder / input_path.with_suffix('.pdf').name}")