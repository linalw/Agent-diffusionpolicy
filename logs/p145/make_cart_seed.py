#!/usr/bin/env python3
"""P145d: a 4-D cartesian seed from `moe_v13s`.

The diffusion weights that fit are the visual encoder and the temporal backbone;
only the action input/output layers are action-dimension-specific. This builds a
4-D model, copies every parameter whose shape still matches, and replaces the
normalizer's action statistics with the ones measured on `datasets/p145_tcp`
(`[jaw xyz, finger]`, the next 30 Hz sample). `111_rl_finetune.py` then trains it
like any other checkpoint.

    python3 logs/p145/make_cart_seed.py
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import torch  # noqa: E402
from fruit_sorting.policy.model import ConditionalUNet1D  # noqa: E402

SOURCE = "checkpoints/moe_v13s/policy_best.pt"
STORE = "datasets/p145_tcp"
OUT = "checkpoints/p145_cart_seed"


def main() -> int:
    ckpt = torch.load(SOURCE, map_location="cpu", weights_only=False)
    config = dict(ckpt["config"])
    config["action_dim"] = 4
    acts = []
    for path in sorted(glob.glob(os.path.join(STORE, "**", "*.npz"), recursive=True)):
        data = np.load(path)
        jaw = np.asarray(data["jaw"], dtype=np.float32)
        finger = np.asarray(data["finger_opening"], dtype=np.float32).reshape(-1, 1)
        cart = np.concatenate([jaw, finger], axis=1)
        acts.append(np.concatenate([cart[1:], cart[-1:]], axis=0))
    A = np.concatenate(acts, axis=0)
    mean = A.mean(axis=0)
    std = A.std(axis=0) + 1e-6
    print(f"[seed] {len(acts)} episodes, {len(A)} frames")
    print("[seed] action mean", np.round(mean, 4).tolist())
    print("[seed] action std ", np.round(std, 4).tolist())

    model = ConditionalUNet1D(
        action_dim=4,
        image_channels=int(config["image_channels"]),
        obs_horizon=int(config["obs_horizon"]),
        goal_dim=int(config["goal_dim"]),
        proprio_dim=int(config["proprio_dim"]),
        num_skills=int(config.get("num_skills", 5)),
    )
    state = model.state_dict()
    copied = 0
    fresh = []
    for key, value in ckpt["model"].items():
        if key in state and state[key].shape == value.shape:
            state[key] = value
            copied += 1
        else:
            fresh.append(key)
    model.load_state_dict(state)
    print(f"[seed] copied {copied}/{len(state)} tensors; fresh: {fresh}")

    normalizer = dict(ckpt["normalizer"])
    normalizer["action_mean"] = mean.tolist()
    normalizer["action_std"] = std.tolist()
    os.makedirs(OUT, exist_ok=True)
    torch.save(
        {"model": model.state_dict(), "config": config, "normalizer": normalizer},
        os.path.join(OUT, "policy_best.pt"),
    )
    print(f"[seed] saved {OUT}/policy_best.pt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
