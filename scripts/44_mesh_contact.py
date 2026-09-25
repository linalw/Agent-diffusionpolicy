"""Do the new mesh fruit collide with the gripper? Close on a stationary fruit.

    $ISAAC_SIM_DIR/python.sh scripts/44_mesh_contact.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager


def close_and_report(arm, label):
    before = arm.jaw_separation()
    for value in np.linspace(arm.OPEN, 0.0, 30):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    for _ in range(80):
        SimulationManager.step(steps=1)
    say(f"{label:26s} sep {before*100:5.2f} -> {arm.jaw_separation()*100:5.2f} cm")


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
    say(f"jaw centre {np.round(jaw, 4).tolist()}, fruit are meshes now")

    for sample in spawner.samples[:4]:
        arm.set_gripper(arm.OPEN)
        for _ in range(60):
            SimulationManager.step(steps=1)
        spawner.place(sample, np.array([float(jaw[0]), float(jaw[1]), float(jaw[2]) - 0.040]))
        sample.held = True
        if sample not in spawner.active:
            spawner.active.append(sample)
        for _ in range(40):
            SimulationManager.step(steps=1)
        p = spawner.position(sample)
        close_and_report(arm, f"{sample.category} d={sample.diameter*100:.1f}cm")
        after = spawner.position(sample)
        say(f"    fruit moved {np.linalg.norm(after - p) * 1000:.1f} mm")

    # control: a box of the same size, same place
    from pxr import UsdPhysics

    from fruit_sorting.scene import _define_box, _set_color

    arm.set_gripper(arm.OPEN)
    for _ in range(60):
        SimulationManager.step(steps=1)
    box = _define_box(scene.stage, "/World/TestCube", size=(0.06, 0.055, 0.055),
                      center=(float(jaw[0]), float(jaw[1]), float(jaw[2]) - 0.040))
    UsdPhysics.CollisionAPI.Apply(box.GetPrim())
    _set_color(box, (0.9, 0.4, 0.1))
    app_utils.update_app(steps=40)
    close_and_report(arm, "control box 5.5cm")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
