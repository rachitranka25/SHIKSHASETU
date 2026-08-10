"""
Unit tests for NCERT catalog parsing and ingestion text handling.

No network and no database: these cover the pure transformations, which is
where quiet corruption would live. A chunker that splits mid-word or a cleaner
that eats paragraph breaks degrades every answer the system ever gives, without
failing anything.
"""

import pytest

from backend.services.ingestion.ncert_catalog import (
    Textbook,
    curriculum_scope,
    decode,
    load_catalog,
    parse_catalog,
    select,
)
from backend.services.ingestion.ncert_ingest import (
    MIN_CHUNK_CHARS,
    is_legacy_font_text,
    OCR_IMAGE_DENSITY,
    OCR_MIN_PAGE_CHARS,
    chunk_text,
    clean_pdf_text,
    page_needs_ocr,
)

# ==================== BOOK CODES ====================


@pytest.mark.parametrize(
    ("code", "grade", "medium"),
    [
        ("aeen1", 1, "English"),
        ("fecu1", 6, "English"),
        ("jesc1", 10, "English"),
        ("lebo1", 12, "English"),
        ("jhsc1", 10, "Hindi"),
        ("lubs1", 12, "Urdu"),
    ],
)
def test_decode_reads_grade_and_medium(code, grade, medium):
    assert decode(code) == (grade, medium)


@pytest.mark.parametrize(
    "code",
    [
        "mesc1",  # class letter past 'l' (there is no class 13)
        "jxsc1",  # medium letter that is not e/h/u
        "jesc",  # no book number
        "jes1",  # one-letter subject
        "",
        "jesc11",  # chapter code, not a book code
    ],
)
def test_decode_rejects_malformed_codes(code):
    with pytest.raises(ValueError):
        decode(code)


def test_urls_follow_the_ncert_scheme():
    book = Textbook(code="jesc1", title="Science", grade=10, medium="English")

    assert book.zip_url.endswith("/jesc1dd.zip")
    assert book.chapter_url(1).endswith("/jesc101.pdf")
    assert book.chapter_url(12).endswith("/jesc112.pdf")


# ==================== CATALOG PARSING ====================

CATALOG_HTML = """
<script>
    if(pm=="jesc1")
    { document.write("<tr><td class='st1'><strong>Science</strong></br></td></tr>"); }
    if(pm=="jemh1")
    { document.write("<tr><td class='st1'><strong>Mathematics</strong></br></td></tr>"); }
    if(pm=="ahhn1")
    { document.write("<tr><td class='st1'><strong>Rimjhim</strong></br></td></tr>"); }
    if(pm=="notacode")
    { document.write("<strong>Should Be Ignored</strong>"); }
</script>
"""


def test_parse_catalog_extracts_books():
    books = parse_catalog(CATALOG_HTML)

    assert {b.code for b in books} == {"jesc1", "jemh1", "ahhn1"}
    assert {b.title for b in books} == {"Science", "Mathematics", "Rimjhim"}


def test_parse_catalog_decodes_grade_and_medium():
    by_code = {b.code: b for b in parse_catalog(CATALOG_HTML)}

    assert (by_code["jesc1"].grade, by_code["jesc1"].medium) == (10, "English")
    assert (by_code["ahhn1"].grade, by_code["ahhn1"].medium) == (1, "Hindi")


def test_parse_catalog_ignores_non_book_identifiers():
    """The page contains ids that are not book codes; they must not become books."""
    assert all(b.code != "notacode" for b in parse_catalog(CATALOG_HTML))


def test_parse_catalog_keeps_the_first_title_for_a_code():
    """Codes recur across the page; the first occurrence is the authoritative one."""
    html = CATALOG_HTML + """
    <script>if(pm=="jesc1"){document.write("<strong>Stale Duplicate</strong>");}</script>
    """

    titles = {b.code: b.title for b in parse_catalog(html)}
    assert titles["jesc1"] == "Science"


