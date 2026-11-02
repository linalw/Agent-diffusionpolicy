#!/usr/bin/env python3
"""P106 pre-flight: what units does *this* articulation API report?

The Allegro USD authors its revolute limits in **degrees** (USD Physics spec) while
the OpenArm asset's limits are authored in radians. Whether the tensor API converts
or not decides every number downstream - the mount's curl command, the drive
torque, and whether the hand's own limits are inside or outside its posture - so
it is measured before the mount is trusted.

    FRUIT_FINGER_COLLIDERS=0 P106_PHASE=U scripts/run.sh logs/p106/m1_mount_probe.py
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 200, "height": 150})

import numpy as np

from isaacsim.core.simulation_manager import SimulationManager

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.fdlimit import raise_fd_limit
from fruit_sorting.scene import SortingScene

raise_fd_limit()


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "robot"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=30)
    robot = scene.robot
    names = list(robot.dof_names)
    lo = np.asarray(robot.get_dof_limits()[0].numpy())[0]
    hi = np.asarray(robot.get_dof_limits()[1].numpy())[0]
    q = np.asarray(robot.get_dof_positions().numpy())[0]
    for name in ("openarm_left_joint1", "openarm_left_joint2", "openarm_left_joint4",
                 "openarm_left_finger_joint1", "openarm_left_hand"):
        i = names.index(name)
        say(f"[p106] {name:28s} q0={q[i]:+9.5f} limit=({lo[i]:+9.5f},{hi[i]:+9.5f})")

    # Command a known target and read it back: the conversion factor is the answer.
    for name, val in (("openarm_left_joint1", 0.3), ("openarm_left_finger_joint1", 0.03)):
        i = names.index(name)
        before = float(np.asarray(robot.get_dof_positions().numpy())[0][i])
        robot.set_dof_position_targets(np.array([[val]]), dof_indices=np.array([i]))
        for _ in range(240):
            SimulationManager.step(steps=1)
        after = float(np.asarray(robot.get_dof_positions().numpy())[0][i])
        say(f"[p106] {name:28s} command {val:+.3f} : {before:+.5f} -> {after:+.5f} "
            f"(ratio {abs(after-before)/max(abs(val-before),1e-9):.3f})")
        robot.set_dof_position_targets(np.array([[before]]), dof_indices=np.array([i]))
        for _ in range(120):
            SimulationManager.step(steps=1)
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    sys.exit(code)
