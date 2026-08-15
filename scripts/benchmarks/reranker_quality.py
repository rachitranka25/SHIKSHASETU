"""
Does the cross-encoder reranker actually improve retrieval, or only cost memory?

The paper reports BGE-Reranker-v2-M3 as integrated but not wired into the
retrieval path, and justifies that by its memory footprint alone. That is half
an argument: a component that fits badly but retrieves much better might still
be worth the RAM, and nothing here had measured the retrieval half.

This reruns the deployed pooled configuration over the same query set the
ablation uses, then reranks each candidate list with the cross-encoder and
scores both by the same rank-1 criterion. The comparison is paired -- identical
queries, identical candidates, the only difference being whether the reranker
reorders them -- so any difference is the reranker's.

    venv/bin/python -u scripts/benchmarks/reranker_quality.py

Reports rank-1 accuracy before and after, how many queries each direction
moved, and the resident memory the reranker added, so the trade can be stated
as a number rather than asserted.
"""

import asyncio
import os
import resource
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(ROOT / "scripts" / "benchmarks"))
from cross_lingual_retrieval import (  # noqa: E402
    SQL,
    TOP_K,
    QUERIES,
    english_queries,
    wilson,
)

# The reranker sees a wider pool than the five passages a verdict is read from;
# reordering the same five could only ever permute what dense retrieval already
# chose, which is not what a reranker is for.
CANDIDATES = 20


def rss_mb() -> float:
    import psutil

    return psutil.Process().memory_info().rss / (1024 * 1024)


def peak_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024


def rank_of(passages: list[str], expect: list[str]) -> int | None:
    for i, p in enumerate(passages, 1):
        if any(t.lower() in p.lower() for t in expect):
            return i
    return None


def main() -> int:
    from backend.services.rag import get_embedder

    url = os.getenv("INGEST_DATABASE_URL",
                    "postgresql://postgres@localhost:5432/shiksha_setu")
    engine = create_engine(url)
    embedder = get_embedder()

    def retrieve(q: str, k: int):
        v = embedder.encode_query(q).tolist()
        with engine.connect() as c:
            return c.execute(SQL, {"v": str(v), "k": k}).all()

    print(f"{len(QUERIES)} queries, pooling raw and rewritten, "
          f"{CANDIDATES} candidates reranked to {TOP_K}\n", flush=True)

    rewrites = asyncio.run(english_queries([q["query"] for q in QUERIES]))

    pooled_lists: list[tuple[dict, list[str]]] = []
    for case, rewritten in zip(QUERIES, rewrites):
        best: dict[str, float] = {}
        for hit in list(retrieve(case["query"], CANDIDATES)) + list(
            retrieve(rewritten, CANDIDATES)
        ):
            key = hit.chunk_text
            best[key] = max(best.get(key, -1.0), hit.sim)
        ordered = sorted(best, key=lambda t: best[t], reverse=True)[:CANDIDATES]
        pooled_lists.append((case, ordered))

    before_load = rss_mb()
    from sentence_transformers import CrossEncoder

    reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=1024)

    base_hits = rr_hits = 0
    improved = worsened = 0
    for case, ordered in pooled_lists:
        base_rank = rank_of(ordered[:TOP_K], case["expect"])
        scores = reranker.predict([(case["query"], p) for p in ordered])
        reordered = [p for _, p in sorted(zip(scores, ordered),
                                          key=lambda pair: pair[0], reverse=True)]
        rr_rank = rank_of(reordered[:TOP_K], case["expect"])
        base_hits += base_rank == 1
        rr_hits += rr_rank == 1
        if base_rank != 1 and rr_rank == 1:
            improved += 1
        elif base_rank == 1 and rr_rank != 1:
            worsened += 1
            print(f"  reranker demoted a correct hit: "
                  f"{case['language']} {case['topic']}", flush=True)

    after = rss_mb()
    n = len(QUERIES)
    bp, blo, bhi = wilson(base_hits, n)
    rp, rlo, rhi = wilson(rr_hits, n)

    print(f"\n{'':<26}{'rank-1':>10}{'95% Wilson':>22}")
    print(f"  {'pooled (deployed)':<24}{base_hits:>4}/{n}{bp:>7.3f}   "
          f"[{blo:.3f}, {bhi:.3f}]")
    print(f"  {'pooled + reranker':<24}{rr_hits:>4}/{n}{rp:>7.3f}   "
          f"[{rlo:.3f}, {rhi:.3f}]")
    print(f"\n  queries the reranker fixed:  {improved}")
    print(f"  queries the reranker broke:  {worsened}")
    print(f"  net:                         {rr_hits - base_hits:+d}")
    print(f"\n  resident memory added by the reranker: "
          f"{after - before_load:.0f} MB")
    print(f"  peak across the run: {peak_mb():.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