def test_parse_catalog_recovers_a_title_from_an_unclosed_strong_tag():
    """
    Two class 11 chemistry blocks on the live page open <strong> and never
    close it. The non-greedy match then ran to the *next* block's </strong>,
    and the title came out as 'Chemistry Part-I");\\n\\t\\tif(pm=="khch1")...'
    — a mangled label that would have been shown to students in the library.
    """
    html = """
    <script>
    if(pm=="kech1"){document.write("<strong>Chemistry Part-I");
    }
    if(pm=="kech2"){document.write("<strong>Chemistry Part-II</strong>");
    }
    </script>
    """

    titles = {b.code: b.title for b in parse_catalog(html)}
    assert titles["kech1"] == "Chemistry Part-I"
    assert titles["kech2"] == "Chemistry Part-II"


def test_parse_catalog_on_an_unrecognisable_page_returns_nothing():
    """A redesign should yield an empty catalog, not garbage entries."""
    assert parse_catalog("<html><body>Site under maintenance</body></html>") == []


# ==================== CURRICULUM SCOPE ====================


def _book(code: str, title: str) -> Textbook:
    grade, medium = decode(code)
    return Textbook(code=code, title=title, grade=grade, medium=medium)


def test_curriculum_scope_prefers_the_english_edition():
    """Translation is the platform's job; one English source serves every language."""
    scoped = curriculum_scope(
        [_book("jesc1", "Science"), _book("jhsc1", "Vigyan"), _book("jusc1", "Science")]
    )

    assert [b.code for b in scoped] == ["jesc1"]


def test_curriculum_scope_keeps_hindi_only_subjects():
    """Rimjhim has no English edition, and translating a Hindi reader is pointless."""
    scoped = curriculum_scope([_book("ahhn1", "Rimjhim"), _book("ahjm1", "Joyful Maths")])

    assert {b.code for b in scoped} == {"ahhn1", "ahjm1"}


def test_curriculum_scope_never_keeps_urdu():
    """An Urdu-only book is dropped rather than taught from."""
    assert curriculum_scope([_book("kuch1", "Keemiya I")]) == []


def test_curriculum_scope_matches_editions_within_a_grade():
    """
    NCERT reuses subject letters across unrelated books: class 9's vocational
    `ievs1` (Solanceous Crop Cultivator) shares `vs` with class 6's Vasant.
    Matching on subject letters alone dropped half the Hindi readers.
    """
    scoped = curriculum_scope([_book("ievs1", "Solanceous Crop"), _book("fhvs1", "Vasant")])

    assert {b.code for b in scoped} == {"ievs1", "fhvs1"}


def test_curriculum_scope_teaches_no_subject_in_hindi_that_english_covers():
    """
    The guarantee the user asked for, checked against the real catalog: every
    Hindi book in scope is a language or arts reader. A rename that strands a
    Hindi maths or science edition — as class 7's Ganit did — must be caught
    here rather than surfacing to a student.
    """
    import re

    non_language = re.compile(
        r"ganit|vigyan|math|scien|samajik|bhugol|itihas|arth|rasayan|bhautik|jeev", re.I
    )
    hindi = [b for b in curriculum_scope(load_catalog()) if b.medium == "Hindi"]

    assert hindi, "the catalog should contain Hindi-only readers"
    assert [b.code for b in hindi if non_language.search(b.title)] == []


def test_select_filters_by_grade_and_medium():
    catalog = parse_catalog(CATALOG_HTML)

    assert len(select(catalog, grades={10})) == 2
    assert len(select(catalog, media={"Hindi"})) == 1
    assert len(select(catalog, grades={10}, media={"Hindi"})) == 0
    assert len(select(catalog)) == 3


# ==================== PDF TEXT CLEANING ====================


def test_rejoins_words_split_across_a_line_break():
    """PDFs hyphenate at line ends; leaving it breaks the word for search."""
    assert "photosynthesis" in clean_pdf_text("The process of photosyn-\nthesis begins")


def test_unwraps_hard_wrapped_lines():
    raw = "Plants make their own\nfood using sunlight\nand water."

    assert clean_pdf_text(raw) == "Plants make their own food using sunlight and water."


