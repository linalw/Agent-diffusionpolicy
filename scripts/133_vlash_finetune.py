"""VLASH temporal-offset fine-tune of a policy checkpoint (offline, no Isaac).

    <lingbot-python> scripts/133_vlash_finetune.py \
        --ckpt checkpoints/moe_v10/policy_best.pt \
        --data datasets/demos_v9 \
        --out checkpoints/moe_v10_vlash \
        --delta-max 4 --epochs 6

Implements the fine-tuning half of VLASH (arXiv 2512.01031,
`docs/research_dynamic_grasp_methods.md` rank 3): for each demonstration window
``(o_t, s_t, A_t)`` the training sample draws ``delta ~ U{0..delta_max}`` and
pairs the **image at t** with the **state and action chunk at t+delta**, so the
model learns to turn a rolled-forward execution-time state into the actions
that are correct at execution time. Deployment (``FRUIT_VLASH=1``) rolls the
state forward under the previously issued chunk by the inference delay and adds
no runtime overhead.

The fine-tune is plain behaviour cloning on the demonstrations
(``weight_mode=ones``); the base checkpoint and the dataset are never modified -
the result goes to a new directory.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.policy.finetune import finetune


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ckpt",
        default=os.environ.get("FRUIT_CKPT", "checkpoints/moe_v10/policy_best.pt"),
        help="base checkpoint to continue-train (not modified)",
    )
    parser.add_argument(
        "--data",
        default=os.environ.get("FRUIT_BASE_DEMOS", "datasets/demos_v9"),
        help="demonstration directory (the VLASH base data)",
    )
    parser.add_argument(
        "--out",
        default=os.environ.get("FRUIT_VLASH_CKPT_DIR", "checkpoints/moe_v10_vlash"),
        help="output checkpoint directory (new name; the base is untouched)",
    )
    parser.add_argument(
        "--delta-max",
        type=int,
        default=int(os.environ.get("FRUIT_VLASH_DELTA_MAX", "4")),
        help="maximum temporal offset in recorded frames (delta ~ U{0..max}); "
             "0 = no augmentation (plain behaviour cloning)",
    )
    parser.add_argument("--epochs", type=int, default=int(os.environ.get("EPOCHS", "6")))
    parser.add_argument("--lr", type=float, default=float(os.environ.get("LR", "2e-5")))
    parser.add_argument(
        "--batch-size", type=int, default=int(os.environ.get("BATCH", "32"))
    )
    parser.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "0")))
    parser.add_argument("--device", default=os.environ.get("DEVICE", ""))
    args = parser.parse_args()

    path = finetune(
        checkpoint=args.ckpt,
        rollouts="",
        base=args.data,
        out_dir=args.out,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        weight_mode="ones",
        vlash_offset_max=args.delta_max,
        seed=args.seed,
        device=args.device or None,
    )
    print(f"[vlash] done -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
