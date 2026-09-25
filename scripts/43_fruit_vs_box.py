"""Same size, same place: does a fruit stop the fingers when a box does?

    $ISAAC_SIM_DIR/python.sh scripts/43_fruit_vs_box.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import UsdGeom, UsdPhysics

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene, _define_box, _set_color
from isaacsim.core.simulation_manager import SimulationManager


def close_and_report(arm, label: str) -> None:
    before = arm.jaw_separation()
    for value in np.linspace(arm.OPEN, 0.0, 30):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    for _ in range(80):
        SimulationManager.step(steps=1)
    say(
        f"{label:22s} sep {before * 100:5.2f}cm -> {arm.jaw_separation() * 100:5.2f}cm  "
        f"q={np.round(arm.dof_positions()[arm.finger_dofs], 4).tolist()}"
    )


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

    arm = ArmController(scene, "left")
    arm.teleport_joints(np.asarray(waypoints["arms"]["left"]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(80):
        SimulationManager.step(steps=1)
    jaw = arm.jaw_centre()
    say(f"jaw centre {np.round(jaw, 4).tolist()}")

    sample = spawner.samples[1]
    d = 0.05
    sample.diameter = d
    UsdGeom.Sphere(scene.stage.GetPrimAtPath(sample.prim_path)).GetRadiusAttr().Set(d / 2.0)
    UsdPhysics.MassAPI(scene.stage.GetPrimAtPath(sample.prim_path)).GetMassAttr().Set(
        float(700.0 * (4 / 3) * np.pi * (d / 2) ** 3)
    )
    app_utils.update_app(steps=20)
    spawner.place(sample, np.array([jaw[0], jaw[1], jaw[2] - 0.040]))
    sample.held = True
    if sample not in spawner.active:
        spawner.active.append(sample)
    for _ in range(30):
        SimulationManager.step(steps=1)
    say(f"fruit at {np.round(spawner.position(sample), 4).tolist()} (dynamic rigid body)")
    close_and_report(arm, "fruit 5cm (dynamic)")

    arm.set_gripper(arm.OPEN)
    for _ in range(80):
        SimulationManager.step(steps=1)
    box = _define_box(
        scene.stage, "/World/TestCube50",
        size=(0.06, 0.05, 0.05),
        center=(float(jaw[0]), float(jaw[1]), float(jaw[2]) - 0.040),
    )
    UsdPhysics.CollisionAPI.Apply(box.GetPrim())
    _set_color(box, (0.9, 0.4, 0.1))
    app_utils.update_app(steps=40)
    close_and_report(arm, "static box 5cm")

    # 3b. dynamic box (rigid body), same size and place
    scene.stage.RemovePrim("/World/TestCube50")
    arm.set_gripper(arm.OPEN)
    for _ in range(80):
        SimulationManager.step(steps=1)
    from pxr import Gf
    dyn = _define_box(
        scene.stage, "/World/TestDynBox",
        size=(0.06, 0.05, 0.05),
        center=(float(jaw[0]), float(jaw[1]), float(jaw[2]) - 0.040),
    )
    UsdPhysics.CollisionAPI.Apply(dyn.GetPrim())
    UsdPhysics.RigidBodyAPI.Apply(dyn.GetPrim())
    UsdPhysics.MassAPI.Apply(dyn.GetPrim()).CreateMassAttr().Set(0.05)
    _set_color(dyn, (0.2, 0.6, 0.9))
    app_utils.update_app(steps=40)
    dyn_prim = __import__("isaacsim.core.experimental.prims", fromlist=["RigidPrim"]).RigidPrim("/World/TestDynBox")
    for _ in range(20):
        SimulationManager.step(steps=1)
    p_before = np.asarray(dyn_prim.get_world_poses()[0].numpy())[0]
    close_and_report(arm, "dynamic box 5cm")
    scene.stage.RemovePrim("/World/TestDynBox")

    scene.stage.RemovePrim("/World/TestCube50")
    arm.set_gripper(arm.OPEN)
    for _ in range(80):
        SimulationManager.step(steps=1)
    spawner.place(sample, np.array([jaw[0], jaw[1], jaw[2] - 0.040]))
    for _ in range(30):
        SimulationManager.step(steps=1)
    close_and_report(arm, "fruit 5cm (repeat)")

    # 4. Does the fruit collide with the robot at all? Drop it onto the hand.
    arm.teleport_joints(np.asarray(waypoints["arms"]["left"]["ready"], dtype=float))
    for _ in range(60):
        SimulationManager.step(steps=1)
    hand = scene.link_pose("openarm_left_hand")[0]
    spawner.place(sample, np.array([hand[0], hand[1], hand[2] + 0.12]))
    sample.held = True
    say(f"drop test: fruit {np.round(spawner.position(sample), 4).tolist()} above hand at {np.round(hand, 4).tolist()}")
    for _ in range(400):
        SimulationManager.step(steps=1)
    say(f"drop test: after 400 steps fruit at {np.round(spawner.position(sample), 4).tolist()} "
        f"(if it did not fall through, z stays above the hand z)")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
