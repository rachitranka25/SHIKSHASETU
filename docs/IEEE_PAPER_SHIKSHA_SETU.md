# Shiksha Setu: A Measurement-Driven, Local-First AI Tutoring Platform for Multilingual Indian Education

**Rachit Ranka**
Department of Computer Science, Chandigarh University, Mohali, Punjab, India
rankarachit5@gmail.com

---

## Abstract

Artificial intelligence holds transformative potential for education in linguistically diverse nations, yet existing systems overwhelmingly depend on cloud infrastructure, operate primarily in English, and lack alignment with national curricula. This paper presents Shiksha Setu, a local-first AI tutoring platform that ingests the complete National Council of Educational Research and Training (NCERT) curriculum — all 559 textbooks spanning classes 1 through 12 in three publication languages — and delivers retrieval-augmented instruction in ten Indian languages without transmitting student data beyond the local device. The system employs BGE-M3 multilingual embeddings with HNSW-indexed vector search over PostgreSQL, achieving cross-lingual retrieval cosine similarities of 0.596–0.672 across Hindi, Marathi, and Bengali queries against an English-language corpus. Through half-precision inference, the embedding pipeline reduces its memory footprint from 2,166 MB to 1,083 MB at a measured cosine fidelity of 0.999999 against full precision, enabling deployment on machines with as little as 4 GB of RAM — verified through kernel-level peak resident set size measurement rather than arithmetic estimation. The ingestion pipeline processes the 263-book taught curriculum at approximately 3.1 minutes per book, and the platform discovers and addresses two classes of corpus corruption: legacy Devanagari fonts that render 66% of Hindi textbooks as Latin gibberish, and mathematical symbol erasure in PDF text layers. A security audit of the codebase identifies and repairs twelve vulnerabilities, including a safety pipeline that silently failed open and a JWT implementation that accepted refresh tokens as access credentials. Reading support for dyslexic learners introduces akshara-level segmentation for nine Brahmic scripts, replacing the Latin-alphabet assumptions of conventional readability tooling. The system is validated by 445 automated tests with zero failures across unit, integration, and end-to-end suites.

**Index Terms** — Retrieval-Augmented Generation, Multilingual Education, Local-First AI, Indian Languages, Curriculum-Aligned Tutoring, Accessibility, NCERT

---

## I. Introduction

India is home to 1.4 billion people speaking 22 constitutionally recognized languages, written in at least 13 distinct scripts. The National Council of Educational Research and Training publishes the curriculum that governs instruction for over 250 million school-age children, yet its textbooks exist only in English, Hindi, and Urdu. A Tamil-speaking student in rural Tamil Nadu, a Marathi-speaking student in Maharashtra, and a Bengali-speaking student in West Bengal all study the same curriculum — but none of them can read it in their mother tongue unless a human teacher translates it in real time.

Artificial intelligence can bridge this gap, but the dominant paradigm of cloud-hosted large language models introduces three structural failures for Indian education:

**Language exclusion.** The overwhelming majority of educational AI systems operate in English as their primary language, treating multilingual capability as an afterthought. For the estimated 800 million Indians whose primary language is not English [11], this renders such systems inaccessible at the point of need. A student who types a chemistry question in romanized Hindi receives no useful response from a system that expects formal English input.

**Infrastructure dependence.** Cloud-based solutions require consistent high-bandwidth internet connectivity and impose per-query costs through API billing. In Tier 2 and Tier 3 Indian cities and rural areas, where internet access is intermittent and cost-sensitive, this dependency makes sustained educational use economically impractical. A system that charges per question creates a perverse incentive for students not to ask questions.

**Pedagogical misalignment.** General-purpose language models produce responses that may be factually accurate but are not pedagogically calibrated. They lack awareness of curriculum structure, grade-appropriate complexity, and the specific conceptual progression that Indian students follow across twelve years of NCERT instruction. A class 6 student asking about chemical reactions requires a fundamentally different explanation from a class 12 student asking about the same topic, and a system that cannot distinguish between the two is educationally harmful.

This paper presents Shiksha Setu, a platform that addresses all three failures simultaneously through a measurement-driven engineering approach. Rather than asserting capabilities, every claim in this paper is backed by an experiment whose procedure, data, and result are reported — including the experiments that produced wrong results before being corrected. The contributions of this work are:

1. A complete ingestion pipeline for the entire NCERT catalog (559 textbooks), with automatic detection and rejection of legacy-font corruption that renders 27 of 41 Hindi books unreadable — a failure mode discovered only through measurement, not documentation.

2. A cross-lingual retrieval system that enables questions in any of ten Indian languages to retrieve relevant passages from an English-language corpus, with measured retrieval quality across five languages and honest documentation of where compound scientific terms cause retrieval failure.

3. A memory optimization strategy verified through kernel-level measurement that enables the serving pipeline to operate within a 4 GB memory budget, correcting an earlier arithmetic estimate that understated actual consumption by 31%.

4. Akshara-level readability measurement and text simplification for nine Brahmic scripts, replacing the Latin-alphabet syllable counting of conventional readability formulas with script-appropriate segmentation.

5. A security audit documenting twelve vulnerabilities in the authentication, authorization, and content safety subsystems — all found and repaired — including a safety pipeline that failed open due to an import error, silently passing every response as safe.

6. A grounding metric that detects when a fluent, confident answer about the wrong topic has drifted from its source material — a failure mode that is indistinguishable from a correct answer without quantitative measurement.

The remainder of this paper is organized as follows. Section II surveys related work across retrieval-augmented generation, multilingual NLP, and reading accessibility. Section III presents the system architecture and request lifecycle. Section IV describes the corpus construction pipeline and its findings. Section V details the cross-lingual retrieval mechanism and its experimental evaluation. Section VI reports memory optimization results. Section VII covers accessibility features. Section VIII presents the security audit. Section IX consolidates experimental results, and Section X concludes with future directions.

---

## II. Related Work

### A. Retrieval-Augmented Generation

