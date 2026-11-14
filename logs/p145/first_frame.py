#!/usr/bin/env python3
"""P145d.1: does the 4-D head fit the **wait state** at all?

The first observation of every demonstration is the wait pose with the fruit far
upstream; the demonstrated TCP there is a constant (~1.241 m in z). A fresh
action head that has not learned the new space outputs near the action mean
(1.364) - 12 cm high - and the closed loop cannot recover. This measures that
first-frame action error offline, before any closed-loop claim.

    FRUIT_ACTION=tcp python3 logs/p145/first_frame.py <ckpt> <store>
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
    ckpt = sys.argv[1] if len(sys.argv) > 1 else "checkpoints/p145_cart3/policy_best.pt"
    data = sys.argv[2] if len(sys.argv) > 2 else "datasets/p145_tcp2"
    cfg = torch.load(ckpt, map_location="cpu", weights_only=False)["config"]
    store = EpisodeStore(
        data,
        obs_horizon=int(cfg.get("obs_horizon", 2)),
        action_horizon=int(cfg.get("action_horizon", 4)),
        image_size=int(cfg.get("image_size", 128)),
        only_successful=False,
    )
    policy = PolicyRunner(ckpt, device="cuda" if torch.cuda.is_available() else "cpu")
    # the first window of each episode
    firsts = []
    seen = set()
    for i, (ep, start) in enumerate(store.windows):
        if ep not in seen:
            seen.add(ep)
            firsts.append(i)
    rows = []
    for i in firsts:
        obs = store[int(i)]
        policy.reset()
        policy.generator = torch.Generator(device=policy.device).manual_seed(int(i) + 3)
        policy._frames = [
            np.transpose(obs["image"][k], (1, 2, 0)) for k in range(obs["image"].shape[0])
        ]
        pred = policy.act(obs["proprio"], obs["goal"], num_steps=16)
        rec = np.asarray(obs["action"])[0]
        rows.append((float(rec[0]), float(pred[0, 0]), float(rec[1]), float(pred[0, 1]),
                     float(rec[2]), float(pred[0, 2]), float(rec[3]), float(pred[0, 3])))
    a = np.asarray(rows)
    rec_xyz = a[:, [0, 2, 4]]
    pred_xyz = a[:, [1, 3, 5]]
    err = np.linalg.norm(pred_xyz - rec_xyz, axis=1)
    print(f"[first] episodes={len(rows)}")
    print(f"[first] recorded xyz mean {np.round(rec_xyz.mean(0), 3).tolist()}")
    print(f"[first] predicted xyz mean {np.round(pred_xyz.mean(0), 3).tolist()}")
    for k, name in enumerate(("x", "y", "z")):
        d = pred_xyz[:, k] - rec_xyz[:, k]
        print(f"[first] {name}: median {np.median(d)*1000:+.1f} mm  "
              f"p90 {np.percentile(np.abs(d), 90)*1000:.1f}")
    print(f"[first] |xyz| median {np.median(err)*1000:.1f} mm  "
          f"p90 {np.percentile(err, 90)*1000:.1f}  "
          f"<= 20 mm {int((err <= 0.020).sum())}/{len(err)}")
    print(f"[first] finger: rec {np.median(a[:,6]):.4f} pred {np.median(a[:,7]):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
