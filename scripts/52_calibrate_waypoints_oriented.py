"""Re-solve the pick waypoints with an explicit gripper orientation.

The v1 waypoints came from position-only IK, which leaves the wrist free. As a
result the two grippers ended up in different orientations at the "grasp" pose:
the right gripper's jaws open roughly along -y, the left gripper's open up and
forward ([-0.35, 0.33, 0.88]), so the left jaws are one above the other and can
never close on a fruit that is resting on the belt.

This script keeps the right arm's calibrated orientation as the reference,
mirrors it across the x-z plane for the left arm, and re-solves every waypoint
with 6-DoF IK so that both grippers approach the fruit the same way.

    $ISAAC_SIM_DIR/python.sh scripts/52_calibrate_waypoints_oriented.py
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

V1 = json.load(open("configs/waypoints.json", encoding="utf-8"))
#: Written separately: the pipeline keeps using waypoints.json until the new
#: orientation-constrained poses have been validated by a physical grasp test.
OUT = "configs/waypoints_oriented.json"


def quat_to_mat(q):
    w, x, y, z = (float(v) for v in q)
    n = np.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def mat_to_quat(r):
    trace = float(np.trace(r))
    if trace > 0.0:
        s = np.sqrt(trace + 1.0) * 2.0
        q = [0.25 * s, (r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s]
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = np.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2.0
        q = [(r[2, 1] - r[1, 2]) / s, 0.25 * s, (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s]
    elif r[1, 1] > r[2, 2]:
        s = np.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2.0
        q = [(r[0, 2] - r[2, 0]) / s, (r[0, 1] + r[1, 0]) / s, 0.25 * s, (r[1, 2] + r[2, 1]) / s]
    else:
        s = np.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2.0
        q = [(r[1, 0] - r[0, 1]) / s, (r[0, 2] + r[2, 0]) / s, (r[1, 2] + r[2, 1]) / s, 0.25 * s]
    q = np.asarray(q, dtype=float)
    return q / np.linalg.norm(q)


def mirror_across_y(q):
    """Mirror a rotation across the x-z plane (the robot's symmetry plane)."""
    r = quat_to_mat(q)
    m = np.diag([1.0, -1.0, 1.0])
    return mat_to_quat(m @ r @ m)


def jaw_target(cfg, side: str, name: str) -> np.ndarray:
    """Same geometry as PickAndPlaceTask.jaw_target (kept in sync by hand)."""
    sign = 1.0 if side == "left" else -1.0
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    if name == "ready":
        return np.array([cfg.pick_x, sign * 0.05, belt_top + 0.20])
    if name == "grasp":
        return np.array([cfg.pick_x, 0.0, belt_top + 0.055])
    if name == "grasp_lift":
        return np.array([cfg.pick_x, sign * 0.05, belt_top + 0.28])
    if name.startswith("place") or name.startswith("bin"):
        index = 0 if "0" in name else 1
        px, py = cfg.output_belt_drop_points[index]
        return np.array([px, py, cfg.output_place_z])
    raise KeyError(name)


def solve(arm, target, quat, warm, iterations=1500, tol=0.005):
    arm.teleport_joints(np.asarray(warm, dtype=float))
    arm.hold_quaternion = np.asarray(quat, dtype=float)
    residual = float("inf")
    for _ in range(iterations):
        arm.ik_step(arm.tcp_target_for_jaw(target))
        SimulationManager.step(steps=1)
        residual = float(np.linalg.norm(arm.jaw_centre() - target))
        if residual <= tol:
            break
    return arm.joint_positions().copy(), residual


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0

    arms = {side: ArmController(scene, side) for side in ("left", "right")}

    # Reference orientation: the right arm's calibrated grasp pose, untouched.
    right = arms["right"]
    right.teleport_joints(np.asarray(V1["arms"]["right"]["grasp"], dtype=float))
    for _ in range(60):
        SimulationManager.step(steps=1)
    _pos, q_ref = right.tcp_pose()
    say(f"reference (right arm) tcp quaternion = {np.round(q_ref, 4).tolist()}")
    say(f"mirrored  (left arm)  tcp quaternion = {np.round(mirror_across_y(q_ref), 4).tolist()}")

    # Keep everything that already works (ready, the place poses, the metadata) and
    # re-solve only the two poses that define the grasp itself.
    out = json.loads(json.dumps(V1))
    solved = ("grasp", "grasp_lift")
    for side in ("left", "right"):
        arm = arms[side]
        quat = q_ref if side == "right" else mirror_across_y(q_ref)
        for name in solved:
            target = jaw_target(cfg, side, name)
            config, residual = solve(arm, target, quat, V1["arms"][side][name])
            if residual > 0.012:
                say(f"{side} {name}: retrying from the joint-limit centre")
                centre = 0.5 * (arm.arm_lo + arm.arm_hi)
                config, residual = solve(arm, target, quat, centre, iterations=2500)
            # Report the gripper geometry that this solution produces.
            left_f, right_f = arm.jaw_positions()
            axis = np.asarray(right_f) - np.asarray(left_f)
            axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
            say(
                f"{side:5s} {name:12s} residual={residual * 1000:6.1f}mm "
                f"jaw={np.round(arm.jaw_centre(), 3).tolist()} "
                f"axis={np.round(axis, 3).tolist()}"
            )
            out["arms"][side][name] = np.asarray(config, dtype=float).round(6).tolist()
    # Record the orientation the waypoints were solved against, so the runtime
    # can pin the same wrist orientation.
    out["grasp_quaternion"] = {
        "right": [float(v) for v in q_ref],
        "left": [float(v) for v in mirror_across_y(q_ref)],
    }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    say(f"wrote {OUT}")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
