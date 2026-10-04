"""Solve and save the joint-space waypoints used by the scripted picker.

Writes ``configs/waypoints.json``. Run again whenever the cell layout changes.

    $ISAAC_SIM_DIR/python.sh scripts/30_calibrate_waypoints.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.control import ArmController
from fruit_sorting.motion import mirror_across_xz, top_down_quaternion
from fruit_sorting.scene import SortingScene

install_failure_handler("30_calibrate_waypoints")

OUT_PATH = os.environ.get("WAYPOINT_PATH", "configs/waypoints.json")
#: Fallback only - the live value is `SceneConfig.grasp_clearance` (`FRUIT_GRASP_Z`),
#: the reachable jaw height above the belt at the pick pose with the jaws across
#: the belt (measured minimum ~0.08; see scripts/97_reach_probe.py).
GRASP_CLEARANCE = 0.09


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor", "bins"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0

    waypoints: dict[str, dict] = {}
    grasp_quaternions: dict[str, list[float]] = {}
    # The belt crosses the robot's front, so the jaws must close *across* it
    # (along X). Both arms hold a straight-down tool with that closing axis at the
    # station (2.1 mm residual, scripts/97_reach_probe.py); the left arm takes the
    # mirrored version of the right arm's attitude.
    q_ref = top_down_quaternion("x")
    for side in ("left", "right"):
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=60)
        side_sign = 1.0 if side == "left" else -1.0
        entries: dict[str, list[float]] = {}
        hold = q_ref if side == "right" else mirror_across_xz(q_ref)
        grasp_quaternions[side] = [float(v) for v in hold]

        # Order matters: solve the poses nearest the default hanging pose first
        # so each solve starts from a nearby configuration.
        clearance = float(cfg.grasp_clearance)
        goals: dict[str, np.ndarray] = {
            "ready": np.array([cfg.pick_x, cfg.pick_y + side_sign * 0.05, belt_top + 0.20]),
            "grasp_lift": np.array([cfg.pick_x, cfg.pick_y + side_sign * 0.05, belt_top + 0.28]),
            "grasp": np.array([cfg.pick_x, cfg.pick_y, belt_top + clearance]),
        }

        # Each arm only serves the output conveyor on its own side: reaching
        # across the body to the far belt is outside the workspace.
        arm_lanes = [0] if side == "left" else [1]
        for index in arm_lanes:
            px, py = cfg.output_belt_drop_points[index]
            goals[f"place{index}"] = np.array([px, py, cfg.output_place_z])

        # The pick poses hold the across-the-belt attitude; the place pose is
        # position-only (the raised belt is beside the robot, and the release
        # only needs the pads above the moving surface).
        oriented = ("ready", "grasp", "grasp_lift")
        for name, goal in goals.items():
            arm.hold_quaternion = hold if name in oriented else None
            config, residual = arm.solve_to(
                goal, iterations=900, tolerance=0.008, restarts=6, seed=hash(name) % 1000
            )
            if residual > 0.020 and name in oriented:
                # The pick poses sit near the edge of the workspace; retry from the
                # joint-limit centre so a bad local minimum does not get written.
                say(f"{side:5s} {name:16s} residual {residual:.4f} m - retrying from centre")
                centre = 0.5 * (arm.arm_lo + arm.arm_hi)
                arm.teleport_joints(centre)
                config, residual = arm.solve_to(
                    goal, iterations=1500, tolerance=0.008, restarts=2, seed=1
                )
            entries[name] = [float(v) for v in config]
            jaw = arm.jaw_centre()
            say(
                f"{side:5s} {name:16s} residual={residual:.4f} m "
                f"jaw={np.round(jaw, 4).tolist()} target={np.round(goal, 4).tolist()}"
            )
        arm.hold_quaternion = None

        # Arm-specific orientation hold, used to re-solve IK at run time if a
        # fruit arrives slightly off-centre.
        waypoints[side] = entries

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    payload = {
        "belt_top": belt_top,
        "pick_x": cfg.pick_x,
        "pick_y": cfg.pick_y,
        "grasp_clearance": float(cfg.grasp_clearance),
        "grasp_quaternion": grasp_quaternions,
        "arms": waypoints,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    say(f"wrote {OUT_PATH}")

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
