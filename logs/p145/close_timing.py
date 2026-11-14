#!/usr/bin/env python3
"""P145d.6: when does the policy close, relative to the demonstrations?

The expert closes when the fruit enters the scripted tracking window
(`FRUIT_TRACK_START` 0.05 / `FRUIT_TRACK_END` -0.02 m relative to the jaw line,
which sits at the wait pose's jaw y ~ 0). The policy's own close is its applied
finger falling below the open value. This reads both from the aligned DAgger
store (which records the expert label and the policy's applied action per frame)
and reports the timing in the fruit's along-position.

    python3 logs/p145/close_timing.py datasets/p145_dagger_wait
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np

CLOSE = 0.030  # the real close (the finger reaches the grip gap), not the 0.044 open value


def main() -> int:
    roots = sys.argv[1:] or ["datasets/p145_dagger_wait"]
    files = []
    for root in roots:
        files.extend(sorted(glob.glob(os.path.join(root, "**", "*.npz"), recursive=True)))
    rows = []
    for path in files:
        d = np.load(path)
        if "policy_action" not in d.files or "fruit_position" not in d.files:
            continue
        fruit = np.asarray(d["fruit_position"], dtype=np.float32)
        label = np.asarray(d["action"], dtype=np.float32)
        policy = np.asarray(d["policy_action"], dtype=np.float32)
        if label.ndim != 2 or label.shape[1] < 8:
            continue
        e = np.flatnonzero(label[:, 7] < CLOSE)
        p = np.flatnonzero(policy[:, 7] < CLOSE)
        # P145d.6: the *first* sub-0.044 crossing is the open value's noise dip
        # (0.1 mm below 0.044) and is not a close; the real close is the finger
        # reaching the grip-gap region, so the threshold is 0.030.
        if not e.size:
            continue
        ey = float(fruit[int(e[0]), 1])
        if p.size:
            py = float(fruit[int(p[0]), 1])
        else:
            py = float("nan")
        rows.append((ey, py, float(fruit[:, 1].min()), len(fruit)))
    if not rows:
        print("[timing] no episodes with both streams")
        return 1
    a = np.asarray(rows)
    ey = a[:, 0]
    py = a[:, 1]
    ok = np.isfinite(py)
    print(f"[timing] episodes={len(rows)}  policy-closed={int(ok.sum())}")
    print(f"[timing] expert close at fruit y: p50 {np.median(ey):+.3f}  "
          f"p10 {np.percentile(ey,10):+.3f}  p90 {np.percentile(ey,90):+.3f}")
    if ok.any():
        d = py[ok] - ey[ok]
        print(f"[timing] policy close at fruit y: p50 {np.median(py[ok]):+.3f}  "
              f"p10 {np.percentile(py[ok],10):+.3f}  p90 {np.percentile(py[ok],90):+.3f}")
        print(f"[timing] policy minus expert (m): p50 {np.median(d):+.3f}  "
              f"p10 {np.percentile(d,10):+.3f}  p90 {np.percentile(d,90):+.3f}  "
              f"(negative = closes later/downstream)")
        late = py[ok] < 0.0
        print(f"[timing] policy closes after the fruit passed (y<0): "
              f"{int(late.sum())}/{int(ok.sum())}")
        print(f"[timing] policy closes within the expert window [-0.02,0.05]: "
              f"{int(((py[ok]>=-0.02)&(py[ok]<=0.05)).sum())}/{int(ok.sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
