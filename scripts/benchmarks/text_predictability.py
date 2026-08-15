"""
Measure the two signals an AI-text detector actually reads.

Detectors of the GPTZero family do not recognise authorship. They score how
predictable a text is to a language model (perplexity) and how much that
predictability varies from sentence to sentence (burstiness). Formal technical
prose is inherently low-perplexity, which is why real papers get flagged.

This computes both locally with GPT-2, so a revision can be aimed at the
passages that actually score low instead of guessed at. GPT-2 is not the model
any detector runs, so the absolute numbers are not a detector score; the
ranking of passages against each other is the usable part.

    venv/bin/python -u scripts/benchmarks/text_predictability.py <file.pdf|file.tex>
"""

import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIN_WORDS = 6


def load(path: Path) -> str:
    if path.suffix == ".pdf":
        from pypdf import PdfReader

        text = " ".join(p.extract_text() for p in PdfReader(str(path)).pages)
        text = text.split("REFERENCES")[0]
    else:
        text = path.read_text()
        text = re.sub(r"%.*", " ", text)
        text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", text)
        text = re.sub(r"[{}$\\]", " ", text)
    # Numbers and citation markers dominate perplexity in a results paper and
    # say nothing about how the prose reads.
    text = re.sub(r"\[\d+\](,\s*\[\d+\])*", " ", text)
    text = re.sub(r"\bFig\.\s*\d+|\bTABLE\s+[IVX]+|\bSection~?[IVX]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def sentences(text: str) -> list[str]:
    out = []
    for s in re.split(r"(?<=[.!?])\s+", text):
        s = s.strip()
        if len(s.split()) >= MIN_WORDS and sum(c.isdigit() for c in s) < len(s) * 0.25:
            out.append(s)
    return out


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/IEEE_CONFERENCE6_SHIKSHA_SETU.pdf"
    sents = sentences(load(target))
    print(f"{target.name}: {len(sents)} prose sentences\n", flush=True)

    import torch
    from transformers import GPT2LMHeadModel, GPT2TokenizerFast

    print("loading gpt2 ...", flush=True)
    tok = GPT2TokenizerFast.from_pretrained("gpt2")
    model = GPT2LMHeadModel.from_pretrained("gpt2").eval()

    scored = []
    with torch.no_grad():
        for s in sents:
            ids = tok(s, return_tensors="pt", truncation=True, max_length=512).input_ids
            if ids.shape[1] < 2:
                continue
            loss = model(ids, labels=ids).loss.item()
            scored.append((float(torch.exp(torch.tensor(loss))), s))

    ppl = [p for p, _ in scored]
    lens = [len(s.split()) for _, s in scored]
    print(f"\nperplexity   mean {statistics.mean(ppl):7.1f}   median {statistics.median(ppl):7.1f}"
          f"   stdev {statistics.pstdev(ppl):7.1f}")
    print(f"burstiness   sentence-length stdev {statistics.pstdev(lens):.1f}"
          f"   range {min(lens)}-{max(lens)} words")
    low = sum(1 for p in ppl if p < 20)
    print(f"             {low}/{len(ppl)} sentences under perplexity 20 "
          f"({100 * low / len(ppl):.0f}%) -- the predictable end\n")

    print("most predictable sentences (revise these first):\n")
    for p, s in sorted(scored)[:8]:
        print(f"  ppl {p:6.1f}  {s[:135]}")
    print("\nleast predictable (these already read as a person wrote them):\n")
    for p, s in sorted(scored)[-3:]:
        print(f"  ppl {p:6.1f}  {s[:135]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
