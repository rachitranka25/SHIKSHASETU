"""
Content ingestion.

Fetches curriculum material from its publisher, extracts text, chunks it, and
stores it with embeddings so the RAG layer has something to retrieve. The
database ships empty; this is what fills it.
"""

from .ncert_catalog import (
    Textbook,
    curriculum_scope,
    decode,
    fetch_catalog,
    load_catalog,
    parse_catalog,
    save_catalog,
    select,
)

__all__ = [
    "Textbook",
    "curriculum_scope",
    "decode",
    "fetch_catalog",
    "load_catalog",
    "parse_catalog",
    "save_catalog",
    "select",
]
