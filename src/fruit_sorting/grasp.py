"""Deterministic grasp primitive.

The physical grasp needs several deterministic steps that a diffusion policy
cannot reasonably learn from a handful of episodes (and that a real cell would
implement in firmware anyway):

1. index the line and seat the fruit on the pick nest,
2. servo the *pads* onto the fruit (they sit ~1 cm along the approach axis from
   the jaw-centre origin, and the arm's IK lands a few millimetres short),
3. close with a force budget instead of a position target,
4. load the grip until the pads actually hold the fruit,
5. verify with a small test lift and re-close if the fruit did not follow.

Extracted from `PickAndPlaceTask` so both the scripted demonstrator and the
policy evaluator use exactly the same grasp. See WORKLOG (2026-09-26) for the
measurements behind every constant.
"""

from __future__ import annotations

import os

import numpy as np
from pxr import Usd, UsdGeom

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.rendering_manager import RenderingManager
from isaacsim.core.simulation_manager import SimulationManager

from .common import say


def pads_mid(stage, side: str, arm, pad_forward: float, band_centre: float) -> np.ndarray:
    """World position of the midpoint between the two fingertip pads.

    Prefers the *actual* pad prims: they are children of the finger links, so
    their world offset rotates with the wrist. Estimating it as
    ``jaw + approach * forward + (0, 0, band)`` is only exact at the pose the
    pads were calibrated at, and a 15 deg wrist difference moves it by more than
    a centimetre - which is enough for the pads to close on air (the 0 N
    failures in logs/134-135).
    """
    if stage is not None:
        mids = []
        for which in ("left", "right"):
            path = f"/World/OpenArm/openarm_{side}_{which}_finger/grasp_pad"
            prim = stage.GetPrimAtPath(path)
            if not prim.IsValid():
                mids = []
                break
            matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
            mids.append(np.array(matrix).reshape(4, 4).T[0:3, 3])
        if len(mids) == 2:
            return (mids[0] + mids[1]) / 2.0
    return (
        arm.jaw_centre()
        + arm.approach_axis() * pad_forward
        + np.array([0.0, 0.0, band_centre])
    )


