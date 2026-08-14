"""
Peak resident memory of the serving path, measured rather than added up.

The 4 GB claim in docs/ARCHITECTURE.md was arithmetic: component sizes summed
to ~1.6 GB, therefore it fits. Summing is not measuring — it misses the
transient peak while the model's weights are converted, the allocator's
fragmentation, and whatever the query path allocates per request. This does the
work a served request does and reports what the kernel actually charged.

    venv/bin/python scripts/benchmarks/serving_footprint.py

Reads a high-water mark for the life of the process, so the figure survives the
pages being swapped out afterwards -- `ps` reported 46 MB for a process holding
a 1 GB model, because the machine had paged it out. The mark comes from
getrusage on POSIX and from the process memory counters on Windows.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

QUESTION = "What is photosynthesis and why do plants need sunlight?"


def peak_mb() -> float:
    """
    Peak RSS in MB, on whatever the platform is.

    `resource` is POSIX-only, so importing it here made this benchmark --- the
    one that substantiates the 4 GB claim --- unrunnable on Windows, which is
    what a 4 GB school machine usually runs.
    """
    from backend.core.platform_info import peak_rss_mb

    value, _ = peak_rss_mb()
    return value


def report(label: str) -> None:
    print(f"  {label:<38} {peak_mb():>8.0f} MB peak")


def main() -> int:
    report("interpreter start")

    from backend.core.config import settings

    report("config imported")

    from backend.services.rag import BGEM3Embedder, resolve_embedding_dtype

    device = os.getenv("FOOTPRINT_DEVICE")

    started = time.time()
    embedder = BGEM3Embedder(device=device) if device else BGEM3Embedder()
    load_seconds = time.time() - started
    report("BGE-M3 loaded")

    started = time.time()
    vector = embedder.encode_query(QUESTION).tolist()
    encode_seconds = time.time() - started
    report("query encoded")

    from sqlalchemy import create_engine, text

    url = os.getenv("INGEST_DATABASE_URL") or str(settings.DATABASE_URL)
    url = url.replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(url)

    started = time.time()
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT pc.grade_level, 1 - (e.embedding <=> CAST(:v AS vector)) AS sim
                FROM embeddings e
                JOIN document_chunks dc ON dc.id = e.chunk_id
                JOIN processed_content pc ON pc.id = dc.content_id
                ORDER BY e.embedding <=> CAST(:v AS vector)
                LIMIT 12
            """),
            {"v": str(vector)},
        ).fetchall()
    search_seconds = time.time() - started
    report("pgvector search done")

    device = getattr(embedder, "device", "unknown")
    print()
    print(f"  device                {device}")
    print(f"  dtype                 {resolve_embedding_dtype(str(device))}")
    print(f"  model load            {load_seconds:.1f} s")
    print(f"  query encode          {encode_seconds * 1000:.0f} ms")
    print(f"  retrieval ({len(rows)} hits)  {search_seconds * 1000:.0f} ms")
    print()
    print(f"  PEAK RESIDENT         {peak_mb():.0f} MB")
    print()
    print("  Postgres runs in its own processes; add shared_buffers (256 MB by")
    print("  default) for the whole-machine figure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
