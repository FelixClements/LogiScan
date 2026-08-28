"""Append-only success log and CSV audit report."""

from __future__ import annotations

import csv
import logging

from logiscan.config import CSV_FIELDS, STATUS_MOVED, Config, ScanResult

LOGGER = logging.getLogger("logiscan")


class ReportManager:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._config.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._config.report_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_csv_header()

    def _ensure_csv_header(self) -> None:
        path = self._config.report_path
        if path.exists() and path.stat().st_size > 0:
            return
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=CSV_FIELDS).writeheader()

    def record(self, result: ScanResult) -> None:
        if result.status == STATUS_MOVED:
            line = (
                f"[{result.timestamp}] MOVED: {result.filename} | "
                f"trailer={result.trailer} seal={result.seal} dest={result.dest_folder}"
            )
            with self._config.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            LOGGER.info(line)
        self._append_csv(result)

    def _append_csv(self, result: ScanResult) -> None:
        with self._config.report_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writerow(
                {
                    "Timestamp": result.timestamp,
                    "Filename": result.filename,
                    "Trailer": result.trailer or "",
                    "Seal": result.seal or "",
                    "DestFolder": result.dest_folder or "",
                    "Status": result.status,
                }
            )
