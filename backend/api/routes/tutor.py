"""
Tutor endpoint: ask in any language, get taught in the one you chose.

    POST /api/v2/tutor/explain

Three things this does that plain retrieval does not:

1. Finds the class for you. A student who does not know which year covers
   Pythagoras should not have to. With no class given, the class is read off
   the retrieved material, then the search is rerun scoped to it — otherwise a
   class 7 question gets answered from a class 10 chapter whenever the wording
   lines up better there.

2. Separates the language you ask in from the language you want back. These
   are genuinely independent: a student reading a Hindi textbook may type the
   question in Hinglish and want the explanation in English. Retrieval is
   already cross-lingual through BGE-M3, so the question's language needs no
   declaration; the answer's does.

3. Grounds the explanation in the retrieved NCERT text and cites the chapters
   it used, rather than letting the model answer from memory.

ON DIAGRAMS: NCERT's own figures are images inside the textbook PDFs, and the
ingestion extracts text only — they are not in the corpus and cannot be served.
An illustration returned here is drawn for the explanation by an image model,
carries no text of its own, and says so in `diagram_note`. See
backend/services/illustration.py for why a language model writing SVG was
abandoned.
"""

import logging
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ...database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# How the answer language is described to the model. Hinglish is not a locale,
# so it needs spelling out, and a bare language name produces Devanagari.
ANSWER_LANGUAGES: dict[str, str] = {
    "English": "English",
    "Hindi": "Hindi, written in Devanagari script",
    "Hinglish": (
        "Hinglish — Hindi written in Roman/Latin script, the way Indian students "
        "text each other. Keep technical terms in English"
    ),
    "Urdu": "Urdu, written in the Perso-Arabic script",
    "Marathi": "Marathi, written in Devanagari script",
    "Bengali": "Bengali, written in the Bengali script",
    "Tamil": "Tamil, written in the Tamil script",
    "Telugu": "Telugu, written in the Telugu script",
    "Gujarati": "Gujarati, written in the Gujarati script",
    "Kannada": "Kannada, written in the Kannada script",
    "Malayalam": "Malayalam, written in the Malayalam script",
    "Punjabi": "Punjabi, written in the Gurmukhi script",
    "Odia": "Odia, written in the Odia script",
}

AnswerLanguage = Literal[
    "English", "Hindi", "Hinglish", "Urdu", "Marathi", "Bengali",
    "Tamil", "Telugu", "Gujarati", "Kannada", "Malayalam", "Punjabi", "Odia",
]

# Retrieval widths. The first pass is wide because it also has to decide which
# class the topic belongs to; the second is narrow because it only has to
# supply context for one answer.
DISCOVERY_HITS = 12
CONTEXT_HITS = 6
CONTEXT_CHARS = 1100

# Below this the corpus simply does not cover the question, and answering from
# the model's own memory would defeat the point of grounding it.
MIN_USEFUL_SIMILARITY = 0.35

# Which textbook editions may be taught from.
#
# NCERT publishes the same curriculum in English, Hindi and Urdu, so every
# chapter exists three times in the corpus. Retrieval is cross-lingual and does
# not care, which had two consequences: an English question was being answered
# from the Urdu edition, and the six context passages could be the same chapter
# repeated in three scripts, crowding out material that would have added
# something.
#
# Restricting the source to English and Hindi fixes both. It is not a judgement
# about the languages — the Urdu editions are ingested and searchable through
# the library — but a student is taught from an edition they can check for
# themselves, and the model is not asked to translate out of a script it
# handles least well.
#
# The answer language is unaffected: an English source still produces a Tamil
# or Hinglish explanation if that is what was asked for.
TEACHING_MEDIA = ("English", "Hindi")

# Cosine similarity, answer against the passages it was given, below which the
# answer is treated as having drifted. Calibrated against four hand-checked
# answers over the Hindi reader corpus:
#
#     0.701  correct  Rahim's couplets, from the chapter that contains them
#     0.668  correct  the Himalaya poem, quoting its own lines back
#     0.583  correct  Baba Bharti and his horse Sultan
#     0.489  wrong    a word-by-word guess at a couplet it never retrieved
#                     ("Don't give a light rope to Rahiman's children")
#
# Correct answers sat at 0.58-0.70 and the invented one at 0.49, so the
# boundary goes between them rather than at a round number. Four points is a
# small sample and this is a starting value, not a validated one.
GROUNDING_MIN = 0.55


class ExplainRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    grade: int | None = Field(default=None, ge=1, le=12, description="Omit to detect")
    answer_language: AnswerLanguage = "English"
    diagram: bool = Field(default=False, description="Attempt an illustrative drawing")
    reading_support: bool = Field(
        default=False,
        description=(
            "Write for a reader who finds decoding hard: short sentences, common "
            "words, one idea at a time. Returns readability measurements and "
            "syllable or akshara breakdowns for the difficult words."
        ),
    )


class Source(BaseModel):
    grade: int | None
    subject: str | None
    chapter: int | None
    url: str | None
    similarity: float


class ReadabilityReport(BaseModel):
    """
    Decoding load of the source material against the adapted answer.

    Both are reported so the adaptation can be checked rather than trusted. The
    units are the script's own — syllables for Latin, aksharas for Devanagari
    and the other Brahmic scripts — and a grade estimate appears only for
    English, where Flesch-Kincaid is actually defined.
    """

    source: dict
    answer: dict
    segmented_words: dict[str, list[str]]


class ExplainResponse(BaseModel):
    answer: str
    answer_language: str
    grade: int | None
    grade_was_detected: bool
    sources: list[Source]
    grounding: float = Field(
        description=(
            "Cosine similarity between the answer and the passages it was "
            "written from. Reported so a low score is visible rather than "
            "silent: a fluent answer about the wrong thing looks exactly like "
            "a correct one."
        ),
    )
    diagram: str | None = None
    diagram_note: str | None = None
    readability: ReadabilityReport | None = None


REWRITE_PROMPT = """Rewrite this student's question as a short English search query for a textbook index.

QUESTION: {question}

Rules:
- Output only the query. No quotes, no explanation, no preamble.
- Keep the subject terms; drop greetings, filler and politeness.
- If the question is not in English, translate it.
- Eight words at most."""


