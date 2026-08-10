# Shiksha Setu — how it works

Everything here is measured on the development machine unless marked otherwise:
an 8 GB Apple M1, PostgreSQL 14, Python 3.11. Numbers are reproducible with the
commands given beside them. Where something does not work, it says so.

---

## 1. What the system is

A student asks a question in whatever language is easiest for them. The system
finds the passages of the NCERT curriculum that answer it, works out which
class the topic belongs to, and teaches it back in the language the student
chose — optionally rewritten for a reader who finds decoding hard, and
optionally illustrated.

Three properties make that harder than it sounds, and most of this document is
about them:

1. **The question's language and the answer's language are independent.** A
   student may type Hinglish and want English back.
2. **The corpus is not in the student's language.** NCERT publishes in English,
   Hindi and Urdu. A Tamil-speaking student is taught from the English edition.
3. **The curriculum is graded.** The same words mean different things in class 6
   and class 12, so retrieval that ignores the class is worse than useless.

---

## 2. Request lifecycle

`POST /api/v2/tutor/explain` — the path a question actually takes.

```
question (any language)
   │
   ├─1─► rewrite to an English search query          llama-3.1-8b   ~0.6 s
   │      "bhai rusting kaise hoti hai"  ->  "how rusting occurs prevention"
   │
   ├─2─► embed the rewritten query                   BGE-M3 fp16    ~0.1 s
   │
   ├─3─► wide retrieval, no class filter             pgvector HNSW  ~0.02 s
   │      12 nearest passages across all classes
   │
   ├─4─► decide the class                            sum of top-3 similarities
   │      per class; class 10 wins with 1.78 against class 1's 1.20
   │
   ├─5─► narrow retrieval, scoped to that class      6 passages
   │      English and Hindi editions only
   │
   ├─6─► generate the explanation                    llama-3.1-8b   ~2 s
   │      grounded in those passages, in the chosen answer language
   │
   ├─7─► (reading support) measure, rewrite, measure, keep the easier
   │
   └─8─► (illustration) FLUX.1-dev                   ~5 s, runs last
```

Steps 7 and 8 are opt-in. Without them a warm request completes in about three
seconds; the first request after a cold start pays ~16 s to load the embedder.

---

## 3. Models, and why each one

| Role | Model | Where it runs | Why this one |
|---|---|---|---|
| Embeddings | `BAAI/bge-m3` | local, fp16 | Multilingual in one vector space, so a Hindi question reaches an English passage without translation. 1024-dim. |
| Explanation | `meta/llama-3.1-8b-instruct` | NVIDIA NIM | 0.9 s against 17–125 s for the 70B on the same prompt. A student waiting on an answer needs the first number. |
| Illustration | `black-forest-labs/flux.1-dev` | NVIDIA NIM | A text model writing SVG produces a box with floating words. See §7. |
| OCR (unused) | `ucaslcl/GOT-OCR2_0` | — | Cannot run here: its own modeling code calls `.cuda()`. See §6. |
| OCR (working) | `nvidia/nemotron-nano-12b-v2-vl` | NVIDIA NIM | Recovers the maths glyphs PyMuPDF drops. |

### Why the 8B and not the 70B

Same prompt, same endpoint, ~70 completion tokens:

```
meta/llama-3.1-8b-instruct           0.9 s
nvidia/nvidia-nemotron-nano-9b-v2    2.5 s
meta/llama-3.3-70b-instruct         17–125 s, highly variable
nvidia/llama-3.1-nemotron-nano-8b-v1   timed out at 180 s
```

End to end through the engine the 70B once took 125 s, because the first
attempt hit the 60 s timeout and the retry took another 63.

---

## 4. The corpus

### Catalog

NCERT's book codes are not derivable. Science is `sc` for classes 7–10, `cu`
(*Curiosity*) for class 6, and splits into `ph`/`ch`/`bo` at 11–12. The catalog
is therefore scraped from NCERT's own textbook picker — a JavaScript page that
writes titles through a chain of `if(pm=="jesc1")` blocks — and cached to
`data/ncert_catalog.json` so ingestion never depends on their site being up.

**558 books**: 208 English, 190 Hindi, 160 Urdu, across classes 1–12.
Roughly a quarter have no zip published; those are recorded as
`.unavailable` markers so a batched run does not re-request them every batch.

### Pipeline

```
zip  ──►  per-chapter PDFs  ──►  text  ──►  chunks  ──►  embeddings  ──►  Postgres
         PyMuPDF                cleanup    1200 chars    BGE-M3 fp16      pgvector
                                           200 overlap
```

