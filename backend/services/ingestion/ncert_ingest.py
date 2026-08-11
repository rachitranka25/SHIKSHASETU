"""
NCERT Ingestion Pipeline
========================

Turns NCERT textbooks into retrievable chunks: download the book, pull text out
of each chapter PDF, split it, embed it, and store it with enough metadata that
a query can be scoped to a class and subject.

Built to survive a long run. NCERT serves large PDFs from a government host
that resets connections under load, and the full catalog is 558 books, so every
stage is resumable: a completed download is not re-fetched, and a book already
in the database is skipped unless forced. Killing the process and starting it
again picks up where it stopped.

One `processed_content` row per chapter, its `document_chunks` beneath it, and
one embedding per chunk.
"""

import io
import logging
import os
import re
import tempfile
import time
import uuid
import zipfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ...core.config import settings
from .ncert_catalog import USER_AGENT, Textbook

logger = logging.getLogger(__name__)

# Alongside the catalog, under the repo's data/ directory. Both are gitignored:
# the corpus is large and re-downloadable.
DOWNLOAD_DIR = Path(__file__).resolve().parents[3] / "data" / "ncert"

# Chunking. BGE-M3 handles long inputs, but retrieval quality drops when a chunk
# spans several ideas, and a student's answer should cite a passage rather than
# a whole chapter. Overlap keeps a sentence that straddles a boundary reachable
# from both sides.
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200
MIN_CHUNK_CHARS = 120

# Politeness. This is a public education ministry host, not a CDN.
REQUEST_DELAY_SECONDS = 1.0
DOWNLOAD_ATTEMPTS = 4
DOWNLOAD_TIMEOUT = 180.0

LANGUAGE_CODES = {"English": "en", "Hindi": "hi", "Urdu": "ur"}

# NCERT chapter PDFs inside a book zip are named <code><chapter>.pdf, plus front
# matter (`ps`, `pr`) and back matter (`an`, `gl`) we do not want as chapters.
_CHAPTER_FILE = re.compile(r"([a-l][ehu][a-z]{2}\d)(\d{2})\.pdf$", re.I)

# ==================== WHEN EMBEDDED TEXT CANNOT BE TRUSTED ====================
#
# PyMuPDF reads the text layer, and on NCERT's maths PDFs that layer is lossy in
# a way that changes meaning. Class 10 Maths chapter 4 defines a quadratic as
#
#     ax² + bx + c, a ≠ 0
#
# and the text layer yields "ax2 + bx + c, a  0". Rendering the same page proves
# both glyphs are present and correct — only the extraction drops them. So the
# superscript is flattened and the inequality is deleted outright, turning a
# constraint into its opposite. Fine in prose, unacceptable in mathematics.
#
# Pages like that are recognisable before OCR: NCERT sets equations as inline
# images, so image count relative to text length separates them cleanly.
# Measured images per 1000 characters:
#
#     Class 10 Maths ch4 (equations)   30.8
#     Class 10 Science ch8 (figures)    5.9
#     Class 10 Science ch5 (prose)      4.0
#     Class 10 Science ch1 (mixed)      2.0
#
# The gap is wide, so the threshold sits between rather than near either side.
#
# A tempting alternative — looking for the run of spaces a dropped glyph leaves
# behind — was tried and discarded: justified prose produces exactly the same
# pattern at the same rate, so it identifies nothing.
OCR_IMAGE_DENSITY = 15.0  # images per 1000 characters
OCR_MIN_PAGE_CHARS = 200  # below this, the page is a diagram with a caption
OCR_RENDER_SCALE = 3.0  # 3x renders equations large enough to read reliably

# Whether the next book is fetched while the current one is embedded. On by
# default; INGEST_PREFETCH=0 turns it off so the two paths can be compared on
# the same books, which is the only way to state a speedup honestly. Download
# and embedding contend for nothing -- one waits on a government web server, the
# other saturates the GPU -- so overlapping them should help, but "should" is
# not a measurement.
PREFETCH_ENABLED = os.getenv("INGEST_PREFETCH", "1") not in ("0", "false", "False")

