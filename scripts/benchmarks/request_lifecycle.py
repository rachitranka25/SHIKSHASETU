"""
Time each stage of the request path, because the paper draws them as measured.

Figure 1 gives a latency for every stage of the tutor request. Those numbers
came from a hand-written architecture note, and no committed script produced
them -- which is the same footing the Apple M4 figures were on before they were
deleted from this paper. Either they get measured or the figure stops calling
them measurements.

This runs the same calls the route runs, in the same order, with a clock around
each: the rewrite, the query embedding, the wide retrieval, class attribution,
the narrow retrieval, and the generation. It does not go through HTTP, so what
it reports is the work rather than the framework overhead around it.

    venv/bin/python -u scripts/benchmarks/request_lifecycle.py [repeats]

Reports median and p95 per stage. The median is what the figure should quote;
the spread is what a reader needs to know about a pipeline containing two
network calls.
"""

import asyncio
import os
import statistics
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

QUESTIONS = [
    "What is photosynthesis and why do plants need sunlight?",
    "bhai rusting kaise hoti hai",
    "Explain the Pythagoras theorem with an example.",
    "மனித கண் எவ்வாறு குவியப்படுத்துகிறது?",
    "What are the causes of the French Revolution?",
]


async def one_request(db, engine, embedder, question, stages):
    from backend.api.routes.tutor import (
        CONTEXT_HITS,
        DISCOVERY_HITS,
        _retrieve,
        build_prompt,
        merge_hits,
        rewrite_for_search,
        vote_grade,
    )
    from backend.services.inference.unified_engine import GenerationConfig

    t0 = time.perf_counter()
    search_query = await rewrite_for_search(question, engine, GenerationConfig)
    stages["1 rewrite"].append(time.perf_counter() - t0)

    queries = [question] + ([search_query] if search_query != question else [])

    t0 = time.perf_counter()
    vectors = [embedder.encode_query(q).tolist() for q in queries]
    stages["2 embed"].append(time.perf_counter() - t0)

    t0 = time.perf_counter()
    discovery = [_retrieve(db, v, None, DISCOVERY_HITS) for v in vectors]
    stages["3 wide retrieval"].append(time.perf_counter() - t0)

    t0 = time.perf_counter()
    grade = vote_grade(discovery)
    stages["4 class scoring"].append(time.perf_counter() - t0)

    t0 = time.perf_counter()
    narrow = [_retrieve(db, v, grade, CONTEXT_HITS) for v in vectors]
    rows = merge_hits(narrow, CONTEXT_HITS)
    stages["5 narrow retrieval"].append(time.perf_counter() - t0)

    if not rows:
        return
    prompt = build_prompt(question, rows, grade, "English", False)

    t0 = time.perf_counter()
    await engine.generate(prompt, GenerationConfig(max_tokens=600, temperature=0.3, use_cache=False))
    stages["6 generate"].append(time.perf_counter() - t0)


async def main() -> int:
    from backend.services.inference.unified_engine import get_inference_engine
    from backend.services.rag import get_embedder

    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    url = os.getenv("INGEST_DATABASE_URL", "postgresql://postgres@localhost:5432/shiksha_setu")
    db = Session(bind=create_engine(url))
    engine = get_inference_engine()
    embedder = get_embedder()

    stages: dict[str, list[float]] = {
        k: [] for k in ("1 rewrite", "2 embed", "3 wide retrieval",
                        "4 class scoring", "5 narrow retrieval", "6 generate")
    }

    # One untimed pass: the first call of anything pays for a cold cache, a
    # cold connection pool and a model that has not been touched yet, and the
    # figure describes a warm request.
    print("warming ...", flush=True)
    await one_request(db, engine, embedder, QUESTIONS[0], {k: [] for k in stages})

    total = repeats * len(QUESTIONS)
    print(f"timing {total} requests ...", flush=True)
    for r in range(repeats):
        for q in QUESTIONS:
            await one_request(db, engine, embedder, q, stages)
            print(".", end="", flush=True)
    print("\n")

    print(f"{'stage':<20}{'n':>3}{'median':>10}{'p95':>10}{'min':>9}{'max':>9}")
    end_to_end = [0.0] * min(len(v) for v in stages.values() if v)
    for name, values in stages.items():
        if not values:
            print(f"{name:<20}  never ran")
            continue
        s = sorted(values)
        p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
        print(f"{name:<20}{len(values):>3}{statistics.median(values):>9.3f}s"
              f"{p95:>9.3f}s{min(values):>8.3f}s{max(values):>8.3f}s")
        for i in range(len(end_to_end)):
            end_to_end[i] += values[i]
    if end_to_end:
        print(f"\n{'end to end':<20}{len(end_to_end):>3}"
              f"{statistics.median(end_to_end):>9.3f}s"
              f"{max(end_to_end):>9.3f}s (max)")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