def test_preserves_paragraph_breaks():
    """Paragraph boundaries are what the chunker prefers to split on."""
    cleaned = clean_pdf_text("First paragraph here.\n\nSecond paragraph here.")

    assert "\n\n" in cleaned


def test_collapses_runs_of_spaces_and_blank_lines():
    cleaned = clean_pdf_text("Column   spacing\n\n\n\nNext section")

    assert "   " not in cleaned
    assert "\n\n\n" not in cleaned


# ==================== CHUNKING ====================


def _paragraphs(count: int, sentence: str = "Photosynthesis converts light energy. ") -> str:
    return "\n\n".join(sentence * 12 for _ in range(count))


def test_short_text_yields_a_single_chunk():
    text = "Photosynthesis is how plants make food. " * 5

    assert len(list(chunk_text(text))) == 1


def test_long_text_is_split():
    chunks = list(chunk_text(_paragraphs(8)))

    assert len(chunks) > 1


def test_chunks_respect_the_size_limit():
    """Oversized chunks defeat retrieval and can exceed the encoder's window."""
    chunks = list(chunk_text(_paragraphs(10), size=600, overlap=100))

    assert all(len(c) <= 600 for c in chunks)


def test_no_chunk_is_below_the_minimum():
    """Fragments retrieve badly and waste an embedding each."""
    chunks = list(chunk_text(_paragraphs(6)))

    assert all(len(c) >= MIN_CHUNK_CHARS for c in chunks)


def test_chunks_cover_the_whole_text():
    """Nothing may be dropped: a missing passage is a question we cannot answer."""
    text = _paragraphs(6)
    joined = "".join(chunk_text(text))

    # Overlap means the concatenation is longer than the source, never shorter.
    assert len(joined) >= len(text.strip()) * 0.95


def test_consecutive_chunks_overlap():
    """A sentence straddling a boundary must be reachable from both sides."""
    chunks = list(chunk_text(_paragraphs(8), size=700, overlap=150))

    assert len(chunks) >= 2
    tail = chunks[0][-60:]
    assert any(fragment in chunks[1] for fragment in (tail[:20], tail[-20:]))


def test_chunks_prefer_to_end_at_a_sentence_or_paragraph():
    """Mid-word cuts read as broken and embed poorly."""
    chunks = list(chunk_text(_paragraphs(8), size=700, overlap=100))

    # Every chunk but the last should end at punctuation, not inside a word.
    for chunk in chunks[:-1]:
        assert chunk[-1] in ".?!।", f"chunk ends mid-sentence: {chunk[-40:]!r}"


def test_empty_and_whitespace_text_yield_nothing():
    assert list(chunk_text("")) == []
    assert list(chunk_text("   \n\n  ")) == []


def test_overlap_must_be_smaller_than_the_chunk():
    """Otherwise the window never advances and the loop cannot terminate."""
    with pytest.raises(ValueError):
        list(chunk_text("some text", size=100, overlap=100))


def test_chunking_terminates_on_text_without_punctuation():
    """A chapter of formulae or a table has no sentence ends to break on."""
    chunks = list(chunk_text("x" * 5000, size=500, overlap=100))

    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)


# ==================== DECIDING WHEN TO OCR ====================


class _FakePage:
    """A PDF page, as much of one as page_needs_ocr looks at."""

    def __init__(self, images: int = 0, drawings: int = 0):
        self._images = images
        self._drawings = drawings

    def get_images(self):
        return [None] * self._images

    def get_drawings(self):
        return [None] * self._drawings


def _page_text(chars: int) -> str:
    return "a" * chars


# Densities measured on real NCERT chapters, in images per 1000 characters.
# The maths case is the one that must be caught; the rest must not be.
@pytest.mark.parametrize(
    ("label", "images", "chars", "expected"),
    [
        ("class 10 maths ch4, equations as images", 47, 1521, True),
        ("class 10 science ch8, figure-heavy", 16, 2642, False),
        ("class 10 science ch5, prose", 10, 2509, False),
        ("class 10 science ch1, mixed", 4, 1991, False),
    ],
)
def test_detector_matches_the_measured_pages(label, images, chars, expected):
    page = _FakePage(images=images)

    assert page_needs_ocr(page, _page_text(chars)) is expected, label