# Older NCERT books are typeset in legacy Devanagari fonts -- Walkman-Chanakya
# 905 in the Hindi readers, and its relatives elsewhere -- which map Devanagari
# glyphs onto ASCII codepoints and ship no ToUnicode table. Extraction returns
# the raw bytes, so Class 10's Kshitij-2 comes out as
#
#     dkO; [kaM ... rqylhnkl ... lu~ 1532 esa gqvk FkkA
#
# where the text is actually
#
#     काव्य खंड ... तुलसीदास ... सन् 1532 में हुआ था।
#
# It is not detectable by looking for broken Devanagari, because there is no
# Devanagari in it at all -- a fact that made an earlier quality pass rank
# these books as the *cleanest* in the corpus. What identifies them is the
# reverse: a Hindi book whose extracted text is overwhelmingly Latin.
#
# Storing it is worse than skipping it. The text is unreadable to a student,
# and BGE-M3 embeds it as meaningless Latin, so it competes for retrieval slots
# against passages that would have helped. 27 of the 41 in-scope Hindi books
# are affected; recovering them needs a Chanakya-to-Unicode transliteration,
# which is a separate piece of work.
LEGACY_FONT_MAX_DEVANAGARI = 0.5  # fraction of letters that must be Devanagari
LEGACY_FONT_MIN_LETTERS = 200  # below this the sample is too small to judge

_DEVANAGARI = re.compile(r"[\u0900-\u097f]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")

# PDF text arrives with hyphenated line breaks and hard-wrapped lines.
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_SINGLE_NEWLINE = re.compile(r"(?<!\n)\n(?!\n)")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_BLANK = re.compile(r"\n{3,}")


@dataclass
class Chapter:
    """One chapter's extracted text."""

    number: int
    text: str
    page_count: int


@dataclass
class IngestStats:
    """What a run did, for the caller to report."""

    books_done: int = 0
    books_skipped: int = 0
    books_failed: int = 0
    chapters: int = 0
    chunks: int = 0

    def __str__(self) -> str:
        return (
            f"{self.books_done} books ingested, {self.books_skipped} skipped, "
            f"{self.books_failed} failed; {self.chapters} chapters, {self.chunks} chunks"
        )


# ==================== DOWNLOAD ====================


