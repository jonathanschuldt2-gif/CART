"""Always-on-top Tkinter window that shows the ranked pack.

It is an ordinary separate window and never touches the game process. Arena
must be in Windowed or Borderless mode for any window to show above it.
"""
from __future__ import annotations

import queue
import tkinter as tk
from tkinter import font as tkfont

from .app import DraftHelper, Snapshot
from .console import pool_line

BG = "#16181d"
ROW_BG = "#1f2229"
TOP_BG = "#24452f"
FG = "#e8e8e8"
DIM = "#9aa0aa"
ACCENT = "#5ad17a"
PIP = {"W": "#f3eccf", "U": "#4a90d9", "B": "#8c7a8f", "R": "#e0533d", "G": "#3f9d55", "C": "#b5b5b5"}
MAX_ROWS = 15


class Overlay:
    def __init__(self, helper: DraftHelper, alpha: float = 0.93):
        self.helper = helper
        self.root = tk.Tk()
        self.root.title("MTG Draft Helper")
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", alpha)
        except tk.TclError:
            pass
        self.root.geometry("560x640+40+40")
        self.root.minsize(380, 240)

        base = tkfont.nametofont("TkDefaultFont").actual("family")
        self.f_title = tkfont.Font(family=base, size=11, weight="bold")
        self.f_name = tkfont.Font(family=base, size=10, weight="bold")
        self.f_small = tkfont.Font(family=base, size=8)

        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=10, pady=(8, 2))
        self.title_var = tk.StringVar(value="MTG Draft Helper")
        tk.Label(header, textvariable=self.title_var, bg=BG, fg=FG, font=self.f_title).pack(side="left")
        self.pin_var = tk.BooleanVar(value=True)
        tk.Checkbutton(header, text="On top", variable=self.pin_var, command=self._toggle_top,
                       bg=BG, fg=DIM, selectcolor=BG, activebackground=BG, activeforeground=FG,
                       font=self.f_small).pack(side="right")

        self.status_var = tk.StringVar(value="Starting…")
        tk.Label(self.root, textvariable=self.status_var, bg=BG, fg=DIM, font=self.f_small,
                 anchor="w", justify="left", wraplength=540).pack(fill="x", padx=10)

        self.list_frame = tk.Frame(self.root, bg=BG)
        self.list_frame.pack(fill="both", expand=True, padx=8, pady=6)

        self.pool_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.pool_var, bg=BG, fg=DIM, font=self.f_small,
                 anchor="w", justify="left", wraplength=540).pack(fill="x", padx=10, pady=(0, 8))
        self.root.bind("<Configure>", self._on_resize)

    def _toggle_top(self) -> None:
        self.root.attributes("-topmost", self.pin_var.get())

    def _on_resize(self, event) -> None:
        if event.widget is self.root:
            wrap = max(200, event.width - 20)
            for child in self.root.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(wraplength=wrap)

    # ---- drawing ------------------------------------------------------------
    def render(self, snap: Snapshot) -> None:
        self.status_var.set(snap.status)
        if snap.summary is None:  # status-only message: keep the list as it is
            return
        self.title_var.set(f"{snap.set_code or '?'} · {snap.fmt} · Pack {snap.pack_number} · Pick {snap.pick_number}")
        for w in self.list_frame.winfo_children():
            w.destroy()
        if snap.ranked:
            top, low = snap.ranked[0].score, snap.ranked[-1].score
            span = max(top - low, 0.5)
            for i, sc in enumerate(snap.ranked[:MAX_ROWS]):
                self._row(i, sc, (sc.score - low) / span)
        self.pool_var.set(pool_line(snap))

    def _row(self, index: int, sc, fraction: float) -> None:
        bg = TOP_BG if index == 0 else ROW_BG
        row = tk.Frame(self.list_frame, bg=bg)
        row.pack(fill="x", pady=1)

        pips = tk.Frame(row, bg=bg, width=46)
        pips.pack(side="left", padx=(6, 4), pady=4)
        for c in (sc.card.colors or "C"):
            tk.Label(pips, text="●", fg=PIP[c], bg=bg, font=self.f_name).pack(side="left")

        mid = tk.Frame(row, bg=bg)
        mid.pack(side="left", fill="x", expand=True)
        tk.Label(mid, text=f"{index + 1}. {sc.card.name}", bg=bg, fg=FG, font=self.f_name,
                 anchor="w").pack(fill="x")
        tk.Label(mid, text=sc.reason, bg=bg, fg=DIM, font=self.f_small, anchor="w").pack(fill="x")

        bar = tk.Canvas(row, width=70, height=10, bg=bg, highlightthickness=0)
        bar.pack(side="right", padx=8)
        bar.create_rectangle(0, 0, 70, 10, fill="#2c3038", width=0)
        bar.create_rectangle(0, 0, max(3, int(70 * fraction)), 10, fill=ACCENT if index == 0 else "#6b7280", width=0)
        tk.Label(row, text=f"{sc.score:+.2f}", bg=bg, fg=FG, font=self.f_small).pack(side="right")

    # ---- loop -----------------------------------------------------------
    def _poll(self) -> None:
        # Draw only the newest full update, but show every status message.
        latest = None
        try:
            while True:
                snap = self.helper.updates.get_nowait()
                if snap.summary is None:
                    self.render(snap)
                else:
                    latest = snap
        except queue.Empty:
            pass
        if latest is not None:
            self.render(latest)
        self.root.after(200, self._poll)

    def run(self) -> None:
        self.root.after(100, self._poll)
        self.root.mainloop()
