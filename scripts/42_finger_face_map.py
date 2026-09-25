"""Measure the true gap between the finger FACES as a function of the jaw command.

Uses a fresh BBoxCache each time so the numbers are not stale.

    $ISAAC_SIM_DIR/python.sh scripts/42_finger_face_map.py
"""

from __future__ import annotations

import json
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
from isaacsim.core.simulation_manager import SimulationManager


def face_gap(stage, side: str) -> tuple[float, float, float]:
    """Returns (gap between inner faces, left face y, right face y)."""
    ranges = []
    for which in ("left", "right"):
        path = f"/World/OpenArm/openarm_{side}_{which}_finger"
        cache = UsdGeom.BBoxCache(
            Usd.TimeCode.Default(), [UsdGeom.Tokens.default_]
        )
        rng = cache.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
        ranges.append((rng.GetMin(), rng.GetMax()))
    (lo_l, hi_l), (lo_r, hi_r) = ranges
    # inner face of the left finger is its +y end, of the right finger its -y end
    left_inner = hi_l[1]
    right_inner = lo_r[1]
    return right_inner - left_inner, left_inner, right_inner


def main() -> int:
    with open("configs/waypoints.json", encoding="utf-8") as fh:
        waypoints = json.load(fh)
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)

    arm = ArmController(scene, "left")
    arm.teleport_joints(np.asarray(waypoints["arms"]["left"]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(80):
        SimulationManager.step(steps=1)

    say("joint | origin_sep | face_gap | fruit diameter that would be gripped")
    for value in (0.044, 0.038, 0.032, 0.026, 0.020, 0.014, 0.008, 0.002, 0.0):
        arm.set_gripper(value)
        for _ in range(90):
            SimulationManager.step(steps=1)
        gap, left_inner, right_inner = face_gap(scene.stage, "left")
        q = arm.dof_positions()[arm.finger_dofs]
        say(
            f"{value:5.3f} | {arm.jaw_separation() * 100:6.2f}cm | {gap * 100:6.2f}cm | "
            f"{gap * 100:6.2f}cm   (q={np.round(q, 4).tolist()}, "
            f"faces y=[{left_inner * 100:+.2f},{right_inner * 100:+.2f}]cm)"
        )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
