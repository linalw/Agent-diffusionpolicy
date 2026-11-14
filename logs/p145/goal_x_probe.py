#!/usr/bin/env python3
"""P145d.7: is the goal's **x** (the fruit's lateral offset) actually used?

At a fixed policy state (an aligned DAgger window near the descent) the goal's
x is nudged by +-50 mm and the action chunk is compared. A policy that tracks
the fruit laterally must change its arm action; a policy that holds the station
x returns the same chunk. Also nudges the goal's y by the same amount as the
control: y is known to matter (the wait/close timing), so it calibrates what a
"meaningful" delta looks like.

    FRUIT_OBS_CMD=1 python3 logs/p145/goal_x_probe.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import torch  # noqa: E402
from fruit_sorting.policy.data import EpisodeStore  # noqa: E402
from fruit_sorting.policy.runtime import PolicyRunner  # noqa: E402


def main() -> int:
    ckpt = "checkpoints/p145_wait_h16c/policy_best.pt"
    data = "datasets/p145_dagger_wait/direct_none_seed77"
    cfg = torch.load(ckpt, map_location="cpu", weights_only=False)["config"]
    store = EpisodeStore(
        data,
        obs_horizon=int(cfg.get("obs_horizon", 2)),
        action_horizon=int(cfg.get("action_horizon", 16)),
        image_size=int(cfg.get("image_size", 128)),
        only_successful=False,
    )
    policy = PolicyRunner(ckpt, device="cuda" if torch.cuda.is_available() else "cpu")
    # windows whose goal is inside the descent band (fruit within 12 cm upstream)
    picks = []
    for i, (ep, start) in enumerate(store.windows):
        obs = store[int(i)]
        g = np.asarray(obs["goal"])
        if abs(float(np.asarray(g).reshape(-1)[1])) < 0.12:
            picks.append(i)
        if len(picks) >= 24:
            break
    if not picks:
        print("[goalx] no windows in the band")
        return 1

    def run(i, dx=0.0, dy=0.0):
        obs = store[int(i)]
        goal = np.array(obs["goal"], dtype=np.float32, copy=True)
        goal = goal.reshape(-1)
        goal[0] += dx
        goal[1] += dy
        policy.reset()
        policy.generator = torch.Generator(device=policy.device).manual_seed(11)
        policy._frames = [
            np.transpose(obs["image"][k], (1, 2, 0)) for k in range(obs["image"].shape[0])
        ]
        pred = policy.act(obs["proprio"], goal, num_steps=16)
        return np.asarray(pred, dtype=np.float64)

    rows = []
    for i in picks:
        base = run(i)
        px = run(i, dx=0.05)
        nx = run(i, dx=-0.05)
        py = run(i, dy=0.05)
        rows.append(
            (
                float(np.abs(px - base)[:, :7].max()),
                float(np.abs(nx - base)[:, :7].max()),
                float(np.abs(py - base)[:, :7].max()),
                float(np.abs(base[:, :7]).max()),
            )
        )
    a = np.asarray(rows)
    print(f"[goalx] windows={len(rows)}  (max |delta joint| over the chunk, rad)")
    print(f"[goalx] goal x +50mm: p50 {np.median(a[:,0]):.5f}  max {a[:,0].max():.5f}")
    print(f"[goalx] goal x -50mm: p50 {np.median(a[:,1]):.5f}  max {a[:,1].max():.5f}")
    print(f"[goalx] goal y +50mm: p50 {np.median(a[:,2]):.5f}  max {a[:,2].max():.5f}")
    print(f"[goalx] action magnitude p50 {np.median(a[:,3]):.3f}")
    print(
        "[goalx] verdict: goal-x used"
        if np.median(a[:, 0]) > 0.02 or np.median(a[:, 1]) > 0.02
        else "[goalx] verdict: goal-x NOT used (below 0.02 rad)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
