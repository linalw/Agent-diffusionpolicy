#!/usr/bin/env python3
"""P172: is the contact-phase error **variance** or **bias**?

A chunked policy re-samples a chunk every decision. If the sampler's spread at a
fixed state is the same order as the belt's per-decision travel (0.12 m/s x 16
ticks = 32 mm), averaging K samples is a lever (variance/sqrt(K)); if the spread is
small and the mean is off, the error is bias and ensembling is not.

Offline, no simulator: for the close-start windows, sample K chunks from the same
conditioning and report the per-joint std as a TCP-equivalent, and the mean's error
against the label (bias and variance separated).

    python3 logs/p145/sampler_var.py checkpoints/p174_fasthead/policy_best.pt datasets/p169_demo_all
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import torch  # noqa: E402
from fruit_sorting.policy.data import EpisodeStore  # noqa: E402
from fruit_sorting.policy.runtime import PolicyRunner  # noqa: E402

REACH = 0.50  # the wrist's rough lever arm from the shoulder (small-angle)


def tcp_mm(v7: np.ndarray) -> float:
    """A joint-space error as an end-effector distance (rms over the 7 joints)."""
    v = np.asarray(v7, dtype=np.float64)
    return float(np.sqrt(np.sum((v * REACH) ** 2)) * 1e3)


def main() -> int:
    ckpt = sys.argv[1]
    data = sys.argv[2]
    k = int(os.environ.get("P172_K", "8"))
    limit = int(os.environ.get("P172_WINDOWS", "12"))
    ddim = int(os.environ.get("P172_DDIM", "16"))
    _ck = torch.load(ckpt, map_location="cpu", weights_only=False)["config"]
    store = EpisodeStore(
        data,
        obs_horizon=int(_ck.get("obs_horizon", 2)),
        action_horizon=int(_ck.get("action_horizon", 4)),
        image_size=int(_ck.get("image_size", 128)),
        only_successful=False,
    )
    policy = PolicyRunner(ckpt, device="cuda" if torch.cuda.is_available() else "cpu")
    closes = []
    for ep, start in store.windows:
        finger = np.asarray(store.episodes[ep]["action"], dtype=np.float32)[:, 7]
        index = np.flatnonzero(finger < 0.0439)
        if index.size:
            c = int(index[0])
            if c - 5 <= start <= c + 10:
                closes.append((ep, start))
    if not closes:
        print("[var] no close-start windows in this store")
        return 1
    pick = closes if len(closes) <= limit else closes[:: max(1, len(closes) // limit)][:limit]
    print(f"{ckpt}\n  windows={len(store)} close_start={len(closes)} sampled={len(pick)} K={k}")
    sp, bi = [], []
    for ep, start in pick:
        i = next(j for j, w in enumerate(store.windows) if w == (ep, start))
        obs = store[int(i)]
        policy.reset()
        policy.generator = torch.Generator(device=policy.device).manual_seed(int(i) + 11)
        policy._frames = [
            np.transpose(obs["image"][j], (1, 2, 0)) for j in range(obs["image"].shape[0])
        ]
        runs = []
        for _ in range(k):
            runs.append(np.asarray(policy.act(obs["proprio"], obs["goal"],
                                              num_steps=ddim)[0], dtype=np.float64))
        s = np.stack(runs)
        sd7 = s[:, :7].std(axis=0)
        label = np.asarray(obs["action"][0], dtype=np.float64)[:7]
        bias7 = s[:, :7].mean(axis=0) - label
        sp.append(sd7)
        bi.append(bias7)
        print(f"  win {i:5d}  sd~{tcp_mm(sd7):5.1f}mm  |bias|~{tcp_mm(bias7):5.1f}mm")
    sd, b = np.stack(sp), np.stack(bi)
    print(f"\n  sampler sd   TCP-equiv p50 {np.median([tcp_mm(x) for x in sd]):5.1f} mm"
          f"  p90 {np.percentile([tcp_mm(x) for x in sd], 90):5.1f}")
    print(f"  mean vs label TCP-equiv p50 {np.median([tcp_mm(x) for x in b]):5.1f} mm")
    print(f"  (belt travel per 16-tick decision at 0.12 m/s: 32.0 mm)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
