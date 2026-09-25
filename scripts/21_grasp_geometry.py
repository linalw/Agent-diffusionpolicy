"""Measure the TCP -> jaw-centre offset and the finger-joint -> jaw-separation map.

    $ISAAC_SIM_DIR/python.sh scripts/21_grasp_geometry.py
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
    names = list(robot.dof_names)

    for side in ("left", "right"):
        tcp = scene.link_pose(f"openarm_{side}_ee_tcp")[0]
        hand = scene.link_pose(f"openarm_{side}_hand")[0]
        fl = scene.link_pose(f"openarm_{side}_left_finger")[0]
        fr = scene.link_pose(f"openarm_{side}_right_finger")[0]
        jaw = (fl + fr) / 2.0
        say(
            f"{side}: tcp={np.round(tcp, 4).tolist()} hand={np.round(hand, 4).tolist()} "
            f"finger_l={np.round(fl, 4).tolist()} finger_r={np.round(fr, 4).tolist()}"
        )
        say(
            f"{side}: jaw_centre={np.round(jaw, 4).tolist()} "
            f"tcp->jaw={np.round(jaw - tcp, 4).tolist()} |tcp->jaw|={np.linalg.norm(jaw - tcp):.4f} "
            f"separation={np.linalg.norm(fl - fr):.4f}"
        )

        j1 = names.index(f"openarm_{side}_finger_joint1")
        j2 = names.index(f"openarm_{side}_finger_joint2")
        base = np.asarray(robot.get_dof_positions().numpy())[0].copy()
        for value in (0.0, 0.011, 0.022, 0.033, 0.044):
            targets = base.copy()
            targets[j1] = value
            targets[j2] = value
            robot.set_dof_positions(targets)
            robot.set_dof_position_targets(targets)
            for _ in range(90):
                app_utils.update_app(steps=1)
            fl = scene.link_pose(f"openarm_{side}_left_finger")[0]
            fr = scene.link_pose(f"openarm_{side}_right_finger")[0]
            q = np.asarray(robot.get_dof_positions().numpy())[0]
            jaw = (fl + fr) / 2.0
            tcp = scene.link_pose(f"openarm_{side}_ee_tcp")[0]
            say(
                f"  cmd={value:.3f} q1={q[j1]:+.4f} q2={q[j2]:+.4f} "
                f"separation={np.linalg.norm(fl - fr):.4f} "
                f"tcp->jaw={np.round(jaw - tcp, 4).tolist()}"
            )
        robot.set_dof_positions(base)
        robot.set_dof_position_targets(base)
        app_utils.update_app(steps=30)

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
