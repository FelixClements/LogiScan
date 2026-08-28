"""CLI for the USB-portable LogiScan trailer photo filer."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from logiscan.batch import run_batch
from logiscan.config import Config
from logiscan.hardware import probe_hardware

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
    return run_batch(config)