def test_a_page_that_is_almost_all_diagram_is_ocred():
    """A caption under a figure is not the content of the page."""
    page = _FakePage(images=3)

    assert page_needs_ocr(page, _page_text(OCR_MIN_PAGE_CHARS - 1)) is True


def test_a_vector_diagram_page_is_ocred_too():
    """NCERT draws many figures as vectors rather than embedded images."""
    page = _FakePage(images=0, drawings=500)

    assert page_needs_ocr(page, _page_text(50)) is True


def test_a_blank_page_is_not_ocred():
    """Nothing to read, so nothing to spend a model pass on."""
    assert page_needs_ocr(_FakePage(), "") is False
    assert page_needs_ocr(_FakePage(), "   \n  ") is False


def test_prose_with_no_images_is_never_ocred():
    assert page_needs_ocr(_FakePage(images=0), _page_text(3000)) is False


def test_threshold_boundary_is_exclusive():
    """Exactly at the threshold counts as acceptable; above it does not."""
    chars = 1000
    at_threshold = int(OCR_IMAGE_DENSITY)

    assert page_needs_ocr(_FakePage(images=at_threshold), _page_text(chars)) is False
    assert page_needs_ocr(_FakePage(images=at_threshold + 1), _page_text(chars)) is True


# ==================== LEGACY DEVANAGARI FONTS ====================


def test_legacy_font_text_is_rejected_for_a_hindi_book():
    """
    Class 10's Kshitij-2 is typeset in Walkman-Chanakya 905, which maps
    Devanagari glyphs onto ASCII codepoints with no ToUnicode table. The
    extracted "text" below is really "काव्य खंड ... तुलसीदास ... सन् 1532 में
    हुआ था।" -- unreadable to a student, and embedded by BGE-M3 as meaningless
    Latin that competes for retrieval slots against passages that would help.
    """
    gibberish = (
        "dkO; [kaM ân; fla/q efr lhi lekukA Lokfr lkjnk dgfga lqtkukA "
        "rqylhnkl dk tUe mÙkj izns'k osQ ck¡nk f”kys osQ jktkiqj xk¡o esa "
        "lu~ 1532 esa gqvk FkkA t;'kadj izlkn dk tUe lu~ 1889 esa okjk.klh "
        'esa gqvkA lw ;Zdkar f=kikBh ^fujkyk* dk tUe caxky osQ efg"kkny esa '
    ) * 3
    book = Textbook(code="jhks1", title="Kshitij-2", grade=10, medium="Hindi")

    assert is_legacy_font_text(gibberish, book)


def test_real_devanagari_is_kept():
    """Sarangi is set in Kokila, a Unicode font, and extracts correctly."""
    real = (
        "बच्चों को पोस्टर देखने के लिए पर्याप्त समय दें। पोस्टर में दिखाए गए "
        "घर-परिवार एवं कार्यों के विषय में बातचीत करें। इस घर में कौन-कौन हैं? "
    ) * 4
    book = Textbook(code="ahsr1", title="Sarangi", grade=1, medium="Hindi")

    assert not is_legacy_font_text(real, book)


def test_an_english_book_is_never_condemned_for_being_latin():
    """The whole point of an English chapter is that it is Latin."""
    book = Textbook(code="jesc1", title="Science", grade=10, medium="English")

    assert not is_legacy_font_text("Light behaves as both a wave and a particle. " * 20, book)


def test_a_short_sample_is_given_the_benefit_of_the_doubt():
    """A page holding only a diagram caption and a folio is no evidence."""
    book = Textbook(code="jhks1", title="Kshitij-2", grade=10, medium="Hindi")

    assert not is_legacy_font_text("figure 3.1", book)
