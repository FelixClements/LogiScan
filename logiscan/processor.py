"""Two-pass OCR over a single image."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from logiscan.config import (
    STATUS_ERROR,
    STATUS_NO_MATCH,
    STATUS_SUCCESS,
    Config,
    ScanResult,
)
from logiscan.hardware import enable_opencl
from logiscan.images import enhance_pass2, load_image

LOGGER = logging.getLogger("logiscan")


class Recognizer(Protocol):
    def recognize(self, image: Any) -> str: ...


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class OCRProcessor:
    """Runs RapidOCR (DirectML) with optional high-contrast Pass 2."""

    def __init__(self, config: Config, engine: Recognizer | None = None) -> None:
        import cv2

        self.config = config
        self._opencl = enable_opencl(cv2)
        if engine is None:
            from logiscan.ocr import RapidOCREngine

            engine = RapidOCREngine(config)
        self._engine = engine

    def process_image(self, path: Path) -> ScanResult:
        timestamp = _now()
        try:
            return self._scan(path, timestamp)
        except Exception as exc:
            LOGGER.exception("Failed processing %s", path.name)
            return ScanResult(
                timestamp=timestamp,
                filename=path.name,
                mrsu_match=False,
                tracking_match_count=0,
                status=STATUS_ERROR,
                error=str(exc),
            )

    def _scan(self, path: Path, timestamp: str) -> ScanResult:
        image = load_image(path)
        layout = self._engine.recognize(image)
        if not self.config.markers_complete(layout):
            enhanced = enhance_pass2(image, self.config, use_opencl=self._opencl)
            layout = layout + "\n" + self._engine.recognize(enhanced)
        LOGGER.info("OCR text %s: %s", path.name, " | ".join(layout.split())[:400])
        mrsu = self.config.mrsu_found(layout)
        tracking = self.config.tracking_count(layout)
        status = (
            STATUS_SUCCESS
            if mrsu and tracking >= self.config.min_tracking_hits
            else STATUS_NO_MATCH
        )
        return ScanResult(
            timestamp=timestamp,
            filename=path.name,
            mrsu_match=mrsu,
            tracking_match_count=tracking,
            status=status,
        )
