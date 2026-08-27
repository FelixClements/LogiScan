"""RapidOCR engine on DirectML (Intel iGPU). No CPU OCR fallback."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from logiscan.config import BACKEND_DML, Config
from logiscan.hardware import (
    DirectMLUnavailableError,
    require_directml,
    require_session_on_dml,
)

LOGGER = logging.getLogger("logiscan")


def engine_params(model_dir: Path) -> dict[str, Any]:
    """RapidOCR params: ORT + DirectML, English rec, models under USB root."""
    from rapidocr import EngineType, LangRec, ModelType, OCRVersion

    return {
        "Det.engine_type": EngineType.ONNXRUNTIME,
        "Cls.engine_type": EngineType.ONNXRUNTIME,
        "Rec.engine_type": EngineType.ONNXRUNTIME,
        "EngineConfig.onnxruntime.use_dml": True,
        "Global.model_root_dir": str(model_dir),
        "Rec.lang_type": LangRec.EN,
        "Rec.ocr_version": OCRVersion.PPOCRV5,
        "Rec.model_type": ModelType.MOBILE,
    }


def _box_sort_key(box: Any) -> tuple[float, float]:
    import numpy as np

    arr = np.asarray(box, dtype=np.float32)
    ys = arr[:, 1] if arr.ndim == 2 else arr[1::2]
    xs = arr[:, 0] if arr.ndim == 2 else arr[0::2]
    return (float(np.min(ys)), float(np.min(xs)))


def layout_from_result(result: Any) -> str:
    txts = getattr(result, "txts", None)
    boxes = getattr(result, "boxes", None)
    if not txts:
        if isinstance(result, (list, tuple)) and result and not hasattr(result, "txts"):
            if isinstance(result[0], str):
                return "\n".join(str(item) for item in result)
            if isinstance(result[0], (list, tuple)) and len(result[0]) >= 2:
                return "\n".join(str(item[1]) for item in result)
        return ""
    if boxes is None:
        return "\n".join(str(text) for text in txts)
    paired = sorted(zip(boxes, txts), key=lambda item: _box_sort_key(item[0]))
    return "\n".join(str(text) for _, text in paired)


def _session_providers(model: Any) -> list[str]:
    session = getattr(model, "session", None)
    inner = getattr(session, "session", session)
    getter = getattr(inner, "get_providers", None)
    if getter is None:
        raise DirectMLUnavailableError(
            "Cannot inspect ORT session providers; refusing to assume DirectML."
        )
    return list(getter())


def _loaded_models(engine: Any) -> tuple[Any, Any, Any]:
    if hasattr(engine, "_load_det_model"):
        det, cls, rec = (
            engine._load_det_model(),
            engine._load_cls_model(),
            engine._load_rec_model(),
        )
    else:
        det, cls, rec = engine.text_det, engine.text_cls, engine.text_rec
    if det is None or cls is None or rec is None:
        raise DirectMLUnavailableError("RapidOCR did not load det/cls/rec sessions.")
    return det, cls, rec


class RapidOCREngine:
    """Loads RapidOCR with DirectML and hard-fails if sessions are not on DML."""

    def __init__(self, config: Config) -> None:
        require_directml()
        from rapidocr import RapidOCR

        config.model_dir.mkdir(parents=True, exist_ok=True)
        self._engine = RapidOCR(params=engine_params(config.model_dir))
        self._assert_loaded_on_dml()
        LOGGER.info("Inference backend: %s", BACKEND_DML)

    def _assert_loaded_on_dml(self) -> None:
        det, cls, rec = _loaded_models(self._engine)
        require_session_on_dml(_session_providers(det), label="Detector")
        require_session_on_dml(_session_providers(cls), label="Classifier")
        require_session_on_dml(_session_providers(rec), label="Recognizer")

    def recognize(self, image: Any) -> str:
        result = self._engine(image)
        return layout_from_result(result)
