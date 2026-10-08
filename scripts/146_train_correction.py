"""Train the A2C2-style per-step correction head (offline, no Isaac).

    python3 scripts/146_train_correction.py \
        --ckpt checkpoints/moe_v11/policy_best.pt \
        --rollouts datasets/path3_a2c2_dagger \
        --out checkpoints/moe_v11_correction --epochs 30

Reads DAgger rollouts (`--dagger --record`): each frame carries the scripted
pick-phase expert label in `action` and the base policy's proposal in
`policy_action`. The head learns `clamp(expert[:7] - proposal[:7], +-0.2)` rad
from (normalised proprio, normalised goal, normalised base action, chunk index)
and is deployed by `rl_env` when `FRUIT_A2C2=<out>/correction.pt` is set.

Pre-registered in `logs/path3/PREREGISTRATION.md`; the base checkpoint and the
rollouts are never modified. `--self-test` builds random windows in memory and
checks the round trip (train -> save -> load -> correct) without a checkpoint.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.policy.correction import (  # noqa: E402
    ACTION_DIM,
    GOAL_DIM,
    INDEX_SCALE,
    OBS_DIM,
    CorrectionController,
    CorrectionHead,
)
from fruit_sorting.policy.data import Normalizer  # noqa: E402

TARGET_CLAMP = 0.2


def load_rollouts(dirs: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Stack (proprio, goal, base action, correction target) over all frames."""
    proprio, goals, actions, targets = [], [], [], []
    for root in dirs:
        index_path = os.path.join(root, "index.json")
        if not os.path.exists(index_path):
            print(f"[correction] skip {root}: no index.json")
            continue
        with open(index_path, encoding="utf-8") as fh:
            entries = json.load(fh)
        for entry in entries:
            path = os.path.join(root, entry["file"])
            if not os.path.exists(path):
                continue
            data = np.load(path)
            if "policy_action" not in data.files or "action" not in data.files:
                continue
            obs = np.concatenate(
                [
                    data["joint_positions"].astype(np.float32),
                    data["finger_opening"].astype(np.float32),
                    data["tactile"].astype(np.float32),
                ],
                axis=1,
            )
            goal = data["goal"].astype(np.float32)
            base = data["policy_action"].astype(np.float32)
            expert = data["action"].astype(np.float32)
            target = np.clip(expert[:, :7] - base[:, :7], -TARGET_CLAMP, TARGET_CLAMP)
            keep = np.isfinite(obs).all(1) & np.isfinite(base).all(1) & np.isfinite(target).all(1)
            proprio.append(obs[keep])
            goals.append(goal[keep])
            actions.append(base[keep])
            targets.append(target[keep])
    if not proprio:
        raise RuntimeError("no DAgger frames with policy_action/action found")
    return (
        np.concatenate(proprio, 0),
        np.concatenate(goals, 0),
        np.concatenate(actions, 0),
        np.concatenate(targets, 0),
    )


def train(
    *,
    ckpt: str,
    rollouts: list[str],
    out_dir: str,
    epochs: int = 30,
    batch_size: int = 256,
    lr: float = 1e-3,
    seed: int = 0,
    device: str | None = None,
    verbose: bool = True,
) -> str:
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(seed)
    np.random.seed(seed)
    os.makedirs(out_dir, exist_ok=True)

    checkpoint = torch.load(ckpt, map_location="cpu", weights_only=False)
    norm = checkpoint["normalizer"]
    normalizer = Normalizer(
        action_mean=np.asarray(norm["action_mean"], dtype=np.float32),
        action_std=np.asarray(norm["action_std"], dtype=np.float32),
        obs_mean=np.asarray(norm["obs_mean"], dtype=np.float32),
        obs_std=np.asarray(norm["obs_std"], dtype=np.float32),
        goal_mean=np.asarray(norm["goal_mean"], dtype=np.float32),
        goal_std=np.asarray(norm["goal_std"], dtype=np.float32),
    )

    proprio, goals, actions, targets = load_rollouts(rollouts)
    obs = normalizer.normalize_obs(proprio).astype(np.float32)
    goal_n = normalizer.normalize_goal(goals).astype(np.float32)
    act_n = normalizer.normalize_action(actions[:, :ACTION_DIM]).astype(np.float32)
    index = np.zeros((len(obs), 1), dtype=np.float32)  # frames are decision points (index 0)
    x = torch.from_numpy(np.concatenate([obs, goal_n, act_n, index], 1)).to(device)
    y = torch.from_numpy(targets).to(device)
    if verbose:
        print(
            f"[correction] data: {len(obs)} frames from {len(rollouts)} dirs; "
            f"target mean|.|={float(torch.abs(y).mean()):.4f} rad "
            f"p95={float(torch.quantile(torch.abs(y).flatten().float(), 0.95)):.4f}"
        )

    model = CorrectionHead().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    dataset = torch.utils.data.TensorDataset(x, y)
    loader = torch.utils.data.DataLoader(
        dataset, batch_size=batch_size, shuffle=True, drop_last=False
    )
    history = []
    for epoch in range(int(epochs)):
        model.train()
        total, seen = 0.0, 0
        for bx, by in loader:
            predicted = model(bx[:, :OBS_DIM], bx[:, OBS_DIM:OBS_DIM + GOAL_DIM],
                              bx[:, OBS_DIM + GOAL_DIM:OBS_DIM + GOAL_DIM + ACTION_DIM],
                              bx[:, -1:])
            loss = torch.nn.functional.mse_loss(predicted, by)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            total += float(loss.item()) * bx.shape[0]
            seen += bx.shape[0]
        history.append(total / max(seen, 1))
        if verbose and (epoch % 5 == 0 or epoch == epochs - 1):
            print(f"[correction] epoch {epoch + 1}/{epochs} mse={history[-1]:.6f}")

    payload = {
        "model": model.state_dict(),
        "config": dict(model.config),
        "normalizer": normalizer.as_dict(),
        "meta": {
            "checkpoint": os.path.abspath(ckpt),
            "rollouts": [os.path.abspath(p) for p in rollouts],
            "frames": int(len(obs)),
            "epochs": int(epochs),
            "batch_size": int(batch_size),
            "lr": float(lr),
            "seed": int(seed),
            "target_clamp": TARGET_CLAMP,
            "index_scale": INDEX_SCALE,
            "history": history,
        },
    }
    out_path = os.path.join(out_dir, "correction.pt")
    torch.save(payload, out_path)
    with open(os.path.join(out_dir, "correction_history.json"), "w", encoding="utf-8") as fh:
        json.dump(payload["meta"], fh, indent=2)
    print(f"[correction] saved {out_path} (final mse {history[-1]:.6f})")
    return out_path


