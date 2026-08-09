"""
Cloud OCR through NVIDIA NIM
============================

An OCR engine for pages whose PDF text layer cannot be trusted, using the same
NIM endpoint the LLM provider already talks to.

This exists because the local option does not work here. GOT-OCR2 is the OCR
backend the project is built around, and its own modeling code hardcodes CUDA:

    modeling_GOT.py:561   input_ids = torch.as_tensor(...).cuda()
    modeling_GOT.py:572   images=[image_tensor_1.unsqueeze(0).half().cuda()]

On Apple Silicon that raises "Torch not compiled with CUDA enabled", so the
documented OCR path cannot run on the hardware the project documents itself as
targeting. A hosted vision model needs no GPU at all.

Verified on the page this was built for — Class 10 Maths chapter 4, whose text
layer turns "a ≠ 0" into "a  0":

    text layer   ax2 + bx + c, a  0
    this engine  ax2 + bx + c, a ≠ 0

The inequality comes back. The superscript stays flat, which is wrong to read
but does not invert a constraint the way a missing ≠ does.

PRIVACY: page images are sent to NVIDIA. That is a real change in posture for a
local-first project, which is why OCR is opt-in per run rather than automatic.
Textbook pages are public material, so the trade is mild here; it would not be
for a student's uploaded work.

Interface-compatible with GOTOCR2.ocr_image(), so ncert_ingest can take either.
"""

import base64
import logging
import time

import httpx

from ...core.config import settings

logger = logging.getLogger(__name__)

# Vision-capable model on the NIM endpoint. nemotron-parse rejects a text part
# in the request ("The model does not support text input"), so it cannot be
# prompted this way; this one accepts an image plus an instruction.
DEFAULT_MODEL = "nvidia/nemotron-nano-12b-v2-vl"

PROMPT = (
    "Transcribe all text on this page exactly as printed. Preserve mathematical "
    "notation, symbols, superscripts and subscripts. Do not summarise, explain, "
    "or add commentary. Output only the transcription."
)

_RETRYABLE = frozenset({408, 429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3
_RETRY_DELAY = 3.0


class NvidiaOCRError(RuntimeError):
    """An OCR request failed. Never carries the API key."""


class NvidiaVisionOCR:
    """OCR by asking a hosted vision model to transcribe a page image."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 4096,
        timeout: float = 180.0,
    ):
        self.api_key = api_key if api_key is not None else settings.NVIDIA_API_KEY
        self.base_url = base_url or settings.NVIDIA_BASE_URL
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _redact(self, text: str) -> str:
        """Keep the key out of logs and exceptions."""
        return text.replace(self.api_key, "***") if self.api_key else text

    def ocr_image(self, image, mode: str = "format") -> str:
        """
        Transcribe a page image.

        Args:
            image: Path to an image file, or PIL Image.
            mode: Accepted for interface compatibility with GOTOCR2 and ignored;
                this engine has one transcription mode.

        Returns:
            The transcribed text, or "" if the request could not be completed —
            matching GOTOCR2, so callers keep their existing fallback to the
            embedded text layer.
        """
        if not self.is_configured:
            raise NvidiaOCRError("NVIDIA_API_KEY is not set")

        payload = self._payload(self._encode(image))
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "NVIDIA OCR unreachable (attempt %s/%s): %s",
                    attempt, _MAX_ATTEMPTS, self._redact(str(exc)),
                )
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_DELAY * attempt)
                continue

            if response.status_code == 200:
                return self._content(response.json())

            if response.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS:
                logger.warning(
                    "NVIDIA OCR HTTP %s (attempt %s/%s), retrying",
                    response.status_code, attempt, _MAX_ATTEMPTS,
                )
                time.sleep(_RETRY_DELAY * attempt)
                continue

            logger.error(
                "NVIDIA OCR failed with HTTP %s: %s",
                response.status_code, self._redact(response.text)[:200],
            )
            return ""

        return ""

    @staticmethod
    def _encode(image) -> str:
        """Base64-encode a page image from a path or a PIL Image."""
        import io
        from pathlib import Path

        if isinstance(image, (str, Path)):
            data = Path(image).read_bytes()
        else:
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            data = buffer.getvalue()

        return base64.b64encode(data).decode("ascii")

    def _payload(self, image_b64: str) -> dict:
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            # Transcription, not generation: any sampling invents text that was
            # never on the page.
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                }
            ],
        }

    @staticmethod
    def _content(body: dict) -> str:
        choices = body.get("choices") or []
        if not choices:
            return ""
        return ((choices[0].get("message") or {}).get("content") or "").strip()
