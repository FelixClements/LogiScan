"""Decode an input photo to PNG thumbnail bytes (no Tk)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

HEIF_SUFFIXES = {".heic", ".heif"}


def thumbnail_png(path: Path, max_size: int = 280) -> bytes:
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