Chunking prefers a paragraph break, then a sentence end, within the last
quarter of the window — a chunk that stops mid-sentence reads as broken and
embeds poorly. Overlap keeps a sentence that straddles a boundary reachable
from both sides.

One `processed_content` row per chapter, its `document_chunks` beneath it, one
embedding per chunk. Committed per book, so an interrupted run leaves no
half-ingested book that the resume check would then skip.

### Text quality, honestly

PyMuPDF's text layer is lossy on mathematics in a way that changes meaning.
Class 10 Maths chapter 4 defines a quadratic as

```
source:      ax² + bx + c,  a ≠ 0
text layer:  ax2 + bx + c,  a  0
```

The superscript flattens and the inequality is **deleted**, turning a
constraint into its opposite. Rendering the same page shows both glyphs present
and correct, so the loss is in extraction, not the PDF.

Affected pages are identifiable before OCR, because NCERT sets equations as
inline images. Measured images per 1000 characters:

```
Class 10 Maths ch4 (equations)   30.8
Class 10 Science ch8 (figures)    5.9
Class 10 Science ch5 (prose)      4.0
Class 10 Science ch1 (mixed)      2.0
```

The threshold sits at 15, in the gap. A tempting alternative — looking for the
run of spaces a dropped glyph leaves behind — was measured and discarded:
justified prose produces the same pattern at the same rate (4 hits in the maths
chapter, 4 in the prose chapter), so it identifies nothing.

**Diagrams are not extracted.** Class 10 Maths ch4 has 515 images across 11
pages; the ingestion takes text only. NCERT's figures are not in the corpus.

---

## 5. Retrieval

`vector(1024)` with an HNSW index on cosine distance:

```sql
CREATE INDEX idx_embeddings_hnsw_cosine
  ON embeddings USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

`EXPLAIN` confirms `Index Scan using idx_embeddings_hnsw_cosine`.

### The Hinglish problem

BGE-M3's cross-lingual strength does not extend to romanised Hindi. Same
question, top-5 hits, correct answer is class 10:

```
English      class 10 at 0.607, 0.596, 0.593, 0.578, 0.570
Devanagari   class 10 at 0.564, 0.557, 0.552, 0.552, 0.548
Hinglish     class  1 at 0.520, 0.506, 0.500, 0.499, 0.495   ← wrong
```

Devanagari retrieves correctly. Roman-script Hindi drifts onto whatever matches
on surface form — here, class 1 picture books answering a class 10 chemistry
question. Since Hinglish is how a great many Indian students type, every
question is now rewritten into a short English search query before embedding.
One sub-second call, with a fallback to the original text.

### Choosing the class

Scored on the **sum of each class's three strongest passages**. Two earlier
scorings were wrong:

- **Summing everything** let volume win: eight weak class 1 matches (0.40 each)
  beat three strong class 10 ones, and a chemistry question was answered at
  class 1 level.
- **Averaging the top few** has the opposite failure, which a test caught: one
  passage at 0.66 beats three at 0.60–0.62, because a single value is its own
  mean.

Capping at three bounds what volume can contribute while still rewarding
corroboration.

### Which editions are taught from

English and Hindi only. Every chapter exists three times in the corpus, so
cross-lingual retrieval was citing *"Class 1 Joyful-Mathematics (Urdu), chapter
13"* as the source of an English answer — a source the student cannot read or
check — and the six context passages could be one chapter in three scripts,
crowding out anything new. The Urdu editions stay searchable through the
library; they are not taught out of. The **answer** language is unaffected.

---

## 6. Optimisations, with the numbers

### Half-precision embeddings

```
                float32     float16
weights         2,166 MB    1,083 MB
encode 4 queries  2,255 ms    1,197 ms
load                8.5 s       8.1 s

cosine(float32, float16) of the same text:
    0.999999  English   1.000000  English
    0.999999  Devanagari   0.999999  romanised Hindi
