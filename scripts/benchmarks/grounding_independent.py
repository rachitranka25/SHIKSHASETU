"""
Score the grounding separation with representations BGE-M3 had no part in.

The grounding metric embeds an answer and its passages with BGE-M3 and calls
them grounded when they are close. BGE-M3 also retrieved those passages in the
first place, so the model is judging its own work: if it maps two topics close
together, retrieval and grounding inherit the same blind spot and no
measurement built on BGE-M3 can see it. A reviewer is entitled to ask whether
the reported separation is a property of the answers or of the embedder.

This re-scores the same cached generations under two representations that share
nothing with BGE-M3:

    tfidf     character 3-5 gram TF-IDF cosine -- not neural at all
    minilm    paraphrase-multilingual-MiniLM-L12-v2 -- a different model family
              (distilled MiniLM) trained on a different objective

If the matched/mismatched gap survives both, the separation is a property of
the text. If it collapses under both, the metric measures BGE-M3's geometry.

    venv/bin/python -u scripts/benchmarks/grounding_independent.py

minilm is downloaded on first use (~470 MB); pass --tfidf-only to skip it.
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CACHE = ROOT / ".grounding_cache.json"
MINILM = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def unit(matrix):
    matrix = np.asarray(matrix, dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.clip(norms, 1e-12, None)


def separation(name, sim):
    n = sim.shape[0]
    matched = np.diag(sim)
    mismatched = sim[~np.eye(n, dtype=bool)]
    best = max(
        (0.5 * ((matched >= t).mean() + (mismatched < t).mean()), t)
        for t in np.arange(0.0, 1.0, 0.005)
    )
    print(
        f"  {name:<9} matched {matched.mean():.3f}+-{matched.std():.3f}   "
        f"mismatched {mismatched.mean():.3f}+-{mismatched.std():.3f}   "
        f"gap {matched.mean()-mismatched.mean():+.3f}   "
        f"bal.acc {best[0]:.3f} @ t={best[1]:.3f}",
        flush=True,
    )
    return best[0]


def main():
    records = json.loads(CACHE.read_text())
    answers = [r["answer"][:4000] for r in records]
    contexts = ["\n\n".join(r["passages"])[:4000] for r in records]
    n = len(answers)
    print(f"{n} cached answer/context pairs -> {n} matched, {n*(n-1)} mismatched\n", flush=True)

    results = {}

    # --- 1. character n-gram TF-IDF: no model, no training, no shared geometry
    from sklearn.feature_extraction.text import TfidfVectorizer

    print("tfidf: character 3-5 grams ...", flush=True)
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True)
    matrix = vec.fit_transform(answers + contexts).toarray()
    matrix = unit(matrix)
    results["tfidf"] = separation("tfidf", matrix[:n] @ matrix[n:].T)

    if "--tfidf-only" in sys.argv:
        return 0

    # --- 2. a different multilingual encoder family
    print(f"\nminilm: {MINILM} ...", flush=True)
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(MINILM)
        vectors = unit(model.encode(answers + contexts, batch_size=8, show_progress_bar=False))
        results["minilm"] = separation("minilm", vectors[:n] @ vectors[n:].T)
    except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
        print(f"  minilm unavailable: {type(exc).__name__}: {exc}")
        return 1

    print("\n  BGE-M3 on these same generations: gap +0.360, bal.acc 1.000")
    if min(results.values()) >= 0.9:
        print("  -> the separation survives both; it is a property of the text.")
    else:
        print("  -> the separation does not survive; it is partly BGE-M3's geometry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