class GraspPrimitive:
    """Contact grasp of one fruit sitting on the pick nest."""

    def __init__(self, cfg, spawner, arm, tactile, arm_name: str, waypoints: dict | None = None):
        self.cfg = cfg
        self.spawner = spawner
        self.arm = arm
        self.stage = getattr(spawner, "stage", None)
        self.tactile = tactile
        self.arm_name = arm_name
        self.waypoints = waypoints
        self.belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
        self.seat_z = self.belt_top + float(getattr(cfg, "nest_height", 0.0))
        self.pad_forward = float(os.environ.get("FRUIT_PAD_FORWARD", "0.010"))
        self.band_centre = (
            float(os.environ.get("FRUIT_PAD_LO", "-0.045"))
            + float(os.environ.get("FRUIT_PAD_HI", "0.012"))
        ) / 2.0
        self.last_note = ""

    # ------------------------------------------------------------------ #
    def fruit_free_point(self, sample) -> np.ndarray:
        """Where the fruit should sit: pick nest centre line, equator up."""
        return np.array(
            [self.cfg.pick_x, self.cfg.pick_y, self.seat_z + sample.diameter / 2.0]
        )

    def pads_mid(self) -> np.ndarray:
        return pads_mid(self.stage, self.arm.spec.side, self.arm, self.pad_forward, self.band_centre)

    def seat(self, sample, verbose: bool = True) -> bool:
        """Index the line, put the fruit on the nest and keep it there."""
        belt = getattr(self.spawner, "belt", None)
        if belt is not None:
            belt.hold()
        free = self.fruit_free_point(sample)
        self.spawner.place(sample, free)
        sample.held = True
        for _ in range(30):
            SimulationManager.step(steps=1)
        # A 2 cm ridge cannot always keep a sphere: re-seat it if it rolled off,
        # otherwise the pads close on the old position with zero contact.
        seated = True
        for _ in range(int(os.environ.get("FRUIT_RESEATS", "2"))):
            pos = np.asarray(self.spawner.position(sample), dtype=float)
            on_nest = float(pos[2]) >= free[2] - 0.010
            centred = float(np.linalg.norm(pos[:2] - free[:2])) < 0.012
            if on_nest and centred:
                break
            self.spawner.place(sample, free)
            for _ in range(30):
                SimulationManager.step(steps=1)
        else:
            pos = np.asarray(self.spawner.position(sample), dtype=float)
            seated = (
                float(pos[2]) >= free[2] - 0.010
                and float(np.linalg.norm(pos[:2] - free[:2])) < 0.012
            )
        self.spawner.stop(sample)
        if verbose:
            say(
                f"[grasp] seated {sample.category} at "
                f"{np.round(self.spawner.position(sample), 4).tolist()} seated={seated}"
            )
        return seated

    def aim_pads(self, sample, seed_goal=None, verbose: bool = True):
        """Servo the pads onto the fruit; returns (goal, aligned, residual)."""
        # Start from the calibrated grasp pose: the policy leaves the arm wherever
        # its last actions took it, and solving from there lands in a local
        # minimum (residuals of 86-171 mm in logs/128).
        if self.waypoints is not None:
            seed = self.waypoints["arms"][self.arm_name]["grasp"]
            self.arm.teleport_joints(np.asarray(seed, dtype=float))
            for _ in range(40):
                SimulationManager.step(steps=1)
        # Aim at where the fruit *is*, not where it was supposed to be: it rolls
        # and slides a few millimetres on the nest, and aiming at the nominal point
        # is what produced the 0 N "closed on air" failures.
        # Nominal nest centre: chasing the fruit's measured position pushed the
        # pick pose out of reach (logs/137); the seating check below keeps the
        # fruit within 12 mm of this point instead.
        free = self.fruit_free_point(sample) + np.array([0.0, 0.0, 0.003])
        goal = free if seed_goal is None else np.asarray(seed_goal, dtype=float)
        aligned = False
        residual = float("inf")
        alignment = (0.0, 0.0, 0.0)
        for _ in range(3):
            residual = self.arm.solve_to(goal, iterations=300, tolerance=0.004)[1]
            if residual > 0.012:
                # The pick pose sits near the edge of the workspace, so the plain
                # solve lands in a local minimum; the scripted pipeline falls back
                # to random restarts here and the primitive has to do the same.
                residual = self.arm.solve_to(
                    goal, iterations=400, tolerance=0.004, restarts=4, seed=7
                )[1]
            axis = self.arm.jaw_axis()
            approach = self.arm.approach_axis()
            error = free - self.pads_mid()
            lateral = float(error @ axis)
            forward = float(error @ approach)
            vertical = float(error[2])
            alignment = (lateral, forward, vertical)
            if abs(lateral) < 0.008 and abs(forward) < 0.020 and -0.015 < vertical < 0.020:
                aligned = True
                break
            goal = goal + axis * lateral + approach * forward
            if verbose:
                say(
                    f"[grasp] realigning: lateral={lateral * 1000:+.1f} "
                    f"forward={forward * 1000:+.1f} vertical={vertical * 1000:+.1f} mm"
                )
        self.last_note = (
            f"align lateral={alignment[0] * 1000:+.1f}mm forward={alignment[1] * 1000:+.1f}mm "
            f"vertical={alignment[2] * 1000:+.1f}mm residual={residual * 1000:.1f}mm"
        )
        return goal, aligned, residual

    def approach(self, sample, verbose: bool = True) -> np.ndarray:
        """Two-stage approach: hover above the fruit, then descend vertically.

        Descending along a slanted path sweeps the pads sideways into the fruit
        and knocks it off the nest (the small-fruit failures in logs/140-141). A
        vertical descent keeps the pads clear until they are level with the fruit.
        """
        free = self.fruit_free_point(sample) + np.array([0.0, 0.0, 0.003])
        hover = free.copy()
        hover[2] += float(os.environ.get("FRUIT_HOVER", "0.0"))
        if hover[2] <= free[2]:
            # Hover is off by default: the two-stage approach measured *worse*
            # than a single gentle descent (0/8 vs 2/8 on the small-fruit probe,
            # logs/141 vs /143), so the vertical descent stays behind a flag.
            self.arm.max_step = float(os.environ.get("FRUIT_APPROACH_STEP", "0.08"))
            self.arm.move_to(
                self.arm.tcp_target_for_jaw(free), max_steps=600, tolerance=0.006
            )
            return free
        previous = self.arm.max_step
        self.arm.max_step = float(os.environ.get("FRUIT_HOVER_STEP", "0.20"))
        self.arm.move_to(self.arm.tcp_target_for_jaw(hover), max_steps=500, tolerance=0.008)
        self.arm.max_step = float(os.environ.get("FRUIT_APPROACH_STEP", "0.08"))
        self.arm.move_to(self.arm.tcp_target_for_jaw(free), max_steps=500, tolerance=0.006)
        self.arm.max_step = previous
        if verbose:
            say(
                f"[grasp] approached: hover={np.round(hover, 4).tolist()} "
                f"jaw={np.round(self.arm.jaw_centre(), 4).tolist()}"
            )
        return free

    def close(self, sample) -> float:
        """Force-limited close followed by loading the grip."""
        squeeze = float(os.environ.get("FRUIT_SQUEEZE", "0.90"))
        block_stop = float(os.environ.get("FRUIT_BLOCK_STOP", "0.030"))
        target_gap = self.arm.gripper_value_for_separation(sample.diameter * squeeze)
        value = self.arm.OPEN
        over_force = 0
        force_limit = float(
            np.clip(
                sample.mass * 9.81 * float(os.environ.get("FRUIT_FORCE_FACTOR", "100")),
                25.0,
                60.0,
            )
        )
        for value in np.linspace(self.arm.OPEN, target_gap, 90):
            self.arm.set_gripper(float(value))
            SimulationManager.step(steps=2)
            expected = self.arm.JAW_SEPARATION_OFFSET + 2.0 * float(value)
            blocked = (self.arm.jaw_separation() - expected) > block_stop
            reading = self.tactile.read()[self.arm_name].normal_force
            over_force = over_force + 1 if reading >= force_limit else 0
            if blocked or over_force >= 3:
                break
        # Load the grip: the first close stops at the first sign of the joints
        # being blocked, which leaves the fruit lightly loaded and it slips.
        force_target = float(np.clip(sample.mass * 9.81 * 60.0, 20.0, 40.0))
        # The pads have to end up within ~2 mm of the fruit's diameter. Stopping
        # merely because the force reading stalled left grips at 8-9 N that then
        # slipped (logs/146: right arm, both pad gaps within 2 mm, still dropped).
        gap_target = sample.diameter - 0.002
        reading = self.tactile.read()[self.arm_name].normal_force
        for load_step in range(40):
            if reading >= force_target or value <= 0.0:
                break
            previous = reading
            value = max(0.0, value - 0.001)
            self.arm.set_gripper(float(value))
            for _ in range(6):
                SimulationManager.step(steps=1)
            reading = self.tactile.read()[self.arm_name].normal_force
            closed_enough = (
                self.arm.jaw_separation() - 2.0 * float(os.environ.get("FRUIT_PAD_RADIUS", "0.010"))
            ) <= gap_target
            if (
                load_step > 10
                and closed_enough
                and abs(reading - previous) < 0.5
                and reading < 2.0
            ):
                break
        return float(value)

    def run(self, sample, verbose: bool = True) -> bool:
        """Full grasp: seat, aim, close, load, verify (with re-grasp)."""
        if not self.seat(sample, verbose=verbose):
            self.last_note = "fruit would not stay on the pick nest"
            return False
        self.approach(sample, verbose=verbose)
        goal, aligned, _residual = self.aim_pads(sample, verbose=verbose)
        if not aligned:
            return False
        fingers = self.close(sample)
        # Verify with a 1 cm test lift; if the fruit does not follow, squeeze and
        # try again (slip detection + re-grasp, as a real cell would).
        for _regrasp in range(int(os.environ.get("FRUIT_REGRASPS", "3"))):
            z0 = float(self.spawner.position(sample)[2])
            probe = goal + np.array([0.0, 0.0, 0.010])
            for _ in range(40):
                self.arm.ik_step(self.arm.tcp_target_for_jaw(probe))
                SimulationManager.step(steps=1)
            followed = float(self.spawner.position(sample)[2]) - z0 > 0.004
            for _ in range(40):
                self.arm.ik_step(self.arm.tcp_target_for_jaw(goal))
                SimulationManager.step(steps=1)
            if followed:
                self.last_note = f"held at {self.tactile.read()[self.arm_name].normal_force:.1f}N"
                return True
            fingers = float(fingers) - float(os.environ.get("FRUIT_REGRASP_STEP", "0.003"))
            for _ in range(60):
                self.arm.set_gripper(fingers)
                SimulationManager.step(steps=1)
        self.last_note = "fruit slipped after loading"
        return False
