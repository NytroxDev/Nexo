import tkinter as tk
from tkinter import ttk
import threading
from pathlib import Path

from nexo.core import start_server
from nexo.gui.theme import SURFACE, FG, FONT_SM, GREEN, RED, YELLOW


def _fmt(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


class ReceiveTab:
    def __init__(self, parent: ttk.Frame, status_bar: tk.Label):
        self.status_bar = status_bar
        self.server = None
        self.running = False

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

        paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # table
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

        # log
        lf = ttk.Frame(paned)
        paned.add(lf, weight=1)

        self.log = tk.Text(lf, bg=SURFACE, fg=FG, font=FONT_SM,
                           wrap=tk.WORD, state=tk.DISABLED,
                           borderwidth=0, relief=tk.FLAT, padx=6, pady=4)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lscr = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.log.yview)
        self.log.configure(yscrollcommand=lscr.set)
        lscr.pack(side=tk.RIGHT, fill=tk.Y)

        self._iid_map = {}

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
        self._log("Server stopped")
        self.status_bar.configure(text="Ready")

    def _on_event(self, evt: str, data: dict) -> None:
        if evt == "file_start":
            iid = self.tree.insert("", tk.END,
                                   values=(data["filename"],
                                           _fmt(data["size"]),
                                           "Receiving..."),
                                   tags=("active",))
            self._iid_map[data["filename"]] = iid
            self._log(f"← {data['filename']} ({_fmt(data['size'])})")

        elif evt == "file_progress":
            iid = self._iid_map.get(data["filename"])
            if iid:
                pct = int(data["received"] / data["size"] * 100)
                self.tree.set(iid, "status", f"Receiving {pct}%")

        elif evt == "file_done":
            iid = self._iid_map.pop(data["filename"], None)
            if iid:
                self.tree.set(iid, "status", "Done")
                self.tree.item(iid, tags=("done",))
            self._log(f"✓ {data['filename']} ({_fmt(data['received'])})")
            self.status_bar.configure(text=f"Received {data['filename']}")

        elif evt == "file_abort":
            iid = self._iid_map.pop(data["filename"], None)
            if iid:
                self.tree.set(iid, "status", "Failed")
                self.tree.item(iid, tags=("fail",))
            self._log(f"✗ {data['filename']} — {data['reason']}")

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
