"""
Practice-set PDF where all QUESTIONS come first and the ANSWER KEY (correct
letter + rationale) is listed at the back. Example layout:

    Question 1.1 · Multiple choice · select ONE
    <scenario statement, possibly multi-paragraph with ● bullets>
    Which ... ?
    A. <option>
    B. <option>
    C. <option>
    D. <option>
    ... (more questions) ...

    Answer Key & Rationales
    Domain 1: ...
    1.1 — Correct: D · Task 1.3 · Skill 1.3.2
    <rationale...>
    Why not the others: A — ... B — ... C — ...
    1.2 — Correct: C · ...

The parser extracts questions (id N.M, statement, options A..F, select ONE/TWO),
then the answer key (id → correct letter(s) + rationale), and merges them.
Questions are renumbered sequentially (1..N) for '## Question N:'; the original
id (e.g. 1.1) is kept at the start of the statement for reference.
"""

import re
from .base import ExamFormat, normalize_question

_Q_HDR = re.compile(r'^\s*Question\s+(\d+\.\d+)\b(.*)$', re.I)
_OPT = re.compile(r'^\s*([A-F])[\.\)]\s+(.*)$')
_ANSKEY = re.compile(r'Answer\s*Key\s*&?\s*Rationales', re.I)
_ANS_LINE = re.compile(r'^\s*(\d+\.\d+)\s*[—\-–]\s*Correct\s*:?\s*([A-F](?:\s*[,&/and]+\s*[A-F])*)', re.I)
# Repeated page footer/header (author credit + page number) to strip.
_FOOTER_RE = re.compile(r'Practice Questions?\s*·|linkedin\.com/in/|Matthew Purcell', re.I)


class MathewPdfFormat(ExamFormat):
    name = 'mathew_pdf'
    label = 'Practice PDF (questions + answer key)'

    def _text(self, path):
        import pdfplumber
        out = []
        with pdfplumber.open(path) as pdf:
            for pg in pdf.pages:
                out.append(pg.extract_text() or '')
        text = '\n'.join(out)
        # Drop repeated page footer/header lines that otherwise glue onto the
        # last option (e.g. "AIB-C01 Practice Questions · Matthew Purcell · ...").
        clean = []
        for ln in text.split('\n'):
            s = ln.strip()
            if _FOOTER_RE.search(s):
                continue
            clean.append(ln)
        return '\n'.join(clean)

    def detect(self, path: str) -> bool:
        if not str(path).lower().endswith('.pdf'):
            return False
        try:
            text = self._text(path)
            has_q = bool(re.search(r'Question\s+\d+\.\d+', text))
            has_key = bool(_ANSKEY.search(text)) or bool(re.search(r'\d+\.\d+\s*[—\-–]\s*Correct\s*:', text))
            return has_q and has_key
        except Exception:
            return False

    def parse(self, path: str, on_progress=None) -> list:
        text = self._text(path)
        lines = text.split('\n')
        # split the document at the answer-key heading
        key_start = None
        for i, l in enumerate(lines):
            if _ANSKEY.search(l):
                key_start = i
                break
        q_lines = lines[:key_start] if key_start is not None else lines
        a_lines = lines[key_start:] if key_start is not None else []

        questions = self._parse_questions(q_lines)
        answers = self._parse_answer_key(a_lines)

        # merge: set correct letters + rationale onto each question
        for q in questions:
            qid = q['_id']
            ans = answers.get(qid)
            if not ans:
                continue
            correct_letters = set(ans['letters'])
            for o in q['options']:
                if o['letter'] in correct_letters:
                    o['correct'] = True
            if ans.get('rationale'):
                q['explanation'] = ans['rationale']

        # finalize: sequential num, keep original id in statement, drop helper key
        pivot = []
        for seq, q in enumerate(sorted(questions, key=lambda x: _idkey(x['_id'])), start=1):
            statement = q['statement'].strip()
            pivot.append(normalize_question(
                seq, statement, q['options'],
                status='', explanation=q.get('explanation', '')))
        if on_progress:
            on_progress(f"Practice PDF: {len(pivot)} questions")
        return pivot

    def _parse_questions(self, lines):
        questions = []
        cur = None
        for l in lines:
            m = _Q_HDR.match(l)
            if m:
                if cur:
                    questions.append(cur)
                meta = m.group(2).lower()
                cur = {'_id': m.group(1), 'statement_lines': [], 'options': [],
                       'multi': 'select two' in meta or 'select 2' in meta}
                continue
            if cur is None:
                continue
            om = _OPT.match(l)
            if om:
                cur['options'].append({'letter': om.group(1), 'text': om.group(2).strip(),
                                       'correct': False, 'selected': False, 'rationale': ''})
            elif cur['options']:
                # continuation of the last option (wrapped line)
                if l.strip():
                    cur['options'][-1]['text'] += ' ' + l.strip()
            else:
                if l.strip():
                    cur['statement_lines'].append(l.strip())
        if cur:
            questions.append(cur)
        # assemble statement text
        for q in questions:
            q['statement'] = '\n'.join(q['statement_lines']).strip()
        return questions

    def _parse_answer_key(self, lines):
        answers = {}
        cur_id = None
        buf = []
        for l in lines:
            m = _ANS_LINE.match(l)
            if m:
                if cur_id:
                    answers[cur_id]['rationale'] = '\n'.join(buf).strip()
                cur_id = m.group(1)
                letters = re.findall(r'[A-F]', m.group(2).upper())
                answers[cur_id] = {'letters': letters, 'rationale': ''}
                buf = []
            elif cur_id:
                if l.strip():
                    buf.append(l.strip())
        if cur_id:
            answers[cur_id]['rationale'] = '\n'.join(buf).strip()
        return answers


def _idkey(sid):
    try:
        a, b = sid.split('.')
        return (int(a), int(b))
    except Exception:
        return (999, 999)
