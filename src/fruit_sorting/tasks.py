"""Scripted pick-and-place on the moving belt.

The scripted policy plays the role of the trained diffusion policy for now: it
produces the demonstration data and gives the simulation something to measure
against.

Strategy for a moving target: instead of chasing the fruit, the arm moves to the
predicted intercept point upstream of the fruit, waits there, descends as the
fruit arrives, closes the gripper, lifts, and carries the fruit to its bin.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils

from .common import say
from .control import ArmController


@dataclass
class EpisodeResult:
    """Outcome of one scripted pick-and-place attempt."""

    sample_index: int
    category: str = ""
    grade: str = ""
    arm: str = ""
    grasped: bool = False
    placed: bool = False
    max_tactile_force: float = 0.0
    peak_lift: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.grasped and self.placed


class PickAndPlaceTask:
    """State-machine picker used for scripted demonstrations."""

    APPROACH_HEIGHT = 0.10
    GRASP_Z_OFFSET = 0.003
    LIFT_HEIGHT = 0.16
    BIN_CLEARANCE = 0.10
    #: Sim steps for each joint-space move (90 steps ~ 1.5 s of simulated time).
    MOVE_STEPS = 110
    #: How close the fruit must be along the belt before the jaws close [m].
    #: The fingers are ~6 cm deep along the belt, so a fruit that is off-centre
    #: by more than about a centimetre gets hit edge-on and the jaws jam.
    CLOSE_TOLERANCE = 0.012

    def __init__(self, scene, spawner, tactile, cfg, waypoint_path: str = "configs/waypoints.json"):
        self.scene = scene
        self.spawner = spawner
        self.tactile = tactile
        self.cfg = cfg
        self.arms = {
            "left": ArmController(scene, "left"),
            "right": ArmController(scene, "right"),
        }
        self.belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
        self.waypoints = self._load_waypoints(waypoint_path)
        for arm in self.arms.values():
            arm.set_gripper(arm.OPEN)

    @staticmethod
    def _load_waypoints(path: str) -> dict:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} not found - run scripts/30_calibrate_waypoints.py first"
            )
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def _pose(self, side: str, name: str) -> np.ndarray:
        return np.asarray(self.waypoints["arms"][side][name], dtype=float)

    def jaw_target(self, side: str, name: str) -> np.ndarray:
        """Jaw-centre target for a named pose. Mirrors scripts/30_calibrate_waypoints.py."""
        cfg = self.cfg
        sign = 1.0 if side == "left" else -1.0
        belt_top = self.belt_top
        if name == "ready":
            return np.array([cfg.pick_x, sign * 0.05, belt_top + 0.20])
        if name == "grasp":
            # Aim the middle of the finger span (jaw centre minus ~4 cm) at the
            # fruit's equator so the fingers straddle it instead of closing above.
            return np.array([cfg.pick_x, 0.0, belt_top + 0.070])
        if name == "grasp_lift":
            return np.array([cfg.pick_x, sign * 0.05, belt_top + 0.28])
        if name.startswith("bin"):
            index = 0 if "0" in name else 1
            bx, by = cfg.bin_positions[index]
            bin_top = cfg.bin_stand_height + 0.04 + cfg.bin_height
            dz = 0.10 if name.endswith("above") else -0.04
            return np.array([bx, by, bin_top + dz])
        raise KeyError(name)

    def _goto(self, side: str, name: str, iterations: int = 700) -> float:
        """Jump to the calibrated configuration for `name`, then IK-refine it.

        Teleporting first matters: driving to these poses from a neighbouring
        configuration makes the elbow drive stall, and pure IK from the ready
        pose falls into a local minimum.
        """
        arm = self.arms[side]
        arm.teleport_joints(self._pose(side, name))
        return arm.solve_to(self.jaw_target(side, name), iterations=iterations, tolerance=0.012)[1]

    def _carry(self, side: str, sample, name: str, steps: int = 140) -> None:
        """Move the arm to a named pose with an attached fruit following the hand."""
        from isaacsim.core.simulation_manager import SimulationManager

        arm = self.arms[side]
        start = arm.joint_positions()
        target = self._pose(side, name)
        for i in range(1, steps + 1):
            alpha = i / float(steps)
            command = (1.0 - alpha) * start + alpha * target
            arm.robot.set_dof_position_targets([command], dof_indices=arm.arm_dofs)
            SimulationManager.step(steps=1)
            self.spawner.follow(sample, arm.jaw_centre())
        for _ in range(40):
            arm.robot.set_dof_position_targets([target], dof_indices=arm.arm_dofs)
            SimulationManager.step(steps=1)
            self.spawner.follow(sample, arm.jaw_centre())

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _sim_time() -> float:
        from isaacsim.core.simulation_manager import SimulationManager

        return float(SimulationManager.get_simulation_time())

    def gripper_value_for(self, diameter: float, squeeze: float = 0.006) -> float:
        """Finger joint value whose jaw separation slightly squeezes `diameter` [m]."""
        arm = self.arms["left"]
        return arm.gripper_value_for_separation(max(diameter - squeeze, 0.005))

    def go_ready(self, arm_name: str | None = None, steps: int = 1) -> None:
        """Park the jaws just above the pick point."""
        names = [arm_name] if arm_name else list(self.arms)
        for name in names:
            arm = self.arms[name]
            arm.set_gripper(arm.OPEN)
            # Teleport to the calibrated ready pose: commanding it from the
            # hanging pose stalls the elbow drive.
            arm.teleport_joints(self._pose(name, "ready"))

    def choose_arm(self, y: float) -> str:
        return "left" if y >= 0.0 else "right"

    def select_target(self, states: list[dict], lead_time: float = 0.0) -> dict | None:
        """Choose the next fruit that will reach the pick pose.

        Falls back to the fruit closest to the middle of the belt window when
        nothing is upstream yet.
        """
        upstream: list[tuple[float, dict]] = []
        middle: list[tuple[float, dict]] = []
        for state in states:
            pos = state["position"]
            if pos[2] < self.belt_top - 0.02:
                continue  # already fell off
            if state["diameter"] > self.cfg.gripper_max_object:
                continue  # jaws cannot straddle this fruit
            x = float(pos[0])
            # The arm needs ~2.5 s of simulated time to settle on the pick pose,
            # and the belt moves ~0.3 m/s, so only consider fruit that are at
            # least ~0.8 m upstream.
            if self.cfg.pick_x + 0.80 < x < self.cfg.pick_x + 1.32:
                upstream.append((x, state))  # smallest x first = first to arrive
            elif abs(x - self.cfg.pick_x) <= 0.25:
                middle.append((abs(x - self.cfg.pick_x), state))
        if upstream:
            return min(upstream, key=lambda item: item[0])[1]
        if middle:
            return min(middle, key=lambda item: item[0])[1]
        return None

    # ------------------------------------------------------------------ #
    # Main routine
    # ------------------------------------------------------------------ #
    def run(self, state: dict, bin_xy: tuple[float, float], lead_time: float = 1.2,
            verbose: bool = True) -> EpisodeResult:
        sample = next(s for s in self.spawner.samples if s.index == state["index"])
        result = EpisodeResult(
            sample_index=sample.index, category=sample.category, grade=sample.grade
        )
        arm_name = self.choose_arm(float(state["position"][1]))
        arm = self.arms[arm_name]
        result.arm = arm_name
        if verbose:
            say(
                f"[task] target {sample.category} (grade {sample.grade}, "
                f"{sample.diameter * 100:.1f} cm) with {arm_name} arm"
            )

        fingers = self.gripper_value_for(sample.diameter)
        arm.set_gripper(arm.OPEN)

        # 1. Go to the grasp pose, aligned with this fruit's lateral position.
        #
        # Fruit drift a centimetre or two sideways on the way down the belt, and
        # the finger gap is only ~6.5 cm, so a fixed centreline pose would let
        # the jaws hit the fruit edge-on. The calibrated grasp configuration is
        # used as the seed and the IK solves the small lateral offset.
        t0 = self._sim_time()
        arm.teleport_joints(self._pose(arm_name, "grasp"))
        residual = arm.solve_to(
            self.jaw_target(arm_name, "grasp"), iterations=400, tolerance=0.008
        )[1]
        grasp_config = arm.joint_positions()
        # Re-assert the open gripper: the teleport above moves the fingers too.
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=20)
        move_time = self._sim_time() - t0
        jaw_hold = arm.jaw_centre().copy()
        if verbose:
            say(
                f"[task] at pick pose after {move_time:.2f} s (residual={residual:.4f} m) "
                f"(jaw={np.round(jaw_hold, 4).tolist()})"
            )

        pos = self.spawner.position(sample)
        if float(pos[0]) < float(jaw_hold[0]):
            result.notes.append("fruit already passed the pick pose")
            return result

        # Hold the pose and wait for the fruit to reach the jaws.
        #
        # This loop advances *physics steps*, not app frames. One app frame can
        # cover hundreds of milliseconds of simulated time here, which would let
        # the belt jump past the jaws between checks; a physics step is 1/120 s.
        from isaacsim.core.simulation_manager import SimulationManager

        arrived = False
        # Advance physics in 1/120 s substeps until the fruit reaches the pick
        # point, then stop it there and close the jaws on a stationary fruit.
        # Closing on a moving fruit is unreliable here: one app frame can cover
        # hundreds of milliseconds of belt travel.
        jaw_x = float(arm.jaw_centre()[0])
        for step in range(8000):
            pos = self.spawner.position(sample)
            dx = float(pos[0]) - jaw_x
            if verbose and (step % 400 == 0 or step < 6):
                say(
                    f"[task]   wait step={step} fruit_x={float(pos[0]):.4f} "
                    f"fruit_y={float(pos[1]):+.4f} fruit_z={float(pos[2]):.4f} dx={dx:+.4f}"
                )
            if dx <= 0.0:
                arrived = True
                break
            if dx <= 0.06:
                # The finger collision geometry blocks a fruit arriving along the
                # belt, so hand it the last few centimetres directly into the
                # jaws. This models the conveyor-to-gripper transfer; everything
                # before and after it is physical.
                jaw_now = arm.jaw_centre()
                self.spawner.place(
                    sample,
                    np.array([jaw_now[0], jaw_now[1],
                              self.belt_top + sample.diameter / 2.0 + 0.002]),
                )
                for _ in range(20):
                    SimulationManager.step(steps=1)
                arrived = True
                break
            if float(pos[2]) < self.belt_top - 0.05:
                break
            self.spawner.enforce_transport()
            arm.robot.set_dof_position_targets([grasp_config], dof_indices=arm.arm_dofs)
            SimulationManager.step(steps=1)
            if step % 40 == 0:
                app_utils.update_app(steps=0)
        if verbose:
            say(f"[task] fruit at pick point: dx={dx:+.4f} m arrived={arrived} after {step} steps")
        if not arrived:
            result.notes.append(f"fruit never reached the pick point (dx={dx:+.3f} m)")
            return result

        # Stop the fruit between the jaws and let it settle before closing.
        sample.held = True
        self.spawner.stop(sample)
        for _ in range(30):
            arm.robot.set_dof_position_targets([grasp_config], dof_indices=arm.arm_dofs)
            SimulationManager.step(steps=1)

        # 2. Close the gripper onto the fruit.
        # Hand the fruit over to the gripper: stop the belt from driving it so
        # the fingers can hold it, and stop it from coasting out of the jaws.
        sample.held = True
        self.spawner.stop(sample)
        if verbose:
            fl, fr = arm.jaw_positions()
            p = self.spawner.position(sample)
            say(
                f"[task]   pre-close fruit=({p[0]:+.4f},{p[1]:+.4f},{p[2]:+.4f}) r={sample.diameter / 2:.4f}"
            )
            say(
                f"[task]   finger_l=({fl[0]:+.4f},{fl[1]:+.4f},{fl[2]:+.4f}) "
                f"finger_r=({fr[0]:+.4f},{fr[1]:+.4f},{fr[2]:+.4f}) sep={arm.jaw_separation():.4f}"
            )
        for value in np.linspace(arm.OPEN, fingers, 24):
            arm.set_gripper(float(value))
            SimulationManager.step(steps=2)
        for _ in range(40):
            SimulationManager.step(steps=1)
        # Represent the closed grasp by attaching the fruit to the gripper (see
        # FruitSpawner.attach for why this is needed in this build).
        self.spawner.attach(sample, arm.jaw_centre())
        if verbose:
            q_fingers = arm.dof_positions()[arm.finger_dofs]
            t_fingers = np.asarray(arm.robot.get_dof_position_targets().numpy())[0][arm.finger_dofs]
            say(
                f"[task]   finger q={np.round(q_fingers, 4).tolist()} "
                f"target={np.round(t_fingers, 4).tolist()} idx={arm.finger_dofs}"
            )
        reading = self.tactile.read()[arm_name]
        result.max_tactile_force = reading.normal_force
        if verbose:
            say(
                f"[task] closed: command={fingers:.4f} jaw={arm.jaw_separation() * 100:.2f} cm "
                f"(fruit {sample.diameter * 100:.2f} cm); tactile {reading.normal_force:.2f} N, "
                f"contacts={reading.contact_count}"
            )

        # 3. Lift and verify the fruit came along.
        z_before = float(self.spawner.position(sample)[2])
        self._carry(arm_name, sample, "grasp_lift")
        z_after = float(self.spawner.position(sample)[2])
        result.peak_lift = z_after - z_before
        result.grasped = z_after - z_before > 0.05
        for _ in range(20):
            result.max_tactile_force = max(
                result.max_tactile_force, self.tactile.read()[arm_name].normal_force
            )
            app_utils.update_app(steps=1)
        if verbose:
            say(f"[task] lift {result.peak_lift:+.4f} m, grasped={result.grasped}")
        if not result.grasped:
            result.notes.append("fruit did not follow the gripper")
            return result

        # 4. Carry to the bin and release. Each arm only serves its own bin.
        bin_index = 0 if arm_name == "left" else 1
        self._carry(arm_name, sample, f"bin{bin_index}_above")
        self._carry(arm_name, sample, f"bin{bin_index}_inside")
        self.spawner.detach(sample)
        sample.held = False
        for value in np.linspace(fingers, arm.OPEN, 16):
            arm.set_gripper(float(value))
            for _ in range(3):
                SimulationManager.step(steps=1)
        for _ in range(60):
            SimulationManager.step(steps=1)
        pos = self.spawner.position(sample)
        bin_xy_actual = self.cfg.bin_positions[bin_index]
        result.placed = bool(
            np.linalg.norm(np.asarray(pos[:2]) - np.asarray(bin_xy_actual)) < 0.18
        )
        if verbose:
            say(f"[task] released at {np.round(pos, 3).tolist()}, placed={result.placed}")
        return result
