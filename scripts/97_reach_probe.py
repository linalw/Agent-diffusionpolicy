"""Can the arm's own jaws/fingers actually reach a fruit at the pick point?

The coherent hand - pads rigidly attached to the wrist instead of a separate
floating frame - only works if some arm pose puts the *jaw centre* (and with it
the finger faces, which sit a centimetre or two below it) on the fruit. This
probe answers that with a multi-start, damped-least-squares search and reports
the best residual for a ladder of target heights, for both arms.

    $ISAAC_SIM_DIR/python.sh scripts/97_reach_probe.py

`FRUIT_HOLD=1` additionally freezes the seed's TCP orientation (position *and*
orientation IK) so the pads keep a top-down grasp attitude.
"""

from __future__ import annotations

import json
import math
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

DT = 1.0 / 120.0
#: Pads are attached at the fingertips: this far below the jaw centre [m].
FINGERTIP = float(os.environ.get("FRUIT_FINGERTIP", "0.060"))
ITERATIONS = int(os.environ.get("FRUIT_PROBE_ITERS", "260"))
SEEDS_PER_ARM = int(os.environ.get("FRUIT_PROBE_SEEDS", "10"))
Z_OFFSETS = tuple(
    float(v) for v in os.environ.get("FRUIT_PROBE_Z", "0.035,0.050,0.070").split(",")
)


def jaw_frame(arm):
    left, right = arm.jaw_positions()
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    centre = (left + right) / 2.0
    axis = right - left
    axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
    approach = arm.tcp_position() - centre
    approach = approach / max(float(np.linalg.norm(approach)), 1e-9)
    return centre, axis, approach


def seed_configs(arm, base, rng):
    """A local jitter cloud around the calibrated grasp pose plus a few random ones."""
    configs = [np.asarray(base, dtype=float)]
    span = 0.35 * (arm.arm_hi - arm.arm_lo)
    for _ in range(SEEDS_PER_ARM - 1):
        jitter = rng.uniform(-1.0, 1.0, size=base.shape) * span * 0.5
        configs.append(np.clip(np.asarray(base, dtype=float) + jitter, arm.arm_lo, arm.arm_hi))
    for _ in range(SEEDS_PER_ARM):
        configs.append(rng.uniform(arm.arm_lo * 0.5, arm.arm_hi * 0.5))
    return configs


def mirror_across_xz(q) -> np.ndarray:
    """Mirror a rotation across the x-z plane (y -> -y), as the robot's arms are."""
    w, x, y, z = (float(v) for v in q)
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    r = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )
    m = np.diag([1.0, -1.0, 1.0])
    r = m @ r @ m
    trace = float(np.trace(r))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        out = [0.25 * s, (r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s]
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = math.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2.0
        out = [(r[2, 1] - r[1, 2]) / s, 0.25 * s, (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s]
    elif r[1, 1] > r[2, 2]:
        s = math.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2.0
        out = [(r[0, 2] - r[2, 0]) / s, (r[0, 1] + r[1, 0]) / s, 0.25 * s, (r[1, 2] + r[2, 1]) / s]
    else:
        s = math.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2.0
        out = [(r[1, 0] - r[0, 1]) / s, (r[0, 2] + r[2, 0]) / s, (r[1, 2] + r[2, 1]) / s, 0.25 * s]
    out = np.asarray(out, dtype=float)
    return out / np.linalg.norm(out)


def top_down_quaternion(closing_axis: str = "x") -> np.ndarray:
    """TCP quaternion whose tool frame points the fingers straight down.

    The gripper places its pads from the *TCP* rotation: column 1 is the closing
    axis, column 2 the direction the fingers extend. A fruit on a belt wants the
    fingers pointing at the ground (column 2 = (0, 0, -1)) and the jaws closing
    horizontally; which horizontal axis they close along is free, and the two
    variants are *different* arm postures - one of them may be inside the joint
    limits while the other is not.
    """
    if closing_axis == "x":
        rot = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])
    else:
        rot = np.array([[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]])
    # Branching matrix -> quaternion (Shepperd's method); the trace here is -1, so
    # the naive formula divides by zero.
    m = rot
    if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    return np.array([w, x, y, z])