def download_book(
    book: Textbook,
    download_dir: Path = DOWNLOAD_DIR,
    client: httpx.Client | None = None,
) -> Path | None:
    """
    Fetch a book's zip, reusing it if already on disk.

    Returns:
        Path to the zip, or None if NCERT does not publish one for this code
        (404 is common — the catalog lists books whose zips were never posted).
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    target = download_dir / f"{book.code}.zip"

    if target.exists() and target.stat().st_size > 0:
        logger.debug("%s already downloaded", book.code)
        return target

    # Roughly a quarter of catalogued books have no zip published. Without a
    # record of that, every run re-requests all of them — which for a batched
    # run over 558 books means the same wasted round trips on every batch.
    missing_marker = download_dir / f"{book.code}.unavailable"
    if missing_marker.exists():
        logger.debug("%s known to have no zip, skipping", book.code)
        return None

    # Spacing between requests. The loop used to pace this; downloads now run
    # on a prefetch thread, so the courtesy has to live where the request is
    # actually made. This is a public education ministry host.
    time.sleep(REQUEST_DELAY_SECONDS)

    owns_client = client is None
    client = client or httpx.Client(
        timeout=DOWNLOAD_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )

    try:
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            try:
                response = client.get(book.zip_url)

                if response.status_code == 404:
                    logger.info("%s: no zip published (404)", book.code)
                    missing_marker.touch()
                    return None
                response.raise_for_status()

                # Write to a temp name first so an interrupted run never leaves a
                # truncated zip that the next run would treat as complete.
                partial = target.with_suffix(".zip.part")
                partial.write_bytes(response.content)
                partial.rename(target)

                logger.info(
                    "%s: downloaded %.1f MB", book.code, len(response.content) / 1e6
                )
                return target

            except httpx.HTTPError as exc:
                logger.warning(
                    "%s: download attempt %s/%s failed: %s",
                    book.code, attempt, DOWNLOAD_ATTEMPTS, exc,
                )
                if attempt < DOWNLOAD_ATTEMPTS:
                    time.sleep(2.0 * attempt)

        logger.error("%s: giving up after %s attempts", book.code, DOWNLOAD_ATTEMPTS)
        return None

    finally:
        if owns_client:
            client.close()


# ==================== EXTRACT ====================


def clean_pdf_text(raw: str) -> str:
    """
    Repair the artefacts PDF extraction leaves behind.

    Rejoins words split across a line break, unwraps hard-wrapped lines while
    keeping paragraph breaks, and collapses runs of whitespace. Without this,
    chunks are full of mid-word hyphens and every line is its own fragment.
    """
    text = _HYPHEN_BREAK.sub(r"\1\2", raw)
    text = _SINGLE_NEWLINE.sub(" ", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def page_needs_ocr(page, raw_text: str) -> bool:
    """
    Whether a page's embedded text layer should be distrusted.

    Two cases, both measured on real NCERT pages (see the constants above):
    a page whose text is dense with inline equation images, and a page that is
    essentially a diagram with almost no text at all.
    """
    chars = len(raw_text.strip())
    images = len(page.get_images())

    if chars < OCR_MIN_PAGE_CHARS:
        # Only worth OCR if there is something on the page to read.
        return bool(images) or bool(page.get_drawings())

    return (images * 1000.0 / chars) > OCR_IMAGE_DENSITY


def ocr_page(page, ocr_engine) -> str:
    """
    Re-read a page by rendering it and running OCR over the image.

    Rendering uses the embedded fonts, so glyphs the text layer failed to map
    are drawn correctly and the OCR sees them. GOT-OCR2's "format" mode returns
    formulas as LaTeX rather than flattening them.
    """
    import fitz  # PyMuPDF

    matrix = fitz.Matrix(OCR_RENDER_SCALE, OCR_RENDER_SCALE)
    pixmap = page.get_pixmap(matrix=matrix)

    # Via a temp file, not a PIL Image. ocr_image() is typed to accept an
    # Image, but GOT-OCR2's chat() calls .startswith() on whatever it is given,
    # so an in-memory image raises
    #     'Image' object has no attribute 'startswith'
    # after a full model load. A path is what it actually wants.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        handle.write(pixmap.tobytes("png"))
        rendered = handle.name

    try:
        return ocr_engine.ocr_image(rendered, mode="format")
    finally:
        Path(rendered).unlink(missing_ok=True)


def is_legacy_font_text(text: str, book: Textbook) -> bool:
    """
    Whether a Devanagari-medium book's text came out as legacy font bytes.

    Only applies to Hindi books: an English chapter is legitimately all Latin.
    Short samples are treated as fine, because a page of nothing but a diagram
    caption and a page number would otherwise be condemned on no evidence.
    """
    if book.medium != "Hindi":
        return False

    devanagari = len(_DEVANAGARI.findall(text))
    latin = len(_LATIN_LETTER.findall(text))
    letters = devanagari + latin
    if letters < LEGACY_FONT_MIN_LETTERS:
        return False

    return devanagari / letters < LEGACY_FONT_MAX_DEVANAGARI


def extract_chapters(
    zip_path: Path, book: Textbook, ocr_engine=None
) -> list[Chapter]:
    """
    Pull text from every chapter PDF inside a book zip.

    Front and back matter are skipped: their filenames carry letters where the
    chapter number would be, so the pattern simply does not match them.

    Args:
        ocr_engine: Optional OCR engine. When given, pages whose text layer is
            untrustworthy are re-read from a rendered image instead. Without
            it, those pages fall back to their embedded text, which for
            mathematics means dropped operators.
    """
    import fitz  # PyMuPDF

    chapters: list[Chapter] = []

    with zipfile.ZipFile(zip_path) as archive:
        for name in sorted(archive.namelist()):
            match = _CHAPTER_FILE.search(name)
            if not match:
                continue

            number = int(match.group(2))
            payload = archive.read(name)

            try:
                with fitz.open(stream=io.BytesIO(payload), filetype="pdf") as document:
                    page_texts = []
                    ocr_pages = 0

                    for page in document:
                        embedded = page.get_text()

                        if ocr_engine is not None and page_needs_ocr(page, embedded):
                            try:
                                recovered = ocr_page(page, ocr_engine)
                                # Only prefer OCR if it actually read something;
                                # a failed pass returning a fragment would lose
                                # the text we already had.
                                if recovered and len(recovered.strip()) >= len(
                                    embedded.strip()
                                ) // 2:
                                    page_texts.append(recovered)
                                    ocr_pages += 1
                                    continue
                            except Exception as exc:  # noqa: BLE001
                                logger.warning(
                                    "%s chapter %s: OCR failed on a page (%s)",
                                    book.code, number, exc,
                                )

                        page_texts.append(embedded)

                    raw = "\n".join(page_texts)
                    page_count = document.page_count

                    if ocr_pages:
                        logger.info(
                            "%s chapter %s: %s/%s pages re-read with OCR",
                            book.code, number, ocr_pages, page_count,
                        )
            except Exception as exc:  # noqa: BLE001 - one bad PDF must not stop a book
                logger.warning("%s chapter %s: unreadable PDF (%s)", book.code, number, exc)
                continue

            cleaned = clean_pdf_text(raw)

            if is_legacy_font_text(cleaned, book):
                logger.warning(
                    "%s chapter %s: legacy Devanagari font, text extracted as "
                    "Latin bytes -- skipping rather than storing gibberish",
                    book.code, number,
                )
                continue

            if len(cleaned) < MIN_CHUNK_CHARS:
                logger.debug(
                    "%s chapter %s: %s chars, likely scanned images — skipping",
                    book.code, number, len(cleaned),
                )
                continue

            chapters.append(Chapter(number=number, text=cleaned, page_count=page_count))

    return chapters


# ==================== CHUNK ====================


def chunk_text(
    text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP
) -> Iterator[str]:
    """
    Split text into overlapping windows, preferring paragraph then sentence ends.

    Cutting mid-sentence produces chunks that read as broken to a student and
    embed poorly, so each window is trimmed back to the last paragraph break,
    and failing that the last sentence end, within the final quarter.
    """
    if size <= overlap:
        raise ValueError("chunk size must exceed overlap")

    text = text.strip()
    if not text:
        return

    start = 0
    while start < len(text):
        end = min(start + size, len(text))

        if end < len(text):
            window_floor = start + (size * 3) // 4
            breakpoint = text.rfind("\n\n", window_floor, end)
            if breakpoint == -1:
                for terminator in (". ", "? ", "! ", "। "):
                    found = text.rfind(terminator, window_floor, end)
                    breakpoint = max(breakpoint, found + len(terminator) - 1)
            if breakpoint > window_floor:
                end = breakpoint

        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK_CHARS:
            yield chunk

        if end >= len(text):
            break
        start = max(start + 1, end - overlap)


# ==================== STORE ====================


def _book_already_ingested(db: Session, book: Textbook) -> bool:
    """Whether any chapter of this book is already stored."""
    found = db.execute(
        sql_text(
            "SELECT 1 FROM processed_content"
            " WHERE metadata ->> 'book_code' = :code LIMIT 1"
        ),
        {"code": book.code},
    ).first()
    return found is not None


def store_chapter(
    db: Session,
    book: Textbook,
    chapter: Chapter,
    embedder,
) -> int:
    """
    Write one chapter, its chunks, and their embeddings.

    Returns:
        Number of chunks stored.
    """
    from ...models.rag import Embedding

    chunks = list(chunk_text(chapter.text))
    if not chunks:
        return 0

    vectors = embedder.encode_documents_chunked(chunks, chunk_size=32)

    content_id = uuid.uuid4()
    db.execute(
        sql_text(
            """
            INSERT INTO processed_content
                (id, original_text, language, grade_level, subject, metadata)
            VALUES (:id, :text, :lang, :grade, :subject, CAST(:meta AS jsonb))
            """
        ),
        {
            "id": content_id,
            "text": chapter.text,
            "lang": LANGUAGE_CODES.get(book.medium, "en"),
            "grade": book.grade,
            "subject": book.title,
            "meta": _json(
                {
                    "source": "NCERT",
                    "book_code": book.code,
                    "book_title": book.title,
                    "medium": book.medium,
                    "chapter": chapter.number,
                    "pages": chapter.page_count,
                    "url": book.chapter_url(chapter.number),
                }
            ),
        },
    )

    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        chunk_id = uuid.uuid4()
        db.execute(
            sql_text(
                """
                INSERT INTO document_chunks
                    (id, content_id, chunk_index, chunk_text, chunk_size, chunk_metadata)
                VALUES (:id, :cid, :idx, :text, :size, CAST(:meta AS jsonb))
                """
            ),
            {
                "id": chunk_id,
                "cid": content_id,
                "idx": index,
                "text": chunk,
                "size": len(chunk),
                "meta": _json(
                    {
                        "grade": book.grade,
                        "subject": book.title,
                        "medium": book.medium,
                        "book_code": book.code,
                        "chapter": chapter.number,
                    }
                ),
            },
        )
        db.add(
            Embedding(
                id=uuid.uuid4(),
                chunk_id=chunk_id,
                content_id=content_id,
                embedding=list(map(float, vector)),
                embedding_model=settings.EMBEDDING_MODEL_ID,
            )
        )

    return len(chunks)


def _json(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)


# ==================== ORCHESTRATION ====================


def ingest_book(
    db: Session,
    book: Textbook,
    embedder,
    download_dir: Path = DOWNLOAD_DIR,
    client: httpx.Client | None = None,
    force: bool = False,
    ocr_engine=None,
    discard_download: bool = False,
    zip_path: Path | None = None,
) -> tuple[int, int]:
    """
    Ingest one textbook end to end.

    Args:
        zip_path: An already-downloaded archive. Passed by ingest_books, which
            fetches the next book while the current one is being embedded.

    Returns:
        (chapters stored, chunks stored). (0, 0) means skipped or unavailable.
    """
    if not force and _book_already_ingested(db, book):
        logger.info("%s: already in database, skipping", book.code)
        return 0, 0

    if zip_path is None:
        zip_path = download_book(book, download_dir=download_dir, client=client)
    if zip_path is None:
        return 0, 0

    chapters = extract_chapters(zip_path, book, ocr_engine=ocr_engine)
    if not chapters:
        logger.warning("%s: no readable chapters", book.code)
        return 0, 0

    total_chunks = 0
    for chapter in chapters:
        total_chunks += store_chapter(db, book, chapter, embedder)

    db.commit()

    # Only after the commit: the zip is the resume point, so it must outlive
    # any chance of the transaction failing. The full catalog is 15-25 GB of
    # archives, which will not fit on most machines alongside the model cache.
    if discard_download:
        zip_path.unlink(missing_ok=True)

    logger.info(
        "%s (class %s %s, %s): %s chapters, %s chunks",
        book.code, book.grade, book.medium, book.title, len(chapters), total_chunks,
    )
    return len(chapters), total_chunks


def record_dead_end(book: Textbook, download_dir: Path, reason: str) -> None:
    """
    Mark a book that cannot be ingested, so a batched run stops retrying it.

    A book is committed in one transaction, so a failure rolls back completely
    and the book never appears in the database. The batched runner selects
    whatever is not yet in the database, which means anything that reliably
    fails is reliably reselected -- an unbounded retry loop. One overnight run
    spent 1,178 batches to ingest 16 books because class 5 Rimjhim has a corrupt
    archive (`Bad CRC-32 for ehhn105.pdf`) and was chosen again every time, in
    company with legacy-font Hindi books that are correctly rejected chapter by
    chapter and therefore also never land.

    404s already had a marker; these two outcomes did not. The reason is written
    into the file so the set of dead ends stays auditable, and deleting the file
    is all it takes to retry a book once its cause is fixed.
    """
    marker = download_dir / f"{book.code}.unavailable"
    if marker.exists():
        return

    download_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"{book.code}\t{book.title}\t{reason}\n", encoding="utf-8")
    logger.warning("%s marked as a dead end: %s", book.code, reason)


def ingest_books(
    db: Session,
    books: list[Textbook],
    embedder,
    download_dir: Path = DOWNLOAD_DIR,
    force: bool = False,
    on_progress=None,
    ocr_engine=None,
    discard_downloads: bool = False,
) -> IngestStats:
    """
    Ingest a list of textbooks, continuing past individual failures.

    A single unreachable book or malformed PDF must not end a run that may take
    hours, so failures are counted and logged rather than raised.

    The next book is downloaded while the current one is being embedded. Those
    are the two dominant costs and they use different resources — one waits on
    a slow government web server, the other saturates the GPU — so running them
    in sequence left each idle for the other. Measured at 97 seconds a book
    before overlapping, against a catalog of 558.
    """
    stats = IngestStats()

    with httpx.Client(
        timeout=DOWNLOAD_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client, ThreadPoolExecutor(max_workers=1, thread_name_prefix="prefetch") as pool:

        def start_download(index: int):
            """Begin fetching books[index], if there is one."""
            if index >= len(books) or not PREFETCH_ENABLED:
                return None
            # A separate client per prefetch: httpx.Client is thread-safe, but
            # the download runs while the main thread may also be using one,
            # and an isolated connection pool keeps the two from interfering.
            return pool.submit(download_book, books[index], download_dir, None)

        pending = start_download(0)

        for position, book in enumerate(books, 1):
            try:
                # Whatever the prefetcher fetched for this book. A failed
                # download surfaces here rather than in the worker thread.
                zip_path = pending.result() if pending is not None else None
            except Exception as exc:  # noqa: BLE001
                logger.error("%s: prefetch failed: %s", book.code, exc)
                zip_path = None

            # Start the next download now, so it runs during this book's
            # extraction and embedding rather than after them.
            pending = start_download(position)

            try:
                chapters, chunks = ingest_book(
                    db, book, embedder, download_dir, client, force, ocr_engine,
                    discard_downloads, zip_path,
                )
                if chapters:
                    stats.books_done += 1
                    stats.chapters += chapters
                    stats.chunks += chunks
                else:
                    stats.books_skipped += 1
                    record_dead_end(book, download_dir, "yielded no usable chapters")
            except Exception as exc:  # noqa: BLE001 - a long run must not die on one book
                db.rollback()
                stats.books_failed += 1
                logger.error("%s: ingestion failed: %s", book.code, exc)
                record_dead_end(book, download_dir, f"{type(exc).__name__}: {exc}")

            if on_progress:
                on_progress(position, len(books), book, stats)

    return stats
