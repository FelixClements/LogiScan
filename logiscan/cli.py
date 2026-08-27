"""CLI for the USB-portable LogiScan OCR batch scanner."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from logiscan.config import STATUS_ERROR, Config
from logiscan.hardware import DirectMLUnavailableError, probe_hardware
from logiscan.images import list_images
from logiscan.processor import OCRProcessor
from logiscan.report import ReportManager

LOGGER = logging.getLogger("logiscan")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-OCR A4 delivery photos for MRSU and tracking markers."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("photos"))
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging()
    if args.check_hardware:
        return probe_hardware()

    config = Config(
        photos_dir=args.input_dir,
        log_path=args.log_file,
        report_path=args.report_file,
    ).resolved()

    if not config.photos_dir.exists():
        LOGGER.error("Input directory does not exist: %s", config.photos_dir)
        return 1
    if not config.photos_dir.is_dir():
        LOGGER.error("Input path is not a directory: %s", config.photos_dir)
        return 1

    images = list_images(config.photos_dir, config.image_suffixes)
    if not images:
        LOGGER.warning("No .jpg/.jpeg/.png files in %s", config.photos_dir)
        return 0

    try:
        processor = OCRProcessor(config)
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
        if result.status == STATUS_ERROR:
            LOGGER.error("ERROR %s: %s", result.filename, result.error)
        else:
            LOGGER.info(
                "%s %s | MRSU=%s tracking=%s",
                result.status,
                result.filename,
                result.mrsu_match,
                result.tracking_match_count,
            )
    return 0