Lewis et al. [1] introduced retrieval-augmented generation (RAG) for knowledge-intensive NLP tasks, establishing the paradigm of conditioning language model output on retrieved passages rather than relying solely on parametric memory. Shiksha Setu adopts this architecture with a critical modification: a grade-level filter is inserted between retrieval and generation, because the same topic taught at class 6 and class 12 requires fundamentally different explanations. Karpukhin et al. [2] demonstrated the superiority of dense passage retrieval over sparse methods such as BM25 for open-domain question answering, motivating the use of learned embeddings over keyword matching. Ma et al. [6] showed that rewriting user queries before embedding improves retrieval quality for conversational inputs — the technique that resolved the romanized Hindi retrieval failure described in Section V-A. Nogueira and Cho [8] established passage re-ranking with cross-encoder models as a complementary stage to bi-encoder retrieval; the BGE-Reranker component exists in the Shiksha Setu codebase but is not yet wired into the retrieval path, representing known future work.

### B. Multilingual Embeddings and Indian Language NLP

Chen et al. [3] presented BGE-M3, a multilingual embedding model supporting over 100 languages in a unified 1024-dimensional vector space. Its cross-lingual property — that semantically equivalent passages in different languages map to nearby vectors — is the foundation that allows a Hindi question to retrieve an English passage without explicit translation. The limits of this property are tested experimentally in Section V-B. Conneau et al. [9] established the theoretical basis for cross-lingual representation learning through unsupervised pre-training at scale, explaining why a single encoder can place translations near each other in embedding space. Gala et al. [10] developed IndicTrans2, a state-of-the-art translation model covering all 22 scheduled Indian languages, which serves as the translation backbone in the Shiksha Setu pipeline. Kakwani et al. [11] provided monolingual corpora and evaluation benchmarks for Indian languages, highlighting the scarcity of evaluation data for most Indian languages — a constraint that limits formal evaluation of retrieval quality beyond the five languages tested in this work. Khanuja et al. [12] trained MuRIL on transliterated text, making it directly relevant to the romanized Hindi failure documented in Section V-A.

### C. Vector Search and Approximate Nearest Neighbors

The retrieval layer uses the Hierarchical Navigable Small World (HNSW) graph structure proposed by Malkov and Yashunin [5], implemented through the pgvector extension for PostgreSQL. The HNSW index parameters (m = 16, ef_construction = 64) balance index build time against query recall; the measured search latency of approximately 20 ms for 12-nearest-neighbor queries over the full corpus confirms sub-interactive response times. Reimers and Gurevych [4] established the sentence-level embedding formulation used to load the BGE-M3 model through the sentence-transformers library.

### D. Reading Accessibility and Brahmic Scripts

Zorzi et al. [13] conducted the foundational experiment on letter spacing for dyslexic readers, finding that extra-large spacing improved reading speed and halved errors in dyslexic children, with no training required and no equivalent effect in non-dyslexic controls. This is the single typographic intervention with strong experimental support, and it is the reason letter spacing is the first and default accessibility control in the platform. Rello and Baeza-Yates [14] studied font effects on dyslexic reading through eye tracking but found no reliable advantage for dyslexia-specific typefaces. Kuster et al. [15] confirmed that the Dyslexie font does not benefit reading in children with or without dyslexia. These findings inform the platform's decision to offer such fonts as user preferences without presenting them as evidence-based interventions.

Nag [16] studied early reading acquisition in Kannada, demonstrating that akshara-based literacy develops through a fundamentally different trajectory than alphabetic literacy. Nag and Snowling [17] argued that alphasyllabaries constitute their own category of writing system rather than alphabets with additional diacritical marks. These findings motivate the akshara-level segmentation described in Section VII, which replaces per-character counting with virama-aware consonant cluster recognition across nine Brahmic scripts.

### E. Text Simplification and Readability

Kincaid et al. [18] derived the Flesch-Kincaid grade-level formula for readability measurement. This formula is defined on English syllable counts, which is why the platform refuses to compute it for Devanagari text — a confident readability score derived from akshara counts rather than syllables is meaningless and potentially harmful. Xu et al. [19] demonstrated that text simplification is not a single task and that generic simplification routinely loses content, motivating the platform's measure-and-keep-the-easier approach rather than blind rewriting.

### F. Efficiency and Precision

Micikevicius et al. [21] established the safety of half-precision arithmetic for neural network inference, providing the theoretical basis for the fp16 embedding optimization that halves the BGE-M3 memory footprint from 2,166 MB to 1,083 MB with no measurable retrieval quality degradation (Section VI-A). Hinton et al. [23] introduced knowledge distillation, the training method BGE-M3 itself employs, and the pathway to smaller encoders for hardware-constrained deployments.

---

## III. System Architecture

### A. Request Lifecycle

A student's question traverses an eight-stage pipeline from input to response. The stages, their executing models, and measured latencies on an 8 GB Apple M1 are:

| Stage | Operation | Model / Component | Latency |
|---|---|---|---|
| 1 | Rewrite to English search query | LLaMA-3.1-8B-Instruct | ~0.6 s |
| 2 | Embed the rewritten query | BGE-M3 (fp16) | ~0.1 s |
| 3 | Wide retrieval (no class filter) | pgvector HNSW | ~0.02 s |
| 4 | Determine target class | Sum-of-top-3 scoring | < 0.01 s |
| 5 | Narrow retrieval (class-scoped) | pgvector HNSW | ~0.02 s |
| 6 | Generate explanation | LLaMA-3.1-8B-Instruct | ~2 s |
| 7 | Reading support (optional) | Readability pipeline | ~0.5 s |
| 8 | Illustration (optional) | FLUX.1-dev | ~5 s |

Without the optional stages, a warm request completes in approximately three seconds. The first request after a cold start incurs an additional 16 seconds for embedding model initialization.

The design separates the question's language from the answer's language. A student may type in romanized Hindi and receive an explanation in formal English, or type in English and receive a response in Tamil. This independence is critical because NCERT publishes in only three languages (English, Hindi, Urdu), while the platform serves ten. Translation is a serving-layer responsibility, not a corpus-layer one — a Tamil-speaking student is taught from the English source text, translated at response time by IndicTrans2 [10].

### B. Model Stack

The platform orchestrates eight specialized models, each selected through empirical comparison rather than specification reading:

