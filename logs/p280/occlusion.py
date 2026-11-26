#!/usr/bin/env python3
"""P280: what actually sits between the wrist camera and the fruit?

The owner's question - "would the Piper arm occlude the wrist camera less?" - only
has an answer if we know **what is occluding it now**. The wrist rig is mounted
6 cm behind the jaw at 4.5 cm lateral, looking at the jaw; the fruit sits 7 cm
below the jaw, inside a 98 mm gap between two 61 x 84.9 mm plates. Two very
different blockers are possible:

* the **hand** (the fingers, the carriage, the palm) - a smaller gripper helps;
* the **arm** (links between the flange and the camera) - a smaller arm helps.

The dump from `FRUIT_WRIST_DUMP` is enough to separate them: per frame it holds
the wrist's own **depth** and the net's **mask**. Pixels *nearer* than the fruit
are, by definition, whatever is in front of it - and near the wrist that can only
be the robot.

Usage: python3 logs/p280/occlusion.py logs/video_p279/wrist
"""
from __future__ import annotations

import glob
import os
import statistics as st
import sys

import numpy as np


def main(argv):
    d = argv[1] if len(argv) > 1 else "logs/video_p279/wrist"
    #: the dump writes `wrist_<side>_<i>.ppm` + `.npy` (depth) and, in `learned`
    #: mode, `wrist_<side>_<i>_pred.npy` (the net's mask)
    stems = sorted(
        p[: -len("_pred.npy")] for p in glob.glob(os.path.join(d, "*_pred.npy"))
    )
    rows = []
    for stem in stems:
        pred_path = stem + "_pred.npy"
        if not (os.path.exists(pred_path) and os.path.exists(stem + ".npy")):
            continue
        depth = np.load(stem + ".npy").astype(np.float32)
        pred = np.load(pred_path).astype(bool)
        if depth.ndim != 2:
            continue
        h, w = depth.shape
        if pred.shape != depth.shape:
            ys = (np.arange(h) * pred.shape[0] // h).clip(0, pred.shape[0] - 1)
            xs = (np.arange(w) * pred.shape[1] // w).clip(0, pred.shape[1] - 1)
            pred = pred[ys][:, xs]
        finite = np.isfinite(depth) & (depth > 0.02)
        if pred.sum() < 40:
            rows.append((stem, 0, 0, 0.0, 0.0))
            continue
        zf = float(np.median(depth[pred]))
        hand = finite & (depth < zf - 0.010)
        rows.append(
            (
                stem,
                int(pred.sum()),
                int(hand.sum()),
                100.0 * pred.sum() / (h * w),
                100.0 * hand.sum() / (h * w),
            )
        )
    if not rows:
        print("no labelled dumps", file=sys.stderr)
        return 2

    # the dumps are ordered in time; a third of the way in is the approach, the
    # last third is the close
    n = len(rows)
    thirds = [(0, n // 3), (n // 3, 2 * n // 3), (2 * n // 3, n)]
    labels = ["early (approach)", "middle", "late (close)"]

    print(f"{n} frames from {d}")
    print(f"{'bucket':18s} {'frames':>6s} {'mask %':>8s} {'nearer-than-fruit %':>20s}")
    for (a, b), lab in zip(thirds, labels):
        chunk = rows[a:b]
        m = [r[3] for r in chunk]
        hm = [r[4] for r in chunk]
        print(f"{lab:18s} {len(chunk):>6d} {st.mean(m):>8.2f} {st.mean(hm):>20.2f}")

    both = [r for r in rows if r[1] > 0]
    if both:
        ratio = [r[4] / max(r[3], 1e-9) for r in both]
        print(
            f"\nframes with a fruit mask: {len(both)}/{n}  "
            f"(hand/fruit area ratio: p50 {st.median(ratio):.2f})"
        )
        big = sum(1 for r in both if r[4] > 0.5 * r[3])
        print(f"frames where the occluder is over half the fruit's area: {big}/{len(both)}")
    print(
        "\nRead: `nearer-than-fruit` is the robot in front of the fruit. If that is a\n"
        "large share of the frame, a **smaller gripper** is the lever; if it is thin\n"
        "and the mask is still small, the fruit is out of frame and the **mount** is."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
