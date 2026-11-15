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

P28-B (the belt-speed channel, `logs/p28/SPEED_CHANNEL_DESIGN.md` 2.2): with
`FRUIT_OBS_SPEED=1` the observation is 26-D and a 25-D `--ckpt` is widened
(one zero column + the fixed `(0.12, 0.05)` normaliser entry). Stores whose
manifest records `supply.belt_speed` (every shard collected since `9cbcfa2`)
pin themselves; the older ones are declared with `--store-speed PATH=SPEED`
(repeatable) or `--base-speed SPEED`, and the declaration is recorded in the
provenance block. The pin table is in the design's section 4.3.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.policy.finetune import finetune


def _parse_store_speeds(items: list[str]) -> dict[str, float]:
    """`PATH=SPEED` -> {normalised path: speed}; a malformed item is an error."""
    pins: dict[str, float] = {}
    for item in items:
        path, sep, value = item.rpartition("=")
        if not sep or not path:
            raise SystemExit(f"--store-speed expects PATH=SPEED, got {item!r}")
        try:
            pins[os.path.normpath(path)] = float(value)
        except ValueError as exc:
            raise SystemExit(f"--store-speed {item!r}: {exc}") from exc
    return pins


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
    parser.add_argument("--obs-cmd", action="store_true",
                        default=os.environ.get("FRUIT_OBS_CMD", "0") == "1",
                        help="P145d.4: append the commanded finger to the proprio")
    parser.add_argument("--action-horizon", type=int, default=None,
                        help="P145: override the checkpoint's action horizon "
                             "(a window property; no weights change). Pair it "
                             "with --execute-steps equal to it.")
    parser.add_argument("--first-steps", type=int,
                        default=int(os.environ.get("FIRST_STEPS", "0")),
                        help="P145: train only the first N actions of each chunk "
                             "(what the env executes before re-planning; 0 = all)")
    parser.add_argument("--close-tail", type=int,
                        default=int(os.environ.get("CLOSE_TAIL", "10")),
                        help="frames after the close start included in the boost")
    parser.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "0")))
    parser.add_argument("--device", default=os.environ.get("DEVICE", ""))
    parser.add_argument("--store-speed", action="append", default=[],
                        metavar="PATH=SPEED",
                        help="P28-B belt-speed pin [m/s] for a store whose "
                             "manifest does not record supply.belt_speed "
                             "(repeatable; the design's 4.3 table)")
    parser.add_argument("--base-speed", type=float, default=None,
                        help="P28-B belt-speed pin [m/s] for the --base store "
                             "(overrides --store-speed for it)")
    parser.add_argument("--goal-aux", action="store_true", default=None,
                        help="P141: append the belt's (v_belt, a_belt) to the "
                             "goal (8 -> 10 dims, zero columns) and train on it")
    parser.add_argument("--obs-horizon", type=int, default=None,
                        help="P141: widen the observation horizon (2 -> 4); the "
                             "visual encoder's first kernel is repeated and halved")
    args = parser.parse_args()
    if not args.rollouts and not args.base:
        # P148: a **base-only** fine-tune is a valid mode (`run_finetune` skips the
        # rollout store when it is empty) and is the control for the DAgger
        # store's close-state labels, which are one IK step from the measured
        # joints (0.199 rad over 16 frames) against the demos' tracking hold
        # (0.734 rad) - with `close_weight` they dominate the close-state fit.
        parser.error(
            "--rollouts or --base is required (a store written by "
            "scripts/110_rl_rollout.py --record, or the demonstrations)"
        )

    pins = _parse_store_speeds(args.store_speed)
    rollout_speed = pins.get(os.path.normpath(args.rollouts))
    base_speed = (
        args.base_speed
        if args.base_speed is not None
        else pins.get(os.path.normpath(args.base)) if args.base else None
    )
    if args.store_speed:
        print(f"[finetune] pinned stores: {pins}")

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
        first_steps=args.first_steps,
        action_horizon=args.action_horizon,
        cmd_channel=args.obs_cmd,
        rollout_speed=rollout_speed,
        base_speed=base_speed,
        goal_aux=args.goal_aux,
        obs_horizon=args.obs_horizon,
        seed=args.seed,
        device=args.device or None,
    )
    print(f"[finetune] done -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
