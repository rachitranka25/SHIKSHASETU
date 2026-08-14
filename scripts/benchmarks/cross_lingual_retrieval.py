"""
Cross-lingual retrieval against the English corpus, with the queries written out.

The paper reports similarity figures for questions asked in Indian languages
against English-medium NCERT science books. Earlier runs recorded only the
resulting numbers, which makes them impossible to re-measure when the corpus
grows. The queries live here instead, so the experiment can be repeated on any
corpus state and the numbers can be regenerated rather than copied.

    venv/bin/python scripts/benchmarks/cross_lingual_retrieval.py

A verdict is decided on the **top hit only**, and the rank of the first on-topic
passage is reported alongside it. An earlier version asked merely whether an
expected term appeared anywhere in the top five, and it scored both
photosynthesis queries as successes: "chlorophyll" did appear -- at rank three,
under two chapters about the reflection and refraction of light. Retrieval that
puts optics above biology has failed the student regardless of what sits below
it.
"""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Each query is a real question a student might type, paired with terms that
# must appear in a correct passage. The English gloss is for the reader; only
# the query is embedded.
QUERIES = [
    {
        "language": "Hindi",
        "gloss": "How does the human eye focus on objects?",
        "query": "मानव नेत्र किसी वस्तु पर फोकस कैसे करता है?",
        "expect": ["eye", "lens", "retina", "ciliary"],
    },
    {
        "language": "Marathi",
        "gloss": "What is electric current?",
        "query": "विद्युत प्रवाह म्हणजे काय?",
        "expect": ["current", "charge", "ampere", "circuit"],
    },
    {
        "language": "Bengali",
        "gloss": "How does the heart work?",
        "query": "হৃৎপিণ্ড কীভাবে কাজ করে?",
        "expect": ["heart", "blood", "ventricle", "atrium"],
    },
    {
        "language": "Hindi",
        "gloss": "What is photosynthesis?",
        "query": "प्रकाश संश्लेषण क्या है?",
        "expect": ["photosynthesis", "chlorophyll", "sunlight"],
    },
    {
        "language": "Tamil",
        "gloss": "What is photosynthesis?",
        "query": "ஒளிச்சேர்க்கை என்றால் என்ன?",
        "expect": ["photosynthesis", "chlorophyll", "sunlight"],
    },
]

TOP_K = 5


def main() -> int:
    from backend.services.rag import get_embedder

    url = os.getenv("INGEST_DATABASE_URL", "postgresql://postgres@localhost:5432/shiksha_setu")
    engine = create_engine(url)
    embedder = get_embedder()

    with engine.connect() as connection:
        books, chunks = connection.execute(
            text("""
                SELECT count(DISTINCT metadata->>'book_code'),
                       (SELECT count(*) FROM document_chunks)
                FROM processed_content WHERE metadata->>'source' = 'NCERT'
            """)
        ).one()

    print(f"corpus: {books} books, {chunks} indexed passages\n")
    print(f"{'Language':<9} {'Topic':<34} {'Top sim':>8}  Verdict")
    print("-" * 78)

    rows_out = []
    for case in QUERIES:
        vector = embedder.encode_query(case["query"]).tolist()
        with engine.connect() as connection:
            hits = connection.execute(
                text("""
                    SELECT 1 - (e.embedding <=> CAST(:v AS vector)) AS sim,
                           p.grade_level, p.subject,
                           (p.metadata->>'chapter')::int AS chapter,
                           d.chunk_text
                    FROM embeddings e
                    JOIN document_chunks d ON d.id = e.chunk_id
                    JOIN processed_content p ON p.id = d.content_id
                    WHERE p.metadata->>'medium' = 'English'
                    ORDER BY e.embedding <=> CAST(:v AS vector)
                    LIMIT :k
                """),
                {"v": str(vector), "k": TOP_K},
            ).all()

        def matches(hit) -> bool:
            body = hit.chunk_text.lower()
            return any(term.lower() in body for term in case["expect"])

        top = hits[0] if hits else None
        top_ok = bool(top and matches(top))
        first_ok = next((i for i, h in enumerate(hits, 1) if matches(h)), None)

        if top_ok:
            verdict = "correct"
        elif first_ok:
            verdict = f"FAILED (on-topic only at rank {first_ok})"
        else:
            verdict = "FAILED (nothing on-topic in top %d)" % TOP_K

        sim = f"{top.sim:.3f}" if top else "---"
        print(f"{case['language']:<9} {case['gloss']:<34} {sim:>8}  {verdict}")
        for h in hits[:3]:
            mark = "*" if matches(h) else " "
            print(f"        {mark} class {h.grade_level:>2} | {h.subject[:26]:<26} ch {h.chapter} | {h.sim:.3f}")
        rows_out.append((case["language"], case["gloss"], top.sim if top else None, top_ok))
        print()

    good = [s for _, _, s, ok in rows_out if ok and s is not None]
    print(f"{len(good)} of {len(rows_out)} queries retrieved an on-topic passage at rank 1"
          + (f", cosine {min(good):.3f}-{max(good):.3f}" if good else ""))
    print("(* marks a hit containing an expected term)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
