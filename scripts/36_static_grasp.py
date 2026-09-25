"""Place a fruit exactly between the jaws and close. Isolates finger-fruit collision.

    $ISAAC_SIM_DIR/python.sh scripts/36_static_grasp.py
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
    arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=40)
    arm.teleport_joints(np.asarray(waypoints["arms"]["left"]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=60)

    sample = spawner.samples[0]
    big = float(os.environ.get("FRUIT_DIAMETER", "0"))
    if big > 0:
        from pxr import UsdGeom

        sample.diameter = big
        UsdGeom.Sphere(scene.stage.GetPrimAtPath(sample.prim_path)).GetRadiusAttr().Set(big / 2.0)
        app_utils.update_app(steps=10)
    jaw = arm.jaw_centre()
    say(f"jaw centre = {np.round(jaw, 4).tolist()}  finger sep={arm.jaw_separation():.4f}")
    from pxr import Usd, UsdGeom

    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    for link in ("openarm_left_left_finger", "openarm_left_right_finger", "openarm_left_hand"):
        rng = cache.ComputeWorldBound(scene.stage.GetPrimAtPath(f"/World/OpenArm/{link}")).ComputeAlignedRange()
        lo, hi = rng.GetMin(), rng.GetMax()
        say(
            f"  {link:26s} y=[{lo[1]:+.4f},{hi[1]:+.4f}] z=[{lo[2]:.4f},{hi[2]:.4f}] "
            f"x=[{lo[0]:+.4f},{hi[0]:+.4f}]"
        )
    say(f"fruit {sample.category} d={sample.diameter:.4f}")

    # Put the fruit exactly at the jaw centre.
    spawner._rigids[sample.index].set_world_poses(
        positions=[[float(jaw[0]), float(jaw[1]), float(jaw[2]) - 0.040]],
        orientations=[[1.0, 0.0, 0.0, 0.0]],
    )
    spawner.stop(sample)
    sample.held = True
    spawner.active.append(sample)
    for _ in range(20):
        SimulationManager.step(steps=1)
    p = spawner.position(sample)
    say(f"fruit placed at {np.round(p, 4).tolist()}  sep={arm.jaw_separation():.4f}")

    target = arm.gripper_value_for_separation(max(sample.diameter - 0.004, 0.005))
    say(f"closing to {target:.4f} (gap target {sample.diameter - 0.004:.4f} m)")
    for value in np.linspace(arm.OPEN, target, 24):
        arm.set_gripper(float(value))
        SimulationManager.step(steps=2)
    for _ in range(60):
        SimulationManager.step(steps=1)
    p2 = spawner.position(sample)
    for link in ("openarm_left_left_finger", "openarm_left_right_finger"):
        rng = cache.ComputeWorldBound(scene.stage.GetPrimAtPath(f"/World/OpenArm/{link}")).ComputeAlignedRange()
        lo, hi = rng.GetMin(), rng.GetMax()
        say(f"  post {link:26s} y=[{lo[1]:+.4f},{hi[1]:+.4f}] z=[{lo[2]:.4f},{hi[2]:.4f}]")
    say(
        f"after close: sep={arm.jaw_separation():.4f} finger_q="
        f"{np.round(arm.dof_positions()[arm.finger_dofs], 4).tolist()} "
        f"fruit={np.round(p2, 4).tolist()} moved={np.linalg.norm(p2 - p):.4f}"
    )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
