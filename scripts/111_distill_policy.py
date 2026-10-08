"""Distill a diffusion policy into a 1-4 step consistency sampler (offline, no Isaac).

    python3 scripts/111_distill_policy.py \
        --teacher checkpoints/moe_v10/policy_best.pt \
        --data datasets/demos_v9 \
        --out checkpoints/distill_v1 \
        --epochs 8 --loss both --x0-weight 1.0 --ema-decay 0.999

The teacher is frozen; the student is the same `ConditionalUNet1D` backbone with
the consistency-distillation objective (`src/fruit_sorting/policy/distill.py`,
the Consistency Policy recipe). The saved checkpoint has the stock layout plus a
`config["sampler"] = "consistency"` marker and a `provenance` block (teacher md5,
dataset index/manifest md5, the held-out episode split, every knob). Deploy it
with the existing runner at `--ddim 1|2|4`: the shipped DDIM chain with k steps
*is* the k-step consistency sampler at the same timesteps.

Knobs (flags or environment): `--loss` = both|cd|x0 (`cd` = consistency
distillation only, `x0` = local denoiser anchor only); `--x0-weight` scales the
anchor in `both`; `--stride` is the teacher DDIM step size the CD target uses;
`--save` picks online/ema/better (better = the smaller paired endpoint deviation
from the teacher on the held-out windows). `--max-batches` truncates epochs for
smoke runs.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.policy.distill import distill


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teacher",
                        default=os.environ.get("FRUIT_TEACHER",
                                              "checkpoints/moe_v10/policy_best.pt"))
    parser.add_argument("--data", default=os.environ.get("FRUIT_DISTILL_DATA",
                                                         "datasets/demos_v9"))
    parser.add_argument("--out", default=os.environ.get("FRUIT_DISTILL_OUT",
                                                        "checkpoints/distill_v1"))
    parser.add_argument("--epochs", type=int, default=int(os.environ.get("EPOCHS", "8")))
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("BATCH", "32")))
    parser.add_argument("--lr", type=float, default=float(os.environ.get("LR", "5e-5")))
    parser.add_argument("--loss", default=os.environ.get("DISTILL_LOSS", "both"),
                        choices=["cd", "x0", "both", "endpoint", "progressive", "deploy"])
    parser.add_argument("--x0-weight", type=float,
                        default=float(os.environ.get("X0_WEIGHT", "1.0")))
    parser.add_argument("--ema-decay", type=float,
                        default=float(os.environ.get("EMA_DECAY", "0.999")))
    parser.add_argument("--stride", type=int, default=int(os.environ.get("STRIDE", "1")),
                        help="teacher DDIM step size for the CD target (1 = adjacent)")
    parser.add_argument("--teacher-steps", type=int,
                        default=int(os.environ.get("TEACHER_STEPS", "16")),
                        help="teacher chain length for the endpoint objective")
    parser.add_argument("--level-focus", default=os.environ.get("LEVEL_FOCUS", ""),
                        help="endpoint objective level probabilities, e.g. "
                             "'99:0.5,66:0.15,33:0.15,0:0.1' (rest uniform)")
    parser.add_argument("--progressive-scheme",
                        default=os.environ.get("PROGRESSIVE_SCHEME", "chain"),
                        choices=["chain", "continuous"],
                        help="chain = the shipped student's recipe (teacher-chain "
                             "intervals); continuous = data-noised arbitrary-t variant")
    parser.add_argument("--chain-steps", type=int,
                        default=int(os.environ.get("CHAIN_STEPS", "4")),
                        help="`deploy` loss: deployment chain length (the stock "
                             "DDIM k the student is built for)")
    parser.add_argument("--student-clamp", type=float,
                        default=float(os.environ.get("STUDENT_CLAMP", "100.0")),
                        help="`deploy` loss: training-time clamp on the student's "
                             "implied x0 (relaxed so the first interval has a "
                             "gradient; the deployed sampler keeps its +/-4 clamp)")
    parser.add_argument("--endpoint-weight", type=float,
                        default=float(os.environ.get("ENDPOINT_WEIGHT", "0.0")),
                        help="`deploy` loss: weight of the final clean-output anchor")
    parser.add_argument("--eps-weight", type=float,
                        default=float(os.environ.get("EPS_WEIGHT", "0.0")),
                        help="`deploy` loss: weight of the direct teacher-eps "
                             "distillation at the deployment levels")
    parser.add_argument("--input-mode",
                        default=os.environ.get("INPUT_MODE", "teacher"),
                        choices=["teacher", "mixed", "student"],
                        help="`deploy` loss: input at levels after the first - "
                             "teacher forcing (teacher), the student's own "
                             "previous output (student), or a per-sample mix")
    parser.add_argument("--mix-prob", type=float,
                        default=float(os.environ.get("MIX_PROB", "0.5")),
                        help="`deploy` loss with --input-mode mixed: per-sample "
                             "probability of using the student's own output")
    parser.add_argument("--input-noise", type=float,
                        default=float(os.environ.get("INPUT_NOISE", "0.0")),
                        help="`deploy` loss: std of zero-mean Gaussian noise added "
                             "to the forced inputs")
    parser.add_argument("--save-epochs", action="store_true",
                        help="also write policy_epoch{N}.pt every epoch")
    parser.add_argument("--max-timestep", type=int,
                        default=int(os.environ.get("MAX_TIMESTEP", "0")),
                        help="highest training timestep (0 = the schedule's T-1)")
    parser.add_argument("--val-fraction", type=float,
                        default=float(os.environ.get("VAL_FRACTION", "0.15")),
                        help="held-out fraction of *episodes* (never trained on)")
    parser.add_argument("--router-weight", type=float,
                        default=float(os.environ.get("ROUTER_WEIGHT", "0.1")))
    parser.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", "2")))
    parser.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "0")))
    parser.add_argument("--probe-steps", type=int,
                        default=int(os.environ.get("PROBE_STEPS", "1")),
                        help="student step count used for the online/ema probe")
    parser.add_argument("--probe-every", type=int,
                        default=int(os.environ.get("PROBE_EVERY", "0")),
                        help="run the endpoint probe every N epochs (0 = only at the end)")
    parser.add_argument("--save", default=os.environ.get("SAVE", "better"),
                        choices=["online", "ema", "better", "best_probe"])
    parser.add_argument("--max-batches", type=int,
                        default=int(os.environ.get("MAX_BATCHES", "0")),
                        help="truncate epochs after this many batches (smoke runs)")
    parser.add_argument("--device", default=os.environ.get("DEVICE", ""))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    path = distill(
        teacher=args.teacher,
        data_dir=args.data,
        out_dir=args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        loss=args.loss,
        x0_weight=args.x0_weight,
        ema_decay=args.ema_decay,
        stride=args.stride,
        max_timestep=args.max_timestep,
        val_fraction=args.val_fraction,
        router_loss_weight=args.router_weight,
        workers=args.workers,
        seed=args.seed,
        teacher_steps=args.teacher_steps,
        level_focus=args.level_focus,
        progressive_scheme=args.progressive_scheme,
        chain_steps=args.chain_steps,
        student_clamp=args.student_clamp,
        endpoint_weight=args.endpoint_weight,
        eps_weight=args.eps_weight,
        input_mode=args.input_mode,
        mix_prob=args.mix_prob,
        input_noise=args.input_noise,
        save_epochs=args.save_epochs,
        probe_steps=args.probe_steps,
        probe_every=args.probe_every,
        save=args.save,
        max_batches=args.max_batches,
        device=args.device or None,
        verbose=not args.quiet,
    )
    print(f"[distill] done -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
