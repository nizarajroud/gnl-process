"""Exam processing pipeline — from raw DOCX to Anki flashcards.

Structure:
    {EXAM_BASE}/pdf-formatting/origin/    ← DOCX brut (input)
    {EXAM_BASE}/pdf-formatting/word/      ← DOCX nettoyé (format)
    {EXAM_BASE}/pdf-formatting/pdf/       ← PDF converti (libreoffice)
    {EXAM_BASE}/pdf-formatting/compact-exam-versions/ ← PDF compact
    {EXAM_BASE}/Anki-generation/markdown/ ← Markdown compact
    {EXAM_BASE}/Anki-generation/anki/     ← Fichier Anki importable
"""

import os
import re
import shutil
import subprocess
from pathlib import Path


def get_exam_base(theme, subtheme):
    """Get base path for exam assets: INBOX_FOLDER/{theme}/{subtheme}/assets/"""
    inbox = os.environ.get('INBOX_FOLDER', '')
    return Path(inbox) / theme / subtheme / 'assets'


def step1_format(input_path, theme, subtheme, origin='udemy', on_progress=None):
    """Step 1: origin/ → word/ (clean DOCX)
    
    Args:
        input_path: Path to original DOCX in origin/
        origin: 'udemy' or 'dojo'
    Returns:
        Path to cleaned DOCX in word/
    """
    from docx import Document

    base = get_exam_base(theme, subtheme)
    word_dir = base / 'pdf-formatting' / 'word'
    word_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(input_path).name
    output_path = word_dir / filename

    # Copy original to word folder
    shutil.copy2(input_path, output_path)

    # Process based on origin
    doc = Document(str(output_path))
    full_text = [para.text for para in doc.paragraphs]
    text = "\n".join(full_text)

    if origin == 'dojo':
        text = re.sub(r"References:.*?(?=Question|\Z)", "", text, flags=re.DOTALL | re.IGNORECASE)
    else:
        for p in [r"\[ \]", r"Ignoré.*?\n", r"Bonne réponse", r"Sélection correcte", r"Explication générale", r"via -.*?\n"]:
            text = re.sub(p, "", text)
        text = re.sub(r"\[Unofficial\].*?Tentative \d+\s*\n", "", text, flags=re.DOTALL)
        text = re.sub(r"Ressources\s*\nDomaine\s*\n.*?\n(?=Question)", "", text, flags=re.IGNORECASE)

    text = re.sub(r"\n\s*\n", "\n", text)
    text = re.sub(r"={50,}\n?", "", text)

    # Renumber questions and format options
    lines = text.split('\n')
    result_lines = []
    question_counter = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if re.match(r'^\d+\.\s*Question$', stripped) or re.match(r'^Question$', stripped):
            question_counter += 1
            result_lines.append(f"Question {question_counter}:")
            i += 1
        elif re.match(r'^Question\s+\d+:?', stripped):
            question_counter += 1
            rest = re.sub(r'^Question\s+\d+:?\s*', '', stripped)
            result_lines.append(f"Question {question_counter}:")
            if rest:
                result_lines.append(rest)
            i += 1
        elif stripped == 'Incorrect' or re.match(r'^Correct\s+options?:', stripped, re.IGNORECASE):
            # Find the last question mark to identify where options start
            last_q_idx = -1
            for j in range(len(result_lines) - 1, -1, -1):
                if '?' in result_lines[j]:
                    last_q_idx = j
                    break

            if last_q_idx != -1:
                # Lines between question mark and here are options
                options = []
                for j in range(last_q_idx + 1, len(result_lines)):
                    if result_lines[j].strip():
                        options.append(result_lines[j].strip())

                # Remove option lines from result
                result_lines = result_lines[:last_q_idx + 1]

                # Add as bullet list
                for opt in options:
                    if not opt.startswith('- '):
                        result_lines.append(f"- {opt}")
                    else:
                        result_lines.append(opt)

            # Add Explanations marker
            result_lines.append("Explanations:")
            i += 1
        else:
            result_lines.append(line)
            i += 1

    # Save cleaned DOCX
    new_doc = Document()
    for line in result_lines:
        para = new_doc.add_paragraph()
        if re.match(r'^Question\s+\d+:', line.strip()):
            para.add_run(line).bold = True
        elif line.strip() == "Explanations:":
            para.add_run(line).bold = True
        else:
            para.add_run(line)
    new_doc.save(str(output_path))

    if on_progress:
        on_progress(f"origin/ → word/{filename}")

    return str(output_path)


