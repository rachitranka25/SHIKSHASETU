"""
Isolate one variable: does encoding answers and contexts in a single batch
give a different result from encoding them separately?

Two runs of what should be the same grounding measurement disagreed --
balanced accuracy 0.451 against 0.998 -- and the two scripts differ in exactly
this respect. If batching moves the vectors, every similarity number the
project has ever reported depends on how many texts happened to be encoded
together, which would be a defect in the embedder wrapper rather than a
property of the metric.

Runs off the cached generations, so it costs no model calls beyond encoding.

    venv/bin/python -u scripts/benchmarks/grounding_batch_check.py
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CACHE = ROOT / ".grounding_cache.json"


def unit(matrix):
    matrix = np.asarray(matrix, dtype=np.float64)
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


def score(name, answers_vecs, context_vecs):
    n = answers_vecs.shape[0]
    sim = answers_vecs @ context_vecs.T
    matched = np.diag(sim)
    mismatched = sim[~np.eye(n, dtype=bool)]
    best = max(
        (0.5 * ((matched >= t).mean() + (mismatched < t).mean()), t)
        for t in np.arange(0.10, 0.95, 0.005)
    )
    print(
        f"  {name:<16} matched {matched.mean():.3f}+-{matched.std():.3f}   "
        f"mismatched {mismatched.mean():.3f}+-{mismatched.std():.3f}   "
        f"bal.acc {best[0]:.3f} @ t={best[1]:.3f}",
        flush=True,
    )
    return matched, mismatched


def main():
    from backend.services.rag import get_embedder

    records = json.loads(CACHE.read_text())
    answers = [r["answer"][:4000] for r in records]
    contexts = ["\n\n".join(r["passages"])[:4000] for r in records]
    n = len(answers)
    print(f"{n} cached answer/context pairs\n", flush=True)

    embedder = get_embedder()

    print("encoding combined (answers + contexts in one call) ...", flush=True)
    combined = unit(embedder.encode(answers + contexts))
    a_combined, c_combined = combined[:n], combined[n:]

    print("encoding separately (two calls) ...", flush=True)
    a_separate = unit(embedder.encode(answers))
    c_separate = unit(embedder.encode(contexts))

    print(flush=True)
    score("combined-batch", a_combined, c_combined)
    score("separate-batch", a_separate, c_separate)

    drift_a = float(np.abs(a_combined - a_separate).max())
    drift_c = float(np.abs(c_combined - c_separate).max())
    cos_a = float((a_combined * a_separate).sum(axis=1).min())
    cos_c = float((c_combined * c_separate).sum(axis=1).min())
    print(
        f"\n  vector drift: answers max|delta| {drift_a:.2e} (min self-cos {cos_a:.6f}), "
        f"contexts max|delta| {drift_c:.2e} (min self-cos {cos_c:.6f})",
        flush=True,
    )
    # The model runs in half precision, so componentwise deltas of order 1e-4
    # are rounding, not batch dependence. Self-cosine is the honest test: two
    # encodings of one text agreeing to 1e-6 are the same vector.
    if min(cos_a, cos_c) > 0.99999:
        print("  -> batching does not move the vectors; the disagreement is elsewhere.")
    else:
        print("  -> batching MOVES the vectors: encode() is batch-dependent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
