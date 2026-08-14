"""
Cross-lingual retrieval against the English corpus, with and without the rewrite.

Two arms, because they answer different questions:

  raw      the student's question is embedded directly. This measures BGE-M3's
           cross-lingual reach, and nothing else.
  rewrite  the question is first turned into an English search query by the
           language model, which is what the tutor actually does. This measures
           the deployed system.

Reporting only the first understates the platform; reporting only the second
hides which component is doing the work. The gap between them is the value of
the rewrite, and it is the number that justifies spending a model call before
every search.

    venv/bin/python scripts/benchmarks/cross_lingual_retrieval.py

A verdict is decided on the **top hit only**, and the rank of the first on-topic
passage is reported alongside it. An earlier version asked merely whether an
expected term appeared anywhere in the top five, and it scored both
photosynthesis queries as successes: "chlorophyll" did appear -- at rank three,
beneath two chapters on the reflection and refraction of light. Retrieval that
ranks optics above biology has failed the student whatever sits below it.
"""

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Two topics across every supported Indian language, so language is the only
# variable that moves. The first is ordinary vocabulary; the second is a
# compound term built from morphemes meaning "light" and "joining" in most of
# these languages, which is the case Section V-C is about.
EYE = ["eye", "lens", "retina", "ciliary", "cornea"]
PHOTO = ["photosynthesis", "chlorophyll", "chloroplast"]

_CASES = [
    ("Hindi", "eye", "मानव नेत्र किसी वस्तु पर फोकस कैसे करता है?", EYE),
    ("Urdu", "eye", "انسانی آنکھ کسی چیز پر فوکس کیسے کرتی ہے؟", EYE),
    ("Marathi", "eye", "मानवी डोळा वस्तूवर फोकस कसा करतो?", EYE),
    ("Bengali", "eye", "মানুষের চোখ কীভাবে ফোকাস করে?", EYE),
    ("Tamil", "eye", "மனித கண் எவ்வாறு குவியப்படுத்துகிறது?", EYE),
    ("Telugu", "eye", "మానవ కన్ను ఎలా దృష్టి కేంద్రీకరిస్తుంది?", EYE),
    ("Gujarati", "eye", "માનવ આંખ કેવી રીતે ફોકસ કરે છે?", EYE),
    ("Kannada", "eye", "ಮಾನವ ಕಣ್ಣು ಹೇಗೆ ಕೇಂದ್ರೀಕರಿಸುತ್ತದೆ?", EYE),
    ("Malayalam", "eye", "മനുഷ്യന്റെ കണ്ണ് എങ്ങനെ ഫോക്കസ് ചെയ്യുന്നു?", EYE),
    ("Punjabi", "eye", "ਮਨੁੱਖੀ ਅੱਖ ਕਿਵੇਂ ਫੋਕਸ ਕਰਦੀ ਹੈ?", EYE),
    ("Odia", "eye", "ମାନବ ଆଖି କିପରି ଫୋକସ୍ କରେ?", EYE),
    ("Hindi", "photosynthesis", "प्रकाश संश्लेषण क्या है?", PHOTO),
    ("Urdu", "photosynthesis", "ضیائی تالیف کیا ہے؟", PHOTO),
    ("Marathi", "photosynthesis", "प्रकाशसंश्लेषण म्हणजे काय?", PHOTO),
    ("Bengali", "photosynthesis", "সালোকসংশ্লেষণ কী?", PHOTO),
    ("Tamil", "photosynthesis", "ஒளிச்சேர்க்கை என்றால் என்ன?", PHOTO),
    ("Telugu", "photosynthesis", "కిరణజన్య సంయోగక్రియ అంటే ఏమిటి?", PHOTO),
    ("Gujarati", "photosynthesis", "પ્રકાશસંશ્લેષણ શું છે?", PHOTO),
    ("Kannada", "photosynthesis", "ದ್ಯುತಿಸಂಶ್ಲೇಷಣೆ ಎಂದರೇನು?", PHOTO),
    ("Malayalam", "photosynthesis", "പ്രകാശസംശ്ലേഷണം എന്താണ്?", PHOTO),
    ("Punjabi", "photosynthesis", "ਪ੍ਰਕਾਸ਼ ਸੰਸ਼ਲੇਸ਼ਣ ਕੀ ਹੈ?", PHOTO),
    ("Odia", "photosynthesis", "ଆଲୋକ ସଂଶ୍ଳେଷଣ କ'ଣ?", PHOTO),
]

QUERIES = [
    {"language": lang, "topic": topic, "query": query, "expect": expect}
    for lang, topic, query, expect in _CASES
]

TOP_K = 5

