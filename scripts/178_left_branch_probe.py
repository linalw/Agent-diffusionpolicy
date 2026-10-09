#!/usr/bin/env python3
"""W1: the left arm's downstream reach, with and without the negative-q2 branch.

    scripts/run.sh scripts/178_left_branch_probe.py

The left shoulder pitch (q2) is capped at +0.1745 rad while the mirrored right
reaches +3.3161. From the calibrated grasp seed the left tracks a fruit only
~4.5 cm downstream of the station before the IK command clips at that limit
(`logs/p2b/reach_ladder.log`: 5.3 mm at y=-0.04, 21.1 mm at -0.06, then the
error grows linearly). This probe measures, on one frozen scene:

1. the **baseline ladder**: from the calibrated grasp seed with the moving-catch
   top-down hold, walk the jaw target downstream in steps and report the
   residual and q2 (the 4.5 cm number above);
2. the **bias ladder**: the same walk with `ArmController.posture_bias` set
   (the W1 nullspace posture task), for a grid of (target, gain); the bias is
   what `FRUIT_LEFT_NEGQ2=1` enables at runtime;
3. the **warm-up + bias ladder**: bias active at the station for
   `FRUIT_LEFT_PROBE_WARMUP` ticks first, then the walk - the runtime shape
   (the hover wait gives the branch time to move before the fruit arrives).

Every variant starts from a fresh teleport to the calibrated seed. Pure
positioning: the gripper is open, no fruit is touched. The `[reach]` lines are
the evidence; the caller tees them into `logs/w1/`.
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

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.control import ArmController
from fruit_sorting.motion import mirror_across_xz, top_down_quaternion
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

install_failure_handler("178_left_branch_probe")

DT = 1.0 / 120.0
FINGER = float(os.environ.get("FRUIT_FINGER_LEN", "0.060"))
PAD_LIFT = 0.010
Y_LADDER = tuple(
    float(v)
    for v in os.environ.get(
        "FRUIT_LADDER", "0,-0.02,-0.04,-0.06,-0.08,-0.10,-0.12,-0.15"
    ).split(",")
)
TICKS = int(os.environ.get("FRUIT_LADDER_TICKS", "200"))
WARMUP = int(os.environ.get("FRUIT_LEFT_PROBE_WARMUP", "60"))
#: (target, gain) grid for the bias ladder; the baseline is always run first.
BIAS_GRID = tuple(
    (float(target), float(gain))
    for target, gain in (
        pair.split(":")
        for pair in os.environ.get("FRUIT_LEFT_PROBE_GRID", "-0.6:0.05").split(",")
        if pair.strip()
    )
)
SIDES = tuple(
    s.strip()
    for s in os.environ.get("FRUIT_LEFT_PROBE_SIDE", "left").split(",")
    if s.strip()
)


def tip_point(arm) -> np.ndarray:
    centre = np.asarray(arm.jaw_centre(), dtype=float)
    q = np.asarray(arm.tcp_pose()[1], dtype=float)
    w, x, yq, zq = (float(v) for v in q)
    rot = np.array(
        [
            [1 - 2 * (yq * yq + zq * zq), 2 * (x * yq - zq * w), 2 * (x * zq + yq * w)],
            [2 * (x * yq + zq * w), 1 - 2 * (x * x + zq * zq), 2 * (yq * zq - x * w)],
            [2 * (x * zq - yq * w), 2 * (yq * zq + x * w), 1 - 2 * (x * x + yq * yq)],
        ]
    )
    return centre + rot @ np.array([0.0, 0.0, FINGER])


def clipped(arm) -> bool:
    return bool(
        np.any(arm._q_cmd < arm.arm_lo - 1e-9)
        or np.any(arm._q_cmd > arm.arm_hi + 1e-9)
    )


def multistart_branch(arm, side, seed, hold, station_y, tip_z):
    """Search for a *discrete* negative-q2 solution at the station [m].

    The nullspace bias cannot move the arm off the local IK branch (measured:
    `bias`/`bias_warm` in this probe are within 4 mm of the baseline and q2
    stays positive). This search asks the stronger question: does *any*
    configuration with q2 < -0.3 put the jaw at the station with the catch's
    top-down hold? If yes, the branch exists and a pre-rotation/seed hop is the
    implementation; if no, the positive-limit clip is a genuine boundary of the
    left arm's reachable set at this pose.
    """
    rng = np.random.default_rng(int(os.environ.get("FRUIT_LEFT_PROBE_SEED", "7")))
    trials = int(os.environ.get("FRUIT_LEFT_PROBE_TRIALS", "40"))
    target = np.array([0.34, station_y, tip_z + FINGER], dtype=float)
    best = None
    for trial in range(trials):
        if trial == 0:
            cfg = np.asarray(seed, dtype=float).copy()
        else:
            jitter = rng.uniform(-0.8, 0.8, size=7)
            cfg = np.clip(np.asarray(seed, dtype=float) + jitter, arm.arm_lo, arm.arm_hi)
            cfg[1] = float(
                -0.3
                - abs(rng.uniform(0.0, 2.4)) * (0.0 if trial % 3 else 1.0)
            )
            cfg[1] = float(np.clip(cfg[1], arm.arm_lo[1], arm.arm_hi[1]))
        arm.teleport_joints(cfg)
        arm.set_gripper(arm.OPEN)
        arm.hold_quaternion = np.asarray(hold, dtype=float)
        for _ in range(25):
            SimulationManager.step(steps=1)
        arm.solve_to(target, iterations=int(os.environ.get("FRUIT_LEFT_PROBE_ITERS", "250")), tolerance=0.006)
        residual = float(np.linalg.norm(arm.jaw_centre() - target))
        q2 = float(arm.joint_positions()[1])
        if residual < 0.006 and q2 < -0.3:
            if best is None or residual < best[0]:
                best = (residual, np.asarray(arm.joint_positions(), dtype=float).copy())
    if best is None:
        say(
            f"[reach] {side} multistart: no negative-q2 solution at the station "
            f"({trials} seeds, residual<6mm and q2<-0.3)"
        )
        return None
    say(
        f"[reach] {side} multistart: negative-q2 solution residual="
        f"{best[0] * 1000:.1f} mm q={np.round(best[1], 4).tolist()}"
    )
    return best[1]


def pinned_q2_probe(arm, side, seed, hold, station_y, tip_z):
    """Pin q2 at negative values and solve the *remaining* 6 joints for the pose.

    This is the existence proof the multi-start cannot give: with q2 fixed the
    problem still has 6 free joints for the 6-DoF pose, so a converging solve
    proves a negative-q2 solution exists (and the differential IK simply never
    takes it), while a non-converging one proves the branch is outside the
    reachable set.
    """
    target = np.array([0.34, station_y, tip_z + FINGER], dtype=float)
    lo_saved = arm.arm_lo.copy()
    hi_saved = arm.arm_hi.copy()
    try:
        for q2 in tuple(
            float(v)
            for v in os.environ.get(
                "FRUIT_LEFT_PROBE_PIN", "-0.4,-0.7,-1.0,-1.5"
            ).split(",")
        ):
            arm.arm_lo = lo_saved.copy()
            arm.arm_hi = hi_saved.copy()
            arm.arm_lo[1] = q2
            arm.arm_hi[1] = q2
            cfg = np.asarray(seed, dtype=float).copy()
            cfg[1] = q2
            arm.teleport_joints(cfg)
            arm.set_gripper(arm.OPEN)
            arm.hold_quaternion = np.asarray(hold, dtype=float)
            for _ in range(25):
                SimulationManager.step(steps=1)
            arm.solve_to(target, iterations=400, tolerance=0.006)
            residual = float(np.linalg.norm(arm.jaw_centre() - target))
            say(
                f"[reach] {side} pinned q2={q2:+.2f}: residual={residual * 1000:7.1f} mm "
                f"q={np.round(arm.joint_positions(), 4).tolist()}"
            )
    finally:
        arm.arm_lo = lo_saved
        arm.arm_hi = hi_saved
        arm.posture_bias = None


def run_ladder(arm, side, seed, hold, station_y, tip_z, bias, warmup, label):
    """Teleport to `seed`, optionally warm the bias up, walk Y_LADDER."""
    arm.teleport_joints(np.asarray(seed, dtype=float))
    arm.set_gripper(arm.OPEN)
    arm.hold_quaternion = np.asarray(hold, dtype=float)
    arm.posture_bias = None
    for _ in range(25):
        SimulationManager.step(steps=1)
    if bias is not None:
        setattr(arm, "posture_bias", (1, float(bias[0]), float(bias[1])))
        for _ in range(warmup):
            arm.ik_step(
                arm.tcp_target_for_jaw(
                    np.array([0.34, station_y, tip_z + FINGER], dtype=float)
                )
            )
            SimulationManager.step(steps=1)
    q2_start = float(arm.joint_positions()[1])
    say(
        f"[reach] {side} {label}: bias={bias} warmup={warmup} "
        f"q2_start={q2_start:+.4f} seed_jaw="
        f"{np.round(np.asarray(arm.jaw_centre(), dtype=float), 4).tolist()}"
    )
    for y in Y_LADDER:
        # Same grip height as `logs/p2b/reach_ladder.py`: the tip target is the
        # fruit equator plus the catch's pad standoff.
        desired = np.array([0.34, y, tip_z + FINGER], dtype=float)
        arm.ik_step(arm.tcp_target_for_jaw(desired))
        SimulationManager.step(steps=1)
        # Measure the *settled* step: 60 more ticks of hold at this target.
        for _ in range(60):
            arm.ik_step(arm.tcp_target_for_jaw(desired))
            SimulationManager.step(steps=1)
        centre = np.asarray(arm.jaw_centre(), dtype=float)
        tip = tip_point(arm)
        tip_desired = np.array([0.34, y, tip_z], dtype=float)
        say(
            f"[reach] {side} {label} y={y:+.3f} "
            f"residual={float(np.linalg.norm(tip - tip_desired)) * 1000:7.1f} mm "
            f"jaw=({centre[0]:.3f},{centre[1]:+.3f},{centre[2]:.3f}) "
            f"j2={float(arm.joint_positions()[1]):+.4f} "
            f"clipped={int(clipped(arm))}"
        )
    arm.posture_bias = None


def main() -> int:
    with open(
        os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json"), encoding="utf-8"
    ) as handle:
        waypoints = json.load(handle)
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    station_y = float(os.environ.get("FRUIT_LEFT_PROBE_STATION", "0.0"))
    for side in SIDES:
        arm = ArmController(scene, side)
        seed = np.asarray(waypoints["arms"][side]["grasp"], dtype=float)
        hold = top_down_quaternion(os.environ.get("FRUIT_HAND_AXIS", "x"))
        if side == "left":
            hold = mirror_across_xz(hold)
        say(
            f"[reach] {side}: limits lo={np.round(arm.arm_lo, 4).tolist()} "
            f"hi={np.round(arm.arm_hi, 4).tolist()} "
            f"station_y={station_y:+.3f} belt_top={belt_top:.3f}"
        )
        tip_z = belt_top + 0.025 + PAD_LIFT
        mode = os.environ.get("FRUIT_LEFT_PROBE_MODE", "bias")
        if mode == "pin":
            pinned_q2_probe(arm, side, seed, hold, station_y, tip_z)
        elif mode == "multistart":
            neg = multistart_branch(arm, side, seed, hold, station_y, tip_z)
            if neg is not None:
                # The decisive test: does the discrete negative-q2 branch itself
                # track downstream, or does it re-collapse onto the same limit?
                run_ladder(arm, side, neg, hold, station_y, tip_z, None, 0, "negq2_seed")
            else:
                run_ladder(
                    arm, side, seed, hold, station_y, tip_z, None, 0, "baseline"
                )
        else:
            run_ladder(arm, side, seed, hold, station_y, tip_z, None, 0, "baseline")
            for target, gain in BIAS_GRID:
                run_ladder(
                    arm, side, seed, hold, station_y, tip_z, (target, gain), 0, "bias"
                )
                run_ladder(
                    arm, side, seed, hold, station_y, tip_z, (target, gain), WARMUP,
                    "bias_warm",
                )
        arm.hold_quaternion = None
        arm.posture_bias = None
    say("[reach] DONE")
    simulation_app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
