"""Joint-space control helpers: damped least-squares Cartesian IK and gripper control."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.experimental.prims import RigidPrim

from .common import say, to_numpy


def quaternion_error(target: np.ndarray, current: np.ndarray) -> np.ndarray:
    """Rotation vector that takes `current` to `target`; quaternions are (w, x, y, z)."""
    w1, x1, y1, z1 = (float(v) for v in target)
    w2, x2, y2, z2 = (float(v) for v in current)
    # target * conjugate(current)
    w = w1 * w2 + x1 * x2 + y1 * y2 + z1 * z2
    x = -w1 * x2 + x1 * w2 - y1 * z2 + z1 * y2
    y = -w1 * y2 + x1 * z2 + y1 * w2 - z1 * x2
    z = -w1 * z2 - x1 * y2 + y1 * x2 + z1 * w2
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    angle = 2.0 * np.arccos(float(np.clip(w, -1.0, 1.0)))
    sin_half = float(np.sqrt(max(1.0 - w * w, 0.0)))
    if sin_half < 1e-8:
        return np.zeros(3)
    return angle * np.array([x, y, z]) / sin_half


@dataclass
class ArmSpec:
    side: str
    arm_joint_names: list[str]
    finger_joint_names: list[str]
    tcp_link: str


def arm_spec(side: str) -> ArmSpec:
    return ArmSpec(
        side=side,
        arm_joint_names=[f"openarm_{side}_joint{i}" for i in range(1, 8)],
        finger_joint_names=[f"openarm_{side}_finger_joint{i}" for i in (1, 2)],
        tcp_link=f"openarm_{side}_ee_tcp",
    )


class ArmController:
    """Damped least-squares differential IK for one OpenArm arm.

    Position-only control: the gripper keeps the configuration it starts in,
    which for this robot is a downward-pointing parallel gripper - exactly what
    is wanted for top-down grasping of round fruit.
    """

    #: Finger joint value for a fully open gripper [m].
    OPEN = 0.044
    #: Finger joint value for a fully closed gripper [m].
    CLOSED = 0.0
    #: Measured on the asset (scripts/21_grasp_geometry.py):
    #: jaw separation = JAW_SEPARATION_OFFSET + JAW_SEPARATION_PER_JOINT * q
    JAW_SEPARATION_OFFSET = 0.010
    JAW_SEPARATION_PER_JOINT = 2.0

    def __init__(
        self,
        scene,
        side: str,
        damping: float | None = None,
        gain: float | None = None,
        max_step: float | None = None,
    ):
        import os

        damping = float(os.environ.get("FRUIT_IK_DAMPING", 0.05)) if damping is None else damping
        gain = float(os.environ.get("FRUIT_IK_GAIN", 1.0)) if gain is None else gain
        max_step = float(os.environ.get("FRUIT_IK_MAX_STEP", 0.5)) if max_step is None else max_step
        self.scene = scene
        self.robot = scene.robot
        self.spec = arm_spec(side)
        self.damping = damping
        self.gain = gain
        self.max_step = max_step
        self._debug_steps = int(__import__("os").environ.get("FRUIT_IK_DEBUG", "0"))
        self.hold_quaternion: np.ndarray | None = None
        #: Incremental IK integrator. Advancing the *commanded* joints (rather
        #: than re-deriving from the lagging measured position every step) is
        #: what makes the servo converge instead of oscillating.
        self._q_cmd: np.ndarray | None = None

        names = list(self.robot.dof_names)
        self.arm_dofs = [names.index(n) for n in self.spec.arm_joint_names]
        self.finger_dofs = [names.index(n) for n in self.spec.finger_joint_names]
        links = list(self.robot.link_names)
        self.tcp_link_index = links.index(self.spec.tcp_link)
        # `Articulation.get_jacobian_matrices()` returns one 6 x n_dof block per
        # link *excluding the base link*, i.e. block k describes
        # `link_names[k + 1]`. Verified numerically in
        # scripts/19_jacobian_map.py against a finite-difference Jacobian.
        self.tcp_jacobian_index = self.tcp_link_index - 1
        paths = self.robot.link_paths
        if paths and isinstance(paths[0], (list, tuple)):
            paths = paths[0]
        path = paths[self.tcp_link_index]
        if isinstance(path, (list, tuple)):
            path = path[0]
        self._tcp_prim = RigidPrim(str(path))

        self._finger_prims = []
        for link_name in (f"openarm_{side}_left_finger", f"openarm_{side}_right_finger"):
            path = paths[links.index(link_name)]
            if isinstance(path, (list, tuple)):
                path = path[0]
            self._finger_prims.append(RigidPrim(str(path)))

        limits_lo = np.asarray(self.robot.get_dof_limits()[0].numpy())[0]
        limits_hi = np.asarray(self.robot.get_dof_limits()[1].numpy())[0]
        self.arm_lo = limits_lo[self.arm_dofs]
        self.arm_hi = limits_hi[self.arm_dofs]
        self.finger_lo = limits_lo[self.finger_dofs]
        self.finger_hi = limits_hi[self.finger_dofs]
        # Both fingers are commanded to the same value, so stay inside the
        # intersection of their ranges.
        self.open_value = float(np.min(self.finger_hi))
        self.closed_value = float(np.max(self.finger_lo))

        # The asset ships with very stiff, heavily damped arm drives (k=22918,
        # c=4583 => ~0.2 s time constant), which makes Cartesian servoing slow.
        # Softer, less damped gains track the IK commands much faster while
        # staying stable at 120 Hz.
        import os

        if os.environ.get("FRUIT_TUNE_GAINS", "0") == "1":
            k = float(os.environ.get("FRUIT_ARM_STIFFNESS", 1500.0))
            c = float(os.environ.get("FRUIT_ARM_DAMPING", 60.0))
            self.robot.set_dof_gains(k, c, dof_indices=self.arm_dofs)

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #
    def tcp_position(self) -> np.ndarray:
        positions, _ = self._tcp_prim.get_world_poses()
        return to_numpy(positions)[0]

    def tcp_pose(self) -> tuple[np.ndarray, np.ndarray]:
        positions, orientations = self._tcp_prim.get_world_poses()
        return to_numpy(positions)[0], to_numpy(orientations)[0]

    def jaw_positions(self) -> tuple[np.ndarray, np.ndarray]:
        left = to_numpy(self._finger_prims[0].get_world_poses()[0])[0]
        right = to_numpy(self._finger_prims[1].get_world_poses()[0])[0]
        return left, right

    def jaw_centre(self) -> np.ndarray:
        left, right = self.jaw_positions()
        return (left + right) / 2.0

    def jaw_separation(self) -> float:
        left, right = self.jaw_positions()
        return float(np.linalg.norm(left - right))

    def tcp_target_for_jaw(self, jaw_target: np.ndarray) -> np.ndarray:
        """TCP position that puts the jaw centre at `jaw_target`.

        The tool point sits ~7.8 cm past the jaws, so the offset is recomputed
        every call and stays correct as the wrist orientation drifts.
        """
        return np.asarray(jaw_target, dtype=float) + (self.tcp_position() - self.jaw_centre())

    def dof_positions(self) -> np.ndarray:
        # `.copy()` matters: without it this is a view onto the physics buffer and
        # any in-place edit (e.g. teleporting the arm) is silently lost.
        return np.array(self.robot.get_dof_positions().numpy())[0]

    def finger_opening(self) -> float:
        return float(np.mean(self.dof_positions()[self.finger_dofs]))

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #
    def set_gripper(self, opening: float) -> None:
        """Command both finger joints to the same opening [m]."""
        value = float(np.clip(opening, self.closed_value, self.open_value))
        self.robot.set_dof_position_targets(
            [[value] * len(self.finger_dofs)], dof_indices=self.finger_dofs
        )

    def gripper_value_for_separation(self, separation: float) -> float:
        """Finger joint command that opens the jaws to `separation` [m]."""
        value = (separation - self.JAW_SEPARATION_OFFSET) / self.JAW_SEPARATION_PER_JOINT
        return float(np.clip(value, self.closed_value, self.open_value))

    def ik_step(self, target: np.ndarray) -> float:
        """One 6-DoF differential-IK update towards `target`; returns position error [m].

        Orientation is held at `self.hold_quaternion` (captured by
        :meth:`capture_hold_pose`). Without that constraint the wrist rotates
        freely - the arm only has 7 DoF and position alone does not pin the
        wrist - which moves the jaw centre away from the commanded point.
        """
        tcp = self.tcp_position()
        error = np.asarray(target, dtype=float) - tcp
        distance = float(np.linalg.norm(error))
        if distance < 1e-5:
            return distance

        jacobian = self.robot.get_jacobian_matrices().numpy()[0, self.tcp_jacobian_index]
        # Rows 0:3 are the linear part, rows 3:6 the angular part.
        j_full = jacobian[:, self.arm_dofs]

        if self.hold_quaternion is None:
            error6 = error
            jac = j_full[0:3, :]
        else:
            _, quat = self.tcp_pose()
            rot_error = quaternion_error(self.hold_quaternion, quat)
            error6 = np.concatenate([error, rot_error])
            jac = j_full

        measured = self.dof_positions()[self.arm_dofs]
        if self._q_cmd is None:
            self._q_cmd = measured.copy()
        # Predict the task error that the *commanded* joints will produce. The
        # measured pose lags the command, so integrating on the measured error
        # would wind up and run away.
        error6 = error6 - jac @ (self._q_cmd - measured)

        lam = self.damping**2
        dq = jac.T @ np.linalg.solve(jac @ jac.T + lam * np.eye(jac.shape[0]), error6)
        dq = np.clip(dq * self.gain, -self.max_step, self.max_step)

        command = np.clip(self._q_cmd + dq, self.arm_lo, self.arm_hi)
        self._q_cmd = command
        self.robot.set_dof_position_targets([command], dof_indices=self.arm_dofs)
        if self._debug_steps > 0:
            self._debug_steps -= 1
            say(
                f"[ik:{self.spec.side}] dist={distance:.4f} |j|={np.linalg.norm(jac):.3f} "
                f"|dq|={np.linalg.norm(dq):.4f} q={np.round(measured, 3).tolist()} "
                f"cmd={np.round(command, 3).tolist()}"
            )
        return distance

    def sync_command_to_measured(self) -> None:
        """Reset the IK integrator to the measured joints (after a jump or reset)."""
        self._q_cmd = self.joint_positions()

    def teleport_joints(self, config: np.ndarray, settle: int = 30) -> None:
        """Place the arm at `config` without driving through intermediate poses.

        Used to park the arm at a calibrated start pose: commanding that pose
        from the hanging pose makes the elbow stall, while teleporting to it is
        an instantaneous, collision-free state change.
        """
        full = self.dof_positions()
        full[self.arm_dofs] = np.asarray(config, dtype=float).reshape(-1)
        self.robot.set_dof_positions(full)
        self.robot.set_dof_position_targets(full)
        app_utils.update_app(steps=settle)
        self.sync_command_to_measured()

    def capture_hold_pose(self) -> None:
        """Freeze the current TCP orientation as the IK orientation target."""
        _, quat = self.tcp_pose()
        self.hold_quaternion = np.asarray(quat, dtype=float)

    def move_to(self, target: np.ndarray, max_steps: int = 900, tolerance: float = 0.012,
                steps_per_update: int = 1) -> float:
        """Iterate IK until the TCP is within `tolerance` or `max_steps` is reached."""
        residual = float("inf")
        for _ in range(max_steps):
            residual = self.ik_step(target)
            app_utils.update_app(steps=steps_per_update)
            if residual <= tolerance:
                break
        return residual

    # ------------------------------------------------------------------ #
    # Joint-space motion
    # ------------------------------------------------------------------ #
    def joint_positions(self) -> np.ndarray:
        return self.dof_positions()[self.arm_dofs].copy()

    def solve_to(self, jaw_target: np.ndarray, iterations: int = 2000,
                 tolerance: float = 0.008, restarts: int = 1,
                 seed: int = 0) -> tuple[np.ndarray, float]:
        """Solve IK to `jaw_target` and return the joint configuration and residual.

        The TCP->jaw offset is re-measured periodically: with position-only IK
        the wrist drifts, so a fixed offset would leave the jaws off target.
        `restarts` > 1 re-solves from random arm configurations, which escapes
        the local minima the solver otherwise falls into from the hanging pose.
        """
        import random

        rng = random.Random(seed)
        target = np.asarray(jaw_target, dtype=float)
        best_config = self.joint_positions()
        best_residual = float("inf")

        for attempt in range(max(1, restarts)):
            if attempt > 0:
                self._jump_to_random_pose(rng)
            offset = self.tcp_position() - self.jaw_centre()
            residual = float("inf")
            for i in range(iterations):
                if i % 25 == 0 and i > 0:
                    offset = self.tcp_position() - self.jaw_centre()
                self.ik_step(target + offset)
                app_utils.update_app(steps=1)
                residual = float(np.linalg.norm(self.jaw_centre() - target))
                if residual <= tolerance:
                    break
            if residual < best_residual:
                best_residual = residual
                best_config = self.joint_positions()
            if best_residual <= tolerance:
                break

        if best_residual > tolerance:
            self.move_joints(best_config, steps=60)
        return best_config, best_residual

    def _jump_to_random_pose(self, rng) -> None:
        """Teleport the arm to a random feasible configuration (calibration only)."""
        full = self.dof_positions()
        arm_target = np.asarray(
            [rng.uniform(lo * 0.4, hi * 0.4) for lo, hi in zip(self.arm_lo, self.arm_hi)]
        )
        full[self.arm_dofs] = arm_target
        self.robot.set_dof_positions(full)
        self.robot.set_dof_position_targets(full)
        app_utils.update_app(steps=20)
        self.sync_command_to_measured()

    def move_joints(
        self,
        target: np.ndarray,
        steps: int = 90,
        settle: int = 260,
        tolerance: float = 0.06,
    ) -> float:
        """Interpolate to `target`, then hold until the joints actually get there.

        Returns the final maximum joint error [rad]. The drives are heavily
        damped, so the commanded position is not reached within the interpolation
        alone.
        """
        start = self.joint_positions()
        target = np.asarray(target, dtype=float).reshape(-1)
        for i in range(1, steps + 1):
            alpha = i / float(steps)
            command = (1.0 - alpha) * start + alpha * target
            self.robot.set_dof_position_targets([command], dof_indices=self.arm_dofs)
            app_utils.update_app(steps=1)
        error = float(np.max(np.abs(self.joint_positions() - target)))
        for _ in range(settle):
            if error <= tolerance:
                break
            self.robot.set_dof_position_targets([target], dof_indices=self.arm_dofs)
            app_utils.update_app(steps=1)
            error = float(np.max(np.abs(self.joint_positions() - target)))
        return error

    def hold(self, steps: int = 30) -> None:
        app_utils.update_app(steps=steps)

    def park_pose(self) -> np.ndarray:
        """A safe resting pose slightly above and behind the belt."""
        return np.array([0.16, 0.34 if self.spec.side == "left" else -0.34, 1.30])