async def rewrite_for_search(question: str, engine, config_cls) -> str:
    """
    Normalise a question into an English search query before embedding it.

    Necessary because BGE-M3's cross-lingual strength does not extend to
    romanised Hindi. Measured against this corpus, same question, top-5 hits:

        English        class 10 at 0.607, 0.596, 0.593 ...
        Devanagari     class 10 at 0.564, 0.557, 0.552 ...
        Hinglish       class  1 at 0.520, 0.506, 0.500 ...

    Devanagari retrieves correctly; Roman-script Hindi drifts onto whatever
    matches on surface form, which here meant class 1 picture books for a
    class 10 chemistry question. Since Hinglish is how a great many Indian
    students actually type, that had to be fixed rather than documented.

    Rewriting runs for every question, not only ones that look non-English:
    deciding what "looks Hinglish" is guesswork, the call is under a second
    against the model already configured, and turning a conversational
    question into its subject terms helps English queries too.

    Falls back to the original question if the rewrite fails or looks wrong —
    a degraded search beats no search.
    """
    try:
        rewritten = await engine.generate(
            REWRITE_PROMPT.format(question=question),
            config_cls(max_tokens=40, temperature=0.0, use_cache=True),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Query rewrite failed, using the original: %s", exc)
        return question

    # .strip('"') only removes quotes at the ends. The model likes to quote the
    # part it is unsure how to translate, which leaves a lone '"' mid-string:
    #   Meaning of "Rahiman dekhi baden ko, laghu na deejiye daari
    cleaned = " ".join(rewritten.replace('"', " ").split()).strip()

    # A model that ignored the instructions and wrote a paragraph, or returned
    # nothing, is worse than the question the student typed.
    if not cleaned or len(cleaned) > 160:
        return question

    return cleaned


def _retrieve(db: Session, vector: list[float], grade: int | None, limit: int) -> list:
    """Nearest passages, optionally restricted to one class."""
    params: dict = {
        "vector": "[" + ",".join(str(x) for x in vector) + "]",
        "limit": limit,
        "chars": CONTEXT_CHARS,
        "media": list(TEACHING_MEDIA),
    }
    grade_filter = ""
    if grade is not None:
        grade_filter = "AND pc.grade_level = :grade"
        params["grade"] = grade

    # CAST(:vector AS vector), not :vector::vector — text() truncates a bind
    # parameter name that is followed by a colon.
    return db.execute(
        sql_text(
            f"""
            SELECT
                left(dc.chunk_text, :chars) AS passage,
                1 - (e.embedding <=> CAST(:vector AS vector)) AS similarity,
                pc.grade_level                   AS grade,
                pc.subject                       AS subject,
                (pc.metadata ->> 'chapter')::int AS chapter,
                pc.metadata ->> 'url'            AS url
            FROM embeddings e
            JOIN document_chunks dc   ON dc.id = e.chunk_id
            JOIN processed_content pc ON pc.id = dc.content_id
            WHERE pc.metadata ->> 'source' = 'NCERT'
              AND pc.metadata ->> 'medium' = ANY(:media) {grade_filter}
            ORDER BY e.embedding <=> CAST(:vector AS vector)
            LIMIT :limit
            """
        ),
        params,
    ).fetchall()


# How many of a class's best passages are averaged when deciding which class a
# topic belongs to.
GRADE_EVIDENCE_DEPTH = 3


def merge_hits(results: list[list], limit: int) -> list:
    """
    One ranked list from several searches, each passage scored by its best hit.

    Taking the maximum rather than the sum matters for grade detection: a
    passage found by both queries is not thereby better evidence than one found
    strongly by a single query, and summing would let the overlap between two
    phrasings of the same question decide the class.
    """
    best: dict[tuple, object] = {}
    for rows in results:
        for row in rows:
            key = (row.grade, row.subject, row.chapter, row.passage[:80])
            if key not in best or row.similarity > best[key].similarity:
                best[key] = row

    return sorted(best.values(), key=lambda r: r.similarity, reverse=True)[:limit]


def detect_grade(rows) -> int | None:
    """
    Work out which class a topic belongs to from the passages that matched.

    Scored on the sum of each class's three strongest passages, which resists
    both ways of getting this wrong.

    Summing everything lets a class win on volume: a chemistry question matched
    eight weak passages in class 1 picture books and three strong ones in the
    class 10 chapter that teaches it, and class 1 won.

    Taking the single best hit has the opposite failure, and so does averaging:
    a class with one passage at 0.66 beats a class with three at 0.60-0.62,
    because its mean is that lone passage. One high match can be a passing
    mention that happens to share wording; three consistent ones mean the topic
    is taught there.

    Capping at three bounds what volume can contribute while still rewarding
    corroboration.
    """
    scores = grade_scores(rows)
    return max(scores, key=scores.get) if scores else None


def grade_scores(rows) -> dict[int, float]:
    """Each class's evidence, as the sum of its three strongest passages."""
    by_grade: dict[int, list[float]] = {}
    for row in rows:
        if row.grade is None or row.similarity < MIN_USEFUL_SIMILARITY:
            continue
        by_grade.setdefault(row.grade, []).append(float(row.similarity))

    return {
        grade: sum(sorted(hits, reverse=True)[:GRADE_EVIDENCE_DEPTH])
        for grade, hits in by_grade.items()
    }


def vote_grade(per_query_rows: list[list]) -> int | None:
    """
    Let each query propose a class, then pick between the proposals.

    Merging two queries' hits into one ranked list does not work, because
    similarity is only comparable within a single query. Asked "Rahiman dekhi
    baden ko, laghu na deejiye daari", the student's own wording ranked class 6
    Malhar -- which contains that couplet -- in every one of its twelve hits,
    while the English rewrite put a class 3 reader on top at 0.513. Pooled and
    sorted, the rewrite's numerically larger scores buried the correct class.

    So each query is scored on its own scale and proposes a winner, weighted by
    how decisive that proposal is: the share of the evidence its winner holds,
    times the absolute evidence behind it. A query that ranks one class
    unanimously speaks with more authority than one that leads by 2%, and a
    class proposed by both queries beats a class proposed by one.
    """
    proposals: dict[int, list[float]] = {}
    for rows in per_query_rows:
        scores = grade_scores(rows)
        if not scores:
            continue

        ranked = sorted(scores.values(), reverse=True)
        top = ranked[0]
        runner_up = ranked[1] if len(ranked) > 1 else 0.0
        # Lead as a fraction of the winner's own score, so it does not depend on
        # the scale of this query's similarities, times the evidence itself, so
        # that a decisive vote on thin evidence cannot outrank a solid one.
        authority = (top - runner_up) / top * top if top else 0.0
        proposals.setdefault(max(scores, key=scores.get), []).append(authority)

    if not proposals:
        return None

    return max(proposals, key=lambda g: (len(proposals[g]), max(proposals[g])))


# Written for a reader whose decoding is effortful, not for a younger reader.
# The distinction matters: a dyslexic class 10 student needs the class 10 idea
# delivered in sentences that cost less to read, not a class 3 explanation.
READING_SUPPORT_RULES = """
- This student finds reading effortful. Do not simplify the idea — simplify the reading.
- One idea per sentence. Aim for twelve words a sentence, never more than eighteen.
- Prefer short, everyday words. When a technical term is needed, use it, then explain it in a sentence of its own.
- Active voice. Say who does what.
- No nested clauses, no semicolons, no parenthetical asides.
- Put a blank line between steps so the eye can find its place again.
- Keep every fact and every technical term the curriculum requires. This is the same lesson, not a smaller one."""


def grounding_score(answer: str, rows, embedder) -> float:
    """
    How close the answer stays to the passages it was given, 0 to 1.

    Lexical overlap cannot measure this: the whole point of the platform is that
    a Devanagari passage produces an English answer, so they share almost no
    tokens. BGE-M3 is cross-lingual, which makes the cosine similarity between
    the answer and its context a usable signal in exactly the case that matters.

    It catches the failure that the prompt does not. Asked about Baba Bharti,
    the model retrieved the right chapter -- the story of his horse Sultan --
    and then wrote that he collects herbs and nurses a wounded bird. Correct
    class, correct chapter, correct answer language, invented content. Nothing
    in the response distinguished it from a good answer.
    """
    context = "\n\n".join(row.passage for row in rows)
    if not context.strip() or not answer.strip():
        return 0.0

    import numpy as np

    vectors = embedder.encode([answer[:4000], context[:4000]])
    a, b = np.asarray(vectors[0]), np.asarray(vectors[1])
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0.0:
        return 0.0

    return float(np.dot(a, b) / denominator)


GROUNDING_PROMPT_SUFFIX = """

The previous attempt described things that are not in the material above. Use
only what is written there. Name only the people, places and objects the
material names. If the material does not answer part of the question, say that
plainly."""


def build_prompt(
    question: str, rows, grade: int | None, language: str, reading_support: bool = False
) -> str:
    """Assemble the grounded teaching prompt."""
    context = "\n\n".join(
        f"[From the Class {row.grade} {row.subject} textbook, chapter {row.chapter}]\n{row.passage}"
        for row in rows
    )
    audience = f"a Class {grade} student" if grade else "a school student"
    support = READING_SUPPORT_RULES if reading_support else ""

    return f"""You are a patient Indian school teacher. Teach {audience} using only the NCERT textbook material below.

NCERT MATERIAL
{context}

STUDENT'S QUESTION
{question}

HOW TO ANSWER
- Write the entire answer in {ANSWER_LANGUAGES[language]}. This is required regardless of the language the question was asked in.
- Use only the material above. Every fact, name, place and number in your answer must appear in it. If it does not cover part of the question, say so plainly rather than filling the gap from memory.
- Teach the concept: what it means, why it is true, and a worked example.
- Pitch it at {audience} — simple sentences, familiar examples from Indian life.
- Keep mathematical notation and formulae exact.
- No preamble. Begin with the explanation.{support}"""


SIMPLIFY_PROMPT = """Rewrite this explanation so it is easier to decode. Keep every fact.

EXPLANATION
{answer}

Rules:
- Write in {language}. Do not change the language.
- Every sentence under fourteen words. Split the long ones.
- Replace long words with short everyday ones — except technical terms the curriculum requires. Keep those, and explain each in its own short sentence.
- Active voice. No semicolons, no nested clauses, no asides in brackets.
- Leave a blank line between steps.
- Same facts, same terms, same worked example. Only the sentences change.
- Output only the rewritten explanation."""

# Targets for the rewrite. Twelve to fourteen words a sentence is where
# readability guidance for struggling readers converges; the unit figure stands
# in for word length in whichever script is being read.
TARGET_WORDS_PER_SENTENCE = 14.0
TARGET_UNITS_PER_WORD = 2.0


def reading_load(metrics) -> float:
    """
    One number for decoding difficulty, comparable across scripts.

    Sentence length and word length both drive effort and can be traded against
    each other, so a scalar is what a rewrite can actually be judged against.
    Each term is normalised by its target, so neither dominates merely because
    its unit is larger.
    """
    return (
        metrics.words_per_sentence / TARGET_WORDS_PER_SENTENCE
        + metrics.units_per_word / TARGET_UNITS_PER_WORD
    )


@router.post("/tutor/explain", response_model=ExplainResponse, tags=["tutor"])
async def explain(request: ExplainRequest, db: Session = Depends(get_db)) -> ExplainResponse:
    """
    Teach a topic from the NCERT corpus, in the requested language.

    The class may be omitted, in which case it is detected from the material
    that matches and the search is rerun scoped to it.
    """
    from ...services.inference.unified_engine import (
        GenerationConfig,
        get_inference_engine,
    )
    from ...services.rag import get_embedder

    engine = get_inference_engine()

    # Search with the student's own wording *and* its English rewrite. The
    # rewrite alone used to replace the question, which made every rewrite
    # failure a retrieval failure: asked "Malhar mein Rahim ke dohe kya sikhate
    # hain?", the model wrote "Rahman's couplets" -- a different poet -- and the
    # search left class 6 Malhar, which contains those exact couplets, for a
    # class 3 English reader. The raw question had ranked Malhar in all twelve
    # of its top hits.
    #
    # Neither form is reliable on its own. Romanised Hindi drifts onto surface
    # form (a class 10 chemistry question landing on class 1 picture books);
    # the rewrite mistranslates proper nouns and is not deterministic even at
    # temperature 0. Searching both and keeping each passage's best score costs
    # one extra embedding call and removes the single point of failure.
    search_query = await rewrite_for_search(request.question, engine, GenerationConfig)
    queries = [request.question]
    if search_query != request.question:
        logger.info("Search rewrite: %r -> %r", request.question[:60], search_query)
        queries.append(search_query)

    try:
        embedder = get_embedder()
        vectors = [embedder.encode_query(q).tolist() for q in queries]
    except Exception as exc:
        logger.error("Query embedding failed: %s", exc)
        raise HTTPException(
            status_code=503, detail="The embedding model is unavailable."
        ) from exc

    def per_query(grade: int | None, limit: int) -> list[list]:
        return [_retrieve(db, vector, grade, limit) for vector in vectors]

    grade = request.grade
    detected = False

    if grade is None:
        discovery = per_query(None, DISCOVERY_HITS)
        grade = vote_grade(discovery)
        detected = grade is not None
        # Once the class is fixed, both queries are searching the same small set
        # of passages, so pooling them by score is safe and picks up whatever
        # either phrasing found.
        rows = (
            merge_hits(per_query(grade, CONTEXT_HITS), CONTEXT_HITS)
            if grade
            else merge_hits(discovery, CONTEXT_HITS)
        )
    else:
        rows = merge_hits(per_query(grade, CONTEXT_HITS), CONTEXT_HITS)

    usable = [row for row in rows if row.similarity >= MIN_USEFUL_SIMILARITY]
    if not usable:
        raise HTTPException(
            status_code=404,
            detail=(
                "The curriculum library has nothing on this yet. It is still being "
                "ingested — try another topic, or a different class."
            ),
        )

    prompt = build_prompt(
        request.question,
        usable,
        grade,
        request.answer_language,
        request.reading_support,
    )

    async def generate(text_prompt: str) -> str:
        return await engine.generate(
            text_prompt,
            GenerationConfig(max_tokens=1200, temperature=0.3, use_cache=False),
        )

    try:
        answer = await generate(prompt)
        grounding = grounding_score(answer, usable, embedder)

        # One retry, with the drift named. Retrying is worth a second call
        # because the failure is not a refusal -- the model had the right
        # passages and wrote around them, and telling it so is usually enough.
        if grounding < GROUNDING_MIN:
            logger.warning(
                "Answer drifted from its sources (grounding %.3f < %.2f), retrying",
                grounding, GROUNDING_MIN,
            )
            retried = await generate(prompt + GROUNDING_PROMPT_SUFFIX)
            retried_grounding = grounding_score(retried, usable, embedder)
            if retried_grounding > grounding:
                answer, grounding = retried, retried_grounding
    except Exception as exc:
        logger.error("Explanation generation failed: %s", exc)
        raise HTTPException(
            status_code=503, detail="The language model is unavailable."
        ) from exc

    diagram = None
    diagram_note = None
    if request.diagram:
        # An image model, not a language model writing SVG. Asking a text model
        # for SVG produced a rectangle with four floating words; the 70B took
        # 145 seconds to do it worse than the 8B did in 8. See
        # backend/services/illustration.py.
        # Geometry first. An image model draws scenes well and constructions
        # badly — asked for Pythagoras it produced three decorative triangles.
        # A language model writing SVG does no better: the coordinates have to
        # be computed. The standard figures are therefore drawn by hand, and
        # everything else falls through to the image model.
        from ...services.geometry_diagrams import render as render_geometry

        drawn = render_geometry(request.question, answer)
        if drawn is not None:
            svg, template_name = drawn
            diagram = "data:image/svg+xml;utf8," + quote(svg)
            diagram_note = (
                "Constructed diagram, drawn to scale — the right angle is a right "
                "angle and the squares match their sides. NCERT's own figures live "
                "inside the textbook PDFs and are not part of the corpus."
            )
            logger.info("Diagram: geometry template %s", template_name)

        from ...services.illustration import generate_illustration

        subject = usable[0].subject or "this topic"
        if diagram is None:
            diagram = generate_illustration(
                concept=f"{request.question.strip()} ({subject}, Class {grade})",
                description=answer[:400],
            )
        if diagram and diagram_note is None:
            diagram_note = (
                "Illustration drawn for this explanation. It carries no text, "
                "because image models misspell words — the labelled facts are in "
                "the explanation above. NCERT's own figures live inside the "
                "textbook PDFs and are not part of the corpus."
            )

    readability = None
    if request.reading_support:
        from ...services.accessibility import measure, segment_hard_words

        # Asking the model to write simply is not enough. Measured against the
        # NCERT source it was built from, the first version of this feature
        # produced an answer that scored *harder* than the textbook — grade 8.2
        # against 7.0 — because instructions buried among a dozen other rules
        # get diluted. So the answer is measured, rewritten with readability as
        # the only goal, measured again, and the easier of the two is kept.
        #
        # Keeping the better one matters: a rewrite can lose as easily as win,
        # and shipping a regression while claiming reading support would be
        # worse than not offering it.
        answer = answer.strip()
        before = measure(answer)

        if reading_load(before) > 2.0:  # both targets exceeded on average
            try:
                rewritten = (
                    await engine.generate(
                        SIMPLIFY_PROMPT.format(
                            answer=answer,
                            language=ANSWER_LANGUAGES[request.answer_language],
                        ),
                        GenerationConfig(max_tokens=1400, temperature=0.2, use_cache=False),
                    )
                ).strip()

                after = measure(rewritten)
                improved = reading_load(after) < reading_load(before)
                # A rewrite that drops half the lesson is not a simplification.
                substantial = len(rewritten) > len(answer) * 0.5

                if improved and substantial:
                    logger.info(
                        "Reading support: load %.2f -> %.2f",
                        reading_load(before), reading_load(after),
                    )
                    answer = rewritten
                else:
                    logger.info(
                        "Reading support: rewrite rejected (load %.2f -> %.2f, "
                        "length ratio %.2f)",
                        reading_load(before), reading_load(after),
                        len(rewritten) / max(len(answer), 1),
                    )
            except Exception as exc:  # noqa: BLE001 - keep the lesson
                logger.warning("Readability rewrite failed: %s", exc)

        source_text = " ".join(row.passage for row in usable)
        readability = ReadabilityReport(
            source=measure(source_text).as_dict(),
            answer=measure(answer).as_dict(),
            segmented_words=segment_hard_words(answer),
        )

    return ExplainResponse(
        answer=answer.strip(),
        answer_language=request.answer_language,
        grade=grade,
        grade_was_detected=detected,
        grounding=round(grounding, 4),
        sources=[
            Source(
                grade=row.grade,
                subject=row.subject,
                chapter=row.chapter,
                url=row.url,
                similarity=round(float(row.similarity), 4),
            )
            for row in usable
        ],
        diagram=diagram,
        diagram_note=diagram_note,
        readability=readability,
    )


@router.get("/tutor/languages", tags=["tutor"])
async def list_languages() -> dict:
    """
    Languages an answer can be written in.

    Questions need no declaration — retrieval is cross-lingual, so a question
    in any of these, or in Hinglish, finds the same material.
    """
    return {
        "answer_languages": list(ANSWER_LANGUAGES),
        "note": (
            "Ask in any language. The answer is written in the one you pick, "
            "which does not have to match."
        ),
    }