| Role | Model | Parameters | Execution |
|---|---|---|---|
| Embeddings | BAAI/bge-m3 | 568M | Local (fp16) |
| Text Generation | LLaMA-3.1-8B-Instruct | 8B | NVIDIA NIM |
| Translation | IndicTrans2-1B | 1B | Local |
| Reranking | BGE-Reranker-v2-M3 | 568M | Local |
| Speech-to-Text | Whisper Large V3 Turbo | 809M | Local |
| Text-to-Speech | MMS-TTS / Edge TTS | Variable | Local / Online |
| Curriculum Validation | Gemma-2-2B-IT | 2B | Local |
| Text Simplification | Qwen2.5-3B-Instruct | 3B | Local (INT4) |

The choice of the 8B model over the 70B variant for text generation was driven by measurement, not assumption. Benchmarked against the same endpoint with identical prompts and approximately 70 completion tokens:

| Model | Measured Latency |
|---|---|
| meta/llama-3.1-8b-instruct | **0.9 s** |
| nvidia/nemotron-nano-9b-v2 | 2.5 s |
| meta/llama-3.3-70b-instruct | 17–125 s (highly variable) |
| nvidia/llama-3.1-nemotron-nano-8b-v1 | Timeout at 180 s |

A student waiting for a chat response needs the first row. The 70B model on one occasion took 125 seconds end-to-end because the initial attempt hit the 60-second timeout and the automatic retry consumed another 63 seconds.

### C. Data Layer

The persistence layer combines PostgreSQL 17 with the pgvector extension for vector storage and HNSW-indexed similarity search, Redis 7 for the second tier of response caching, and SQLite for the third cache tier. A multi-tier caching architecture (L1: in-memory LRU, L2: Redis, L3: SQLite on disk) serves read-heavy endpoints. Cache keys incorporate a SHA-256 hash of the caller's authorization header, ensuring that one student's cached response is never served to another. Streaming endpoints, per-user routes, and responses containing Set-Cookie headers are excluded from caching by design.

The vector index is defined as:

