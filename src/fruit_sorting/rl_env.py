"""RL rollout environment around the sorting cell's hybrid pick-and-place loop.

P4 (RL post-training): this is the environment the diffusion policy is rolled out
in and scored by, and the one the reward-weighted fine-tune consumes. It is a
wrapper, not a rewrite - the contact work stays `PickAndPlaceTask.grasp_carry_place`
(unchanged), the conveyor/scene stay the shipped build, and `tasks.py` is frozen
at the revision this module asserts by md5.

Two presentations:

``handoff``
    Reproduces ``scripts/60_eval_policy.py`` (the hybrid evaluator) step for step,
    for the P0a check only: the policy drives for ``approach_steps`` control
    iterations, then the fruit is handed to the jaw by teleport (the station
    hand-off) and the deterministic primitive cycle runs. The policy's approach
    does not decide the outcome - which is exactly what P0b measures.

``direct``
    No station hand-off teleport: the fruit keeps moving on the belt. The
    primitive cycle is *triggered by the policy's own close command* - when the
    policy commands ``finger < 0.030`` while the jaw is within 0.06 m of the
    fruit - which is the causal interface the RL work needs. The close trigger
    is the same ``finger < 0.030`` test the hybrid evaluator uses for its
    ``GraspPrimitive`` branch, and the 0.06 m test is the same 2-D
    (cross-belt) proximity test the harness uses for the modelled attach.

    ``direct`` starts where the demonstrations do: every recorded `demos_v7`
    episode begins in the scripted pick's wait loop, with the arm already at the
    calibrated grasp pose (`|q-grasp| <= 0.011 rad` at frame 0; no demo frame
    comes closer than 0.220 rad to the ready pose), because the pre-pose before
    it is not recorded. The env therefore parks both arms at ready (like
    `go_ready()` before every collected episode) and puts the active arm at the
    grasp pose. Starting `direct` at the ready pose - as the harness does, and
    as this env did before the P4 Step-1 diagnostic - hands the policy an
    observation no demonstration ever produced.

``direct`` + ``dagger``
    Adds the scripted pick-phase controller as an HG-DAgger expert
    (`ExpertConfig`): each decision point's label is the scripted command for
    that state, and the expert takes control for a short window when the policy
    deviates from it.

``direct`` + ``rtc``
    RTC-style asynchronous chunking (``FRUIT_RTC=1``, see
    ``policy.runtime.RTCSettings``): one action executes per control step and the
    next chunk is sampled *interleaved* with execution (a few denoising steps per
    control step over ``inference_delay`` control steps), its first
    ``inference_delay`` actions frozen to the old chunk's tail and the rest
    soft-inpainted so the boundary is continuous. Default off; the shipped
    synchronous path is unchanged. ``--execute-steps`` is the chunk turnover
    period in both paths, so ``1/2/4`` is the same tight-loop knob.

Observation interface (identical to training): the head-camera frame is rendered
and read every 4 physics ticks (30 Hz), downsampled and buffered by
``PolicyRunner.push_frame``; proprioception is all 22 joint positions + the finger
opening + the two tactile forces (25-D); the goal is the 8-D
``[position(3), velocity(3), diameter, bin_index]`` vector the demonstrations
recorded. Action interface: ``action[:7]`` are the active arm's joint targets,
``action[7]`` is the finger opening clipped to ``[0, 0.044]``, and ``action[8]``
is only recorded (mirrored from ``action[7]``) exactly like the harness.

Mechanics that must not be broken (see AGENTS.md section 3b):
* every advance is ``SimulationManager.step`` + ``update_app(steps=0)``; this
  file never calls ``update_app(steps=N)``;
* ``RenderingManager.render()`` runs before every camera read;
* diagnostics default off and are read-only;
* one simulator at a time is the caller's job.

The manifest written per run records the presentation, ablation, reward config,
camera resolution, checkpoint and the md5 of every source that decided the run,
and the constructor refuses to build when ``src/fruit_sorting/tasks.py`` is not
the revision the environment was validated against.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field

import numpy as np

from .motion import min_jerk_ramp
from .policy.trigger import TriggerSettings, should_fire

#: md5 of `src/fruit_sorting/tasks.py` this environment was validated against.
#: History: `0bc3253a` was the P2/P3 frozen revision; `e553b34e` is that
#: revision plus the P4 recorder-semantics fix (record the commanded joint
#: target, not the measured q - see WORKLOG "P4: the recorder now records the
#: command"); `4e17dd1d` is the revision the RTC phase (P4 fast closed loop)
#: pinned for its A/B - every run's manifest carries it, and
#: `scripts/129_rtc_report.py` cross-checks the source set across runs. A run on
#: a different tasks.py is a different scenario, so the constructor refuses to
#: start instead of writing a manifest that cannot be tied to a tree.
#: `e871231a` is the v5 revision (force-servo knobs + the dynamic lift-origin
#: fix); the B lane's trigger A/B runs on it with `FRUIT_DYNAMIC_FORCE_SERVO`
#: off/on, so the pin was moved from 4e17dd1d when that tree froze.
#: `7decbbc7` was the v6 revision (contact-verification dwell + staged lift,
#: deeper finger face; both default off). `ae841a17` is the v7 revision: the
#: dynamic lift metric is peak-hold (`FRUIT_DYNAMIC_LIFT_PEAK`, default on only
#: while a dynamic capture is active); the indexed path and all control are
#: unchanged, so the policy loop (which never sets `_dynamic_capture_active`)
#: runs the same scenario.
#: `085256b2` is the v5-A integrated revision: the shipped place is the lowered,
#: accompanied descent (`FRUIT_PLACE_LOW=1`, the new default; `=0` restores the
#: historical free drop bit-for-bit). The indexed line's descents are unchanged
#: and the policy loop (which never sets `_dynamic_capture_active`) runs the
#: same scenario with the lowered place at the end of `grasp_carry_place`; the
#: D-entry canary re-measured the hybrid policy path on it (`logs/d_v5entry/`).
#: `3003679b` was the first D2-integrated revision (compliant soft pads opt-in,
#: default off). The D2 lane kept iterating while the entry work ran, and the
#: pin moved with it - it is now `25281bb1`, the revision the second place-low
#: canary ran on (7/10 PASS; `logs/d_v5entry/08_canary_placelow_d2.*`). The
#: re-pin smoke for this revision is queued in `entry_batch3` because the D2
#: lane holds the simulator. The D1 baseline was measured on the earlier
#: `29db6b64` merge and is bit-identical to the pre-merge `085256b2` outputs.
#: The F1 lane moved `tasks.py` again (dynamic line the shipped default, faster
#: dynamic profiles, cycle report), so the pin is now `d47be123`, the revision
#: the F1 acceptance ran on (`logs/fast/11_accept_v7fast_verified.log`; the F2
#: bimanual lane must move it again when it edits `tasks.py`).
#: The P2b lane (left-handover diagnosis + fix) moved `tasks.py`; the pin below
#: is the P2b revision measured in `logs/p2b/` (diagnostic revision first, then
#: the frozen fix revision - the hash follows the file).
#: The final-review pass (2026-10-08) touched only the `_dynamic_pick_mode`
#: docstring (the stale "ceiling is 8/10" -> the Gate-19 9/10), so the pin moved
#: with the docstring-only revision (`2574ceac...`); no control logic changed,
#: and the P2b/G measurements remain valid for this tree.
#: The v9/V1 scattered-supply lane (2026-10-08) changed `select_target` /
#: `_balance_arm`: the moving catch now refuses candidates inside
#: `_dynamic_select_floor()` and takes the farthest-upstream eligible fruit
#: (the documented schedule semantics; the lane path takes the nearest usable
#: one). The policy handover keeps the indexed primitive unless
#: `FRUIT_DYNAMIC_PICK=1`, but the pin follows the file as always.
#: The v9/V3 integration (2026-10-09) froze the V2 two-line tree: the
#: `_prepare_two_line_stations` setup now steps physics explicitly
#: (`SimulationManager.step(10)` + `update_app(0)`, AGENTS section 3b) instead
#: of the non-fixed `update_app(steps=10)`, the two-line scheduler is the
#: explicit opt-in `FRUIT_BIARM_TWOLINE=1` (the pre-registration's decision
#: rule: 1.08x placed/min missed the 1.25x bar), and the station docstrings
#: state the shipped 0.10 m separation. The dynamic-path measurements on this
#: revision are `logs/v3/`; the pin is the frozen revision.
#: The W1/W2 lanes (2026-10-09) then moved `tasks.py` twice (the two-line grip
#: profile, the W2 clearance levers - all measured in `logs/w1`/`logs/w2`), and
#: the W3 lane (2026-10-10) added the pure per-arm grade routing
#: (`FRUIT_GRADE_ROUTING`), the capture token (wave two-line default: one arm in
#: its capture window at a time), allowed the recorder on the two-line branch,
#: and bridged the recorder render; the pin follows the file as always
#: (`logs/w3/`).
#: The W4 gate-30 pass (2026-10-10) added one comment at `_biarm_park`'s broad
#: `except` (a swallowed `AttemptTimeout` is safe because the per-attempt
#: deadline is already cleared); comment-only, so the control path is unchanged
#: and the W3 measurements carry (`logs/w4/`).
#: The W5-C mechanism-screens lane (2026-10-10) added the default-off
#: probe/belt-break x-pin (`FRUIT_DYNAMIC_TAKEOFF_LOCK_X`, `69823dc1`); with the
#: env unset the control path is byte-identical (the cfg0 screen reproduced the
#: W4 `[fruit]` stream; `logs/w5/30_cfg0_rate1.log` vs
#: `logs/w4/20_dense_repeat.log`), so the W3/W4 measurements carry and the H5
#: direct-path trace rides the same branch as `logs/w4/13_direct_v13s_pinned.log`.
#: The W6-C speed-lever lane (2026-10-11) added two default-off, two-line-only
#: knobs (`FRUIT_BIARM_PARK_EARLY` - the park-gate lever; `FRUIT_BIARM_PREFETCH`
#: - L1 prefetch/reserve) plus a prefetch-gated handover log line; with the
#: envs unset the single-arm control path is byte-identical (the acceptance
#: fingerprint matches and the two-line baseline stream reproduces;
#: `logs/w6/`), so the W5-C measurements carry and the pin follows the file as
#: always.
TASKS_MD5 = "fa9594fb32e3518ad7968d3cc27604d1"

#: Repository root, derived from this file (`src/fruit_sorting/rl_env.py`).
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

#: Sources whose md5 goes into the run manifest (mirrors 40_collect_demos.py's
#: shard manifest, plus this file and the waypoints it moves the arms with, plus
#: the policy runtime that decided the actions - the RTC phase needs the sampler
#: code pinned alongside the checkpoint).
_MANIFEST_SOURCES = (
    "src/fruit_sorting/tasks.py",
    "src/fruit_sorting/assets.py",
    "src/fruit_sorting/conveyor.py",
    "src/fruit_sorting/scene.py",
    "src/fruit_sorting/fruits.py",
    "src/fruit_sorting/control.py",
    "src/fruit_sorting/rl_env.py",
    "src/fruit_sorting/policy/runtime.py",
    "src/fruit_sorting/policy/diffusion.py",
    "src/fruit_sorting/policy/trigger.py",
    "configs/waypoints.json",
    "configs/motion_reference.json",
)


def _md5(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.md5(handle.read()).hexdigest()
    except OSError:
        return ""


@dataclass
class RewardConfig:
    """Terminal-only reward (the Oracle's recipe): no shaping.

    ``R = success_value * (1 - time_penalty * T / horizon)`` on success, else 0.
    ``T`` is the number of *policy-phase control steps* - the loop iterations the
    policy took before the scripted primitive decided the episode, which is the
    budget `horizon=1500` refers to (the hybrid evaluator's own loop). It is not
    the total simulated cycle time: the primitive then spends ~3,000 more scripted
    ticks whose length the policy barely influences, and including them would
    clamp every success to the same ``0.8`` and erase the time gradient. The
    callers log both (`ticks=` total cycle time, `decision=` policy steps).
    """

    success_value: float = 1.0
    time_penalty: float = 0.2
    horizon: int = 1500

    def compute(self, success: bool, ticks: float) -> float:
        if not success:
            return 0.0
        t = min(max(float(ticks), 0.0), float(self.horizon))
        return float(self.success_value) * (
            1.0 - float(self.time_penalty) * t / float(self.horizon)
        )


@dataclass
class ExpertConfig:
    """DAgger expert: the scripted pick-phase controller, run *env-side*.

    Enabled with ``--dagger`` (``direct`` presentation only). At every policy
    decision point the scripted line's command for the current state is computed
    as the label: hold the calibrated grasp pose while the fruit is outside the
    tracking window, then track the fruit's measured centre and ramp the pads
    closed (the same window and ramp `PickAndPlaceTask` uses, read from the same
    env knobs). If the policy's own action deviates from that label by more than
    ``tolerance`` rad - or closes the finger before the window opens - the expert
    takes control for ``window_steps`` policy steps. The recorded ``action`` is
    always the expert label (standard DAgger aggregation: states from the policy,
    labels from the expert); the policy's own action is recorded alongside as
    ``policy_action``.
    """

    tolerance: float = 0.35
    #: How many 4-tick policy steps the expert holds control after a deviation.
    window_steps: int = 15


@dataclass
class StepResult:
    """Result of one ``act`` call: terminal reward, done flag, outcome info."""

    obs: dict
    reward: float
    done: bool
    info: dict = field(default_factory=dict)


def carry_and_release(arm, cfg, bin_index: int, advance, steps: int = 220) -> None:
    """Post-grasp primitive copied from ``scripts/60_eval_policy.py``.

    The same Cartesian path to the output-belt drop point, then the pads open
    over the moving belt. Only used by the ``direct`` path's fallback below: the
    task's own ``grasp_carry_place`` already carries and releases, so this is
    the harness helper re-run when a grasp did not end on the output belt.
    """
    px, py = cfg.output_belt_drop_points[bin_index]
    goal = np.array([px, py, cfg.output_place_z])
    for _ in range(steps):
        arm.ik_step(arm.tcp_target_for_jaw(goal))
        advance(1)
        if float(np.linalg.norm(arm.jaw_centre() - goal)) < 0.010:
            break
    for value in np.linspace(arm.finger_opening(), arm.OPEN, 16):
        arm.set_gripper(float(value))
        for _ in range(3):
            advance(1)
    for _ in range(60):
        advance(1)


class RolloutRecorder:
    """Records rollout episodes in the training schema, successes *and* failures.

    ``EpisodeRecorder`` (the demonstration schema) is deliberately untouched: it
    drops failed episodes and computes ``success`` from the caller. This recorder
    keeps every attempt whose arrays were written, writes the same npz keys
    ``EpisodeStore`` reads (so a rollout directory trains like a demo directory),
    and adds the RL bookkeeping - ``success/grasped/placed/notes/ticks/category/
    diameter/reward`` - to ``index.json``.

    ``add`` is called on the observation ticks (every 4 physics steps, 30 Hz);
    ``decimation`` must stay 1 so the rollout frames have the same 30 Hz cadence
    as the demonstrations.
    """

    def __init__(self, out_dir: str, decimation: int = 1):
        self.out_dir = out_dir
        self.decimation = max(1, int(decimation))
        self._counter = 0
        self._frames: list[dict] = []
        self.meta: dict | None = None
        os.makedirs(out_dir, exist_ok=True)

    # ------------------------------------------------------------------ #
    def begin(self, meta: dict) -> None:
        self.meta = dict(meta)
        self._frames = []
        self._counter = 0

    @property
    def recording(self) -> bool:
        return self.meta is not None

    def tick(self) -> bool:
        self._counter += 1
        return self._counter % self.decimation == 0

    def add(self, observation: dict, action: np.ndarray | None = None) -> None:
        if self.meta is None or not self.tick():
            return
        frame = {k: np.asarray(v) for k, v in observation.items() if v is not None}
        if action is not None:
            frame["action"] = np.asarray(action, dtype=np.float32)
        self._frames.append(frame)

    # ------------------------------------------------------------------ #
    def finish(
        self,
        *,
        success: bool,
        grasped: bool,
        placed: bool,
        reward: float,
        ticks: int,
        notes: list[str] | None = None,
        extra: dict | None = None,
    ) -> str | None:
        """Write the episode npz + index row. Returns the path (or None)."""
        meta = self.meta
        self.meta = None
        frames = self._frames
        self._frames = []
        if meta is None:
            return None
        if not frames:
            # Nothing was written for this attempt (it failed before an
            # observation tick). No file, no index row - an empty npz would
            # break `EpisodeStore`'s skill labelling.
            return None
        keys = frames[0].keys()
        arrays = {key: np.stack([f[key] for f in frames]) for key in keys}
        name = f"rollout_{int(meta['index']):05d}.npz"
        path = os.path.join(self.out_dir, name)
        np.savez_compressed(path, **arrays)
        row = {
            "file": name,
            "index": int(meta["index"]),
            "category": str(meta.get("category", "")),
            "grade": str(meta.get("grade", "")),
            "arm": str(meta.get("arm", "")),
            "bin_index": int(meta.get("bin_index", -1)),
            "diameter": float(meta.get("diameter", 0.0)),
            "success": bool(success),
            "grasped": bool(grasped),
            "placed": bool(placed),
            "notes": list(notes or []),
            "ticks": int(ticks),
            "reward": float(reward),
            "frames": int(len(frames)),
            "presentation": str(meta.get("presentation", "")),
            "ablate": str(meta.get("ablate", "")),
            "seed": int(meta.get("seed", -1)),
        }
        if extra:
            row.update(extra)
        self._append_index(path, row)
        return path

    def abort(self) -> None:
        """Drop an unfinished episode without writing anything."""
        self.meta = None
        self._frames = []

    def _append_index(self, path: str, row: dict) -> None:
        index_path = os.path.join(self.out_dir, "index.json")
        entries = []
        if os.path.exists(index_path):
            try:
                with open(index_path, encoding="utf-8") as fh:
                    entries = json.load(fh)
                if not isinstance(entries, list):
                    entries = []
            except (OSError, ValueError):
                # A run killed mid-write (the contact-grind wedge) can leave a
                # truncated/empty index; treat it as empty instead of crashing
                # the next episode's recorder. The npz files are unaffected.
                entries = []
        name = os.path.basename(path)
        for position, existing in enumerate(entries):
            if existing.get("file") == name:
                entries[position] = row
                break
        else:
            entries.append(row)
        # Atomic write: a SIGKILL during json.dump must not corrupt the index.
        tmp_path = index_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2)
        os.replace(tmp_path, index_path)


class SortingRLEnv:
    """One sorting cell, reused for many episodes; the policy is rolled inside.

    The caller creates the env once (scene build is expensive), then per episode::

        obs = env.reset(seed)          # first episode of a run
        while not done:
            chunk = env.sample_chunk()  # harness order: frame push, then sample
            result = env.act(chunk, execute_steps=4)
            done = result.done
        obs = env.reset()               # subsequent episodes

    ``act`` executes up to ``execute_steps`` actions of ``chunk`` (one physics
    tick each), so ``execute_steps=4`` reproduces the hybrid evaluator's
    re-plan-every-4-actions loop.
    """

    def __init__(
        self,
        *,
        presentation: str = "direct",
        seed: int = 77,
        size_filter: str | None = None,
        ablate: str = "none",
        checkpoint: str | None = None,
        record: bool = False,
        out_dir: str | None = None,
        execute_steps: int = 4,
        ddim_steps: int = 16,
        approach_steps: int = 400,
        reward: RewardConfig | None = None,
        verbose: bool = False,
        waypoint_path: str | None = None,
        dagger: ExpertConfig | None = None,
    ) -> None:
        if presentation not in ("direct", "handoff"):
            raise ValueError(f"presentation must be direct|handoff, got {presentation!r}")
        if ablate not in ("none", "zero", "scripted"):
            raise ValueError(f"ablate must be none|zero|scripted, got {ablate!r}")
        if ablate == "none" and not checkpoint:
            raise ValueError("ablate='none' needs --ckpt (the policy to roll out)")
        if dagger is not None and presentation != "direct":
            raise ValueError("the DAgger expert is only defined for presentation='direct'")
        self.presentation = presentation
        self.ablate = ablate
        self.dagger = dagger
        self.seed = int(seed)
        self._active_seed = int(seed)
        self.execute_steps = int(execute_steps)
        self.ddim_steps = int(ddim_steps)
        self.approach_steps = int(approach_steps)
        self.reward = reward or RewardConfig()
        self.verbose = bool(verbose)
        #: Off by default. `RL_ENV_DEBUG=1` traces the direct close decision
        #: (one fruit-pose read every 25 applied actions) - diagnostics are part
        #: of the measurement, so this must only be used to find a mechanism.
        self._debug = os.environ.get("RL_ENV_DEBUG", "0") == "1"
        #: GEM-style tracking half (arXiv 2508.14042), default off: add the
        #: joint-space image of the fruit's measured Cartesian velocity to the
        #: policy's arm command each tick, so the end-effector tracks the fruit
        #: and the learned action only has to supply the interaction. Read-only
        #: (a rigid-body velocity read plus the TCP Jacobian); the knob is
        #: diagnostics-grade in the sense that it changes the control loop, so
        #: it is opt-in and recorded in the manifest.
        self._policy_track = os.environ.get("FRUIT_POLICY_TRACK", "0") == "1"
        #: Encoder-based intercept trigger (P4b1, `policy/trigger.py`), default
        #: off: with `FRUIT_POLICY_TRIGGER` unset the trigger below is the
        #: shipped `finger < 0.030 and distance < 0.06` test unchanged. When
        #: enabled it fires the scripted primitive on the fruit's predicted
        #: arrival at the jaw, from the belt encoder / measured velocity.
        self.trigger_settings = TriggerSettings.from_env()

        # --- event-triggered replanning (path-3 arm), default off ----------- #
        #: DVAC/ChunkTrust-spirited test-time horizon adaptation: the execute
        #: horizon for each newly sampled chunk is chosen from the continuity
        #: between the new chunk's clean actions and the previous chunk's
        #: overlapping prediction (see `_event_horizon`). Off by default; when
        #: off the loop is the shipped fixed `execute_steps`.
        self._event = os.environ.get("FRUIT_POLICY_EVENT", "0") == "1"
        self._event_min = max(2, int(os.environ.get("FRUIT_POLICY_EVENT_MIN", "2")))
        self._event_max = max(
            self._event_min, int(os.environ.get("FRUIT_POLICY_EVENT_MAX", "6"))
        )
        self._event_default = min(
            self._event_max,
            max(
                self._event_min,
                int(os.environ.get("FRUIT_POLICY_EVENT_HORIZON", str(self.execute_steps))),
            ),
        )
        if self._event and presentation != "direct":
            raise ValueError(
                "event-triggered replanning is only defined for presentation='direct'"
            )
        #: A2C2-style per-step correction head (path-3 arm), default off. Loaded
        #: after the policy below (it only needs the checkpoint normalizer).
        self._a2c2_path = os.environ.get("FRUIT_A2C2", "").strip()
        self._a2c2 = None

        # --- RTC (real-time chunking), default off --------------------------- #
        from .policy.runtime import RTCSettings

        self.rtc_settings = RTCSettings.from_env()
        if self.rtc_settings.enabled:
            if presentation != "direct":
                raise ValueError("RTC is only defined for presentation='direct'")
            if dagger is not None:
                raise ValueError("RTC and the DAgger expert are mutually exclusive")
        #: `FRUIT_RTC_REPORT=1` records per-control-step wall time and the executed
        #: action stream's boundary jumps, for both the legacy and the RTC path.
        #: Pure reporting (already-materialised CPU arrays plus `perf_counter`),
        #: off for the rate runs.
        self._rtc_report = os.environ.get("FRUIT_RTC_REPORT", "0") == "1"
        self.rtc = None
        #: Run-level RTC report accumulators (only filled when `_rtc_report`).
        self._rtc_totals: dict = {
            "boundary": [], "within": [], "step": [], "jerk": [],
            "control_ms": [], "policy_ms": [],
            "switches": 0, "steps": 0, "chunks": 0, "decisions": 0,
            "policy_ms_total": 0.0,
        }

        # --- frozen-tree check, before any simulator state is spent ---------- #
        self.tasks_md5 = self._verify_tasks()

        # Deferred Isaac imports: this module must import offline (selfcheck).
        import isaacsim.core.experimental.utils.app as app_utils
        from isaacsim.core.rendering_manager import RenderingManager
        from isaacsim.core.simulation_manager import SimulationManager

        from .assets import SceneConfig
        from .common import say
        from .fruits import FruitSpawner
        from .scene import SortingScene
        from .tactile import GripperTactile
        from .tasks import PickAndPlaceTask

        self._app_utils = app_utils
        self._RenderingManager = RenderingManager
        self._SimulationManager = SimulationManager
        self._say = say
        self._sim_time = lambda: float(SimulationManager.get_simulation_time())

        # The direct presentation's contract is "no station hand-off": a fruit
        # the policy is about to grasp must not be teleported to the nest mark.
        # `grasp_carry_place` only teleports when the fruit is > FRUIT_HANDOFF_MAX
        # from the nest centre (default 0.30 m) or below seat height; disabling
        # that fallback does not change the function, only the data it sees.
        if presentation == "direct":
            os.environ.setdefault("FRUIT_HANDOFF", "contact")
            os.environ.setdefault("FRUIT_HANDOFF_MAX", "10.0")

        kwargs = {}
        if size_filter:
            kwargs["size_filter"] = size_filter
        self.cfg = SceneConfig(**kwargs)
        self.scene = SortingScene(self.cfg).build()
        self.tactile = GripperTactile()
        self.tactile.attach(stage=self.scene.stage)
        self.scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
        self.tactile.refresh()

        self.spawner = FruitSpawner(self.scene.stage, self.cfg, seed=self.seed)
        self.spawner.create_pool()
        self.advance(30)
        self.spawner.refresh_rigids()
        self.spawner.belt = self.scene.belt
        self.spawner.reset()
        self.spawner.prime(count=6)

        # Policy (only `ablate=none`): the same runner the hybrid evaluator uses.
        from .policy.runtime import PolicyRunner, RealtimeChunker

        self.policy = PolicyRunner(checkpoint) if ablate == "none" else None
        if self.policy is not None:
            say(
                f"[rl] loaded {checkpoint} (obs_horizon={self.policy.obs_horizon}, "
                f"action_horizon={self.policy.action_horizon})"
            )
            if self._a2c2_path:
                from .policy.correction import CorrectionController

                self._a2c2 = CorrectionController(
                    self._a2c2_path, device=self.policy.device
                )
                say(
                    f"[rl] A2C2 correction head {self._a2c2_path} "
                    f"(gain={self._a2c2.gain}, clamp={self._a2c2.clamp})"
                )
            self.action_dim = int(self.policy.config["action_dim"])
            self.action_horizon = int(self.policy.config["action_horizon"])
            self._image_channels = int(self.policy.config["image_channels"])
            if self.rtc_settings.enabled:
                self.rtc = RealtimeChunker(
                    self.policy,
                    execute_steps=self.execute_steps,
                    settings=self.rtc_settings,
                )
                say(
                    f"[rl] {self.rtc_settings.summary()} period={self.execute_steps} "
                    f"(interleaved sampler, no background thread)"
                )
        else:
            self.action_dim = 9
            self.action_horizon = 16
            self._image_channels = 5

        # The task is used for its primitives only; it must not record.
        self.task = PickAndPlaceTask(self.scene, self.spawner, self.tactile, self.cfg,
                                     waypoint_path=waypoint_path)
        self.task.recorder = None

        with open("configs/waypoints.json", encoding="utf-8") as fh:
            self.waypoints = json.load(fh)

        # Harness warm-up (60_eval_policy.py does this once): both arms parked at
        # the calibrated ready pose before the first episode - the initial
        # condition the demonstrations start from, and part of the 22-D proprio
        # the policy sees.
        for name in ("left", "right"):
            arm = self.task.arms[name]
            arm.set_gripper(arm.OPEN)
            arm.teleport_joints(
                np.asarray(self.waypoints["arms"][name]["ready"], dtype=float)
            )
        self.advance(40)

        self._out_dir = out_dir
        self.run_dir = None
        self.manifest_path = None
        if out_dir:
            self.run_dir = os.path.join(
                out_dir, f"{presentation}_{ablate}_seed{self.seed}"
            )
            os.makedirs(self.run_dir, exist_ok=True)
            self._manifest_base = self._build_manifest(checkpoint)
            self._write_manifest()

        self._recorder = RolloutRecorder(self.run_dir) if (record and self.run_dir) else None

        self.belt_top = float(self.cfg.belt_center[2]) + float(self.cfg.belt_size[2]) / 2.0
        self._episode = -1
        self._done = True
        self._sample = None
        self._active = "left"
        self._bin_index = 0
        self._goal = np.zeros(8, dtype=np.float32)
        self._tick = 0
        self._step = 0
        self._observed_step = -1
        self._last_rgb: np.ndarray | None = None
        self._last_depth: np.ndarray | None = None
        self._last_mask: np.ndarray | None = None
        self._outcome: dict | None = None
        # --- DAgger expert state (only when `dagger` is set) ----------------- #
        self._expert_until = -1
        self._expert_close_start: int | None = None
        self._expert_label: np.ndarray | None = None
        self._expert_grasp = np.zeros(7, dtype=np.float32)
        self._expert_jaw_y = float(self.cfg.pick_y)
        self._policy_proposal: np.ndarray | None = None
        self._ep_interventions = 0
        self._ep_expert_ticks = 0
        say(f"[rl] env ready: presentation={presentation} ablate={ablate} "
            f"dagger={'on' if dagger is not None else 'off'} "
            f"camera={self._camera_res_text()} tasks_md5={self.tasks_md5[:8]}")
        if self.trigger_settings.enabled:
            say(f"[rl] {self.trigger_settings.summary()}")

    # ------------------------------------------------------------------ #
    # Frozen-tree / manifest
    # ------------------------------------------------------------------ #
    def _verify_tasks(self) -> str:
        digest = _md5(os.path.join(_REPO_ROOT, "src/fruit_sorting/tasks.py"))
        if digest != TASKS_MD5:
            raise RuntimeError(
                "src/fruit_sorting/tasks.py md5 is "
                f"{digest or 'missing'}, expected {TASKS_MD5}. The RL environment "
                "was validated against the frozen revision; refusing to run on a "
                "different tree."
            )
        return digest

    def _camera_res_text(self) -> str:
        return os.environ.get(
            "FRUIT_CAMERA_RES",
            f"{self.cfg.camera_resolution[0]},{self.cfg.camera_resolution[1]}",
        )

    def _build_manifest(self, checkpoint: str | None) -> dict:
        sources = {
            name: _md5(os.path.join(_REPO_ROOT, name)) for name in _MANIFEST_SOURCES
        }
        checkpoint_md5 = ""
        if checkpoint:
            checkpoint_md5 = _md5(
                checkpoint
                if os.path.isabs(checkpoint)
                else os.path.join(_REPO_ROOT, checkpoint)
            )
        return {
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "presentation": self.presentation,
            "ablate": self.ablate,
            "seed": self.seed,
            "size_filter": self.cfg.size_filter,
            "camera_res": self._camera_res_text(),
            "fixed_stepping": True,
            "execute_steps": self.execute_steps,
            "ddim_steps": self.ddim_steps,
            "approach_steps": self.approach_steps,
            "reward": asdict(self.reward),
            "dagger": asdict(self.dagger) if self.dagger is not None else None,
            "rtc": asdict(self.rtc_settings) if self.rtc_settings.enabled else None,
            "rtc_report": bool(self._rtc_report),
            "policy_track": bool(self._policy_track),
            "event_replan": {
                "enabled": bool(self._event),
                "min": int(self._event_min),
                "max": int(self._event_max),
                "default": int(self._event_default),
            },
            "a2c2": (
                {
                    "path": self._a2c2_path,
                    "md5": _md5(
                        self._a2c2_path
                        if os.path.isabs(self._a2c2_path)
                        else os.path.join(_REPO_ROOT, self._a2c2_path)
                    ),
                    "gain": os.environ.get("FRUIT_A2C2_GAIN", "1.0"),
                    "clamp": os.environ.get("FRUIT_A2C2_CLAMP", "0.2"),
                }
                if self._a2c2_path
                else None
            ),
            "dynamic_force": {
                # OpenArm grip force servo (tasks.py; default off). Recorded even
                # when off so a run is identifiable from its manifest alone.
                "servo": os.environ.get("FRUIT_DYNAMIC_FORCE_SERVO", "0"),
                "min": os.environ.get("FRUIT_DYNAMIC_FORCE_MIN", "2.0"),
                "drop": os.environ.get("FRUIT_DYNAMIC_FORCE_DROP", "0.8"),
                "max": os.environ.get("FRUIT_DYNAMIC_FORCE_MAX", "12.0"),
                "ref_max": os.environ.get("FRUIT_DYNAMIC_FORCE_REF_MAX", "4.0"),
                "step": os.environ.get("FRUIT_DYNAMIC_FORCE_STEP", "0.0004"),
                "ticks": os.environ.get("FRUIT_DYNAMIC_FORCE_TICKS", "3"),
                "ref_ticks": os.environ.get("FRUIT_DYNAMIC_FORCE_REF_TICKS", "48"),
                "range": os.environ.get("FRUIT_DYNAMIC_FORCE_RANGE", "0.015"),
                "backoff": os.environ.get("FRUIT_DYNAMIC_FORCE_BACKOFF", "0.003"),
            },
            "dynamic_lift": {
                # v6 contact-verification dwell + staged first lift (tasks.py;
                # default off for both). Recorded even when off so a run is
                # identifiable from its manifest alone.
                # v7: `lift_peak` is the peak-hold lift metric, default **on**
                # only while a dynamic capture is active (the policy loop never
                # is, so its scenario is unchanged).
                "lift_peak": os.environ.get("FRUIT_DYNAMIC_LIFT_PEAK", "1"),
                "verify_dwell": os.environ.get("FRUIT_DYNAMIC_VERIFY_DWELL", "0"),
                "verify_force": os.environ.get("FRUIT_DYNAMIC_VERIFY_FORCE", "2.0"),
                "verify_ticks": os.environ.get("FRUIT_DYNAMIC_VERIFY_TICKS", "24"),
                "verify_max_ticks": os.environ.get(
                    "FRUIT_DYNAMIC_VERIFY_MAX_TICKS", "240"
                ),
                "ramp": os.environ.get("FRUIT_DYNAMIC_RAMP_LIFT", "0"),
                "ramp_step": os.environ.get("FRUIT_DYNAMIC_RAMP_STEP", "0.0025"),
                "ramp_step_ticks": os.environ.get(
                    "FRUIT_DYNAMIC_RAMP_STEP_TICKS", "24"
                ),
                "ramp_pause_ticks": os.environ.get(
                    "FRUIT_DYNAMIC_RAMP_PAUSE_TICKS", "24"
                ),
                "ramp_rest_ticks": os.environ.get(
                    "FRUIT_DYNAMIC_RAMP_REST_TICKS", "72"
                ),
            },
            "trigger": (
                asdict(self.trigger_settings) if self.trigger_settings.enabled else None
            ),
            "tasks_md5": self.tasks_md5,
            "checkpoint": checkpoint or "",
            "checkpoint_md5": checkpoint_md5,
            "handoff_mode": os.environ.get("FRUIT_HANDOFF", ""),
            "handoff_max": os.environ.get("FRUIT_HANDOFF_MAX", ""),
            "no_attach": os.environ.get("FRUIT_NO_ATTACH", ""),
            "no_sleep": os.environ.get("FRUIT_NO_SLEEP", ""),
            "policy_seed": os.environ.get("FRUIT_POLICY_SEED", ""),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "sources": sources,
        }

    def _write_manifest(self) -> None:
        assert self.run_dir is not None
        self.manifest_path = os.path.join(self.run_dir, "manifest.json")
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(self._manifest_base, fh, indent=2, sort_keys=True)
        self._say(f"[rl] manifest -> {self.manifest_path} "
                  f"(reward={json.dumps(self._manifest_base['reward'])})")

    # ------------------------------------------------------------------ #
    # Stepping
    # ------------------------------------------------------------------ #
    def advance(self, steps: int) -> None:
        """Tick-exact physics advance + callback pump.

        Same rule as `60_eval_policy.advance` and `40_collect_demos.advance`:
        `SimulationManager.step` is the fixed step, `update_app(steps=0)` only
        services the camera/sensor callbacks. Never `update_app(steps=N)`.
        """
        self._SimulationManager.step(steps=int(steps))
        self._app_utils.update_app(steps=0)

    # ------------------------------------------------------------------ #
    # Episode setup
    # ------------------------------------------------------------------ #
    def reset(self, seed: int | None = None) -> dict:
        """Start the next episode. Returns a light observation snapshot.

        The first episode of a run passes `seed` (the spawner seed); later
        episodes call `reset()` so the fruit sequence continues rather than
        restarting from the same RNG state every time.
        """
        if self._recorder is not None and self._recorder.recording:
            # An episode that is reset without reaching `_finalize` (the driver
            # grew impatient) must not leak a half file into the index.
            self._recorder.abort()
        if seed is not None:
            seed = int(seed)
            if seed != self._active_seed:
                self.spawner.rng.seed(seed)
                self._active_seed = seed
                self.seed = seed
        self._episode += 1

        # Target selection. `handoff` uses the hybrid evaluator's window (the
        # teleport makes distance harmless); `direct` uses the *scripted line's*
        # selector, which is how demos_v7 was collected: a fruit already at the
        # station first (`pick_y`+0.02..0.18 with the pre-pose lead), and only
        # then the closest fruit upstream. Selecting far upstream gives the
        # policy an 11 s walk for a 12.5 s budget, which is a different task
        # from the one it was trained on.
        rounds = 0
        target_state: dict | None = None
        while True:
            for _ in range(30):
                self.advance(1)
                self.spawner.update(self._sim_time())
                self.spawner.enforce_transport()
            if self.presentation == "handoff":
                states = [
                    s for s in self.spawner.state()
                    if s["diameter"] <= self.cfg.gripper_max_object
                ]
                states = [
                    s for s in states
                    if abs(float(s["position"][0]) - self.cfg.belt_center[0]) < 0.30
                    and self.cfg.pick_y + 0.15 < float(s["position"][1])
                    < self.cfg.spawn_y + 0.05
                ]
                target_state = min(states, key=lambda s: float(s["position"][1])) if states else None
            else:
                target_state = self.task.select_target(self.spawner.state())
            if target_state is not None or rounds >= 40:
                break
            rounds += 1
        if target_state is None:
            raise RuntimeError(
                "no graspable fruit reached the selection window in 40 feed rounds"
            )
        target = target_state
        sample = next(s for s in self.spawner.samples if s.index == target["index"])
        grade = target["grade"]
        bin_index = 0 if grade == "A" else 1
        active = "left" if bin_index == 0 else "right"

        self._sample = sample
        self._active = active
        self._bin_index = bin_index
        self._goal = np.array(
            [
                *np.asarray(target["position"], dtype=np.float32),
                *np.asarray(target["velocity"], dtype=np.float32),
                float(target["diameter"]),
                float(bin_index),
            ],
            dtype=np.float32,
        )
        self._belt_rest = self.belt_top + float(target["diameter"]) / 2.0

        # Start state. Every `demos_v7` episode begins when the scripted pick
        # reaches its *wait loop*: the pre-pose before it is not recorded, so the
        # first frame of every demonstration already has the arm at the calibrated
        # grasp pose (measured: |q-grasp| <= 0.011 rad at frame 0, and no demo
        # frame ever comes closer than 0.220 rad to the ready pose). `handoff`
        # still reproduces the hybrid evaluator (ready pose + station hand-off);
        # `direct` is the causal interface and must start where the training
        # distribution starts, or the policy's very first observation is a state
        # it has never seen. Both arms are parked at ready first, like
        # `go_ready()` does before every collected episode, so the inactive arm is
        # not left wherever the previous carry dropped it.
        arm = self.task.arms[active]
        if self.presentation == "direct":
            for name, other in self.task.arms.items():
                other.set_gripper(other.OPEN)
                other.teleport_joints(
                    np.asarray(self.waypoints["arms"][name]["ready"], dtype=float)
                )
            start = np.asarray(self.waypoints["arms"][active]["grasp"], dtype=float)
        else:
            start = np.asarray(self.waypoints["arms"][active]["ready"], dtype=float)
        arm.teleport_joints(start)
        # `teleport_joints` writes the *measured* dof state back through the
        # drive, and Isaac re-targets from it, so the `set_gripper(OPEN)` in the
        # parking loop does not survive: the first observation then carried all
        # four finger joints at 0.000 where every recorded wait frame has them
        # at 0.044. The policy reads those channels as its wait/close phase cue
        # (measured: with them closed the first chunk executes the close/track
        # phase, and with them open it holds the grasp pose), so start the
        # episode with both grippers open, measured and commanded, exactly like
        # the demonstrations' frame 0.
        gripper_open = float(arm.OPEN)
        dof = np.asarray(self.scene.robot.get_dof_positions().numpy())[0].copy()
        for other in self.task.arms.values():
            dof[list(other.finger_dofs)] = gripper_open
        self.scene.robot.set_dof_positions(dof)
        for other in self.task.arms.values():
            other.set_gripper(gripper_open)
        self.advance(20)
        #: Pick-station jaw line the scripted tracking window is measured against
        #: (`_run_impl` reads it after its pre-pose, at the same pose).
        self._expert_jaw_y = float(arm.jaw_centre()[1])
        #: Nominal close zone captured at reset: the jaw centre at the calibrated
        #: grasp pose. The intercept trigger can time the fruit's arrival against
        #: this point instead of the current jaw, which is robust to the policy's
        #: own slow arm drift over the long wait (`FRUIT_POLICY_TRIGGER_FRAME`).
        self._trigger_station = np.asarray(arm.jaw_centre()[:2], dtype=float).copy()
        if self.spawner.belt is not None:
            self.spawner.belt.start()

        if self.policy is not None:
            self.policy.reset()
        if self.rtc is not None:
            self.rtc.reset()

        self._tick = 0
        self._step = 0
        self._observed_step = -1
        self._last_rgb = None
        self._last_depth = None
        self._last_mask = None
        self._done = False
        self._triggered = False
        self._handoff_done = False
        self._grasp_done = False
        self._lifted = False
        self._grasped = False
        self._placed = False
        self._notes: list[str] = []
        self._last_action = np.zeros(self.action_dim, dtype=np.float32)
        self._episode_t0 = self._sim_time()
        self._decision_step: int | None = None
        self.spawner.protected = int(target["index"])
        # RTC report buffers for this episode (empty and unused when off).
        self._report_boundary: list[float] = []
        self._report_within: list[float] = []
        self._report_step: list[float] = []
        self._report_jerk: list[float] = []
        self._report_control_ms: list[float] = []
        self._report_policy_ms: list[float] = []
        self._report_decisions = 0
        self._last7: np.ndarray | None = None
        self._prev7: np.ndarray | None = None
        self._switch_flag = False
        self._pending_switch = False
        self._applied_any = False
        # Event-triggered replanning state for this episode (empty when off).
        self._prev_chunk: np.ndarray | None = None
        self._prev_exec = 0
        self._event_continuities: list[float] = []
        self._event_horizons: list[int] = []
        # DAgger bookkeeping for this episode (the expert label buffer starts
        # empty; `_observe`/`_record_tick` fill it at the decision points).
        self._expert_until = -1
        self._expert_close_start = None
        self._expert_label = None
        self._expert_grasp = np.asarray(
            self.waypoints["arms"][active]["grasp"], dtype=np.float32
        ).copy()
        self._policy_proposal = None
        self._ep_interventions = 0
        self._ep_expert_ticks = 0

        self._say(
            f"[rl] episode {self._episode}: {target['category']} grade={grade} "
            f"d={target['diameter'] * 100:.1f}cm bin={bin_index} arm={active} "
            f"y={float(target['position'][1]):+.3f} presentation={self.presentation}"
        )
        if self._recorder is not None:
            self._recorder.begin(
                {
                    "index": self._episode,
                    "category": sample.category,
                    "grade": sample.grade,
                    "arm": active,
                    "bin_index": bin_index,
                    "diameter": sample.diameter,
                    "presentation": self.presentation,
                    "ablate": self.ablate,
                    "seed": self._active_seed,
                }
            )
        # Frame 0, so `policy.ready` becomes true after the first window fills.
        self._observe()
        return self._obs_snapshot()

    # ------------------------------------------------------------------ #
    # Observation
    # ------------------------------------------------------------------ #
    def _observe(self) -> None:
        """Render and read the head camera once per observation tick."""
        if self._observed_step == self._step:
            return
        self._observed_step = self._step
        if self.policy is None and self._recorder is None:
            return
        self._RenderingManager.render()
        raw_rgb = self.scene.camera_sensor.get_data("rgb")
        raw_depth = self.scene.camera_sensor.get_data("distance_to_image_plane")
        rgb = np.asarray(raw_rgb[0].numpy()) if raw_rgb is not None else None
        depth = np.asarray(raw_depth[0].numpy()) if raw_depth is not None else None
        mask = None
        if rgb is not None and depth is not None:
            if self._image_channels == 5 or self._recorder is not None:
                raw = self.scene.camera_sensor.get_data("instance_id_segmentation")
                seg = np.asarray(raw[0].numpy()) if raw is not None else None
                if seg is not None:
                    if seg.ndim == 3:
                        seg = seg[..., 0]
                    info = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else {}
                    labels = info.get("idToLabels", {}) if isinstance(info, dict) else {}
                    target_id = 0
                    want = self._sample.prim_path if self._sample is not None else None
                    for key, value in labels.items():
                        if want and want in str(value):
                            target_id = int(key)
                            break
                    mask = (seg == target_id).astype(np.float32)
        self._last_rgb, self._last_depth, self._last_mask = rgb, depth, mask
        if self.policy is not None and rgb is not None and depth is not None:
            self.policy.push_frame(rgb, depth, mask)

    def proprio(self) -> np.ndarray:
        """The 25-D proprioception vector the training data recorded.

        All 22 joint positions, the active arm's finger opening, the two tactile
        normal forces. In `handoff` mode the finger channel is the harness's
        (``mean(dof[[14, 15]])`` - the left fingers, whatever arm is active),
        because that presentation's job is to reproduce the harness exactly;
        `direct` uses the active arm's finger, which is what the demonstrations
        recorded.
        """
        dof = np.asarray(self.scene.robot.get_dof_positions().numpy())[0].astype(
            np.float32
        )
        if self.presentation == "handoff":
            finger = float(np.mean(dof[[14, 15]]))
        else:
            arm = self.task.arms[self._active]
            finger = float(np.mean(dof[list(arm.finger_dofs)]))
        reading = self.tactile.read()
        zero = 0.0
        forces = [
            float(reading.get("left").normal_force) if reading.get("left") else zero,
            float(reading.get("right").normal_force) if reading.get("right") else zero,
        ]
        return np.concatenate(
            [dof, np.array([finger], dtype=np.float32),
             np.asarray(forces, dtype=np.float32)]
        ).astype(np.float32)

    def _obs_snapshot(self) -> dict:
        """Light observation for the caller (the policy input is built above).

        Getting the policy's observation is `push_frame` (camera) plus
        `proprio()` plus `goal`; this snapshot only reports where the episode is,
        so it costs no extra sensor reads in the control loop.
        """
        sample = self._sample
        return {
            "episode": self._episode,
            "tick": self._tick,
            "step": self._step,
            "policy_ready": bool(self.policy.ready) if self.policy is not None else False,
            "goal": self._goal.copy(),
            "fruit_position": (
                np.asarray(self.spawner.position(sample), dtype=float).copy()
                if sample is not None else None
            ),
            "presentation": self.presentation,
            "ablate": self.ablate,
        }

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def sample_chunk(self, num_steps: int | None = None) -> np.ndarray | None:
        """Sample a fresh action chunk, or zeros for the zero ablation.

        Matches the harness order: push the due camera frame first, then sample
        from the buffer. Returns None until the observation horizon is full.
        With RTC the chunker samples internally, one action per control step, so
        this only services the camera and returns None (`act` ignores it).
        """
        if self._done:
            return None
        if self._step % 4 == 0:
            self._observe()
        if self.ablate == "zero":
            return np.zeros((self.action_horizon, self.action_dim), dtype=np.float32)
        if self.policy is None or not self.policy.ready:
            return None
        if self.rtc is not None:
            return None
        if self._rtc_report:
            start = time.perf_counter()
        chunk = self.policy.act(
            self.proprio(), self._goal, num_steps=self.ddim_steps if num_steps is None
            else int(num_steps)
        )
        if self._rtc_report:
            self._report_policy_ms.append((time.perf_counter() - start) * 1e3)
            self._report_decisions += 1
            self._pending_switch = True
        return chunk

    def act(self, chunk: np.ndarray | None, execute_steps: int | None = None) -> StepResult:
        """Execute up to ``execute_steps`` actions; returns the step result.

        With event-triggered replanning (``FRUIT_POLICY_EVENT=1``) the horizon
        for this chunk is chosen by `_event_horizon` instead of the passed
        ``execute_steps``; the argument is then the reference/default only.
        """
        steps = self.execute_steps if execute_steps is None else max(1, int(execute_steps))
        if self._done:
            return self._step_result()
        if self._sample is None:
            raise RuntimeError("call reset() before act()")
        if self.ablate == "scripted":
            self._run_scripted()
            return self._step_result()
        if self._event:
            steps = self._event_horizon(chunk)

        executed = 0
        for index in range(steps):
            step_start = time.perf_counter() if self._rtc_report else 0.0
            if self._step % 4 == 0:
                self._observe()
            # The handoff evaluator hands over on a fixed control-step budget,
            # before the observation branch of the loop body.
            if self.presentation == "handoff" and self._step >= self.approach_steps:
                self._run_primitive()
                if self._done:
                    break
            self._switch_flag = False
            action = None
            if self.rtc is not None:
                # One action per control step; the sampler advances interleaved.
                # `last_switch` was set by the previous step's completion, so the
                # action about to be applied is the first of a new chunk.
                self._switch_flag = bool(self.rtc.last_switch)
                if self.policy.ready:
                    if self._rtc_report:
                        start = time.perf_counter()
                    action = self.rtc.next_action(
                        self.proprio, self._goal, self.ddim_steps,
                        roll=self._roll_proprio if self.rtc_settings.vlash else None,
                    )
                    if self._rtc_report:
                        self._report_policy_ms.append((time.perf_counter() - start) * 1e3)
            elif chunk is not None:
                arr = np.asarray(chunk)
                if index < arr.shape[0]:
                    action = arr[index]
                if self._rtc_report and index == 0:
                    self._switch_flag = bool(self._pending_switch)
                    self._pending_switch = False
            if self.dagger is not None:
                action = self._dagger_action(action)
            if action is not None:
                self._apply(action, index)
                if self._done:
                    executed = index + 1
                    break
                self._record_tick()
                self.advance(1)
            else:
                self.advance(1)
            if self._rtc_report:
                self._report_control_ms.append(
                    (time.perf_counter() - step_start) * 1e3
                )
            self._tick += 1
            self.spawner.enforce_transport()
            self._step += 1
            executed = index + 1
            if self._episode_events():
                continue
            if self._tick >= int(self.reward.horizon):
                self._finalize(
                    notes=self._notes + [
                        f"timeout: no grasp within {int(self.reward.horizon)} ticks"
                    ]
                )
                break
        if self._event:
            # The next chunk is sampled at the state after these `executed`
            # steps; its index `i` then corresponds to this chunk's index
            # `executed + i` (the same absolute control step).
            self._prev_chunk = (
                None if chunk is None else np.asarray(chunk, dtype=np.float64).copy()
            )
            self._prev_exec = int(executed)
        return self._step_result()

    def _apply(self, action, index: int = 0) -> None:
        action = np.asarray(action, dtype=np.float64).reshape(-1)
        if not np.isfinite(action).all():
            self._notes.append("non-finite policy action")
            return
        arm = self.task.arms[self._active]
        if self._a2c2 is not None and not self._triggered:
            # A2C2-style per-step correction on the frozen base policy, before
            # the primitive owns the arm. The head only shifts the 7 arm
            # channels; the finger command (and so the trigger) is unchanged.
            action = self._a2c2.correct(action, self.proprio(), self._goal, index)
        if self._policy_track and self._sample is not None and not self._sample.attached:
            action = self._tracking_action(action, arm)
        self.scene.robot.set_dof_position_targets(
            [action[:7].tolist()], dof_indices=list(arm.arm_dofs)
        )
        finger = float(np.clip(action[7], 0.0, 0.044))
        self.scene.robot.set_dof_position_targets(
            [[finger, finger]], dof_indices=list(arm.finger_dofs)
        )
        if action.shape[0] > 8:
            # Recorded channel: the two finger joints mirror `action[7]`, the
            # same convention the demonstrations use.
            action = action.copy()
            action[7] = finger
            action[8] = finger
        if self._rtc_report:
            # Executed-stream diagnostics (off for rate runs): the 7-D arm command
            # jump between consecutive applied actions, split into switch
            # boundaries and within-chunk steps, plus the second difference
            # (jerk) of the whole executed stream. Pure reporting over
            # already-materialised arrays.
            current7 = np.asarray(action[:7], dtype=np.float64)
            if self._applied_any:
                delta = float(np.linalg.norm(current7 - self._last7))
                if self._switch_flag:
                    self._report_boundary.append(delta)
                else:
                    self._report_within.append(delta)
                self._report_step.append(delta)
                if self._prev7 is not None:
                    self._report_jerk.append(
                        float(np.linalg.norm(current7 - 2.0 * self._last7 + self._prev7))
                    )
            self._prev7 = self._last7
            self._last7 = current7
            self._applied_any = True
        self._last_action = action.astype(np.float32)
        self._last_finger = finger
        if self.presentation == "handoff":
            self._handoff_action_extras(finger)
        elif not self._triggered:
            jaw = arm.jaw_centre()
            fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
            distance = float(
                np.linalg.norm(fruit[:2] - np.asarray(jaw[:2], dtype=float))
            )
            if self._debug and (self._step % 25 == 0 or finger < 0.030):
                self._say(
                    f"[rl]   step={self._step} finger={finger:.4f} "
                    f"|jaw-fruit|xy={distance * 100:.1f}cm "
                    f"fruit=({fruit[0]:.3f},{fruit[1]:+.3f},{fruit[2]:.3f}) "
                    f"jaw=({jaw[0]:.3f},{jaw[1]:+.3f},{jaw[2]:.3f})"
                )
            policy_close = bool(finger < 0.030 and distance < 0.06)
            intercept = False
            intercept_info: dict | None = None
            presented_note: str | None = None
            if self.trigger_settings.enabled:
                encoder = None
                if self.spawner.belt is not None:
                    encoder = getattr(self.spawner.belt, "encoder_speed", None)
                reference = jaw
                if self.trigger_settings.frame == "station":
                    reference = np.array(
                        [self._trigger_station[0], self._trigger_station[1], jaw[2]],
                        dtype=float,
                    )
                intercept, intercept_info = should_fire(
                    self.trigger_settings,
                    fruit,
                    reference,
                    encoder_speed=encoder,
                    measured_velocity=self.spawner.velocity(self._sample),
                    finger=finger,
                )
                # P4b2: the scripted primitive re-selects the fruit the feeder
                # presents (`task.station_sample`) at grasp time, but this trigger
                # was watching the selected upstream sample. When that sample is
                # blocked, recirculated or pushed off-lane, a *firable* presented
                # fruit is the one the primitive would grasp - adopt it here so
                # the trigger fires on the fruit that will actually be picked.
                # Only when the selected sample is not already firable/closable,
                # so the clean path is byte-identical. Default off.
                if (
                    self.trigger_settings.present
                    and not intercept
                    and not policy_close
                ):
                    presented = self.task.station_sample()
                    if (
                        presented is not None
                        and int(presented.index) != int(self._sample.index)
                        and float(presented.diameter)
                        <= float(self.cfg.gripper_max_object)
                    ):
                        presented_fruit = np.asarray(
                            self.spawner.position(presented), dtype=float
                        )
                        p_fire, p_info = should_fire(
                            self.trigger_settings,
                            presented_fruit,
                            reference,
                            encoder_speed=encoder,
                            measured_velocity=self.spawner.velocity(presented),
                            finger=finger,
                        )
                        if p_fire:
                            selected_dy = float(
                                (intercept_info or {}).get("dy", float("nan"))
                            )
                            self._sample = presented
                            # Keep the observation coherent for any tick before
                            # the primitive takes over; the arm's lane is kept
                            # (`_bin_index`), like the task's station re-select.
                            self._goal = np.array(
                                [
                                    *np.asarray(
                                        self.spawner.position(presented), dtype=np.float32
                                    ),
                                    *np.asarray(
                                        self.spawner.velocity(presented), dtype=np.float32
                                    ),
                                    float(presented.diameter),
                                    float(self._bin_index),
                                ],
                                dtype=np.float32,
                            )
                            intercept, intercept_info = True, p_info
                            presented_note = (
                                f"presented intercept: adopted index "
                                f"{presented.index} ({presented.category}) over the "
                                f"selected sample (selected dy={selected_dy:+.3f} m)"
                            )
            if policy_close or intercept:
                self._triggered = True
                closer = (
                    "expert"
                    if self.dagger is not None and self._step < self._expert_until
                    else "policy"
                )
                if policy_close:
                    self._notes.append(
                        f"{closer} closed on the fruit (finger={finger:.4f}, "
                        f"|jaw-fruit|xy={distance * 100:.1f}cm)"
                    )
                if intercept:
                    info = intercept_info or {}
                    self._notes.append(
                        "intercept trigger ("
                        f"dy={info.get('dy', float('nan')) * 100:.1f}cm, "
                        f"dx={info.get('dx', float('nan')) * 100:.1f}cm, "
                        f"t_arrive={info.get('t_arrive', float('nan')):.2f}s, "
                        f"speed={info.get('speed', float('nan')):.3f}m/s/"
                        f"{info.get('source', '?')}, frame={self.trigger_settings.frame}, "
                        f"finger={finger:.4f})"
                    )
                if presented_note is not None:
                    self._notes.append(presented_note)
                self._run_primitive()

    def _event_horizon(self, chunk: np.ndarray | None) -> int:
        """Event-triggered execute horizon from chunk-to-chunk continuity.

        The new chunk is sampled at the state after ``_prev_exec`` steps of the
        previous chunk, so new index ``i`` and prev index ``_prev_exec + i`` are
        the same absolute control step. Their mean 7-D arm disagreement over the
        first few indices is a direct continuity read on the clean actions
        (ChunkTrust's stability idea; DVAC's "variance decides the replan" at
        chunk turnover). With the run's online median ``m``: ``hi = 1.5 m``,
        ``lo = 0.5 m``; horizon = min (2) above hi, max (6) below lo, the
        default (4) in between. Test-time only; no retraining.
        """
        if chunk is None or self._prev_chunk is None:
            return self._event_default
        new = np.asarray(chunk, dtype=np.float64)
        prev = self._prev_chunk
        start = int(self._prev_exec)
        window = min(
            self._event_default + 2,
            self._event_max,
            new.shape[0],
            int(prev.shape[0]) - start,
        )
        if window <= 0:
            return self._event_default
        delta = new[:window, :7] - prev[start : start + window, :7]
        continuity = float(np.linalg.norm(delta, axis=1).mean())
        self._event_continuities.append(continuity)
        median = float(np.median(self._event_continuities))
        hi = max(1.5 * median, 1e-4)
        lo = max(0.5 * median, 1e-4)
        if continuity >= hi:
            steps = self._event_min
        elif continuity <= lo:
            steps = self._event_max
        else:
            steps = self._event_default
        self._event_horizons.append(int(steps))
        if os.environ.get("FRUIT_POLICY_EVENT_LOG", "0") == "1":
            self._say(
                f"[event] step={self._step} continuity={continuity:.5f} "
                f"median={median:.5f} horizon={steps}"
            )
        return int(steps)

    def _tracking_action(self, action: np.ndarray, arm) -> np.ndarray:
        """GEM-style tracking half: shift the arm command with the fruit velocity.

        The policy's 7 joint targets are an interaction command in the belt
        frame; adding the joint image of the fruit's measured Cartesian velocity
        for one control tick (``J^+ v dt``, damped least squares, the same
        pseudo-inverse `control.ik_step` uses) makes the end-effector track the
        fruit so the learned action only has to supply the interaction. Default
        off (`FRUIT_POLICY_TRACK=1`); gain and damping are env knobs. Skipped
        once the fruit is attached/held.
        """
        velocity = np.asarray(self.spawner.velocity(self._sample), dtype=float)
        if float(np.linalg.norm(velocity)) < 1e-4:
            return action
        jacobian = self.scene.robot.get_jacobian_matrices().numpy()[
            0, arm.tcp_jacobian_index
        ]
        jac = np.asarray(jacobian[:3, list(arm.arm_dofs)], dtype=float)
        damping = float(os.environ.get("FRUIT_POLICY_TRACK_DAMPING", "1.0e-3"))
        gain = float(os.environ.get("FRUIT_POLICY_TRACK_GAIN", "1.0"))
        dq = jac.T @ np.linalg.solve(
            jac @ jac.T + damping * np.eye(3), velocity / 120.0
        )
        tracked = np.array(action, dtype=float, copy=True)
        tracked[:7] += gain * dq
        return tracked

    def _roll_proprio(self, measured: np.ndarray, window) -> np.ndarray:
        """VLASH state roll-forward: the execution-time proprio under the chunk.

        arXiv 2512.01031: for absolute actions, "the last action in the executed
        sequence directly serves as the estimated future state". ``window`` is
        the slice of the current chunk that will execute while the next chunk is
        sampled (the inference delay); its last action replaces the active
        arm's 7 joint channels and the finger channel, the other arm and the
        two tactile reads stay measured. The rolled state is only fed to the
        sampler; once a chunk is executing, the action applied to the robot is
        still the chunk's own command.
        """
        out = np.array(measured, dtype=np.float32, copy=True)
        if window is None or len(window) == 0:
            return out
        last = np.asarray(window[-1], dtype=np.float32)
        if last.shape[0] < 8:
            return out
        arm = self.task.arms[self._active]
        out[list(arm.arm_dofs)] = last[:7]
        out[22] = float(np.clip(last[7], 0.0, 0.044))
        return out

    def _handoff_action_extras(self, finger: float) -> None:
        """The hybrid evaluator's attach / grasp-primitive branch (P0a)."""
        from .grasp import GraspPrimitive

        arm = self.task.arms[self._active]
        jaw = arm.jaw_centre()
        fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
        near = float(np.linalg.norm(fruit[:2] - np.asarray(jaw[:2], dtype=float))) < 0.06
        if os.environ.get("FRUIT_NO_ATTACH", "0") != "1":
            if finger < 0.030 and near and not self._sample.attached:
                self._sample.held = True
                self.spawner.attach(self._sample, jaw)
            elif finger > 0.040 and self._sample.attached:
                self.spawner.detach(self._sample)
                self._sample.held = False
        elif not self._grasp_done and finger < 0.030 and near:
            primitive = GraspPrimitive(
                self.cfg, self.spawner, arm, self.tactile, self._active,
                waypoints=self.waypoints,
            )
            held = primitive.run(self._sample)
            self._grasp_done = True
            self._say(
                f"[rl]   grasp primitive: {'held' if held else 'failed'} "
                f"({primitive.last_note})"
            )
            if held and os.environ.get("FRUIT_PRIMITIVE_CARRY", "0") == "1":
                carry_and_release(arm, self.cfg, self._bin_index, self.advance)
                self._say(
                    f"[rl]   carry primitive: released at "
                    f"{np.round(self.spawner.position(self._sample), 3).tolist()}"
                )
        if self._sample.attached:
            self.spawner.follow(self._sample, arm.jaw_centre())

    # ------------------------------------------------------------------ #
    # DAgger expert (the scripted pick-phase controller)
    # ------------------------------------------------------------------ #
    def _dagger_action(self, policy_action) -> np.ndarray | None:
        """Return the action to execute; keep the expert label for the recorder.

        One label per decision point (`index 0` of a 4-tick chunk). While the
        expert has control the label is recomputed every tick, like the scripted
        close loop. `_record_tick` writes the label as the frame's ``action``.
        """
        if self._done or self._sample is None:
            return policy_action
        label = None
        if self._step % 4 == 0 or self._step < self._expert_until:
            label = self._expert_action()
            self._expert_label = label
        if self._step < self._expert_until:
            self._ep_expert_ticks += 1
            return label
        if policy_action is None or label is None:
            return policy_action
        self._policy_proposal = np.asarray(policy_action, dtype=np.float32)
        if self._expert_deviation(policy_action, label):
            self._expert_until = self._step + self.dagger.window_steps * 4
            self._ep_interventions += 1
            self._ep_expert_ticks += 1
            return label
        return policy_action

    def _expert_deviation(self, policy_action, expert_action: np.ndarray) -> bool:
        """The HG-DAgger takeover test: joint-space error, plus an early close.

        The scripted line keeps the pads open until the fruit reaches its
        tracking window; a policy that closes before that is deviating even if
        its arm joints are close.
        """
        policy = np.asarray(policy_action, dtype=np.float64).reshape(-1)
        error = float(np.linalg.norm(policy[:7] - expert_action[:7]))
        early_close = bool(expert_action[7] > 0.040 and policy[7] < 0.030)
        return error > float(self.dagger.tolerance) or early_close

    def _expert_action(self) -> np.ndarray:
        """The scripted pick-phase command for the current state [9-D].

        Same shape as the recorded demonstrations: 7 absolute arm joint targets
        (the calibrated grasp pose while the fruit is outside the tracking
        window, then the IK command that tracks the fruit's measured centre) and
        the two equal finger channels (open, then the scripted 60-tick quintic
        close ramp). The window and the ramp knobs are the ones
        `PickAndPlaceTask` reads, so the label is the controller the dataset came
        from; the controller itself lives in the frozen `tasks.py` and is not
        called here because `grasp_carry_place` would run the whole cycle.
        """
        arm = self.task.arms[self._active]
        sample = self._sample
        fruit = np.asarray(self.spawner.position(sample), dtype=float)
        label = np.zeros(max(9, self.action_dim), dtype=np.float32)

        # Tracking window, relative to the pick-station jaw line (`_run_impl`).
        track_start = float(os.environ.get("FRUIT_TRACK_START", "0.05"))
        track_end = -float(os.environ.get("FRUIT_TRACK_END", "0.02"))
        dy = float(fruit[1]) - float(self._expert_jaw_y)
        if self._expert_close_start is None and track_end <= dy <= track_start:
            self._expert_close_start = int(self._step)

        if self._expert_close_start is None:
            # Wait loop of the scripted line: hold the calibrated grasp pose
            # with the pads open (the recorded wait-phase action).
            label[:7] = self._expert_grasp
            finger = float(arm.OPEN)
        else:
            quat = np.asarray(arm.tcp_pose()[1], dtype=float)
            width = float(sample.diameter)
            if os.environ.get("FRUIT_CLOSE_ON_EXTENT", "1") == "1":
                width = float(self.task.pinch_width(sample, quat))
            grip_gap = width * float(os.environ.get("FRUIT_GRIPPER_SQUEEZE", "0.98"))
            ramp = min_jerk_ramp(
                float(os.environ.get("FRUIT_GRIPPER_OPEN", "0.09")),
                grip_gap,
                60,
            )
            index = min(int(self._step - self._expert_close_start), len(ramp) - 1)
            finger = float(arm.gripper_value_for_separation(float(ramp[index])))
            # The close tracks the fruit's measured centre with position-only IK,
            # one step per tick (the same call the scripted close makes). The
            # command is written to the robot here and immediately overwritten by
            # whatever action the caller applies, so this only decides the label.
            arm.hold_quaternion = None
            arm.sync_command_to_measured()
            pad_lift = float(os.environ.get("FRUIT_PAD_LIFT", "0.010"))
            arm.ik_step(
                arm.tcp_target_for_jaw(fruit + np.array([0.0, 0.0, pad_lift]))
            )
            if arm._q_cmd is not None:
                label[:7] = np.asarray(arm._q_cmd, dtype=np.float32)[:7]
        label[7] = label[8] = np.float32(finger)
        return label

    def _record_tick(self) -> None:
        """Record (observation, action) on observation ticks (30 Hz like demos)."""
        if self._recorder is None or not self._recorder.recording:
            return
        if self._observed_step != self._step:
            return
        arm = self.task.arms[self._active]
        dof = np.asarray(self.scene.robot.get_dof_positions().numpy())[0].astype(
            np.float32
        )
        reading = self.tactile.read()
        left = reading.get("left")
        right = reading.get("right")
        observation = {
            "joint_positions": dof,
            "finger_opening": np.array(
                [float(np.mean(dof[list(arm.finger_dofs)]))], dtype=np.float32
            ),
            "goal": self._goal.copy(),
            "tactile": np.array(
                [
                    float(left.normal_force) if left else 0.0,
                    float(right.normal_force) if right else 0.0,
                ],
                dtype=np.float32,
            ),
        }
        if self._last_rgb is not None:
            observation["image_rgb"] = self._last_rgb
        if self._last_depth is not None:
            observation["image_distance_to_image_plane"] = (
                self._last_depth[..., None] if self._last_depth.ndim == 2
                else self._last_depth
            )
        if self._last_mask is not None:
            observation["target_mask"] = (np.asarray(self._last_mask) > 0.5).astype(
                np.uint8
            ) * 255
        observation["fruit_position"] = np.asarray(
            self.spawner.position(self._sample), dtype=np.float32
        )
        label = self._last_action
        if self.dagger is not None and self._expert_label is not None:
            # Standard DAgger aggregation: the frame's label is the expert
            # command for the state the policy visited; the policy's own
            # *proposal* for this state is kept so the takeover statistics can be
            # read off the data (the applied action is the expert's while the
            # expert holds control, so it is not the proposal).
            observation["policy_action"] = (
                np.asarray(self._last_action, dtype=np.float32)
                if self._policy_proposal is None
                else np.asarray(self._policy_proposal, dtype=np.float32)
            )
            label = np.asarray(self._expert_label, dtype=np.float32)
        self._recorder.add(observation, action=label)

    # ------------------------------------------------------------------ #
    # Episode events / primitives
    # ------------------------------------------------------------------ #
    def _episode_events(self) -> bool:
        """Post-step episode bookkeeping; returns True to skip this iteration.

        The handoff teleport is the harness's station hand-off (never used in
        `direct`: the constructor disables its fallback and the trigger decides).
        """
        if self._done or self._sample is None:
            return False
        sample = self._sample
        pos = np.asarray(self.spawner.position(sample), dtype=float)
        z = float(pos[2])
        if z < self.belt_top - 0.25:
            self._notes.append("fruit fell off the line")
            self._finalize(notes=self._notes)
            return True
        if self.presentation == "handoff":
            if not self._handoff_done and float(pos[1]) <= self.cfg.pick_y + 0.10:
                arm = self.task.arms[self._active]
                jaw = np.asarray(arm.jaw_centre(), dtype=float)
                self.spawner.place(
                    sample,
                    np.array(
                        [jaw[0], jaw[1], self.belt_top + float(sample.diameter) / 2.0 + 0.002]
                    ),
                )
                sample.held = True
                for _ in range(20):
                    self.advance(1)
                self._handoff_done = True
                return True
            if z > self._belt_rest + 0.05:
                self._lifted = True
        return False

    def _run_primitive(self) -> None:
        """The contact work: `grasp_carry_place` on the measured fruit."""
        from .tasks import EpisodeResult

        self._decision_step = int(self._step)
        result = EpisodeResult(
            sample_index=self._sample.index,
            category=self._sample.category,
            grade=self._sample.grade,
            arm=self._active,
        )
        result = self.task.grasp_carry_place(
            self._active, self._sample, self._bin_index, result, verbose=self.verbose
        )
        self._grasped = bool(result.grasped)
        self._placed = bool(result.placed)
        self._lifted = bool(result.grasped)
        notes = list(self._notes) + list(result.notes)
        if (
            self.presentation == "direct"
            and result.grasped
            and not result.placed
        ):
            # `grasp_carry_place` already carried and released, so this is the
            # harness helper re-run only when a grasp did not end on the belt
            # (the plan's "on res.grasped call carry_and_release"). On a placed
            # episode it would repeat the same arm motion with an empty hand.
            self._say("[rl]   grasp did not land on the belt; re-running carry_and_release")
            carry_and_release(
                self.task.arms[self._active], self.cfg, self._bin_index, self.advance
            )
        self._finalize(notes=notes)

    def _run_scripted(self) -> None:
        """`--ablate scripted`: the demonstration controller runs the episode."""
        self._decision_step = int(self._step)
        state = next(
            (s for s in self.spawner.state() if int(s["index"]) == int(self._sample.index)),
            None,
        )
        if state is None:
            self._finalize(notes=["scripted ablation: target left the line"])
            return
        result = self.task.run(state, self._bin_index, verbose=self.verbose)
        self._grasped = bool(result.grasped)
        self._placed = bool(result.placed)
        self._lifted = bool(result.grasped)
        self._finalize(notes=list(self._notes) + list(result.notes))

    def _finalize(self, notes: list[str] | None = None) -> None:
        if self._done:
            return
        self._ticks = int(round((self._sim_time() - self._episode_t0) * 120.0))
        decision = (
            int(self._decision_step)
            if self._decision_step is not None
            else min(int(self._step), int(self.reward.horizon))
        )
        final = np.asarray(self.spawner.position(self._sample), dtype=float)
        success = bool(self._lifted) and bool(self.cfg.on_output_belt(final))
        reward = self.reward.compute(success, decision)
        notes = list(self._notes if notes is None else notes)
        self._outcome = {
            "episode": self._episode,
            "category": self._sample.category,
            "grade": self._sample.grade,
            "diameter": float(self._sample.diameter),
            "bin_index": self._bin_index,
            "arm": self._active,
            "success": success,
            "grasped": bool(self._grasped),
            "placed": bool(self._placed),
            "lifted": bool(self._lifted),
            "ticks": self._ticks,
            "decision": decision,
            "reward": float(reward),
            "notes": notes,
            "final_position": final.tolist(),
            "presentation": self.presentation,
            "ablate": self.ablate,
            "dagger": self.dagger is not None,
            "interventions": int(self._ep_interventions),
            "expert_ticks": int(self._ep_expert_ticks),
        }
        if self._event:
            horizons = np.asarray(self._event_horizons, dtype=float)
            continuity = np.asarray(self._event_continuities, dtype=float)
            self._outcome["event_chunks"] = int(horizons.size)
            self._outcome["event_horizon_2"] = int((horizons == 2).sum())
            self._outcome["event_horizon_4"] = int((horizons == 4).sum())
            self._outcome["event_horizon_6"] = int((horizons == 6).sum())
            self._outcome["event_mean_horizon"] = (
                float(horizons.mean()) if horizons.size else float("nan")
            )
            self._outcome["event_continuity_median"] = (
                float(np.median(continuity)) if continuity.size else float("nan")
            )
        if self._recorder is not None:
            self._recorder.finish(
                success=success,
                grasped=bool(self._grasped),
                placed=bool(self._placed),
                reward=float(reward),
                ticks=self._ticks,
                notes=notes,
            )
        self.spawner.protected = None
        self._done = True
        report = self._collect_rtc_report()
        if report:
            self._outcome.update(report)
        self._say(
            f"[rl] episode {self._episode}: {self._sample.category} "
            f"d={self._sample.diameter * 100:.1f}cm bin={self._bin_index} "
            f"arm={self._active} success={success} grasped={bool(self._grasped)} "
            f"placed={bool(self._placed)} ticks={self._ticks} decision={decision} "
            f"reward={reward:.4f} notes={notes} presentation={self.presentation} "
            f"ablate={self.ablate}"
        )
        if report:
            self._say(
                f"[rtc]   boundaries={report['rtc_boundaries']} "
                f"median={report['rtc_boundary_median']:.4f} "
                f"within={report['rtc_within_median']:.4f} "
                f"step={report['rtc_step_median']:.4f} "
                f"jerk={report['rtc_jerk_median']:.4f} "
                f"switches={report['rtc_switches']} "
                f"decisions={report['rtc_decisions']} "
                f"rate={report['rtc_decision_rate']:.1f}/s "
                f"policy_ms={report['rtc_policy_ms_median']:.1f} "
                f"policy_ms/step={report['rtc_policy_ms_per_step']:.2f} "
                f"control_ms={report['rtc_control_ms_median']:.1f}"
            )
        if self._event:
            self._say(
                f"[event] chunks={self._outcome['event_chunks']} "
                f"h2={self._outcome['event_horizon_2']} "
                f"h4={self._outcome['event_horizon_4']} "
                f"h6={self._outcome['event_horizon_6']} "
                f"mean={self._outcome['event_mean_horizon']:.2f} "
                f"continuity_med={self._outcome['event_continuity_median']:.5f}"
            )
        if self.dagger is not None:
            decisions = max(1, int(self._step) // 4)
            self._say(
                f"[rl]   dagger: interventions={self._ep_interventions}/{decisions} "
                f"expert_ticks={self._ep_expert_ticks}/{int(self._step)}"
            )

    def _collect_rtc_report(self) -> dict:
        """Episode-level executed-boundary + wall-time stats (empty when off)."""
        if not self._rtc_report:
            return {}
        boundary = np.asarray(self._report_boundary, dtype=np.float64)
        within = np.asarray(self._report_within, dtype=np.float64)
        step = np.asarray(self._report_step, dtype=np.float64)
        jerk = np.asarray(self._report_jerk, dtype=np.float64)
        controls = np.asarray(self._report_control_ms, dtype=np.float64)
        policy = np.asarray(self._report_policy_ms, dtype=np.float64)
        decisions = (
            int(self.rtc.chunks_sampled)
            if self.rtc is not None
            else int(self._report_decisions)
        )
        # Decision rate over the *policy phase* (the steps before the scripted
        # primitive takes over), not the whole episode: the primitive's carry
        # ticks would dilute it (measured: an E=1 episode reads 119/s on its
        # policy steps and 13/s over the full episode).
        seconds = max(int(self._step), 1) / 120.0
        policy_total = float(policy.sum()) if policy.size else 0.0

        def _median(values: np.ndarray) -> float:
            return float(np.median(values)) if values.size else float("nan")

        self._rtc_totals["boundary"].extend(boundary.tolist())
        self._rtc_totals["within"].extend(within.tolist())
        self._rtc_totals["step"].extend(step.tolist())
        self._rtc_totals["jerk"].extend(jerk.tolist())
        self._rtc_totals["control_ms"].extend(controls.tolist())
        self._rtc_totals["policy_ms"].extend(policy.tolist())
        self._rtc_totals["policy_ms_total"] += policy_total
        self._rtc_totals["switches"] += int(boundary.size)
        self._rtc_totals["steps"] += int(self._step)
        self._rtc_totals["decisions"] += decisions
        self._rtc_totals["chunks"] += int(
            self.rtc.chunks_sampled if self.rtc is not None else 0
        )
        return {
            "rtc_boundaries": int(boundary.size),
            "rtc_boundary_median": _median(boundary),
            "rtc_boundary_p90": (
                float(np.percentile(boundary, 90)) if boundary.size else float("nan")
            ),
            "rtc_within_median": _median(within),
            "rtc_within_p90": (
                float(np.percentile(within, 90)) if within.size else float("nan")
            ),
            "rtc_step_median": _median(step),
            "rtc_step_p90": (
                float(np.percentile(step, 90)) if step.size else float("nan")
            ),
            "rtc_jerk_median": _median(jerk),
            "rtc_jerk_p90": (
                float(np.percentile(jerk, 90)) if jerk.size else float("nan")
            ),
            "rtc_switches": int(boundary.size),
            "rtc_decisions": decisions,
            "rtc_decision_rate": decisions / seconds,
            "rtc_policy_ms_median": _median(policy),
            "rtc_policy_ms_p90": (
                float(np.percentile(policy, 90)) if policy.size else float("nan")
            ),
            "rtc_policy_ms_per_step": policy_total / max(int(self._step), 1),
            "rtc_control_ms_median": _median(controls),
        }

    def report_summary(self) -> str | None:
        """Run-level RTC timing/boundary summary; None when reporting is off."""
        if not self._rtc_report:
            return None
        boundary = np.asarray(self._rtc_totals["boundary"], dtype=np.float64)
        within = np.asarray(self._rtc_totals["within"], dtype=np.float64)
        step = np.asarray(self._rtc_totals["step"], dtype=np.float64)
        jerk = np.asarray(self._rtc_totals["jerk"], dtype=np.float64)
        controls = np.asarray(self._rtc_totals["control_ms"], dtype=np.float64)
        policy = np.asarray(self._rtc_totals["policy_ms"], dtype=np.float64)
        steps = max(int(self._rtc_totals["steps"]), 1)
        decisions = int(self._rtc_totals["decisions"])
        seconds = steps / 120.0

        def _stats(values: np.ndarray, label: str) -> str:
            if not values.size:
                return f"{label}=n/a"
            return (
                f"{label} n={values.size} med={np.median(values):.2f} "
                f"p90={np.percentile(values, 90):.2f} max={values.max():.2f}"
            )

        return (
            f"[rtc] summary: steps={self._rtc_totals['steps']} "
            f"chunks={self._rtc_totals['chunks']} "
            f"decisions={decisions} "
            f"decisions/s={decisions / seconds:.1f} "
            f"switches={self._rtc_totals['switches']} | "
            f"step {_stats(step, 'rad')} | jerk {_stats(jerk, 'rad')} | "
            f"boundary {_stats(boundary, 'rad')} | within {_stats(within, 'rad')} | "
            f"policy_ms {_stats(policy, 'ms')} | "
            f"policy_ms/step {self._rtc_totals['policy_ms_total'] / steps:.2f} | "
            f"control_ms {_stats(controls, 'ms')}"
        )

    def _step_result(self) -> StepResult:
        outcome = self._outcome or {}
        return StepResult(
            obs=self._obs_snapshot(),
            reward=float(outcome.get("reward", 0.0)),
            done=bool(self._done),
            info=dict(outcome),
        )

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        """No-op: the driver owns the SimulationApp lifetime."""
