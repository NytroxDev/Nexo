from tkinter import ttk

BG = "#2b2b3d"
FG = "#e0e0f0"
SURFACE = "#363649"
ACCENT = "#7aa2f7"
RED = "#f7768e"
GREEN = "#9ece6a"
YELLOW = "#e0af68"
BORDER = "#1a1a2e"

FONT = ("Segoe UI", 10)
FONT_SM = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 10, "bold")


def apply() -> None:
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=FG, font=FONT)

    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG)

    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=SURFACE, foreground=FG,
                    padding=[10, 3], font=FONT_BOLD)
    style.map("TNotebook.Tab",
              background=[("selected", ACCENT)],
              foreground=[("selected", BG)])

    style.configure("TEntry",
                    fieldbackground=SURFACE,
                    foreground=FG,
                    insertcolor=FG,
                    borderwidth=0,
                    padding=4)
    style.map("TEntry",
              fieldbackground=[("focus", "#40405a")])

    style.configure("TButton", background=ACCENT, foreground=BG,
                    padding=[10, 5], font=FONT_BOLD, borderwidth=0)
    style.map("TButton",
              background=[("active", "#89b4fa")])

    style.configure("Stop.TButton", background=RED, foreground=BG)
    style.map("Stop.TButton",
              background=[("active", "#e64553")])

    style.configure("Treeview", background=SURFACE, foreground=FG,
                    fieldbackground=SURFACE, borderwidth=0,
                    rowheight=26)
    style.configure("Treeview.Heading", background=SURFACE, foreground=FG,
                    font=FONT_BOLD, borderwidth=0, padding=3)
    style.map("Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", BG)])

    style.configure("Horizontal.TProgressbar", background=ACCENT,
                    troughcolor=SURFACE, borderwidth=0, thickness=10)

    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
