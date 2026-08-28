"""Convert, OCR, extract, look up, and move one photo."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from logiscan.config import (
    STATUS_CONVERT_ERROR,
    STATUS_DEST_EXISTS,
    STATUS_ERROR,
    STATUS_MOVED,
    Config,
    ScanResult,
)
from logiscan.extract import ExtractedFields, extract_fields
from logiscan.hardware import enable_opencl
from logiscan.images import CONVERT_SUFFIXES, enhance_pass2, load_image, prepare_working_image
from logiscan.index import FolderIndex

LOGGER = logging.getLogger("logiscan")


class Recognizer(Protocol):
    def recognize(self, image: Any) -> str: ...


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def destination_for(folder: Path, trailer: str, seal: str) -> Path:
    return folder / f"{trailer}_{seal}.jpg"


def gate_status(fields: ExtractedFields, index: FolderIndex) -> tuple[str, Path | None]:
    if fields.trailer_status:
        return fields.trailer_status, None
    if fields.seal_status:
        return fields.seal_status, None
    assert fields.trailer is not None and fields.seal is not None
    folder, folder_status = index.lookup_status(fields.trailer)
    if folder_status:
        return folder_status, None
    assert folder is not None
    dest = destination_for(folder, fields.trailer, fields.seal)
    if dest.exists():
        return STATUS_DEST_EXISTS, folder
    return STATUS_MOVED, folder


def commit_move(
    *,
    original: Path,
    working: Path,
    dest: Path,
    processed_dir: Path,
) -> None:
    shutil.move(str(working), str(dest))
    if original.suffix.lower() not in CONVERT_SUFFIXES:
        return
    try:
        processed_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(original), str(processed_dir / original.name))
    except OSError as exc:
        LOGGER.error(
            "Moved JPEG to %s but failed to archive %s: %s",
            dest,
            original,
            exc,
        )


class OCRProcessor:
    """Runs RapidOCR (DirectML) then files the JPEG into the PO folder."""

    def __init__(
        self,
        config: Config,
        index: FolderIndex,
        engine: Recognizer | None = None,
    ) -> None:
        import cv2

        self.config = config
        self._index = index
        self._opencl = enable_opencl(cv2)
        if engine is None:
            from logiscan.ocr import RapidOCREngine

            engine = RapidOCREngine(config)
        self._engine = engine

    def process_image(self, path: Path) -> ScanResult:
        timestamp = _now()
        temp: Path | None = None
        try:
            working, temp = prepare_working_image(path)
        except Exception as exc:
            LOGGER.exception("Failed converting %s", path.name)
            return ScanResult(
                timestamp=timestamp,
                filename=path.name,
                status=STATUS_CONVERT_ERROR,
                error=str(exc),
            )
        try:
            return self._scan(path, working, timestamp)
        except Exception as exc:
            LOGGER.exception("Failed processing %s", path.name)
            return ScanResult(
                timestamp=timestamp,
                filename=path.name,
                status=STATUS_ERROR,
                error=str(exc),
            )
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    def _scan(self, original: Path, working: Path, timestamp: str) -> ScanResult:
        image = load_image(working)
        layout = self._engine.recognize(image)
        fields = extract_fields(layout)
        if not fields.complete:
            enhanced = enhance_pass2(image, self.config, use_opencl=self._opencl)
            fields = extract_fields(self._engine.recognize(enhanced))
        LOGGER.info(
            "OCR text %s: %s",
            original.name,
            " | ".join(layout.split())[:400],
        )
        status, folder = gate_status(fields, self._index)
        dest_folder = str(folder) if folder is not None else None
        if status != STATUS_MOVED:
            return ScanResult(
                timestamp=timestamp,
                filename=original.name,
                trailer=fields.trailer,
                seal=fields.seal,
                dest_folder=dest_folder,
                status=status,
            )
        assert folder is not None and fields.trailer is not None and fields.seal is not None
        dest = destination_for(folder, fields.trailer, fields.seal)
        commit_move(
            original=original,
            working=working,
            dest=dest,
            processed_dir=self.config.processed_dir,
        )
        return ScanResult(
            timestamp=timestamp,
            filename=original.name,
            trailer=fields.trailer,
            seal=fields.seal,
            dest_folder=dest_folder,
            status=STATUS_MOVED,
        )
