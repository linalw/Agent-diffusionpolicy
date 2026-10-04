"""Where are the P3 contact faces, and do they cradle a static fruit?

    FRUIT_FINGER_FACE=h scripts/run.sh scripts/144_contact_face_probe.py

Builds the cell, poses each arm at its recorded grasp pose and prints, for every
finger, the link origin, the visual-mesh world bounds and every authored
`contact_faces/*` wing's world bounds. Then it drops one fruit of the pool
between the left fingers at the *same standoff the dynamic close uses*
(`FRUIT_FINGER_LEN + FRUIT_DYNAMIC_PAD_LIFT`), closes to 0.97x the fruit's
diameter, lifts the arm 15 cm and reports the tactile force and whether the
fruit followed.

Simulator-free geometry is not available (`pxr` only exists inside Isaac Sim),
so this is the fast mechanism A/B for face designs; the ten-attempt dynamic run
remains the measurement.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import numpy as np
from pxr import Usd, UsdGeom

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

DT = 1.0 / 120.0
os.environ.setdefault("FRUIT_NO_SLEEP", "1")


def world_matrix(prim) -> np.ndarray:
    return np.array(
        UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    ).reshape(4, 4).T


def world_bounds(prim):
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    rng = cache.ComputeWorldBound(prim).ComputeAlignedRange()
    return np.array(rng.GetMin(), dtype=float), np.array(rng.GetMax(), dtype=float)


def report_arm(scene, waypoints, side: str) -> ArmController:
    arm = ArmController(scene, side)
    arm.teleport_joints(np.asarray(waypoints["arms"][side]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(120):
        SimulationManager.step(steps=1)
    jaw = arm.jaw_centre()
    axis = arm.jaw_axis()
    tool = arm.approach_axis()
    say(
        f"--- {side} grasp pose: jaw={np.round(jaw, 4).tolist()} "
        f"jaw_axis={np.round(axis, 3).tolist()} tool_axis={np.round(tool, 3).tolist()} "
        f"span={arm.jaw_separation() * 1000:.1f} mm"
    )
    for which in ("left", "right"):
        path = f"/World/OpenArm/openarm_{side}_{which}_finger"
        prim = scene.stage.GetPrimAtPath(path)
        origin = world_matrix(prim)[:3, 3]
        face_prim = scene.stage.GetPrimAtPath(f"{path}/contact_faces")
        say(
            f"    {which}: link origin={np.round(origin, 4).tolist()} "
            f"gap-sign={np.sign(float(np.dot(axis, origin - jaw))):+.0f}"
        )
        if not face_prim.IsValid():
            say("      (no authored contact faces)")
            continue
        kids = [child for child in face_prim.GetChildren()]
        for child in sorted(kids, key=lambda p: p.GetName()):
            lo, hi = world_bounds(child)
            centre = (lo + hi) / 2.0
            say(
                f"      {child.GetName():<10} centre={np.round(centre, 4).tolist()} "
                f"size={np.round(hi - lo, 4).tolist()} "
                f"gap-extreme={np.dot(axis, centre - jaw):+.4f} m"
            )
    return arm


def main() -> int:
    with open("configs/waypoints.json", encoding="utf-8") as fh:
        waypoints = json.load(fh)
    from fruit_sorting.tactile import GripperTactile

    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()
    say(f"FINGER_FACE={os.environ.get('FRUIT_FINGER_FACE', 'flat')}")

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    for _ in range(30):
        SimulationManager.step(steps=1)
    spawner.refresh_rigids()

    arm = report_arm(scene, waypoints, "left")

    # Static cradle test: the largest fruit in the pool, placed on the pad
    # standoff the dynamic close actually uses - the *measured* fingertip
    # offset, exactly like `PickAndPlaceTask._pad_standoff`.
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    lowest = None
    for which in ("left", "right"):
        path = f"/World/OpenArm/openarm_left_{which}_finger"
        rng = cache.ComputeWorldBound(scene.stage.GetPrimAtPath(path)).ComputeAlignedRange()
        lo = float(rng.GetMin()[2])
        lowest = lo if lowest is None else min(lowest, lo)
    finger_len = float(arm.jaw_centre()[2]) - float(lowest)
    lift = float(os.environ.get("FRUIT_DYNAMIC_PAD_LIFT", "0.005"))
    sample = max(spawner.samples, key=lambda s: s.diameter)
    jaw = arm.jaw_centre()
    tool = arm.approach_axis()
    target = jaw + tool * (finger_len + lift)
    say(f"static test standoff: fingertip={finger_len * 1000:.1f} mm + lift={lift * 1000:.1f} mm")
    spawner._rigids[sample.index].set_world_poses(
        positions=[target.tolist()], orientations=[[1.0, 0.0, 0.0, 0.0]]
    )
    for _ in range(2):
        SimulationManager.step(steps=1)
    fruit0 = np.asarray(spawner.position(sample), dtype=float)
    say(
        f"static test: {sample.category} d={sample.diameter * 1000:.1f} mm at "
        f"{np.round(fruit0, 4).tolist()} (jaw offset {np.round(fruit0 - jaw, 4).tolist()})"
    )
    # Ramp the fingers shut over 90 ticks (~0.37 s, the dynamic close's fast
    # phase) while the fruit is still where it was placed; the drop in that
    # time is under a millimetre.
    end = max(sample.diameter * 0.97, 0.012)
    for gap in np.linspace(0.098, end, 90):
        arm.set_gripper(arm.gripper_value_for_separation(float(gap)))
        SimulationManager.step(steps=1)
    reading = tactile.read().get("left")
    force = float(reading.normal_force) if reading is not None else 0.0
    fruit1 = np.asarray(spawner.position(sample), dtype=float)
    say(
        f"static close: span={arm.jaw_separation() * 1000:.1f} mm "
        f"fruit moved {np.round(fruit1 - fruit0, 4).tolist()} force={force:.2f} N"
    )
    # Lift 15 cm and see whether the payload follows.
    for _ in range(240):
        jaw_now = arm.jaw_centre()
        arm.ik_step(arm.tcp_target_for_jaw(jaw_now + np.array([0.0, 0.0, 0.0007])))
        SimulationManager.step(steps=1)
        if _ % 60 == 0:
            arm.set_gripper(arm.gripper_value_for_separation(end))
    fruit2 = np.asarray(spawner.position(sample), dtype=float)
    say(
        f"static lift: fruit moved {np.round(fruit2 - fruit1, 4).tolist()} "
        f"(jaw moved {np.round(arm.jaw_centre() - jaw, 4).tolist()}) "
        f"followed={'YES' if fruit2[2] - fruit1[2] > 0.08 else 'NO'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
