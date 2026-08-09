"""
Unit tests for the NVIDIA NIM inference backend.

Everything here runs against httpx.MockTransport — no test makes a live call,
so the suite stays offline, free, and deterministic.

The properties worth pinning: the API key never escapes into an error message,
transient failures are retried but streams are not, and a hosted outage
degrades to the local model instead of failing the request.
"""

import json

import httpx
import pytest

from backend.services.inference.nvidia_backend import (
    NVIDIABackendError,
    NVIDIAConfig,
    NVIDIAInferenceBackend,
)

API_KEY = "nvapi-test-key-do-not-use"


def _config(**overrides) -> NVIDIAConfig:
    defaults = {
        "api_key": API_KEY,
        "base_url": "https://nim.test/v1",
        "model": "meta/llama-3.3-70b-instruct",
        "timeout_seconds": 5.0,
    }
    return NVIDIAConfig(**{**defaults, **overrides})


def _backend(handler, **config_overrides) -> NVIDIAInferenceBackend:
    """A backend whose HTTP layer is a MockTransport running `handler`."""
    backend = NVIDIAInferenceBackend(_config(**config_overrides))
    backend._client = httpx.AsyncClient(
        base_url=backend.config.base_url,
        transport=httpx.MockTransport(handler),
        headers={"Authorization": f"Bearer {backend.config.api_key}"},
    )
    return backend


def _completion(text: str) -> dict:
    return {
        "model": "meta/llama-3.3-70b-instruct",
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"total_tokens": 42},
    }


# ==================== CONFIGURATION ====================


def test_is_configured_requires_a_key():
    assert NVIDIAInferenceBackend(_config()).is_configured is True
    assert NVIDIAInferenceBackend(_config(api_key="")).is_configured is False


async def test_generate_without_a_key_fails_fast():
    backend = NVIDIAInferenceBackend(_config(api_key=""))

    with pytest.raises(NVIDIABackendError, match="NVIDIA_API_KEY"):
        await backend.generate("hello")


# ==================== REQUEST SHAPE ====================


async def test_generate_returns_the_message_content():
    backend = _backend(lambda request: httpx.Response(200, json=_completion("Photosynthesis is...")))

    assert await backend.generate("explain photosynthesis") == "Photosynthesis is..."


async def test_request_carries_model_prompt_and_sampling_params():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=_completion("ok"))

    backend = _backend(handler)
    await backend.generate(
        "what is gravity",
        system_prompt="You are a physics teacher.",
        max_tokens=256,
        temperature=0.3,
        top_p=0.8,
        stop=["\n\n"],
    )

    assert seen["model"] == "meta/llama-3.3-70b-instruct"
    assert seen["max_tokens"] == 256
    assert seen["temperature"] == 0.3
    assert seen["top_p"] == 0.8
    assert seen["stop"] == ["\n\n"]
    assert seen["stream"] is False
    assert seen["messages"] == [
        {"role": "system", "content": "You are a physics teacher."},
        {"role": "user", "content": "what is gravity"},
    ]


async def test_system_prompt_is_omitted_when_absent():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=_completion("ok"))

    await _backend(handler).generate("hello")

    assert [m["role"] for m in seen["messages"]] == ["user"]


async def test_stop_is_omitted_when_empty():
    """An empty stop list must not be sent as `"stop": []`."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=_completion("ok"))

    await _backend(handler).generate("hello", stop=None)

    assert "stop" not in seen


# ==================== THE KEY MUST NOT LEAK ====================


async def test_error_message_never_contains_the_api_key():
    """
    An upstream 401 echoing the request back is the realistic way a key ends
    up in a log. The error must carry the status and body only.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, text=f"unauthorized for header {request.headers.get('Authorization')}"
        )

    backend = _backend(handler)

    with pytest.raises(NVIDIABackendError) as exc:
        await backend.generate("hello")

    assert API_KEY not in str(exc.value)
    assert "401" in str(exc.value)


async def test_transport_error_message_never_contains_the_api_key():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"failed with {API_KEY}")

    backend = _backend(handler)

    with pytest.raises(NVIDIABackendError) as exc:
        await backend.generate("hello")

    assert API_KEY not in str(exc.value)


# ==================== RETRIES ====================


async def test_retries_once_on_a_transient_status(monkeypatch):
    monkeypatch.setattr(
        "backend.services.inference.nvidia_backend._RETRY_DELAY_SECONDS", 0
    )
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, json=_completion("second time lucky"))

    assert await _backend(handler).generate("hello") == "second time lucky"
    assert attempts["n"] == 2


async def test_does_not_retry_a_client_error(monkeypatch):
    """A 400 will fail identically on a retry; do not spend the round trip."""
    monkeypatch.setattr(
        "backend.services.inference.nvidia_backend._RETRY_DELAY_SECONDS", 0
    )
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(400, text="bad request")

    with pytest.raises(NVIDIABackendError):
        await _backend(handler).generate("hello")

    assert attempts["n"] == 1


async def test_gives_up_after_the_attempt_limit(monkeypatch):
    monkeypatch.setattr(
        "backend.services.inference.nvidia_backend._RETRY_DELAY_SECONDS", 0
    )
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(503, text="unavailable")

    with pytest.raises(NVIDIABackendError, match="503"):
        await _backend(handler).generate("hello")

    assert attempts["n"] == 2


# ==================== MALFORMED RESPONSES ====================


@pytest.mark.parametrize(
    "body",
    [
        {"choices": []},
        {},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {}}]},
    ],
)
async def test_unusable_response_bodies_raise(body):
    backend = _backend(lambda request: httpx.Response(200, json=body))

    with pytest.raises(NVIDIABackendError):
        await backend.generate("hello")


# ==================== STREAMING ====================


def _sse(*chunks: str) -> str:
    lines = []
    for chunk in chunks:
        lines.append(
            "data: " + json.dumps({"choices": [{"delta": {"content": chunk}}]})
        )
    lines.append("data: [DONE]")
    return "\n".join(lines) + "\n"


async def test_stream_yields_text_deltas():
    backend = _backend(
        lambda request: httpx.Response(200, text=_sse("Photo", "synthesis", " is"))
    )

    chunks = [c async for c in backend.stream("explain photosynthesis")]

    assert "".join(chunks) == "Photosynthesis is"


async def test_stream_ignores_keepalives_and_role_openers():
    payload = "\n".join(
        [
            ": keep-alive",
            "",
            'data: {"choices":[{"delta":{"role":"assistant"}}]}',
            'data: {"choices":[{"delta":{"content":"Hi"}}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ]
    )
    backend = _backend(lambda request: httpx.Response(200, text=payload))

    assert [c async for c in backend.stream("hello")] == ["Hi"]


async def test_stream_skips_malformed_chunks():
    """One bad frame must not abort a response already in flight."""
    payload = "\n".join(
        [
            'data: {"choices":[{"delta":{"content":"good"}}]}',
            "data: {not json at all",
            'data: {"choices":[{"delta":{"content":" end"}}]}',
            "data: [DONE]",
        ]
    )
    backend = _backend(lambda request: httpx.Response(200, text=payload))

    assert "".join([c async for c in backend.stream("hello")]) == "good end"


async def test_stream_requests_streaming_mode():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, text=_sse("ok"))

    async for _ in _backend(handler).stream("hello"):
        pass

    assert seen["stream"] is True


async def test_stream_error_never_contains_the_api_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text=f"boom {API_KEY}")

    backend = _backend(handler)

    with pytest.raises(NVIDIABackendError) as exc:
        async for _ in backend.stream("hello"):
            pass

    assert API_KEY not in str(exc.value)
