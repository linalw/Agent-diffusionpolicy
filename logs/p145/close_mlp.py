#!/usr/bin/env python3
"""P145c: is the close mapping deterministic? A direct MLP vs the diffusion fit.

The diffusion policy reads 0.036-0.041 rad joint error on the close-start windows
of the demonstrations it was trained on. If a plain MLP - no sampling, one mean
output - fits the same windows much better, the residual is the diffusion
sampler and a deterministic close head is the fix; if it is the same, the
observation does not determine the expert's command to better than ~2 cm.

    python3 logs/p145/close_mlp.py [datasets/demos_v11]
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import torch  # noqa: E402

HZ = 30.0


def load(store: str):
    episodes = []
    for path in sorted(glob.glob(os.path.join(store, "**", "*.npz"), recursive=True)):
        d = np.load(path)
        if "fruit_position" not in d.files:
            continue
        pos = np.asarray(d["fruit_position"], dtype=np.float32)
        vel = np.gradient(pos.astype(np.float64), axis=0)[:, :3].astype(np.float32) * HZ
        goal = np.asarray(d["goal"], dtype=np.float32)
        dia = goal[:, 6:7]
        binv = goal[:, 7:8]
        finger = np.asarray(d["finger_opening"], dtype=np.float32).reshape(-1, 1)
        joints = np.asarray(d["joint_positions"], dtype=np.float32)
        tactile = np.asarray(d["tactile"], dtype=np.float32).reshape(-1, 2)
        action = np.asarray(d["action"], dtype=np.float32)
        features = np.concatenate([pos, vel, dia, binv, joints, finger, tactile], axis=1)
        ramp = np.asarray(action[:, 7], dtype=np.float32)
        closed = np.flatnonzero(ramp < 0.0439)
        if not closed.size:
            continue
        c = int(closed[0])
        idx = [t for t in range(max(0, c - 5), min(len(ramp), c + 11))]
        episodes.append((features[idx], action[idx, :7]))
    return episodes


def normalise(x, mean=None, std=None):
    if mean is None:
        return x, x.mean(0), x.std(0) + 1e-6
    return (x - mean) / std, mean, std


def main() -> int:
    stores = sys.argv[1].split(",") if len(sys.argv) > 1 else ["datasets/demos_v11"]
    eps = []
    for store in stores:
        got = load(store)
        print(f"[mlp] {store}: {len(got)} episodes")
        eps.extend(got)
    # Split **by episode** (a window split leaks: adjacent close frames are nearly
    # identical). Random over episodes, not the tail (the tail is one arm).
    rng = np.random.RandomState(0)
    order = rng.permutation(len(eps))
    n_val = max(1, len(eps) // 5)
    va_eps = [eps[i] for i in order[:n_val]]
    tr_eps = [eps[i] for i in order[n_val:]]
    X = np.concatenate([e[0] for e in tr_eps]); Y = np.concatenate([e[1] for e in tr_eps])
    Xv = np.concatenate([e[0] for e in va_eps]); Yv = np.concatenate([e[1] for e in va_eps])
    X, mean, std = normalise(X)
    Xv = (Xv - mean) / std
    print(f"[mlp] train {len(X)} val {len(Xv)} features {X.shape[1]}")

    net = torch.nn.Sequential(
        torch.nn.Linear(X.shape[1], 64), torch.nn.SiLU(),
        torch.nn.Linear(64, 64), torch.nn.SiLU(),
        torch.nn.Linear(64, 7),
    )
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-3)
    Xt, Yt = torch.from_numpy(X), torch.from_numpy(Y)
    Xvt, Yvt = torch.from_numpy(Xv), torch.from_numpy(Yv)
    best = (float("inf"), None)
    for epoch in range(3000):
        net.train(); opt.zero_grad()
        loss = torch.nn.functional.mse_loss(net(Xt), Yt)
        loss.backward(); opt.step()
        if (epoch + 1) % 50 == 0:
            net.eval()
            with torch.no_grad():
                v = float((net(Xvt) - Yvt).norm(dim=1).median())
            if v < best[0]:
                best = (v, {k: t.detach().clone() for k, t in net.state_dict().items()})
    if best[1] is not None:
        net.load_state_dict(best[1])
    net.eval()
    with torch.no_grad():
        pred = net(Xvt)
        err = (pred - Yvt).norm(dim=1)
        train_err = (net(Xt) - Yt).norm(dim=1)
    print(f"[mlp] train |err| median {float(train_err.median()):.4f} rad  "
          f"val |err| median {float(err.median()):.4f} rad  p90 {float(err.quantile(0.9)):.4f}")
    # the diffusion model's close-only number, same instrument, is 0.0362 rad
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
