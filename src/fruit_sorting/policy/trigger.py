"""Encoder-based intercept trigger for the direct policy loop (P4b1, default off).

The direct presentation's causal interface triggers the scripted contact
primitive when the *policy* commands ``finger < 0.030`` while the jaw is within
0.06 m of the fruit. With the visible-jaw policy (`moe_v10`) that gate is
marginal: the 10/45 episodes that closed did so at ``|jaw-fruit|xy =
5.9-6.0 cm`` - exactly on the gate - and the other 35 never fired at all
(`logs/798_direct_moe_v10.log`). The belt encoder makes the arrival time of the
fruit at the jaw's close zone an exact, cheap quantity, so this module computes
it and fires the primitive at a settable lead instead of waiting for the
learned finger crossing.

This is inference-time only and *off by default*: with ``FRUIT_POLICY_TRIGGER``
unset the env's trigger code is the shipped ``finger < 0.030 and distance <
0.06`` test, byte for byte.

    FRUIT_POLICY_TRIGGER        off | arrival | assist   (default off)
    FRUIT_POLICY_TRIGGER_LEAD   predicted seconds to the jaw line at fire time
                                (default 0.90 s: the 10 closed episodes of
                                `logs/798` fired at 5.9-6.0 cm at 0.06 m/s)
    FRUIT_POLICY_TRIGGER_LATERAL  max |dx| (cross-belt) at fire time [m] (0.06)
    FRUIT_POLICY_TRIGGER_REACH  max upstream distance the trigger considers [m]
                                (0.20)
    FRUIT_POLICY_TRIGGER_FINGER `assist` mode: the policy finger must be below
                                this value at fire time (0.040)
    FRUIT_POLICY_TRIGGER_ENCODER 1 = use the belt encoder's speed; 0 = the
                                fruit's measured velocity (default 1)
    FRUIT_POLICY_TRIGGER_FRAME  station = time the arrival at the nominal pick
                                station captured at reset (robust to the
                                policy's own arm drift); jaw = the current
                                measured jaw (default station)
    FRUIT_POLICY_TRIGGER_PRESENT 1 = also consider the fruit the feeder is
                                presenting at the station (`station_sample`)
                                when the selected upstream sample is not
                                firable: if the presented fruit is firable and
                                differs, the env adopts it (the same fruit the
                                scripted primitive's station re-select would
                                grasp) and fires. Default 0.

``arrival`` fires from the schedule alone; ``assist`` additionally requires the
policy to be *near* closing so the learned approach stays causally necessary.
Both are recorded in the run manifest and add a note with the numbers.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np

TRIGGER_MODES = ("off", "arrival", "assist")
#: Reference point the arrival is measured against: the nominal pick station
#: captured at reset (`station`, robust to the policy's own arm drift) or the
#: current measured jaw (`jaw`).
TRIGGER_FRAMES = ("station", "jaw")


@dataclass
class TriggerSettings:
    """Environment-driven intercept-trigger configuration. Disabled by default."""

    mode: str = "off"
    lead: float = 0.90
    lateral: float = 0.06
    reach: float = 0.20
    finger: float = 0.040
    use_encoder: bool = True
    frame: str = "station"
    #: Also fire on a firable fruit the feeder is presenting at the station
    #: when it differs from the selected sample (P4b2). Default off.
    present: bool = False

    @classmethod
    def from_env(cls) -> "TriggerSettings":
        mode = os.environ.get("FRUIT_POLICY_TRIGGER", "off").strip().lower() or "off"
        if mode not in TRIGGER_MODES:
            raise ValueError(
                f"FRUIT_POLICY_TRIGGER must be one of {TRIGGER_MODES}, got {mode!r}"
            )
        frame = os.environ.get("FRUIT_POLICY_TRIGGER_FRAME", "station").strip().lower()
        if frame not in TRIGGER_FRAMES:
            raise ValueError(
                f"FRUIT_POLICY_TRIGGER_FRAME must be one of {TRIGGER_FRAMES}, "
                f"got {frame!r}"
            )
        return cls(
            mode=mode,
            lead=float(os.environ.get("FRUIT_POLICY_TRIGGER_LEAD", "0.90")),
            lateral=float(os.environ.get("FRUIT_POLICY_TRIGGER_LATERAL", "0.06")),
            reach=float(os.environ.get("FRUIT_POLICY_TRIGGER_REACH", "0.20")),
            finger=float(os.environ.get("FRUIT_POLICY_TRIGGER_FINGER", "0.040")),
            use_encoder=os.environ.get("FRUIT_POLICY_TRIGGER_ENCODER", "1") != "0",
            frame=frame,
            present=os.environ.get("FRUIT_POLICY_TRIGGER_PRESENT", "0").strip() == "1",
        )

    @property
    def enabled(self) -> bool:
        return self.mode != "off"

    def summary(self) -> str:
        return (
            f"trigger={self.mode} lead={self.lead:.2f}s lateral={self.lateral:.3f} "
            f"reach={self.reach:.2f} finger={self.finger:.3f} frame={self.frame} "
            f"encoder={'on' if self.use_encoder else 'off'} "
            f"present={'on' if self.present else 'off'}"
        )


def transport_speed(
    fruit: np.ndarray,
    jaw: np.ndarray,
    *,
    encoder_speed: float | None = None,
    measured_velocity: np.ndarray | None = None,
    use_encoder: bool = True,
) -> tuple[float, str]:
    """Signed approach speed of the fruit toward the jaw line [m/s].

    ``dy = fruit_y - jaw_y``; the fruit approaches when ``dy > 0`` and its
    velocity along -y is positive. The belt encoder is the exact transport
    speed (the fruit rides at 1.01-1.14x, `logs/173`); the measured rigid-body
    velocity can read low when the fruit rolls on the belt (a demo's stored vy
    was -0.0225 against the belt's -0.06). Prefer the encoder when it is
    finite and non-zero, otherwise fall back to the measurement.
    """
    fallback = 0.0
    if measured_velocity is not None:
        fallback = max(-float(np.asarray(measured_velocity, dtype=float)[1]), 0.0)
    if use_encoder and encoder_speed is not None:
        speed = float(encoder_speed)
        if math.isfinite(speed) and abs(speed) > 1e-6:
            return max(-speed, 0.0), "encoder"
    return fallback, "measured"


def should_fire(
    settings: TriggerSettings,
    fruit: np.ndarray,
    jaw: np.ndarray,
    *,
    encoder_speed: float | None = None,
    measured_velocity: np.ndarray | None = None,
    finger: float | None = None,
) -> tuple[bool, dict]:
    """Whether the intercept trigger fires now, plus the numbers behind it.

    ``jaw`` is the reference point the arrival time is measured against - the
    nominal station or the current measured jaw, chosen by the env from
    ``settings.frame``. Fires when the fruit is upstream (or barely past),
    laterally aligned with that reference, inside the reach window, and
    predicted to reach its y line within ``lead`` seconds. ``assist``
    additionally needs the policy's finger command below ``settings.finger`` at
    this tick.
    """
    fruit = np.asarray(fruit, dtype=float)
    jaw = np.asarray(jaw, dtype=float)
    dx = float(fruit[0] - jaw[0])
    dy = float(fruit[1] - jaw[1])
    speed, source = transport_speed(
        fruit, jaw, encoder_speed=encoder_speed,
        measured_velocity=measured_velocity, use_encoder=settings.use_encoder,
    )
    info = {
        "dx": dx,
        "dy": dy,
        "speed": speed,
        "source": source,
        "t_arrive": float("nan"),
        "finger": float("nan") if finger is None else float(finger),
    }
    if not settings.enabled:
        return False, info
    if abs(dx) > settings.lateral:
        return False, info
    if dy > settings.reach or dy < -0.05:
        return False, info
    if speed <= 1e-3:
        # No transport: only an already-arrived fruit qualifies (the policy
        # gate owns the stationary case).
        return False, info
    t_arrive = max(dy, 0.0) / speed
    info["t_arrive"] = t_arrive
    if t_arrive > settings.lead:
        return False, info
    if settings.mode == "assist":
        if finger is None or float(finger) >= settings.finger:
            return False, info
    return True, info
