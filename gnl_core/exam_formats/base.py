"""
Exam format parsers — plug-and-play architecture.

Each exam source (DOJO, AWS Practice Exam, Udemy, ...) is a *format* that knows:
  - detect(path)   -> bool     : "is this document my format?"
  - parse(path, ...) -> list   : produce the NORMALIZED pivot structure

The pipeline never hard-codes a format. It asks the registry to detect the
right parser, calls parse(), and builds the artifacts (markdown, Anki, podcast)
from the common pivot. Adding a new format = drop a new module + register it.

Normalized pivot — one dict per question:
    {
        'num': int,                 # question number (1-based)
        'statement': str,           # the question text (may be multi-paragraph)
        'options': [
            {
                'letter': str,      # 'A', 'B', ... ('' if unknown)
                'text': str,        # option text
                'correct': bool,    # is this a correct answer?
                'selected': bool,   # did the user pick it? (False if unknown)
                'rationale': str,   # per-option explanation ('' if none)
            }, ...
        ],
        'status': str,              # 'Correct' | 'Incorrect' | '' (optional)
        'explanation': str,         # global explanation ('' if per-option only)
    }
"""

from abc import ABC, abstractmethod


class ExamFormat(ABC):
    """Contract every exam-format parser must implement."""

    #: Short stable identifier, e.g. 'dojo', 'aws_practice_exam'.
    name = 'base'
    #: Human-readable label for UI/logs.
    label = 'Base'

    @abstractmethod
    def detect(self, path: str) -> bool:
        """Return True if `path` (a .docx) is this format. Must be cheap and
        side-effect free. Should never raise — return False on any doubt."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, path: str, on_progress=None) -> list:
        """Return the normalized pivot: a list of question dicts (see module
        docstring). May be expensive (Bedrock, etc.) depending on the format."""
        raise NotImplementedError


def normalize_question(num, statement, options, status='', explanation=''):
    """Helper to build a well-formed pivot question dict."""
    norm_opts = []
    for o in options:
        norm_opts.append({
            'letter': o.get('letter', ''),
            'text': o.get('text', ''),
            'correct': bool(o.get('correct', False)),
            'selected': bool(o.get('selected', False)),
            'rationale': o.get('rationale', '') or '',
        })
    return {
        'num': int(num),
        'statement': (statement or '').strip(),
        'options': norm_opts,
        'status': status or '',
        'explanation': (explanation or '').strip(),
    }
