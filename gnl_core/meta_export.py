"""
Meta AI export — generic, format-agnostic.

Turns an exam's normalized pivot (same structure produced by every ExamFormat)
into a set of 'part' text files ready to paste into Meta AI, one message per
part, under Meta AI's input size limit. Part 1 is prefixed with a configurable
expert prompt.

Nothing here is specific to a single question or format. The prompt and the
size limit are read from config (externalized), with sensible defaults.
"""

import os
import re
from pathlib import Path


DEFAULT_MAX_CHARS = 65000

# Default expert prompt. {N} is replaced with the number of parts.
DEFAULT_PROMPT = (
    "You are a senior AWS Solutions Architect (SAP-C02 level) and my study "
    "partner for a natural, expert-to-expert exam-prep conversation.\n\n"
    "I will paste a set of AWS practice questions in {N} messages (Part 1 of "
    "{N}, Part 2 of {N}, ...), each question with its options (A-D) and a "
    "detailed explanation (some explanations contain AWS doc links).\n\n"
    "How to behave once all parts are pasted:\n"
    "- Answer DIRECTLY and conversationally, like an expert talking to a peer. "
    "Straight to the substance.\n"
    "- NEVER say \"according to the file\", \"from Question N\", \"the file "
    "says\", \"based on the explanation\", never mention question numbers as "
    "bookkeeping, never announce that you consulted a link.\n"
    "- When I ask \"why X and not Y\", reply \"Because ...\" and explain the "
    "real reason, the trade-off, and the key difference, in flowing prose - "
    "not a labeled template. Weave requirements and constraints naturally into "
    "the explanation; do NOT output headed sections.\n"
    "- If you need more depth, you MAY silently use the AWS doc links in that "
    "question's explanation to stay accurate. Never announce it, never paste a "
    "link unless I explicitly ask.\n"
    "- Be solid and precise. If you state a specific limit/duration/behavior, "
    "be correct - if unsure, say so plainly instead of inventing.\n"
    "- No filler, no meta-commentary about files or rules.\n\n"
    "IMPORTANT: I am sending the questions across {N} parts. Do NOT start "
    "answering yet. After each part, just reply \"Part K received.\" When I say "
    "\"ALL PARTS SENT\", reply \"Ready.\" and wait for my questions."
)


def _render_question(q):
    """Render one pivot question as plain markdown text (statement, options,
    per-option explanation)."""
    lines = [f"## Question {q['num']}:"]
    if q.get('statement'):
        lines.append(q['statement'])
    lines.append("")
    for o in q.get('options', []):
        letter = (o['letter'] + '. ') if o.get('letter') else ''
        lines.append(f"- {letter}{o['text']}")
    rats = [o for o in q.get('options', []) if o.get('rationale')]
    if rats:
        lines.append("")
        lines.append("Explanations:")
        for o in q.get('options', []):
            if o.get('rationale'):
                mark = '[CORRECT] ' if o['correct'] else '[incorrect] '
                letter = (o['letter'] + '. ') if o.get('letter') else ''
                lines.append(f"{mark}{letter}{o['rationale']}")
    elif q.get('explanation'):
        lines.append("")
        lines.append("Explanations:")
        lines.append(q['explanation'])
    lines.append("")
    return "\n".join(lines)


def build_parts(pivot, max_chars=None, prompt_template=None):
    """Split the pivot into parts (list of strings), each < max_chars, split at
    question boundaries. Part 1 is prefixed with the prompt (with {N} filled).

    Returns the list of part strings.
    """
    max_chars = int(max_chars or DEFAULT_MAX_CHARS)
    prompt_template = prompt_template or DEFAULT_PROMPT

    rendered = [(_q['num'], _render_question(_q))
                for _q in sorted(pivot, key=lambda x: x['num'])]

    # First pass: pack bodies greedily. We don't know N (part count) up front,
    # and the prompt length depends on N only via the {N} digits (negligible),
    # so we reserve the prompt length using a placeholder estimate.
    prompt_reserve = len(prompt_template.replace('{N}', '99')) + len(
        "\n\n===QUESTIONS PART 1 OF 99===\n")
    part_header = "===QUESTIONS PART {k} OF {n}===\n"

    def pack(reserve_first):
        groups = [[]]
        sizes = [reserve_first]
        for num, body in rendered:
            budget = sizes[-1] + len(body) + len(part_header)
            if budget > max_chars and groups[-1]:
                groups.append([])
                sizes.append(0)
            groups[-1].append((num, body))
            sizes[-1] += len(body)
        return groups

    groups = pack(prompt_reserve)
    n = len(groups)

    parts = []
    for k, g in enumerate(groups, start=1):
        body = "".join(b for _, b in g)
        if k == 1:
            head = prompt_template.replace('{N}', str(n)) \
                + f"\n\n===QUESTIONS PART 1 OF {n}===\n"
        else:
            head = f"===QUESTIONS PART {k} OF {n}===\n"
        parts.append(head + body)
    return parts


