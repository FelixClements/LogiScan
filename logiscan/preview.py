"""Decode an input photo to PNG thumbnail bytes (no Tk)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

HEIF_SUFFIXES = {".heic", ".heif"}
DEFAULT_PREVIEW_MAX = 280
UNMAPPED_EDGE = 2
RESIZE_THRESHOLD = 8


def pane_max_size(width: int, height: int) -> int:
    if width < UNMAPPED_EDGE or height < UNMAPPED_EDGE:
        return DEFAULT_PREVIEW_MAX
    return min(width, height)


def pane_resized(
    old: tuple[int, int],
    new: tuple[int, int],
    *,
    threshold: int = RESIZE_THRESHOLD,
) -> bool:
    return abs(new[0] - old[0]) > threshold or abs(new[1] - old[1]) > threshold


def thumbnail_png(path: Path, max_size: int = DEFAULT_PREVIEW_MAX) -> bytes:
    from PIL import Image

    if path.suffix.lower() in HEIF_SUFFIXES:
        import pillow_heif

        pillow_heif.register_heif_opener()
    try:
        image = Image.open(path)
        rgb = image.convert("RGB")
    except Exception as exc:
        raise ValueError(f"Unreadable or corrupted image: {path.name}") from exc
    rgb.thumbnail((max_size, max_size))
    buffer = BytesIO()
    rgb.save(buffer, format="PNG")
    return buffer.getvalue()
