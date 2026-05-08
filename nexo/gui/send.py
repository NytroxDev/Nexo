import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path

from nexo.core import send_file
from nexo.gui.theme import SURFACE, FG, FONT_SM


class SendTab:
    def __init__(self, parent: ttk.Frame, status_bar: tk.Label):
        self.status_bar = status_bar

        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(row, text="File:").pack(side=tk.LEFT, padx=(0, 4))
        self.path_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.path_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(row, text="Browse",
                   command=self._browse).pack(side=tk.LEFT)

        row2 = ttk.Frame(parent)
        row2.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(row2, text="Target:").pack(side=tk.LEFT, padx=(0, 4))
        self.target_var = tk.StringVar(value="127.0.0.1:9000")
        ttk.Entry(row2, textvariable=self.target_var, width=25).pack(
            side=tk.LEFT, padx=(0, 8))

        self.send_btn = ttk.Button(row2, text="Send",
                                   command=self._send)
        self.send_btn.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(parent, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(0, 8))
        self.progress["maximum"] = 100

        self.log = tk.Text(parent, bg=SURFACE, fg=FG, font=FONT_SM,
                           wrap=tk.WORD, state=tk.DISABLED,
                           borderwidth=0, relief=tk.FLAT, padx=6, pady=4)
        self.log.pack(fill=tk.BOTH, expand=True)

    def _browse(self) -> None:
        f = filedialog.askopenfilename()
        if f:
            self.path_var.set(f)

    def _send(self) -> None:
        path = self.path_var.get()
        target = self.target_var.get()
        if not path or not target:
            messagebox.showwarning("Nexo", "Select a file and enter a target.")
            return

        self.send_btn.configure(state=tk.DISABLED)
        self.progress["value"] = 0
        self._log(f"Sending {Path(path).name} to {target} ...")

        def task():
            try:
                host, port_str = target.split(":")
                send_file(path, host, int(port_str))
                self.log.winfo_toplevel().after(0, self._done, True, None)
            except Exception as e:
                self.log.winfo_toplevel().after(0, self._done, False, str(e))

        threading.Thread(target=task, daemon=True).start()

    def _done(self, ok: bool, err: str | None) -> None:
        self.send_btn.configure(state=tk.NORMAL)
        if ok:
            self.progress["value"] = 100
            self._log("✓ Transfer complete!")
        else:
            self._log(f"✗ Error: {err}")
        self.status_bar.configure(text="Ready")

    def _log(self, msg: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)
