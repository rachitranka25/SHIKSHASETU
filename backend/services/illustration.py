"""
Concept illustrations for explanations.

The first attempt at diagrams asked a language model to write SVG. It produced
a rectangle with four words floating in it — "Sun", "Precipitation",
"Evaporation", "Clouds" — and two meaningless curves. That is what a text model
writing raw SVG gives you, and a bigger text model gives you the same thing more
slowly: llama-3.3-70b took 145 seconds to produce fewer elements than the 8B
managed in 8.

The prompt was partly to blame — it forbade colour and asked for "essential
shapes only", to stay theme-neutral — but the deeper problem is that composing
a recognisable scene in SVG coordinates is not something a text model does well.

An image model does. FLUX.1-dev, on the same NVIDIA endpoint the tutor already
uses, draws the water cycle as a sun with rays, a cloud, falling rain, a blue
lake and green trees in five seconds.

WHY THE PICTURES CARRY NO TEXT

Diffusion models garble words. A textbook diagram with misspelt labels is worse
than one with none, so the illustration is asked for without any text at all
and the labels are supplied separately, as real characters, from the
explanation the tutor already produced. Those are accurate, selectable,
translatable and readable by a screen reader — none of which is true of text
baked into a raster image.
"""

import base64
import logging
import time

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

# Image models sit on NVIDIA's genai host, not the OpenAI-compatible one the
# chat models use.
IMAGE_ENDPOINT = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev"

# FLUX accepts only a fixed set of dimensions — 768, 832, 896, 960, 1024, 1088,
# 1152, 1216, 1280, 1344 — and rejects anything else with a 422. 768x512 looked
# like a sensible way to keep the base64 payload small and was refused outright.
# This is the smallest valid landscape pair.
WIDTH = 1024
HEIGHT = 768
STEPS = 30
CFG_SCALE = 3.5
TIMEOUT = 120.0

STYLE = (
    "Flat vector cartoon illustration for a children's school textbook. "
    "Clean white background, bright cheerful colours, simple bold shapes, "
    "no shading, no gradients, no photorealism. "
    "IMPORTANT: no text, no words, no letters, no numbers, no labels anywhere "
    "in the image."
)


class IllustrationError(RuntimeError):
    """Image generation failed. Never carries the API key."""


def _redact(text: str, key: str) -> str:
    return text.replace(key, "***") if key else text


def build_scene_prompt(concept: str, description: str = "") -> str:
    """
    Turn a topic into a description of a picture.

    The concept alone produces something generic, so a sentence of the
    explanation goes in too — it is what distinguishes "the water cycle" as a
    landscape from "the water cycle" as an abstract loop.
    """
    scene = concept.strip()
    if description:
        scene = f"{scene}. {' '.join(description.split())[:280]}"

    return f"Educational illustration showing: {scene}\n\n{STYLE}"


def generate_illustration(
    concept: str,
    description: str = "",
    seed: int | None = None,
) -> str | None:
    """
    Draw a concept.

    Returns:
        A `data:image/png;base64,...` URI, or None when illustration is not
        configured or the request failed. A missing picture must never cost the
        student the explanation, so nothing here raises into the request.
    """
    key = settings.NVIDIA_API_KEY
    if not key:
        logger.debug("No NVIDIA_API_KEY; skipping illustration")
        return None

    payload = {
        "prompt": build_scene_prompt(concept, description),
        "width": WIDTH,
        "height": HEIGHT,
        "steps": STEPS,
        "cfg_scale": CFG_SCALE,
    }
    if seed is not None:
        # A fixed seed makes the same lesson reproduce the same picture, which
        # matters for a textbook and for anyone trying to reproduce a result.
        payload["seed"] = seed

    started = time.perf_counter()

    try:
        response = httpx.post(
            IMAGE_ENDPOINT,
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            json=payload,
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        logger.warning("Illustration unreachable: %s", _redact(str(exc), key))
        return None

    if response.status_code != 200:
        logger.warning(
            "Illustration failed with HTTP %s: %s",
            response.status_code,
            _redact(response.text, key)[:200],
        )
        return None

    artifacts = response.json().get("artifacts") or []
    if not artifacts:
        logger.warning("Illustration returned no image")
        return None

    encoded = artifacts[0].get("base64") or artifacts[0].get("b64_json")
    if not encoded:
        return None

    logger.info(
        "Illustration drawn in %.1fs (%.0f KB)",
        time.perf_counter() - started,
        len(encoded) * 0.75 / 1024,
    )

    # Read the format off the bytes rather than assuming it. FLUX returns JPEG,
    # not PNG — the first version hard-coded image/png, validated against the
    # PNG signature, and threw every picture away.
    try:
        head = base64.b64decode(encoded[:32], validate=False)[:8]
    except Exception:  # noqa: BLE001
        logger.warning("Illustration was not decodable base64")
        return None

    mime = _sniff_mime(head)
    if mime is None:
        logger.warning("Illustration was not a recognised image; discarding")
        return None

    return f"data:{mime};base64,{encoded}"


def _sniff_mime(head: bytes) -> str | None:
    """Image type from its magic bytes, or None if it is not one we serve."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"RIFF") or head[:4] == b"GIF8":
        return None  # not expected from this model; refuse rather than guess
    return None
