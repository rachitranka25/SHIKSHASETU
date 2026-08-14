"""
Memory and CPU facts, on whatever the platform is.

The optimisation code grew up on Apple silicon and asked the operating system
directly: `sysctl -n hw.memsize` for RAM, `sysctl vm.swapusage` for swap,
`getrusage(RUSAGE_SELF).ru_maxrss` for peak footprint. None of those exist on
Windows, and one call site was not even wrapped in a try -- an unhandled
`FileNotFoundError` at import-adjacent code, which is a crash rather than a
degraded feature.

This module answers the same questions through psutil, which is already a
declared dependency and reports the same values on Linux, Windows and macOS.
The point is not portability for its own sake: a platform that only runs on a
Mac cannot honestly claim to serve a 4 GB machine in a school, because those
machines are overwhelmingly Windows.

Peak RSS is the one figure psutil cannot give directly on every platform --
`getrusage` is POSIX-only and Windows exposes a peak through the process
handle -- so `peak_rss_mb()` reads whichever is available and falls back to
current RSS with a flag, rather than silently reporting a smaller number as if
it were the peak.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

import psutil

# macOS reports ru_maxrss in bytes; Linux reports kilobytes. Getting this wrong
# is a factor-of-1024 error in a memory figure, which is exactly the kind of
# number a reader will not sanity-check.
_RU_MAXRSS_IS_BYTES = sys.platform == "darwin"


@dataclass(frozen=True)
class MemorySnapshot:
    """What is free right now, in MB, plus the totals for context."""

    total_mb: float
    available_mb: float
    used_percent: float
    swap_total_mb: float
    swap_free_mb: float

    @property
    def available_percent(self) -> float:
        return 100.0 - self.used_percent


def memory() -> MemorySnapshot:
    """Current memory state. Works on Linux, Windows and macOS alike."""
    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()
    mb = 1024 * 1024

    return MemorySnapshot(
        total_mb=virtual.total / mb,
        available_mb=virtual.available / mb,
        used_percent=virtual.percent,
        swap_total_mb=swap.total / mb,
        swap_free_mb=(swap.total - swap.used) / mb,
    )


def total_memory_gb() -> float:
    """Installed RAM in GB. Replaces `sysctl -n hw.memsize`."""
    return psutil.virtual_memory().total / (1024**3)


def peak_rss_mb() -> tuple[float, bool]:
    """
    Peak resident set of this process in MB, and whether it is really a peak.

    Returns (value, is_true_peak). A false flag means the platform offered no
    high-water mark and the number is current RSS, which understates the peak
    whenever pages have been reclaimed -- `ps` reported 46 MB for a process
    holding a 1 GB model because the machine had swapped it out.
    """
    process = psutil.Process()

    # Windows tracks a genuine peak in the process memory counters.
    info = process.memory_info()
    peak_wset = getattr(info, "peak_wset", None)
    if peak_wset:
        return peak_wset / (1024 * 1024), True

    try:
        import resource  # POSIX only
    except ImportError:
        return info.rss / (1024 * 1024), False

    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = raw if _RU_MAXRSS_IS_BYTES else raw * 1024
    return peak / (1024 * 1024), True


def cpu_description() -> str:
    """
    A human-readable processor name. Replaces `sysctl -n machdep.cpu.brand_string`.

    Falls back through the platform module rather than shelling out, because the
    answer is only ever used for logging and a missing binary must not raise.
    """
    for candidate in (platform.processor(), platform.machine()):
        if candidate:
            return f"{candidate} ({platform.system()})"
    return platform.system() or "unknown"


def describe() -> dict:
    """Everything above in one dict, for logs and the /health payload."""
    snapshot = memory()
    peak, is_true_peak = peak_rss_mb()

    return {
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "cpu": cpu_description(),
        "cpu_count": psutil.cpu_count(logical=True),
        "total_memory_gb": round(total_memory_gb(), 2),
        "available_memory_mb": round(snapshot.available_mb),
        "swap_total_mb": round(snapshot.swap_total_mb),
        "process_peak_rss_mb": round(peak),
        "peak_rss_is_exact": is_true_peak,
    }
