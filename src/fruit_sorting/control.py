"""Joint-space control helpers: damped least-squares Cartesian IK and gripper control."""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.experimental.prims import RigidPrim
from isaacsim.core.simulation_manager import SimulationManager

from .common import say, substeps, to_numpy


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
    #: Offset between the finger *link origins* and the gap between the pad
    #: surfaces. Every earlier estimate was wrong by 1-2 cm because it came from
    #: bounding boxes or from projecting the finger point clouds onto a closing
    #: axis that is tilted ~30 deg away from the pad normal, both of which
    #: overestimate the free gap. The authoritative number is the kinematic-sphere
    #: sweep (scripts/55_grasp_sweep.py): a sphere of diameter d is stopped by the
    #: pads at an *origin* separation of about d (2 cm -> 2.46, 3 -> 3.50,
    #: 5 -> 4.86, 7 -> 5.95, 9 -> 8.99 cm), i.e. the pad surfaces are
    #: essentially at the link origins. Commanding a wider gap leaves the pads
    #: short of the fruit and every grasp reads zero contact force - which is
    #: exactly what the 2.22 cm and 1.15 cm constants did.
    FINGER_FACE_OFFSET = 0.0

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
        #: Set to a list to record every IK step (see `begin_trace`/`end_trace`).
        self._trace_rows: list[dict] | None = None
        #: Triggered diagnostic. `ik_step` already reads the measured joints every
        #: tick, so an external push can be detected *online* from data the
        #: baseline collects anyway: the joint moves far more than the command
        #: asked for. Reading more state per tick disturbs the run (see the
        #: WORKLOG), but reading it once, on the tick that matters, does not.
        self._prev_measured: np.ndarray | None = None
        self._last_dq: np.ndarray | None = None
        self.anomaly_hook = None
        self.anomaly_kicks = 0
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
        # The finger drives are stiff and weakly actuated in this asset: with the
        # jaw centre down at the pick pose they sometimes refuse to move at all
        # (logs/85: commanded 0.044 -> 0.0, measured q stayed 0.044), which reads
        # as "no contact" in every grasp test. Raise their stiffness so a small
        # jam cannot stall the close.
        finger_default = "60000" if os.environ.get("FRUIT_FINGER_PADS", "0") == "1" else "0"
        finger_k = float(os.environ.get("FRUIT_FINGER_STIFFNESS", finger_default))
        if finger_k > 0.0:
            finger_c = float(os.environ.get("FRUIT_FINGER_DAMPING", str(finger_k * 0.02)))
            self.robot.set_dof_gains(finger_k, finger_c, dof_indices=self.finger_dofs)

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

    def approach_axis(self) -> np.ndarray:
        """Unit vector from the jaw centre towards the TCP (down the fingers).

        The fingertip pads sit about 1 cm along this axis from the jaw centre, so
        aiming the *pads* at a fruit means offsetting the commanded jaw centre
        backwards along it.
        """
        axis = self.tcp_position() - self.jaw_centre()
        return axis / max(float(np.linalg.norm(axis)), 1e-9)

    def jaw_axis(self) -> np.ndarray:
        """Unit vector along the closing axis (left finger -> right finger)."""
        left, right = self.jaw_positions()
        axis = np.asarray(right, dtype=float) - np.asarray(left, dtype=float)
        return axis / max(float(np.linalg.norm(axis)), 1e-9)

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
        """Finger joint command whose finger faces span `separation` [m]."""
        origin_separation = separation + self.FINGER_FACE_OFFSET
        value = (origin_separation - self.JAW_SEPARATION_OFFSET) / self.JAW_SEPARATION_PER_JOINT
        return float(np.clip(value, self.closed_value, self.open_value))

    def ik_step(self, target: np.ndarray, target_velocity: np.ndarray | None = None) -> float:
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
            if self._trace_rows is not None:
                # Keep the trace one row per control tick even on the early return,
                # so a row index is a tick index.
                self._trace_rows.append(
                    {
                        "dq": [0.0] * len(self.arm_dofs),
                        "dq_norm": 0.0,
                        "task_err": error.tolist(),
                        "task_err_norm": distance,
                        "lag": [0.0] * len(self.arm_dofs),
                        "lag_norm": 0.0,
                        "error6": error.tolist(),
                        "error6_norm": distance,
                        "sigma_min": float("nan"),
                        "command": None if self._q_cmd is None else self._q_cmd.tolist(),
                        "limit_clipped": False,
                        "limit_margin": float("nan"),
                        "jac_rows": 0,
                        "tcp": tcp.tolist(),
                        "measured": None,
                        "q_cmd": None if self._q_cmd is None else self._q_cmd.tolist(),
                        "sim_time": float(
                            __import__(
                                "isaacsim.core.simulation_manager",
                                fromlist=["SimulationManager"],
                            ).SimulationManager.get_simulation_time()
                        ),
                        "early_return": True,
                    }
                )
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
        # Every line of the detector is behind the hook: the shipped control loop
        # must not carry even two small array copies, because the run is measurably
        # sensitive to what `ik_step` does per tick (a run with the hook installed
        # but no kick fires still diverges from the baseline - logs/453/455).
        if self.anomaly_hook is not None:
            if self._prev_measured is not None and self._last_dq is not None:
                achieved = float(np.linalg.norm(measured - self._prev_measured))
                commanded = float(np.linalg.norm(self._last_dq))
                # The arm cannot move much further than it was told to: when it
                # does, something other than the drive moved it.
                if achieved > float(
                    os.environ.get("FRUIT_ANOMALY_STEP", "0.015")
                ) and (achieved > 5.0 * commanded):
                    self.anomaly_kicks += 1
                    self.anomaly_hook(
                        {
                            "achieved_rad": achieved,
                            "commanded_rad": commanded,
                            "measured": measured.tolist(),
                            "previous_measured": self._prev_measured.tolist(),
                            "last_dq": self._last_dq.tolist(),
                            "tcp": tcp.tolist(),
                            "task_err_m": distance,
                        }
                    )
            self._prev_measured = measured.copy()
        if self._q_cmd is None:
            self._q_cmd = measured.copy()
        # Predict the task error that the *commanded* joints will produce. The
        # measured pose lags the command, so integrating on the measured error
        # would wind up and run away.
        error6 = error6 - jac @ (self._q_cmd - measured)

        lam = self.damping**2
        dq = jac.T @ np.linalg.solve(jac @ jac.T + lam * np.eye(jac.shape[0]), error6)
        dq = np.clip(dq * self.gain, -self.max_step, self.max_step)
        if self._trace_rows is not None:
            # Per-tick record for the one-descent-in-ten lurch: the interesting
            # question is whether the integrator runs away because it saturates at
            # a joint limit, because the Jacobian goes near-singular, or because
            # the lag-compensation term inverts sign.
            unclipped = self._q_cmd + dq
            singular = float(np.linalg.svd(jac, compute_uv=False)[-1])
            self._trace_rows.append(
                {
                    "dq": dq.tolist(),
                    "dq_norm": float(np.linalg.norm(dq)),
                    "task_err": error.tolist(),
                    "task_err_norm": distance,
                    "lag": (self._q_cmd - measured).tolist(),
                    "lag_norm": float(np.linalg.norm(self._q_cmd - measured)),
                    "error6": error6.tolist(),
                    "error6_norm": float(np.linalg.norm(error6)),
                    "sigma_min": singular,
                    "command": unclipped.tolist(),
                    "limit_clipped": bool(
                        np.any(unclipped < self.arm_lo - 1e-12)
                        or np.any(unclipped > self.arm_hi + 1e-12)
                    ),
                    "limit_margin": float(
                        min(np.min(unclipped - self.arm_lo), np.min(self.arm_hi - unclipped))
                    ),
                    # Joint limits: static, trace-only, so a clipping read can name
                    # the saturated joint instead of only its margin [rad].
                    "arm_lo": self.arm_lo.tolist(),
                    "arm_hi": self.arm_hi.tolist(),
                    "jac_rows": int(jac.shape[0]),
                    "tcp": tcp.tolist(),
                    "measured": measured.tolist(),
                    "q_cmd": self._q_cmd.tolist() if self._q_cmd is not None else None,
                    "drive_target": np.asarray(
                        self.robot.get_dof_position_targets().numpy()
                    )[0][self.arm_dofs].tolist(),
                    "drive_velocity_target": np.asarray(
                        self.robot.get_dof_velocity_targets().numpy()
                    )[0][self.arm_dofs].tolist(),
                    "sim_time": float(
                        __import__(
                            "isaacsim.core.simulation_manager",
                            fromlist=["SimulationManager"],
                        ).SimulationManager.get_simulation_time()
                    ),
                    "early_return": False,
                }
            )
        # Command rate limit. The position step cap above is *not* what bounds the
        # visible smoothness: the integrator's `jac @ (q_cmd - q_measured)` lag
        # compensation can inject a single-tick joint command of ~9 mrad (~4.5 mm
        # of tip motion in 8 ms) while the task residual is 0.01 mm, and the drive
        # answers that with a 2-3 m/s^2 lurch (measured, logs/420). `FRUIT_IK_RATE`
        # bounds the command change per control tick instead; 0 disables it.
        rate = float(os.environ.get("FRUIT_IK_RATE", "0.0"))
        if rate > 0.0:
            magnitude = float(np.linalg.norm(dq))
            if magnitude > rate:
                dq = dq * (rate / magnitude)
        if self.anomaly_hook is not None:
            self._last_dq = np.asarray(dq, dtype=float).copy()
        warn = float(os.environ.get("FRUIT_IK_WARN", "0.0"))
        if warn > 0.0 and float(np.linalg.norm(dq)) > warn:
            say(
                f"[ik:{self.spec.side}] LARGE command |dq|={np.linalg.norm(dq):.4f} rad "
                f"task_err={np.linalg.norm(error):.4f} m "
                f"lag|q_cmd-q|={np.linalg.norm(self._q_cmd - measured):.4f} rad"
            )

        command = np.clip(self._q_cmd + dq, self.arm_lo, self.arm_hi)
        self._q_cmd = command
        self.robot.set_dof_position_targets([command], dof_indices=self.arm_dofs)
        # Velocity feed-forward: the PD drives lag the position reference, and that
        # lag is what showed up as 3.5-7 m/s^2 of *achieved* TCP acceleration in
        # the approach (logs/374 - the reference itself was smooth). Feeding the
        # reference's Cartesian velocity through the pseudo-inverse gives the
        # drives the velocity term they need to track it.
        # Default 0 (off): the joint-velocity feed-forward was measured with gain
        # 1.0 and did not help - achieved approach |a|max went 3.5/4.7/15.1 m/s^2
        # versus 3.7/5.4/6.4 m/s^2 without it (logs/375 vs /376), with one attempt
        # clearly worse, so the velocity-target convention needs its own study.
        ff = float(os.environ.get("FRUIT_FF_GAIN", "0.0"))
        if target_velocity is not None and ff > 0.0:
            lam = self.damping**2
            dq_rate = jac.T @ np.linalg.solve(
                jac @ jac.T + lam * np.eye(jac.shape[0]), np.asarray(target_velocity, dtype=float)[: jac.shape[0]]
            )
            setter = getattr(self.robot, "set_dof_velocity_targets", None)
            if setter is not None:
                try:
                    setter([[float(v) * ff for v in dq_rate]], dof_indices=self.arm_dofs)
                except (AttributeError, TypeError, ValueError):
                    pass
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
        # The achieved-motion detector compares consecutive ticks; a jump or a
        # reset makes that comparison meaningless.
        self._prev_measured = None
        self._last_dq = None

    def begin_trace(self) -> None:
        """Start recording every IK step (see `end_trace`)."""
        self._trace_rows = []

    def end_trace(self, path: str) -> int:
        """Write the recorded IK steps to `path` and stop recording."""
        import json

        rows = self._trace_rows or []
        self._trace_rows = None
        if not rows:
            return 0
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(rows, handle)
        return len(rows)

    def teleport_joints(self, config: np.ndarray, settle: int = 30) -> None:
        """Place the arm at `config` without driving through intermediate poses.

        Used to park the arm at a calibrated start pose: commanding that pose
        from the hanging pose makes the elbow stall, while teleporting to it is
        an instantaneous, collision-free state change.
        """
        full = self.dof_positions()
        full[self.arm_dofs] = np.asarray(config, dtype=float).reshape(-1)
        self.robot.set_dof_positions(full)
        # Only re-target the arm joints. Writing all 22 targets would clobber the
        # gripper command with whatever the fingers happen to be doing.
        self.robot.set_dof_position_targets(
            [full[self.arm_dofs]], dof_indices=self.arm_dofs
        )
        for _ in range(settle):
            SimulationManager.step(steps=substeps())
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
            SimulationManager.step(steps=steps_per_update * substeps())
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
                 seed: int = 0, move_on_fail: bool = True) -> tuple[np.ndarray, float]:
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
                # Physics step, not an app update: an app update renders and
                # costs ~0.4 s here, which made IK solves take minutes.
                SimulationManager.step(steps=substeps())
                residual = float(np.linalg.norm(self.jaw_centre() - target))
                if residual <= tolerance:
                    break
            if residual < best_residual:
                best_residual = residual
                best_config = self.joint_positions()
            if best_residual <= tolerance:
                break

        if best_residual > tolerance and move_on_fail:
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
        for _ in range(20):
            SimulationManager.step(steps=substeps())
        self.sync_command_to_measured()

    def move_joints(
        self,
        target: np.ndarray,
        steps: int = 90,
        settle: int = 260,
        tolerance: float = 0.06,
    ) -> float:
        """Blend to `target` along a quintic, then hold until the joints get there.

        Returns the final maximum joint error [rad]. The drives are heavily
        damped, so the commanded position is not reached within the interpolation
        alone.

        The blend is minimum-jerk (`10u^3 - 15u^4 + 6u^5`) rather than linear:
        a straight joint-space line starts and stops with a velocity step, which
        the drives answer with a lurch and which is visible in the demo videos.
        """
        from .motion import min_jerk_ramp

        start = self.joint_positions()
        target = np.asarray(target, dtype=float).reshape(-1)
        blend = min_jerk_ramp(0.0, 1.0, steps)
        for i in range(1, steps + 1):
            alpha = float(blend[i - 1])
            command = start + alpha * (target - start)
            self.robot.set_dof_position_targets([command], dof_indices=self.arm_dofs)
            SimulationManager.step(steps=substeps())
        error = float(np.max(np.abs(self.joint_positions() - target)))
        for _ in range(settle):
            if error <= tolerance:
                break
            self.robot.set_dof_position_targets([target], dof_indices=self.arm_dofs)
            SimulationManager.step(steps=substeps())
            error = float(np.max(np.abs(self.joint_positions() - target)))
        # Re-seat the differential-IK integrator on the pose the arm actually
        # reached. This function writes position targets directly, so `_q_cmd`
        # would otherwise still hold the configuration from before the move; the
        # next `ik_step` would then fold the whole difference into one command and
        # the stiff drive snaps to it (the 1.79 m/s single-tick lurch in logs/423).
        self.sync_command_to_measured()
        return error

    def hold(self, steps: int = 30) -> None:
        for _ in range(steps):
            SimulationManager.step(steps=substeps())

    def park_pose(self) -> np.ndarray:
        """A safe resting pose slightly above and behind the belt."""
        return np.array([0.16, 0.34 if self.spec.side == "left" else -0.34, 1.30])
