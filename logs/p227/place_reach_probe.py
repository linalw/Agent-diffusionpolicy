#!/usr/bin/env python3
"""P227n: can the Panda **servo** into each side bin with the payload, and where not?

    FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 \
        scripts/run.sh logs/p227/place_reach_probe.py

The left label now grasps (the mirrored attitude was the blocker) but its place
leg stalls: `carry place0` ends at `jaw=[-0.177, +0.180, 1.603]` against
`(-0.10, +0.55)` at z 1.38, then the payload drops to the floor
(`logs/p227/attempt_6_s6_fix2.log`), while the right label places into its own
bin. P227e measured the *solve* (a position-only multi-restart reaches 2.6-3.2 mm
at every cell), but the place leg runs an **incremental servo** from the lift
pose with the payload - which can stall at a joint limit the solve steps over.

This probe drives that servo exactly (`move_to`, the carry's own primitive):
start at the calibrated `grasp_lift` pose, attitude released (the place is
position-only), and sweep the bins' x (P227e's validated band -0.10..0.06) x
|y| 0.55 x z {1.38, 1.30}, for **both** signs, printing the residual, the jaw
and the tightest joint.
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
from fruit_sorting.scene import SortingScene  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402

DT = 1.0 / 120.0
WAYPOINTS = "configs/waypoints_franka.json"


def say(text: str) -> None:
    print(f"[fruit] [pr] {text}", flush=True)


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(
        parts=("environment", "pedestal", "robot", "conveyor", "output_belts")
    )
    scene.start(physics_dt=DT, warmup_steps=60)
    with open(WAYPOINTS, encoding="utf-8") as fh:
        waypoints = json.load(fh)
    lift = np.asarray(waypoints["arms"]["left"]["grasp_lift"], dtype=float)
    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)
    SimulationManager.step(steps=20)
    say(f"bins: x={cfg.bin_center_x:+.3f} |y|={cfg.bin_center_y:.3f} "
        f"place_z={cfg.output_place_z:.3f} floor={cfg.bin_floor_top_z:.3f} rim={cfg.bin_floor_top_z + cfg.bin_wall_height:.3f}")

    transfer_lift = float(os.environ.get("FRUIT_OPENARM_TRANSFER_LIFT", "0.08"))
    conditioned = os.environ.get("PROBE_TRANSFER_LIFT")
    if conditioned is not None:
        transfer_lift = float(conditioned)
    xs = [float(v) for v in os.environ.get("PROBE_X", "-0.10,-0.02,0.06").split(",")]
    zs = [float(v) for v in os.environ.get("PROBE_Z", "1.38,1.30").split(",")]
    ys = [float(v) for v in os.environ.get("PROBE_Y", "0.55").split(",")]

    for z in zs:
        for y in ys:
            for x in xs:
                for sign in (1.0, -1.0):
                    arm.teleport_joints(np.asarray(lift, dtype=float))
                    SimulationManager.step(steps=20)
                    arm.hold_quaternion = None
                    arm.sync_command_to_measured()
                    target = np.array([x, sign * y, z])
                    err = arm.move_to(arm.tcp_target_for_jaw(target),
                                      max_steps=900, tolerance=0.01)
                    jaw = np.asarray(arm.jaw_centre(), dtype=float)
                    qa = np.asarray(arm.joint_positions(), dtype=float)
                    margins = np.minimum(qa - arm.arm_lo, arm.arm_hi - qa)
                    worst = int(np.argmin(margins))
                    dist = float(np.linalg.norm(jaw - target))
                    say(
                        f"place sign={'+' if sign > 0 else '-'} x={x:+.2f} z={z:.2f} "
                        f"jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f}) "
                        f"dist={dist * 1e3:6.1f} mm tcp_res={err * 1e3:6.1f} mm "
                        f"margin={margins[worst]:+.4f}@j{worst + 1} "
                        f"{'PASS' if dist <= 0.012 else 'fail'}"
                    )
    if os.environ.get("PROBE_STAGED", "0") == "1":
        say("--- staged / seeded forms for the +Y bin ---")
        for x in xs:
            for sign in (1.0,):
                target = np.array([x, sign * y, zs[0]])
                # (1) staged: lift -> above the bin (z + 0.15) -> target
                arm.teleport_joints(np.asarray(lift, dtype=float))
                SimulationManager.step(steps=20)
                arm.hold_quaternion = None
                arm.sync_command_to_measured()
                above = target + np.array([0.0, 0.0, 0.15])
                e1 = arm.move_to(arm.tcp_target_for_jaw(above), max_steps=900, tolerance=0.01)
                e2 = arm.move_to(arm.tcp_target_for_jaw(target), max_steps=600, tolerance=0.01)
                jaw = np.asarray(arm.jaw_centre(), dtype=float)
                say(f"staged x={x:+.2f} above_res={e1 * 1e3:6.1f} mm "
                    f"jaw_above_done=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f}) "
                    f"final_dist={np.linalg.norm(jaw - target) * 1e3:6.1f} mm tcp_res={e2 * 1e3:6.1f} mm")
                # (2) seeded: the calibration's own bin_above joint configuration
                key = "bin0_above" if sign > 0 else "bin1_above"
                seed = np.asarray(waypoints["arms"]["left"][key], dtype=float)
                arm.teleport_joints(seed.copy())
                SimulationManager.step(steps=20)
                arm.hold_quaternion = None
                arm.sync_command_to_measured()
                e3 = arm.move_to(arm.tcp_target_for_jaw(target), max_steps=400, tolerance=0.01)
                jaw = np.asarray(arm.jaw_centre(), dtype=float)
                say(f"seeded x={x:+.2f} ({key}) dist={np.linalg.norm(jaw - target) * 1e3:6.1f} mm "
                    f"tcp_res={e3 * 1e3:6.1f} mm jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f})")
    if os.environ.get("PROBE_ROUTE", "").strip():
        say("--- routed Cartesian transits (lift -> route -> bin) ---")
        routes = [
            [float(v) for v in r.split(",")]
            for r in os.environ["PROBE_ROUTE"].split(";")
            if r.strip()
        ]
        for x in xs:
            for sign in (1.0, -1.0):
                target = np.array([x, sign * y, zs[0]])
                for route in routes:
                    arm.teleport_joints(np.asarray(lift, dtype=float))
                    SimulationManager.step(steps=20)
                    arm.hold_quaternion = None
                    arm.sync_command_to_measured()
                    way = np.array([route[0], sign * route[1], route[2]])
                    e1 = arm.move_to(arm.tcp_target_for_jaw(way), max_steps=900, tolerance=0.01)
                    jaw1 = np.asarray(arm.jaw_centre(), dtype=float)
                    e2 = arm.move_to(arm.tcp_target_for_jaw(target), max_steps=700, tolerance=0.01)
                    jaw = np.asarray(arm.jaw_centre(), dtype=float)
                    say(
                        f"route sign={'+' if sign > 0 else '-'} x={x:+.2f} "
                        f"via=({way[0]:+.2f},{way[1]:+.2f},{way[2]:.2f}) "
                        f"via_dist={np.linalg.norm(jaw1 - way) * 1e3:6.1f} mm "
                        f"final_dist={np.linalg.norm(jaw - target) * 1e3:6.1f} mm "
                        f"jaw=({jaw[0]:+.3f},{jaw[1]:+.3f},{jaw[2]:.3f})"
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
