"""
Readability measurement and syllable segmentation, for Latin and Indic scripts.

Reading support for dyslexic learners is almost entirely an English-language
field, and its tooling assumes an alphabet. Most Indian students read Devanagari
or another Brahmic script, where the unit of decoding is not the letter but the
**akshara** — a consonant cluster carrying an inherent or written vowel. A word
like क्ष्मा is three letters and one akshara-plus-matra structure, and splitting
it "per character" produces fragments no reader can decode.

So this module measures and segments both, and reports the metrics in each
script's own terms rather than forcing Latin assumptions onto Devanagari.

WHAT IS SUPPORTED BY EVIDENCE, AND WHAT IS NOT

The one typographic intervention with strong experimental support is increased
letter and word spacing: Zorzi et al. (PNAS, 2012) found extra-large spacing
improved reading speed and halved errors in dyslexic children, with no training
required, and the effect did not appear in non-dyslexic controls. Shorter
sentences and more common words reduce decoding load and are well supported in
the readability literature.

Dyslexia-specific fonts (OpenDyslexic and similar) and coloured overlays are
popular and weakly evidenced — controlled studies have not reliably shown them
to outperform ordinary fonts or clear backgrounds. They are offered to users as
preferences because some readers report benefit, but nothing here presents them
as established, and the defaults do not rely on them.

Nothing in this module diagnoses anything. It adjusts presentation.
"""

import re
import unicodedata
from dataclasses import dataclass, field

# ==================== SCRIPT DETECTION ====================
#
# Unicode blocks for the Brahmic scripts NCERT publishes in, plus Urdu's
# Perso-Arabic. Range-based rather than per-language, because a passage may mix
# scripts (English technical terms inside a Hindi sentence are the norm).
SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "Devanagari": ((0x0900, 0x097F),),   # Hindi, Marathi, Sanskrit
    "Bengali": ((0x0980, 0x09FF),),
    "Gurmukhi": ((0x0A00, 0x0A7F),),     # Punjabi
    "Gujarati": ((0x0A80, 0x0AFF),),
    "Odia": ((0x0B00, 0x0B7F),),
    "Tamil": ((0x0B80, 0x0BFF),),
    "Telugu": ((0x0C00, 0x0C7F),),
    "Kannada": ((0x0C80, 0x0CFF),),
    "Malayalam": ((0x0D00, 0x0D7F),),
    "Arabic": ((0x0600, 0x06FF), (0x0750, 0x077F)),  # Urdu
    "Latin": ((0x0041, 0x005A), (0x0061, 0x007A)),
}

# Every Brahmic script marks a dead consonant the same way, with a virama
# (halant) that suppresses the inherent vowel and binds the next consonant.
# Recognising it is what makes akshara segmentation possible generically.
VIRAMA = {
    "Devanagari": "्",
    "Bengali": "্",
    "Gurmukhi": "੍",
    "Gujarati": "્",
    "Odia": "୍",
    "Tamil": "்",
    "Telugu": "్",
    "Kannada": "್",
    "Malayalam": "്",
}

BRAHMIC = frozenset(VIRAMA)

# Combining marks: vowel signs (matras), nukta, anusvara and friends. These
# attach to the preceding consonant and never start an akshara.
_COMBINING = ("Mn", "Mc")

_WORD = re.compile(r"[^\s]+", re.UNICODE)
_SENTENCE = re.compile(r"[.!?।॥]+[\s]|[.!?।॥]+$")
_VOWEL_GROUP = re.compile(r"[aeiouy]+", re.I)


def detect_script(text: str) -> str:
    """
    The dominant script of a passage.

    Dominant rather than exclusive: Indian textbook prose routinely embeds
    English terms, and one word of Latin should not change how a Hindi
    paragraph is segmented.
    """
    counts: dict[str, int] = {}

    for char in text:
        code = ord(char)
        for script, ranges in SCRIPT_RANGES.items():
            if any(low <= code <= high for low, high in ranges):
                counts[script] = counts.get(script, 0) + 1
                break

    if not counts:
        return "Unknown"
    return max(counts, key=counts.get)


# ==================== SEGMENTATION ====================


def split_aksharas(word: str, script: str) -> list[str]:
    """
    Split a Brahmic word into aksharas — the units a reader actually decodes.

    An akshara is a consonant, plus any combining marks, plus any further
    consonants bound to it by a virama. So क्ष्मा is one unit, not four
    characters, and breaking it apart gives a struggling reader fragments that
    are unpronounceable rather than easier.

    >>> split_aksharas("नमस्ते", "Devanagari")
    ['न', 'म', 'स्ते']
    """
    virama = VIRAMA.get(script)
    if not virama:
        return [word]

    units: list[str] = []
    current = ""
    pending_virama = False

    for char in word:
        category = unicodedata.category(char)

        if category in _COMBINING:
            # A matra or nukta belongs to the akshara being built.
            current += char
            pending_virama = char == virama
            continue

        if pending_virama:
            # The previous consonant was killed; this one joins it.
            current += char
            pending_virama = False
            continue

        if current:
            units.append(current)
        current = char

    if current:
        units.append(current)

    return units or [word]


