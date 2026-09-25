"""Benchmark diffusion-policy inference and the available speed-ups.

    /path/to/python scripts/80_benchmark_policy.py

Reports per-chunk latency and the control rate it supports, so the 20 Hz
sorting budget can be checked.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import numpy as np
import torch

from fruit_sorting.policy.runtime import PolicyRunner


def timeit(fn, warmup: int = 3, iters: int = 20) -> float:
    for _ in range(warmup):
        fn()
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    start = time.perf_counter()
    for _ in range(iters):
        fn()
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    return (time.perf_counter() - start) / iters * 1000.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", default=os.environ.get("FRUIT_CKPT", "checkpoints/moe_v1/policy_best.pt"))
    parser.add_argument("--steps", default="16,8,4,2", help="DDIM step counts to sweep")
    args = parser.parse_args()

    runner = PolicyRunner(args.ckpt, use_half=False)
    cfg = runner.config
    say = lambda m: print(m, flush=True)
    say(f"checkpoint {args.ckpt}")
    say(f"config {cfg}")
    say(f"device {runner.device}")

    rgb = (np.random.rand(480, 848, 3) * 255).astype(np.uint8)
    depth = (np.random.rand(480, 848, 1) * 2.0).astype(np.float32)
    for _ in range(runner.obs_horizon):
        runner.push_frame(rgb, depth)
    proprio = np.zeros(cfg["proprio_dim"], dtype=np.float32)
    goal = np.zeros(cfg["goal_dim"], dtype=np.float32)

    say("")
    say(f"{'variant':34s}{'ms/chunk':>12}{'Hz (serial)':>14}{'Hz (chunk 8)':>14}")
    results: dict[str, float] = {}
    for steps in [int(s) for s in args.steps.split(",")]:
        ms = timeit(lambda: runner.act(proprio, goal, num_steps=steps))
        results[f"ddim{steps}"] = ms
        say(f"{f'eager fp32, DDIM {steps} steps':34s}{ms:12.2f}{1000 / ms:14.1f}{8 * 1000 / ms:14.1f}")

    # Half precision (only worthwhile on GPU).
    if runner.device == "cuda":
        runner.set_precision(True)
        try:
            ms = timeit(lambda: runner.act(proprio, goal, num_steps=8))
            results["fp16"] = ms
            say(f"{'fp16, DDIM 8 steps':34s}{ms:12.2f}{1000 / ms:14.1f}{8 * 1000 / ms:14.1f}")
        except Exception as exc:  # noqa: BLE001
            say(f"fp16 failed: {exc}")
        runner.set_precision(False)

        # torch.compile fuses the UNet and removes Python overhead per step.
        try:
            runner.model = torch.compile(runner.model, mode="reduce-overhead")
            ms = timeit(lambda: runner.act(proprio, goal, num_steps=8), warmup=6, iters=20)
            results["compiled"] = ms
            say(f"{'torch.compile, DDIM 8 steps':34s}{ms:12.2f}{1000 / ms:14.1f}{8 * 1000 / ms:14.1f}")
        except Exception as exc:  # noqa: BLE001
            say(f"torch.compile failed: {exc}")

    say("")
    best = min(results.items(), key=lambda kv: kv[1])
    say(f"fastest variant: {best[0]} at {best[1]:.2f} ms/chunk")
    say(
        "note: the policy only runs when a new chunk is needed, so with an "
        "action_horizon of "
        f"{cfg['action_horizon']} and re-planning every N steps the amortised cost "
        "is ms/chunk / N"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
