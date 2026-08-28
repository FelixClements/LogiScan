"""Last-used folder paths for the operator GUI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PREFS_NAME = "logiscan_gui.json"
DEFAULT_PHOTOS = Path("photos")


@dataclass(frozen=True)
class GuiPrefs:
    photos_dir: Path = DEFAULT_PHOTOS
    search_root: Path | None = None


def prefs_path(root: Path) -> Path:
    return root / PREFS_NAME


def load_prefs(root: Path) -> GuiPrefs:
    path = prefs_path(root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return GuiPrefs()
    if not isinstance(raw, dict):
        return GuiPrefs()
    photos = raw.get("photos_dir")
    search = raw.get("search_root")
    photos_dir = Path(photos) if isinstance(photos, str) and photos else DEFAULT_PHOTOS
    search_root = Path(search) if isinstance(search, str) and search else None
    return GuiPrefs(photos_dir=photos_dir, search_root=search_root)


def save_prefs(root: Path, prefs: GuiPrefs) -> None:
    payload = {
        "photos_dir": str(prefs.photos_dir),
        "search_root": str(prefs.search_root) if prefs.search_root is not None else "",
    }
    prefs_path(root).write_text(json.dumps(payload, indent=2), encoding="utf-8")
