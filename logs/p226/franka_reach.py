#!/usr/bin/env python3
"""P227b: the Panda's IK reach to the pick and the two side bins (the layout gate).

    FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 FRUIT_FRANKA_BASE_Z=0.79 \
        scripts/run.sh logs/p226/franka_reach.py

Builds the scene, drives an `ArmController` with the Panda spec to each target
(position-only, the shipped place leg's own solve), and prints the residual and
the smallest joint-limit margin - the P90 criterion (6 mm, 0.05 rad) applied to
the new arm and the new cell.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import numpy as np  # noqa: E402

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.common import say  # noqa: E402
from fruit_sorting.control import ArmController  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(
        parts=("environment", "pedestal", "robot", "conveyor", "output_belts")
    )
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=30)
    belt_top = float(scene.belt.belt_top)
    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)
    q0 = np.asarray(arm.joint_positions(), dtype=float)
    say(f"[reach] kind={os.environ.get('FRUIT_ARM_KIND')} q0={np.array2string(q0, precision=3)}")
    targets = {
        "pick": (float(cfg.pick_x), float(cfg.pick_y), belt_top + 0.03),
        "binP": (float(cfg.bin_center_x), float(cfg.bin_center_y), float(cfg.bin_floor_top_z) + 0.10),
        "binN": (float(cfg.bin_center_x), -float(cfg.bin_center_y), float(cfg.bin_floor_top_z) + 0.10),
    }
    for name, target in targets.items():
        target = np.asarray(target, dtype=float)
        # The repo's calibration solver (multi-restart, position-only) is the
        # right instrument for a *layout* question: it answers "does a
        # configuration exist", which is what the waypoints need.
        arm.teleport_joints(np.asarray(q0, dtype=float))
        arm.hold_quaternion = None
        q_sol, err_solve = arm.solve_to(
            target, iterations=1500, tolerance=0.004, restarts=3, move_on_fail=True
        )
        app_utils.update_app(steps=5)
        qa = np.asarray(arm.joint_positions(), dtype=float)
        margin = float(np.min(np.minimum(qa - arm.arm_lo, arm.arm_hi - qa)))
        # and the incremental servo from the current configuration, for the
        # loop the place leg actually runs
        arm.teleport_joints(np.asarray(q0, dtype=float))
        arm.hold_quaternion = None
        arm.sync_command_to_measured()
        err_step = float("inf")
        for _ in range(900):
            err_step = arm.ik_step(arm.tcp_target_for_jaw(target))
            app_utils.update_app(steps=1)
            if err_step <= 0.003:
                break
        # The number that matters is the **jaw** error: `ik_step`/`solve_to`
        # return the TCP residual, and the TCP<->jaw offset rotates with the
        # wrist, so a TCP residual is not a jaw error.
        jaw = np.asarray(arm.jaw_centre(), dtype=float)
        err_jaw = float(np.linalg.norm(jaw - target))
        say(
            f"[reach] {name:4s} target=({target[0]:+.3f},{target[1]:+.3f},{target[2]:.3f}) "
            f"jaw_err={err_jaw * 1e3:7.1f} mm at ({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f})  "
            f"tcp_res={err_step * 1e3:6.1f} mm  margin={margin:+.3f} rad  "
            f"{'PASS' if err_jaw <= 0.006 and margin >= 0.05 else 'fail'}"
        )
    simulation_app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