def count_latin_syllables(word: str) -> int:
    """
    Approximate syllables in an English word by vowel groups.

    Deliberately approximate. Exact syllabification needs a pronunciation
    dictionary, and the metric is used comparatively — before against after a
    rewrite — where a consistent approximation is enough.
    """
    stripped = re.sub(r"[^a-z]", "", word.lower())
    if not stripped:
        return 0

    groups = len(_VOWEL_GROUP.findall(stripped))

    # A trailing silent 'e' is not a syllable, unless it is the only one.
    if stripped.endswith("e") and groups > 1 and not stripped.endswith(("le", "ee")):
        groups -= 1

    return max(groups, 1)


def segment_word(word: str, script: str) -> list[str]:
    """Decoding units for a word, in whichever script it is written."""
    if script in BRAHMIC:
        return split_aksharas(word, script)
    return [word]


# ==================== METRICS ====================


@dataclass
class Readability:
    """
    How hard a passage is to decode.

    Reported per script, because the units differ. Comparing an
    aksharas-per-word figure to an English syllables-per-word figure is
    meaningless, and quietly doing so is how "readability" tooling ends up
    giving nonsense answers on Indian text.
    """

    script: str
    sentences: int
    words: int
    units: int  # syllables for Latin, aksharas for Brahmic
    words_per_sentence: float
    units_per_word: float
    long_words: int  # words above the decoding-load threshold
    long_word_ratio: float
    grade_estimate: float | None = None  # Flesch-Kincaid, Latin only
    hardest_words: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "script": self.script,
            "sentences": self.sentences,
            "words": self.words,
            "units": self.units,
            "words_per_sentence": round(self.words_per_sentence, 2),
            "units_per_word": round(self.units_per_word, 2),
            "long_words": self.long_words,
            "long_word_ratio": round(self.long_word_ratio, 3),
            "grade_estimate": (
                round(self.grade_estimate, 1) if self.grade_estimate is not None else None
            ),
            "hardest_words": self.hardest_words,
        }


# A word of four or more decoding units carries enough load to be worth
# flagging. The same threshold reads sensibly for both syllables and aksharas.
LONG_WORD_UNITS = 4
HARDEST_WORDS_SHOWN = 8


def count_sentences(text: str) -> int:
    """
    Sentence count, honouring the danda (।) as well as the full stop.

    Devanagari and several other Indic scripts end sentences with ।, and a
    counter that only knows about '.' reports a Hindi paragraph as one enormous
    sentence — which then makes every readability figure derived from it wrong.
    """
    parts = [part for part in _SENTENCE.split(text) if part and part.strip()]
    return max(len(parts), 1)


def measure(text: str) -> Readability:
    """Measure decoding load, in the units of the text's own script."""
    script = detect_script(text)
    words = _WORD.findall(text)
    sentences = count_sentences(text)

    if not words:
        return Readability(script, sentences, 0, 0, 0.0, 0.0, 0, 0.0)

    counter = (
        (lambda w: len(split_aksharas(w, script)))
        if script in BRAHMIC
        else count_latin_syllables
    )

    per_word = [(word, counter(word)) for word in words]
    total_units = sum(count for _, count in per_word)
    long_words = [word for word, count in per_word if count >= LONG_WORD_UNITS]

    grade = None
    if script == "Latin":
        # Flesch-Kincaid grade level. Defined for English only — applying it to
        # akshara counts would produce a confident number that means nothing.
        grade = (
            0.39 * (len(words) / sentences)
            + 11.8 * (total_units / len(words))
            - 15.59
        )

    hardest = sorted(set(long_words), key=lambda w: -counter(w))[:HARDEST_WORDS_SHOWN]

    return Readability(
        script=script,
        sentences=sentences,
        words=len(words),
        units=total_units,
        words_per_sentence=len(words) / sentences,
        units_per_word=total_units / len(words),
        long_words=len(long_words),
        long_word_ratio=len(long_words) / len(words),
        grade_estimate=grade,
        hardest_words=hardest,
    )


def segment_hard_words(text: str, threshold: int = LONG_WORD_UNITS) -> dict[str, list[str]]:
    """
    Decoding units for the words heavy enough to be worth breaking up.

    Only the hard ones: segmenting every word turns a page into confetti and
    slows down the reading it was meant to help.
    """
    script = detect_script(text)
    counter = (
        (lambda w: len(split_aksharas(w, script)))
        if script in BRAHMIC
        else count_latin_syllables
    )

    segmented: dict[str, list[str]] = {}
    for word in _WORD.findall(text):
        cleaned = word.strip(".,;:!?()[]\"'।॥")
        if not cleaned or cleaned in segmented:
            continue
        if counter(cleaned) >= threshold:
            units = segment_word(cleaned, script)
            if len(units) > 1:
                segmented[cleaned] = units

    return segmented
