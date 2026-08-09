"""
NCERT Textbook Catalog
======================

Which books exist, what they are called, and where their PDFs live.

NCERT encodes every textbook as a five-character code — `jesc1` is Class 10,
English medium, Science, book 1 — and serves it at predictable URLs:

    https://ncert.nic.in/textbook/pdf/jesc1dd.zip   whole book
    https://ncert.nic.in/textbook/pdf/jesc101.pdf   chapter 1

The subject letters are not guessable. Science is `sc` for classes 7-10, but
Class 6 science is `cu` (Curiosity) and Class 12 splits into `ph`, `ch`, `bo`.
Nor is the set stable — NCERT renames and replaces books between syllabus
revisions. So the catalog is scraped from NCERT's own textbook picker, which is
the authoritative list, and cached to disk. Ingestion reads the cache, so a
download run does not depend on their site being reachable.

The picker is a JavaScript page that writes titles through a chain of

    if(pm=="jesc1") { document.write("...<strong>Science</strong>...") }

blocks. Ugly to parse, but it is the mapping, and there is no API.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CATALOG_URL = "https://ncert.nic.in/textbook.php"
PDF_BASE = "https://ncert.nic.in/textbook/pdf"

# Shipped with the repo so ingestion works offline and runs are reproducible.
CATALOG_PATH = Path(__file__).resolve().parents[3] / "data" / "ncert_catalog.json"

# Book codes are exactly: class letter, medium letter, two subject letters, book
# number. Anything looser matches unrelated identifiers elsewhere in the page.
BOOK_CODE = re.compile(r"^[a-l][ehu][a-z]{2}\d$")

_TITLE_BLOCK = re.compile(
    r'pm==\"([a-l][ehu][a-z]{2}\d)\"\s*\)\s*\{.*?<strong>(.*?)</strong>', re.S
)
_TAGS = re.compile(r"<[^>]+>")

MEDIUM_NAMES = {"e": "English", "h": "Hindi", "u": "Urdu"}

# NCERT's server resets connections under load; it is a government site serving
# large PDFs, not a CDN. Identify honestly and retry rather than hammering.
USER_AGENT = "ShikshaSetu-ingest/1.0 (educational content ingestion)"


@dataclass(frozen=True)
class Textbook:
    """One NCERT textbook."""

    code: str
    title: str
    grade: int
    medium: str

    @property
    def zip_url(self) -> str:
        """Whole book as a zip of per-chapter PDFs."""
        return f"{PDF_BASE}/{self.code}dd.zip"

    def chapter_url(self, chapter: int) -> str:
        """A single chapter PDF. Chapters are zero-padded to two digits."""
        return f"{PDF_BASE}/{self.code}{chapter:02d}.pdf"


def decode(code: str) -> tuple[int, str]:
    """
    Split a book code into its grade and medium.

    >>> decode("jesc1")
    (10, 'English')

    Raises:
        ValueError: If the code is not a valid NCERT book code.
    """
    if not BOOK_CODE.match(code):
        raise ValueError(f"not an NCERT book code: {code!r}")

    grade = ord(code[0]) - ord("a") + 1
    return grade, MEDIUM_NAMES[code[1]]


def parse_catalog(html: str) -> list[Textbook]:
    """
    Pull every textbook out of the picker page.

    Titles repeat across the page; the first occurrence wins, which is the one
    in the class's own block.
    """
    seen: dict[str, str] = {}

    for code, raw_title in _TITLE_BLOCK.findall(html):
        title = _TAGS.sub("", raw_title).strip()
        if title and code not in seen:
            seen[code] = title

    books = []
    for code, title in seen.items():
        grade, medium = decode(code)
        books.append(Textbook(code=code, title=title, grade=grade, medium=medium))

    return sorted(books, key=lambda b: (b.grade, b.medium, b.code))


def fetch_catalog(timeout: float = 30.0, attempts: int = 4) -> list[Textbook]:
    """
    Download and parse the catalog from NCERT.

    Raises:
        httpx.HTTPError: If the page cannot be fetched after `attempts` tries.
    """
    import time

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    last: Exception | None = None

    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for attempt in range(1, attempts + 1):
            try:
                response = client.get(CATALOG_URL)
                response.raise_for_status()
                return parse_catalog(response.text)
            except httpx.HTTPError as exc:
                last = exc
                logger.warning(
                    "NCERT catalog fetch attempt %s/%s failed: %s", attempt, attempts, exc
                )
                if attempt < attempts:
                    time.sleep(2.0 * attempt)

    raise last  # type: ignore[misc]


def save_catalog(books: list[Textbook], path: Path = CATALOG_PATH) -> None:
    """Write the catalog to disk, sorted, so diffs between refreshes are readable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": CATALOG_URL,
        "count": len(books),
        "books": [asdict(b) for b in books],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote %s textbooks to %s", len(books), path)


def load_catalog(path: Path = CATALOG_PATH) -> list[Textbook]:
    """
    Read the cached catalog.

    Raises:
        FileNotFoundError: With the command needed to create it.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"No NCERT catalog at {path}. Build it with:\n"
            "    python -m scripts.ingest_ncert --refresh-catalog"
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Textbook(**entry) for entry in payload["books"]]


def select(
    books: list[Textbook],
    grades: set[int] | None = None,
    media: set[str] | None = None,
) -> list[Textbook]:
    """Filter a catalog by grade and medium. None means no restriction."""
    return [
        b
        for b in books
        if (grades is None or b.grade in grades) and (media is None or b.medium in media)
    ]
