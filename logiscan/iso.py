"""ISO-6346 container code normalize, check digit, and scan."""

from __future__ import annotations

import re

ISO_TOKEN = re.compile(r"(?<![A-Z0-9])([A-Z]{4})[\s\-]*(\d{7})(?!\d)")

_LETTER_VALUE = {
    "A": 10,
    "B": 12,
    "C": 13,
    "D": 14,
    "E": 15,
    "F": 16,
    "G": 17,
    "H": 18,
    "I": 19,
    "J": 20,
    "K": 21,
    "L": 23,
    "M": 24,
    "N": 25,
    "O": 26,
    "P": 27,
    "Q": 28,
    "R": 29,
    "S": 30,
    "T": 31,
    "U": 32,
    "V": 34,
    "W": 35,
    "X": 36,
    "Y": 37,
    "Z": 38,
}


def normalize_iso(raw: str) -> str:
    return re.sub(r"[\s\-]", "", raw).upper()


def _char_value(char: str) -> int:
    if char.isdigit():
        return int(char)
    return _LETTER_VALUE[char]


def check_digit(body: str) -> int:
    total = sum(_char_value(char) * (2**index) for index, char in enumerate(body))
    remainder = total % 11
    return 0 if remainder == 10 else remainder


def is_valid_iso(code: str) -> bool:
    normalized = normalize_iso(code)
    if len(normalized) != 11 or not normalized[:4].isalpha() or not normalized[4:].isdigit():
        return False
    return int(normalized[10]) == check_digit(normalized[:10])


def codes_in_text(text: str) -> tuple[str, ...]:
    found: list[str] = []
    seen: set[str] = set()
    for match in ISO_TOKEN.finditer(text.upper()):
        owner, serial = match.groups()
        code = owner + serial
        if code in seen or not is_valid_iso(code):
            continue
        seen.add(code)
        found.append(code)
    return tuple(found)
