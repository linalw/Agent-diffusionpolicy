"""Policy sampler latency at 1/2/4 steps (offline, fp16, same machine).

The v5 decision-rate question: the shipped DDIM-16 teacher costs ~26 ms/chunk;
the distilled consistency student is sampled through the stock DDIM chain, so
`num_steps` is the deployed sampler budget. This measures the wall-clock chunk
cost at 1/2/4 (and the teacher's 16) with warmup, plus one `push_frame` (the
30 Hz camera preprocessing the deployed loop pays), and prints the decision
rate each budget allows (1 / chunk cost) and the duty against the 8.33 ms
control period.

    python3 scripts/137_student_latency.py --ckpt checkpoints/distill_v1/policy_best.pt \
        --label student --data datasets/demos_v9 --steps 1,2,4 --out logs/distill/137_latency_student.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch

from fruit_sorting.policy.data import EpisodeStore
from fruit_sorting.policy.runtime import PolicyRunner


def sync() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def timed(fn, repeats: int, warmup: int = 5) -> dict:
    for _ in range(warmup):
        fn()
    sync()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        sync()
        samples.append(time.perf_counter() - start)
    a = np.asarray(samples)
    return {
        "n": int(repeats),
        "median_ms": float(np.median(a) * 1e3),
        "p10_ms": float(np.percentile(a, 10) * 1e3),
        "p90_ms": float(np.percentile(a, 90) * 1e3),
        "min_ms": float(a.min() * 1e3),
        "max_ms": float(a.max() * 1e3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--label", default="policy")
    parser.add_argument("--data", default="datasets/demos_v9")
    parser.add_argument("--steps", default="1,2,4")
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--device", default="")
    parser.add_argument("--out", default="logs/distill/137_latency.json")
    args = parser.parse_args()
    steps = [int(v) for v in str(args.steps).split(",") if v.strip()]

    runner = PolicyRunner(args.ckpt, device=args.device or None)
    device = runner.device
    store = EpisodeStore(args.data, obs_horizon=2, action_horizon=16, image_size=128,
                         only_successful=True)
    obs = store[0]
    frames = [
        np.transpose(obs["image"][k], (1, 2, 0)) for k in range(obs["image"].shape[0])
    ]
    raw_rgb = np.zeros((240, 424, 3), dtype=np.uint8)
    raw_depth = np.zeros((240, 424), dtype=np.float32)
    raw_mask = np.zeros((240, 424), dtype=np.float32)

    report = {
        "checkpoint": args.ckpt,
        "label": args.label,
        "device": str(device),
        "half": bool(runner.use_half),
        "frequency_hz": 120.0,
        "control_period_ms": 1000.0 / 120.0,
        "steps": {},
    }
    for k in steps:
        def call(num_steps=k):
            runner._frames = frames
            return runner.act(obs["proprio"], obs["goal"], num_steps=num_steps)

        row = timed(call, int(args.repeats))
        row["decisions_per_s"] = 1000.0 / row["median_ms"] if row["median_ms"] else float("inf")
        row["duty_at_120hz"] = row["median_ms"] / report["control_period_ms"]
        report["steps"][str(k)] = row

    def preprocess():
        runner._frames = []
        runner.push_frame(raw_rgb, raw_depth, raw_mask)

    report["push_frame_cpu"] = timed(preprocess, max(10, args.repeats // 3), warmup=2)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"=== {args.label}: {args.ckpt} ({device}, half={runner.use_half})")
    print(f"{'steps':>5s} {'median':>8s} {'p10':>8s} {'p90':>8s} "
          f"{'dec/s':>8s} {'duty':>6s}")
    for k in steps:
        row = report["steps"][str(k)]
        print(f"{k:>5d} {row['median_ms']:8.2f} {row['p10_ms']:8.2f} "
              f"{row['p90_ms']:8.2f} {row['decisions_per_s']:8.1f} "
              f"{row['duty_at_120hz']:6.2f}")
    print(f"push_frame CPU: {report['push_frame_cpu']['median_ms']:.2f} ms")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
