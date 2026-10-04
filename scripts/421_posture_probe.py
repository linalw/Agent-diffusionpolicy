"""Posture-quality probe: per-tick joint continuity, wrist attitude, IK branch.

Usage
-----
    # Record the stream while driving the *shipped* flow (needs Isaac Sim), then
    # analyze it and print the report:
    ATTEMPTS=5 scripts/run.sh scripts/421_posture_probe.py > logs/461_posture.log 2>&1

    # Re-analyze a recorded stream, offline (no Isaac Sim):
    python3 scripts/421_posture_probe.py --analyze logs/461_posture/stream.jsonl
    python3 scripts/421_posture_probe.py --self-test

    # Control for the "ready pose is never reached" finding below: one-shot
    # reads only (no per-tick hooks), drive to ready, then hold and watch.
    FRUIT_POSTURE_MODE=transit scripts/run.sh scripts/421_posture_probe.py

Why this exists
---------------
The user reports that the arm "uses weird postures" and that the motion is not
human-like, and there is no number for posture quality anywhere in the tree.
This probe supplies one. What it measures, per attempt and per leg:

  * joint-space continuity: max per-tick |q[t+1]-q[t]| over each of the 7 arm
    joints, measured and commanded, with the joint and the tick where it occurs,
    plus the command jump across leg boundaries (a deliberate `teleport_joints`
    is reported as an event, not silently averaged into the step statistics);
  * wrist attitude: the tool axis (from the TCP quaternion plus the arm's
    measured TCP->jaw geometry, captured once at attach) and its per-tick
    angular change; flags a sign flip (>90 deg between consecutive ticks) and
    > 1 rad in one tick;
  * elbow/shoulder branch: sign of joints 3 and 5 relative to the calibrated
    ready seed for every attempt, whether the attempt crosses its own seed
    plane, and whether the branch changes between attempts of the same arm
    ("reconfigured");
  * a compact verdict line per attempt and a summary with the worst offenders.

Read class (AGENTS.md section 2). The stock `FRUIT_MOTION_REPORT=1` log carries
only Cartesian leg summaries (|v|, |a|, ...), and `FRUIT_APPROACH_TRACE=1`
carries per-tick joints only for descents - checked before writing this script,
so no existing log has the joint stream the probe needs. The probe therefore
records it itself, using reads of the articulation's DOF state (measured joint
positions and drive position targets) plus the TCP link world pose. The shipped
control loop already reads DOF state every `ik_step`, so this is the same class
of read; but it is an extra per-tick read around the articulation, which
AGENTS.md measured can move the scripted run into another attractor. Treat a
recording as an *instrumented branch* and its numbers as per-leg mechanism
measurements, not as a success-rate claim. The stream is written to JSONL so
the analysis can be re-run without the simulator.

Instrumentation is installed by monkey-patching the task/controller methods at
runtime from this script - `src/` is not edited. Hooks used: task `run`,
`go_ready`, `_transit_to`, `_approach`, `_carry`, `grasp_carry_place`, and
`SimulationManager.step` plus the arm's `teleport_joints` /
`_jump_to_random_pose`, so every physics advance during a run is attributed to
an attempt, an arm and a leg.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime

import numpy as np

#: Per-tick thresholds (rad/tick unless noted). Measured joint steps above
#: `WARN_STEP` are "noticeable", above `FLAG_STEP` are "lurch" level; the
#: commanded stream is held to tighter numbers because it is the reference.
WARN_STEP = float(os.environ.get("FRUIT_POSTURE_STEP_WARN", "0.10"))
FLAG_STEP = float(os.environ.get("FRUIT_POSTURE_STEP_FLAG", "0.30"))
WARN_CMD = float(os.environ.get("FRUIT_POSTURE_CMD_WARN", "0.05"))
FLAG_CMD = float(os.environ.get("FRUIT_POSTURE_CMD_FLAG", "0.15"))
WARN_WRIST = float(os.environ.get("FRUIT_POSTURE_WRIST_WARN", "0.20"))
FLAG_WRIST = float(os.environ.get("FRUIT_POSTURE_WRIST_FLAG", "1.0"))
#: Tool attitude: below `TILT_WARN` the tool is "roughly down"; a flagged leg at
#: > `FLAG_TILT` is pointing more sideways/up than down.
TILT_WARN = float(os.environ.get("FRUIT_POSTURE_TILT_WARN", "45.0"))
FLAG_TILT = float(os.environ.get("FRUIT_POSTURE_TILT_FLAG", "90.0"))
#: A joint's deviation from the seed is only counted as a branch sign if it is
#: farther than this; inside the band the sign is "0" (near the seed plane).
SIGN_DEADBAND = float(os.environ.get("FRUIT_POSTURE_SIGN_DEADBAND", "0.08"))

DEFAULT_DIR = os.environ.get("FRUIT_POSTURE_DIR", "logs/461_posture")
CONTROL_DT = 1.0 / 120.0

#: Joints the user names for the branch test (1-based, as the log prints them).
BRANCH_JOINTS = (3, 5)


# --------------------------------------------------------------------------- #
# quaternion helpers
# --------------------------------------------------------------------------- #
def quat_matrix(q) -> np.ndarray:
    """Rotation matrix from a (w, x, y, z) quaternion (normalized here)."""
    w, x, y, z = (float(v) for v in q)
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def quat_matrices(quats) -> np.ndarray:
    """Rotation matrices for N quaternions -> (N, 3, 3)."""
    qs = np.asarray(quats, dtype=float)
    n = np.linalg.norm(qs, axis=1, keepdims=True)
    qs = qs / np.where(n > 0.0, n, 1.0)
    w, x, y, z = qs[:, 0], qs[:, 1], qs[:, 2], qs[:, 3]
    out = np.empty((len(qs), 3, 3), dtype=float)
    out[:, 0, 0] = 1 - 2 * (y * y + z * z)
    out[:, 0, 1] = 2 * (x * y - z * w)
    out[:, 0, 2] = 2 * (x * z + y * w)
    out[:, 1, 0] = 2 * (x * y + z * w)
    out[:, 1, 1] = 1 - 2 * (x * x + z * z)
    out[:, 1, 2] = 2 * (y * z - x * w)
    out[:, 2, 0] = 2 * (x * z - y * w)
    out[:, 2, 1] = 2 * (y * z + x * w)
    out[:, 2, 2] = 1 - 2 * (x * x + y * y)
    return out


def quat_angle(q1, q2) -> float:
    """Geodesic angle [rad] between two orientations (double cover handled)."""
    d = abs(float(np.dot(np.asarray(q1, float), np.asarray(q2, float))))
    return 2.0 * math.acos(min(1.0, max(-1.0, d)))


# --------------------------------------------------------------------------- #
# recording (runs inside Isaac Sim)
# --------------------------------------------------------------------------- #
class JointStreamRecorder:
    """Accumulates one JSONL row per physics advance during a scripted attempt.

    Rows are buffered and flushed when an attempt ends, so a crash late in the
    run still leaves the completed attempts on disk. The recorder is attached
    by the `PickAndPlaceTask.__init__` hook below; every other hook is a small
    reporting-only wrapper around a script method and touches no `src/` file.
    """

    def __init__(self, path: str, meta: dict):
        self.path = path
        self.meta = meta
        self.rows: list[dict] = []
        self.attempt = -1
        self.leg = "idle"
        self.arm_override: str | None = None
        self.task = None
        self.arms: dict = {}
        self.t = 0
        self._fh = None
        self._header_written = False

    # -- stream plumbing ------------------------------------------------ #
    def open(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._fh = open(self.path, "w", encoding="utf-8")

    def close(self) -> None:
        self.flush()
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def flush(self) -> None:
        if self._fh is None:
            return
        if not self._header_written:
            # The header carries geometry measured in `attach`, which runs after
            # the stream file is opened, so it is written on the first flush.
            self._fh.write(json.dumps({"kind": "header", **self.meta}) + "\n")
            self._header_written = True
        for row in self.rows:
            self._fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        self.rows.clear()
        self._fh.flush()

    def _row(self, **row) -> None:
        self.rows.append(row)

    # -- hooks ---------------------------------------------------------- #
    def attach(self, task) -> None:
        self.task = task
        self.arms = dict(task.arms)
        for side, arm in self.arms.items():
            self.meta["joint_names"][side] = list(arm.spec.arm_joint_names)
            try:
                self.meta["ready"][side] = [float(v) for v in task._pose(side, "ready")]
            except Exception:  # noqa: BLE001 - missing waypoint file entry
                self.meta["ready"][side] = None
            self._wrap_arm(side, arm)
            self._capture_tool_geometry(side, arm)

    def _capture_tool_geometry(self, side: str, arm) -> None:
        """Tool axis and closing axis in the TCP frame, measured once.

        `approach_axis` points from the jaw centre towards the TCP (down the
        fingers); recording it in the TCP frame lets the offline analysis
        rebuild the world tool axis from the quaternion alone.
        """
        try:
            pos, quat = arm.tcp_pose()
            rot = quat_matrix(quat)
            left, right = (np.asarray(p, dtype=float) for p in arm.jaw_positions())
            jaw = (left + right) / 2.0
            axis = np.asarray(pos, dtype=float) - jaw
            axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
            closing = right - left
            closing = closing / max(float(np.linalg.norm(closing)), 1e-9)
            self.meta["tool_local"][side] = [float(v) for v in rot.T @ axis]
            self.meta["close_local"][side] = [float(v) for v in rot.T @ closing]
        except Exception:  # noqa: BLE001 - analysis falls back to quat-only
            self.meta["tool_local"][side] = None
            self.meta["close_local"][side] = None

    def _wrap_arm(self, side: str, arm) -> None:
        recorder = self

        orig_teleport = arm.teleport_joints

        def teleport(config, settle=30, _side=side, _orig=orig_teleport):
            before = arm.joint_positions()
            _orig(config, settle)
            recorder.teleport_event(_side, "teleport_joints", before, arm.joint_positions())

        arm.teleport_joints = teleport  # type: ignore[method-assign]

        orig_jump = getattr(arm, "_jump_to_random_pose", None)
        if orig_jump is not None:

            def jump(rng, _side=side, _orig=orig_jump):
                before = arm.joint_positions()
                _orig(rng)
                recorder.teleport_event(
                    _side, "jump_to_random_pose", before, arm.joint_positions()
                )

            arm._jump_to_random_pose = jump  # type: ignore[method-assign]

    # -- leg/attempt bookkeeping --------------------------------------- #
    def _arm(self) -> str | None:
        if self.arm_override is not None:
            return self.arm_override
        return getattr(self.task, "current_arm", None)

    def set_leg(self, leg: str, arm: str | None = None) -> None:
        if arm is not None:
            self.arm_override = arm
        if leg == self.leg:
            return
        self.leg = leg
        self._row(
            kind="leg", t=self.t, attempt=self.attempt, arm=self._arm(), leg=leg
        )

    def begin_attempt(self) -> None:
        self.attempt += 1
        self.arm_override = None
        self.set_leg("prepose")

    def end_attempt(self) -> None:
        self.set_leg("idle")
        self.flush()

    def teleport_event(self, side: str, label: str, before, after) -> None:
        self._row(
            kind="teleport",
            t=self.t,
            attempt=self.attempt,
            arm=side,
            leg=self.leg,
            label=label,
            q_before=[float(v) for v in before],
            q_after=[float(v) for v in after],
        )

    # -- per-tick read -------------------------------------------------- #
    def on_step(self, steps: int) -> None:
        if self.task is None or self.leg == "idle":
            return
        side = self._arm()
        arm = self.arms.get(side)
        if arm is None:
            return
        self.t += int(steps)
        try:
            q = arm.joint_positions()
        except Exception:  # noqa: BLE001
            return
        row = {
            "kind": "tick",
            "t": self.t,
            "attempt": self.attempt,
            "arm": side,
            "leg": self.leg,
            "q": [float(v) for v in q],
        }
        try:
            targets = arm.robot.get_dof_position_targets()
            if hasattr(targets, "numpy"):
                targets = targets.numpy()
            row["qcmd"] = [
                float(v) for v in np.asarray(targets, dtype=float)[0][arm.arm_dofs]
            ]
        except Exception:  # noqa: BLE001
            row["qcmd"] = None
        try:
            _, quat = arm.tcp_pose()
            row["quat"] = [float(v) for v in quat]
        except Exception:  # noqa: BLE001
            row["quat"] = None
        self._row(**row)


def _install_task_hooks(rec: JointStreamRecorder) -> list[str]:
    """Patch the task's script methods at runtime; never edits `src/`."""
    from fruit_sorting.tasks import PickAndPlaceTask

    installed: list[str] = []

    def hook(name: str, make):
        original = getattr(PickAndPlaceTask, name, None)
        if original is None:
            return False
        setattr(PickAndPlaceTask, name, make(original))
        installed.append(name)
        return True

    def make_init(original):
        def init(self, *args, **kwargs):
            original(self, *args, **kwargs)
            rec.attach(self)

        return init

    def make_run(original):
        def run(self, *args, **kwargs):
            rec.begin_attempt()
            try:
                return original(self, *args, **kwargs)
            finally:
                rec.end_attempt()

        return run

    def make_go_ready(original):
        def go_ready(self, *args, **kwargs):
            rec.set_leg("go_ready")
            rec.arm_override = None
            try:
                return original(self, *args, **kwargs)
            finally:
                rec.set_leg("idle")

        return go_ready

    def make_transit(original):
        def transit_to(self, side, name, *args, **kwargs):
            rec.set_leg(f"transit_to_{name}", arm=side)
            try:
                return original(self, side, name, *args, **kwargs)
            finally:
                rec.arm_override = None

        return transit_to

    def make_approach(original):
        def approach(self, arm, jaw_target, *args, **kwargs):
            side = getattr(arm.spec, "side", None)
            mode = os.environ.get("FRUIT_APPROACH_MODE", "cartesian")
            rec.set_leg(f"approach({mode})", arm=side)
            try:
                return original(self, arm, jaw_target, *args, **kwargs)
            finally:
                rec.set_leg("align_close", arm=side)

        return approach

    def make_carry(original):
        def carry(self, side, sample, name, *args, **kwargs):
            rec.set_leg(f"carry {name}", arm=side)
            try:
                return original(self, side, sample, name, *args, **kwargs)
            finally:
                after = "release" if name.startswith("bin") else f"after_{name}"
                rec.set_leg(after, arm=side)

        return carry

    def make_grasp_carry_place(original):
        def grasp_carry_place(self, arm_name, *args, **kwargs):
            rec.set_leg("grasp_prepare", arm=arm_name)
            try:
                return original(self, arm_name, *args, **kwargs)
            finally:
                rec.set_leg("release", arm=arm_name)

        return grasp_carry_place

    hook("__init__", make_init)
    hook("run", make_run)
    hook("go_ready", make_go_ready)
    hook("_transit_to", make_transit)
    hook("_approach", make_approach)
    hook("_carry", make_carry)
    hook("grasp_carry_place", make_grasp_carry_place)
    return installed


