"""
Hand-drawn SVG templates for the standard mathematics figures.

Illustrations and diagrams are not the same problem, and one tool does not
serve both.

An image model draws the water cycle beautifully — a sun, clouds, rain, a lake
— because that is a *scene*, and being approximately right is fine. Asked for
the Pythagoras theorem it produced three decorative triangles in autumn
colours, which teaches nothing.

A language model writing SVG does no better. Given a worked example, colours
and explicit instructions, llama-3.1-8b produced a Pythagoras figure with no
recognisable right triangle, squares a tenth of the size they should be, and
five overlapping labels. The coordinates have to be computed, and that is not
what these models do.

In mathematics "nearly right" is wrong. A right angle drawn at 80 degrees, a
hypotenuse that is not the longest side, a square whose area does not match its
side — each teaches the opposite of the lesson.

So the standard figures are drawn here, by hand, once. Each is correct by
construction: the 3-4-5 triangle below really is right-angled, and the squares
really do sit on their sides. The model's remaining job is to pick which figure
a question needs, which it can do reliably.

The templates are parameterised where a parameter is genuinely free — the
lengths in a right triangle, the fraction shaded — and fixed where geometry
fixes it.

Anything not in this catalogue falls through to the image model, which is the
right tool for everything that is a picture rather than a construction.
"""

import logging
import re
from collections.abc import Callable

logger = logging.getLogger(__name__)

VIEWBOX = "0 0 480 360"

# One palette across every figure, so a student reading two diagrams is not
# relearning the colour code. Chosen to stay legible on light and dark.
INK = "#111827"
MAIN = "#2563EB"
PART_A = "#DC2626"
PART_B = "#16A34A"
ACCENT = "#F59E0B"

_HEAD = (
    f'<svg viewBox="{VIEWBOX}" xmlns="http://www.w3.org/2000/svg" '
    'font-family="system-ui, sans-serif" role="img">'
)


def _label(x: float, y: float, text: str, size: int = 17, fill: str = INK) -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="600" '
        f'fill="{fill}" text-anchor="middle">{text}</text>'
    )


def _right_angle_mark(x: float, y: float, dx: float, dy: float, size: float = 14) -> str:
    """
    The small square that marks a right angle.

    dx, dy are unit directions along the two arms, so the mark sits inside the
    angle whichever way the corner faces.
    """
    return (
        f'<path d="M {x + dx * size} {y + dy * 0} '
        f'L {x + dx * size} {y + dy * size} '
        f'L {x} {y + dy * size}" '
        f'fill="none" stroke="{INK}" stroke-width="2"/>'
    )


# ==================== TEMPLATES ====================


def pythagoras(**_) -> str:
    """
    Right triangle with a square on each side.

    A 3-4-5 triangle scaled by 20: legs of 80 and 60, hypotenuse exactly 100.
    Every coordinate below follows from that, so the picture is not an
    approximation of the theorem — it satisfies it.

        A (150,220) right angle
        B (230,220)   a = 80, horizontal
        C (150,160)   b = 60, vertical
        CB            c = sqrt(80^2 + 60^2) = 100

    The square on the hypotenuse is placed along the outward normal
    (60,-80)/100 * 100 = (60,-80), which is why its far corners are (290,140)
    and (210,80) rather than anything eyeballed.
    """
    ax, ay = 150, 220
    bx, by = 230, 220
    cx, cy = 150, 160

    return (
        _HEAD
        + '<title>Pythagoras theorem: squares on the sides of a right triangle</title>'
        # square on side a (below the base)
        + f'<polygon points="{ax},{ay} {bx},{by} {bx},{by + 80} {ax},{ay + 80}" '
          f'fill="{PART_A}" fill-opacity="0.15" stroke="{PART_A}" stroke-width="2.5"/>'
        + _label((ax + bx) / 2, ay + 46, "a² = 64", 15, PART_A)
        # square on side b (left of the vertical leg)
        + f'<polygon points="{ax},{ay} {cx},{cy} {cx - 60},{cy} {ax - 60},{ay}" '
          f'fill="{PART_B}" fill-opacity="0.15" stroke="{PART_B}" stroke-width="2.5"/>'
        + _label(ax - 34, (ay + cy) / 2 + 26, "b² = 36", 15, PART_B)
        # square on the hypotenuse, along the outward normal
        + f'<polygon points="{cx},{cy} {bx},{by} {bx + 60},{by - 80} {cx + 60},{cy - 80}" '
          f'fill="{ACCENT}" fill-opacity="0.18" stroke="{ACCENT}" stroke-width="2.5"/>'
        + _label(cx + 60, cy - 30, "c² = 100", 15, "#B45309")
        # the triangle itself, drawn last so it sits on top
        + f'<polygon points="{ax},{ay} {bx},{by} {cx},{cy}" '
          f'fill="{MAIN}" fill-opacity="0.25" stroke="{MAIN}" stroke-width="3"/>'
        + _right_angle_mark(ax, ay, 1, -1)
        + _label((ax + bx) / 2, ay + 18, "a = 8", 16, MAIN)
        + _label(ax - 26, (ay + cy) / 2 - 8, "b = 6", 16, MAIN)
        + _label((cx + bx) / 2 + 22, (cy + by) / 2 - 8, "c = 10", 16, MAIN)
        + _label(240, 330, "a² + b² = c²   ·   64 + 36 = 100", 18)
        + "</svg>"
    )


