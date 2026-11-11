"""Plain-text output: used with --console, or when Tkinter isn't available."""
from __future__ import annotations

import queue

from .app import DraftHelper, Snapshot


def format_snapshot(snap: Snapshot, top: int = 15) -> str:
    lines = []
    if snap.pack_number:
        lines.append(f"=== {snap.set_code} {snap.fmt} | Pack {snap.pack_number} Pick {snap.pick_number} ===")
    lines.append(snap.status)
    for i, sc in enumerate(snap.ranked[:top], 1):
        colors = sc.card.colors or "C"
        lines.append(f"{'>>' if i == 1 else '  '} {i:2}. {sc.card.name:<32} [{colors:<3}] {sc.score:+.2f}  {sc.reason}")
    if snap.summary:
        lines.append(pool_line(snap))
    return "\n".join(lines)


def pool_line(snap: Snapshot) -> str:
    s = snap.summary
    weights = " ".join(f"{c}:{w:.1f}" for c, w in s.color_weights.items() if w > 0) or "-"
    curve = " ".join(f"{mv}{'+' if mv == 6 else ''}:{n}" for mv, n in sorted(s.curve.items())) or "-"
    return (f"Pool {s.size} cards | colors {weights} | main {s.main_colors or '-'} "
            f"(commit {s.commitment:.0%}) | creatures {s.creatures} | 2-drops {s.two_drops} | curve {curve}")


def run_console(helper: DraftHelper) -> None:
    last = None
    try:
        while True:
            try:
                snap = helper.updates.get(timeout=0.5)
            except queue.Empty:
                continue
            text = format_snapshot(snap)
            if text != last:
                print("\n" + text, flush=True)
                last = text
    except KeyboardInterrupt:
        pass
