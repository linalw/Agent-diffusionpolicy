"""Offline latency budget for the policy loop (P4: RTC-style async chunking).

No simulator. Measures, on the machine that runs the policy:

1. The DDIM chunk cost of a checkpoint (default `checkpoints/moe_v9`), fp16
   (the deployed setting) and fp32, at several sampler budgets. The number the
   RTC/execute-steps choice divides by is the *full chunk* cost.
2. The per-denoising-step UNet cost, so an interleaved sampler's per-control-step
   work can be predicted as `steps_per_call * step_cost`.
3. The CPU frame preprocessing (`PolicyRunner.push_frame` on a real 240x424
   RGB+depth+mask observation), which the env pays once per observation tick
   (every 4 physics ticks / 30 Hz).
4. The control period: physics runs at 1/120 s per control step, so a chunk
   sampled every `execute_steps` control steps has a sim-time budget of
   `execute_steps / 120` s. The table prints the *amortised* per-control-step
   cost and the real-time factor it implies.

The environment's own wall-clock per control step (physics + render + camera +
policy) is measured in the simulator, not here; this script isolates the policy.

    python3 scripts/123_rtc_budget.py --ckpt checkpoints/moe_v9/policy_best.pt
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


def timed(fn, repeats: int, warmup: int = 3) -> dict:
    """Wall-clock seconds per call: median/p10/p90/min/max over `repeats`."""
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
    parser.add_argument("--ckpt", default="checkpoints/moe_v9/policy_best.pt")
    parser.add_argument("--data", default="datasets/demos_v8",
                        help="window source for one real observation")
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--device", default="")
    parser.add_argument("--out", default="logs/123_rtc_budget.json")
    args = parser.parse_args()

    device = args.device or None
    torch.manual_seed(0)
    start = time.perf_counter()
    runner = PolicyRunner(args.ckpt, device=device)
    load_s = time.perf_counter() - start
    device = runner.device
    dtype = torch.float16 if runner.use_half else torch.float32

    # One real observation from a recorded episode: same construction the env uses.
    store = EpisodeStore(args.data, obs_horizon=2, action_horizon=16, image_size=128,
                         only_successful=True)
    obs = store[0]
    frames = [np.transpose(obs["image"][k], (1, 2, 0)) for k in range(obs["image"].shape[0])]
    raw_rgb = np.zeros((240, 424, 3), dtype=np.uint8)
    raw_depth = np.zeros((240, 424), dtype=np.float32)
    raw_mask = np.zeros((240, 424), dtype=np.float32)

    report: dict = {
        "checkpoint": args.ckpt,
        "device": str(device),
        "half": bool(runner.use_half),
        "load_s": round(load_s, 3),
        "obs_horizon": runner.obs_horizon,
        "action_horizon": runner.action_horizon,
        "action_dim": int(runner.config["action_dim"]),
        "num_train_steps": int(runner.schedule.num_train_steps),
        "beta_schedule": str(runner.schedule.beta_schedule),
    }

    # --- chunk cost -------------------------------------------------------- #
    chunks = {}
    for steps in (16, 8, 4, 2):
        def call(num_steps=steps):
            runner._frames = frames
            return runner.act(obs["proprio"], obs["goal"], num_steps=num_steps)

        chunks[str(steps)] = timed(call, args.repeats)
    report["ddim_chunk"] = chunks

    # --- per-denoising-step UNet cost -------------------------------------- #
    condition = runner._condition(obs["proprio"], obs["goal"])  # implemented by the RTC patch
    sample = torch.randn((1, runner.config["action_dim"], runner.action_horizon),
                         device=device, dtype=dtype)
    t = torch.full((1,), 50, device=device, dtype=torch.long)

    def denoise():
        return runner.model.denoise(sample, condition, t)

    report["unet_denoise_step"] = timed(denoise, args.repeats)

    # --- CPU preprocessing (one 240x424 RGB + depth + mask frame) ---------- #
    def preprocess():
        runner._frames = []
        runner.push_frame(raw_rgb, raw_depth, raw_mask)

    report["push_frame_cpu"] = timed(preprocess, max(args.repeats, 10), warmup=2)

    # --- budget arithmetic -------------------------------------------------- #
    control_period_ms = 1000.0 / 120.0
    full_ms = chunks["16"]["median_ms"]
    budget = {
        "control_period_ms": control_period_ms,
        "physics_hz": 120,
        "chunk_cost_ms": full_ms,
        "amortised_ms_per_control_step": {
            str(e): full_ms / e for e in (1, 2, 4, 8)
        },
        "chunk_cost_in_control_steps": full_ms / control_period_ms,
        "observation_preprocess_ms": report["push_frame_cpu"]["median_ms"],
        "note": (
            "amortised = full DDIM-16 chunk / execute_steps; a wall-clock control "
            "step in the sim is physics+render+camera+policy and is measured in "
            "scripts/127_rtc_ab.sh with FRUIT_RTC_REPORT=1"
        ),
    }
    report["budget"] = budget

    # --- interleaved RTC sampler: per-control-step cost --------------------- #
    from fruit_sorting.policy.runtime import RTCSampler

    interleave = {}
    for calls in (1, 2, 4):
        per_call: list[float] = []
        totals: list[float] = []
        for _ in range(max(3, args.repeats // 3)):
            prev = np.random.RandomState(0).randn(16, 9).astype(np.float32) * 0.1
            sampler = RTCSampler(
                runner, condition, prev, num_steps=16, inference_delay=calls,
                execution_horizon=10, schedule="EXP",
            )
            chunk_start = time.perf_counter()
            while True:
                sync()
                start = time.perf_counter()
                finished = sampler.advance()
                sync()
                per_call.append((time.perf_counter() - start) * 1e3)
                if finished:
                    break
            totals.append((time.perf_counter() - chunk_start) * 1e3)
        interleave[str(calls)] = {
            "call_ms_median": float(np.median(per_call)),
            "chunk_total_ms_median": float(np.median(totals)),
            "calls": int(calls),
        }
    report["rtc_interleave"] = interleave

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"=== policy latency budget ({args.ckpt}, {device}, half={runner.use_half})")
    print(f"load {load_s:.2f}s, obs_horizon={runner.obs_horizon}, "
          f"action_horizon={runner.action_horizon}, beta={runner.schedule.beta_schedule}")
    print("DDIM chunk (median/p10/p90 ms):")
    for steps, row in chunks.items():
        print(f"  {steps:>2s} steps: {row['median_ms']:7.2f} / {row['p10_ms']:7.2f} / "
              f"{row['p90_ms']:7.2f}  -> {row['median_ms'] / control_period_ms:5.2f} control steps")
    print(f"UNet denoise step: {report['unet_denoise_step']['median_ms']:.2f} ms")
    print(f"push_frame CPU:    {report['push_frame_cpu']['median_ms']:.2f} ms")
    print(f"control period:    {control_period_ms:.2f} ms (120 Hz)")
    print("interleaved RTC sampler (DDIM-16 over E control steps):")
    for calls, row in report["rtc_interleave"].items():
        print(f"  E={calls}: {row['call_ms_median']:6.2f} ms/call "
              f"({row['chunk_total_ms_median']:6.2f} ms/chunk)")
    print("amortised policy cost per control step (ms): "
          + ", ".join(f"E={e}: {full_ms / e:.1f}" for e in (1, 2, 4, 8)))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
