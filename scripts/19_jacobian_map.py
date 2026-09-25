"""Map the Jacobian tensor: which rows/columns carry the TCP linear velocity.

    $ISAAC_SIM_DIR/python.sh scripts/19_jacobian_map.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.scene import SortingScene


def main() -> int:
    scene = SortingScene(SceneConfig()).build(parts=("environment", "robot"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    robot = scene.robot

    names = list(robot.dof_names)
    links = list(robot.link_names)
    tcp_idx = links.index("openarm_left_ee_tcp")
    left_arm = [names.index(f"openarm_left_joint{i}") for i in range(1, 8)]
    right_arm = [names.index(f"openarm_right_joint{i}") for i in range(1, 8)]
    left_tcp_tensor_index = tcp_idx - 1

    jac = robot.get_jacobian_matrices().numpy()[0]
    say(f"shape={jac.shape}")
    for label, lidx in (("tcp_left", tcp_idx), ("hand_left", links.index("openarm_left_hand")),
                        ("link7_left", links.index("openarm_left_link7")),
                        ("finger_left", links.index("openarm_left_left_finger"))):
        block = jac[lidx]
        say(
            f"{label:12s} total={np.linalg.norm(block):7.4f} "
            f"rows0_3={np.linalg.norm(block[0:3, :]):7.4f} rows3_6={np.linalg.norm(block[3:6, :]):7.4f} "
            f"left_arm_cols total={np.linalg.norm(block[:, left_arm]):6.3f} "
            f"row0={np.linalg.norm(block[0, left_arm]):6.3f} rows0_3={np.linalg.norm(block[0:3, left_arm]):6.3f} "
            f"rows3_6={np.linalg.norm(block[3:6, left_arm]):6.3f}"
        )

    say(f"per-row norm for tcp_left: {np.round(np.linalg.norm(jac[tcp_idx], axis=1), 4).tolist()}")
    say(f"per-col norm for tcp_left (left arm): "
        f"{np.round(np.linalg.norm(jac[tcp_idx][:, left_arm], axis=0), 4).tolist()}")
    say(f"per-col norm for tcp_left (right arm): "
        f"{np.round(np.linalg.norm(jac[tcp_idx][:, right_arm], axis=0), 4).tolist()}")

    say("--- hypothesis: jac[k] describes link_names[k+1] ---")
    for k in (19, 20, 21):
        block = jac[k]
        say(
            f"jac[{k}] (-> link_names[{k + 1}]={links[k + 1]}) "
            f"left_cols={np.linalg.norm(block[:, left_arm]):6.3f} "
            f"right_cols={np.linalg.norm(block[:, right_arm]):6.3f}"
        )

    blk = jac[left_tcp_tensor_index]
    say(f"jac[20] rows0_3 col0 = {np.round(blk[0:3, left_arm[0]], 4).tolist()}")
    say(f"jac[20] rows3_6 col0 = {np.round(blk[3:6, left_arm[0]], 4).tolist()}")
    say(f"jac[20] rows0_3 col3 = {np.round(blk[0:3, left_arm[3]], 4).tolist()}")
    say(f"jac[20] rows3_6 col3 = {np.round(blk[3:6, left_arm[3]], 4).tolist()}")

    # Try a finite-difference check: nudge joint1 and see how the TCP moves.
    base = np.asarray(robot.get_dof_positions().numpy())[0].copy()
    tcp0 = scene.link_pose("openarm_left_ee_tcp")[0]
    for joint_name, delta in (("openarm_left_joint1", 0.1), ("openarm_left_joint4", 0.1)):
        idx = names.index(joint_name)
        targets = base.copy()
        targets[idx] += delta
        robot.set_dof_positions(targets)
        robot.set_dof_position_targets(targets)
        for _ in range(90):
            robot.set_dof_position_targets([targets], dof_indices=list(range(len(names))))
            simulation_app.update()
        tcp1 = scene.link_pose("openarm_left_ee_tcp")[0]
        say(f"fd {joint_name} delta={delta}: d_tcp={np.round((tcp1 - tcp0) / delta, 4).tolist()}")
        robot.set_dof_positions(base)
        robot.set_dof_position_targets(base)
        for _ in range(90):
            simulation_app.update()

    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
