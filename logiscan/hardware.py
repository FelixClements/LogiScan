"""DirectML hard-fail and OpenCL image-filter probe."""

from __future__ import annotations

import logging
from typing import Any, Sequence

from logiscan.config import APP_ROOT, BACKEND_DML

LOGGER = logging.getLogger("logiscan")
DML_PROVIDER = "DmlExecutionProvider"


class DirectMLUnavailableError(RuntimeError):
    """Raised when OCR cannot run on DirectML / iGPU."""


def ort_providers() -> list[str]:
    import onnxruntime as ort

    return list(ort.get_available_providers())


def dml_available() -> bool:
    return DML_PROVIDER in ort_providers()


def require_directml() -> None:
    providers = ort_providers()
    if DML_PROVIDER not in providers:
        raise DirectMLUnavailableError(
            "DmlExecutionProvider is not available. "
            f"ORT providers: {providers}. "
            "Install onnxruntime-directml (not CPU onnxruntime) and rerun."
        )


def require_session_on_dml(providers: Sequence[str], *, label: str) -> None:
    if not providers or providers[0] != DML_PROVIDER:
        raise DirectMLUnavailableError(
            f"{label} is not running on DirectML (first provider={providers!r}). "
            "Refusing CPU OCR fallback."
        )


def enable_opencl(cv2: Any) -> bool:
    try:
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)
            LOGGER.info("OpenCV OpenCL enabled for iGPU image filters.")
            return bool(cv2.ocl.useOpenCL())
    except Exception as exc:
        LOGGER.warning("OpenCV OpenCL not usable: %s", exc)
    LOGGER.warning("Pass 2 image filters will run on CPU (OCR remains DirectML).")
    return False


def probe_hardware() -> int:
    """Print DirectML / OpenCL status. Exit 0 only when DML is present."""
    print(f"App root: {APP_ROOT}")
    dml_ok = False
    try:
        providers = ort_providers()
        print(f"onnxruntime providers: {providers}")
        dml_ok = DML_PROVIDER in providers
        print(f"DmlExecutionProvider present: {dml_ok}")
    except Exception as exc:
        print(f"ONNX Runtime probe failed: {exc}")
    try:
        import cv2

        print(f"cv2.ocl.haveOpenCL(): {cv2.ocl.haveOpenCL()}")
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)
            print(f"cv2.ocl.useOpenCL(): {cv2.ocl.useOpenCL()}")
    except Exception as exc:
        print(f"OpenCV OpenCL probe failed: {exc}")
    if not dml_ok:
        print("FAIL: DirectML is required. No CPU OCR fallback.")
        return 1
    print(f"OK: iGPU OCR backend will be {BACKEND_DML}")
    return 0
