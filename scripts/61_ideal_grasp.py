"""Can the gripper hold a real fruit by friction, under ideal conditions?

Strips the moving-belt problem out of the question: the belt is stopped, the
fruit is placed exactly on the jaw centre line with its equator at the jaw
centre, the jaws close to a 3 % squeeze (with the corrected face-offset
calibration), and the arm then lifts smoothly. If the fruit follows, physical
grasping works and the remaining work is making the conveyor hand-off repeatable.

    $ISAAC_SIM_DIR/python.sh scripts/61_ideal_grasp.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.grasp import GraspPrimitive
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from isaacsim.core.simulation_manager import SimulationManager
from pxr import Usd, UsdGeom

from pxr import Usd, UsdPhysics
from fruit_sorting.scene import _add_physics_material

CONFIG = json.load(open(os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json"), encoding="utf-8"))
SQUEEZE = float(os.environ.get("FRUIT_SQUEEZE", "0.995"))
LIFT = 0.12


def pose_grasp(arm, target) -> float:
    arm.teleport_joints(np.asarray(CONFIG["arms"][arm.spec.side]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(80):
        SimulationManager.step(steps=1)
    _cfg, residual = arm.solve_to(target, iterations=500, tolerance=0.004)
    if residual > 0.010:
        # The low pick pose sits near the edge of the workspace, so the plain
        # solve lands in a local minimum; the pipeline uses random restarts here.
        _cfg, residual = arm.solve_to(target, iterations=500, tolerance=0.004, restarts=4, seed=7)
    for _ in range(30):
        SimulationManager.step(steps=1)
    return residual


def run(arm, spawner, tactile, sample, belt_top) -> dict:
    d = sample.diameter
    cfg = spawner.cfg
    seat = belt_top + cfg.nest_height
    if cfg.nest_height > 0.0:
        # Fruit ride up the ramp and come to rest against the low downstream stop,
        # so their centre sits half a diameter upstream of it.
        stop_x = cfg.pick_x + 0.02 - cfg.nest_length_x / 2.0
        pick_x = stop_x + d / 2.0
    else:
        pick_x = cfg.pick_x
    # The pad surfaces sit ~15 mm along the approach axis from `jaw_centre`
    # (the midpoint of the finger *link origins*, which is where the finger roots
    # are). A fruit placed at the jaw centre therefore lands between the finger
    # roots and gets pushed out - the 4.5 cm displacement in logs/78_trace.log.
    # Aim the *pads* at the fruit instead.
    pad_offset = float(os.environ.get("FRUIT_PAD_OFFSET", "0.015"))
    _res = pose_grasp(arm, np.array([pick_x, 0.0, seat + d / 2.0 + 0.003]))
    left_f, right_f = arm.jaw_positions()
    left_f = np.asarray(left_f, dtype=float)
    right_f = np.asarray(right_f, dtype=float)
    approach = arm.tcp_position() - (left_f + right_f) / 2.0
    approach = approach / max(float(np.linalg.norm(approach)), 1e-9)
    # Aim the jaw centre so that the *pads* land on the fruit: the pads sit
    # `pad_offset` along the approach axis from the jaw centre.
    # The fruit sits on the nest centre line; the *pads* have to be servo'd onto
    # it. The pads are at `pad_forward` along the approach axis and `band_centre`
    # below the jaw centre, so the jaw command is the fruit position minus both.
    pad_forward = float(os.environ.get("FRUIT_PAD_FORWARD", "0.010"))
    band_centre = (float(os.environ.get("FRUIT_PAD_LO", "-0.045"))
                   + float(os.environ.get("FRUIT_PAD_HI", "0.012"))) / 2.0
    fruit_pos = np.array([pick_x, 0.0, seat + d / 2.0])
    target = fruit_pos + np.array([0.0, 0.0, 0.003]) - approach * pad_forward \
        - np.array([0.0, 0.0, band_centre])
    residual = pose_grasp(arm, target)
    # The fruit stays on the nest centre line - placing it at the pads' projected
    # x/y put it *beside* the 2 cm ridge and 4.5 cm below the pads, which is what
    # the close-up render shows (logs/gripper_view/close_front.png).
    rest = fruit_pos
    spawner.place(sample, rest)
    sample.held = True
    for _ in range(40):
        SimulationManager.step(steps=1)

    # Force-limited closing. Two stop conditions, because the tactile sensor is
    # unreliable in this build (it reads 0 N through real contact as often as it
    # reads hundreds):
    #   1. the finger joints stop following the command - `jaw_separation` stays
    #      above what the command asks for - which means the pads are loaded;
    #   2. the tactile force reaches the budget.
    # Driving to a fixed position instead spikes the contact to hundreds of
    # newtons and wedges the fruit out of the jaws (logs/72, logs/92).
    grip = arm.gripper_value_for_separation(d * SQUEEZE)
    force_factor = float(os.environ.get("FRUIT_FORCE_FACTOR", "20"))
    force_limit = float(np.clip(sample.mass * 9.81 * force_factor, 2.0, 60.0))
    value = arm.OPEN
    blocked_at = None
    stop_reason = "commanded limit"
    block_stop = float(os.environ.get("FRUIT_BLOCK_STOP", "0.006"))
    for value in np.linspace(arm.OPEN, grip, 90):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
        expected = arm.JAW_SEPARATION_OFFSET + 2.0 * float(value)
        block = arm.jaw_separation() - expected
        reading = tactile.read()[arm.spec.side].normal_force
        if block > block_stop:
            blocked_at = block
            stop_reason = f"blocked by fruit (+{block * 1000:.1f}mm)"
            break
        if reading >= force_limit:
            stop_reason = f"force limit {reading:.1f}N"
            break
    # Then load the grip with the *same* code the task uses, so this probe
    # measures the production path rather than its own private close loop.
    primitive = GraspPrimitive(cfg, spawner, arm, tactile, arm.spec.side)
    grip = primitive.close(sample)
    for _ in range(60):
        arm.set_gripper(float(grip))
        SimulationManager.step(steps=1)
    say(f"  close stopped: {stop_reason} at cmd={grip:.4f} "
        f"jaw={arm.jaw_separation() * 100:.2f}cm blocked={blocked_at}")
    for _ in range(90):
        SimulationManager.step(steps=1)
    force = tactile.read()[arm.spec.side].normal_force
    gap = arm.jaw_separation()
    closed_pos = spawner.position(sample).copy()
    drift = closed_pos - rest
    # Diagnostic: gap between each pad's surface and the fruit's surface. A pad
    # that is "loaded" but not carrying should show up here as a positive gap.
    pad_gap = None
    stage = spawner.stage
    if stage is not None:
        pads = []
        for which in ("left", "right"):
            path = f"/World/OpenArm/openarm_{arm.spec.side}_{which}_finger/grasp_pad"
            prim = stage.GetPrimAtPath(path)
            if prim.IsValid():
                matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
                    Usd.TimeCode.Default()
                )
                pads.append(np.array(matrix).reshape(4, 4).T[0:3, 3])
        if len(pads) == 2:
            r = sample.diameter / 2.0
            pad_radius = float(os.environ.get("FRUIT_PAD_RADIUS", "0.010"))
            pad_gap = [
                float(np.linalg.norm(p - closed_pos) - pad_radius - r) for p in pads
            ]
            # Vertical offset of each pad centre from the fruit's centre: if a pad
            # sits well above the fruit, its contact normal points downwards and the
            # squeeze presses the fruit onto the belt instead of pinching it.
            pad_dz = [float(p[2] - closed_pos[2]) for p in pads]
        else:
            pad_dz = None
    else:
        pad_dz = None

    # Smooth Cartesian lift: a friction grip must not be shocked off.
    goal = target + [0.0, 0.0, LIFT]
    for i in range(240):
        step_target = target + [0.0, 0.0, LIFT * (i + 1) / 240.0]
        arm.ik_step(arm.tcp_target_for_jaw(step_target))
        SimulationManager.step(steps=1)
    for _ in range(60):
        arm.ik_step(arm.tcp_target_for_jaw(goal))
        SimulationManager.step(steps=1)
    lifted = float(spawner.position(sample)[2] - closed_pos[2])

    for value in np.linspace(grip, arm.OPEN, 20):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    sample.held = False
    return {
        "category": sample.category,
        "d": d,
        "residual": residual,
        "gap": gap,
        "force": force,
        "drift": drift,
        "pad_gap": pad_gap,
        "pad_dz": pad_dz,
        "lifted": lifted,
        "held": lifted > 0.05,
    }


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    # Real grippers have rubber pads. Binding a high-friction material to the
    # finger links is the difference between a squeeze that carries the fruit and
    # one that squeezes it out (the pad friction coefficient is otherwise the
    # PhysX default, which is too low for a round fruit).
    pad_mu = float(os.environ.get("FRUIT_PAD_MU", "1.2"))
    for side in ("left", "right"):
        for which in ("left", "right"):
            path = f"/World/OpenArm/openarm_{side}_{which}_finger"
            prim = scene.stage.GetPrimAtPath(path)
            if prim.IsValid():
                _add_physics_material(prim, pad_mu, pad_mu, 0.0)
    say(f"finger pads bound with mu={pad_mu}")
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    spawner = FruitSpawner(scene.stage, cfg, seed=4)
    spawner.create_pool()
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    tactile.refresh()
    spawner.refresh_rigids()
    spawner.reset()
    if spawner.belt is not None:
        spawner.belt.stop()
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(f"belt_top={belt_top:.3f} m, waypoints=" + os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json"))

    # One fruit per size class, so the sweep covers the whole 2-7 cm range.
    by_size = sorted(spawner.samples, key=lambda s: s.diameter)
    band = os.environ.get("FRUIT_SIZE_BAND", "all")
    if band == "small":
        # 2-4 cm fruit only: the weakest class in the pipeline runs (logs/134:
        # 1/3), and the class the pick-nest geometry is most marginal for.
        picks = [s for s in by_size if s.diameter < 0.045][:6]
    else:
        picks = [by_size[0], by_size[len(by_size) // 3], by_size[len(by_size) // 2],
                 by_size[2 * len(by_size) // 3], by_size[-1]]
    say(f"size band={band}: {[round(s.diameter * 100, 1) for s in picks]}")

    results = []
    for side in ("left", "right"):
        arm = ArmController(scene, side)
        for sample in picks:
            res = run(arm, spawner, tactile, sample, belt_top)
            results.append((side, res))
            gap_str = ""
            if res.get("pad_gap"):
                gap_str = (
                    f"pad_gap=({res['pad_gap'][0] * 1000:+.1f},"
                    f"{res['pad_gap'][1] * 1000:+.1f})mm dz=("
                    f"{res['pad_dz'][0] * 1000:+.1f},"
                    f"{res['pad_dz'][1] * 1000:+.1f})mm "
                )
            say(
                f"{side:5s} {res['category']:10s} d={res['d'] * 100:4.1f}cm "
                f"res={res['residual'] * 1000:5.1f}mm grip_cmd={res['gap'] * 100:5.2f}cm "
                f"force={res['force']:7.2f}N drift=({res['drift'][0] * 1000:+5.1f},"
                f"{res['drift'][1] * 1000:+5.1f},{res['drift'][2] * 1000:+5.1f})mm "
                f"{gap_str}"
                f"lift={res['lifted'] * 100:+6.1f}cm "
                f"{'HELD' if res['held'] else 'slipped'}"
            )
    wins = sum(1 for _s, r in results if r["held"])
    say(f"summary: {wins}/{len(results)} held")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
