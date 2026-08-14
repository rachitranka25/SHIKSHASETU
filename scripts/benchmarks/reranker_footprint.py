"""
Measure what a cross-encoder reranker would cost, instead of asserting it.

The paper reports BGE-Reranker-v2-M3 as integrated but not wired into the
retrieval path, and separately argues that a bi-encoder is what a 4 GB machine
can afford. Those two statements are only connected if the reranker actually
does not fit, and nothing here had measured that.

A cross-encoder is not a second copy of the embedder. It scores query and
passage jointly, so it holds its own weights and its own attention workspace,
on top of the embedder that must stay resident to search at all. This loads
the embedder first, records peak resident set, then loads the reranker and
reranks a realistic candidate list, and records it again.

    venv/bin/python -u scripts/benchmarks/reranker_footprint.py

Reports peak RSS after each stage, so the question "does the reranker fit
beside the embedder inside 4 GB" has a number rather than an opinion.
"""

import os
import resource
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

QUERY = "What is photosynthesis and why do plants need sunlight?"
CANDIDATES = 12  # what the wide retrieval hands on


def peak_mb() -> float:
    """Peak RSS. ru_maxrss is bytes on macOS and kilobytes on Linux."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024


def now_mb() -> float:
    """
    Resident set right now.

    Peak alone cannot answer this question. ru_maxrss is a high-water mark and
    never falls, so once the embedder's first forward pass has peaked above
    whatever the reranker costs, loading the reranker moves the peak by zero
    and looks free. What the reranker adds is visible only in current RSS.
    """
    import psutil

    return psutil.Process().memory_info().rss / (1024 * 1024)


def passages(n: int) -> list[str]:
    from sqlalchemy import create_engine, text

    url = os.getenv("INGEST_DATABASE_URL", "postgresql://postgres@localhost:5432/shiksha_setu")
    sql = text("""
        SELECT left(d.chunk_text, 1200) AS passage
        FROM document_chunks d
        JOIN processed_content p ON p.id = d.content_id
        WHERE p.metadata->>'source' = 'NCERT'
        ORDER BY d.id LIMIT :n
    """)
    with create_engine(url).connect() as c:
        return [r.passage for r in c.execute(sql, {"n": n})]


def main() -> int:
    print(f"{'stage':<40}{'now':>10}{'peak':>10}")
    print(f"{'interpreter and imports':<40}{now_mb():>8.0f} MB{peak_mb():>8.0f} MB")

    from backend.services.rag import get_embedder

    embedder = get_embedder()
    embedder.encode_query(QUERY)
    after_embedder = now_mb()
    print(f"{'embedder loaded, one query encoded':<40}{after_embedder:>8.0f} MB{peak_mb():>8.0f} MB")

    docs = passages(CANDIDATES)

    from sentence_transformers import CrossEncoder

    reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=1024)
    after_load = now_mb()
    print(f"{'reranker loaded':<40}{after_load:>8.0f} MB{peak_mb():>8.0f} MB")

    scores = reranker.predict([(QUERY, d) for d in docs])
    after_rerank = now_mb()
    print(f"{'reranked ' + str(len(docs)) + ' candidates':<40}{after_rerank:>8.0f} MB{peak_mb():>8.0f} MB")

    print(f"\n  reranker adds {after_rerank - after_embedder:.0f} MB resident on top of the embedder")
    print(f"  peak across the whole run: {peak_mb():.0f} MB")
    budget = 4096
    headroom = budget - peak_mb()
    if headroom > 0:
        print(f"  fits a {budget} MB budget with {headroom:.0f} MB to spare, before OS overhead")
    else:
        print(f"  exceeds a {budget} MB budget by {-headroom:.0f} MB")
    print(f"  top candidate by reranker: index {int(scores.argmax())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
