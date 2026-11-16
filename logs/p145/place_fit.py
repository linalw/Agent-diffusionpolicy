#!/usr/bin/env python3
"""P173b: does the model predict the **place transit** at all?

Offline, no simulator. At windows where the label is carrying (finger closed) and
the arm is transiting (the label's first 7 channels move > 3 mm TCP-equivalent in
one step), compare the model's chunk with the label: per-step TCP-equivalent error,
and the predicted vs labelled *displacement* over the chunk. A model that predicts
"hold" has a correct absolute pose and a near-zero displacement error - that is the
signature the loop's oscillation cannot show.

    FRUIT_OBS_CMD=1 FRUIT_TRAIN_GOAL=moving FRUIT_IMAGE_FOVEA=64 python3 logs/p145/place_fit.py \
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

REACH = 0.50


def mm(v) -> float:
    return float(np.sqrt(np.sum((np.asarray(v, dtype=np.float64)[:7] * REACH) ** 2)) * 1e3)


def main() -> int:
    ckpt, data = sys.argv[1], sys.argv[2]
    limit = int(os.environ.get("P173B_WINDOWS", "20"))
    ddim = int(os.environ.get("P173B_DDIM", "16"))
    _ck = torch.load(ckpt, map_location="cpu", weights_only=False)["config"]
    store = EpisodeStore(data, obs_horizon=int(_ck.get("obs_horizon", 2)),
                         action_horizon=int(_ck.get("action_horizon", 4)),
                         image_size=int(_ck.get("image_size", 128)), only_successful=False)
    policy = PolicyRunner(ckpt, device="cuda" if torch.cuda.is_available() else "cpu")
    # carrying + transiting windows: finger closed in the label, 3 mm of motion
    picks = []
    for ep, start in store.windows:
        a = np.asarray(store.episodes[ep]["action"], dtype=np.float32)
        if start + 4 >= len(a) or a.shape[1] < 8 or not (a[start, 7] < 0.032):
            continue
        if mm(a[start + 1] - a[start]) > 3.0:
            picks.append((ep, start))
    if not picks:
        print("[place] no carrying/transit windows")
        return 1
    step = max(1, len(picks) // limit)
    picks = picks[::step][:limit]
    errs, dsp_err, dsp_lab = [], [], []
    for ep, start in picks:
        i = next(j for j, w in enumerate(store.windows) if w == (ep, start))
        obs = store[int(i)]
        policy.reset()
        policy.generator = torch.Generator(device=policy.device).manual_seed(int(i) + 11)
        policy._frames = [np.transpose(obs["image"][k], (1, 2, 0))
                          for k in range(obs["image"].shape[0])]
        pred = np.asarray(policy.act(obs["proprio"], obs["goal"], num_steps=ddim), dtype=np.float64)
        lab = np.asarray(obs["action"], dtype=np.float64)
        h = min(len(pred), len(lab))
        errs.append(mm(pred[0] - lab[0]))
        dsp_err.append(mm(pred[h - 1] - pred[0]))
        dsp_lab.append(mm(lab[h - 1] - lab[0]))
    e, de, dl = np.array(errs), np.array(dsp_err), np.array(dsp_lab)
    print(f"{ckpt}  windows={len(store)} carry-transit={len(picks)}")
    print(f"  first-step err   p50 {np.median(e):5.1f}mm  p90 {np.percentile(e, 90):5.1f}mm")
    print(f"  predicted travel p50 {np.median(de):5.1f}mm   labelled travel p50 {np.median(dl):5.1f}mm"
          f"   ratio {np.median(de) / max(np.median(dl), 1e-9):.2f}")
    frac = float(np.mean(de < 0.25 * dl))
    print(f"  windows whose predicted travel is < 25 % of the label's: {frac:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
