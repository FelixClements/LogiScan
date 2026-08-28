"""USB-portable RapidOCR trailer photo filer (DirectML iGPU)."""

from logiscan.cli import main
from logiscan.config import (
    STATUS_AMBIGUOUS_FOLDER,
    STATUS_AMBIGUOUS_SEAL,
    STATUS_AMBIGUOUS_TRAILER,
    STATUS_CONVERT_ERROR,
    STATUS_DEST_EXISTS,
    STATUS_ERROR,
    STATUS_MOVED,
    STATUS_NO_FOLDER,
    STATUS_NO_SEAL,
    STATUS_NO_TRAILER,
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
    "STATUS_AMBIGUOUS_FOLDER",
    "STATUS_AMBIGUOUS_SEAL",
    "STATUS_AMBIGUOUS_TRAILER",
    "STATUS_CONVERT_ERROR",
    "STATUS_DEST_EXISTS",
    "STATUS_ERROR",
    "STATUS_MOVED",
    "STATUS_NO_FOLDER",
    "STATUS_NO_SEAL",
    "STATUS_NO_TRAILER",
    "list_images",
    "main",
]
