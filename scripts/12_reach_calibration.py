"""Sample the OpenArm bimanual reachable workspace to place the conveyor correctly.

    $ISAAC_SIM_DIR/python.sh scripts/12_reach_calibration.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import random

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import OPENARM_TCP_LINKS, SceneConfig
from fruit_sorting.common import say
from fruit_sorting.scene import SortingScene

SAMPLES = int(os.environ.get("REACH_SAMPLES", "150"))


def main() -> int:
    scene = SortingScene(SceneConfig()).build(parts=("environment", "robot"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    robot = scene.robot

    joints = list(robot.joint_names)
    lower = np.asarray(robot.get_dof_limits()[0].numpy())[0]
    upper = np.asarray(robot.get_dof_limits()[1].numpy())[0]
    limits = {name: (float(lower[i]), float(upper[i])) for i, name in enumerate(joints)}

    # Shoulder positions are the world pose of link1 for each side.
    shoulders = {}
    for side in ("left", "right"):
        pose, _ = scene.link_pose(f"openarm_{side}_link1")
        shoulders[side] = pose
        say(f"shoulder {side} origin at {np.round(pose, 4).tolist()}")

    rng = random.Random(0)
    kept: dict[str, list[np.ndarray]] = {"left": [], "right": []}
    targets = np.zeros(len(joints))
    for _ in range(SAMPLES):
        for i, name in enumerate(joints):
            lo, hi = limits[name]
            if "finger" in name or name.endswith("_hand") or "ee_tcp" in name:
                targets[i] = lo
            else:
                targets[i] = rng.uniform(lo + 0.1 * (hi - lo), hi - 0.1 * (hi - lo))
        robot.set_dof_positions(targets)
        robot.set_dof_position_targets(targets)
        app_utils.update_app(steps=2)
        for side, link in OPENARM_TCP_LINKS.items():
            pose, _ = scene.link_pose(link)
            kept[side].append(pose)

    for side in ("left", "right"):
        pts = np.asarray(kept[side])
        shoulder = shoulders[side]
        rel = pts - shoulder
        radius = np.linalg.norm(rel, axis=1)
        say(
            f"{side:5s} TCP reach: radius max={radius.max():.3f} m "
            f"p90={np.percentile(radius, 90):.3f} m"
        )
        say(
            f"{side:5s} world bbox x=[{pts[:, 0].min():+.3f},{pts[:, 0].max():+.3f}] "
            f"y=[{pts[:, 1].min():+.3f},{pts[:, 1].max():+.3f}] "
            f"z=[{pts[:, 2].min():+.3f},{pts[:, 2].max():+.3f}]"
        )
        forward = pts[(rel[:, 0] > 0.15) & (pts[:, 2] > 0.55)]
        if forward.size:
            say(
                f"{side:5s} forward-down samples={len(forward)} "
                f"x=[{forward[:, 0].min():.3f},{forward[:, 0].max():.3f}] "
                f"z=[{forward[:, 2].min():.3f},{forward[:, 2].max():.3f}] "
                f"|y|max={np.abs(forward[:, 1]).max():.3f}"
            )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
