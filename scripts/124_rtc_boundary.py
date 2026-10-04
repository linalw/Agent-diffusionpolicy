"""Chunk-boundary discontinuity on recorded rollouts, legacy vs RTC (offline).

No simulator. Replays the policy over the observation sequence of a few
recorded `direct` rollouts (`datasets/rl_rollouts/...`, the training schema:
30 Hz frames, joint/finger/tactile proprio, goal) and measures the executed
action stream's jump at every chunk boundary:

    legacy, execute_steps E:    jump_k = || chunk_{k+1}[0]  - chunk_k[E-1] ||
    RTC, period E:              jump_k = || new[E]           - old[E-1] ||
                                (new[E-1] is frozen to old[E-1])

Against the within-chunk reference, the distribution of
``|| chunk[i+1] - chunk[i] ||``. The metric is reported in the 7-D arm units
(`[:7]`, rad) and the full 9-D units (the finger channel included), median and
p90 over each episode, plus the fraction of boundaries above the within-chunk
p95.

The rollout's recorded observations are teacher-forced (the policy's own actions
were not re-applied to the simulator), so this measures the *sampler's* boundary
behaviour on real observation sequences, not closed-loop dynamics. The in-sim
executed boundary is reported by the env with `FRUIT_RTC_REPORT=1` during the
rate runs.

    python3 scripts/124_rtc_boundary.py \
        --ckpt checkpoints/moe_v9/policy_best.pt \
        --data datasets/rl_rollouts/rwr1/direct_none_seed101 \
        --episodes 6 --exec-steps 1,2,4 --out logs/rtc/124_boundary.txt
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch

from fruit_sorting.policy.runtime import PolicyRunner, RTCSettings, RealtimeChunker


def _load_episode(path: str) -> dict:
    data = np.load(path)
    frames = []
    for k in range(data["image_rgb"].shape[0]):
        rgb = data["image_rgb"][k]
        depth = np.asarray(data["image_distance_to_image_plane"][k])
        if depth.ndim == 3:
            depth = depth[..., 0]
        mask = (np.asarray(data["target_mask"][k]).astype(np.float32) / 255.0)
        from fruit_sorting.policy.data import downsample_frame

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
        "frames": frames,       # already downsampled (H, W, C), the runner buffer form
        "proprio": proprio,     # (T, 25)
        "goal": np.asarray(data["goal"], dtype=np.float32),
        "recorded": np.asarray(data["action"], dtype=np.float32),
        "length": len(frames),
    }


def _norm(a: np.ndarray, dims: int) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=np.float64)[:dims]))


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median": float("nan"), "p90": float("nan"), "max": float("nan")}
    a = np.asarray(values)
    return {
        "n": int(len(a)),
        "median": float(np.median(a)),
        "p90": float(np.percentile(a, 90)),
        "max": float(a.max()),
    }


def replay_legacy(
    runner: PolicyRunner, episode: dict, exec_steps: int, ddim: int, seed: int
) -> dict:
    runner.reset()
    runner.generator = torch.Generator(device=runner.device).manual_seed(seed)
    length = episode["length"]
    boundary = {7: [], 9: []}
    within = {7: [], 9: []}
    executed = []
    positions = list(range(0, length, exec_steps))
    for t in positions:
        runner._frames = episode["frames"][max(0, t - runner.obs_horizon + 1) : t + 1]
        if len(runner._frames) < runner.obs_horizon:
            runner._frames = [episode["frames"][0]] * runner.obs_horizon
        chunk = runner.act(episode["proprio"][t], episode["goal"][t], num_steps=ddim)
        previous = executed[-1] if executed else None
        executed.append(np.asarray(chunk[0], dtype=np.float64))
        if previous is not None:
            for dims in (7, 9):
                boundary[dims].append(_norm(chunk[0] - previous, dims))
        for i in range(min(exec_steps, len(chunk) - 1)):
            for dims in (7, 9):
                within[dims].append(_norm(chunk[i + 1] - chunk[i], dims))
    return {"boundary": boundary, "within": within, "replans": len(positions)}


def replay_rtc(
    runner: PolicyRunner, episode: dict, exec_steps: int, ddim: int, seed: int,
    settings: RTCSettings,
) -> dict:
    runner.reset()
    runner.generator = torch.Generator(device=runner.device).manual_seed(seed)
    chunker = RealtimeChunker(
        runner, execute_steps=exec_steps, settings=settings, trace_samplers=True
    )
    boundary = {7: [], 9: []}
    within = {7: [], 9: []}
    executed = []
    previous_switch = False
    goal = episode["goal"]
    for t in range(episode["length"]):
        runner._frames = episode["frames"][max(0, t - runner.obs_horizon + 1) : t + 1]
        if len(runner._frames) < runner.obs_horizon:
            runner._frames = [episode["frames"][0]] * runner.obs_horizon
        proprio = episode["proprio"][t]
        # Snapshot the state the env would pass; the closure keeps `t` current.
        action = chunker.next_action(lambda i=t: episode["proprio"][i], goal[t], ddim)
        if executed:
            for dims in (7, 9):
                delta = _norm(action - executed[-1], dims)
                (boundary if previous_switch else within)[dims].append(delta)
        executed.append(np.asarray(action, dtype=np.float64))
        previous_switch = bool(chunker.last_switch)
    freeze = []
    for row in chunker.trace:
        prefix = min(int(row["prefix"]), len(row["prev"]) if row["prev"] is not None else 0)
        if row["prev"] is not None and prefix > 0:
            freeze.append(_norm(row["chunk"][prefix - 1] - row["prev"][prefix - 1], 7))
    return {
        "boundary": boundary,
        "within": within,
        "replans": len(executed),
        "switches": len(chunker.trace),
        "freeze_error": freeze,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", default="checkpoints/moe_v9/policy_best.pt")
    parser.add_argument("--data",
                        default="datasets/rl_rollouts/rwr1/direct_none_seed101")
    parser.add_argument("--episodes", type=int, default=6)
    parser.add_argument("--exec-steps", default="1,2,4")
    parser.add_argument("--ddim", type=int, default=16)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--out", default="logs/rtc/124_boundary.txt")
    args = parser.parse_args()
    exec_steps = [int(v) for v in str(args.exec_steps).split(",") if v.strip()]

    import glob

    files = sorted(glob.glob(os.path.join(args.data, "rollout_*.npz")))[: args.episodes]
    if not files:
        raise SystemExit(f"no rollout npz under {args.data}")
    runner = PolicyRunner(args.ckpt)
    print(f"replaying {len(files)} rollouts, ddim={args.ddim}, seed={args.seed}")

    lines = [
        f"checkpoint {args.ckpt}",
        f"data {args.data} ({len(files)} episodes)",
        "boundary = jump between the last executed action and the first action of the",
        "next chunk; within = consecutive sampled actions inside a chunk (7-D arm norm, rad)",
        "",
    ]
    table = []
    for path in files:
        episode = _load_episode(path)
        for e in exec_steps:
            legacy = replay_legacy(runner, episode, e, args.ddim, args.seed)
            settings = RTCSettings(
                enabled=True, inference_delay=e, execution_horizon=10,
                max_guidance_weight=1.0, schedule="EXP",
            )
            rtc = replay_rtc(runner, episode, e, args.ddim, args.seed, settings)
            for label, result in (("legacy", legacy), ("rtc", rtc)):
                for dims in (7, 9):
                    b = _stats(result["boundary"][dims])
                    w = _stats(result["within"][dims])
                    ratio = b["median"] / w["median"] if w["median"] else float("nan")
                    if result["within"][dims] and result["boundary"][dims]:
                        threshold = np.percentile(result["within"][dims], 95)
                        over = float(
                            np.mean(np.asarray(result["boundary"][dims]) > threshold)
                        )
                    else:
                        over = float("nan")
                    table.append(
                        {
                            "episode": os.path.basename(path),
                            "arm": label,
                            "exec_steps": e,
                            "dims": dims,
                            "replans": result["replans"],
                            "switches": len(result["boundary"][dims]),
                            "boundary_median": b["median"],
                            "boundary_p90": b["p90"],
                            "within_median": w["median"],
                            "ratio": ratio,
                            "frac_over_within_p95": over,
                            "freeze_error_median": (
                                _stats(result["freeze_error"])["median"]
                                if result.get("freeze_error") else float("nan")
                            ),
                        }
                    )
        lines.append(
            f"{os.path.basename(path)}: {episode['length']} frames, "
            f"recorded actions {episode['recorded'].shape}"
        )

    lines.append("")
    lines.append(
        f"{'episode':<16s} {'arm':<7s} {'E':>2s} {'dim':>3s} {'#bnd':>5s} "
        f"{'bnd med':>8s} {'bnd p90':>8s} {'within':>8s} {'ratio':>6s} "
        f"{'over p95':>8s} {'freeze':>7s}"
    )
    for row in table:
        lines.append(
            f"{row['episode']:<16s} {row['arm']:<7s} {row['exec_steps']:>2d} "
            f"{row['dims']:>3d} {row['switches']:>5d} "
            f"{row['boundary_median']:8.4f} {row['boundary_p90']:8.4f} "
            f"{row['within_median']:8.4f} {row['ratio']:6.2f} "
            f"{row['frac_over_within_p95']:8.2f} {row['freeze_error_median']:7.5f}"
        )

    # Pooled summary per (arm, E) over episodes.
    lines.append("")
    lines.append("pooled over episodes (7-D arm units):")
    for e in exec_steps:
        for arm in ("legacy", "rtc"):
            rows = [r for r in table if r["arm"] == arm and r["exec_steps"] == e
                    and r["dims"] == 7]
            b = np.asarray([r["boundary_median"] for r in rows])
            w = np.asarray([r["within_median"] for r in rows])
            ratios = b / w
            lines.append(
                f"  {arm:<6s} E={e}: boundary median {np.median(b):.4f} rad "
                f"(range {b.min():.4f}-{b.max():.4f}), within {np.median(w):.4f}, "
                f"ratio {np.median(ratios):.2f}"
            )

    text = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(args.out.replace(".txt", ".json"), "w", encoding="utf-8") as fh:
        json.dump(table, fh, indent=2)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
