#!/usr/bin/env python3
"""P153: the loop's post-close tracking, straight from the `[policy-trace]` rows.

The trace prints `jaw_y`, `fruit_y` and `jaw_z`/`fruit_z` every 4 control ticks
(= one 30 Hz frame). For each episode this regresses `jaw_y - fruit_y` on the
frame index over the 17 frames after the `[close]` latch and reports the slope
(mm/frame), plus the jaw's and the fruit's downstream travel. A world-static hold
reads a slope near -4 mm/frame; the demonstrations read -0.1.

    python3 logs/p145/loop_track.py logs/p155_ff0_77.log logs/p155_ff2_77.log
"""
from __future__ import annotations

import re
import sys

import numpy as np

CLOSE = re.compile(r"\[close\] t=(\d+)")
ROW = re.compile(
    r"\[policy-trace\] t=(\d+) .*jaw_y=([+-][\d.]+) fruit_y=([+-][\d.]+) "
    r".*jaw_z=([\d.]+)"
)


def episodes(path: str) -> list[tuple[str, float]]:
    out = []
    close_t = None
    rows: list[tuple[int, float, float]] = []
    cur = None
    for line in open(path, errors="replace"):
        m = CLOSE.search(line)
        if m:
            if cur is not None:
                out.append((cur, _stats(cur, rows)))
            cur = "close@%s" % m.group(1)
            close_t = int(m.group(1))
            rows = []
            continue
        if cur is None:
            continue
        r = ROW.search(line)
        if r and close_t is not None and int(r.group(1)) >= close_t:
            rows.append((int(r.group(1)), float(r.group(2)), float(r.group(3))))
            if len(rows) >= 17:
                out.append((cur, _stats(cur, rows)))
                cur = None
    # an episode whose rows never complete is dropped (the fruit left first)
    return out


def _stats(_name, rows):
    t = np.array([r[0] for r in rows], dtype=float)
    dy = np.array([r[1] - r[2] for r in rows], dtype=float) * 1000.0
    if len(t) < 5 or np.ptp(t) == 0:
        return None
    slope = float(np.polyfit(t / 4.0, dy, 1)[0])  # mm per 30 Hz frame
    jaw = float(rows[-1][1] - rows[0][1]) * 1000.0
    fruit = float(rows[-1][2] - rows[0][2]) * 1000.0
    return slope, jaw, fruit


def main(paths: list[str]) -> int:
    for path in paths:
        got = [(n, s) for n, s in episodes(path) if s is not None]
        if not got:
            print(f"{path}: no complete post-close windows")
            continue
        sl = np.array([s[0] for _, s in got])
        jaw = np.array([s[1] for _, s in got])
        fruit = np.array([s[2] for _, s in got])
        ok = (np.abs(fruit) > 1.0)
        ratio = jaw[ok] / fruit[ok] if ok.any() else np.array([])
        print(
            f"{path.split('/')[-1]}: n={len(got)}  slope p50 {np.median(sl):+.2f} mm/frame  "
            f"jaw p50 {np.median(jaw):+.1f} mm  fruit p50 {np.median(fruit):+.1f} mm  "
            f"ratio p50 {np.median(ratio) if ratio.size else float('nan'):.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
