"""Try a simpler collision approximation on the finger links and re-test the grasp.

    $ISAAC_SIM_DIR/python.sh scripts/38_collision_approx.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import UsdPhysics

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager


def main() -> int:
    with open("configs/waypoints.json", encoding="utf-8") as fh:
        waypoints = json.load(fh)
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))

    # Force a simple convex hull on the finger collision meshes.
    stage = scene.stage
    changed = 0
    for side in ("left", "right"):
        for which in ("left", "right"):
            path = f"/World/OpenArm/openarm_{side}_{which}_finger/collisions"
            prim = stage.GetPrimAtPath(path)
            if not prim.IsValid():
                continue
            mesh_api = UsdPhysics.MeshCollisionAPI(prim)
            mesh_api.GetApproximationAttr().Set("convexHull")
            changed += 1
    say(f"set convexHull on {changed} finger collision prims")

    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    spawner = FruitSpawner(scene.stage, cfg, seed=4)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()
    app_utils.update_app(steps=10)

    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=40)
    arm.teleport_joints(np.asarray(waypoints["arms"]["left"]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=60)

    sample = spawner.samples[0]
    diameter = float(os.environ.get("FRUIT_DIAMETER", "0.05"))
    sample.diameter = diameter
    from pxr import UsdGeom

    UsdGeom.Sphere(scene.stage.GetPrimAtPath(sample.prim_path)).GetRadiusAttr().Set(diameter / 2.0)
    app_utils.update_app(steps=10)

    jaw = arm.jaw_centre()
    spawner.place(sample, np.array([jaw[0], jaw[1], jaw[2] - 0.040]))
    sample.held = True
    spawner.active.append(sample)
    for _ in range(20):
        SimulationManager.step(steps=1)

    target = arm.gripper_value_for_separation(max(diameter - 0.004, 0.005))
    say(f"fruit d={diameter:.3f} closing to joint {target:.4f} (gap {diameter - 0.004:.4f} m)")
    for value in np.linspace(arm.OPEN, target, 24):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    for _ in range(60):
        SimulationManager.step(steps=1)
    say(
        f"result: jaw sep={arm.jaw_separation():.4f} "
        f"finger_q={np.round(arm.dof_positions()[arm.finger_dofs], 4).tolist()} "
        f"(commanded gap would give sep={target * 2 + 0.010:.4f})"
    )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
