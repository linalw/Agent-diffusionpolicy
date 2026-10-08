"""Roll out a trained policy in the sorting cell (P4: RL post-training).

    scripts/run.sh scripts/110_rl_rollout.py \
        --ckpt checkpoints/moe_v7/policy_best.pt \
        --presentation direct --episodes 15 --seeds 77 --record

One invocation runs `--episodes` episodes per seed, all inside one simulator
session, and prints one machine-readable `[rl] episode ...` line per episode
(`success/grasped/placed/ticks/reward/notes`) that `scripts/113_rl_report.py`
parses. The environment and everything it writes is described in
`src/fruit_sorting/rl_env.py`; the manifest path is printed at the start.

`--presentation handoff` reproduces `scripts/60_eval_policy.py` (P0a check);
`--presentation direct` is the causal interface the RL work uses. `--ablate
zero` feeds zero actions instead of the policy's (P0b causal check: if zero
actions score the same as the trained policy, the interface is inert);
`--ablate scripted` runs the demonstration controller instead.

`--dagger` runs the direct env with the scripted pick-phase controller as an
HG-DAgger expert: every recorded frame's `action` is the expert's command for
that state, the expert takes control for `--expert-window` policy steps when the
policy's action deviates by more than `--expert-tolerance` rad (or closes the
finger before the tracking window), and the policy's own proposal is recorded
alongside as `policy_action`. The run prints the takeover summary at the end;
use `--record` to write the training data.

`--rtc` enables RTC-style asynchronous chunking (`--execute-steps` is the chunk
turnover period; the sampler is interleaved over that many control steps, one
action per step). The knobs map to `FRUIT_RTC_*` (`--rtc-delay`,
`--rtc-horizon`, `--rtc-schedule`, `--rtc-max-weight`); `--rtc-report` records
per-control-step wall time and the executed boundary jumps. Default off.
`--rtc-no-guidance` runs the same async chunker without freeze/soft-inpaint and
`--vlash` additionally conditions the sampler on the rolled-forward
execution-time state (VLASH; needs the offset fine-tune).

One simulator at a time: the caller must make sure no other Isaac process is
running (`pgrep -fc "[p]ython.sh"`).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

# Set HEADLESS=0 to watch the run in the Isaac Sim GUI.
HEADLESS = os.environ.get("HEADLESS", "1") == "1"

from fruit_sorting.fdlimit import raise_fd_limit

# Raise the fd limit before Isaac Sim starts: this build opens ~2100
# `/dev/nvidiactl` descriptors on the first camera read and dies with
# `dup failed ... Too many open files` at the default limit.
raise_fd_limit()

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.rl_env import ExpertConfig, RewardConfig, SortingRLEnv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ckpt",
        default=os.environ.get("FRUIT_CKPT", "checkpoints/moe_v7/policy_best.pt"),
        help="policy checkpoint (used when --ablate none)",
    )
    parser.add_argument(
        "--out",
        default=os.environ.get("FRUIT_RL_OUT", "datasets/rl_rollouts"),
        help="rollout output root; one manifest/npz directory per (presentation, ablate, seed)",
    )
    parser.add_argument("--episodes", type=int,
                        default=int(os.environ.get("FRUIT_EPISODES", "15")))
    parser.add_argument("--seeds", default=os.environ.get("FRUIT_RL_SEEDS", "77"),
                        help="comma-separated spawner seeds, one run each")
    parser.add_argument("--presentation", choices=["direct", "handoff"], default="direct")
    parser.add_argument("--size-filter", choices=["", "small", "large"], default="",
                        help="SceneConfig fruit-size pool (empty = FRUIT_SIZE_FILTER/default)")
    parser.add_argument("--ablate", choices=["none", "zero", "scripted"], default="none")
    parser.add_argument("--record", action="store_true",
                        help="write per-episode npz + index.json (training schema)")
    parser.add_argument("--execute-steps", type=int, default=4,
                        help="actions executed per re-plan (harness: FRUIT_EXEC=4)")
    parser.add_argument("--ddim", type=int, default=16)
    parser.add_argument("--approach-steps", type=int, default=400,
                        help="handoff presentation only: the harness's APPROACH_STEPS")
    parser.add_argument("--horizon", type=int, default=1500,
                        help="episode tick budget (reward normalisation horizon)")
    parser.add_argument("--time-penalty", type=float, default=0.2)
    parser.add_argument("--dagger", action="store_true",
                        help="DAgger: record the scripted pick-phase command as the "
                             "label; hand the expert control for a short window when "
                             "the policy action deviates (direct presentation only)")
    parser.add_argument("--expert-tolerance", type=float,
                        default=float(os.environ.get("FRUIT_RL_EXPERT_TOL", "0.35")),
                        help="joint-space deviation [rad] that triggers an expert window")
    parser.add_argument("--expert-window", type=int,
                        default=int(os.environ.get("FRUIT_RL_EXPERT_WINDOW", "15")),
                        help="policy steps (4 ticks each) the expert holds control")
    parser.add_argument("--rtc", action="store_true",
                        help="RTC-style async chunking: one action per control step, "
                             "the next chunk sampled interleaved over --execute-steps "
                             "control steps (direct presentation only)")
    parser.add_argument("--rtc-no-guidance", action="store_true",
                        help="FRUIT_RTC_GUIDANCE=0: plain async chunk switching, no "
                             "freeze/soft-inpaint (the VLASH-style deployment)")
    parser.add_argument("--vlash", action="store_true",
                        help="FRUIT_VLASH=1: async chunking with guidance off and the "
                             "sampler conditioned on the state rolled forward under the "
                             "previous chunk's pending actions (needs a checkpoint "
                             "fine-tuned with scripts/133_vlash_finetune.py)")
    parser.add_argument("--rtc-delay", type=int, default=None,
                        help="FRUIT_RTC_INFERENCE_DELAY: control steps the sampler is "
                             "spread over (default: --execute-steps)")
    parser.add_argument("--rtc-horizon", type=int, default=None,
                        help="FRUIT_RTC_EXECUTION_HORIZON: soft-inpaint window length")
    parser.add_argument("--rtc-schedule", default=None,
                        choices=["EXP", "LINEAR", "ONES", "ZEROS"],
                        help="FRUIT_RTC_SCHEDULE prefix weight schedule")
    parser.add_argument("--rtc-max-weight", type=float, default=None,
                        help="FRUIT_RTC_MAX_GUIDANCE_WEIGHT: cap on the soft blend")
    parser.add_argument("--rtc-report", action="store_true",
                        help="FRUIT_RTC_REPORT=1: per-episode boundary jumps and "
                             "per-control-step wall time (diagnostic; off for rates)")
    parser.add_argument("--track", action="store_true",
                        help="FRUIT_POLICY_TRACK=1: GEM-style fruit-velocity "
                             "feed-forward added to the policy's arm command "
                             "(default off; changes the control loop)")
    parser.add_argument("--trigger", choices=["off", "arrival", "assist"], default=None,
                        help="FRUIT_POLICY_TRIGGER: encoder-based intercept trigger "
                             "(default off). `arrival` fires the scripted primitive on "
                             "the fruit's predicted arrival at the jaw; `assist` also "
                             "requires the policy's finger near closed")
    parser.add_argument("--trigger-lead", type=float, default=None,
                        help="FRUIT_POLICY_TRIGGER_LEAD: seconds to arrival at fire time")
    parser.add_argument("--trigger-lateral", type=float, default=None,
                        help="FRUIT_POLICY_TRIGGER_LATERAL: max |dx| at fire time [m]")
    parser.add_argument("--trigger-reach", type=float, default=None,
                        help="FRUIT_POLICY_TRIGGER_REACH: max upstream distance [m]")
    parser.add_argument("--trigger-finger", type=float, default=None,
                        help="FRUIT_POLICY_TRIGGER_FINGER: `assist` finger threshold")
    parser.add_argument("--trigger-measured", action="store_true",
                        help="FRUIT_POLICY_TRIGGER_ENCODER=0: use the fruit's measured "
                             "velocity instead of the belt encoder")
    parser.add_argument("--trigger-frame", choices=["station", "jaw"], default=None,
                        help="FRUIT_POLICY_TRIGGER_FRAME: reference the arrival is timed "
                             "against (default station = the jaw at the grasp pose)")
    parser.add_argument("--trigger-present", action="store_true",
                        help="FRUIT_POLICY_TRIGGER_PRESENT=1: also fire on a firable "
                             "fruit the feeder presents at the station when it differs "
                             "from the selected sample (default off)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    install_failure_handler("110_rl_rollout")

    # RTC knobs are environment-driven so the env and its manifest see exactly
    # the same configuration the shell would have set.
    if args.rtc:
        os.environ["FRUIT_RTC"] = "1"
    if args.rtc_no_guidance:
        os.environ["FRUIT_RTC_GUIDANCE"] = "0"
    if args.vlash:
        os.environ["FRUIT_VLASH"] = "1"
    if args.rtc_delay is not None:
        os.environ["FRUIT_RTC_INFERENCE_DELAY"] = str(int(args.rtc_delay))
    if args.rtc_horizon is not None:
        os.environ["FRUIT_RTC_EXECUTION_HORIZON"] = str(int(args.rtc_horizon))
    if args.rtc_schedule is not None:
        os.environ["FRUIT_RTC_SCHEDULE"] = str(args.rtc_schedule)
    if args.rtc_max_weight is not None:
        os.environ["FRUIT_RTC_MAX_GUIDANCE_WEIGHT"] = str(float(args.rtc_max_weight))
    if args.rtc_report:
        os.environ["FRUIT_RTC_REPORT"] = "1"
    if args.track:
        os.environ["FRUIT_POLICY_TRACK"] = "1"
    if args.trigger is not None:
        os.environ["FRUIT_POLICY_TRIGGER"] = str(args.trigger)
    if args.trigger_lead is not None:
        os.environ["FRUIT_POLICY_TRIGGER_LEAD"] = str(float(args.trigger_lead))
    if args.trigger_lateral is not None:
        os.environ["FRUIT_POLICY_TRIGGER_LATERAL"] = str(float(args.trigger_lateral))
    if args.trigger_reach is not None:
        os.environ["FRUIT_POLICY_TRIGGER_REACH"] = str(float(args.trigger_reach))
    if args.trigger_finger is not None:
        os.environ["FRUIT_POLICY_TRIGGER_FINGER"] = str(float(args.trigger_finger))
    if args.trigger_measured:
        os.environ["FRUIT_POLICY_TRIGGER_ENCODER"] = "0"
    if args.trigger_frame is not None:
        os.environ["FRUIT_POLICY_TRIGGER_FRAME"] = str(args.trigger_frame)
    if args.trigger_present:
        os.environ["FRUIT_POLICY_TRIGGER_PRESENT"] = "1"

    seeds = [int(s) for s in str(args.seeds).split(",") if s.strip()]
    if not seeds:
        parser.error("--seeds must list at least one seed")
    reward = RewardConfig(
        time_penalty=float(args.time_penalty), horizon=int(args.horizon)
    )
    dagger = (
        ExpertConfig(tolerance=float(args.expert_tolerance),
                     window_steps=int(args.expert_window))
        if args.dagger else None
    )
    say(
        f"[rl] rollout: presentation={args.presentation} ablate={args.ablate} "
        f"episodes={args.episodes} seeds={seeds} ckpt={args.ckpt} "
        f"execute_steps={args.execute_steps} ddim={args.ddim} "
        f"dagger={dagger} reward={reward} "
        f"rtc={'on' if os.environ.get('FRUIT_RTC', '0') == '1' else 'off'} "
        f"schedule={os.environ.get('FRUIT_RTC_SCHEDULE', 'EXP')} "
        f"delay={os.environ.get('FRUIT_RTC_INFERENCE_DELAY', '0')} "
        f"horizon={os.environ.get('FRUIT_RTC_EXECUTION_HORIZON', '10')} "
        f"guidance={os.environ.get('FRUIT_RTC_GUIDANCE', '1')} "
        f"vlash={'on' if os.environ.get('FRUIT_VLASH', '0') == '1' else 'off'} "
        f"track={'on' if os.environ.get('FRUIT_POLICY_TRACK', '0') == '1' else 'off'} "
        f"event={'on' if os.environ.get('FRUIT_POLICY_EVENT', '0') == '1' else 'off'} "
        f"a2c2={os.environ.get('FRUIT_A2C2', '') or 'off'} "
        f"trigger={os.environ.get('FRUIT_POLICY_TRIGGER', 'off')} "
        f"trigger_present={'on' if os.environ.get('FRUIT_POLICY_TRIGGER_PRESENT', '0') == '1' else 'off'}"
    )

    env = SortingRLEnv(
        presentation=args.presentation,
        seed=seeds[0],
        size_filter=args.size_filter or None,
        ablate=args.ablate,
        checkpoint=args.ckpt,
        record=args.record,
        out_dir=args.out,
        execute_steps=args.execute_steps,
        ddim_steps=args.ddim,
        approach_steps=args.approach_steps,
        reward=reward,
        verbose=args.verbose,
        dagger=dagger,
    )
    if env.manifest_path:
        say(f"[rl] manifest: {env.manifest_path}")
    run_start = time.time()
    say(f"[rl] run wall start {run_start:.3f}")

    totals = []
    dagger_totals = []
    for seed in seeds:
        successes = 0
        episodes = 0
        interventions = 0
        expert_ticks = 0
        agent_ticks = 0
        for episode in range(int(args.episodes)):
            env.reset(seed if episode == 0 else None)
            done = False
            result = None
            while not done:
                chunk = env.sample_chunk()
                result = env.act(chunk, execute_steps=args.execute_steps)
                done = bool(result.done)
            info = result.info if result is not None else {}
            successes += 1 if info.get("success") else 0
            episodes += 1
            interventions += int(info.get("interventions", 0))
            expert_ticks += int(info.get("expert_ticks", 0))
            agent_ticks += int(info.get("decision", 0))
        totals.append((successes, episodes))
        dagger_totals.append((interventions, expert_ticks, agent_ticks))
        say(f"[rl] seed {seed}: {successes}/{episodes} success")

    ok = sum(s for s, _ in totals)
    n = sum(e for _, e in totals)
    run_end = time.time()
    say(
        f"[rl] rollout success {ok}/{n} "
        f"(presentation={args.presentation}, ablate={args.ablate}, seeds={seeds})"
    )
    say(
        f"[rl] run wall end {run_end:.3f} duration {run_end - run_start:.1f}s"
    )
    summary = env.report_summary()
    if summary:
        say(summary)
    if args.dagger:
        intr = sum(i for i, _, _ in dagger_totals)
        expert = sum(e for _, e, _ in dagger_totals)
        agent = sum(a for _, _, a in dagger_totals)
        say(
            f"[rl] dagger takeover: {intr} interventions, expert_ticks {expert}/{agent} "
            f"({(expert / agent if agent else 0.0):.1%} of policy ticks)"
        )
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
