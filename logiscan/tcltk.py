"""Copy staged Tcl/Tk files from vendor/tcltk into the USB Python runtime."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from logiscan.config import APP_ROOT

TKINTER_PYD = "_tkinter.pyd"


def copy_tcltk(vendor: Path, runtime: Path) -> bool:
    runtime.mkdir(parents=True, exist_ok=True)
    src_pyd = vendor / TKINTER_PYD
    if not src_pyd.is_file() and not (runtime / TKINTER_PYD).is_file():
        return False
    if src_pyd.is_file():
        shutil.copy2(src_pyd, runtime / TKINTER_PYD)
    if vendor.is_dir():
        for dll in vendor.glob("tcl86*.dll"):
            shutil.copy2(dll, runtime / dll.name)
        for dll in vendor.glob("tk86*.dll"):
            shutil.copy2(dll, runtime / dll.name)
        for rel in ("tcl/tcl8.6", "tcl/tk8.6", "Lib/site-packages/tkinter"):
            src = vendor.joinpath(*rel.split("/"))
            dest = runtime.joinpath(*rel.split("/"))
            if src.is_dir():
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
    return (runtime / TKINTER_PYD).is_file()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy vendor/tcltk into runtime/python.")
    parser.parse_args(argv)
    vendor = APP_ROOT / "vendor" / "tcltk"
    runtime = APP_ROOT / "runtime" / "python"
    ok = copy_tcltk(vendor, runtime)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