def solve(arm, seed_config, target, hold, grasp_quat=None):
    arm.teleport_joints(np.asarray(seed_config, dtype=float))
    arm.set_gripper(arm.OPEN)
    if grasp_quat is not None:
        arm.hold_quaternion = np.asarray(grasp_quat, dtype=float)
    elif hold:
        arm.capture_hold_pose()
    for _ in range(25):
        SimulationManager.step(steps=1)
    def tool_point():
        """Point the pads are attached to: the fingertips, not the jaw centre."""
        centre, _, approach = jaw_frame(arm)
        return centre - approach * FINGERTIP

    use_pad = os.environ.get("FRUIT_PROBE_TARGET", "jaw") == "pad"
    point = tool_point if use_pad else arm.jaw_centre
    best = float(np.linalg.norm(point() - target))
    best_config = arm.joint_positions().copy()
    if use_pad:
        offset = arm.tcp_position() - tool_point()
    else:
        offset = arm.tcp_position() - arm.jaw_centre()
    for i in range(ITERATIONS):
        if i % 25 == 0:
            offset = (
                arm.tcp_position() - tool_point()
                if use_pad
                else arm.tcp_position() - arm.jaw_centre()
            )
        arm.ik_step(target + offset)
        SimulationManager.step(steps=1)
        residual = float(np.linalg.norm(point() - target))
        if residual < best:
            best = residual
            best_config = arm.joint_positions().copy()
    return best, best_config


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    hold_mode = os.environ.get("FRUIT_HOLD", "0")
    fingertip_offset = FINGERTIP
    waypoints = json.load(open(os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json")))
    diameter = 0.05
    rng = np.random.default_rng(7)
    say(
        f"belt_top={belt_top:.3f} pick_x={cfg.pick_x:.3f} fruit d={diameter * 100:.0f} cm "
        f"equator_z={belt_top + diameter / 2:.3f} hold_mode={hold_mode}"
    )
    for side in ("left", "right"):
        arm = ArmController(scene, side)
        base = np.asarray(waypoints["arms"][side]["grasp"], dtype=float)
        grasp_quat = None
        if hold_mode == "grasp":
            arm.teleport_joints(base)
            for _ in range(20):
                SimulationManager.step(steps=1)
            grasp_quat = np.asarray(arm.tcp_pose()[1], dtype=float).copy()
            say(f"{side}: grasp attitude quaternion {np.round(grasp_quat, 4).tolist()}")
        elif hold_mode.startswith("topdown"):
            axis = hold_mode.split("_")[1] if "_" in hold_mode else "x"
            grasp_quat = top_down_quaternion(axis)
            if side == "left":
                # The arms are mirrored, so the left arm needs the mirrored
                # attitude; feeding both arms the right arm's quaternion made the
                # left solver drift into a near-horizontal tool (measured).
                grasp_quat = mirror_across_xz(grasp_quat)
            say(f"{side}: top-down({axis}) quaternion {np.round(grasp_quat, 4).tolist()}")
        configs = seed_configs(arm, base, rng)
        for z_offset in Z_OFFSETS:
            target = np.array([cfg.pick_x, 0.0, belt_top + diameter / 2.0 + z_offset])
            results = [solve(arm, c, target, hold_mode == "1", grasp_quat) for c in configs]
            residuals = [r for r, _ in results]
            best = float(np.min(residuals))
            best_config = results[int(np.argmin(residuals))][1]
            arm.teleport_joints(best_config)
            if grasp_quat is not None:
                arm.hold_quaternion = grasp_quat
            elif hold_mode == "1":
                arm.capture_hold_pose()
            for _ in range(25):
                SimulationManager.step(steps=1)
            centre, axis, approach = jaw_frame(arm)
            # Tool z axis as the *TCP quaternion* defines it (the direction the
            # fingers extend); a top-down grasp wants it near (0, 0, -1).
            q = np.asarray(arm.tcp_pose()[1], dtype=float)
            w, x, y, z = (float(v) for v in q)
            tool_z = np.array(
                [
                    2 * (x * z + y * w),
                    2 * (y * z - x * w),
                    1 - 2 * (x * x + y * y),
                ]
            )
            # The pads are attached at the fingertips, i.e. below the jaw centre
            # along the (jaw -> TCP) axis.
            pad_point = centre - approach * fingertip_offset
            say(
                f"{side:5s} z_off={z_offset * 100:4.1f}cm target={np.round(target, 3).tolist()} "
                f"best={best * 1000:6.1f}mm jaw={np.round(centre, 3).tolist()} "
                f"jaw_z-{belt_top + diameter / 2:+.3f}={centre[2] - (belt_top + diameter / 2):+.3f} "
                f"pad@-{fingertip_offset * 100:.0f}mm->fruit="
                f"{np.linalg.norm(pad_point - target) * 1000:6.1f}mm "
                f"approach={np.round(approach, 2).tolist()} tool_z={np.round(tool_z, 2).tolist()}"
            )
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
