"""Repeat *only* the approach (descent-to-grasp) leg and report its achieved motion.

    FRUIT_APPROACH_STEP=0.08 scripts/run.sh scripts/104_approach_probe.py

Why this exists. The approach leg is the one place where the *achieved* TCP
motion is much rougher than the reference: the jerk-limited reference asks for
0.4 m/s^2, the arm delivers 3.5-7.2 m/s^2, and the residual is the IK tracking
error (WORKLOG, `logs/374`; three-attempt A/B runs in `logs/375/376` were too
noisy to separate a 2x effect from the fruit's position in the workspace).

This probe removes that noise source: it teleports to the calibrated grasp pose
to learn the exact jaw target, hovers above it, then runs the *same*
`PickAndPlaceTask._approach` code path N times on that one point. Same target,
same arm, same reference - the only thing that changes between runs is the knob
under test. It also reports the final position error, so "smoother because it
never arrived" cannot be mistaken for a win.

Environment:
  FRUIT_PROBE_N       descents per arm (default 6)
  FRUIT_PROBE_SIDE    left | right | both (default both)
  FRUIT_PROBE_HOVER   hover height above the grasp point [m] (default 0.07)
  FRUIT_PROBE_JITTER  per-descent target spread [m] (default 0.0; 0.04 is the
                      arrival spread a real fruit has, so an A/B covers the
                      workspace band instead of one lucky point)
  FRUIT_PROBE_SEED    seed for that spread (default 0)
  FRUIT_APPROACH_MODE move_to | cartesian | joint (default: task default)
  FRUIT_APPROACH_STEP IK joint-step cap used on the descent (default 0.08)
  FRUIT_FF_GAIN       velocity feed-forward gain (default 0.0)
  FRUIT_IK_GAIN       differential-IK gain (default 1.0)
"""

from __future__ import annotations

import os
import re
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

HEADLESS = os.environ.get("HEADLESS", "1") == "1"

