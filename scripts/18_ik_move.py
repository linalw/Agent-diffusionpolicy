"""Move each arm's TCP to a fixed point with differential IK and log convergence.

    FRUIT_PARTS=environment,robot $ISAAC_SIM_DIR/python.sh scripts/18_ik_move.py
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

PARTS = tuple(
    p.strip()
    for p in os.environ.get("FRUIT_PARTS", "environment,pedestal,robot,conveyor,bins").split(",")
    if p.strip()
)


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=PARTS)
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)

    for side, y in (("left", 0.18), ("right", -0.18)):
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=30)
        arm.capture_hold_pose()
        goal = np.array([0.30, y, 1.20])
        say(f"{side}: start tcp={np.round(arm.tcp_position(), 4).tolist()} goal={goal.tolist()}")
        for step in range(400):
            residual = arm.ik_step(goal)
            app_utils.update_app(steps=1)
            if step % 80 == 0:
                say(
                    f"  step={step:3d} tcp={np.round(arm.tcp_position(), 4).tolist()} "
                    f"residual={residual:.4f}"
                )
            if residual < 0.012:
                break
        final = arm.tcp_position()
        say(
            f"{side}: final tcp={np.round(final, 4).tolist()} "
            f"error={np.linalg.norm(final - goal):.4f} m"
        )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
