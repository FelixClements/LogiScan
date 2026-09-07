"""One-pass filename index: ISO-6346 code to parent PO folders."""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from logiscan.iso import codes_in_text

LOGGER = logging.getLogger("logiscan")


class FolderIndex:
    def __init__(self, mapping: dict[str, set[Path]]) -> None:
        self._map = mapping

    def lookup_status(self, trailer: str) -> tuple[list[Path], str | None]:
        folders = sorted(self._map.get(trailer, set()), key=str)
        if not folders:
            return [], "NO_FOLDER"
        return folders, None


def build_index(search_root: Path) -> FolderIndex:
    mapping: dict[str, set[Path]] = defaultdict(set)
    try:
        candidates = list(search_root.rglob("*"))
    except OSError as exc:
        LOGGER.warning("Unreadable search root %s: %s", search_root, exc)
        return FolderIndex({})
    for path in candidates:
        try:
            if not path.is_file():
                continue
        except OSError as exc:
            LOGGER.warning("Skipping %s: %s", path, exc)
            continue
        parent = path.parent.resolve()
        for code in codes_in_text(path.name):
            mapping[code].add(parent)
    return FolderIndex(dict(mapping))
