"""Scripted pick-and-place on the moving belt.

The scripted policy plays the role of the trained diffusion policy for now: it
produces the demonstration data and gives the simulation something to measure
against.

Strategy for a moving target: instead of chasing the fruit, the arm moves to the
predicted intercept point upstream of the fruit, waits there, descends as the
fruit arrives, closes the gripper, lifts, and carries the fruit to the output
conveyor beside the robot.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.rendering_manager import RenderingManager

from .common import say, substeps, to_numpy
from .control import ArmController
from .dataset import EpisodeMeta, EpisodeRecorder, camera_observation
from .grasp import pads_mid
from .actuated_gripper import ActuatedGripper
from .kinematic_gripper import KinematicGripper, PAD_THICK
from .motion import (
    MotionMonitor,
    TrajectoryLimits,
    jerk_limited,
    min_jerk_ramp,
    mirror_across_xz,
    top_down_quaternion,
)
from .tactile import TactileReading

#: Small vertical offset of the coherent hand above the fruit's centre, so the pads'
#: lower edge clears the belt and the gate: with the pads centred exactly on a small
#: fruit their bottom sits below the belt surface and the close squeezes the fruit
#: upwards and out.
PAD_LIFT = float(os.environ.get("FRUIT_PAD_LIFT", "0.010"))

#: Control period of the scripted pipeline: physics advances 1/120 s per
#: `_step_sim(1)`, and every trajectory is generated against this rate.
CONTROL_DT = 1.0 / 120.0


def _quat_matrix(q) -> np.ndarray:
    """Rotation matrix from a (w, x, y, z) quaternion."""
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

_EMPTY_TACTILE = TactileReading(side="none")


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

    def __init__(self, scene, spawner, tactile, cfg, waypoint_path: str | None = None):
        # The v1 file reproduces the recorded datasets. Physical grasping uses the
        # orientation-constrained poses: FRUIT_WAYPOINTS=configs/waypoints_oriented.json
        waypoint_path = waypoint_path or os.environ.get(
            "FRUIT_WAYPOINTS", "configs/waypoints.json"
        )
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
        self.recorder: EpisodeRecorder | None = None
        #: Last joint configuration that produced a successful grasp, per arm. The
        #: pick pose sits near the edge of the workspace, so the IK occasionally
        #: diverges (residuals of 81-384 mm in logs/134); re-using a known-good
        #: configuration as the seed removes most of that.
        self._grasp_cache: dict[str, np.ndarray] = {}
        #: Parallel gripper modelled as two kinematic fingers (see
        #: kinematic_gripper.py): the OpenArm asset's own gripper cannot be made to
        #: pinch these fruit, while this one holds 10/10 (3.3-6.9 cm) in the
        #: isolated test. The arm still does all the motion; the gripper only
        #: provides the contact geometry.
        # `FRUIT_GRIPPER_KIND=actuated` swaps the contact model: prismatic fingers
        # with force-limited drives instead of kinematic pads whose normal force is
        # an interference artefact (see actuated_gripper.py).
        if os.environ.get("FRUIT_GRIPPER_KIND", "kinematic") == "actuated":
            self.grippers = {
                side: ActuatedGripper(scene.stage, side) for side in ("left", "right")
            }
        else:
            self.grippers = {
                side: KinematicGripper(scene.stage, side) for side in ("left", "right")
            }
        self._closed_gap: dict[str, float | None] = {"left": None, "right": None}
        #: How many episodes each arm has been given, for the collector's
        #: target balancing.
        self._episodes_by_arm: dict[str, int] = {"left": 0, "right": 0}
        #: Per-fruit failure counts and the run statistics. A fruit that keeps
        #: failing is *diverted* (a real line has a reject chute) instead of being
        #: retried forever - retrying the same hard item was what turned one
        #: strawberry into three wasted attempts (logs/277).
        self.failures: dict[int, int] = {}
        self.max_retries = int(os.environ.get("FRUIT_MAX_RETRIES", "2"))
        self.stats: dict[str, float] = {
            "attempts": 0,
            "successes": 0,
            "rejected": 0,
            "gate_open_ticks": 0.0,
            "queue_peak": 0.0,
            "sim_time": 0.0,
        }
        #: Demo mode: pump the Isaac UI from the control loop so the window does
        #: not appear frozen (see `_step_sim`).
        self.gui_smooth = os.environ.get("FRUIT_GUI_SMOOTH", "0") == "1"
        self._gui_tick = 0
        #: Offset from the arm's tool point to the pad centre, recorded at the
        #: moment of grasping. While the fruit is held the pads must move *with the
        #: arm* (they are the hand); pinning them to the fruit instead means the
        #: arm lifts away and nothing carries the fruit.
        self._gripper_offset: dict[str, np.ndarray | None] = {"left": None, "right": None}
        #: Orientation of the *pads* at the moment the grip closed, and the pad
        #: centre last commanded. A real hand carries its orientation with the
        #: payload; re-reading the wrist quaternion every step meant the pads
        #: twisted off the fruit whenever the arm's IK lagged (measured: 27 cm of
        #: payload slip with the twist, 0.1 mm without it).
        self._grip_quat: dict[str, np.ndarray | None] = {"left": None, "right": None}
        self._grip_centre: dict[str, np.ndarray | None] = {"left": None, "right": None}
        #: Coherent-hand mode per arm: the pads are mounted at the fingertips of a
        #: top-down posed arm, so the arm itself presents the fingers on the fruit.
        self._coherent: dict[str, bool] = {"left": False, "right": False}
        #: Optional hook called on every rendered tick (used by the video recorder).
        self.frame_callback = None
        self.current_sample = None
        self.current_arm = "left"
        self.current_goal = np.zeros(8, dtype=np.float32)
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

    # ------------------------------------------------------------------ #
    # Run statistics / reject policy
    # ------------------------------------------------------------------ #
    def station_sample(self):
        """The fruit actually presented at the pick station, if any.

        The feeder presents one fruit at a time, and the task's own selection can
        disagree with it (a fruit that was selected upstream while another sits
        between the jaws - `logs/316`: target index 1 at x = 0.604 m while the jaw
        was at x = 0.336 m). Closing on the wrong fruit is what that produced.
        """
        best = None
        best_distance = float("inf")
        for sample in self.spawner.active:
            if sample.parked or sample.held:
                continue
            pos = self.spawner.position(sample)
            along = float(pos[1])
            if abs(float(pos[0]) - self.cfg.belt_center[0]) > 0.30:
                continue  # placed on the output line, not on the main belt
            if float(pos[2]) < self.belt_top - 0.05:
                continue  # fell off
            if self.cfg.pick_y - 0.08 <= along <= self.cfg.pick_y + 0.20:
                distance = abs(along - self.cfg.pick_y)
                if distance < best_distance:
                    best_distance = distance
                    best = sample
        return best

    def _queue_depth(self) -> int:
        """Fruit waiting between the gate and the upstream window."""
        spawner = getattr(self, "spawner", None)
        if spawner is None:
            return 0
        depth = 0
        for sample in spawner.active:
            if sample.parked or sample.held:
                continue
            pos = spawner.position(sample)
            if (
                abs(float(pos[0]) - self.cfg.belt_center[0]) > 0.30
                or float(pos[2]) > self.belt_top + 0.12
            ):
                continue  # on an output conveyor, not in the main-belt queue
            along = float(pos[1])
            if self.cfg.pick_y - 0.05 <= along <= self.cfg.pick_y + 0.45:
                depth += 1
        return depth

    def _record_gate(self, step: int) -> None:
        """Accumulate the indexing statistics when the gate closes on a fruit."""
        opened_at = getattr(self, "_gate_open_step", 0)
        self.stats["gate_open_ticks"] += max(0, int(step) - opened_at)
        self.stats["queue_peak"] = max(self.stats["queue_peak"], float(self._queue_depth()))
        self._gate_open_step = int(step)

    def note_result(self, result: "EpisodeResult") -> None:
        """Book-keeping after an attempt: counts, and the reject/divert policy.

        A fruit that fails `FRUIT_MAX_RETRIES` times is parked (removed from the
        line) so the station is not wedged by one hard item - the same hard
        strawberry was retried three times in a row and blocked the line
        (logs/277). Real cells divert such a product to a reject chute.
        """
        self.stats["attempts"] += 1
        # Simulated-time cycle accounting: the wall clock is not a usable metric
        # on a shared machine (170-207 % CPU during the slow runs, logs/289), but
        # seconds of *simulated* time per pick is what a real cell's cycle time is.
        started = getattr(self, "_attempt_sim_t0", None)
        if started is not None:
            self.stats["sim_time"] += max(0.0, self._sim_time() - started)
        if result.success:
            self.stats["successes"] += 1
            self.failures.pop(int(result.sample_index), None)
            return
        count = self.failures.get(int(result.sample_index), 0) + 1
        self.failures[int(result.sample_index)] = count
        if count >= self.max_retries:
            spawner = getattr(self, "spawner", None)
            sample = None
            if spawner is not None:
                sample = next(
                    (s for s in spawner.samples if s.index == int(result.sample_index)), None
                )
            if sample is not None and not sample.parked:
                spawner.park(sample)
                self.stats["rejected"] += 1
                say(
                    f"[task] diverting {result.category} (index {result.sample_index}) after "
                    f"{count} failed attempts - reject chute"
                )

    def stats_line(self) -> str:
        attempts = max(1.0, self.stats["attempts"])
        per_attempt = self.stats["sim_time"] / attempts
        per_success = self.stats["sim_time"] / max(1.0, self.stats["successes"])
        belt = getattr(self.spawner, "belt", None)
        encoder = float(getattr(belt, "encoder_speed", float("nan")))
        command = float(getattr(belt, "speed", float("nan")))
        spread = abs(encoder - command)
        # With the cleats off there is no belt furniture to difference, so the
        # encoder reading would just be the initialised command. Say so instead of
        # printing a "measured" zero spread the probe never measured.
        if getattr(belt, "cleats", None):
            encoder_text = (
                f"encoder={encoder:+.3f} m/s (command {command:+.3f}, spread {spread:.4f})"
            )
        else:
            encoder_text = (
                f"encoder={command:+.3f} m/s nominal (command {command:+.3f}, "
                "no cleats to measure travel)"
            )
        # NOTE: the gate/queue counters only move on the indexed (non-dynamic)
        # feed; on the shipped dynamic line they read zero. They are left in the
        # line because `scripts/105_motion_regression.py` and the acceptance logs
        # parse this format - changing it after a run would make the tree disagree
        # with the log the gate was measured on.
        return (
            f"[stats] attempts={int(self.stats['attempts'])} "
            f"successes={int(self.stats['successes'])} "
            f"diverted={int(self.stats['rejected'])} "
            f"success_rate={self.stats['successes'] / attempts * 100:.0f}% "
            f"sim={self.stats['sim_time']:.1f}s total, "
            f"{per_attempt:.1f}s/attempt, {per_success:.1f}s/success "
            f"gate_open={self.stats['gate_open_ticks'] / 120.0:.1f}s total, "
            f"queue_peak={int(self.stats['queue_peak'])} "
            f"recirculated={int(getattr(self.spawner, 'stats', {}).get('recirculated', 0))} "
            # The belt speed: what the belt actually did over the run, next to the
            # count of fruit that had to wait for it.
            f"{encoder_text}"
        )

    def _fingertip_offset(self, side: str) -> float:
        """Distance from the jaw centre down to the lowest fingertip, measured live.

        The OpenArm fingers are long plates, so this varies with wrist
        orientation (about 6.1 cm at the pick pose, 8 cm hanging). Using a fixed
        number puts the fingers above small fruit and the jaws close on air.
        """
        from pxr import Usd, UsdGeom

        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
        lowest = None
        for which in ("left", "right"):
            path = f"/World/OpenArm/openarm_{side}_{which}_finger"
            rng = cache.ComputeWorldBound(self.scene.stage.GetPrimAtPath(path)).ComputeAlignedRange()
            lo = float(rng.GetMin()[2])
            lowest = lo if lowest is None else min(lowest, lo)
        jaw_z = float(self.arms[side].jaw_centre()[2])
        return max(0.02, jaw_z - lowest)

    def seat_height(self) -> float:
        """How high the fruit is presented for the grasp.

        With the pop-up lifter and the pick stop gone, this is the static nest
        height (0 by default): the fruit rests where the belt left it and the
        kinematic pad hand is placed on its measured centre.
        """
        return float(getattr(self.cfg, "nest_height", 0.0))

    def _transit_to(self, side: str, name: str, ticks: int = 90, settle: int = 120) -> None:
        """Drive an arm to a named pose along a min-jerk joint blend.

        The named poses used to be *teleported* to, which is the most visible
        non-human thing in the clip: between cycles the arm snaps from over the
        output line back to the ready pose in one tick. The blend is the same
        quintic the jaw and the belt use, so it starts and ends at zero velocity.

        `ready` is special: the straight joint line from a far-away seed (the
        hanging pose, or the post-place pose with the pre-pose path on) drags the
        hand under the main belt and up through it and jams on the belt's near
        face (measured, `logs/600`). A far seed is therefore routed *around* the
        belt by `_ready_transit`; a seed already near ready keeps the plain blend
        (a no-op for the arm that did not move).
        """
        self._catch_up_drive(side)
        if (
            name == "ready"
            and os.environ.get("FRUIT_READY_TRANSIT", "staged") == "staged"
            and self._ready_transit(side, ticks=ticks, settle=settle)
        ):
            return
        self._blend_to(side, self._pose(side, name), ticks=ticks, settle=settle)

    def _catch_up_drive(self, side: str, ticks: int = 20) -> bool:
        """Ramp the drive target onto the measured pose before a new leg starts.

        During the release the kinematic pads (which sit inside the arm's own
        hand) push the arm out: with the drive target frozen the arm drifts up
        to 0.9 rad away from it (`logs/630`, A4 left). A leg that starts from
        the stale target would put that whole difference into its first command
        - a boundary jump no matter where it is written. Ramping the target onto
        the arm keeps every command step under 0.05 rad/tick and hands the next
        leg a consistent starting point. The ramp length scales with the gap: the
        minimum-jerk profile peaks at ~1.9x its average rate, so a 0.9 rad gap in
        20 ticks would still command 0.085 rad/tick and a 2 rad one 0.19
        (`logs/650` measured 0.1655).
        """
        arm = self.arms[side]
        current = np.asarray(
            arm.robot.get_dof_position_targets().numpy(), dtype=float
        )[0][arm.arm_dofs]
        measured = arm.joint_positions()
        gap = float(np.max(np.abs(current - measured)))
        if gap <= 0.01:
            return False
        ticks = max(int(ticks), int(np.ceil(gap / 0.02)))
        ramp = min_jerk_ramp(0.0, 1.0, max(1, int(ticks)))
        for alpha in ramp:
            # Re-read the measured pose every tick: the arm is not stationary
            # (the pads are pushing it out of the hand), and a ramp that aims at
            # the *snapshot* taken at the start then re-anchors the integrator on
            # the moved arm finishes with one last step of the whole drift
            # (measured 0.165 on j1, `logs/660`).
            measured = arm.joint_positions()
            arm.robot.set_dof_position_targets(
                [current + float(alpha) * (measured - current)], dof_indices=arm.arm_dofs
            )
            self._step_sim(1)
            self._tick_frame()
        arm.sync_command_to_measured()
        return True

    #: Joint error above which a `ready` transit is routed around the main
    #: conveyor instead of through it (see `_ready_transit`).
    READY_STAGE_ERR = 0.35

    def _lift_clear(self, side: str, lift: float = 0.20, cap: int = 420) -> float:
        """IK-lift the hand clear of the main belt before a long joint blend.

        The hand is raised to at least `belt_top + 0.30`, straight up from under
        the robot and up-and-inward from a far place pose (see the comment
        below). Position-only on purpose: the ready pose is reached by the joint
        blend that follows, and the wrist has to be free to fold clear of the
        belt. Returns the achieved jaw height [m].
        """
        arm = self.arms[side]
        # Start the IK from where the arm actually is. The carry leaves the
        # integrator up to ~1 rad ahead of the measured joints (its last command
        # held j7 at 0.57 while the wrist sat at 1.57, `logs/610`); worse, the
        # release leaves the *drive target* on a stale pose while the pads push
        # the arm away from it (`logs/630`), and a lift that follows a jammed
        # blend (`_recover_ready`) holds the ready pose while the arm sits ~1.5
        # rad away (`logs/640`). `_catch_up_drive` ramps the target onto the
        # measured over 20 ticks and re-anchors the integrator, so the first IK
        # step cannot command the whole gap in one tick.
        self._catch_up_drive(side)
        jaw = arm.jaw_centre().copy()
        # Lift up *and* back toward the body, not straight up. From a far place
        # pose a vertical lift is bought by the position-only IK with the wrist,
        # and the tool swings past horizontal on the way (measured: 88.9 -> 113.6
        # deg during this lift, A4 left, `logs/610`). A hand that is already out
        # over the belt is pulled inward as it rises; a hand under the robot
        # (hanging) has no inward component and rises straight.
        dx = max(0.0, float(jaw[0]) - 0.25)
        dy = max(0.0, abs(float(jaw[1])) - 0.20)
        inward = np.array([-dx, -dy * (1.0 if float(jaw[1]) >= 0.0 else -1.0), 1.0])
        direction = inward / max(float(np.linalg.norm(inward)), 1e-9)
        # The full 0.20 m (and `belt_top + 0.30`) is kept: a shorter lift from the
        # post-place seed was measured and the following blend jammed on j5
        # again (`ready_err` 1.52, `logs/640`) - the lift is what clears the
        # belt, and 5 cm is not enough. The wrist-neutral part of the fix is the
        # *direction*, not the length.
        reach = max(float(lift), self.belt_top + 0.30 - float(jaw[2]))
        goal = jaw + direction * reach
        target_z = float(goal[2])
        arm.hold_quaternion = None
        # Cap the per-tick IK step. Two thresholds matter: the posture gate flags a
        # commanded step above 0.15 rad/tick (the default 0.5 rad/tick made the
        # lift itself the worst command jump in the run, `logs/610`), and the
        # leg-boundary check flags a jump above 0.05 between the release and this
        # lift. 0.04 rad/tick clears both; the 0.20-0.60 m lift takes a few dozen
        # ticks instead of a handful.
        previous_max_step = arm.max_step
        arm.max_step = min(
            previous_max_step, float(os.environ.get("FRUIT_READY_LIFT_STEP", "0.04"))
        )
        try:
            for _ in range(max(1, int(cap))):
                if float(arm.jaw_centre()[2]) >= target_z - 0.05:
                    break
                arm.ik_step(arm.tcp_target_for_jaw(goal))
                self._step_sim(1)
                self._tick_frame()
        finally:
            arm.max_step = previous_max_step
        return float(arm.jaw_centre()[2])

    def _ready_transit(self, side: str, ticks: int = 90, settle: int = 120) -> bool:
        """Route a `ready` transit around the main conveyor when the seed is far.

        Measured (`logs/600`): from the hanging pose the straight joint blend to
        ready takes the hand under the belt slab and up through it; the hand jams
        on the belt's near face and the blend ends 1.29 rad short on j1 with the
        drive target exactly at ready (zero velocity while the target is held for
        10 s). With the main conveyor removed the same blend reaches ready to
        0.0135 rad, and with only the output belts 0.0150 - the main conveyor is
        the blocker, and j1 is the joint that stalls. A Cartesian lift first
        (0.20 m, and at least `belt_top + 0.30`) then the same blend reaches
        ready to 0.0147 rad from the hanging seed and 0.0131 rad from the
        measured post-place seed, which otherwise jams on j5 (`logs/499`).

        Returns False when the seed is already near ready, so the ordinary blend
        is kept for the arm that did not move.
        """
        arm = self.arms[side]
        ready = self._pose(side, "ready")
        err = float(np.max(np.abs(arm.joint_positions() - ready)))
        if err <= float(os.environ.get("FRUIT_READY_STAGE_ERR", str(self.READY_STAGE_ERR))):
            return False
        self._lift_clear(side)
        # The lift stops when the *measured* jaw is high enough, so its IK
        # integrator (and drive target) can still be ahead of the arm; the blend
        # that follows starts from the measured joints and would command the
        # whole lag in one tick (0.17-0.22 rad/tick on j1/j3, `logs/650`). Ramp
        # the target onto the arm first, exactly as at a leg boundary.
        self._catch_up_drive(side)
        self._blend_to(side, ready, ticks=ticks, settle=settle)
        return True

    def _blend_to(self, side: str, target, ticks: int = 90, settle: int = 120) -> None:
        """Min-jerk joint blend to an explicit configuration."""
        arm = self.arms[side]
        start = arm.joint_positions().copy()
        target = np.asarray(target, dtype=float).copy()
        for alpha in min_jerk_ramp(0.0, 1.0, max(1, ticks)):
            command = start + float(alpha) * (target - start)
            arm.robot.set_dof_position_targets([command], dof_indices=arm.arm_dofs)
            self._step_sim(1)
            self._tick_frame()
        for _ in range(max(0, settle)):
            arm.robot.set_dof_position_targets([target], dof_indices=arm.arm_dofs)
            self._step_sim(1)
            self._tick_frame()
        # The next `ik_step` (the grasp solve, the carry) integrates from the
        # *commanded* joints; after a blend the integrator still holds whatever
        # the previous IK left, which is a different pose. The teleport path
        # always synced here (`teleport_joints`), so the blend has to as well.
        arm.sync_command_to_measured()

    def _pose(self, side: str, name: str) -> np.ndarray:
        return np.asarray(self.waypoints["arms"][side][name], dtype=float)

    #: Joint error above which a smooth transit counts as blocked by a contact
    #: rather than merely lagging its drive.
    TRANSIT_TOL = 0.08

    def _recover_ready(self, side: str) -> bool:
        """Fallback for a `ready` blend that still ended short.

        The primary fix is `_ready_transit` (lift clear, then blend). If a blend
        still ends short - a seed or contact this routing does not know about -
        lift the hand clear *from wherever the arm is* and re-blend. The earlier
        fallback retracted to the hanging pose first, which sweeps the hand down
        across the belts and left the post-place stall worse (1.11 rad after
        recovery, `logs/499`); lifting from the current pose fixes the hanging
        seed to 0.0147 rad and the post-place seed to 0.0131 rad (`logs/600`).
        """
        arm = self.arms[side]
        ready = self._pose(side, "ready")
        err = float(np.max(np.abs(arm.joint_positions() - ready)))
        if err <= self.TRANSIT_TOL:
            return False
        joint = int(np.argmax(np.abs(arm.joint_positions() - ready))) + 1
        say(
            f"[task] {side} ready blend stopped {err:.2f} rad short on j{joint}; "
            "lifting the hand clear of the belt and re-blending"
        )
        self._lift_clear(side)
        self._blend_to(side, ready)
        err = float(np.max(np.abs(arm.joint_positions() - ready)))
        say(f"[task] {side} ready after recovery: {err:.4f} rad")
        return True

    def _grasp_quat(self, side: str) -> np.ndarray | None:
        """Tool attitude recorded for this arm's grasp pose, if the file has one.

        Pinning it keeps the jaws closing across the belt (along X) instead of
        letting a position-only IK solve drift the wrist back to jaws-along-Y.
        """
        entry = (self.waypoints.get("grasp_quaternion") or {}).get(side)
        return None if entry is None else np.asarray(entry, dtype=float)

    def _step_sim(self, steps: int = 1) -> None:
        """Advance physics by `steps` control ticks.

        Normally this is `SimulationManager.step`, which keeps the 1/120 s control
        timing exact. With `FRUIT_GUI_SMOOTH=1` it uses `update_app` instead: that
        is exactly one 1/60 s tick *plus* a UI pump, so the Isaac window stays
        responsive. Without the pump the GUI looks frozen for the whole attempt -
        the script drives physics in a Python loop and never services the
        interface, so the OS marks the window as not responding (measured: an
        update_app call = 1/60 s, a no-op update_app(0) does not advance physics).
        """
        from isaacsim.core.simulation_manager import SimulationManager

        steps = max(1, int(steps)) * substeps()
        if self.gui_smooth:
            # `update_app(steps=1)` advances one 1/60 s tick and pumps the UI, so
            # use it every other control tick: the average stays 1/120 s (the
            # timing the grasp was tuned at) and the window keeps responding.
            self._gui_tick += max(1, int(steps))
            if self._gui_tick >= 2:
                self._gui_tick = 0
                app_utils.update_app(steps=1)
            else:
                SimulationManager.step(steps=steps)
        else:
            SimulationManager.step(steps=steps)

    def _hold_with_gripper(self, side: str, sample) -> None:
        """Keep the kinematic fingers wrapped around a held fruit.

        The gripper is kinematic, so it has to be told where the fruit is every
        step while the arm carries it; the arm's own motion stays authoritative.
        """
        gap = self._closed_gap.get(side)
        if gap is None:
            return
        centre = self._grip_centre.get(side)
        quat = self._grip_quat.get(side)
        if centre is None or quat is None:
            return
        # Frozen orientation: the pads are a rigid tool, so they keep the pose
        # they gripped with instead of chasing the wrist, which is what made the
        # pads twist off the payload when the arm's IK lagged.
        self.grippers[side].follow_centre(
            np.asarray(centre, dtype=float),
            np.asarray(quat, dtype=float),
            float(gap),
        )

    def _recentre_gripper(self, side: str, sample) -> None:
        """Re-aim the closed pads on the fruit just before lifting it.

        The fruit settles (or rolls a centimetre) between the moment the grip is
        first closed and the moment the arm starts to lift, and the pads then sit
        off-centre and slide off it: the carry trace showed the pads 2 cm above the
        fruit at step 0 and 22 cm above it by the end of the lift (logs/173).

        This is slip *compensation*, not transport: with the pads rigid and
        orientation-frozen the grip carries the fruit by friction (0.1 mm of slip
        over a 27 cm lift), so the correction only absorbs the millimetres the
        fruit rolls while the line indexes. Each call moves the pads at most
        `FRUIT_SLIP_STEP` towards the fruit (default 1.5 mm per 0.17 s, a 9 mm/s
        crawl) instead of teleporting them onto it.
        """
        gap = self._closed_gap.get(side)
        if gap is None or not self.grippers[side].enabled:
            return
        quat = self._grip_quat.get(side)
        centre = self._grip_centre.get(side)
        if quat is None or centre is None:
            return
        rot = _quat_matrix(quat)
        centre = np.asarray(centre, dtype=float)
        target = np.asarray(self.spawner.position(sample), dtype=float)
        error = target - centre
        norm = float(np.linalg.norm(error))
        limit = float(os.environ.get("FRUIT_SLIP_STEP", "0.0015"))
        if norm > limit > 0.0:
            centre = centre + error * (limit / norm)
        self._grip_centre[side] = centre
        self._gripper_offset[side] = rot.T @ (
            centre - np.asarray(self.arms[side].tcp_position(), dtype=float)
        )
        self._hold_with_gripper(side, sample)

    def jaw_target(self, side: str, name: str) -> np.ndarray:
        """Jaw-centre target for a named pose. Mirrors scripts/30_calibrate_waypoints.py."""
        cfg = self.cfg
        sign = 1.0 if side == "left" else -1.0
        belt_top = self.belt_top
        if name == "ready":
            return np.array([cfg.pick_x, cfg.pick_y + sign * 0.05, belt_top + 0.20])
        if name == "grasp":
            # Aim the middle of the finger span at the reachable pick height. See
            # scripts/45_grasp_height_test.py and `grasp_clearance`: with the jaws
            # across the belt the wrist bottoms out well above the old v1 height.
            return np.array([cfg.pick_x, cfg.pick_y, belt_top + cfg.grasp_clearance])
        if name == "grasp_lift":
            return np.array([cfg.pick_x, cfg.pick_y + sign * 0.05, belt_top + 0.28])
        if name.startswith("place") or name.startswith("bin"):
            # v3: the place target is *above the output conveyor*, not inside a
            # bin. The old `bin{0,1}_above` / `bin{0,1}_inside` names both map
            # here - there is no lowering leg any more; the pads open
            # `output_place_clearance` above the moving belt and the fruit drops
            # onto it and is carried away along +X.
            index = 0 if "0" in name else 1
            px, py = cfg.output_belt_drop_points[index]
            return np.array([px, py, cfg.output_place_z])
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

    def _carry(self, side: str, sample, name: str, steps: int = 200) -> None:
        """Move the arm to a named pose with an attached fruit following the hand.

        Cartesian IK, not straight-line joint interpolation: a joint-space line
        from the pick pose to the output line passes through configurations the
        arm cannot physically reach and stalled there with ~1.6 rad of joint
        error, which is what made placements miss the target.
        """
        from isaacsim.core.simulation_manager import SimulationManager

        arm = self.arms[side]
        goal = self.jaw_target(side, name)
        gap = self._closed_gap.get(side)
        offset_tool = self._gripper_offset.get(side)
        if self.grippers[side].enabled and gap is not None and offset_tool is not None:
            # Lead with the gripper: it is kinematic, so its motion is exact - no IK
            # lag, no wrist drift - and the arm is commanded to follow. Carrying the
            # other way round lost the fruit in the lateral leg (logs/175-178).
            from isaacsim.core.simulation_manager import SimulationManager as _SM

            # Rigid tool: the pads keep the orientation they gripped with, so the
            # grip cannot twist off the payload when the arm's IK lags.
            quat = self._grip_quat.get(side)
            if quat is None:
                quat = np.asarray(arm.tcp_pose()[1], dtype=float)
            quat = np.asarray(quat, dtype=float)
            # Hold the wrist at the attitude the grip was taken with. With
            # position-only IK the arm finds its own wrist, and over the output
            # line the left arm's solve swings the tool to 93.6 deg from
            # vertical - the flattest posture in the cycle and the only tilt flag
            # the posture probe raises (`logs/428`). The pads are kinematic and
            # already carry the fruit at this attitude, so the arm can hold it
            # too. Off by default until measured (`FRUIT_CARRY_HOLD_QUAT=1`).
            hold_wrist = os.environ.get("FRUIT_CARRY_HOLD_QUAT", "0") == "1"
            if hold_wrist:
                arm.hold_quaternion = quat
            rot = _quat_matrix(quat)
            measured = np.asarray(self.grippers[side].pad_centre(), dtype=float)
            start = self._grip_centre.get(side)
            if start is not None:
                drift = float(np.linalg.norm(np.asarray(start, dtype=float) - measured))
                if drift > 0.01:
                    # The stored hand centre must be where the pads actually are:
                    # a stale value turned one lift into an 81 cm leg (logs/239).
                    say(
                        f"[task]   carry {name}: stored pad centre {drift * 1000:.0f} mm "
                        f"from the measured pads; re-anchoring"
                    )
                    start = None
            start = (measured if start is None else np.asarray(start, dtype=float)).copy()
            finish = np.asarray(goal, dtype=float) + np.array([0.0, 0.0, 0.0])
            delta = finish - start
            distance = float(np.linalg.norm(delta))
            direction = delta / max(distance, 1e-9)
            report = os.environ.get("FRUIT_MOTION_REPORT", "0") == "1"
            mu_eff = float(os.environ.get("FRUIT_MU_SAFETY", "0.6")) * float(
                self.grippers[side].mu
            )
            if os.environ.get("FRUIT_CARRY_PROFILE", "1") == "1":
                # Jerk-limited reference instead of the constant-velocity ramp:
                # the old interpolation demanded an infinite acceleration at both
                # ends of every leg, which is exactly where the fruit slipped.
                # While a fruit is held the acceleration budget is additionally
                # clipped to the friction cone (see fruit_sorting.motion).
                limits = TrajectoryLimits.from_env(CONTROL_DT)
                if name == "grasp_lift":
                    # Establishing the grip is the critical move: lift it slower
                    # than the transfer legs.
                    limits.v_max = float(os.environ.get("FRUIT_LIFT_VMAX", "0.18"))
                    limits.a_max = float(os.environ.get("FRUIT_LIFT_AMAX", "1.0"))
                limits = limits.limited_by_cone(direction, mu_eff)
                positions, velocities, accelerations = jerk_limited(distance, limits)
                commands = start[None, :] + positions[:, None] * direction[None, :]
            else:
                steps = int(steps * float(os.environ.get("FRUIT_CARRY_SLOWDOWN", "2.0")))
                commands = np.array(
                    [start + delta * (i / steps) for i in range(1, steps + 1)]
                )
                velocities = np.full(len(commands), distance * 120.0 / max(steps, 1))
                accelerations = np.zeros(len(commands))
            monitor = MotionMonitor(f"carry {name}", mu_eff=mu_eff) if report else None
            if monitor is not None:
                # Include the start sample, otherwise a velocity step *into* the
                # first tick (which is exactly what the old linear ramp does)
                # never shows up in the finite differences.
                monitor.add(0.0, self.grippers[side].pad_centre(), self.spawner.position(sample))
            # Slip detection and reactive regrasp. The pads are rigid, so the
            # payload's pose *in the hand frame* is constant while the grip holds;
            # any change of it is slip. On detection the controller does what a
            # real gripper does: close a little more, re-seat the hand on the
            # object, and continue on the same trajectory (the remaining profile
            # is rebased, so the motion stays jerk-limited).
            commands = np.asarray(commands, dtype=float)
            # Start the leg's IK from where the arm actually is: the previous leg
            # may have ended with the drive target *ahead* of the measured joints
            # (the close and the test lifts), and the first `ik_step` would then
            # command the difference in one tick (measured: a 0.21 rad j7 command
            # step at `align_close -> carry grasp_lift`, logs/610).
            arm.sync_command_to_measured()
            # Bound the per-tick IK step for the whole leg. 0.04 rad/tick is far
            # above what tracking the pads needs (the fastest carry profile is
            # 0.371 m/s = 3 mm/tick) and it keeps the first command after the
            # close under the leg-boundary check: the IK's first solution of the
            # leg can ask for ~0.2 rad in one tick (measured 0.2030 on j1,
            # logs/621) even when the position error is only a couple of
            # centimetres.
            previous_carry_step = arm.max_step
            arm.max_step = min(
                previous_carry_step, float(os.environ.get("FRUIT_CARRY_STEP", "0.03"))
            )
            # Thresholds come from the measured distributions: contact jitter sits
            # inside ~13 mm (logs/271) while a genuine loss of grip runs away
            # (140-380 mm, logs/263/271/280). Triggering at 25 mm therefore reacts
            # to real slip only - the earlier 3 mm trigger fired 128 times per run
            # on jitter alone and cost the default suite a point.
            slip_enabled = os.environ.get("FRUIT_SLIP_RECOVERY", "1") == "1"
            slip_trigger = float(os.environ.get("FRUIT_SLIP_TRIGGER", "0.025"))
            # Gross relative motion means the payload is being held by something
            # else (the support surface) rather than sliding in the grip; reacting
            # to it just drags the pads around on the surface.
            slip_react_max = float(os.environ.get("FRUIT_SLIP_REACT_MAX", "0.060"))
            # Default 0: do *not* squeeze harder when the payload slips. The
            # reaction used to close another 1 mm per event, and that made the
            # problem it was reacting to worse - the payload is not lost to
            # insufficient normal force, it is *ejected* along the pad faces (see
            # the slip-debug note below), so adding interference adds to the
            # ejection. A/B, ten attempts each, identical otherwise: 1 mm per event
            # gave 4 affected legs and 17 re-seats (`logs/145/146`), 0 gave 2 legs
            # and 6 re-seats (`logs/149`, reproduced bit-identically in `logs/151`),
            # both at 10/10. The squeeze that carries the fruit is set at closure
            # and is not touched by this knob.
            squeeze_step = float(os.environ.get("FRUIT_SLIP_SQUEEZE_STEP", "0.0"))
            gap_min = float(sample.diameter) * float(
                os.environ.get("FRUIT_GRIPPER_MIN_SQUEEZE", "0.85")
            )
            gap_command = float(gap)
            slip_ref = rot.T @ (
                np.asarray(self.spawner.position(sample), dtype=float)
                - np.asarray(self.grippers[side].pad_centre(), dtype=float)
            )
            slip_max = 0.0
            slip_vel_max = 0.0
            rel_prev = slip_ref
            recoveries = 0
            coherent = self._coherent.get(side, False)
            finger_len = self._fingertip_offset(side) if coherent else 0.0
            for i in range(len(commands)):
                centre = commands[i]
                if coherent:
                    # Rigid hand: command the *palm* along the profile and let the
                    # pads follow wherever the arm actually is - the IK lag is real
                    # hand deflection, and the payload is carried by friction.
                    arm.ik_step(
                        arm.tcp_target_for_jaw(centre + np.array([0.0, 0.0, finger_len + PAD_LIFT]))
                    )
                    quat = np.asarray(arm.tcp_pose()[1], dtype=float)
                    rot = _quat_matrix(quat)
                    centre = np.asarray(arm.jaw_centre(), dtype=float) + rot @ np.array(
                        [0.0, 0.0, finger_len]
                    )
                    self.grippers[side].follow_centre(centre, quat, gap_command)
                    self._grip_centre[side] = np.asarray(centre, dtype=float)
                    self._grip_quat[side] = quat
                else:
                    # Command the hand first and let the *arm* follow where the hand
                    # actually went: `follow_centre` rate-limits the pads, so using
                    # the request here would drive the arm towards a pose the hand
                    # cannot be at in one tick.
                    centre = np.asarray(
                        self.grippers[side].follow_centre(centre, quat, gap_command),
                        dtype=float,
                    )
                    self._grip_centre[side] = centre
                    arm.ik_step(arm.tcp_target_for_jaw(centre - rot @ offset_tool))
                self._step_sim(1)
                self._tick_frame()
                self._record(self._action9(arm.joint_positions(), arm))
                # Always *measure* the payload's motion in the hand frame - it is
                # the honest slip/jitter signal and it goes into the motion report;
                # only *react* to it when the recovery is enabled.
                fruit = np.asarray(self.spawner.position(sample), dtype=float)
                pads = np.asarray(self.grippers[side].pad_centre(), dtype=float)
                slip = float(np.linalg.norm((rot.T @ (fruit - pads)) - slip_ref))
                slip_max = max(slip_max, slip)
                rel_now = rot.T @ (fruit - pads)
                slip_vel_max = max(
                    slip_vel_max, float(np.linalg.norm(rel_now - rel_prev)) / CONTROL_DT
                )
                rel_prev = rel_now
                if slip_enabled:
                    if slip_trigger < slip <= slip_react_max:
                        recoveries += 1
                        gap_command = max(gap_min, gap_command - squeeze_step)
                        # Pad centre that restores the gripped relation to the fruit.
                        target = fruit - rot @ slip_ref
                        # Applied in one go: with the grip holding, moving the pads
                        # *with* the fruit changes nothing in the hand frame, so a
                        # clamped correction can never restore the relation - it
                        # just re-fires (logs/264: 128 events, all ~7.6 mm). The
                        # pads have to be slid relative to the fruit, which is a
                        # regrasp and is bounded by `slip_react_max`.
                        correction = target - pads
                        reseated = pads + correction
                        # The pads are rate-limited, so they may not reach
                        # `reseated` in this tick; remember where they really are
                        # and let the next ticks converge (the rebased path below
                        # continues from `reseated`, so the hand simply lags it).
                        placed = self.grippers[side].follow_centre(
                            reseated, quat, gap_command
                        )
                        self._grip_centre[side] = np.asarray(placed, dtype=float)
                        self._closed_gap[side] = gap_command
                        if i + 1 < len(commands):
                            commands[i + 1 :] = (
                                reseated[None, :]
                                + (positions[i + 1 :] - positions[i])[:, None] * direction[None, :]
                            )
                        say(
                            f"[task]   slip {slip * 1000:.1f} mm during {name}: "
                            f"grip {gap_command * 1000:.1f} mm, re-seated by "
                            f"{np.linalg.norm(correction) * 1000:.1f} mm ({recoveries}x)"
                        )
                        if os.environ.get("FRUIT_SLIP_DEBUG") == "1":
                            say(
                                f"[task]     slip debug: fruit={np.round(fruit, 4).tolist()} "
                                f"pads={np.round(pads, 4).tolist()} "
                                f"fruit_v={np.round(self.spawner.velocity(sample), 4).tolist()} "
                                f"pad_cmd={np.round(centre, 4).tolist()} "
                                f"rel={np.round(rot.T @ (fruit - pads), 4).tolist()} "
                                f"ref={np.round(slip_ref, 4).tolist()}"
                            )
                if monitor is not None:
                    monitor.add(
                        (i + 1) * CONTROL_DT,
                        self.grippers[side].pad_centre(),
                        self.spawner.position(sample),
                    )
                if (i + 1) % 20 == 0:
                    # Bounded slip compensation (1.5 mm per call): the pads keep
                    # following the payload within a few millimetres without the
                    # teleporting that used to do the carrying.
                    self._recentre_gripper(side, sample)
            if monitor is not None:
                summary = monitor.summary()
                summary["label"] = (
                    f"carry {name}: {distance * 100:.0f} cm, {len(commands)} ticks, "
                    f"|v|cmd={np.abs(velocities).max():.3f} |a|cmd={np.abs(accelerations).max():.3f}, "
                    f"slip_max={slip_max * 1000:.1f} mm, "
                    f"in-hand |v|max={slip_vel_max:.3f} m/s, recoveries={recoveries}"
                )
                say(MotionMonitor.format(summary))
            for _ in range(30):
                # When the leg was rebased after a slip, `finish` is up to a
                # re-seat away from where the pads are; take the achieved centre
                # (the rate limiter converges to `finish` well inside these 30
                # ticks) so the grip bookkeeping stays truthful.
                placed = np.asarray(
                    self.grippers[side].follow_centre(finish, quat, gap_command),
                    dtype=float,
                )
                self._grip_centre[side] = placed
                arm.ik_step(arm.tcp_target_for_jaw(placed - rot @ offset_tool))
                self._step_sim(1)
                self._record(self._action9(arm.joint_positions(), arm))
            self._gripper_offset[side] = offset_tool
            if hold_wrist:
                arm.hold_quaternion = None
            if os.environ.get("FRUIT_CARRY_FREEZE", "1") == "1":
                # Stop the arm where it is instead of letting it settle into the
                # last IK command. At the far end of a place leg that command is
                # a flattened wrist (the IK buys reach with it): the left arm
                # drifts from 84.6 to 93.6 deg of tool tilt after the carry ends,
                # which is the only >90 deg posture in the cycle (logs/428). The
                # pads are kinematic and carry the payload exactly, so freezing
                # the arm one or two centimetres short of its target costs
                # nothing and keeps the wrist neutral.
                #
                # Ramp the drive target to the measured pose over 20 ticks: the
                # IK's last command can be 0.2-0.5 rad ahead of the arm, and
                # setting the target to the measured in one tick is itself a
                # command discontinuity (0.4875 on j7 at `carry place0 ->
                # after_place0`, logs/621) - exactly what the freeze is there to
                # avoid. The ramp also gives the wrist time to relax from the
                # flattened command instead of snapping back.
                current = np.asarray(
                    arm.robot.get_dof_position_targets().numpy(), dtype=float
                )[0][arm.arm_dofs]
                measured = arm.joint_positions()
                for alpha in min_jerk_ramp(0.0, 1.0, 20):
                    arm.robot.set_dof_position_targets(
                        [current + float(alpha) * (measured - current)],
                        dof_indices=arm.arm_dofs,
                    )
                    self._step_sim(1)
                arm.sync_command_to_measured()
            arm.max_step = previous_carry_step
            if os.environ.get("FRUIT_CARRY_DEBUG") == "1":
                say(
                    f"[task]   carry(gripper-led) {name}: pads={np.round(finish, 3).tolist()} "
                    f"fruit={np.round(self.spawner.position(sample), 3).tolist()}"
                )
            return
        offset = arm.tcp_position() - arm.jaw_centre()
        # Slower lateral motion while carrying: the grip survives a vertical lift
        # but not a fast sideways sweep (logs/176).
        steps = int(steps * float(os.environ.get("FRUIT_CARRY_SLOWDOWN", "2.0")))
        for _ in range(steps):
            arm.ik_step(goal + offset)
            self._step_sim(1)
            self.spawner.follow(sample, arm.jaw_centre())
            self._hold_with_gripper(side, sample)
            if _ % 20 == 0:
                # A real gripper keeps the fruit centred between its pads for the
                # whole carry; without this the pads drift off the fruit as the
                # wrist turns (logs/173) and it slides out.
                gripper = self.grippers[side]
                gap = self._closed_gap.get(side)
                if gripper.enabled and gap is not None:
                    offset_from_pads = float(
                        np.linalg.norm(
                            np.asarray(self.spawner.position(sample), dtype=float)
                            - gripper.pad_centre()
                        )
                    )
                    self._recentre_gripper(side, sample)
                    if offset_from_pads > 0.008:
                        # The fruit is creeping: tighten a millimetre and keep
                        # going, rather than letting it work its way out during the
                        # lateral carry (logs/176: 4/8 grasped, 0/8 placed).
                        floor = float(sample.diameter) * float(
                            os.environ.get("FRUIT_GRIPPER_MIN_SQUEEZE", "0.85")
                        )
                        gap = max(floor, float(gap) - 0.001)
                        self._closed_gap[side] = gap
                        self._hold_with_gripper(side, sample)
            if os.environ.get("FRUIT_GRIPPER_DEBUG") == "1" and _ % 40 == 0:
                gripper = self.grippers[side]
                if gripper.enabled:
                    pads = gripper.pad_centre()
                    fruit = np.asarray(self.spawner.position(sample), dtype=float)
                    say(
                        f"[task]   carry {name} step {_:3d}: pads={np.round(pads, 4).tolist()} "
                        f"fruit={np.round(fruit, 4).tolist()} "
                        f"rel={np.round(fruit - pads, 4).tolist()} "
                        f"tcp_z={arm.tcp_position()[2]:.4f}"
                    )
            self._tick_frame()
            self._record(self._action9(arm.joint_positions(), arm))
            if np.linalg.norm(arm.jaw_centre() - goal) < 0.010:
                break
        for _ in range(30):
            arm.ik_step(goal + offset)
            self._step_sim(1)
            self.spawner.follow(sample, arm.jaw_centre())
            self._hold_with_gripper(side, sample)
            self._record(self._action9(arm.joint_positions(), arm))
        if os.environ.get("FRUIT_CARRY_DEBUG") == "1":
            say(
                f"[task]   carry {name}: jaw={np.round(arm.jaw_centre(), 3).tolist()} "
                f"goal={np.round(goal, 3).tolist()} "
                f"err={float(np.linalg.norm(arm.jaw_centre() - goal)):.4f} m"
            )

    # ------------------------------------------------------------------ #
    # Data collection
    # ------------------------------------------------------------------ #
    def _action9(self, arm_config: np.ndarray, arm, finger_value: float | None = None) -> np.ndarray:
        """Pack an action as 7 arm joints + 2 finger joints.

        With the kinematic gripper the finger channel is the *gap the pads are
        actually holding*, expressed in the gripper's own joint units, so a policy
        trained on these frames closes the real gripper rather than the OpenArm
        fingers it no longer uses.
        """
        if finger_value is None:
            gap = self._closed_gap.get(arm.spec.side) if hasattr(self, "_closed_gap") else None
            if gap is not None and self.grippers[arm.spec.side].enabled:
                value = arm.gripper_value_for_separation(float(gap))
            else:
                value = arm.finger_opening()
        else:
            value = float(finger_value)
        return np.concatenate(
            [np.asarray(arm_config, dtype=np.float32).reshape(-1)[:7], [value, value]]
        ).astype(np.float32)

    def _record(self, action: np.ndarray | None = None) -> None:
        """Sample one training frame if a recorder is attached."""
        if self.recorder is None or not self.recorder.recording:
            return
        if not self.recorder.tick():
            return
        # Actions are always 9-D: 7 arm joints plus the two finger joints.
        if action is None or np.asarray(action).shape[-1] != 9:
            return
        arm = self.arms[self.current_arm]
        observation: dict = {
            "joint_positions": arm.dof_positions().astype(np.float32),
            "finger_opening": np.array([arm.finger_opening()], dtype=np.float32),
            "goal": self.current_goal,
        }
        tactile = self.tactile.read()
        observation["tactile"] = np.array(
            [
                tactile.get("left", _EMPTY_TACTILE).normal_force,
                tactile.get("right", _EMPTY_TACTILE).normal_force,
            ],
            dtype=np.float32,
        )
        if self.scene.camera_sensor is not None:
            observation.update(
                camera_observation(self.scene.camera_sensor, ("rgb", "distance_to_image_plane"))
            )
            # Target mask: instance-id segmentation, reduced to the fruit the
            # slow-loop decision selected. This is the 5th visual channel the
            # design calls for (RGB + depth + mask).
            try:
                raw = self.scene.camera_sensor.get_data("instance_id_segmentation")
                seg = to_numpy(raw)
                if seg is not None:
                    seg = np.asarray(seg)
                    if seg.ndim == 3:
                        seg = seg[..., 0]
                    # Map the target fruit's prim path to its rendered instance id
                    # so the mask channel isolates *this* fruit.
                    target_id = 0
                    info = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else {}
                    labels = info.get("idToLabels", {}) if isinstance(info, dict) else {}
                    want = self.current_sample.prim_path if self.current_sample else None
                    for key, value in labels.items():
                        if want and want in str(value):
                            target_id = int(key)
                            break
                    # Store the binary target mask (uint8), not the raw int32 id
                    # map: same information for the policy and ~8x smaller.
                    observation["target_mask"] = (
                        (seg == target_id).astype(np.uint8) * 255
                    )
            except Exception:  # noqa: BLE001
                pass
        if self.current_sample is not None:
            observation["fruit_position"] = self.spawner.position(self.current_sample).astype(np.float32)
        self.recorder.add(observation, action)

    def _tick_frame(self) -> None:
        """Refresh the camera / hand a frame to the video recorder.

        ``RenderingManager.render()`` renders without advancing physics, so the
        control loop keeps its exact 1/120 s timing. ``update_app`` would render
        too, but it advances the simulation by a variable amount.
        """
        if self.frame_callback is not None:
            self.frame_callback()
        elif self.recorder is not None:
            RenderingManager.render()

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
        smooth = os.environ.get("FRUIT_SMOOTH_TRANSIT", "1") == "1"
        for name in names:
            arm = self.arms[name]
            arm.set_gripper(arm.OPEN)
            if not smooth:
                # Teleport to the calibrated ready pose: commanding it from the
                # hanging pose stalls the elbow drive.
                arm.teleport_joints(self._pose(name, "ready"))
                continue
            self._transit_to(name, "ready")
            if os.environ.get("FRUIT_READY_RECOVERY", "1") == "1":
                self._recover_ready(name)

    def choose_arm(self, y: float) -> str:
        return "left" if y >= 0.0 else "right"

    def select_target(self, states: list[dict], lead_time: float = 0.0) -> dict | None:
        """Choose the next fruit that will reach the pick pose.

        Falls back to the fruit closest to the middle of the belt window when
        nothing is upstream yet.
        """
        upstream: list[tuple[float, dict]] = []
        middle: list[tuple[float, dict]] = []
        station: list[tuple[float, dict]] = []
        for state in states:
            if self.failures.get(int(state["index"]), 0) >= self.max_retries:
                continue  # diverted after repeated failures
            pos = state["position"]
            if pos[2] < self.belt_top - 0.02:
                continue  # already fell off
            if state["diameter"] > self.cfg.gripper_max_object:
                continue  # jaws cannot straddle this fruit
            # Only fruit *on the main belt* are candidates. A fruit already placed
            # on a raised output conveyor sits at the same along-belt position
            # window (the +Y belt overlaps it) and must not be picked again -
            # measured: `logs/425` attempt 3 selected a peach a previous attempt
            # had put on the +Y belt at x=1.13. The main belt is the only surface
            # at the pick height near its centre line.
            if abs(float(pos[0]) - self.cfg.belt_center[0]) > 0.30:
                continue  # on an output conveyor (or off the line)
            if float(pos[2]) > self.belt_top + 0.12:
                continue  # above the main belt surface: already on an output belt
            along = float(pos[1])
            # A fruit selected *inside* the old station window is lost with the
            # smooth pre-pose: the arm needs ~1.1 s to reach the grasp pose
            # (`logs/611_accept.log`) and the belt carries a fruit 6-7 cm in that
            # time, so a fruit selected at +0.02..+0.05 is already past the
            # tracking window when the pre-pose ends (attempts 0 and 1 there:
            # dy=-0.046/-0.060 at step 0). With the smooth pre-pose the station
            # window therefore starts one pre-pose travel upstream; the upstream
            # window keeps its own 0.18 floor and the station branch covers the
            # band between the two, so no position inside the window is
            # unreachable. A fruit below the line is carried past uncaught (it is
            # recirculated) but no attempt is spent on it.
            prepose_lead = (
                float(os.environ.get("FRUIT_PREPOSE_LEAD", "0.12"))
                if os.environ.get("FRUIT_SMOOTH_TRANSIT_PREPOSE", "1") == "1"
                else 0.0
            )
            station_floor = self.cfg.pick_y - 0.02 + prepose_lead
            upstream_floor = max(self.cfg.pick_y + 0.18, station_floor)
            if (
                # Default on: the gate presents one fruit at a time, so taking what
                # the feeder presents is both what a real cell does and what keeps
                # the cycle short. The reject policy (FRUIT_MAX_RETRIES) is what
                # makes it safe - without it the same hard fruit was retried until
                # the attempts ran out (logs/277).
                os.environ.get("FRUIT_STATION_FIRST", "1") == "1"
                and station_floor <= along <= self.cfg.pick_y + 0.18
            ):
                # Optional: take whichever fruit is already gated at the station
                # (a real cell picks what the feeder presents). Only sensible
                # together with the reject policy, otherwise the same hard fruit
                # is retried until the attempts run out (logs/277).
                station.append((along, state))
                continue
            # Upstream only, and within a window the arm can settle in: at 0.06 m/s
            # the old v1 0.8-1.32 m window is far too deep, and the 0.18-0.80 gap
            # was a dead zone where a fruit could sit unselectable (logs/363). A
            # fruit *past* the station must not be selected at all - with the belt
            # running it keeps going and cannot be caught (logs/388 selected one,
            # the belt carried it off the end, and the task teleported it back).
            if upstream_floor < along <= self.cfg.pick_y + 0.85:
                upstream.append((along, state))  # smallest y first = first to arrive
        if station:
            ordered = sorted(station, key=lambda item: item[0])
            return self._balance_arm(ordered)
        if upstream:
            ordered = sorted(upstream, key=lambda item: item[0])
            return self._balance_arm(ordered)
        if middle:
            return min(middle, key=lambda item: item[0])[1]
        return None

    def _balance_arm(self, ordered: list[tuple[float, dict]]) -> dict:
        """Prefer a fruit whose grade sends it to the less-used arm.

        The collector used to take the next fruit in arrival order, which - with a
        fixed seed - produced 17 right-arm episodes and no left-arm ones. Sorting
        is a two-arm task, so the balance is worth a small amount of look-ahead.
        """
        wanted = "left" if self._episodes_by_arm.get("left", 0) <= self._episodes_by_arm.get(
            "right", 0
        ) else "right"
        for _x, state in ordered[:4]:
            grade = state.get("grade")
            arm = "left" if grade == "A" else "right"
            if arm == wanted:
                return state
        return ordered[0][1]

    # ------------------------------------------------------------------ #
    # Main routine
    # ------------------------------------------------------------------ #
    def run(self, state: dict, bin_index: int, lead_time: float = 1.2,
            verbose: bool = True) -> EpisodeResult:
        """Attempt one pick and book-keep the outcome.

        `bin_index` is the output lane (0 = +Y, left arm; 1 = -Y, right arm) -
        the field keeps its old name because it is part of the recorded goal
        vector and the episode metadata.

        The statistics and the reject policy live here rather than in the calling
        script: only `scripts/20_pick_place.py` used to call `note_result`, so the
        demonstration collector retried the *same* hard strawberry nine times in a
        row instead of diverting it (logs/328).
        """
        self.spawner.protected = int(state["index"]) if "index" in state else None
        try:
            result = self._run_impl(state, bin_index, lead_time, verbose)
        finally:
            self.spawner.protected = None
        self.note_result(result)
        return result

    def _run_impl(self, state: dict, bin_index: int, lead_time: float = 1.2,
                  verbose: bool = True) -> EpisodeResult:
        sample = next(s for s in self.spawner.samples if s.index == state["index"])
        result = EpisodeResult(
            sample_index=sample.index, category=sample.category, grade=sample.grade
        )
        # Each arm only reaches the conveyor on its own side (crossing the body
        # is outside the workspace), so the destination lane decides which arm
        # picks.
        arm_name = "left" if bin_index == 0 else "right"
        arm = self.arms[arm_name]
        result.arm = arm_name
        self._episodes_by_arm[arm_name] = self._episodes_by_arm.get(arm_name, 0) + 1
        # Start every attempt with clean gripper state: a failed attempt used to
        # leave the pads closed somewhere on the belt, which then blocked arriving
        # fruit and stalled the whole collector (20 minutes without an episode).
        self._closed_gap[arm_name] = None
        self._gripper_offset[arm_name] = None
        self._grip_quat[arm_name] = None
        self._grip_centre[arm_name] = None
        self.grippers[arm_name].park()
        self.current_arm = arm_name
        self.current_sample = sample
        self.current_goal = np.array(
            [
                *np.asarray(state["position"], dtype=np.float32),
                *np.asarray(state["velocity"], dtype=np.float32),
                float(sample.diameter),
                float(bin_index),
            ],
            dtype=np.float32,
        )
        if self.recorder is not None:
            self.recorder.begin(
                EpisodeMeta(
                    index=int(os.environ.get("FRUIT_EPISODE_INDEX", "0")),
                    category=sample.category,
                    grade=sample.grade,
                    arm=arm_name,
                    bin_index=bin_index,
                    diameter=sample.diameter,
                )
            )
        if verbose:
            say(
                f"[task] target {sample.category} (grade {sample.grade}, "
                f"{sample.diameter * 100:.1f} cm) with {arm_name} arm"
            )

        arm.set_gripper(arm.OPEN)
        # Feed sequencing: the line *holds* (belt stopped) while the arm moves
        # into position, and is only started for the feed phase below. Starting it
        # up front let the selected fruit roll past the station during the ~4 s
        # pre-pose: three of ten attempts died with "fruit already passed the pick
        # pose" (logs/294).
        belt = getattr(self.spawner, "belt", None)
        # `FRUIT_DYNAMIC_PICK=1` (default) runs a *dynamic* line instead: the belt
        # never stops and fruit are taken while they travel. The hand-off, the
        # close and the carry all re-place the pads on the fruit's measured centre
        # every tick already, so the grasp tracks by construction - what made it
        # impossible before was the belt being stopped and the fruit being
        # required to come to rest (`FRUIT_DYNAMIC_PICK=0` restores that
        # behaviour).
        dynamic_pick = os.environ.get("FRUIT_DYNAMIC_PICK", "1") == "1"
        if belt is not None and not dynamic_pick:
            belt.stop()

        # 1. Go to the grasp pose, aligned with this fruit's lateral position.
        #
        # Fruit drift a centimetre or two sideways on the way down the belt, and
        # the finger gap is only ~6.5 cm, so a fixed centreline pose would let
        # the jaws hit the fruit edge-on. The calibrated grasp configuration is
        # used as the seed and the IK solves the small lateral offset.
        t0 = self._sim_time()
        self._attempt_sim_t0 = t0
        # Grasp height. The wrist cannot descend to the fruit's equator with the
        # jaws across the belt (measured minimum ~belt_top + 0.08, see
        # `SceneConfig.grasp_clearance`), so the arm is aimed at the reachable pick
        # height and the *pads*, placed on the fruit's measured centre by the
        # kinematic gripper, do the grasping.
        grasp_goal = self.jaw_target(arm_name, "grasp").copy()
        # Aim the arm at the *reachable* pick pose, not at the fruit's equator: the
        # pads are placed on the fruit's measured centre by the kinematic gripper, so
        # `pad_forward` / `band_centre` offsets only mean anything for the coherent
        # hand, which computes its own fingertip target further down.
        free = np.array(
            [self.cfg.pick_x, self.cfg.pick_y, self.belt_top + self.cfg.grasp_clearance]
        )
        # The pads are placed on the fruit's *measured* centre by the kinematic
        # gripper, so the arm target is just the reachable pick pose: the pad-forward
        # and band-centre offsets only mean anything for the coherent hand, which
        # computes its own fingertip target further down. Aiming the arm at the
        # fruit's equator instead put it 3-7 cm outside the reachable band and the
        # position-only fallback then wandered (right arm, 70 mm residual).
        grasp_goal = free.copy()
        # Pre-pose. The default used to be an instant `teleport_joints`, which is
        # the largest command discontinuity the posture probe reports (0.39-1.05
        # rad on j1 at the attempt boundary, logs/428). The blend gets to the same
        # configuration without the jump - and it *does* get there: measured from
        # the ready pose the residual is 8 mm and the jaw lands on the pick point
        # (logs/490) - but on a dynamic line its duration is a feed-time budget.
        # The fruit travels ~0.06 m/s, so the 140+60-tick version (2.3 s to the
        # pick pose) let it pass the tracking window and cost two of five
        # attempts; 45 ticks (0.4 s) keeps the pre-pose within the window
        # (logs/499).
        if os.environ.get("FRUIT_SMOOTH_TRANSIT_PREPOSE", "1") == "1":
            self._transit_to(
                arm_name,
                "grasp",
                ticks=int(os.environ.get("FRUIT_PREPOSE_TICKS", "45")),
                # No settle: the pre-pose holds the calibrated configuration (the
                # solve below is skipped), and the wait loop keeps commanding that
                # same configuration, so the arm finishes converging there while
                # the fruit travels. Waiting here would only spend feed time - on
                # a dynamic line the fruit moves ~0.06 m/s and the first two
                # attempts of a run select fruit that is already near the window
                # (measured: `dy=-0.046/-0.060` with a 1.08 s pre-pose, `logs/611`,
                # `logs/621`).
                settle=int(os.environ.get("FRUIT_PREPOSE_SETTLE", "0")),
            )
        else:
            arm.teleport_joints(self._pose(arm_name, "grasp"))
        # Pin the calibrated grasp attitude: with the belt crossing the robot's
        # front the jaws must close along X, and a position-only solve drifts the
        # wrist back to jaws-along-Y (the exposed 7 cm finger gap then straddles
        # nothing). `configs/waypoints*.json` records the attitude it was solved
        # with; older files have none and stay position-only.
        arm.hold_quaternion = self._grasp_quat(arm_name)
        # The low grasp pose is near the edge of the workspace, so fall back to
        # random restarts if the calibrated seed does not converge.
        #
        # Default is *not* to solve: the blend above already puts the arm on the
        # calibrated grasp configuration, and the closed-loop correction is both
        # nearly a no-op (it converges to its own 8 mm tolerance, and the jaw is
        # within ~5 mm of the target before it starts) and the noisy part - its
        # ~400 iterations cost 0.3-0.5 s of feed time on a moving line, and where
        # it starts depends on the blend's lag, which is what scattered the grasp
        # across j3/j5 branches (3 of 5 attempts flagged `reconfigured`,
        # `logs/610`). The pads are placed on the fruit's measured centre, so the
        # arm's exact pose is cosmetic; holding the calibrated pose is
        # deterministic. `FRUIT_PREPOSE_SOLVE=1` restores the solve.
        if os.environ.get("FRUIT_PREPOSE_SOLVE", "0") == "1":
            residual = arm.solve_to(grasp_goal, iterations=400, tolerance=0.008)[1]
            # The 4-restart re-solve costs ~1500 extra physics steps (13 s of
            # simulated time - a quarter of the whole cycle, see the [stats] line in
            # logs/292) and it only matters when the *arm's own* geometry does the
            # grasping. With the kinematic pads enabled the pads are placed on the
            # fruit's measured position, so the pose is cosmetic: skip it.
            if residual > 0.015 and not self.grippers[arm_name].enabled:
                residual = arm.solve_to(
                    grasp_goal, iterations=400, tolerance=0.008, restarts=4, seed=7
                )[1]
            grasp_config = arm.joint_positions()
        else:
            grasp_config = self._pose(arm_name, "grasp").copy()
            residual = float(np.linalg.norm(arm.jaw_centre() - grasp_goal))
        # Release the attitude hold: the carry and the place poses are position-only.
        arm.hold_quaternion = None
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
        # The pads are placed on the fruit's *measured* position, so a fruit a few
        # centimetres past the nominal jaw position is still perfectly graspable -
        # the jaws are cosmetic. Only a fruit that has run well past the station
        # is a miss. (The strict check rejected fruit sitting in the station window
        # and cost 2-3 attempts per ten, logs/294/297.)
        if not dynamic_pick and float(pos[1]) < float(jaw_hold[1]) - 0.10:
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
        if belt is not None:
            # Run the line for the feed phase (the dynamic line keeps it at its
            # constant speed for the whole run).
            belt.start()
            self._gate_open_step = 0
        jaw_y = float(arm.jaw_centre()[1])
        last_y = None
        stalled = 0
        indexed = False
        settled = 0
        for step in range(8000):
            pos = self.spawner.position(sample)
            dy = float(pos[1]) - jaw_y
            if dynamic_pick:
                # Take the fruit while it moves. The pads are placed on the fruit's
                # measured centre by the hand-off below and re-placed every tick
                # through the close, so the requirement is only that the close-and-
                # lift fits inside the arm's window and that the fruit is *near the
                # arm* when the grip is taken: the pads are carried at their offset
                # from the arm's tool point, so grasping a fruit 20 cm up the belt
                # (the first version's default) leaves the payload on a 20 cm lever.
                # Start when the fruit is a few centimetres upstream (+Y) of the
                # jaw and give up once it is past the downstream end of the reach.
                track_start = float(os.environ.get("FRUIT_TRACK_START", "0.05"))
                track_end = -float(os.environ.get("FRUIT_TRACK_END", "0.02"))
                if track_end <= dy <= track_start:
                    arrived = True
                    if verbose:
                        say(
                            f"[task]   taking it on the fly: fruit_y={float(pos[1]):.4f} "
                            f"dy={dy:+.4f} m at "
                            f"{float(belt.encoder_speed) if belt is not None else 0.0:+.3f} m/s"
                        )
                    break
                if dy < track_end:
                    # The fruit ran past the tracking window: it is downstream and
                    # still moving away, so this attempt is a miss. Do not fall
                    # through to the "reached the jaw" branch - that used to accept
                    # a fruit that had already left the belt end (logs/388).
                    if verbose:
                        say(f"[task]   fruit passed the tracking window (dy={dy:+.3f} m)")
                    break
            if step % 50 == 25:
                # Nothing on the line can reach the station any more (everything is
                # parked, on the output line, or already past): stop burning cycle
                # time. The 8000-step wait is 66 s of simulated time - about 10
                # minutes of wall clock on this machine - and it was being spent
                # staring at an empty line (logs/296).
                incoming = False
                for other in self.spawner.active:
                    if other.parked or other.held:
                        continue
                    other_pos = self.spawner.position(other)
                    if (
                        abs(float(other_pos[0]) - self.cfg.belt_center[0]) > 0.30
                        or float(other_pos[2]) > self.belt_top + 0.12
                    ):
                        continue  # placed on an output conveyor / off the line
                    if float(other_pos[1]) > self.cfg.pick_y + 0.05:
                        incoming = True
                        break
                if not incoming and float(pos[1]) > self.cfg.pick_y + 0.6:
                    if verbose:
                        say("[task]   no fruit left on the line - abandoning the attempt")
                    result.notes.append("no fruit left on the line")
                    break
            if verbose and (step % 400 == 0 or step < 6):
                say(
                    f"[task]   wait step={step} fruit_y={float(pos[1]):.4f} "
                    f"fruit_x={float(pos[0]):+.4f} fruit_z={float(pos[2]):.4f} dy={dy:+.4f}"
                )
            if not dynamic_pick and dy <= 0.0:
                arrived = True
                break
            if last_y is not None and abs(float(pos[1]) - last_y) < 5e-4:
                stalled += 1
            else:
                stalled = 0
            last_y = float(pos[1])
            # Index the line: stop the belt once the fruit is close and let it
            # coast to a halt between the open jaws. Closing on a fruit that the
            # belt is still dragging was impossible - the fruit travelled ~6 cm
            # out of the jaws during the settling time and every grasp read 0 N.
            # A *dynamic* line never does this: the belt keeps running and the
            # fruit is taken on the fly (below).
            if not dynamic_pick and not indexed and dy <= 0.025:
                if belt is not None:
                    belt.stop()
                self._record_gate(step)
                indexed = True
            # Fruit often stall at the foot of the pick-nest ramp instead of
            # climbing it. Stop the line and accept them there: the hand-off seats
            # them on the nest anyway, so they only have to be within reach.
            if not dynamic_pick and not indexed and stalled > 200 and dy <= 0.35:
                if belt is not None:
                    belt.stop()
                self._record_gate(step)
                indexed = True
                if verbose:
                    say(f"[task] fruit stalled at dy={dy:+.3f} m; indexing the line here")
            if indexed:
                # Wait for the fruit to come to rest, then accept it: the jaws are
                # re-centred on the fruit's measured position below, so a couple
                # of centimetres of arrival error are harmless.
                if abs(float(self.spawner.velocity(sample)[1])) < 0.01:
                    settled += 1
                else:
                    settled = 0
                if settled >= 30 or step > 900:
                    # The fruit is seated on the pick nest by hand-off afterwards,
                    # so the arrival test only has to confirm it reached the pick
                    # station: the belt's stop takes effect over a few centimetres
                    # and fruit routinely coast to rest 5-20 cm short.
                    arrived = -0.05 <= dy <= float(
                        os.environ.get("FRUIT_ARRIVE_TOL", "0.30")
                    )
                    if verbose:
                        say(
                            f"[task]   indexed: fruit_y={float(pos[1]):.4f} "
                            f"dy={dy * 1000:+.1f}mm arrived={arrived}"
                        )
                    break
            elif dy <= self.CLOSE_TOLERANCE:
                arrived = True
                break
            if float(pos[2]) < self.belt_top - 0.05:
                break
            self.spawner.enforce_transport()
            arm.robot.set_dof_position_targets([grasp_config], dof_indices=arm.arm_dofs)
            self._step_sim(1)
            self._record(self._action9(grasp_config, arm))
            # Refresh the camera every 4 physics steps (30 Hz, matching the
            # dataset decimation). `RenderingManager.render()` renders without
            # advancing physics, unlike `update_app`, so the control loop keeps
            # its exact 1/120 s timing.
            if step % 4 == 0:
                self._tick_frame()
        if verbose:
            say(f"[task] fruit at pick point: dy={dy:+.4f} m arrived={arrived} after {step} steps")
        if not arrived:
            result.notes.append(f"fruit never settled at the pick point (dy={dy:+.3f} m)")
            return result

        # Everything from here on is the contact work: seat, grasp, carry, release.
        # It lives in its own method so the hybrid evaluator can reuse exactly the
        # same primitives after the policy has driven the approach.
        return self.grasp_carry_place(arm_name, sample, bin_index, result, verbose=verbose)

    def grasp_carry_place(self, arm_name: str, sample, bin_index: int,
                          result, verbose: bool = False):
        """Seat, grasp, carry and release a fruit that is already at the pick point.

        The contact work of an episode, without the approach: the hybrid evaluator
        lets the policy drive the arm towards the fruit first and then calls this,
        so the policy and the primitives share exactly the same grasp.
        """
        belt = getattr(self.spawner, "belt", None)
        arm = self.arms[arm_name]
        # Same flag as `_run_impl`: a dynamic line keeps running while the arm
        # carries and places (see the note at the end of the lift).
        dynamic_pick = os.environ.get("FRUIT_DYNAMIC_PICK", "1") == "1"
        # Same clean start as `run()`: a leftover closed gripper from the previous
        # episode can otherwise grab a fruit off the belt on its own, which is what
        # produced the odd `handoff=False lifted=True` episodes in logs/200.
        self._closed_gap[arm_name] = None
        self._gripper_offset[arm_name] = None
        self._grip_quat[arm_name] = None
        self._grip_centre[arm_name] = None
        self.grippers[arm_name].park()
        # The block below was written inside `run()`, where this import was local.
        from isaacsim.core.simulation_manager import SimulationManager
        # Seat the fruit on the pick nest centre line, then servo the *pads* onto
        # it. The conveyor-to-nest hand-off stays a positioning step (as it always
        # was in this project); everything from here to the release is contact.
        # This is the configuration that first carried fruit by friction
        # (logs/106_mu2.log), reproduced here so the pipeline and the isolated
        # test agree.
        seat = self.belt_top + self.seat_height()
        rest = np.array(
            [self.cfg.pick_x, self.cfg.pick_y, seat + sample.diameter / 2.0]
        )
        # Hand-off. The old pipeline teleported the fruit onto the nest centre
        # before every grasp (`spawner.place` = set_world_poses + zero velocity),
        # which is a visible jump of up to ~20 cm and a velocity step the contact
        # never sees. A fruit that the (ramped, indexed) belt has already brought
        # to rest within `FRUIT_SEAT_TOL` of the pick centre is simply picked up
        # where it stands - the pads are placed on the fruit's *measured* position
        # anyway - so the default is now contact seating, with the teleport kept
        # as a logged fallback for fruit that stopped short.
        measured = np.asarray(self.spawner.position(sample), dtype=float)
        jump = float(np.linalg.norm(measured - rest))
        # Only a fruit that stopped absurdly far away, or one that is not even at
        # seat height (e.g. a raised nest with `FRUIT_NEST`), is teleported.
        hard_limit = float(os.environ.get("FRUIT_HANDOFF_MAX", "0.30"))
        teleport = (
            os.environ.get("FRUIT_HANDOFF", "contact") == "teleport"
            or jump > hard_limit
            or float(measured[2]) < seat - 0.02
        )
        if teleport:
            self.spawner.place(sample, rest)
            if verbose:
                say(
                    f"[task] seated by teleport: fruit {jump * 1000:.0f} mm from the pick "
                    f"centre (hard limit {hard_limit * 1000:.0f} mm)"
                )
        else:
            # Pick it up where it stands - a real cell does not teleport the
            # product onto a mark before grasping it.
            rest = measured.copy()
            if verbose:
                say(
                    f"[task] seated by contact: picking the fruit {jump * 1000:.0f} mm "
                    f"from the pick centre"
                )
        sample.held = True
        for _ in range(30):
            self._step_sim(1)
        # The nest ridge is only 2 cm wide (it has to be narrower than the fruit
        # so the pads can pass on both sides), and fruit roll off it during the
        # settle in ~30 % of attempts - which reads as "the pads closed through
        # the fruit with 0 N" once the fruit is lying 4.5 cm lower on the belt.
        # Re-seat it if that happened.
        for _reseat in range(int(os.environ.get("FRUIT_RESEATS", "2"))):
            if float(self.spawner.position(sample)[2]) >= rest[2] - 0.010:
                break
            self.spawner.place(sample, rest)
            for _ in range(30):
                self._step_sim(1)

        # The coherent-hand flag only exists inside the kinematic-gripper branch; the
        # robot's-own-fingers path (`FRUIT_KINEMATIC_GRIPPER=0`) needs it defined too
        # (it crashed with UnboundLocalError before this line existed, logs/423).
        coherent = False
        if self.grippers[arm_name].enabled:
            # Kinematic gripper: the pads are placed explicitly around the fruit, so
            # there is nothing to align and nothing to estimate - this is the
            # geometry that held 10/10 fruit in scripts/91_simple_gripper_test.py.
            gripper = self.grippers[arm_name]
            _, quat = arm.tcp_pose()
            quat = np.asarray(quat, dtype=float)
            # The pads are the hand: remember where they sit relative to the tool
            # point so they travel with the arm while the fruit is held.
            # Offset in the *tool frame* so it can be rotated back into the world
            # as the wrist moves during the carry.
            _pos, _quat = arm.tcp_pose()
            _rot = _quat_matrix(_quat)
            self._gripper_offset[arm_name] = _rot.T @ (
                np.asarray(self.spawner.position(sample), dtype=float)
                - np.asarray(_pos, dtype=float)
            )
            gap_open = float(os.environ.get("FRUIT_GRIPPER_OPEN", "0.09"))
            coherent = os.environ.get("FRUIT_COHERENT_HAND", "0") == "1"
            finger_len = 0.0
            if coherent:
                # Rigid hand: hold a top-down attitude and put the *palm* one finger
                # length above the fruit, so the fingertips (where the pads are
                # mounted) land on it. Measured reachable on both arms with
                # scripts/97_reach_probe.py (5.8-7.1 mm residual, tool axis down).
                # The live fingertip measurement depends on the pose it is taken in
                # (6 cm at the top-down grasp pose, 8-9 cm hanging) and reading it
                # before the IK gave 47-89 mm in the first coherent run
                # (logs/301). The probe established ~60 mm at the top-down pose, so
                # that is the default and it stays an env knob.
                finger_len = float(os.environ.get("FRUIT_FINGER_LEN", "0.060"))
                # Consistency: close on the fruit the feeder is actually presenting.
                # The task's own selection can lag the queue, and closing on a fruit
                # that is not between the fingers is a guaranteed miss
                # (`logs/316`). Opt-in through FRUIT_STATION_RESELECT so the
                # assisted default keeps the behaviour it was verified with.
                if os.environ.get("FRUIT_STATION_RESELECT", "1") == "1":
                    presented = self.station_sample()
                    if presented is not None and int(presented.index) != int(sample.index):
                        say(
                            f"[task]   reselecting: selected index {sample.index} is not at "
                            f"the station; taking index {presented.index}"
                        )
                        sample = presented
                        result.sample_index = int(presented.index)
                        result.category = presented.category
                        result.grade = presented.grade
                        bin_index = 0 if presented.grade == "A" else 1
                hold = top_down_quaternion(os.environ.get("FRUIT_HAND_AXIS", "x"))
                if arm_name == "left":
                    # The arms are mirrored, so the left arm needs the mirrored
                    # attitude: feeding both arms the right arm's quaternion makes
                    # the left solver drift to a near-horizontal tool (probe: 28 mm
                    # against 2.1 mm; scripts/97_reach_probe.py mirrors for exactly
                    # this reason). This bug was in the coherent block only.
                    hold = mirror_across_xz(hold)
                arm.hold_quaternion = hold
                # Hold the line for the whole coherent block: the servo costs up to
                # 4 x 250 physics steps (~8 s of simulated time) and a fruit on a
                # running belt moves ~0.4 m in that window - which is exactly what
                # left the pads 603 mm behind the fruit in logs/309.
                # (Touching the gate/belt here was tried and removed: stopping the
                # belt mid-feed let the queue pile up and the *selected* fruit never
                # reached the station - the grasp then ran against whatever fruit was
                # there while the pads were aimed at the target's position,
                # `|pads-fruit| = 555 mm` in logs/313.)
                pad_error = float("inf")
                residual = float("inf")
                # Track the moving fruit at the *control rate*. The old version
                # called `solve_to(iterations=250)` up to four times, and at the
                # line's 0.06 m/s the fruit travels 12 cm during one solve, so the
                # "servo" chased a stale target and diverged - measured
                # fingertip-to-fruit 167-871 mm, falling back to the assisted frame
                # every time (`logs/400`). One `ik_step` per tick with the target
                # re-read every tick is a 120 Hz tracker; the drive lag (tau 0.2 s)
                # trails it by roughly `v*tau ~ 12 mm`, which the pads' height covers.
                track_ticks = int(os.environ.get("FRUIT_COHERENT_TRACK", "180"))
                fruit = np.asarray(self.spawner.position(sample), dtype=float)
                for _tick in range(track_ticks):
                    fruit = np.asarray(self.spawner.position(sample), dtype=float)
                    arm.ik_step(
                        arm.tcp_target_for_jaw(
                            fruit + np.array([0.0, 0.0, finger_len + PAD_LIFT])
                        )
                    )
                    self._step_sim(1)
                rot_now = _quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
                # The fingers extend along the tool's +z axis (`down` in
                # follow_centre), so the fingertips are *plus* a finger length along
                # it - the first version subtracted and reported errors of 2 finger
                # lengths (logs/306).
                fingertip = np.asarray(arm.jaw_centre(), dtype=float) + rot_now @ np.array(
                    [0.0, 0.0, finger_len]
                )
                pad_error = float(np.linalg.norm(fingertip - fruit))
                residual = pad_error
                if verbose:
                    say(
                        f"[task] coherent track {track_ticks} ticks: "
                        f"fingertip-to-fruit={pad_error * 1000:.1f} mm"
                    )
                # Attitude check: the pads are mounted on the fingers, so the *tool
                # axis* matters as much as the position - if the wrist has swung away
                # from vertical the pads sweep off the fruit even with a perfect
                # position (jaw 19 cm off in y, logs/318). Drive the attitude until
                # the fingers really point down, or give up on coherent mode.
                axis_error = 0.0
                for _ in range(int(os.environ.get("FRUIT_AXIS_SERVO", "180"))):
                    rot_now = _quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
                    tool_z = rot_now @ np.array([0.0, 0.0, 1.0])
                    axis_error = 1.0 - float(np.dot(tool_z, np.array([0.0, 0.0, -1.0])))
                    if axis_error <= float(os.environ.get("FRUIT_AXIS_TOL", "0.01")):
                        break
                    arm.ik_step(
                        arm.tcp_target_for_jaw(
                            np.asarray(self.spawner.position(sample), dtype=float)
                            + np.array([0.0, 0.0, finger_len + PAD_LIFT])
                        )
                    )
                    self._step_sim(1)
                if verbose:
                    say(
                        f"[task] coherent axis: 1-cos={axis_error:.4f} "
                        f"({'ok' if axis_error <= float(os.environ.get('FRUIT_AXIS_TOL', '0.01')) else 'FAILED'})"
                    )
                if axis_error > float(os.environ.get("FRUIT_AXIS_TOL", "0.01")):
                    coherent = False
                    self._coherent[arm_name] = False
                if pad_error > float(os.environ.get("FRUIT_COHERENT_FALLBACK", "0.020")):
                    # The real fingertips cannot be brought onto the fruit for this
                    # attempt: keep the pipeline reliable and use the assisted pad
                    # frame instead (logged, so the rate is visible in the stats).
                    coherent = False
                    self._coherent[arm_name] = False
                    if verbose:
                        say(
                            f"[task] coherent hand fell back to the assisted frame "
                            f"(fingertip error {pad_error * 1000:.0f} mm)"
                        )
                else:
                    self._coherent[arm_name] = True
                if not coherent:
                    # Assisted frame: the pads are placed on the fruit's measured
                    # centre, and the *arm* is commanded so its jaw centre lands at
                    # the hand's wrist (one `wrist_back` behind the pads along the
                    # tool axis) instead of at whatever standoff the grip happened
                    # to have. That standoff was 5-14 cm - the "floating hand" - so
                    # this is what makes the arm visibly hold the hand that holds
                    # the fruit. The jaw target is `fruit + wrist_back` = belt_top +
                    # ~0.08, inside the measured reachable band (2.1 mm at
                    # belt_top+0.095, scripts/97_reach_probe.py).
                    self._gripper_offset[arm_name] = np.array(
                        [0.0, 0.0, float(getattr(self.grippers[arm_name], "wrist_back", 0.06))]
                    )
                _, quat = arm.tcp_pose()
                quat = np.asarray(quat, dtype=float)
            settle_ticks = int(os.environ.get("FRUIT_COHERENT_SETTLE", "60")) if coherent else 60
            for _ in range(settle_ticks):
                centre = self.spawner.position(sample)
                if coherent:
                    # Rigid: the pads sit a finger length down the tool axis from
                    # the wrist, exactly where the real fingertips are.
                    rot_now = _quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
                    centre = np.asarray(arm.jaw_centre(), dtype=float) + rot_now @ np.array(
                        [0.0, 0.0, finger_len]
                    )
                gripper.follow_centre(centre, quat, gap_open)
                self._step_sim(1)
            # What the pads close *on* is the fruit's width along the closing axis,
            # which is its nominal diameter only for a sphere. A strawberry's radial
            # extent is 79-94 % of its nominal diameter and a lychee's is exactly
            # 100 %, so `d * 0.98` leaves the pads several millimetres apart on a
            # strawberry - no contact at all, which is what the closure diagnostic
            # measured (negative interference on every failing strawberry, positive
            # on every lychee; WORKLOG "closure geometry").
            #
            # Default **on**. The grasp evidence is settled with matched
            # instrumentation (three runs of twelve small-fruit episodes per arm, same
            # seed, closure diagnostic on for both arms, `logs/policy_ab_extent5`): the
            # arms separate - strawberry 20 % [20 %, 60 %] against 100 % - and the
            # closure records say why. Every strawberry closed with *negative*
            # interference under the nominal rule (median -7.10 mm, 15/15) and positive
            # under the measured-extent rule (median +0.20 mm), while the lychee is
            # unchanged in both because a sphere's extent is its diameter. Negative
            # interference means the pads never touch the fruit, so the nominal rule was
            # not a weaker grasp on small fruit, it was *no* physical grasp on small
            # fruit - the fruit was carried by the hand's placement, not by friction.
            #
            # The scripted line's motion gate used to block this. With the flag on, two
            # bit-identical acceptance runs (`logs/142_accept_extent_default_1/2`) score
            # 10/10 and reproduce exactly, but three descents exceeded the gate's
            # 2.0 m/s^2 `a_win5` budget (worst 2.740; `|v|max` 0.0600, at the 0.06 m/s
            # reference). The gate was wrong, not the flag: 2.0 m/s^2 is `mu_eff * g`,
            # the acceleration pad friction can transmit *while carrying a payload*, and
            # a descent carries nothing. `scripts/105_motion_regression.py` now judges
            # the two legs by two budgets - descent on the commanded speed and a
            # single-tick lurch bound, carry on the friction cone - and keeps the old
            # number as a non-blocking roughness warning, so the descent difference is
            # still visible (3 warnings on the extent-close run, 0 on the nominal one).
            # Both configurations pass the re-derived gate, so the flag is decided on
            # the grasp, which is what it governs.
            #
            # Open item, deliberately not papered over: the descent does carry brief
            # ~2-7 m/s^2 blips (a_med ~0.05, so the body of the motion is smooth). They
            # are an unlocated end-of-leg transient, they are present with the flag off
            # too (1.800), and they are now reported rather than gated. Fixing them is
            # the remaining smoothness work.
            pinch_width = float(sample.diameter)
            if os.environ.get("FRUIT_CLOSE_ON_EXTENT", "1") == "1":
                pinch_width = self.pinch_width(sample, quat)
            grip_gap = pinch_width * float(
                os.environ.get("FRUIT_GRIPPER_SQUEEZE", "0.98")
            )
            # A real gripper is commanded an *interference*, not a fraction of the
            # part: `d * 0.98` leaves a 4 cm fruit only 0.4 mm of interference,
            # which PhysX does not reliably turn into a contact, and small /
            # non-spherical fruit (3.4 cm strawberries) then read 0 N and slide
            # straight out (logs/245: 2/3 attempts). Subtracting an absolute
            # preload makes the interference scale with the gripper, not the fruit.
            # Default 0: an absolute preload was tested on the worst case (3.4 cm
            # strawberries) and changed nothing (logs/247 vs 248, both 3/4 with the
            # same placement miss), so it stays an opt-in knob rather than a new
            # unverified default.
            grip_gap -= float(os.environ.get("FRUIT_GRIPPER_PRELOAD", "0.0"))
            # Absolute interference floor and a slower close for small fruit. Both
            # are opt-in until measured: the closed-loop failures now concentrate in
            # fruit below ~4.5 cm, where `d * 0.98` is only 0.3 mm of interference
            # per side (barely a contact) and the 1 s close can bat the fruit off the
            # nest before the pads are loaded.
            min_interference = float(os.environ.get("FRUIT_MIN_INTERFERENCE", "0.0"))
            if min_interference > 0.0:
                grip_gap = min(grip_gap, float(sample.diameter) - 2.0 * min_interference)
            close_steps = 60
            if float(sample.diameter) < float(os.environ.get("FRUIT_SMALL_D", "0.045")):
                close_steps += int(os.environ.get("FRUIT_SMALL_CLOSE_STEPS", "0"))
            # Quintic jaw blend: the pads arrive at the fruit with zero velocity
            # instead of the constant closing speed the linear ramp produced.
            #
            # The commanded close places the physical pad faces `PAD_THICK` (6 mm)
            # inside the commanded span (see `_release_relax_gap`), so a fruit
            # seated a couple of millimetres off the nest centre is squeezed
            # sideways while the pads chase it; about one attempt in ten is shoved
            # off the pick station entirely, the pads follow it across the cell,
            # and the attempt ends with the fruit on the floor (`logs/416`
            # attempt 7, `logs/460` attempt 2, `logs/469` attempt 2). Detect that
            # and close once more; a second drift aborts the attempt cleanly
            # instead of dragging the fruit away. Normal attempts execute the ramp
            # once and pay only one fruit-pose read.
            #
            # **The drift is measured across the belt, not along it.** The v2
            # cells pinned the fruit at the station (the pick stop, then the
            # pop-up plate), so an absolute distance to the seat point worked. On
            # the v3 dynamic line the belt keeps carrying the fruit while the pads
            # close - 0.06 m/s is 60 mm over one close ramp - and an absolute
            # check reads that transport as a lost grip: it fired on 4 of 10
            # attempts and aborted 3 of them (`logs/425`). Only the cross-belt
            # (X/Z) displacement says the payload left the hand.
            close_attempts = max(1, int(os.environ.get("FRUIT_CLOSE_ATTEMPTS", "2")))
            drift_max = float(os.environ.get("FRUIT_CLOSE_DRIFT_MAX", "0.06"))
            for _close_attempt in range(close_attempts):
                for gap in min_jerk_ramp(gap_open, grip_gap, close_steps):
                    centre = np.asarray(self.spawner.position(sample), dtype=float)
                    # Close on the fruit's *measured* centre, which is what a real
                    # controller does. Placing the pads on the fingertip estimate
                    # instead - good to only ~5 mm - makes the closing asymmetric and
                    # squeezes the fruit out backwards (the target moved 11 cm upstream
                    # during the close, logs/314). The hand stays rigid because the pads
                    # are mounted on the fingers; only the command is referenced to the
                    # fruit, and the wrist attitude still comes from the arm.
                    if coherent:
                        # Keep the IK alive: leaving the arm uncommanded for the ~400
                        # ticks of closing and settling let the wrist swing away from
                        # the solved top-down attitude (the jaw ended 19 cm from the
                        # fruit in y, logs/318).
                        arm.ik_step(
                            arm.tcp_target_for_jaw(centre + np.array([0.0, 0.0, finger_len + PAD_LIFT]))
                        )
                        close_quat = np.asarray(arm.tcp_pose()[1], dtype=float)
                    else:
                        close_quat = quat
                    gripper.follow_centre(centre, close_quat, float(gap))
                    self._step_sim(2)
                    self._record(
                        self._action9(
                            arm.joint_positions(), arm, arm.gripper_value_for_separation(float(gap))
                        )
                    )
                delta = np.asarray(self.spawner.position(sample), dtype=float) - np.asarray(
                    rest, dtype=float
                )
                if dynamic_pick:
                    delta = delta * np.array([1.0, 0.0, 1.0])
                drift = float(np.linalg.norm(delta))
                if drift <= drift_max:
                    break
                if _close_attempt + 1 >= close_attempts:
                    say(
                        f"[task]   close: fruit left the pick station ({drift * 1000:.0f} mm "
                        "cross-belt); aborting the attempt instead of chasing it"
                    )
                    result.notes.append(
                        f"fruit left the pick station during the close ({drift * 1000:.0f} mm)"
                    )
                    # Let go so the next attempt starts from a clean hand.
                    for value in min_jerk_ramp(grip_gap, gap_open, 20):
                        gripper.follow_centre(
                            np.asarray(self.spawner.position(sample), dtype=float),
                            quat,
                            float(value),
                        )
                        self._step_sim(2)
                    self._closed_gap[arm_name] = None
                    return result
                say(
                    f"[task]   close: fruit drifted {drift * 1000:.0f} mm off the pick "
                    "centre (cross-belt); re-closing on it where it is"
                )
                for value in min_jerk_ramp(grip_gap, gap_open, 20):
                    gripper.follow_centre(
                        np.asarray(self.spawner.position(sample), dtype=float), quat, float(value)
                    )
                    self._step_sim(2)
                # Re-anchor on where the fruit actually is now instead of
                # teleporting it back to the old seat point: on a moving line that
                # teleport is a hand-off a real cell does not have.
                rest = np.asarray(self.spawner.position(sample), dtype=float).copy()
                for _ in range(30):
                    self._step_sim(1)
            self._closed_gap[arm_name] = grip_gap
            if coherent and os.environ.get("FRUIT_COHERENT_DEBUG") == "1":
                say(
                    f"[task]   coherent debug(close): sample_index={sample.index} "
                    f"active={[(s.index, round(float(self.spawner.position(s)[0]), 3)) for s in self.spawner.active]} "
                    f"fruit="
                    f"{np.round(np.asarray(self.spawner.position(sample)), 4).tolist()} "
                    f"jaw={np.round(np.asarray(arm.jaw_centre()), 4).tolist()} "
                    f"pads={np.round(np.asarray(gripper.pad_centre()), 4).tolist()} "
                    f"|pads-fruit|="
                    f"{np.linalg.norm(np.asarray(gripper.pad_centre()) - np.asarray(self.spawner.position(sample))) * 1000:.1f}mm "
                    f"gap={grip_gap * 1000:.1f}mm quat={np.round(quat, 3).tolist()}"
                )
            # Freeze the hand frame now: the pads are a rigid tool from here on,
            # so they keep this centre and orientation for the whole carry and
            # the fruit is held by friction alone.
            self._grip_quat[arm_name] = np.asarray(quat, dtype=float).copy()
            self._grip_centre[arm_name] = np.asarray(
                self.spawner.position(sample), dtype=float
            ).copy()
            if os.environ.get("FRUIT_GRIPPER_DEBUG") == "1":
                say(
                    f"[task]   grip debug: tcp={np.round(arm.tcp_position(), 4).tolist()} "
                    f"fruit={np.round(self.spawner.position(sample), 4).tolist()} "
                    f"pads={gripper.summary()}"
                )
            for _ in range(60):
                self._hold_with_gripper(arm_name, sample)
                self._step_sim(1)
            if verbose:
                say(
                    f"[task] kinematic grip closed to {grip_gap * 100:.2f}cm "
                    f"around a {sample.diameter * 100:.2f}cm fruit"
                )
        # Aim at where the fruit actually is (it rolls a few millimetres on the
        # nest), not the nominal nest centre - otherwise the pads close on air.
        # Aim at the nominal nest centre. Following the fruit's measured position
        # proved worse in practice: the extra millimetres of correction push the
        # pick pose out of reach and the IK diverges (logs/137). The seating check
        # above keeps the fruit within 12 mm of this point instead.
        # With contact seating the fruit can be a few centimetres off the nominal
        # centre, so aim the arm (and the alignment diagnostic) at where it
        # actually rests; the pads are placed on the measured fruit either way.
        # Aim the *arm* at the reachable pick height, not at the fruit's equator.
        # The fruit's equator is below the arm's band at this station, but
        # the band's edge is where the servo strains (descents ended 4-27 mm short
        # with |v|max 0.089 against the 0.06 reference, logs/410); the pads are
        # placed on the fruit by the kinematic gripper, so the arm's own target can
        # be the comfortable height. The fingers still pass beside the 5 cm plate.
        free = np.array(
            [float(rest[0]), float(rest[1]), self.belt_top + self.cfg.grasp_clearance]
        )
        # The pads are placed on the fruit by the kinematic gripper, so the arm's
        # goal is simply the comfortable pick height. The old pad-forward /
        # band-centre subtraction pushed it 2.6 cm *higher* (1.29 instead of 1.265),
        # which is where the IK started wandering (hand_gap 1.37 m, logs/412); those
        # offsets only mean something for the coherent hand, which computes its own
        # fingertip target further down. They are still needed by the alignment
        # diagnostic below, which asks where the *pads* are.
        approach = arm.approach_axis()
        pad_forward = float(os.environ.get("FRUIT_PAD_FORWARD", "0.010"))
        band_centre = (
            float(os.environ.get("FRUIT_PAD_LO", "-0.045"))
            + float(os.environ.get("FRUIT_PAD_HI", "0.012"))
        ) / 2.0
        grasp_goal = free.copy()
        # Closed-loop alignment: solve, measure where the *pads* ended up, correct
        # the goal and solve again. The IK residual alone is a few millimetres, but
        # the pads sit ~1 cm along the approach axis and the fruit has to be
        # between them - a 1 cm lateral error is the difference between a pinch
        # and closing on air, which is what half the failures in logs/114 were.
        aligned = False
        alignment = (0.0, 0.0, 0.0)
        if coherent:
            # The legacy alignment block aims the OpenArm's *own* pad prims at the
            # fruit and re-solves the pose - in coherent mode the pads are mounted
            # on those fingertips, so it would undo the top-down attitude the hand
            # depends on. Skip it and keep the pose the coherent solve produced.
            aligned = True
        # Approach the fruit with smaller IK steps: a coarse step sweeps the pads
        # sideways into the fruit and knocks it off the 2 cm nest ridge (the
        # small-fruit probe went from 0/8 to 2/8 with this alone, logs/140 vs /141).
        previous_max_step = arm.max_step
        # The IK integrator is still holding the *commanded* pose from the
        # pre-pose solve, which the drives were lagging when the solve stopped;
        # the first hover `ik_step` then commands a 0.22 rad single-tick step on
        # j4 while the arm itself moves 0.009 rad (the worst commanded step the
        # posture probe sees, A2/A4 left `grasp_prepare`, logs/428). Re-anchor
        # the integrator on the measured arm before the contact work starts: the
        # arm is where it is, and every command should be a step away from that.
        arm.sync_command_to_measured()
        # Approach. Three modes, selectable with FRUIT_APPROACH_MODE, all
        # instrumented the same way so the *achieved* TCP motion can be compared:
        #   move_to   - the historic IK chase (arm.move_to)
        #   cartesian - a jerk-limited Cartesian reference tracked by the IK
        #   joint     - solve the approach pose once, then blend the *joints* with a
        #               minimum-jerk ramp (no IK in the loop, so the drives track a
        #               smooth joint reference instead of chasing a Cartesian point)
        hover = free.copy()
        hover[2] += float(os.environ.get("FRUIT_HOVER", "0.06"))
        if hover[2] > free[2]:
            # 0.04 rad/tick, not 0.20: the hover is commanded by an IK step per
            # tick, and the old cap let the first step alone move a joint 0.20 rad
            # - the worst commanded step the posture probe reports (0.2004 on j7,
            # A0 right `grasp_prepare`, logs/610; the baseline had 0.2156 on j4).
            # It is also the first tick after the pre-pose leg, and the leg
            # boundary check allows only 0.05 rad. The hover is 6 cm, so the
            # lower cap costs a handful of ticks.
            arm.max_step = float(os.environ.get("FRUIT_HOVER_STEP", "0.04"))
            arm.move_to(arm.tcp_target_for_jaw(hover), max_steps=500, tolerance=0.008)
        if os.environ.get("FRUIT_APPROACH_SETTLE", "1") == "1":
            # Start the descent from a stationary hand. `move_to` returns the tick
            # the position error is inside tolerance, which leaves the arm still
            # moving; the descent then inherits the previous leg's deceleration as
            # an acceleration spike in its first ticks (measured: the peak sits at
            # 3 % of the leg, logs/418).
            ticks, speed = self._settle_to_rest(arm)
            if verbose:
                say(
                    f"[task] approach settle: {ticks} ticks to |v|<"
                    f"{os.environ.get('FRUIT_SETTLE_EPS', '0.002')} m/s "
                    f"(|v|={speed:.4f} m/s)"
                )
        arm.max_step = float(os.environ.get("FRUIT_APPROACH_STEP", "0.08"))
        self._approach(arm, free, verbose=verbose)

        # Off by default: seeding from the cached configuration removed the IK
        # divergences but did not improve the measured rate (logs/135 vs /134), so
        # it stays behind a flag until a larger sample says otherwise.
        cached = (
            self._grasp_cache.get(arm_name)
            if os.environ.get("FRUIT_GRASP_CACHE", "0") == "1"
            else None
        )
        if cached is not None:
            arm.teleport_joints(cached)
            for _ in range(30):
                self._step_sim(1)
        for _ in range(3):
            residual = arm.solve_to(grasp_goal, iterations=300, tolerance=0.004)[1]
            axis = arm.jaw_axis()
            # Use the real pad prims when they exist (see fruit_sorting.grasp):
            # their world offset rotates with the wrist, so the closed-form
            # estimate is only valid at the pose they were calibrated at.
            pad_mid_point = pads_mid(
                self.scene.stage, arm_name, arm, pad_forward, band_centre
            )
            error = free - pad_mid_point
            lateral = float(error @ axis)
            forward = float(error @ arm.approach_axis())
            vertical = float(error[2])
            alignment = (lateral, forward, vertical)
            if abs(lateral) < 0.008 and abs(forward) < 0.020 and -0.015 < vertical < 0.020:
                aligned = True
                break
            grasp_goal = np.asarray(grasp_goal, dtype=float) + axis * lateral + arm.approach_axis() * forward
        grasp_config = arm.joint_positions()
        arm.max_step = previous_max_step
        if not aligned and not self.grippers[arm_name].enabled:
            # Closing now would pinch air. Report the attempt as a failure so the
            # caller re-runs the hand-off instead of recording a broken episode.
            result.notes.append(
                f"pads not aligned on the fruit (residual={residual * 1000:.0f}mm, "
                f"lateral={alignment[0] * 1000:+.0f}mm, forward={alignment[1] * 1000:+.0f}mm)"
            )
            if belt is not None:
                belt.start()
            return result
        if verbose:
            hand_tail = ""
            if self.grippers[arm_name].enabled:
                # How far the commanded pads sit from the arm's own jaws: the
                # gripper is kinematic, so this is a measure of how detached the
                # "hand" is from the wrist the IK is driving.
                hand_gap = float(
                    np.linalg.norm(
                        np.asarray(self.grippers[arm_name].pad_centre(), dtype=float)
                        - np.asarray(arm.jaw_centre(), dtype=float)
                    )
                )
                hand_tail = f" hand_gap={hand_gap * 1000:.0f}mm"
                if os.environ.get("FRUIT_ACTUATED_DEBUG") == "1":
                    pads = np.asarray(self.grippers[arm_name].pad_centre(), dtype=float)
                    fr = np.asarray(self.spawner.position(sample), dtype=float)
                    hand_tail += (
                        f" pads={np.round(pads, 4).tolist()} fruit={np.round(fr, 4).tolist()}"
                        f" |pads-fruit|={np.linalg.norm(pads - fr) * 1000:.0f}mm"
                        f" tcp={np.round(np.asarray(arm.tcp_position(), dtype=float), 4).tolist()}"
                    )
            say(
                f"[task] pads aimed at {np.round(free, 4).tolist()} "
                f"(fruit on nest at {np.round(rest, 4).tolist()}): "
                f"jaw={np.round(arm.jaw_centre(), 4).tolist()} residual={residual * 1000:.1f}mm "
                f"align=({alignment[0] * 1000:+.1f},{alignment[1] * 1000:+.1f},"
                f"{alignment[2] * 1000:+.1f})mm aligned={aligned}{hand_tail}"
            )

        sample.held = True
        self.spawner.stop(sample)
        # No teleporting from here on: the fruit stays where the belt left it and
        # the jaws do the work, so the grasp is pure contact.
        for _ in range(30):
            arm.robot.set_dof_position_targets([grasp_config], dof_indices=arm.arm_dofs)
            self._step_sim(1)
            self._record(self._action9(grasp_config, arm))

        # Force-limited close. Two stop conditions, because the tactile sensor in
        # this build reads 0 N through real contact as often as it reads hundreds:
        #   1. the finger joints stop following the command (`jaw_separation`
        #      stays above what the command asks for) - the pads are loaded;
        #   2. the tactile force reaches the budget (100x the fruit's weight).
        # This configuration is the one that first carried fruit by contact
        # (logs/106_mu2.log: 6/10, see WORKLOG).
        squeeze = float(os.environ.get("FRUIT_SQUEEZE", "0.90"))
        block_stop = float(os.environ.get("FRUIT_BLOCK_STOP", "0.030"))
        force_limit = float(
            np.clip(sample.mass * 9.81 * float(os.environ.get("FRUIT_FORCE_FACTOR", "100")),
                    25.0, 60.0)
        )
        fingers = arm.gripper_value_for_separation(sample.diameter * squeeze)
        value = arm.OPEN
        over_force = 0
        for value in min_jerk_ramp(arm.OPEN, fingers, 90):
            arm.set_gripper(float(value))
            self._step_sim(2)
            expected = arm.JAW_SEPARATION_OFFSET + 2.0 * float(value)
            blocked = (arm.jaw_separation() - expected) > block_stop
            reading = self.tactile.read()[arm_name].normal_force
            # The sensor throws isolated spikes (a 10 g fruit has read 21 N with
            # the jaws wide open), so require three consecutive samples.
            over_force = over_force + 1 if reading >= force_limit else 0
            self._tick_frame()
            self._record(self._action9(grasp_config, arm, float(value)))
            if blocked or over_force >= 3:
                break
        fingers = float(value)
        # The first close stops at the first sign of the joints being blocked,
        # which leaves the fruit only lightly loaded (5-14 N in logs/114-117) and
        # it slips as soon as the arm lifts. Load the grip properly: keep closing
        # in 1 mm steps until the pads reach 60x the fruit's weight (20-40 N) or
        # the reading stops rising (no contact / saturated).
        target_force = float(
            np.clip(sample.mass * 9.81 * 60.0, 20.0, 40.0)
        )
        # Require the pads to actually reach the fruit's diameter before accepting
        # a stalled force reading: stopping early left 8-9 N grips that slipped
        # (logs/146, right arm - both pads within 2 mm of the fruit, still dropped).
        gap_target = sample.diameter - 0.002
        pad_radius = float(os.environ.get("FRUIT_PAD_RADIUS", "0.010"))
        reading = self.tactile.read()[arm_name].normal_force
        for _load in range(40):
            if reading >= target_force or fingers <= 0.0:
                break
            previous = reading
            fingers = max(0.0, fingers - 0.001)
            arm.set_gripper(fingers)
            for _ in range(6):
                self._step_sim(1)
            reading = self.tactile.read()[arm_name].normal_force
            self._record(self._action9(grasp_config, arm, float(fingers)))
            closed_enough = (arm.jaw_separation() - 2.0 * pad_radius) <= gap_target
            if (
                _load > 10
                and closed_enough
                and abs(reading - previous) < 0.5
                and reading < 2.0
            ):
                break  # nothing between the pads
        # Let the contact settle; the fruit is free the whole time, so the solver
        # builds a real static-friction constraint.
        for _ in range(60):
            self._step_sim(1)
            self._record(self._action9(grasp_config, arm, float(fingers)))

        # Grasp model. With the kinematic gripper (the default) the fruit is held
        # by real contact, so attachment is off unless it is asked for explicitly.
        # `FRUIT_ATTACH=1` restores the old modelled carry for the legacy pipeline.
        default_attach = "0" if self.grippers[arm_name].enabled else "1"
        if os.environ.get("FRUIT_ATTACH", default_attach) == "1" and (
            os.environ.get("FRUIT_NO_ATTACH", "0") != "1"
        ):
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
        if os.environ.get("FRUIT_CLOSURE_DEBUG", "0") in ("1", "2"):
            # The grasp-time numbers in the log (`|pads-fruit|`, `hand_gap`,
            # alignment) all describe *where the pads were commanded*; none of them
            # says what the grip closed on. Fifty small-fruit episodes left the
            # strawberry's 38 % unexplained by any of them (WORKLOG), so this
            # records the geometry at the moment the fingers stop: the separation
            # between the pad faces, the fruit's own extent along that axis, and
            # how far the fruit sits off the mid-point and along the fingers.
            say(f"[task] closure: {self.closure_record(arm_name, sample)}")

        # 3. Lift and verify the fruit came along.
        z_before = float(self.spawner.position(sample)[2])
        self._recentre_gripper(arm_name, sample)
        # Same re-anchor as before the hover: the close ran with no IK command
        # (assisted frame), so the integrator is still at the approach's last
        # command and the first test-lift step would otherwise jump.
        arm.sync_command_to_measured()
        # Slip compensation: verify the grip with a 1 cm test lift and, if the
        # fruit did not follow, squeeze harder and try again (the design calls for
        # slip detection with a regrasp). A fruit that slips usually sits too
        # low between the pads, which the firmer squeeze corrects.
        for _regrasp in range(int(os.environ.get("FRUIT_REGRASPS", "3"))):
            probe = grasp_goal + np.array([0.0, 0.0, 0.010])
            for _ in range(40):
                arm.ik_step(arm.tcp_target_for_jaw(probe))
                self._step_sim(1)
            if float(self.spawner.position(sample)[2]) - z_before > 0.004:
                for _ in range(40):
                    arm.ik_step(arm.tcp_target_for_jaw(grasp_goal))
                    self._step_sim(1)
                break
            for _ in range(40):
                arm.ik_step(arm.tcp_target_for_jaw(grasp_goal))
                self._step_sim(1)
            # Squeeze 3 mm harder each time: the first close often stops at the
            # first sign of the joints being blocked, which leaves the fruit only
            # lightly loaded (5-14 N) - enough to feel, not enough to carry.
            if (
                _regrasp == int(os.environ.get("FRUIT_REGRASPS", "3")) - 1
                and os.environ.get("FRUIT_REGRASP_REOPEN", "0") == "1"
            ):
                # Last-resort recovery: a full re-grasp. Squeezing harder does not
                # restore a lost grip in this model (measured), but opening the pads,
                # re-seating them on the fruit's *current* measured position and
                # closing again can - and it is what a real cell does before it
                # gives up on the product.
                # Default OFF: measured worse than the plain third squeeze
                # (5/8 vs 7/8 on the small-fruit set, logs/342) because opening the
                # pads disturbs grips that were already holding.
                gap_open_now = float(os.environ.get("FRUIT_GRIPPER_OPEN", "0.09"))
                quat_now = np.asarray(arm.tcp_pose()[1], dtype=float)
                for _ in range(30):
                    self.grippers[arm_name].follow_centre(
                        np.asarray(self.spawner.position(sample), dtype=float),
                        quat_now,
                        gap_open_now,
                    )
                    self._step_sim(1)
                for gap in min_jerk_ramp(gap_open_now, grip_gap, 45):
                    self.grippers[arm_name].follow_centre(
                        np.asarray(self.spawner.position(sample), dtype=float),
                        quat_now,
                        float(gap),
                    )
                    self._step_sim(2)
                if verbose:
                    say("[task]   recovery: re-grasped (open, re-seat, close)")
            fingers = float(fingers) - float(os.environ.get("FRUIT_REGRASP_STEP", "0.003"))
            for _ in range(60):
                arm.set_gripper(fingers)
                self._step_sim(1)
        z_before = float(self.spawner.position(sample)[2])
        if os.environ.get("FRUIT_LIFT_DEBUG") == "1":
            say(f"[task]   lift start: fruit_z={z_before:.4f} jaw_z={arm.jaw_centre()[2]:.4f} "
                f"grip={arm.finger_opening():.4f}")
        self._carry(arm_name, sample, "grasp_lift")
        if os.environ.get("FRUIT_GRIPPER_DEBUG") == "1":
            say(
                f"[task]   lift debug: tcp_z={arm.tcp_position()[2]:.4f} "
                f"fruit_z={float(self.spawner.position(sample)[2]):.4f} "
                f"pads={self.grippers[arm_name].summary()}"
            )
        if os.environ.get("FRUIT_LIFT_DEBUG") == "1":
            say(f"[task]   lift end:   fruit_z={float(self.spawner.position(sample)[2]):.4f} "
                f"jaw_z={arm.jaw_centre()[2]:.4f} grip={arm.finger_opening():.4f}")
        z_after = float(self.spawner.position(sample)[2])
        result.peak_lift = z_after - z_before
        result.grasped = z_after - z_before > 0.05
        if result.grasped:
            # Remember the configuration that worked: it is the best seed for the
            # next episode on this arm.
            self._grasp_cache[arm_name] = np.asarray(grasp_config, dtype=float).copy()
        for _ in range(20):
            result.max_tactile_force = max(
                result.max_tactile_force, self.tactile.read()[arm_name].normal_force
            )
            app_utils.update_app(steps=1)
        # Indexed line: hold the queue (gate closed, belt stopped) while the arm
        # carries and places, then re-open and re-start for the next attempt. A
        # *dynamic* line never stops - the rest of the fruit keep travelling and the
        # ones that are not taken simply pass the station.
        if belt is not None and not dynamic_pick:
            belt.stop()
        if verbose:
            say(f"[task] lift {result.peak_lift:+.4f} m, grasped={result.grasped}")
        if not result.grasped:
            result.notes.append("fruit did not follow the gripper")
            return result

        # 4. Carry to the output line and release. Each arm only serves the
        # conveyor on its own side (crossing the body is outside the workspace),
        # so the lane index decides which arm picks.
        self._carry(arm_name, sample, f"place{bin_index}")
        if verbose:
            jaw = arm.jaw_centre()
            fr = self.spawner.position(sample)
            px, py = self.cfg.output_belt_drop_points[bin_index]
            say(
                f"[task]   over the output belt: jaw={np.round(jaw, 3).tolist()} "
                f"fruit={np.round(fr, 3).tolist()} target=({px:.2f},{py:+.2f}) "
                f"top={self.cfg.output_belt_top_z:.2f}"
            )
        self.spawner.detach(sample)
        sample.held = False
        if self.grippers[arm_name].enabled and self._closed_gap.get(arm_name) is not None:
            # Open the kinematic jaws or the fruit stays gripped and is dragged
            # straight back off the line with the arm (logs/175: 5/8 grasped,
            # 0/8 placed because this step was missing).
            gripper = self.grippers[arm_name]
            gap = float(self._closed_gap[arm_name] or 0.0)
            # Release from the frozen hand frame: the pads are already sitting at
            # the fruit, so opening them about `_grip_centre` just lets go.
            quat = self._grip_quat.get(arm_name)
            centre = self._grip_centre.get(arm_name)
            if quat is None or centre is None:
                _, quat = arm.tcp_pose()
                quat = np.asarray(quat, dtype=float)
                offset = self._gripper_offset.get(arm_name)
                rot = _quat_matrix(quat)
                centre = np.asarray(arm.tcp_position(), dtype=float)
                if offset is not None:
                    centre = centre + rot @ offset
            centre = np.asarray(centre, dtype=float)
            quat = np.asarray(quat, dtype=float)
            # Open *past the fruit*, not by a fixed amount. `follow_centre`'s gap is
            # the pad-prim span and the inner faces sit `PAD_THICK` closer, so
            # `closed_gap + 0.10` (6.64 cm for a 6.7 cm peach) still clamped it and
            # the arm dragged the fruit out of the bin (logs/369; a raised output
            # belt has no rim, but the same clamping dragged fruit off it). The target
            # clears the fruit's diameter with margin, and the ramp is slow so the
            # let-go does not flick the payload.
            release_gap = max(gap + 0.10, float(sample.diameter) + 0.03)
            # Diagnostic only (`FRUIT_RELEASE_DEBUG=1`): the payload's velocity
            # while the pads open. It answers where the 1-in-10 ejection happens -
            # on the pad ramp, on the arm-gripper ramp or during the settle - and
            # in which world direction the payload leaves. Off by default because
            # instrumentation is part of the measurement (AGENTS.md).
            release_debug = os.environ.get("FRUIT_RELEASE_DEBUG", "0") == "1"
            trace = {"tick": 0, "vmax": 0.0, "tick_vmax": 0, "gap_vmax": 0.0,
                     "stage_vmax": "", "vel_vmax": np.zeros(3), "fruit_vmax": np.zeros(3),
                     "pads_vmax": (np.zeros(3), np.zeros(3)), "events": []}
            if release_debug:
                support_z = float(self.cfg.output_belt_top_z)
                fruit_now = np.asarray(self.spawner.position(sample), dtype=float)
                say(
                    f"[task] release: gap={gap * 1000:.1f}mm -> {release_gap * 1000:.1f}mm, "
                    f"fruit={np.round(fruit_now, 4).tolist()} bottom="
                    f"{(fruit_now[2] - self._shape_support(sample, np.array([0.0, 0.0, -1.0]))) * 1000:.0f}mm "
                    f"above the output belt top ({support_z * 1000:.0f}mm), "
                    f"pads={np.round(gripper.pad_centre(), 4).tolist()} "
                    f"pad_axis={np.round(_quat_matrix(quat)[:, 1], 3).tolist()}"
                )
            # Release ordering for the raised output line. The payload hangs
            # `output_place_clearance` (10 cm) above the belt surface, so the
            # bin-specific floor-supported ordering (lower the gripped payload to
            # first contact) is **off by default**: lowering it onto the raised
            # belt brings the OpenArm's own fingers down to the belt top. The
            # default is the literal "put it on the line" release: relax the span
            # to the first one whose physical faces clear the fruit, dwell so
            # residual motion decays, then open - the fruit drops the remaining
            # ~10 cm onto the moving surface and is carried away.
            # `FRUIT_RELEASE_SUPPORT=1` restores the set-down ordering (lower to
            # first contact with the belt, then relax/dwell/open) as an A/B; the
            # `FRUIT_RELEASE_*` knobs all still apply.
            if (
                os.environ.get("FRUIT_RELEASE_SUPPORT", "0") == "1"
                and isinstance(gripper, KinematicGripper)
            ):
                centre = self._release_lower(
                    arm_name, sample, centre, quat, gap, trace, release_debug,
                    floor=float(self.cfg.output_belt_top_z),
                )
            relax_gap = gap
            if os.environ.get("FRUIT_RELEASE_RELAX", "1") == "1":
                relax_gap = self._release_relax_gap(sample, quat, gap, release_gap)
            if relax_gap > gap + 1e-6:
                relax_steps = max(1, int(os.environ.get("FRUIT_RELEASE_RELAX_STEPS", "4")))
                if os.environ.get("FRUIT_RELEASE_ASYMMETRIC", "1") == "1":
                    # Retreat one pad first while the other stays: the stored
                    # normal force then pushes the payload along the closing
                    # axis (a shear along the belt) instead of trapping it
                    # between two retreating contacts, where it can pop out of
                    # the pad span like a seed. Probe, same pool and offsets: the
                    # symmetric fast relax threw one 2.8 cm lychee at 1.34 m/s;
                    # this keeps every trial of the series at or below 0.75 m/s
                    # (`logs/473` vs `logs/474`).
                    axis = _quat_matrix(quat)[:, 1]
                    base = np.asarray(centre, dtype=float).copy()
                    for _index, value in enumerate(min_jerk_ramp(gap, relax_gap, relax_steps)):
                        shift = (float(value) - gap) / 2.0
                        gripper.follow_centre(base + axis * shift, quat, float(value))
                        for _ in range(2):
                            self._step_sim(1)
                            if release_debug:
                                self._release_probe(
                                    arm_name, sample, trace, "relax", _index, float(value)
                                )
                    centre = base + axis * ((relax_gap - gap) / 2.0)
                else:
                    for _index, value in enumerate(min_jerk_ramp(gap, relax_gap, relax_steps)):
                        gripper.follow_centre(centre, quat, float(value))
                        for _ in range(2):
                            self._step_sim(1)
                            if release_debug:
                                self._release_probe(
                                    arm_name, sample, trace, "relax", _index, float(value)
                                )
                gap = relax_gap
            for _index in range(max(0, int(os.environ.get("FRUIT_RELEASE_DWELL", "20")))):
                gripper.follow_centre(centre, quat, gap)
                self._step_sim(1)
                if release_debug:
                    self._release_probe(arm_name, sample, trace, "dwell", _index, gap)
            for _index, value in enumerate(min_jerk_ramp(gap, release_gap, 40)):
                gripper.follow_centre(centre, quat, float(value))
                for _ in range(3):
                    self._step_sim(1)
                    if release_debug:
                        self._release_probe(arm_name, sample, trace, "pads", _index, float(value))
            self._closed_gap[arm_name] = None
            self._gripper_offset[arm_name] = None
            self._grip_quat[arm_name] = None
            self._grip_centre[arm_name] = None
        for _index, value in enumerate(min_jerk_ramp(fingers, arm.OPEN, 16)):
            arm.set_gripper(float(value))
            for _ in range(3):
                self._step_sim(1)
                if os.environ.get("FRUIT_RELEASE_DEBUG", "0") == "1":
                    self._release_probe(arm_name, sample, trace, "arm", _index, float(value))
        # Retreat. Once the pads are open the fruit is on its own, and holding
        # station for another second is what the release `settle` used to do (60
        # ticks after a 48-tick finger ramp). Lifting the hand away instead is
        # both faster and cleaner, and it is what the demo video reads as
        # "letting go". It starts only after the pad ramp, so the payload can no
        # longer be flicked. Off by default until measured on v3.
        retreat = float(os.environ.get("FRUIT_RELEASE_RETREAT", "0.0"))
        if retreat > 0.0:
            start_tcp = arm.tcp_position().copy()
            for alpha in min_jerk_ramp(0.0, 1.0, 60):
                arm.ik_step(start_tcp + np.array([0.0, 0.0, retreat * float(alpha)]))
                self._step_sim(1)
                if os.environ.get("FRUIT_RELEASE_DEBUG", "0") == "1":
                    self._release_probe(arm_name, sample, trace, "retreat", 0, float(alpha))
        else:
            for _ in range(60):
                self._step_sim(1)
                if os.environ.get("FRUIT_RELEASE_DEBUG", "0") == "1":
                    self._release_probe(arm_name, sample, trace, "settle", 0, 0.0)
        if os.environ.get("FRUIT_RELEASE_DEBUG", "0") == "1":
            self._release_report(arm_name, sample, trace)
        pos = self.spawner.position(sample)
        result.placed = bool(self.cfg.on_output_belt(pos))
        if verbose:
            say(
                f"[task] released at {np.round(pos, 3).tolist()}, placed={result.placed} "
                f"(on/next to output belt {bin_index})"
            )
        if self.recorder is not None:
            self.recorder.save(result.success, result.notes)
        self.current_sample = None
        return result

    @staticmethod
    def _quat_matrix(quat) -> np.ndarray:
        w, x, y, z = (float(v) for v in quat)
        return np.array(
            [
                [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
            ]
        )

    def _shape_support(self, sample, direction_world) -> float:
        """Distance from the fruit's origin to its extreme point along a direction [m].

        The mesh is a surface of revolution, so its support follows from the
        profile - the same math as `meshes.axis_extent`, but **one-sided**,
        because the release needs the origin-to-lowest-point distance and not the
        full chord. The half of `axis_extent` is exact only for a symmetric
        profile centred on its z mid-point; a tilted peach reaches further down
        than half its height, and using the half would leave the payload above the
        floor exactly in the tilted poses that need the support most.
        """
        from .meshes import FRUIT_SHAPES

        half = float(sample.diameter) / 2.0
        shape = FRUIT_SHAPES.get(sample.category)
        if shape is None:
            return half
        direction = np.asarray(direction_world, dtype=float)
        length = float(np.linalg.norm(direction))
        if length < 1e-9:
            return half
        direction = direction / length
        _, fruit_quat = self.spawner.fruit_pose(sample)
        local = self._quat_matrix(fruit_quat).T @ direction
        scale = half
        radial = float(np.hypot(local[0], local[1]))
        axial = float(shape.length_scale) * float(local[2])
        return float(max(r * scale * radial + z * scale * axial for (r, z) in shape.profile()))

    def _release_lower(self, arm_name, sample, centre, quat, gap, trace, debug, floor: float):
        """Lower the gripped payload until it first touches the support [m].

        The pads hold the fruit between them, so this is a command for the pad
        centre (and the arm follows it). `FRUIT_RELEASE_SINK` defaults to 0: stop
        at first contact, do not press - pressing stores floor penetration that
        the solver returns as a launch (the probe trace that buried a fruit 15 mm
        into the floor released it at 4.5 m/s, `logs/464`). Returns the new pad
        centre. The pads lead (they are kinematic and exact) and the arm follows
        them with `ik_step`, exactly as the carry does.

        `floor` is the surface below the release point: the bin floor in the v2
        layout, the output-belt top in v3. This ordering is off by default on the
        raised output line (see the release block in `grasp_carry_place`).
        """
        fruit = np.asarray(self.spawner.position(sample), dtype=float)
        half_extent = self._shape_support(sample, np.array([0.0, 0.0, -1.0]))
        sink = float(os.environ.get("FRUIT_RELEASE_SINK", "0.0"))
        drop = float(fruit[2]) - half_extent - floor + sink
        ceiling = float(os.environ.get("FRUIT_RELEASE_DROP_MAX", "0.10"))
        drop = float(np.clip(drop, 0.0, ceiling))
        base = np.asarray(centre, dtype=float).copy()
        if drop <= 1e-4:
            return base
        steps = max(4, int(os.environ.get("FRUIT_RELEASE_DROP_STEPS", "60")))
        rot = _quat_matrix(quat)
        offset_tool = self._gripper_offset.get(arm_name)
        offset_tool = None if offset_tool is None else np.asarray(offset_tool, dtype=float)
        arm = self.arms[arm_name]
        # If the pad/arm relation is already broken (the intermittent detachment
        # class, `hand_gap` 0.24-1.5 m at the pads-aimed line), do not command the
        # arm at all: a large `ik_step` transit can sweep the wrist through the
        # payload. One read per release, not per tick - per-tick link reads change
        # the run (AGENTS.md).
        follow_arm = offset_tool is not None
        if follow_arm:
            target0 = base - rot @ offset_tool
            follow_arm = bool(
                np.linalg.norm(target0 - np.asarray(arm.tcp_position(), dtype=float))
                < float(os.environ.get("FRUIT_RELEASE_ARM_TRACK", "0.20"))
            )
        centre = base
        for _index, dz in enumerate(min_jerk_ramp(0.0, drop, steps)):
            centre = base + np.array([0.0, 0.0, -float(dz)])
            placed = np.asarray(
                self.grippers[arm_name].follow_centre(centre, quat, gap), dtype=float
            )
            self._grip_centre[arm_name] = placed
            if follow_arm:
                arm.ik_step(arm.tcp_target_for_jaw(placed - rot @ offset_tool))
            self._step_sim(1)
            if debug:
                self._release_probe(arm_name, sample, trace, "lower", _index, gap)
        return centre

    def _release_relax_gap(self, sample, quat, gap, release_gap) -> float:
        """Gap that removes the commanded overlap before the faces separate [m].

        The grip carries the payload by commanding the pad faces *inside* the
        fruit, so the normal force is an artefact of that overlap. The geometry
        has one subtlety that the closure diagnostic reads 6 mm wrong:
        `follow_centre` puts each pad *prim centre* at `centre +/- gap/2` and the
        pad is `PAD_THICK` thick along the closing axis, so the **physical face
        separation is `gap - PAD_THICK`** - not `gap`. Measured on the release
        trace (`logs/460` attempt 0): the payload begins free fall when the
        commanded span is 35.5 mm, and its own width is 29.8 mm - 35.5 - 6 =
        29.5. Relaxing to `pinch_width + PAD_THICK + margin` therefore leaves the
        faces roughly `margin/2` clear of the fruit; the 6 mm default margin
        covers the measured off-centre seat (up to 2 mm in the closure records)
        as well. The payload is on the floor by then, so losing the grip early
        costs nothing.
        """
        margin = float(os.environ.get("FRUIT_RELEASE_RELAX_MARGIN", "0.006"))
        relax = max(gap, float(self.pinch_width(sample, quat)) + PAD_THICK + margin)
        return float(min(release_gap, relax))

    def _release_probe(self, side: str, sample, trace: dict, stage: str,
                       index: int, gap: float) -> None:
        """One release-trace sample: payload velocity and pad geometry [diagnostic].

        Only called with `FRUIT_RELEASE_DEBUG=1`. Reading the fruit on the release
        path does not enter the control loop (`ik_step`), so unlike the arm-link
        readback it does not change the motion it measures - but it is still
        instrumentation and stays behind a knob.
        """
        fruit = np.asarray(self.spawner.position(sample), dtype=float)
        vel = np.asarray(self.spawner.velocity(sample), dtype=float)
        speed = float(np.linalg.norm(vel))
        try:
            pad_a, pad_b = (
                np.asarray(p, dtype=float) for p in self.grippers[side].pad_faces()
            )
        except (AttributeError, TypeError):  # actuated gripper has no pad prims
            pad_a = pad_b = np.asarray(self.grippers[side].pad_centre(), dtype=float)
        trace["tick"] += 1
        if speed > trace["vmax"]:
            trace["vmax"] = speed
            trace["tick_vmax"] = trace["tick"]
            trace["gap_vmax"] = float(gap)
            trace["stage_vmax"] = stage
            trace["vel_vmax"] = vel.copy()
            trace["fruit_vmax"] = fruit.copy()
            trace["pads_vmax"] = (pad_a.copy(), pad_b.copy())
        threshold = float(os.environ.get("FRUIT_RELEASE_TRACE_THRESHOLD", "0.20"))
        if speed > threshold and len(trace["events"]) < 40:
            trace["events"].append(
                (trace["tick"], stage, index, float(gap), speed, fruit.copy(),
                 vel.copy(), pad_a.copy(), pad_b.copy())
            )

    def _release_report(self, side: str, sample, trace: dict) -> None:
        """Print the release trace summary and any threshold crossings [diagnostic]."""
        for tick, stage, index, gap, speed, fruit, vel, pad_a, pad_b in trace["events"]:
            say(
                f"[task]   release event t={tick} {stage}[{index}] gap={gap * 1000:.1f}mm "
                f"|v|={speed:.3f} m/s fruit={np.round(fruit, 4).tolist()} "
                f"vel={np.round(vel, 3).tolist()} "
                f"pads=({np.round(pad_a, 4).tolist()}|{np.round(pad_b, 4).tolist()})"
            )
        a, b = trace["pads_vmax"]
        say(
            f"[task]   release trace: {trace['tick']} ticks, peak |v|={trace['vmax']:.3f} m/s "
            f"at t={trace['tick_vmax']} ({trace['stage_vmax']}, "
            f"gap={trace['gap_vmax'] * 1000:.1f}mm) "
            f"vel={np.round(trace['vel_vmax'], 3).tolist()} "
            f"fruit={np.round(trace['fruit_vmax'], 4).tolist()} "
            f"pads=({np.round(a, 4).tolist()}|{np.round(b, 4).tolist()}) "
            f"events={len(trace['events'])}"
        )

    def pinch_width(self, sample, hand_quat) -> float:
        """The fruit's width along the closing axis the pads will use [m].

        The mesh is a surface of revolution, so its extent along any direction comes
        from the shape profile (`meshes.axis_extent`) - no mesh walk, no USD query.
        The per-instance deformation (a +/-6 % length bias and small lobing) is not
        reproduced, so this is good to a few percent, which is what a closing target
        needs.
        """
        from .meshes import FRUIT_SHAPES, axis_extent

        shape = FRUIT_SHAPES.get(sample.category)
        if shape is None:
            return float(sample.diameter)
        axis_world = self._quat_matrix(hand_quat)[:, 1]  # the pads' closing axis
        _, fruit_quat = self.spawner.fruit_pose(sample)
        local_axis = self._quat_matrix(fruit_quat).T @ axis_world
        return float(axis_extent(shape, float(sample.diameter), local_axis))

    def closure_record(self, side: str, sample) -> str:
        """Geometry of the grip at the moment the fingers stop [string].

        Reports the *faces*, not the commanded centre: the separation of the two
        pad faces along the closing axis, the fruit's own extent along that axis
        (its world bound projected on the axis, so a cone reports less than its
        nominal diameter), the fruit's offset from the pad mid-point along the
        closing axis (off-centre) and along the finger direction (too shallow or
        too deep), plus the tactile reading.
        """
        gripper = self.grippers[side]
        arm = self.arms[side]
        try:
            pad_a, pad_b = gripper.pad_faces()
        except Exception:  # noqa: BLE001 - actuated gripper has no pad prims
            return f"unavailable (gripper {type(gripper).__name__})"
        axis = pad_b - pad_a
        span = float(np.linalg.norm(axis))
        if span < 1e-9:
            return "degenerate (pads coincident)"
        axis = axis / span
        centre = (pad_a + pad_b) / 2.0
        # `follow_centre` puts each pad *prim centre* at `centre +/- axis * gap/2`,
        # so the prim-centre span is the commanded face separation.
        faces = span

        # The fruit's extent along the closing axis, from the shape profile rather
        # than from the mesh: the per-grasp USD traversal this replaced slowed the
        # loop by ~4x (and per-tick reads inside the control loop perturb the run -
        # see the WORKLOG). Only the fruit's own rotation is needed to bring the
        # axis into its local frame.
        from .meshes import FRUIT_SHAPES, axis_extent

        width = float("nan")
        debug = ""
        shape = FRUIT_SHAPES.get(sample.category)
        if shape is not None:
            locations, orientations = self.spawner.fruit_pose(sample)
            w, x, y, z = (float(v) for v in orientations)
            rotation = np.array(
                [
                    [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                    [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                    [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
                ]
            )
            width = axis_extent(shape, sample.diameter, rotation.T @ axis)
            if os.environ.get("FRUIT_CLOSURE_DEBUG") == "2":
                debug = f" fruit_at={np.round(np.asarray(locations), 3).tolist()}"

        fruit = np.asarray(self.spawner.position(sample), dtype=float)
        relative = fruit - centre
        off_axis = float(np.dot(relative, axis))
        # Along the fingers: the tool axis, i.e. the direction the jaws reach.
        reach = np.asarray(arm.tcp_position(), dtype=float) - centre
        reach = reach / max(float(np.linalg.norm(reach)), 1e-9)
        off_reach = float(np.dot(relative, reach))
        reading = self.tactile.read()[side]
        return (
            f"{sample.category} d={sample.diameter * 1000:.1f}mm "
            f"faces={faces * 1000:.1f}mm width_along_axis={width * 1000:.1f}mm "
            f"interference={(width - faces) * 1000:+.1f}mm "
            f"off_axis={off_axis * 1000:+.1f}mm off_reach={off_reach * 1000:+.1f}mm "
            f"tactile={reading.normal_force:.2f}N contacts={reading.contact_count}"
            f"{debug}"
        )

    def _arm_link_handles(self, arm, rigid_prim_cls):
        """Cached `RigidPrim` handles for one arm's links, built once per task.

        Building them per leg is measurably worse than reusing them, and reading
        them every tick perturbs the run (WORKLOG), so both the per-tick proximity
        hook and the triggered anomaly snapshot go through this cache.
        """
        side = arm.spec.side
        cache = getattr(self, "_link_handle_cache", None)
        if cache is None:
            cache = {}
            self._link_handle_cache = cache
        if side in cache:
            return cache[side]
        names = list(arm.robot.link_names)
        paths = arm.robot.link_paths
        if paths and isinstance(paths[0], (list, tuple)):
            paths = paths[0]
        handles: list[tuple[str, object]] = []
        for index, name in enumerate(names):
            if f"_{side}_" not in name:
                continue
            path = paths[index]
            if isinstance(path, (list, tuple)):
                path = path[0]
            handles.append((name, rigid_prim_cls(str(path))))
        cache[side] = handles
        return handles

    def _settle_to_rest(
        self, arm, min_ticks: int = 10, max_ticks: int = 900, eps: float | None = None
    ) -> tuple[int, float]:
        """Step until the TCP is stationary, not merely inside a position tolerance.

        Returns ``(ticks, speed)``. Used before a leg whose smoothness matters: a
        leg started on a moving arm absorbs the previous leg's deceleration, which
        shows up as an acceleration spike in its first few control ticks.
        """
        limit = float(os.environ.get("FRUIT_SETTLE_EPS", "0.002")) if eps is None else eps
        previous = np.asarray(arm.tcp_position(), dtype=float)
        calm = 0
        speed = float("inf")
        for i in range(max_ticks):
            self._step_sim(1)
            current = np.asarray(arm.tcp_position(), dtype=float)
            speed = float(np.linalg.norm(current - previous)) / CONTROL_DT
            previous = current
            if i >= min_ticks and speed < limit:
                calm += 1
                if calm >= 5:
                    return i + 1, speed
            else:
                calm = 0
        return max_ticks, speed

    def _approach(self, arm, jaw_target, verbose: bool = False) -> None:
        """Descend to the grasp pose; `FRUIT_APPROACH_MODE` picks how it is referenced."""
        # Start the differential IK from the arm's *measured* configuration. The
        # integrator keeps its own commanded joints, and anything that repositions
        # the arm without going through `ik_step` (a teleport, a joint-space move,
        # a drive that saturated at a joint limit) leaves the two far apart - the
        # descent then folds that whole difference into one command and the stiff
        # drive snaps to it. Measured: a 0.52 rad offset at the start of a left-arm
        # descent produced a 2.18 m/s, 261 m/s^2 single-tick lurch (logs/427).
        arm.sync_command_to_measured()
        tracing = os.environ.get("FRUIT_APPROACH_TRACE", "0") == "1"
        # Triggered diagnostic: no per-tick readback at all, so the run stays the
        # shipped one. `ik_step` raises its hand only on a tick where the measured
        # joints moved far more than the command asked for, and *then* we spend one
        # snapshot on the question "what was near the arm".
        anomaly_rows: list = []
        anomaly_path: str | None = None
        if os.environ.get("FRUIT_ANOMALY_TRACE", "0") == "1":
            self._approach_index = getattr(self, "_approach_index", 0) + 1
            anomaly_path = os.path.join(
                os.environ.get("FRUIT_ANOMALY_DIR", "logs/anomaly"),
                f"anomaly_{self._approach_index:03d}.json",
            )
            from isaacsim.core.experimental.prims import RigidPrim as _RigidPrim

            # `FRUIT_ANOMALY_LINKS=0` skips building the link handles, which is the
            # A/B for whether *creating* a RigidPrim mid-run is itself the thing
            # that moves the run (the SEED=5 anomaly run fires no kicks at all and
            # still differs from the baseline).
            link_handles = (
                self._arm_link_handles(arm, _RigidPrim)
                if os.environ.get("FRUIT_ANOMALY_LINKS", "1") == "1"
                else []
            )

            def on_anomaly(info, _arm=arm, _links=link_handles, _rows=anomaly_rows):
                def plain(value):
                    """numpy scalars/arrays -> JSON types; anything else -> repr.

                    `spawner.state()` hands back numpy arrays for the pose and
                    velocity, and the first run that ever fired these snapshots
                    died inside `json.dump` on exactly that (`logs/156`).
                    """
                    if isinstance(value, np.ndarray):
                        return value.tolist()
                    if isinstance(value, (list, tuple)):
                        return [plain(item) for item in value]
                    if isinstance(value, (str, bool, int, float)) or value is None:
                        return value
                    if isinstance(value, (np.floating, np.integer)):
                        return value.item()
                    return repr(value)

                snapshot = dict(info)
                for key, value in list(snapshot.items()):
                    snapshot[key] = plain(value)
                snapshot["sim_time"] = self._sim_time()
                snapshot["side"] = _arm.spec.side
                snapshot["links"] = {
                    name: np.asarray(
                        prim.get_world_poses()[0][0].numpy(), dtype=float
                    ).tolist()
                    for name, prim in _links
                }
                try:
                    snapshot["fruit"] = [
                        {
                            "index": plain(state["index"]),
                            "position": plain(state["position"]),
                            "diameter": plain(state["diameter"]),
                            "velocity": plain(state["velocity"]),
                        }
                        for state in self.spawner.state()
                    ]
                except Exception:  # noqa: BLE001
                    snapshot["fruit"] = None
                try:
                    snapshot["q_cmd"] = (
                        None if _arm._q_cmd is None else np.asarray(_arm._q_cmd).tolist()
                    )
                    snapshot["drive_target"] = np.asarray(
                        _arm.robot.get_dof_position_targets().numpy()
                    )[0].tolist()
                except Exception:  # noqa: BLE001
                    pass
                _rows.append(snapshot)

            arm.anomaly_hook = on_anomaly
        if tracing:
            self._approach_index = getattr(self, "_approach_index", 0) + 1
            arm.begin_trace()
            trace_path = os.path.join(
                os.environ.get("FRUIT_TRACE_DIR", "logs/approach_trace"),
                f"approach_{self._approach_index:03d}.json",
            )
        # Per-tick observation of the line, independent of the IK trace: the
        # descent runs while the feeder indexes behind the stop, so it answers
        # "was the arm hit by produce?" without needing contact queries.
        fruit_trace: list | None = None
        proximity_mode = os.environ.get("FRUIT_PROXIMITY_TRACE", "0")
        if tracing or proximity_mode in ("1", "2"):
            if not tracing:
                self._approach_index = getattr(self, "_approach_index", 0) + 1
                trace_path = os.path.join(
                    os.environ.get("FRUIT_TRACE_DIR", "logs/approach_trace"),
                    f"approach_{self._approach_index:03d}.json",
                )
            fruit_trace = []
            original_step = self._step_sim
            if proximity_mode == "2":
                # Control arm for the perturbation question: install exactly the
                # same hook structure with *no* readback inside. If this still
                # moves the run, the cause is the extra per-tick work; if it does
                # not, the reads themselves are what change the simulation.
                def noop_step(steps: int = 1, _inner=original_step, _rows=fruit_trace):
                    _inner(steps)
                    _rows.append(None)

                self._step_sim = noop_step
            else:
                from isaacsim.core.experimental.prims import RigidPrim

                # The hand bodies are parked 3 m below the cell for the whole
                # descent, so a push on the arm has to come from something else.
                # The line is indexing behind the stop while this leg runs, so
                # record the nearest fruit to the TCP and to any arm link each
                # tick - one row per tick, matching the IK trace rows.
                side_name = arm.spec.side
                link_names = list(arm.robot.link_names)
                link_paths = arm.robot.link_paths
                # `link_paths` is grouped per environment (one sub-list here),
                # exactly as `ArmController.__init__` handles it.
                if link_paths and isinstance(link_paths[0], (list, tuple)):
                    link_paths = link_paths[0]
                # `FRUIT_PROXIMITY_LINKS=0` keeps the per-tick hook but drops the
                # arm-link readback, which is the A/B that says whether it is the
                # link reads or the fruit reads that move the run.
                arm_links: list[tuple[str, object]] | None = None
                if os.environ.get("FRUIT_PROXIMITY_LINKS", "1") == "1":
                    arm_links = self._arm_link_handles(arm, RigidPrim)
                # `spawner.state()` reads each rigid body's linear+angular
                # velocity as well as its pose. `FRUIT_PROXIMITY_VELOCITY=0`
                # keeps the pose read only.
                read_velocity = os.environ.get("FRUIT_PROXIMITY_VELOCITY", "1") == "1"
                # Fruit contact forces come from the solver via a one-time
                # `set_enabled_contact_tracking`, so reading them is a fruit read -
                # the class of readback that leaves the run bit-identical.
                read_force = os.environ.get("FRUIT_PROXIMITY_FORCE", "0") == "1"
                if read_force:
                    say(
                        f"[task] fruit contact tracking enabled on "
                        f"{self.spawner.enable_contact_tracking()} bodies"
                    )

                def proximity_step(steps: int = 1, _inner=original_step,
                                   _rows=fruit_trace, _arm=arm, _links=arm_links,
                                   _vel=read_velocity, _force=read_force):
                    _inner(steps)
                    tcp = np.asarray(_arm.tcp_position(), dtype=float)
                    if _vel:
                        states = self.spawner.state()
                    else:
                        states = [
                            {
                                "index": sample.index,
                                "position": self.spawner.position(sample),
                                "diameter": sample.diameter,
                                "velocity": [0.0, 0.0, 0.0],
                            }
                            for sample in self.spawner.active
                            if not sample.parked
                        ]
                    forces = self.spawner.net_contact_forces() if _force else {}
                    best = None
                    for state in states:
                        position = np.asarray(state["position"], dtype=float)
                        distance = float(np.linalg.norm(position - tcp))
                        if best is None or distance < best[0]:
                            best = (
                                distance,
                                position.tolist(),
                                float(state["diameter"]),
                                np.asarray(state["velocity"], dtype=float)[:3].tolist(),
                            )
                    if _force:
                        for state in states:
                            state["force"] = forces.get(state["index"], [0.0, 0.0, 0.0])
                    link_best = None
                    if _links is not None:
                        positions = [
                            (state["index"], np.asarray(state["position"], dtype=float),
                             float(state["diameter"]))
                            for state in states
                        ]
                        for name, prim in _links:
                            pose = np.asarray(
                                prim.get_world_poses()[0][0].numpy(), dtype=float
                            )
                            for index, position, diameter in positions:
                                gap = float(np.linalg.norm(position - pose))
                                if link_best is None or gap < link_best[0]:
                                    link_best = (gap, name, int(index), diameter)
                    _rows.append({"tcp_fruit": best, "link_fruit": link_best})

                self._step_sim = proximity_step
        # Default `cartesian` since logs/372/373: the profiled descent halves the
        # end-of-leg velocity step (12-14 m/s^2 -> 0-1 m/s^2) and is 4/4, where the
        # old IK chase ended with a 0.10-0.12 m/s step right as the pads meet the fruit.
        mode = os.environ.get("FRUIT_APPROACH_MODE", "cartesian")
        report = os.environ.get("FRUIT_MOTION_REPORT", "0") == "1"
        target = arm.tcp_target_for_jaw(jaw_target)
        start = np.asarray(arm.tcp_position(), dtype=float)
        delta = np.asarray(target, dtype=float) - start
        distance = float(np.linalg.norm(delta))
        monitor = MotionMonitor(f"approach({mode})", mu_eff=None) if report else None
        if monitor is not None:
            monitor.add(0.0, arm.tcp_position())

        if mode == "joint":
            # Solve once, then move the joints along a minimum-jerk blend.
            q_start = arm.joint_positions()
            q_goal, residual = arm.solve_to(
                jaw_target, iterations=400, tolerance=0.006, move_on_fail=False
            )
            limits = TrajectoryLimits.from_env(CONTROL_DT)
            limits.v_max = float(os.environ.get("FRUIT_APPROACH_VMAX", "0.03"))
            limits.a_max = float(os.environ.get("FRUIT_APPROACH_AMAX", "0.4"))
            positions, _, _ = jerk_limited(max(distance, 1e-3), limits)
            blend = min_jerk_ramp(0.0, 1.0, len(positions))
            for i, alpha in enumerate(blend):
                command = q_start + (np.asarray(q_goal, dtype=float) - q_start) * float(alpha)
                arm.robot.set_dof_position_targets([command], dof_indices=arm.arm_dofs)
                self._step_sim(1)
                if monitor is not None:
                    monitor.add((i + 1) * CONTROL_DT, arm.tcp_position())
            if verbose:
                say(f"[task] approach(joint): {len(blend)} ticks, ik residual={residual * 1000:.1f} mm")
        elif mode == "cartesian" and distance > 0.004:
            limits = TrajectoryLimits.from_env(CONTROL_DT)
            limits.v_max = float(os.environ.get("FRUIT_APPROACH_VMAX", "0.03"))
            limits.a_max = float(os.environ.get("FRUIT_APPROACH_AMAX", "0.4"))
            positions, velocities, _ = jerk_limited(distance, limits)
            direction = delta / distance
            for i, value in enumerate(positions):
                arm.ik_step(
                    start + direction * float(value),
                    target_velocity=direction * float(velocities[i]),
                )
                self._step_sim(1)
                if monitor is not None:
                    monitor.add((i + 1) * CONTROL_DT, arm.tcp_position())
        else:
            for _ in range(600):
                residual = arm.ik_step(target)
                self._step_sim(1)
                if monitor is not None:
                    monitor.add(len(monitor.times) * CONTROL_DT, arm.tcp_position())
                if residual <= 0.006:
                    break

        if monitor is not None:
            summary = monitor.summary()
            # Where the leg actually ended, against the point it was sent to. This
            # is the one number in the report that says the descent *arrived*: the
            # speed/acceleration metrics all describe how the hand moved, and a leg
            # that stalls (or that an external push derails) can look "smooth by
            # being slow" while ending centimetres short of the fruit. Measured on
            # `logs/158` (instrumented): one leg ended with a 4-9 cm task error and
            # the post-descent solver finished the approach instead.
            arrived = np.asarray(arm.tcp_position(), dtype=float)
            summary["end_gap_mm"] = float(
                np.linalg.norm(arrived - np.asarray(target, dtype=float)) * 1000.0
            )
            summary["label"] = f"approach({mode}): {distance * 100:.1f} cm, {int(summary['steps'])} samples"
            say(MotionMonitor.format(summary))
        if fruit_trace is not None:
            self._step_sim = original_step
            fruit_path = trace_path.replace(".json", "_fruit.json")
            try:
                os.makedirs(os.path.dirname(fruit_path) or ".", exist_ok=True)
                with open(fruit_path, "w", encoding="utf-8") as handle:
                    json.dump(fruit_trace, handle)
            except TypeError:
                pass
        if arm.anomaly_hook is not None:
            arm.anomaly_hook = None
            if anomaly_rows and anomaly_path is not None:
                os.makedirs(os.path.dirname(anomaly_path) or ".", exist_ok=True)
                with open(anomaly_path, "w", encoding="utf-8") as handle:
                    json.dump(anomaly_rows, handle)
                say(
                    f"[task] anomaly {self._approach_index}: {len(anomaly_rows)} kick(s) "
                    f"-> {anomaly_path}"
                )
        if tracing:
            count = arm.end_trace(trace_path)
            peak = monitor.summary()["a_max"] if monitor is not None else float("nan")
            say(
                f"[task] approach trace {self._approach_index}: {count} IK steps -> "
                f"{trace_path} (a_max={peak:.2f})"
            )
