"""Discriminating test: does the gripper's collision geometry touch an object at all?

Places a sphere of a given diameter exactly between the jaws, commands the
gripper fully closed, and reports how far the fingers actually travel.

    $ISAAC_SIM_DIR/python.sh scripts/41_grasp_contact_test.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import UsdGeom

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager


def run_case(scene, spawner, arm, waypoints, diameter: float, z_offset: float) -> None:
    sample = spawner.samples[1]
    sample.diameter = diameter
    UsdGeom.Sphere(scene.stage.GetPrimAtPath(sample.prim_path)).GetRadiusAttr().Set(diameter / 2.0)
    # Re-apply mass so the physics properties match the new size.
    from pxr import UsdPhysics

    UsdPhysics.MassAPI(scene.stage.GetPrimAtPath(sample.prim_path)).GetMassAttr().Set(
        float(700.0 * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3)
    )
    app_utils.update_app(steps=20)

    arm.teleport_joints(np.asarray(waypoints["arms"]["left"]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(60):
        SimulationManager.step(steps=1)

    jaw = arm.jaw_centre()
    spawner.place(sample, np.array([jaw[0], jaw[1], jaw[2] - z_offset]))
    sample.held = True
    if sample not in spawner.active:
        spawner.active.append(sample)
    for _ in range(30):
        SimulationManager.step(steps=1)
    before = spawner.position(sample).copy()
    open_sep = arm.jaw_separation()

    # Command the gripper fully closed and let it push.
    for value in np.linspace(arm.OPEN, 0.0, 30):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    for _ in range(80):
        SimulationManager.step(steps=1)

    after = spawner.position(sample)
    say(
        f"d={diameter * 100:5.1f}cm z_off={z_offset * 100:4.1f}cm | "
        f"sep {open_sep * 100:5.2f}cm -> {arm.jaw_separation() * 100:5.2f}cm | "
        f"finger_q={np.round(arm.dof_positions()[arm.finger_dofs], 4).tolist()} | "
        f"fruit moved {np.linalg.norm(after - before) * 1000:5.1f}mm"
    )
    sample.held = False


def main() -> int:
    with open("configs/waypoints.json", encoding="utf-8") as fh:
        waypoints = json.load(fh)
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)

    spawner = FruitSpawner(scene.stage, cfg, seed=4)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()
    app_utils.update_app(steps=10)

    arm = ArmController(scene, "left")
    say("commanding the gripper FULLY CLOSED (finger joint 0.044 -> 0.0)")
    say("if the fingers stop well above the closed position, contact works")
    for diameter in (0.12, 0.09, 0.07, 0.05, 0.03):
        run_case(scene, spawner, arm, waypoints, diameter, 0.040)

    say("--- same, but with the sphere centred on the finger span mid-height ---")
    for diameter in (0.09, 0.05):
        run_case(scene, spawner, arm, waypoints, diameter, 0.038)

    # Control: does anything the gripper touches stop it? Put a large static box
    # where the jaws are and close again.
    say("--- control: large STATIC box between the jaws ---")
    from pxr import Gf, UsdPhysics

    from fruit_sorting.scene import _define_box, _set_color

    arm.teleport_joints(np.asarray(waypoints["arms"]["left"]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(60):
        SimulationManager.step(steps=1)
    jaw = arm.jaw_centre()
    box = _define_box(
        scene.stage,
        "/World/TestBlock",
        size=(0.10, 0.16, 0.10),
        center=(float(jaw[0]) + 0.01, float(jaw[1]), float(jaw[2]) - 0.04),
    )
    UsdPhysics.CollisionAPI.Apply(box.GetPrim())
    _set_color(box, (0.9, 0.3, 0.1))
    app_utils.update_app(steps=40)
    say(f"block placed at jaw; sep before = {arm.jaw_separation() * 100:.2f}cm")
    for value in np.linspace(arm.OPEN, 0.0, 30):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    for _ in range(80):
        SimulationManager.step(steps=1)
    say(
        f"block test: sep {arm.jaw_separation() * 100:.2f}cm "
        f"finger_q={np.round(arm.dof_positions()[arm.finger_dofs], 4).tolist()}"
    )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
