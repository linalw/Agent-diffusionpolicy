#!/usr/bin/env python3
"""P173c: does the model emit the **release** where the label does?

Offline. A release window is one where the label's finger was closed at some point
and is open (>= 0.040) now. For those windows report the label's finger, the
model's predicted first-step finger, and the same for carry windows (label closed)
as the control - so "pinned at the action mean" and "learned to release" separate.

    FRUIT_OBS_CMD=1 FRUIT_TRAIN_GOAL=moving FRUIT_IMAGE_FOVEA=64 python3 logs/p145/release_fit.py \
        checkpoints/p174_fasthead/policy_best.pt datasets/p169_demo_all
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
    ckpt, data = sys.argv[1], sys.argv[2]
    limit = int(os.environ.get("P173C_WINDOWS", "30"))
    ddim = int(os.environ.get("P173C_DDIM", "16"))
    _ck = torch.load(ckpt, map_location="cpu", weights_only=False)["config"]
    store = EpisodeStore(data, obs_horizon=int(_ck.get("obs_horizon", 2)),
                         action_horizon=int(_ck.get("action_horizon", 4)),
                         image_size=int(_ck.get("image_size", 128)), only_successful=False)
    policy = PolicyRunner(ckpt, device="cuda" if torch.cuda.is_available() else "cpu")
    rel, car = [], []
    for ep, start in store.windows:
        a = np.asarray(store.episodes[ep]["action"], dtype=np.float32)
        if a.shape[1] < 8 or start >= len(a):
            continue
        f = a[:, 7]
        closed_before = bool(np.any(f[:start] < 0.030))
        if closed_before and float(f[start]) >= 0.040:
            rel.append((ep, start))
        elif float(f[start]) < 0.030:
            car.append((ep, start))
        if len(rel) >= limit and len(car) >= limit:
            break
    print(f"{ckpt}\n  release windows {len(rel)}, carry windows {len(car)}")
    for name, pool in (("release", rel), ("carry", car)):
        if not pool:
            print(f"  [{name}] none")
            continue
        step = max(1, len(pool) // limit)
        lab, prd = [], []
        for ep, start in pool[::step][:limit]:
            i = next(j for j, w in enumerate(store.windows) if w == (ep, start))
            obs = store[int(i)]
            policy.reset()
            policy.generator = torch.Generator(device=policy.device).manual_seed(int(i) + 11)
            policy._frames = [np.transpose(obs["image"][k], (1, 2, 0))
                              for k in range(obs["image"].shape[0])]
            pred = np.asarray(policy.act(obs["proprio"], obs["goal"], num_steps=ddim))
            lab.append(float(np.asarray(obs["action"])[0, 7]))
            prd.append(float(pred[0, 7]))
        lab_a, prd_a = np.array(lab), np.array(prd)
        open_lab = float(np.mean(lab_a >= 0.040))
        open_prd = float(np.mean(prd_a >= 0.040))
        print(f"  [{name}] label finger p50 {np.median(lab_a):.4f} (open {open_lab:.0%})   "
              f"pred p50 {np.median(prd_a):.4f} (open {open_prd:.0%})   "
              f"|err| p50 {np.median(np.abs(prd_a - lab_a)):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
