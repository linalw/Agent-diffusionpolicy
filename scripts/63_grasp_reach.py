"""Find an arm configuration that actually reaches the pick point.

The right arm's v1 grasp configuration solves IK to z ~ 1.29 m and stops there,
7 cm above the target, while the left arm's mirrored configuration reaches
1.223 m. A 0.007 rad joint difference cannot change reachability that much, so
the right arm is stuck in a local minimum and needs a better seed.

This probe solves every candidate seed for both arms and reports which ones
converge, so the waypoints file can store seeds that work.

    $ISAAC_SIM_DIR/python.sh scripts/63_grasp_reach.py
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
from fruit_sorting.control import ArmController
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

V1 = json.load(open("configs/waypoints_v1.json", encoding="utf-8"))
CUR = json.load(open("configs/waypoints.json", encoding="utf-8"))
SIGNS = np.array([-1.0, -1.0, -1.0, 1.0, -1.0, -1.0, -1.0])


def jaw_frame(arm):
    left_f, right_f = arm.jaw_positions()
    left_f = np.asarray(left_f, dtype=float)
    right_f = np.asarray(right_f, dtype=float)
    axis = right_f - left_f
    axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
    approach = arm.tcp_position() - (left_f + right_f) / 2.0
    approach = approach / max(float(np.linalg.norm(approach)), 1e-9)
    return (left_f + right_f) / 2.0, axis, approach


def try_seed(arm, seed, target, iterations=700):
    arm.teleport_joints(np.asarray(seed, dtype=float))
    arm.set_gripper(arm.OPEN)
    for _ in range(50):
        SimulationManager.step(steps=1)
    best = (float(np.linalg.norm(arm.jaw_centre() - target)), arm.joint_positions().copy())
    for _ in range(iterations):
        arm.ik_step(arm.tcp_target_for_jaw(target))
        SimulationManager.step(steps=1)
        current = float(np.linalg.norm(arm.jaw_centre() - target))
        if current < best[0]:
            best = (current, arm.joint_positions().copy())
    arm.teleport_joints(best[1])
    for _ in range(40):
        SimulationManager.step(steps=1)
    centre, axis, approach = jaw_frame(arm)
    return best[0], best[1], centre, axis, approach


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    # A 5 cm fruit is the middle of the range.
    target = np.array([cfg.pick_x, 0.0, belt_top + 0.025 + 0.003])
    say(f"belt_top={belt_top:.3f} target={np.round(target, 4).tolist()}")

    mirror_left = np.asarray(CUR["arms"]["left"]["grasp"], dtype=float) * SIGNS
    mirror_right = np.asarray(CUR["arms"]["right"]["grasp"], dtype=float) * SIGNS
    seeds = {
        "v1_right": V1["arms"]["right"]["grasp"],
        "v1_left": V1["arms"]["left"]["grasp"],
        "cur_right": CUR["arms"]["right"]["grasp"],
        "cur_left": CUR["arms"]["left"]["grasp"],
        "mirror_of_left": mirror_left.tolist(),
        "mirror_of_right": mirror_right.tolist(),
        "ready_right": V1["arms"]["right"]["ready"],
        "ready_left": V1["arms"]["left"]["ready"],
    }
    results = {}
    for side in ("left", "right"):
        arm = ArmController(scene, side)
        for name, seed in seeds.items():
            residual, config, centre, axis, approach = try_seed(arm, seed, target)
            results[(side, name)] = (residual, config)
            say(
                f"{side:5s} seed={name:15s} residual={residual * 1000:6.1f}mm "
                f"jaw={np.round(centre, 4).tolist()} axis={np.round(axis, 3).tolist()} "
                f"approach={np.round(approach, 3).tolist()}"
            )

    out = json.loads(json.dumps(CUR))
    for side in ("left", "right"):
        best = min(
            ((name, res) for (s, name), res in results.items() if s == side),
            key=lambda item: item[1][0],
        )
        say(f"{side}: best seed {best[0]} residual={best[1][0] * 1000:.1f}mm")
        out["arms"][side]["grasp"] = np.asarray(best[1][1], dtype=float).round(6).tolist()
        # Keep the lift pose consistent with the grasp pose.
        lift = np.asarray(best[1][1], dtype=float).copy()
        lift[3] = np.clip(lift[3] + 0.30, -3.0, 3.0)
        out["arms"][side]["grasp_lift"] = lift.round(6).tolist()
    with open("configs/waypoints_reach.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    say("wrote configs/waypoints_reach.json")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
