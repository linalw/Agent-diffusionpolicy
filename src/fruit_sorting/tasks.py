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
import threading
import time
from dataclasses import dataclass, field

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.rendering_manager import RenderingManager

from .bimanual import CoopSession
from .common import say, substeps, to_numpy
from .control import ArmController
from .dataset import EpisodeMeta, EpisodeRecorder, camera_observation
from .grasp import pads_mid
from .actuated_gripper import ActuatedGripper
from .kinematic_gripper import KinematicGripper, OpenArmHand, PAD_THICK
from .motion import (
    MotionMonitor,
    TrajectoryLimits,
    accel_budget,
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


def _quat_about_axis(q, axis, angle: float) -> np.ndarray:
    """`q` rotated by `angle` [rad] about the world `axis` (right-hand rule)."""
    axis = np.asarray(axis, dtype=float)
    axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
    half = 0.5 * float(angle)
    dw, dx, dy, dz = np.cos(half), *(np.sin(half) * axis)
    w, x, y, z = (float(v) for v in q)
    out = np.array(
        [
            dw * w - dx * x - dy * y - dz * z,
            dw * x + dx * w + dy * z - dz * y,
            dw * y - dx * z + dy * w + dz * x,
            dw * z + dx * y - dy * x + dz * w,
        ],
        dtype=float,
    )
    return out / max(float(np.linalg.norm(out)), 1e-9)


_EMPTY_TACTILE = TactileReading(side="none")


class AttemptTimeout(RuntimeError):
    """One scripted attempt exceeded its wall-clock budget.

    Raised by `_step_sim` when `episode_timeout_s > 0` and the attempt's
    deadline has passed; the collector catches it and **skips** the attempt
    (the recorder discards its partial frames) so the next fruit is retried.
    It is a collector-side watchdog only: the belt never stops, the dynamic
    catch never turns into an indexed/stationary pick, and the deadline is
    cleared before the exception leaves `_step_sim`, so the arm's park/feed
    steps after the abort are unaffected. Default off (`episode_timeout_s=0`
    leaves the deadline `None`, one attribute read per tick).
    """


class _AttemptLocal:
    """Per-attempt-thread storage for one attempt's mutable state.

    The bimanual scheduler runs two attempts concurrently in two threads. Every
    field an attempt writes through `self` must be thread-local or the two arms
    clobber each other (the deepest grasp/carry code reads them). The per-arm
    dicts (`_closed_gap[side]`, `_force_*[side]`, ...) stay shared because each
    thread only ever touches its own side.
    """

    def __init__(self, name: str, default=None, factory=None):
        self.name = name
        self.default = default
        self.factory = factory

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        local = obj._attempt_state()
        if not hasattr(local, self.name):
            setattr(local, self.name, self.factory() if self.factory else self.default)
        return getattr(local, self.name)

    def __set__(self, obj, value):
        setattr(obj._attempt_state(), self.name, value)


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
    #: Simulated-clock window of the attempt [s]. Under the bimanual scheduler
    #: the two arms' windows overlap, so these are per-attempt, not cumulative.
    sim_start: float = 0.0
    sim_end: float = 0.0

    @property
    def success(self) -> bool:
        return self.grasped and self.placed

    @property
    def sim_span(self) -> float:
        return max(0.0, self.sim_end - self.sim_start)


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

    # -- per-attempt state -------------------------------------------------- #
    # The bimanual scheduler runs two attempts concurrently, so everything an
    # attempt mutates through `self` lives in the calling thread's local state
    # (`_attempt_state`). Single-arm runs see exactly the old behaviour: the
    # main thread is the only attempt thread and gets the same defaults.
    current_sample = _AttemptLocal("current_sample")
    current_arm = _AttemptLocal("current_arm", "left")
    current_goal = _AttemptLocal(
        "current_goal", factory=lambda: np.zeros(8, dtype=np.float32)
    )
    _dynamic_capture_active = _AttemptLocal("_dynamic_capture_active", False)
    _dynamic_peak_z = _AttemptLocal("_dynamic_peak_z")
    _dynamic_grip_target = _AttemptLocal("_dynamic_grip_target")
    _dynamic_hover_target = _AttemptLocal("_dynamic_hover_target")
    _attempt_sim_t0 = _AttemptLocal("_attempt_sim_t0")
    _gate_open_step = _AttemptLocal("_gate_open_step", 0)
    _biarm_clear_streak = _AttemptLocal("_biarm_clear_streak", 0)
    #: Wall-clock deadline of the current attempt (`episode_timeout_s > 0`
    #: only; the collector arms it, `_step_sim` enforces it). Per-attempt
    #: because the bimanual runs two attempts concurrently.
    _episode_deadline = _AttemptLocal("_episode_deadline")
    #: Two-line scheduler only: the session's pre-pose lock while this slot holds
    #: it. The two pre-poses converge on the shipped shared grasp configuration
    #: (both jaws at y ~ 0), so they are serialized; `_run_impl` releases the
    #: lock once the hover move has taken the hand to its own station.
    _prepose_lock = _AttemptLocal("_prepose_lock")
    _dynamic_trace = _AttemptLocal(
        "_dynamic_trace",
        factory=lambda: (
            [] if os.environ.get("FRUIT_DYNAMIC_TRACE", "0") == "1" else None
        ),
    )
    _cycle_marks = _AttemptLocal(
        "_cycle_marks",
        factory=lambda: (
            [] if os.environ.get("FRUIT_CYCLE_REPORT", "0") == "1" else None
        ),
    )

    def _attempt_state(self):
        """The calling thread's attempt-local container (created on first use)."""
        container = self.__dict__.get("_attempt_tls")
        if container is None:
            container = threading.local()
            self.__dict__["_attempt_tls"] = container
        return container

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
        # `FRUIT_GRIPPER_KIND` selects the contact model:
        #   openarm   (default) - the robot's own visible jaws are the bodies that
        #               hold the fruit (`OpenArmHand`); requires the flattened,
        #               de-instanced asset (the default when present) so the finger
        #               meshes collide. `logs/422` + `logs/431`: the fingers close
        #               on 3.0-6.5 cm fruit and lift ~9.5 cm.
        #   kinematic - the invisible kinematic pads (see kinematic_gripper.py)
        #   actuated  - prismatic fingers with force-limited drives
        kind = os.environ.get("FRUIT_GRIPPER_KIND", "openarm")
        if kind == "actuated":
            self.grippers = {
                side: ActuatedGripper(scene.stage, side) for side in ("left", "right")
            }
        elif kind == "kinematic":
            self.grippers = {
                side: KinematicGripper(scene.stage, side) for side in ("left", "right")
            }
        else:
            self.grippers = {
                side: OpenArmHand(scene.stage, side, self.arms[side])
                for side in ("left", "right")
            }
        self._closed_gap: dict[str, float | None] = {"left": None, "right": None}
        #: The scripted moving catch is arrival-scheduled: pick the fruit farthest
        #: upstream so the pre-pose/hover fit inside its travel time (see
        #: `_balance_arm`). The indexed and policy paths keep grade balancing.
        self._prefer_upstream = bool(
            kind == "openarm" and self._dynamic_pick_mode(openarm=True, scripted=True)
        )
        #: Per-arm pick-station Y [m] (v9/V2 two-line scheduler). Both are the
        #: shipped station (0.0) on every single-arm / shared-station path; the
        #: two-line scheduler sets the right arm's station downstream of the
        #: left's so the two catches no longer contend for one point (see
        #: `run_bimanual` and docs: two stations on the one belt).
        self.station_y: dict[str, float] = {
            "left": float(self.cfg.pick_y),
            "right": float(self.cfg.pick_y),
        }
        #: Station-specific pre-pose configurations (two-line scheduler), keyed
        #: by the resolved station pair -> {side: joint config}. Filled once per
        #: batch by `_prepare_two_line_stations`, before the workers start.
        self._station_grasp: dict[tuple[float, float], dict[str, np.ndarray]] = {}
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
        #: Per-attempt wall-clock budget for the collector's stall guard
        #: (seconds; **0 = off**, the default everywhere except the collector).
        #: `_step_sim` raises `AttemptTimeout` when an attempt runs past it;
        #: the collector skips that attempt (the recorder discards its partial
        #: frames) and retries the next fruit. The belt is never stopped - a
        #: timeout aborts the arm's attempt, not the line.
        self.episode_timeout_s = float(
            os.environ.get("FRUIT_EPISODE_TIMEOUT_S", "0.0")
        )
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
        #: True while a P2 moving catch is in flight: the lift that follows breaks
        #: the moving belt's contact straight up instead of dragging the payload
        #: sideways across it (`logs/p2_012_run2` first-10 carry accelerations).
        #: (Thread-local; see the `_AttemptLocal` block above.)
        #: Peak-hold lift metric for the dynamic path (`FRUIT_DYNAMIC_LIFT_PEAK`,
        #: default on; only consulted while a dynamic capture is active). The
        #: dynamic lift is the *maximum* payload z through the probe, the
        #: belt-break and the first carry, relative to the pre-probe origin,
        #: instead of the final z: a tapered fruit squeezed up into the hand and
        #: then carried back to a lower nominal goal read a negative lift while
        #: the hand still held it (the v5/v6 kiwi artifact - hand-frame pose
        #: constant, 4.4 N, `lift -0.010`, dropped as "fruit did not follow the
        #: gripper"). `FRUIT_DYNAMIC_LIFT_PEAK=0` restores the final-z metric for
        #: an A/B. The indexed path never consults this.
        self._dynamic_lift_peak = (
            os.environ.get("FRUIT_DYNAMIC_LIFT_PEAK", "1") == "1"
        )
        #: Highest payload z seen since the pre-probe origin, or None when no
        #: peak-hold is being tracked (`_dynamic_peak_z` is set in
        #: `grasp_carry_place` and updated in the probe/belt-break/first carry).
        #: Grip/hover jaw targets the arm is left holding before a moving-pick
        #: handover (set in `_run_impl`, read by `grasp_carry_place`).
        #: Optional hook called on every rendered tick (used by the video recorder).
        self.frame_callback = None
        #: The live bimanual session, if any (`CoopSession`); `_step_sim` and
        #: `run` consult it. None on every single-arm path.
        self._active_session: CoopSession | None = None
        #: Opt-in dynamic-pick mechanism trace (`FRUIT_DYNAMIC_TRACE=1`). Off by
        #: default and never part of a shipped run: the per-tick arm-link/tactile
        #: readback measurably moves the run (AGENTS.md section 2), which is
        #: exactly what a mechanism trace is for - it answers *where* a moving
        #: fruit leaves the jaws, not what the shipped line scores.
        if os.environ.get("FRUIT_DYNAMIC_TRACE", "0") == "1":
            say("[trace] dynamic-pick mechanism trace on (FRUIT_DYNAMIC_TRACE=1)")
        #: Sequence number for the direct-path trace dumps (`_dynamic_trace_dump`).
        #: Diagnostics only; never read by the shipped control path.
        self._trace_dump_seq = 0
        #: Opt-in per-attempt cycle breakdown (`FRUIT_CYCLE_REPORT=1`). Pure
        #: `SimulationManager` simulation-time reads at phase boundaries - no
        #: link/tactile readback - so it is the non-invasive reporting class
        #: (AGENTS section 2); off by default like every diagnostic. The phase
        #: names match the per-fruit cycle the speed work reports. Both the trace
        #: and the cycle marks are thread-local (the `_AttemptLocal` block).
        #: Jaw-centre-to-pad standoff of the *moving* catch [m]. Defaults to the
        #: global `PAD_LIFT`, so the shipped line is bit-unchanged; the knob exists
        #: because the catch's grip height on a fruit is a measured variable (the
        #: left-arm carry slip) and the indexed line's contact work is untouched.
        self._dynamic_pad_lift = float(
            os.environ.get("FRUIT_DYNAMIC_PAD_LIFT", str(PAD_LIFT))
        )
        #: Cap the moving catch's pad standoff at a fraction of the fruit's
        #: diameter, to put the pads on/near the widest section of a small
        #: conical fruit. Measured and left **off**: at 0.15 the strawberry still
        #: leaves the hand (hand-frame slide 1659 mm, `logs/p3fix/probe_padfrac`),
        #: so the contact height is not what ejects it.
        self._dynamic_pad_lift_frac = float(
            os.environ.get("FRUIT_DYNAMIC_PAD_LIFT_FRAC", "0.0")
        )
        #: Fraction of the live extent used as the dynamic close's minimum
        #: interference; >0 also turns the live clamp from a floor into a cap and
        #: lets the hold relax to it (small-fruit crush). Measured and left
        #: **off**: the cap shallows the strawberry's commanded depth 2.5 -> 1.3 mm
        #: and it is still ejected (`logs/p3fix/mech_v3`), and it perturbs the
        #: lychee's close, which shifts every later attempt. 0 = historical.
        self._dynamic_interference_frac = float(
            os.environ.get("FRUIT_DYNAMIC_MIN_INTERFERENCE_FRAC", "0.0")
        )
        #: Lateral walk speed above which the close's x-lock is skipped: a fruit
        #: already walking across the belt is a transport to follow, not a slip to
        #: pin [m/s]. Off by default: the measured A/B (`logs/p3fix/mech_v4_walk`)
        #: shows the tracking *chases the squeeze-out* (kiwi close-phase dx
        #: +43 -> +111 mm, a second event at 0.885 m/s), so the pinned x stays.
        self._dynamic_track_walk = os.environ.get("FRUIT_DYNAMIC_TRACK_WALK", "0") == "1"
        self._dynamic_walk_vx = float(
            os.environ.get("FRUIT_DYNAMIC_WALK_VX", "0.03")
        )
        #: Bounded cross-belt (x) seek while the close ramp is still travelling
        #: and no *sustained* contact has been declared [m/s]. The P2b x-lock
        #: pins the span to the fruit's x at the first close tick; a fruit that
        #: is already walking across the belt (the A6 kiwi, +0.08 m/s) then
        #: walks out of the pinned span before the pads arrive. Following the
        #: measured x every tick was measured worse (`FRUIT_DYNAMIC_TRACK_WALK`,
        #: it chases the squeeze-out once loaded), so this seeks at a *bounded*
        #: rate and only until the freeze fires: contact pins x again.
        #: 0.12 is the measured winner's centring seek (v3-C2 `s8_centre_place20`,
        #: repeated in every 8/10 batch); 0 restores the pinned behaviour.
        self._dynamic_x_track_vmax = float(
            os.environ.get("FRUIT_DYNAMIC_X_TRACK_VMAX", "0.12")
        )
        #: Cross-belt walk speed below which the bounded x-seek is a *centring*
        #: action [m/s]. The A2/A8 carry slide starts from a few mm of x
        #: off-centre in the close (the seek fixes it); the A6 kiwi walks at
        #: 0.08-0.23 m/s and following it pushes/launches it (`s6_xseek12`), so
        #: a walking fruit is left pinned: 0 disables the gate (historical
        #: seek-everything), >0 is the shipped centring form.
        self._dynamic_x_track_vx_max = float(
            os.environ.get("FRUIT_DYNAMIC_X_TRACK_VX_MAX", "0.05")
        )
        #: Latch the cross-belt *walk* decision at the first close tick instead of
        #: re-testing it every tick (`FRUIT_DYNAMIC_X_TRACK_LATCH`, **default on
        #: since the v7 directive** - it is part of the measured winner; `=0`
        #: restores the per-tick gate).
        #: The per-tick gate cuts the centring seek off mid-close when a squeeze-out
        #: briefly exceeds `VX_MAX` (measured: A2/A8 hold with the seek always on in
        #: `s6_xseek12` but are lost with the 0.05 gate in `s8_centre_place20`), while
        #: a fruit that is *already* walking at contact (the A6 kiwi, |vx| 0.092 at
        #: the first close tick) must keep the gate or it is pushed off the belt
        #: (`s11_gate10_place15`). The latch separates the two cases by the
        #: pre-contact state.
        self._dynamic_x_track_latch = (
            os.environ.get("FRUIT_DYNAMIC_X_TRACK_LATCH", "1") == "1"
        )
        #: Record carry-leg mechanism rows for the dynamic *place* legs too
        #: (`FRUIT_DYNAMIC_TRACE=1` still required). Off by default: the existing
        #: trace rows and the trace-on runs are unchanged unless this is set.
        self._dynamic_trace_place = (
            os.environ.get("FRUIT_DYNAMIC_TRACE_PLACE", "0") == "1"
        )
        #: GEM-style tracking action for the jaw hand's dynamic `grasp_lift`
        #: carry: proportional gain (0 = off) on the payload's *change* of
        #: position in the hand frame, added to the world-frame carry command so
        #: the hand tracks the payload instead of letting a slip run away. The
        #: correction is clipped to `FRUIT_OPENARM_REACT_MAX` [m].
        self._openarm_react_gain = float(
            os.environ.get("FRUIT_OPENARM_CARRY_REACT", "0.0")
        )
        self._openarm_react_max = float(
            os.environ.get("FRUIT_OPENARM_REACT_MAX", "0.015")
        )
        #: Real force servo for the OpenArm grip's hold/carry legs
        #: (`FRUIT_DYNAMIC_FORCE_SERVO`, **default on since the v7 directive**: the
        #: measured dynamic winner of v3-C2/v5 runs it; `=0` is the opt-out for a
        #: like-for-like A/B). The close freezes the
        #: commanded jaw separation at the depth the fingers found the fruit at;
        #: the drives then hold that *fixed* face separation, so as the payload's
        #: local width shrinks under load (a rolling oblate fruit, a fruit wedged
        #: below its seat) the faces run out of travel, the force collapses and
        #: the payload slides along the tool axis - the A2 place fall-through, the
        #: A6/A8 lift escapes and the policy's post-fire grip losses all end this
        #: way (`logs/dyn_v4`: sep converges onto `gap_cmd` and F 4.4 -> 0 in two
        #: ticks). The servo reads the tactile force every grip tick and moves the
        #: commanded separation by at most `FRUIT_DYNAMIC_FORCE_STEP` per tick:
        #: a sustained force below `max(FRUIT_DYNAMIC_FORCE_MIN,
        #: FRUIT_DYNAMIC_FORCE_DROP * ref)` closes it further, so the squeeze
        #: follows the fruit's local width; a force above
        #: `FRUIT_DYNAMIC_FORCE_MAX` backs it off, so a soft fruit cannot be
        #: crushed. `ref` is the grip's own settle force - the median of the first
        #: `FRUIT_DYNAMIC_FORCE_REF_TICKS` readings - because a light fruit holds
        #: at 2.5-3.6 N while a peach holds at 4.4-4.6 N and an absolute target
        #: would over-squeeze one of them. Travel is bounded to
        #: `[-FRUIT_DYNAMIC_FORCE_RANGE, +FRUIT_DYNAMIC_FORCE_BACKOFF]` around the
        #: gap the grip closed with. Only the *close* direction is used to
        #: recover contact, so the servo can never drop an established squeeze;
        #: the contact force stays at the drive's measured 2.5-4.9 N, i.e. well
        #: inside the friction-cone budget (`FRUIT_MU_SAFETY * mu` with
        #: N = m g needs 0.6-1.7 N for the 20-200 g fruit here). Gated to the
        #: visible OpenArm hand; with the knob off no tactile read happens and the
        #: shipped line is unchanged.
        #: The force servo default follows the shipped line: on for the dynamic
        #: OpenArm catch, off for the indexed opt-out (so `FRUIT_DYNAMIC_PICK=0`
        #: still reproduces the P1 line) and for the policy handover.
        dynamic_default = self._dynamic_pick_mode(
            openarm=(kind == "openarm"), scripted=True
        )
        self._force_servo = os.environ.get(
            "FRUIT_DYNAMIC_FORCE_SERVO", "1" if dynamic_default else "0"
        ) == "1"
        self._force_min = float(os.environ.get("FRUIT_DYNAMIC_FORCE_MIN", "2.0"))
        self._force_drop = float(os.environ.get("FRUIT_DYNAMIC_FORCE_DROP", "0.8"))
        self._force_max = float(os.environ.get("FRUIT_DYNAMIC_FORCE_MAX", "12.0"))
        #: Ceiling on the reference force. A grip that starts with a crush
        #: spike (a strawberry hold reads 13-22 N) would otherwise set a floor
        #: above the healthy carry force (4.3-4.5 N) and the servo would close
        #: to its range limit on a grip that is holding fine (`logs/dyn_v5`,
        #: servo-2 attempts 4/5). 4 N keeps the floor at <= 3.2 N for every
        #: fruit while still scaling down for a light one (orange 2.9 N ->
        #: 2.3 N floor).
        self._force_ref_max = float(
            os.environ.get("FRUIT_DYNAMIC_FORCE_REF_MAX", "4.0")
        )
        self._force_step = float(os.environ.get("FRUIT_DYNAMIC_FORCE_STEP", "0.0004"))
        self._force_ticks = max(1, int(os.environ.get("FRUIT_DYNAMIC_FORCE_TICKS", "3")))
        self._force_settle_ticks = max(
            1, int(os.environ.get("FRUIT_DYNAMIC_FORCE_REF_TICKS", "48"))
        )
        self._force_range = float(os.environ.get("FRUIT_DYNAMIC_FORCE_RANGE", "0.015"))
        self._force_backoff = float(
            os.environ.get("FRUIT_DYNAMIC_FORCE_BACKOFF", "0.003")
        )
        self._force_gap: dict[str, float | None] = {"left": None, "right": None}
        self._force_anchor: dict[str, float | None] = {"left": None, "right": None}
        self._force_under = {"left": 0, "right": 0}
        self._force_over = {"left": 0, "right": 0}
        self._force_tick: dict[str, float] = {"left": -1.0, "right": -1.0}
        #: Servo bookkeeping for the per-attempt report: force samples, the
        #: trips that moved the command, and the last readout.
        self._force_samples: dict[str, list[float]] = {"left": [], "right": []}
        self._force_moves: dict[str, dict] = {}
        self._force_read: dict[str, dict] = {}
        #: State of the last released grip, kept for the per-attempt report
        #: (the release resets the live state before `note_result` prints).
        self._force_last: dict[str, dict] = {}
        #: Contact-verification dwell (v6 experiment 1, `FRUIT_DYNAMIC_VERIFY_DWELL`,
        #: default off). The close/hold returns after the close ramp plus the fixed
        #: `FRUIT_DYNAMIC_HOLD` ticks, whether or not the tactile ever read a real
        #: load. With the knob on, the hold keeps tracking the fruit until the grip
        #: has read at least `FRUIT_DYNAMIC_VERIFY_FORCE` N for
        #: `FRUIT_DYNAMIC_VERIFY_TICKS` consecutive ticks, up to
        #: `FRUIT_DYNAMIC_VERIFY_MAX_TICKS`; no lift is commanded until then, and a
        #: grip that never verifies is released and the attempt fails before the
        #: lift. One `[task] dynamic lift controls:` line per attempt is the
        #: control change's own readout (like the force servo's).
        self._verify_dwell = os.environ.get("FRUIT_DYNAMIC_VERIFY_DWELL", "0") == "1"
        self._verify_force = float(os.environ.get("FRUIT_DYNAMIC_VERIFY_FORCE", "2.0"))
        self._verify_ticks = max(
            1, int(os.environ.get("FRUIT_DYNAMIC_VERIFY_TICKS", "24"))
        )
        self._verify_max = max(
            1, int(os.environ.get("FRUIT_DYNAMIC_VERIFY_MAX_TICKS", "240"))
        )
        #: Staged first lift (v6 experiment 1, `FRUIT_DYNAMIC_RAMP_LIFT`, default
        #: off). The belt-break is a single 50 mm min-jerk ramp over
        #: `FRUIT_DYNAMIC_TAKEOFF_MATCH + _TRANS` (0.45 s) today. The staged form
        #: moves a small first step (`FRUIT_DYNAMIC_RAMP_STEP`, ~2.5 mm) slowly,
        #: pauses (`FRUIT_DYNAMIC_RAMP_PAUSE_TICKS`) to verify the force is still
        #: there, then finishes over `FRUIT_DYNAMIC_RAMP_REST_TICKS` - a longer
        #: horizon than the shipped ramp. The horizontal belt-match profile is
        #: unchanged; only the vertical profile is staged.
        self._ramp_lift = os.environ.get("FRUIT_DYNAMIC_RAMP_LIFT", "0") == "1"
        self._ramp_step = float(os.environ.get("FRUIT_DYNAMIC_RAMP_STEP", "0.0025"))
        self._ramp_step_ticks = max(
            1, int(os.environ.get("FRUIT_DYNAMIC_RAMP_STEP_TICKS", "24"))
        )
        self._ramp_pause_ticks = max(
            0, int(os.environ.get("FRUIT_DYNAMIC_RAMP_PAUSE_TICKS", "24"))
        )
        self._ramp_rest_ticks = max(
            1, int(os.environ.get("FRUIT_DYNAMIC_RAMP_REST_TICKS", "72"))
        )
        #: Force below which the staged ramp counts the payload as lost (a real
        #: loss, not a sensor dropout).
        self._ramp_floor = float(os.environ.get("FRUIT_DYNAMIC_RAMP_FLOOR", "0.5"))
        #: Per-attempt readouts of the two v6 controls (cleared by the report).
        self._dwell_state: dict[str, dict] = {}
        self._ramp_state: dict[str, dict] = {}
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
        self._dynamic_trace_flush(result)
        self._force_servo_report(result)
        self._lift_control_report(result)
        self.stats["attempts"] += 1
        # Simulated-time cycle accounting: the wall clock is not a usable metric
        # on a shared machine (170-207 % CPU during the slow runs, logs/289), but
        # seconds of *simulated* time per pick is what a real cell's cycle time is.
        started = getattr(self, "_attempt_sim_t0", None)
        if started is not None:
            result.sim_start = float(started)
            result.sim_end = float(self._sim_time())
            if self._active_session is None:
                # Cumulative accounting is meaningful only for sequential
                # attempts; under the bimanual session the coordinator records
                # the *span* once (overlapping attempts would double-count).
                self.stats["sim_time"] += max(0.0, result.sim_end - float(started))
        self._cycle_report()
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

    def _fingertip_lowest_z(self, side: str) -> float:
        """World z of the lowest fingertip point of one OpenArm hand [m].

        One aligned-BBox read of the two finger links. `_place_low` uses it once
        per lowered place to bound the descent so the fingers cannot be driven
        into the output belt; it is not read per control tick (arm-link
        readbacks are the invasive class, AGENTS section 2).
        """
        from pxr import Usd, UsdGeom

        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
        lowest = None
        for which in ("left", "right"):
            path = f"/World/OpenArm/openarm_{side}_{which}_finger"
            rng = cache.ComputeWorldBound(self.scene.stage.GetPrimAtPath(path)).ComputeAlignedRange()
            lo = float(rng.GetMin()[2])
            lowest = lo if lowest is None else min(lowest, lo)
        if lowest is None:
            return float(self.arms[side].jaw_centre()[2]) - 0.06
        return float(lowest)

    def _fingertip_offset(self, side: str) -> float:
        """Distance from the jaw centre down to the lowest fingertip, measured live.

        The OpenArm fingers are long plates, so this varies with wrist
        orientation (about 6.1 cm at the pick pose, 8 cm hanging). Using a fixed
        number puts the fingers above small fruit and the jaws close on air.
        """
        jaw_z = float(self.arms[side].jaw_centre()[2])
        return max(0.02, jaw_z - self._fingertip_lowest_z(side))

    def seat_height(self) -> float:
        """How high the fruit is presented for the grasp.

        With the pop-up lifter and the pick stop gone, this is the static nest
        height (0 by default): the fruit rests where the belt left it and the
        kinematic pad hand is placed on its measured centre.
        """
        return float(getattr(self.cfg, "nest_height", 0.0))

    def _transit_to(
        self, side: str, name: str, ticks: int = 90, settle: int = 120,
        target: np.ndarray | None = None,
    ) -> None:
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

        `target` overrides the named pose's configuration (two-line scheduler:
        the arm's own-station pre-pose configuration, see
        `_prepare_two_line_stations`).
        """
        self._catch_up_drive(side)
        if (
            name == "ready"
            and os.environ.get("FRUIT_READY_TRANSIT", "staged") == "staged"
            and self._ready_transit(side, ticks=ticks, settle=settle)
        ):
            return
        goal = self._pose(side, name) if target is None else np.asarray(target, dtype=float)
        self._blend_to(side, goal, ticks=ticks, settle=settle)

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

        The collector's per-attempt wall budget (`episode_timeout_s`) is checked
        here, on the way into a step: default 0 leaves the deadline `None` (one
        attribute read) and every non-collector path is unchanged.
        """
        deadline = self._episode_deadline
        if deadline is not None and time.monotonic() > deadline:
            # Clear before raising, so the park/feed steps that follow the
            # abort are not re-raised. The collector catches AttemptTimeout,
            # discards the partial recording and retries; the belt is never
            # stopped by this.
            self._episode_deadline = None
            raise AttemptTimeout(
                f"attempt exceeded its {self.episode_timeout_s:.0f}s wall budget"
            )
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
        session = self._active_session
        if session is not None and session.after_step is not None:
            # Bimanual bookkeeping runs on the thread that just advanced the
            # clock: the station release check (payload clear of the station
            # box) and, with the opt-in clearance trace, the link readback.
            session.after_step()

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
        gap = self._force_servo_step(side, float(gap))
        self._closed_gap[side] = gap
        self.grippers[side].follow_centre(
            np.asarray(centre, dtype=float),
            np.asarray(quat, dtype=float),
            float(gap),
        )

    # ------------------------------------------------------------------ #
    # OpenArm grip force servo (`FRUIT_DYNAMIC_FORCE_SERVO`, default on)
    # ------------------------------------------------------------------ #
    def _force_servo_reset(self, side: str) -> None:
        """Drop the force servo's per-grip state (new grip or grip released).

        The released state is kept in `_force_last` for `_force_servo_report`:
        the release resets the live state before `note_result` runs.
        """
        book = self._force_moves.get(side)
        read = self._force_read.get(side)
        if book is not None or read is not None:
            self._force_last[side] = {"book": book, "read": read}
        self._force_gap[side] = None
        self._force_anchor[side] = None
        self._force_under[side] = 0
        self._force_over[side] = 0
        self._force_tick[side] = -1.0
        self._force_samples[side] = []
        self._force_moves.pop(side, None)
        self._force_read.pop(side, None)

    def _force_servo_step(self, side: str, gap: float) -> float:
        """One tick of the OpenArm grip force servo; returns the gap to command.

        See the knob block in `__init__` for the mechanism. The law is a
        rate-bounded integral controller in separation space with a force
        deadband:

        * `F < max(MIN, DROP * ref)` for `TICKS` ticks -> close one STEP [m];
        * `F > MAX` for `TICKS` ticks                  -> open one STEP [m];
        * otherwise hold.

        `ref` is the median of the grip's first `REF_TICKS` force samples, so the
        trigger scales with the fruit the grip actually took. The command is
        bounded to the closed gap `- RANGE .. + BACKOFF` metres, which is the
        travel the servo may add while the payload's local width shrinks. The
        same physical tick is only servoed once even when `_hold_with_gripper`
        and `_carry` both run on it.
        """
        if not self._force_servo:
            return float(gap)
        if getattr(self.grippers.get(side), "kind", "") != "openarm":
            return float(gap)
        now = self._sim_time()
        if self._force_tick.get(side) == now:
            current = self._force_gap.get(side)
            return float(gap if current is None else current)
        self._force_tick[side] = now
        gap = float(gap)
        if self._force_anchor.get(side) is None:
            # Engage on the gap the grip closed with; the first REF_TICKS reads
            # establish the reference force.
            self._force_anchor[side] = gap
            self._force_gap[side] = gap
            self._force_samples[side] = []
            self._force_moves[side] = {
                "closed_mm": 0.0, "opened_mm": 0.0, "ref_n": 0.0, "trips": 0,
                "f_min": float("inf"), "f_max": 0.0,
            }
        ref_gap = float(self._force_anchor[side])
        current = self._force_gap.get(side)
        current = ref_gap if current is None else float(current)
        reading = self.tactile.read().get(side, _EMPTY_TACTILE)
        force = float(reading.normal_force)
        samples = self._force_samples[side]
        if len(samples) < self._force_settle_ticks:
            samples.append(force)
        if len(samples) == self._force_settle_ticks:
            ref_force = float(np.median(np.asarray(samples, dtype=float)))
            ref_force = min(ref_force, self._force_ref_max)
            self._force_moves[side]["ref_n"] = ref_force
        else:
            ref_force = float(self._force_moves[side].get("ref_n", 0.0))
        floor = max(self._force_min, self._force_drop * ref_force)
        if len(samples) < self._force_settle_ticks and ref_force <= 0.0:
            # No reference yet (first grip ticks): use the absolute floor only.
            floor = self._force_min
        under = self._force_under[side]
        over = self._force_over[side]
        if force < floor:
            under += 1
            over = 0
        elif force > self._force_max:
            over += 1
            under = 0
        else:
            under = 0
            over = 0
        self._force_under[side], self._force_over[side] = under, over
        moved = 0.0
        if under >= self._force_ticks:
            new = max(ref_gap - self._force_range, current - self._force_step)
            moved = new - current
            current = new
        elif over >= self._force_ticks:
            new = min(ref_gap + self._force_backoff, current + self._force_step)
            moved = new - current
            current = new
        self._force_gap[side] = current
        if moved != 0.0:
            book = self._force_moves[side]
            book["trips"] = int(book.get("trips", 0)) + 1
            if moved < 0.0:
                book["closed_mm"] = float(book.get("closed_mm", 0.0)) - moved * 1000.0
            else:
                book["opened_mm"] = float(book.get("opened_mm", 0.0)) + moved * 1000.0
        self._force_read[side] = {
            "gap_mm": current * 1000.0,
            "force": force,
            "ref_n": ref_force,
            "floor_n": floor,
            "sep_mm": float(
                self.arms[side].JAW_SEPARATION_OFFSET
                + self.arms[side].JAW_SEPARATION_PER_JOINT
                * self.arms[side].finger_opening()
                - self.arms[side].FINGER_FACE_OFFSET
            )
            * 1000.0,
        }
        book = self._force_moves[side]
        book["f_min"] = min(float(book.get("f_min", float("inf"))), force)
        book["f_max"] = max(float(book.get("f_max", 0.0)), force)
        return float(current)

    def _force_servo_report(self, result) -> None:
        """One line per attempt with the servo's own numbers (trace-off mechanism).

        Printed only when the servo is on; it is the control change's own
        readout, not an extra diagnostic, so it rides in the normal log.
        """
        if not self._force_servo:
            return
        entries = []
        for side in ("left", "right"):
            book = self._force_moves.get(side)
            read = self._force_read.get(side)
            if book is None and read is None:
                saved = self._force_last.get(side)
                if saved:
                    book, read = saved.get("book"), saved.get("read")
            if not book or not read:
                continue
            entries.append(
                f"{side}: ref={book.get('ref_n', 0.0):.2f}N "
                f"F[{book.get('f_min', 0.0):.2f},{book.get('f_max', 0.0):.2f}]N "
                f"gap={read.get('gap_mm', 0.0):.1f}mm sep={read.get('sep_mm', 0.0):.1f}mm "
                f"closed={book.get('closed_mm', 0.0):.2f}mm "
                f"opened={book.get('opened_mm', 0.0):.2f}mm "
                f"trips={int(book.get('trips', 0))}"
            )
        # The report is per attempt: clear both the saved and any live state so
        # an earlier episode's grip cannot show up in a later one.
        self._force_last.clear()
        for side in ("left", "right"):
            self._force_gap[side] = None
            self._force_anchor[side] = None
            self._force_under[side] = 0
            self._force_over[side] = 0
            self._force_samples[side] = []
        self._force_moves.clear()
        self._force_read.clear()
        if entries:
            say(f"[task] force servo: {' | '.join(entries)}")

    # ------------------------------------------------------------------ #
    # Contact-verification dwell + staged first lift (v6 experiment 1)
    # ------------------------------------------------------------------ #
    def _dynamic_contact_dwell(
        self,
        side: str,
        sample,
        arm,
        gripper,
        grip_gap: float,
        frozen_x,
        dynamic_v,
        lock_x: bool,
        walk_latched,
        lead_s: float,
    ) -> bool:
        """Hold and verify contact before any lift (opt-in).

        Runs after the close's fixed hold and tracks the fruit exactly as that
        hold does (`FRUIT_DYNAMIC_X_TRACK_*` seek/latch, `v * lead`
        feed-forward, `_hold_with_gripper`). Returns True once the tactile has
        read `FRUIT_DYNAMIC_VERIFY_FORCE` for `FRUIT_DYNAMIC_VERIFY_TICKS`
        consecutive ticks; otherwise it runs to `FRUIT_DYNAMIC_VERIFY_MAX_TICKS`
        and returns False. The per-attempt numbers go to `_dwell_state`.
        """
        book = {
            "min_n": float("inf"),
            "max_n": 0.0,
            "run": 0,
            "ticks": 0,
            "verified": False,
            "need": self._verify_ticks,
            "floor": self._verify_force,
            "cap": self._verify_max,
        }
        self._dwell_state[side] = book
        run = 0
        for tick in range(self._verify_max):
            if tick % 8 == 0:
                # The close refreshed its velocity feed-forward every 8 ticks;
                # a dwell up to 2 s must not command a stale one.
                dynamic_v = np.asarray(self.spawner.velocity(sample), dtype=float)
            centre_now = np.asarray(self.spawner.position(sample), dtype=float)
            if lock_x and frozen_x is not None:
                # Same frozen-x / bounded x-seek as the close's hold: a loaded
                # grip that is being carried (the A6 kiwi) is followed, the
                # squeeze-out is not.
                if self._dynamic_x_track_vmax > 0.0:
                    vx_now = abs(
                        float(np.asarray(self.spawner.velocity(sample), dtype=float)[0])
                    )
                    if self._x_seek_allowed(vx_now, walk_latched, hold=True):
                        frozen_x = self._x_seek_step(
                            float(frozen_x), float(centre_now[0])
                        )
                centre_now[0] = frozen_x
            arm.ik_step(
                arm.tcp_target_for_jaw(
                    centre_now
                    + np.array(
                        [
                            0.0,
                            float(dynamic_v[1]) * lead_s,
                            self._pad_standoff(True, sample),
                        ]
                    )
                )
            )
            self._hold_with_gripper(side, sample)
            self._step_sim(1)
            self._tick_frame()  # pure render; no-op unless recording
            reading = self.tactile.read().get(side, _EMPTY_TACTILE)
            force = float(reading.normal_force)
            book["min_n"] = min(float(book["min_n"]), force)
            book["max_n"] = max(float(book["max_n"]), force)
            run = run + 1 if force >= self._verify_force else 0
            book["run"] = max(int(book["run"]), run)
            book["ticks"] = tick + 1
            self._dynamic_trace_sample(
                "dwell",
                sample,
                arm,
                self.grippers[side],
                float(self._closed_gap.get(side) or grip_gap),
            )
            if run >= self._verify_ticks:
                book["verified"] = True
                return True
        return False

    def _lift_control_report(self, result) -> None:
        """One per-attempt line for the v6 lift controls (trace-off mechanism).

        Printed only when one of the knobs produced state; with the knobs off
        nothing runs, nothing is printed and the shipped/dynamic-default logs
        are unchanged.
        """
        entries = []
        for side in ("left", "right"):
            book = self._dwell_state.get(side)
            if not book:
                continue
            entries.append(
                f"dwell[{side}]: verified={bool(book['verified'])} "
                f"ticks={int(book['ticks'])}/{int(book['cap'])} "
                f"run={int(book['run'])}/{int(book['need'])} "
                f"F[{float(book['min_n']):.2f},{float(book['max_n']):.2f}]N "
                f">={float(book['floor']):.1f}N"
            )
        for side in ("left", "right"):
            book = self._ramp_state.get(side)
            if not book:
                continue
            lost = len(book.get("lost_ticks", []))
            entries.append(
                f"ramp[{side}]: step={float(book['step']) * 1000:.1f}mm "
                f"maintained={bool(book['maintained'])} "
                f"sustained={int(book['sustained'])}/{int(book['pause'])} "
                f"F[{float(book['min_n']):.2f},{float(book['max_n']):.2f}]N "
                f"lost_ticks={lost}"
            )
        if entries:
            say("[task] dynamic lift controls: " + " | ".join(entries))
        self._dwell_state.clear()
        self._ramp_state.clear()


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
            z = belt_top + 0.28
            if getattr(self.grippers.get(side), "kind", "") == "openarm":
                # The jaws hang ~8 cm below the jaw centre; riding higher keeps
                # the fingertips clear of the output line's side rail when the
                # transfer crosses it (measured: the fingertips clipped the rail
                # and the payload jolted 48 m/s^2, `logs/445/446`).
                z += float(os.environ.get("FRUIT_OPENARM_TRANSFER_LIFT", "0.08"))
            return np.array([cfg.pick_x, cfg.pick_y + sign * 0.05, z])
        if name.startswith("place") or name.startswith("bin"):
            # v3: the place target is *above the output conveyor*, not inside a
            # bin. The old `bin{0,1}_above` / `bin{0,1}_inside` names both map
            # here. This is the **transfer** pose the carry leg ends at
            # (`output_place_z`): it keeps the OpenArm fingertips clear of the
            # output line's side rail while the arm crosses it. On the shipped
            # line the hand then descends with the payload to the measured
            # finger-limited clearance before the jaws open
            # (`tasks.py::_place_low`, `FRUIT_PLACE_LOW`); with `FRUIT_PLACE_LOW=0`
            # the pads open here and the fruit free-drops the `output_place_clearance`
            # onto the belt.
            index = 0 if "0" in name else 1
            px, py = cfg.output_belt_drop_points[index]
            z = float(cfg.output_place_z)
            if getattr(self.grippers.get(side), "kind", "") == "openarm":
                # Same fingertip clearance as `grasp_lift`: the transfer is a
                # little higher so the long finger plates clear the output rail.
                z += float(os.environ.get("FRUIT_OPENARM_TRANSFER_LIFT", "0.08"))
            return np.array([px, py, z])
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

    def _payload_clearance(self, sample, fruit) -> tuple[float, str]:
        """Vertical gap from the payload's lowest point to the surface under it.

        The P2-3 check. The pads carry the payload, so the fruit's lowest point
        is what has to clear the line. The surfaces are the main belt top, the
        raised output belt top, and the output belt's side rail top near the
        edge - the rail is what the payload crosses when it moves from the
        pick station to the output line.
        """
        lowest = float(fruit[2]) - self._shape_support(
            sample, np.array([0.0, 0.0, -1.0])
        )
        y = abs(float(fruit[1]))
        if y < 0.40:
            surface, where = self.belt_top, "main belt"
        else:
            surface, where = float(self.cfg.output_belt_top_z), "output belt"
            if y <= 0.46:
                rail = float(self.cfg.output_belt_top_z) + 0.035
                if rail > surface:
                    surface, where = rail, "output rail"
        return lowest - surface, where

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
        if name == "grasp_lift" and self._dynamic_capture_active:
            # A P2 moving catch ends with the payload still over the *running*
            # belt. Break that contact straight up: a diagonal lift drags the
            # payload across the belt surface while it is still touching, which
            # arrived as 5-9 m/s^2 first-10 pad accelerations in the 0.12 m/s
            # acceptance (`logs/p2_012_run2`). The lateral transfer is the place
            # leg's job, after the grip has left the belt.
            pad = np.asarray(self.grippers[side].pad_centre(), dtype=float)
            goal = np.array([float(pad[0]), float(pad[1]), float(goal[2])])
        gap = self._closed_gap.get(side)
        offset_tool = self._gripper_offset.get(side)
        # The OpenArm hand's `pad_centre` *is* the measured jaw centre, so the
        # coherent profile is already in jaw units and must not have the fingertip
        # offset added on top. Its slip "recovery" (which re-seats kinematic pads)
        # cannot move the arm either, so it is off for this hand.
        hand_is_jaw = getattr(self.grippers[side], "kind", "") == "openarm"
        if (
            hand_is_jaw
            and name != "grasp_lift"
            and os.environ.get("FRUIT_OPENARM_HOLD_QUAT", "0") != "1"
        ):
            # The pinned top-down attitude is what keeps the fingers closing
            # across the belt during the grasp and the first lift. The transfer
            # pose is only reachable with the wrist free - exactly the reason the
            # shipped carry runs with `FRUIT_CARRY_HOLD_QUAT=0` - and with the
            # hold pinned the IK stalls ~12 cm short of the output line and the
            # fruit drops beside it (`logs/444`).
            arm.hold_quaternion = None
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
                    if self._dynamic_capture_active:
                        # A grip taken off a *moving* belt has a smaller secure
                        # envelope than the indexed one: the achieved first-10
                        # acceleration overshoots the command at take-off, and the
                        # 3 cm strawberry slipped out mid-lift at 27 N tactile
                        # (`logs/p2_smoke7`). The v7/F1 sweep raised the dynamic
                        # lift in bounded steps; **the dynamic caps are
                        # authoritative here, not a min() against the indexed
                        # lift** - the indexed `FRUIT_LIFT_VMAX` (0.18) is the pad
                        # hand's budget, and with a min() the 0.20/0.30 steps are
                        # inert (measured: `sweep_a3_l020` and `sweep_a3_l030` are
                        # identical at |v|cmd=0.176). The vertical friction cone
                        # caps a <= 1.96 m/s^2, so 1.0 is half the budget and the
                        # held-leg read decides (`sweep_a2_l030_true`). The
                        # Gate-19 lift sweep at the chosen place (0.20/0.25/0.30,
                        # `logs/fast/sweep_iso_p035_l0*`) measured 8/10, 8/10 and
                        # 9/10, so the 0.30 stays the shipped cap.
                        limits.v_max = float(
                            os.environ.get("FRUIT_DYNAMIC_LIFT_VMAX", "0.30")
                        )
                        limits.a_max = float(
                            os.environ.get("FRUIT_DYNAMIC_LIFT_AMAX", "1.0")
                        )
                elif self._dynamic_capture_active:
                    # A moving catch's grip is the most marginal at the first
                    # transfer leg: the A2 peach holds a 0.12 m/s lift but leaves
                    # the jaws somewhere in the 0.37 m/s place leg (grasped=True,
                    # placed=False, `logs/dyn_v3c/s6_xseek12`). The dynamic path
                    # caps the place profile; the indexed line's place profile is
                    # fingerprinted and stays untouched. Set either to 0 to remove
                    # that cap.
                    #
                    # Gate-19 isolation sweep (approach/lift/x-track fixed at the
                    # F1 values, place varied alone, one run per config, trace
                    # off, `logs/fast/sweep_iso_*`): place 0.20 -> 7/10 (17.2 s),
                    # 0.25 -> 7/10 (16.4), 0.30 -> 8/10 (16.1), **0.35 -> 9/10
                    # (15.8, bit-identical double-run)**; the 0.20/0.25 steps flip
                    # the A8 marginal lift, 0.30 holds it. The acceleration is
                    # scaled with v to keep the shipped profile shape (the F1
                    # winner 0.15/0.20): a = 0.20*(v/0.15)^2, so v=0.35 -> 1.089.
                    # The place block falls 5.64 -> 2.85 s and the old "place
                    # raise is 7/10" reading was the unisolated approach+x-track
                    # change, not the place.
                    place_v = float(os.environ.get("FRUIT_DYNAMIC_PLACE_VMAX", "0.35"))
                    if place_v > 0.0:
                        limits.v_max = min(limits.v_max, place_v)
                    place_a = float(os.environ.get("FRUIT_DYNAMIC_PLACE_AMAX", "1.089"))
                    if place_a > 0.0:
                        limits.a_max = min(limits.a_max, place_a)
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
            # Brief wrist hold at the start of a dynamic place leg (opt-in,
            # `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S`). The payload has just rolled
            # into its carry equilibrium and the position-only IK's null-space
            # wrist swing at the lift->place boundary tips a marginal grip out
            # (the A2 peach is lost in the first place ticks, `logs/dyn_v3c`).
            # Hold the attitude the leg starts with for a short time, then
            # release: a full-leg hold stalls the IK ~12 cm short of the output
            # line (`logs/444`), a short one does not.
            place_hold_ticks = 0
            place_hold_active = False
            if (
                hand_is_jaw
                and self._dynamic_capture_active
                and name.startswith("place")
            ):
                place_hold_s = float(
                    os.environ.get("FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S", "0.0")
                )
                if place_hold_s > 0.0:
                    place_hold_ticks = max(
                        1, int(round(place_hold_s / CONTROL_DT))
                    )
                    arm.hold_quaternion = np.asarray(
                        arm.tcp_pose()[1], dtype=float
                    ).copy()
                    place_hold_active = True
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
            slip_enabled = (
                os.environ.get("FRUIT_SLIP_RECOVERY", "1") == "1" and not hand_is_jaw
            )
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
            if (
                hand_is_jaw
                and self._dynamic_capture_active
                and name.startswith("place")
            ):
                # Maintain the squeeze through the place (opt-in,
                # `FRUIT_DYNAMIC_PLACE_SQUEEZE` [m]). The lift ends with the
                # payload wedged near the finger faces; the transfer leg's first
                # motion lets it slide and the finger drives - already at their
                # 10 N/joint limit - stop at the recorded gap while the fruit's
                # local width shrinks, so it drops through (the A2 peach, force
                # 8.4 -> 0 N in two ticks at the place start,
                # `logs/dyn_v3c2/traces_s13_place_trace`). Commanding the faces a
                # little deeper keeps them following the narrowing section
                # instead of stopping. The drive cap bounds the force.
                squeeze = float(
                    os.environ.get("FRUIT_DYNAMIC_PLACE_SQUEEZE", "0.0")
                )
                if squeeze > 0.0:
                    gap_command = max(gap_min, gap_command - squeeze)
            slip_ref = rot.T @ (
                np.asarray(self.spawner.position(sample), dtype=float)
                - np.asarray(self.grippers[side].pad_centre(), dtype=float)
            )
            slip_max = 0.0
            slip_vel_max = 0.0
            # P2-3: per-leg clearance. The payload hangs from the pads, so the
            # fruit's lowest point is what has to clear the belts and rails; it
            # is measured against the highest surface under it every tick and
            # reported per carry leg (the motion gate does not read it).
            clearance_min = float("inf")
            clearance_where = ""
            rel_prev = slip_ref
            recoveries = 0
            coherent = self._coherent.get(side, False)
            finger_len = self._fingertip_offset(side) if coherent else 0.0
            # GEM-style tracking action (opt-in): remember the payload's initial
            # position in the hand frame so the reaction can cancel a *change*
            # of it, not the seating offset itself.
            react = (
                hand_is_jaw
                and self._dynamic_capture_active
                and name == "grasp_lift"
                and self._openarm_react_gain > 0.0
            )
            react_ref = None
            if react:
                react_ref = (
                    np.asarray(self.spawner.position(sample), dtype=float)
                    - np.asarray(arm.jaw_centre(), dtype=float)
                ).copy()
            for i in range(len(commands)):
                centre = commands[i]
                if place_hold_active and i >= place_hold_ticks:
                    # Release the place-start wrist hold; the position-only IK
                    # takes the wrist back from here (see the hold above).
                    arm.hold_quaternion = None
                    place_hold_active = False
                if react and react_ref is not None:
                    # Tracking term: the hand command follows the payload's
                    # displacement in the hand frame (clipped), so the relative
                    # motion a sliding grip has begun is servoed back toward
                    # zero while the world profile continues. The clip bounds
                    # the chase; a payload that runs past it is lost as before.
                    fruit_now = np.asarray(self.spawner.position(sample), dtype=float)
                    jaw_now = np.asarray(arm.jaw_centre(), dtype=float)
                    err = (fruit_now - jaw_now) - react_ref
                    centre = centre + np.clip(
                        self._openarm_react_gain * err,
                        -self._openarm_react_max,
                        self._openarm_react_max,
                    )
                # Force servo (default off): one decision per control tick for
                # both carry branches - the OpenArm's coherent flag is often
                # False even though the jaws are the hand (the fingertip
                # estimate reads 6 cm long, `logs/...`), so the assignment has
                # to sit before the branch or it silently never runs.
                gap_command = self._force_servo_step(side, gap_command)
                self._closed_gap[side] = gap_command
                if coherent:
                    # Rigid hand: command the *palm* along the profile and let the
                    # pads follow wherever the arm actually is - the IK lag is real
                    # hand deflection, and the payload is carried by friction.
                    if hand_is_jaw:
                        arm.ik_step(arm.tcp_target_for_jaw(centre))
                    else:
                        arm.ik_step(
                            arm.tcp_target_for_jaw(
                                centre + np.array([0.0, 0.0, finger_len + PAD_LIFT])
                            )
                        )
                    quat = np.asarray(arm.tcp_pose()[1], dtype=float)
                    rot = _quat_matrix(quat)
                    if hand_is_jaw:
                        centre = np.asarray(arm.jaw_centre(), dtype=float)
                    else:
                        centre = np.asarray(arm.jaw_centre(), dtype=float) + rot @ np.array(
                            [0.0, 0.0, finger_len]
                        )
                    self.grippers[side].follow_centre(centre, quat, gap_command)
                    self._grip_centre[side] = np.asarray(centre, dtype=float)
                    self._grip_quat[side] = quat
                    trace_n = int(os.environ.get("FRUIT_OPENARM_TRACE", "0"))
                    if trace_n and (
                        i < trace_n or i > len(commands) - trace_n
                    ):
                        say(
                            f"[task]   openarm carry {name} tick {i}: "
                            f"cmd={np.round(commands[i], 4).tolist()} "
                            f"jaw={np.round(arm.jaw_centre(), 4).tolist()} "
                            f"tcp={np.round(arm.tcp_position(), 4).tolist()} "
                            f"q={np.round(arm.dof_positions()[arm.arm_dofs], 4).tolist()}"
                        )
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
                    if os.environ.get("FRUIT_CARRY_DIAG", "0") == "1" and i < 3:
                        say(
                            f"[diag] carry-assist {side} {name} tick {i}: "
                            f"cmd_centre={np.round(centre, 4).tolist()} "
                            f"offset={np.round(offset_tool, 4).tolist()} "
                            f"|offset|={float(np.linalg.norm(offset_tool)) * 1000:.0f} mm "
                            f"jaw_target={np.round(centre - rot @ offset_tool, 4).tolist()} "
                            f"jaw={np.round(arm.jaw_centre(), 4).tolist()} "
                            f"coherent={bool(self._coherent.get(side, False))} "
                            f"hand_is_jaw={hand_is_jaw}"
                        )
                self._step_sim(1)
                self._tick_frame()
                self._record(self._action9(self._commanded_arm(arm), arm))
                if self._dynamic_capture_active and (
                    name == "grasp_lift"
                    or (self._dynamic_trace_place and name.startswith("place"))
                ):
                    # Mechanism rows for the dynamic lift (trace-on only): the
                    # ejection happens somewhere in this leg and the carry's own
                    # summary only reports the extremes.
                    self._dynamic_trace_sample(
                        "carry", sample, arm, self.grippers[side], gap_command,
                        cmd=commands[i],
                    )
                # Always *measure* the payload's motion in the hand frame - it is
                # the honest slip/jitter signal and it goes into the motion report;
                # only *react* to it when the recovery is enabled.
                fruit = np.asarray(self.spawner.position(sample), dtype=float)
                if (
                    self._dynamic_capture_active
                    and self._dynamic_lift_peak
                    and name == "grasp_lift"
                    and self._dynamic_peak_z is not None
                ):
                    # Peak-hold metric (dynamic first carry only): see `__init__`.
                    self._dynamic_peak_z = max(self._dynamic_peak_z, float(fruit[2]))
                pads = np.asarray(self.grippers[side].pad_centre(), dtype=float)
                clearance, where = self._payload_clearance(sample, fruit)
                if clearance < clearance_min:
                    clearance_min, clearance_where = clearance, where
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
                if clearance_min < float("inf"):
                    say(
                        f"[motion] carry {name} clearance: lowest payload point "
                        f"{clearance_min * 1000:+.0f} mm to the {clearance_where}"
                    )
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
                clearance, where = self._payload_clearance(
                    sample, np.asarray(self.spawner.position(sample), dtype=float)
                )
                if clearance < clearance_min:
                    clearance_min, clearance_where = clearance, where
                arm.ik_step(
                    arm.tcp_target_for_jaw(
                        placed if hand_is_jaw else placed - rot @ offset_tool
                    )
                )
                self._step_sim(1)
                self._record(self._action9(self._commanded_arm(arm), arm))
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
            self._record(self._action9(self._commanded_arm(arm), arm))
            if np.linalg.norm(arm.jaw_centre() - goal) < 0.010:
                break
        for _ in range(30):
            arm.ik_step(goal + offset)
            self._step_sim(1)
            self.spawner.follow(sample, arm.jaw_centre())
            self._hold_with_gripper(side, sample)
            self._record(self._action9(self._commanded_arm(arm), arm))
        if os.environ.get("FRUIT_CARRY_DEBUG") == "1":
            say(
                f"[task]   carry {name}: jaw={np.round(arm.jaw_centre(), 3).tolist()} "
                f"goal={np.round(goal, 3).tolist()} "
                f"err={float(np.linalg.norm(arm.jaw_centre() - goal)):.4f} m"
            )

    # ------------------------------------------------------------------ #
    # Data collection
    # ------------------------------------------------------------------ #
    def _commanded_arm(self, arm) -> np.ndarray:
        """The joint target the drives hold for `arm`'s seven arm joints.

        Contract (P4 fix): the recorded `action[:7]` is the *commanded* joint
        target - the vector `ik_step` wrote to the drives, i.e. the joint target
        that produces the next tick's motion - never the measured joints. A
        measured-joint action commanded back is a brake, and the demonstrated
        motion then does not exist in the action column at all (WORKLOG: "the
        recorded action is the measured joint state").

        `ik_step` stores exactly the vector it sends (`control.py`:
        `self._q_cmd = command` immediately before `set_dof_position_targets`),
        so after an IK step `arm._q_cmd` is the command the drive received.
        Before any IK step in the episode there is nothing commanded to record
        but the measured pose.
        """
        if getattr(arm, "_q_cmd", None) is None:
            return arm.joint_positions()
        return np.asarray(arm._q_cmd, dtype=float)

    def _arm_drive_target(self, arm) -> np.ndarray:
        """The position target the arm's drives currently hold (one readback).

        Used where the loop does not command the arm (the assisted close) and
        `_q_cmd` therefore does not mirror the drives; one read per close, only
        while a recorder is attached, so the scripted control path is unchanged.
        """
        targets = np.asarray(arm.robot.get_dof_position_targets().numpy())[0]
        return targets[arm.arm_dofs].astype(float).copy()

    def _action9(self, arm_config: np.ndarray, arm, finger_value: float | None = None) -> np.ndarray:
        """Pack an action as 7 arm joints + 2 finger joints.

        `arm_config` must be the *commanded* joint target (`_commanded_arm` or
        the calibrated target the loop set directly), not the measured state:
        `action[:7]` is the joint target that produced the next tick's motion.
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
        too, but it advances the simulation by a variable amount. Under the
        bimanual session the callback is routed to the main thread (rendering is
        not thread-safe); outside it, it runs inline as always.
        """
        session = self._active_session
        bridged = (
            session is not None
            and session.relay.participant()
            and session.bridge.serving
        )
        if self.frame_callback is not None:
            if bridged:
                session.bridge.call(self.frame_callback)
            else:
                self.frame_callback()
        elif self.recorder is not None:
            # W3: the two-line collector calls this from an attempt thread; a
            # render from there is not thread-safe, so route it through the
            # session's main-thread bridge (same rule as `frame_callback`).
            if bridged:
                session.bridge.call(RenderingManager.render)
            else:
                RenderingManager.render()

    # ------------------------------------------------------------------ #
    # Dynamic-pick mechanism trace (opt-in, diagnostic only)
    # ------------------------------------------------------------------ #
    def _dynamic_trace_sample(self, phase: str, sample, arm, gripper, gap: float,
                              fruit=None, cmd=None) -> None:
        """Record one mechanism sample while a moving fruit is being caught.

        Only active with `FRUIT_DYNAMIC_TRACE=1`. The row carries where the
        *fingertips* are against where the *fruit* is, the commanded and measured
        jaw spans, and the tactile force - the four numbers that say whether the
        close is late (plot: is the fruit already downstream of the fingertips?),
        the close is too slow (span still wide when the fruit passes the trailing
        edge), or the grip is taken and then lost (offset grows from zero).

        The carry-phase diagnosis of the left-arm slip additionally needs the
        contact geometry the jaw-span number cannot show: the two finger link
        origins, the fruit's linear *and angular* velocity, and the payload's
        pose in the hand frame (`hand_rel`). All of these are fruit/finger reads,
        i.e. the same class the trace already does every tick.
        """
        if self._dynamic_trace is None:
            return
        try:
            if fruit is None:
                fruit = self.spawner.position(sample)
            fruit = np.asarray(fruit, dtype=float)
            jaw_left = jaw_right = None
            try:
                jaw_left, jaw_right = arm.jaw_positions()
                jaw_left = np.asarray(jaw_left, dtype=float)
                jaw_right = np.asarray(jaw_right, dtype=float)
                jaw = (jaw_left + jaw_right) / 2.0
            except Exception:  # noqa: BLE001
                jaw = np.asarray(arm.jaw_centre(), dtype=float)
            _, quat = arm.tcp_pose()
            rot = _quat_matrix(np.asarray(quat, dtype=float))
            tip = jaw + rot @ np.array([0.0, 0.0, float(os.environ.get("FRUIT_FINGER_LEN", "0.060"))])
            reading = self.tactile.read().get(arm.spec.side, _EMPTY_TACTILE)
            belt = getattr(self.spawner, "belt", None)
            row = {
                "phase": phase,
                "t": round(self._sim_time(), 5),
                "fruit": [round(float(v), 5) for v in fruit],
                "jaw": [round(float(v), 5) for v in jaw],
                "tip": [round(float(v), 5) for v in tip],
                "offset": [round(float(v), 5) for v in (tip - fruit)],
                "sep": round(float(arm.jaw_separation()), 5),
                "gap_cmd": round(float(gap), 5),
                "force": round(float(reading.normal_force), 3),
                "contacts": int(reading.contact_count),
                # Per-sensor split (`side_i` -> N): with the D2 soft pads this
                # reads which bodies carry the load (finger meshes vs pads).
                "ft": {
                    str(k): round(float(v), 3)
                    for k, v in (reading.fingertip_forces or {}).items()
                },
                "belt": round(float(getattr(belt, "encoder_speed", 0.0)), 5),
                # Contact-geometry fields for the carry-slip diagnosis. `hand_rel`
                # is the payload's position in the *hand* (tool) frame - a hold
                # keeps it constant, a slide grows it - and `along` is where the
                # fruit centre sits on the tool axis relative to the jaw midpoint.
                "hand_rel": [
                    round(float(v), 5) for v in (rot.T @ (fruit - jaw))
                ],
                "fruit_vel": [
                    round(float(v), 5)
                    for v in np.asarray(self.spawner.velocity(sample), dtype=float)
                ],
                "fruit_omega": [
                    round(float(v), 5)
                    for v in np.asarray(self.spawner.angular(sample), dtype=float)
                ],
                "quat": [round(float(v), 5) for v in np.asarray(quat, dtype=float)],
            }
            if jaw_left is not None and jaw_right is not None:
                row["finger_left"] = [round(float(v), 5) for v in jaw_left]
                row["finger_right"] = [round(float(v), 5) for v in jaw_right]
            if cmd is not None:
                row["cmd"] = [round(float(v), 5) for v in np.asarray(cmd, dtype=float)]
            # D2 mechanism readout (trace-on only): the compliant pads'
            # compression [mm], so the trace shows the pad following the local
            # width while the in-hand slide is measured. No-op (empty) unless
            # `FRUIT_FINGER_SOFT_PAD=1` authored the pads.
            try:
                pad_states = getattr(self.scene, "soft_pad_states", None)
                if pad_states is not None:
                    states = pad_states(getattr(arm.spec, "side", ""))
                    if states:
                        row["soft_pad"] = states
            except Exception:  # noqa: BLE001 - the trace must never change an outcome
                pass
            self._dynamic_trace.append(row)
        except Exception:  # noqa: BLE001 - a trace must never change an outcome
            pass

    def _dynamic_trace_flush(self, result) -> None:
        """Write the trace and its per-attempt summary, then start a new attempt."""
        rows = self._dynamic_trace
        if rows is None:
            return
        self._dynamic_trace = []
        index = int(self.stats["attempts"])
        try:
            import json

            os.makedirs("logs", exist_ok=True)
            path = os.path.join("logs", f"dynamic_trace_{index:02d}.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(rows, handle)
            close = [r for r in rows if r["phase"] == "close"]
            contact = [r for r in rows if r["force"] >= 0.5 or r["contacts"] > 0]
            summary = {
                "attempt": index,
                "sample": result.sample_index,
                "rows": len(rows),
                "close_rows": len(close),
                "close_start_offset_mm": None if not close else [
                    round(float(v) * 1000.0, 1) for v in close[0]["offset"]
                ],
                "t_close_start": None if not close else close[0]["t"],
                "force_max": max((r["force"] for r in rows), default=0.0),
                "sep_min": min((r["sep"] for r in close), default=0.0),
                "first_contact": None if not contact else {
                    "t": contact[0]["t"],
                    "fruit_y": contact[0]["fruit"][1],
                    "offset_y_mm": round(contact[0]["offset"][1] * 1000.0, 1),
                },
                "last_contact": None if not contact else {
                    "t": contact[-1]["t"],
                    "fruit_y": contact[-1]["fruit"][1],
                },
                "fruit_y_close_start": None if not close else close[0]["fruit"][1],
                "fruit_y_close_end": None if not close else close[-1]["fruit"][1],
                "fruit_y_at_eject": None if not contact else contact[-1]["fruit"][1],
                "grasped": bool(result.grasped),
                "lift": float(result.peak_lift),
                "notes": list(result.notes),
            }
            with open(path.replace(".json", "_summary.json"), "w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2)
            say(
                f"[trace] dynamic attempt {index}: rows={len(rows)} "
                f"close_start_offset={summary['close_start_offset_mm']} "
                f"first_contact={summary['first_contact']} sep_min="
                f"{summary['sep_min']:.4f} force_max={summary['force_max']:.2f} "
                f"grasped={result.grasped} lift={result.peak_lift:+.3f} -> {path}"
            )
        except Exception as exc:  # noqa: BLE001
            say(f"[trace] dynamic trace flush failed: {exc!r}")

    def _dynamic_trace_dump(self, arm_name: str, scripted: bool, outcome: str) -> None:
        """Write an attempt's dynamic-trace rows for the *policy* path.

        `_dynamic_trace_flush` runs from `note_result`, which only the scripted
        loop calls; the direct handover ends inside `grasp_carry_place` and its
        rows used to die with the attempt. Diagnostics only: a no-op unless
        `FRUIT_DYNAMIC_TRACE=1`, and it never touches the control path.
        """
        rows = self._dynamic_trace
        if rows is None:
            return
        self._dynamic_trace = []
        self._trace_dump_seq = int(getattr(self, "_trace_dump_seq", 0)) + 1
        try:
            import json

            out_dir = os.environ.get("FRUIT_DYNAMIC_TRACE_DIR", "logs/dynamic_trace")
            os.makedirs(out_dir, exist_ok=True)
            mode = "scripted" if scripted else "direct"
            path = os.path.join(
                out_dir,
                f"trace_{self._trace_dump_seq:02d}_{arm_name}_{mode}_{outcome}.json",
            )
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "arm": arm_name,
                        "scripted": bool(scripted),
                        "outcome": outcome,
                        "rows": rows,
                    },
                    handle,
                )
            say(
                f"[trace] {mode} {arm_name} {outcome}: {len(rows)} rows -> {path}"
            )
        except Exception as exc:  # noqa: BLE001
            say(f"[trace] direct trace dump failed: {exc!r}")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _sim_time() -> float:
        from isaacsim.core.simulation_manager import SimulationManager

        return float(SimulationManager.get_simulation_time())

    def _cycle_begin(self) -> None:
        """Start a per-attempt cycle breakdown (no-op unless `FRUIT_CYCLE_REPORT`)."""
        if self._cycle_marks is not None:
            self._cycle_marks = [("start", float(self._sim_time()))]

    def _cycle_mark(self, label: str) -> None:
        """Record one phase boundary of the per-attempt cycle (no-op unless enabled)."""
        if self._cycle_marks is not None:
            self._cycle_marks.append((label, float(self._sim_time())))

    def _cycle_report(self) -> None:
        """Print the phase breakdown of the attempt that just finished (see `__init__`)."""
        marks = self._cycle_marks
        if marks is None:
            return
        self._cycle_marks = []
        if len(marks) < 2:
            return
        segments = " ".join(
            f"{nxt[0]}={nxt[1] - cur[1]:.2f}s" for cur, nxt in zip(marks, marks[1:])
        )
        say(
            f"[cycle] attempt {int(self.stats['attempts'])}: {segments} "
            f"total={marks[-1][1] - marks[0][1]:.2f}s"
        )

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

    def station_y_for(self, arm: str) -> float:
        """The pick-station Y this arm catches at [m].

        0.0 (the shipped station) unless the two-line scheduler assigned this
        arm its own station on the shared belt (`run_bimanual`). Thread-safe:
        the dict is written once per batch before the workers start.
        """
        return float(self.station_y.get(arm, self.cfg.pick_y))

    def select_target(
        self, states: list[dict], lead_time: float = 0.0, lane: int | None = None,
        min_lead_s: float | None = None, station_y: float | None = None,
        prefer_lane: int | None = None, exclude: set[int] | None = None,
    ) -> dict | None:
        """Choose the next fruit that will reach the pick pose.

        Falls back to the fruit closest to the middle of the belt window when
        nothing is upstream yet.

        `lane` restricts the choice to one output lane (0 = grade A, +Y, the
        left arm; 1 = everything else, -Y, the right arm). The bimanual
        scheduler selects one target per arm with it; `lane=None` keeps the
        single-arm behaviour byte-for-byte for the indexed path. `min_lead_s`
        raises the window's upstream edge to the setup a caller actually needs
        (the bimanual worker passes its measured pre-pose + hover-move time, so
        a fruit can never be selected so close to the station that the setup
        ends after it has passed). On the moving-catch line
        (`_prefer_upstream`) candidates below `_dynamic_select_floor()` are
        refused outright: the catch's setup consumes that much belt travel
        before its handover check, so a fruit selected inside the floor is
        already past the point the descent can meet (measured: 253 mm
        catch-up residual, 1/10 rate on the scattered supply before this
        floor, `logs/v1/20_rate_supply_1.log`).

        `station_y` (default: `cfg.pick_y`) is the Y the windows are measured
        from: the two-line scheduler passes the arm's own station. `prefer_lane`
        (two-line only, `lane=None`) selects for one arm. With the W3 grade
        routing (**shipped: pure per arm** - left arm grade A only, right arm
        grade B only, grade C is never selected; `FRUIT_GRADE_ROUTING=0`
        restores the V2 grade-preference-with-any-grade-fallback), the lane's
        grade is the *eligibility* filter, so a lane can starve when the grade
        is not on the segment (that is the owner's routing semantics, not a
        starvation bug). `exclude` skips fruit indices already protected by
        the other arm's in-flight attempt (concurrent selection must not
        double-book one fruit).
        """
        pick_y = float(self.cfg.pick_y) if station_y is None else float(station_y)
        exclude = exclude or ()
        #: W3 pure routing: only meaningful together with `prefer_lane` (the
        #: two-line worker); the single-arm selectors keep every grade.
        pure_grade = prefer_lane is not None and self._pure_grade_routing()
        wanted_grade = "A" if prefer_lane == 0 else "B"
        upstream: list[tuple[float, dict]] = []
        middle: list[tuple[float, dict]] = []
        station: list[tuple[float, dict]] = []
        for state in states:
            if exclude and int(state["index"]) in exclude:
                continue
            if pure_grade and state.get("grade") != wanted_grade:
                # W3 owner decision: each arm sorts exactly one grade, and
                # grade C (neither arm's) is never selected - it rides past
                # both stations to the end of the main belt, where `update`
                # counts it `reached_end` and the feeder recycles it (the
                # end-of-line path; see `FruitSpawner.update`).
                continue
            if lane is not None:
                # The lane is the arm (the left arm cannot cross the body to the
                # -Y belt), and the lane is decided by the grade - see
                # `20_pick_place.py` / `_run_impl`.
                grade_lane = 0 if state.get("grade") == "A" else 1
                if grade_lane != lane:
                    continue
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
            # Scale the station window's upstream edge with the belt speed. The
            # fixed 0.12 m is only 2 s of travel at 0.06 m/s but 0.4 s at 0.30:
            # a fruit selected inside the old window is carried past the pick
            # pose before the pre-pose finishes. The moving line's setup is
            # ~0.9 s (transit+update+handover) and the descent waits for the
            # fruit anyway, so this only keeps the *selection* from choosing
            # fruit that is already past the point the arm can meet.
            prepose_lead = max(
                prepose_lead,
                abs(float(self.cfg.belt_speed))
                * float(os.environ.get("FRUIT_PREPOSE_LEAD_S", "0.9")),
            )
            if min_lead_s is not None:
                prepose_lead = max(
                    prepose_lead, abs(float(self.cfg.belt_speed)) * float(min_lead_s)
                )
            station_floor = pick_y - 0.02 + prepose_lead
            upstream_floor = max(pick_y + 0.18, station_floor)
            if (
                # Default on: the gate presents one fruit at a time, so taking what
                # the feeder presents is both what a real cell does and what keeps
                # the cycle short. The reject policy (FRUIT_MAX_RETRIES) is what
                # makes it safe - without it the same hard fruit was retried until
                # the attempts ran out (logs/277).
                os.environ.get("FRUIT_STATION_FIRST", "1") == "1"
                and station_floor <= along <= pick_y + 0.18
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
            if upstream_floor < along <= pick_y + 0.85:
                upstream.append((along, state))  # smallest y first = first to arrive
        if self._prefer_upstream:
            # Moving catch: only candidates the schedule can meet (see
            # `_dynamic_select_floor`); the wait loop absorbs any extra lead by
            # hovering at the station. A lane selection (bimanual) takes the
            # nearest usable fruit so the station is held for the shortest
            # hover; the single-arm selection keeps the farthest-upstream rule
            # (`_balance_arm`). The two-line scheduler passes `prefer_lane` with
            # `lane=None`: eligibility is any grade (no starvation), the nearest
            # fruit of the arm's own lane wins when one is in the window, and a
            # cross-lane fruit is taken only when the arm's own lane has none.
            floor = pick_y + self._dynamic_select_floor(min_lead_s)
            usable = [item for item in station + upstream if item[0] >= floor]
            if not usable:
                return None
            usable.sort(key=lambda item: item[0])
            if lane is not None:
                return usable[0][1]
            if prefer_lane is not None:
                if pure_grade:
                    # W3 pure routing: every `usable` candidate already carries
                    # the arm's own grade, so the nearest (shortest hover) is
                    # returned directly - no cross-grade fallback.
                    return usable[0][1]
                for _along, state in usable:
                    grade_lane = 0 if state.get("grade") == "A" else 1
                    if grade_lane == prefer_lane:
                        return state
                return usable[0][1]
            return self._balance_arm(usable)
        if station:
            ordered = sorted(station, key=lambda item: item[0])
            return ordered[0][1] if lane is not None else self._balance_arm(ordered)
        if upstream:
            ordered = sorted(upstream, key=lambda item: item[0])
            # A lane-filtered (bimanual) selection takes the fruit that arrives
            # first in that lane: the two arms run concurrently, so the schedule
            # cannot use the single-arm "farthest upstream" preference.
            return ordered[0][1] if lane is not None else self._balance_arm(ordered)
        if middle:
            return min(middle, key=lambda item: item[0])[1]
        return None

    def _pure_grade_routing(self) -> bool:
        """Whether `prefer_lane` selection is grade-pure (W3 owner decision).

        Left arm (lane 0) takes grade A only, right arm (lane 1) grade B only,
        and grade C is never selected (it passes both stations and leaves the
        main belt at the end of the line, where `FruitSpawner.update` counts
        it `reached_end` and the feeder recycles it). Default **on** for the
        two-line selector; `FRUIT_GRADE_ROUTING=0` restores the V2
        grade-preference with the any-grade fallback. The single-arm selector
        never calls this (it passes no `prefer_lane`), so its line is
        byte-unchanged.
        """
        mode = os.environ.get("FRUIT_GRADE_ROUTING", "auto").strip().lower()
        return mode not in ("0", "off", "prefer", "fallback", "false", "no")

    def _dynamic_profile(self, name: str, shipped: str, two_line: str) -> str:
        """Resolve a dynamic-path knob: env override, else the two-line profile.

        The W1 grip profile (re-seat in place after a failed probe + a gentler
        probe) is scoped to the two-line scheduler. With the same values as
        *global* defaults the shipped single arm drops 9/10 -> 6/10 (its
        selection cycle shifts and reshuffles the marginal branch,
        `logs/w1/36_single_winner_screen.log`); the two-line is a separate
        scenario (`AGENTS.md`) and keeps the shipped single-arm branch
        byte-unchanged unless `FRUIT_BIARM_TWOLINE=1` runs it. An explicit env
        value always wins, on either path.
        """
        env = os.environ.get(name)
        if env is not None:
            return env
        session = self._active_session
        if session is not None and getattr(session, "twoline", False):
            return two_line
        return shipped

    def _dynamic_select_floor(self, min_lead_s: float | None = None) -> float:
        """Minimum along-position a moving catch can still meet, above the station [m].

        The catch breaks out of its wait when the fruit reaches
        `_dynamic_pick_lead()`, and the selection-to-wait-loop setup consumes
        `FRUIT_DYNAMIC_SELECT_S` seconds of belt travel first (measured: the
        selected fruit sits ~0.62 m upstream at selection, 0.43 m at the wait
        loop's first step and 0.19 m at the handover, i.e. ~1.5 s of pre-pose +
        transit; `logs/v1/00_accept_scatter_off.log` attempt 0). A fruit
        selected inside this floor is already past the point the descent can
        meet, and the attempt chases it downstream - with the scattered, stocked
        belt that produced 253 mm catch-up residuals and a 1/10 rate
        (`logs/v1/20_rate_supply_1.log`), because the old station-first rule
        handed the catch the nearest fruit (0.10-0.18 m) instead of the one the
        schedule can meet. The floor is in the *selector*, not the catch: the
        wait loop still absorbs any extra lead by hovering.
        """
        speed = abs(self._belt_speed_estimate())
        setup = float(os.environ.get("FRUIT_DYNAMIC_SELECT_S", "1.5"))
        if min_lead_s is not None:
            setup = max(setup, float(min_lead_s))
        margin = float(os.environ.get("FRUIT_DYNAMIC_SELECT_MARGIN", "0.03"))
        return self._dynamic_pick_lead() + speed * setup + margin

    def _balance_arm(self, ordered: list[tuple[float, dict]]) -> dict:
        """Prefer a fruit whose grade sends it to the less-used arm.

        The collector used to take the next fruit in arrival order, which - with a
        fixed seed - produced 17 right-arm episodes and no left-arm ones. Sorting
        is a two-arm task, so the balance is worth a small amount of look-ahead.

        The shipped moving catch is the exception: it is *scheduled* (the hand
        waits at the hover and the descent must fit inside the fruit's travel),
        so it takes the farthest-upstream eligible fruit (the list is sorted
        ascending by along-position) instead of a closer one the schedule cannot
        meet. The pre-scattered line handed the catch whatever single fruit the
        feeder presented and this rarely bit (`logs/p2_trace10`: handovers
        5-15 cm inside the lead left the close 8-15 cm behind the fruit); with
        several candidates it is the difference between 9/10 and 1/10. Callers
        that need the catch still only pass candidates at/above
        `_dynamic_select_floor()` (see `select_target`). The two-arm balance
        still applies to the indexed and policy paths.
        """
        if self._prefer_upstream:
            return ordered[-1][1]
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
    # Moving-pick scheduling (P2)
    # ------------------------------------------------------------------ #
    def _dynamic_pick_mode(self, openarm: bool, scripted: bool) -> bool:
        """Whether this attempt takes the fruit on the fly.

        **Shipped default (v7 directive): the OpenArm *scripted* line takes the
        fruit on the fly** - the belt never stops (`gate_open=0.0s`), which is
        the owner's standing ask ("still letting the belt stop?"). The dynamic
        line's measured rate is the Gate-19 **9/10** (15.8 s/attempt; the one
        failure is the A6 kiwi catch-window miss, `logs/fast/`), accepted and
        documented, and it is why the speed sweep reports per-leg cone/slip
        rather than a success delta.

        The environment overrides both ways: `FRUIT_DYNAMIC_PICK=1` forces the
        moving catch for either hand and either path; `FRUIT_DYNAMIC_PICK=0`
        restores the P1 indexed line (belt stopped at the station). The pad hand
        keeps its dynamic line. The OpenArm *policy* handover (`scripted=False`)
        follows `FRUIT_DYNAMIC_PICK`: with the env unset it keeps the P1 indexed
        primitive (the policy drives its own close; the hybrid canary was
        measured on that primitive), and with `FRUIT_DYNAMIC_PICK=1` it runs the
        same moving catch as the scripted line.
        """
        env = os.environ.get("FRUIT_DYNAMIC_PICK")
        if env is not None:
            return env == "1"
        return (openarm and scripted) or not openarm

    def _dynamic_pick_lead(self) -> float:
        """Upstream distance at which the moving pick is handed over [m].

        The catch does a *static* descent at the station (the world-frame speed
        budget the motion gate checks is payload-free and fruit-independent), so
        the hand needs the fruit to arrive as the descent ends. Handover happens
        far enough upstream that the descent - and the arm's own settling before
        it - fits in the fruit's travel time; the descent itself re-checks the
        timing and waits at hover if the estimate was generous.
        """
        speed = abs(self._belt_speed_estimate())
        overhead = float(os.environ.get("FRUIT_DYNAMIC_OVERHEAD_S", "0.4"))
        hover = float(os.environ.get("FRUIT_DYNAMIC_HOVER", os.environ.get("FRUIT_HOVER", "0.06")))
        v_max = float(os.environ.get("FRUIT_DYNAMIC_APPROACH_VMAX", os.environ.get("FRUIT_APPROACH_VMAX", "0.15")))
        t_desc = self._approach_duration(hover, v_max)
        margin = float(os.environ.get("FRUIT_DYNAMIC_LEAD_MARGIN", "0.03"))
        # The hover wait starts the descent `FRUIT_DYNAMIC_DESCEND_MARGIN` early,
        # so the handover has to be at least that much further upstream.
        descend_margin_s = float(os.environ.get("FRUIT_DYNAMIC_DESCEND_MARGIN", "0.15"))
        # Never demand more upstream room than the selector window has: if the
        # fruit is already inside, the hover wait absorbs the slack.
        return min(speed * (overhead + t_desc + descend_margin_s) + margin, 0.80)

    def _belt_speed_estimate(self) -> float:
        """Signed belt surface speed [m/s] - the encoder when it is meaningful."""
        belt = getattr(self.spawner, "belt", None)
        speed = float(getattr(belt, "encoder_speed", 0.0) or 0.0)
        if not np.isfinite(speed) or abs(speed) < 1e-6:
            speed = float(self.cfg.belt_speed)
        return speed

    @staticmethod
    def _approach_duration(distance: float, v_max: float, a_max: float | None = None) -> float:
        """Ticks the jerk-limited approach profile for `distance` will take [s]."""
        from .motion import TrajectoryLimits, jerk_limited

        limits = TrajectoryLimits.from_env(CONTROL_DT)
        limits.v_max = float(v_max)
        if a_max is not None:
            limits.a_max = float(a_max)
        positions, _, _ = jerk_limited(max(float(distance), 1e-3), limits)
        return len(positions) * CONTROL_DT

    def _two_line_catch_lead(self) -> float:
        """W2 clearance: how far upstream of its station the left catches [m].

        Mechanism: the moving catch tracks the fruit downstream through the
        close, hold and belt-break (~0.15-0.22 m of belt travel), so the left
        hand's dwell sweeps from its catch point down *across the right's
        station zone*. That sweep is the source of the sub-30 mm bands on the
        shipped W1 branch (`logs/w2/10_trace_before.log`: 13.9 mm at
        left=grip/right=close). Catching earlier moves the whole sweep
        upstream; the catch point is reach-limited: the left holds <= 6 mm to
        dy=+0.10, ~9 mm at +0.16 and 13-19 mm at +0.20 across the delivered
        band (`logs/w2/22_reach_catchpoint.log`, `logs/v3/60_...`). The
        measured best clearance state used +0.10 (left) and -0.03 (right,
        reach <= 9.4 mm at the band edge, `logs/w2/23_reach_right_deep.log`)
        plus the park bias, and reached min 38.9 mm / zero < 30 mm but at
        6/10 and 9.8 s/attempt (`logs/w2/60_trace_lead_park.log`) - it does
        not meet the W2 gate, so the **default is 0.0** (shipped behaviour)
        and the lever is kept for a later reach change. Scoped to the
        two-line; a global default would move the shipped single arm's catch
        (byte-frozen). `FRUIT_BIARM_CATCH_LEAD_L/R` override.
        """
        session = self._active_session
        if session is None or not getattr(session, "twoline", False):
            return 0.0
        if self.current_arm == "left":
            return float(os.environ.get("FRUIT_BIARM_CATCH_LEAD_L", "0.0"))
        return float(os.environ.get("FRUIT_BIARM_CATCH_LEAD_R", "0.0"))

    def _dynamic_aim(self, sample) -> np.ndarray:
        """Where the moving fruit will be when the static descent ends [m].

        The catch's descent is a *station-relative* move (see
        `_dynamic_pick_lead`): the hand goes to the pick station at the fruit's
        grasp height, and the fruit arrives under it. The aim therefore uses the
        fruit's measured lateral x (the belt jitters fruit sideways) and its
        *measured* centre height - a prolate fruit (a kiwi stands 23 % taller
        than its nominal diameter) would otherwise have the descent end inside
        its top. The two-line left adds `_two_line_catch_lead` upstream (W2
        clearance redesign, see there).
        """
        fruit = np.asarray(self.spawner.position(sample), dtype=float)
        return np.array(
            [
                float(fruit[0]),
                self.station_y_for(self.current_arm) + self._two_line_catch_lead(),
                float(fruit[2]),
            ]
        )

    def _pad_standoff(self, dynamic: bool = False, sample=None) -> float:
        """Jaw-centre to fingertip-pad standoff for a grasp command [m].

        `dynamic=True` selects the moving catch's own pad height; the default is
        the global `PAD_LIFT`, so an unset knob is a no-op. With
        `FRUIT_DYNAMIC_PAD_LIFT_FRAC` the standoff is additionally capped at that
        fraction of the fruit's diameter, which puts the pads on/near the widest
        section of a small conical fruit instead of above it.
        """
        finger_len = float(os.environ.get("FRUIT_FINGER_LEN", "0.060"))
        lift = self._dynamic_pad_lift if dynamic else PAD_LIFT
        if dynamic and sample is not None and self._dynamic_pad_lift_frac > 0.0:
            lift = min(lift, self._dynamic_pad_lift_frac * float(sample.diameter))
        return finger_len + lift

    def _dynamic_grip_point(self, sample) -> np.ndarray:
        """Jaw target of the moving catch's *grip* pose [m] (station, at height)."""
        return self._dynamic_aim(sample) + np.array([0.0, 0.0, self._pad_standoff(True, sample)])

    def _dynamic_hover_point(self, sample) -> np.ndarray:
        """Jaw target of the moving catch's hover, `FRUIT_DYNAMIC_HOVER` above grip [m]."""
        hover = float(
            os.environ.get("FRUIT_DYNAMIC_HOVER", os.environ.get("FRUIT_HOVER", "0.06"))
        )
        return self._dynamic_grip_point(sample) + np.array([0.0, 0.0, hover])

    def _x_seek_step(self, frozen_x: float, fruit_x: float) -> float:
        """One bounded cross-belt seek tick toward the fruit's measured x.

        Only reached with `FRUIT_DYNAMIC_X_TRACK_VMAX > 0`; the cap is what
        separates this from the raw every-tick tracker the P3-fix lane
        falsified - a steady walk at or below the cap is followed, an ejection
        that accelerates past it is not.
        """
        step = self._dynamic_x_track_vmax * CONTROL_DT
        return float(frozen_x + np.clip(fruit_x - frozen_x, -step, step))

    def _x_seek_allowed(
        self, vx: float, walk_latched: bool | None, hold: bool = False
    ) -> bool:
        """Whether the bounded x-seek may move on this tick.

        Per-tick gate (historical, `FRUIT_DYNAMIC_X_TRACK_LATCH=0`): follow only
        while the measured walk is below `FRUIT_DYNAMIC_X_TRACK_VX_MAX`. With the
        latch, the first close tick decides for the whole close/hold: a fruit
        already walking across the belt at contact keeps the per-tick gate
        through the *close* (a walking fruit is transport, and following it
        through the closing phase pushed the A6 kiwi off the belt in
        `s11_gate10_place15`), while a fruit that was still at contact gets the
        seek for the whole close/hold - its later drift is the squeeze-out the
        centring exists for, and the per-tick gate cut that centring off
        mid-close (A2/A8 held in `s6_xseek12` with the seek always on, lost in
        `s8_centre_place20` with the 0.05 gate).

        `hold=True` relaxes the walking gate: once the pads are frozen the fruit
        can no longer be pushed by the closing faces, and a kiwi that walks
        0.09-0.23 m/s (branch-dependent, `logs/dyn_v3c2/traces_s14`) must be
        followed or it walks out of the span during the 48-tick hold.
        """
        if self._dynamic_x_track_vx_max <= 0.0:
            return True
        if self._dynamic_x_track_latch and walk_latched is not None:
            if not walk_latched:
                return True
            if hold:
                return True
        return abs(vx) < self._dynamic_x_track_vx_max

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
        index = int(state["index"]) if "index" in state else None
        self.spawner.protect(index)
        try:
            result = self._run_impl(state, bin_index, lead_time, verbose)
        finally:
            # Safety net for the two-line pre-pose serialization: if the attempt
            # errored before reaching its hover, the lock is still held here.
            self._release_prepose()
            # Clear the collector's per-attempt budget before any park/feed
            # step (a timed-out attempt must not re-raise on the way out).
            self._episode_deadline = None
            self.spawner.unprotect(index)
            self._biarm_clear_streak = 0
            # A failed attempt returns before the release block, which is the
            # only place that clears `sample.held`; a stale held flag blocks the
            # feeder cursor (release_next skips held/protected fruit) forever.
            if index is not None:
                for candidate in self.spawner.samples:
                    if candidate.index == index:
                        candidate.held = False
                        break
        self.note_result(result)
        return result

    # ------------------------------------------------------------------ #
    # Bimanual (pipelined shared-station) scheduling - F2
    # ------------------------------------------------------------------ #
    def bimanual_enabled(self) -> bool:
        """Whether the scripted line should run the two-arm pipeline.

        **Default off while F2 measures it.** The shipped v7/F1 default is the
        single-arm dynamic line and its acceptance fingerprint is the recorded
        reference; flipping the default is the integration phase's (G) decision.
        `FRUIT_BIARM=1` enables the pipeline explicitly.

        Only the scripted OpenArm dynamic line qualifies: the indexed path stops
        the shared belt (`belt.stop()`), the pad hand keeps its own measured
        line, and the policy handover drives its own primitive - none of those
        can share a station between two concurrent attempts.
        """
        env = os.environ.get("FRUIT_BIARM")
        if env != "1" or self._active_session is not None:
            return False
        kind = getattr(self.grippers.get("left"), "kind", "")
        if kind != "openarm":
            say(f"[biarm] FRUIT_BIARM=1 ignored: hand is {kind!r}, not openarm")
            return False
        if not self._dynamic_pick_mode(openarm=True, scripted=True):
            say("[biarm] FRUIT_BIARM=1 ignored: the line is the indexed primitive")
            return False
        if self.recorder is not None:
            # W3: the collector records on the two-line branch too. The
            # per-episode buffers are thread-local (`EpisodeRecorder`, W3) and
            # `_tick_frame` bridges `RenderingManager.render()` to the main
            # thread under the session, so the recorder runs off-thread safely.
            say("[biarm] recorder attached; two-line episodes are recorded per arm")
        return True

    def _station_prepose_target(self, arm: str) -> np.ndarray | None:
        """This arm's station-specific pre-pose joints, or None (shared config).

        None on every single-arm / shared-station path (byte-identical to the
        shipped line) and for an arm whose station solve did not converge.
        """
        key = (self.station_y_for("left"), self.station_y_for("right"))
        return self._station_grasp.get(key, {}).get(arm)

    def _prepare_two_line_stations(self) -> None:
        """Pre-solve each arm's pre-pose configuration at its own station.

        The shipped pre-pose blends to the calibrated `grasp` joint config,
        whose jaw sits at the *shared* station (y ~ 0). On the two-line
        scheduler the right arm's station is 0.10 m downstream (the default
        separation), and a blend through the shared configuration would sweep
        the right hand through the left arm's station - which is otherwise a
        live work volume for the whole cycle. Each arm therefore pre-poses at a
        station-specific configuration, solved once here from the calibrated
        `grasp` seed (the same seed `scripts/174_station_reach.py` uses;
        measured residuals are printed and become part of the run log).

        Runs before the workers are started, with both arms at ready, and
        returns each arm to ready before touching the other: the two stations
        are 0.10 m apart but the *seeds* are the same point, so the arms must
        never be calibrated at once. The configuration is cached per station
        pair, so later batches in one process skip the solve. If an arm's solve
        does not converge (`FRUIT_BIARM_STATION_TOL`, default 10 mm) it keeps
        the shared configuration and the pre-pose lock serializes the two
        approaches.
        """
        key = (self.station_y_for("left"), self.station_y_for("right"))
        if key in self._station_grasp:
            return
        solved: dict[str, np.ndarray] = {}
        for side in ("left", "right"):
            target_y = self.station_y_for(side)
            if abs(target_y - float(self.cfg.pick_y)) < 1e-9:
                continue  # shared station: the calibrated config is correct
            arm = self.arms[side]
            arm.set_gripper(arm.OPEN)
            arm.teleport_joints(self._pose(side, "grasp"))
            hold = top_down_quaternion(os.environ.get("FRUIT_HAND_AXIS", "x"))
            if side == "left":
                hold = mirror_across_xz(hold)
            arm.hold_quaternion = hold
            target = np.array(
                [self.cfg.pick_x, target_y, self.belt_top + self.cfg.grasp_clearance],
                dtype=float,
            )
            config, residual = arm.solve_to(target, iterations=400, tolerance=0.006)
            arm.hold_quaternion = None
            say(
                f"[biarm] station {side} y={target_y:+.3f}: pre-pose solve "
                f"residual {residual * 1000:.1f} mm"
            )
            if residual <= float(os.environ.get("FRUIT_BIARM_STATION_TOL", "0.010")):
                solved[side] = np.asarray(config, dtype=float).copy()
            else:
                say(
                    f"[biarm] station {side}: solve residual over tolerance; the "
                    "shared grasp config is kept for this arm"
                )
            # Back to ready before the other arm is calibrated (shared seed).
            # Step physics explicitly and keep the pump: `update_app(steps=N)`
            # is not a fixed step (AGENTS section 3b) and this setup is a
            # scripted path, so the old `update_app(steps=10)` could advance
            # 9-10 ticks from run to run.
            from isaacsim.core.simulation_manager import SimulationManager

            self.go_ready(side)
            SimulationManager.step(steps=10)
            app_utils.update_app(steps=0)
        self._station_grasp[key] = solved

    def _two_line_prepose_locked(self) -> bool:
        """Whether the two-line approaches must be serialized by the pre-pose lock.

        Only when an arm whose station is *off* the calibrated pick point could
        not be given a station-specific pre-pose configuration: its blend then
        still ends at the shared grasp point (y ~ 0), which lies inside the other
        arm's station volume, so the two approaches must not run at once. In the
        normal case (every off-centre station solved) each arm's approach stays
        on its own side of the belt and the lock is unnecessary.
        """
        key = (self.station_y_for("left"), self.station_y_for("right"))
        solved = self._station_grasp.get(key, {})
        for side in ("left", "right"):
            if abs(self.station_y_for(side) - float(self.cfg.pick_y)) > 1e-9:
                if solved.get(side) is None:
                    return True
        return False

    def two_line_enabled(self) -> bool:
        """Whether the v9/V2 two-line scheduler is on for `FRUIT_BIARM=1`.

        Default **off**, per the V2 pre-registration's decision rule
        (`logs/v2/PREREGISTRATION.md`): the two-line's placed/min gain was 1.08x,
        short of the 1.25x bar for replacing the shared-station meaning of
        `FRUIT_BIARM=1`, so `FRUIT_BIARM=1` stays the F2 shared-station pipeline
        and the two-line is the explicit opt-in `FRUIT_BIARM_TWOLINE=1`. When on,
        each arm owns its own pick station on the shared belt
        (`FRUIT_BIARM_STATION_L/R`, default 0.0 / -0.10).
        """
        return os.environ.get("FRUIT_BIARM_TWOLINE", "0") == "1"

    def run_bimanual(self, attempts: int) -> list[EpisodeResult]:
        """Run a batch of up to `attempts` scripted attempts on two arms.

        Two modes:

        * **two-line (`FRUIT_BIARM_TWOLINE=1`, opt-in)**: each arm owns a pick
          station on the shared belt; the left catches at `FRUIT_BIARM_STATION_L`
          (upstream, default 0.0; the W2 +0.05/+0.08 widening screens are
          documented in the comment below and `logs/w2/RESULT.md`) and the
          right at `FRUIT_BIARM_STATION_R` (downstream, -0.10). Both arms
          select at their own station with the **W3 pure grade routing** (left
          = grade A only, right = grade B only, C never selected;
          `FRUIT_GRADE_ROUTING=0` restores the V2 grade preference with the
          any-grade fallback), exclude the other arm's protected target, and
          run their attempts concurrently; only the approach phase is
          serialized when a station-specific pre-pose solve failed.
          Geometry/semantics are pre-registered in
          `logs/v2/PREREGISTRATION.md`; the rate and clearance are in
          `logs/v2/RESULT.md` (pre-W2) and `logs/w2/RESULT.md` (W2 redesign).
        * **shared station (default, F2)**: the two arms take turns owning one
          station (acquire -> fresh select -> dynamic attempt) until the batch
          budget is spent.

        One session spans the whole batch (not one session per pair), so a
        carry never idles the other arm until the previous pair finishes.

        Returns the attempts that ran (sorted by start time). The caller keeps
        the single-arm loop for the policy and collector paths.
        """
        if not self.bimanual_enabled():
            return []
        trace = os.environ.get("FRUIT_BIARM_TRACE", "0") == "1"
        two_line = self.two_line_enabled()
        saved_stations = dict(self.station_y)
        saved_recycle = float(getattr(self.spawner, "recycle_y", self.cfg.pick_y))
        if two_line:
            # W2 clearance redesign (2026-10-09, `logs/w2/RESULT.md`): the
            # shipped left station (y=0.0, 0.10 m upstream of the right's
            # -0.10) measured **min 13.9 mm** link-origin separation on the
            # shipped W1 branch (t=95.8-96.3 s, left=grip/right=close) against
            # the F2 45 mm / zero-under-30 convention. The screens: moving the
            # left station to +0.05 cleared the dwell pairs (33.8 mm, zero<30)
            # but rescheduled the branch to 6/10; +0.08 landed 2.3 mm / 5/10.
            # The mechanism is the moving catch's belt-riding dwell (~0.22 m,
            # longer than the reachable station separation: the left's
            # upstream catch is reach-clean only to +0.10), so the station
            # default stays 0.0 (shipped) and the measured levers
            # (`FRUIT_BIARM_CATCH_LEAD_L/R`, `FRUIT_BIARM_PARK_BIAS`,
            # `FRUIT_BIARM_PARK_GATE`, `FRUIT_BIARM_START_GAP`) are all
            # default-off - the best clearance state (38.9 mm, zero<30) cost
            # the rate (6/10, 9.8 s/attempt). `FRUIT_BIARM_STATION_L/R` still
            # override.
            left_y = float(os.environ.get("FRUIT_BIARM_STATION_L", "0.0"))
            right_y = float(os.environ.get("FRUIT_BIARM_STATION_R", "-0.10"))
            self.station_y = {"left": left_y, "right": right_y}
            # A mid-belt recycle (the feeder's least-preferred path) must not
            # steal a fruit the downstream station can still catch.
            self.spawner.recycle_y = min(left_y, right_y)
            say(
                f"[biarm] two-line scheduler: left station y={left_y:+.3f}, "
                f"right station y={right_y:+.3f} "
                f"(separation {left_y - right_y:.3f} m)"
            )
            # One-time: solve each arm's station-specific pre-pose config (the
            # two approaches must not both sweep through the shared grasp pose).
            self._prepare_two_line_stations()
        session = CoopSession(["left", "right"], trace=trace)
        session.twoline = two_line
        #: W3 capture token: on the wave-supply two-line scenario both arms
        #: catch the same burst, and the measured both-hands band collapsed to
        #: 1.9 mm link-origin separation / 710 samples <30 mm
        #: (`logs/w3/10_trace_waves.log`). The token serializes the *capture
        #: window* (pre-pose -> payload clear): it removes the both-at-station
        #: overlap (min 17.4 mm, 118 samples <30 mm) but the measured branch
        #: collapses (2/10, 62.9 s/success, `logs/w3/24_token_trace.log`), so
        #: the shipped default is **off**; `FRUIT_BIARM_CAPTURE_TOKEN=1` opts
        #: in (the right fix needs a schedule that keeps the rate - W4).
        capture_env = os.environ.get("FRUIT_BIARM_CAPTURE_TOKEN")
        if capture_env is not None:
            session.capture_enabled = bool(two_line and capture_env == "1")
        else:
            session.capture_enabled = False
        #: True when an off-centre station could not get a station-specific
        #: pre-pose config; the worker then serializes the approach phases.
        session.prepose_locked = bool(two_line and self._two_line_prepose_locked())
        if two_line:
            say(
                "[biarm] two-line pre-pose lock: "
                + ("serialize the approaches" if session.prepose_locked
                   else "not needed (station-specific pre-poses)")
            )
        session.after_step = self._biarm_after_step
        session.budget = max(1, int(attempts))
        session.reserved = 0
        #: W2 clearance: sim time each arm last started an attempt. The start
        #: gate (`FRUIT_BIARM_START_GAP`) keeps the two arms' station dwells
        #: (close/hold/belt-break, where each hand rides the belt through the
        #: other's station zone) out of phase. Access is serialized by the
        #: single run permit; no lock needed.
        session.attempt_start: dict[str, float] = {}
        #: W2: whether each arm's held payload is clear of its station box
        #: (published per tick by `_biarm_after_step`; read by the park gate).
        session.payload_clear: dict[str, bool] = {"left": True, "right": True}
        self._active_session = session
        try:
            with session:
                threads = [
                    threading.Thread(
                        target=self._biarm_worker,
                        args=(session, arm, 0 if arm == "left" else 1),
                        name=f"biarm-{arm}",
                        daemon=True,
                    )
                    for arm in ("left", "right")
                ]
                session.run(threads)
            results = list(session.results)
        finally:
            self._active_session = None
            if two_line:
                self.station_y = saved_stations
                self.spawner.recycle_y = saved_recycle
        results.sort(key=lambda item: float(item.sim_start))
        timed_out = int(getattr(session, "timed_out", 0))
        if timed_out:
            say(
                "[biarm] attempt timeouts (skipped, belt never stopped, fruits "
                f"retryable): {timed_out}"
            )
        if results:
            # Throughput denominator: the simulated-clock span from the first
            # attempt's start to the last attempt's end. Per-attempt spans
            # overlap, so summing them would double-count.
            span = max(item.sim_end for item in results) - min(
                item.sim_start for item in results
            )
            self.stats["sim_time"] += max(0.0, span)
        if two_line and results:
            # W3 grade routing report: one line per batch, per arm, so the
            # purity claim is read off the run that produced the rate (and the
            # `scripts/175_twoline_report.py` parser can quote it). `C picked`
            # must be 0 under pure routing.
            per_arm: dict[str, dict[str, int]] = {"left": {}, "right": {}}
            for item in results:
                per_arm[item.arm][item.grade] = per_arm[item.arm].get(item.grade, 0) + 1
            def _fmt(counts: dict[str, int]) -> str:
                return " ".join(f"{g}={counts.get(g, 0)}" for g in ("A", "B", "C"))
            c_picked = sum(1 for item in results if item.grade == "C")
            say(
                f"[biarm] grade routing: left {_fmt(per_arm['left'])}; "
                f"right {_fmt(per_arm['right'])}; C picked={c_picked}; "
                f"pure={'on' if self._pure_grade_routing() else 'off'}"
            )
        self.stats["biarm_sessions"] = int(self.stats.get("biarm_sessions", 0)) + 1
        self._biarm_trace_report(session)
        return results

    def _release_prepose(self) -> None:
        """Release the two-line pre-pose lock if this slot holds it (idempotent).

        Called at the end of the hover move in `_run_impl` and again from the
        worker's and attempt's `finally` blocks; the second call is a no-op.
        """
        lock = self._prepose_lock
        if lock is not None:
            self._prepose_lock = None
            lock.release()

    def _biarm_clear_slot(self, arm: str) -> None:
        """Reset one attempt thread's per-slot state before it takes a station.

        A failed attempt leaves its thread-local `current_sample`/grip state and,
        for the openarm hand, can leave `sample.held` set (the release block is
        the only place that clears it); a later no-fruit slot must not read that
        stale state and "release" the station the moment it takes it.
        """
        self._closed_gap[arm] = None
        self._biarm_clear_streak = 0
        sample = self.current_sample
        if sample is not None:
            sample.held = False
        self.current_sample = None

    def _biarm_worker(self, session: CoopSession, arm: str, bin_index: int) -> None:
        """One attempt thread: take station slots until the batch budget is spent.

        Two-line mode: each arm owns its station; the worker takes the
        session's pre-pose lock (serializing only the approach, which converges
        on the shared grasp configuration), selects a target at its own
        station excluding the other arm's protected fruit, runs the attempt
        (which releases the pre-pose lock once the hover is reached), and
        parks. Shared-station mode: the F2 protocol, unchanged.
        """
        relay = session.relay
        relay.register(arm)
        relay.enter()
        gap_ticks = max(0, int(os.environ.get("FRUIT_BIARM_GAP_TICKS", "30")))
        two_line = bool(getattr(session, "twoline", False))
        try:
            while True:
                self._biarm_clear_slot(arm)
                # The reservation is atomic: only the token holder runs Python,
                # and no step call happens between the check and the increment.
                if session.reserved >= session.budget:
                    break
                session.reserved += 1
                ran = False
                try:
                    if two_line and session.prepose_locked:
                        # Only when an arm's station could not get its own
                        # pre-pose configuration: the two approaches converge on
                        # the shipped shared grasp configuration (both jaws near
                        # y ~ 0) and must not cross at once. `_run_impl` releases
                        # the lock after the hover; the normal two-line case
                        # solves per-station pre-poses and never takes it.
                        session.prepose.acquire(relay)
                        self._prepose_lock = session.prepose
                    elif not two_line:
                        session.station.acquire(relay)
                    if two_line and session.capture_enabled:
                        # W3 capture token: the wave supply sends both arms at
                        # the same burst; the token keeps their capture windows
                        # (pre-pose -> payload clear) from overlapping. Acquired
                        # before selection so the chosen fruit is still ahead of
                        # the hover when the wait ends, released at payload-clear
                        # (`_biarm_after_step`) or in the finally below.
                        session.capture.acquire(relay)
                    say(f"[biarm] {arm}: station acquired at t={self._sim_time():.1f}s")
                    if two_line:
                        # W2 clearance: keep the two arms' station dwells out of
                        # phase. The moving catch rides the belt through the
                        # close/hold/belt-break, so the left's hand sweeps across
                        # the right's station zone (and vice versa); when the two
                        # sweeps coincide the measured link separation collapses
                        # to 2-34 mm (`logs/w2/10/30/40`). A minimum gap between
                        # the arms' attempt *starts* (the dwell follows the start
                        # by prepose+hover+descent) is the deterministic
                        # separator; the hover absorbs the wait, and the target is
                        # selected *after* the gate, so nothing is half-committed
                        # when the arm yields. The gate check + selection + record
                        # is one run-permit segment (no step call between them),
                        # so the two workers cannot both pass on the first pair.
                        # Default 0 keeps the shipped schedule;
                        # `FRUIT_BIARM_START_GAP` (seconds of sim time) enables
                        # it - measured value in `logs/w2/RESULT.md`.
                        start_gap = float(os.environ.get("FRUIT_BIARM_START_GAP", "0.0"))
                        if start_gap > 0.0:
                            other = "right" if arm == "left" else "left"
                            waited = 0
                            while True:
                                previous = session.attempt_start.get(other)
                                if (
                                    previous is None
                                    or self._sim_time() - previous >= start_gap
                                ):
                                    break
                                self._step_sim(1)
                                waited += 1
                            if waited:
                                ago = (
                                    self._sim_time() - previous
                                    if previous is not None
                                    else float("nan")
                                )
                                say(
                                    f"[biarm] {arm}: start gate waited {waited} ticks "
                                    f"(other started {ago:.1f}s ago)"
                                )
                        state = self.select_target(
                            self.spawner.state(),
                            station_y=self.station_y_for(arm),
                            prefer_lane=bin_index,
                            exclude=set(self.spawner.protected_indices),
                            min_lead_s=float(
                                os.environ.get("FRUIT_BIARM_SELECT_LEAD_S", "1.4")
                            ),
                        )
                        if start_gap > 0.0 and state is not None:
                            # Record only real attempts: a starved slot must not
                            # delay the other arm (the batch-start priming loops
                            # through several).
                            session.attempt_start[arm] = self._sim_time()
                    else:
                        self._biarm_wait_station_clear(session, arm)
                        state = self.select_target(
                            self.spawner.state(),
                            lane=bin_index,
                            min_lead_s=float(
                                os.environ.get("FRUIT_BIARM_SELECT_LEAD_S", "1.4")
                            ),
                        )
                    if state is None:
                        # Nothing this arm can take right now; give the slot
                        # back, feed the line and try again later.
                        session.reserved -= 1
                        if two_line and session.capture_enabled:
                            # Do not hold the capture token through a starved
                            # slot: the other arm may have work.
                            session.capture.release()
                        say(f"[biarm] {arm}: no eligible fruit; station released")
                    else:
                        try:
                            result = self.run(state, bin_index)
                        except AttemptTimeout as exc:
                            # Collector watchdog: skip this attempt, keep the
                            # line running (never stopped, never indexed), and
                            # let this worker take the next fruit. The fruit
                            # recycles; the recorder discards the partial clip.
                            session.timed_out = (
                                int(getattr(session, "timed_out", 0)) + 1
                            )
                            result = EpisodeResult(
                                sample_index=int(state["index"]),
                                category=str(state.get("category", "")),
                                grade=str(state.get("grade", "")),
                                arm=arm,
                                notes=[f"attempt timed out: {exc}"],
                            )
                            say(
                                f"[biarm] {arm}: attempt timed out ({exc}); "
                                "skipped, line still running"
                            )
                        session.results.append(result)
                        ran = True
                        # Print the attempt as it completes, so a killed batch
                        # still leaves a parseable per-attempt record.
                        say(
                            f"[biarm] result {arm} index={result.sample_index} "
                            f"{result.category} grasped={result.grasped} "
                            f"placed={result.placed} lift={result.peak_lift:+.3f} "
                            f"force={result.max_tactile_force:.2f} "
                            f"sim={result.sim_span:.1f}s notes={result.notes}"
                        )
                finally:
                    self._release_prepose()
                    self._biarm_clear_slot(arm)
                    self._biarm_park(arm)
                    if not two_line:
                        session.station.release()
                    elif session.capture_enabled:
                        # Safety net: a failed attempt that never reached its
                        # payload-clear release must not wedge the other arm.
                        session.capture.release()
                if not ran:
                    # Starved lane: release, feed once and let the belt advance;
                    # the release schedule advances at attempt boundaries only
                    # (the single-arm line's cadence), so the station does not
                    # face a permanently packed queue.
                    self.spawner.update(self._sim_time())
                    for _ in range(max(60, gap_ticks)):
                        self._step_sim(1)
                    continue
                # A short feed gap between attempts, like the driver's between
                # loops: recycle line traffic and let the feeder release fruit.
                self.spawner.update(self._sim_time())
                for _ in range(gap_ticks):
                    self._step_sim(1)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the main thread
            session.errors.append(exc)
        finally:
            self._release_prepose()
            relay.release()

    def _biarm_park(self, arm: str) -> None:
        """Return a finished attempt's arm to ready, gated on the other arm.

        `_ready_transit` sweeps the hand up and back toward the body, i.e.
        through the station volume, and the single-arm line does it with the
        cell empty. Here the *other* arm may be using the station (`run 07`: the
        right arm's return re-blended its wrist while the left arm was carrying,
        and the left payload was knocked out of the jaws mid-place). The return
        therefore waits until the other arm neither owns the station nor carries
        a payload, stepping physics in place meanwhile. An arm already at ready
        returns immediately - the starved no-fruit slots depend on that.
        """
        try:
            ready = self._pose(arm, "ready")
            if float(np.max(np.abs(self.arms[arm].joint_positions() - ready))) <= self.TRANSIT_TOL:
                return
            other = "right" if arm == "left" else "left"
            limit = int(os.environ.get("FRUIT_BIARM_PARK_WAIT", "1200"))
            # Default-off diagnostic (`FRUIT_BIARM_PARK_TRACE=1`): when the
            # return starts, when the gate opens and how long it waited. The
            # clearance analysis needs the wait window to attribute a near-miss
            # band to "frozen at the end-of-attempt pose" rather than guessing
            # from the cycle marks. Pure reporting - no control input.
            trace = os.environ.get("FRUIT_BIARM_PARK_TRACE", "0") == "1"
            if trace:
                say(
                    f"[biarm] {arm}: park wait start t={self._sim_time():.1f}s "
                    f"(closed_gap[{other}]={'set' if self._closed_gap.get(other) is not None else 'clear'})"
                )
            waited = 0
            session_ctx = self._active_session
            two_line_ctx = session_ctx is not None and getattr(session_ctx, "twoline", False)
            for _ in range(limit):
                session = self._active_session
                owner = session.station.owner if session is not None else None
                station_busy = owner is not None and owner != threading.get_ident()
                other_gripping = self._closed_gap.get(other) is not None
                # W2 lever (default off): on the two-line, a payload that has
                # left its station box (lift/place/release) cannot be reached
                # by the return any more, so the gate can open then instead of
                # at the other arm's release. The shipped F2 rule waits for the
                # whole grip. `FRUIT_BIARM_PARK_GATE=1` enables the
                # payload-clear reading (published by `_biarm_after_step`).
                if two_line_ctx and os.environ.get("FRUIT_BIARM_PARK_GATE", "0") == "1":
                    other_blocked = other_gripping and not bool(
                        session.payload_clear.get(other, True)
                    )
                else:
                    other_blocked = other_gripping
                if not station_busy and not other_blocked:
                    break
                self._step_sim(1)
                waited += 1
            else:
                say(
                    f"[biarm] {arm}: the other arm was busy for {limit} ticks; "
                    "parking anyway"
                )
            if trace:
                say(
                    f"[biarm] {arm}: park moving t={self._sim_time():.1f}s "
                    f"(waited {waited} ticks)"
                )
            self.go_ready(arm)
            # W2 clearance lever (default **off**): bias the idle hand outward
            # (left +Y, right -Y). The other arm's place carry crosses the
            # shipped ready pose (y=+-0.055); the measured 16 mm band at
            # t=119.9-120.35 in `logs/w2/50_trace_gap4.log` is the left carry
            # vs the parked right `link6`, and the bias removes it (the
            # `logs/w2/60_...` run has no park band). It is not shipped on
            # because it does not by itself meet the 45 mm bar;
            # `FRUIT_BIARM_PARK_BIAS` (metres) enables it.
            session = self._active_session
            if session is not None and getattr(session, "twoline", False):
                bias = float(os.environ.get("FRUIT_BIARM_PARK_BIAS", "0.0"))
                if bias > 0.0:
                    self._park_bias(arm, bias if arm == "left" else -bias)
            if trace:
                say(f"[biarm] {arm}: park done t={self._sim_time():.1f}s")
        except Exception as exc:  # noqa: BLE001 - parking must not mask the result
            say(f"[biarm] {arm}: park after attempt failed ({exc!r})")

    def _park_bias(self, side: str, dy: float, ticks: int = 80) -> None:
        """Move a parked two-line arm's jaw `dy` in y (outward) and hold there.

        Position-only IK with the posture-capped step; idempotent (stops once
        the jaw is within 5 mm). The drive target is left at the biased pose,
        so the idle arm holds the clear position until its next pre-pose.
        """
        arm = self.arms[side]
        self._catch_up_drive(side)
        goal_y = float(np.asarray(arm.jaw_centre(), dtype=float)[1]) + float(dy)
        previous = arm.max_step
        arm.max_step = min(
            previous, float(os.environ.get("FRUIT_READY_LIFT_STEP", "0.04"))
        )
        try:
            for _ in range(max(1, int(ticks))):
                jaw = np.asarray(arm.jaw_centre(), dtype=float)
                if abs(float(jaw[1]) - goal_y) <= 0.005:
                    break
                goal = jaw + np.array([0.0, goal_y - float(jaw[1]), 0.0])
                arm.ik_step(arm.tcp_target_for_jaw(goal))
                self._step_sim(1)
                self._tick_frame()
        finally:
            arm.max_step = previous
        arm.sync_command_to_measured()

    def _biarm_wait_station_clear(self, session: CoopSession, arm: str) -> None:
        """Wait for the other arm to leave the station box before pre-posing.

        The station lock already hands over only after the previous payload
        cleared the box; this additionally watches the *hand*, which trails the
        payload out of the box. A failed attempt parks its arm at ready in the
        worker's `finally`, so this normally passes within a few ticks.
        """
        other = "right" if arm == "left" else "left"
        limit = int(os.environ.get("FRUIT_BIARM_CLEAR_WAIT", "600"))
        for _ in range(limit):
            if not self._biarm_arm_inside_station(other):
                return
            self._step_sim(1)
        say(
            f"[biarm] warning: {other} arm still inside the station box after "
            f"{limit} ticks; proceeding"
        )

    def _biarm_arm_inside_station(self, side: str) -> bool:
        """Whether one arm's measured jaw centre is inside *its own* station box.

        The box is deliberately tighter than the ready-pose offsets: the two
        ready jaws sit at y = +-0.055 m, 55 mm apart, and coexist by design in
        the shipped line, so they must count as *clear*. On the two-line
        scheduler the side's box sits at its own station (`station_y_for`).
        """
        jaw = np.asarray(self.arms[side].jaw_centre(), dtype=float)
        return bool(
            abs(float(jaw[1]) - self.station_y_for(side))
            <= float(os.environ.get("FRUIT_BIARM_GUARD_Y", "0.045"))
            and float(jaw[0]) <= float(os.environ.get("FRUIT_BIARM_GUARD_X", "0.55"))
            and float(jaw[2]) <= float(os.environ.get("FRUIT_BIARM_GUARD_Z", "1.45"))
        )

    def _biarm_payload_clear(self, sample) -> bool:
        """Whether the carried payload has left the station box.

        Only the lateral/forward terms are used: during the vertical belt-break
        the payload is directly above the station at z ~ 1.4-1.45 and the other
        arm must not descend under it, so a height criterion would release the
        station too early.
        """
        pos = np.asarray(self.spawner.position(sample), dtype=float)
        return bool(
            abs(float(pos[1]) - self.station_y_for(self.current_arm))
            > float(os.environ.get("FRUIT_BIARM_CLEAR_Y", "0.28"))
            or float(pos[0]) > float(os.environ.get("FRUIT_BIARM_CLEAR_X", "0.52"))
        )

    def _biarm_after_step(self) -> None:
        """Per-tick bimanual bookkeeping, called from `_step_sim`.

        Station release: the holder gives the station up once the carried
        payload has been clear of the station box for
        `FRUIT_BIARM_CLEAR_TICKS` consecutive ticks (transients must not hand it
        over mid-crossing). The two-line scheduler owns no shared station, so
        that block is inert there.
        Capture token (W3, two-line wave scenario): when enabled, the token is
        released the first tick the holder's payload has cleared its station
        box, so the other arm's capture starts while the holder carries/places.
        Clearance trace: with `FRUIT_BIARM_TRACE=1`, the minimum inter-arm
        link-origin distance is sampled - link reads are the invasive class, so
        the trace is default off.
        """
        session = self._active_session
        if session is None:
            return
        if session.trace:
            self._biarm_trace_sample(session)
        if getattr(session, "twoline", False) and os.environ.get(
            "FRUIT_BIARM_PARK_GATE", "0"
        ) == "1":
            # W2 lever (default off): publish whether this arm's payload is
            # clear of its station box, so the other arm's park gate
            # (`_biarm_park`) can open while the payload is over the output
            # belt - the shipped gate waits for the whole grip/release, which
            # cost the left 3-4 s per turn once the W2 schedule shifted
            # (`logs/w2/60_...` park waits 3.2/4.4 s). Off by default: the
            # per-tick position read is the instrumentation class (AGENTS
            # section 2) and the lever did not meet the W2 gate.
            sample_now = self.current_sample
            if sample_now is not None and self._closed_gap.get(self.current_arm) is not None:
                session.payload_clear[self.current_arm] = bool(
                    self._biarm_payload_clear(sample_now)
                )
            else:
                session.payload_clear[self.current_arm] = True
        if getattr(session, "capture_enabled", False):
            # W3 capture token: release once this attempt's payload has cleared
            # its station box (during the lift), so the other arm may start its
            # approach while this arm carries and places. A failed attempt that
            # never gets here releases in the worker's finally.
            sample_now = self.current_sample
            if (
                sample_now is not None
                and self._closed_gap.get(self.current_arm) is not None
                and self._biarm_payload_clear(sample_now)
            ):
                session.capture.release()
        if not session.station.held_by_current():
            self._biarm_clear_streak = 0
            return
        sample = self.current_sample
        if sample is None or self._closed_gap.get(self.current_arm) is None:
            # No payload in the hand yet (or any more): the fruit's position on
            # the belt says nothing about station occupancy. Only a *held*
            # payload that has left the box frees the station.
            self._biarm_clear_streak = 0
            return
        if self._biarm_payload_clear(sample):
            self._biarm_clear_streak += 1
        else:
            self._biarm_clear_streak = 0
        if self._biarm_clear_streak >= int(os.environ.get("FRUIT_BIARM_CLEAR_TICKS", "5")):
            session.station.release()
            self._biarm_clear_streak = 0
            say(f"[biarm] station handed over by {self.current_arm} (payload clear)")

    def _biarm_trace_sample(self, session: CoopSession) -> None:
        """Sample the minimum inter-arm link-origin separation (opt-in trace).

        Uses USD world transforms, not `RigidPrim.get_world_poses`: the physics
        tensor read back-syncs per call and measured ~30 s per 20-link sample
        (the first trace run spent 13 minutes in one pre-pose). The USD xform
        the renderer uses is the same physics state (`_fingertip_lowest_z`
        already reads it for the lowered place) and costs microseconds. The
        trace is still default off: it is a report, not a control input.
        """
        every = max(1, int(os.environ.get("FRUIT_BIARM_TRACE_EVERY", "2")))
        count = getattr(session, "_trace_ticks", 0) + 1
        session._trace_ticks = count
        if count % every:
            return
        from pxr import Usd, UsdGeom

        paths = getattr(self, "_biarm_link_paths", None)
        if paths is None:
            paths = {}
            for side in ("left", "right"):
                names = list(self.arms[side].robot.link_names)
                link_paths = self.arms[side].robot.link_paths
                if link_paths and isinstance(link_paths[0], (list, tuple)):
                    link_paths = link_paths[0]
                entries = []
                for index, name in enumerate(names):
                    # `openarm_left_right_finger` contains both `_left_` and
                    # `_right_`, so the side must be a name *prefix*; the
                    # substring filter cross-links the arms' opposite fingers
                    # (the first trace reported 0 mm: both sides resolved to
                    # `openarm_left_right_finger`).
                    if not str(name).startswith(f"openarm_{side}_"):
                        continue
                    path = link_paths[index]
                    if isinstance(path, (list, tuple)):
                        path = path[0]
                    entries.append((name, str(path)))
                paths[side] = entries
            self._biarm_link_paths = paths
        stage = self.scene.stage
        names: dict[str, list[str]] = {"left": [], "right": []}
        poses: dict[str, list[np.ndarray]] = {"left": [], "right": []}
        for side in ("left", "right"):
            for name, path in paths[side]:
                prim = stage.GetPrimAtPath(path)
                if not prim.IsValid():
                    continue
                matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
                    Usd.TimeCode.Default()
                )
                positions = np.array(matrix).reshape(4, 4).T[0:3, 3]
                poses[side].append(np.asarray(positions, dtype=float))
                names[side].append(name)
        if not poses["left"] or not poses["right"]:
            return
        right = np.asarray(poses["right"], dtype=float)
        best = (float("inf"), "", "")
        for index, left_pos in enumerate(poses["left"]):
            distances = np.linalg.norm(right - np.asarray(left_pos, dtype=float), axis=1)
            nearest = int(np.argmin(distances))
            if float(distances[nearest]) < best[0]:
                best = (float(distances[nearest]), names["left"][index], names["right"][nearest])
        # W2: record the two hands' and tool tips' origins alongside the minimum
        # (the pairs that drive the bar are hand/finger links). Without them a
        # near-miss band can only be attributed to a *phase*; with them the
        # mechanism can be read in world y (the left's downstream belt-riding
        # dwell crossing the right's station zone).
        probe: dict[str, list[float]] = {}
        for side in ("left", "right"):
            for name, pos in zip(names[side], poses[side]):
                if name in (f"openarm_{side}_hand", f"openarm_{side}_ee_tcp"):
                    probe[name] = [round(float(value), 5) for value in pos]
        session.trace_rows.append(
            (float(self._sim_time()), best[0], best[1], best[2], probe)
        )

    def _biarm_trace_report(self, session: CoopSession) -> None:
        """Print (and optionally persist) the clearance trace of one pair-run."""
        if not session.trace:
            return
        rows = session.trace_rows
        if not rows:
            say("[biarm] clearance trace: no samples")
            return
        best = min(rows, key=lambda row: row[1])
        say(
            f"[biarm] clearance trace: min link separation {best[1] * 1000:.0f} mm "
            f"at t={best[0]:.2f}s ({best[2]} vs {best[3]}), {len(rows)} samples"
        )
        path = os.environ.get("FRUIT_BIARM_TRACE_FILE")
        if path:
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(path, "a", encoding="utf-8") as handle:
                for row in rows:
                    record = {
                        "t": round(row[0], 5),
                        "min_m": round(row[1], 5),
                        "left_link": row[2],
                        "right_link": row[3],
                    }
                    if len(row) > 4:
                        record["pos"] = row[4]
                    handle.write(json.dumps(record) + "\n")
            say(f"[biarm] clearance trace appended -> {path}")

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
        #: The arm's own pick station (two-line scheduler) or the shipped shared
        #: station (0.0) on every other path. All station-relative quantities of
        #: this attempt are measured from here, not from `cfg.pick_y`.
        station_y = self.station_y_for(arm_name)
        self._episodes_by_arm[arm_name] = self._episodes_by_arm.get(arm_name, 0) + 1
        # Start every attempt with clean gripper state: a failed attempt used to
        # leave the pads closed somewhere on the belt, which then blocked arriving
        # fruit and stalled the whole collector (20 minutes without an episode).
        self._closed_gap[arm_name] = None
        self._force_servo_reset(arm_name)
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
                    #: W3 schema addition (backwards-compatible: a new field):
                    #: which pick station this arm worked, so the merged dataset
                    #: keeps the per-arm/station label of a two-line episode.
                    #: 0.0 on every single-arm episode.
                    station_y=float(station_y),
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
        # `FRUIT_DYNAMIC_PICK` is resolved by `_dynamic_pick_mode`: the shipped
        # scripted line takes the fruit on the fly with either hand, the policy
        # handover keeps its P1 default. The OpenArm hand's dynamic catch is the
        # arrival-synchronised descent in `grasp_carry_place`; the pads track by
        # construction. What made the old openarm dynamic pick fail was measured
        # (`logs/p2_step1_trace.log`): the close started 274-588 mm *behind* the
        # fruit because the hover/descent targeted a stale point after a 1.5 s
        # track and a 3.5 s approach (~38 cm of fruit travel), so the arm ran to
        # its reach edge and the fruit left the belt (`logs/dynamic_trace_00`).
        openarm = getattr(self.grippers[arm_name], "kind", "") == "openarm"
        dynamic_pick = self._dynamic_pick_mode(openarm, scripted=True)
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
        # Arm the collector's per-attempt wall budget (0 = off everywhere but
        # the collector; see `_step_sim`). Per-attempt thread-local, so the
        # bimanual's two concurrent attempts each get their own deadline.
        self._episode_deadline = (
            time.monotonic() + self.episode_timeout_s
            if self.episode_timeout_s > 0.0
            else None
        )
        self._cycle_begin()
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
            [self.cfg.pick_x, station_y, self.belt_top + self.cfg.grasp_clearance]
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
                # Two-line: blend to *this arm's* station configuration so the
                # approach never sweeps through the other arm's station.
                target=self._station_prepose_target(arm_name),
            )
        else:
            prepose = self._station_prepose_target(arm_name)
            arm.teleport_joints(
                self._pose(arm_name, "grasp") if prepose is None else prepose
            )
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
        if self._active_session is not None:
            # Under the bimanual session this pump is bridged to the main thread,
            # and `update_app` is not a fixed step (AGENTS section 3b): measured,
            # twenty app updates advanced the pre-pose 1.37 s instead of the
            # single-arm 0.88 s, which pushed the selection lead out of
            # calibration (fruits selected in the station window arrived after
            # the pre-pose had ended). Step physics explicitly and keep the pump,
            # exactly like the drivers' `advance()`.
            from isaacsim.core.simulation_manager import SimulationManager

            SimulationManager.step(steps=20)
            app_utils.update_app(steps=0)
        else:
            app_utils.update_app(steps=20)
        move_time = self._sim_time() - t0
        jaw_hold = arm.jaw_centre().copy()
        self._cycle_mark("prepose")
        if verbose:
            say(
                f"[task] at pick pose after {move_time:.2f} s (residual={residual:.4f} m) "
                f"(jaw={np.round(jaw_hold, 4).tolist()})"
            )

        if dynamic_pick and openarm:
            # Wait out the feed *at the hover*. The moving catch's descent has to
            # start exactly `v*T_descent` upstream, and every tick of hover-move or
            # settle spent after the handover is feed timing the schedule cannot
            # give back - with the hover move inside `grasp_carry_place` the
            # descent began 6-9 cm past its deadline and the close opened behind
            # the fruit (`logs/p2_smoke5`). The gripper is empty, so this is a
            # positioning move exactly like the pre-pose.
            hold = top_down_quaternion(os.environ.get("FRUIT_HAND_AXIS", "x"))
            if arm_name == "left":
                hold = mirror_across_xz(hold)
            arm.hold_quaternion = hold
            self._dynamic_grip_target = self._dynamic_grip_point(sample)
            self._dynamic_hover_target = self._dynamic_hover_point(sample)
            previous_hover_step = arm.max_step
            arm.max_step = float(os.environ.get("FRUIT_HOVER_STEP", "0.04"))
            arm.move_to(
                arm.tcp_target_for_jaw(self._dynamic_hover_target),
                max_steps=int(os.environ.get("FRUIT_DYNAMIC_HOVER_MOVE", "300")),
                tolerance=0.008,
            )
            arm.max_step = previous_hover_step
            # Hold the hover with the same joint targets the wait loop already
            # re-commands every tick, so the arm is calm and exactly there when the
            # handover happens.
            grasp_config = arm.joint_positions()
            jaw_hold = arm.jaw_centre().copy()
            for _ in range(int(os.environ.get("FRUIT_DYNAMIC_HOVER_SETTLE", "20"))):
                arm.robot.set_dof_position_targets([grasp_config], dof_indices=arm.arm_dofs)
                self._step_sim(1)
        else:
            self._dynamic_grip_target = None
            self._dynamic_hover_target = None
        # The hover is where this attempt's hand reaches its own station; the
        # two-line scheduler's pre-pose serialization ends here (a no-op on
        # every single-arm / shared-station path).
        self._release_prepose()
        self._cycle_mark("hover")

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
                if openarm:
                    # Arrival-synchronised handover (P2). The openarm catch is a
                    # *static* descent at the station - the only way the descent
                    # stays inside the motion gate's world-frame speed budget -
                    # so it has to start while the fruit is still upstream. The
                    # descent itself re-checks the timing and waits at hover, so
                    # this estimate only has to be generous, never exact.
                    lead = self._dynamic_pick_lead()
                    if dy <= lead:
                        arrived = True
                        if verbose:
                            belt_v = self._belt_speed_estimate()
                            try:
                                fruit_v = float(
                                    np.asarray(self.spawner.velocity(sample), dtype=float)[1]
                                )
                                ratio = fruit_v / belt_v if abs(belt_v) > 1e-9 else float("nan")
                            except Exception:  # noqa: BLE001
                                fruit_v, ratio = float("nan"), float("nan")
                            say(
                                f"[task]   intercept handover: fruit_y={float(pos[1]):.4f} "
                                f"dy={dy:+.4f} m lead={lead:.3f} m at "
                                f"{float(belt.encoder_speed) if belt is not None else 0.0:+.3f} m/s "
                                f"(fruit |v_y|={abs(fruit_v):.3f} m/s, ratio {ratio:.2f}x, "
                                f"queue={self._queue_depth()})"
                            )
                        break
                    if dy < -0.25:
                        # Already past the downstream end of the reach: the fruit
                        # is carried off (and recirculated), so do not spend the
                        # attempt on it (logs/388).
                        if verbose:
                            say(f"[task]   fruit past the catch window (dy={dy:+.3f} m)")
                        break
                else:
                    # Take the fruit while it moves. The pads are placed on the
                    # fruit's measured centre by the hand-off below and re-placed
                    # every tick through the close, so the requirement is only
                    # that the close-and-lift fits inside the arm's window and
                    # that the fruit is *near the arm* when the grip is taken:
                    # the pads are carried at their offset from the arm's tool
                    # point, so grasping a fruit 20 cm up the belt (the first
                    # version's default) leaves the payload on a 20 cm lever.
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
                        # The fruit ran past the tracking window: it is downstream
                        # and still moving away, so this attempt is a miss. Do not
                        # fall through to the "reached the jaw" branch - that used
                        # to accept a fruit that had already left the belt end
                        # (logs/388).
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
                    if float(other_pos[1]) > station_y + 0.05:
                        incoming = True
                        break
                if not incoming and float(pos[1]) > station_y + 0.6:
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
        result = self.grasp_carry_place(
            arm_name, sample, bin_index, result, verbose=verbose, scripted=True
        )
        self._cycle_mark("end")
        return result

    def grasp_carry_place(self, arm_name: str, sample, bin_index: int,
                          result, verbose: bool = False, scripted: bool = False):
        """Public entry: the contact work, with the mechanism trace kept alive.

        Thin wrapper over `_grasp_carry_place_impl`. It exists only so the
        attempt's `FRUIT_DYNAMIC_TRACE` rows survive on the *direct* path (the
        scripted loop flushes them from `note_result`); with the trace off this
        adds one function call and does nothing else. The handover row it
        records before the primitive starts is what says where the policy left
        the jaws relative to the station.
        """
        if not scripted and self._dynamic_trace is not None:
            self._dynamic_trace_sample(
                "handover", sample, self.arms[arm_name], self.grippers[arm_name], 0.0
            )
        outcome = "fail"
        try:
            result = self._grasp_carry_place_impl(
                arm_name, sample, bin_index, result, verbose=verbose, scripted=scripted
            )
            outcome = "ok" if getattr(result, "success", False) else "fail"
        finally:
            self._dynamic_trace_dump(arm_name, scripted, outcome)
        return result

    def _grasp_carry_place_impl(self, arm_name: str, sample, bin_index: int,
                                result, verbose: bool = False, scripted: bool = False):
        """Seat, grasp, carry and release a fruit that is already at the pick point.

        The contact work of an episode, without the approach: the hybrid evaluator
        lets the policy drive the arm towards the fruit first and then calls this,
        so the policy and the primitives share exactly the same grasp.

        `scripted=True` marks the call from `_run_impl` (the scripted line), which
        is the path the P2 moving catch is built for. A direct call (the policy
        handover) keeps the P1 indexed default unless `FRUIT_DYNAMIC_PICK=1`
        asks for the true dynamic line - `_dynamic_pick_mode` is the single
        place that decides.
        """
        belt = getattr(self.spawner, "belt", None)
        arm = self.arms[arm_name]
        #: The arm's own pick station (two-line scheduler); 0.0 on every other
        #: path. `arm_name` is authoritative here: the policy handover may call
        #: this without `_run_impl` having set `current_arm`.
        station_y = self.station_y_for(arm_name)
        #: The OpenArm hand *is* the robot's fingers, so the arm has to stay with
        #: the payload; its scripted catch is arrival-synchronised (P2), and a
        #: moving pick is only attempted when `_dynamic_pick_mode` says so.
        openarm = getattr(self.grippers[arm_name], "kind", "") == "openarm"
        # Same flag as `_run_impl`: a dynamic line keeps running while the arm
        # carries and places (see the note at the end of the lift).
        dynamic_pick = self._dynamic_pick_mode(openarm, scripted=scripted)
        #: The P2 catch proper: the arm meets the fruit at the station with a
        #: static descent and closes while tracking it. The scripted openarm path
        #: always runs it; the policy handover runs it when `FRUIT_DYNAMIC_PICK=1`
        #: asks for the true dynamic line (the v8/P1 directive) - its trigger
        #: hands over on the predicted arrival, so the catch only has to meet the
        #: schedule. With the env unset the handover keeps the P1 indexed
        #: primitive (the pad hand's dynamic close tracks by construction).
        dynamic_capture = bool(dynamic_pick and openarm)
        #: P2b left-arm fix. The direct (policy) handover used the scripted 6 cm
        #: hover and paid for it: its pre-descent overhead (~0.7 s) plus the
        #: descent itself (~0.7 s) put the fruit 5-8 cm *downstream* when the
        #: catch-up began. Chasing it there drives the left arm's joint2 into its
        #: upper limit (+0.1745 rad; the mirrored right range is +3.32 rad), the
        #: IK saturates (clipped 200/200 ticks, |error6| 0.09 -> 0.83 rad,
        #: `logs/p2b/diag3/`) and the close misses. Measured on a reach ladder
        #: (`logs/p2b/reach_ladder.log`): with the catch hold the left tracks
        #: cleanly to ~4.5 cm downstream of the station, the right to ~15 cm.
        #:
        #: The fix, direct path only (the scripted line reads none of it and is
        #: bit-unchanged):
        #: * park at the station's *grip* pose (`FRUIT_DIRECT_HOVER=0`) instead
        #:   of the 6 cm hover, so the setup no longer spends the descent's 0.7 s
        #:   after the trigger;
        #: * hold the grip for a bounded servo (`FRUIT_DIRECT_HOLD_TICKS`) so the
        #:   coarse `move_to`'s ~1 cm parking residual is settled before the fruit
        #:   arrives;
        #: * skip the profiled final approach (`FRUIT_DIRECT_SKIP_APPROACH`): its
        #:   minimum duration (40 ticks for 11 mm) let the fruit cross the station
        #:   before the close; the catch-up tracks the fruit and completes the
        #:   last centimetres itself;
        #: * cap the catch-up's per-tick downstream command
        #:   (`FRUIT_DIRECT_CATCH_MAX=0.035`), so any timing residual stays inside
        #:   the left arm's measured band;
        #: * `FRUIT_DIRECT_CATCH_LEAD` (0.25 s, the same as the scripted catch-up
        #:   lead) is the convergence compensation - it only applies while the tip
        #:   chases, and the cap bounds it.
        #: `FRUIT_DIRECT_HOVER=0.06 FRUIT_DIRECT_SKIP_APPROACH=0
        #: FRUIT_DIRECT_HOLD_TICKS=0 FRUIT_DIRECT_CATCH_MAX=1000` restores the
        #: pre-fix direct flow as the control.
        direct_capture = bool(dynamic_capture and not scripted)
        direct_hover = float(os.environ.get("FRUIT_DIRECT_HOVER", "0.0"))
        direct_catch_lead = float(os.environ.get("FRUIT_DIRECT_CATCH_LEAD", "0.25"))
        #: Safety net for the direct catch-up: never command the tip more than
        #: this far downstream of where it is. The left arm cannot track more
        #: than ~4.5 cm downstream of the station with the catch hold
        #: (`logs/p2b/reach_ladder.log`); a larger command saturates joint2 and
        #: the arm sweeps across the fruit instead of following it. The fruit
        #: moves 1 mm/tick, so a 3.5 cm cap loses nothing: the next tick
        #: re-commands from the improved tip.
        direct_catch_max = float(os.environ.get("FRUIT_DIRECT_CATCH_MAX", "0.035"))
        if direct_capture:
            # `_run_impl` computes these at its upstream hover handover; a direct
            # handover has no hover yet (the policy left the arm near its own
            # pose) and the attempt-local values may be stale from a previous
            # episode, so recompute the station-relative grip/hover for this
            # fruit. The hover-wait and intercept below then time the descent.
            self._dynamic_grip_target = self._dynamic_grip_point(sample)
            self._dynamic_hover_target = (
                self._dynamic_grip_point(sample)
                + np.array([0.0, 0.0, direct_hover])
            )
            if os.environ.get("FRUIT_HANDOVER_DIAG", "0") == "1":
                _jaw = np.asarray(arm.jaw_centre(), dtype=float)
                say(
                    f"[diag] handover {arm_name}: fruit="
                    f"{np.round(np.asarray(self.spawner.position(sample), dtype=float), 4).tolist()} "
                    f"jaw={np.round(_jaw, 4).tolist()} grip="
                    f"{np.round(self._dynamic_grip_target, 4).tolist()} hover="
                    f"{np.round(self._dynamic_hover_target, 4).tolist()} "
                    f"dy_station={station_y - float(_jaw[1]):+.4f} m"
                )
        self._dynamic_capture_active = dynamic_capture
        # W1 two-line grip profile (env-overridable; see `_dynamic_profile`):
        # the re-seat-in-place regrasp and the gentler probe apply on the
        # two-line scheduler. As *global* defaults the same values reshuffle
        # the shipped single arm's marginal branch (9/10 -> 6/10, measured
        # `logs/w1/36_single_winner_screen.log`), so they are scoped to the
        # two-line scenario.
        regrasp_keep = (
            self._dynamic_profile("FRUIT_DYNAMIC_REGRASP_KEEP", "0", "1") == "1"
        )
        probe_ticks_default = self._dynamic_profile(
            "FRUIT_DYNAMIC_PROBE_TICKS", "40", "60"
        )
        probe_lift_default = self._dynamic_profile(
            "FRUIT_DYNAMIC_PROBE", "0.010", "0.006"
        )
        test_step_default = self._dynamic_profile(
            "FRUIT_DYNAMIC_TEST_STEP", "0.02", "0.01"
        )
        # Fresh peak-hold origin per attempt (set pre-probe below).
        self._dynamic_peak_z = None
        if belt is not None and not dynamic_pick and openarm:
            # The policy evaluator calls this primitive with the belt already
            # running, and `stop()` only ramps inside `Conveyor.step`, which is
            # not called during the grasp; apply the stop now.
            belt.hold()
        # Same clean start as `run()`: a leftover closed gripper from the previous
        # episode can otherwise grab a fruit off the belt on its own, which is what
        # produced the odd `handoff=False lifted=True` episodes in logs/200.
        self._closed_gap[arm_name] = None
        self._force_servo_reset(arm_name)
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
            [self.cfg.pick_x, station_y, seat + sample.diameter / 2.0]
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
        # seat height (e.g. a raised nest with `FRUIT_NEST`), is teleported. The
        # OpenArm hand needs the fruit *at the station*: the jaws cannot be placed
        # on a fruit the coherent servo cannot reach, so its hand-off limit is the
        # servo's own working envelope.
        hard_limit = float(
            os.environ.get("FRUIT_HANDOFF_MAX", "0.06" if openarm else "0.30")
        )
        teleport = (
            not dynamic_capture
            and (
                os.environ.get("FRUIT_HANDOFF", "contact") == "teleport"
                or jump > hard_limit
                or float(measured[2]) < seat - 0.02
            )
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
                if dynamic_capture:
                    say(
                        f"[task] moving pick: meeting the fruit {jump * 1000:.0f} mm "
                        f"upstream of the pick centre (no seat dwell)"
                    )
                else:
                    say(
                        f"[task] seated by contact: picking the fruit {jump * 1000:.0f} mm "
                        f"from the pick centre"
                    )
        sample.held = True
        if not dynamic_capture:
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
            # The `openarm` hand *is* the robot's fingers: there are no free pads
            # to teleport onto the fruit, so it always uses the coherent servo
            # (fingertips tracked onto the fruit's measured centre) and never falls
            # back to the assisted pad frame, which would close the jaws on air.
            openarm = getattr(gripper, "kind", "") == "openarm"
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
            coherent = openarm or os.environ.get("FRUIT_COHERENT_HAND", "0") == "1"
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
                if os.environ.get("FRUIT_STATION_RESELECT", "1") == "1" and not dynamic_capture:
                    # The reselect exists for the *stationary* hand-off (a fruit
                    # that stopped short of the mark while another sits between
                    # the jaws). The moving catch tracks the fruit it selected, so
                    # switching to a different one would break the arrival
                    # schedule; it is skipped there and kept for the indexed path
                    # (policy handover), now lane-safely.
                    presented = self.station_sample()
                    if presented is not None and int(presented.index) != int(sample.index):
                        # P1 item 4: this used to recompute `bin_index` from the
                        # presented fruit's grade while the *arm* had already been
                        # chosen from the original lane. A cross-lane switch then
                        # sent the arm into a body it cannot cross and the fruit
                        # was dropped (`logs/video_grasp_seed5`, two peach cycles).
                        # The arm cannot change lanes mid-attempt, so the presented
                        # fruit is taken onto the *arm's own* lane and the sort
                        # error is recorded; a drop is never acceptable.
                        presented_lane = 0 if presented.grade == "A" else 1
                        if presented_lane == bin_index:
                            say(
                                f"[task]   reselecting: selected index {sample.index} is not "
                                f"at the station; taking index {presented.index}"
                            )
                        else:
                            say(
                                f"[task]   reselecting across lanes: presented index "
                                f"{presented.index} (grade {presented.grade}) belongs to lane "
                                f"{presented_lane}, but the {arm_name} arm serves lane "
                                f"{bin_index}; placing it on the arm's own lane"
                            )
                            result.notes.append(
                                f"cross-lane station fruit (index {presented.index}) placed "
                                f"on lane {bin_index}"
                            )
                        sample.held = False  # release the fruit we are not picking
                        sample = presented
                        sample.held = True
                        result.sample_index = int(presented.index)
                        result.category = presented.category
                        result.grade = presented.grade
                        # `bin_index` stays the arm's lane - see above.
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
                if openarm:
                    # Seed from the calibrated grasp pose. The policy evaluator
                    # hands over with the arm wherever the policy stopped, and the
                    # differential IK can stall from there (measured 41 cm away
                    # and 30 cm below the fruit, `logs/458`); the pad hand's
                    # `aim_pads` primitive seeds the same way for the same reason.
                    # Teleporting joints with an empty hand is a positioning step,
                    # exactly like the scripted pre-pose. The *scripted* moving catch
                    # is already at the calibrated pose (its pre-pose), and the
                    # 40-tick seed plus this teleport's `sync` was 0.33 s of the
                    # feed-time budget it hands over for - skipped there so the
                    # hover wait has slack to time the descent (`logs/p2_smoke4`:
                    # the seed+settle overhead put the descent start 17 cm past
                    # the deadline at the shipped 0.12 m/s with the 0.03 profile).
                    if not dynamic_capture:
                        seed = (
                            self.waypoints.get("arms", {}).get(arm_name, {}).get("grasp")
                        )
                        if seed is not None:
                            arm.teleport_joints(np.asarray(seed, dtype=float))
                            for _ in range(40):
                                self._step_sim(1)
                            arm.sync_command_to_measured()
                track_ticks = int(os.environ.get("FRUIT_COHERENT_TRACK", "180"))
                if dynamic_capture:
                    # The moving catch aims the *whole pre-close* at the station:
                    # a short hold there (0 ticks by default) instead of a 1.5 s
                    # fruit-chasing track, because that track's 9 cm of fruit
                    # travel is part of what made the old close start 30-59 cm
                    # behind (`logs/p2_step1_trace.log`).
                    track_ticks = int(os.environ.get("FRUIT_DYNAMIC_TRACK", "0"))
                    aim = self._dynamic_aim(sample)
                    fruit = aim
                else:
                    fruit = np.asarray(self.spawner.position(sample), dtype=float)
                if openarm:
                    # Coarse first move to the fruit. The policy evaluator hands
                    # over with the arm wherever the policy's last actions left it
                    # (measured 41 cm away and 30 cm below the fruit, `logs/458`),
                    # and the 120 Hz tracker alone can stall in a local minimum at
                    # that distance. The scripted path arrives at the pick pose.
                    premove = fruit + np.array(
                        [0.0, 0.0, self._pad_standoff(dynamic_capture, sample)]
                    )
                    if dynamic_capture:
                        # Straight to the hover: the fruit is still upstream, so
                        # the hand waits for it above the station and the descent
                        # in the block below is the measured approach leg. The
                        # direct (policy) handover uses its own short hover
                        # (`direct_hover`): its late start cannot afford the 6 cm
                        # descent that would put the fruit past the reachable
                        # downstream band of the left arm (`logs/p2b/diag3`).
                        premove = premove + np.array(
                            [0.0, 0.0, direct_hover if direct_capture else float(
                                os.environ.get(
                                    "FRUIT_DYNAMIC_HOVER",
                                    os.environ.get("FRUIT_HOVER", "0.06"),
                                )
                            )]
                        )
                    arm.move_to(
                        arm.tcp_target_for_jaw(premove),
                        max_steps=int(os.environ.get("FRUIT_OPENARM_PREMOVE", "400")),
                        tolerance=0.02,
                    )
                    if os.environ.get("FRUIT_HANDOVER_DIAG", "0") == "1":
                        _jaw = np.asarray(arm.jaw_centre(), dtype=float)
                        _err = float(np.linalg.norm(_jaw - premove))
                        say(
                            f"[diag] premove {arm_name}: err={_err * 1000:.0f} mm "
                            f"jaw={np.round(_jaw, 4).tolist()} "
                            f"target={np.round(premove, 4).tolist()}"
                        )
                for _tick in range(track_ticks):
                    if dynamic_capture:
                        fruit = aim  # hold the station; see the note above
                    else:
                        fruit = np.asarray(self.spawner.position(sample), dtype=float)
                    arm.ik_step(
                        arm.tcp_target_for_jaw(
                            fruit + np.array([0.0, 0.0, self._pad_standoff(dynamic_capture, sample)])
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
                            (aim if dynamic_capture else np.asarray(
                                self.spawner.position(sample), dtype=float
                            ))
                            + np.array([0.0, 0.0, self._pad_standoff(dynamic_capture, sample)])
                        )
                    )
                    self._step_sim(1)
                if verbose:
                    say(
                        f"[task] coherent axis: 1-cos={axis_error:.4f} "
                        f"({'ok' if axis_error <= float(os.environ.get('FRUIT_AXIS_TOL', '0.01')) else 'FAILED'})"
                    )
                if axis_error > float(os.environ.get("FRUIT_AXIS_TOL", "0.01")):
                    if openarm:
                        # The fingers themselves are the hand: keep the tracker
                        # (the close will simply miss if the attitude is wrong) but
                        # record why instead of switching to a pad frame that does
                        # not exist.
                        say(
                            f"[task]   openarm hand attitude not settled "
                            f"(1-cos={axis_error:.4f}); closing anyway"
                        )
                    else:
                        coherent = False
                        self._coherent[arm_name] = False
                if pad_error > float(os.environ.get("FRUIT_COHERENT_FALLBACK", "0.020")):
                    # The real fingertips cannot be brought onto the fruit for this
                    # attempt: keep the pipeline reliable and use the assisted pad
                    # frame instead (logged, so the rate is visible in the stats).
                    # With the openarm hand there is no assisted frame - the jaws
                    # are the only grip - so the attempt proceeds and the lift
                    # check decides.
                    if openarm:
                        say(
                            f"[task]   openarm fingertips {pad_error * 1000:.0f} mm "
                            "from the fruit; closing anyway"
                        )
                    else:
                        coherent = False
                        self._coherent[arm_name] = False
                        if verbose:
                            say(
                                f"[task] coherent hand fell back to the assisted frame "
                                f"(fingertip error {pad_error * 1000:.0f} mm)"
                            )
                else:
                    self._coherent[arm_name] = True
                if openarm:
                    # Reproduce the shipped *descent* leg for the OpenArm hand. The
                    # coherent servo above has found the fruit, so back up
                    # `FRUIT_HOVER` along the tool axis, settle, then descend onto
                    # the tracked grip pose with the same jerk-limited cartesian
                    # profile the motion gate measures - the assisted block that
                    # carries that leg for the pad hand is skipped for the jaws.
                    # For the moving catch the grip pose is the *station* aim
                    # (`_dynamic_aim`), the hover is the dynamic clearance, and the
                    # descent waits at hover until the fruit is one descent away:
                    # the fruit then arrives under the fingers as the leg ends, so
                    # the world-frame profile never has to chase the belt.
                    if dynamic_capture and self._dynamic_grip_target is not None:
                        # The arm waited at this hover (see `_run_impl`): use the
                        # exact target it is already holding, so the descent starts
                        # on schedule instead of after a fresh move. A direct
                        # handover computed this hover itself (`direct_hover`).
                        grip = np.asarray(self._dynamic_grip_target, dtype=float).copy()
                        hover = np.asarray(self._dynamic_hover_target, dtype=float).copy()
                    else:
                        grip = np.asarray(
                            self.spawner.position(sample), dtype=float
                        ) + np.array([0.0, 0.0, finger_len + PAD_LIFT])
                        hover = grip.copy()
                        hover[2] += float(os.environ.get("FRUIT_HOVER", "0.06"))
                    previous_max_step = arm.max_step
                    arm.max_step = float(os.environ.get("FRUIT_HOVER_STEP", "0.04"))
                    # NB: a *tighter* tolerance here was measured harmful: the
                    # drives settle at ~5-8 mm, so a 3 mm target runs `move_to` to
                    # its full 500 steps (4.2 s) and the fruit is 40 cm downstream
                    # before the descent (`logs/p2b/smoke_fix2`). The descent below
                    # starts from the parked pose and absorbs the residual.
                    hover_residual = arm.move_to(
                        arm.tcp_target_for_jaw(hover), max_steps=500, tolerance=0.008
                    )
                    if os.environ.get("FRUIT_HANDOVER_DIAG", "0") == "1":
                        _jaw = np.asarray(arm.jaw_centre(), dtype=float)
                        say(
                            f"[diag] hover {arm_name}: err={hover_residual * 1000:.0f} mm "
                            f"jaw={np.round(_jaw, 4).tolist()} "
                            f"target={np.round(hover, 4).tolist()}"
                        )
                    if os.environ.get("FRUIT_APPROACH_SETTLE", "1") == "1":
                        # The scripted moving catch bounds this: it hands over a
                        # fixed upstream distance and every 0.1 s of settling is
                        # 1.2 cm of feed timing the hover wait then cannot give
                        # back. It still starts the descent from a calm arm.
                        settle_max = (
                            int(os.environ.get("FRUIT_DYNAMIC_SETTLE_TICKS", "0"))
                            if dynamic_capture
                            else 900
                        )
                        ticks, speed = self._settle_to_rest(arm, max_ticks=settle_max)
                        if verbose:
                            say(
                                f"[task] openarm approach settle: {ticks} ticks to "
                                f"|v|<{os.environ.get('FRUIT_SETTLE_EPS', '0.002')} m/s "
                                f"(|v|={speed:.4f} m/s)"
                            )
                    dyn_v_max = None
                    if dynamic_capture:
                        # Wait at the hover until the fruit is roughly one descent
                        # away. `_dynamic_pick_lead` handed over early enough that
                        # this wait is normally a few ticks; if the fruit is
                        # already late the loop exits at once and the intercept
                        # below aims at wherever the fruit will then be. Nothing
                        # here commands the arm but the hover hold, and no
                        # `[motion]` leg is emitted for it.
                        dyn_v_max = float(
                            os.environ.get("FRUIT_DYNAMIC_APPROACH_VMAX", os.environ.get("FRUIT_APPROACH_VMAX", "0.15"))
                        )
                        dyn_a_max = float(os.environ.get("FRUIT_APPROACH_AMAX", "0.8"))
                        # Time the descent with the duration it will actually
                        # take. The historic estimate fed `_approach_duration`
                        # the jaw-space hover height (0.06 m), 12 % longer than
                        # the 0.054 m TCP distance the leg really covers, so
                        # every descent started ~45 mm early and the P2b
                        # diagnosis ended with the fruit 4-6 cm upstream of the
                        # descending jaws. Measure the live TCP distance instead
                        # (a fruit read is free per the instrumentation rule).
                        target_now = arm.tcp_target_for_jaw(grip)
                        t_desc = self._approach_duration(
                            float(np.linalg.norm(target_now - arm.tcp_position())),
                            dyn_v_max,
                            dyn_a_max,
                        )
                        speed_now = abs(self._belt_speed_estimate())
                        deadline = speed_now * (
                            t_desc + float(os.environ.get("FRUIT_DYNAMIC_DESCEND_MARGIN", "0.15"))
                        )
                        waited = 0
                        max_wait = int(os.environ.get("FRUIT_DYNAMIC_WAIT_MAX", "900"))
                        # The direct handover parks at the grip; it must actually
                        # *reach* it before the close starts. A held servo of
                        # `FRUIT_DIRECT_HOLD_TICKS` settles the ~1 cm parking
                        # residual the coarse `move_to` leaves (the drives settle
                        # near its 8 mm tolerance), so the catch-up begins with
                        # the tip at the station instead of a centimetre short
                        # (`logs/p2b/smoke_fix1`, left strawberry). The scripted
                        # line reads 0 and is bit-unchanged.
                        hold_ticks = (
                            int(os.environ.get("FRUIT_DIRECT_HOLD_TICKS", "20"))
                            if direct_capture
                            else 0
                        )
                        while waited < max_wait:
                            fruit_now = np.asarray(self.spawner.position(sample), dtype=float)
                            if (
                                float(fruit_now[1]) - float(grip[1]) <= deadline
                                and waited >= hold_ticks
                            ):
                                break
                            arm.ik_step(arm.tcp_target_for_jaw(hover))
                            self._step_sim(1)
                            waited += 1
                        # Reachable intercept (P3 arrival fix). Compute where the
                        # fruit will be when this leg ends and use it to *time*
                        # the descent. A target shift was tried first and is
                        # measured bad: aiming downstream moves the target
                        # farther from the TCP, so the descent takes longer and
                        # the fruit overshoots even more (`logs/p3_..._smoke1`,
                        # A1 arrival error -34 mm against -20 mm at the station,
                        # and the stationary hand then took a hit from the
                        # fruit). The descent is a static, slow leg; the fruit
                        # has to arrive at the *station*, so the intercept is
                        # applied to the schedule -  the wait below starts the
                        # leg exactly `speed * t_desc` before the fruit reaches
                        # it - and the catch-up then acquires the (small) timing
                        # residual with velocity feed-forward.
                        intercept_y = float(fruit_now[1]) - speed_now * t_desc
                        max_shift = float(
                            os.environ.get("FRUIT_DYNAMIC_INTERCEPT_MAX", "0.03")
                        )
                        # W2: on the two-line left the catch point sits
                        # `_two_line_catch_lead` upstream of the station, so the
                        # timing clip is centred there, not on the station.
                        catch_y = station_y + self._two_line_catch_lead()
                        intercept_y = float(
                            np.clip(
                                intercept_y,
                                catch_y - max_shift,
                                catch_y + max_shift,
                            )
                        )
                        if verbose:
                            dy_now = float(fruit_now[1]) - intercept_y
                            say(
                                f"[task] dynamic descent: waited {waited} ticks, "
                                f"intercept={intercept_y:+.4f} m "
                                f"(station {station_y:+.4f}, shift "
                                f"{intercept_y - station_y:+.4f} m), "
                                f"fruit dy={dy_now:+.4f} m, deadline={deadline:.4f} m, "
                                f"t_desc={t_desc:.2f} s"
                            )
                        if os.environ.get("FRUIT_HANDOVER_DIAG", "0") == "1":
                            _jaw = np.asarray(arm.jaw_centre(), dtype=float)
                            _fruit = np.asarray(
                                self.spawner.position(sample), dtype=float
                            )
                            say(
                                f"[diag] wait {arm_name}: waited={waited} "
                                f"deadline={deadline:.4f} fruit_y={float(_fruit[1]):+.4f} "
                                f"jaw={np.round(_jaw, 4).tolist()} "
                                f"jaw_to_grip={float(np.linalg.norm(_jaw - grip)) * 1000:.0f} mm"
                            )
                    self._dynamic_trace_sample("descent", sample, arm, gripper, 0.0,
                                               fruit=np.asarray(self.spawner.position(sample)))
                    # The *direct* handover's final approach is the catch-up
                    # itself: `_approach` runs a jerk-limited profile whose
                    # minimum duration is 40 ticks for 11 mm, and those 0.33 s
                    # let the fruit cross the station before the close even
                    # starts (`logs/p2b/smoke_fix4`, left strawberry). The
                    # catch-up tracks the fruit's measured position, so it
                    # completes the last centimetres *and* the timing in the
                    # same ticks. The scripted line keeps the profiled descent -
                    # the motion gate measures that leg and its timing is what
                    # the arrival schedule is calibrated on.
                    skip_approach = direct_capture and (
                        os.environ.get("FRUIT_DIRECT_SKIP_APPROACH", "1") == "1"
                    )
                    if not skip_approach:
                        arm.max_step = float(os.environ.get("FRUIT_APPROACH_STEP", "0.08"))
                        self._approach(arm, grip, verbose=verbose, v_max=dyn_v_max)
                    arm.max_step = previous_max_step
                    self._cycle_mark("descent")
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
            if dynamic_capture:
                # The descent ends at the station with the fruit arriving; a
                # 0.5 s uncommanded settle would let it travel 3-9 cm out of the
                # jaw span before the close even starts.
                settle_ticks = int(os.environ.get("FRUIT_DYNAMIC_SETTLE", "0"))
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
            if dynamic_capture:
                # Two-phase moving close: a fast traverse to just outside the
                # fruit, then a loaded squeeze onto it. The shipped 1 s single
                # ramp let the fruit travel 6-18 cm through the jaws before they
                # closed.
                #
                # **The depth must not trust the pre-close chord.** `pinch_width`
                # is the fruit's extent along the closing axis *at the pose it was
                # measured in*; a kiwi measured with its long axis along the closing
                # axis reads 1.15x its diameter, and a rolling fruit rotates away
                # from that orientation during the 0.4 s close - the first 0.12 m/s
                # acceptance run closed on air for exactly that (0 N at the close,
                # `logs/accept.log` attempt 6). The squeeze target is therefore the
                # fruit's *minimum* extent (its radial width or its axial width,
                # whichever is smaller), which no orientation can undercut, and the
                # loop freezes the depth the moment the measured jaw span stops
                # following the command (contact).
                from .meshes import FRUIT_SHAPES, axis_extent

                shape = FRUIT_SHAPES.get(sample.category)
                if shape is not None:
                    radial_extent = axis_extent(shape, float(sample.diameter), np.array([1.0, 0.0, 0.0]))
                    axial_extent = axis_extent(shape, float(sample.diameter), np.array([0.0, 0.0, 1.0]))
                    min_extent = min(radial_extent, axial_extent)
                else:
                    min_extent = float(sample.diameter)
                wide = max(pinch_width * 1.02, float(sample.diameter) * 1.02)
                deep = min_extent * float(os.environ.get("FRUIT_DYNAMIC_CLOSE_DEEP", "0.97"))
                fast_ticks = int(os.environ.get("FRUIT_DYNAMIC_CLOSE_FAST", "24"))
                load_ticks = int(os.environ.get("FRUIT_DYNAMIC_CLOSE_LOAD", "60"))
                close_ramp = np.concatenate(
                    [
                        min_jerk_ramp(gap_open, wide, fast_ticks),
                        min_jerk_ramp(wide, deep, load_ticks),
                    ]
                )
                close_substeps = 1
            else:
                close_ramp = min_jerk_ramp(gap_open, grip_gap, close_steps)
                close_substeps = 2
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
            # The assisted (non-coherent) close does not command the arm, so the
            # drives keep the target the caller last set. `_q_cmd` is *not* that
            # target here: the pre-pose blend synced it to the lagging measured
            # pose (0.275 rad short of the converged pick pose in the verification
            # episode), and recording it would teach the policy to move backwards
            # during the close. Read the drive target once per close; the coherent
            # path re-commands the arm every tick and uses `_q_cmd` below.
            hold_target = None
            if not coherent and self.recorder is not None and self.recorder.recording:
                hold_target = self._arm_drive_target(arm)
            # Moving close: the target is the fruit's measured centre with the
            # drive lag fed forward. The drive trails a target moving at `v` by
            # about `v*tau`; aiming the target `v*lead` *downstream* makes the
            # achieved fingertip sit on the fruit instead of behind it, which is
            # what keeps a 6-18 cm/s fruit inside the closing span.
            dynamic_lead_s = float(os.environ.get("FRUIT_DYNAMIC_TRACK_LEAD", "0.18"))
            dynamic_v = np.zeros(3)
            if dynamic_capture:
                dynamic_v = np.asarray(self.spawner.velocity(sample), dtype=float)
                # Catch-up before the jaws start closing. The arrival-synchronised
                # descent can end a few centimetres upstream or downstream of the
                # fruit when the selector handed over inside the lead (measured
                # 0.41-0.42 m at the descent start against a 0.479 m deadline,
                # `logs/p2_smoke6`) - closing the fast phase there would close on
                # air and bat the arriving fruit. Track the residual out at the
                # close's tracking rate first (this is grasp contact work, not a
                # monitored transit leg), then close from a centred span.
                #
                # Velocity feed-forward (P3 arrival fix). The old loop commanded
                # the fruit's *measured* position, so a moving fruit could only
                # be acquired while it was upstream and crossing the tip: the
                # drive drops the achieved pose ~`v * tau` (20-45 mm at
                # 0.12 m/s) behind a target that moves, and the 200-tick loop
                # timed out with exactly that residual on A1/A6/A7
                # (`logs/p2b_diag_before_1`, 35.1/46.0/107.4 mm). Command the
                # same `v * lead` downstream that the close uses; the achieved
                # tip then converges onto the fruit from either side. The
                # break test stays the *measured* tip-to-fruit distance, so the
                # residual stays an honest number.
                catch_ticks = int(os.environ.get("FRUIT_DYNAMIC_CATCH_TICKS", "200"))
                catch_tol = float(os.environ.get("FRUIT_DYNAMIC_CATCH_TOL", "0.006"))
                # The close's 0.18 s lead is measured against a hand already
                # moving with the fruit; the catch-up starts from rest and the
                # drive lag is larger. Measured on the P3 smoke trace
                # (`logs/p3_..._smoke2`, A1): the commanded target ran 28 mm
                # (0.23 s) ahead of the achieved tip, so a 0.18 s lead left the
                # tip riding ~6-7 mm behind the fruit - just outside the 6 mm
                # tolerance, 200 ticks of grazing contact, and the hand shoved
                # the fruit off the line. Use its own (larger) lead so the
                # achieved tip lands on the fruit.
                # The direct (policy) handover uses its own smaller lead: it meets
                # the fruit near the station with a small gap, and the scripted
                # 0.25 s lead would command ~3 cm past a 1 cm gap - past the left
                # arm's measured downstream band (`logs/p2b/reach_ladder.log`).
                catch_lead_s = float(
                    direct_catch_lead
                    if direct_capture
                    else os.environ.get("FRUIT_DYNAMIC_CATCH_LEAD", "0.25")
                )
                catch_residual = float("inf")
                #: Per-tick IK trace of the catch-up only (diagnostic, off by
                #: default): it carries `limit_clipped`, `limit_margin`, the
                #: Jacobian `sigma_min` and the position/attitude split, which the
                #: dynamic trace cannot show.
                catch_trace = os.environ.get("FRUIT_CATCH_TRACE", "0") == "1"
                if catch_trace:
                    arm.begin_trace()
                for _ in range(catch_ticks):
                    fruit_now = np.asarray(self.spawner.position(sample), dtype=float)
                    dynamic_v = np.asarray(self.spawner.velocity(sample), dtype=float)
                    rot_now = _quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
                    tip = np.asarray(arm.jaw_centre(), dtype=float) + rot_now @ np.array(
                        [0.0, 0.0, finger_len]
                    )
                    desired_tip = fruit_now + np.array([0.0, 0.0, self._dynamic_pad_lift])
                    catch_residual = float(np.linalg.norm(tip - desired_tip))
                    if catch_residual < catch_tol:
                        break
                    # Direction-aware lead: only catch *up* when the tip is
                    # behind the fruit. When the tip is already downstream, a
                    # lead would command it further away from a fruit that is
                    # closing from upstream - measured on A5 (lychee), whose
                    # first catch-up sample had the tip 8.9 mm downstream and
                    # whose 200-tick run then ended 25.4 mm short. With the tip
                    # downstream, command the fruit itself and let it arrive
                    # through the 6 mm window.
                    if float(tip[1]) - float(fruit_now[1]) > 0.0:
                        catch_centre = fruit_now + np.array(
                            [0.0, float(dynamic_v[1]) * catch_lead_s, 0.0]
                        )
                    else:
                        catch_centre = fruit_now
                    catch_target = catch_centre + np.array(
                        [0.0, 0.0, self._pad_standoff(True, sample)]
                    )
                    if direct_capture:
                        # Never command more than `direct_catch_max` downstream of
                        # the current tip (see the knob's note): the left arm's
                        # reachable band is ~4.5 cm, and a larger jump saturates
                        # joint2 instead of closing the gap.
                        catch_target[1] = max(
                            float(catch_target[1]),
                            float(tip[1]) - direct_catch_max,
                        )
                    arm.ik_step(arm.tcp_target_for_jaw(catch_target))
                    gripper.follow_centre(
                        fruit_now, np.asarray(arm.tcp_pose()[1], dtype=float), gap_open
                    )
                    self._step_sim(1)
                    self._dynamic_trace_sample(
                        "catchup", sample, arm, gripper, gap_open, cmd=catch_target
                    )
                if catch_trace:
                    self._catch_trace_seq = int(
                        getattr(self, "_catch_trace_seq", 0)
                    ) + 1
                    _dir = os.environ.get(
                        "FRUIT_CATCH_TRACE_DIR", "logs/p2b/catch_trace"
                    )
                    os.makedirs(_dir, exist_ok=True)
                    _path = os.path.join(
                        _dir, f"catch_{self._catch_trace_seq:02d}_{arm_name}.json"
                    )
                    _count = arm.end_trace(_path)
                    say(
                        f"[trace] catchup IK trace {_count} steps -> {_path}"
                    )
                if verbose:
                    say(
                        f"[task] dynamic catch-up: residual={catch_residual * 1000:.1f} mm "
                        f"(tol {catch_tol * 1000:.0f} mm)"
                    )
                if (
                    os.environ.get("FRUIT_HANDOVER_DIAG", "0") == "1"
                    and dynamic_capture
                ):
                    _jaw = np.asarray(arm.jaw_centre(), dtype=float)
                    _fruit = np.asarray(self.spawner.position(sample), dtype=float)
                    say(
                        f"[diag] catchup {arm_name}: residual={catch_residual * 1000:.1f} mm "
                        f"jaw={np.round(_jaw, 4).tolist()} "
                        f"fruit={np.round(_fruit, 4).tolist()} "
                        f"tip_y-fruit_y={float(_jaw[1] - _fruit[1]):+.4f}"
                    )
            live_squeeze = float(os.environ.get("FRUIT_DYNAMIC_CLOSE_LIVE", "0.97"))
            # --- P2b: stop the close expelling the fruit ------------------- #
            # The pre-P2b close let the live clamp keep deepening the squeeze
            # for the whole load ramp while the arm steered itself onto the
            # fruit's measured x every tick. On the centered failures of
            # `logs/p2_trace10` the payload left the span *during* the close
            # (cross-belt +122/+147 mm, force 0 through the whole hold) and the
            # clamp had walked from the contact depth down to
            # `min_extent * FRUIT_DYNAMIC_CLOSE_LIVE`. This is the gate's
            # ordered fix: (a) freeze the closing command at the first
            # *sustained* contact, so the depth stops growing once the fingers
            # are loaded; (b) stop steering the hand along the closing axis (x),
            # so a fruit that starts sliding sideways presses against a
            # stationary finger instead of being followed. Both are control
            # changes, not diagnostics; set `FRUIT_DYNAMIC_CLOSE_FREEZE=0` /
            # `FRUIT_DYNAMIC_CLOSE_LOCK_X=0` to restore the old policy for an
            # A/B.
            freeze_close = os.environ.get("FRUIT_DYNAMIC_CLOSE_FREEZE", "1") == "1"
            lock_x = os.environ.get("FRUIT_DYNAMIC_CLOSE_LOCK_X", "1") == "1"
            contact_force = float(os.environ.get("FRUIT_DYNAMIC_CONTACT_FORCE", "0.5"))
            contact_ticks = int(os.environ.get("FRUIT_DYNAMIC_CONTACT_TICKS", "3"))
            contact_stall = float(
                os.environ.get("FRUIT_DYNAMIC_CONTACT_STALL", "0.00015")
            )
            for _close_attempt in range(close_attempts):
                last_cmd = grip_gap
                freeze_cmd: float | None = None
                frozen_x: float | None = None
                #: Set at the first close tick when `FRUIT_DYNAMIC_X_TRACK_LATCH`
                #: is on: True means the fruit was already walking at contact.
                walk_latched: bool | None = None
                #: Payload pose in the hand frame at the first close tick; the
                #: drift check uses it to tell a *loaded* grip (kiwi transport)
                #: from a lost one.
                hand_rel_ref: np.ndarray | None = None
                # The x-lock pins the close against a *squeeze* that walks the
                # fruit sideways. A fruit that is already walking across the belt
                # before the pads touch (the kiwi, A6: +0.07-0.14 m/s during the
                # catch-up) is transport and must be tracked, or the pinned pad
                # lets it run out of the span; the velocity is measured at the
                # first close tick, so the threshold separates the two cases.
                x_pinned = lock_x
                contact_run = 0
                sep_prev: float | None = None
                for _close_step, gap in enumerate(close_ramp):
                    cmd = float(gap)
                    fruit_now = np.asarray(self.spawner.position(sample), dtype=float)
                    centre = fruit_now
                    if dynamic_capture:
                        if _close_step % 8 == 0:
                            dynamic_v = np.asarray(self.spawner.velocity(sample), dtype=float)
                        centre = centre + np.array(
                            [0.0, float(dynamic_v[1]) * dynamic_lead_s, 0.0]
                        )
                    if (
                        dynamic_capture
                        and x_pinned
                        and frozen_x is None
                        and self._dynamic_track_walk
                    ):
                        if abs(float(dynamic_v[0])) >= self._dynamic_walk_vx:
                            x_pinned = False
                            if verbose:
                                say(
                                    f"[task]   close x-lock off: fruit walks at "
                                    f"{float(dynamic_v[0]):+.3f} m/s; tracking x"
                                )
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
                        if dynamic_capture and x_pinned:
                            if frozen_x is None:
                                frozen_x = float(fruit_now[0])
                                if self._dynamic_x_track_latch:
                                    walk_latched = (
                                        self._dynamic_x_track_vx_max > 0.0
                                        and abs(float(dynamic_v[0]))
                                        >= self._dynamic_x_track_vx_max
                                    )
                                if coherent:
                                    rot0 = _quat_matrix(
                                        np.asarray(arm.tcp_pose()[1], dtype=float)
                                    )
                                    hand_rel_ref = rot0.T @ (
                                        fruit_now
                                        - np.asarray(
                                            self.grippers[arm_name].pad_centre(),
                                            dtype=float,
                                        )
                                    )
                                # Anti-walk lead (opt-in): a fruit already
                                # walking across the belt at `vx` gets the span
                                # placed *ahead* of it by `vx * lead`, so the
                                # fruit walks into the span centre and the
                                # leading finger blocks it, instead of the pads
                                # closing off-centre and batting/launching it
                                # (the A6 kiwi). 0 keeps the shipped pin.
                                walk_lead = float(
                                    os.environ.get("FRUIT_DYNAMIC_WALK_LEAD", "0.0")
                                )
                                if walk_lead > 0.0:
                                    frozen_x += float(dynamic_v[0]) * walk_lead
                            elif (
                                self._dynamic_x_track_vmax > 0.0
                                and self._x_seek_allowed(
                                    float(dynamic_v[0]), walk_latched
                                )
                            ):
                                # Anti-walk (A6): let the pinned x *seek* the
                                # fruit's measured x at a bounded rate. The cap
                                # is what separates this from the falsified raw
                                # tracker: a steady walk (<= the cap) is
                                # followed, a squeeze-out that accelerates past
                                # it is not (`logs/p3fix/mech_v4_walk`). The
                                # seek keeps running through the hold, because
                                # the kiwi's walk does not stop at first
                                # contact - without that the fruit leaves the
                                # span again during the 48-tick hold.
                                frozen_x = self._x_seek_step(
                                    float(frozen_x), float(fruit_now[0])
                                )
                            aim = np.array(
                                [frozen_x, float(centre[1]), float(centre[2])],
                                dtype=float,
                            )
                        else:
                            aim = centre
                        arm.ik_step(
                            arm.tcp_target_for_jaw(
                                aim + np.array([0.0, 0.0, self._pad_standoff(True, sample)])
                            )
                        )
                        close_quat = np.asarray(arm.tcp_pose()[1], dtype=float)
                    else:
                        close_quat = quat
                    if dynamic_capture and freeze_cmd is not None:
                        # Hold the depth the jaws found the fruit at.
                        cmd = freeze_cmd
                    elif dynamic_capture and _close_step >= fast_ticks:
                        # Follow the fruit's *current* extent, not the chord measured
                        # before the close: a rolling kiwi measured with its long axis
                        # along the closing axis reads 1.15x its diameter, and if it
                        # rotates away the open-loop target closes on air (the
                        # `logs/accept.log` attempt-6 0 N grip). `pinch_width` is pure
                        # geometry from the fruit's pose (a safe read), so it is
                        # re-evaluated every tick; the command stays a fixed
                        # interference *outside* whatever the fruit currently presents.
                        #
                        # Only from the *load* phase: clamping the fast phase too made
                        # the jaws squeeze `0.94x extent` on the first tick, before the
                        # fruit had arrived - the 0.12 m/s run scored 1/10 with every
                        # payload batted out of a pre-closed span (`logs/p2_012_run3`).
                        #
                        # The absolute-interference floor matters for small fruit:
                        # 3 % of a 3 cm strawberry is only 0.9 mm, and light fruit
                        # slipped out of the dynamic lift (`logs/p2_smoke7`). The
                        # clamp always leaves `max(3 %, 2.5 mm)` of interference;
                        # the finger drives' 10 N/joint limit caps the squeeze.
                        live_extent = self.pinch_width(sample, close_quat)
                        min_interference = float(
                            os.environ.get("FRUIT_DYNAMIC_MIN_INTERFERENCE", "0.0025")
                        )
                        if self._dynamic_interference_frac > 0.0:
                            # Scale the floor with the fruit: 2.5 mm is 10 % of a
                            # 3 cm strawberry and the flat 2.5 mm floor crushed it
                            # out during the hold (A4, `logs/p3fix/mech_diag1`).
                            min_interference = min(
                                min_interference,
                                live_extent * self._dynamic_interference_frac,
                            )
                        interference = max(live_extent * (1.0 - live_squeeze), min_interference)
                        if self._dynamic_interference_frac > 0.0:
                            # Capped mode: the ramp must not close deeper than the
                            # interference target (the historical `min` could only
                            # ever deepen it).
                            cmd = max(cmd, live_extent - interference)
                        else:
                            cmd = min(cmd, live_extent - interference)
                    if freeze_close and dynamic_capture and freeze_cmd is None:
                        # "First sustained contact" has to mean the fruit is
                        # actually loaded: force alone false-fires on the sensor's
                        # isolated spikes and on a fingertip grazing the fruit top
                        # (a 3 cm strawberry read 30 N with the jaws 89 mm open,
                        # `logs/p2b_diag_before_1` A4). Require the joint span to
                        # have *stalled* as well - the finger drives stopped
                        # following the command because the fruit is between them
                        # - which a flat-faced jam does, while a span still
                        # travelling (even slowly) does not.
                        reading = self.tactile.read().get(arm.spec.side, _EMPTY_TACTILE)
                        force_now = float(reading.normal_force)
                        sep_meas = float(
                            arm.JAW_SEPARATION_OFFSET
                            + arm.JAW_SEPARATION_PER_JOINT * arm.finger_opening()
                            - arm.FINGER_FACE_OFFSET
                        )
                        stalled = (
                            sep_prev is not None and abs(sep_meas - sep_prev) <= contact_stall
                        )
                        sep_prev = sep_meas
                        if force_now >= contact_force and stalled:
                            contact_run += 1
                        else:
                            contact_run = 0
                        if contact_run >= contact_ticks:
                            freeze_cmd = float(cmd)
                            if verbose:
                                say(
                                    f"[task] dynamic close: sustained contact after "
                                    f"{_close_step + 1} ticks (force={force_now:.2f} N, "
                                    f"span={sep_meas * 1000:.1f} mm); freezing the "
                                    f"closing command at {freeze_cmd * 1000:.1f} mm"
                                )
                    last_cmd = cmd
                    gripper.follow_centre(centre, close_quat, cmd)
                    self._step_sim(close_substeps)
                    self._tick_frame()  # pure render; no-op unless recording
                    self._dynamic_trace_sample(
                        "close", sample, arm, gripper, cmd, fruit=fruit_now
                    )
                    self._record(
                        self._action9(
                            self._commanded_arm(arm) if coherent else (
                                hold_target if hold_target is not None
                                else self._commanded_arm(arm)
                            ),
                            arm,
                            arm.gripper_value_for_separation(cmd),
                        )
                    )
                if dynamic_capture:
                    # The hold/carry re-commands the *recorded* gap every tick, so
                    # it must be the gap actually closed with (the live clamp is
                    # often shallower than the shipped 0.98x extent rule). Using
                    # the freeze depth alone (a narrower squeeze) was measured
                    # worse: 4/10 with a new lift-slip on A7, so the firmer
                    # recorded clamp stays.
                    grip_gap = min(grip_gap, last_cmd)
                    if (
                        self._dynamic_interference_frac > 0.0
                        and freeze_cmd is None
                    ):
                        # Capped mode without a freeze depth: the recorded gap is
                        # the live target the close stopped at, and the hold must
                        # not squeeze the small fruit deeper than that (the
                        # `pinch_width * 0.98` chord can be 2 mm inside the live
                        # extent once the fruit has turned).
                        grip_gap = max(grip_gap, last_cmd)
                fruit_end = np.asarray(self.spawner.position(sample), dtype=float)
                delta = fruit_end - np.asarray(rest, dtype=float)
                if dynamic_pick:
                    delta = delta * np.array([1.0, 0.0, 1.0])
                    if self._dynamic_x_track_vmax > 0.0 and frozen_x is not None:
                        # With the bounded x-seek the hand is following the
                        # fruit's cross-belt walk; the absolute displacement
                        # from the hand-off point is then transport, not a lost
                        # grip (the A6 kiwi walks ~+50 mm through the close and
                        # the absolute check re-closed on it). Measure the
                        # cross-belt error against the hand instead.
                        delta[0] = float(fruit_end[0]) - float(frozen_x)
                drift = float(np.linalg.norm(delta))
                if drift <= drift_max:
                    break
                if dynamic_capture and hand_rel_ref is not None:
                    # A position-only drift check on a *loaded* grip is a false
                    # positive. The A6 kiwi walks across the belt while the pads
                    # hold it (force ~4 N) and the payload's pose in the hand
                    # frame stays constant to a few mm, yet the world-x drift
                    # from the pinned span exceeds `drift_max`; re-closing then
                    # crushes/misses it (`logs/dyn_v3c2/traces_s14`: drift
                    # 89 mm at force 3.9 N, hand-relative pose constant). Only
                    # re-close when the payload has actually moved in the hand
                    # frame; a loaded, hand-stable grip is held.
                    reading = self.tactile.read().get(arm.spec.side, _EMPTY_TACTILE)
                    rot_now = _quat_matrix(
                        np.asarray(arm.tcp_pose()[1], dtype=float)
                    )
                    hand_rel_now = rot_now.T @ (
                        fruit_end
                        - np.asarray(self.grippers[arm_name].pad_centre(), dtype=float)
                    )
                    if (
                        float(reading.normal_force) >= contact_force
                        and float(np.linalg.norm(hand_rel_now - hand_rel_ref))
                        <= float(
                            os.environ.get("FRUIT_DYNAMIC_HAND_HELD_MAX", "0.020")
                        )
                    ):
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
                    self._force_servo_reset(arm_name)
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
            hold_ticks = int(
                os.environ.get("FRUIT_DYNAMIC_HOLD", "48")
                if dynamic_capture
                else "60"
            )
            for _ in range(hold_ticks):
                if dynamic_capture:
                    # Keep tracking while the contact settles: the jaws hold the
                    # fruit, but an uncommanded arm lets the belt drag it out
                    # during the hold (the baseline slip was measured at
                    # `logs/dynamic_trace_00`).
                    centre_now = np.asarray(self.spawner.position(sample), dtype=float)
                    if lock_x and frozen_x is not None:
                        # Same closing-axis freeze as the close: while the grip
                        # is being taken, following the fruit's measured x turns
                        # a small sideways slip into a runaway. With the bounded
                        # x-seek (A6) the same capped follow continues through
                        # the hold, so steady transport stays in the span.
                        if self._dynamic_x_track_vmax > 0.0:
                            vx_now = abs(
                                float(
                                    np.asarray(
                                        self.spawner.velocity(sample), dtype=float
                                    )[0]
                                )
                            )
                            if self._x_seek_allowed(vx_now, walk_latched, hold=True):
                                frozen_x = self._x_seek_step(
                                    float(frozen_x), float(centre_now[0])
                                )
                        centre_now[0] = frozen_x
                    arm.ik_step(
                        arm.tcp_target_for_jaw(
                            centre_now
                            + np.array([0.0, float(dynamic_v[1]) * dynamic_lead_s,
                                        self._pad_standoff(True, sample)])
                        )
                    )
                self._hold_with_gripper(arm_name, sample)
                self._step_sim(1)
                self._tick_frame()  # pure render; no-op unless recording
                if _ % 2 == 0:
                    self._dynamic_trace_sample(
                        "hold", sample, arm, self.grippers[arm_name],
                        float(self._closed_gap.get(arm_name) or grip_gap),
                    )
            if verbose:
                say(
                    f"[task] kinematic grip closed to {grip_gap * 100:.2f}cm "
                    f"around a {sample.diameter * 100:.2f}cm fruit"
                )
        self._cycle_mark("close")
        # v6 experiment 1 (opt-in): contact-verification dwell. The close's fixed
        # `FRUIT_DYNAMIC_HOLD` ticks have run; with the knob on, keep holding and
        # tracking until the tactile verifies a real load
        # (`FRUIT_DYNAMIC_VERIFY_FORCE` for `FRUIT_DYNAMIC_VERIFY_TICKS`
        # consecutive ticks, capped at `FRUIT_DYNAMIC_VERIFY_MAX_TICKS`). An
        # unverified grip is released and the attempt fails *before* any lift
        # command: the v5 evidence says the payload is ejected in the first lift,
        # so a lift from a grip that never read contact would add nothing.
        if dynamic_capture and self._verify_dwell:
            verified = self._dynamic_contact_dwell(
                arm_name,
                sample,
                arm,
                self.grippers[arm_name],
                float(grip_gap),
                frozen_x,
                dynamic_v,
                lock_x,
                walk_latched,
                dynamic_lead_s,
            )
            if not verified:
                book = self._dwell_state.get(arm_name, {})
                say(
                    f"[task]   dynamic dwell: no sustained contact before the lift "
                    f"(F=[{float(book.get('min_n', 0.0)):.2f},"
                    f"{float(book.get('max_n', 0.0)):.2f}] N); releasing"
                )
                result.notes.append("dynamic dwell: grip not verified before lift")
                for value in min_jerk_ramp(float(grip_gap), gap_open, 20):
                    self.grippers[arm_name].follow_centre(
                        np.asarray(self.spawner.position(sample), dtype=float),
                        np.asarray(quat, dtype=float),
                        float(value),
                    )
                    self._step_sim(2)
                self._closed_gap[arm_name] = None
                self._force_servo_reset(arm_name)
                return result
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
        if openarm:
            # The OpenArm hand *is* the gripping bodies, so the arm has to stay
            # with the payload. The assisted block below re-solves the OpenArm pad
            # frame ~7 cm above the fruit and closes the fingers *there* - running
            # it with a fruit already in the jaws would pull the fruit out of the
            # grip. The test lift that follows aims at the tracked jaw target.
            grasp_goal = np.asarray(self.spawner.position(sample), dtype=float) + np.array(
                [0.0, 0.0, self._pad_standoff(self._dynamic_capture_active, sample)]
            )
            grasp_config = arm.joint_positions()
            fingers = float(arm.dof_positions()[arm.finger_dofs].mean())
            if not self._dynamic_capture_active:
                # Indexed primitives stop the fruit here; the *moving* catch must
                # not: `spawner.stop` zeroes a 0.06-0.12 m/s velocity in one tick,
                # an impulse through the fresh contact that unseats the grip
                # (the 4.4 N close followed by a failed test lift,
                # `logs/p2_speed_006`). The arm's carry decelerates the payload
                # through friction instead, exactly as the pad hand's dynamic
                # line always did.
                self.spawner.stop(sample)
            result.max_tactile_force = self.tactile.read()[arm_name].normal_force
            self._dynamic_trace_sample(
                "grip", sample, arm, self.grippers[arm_name],
                float(self._closed_gap.get(arm_name) or 0.0), fruit=rest,
            )
            if os.environ.get("FRUIT_OPENARM_DEBUG", "0") == "1":
                say(
                    f"[task]   openarm grip: jaw={np.round(arm.jaw_centre(), 4).tolist()} "
                    f"fruit={np.round(np.asarray(self.spawner.position(sample)), 4).tolist()} "
                    f"finger_q={np.round(np.asarray(arm.dof_positions()[arm.finger_dofs]), 4).tolist()} "
                    f"gap={grip_gap * 1000:.1f}mm {self.grippers[arm_name].summary()}"
                )
        else:
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
        if self._dynamic_capture_active and self._dynamic_lift_peak:
            # Origin for the peak-hold metric (see `__init__`): the fruit's z
            # *before* the probe/belt-break, so the take-off's rise counts.
            self._dynamic_peak_z = z_before
        self._recentre_gripper(arm_name, sample)
        # Same re-anchor as before the hover: the close ran with no IK command
        # (assisted frame), so the integrator is still at the approach's last
        # command and the first test-lift step would otherwise jump.
        arm.sync_command_to_measured()
        # Slip compensation: verify the grip with a 1 cm test lift and, if the
        # fruit did not follow, squeeze harder and try again (the design calls for
        # slip detection with a regrasp). A fruit that slips usually sits too
        # low between the pads, which the firmer squeeze corrects.
        squeeze_gap: float | None = None
        for _regrasp in range(int(os.environ.get("FRUIT_REGRASPS", "3"))):
            probe = grasp_goal + np.array([0.0, 0.0, 0.010])
            # The grip was taken from a *moving* fruit; a coarse test lift (the
            # 0.5 rad/tick default) can work a marginal hold out before the
            # carry even starts. Testing it gently costs half a second.
            previous_test_step = arm.max_step
            if self._dynamic_capture_active:
                arm.max_step = min(
                    previous_test_step,
                    float(test_step_default),
                )
            try:
                if self._dynamic_capture_active:
                    # Tracked, force-limited squeeze + probe (P3 take-off fix).
                    # The historic probe commanded the *fixed* `grasp_goal`
                    # captured at the end of the close. The 48-tick hold then
                    # let the fruit travel ~50 mm downstream while the pads
                    # followed it, so the probe yanked the pads back upstream
                    # relative to the payload before lifting - the lift-slip
                    # class (A2/A4/A8, lost at the first lift) was lost here.
                    # Keep the pads on the fruit's measured centre with the
                    # same `v * lead` feed-forward as the close, probe 10 mm
                    # up along the tool axis, and spend the first ~0.1 s
                    # stepping the commanded gap 1 mm deeper while the tactile
                    # is under `FRUIT_DYNAMIC_TAKEOFF_FORCE` (the finger drives
                    # cap at 10 N/joint, so this is a force-limited pinch, not
                    # a crush).
                    probe_ticks = int(probe_ticks_default)
                    probe_lift = float(probe_lift_default)
                    lead_s = float(os.environ.get("FRUIT_DYNAMIC_TRACK_LEAD", "0.18"))
                    squeeze_max = float(
                        os.environ.get("FRUIT_DYNAMIC_TAKEOFF_SQUEEZE", "0.001")
                    )
                    squeeze_s = float(
                        os.environ.get("FRUIT_DYNAMIC_TAKEOFF_SQUEEZE_S", "0.10")
                    )
                    force_cap = float(
                        os.environ.get("FRUIT_DYNAMIC_TAKEOFF_FORCE", "20.0")
                    )
                    z_ramp = min_jerk_ramp(0.0, probe_lift, probe_ticks)
                    squeeze_ticks = max(1, int(round(squeeze_s / CONTROL_DT)))
                    squeeze_gap = float(grip_gap)
                    for _probe in range(probe_ticks):
                        fruit_now = np.asarray(self.spawner.position(sample), dtype=float)
                        dynamic_v = np.asarray(self.spawner.velocity(sample), dtype=float)
                        if self._force_servo:
                            # Servo mode: the squeeze follows the measured
                            # contact instead of the open-loop 1 mm ramp.
                            squeeze_gap = self._force_servo_step(
                                arm.spec.side, squeeze_gap
                            )
                        elif _probe < squeeze_ticks:
                            reading = self.tactile.read().get(arm.spec.side, _EMPTY_TACTILE)
                            if float(reading.normal_force) < force_cap:
                                squeeze_gap = max(
                                    float(grip_gap) - squeeze_max,
                                    squeeze_gap - squeeze_max / squeeze_ticks,
                                )
                        arm.ik_step(
                            arm.tcp_target_for_jaw(
                                fruit_now
                                + np.array(
                                    [
                                        0.0,
                                        float(dynamic_v[1]) * lead_s,
                                        self._pad_standoff(True, sample) + float(z_ramp[_probe]),
                                    ]
                                )
                            )
                        )
                        self.grippers[arm_name].follow_centre(
                            fruit_now,
                            np.asarray(arm.tcp_pose()[1], dtype=float),
                            float(squeeze_gap),
                        )
                        self._step_sim(1)
                        if self._dynamic_peak_z is not None:
                            self._dynamic_peak_z = max(
                                self._dynamic_peak_z,
                                float(self.spawner.position(sample)[2]),
                            )
                        self._dynamic_trace_sample(
                            "takeoff_probe", sample, arm, gripper, float(squeeze_gap)
                        )
                    # The carry and the release re-command `_closed_gap`; it has
                    # to be the depth the pads were actually left at, or they
                    # open the 1 mm squeeze again at the take-off and the grip
                    # goes slack exactly when the lift starts (the left-arm
                    # lift-slips: A2/A8 carry slip 345/354 mm with the take-off
                    # force steady at 4.3-4.5 N).
                    self._closed_gap[arm_name] = float(squeeze_gap)
                else:
                    for _ in range(40):
                        arm.ik_step(arm.tcp_target_for_jaw(probe))
                        self._step_sim(1)
            finally:
                arm.max_step = previous_test_step
            if float(self.spawner.position(sample)[2]) - z_before > 0.004:
                if self._dynamic_capture_active:
                    # Do *not* park the hand at a fixed point after the probe:
                    # the velocity-matched belt-clear below takes over from the
                    # moving frame. The historic `_settle_to_rest` stopped the
                    # pads relative to the world while the payload was still on
                    # the running belt - the same relative-motion shear this
                    # take-off exists to remove - so it is now opt-in
                    # (`FRUIT_DYNAMIC_LIFT_SETTLE=1` restores it for an A/B).
                    if os.environ.get("FRUIT_DYNAMIC_LIFT_SETTLE", "0") == "1":
                        self._settle_to_rest(arm, max_ticks=150)
                    break
                for _ in range(40):
                    arm.ik_step(arm.tcp_target_for_jaw(grasp_goal))
                    self._step_sim(1)
                break
            if self._dynamic_capture_active:
                # Keep the pads on the moving fruit through the failed probe:
                # the historic fixed `grasp_goal` return is the same
                # upstream yank the tracked probe removes, and the regrasp
                # below needs the payload still in the span.
                pass
            else:
                for _ in range(40):
                    arm.ik_step(arm.tcp_target_for_jaw(grasp_goal))
                    self._step_sim(1)
            if self._dynamic_capture_active:
                # A failed test lift after a *moving* close usually means the fruit
                # sat at the edge of the span (the close can only squeeze, not
                # re-centre). Open, re-centre on the fruit's measured position
                # while tracking (with the same `v * lead` feed-forward), and
                # close again with the live clamp before spending the attempt.
                quat_now = np.asarray(arm.tcp_pose()[1], dtype=float)
                if regrasp_keep:
                    # W1 re-seat in place: descend back onto the fruit's
                    # measured centre at the gap the failed probe left. The
                    # pads never leave the fruit, so a walking fruit cannot
                    # roll out of an open span (see the knob's note).
                    keep_gap = (
                        float(squeeze_gap)
                        if squeeze_gap is not None
                        else float(grip_gap)
                    )
                    for _ in range(40):
                        fruit_now = np.asarray(
                            self.spawner.position(sample), dtype=float
                        )
                        fruit_v_now = np.asarray(
                            self.spawner.velocity(sample), dtype=float
                        )
                        arm.ik_step(
                            arm.tcp_target_for_jaw(
                                fruit_now
                                + np.array(
                                    [0.0, 0.0, self._pad_standoff(True, sample)]
                                )
                                + np.array(
                                    [0.0, float(fruit_v_now[1]) * dynamic_lead_s, 0.0]
                                )
                            )
                        )
                        self.grippers[arm_name].follow_centre(
                            fruit_now, quat_now, keep_gap
                        )
                        self._step_sim(1)
                    self._force_servo_reset(arm_name)
                    if verbose:
                        say(
                            "[task]   dynamic regrasp: re-seated in place "
                            f"(gap {keep_gap * 1000:.1f} mm kept)"
                        )
                else:
                    for _ in range(40):
                        fruit_now = np.asarray(self.spawner.position(sample), dtype=float)
                        fruit_v_now = np.asarray(self.spawner.velocity(sample), dtype=float)
                        rot_now = _quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
                        tip = np.asarray(arm.jaw_centre(), dtype=float) + rot_now @ np.array(
                            [0.0, 0.0, finger_len]
                        )
                        desired_tip = fruit_now + np.array([0.0, 0.0, self._dynamic_pad_lift])
                        if float(np.linalg.norm(tip - desired_tip)) < catch_tol:
                            break
                        arm.ik_step(
                            arm.tcp_target_for_jaw(
                                fruit_now
                                + np.array([0.0, 0.0, self._pad_standoff(True, sample)])
                                + np.array([0.0, float(fruit_v_now[1]) * dynamic_lead_s, 0.0])
                            )
                        )
                        self.grippers[arm_name].follow_centre(fruit_now, quat_now, gap_open)
                        self._step_sim(1)
                    for gap in min_jerk_ramp(gap_open, grip_gap, 45):
                        fruit_now = np.asarray(self.spawner.position(sample), dtype=float)
                        fruit_v_now = np.asarray(self.spawner.velocity(sample), dtype=float)
                        arm.ik_step(
                            arm.tcp_target_for_jaw(
                                fruit_now
                                + np.array([0.0, 0.0, self._pad_standoff(True, sample)])
                                + np.array([0.0, float(fruit_v_now[1]) * dynamic_lead_s, 0.0])
                            )
                        )
                        self.grippers[arm_name].follow_centre(fruit_now, quat_now, float(gap))
                        self._step_sim(1)
                    # The regrasp re-seated the grip at `grip_gap`; re-engage
                    # the force servo on the new grip instead of returning its
                    # old gap.
                    self._force_servo_reset(arm_name)
                    if verbose:
                        say("[task]   dynamic regrasp: re-seated on the moving fruit")
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
            step = float(os.environ.get("FRUIT_REGRASP_STEP", "0.003"))
            if self._dynamic_capture_active:
                # Half the indexed step: the dynamic hold is already loaded by the
                # live-extent clamp, and three 3 mm steps can squeeze light fruit
                # straight out of the jaws (`logs/p2_smoke11` attempt 6).
                step = min(step, float(os.environ.get("FRUIT_DYNAMIC_REGRASP_STEP", "0.0015")))
            fingers = float(fingers) - step
            for _ in range(60):
                arm.set_gripper(fingers)
                self._step_sim(1)
        # The dynamic line's origin stays the pre-probe one (set above), the
        # indexed line re-bases here. A tapered fruit can be squeezed *up* into
        # the openarm hand during the close/hold (the kiwi rises ~0.4 m before
        # the belt-break, `logs/dyn_v5`), and the probe/belt-break then already
        # lift it clear. Re-basing the metric after those legs made a *held*
        # payload read as "fruit did not follow the gripper" (lift -0.11 m with
        # the in-hand pose constant and 4.4 N contact through the whole 0.5 s
        # carry) and dropped a fruit the hand was carrying; the pre-probe origin
        # alone was not enough, because the *final* z can still sit below it
        # when the carry descends to its nominal goal (`logs/dyn_v5/v6`), so the
        # dynamic metric is peak-hold over the take-off and first carry
        # (`_dynamic_peak_z`, `FRUIT_DYNAMIC_LIFT_PEAK`).
        if not self._dynamic_capture_active:
            z_before = float(self.spawner.position(sample)[2])
        if os.environ.get("FRUIT_LIFT_DEBUG") == "1":
            say(f"[task]   lift start: fruit_z={z_before:.4f} jaw_z={arm.jaw_centre()[2]:.4f} "
                f"grip={arm.finger_opening():.4f}")
        if self._dynamic_capture_active:
            # Velocity-matched belt-break (P3 take-off fix). A purely vertical
            # lift deletes the belt's 0.12 m/s of relative motion in the pads in
            # a few ticks - the same shear as the spawner's `stop`, already
            # measured to unseat the grip (`logs/p2_speed_006`) - and the
            # lift-slip class (A2/A4/A8) is lost at exactly the first lift. Ride
            # *with* the belt for `FRUIT_DYNAMIC_TAKEOFF_MATCH` seconds while
            # the lift takes the payload clear, then decelerate to the world
            # frame over `FRUIT_DYNAMIC_TAKEOFF_TRANS`; the friction cone only
            # has to absorb that gentle deceleration (~0.6 m/s^2 at the
            # defaults, well inside the carry budget). The reference starts at
            # the payload's *measured* along-belt velocity, so a payload the
            # probe already slowed down is not yanked back up to belt speed.
            #
            # Break the belt contact before the *monitored* carry leg: a
            # payload just plucked off a running belt is still pulled by the
            # surface until it clears (that take-off arrived as 1.05-1.15x
            # cone breaches with the peak at the leg start, `logs/p2_smoke8`),
            # and the carry-leg cone is about held transport, so the pluck is
            # contact work first.
            start_jaw = np.asarray(arm.jaw_centre(), dtype=float).copy()
            clearance = float(os.environ.get("FRUIT_DYNAMIC_CLEAR_LIFT", "0.05"))
            match_s = float(os.environ.get("FRUIT_DYNAMIC_TAKEOFF_MATCH", "0.20"))
            trans_s = float(os.environ.get("FRUIT_DYNAMIC_TAKEOFF_TRANS", "0.25"))
            # GEM-style tracking/interaction decomposition (opt-in): hold a
            # pure-tracking pre-phase of `FRUIT_DYNAMIC_TAKEOFF_TRACK` seconds
            # before the lift starts. The end-effector rides the belt with the
            # payload (zero relative motion, the interaction action is not yet
            # applied); the lift then starts from a grip that has settled at
            # zero load, and the velocity-matched lift/decel follows as before.
            # 0 keeps the shipped behaviour (the lift starts with the match).
            track_s = max(
                0.0, float(os.environ.get("FRUIT_DYNAMIC_TAKEOFF_TRACK", "0.0"))
            )
            # Staged first lift (v6 experiment 1, opt-in): instead of the single
            # 50 mm min-jerk ramp, move `FRUIT_DYNAMIC_RAMP_STEP` slowly, pause
            # to verify the force is still there, then finish over a longer
            # horizon. The horizontal belt-match profile (`match_s`/`trans_s`)
            # is unchanged; only the vertical profile is staged.
            ramp_book: dict | None = None
            if self._ramp_lift:
                ramp_step = min(max(self._ramp_step, 0.0), clearance)
                step_ticks = self._ramp_step_ticks
                pause_ticks = self._ramp_pause_ticks
                rest_ticks = self._ramp_rest_ticks
                z_ramp = np.concatenate(
                    [
                        min_jerk_ramp(0.0, ramp_step, step_ticks),
                        np.full(pause_ticks, ramp_step, dtype=float),
                        min_jerk_ramp(ramp_step, clearance, rest_ticks),
                    ]
                )
                ticks = step_ticks + pause_ticks + rest_ticks
                ramp_book = {
                    "step": ramp_step,
                    "step_ticks": step_ticks,
                    "pause": pause_ticks,
                    "sustained": 0,
                    "maintained": False,
                    "min_n": float("inf"),
                    "max_n": 0.0,
                    "lost_ticks": [],
                }
                self._ramp_state[arm_name] = ramp_book
            else:
                ticks = max(1, int(round((match_s + trans_s) / CONTROL_DT)))
                z_ramp = min_jerk_ramp(0.0, clearance, ticks)
            track_ticks = int(round(track_s / CONTROL_DT))
            correction = float(os.environ.get("FRUIT_DYNAMIC_TAKEOFF_CORR", "0.010"))
            fruit_v_now = np.asarray(self.spawner.velocity(sample), dtype=float)
            v_ref = float(fruit_v_now[1])
            if not np.isfinite(v_ref) or abs(v_ref) < 1e-6:
                v_ref = float(self._belt_speed_estimate())
            v_ref_start = float(v_ref)
            y_ref = float(start_jaw[1])
            previous_clear_step = arm.max_step
            # Gentle: the take-off must not yank the payload. A 0.5 rad/tick IK
            # step here threw a 6.8 cm orange out of the jaws during the pluck
            # (`logs/p2_smoke9`, 980 mm slip before the carry even started).
            arm.max_step = min(
                previous_clear_step, float(os.environ.get("FRUIT_DYNAMIC_CLEAR_STEP", "0.01"))
            )
            hold_gap = float(grip_gap if squeeze_gap is None else squeeze_gap)
            try:
                for i in range(track_ticks + ticks):
                    if i < track_ticks:
                        # Tracking only: full belt match, no lift.
                        z_cmd = float(start_jaw[2])
                    else:
                        t = (i - track_ticks) * CONTROL_DT
                        if trans_s > 0.0 and t >= match_s:
                            v_ref = v_ref_start * max(0.0, 1.0 - (t - match_s) / trans_s)
                        k = i - track_ticks
                        z_cmd = float(start_jaw[2]) + float(z_ramp[k])
                        if ramp_book is not None:
                            # Verify the load through the small first step and
                            # the pause: `lost_ticks` is a real loss (below
                            # `FRUIT_DYNAMIC_RAMP_FLOOR`), not a sensor dropout.
                            reading = self.tactile.read().get(
                                arm.spec.side, _EMPTY_TACTILE
                            )
                            force = float(reading.normal_force)
                            ramp_book["min_n"] = min(float(ramp_book["min_n"]), force)
                            ramp_book["max_n"] = max(float(ramp_book["max_n"]), force)
                            if force < self._ramp_floor:
                                ramp_book["lost_ticks"].append(k)
                            if (
                                step_ticks <= k < step_ticks + pause_ticks
                                and force >= self._verify_force
                            ):
                                ramp_book["sustained"] = (
                                    int(ramp_book["sustained"]) + 1
                                )
                    y_ref += v_ref * CONTROL_DT
                    fruit_now = np.asarray(self.spawner.position(sample), dtype=float)
                    # Bound the reference to the payload: a grip that slips
                    # moves the pads with the fruit instead of tearing away.
                    y_cmd = y_ref + float(
                        np.clip(float(fruit_now[1]) - y_ref, -correction, correction)
                    )
                    target = np.array(
                        [
                            float(fruit_now[0]),
                            y_cmd,
                            z_cmd,
                        ]
                    )
                    arm.ik_step(arm.tcp_target_for_jaw(target))
                    hold_gap = self._force_servo_step(arm_name, hold_gap)
                    self.grippers[arm_name].follow_centre(
                        fruit_now,
                        np.asarray(arm.tcp_pose()[1], dtype=float),
                        hold_gap,
                    )
                    self._step_sim(1)
                    if self._dynamic_peak_z is not None:
                        self._dynamic_peak_z = max(
                            self._dynamic_peak_z,
                            float(self.spawner.position(sample)[2]),
                        )
                    self._dynamic_trace_sample(
                        "takeoff", sample, arm, self.grippers[arm_name], hold_gap
                    )
            finally:
                arm.max_step = previous_clear_step
            if ramp_book is not None:
                pause = int(ramp_book["pause"])
                ramp_book["maintained"] = bool(
                    pause == 0
                    or int(ramp_book["sustained"]) >= max(1, pause - 2)
                )
            self._settle_to_rest(arm, max_ticks=120)
        self._cycle_mark("grip")
        self._carry(arm_name, sample, "grasp_lift")
        self._cycle_mark("lift")
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
        if (
            self._dynamic_capture_active
            and self._dynamic_lift_peak
            and self._dynamic_peak_z is not None
        ):
            # Peak-hold metric (dynamic path only, default on; see `__init__`).
            # "Held" is the payload's *motion while held* - the highest z it
            # reached through the probe/belt-break/first carry - not where it
            # ended up: a fruit squeezed up into the hand and carried back to a
            # lower nominal goal read a negative final lift while the hand was
            # still holding it (the A6 kiwi artifact). The indexed path keeps
            # the old final-z metric (its origin is re-based after the probe,
            # above).
            result.peak_lift = max(float(self._dynamic_peak_z), z_after) - z_before
        else:
            result.peak_lift = z_after - z_before
        result.grasped = result.peak_lift > 0.05
        if result.grasped:
            # Remember the configuration that worked: it is the best seed for the
            # next episode on this arm.
            self._grasp_cache[arm_name] = np.asarray(grasp_config, dtype=float).copy()
        for _ in range(20):
            result.max_tactile_force = max(
                result.max_tactile_force, self.tactile.read()[arm_name].normal_force
            )
            if self._active_session is not None:
                # Same fixed-step rule as the pre-pose: under the bimanual
                # session the app pump must not advance physics by a
                # wall-clock-dependent amount.
                SimulationManager.step(steps=1)
                app_utils.update_app(steps=0)
            else:
                app_utils.update_app(steps=1)
        # Indexed line: hold the queue (gate closed, belt stopped) while the arm
        # grasps, then re-open and re-start for the next attempt. A *dynamic* line
        # never stops - the rest of the fruit keep travelling and the ones that are
        # not taken simply pass the station. The OpenArm hand re-starts the belt
        # after the lift instead: the jaws carry the fruit for ~20 s of simulated
        # time, and holding the queue that long starves the next pick
        # (`logs/451`: a stalled tomato 27 cm short, then a target that never
        # arrived).
        if belt is not None and not dynamic_pick and not openarm:
            belt.stop()
        if belt is not None and openarm:
            belt.start()
        if verbose:
            say(f"[task] lift {result.peak_lift:+.4f} m, grasped={result.grasped}")
        if not result.grasped:
            result.notes.append("fruit did not follow the gripper")
            return result

        # 4. Carry to the output line and release. Each arm only serves the
        # conveyor on its own side (crossing the body is outside the workspace),
        # so the lane index decides which arm picks.
        self._carry(arm_name, sample, f"place{bin_index}")
        self._cycle_mark("place")
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
        #: Lowered place (v5 directive, phase A): set when `FRUIT_PLACE_LOW=1`
        #: runs the accompanied descent in the block below; read by the retreat
        #: and the landing trace after the release.
        place_low = False
        place_trace = None
        low_info = None
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
            #
            # `FRUIT_PLACE_LOW` (default 1) replaces the free drop with the
            # accompanied descent: the hand carries the fruit down to
            # `FRUIT_PLACE_LOW_CLEARANCE` above the belt (fingertip-bounded), and
            # the release ordering below then runs at that low pose. `=0`
            # restores the historical 10 cm drop bit-for-bit. The landing trace
            # (`FRUIT_PLACE_TRACE=1`) measures both modes identically.
            place_low = os.environ.get("FRUIT_PLACE_LOW", "1") == "1"
            if os.environ.get("FRUIT_PLACE_TRACE", "0") == "1":
                place_trace = self._place_trace_start(
                    arm_name, sample, self.cfg.output_belt_drop_points[bin_index]
                )
            if place_low:
                centre, low_info = self._place_low(
                    arm_name, sample, centre, quat, gap, place_trace
                )
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
                            self._place_probe(place_trace, sample, "relax", _index, float(value))
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
                            self._place_probe(place_trace, sample, "relax", _index, float(value))
                gap = relax_gap
            for _index in range(max(0, int(os.environ.get("FRUIT_RELEASE_DWELL", "20")))):
                gripper.follow_centre(centre, quat, gap)
                self._step_sim(1)
                if release_debug:
                    self._release_probe(arm_name, sample, trace, "dwell", _index, gap)
                self._place_probe(place_trace, sample, "dwell", _index, gap)
            for _index, value in enumerate(min_jerk_ramp(gap, release_gap, 40)):
                gripper.follow_centre(centre, quat, float(value))
                for _ in range(3):
                    self._step_sim(1)
                    if release_debug:
                        self._release_probe(arm_name, sample, trace, "pads", _index, float(value))
                    self._place_probe(place_trace, sample, "pads", _index, float(value))
            self._closed_gap[arm_name] = None
            self._force_servo_reset(arm_name)
            self._gripper_offset[arm_name] = None
            self._grip_quat[arm_name] = None
            self._grip_centre[arm_name] = None
        for _index, value in enumerate(min_jerk_ramp(fingers, arm.OPEN, 16)):
            arm.set_gripper(float(value))
            for _ in range(3):
                self._step_sim(1)
                if os.environ.get("FRUIT_RELEASE_DEBUG", "0") == "1":
                    self._release_probe(arm_name, sample, trace, "arm", _index, float(value))
                self._place_probe(place_trace, sample, "arm", _index, float(value))
        self._cycle_mark("release")
        # Retreat. Once the pads are open the fruit is on its own, and holding
        # station for another second is what the release `settle` used to do (60
        # ticks after a 48-tick finger ramp). Lifting the hand away instead reads
        # as "letting go" in the video. Measured on v3 at 0.08 m: 5/5,
        # 36.2 s/attempt (the no-retreat run is 36.0-36.1 s) and the release
        # peaks are unchanged (1.13-1.33 m/s in both, `logs/693`) - but the
        # upward IK move from the far place pose is bought with the wrist, and
        # the A4 left return then swings to 110.2 deg (`logs/694`, against
        # 64.3 deg with the plain settle). **Default 0** for that reason;
        # `FRUIT_RELEASE_RETREAT=0.08` turns it on if the carry attitude is fixed.
        # The lowered place ends close to the belt, so it raises the hand by
        # `FRUIT_PLACE_LOW_RETREAT` (8 cm) before the next cycle instead.
        retreat = float(os.environ.get("FRUIT_RELEASE_RETREAT", "0.0"))
        if place_low:
            retreat = float(os.environ.get("FRUIT_PLACE_LOW_RETREAT", "0.08"))
        if retreat > 0.0:
            # Re-anchor the drive target on the measured arm first: the pads push
            # the arm during the release (`logs/630`), and the first retreat step
            # would otherwise command the stale target-to-measured difference in
            # one tick.
            self._catch_up_drive(arm_name)
            start_tcp = arm.tcp_position().copy()
            for alpha in min_jerk_ramp(0.0, 1.0, 60):
                arm.ik_step(start_tcp + np.array([0.0, 0.0, retreat * float(alpha)]))
                self._step_sim(1)
                if os.environ.get("FRUIT_RELEASE_DEBUG", "0") == "1":
                    self._release_probe(arm_name, sample, trace, "retreat", 0, float(alpha))
                self._place_probe(place_trace, sample, "retreat", 0, float(alpha))
        else:
            for _ in range(60):
                self._step_sim(1)
                if os.environ.get("FRUIT_RELEASE_DEBUG", "0") == "1":
                    self._release_probe(arm_name, sample, trace, "settle", 0, 0.0)
                self._place_probe(place_trace, sample, "settle", 0, 0.0)
        self._cycle_mark("return")
        if os.environ.get("FRUIT_RELEASE_DEBUG", "0") == "1":
            self._release_report(arm_name, sample, trace)
        if place_trace is not None:
            self._place_trace_report(place_trace, low_info)
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

    # ------------------------------------------------------------------ #
    # Lowered place / landing trace (v5 directive, phase A)
    # ------------------------------------------------------------------ #
    def _place_low(self, arm_name, sample, centre, quat, gap, trace=None):
        """Descend with the payload to a small clearance above the output belt.

        The shipped place (since v5-A, `FRUIT_PLACE_LOW=1`): the historical 10 cm
        free-drop release is replaced by an accompanied descent - the hand (and
        the payload held in it) goes down until the fruit's lowest point stands
        `FRUIT_PLACE_LOW_CLEARANCE` above the output-belt top (measured: the
        OpenArm finger plates bind first at ~50 mm, so that is the effective
        clearance), then the release ordering runs at that pose, so the pads open
        a few centimetres over the surface instead of ten. The stop condition
        reads the *fruit's* measured lowest point every tick, so a hand
        that stalls or a payload that slips down relative to the hand stops the
        leg at the honest height. The OpenArm jaw hand's descent is additionally
        capped by the measured fingertip height (`FRUIT_PLACE_LOW_FINGER_MARGIN`
        above the belt), so the visible fingers cannot be driven into the belt;
        `FRUIT_PLACE_LOW_MAX_DROP` bounds the leg. The descent is payload-carrying
        motion (slow and vertical), so it stays inside the friction cone.

        Returns `(pad/jaw centre where the leg stopped, info dict)`. Reached on the
        shipped line (`FRUIT_PLACE_LOW` default 1); `=0` restores the historical
        free-drop release bit-for-bit.
        """
        floor = float(self.cfg.output_belt_top_z)
        clearance = float(os.environ.get("FRUIT_PLACE_LOW_CLEARANCE", "0.025"))
        ceiling = float(os.environ.get("FRUIT_PLACE_LOW_MAX_DROP", "0.30"))
        margin = float(os.environ.get("FRUIT_PLACE_LOW_FINGER_MARGIN", "0.005"))
        steps = max(4, int(os.environ.get("FRUIT_PLACE_LOW_STEPS", "40")))
        arm = self.arms[arm_name]
        gripper = self.grippers[arm_name]
        hand_is_jaw = getattr(gripper, "kind", "") == "openarm"
        down = np.array([0.0, 0.0, -1.0])
        fruit = np.asarray(self.spawner.position(sample), dtype=float)
        bottom = float(fruit[2]) - self._shape_support(sample, down)
        info = {
            "target": clearance,
            "need": bottom - floor - clearance,
            "drop": 0.0,
            "finger_budget": None,
            "finger_bound": False,
            "clearance": bottom - floor,
            "residual": 0.0,
            "ticks": 0,
        }
        need = float(info["need"])
        if need <= 1e-4:
            return np.asarray(centre, dtype=float), info
        # Optional wrist hold for the vertical descent, applied *before* the
        # fingertip floor is measured: `FRUIT_PLACE_LOW_TUCK_DEG` rotates the tool
        # about its own closing axis so the long finger plates swing up instead of
        # hanging below the payload (the shipped attitude leaves them ~43 mm below
        # the fruit bottom, which is what stops the descent). Both knobs are off by
        # default, and the tuck is a **measured negative**: +60 deg lifts the
        # payload during the rotation (a held object is kinematically held, so the
        # hand cannot re-seat it in the air - the fruit stopped 142 mm above the
        # belt), -60 deg reaches 35-43 mm but the fruit then does not ride the belt
        # (settle never reached, skid -214..-258 mm, `logs/place_low/04/05`). The
        # place reach was also a measured constraint (a full-leg pin stalled the
        # carry ~12 cm short, `logs/444`).
        pinned = None
        tuck_deg = float(os.environ.get("FRUIT_PLACE_LOW_TUCK_DEG", "0.0"))
        if hand_is_jaw and (
            tuck_deg != 0.0 or os.environ.get("FRUIT_PLACE_LOW_HOLD_QUAT", "0") == "1"
        ):
            q0 = np.asarray(arm.tcp_pose()[1], dtype=float).copy()
            if tuck_deg != 0.0:
                q0 = _quat_about_axis(q0, _quat_matrix(q0)[:, 1], np.deg2rad(tuck_deg))
            pinned = q0
            arm.hold_quaternion = pinned
            if tuck_deg != 0.0:
                jaw_now = np.asarray(arm.jaw_centre(), dtype=float).copy()
                for _ in range(max(0, int(os.environ.get("FRUIT_PLACE_LOW_TUCK_SETTLE", "30")))):
                    arm.ik_step(arm.tcp_target_for_jaw(jaw_now))
                    self._step_sim(1)
                    if trace is not None:
                        self._place_probe(trace, sample, "tuck", 0, gap)
                fruit = np.asarray(self.spawner.position(sample), dtype=float)
                bottom = float(fruit[2]) - self._shape_support(sample, down)
                info["need"] = float(bottom - floor - clearance)
                need = float(info["need"])
        drop = min(need, ceiling)
        jaw0 = None
        if hand_is_jaw:
            jaw0 = np.asarray(arm.jaw_centre(), dtype=float).copy()
            finger_budget = self._fingertip_lowest_z(arm_name) - floor - margin
            info["finger_budget"] = float(finger_budget)
            if finger_budget < drop:
                drop = max(0.0, float(finger_budget))
                info["finger_bound"] = True
        info["drop"] = float(drop)
        # The binding friction-cone direction of a vertical descent is the
        # *upward* deceleration at the end (gravity hangs the payload from the
        # faces), so the profile is budgeted on +z exactly as `grasp_lift` is;
        # `FRUIT_PLACE_LOW_VMAX/AMAX` only tighten it further.
        limits = TrajectoryLimits.from_env(CONTROL_DT)
        limits.v_max = min(limits.v_max, float(os.environ.get("FRUIT_PLACE_LOW_VMAX", "0.30")))
        limits.a_max = min(limits.a_max, float(os.environ.get("FRUIT_PLACE_LOW_AMAX", "2.0")))
        mu_eff = float(os.environ.get("FRUIT_MU_SAFETY", "0.6")) * float(gripper.mu)
        limits = limits.limited_by_cone(np.array([0.0, 0.0, 1.0]), mu_eff)
        profile = jerk_limited(drop, limits)
        steps = max(steps, len(profile[0]))
        info["a_peak"] = float(np.abs(profile[2]).max()) if len(profile[2]) else 0.0
        info["cone_budget"] = float(accel_budget(np.array([0.0, 0.0, 1.0]), mu_eff))
        base = np.asarray(centre, dtype=float).copy()
        rot = _quat_matrix(quat)
        offset_tool = self._gripper_offset.get(arm_name)
        offset_tool = None if offset_tool is None else np.asarray(offset_tool, dtype=float)
        follow_arm = offset_tool is not None
        if follow_arm and not hand_is_jaw:
            target0 = base - rot @ offset_tool
            follow_arm = bool(
                np.linalg.norm(target0 - np.asarray(arm.tcp_position(), dtype=float))
                < float(os.environ.get("FRUIT_RELEASE_ARM_TRACK", "0.20"))
            )
        residual = 0.0
        placed = base
        try:
            for _index, dz in enumerate(min_jerk_ramp(0.0, drop, steps)):
                if hand_is_jaw:
                    arm.ik_step(
                        arm.tcp_target_for_jaw(
                            jaw0 + np.array([0.0, 0.0, -float(dz)])
                        )
                    )
                    placed = np.asarray(arm.jaw_centre(), dtype=float)
                    gripper.follow_centre(placed, quat, gap)
                else:
                    placed = np.asarray(
                        gripper.follow_centre(
                            base + np.array([0.0, 0.0, -float(dz)]), quat, gap
                        ),
                        dtype=float,
                    )
                    self._grip_centre[arm_name] = placed
                    if follow_arm:
                        residual = max(
                            residual,
                            abs(arm.ik_step(arm.tcp_target_for_jaw(placed - rot @ offset_tool))),
                        )
                self._step_sim(1)
                info["ticks"] += 1
                if trace is not None:
                    self._place_probe(trace, sample, "lower", _index, gap)
                fruit_now = np.asarray(self.spawner.position(sample), dtype=float)
                bottom_now = float(fruit_now[2]) - self._shape_support(sample, down)
                info["clearance"] = bottom_now - floor
                if info["clearance"] <= clearance + 1e-4:
                    break
        finally:
            if pinned is not None:
                arm.hold_quaternion = None
        info["residual"] = float(residual)
        if hand_is_jaw:
            placed = np.asarray(arm.jaw_centre(), dtype=float)
        if os.environ.get("FRUIT_PLACE_LOW_DEBUG", "0") == "1" or info["finger_bound"]:
            say(
                f"[task] place low: bottom {bottom * 1000:.0f} -> "
                f"{info['clearance'] * 1000:.0f} mm (target {clearance * 1000:.0f}), "
                f"drop {info['drop'] * 1000:.0f}/{need * 1000:.0f} mm"
                + (
                    f", FINGER FLOOR budget {info['finger_budget'] * 1000:.0f} mm"
                    if info["finger_bound"]
                    else ""
                )
                + f", residual {info['residual'] * 1000:.1f} mm, {info['ticks']} ticks"
            )
        return placed, info

    def _place_trace_start(self, arm_name, sample, target) -> dict:
        """Begin one place's landing trace [diagnostic, `FRUIT_PLACE_TRACE=1`].

        The trace is measurement only: it reads the fruit's pose/velocity and the
        logger writes the landing (release height, impact, bounce, roll, settle,
        final accuracy). It never commands anything, and fruit-pose reads are the
        safe readback class (AGENTS section 2), so a trace-on run measures the
        same scenario as a trace-off one.
        """
        return {
            "arm": arm_name,
            "sample": sample,
            "target": np.asarray(target, dtype=float).copy(),
            "t0": float(self._sim_time()),
            "samples": [],
        }

    def _place_probe(self, trace, sample, stage: str, index: int, gap: float = 0.0) -> None:
        """One landing-trace sample: the fruit's lowest point, pose and velocity."""
        if trace is None:
            return
        fruit = np.asarray(self.spawner.position(sample), dtype=float)
        vel = np.asarray(self.spawner.velocity(sample), dtype=float)
        bottom = float(fruit[2]) - self._shape_support(sample, np.array([0.0, 0.0, -1.0]))
        trace["samples"].append(
            (
                float(self._sim_time()),
                stage,
                int(index),
                bottom,
                float(fruit[0]),
                float(fruit[1]),
                float(fruit[2]),
                float(vel[0]),
                float(vel[1]),
                float(vel[2]),
            )
        )

    def _place_trace_report(self, trace, info=None) -> None:
        """Summarise one place's landing [diagnostic, `FRUIT_PLACE_TRACE=1`].

        `release` is the last sample with the pads still closed (before the
        relax/dwell/pads opening stages; a raw `vz < 0` test would fire inside a
        lowered descent), `impact` the largest downward speed after the release,
        `bounce` the highest lowest-point after first contact above the belt top,
        `roll` the along-belt travel from the release to the end of the window,
        `skid` the part of that travel the fruit did *not* get from riding the
        belt, `settle` the first time the fruit tracks the belt (|v - belt| <
        0.05 m/s and |vz| < 0.03 m/s) for 10 consecutive samples. `off` is the
        final position against the commanded place point.
        """
        samples = trace["samples"]
        if not samples:
            return
        floor = float(self.cfg.output_belt_top_z)
        belt_v = float(self.cfg.output_belt_speed)
        # Release: the last sample while the pads are still closed at the place
        # pose. The fall detector alone cannot define this on the lowered place -
        # the descent itself moves the payload down at up to 0.3 m/s, so `vz < 0`
        # fires inside the descent. The stage labels are the honest boundary: the
        # last sample before the relax/dwell/pads opening begins.
        stage_release = len(samples)
        for index, sample in enumerate(samples):
            if sample[1] in ("relax", "pads", "arm"):
                stage_release = index
                break
        release_index = max(0, stage_release - 1)
        release = samples[release_index]
        first_fall = release_index
        for index in range(release_index, len(samples)):
            if samples[index][9] < -0.05:
                first_fall = index
                break
        release_bottom = float(release[3]) - floor
        impact = min(float(sample[9]) for sample in samples[first_fall:])
        contact = None
        for index in range(first_fall, len(samples)):
            if samples[index][3] - floor <= 0.006:
                contact = index
                break
        bounce = 0.0
        settle_t = float("nan")
        if contact is not None:
            bounce = max(float(sample[3]) for sample in samples[contact:]) - floor
            streak = 0
            for sample in samples[contact:]:
                speed = np.hypot(
                    float(sample[7]) - belt_v, float(sample[8])
                )
                if speed < 0.05 and abs(float(sample[9])) < 0.03:
                    streak += 1
                    if streak >= 10:
                        settle_t = float(sample[0]) - float(release[0])
                        break
                else:
                    streak = 0
        final = samples[-1]
        roll = float(final[4]) - float(release[4])
        # Belt-relative travel: how much of the along-belt motion the fruit did
        # *not* get from simply riding the surface (a drop skids/slides, a
        # settled fruit tracks the belt). Same sign as the belt, +X.
        skid = roll - belt_v * (float(final[0]) - float(release[0]))
        target = np.asarray(trace["target"], dtype=float)
        off_xy = np.array([float(final[4]), float(final[5])]) - target
        on_belt = bool(self.cfg.on_output_belt(np.array([final[4], final[5], final[6]])))
        low_text = ""
        if info is not None:
            low_text = (
                f" clearance={info['clearance'] * 1000:.1f}mm"
                f" target={info['target'] * 1000:.1f}mm"
                f" drop={info['drop'] * 1000:.1f}mm"
                + (
                    f" FINGER_FLOOR(budget {info['finger_budget'] * 1000:.0f}mm)"
                    if info["finger_bound"]
                    else ""
                )
                + f" ik={info['residual'] * 1000:.1f}mm"
                + (
                    f" a={info['a_peak']:.2f}/{info['cone_budget']:.2f}m/s^2"
                    if "a_peak" in info
                    else ""
                )
            )
        say(
            f"[task]   place trace {trace['arm']}: release_bottom={release_bottom * 1000:.1f}mm "
            f"impact={impact:.2f}m/s bounce={bounce * 1000:.1f}mm roll={roll * 1000:+.0f}mm "
            f"skid={skid * 1000:+.0f}mm settle={settle_t * 1000:.0f}ms "
            f"final=({final[4]:.3f},{final[5]:+.3f},{final[6]:.3f}) "
            f"off=({off_xy[0] * 1000:+.0f},{off_xy[1] * 1000:+.0f})mm on_belt={on_belt}"
            f"{low_text}"
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

    def _approach(self, arm, jaw_target, verbose: bool = False,
                  v_max: float | None = None, a_max: float | None = None) -> None:
        """Descend to the grasp pose; `FRUIT_APPROACH_MODE` picks how it is referenced.

        `v_max`/`a_max` override the profile limits for this leg (the moving
        catch uses its own `FRUIT_DYNAMIC_APPROACH_VMAX`, still under the motion
        gate's budget); the default is the shipped `FRUIT_APPROACH_*` value.
        """
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
            limits.v_max = (
                float(os.environ.get("FRUIT_APPROACH_VMAX", "0.03"))
                if v_max is None else float(v_max)
            )
            limits.a_max = (
                float(os.environ.get("FRUIT_APPROACH_AMAX", "0.8"))
                if a_max is None else float(a_max)
            )
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
            limits.v_max = (
                float(os.environ.get("FRUIT_APPROACH_VMAX", "0.03"))
                if v_max is None else float(v_max)
            )
            limits.a_max = (
                float(os.environ.get("FRUIT_APPROACH_AMAX", "0.8"))
                if a_max is None else float(a_max)
            )
            positions, velocities, _ = jerk_limited(distance, limits)
            direction = delta / distance
            for i, value in enumerate(positions):
                arm.ik_step(
                    start + direction * float(value),
                    target_velocity=direction * float(velocities[i]),
                )
                self._step_sim(1)
                self._tick_frame()  # pure render; no-op unless recording
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