```

Half the memory, roughly twice the speed, retrieval unchanged — a similarity of
0.999999 cannot reorder a result list. `EMBEDDING_DTYPE=auto` picks fp16 on MPS
and CUDA, fp32 on CPU where fp16 is emulated and slower.

### Memory ladder

```
bare interpreter                13 MB
+ torch                        198 MB
+ app config                   264 MB
+ BGE-M3 (float32)           1,015 MB
```

### Response caching

Route-level caching on read-heavy GETs and expensive POSTs, through a
multi-tier cache (L1 memory → L2 Redis → L3 disk). Cache keys include a
SHA-256 of the caller's `Authorization` header, so one student's response can
never be served to another; per-user, streaming and admin routes are never
cached, and a response carrying `Set-Cookie` is never stored.

`accept-encoding` is part of the key because the middleware sits outside GZip
and therefore caches encoded bodies.

### Embedder singleton

The library search endpoint originally constructed `BGEM3Embedder()` per
request and answered in **19.2 s**. Using the existing singleton: 18 s on the
first call while the model loads, then **0.7–1.2 s**.

### Ingestion throughput

Downloading and embedding contend for nothing — one waits on a slow government
web server, the other saturates the GPU — but ran in sequence, so each sat idle
while the other worked. Measured at **97 s/book** over 558 books. The next book
is now fetched on a prefetch thread while the current one is embedded.

### Batching, because 8 GB is not enough

A single process attempting all 558 books reached book 8 and wedged: swap at
11.4 GB of 12.2, the process in uninterruptible I/O wait with its resident set
paged entirely out, no progress for eleven minutes, no recovery. One process
per small batch returns every page between batches, at the cost of a ~20 s
model reload.

The memory guard checks **free RAM and swap together**. Swap alone is the wrong
signal and stopped a healthy run dead: macOS keeps swap allocated after use and
grows it on demand, so "937 MB free" was reported while 65% of RAM was idle.

### Running on 4 GB

With fp16 the serving path is roughly:

```
python + torch + app        ~264 MB
BGE-M3 fp16 weights       ~1,083 MB
Postgres (shared buffers)   ~256 MB default
                          ─────────
                           ~1.6 GB steady state
```

That fits. What does **not** fit on 4 GB is ingestion at the same time — the
embedder plus a 70 MB zip expanded across twenty PDFs needs the headroom.
Ingest on a larger machine, or ingest and serve at different times. The
pipeline is fully resumable, so alternating costs nothing but wall-clock.

Set `EMBEDDING_DTYPE=float16` explicitly if the platform detection picks CPU.

---

## 7. Illustrations

Asking a language model for SVG produces a rectangle with four floating words.
The 70B took **145 s** to produce fewer elements than the 8B managed in **8**.
Composing a recognisable scene in SVG coordinates is not something text models
do, and the prompt made it worse by specifying `fill="none"` and "no colour" for
theme-neutrality.

FLUX.1-dev draws the water cycle — sun with rays, clouds, falling rain, a blue
lake, green trees — in **5 s**.

**The pictures carry no text, deliberately.** Diffusion models misspell, and a
textbook diagram with garbled labels is worse than one with none. The facts stay
in the explanation, where they are accurate, selectable, translatable and
reachable by a screen reader.

Three failure modes are handled:

- FLUX accepts only fixed dimensions (768, 832, … 1344) and 422s anything else.
- It returns **JPEG**, not PNG. Validating against the PNG signature discarded
  every successful generation.
- It sometimes returns a blank frame and still reports `finishReason: SUCCESS`
  — all-black, or near-white at 8 KB with a brightness spread of **2** against
  205 for a good picture. Spread catches both; a blank triggers one retry with
  a different seed, then no picture rather than a black rectangle.

Rendered as `<img>`, not injected SVG, which removes that injection surface
entirely.

---

## 8. Reading support for dyslexic learners

### Aksharas, not letters

Dyslexia tooling is almost entirely English and assumes an alphabet. Most
Indian students read a Brahmic script, where the decoding unit is the
**akshara** — a consonant cluster carrying a vowel.

```
प्रकाश   per character:  प · ् · र · क · ा · श     unpronounceable fragments
        per akshara:    प्र · का · श              what a reader sounds out
