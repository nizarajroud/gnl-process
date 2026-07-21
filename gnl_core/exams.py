"""Exam processing pipeline — from raw PDF/DOCX to Anki flashcards."""

import os
import re
import subprocess
from pathlib import Path


def format_exam(input_path, origin='udemy'):
    """Step 1: Clean and format raw exam document.
    
    Args:
        input_path: Path to DOCX file
        origin: 'udemy' or 'dojo'
    Returns:
        Path to formatted PDF
    """
    from docx import Document

    doc = Document(input_path)
    full_text = [para.text for para in doc.paragraphs]
    text = "\n".join(full_text)

    if origin == 'dojo':
        # Remove References sections
        text = re.sub(r"References:.*?(?=Question|\Z)", "", text, flags=re.DOTALL | re.IGNORECASE)
    else:
        # Remove Udemy-specific patterns
        for p in [r"\[ \]", r"Ignoré.*?\n", r"Bonne réponse", r"Sélection correcte", r"Explication générale", r"via -.*?\n"]:
            text = re.sub(p, "", text)
        text = re.sub(r"\[Unofficial\].*?Tentative \d+\s*\n", "", text, flags=re.DOTALL)
        text = re.sub(r"Ressources\s*\nDomaine\s*\n.*?\n(?=Question)", "", text, flags=re.IGNORECASE)

    # Remove multiple blank lines
    text = re.sub(r"\n\s*\n", "\n", text)
    text = re.sub(r"={50,}\n?", "", text)

    # Renumber questions sequentially
    lines = text.split('\n')
    result_lines = []
    question_counter = 0

    for line in lines:
        stripped = line.strip()
        if re.match(r'^\d+\.\s*Question$', stripped) or re.match(r'^Question$', stripped):
            question_counter += 1
            result_lines.append(f"Question {question_counter}:")
        elif re.match(r'^Question\s+\d+:?', stripped):
            question_counter += 1
            rest = re.sub(r'^Question\s+\d+:?\s*', '', stripped)
            result_lines.append(f"Question {question_counter}:")
            if rest:
                result_lines.append(rest)
        else:
            result_lines.append(line)

    text = '\n'.join(result_lines)

    # Save as markdown
    output_dir = Path(os.environ.get('PDF_PARTS_FOLDER', '')) / 'exams'
    output_dir.mkdir(parents=True, exist_ok=True)
    name = Path(input_path).stem
    md_path = output_dir / f"{name}-formatted.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return str(md_path)


def highlight_answers(text, on_progress=None):
    """Step 2: Use Bedrock to identify correct answers.
    
    Args:
        text: Formatted exam text
        on_progress: Optional callback
    Returns:
        Dict {question_number: [correct_answers]}
    """
    import boto3
    from botocore.config import Config

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

    # Process in batches of 10
    for batch_start in range(0, len(question_blocks), 10):
        batch_end = min(batch_start + 10, len(question_blocks))
        batch = question_blocks[batch_start:batch_end]

        if on_progress:
            on_progress(f"Analyse questions {batch_start + 1}-{batch_end}...")

        batch_text = "\n\n".join([content for _, content in batch])

        prompt = f"""Extract the correct answer(s) for each question below.

{batch_text}

For each question, find the correct answer by looking for:
- "Hence, the correct answer is: ..."
- "Hence, the correct answers are:" followed by "–" lines
- Bold/highlighted options
- "Correct option:" pattern

Return as JSON: {{"1": ["answer1"], "2": ["answer1", "answer2"], ...}}
Only return the JSON, nothing else."""

        try:
            response = client.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": int(os.environ.get('BEDROCK_MAX_TOKENS', '4096'))}
            )
            result_text = response['output']['message']['content'][0]['text']
            # Parse JSON from response
            import json
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                batch_answers = json.loads(json_match.group())
                all_answers.update(batch_answers)
        except Exception as e:
            if on_progress:
                on_progress(f"⚠ Erreur batch {batch_start}: {str(e)[:50]}")

    return all_answers


def generate_compact(text, answers, name):
    """Step 3: Generate compact markdown with questions + correct answers only.
    
    Args:
        text: Formatted exam text
        answers: Dict from highlight_answers
        name: Exam name
    Returns:
        Path to compact markdown file
    """
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

            # Extract question text (before options)
            lines = q_content.split('\n')
            question_text = []
            options = []
            in_explanation = False

            for line in lines:
                if line.strip().startswith('- '):
                    options.append(line.strip())
                elif 'Explanation' in line or 'Hence,' in line:
                    in_explanation = True
                elif not in_explanation and not options:
                    question_text.append(line)

            compact_lines.append(f"\n**Question {num}:**")
            compact_lines.append(' '.join(question_text).strip())

            # Add options with correct ones marked
            correct = answers.get(num, [])
            for opt in options:
                opt_text = opt[2:]  # Remove "- "
                is_correct = any(
                    opt_text.lower().strip() in ans.lower() or ans.lower() in opt_text.lower()
                    for ans in correct
                )
                marker = "✓" if is_correct else "○"
                compact_lines.append(f"  {marker} {opt_text}")

    output_dir = Path(os.environ.get('PDF_PARTS_FOLDER', '')) / 'exams'
    output_dir.mkdir(parents=True, exist_ok=True)
    compact_path = output_dir / f"{name}-compact.md"
    with open(compact_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(compact_lines))

    return str(compact_path)


def generate_anki(compact_path, name):
    """Step 4: Generate Anki flashcard file from compact markdown.
    
    Args:
        compact_path: Path to compact markdown
        name: Exam name
    Returns:
        Path to Anki file
    """
    with open(compact_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse questions
    questions = re.split(r'\*\*Question\s+\d+:\*\*', content)
    anki_cards = []

    for q in questions[1:]:  # Skip header
        lines = q.strip().split('\n')
        if not lines:
            continue

        # Question text = first non-empty line
        question_text = lines[0].strip()

        # Options
        options = []
        correct = []
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('✓ '):
                correct.append(line[2:])
                options.append(line)
            elif line.startswith('○ '):
                options.append(line)

        if question_text and correct:
            # Front: question + all options
            front = f"{question_text}\n" + "\n".join(f"  {o}" for o in options)
            # Back: correct answers
            back = "\n".join(f"✓ {c}" for c in correct)
            anki_cards.append(f"{front}\t{back}")

    output_dir = Path(os.environ.get('PDF_PARTS_FOLDER', '')) / 'exams'
    output_dir.mkdir(parents=True, exist_ok=True)
    anki_path = output_dir / f"{name}-anki.txt"
    with open(anki_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(anki_cards))

    return str(anki_path)


def _get_config():
    """Load config."""
    from gnl_core.config import get_config
    return get_config()
