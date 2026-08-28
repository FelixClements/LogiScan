"""Tkinter operator console for the USB-portable LogiScan filer."""

from __future__ import annotations

import base64
import threading
from pathlib import Path

from logiscan.batch import BatchCallbacks, require_dir, run_batch
from logiscan.config import APP_ROOT, STATUS_ERROR, Config
from logiscan.gui_prefs import GuiPrefs, load_prefs, save_prefs
from logiscan.images import list_images
from logiscan.preview import thumbnail_png

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None  # type: ignore[assignment]
    filedialog = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]


def _message_box(title: str, text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:
        print(f"{title}: {text}")


if tk is not None:

    class App(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title("LogiScan")
            self.minsize(900, 560)
            self._stop = threading.Event()
            self._worker: threading.Thread | None = None
            self._closing = False
            self._photo_image: tk.PhotoImage | None = None
            prefs = load_prefs(APP_ROOT)
            self._build(prefs)
            self.protocol("WM_DELETE_WINDOW", self._on_close)
            self._set_running(False)

        def _build(self, prefs: GuiPrefs) -> None:
            pad = {"padx": 8, "pady": 4}
            top = ttk.Frame(self)
            top.pack(fill="x")
            ttk.Label(top, text="Photos", width=10).grid(row=0, column=0, sticky="w", **pad)
            self.photos_var = tk.StringVar(value=str(prefs.photos_dir))
            self.photos_entry = ttk.Entry(top, textvariable=self.photos_var)
            self.photos_entry.grid(row=0, column=1, sticky="ew", **pad)
            self.photos_browse = ttk.Button(top, text="Browse", command=self._browse_photos)
            self.photos_browse.grid(row=0, column=2, **pad)
            ttk.Label(top, text="PO root", width=10).grid(row=1, column=0, sticky="w", **pad)
            self.search_var = tk.StringVar(
                value="" if prefs.search_root is None else str(prefs.search_root)
            )
            self.search_entry = ttk.Entry(top, textvariable=self.search_var)
            self.search_entry.grid(row=1, column=1, sticky="ew", **pad)
            self.search_browse = ttk.Button(top, text="Browse", command=self._browse_search)
            self.search_browse.grid(row=1, column=2, **pad)
            top.columnconfigure(1, weight=1)

            controls = ttk.Frame(self)
            controls.pack(fill="x")
            self.run_btn = ttk.Button(controls, text="Run", command=self._on_run)
            self.run_btn.pack(side="left", **pad)
            self.cancel_btn = ttk.Button(controls, text="Cancel", command=self._on_cancel)
            self.cancel_btn.pack(side="left", **pad)
            self.count_var = tk.StringVar(value="0 / 0")
            ttk.Label(controls, textvariable=self.count_var).pack(side="left", **pad)
            self.progress = ttk.Progressbar(controls, mode="determinate")
            self.progress.pack(side="left", fill="x", expand=True, **pad)

            body = ttk.Frame(self)
            body.pack(fill="both", expand=True)
            self.preview = tk.Label(body, width=40, height=18, bg="#222222", fg="#aaaaaa", text="")
            self.preview.pack(side="left", fill="y", padx=8, pady=4)
            columns = ("filename", "trailer", "seal", "status")
            self.tree = ttk.Treeview(body, columns=columns, show="headings")
            for key, heading in (
                ("filename", "Filename"),
                ("trailer", "Trailer"),
                ("seal", "Seal"),
                ("status", "Status"),
            ):
                self.tree.heading(key, text=heading)
                self.tree.column(key, width=140 if key != "filename" else 220)
            scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=scroll.set)
            self.tree.pack(side="left", fill="both", expand=True, pady=4)
            scroll.pack(side="left", fill="y")

            self.footer_var = tk.StringVar(value="")
            ttk.Label(self, textvariable=self.footer_var).pack(fill="x", **pad)

        def _browse_photos(self) -> None:
            chosen = filedialog.askdirectory(title="Photos")
            if chosen:
                self.photos_var.set(chosen)

        def _browse_search(self) -> None:
            chosen = filedialog.askdirectory(title="PO root")
            if chosen:
                self.search_var.set(chosen)

        def _set_running(self, running: bool) -> None:
            state_run = "disabled" if running else "normal"
            state_cancel = "normal" if running else "disabled"
            state_fields = "disabled" if running else "normal"
            self.run_btn.configure(state=state_run)
            self.cancel_btn.configure(state=state_cancel)
            self.photos_browse.configure(state=state_fields)
            self.search_browse.configure(state=state_fields)
            self.photos_entry.configure(state=state_fields)
            self.search_entry.configure(state=state_fields)

        def _on_run(self) -> None:
            photos = Path(self.photos_var.get().strip())
            search = Path(self.search_var.get().strip())
            if not self.search_var.get().strip():
                messagebox.showerror("LogiScan", "PO root is required")
                return
            for path, label in ((photos, "Input directory"), (search, "Search root")):
                error = require_dir(path, label)
                if error:
                    messagebox.showerror("LogiScan", error)
                    return
            config = Config(photos_dir=photos, search_root=search).resolved()
            images = list_images(config.photos_dir, config.image_suffixes)
            if not images:
                messagebox.showinfo("LogiScan", f"No image files in {config.photos_dir}")
                return
            save_prefs(APP_ROOT, GuiPrefs(photos_dir=photos, search_root=search))
            for item in self.tree.get_children():
                self.tree.delete(item)
            for path in images:
                self.tree.insert("", "end", iid=path.name, values=(path.name, "", "", ""))
            self.progress["maximum"] = len(images)
            self.progress["value"] = 0
            self.count_var.set(f"0 / {len(images)}")
            self.footer_var.set("")
            self._stop.clear()
            self._set_running(True)
            self._worker = threading.Thread(target=self._worker_main, args=(config,), daemon=True)
            self._worker.start()

        def _worker_main(self, config: Config) -> None:
            def on_phase(message: str) -> None:
                self.after(0, lambda m=message: self.footer_var.set(m))

            def on_begin(index: int, total: int, path: Path) -> None:
                png: bytes | None
                try:
                    png = thumbnail_png(path)
                except ValueError:
                    png = None
                self.after(
                    0,
                    lambda i=index, n=total, p=path, b=png: self._photo_begin_ui(i, n, p, b),
                )

            def on_done(index: int, total: int, result) -> None:
                self.after(
                    0,
                    lambda i=index, n=total, r=result: self._photo_done_ui(i, n, r),
                )

            code = run_batch(
                config,
                callbacks=BatchCallbacks(
                    on_phase=on_phase,
                    on_photo_begin=on_begin,
                    on_photo_done=on_done,
                    should_stop=self._stop.is_set,
                ),
            )
            self.after(0, lambda c=code: self._batch_finished(c))

        def _photo_begin_ui(
            self, index: int, total: int, path: Path, png: bytes | None
        ) -> None:
            self.count_var.set(f"{index} / {total}")
            self.progress["value"] = index - 1
            if path.name in self.tree.get_children():
                self.tree.set(path.name, "status", "…")
                self.tree.see(path.name)
            if png is None:
                self._photo_image = None
                self.preview.configure(image="", text=path.name, bg="#222222")
                self.footer_var.set(f"Preview failed: {path.name}")
                return
            self._photo_image = tk.PhotoImage(data=base64.standard_b64encode(png))
            self.preview.configure(image=self._photo_image, text="")

        def _photo_done_ui(self, index: int, total: int, result) -> None:
            self.progress["value"] = index
            self.count_var.set(f"{index} / {total}")
            iid = result.filename
            if iid in self.tree.get_children():
                self.tree.item(
                    iid,
                    values=(
                        result.filename,
                        result.trailer or "",
                        result.seal or "",
                        result.status,
                    ),
                )
            if result.status == STATUS_ERROR and result.error:
                self.footer_var.set(result.error)

        def _batch_finished(self, code: int) -> None:
            self._set_running(False)
            if code == 2:
                messagebox.showerror(
                    "LogiScan",
                    "DirectML iGPU is required; refusing CPU OCR.",
                )
            if self._closing:
                self.destroy()

        def _on_cancel(self) -> None:
            self._stop.set()
            self.footer_var.set("Stopping…")

        def _on_close(self) -> None:
            worker = self._worker
            if worker is not None and worker.is_alive():
                self._closing = True
                self._stop.set()
                self.footer_var.set("Stopping…")
                return
            self.destroy()


def main() -> int:
    if tk is None:
        _message_box(
            "LogiScan",
            "tkinter is missing. Re-run scripts\\prepare.ps1 on a trusted PC.",
        )
        return 1
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
