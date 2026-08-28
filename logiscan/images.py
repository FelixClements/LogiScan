"""Image listing, loading, HEIC/PNG conversion, and Pass 2 enhancement."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from logiscan.config import JPEG_QUALITY, PROCESSED_DIR_NAME, Config

LOGGER = logging.getLogger("logiscan")
CONVERT_SUFFIXES = {".heic", ".heif", ".png"}
JPEG_SUFFIXES = {".jpg", ".jpeg"}


def load_image(path: Path) -> Any:
    import cv2
    import numpy as np

    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unreadable or corrupted image: {path.name}")
    return image


def list_images(photos_dir: Path, suffixes: tuple[str, ...]) -> list[Path]:
    wanted = {item.lower() for item in suffixes}
    return sorted(
        path
        for path in photos_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in wanted
        and path.name != PROCESSED_DIR_NAME
    )


def prepare_working_image(path: Path) -> tuple[Path, Path | None]:
    suffix = path.suffix.lower()
    if suffix in JPEG_SUFFIXES:
        return path, None
    if suffix not in CONVERT_SUFFIXES:
        raise ValueError(f"Unsupported image type: {path.name}")
    return _convert_to_temp_jpeg(path)


def _convert_to_temp_jpeg(path: Path) -> tuple[Path, Path]:
    from PIL import Image

    suffix = path.suffix.lower()
    if suffix in {".heic", ".heif"}:
        import pillow_heif

        pillow_heif.register_heif_opener()
    image = Image.open(path)
    rgb = image.convert("RGB")
    handle, raw_name = tempfile.mkstemp(suffix=".jpg")
    os.close(handle)
    dest = Path(raw_name)
    try:
        rgb.save(dest, format="JPEG", quality=JPEG_QUALITY)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest, dest


def enhance_pass2(image: Any, config: Config, *, use_opencl: bool) -> Any:
    import cv2

    clip = config.clahe_clip_limit
    tiles = config.clahe_tile_grid
    diameter = config.bilateral_diameter
    sigma_c = config.bilateral_sigma_color
    sigma_s = config.bilateral_sigma_space
    try:
        src = cv2.UMat(image) if use_opencl else image
        gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.createCLAHE(clipLimit=clip, tileGridSize=tiles).apply(gray)
        filtered = cv2.bilateralFilter(enhanced, diameter, sigma_c, sigma_s)
        if use_opencl:
            filtered = filtered.get()
        if len(filtered.shape) == 2:
            return cv2.cvtColor(filtered, cv2.COLOR_GRAY2BGR)
        return filtered
    except Exception as exc:
        LOGGER.warning("OpenCL Pass 2 failed (%s); using CPU filters.", exc)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.createCLAHE(clipLimit=clip, tileGridSize=tiles).apply(gray)
        filtered = cv2.bilateralFilter(enhanced, diameter, sigma_c, sigma_s)
        return cv2.cvtColor(filtered, cv2.COLOR_GRAY2BGR)
