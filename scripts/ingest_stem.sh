#!/bin/bash
# Ingest the mathematics and science strand across classes 1-12, before the
# rest of the catalog.
#
# English medium only. NCERT publishes each chapter in English, Hindi and Urdu;
# they are the same curriculum, so ingesting all three triples the corpus for
# no new content and crowds retrieval with the same passage in three scripts.
# The tutor answers in whatever language the student picked regardless of which
# edition it read — that is what the language selector is for. Hindi-language
# and Urdu-language *subject* textbooks are a separate case and are not part of
# this strand.
#
# 30-odd books instead of 398. Chosen because it is what a student most often asks
# about and what the tutor answers worst without — a Pythagoras question
# against a corpus of class 1-3 picture books returns "this explanation is not
# based on the provided textbook material", which is honest and useless.
#
# Batched for the same reason as ingest_ncert_batched.sh: one process cannot
# hold the embedder and a textbook's PDFs on 8 GB without wedging.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
export INGEST_DATABASE_URL="${INGEST_DATABASE_URL:-postgresql://postgres@localhost:5432/shiksha_setu}"
BATCH="${1:-6}"

while :; do
    pending=$(venv/bin/python - "$BATCH" <<'PY'
import os, re, sys
from pathlib import Path
from sqlalchemy import create_engine, text
sys.path.insert(0, str(Path.cwd()))
from backend.services.ingestion import load_catalog
from backend.services.ingestion.ncert_ingest import DOWNLOAD_DIR

STEM = re.compile(r"mathemat|ganita|maths|science|curiosity|physics|chemistry|biology|magic", re.I)
SKIP = re.compile(r"exemplar|lab manual|supplement|kit", re.I)

engine = create_engine(os.environ["INGEST_DATABASE_URL"])
with engine.connect() as c:
    done = {r[0] for r in c.execute(text(
        "SELECT DISTINCT metadata->>'book_code' FROM processed_content"
        " WHERE metadata->>'source'='NCERT'")) if r[0]}
skip = done | {p.stem for p in DOWNLOAD_DIR.glob("*.unavailable")}

# Codes NCERT serves but its own picker does not list. Class 9 Science and
# Mathematics are both absent from the scraped catalog, yet iesc1dd.zip and
# iemh1dd.zip download fine — verified before this list was written. Class 9 is
# not a year to be missing.
KNOWN_MISSING = ["iesc1", "iemh1"]

remaining = [
    b.code for b in load_catalog()
    if b.code not in skip and b.medium == "English"
    and STEM.search(b.title) and not SKIP.search(b.title)
]
remaining += [c for c in KNOWN_MISSING if c not in skip and c not in remaining]
print(" ".join(remaining[: int(sys.argv[1])]))
PY
) || exit 1

    [ -z "$pending" ] && { echo "STEM strand complete."; break; }

    echo "──── $(echo "$pending" | wc -w | tr -d ' ') books: $pending ────"
    venv/bin/python scripts/ingest_ncert.py --codes $pending --discard-downloads
    sleep 5
done
