#!/usr/bin/env python3
"""P227l: can the Panda's servo reach down to the pick point, and if not, why?

    FRUIT_ARM_KIND=franka scripts/run.sh logs/p227/ik_probe.py

P227d/P227f/P227g read the Panda's *position-only solve* as 15.6 mm high at the
pick, and P227i's grasp probe measured the incremental servo stalling ~24 mm
short of the same point - which is the difference between "the station is out of
reach" and "the servo cannot get there". This probe separates them: it walks the
jaw target down in 20 mm steps from 1.32 to 1.20 at the pick column, holds the
top-down attitude, and prints the **achieved** jaw, the residual, the smallest
joint-limit margin and the worst joint's index, for

  * the asset's arm drive (`k = 22918, c = 4583` - the Panda's own), and
  * the repo's tuned Cartesian drive (`FRUIT_TUNE_GAINS`' pair, k = 1500,
    c = 60), which the OpenArm path already uses.

Read-only on `src/`.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import numpy as np  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.control import ArmController, quaternion_error  # noqa: E402
from fruit_sorting.motion import top_down_quaternion  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

DT = 1.0 / 120.0


def say(text: str) -> None:
    print(f"[fruit] [ik] {text}", flush=True)


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = float(scene.belt.belt_top)
    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)

    # a grasp configuration to start from (the staged solve)
    target = np.array([cfg.pick_x, cfg.pick_y, belt_top + float(cfg.grasp_clearance)])
    q0 = np.asarray(arm.joint_positions(), dtype=float)
    arm.teleport_joints(q0)
    arm.hold_quaternion = None
    arm.solve_to(np.array([target[0], target[1], target[2] + 0.12]),
                 iterations=600, tolerance=0.006, restarts=1, move_on_fail=True)
    SimulationManager.step(steps=5)
    q_grasp, _ = arm.solve_to(target, iterations=1500, tolerance=0.004, restarts=2,
                              move_on_fail=True)
    SimulationManager.step(steps=5)
    say(f"start conf jaw={np.round(np.asarray(arm.jaw_centre()), 3)}")

    hold = top_down_quaternion("x")

    def sweep(label: str, k: float | None, c: float | None, steps: int = 400) -> None:
        if k:
            arm.robot.set_dof_gains(k, c, dof_indices=arm.arm_dofs)
        arm.teleport_joints(np.asarray(q_grasp, dtype=float))
        SimulationManager.step(steps=10)
        arm.hold_quaternion = np.asarray(hold, dtype=float)
        arm.sync_command_to_measured()
        for z in (1.32, 1.30, 1.28, 1.26, 1.24, 1.22, 1.20):
            goal = np.array([target[0], target[1], z])
            tcp_goal = arm.tcp_target_for_jaw(goal)
            for _ in range(steps):
                arm.ik_step(tcp_goal)
                SimulationManager.step(steps=1)
            jaw = np.asarray(arm.jaw_centre(), dtype=float)
            qa = np.asarray(arm.joint_positions(), dtype=float)
            margins = np.minimum(qa - arm.arm_lo, arm.arm_hi - qa)
            worst = int(np.argmin(margins))
            att = float(np.linalg.norm(quaternion_error(hold, arm.tcp_pose()[1])))
            say(
                f"{label} goal_z={z:.3f} jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f}) "
                f"dz={jaw[2] - z:+.4f} dxy={np.linalg.norm(jaw[:2] - goal[:2]) * 1e3:5.1f}mm "
                f"att={np.degrees(att):5.2f}deg margin={margins[worst]:+.4f}@j{worst + 1}"
            )

    sweep("asset   ", None, None)
    sweep("tuned   ", 1500.0, 60.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
