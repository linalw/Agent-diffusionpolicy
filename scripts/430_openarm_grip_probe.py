"""Screen the *robot's own jaws* as the grasp on the real cell geometry.

`logs/422` proved the de-instanced asset's finger meshes grip an isolated
strawberry. `logs/423-425` then showed the line has an *alignment* problem, not a
force one: the fingers closed past the fruit because nothing servos the real
fingertips onto the fruit's measured centre (the kinematic pads did that job).

This probe measures the grasp primitive the fix needs, on the real cell, before
any pipeline change:

  1. put a fruit on the belt at the pick station (contact-seated, like the line);
  2. hold the top-down attitude and servo the jaw centre to `fruit + dz` at
     120 Hz - the coherent-hand servo, with `dz` standing in for the
     jaw-centre-to-fruit standoff;
  3. close the OpenArm's own finger joints (force limit 10 N, asset drive);
  4. lift 12 cm and measure whether the fruit follows, the finger stall
     separation, the tactile force and the in-hand slip.

    FRUIT_ROBOT_USD=assets/openarm_flat/openarm_flat_deinst.usda \
      scripts/run.sh scripts/430_openarm_grip_probe.py

Sweeps `PROBE_FRUITS` x `PROBE_DZ` x `PROBE_SIDES`. Every configuration runs in
one app session; the fruit is teleported back between the runs.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import json

import numpy as np

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.motion import min_jerk_ramp, mirror_across_xz, top_down_quaternion
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from isaacsim.core.simulation_manager import SimulationManager

DT = 1.0 / 120.0

os.environ.setdefault("FRUIT_FINGER_COLLIDERS", "1")
os.environ.setdefault("FRUIT_FINGER_MU", "1.0")
# Keep the fruits awake: a sleeping body is not woken by an approaching finger.
os.environ.setdefault("FRUIT_NO_SLEEP", "1")


def quat_matrix(q) -> np.ndarray:
    w, x, y, z = (float(v) for v in q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def pinch_extent(sample, quat) -> float:
    from fruit_sorting.meshes import FRUIT_SHAPES, axis_extent

    shape = FRUIT_SHAPES.get(sample.category)
    if shape is None:
        return float(sample.diameter)
    axis_world = quat_matrix(quat)[:, 1]
    _, fruit_quat = _spawner.fruit_pose(sample)
    local_axis = quat_matrix(fruit_quat).T @ axis_world
    return float(axis_extent(shape, float(sample.diameter), local_axis))


def finger_geometry(arm, quat) -> str:
    """Where the finger collision geometry is, in the hand frame.

    Prints, relative to the jaw centre, the world-bound range along the closing
    axis (`y` of the tool) and along the finger direction (`z`, + = down the
    fingers). This is the geometry PhysX cooks as a convex hull.
    """
    from pxr import Usd, UsdGeom

    rot = quat_matrix(quat)
    stage = arm.scene.stage
    jaw = np.asarray(arm.jaw_centre(), dtype=float)
    parts = []
    for which in ("left", "right"):
        path = f"/World/OpenArm/openarm_{arm.spec.side}_{which}_finger/visuals"
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid():
            parts.append(f"{which}: missing")
            continue
        box = UsdGeom.Boundable(prim).ComputeWorldBound(
            Usd.TimeCode.Default(), UsdGeom.Tokens.default_
        )
        rng = box.ComputeAlignedRange()
        mn = np.array(rng.GetMin(), dtype=float)
        mx = np.array(rng.GetMax(), dtype=float)
        corners = np.array(
            [[x, y, z] for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
        )
        rel = (corners - jaw) @ rot
        parts.append(
            f"{which}: close[{rel[:, 1].min():+.3f},{rel[:, 1].max():+.3f}] "
            f"down[{rel[:, 2].min():+.3f},{rel[:, 2].max():+.3f}]"
        )
    return " | ".join(parts)


def run_one(side: str, sample, dz: float) -> dict:
    cfg = SceneConfig()
    arm = ARMS[side]
    waypoints = WAYPOINTS["arms"][side]

    # Contact seating, as on the line: put the fruit where it stopped.
    d = float(sample.diameter)
    seat = np.array([cfg.pick_x, cfg.pick_y, cfg.belt_center[2] + cfg.belt_size[2] / 2.0 + d / 2.0])
    _spawner.place(sample, seat)
    sample.held = True
    for _ in range(30):
        SimulationManager.step(steps=1)

    # Return the hand to the calibrated pick pose, then take the top-down hold.
    arm.teleport_joints(np.asarray(waypoints["grasp"], dtype=float))
    for _ in range(40):
        SimulationManager.step(steps=1)
    hold = top_down_quaternion(os.environ.get("FRUIT_HAND_AXIS", "x"))
    if side == "left":
        hold = mirror_across_xz(hold)
    arm.hold_quaternion = hold
    arm.sync_command_to_measured()

    # 1. Servo the jaw centre to `fruit + dz` at the control rate (the
    # coherent-hand tracker, pointed at the real fingers).
    track = int(os.environ.get("PROBE_TRACK", "240"))
    for _ in range(track):
        fruit = np.asarray(_spawner.position(sample), dtype=float)
        arm.ik_step(arm.tcp_target_for_jaw(fruit + np.array([0.0, 0.0, float(dz)])))
        SimulationManager.step(steps=1)
    fruit = np.asarray(_spawner.position(sample), dtype=float)
    jaw = np.asarray(arm.jaw_centre(), dtype=float)
    quat = np.asarray(arm.tcp_pose()[1], dtype=float)
    place_error = float(np.linalg.norm((jaw - fruit) - np.array([0.0, 0.0, float(dz)])))
    dz_real = float((jaw - fruit) @ quat_matrix(quat)[:, 2])
    geometry = finger_geometry(arm, quat)

    # 2. Close the robot's own fingers on the measured extent, tracking the
    # fruit's measured centre every tick (the line keeps carrying it).
    width = pinch_extent(sample, quat)
    squeeze = float(os.environ.get("PROBE_SQUEEZE", "0.98"))
    gap = width * squeeze
    value = arm.gripper_value_for_separation(gap)
    force_max = 0.0
    q_before = arm.dof_positions()[arm.finger_dofs].copy()
    for cmd in min_jerk_ramp(arm.OPEN, value, 60):
        fruit = np.asarray(_spawner.position(sample), dtype=float)
        arm.ik_step(arm.tcp_target_for_jaw(fruit + np.array([0.0, 0.0, float(dz)])))
        arm.set_gripper(float(cmd))
        for _ in range(2):
            SimulationManager.step(steps=1)
            reading = TACTILE.read()[side]
            force_max = max(force_max, reading.normal_force)
    for _ in range(60):
        fruit = np.asarray(_spawner.position(sample), dtype=float)
        arm.ik_step(arm.tcp_target_for_jaw(fruit + np.array([0.0, 0.0, float(dz)])))
        SimulationManager.step(steps=1)
        reading = TACTILE.read()[side]
        force_max = max(force_max, reading.normal_force)
    q_after = arm.dof_positions()[arm.finger_dofs].copy()
    separation = arm.jaw_separation()
    fruit = np.asarray(_spawner.position(sample), dtype=float)
    jaw = np.asarray(arm.jaw_centre(), dtype=float)
    reading = TACTILE.read()[side]
    contacts = reading.contact_count

    # 3. Lift 12 cm, keeping the top-down hold, and watch the payload.
    start = np.asarray(arm.jaw_centre(), dtype=float).copy()
    rel0 = quat_matrix(quat).T @ (fruit - jaw)
    slip_max = 0.0
    lift_force = 0.0
    for dz_lift in min_jerk_ramp(0.0, float(os.environ.get("PROBE_LIFT", "0.12")), 200):
        arm.ik_step(arm.tcp_target_for_jaw(start + np.array([0.0, 0.0, float(dz_lift)])))
        SimulationManager.step(steps=1)
        now = np.asarray(_spawner.position(sample), dtype=float)
        rot = quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
        slip_max = max(slip_max, float(np.linalg.norm(rot.T @ (now - arm.jaw_centre()) - rel0)))
        lift_force = max(lift_force, TACTILE.read()[side].normal_force)
    for _ in range(60):
        SimulationManager.step(steps=1)
    fruit_after = np.asarray(_spawner.position(sample), dtype=float)
    lift = float(fruit_after[2] - fruit[2])

    # Open and park so the next configuration starts clean.
    for cmd in min_jerk_ramp(value, arm.OPEN, 30):
        arm.set_gripper(float(cmd))
        SimulationManager.step(steps=1)
    arm.hold_quaternion = None
    for _ in range(20):
        SimulationManager.step(steps=1)

    return {
        "side": side,
        "fruit": sample.category,
        "d": d,
        "dz": dz,
        "err": place_error,
        "dz_real": dz_real,
        "jaw": float(separation),
        "width": width,
        "q0": float(q_before.mean()),
        "q1": float(q_after.mean()),
        "force": max(force_max, lift_force),
        "contacts": contacts,
        "lift": lift,
        "slip": slip_max,
        "geom": geometry,
    }


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    global _spawner, ARMS, WAYPOINTS, TACTILE
    TACTILE = GripperTactile()
    TACTILE.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    TACTILE.refresh()

    _spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    _spawner.create_pool()
    SimulationManager.step(steps=30)
    _spawner.refresh_rigids()
    _spawner.belt = scene.belt
    _spawner.reset()

    ARMS = {"left": ArmController(scene, "left"), "right": ArmController(scene, "right")}
    with open(os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json"), encoding="utf-8") as fh:
        WAYPOINTS = json.load(fh)
    for arm in ARMS.values():
        arm.set_gripper(arm.OPEN)

    sides = os.environ.get("PROBE_SIDES", "right").split(",")
    fruits = os.environ.get("PROBE_FRUITS", "strawberry,apple,orange").split(",")
    dzs = [float(v) for v in os.environ.get("PROBE_DZ", "0.045,0.060,0.075").split(",")]

    picks: dict[str, object] = {}
    for sample in _spawner.samples:
        picks.setdefault(sample.category, sample)

    rows = []
    for side in sides:
        for category in fruits:
            sample = picks.get(category)
            if sample is None:
                continue
            for dz in dzs:
                row = run_one(side, sample, dz)
                rows.append(row)
                say(
                    f"[probe] {row['side']:5s} {row['fruit']:10s} d={row['d']*100:4.1f}cm "
                    f"dz={row['dz']*100:4.1f}cm(real {row['dz_real']*100:4.1f}) "
                    f"err={row['err']*1000:5.1f}mm "
                    f"jaw={row['jaw']*100:5.2f}cm vs w={row['width']*100:5.2f}cm "
                    f"q {row['q0']:.4f}->{row['q1']:.4f} F={row['force']:5.2f}N "
                    f"lift={row['lift']*100:+5.1f}cm slip={row['slip']*1000:4.1f}mm"
                )
                say(f"[probe]   fingers {row['geom']}")

    print()
    print("side  fruit      d[cm]  dz[cm]  err[mm]  jaw[cm]  w[cm]   q0     q1     "
          "F[N]   lift[cm] slip[mm]")
    for row in rows:
        print(
            f"{row['side']:5s} {row['fruit']:10s} {row['d']*100:5.1f}  {row['dz']*100:6.1f}  "
            f"{row['err']*1000:6.1f}  {row['jaw']*100:6.2f}  {row['width']*100:5.2f}  "
            f"{row['q0']:.4f} {row['q1']:.4f} {row['force']:6.2f} "
            f"{row['lift']*100:+7.1f} {row['slip']*1000:7.1f}"
        )
    say("DONE")
    return 0


_spawner = None
ARMS = {}
WAYPOINTS = {}
TACTILE = None

if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
