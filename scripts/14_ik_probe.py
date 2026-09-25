"""Probe the articulation Jacobian layout and finger-joint convention.

    $ISAAC_SIM_DIR/python.sh scripts/14_ik_probe.py
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
from fruit_sorting.scene import SortingScene


def main() -> int:
    scene = SortingScene(SceneConfig()).build(parts=("environment", "robot"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    robot = scene.robot

    say(f"num_links={robot.num_links} num_dofs={robot.num_dofs} num_joints={robot.num_joints}")
    say(f"jacobian_matrix_shape={robot.jacobian_matrix_shape}")
    jac = robot.get_jacobian_matrices()
    say(f"jacobian array shape={jac.numpy().shape}")
    say(f"mass_matrix_shape={robot.mass_matrix_shape}")

    dof_names = list(robot.dof_names)
    for name in ("openarm_left_joint1", "openarm_left_finger_joint1", "openarm_left_ee_tcp_joint"):
        idx = robot.get_dof_indices(name)
        say(f"dof index {name} -> {idx.numpy().tolist()}")

    link_names = list(robot.link_names)
    say(f"links({len(link_names)}): {link_names}")
    for name in ("openarm_left_ee_tcp", "openarm_left_left_finger", "openarm_left_hand"):
        idx = robot.get_link_indices(name)
        say(f"link index {name} -> {idx.numpy().tolist()}")

    # Finger joint convention: measure finger separation at open and closed.
    finger_dofs = list(robot.get_dof_indices(
        ["openarm_left_finger_joint1", "openarm_left_finger_joint2"]
    ).numpy())
    lower = np.asarray(robot.get_dof_limits()[0].numpy())[0]
    upper = np.asarray(robot.get_dof_limits()[1].numpy())[0]

    for label, value in (("open", upper), ("closed", lower)):
        targets = np.asarray(robot.get_dof_positions().numpy())[0].copy()
        for d in finger_dofs:
            targets[d] = value[d]
        robot.set_dof_positions(targets)
        robot.set_dof_position_targets(targets)
        app_utils.update_app(steps=60)
        left, _ = scene.link_pose("openarm_left_left_finger")
        right, _ = scene.link_pose("openarm_left_right_finger")
        tip_l, _ = scene.link_pose("openarm_left_hand")
        say(
            f"gripper {label:6s}: finger sep={np.linalg.norm(left - right):.4f} m "
            f"hand_z={tip_l[2]:.4f}"
        )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
