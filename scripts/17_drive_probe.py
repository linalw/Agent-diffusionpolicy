"""Check DOF drive types / control mode and confirm position targets move the arm.

    $ISAAC_SIM_DIR/python.sh scripts/17_drive_probe.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import inspect

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.scene import SortingScene
from isaacsim.core.experimental.prims import Articulation

ARM = [f"openarm_left_joint{i}" for i in range(1, 8)]


def main() -> int:
    scene = SortingScene(SceneConfig()).build(parts=("environment", "robot"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=30)
    robot = scene.robot

    say(f"get_dof_drive_types: {robot.get_dof_drive_types()}")
    say(f"switch_dof_control_mode signature: {inspect.signature(Articulation.switch_dof_control_mode)}")
    say(f"get_dof_position_targets shape: {np.asarray(robot.get_dof_position_targets().numpy()).shape}")

    names = list(robot.dof_names)
    arm_dofs = [names.index(n) for n in ARM]
    link_names = list(robot.link_names)
    tcp_idx = link_names.index("openarm_left_ee_tcp")
    jac = robot.get_jacobian_matrices().numpy()
    say(f"jacobian shape={jac.shape} norm={np.linalg.norm(jac):.4f} "
        f"tcp_block_norm={np.linalg.norm(jac[0, tcp_idx]):.4f}")
    say(f"tcp jac pos block:\n{np.round(jac[0, tcp_idx][0:3, :][:, arm_dofs], 4)}")
    tcp_before = scene.link_pose("openarm_left_ee_tcp")[0]
    say(f"tcp before: {np.round(tcp_before, 4).tolist()}")

    for mode in ("position", None):
        if mode is not None:
            try:
                robot.switch_dof_control_mode(mode, dof_indices=arm_dofs)
                say(f"switched control mode to {mode}")
            except Exception as exc:  # noqa: BLE001
                say(f"switch_dof_control_mode({mode}) failed: {exc}")

        targets = np.asarray(robot.get_dof_positions().numpy())[0].copy()
        targets[arm_dofs[0]] = 0.3
        targets[arm_dofs[2]] = -0.5
        targets[arm_dofs[3]] = 0.9
        for _ in range(240):
            robot.set_dof_position_targets([targets[arm_dofs]], dof_indices=arm_dofs)
            app_utils.update_app(steps=1)
        tcp_after = scene.link_pose("openarm_left_ee_tcp")[0]
        dof_now = np.asarray(robot.get_dof_positions().numpy())[0][arm_dofs]
        say(f"mode={mode}: dof={np.round(dof_now, 3).tolist()}")
        say(f"mode={mode}: tcp={np.round(tcp_after, 4).tolist()} moved={np.linalg.norm(tcp_after - tcp_before):.4f} m")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
