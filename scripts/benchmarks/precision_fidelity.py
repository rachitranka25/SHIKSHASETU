"""
Measure what half precision costs, on the corpus rather than on four queries.

The paper reports a cosine fidelity of 0.999999 between the half-precision and
full-precision embeddings, and concludes that a difference that small "cannot
reorder any result list". The first number came from four short queries. The
second is not a measurement at all: it is an inference, and a wrong one in
principle, because two passages whose similarities differ by less than the
perturbation can swap.

So both get measured here, on real passages:

    fidelity   cosine between the fp32 and fp16 embedding of the same text,
               reported as a distribution rather than a single figure
    ranking    for each query, whether the top-k under fp16 is the same list
               in the same order as under fp32

    venv/bin/python -u scripts/benchmarks/precision_fidelity.py [n_passages]
"""

import os
import sys
from pathlib import Path

import numpy as np
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

QUERIES = [
    "What is photosynthesis and why do plants need sunlight?",
    "Explain the Pythagoras theorem with an example.",
    "How does the human eye focus on distant objects?",
    "What are the causes of the French Revolution?",
    "Describe the structure and function of the human heart.",
    "What is the difference between an acid and a base?",
    "Explain the water cycle in nature.",
    "How does a lever reduce the effort needed to lift a load?",
]
TOP_K = 12

SAMPLE = text("""
    SELECT left(d.chunk_text, 1200) AS passage
    FROM document_chunks d
    JOIN processed_content p ON p.id = d.content_id
    WHERE p.metadata->>'source' = 'NCERT'
    ORDER BY d.id
    LIMIT :n
""")


def unit(m):
    m = np.asarray(m, dtype=np.float64)
    return m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-12, None)


def main() -> int:
    from sentence_transformers import SentenceTransformer

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    url = os.getenv("INGEST_DATABASE_URL", "postgresql://postgres@localhost:5432/shiksha_setu")
    with create_engine(url).connect() as c:
        passages = [r.passage for r in c.execute(SAMPLE, {"n": n})]
    print(f"{len(passages)} passages, {len(QUERIES)} queries\n", flush=True)

    vecs = {}
    for precision in ("float32", "float16"):
        print(f"encoding at {precision} ...", flush=True)
        model = SentenceTransformer("BAAI/bge-m3")
        model = model.half() if precision == "float16" else model.float()
        vecs[precision] = (
            unit(model.encode(passages, batch_size=8, show_progress_bar=False)),
            unit(model.encode(QUERIES, batch_size=8, show_progress_bar=False)),
        )
        del model

    (p32, q32), (p16, q16) = vecs["float32"], vecs["float16"]

    fid = (p32 * p16).sum(axis=1)
    print(f"\nfidelity over {len(fid)} passages")
    print(f"  mean {fid.mean():.6f}   min {fid.min():.6f}   "
          f"1st pct {np.percentile(fid, 1):.6f}")

    # The claim under test: does the top-k list, and its order, survive fp16?
    s32, s16 = q32 @ p32.T, q16 @ p16.T
    same_set = same_order = 0
    worst = None
    for i in range(len(QUERIES)):
        a = np.argsort(-s32[i])[:TOP_K]
        b = np.argsort(-s16[i])[:TOP_K]
        same_set += set(a) == set(b)
        same_order += list(a) == list(b)
        if list(a) != list(b) and worst is None:
            first = next(j for j in range(TOP_K) if a[j] != b[j])
            worst = (i, first + 1)
    print(f"\ntop-{TOP_K} under fp16 against fp32, over {len(QUERIES)} queries")
    print(f"  same passages, any order : {same_set}/{len(QUERIES)}")
    print(f"  same passages, same order: {same_order}/{len(QUERIES)}")
    if worst:
        print(f"  first divergence: query {worst[0]+1} at rank {worst[1]}")
    print("\n  " + ("no reordering observed" if same_order == len(QUERIES)
                    else "reordering does occur, so the claim needs the rank at which it happens"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
