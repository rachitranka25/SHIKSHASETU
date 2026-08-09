# Third-Party Notices

Shiksha Setu is released under the MIT License (see [LICENSE](LICENSE)).

These notes used to live inside `LICENSE` itself. GitHub detects a project's
license by matching that file against the known license texts, and the extra
prose pushed it below the matching threshold — so the repository showed no
license at all. `LICENSE` is now the unmodified MIT text, and everything that
is not part of the license lives here.

## Dependencies

This project incorporates components from various open-source projects. Each
component retains its original license; consult the respective project for
authoritative terms.

| Component | License |
|---|---|
| FastAPI | MIT |
| Starlette | BSD 3-Clause |
| Pydantic | MIT |
| SQLAlchemy | MIT |
| Alembic | MIT |
| React | MIT |
| Vite | MIT |
| Tailwind CSS | MIT |
| PostgreSQL | PostgreSQL License |
| Redis | BSD 3-Clause |
| PyTorch | BSD 3-Clause |
| Hugging Face Transformers | Apache 2.0 |
| python-jose | MIT |
| bcrypt | Apache 2.0 |

## Models

Model weights are **not** distributed with this repository — they are fetched
from Hugging Face on first run and cached under `data/models/`. Each model
carries its own license, and several are more restrictive than the code that
calls them. Check the licence of every model you intend to ship before
deploying commercially.

| Model | Used for |
|---|---|
| Qwen2.5-3B-Instruct | Text simplification |
| IndicTrans2-1B | Translation into Indian languages |
| Gemma-2-2B-IT | NCERT curriculum validation |
| GOT-OCR2.0 | Document and image OCR |
| Whisper Large V3 Turbo | Speech to text |
| MMS-TTS | Offline text to speech |
| BGE-M3 | Embeddings for retrieval |
| BGE-Reranker-v2-M3 | Retrieval reranking |

## Curriculum content

NCERT and CBSE publish textbooks, syllabi, and question papers under their own
terms. This repository ships no such content; anything ingested at runtime
remains subject to the publisher's terms.
