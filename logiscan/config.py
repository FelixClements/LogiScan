"""Shared paths, statuses, and runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
CSV_FIELDS = ("Timestamp", "Filename", "Trailer", "Seal", "DestFolder", "Status")
STATUS_MOVED = "MOVED"
STATUS_CONVERT_ERROR = "CONVERT_ERROR"
STATUS_ERROR = "ERROR"
STATUS_NO_TRAILER = "NO_TRAILER"
STATUS_AMBIGUOUS_TRAILER = "AMBIGUOUS_TRAILER"
STATUS_NO_SEAL = "NO_SEAL"
STATUS_AMBIGUOUS_SEAL = "AMBIGUOUS_SEAL"
STATUS_NO_FOLDER = "NO_FOLDER"
STATUS_AMBIGUOUS_FOLDER = "AMBIGUOUS_FOLDER"
STATUS_DEST_EXISTS = "DEST_EXISTS"
BACKEND_DML = "onnxruntime-dml"
PROCESSED_DIR_NAME = "_processed"
JPEG_QUALITY = 95


def resolve_path(path: Path, root: Path = APP_ROOT) -> Path:
    return path if path.is_absolute() else (root / path).resolve()


@dataclass(frozen=True)
class Config:
    """Folder layout and Pass 2 filter settings."""

    photos_dir: Path = field(default_factory=lambda: Path("photos"))
    search_root: Path = field(default_factory=lambda: Path("."))
    log_path: Path = field(default_factory=lambda: Path("ocr_matches.log"))
    report_path: Path = field(default_factory=lambda: Path("ocr_report.csv"))
    model_dir: Path = field(default_factory=lambda: Path("models") / "rapidocr")
    image_suffixes: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".heic", ".heif")
    clahe_clip_limit: float = 4.0
    clahe_tile_grid: tuple[int, int] = (8, 8)
    bilateral_diameter: int = 9
    bilateral_sigma_color: float = 75.0
    bilateral_sigma_space: float = 75.0

    def resolved(self, root: Path = APP_ROOT) -> Config:
        return Config(
            photos_dir=resolve_path(self.photos_dir, root),
            search_root=resolve_path(self.search_root, root),
            log_path=resolve_path(self.log_path, root),
            report_path=resolve_path(self.report_path, root),
            model_dir=resolve_path(self.model_dir, root),
            image_suffixes=self.image_suffixes,
            clahe_clip_limit=self.clahe_clip_limit,
            clahe_tile_grid=self.clahe_tile_grid,
            bilateral_diameter=self.bilateral_diameter,
            bilateral_sigma_color=self.bilateral_sigma_color,
            bilateral_sigma_space=self.bilateral_sigma_space,
        )

    @property
    def processed_dir(self) -> Path:
        return self.photos_dir / PROCESSED_DIR_NAME


@dataclass(frozen=True)
class ScanResult:
    """One image's filing outcome."""

    timestamp: str
    filename: str
    trailer: str | None = None
    seal: str | None = None
    dest_folder: str | None = None
    status: str = STATUS_ERROR
    error: str | None = None
