"""
Route Optimization Middleware
=============================

Applies v2-level optimizations to every route from one place:

- Response caching for read-heavy GETs and expensive POSTs (simplify /
  translate / tts), backed by the multi-tier UnifiedCache (L1 memory ->
  L2 Redis -> L3 disk).
- AI device routing hints: routes that hit a model get the resolved
  compute backend attached to the request scope, so handlers do not each
  re-ask the DeviceRouter.
- Per-route metrics (request counts, cache hits, latency).

Raw ASGI, not BaseHTTPMiddleware: the same stacking/hanging issue
documented in `unified_middleware.py` applies here.

CACHE CORRECTNESS
-----------------
Cache keys are scoped by the caller's Authorization header, so one
student can never be served another's response. Routes that are
inherently per-user or streaming are listed in NEVER_CACHE_PATTERNS and
skipped outright, and any response carrying Set-Cookie is not stored.

Patterns are tuples of (pattern, ttl/type) rather than dicts — iteration
over a small tuple is faster than dict lookups plus we need
longest-prefix-wins ordering, which a dict does not give us.
"""

import base64
import hashlib
import re
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..cache import CacheTier, get_unified_cache
from ..core.optimized.device_router import TaskType, get_device_router
from ..utils.logging import get_logger

logger = get_logger(__name__)

# ==================== ROUTE PATTERNS ====================
# Ordered most-specific first: _match_prefix returns the first hit, so
# "/api/v2/content/tts/voices" must appear before "/api/v2/content/".

# GET routes worth caching, with TTL in seconds.
CACHEABLE_PATTERNS: tuple[tuple[str, int], ...] = (
    ("/api/v2/content/tts/voices", 3600),  # Voice list changes rarely
    ("/api/v2/chat/tts/voices", 3600),
    ("/api/v2/stt/languages", 3600),
    ("/api/v2/ocr/capabilities", 3600),
    ("/api/v2/policy/modes", 3600),
    ("/api/v2/hardware/benchmarks", 900),
    ("/api/v2/health/detailed", 30),
    ("/api/v2/library", 300),  # 5 min for library
    ("/api/v2/content/", 300),
    ("/api/v2/ai/prompts", 300),
    ("/api/v2/models/status", 60),
    ("/api/v2/hardware/status", 60),
    ("/api/v2/cache/status", 30),
    ("/api/v2/stats", 30),
    ("/api/v2/health", 10),  # Short TTL for health
)

# POST routes whose work is expensive and deterministic enough to cache.
# Keyed on the request body, so identical input reuses the answer.
CACHEABLE_POST_PATTERNS: tuple[tuple[str, int], ...] = (
    ("/api/v2/content/tts", 86400),  # Audio synthesis: slowest, cache a day
    ("/api/v2/content/translate", 21600),
    ("/api/v2/content/simplify", 21600),
    ("/api/v2/embeddings/rerank", 3600),
    ("/api/v2/embeddings/generate", 3600),
    ("/api/v2/content/validate", 3600),
    ("/api/v2/ocr/extract", 3600),
    ("/api/v2/embed", 3600),
)

# Routes that run a model, and which model class they need.
AI_ROUTE_PATTERNS: tuple[tuple[str, TaskType], ...] = (
    ("/api/v2/content/process", TaskType.EMBEDDING),
    ("/api/v2/content/validate", TaskType.EMBEDDING),
    ("/api/v2/content/simplify", TaskType.LLM_INFERENCE),
    ("/api/v2/content/translate", TaskType.TRANSLATION),
    ("/api/v2/content/tts", TaskType.TTS),
    ("/api/v2/embeddings/rerank", TaskType.RERANKING),
    ("/api/v2/embeddings/generate", TaskType.EMBEDDING),
    ("/api/v2/embed", TaskType.EMBEDDING),
    ("/api/v2/stt/transcribe", TaskType.STT),
    ("/api/v2/ocr/extract", TaskType.OCR),
    ("/api/v2/qa/ask", TaskType.LLM_INFERENCE),
    ("/api/v2/ai/explain", TaskType.LLM_INFERENCE),
    ("/api/v2/chat", TaskType.LLM_INFERENCE),
)

# Never cached, for correctness or privacy — checked before anything else.
NEVER_CACHE_PATTERNS: tuple[str, ...] = (
    "/api/v2/auth/",  # Tokens and credentials
    "/api/v2/chat/stream",  # SSE stream
    "/api/v2/content/process/stream",
    "/api/v2/voice/stream",
    "/admin/",  # Admin actions are never idempotent
    "/api/v2/admin/",
    "/api/v2/profile/",  # Per-user
    "/api/v2/progress/",  # Per-user
    "/api/v2/review/",  # Moderation queue, must be live
    "/metrics",
)

# ==================== LIMITS ====================

# Bodies/responses above this are streamed through uncached: holding
# multi-MB blobs in L1 evicts everything useful.
_MAX_BODY_BYTES = 1 << 20  # 1 MiB
_MAX_RESPONSE_BYTES = 4 << 20  # 4 MiB

