"""P4 verification: is the recorded `action` a command or a brake?

Offline (no simulator). For every episode in each given dataset directory,
compare the recorded arm action with the measured joints it is paired with:

* `|a(t) - q(t)|` - zero for a measured-joint (brake) action, nonzero for a
  commanded target that leads the state;
* `|a(t) - q(t+1)|` and the per-tick motion `|q(t+1) - q(t)|`;
* the fraction of ticks where `a(t)` lies ahead of `q(t)` along the motion
  (`(a - q(t)) . (q(t+1) - q(t)) > 0`), computed over ticks that actually move.

The `moving` columns restrict to ticks with `|q(t+1)-q(t)| > 1e-4` rad, i.e.
where a demonstration has motion to encode; `all` is every frame.

    python3 scripts/115_action_semantics.py datasets/demos_v7 datasets/demos_v8
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

# Same dof mapping scripts/114_rl_obs_diff.py uses: the recorded
# `joint_positions` interleaves the arms, left at even and right at odd indices.
ARM_JOINTS = {
    "left": [0, 2, 4, 6, 8, 10, 12],
    "right": [1, 3, 5, 7, 9, 11, 13],
}


def stats(directory: str) -> dict[str, float]:
    with open(os.path.join(directory, "index.json"), encoding="utf-8") as fh:
        entries = json.load(fh)
    hold_all, hold_moving, step_moving, lead_moving = [], [], [], []
    ahead_all, ahead_moving, brake = [], [], []
    for entry in entries:
        path = os.path.join(directory, entry["file"])
        if not os.path.exists(path):
            continue
        with np.load(path) as data:
            arm = entry.get("arm", "left")
            idx = ARM_JOINTS.get(arm, ARM_JOINTS["left"])
            q = data["joint_positions"][:, idx]
            a = data["action"][:, :7]
            hold = np.linalg.norm(a - q, axis=1)
            step = np.linalg.norm(q[1:] - q[:-1], axis=1)
            dnext = np.linalg.norm(a[:-1] - q[1:], axis=1)
            ahead = np.einsum("ij,ij->i", a[:-1] - q[:-1], q[1:] - q[:-1]) > 0.0
            moving = step > 1e-4
            hold_all.append(hold)
            hold_moving.append(hold[:-1][moving])
            step_moving.append(step[moving])
            lead_moving.append((hold[:-1] / np.maximum(step, 1e-9))[moving])
            ahead_all.append(ahead)
            ahead_moving.append(ahead[moving])
            brake.append(hold < 2e-3)
    hold_all = np.concatenate(hold_all)
    hold_moving = np.concatenate(hold_moving)
    step_moving = np.concatenate(step_moving)
    lead_moving = np.concatenate(lead_moving)
    ahead_all = np.concatenate(ahead_all)
    ahead_moving = np.concatenate(ahead_moving)
    brake = np.concatenate(brake)
    return {
        "episodes": len(entries),
        "frames": int(len(hold_all)),
        "moving": int(len(hold_moving)),
        "hold_med": float(np.median(hold_all)),
        "hold_moving_med": float(np.median(hold_moving)),
        "step_moving_med": float(np.median(step_moving)),
        "lead_ratio_med": float(np.median(lead_moving)),
        "ahead_all": float(np.mean(ahead_all)),
        "ahead_moving": float(np.mean(ahead_moving)),
        "brake_frac": float(np.mean(brake)),
    }


def main(argv: list[str]) -> int:
    dirs = argv[1:] or ["datasets/demos_v7"]
    rows = [(d, stats(d)) for d in dirs]
    print(
        f"{'dataset':24s} {'eps':>3s} {'frames':>7s} {'moving':>7s} "
        f"{'|a-q|med':>9s} {'mov|a-q|':>9s} {'mov step':>9s} {'lead':>6s} "
        f"{'ahead all':>9s} {'ahead mov':>9s} {'brake<2mrad':>11s}"
    )
    for name, s in rows:
        print(
            f"{name:24s} {s['episodes']:3d} {s['frames']:7d} {s['moving']:7d} "
            f"{s['hold_med']:9.4f} {s['hold_moving_med']:9.4f} "
            f"{s['step_moving_med']:9.4f} {s['lead_ratio_med']:6.2f} "
            f"{s['ahead_all']:9.1%} {s['ahead_moving']:9.1%} {s['brake_frac']:11.1%}"
        )
    print()
    print("|a-q|med     median over all frames of ||action[:7] - q(t)|| [rad]")
    print("mov|a-q|     same, over ticks with motion (|q(t+1)-q(t)| > 1e-4)")
    print("mov step     median per-tick motion ||q(t+1)-q(t)|| on those ticks [rad]")
    print("lead         median ||action - q(t)|| / ||q(t+1) - q(t)|| (how far ahead)")
    print("ahead all    fraction of ticks with (action-q(t))·(q(t+1)-q(t)) > 0")
    print("ahead mov    same, moving ticks only")
    print("brake<2mrad  fraction of frames with ||action-q(t)|| < 0.002 rad")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
