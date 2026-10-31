"""
Dojo 'Category' format (newer TutorialsDojo export).

Unlike the classic DOJO format, this export has NO 'N. Question' header. Each
question starts with a 'Category: <code> – <domain>' line (the numbering '2.'
is a Word auto-number, invisible to python-docx). Structure per question:

    Category: AIBC01 – <domain>          <- question delimiter (dropped)
    <statement paragraph(s)>             <- ends with the "Which ... ?" line
    <option A>
    <option B>
    <option C>
    <option D>
    Incorrect | Correct                  <- user's own status (ignored)
    <explanation paragraphs...>
    Hence, the correct answer is: <text> <- identifies the correct option
    The option that says: ... is incorrect   (x N)
    References:
    <links...>

The parser drops the Category line, keeps a sequential question number, extracts
the 4 options, finds the correct one via 'Hence, the correct answer is:', and
keeps the whole explanation. The pipeline then renders '## Question N:' headers.
"""

import re
from .base import ExamFormat, normalize_question

_CATEGORY_RE = re.compile(r'^\s*Category\s*:', re.I)
_STATUS_RE = re.compile(r'^(Correct|Incorrect)$', re.I)
# Matches "Hence, the correct answer is:" AND "...answers are:" (singular/plural).
_HENCE_RE = re.compile(r'Hence,?\s+the\s+correct\s+answers?\s+(?:is|are)\s*:?\s*(.*)', re.I)


class DojoCategoryFormat(ExamFormat):
    name = 'dojo_category'
    label = 'Dojo (Category)'

    def detect(self, path: str) -> bool:
        if not str(path).lower().endswith('.docx'):
            return False
        try:
            from docx import Document
            doc = Document(path)
            # If it has practice-exam option tables, it's NOT this format.
            for tbl in doc.tables:
                if tbl.rows:
                    header = [c.text.strip().lower() for c in tbl.rows[0].cells]
                    if 'option' in header and 'correct answer' in header:
                        return False
            paras = [p.text for p in doc.paragraphs]
            text = "\n".join(paras)
            n_cat = sum(1 for p in paras if _CATEGORY_RE.match(p.strip()))
            # Must have several 'Category:' delimiters AND NO classic
            # 'N. Question' headers (that case is handled by DojoFormat).
            has_qheader = bool(re.search(r'\d+\.\s*Question', text)) \
                or bool(re.search(r'Question\s+\d+', text))
            dojo_hint = ('Hence, the correct answer is' in text
                         or 'References:' in text or 'dojo' in str(path).lower())
            return n_cat >= 2 and not has_qheader and dojo_hint
        except Exception:
            return False

    def parse(self, path: str, on_progress=None) -> list:
        from docx import Document
        doc = Document(path)
        paras = [p.text.strip() for p in doc.paragraphs]
        # indices of each 'Category:' line = question boundaries
        bounds = [i for i, t in enumerate(paras) if _CATEGORY_RE.match(t)]
        questions = []
        for qi, start in enumerate(bounds):
            end = bounds[qi + 1] if qi + 1 < len(bounds) else len(paras)
            block = [t for t in paras[start + 1:end] if t]  # drop Category line + blanks
            if not block:
                continue
            q = self._parse_block(block, qi + 1)
            if q:
                questions.append(q)
        if on_progress:
            on_progress(f"Dojo (Category): {len(questions)} questions")
        return questions

    def _parse_block(self, block, num):
        # 1) status line ('Correct'/'Incorrect') separates Q+options from explanation
        status_idx = None
        for i, t in enumerate(block):
            if _STATUS_RE.match(t):
                status_idx = i
                break
        if status_idx is None:
            # no status marker → cannot reliably split; skip
            return None
        head = block[:status_idx]          # statement + options
        status = block[status_idx]
        expl_lines = block[status_idx + 1:]  # explanation + references

        # 2) statement vs options: the statement ends at the "...?" question line.
        q_end = None
        for i, t in enumerate(head):
            if t.rstrip().endswith('?'):
                q_end = i
                break
        if q_end is None:
            # fallback: assume last 4 lines are options
            q_end = max(0, len(head) - 5)
        statement = "\n".join(head[:q_end + 1]).strip()
        option_texts = [t for t in head[q_end + 1:] if t]

        # 3) correct answer(s): take the region starting at
        # 'Hence, the correct answer(s) is/are:' until the first
        # 'The option that says' / 'References:' line. Each option whose text
        # appears there is marked correct (supports single AND multi answers).
        explanation = "\n".join(expl_lines).strip()
        correct_region = ''
        for i, t in enumerate(expl_lines):
            m = _HENCE_RE.search(t)
            if m:
                parts = [m.group(1).strip()]
                for t2 in expl_lines[i + 1:]:
                    low = t2.lower()
                    if low.startswith('the option that says') or low.startswith('references'):
                        break
                    parts.append(t2.strip())
                correct_region = " ".join(parts)
                break

        def _norm(s):
            s = (s or '')
            # unify curly quotes/apostrophes/dashes so matching is robust
            s = (s.replace('\u2019', "'").replace('\u2018', "'")
                   .replace('\u201c', '"').replace('\u201d', '"')
                   .replace('\u2013', '-').replace('\u2014', '-'))
            return re.sub(r'\s+', ' ', s).strip().lower().rstrip('.')

        region_norm = _norm(correct_region)
        options = []
        letters = 'ABCDEFGH'
        for idx, otext in enumerate(option_texts):
            onorm = _norm(otext)
            is_correct = False
            if region_norm and onorm:
                # option text is contained in the correct region (robust to
                # minor rephrasing of short options via a length guard)
                is_correct = (onorm in region_norm) or (len(onorm) > 25 and onorm[:60] in region_norm)
            options.append({
                'letter': letters[idx] if idx < len(letters) else '',
                'text': otext,
                'correct': is_correct,
                'selected': False,
                'rationale': '',
            })
        return normalize_question(num, statement, options,
                                  status=status, explanation=explanation)