def _install_step_hook(rec: JointStreamRecorder) -> None:
    """Record every physics advance while a leg is active (plus the steps count)."""
    from isaacsim.core.simulation_manager import SimulationManager

    original = SimulationManager.step

    def step(*args, **kwargs):
        original(*args, **kwargs)
        if "steps" in kwargs:
            steps = int(kwargs["steps"])
        elif args:
            steps = int(args[0])
        else:
            steps = 1
        rec.on_step(steps)

    SimulationManager.step = staticmethod(step)  # type: ignore[method-assign]


def transit_check_main() -> int:
    """One-shot-read control for the ready-pose stall: drive, hold, watch j1.

    The stream shows every `_transit_to("ready")` ending 1.29-1.35 rad short in
    joint 1 while the drive target is exactly the waypoint. This mode answers the
    two questions the report cannot: is it my per-tick instrumentation (this run
    has none - it only reads joints once per second of sim time), and is the arm
    *blocked* or just *slow* (it holds the target for 10 s of simulated time and
    prints the trajectory of joint 1).
    """
    import importlib.util

    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "pp20", os.path.join(scripts_dir, "20_pick_place.py")
    )
    assert spec is not None and spec.loader is not None
    pp20 = importlib.util.module_from_spec(spec)
    sys.modules["pp20"] = pp20
    spec.loader.exec_module(pp20)

    import isaacsim.core.experimental.utils.app as app_utils
    from isaacsim.core.simulation_manager import SimulationManager

    from fruit_sorting.assets import SceneConfig
    from fruit_sorting.common import install_failure_handler, say
    from fruit_sorting.fruits import FruitSpawner
    from fruit_sorting.scene import SortingScene
    from fruit_sorting.tactile import GripperTactile
    from fruit_sorting.tasks import PickAndPlaceTask

    install_failure_handler("421_posture_probe_transit")
    DT = 1.0 / 120.0
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
    for side in ("left", "right"):
        arm = task.arms[side]
        arm.set_gripper(arm.OPEN)
    say("[transit] go_ready() with default smooth transit ...")
    task.go_ready()
    for side in ("left", "right"):
        arm = task.arms[side]
        ready = np.asarray(task._pose(side, "ready"), dtype=float)
        q = arm.joint_positions()
        err = np.abs(q - ready)
        targets = np.asarray(arm.robot.get_dof_position_targets().numpy(), dtype=float)[0]
        tgt_err = np.abs(targets[arm.arm_dofs] - ready)
        say(
            f"[transit] {side} after go_ready: max |q-ready|={err.max():.4f} rad "
            f"(j{int(np.argmax(err)) + 1}), drive |target-ready|max={tgt_err.max():.6f}"
        )
        say(f"[transit]   q    ={np.round(q, 3).tolist()}")
        say(f"[transit]   ready={np.round(ready, 3).tolist()}")

    say("[transit] holding the ready target for 10 s of simulated time ...")
    for k in range(10):
        for side in ("left", "right"):
            arm = task.arms[side]
            ready = np.asarray(task._pose(side, "ready"), dtype=float)
            arm.robot.set_dof_position_targets([ready], dof_indices=arm.arm_dofs)
        for _ in range(120):
            SimulationManager.step(steps=1)
        parts = []
        for side in ("left", "right"):
            arm = task.arms[side]
            ready = np.asarray(task._pose(side, "ready"), dtype=float)
            q = arm.joint_positions()
            err = np.abs(q - ready)
            parts.append(
                f"{side} max_err={err.max():.4f} j{int(np.argmax(err)) + 1} "
                f"(j1 {q[0]:+.3f}->{ready[0]:+.3f})"
            )
        say(f"[transit] t={(k + 1):.2f}s  " + " | ".join(parts))
    say("[transit] DONE (if max_err is unchanged, the pose is blocked, not slow)")
    try:
        pp20.simulation_app.close()
    except Exception:  # noqa: BLE001
        pass
    return 0


