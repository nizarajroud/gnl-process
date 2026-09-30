"""
Pipeline: build artifacts (markdown + Anki) from the normalized pivot.

Format-agnostic. Any ExamFormat.parse() output feeds this to produce the same
artifacts DOJO produces, so the UI/podcast/Anki flows stay unchanged.
"""

import re
from pathlib import Path


def pivot_to_markdown(pivot, name):
    """Render the pivot as the full markdown used by step5_anki + podcast.

    Layout matches the DOJO full-markdown so downstream steps are identical:
        ## Question N:
        <statement>
        - option A
        - option B
        Explanations:
        <per-option or global explanation>
    """
    lines = [f"# {name}\n"]
    for q in sorted(pivot, key=lambda x: x['num']):
        lines.append(f"## Question {q['num']}:")
        if q.get('statement'):
            lines.append(q['statement'])
        lines.append('')
        for o in q['options']:
            lines.append(f"- {o['text']}")
        lines.append('')
        # Explanation: prefer per-option rationale, else global explanation.
        rationales = [o for o in q['options'] if o.get('rationale')]
        lines.append('Explanations:')
        if rationales:
            for o in q['options']:
                mark = 'CORRECT' if o['correct'] else 'incorrect'
                letter = (o['letter'] + '. ') if o.get('letter') else ''
                if o.get('rationale'):
                    lines.append(f"[{mark}] {letter}{o['rationale']}")
        elif q.get('explanation'):
            lines.append(q['explanation'])
        lines.append('')
    return '\n'.join(lines).strip()


def pivot_to_answers(pivot):
    """Convert the pivot into the step5_anki `answers` dict:
        {num: {'type','options','correct'}}"""
    answers = {}
    for q in pivot:
        opts = [o['text'] for o in q['options']]
        correct = [o['text'] for o in q['options'] if o['correct']]
        qtype = 'multi' if len(correct) > 1 else 'single'
        answers[str(q['num'])] = {
            'type': qtype, 'options': opts, 'correct': correct,
        }
    return answers


def resolve_format_output(fmt, origin_path, name, theme, subtheme, on_progress=None):
    """Parse a document with the detected format and return everything the
    exam pipeline needs, format-agnostically:

        (pivot, md_path, answers)

    - DOJO: reuses its unchanged step1/step2b/step3 pipeline -> byte-identical
      md_path + answers (zero regression). We DON'T rebuild them from the pivot.
    - Other formats (AWS Practice Exam, ...): answers come straight from the
      document (no Bedrock); the markdown is rendered from the pivot.
    """
    from pathlib import Path
    from gnl_core.exams import get_exam_base

    if fmt.name == 'dojo':
        pivot = fmt.parse(origin_path, on_progress=on_progress,
                          theme=theme, subtheme=subtheme)
        md_path = getattr(fmt, '_last_md_path', None)
        answers = getattr(fmt, '_last_answers', None)
        return pivot, md_path, answers

    # Generic path: parse -> pivot -> derive md + answers (no Bedrock).
    pivot = fmt.parse(origin_path, on_progress=on_progress)
    base = get_exam_base(theme, subtheme)
    md_dir = base / 'pdf-formatting' / 'full-markdown'
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = str(md_dir / f"{name}.md")
    Path(md_path).write_text(pivot_to_markdown(pivot, name), encoding='utf-8')
    answers = pivot_to_answers(pivot)
    if on_progress:
        on_progress(f"markdown → {md_path}")
    return pivot, md_path, answers


def build_artifacts(pivot, name, theme, subtheme, on_progress=None,
                    md_path=None, answers=None):
    """Write the full markdown (if not provided) and generate the Anki apkg.

    Returns {'md_path': ..., 'anki_path': ...}.
    For DOJO, `md_path` and `answers` are already produced by its (unchanged)
    pipeline and passed in, so the generated apkg is byte-identical (zero
    regression). For new formats, both are derived from the pivot.
    """
    from gnl_core.exams import get_exam_base, step5_anki

    base = get_exam_base(theme, subtheme)
    if md_path is None:
        md_dir = base / 'pdf-formatting' / 'full-markdown'
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = str(md_dir / f"{name}.md")
        Path(md_path).write_text(pivot_to_markdown(pivot, name), encoding='utf-8')
        if on_progress:
            on_progress(f"markdown → {md_path}")

    if answers is None:
        answers = pivot_to_answers(pivot)
    anki_path = step5_anki(answers, md_path, theme, subtheme, on_progress=on_progress)
    return {'md_path': md_path, 'anki_path': anki_path}