def right_triangle(**_) -> str:
    """A right triangle with its parts named. The 3-4-5 again, unadorned."""
    ax, ay = 140, 250
    bx, by = 300, 250
    cx, cy = 140, 130

    return (
        _HEAD
        + "<title>A right-angled triangle</title>"
        + f'<polygon points="{ax},{ay} {bx},{by} {cx},{cy}" '
          f'fill="{MAIN}" fill-opacity="0.15" stroke="{MAIN}" stroke-width="3"/>'
        + _right_angle_mark(ax, ay, 1, -1, 18)
        + _label((ax + bx) / 2, ay + 26, "base", 17, PART_A)
        + _label(ax - 34, (ay + cy) / 2, "height", 17, PART_B)
        + _label((cx + bx) / 2 + 26, (cy + by) / 2 - 10, "hypotenuse", 17, "#B45309")
        + _label(ax + 44, ay - 18, "90°", 15)
        + "</svg>"
    )


def circle_parts(**_) -> str:
    """Centre, radius, diameter and circumference on one circle."""
    cx, cy, r = 240, 175, 110

    return (
        _HEAD
        + "<title>Parts of a circle</title>"
        + f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{MAIN}" fill-opacity="0.12" '
          f'stroke="{MAIN}" stroke-width="3"/>'
        + f'<line x1="{cx - r}" y1="{cy}" x2="{cx + r}" y2="{cy}" '
          f'stroke="{PART_A}" stroke-width="2.5"/>'
        + f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy - r}" '
          f'stroke="{PART_B}" stroke-width="2.5"/>'
        + f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="{INK}"/>'
        + _label(cx - 18, cy - 12, "O", 17)
        + _label(cx + 26, cy - 34, "radius", 16, PART_B)
        + _label(cx, cy + 26, "diameter", 16, PART_A)
        + _label(cx, cy - r - 14, "circumference", 16, MAIN)
        + _label(240, 330, "diameter = 2 × radius", 17)
        + "</svg>"
    )


def number_line(**_) -> str:
    """A number line from -5 to 5, ticked and labelled."""
    left, right, y = 60, 420, 190
    step = (right - left) / 10

    ticks = "".join(
        f'<line x1="{left + i * step}" y1="{y - 10}" x2="{left + i * step}" y2="{y + 10}" '
        f'stroke="{INK}" stroke-width="2"/>'
        + _label(left + i * step, y + 34, str(i - 5), 15)
        for i in range(11)
    )

    return (
        _HEAD
        + "<title>The number line</title>"
        + f'<line x1="{left - 25}" y1="{y}" x2="{right + 25}" y2="{y}" '
          f'stroke="{MAIN}" stroke-width="3"/>'
        + f'<polygon points="{right + 25},{y} {right + 10},{y - 7} {right + 10},{y + 7}" fill="{MAIN}"/>'
        + f'<polygon points="{left - 25},{y} {left - 10},{y - 7} {left - 10},{y + 7}" fill="{MAIN}"/>'
        + ticks
        + f'<circle cx="{left + 5 * step}" cy="{y}" r="6" fill="{PART_A}"/>'
        + _label(left + 5 * step, y - 24, "zero", 16, PART_A)
        + _label(140, 100, "negative ←", 16, PART_B)
        + _label(360, 100, "→ positive", 16, PART_B)
        + "</svg>"
    )


