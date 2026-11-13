#!/usr/bin/env python3
"""P145: does the fine-tuned model close on the DAgger close windows?

Offline (no simulator). For every window whose label (the scripted pick
controller's command) is already closing, sample the policy and compare its
**first action's finger** to the label's. If the model outputs ~open where the
label closes, the closed-loop failure is a fitting problem, not a closed-loop
one.

    FRUIT_DAGGER_FOCUS=1 python3 logs/p145/close_fidelity.py \
        checkpoints/p145_dagger_a/policy_best.pt datasets/p145_dagger_all
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import torch  # noqa: E402
from fruit_sorting.policy.data import EpisodeStore  # noqa: E402
from fruit_sorting.policy.runtime import PolicyRunner  # noqa: E402

CLOSE = 0.030


def main() -> int:
    ckpt = sys.argv[1] if len(sys.argv) > 1 else "checkpoints/p145_dagger_a/policy_best.pt"
    data = sys.argv[2] if len(sys.argv) > 2 else "datasets/p145_dagger_all"
    limit = int(os.environ.get("P145_WINDOWS", "120"))
    ddim = int(os.environ.get("P145_DDIM", "16"))
    store = EpisodeStore(
        data, obs_horizon=2, action_horizon=16, image_size=128, only_successful=False
    )
    policy = PolicyRunner(ckpt, device="cuda" if torch.cuda.is_available() else "cpu")
    rng = np.random.RandomState(7)
    # Close windows first: the label's first action is already ramping.
    closes, opens = [], []
    for i in range(len(store)):
        obs = store[int(i)]
        # A window is a "close window" when the label's 16-step chunk contains the
        # ramp, not when its first step is already below the open value (the ramp's
        # first frame is exactly 0.044).
        finger = float(np.min(obs["action"][:, 7]))
        (closes if finger < 0.035 else opens).append(i)
    if not closes:
        print("[close] no closing windows in this store")
        return 1
    pick = closes if len(closes) <= limit else list(rng.choice(closes, limit, replace=False))
    print(f"[close] windows={len(store)} closing={len(closes)} sampled={len(pick)}")

    rows = []
    for i in pick:
        obs = store[int(i)]
        policy.reset()
        policy.generator = torch.Generator(device=policy.device).manual_seed(int(i) + 11)
        policy._frames = [
            np.transpose(obs["image"][k], (1, 2, 0)) for k in range(obs["image"].shape[0])
        ]
        pred = policy.act(obs["proprio"], obs["goal"], num_steps=ddim)
        chunk = np.asarray(obs["action"])
        label = chunk[0]
        rows.append(
            (
                float(label[7]),
                float(pred[0, 7]),
                float(np.min(chunk[:, 7])),
                float(np.min(pred[:, 7])),
                float(np.linalg.norm(pred[0, :7] - chunk[0, :7])),
                float(np.linalg.norm(pred[-1, :7] - chunk[-1, :7])),
            )
        )

    lab = np.array([r[0] for r in rows])
    prd = np.array([r[1] for r in rows])
    print(
        f"[close] label finger median {np.median(lab):.4f}  "
        f"predicted median {np.median(prd):.4f}"
    )
    print(
        f"[close] label closed {int((lab < CLOSE).sum())}/{len(lab)}  "
        f"pred closed {int((prd < CLOSE).sum())}/{len(prd)}  "
        f"both {int(((lab < CLOSE) & (prd < CLOSE)).sum())}"
    )
    lmin = np.array([r[2] for r in rows])
    pmin = np.array([r[3] for r in rows])
    print(
        f"[close] chunk min: label median {np.median(lmin):.4f}  "
        f"predicted median {np.median(pmin):.4f}  "
        f"pred chunk closes (<0.035) {int((pmin < 0.035).sum())}/{len(pmin)}"
    )
    print(
        f"[close] |pred-label| first step median {np.median(np.abs(prd - lab)):.4f}  "
        f"p90 {np.percentile(np.abs(prd - lab), 90):.4f}"
    )
    joint_err = [r[4] for r in rows]
    joint_last = [r[5] for r in rows]
    print(
        f"[close] joint err first step median {np.median(joint_err):.4f} rad  "
        f"last step median {np.median(joint_last):.4f} rad"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
