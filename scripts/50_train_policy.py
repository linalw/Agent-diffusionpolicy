"""Train the diffusion policy on the collected demonstrations.

    /path/to/python scripts/50_train_policy.py

This runs outside Isaac Sim: it only needs PyTorch and the recorded episodes.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.policy.train import train


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=os.environ.get("FRUIT_DEMO_DIR", "datasets/demos_v1"))
    parser.add_argument("--out", default=os.environ.get("FRUIT_CKPT_DIR", "checkpoints/policy"))
    parser.add_argument("--epochs", type=int, default=int(os.environ.get("EPOCHS", "6")))
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("BATCH", "32")))
    parser.add_argument("--lr", type=float, default=float(os.environ.get("LR", "1e-4")))
    parser.add_argument("--obs-horizon", type=int, default=int(os.environ.get("OBS_H", "2")))
    parser.add_argument("--action-horizon", type=int, default=int(os.environ.get("ACT_H", "16")))
    parser.add_argument("--image-size", type=int, default=int(os.environ.get("IMG", "128")))
    args = parser.parse_args()

    train(
        data_dir=args.data,
        out_dir=args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        obs_horizon=args.obs_horizon,
        action_horizon=args.action_horizon,
        image_size=args.image_size,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
