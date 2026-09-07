"""Convert, OCR, extract, look up, and move one photo."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from logiscan.config import (
    DEST_FOLDER_SEP,
    STATUS_CONVERT_ERROR,
    STATUS_DEST_EXISTS,
    STATUS_ERROR,
    STATUS_MOVED,
    Config,
    ScanResult,
)
from logiscan.extract import ExtractedFields, extract_fields
from logiscan.gui_copy import leftover_reason
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


def join_dest_folders(folders: list[Path]) -> str | None:
    if not folders:
        return None
    return DEST_FOLDER_SEP.join(str(path) for path in folders)


def gate_status(fields: ExtractedFields, index: FolderIndex) -> tuple[str, list[Path]]:
    if fields.trailer_status:
        return fields.trailer_status, []
    if fields.seal_status:
        return fields.seal_status, []
    assert fields.trailer is not None and fields.seal is not None
    folders, folder_status = index.lookup_status(fields.trailer)
    if folder_status:
        return folder_status, []
    if any(
        destination_for(folder, fields.trailer, fields.seal).exists()
        for folder in folders
    ):
        return STATUS_DEST_EXISTS, folders
    return STATUS_MOVED, folders


def commit_copies(
    *,
    original: Path,
    working: Path,
    dests: list[Path],
    processed_dir: Path,
) -> None:
    for dest in dests:
        shutil.copy2(str(working), str(dest))
    converting = original.suffix.lower() in CONVERT_SUFFIXES
    if converting:
        if working != original:
            working.unlink(missing_ok=True)
        try:
            processed_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(original), str(processed_dir / original.name))
        except OSError as exc:
            LOGGER.error(
                "Copied JPEG to %s but failed to archive %s: %s",
                dests,
                original,
                exc,
            )
        return
    if original.exists():
        original.unlink()


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
        status, folders = gate_status(fields, self._index)
        dest_folder = join_dest_folders(folders)
        if status != STATUS_MOVED:
            if (
                status == STATUS_DEST_EXISTS
                and dest_folder
                and DEST_FOLDER_SEP in dest_folder
            ):
                LOGGER.warning(
                    "%s %s | trailer=%s seal=%s dest=%s",
                    leftover_reason(status, dest_folder=dest_folder),
                    original.name,
                    fields.trailer,
                    fields.seal,
                    dest_folder,
                )
            return ScanResult(
                timestamp=timestamp,
                filename=original.name,
                trailer=fields.trailer,
                seal=fields.seal,
                dest_folder=dest_folder,
                status=status,
            )
        assert fields.trailer is not None and fields.seal is not None
        dests = [
            destination_for(folder, fields.trailer, fields.seal) for folder in folders
        ]
        commit_copies(
            original=original,
            working=working,
            dests=dests,
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
