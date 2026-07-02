from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path
from typing import Optional

from nexo.core.client import NexoClient
from nexo.gui.theme import SURFACE, FG, FONT_SM, GREEN, RED, YELLOW


_MODE_FILE = "File"
_MODE_DIR = "Directory"


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


class SendTab:
    def __init__(self, parent: ttk.Frame, status_bar: tk.Label):
        self.status_bar = status_bar
        self._iid_map: dict[str, str] = {}
        self._client: Optional[NexoClient] = None
        self._cancelled = False

        # stats tracking
        self._start_time = 0.0
        self._bytes_sent = 0
        self._cur_fname = ""
        self._cur_sent = 0
        self._files_done = 0
        self._total_files = 0

        # top controls
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 6))

        self.mode_var = tk.StringVar(value=_MODE_FILE)
        ttk.Radiobutton(row, text=_MODE_FILE, variable=self.mode_var,
                        value=_MODE_FILE, command=self._mode_changed).pack(
            side=tk.LEFT, padx=(0, 4))
        ttk.Radiobutton(row, text=_MODE_DIR, variable=self.mode_var,
                        value=_MODE_DIR, command=self._mode_changed).pack(
            side=tk.LEFT, padx=(0, 12))

        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(row, textvariable=self.path_var)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.browse_btn = ttk.Button(row, text="Browse",
                                     command=self._browse)
        self.browse_btn.pack(side=tk.LEFT)

        row2 = ttk.Frame(parent)
        row2.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(row2, text="Target:").pack(side=tk.LEFT, padx=(0, 4))
        self.target_var = tk.StringVar(value="127.0.0.1:9000")
        ttk.Entry(row2, textvariable=self.target_var, width=25).pack(
            side=tk.LEFT, padx=(0, 8))

        self.send_btn = ttk.Button(row2, text="Send",
                                   command=self._send)
        self.send_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.cancel_btn = ttk.Button(row2, text="Cancel",
                                     command=self._cancel,
                                     state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT)

        # stats bar
        self.stats_var = tk.StringVar()
        stats_bar = ttk.Label(parent, textvariable=self.stats_var,
                              font=FONT_SM, anchor=tk.W,
                              background=SURFACE, foreground=FG)
        stats_bar.pack(fill=tk.X, pady=(0, 4))

        # paned: treeview on top, log below
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

    def _mode_changed(self) -> None:
        self.path_var.set("")

    def _browse(self) -> None:
        if self.mode_var.get() == _MODE_DIR:
            d = filedialog.askdirectory()
            if d:
                self.path_var.set(d)
        else:
            f = filedialog.askopenfilename()
            if f:
                self.path_var.set(f)

    def _send(self) -> None:
        path = self.path_var.get()
        target = self.target_var.get()
        if not path or not target:
            messagebox.showwarning("Nexo", "Select a file/directory and enter a target.")
            return

        name = Path(path).name
        is_dir = self.mode_var.get() == _MODE_DIR
        label = "Directory" if is_dir else "File"

        self.send_btn.configure(state=tk.DISABLED)
        self._clear_log()
        self.tree.delete(*self.tree.get_children())
        self._iid_map.clear()
        self._cancelled = False
        self.cancel_btn.configure(state=tk.NORMAL)

        # reset stats
        self._start_time = time.time()
        self._bytes_sent = 0
        self._cur_fname = ""
        self._cur_sent = 0
        self._files_done = 0
        self._total_files = 0
        self.stats_var.set("")

        self._log(f"Sending {label} '{name}' to {target} ...")

        def task():
            try:
                host, port_str = target.split(":")
                port = int(port_str)

                def prog(sent: int, total: int, fname: str) -> None:
                    self.log.winfo_toplevel().after(
                        0, self._on_progress, sent, total, fname)

                c = NexoClient()
                self._client = c
                if is_dir:
                    c.send_directory(path, host, port, on_progress=prog)
                else:
                    fsize = Path(path).stat().st_size
                    self.log.winfo_toplevel().after(
                        0, self._insert_file, name, fsize)
                    c.send(path, host, port, on_progress=prog)
                self.log.winfo_toplevel().after(0, self._done, True, None)
            except Exception:
                self.log.winfo_toplevel().after(0, self._done, False, None)

        threading.Thread(target=task, daemon=True).start()

    def _cancel(self) -> None:
        self._cancelled = True
        self.cancel_btn.configure(state=tk.DISABLED)
        if self._client:
            self._client.cancel()
        self._log("Cancelling...")

    def _insert_file(self, fname: str, fsize: int) -> None:
        iid = self.tree.insert("", tk.END,
                               values=(fname, _fmt(fsize), "Sending..."),
                               tags=("active",))
        self._iid_map[fname] = iid
        self.tree.see(iid)

    def _on_progress(self, sent: int, total: int, fname: str) -> None:
        # track per-file byte delta
        if fname == self._cur_fname:
            delta = sent - self._cur_sent
        else:
            delta = sent
            if self._cur_fname:
                self._files_done += 1
            self._cur_fname = fname
        self._bytes_sent += delta
        self._cur_sent = sent

        # treeview row
        if fname not in self._iid_map:
            self._total_files += 1
            iid = self.tree.insert("", tk.END,
                                   values=(fname, _fmt(total), "Sending..."),
                                   tags=("active",))
            self._iid_map[fname] = iid
            self.tree.see(iid)
        iid = self._iid_map[fname]
        if total:
            pct = int(sent / total * 100)
            self.tree.set(iid, "status", f"Sending {pct}%")
            self.tree.see(iid)

        # stats
        elapsed = time.time() - self._start_time
        speed = self._bytes_sent / elapsed if elapsed > 0 else 0
        parts = [f"Speed: {_fmt_speed(speed)}"]
        if self._total_files > 1:
            parts.append(f"Files: {self._files_done}/{self._total_files}")
        self.stats_var.set("  |  ".join(parts))
        self.status_bar.configure(text=fname)

    def _done(self, ok: bool, err: Optional[str]) -> None:
        self.send_btn.configure(state=tk.NORMAL)
        self.cancel_btn.configure(state=tk.DISABLED)
        if self._cancelled:
            for iid in list(self._iid_map.values()):
                self.tree.set(iid, "status", "Cancelled")
                self.tree.item(iid, tags=("fail",))
            self._log("✗ Cancelled")
            self.stats_var.set("")
        elif ok:
            for iid in list(self._iid_map.values()):
                self.tree.set(iid, "status", "Done")
                self.tree.item(iid, tags=("done",))
            # final stats
            elapsed = time.time() - self._start_time
            avg_speed = self._bytes_sent / elapsed if elapsed > 0 else 0
            self.stats_var.set(f"Completed — "
                               f"{_fmt(self._bytes_sent)} in {elapsed:.1f}s "
                               f"({_fmt_speed(avg_speed)})")
            self._log("✓ Transfer complete!")
        else:
            for iid in list(self._iid_map.values()):
                self.tree.set(iid, "status", "Failed")
                self.tree.item(iid, tags=("fail",))
            self._log("✗ Transfer failed")
            self.stats_var.set("")
        self.status_bar.configure(text="Ready")

    def _log(self, msg: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)
