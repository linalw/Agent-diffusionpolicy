#!/usr/bin/env python3
"""P145d.7: at the **descent** state, does the policy reproduce the demo's lateral
reach, or does it fall back to the station pose?

For every window in the DAgger store whose goal is in the descent band
(|goal_y| < 0.10) this compares the policy's 16-step chunk to the demonstrated
chunk and to the **hold baseline** (the episode's station/grasp joint vector,
taken as the first action of the episode):

  amp = ||chunk_end - station|| / ||demo_end - station||

amp ~ 1 -> the policy performs the demonstrated reach; amp ~ 0 -> it holds.

    FRUIT_OBS_CMD=1 python3 logs/p145/descent_amp.py
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
    ckpt = sys.argv[1] if len(sys.argv) > 1 else "checkpoints/p145_wait_h16c/policy_best.pt"
    data = sys.argv[2] if len(sys.argv) > 2 else "datasets/p145_dagger_wait/direct_none_seed77"
    cfg = torch.load(ckpt, map_location="cpu", weights_only=False)["config"]
    store = EpisodeStore(
        data,
        obs_horizon=int(cfg.get("obs_horizon", 2)),
        action_horizon=int(cfg.get("action_horizon", 16)),
        image_size=int(cfg.get("image_size", 128)),
        only_successful=False,
    )
    policy = PolicyRunner(ckpt, device="cuda" if torch.cuda.is_available() else "cpu")
    station: dict[int, np.ndarray] = {}
    rows = []
    for i, (ep, start) in enumerate(store.windows):
        obs = store[int(i)]
        goal = np.asarray(obs["goal"], dtype=np.float32).reshape(-1)
        if abs(float(goal[1])) > 0.10:
            continue
        if ep not in station:
            first = next(j for j, w in enumerate(store.windows) if w[0] == ep)
            station[ep] = np.asarray(store[int(first)]["action"])[0, :7].astype(np.float64)
        base = station[ep]
        demo = np.asarray(obs["action"], dtype=np.float64)[:, :7]
        policy.reset()
        policy.generator = torch.Generator(device=policy.device).manual_seed(7)
        policy._frames = [
            np.transpose(obs["image"][k], (1, 2, 0)) for k in range(obs["image"].shape[0])
        ]
        pred = np.asarray(policy.act(obs["proprio"], obs["goal"], num_steps=16), dtype=np.float64)
        d_pred = float(np.linalg.norm(pred[-1, :7] - base))
        d_demo = float(np.linalg.norm(demo[-1] - base))
        dp = pred[-1, :7] - base
        dd = demo[-1] - base
        cos = float(np.dot(dp, dd) / max(np.linalg.norm(dp) * np.linalg.norm(dd), 1e-9))
        rows.append((d_pred, d_demo, d_pred / max(d_demo, 1e-6), float(goal[1]), cos,
                     float(np.linalg.norm(pred[-1, :7] - demo[-1])), float(goal[0])))
        if len(rows) >= 24:
            break
    if not rows:
        print("[amp] no windows in the band")
        return 1
    a = np.asarray(rows)
    print(f"[amp] windows={len(rows)}  (||chunk_end - station||, rad)")
    print(f"[amp] demo reach  p50 {np.median(a[:,1]):.3f}  max {a[:,1].max():.3f}")
    print(f"[amp] policy reach p50 {np.median(a[:,0]):.3f}  max {a[:,0].max():.3f}")
    print(f"[amp] amplitude ratio p50 {np.median(a[:,2]):.2f}  "
          f"p10 {np.percentile(a[:,2],10):.2f}  p90 {np.percentile(a[:,2],90):.2f}")
    print(f"[amp] direction cos p50 {np.median(a[:,4]):.3f}  "
          f"p10 {np.percentile(a[:,4],10):.3f}")
    print(f"[amp] endpoint |pred-demo| p50 {np.median(a[:,5]):.3f} rad  "
          f"p90 {np.percentile(a[:,5],90):.3f}")
    for r in a[:8]:
        print(f"  demo {r[1]:.3f}  policy {r[0]:.3f}  ratio {r[2]:.2f}  cos {r[4]:+.2f}  "
              f"|err| {r[5]:.3f}  goal_y {r[3]:+.3f}  goal_x {r[6]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