def build_meta_corpus(pivot, prompt_template=None):
    """Plan B (exam): the WHOLE exam as a single string = prompt header + every
    rendered question concatenated (same _render_question as build_parts, so the
    content is identical to the parts, just not split). Used to write one .md.
    """
    prompt_template = prompt_template or DEFAULT_PROMPT
    rendered = [_render_question(_q)
                for _q in sorted(pivot, key=lambda x: x['num'])]
    header = prompt_template.replace('{N}', '1')
    return header + "\n\n===QUESTIONS===\n" + "".join(rendered)


# --- Generic (non-exam) text splitting -------------------------------------
# Independent of the exam pivot. Used by the generic Doc→Meta tool. The exam
# path (build_parts above) is NOT touched.

DEFAULT_GENERIC_PROMPT = (
    "You are an expert on the subject of the material I'm about to paste. I will "
    "paste it across {N} messages (Part 1 of {N}, Part 2 of {N}, ...).\n\n"
    "During the loading phase (while I paste the parts):\n"
    "- Do NOT start answering or summarizing. After each part, reply ONLY with "
    "\"Part K received.\" When I say \"ALL PARTS SENT\", reply ONLY \"Ready.\"\n\n"
    "Once we start talking, behave like a knowledgeable expert having a natural "
    "conversation with a peer:\n"
    "- Answer DIRECTLY and conversationally. Just explain the thing, as if you "
    "simply know it.\n"
    "- NEVER refer to \"the pasted content\", \"the context you gave me\", \"the "
    "document\", \"the material\", \"the table of contents\", \"according to what "
    "you pasted\", or part/section numbers. Never talk about the format or "
    "structure of what I sent. Just talk about the subject itself.\n"
    "- NEVER tell me to \"read the table of contents\" or point me back to the "
    "text. Give me the answer.\n"
    "- Ground your answers in what I shared, but present them as your own "
    "knowledge, in flowing natural prose — no headers, no bullet-point templates "
    "unless I ask.\n"
    "- Be precise and honest: if something genuinely isn't covered by what I "
    "shared and you're not sure, say so plainly in one short sentence, then give "
    "your best expert view if helpful.\n"
    "- If you need more depth than what I shared, you may silently consult a link "
    "that appears in the material to stay accurate — but ONLY links actually "
    "present in what I shared, nothing else. Never announce that you followed a "
    "link, and never paste it unless I explicitly ask.\n"
    "- No filler, no meta-commentary.\n\n"
    "For now, just wait for the parts. Reply only \"Part K received.\" after each, "
    "and \"Ready.\" after \"ALL PARTS SENT\"."
)


# Continuation variant: used when the new parts ADD to an ongoing conversation
# (same Meta AI chat). Tells the model to keep all prior context and treat this
# as a follow-up corpus, not a reset.
DEFAULT_CONTINUATION_PROMPT = (
    "The following is a CONTINUATION of our ongoing conversation. I'm pasting "
    "additional material across {N} messages (Part 1 of {N}, ...).\n\n"
    "IMPORTANT:\n"
    "- Do NOT reset or forget anything from earlier in this conversation. KEEP "
    "all the previous context and ADD this new material to it, as one combined "
    "body of knowledge.\n"
    "- During loading, reply ONLY \"Part K received.\" after each part, and "
    "\"Ready.\" after \"ALL PARTS SENT\".\n"
    "- Afterwards, answer naturally as an expert, using BOTH the earlier content "
    "and this new material together. Never say \"according to the pasted "
    "content\" or refer to parts/structure — just talk about the subject.\n"
    "- If links appear in the material, you may silently consult them to be "
    "accurate; never announce it.\n\n"
    "For now, just wait for the parts."
)


