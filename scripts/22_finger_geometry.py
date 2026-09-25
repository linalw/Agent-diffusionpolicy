"""Measure finger link bounding boxes and the reachable jaw height at the pick pose.

    $ISAAC_SIM_DIR/python.sh scripts/22_finger_geometry.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Usd, UsdGeom

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.scene import SortingScene


def bbox(stage, path):
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.proxy])
    rng = cache.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
    return np.array(rng.GetMin()), np.array(rng.GetMax())


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)

    for side in ("left",):
        for link in ("hand", "left_finger", "right_finger", "ee_tcp", "link7"):
            lo, hi = bbox(scene.stage, f"/World/OpenArm/openarm_{side}_{link}")
            say(f"{link:13s} z=[{lo[2]:.4f},{hi[2]:.4f}] y=[{lo[1]:.4f},{hi[1]:.4f}] x=[{lo[0]:.4f},{hi[0]:.4f}]")

    # How low can the jaw centre go at the pick pose?
    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=30)
    for target_z in (1.00, 1.02, 1.04, 1.06, 1.08, 1.10, 1.12):
        goal = np.array([0.28, 0.0, target_z])
        offset = arm.tcp_position() - arm.jaw_centre()
        for _ in range(260):
            arm.ik_step(goal + offset)
            app_utils.update_app(steps=1)
            if np.linalg.norm(arm.jaw_centre() - goal) < 0.008:
                break
        jaw = arm.jaw_centre()
        say(
            f"target_z={target_z:.3f} -> jaw={np.round(jaw, 4).tolist()} "
            f"err={np.linalg.norm(jaw - goal):.4f}"
        )

    lo, hi = bbox(scene.stage, "/World/OpenArm/openarm_left_left_finger")
    say(f"final finger z span=[{lo[2]:.4f},{hi[2]:.4f}] jaw_z={arm.jaw_centre()[2]:.4f}")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
