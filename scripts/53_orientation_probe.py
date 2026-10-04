"""Does the orientation term of ArmController.ik_step converge or diverge?

``ik_step`` adds a rotation-vector error to the linear error when
``hold_quaternion`` is set. Which frame that vector must live in (and its sign)
depends on the convention of ``get_jacobian_matrices()``. This probe rotates the
target orientation by a known 20 degrees about world z while holding the TCP
position fixed, then reports whether the error shrinks (converges) or grows.

    $ISAAC_SIM_DIR/python.sh scripts/53_orientation_probe.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController, quaternion_error
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

V1 = json.load(open("configs/waypoints.json", encoding="utf-8"))


def qz(angle: float) -> np.ndarray:
    return np.array([np.cos(angle / 2.0), 0.0, 0.0, np.sin(angle / 2.0)])


def qmul(a, b) -> np.ndarray:
    w1, x1, y1, z1 = (float(v) for v in a)
    w2, x2, y2, z2 = (float(v) for v in b)
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ]
    )


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)

    for side, mode in (("left", "world"), ("left", "body")):
        arm = ArmController(scene, side)
        arm.teleport_joints(np.asarray(V1["arms"][side]["grasp"], dtype=float))
        for _ in range(120):
            SimulationManager.step(steps=1)
        pos0, q0 = arm.tcp_pose()
        q0 = np.asarray(q0, dtype=float)
        if mode == "world":
            target_q = qmul(qz(np.deg2rad(20.0)), q0)  # rotate about world z
        else:
            target_q = qmul(q0, qz(np.deg2rad(20.0)))  # rotate about body z
        say(f"{side}/{mode}: start angle error = "
            f"{np.rad2deg(np.linalg.norm(quaternion_error(target_q, q0))):.2f} deg")

        arm.hold_quaternion = target_q
        hold_pos = np.asarray(pos0, dtype=float)
        for step in range(400):
            arm.ik_step(hold_pos)
            SimulationManager.step(steps=1)
            if step % 50 == 0 or step == 399:
                _p, q = arm.tcp_pose()
                err = np.rad2deg(np.linalg.norm(quaternion_error(target_q, np.asarray(q, dtype=float))))
                say(f"  {side}/{mode} step {step:3d}: orientation error {err:6.2f} deg")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
