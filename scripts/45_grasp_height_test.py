"""Test the grasp at different palm heights relative to the fruit.

    $ISAAC_SIM_DIR/python.sh scripts/45_grasp_height_test.py
"""

from __future__ import annotations

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


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0

    spawner = FruitSpawner(scene.stage, cfg, seed=4)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()

    arm = ArmController(scene, "left")
    fruit = spawner.samples[1]

    say(f"belt_top={belt_top:.3f}; finger span is jaw_z-0.076 .. jaw_z+0.031")
    say("palm offsets tested: how far above the fruit's centre the jaw centre sits")
    for diameter in (0.030, 0.050, 0.070):
        for palm_offset in (0.020, 0.030, 0.040, 0.055, 0.070):
            resta = belt_top + diameter / 2.0
            jaw_target = np.array([cfg.pick_x, 0.0, resta + palm_offset])
            arm.teleport_joints(np.asarray(
                __import__("json").load(open("configs/waypoints.json"))["arms"]["left"]["grasp"],
                dtype=float))
            arm.set_gripper(arm.OPEN)
            for _ in range(40):
                SimulationManager.step(steps=1)
            _, residual = arm.solve_to(jaw_target, iterations=400, tolerance=0.006)

            fruit.diameter = diameter
            from pxr import UsdGeom, UsdPhysics

            prim = scene.stage.GetPrimAtPath(fruit.prim_path)
            UsdGeom.Sphere(prim).GetRadiusAttr().Set(diameter / 2.0)
            UsdPhysics.MassAPI(prim).GetMassAttr().Set(
                float(700.0 * (4 / 3) * np.pi * (diameter / 2) ** 3)
            )
            app_utils.update_app(steps=20)
            spawner.place(fruit, np.array([cfg.pick_x, 0.0, resta]))
            fruit.held = True
            if fruit not in spawner.active:
                spawner.active.append(fruit)
            for _ in range(40):
                SimulationManager.step(steps=1)

            jaw = arm.jaw_centre()
            sep_open = arm.jaw_separation()
            for value in np.linspace(arm.OPEN, 0.0, 30):
                arm.set_gripper(float(value))
                SimulationManager.step(steps=2)
            for _ in range(80):
                SimulationManager.step(steps=1)
            say(
                f"d={diameter*100:4.1f}cm palm+{palm_offset*100:4.1f}cm | "
                f"jaw_z={jaw[2]:.3f} (want {jaw_target[2]:.3f}, res {residual:.3f}) | "
                f"fruit_z={float(spawner.position(fruit)[2]):.3f} | "
                f"sep {sep_open*100:5.2f} -> {arm.jaw_separation()*100:5.2f}cm"
            )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