simulation_app = SimulationApp({"headless": HEADLESS, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
import fruit_sorting.tasks as tasks_mod
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.motion import TrajectoryLimits, jerk_limited
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from fruit_sorting.tasks import PickAndPlaceTask

install_failure_handler("104_approach_probe")

DT = 1.0 / 120.0
N = int(os.environ.get("FRUIT_PROBE_N", "6"))
SIDE = os.environ.get("FRUIT_PROBE_SIDE", "both")
HOVER = float(os.environ.get("FRUIT_PROBE_HOVER", "0.07"))
JITTER = float(os.environ.get("FRUIT_PROBE_JITTER", "0.0"))
PROBE_SEED = int(os.environ.get("FRUIT_PROBE_SEED", "0"))

#: `MotionMonitor.format` line emitted by the task, e.g.
#: "approach(cartesian): 7.2 cm, 278 samples: steps=278, |v|max=..., |a|max=...,
#:  |j|max=..., ends |v|=.../... m/s (a_step=0.40)"
LINE = re.compile(
    r"approach\((\w+)\).*?\|v\|max=([\d.]+) m/s, \|a\|max=([\d.]+) m/s\^2, "
    r"\|j\|max=([\d.]+) m/s\^3.*?a_step=([\d.]+)"
)

_captured: list[str] = []
_real_say = tasks_mod.say


def _spy(msg) -> None:
    _captured.append(str(msg))
    _real_say(msg)


def _settle_to_rest(
    task, arm, min_ticks: int = 40, max_ticks: int = 1200, eps: float = 0.002
) -> tuple[int, float]:
    """Step until the TCP is *at rest*, not just once a fixed count has passed.

    `move_to` returns the moment the position error is inside tolerance, which
    leaves the arm mid-motion. Starting the descent from a moving arm puts the
    previous leg's deceleration into the descent's first ticks, which is exactly
    where the measured acceleration peak sits.
    """
    previous = np.asarray(arm.tcp_position(), dtype=float)
    calm = 0
    speed = float("inf")
    for i in range(max_ticks):
        task._step_sim(1)
        current = np.asarray(arm.tcp_position(), dtype=float)
        speed = float(np.linalg.norm(current - previous)) / DT
        previous = current
        if i >= min_ticks and speed < eps:
            calm += 1
            if calm >= 5:
                return i + 1, speed
        else:
            calm = 0
    return max_ticks, speed


def _profile(trace: list[np.ndarray], start, tcp_target) -> dict:
    """Where inside the leg the achieved acceleration peaks.

    The reference is smooth by construction, so "achieved |a|max" alone cannot
    say whether the arm lurches at the *start* of the descent (servo start-up),
    in the *middle* (steady-state tracking), or at the *end* (the pads meeting
    the fruit). Regenerating the reference here puts both in the same frame.
    """
    if len(trace) < 4:
        return {}
    points = np.asarray(trace, dtype=float)
    vel = np.diff(points, axis=0) / DT
    acc = np.diff(vel, axis=0) / DT
    magnitude = np.linalg.norm(acc, axis=1)
    n = len(magnitude)
    window = max(1, n // 10)
    delta = np.asarray(tcp_target, dtype=float) - np.asarray(start, dtype=float)
    limits = TrajectoryLimits.from_env(DT)
    limits.v_max = float(os.environ.get("FRUIT_APPROACH_VMAX", "0.06"))
    limits.a_max = float(os.environ.get("FRUIT_APPROACH_AMAX", "0.4"))
    ref_pos, ref_vel, ref_acc = jerk_limited(float(np.linalg.norm(delta)), limits)
    # The *speed* ratio is the number the shipped gate budgets: an achieved peak
    # above the commanded peak means something moved the hand, and the acceptance
    # run's one bad leg sits at 1.43x (logs/153) against 0.15-0.85 for every clean
    # leg. Reporting both here answers "does that overshoot need the line, or is it
    # in the servo" - this cell has no fruit on the belt at all.
    own_vmax = float(np.linalg.norm(vel, axis=1).max())
    ref_vmax = float(np.abs(ref_vel).max()) if len(ref_vel) else 0.0
    return {
        "ref_a": float(np.abs(ref_acc).max()) if len(ref_acc) else 0.0,
        "ref_v": ref_vmax,
        "v_ratio": own_vmax / ref_vmax if ref_vmax > 0 else float("nan"),
        "ref_steps": float(len(ref_pos)),
        "own_a": float(magnitude.max()),
        "own_steps": float(n),
        "own_vmax": own_vmax,
        "peak_at": float(int(np.argmax(magnitude)) + 1) / float(n),
        "a_first10": float(magnitude[:window].max()),
        "a_last10": float(magnitude[-window:].max()),
        "a_med": float(np.median(magnitude)),
    }


def _run_arm(task, name: str, offsets: list[np.ndarray]) -> list[dict]:
    arm = task.arms[name]
    # The calibrated grasp pose *is* the target, so the probe inherits the real
    # reachability and geometry of the cell rather than an invented point.
    ready = task._pose(name, "ready")
    grasp = task._pose(name, "grasp")
    arm.teleport_joints(grasp)
    for _ in range(30):
        task._step_sim(1)
    jaw_target = np.asarray(arm.jaw_centre(), dtype=float).copy()
    say(f"[probe] {name}: grasp jaw centre {np.round(jaw_target, 4).tolist()}")

    arm.teleport_joints(ready)
    for _ in range(30):
        task._step_sim(1)

    rows: list[dict] = []
    for i in range(N):
        # The descent target is the calibrated grasp point plus a deterministic
        # offset, so the A/B samples the band a real fruit actually arrives in
        # (arrival error is -6..+27 mm, logs/259). Both arms see the same offsets.
        target = jaw_target + offsets[i]
        # Return to the hover point with the normal servo, then hand the descent
        # to the task's own `_approach` so nothing about the leg is re-implemented.
        arm.max_step = float(os.environ.get("FRUIT_HOVER_STEP", "0.20"))
        arm.move_to(arm.tcp_target_for_jaw(target + np.array([0.0, 0.0, HOVER])),
                    max_steps=900, tolerance=0.006)
        if os.environ.get("FRUIT_PROBE_REST", "1") == "1":
            settle_ticks, start_speed = _settle_to_rest(
                task, arm, min_ticks=int(os.environ.get("FRUIT_PROBE_MIN_SETTLE", "40"))
            )
        else:
            for _ in range(40):
                task._step_sim(1)
            settle_ticks, start_speed = 40, float("nan")
        arm.max_step = float(os.environ.get("FRUIT_APPROACH_STEP", "0.08"))
        _captured.clear()
        # Record the *achieved* TCP once per control tick so the peak can be
        # located inside the leg, not just reported as a maximum.
        trace: list[np.ndarray] = []
        original_step = task._step_sim

        def traced_step(steps: int = 1, _arm=arm, _trace=trace, _inner=original_step):
            _inner(steps)
            _trace.append(np.asarray(_arm.tcp_position(), dtype=float))

        # The IK's own joint command per tick: the achieved lurch has to come
        # from a large first `dq`, and only the integrator knows whether it did.
        ik_log: list[tuple[float, float]] = []
        original_ik = arm.ik_step

        def traced_ik(target_pose, target_velocity=None, _arm=arm, _log=ik_log,
                      _inner=original_ik):
            before = None if _arm._q_cmd is None else np.array(_arm._q_cmd, dtype=float)
            residual = _inner(target_pose, target_velocity)
            after = np.array(_arm._q_cmd, dtype=float)
            step = float(np.linalg.norm(after - before)) if before is not None else float("nan")
            _log.append((step, float(residual)))
            return residual

        arm.ik_step = traced_ik
        start_of_leg = np.asarray(arm.tcp_position(), dtype=float).copy()
        tcp_toward_target = np.asarray(arm.tcp_target_for_jaw(target), dtype=float)
        task._step_sim = traced_step
        task._approach(arm, target, verbose=False)
        task._step_sim = original_step
        arm.ik_step = original_ik
        for _ in range(30):
            task._step_sim(1)
        error = float(np.linalg.norm(np.asarray(arm.jaw_centre(), dtype=float) - target))
        match = None
        for line in _captured:
            found = LINE.search(line)
            if found is not None:
                match = found
        if match is None:
            say(f"[probe] {name} descent {i}: no metric line captured")
            continue
        row = {
            "arm": name,
            "i": i,
            "mode": match.group(1),
            "v": float(match.group(2)),
            "a": float(match.group(3)),
            "j": float(match.group(4)),
            "a_step": float(match.group(5)),
            "err_mm": error * 1000.0,
            "offset_mm": (offsets[i] * 1000.0).tolist(),
        }
        row.update(_profile(trace, start_of_leg, tcp_toward_target))
        row["start_speed"] = start_speed
        row["settle_ticks"] = settle_ticks
        if os.environ.get("FRUIT_PROBE_HEAD", "0") == "1" and i == 0:
            points = np.asarray(trace, dtype=float)
            vel = np.diff(points, axis=0) / DT
            acc = np.diff(vel, axis=0) / DT
            head = min(20, len(acc))
            say(f"[probe] {name} descent {i} head (tick, |v| [m/s], |a| [m/s^2]):")
            for k in range(head):
                say(
                    f"[probe]   {k + 1:3d}  {np.linalg.norm(vel[k]):.5f}  "
                    f"{np.linalg.norm(acc[k]):.3f}"
                    + (
                        f"  |dq|={ik_log[k][0]:.5f} rad  residual={ik_log[k][1] * 1000:.2f} mm"
                        if k < len(ik_log)
                        else ""
                    )
                )
        rows.append(row)
        say(
            f"[probe] {name} descent {i}: |v|max={row['v']:.3f} m/s "
            f"|a|max={row['a']:.3f} m/s^2 |j|max={row['j']:.1f} m/s^3 "
            f"a_step={row['a_step']:.2f} residual={row['err_mm']:.1f} mm "
            f"peak@{row.get('peak_at', float('nan')):.2f} first10={row.get('a_first10', 0.0):.2f} "
            f"last10={row.get('a_last10', 0.0):.2f} med={row.get('a_med', 0.0):.2f} "
            f"ref={row.get('ref_a', 0.0):.2f} m/s^2 "
            f"start|v|={start_speed:.4f} m/s settle={settle_ticks} "
            f"own_a={row.get('own_a', 0.0):.2f} own_n={int(row.get('own_steps', 0))} "
            f"ref_n={int(row.get('ref_steps', 0))} "
            f"v={row.get('own_vmax', 0.0):.4f}/ref {row.get('ref_v', 0.0):.4f} "
            f"v_ratio={row.get('v_ratio', float('nan')):.2f}"
        )
    return rows


def main() -> int:
    # The task's monitor (and therefore the metric line this probe parses) is
    # created only when the report flag is on; the probe is useless without it.
    os.environ["FRUIT_MOTION_REPORT"] = "1"
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()

    task = PickAndPlaceTask(scene, spawner, tactile, cfg)
    tasks_mod.say = _spy
    task.go_ready()
    for _ in range(30):
        task._step_sim(1)

    sides = ["left", "right"] if SIDE == "both" else [SIDE]
    rng = np.random.default_rng(PROBE_SEED)
    offsets = [
        np.array([rng.uniform(-JITTER, JITTER), rng.uniform(-JITTER, JITTER), 0.0])
        for _ in range(N)
    ]
    say(
        f"[probe] mode={os.environ.get('FRUIT_APPROACH_MODE', 'cartesian')} "
        f"step={os.environ.get('FRUIT_APPROACH_STEP', '0.08')} "
        f"ff={os.environ.get('FRUIT_FF_GAIN', '0.0')} "
        f"ik_gain={os.environ.get('FRUIT_IK_GAIN', '1.0')} "
        f"vmax={os.environ.get('FRUIT_APPROACH_VMAX', '0.06')} "
        f"amax={os.environ.get('FRUIT_APPROACH_AMAX', '0.4')} n={N} sides={sides} "
        f"jitter={JITTER} seed={PROBE_SEED}"
    )

    rows: list[dict] = []
    for name in sides:
        rows.extend(_run_arm(task, name, offsets))

    if not rows:
        say("[probe] no samples")
        return 1
    say("[probe] ---- aggregate (achieved TCP motion over the approach leg) ----")
    for name in sides:
        subset = [r for r in rows if r["arm"] == name]
        if not subset:
            continue
        ratios = [r["v_ratio"] for r in subset if r.get("v_ratio") == r.get("v_ratio")]
        say(
            f"[probe] {name}: n={len(subset)} "
            f"v_ratio med={statistics.median(ratios):.2f} worst={max(ratios):.2f} "
            f"(>1 count={sum(1 for r in ratios if r > 1.0)}) | "
            f"|a|max med={statistics.median(r['a'] for r in subset):.2f} "
            f"worst={max(r['a'] for r in subset):.2f} m/s^2 | "
            f"|j|max med={statistics.median(r['j'] for r in subset):.0f} "
            f"worst={max(r['j'] for r in subset):.0f} m/s^3 | "
            f"a_step med={statistics.median(r['a_step'] for r in subset):.2f} "
            f"worst={max(r['a_step'] for r in subset):.2f} m/s^2 | "
            f"residual med={statistics.median(r['err_mm'] for r in subset):.1f} "
            f"worst={max(r['err_mm'] for r in subset):.1f} mm"
        )
    all_ratios = [r["v_ratio"] for r in rows if r.get("v_ratio") == r.get("v_ratio")]
    say(
        f"[probe] all: v_ratio med={statistics.median(all_ratios):.2f} "
        f"worst={max(all_ratios):.2f} "
        f"(>1 count={sum(1 for r in all_ratios if r > 1.0)}/{len(all_ratios)})"
    )
    say(
        f"[probe] all: n={len(rows)} "
        f"|a|max med={statistics.median(r['a'] for r in rows):.2f} "
        f"worst={max(r['a'] for r in rows):.2f} m/s^2 | "
        f"residual med={statistics.median(r['err_mm'] for r in rows):.1f} "
        f"worst={max(r['err_mm'] for r in rows):.1f} mm"
    )
    say("[probe] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
