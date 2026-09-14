"""
Find vertical holes in a typeset PDF, anywhere on the page.

An earlier check measured only how far down each page the text reached, which
catches a page that ends early and is blind to a gap in the middle. Two floats
placed at the top and bottom of the same page with nothing between them leave
exactly that, and it reads worse than a short page.

    venv/bin/python scripts/benchmarks/page_gaps.py <file.pdf> [threshold_cm]

Reports every vertical run of empty space taller than the threshold, with the
page it is on, so a float placement can be judged rather than guessed at.
"""

import sys
from pathlib import Path

PT_PER_CM = 28.3465
DEFAULT_CM = 2.0


def page_rows(page) -> list[float]:
    """Baseline y of every non-empty text run on the page."""
    ys: list[float] = []
    page.extract_text(
        visitor_text=lambda t, cm, tm, font, size: ys.append(tm[5]) if t.strip() else None
    )
    return sorted(set(round(y, 1) for y in ys), reverse=True)


def gaps(ys: list[float], line_height: float) -> list[tuple[float, float]]:
    """
    Runs of empty space between consecutive baselines.

    A normal line advance is one line height. Anything materially larger is
    either deliberate (a section break, a float's own surrounding space) or a
    hole; the caller decides using the threshold.
    """
    out = []
    for a, b in zip(ys, ys[1:]):
        d = a - b
        if d > line_height * 1.8:
            out.append((b, d))
    return out


def main() -> int:
    from pypdf import PdfReader

    path = Path(sys.argv[1])
    thresh_cm = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CM
    thresh = thresh_cm * PT_PER_CM
    r = PdfReader(str(path))

    # Estimate the body line advance from the most common small spacing seen,
    # rather than assuming a point size the document may not use.
    deltas = []
    for pg in r.pages:
        ys = page_rows(pg)
        deltas += [a - b for a, b in zip(ys, ys[1:]) if 5 < a - b < 30]
    line = sorted(deltas)[len(deltas) // 2] if deltas else 12.0

    print(f"{path.name}: {len(r.pages)} pages, line advance {line:.1f}pt, "
          f"reporting holes over {thresh_cm:.1f}cm\n")

    worst = 0.0
    found = 0
    for i, pg in enumerate(r.pages, 1):
        ys = page_rows(pg)
        if not ys:
            continue
        holes = [(y, d) for y, d in gaps(ys, line) if d > thresh]
        # The foot of the page counts too: compare against the deepest baseline
        # reached anywhere in the document.
        for y, d in holes:
            found += 1
            worst = max(worst, d)
            print(f"  page {i:2}: {d / PT_PER_CM:4.1f} cm hole")
    deepest = min(min(page_rows(p) or [0]) for p in r.pages if page_rows(p))
    for i, pg in enumerate(r.pages, 1):
        ys = page_rows(pg)
        if not ys or i == len(r.pages):
            continue
        tail = ys[-1] - deepest
        if tail > thresh:
            found += 1
            worst = max(worst, tail)
            print(f"  page {i:2}: {tail / PT_PER_CM:4.1f} cm short at the foot")

    print(f"\n  {found} hole(s), worst {worst / PT_PER_CM:.1f} cm"
          if found else "\n  no holes over threshold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
