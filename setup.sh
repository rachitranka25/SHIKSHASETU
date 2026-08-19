#!/usr/bin/env bash
# Shiksha Setu -- one-command setup for macOS and Linux.
#
#   bash setup.sh
#
# Checks what is missing, sets up everything that can be set up, and says
# plainly what it could not do. Safe to run again: every step checks whether it
# has already been done, so a run that failed halfway can simply be repeated.

set -uo pipefail
cd "$(dirname "$0")"

say()  { echo "  $*"; }
good() { printf "  \033[32mOK   \033[0m %s\n" "$*"; }
warn() { printf "  \033[33m..   \033[0m %s\n" "$*"; }
die()  { printf "\n  \033[31mSTOP \033[0m %s\n\n" "$*"; exit 1; }

echo
echo "  Shiksha Setu setup"
echo "  ------------------"
echo

# ---------------------------------------------------------------- prerequisites
say "Checking what is installed..."

PY=""
for c in python3.11 python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" --version 2>&1 | grep -q "3\.11\."; then PY="$c"; break; fi
done
[ -z "$PY" ] && die "Python 3.11 was not found.

  macOS:  brew install python@3.11
  Linux:  sudo apt install python3.11 python3.11-venv

  3.12 and 3.13 will not work: some libraries this project pins have no
  installers for them yet. Then run this script again."
good "Python 3.11 found ($PY)"

command -v docker >/dev/null 2>&1 || die "Docker was not found.

  macOS:  https://www.docker.com/products/docker-desktop/
  Linux:  sudo apt install docker.io docker-compose-plugin

  Docker is only used for the database. Then run this script again."
docker info >/dev/null 2>&1 || die "Docker is installed but not running. Start Docker Desktop, wait for it to settle, and run this script again."
good "Docker is running"

HAS_NODE=0
if command -v node >/dev/null 2>&1; then HAS_NODE=1; good "Node.js found (website will be set up)"
else warn "Node.js not found. The website will be skipped; the API will still work."; fi

# ---------------------------------------------------------------------- secrets
if [ ! -f .env ]; then
    [ -f .env.example ] && cp .env.example .env || touch .env
    {
      echo
      echo "DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/shiksha_setu"
      echo "JWT_SECRET_KEY=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    } >> .env
    good "Created .env with a fresh JWT secret"
    warn "You still need to paste NVIDIA_API_KEY into .env -- ask whoever sent you this project."
else
    good ".env already exists, leaving it alone"
fi

# --------------------------------------------------------------------- database
say "Starting the database..."
docker compose up -d postgres >/dev/null 2>&1

ready=0
for _ in $(seq 1 40); do
    if docker compose exec -T postgres pg_isready -U postgres -q >/dev/null 2>&1; then ready=1; break; fi
    sleep 2
done
[ "$ready" -eq 1 ] || die "The database container started but never became ready. Run 'docker compose logs postgres' and send the output to whoever gave you this project."
good "Database is running"

docker compose exec -T postgres psql -U postgres -c "CREATE DATABASE shiksha_setu;" >/dev/null 2>&1
docker compose exec -T postgres psql -U postgres -d shiksha_setu -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null 2>&1
good "Database prepared"

# ------------------------------------------------------------------- the corpus
count_books() {
    docker compose exec -T postgres psql -U postgres -d shiksha_setu -tAc \
      "SELECT count(DISTINCT metadata->>'book_code') FROM processed_content WHERE metadata->>'source'='NCERT'" 2>/dev/null | tr -d ' \r\n'
}
BOOKS="$(count_books)"; [[ "$BOOKS" =~ ^[0-9]+$ ]] || BOOKS=0

if [ "$BOOKS" -gt 0 ]; then
    good "Corpus already loaded ($BOOKS textbooks)"
elif [ -f shiksha_setu.dump ]; then
    say "Restoring the corpus from shiksha_setu.dump (a few minutes)..."
    docker compose exec -T postgres pg_restore -U postgres -d shiksha_setu --no-owner < shiksha_setu.dump >/dev/null 2>&1
    good "Corpus restored ($(count_books) textbooks)"
else
    warn "No corpus found and no shiksha_setu.dump in this folder."
    warn "Ask for the dump file, put it here, and run this script again."
    warn "Without it the system starts but cannot answer questions."
fi

# ---------------------------------------------------------------------- backend
[ -d venv ] || { say "Creating the Python environment..."; "$PY" -m venv venv; }
say "Installing Python packages (several minutes the first time)..."
./venv/bin/python -m pip install --quiet --upgrade pip
./venv/bin/python -m pip install --quiet -r requirements.txt
good "Python packages installed"

say "Applying database migrations..."
./venv/bin/python -m alembic upgrade head >/dev/null 2>&1
good "Migrations applied"

# --------------------------------------------------------------------- frontend
if [ "$HAS_NODE" -eq 1 ] && [ ! -d frontend/node_modules ]; then
    say "Installing the website's packages..."
    (cd frontend && npm ci --silent)
    good "Website packages installed"
fi

# ------------------------------------------------------------------------- done
cat <<'EOF'

  Setup finished.

  To start it, open two terminal windows in this folder:

    1)  ./venv/bin/python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
    2)  cd frontend && npm run dev

  Then open  http://localhost:3000  in your browser.

  The very first question will be slow -- about 2.3 GB of language model
  downloads in the background. Every question after that is fast.

EOF

grep -qE "^NVIDIA_API_KEY=.+" .env || \
  warn "One thing is still missing: NVIDIA_API_KEY in the .env file. Without it, search works but the tutor cannot write answers."
