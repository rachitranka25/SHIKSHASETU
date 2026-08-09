"""
Unit tests for the tutor's decision logic.

No model and no database. These cover the parts that decide what a student is
taught and what gets rendered into their browser — which class the answer comes
from, and whether a model-authored SVG is safe to insert.
"""

import re

import pytest

from backend.api.routes.tutor import (
    ANSWER_LANGUAGES,
    MIN_USEFUL_SIMILARITY,
    AnswerLanguage,
    detect_grade,
    extract_svg,
)


class _Row:
    """A retrieved passage, as much of one as detect_grade reads."""

    def __init__(self, grade: int | None, similarity: float):
        self.grade = grade
        self.similarity = similarity


# ==================== WHICH CLASS TEACHES THIS ====================


def test_detects_the_class_with_the_strongest_passages():
    rows = [_Row(10, 0.61), _Row(10, 0.59), _Row(10, 0.58), _Row(7, 0.40)]

    assert detect_grade(rows) == 10


def test_many_weak_hits_do_not_outvote_a_few_strong_ones():
    """
    The failure this scoring exists to prevent.

    Summing similarities let volume win: a Hinglish chemistry question matched
    eight weak passages in class 1 picture books and four strong ones in the
    class 10 chapter that actually teaches it, and the student was answered at
    class 1 level.
    """
    rows = [_Row(1, 0.40) for _ in range(8)] + [_Row(10, 0.61), _Row(10, 0.59), _Row(10, 0.58)]

    assert detect_grade(rows) == 10


def test_one_lucky_passage_does_not_decide_alone():
    """The opposite error: a single high hit against a consistent body of work."""
    rows = [_Row(3, 0.66)] + [_Row(8, 0.62), _Row(8, 0.61), _Row(8, 0.60)]

    assert detect_grade(rows) == 8


def test_passages_below_the_usefulness_floor_are_ignored():
    """Noise must not get a vote."""
    rows = [_Row(1, MIN_USEFUL_SIMILARITY - 0.01) for _ in range(20)] + [_Row(9, 0.55)]

    assert detect_grade(rows) == 9


def test_no_usable_passages_means_no_class():
    assert detect_grade([]) is None
    assert detect_grade([_Row(5, 0.10), _Row(6, 0.20)]) is None
    assert detect_grade([_Row(None, 0.90)]) is None


def test_a_single_strong_passage_is_enough():
    assert detect_grade([_Row(6, 0.72)]) == 6


# ==================== GENERATED SVG IS UNTRUSTED ====================


def test_extracts_a_plain_svg():
    raw = 'Here you go:\n<svg viewBox="0 0 400 300"><circle cx="10" cy="10" r="5"/></svg>\nHope that helps!'

    svg = extract_svg(raw)

    assert svg is not None
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "Hope that helps" not in svg


def test_none_sentinel_yields_no_diagram():
    """The model is told to say NONE when a concept cannot be drawn."""
    assert extract_svg("NONE") is None
    assert extract_svg("  none  ") is None


def test_missing_svg_yields_no_diagram():
    assert extract_svg("I cannot draw that.") is None
    assert extract_svg("") is None


@pytest.mark.parametrize(
    "payload",
    [
        '<svg viewBox="0 0 400 300"><script>alert(1)</script></svg>',
        '<svg viewBox="0 0 400 300" onload="steal()"></svg>',
        '<svg viewBox="0 0 400 300"><image onerror="x()" href="a"/></svg>',
        '<svg viewBox="0 0 400 300"><a href="javascript:x()">t</a></svg>',
    ],
)
def test_svg_carrying_script_is_discarded(payload):
    """
    This string is inserted into the page with dangerouslySetInnerHTML. A
    language model is not a trusted author, and its output can be steered by
    the question a student types.
    """
    assert extract_svg(payload) is None


def test_extraction_is_not_fooled_by_a_fenced_block():
    raw = "```svg\n<svg viewBox=\"0 0 400 300\"><rect width=\"10\" height=\"10\"/></svg>\n```"

    svg = extract_svg(raw)

    assert svg is not None
    assert "```" not in svg


# ==================== LANGUAGES ====================


def test_every_offered_language_has_an_instruction():
    """
    A language the API accepts but cannot describe to the model would silently
    produce English.
    """
    offered = set(AnswerLanguage.__args__)

    assert offered == set(ANSWER_LANGUAGES)
    assert all(ANSWER_LANGUAGES[name].strip() for name in offered)


def test_scripts_are_named_where_they_are_ambiguous():
    """
    Naming the language alone is not enough where more than one script is
    plausible: "Hindi" alone gives Devanagari, which is wrong for a student who
    asked for Hinglish.
    """
    assert "Roman" in ANSWER_LANGUAGES["Hinglish"]
    assert "Devanagari" in ANSWER_LANGUAGES["Hindi"]
    assert "Perso-Arabic" in ANSWER_LANGUAGES["Urdu"]


def test_hinglish_and_hindi_are_distinct_instructions():
    assert ANSWER_LANGUAGES["Hinglish"] != ANSWER_LANGUAGES["Hindi"]


# ==================== SQL SHAPE ====================


def test_retrieval_sql_uses_cast_not_double_colon():
    """The bind-parameter truncation that once disabled search entirely."""
    import inspect

    from backend.api.routes import tutor

    source = inspect.getsource(tutor._retrieve)
    offenders = [
        line.strip()
        for line in source.splitlines()
        if not line.strip().startswith("#")
        and re.search(r":[a-zA-Z_][a-zA-Z0-9_]*::", line)
    ]

    assert not offenders, "use CAST(:name AS type):\n" + "\n".join(offenders)
