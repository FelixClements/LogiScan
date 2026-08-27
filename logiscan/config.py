"""Shared paths, statuses, and runtime configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from logiscan.markers import (
    DEFAULT_MIN_TRACKING_HITS,
    DEFAULT_MRSU_PATTERN,
    DEFAULT_TRACKING_PATTERN,
    compile_mrsu,
    compile_tracking,
    markers_complete,
    mrsu_found,
    tracking_count,
)

APP_ROOT = Path(__file__).resolve().parent.parent
CSV_FIELDS = ("Timestamp", "Filename", "MRSU_Match", "Tracking_Match_Count", "Status")
STATUS_SUCCESS = "SUCCESS"
STATUS_NO_MATCH = "NO_MATCH"
STATUS_ERROR = "ERROR"
BACKEND_DML = "onnxruntime-dml"


def resolve_path(path: Path, root: Path = APP_ROOT) -> Path:
    return path if path.is_absolute() else (root / path).resolve()


@dataclass(frozen=True)
class Config:
    """Patterns, thresholds, and folder layout."""

    photos_dir: Path = field(default_factory=lambda: Path("photos"))
    log_path: Path = field(default_factory=lambda: Path("ocr_matches.log"))
    report_path: Path = field(default_factory=lambda: Path("ocr_report.csv"))
    model_dir: Path = field(default_factory=lambda: Path("models") / "rapidocr")
    image_suffixes: tuple[str, ...] = (".jpg", ".jpeg", ".png")
    mrsu_pattern: str = DEFAULT_MRSU_PATTERN
    tracking_pattern: str = DEFAULT_TRACKING_PATTERN
    min_tracking_hits: int = DEFAULT_MIN_TRACKING_HITS
    clahe_clip_limit: float = 4.0
    clahe_tile_grid: tuple[int, int] = (8, 8)
    bilateral_diameter: int = 9
    bilateral_sigma_color: float = 75.0
    bilateral_sigma_space: float = 75.0
    _mrsu_re: re.Pattern[str] = field(init=False, repr=False, compare=False)
    _tracking_re: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_mrsu_re", compile_mrsu(self.mrsu_pattern))
        object.__setattr__(self, "_tracking_re", compile_tracking(self.tracking_pattern))

    def resolved(self, root: Path = APP_ROOT) -> Config:
        return Config(
            photos_dir=resolve_path(self.photos_dir, root),
            log_path=resolve_path(self.log_path, root),
            report_path=resolve_path(self.report_path, root),
            model_dir=resolve_path(self.model_dir, root),
            image_suffixes=self.image_suffixes,
            mrsu_pattern=self.mrsu_pattern,
            tracking_pattern=self.tracking_pattern,
            min_tracking_hits=self.min_tracking_hits,
            clahe_clip_limit=self.clahe_clip_limit,
            clahe_tile_grid=self.clahe_tile_grid,
            bilateral_diameter=self.bilateral_diameter,
            bilateral_sigma_color=self.bilateral_sigma_color,
            bilateral_sigma_space=self.bilateral_sigma_space,
        )

    def mrsu_found(self, text: str) -> bool:
        return mrsu_found(text, self._mrsu_re)

    def tracking_count(self, text: str) -> int:
        return tracking_count(text, self._tracking_re)

    def markers_complete(self, text: str) -> bool:
        return markers_complete(
            text,
            mrsu=self._mrsu_re,
            tracking=self._tracking_re,
            min_hits=self.min_tracking_hits,
        )


@dataclass(frozen=True)
class ScanResult:
    """One image's verification outcome."""

    timestamp: str
    filename: str
    mrsu_match: bool
    tracking_match_count: int
    status: str
    error: str | None = None
