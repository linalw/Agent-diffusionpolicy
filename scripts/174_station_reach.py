"""Measure the reachable lateral band at the pick station (v9/V1 supply).

    scripts/run.sh scripts/174_station_reach.py

The scattered supply draws each fruit's across-the-belt (x) offset from
`FRUIT_SUPPLY_X_MIN/MAX` (default x = 0.20-0.36 m). The moving catch descends
onto the fruit's *measured* x with the top-down grasp attitude, so the scatter
is only valid if the arm can put the jaw centre on those positions at the pick
height. `scripts/12_reach_calibration.py`/`97_reach_probe.py` measured the
*centre* station (2.1-8 mm residual) and a forward-down world bbox, not this
band.

This probe seeds every solve from the calibrated grasp pose (a cold start put
the right arm in a local minimum, 114-438 mm on every dx) and solves the
position IK for the jaw centre at ``(pick_x + dx, pick_y, belt_top + Z)`` -
the grip height the catch uses - for a ladder of dx, both arms. Run it and set
`FRUIT_SUPPLY_X_MIN/MAX` to the band whose residual stays inside the catch-up
tolerance (6 mm) with margin.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.control import ArmController
from fruit_sorting.motion import mirror_across_xz, top_down_quaternion
from fruit_sorting.scene import SortingScene

install_failure_handler("174_station_reach")

DT = 1.0 / 120.0
#: The ladder starts below the *delivered* lateral edge: the scatter draws
#: x in [0.20, 0.36], but the belt's own drift carries fruit to x = 0.148
#: (measured, `logs/v1/12b_supply_after_free.log`), so x = 0.10-0.18 (dx =
#: -0.24..-0.16) must be probed too - the original ladder stopped at x = 0.18
#: and that gap was called out in review.
DX = tuple(
    float(v)
    for v in os.environ.get("FRUIT_REACH_DX", "-0.24,-0.22,-0.20,-0.18,-0.16,-0.12,-0.08,-0.05,-0.03,0,0.03,0.05,0.08,0.12,0.16").split(",")
)
#: Station Y offsets to probe (v9/V2 two-line stations: the left at 0.0, the
#: right at -0.20). The catch's grip pose is station-relative, so the reach
#: that matters is `(pick_x + dx, pick_y + dy)` for each arm.
DY = tuple(
    float(v)
    for v in os.environ.get("FRUIT_REACH_DY", "0").split(",") if v.strip()
)
#: Optional arm filter ("left" or "right"): the two-line geometry needs the
#: right arm's downstream reach ladder and the left's cross-body limit, and
#: the probes are the slow part of the run.
SIDES = tuple(
    side.strip()
    for side in os.environ.get("FRUIT_REACH_SIDE", "left,right").split(",")
    if side.strip()
)
Z_OFFSET = float(os.environ.get("FRUIT_REACH_Z", "0.09"))


def main() -> int:
    with open(
        os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json"), encoding="utf-8"
    ) as handle:
        waypoints = json.load(handle)
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(f"[reach] belt_top={belt_top:.3f} pick=({cfg.pick_x:.3f},{cfg.pick_y:.3f}) z_off={Z_OFFSET:.2f}")
    for side in SIDES:
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=40)
        hold = top_down_quaternion(os.environ.get("FRUIT_HAND_AXIS", "x"))
        if side == "left":
            hold = mirror_across_xz(hold)
        seed = np.asarray(waypoints["arms"][side]["grasp"], dtype=float)
        for dy in DY:
            for dx in DX:
                arm.teleport_joints(seed)
                arm.hold_quaternion = hold
                arm.set_gripper(arm.OPEN)
                app_utils.update_app(steps=20)
                target = np.array(
                    [cfg.pick_x + dx, cfg.pick_y + dy, belt_top + Z_OFFSET], dtype=float
                )
                config, residual = arm.solve_to(target, iterations=400, tolerance=0.006)
                jaw = arm.jaw_centre()
                say(
                    f"[reach] {side:5s} dy={dy:+.2f} dx={dx:+.2f} "
                    f"residual={residual * 1000:6.1f} mm "
                    f"jaw=[{jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f}]"
                )
        arm.hold_quaternion = None
        app_utils.update_app(steps=30)
    say("[reach] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

