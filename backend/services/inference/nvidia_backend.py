"""
NVIDIA NIM Backend - Hosted LLM Inference
=========================================

The one hosted path in an otherwise on-device pipeline. Used for text
generation when LLM_PROVIDER=nvidia; translation, OCR, TTS, STT and embeddings
stay local regardless.

NIM exposes an OpenAI-compatible chat-completions API, so this speaks HTTP
directly with httpx (already a dependency) rather than pulling in a vendor SDK.

PRIVACY: prompts sent through here leave the machine and reach NVIDIA's
servers. That is a deliberate trade for speed on hardware that cannot hold a
70B model, and it is why this is opt-in per environment rather than the
default. When it fails, callers fall back to the local model instead of
failing the student's request.

The API key is never logged, never included in an exception message, and never
echoed in a response.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx

from ...core.config import settings

logger = logging.getLogger(__name__)

# Transient conditions worth one retry: NIM cold-starts a model on first hit,
# and shared capacity returns 429 under load.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_RETRY_DELAY_SECONDS = 2.0
_MAX_ATTEMPTS = 2


class NVIDIABackendError(RuntimeError):
    """A NIM request failed. Never carries the API key."""


@dataclass
class NVIDIAConfig:
    """Connection settings for the NIM endpoint."""

    api_key: str
    base_url: str = "https://integrate.api.nvidia.com/v1"
    model: str = "meta/llama-3.3-70b-instruct"
    timeout_seconds: float = 60.0

    @classmethod
    def from_settings(cls) -> "NVIDIAConfig":
        return cls(
            api_key=settings.NVIDIA_API_KEY,
            base_url=settings.NVIDIA_BASE_URL,
            model=settings.NVIDIA_LLM_MODEL,
            timeout_seconds=float(settings.NVIDIA_TIMEOUT_SECONDS),
        )


class NVIDIAInferenceBackend:
    """
    Async client for NVIDIA NIM chat completions.

    One AsyncClient is reused across requests so connections are pooled;
    close() releases it.
    """

    def __init__(self, config: NVIDIAConfig | None = None):
        self.config = config or NVIDIAConfig.from_settings()
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    @property
    def is_configured(self) -> bool:
        """Whether there is a key to authenticate with at all."""
        return bool(self.config.api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            async with self._lock:
                if self._client is None or self._client.is_closed:
                    self._client = httpx.AsyncClient(
                        base_url=self.config.base_url,
                        timeout=httpx.Timeout(self.config.timeout_seconds),
                        headers={
                            "Authorization": f"Bearer {self.config.api_key}",
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                        },
                    )
        return self._client

    def _build_payload(
        self,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
        top_p: float,
        stop: list[str] | None,
        stream: bool,
    ) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream,
        }
        if stop:
            payload["stop"] = stop
        return payload

    def _redact(self, text: str) -> str:
        """
        Strip the API key out of anything headed for a log or an exception.

        Not paranoia: an upstream 401 commonly echoes the offending
        Authorization header back in its body, and httpx transport errors can
        carry the request URL. Redaction happens before truncation so a
        half-sliced key cannot survive either.
        """
        if self.config.api_key:
            return text.replace(self.config.api_key, "***")
        return text

    def _fail(self, status_code: int, body: str) -> NVIDIABackendError:
        """
        Build an error from a failed response.

        Only the status and a redacted, truncated body go in.
        """
        return NVIDIABackendError(
            f"NVIDIA NIM request failed with HTTP {status_code}: "
            f"{self._redact(body)[:200]}"
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: list[str] | None = None,
    ) -> str:
        """
        Generate a completion.

        Returns:
            The assistant's message text.

        Raises:
            NVIDIABackendError: No key configured, the API refused the request,
                or the response had no usable content.
        """
        if not self.is_configured:
            raise NVIDIABackendError("NVIDIA_API_KEY is not set")

        payload = self._build_payload(
            prompt, system_prompt, max_tokens, temperature, top_p, stop, stream=False
        )
        client = await self._get_client()

        last_error: Exception | None = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await client.post("/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                # Transport-level failure: no response to inspect.
                last_error = NVIDIABackendError(
                    f"NVIDIA NIM unreachable: {self._redact(str(exc))}"
                )
                if attempt < _MAX_ATTEMPTS:
                    await asyncio.sleep(_RETRY_DELAY_SECONDS)
                    continue
                raise last_error from exc

            if response.status_code == 200:
                return self._extract_content(response.json())

            if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_ATTEMPTS:
                logger.warning(
                    "[NVIDIA] HTTP %s on attempt %s/%s, retrying",
                    response.status_code,
                    attempt,
                    _MAX_ATTEMPTS,
                )
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
                continue

            raise self._fail(response.status_code, response.text)

        raise last_error or NVIDIABackendError("NVIDIA NIM request failed")

    @staticmethod
    def _extract_content(body: dict) -> str:
        """Pull the message text out of a chat-completions response."""
        choices = body.get("choices") or []
        if not choices:
            raise NVIDIABackendError("NVIDIA NIM returned no choices")

        content = (choices[0].get("message") or {}).get("content")
        if not content:
            raise NVIDIABackendError("NVIDIA NIM returned an empty message")

        return content

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a completion as text deltas.

        Not retried: once tokens have been handed to the caller, replaying the
        request would duplicate them.
        """
        if not self.is_configured:
            raise NVIDIABackendError("NVIDIA_API_KEY is not set")

        payload = self._build_payload(
            prompt, system_prompt, max_tokens, temperature, top_p, stop, stream=True
        )
        client = await self._get_client()

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            if response.status_code != 200:
                body = (await response.aread()).decode("utf-8", "replace")
                raise self._fail(response.status_code, body)

            async for line in response.aiter_lines():
                delta = self._parse_sse_line(line)
                if delta:
                    yield delta

    @staticmethod
    def _parse_sse_line(line: str) -> str | None:
        """
        Pull the text delta out of one SSE line.

        Returns None for keep-alives, the terminating [DONE] sentinel, and
        chunks that carry no text (role-only openers, finish-reason closers).
        """
        if not line.startswith("data:"):
            return None

        data = line[len("data:") :].strip()
        if not data or data == "[DONE]":
            return None

        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            logger.debug("[NVIDIA] Skipping malformed SSE chunk")
            return None

        choices = chunk.get("choices") or []
        if not choices:
            return None

        return (choices[0].get("delta") or {}).get("content") or None

    async def close(self) -> None:
        """Release the pooled connections."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None


_backend: NVIDIAInferenceBackend | None = None


def get_nvidia_backend() -> NVIDIAInferenceBackend:
    """Process-wide backend singleton."""
    global _backend
    if _backend is None:
        _backend = NVIDIAInferenceBackend()
    return _backend
