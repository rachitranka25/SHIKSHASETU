"""
Find out why 32 of 50 chunks in one chapter embedded to a non-finite vector.

Ingesting class 11 Physics chapter 7 produced 32 chunks whose embedding
contained NaN or an infinity. The pipeline now drops them, which keeps one
chapter from costing a textbook, but dropping is not an explanation, and the
paper claims half precision costs "no measurable quality degradation" on the
strength of a cosine fidelity of 0.999999 measured over four queries.

If half precision is what produces these vectors, that claim is measured on the
wrong sample: four short queries cannot exhibit a failure that appears on long
textbook passages. So encode the same chunks both ways and compare.

    venv/bin/python -u scripts/benchmarks/nan_embedding_probe.py
"""

import os
import sys
from pathlib import Path

import numpy as np
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CHAPTER_SQL = text("""
    SELECT original_text
    FROM processed_content
    WHERE metadata->>'book_code' = :code AND (metadata->>'chapter')::int = :chapter
    LIMIT 1
""")


def non_finite(matrix):
    matrix = np.asarray(matrix, dtype=np.float64)
    return int((~np.isfinite(matrix)).any(axis=1).sum())


def main():
    from backend.services.ingestion.ncert_ingest import chunk_text

    code = sys.argv[1] if len(sys.argv) > 1 else "keph1"
    chapter = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    url = os.getenv("INGEST_DATABASE_URL", "postgresql://postgres@localhost:5432/shiksha_setu")
    with create_engine(url).connect() as connection:
        row = connection.execute(CHAPTER_SQL, {"code": code, "chapter": chapter}).first()
    if not row:
        print(f"{code} chapter {chapter} is not in the database")
        return 1

    chunks = list(chunk_text(row.original_text))
    print(f"{code} chapter {chapter}: {len(chunks)} chunks, "
          f"{min(map(len, chunks))}-{max(map(len, chunks))} chars\n", flush=True)

    from sentence_transformers import SentenceTransformer

    results = {}
    for precision in ("float16", "float32"):
        print(f"encoding at {precision} ...", flush=True)
        model = SentenceTransformer("BAAI/bge-m3")
        model = model.half() if precision == "float16" else model.float()
        vectors = model.encode(chunks, batch_size=8, show_progress_bar=False)
        bad = non_finite(vectors)
        results[precision] = (vectors, bad)
        print(f"  {precision}: {bad} of {len(chunks)} chunks non-finite", flush=True)
        del model

    fp16, fp32 = results["float16"][0], results["float32"][0]
    both_ok = np.isfinite(fp16).all(axis=1) & np.isfinite(fp32).all(axis=1)
    if both_ok.sum():
        a = np.asarray(fp16[both_ok], dtype=np.float64)
        b = np.asarray(fp32[both_ok], dtype=np.float64)
        a /= np.linalg.norm(a, axis=1, keepdims=True)
        b /= np.linalg.norm(b, axis=1, keepdims=True)
        cos = (a * b).sum(axis=1)
        print(f"\n  on the {int(both_ok.sum())} chunks finite in both: "
              f"cosine fidelity min {cos.min():.6f}, mean {cos.mean():.6f}")

    print()
    if results["float16"][1] and not results["float32"][1]:
        print("  -> half precision is the cause. Full precision produces none.")
    elif results["float16"][1] and results["float32"][1]:
        print("  -> both precisions fail; the input, not the precision, is the cause.")
    else:
        print("  -> neither reproduces it here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
