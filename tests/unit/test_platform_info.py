"""
Platform facts must be answerable off a Mac.

The 4 GB claim is about the machines schools actually own, and those are
overwhelmingly Windows. Code that reads memory through `sysctl` answers that
claim only on the one platform that did not need it.
"""

import sys
from unittest.mock import patch

import pytest

from backend.core import platform_info


def test_memory_reports_plausible_totals():
    snapshot = platform_info.memory()

    assert snapshot.total_mb > 0
    assert 0 <= snapshot.available_mb <= snapshot.total_mb
    assert 0 <= snapshot.used_percent <= 100
    assert snapshot.swap_free_mb <= snapshot.swap_total_mb or snapshot.swap_total_mb == 0


def test_available_percent_complements_used():
    snapshot = platform_info.memory()

    assert snapshot.available_percent == pytest.approx(100.0 - snapshot.used_percent)


def test_total_memory_is_in_gigabytes_not_bytes():
    """
    `sysctl -n hw.memsize` returns bytes. A call site that forgot to divide
    would report 8589934592 "GB" and every downstream threshold would pass.
    """
    assert 0.25 < platform_info.total_memory_gb() < 4096


def test_peak_rss_is_reported_in_megabytes():
    value, is_exact = platform_info.peak_rss_mb()

    assert value > 1  # a Python process with psutil loaded is never under 1 MB
    assert value < 1024 * 1024
    assert isinstance(is_exact, bool)


def test_peak_rss_falls_back_when_resource_is_missing():
    """
    Windows has no `resource` module. The fallback must return current RSS and
    say so, rather than presenting it as a high-water mark -- `ps` reported
    46 MB for a process holding a 1 GB model that had been paged out.
    """
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def no_resource(name, *args, **kwargs):
        if name == "resource":
            raise ImportError("no resource module on this platform")
        return real_import(name, *args, **kwargs)

    class _Info:
        rss = 123 * 1024 * 1024  # no peak_wset attribute, as on POSIX

    with patch("psutil.Process") as process:
        process.return_value.memory_info.return_value = _Info()
        with patch("builtins.__import__", side_effect=no_resource):
            value, is_exact = platform_info.peak_rss_mb()

    assert value == pytest.approx(123, abs=0.5)
    assert is_exact is False


def test_windows_peak_working_set_is_preferred_when_present():
    """Windows exposes a genuine peak; it must be used rather than current RSS."""

    class _Info:
        rss = 100 * 1024 * 1024
        peak_wset = 900 * 1024 * 1024

    with patch("psutil.Process") as process:
        process.return_value.memory_info.return_value = _Info()
        value, is_exact = platform_info.peak_rss_mb()

    assert value == pytest.approx(900, abs=0.5)
    assert is_exact is True


def test_cpu_description_never_raises_or_returns_empty():
    """It is only ever logged, so a missing binary must not become an exception."""
    assert platform_info.cpu_description().strip()


def test_describe_carries_what_a_bug_report_needs():
    facts = platform_info.describe()

    for key in ("os", "machine", "total_memory_gb", "available_memory_mb", "peak_rss_is_exact"):
        assert key in facts


@pytest.mark.skipif(sys.platform != "darwin", reason="unit conversion is platform-specific")
def test_darwin_ru_maxrss_is_treated_as_bytes():
    """
    macOS reports ru_maxrss in bytes and Linux in kilobytes. Getting this
    backwards is a factor-of-1024 error in a headline memory figure.
    """
    assert platform_info._RU_MAXRSS_IS_BYTES is True
