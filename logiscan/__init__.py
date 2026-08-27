"""USB-portable RapidOCR batch scanner (DirectML iGPU)."""

from logiscan.cli import main
from logiscan.config import (
    STATUS_ERROR,
    STATUS_NO_MATCH,
    STATUS_SUCCESS,
    Config,
    ScanResult,
)
from logiscan.images import list_images
from logiscan.processor import OCRProcessor
from logiscan.report import ReportManager

__all__ = [
    "Config",
    "OCRProcessor",
    "ReportManager",
    "ScanResult",
    "STATUS_ERROR",
    "STATUS_NO_MATCH",
    "STATUS_SUCCESS",
    "list_images",
    "main",
]
