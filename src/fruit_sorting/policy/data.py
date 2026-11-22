"""Dataset for the recorded pick-and-place episodes.

P28-B: this module also owns the **belt-speed channel**, the 26th proprio
scalar (design `logs/p28/SPEED_CHANNEL_DESIGN.md` section 2.2). The channel is
gated by ``FRUIT_OBS_SPEED`` (default unset = the shipped 25-D observation, so
every pre-existing path is byte-inert) and its value is **synthesised at load
time** from a per-store pin - no recorded array changes meaning:

* the pin's resolution chain is
  ``index.json`` entry -> ``"shard"`` -> ``<shard>/manifest.json`` ->
  ``supply.belt_speed`` (written by `scripts/40_collect_demos.py` since the
  P28-A commit, and by `rl_env._build_manifest` for a rollout run dir), then the
  caller's ``belt_speed=`` declaration, then the documented legacy table
  :data:`SPEED_PIN_KNOWN`, and **neither -> a ValueError** (P28 Gate A B2: there
  is no silent default). A manifest value and a legacy pin must agree;
* the normaliser entry is the **fixed** pair (:data:`SPEED_CHANNEL_MEAN`,
  :data:`SPEED_CHANNEL_STD`), never a store statistic - the fine-tune inherits
  the checkpoint's normaliser verbatim, so a derived value would silently
  redefine the channel's units on a later retrain (design C2);
* the live value at inference comes from :func:`belt_speed_scalar`, i.e.
  ``trigger.transport_speed()`` - the *same* estimator the scripted primitive
  acts on (design C1), so the model and the schedule cannot disagree.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np

from .vision import camera_pose, crop_and_resize, foveal_window, project
from .skills import label_episode
from .trigger import transport_speed

#: The shipped observation width: 22 joint positions + finger + 2 tactile.
PROPRIO_DIM = 25


def action_mode_from_env() -> str:
    """P145d.8: the action **representation** (`FRUIT_ACTION`).

    ``""`` (default) = the absolute 7 joint targets + finger (the shipment).
    ``"dq"`` = the per-step **joint delta** + finger: the arm servo integrates
    ``q_target = q_measured + dq`` once per executed waypoint.
    ``"rel"`` = the **chunk-relative** joint action: the 16 waypoints are
    offsets from the window's first frame, so the model predicts the *shape* of
    the motion and the env re-anchors it to the measured joints at the chunk's
    start (the 13k-rollout study's chunk-wise relative form; absolute targets
    are what under-execute the demos' motions - measured 35 % on the lateral aim
    and 42 % on the tracking hold). The measured
    direct loop commits to the *band-mean* aim with absolute targets (the jaw
    stops at x 0.27 for a fruit at 0.225, on every episode), which is the
    classic absolute-endpoint bias; a delta action turns the same policy into a
    residual servo whose error the next observation corrects.
    """
    raw = os.environ.get("FRUIT_ACTION", "").strip().lower()
    if raw not in ("", "dq", "rel", "posvel", "hybrid", "jaw", "tcp"):
        raise ValueError(
            f"FRUIT_ACTION={raw!r} is not one of '', 'dq', 'rel', 'posvel', 'jaw', 'tcp'"
        )
    return raw

#: The P28-B gate. ``1`` arms the 26th scalar; unset/anything else keeps the
#: shipped 25-D observation (and every store's 25-D assembly) byte-identical.
SPEED_CHANNEL_ENV = "FRUIT_OBS_SPEED"

#: The fixed normaliser pair for the channel (design C2): mean 0.12 m/s (the
#: shipped belt), std 0.05 m/s. Under it 0.06 -> z = -1.20, 0.08 -> -0.80,
#: 0.10 -> -0.40, 0.12 -> 0.00, 0.15 -> +0.60: every speed the line can
#: plausibly run sits inside |z| <= 1.3.
SPEED_CHANNEL_MEAN = 0.12
SPEED_CHANNEL_STD = 0.05

#: P141: the **goal** vector's auxiliary pair and the **per-frame** belt trace.
#:
#: The shipped goal is ``[xyz, v(3), diameter, bin_index]`` - 8 numbers, all
#: snapshotted when the fruit is selected. That is enough for a constant belt and
#: blind to a belt that changes speed: the record's ``FRUIT_BELT_WAVE`` cells
#: move the surface by 0.04 m/s at 0.5 Hz, and two frames 33 ms apart differ by
#: ~1.3 mm, which is inside the camera's own 2 mm position error - so the wave
#: is **not** observable from the image horizon at any horizon length that fits
#: the encoder's receptive field. It has to be an input.
#:
#: Two terms, both gated by :data:`GOAL_AUX_ENV`, default off (the 8-D goal and
#: every existing store stay byte-identical):
#:
#: * ``v_belt``  - the belt's own surface speed [m/s], **positive downstream**,
#:   from the encoder (`tasks._belt_speed_estimate`), the same estimator the
#:   trigger and the 26th proprio channel read;
#: * ``a_belt``  - its low-passed derivative [m/s^2], ~0.05 s time constant.
#:
#: The store derives both from the recorded per-frame ``belt_speed`` array
#: (written by the collector when ``FRUIT_OBS_SPEED=1``), so a wave-capable
#: store and the live loop assemble the same numbers.
GOAL_DIM = 8
GOAL_AUX_ENV = "FRUIT_OBS_GOAL_AUX"
GOAL_AUX_MEAN = (0.12, 0.0)
GOAL_AUX_STD = (0.05, 0.15)
BELT_TAU_ENV = "FRUIT_OBS_BELT_TAU"
BELT_TAU_DEFAULT = 0.05


def goal_aux_enabled() -> bool:
    """Is the goal's ``(v_belt, a_belt)`` pair armed?"""
    return os.environ.get(GOAL_AUX_ENV, "0").strip() == "1"


def belt_accel_trace(
    speed: np.ndarray, dt: float = 1.0 / 120.0, tau: float | None = None
) -> np.ndarray:
    """Low-passed derivative of a per-frame belt-speed trace [m/s^2].

    The same first-order filter the live loop runs, so a store's ``a_belt`` and
    the deployed one are the same function of the same signal (the record's
    rule: the model and the schedule must not disagree). ``tau`` is the EMA time
    constant; the per-tick weight is ``dt / (tau + dt)``.
    """
    values = np.asarray(speed, dtype=np.float64).reshape(-1)
    if tau is None:
        tau = float(os.environ.get(BELT_TAU_ENV, str(BELT_TAU_DEFAULT)))
    alpha = float(dt) / (float(tau) + float(dt))
    out = np.zeros_like(values)
    accel = 0.0
    for i in range(1, values.size):
        accel = (1.0 - alpha) * accel + alpha * (
            (values[i] - values[i - 1]) / float(dt)
        )
        out[i] = accel
    return out.astype(np.float32)

