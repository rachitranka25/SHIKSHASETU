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
import json
import logging
import math
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Seven topics across every supported Indian language, so language remains the
# only variable that moves within a topic. Two of them were the original pair:
# the eye is ordinary vocabulary, and photosynthesis is a compound built from
# morphemes meaning "light" and "joining" in most of these languages, which is
# the case Section V-C is about. The other five were added to widen the base
# the retrieval numbers rest on, and were chosen to span subjects rather than
# to be easy: a mathematical result named after a person, a chemistry
# contrast, a geography process, a physics quantity, and a biology process.
#
# Every topic was checked against the English corpus before being included,
# and one candidate was dropped for having four matching passages, which would
# have measured the corpus rather than the retriever.
LANGUAGES = ["Hindi", "Urdu", "Marathi", "Bengali", "Tamil", "Telugu",
             "Gujarati", "Kannada", "Malayalam", "Punjabi", "Odia"]

TOPICS: dict[str, dict] = {
    "eye": {
        "expect": ["eye", "lens", "retina", "ciliary", "cornea"],
        "q": {
            "Hindi": "मानव नेत्र किसी वस्तु पर फोकस कैसे करता है?",
            "Urdu": "انسانی آنکھ کسی چیز پر فوکس کیسے کرتی ہے؟",
            "Marathi": "मानवी डोळा वस्तूवर फोकस कसा करतो?",
            "Bengali": "মানুষের চোখ কীভাবে ফোকাস করে?",
            "Tamil": "மனித கண் எவ்வாறு குவியப்படுத்துகிறது?",
            "Telugu": "మానవ కన్ను ఎలా దృష్టి కేంద్రీకరిస్తుంది?",
            "Gujarati": "માનવ આંખ કેવી રીતે ફોકસ કરે છે?",
            "Kannada": "ಮಾನವ ಕಣ್ಣು ಹೇಗೆ ಕೇಂದ್ರೀಕರಿಸುತ್ತದೆ?",
            "Malayalam": "മനുഷ്യന്റെ കണ്ണ് എങ്ങനെ ഫോക്കസ് ചെയ്യുന്നു?",
            "Punjabi": "ਮਨੁੱਖੀ ਅੱਖ ਕਿਵੇਂ ਫੋਕਸ ਕਰਦੀ ਹੈ?",
            "Odia": "ମାନବ ଆଖି କିପରି ଫୋକସ୍ କରେ?",
        },
    },
    "photosynthesis": {
        "expect": ["photosynthesis", "chlorophyll", "chloroplast"],
        "q": {
            "Hindi": "प्रकाश संश्लेषण क्या है?",
            "Urdu": "ضیائی تالیف کیا ہے؟",
            "Marathi": "प्रकाशसंश्लेषण म्हणजे काय?",
            "Bengali": "সালোকসংশ্লেষণ কী?",
            "Tamil": "ஒளிச்சேர்க்கை என்றால் என்ன?",
            "Telugu": "కిరణజన్య సంయోగక్రియ అంటే ఏమిటి?",
            "Gujarati": "પ્રકાશસંશ્લેષણ શું છે?",
            "Kannada": "ದ್ಯುತಿಸಂಶ್ಲೇಷಣೆ ಎಂದರೇನು?",
            "Malayalam": "പ്രകാശസംശ്ലേഷണം എന്താണ്?",
            "Punjabi": "ਪ੍ਰਕਾਸ਼ ਸੰਸ਼ਲੇਸ਼ਣ ਕੀ ਹੈ?",
            "Odia": "ଆଲୋକ ସଂଶ୍ଳେଷଣ କ'ଣ?",
        },
    },
    "pythagoras": {
        "expect": ["pythagoras", "hypotenuse"],
        "q": {
            "Hindi": "पाइथागोरस प्रमेय क्या है?",
            "Urdu": "فیثاغورث کا نظریہ کیا ہے؟",
            "Marathi": "पायथागोरसचे प्रमेय काय आहे?",
            "Bengali": "পিথাগোরাসের উপপাদ্য কী?",
            "Tamil": "பைதாகரஸ் தேற்றம் என்றால் என்ன?",
            "Telugu": "పైథాగరస్ సిద్ధాంతం అంటే ఏమిటి?",
            "Gujarati": "પાયથાગોરસનું પ્રમેય શું છે?",
            "Kannada": "ಪೈಥಾಗೋರಸ್ ಪ್ರಮೇಯ ಎಂದರೇನು?",
            "Malayalam": "പൈതഗോറസ് സിദ്ധാന്തം എന്താണ്?",
            "Punjabi": "ਪਾਇਥਾਗੋਰਸ ਦਾ ਪ੍ਰਮੇਯ ਕੀ ਹੈ?",
            "Odia": "ପାଇଥାଗୋରସ୍ ଉପପାଦ୍ୟ କ'ଣ?",
        },
    },
    "acids_bases": {
        "expect": ["litmus", "acidic", "alkali", "acid"],
        "q": {
            "Hindi": "अम्ल और क्षार में क्या अंतर है?",
            "Urdu": "تیزاب اور الکلی میں کیا فرق ہے؟",
            "Marathi": "आम्ल आणि आम्लारी यांच्यात काय फरक आहे?",
            "Bengali": "অ্যাসিড ও ক্ষারের মধ্যে পার্থক্য কী?",
            "Tamil": "அமிலத்திற்கும் காரத்திற்கும் என்ன வேறுபாடு?",
            "Telugu": "ఆమ్లం మరియు క్షారానికి మధ్య తేడా ఏమిటి?",
            "Gujarati": "એસિડ અને બેઝ વચ્ચે શું તફાવત છે?",
            "Kannada": "ಆಮ್ಲ ಮತ್ತು ಪ್ರತ್ಯಾಮ್ಲದ ನಡುವಿನ ವ್ಯತ್ಯಾಸವೇನು?",
            "Malayalam": "ആസിഡും ബേസും തമ്മിലുള്ള വ്യത്യാസം എന്താണ്?",
            "Punjabi": "ਤੇਜ਼ਾਬ ਅਤੇ ਖਾਰ ਵਿੱਚ ਕੀ ਫਰਕ ਹੈ?",
            "Odia": "ଅମ୍ଳ ଏବଂ କ୍ଷାର ମଧ୍ୟରେ ପାର୍ଥକ୍ୟ କ'ଣ?",
        },
    },
    "water_cycle": {
        "expect": ["evaporation", "condensation", "precipitation", "water cycle"],
        "q": {
            "Hindi": "जल चक्र क्या है?",
            "Urdu": "پانی کا چکر کیا ہے؟",
            "Marathi": "जलचक्र म्हणजे काय?",
            "Bengali": "জলচক্র কী?",
            "Tamil": "நீர்ச்சுழற்சி என்றால் என்ன?",
            "Telugu": "జలచక్రం అంటే ఏమిటి?",
            "Gujarati": "જળચક્ર શું છે?",
            "Kannada": "ಜಲಚಕ್ರ ಎಂದರೇನು?",
            "Malayalam": "ജലചക്രം എന്താണ്?",
            "Punjabi": "ਪਾਣੀ ਦਾ ਚੱਕਰ ਕੀ ਹੈ?",
            "Odia": "ଜଳଚକ୍ର କ'ଣ?",
        },
    },
    "electric_current": {
        "expect": ["electric current", "ammeter", "ampere", "resistor"],
        "q": {
            "Hindi": "विद्युत धारा क्या है और इसे कैसे मापा जाता है?",
            "Urdu": "برقی رو کیا ہے اور اسے کیسے ناپا جاتا ہے؟",
            "Marathi": "विद्युत प्रवाह म्हणजे काय आणि तो कसा मोजतात?",
            "Bengali": "তড়িৎ প্রবাহ কী এবং এটি কীভাবে মাপা হয়?",
            "Tamil": "மின்னோட்டம் என்றால் என்ன, அது எப்படி அளக்கப்படுகிறது?",
            "Telugu": "విద్యుత్ ప్రవాహం అంటే ఏమిటి, దానిని ఎలా కొలుస్తారు?",
            "Gujarati": "વિદ્યુત પ્રવાહ શું છે અને તે કેવી રીતે માપવામાં આવે છે?",
            "Kannada": "ವಿದ್ಯುತ್ ಪ್ರವಾಹ ಎಂದರೇನು ಮತ್ತು ಅದನ್ನು ಹೇಗೆ ಅಳೆಯುತ್ತಾರೆ?",
            "Malayalam": "വൈദ്യുത പ്രവാഹം എന്താണ്, അത് എങ്ങനെ അളക്കുന്നു?",
            "Punjabi": "ਬਿਜਲਈ ਕਰੰਟ ਕੀ ਹੈ ਅਤੇ ਇਸਨੂੰ ਕਿਵੇਂ ਮਾਪਿਆ ਜਾਂਦਾ ਹੈ?",
            "Odia": "ବିଦ୍ୟୁତ୍ ପ୍ରବାହ କ'ଣ ଏବଂ ଏହା କିପରି ମପାଯାଏ?",
        },
    },
    "digestion": {
        "expect": ["digestion", "digestive", "oesophagus", "villi"],
        "q": {
            "Hindi": "मानव शरीर में भोजन का पाचन कैसे होता है?",
            "Urdu": "انسانی جسم میں کھانا کیسے ہضم ہوتا ہے؟",
            "Marathi": "मानवी शरीरात अन्नाचे पचन कसे होते?",
            "Bengali": "মানবদেহে খাদ্য কীভাবে হজম হয়?",
            "Tamil": "மனித உடலில் உணவு எவ்வாறு செரிக்கப்படுகிறது?",
            "Telugu": "మానవ శరీరంలో ఆహారం ఎలా జీర్ణమవుతుంది?",
            "Gujarati": "માનવ શરીરમાં ખોરાકનું પાચન કેવી રીતે થાય છે?",
            "Kannada": "ಮಾನವ ದೇಹದಲ್ಲಿ ಆಹಾರ ಹೇಗೆ ಜೀರ್ಣವಾಗುತ್ತದೆ?",
            "Malayalam": "മനുഷ്യ ശരീരത്തിൽ ഭക്ഷണം എങ്ങനെ ദഹിക്കുന്നു?",
            "Punjabi": "ਮਨੁੱਖੀ ਸਰੀਰ ਵਿੱਚ ਭੋਜਨ ਕਿਵੇਂ ਪਚਦਾ ਹੈ?",
            "Odia": "ମାନବ ଶରୀରରେ ଖାଦ୍ୟ କିପରି ହଜମ ହୁଏ?",
        },
    },
}