def self_test() -> int:
    """Offline round trip: random windows -> train -> save -> load -> correct."""
    import tempfile

    rng = np.random.default_rng(0)
    frames = 512
    proprio = rng.normal(0.0, 0.3, (frames, OBS_DIM)).astype(np.float32)
    goal = rng.normal(0.0, 0.3, (frames, GOAL_DIM)).astype(np.float32)
    action = rng.normal(0.0, 0.3, (frames, ACTION_DIM)).astype(np.float32)
    target = rng.normal(0.0, 0.02, (frames, 7)).astype(np.float32)

    # Minimal in-memory training of the real head (50 steps on 512 windows).
    model = CorrectionHead()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)
    x = torch.from_numpy(np.concatenate([proprio, goal, action[:, :ACTION_DIM],
                                         np.zeros((frames, 1), np.float32)], 1))
    y = torch.from_numpy(target)
    for _ in range(50):
        predicted = model(x[:, :OBS_DIM], x[:, OBS_DIM:OBS_DIM + GOAL_DIM],
                          x[:, OBS_DIM + GOAL_DIM:OBS_DIM + GOAL_DIM + ACTION_DIM],
                          x[:, -1:])
        loss = torch.nn.functional.mse_loss(predicted, y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
    if float(loss.item()) > 0.01:
        print(f"correction selftest FAIL: in-memory loss {float(loss.item())}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        payload = {
            "model": model.state_dict(),
            "config": dict(model.config),
            "normalizer": {
                "action_mean": np.zeros(ACTION_DIM, np.float32).tolist(),
                "action_std": np.ones(ACTION_DIM, np.float32).tolist(),
                "obs_mean": np.zeros(OBS_DIM, np.float32).tolist(),
                "obs_std": np.ones(OBS_DIM, np.float32).tolist(),
                "goal_mean": np.zeros(GOAL_DIM, np.float32).tolist(),
                "goal_std": np.ones(GOAL_DIM, np.float32).tolist(),
            },
            "meta": {},
        }
        path = os.path.join(tmp, "correction.pt")
        torch.save(payload, path)
        controller = CorrectionController(path, gain=1.0, clamp=0.2)
        base = np.zeros(9, np.float32)
        out = controller.correct(base, proprio[0], goal[0], 0)
        if out.shape != (9,) or not np.isfinite(out).all():
            print("correction selftest FAIL: bad controller output")
            return 1
        if float(np.abs(out - base).max()) > 0.2 + 1e-6:
            print("correction selftest FAIL: clamp not honoured")
            return 1
        if float(np.abs(out[7:]).max()) > 0:
            print("correction selftest FAIL: finger channels must be untouched")
            return 1
    print("correction selftest PASS (train, save/load, correct, clamp, finger untouched)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", default="checkpoints/moe_v11/policy_best.pt")
    parser.add_argument(
        "--rollouts",
        default=os.environ.get("FRUIT_A2C2_ROLLOUTS", "datasets/path3_a2c2_dagger"),
        help="comma-separated rollout roots (each with index.json + npz)",
    )
    parser.add_argument("--out", default="checkpoints/moe_v11_correction")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    dirs = [p for p in args.rollouts.split(",") if p.strip()]
    train(
        ckpt=args.ckpt,
        rollouts=dirs,
        out_dir=args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
        device=args.device or None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