#: Fallback pin when neither the store's manifest nor the caller declares one.
#: P28 Gate A (B2): there is **no silent 0.12 default any more** - a store whose
#: speed is neither in its artifact nor declared **raises**, because a wrong pin
#: is a silent scenario change (`demos_v12_015` at 0.15 and the 0.06 lineage are
#: exactly the cases the design's risk 2 names). What remains is a
#: *provenance* table for the legacy stores: the basenames whose collection speed
#: is documented by the design's section 4.3 (collection script + log) and
#: cross-checked here against each store's recorded goal-`vy` mean:
#: 0.06 -> -0.060, 0.12 -> -0.119..-0.120, and `demos_v12_015` at 0.15 is
#: deliberately **absent** so it must be pinned.
SPEED_PIN_KNOWN: dict[str, float] = {
    # the 0.06 lineage (goal vy mean -0.060 on every merged store below)
    "demos_v7": 0.06, "v7_s0": 0.06, "v7_s1": 0.06, "v7_s2": 0.06,
    "demos_v8": 0.06, "v8_s0": 0.06, "v8_s1": 0.06, "v8_s2": 0.06,
    "demos_v9": 0.06, "v9_s0": 0.06, "v9_s1": 0.06, "v9_s2": 0.06,
    "demos_v10": 0.06, "v10_s0": 0.06, "v10_s1": 0.06, "v10_s2": 0.06,
    "v10_s3": 0.06, "demos_v10_vlash": 0.06,
    # the 0.12 lineage (goal vy mean -0.119..-0.120)
    "demos_v11": 0.12, "v11_s0": 0.12, "v11_s1": 0.12,
    "demos_v12": 0.12, "v12d_s02": 0.12,
    "demos_v13p": 0.12, "v13p_probe": 0.12, "v13p_s0": 0.12,
    "v13p_s0_r1": 0.12, "v13p_s1": 0.12, "v13p_s1_r1": 0.12,
    "v13p_s1_r2": 0.12, "v13p_s2": 0.12, "v13p_s2_r1": 0.12,
    "v13p_s2_r2": 0.12,
    "demos_v12_spaced": 0.12, "v12w_s0": 0.12, "v12w_s02": 0.12,
    "v12w_s03": 0.12, "v12w_s04": 0.12, "v12w_s05": 0.12,
    "v12w_s06": 0.12, "v12w_s1": 0.12,
}

#: A declared pin and a manifest value within this tolerance are the same pin.
#: Further apart is a provenance error, not a rounding difference (design
#: section 2.2 risk 2) - the loader refuses rather than training on a wrong
#: constant.
SPEED_PIN_TOL = 1e-3


def speed_channel_enabled() -> bool:
    """Whether the 26-D observation (the belt-speed channel) is armed."""
    return os.environ.get(SPEED_CHANNEL_ENV, "0").strip() == "1"


def belt_speed_scalar(
    spawner, sample=None, *, use_encoder: bool = True, fallback: float | None = None
) -> float:
    """The channel's live value: ``trigger.transport_speed()``'s answer [m/s].

    The estimator returns the belt encoder when it is finite and non-zero and
    falls back to the fruit's measured velocity otherwise (tagged in
    ``trigger.transport_speed``'s second return value). This wrapper is shared
    by **both** observation-assembly sites - `rl_env.proprio()` and
    `scripts/60_eval_policy.py` - so the two paths cannot drift (the
    `scripts/114_rl_obs_diff.py` guard is what pins that they agree).

    The measured velocity is read **lazily**, only when the estimator says the
    encoder is unusable: on the shipped build the encoder is a setpoint echo
    (`conveyor.py`, P27), so the control loop pays one attribute read and no
    rigid-body read.

    ``use_encoder`` stays **True** even when the trigger's own
    ``FRUIT_POLICY_TRIGGER_ENCODER=0`` selects the measured velocity: the
    channel is the model's input, and letting a trigger knob change it would
    make an A/B arm change the observation as well as the trigger (P28 Gate A
    section 1, correction 1).

    ``fallback`` is the *configured* belt speed [m/s]. With no belt on the
    spawner (unit paths) the channel reports ``abs(fallback)``; emitting 0.0
    instead would be z = -2.40 under the fixed (0.12, 0.05) pair and would
    *mean* "the belt stopped" - a healthy run would look like a policy failure
    with no error anywhere (P28 Gate A section 1, correction 2). No belt and no
    fallback raises.
    """
    belt = getattr(spawner, "belt", None)
    if belt is None:
        if fallback is None:
            raise RuntimeError(
                "the belt-speed channel needs a belt on the spawner or an "
                "explicit fallback (the configured belt speed); 0.0 is not a "
                "valid value - it reads as 'the belt is stopped'"
            )
        return float(abs(fallback))
    # P141: the belt's **applied** surface speed, not the cleat-phase echo.
    # `encoder_speed` is only recomputed inside `Conveyor.step` while the cleats
    # exist, and they are off by default, so it reports the value it was
    # initialised with - measured: a wave collection recorded a constant 0.1200
    # in every frame. `surface_speed` is the number `_apply_speed` writes into
    # `PhysxSurfaceVelocityAPI`, i.e. the belt the fruit ride. On the shipped
    # constant belt the two are equal, which is why this is inert there.
    encoder = getattr(belt, "surface_speed", None)
    if encoder is None:
        encoder = getattr(belt, "encoder_speed", None)
    # `transport_speed`'s fruit/jaw arguments are unused by its body (the value
    # is the encoder-or-measured scalar); pass None rather than add a pose read
    # to the control loop.
    speed, source = transport_speed(
        None, None, encoder_speed=encoder, use_encoder=use_encoder
    )
    if source == "measured" and sample is not None:
        speed, source = transport_speed(
            None,
            None,
            encoder_speed=encoder,
            measured_velocity=spawner.velocity(sample),
            use_encoder=use_encoder,
        )
    return float(speed)


