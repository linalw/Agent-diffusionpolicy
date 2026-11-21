#!/usr/bin/env python3
"""P227m: calibrate the Franka's joint waypoints to `configs/waypoints_franka.json`.

    FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 \
        scripts/run.sh logs/p227/franka_waypoints.py

`configs/waypoints.json` is the **OpenArm's** joint space; `tasks._pose` teleports
to those vectors for `ready`/`wait`/`grasp`/`grasp_lift`, so a task attempt on
the Panda starts from a nonsense configuration. This is the repo's own
calibration flow (`scripts/30_calibrate_waypoints.py`) applied to one arm, with
the differences the Panda's measurements require:

* **one arm** (the single-arm cell) and **no mirror** - `top_down_quaternion("x")`
  is the Panda's pick attitude at 0.11 deg (`logs/p227/hand_frame.log`);
* the **grasp height** is the Panda's `belt_top + 0.095` for the *fixed* pose -
  it is documented as a compromise (a fixed height holds 1/4 fruits, the moving
  catch's per-fruit standoff is what works: `logs/p227/RESULTS.md` §6), and the
  fix is the task's `_pad_standoff`, not this file;
* the **place poses are the bins** (`FRUIT_OUTPUT_BINS=1`: jaw 1.30 at
  x = -0.10, |y| = 0.55, each bin its own key), because one arm serves both.

Writes if `WAYPOINT_PATH` is unset: `configs/waypoints_franka.json`. Nothing in
`src/` is edited, and the OpenArm `configs/waypoints.json` is never touched.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.common import say  # noqa: E402
from fruit_sorting.control import ArmController, arm_specs  # noqa: E402
from fruit_sorting.motion import top_down_quaternion  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

DT = 1.0 / 120.0
OUT = os.environ.get("WAYPOINT_PATH", "configs/waypoints_franka.json")


def main() -> int:
    cfg = SceneConfig()
    if not cfg.output_bins:
        say("FRUIT_OUTPUT_BINS=1 is required (the single-arm cell's bins)")
        return 2
    scene = SortingScene(cfg).build(
        parts=("environment", "pedestal", "robot", "conveyor", "output_belts")
    )
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = float(scene.belt.belt_top)
    spec = arm_specs()[0]
    side = spec.side
    arm = ArmController(scene, side)
    arm.set_gripper(arm.OPEN)
    SimulationManager.step(steps=30)
    say(f"arm kind={os.environ.get('FRUIT_ARM_KIND')} side={side} belt_top={belt_top:.3f}")

    hold = top_down_quaternion("x")
    clearance = float(cfg.grasp_clearance)
    # The Panda's own tool geometry: pads from 11 mm above to 65 mm below the jaw
    # centre, palm 47 mm below it (`logs/p227/pad_geometry.log`), so the *fixed*
    # pose is a compromise (see the module docstring).
    goals: dict[str, tuple[np.ndarray, bool]] = {
        # name: (jaw target, hold the top-down attitude)
        "ready": (np.array([cfg.pick_x, cfg.pick_y + 0.05, belt_top + 0.20]), True),
        "grasp_lift": (np.array([cfg.pick_x, cfg.pick_y + 0.05, belt_top + 0.28]), True),
        "grasp": (np.array([cfg.pick_x, cfg.pick_y, belt_top + clearance]), True),
        # P145b's wait family (the demos' frame-0 pose), a little behind/above.
        "wait": (np.array([cfg.pick_x - 0.06, cfg.pick_y + 0.05, belt_top + 0.24]), True),
    }
    for index, sign in ((0, 1.0), (1, -1.0)):
        goals[f"bin{index}_above"] = (
            np.array([cfg.bin_center_x, sign * cfg.bin_center_y,
                      float(cfg.bin_floor_top_z) + 0.22]),
            False,
        )

    entries: dict[str, list[float]] = {}
    q_start = np.asarray(arm.joint_positions(), dtype=float)
    for name, (goal, oriented) in goals.items():
        arm.teleport_joints(np.asarray(q_start, dtype=float))
        SimulationManager.step(steps=5)
        arm.hold_quaternion = np.asarray(hold, dtype=float) if oriented else None
        # approach from above, then solve at the target (P227's staged solve)
        above = np.array([goal[0], goal[1], goal[2] + 0.10])
        arm.solve_to(above, iterations=800, tolerance=0.006, restarts=2, move_on_fail=True)
        SimulationManager.step(steps=10)
        q_sol, residual = arm.solve_to(
            goal, iterations=1500, tolerance=0.004, restarts=3, move_on_fail=True
        )
        SimulationManager.step(steps=10)
        jaw = np.asarray(arm.jaw_centre(), dtype=float)
        err = float(np.linalg.norm(jaw - goal))
        qa = np.asarray(arm.joint_positions(), dtype=float)
        margin = float(np.min(np.minimum(qa - arm.arm_lo, arm.arm_hi - qa)))
        att = arm.tcp_pose()[1] if oriented else None
        say(
            f"{name:12s} goal=({goal[0]:+.3f},{goal[1]:+.3f},{goal[2]:.3f}) "
            f"jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f}) err={err * 1e3:6.1f} mm "
            f"margin={margin:+.3f} rad "
            f"{'PASS' if err <= 0.006 and margin >= 0.05 else 'fail'}"
        )
        entries[name] = [float(v) for v in q_sol]

    payload = {
        "arm_kind": "franka",
        "belt_top": belt_top,
        "pick_x": float(cfg.pick_x),
        "pick_y": float(cfg.pick_y),
        "grasp_clearance": clearance,
        "grasp_quaternion": {
            "left": [float(v) for v in hold],
            "right": [float(v) for v in hold],
        },
        # The task always builds two controllers; on the Panda both resolve to
        # the **same** physical arm (`arm_spec` ignores the side for it), so both
        # arm labels carry this arm's configurations. The single-arm cell is then
        # one arm serving both destinations (`_place_xy_for` -> the bins).
        "arms": {"left": entries, "right": dict(entries)},
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    say(f"wrote {OUT}: keys={sorted(entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