SQL = text("""
    SELECT 1 - (e.embedding <=> CAST(:v AS vector)) AS sim,
           d.chunk_text
    FROM embeddings e
    JOIN document_chunks d ON d.id = e.chunk_id
    JOIN processed_content p ON p.id = d.content_id
    WHERE p.metadata->>'medium' = 'English'
    ORDER BY e.embedding <=> CAST(:v AS vector)
    LIMIT :k
""")


async def english_queries(questions: list[str]) -> list[str]:
    """
    The English search queries the tutor would actually embed.

    All of them in one event loop. Calling asyncio.run() per question closed
    the loop the HTTP client was bound to, so every second rewrite raised
    "Event loop is closed" and fell back to the original text -- silently,
    because the fallback is deliberate and only logs a warning. Half the
    rewrite arm was therefore measuring the raw arm.
    """
    from backend.api.routes.tutor import rewrite_for_search
    from backend.services.inference.unified_engine import (
        GenerationConfig,
        get_inference_engine,
    )

    engine = get_inference_engine()
    return [
        await rewrite_for_search(question, engine, GenerationConfig)
        for question in questions
    ]


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

    def retrieve(query_text: str):
        vector = embedder.encode_query(query_text).tolist()
        with engine.connect() as connection:
            return connection.execute(SQL, {"v": str(vector), "k": TOP_K}).all()

    def rank_in(hits, expect: list[str]) -> tuple[float | None, int | None]:
        """Top similarity, and the rank at which an on-topic passage first appears."""
        if not hits:
            return None, None
        rank = next(
            (
                i
                for i, hit in enumerate(hits, 1)
                if any(term.lower() in hit.chunk_text.lower() for term in expect)
            ),
            None,
        )
        return hits[0].sim, rank

    def first_match(query_text: str, expect: list[str]):
        return rank_in(retrieve(query_text), expect)

    def merged(a, b, expect: list[str]):
        """
        Both result sets pooled by best score per passage -- what merge_hits()
        in the tutor does. The two arms fail on different things, so pooling
        them is not an average of the two but a union of what each finds.
        """
        best: dict[str, object] = {}
        for hit in list(a) + list(b):
            key = hit.chunk_text[:80]
            if key not in best or hit.sim > best[key].sim:
                best[key] = hit
        pooled = sorted(best.values(), key=lambda h: h.sim, reverse=True)[:TOP_K]
        return rank_in(pooled, expect)

    def cell(sim, rank) -> str:
        if sim is None:
            return "no hits"
        if rank == 1:
            return f"{sim:.3f} correct"
        if rank:
            return f"{sim:.3f} rank {rank}"
        return f"{sim:.3f} miss"

    languages = {q["language"] for q in QUERIES}
    topics = {q["topic"] for q in QUERIES}
    print(f"corpus: {books} books, {chunks} indexed passages")
    print(f"{len(QUERIES)} queries, {len(languages)} languages, {len(topics)} topics\n")
    print(f"{'Language':<10} {'Topic':<15} {'raw':>15} {'rewrite':>15} {'both (shipped)':>16}")
    print("-" * 78)

    totals = {"raw": 0, "rewrite": 0, "both": 0}
    per_topic: dict[str, dict[str, int]] = {}

    rewrites = asyncio.run(english_queries([c["query"] for c in QUERIES]))
    unchanged = sum(1 for c, r in zip(QUERIES, rewrites) if r == c["query"])
    if unchanged:
        print(f"warning: {unchanged} rewrites returned the original text\n")

    for case, rewritten in zip(QUERIES, rewrites):
        raw_hits = retrieve(case["query"])
        new_hits = retrieve(rewritten)
        raw_sim, raw_rank = rank_in(raw_hits, case["expect"])
        new_sim, new_rank = rank_in(new_hits, case["expect"])
        both_sim, both_rank = merged(raw_hits, new_hits, case["expect"])

        bucket = per_topic.setdefault(
            case["topic"], {"raw": 0, "rewrite": 0, "both": 0, "n": 0}
        )
        bucket["n"] += 1
        for name, rank in (("raw", raw_rank), ("rewrite", new_rank), ("both", both_rank)):
            if rank == 1:
                totals[name] += 1
                bucket[name] += 1

        print(f"{case['language']:<10} {case['topic']:<15} "
              f"{cell(raw_sim, raw_rank):>15} {cell(new_sim, new_rank):>15} "
              f"{cell(both_sim, both_rank):>16}")

    n = len(QUERIES)
    print("\n" + "-" * 66)
    print(f"correct at rank 1:   raw {totals['raw']}/{n}   "
          f"rewrite {totals['rewrite']}/{n}   both {totals['both']}/{n}")
    for topic, b in sorted(per_topic.items()):
        print(f"   {topic:<16} raw {b['raw']}/{b['n']}   "
              f"rewrite {b['rewrite']}/{b['n']}   both {b['both']}/{b['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
