"""MRSU and tracking regex helpers."""

from __future__ import annotations

import re

DEFAULT_MRSU_PATTERN = r"(?i)MRSU[\s\-]*8692215"
DEFAULT_TRACKING_PATTERN = r"(?<!\d)738[68]8(?!\d)"
DEFAULT_MIN_TRACKING_HITS = 2


def compile_mrsu(pattern: str = DEFAULT_MRSU_PATTERN) -> re.Pattern[str]:
    return re.compile(pattern)


def compile_tracking(pattern: str = DEFAULT_TRACKING_PATTERN) -> re.Pattern[str]:
    return re.compile(pattern)


def mrsu_found(text: str, compiled: re.Pattern[str]) -> bool:
    return compiled.search(text) is not None


def tracking_count(text: str, compiled: re.Pattern[str]) -> int:
    return len(compiled.findall(text))


def markers_complete(
    text: str,
    *,
    mrsu: re.Pattern[str],
    tracking: re.Pattern[str],
    min_hits: int = DEFAULT_MIN_TRACKING_HITS,
) -> bool:
    return mrsu_found(text, mrsu) and tracking_count(text, tracking) >= min_hits
