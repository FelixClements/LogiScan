"""CLI for the USB-portable LogiScan trailer photo filer."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from logiscan.config import STATUS_ERROR, Config
from logiscan.hardware import DirectMLUnavailableError, probe_hardware
from logiscan.images import list_images
from logiscan.index import build_index
from logiscan.processor import OCRProcessor
from logiscan.report import ReportManager

LOGGER = logging.getLogger("logiscan")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert HEIC, OCR trailer and seal, and file photos into PO folders."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("photos"))
    parser.add_argument("--search-root", type=Path, default=None)
    parser.add_argument("--log-file", type=Path, default=Path("ocr_matches.log"))
    parser.add_argument("--report-file", type=Path, default=Path("ocr_report.csv"))
    parser.add_argument(
        "--check-hardware",
        action="store_true",
        help="Print DirectML / OpenCL status and exit non-zero if DML is missing.",
    )
    return parser.parse_args(argv)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _require_dir(path: Path, label: str) -> str | None:
    if not path.exists():
        return f"{label} does not exist: {path}"
    if not path.is_dir():
        return f"{label} is not a directory: {path}"
    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging()
    if args.check_hardware:
        return probe_hardware()

    if args.search_root is None:
        LOGGER.error("--search-root is required")
        return 1

    config = Config(
        photos_dir=args.input_dir,
        search_root=args.search_root,
        log_path=args.log_file,
        report_path=args.report_file,
    ).resolved()

    for path, label in (
        (config.photos_dir, "Input directory"),
        (config.search_root, "Search root"),
    ):
        error = _require_dir(path, label)
        if error:
            LOGGER.error("%s", error)
            return 1

    images = list_images(config.photos_dir, config.image_suffixes)
    if not images:
        LOGGER.warning("No image files in %s", config.photos_dir)
        return 0

    index = build_index(config.search_root)
    try:
        processor = OCRProcessor(config, index)
    except DirectMLUnavailableError:
        LOGGER.exception("DirectML iGPU is required; refusing CPU OCR.")
        return 2
    except Exception:
        LOGGER.exception("Failed to initialize the OCR engine.")
        return 2

    reporter = ReportManager(config)
    LOGGER.info("Processing %s image(s) from %s", len(images), config.photos_dir)
    for path in images:
        result = processor.process_image(path)
        reporter.record(result)
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
