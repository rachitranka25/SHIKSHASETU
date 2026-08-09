# Shiksha Setu

**Safe, Open AI for Education & Noble Purposes**

A local-first, unrestricted AI platform that empowers learning, research, creativity, and noble causes—while maintaining essential safety guardrails.

---

## Vision

Shiksha Setu is evolving beyond education into a **general-purpose AI** that:
- 🎓 **Educates** — STEM-aligned content, multilingual support, grade adaptation
- 🔬 **Researches** — Unrestricted knowledge exploration for academic work
- 🎨 **Creates** — Assists with writing, coding, analysis, and creative tasks
- 🌍 **Serves Noble Purposes** — Healthcare, accessibility, social good

### Philosophy

> **Safe without being restricted. Powerful without being harmful.**

We block only genuinely dangerous content (weapons, malware, real harm) while trusting users with good intent for everything else.

---

## Overview

Shiksha Setu is a production-grade AI platform that runs entirely locally on Apple Silicon, with no cloud dependencies. It simplifies content, translates to Indian languages, answers questions, and generates audio—all through a unified AI pipeline.

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Text Simplification** | Grade-level adaptation using Qwen2.5-3B-Instruct |
| **Translation** | 10 Indian languages via IndicTrans2-1B |
| **OCR** | Document extraction with GOT-OCR2.0 (95%+ accuracy on Indian scripts) |
| **Validation** | NCERT curriculum alignment using Gemma-2-2B-IT (≥80% threshold) |
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

Hindi • Tamil • Telugu • Bengali • Marathi • Gujarati • Kannada • Malayalam • Punjabi • Odia

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

## Quick Start

### Prerequisites

- **Python 3.11** (recommended) — See [Python Version Note](#python-version-note) below
- Node.js 20+
- Redis 7+
- PostgreSQL 17+ (or Supabase)

### Setup

```bash
git clone https://github.com/rachitranka25/SHIKSHASETU.git
cd shiksha_setu
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
# Run tests
./bin/test                    # Full test suite
./bin/smoke-test              # Quick smoke tests

# Validate system
./bin/validate                # System validation
./bin/validate-production     # Production readiness check
```

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

MIT License — see [LICENSE](LICENSE)

---

⸻

Created by: **Rachit Ranka**
Email: rankarachit5@gmail.com


