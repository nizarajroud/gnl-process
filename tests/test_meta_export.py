"""Tests for the generic Meta AI export module."""
from gnl_core.meta_export import build_parts, DEFAULT_PROMPT
from gnl_core.exam_formats.base import normalize_question


def _pivot(n):
    out = []
    for i in range(1, n + 1):
        out.append(normalize_question(
            i, f"Statement {i} " + ("x" * 500),
            [{'letter': 'A', 'text': 'opt A ' + 'y' * 300, 'correct': True, 'rationale': 'because A ' + 'z' * 300},
             {'letter': 'B', 'text': 'opt B', 'correct': False, 'rationale': 'B wrong'}]))
    return out


def test_single_part_small_pivot():
    parts = build_parts(_pivot(2), max_chars=65000)
    assert len(parts) == 1
    assert 'senior AWS Solutions Architect' in parts[0]
    assert 'OF 1' in parts[0]
    assert '## Question 1:' in parts[0] and '## Question 2:' in parts[0]


def test_splits_into_multiple_parts_under_limit():
    # Each question ~1600 chars; with a small limit we force several parts.
    pivot = _pivot(30)
    parts = build_parts(pivot, max_chars=8000)
    assert len(parts) > 1
    for p in parts:
        assert len(p) <= 8000 + 2000  # body boundary tolerance (1 question)
    # prompt only in part 1
    assert 'senior AWS Solutions Architect' in parts[0]
    assert all('senior AWS Solutions Architect' not in p for p in parts[1:])
    # N filled consistently
    n = len(parts)
    assert f'OF {n}' in parts[0]


def test_questions_not_split_across_parts():
    pivot = _pivot(20)
    parts = build_parts(pivot, max_chars=9000)
    joined = "\n".join(parts)
    # every question appears exactly once
    for i in range(1, 21):
        assert joined.count(f"## Question {i}:") == 1


def test_custom_prompt_and_placeholder():
    parts = build_parts(_pivot(2), max_chars=65000,
                        prompt_template="CUSTOM PROMPT {N} parts")
    assert parts[0].startswith("CUSTOM PROMPT 1 parts")


def test_exam_plan_b_markdown(tmp_path):
    """Plan B (exam): build_meta_corpus + generate_meta_markdown write one .md
    containing the prompt header and every question; build_parts is unchanged."""
    from gnl_core.meta_export import (build_parts, build_meta_corpus,
                                     generate_meta_markdown)
    pivot = [
        {'num': 1, 'statement': 'Q one?',
         'options': [{'letter': 'A', 'text': 'a', 'rationale': 'because a', 'correct': True},
                     {'letter': 'B', 'text': 'b', 'rationale': 'nope', 'correct': False}]},
        {'num': 2, 'statement': 'Q two?',
         'options': [{'letter': 'A', 'text': 'a', 'rationale': 'nope', 'correct': False},
                     {'letter': 'B', 'text': 'b', 'rationale': 'because b', 'correct': True}]},
    ]
    # Plan A still works and is unaffected.
    parts = build_parts(pivot)
    assert len(parts) >= 1
    # Plan B corpus contains both questions.
    corpus = build_meta_corpus(pivot)
    assert 'Q one?' in corpus and 'Q two?' in corpus
    # Writer drops a single .md in the given dir.
    res = generate_meta_markdown(pivot, 'my-exam', icloud_dir=str(tmp_path))
    import os
    assert os.path.exists(res['path']) and res['path'].endswith('my-exam.md')
    assert res['chars'] == len(open(res['path'], encoding='utf-8').read())
