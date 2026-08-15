# Running Shiksha Setu on Windows

The setup scripts in `scripts/` are bash, and the README's installation section
is written for macOS. Neither is a requirement of the system: the Python is
portable and the one genuinely awkward dependency, pgvector, is easier to run in
a container than to build. These are the steps that work on Windows.

Tested against Windows 10 and 11 on x86-64. A machine with 8 GB of RAM is
comfortable; 4 GB is the target the paper measures against and works, with the
caveat in the last section.

## 1. Prerequisites

| | Why |
|---|---|
| **Python 3.11** | 3.12 and 3.13 have wheel gaps for some pinned dependencies. Install from python.org and tick *Add python.exe to PATH*. |
| **Docker Desktop** | Runs PostgreSQL with the pgvector extension. Building pgvector by hand on Windows needs a C toolchain and is not worth it. |
| **Node.js 20** | Frontend only. Skip if you only want the API. |
| **Git** | To clone. |

Nothing needs WSL. It works if you have it, but plain PowerShell is enough.

## 2. Database

```powershell
git clone https://github.com/rachitranka25/SHIKSHASETU.git
cd SHIKSHASETU
docker compose up -d postgres
```

That starts `pgvector/pgvector:pg16` on `127.0.0.1:5432` with a named volume, so
the data survives restarts. Confirm it is up:

```powershell
docker compose ps
```

Create the extension once:

```powershell
docker compose exec postgres psql -U postgres -d shiksha_setu -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## 3. Backend

```powershell
py -3.11 -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell refuses to run the activate script, it is the execution policy,
not the project:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Copy `.env.example` to `.env` and set at least these:

```
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/shiksha_setu
JWT_SECRET_KEY=<a long random string, 64 characters or more>
NVIDIA_API_KEY=<your key, for generation>
```

Use `127.0.0.1` rather than `localhost`. On Windows `localhost` can resolve to
IPv6 `::1` first, and the container publishes on IPv4 only, which produces a
connection refused that looks like the database is down when it is not.

Then apply migrations and start the API:

```powershell
alembic upgrade head
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The first request downloads BGE-M3, roughly 2.3 GB, into `data/models`. It is
slow once and cached after.

## 4. Frontend

```powershell
cd frontend
npm ci
npm run dev
```

Then open `http://localhost:3000`.

## 5. The corpus, which is the part people underestimate

A running backend against an empty database answers nothing useful. Retrieval
needs the NCERT corpus ingested: 155 textbooks, 43,621 indexed passages.

```powershell
python scripts/ingest_ncert.py
```

This downloads from NCERT and embeds every chapter. It took about six hours on
an M1 with prefetching; expect the same order on a comparable Windows machine,
longer without a GPU. It is resumable, and a book that fails leaves a marker
naming the reason rather than being retried forever.

If you have access to a machine that has already ingested, a dump is far
quicker: 659 MB of database compresses to about 213 MB and restores in minutes.

On the machine that has the data:

```bash
pg_dump -Fc -Z6 -d shiksha_setu -f shiksha_setu.dump
```

Copy the file across by whatever means you like, then on Windows:

```powershell
docker compose up -d postgres
docker compose exec postgres psql -U postgres -c "CREATE DATABASE shiksha_setu;"
docker compose exec postgres psql -U postgres -d shiksha_setu -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose exec -T postgres pg_restore -U postgres -d shiksha_setu < shiksha_setu.dump
```

Create the extension *before* restoring. The dump contains `vector` columns and
`pg_restore` cannot create them if the type does not exist yet.

Do not put this dump in the repository or a public release. `document_chunks`
holds the textbook text itself, and NCERT owns it. That is also why `data/ncert`
is in `.gitignore`: the catalog is committed, the books are not, and
`scripts/ingest_ncert.py` fetches them from NCERT directly.

Model weights are not in the dump either, and should not be. They are about
2.3 GB for BGE-M3, download from HuggingFace on first use, and cache in
`data/models`.

## 6. What 4 GB actually means

The paper's 4 GB figure is the serving pipeline: the embedder at half precision
and the retrieval path, measured at a 2,094 MB peak resident set. That fits.

Two things do not fit in 4 GB and are not part of it. Ingestion embeds in
batches and wants more headroom. The cross-encoder reranker does not fit beside
the embedder at all: measured on an 8 GB machine the pair drove swap to 12.5 GB
and 435,654 page-ins. It is not in the retrieval path, and on a small machine
you should leave it that way.

If Windows starts paging heavily, the usual cause is running ingestion and
serving at once. Run one at a time.

## 7. Things that were Windows-specific bugs

Recorded because they are the sort of thing that reappears.

- `os.uname()` does not exist on Windows. Two calls in `backend/services/rag.py`
  tested for Apple silicon with it, and since the device is `cpu` on Windows the
  expression was reached and raised `AttributeError` while loading the embedder.
  They use `platform.machine()` now.
- `docker-compose.yml` was a symbolic link to a file that was never committed.
  It dangled everywhere, and git on Windows would not have reproduced a link in
  any case. It is a plain file.
- `sysctl` calls for memory and CPU description are macOS-only and are behind
  `backend/core/platform_info.py`, which uses `psutil` and `platform`.
- Installed memory was read only inside the Apple silicon branch, so on every
  other platform the router saw a machine with 0 GB.