def _manifest_belt_speed(path: str) -> float | None:
    """``supply.belt_speed`` (or a top-level ``belt_speed``) from a manifest."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    for holder in (data.get("supply"), data):
        if isinstance(holder, dict) and "belt_speed" in holder:
            try:
                return float(holder["belt_speed"])
            except (TypeError, ValueError):
                return None
    return None


def _area_resize_axis(v: np.ndarray, out_n: int, axis: int) -> np.ndarray:
    """Area-average `v` along `axis` to `out_n` samples (exact overlap weights).

    `np.interp` over the cumulative sum of `v`: the integral between two
    fractional edges is the difference of the interpolated prefix sums, so a
    resize to any size (integer or not) is exact and needs no scipy/cv2.
    """
    v = np.moveaxis(v, axis, 0)
    n = v.shape[0]
    flat = np.ascontiguousarray(v.reshape(n, -1), dtype=np.float32)
    cumulative = np.empty((n + 1, flat.shape[1]), dtype=np.float32)
    cumulative[0] = 0.0
    np.cumsum(flat, axis=0, out=cumulative[1:])
    edges = np.linspace(0.0, float(n), out_n + 1)
    lower = np.minimum(np.floor(edges).astype(np.intp), n - 1)
    frac = (edges - lower).astype(np.float32)
    values = (
        cumulative[lower] * (1.0 - frac)[:, None]
        + cumulative[lower + 1] * frac[:, None]
    )
    out = (values[1:] - values[:-1]) / (edges[1:] - edges[:-1]).astype(np.float32)[:, None]
    out = out.reshape((out_n,) + v.shape[1:])
    return np.moveaxis(out, 0, axis)


def downsample_frame(image: np.ndarray, size: int = 128) -> np.ndarray:
    """Resize a camera frame to the square `size` policy input.

    The head camera is 240x424 but the policy consumes 128x128.  The old
    top-left stride crop cut the pick station out of the input (measured on
    `demos_v8`: 27 % of the target blobs sat entirely below row 127 and only
    53 % were fully inside - WORKLOG "P4 follow-up diagnosis"), so the whole
    frame is area-averaged down to the square input instead.  Training
    (`EpisodeStore`) and inference (`PolicyRunner`) must call this same
    function or the policy sees a different camera than it learned on.
    """
    image = np.asarray(image)
    if image.shape[0] == size and image.shape[1] == size:
        return image
    out = _area_resize_axis(image, size, axis=0)
    return np.ascontiguousarray(_area_resize_axis(out, size, axis=1))


@dataclass
class Normalizer:
    """Per-channel mean/std for the low-dimensional inputs and the actions."""

    action_mean: np.ndarray
    action_std: np.ndarray
    obs_mean: np.ndarray
    obs_std: np.ndarray
    goal_mean: np.ndarray
    goal_std: np.ndarray

    def normalize_action(self, action: np.ndarray) -> np.ndarray:
        return (action - self.action_mean) / self.action_std

    def denormalize_action(self, action: np.ndarray) -> np.ndarray:
        return action * self.action_std + self.action_mean

    def normalize_obs(self, obs: np.ndarray) -> np.ndarray:
        return (obs - self.obs_mean) / self.obs_std

    def normalize_goal(self, goal: np.ndarray) -> np.ndarray:
        return (goal - self.goal_mean) / self.goal_std

    def as_dict(self) -> dict:
        return {
            "action_mean": self.action_mean.tolist(),
            "action_std": self.action_std.tolist(),
            "obs_mean": self.obs_mean.tolist(),
            "obs_std": self.obs_std.tolist(),
            "goal_mean": self.goal_mean.tolist(),
            "goal_std": self.goal_std.tolist(),
        }


class EpisodeStore:
    """Loads recorded ``.npz`` episodes and slices observation/action windows.

    P28-B: pass ``speed_channel=True`` (or ``belt_speed=<m/s>``, or set
    ``FRUIT_OBS_SPEED=1``) to append the belt-speed scalar to the proprio
    vector - the store then returns ``proprio_dim = 26`` and its windows must
    be trained against a 26-D checkpoint. The pin is resolved **per episode**
    from the manifest chain (see the module docstring); ``belt_speed``
    *declares* the legacy pin for stores that predate the manifest field, and
    an unpinned store with no manifest value raises (P28 Gate A B2).
    """

    #: Channels fed to the visual encoder: RGB (3) + depth (1) [+ target mask (1)].
    IMAGE_CHANNELS = 5

    def __init__(
        self,
        root: str,
        obs_horizon: int = 2,
        action_horizon: int = 16,
        image_size: int = 128,
        only_successful: bool = True,
        belt_speed: float | None = None,
        speed_channel: bool | None = None,
        goal_aux: bool | None = None,
        cmd_channel: bool | None = None,
    ):
        self.root = root
        self.obs_horizon = obs_horizon
        self.action_horizon = action_horizon
        self.image_size = image_size
        #: P28-B: append the synthesised belt-speed scalar (25 -> 26). ``None``
        #: defers to the `FRUIT_OBS_SPEED` gate, and an explicit ``belt_speed``
        #: arms the channel on its own (so a caller can never hand a store a pin
        #: that is silently dropped). With the channel off the assembly below is
        #: the shipped 25-D one, byte for byte.
        if speed_channel is None:
            speed_channel = bool(belt_speed is not None or speed_channel_enabled())
        self.speed_channel = bool(speed_channel)
        #: The caller's declared pin (the `--store-speed` value), or None.
        self.belt_speed = None if belt_speed is None else float(belt_speed)
        #: The width `__getitem__` returns - `finetune` cross-checks it against
        #: the checkpoint's `config["proprio_dim"]`.
        #: P145d.4: the **commanded** finger as an observation channel. The
        #: measured finger is aliased at the loaded close (the drive's +6 mm),
        #: so the same observation means "early ramp" or "loaded hold"; the
        #: previous command disambiguates them. Training reads it from the
        #: recorded action stream; deployment from the env's `_last_finger`.
        #: P145d.8: the action representation ("": absolute joints, "dq": deltas)
        self.action_mode = action_mode_from_env()
        #: P163: the **foveal crop** - `FRUIT_IMAGE_FOVEA=<crop px>` cuts a square
        #: window around the target fruit's projected position and resizes it to
        #: `image_size`. Measured (P161): the fruit is 1-4 px in the full frame
        #: (0-1 px at 128), so the visual encoder cannot see it; the crop makes it
        #: 15-40 px. 0 = the shipped full frame.
        self.fovea = int(float(os.environ.get("FRUIT_IMAGE_FOVEA", "0") or 0))
        #: P173b: the **phase-dependent view**. The crop is what made the approach
        #: visible (the fruit is 1-4 px in the full frame), but it also removes the
        #: output bins, and the place phase's measured error at demonstration
        #: states is 48 mm TCP-equivalent (`logs/p145/place_fit.py`) - the largest
        #: of any phase. With `FRUIT_IMAGE_FOVEA_PHASE=1` the loader crops the
        #: *pre-close* frames (the label's finger open) and feeds the **wide**
        #: frame once the label's finger is closed; the environment does the same,
        #: switching on its own latch. The phase is also in the router's skill
        #: conditioning, so one encoder can hold both statistics.
        self.fovea_phase = os.environ.get("FRUIT_IMAGE_FOVEA_PHASE", "0").strip() == "1"
        #: P164: crop **augmentation** for the loader only (training). Measured in
        #: the literature: a standard policy scores 0 % at a 0.7x image scale and
        #: 0.725 with 0.7-1.3 random scale augmentation; a crop's centre/size is
        #: exactly such a scale/translation shift, so the loader jitters both.
        #: `FRUIT_IMAGE_AUG=<0..0.5>`: size x (1 +- a), centre +- a*crop/4.
        self.aug = float(os.environ.get("FRUIT_IMAGE_AUG", "0") or 0.0)
        self._cam_eye = self._cam_target = None
        if self.fovea > 0:
            _name = os.environ.get("FRUIT_HEAD_CAMERA", "").strip()
            self._cam_eye, self._cam_target = camera_pose()
        #: P149: drop a **rollout store's** windows whose *action* reaches the
        #: close (`start + H > close`). Measured: the labels-only DAgger store's
        #: close-state action is one IK step from the measured joints (0.199 rad
        #: over 16 frames) while the demonstrations' is the tracking hold
        #: (0.734 rad); with `close_weight` the rollout store dominates the
        #: close-state fit and the deployed hold under-tracks by 2.4x, so the
        #: fruit slides out of the pads. The demos own the close/hold/lift; the
        #: rollout store keeps the approach states it was collected for.
        self.dagger_stop_before_close = int(
            float(os.environ.get("FRUIT_DAGGER_STOP_BEFORE_CLOSE", "0") or 0)
        )
        self.cmd_channel = (
            os.environ.get("FRUIT_OBS_CMD", "0") == "1"
            if cmd_channel is None else bool(cmd_channel)
        )
        #: P227v: the width is the **store's own**, not the OpenArm constant. The
        #: proprio is the whole articulation's DOF vector + the finger + the two
        #: tactile forces - 25 on the bimanual OpenArm (22 joints) and **12 on
        #: the single Panda** (9 joints) - so a store recorded on another arm
        #: would otherwise *declare* 25 while its windows are 12, and a model
        #: built from a 25/26-D checkpoint rejects it (the direct env's own
        #: assembly is arm-sized too: `rl_env.proprio` returned 13 against the
        #: checkpoint's 26). Resolved from the first episode below; the constant
        #: stays as the fallback for an empty store.
        self.proprio_dim = (
            PROPRIO_DIM + (1 if self.speed_channel else 0) + (1 if self.cmd_channel else 0)
        )
        #: P141: the goal's auxiliary pair. Like the speed channel this is a
        #: property of the artifact, and the fine-tune cross-checks it against
        #: the checkpoint's ``config["goal_dim"]``.
        if goal_aux is None:
            goal_aux = goal_aux_enabled()
        self.goal_aux = bool(goal_aux)
        self.goal_dim = GOAL_DIM + (2 if self.goal_aux else 0)
        self._speed_cache: dict[str, float | None] = {}

        index_path = os.path.join(root, "index.json")
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"{index_path} not found - collect demonstrations first")
        with open(index_path, encoding="utf-8") as fh:
            entries = json.load(fh)
        if only_successful:
            entries = [e for e in entries if e.get("success")]
        if not entries:
            raise ValueError(f"no usable episodes in {root}")

        #: Per-episode pin, in `self.episodes` order (only when the channel is
        #: on). A merged store can carry two speeds (the design's `demos_ss`),
        #: so the value is per episode, not per store.
        self.belt_speeds: list[float] = []
        self.speed_sources: list[str] = []
        #: P141: per-episode **per-frame** speed trace when the store carries one
        #: (``belt_speed`` array; written by the collector under
        #: ``FRUIT_OBS_SPEED=1``). ``None`` = a pre-P141 store, whose channel is
        #: the constant pin it always was.
        #: P145: rebuild the goal as the fruit's **current** state from the
        #: store's own `fruit_position` trace. The demonstrations' goal is a
        #: selection-time snapshot (the fruit's release point), i.e. a timer; a
        #: measured goal moves. Training on both without this would teach the
        #: policy two meanings for one channel. A store recorded with
        #: `goal_source=perception` already moves and is left alone.
        self.moving_goal = os.environ.get("FRUIT_TRAIN_GOAL", "stored").strip().lower() in (
            "moving", "dynamic", "perception"
        )
        self.goal_rebuilt = 0
        #: P145: focus a DAgger store on the frames that carry the correction.
        #: A pick episode is ~100 frames of "hold the grasp pose" plus a 15-frame
        #: close ramp; the hold is already in the anchor, the ramp is not. With
        #: this set, windows starting more than N frames before the ramp's first
        #: frame are dropped (0 = keep every valid window).
        self.dagger_focus = max(0, int(os.environ.get("FRUIT_DAGGER_FOCUS", "0")))
        #: P145c: keep **only the close window** of each episode - the frames
        #: around the first closed-finger command. A close-only model has one mode
        #: (descend + close), so it is the test of whether the phase mixture is
        #: what holds the fit at 0.04 rad. `FRUIT_CLOSE_ONLY=1`, off by default.
        #: P145d: `FRUIT_ACTION=jaw` makes the store's action the **task-space
        #: target** `[jaw xyz, finger]` of the next 30 Hz sample, from the `jaw`
        #: key the P145d collector records. Default off: every store's action is
        #: the recorded 9-D joint command, byte for byte.
        self.action_jaw = os.environ.get("FRUIT_ACTION", "").strip().lower() in (
            "jaw", "cartesian", "tcp"
        )
        self.close_only = os.environ.get("FRUIT_CLOSE_ONLY", "0") == "1"
        self.close_lead = max(0, int(os.environ.get("FRUIT_CLOSE_LEAD", "5")))
        self.close_tail = max(0, int(os.environ.get("FRUIT_CLOSE_TAIL", "10")))
        self.close_kept = 0
        #: P145: keep only the **carry/place** half of a plain demonstration
        #: episode (post close). The pick is taught by the DAgger store, the
        #: carry by the demonstrations; mixing the demonstrations' pick windows
        #: back in fights the correction the DAgger store exists to make.
        self.base_carry_only = os.environ.get("FRUIT_BASE_CARRY_ONLY", "0") == "1"
        self.base_kept = 0
        self.speed_traces: list[np.ndarray | None] = []
        self.belt_accels: list[np.ndarray | None] = []
        self.episodes: list[dict] = []
        for entry in entries:
            data = np.load(os.path.join(root, entry["file"]))
            action_array = data["action"]
            _hybrid_now = action_mode_from_env() == "hybrid"
            if (self.action_jaw or _hybrid_now) and "jaw" in data.files:
                # (T,3) task-space target + (T,1) finger. P145d.1: prefer the
                # **commanded** IK target (`cmd_tcp`, the setpoint the scripted
                # close asked the servo for) when it is fresh; during the wait the
                # scripted line holds with joint targets and the achieved `tcp` is
                # the right label (a static hold). The first attempt used the
                # achieved jaw of the *next* sample, i.e. the servo's lagging
                # response, and the policy learned to reproduce the lag.
                _finger = np.asarray(data["finger_opening"], dtype=np.float32).reshape(-1, 1)
                if "cmd_tcp" in data.files:
                    _cmd = np.asarray(data["cmd_tcp"], dtype=np.float32)
                    if "cmd_fresh" in data.files:
                        _fresh = np.asarray(data["cmd_fresh"], dtype=np.float32).reshape(-1) > 0.5
                    else:
                        _fresh = np.ones(len(_cmd), dtype=bool)
                    _achieved = np.asarray(data["tcp"], dtype=np.float32)
                    _target = np.where(_fresh[:, None], _cmd, _achieved)
                else:
                    _target = np.asarray(data["jaw"], dtype=np.float32)
                if _hybrid_now:
                    # P171: the **12-D joint head** - the joints the scripted arm
                    # commanded plus the jaw target it asked for, in one action:
                    # `[pos(7), finger, finger, jaw(3)]`. One state distribution,
                    # two action forms the policy can switch between by phase.
                    _joints = np.asarray(data["action"], dtype=np.float32)[:, :7]
                    _f2 = np.asarray(data["action"], dtype=np.float32)[:, 7:8]
                    action_array = np.concatenate([_joints, _f2, _f2, _target], axis=1)
                else:
                    action_array = np.concatenate([_target, _finger], axis=1)
            has_mask = "target_mask" in data.files
            skills = None
            if all(k in data.files for k in ("fruit_position", "finger_opening", "goal")):
                # P145d.3: label the skill on the **commanded** finger, not the
                # measured one. The measured finger sits +6 mm above the command
                # at the loaded close (p50: command 0.0269, measured 0.0304-0.0328)
                # and `label_episode`'s 0.030 threshold then labels the whole
                # loaded close `approach` (24/50 episodes have zero `grasp`
                # frames). The approach expert therefore contains the close and
                # re-opens the fingers at the re-plan; the measured value means
                # "free ramp" or "loaded squeeze" depending only on the fruit's
                # width. The action's finger channel is the command.
                _raw_action = np.asarray(data["action"], dtype=np.float32)
                _label_finger = (
                    _raw_action[:, 7]
                    if _raw_action.ndim == 2 and _raw_action.shape[1] > 7
                    else data["finger_opening"]
                )
                skills = label_episode(
                    data["fruit_position"], _label_finger, data["goal"]
                )
            self.episodes.append(
                {
                    "mask": (
                        (data["target_mask"].astype(np.float32) / 255.0)
                        if has_mask else None
                    ),
                    "skills": skills,
                    "rgb": data["image_rgb"],
                    "depth": data["image_distance_to_image_plane"],
                    "joint": data["joint_positions"],
                    "finger": data["finger_opening"],
                    "tactile": data["tactile"],
                    "goal": self._goal_trace(data, entry),
                    # P141: one float per recorded tick, present only when the
                    # channel was armed at collection time.
                    "belt_speed": (
                        np.asarray(data["belt_speed"], dtype=np.float32).reshape(-1)
                        if "belt_speed" in data.files else None
                    ),
                    "action": action_array,
                    # P145: a DAgger store may flag frames whose label is not the
                    # behaviour to clone (the expert's post-close hold). Absent =
                    # every frame valid, i.e. every pre-P145 store is unchanged.
                    "valid": (
                        np.asarray(data["dagger_valid"], dtype=np.float32).reshape(-1) > 0.5
                        if "dagger_valid" in data.files else None
                    ),
                    "meta": entry,
                }
            )
            if self.speed_channel:
                pin, source = self._resolve_speed(entry)
                self.belt_speeds.append(pin)
                self.speed_sources.append(source)
                trace = self.episodes[-1]["belt_speed"]
                if trace is not None and trace.size != int(
                    self.episodes[-1]["joint"].shape[0]
                ):
                    raise ValueError(
                        f"{entry.get('file')}: belt_speed has {trace.size} frames "
                        f"but the episode has {self.episodes[-1]['joint'].shape[0]}"
                    )
                self.speed_traces.append(trace)
                self.belt_accels.append(
                    None if trace is None else belt_accel_trace(trace)
                )

        # P227v: one width, the store's own (see the attribute's note). Every
        # episode of a store is written by one arm, so they must agree.
        widths = {int(np.asarray(ep["joint"]).shape[1]) for ep in self.episodes}
        if len(widths) > 1:
            raise ValueError(
                f"{root}: episodes disagree on the joint width {sorted(widths)}"
            )
        if widths:
            self.proprio_dim = (
                widths.pop()
                + 1
                + 2
                + (1 if self.speed_channel else 0)
                + (1 if self.cmd_channel else 0)
            )
        # Windows must fit inside each episode.
        self.windows: list[tuple[int, int]] = []
        for ep_index, episode in enumerate(self.episodes):
            length = episode["action"].shape[0]
            last = length - self.action_horizon
            valid = episode.get("valid")
            focus_lo = 0
            focus_hi = None
            if valid is not None and self.dagger_focus and not self.action_jaw:
                finger = np.asarray(episode["action"], dtype=np.float32)[:, 7]
                closed = np.nonzero(finger < 0.0439)[0]
                focus_lo = max(
                    0, (int(closed[0]) if closed.size else length) - self.dagger_focus
                )
            elif self.close_only and not self.action_jaw:
                finger = np.asarray(episode["action"], dtype=np.float32)[:, 7]
                closed = np.nonzero(finger < 0.0439)[0]
                if closed.size:
                    focus_lo = max(0, int(closed[0]) - self.close_lead)
                    focus_hi = int(closed[0]) + self.close_tail
                    self.close_kept += 1
                else:
                    focus_lo, focus_hi = 0, -1
            elif valid is None and self.base_carry_only and not self.action_jaw:
                finger = np.asarray(episode["action"], dtype=np.float32)[:, 7]
                closed = np.nonzero(finger < 0.0439)[0]
                # +15 frames = past the close ramp, i.e. the lift/carry/place.
                focus_lo = (int(closed[0]) + 15) if closed.size else length
                self.base_kept += 1
            if valid is not None and self.dagger_stop_before_close > 0:
                finger = np.asarray(episode["action"], dtype=np.float32)[:, 7]
                closed = np.nonzero(finger < 0.0439)[0]
                if closed.size:
                    _stop = max(0, int(closed[0]) - self.dagger_stop_before_close)
                    focus_hi = _stop if focus_hi is None else min(focus_hi, _stop)
            for start in range(self.obs_horizon - 1, last):
                if valid is not None:
                    lo = max(0, start - self.obs_horizon + 1)
                    if not valid[lo : start + self.action_horizon].all():
                        continue
                if start < focus_lo:
                    continue
                if focus_hi is not None and start > focus_hi:
                    continue
                self.windows.append((ep_index, start))
        if self.base_kept:
            print(
                f"[data] base: kept only the post-close windows of "
                f"{self.base_kept} episode(s) (FRUIT_BASE_CARRY_ONLY=1)",
                flush=True,
            )
        if self.goal_rebuilt:
            print(
                f"[data] goal: rebuilt {self.goal_rebuilt} episode(s) as the "
                f"fruit's current state (FRUIT_TRAIN_GOAL=moving); "
                f"{len(self.episodes) - self.goal_rebuilt} stored",
                flush=True,
            )
        if not self.windows:
            raise ValueError(
                f"episodes are shorter than obs_horizon + action_horizon "
                f"({self.obs_horizon} + {self.action_horizon})"
            )
        if self.speed_channel:
            pins = sorted({float(v) for v in self.belt_speeds})
            sources = {}
            for source in self.speed_sources:
                key = source.split(":", 1)[0]
                sources[key] = sources.get(key, 0) + 1
            print(
                f"[data] speed channel: {len(self.episodes)} episodes, "
                f"proprio_dim={self.proprio_dim}, pins={pins}, "
                f"declared={self.belt_speed}, sources={sources} "
                f"(unpinned stores raise; see SPEED_PIN_KNOWN)",
                flush=True,
            )

    def _goal_trace(self, data, entry: dict) -> np.ndarray:
        """The goal per frame: stored, or rebuilt as the fruit's current state."""
        goal = np.asarray(data["goal"], dtype=np.float32)
        if not self.moving_goal or entry.get("goal_source") == "perception":
            return goal
        fp = np.asarray(data["fruit_position"], dtype=np.float32)
        if fp.ndim != 2 or fp.shape[0] != goal.shape[0] or fp.shape[1] < 3:
            return goal
        trace = goal.copy()
        trace[:, 0:3] = fp[:, :3]
        # 30 Hz demo cadence (the recorder's own contract).
        trace[:, 3:6] = np.gradient(fp[:, :3].astype(np.float64), axis=0)[
            :, :3
        ].astype(np.float32) * 30.0
        self.goal_rebuilt += 1
        return trace

    # ------------------------------------------------------------------ #
    def _shard_manifest(self, entry: dict) -> str | None:
        """The manifest that can pin this episode's speed, or None.

        A merged store stamps the source directory into ``entry["shard"]``
        (`scripts/41_merge_demos.py`); a raw shard store (and a rollout run
        dir, whose `rl_env` manifest carries ``belt_speed``) is its own
        manifest. The shard path is repo-relative, so it is tried as given and
        relative to the store's parent - the caller's cwd may be anywhere.
        """
        shard = entry.get("shard")
        if shard:
            candidates = [
                os.path.join(str(shard), "manifest.json"),
                os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(self.root))),
                    str(shard),
                    "manifest.json",
                ),
            ]
            for candidate in candidates:
                if os.path.exists(candidate):
                    return candidate
            return None
        own = os.path.join(self.root, "manifest.json")
        return own if os.path.exists(own) else None

    def _resolve_speed(self, entry: dict) -> tuple[float, str]:
        """One episode's belt-speed pin and the source that produced it.

        P28 Gate A B2 - the order is:

        1. **the episode's own manifest** - ``entry["shard"]`` (a merged store's
           stamp, `scripts/41_merge_demos.py`) or the store's own
           ``manifest.json`` -> ``supply.belt_speed``. This is per *episode*, so
           a merged cross-speed store resolves each of its shards correctly;
        2. **the legacy pin** - the caller's declared ``belt_speed=`` (the
           `--store-speed` / `--base-speed` value), else the documented
           provenance table :data:`SPEED_PIN_KNOWN` for the legacy lineages;
        3. **neither -> raise.** There is no silent default: a store nobody
           pinned is a scenario change waiting to be attributed to the recipe.

        When (1) and (2) both exist they must **agree** (``SPEED_PIN_TOL``);
        a contradiction raises, naming both values and where each came from.
        """
        path = self._shard_manifest(entry)
        manifest_speed = None
        if path is not None:
            if path not in self._speed_cache:
                self._speed_cache[path] = _manifest_belt_speed(path)
            manifest_speed = self._speed_cache[path]
        legacy, legacy_source = self._legacy_pin(entry)
        if (
            legacy is not None
            and manifest_speed is not None
            and abs(legacy - manifest_speed) > SPEED_PIN_TOL
        ):
            raise ValueError(
                f"belt-speed pin conflict for {self.root}: {legacy_source} pins "
                f"{legacy:.4f} m/s but {path} records {manifest_speed:.4f} m/s. "
                f"The speed channel trains on a constant, so a wrong pin is a "
                f"silent scenario change; fix the pin (see the table in "
                f"logs/p28/SPEED_CHANNEL_DESIGN.md 4.3) or the manifest."
            )
        if manifest_speed is not None:
            return float(manifest_speed), f"manifest:{path}"
        if legacy is not None:
            return float(legacy), legacy_source
        raise ValueError(
            f"no belt-speed pin for {self.root} (episode "
            f"{entry.get('file', '?')}): its manifest records no "
            f"supply.belt_speed and no pin was declared. The speed channel "
            f"trains on a constant, so pin the store explicitly - "
            f"--store-speed {self.root}=<m/s> (or --base-speed) - using the "
            f"table in logs/p28/SPEED_CHANNEL_DESIGN.md 4.3; a store collected "
            f"since P28-A carries its speed in its own manifest."
        )

    def _legacy_pin(self, entry: dict) -> tuple[float | None, str | None]:
        """The non-manifest pin: the caller's declaration, else the known lineage."""
        if self.belt_speed is not None:
            return float(self.belt_speed), "declared"
        names = [
            os.path.basename(os.path.normpath(str(entry.get("shard") or self.root))),
            os.path.basename(os.path.normpath(self.root)),
        ]
        for name in names:
            if name in SPEED_PIN_KNOWN:
                return float(SPEED_PIN_KNOWN[name]), f"known:{name}"
        return None, None

    def speed_pin_summary(self) -> dict:
        """Provenance for the training record (and for `--store-speed` checks)."""
        if not self.speed_channel:
            return {"channel": False, "proprio_dim": self.proprio_dim}
        per_source: dict[str, int] = {}
        for source in self.speed_sources:
            key = source.split(":", 1)[0]
            per_source[key] = per_source.get(key, 0) + 1
        return {
            "channel": True,
            "proprio_dim": self.proprio_dim,
            "declared": self.belt_speed,
            "values": sorted({round(float(v), 6) for v in self.belt_speeds}),
            "sources": per_source,
            "manifests": sorted(
                path for path, value in self._speed_cache.items() if value is not None
            ),
        }

    # ------------------------------------------------------------------ #
    def __len__(self) -> int:
        return len(self.windows)

    def _downsample(self, image: np.ndarray) -> np.ndarray:
        return downsample_frame(image, self.image_size)

    def proprio(self, ep_index: int, t: int | None = None) -> np.ndarray:
        """The proprio vector for one episode - the single assembly site.

        ``t`` given: one frame, (proprio_dim,), exactly as `__getitem__` uses
        it. ``t=None``: every frame of the episode, (frames, proprio_dim), as
        `compute_normalizer` uses it. The belt-speed column (P28-B) is appended
        last and is constant per episode, so both forms agree by construction -
        and `_OffsetWindows` (the VLASH state offset) reuses this instead of
        duplicating the concatenation.
        """
        episode = self.episodes[ep_index]
        if t is None:
            parts = [
                np.concatenate(
                    [episode["joint"], episode["finger"], episode["tactile"]], axis=-1
                )
            ]
        else:
            parts = [
                episode["joint"][t].astype(np.float32),
                episode["finger"][t].astype(np.float32),
                episode["tactile"][t].astype(np.float32),
            ]
        if self.cmd_channel:
            # the command applied at t-1 (the recorded action stream); at t=0
            # the wait hold, which is what the demos start with.
            action = np.asarray(episode["action"], dtype=np.float32)
            col = 7 if action.ndim == 2 and action.shape[1] > 7 else 3
            command = action[:, col]
            if t is None:
                parts.append(np.concatenate([[command[0]], command[:-1]])[:, None])
            else:
                prev = command[t - 1] if t > 0 else command[0]
                parts.append(np.array([prev], dtype=np.float32))
        if self.speed_channel:
            trace = self.speed_traces[ep_index]
            if trace is not None:
                # P141: the recorded trace. This is the difference between a
                # constant-belt channel and one that can carry a wave - and the
                # deployed loop already reads the encoder per tick, so a pinned
                # constant while the belt moved would be a train/inference
                # mismatch, not a simplification.
                if t is None:
                    parts.append(trace.reshape(-1, 1).astype(np.float32))
                else:
                    parts.append(np.array([trace[t]], dtype=np.float32))
            elif t is None:
                # One constant column for the whole episode (a pre-P141 store:
                # the channel is a per-episode constant, byte-identical to what
                # it always was).
                frames = int(episode["joint"].shape[0])
                parts.append(
                    np.full(
                        (frames, 1), self.belt_speeds[ep_index], dtype=np.float32
                    )
                )
            else:
                parts.append(np.array([self.belt_speeds[ep_index]], dtype=np.float32))
        # axis=-1: one frame -> the shipped 1-D concatenation (a no-op change);
        # all frames -> the pin joins as a column.
        return np.concatenate(parts, axis=-1)

    def goal_at(self, ep_index: int, t: int) -> np.ndarray:
        """The goal vector for one frame - the single assembly site.

        ``[xyz, v(3), diameter, bin_index]``, plus P141's ``(v_belt, a_belt)``
        when the pair is armed. The pair is read from the same per-frame trace
        the 26th proprio column reads, so a store's two channels cannot
        disagree; a pre-P141 store falls back to the constant pin and ``a = 0``.
        """
        episode = self.episodes[ep_index]
        goal = episode["goal"][t].astype(np.float32)
        if not self.goal_aux:
            return goal
        trace = self.speed_traces[ep_index]
        accel = self.belt_accels[ep_index]
        speed = float(self.belt_speeds[ep_index]) if trace is None else float(trace[t])
        a = 0.0 if accel is None else float(accel[t])
        return np.concatenate([goal, np.array([speed, a], dtype=np.float32)])

    def goal_frames(self, ep_index: int) -> np.ndarray:
        """Every frame's goal for one episode, ``(frames, goal_dim)``."""
        if not self.goal_aux:
            return self.episodes[ep_index]["goal"].astype(np.float32)
        frames = int(self.episodes[ep_index]["goal"].shape[0])
        return np.stack([self.goal_at(ep_index, t) for t in range(frames)], axis=0)

    def __getitem__(self, index: int) -> dict:
        ep_index, t = self.windows[index]
        episode = self.episodes[ep_index]

        # Image stack over the observation horizon, oldest first.
        frames = []
        _act = episode["action"] if "action" in episode else None
        for k in range(self.obs_horizon - 1, -1, -1):
            idx = max(0, t - k)
            _crop_now = self.fovea > 0
            if _crop_now and self.fovea_phase and _act is not None:
                # pre-close = the label's finger open: the approach and the contact
                # need the fruit (1-4 px wide otherwise); the carry and the place
                # need the bins.
                try:
                    _crop_now = float(np.asarray(_act)[idx][7]) > 0.035
                except Exception:  # noqa: BLE001 - no label, keep the shipped crop
                    _crop_now = True
            if _crop_now:
                _pos = episode.get("fruit_position")
                _uv = None
                if _pos is not None:
                    _uv = project(
                        _pos[idx],
                        eye=self._cam_eye,
                        target=self._cam_target,
                        width=episode["rgb"].shape[2],
                        height=episode["rgb"].shape[1],
                    )
                _size_px = self.fovea
                if self.aug > 0.0:
                    _rng = np.random.default_rng()
                    _size_px = int(max(16, round(self.fovea * (1.0 + _rng.uniform(-self.aug, self.aug)))))
                    if _uv is not None:
                        _jit = self.aug * self.fovea * 0.25
                        _uv = (
                            _uv[0] + float(_rng.uniform(-_jit, _jit)),
                            _uv[1] + float(_rng.uniform(-_jit, _jit)),
                        )
                _win = foveal_window(
                    _uv, episode["rgb"].shape[2], episode["rgb"].shape[1], _size_px
                )
                _size = self.image_size
                rgb = crop_and_resize(episode["rgb"][idx], _win, _size).astype(np.float32) / 255.0
                depth = crop_and_resize(episode["depth"][idx][..., 0], _win, _size).astype(np.float32)
                depth = np.clip(depth, 0.0, 3.0) / 3.0
                _ch = [rgb, depth[..., None]]
                if episode["mask"] is not None:
                    _m = crop_and_resize(episode["mask"][idx], _win, _size).astype(np.float32)
                    _ch.append(_m[..., None])
                frames.append(np.concatenate(_ch, axis=-1))
                continue
            rgb = self._downsample(episode["rgb"][t - k]).astype(np.float32) / 255.0
            _d = episode["depth"][t - k][..., 0]
            if self.fovea_phase:
                # The wide frame's depth carries `inf` where the raycast missed
                # (26 % of the pixels in `p169_demo_all`). The crop path clips
                # *after* resampling, which turns inf into 3.0; the wide path
                # resamples first, and `inf - inf` is NaN - measured, that NaN
                # reached the encoder. Sanitise before the resample, and only on
                # this path: the shipped wide path must stay byte-identical for
                # the models trained on it.
                _d = np.nan_to_num(np.asarray(_d, dtype=np.float32),
                                   nan=0.0, posinf=3.0, neginf=0.0)
            depth = self._downsample(_d).astype(np.float32)
            # Depth is metres; clip and normalise into a sane range for the CNN.
            depth = np.clip(depth, 0.0, 3.0) / 3.0
            channels = [rgb, depth[..., None]]
            if episode["mask"] is not None:
                # Target mask channel isolates the fruit the slow loop selected.
                mask = self._downsample(episode["mask"][t - k]).astype(np.float32)
                channels.append(mask[..., None])
            frames.append(np.concatenate(channels, axis=-1))
        image = np.stack(frames, axis=0)  # (obs_horizon, H, W, C)
        image = np.transpose(image, (0, 3, 1, 2))  # (obs_horizon, C, H, W)

        proprio = self.proprio(ep_index, t)
        goal = self.goal_at(ep_index, t)
        action = episode["action"][t : t + self.action_horizon].astype(np.float32)
        if self.action_mode == "dq":
            # the per-step joint delta (the first frame has no predecessor)
            full = np.asarray(episode["action"], dtype=np.float32)
            delta = np.zeros_like(full)
            delta[1:, :7] = full[1:, :7] - full[:-1, :7]
            action = delta[t : t + self.action_horizon].copy()
            action[:, 7:] = full[t : t + self.action_horizon, 7:]
        elif self.action_mode == "posvel":
            # P157: [pos(7), finger, finger, delta(7)] - the joint position the
            # demos command **plus their own per-frame velocity**. The position
            # half keeps the approach; the delta half is a *supervised* velocity
            # the env can lead with (the contact phase's hold is a velocity task,
            # and a position action under-executes it at 35-42 %; a feed-forward
            # of the position's own velocity is a null because the position's
            # velocity is already ~0).
            _pos = action[:, :7].copy()
            _fing = action[:, 7:8].copy()
            _delta = np.zeros_like(_pos)
            _delta[:-1] = _pos[1:] - _pos[:-1]
            action = np.concatenate([_pos, _fing, _fing, _delta], axis=1).astype(np.float32)
        elif self.action_mode == "rel":
            # the chunk-relative form: offsets from the window's own first frame
            action = action.copy()
            action[:, :7] = action[:, :7] - action[:1, :7]
        skills = episode["skills"]
        skill = int(skills[t]) if skills is not None else 0
        return {
            "image": image,
            "proprio": proprio,
            "goal": goal,
            "action": action,
            "skill": np.int64(skill),
        }

    # ------------------------------------------------------------------ #
    def compute_normalizer(self) -> Normalizer:
        actions, obs, goals = [], [], []
        for ep_index, episode in enumerate(self.episodes):
            full = np.asarray(episode["action"], dtype=np.float32)
            if self.action_mode == "posvel":
                H = self.action_horizon
                chunks = []
                for t0 in range(0, max(1, len(full) - H), 4):
                    win = full[t0 : t0 + H].copy()
                    _pos = win[:, :7].copy()
                    _fing = win[:, 7:8].copy()
                    _delta = np.zeros_like(_pos)
                    _delta[:-1] = _pos[1:] - _pos[:-1]
                    chunks.append(
                        np.concatenate([_pos, _fing, _fing, _delta], axis=1)
                    )
                actions.append(np.concatenate(chunks, axis=0) if chunks else np.zeros((1, 16), np.float32))
                continue
            if self.action_mode == "rel":
                # per-window relative offsets, sampled every 4 frames
                H = self.action_horizon
                rel = []
                for t0 in range(0, max(1, len(full) - H), 4):
                    win = full[t0 : t0 + H].copy()
                    win[:, :7] = win[:, :7] - win[:1, :7]
                    rel.append(win)
                actions.append(np.concatenate(rel, axis=0) if rel else full)
                continue
            if self.action_mode == "dq":
                delta = np.zeros_like(full)
                delta[1:, :7] = full[1:, :7] - full[:-1, :7]
                delta[:, 7:] = full[:, 7:]
                actions.append(delta)
            else:
                actions.append(full)
            obs.append(self.proprio(ep_index))
            goals.append(self.goal_frames(ep_index))
        actions = np.concatenate(actions, axis=0)
        obs = np.concatenate(obs, axis=0)
        goals = np.concatenate(goals, axis=0)
        obs_mean = obs.mean(0).astype(np.float32)
        obs_std = (obs.std(0) + 1e-6).astype(np.float32)
        goal_mean = goals.mean(0).astype(np.float32)
        goal_std = (goals.std(0) + 1e-6).astype(np.float32)
        if self.speed_channel:
            # P28-B, design C2: the channel's units are FIXED, not a store
            # statistic. A fine-tune inherits the checkpoint's normaliser
            # verbatim (it is never recomputed), so a value derived here would
            # silently redefine the channel for every later checkpoint.
            obs_mean[-1] = SPEED_CHANNEL_MEAN
            obs_std[-1] = SPEED_CHANNEL_STD
        if self.goal_aux:
            # Same rule for the goal pair: a constant belt gives ``a = 0`` for
            # every training frame, so a store statistic would divide by ~0.
            goal_mean[-2:] = GOAL_AUX_MEAN
            goal_std[-2:] = GOAL_AUX_STD
        return Normalizer(
            action_mean=actions.mean(0).astype(np.float32),
            action_std=(actions.std(0) + 1e-6).astype(np.float32),
            obs_mean=obs_mean,
            obs_std=obs_std,
            goal_mean=goal_mean,
            goal_std=goal_std,
        )

    def skill_histogram(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        from .skills import SKILLS

        for episode in self.episodes:
            if episode["skills"] is None:
                continue
            for value in np.unique(episode["skills"]):
                name = SKILLS[int(value)]
                counts[name] = counts.get(name, 0) + int((episode["skills"] == value).sum())
        return counts

    def summary(self) -> str:
        categories: dict[str, int] = {}
        arms: dict[str, int] = {}
        for episode in self.episodes:
            categories[episode["meta"]["category"]] = (
                categories.get(episode["meta"]["category"], 0) + 1
            )
            arms[episode["meta"]["arm"]] = arms.get(episode["meta"]["arm"], 0) + 1
        traced = sum(1 for trace in self.speed_traces if trace is not None)
        return (
            f"{len(self.episodes)} episodes, {len(self.windows)} windows; "
            f"categories={categories}; arms={arms}; "
            f"proprio_dim={self.proprio_dim} goal_dim={self.goal_dim} "
            f"speed_trace={traced}/{len(self.episodes)}"
        )
