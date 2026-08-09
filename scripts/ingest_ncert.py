#!/usr/bin/env python3
"""
Ingest NCERT textbooks into the RAG store.

    # Refresh the book catalog from ncert.nic.in (cached in data/)
    python scripts/ingest_ncert.py --refresh-catalog

    # See what would run, without downloading anything
    python scripts/ingest_ncert.py --grades 10 --medium English --dry-run

    # One book, to check quality before committing to a long run
    python scripts/ingest_ncert.py --codes jesc1

    # Everything: 558 books across classes 1-12 in English, Hindi and Urdu
    python scripts/ingest_ncert.py --all

Safe to interrupt. Downloaded zips are reused and books already in the database
are skipped, so re-running resumes rather than restarting.

Migrations must be at head first — embeddings.embedding has to be a pgvector
column, not a float array. See migration 019.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.config import settings  # noqa: E402
from backend.services.ingestion import (  # noqa: E402
    fetch_catalog,
    load_catalog,
    save_catalog,
    select,
)
from backend.services.ingestion.ncert_ingest import ingest_books  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh-catalog", action="store_true", help="Re-scrape the book list from NCERT and exit")
    parser.add_argument("--all", action="store_true", help="Every book in the catalog")
    parser.add_argument("--grades", type=int, nargs="+", help="Class numbers, e.g. --grades 6 7 8")
    parser.add_argument("--medium", nargs="+", choices=["English", "Hindi", "Urdu"], help="Languages to ingest")
    parser.add_argument("--codes", nargs="+", help="Specific book codes, e.g. jesc1")
    parser.add_argument("--limit", type=int, help="Stop after this many books")
    parser.add_argument("--force", action="store_true", help="Re-ingest books already in the database")
    parser.add_argument("--dry-run", action="store_true", help="List the selection and exit")
    parser.add_argument(
        "--ocr",
        action="store_true",
        help=(
            "Re-read untrustworthy pages with GOT-OCR2. NCERT sets equations as "
            "images and the PDF text layer drops the glyphs: 'a != 0' arrives as "
            "'a  0', and superscripts flatten. Only pages that look affected are "
            "sent through OCR, but those pages become much slower. Strongly "
            "recommended for mathematics; unnecessary for prose."
        ),
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("INGEST_DATABASE_URL"),
        help=(
            "Connection to write with. Defaults to $INGEST_DATABASE_URL, then "
            "settings.DATABASE_URL. Shared curriculum is stored with no "
            "organization, and row-level security only lets the table owner "
            "create such rows, so this normally needs the owner connection "
            "(the same one migrations use), not the least-privilege app role."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.refresh_catalog:
        books = fetch_catalog()
        save_catalog(books)
        print(f"Catalog refreshed: {len(books)} textbooks")
        return 0

    catalog = load_catalog()

    if args.codes:
        wanted = set(args.codes)
        books = [b for b in catalog if b.code in wanted]
        missing = wanted - {b.code for b in books}
        if missing:
            logger.error("Unknown book codes: %s", ", ".join(sorted(missing)))
            return 1
    elif args.all:
        books = catalog
    elif args.grades or args.medium:
        books = select(
            catalog,
            grades=set(args.grades) if args.grades else None,
            media=set(args.medium) if args.medium else None,
        )
    else:
        logger.error("Choose a selection: --all, --grades, --medium, or --codes")
        return 1

    if args.limit:
        books = books[: args.limit]

    if not books:
        logger.error("Selection matched no books")
        return 1

    print(f"{len(books)} textbooks selected")
    if args.dry_run:
        for b in books:
            print(f"  {b.code}  class {b.grade:>2}  {b.medium:8}  {b.title}")
        return 0

    # Loaded once and reused: BGE-M3 takes a while to come up and holds
    # meaningful memory, so a per-book load would dominate the run.
    logger.info("Loading %s ...", settings.EMBEDDING_MODEL_ID)
    from backend.services.rag import BGEM3Embedder

    embedder = BGEM3Embedder()

    ocr_engine = None
    if args.ocr:
        logger.info("Loading OCR engine (%s) ...", settings.OCR_MODEL_ID)
        from backend.services.ocr import get_ocr_service

        ocr_engine = get_ocr_service().ocr

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine(args.database_url or settings.DATABASE_URL)
    started = time.perf_counter()

    def report(position: int, total: int, book, stats) -> None:
        elapsed = time.perf_counter() - started
        rate = position / elapsed if elapsed else 0
        remaining = (total - position) / rate if rate else 0
        logger.info(
            "[%s/%s] %s — %s chunks so far, ~%.0f min left",
            position, total, book.code, stats.chunks, remaining / 60,
        )

    with Session(engine) as db:
        stats = ingest_books(
            db, books, embedder, force=args.force, on_progress=report,
            ocr_engine=ocr_engine,
        )

    print()
    print(stats)
    print(f"took {(time.perf_counter() - started) / 60:.1f} minutes")
    return 0 if stats.books_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
