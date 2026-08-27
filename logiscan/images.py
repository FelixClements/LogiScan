"""Image loading and Pass 2 contrast enhancement."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from logiscan.config import Config

LOGGER = logging.getLogger("logiscan")


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
        if path.is_file() and path.suffix.lower() in wanted
    )


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
