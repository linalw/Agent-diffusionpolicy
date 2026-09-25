"""Sweep reachable jaw-centre heights at the pick pose.

    $ISAAC_SIM_DIR/python.sh scripts/31_reach_sweep.py
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
from fruit_sorting.scene import SortingScene


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(f"belt_top={belt_top:.3f}")

    for side in ("left", "right"):
        sign = 1.0 if side == "left" else -1.0
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=60)
        for dz in (0.06, 0.08, 0.09, 0.10, 0.12, 0.16, 0.20, 0.26):
            goal = np.array([cfg.pick_x, sign * 0.02, belt_top + dz])
            config, residual = arm.solve_to(goal, iterations=900, tolerance=0.006)
            jaw = arm.jaw_centre()
            say(
                f"{side:5s} dz={dz:.2f} target_z={goal[2]:.3f} -> jaw={np.round(jaw, 3).tolist()} "
                f"residual={residual:.4f}"
            )
        app_utils.update_app(steps=30)

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
