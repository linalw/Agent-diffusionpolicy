"""Executed-stream smoothness, decision rate and policy latency (offline).

The v5-B metric (owner ask: "raise the decision rate and make the arm's motion
smoother / faster"): per-control-step joint-command **step** and **jerk** of the
stream the policy actually executes, the chunk-boundary discontinuity, the
**decision rate** (new chunks per second) and the wall-clock latency per
sampling call. No simulator: the policy is replayed over recorded `direct`
rollout / demonstration episodes, teacher-forced on their observations, exactly
like `scripts/124_rtc_boundary.py` (which measures only the boundary jump).

    python3 scripts/125_loop_metrics.py \
        --ckpt checkpoints/moe_v10/policy_best.pt \
        --data datasets/rl_rollouts/rwr1/direct_none_seed101 \
        --episodes 6 --exec-steps 1,2,4 --out logs/v5b/125_loop_metrics.txt

    python3 scripts/125_loop_metrics.py --self-test

Definitions (all on the 7-D arm unit of the executed command, radians):

* ``step_i   = || a_i - a_{i-1} ||``
* ``jerk_i   = || a_i - 2 a_{i-1} + a_{i-2} ||`` (second difference; at the
  fixed control period it is proportional to the true jerk)
* ``boundary = the step into the first action of a newly sampled chunk``;
  ``within`` = every other step. The ratio boundary/within is the same
  discontinuity measure `124` reports, but computed on the executed stream
  (legacy replays ``chunk[:E]`` per re-plan, not ``chunk[0]`` per re-plan).
* ``decision rate`` = sampled chunks per replayed second. The offline replay
  uses one recorded (30 Hz) frame as the control step, like `124`; the deployed
  120 Hz rate is measured in the simulator with ``FRUIT_RTC_REPORT=1``.
* ``latency`` = wall-clock per sampling call (legacy: the whole chunk; RTC: the
  interleaved per-control-step share), and the amortised ms per replayed frame.

Legacy re-plans every ``E`` frames and executes the chunk's first ``E`` actions;
RTC runs the interleaved chunker (one action per frame, sampler spread over
``E`` frames, ``FRUIT_RTC_*`` defaults: horizon 10, EXP). Both use
``FRUIT_POLICY_SEED`` for the sampler noise.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch

from fruit_sorting.policy.data import downsample_frame
from fruit_sorting.policy.runtime import PolicyRunner, RTCSettings, RealtimeChunker


def _load_episode(path: str) -> dict:
    """One recorded episode in the replay form (mirrors `124_rtc_boundary`)."""
    data = np.load(path)
    frames = []
    for k in range(data["image_rgb"].shape[0]):
        rgb = data["image_rgb"][k]
        depth = np.asarray(data["image_distance_to_image_plane"][k])
        if depth.ndim == 3:
            depth = depth[..., 0]
        mask = np.asarray(data["target_mask"][k]).astype(np.float32) / 255.0
        rgb_f = downsample_frame(rgb, 128).astype(np.float32) / 255.0
        depth_f = np.clip(downsample_frame(depth, 128).astype(np.float32), 0, 3) / 3.0
        mask_f = downsample_frame(mask, 128).astype(np.float32)
        frames.append(np.concatenate([rgb_f, depth_f[..., None], mask_f[..., None]], -1))
    proprio = np.concatenate(
        [
            np.asarray(data["joint_positions"], dtype=np.float32),
            np.asarray(data["finger_opening"], dtype=np.float32),
            np.asarray(data["tactile"], dtype=np.float32),
        ],
        axis=1,
    )
    return {
        "frames": frames,
        "proprio": proprio,
        "goal": np.asarray(data["goal"], dtype=np.float32),
        "length": len(frames),
    }


def _sync() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def _stats(values) -> dict:
    if len(values) == 0:
        return {"n": 0, "median": float("nan"), "p90": float("nan"), "max": float("nan")}
    a = np.asarray(values, dtype=np.float64)
    return {
        "n": int(a.size),
        "median": float(np.median(a)),
        "p90": float(np.percentile(a, 90)),
        "max": float(a.max()),
    }


def stream_metrics(stream: list[np.ndarray], boundary: list[bool]) -> dict:
    """Step/jerk/boundary statistics of an executed action stream (7-D units).

    ``boundary[i]`` is True when ``stream[i]`` is the first action of a new
    chunk. Pure arithmetic, so the self-test can call it directly.
    """
    arm = np.asarray(stream, dtype=np.float64)[:, :7]
    n = arm.shape[0]
    steps, boundary_steps, within_steps = [], [], []
    for i in range(1, n):
        value = float(np.linalg.norm(arm[i] - arm[i - 1]))
        steps.append(value)
        (boundary_steps if boundary[i] else within_steps).append(value)
    jerks = [
        float(np.linalg.norm(arm[i] - 2.0 * arm[i - 1] + arm[i - 2]))
        for i in range(2, n)
    ]
    b, w = _stats(boundary_steps), _stats(within_steps)
    s, j = _stats(steps), _stats(jerks)
    ratio = b["median"] / w["median"] if w["median"] else float("nan")
    return {
        "frames": int(n),
        "step": s,
        "jerk": j,
        "boundary": b,
        "within": w,
        "boundary_ratio": float(ratio),
    }


def replay_legacy(runner: PolicyRunner, episode: dict, exec_steps: int,
                  ddim: int, seed: int) -> dict:
    """Synchronous re-planning every ``exec_steps`` frames; execute chunk[:E]."""
    runner.reset()
    runner.generator = torch.Generator(device=runner.device).manual_seed(seed)
    length = episode["length"]
    stream: list[np.ndarray] = []
    boundary: list[bool] = []
    chunk_ms: list[float] = []
    decisions = 0
    for t in range(0, length, exec_steps):
        runner._frames = episode["frames"][max(0, t - runner.obs_horizon + 1) : t + 1]
        if len(runner._frames) < runner.obs_horizon:
            runner._frames = [episode["frames"][0]] * runner.obs_horizon
        start = time.perf_counter()
        chunk = runner.act(episode["proprio"][t], episode["goal"][t], num_steps=ddim)
        _sync()
        chunk_ms.append((time.perf_counter() - start) * 1e3)
        decisions += 1
        for i in range(min(exec_steps, len(chunk))):
            stream.append(np.asarray(chunk[i], dtype=np.float64))
            boundary.append(i == 0)
    return {
        "stream": stream,
        "boundary": boundary,
        "chunk_ms": chunk_ms,
        "decisions": decisions,
    }


def replay_rtc(runner: PolicyRunner, episode: dict, exec_steps: int,
               ddim: int, seed: int, settings: RTCSettings) -> dict:
    """Interleaved RTC chunker, one executed action per frame."""
    runner.reset()
    runner.generator = torch.Generator(device=runner.device).manual_seed(seed)
    chunker = RealtimeChunker(
        runner, execute_steps=exec_steps, settings=settings
    )
    length = episode["length"]
    stream: list[np.ndarray] = []
    boundary: list[bool] = []
    call_ms: list[float] = []
    switch = False
    for t in range(length):
        runner._frames = episode["frames"][max(0, t - runner.obs_horizon + 1) : t + 1]
        if len(runner._frames) < runner.obs_horizon:
            runner._frames = [episode["frames"][0]] * runner.obs_horizon
        start = time.perf_counter()
        action = chunker.next_action(
            lambda i=t: episode["proprio"][i], episode["goal"][t], ddim
        )
        _sync()
        call_ms.append((time.perf_counter() - start) * 1e3)
        boundary.append(bool(switch))
        stream.append(np.asarray(action, dtype=np.float64))
        switch = bool(chunker.last_switch)
    return {
        "stream": stream,
        "boundary": boundary,
        "chunk_ms": call_ms,
        "decisions": int(chunker.chunks_sampled),
    }


def _pooled(rows: list[dict], key: str) -> dict:
    values = [r[key]["median"] for r in rows if r[key]["n"]]
    return _stats(values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", default="checkpoints/moe_v10/policy_best.pt")
    parser.add_argument("--data",
                        default="datasets/rl_rollouts/rwr1/direct_none_seed101")
    parser.add_argument("--episodes", type=int, default=6)
    parser.add_argument("--exec-steps", default="1,2,4")
    parser.add_argument("--arms", default="legacy,rtc",
                        help="comma list of legacy,rtc")
    parser.add_argument("--ddim", type=int, default=16)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--rtc-horizon", type=int, default=10)
    parser.add_argument("--rtc-schedule", default="EXP",
                        choices=["EXP", "LINEAR", "ONES", "ZEROS"])
    parser.add_argument("--out", default="logs/v5b/125_loop_metrics.txt")
    args = parser.parse_args()

    exec_steps = [int(v) for v in str(args.exec_steps).split(",") if v.strip()]
    arms = [a.strip() for a in str(args.arms).split(",") if a.strip()]
    files = sorted(glob.glob(os.path.join(args.data, "*.npz")))[: args.episodes]
    if not files:
        raise SystemExit(f"no episode npz under {args.data}")
    runner = PolicyRunner(args.ckpt)
    print(f"125 loop metrics: {len(files)} episodes from {args.data}, "
          f"ckpt={args.ckpt}, ddim={args.ddim}, seed={args.seed}")

    per_episode: list[dict] = []
    starts = []
    for path in files:
        episode = _load_episode(path)
        for e in exec_steps:
            for arm in arms:
                start = time.perf_counter()
                if arm == "legacy":
                    result = replay_legacy(runner, episode, e, args.ddim, args.seed)
                elif arm == "rtc":
                    settings = RTCSettings(
                        enabled=True, inference_delay=e,
                        execution_horizon=args.rtc_horizon,
                        max_guidance_weight=1.0, schedule=args.rtc_schedule,
                    )
                    result = replay_rtc(runner, episode, e, args.ddim, args.seed,
                                        settings)
                else:
                    raise SystemExit(f"unknown arm {arm!r}")
                metrics = stream_metrics(result["stream"], result["boundary"])
                calls = _stats(result["chunk_ms"])
                elapsed = time.perf_counter() - start
                print(
                    f"  [125] {os.path.basename(path)} {arm} E={e}: "
                    f"{elapsed:.1f}s, call {calls['median']:.1f} ms, "
                    f"decisions {result['decisions']}",
                    flush=True,
                )
                per_episode.append(
                    {
                        "episode": os.path.basename(path),
                        "arm": arm,
                        "exec_steps": e,
                        "decisions": result["decisions"],
                        "decision_rate": result["decisions"] / (episode["length"] / 30.0),
                        "latency_ms": calls,
                        "amortised_ms_per_frame": (
                            float(np.sum(result["chunk_ms"])) / episode["length"]
                        ),
                        "wall_s": float(time.perf_counter() - start),
                        **metrics,
                    }
                )

    lines = [
        f"checkpoint {args.ckpt}",
        f"data {args.data} ({len(files)} episodes)",
        "executed stream, 7-D arm units (rad); one executed action per replayed",
        "30 Hz frame; latency is wall-clock on this machine",
        "",
        f"{'episode':<20s} {'arm':<7s} {'E':>2s} {'frames':>6s} {'bnd med':>8s} "
        f"{'within':>8s} {'ratio':>6s} {'step':>8s} {'jerk':>8s} "
        f"{'dec/s':>6s} {'ms/call':>8s} {'ms/frame':>8s}",
    ]
    for row in per_episode:
        lines.append(
            f"{row['episode']:<20s} {row['arm']:<7s} {row['exec_steps']:>2d} "
            f"{row['frames']:>6d} {row['boundary']['median']:8.4f} "
            f"{row['within']['median']:8.4f} {row['boundary_ratio']:6.2f} "
            f"{row['step']['median']:8.4f} {row['jerk']['median']:8.4f} "
            f"{row['decision_rate']:6.1f} {row['latency_ms']['median']:8.2f} "
            f"{row['amortised_ms_per_frame']:8.2f}"
        )

    lines.append("")
    lines.append("pooled over episodes (median of the per-episode medians):")
    pooled = []
    for e in exec_steps:
        for arm in arms:
            rows = [r for r in per_episode if r["arm"] == arm and r["exec_steps"] == e]
            if not rows:
                continue
            entry = {
                "arm": arm,
                "exec_steps": e,
                "frames": int(np.median([r["frames"] for r in rows])),
                "boundary_median": _pooled(rows, "boundary")["median"],
                "within_median": _pooled(rows, "within")["median"],
                "boundary_ratio": float(
                    np.median([r["boundary_ratio"] for r in rows])
                ),
                "step_median": _pooled(rows, "step")["median"],
                "jerk_median": _pooled(rows, "jerk")["median"],
                "decision_rate": float(np.median([r["decision_rate"] for r in rows])),
                "latency_ms_median": _pooled(rows, "latency_ms")["median"],
                "amortised_ms_per_frame": float(
                    np.median([r["amortised_ms_per_frame"] for r in rows])
                ),
            }
            pooled.append(entry)
            lines.append(
                f"  {arm:<6s} E={e}: frames {entry['frames']:>4d}  "
                f"boundary {entry['boundary_median']:.4f}  "
                f"within {entry['within_median']:.4f}  "
                f"ratio {entry['boundary_ratio']:.2f}  "
                f"step {entry['step_median']:.4f}  jerk {entry['jerk_median']:.4f}  "
                f"decisions {entry['decision_rate']:.1f}/s  "
                f"call {entry['latency_ms_median']:.2f} ms  "
                f"amortised {entry['amortised_ms_per_frame']:.2f} ms/frame"
            )

    text = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(args.out.replace(".txt", ".json"), "w", encoding="utf-8") as fh:
        json.dump({"episodes": per_episode, "pooled": pooled}, fh, indent=2)
    print(text)
    print(f"wrote {args.out}")
    return 0


def self_test() -> int:
    """Offline arithmetic checks (also wired into scripts/selfcheck.sh)."""
    failures = []
    # A 4-action executed stream: 0 -> 0.1 -> 0.2 -> 0 (a chunk boundary into 0).
    stream = [
        np.array([0.0] * 9),
        np.array([0.1] + [0.0] * 8),
        np.array([0.2] + [0.0] * 8),
        np.array([0.0] * 9),
    ]
    boundary = [False, False, False, True]
    m = stream_metrics(stream, boundary)
    if abs(m["step"]["median"] - 0.1) > 1e-9:
        failures.append(f"step median {m['step']['median']} != 0.1")
    if abs(m["within"]["median"] - 0.1) > 1e-9:
        failures.append(f"within median {m['within']['median']} != 0.1")
    if abs(m["boundary"]["median"] - 0.2) > 1e-9:
        failures.append(f"boundary median {m['boundary']['median']} != 0.2")
    if abs(m["boundary_ratio"] - 2.0) > 1e-9:
        failures.append(f"boundary ratio {m['boundary_ratio']} != 2.0")
    if abs(m["jerk"]["n"] - 2) != 0:
        failures.append(f"jerk count {m['jerk']['n']} != 2")
    # jerk at action 3 (0 - 2*0.2 + 0.1 = -0.3) and at action 4 skipped (n-2).
    if abs(max(m["jerk"]["max"], 0.0) - 0.3) > 1e-9:
        failures.append(f"jerk max {m['jerk']['max']} != 0.3")
    # decision rate: 8 chunks over 240 frames (8 s at 30 Hz) = 1/s.
    if abs(8 / (240 / 30.0) - 1.0) > 1e-12:
        failures.append("decision rate arithmetic")
    # stats helper on a known list.
    s = _stats([1.0, 2.0, 3.0])
    if s["median"] != 2.0 or abs(s["p90"] - 2.8) > 1e-9 or s["n"] != 3:
        failures.append(f"stats helper {s}")
    if failures:
        print("loop metrics self-test FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("loop metrics self-test PASS (step, jerk, boundary split, decision rate)")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    raise SystemExit(main())
