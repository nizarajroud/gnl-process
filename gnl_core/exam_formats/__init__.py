"""
Exam format registry — auto-detection dispatch.

Register formats here (order matters: more specific first). To add a new
format: create a module with an ExamFormat subclass and append it to FORMATS.
"""

from .base import ExamFormat, normalize_question
from .aws_practice_exam import AwsPracticeExamFormat
from .dojo import DojoFormat

# Order: most specific / table-based first, generic paragraph-based last.
FORMATS = [
    AwsPracticeExamFormat(),
    DojoFormat(),
]


def detect_format(path):
    """Return the first ExamFormat whose detect() matches, or None."""
    for fmt in FORMATS:
        try:
            if fmt.detect(path):
                return fmt
        except Exception:
            continue
    return None


def get_format_by_name(name):
    for fmt in FORMATS:
        if fmt.name == name:
            return fmt
    return None


__all__ = [
    'ExamFormat', 'normalize_question',
    'FORMATS', 'detect_format', 'get_format_by_name',
    'AwsPracticeExamFormat', 'DojoFormat',
]
