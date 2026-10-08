"""Run scripted pick-and-place attempts on the moving belt.

    scripts/run.sh scripts/20_pick_place.py

`scripts/run.sh` raises the file-descriptor limit before starting Isaac Sim; without
that this build dies about 40 s into the first camera read (`dup failed ... Too many
open files`, then a wedged crash reporter and a frozen window). Launching
`$ISAAC_SIM_DIR/python.sh` directly also works now - `fruit_sorting.fdlimit` raises
the limit in-process - but the wrapper is the supported path.
"""

from __future__ import annotations

import os
import sys

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

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, look_at_quat, say
from fruit_sorting.dataset import EpisodeRecorder
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from fruit_sorting.slow_loop import ExperienceMemory, SlowLoopAgent
from fruit_sorting.tasks import PickAndPlaceTask
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

install_failure_handler("20_pick_place")

DT = 1.0 / 120.0
ATTEMPTS = int(os.environ.get("ATTEMPTS", "4"))


def main() -> int:
    from isaacsim.core.simulation_manager import SimulationManager

    # `app_utils.update_app(steps=N)` is not a fixed advance: with the app timeline
    # running, Kit moves physics by elapsed wall-clock time, and `assets.py` already
    # notes that one call can advance "several hundred milliseconds". Measured here:
    # sixty `update_app(steps=1)` calls consumed 118 ticks on one run and 120 on the
    # next, which moved the feed/index clock, put the fruit 2 mm further along, and
    # sent the whole run down a different branch (WORKLOG "the run is not
    # reproducible"). `FRUIT_FIXED_STEPPING=1` routes every such advance through
    # `SimulationManager.step`, the tick-exact API the control loop already uses.
    # Default **on**: this is what makes the run reproducible. Measured before the
    # change: sixty `update_app(steps=1)` calls consumed 118 ticks on one run and 120
    # on the next, the feed/index clock moved by two ticks, the fruit stopped 2 mm
    # further along, and the whole run followed a different branch. With tick-exact
    # stepping: five single-attempt probes identical, and two ten-attempt acceptance
    # runs bit-identical in every statistic and every per-leg metric
    # (`logs/127/128`). Set `FRUIT_FIXED_STEPPING=0` to reproduce the older,
    # non-deterministic behaviour (WORKLOG "the run is not reproducible").
    fixed_stepping = os.environ.get(
        "FRUIT_FIXED_STEPPING", os.environ.get("FRUIT_FIXED_PRELOOP", "1")
    ) == "1"

    def advance(steps: int) -> None:
        if fixed_stepping:
            # Physics tick-exact, plus a pump-only update so the camera/sensor
            # callbacks still run (`update_app` does both jobs; `SimulationManager.step`
            # only advances physics, and dropping the pump entirely starves the
            # sensors - it crashed the evaluator, WORKLOG).
            SimulationManager.step(steps=steps)
            app_utils.update_app(steps=0)
        else:
            app_utils.update_app(steps=steps)

    cfg = SceneConfig()
    scene = SortingScene(cfg).build()

    capture = os.environ.get("FRUIT_CAPTURE", "0") == "1"
    if capture:
        eye = (1.75, 1.55, 2.35)
        observer = RtxCamera(
            "/World/ObserverCamera",
            tick_rate=30.0,
            positions=[eye],
            orientations=[look_at_quat(eye, (0.34, 0.0, 1.12))],
        )
        observer.camera.set_focal_lengths(0.016)
        observer.camera.set_apertures((0.036, 0.02025))
        observer.camera.set_clipping_ranges(0.01, 50.0)
        observer_sensor = CameraSensor(observer, resolution=(600, 1000), annotators=["rgb"])

    tactile = GripperTactile()
    # Attach before play() so the contact views are valid.
    tactile.attach(stage=scene.stage)

    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    advance(30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    spawner.prime(count=4)

    task = PickAndPlaceTask(scene, spawner, tactile, cfg)
    task.go_ready()
    say(f"arms ready; belt top z={task.belt_top:.3f}")

    from isaacsim.core.simulation_manager import SimulationManager

    TIME_AT_START = float(SimulationManager.get_simulation_time())
    if os.environ.get("FRUIT_TIME_DEBUG", "0") == "1":
        say(f"[time] clock at start of the attempt loop: t={TIME_AT_START:.6f}")

    # `FRUIT_RECORD=1` attaches the same recorder the demo collector uses, so the
    # scripted pipeline can be run with and without it at one seed. That is the
    # only way to ask whether the recorder's per-tick observation - a fruit pose
    # read plus a camera frame - changes the transport the episodes are recorded
    # in (see the WORKLOG entry "reading the line every tick changes the line").
    if os.environ.get("FRUIT_RECORD", "0") == "1":
        record_dir = os.environ.get("FRUIT_RECORD_DIR", "logs/record_probe")
        task.recorder = EpisodeRecorder(record_dir, decimation=4)
        say(f"[run] recorder attached -> {record_dir}")

    results = []
    # Slow loop (design doc section 4): structured state -> experience memory ->
    # structured Manipulation Goal. Opt-in; the built-in selector stays the default.
    use_agent = os.environ.get("FRUIT_SLOW_LOOP", "0") == "1"
    agent = None
    if use_agent:
        memory = ExperienceMemory(os.environ.get("FRUIT_MEMORY", "logs/experience.jsonl"))
        agent = SlowLoopAgent(cfg, memory)
        say(f"[agent] slow loop enabled, policy={agent.policy}, memory={memory.summary()}")
    # F2 pipelined bimanual line (FRUIT_BIARM=1): the whole batch runs in one
    # session; both arms keep taking station slots until ATTEMPTS attempts are
    # done (each arm selects its own fruit after acquiring the station). The
    # per-iteration driver loop below is the single-arm path.
    bimanual_batch = agent is None and task.bimanual_enabled()
    if bimanual_batch:
        made = task.run_bimanual(ATTEMPTS)
        results.extend(made)
        for index, result in enumerate(made):
            bin_index = 0 if result.arm == "left" else 1
            lane_xy = cfg.output_belt_drop_points[bin_index]
            say(
                f"[run] attempt {index} ({result.arm}): picking {result.category} "
                f"grade {result.grade} into output lane {bin_index} at {lane_xy} "
                f"sim={result.sim_start:.1f}-{result.sim_end:.1f}s"
            )
            say(
                f"[run] attempt {index} ({result.arm}): grasped={result.grasped} "
                f"placed={result.placed} lift={result.peak_lift:+.3f} m "
                f"force={result.max_tactile_force:.2f} N sim={result.sim_span:.1f}s "
                f"notes={result.notes}"
            )
        task.go_ready()
        advance(30)

    for attempt in range(ATTEMPTS):
        if bimanual_batch:
            continue
        for _ in range(60):
            advance(1)
            spawner.update(__import__("isaacsim.core.simulation_manager", fromlist=["SimulationManager"]).SimulationManager.get_simulation_time())
        if os.environ.get("FRUIT_TIME_DEBUG", "0") == "1":
            # Is the physics clock advancing by exactly what the code asks for?
            # The run's outcome depends on where the fruit stops, which is set by the
            # feed/index ticks, so a variable number of ticks per app update would
            # explain the run-to-run branches (WORKLOG "the run is not
            # reproducible"). This prints the clock either side of the 60-step
            # advance and the per-step delta it implies.
            from isaacsim.core.simulation_manager import SimulationManager as _SM

            now = _SM.get_simulation_time()
            say(
                f"[time] after 60 update_app steps: t={now:.6f} "
                f"(delta since run start {now - TIME_AT_START:.6f}s, "
                f"{(now - TIME_AT_START) / DT:.2f} ticks at dt={DT:.6f})"
            )
        states = spawner.state()
        goal = None
        if agent is not None:
            sim_time = __import__("isaacsim.core.simulation_manager", fromlist=["SimulationManager"]).SimulationManager.get_simulation_time()
            # The encoder, not the command: the planner's velocity prior for a
            # fruit riding the belt is the belt's measured travel (`方案 3` in the
            # design notes).
            goal = agent.decide(
                states,
                sim_time,
                spawner.belt.encoder_speed if spawner.belt else cfg.belt_speed,
            )
            if goal is not None:
                state = next((s for s in states if int(s["index"]) == goal.index), None)
                if state is not None:
                    target = state
                    say(
                        f"[agent] goal: index={goal.index} {goal.category} grade={goal.grade} "
                        f"bin={goal.bin_index} skill={goal.skill} force<={goal.force_limit_n:.0f}N "
                        f"approach={goal.approach} conf={goal.confidence:.2f} why=[{goal.rationale}]"
                    )
                else:
                    target = None
            else:
                target = None
        else:
            target = task.select_target(states)
        if target is None:
            summary = [
                (s["category"], round(float(s["position"][1]), 3), round(s["diameter"], 3))
                for s in states
            ]
            say(f"[run] attempt {attempt}: no eligible fruit; active={summary} stats={spawner.stats}")
            continue
        grade = target["grade"]
        bin_index = 0 if grade == "A" else 1
        lane_xy = cfg.output_belt_drop_points[bin_index]
        say(
            f"[run] attempt {attempt}: picking {target['category']} grade {grade} "
            f"into output lane {bin_index} at {lane_xy}"
        )
        started = __import__("time").time()
        if task.recorder is not None:
            os.environ["FRUIT_EPISODE_INDEX"] = str(attempt)
        result = task.run(target, bin_index)
        results.append(result)
        if agent is not None and goal is not None:
            agent.arm_counts[result.arm] = agent.arm_counts.get(result.arm, 0) + 1
            sample = next((s for s in spawner.samples if s.index == goal.index), None)
            agent.memory.remember(
                goal, success=result.success, arm=result.arm, notes=result.notes,
                cycle_s=__import__("time").time() - started,
                diameter=float(sample.diameter) if sample else 0.0,
            )
            agent.record_outcome(
                success=result.success, arm=result.arm, notes=result.notes,
                cycle_s=__import__("time").time() - started,
            )
        say(
            f"[run] attempt {attempt}: grasped={result.grasped} placed={result.placed} "
            f"lift={result.peak_lift:+.3f} m force={result.max_tactile_force:.2f} N "
            f"notes={result.notes}"
        )
        task.go_ready()
        advance(30)

    if capture:
        for tag, sensor in (("observer", observer_sensor), ("head", scene.camera_sensor)):
            data = sensor.get_data("rgb")
            if data is None:
                continue
            arr = np.asarray(data[0].numpy() if hasattr(data, "__getitem__") else data)
            from PIL import Image

            path = f"logs/pick_{tag}.png"
            Image.fromarray(arr[..., :3].astype(np.uint8)).save(path)
            say(f"saved {path}")

    say(task.stats_line())
    if agent is not None:
        say(f"[agent] {agent.summary()}")
    pairs = int(task.stats.get("biarm_sessions", 0))
    if pairs:
        # Throughput of the pipelined line: fruits per simulated minute and the
        # per-fruit time, against the F1 single-arm dynamic line's 18.4 s/attempt.
        per_arm = {"left": [0, 0], "right": [0, 0]}
        for result in results:
            slot = per_arm.setdefault(result.arm, [0, 0])
            slot[0] += 1
            slot[1] += int(result.success)
        attempts_n = max(1, int(task.stats["attempts"]))
        span = float(task.stats["sim_time"])
        say(
            f"[biarm] {pairs} pipelined slots, {attempts_n} attempts, "
            f"{int(task.stats['successes'])} successes, {span:.1f}s sim span, "
            f"{span / attempts_n:.1f}s/attempt, {span / max(1, int(task.stats['successes'])):.1f}s/success, "
            f"{int(task.stats['successes']) / max(span, 1e-9) * 60.0:.2f} fruits/min; "
            f"per arm left={per_arm['left'][1]}/{per_arm['left'][0]} "
            f"right={per_arm['right'][1]}/{per_arm['right'][0]}"
        )
    if results:
        successes = sum(1 for r in results if r.success)
        say(f"[run] summary: {successes}/{len(results)} successful")
    for r in results:
        say(
            f"[run]   {r.category:10s} arm={r.arm:5s} grasped={r.grasped} placed={r.placed} "
            f"lift={r.peak_lift:+.3f} N={r.max_tactile_force:.2f} sim={r.sim_span:.1f}s"
        )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
