"""
Unit tests for upload size and type enforcement.

Every upload endpoint buffers the whole file in memory before handing it to a
model, so an unbounded body is a straight route to OOM. /stt/guest takes no
auth at all, which means that route was reachable by anyone. These tests pin
the cap and the type allowlist that close it.
"""

import pytest
from fastapi import HTTPException, UploadFile

from backend.api.routes.content import (
    _AUDIO_SUFFIXES,
    _DOCUMENT_SUFFIXES,
    MAX_UPLOAD_BYTES,
    _read_upload,
)


class _FakeUpload:
    """Minimal stand-in for UploadFile: a filename and a chunked body."""

    def __init__(self, filename: str | None, body: bytes):
        self.filename = filename
        self._body = body
        self._offset = 0

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk = self._body[self._offset :]
            self._offset = len(self._body)
            return chunk
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


async def test_reads_a_small_allowed_upload():
    content, suffix = await _read_upload(
        _FakeUpload("lecture.mp3", b"audio-bytes"), _AUDIO_SUFFIXES, ".wav"
    )

    assert content == b"audio-bytes"
    assert suffix == ".mp3"


async def test_reassembles_a_multi_chunk_upload():
    """The body is read in 64 KiB chunks; it must come back whole."""
    body = b"x" * (200 * 1024)

    content, _ = await _read_upload(
        _FakeUpload("lecture.wav", body), _AUDIO_SUFFIXES, ".wav"
    )

    assert content == body


async def test_rejects_an_oversized_upload():
    """The whole point: a body past the cap is refused with 413."""
    oversized = b"x" * (MAX_UPLOAD_BYTES + 1)

    with pytest.raises(HTTPException) as exc:
        await _read_upload(_FakeUpload("huge.wav", oversized), _AUDIO_SUFFIXES, ".wav")

    assert exc.value.status_code == 413


async def test_accepts_an_upload_exactly_at_the_cap():
    """The limit is inclusive, so a file at the boundary still works."""
    at_limit = b"x" * MAX_UPLOAD_BYTES

    content, _ = await _read_upload(
        _FakeUpload("big.wav", at_limit), _AUDIO_SUFFIXES, ".wav"
    )

    assert len(content) == MAX_UPLOAD_BYTES


async def test_rejects_a_disallowed_extension():
    """An executable is not audio, whatever the client calls it."""
    with pytest.raises(HTTPException) as exc:
        await _read_upload(_FakeUpload("payload.exe", b"MZ"), _AUDIO_SUFFIXES, ".wav")

    assert exc.value.status_code == 415


async def test_rejects_type_before_reading_the_body():
    """A bad type must not cost us a full read of a huge body first."""
    upload = _FakeUpload("payload.exe", b"x" * (MAX_UPLOAD_BYTES + 1))

    with pytest.raises(HTTPException) as exc:
        await _read_upload(upload, _AUDIO_SUFFIXES, ".wav")

    assert exc.value.status_code == 415
    assert upload._offset == 0  # nothing was consumed


async def test_falls_back_to_the_default_suffix_when_filename_is_missing():
    _, suffix = await _read_upload(_FakeUpload(None, b"data"), _AUDIO_SUFFIXES, ".webm")

    assert suffix == ".webm"


async def test_suffix_is_lowercased():
    """Clients send .WAV and .MP3; the allowlist is lowercase."""
    _, suffix = await _read_upload(
        _FakeUpload("RECORDING.WAV", b"data"), _AUDIO_SUFFIXES, ".wav"
    )

    assert suffix == ".wav"


@pytest.mark.parametrize(
    "filename",
    [
        "audio.wav/../../../etc/passwd",
        "../../../etc/passwd",
        "../../secrets.wav",
        "/absolute/path/clip.wav",
        "clip.wav\x00.sh",
    ],
)
async def test_suffix_never_carries_a_path(filename):
    """
    The suffix is handed to NamedTemporaryFile, so it must never contain a
    path. Only the extension is ever taken from the client's filename — the
    rest is discarded — and the allowlist then has to recognise whatever is
    left, so a traversal attempt either degrades to the safe default or is
    refused outright.
    """
    try:
        _, suffix = await _read_upload(
            _FakeUpload(filename, b"data"), _AUDIO_SUFFIXES, ".wav"
        )
    except HTTPException as exc:
        assert exc.status_code == 415
        return

    assert "/" not in suffix
    assert ".." not in suffix
    assert "\x00" not in suffix
    assert suffix in _AUDIO_SUFFIXES


async def test_extension_after_a_traversal_attempt_is_still_checked():
    """A traversal path ending in a real extension is judged on it."""
    with pytest.raises(HTTPException) as exc:
        await _read_upload(
            _FakeUpload("audio.wav/../../../etc/evil.sh", b"data"),
            _AUDIO_SUFFIXES,
            ".wav",
        )

    assert exc.value.status_code == 415


async def test_document_and_audio_allowlists_are_distinct():
    """An audio route must not accept a PDF, and vice versa."""
    with pytest.raises(HTTPException):
        await _read_upload(_FakeUpload("notes.pdf", b"%PDF"), _AUDIO_SUFFIXES, ".wav")

    with pytest.raises(HTTPException):
        await _read_upload(_FakeUpload("song.mp3", b"ID3"), _DOCUMENT_SUFFIXES, ".png")


def test_cap_is_a_sane_size():
    """A cap so large it cannot protect anything is not a cap."""
    assert 0 < MAX_UPLOAD_BYTES <= 200 * 1024 * 1024
