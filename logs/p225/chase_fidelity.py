#!/usr/bin/env python3
"""P225s: offline DAgger-label fidelity on the approach/chase states.

Reads the raw per-episode `.npz` of a **labels-only** DAgger store
(`FRUIT_DAGGER_NO_TAKEOVER=1`): `action` is the expert label, `policy_action`
the action the policy actually applied. For every frame with
`dagger_valid > 0.5` it reports the joint-space error
`||policy[:7] - expert[:7]||` [rad] and the finger difference, split by

  * **approach** (the expert's finger is open, `action[7] > 0.040`);
  * **close** (the expert's finger is closed, `action[7] < 0.030`);
  * **chase** (an approach frame whose goal is at/past the station,
    `goal[1] <= 0`).

The number that decides whether a training round can help is the share of
frames whose error is **far above the fit floor** (0.065 rad, `close_fidelity`
on the demonstrations): if the expert is only a few hundredths away, the model
already represents it and more data cannot buy the approach.

    python3 logs/p225/chase_fidelity.py datasets/p225_chase_diag
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

FLOOR = 0.065


def stats(values: np.ndarray) -> str:
    if not values.size:
        return "n=0"
    return (
        f"n={values.size:5d} median={np.median(values):.3f} "
        f"p90={np.percentile(values, 90):.3f} max={values.max():.3f} "
        f">floor={100.0 * np.mean(values > FLOOR):4.1f}%"
    )


def main(argv) -> int:
    root = argv[1] if len(argv) > 1 else "datasets/p225_chase_diag"
    files = sorted(glob.glob(os.path.join(root, "**", "*.npz"), recursive=True))
    if not files:
        print(f"[chase] no npz under {root}")
        return 1
    rows = []
    for path in files:
        data = np.load(path)
        if "policy_action" not in data.files:
            continue
        act = np.asarray(data["action"], dtype=np.float64)
        pol = np.asarray(data["policy_action"], dtype=np.float64)
        valid = (
            np.asarray(data["dagger_valid"], dtype=np.float64).reshape(-1) > 0.5
            if "dagger_valid" in data.files
            else np.ones(len(act), dtype=bool)
        )
        goal = np.asarray(data["goal"], dtype=np.float64)
        e = np.linalg.norm(pol[:, :7] - act[:, :7], axis=1)
        df = pol[:, 7] - act[:, 7]
        for i in range(len(e)):
            if not valid[i]:
                continue
            rows.append(
                (
                    e[i],
                    df[i],
                    act[i, 7],
                    float(goal[i, 1]),
                    os.path.basename(path),
                )
            )
    if not rows:
        print("[chase] no valid frames")
        return 1
    e = np.array([r[0] for r in rows])
    df = np.array([r[1] for r in rows])
    fing = np.array([r[2] for r in rows])
    gy = np.array([r[3] for r in rows])
    approach = fing > 0.040
    close = fing < 0.030
    chase = approach & (gy <= 0.0)
    print(f"[chase] files={len(files)} frames={len(rows)} floor={FLOOR} rad")
    print("  all      ", stats(e))
    print("  approach ", stats(e[approach]))
    print("  chase    ", stats(e[chase]))
    print("  close    ", stats(e[close]))
    print(
        f"  finger   all: median={np.median(df):+.4f} mean={np.mean(df):+.4f} "
        f"|d|>0.010 {100.0 * np.mean(np.abs(df) > 0.010):4.1f}%"
    )
    print(
        f"  chase    finger: median={np.median(df[chase]):+.4f} "
        f"|d|>0.010 {100.0 * np.mean(np.abs(df[chase]) > 0.010):4.1f}%"
        if chase.any() else "  chase    finger: n=0"
    )
    # per-file (episode) medians, so one hard episode cannot carry the read
    files_e = {}
    for r in rows:
        files_e.setdefault(r[4], []).append(r[0])
    med = np.array([np.median(v) for v in files_e.values()])
    print(
        f"  per-file median of medians={np.median(med):.3f} "
        f"min={med.min():.3f} max={med.max():.3f} files={len(med)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
