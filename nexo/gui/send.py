import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path
from typing import Optional

from nexo.core import send_file, send_directory
from nexo.gui.theme import SURFACE, FG, FONT_SM, GREEN, RED, YELLOW


_MODE_FILE = "File"
_MODE_DIR = "Directory"


def _fmt(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


class SendTab:
    def __init__(self, parent: ttk.Frame, status_bar: tk.Label):
        self.status_bar = status_bar
        self._iid_map: dict[str, str] = {}

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
        row2.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(row2, text="Target:").pack(side=tk.LEFT, padx=(0, 4))
        self.target_var = tk.StringVar(value="127.0.0.1:9000")
        ttk.Entry(row2, textvariable=self.target_var, width=25).pack(
            side=tk.LEFT, padx=(0, 8))

        self.send_btn = ttk.Button(row2, text="Send",
                                   command=self._send)
        self.send_btn.pack(side=tk.LEFT)

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

        self._log(f"Sending {label} '{name}' to {target} ...")

        def task():
            try:
                host, port_str = target.split(":")
                port = int(port_str)

                def prog(sent: int, total: int, fname: str) -> None:
                    self.log.winfo_toplevel().after(
                        0, self._on_progress, sent, total, fname)

                if is_dir:
                    send_directory(path, host, port, on_progress=prog)
                else:
                    # pre-insert the single-file row so progress works
                    fsize = Path(path).stat().st_size
                    self.log.winfo_toplevel().after(
                        0, self._insert_file, name, fsize)
                    send_file(path, host, port, on_progress=prog)
                self.log.winfo_toplevel().after(0, self._done, True, None)
            except Exception as e:
                self.log.winfo_toplevel().after(0, self._done, False, str(e))

        threading.Thread(target=task, daemon=True).start()

    def _insert_file(self, fname: str, fsize: int) -> None:
        iid = self.tree.insert("", tk.END,
                               values=(fname, _fmt(fsize), "Sending..."),
                               tags=("active",))
        self._iid_map[fname] = iid
        self.tree.see(iid)

    def _on_progress(self, sent: int, total: int, fname: str) -> None:
        if fname not in self._iid_map:
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
        self.status_bar.configure(text=fname)

    def _done(self, ok: bool, err: Optional[str]) -> None:
        self.send_btn.configure(state=tk.NORMAL)
        if ok:
            # mark all active rows as done
            for iid in list(self._iid_map.values()):
                self.tree.set(iid, "status", "Done")
                self.tree.item(iid, tags=("done",))
            self._log("✓ Transfer complete!")
        else:
            # mark remaining active rows as failed
            for iid in list(self._iid_map.values()):
                self.tree.set(iid, "status", "Failed")
                self.tree.item(iid, tags=("fail",))
            self._log(f"✗ Error: {err}")
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
