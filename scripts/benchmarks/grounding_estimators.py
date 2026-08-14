"""
Choose the grounding estimator by measurement rather than by assumption.

The shipped estimator scores an answer against the concatenation of every
passage it was given. Calibrated on four hand-checked answers it appeared to
separate grounded from fabricated text, but on a real distribution it does not
separate them at all: mismatched pairs score *higher* on average than matched
ones, and the shipped threshold lands below chance.

The likely cause is the concatenation. Six passages joined into one 6 kB string
embed to a point dominated by register -- "this is school science prose" --
which every fluent answer on the corpus is close to. Grounding is a property of
the answer against *some* passage, not against their average.

So this compares four estimators over the same generations:

    concat      cos(answer, passages joined)          the shipped estimator
    max         max_j cos(answer, passage_j)
    top3        mean of the three best cos(answer, passage_j)
    sentence    mean over answer sentences of max_j cos(sentence, passage_j)

Each is scored on the same matched/mismatched construction: every answer is
generated normally from its own passages, then scored against its own passages
(matched) and against every other question's passages (mismatched). A
mismatched pair is exactly the failure the metric exists to catch, needs no
human labelling, and yields N(N-1) negatives from N generations.

Reported per estimator: the two distributions, the threshold maximising
balanced accuracy, and that accuracy. An estimator at 0.5 is a coin flip.

    venv/bin/python -u scripts/benchmarks/grounding_estimators.py [n_questions]

Generations are cached in .grounding_cache.json, so re-running to add an
estimator costs no model calls.
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CACHE = ROOT / ".grounding_cache.json"

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


class Row:
    """The attributes build_prompt() reads off a retrieved row."""

    def __init__(self, passage):
        self.passage = passage
        self.grade = None
        self.subject = "Science"
        self.chapter = 1


async def generate_all(prompts):
    """Every generation in one event loop; asyncio.run() per prompt closes the
    loop the HTTP client is bound to and the next call dies in its teardown."""
    from backend.services.inference.unified_engine import (
        GenerationConfig,
        get_inference_engine,
    )

    engine = get_inference_engine()
    config = GenerationConfig(max_tokens=600, temperature=0.3, use_cache=False)
    out = []
    for i, prompt in enumerate(prompts, 1):
        answer = await engine.generate(prompt, config)
        print(f"  {i}. {len(answer)} chars", flush=True)
        out.append(answer)
    return out


def collect(questions):
    """Retrieve passages and generate one answer per question, with a cache."""
    from backend.api.routes.tutor import TEACHING_MEDIA, build_prompt
    from backend.services.rag import get_embedder

    if CACHE.exists():
        cached = json.loads(CACHE.read_text())
        if [r["question"] for r in cached] == questions:
            print(f"reusing {len(cached)} cached generations", flush=True)
            return cached

    url = os.getenv("INGEST_DATABASE_URL", "postgresql://postgres@localhost:5432/shiksha_setu")
    db = create_engine(url)
    embedder = get_embedder()

    print(f"retrieving context for {len(questions)} questions ...", flush=True)
    records, prompts = [], []
    for question in questions:
        vector = embedder.encode_query(question).tolist()
        with db.connect() as connection:
            passages = [
                r.passage
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
        if not passages:
            continue
        rows = [Row(p) for p in passages]
        prompts.append(build_prompt(question, rows, None, "English", False))
        records.append({"question": question, "passages": passages})

    print(f"generating {len(prompts)} answers ...", flush=True)
    answers = asyncio.run(generate_all(prompts))
    for record, answer in zip(records, answers):
        record["answer"] = answer

    records = [r for r in records if r["answer"].strip()]
    CACHE.write_text(json.dumps(records, ensure_ascii=False))
    return records


def sentences(answer, minimum=40):
    """Sentence split good enough for prose; short fragments carry no topic."""
    parts = re.split(r"(?<=[.!?])\s+", answer.replace("\n", " "))
    return [p.strip() for p in parts if len(p.strip()) >= minimum] or [answer[:1000]]


def unit(matrix):
    matrix = np.asarray(matrix, dtype=np.float64)
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


def balanced_best(matched, mismatched):
    """Threshold maximising 0.5*(TPR+TNR), and that accuracy."""
    best = max(
        (0.5 * ((matched >= t).mean() + (mismatched < t).mean()), t)
        for t in np.arange(0.10, 0.95, 0.005)
    )
    return best[1], best[0]


def report(name, sim):
    n = sim.shape[0]
    matched = np.diag(sim)
    mismatched = sim[~np.eye(n, dtype=bool)]
    threshold, accuracy = balanced_best(matched, mismatched)
    gap = matched.mean() - mismatched.mean()
    print(
        f"  {name:<10} matched {matched.mean():.3f}+-{matched.std():.3f}   "
        f"mismatched {mismatched.mean():.3f}+-{mismatched.std():.3f}   "
        f"gap {gap:+.3f}   best t={threshold:.3f}  bal.acc {accuracy:.3f}"
    )
    return {"name": name, "threshold": float(threshold), "accuracy": float(accuracy),
            "gap": float(gap)}


def main():
    from backend.services.rag import get_embedder

    wanted = int(sys.argv[1]) if len(sys.argv) > 1 else len(QUESTIONS)
    records = collect(QUESTIONS[:wanted])
    n = len(records)
    if n < 4:
        print("too few answers to calibrate")
        return 1

    embedder = get_embedder()
    answers = [r["answer"] for r in records]
    passage_lists = [r["passages"] for r in records]

    # One encode pass over everything, then all pairs by dot product.
    flat_passages = [p for group in passage_lists for p in group]
    offsets, cursor = [], 0
    for group in passage_lists:
        offsets.append((cursor, cursor + len(group)))
        cursor += len(group)

    answer_sentences = [sentences(a) for a in answers]
    flat_sentences = [s for group in answer_sentences for s in group]
    sent_offsets, cursor = [], 0
    for group in answer_sentences:
        sent_offsets.append((cursor, cursor + len(group)))
        cursor += len(group)

    concats = ["\n\n".join(group)[:4000] for group in passage_lists]

    print(f"\nencoding {n} answers, {len(flat_passages)} passages, "
          f"{len(flat_sentences)} sentences ...", flush=True)
    A = unit(embedder.encode([a[:4000] for a in answers]))
    P = unit(embedder.encode([p[:4000] for p in flat_passages]))
    S = unit(embedder.encode([s[:4000] for s in flat_sentences]))
    C = unit(embedder.encode(concats))

    concat_sim = A @ C.T

    answer_passage = A @ P.T                      # n x total_passages
    max_sim = np.zeros((n, n))
    top3_sim = np.zeros((n, n))
    for j, (start, end) in enumerate(offsets):
        block = answer_passage[:, start:end]      # n x k
        max_sim[:, j] = block.max(axis=1)
        k = min(3, block.shape[1])
        top3_sim[:, j] = np.sort(block, axis=1)[:, -k:].mean(axis=1)

    sent_passage = S @ P.T
    sentence_sim = np.zeros((n, n))
    for i, (s_start, s_end) in enumerate(sent_offsets):
        rows = sent_passage[s_start:s_end]        # sentences_i x total_passages
        for j, (p_start, p_end) in enumerate(offsets):
            sentence_sim[i, j] = rows[:, p_start:p_end].max(axis=1).mean()

    print(f"\n{n} answers -> {n} matched pairs, {n * (n - 1)} mismatched pairs\n")
    results = [
        report("concat", concat_sim),
        report("max", max_sim),
        report("top3", top3_sim),
        report("sentence", sentence_sim),
    ]

    winner = max(results, key=lambda r: r["accuracy"])
    print(f"\n  best estimator: {winner['name']} at threshold {winner['threshold']:.3f} "
          f"(balanced accuracy {winner['accuracy']:.3f})")
    print("  chance is 0.500; the shipped estimator is 'concat'.")

    # What the deployed threshold costs on the estimator actually deployed.
    from backend.api.routes.tutor import GROUNDING_MIN

    matched = np.diag(concat_sim)
    mismatched = concat_sim[~np.eye(n, dtype=bool)]
    for label, t in (("shipped", GROUNDING_MIN), ("measured", winner["threshold"])):
        flagged = int((matched < t).sum())
        missed = int((mismatched >= t).sum())
        accuracy = 0.5 * ((matched >= t).mean() + (mismatched < t).mean())
        print(
            f"  {label:<9} t={t:.3f}  bal.acc {accuracy:.3f}  "
            f"grounded answers wrongly flagged {flagged}/{n}  "
            f"drifted answers missed {missed}/{len(mismatched)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
