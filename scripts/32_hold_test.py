"""Hold a calibrated waypoint and report joint tracking, limits, and contacts.

    $ISAAC_SIM_DIR/python.sh scripts/32_hold_test.py
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
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile


def main() -> int:
    with open("configs/waypoints.json", encoding="utf-8") as fh:
        waypoints = json.load(fh)
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    tactile = GripperTactile()
    if os.environ.get("FRUIT_TACTILE", "1") == "1":
        tactile.attach(stage=scene.stage)
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    if os.environ.get("FRUIT_TACTILE", "1") == "1":
        tactile.refresh()

    for side in ("right",):
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=60)
        names = [f"openarm_{side}_joint{i}" for i in range(1, 8)]
        say(f"self collisions enabled: {scene.robot.get_enabled_self_collisions()}")

        for wp in ("ready", "grasp"):
            target = np.asarray(waypoints["arms"][side][wp], dtype=float)
            arm.teleport_joints(target, settle=10)
            for _ in range(120):
                app_utils.update_app(steps=1)
            actual = arm.joint_positions()
            say(f"--- {wp} ---")
            for name, t, a in zip(names, target, actual):
                say(f"   {name:24s} target={t:+.3f} actual={a:+.3f} err={a - t:+.3f}")
            say(f"   jaw={np.round(arm.jaw_centre(), 4).tolist()} sep={arm.jaw_separation():.4f}")
            say("   tactile: skipped")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
