"""
A failed book should cost what it actually cost.

An audit of 118 dead-end markers found two books lost to causes that had
nothing to do with the books: one run exhausted the disk, and one chunk of the
class 11 Physics text embedded to NaN. Both were recorded with the same
permanent marker a corrupt archive gets, and the marker is what stops the
batched runner reselecting a book forever.

These tests hold both properties at once: the retry loop stays bounded, and a
transient failure does not spend a textbook.
"""

import zipfile
from dataclasses import dataclass

import pytest

from backend.services.ingestion.ncert_ingest import (
    MAX_TRANSIENT_ATTEMPTS,
    _drop_unusable_vectors,
    _is_source_defect,
    clear_failure_record,
    record_failure,
)


@dataclass
class FakeBook:
    code: str = "keph1"
    title: str = "Physics Part-I"


@dataclass
class FakeChapter:
    number: int = 1


def marker(tmp_path, book=FakeBook()):
    return tmp_path / f"{book.code}.unavailable"


def attempts(tmp_path, book=FakeBook()):
    return tmp_path / f"{book.code}.attempts"


# --------------------------------------------------------------- classification


@pytest.mark.parametrize(
    "exc",
    [
        zipfile.BadZipFile("Bad CRC-32 for file ehhn105.pdf"),
        RuntimeError("cannot open broken document"),
        ValueError("not a zip file"),
    ],
)
def test_archive_faults_are_source_defects(exc):
    assert _is_source_defect(exc) is True


@pytest.mark.parametrize(
    "exc",
    [
        OSError(28, "No space left on device"),
        ConnectionError("connection reset by peer"),
        ValueError("NaN not allowed in vector"),
    ],
)
def test_our_own_faults_are_not_source_defects(exc):
    assert _is_source_defect(exc) is False


# ------------------------------------------------------------------- recording


def test_source_defect_is_marked_on_sight(tmp_path):
    """A corrupt archive fails the same way forever; retrying it is the bug."""
    record_failure(FakeBook(), tmp_path, zipfile.BadZipFile("Bad CRC-32 for file x.pdf"))

    assert marker(tmp_path).exists()
    assert not attempts(tmp_path).exists()
    assert "Bad CRC-32" in marker(tmp_path).read_text()


def test_transient_failure_is_retried_not_marked(tmp_path):
    """The disk-full case. The book is fine; this run was not."""
    record_failure(FakeBook(), tmp_path, OSError(28, "No space left on device"))

    assert not marker(tmp_path).exists(), "a full disk must not cost a textbook"
    assert attempts(tmp_path).read_text().startswith("1\t")


def test_transient_failure_becomes_a_dead_end_eventually(tmp_path):
    """The loop still has to terminate, which is why the markers exist at all."""
    for _ in range(MAX_TRANSIENT_ATTEMPTS):
        record_failure(FakeBook(), tmp_path, OSError(28, "No space left on device"))

    assert marker(tmp_path).exists()
    assert not attempts(tmp_path).exists(), "the tally is spent once it is promoted"
    text = marker(tmp_path).read_text()
    assert f"after {MAX_TRANSIENT_ATTEMPTS} attempts" in text
    assert "No space left on device" in text


def test_a_book_that_lands_forgets_its_earlier_failures(tmp_path):
    record_failure(FakeBook(), tmp_path, OSError(28, "No space left on device"))
    assert attempts(tmp_path).exists()

    clear_failure_record(FakeBook(), tmp_path)

    assert not attempts(tmp_path).exists()
    assert not marker(tmp_path).exists()


def test_clearing_is_safe_when_nothing_was_recorded(tmp_path):
    clear_failure_record(FakeBook(), tmp_path)  # must not raise


# ----------------------------------------------------------------- NaN vectors


def test_non_finite_vectors_are_dropped_not_fatal():
    """
    One chunk of NaN cost 15 chapters, because a book commits in one
    transaction. The cost should be one chunk.
    """
    chunks = ["good one", "the bad one", "good two"]
    vectors = [[0.1, 0.2], [float("nan"), 0.5], [0.3, 0.4]]

    kept_chunks, kept_vectors = _drop_unusable_vectors(
        FakeBook(), FakeChapter(), chunks, vectors
    )

    assert kept_chunks == ["good one", "good two"]
    assert kept_vectors == [[0.1, 0.2], [0.3, 0.4]]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_every_non_finite_value_is_caught(bad):
    kept_chunks, _ = _drop_unusable_vectors(
        FakeBook(), FakeChapter(), ["only"], [[bad, 0.0]]
    )
    assert kept_chunks == []


def test_clean_vectors_pass_through_unchanged():
    chunks = ["a", "b"]
    vectors = [[0.1, 0.2], [0.3, 0.4]]

    kept_chunks, kept_vectors = _drop_unusable_vectors(
        FakeBook(), FakeChapter(), chunks, vectors
    )

    assert kept_chunks == chunks
    assert kept_vectors == vectors
