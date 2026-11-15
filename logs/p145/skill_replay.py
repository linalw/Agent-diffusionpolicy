#!/usr/bin/env python3
"""P145d.12: the oracle's decisive replay - skill 1 (grasp) vs 2 (lift) at the
post-close state, and whether the goal's velocity is used at all.

At each episode's close+6 frame (the demos' committed-ramp settle) the policy is
asked for a chunk under each hard skill, and the *joint displacement* over the 16
waypoints is compared with the demonstrated chunk's. A world-static hold reads
~0 displacement; the demos' tracking hold + pop + ramp reads the demo's own
displacement. The velocity guard re-runs with the goal's velocity channels
zeroed: if the chunk does not change, the policy is not using belt velocity.

    FRUIT_OBS_CMD=1 python3 logs/p145/skill_replay.py [ckpt]
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import torch  # noqa: E402
from fruit_sorting.policy.data import EpisodeStore  # noqa: E402
from fruit_sorting.policy.runtime import PolicyRunner  # noqa: E402


def main() -> int:
    ckpt = sys.argv[1] if len(sys.argv) > 1 else "checkpoints/p145_wait_h16c/policy_best.pt"
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
    # windows at the close+6 of each episode
    per_ep: dict[int, list[tuple[int, int]]] = {}
    for i, (ep, t) in enumerate(store.windows):
        per_ep.setdefault(ep, []).append((t, i))
    picks = []
    for ep, rows in per_ep.items():
        rows.sort()
        picks.append(rows[min(len(rows) - 1, 6)][1])
    picks = picks[:16]

    def run(i, skill, zero_vel=False):
        obs = store[int(i)]
        goal = np.array(obs["goal"], dtype=np.float32).reshape(-1).copy()
        if zero_vel:
            goal[3:6] = 0.0
        policy.reset()
        policy.generator = torch.Generator(device=policy.device).manual_seed(5)
        policy._frames = [
            np.transpose(obs["image"][k], (1, 2, 0)) for k in range(obs["image"].shape[0])
        ]
        return np.asarray(
            policy.act(obs["proprio"], goal, num_steps=16, phase=int(skill)), dtype=np.float64
        )

    rows = []
    for i in picks:
        obs = store[int(i)]
        demo = np.asarray(obs["action"], dtype=np.float64)[:, :7]
        c1 = run(i, 1)
        c2 = run(i, 2)
        c0 = run(i, 1, zero_vel=True)
        rows.append(
            (
                float(np.linalg.norm(c1[-1, :7] - c1[0, :7])),
                float(np.linalg.norm(c2[-1, :7] - c2[0, :7])),
                float(np.linalg.norm(demo[-1] - demo[0])),
                float(np.linalg.norm(c2 - c1)),
                float(np.linalg.norm(c0 - c1)),
            )
        )
    a = np.asarray(rows)
    print(f"[replay] states={len(a)}  (norm over the 16-waypoint chunk, rad)")
    print(f"[replay] skill=grasp  displacement p50 {np.median(a[:,0]):.3f}  p90 {np.percentile(a[:,0],90):.3f}")
    print(f"[replay] skill=lift   displacement p50 {np.median(a[:,1]):.3f}  p90 {np.percentile(a[:,1],90):.3f}")
    print(f"[replay] demo chunk   displacement p50 {np.median(a[:,2]):.3f}  p90 {np.percentile(a[:,2],90):.3f}")
    print(f"[replay] |lift-grasp| p50 {np.median(a[:,3]):.3f}   (0 => the skill does not change the action)")
    print(f"[replay] goal-vel guard |zero-truth| p50 {np.median(a[:,4]):.3f}  "
          f"p10 {np.percentile(a[:,4],10):.3f}  (0 => belt velocity is unused)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