def step2_convert_pdf(word_path, theme, subtheme, on_progress=None):
    """Step 2: word/ → pdf/ (LibreOffice conversion)
    
    Returns:
        Path to PDF
    """
    base = get_exam_base(theme, subtheme)
    pdf_dir = base / 'pdf-formatting' / 'pdf'
    pdf_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run([
        "libreoffice", "--headless", "--convert-to", "pdf",
        "--outdir", str(pdf_dir), word_path
    ], capture_output=True)

    pdf_path = pdf_dir / Path(word_path).with_suffix('.pdf').name

    if on_progress:
        on_progress(f"word/ → pdf/{pdf_path.name}")

    return str(pdf_path)


def step3_highlight(word_path, on_progress=None):
    """Step 3: Identify correct answers using Bedrock/Claude.
    
    Returns:
        Dict {question_number: [correct_answers]}
    """
    import boto3
    from botocore.config import Config
    from docx import Document

    # Read text from cleaned DOCX
    doc = Document(word_path)
    text = "\n".join([para.text for para in doc.paragraphs])

    config_data = _get_config()
    model_id = config_data.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-20250514-v1:0')
    region = config_data.get('AWS_REGION', 'ca-central-1')
    profile = config_data.get('AWS_PROFILE', '')

    session = boto3.Session(profile_name=profile, region_name=region)
    client = session.client('bedrock-runtime', config=Config(read_timeout=600))

    # Split into questions
    questions = re.split(r'(Question\s+\d+:)', text)
    question_blocks = []
    for i in range(1, len(questions), 2):
        if i + 1 < len(questions):
            q_num = re.search(r'\d+', questions[i])
            if q_num:
                question_blocks.append((q_num.group(), questions[i] + questions[i + 1]))

    all_answers = {}
    max_tokens = int(os.environ.get('BEDROCK_MAX_TOKENS', '4096'))

    for batch_start in range(0, len(question_blocks), 10):
        batch_end = min(batch_start + 10, len(question_blocks))
        batch = question_blocks[batch_start:batch_end]

        if on_progress:
            on_progress(f"Questions {batch_start + 1}-{batch_end}...")

        batch_text = "\n\n".join([content for _, content in batch])

        # Load prompt from external file
        prompt_file = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'prompts' / 'exam-highlight.txt'
        if prompt_file.exists():
            prompt_template = prompt_file.read_text(encoding='utf-8')
        else:
            prompt_template = "Extract the correct answer(s) for each question below.\n\n{questions}\n\nReturn as JSON: {\"1\": [\"answer1\"], \"2\": [\"answer1\", \"answer2\"], ...}\nOnly return the JSON, nothing else."
        prompt = prompt_template.replace('{questions}', batch_text)

        try:
            response = client.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": max_tokens}
            )
            result_text = response['output']['message']['content'][0]['text']
            import json
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                batch_answers = json.loads(json_match.group())
                all_answers.update(batch_answers)
        except Exception as e:
            if on_progress:
                on_progress(f"⚠ Erreur batch {batch_start}: {str(e)[:50]}")

    return all_answers


