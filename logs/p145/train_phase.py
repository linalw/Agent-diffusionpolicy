#!/usr/bin/env python3
"""P145c: a phase classifier from the **perceived fruit + finger** (vision + touch).

The policy's MoE router infers the phase from the full condition (image + goal +
proprio + time). Measured in the closed loop, its argmax flips to `lift` at
`goal_y = +0.126` while the fruit is still on the belt - the router reads the
*arm's* pose ("I am at the grasp waypoint, the finger is closed"), so the policy's
own early close feeds back into the phase and the lift expert fires with nothing
in the hand.

This trains a small classifier on the **task state** instead:

    features = [fruit xyz, fruit velocity, diameter, finger opening]
    labels   = policy.skills.label_episode(...)   (the demos' own rule)

Every feature is available at deployment from the depth-camera goal (position,
velocity, diameter) and the finger channel - no arm pose, no image. The lift and
place labels therefore cannot fire until the fruit has actually been carried
(their rule is `fruit z > rest + 6 cm` / over the bin), which breaks the feedback
loop.

    python3 logs/p145/train_phase.py [datasets/demos_v11] [checkpoints/p145_phase]
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import torch  # noqa: E402
from fruit_sorting.policy.skills import SKILLS, label_episode  # noqa: E402

HZ = 30.0


def features(pos, vel, dia, finger):
    pos = np.asarray(pos, dtype=np.float32)
    vel = np.asarray(vel, dtype=np.float32)
    return np.concatenate(
        [pos.reshape(-1, 3), vel.reshape(-1, 3),
         np.asarray(dia, dtype=np.float32).reshape(-1, 1),
         np.asarray(finger, dtype=np.float32).reshape(-1, 1)], axis=1
    )


def load(store: str):
    episodes = []
    for path in sorted(glob.glob(os.path.join(store, "**", "*.npz"), recursive=True)):
        data = np.load(path)
        if "fruit_position" not in data.files:
            continue
        pos = np.asarray(data["fruit_position"], dtype=np.float32)
        # P145d.6: label on the **commanded** finger (the action stream), the
        # same convention as the loader's P145d.3 skills - the measured finger
        # aliases the loaded close.
        _a = np.asarray(data["action"], dtype=np.float32)
        finger = (
            _a[:, 7]
            if _a.ndim == 2 and _a.shape[1] > 7
            else np.asarray(data["finger_opening"], dtype=np.float32).reshape(-1)
        )
        goal = np.asarray(data["goal"], dtype=np.float32)
        vel = np.gradient(pos.astype(np.float64), axis=0)[:, :3] * HZ
        dia = goal[:, 6].reshape(-1)
        labels = label_episode(pos, finger, goal)
        episodes.append((features(pos, vel, dia, finger), labels))
    return episodes


def main() -> int:
    store = sys.argv[1] if len(sys.argv) > 1 else "datasets/demos_v11"
    out = sys.argv[2] if len(sys.argv) > 2 else "checkpoints/p145_phase"
    episodes = load(store)
    if not episodes:
        print("[phase] no episodes")
        return 1
    n_val = max(1, len(episodes) // 5)
    train_eps, val_eps = episodes[:-n_val], episodes[-n_val:]
    X = np.concatenate([e[0] for e in train_eps], axis=0)
    y = np.concatenate([e[1] for e in train_eps], axis=0)
    Xv = np.concatenate([e[0] for e in val_eps], axis=0)
    yv = np.concatenate([e[1] for e in val_eps], axis=0)
    mean, std = X.mean(axis=0), X.std(axis=0) + 1e-6
    print(
        f"[phase] train {len(X)} frames / {len(train_eps)} eps, "
        f"val {len(Xv)} / {len(val_eps)} eps; labels "
        + ", ".join(f"{SKILLS[k]}={int((y == k).sum())}" for k in range(len(SKILLS)))
    )

    net = torch.nn.Sequential(
        torch.nn.Linear(X.shape[1], 64), torch.nn.SiLU(),
        torch.nn.Linear(64, 64), torch.nn.SiLU(),
        torch.nn.Linear(64, len(SKILLS)),
    )
    opt = torch.optim.AdamW(net.parameters(), lr=3e-3, weight_decay=1e-4)
    Xt = torch.from_numpy((X - mean) / std)
    yt = torch.from_numpy(y)
    Xv_t = torch.from_numpy((Xv - mean) / std)
    yv_t = torch.from_numpy(yv)
    for epoch in range(300):
        net.train()
        opt.zero_grad()
        logits = net(Xt)
        loss = torch.nn.functional.cross_entropy(logits, yt)
        loss.backward()
        opt.step()
        if (epoch + 1) % 50 == 0 or epoch == 0:
            net.eval()
            with torch.no_grad():
                pred = net(Xv_t).argmax(dim=-1)
                acc = float((pred == yv_t).float().mean())
            print(f"[phase] epoch {epoch + 1}: loss {float(loss):.4f} val acc {acc:.4f}")
    net.eval()
    with torch.no_grad():
        pred = net(Xv_t).argmax(dim=-1).numpy()
    confusion = np.zeros((len(SKILLS), len(SKILLS)), dtype=int)
    for t, p in zip(yv, pred):
        confusion[int(t), int(p)] += 1
    print("[phase] confusion (rows true, cols pred):")
    for k, name in enumerate(SKILLS):
        print(f"  {name:8s} " + " ".join(f"{v:6d}" for v in confusion[k]))
    os.makedirs(out, exist_ok=True)
    torch.save(
        {
            "model": net.state_dict(),
            "features": ["pos3", "vel3", "diameter", "finger"],
            "mean": mean.tolist(),
            "std": std.tolist(),
            "skills": list(SKILLS),
            "train_frames": int(len(X)),
        },
        os.path.join(out, "phase.pt"),
    )
    with open(os.path.join(out, "phase.json"), "w", encoding="utf-8") as fh:
        json.dump({"skills": list(SKILLS), "frames": int(len(X))}, fh, indent=2)
    print(f"[phase] saved {out}/phase.pt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
