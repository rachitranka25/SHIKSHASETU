"""
Unit tests for the tutor's decision logic.

No model and no database. These cover the parts that decide what a student is
taught and what is shown to them — which class the answer comes from, which
textbook editions may be taught out of, and what the illustration is asked for.
"""

import re

import pytest

from backend.api.routes.tutor import (
    ANSWER_LANGUAGES,
    MIN_USEFUL_SIMILARITY,
    AnswerLanguage,
    detect_grade,
    merge_hits,
    vote_grade,
)


class _Row:
    """A retrieved passage, as much of one as detect_grade reads."""

    def __init__(self, grade: int | None, similarity: float, passage: str = "", subject: str = "", chapter: int = 1):
        self.grade = grade
        self.similarity = similarity
        self.passage = passage or f"passage g{grade} s{similarity}"
        self.subject = subject
        self.chapter = chapter


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


# ==================== ILLUSTRATIONS ====================


def test_illustration_prompt_forbids_text_in_the_image():
    """
    Diffusion models misspell words, and a textbook diagram with garbled labels
    is worse than one with none. The labels come from the explanation instead,
    as real characters.
    """
    from backend.services.illustration import build_scene_prompt

    prompt = build_scene_prompt("the water cycle", "Water evaporates from lakes.")

    lowered = prompt.lower()
    assert "no text" in lowered
    assert "no words" in lowered
    assert "no labels" in lowered


def test_illustration_prompt_includes_the_explanation():
    """
    The concept alone draws something generic. A sentence of the explanation is
    what makes it this lesson's picture.
    """
    from backend.services.illustration import build_scene_prompt

    prompt = build_scene_prompt("photosynthesis", "Green leaves absorb sunlight.")

    assert "photosynthesis" in prompt
    assert "Green leaves absorb sunlight" in prompt


def test_illustration_is_skipped_without_a_key(monkeypatch):
    """A missing picture must never cost the student the explanation."""
    from backend.core.config import settings
    from backend.services import illustration

    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "")

    assert illustration.generate_illustration("anything") is None


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


def test_teaching_sources_exclude_urdu():
    """
    NCERT publishes each chapter in English, Hindi and Urdu, and cross-lingual
    retrieval happily returned the Urdu edition for an English question — so a
    student was shown "Class 1 Joyful-Mathematics (Urdu), chapter 13" as the
    source of their answer, in a script they cannot read and cannot check.

    The same repetition also crowded the context: six passages could be one
    chapter in three scripts.
    """
    from backend.api.routes.tutor import TEACHING_MEDIA

    assert "Urdu" not in TEACHING_MEDIA
    assert set(TEACHING_MEDIA) == {"English", "Hindi"}


def test_retrieval_filters_by_medium():
    """The restriction has to reach the query, not just the constant."""
    import inspect

    from backend.api.routes import tutor

    source = inspect.getsource(tutor._retrieve)

    assert "medium" in source
    assert ":media" in source, "the medium filter must be a bound parameter"


def test_source_medium_does_not_constrain_the_answer_language():
    """
    Teaching from an English textbook must still allow a Tamil answer. These
    are separate axes and conflating them would undo the point of the feature.
    """
    from backend.api.routes.tutor import ANSWER_LANGUAGES, TEACHING_MEDIA

    assert set(ANSWER_LANGUAGES) - set(TEACHING_MEDIA), (
        "answers must be available in languages beyond the teaching media"
    )
    assert "Tamil" in ANSWER_LANGUAGES
    assert "Urdu" in ANSWER_LANGUAGES, (
        "an Urdu-speaking student may still want the answer in Urdu, taught "
        "from the English edition"
    )


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


# ==================== VOTING ACROSS QUERY PHRASINGS ====================


def test_a_unanimous_query_beats_one_that_leads_narrowly():
    """
    The failure this exists for. Asked "Rahiman dekhi baden ko, laghu na
    deejiye daari", the student's own wording ranked class 6 Malhar -- which
    contains that couplet -- in every one of its hits, while the English
    rewrite put a class 3 reader on top and class 6 just behind it. Pooling the
    two by similarity let the rewrite's numerically larger scores win, and the
    answer came back from a class 3 book about bus safety.
    """
    raw = [_Row(6, 0.50), _Row(6, 0.43), _Row(6, 0.42), _Row(6, 0.41)]
    rewrite = [_Row(3, 0.513), _Row(3, 0.497), _Row(3, 0.490), _Row(6, 0.489)]

    assert vote_grade([raw, rewrite]) == 6


def test_a_class_both_queries_agree_on_wins():
    """Corroboration counts before decisiveness does."""
    raw = [_Row(8, 0.60), _Row(8, 0.58), _Row(8, 0.57), _Row(4, 0.40)]
    rewrite = [_Row(8, 0.55), _Row(8, 0.54), _Row(8, 0.53), _Row(9, 0.52)]

    assert vote_grade([raw, rewrite]) == 8


def test_a_decisive_vote_on_thin_evidence_loses_to_a_solid_one():
    """
    A query whose only hit is one weak passage is unanimous by default. That is
    not authority, so the lead is weighted by the evidence behind it.
    """
    thin = [_Row(2, 0.36)]
    solid = [_Row(11, 0.62), _Row(11, 0.61), _Row(11, 0.60), _Row(5, 0.38)]

    assert vote_grade([thin, solid]) == 11


def test_vote_grade_returns_none_when_nothing_is_useful():
    assert vote_grade([[_Row(6, 0.10)], [_Row(3, 0.20)]]) is None


def test_vote_grade_survives_a_query_that_matched_nothing():
    """One empty result must not silence the other."""
    assert vote_grade([[], [_Row(7, 0.55), _Row(7, 0.54)]]) == 7


# ==================== POOLING PASSAGES ====================


def test_merge_hits_keeps_each_passage_once_at_its_best_score():
    """
    Both phrasings find the same passage; it is one passage, and its score is
    the better of the two. Summing would let the overlap between two wordings
    of the same question outrank a passage only one of them found.
    """
    a = [_Row(6, 0.50, passage="the couplet", subject="Malhar", chapter=5)]
    b = [_Row(6, 0.61, passage="the couplet", subject="Malhar", chapter=5)]

    merged = merge_hits([a, b], 5)

    assert len(merged) == 1
    assert merged[0].similarity == 0.61


def test_merge_hits_orders_by_score_and_respects_the_limit():
    a = [_Row(6, 0.40, passage="one"), _Row(6, 0.70, passage="two")]
    b = [_Row(8, 0.55, passage="three")]

    merged = merge_hits([a, b], 2)

    assert [r.similarity for r in merged] == [0.70, 0.55]
