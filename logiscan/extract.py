"""Trailer and seal fields from OCR text."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from logiscan.iso import codes_in_text

SEAL_TOKEN = re.compile(r"(?<!\d)(\d{5})(?!\d)")


@dataclass(frozen=True)
class ExtractedFields:
    trailer: str | None
    seal: str | None
    trailer_status: str | None
    seal_status: str | None

    @property
    def complete(self) -> bool:
        return self.trailer is not None and self.seal is not None


def extract_fields(text: str) -> ExtractedFields:
    codes = codes_in_text(text)
    if not codes:
        trailer, trailer_status = None, "NO_TRAILER"
    elif len(codes) > 1:
        trailer, trailer_status = None, "AMBIGUOUS_TRAILER"
    else:
        trailer, trailer_status = codes[0], None

    counts = Counter(SEAL_TOKEN.findall(text.upper()))
    confirmed = [value for value, hits in counts.items() if hits >= 2]
    if not confirmed:
        seal, seal_status = None, "NO_SEAL"
    elif len(confirmed) > 1:
        seal, seal_status = None, "AMBIGUOUS_SEAL"
    else:
        seal, seal_status = confirmed[0], None

    return ExtractedFields(
        trailer=trailer,
        seal=seal,
        trailer_status=trailer_status,
        seal_status=seal_status,
    )
