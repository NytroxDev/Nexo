import tkinter as tk
from tkinter import ttk

from nexo.gui import theme
from nexo.gui.config import load as load_config, save as save_config
from nexo.gui.receive import ReceiveTab
from nexo.gui.send import SendTab
from nexo.gui.theme import SURFACE, FG, FONT_SM


class NexoGUI:
    def __init__(self) -> None:
        cfg = load_config()

        self.root = tk.Tk()
        self.root.title("Nexo")
        self.root.geometry(cfg.get("geometry", "680x480"))
        self.root.minsize(600, 380)
        self.root.configure(bg=theme.BG)

        theme.apply()

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        r_frame = ttk.Frame(nb)
        nb.add(r_frame, text="  Receive  ")
        s_frame = ttk.Frame(nb)
        nb.add(s_frame, text="  Send  ")

        bar = tk.Frame(self.root, bg=SURFACE, height=26)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        self.status = tk.Label(bar, text="Ready", bg=SURFACE, fg=FG,
                               font=FONT_SM, anchor=tk.W, padx=8)
        self.status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.recv_tab = ReceiveTab(r_frame, self.status)
        self.send_tab = SendTab(s_frame, self.status)

        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _close(self) -> None:
        save_config({"geometry": self.root.geometry()})
        self.recv_tab.shutdown()
        self.send_tab.shutdown()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def launch_gui() -> None:
    NexoGUI().run()
