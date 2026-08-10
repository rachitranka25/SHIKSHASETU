#!/bin/bash
# Ingest the NCERT catalog in small batches, one process per batch.
#
# WHY BATCHES
#
# A single process cannot finish the catalog on a machine with 8 GB of RAM.
# BGE-M3 holds ~2.5 GB resident, a textbook zip is up to 70 MB expanded across
# 20-odd PDFs, and Postgres wants its share. Attempting all 558 books in one
# process reached book 8 and then wedged: swap hit 11.4 GB of 12.2 GB, the
# process dropped into uninterruptible I/O wait with its resident set paged
# entirely out, and it made no further progress for eleven minutes. It does not
# recover on its own.
#
# Exiting between batches is what fixes it. The embedder is reloaded each time,
# which costs about 20 seconds, and in exchange every page of the previous
# batch's working set is genuinely returned to the OS.
#
# Resuming is free: books already in the database are skipped by a query, not by
# any on-disk state, so re-running this script continues where it stopped and
# interrupting it costs at most the batch in flight.
#
# USAGE
#     scripts/ingest_ncert_batched.sh [batch_size] [max_batches]
#
#     scripts/ingest_ncert_batched.sh            # 5 at a time, until done
#     scripts/ingest_ncert_batched.sh 3          # smaller batches
#     scripts/ingest_ncert_batched.sh 5 10       # stop after 10 batches
set -uo pipefail

BATCH_SIZE="${1:-5}"
MAX_BATCHES="${2:-0}"   # 0 means keep going until the catalog is exhausted

# What to ingest. "curriculum" is the 263 books the platform teaches from: one
# edition per book, English wherever NCERT publishes one, Hindi for the
# subjects that exist only in Devanagari, never Urdu. See curriculum_scope() in
# backend/services/ingestion/ncert_catalog.py for why.
#
# "all" takes every edition of every book — 559 — which is mostly the same
# curriculum a second and third time in scripts the tutor does not teach out
# of. Only useful for library search coverage:
#     INGEST_SCOPE=all scripts/ingest_ncert_batched.sh
INGEST_SCOPE="${INGEST_SCOPE:-curriculum}"

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

PYTHON="venv/bin/python"
# Shared curriculum is stored with no organization, and row-level security only
# lets the table owner create such rows.
export INGEST_DATABASE_URL="${INGEST_DATABASE_URL:-postgresql://postgres@localhost:5432/shiksha_setu}"

# Refuse to start a batch when memory is genuinely exhausted.
#
# Free swap alone is the wrong signal, and using it stopped a healthy run dead:
# macOS keeps swap allocated after it has been used and grows the file on
# demand, so "937 MB free" was reported while 65% of RAM was idle. What
# actually preceded the wedge was both numbers being bad at once — free memory
# down to 18% with swap nearly full — so both are required now.
memory_free_pct() {
    memory_pressure 2>/dev/null \
        | sed -n 's/.*System-wide memory free percentage: \([0-9]*\)%.*/\1/p'
}

swap_free_mb() {
    sysctl vm.swapusage 2>/dev/null \
        | sed -n 's/.*free = \([0-9.]*\)M.*/\1/p' \
        | cut -d. -f1
}

memory_is_exhausted() {
    local mem swap
    mem="$(memory_free_pct)"
    swap="$(swap_free_mb)"

    [ -z "$mem" ] || [ -z "$swap" ] && return 1          # cannot tell: proceed
    [ "$mem" -lt 20 ] && [ "$swap" -lt 800 ] && return 0 # both bad: stop
    return 1
}

batch=0
while :; do
    batch=$((batch + 1))
    if [ "$MAX_BATCHES" -gt 0 ] && [ "$batch" -gt "$MAX_BATCHES" ]; then
        echo "Reached the requested batch limit."
        break
    fi

    if memory_is_exhausted; then
        echo "Memory is exhausted ($(memory_free_pct)% free, $(swap_free_mb) MB swap)."
        echo "Pausing 180s to let the system settle."
        sleep 180

        if memory_is_exhausted; then
            echo "Still exhausted. Stopping rather than wedging the machine."
            echo "Close other applications, then run this again — progress is kept."
            exit 1
        fi
    fi

    # Pick the next books that are genuinely outstanding.
    #
    # --limit takes the first N of the catalog, which does not advance: the
    # first slots are permanently occupied by books already ingested and by
    # books NCERT never published a zip for. A trial run with --limit reported
    # "0 books ingested, 8 skipped" twice in a row for exactly that reason.
    # Selecting the pending codes explicitly is what makes each batch do work.
    pending=$($PYTHON - "$BATCH_SIZE" "$INGEST_SCOPE" <<'PY'
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path.cwd()))
from backend.services.ingestion import curriculum_scope, load_catalog
from backend.services.ingestion.ncert_ingest import DOWNLOAD_DIR

wanted = int(sys.argv[1])
scope = sys.argv[2] if len(sys.argv) > 2 else "curriculum"

engine = create_engine(os.environ["INGEST_DATABASE_URL"])
with engine.connect() as connection:
    done = {
        row[0]
        for row in connection.execute(
            text(
                "SELECT DISTINCT metadata->>'book_code' FROM processed_content"
                " WHERE metadata->>'source' = 'NCERT'"
            )
        )
        if row[0]
    }

unavailable = {p.stem for p in DOWNLOAD_DIR.glob("*.unavailable")}
skip = done | unavailable

catalog = load_catalog()
books = catalog if scope == "all" else curriculum_scope(catalog)
remaining = [b.code for b in books if b.code not in skip]
print(" ".join(remaining[:wanted]))
print(len(done), len(unavailable), len(remaining), file=sys.stderr)
PY
) || { echo "Could not determine pending books."; exit 1; }

    if [ -z "$pending" ]; then
        echo "Nothing left to ingest."
        break
    fi

    echo
    echo "──── batch $batch [$INGEST_SCOPE] — $(echo "$pending" | wc -w | tr -d ' ') books: $pending ────"

    $PYTHON scripts/ingest_ncert.py --codes $pending --discard-downloads
    status=$?

    if [ "$status" -ne 0 ]; then
        echo "Batch $batch exited $status. Continuing — a failed book is recorded and skipped."
    fi

    # Let the page cache and Postgres settle before loading the model again.
    sleep 10
done
