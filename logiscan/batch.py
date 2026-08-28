"""Shared convert/OCR/file batch used by CLI and GUI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from logiscan.config import STATUS_ERROR, Config, ScanResult
from logiscan.hardware import DirectMLUnavailableError
from logiscan.images import list_images
from logiscan.index import FolderIndex, build_index
from logiscan.processor import OCRProcessor
from logiscan.report import ReportManager

LOGGER = logging.getLogger("logiscan")


@dataclass
class BatchCallbacks:
    on_phase: Callable[[str], None] | None = None
    on_photo_begin: Callable[[int, int, Path], None] | None = None
    on_photo_done: Callable[[int, int, ScanResult], None] | None = None
    should_stop: Callable[[], bool] | None = None


def require_dir(path: Path, label: str) -> str | None:
    if not path.exists():
        return f"{label} does not exist: {path}"
    if not path.is_dir():
        return f"{label} is not a directory: {path}"
    return None


def _stopped(callbacks: BatchCallbacks | None) -> bool:
    return bool(callbacks and callbacks.should_stop and callbacks.should_stop())


def _phase(callbacks: BatchCallbacks | None, message: str) -> None:
    if callbacks and callbacks.on_phase:
        callbacks.on_phase(message)


def run_batch(
    config: Config,
    *,
    callbacks: BatchCallbacks | None = None,
    processor_factory: Callable[[Config, FolderIndex], Any] | None = None,
    index_builder: Callable[[Path], FolderIndex] | None = None,
) -> int:
    for path, label in (
        (config.photos_dir, "Input directory"),
        (config.search_root, "Search root"),
    ):
        error = require_dir(path, label)
        if error:
            LOGGER.error("%s", error)
            return 1
    if _stopped(callbacks):
        return 0

    images = list_images(config.photos_dir, config.image_suffixes)
    if not images:
        LOGGER.warning("No image files in %s", config.photos_dir)
        return 0
    if _stopped(callbacks):
        return 0

    _phase(callbacks, "Indexing PO folders…")
    builder = index_builder or build_index
    index = builder(config.search_root)
    if _stopped(callbacks):
        return 0

    _phase(callbacks, "Starting OCR…")
    factory = processor_factory or (lambda cfg, idx: OCRProcessor(cfg, idx))
    try:
        processor = factory(config, index)
    except DirectMLUnavailableError:
        LOGGER.exception("DirectML iGPU is required; refusing CPU OCR.")
        return 2
    except Exception:
        LOGGER.exception("Failed to initialize the OCR engine.")
        return 2
    if _stopped(callbacks):
        return 0

    reporter = ReportManager(config)
    total = len(images)
    LOGGER.info("Processing %s image(s) from %s", total, config.photos_dir)
    for offset, path in enumerate(images, start=1):
        if _stopped(callbacks):
            return 0
        if callbacks and callbacks.on_photo_begin:
            callbacks.on_photo_begin(offset, total, path)
        result = processor.process_image(path)
        reporter.record(result)
        if callbacks and callbacks.on_photo_done:
            callbacks.on_photo_done(offset, total, result)
        if result.status == STATUS_ERROR or result.error:
            LOGGER.error("%s %s: %s", result.status, result.filename, result.error or "")
        else:
            LOGGER.info(
                "%s %s | trailer=%s seal=%s dest=%s",
                result.status,
                result.filename,
                result.trailer,
                result.seal,
                result.dest_folder,
            )
    return 0
