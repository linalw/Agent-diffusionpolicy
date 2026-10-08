"""Jaw-TCP SPARC + executed-stream boundary probe for one policy checkpoint.

The survey's smoothness metric (`docs/research_dynamic_grasp_methods.md` §5):
jaw-TCP **SPARC** (spectral arc length of the speed profile, Balasubramanian et
al. 2015) plus the executed-stream boundary jump at each re-plan. This script
runs the direct interface for a few episodes and records, once per policy call
(30 Hz), the measured jaw centre and the chunk-boundary jump; after the run it
prints per-episode SPARC values (policy phase and full episode) and the boundary
statistics, and writes them to JSON.

Diagnostic by construction (it reads the jaw every control call and reports);
never use its success counts for anything - rates come from
`scripts/110_rl_rollout.py`. One simulator at a time.

    FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_TRIGGER=arrival \
      scripts/run.sh scripts/136_policy_sparc.py \
        --ckpt checkpoints/distill_v1/policy_best.pt \
        --episodes 3 --seed 77 --ddim 1 \
        --out logs/distill/136_sparc_student1.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import numpy as np

from isaacsim import SimulationApp

HEADLESS = os.environ.get("HEADLESS", "1") == "1"

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.rl_env import RewardConfig, SortingRLEnv  # noqa: E402

#: Reference SPARC parameters (monalysa / Balasubramanian): low-pass fc, the
#: magnitude threshold that trims the noise floor, and FFT zero-padding.
SPARC_FC = 10.0
SPARC_AMP_TH = 0.05
SPARC_PAD = 4


def sparc(speed: np.ndarray, fs: float, fc: float = SPARC_FC,
          amp_th: float = SPARC_AMP_TH, padlevel: int = SPARC_PAD) -> float:
    """Spectral arc length of a speed profile (negative; 0 = smoothest).

    Port of the reference implementation: normalized FFT magnitude, band-limited
    to `fc`, trimmed to the last bin >= `amp_th`, arc length over the normalized
    frequency axis.
    """
    speed = np.asarray(speed, dtype=np.float64)
    if speed.size < 4 or not np.any(speed > 0):
        return 0.0
    nfft = int(pow(2, np.ceil(np.log2(len(speed))) + padlevel))
    frequency = np.arange(0, fs, fs / nfft)
    magnitude = np.abs(np.fft.fft(speed, nfft))
    peak = float(magnitude.max())
    if peak <= 0:
        return 0.0
    magnitude = magnitude / peak
    band = frequency <= fc
    frequency = frequency[band]
    magnitude = magnitude[band]
    above = np.flatnonzero(magnitude >= amp_th)
    if above.size < 2:
        return 0.0
    frequency = frequency[above[0]: above[-1] + 1]
    magnitude = magnitude[above[0]: above[-1] + 1]
    span = frequency[-1] - frequency[0]
    if span <= 0:
        return 0.0
    return float(
        -np.sum(
            np.sqrt(
                (np.diff(frequency) / span) ** 2 + np.diff(magnitude) ** 2
            )
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", default=os.environ.get(
        "FRUIT_CKPT", "checkpoints/moe_v10/policy_best.pt"))
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--seed", type=int, default=77)
    parser.add_argument("--execute-steps", type=int, default=4)
    parser.add_argument("--ddim", type=int, default=16)
    parser.add_argument("--out", default="logs/distill/136_sparc.json")
    parser.add_argument("--out-dir", default="logs/distill/sparc_rollouts")
    parser.add_argument("--report", action="store_true",
                        help="FRUIT_RTC_REPORT=1: also record the env's per-control-step "
                             "wall time, decisions/s and boundary statistics (mechanism "
                             "run; do not quote its outcomes as rates)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    install_failure_handler("136_policy_sparc")
    if args.report:
        os.environ["FRUIT_RTC_REPORT"] = "1"

    env = SortingRLEnv(
        presentation="direct",
        seed=int(args.seed),
        checkpoint=args.ckpt,
        out_dir=args.out_dir,
        execute_steps=int(args.execute_steps),
        ddim_steps=int(args.ddim),
        reward=RewardConfig(),
        verbose=args.verbose,
    )

    reports = []
    for episode in range(int(args.episodes)):
        env.reset(int(args.seed) if episode == 0 else None)
        jaw_trace: list[np.ndarray] = []
        policy_trace: list[bool] = []
        boundaries: list[float] = []
        previous_executed: np.ndarray | None = None
        done = False
        result = None
        while not done:
            chunk = env.sample_chunk()
            result = env.act(chunk, execute_steps=int(args.execute_steps))
            done = bool(result.done)
            arm = env.task.arms[env._active]
            jaw_trace.append(np.asarray(arm.jaw_centre(), dtype=np.float64))
            in_policy = not bool(getattr(env, "_triggered", False))
            policy_trace.append(in_policy)
            # Executed boundary at this re-plan: chunk[0] vs the previous
            # call's last executed action (same definition as the 124/125
            # legacy replay, one sample per control call).
            if chunk is not None:
                first = np.asarray(chunk[0], dtype=np.float64)[:7]
                if previous_executed is not None:
                    boundaries.append(
                        float(np.linalg.norm(first - previous_executed))
                    )
                index = min(int(args.execute_steps), len(chunk)) - 1
                previous_executed = np.asarray(chunk[index], dtype=np.float64)[:7]
        info = result.info if result is not None else {}
        jaw = np.asarray(jaw_trace, dtype=np.float64)
        speed = (
            np.linalg.norm(np.diff(jaw, axis=0), axis=1) * 30.0
            if len(jaw) > 1 else np.zeros(1)
        )
        policy_mask = np.asarray(policy_trace, dtype=bool)
        policy_jaw = (
            jaw[: int(np.argmax(~policy_mask)) + 1]
            if bool((~policy_mask).any()) else jaw
        )
        policy_speed = (
            np.linalg.norm(np.diff(policy_jaw, axis=0), axis=1) * 30.0
            if len(policy_jaw) > 1 else np.zeros(1)
        )
        row = {
            "episode": episode,
            "category": info.get("category", ""),
            "diameter": float(info.get("diameter", 0.0)),
            "success": bool(info.get("success", False)),
            "ticks": int(info.get("ticks", 0)),
            "samples": int(len(jaw)),
            "sparc_full": sparc(speed, 30.0),
            "sparc_policy": sparc(policy_speed, 30.0),
            "boundary_median": float(np.median(boundaries)) if boundaries else float("nan"),
            "boundary_p90": float(np.percentile(boundaries, 90)) if boundaries else float("nan"),
            "boundary_max": float(np.max(boundaries)) if boundaries else float("nan"),
            "boundaries": len(boundaries),
        }
        reports.append(row)
        say(
            f"[sparc] episode {episode}: {row['category']} success={row['success']} "
            f"samples={row['samples']} sparc_full={row['sparc_full']:.4f} "
            f"sparc_policy={row['sparc_policy']:.4f} "
            f"boundary_med={row['boundary_median']:.4f}"
        )
        if args.report:
            for key in (
                "rtc_boundaries", "rtc_boundary_median", "rtc_within_median",
                "rtc_step_median", "rtc_jerk_median", "rtc_switches",
                "rtc_decisions", "rtc_decision_rate", "rtc_policy_ms_median",
                "rtc_policy_ms_per_step", "rtc_control_ms_median",
            ):
                row[key] = info.get(key, float("nan"))
            say(
                f"[sparc]   report: decisions={row['rtc_decisions']} "
                f"rate={row['rtc_decision_rate']:.1f}/s "
                f"policy_ms={row['rtc_policy_ms_median']:.2f} "
                f"control_ms={row['rtc_control_ms_median']:.2f} "
                f"boundary={row['rtc_boundary_median']:.4f} "
                f"jerk={row['rtc_jerk_median']:.4f}"
            )

    payload = {
        "checkpoint": args.ckpt,
        "ddim": int(args.ddim),
        "execute_steps": int(args.execute_steps),
        "seed": int(args.seed),
        "episodes": reports,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    pooled_full = np.median([r["sparc_full"] for r in reports]) if reports else float("nan")
    pooled_policy = np.median([r["sparc_policy"] for r in reports]) if reports else float("nan")
    say(
        f"[sparc] pooled: sparc_full {pooled_full:.4f} sparc_policy {pooled_policy:.4f} "
        f"-> {args.out}"
    )
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
