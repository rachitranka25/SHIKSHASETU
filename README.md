# Shiksha Setu

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Tests](https://img.shields.io/badge/tests-445%20passing-brightgreen.svg)](#project-status)
[![Architecture](https://img.shields.io/badge/docs-architecture-blue.svg)](docs/ARCHITECTURE.md)

**Open AI for Education & Noble Purposes**

A local-first, unrestricted AI platform that empowers learning, research, creativity, and noble causes.

> **Content policy:** this platform ships **unrestricted**. Output filtering is
> off by default. See [Content Policy](#content-policy) before deploying it to
> students.

## Curriculum coverage

The pipeline covers **the entire NCERT catalog — all 558 textbooks across
classes 1 to 12**, in English, Hindi and Urdu. Book codes are scraped from
NCERT's own picker, so the catalog tracks whatever they publish rather than a
hand-written list, and ingestion is a single resumable command:

```bash
scripts/ingest_ncert_batched.sh          # English + Hindi, ~398 books
INGEST_MEDIA=Urdu scripts/ingest_ncert_batched.sh   # the rest, later
```

How much of that is loaded into any given deployment is a separate question —
it depends on how long the operator has let the ingestion run. Check with:

```bash
curl localhost:8000/api/v2/library | jq '{books: .total_books, classes: .grades}'
```

The `/library` page shows the same thing, and the class filter is built from
what is actually present rather than from a fixed list.

---

**[→ docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — how every part works, with
the measurements behind each decision: request lifecycle, model choices and the
benchmarks that drove them, the ingestion pipeline, why Hinglish retrieval was
broken and how it was fixed, memory optimisation and the 4 GB path, akshara
segmentation for dyslexic readers, and the security findings.

---

## Vision

Shiksha Setu is evolving beyond education into a **general-purpose AI** that:
- 🎓 **Educates** — STEM-aligned content, multilingual support, grade adaptation
- 🔬 **Researches** — Unrestricted knowledge exploration for academic work
- 🎨 **Creates** — Assists with writing, coding, analysis, and creative tasks
- 🌍 **Serves Noble Purposes** — Healthcare, accessibility, social good

### Philosophy

> **Open by default. Restriction is a deployment decision, not a default.**

---

## Content Policy

Read this before putting the platform in front of students. It describes what
the code does, not what would be reassuring.

**Nothing is filtered out of the box.** The policy engine starts in `research`
mode — "maximum freedom" — with `POLICY_FILTERS_ENABLED=false` and
`SENSITIVE_RESPONSE_BLOCKING=false`. Model output reaches the student
unchanged.

**The age gate does nothing.** `AgeConsentMiddleware` reads an `X-Age-Consent`
header into `request.state.age_consent` and deliberately does not block. It is
never registered on the app, and no route reads the flag. Its own docstring
calls it "the ONLY content restriction in Universal Mode", which makes the
overall position clear enough.

**Curriculum enforcement and grade-level adaptation cannot be switched on while
`UNIVERSAL_MODE=true`.** The configuration reads
`not universal_mode and os.getenv(...)`, so the environment variables for both
are ignored, whatever they are set to. Both appear in the capability table
above. To reach them, set `UNIVERSAL_MODE=false`.

**The safety pipeline runs, but it is a keyword filter.** Three verification
passes execute on chat responses; pass 3 scores toxicity with regexes, adding
0.2 per match against a 0.3 threshold. Consequences worth knowing:

- A single occurrence of a flagged word scores 0.2 and passes. Two are needed
  to trip anything.
- Phrasing outside the word list is not matched at all — `bomb` is listed,
  `explosive device` is not.
- The list contains `kill`, `die`, `hate`, and `bomb`, which are ordinary words
  in a history or chemistry lesson. "Gandhi was killed", "the hydrogen bomb",
  and "cells die" are all flagged by the same mechanism that misses the
  paragraph above it.

So it under-blocks real harm and over-blocks legitimate coursework. Treat it as
a placeholder rather than a control you can rely on.

**If you need real filtering**, the NVIDIA endpoint this project can already
talk to (see [LLM Provider](#llm-provider)) serves purpose-built classifiers —
`nvidia/llama-3.1-nemotron-safety-guard-8b-v3` and
`nvidia/nemotron-3.5-content-safety` — which are a far better foundation than
the regex list. Wiring one in is not done.

**Unauthenticated surface:** `/api/v2/chat/guest` and `/api/v2/stt/guest`
require no credentials, so everything above applies to anonymous callers.

---

## Overview

Shiksha Setu is a production-grade AI platform that runs entirely locally on Apple Silicon, with no cloud dependencies. It simplifies content, translates to Indian languages, answers questions, and generates audio—all through a unified AI pipeline.

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Text Simplification** | Grade-level adaptation using Qwen2.5-3B-Instruct — grade adaptation requires `UNIVERSAL_MODE=false`, see [Content Policy](#content-policy) |
| **Translation** | 10 Indian languages via IndicTrans2-1B |
| **OCR** | Document extraction with GOT-OCR2.0 (95%+ accuracy on Indian scripts) |
| **Validation** | NCERT curriculum alignment using Gemma-2-2B-IT (≥80% threshold) — requires `UNIVERSAL_MODE=false`, see [Content Policy](#content-policy) |
| **Text-to-Speech** | Dual TTS: Edge TTS (online) + MMS-TTS (offline, 1100+ languages) |
| **Speech-to-Text** | Whisper Large V3 Turbo (8x faster, 99 languages) |
| **RAG Q&A** | Intelligent question answering with BGE-M3 embeddings |
| **Reranking** | Improved retrieval with BGE-Reranker-v2-M3 |
| **Universal File Upload** | Process any file: images, PDFs, audio, video, spreadsheets |
| **A/B Testing** | Experiment framework for content optimization |
| **Multi-Tenancy** | Organization-level isolation and management |
| **Learning Recommendations** | Personalized content suggestions |
| **Question Generation** | Auto-generate quizzes from content |
| **Teacher Evaluation** | Content review and approval workflows |

### Universal File Processing

Upload **any file type** and get intelligent AI processing:

| File Type | Extensions | AI Processing |
|-----------|-----------|---------------|
| **Audio** | mp3, wav, m4a, ogg, flac, aac, wma | Whisper V3 transcription |
| **Video** | mp4, webm, mov, avi, mkv | Audio extraction + STT |
| **Documents** | pdf (multi-page), docx | GOT-OCR2 + Tesseract OCR |
| **Images** | png, jpg, jpeg, tiff, bmp, webp, gif, heic | GOT-OCR2 text extraction |
| **Spreadsheets** | csv, xls, xlsx | Direct parsing + analysis |
| **Text** | txt, md, json, xml, yaml | Direct content extraction |

### Supported Languages

**Translation output** — Hindi • Tamil • Telugu • Bengali • Marathi • Gujarati •
Kannada • Malayalam • Punjabi • Odia, via IndicTrans2.

**Retrieval** is multilingual through BGE-M3, and works across languages: a
question asked in one language finds passages written in another. Measured
against an English-only Class 10 Science corpus:

| Asked in | Question | Retrieved | |
|---|---|---|---|
| Hindi | मानव आँख अलग-अलग दूरी पर कैसे फोकस करती है? | ch10, hypermetropia | ✅ 0.672 |
| Marathi | विद्युत प्रवाह म्हणजे काय? | ch11, Electricity | ✅ 0.637 |
| Bengali | মানুষের হৃদয় কীভাবে কাজ করে? | ch5, circulation | ✅ 0.596 |
| Hindi | प्रकाश संश्लेषण क्या है? | ch9, Light | ❌ wanted ch5 |
| Tamil | ஒளிச்சேர்க்கை என்றால் என்ன? | ch11, Electricity | ❌ wanted ch5 |

The failures share a cause worth knowing: compound scientific terms. Both
प्रकाश संश्लेषण and ஒளிச்சேர்க்கை mean *photosynthesis* and both begin with the
word for *light*, and retrieval followed the component rather than the compound.
Tamil is the weakest of the languages tried. A reranking pass would likely
recover these — `BGEReranker` exists in the codebase but is not wired into the
retrieval path.

**Corpus** is a separate question from either. NCERT publishes in three
languages only — English, Hindi and Urdu — so that is the ceiling on what can
be ingested, whatever the model understands. Of the 558 books in the catalog:
208 English, 190 Hindi, 160 Urdu. There are no NCERT textbooks in Tamil,
Telugu, Bengali or the other languages listed above.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                     │
│              TypeScript • TailwindCSS • Shadcn/UI               │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Backend (FastAPI)                          │
│     REST API • JWT Auth • Rate Limiting • Multi-Tier Cache      │
└─────────────────────────────────────────────────────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐
│   PostgreSQL    │    │   Multi-Tier     │    │  Unified Pipeline │
│ pgvector + HNSW │    │     Cache        │    │   (Optimized)     │
└─────────────────┘    │  L1: Memory      │    └───────────────────┘
                       │  L2: Redis       │              │
                       │  L3: SQLite      │              ▼
                       └──────────────────┘    ┌───────────────────┐
                                               │   Device Router   │
                                               │  GPU│MPS│ANE│CPU  │
                                               └───────────────────┘
                                                         │
                    ┌────────────────┬──────────────────┼──────────────────┐
                    ▼                ▼                  ▼                  ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
           │     MLX      │ │   CoreML     │ │     MPS      │ │   vLLM/HF    │
           │  (Apple M4)  │ │ (ANE 38TOPS) │ │   (Metal)    │ │   (CUDA)     │
           └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
                    │                │                │                │
                    ▼                ▼                ▼                ▼
           ┌──────────────────────────────────────────────────────────────┐
           │                        ML Models                             │
           │  Qwen2.5-3B • IndicTrans2 • GOT-OCR • Gemma-2-2B • BGE-M3    │
           │  Whisper V3 Turbo • Edge TTS • MMS-TTS • BGE-Reranker        │
           └──────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18 • TypeScript 5 • Vite 5 • TailwindCSS • Shadcn/UI |
| **Backend** | FastAPI • SQLAlchemy 2.0 • Pydantic v2 • Celery |
| **Database** | PostgreSQL 17 • pgvector • HNSW indexes |
| **Cache** | Multi-Tier: L1 (LRU) → L2 (Redis) → L3 (SQLite) |
| **ML/AI** | PyTorch • MLX (Apple Silicon) • CoreML • Transformers • vLLM |
| **Inference** | DeviceRouter: MLX/CoreML/MPS/CUDA with auto-selection |
| **Resilience** | Circuit Breakers • Graceful Degradation |
| **Observability** | OpenTelemetry • Prometheus • Grafana • Sentry |
| **Infrastructure** | Docker • Kubernetes |

---

## Project Status

The capability table above describes what the codebase is built to do. This
section describes what is currently verified, so you can tell the two apart.

**Verified**

- 72 routes register and the app boots.
- The tutor answers in 13 languages independently of the question's language —
  Hinglish in, English out, verified end to end.
- Illustrations are drawn by an image model in ~5 s and blank frames are
  rejected rather than shown.
- Reading support measurably lowers decoding load: grade 6.9 against the NCERT
  source's 7.0, having first made it *worse* at 8.2 before the measure-and-keep
  -the-better loop was added.
- BGE-M3 loads at half precision: 1,083 MB instead of 2,166, roughly twice the
  encode speed, cosine 0.999999 against float32.
- 445 tests, no failures. Roughly 33 skip themselves when a prerequisite is
  absent — no running server for the e2e suite, no loaded model for the
  benchmarks, no greenlet for the async-database tests.
- Auth: bcrypt hashing at 12 rounds, JWT access/refresh with the token type
  enforced in both directions, forged signatures and expired tokens rejected.
- Response caching and per-route metrics across the v2 API, keyed per caller
  so no response crosses between users.
- Upload endpoints enforce a 100 MB cap and a file-type allowlist.
- Production startup refuses to boot on a missing JWT secret, a missing
  `DATABASE_URL`, disabled rate limiting, or a wildcard CORS origin combined
  with credentials.

**Not yet implemented** — referenced in tests or docs, absent from the API:

- `/api/v2/content/` CRUD. Content goes through `/api/v2/content/process`.
- `/api/v2/experiments/` (the A/B testing surface).
- `/api/v2/admin/backup/*`.
- `/api/v2/library`.

**Known gaps**

- Retrieval quality depends on how much of the catalog a deployment has
  ingested. The pipeline reaches all 558 books; a fresh clone starts at zero
  and fills as the ingestion runs, so a question about a class whose books are
  not yet loaded returns "the curriculum library has nothing on this yet"
  rather than guessing.
- `WriteBehindQueue.put` is synchronous while `cache.set` awaits it; four
  cache tests are skipped pending that refactor.
- 33 handlers return internal exception text to the client via
  `detail=str(e)`, which leaks paths and driver errors.
- Rate limiting is off in the shipped `.env`. Startup now refuses to run that
  way in production, but local defaults remain permissive.
- Output filtering is off and the age gate is inert. This is deliberate — see
  [Content Policy](#content-policy) — but it is a gap if you are deploying to
  minors.

---

## Quick Start

### Prerequisites

- **Python 3.11** (recommended) — See [Python Version Note](#python-version-note) below
- Node.js 20+
- Redis 7+
- PostgreSQL 17+ (or Supabase), with the **pgvector** extension

pgvector is not optional if you want retrieval: without it the app still boots
and logs `Could not enable pgvector extension`, but RAG and Q&A fall back to
degraded behaviour.

```bash
brew install pgvector
psql -d shiksha_setu -c 'CREATE EXTENSION IF NOT EXISTS vector;'
```

**Check which PostgreSQL the extension landed in.** Homebrew's pgvector formula
builds only against the PostgreSQL versions it currently supports, so on a
machine running an older server the install succeeds and the extension is still
missing — `CREATE EXTENSION` then fails with `could not open extension control
file .../postgresql@14/extension/vector.control`, which reads like pgvector is
absent when it is merely installed elsewhere.

```bash
# Where did the extension actually go?
find /opt/homebrew -name vector.control

# Which server is running?
psql --version
```

If those disagree, either point `DATABASE_URL` at a server version pgvector
supports, or build the extension against your own:

```bash
git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git
cd pgvector
make PG_CONFIG=/opt/homebrew/opt/postgresql@14/bin/pg_config
make install PG_CONFIG=/opt/homebrew/opt/postgresql@14/bin/pg_config
```

### Setup

```bash
git clone https://github.com/rachitranka25/SHIKSHASETU.git
cd SHIKSHASETU
./setup.sh
```

The setup script:
- Creates Python virtual environment
- Installs backend dependencies
- Installs frontend dependencies
- Generates secure JWT secret
- Initializes database schema
- Creates required directories

### Run

```bash
./start.sh
```

Starts:
- Backend API (port 8000)
- AI Pipeline (8 models ready)
- Frontend (port 3000)

Access: http://localhost:3000

### Stop

```bash
./stop.sh
```

---

## Python Version Note

**Why Python 3.11?**

This project requires **Python 3.11** specifically (not newer versions) for optimal ML/AI stack compatibility:

| Reason | Explanation |
|--------|-------------|
| **Pre-built Wheels** | All ML packages (PyTorch, MLX, Transformers, etc.) have pre-built wheels for 3.11, avoiding compilation |
| **Proven Stability** | Python 3.11 is mature and thoroughly tested with production ML frameworks |
| **Package Support** | Some packages don't yet support Python 3.13+ (e.g., verovio requires compilation on 3.14) |
| **Performance** | Python 3.11 includes significant performance improvements (~25% faster than 3.10) |
| **Apple Silicon** | MLX and CoreML tools are optimized and tested for Python 3.11 |

**Tested Package Versions (Python 3.11):**
- PyTorch 2.9.1, Transformers 4.57.3, MLX 0.30.0
- Sentence-Transformers 3.4.1, FastAPI 0.123.2
- Edge-TTS 7.2.3, Verovio 5.6.0

**Installation (macOS):**
```bash
brew install python@3.11
```

---

## Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Chat Interface | http://localhost:3000/chat |
| Settings | http://localhost:3000/settings |
| Backend API (V2) | http://localhost:8000/api/v2 |
| Health Check | http://localhost:8000/api/v2/health |
| Hardware Status | http://localhost:8000/api/v2/hardware/status |
| Models Status | http://localhost:8000/api/v2/models/status |
| API Documentation | http://localhost:8000/docs |
| Prometheus Metrics | http://localhost:8000/metrics |

### V2 API Quick Reference

```bash
# Guest chat (no auth required)
curl -X POST http://localhost:8000/api/v2/chat/guest \
  -H "Content-Type: application/json" \
  -d '{"message": "What is photosynthesis?", "language": "hi", "grade_level": 5}'

# Streaming chat with conversation history (v2.3.1+)
curl -X POST http://localhost:8000/api/v2/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can you explain more?",
    "history": [
      {"role": "user", "content": "What is AI?"},
      {"role": "assistant", "content": "AI stands for Artificial Intelligence..."}
    ]
  }'

# Content simplification
curl -X POST http://localhost:8000/api/v2/content/simplify \
  -H "Content-Type: application/json" \
  -d '{"text": "Complex text here", "target_grade": 5}'
```

---

## Scripts

### Start/Stop (v3.3)

```bash
# Start all services
./start.sh                    # Full start with Docker
./start.sh --skip-docker      # Skip Docker (use existing containers)
./start.sh --quick            # Quick start (minimal checks)
./start.sh --monitoring       # Include Prometheus + Grafana

# Stop all services
./stop.sh                     # Graceful stop (keeps Docker containers)
./stop.sh --all               # Stop everything including Docker
./stop.sh --force             # Force kill immediately
./stop.sh --status            # Show optimization metrics before stopping
```

### Validation & Testing

```bash
# Full test suite
venv/bin/python -m pytest

# One area, with names
venv/bin/python -m pytest tests/unit -v

# Coverage (pytest.ini requires 70%)
venv/bin/python -m pytest --cov=backend
```

Suites live under `tests/`: `unit/`, `integration/`, `e2e/`, `performance/`,
`manual/`. The e2e suite skips itself unless a backend is already serving on
`localhost:8000`, so start the app first if you want it to run.

---

## Project Structure

```
shiksha_setu/
├── README.md                 # This file
├── CHANGELOG.md              # Version history
├── requirements.txt          # Python dependencies
├── requirements.dev.txt      # Development dependencies
├── docker-compose.yml        # Docker orchestration
├── setup.sh                  # Setup script
├── start.sh                  # Start services (v3.3)
├── stop.sh                   # Stop services (v3.3)
│
├── bin/                      # Executable scripts
│   ├── start                 # Start services
│   ├── stop                  # Stop services
│   ├── test                  # Run tests
│   ├── validate              # System validation
│   └── smoke-test            # Quick smoke tests
│
├── backend/                  # FastAPI application (v4.1.0)
│   ├── api/                  # Routes & endpoints
│   │   ├── main.py           # Application entry (V2 only)
│   │   └── routes/
│   │       ├── v2_api.py     # Consolidated V2 API (all endpoints)
│   │       ├── health.py     # Health checks
│   │       └── helpers.py    # Route utilities
│   ├── core/                 # Core modules
│   │   ├── config.py         # Settings
│   │   ├── hardware_optimizer.py  # Apple Silicon detection
│   │   ├── ane_inference.py  # Neural Engine integration
│   │   └── optimized/        # M4 5-Phase Optimizations
│   │       ├── device_router.py    # GPU/MPS/ANE routing
│   │       ├── async_optimizer.py  # Phase 1: Async-first
│   │       ├── gpu_pipeline.py     # Phase 3: GPU queue pipelining
│   │       ├── core_affinity.py    # Phase 4: P/E core routing
│   │       └── memory_pool.py      # Phase 5: Buffer pools
│   ├── cache/unified/        # Multi-tier cache (L1/L2/L3)
│   │   ├── multi_tier_cache.py  # BloomFilter, AdaptiveTTL, LZ4
│   │   └── fast_serializer.py   # Phase 2: msgpack serialization
│   ├── services/             # Business logic
│   │   ├── pipeline/         # AI pipeline orchestration
│   │   ├── inference/        # ML backends (MLX/CoreML)
│   │   ├── ocr.py            # GOT-OCR2 service
│   │   ├── rag.py            # RAG Q&A system
│   │   ├── review_queue.py   # Teacher review system
│   │   └── student_profile.py # Student profiles
│   ├── models/               # SQLAlchemy models
│   └── tasks/                # Celery tasks
│
├── frontend/                 # React + TypeScript + Vite (v2.1.0)
│   └── src/
│       ├── pages/            # Auth, Chat, LandingPage, Settings
│       ├── components/       # Chat, Landing, UI, System components
│       ├── context/          # SystemStatusContext, ThemeContext
│       ├── api/              # V2 API client + system status
│       └── store/            # Zustand state management
│
├── tests/                    # Test suite
├── infrastructure/           # DevOps configs
├── docs/                     # Documentation
│   ├── BACKEND.md            # Backend architecture
│   ├── FRONTEND.md           # Frontend architecture
│   └── ai_pipeline.md        # AI pipeline details
├── alembic/                  # Database migrations
└── data/                     # Data storage
    ├── audio/                # Generated audio files
    ├── captions/             # Caption files
    ├── models/               # ML model cache
    └── uploads/              # User uploads
```

---

## LLM Provider

Text generation can run on-device or through NVIDIA NIM. Everything else —
translation, OCR, TTS, STT, embeddings — is always on-device.

```bash
LLM_PROVIDER=local    # Qwen2.5-3B via MLX/MPS. Nothing leaves the machine.
LLM_PROVIDER=nvidia   # NVIDIA NIM, with automatic fallback to local on failure.
```

`local` is the default, deliberately: under `nvidia`, student prompts are sent
to NVIDIA's servers. That is a privacy decision, so it has to be made rather
than inherited. A hosted failure degrades to the local model instead of
failing the request, which is why the local stack stays installed either way.

Model choice matters more than it looks. Measured against this endpoint with
the same prompt and roughly 70 completion tokens:

| Model | Latency |
|---|---|
| `meta/llama-3.1-8b-instruct` (default) | **0.9s** |
| `nvidia/nvidia-nemotron-nano-9b-v2` | 2.5s |
| `meta/llama-3.3-70b-instruct` | 17–125s, highly variable |

A student waiting on a chat reply needs the first row. Override
`NVIDIA_LLM_MODEL` for batch work where quality outweighs latency.

Get a key at [build.nvidia.com](https://build.nvidia.com). Keep it in `.env`,
which is gitignored — never in `.env.example` or any tracked file.

---

## Environment Configuration

Key variables in `.env`:

```bash
# Application
ENVIRONMENT=development
DEBUG=true

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/shiksha_setu

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
JWT_SECRET_KEY=<auto-generated>

# ML Models (2025 Optimal Stack)
DEVICE=auto                    # auto | cuda | mps | cpu
USE_QUANTIZATION=true

# Model IDs
SIMPLIFICATION_MODEL_ID=Qwen/Qwen2.5-3B-Instruct
TRANSLATION_MODEL_ID=ai4bharat/indictrans2-en-indic-1B
VALIDATION_MODEL_ID=google/gemma-2-2b-it
EMBEDDING_MODEL_ID=BAAI/bge-m3
RERANKER_MODEL_ID=BAAI/bge-reranker-v2-m3
TTS_MODEL_ID=facebook/mms-tts-hin
WHISPER_MODEL_ID=openai/whisper-large-v3-turbo

# TTS Configuration
EDGE_TTS_ENABLED=true          # Use Edge TTS as primary (online)
MMS_TTS_FALLBACK=true          # Use MMS-TTS as fallback (offline)
```

See `.env.example` for complete configuration.

---

## API Overview

### V2 API (Current - Recommended)

All endpoints are consolidated under `/api/v2/` with full hardware optimization.

#### Authentication
- `POST /api/v2/auth/register` — Create account
- `POST /api/v2/auth/login` — Get tokens
- `POST /api/v2/auth/refresh` — Refresh access token
- `GET /api/v2/auth/me` — Get current user

#### Chat
- `POST /api/v2/chat` — Authenticated chat
- `POST /api/v2/chat/stream` — Streaming chat (SSE)
- `POST /api/v2/chat/guest` — Guest chat (no auth)
- `GET /api/v2/chat/conversations` — List conversations
- `POST /api/v2/chat/conversations` — Create conversation
- `GET /api/v2/chat/conversations/{id}` — Get conversation
- `GET /api/v2/chat/conversations/{id}/messages` — Get messages
- `DELETE /api/v2/chat/conversations/{id}` — Delete conversation

#### Content Processing
- `POST /api/v2/content/process` — Full pipeline (simplify + translate + validate + TTS)
- `POST /api/v2/content/process/stream` — Full pipeline with streaming progress
- `POST /api/v2/content/simplify` — Simplify text (Qwen2.5-3B)
- `POST /api/v2/content/translate` — Translate (IndicTrans2)
- `POST /api/v2/content/tts` — Text-to-Speech (MMS-TTS/Edge TTS)
- `GET /api/v2/content/tts/voices` — List TTS voices

#### Speech-to-Text (Whisper V3 Turbo)
- `POST /api/v2/stt/transcribe` — Transcribe audio
- `GET /api/v2/stt/languages` — List supported languages

#### OCR (GOT-OCR2)
- `POST /api/v2/ocr/extract` — Extract text from images
- `GET /api/v2/ocr/capabilities` — Get OCR capabilities

#### Embeddings & Reranking (BGE-M3)
- `POST /api/v2/embeddings/generate` — Generate embeddings
- `POST /api/v2/embeddings/rerank` — Rerank documents

#### Q&A (RAG)
- `POST /api/v2/qa/process` — Process document for Q&A
- `POST /api/v2/qa/ask` — Ask questions

#### Progress & Quizzes
- `GET /api/v2/progress/stats` — User progress
- `POST /api/v2/progress/quiz/generate` — Generate quiz
- `POST /api/v2/progress/quiz/submit` — Submit answers

#### Embeddings
- `POST /api/v2/embeddings/generate` — Generate embeddings (BGE-M3)
- `POST /api/v2/embeddings/rerank` — Rerank documents (BGE-Reranker-v2-M3)
- `POST /api/v2/embed` — Generate embeddings (alternative)

#### Teacher Review
- `GET /api/v2/review/pending` — Get pending reviews
- `GET /api/v2/review/{response_id}` — Get flagged response
- `POST /api/v2/review/{response_id}/submit` — Submit review
- `GET /api/v2/review/stats` — Review statistics

#### Student Profile
- `GET /api/v2/profile/me` — Get student profile
- `PUT /api/v2/profile/me` — Update profile

#### AI Core
- `POST /api/v2/ai/explain` — Explain content
- `GET /api/v2/ai/prompts` — List prompts
- `POST /api/v2/ai/safety/check` — Safety check

#### Admin
- `POST /api/v2/admin/backup` — Create backup
- `GET /api/v2/admin/backups` — List backups

#### System
- `GET /api/v2/health` — Health check with device info
- `GET /api/v2/health/detailed` — Detailed health check
- `GET /api/v2/stats` — API statistics
- `GET /health` — Basic health check
- `GET /metrics` — Prometheus metrics

---

## Testing

```bash
# Activate environment
source venv/bin/activate

# All tests
pytest tests/

# With coverage
pytest tests/ --cov=backend --cov-report=html

# Frontend tests
cd frontend && npm test
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Redis connection failed | Start Redis: `redis-server` |
| Database connection error | Check `DATABASE_URL` in `.env` |
| Model loading slow | First run downloads models (~10GB) |
| CUDA out of memory | Set `USE_QUANTIZATION=true` |
| Port already in use | Run `./stop.sh` first |

---

## License

MIT — see [LICENSE](LICENSE). Third-party component and model licences are
listed in [NOTICE.md](NOTICE.md); model weights are downloaded at runtime and
several carry terms more restrictive than this repository's, so check them
before deploying commercially.

---

⸻

Created by: **Rachit Ranka**
Email: rankarachit5@gmail.com


