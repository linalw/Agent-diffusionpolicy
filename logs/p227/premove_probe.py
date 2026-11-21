#!/usr/bin/env python3
"""P227n: why the single-arm cell's premove stalls at one fruit x (144 mm vs 8).

    FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 \
        scripts/run.sh logs/p227/premove_probe.py

The acq-diag cell (`logs/p227/acq_diag_3_s6.log`) shows the failing attempts'
premove ending **144 mm** from its target (`jaw=[0.157, 0.111, 1.301]` against
`[0.249, 0.0, 1.297]`) while the first, fresh attempt reads **8 mm** - and the
failures correlate with the `left` label, which on this cell is the *second*
`ArmController` to drive the same physical Panda. Two candidate mechanisms:

  (H1) a **stale IK integrator**: `ArmController._q_cmd` persists across
       attempts, and the scripted moving catch deliberately skips the 40-tick
       seed *and* its `sync_command_to_measured()`. One physical arm driven by
       two controllers makes the inactive controller's command wrong by a whole
       configuration.
  (H2) a **target the servo cannot reach**: x = fruit_x = 0.249 is nearer the
       base than the station's 0.34 and the IK may sit in a local minimum.

This probe separates them with the attempt's own start pose and call
(`teleport` to the calibrated `grasp`, `move_to` 400 steps / 0.02), sweeping

  * `x` = 0.2493 (the failing target), 0.3157 (the first, working one), 0.34;
  * with the integrator **synced** to the measured joints (H1 removed) and
    **not** synced after a *foreign* command was written (H1 as it happens).

Read-only on `src/`.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import numpy as np  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.control import ArmController  # noqa: E402
from fruit_sorting.motion import top_down_quaternion  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

DT = 1.0 / 120.0
WAYPOINTS = "configs/waypoints_franka.json"


def say(text: str) -> None:
    print(f"[fruit] [pp] {text}", flush=True)


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    with open(WAYPOINTS, encoding="utf-8") as fh:
        waypoints = json.load(fh)
    grasp = np.asarray(waypoints["arms"]["left"]["grasp"], dtype=float)
    say(f"grasp config={np.round(grasp, 3).tolist()}")

    # the task builds BOTH labels on the one Panda (`ArmController(scene, side)`)
    arms = {"left": ArmController(scene, "left"), "right": ArmController(scene, "right")}
    for arm in arms.values():
        arm.set_gripper(arm.OPEN)
    SimulationManager.step(steps=30)
    hold = top_down_quaternion("x")

    def reset(arm) -> None:
        arm.teleport_joints(grasp.copy())  # the attempt's pre-pose start
        SimulationManager.step(steps=20)
        arm.hold_quaternion = np.asarray(hold, dtype=float)

    targets = [0.2493, 0.3157, 0.3400]
    z = 1.2972

    say("--- (H2) fresh controller, integrator synced by the teleport ---")
    for x in targets:
        arm = arms["left"]
        reset(arm)
        arm.sync_command_to_measured()
        err = arm.move_to(arm.tcp_target_for_jaw(np.array([x, 0.0, z])),
                          max_steps=400, tolerance=0.02)
        jaw = np.asarray(arm.jaw_centre(), dtype=float)
        say(f"x={x:.4f} tcp_res={err * 1e3:6.1f} mm jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f}) "
            f"dist={np.linalg.norm(jaw - np.array([x, 0.0, z])) * 1e3:6.1f} mm")

    say("--- (H1) integrator left stale by the OTHER controller ---")
    for x in targets:
        right, left = arms["right"], arms["left"]
        # the other label drives the shared arm first (as attempt N-1 does)
        reset(right)
        right.sync_command_to_measured()
        right.move_to(right.tcp_target_for_jaw(np.array([0.34, 0.0, z])),
                      max_steps=200, tolerance=0.02)
        # now the active label starts from the calibrated pose, but its own
        # integrator still holds wherever *it* last commanded (the startup pose)
        left.teleport_joints(grasp.copy())
        SimulationManager.step(steps=20)
        left.hold_quaternion = np.asarray(hold, dtype=float)
        err = left.move_to(left.tcp_target_for_jaw(np.array([x, 0.0, z])),
                           max_steps=400, tolerance=0.02)
        jaw = np.asarray(left.jaw_centre(), dtype=float)
        say(f"x={x:.4f} tcp_res={err * 1e3:6.1f} mm jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f}) "
            f"dist={np.linalg.norm(jaw - np.array([x, 0.0, z])) * 1e3:6.1f} mm  (no sync)")

    say("--- (H1-fix) same, one sync before the premove ---")
    for x in targets:
        right, left = arms["right"], arms["left"]
        reset(right)
        right.sync_command_to_measured()
        right.move_to(right.tcp_target_for_jaw(np.array([0.34, 0.0, z])),
                      max_steps=200, tolerance=0.02)
        left.teleport_joints(grasp.copy())
        SimulationManager.step(steps=20)
        left.hold_quaternion = np.asarray(hold, dtype=float)
        left.sync_command_to_measured()
        err = left.move_to(left.tcp_target_for_jaw(np.array([x, 0.0, z])),
                           max_steps=400, tolerance=0.02)
        jaw = np.asarray(left.jaw_centre(), dtype=float)
        say(f"x={x:.4f} tcp_res={err * 1e3:6.1f} mm jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f}) "
            f"dist={np.linalg.norm(jaw - np.array([x, 0.0, z])) * 1e3:6.1f} mm  (synced)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
