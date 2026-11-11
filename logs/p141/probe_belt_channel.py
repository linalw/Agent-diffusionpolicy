#!/usr/bin/env python3
"""P141: does the model actually *use* the belt channels?

Three measurements, all offline (no simulator):

1. **Sensitivity** - take a real window from the wave store, sample the chunk
   with the true observation, then again with the belt channels replaced by the
   *constant-belt belief* (`v = 0.12`, `a = 0`, 26th proprio = 0.12). The mean
   absolute action change over the chunk is the answer. Two controls calibrate
   it: a repeated call with the same observation (the sampler's own noise, which
   is zero with a seeded generator) and a 1e-6 nudge to an unrelated goal dim
   (the numerical floor).
2. **Latency** - the wall time of one `act` at DDIM 16 vs 8, because that is the
   budget `execute_steps` trades against (`FRUIT_POLICY_EXEC_STEPS` /
   `FRUIT_POLICY_DDIM`).
3. **Sanity** - the chunk's finger channel and joint range, so a degenerate
   prediction cannot masquerade as a sensitivity.
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

os.environ.setdefault("FRUIT_OBS_SPEED", "1")
os.environ.setdefault("FRUIT_OBS_GOAL_AUX", "1")

import torch  # noqa: E402

from fruit_sorting.policy.data import EpisodeStore  # noqa: E402
from fruit_sorting.policy.runtime import PolicyRunner  # noqa: E402

FLAT_V = 0.12
FLAT_A = 0.0


def chunk_for(runner: PolicyRunner, item: dict, num_steps: int) -> np.ndarray:
    """Sample one chunk for a store item, bypassing the frame ring buffer."""
    dtype = torch.float16 if runner.use_half else torch.float32
    image = torch.from_numpy(np.asarray(item["image"], dtype=np.float32))[None]
    goal = np.asarray(item["goal"], dtype=np.float32)
    proprio = np.asarray(item["proprio"], dtype=np.float32)
    goal_t = torch.from_numpy(runner.normalizer.normalize_goal(goal)[None])
    proprio_t = torch.from_numpy(runner.normalizer.normalize_obs(proprio)[None])
    condition = (
        image.to(runner.device, dtype=dtype),
        goal_t.to(runner.device, dtype=dtype),
        proprio_t.to(runner.device, dtype=dtype),
    )
    generator = torch.Generator(device=runner.device).manual_seed(0)
    with torch.no_grad():
        sample = runner.schedule.ddim_sample(
            runner.model,
            condition,
            (1, int(runner.config["action_dim"]), int(runner.action_horizon)),
            num_steps=num_steps,
            dtype=dtype,
            generator=generator,
        )
    action = sample[0].float().transpose(0, 1).cpu().numpy()
    return runner.normalizer.denormalize_action(action)


def flatten(item: dict) -> dict:
    """The same window with the belt channels at the constant-belt belief."""
    out = dict(item)
    goal = np.asarray(item["goal"], dtype=np.float32).copy()
    if goal.size >= 10:
        goal[-2] = FLAT_V
        goal[-1] = FLAT_A
    proprio = np.asarray(item["proprio"], dtype=np.float32).copy()
    if proprio.size >= 26:
        proprio[-1] = FLAT_V
    out["goal"] = goal
    out["proprio"] = proprio
    return out


def nudge(item: dict) -> dict:
    """The numerical-floor control: an unrelated goal dim moved by 1e-6."""
    out = dict(item)
    goal = np.asarray(item["goal"], dtype=np.float32).copy()
    goal[6] = float(goal[6]) + 1e-6
    out["goal"] = goal
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", default="checkpoints/p141_wave/policy_best.pt")
    parser.add_argument("--store", default="datasets/p141_wave")
    parser.add_argument("--windows", type=int, default=12)
    parser.add_argument("--steps", type=int, default=16)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    runner = PolicyRunner(args.ckpt, device=args.device)
    config = runner.config
    print(
        f"[probe] {args.ckpt}: goal_dim={config['goal_dim']} "
        f"proprio_dim={config['proprio_dim']} obs_horizon={config['obs_horizon']}"
    )
    store = EpisodeStore(
        args.store,
        obs_horizon=int(config["obs_horizon"]),
        action_horizon=int(config["action_horizon"]),
        image_size=int(config["image_size"]),
        speed_channel=int(config["proprio_dim"]) > 25,
        goal_aux=int(config["goal_dim"]) > 8,
    )
    print(f"[probe] store: {store.summary()}")

    # One window per episode, evenly spaced - a spread of belt phases.
    per_episode: dict[int, list[int]] = {}
    for index, (ep, _t) in enumerate(store.windows):
        per_episode.setdefault(ep, []).append(index)
    picks: list[int] = []
    eps = sorted(per_episode)
    while len(picks) < min(args.windows, len(store.windows)):
        for ep in eps:
            rows = per_episode[ep]
            if rows and len(picks) < args.windows:
                picks.append(rows[len(picks) % len(rows)])
        if len(picks) >= len(store.windows):
            break

    rows = {"repeat": [], "nudge": [], "flat": []}
    finger_span, joint_span = [], []
    for index in picks:
        item = store[index]
        base = chunk_for(runner, item, args.steps)
        # Deterministic sampler: the same condition must give the same chunk.
        again = chunk_for(runner, item, args.steps)
        rows["repeat"].append(float(np.abs(base - again).mean()))
        rows["nudge"].append(
            float(np.abs(base - chunk_for(runner, nudge(item), args.steps)).mean())
        )
        rows["flat"].append(
            float(np.abs(base - chunk_for(runner, flatten(item), args.steps)).mean())
        )
        finger_span.append(float(np.ptp(base[:, 7])))
        joint_span.append(float(np.abs(base[:, :7]).max()))

    def report(name: str, values: list[float]) -> float:
        median = statistics.median(values)
        print(
            f"[probe] {name:8s} mean |dAction| median {median:.5f} "
            f"mean {statistics.mean(values):.5f} max {max(values):.5f} rad"
        )
        return median

    repeat = report("repeat", rows["repeat"])
    nudge_v = report("nudge", rows["nudge"])
    flat = report("flat", rows["flat"])
    floor = max(repeat, nudge_v)
    ratio = flat / floor if floor > 0 else float("inf")
    print(
        f"[probe] belt-state sensitivity: {flat:.5f} rad vs a floor of "
        f"{floor:.5f} = {ratio:.1f}x"
    )
    print(
        f"[probe] finger span p50 {statistics.median(finger_span):.2f} mm, "
        f"joint |a| max p50 {statistics.median(joint_span):.2f} rad"
    )
    verdict = "USED" if ratio >= 3.0 else "not resolved"
    print(f"[probe] verdict: the belt channels are {verdict} by the model")

    # ---- latency -------------------------------------------------------- #
    item = store[picks[0]]
    warm = chunk_for(runner, item, args.steps)
    del warm
    timings = {}
    for steps in (16, 8):
        samples = []
        for _ in range(12):
            start = time.perf_counter()
            chunk_for(runner, item, steps)
            samples.append((time.perf_counter() - start) * 1e3)
        samples.sort()
        timings[steps] = samples
        print(
            f"[probe] ddim={steps:2d}: p50 {samples[len(samples) // 2]:.1f} ms, "
            f"p95 {samples[int(len(samples) * 0.95)]:.1f} ms"
        )
    print(
        f"[probe] 8 steps is {timings[16][len(timings[16]) // 2] / timings[8][len(timings[8]) // 2]:.2f}x "
        f"the 16-step p50"
    )
    if args.json:
        import json

        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "checkpoint": args.ckpt,
                    "store": args.store,
                    "windows": len(picks),
                    "sensitivity": {k: v for k, v in rows.items()},
                    "ratio": ratio,
                    "timings_ms": {str(k): v for k, v in timings.items()},
                },
                fh,
                indent=2,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
