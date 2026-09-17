"""Shared desktop styling using Tk's bundled, cross-platform theme."""
from tkinter import ttk
from .settings import WINDOWS

BACKGROUND = "#eef2f6"
SURFACE = "#ffffff"
INK = "#172b42"
MUTED = "#526579"
ACCENT = "#2463a6"


def configure_style(window):
    window.configure(background=BACKGROUND)
    style = ttk.Style(window)
    style.theme_use("clam")
    font = "Segoe UI" if WINDOWS else "Helvetica"
    style.configure(".", font=(font, 10), background=SURFACE, foreground=INK)
    style.configure("TFrame", background=SURFACE)
    style.configure("Page.TFrame", background=BACKGROUND)
    style.configure("TLabel", background=SURFACE, foreground=INK)
    style.configure("Title.TLabel", background=BACKGROUND, font=(font, 23, "bold"))
    style.configure("Subtitle.TLabel", background=BACKGROUND, foreground=MUTED)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Section.TLabel", font=(font, 10, "bold"))
    style.configure("Version.TLabel", background="#dfeaf5", foreground=ACCENT, padding=(10, 5))
    style.configure("TButton", padding=(12, 5), background="#edf3f9", bordercolor="#cbd7e3", relief="flat")
    style.map("TButton", background=[("disabled", "#f0f2f5"), ("pressed", "#cedded"), ("active", "#dfebf7")], foreground=[("disabled", "#778492")])
    style.configure("Primary.TButton", background=ACCENT, foreground="white", bordercolor=ACCENT)
    style.map("Primary.TButton", background=[("disabled", "#dce3ea"), ("pressed", "#174776"), ("active", "#1d558f")], foreground=[("disabled", "#687888"), ("!disabled", "white")])
    style.configure("Stop.TButton", foreground="#9b3535")
    style.map("Stop.TButton", foreground=[("disabled", "#778492"), ("!disabled", "#9b3535")])
    style.configure("TEntry", padding=4, fieldbackground=SURFACE, bordercolor="#cbd7e3")
    style.map("TEntry", fieldbackground=[("disabled", "#f0f2f5"), ("readonly", "#f5f7fa")], foreground=[("disabled", "#778492")], bordercolor=[("focus", ACCENT)])
    style.configure("TRadiobutton", padding=(0, 5), background=SURFACE)
    style.map("TRadiobutton", background=[("active", SURFACE)])
    style.configure("TNotebook", background=BACKGROUND, borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", padding=(18, 7), background="#e2e8f0", foreground=MUTED)
    style.map("TNotebook.Tab", background=[("selected", SURFACE), ("active", "#eaf0f7")], foreground=[("selected", ACCENT)])
    return style
