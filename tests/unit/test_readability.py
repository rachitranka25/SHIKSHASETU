"""
Unit tests for readability measurement and script-aware segmentation.

The akshara logic is the part worth testing hardest. Splitting Devanagari the
naive way — per character — produces fragments a reader cannot pronounce, which
is worse than not segmenting at all, and the error is invisible to anyone
reading the code in Latin script.
"""

import pytest

from backend.services.accessibility import (
    detect_script,
    measure,
    segment_hard_words,
    segment_word,
    split_aksharas,
)
from backend.services.accessibility.readability import (
    LONG_WORD_UNITS,
    count_latin_syllables,
    count_sentences,
)

# ==================== AKSHARA SEGMENTATION ====================


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        # स् + ते is one conjunct and must not be split between them
        ("नमस्ते", ["न", "म", "स्ते"]),
        # प् + र likewise
        ("प्रकाश", ["प्र", "का", "श"]),
        ("विद्यार्थी", ["वि", "द्या", "र्थी"]),
        ("संश्लेषण", ["सं", "श्ले", "ष", "ण"]),
        # Single akshara stays whole
        ("का", ["का"]),
    ],
)
def test_devanagari_splits_on_aksharas(word, expected):
    assert split_aksharas(word, "Devanagari") == expected


def test_a_matra_never_starts_a_unit():
    """
    A vowel sign attaches to its consonant. Left on its own it is a mark with
    nothing to attach to, and unreadable.
    """
    for unit in split_aksharas("किताब", "Devanagari"):
        assert unit[0] not in "ािीुूेैोौ्ं"


def test_virama_binds_the_following_consonant():
    """The whole point: a dead consonant joins what comes next."""
    units = split_aksharas("स्कूल", "Devanagari")

    assert units[0] == "स्कू", units
    assert "्" not in "".join(u[0] for u in units)


def test_segmentation_is_lossless():
    """Rejoining the units must give back the word, for every script."""
    for word, script in [
        ("नमस्ते", "Devanagari"),
        ("विद्यार्थी", "Devanagari"),
        ("শিক্ষা", "Bengali"),
        ("கல்வி", "Tamil"),
        ("ವಿದ್ಯಾ", "Kannada"),
    ]:
        assert "".join(split_aksharas(word, script)) == word


def test_non_brahmic_words_are_left_whole():
    """There is no akshara in Latin, and pretending otherwise helps nobody."""
    assert segment_word("photosynthesis", "Latin") == ["photosynthesis"]
    assert split_aksharas("hello", "Latin") == ["hello"]


def test_empty_input_does_not_crash():
    assert split_aksharas("", "Devanagari") == [""]


# ==================== SCRIPT DETECTION ====================


@pytest.mark.parametrize(
    ("text", "script"),
    [
        ("The human eye focuses light", "Latin"),
        ("प्रकाश संश्लेषण एक प्रक्रिया है", "Devanagari"),
        ("ஒளிச்சேர்க்கை என்றால் என்ன", "Tamil"),
        ("মানুষের চোখ কীভাবে কাজ করে", "Bengali"),
        ("ਵਿਦਿਆਰਥੀ", "Gurmukhi"),
        ("વિદ્યાર્થી", "Gujarati"),
    ],
)
def test_detects_the_script(text, script):
    assert detect_script(text) == script


def test_dominant_script_wins_over_embedded_terms():
    """
    Indian textbook prose embeds English constantly. One Latin word must not
    make a Hindi paragraph be treated as English, because that changes which
    segmentation and which metrics apply.
    """
    mixed = "प्रकाश संश्लेषण की प्रक्रिया में chlorophyll की भूमिका होती है"

    assert detect_script(mixed) == "Devanagari"


def test_text_without_letters_is_unknown():
    assert detect_script("123 ... !!") == "Unknown"


# ==================== SENTENCES ====================


def test_danda_ends_a_hindi_sentence():
    """
    Devanagari ends sentences with ।, not a full stop. A counter that only
    knows '.' calls a Hindi paragraph one sentence, and every figure derived
    from it — words per sentence, grade level — is then wrong.
    """
    hindi = "यह पहला वाक्य है। यह दूसरा वाक्य है। यह तीसरा है।"

    assert count_sentences(hindi) == 3


def test_english_sentences_are_counted():
    assert count_sentences("One. Two! Three? Four.") == 4


def test_text_with_no_terminator_counts_as_one():
    assert count_sentences("a sentence with no full stop") == 1


# ==================== LATIN SYLLABLES ====================


@pytest.mark.parametrize(
    ("word", "count"),
    [("cat", 1), ("water", 2), ("photosynthesis", 5), ("the", 1), ("make", 1)],
)
def test_latin_syllable_approximation(word, count):
    assert count_latin_syllables(word) == count


def test_every_real_word_has_at_least_one_syllable():
    for word in ("rhythm", "a", "strengths"):
        assert count_latin_syllables(word) >= 1


# ==================== MEASUREMENT ====================


def test_measures_english_with_a_grade_level():
    text = "The cat sat on the mat. The dog ran fast."

    metrics = measure(text)

    assert metrics.script == "Latin"
    assert metrics.sentences == 2
    assert metrics.words == 10
    assert metrics.grade_estimate is not None


def test_no_grade_level_is_claimed_for_devanagari():
    """
    Flesch-Kincaid is defined on English syllables. Running it over akshara
    counts yields a confident number that means nothing, so none is given.
    """
    metrics = measure("प्रकाश संश्लेषण एक प्रक्रिया है। पौधे भोजन बनाते हैं।")

    assert metrics.script == "Devanagari"
    assert metrics.grade_estimate is None
    assert metrics.units_per_word > 0


def test_simpler_text_measures_easier():
    """The metric has to move in the direction a reader would agree with."""
    hard = measure(
        "Photosynthesis constitutes the biochemical mechanism whereby chlorophyllous "
        "organisms synthesise carbohydrates utilising electromagnetic radiation."
    )
    easy = measure("Plants make food. They use sunlight. They use water and air.")

    assert easy.words_per_sentence < hard.words_per_sentence
    assert easy.units_per_word < hard.units_per_word
    assert easy.grade_estimate < hard.grade_estimate


def test_empty_text_measures_without_crashing():
    metrics = measure("")

    assert metrics.words == 0
    assert metrics.units_per_word == 0.0


def test_long_words_are_counted_and_named():
    metrics = measure("Photosynthesis and respiration are complementary.")

    assert metrics.long_words >= 1
    assert any(len(word) > 6 for word in metrics.hardest_words)


# ==================== PICKING WHAT TO SEGMENT ====================


def test_only_hard_words_are_segmented():
    """Breaking up every word turns the page into confetti."""
    segmented = segment_hard_words("प्रकाश संश्लेषण एक प्रक्रिया है")

    assert all(
        len(units) > 1 for units in segmented.values()
    ), "a single-unit 'segmentation' helps nobody"
    assert "है" not in segmented


def test_segmentation_ignores_punctuation():
    segmented = segment_hard_words("संश्लेषण। प्रक्रिया,")

    assert all("।" not in word and "," not in word for word in segmented)


def test_short_english_text_needs_no_segmentation():
    assert segment_hard_words("the cat sat on the mat") == {}


def test_threshold_is_respected():
    everything = segment_hard_words("प्रकाश संश्लेषण प्रक्रिया", threshold=1)
    defaults = segment_hard_words("प्रकाश संश्लेषण प्रक्रिया")

    assert len(everything) >= len(defaults)
    assert LONG_WORD_UNITS > 1