_HEADER_AUTHORIZATION = b"authorization"
_HEADER_ACCEPT_ENCODING = b"accept-encoding"
_HEADER_SET_COOKIE = b"set-cookie"
_CACHE_STATUS_HEADER = b"x-cache"

# UUIDs and bare numeric ids collapse to {id} for metrics grouping.
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_NUMERIC_SEGMENT_RE = re.compile(r"/\d+(?=/|$)")

# Set by __init__ so the metrics endpoint can reach the live instance.
_instance: "OptimizationMiddleware | None" = None


def _match_prefix(patterns: tuple[tuple[str, Any], ...], path: str) -> Any | None:
    """Return the value of the first pattern that prefixes `path`."""
    for pattern, value in patterns:
        if path.startswith(pattern):
            return value
    return None


class OptimizationMiddleware:
    """Route-level caching, device-routing hints, and metrics."""

    __slots__ = ("_cache", "_device_router", "_metrics", "_routing_cache", "app")

    def __init__(self, app: ASGIApp) -> None:
        global _instance

        self.app = app
        self._cache = get_unified_cache()
        self._device_router = get_device_router()
        self._metrics: dict[str, dict[str, Any]] = {}
        # RoutingDecision per TaskType is stable for a given machine.
        self._routing_cache: dict[TaskType, Any] = {}

        _instance = self

    # ---------- helpers ----------

    def _normalize_path(self, path: str) -> str:
        """Collapse resource ids so metrics group by route, not by row."""
        path = _UUID_RE.sub("{id}", path)
        return _NUMERIC_SEGMENT_RE.sub("/{id}", path)

    def _make_cache_key(
        self,
        request: Any,
        method: str = "get",
        body: bytes = b"",
        auth_token: str = "",
        accept_encoding: str = "",
    ) -> str:
        """
        Build a cache key for a request.

        The digest covers the raw path, sorted query params, the caller's
        credentials, the request body, and the accepted encodings — so
        two callers only share an entry when every one of those matches.
        The readable prefix is the normalized path, purely for debugging.
        """
        path = request.url.path
        query = "&".join(f"{k}={v}" for k, v in sorted(dict(request.query_params).items()))

        raw = f"{path}?{query}|{auth_token}|{accept_encoding}|".encode() + body
        # md5 is a cache key, not a security primitive.
        digest = hashlib.md5(raw, usedforsecurity=False).hexdigest()

        return f"opt:{method.lower()}:{self._normalize_path(path)}:{digest}"

    def _record_metrics(self, path: str, outcome: str, duration: float) -> None:
        """Accumulate per-route counters. Called once per request."""
        entry = self._metrics.get(path)
        if entry is None:
            entry = {
                "total_requests": 0,
                "cache_hits": 0,
                "errors": 0,
                "total_time": 0.0,
            }
            self._metrics[path] = entry

        entry["total_requests"] += 1
        entry["total_time"] += duration
        if outcome == "cache_hit":
            entry["cache_hits"] += 1
        elif outcome == "error":
            entry["errors"] += 1

    def get_metrics(self) -> dict[str, dict[str, Any]]:
        """Per-route metrics with derived averages and hit rates."""
        result: dict[str, dict[str, Any]] = {}
        for path, entry in self._metrics.items():
            total = entry["total_requests"] or 1
            result[path] = {
                "total_requests": entry["total_requests"],
                "cache_hits": entry["cache_hits"],
                "errors": entry["errors"],
                "cache_hit_rate": round(entry["cache_hits"] / total, 4),
                "avg_time_ms": round(entry["total_time"] / total * 1000, 3),
            }
        return result

    def _route_hint(self, path: str) -> dict[str, str] | None:
        """Resolve the compute backend for an AI route, memoized."""
        task_type = _match_prefix(AI_ROUTE_PATTERNS, path)
        if task_type is None:
            return None

        decision = self._routing_cache.get(task_type)
        if decision is None:
            try:
                decision = self._device_router.route(task_type)
            except Exception as exc:  # Router must never break a request
                logger.warning("Device routing failed for %s: %s", task_type, exc)
                return {"task_type": task_type.value}
            self._routing_cache[task_type] = decision

        backend = getattr(decision, "backend", None)
        return {
            "task_type": task_type.value,
            "backend": getattr(backend, "value", str(backend)),
        }

    # ---------- ASGI ----------

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]
        method: str = scope["method"]
        started = time.perf_counter()

        # Fast path: never-cache routes get no bookkeeping beyond metrics.
        for pattern in NEVER_CACHE_PATTERNS:
            if path.startswith(pattern):
                await self.app(scope, receive, send)
                return

        normalized = self._normalize_path(path)

        # Attach the device-routing hint for handlers to honor.
        hint = self._route_hint(path)
        if hint is not None:
            scope.setdefault("state", {})["ai_route"] = hint

        if method == "GET":
            ttl = _match_prefix(CACHEABLE_PATTERNS, path)
            body = b""
        elif method == "POST":
            ttl = _match_prefix(CACHEABLE_POST_PATTERNS, path)
            body = b""
        else:
            ttl = None
            body = b""

        if ttl is None:
            await self.app(scope, receive, send)
            self._record_metrics(normalized, "processed", time.perf_counter() - started)
            return

        # POST caching keys on the body, so it has to be buffered and replayed.
        if method == "POST":
            body, receive = await self._buffer_body(receive)
            if len(body) > _MAX_BODY_BYTES:
                await self.app(scope, receive, send)
                self._record_metrics(
                    normalized, "processed", time.perf_counter() - started
                )
                return

        auth_token = ""
        accept_encoding = ""
        for name, value in scope.get("headers", ()):
            if name == _HEADER_AUTHORIZATION:
                auth_token = hashlib.sha256(value).hexdigest()
            elif name == _HEADER_ACCEPT_ENCODING:
                accept_encoding = value.decode("latin-1")

        from starlette.requests import Request

        key = self._make_cache_key(
            Request(scope),
            method=method,
            body=body,
            auth_token=auth_token,
            accept_encoding=accept_encoding,
        )

        cached = None
        try:
            cached = await self._cache.get(key)
        except Exception as exc:  # A cache outage must not take the API down
            logger.warning("Optimization cache read failed for %s: %s", path, exc)

        if cached is not None:
            await self._send_cached(cached, send)
            self._record_metrics(normalized, "cache_hit", time.perf_counter() - started)
            return

        await self._call_and_store(scope, receive, send, key, ttl, normalized, started)

    async def _buffer_body(self, receive: Receive) -> tuple[bytes, Receive]:
        """Drain the request body, returning it plus a replaying receive."""
        chunks: list[bytes] = []
        messages: list[Message] = []

        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break

        index = 0

        async def replay() -> Message:
            nonlocal index
            if index < len(messages):
                message = messages[index]
                index += 1
                return message
            return await receive()

        return b"".join(chunks), replay

    async def _send_cached(self, cached: dict[str, Any], send: Send) -> None:
        """Replay a stored response, tagged so clients can see the hit."""
        headers = [
            (name.encode("latin-1"), value.encode("latin-1"))
            for name, value in cached["headers"]
        ]
        headers.append((_CACHE_STATUS_HEADER, b"HIT"))

        await send(
            {
                "type": "http.response.start",
                "status": cached["status"],
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": base64.b64decode(cached["body"]),
            }
        )

    async def _call_and_store(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        key: str,
        ttl: int,
        normalized: str,
        started: float,
    ) -> None:
        """Run the route, capturing the response so it can be cached."""
        status = 0
        raw_headers: list[tuple[bytes, bytes]] = []
        chunks: list[bytes] = []
        size = 0
        cacheable = True

        async def capture(message: Message) -> None:
            nonlocal status, raw_headers, size, cacheable

            if message["type"] == "http.response.start":
                status = message["status"]
                raw_headers = list(message.get("headers", ()))
                if status != 200 or any(
                    name == _HEADER_SET_COOKIE for name, _ in raw_headers
                ):
                    # Sessions and errors are never reusable.
                    cacheable = False
                message = {**message, "headers": [*raw_headers, (_CACHE_STATUS_HEADER, b"MISS")]}

            elif message["type"] == "http.response.body" and cacheable:
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > _MAX_RESPONSE_BYTES:
                    cacheable = False
                    chunks.clear()
                else:
                    chunks.append(chunk)

            await send(message)

        try:
            await self.app(scope, receive, capture)
        except Exception:
            self._record_metrics(normalized, "error", time.perf_counter() - started)
            raise

        if cacheable and chunks:
            payload = {
                "status": status,
                "headers": [
                    (name.decode("latin-1"), value.decode("latin-1"))
                    for name, value in raw_headers
                ],
                "body": base64.b64encode(b"".join(chunks)).decode("ascii"),
            }
            try:
                await self._cache.set(key, payload, tier=CacheTier.L2, ttl=ttl)
            except Exception as exc:
                logger.warning("Optimization cache write failed for %s: %s", key, exc)

        self._record_metrics(normalized, "processed", time.perf_counter() - started)


def get_route_optimization_metrics() -> dict[str, Any]:
    """
    Snapshot of the optimization layer, for the metrics endpoint.

    Safe to call before the middleware is installed — it then reports the
    configured patterns with no per-route data.
    """
    try:
        return {
            "total_patterns": (
                len(CACHEABLE_PATTERNS)
                + len(CACHEABLE_POST_PATTERNS)
                + len(AI_ROUTE_PATTERNS)
                + len(NEVER_CACHE_PATTERNS)
            ),
            "cacheable_get": len(CACHEABLE_PATTERNS),
            "cacheable_post": len(CACHEABLE_POST_PATTERNS),
            "ai_routes": len(AI_ROUTE_PATTERNS),
            "never_cache": len(NEVER_CACHE_PATTERNS),
            "middleware_active": _instance is not None,
            "routes": _instance.get_metrics() if _instance is not None else {},
        }
    except Exception as exc:
        return {"error": str(exc)}