def step4_compact(word_path, answers, theme, subtheme, on_progress=None):
    """Step 4: Generate compact version (Markdown + PDF).
    
    Returns:
        Path to compact markdown
    """
    from docx import Document
    import markdown
    from weasyprint import HTML

    base = get_exam_base(theme, subtheme)
    name = Path(word_path).stem

    # Read formatted text
    doc = Document(word_path)
    text = "\n".join([para.text for para in doc.paragraphs])

    # Parse and generate compact
    questions = re.split(r'(Question\s+\d+:)', text)
    compact_lines = [f"# {name} — Compact Version\n"]

    for i in range(1, len(questions), 2):
        if i + 1 < len(questions):
            q_header = questions[i].strip()
            q_content = questions[i + 1].strip()
            q_num = re.search(r'\d+', q_header)
            if not q_num:
                continue
            num = q_num.group()

            # Get question text and options
            lines = q_content.split('\n')
            question_text = []
            options = []

            for line in lines:
                if line.strip().startswith('- '):
                    options.append(line.strip()[2:])
                elif 'Explanation' in line or 'Hence,' in line:
                    break
                elif not options:
                    if line.strip():
                        question_text.append(line.strip())

            compact_lines.append(f"\n**Question {num}:**")
            compact_lines.append("")
            compact_lines.append(' '.join(question_text[:3]))  # First 3 lines as question
            compact_lines.append("")

            correct = answers.get(num, [])
            for opt in options:
                is_correct = any(
                    opt.lower().strip()[:50] in ans.lower() or ans.lower()[:50] in opt.lower()
                    for ans in correct
                ) if correct else False
                if is_correct:
                    compact_lines.append(f"- **{opt}**")
                else:
                    compact_lines.append(f"- {opt}")

    # Save markdown
    md_dir = base / 'Anki-generation' / 'markdown'
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{name}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(compact_lines))

    # Generate compact PDF
    compact_pdf_dir = base / 'pdf-formatting' / 'compact-exam-versions'
    compact_pdf_dir.mkdir(parents=True, exist_ok=True)
    html_content = markdown.markdown('\n'.join(compact_lines))
    html_full = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>body{{font-family:Arial;font-size:11px;margin:30px;}}
    h1{{color:#232f3e;border-bottom:2px solid #ff9900;}}
    strong{{color:#0073bb;}}</style></head><body>{html_content}</body></html>"""
    HTML(string=html_full).write_pdf(str(compact_pdf_dir / f"{name}.pdf"))

    if on_progress:
        on_progress(f"compact → {md_path.name}")

    return str(md_path)


def step5_anki(compact_md_path, theme, subtheme, on_progress=None):
    """Step 5: Generate Anki .apkg package from compact markdown.
    
    Returns:
        Path to .apkg file
    """
    import genanki
    import random

    base = get_exam_base(theme, subtheme)
    name = Path(compact_md_path).stem

    with open(compact_md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Model for exam cards
    font_size = os.environ.get('ANKI_FONT_SIZE', '14')
    model_id = random.randrange(1 << 30, 1 << 31)
    model = genanki.Model(
        model_id,
        f'{name} Model',
        fields=[
            {'name': 'Front'},
            {'name': 'Back'},
        ],
        templates=[{
            'name': 'Card 1',
            'qfmt': '{{Front}}',
            'afmt': '{{Back}}',
        }],
        css=f"""
            .card {{ text-align: left; font-family: Arial; font-size: {font_size}px; padding: 10px; }}
            ul {{ padding-left: 20px; }}
            li {{ margin-bottom: 5px; }}
            .correct {{ color: #28a745; font-weight: bold; }}
            b {{ color: #0073bb; }}
        """
    )

    # Deck with exam name
    deck_id = random.randrange(1 << 30, 1 << 31)
    deck = genanki.Deck(deck_id, name)

    # Parse questions
    questions = re.split(r'(\*\*Question\s+\d+:\*\*)', content)

    cards_count = 0
    for i in range(1, len(questions), 2):
        q_header = questions[i].replace('**', '')
        q_body = questions[i + 1].strip() if i + 1 < len(questions) else ''
        lines = q_body.split('\n')

        question_text = ''
        for l in lines:
            if l.strip():
                question_text = l.strip()
                break

        options = []
        for line in lines:
            line = line.strip()
            if line.startswith('- **') and line.endswith('**'):
                opt_text = line[4:-2]
                options.append(('correct', opt_text))
            elif line.startswith('- '):
                opt_text = line[2:]
                options.append(('wrong', opt_text))

        if question_text and options:
            options_html = "".join(f"<li>{opt_text}</li>" for _, opt_text in options)
            front = f"<b>{q_header}</b><br><br>{question_text}<br><br><ul>{options_html}</ul>"

            back_items = []
            for status, opt_text in options:
                if status == 'correct':
                    back_items.append(f"<li><span class='correct'>{opt_text}</span></li>")
                else:
                    back_items.append(f"<li>{opt_text}</li>")
            back = f"<b>{q_header}</b><br><br>{question_text}<br><br><ul>{''.join(back_items)}</ul>"

            note = genanki.Note(model=model, fields=[front, back])
            deck.add_note(note)
            cards_count += 1

    # Save .apkg
    anki_dir = base / 'Anki-generation' / 'anki'
    anki_dir.mkdir(parents=True, exist_ok=True)
    apkg_path = anki_dir / f"{name}.apkg"
    genanki.Package(deck).write_to_file(str(apkg_path))

    if on_progress:
        on_progress(f"anki → {apkg_path.name} ({cards_count} cards)")

    return str(apkg_path)


def _get_config():
    from gnl_core.config import get_config
    return get_config()
