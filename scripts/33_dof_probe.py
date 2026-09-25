"""Probe DOF ordering and whether set_dof_positions/set_dof_position_targets apply.

    $ISAAC_SIM_DIR/python.sh scripts/33_dof_probe.py
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
    scene = SortingScene(SceneConfig()).build(parts=("environment", "robot"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    robot = scene.robot
    names = list(robot.dof_names)
    say(f"dof_names: {names}")
    arm = ArmController(scene, "right")
    say(f"right arm_dofs: {arm.arm_dofs}")
    say(f"right arm_idx via get_dof_indices: {robot.get_dof_indices([f'openarm_right_joint{i}' for i in range(1, 8)]).numpy().tolist()}")

    target_idx = names.index("openarm_right_joint4")
    say(f"index of openarm_right_joint4 in dof_names = {target_idx}")

    # 1) set_dof_positions on a 1-D array
    q = np.asarray(robot.get_dof_positions().numpy())[0].copy()
    q[target_idx] = 1.0
    robot.set_dof_positions(q)
    robot.set_dof_position_targets(q)
    app_utils.update_app(steps=60)
    after = np.asarray(robot.get_dof_positions().numpy())[0]
    say(f"1D set_dof_positions: q[{target_idx}]={after[target_idx]:+.4f}")

    # 2) set_dof_position_targets with dof_indices
    q2 = np.asarray(robot.get_dof_positions().numpy())[0].copy()
    q2[target_idx] = 0.6
    robot.set_dof_position_targets([[0.6]], dof_indices=[target_idx])
    app_utils.update_app(steps=60)
    after2 = np.asarray(robot.get_dof_positions().numpy())[0]
    say(f"targets via dof_indices: q[{target_idx}]={after2[target_idx]:+.4f}")

    # 3) set_dof_positions with 2-D array
    q3 = np.asarray(robot.get_dof_positions().numpy()).copy()
    q3[0, target_idx] = 0.9
    robot.set_dof_positions(q3)
    robot.set_dof_position_targets(q3)
    app_utils.update_app(steps=60)
    after3 = np.asarray(robot.get_dof_positions().numpy())[0]
    say(f"2D set_dof_positions: q[{target_idx}]={after3[target_idx]:+.4f}")

    # 4) gripper: command both grippers closed and read back
    for side in ("left", "right"):
        side_arm = ArmController(scene, side)
        finger_idx = side_arm.finger_dofs
        say(f"{side} finger_dofs={finger_idx}")
        for value in (0.044, 0.02, 0.005, 0.0):
            robot.set_dof_position_targets([[value] * len(finger_idx)], dof_indices=finger_idx)
            app_utils.update_app(steps=40)
            q = np.asarray(robot.get_dof_positions().numpy())[0]
            say(
                f"  {side} cmd={value:.3f} -> q={np.round(q[finger_idx], 4).tolist()} "
                f"separation={side_arm.jaw_separation():.4f}"
            )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
