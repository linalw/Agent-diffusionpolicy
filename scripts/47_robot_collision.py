"""Does the robot collide with anything at all in the current scene?

    $ISAAC_SIM_DIR/python.sh scripts/47_robot_collision.py
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

CONFIG = json.load(open("configs/waypoints.json"))


def main() -> int:
    cfg = SceneConfig()
    # `FRUIT_PARTS` lets this probe drop the conveyor: the first run showed the jaw
    # stopped 8 cm above the belt top with the finger bounding boxes overlapping it,
    # so "with conveyor" vs "without conveyor" is what attributes the stop.
    parts = tuple(
        piece.strip()
        for piece in os.environ.get(
            "FRUIT_PARTS", "environment,pedestal,robot,conveyor"
        ).split(",")
        if piece.strip()
    )
    scene = SortingScene(cfg).build(parts=parts)
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    arm = ArmController(scene, "left")
    belt = getattr(scene, "belt", None)
    belt_top = belt.belt_top if belt is not None else float("nan")
    say(f"parts={parts} belt top {belt_top:.3f}; robot base z={cfg.robot_base_z}")

    # Drive the TCP straight down into the belt and see whether it is stopped.
    arm.teleport_joints(np.asarray(CONFIG["arms"]["left"]["grasp"], dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(60):
        SimulationManager.step(steps=1)
    start = arm.jaw_centre().copy()
    say(f"start jaw {np.round(start, 3).tolist()}")
    target = start + np.array([0.0, 0.0, -0.35])
    offset = arm.tcp_position() - arm.jaw_centre()
    for i in range(700):
        arm.ik_step(target + offset)
        SimulationManager.step(steps=1)
    end = arm.jaw_centre()
    say(
        f"after driving down: jaw {np.round(end, 3).tolist()} "
        f"(target {np.round(target, 3).tolist()}, belt top {belt_top:.3f})"
    )
    say("if the robot collides with the belt, the jaw stops above the belt top")

    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    for link in ("openarm_left_left_finger", "openarm_left_right_finger"):
        rng = cache.ComputeWorldBound(scene.stage.GetPrimAtPath(f"/World/OpenArm/{link}")).ComputeAlignedRange()
        lo, hi = rng.GetMin(), rng.GetMax()
        say(f"  {link:28s} y=[{lo[1]:+.4f},{hi[1]:+.4f}] z=[{lo[2]:.4f},{hi[2]:.4f}] x=[{lo[0]:+.4f},{hi[0]:+.4f}]")
    say(f"  jaw centre now {np.round(arm.jaw_centre(), 4).tolist()} sep={arm.jaw_separation():.4f}")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
