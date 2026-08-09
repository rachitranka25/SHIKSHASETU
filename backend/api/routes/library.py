"""
Curriculum library endpoints.

The ingested NCERT corpus had no way in. Chapters, chunks and embeddings were
being written by scripts/ingest_ncert.py and nothing could read them back: no
route listed what was available, and no route searched it. The corpus existed
and was unreachable.

Two endpoints, both read-only:

    GET /api/v2/library          what is ingested, by class and subject
    GET /api/v2/library/search   semantic search across it

`/api/v2/library` is also the path the route optimization middleware already
caches for 300 seconds. That entry was written against the test suite's
specification while no such route existed, so it has been matching nothing.

Shared curriculum is stored with no organization, which row-level security
exposes to every caller for reading — the point being that NCERT belongs to no
single school. These endpoints therefore need no authentication, matching the
guest chat and guest speech-to-text routes.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ...database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# A query embedding costs a model call, so cap how much work one request can ask
# for and how much text it can hand back.
MAX_RESULTS = 50
DEFAULT_RESULTS = 10
SNIPPET_CHARS = 400


class BookSummary(BaseModel):
    """One ingested textbook."""

    book_code: str
    title: str
    grade: int
    medium: str
    chapters: int
    chunks: int


class LibraryResponse(BaseModel):
    """What the corpus currently holds."""

    books: list[BookSummary]
    total_books: int
    total_chapters: int
    total_chunks: int
    grades: list[int]
    subjects: list[str]


class SearchHit(BaseModel):
    """One retrieved passage."""

    text: str
    similarity: float = Field(description="Cosine similarity, 0 to 1")
    grade: int | None = None
    subject: str | None = None
    medium: str | None = None
    chapter: int | None = None
    book_code: str | None = None
    source_url: str | None = None


class SearchResponse(BaseModel):
    """Search results, with the query echoed for client-side caching."""

    query: str
    hits: list[SearchHit]
    count: int


@router.get("/library", response_model=LibraryResponse, tags=["library"])
async def list_library(db: Session = Depends(get_db)) -> LibraryResponse:
    """
    Summarise the ingested curriculum.

    Grouped by book rather than by chapter: a class 10 Science book is one
    entry with 13 chapters, not 13 entries.
    """
    rows = db.execute(
        sql_text(
            """
            SELECT
                pc.metadata ->> 'book_code'  AS book_code,
                pc.metadata ->> 'book_title' AS title,
                pc.grade_level               AS grade,
                pc.metadata ->> 'medium'     AS medium,
                count(DISTINCT pc.id)        AS chapters,
                count(dc.id)                 AS chunks
            FROM processed_content pc
            LEFT JOIN document_chunks dc ON dc.content_id = pc.id
            WHERE pc.metadata ->> 'source' = 'NCERT'
            GROUP BY 1, 2, 3, 4
            ORDER BY grade, title
            """
        )
    ).fetchall()

    books = [
        BookSummary(
            book_code=row.book_code,
            title=row.title or row.book_code,
            grade=row.grade,
            medium=row.medium or "English",
            chapters=row.chapters,
            chunks=row.chunks,
        )
        for row in rows
    ]

    return LibraryResponse(
        books=books,
        total_books=len(books),
        total_chapters=sum(b.chapters for b in books),
        total_chunks=sum(b.chunks for b in books),
        grades=sorted({b.grade for b in books}),
        subjects=sorted({b.title for b in books}),
    )


@router.get("/library/search", response_model=SearchResponse, tags=["library"])
async def search_library(
    q: str = Query(min_length=2, max_length=500, description="What to look for"),
    grade: int | None = Query(default=None, ge=1, le=12),
    subject: str | None = Query(default=None, max_length=120),
    medium: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=DEFAULT_RESULTS, ge=1, le=MAX_RESULTS),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Search the curriculum semantically.

    Meaning, not keywords, and cross-lingual: BGE-M3 embeds the query into the
    same space as the passages, so a question in Hindi or Marathi retrieves
    English chapters. Filters narrow the candidate set before the vector scan,
    which is what makes "explain this to a class 6 student" answerable from
    class 6 material rather than from wherever the wording happens to match.
    """
    # get_embedder(), not BGEM3Embedder(): the model is 2.5 GB and takes about
    # 20 seconds to load. Constructing one per request made the first version of
    # this endpoint answer in 19.2s.
    from ...services.rag import get_embedder

    try:
        vector = get_embedder().encode_query(q)
    except Exception as exc:
        logger.error("Query embedding failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Search is unavailable because the embedding model could not be loaded.",
        ) from exc

    filters = ["pc.metadata ->> 'source' = 'NCERT'"]
    params: dict = {
        "vector": "[" + ",".join(str(x) for x in vector.tolist()) + "]",
        "limit": limit,
        "snippet": SNIPPET_CHARS,
    }

    if grade is not None:
        filters.append("pc.grade_level = :grade")
        params["grade"] = grade
    if subject:
        filters.append("pc.subject ILIKE :subject")
        params["subject"] = f"%{subject}%"
    if medium:
        filters.append("pc.metadata ->> 'medium' = :medium")
        params["medium"] = medium

    where = " AND ".join(filters)

    # CAST(:vector AS vector), never :vector::vector — SQLAlchemy will not let a
    # bind parameter be followed by a colon and silently truncates the name.
    rows = db.execute(
        sql_text(
            f"""
            SELECT
                left(dc.chunk_text, :snippet)        AS snippet,
                1 - (e.embedding <=> CAST(:vector AS vector)) AS similarity,
                pc.grade_level                       AS grade,
                pc.subject                           AS subject,
                pc.metadata ->> 'medium'             AS medium,
                (pc.metadata ->> 'chapter')::int     AS chapter,
                pc.metadata ->> 'book_code'          AS book_code,
                pc.metadata ->> 'url'                AS source_url
            FROM embeddings e
            JOIN document_chunks dc   ON dc.id = e.chunk_id
            JOIN processed_content pc ON pc.id = dc.content_id
            WHERE {where}
            ORDER BY e.embedding <=> CAST(:vector AS vector)
            LIMIT :limit
            """
        ),
        params,
    ).fetchall()

    hits = [
        SearchHit(
            text=row.snippet,
            similarity=round(float(row.similarity), 4),
            grade=row.grade,
            subject=row.subject,
            medium=row.medium,
            chapter=row.chapter,
            book_code=row.book_code,
            source_url=row.source_url,
        )
        for row in rows
    ]

    return SearchResponse(query=q, hits=hits, count=len(hits))