```

Segmentation is generic across Devanagari, Bengali, Gurmukhi, Gujarati, Odia,
Tamil, Telugu, Kannada and Malayalam, by recognising each script's virama.

Two consequences that are easy to miss:

- **Sentence counting honours the danda (।).** A counter that only knows `.`
  reports a Hindi paragraph as one enormous sentence, and every figure derived
  from it is then wrong.
- **Flesch-Kincaid is reported for English only.** It is defined on English
  syllables; running it over akshara counts produces a confident number that
  means nothing.

### Measured, not asserted

The first version added instructions to the prompt. Measured against the NCERT
passages it was built from, the result came out **harder** than the textbook —
grade 8.2 against 7.0 — and the same prompt made the model answer a Hindi
request in romanised Hinglish.

So the answer is measured, rewritten with readability as the only goal,
measured again, and **the easier of the two is kept**. A rewrite that scores
worse, or loses more than half its length, is discarded. Same question after
the change: grade **6.9** against the source's 7.0, sentences 12.7 words
against 12.9.

### Typography, ordered by evidence

Letter and word spacing come first and are on by default: Zorzi et al. (PNAS,
2012) found extra-large spacing improved reading speed and halved errors in
dyslexic children, with no training and no equivalent effect in controls.

Dyslexia-specific fonts and coloured overlays sit under their own heading
saying plainly that studies have not shown a reliable benefit. They are offered
because some readers report they help — not presented as science.

Nothing here diagnoses anything.

---

## 9. Security posture

Findings from an audit of this codebase, all since fixed:

- A **duplicate auth module** whose `decode_token()` never checked the `type`
  claim — a refresh token (7 days) would have been accepted where an access
  token (30 minutes) was expected. Deleted rather than repaired; two
  password-hashing paths in a product holding student credentials is the defect.
- `validate_required()` **was never called**. A production deploy with no JWT
  secret, no `DATABASE_URL` and `DEBUG=true` booted silently. Startup now
  refuses on any ERROR-level issue in production.
- `getattr(settings, "RATE_LIMIT_CALLS", 100)` — **no such setting exists**, so
  the default silently replaced whatever operators configured and every deploy
  ran at 100/min.
- The **safety pipeline never loaded**: an import of `..safety` (the module is
  `..safety_pipeline`) raised `ModuleNotFoundError` into a bare `except`, so
  `_verify_response_safety` took the `if not pipeline: return response, True`
  branch and marked every chat response safe without checking it.
- **Sentry received student email, username and IP.** An explicit `set_user()`
  call ignores `send_default_pii=False`. Now the opaque account id only, with
  the email reduced to a truncated hash.
- The Sentry header filter was **case-sensitive**, so an event carrying
  `Authorization` rather than `authorization` shipped a live bearer token.
- **Uploads had no size limit.** `/stt/guest` takes no auth, so one POST could
  OOM the process. Now a 100 MB cap read in 64 KiB chunks, plus a type
  allowlist checked before a byte is read.
- The app role held **zero privileges on all 42 tables**. Route registration
  succeeding is what made the least-privilege switch look complete.
- RLS made shared curriculum **unrepresentable**: `organization_id = NULL`
  compares `NULL = NULL`, which is false, so unowned content was invisible to
  everyone permanently.

Still open: 33 handlers return internal exception text via `detail=str(e)`.

---

## 10. Content policy

**This platform ships unrestricted.** Output filtering is off by default, the
policy engine starts in `research` mode, and the age gate is inert — it reads a
header, never blocks, is never registered, and no route reads its flag. Its own
docstring calls it "the ONLY content restriction in Universal Mode".

Curriculum enforcement and grade-level adaptation **cannot be enabled** while
`UNIVERSAL_MODE=true`: the config reads `not universal_mode and os.getenv(...)`,
so their environment variables are ignored at any value.

The safety pipeline runs but is a keyword filter scoring 0.2 per regex match
against a 0.3 threshold — one flagged word passes, "explosive device" is not
matched at all, and "Gandhi was killed" or "the hydrogen bomb" are. It
under-blocks harm and over-blocks coursework.

`nvidia/llama-3.1-nemotron-safety-guard-8b-v3` is reachable through the
endpoint this project already uses, if real filtering is wanted.

---

## 11. What is verified

- 72 routes register; the app boots.
- **445 tests, no failures.** ~33 skip when a prerequisite is absent.
- Auth: bcrypt at 12 rounds, JWT type enforced both directions, forged
  signatures and expired tokens rejected.
- Retrieval answers real questions: "how does the human eye focus" returns
  Class 10 Science chapter 10 at 0.695.
- Cross-lingual retrieval: Hindi, Marathi and Bengali questions all find the
  right English chapter (0.596–0.672). Tamil is weakest — compound scientific
  terms retrieve on their first component, and both प्रकाश संश्लेषण and
  ஒளிச்சேர்க்கை open with the word for *light*.

### Not implemented, though referenced

`/api/v2/content/` CRUD · `/api/v2/experiments/` · `/api/v2/admin/backup/*`

### Known gaps

- `BGEReranker` exists and is not wired into retrieval. It would likely fix the
  compound-term misses above.
- `WriteBehindQueue.put` is synchronous while `cache.set` awaits it; four cache
  tests are skipped pending that refactor.
- Rate limiting is off in the shipped `.env`.

---

## 12. Reproducing the measurements

```bash
# retrieval quality across scripts
venv/bin/python - <<'PY'
from backend.services.rag import get_embedder
# ... embed the same question in three scripts, compare top-k
PY

# embedding precision
venv/bin/python -m pytest tests/unit/test_config.py -k precision -v

# akshara segmentation
venv/bin/python -m pytest tests/unit/test_readability.py -v

# the whole suite
venv/bin/python -m pytest
```