QUERIES = [
    {"language": lang, "topic": topic, "query": spec["q"][lang], "expect": spec["expect"]}
    for topic, spec in TOPICS.items()
    for lang in LANGUAGES
]

TOP_K = 5

# Spacing between hosted rewrite calls, and how many times a rate-limited
# question is retried before the run is abandoned. Eight of the first
# queries issued back to back came back HTTP 429.
PACE_SECONDS = 4.0
MAX_ATTEMPTS = 4

# Lexical baseline. Postgres full-text search with ts_rank is not BM25 exactly
# -- it is a length-normalised tf-idf variant -- but it is the same family, it
# needs no extra index or dependency, and it answers the question a reviewer
# asks first: how much of this is the embedding model earning its keep?
#
# Its expected behaviour on a Devanagari query against an English corpus is to
# return nothing at all, which is the point of including it.
BM25_SQL = text("""
    SELECT ts_rank(to_tsvector('english', d.chunk_text),
                   plainto_tsquery('english', :q)) AS sim,
           d.chunk_text
    FROM document_chunks d
    JOIN processed_content p ON p.id = d.content_id
    WHERE p.metadata->>'medium' = 'English'
      AND to_tsvector('english', d.chunk_text) @@ plainto_tsquery('english', :q)
    ORDER BY sim DESC
    LIMIT :k
""")

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


