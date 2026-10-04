"""Fine-tune a policy checkpoint on reward-weighted rollouts (offline, no Isaac).

    <lingbot-python> scripts/111_rl_finetune.py \
        --ckpt checkpoints/moe_v7/policy_best.pt \
        --rollouts datasets/rl_rollouts/direct_none_seed77 \
        --out checkpoints/rl_iter1

Knobs (flags or environment): EPOCHS, LR, WEIGHT_MODE, BETA, FAILURE_WEIGHT,
BASE_WEIGHT; the base demonstrations are mixed in at BASE_WEIGHT. The last epoch
is saved as `policy_best.pt` (not best-val on the demos - see
`fruit_sorting.policy.finetune`), with a provenance block naming the base
checkpoint, the rollout data and every weight knob.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.policy.finetune import finetune


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", default=os.environ.get("FRUIT_CKPT",
                                                         "checkpoints/moe_v7/policy_best.pt"))
    parser.add_argument("--rollouts", default=os.environ.get("FRUIT_RL_ROLLOUTS", ""))
    parser.add_argument("--base", default=os.environ.get("FRUIT_BASE_DEMOS", "datasets/demos_v7"))
    parser.add_argument("--out", default=os.environ.get("FRUIT_RL_CKPT_DIR", "checkpoints/rl_iter1"))
    parser.add_argument("--epochs", type=int, default=int(os.environ.get("EPOCHS", "4")))
    parser.add_argument("--lr", type=float, default=float(os.environ.get("LR", "5e-5")))
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("BATCH", "32")))
    parser.add_argument("--weight-mode", default=os.environ.get("WEIGHT_MODE", "success"),
                        choices=["ones", "success", "awr"])
    parser.add_argument("--beta", type=float, default=float(os.environ.get("BETA", "4.0")))
    parser.add_argument("--failure-weight", type=float,
                        default=float(os.environ.get("FAILURE_WEIGHT", "0.05")))
    parser.add_argument("--base-weight", type=float,
                        default=float(os.environ.get("BASE_WEIGHT", "1.0")))
    parser.add_argument("--hard-epochs", type=int, default=int(os.environ.get("HARD_EPOCHS", "0")),
                        help="force the router from the skill label for this many epochs")
    parser.add_argument("--close-weight", type=float,
                        default=float(os.environ.get("CLOSE_WEIGHT", "1.0")),
                        help="timing-aware objective: upweight the windows that start "
                             "near the recorded close command (>= 1.0; 1.0 off)")
    parser.add_argument("--close-lead", type=int,
                        default=int(os.environ.get("CLOSE_LEAD", "10")),
                        help="frames before the close start included in the boost")
    parser.add_argument("--close-tail", type=int,
                        default=int(os.environ.get("CLOSE_TAIL", "10")),
                        help="frames after the close start included in the boost")
    parser.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "0")))
    parser.add_argument("--device", default=os.environ.get("DEVICE", ""))
    args = parser.parse_args()
    if not args.rollouts:
        parser.error("--rollouts is required (a directory written by scripts/110_rl_rollout.py --record)")

    path = finetune(
        checkpoint=args.ckpt,
        rollouts=args.rollouts,
        base=args.base or None,
        out_dir=args.out,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        weight_mode=args.weight_mode,
        beta=args.beta,
        failure_weight=args.failure_weight,
        base_weight=args.base_weight,
        hard_epochs=args.hard_epochs,
        close_weight=args.close_weight,
        close_lead=args.close_lead,
        close_tail=args.close_tail,
        seed=args.seed,
        device=args.device or None,
    )
    print(f"[finetune] done -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
