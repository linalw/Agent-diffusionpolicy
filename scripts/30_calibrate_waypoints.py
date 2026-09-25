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
from fruit_sorting.scene import SortingScene

install_failure_handler("30_calibrate_waypoints")

OUT_PATH = os.environ.get("WAYPOINT_PATH", "configs/waypoints.json")
#: The fingers hang ~8 cm below the jaw centre, so the jaw cannot go lower than
#: `belt_top + 0.081` without the finger tips hitting the belt. That height also
#: straddles every fruit in the pool, so one grasp pose covers all of them.
GRASP_CLEARANCE = 0.090


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor", "bins"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0

    waypoints: dict[str, dict] = {}
    for side in ("left", "right"):
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=60)
        # Position-only IK: at run time the task plays back these joint
        # configurations, so the wrist orientation is free during calibration.
        arm.hold_quaternion = None
        side_sign = 1.0 if side == "left" else -1.0
        entries: dict[str, list[float]] = {}

        # Order matters: solve the poses nearest the default hanging pose first
        # so each solve starts from a nearby configuration.
        goals: dict[str, np.ndarray] = {
            "ready": np.array([cfg.pick_x, side_sign * 0.05, belt_top + 0.20]),
            "grasp_lift": np.array([cfg.pick_x, side_sign * 0.05, belt_top + 0.28]),
            "grasp": np.array([cfg.pick_x, 0.0, belt_top + GRASP_CLEARANCE]),
        }

        # Each arm only serves the bin on its own side: reaching across the body
        # to the far bin is outside the workspace.
        arm_bins = [0] if side == "left" else [1]
        for index in arm_bins:
            bx, by = cfg.bin_positions[index]
            bin_top = cfg.bin_stand_height + 0.04 + cfg.bin_height
            goals[f"bin{index}_above"] = np.array([bx, by, bin_top + 0.10])
            goals[f"bin{index}_inside"] = np.array([bx, by, bin_top - 0.04])

        for name, goal in goals.items():
            config, residual = arm.solve_to(
                goal, iterations=900, tolerance=0.008, restarts=6, seed=hash(name) % 1000
            )
            entries[name] = [float(v) for v in config]
            jaw = arm.jaw_centre()
            say(
                f"{side:5s} {name:16s} residual={residual:.4f} m "
                f"jaw={np.round(jaw, 4).tolist()} target={np.round(goal, 4).tolist()}"
            )

        # Arm-specific orientation hold, used to re-solve IK at run time if a
        # fruit arrives slightly off-centre.
        waypoints[side] = entries

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    payload = {
        "belt_top": belt_top,
        "pick_x": cfg.pick_x,
        "grasp_clearance": GRASP_CLEARANCE,
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