class _FallbackWatch(logging.Handler):
    """
    Notice when the engine quietly stopped using the hosted model.

    Falling back to the on-device model is correct in production: a student
    should get a degraded answer rather than an error. In a benchmark it is
    the opposite of what is wanted, because the rewrite arm would then be
    measuring two different models depending on how fast the queries were
    issued, and nothing in the output would say which.
    """

    def __init__(self) -> None:
        super().__init__()
        self.fell_back = False

    def emit(self, record: logging.LogRecord) -> None:
        if "using local model" in record.getMessage():
            self.fell_back = True


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """
    Point estimate and 95% Wilson score interval for k successes in n trials.

    Wilson rather than the normal approximation because the lexical arm scores
    zero, where the normal approximation collapses to a zero-width interval and
    would assert certainty from the one result that most needs an interval.
    """
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


async def english_queries(questions: list[str]) -> list[str]:
    """
    The English search queries the tutor would actually embed.

    All of them in one event loop. Calling asyncio.run() per question closed
    the loop the HTTP client was bound to, so every second rewrite raised
    "Event loop is closed" and fell back to the original text -- silently,
    because the fallback is deliberate and only logs a warning. Half the
    rewrite arm was therefore measuring the raw arm.

    Paced, for a second reason with the same shape. Issued back to back, this
    many rewrites trip the hosted endpoint's rate limit; it answers HTTP 429,
    the engine degrades to the local model exactly as designed, and the arm
    silently becomes a mixture of two models. So the calls are spaced, a 429
    backs off and retries rather than being accepted, and a question that
    still cannot be served by the hosted model stops the run instead of
    entering the results.
    """
    from backend.api.routes.tutor import rewrite_for_search
    from backend.services.inference.unified_engine import (
        GenerationConfig,
        get_inference_engine,
    )

    # Rewrites are paced to stay under the hosted rate limit, which makes them
    # the slow part of every run that needs them. They are cached by question
    # text so a second benchmark over the same queries does not pay for them
    # again, and so a run that has to be repeated is not repeating the part
    # that was already correct. Delete the file to force fresh rewrites.
    cache_path = Path(__file__).resolve().parents[2] / ".rewrite_cache.json"
    cache: dict[str, str] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())
        have = sum(1 for q in questions if q in cache)
        print(f"  rewrite cache: {have}/{len(questions)} already present", flush=True)

    engine = get_inference_engine()
    watch = _FallbackWatch()
    logging.getLogger("backend.services.inference.unified_engine").addHandler(watch)

    out: list[str] = []
    for i, question in enumerate(questions, 1):
        if question in cache:
            out.append(cache[question])
            continue
        for attempt in range(MAX_ATTEMPTS):
            watch.fell_back = False
            rewritten = await rewrite_for_search(question, engine, GenerationConfig)
            if not watch.fell_back:
                break
            wait = PACE_SECONDS * (2 ** (attempt + 1))
            print(f"  [{i}/{len(questions)}] hosted model unavailable, "
                  f"waiting {wait:.0f}s (attempt {attempt + 1}/{MAX_ATTEMPTS})",
                  flush=True)
            await asyncio.sleep(wait)
        else:
            raise SystemExit(
                f"query {i} could not be rewritten by the hosted model after "
                f"{MAX_ATTEMPTS} attempts. Reporting a rewrite arm that is part "
                f"hosted and part on-device would not measure anything, so this "
                f"run is abandoned rather than completed."
            )
        out.append(rewritten)
        cache[question] = rewritten
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
        if i % 10 == 0:
            print(f"  rewritten {i}/{len(questions)}", flush=True)
        await asyncio.sleep(PACE_SECONDS)
    return out


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

    def lexical(query_text: str):
        with engine.connect() as connection:
            return connection.execute(
                BM25_SQL, {"q": query_text, "k": TOP_K}
            ).all()

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
    print(f"{'Language':<10} {'Topic':<14} {'BM25':>13} {'BM25+rw':>13} "
          f"{'dense':>13} {'dense+rw':>13} {'pooled':>13}")
    print("-" * 96)

    totals = {"bm25": 0, "bm25_rw": 0, "raw": 0, "rewrite": 0, "both": 0}
    per_topic: dict[str, dict[str, int]] = {}
    per_language: dict[str, list[int | None]] = {}

    rewrites = asyncio.run(english_queries([c["query"] for c in QUERIES]))
    unchanged = sum(1 for c, r in zip(QUERIES, rewrites) if r == c["query"])
    if unchanged:
        print(f"warning: {unchanged} rewrites returned the original text\n")

    for case, rewritten in zip(QUERIES, rewrites):
        bm_sim, bm_rank = rank_in(lexical(case["query"]), case["expect"])
        bmw_sim, bmw_rank = rank_in(lexical(rewritten), case["expect"])
        raw_hits = retrieve(case["query"])
        new_hits = retrieve(rewritten)
        raw_sim, raw_rank = rank_in(raw_hits, case["expect"])
        new_sim, new_rank = rank_in(new_hits, case["expect"])
        both_sim, both_rank = merged(raw_hits, new_hits, case["expect"])

        per_language.setdefault(case["language"], []).append(both_rank)

        bucket = per_topic.setdefault(
            case["topic"],
            {"bm25": 0, "bm25_rw": 0, "raw": 0, "rewrite": 0, "both": 0, "n": 0},
        )
        bucket["n"] += 1
        for name, rank in (
            ("bm25", bm_rank), ("bm25_rw", bmw_rank),
            ("raw", raw_rank), ("rewrite", new_rank), ("both", both_rank),
        ):
            if rank == 1:
                totals[name] += 1
                bucket[name] += 1

        print(f"{case['language']:<10} {case['topic']:<14} "
              f"{cell(bm_sim, bm_rank):>13} {cell(bmw_sim, bmw_rank):>13} "
              f"{cell(raw_sim, raw_rank):>13} {cell(new_sim, new_rank):>13} "
              f"{cell(both_sim, both_rank):>13}")

    n = len(QUERIES)
    print("\n" + "-" * 66)
    order = [("BM25", "bm25"), ("BM25+rewrite", "bm25_rw"), ("dense", "raw"),
             ("dense+rewrite", "rewrite"), ("pooled (deployed)", "both")]
    print("correct at rank 1, out of", n)
    for label, key in order:
        print(f"   {label:<20} {totals[key]:>3}/{n}   ({100*totals[key]/n:.0f}%)")

    # The figure plots a proportion with a 95% Wilson score interval, which is
    # the right interval at this sample size and for proportions at 0 -- the
    # normal approximation gives a zero-width interval for the lexical arm,
    # which is exactly the arm the paper draws a conclusion about. Emitted in
    # the coordinate form the figure consumes, so the numbers reach the paper
    # without being retyped.
    print("\n   95% Wilson score intervals, as figure coordinates:")
    for label, key in order:
        point, lo, hi = wilson(totals[key], n)
        print(f"   ({point:.3f},{label:<18}) +- ({point - lo:.3f},{hi - point:.3f})")
    print("\n   by topic:")
    for topic, b in sorted(per_topic.items()):
        cells = "  ".join(f"{key}={b[key]}/{b['n']}" for _, key in order)
        print(f"   {topic:<16} {cells}")

    # Per-language mean reciprocal rank for the deployed configuration, which
    # is what the per-language figure plots. Previously it had to be read back
    # out of the printed table by hand, which is fine for two topics per
    # language and not fine for seven.
    print("\n   deployed configuration, mean reciprocal rank by language:")
    for lang in LANGUAGES:
        ranks = per_language.get(lang, [])
        mrr = sum(1 / r for r in ranks if r) / len(ranks) if ranks else 0.0
        firsts = sum(1 for r in ranks if r == 1)
        print(f"   {lang:<12} MRR {mrr:.3f}   rank-1 {firsts}/{len(ranks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
