"""
Accessibility services.

Presentation and text adaptation for learners who need it — currently reading
support for dyslexia, measured in the units of whichever script the text is
written in rather than assuming an alphabet.

Nothing here diagnoses anything.
"""

from .readability import (
    Readability,
    detect_script,
    measure,
    segment_hard_words,
    segment_word,
    split_aksharas,
)

__all__ = [
    "Readability",
    "detect_script",
    "measure",
    "segment_hard_words",
    "segment_word",
    "split_aksharas",
]