def fraction(numerator: int = 3, denominator: int = 8, **_) -> str:
    """
    A fraction as shaded parts of a circle.

    Sectors are computed from the denominator rather than drawn by eye, so
    three eighths really does occupy three eighths of the area.
    """
    import math

    numerator = max(0, min(int(numerator), 24))
    denominator = max(2, min(int(denominator), 24))
    numerator = min(numerator, denominator)

    cx, cy, r = 190, 175, 110
    parts = []

    for i in range(denominator):
        start = 2 * math.pi * i / denominator - math.pi / 2
        end = 2 * math.pi * (i + 1) / denominator - math.pi / 2
        x1, y1 = cx + r * math.cos(start), cy + r * math.sin(start)
        x2, y2 = cx + r * math.cos(end), cy + r * math.sin(end)
        large = 1 if (end - start) > math.pi else 0
        fill = PART_A if i < numerator else "#FFFFFF"
        opacity = "0.55" if i < numerator else "1"
        parts.append(
            f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} '
            f'A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f} Z" '
            f'fill="{fill}" fill-opacity="{opacity}" stroke="{MAIN}" stroke-width="2"/>'
        )

    return (
        _HEAD
        + f"<title>The fraction {numerator} over {denominator}</title>"
        + "".join(parts)
        + f'<text x="380" y="150" font-size="52" font-weight="700" fill="{PART_A}" '
          f'text-anchor="middle">{numerator}</text>'
        + f'<line x1="340" y1="168" x2="420" y2="168" stroke="{INK}" stroke-width="3"/>'
        + f'<text x="380" y="222" font-size="52" font-weight="700" fill="{INK}" '
          f'text-anchor="middle">{denominator}</text>'
        + _label(380, 268, f"{numerator} of {denominator} equal parts", 15)
        + "</svg>"
    )


# ==================== SELECTION ====================
#
# Keyword matching, not a model call. The set of standard figures is small and
# their names are stable, so a lookup is both faster and more predictable than
# asking a model to choose — and a wrong choice here shows a student the wrong
# mathematics.

TEMPLATES: dict[str, Callable[..., str]] = {
    "pythagoras": pythagoras,
    "right_triangle": right_triangle,
    "circle_parts": circle_parts,
    "number_line": number_line,
    "fraction": fraction,
}

_MATCHERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pythagoras", ("pythagoras", "pythagorean", "baudhayana", "a2 + b2", "a² + b²")),
    ("right_triangle", ("right triangle", "right-angled triangle", "right angled triangle")),
    ("circle_parts", ("radius", "diameter", "circumference", "parts of a circle")),
    ("number_line", ("number line", "integers on a line", "negative numbers")),
    ("fraction", ("fraction", "numerator", "denominator", "parts of a whole")),
)

_FRACTION_RE = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})\b")


def select_template(question: str, answer: str = "") -> tuple[str, dict] | None:
    """
    Find the standard figure a question is asking about.

    Matches the question first and the explanation only as a fallback: the
    explanation may mention a circle in passing while the question is about
    something else entirely.
    """
    for text in (question.lower(), answer.lower()[:600]):
        for name, keywords in _MATCHERS:
            if any(keyword in text for keyword in keywords):
                params: dict = {}
                if name == "fraction":
                    match = _FRACTION_RE.search(question) or _FRACTION_RE.search(answer)
                    if match:
                        params = {
                            "numerator": int(match.group(1)),
                            "denominator": int(match.group(2)),
                        }
                return name, params
    return None


def render(question: str, answer: str = "") -> tuple[str, str] | None:
    """
    Draw the standard figure for a question, if there is one.

    Returns:
        (svg, template name), or None to let the caller fall back to the image
        model — which is the right tool for anything that is a picture rather
        than a construction.
    """
    chosen = select_template(question, answer)
    if chosen is None:
        return None

    name, params = chosen
    try:
        svg = TEMPLATES[name](**params)
    except Exception as exc:  # noqa: BLE001 - a missing figure must not lose the lesson
        logger.warning("Geometry template %r failed: %s", name, exc)
        return None

    logger.info("Geometry template: %s", name)
    return svg, name
