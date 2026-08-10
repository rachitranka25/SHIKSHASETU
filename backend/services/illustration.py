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
    # Without this the model draws correct but tiny subjects in one corner and
    # leaves most of the frame empty — the first life-cycle attempt put four
    # small figures along the bottom edge of an otherwise blank page.
    "Fill the whole frame: large, clear subjects, centred, evenly spaced, "
    "close-up composition with little empty space. "
    "IMPORTANT: no text, no words, no letters, no numbers, no labels anywhere "
    "in the image."
)


# A picture that is very nearly one flat colour has nothing in it.
#
# FLUX sometimes returns a blank frame and still reports finishReason SUCCESS,
# so the API cannot be asked whether it drew anything. Two ways it fails: an
# all-black frame, and a near-white one — "the human life cycle" came back at
# 8 KB with a brightness spread of 2 across the whole image, against 205 for a
# good water cycle. Human figures seem the likelier trigger.
#
# Spread separates the two cases cleanly and needs no knowledge of which
# happened. A real illustration on a white ground still has dark outlines.
MIN_BRIGHTNESS_SPREAD = 40
BLANK_RETRIES = 1


class IllustrationError(RuntimeError):
    """Image generation failed. Never carries the API key."""


def is_blank(raw: bytes) -> bool:
    """
    Whether an image is effectively empty.

    Downsampled to 32x24 first: the question is whether the picture has content
    at all, and a thumbnail answers it for a thousandth of the work.
    """
    try:
        import io

        from PIL import Image

        thumb = Image.open(io.BytesIO(raw)).convert("L").resize((32, 24))
        pixels = list(thumb.getdata())
    except Exception as exc:  # noqa: BLE001 - an unreadable image is unusable anyway
        logger.warning("Could not inspect the illustration: %s", exc)
        return True

    spread = max(pixels) - min(pixels)
    if spread < MIN_BRIGHTNESS_SPREAD:
        logger.info(
            "Illustration came back blank (brightness spread %s, mean %.0f)",
            spread, sum(pixels) / len(pixels),
        )
        return True

    return False


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

    prompt = build_scene_prompt(concept, description)

    # Retry once on a blank frame. A different seed is usually enough; if the
    # subject itself is the problem the second attempt fails the same way and
    # the student simply gets no picture, which is the right outcome.
    for attempt in range(BLANK_RETRIES + 1):
        payload = {
            "prompt": prompt,
            "width": WIDTH,
            "height": HEIGHT,
            "steps": STEPS,
            "cfg_scale": CFG_SCALE,
        }
        if seed is not None:
            # A fixed seed makes the same lesson reproduce the same picture,
            # which matters for a textbook and for reproducing a result.
            payload["seed"] = seed + attempt

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

        try:
            raw = base64.b64decode(encoded)
        except Exception:  # noqa: BLE001
            logger.warning("Illustration was not decodable base64")
            return None

        # finishReason is SUCCESS even for an empty frame, so the picture has to
        # be looked at rather than trusted.
        if is_blank(raw):
            if attempt < BLANK_RETRIES:
                logger.info("Retrying the illustration with a different seed")
                continue
            logger.info("Illustration blank after %s attempts; sending none", attempt + 1)
            return None

        mime = _sniff_mime(raw[:8])
        if mime is None:
            logger.warning("Illustration was not a recognised image; discarding")
            return None

        logger.info(
            "Illustration drawn in %.1fs (%.0f KB, %s)",
            time.perf_counter() - started, len(raw) / 1024, mime,
        )
        return f"data:{mime};base64,{encoded}"

    return None


def _sniff_mime(head: bytes) -> str | None:
    """Image type from its magic bytes, or None if it is not one we serve."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None
