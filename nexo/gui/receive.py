import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from pathlib import Path
from typing import Optional

from nexo.core import start_server
from nexo.gui.theme import SURFACE, FG, FONT_SM, GREEN, RED, YELLOW


def _fmt(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


def _fmt_speed(bps: float) -> str:
    if bps >= 1_048_576:
        return f"{bps / 1_048_576:.1f} MB/s"
    if bps >= 1024:
        return f"{bps / 1024:.1f} KB/s"
    return f"{bps:.0f} B/s"


class ReceiveTab:
    def __init__(self, parent: ttk.Frame, status_bar: tk.Label):
        self.status_bar = status_bar
        self.server = None
        self.running = False

        # stats tracking
        self._start_time = 0.0
        self._bytes_received = 0
        self._cur_fname = ""
        self._cur_received = 0
        self._files_done = 0

        ctrl = ttk.Frame(parent)
        ctrl.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(ctrl, text="Port:").pack(side=tk.LEFT, padx=(0, 4))
        self.port_entry = ttk.Entry(ctrl, width=7)
        self.port_entry.insert(0, "9000")
        self.port_entry.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(ctrl, text="Save to:").pack(side=tk.LEFT, padx=(0, 4))
        self.dir_var = tk.StringVar(value=str(Path.home() / "Downloads"))
        e = ttk.Entry(ctrl, textvariable=self.dir_var)
        e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(ctrl, text="Browse",
                   command=self._browse).pack(side=tk.LEFT, padx=(0, 8))

        self.toggle_btn = ttk.Button(ctrl, text="Start",
                                     command=self._toggle)
        self.toggle_btn.pack(side=tk.LEFT)

        # stats bar
        self.stats_var = tk.StringVar()
        stats_bar = ttk.Label(ctrl, textvariable=self.stats_var,
                              font=FONT_SM, anchor=tk.W,
                              background=SURFACE, foreground=FG)
        stats_bar.pack(side=tk.RIGHT, padx=(8, 0))

        paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        tw = ttk.Frame(paned)
        paned.add(tw, weight=2)

        cols = ("file", "size", "status")
        self.tree = ttk.Treeview(tw, columns=cols, show="headings",
                                 height=6)
        self.tree.heading("file", text="File")
        self.tree.heading("size", text="Size")
        self.tree.heading("status", text="Status")
        self.tree.column("file", width=220)
        self.tree.column("size", width=90, anchor=tk.CENTER)
        self.tree.column("status", width=130, anchor=tk.CENTER)

        scr = ttk.Scrollbar(tw, orient=tk.VERTICAL,
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=scr.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scr.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("done", foreground=GREEN)
        self.tree.tag_configure("active", foreground=YELLOW)
        self.tree.tag_configure("fail", foreground=RED)

        lf = ttk.Frame(paned)
        paned.add(lf, weight=1)

        self.log = tk.Text(lf, bg=SURFACE, fg=FG, font=FONT_SM,
                           wrap=tk.WORD, state=tk.DISABLED,
                           borderwidth=0, relief=tk.FLAT, padx=6, pady=4)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lscr = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.log.yview)
        self.log.configure(yscrollcommand=lscr.set)
        lscr.pack(side=tk.RIGHT, fill=tk.Y)

        self._iid_map: dict[str, str] = {}
        self._output_dir: Path = Path.home() / "Downloads"
        self._dir_root: Optional[Path] = None
        self._file_paths: dict[str, Path] = {}

        self.tree.bind("<Double-1>", self._on_double_click)

    def _browse(self) -> None:
        d = tk.filedialog.askdirectory(initialdir=self.dir_var.get())
        if d:
            self.dir_var.set(d)

    def _toggle(self) -> None:
        if self.running:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        port = int(self.port_entry.get())
        out = Path(self.dir_var.get())

        self.tree.delete(*self.tree.get_children())
        self._iid_map.clear()
        self._clear_log()
        self._output_dir = out
        self._dir_root = None
        self._file_paths.clear()
        self._start_time = time.time()
        self._bytes_received = 0
        self._cur_fname = ""
        self._cur_received = 0
        self._files_done = 0
        self.stats_var.set("")

        def cb(evt: str, data: dict) -> None:
            self.tree.winfo_toplevel().after(0, self._on_event, evt, data)

        def target():
            self.server = start_server("0.0.0.0", port, out, on_event=cb)

        threading.Thread(target=target, daemon=True).start()

        self.running = True
        self.toggle_btn.configure(text="Stop", style="Stop.TButton")
        self.port_entry.configure(state=tk.DISABLED)
        self._log(f"Server listening on port {port}")
        self.status_bar.configure(text=f"Receiving on :{port}")

    def _stop(self) -> None:
        if self.server:
            self.server.close_all()
            self.server = None
        self.running = False
        self.toggle_btn.configure(text="Start", style="TButton")
        self.port_entry.configure(state=tk.NORMAL)
        self._set_title()
        self._log("Server stopped")
        self.status_bar.configure(text="Ready")
        self.stats_var.set("")

    def _set_title(self, text: str = "") -> None:
        self.status_bar.winfo_toplevel().title(
            f"Nexo — {text}" if text else "Nexo")

    def _on_event(self, evt: str, data: dict) -> None:
        if evt == "file_start":
            self._file_paths[data["filename"]] = (
                self._dir_root or self._output_dir) / data["filename"]
            iid = self.tree.insert("", tk.END,
                                   values=(data["filename"],
                                           _fmt(data["size"]),
                                           "Receiving..."),
                                   tags=("active",))
            self._iid_map[data["filename"]] = iid
            self.tree.see(iid)

        elif evt == "file_progress":
            # track byte delta
            fname = data["filename"]
            recv = data["received"]
            if fname == self._cur_fname:
                delta = recv - self._cur_received
            else:
                delta = recv
                self._cur_fname = fname
            self._bytes_received += delta
            self._cur_received = recv

            iid = self._iid_map.get(fname)
            if iid and data["size"]:
                pct = int(recv / data["size"] * 100)
                self.tree.set(iid, "status", f"Receiving {pct}%")
                self.tree.see(iid)
                self._set_title(f"Receiving {fname} ({pct}%)")

            # stats
            elapsed = time.time() - self._start_time
            speed = self._bytes_received / elapsed if elapsed > 0 else 0
            parts = [f"Speed: {_fmt_speed(speed)}"]
            if self._files_done or self._bytes_received:
                parts.append(f"Received: {_fmt(self._bytes_received)}")
            self.stats_var.set("  |  ".join(parts))

        elif evt == "file_done":
            iid = self._iid_map.pop(data["filename"], None)
            if iid:
                self.tree.set(iid, "status", "Done")
                self.tree.item(iid, tags=("done",))
            self._files_done += 1
            self.status_bar.configure(text=f"Received {data['filename']}")
            if not self._iid_map:
                self._set_title()

        elif evt == "dir_start":
            self._dir_root = self._output_dir / data["base"]

        elif evt == "dir_done":
            self._dir_root = None
            self._set_title()
            self._log(f"✓ Transfer complete: {data['base']}")

        elif evt == "file_abort":
            iid = self._iid_map.pop(data["filename"], None)
            if iid:
                self.tree.set(iid, "status", "Failed")
                self.tree.item(iid, tags=("fail",))
            self._log(f"✗ {data['filename']} — {data['reason']}")

    def _on_double_click(self, event: tk.Event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        tags = self.tree.item(sel[0], "tags")
        if "done" not in tags:
            return
        filename = self.tree.set(sel[0], "file")
        path = self._file_paths.get(filename)
        if not path or not path.exists():
            messagebox.showerror("Nexo", f"File not found:\n{path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Nexo", f"Failed to open file:\n{e}")

    def _log(self, msg: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def shutdown(self) -> None:
        if self.server:
            self.server.close_all()
