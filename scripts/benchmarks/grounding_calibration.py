"""
Calibrate the grounding threshold on a distribution rather than on four answers.

GROUNDING_MIN separates answers written from their retrieved passages from
answers that drifted. It was set at 0.55 because three hand-checked correct
answers scored 0.583-0.701 and one invented answer scored 0.489. Four points
that happen to separate are not a calibration, and the paper said so.

The difficulty is obtaining ungrounded answers in quantity: a model asked to
hallucinate does not hallucinate the way a grounded pipeline fails. So the
negatives are constructed instead of solicited. Every answer is generated
normally, from its own retrieved context, and then scored twice:

    matched     answer against the passages it was actually written from
    mismatched  the same answer against another question's passages

A mismatched pair is exactly the failure the metric exists to catch -- fluent,
well-formed, on a different subject -- and it needs no human labelling and no
second generation pass. N questions yield N matched and N(N-1) mismatched
pairs, so a modest number of generations produces a usable distribution.

    venv/bin/python scripts/benchmarks/grounding_calibration.py [n_questions]

Reports both distributions, the separation between them, and the threshold that
maximises balanced accuracy -- alongside the one currently shipped.
"""

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Spread across subjects and classes so the mismatched pairs are genuinely
# unrelated rather than neighbouring chapters of one book.
QUESTIONS = [
    "What is photosynthesis and why do plants need sunlight?",
    "Explain the Pythagoras theorem with an example.",
    "How does the human eye focus on distant objects?",
    "What is an electric current and how is it measured?",
    "Describe the structure and function of the human heart.",
    "What are the causes of the French Revolution?",
    "Explain how sound travels through different media.",
    "What is the difference between an acid and a base?",
    "How do plants transport water from roots to leaves?",
    "What is gravitation and who described it first?",
    "Explain the water cycle in nature.",
    "What are the main features of Indian democracy?",
    "How does a lever reduce the effort needed to lift a load?",
    "What is the role of chlorophyll in a leaf?",
    "Explain the process of digestion in humans.",
    "What is a chemical reaction? Give two examples.",
]

CONTEXT_HITS = 6
CONTEXT_CHARS = 1100

SQL = text("""
    SELECT left(d.chunk_text, :chars) AS passage
    FROM embeddings e
    JOIN document_chunks d ON d.id = e.chunk_id
    JOIN processed_content p ON p.id = d.content_id
    WHERE p.metadata->>'source' = 'NCERT'
      AND p.metadata->>'medium' = ANY(:media)
    ORDER BY e.embedding <=> CAST(:v AS vector)
    LIMIT :k
""")


async def generate_all(prompts: list[str]) -> list[str]:
    """
    Every generation in one event loop.

    asyncio.run() per prompt closes the loop the HTTP client is bound to, and
    the second call then dies inside the client's own connection teardown with
    "Event loop is closed". The same mistake silently degraded the
    cross-lingual benchmark, where the failure was caught by a fallback and
    half the measurements quietly became the control arm.
    """
    from backend.services.inference.unified_engine import (
        GenerationConfig,
        get_inference_engine,
    )

    engine = get_inference_engine()
    config = GenerationConfig(max_tokens=600, temperature=0.3, use_cache=False)

    out = []
    for i, prompt in enumerate(prompts, 1):
        answer = await engine.generate(prompt, config)
        print(f"  {i}. {len(answer)} chars")
        out.append(answer)
    return out


def main() -> int:
    import numpy as np

    from backend.api.routes.tutor import GROUNDING_MIN, TEACHING_MEDIA, build_prompt
    from backend.services.rag import get_embedder

    wanted = int(sys.argv[1]) if len(sys.argv) > 1 else len(QUESTIONS)
    questions = QUESTIONS[:wanted]

    url = os.getenv("INGEST_DATABASE_URL", "postgresql://postgres@localhost:5432/shiksha_setu")
    engine = create_engine(url)
    embedder = get_embedder()

    class Row:
        """The attributes build_prompt() reads off a retrieved row."""

        def __init__(self, passage):
            self.passage = passage
            self.grade = None
            self.subject = "Science"
            self.chapter = 1

    print(f"retrieving context for {len(questions)} questions ...")
    prompts, contexts = [], []
    for question in questions:
        vector = embedder.encode_query(question).tolist()
        with engine.connect() as connection:
            rows = [
                Row(r.passage)
                for r in connection.execute(
                    SQL,
                    {
                        "v": str(vector),
                        "k": CONTEXT_HITS,
                        "chars": CONTEXT_CHARS,
                        "media": list(TEACHING_MEDIA),
                    },
                ).all()
            ]
        if not rows:
            continue
        prompts.append(build_prompt(question, rows, None, "English", False))
        contexts.append("\n\n".join(r.passage for r in rows))

    print(f"generating {len(prompts)} answers ...")
    generated = asyncio.run(generate_all(prompts))

    answers = [a for a in generated if a.strip()]
    contexts = [c for c, a in zip(contexts, generated) if a.strip()]
    n = len(answers)
    if n < 4:
        print("too few answers to calibrate")
        return 1

    # One encode per answer and per context, then all pairs by dot product.
    vectors = embedder.encode([a[:4000] for a in answers] + [c[:4000] for c in contexts])
    vectors = np.asarray(vectors, dtype=np.float64)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    answer_vecs, context_vecs = vectors[:n], vectors[n:]
    sim = answer_vecs @ context_vecs.T

    matched = np.diag(sim)
    mismatched = sim[~np.eye(n, dtype=bool)]

    def summary(name, values):
        print(f"  {name:<12} n={len(values):>4}  mean {values.mean():.3f}  "
              f"sd {values.std():.3f}  min {values.min():.3f}  max {values.max():.3f}")

    print(f"\n{n} answers -> {n} matched pairs, {len(mismatched)} mismatched pairs\n")
    summary("matched", matched)
    summary("mismatched", mismatched)
    print(f"\n  overlap: {(mismatched >= matched.min()).sum()} mismatched pairs score at or "
          f"above the weakest matched pair ({matched.min():.3f})")

    # Balanced accuracy over candidate thresholds.
    best = max(
        (
            (
                0.5 * ((matched >= t).mean() + (mismatched < t).mean()),
                t,
            )
            for t in np.arange(0.30, 0.85, 0.005)
        )
    )
    accuracy, threshold = best
    shipped = 0.5 * ((matched >= GROUNDING_MIN).mean() + (mismatched < GROUNDING_MIN).mean())

    print(f"\n  best threshold      {threshold:.3f}   balanced accuracy {accuracy:.3f}")
    print(f"  shipped threshold   {GROUNDING_MIN:.3f}   balanced accuracy {shipped:.3f}")
    print(f"    at shipped: {(matched < GROUNDING_MIN).sum()}/{n} grounded answers "
          f"flagged, {(mismatched >= GROUNDING_MIN).sum()}/{len(mismatched)} drifted answers missed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