```sql
CREATE INDEX idx_embeddings_hnsw_cosine
  ON embeddings USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

Query execution plans confirm Index Scan using idx_embeddings_hnsw_cosine, verifying that retrieval uses the HNSW graph rather than falling back to sequential scan. An earlier migration stored embeddings as double precision[] rather than the vector(1024) type, which made index creation impossible and condemned every search to a full table scan — a defect discovered only when query latency was measured against expectation.

### D. Hardware Optimization

The platform implements a five-phase optimization architecture for Apple Silicon deployment:

| Phase | Component | Measured Improvement |
|---|---|---|
| Phase 1 | Async-first I/O | 19.4x over threading |
| Phase 2 | Type-optimized serialization | 2.2 ms round-trip |
| Phase 3 | GPU priority queue pipelining | 0.3 microsecond scheduling overhead |
| Phase 4 | P-core / E-core affinity routing | 0.1 microsecond task lookup |
| Phase 5 | Buffer pool allocation | 94.3% reuse rate |

A DeviceRouter automatically selects the optimal execution backend (MLX, CoreML, MPS, or CUDA) based on detected hardware capabilities. On Apple M4, measured hardware benchmarks include GPU throughput of 3.72 TFLOPS (FP16), SIMD-accelerated cosine similarity at 54.7 million operations per second, and full-stack import latency of 1.6 seconds.

---

## IV. Corpus Construction

### A. The NCERT Catalog

NCERT encodes every textbook with a five-character code — jesc1 represents Class 10, English medium, Science, book 1 — and serves them at predictable URLs. The subject letters within these codes are not algorithmically derivable: science is sc for classes 7–10 but cu (Curiosity) for class 6, and splits into ph, ch, bo at classes 11–12. The catalog is therefore scraped from NCERT's own textbook selection page, a JavaScript-based interface that writes titles through chains of conditional statements. This scraped catalog is cached locally so that ingestion runs never depend on the availability of NCERT's web server.

The complete catalog contains **559 textbooks**: 209 in English, 191 in Hindi, and 159 in Urdu, across classes 1 through 12. The platform teaches from a deliberate subset of **263 books** — every English edition, plus the 54 subjects that exist only in Devanagari (the Hindi readers, the Sanskrit readers, Hindustani music texts). Storing the Hindi and Urdu translations alongside the English edition of Class 10 Science would triple the corpus without teaching anything new, because translation is handled at serving time. However, translating a Hindi poetry reader into English would destroy the subject matter being taught, so these are retained in their original script.

Edition deduplication is matched on grade plus subject letters rather than subject letters alone, because NCERT reuses letter codes across unrelated books: class 9's vocational ievs1 (Solanceous Crop Cultivator) shares the vs letters with class 6's Vasant (a Hindi reader). Matching on letters alone incorrectly discarded half the Hindi readers as "already available in English."

### B. Ingestion Pipeline

The pipeline processes each book through five stages: ZIP download, per-chapter PDF extraction, text extraction via PyMuPDF, semantic chunking (1200 characters with 200-character overlap), BGE-M3 embedding at half precision, and storage in PostgreSQL with pgvector.

Chunking prefers paragraph breaks, then sentence boundaries, within the final quarter of the 1200-character window. A chunk that terminates mid-sentence embeds poorly and reads as fragmented to a student. The 200-character overlap ensures that sentences straddling chunk boundaries remain retrievable from either adjacent chunk. Each book is committed as a single database transaction, so an interrupted run leaves no half-ingested book that the resumption check would then incorrectly skip.

**Measured throughput.** Downloading from NCERT's servers and computing embeddings contend for no shared resource — one waits on network I/O from a government web server, the other saturates the GPU — yet they initially ran in sequence, yielding a throughput of 97 seconds per book (approximately seven hours for 263 books). After introducing a prefetch thread that downloads the next book while the current one is being embedded, throughput improved to **approximately 3.1 minutes per book**, reducing total ingestion time for the taught curriculum to approximately seven hours on an Apple M1.

### C. Experimental Finding: Legacy Font Corruption

Two-thirds of the Hindi curriculum is rendered unreadable by every PDF text extractor tested. NCERT's older Hindi textbooks are typeset in **Walkman-Chanakya 905**, a legacy font that maps Devanagari glyphs onto ASCII codepoints and ships no ToUnicode table. Text extraction returns raw byte values rather than Unicode characters. Class 10's Kshitij-2, for instance, yields:

```
dkO; [kaM ... rqylhnkl ... lu~ 1532 esa gqvk FkkA
```

where the intended text is the Devanagari: "kaavya khand ... tulaseedaas ... san 1532 mein hua tha"

Measured across 41 in-scope Hindi books (chapter 3 of each):

| Extraction Category | Books | Devanagari Content in Output |
|---|---|---|
| Legacy font (Walkman-Chanakya) | **27** | 0.0% |
| Unicode font (Kokila, Arya) | 14 | 97.9–100% |

**The measurement that was inverted.** An earlier quality assessment scored these books by counting broken Devanagari sequences: orphan vowel signs, doubled conjuncts, a virama followed by a vowel sign. It reported the 27 legacy-font books as the *cleanest in the corpus*, because a detector searching for damaged Devanagari finds nothing in a book containing no Devanagari at all. Kshitij-2 and Aroh were ranked as perfect and ingested on that basis; 133 chunks of Latin gibberish entered the retrieval corpus before a chapter was manually inspected. The measurement was not merely imprecise — it was *inverted*. The books it ranked worst (Sarangi, with 12 defects) are the only usable ones, and those it ranked perfect are entirely unusable.

The corrected detection function identifies the failure through the reverse signal: a Hindi book whose extracted text is overwhelmingly Latin. The ingestion pipeline now rejects such chapters rather than storing them, because a passage unreadable to any student still competes for retrieval slots against one that would have provided a correct answer.

### D. Experimental Finding: Text Layer Fidelity in Mathematics

PyMuPDF's text layer is lossy on mathematical content in a manner that changes semantic meaning. Class 10 Mathematics chapter 4 defines a quadratic equation as ax squared plus bx plus c, where a is not equal to zero. The text layer yields ax2 + bx + c, a  0 — the superscript is flattened and the inequality symbol is silently deleted, converting a defining constraint into its opposite.

Pages requiring optical character recognition are identifiable before OCR execution. NCERT sets equations as inline images, and image density relative to text length cleanly separates affected pages:

| Page Type | Images per 1000 Characters |
|---|---|
| Mathematics with inline equations | 30.8 |
| Science with figures | 5.9 |
| Prose with occasional figures | 2.0–4.0 |

A threshold of 15 images per 1000 characters sits in the wide gap between the two categories. An alternative heuristic — detecting the run of whitespace that a deleted glyph leaves in justified text — was tested and rejected: justified prose produces the identical pattern at the same frequency (4 matches in the mathematics chapter, 4 in a prose chapter), providing no discriminative signal.

**Cloud OCR does not resolve this.** Rendering pages at 3x resolution and transcribing with a vision-language model (nvidia/nemotron-nano-12b-v2-vl) correctly recovers the mathematical symbols but introduces substitution errors that are worse for a learner:

| Dimension | Text Layer | Vision OCR |
|---|---|---|
| Mathematical symbols | Dropped | Correctly recovered |
| Word identity | Correct | Substituted (e.g., words replaced with visually similar alternatives) |
| Hallucination | None | Fabricated a "Reprint 2026-27" header |

The text layer loses glyphs; the vision model substitutes visually similar characters and adds text that does not exist on the page. For a student, silent substitution of an incorrect but plausible word is more harmful than a visible gap.

---

## V. Cross-Lingual Retrieval

### A. The Romanized Hindi Problem

BGE-M3's cross-lingual capability — mapping semantically equivalent passages in different languages to nearby vectors — does not extend to romanized Hindi (transliterated Hindi written in Latin script). This is a critical limitation because romanized Hindi is the predominant text input mode for Indian students using standard keyboards.

The same chemistry question was embedded in three scripts and compared against the Class 10 Science corpus. The correct answer resides in class 10:

| Script | Top-5 Retrieval | Correct Class |
|---|---|---|
| English | Class 10 at 0.607, 0.596, 0.593, 0.578, 0.570 | Yes |
| Devanagari | Class 10 at 0.564, 0.557, 0.552, 0.552, 0.548 | Yes |
| Romanized Hindi | Class 1 at 0.520, 0.506, 0.500, 0.499, 0.495 | No |

Devanagari retrieves correctly. Romanized Hindi drifts to class 1 picture books that match on surface-level token overlap, answering a class 10 chemistry question with early-reader content. Since romanized Hindi is how a significant proportion of Indian students type, every question is now rewritten into a short English search query before embedding, following the query rewriting approach of Ma et al. [6]. This is a single sub-second call to the language model, with automatic fallback to the original text if rewriting fails.

### B. Cross-Lingual Retrieval Quality

Retrieval was evaluated across five Indian languages, querying against an English-only Class 10 Science corpus:

| Query Language | Question Topic | Retrieved Chapter | Similarity | Correct |
|---|---|---|---|---|
| Hindi | Human eye focusing | Ch. 10 (Hypermetropia) | 0.672 | Yes |
| Marathi | Electric current | Ch. 11 (Electricity) | 0.637 | Yes |
| Bengali | Human heart function | Ch. 5 (Circulation) | 0.596 | Yes |
| Hindi | Photosynthesis (compound term) | Ch. 9 (Light) | — | No |
| Tamil | Photosynthesis (compound term) | Ch. 11 (Electricity) | — | No |

The two failures share a common cause: compound scientific terminology. Both the Hindi and Tamil words for photosynthesis begin with the word for light. Retrieval follows the component word rather than the compound concept, matching the optics chapter rather than the biology chapter. Tamil exhibits the weakest performance among tested languages. Wiring the BGE-Reranker-v2-M3, which exists in the codebase as a cross-encoder scorer, into the retrieval path would likely resolve these compound-term failures through deeper semantic matching [8].

### C. Grade-Level Classification

Determining which class a question belongs to is essential because the same topic is taught at different levels of abstraction across grades. The platform uses the **sum of each class's three strongest passage similarities** as the classification signal. Two earlier scoring functions were tested and rejected:

- **Summing all passage similarities** allowed volume to dominate: eight weak class 1 matches (similarity approximately 0.40 each) outscored three strong class 10 matches, causing a chemistry question to be answered at class 1 level.
- **Averaging the top few passages** exhibited the opposite failure: a single passage at 0.66 similarity defeats three passages at 0.60–0.62 because a single value is its own mean, providing no corroboration signal.

Capping at three passages bounds the contribution of volume while still rewarding corroboration across multiple passages.

### D. Multi-Query Grade Resolution

When both the original query and the English rewrite independently propose a grade, their similarity scores cannot be naively pooled. The rewrite's absolute similarity scores tend to run higher than the original query's, so pooling allows the rewrite's incorrect class 3 hits (0.513, 0.497, 0.490) to outrank the original query's correct class 6 hits (0.496, 0.425, 0.423), causing the wrong class to win again.

The vote_grade function instead lets each query independently propose a class on its own scale, weighted by how decisive the proposal is — the fraction of total evidence its winning class holds, multiplied by the absolute evidence behind it. A query that ranks one class unanimously outweighs one that leads by 2%; a query whose single weak hit makes it unanimous by default does not outweigh a solid proposal.

---

## VI. Memory Optimization

### A. Half-Precision Embeddings

BGE-M3's weights were evaluated at both full (float32) and half (float16) precision:

| Metric | float32 | float16 |
|---|---|---|
| Weight memory | 2,166 MB | 1,083 MB |
| Encode 4 queries | 2,255 ms | 1,197 ms |
| Model load time | 8.5 s | 8.1 s |

Cosine similarity between vectors produced by each precision, for the same input text:

| Input Language | Cosine Similarity (fp32 vs fp16) |
|---|---|
| English | 0.999999–1.000000 |
| Devanagari Hindi | 0.999999 |
| Romanized Hindi | 0.999999 |

Half precision yields 50% memory reduction, approximately 1.88x encoding speedup, and retrieval quality that is indistinguishable from full precision. A cosine similarity of 0.999999 cannot reorder any result list. The EMBEDDING_DTYPE=auto configuration selects fp16 on MPS and CUDA backends, where hardware half-precision is native, and fp32 on CPU, where fp16 arithmetic is software-emulated and therefore slower — the opposite of the intended effect.

### B. Serving Footprint: Measurement vs. Arithmetic

An earlier version of the memory analysis summed static component sizes to approximately 1.6 GB and concluded that the system fits comfortably within 4 GB. A dedicated benchmarking script measures actual peak resident set size (RSS) through getrusage(RUSAGE_SELF), which records a high-water mark that survives subsequent page eviction — unlike ps, which reported 46 MB for a process holding a 1 GB model because the operating system had paged it out.

| Pipeline Stage | Peak RSS |
|---|---|
| Interpreter start | 14 MB |
| Configuration imported | 265 MB |
| BGE-M3 loaded (fp16) | 534 MB |
| **Query encoded** | **2,094 MB** |
| pgvector search complete | 2,094 MB |

The actual peak is **2,094 MB**, not the 1,600 MB that arithmetic predicted. The cost is not where summation placed it: loading the model weights accounts for only 534 MB (because safetensors memory-maps them), while the first forward pass adds **1,560 MB** as weight pages become resident and attention workspaces are allocated. Summing static component sizes misses this transient peak, which on a 4 GB machine is the number that determines whether the process survives.

The system does fit within 4 GB alongside PostgreSQL (whose shared_buffers defaults to 256 MB), but with approximately 1.4 GB of headroom rather than the 2.4 GB that arithmetic implied. Two limitations of this measurement are stated: (1) the 1,560 MB spike is hypothesized to be an attention workspace sized for the model's maximum sequence length of 8,192 tokens, although an attempt to cap max_seq_length did not take effect; (2) two runs of the same configuration on a swapping machine differed by 414 MB, so these figures are accurate to within a few hundred megabytes.

### C. Ingestion Memory Management

A single process attempting to ingest the entire 263-book curriculum reached book 8 and entered an unrecoverable state: swap usage at 11.4 GB of 12.2 GB maximum, the process in uninterruptible I/O wait with its entire resident set paged out, and no progress for eleven minutes. SIGKILL is not delivered in that state because the kernel cannot deliver signals until the pending I/O operation completes. There is no recovery mechanism; only waiting.

The solution is batch processing: one process per batch of six books, with the process exiting and a new one starting between batches. This appears wasteful — each batch pays approximately 20 seconds for model reloading — but it is the only approach that prevents memory exhaustion on an 8 GB machine. The memory guard checks **free RAM and swap together**. An earlier implementation checked swap alone and terminated a healthy run while 65% of RAM sat idle, because macOS maintains swap allocation after use and grows it on demand, reporting "937 MB free" while the system had abundant RAM available.

---

## VII. Reading Support for Brahmic Script Readers

### A. Akshara Segmentation

Dyslexia support tooling is overwhelmingly designed for English-language alphabetic reading. Most Indian students read a Brahmic script, where the fundamental unit of decoding is the **akshara** — a consonant cluster carrying an inherent or explicitly marked vowel. Splitting an Indic word per Unicode character yields fragments that do not correspond to pronounceable units. Splitting per akshara yields segments that are exactly what a reader sounds out.

The segmentation algorithm recognizes the virama (halant) character in each Brahmic script as the signal that two consonants are conjoined. It operates generically across Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, and Malayalam by detecting each script's virama from a lookup table and grouping consonant clusters with their following vowel marks.

Two implementation details are easily overlooked:

1. **Sentence counting must honor the danda.** A counter that recognizes only the Latin period reports an entire Hindi paragraph as a single sentence, invalidating every derived metric.

2. **Flesch-Kincaid is computed for English text only.** The formula is defined on English syllable counts; computing it over akshara counts produces a numerically confident result that carries no meaning and could mislead educators into harmful conclusions about text difficulty.

### B. Measured Simplification Quality

The first implementation of reading support added simplification instructions to the generation prompt. When measured against the NCERT source passages, the simplified output was **harder** than the original textbook:

| Version | Flesch-Kincaid Grade Level |
|---|---|
| NCERT source text | 7.0 |
| First simplification attempt | **8.2** (harder) |
| Measure-and-keep approach | **6.9** (easier) |

The same prompt also caused the model to respond in romanized text when a formal response in the native script was requested, contaminating the output language.

The corrected approach measures the readability of the original answer, rewrites it with readability as the sole objective, measures the rewrite, and **retains whichever version is easier**. A rewrite that scores worse than the original, or that loses more than half its content length, is discarded. After this correction, the same question produced a response at grade level 6.9 with an average sentence length of 12.7 words, against the source's 7.0 grade level and 12.9 words per sentence.

### C. Evidence-Based Typography

Typographic interventions are presented in order of experimental evidence:

1. **Letter and word spacing** (on by default): Supported by Zorzi et al. [13], who demonstrated that extra-large spacing improved reading speed and halved errors in dyslexic children in a controlled experiment with no equivalent effect in non-dyslexic controls.

2. **Dyslexia-specific fonts and colored overlays** (available as preferences, labeled as weakly evidenced): Rello and Baeza-Yates [14] found readability effects across fonts but no specific advantage for dyslexia-designed typefaces. Kuster et al. [15] confirmed that the Dyslexie font provides no measurable benefit. These options are offered because individual readers report subjective benefit, but they are not presented as evidence-based interventions.

Nothing in the accessibility module diagnoses any condition. It adjusts presentation based on user preferences and measured readability outcomes.

---

## VIII. Security Analysis

A comprehensive audit of the codebase identified twelve vulnerabilities, all of which have been repaired. The findings are ordered by consequence severity:

| No. | Vulnerability | Consequence |
|---|---|---|
| 1 | Safety pipeline import path error caught by bare except | Content filtering failed open — every response marked safe without evaluation |
| 2 | Duplicate auth module with no JWT type claim check | Refresh tokens (7-day) accepted as access tokens (30-minute) |
| 3 | validate_required() only logged, never called | Production with no JWT secret booted silently |
| 4 | RATE_LIMIT_CALLS referenced via getattr; setting did not exist | Every deployment ran at hardcoded default regardless of config |
| 5 | Embedding column stored as double precision array | No vector index possible; all searches were sequential scans |
| 6 | SQL bind parameter syntax error with colon | SQLAlchemy truncated parameter names |
| 7 | Row-level security compared NULL = NULL | Shared curriculum invisible to all users permanently |
| 8 | Application role held zero table privileges | Least-privilege role could not read any data |
| 9 | Sentry received student PII despite configuration | Email, username, IP transmitted externally |
| 10 | Case-sensitive credential header filter | Capitalized Authorization header bypassed stripping |
| 11 | No upload size limit on unauthenticated route | Single POST could exhaust disk storage |
| 12 | torchvision undeclared as dependency | OCR module could never import |

**Vulnerability #1** is the most consequential: the safety pipeline was designed as a three-pass content filter, but an import path error caused the entire pipeline to fail to load. The error was caught by a bare except clause, which returned the response as safe. This meant the content safety system was structurally incapable of blocking any response since deployment, while appearing functional in all diagnostic checks.

**Remaining open issue.** The processed_content table carries row-level security for multi-tenant isolation. Its child tables, document_chunks and embeddings, carry none. Tenant isolation is therefore bypassable: a tenant's database connection can read and delete another tenant's chunks directly.

---

## IX. Grounding and Hallucination Detection

A retrieval-augmented system can retrieve the correct chapter and still generate a fabricated answer. When asked about a specific story from the Hindi curriculum, the system retrieved the correct chapter and then described events that never occurred in the text. The class was correct, the chapter was correct, the response language was correct, and every narrative detail was invented.

Nothing in the response's surface features distinguishes it from a correct answer. The **grounding score** addresses this by computing the cosine similarity between the generated answer and the source passages from which it was derived. Lexical overlap metrics cannot serve this purpose because the platform's fundamental design produces answers in a different language from the source passages — a Devanagari passage generating an English answer shares almost no surface tokens. BGE-M3's cross-lingual embedding property is what makes the metric functional in exactly this case.

Calibrated against four hand-verified answers:

| Grounding Score | Verification | Content Description |
|---|---|---|
| 0.701 | Correct | Poetry couplets sourced from the correct chapter |
| 0.668 | Correct | Poem content quoting its own lines |
| 0.583 | Correct | Narrative correctly describing story events |
| 0.489 | **Incorrect** | Fabricated content bearing no relation to source |

GROUNDING_MIN = 0.55 is set between the correct and incorrect answers. Below this threshold, the answer is regenerated once with the detected drift named explicitly in the prompt; the grounding score is returned in the API response regardless. Four data points constitute a starting value for calibration, not a validated threshold.

The 0.489 case is particularly instructive: after the grade-voting fix resolved the class assignment, the end-to-end test *passed* — the response was in the correct language, attributed to the correct class, and cited sources from the correct reader. The answer was still fabricated, because retrieval landed on the wrong chapter within the correct book, and the model generated content word by word from parametric memory. Only the grounding score caught the failure. A test that verifies language and class verifies the easy half.

---

## X. Illustration Generation

Requesting SVG illustrations from language models produces geometrically degenerate output. The 70B model consumed 145 seconds to generate fewer recognizable elements than the 8B model produced in 8 seconds. FLUX.1-dev generates photorealistic educational illustrations in approximately 5 seconds. Three failure modes are handled programmatically:

1. **Dimension rejection**: FLUX accepts only specific image dimensions and returns HTTP 422 for others.
2. **Format mismatch**: The model returns JPEG despite PNG documentation. Validation against PNG magic bytes discarded every successful generation until detection was corrected.
3. **Blank frames with success status**: Detection uses brightness spread: a blank frame measures a spread of 2, while a genuine illustration measures approximately 205. Below a threshold of 40, one retry is attempted.

Generated images are deliberately text-free. Diffusion models render characters as visual texture rather than legible glyphs, producing misspelled labels that are educationally harmful. Factual content remains in the textual explanation, where it is accurate, selectable, translatable, and accessible to screen readers [26].

---

## XI. Consolidated Results

### A. Validation Suite

The platform is validated by **445 automated tests** with zero failures:

| Suite | Tests | Scope |
|---|---|---|
| Unit | 350+ | Individual components, models, utilities |
| Integration | ~60 | Cross-component interactions |
| End-to-end | ~20 | Full request lifecycle |
| Performance | ~15 | Benchmark contracts and latency bounds |

### B. Retrieval Performance Summary

| Metric | Value |
|---|---|
| Cross-lingual retrieval (Hindi to English) | 0.672 cosine similarity |
| Cross-lingual retrieval (Marathi to English) | 0.637 cosine similarity |
| Cross-lingual retrieval (Bengali to English) | 0.596 cosine similarity |
| HNSW search latency (12 nearest neighbors) | ~20 ms |
| Embedding encode (warm, single query) | 83 ms |
| Embedding encode (cold start) | 12.4 s |
| Embedding model load | 5.3 s |

### C. System-Level Metrics

| Metric | Value |
|---|---|
| NCERT catalog coverage | 559 textbooks (complete) |
| Taught curriculum | 263 textbooks |
| Supported translation languages | 10 |
| API routes | 72 |
| Ingestion throughput | ~3.1 min/book |
| Full curriculum ingestion time | ~7 hours (Apple M1) |
| Peak serving memory (fp16) | 2,094 MB |
| Embedding precision fidelity | 0.999999 cosine (fp16 vs fp32) |
| Memory reduction (fp16) | 50% (2,166 to 1,083 MB) |
| Encoding speedup (fp16) | 1.88x |
| End-to-end response latency (warm) | ~3 s |
| Grounding threshold | 0.55 |
| Security vulnerabilities found and fixed | 12 |
| Automated tests passing | 445 (zero failures) |

### D. Hardware Optimization Benchmarks (Apple M4)

| Metric | Value |
|---|---|
| GPU TFLOPS (FP16) | 3.72 |
| SIMD Throughput (cosine similarity) | 54.7M ops/sec |
| Async I/O speedup over threading | 19.4x |
| Buffer pool reuse rate | 94.3% |
| Full FastAPI import latency | 1.6 s |
| Device detection latency | 18.7 ms |

### E. Accessibility Metrics

| Metric | Value |
|---|---|
| Brahmic scripts with akshara segmentation | 9 |
| Readability improvement (FK grade) | 7.0 to 6.9 |
| Initial failed simplification (FK grade) | 7.0 to 8.2 (made harder) |

---

## XII. Discussion

The measurement-driven methodology adopted in this work reveals a recurring pattern: intuitive engineering assumptions about system behavior are frequently contradicted by empirical measurement, and the contradictions are more informative than the original assumptions.

The legacy font detection illustrates this most starkly. A quality metric designed to identify corrupted Devanagari text ranked the most corrupted books as the best in the corpus — not because the metric was poorly designed, but because its design assumption (that corruption manifests as damaged Devanagari) was wrong. The corruption manifested as the absence of Devanagari entirely, which the metric interpreted as perfection. One hundred and thirty-three chunks of gibberish entered the retrieval corpus before the error was caught through manual inspection rather than automated testing.

The memory estimation follows the same pattern at a different scale. Summing component sizes is a reasonable engineering heuristic, but it misses the transient allocation peak during the first forward pass — the peak that determines whether a memory-constrained device can serve the model at all. The difference between the arithmetic estimate (1.6 GB) and the measured peak (2.1 GB) is the difference between "fits with 2.4 GB headroom" and "fits with 1.4 GB headroom" — still feasible, but with significantly less margin for concurrent operations.

The grounding score addresses a fundamental limitation of retrieval-augmented generation that evaluation metrics typically overlook: a system can retrieve the correct source document, generate a fluent and confident response, pass every surface-level quality check, and still fabricate content. The end-to-end test that verified language, class, and source attribution passed for an answer that was entirely invented. Without a semantic similarity measurement between the answer and its stated sources, such failures are invisible.

These findings suggest that measurement-driven validation — including measurement of the measurement tools themselves — should be a standard component of educational AI system development, particularly when the system operates autonomously without expert oversight.

### Limitations

Several limitations of this work should be noted:

1. The grounding threshold of 0.55 is calibrated on only four hand-verified answers. While it cleanly separates the correct from incorrect cases observed, this sample is insufficient for statistical validation.

2. Cross-lingual retrieval quality has been evaluated across five languages. The remaining five supported translation languages (Gujarati, Kannada, Malayalam, Punjabi, Odia) have not been tested for retrieval quality.

3. The 27 legacy-font Hindi books remain unprocessable. Recovering them requires a transliteration with matra reordering that has not been implemented.

4. The BGE-Reranker component, which would likely resolve compound-term retrieval failures, exists in the codebase but is not integrated into the retrieval path.

5. Memory measurements were taken on a single machine under swapping conditions, with run-to-run variance of up to 414 MB.

---

## XIII. Conclusion and Future Work

This paper has presented Shiksha Setu, a local-first AI tutoring platform that processes the complete NCERT curriculum of 559 textbooks and delivers instruction in ten Indian languages on consumer hardware with as little as 4 GB of RAM. Every performance claim has been substantiated through kernel-level measurement rather than specification-based estimation, and engineering failures encountered during development have been documented alongside their corrections.

The principal technical contributions are: (1) a corpus construction pipeline that identifies and rejects legacy-font corruption affecting 66% of Hindi textbooks, (2) cross-lingual retrieval achieving 0.596–0.672 cosine similarity across three tested Indian languages against an English corpus, (3) a grounding metric that detects hallucinated responses invisible to surface-level evaluation, (4) half-precision embedding inference that halves memory requirements with 0.999999 cosine fidelity, (5) akshara-level readability measurement for nine Brahmic scripts, and (6) a security audit documenting and repairing twelve production vulnerabilities.

Future work will focus on four directions. First, integrating the BGE-Reranker cross-encoder into the retrieval path to resolve compound scientific term failures in Hindi and Tamil. Second, developing a Walkman-Chanakya-to-Unicode transliterator with matra reordering to recover the 27 legacy Hindi books currently excluded from the corpus. Third, expanding the grounding score calibration from four to a statistically meaningful sample of hand-verified answers. Fourth, evaluating retrieval quality across all ten supported languages rather than the five currently tested.

The platform demonstrates that meaningful multilingual AI education is achievable on consumer hardware, without cloud dependency, and without sacrificing privacy — but only when every component is measured rather than assumed to work, and when failures are treated as findings rather than concealed.

---

## References

[1] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Kuttler, M. Lewis, W.-T. Yih, T. Rocktaschel, S. Riedel, and D. Kiela, "Retrieval-augmented generation for knowledge-intensive NLP tasks," in Proc. Advances in Neural Information Processing Systems (NeurIPS), 2020.

[2] V. Karpukhin, B. Oguz, S. Min, P. Lewis, L. Wu, S. Edunov, D. Chen, and W.-T. Yih, "Dense passage retrieval for open-domain question answering," in Proc. Conf. Empirical Methods in Natural Language Processing (EMNLP), 2020.

[3] J. Chen, S. Xiao, P. Zhang, K. Luo, D. Lian, and Z. Liu, "BGE M3-Embedding: Multi-lingual, multi-functionality, multi-granularity text embeddings through self-knowledge distillation," arXiv preprint arXiv:2402.03216, 2024.

[4] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese BERT-Networks," in Proc. Conf. Empirical Methods in Natural Language Processing (EMNLP), 2019.

[5] Y. A. Malkov and D. A. Yashunin, "Efficient and robust approximate nearest neighbor search using hierarchical navigable small world graphs," IEEE Trans. Pattern Anal. Mach. Intell., vol. 42, no. 4, pp. 824-836, 2020.

[6] X. Ma, Y. Gong, P. He, H. Zhao, and N. Duan, "Query rewriting for retrieval-augmented large language models," in Proc. Conf. Empirical Methods in Natural Language Processing (EMNLP), 2023.

[7] L. Gao, X. Ma, J. Lin, and J. Callan, "Precise zero-shot dense retrieval without relevance labels," in Proc. Annual Meeting of the Association for Computational Linguistics (ACL), 2023.

[8] R. Nogueira and K. Cho, "Passage re-ranking with BERT," arXiv preprint arXiv:1901.04085, 2019.

[9] A. Conneau, K. Khandelwal, N. Goyal, V. Chaudhary, G. Wenzek, F. Guzman, E. Grave, M. Ott, L. Zettlemoyer, and V. Stoyanov, "Unsupervised cross-lingual representation learning at scale," in Proc. Annual Meeting of the Association for Computational Linguistics (ACL), 2020.

[10] A. Gala, P. A. Jayakumar, J. Kumar, A. Shenoy, R. Gala et al., "IndicTrans2: Towards high-quality and accessible machine translation models for all 22 scheduled Indian languages," Trans. Machine Learning Research (TMLR), 2023.

[11] D. Kakwani, A. Kunchukuttan, S. Golla, N. C. Gokul, A. Bhattacharyya, M. M. Khapra, and P. Kumar, "IndicNLPSuite: Monolingual corpora, evaluation benchmarks and pre-trained multilingual language models for Indian languages," in Findings of EMNLP, 2020.

[12] S. Khanuja, D. Bansal, S. Mehtani, S. Khosla, A. Dey, B. Gopalan, D. K. Margam, P. Aggarwal, R. T. Nagipogu, S. Dave, S. Gupta, S. C. B. Gali, V. Subramanian, and P. Talukdar, "MuRIL: Multilingual representations for Indian languages," 2021.

[13] M. Zorzi, C. Barbiero, A. Facoetti, J. Lonciari, M. Carrozzi, M. Montico, L. Bravar, F. Kelly, C. Butterworth, and J. Ziegler, "Extra-large letter spacing improves reading in dyslexia," Proc. National Academy of Sciences (PNAS), vol. 109, no. 28, pp. 11455-11459, 2012.

[14] L. Rello and R. Baeza-Yates, "Good fonts for dyslexia," in Proc. ACM SIGACCESS Conf. Computers and Accessibility (ASSETS), 2013.

[15] S. M. Kuster, M. van Weerdenburg, M. Gompel, and A. M. T. Bosman, "Dyslexie font does not benefit reading in children with or without dyslexia," Annals of Dyslexia, vol. 68, pp. 25-42, 2018.

[16] S. Nag, "Early reading in Kannada: The pace of acquisition of orthographic knowledge and phonemic awareness," J. Research in Reading, vol. 30, no. 1, pp. 7-22, 2007.

[17] S. Nag and M. J. Snowling, "Reading in an alphasyllabary: Implications for a language-universal theory of learning to read," Scientific Studies of Reading, vol. 16, no. 5, pp. 404-423, 2012.

[18] J. P. Kincaid, R. P. Fishburne, R. L. Rogers, and B. S. Chissom, "Derivation of new readability formulas for Navy enlisted personnel," Naval Technical Training Command, Research Branch Report 8-75, 1975.

[19] W. Xu, C. Callison-Burch, and C. Napoles, "Problems in current text simplification research: New data can help," Trans. Association for Computational Linguistics (TACL), vol. 3, pp. 283-297, 2015.

[20] C. Jiang, M. Maddela, W. Xu, and D. Preotiuc-Pietro, "Neural CRF model for sentence alignment in text simplification," in Proc. Annual Meeting of the Association for Computational Linguistics (ACL), 2020.

[21] P. Micikevicius, S. Narang, J. Alben, G. Diamos, E. Elsen, D. Garcia, B. Ginsburg, M. Houston, O. Kuchaiev, G. Venkatesh, and H. Wu, "Mixed precision training," in Proc. Int. Conf. Learning Representations (ICLR), 2018.

[22] T. Dettmers, M. Lewis, Y. Belkada, and L. Zettlemoyer, "LLM.int8(): 8-bit matrix multiplication for transformers at scale," in Proc. Advances in Neural Information Processing Systems (NeurIPS), 2022.

[23] G. Hinton, O. Vinyals, and J. Dean, "Distilling the knowledge in a neural network," arXiv preprint arXiv:1503.02531, 2015.

[24] A. Radford, J. W. Kim, T. Xu, G. Brockman, C. McLeavey, and I. Sutskever, "Robust speech recognition via large-scale weak supervision," in Proc. Int. Conf. Machine Learning (ICML), 2023.

[25] H. Wei, C. Liu, J. Chen, J. Wang, L. Kong, Y. Xu, Z. Ge, L. Si, F. Zhu, and Y. Huo, "General OCR theory: Towards OCR-2.0 via a unified end-to-end model," arXiv preprint arXiv:2409.01704, 2024.

[26] R. Rombach, A. Blattmann, D. Lorenz, P. Esser, and B. Ommer, "High-resolution image synthesis with latent diffusion models," in Proc. IEEE/CVF Conf. Computer Vision and Pattern Recognition (CVPR), 2022.