def record_main(record_dir: str) -> int:
    import hashlib
    import importlib.util

    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    os.environ["FRUIT_MOTION_REPORT"] = "1"

    spec = importlib.util.spec_from_file_location(
        "pp20", os.path.join(scripts_dir, "20_pick_place.py")
    )
    assert spec is not None and spec.loader is not None
    pp20 = importlib.util.module_from_spec(spec)
    sys.modules["pp20"] = pp20
    # This executes `20_pick_place.py`'s module level: fd limit, SimulationApp,
    # imports. Its `main()` is the shipped attempt loop, unchanged.
    spec.loader.exec_module(pp20)

    from fruit_sorting.common import install_failure_handler, say

    install_failure_handler("421_posture_probe")

    def md5(path: str) -> str:
        digest = hashlib.md5()
        try:
            with open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError:
            return "missing"

    meta = {
        "script": "421_posture_probe.py",
        "created": datetime.now().isoformat(timespec="seconds"),
        "attempts": int(os.environ.get("ATTEMPTS", "4")),
        "seed": os.environ.get("SEED", "5"),
        "jobs_note": "per-tick articulation DOF state + TCP link pose reads (instrumented branch)",
        "tasks_md5": md5(os.path.join(scripts_dir, "..", "src", "fruit_sorting", "tasks.py")),
        "waypoints": os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json"),
        "waypoints_md5": md5(os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json")),
        "arms": ["left", "right"],
        "joint_names": {},
        "ready": {},
        "tool_local": {},
        "close_local": {},
    }

    stream_path = os.path.join(record_dir, "stream.jsonl")
    rec = JointStreamRecorder(stream_path, meta)
    rec.open()
    installed = _install_task_hooks(rec)
    _install_step_hook(rec)
    say(f"[posture] hooks installed: {', '.join(installed)}")
    say(f"[posture] recording joint stream -> {stream_path}")
    say(f"[posture] read class: DOF state + TCP pose per tick (instrumented branch)")

    code = 1
    try:
        code = pp20.main()
    finally:
        rec.close()

    # Analyze before closing the app: `SimulationApp.close()` ends the process
    # (the smoke run printed no report when this came first).
    report = analyze_stream(load_stream(stream_path))
    say(f"[posture] analyzed {stream_path}")
    for line in format_report(report):
        say(line)
    report_path = os.path.join(record_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    say(f"[posture] report json -> {report_path}")
    try:
        pp20.simulation_app.close()
    except Exception:  # noqa: BLE001 - already closing
        pass
    return code


# --------------------------------------------------------------------------- #
# offline analysis
# --------------------------------------------------------------------------- #
def load_stream(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _percentile(values: np.ndarray, q: float) -> float:
    return float(np.percentile(values, q)) if values.size else 0.0


def _segment_metrics(seg: dict, tool_local, step_warn: float, cmd_warn: float) -> dict:
    rows = seg["rows"]
    q = np.asarray([r["q"] for r in rows], dtype=float)
    t = np.asarray([r["t"] for r in rows], dtype=int)
    out = {
        "arm": seg["key"][0],
        "attempt": seg["key"][1],
        "leg": seg["key"][2],
        "ticks": len(rows),
        "t0": int(t[0]),
        "t1": int(t[-1]),
        "dq_max": 0.0,
        "dq_joint": None,
        "dq_t": None,
        "dq_p95": 0.0,
        "dq_over_warn": 0,
        "cmd_max": 0.0,
        "cmd_joint": None,
        "cmd_t": None,
        "cmd_over_warn": 0,
        "wrist_max": 0.0,
        "wrist_t": None,
        "axis_max": 0.0,
        "axis_t": None,
        "axis_flips": 0,
        "tilt_med": None,
        "tilt_max": None,
    }
    if len(q) >= 2:
        dq = np.abs(np.diff(q, axis=0))
        idx = np.unravel_index(int(np.argmax(dq)), dq.shape)
        out["dq_max"] = float(dq[idx])
        out["dq_joint"] = int(idx[1]) + 1
        out["dq_t"] = int(t[idx[0] + 1])
        out["dq_p95"] = _percentile(dq, 95)
        out["dq_over_warn"] = int((dq > step_warn).sum())
    cmds = [r.get("qcmd") for r in rows]
    if all(c is not None for c in cmds) and len(cmds) >= 2:
        qc = np.asarray(cmds, dtype=float)
        dqc = np.abs(np.diff(qc, axis=0))
        idx = np.unravel_index(int(np.argmax(dqc)), dqc.shape)
        out["cmd_max"] = float(dqc[idx])
        out["cmd_joint"] = int(idx[1]) + 1
        out["cmd_t"] = int(t[idx[0] + 1])
        out["cmd_over_warn"] = int((dqc > cmd_warn).sum())
    quats = [r.get("quat") for r in rows]
    if all(x is not None for x in quats) and len(quats) >= 2:
        qs = np.asarray(quats, dtype=float)
        ang_q = np.arccos(
            np.clip(np.abs(np.einsum("ni,ni->n", qs[1:], qs[:-1])), 0.0, 1.0)
        ) * 2.0
        out["wrist_max"] = float(ang_q.max())
        out["wrist_t"] = int(t[int(np.argmax(ang_q)) + 1])
        if tool_local is not None:
            axis = np.einsum("nij,j->ni", quat_matrices(qs), np.asarray(tool_local, float))
            dots = np.einsum("ni,ni->n", axis[1:], axis[:-1])
            ang_a = np.arccos(np.clip(dots, -1.0, 1.0))
            out["axis_max"] = float(ang_a.max())
            out["axis_t"] = int(t[int(np.argmax(ang_a)) + 1])
            out["axis_flips"] = int((dots < 0.0).sum())
            down = np.array([0.0, 0.0, -1.0])
            tilt = np.degrees(np.arccos(np.clip(axis @ down, -1.0, 1.0)))
            out["tilt_med"] = float(np.median(tilt))
            out["tilt_max"] = float(tilt.max())
    return out


def analyze_stream(
    rows: list[dict],
    step_warn: float = WARN_STEP,
    step_flag: float = FLAG_STEP,
    cmd_warn: float = WARN_CMD,
    cmd_flag: float = FLAG_CMD,
    wrist_warn: float = WARN_WRIST,
    wrist_flag: float = FLAG_WRIST,
    deadband: float = SIGN_DEADBAND,
) -> dict:
    header = next((r for r in rows if r.get("kind") == "header"), {})
    # Attempts are numbered from 0; the startup `go_ready` runs at attempt -1
    # and is context, not a measured attempt, so it is excluded here.
    ticks = [
        r
        for r in rows
        if r.get("kind") == "tick" and int(r.get("attempt", -1)) >= 0
    ]
    teleports = [
        r
        for r in rows
        if r.get("kind") == "teleport" and int(r.get("attempt", -1)) >= 0
    ]
    tool_local = header.get("tool_local") or {}
    ready = header.get("ready") or {}

    # The tool vector's sign is arbitrary (jaw->TCP vs TCP->jaw): decide it once
    # per arm from the whole stream so a single leg with the tool pointing up
    # cannot be normalized to "down" by a per-segment median.
    tool_signed: dict = {}
    for arm, local in tool_local.items():
        if local is None:
            tool_signed[arm] = None
            continue
        arm_quats = [r.get("quat") for r in ticks if r.get("arm") == arm and r.get("quat")]
        if not arm_quats:
            tool_signed[arm] = np.asarray(local, float)
            continue
        axis = np.einsum(
            "nij,j->ni", quat_matrices(arm_quats), np.asarray(local, float)
        )
        sign = -1.0 if float(np.median(axis[:, 2])) > 0.0 else 1.0
        tool_signed[arm] = sign * np.asarray(local, float)

    # Contiguous (arm, attempt, leg) runs, in stream order.
    segments: list[dict] = []
    for row in ticks:
        key = (row.get("arm"), row.get("attempt"), row.get("leg"))
        if segments and segments[-1]["key"] == key:
            segments[-1]["rows"].append(row)
        else:
            segments.append({"key": key, "rows": [row]})
    seg_metrics = [
        _segment_metrics(seg, tool_signed.get(seg["key"][0]), step_warn, cmd_warn)
        for seg in segments
    ]

    # --- per attempt (and arm) --------------------------------------- #
    attempts: dict[tuple, dict] = {}
    for m in seg_metrics:
        key = (m["arm"], m["attempt"])
        entry = attempts.setdefault(
            key,
            {
                "arm": m["arm"],
                "attempt": m["attempt"],
                "ticks": 0,
                "legs": [],
                "dq_max": 0.0,
                "dq_leg": None,
                "dq_joint": None,
                "dq_t": None,
                "cmd_max": 0.0,
                "cmd_leg": None,
                "cmd_joint": None,
                "wrist_max": 0.0,
                "wrist_leg": None,
                "axis_max": 0.0,
                "axis_leg": None,
                "axis_flips": 0,
                "tilt_med": [],
                "tilt_max": 0.0,
                "tilt_leg": None,
                "ready_err": 0.0,
                "ready_err_joint": None,
                "teleports": 0,
                "config": None,
                "crossed": [],
                "reconfigured": False,
                "flags": [],
                "notes": [],
            },
        )
        entry["ticks"] += m["ticks"]
        entry["legs"].append(m["leg"])
        if m["dq_max"] > entry["dq_max"]:
            entry.update(
                dq_max=m["dq_max"], dq_leg=m["leg"], dq_joint=m["dq_joint"], dq_t=m["dq_t"]
            )
        if m["cmd_max"] > entry["cmd_max"]:
            entry.update(
                cmd_max=m["cmd_max"], cmd_leg=m["leg"], cmd_joint=m["cmd_joint"]
            )
        if m["wrist_max"] > entry["wrist_max"]:
            entry.update(wrist_max=m["wrist_max"], wrist_leg=m["leg"])
        if m["axis_max"] > entry["axis_max"]:
            entry.update(axis_max=m["axis_max"], axis_leg=m["leg"])
        entry["axis_flips"] += m["axis_flips"]
        if m["tilt_med"] is not None:
            entry["tilt_med"].append(m["tilt_med"])
        if m["tilt_max"] is not None and m["tilt_max"] > entry["tilt_max"]:
            entry["tilt_max"] = m["tilt_max"]
            entry["tilt_leg"] = m["leg"]

    # Config branch: joints 3/5 of the configuration the attempt grasps with,
    # against the calibrated ready seed. Prefer the first carry leg (the arm is
    # loaded there), else the end of the approach.
    for seg in segments:
        key = (seg["key"][0], seg["key"][1])
        entry = attempts.get(key)
        if entry is None:
            continue
        leg = str(seg["key"][2] or "")
        # How far the calibration's ready pose is from where the arm actually
        # ends after the smooth transit (the stream showed 12/12 transits ending
        # 1.3 rad short in joint 1 while the drive target was exactly the pose).
        seed = ready.get(seg["key"][0])
        if seed is not None and leg == "transit_to_ready":
            err = np.abs(np.asarray(seg["rows"][-1]["q"], float) - np.asarray(seed, float))
            if err.max() > entry["ready_err"]:
                entry["ready_err"] = float(err.max())
                entry["ready_err_joint"] = int(np.argmax(err)) + 1
        row = None
        if leg.startswith("carry "):
            row = seg["rows"][0]
        elif leg.startswith("approach"):
            row = seg["rows"][-1]
        if row is None:
            continue
        current = entry.get("config") or {}
        prefer = leg.startswith("carry ") and not str(current.get("leg", "")).startswith("carry ")
        if prefer or entry.get("config") is None:
            entry["config"] = {
                "leg": leg,
                "q": list(row["q"]),
                "qcmd": row.get("qcmd"),
                "t": row["t"],
            }

    for key, entry in attempts.items():
        arm = key[0]
        seed = ready.get(arm)
        arm_teleports = [
            e for e in teleports if e.get("arm") == arm and e.get("attempt") == key[1]
        ]
        entry["teleports"] = len(arm_teleports)
        entry["teleport_max"] = 0.0
        entry["teleport_max_joint"] = None
        for e in arm_teleports:
            delta = np.abs(
                np.asarray(e["q_after"], float) - np.asarray(e["q_before"], float)
            )
            joint = int(np.argmax(delta)) + 1
            if delta.max() > entry["teleport_max"]:
                entry["teleport_max"] = float(delta.max())
                entry["teleport_max_joint"] = joint
        if seed is not None and entry["config"] is not None:
            sign = []
            for j in BRANCH_JOINTS:
                dev = entry["config"]["q"][j - 1] - seed[j - 1]
                sign.append(int(np.sign(dev)) if abs(dev) > deadband else 0)
            entry["config_signs"] = tuple(sign)
            # Seed-plane crossings within the attempt (per contiguous segment).
            crossed = set()
            for seg in segments:
                if (seg["key"][0], seg["key"][1]) != key:
                    continue
                q = np.asarray([r["q"] for r in seg["rows"]], dtype=float)
                dev = q - np.asarray(seed, dtype=float)
                for j in range(dev.shape[1]):
                    if dev[:, j].min() < -deadband and dev[:, j].max() > deadband:
                        crossed.add(j + 1)
            entry["crossed"] = sorted(crossed)
        # Flags/warnings.
        if entry["dq_max"] > step_flag:
            entry["flags"].append(f"joint lurch {entry['dq_max']:.2f} rad/tick (j{entry['dq_joint']} @{entry['dq_leg']})")
        elif entry["dq_max"] > step_warn:
            entry["notes"].append(
                f"joint step {entry['dq_max']:.2f} rad/tick (j{entry['dq_joint']} @{entry['dq_leg']})"
            )
        if entry["cmd_max"] > cmd_flag:
            entry["flags"].append(f"command jump {entry['cmd_max']:.2f} rad/tick")
        if entry["wrist_max"] > wrist_flag:
            entry["flags"].append(
                f"wrist lurch {entry['wrist_max']:.2f} rad/tick @{entry['wrist_leg']}"
            )
        elif entry["wrist_max"] > wrist_warn:
            entry["notes"].append(
                f"wrist rate {entry['wrist_max']:.2f} rad/tick @{entry['wrist_leg']}"
            )
        if entry["axis_flips"]:
            entry["flags"].append(f"tool-axis flip x{entry['axis_flips']}")
        if entry["tilt_max"] > FLAG_TILT:
            entry["flags"].append(f"tool axis not down ({entry['tilt_max']:.0f} deg)")
        elif entry["tilt_max"] > TILT_WARN:
            entry["notes"].append(
                f"tool tilted {entry['tilt_max']:.0f} deg @{entry['tilt_leg']}"
            )
        if entry["crossed"]:
            entry["notes"].append(
                "crosses seed plane: " + ",".join(f"j{j}" for j in entry["crossed"])
            )
        if entry["teleports"]:
            entry["notes"].append(
                f"deliberate teleport x{entry['teleports']} "
                f"(max {entry['teleport_max']:.2f} rad on j{entry['teleport_max_joint']})"
            )
        if entry["ready_err"] > 0.05:
            entry["notes"].append(
                f"ready pose not reached (off {entry['ready_err']:.2f} rad "
                f"on j{entry['ready_err_joint']})"
            )

    # "Reconfigured": branch signs differ from the arm's modal sign pair (or
    # from the previous attempt of the same arm).
    for arm in ("left", "right"):
        pair_signs = [
            e.get("config_signs")
            for key, e in sorted(attempts.items())
            if key[0] == arm and e.get("config_signs") is not None
        ]
        if not pair_signs:
            continue
        counts: dict[tuple, int] = {}
        for signs in pair_signs:
            counts[signs] = counts.get(signs, 0) + 1
        mode = max(counts, key=counts.get)
        previous = None
        for key, entry in sorted(attempts.items()):
            if key[0] != arm or entry.get("config_signs") is None:
                continue
            entry["branch_mode"] = mode
            entry["reconfigured"] = (
                previous is not None and entry["config_signs"] != previous
            ) or (len(pair_signs) >= 3 and entry["config_signs"] != mode)
            if entry["reconfigured"]:
                entry["flags"].append("reconfigured")
            previous = entry["config_signs"]

    # --- leg boundaries (same arm, consecutive segments) -------------- #
    boundaries: list[dict] = []
    by_arm_idx: dict[str, list[int]] = {}
    for i, seg in enumerate(segments):
        by_arm_idx.setdefault(seg["key"][0], []).append(i)
    for arm, idxs in by_arm_idx.items():
        for i, j in zip(idxs, idxs[1:]):
            first = seg_metrics[i]
            second = seg_metrics[j]
            first_rows = segments[i]["rows"]
            second_rows = segments[j]["rows"]
            cmd_jump, joint = 0.0, None
            if first_rows[-1].get("qcmd") and second_rows[0].get("qcmd"):
                delta = np.abs(
                    np.asarray(second_rows[0]["qcmd"], float)
                    - np.asarray(first_rows[-1]["qcmd"], float)
                )
                joint = int(np.argmax(delta)) + 1
                cmd_jump = float(delta.max())
            meas_jump = float(
                np.abs(
                    np.asarray(second_rows[0]["q"], float)
                    - np.asarray(first_rows[-1]["q"], float)
                ).max()
            )
            tele = [
                e
                for e in teleports
                if e.get("arm") == arm and first["t1"] <= e.get("t", -1) <= second["t0"] + 1
            ]
            boundaries.append(
                {
                    "arm": arm,
                    "from": f"{first['leg']} (attempt {first['attempt']})",
                    "to": f"{second['leg']} (attempt {second['attempt']})",
                    "cmd_jump": cmd_jump,
                    "cmd_joint": joint,
                    "meas_jump": meas_jump,
                    "teleports": [e.get("label") for e in tele],
                }
            )
    boundaries.sort(key=lambda b: -b["cmd_jump"])

    # --- offenders ---------------------------------------------------- #
    teleport_rows = []
    for e in teleports:
        delta = np.abs(
            np.asarray(e["q_after"], float) - np.asarray(e["q_before"], float)
        )
        teleport_rows.append(
            {
                "arm": e.get("arm"),
                "attempt": e.get("attempt"),
                "leg": e.get("leg"),
                "label": e.get("label"),
                "max_rad": float(delta.max()),
                "joint": int(np.argmax(delta)) + 1,
                "sum_rad": float(delta.sum()),
            }
        )
    teleport_rows.sort(key=lambda r: -r["max_rad"])

    offenders = {
        "step": sorted(seg_metrics, key=lambda m: -m["dq_max"])[:8],
        "cmd": sorted(seg_metrics, key=lambda m: -m["cmd_max"])[:8],
        "wrist": sorted(seg_metrics, key=lambda m: -m["wrist_max"])[:8],
        "tilt": sorted(seg_metrics, key=lambda m: -(m["tilt_max"] or 0.0))[:8],
        "flips": [
            {
                "arm": m["arm"],
                "attempt": m["attempt"],
                "leg": m["leg"],
                "flips": m["axis_flips"],
                "tilt_max": m["tilt_max"],
            }
            for m in seg_metrics
            if m["axis_flips"]
        ],
    }

    flagged = [
        e
        for e in attempts.values()
        if e["flags"]
    ]
    totals = {
        "ticks": len(ticks),
        "segments": len(seg_metrics),
        "attempts": len({e["attempt"] for e in attempts.values()}),
        "arm_attempts": len(attempts),
        "teleports": len(teleports),
        "axis_flips": sum(m["axis_flips"] for m in seg_metrics),
        "lurch_legs": sum(1 for m in seg_metrics if m["dq_max"] > step_flag),
        "flagged_attempts": len(flagged),
    }
    return {
        "header": header,
        "attempts": [e for _, e in sorted(attempts.items(), key=lambda kv: (kv[0][1], kv[0][0]))],
        "segments": seg_metrics,
        "boundaries": boundaries,
        "teleports": teleport_rows,
        "offenders": offenders,
        "totals": totals,
        "flags": flagged,
        "thresholds": {
            "step_warn": step_warn,
            "step_flag": step_flag,
            "cmd_warn": cmd_warn,
            "cmd_flag": cmd_flag,
            "wrist_warn": wrist_warn,
            "wrist_flag": wrist_flag,
            "deadband": deadband,
        },
    }


def format_report(report: dict) -> list[str]:
    """Human-readable report; one line per attempt plus the offender summary."""
    lines: list[str] = []
    h = report["header"]
    t = report["totals"]
    lines.append(
        f"[posture] stream: {t['ticks']} ticks, {t['segments']} leg segments, "
        f"{t['attempts']} attempt(s) ({t['arm_attempts']} per-arm entries), "
        f"{t['teleports']} deliberate teleport(s)"
    )
    lines.append(
        f"[posture] source: {h.get('script', '?')} seed={h.get('seed', '?')} "
        f"tasks_md5={str(h.get('tasks_md5'))[:8]} waypoints={h.get('waypoints')}"
    )
    lines.append(f"[posture] read class: {h.get('jobs_note', 'unknown')}")
    lines.append(
        "[posture] thresholds: notice step>"
        f"{report['thresholds']['step_warn']:.2f}/cmd>{report['thresholds']['cmd_warn']:.2f}, "
        f"flag step>{report['thresholds']['step_flag']:.2f}/cmd>{report['thresholds']['cmd_flag']:.2f}, "
        f"wrist flag>{report['thresholds']['wrist_flag']:.2f} rad/tick"
    )
    lines.append("[posture] ---- attempts ----")
    for e in report["attempts"]:
        cfg = e.get("config_signs")
        cfg_txt = (
            f"({cfg[0]:+d},{cfg[1]:+d})" if cfg else "n/a"
        )
        mode = e.get("branch_mode")
        mode_txt = f"({mode[0]:+d},{mode[1]:+d})" if mode else "n/a"
        recon = " RECONFIGURED" if e.get("reconfigured") else ""
        verdict = "ok"
        if e["flags"]:
            verdict = "ODD: " + "; ".join(e["flags"])
        elif e["notes"]:
            verdict = "notice: " + "; ".join(e["notes"])
        lines.append(
            f"[posture] A{e['attempt']} {e['arm']:5s} {e['ticks']:5d} ticks "
            f"| dq {e['dq_max']:.3f} rad/t (j{e['dq_joint']}@{e['dq_leg']}) "
            f"| cmd {e['cmd_max']:.3f} (j{e['cmd_joint']}@{e['cmd_leg']}) "
            f"| wrist {e['wrist_max']:.3f} @{e['wrist_leg']} "
            f"| flips {e['axis_flips']} "
            f"| tele {e['teleports']}"
            + (f"(max {e['teleport_max']:.2f} j{e['teleport_max_joint']})" if e["teleports"] else "")
            + f" | ready err {e['ready_err']:.2f} j{e['ready_err_joint']}"
            + f" | tilt med/max {(np.mean(e['tilt_med']) if e['tilt_med'] else float('nan')):.1f}/{e['tilt_max']:.1f} deg "
            f"| cfg(3,5)={cfg_txt} mode={mode_txt}{recon} "
            f"| verdict {verdict}"
        )
    lines.append("[posture] ---- worst joint steps (measured, rad/tick) ----")
    for i, m in enumerate(report["offenders"]["step"], 1):
        if m["dq_max"] <= 0.0:
            continue
        tag = " FLAG" if m["dq_max"] > report["thresholds"]["step_flag"] else ""
        lines.append(
            f"[posture]  {i}. {m['dq_max']:.4f} A{m['attempt']} {m['arm']:5s} "
            f"{m['leg']}: j{m['dq_joint']} at tick {m['dq_t']} "
            f"(p95 {m['dq_p95']:.3f}, {m['dq_over_warn']} pairs > "
            f"{report['thresholds']['step_warn']:.2f}){tag}"
        )
    lines.append("[posture] ---- worst commanded steps (rad/tick) ----")
    for i, m in enumerate(report["offenders"]["cmd"], 1):
        if m["cmd_max"] <= 0.0:
            continue
        lines.append(
            f"[posture]  {i}. {m['cmd_max']:.4f} A{m['attempt']} {m['arm']:5s} "
            f"{m['leg']}: j{m['cmd_joint']} at tick {m['cmd_t']}"
        )
    lines.append("[posture] ---- worst wrist rotation (rad/tick) ----")
    for i, m in enumerate(report["offenders"]["wrist"], 1):
        if m["wrist_max"] <= 0.0:
            continue
        lines.append(
            f"[posture]  {i}. {m['wrist_max']:.4f} A{m['attempt']} {m['arm']:5s} "
            f"{m['leg']}: at tick {m['wrist_t']} (axis {m['axis_max']:.3f} rad/t, "
            f"tilt max {m['tilt_max']:.1f} deg)"
        )
    lines.append("[posture] ---- tool attitude (tilt of the tool axis from vertical, deg) ----")
    for i, m in enumerate(report["offenders"]["tilt"], 1):
        if m["tilt_max"] is None:
            continue
        lines.append(
            f"[posture]  {i}. {m['tilt_max']:.1f} max / {m['tilt_med']:.1f} med "
            f"A{m['attempt']} {m['arm']:5s} {m['leg']}"
        )
    lines.append("[posture] ---- deliberate teleports (instant joint jumps) ----")
    if not report["teleports"]:
        lines.append("[posture]  none")
    for tr in report["teleports"]:
        lines.append(
            f"[posture]  A{tr['attempt']} {tr['arm']:5s} {tr['leg']} ({tr['label']}): "
            f"max {tr['max_rad']:.3f} rad on j{tr['joint']}, sum |dq| {tr['sum_rad']:.3f} rad"
        )
    lines.append("[posture] ---- tool-axis flips (>90 deg between ticks) ----")
    if not report["offenders"]["flips"]:
        lines.append("[posture]  none")
    for f in report["offenders"]["flips"]:
        lines.append(
            f"[posture]  A{f['attempt']} {f['arm']:5s} {f['leg']}: "
            f"{f['flips']} flip(s), tilt max {f['tilt_max']:.1f} deg"
        )
    lines.append("[posture] ---- leg-boundary command jumps ----")
    for b in report["boundaries"][:10]:
        tele = " TELEPORT:" + ",".join(str(x) for x in b["teleports"]) if b["teleports"] else ""
        lines.append(
            f"[posture]  {b['cmd_jump']:.4f} rad (j{b['cmd_joint']}) / meas "
            f"{b['meas_jump']:.4f} | {b['from']} -> {b['to']} [{b['arm']}]{tele}"
        )
    lines.append("[posture] ---- overall ----")
    lines.append(
        f"[posture] {t['lurch_legs']} leg(s) above the lurch threshold, "
        f"{t['axis_flips']} tool-axis flip(s), {t['flagged_attempts']} flagged attempt(s)"
    )
    if report["flags"]:
        worst = max(report["flags"], key=lambda e: e["dq_max"])
        lines.append(
            f"[posture] VERDICT: postures need work - worst joint step {worst['dq_max']:.3f} "
            f"rad/tick (A{worst['attempt']} {worst['arm']} {worst['dq_leg']}); "
            f"see the offender lists above"
        )
    else:
        lines.append(
            "[posture] VERDICT: no lurch/flip/reconfigure flags at the current thresholds"
        )
    return lines


# --------------------------------------------------------------------------- #
# offline self-test (no Isaac Sim, no logs)
# --------------------------------------------------------------------------- #
def self_test() -> int:
    """Exercise the analyzer on a synthetic stream with a known lurch and flip."""

    def quat_y(a: float):
        return [math.cos(a / 2.0), 0.0, math.sin(a / 2.0), 0.0]

    header = {
        "kind": "header",
        "script": "421_posture_probe.py",
        "seed": "5",
        "arms": ["left", "right"],
        "joint_names": {"left": [f"j{i}" for i in range(1, 8)]},
        "ready": {"left": [0.0] * 7, "right": [0.0] * 7},
        "tool_local": {"left": [0.0, 0.0, -1.0], "right": [0.0, 0.0, -1.0]},
        "close_local": {"left": [1.0, 0.0, 0.0], "right": [1.0, 0.0, 0.0]},
    }
    rows = [header]
    t = 0

    def tick(attempt, leg, q, quat):
        nonlocal t
        t += 1
        rows.append(
            {
                "kind": "tick",
                "t": t,
                "attempt": attempt,
                "arm": "left",
                "leg": leg,
                "q": [float(v) for v in q],
                "qcmd": [float(v) for v in q],
                "quat": quat,
            }
        )

    # Leg 1: smooth j1 ramp with one 0.40 rad j2 lurch at pair 20.
    for i in range(40):
        q = [0.01 * i, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        if i >= 21:
            q[1] = 0.40
        tick(0, "approach(cartesian)", q, [1.0, 0.0, 0.0, 0.0])
    # Leg 2: a 2.2 rad wrist turn in one tick (a flip and a lurch).
    for i in range(10):
        angle = 0.1 * i if i < 5 else 2.2 + 0.05 * i
        tick(0, "carry grasp_lift", [0.4] * 7, quat_y(angle))
    report = analyze_stream(rows)
    worst = report["offenders"]["step"][0]
    per_attempt = report["attempts"][0]
    ok = (
        abs(worst["dq_max"] - 0.40) < 1e-9
        and worst["dq_joint"] == 2
        and worst["leg"] == "approach(cartesian)"
        and per_attempt["axis_flips"] >= 1
        and per_attempt["wrist_max"] > 1.0
        and report["totals"]["teleports"] == 0
    )
    print(f"[posture self-test] {'PASS' if ok else 'FAIL'}")
    for line in format_report(report):
        print(line)
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# entry points
# --------------------------------------------------------------------------- #
def _parse_args(argv: list[str]):
    record_dir = DEFAULT_DIR
    analyze = None
    want_self_test = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--analyze":
            i += 1
            analyze = argv[i] if i < len(argv) else os.path.join(record_dir, "stream.jsonl")
        elif arg == "--dir":
            i += 1
            record_dir = argv[i]
        elif arg == "--self-test":
            want_self_test = True
        i += 1
    return record_dir, analyze, want_self_test


def main(argv: list[str] | None = None) -> int:
    if os.environ.get("FRUIT_POSTURE_MODE") == "transit":
        return transit_check_main()
    argv = list(sys.argv[1:] if argv is None else argv)
    record_dir, analyze, want_self_test = _parse_args(argv)
    if want_self_test:
        return self_test()
    if analyze is not None:
        path = analyze or os.path.join(record_dir, "stream.jsonl")
        if not os.path.exists(path):
            print(f"[posture] no stream at {path}; run the probe first")
            return 1
        report = analyze_stream(load_stream(path))
        for line in format_report(report):
            print(line)
        return 0
    return record_main(record_dir)


if __name__ == "__main__":
    raise SystemExit(main())