def build_parts_from_text(text, max_chars=None, prompt_template=None):
    """Split arbitrary text into parts (list of strings), each < max_chars,
    cutting at paragraph boundaries (never mid-paragraph when avoidable).
    Part 1 is prefixed with the generic prompt (with {N} filled).
    """
    max_chars = int(max_chars or DEFAULT_MAX_CHARS)
    prompt_template = prompt_template or DEFAULT_GENERIC_PROMPT

    # Split into paragraphs; keep very long paragraphs splittable by lines.
    paragraphs = re.split(r'\n\s*\n', text.strip())
    units = []
    for para in paragraphs:
        if len(para) <= max_chars:
            units.append(para)
        else:
            # hard-split an oversized paragraph by lines, then by slices
            buf = ''
            for line in para.split('\n'):
                if len(buf) + len(line) + 1 > max_chars and buf:
                    units.append(buf)
                    buf = ''
                while len(line) > max_chars:
                    units.append(line[:max_chars])
                    line = line[max_chars:]
                buf = (buf + '\n' + line) if buf else line
            if buf:
                units.append(buf)

    prompt_reserve = len(prompt_template.replace('{N}', '99')) + len(
        "\n\n===PART 1 OF 99===\n")
    part_header = "===PART {k} OF {n}===\n"

    groups = [[]]
    sizes = [prompt_reserve]
    for u in units:
        if sizes[-1] + len(u) + 2 + len(part_header) > max_chars and groups[-1]:
            groups.append([])
            sizes.append(0)
        groups[-1].append(u)
        sizes[-1] += len(u) + 2

    n = len(groups)
    parts = []
    for k, g in enumerate(groups, start=1):
        body = "\n\n".join(g)
        if k == 1:
            head = prompt_template.replace('{N}', str(n)) + f"\n\n===PART 1 OF {n}===\n"
        else:
            head = f"===PART {k} OF {n}===\n"
        parts.append(head + body)
    return parts


def generate_doc_export(text, name, out_dir, on_progress=None,
                        max_chars=None, prompt_template=None):
    """Write generic Doc→Meta part files into out_dir and return a list of
    {'part','total','path','chars'}. out_dir is created/cleaned."""
    from pathlib import Path as _P
    out = _P(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob('part*_of_*.txt'):
        try:
            old.unlink()
        except Exception:
            pass
    parts = build_parts_from_text(text, max_chars=max_chars,
                                  prompt_template=prompt_template)
    n = len(parts)
    results = []
    for k, content in enumerate(parts, start=1):
        p = out / f"part{k}_of_{n}.txt"
        p.write_text(content, encoding='utf-8')
        results.append({'part': k, 'total': n, 'path': str(p), 'chars': len(content)})
        if on_progress:
            on_progress(f"Doc export part {k}/{n} → {p.name} ({len(content)} chars)")
    return results


def generate_meta_export(pivot, name, theme, subtheme, on_progress=None,
                         max_chars=None, prompt_template=None):
    """Write the Meta AI part files into assets/Meta-export/<name>/ and return
    a list of {'part': k, 'total': n, 'path': ..., 'chars': ...}.
    """
    from gnl_core.exams import get_exam_base
    base = get_exam_base(theme, subtheme)
    out_dir = base / 'Meta-export' / name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clean previous parts for this exam (avoid stale leftovers).
    for old in out_dir.glob('part*_of_*.txt'):
        try:
            old.unlink()
        except Exception:
            pass

    parts = build_parts(pivot, max_chars=max_chars,
                        prompt_template=prompt_template)
    n = len(parts)
    results = []
    for k, content in enumerate(parts, start=1):
        p = out_dir / f"part{k}_of_{n}.txt"
        p.write_text(content, encoding='utf-8')
        results.append({'part': k, 'total': n, 'path': str(p),
                        'chars': len(content)})
        if on_progress:
            on_progress(f"Meta export part {k}/{n} → {p.name} ({len(content)} chars)")
    return results


def generate_meta_markdown(pivot, name, prompt_template=None, icloud_dir=None,
                           on_progress=None):
    """Plan B (exam): write the whole exam corpus as a single Markdown file into
    the iCloud META-AI folder. Returns {'name','path','chars'}.
    """
    import os as _os
    from pathlib import Path as _P
    content = build_meta_corpus(pivot, prompt_template=prompt_template)
    icloud_dir = icloud_dir or _os.environ.get(
        'ICLOUD_META_DIR',
        '/mnt/c/Users/nizar/Synchro-iphone/iCloudDrive/META-AI')
    out = _P(icloud_dir)
    out.mkdir(parents=True, exist_ok=True)
    safe = (''.join(c if c.isalnum() or c in ' -_' else '_' for c in name).strip()
            or 'exam')
    path = out / f"{safe}.md"
    path.write_text(content, encoding='utf-8')
    if on_progress:
        on_progress(f"markdown iCloud → {path} ({len(content)} chars)")
    return {'name': name, 'path': str(path), 'chars': len(content)}
