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
    FRUIT_POLICY_TRIGGER_LATERAL  max |dx| (cross-belt) at fire time [m] (0.16)
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

The adaptive acquisition lead (**W7-B**, default **off**):

    FRUIT_POLICY_TRIGGER_ACQ      1 = fire earlier when the jaw is farther
                                from the station: the scripted handover's
                                setup (wrist attitude + park at the grip) has
                                to finish before the fruit arrives, and the
                                W7-B mechanism run measured that setup at
                                1.4-4.1 s on the left's no-contact failures
                                against a 0.9 s fixed lead (`logs/w7/B_*`).
                                With the knob on, the effective lead is
                                `lead + margin + |jaw - station| / speed`
                                and the reach gate is raised with it (or the
                                earlier fire would be refused for a fruit
                                still upstream). Only the direct policy path
                                uses this module.
    FRUIT_POLICY_TRIGGER_ACQ_SPEED  jaw->station approach speed [m/s] (0.20)
    FRUIT_POLICY_TRIGGER_ACQ_MARGIN constant setup overhead [s] (0.60)
    FRUIT_POLICY_TRIGGER_ACQ_CAP   cap on the effective lead [s] (4.5)
    FRUIT_POLICY_TRIGGER_ACQ_REACH extra reach margin [m] (0.05)

The lateral default is **0.16 m** (W4, 2026-10-10): the pre-v9 fixed supply
kept fruit within ~5 mm of the belt centre, where 0.06 was calibrated, but the
shipped v9/V1 scattered/dense band is x = 0.20-0.36 m against the grasp-pose
jaw at x ~ 0.30-0.34 m, so the old gate refused the outer half of the band and
the direct interface stalled in a no-fire class (`moe_v13s` dense, N=3x15:
0.06 -> 7/45 with 21/45 no-fire, 0.16 -> 19/45 with 1/45 no-fire,
`logs/w4/table_2x2.txt`). 0.16 also stays inside the measured top-down station
reach band (x = 0.18-0.39, `scripts/174_station_reach.py`); pin `=0.06` to
reproduce the pre-W4 gate (the P2b-era direct logs were recorded with it).

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
    #: W4: the v9/V1 scattered/dense supply band (x = 0.20-0.36 m) sits up to
    #: ~0.14 m off the grasp-pose jaw line; 0.06 refused its outer half (see
    #: the module docstring). Pin 0.06 via env to reproduce the pre-W4 gate.
    lateral: float = 0.16
    reach: float = 0.20
    finger: float = 0.040
    use_encoder: bool = True
    frame: str = "station"
    #: Also fire on a firable fruit the feeder is presenting at the station
    #: when it differs from the selected sample (P4b2). Default off.
    present: bool = False
    #: W7-B adaptive acquisition lead (default off): extend the lead by the
    #: jaw->station distance over `acq_speed` (+ `acq_margin`), so the
    #: scripted handover's setup finishes before the fruit arrives; the reach
    #: gate is raised with the lead. Off = the settings' own lead/reach.
    acq: bool = False
    acq_speed: float = 0.20
    acq_margin: float = 0.60
    acq_cap: float = 4.50
    acq_reach_margin: float = 0.05

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
            lateral=float(os.environ.get("FRUIT_POLICY_TRIGGER_LATERAL", "0.16")),
            reach=float(os.environ.get("FRUIT_POLICY_TRIGGER_REACH", "0.20")),
            finger=float(os.environ.get("FRUIT_POLICY_TRIGGER_FINGER", "0.040")),
            use_encoder=os.environ.get("FRUIT_POLICY_TRIGGER_ENCODER", "1") != "0",
            frame=frame,
            present=os.environ.get("FRUIT_POLICY_TRIGGER_PRESENT", "0").strip() == "1",
            acq=os.environ.get("FRUIT_POLICY_TRIGGER_ACQ", "0").strip() == "1",
            acq_speed=float(os.environ.get("FRUIT_POLICY_TRIGGER_ACQ_SPEED", "0.20")),
            acq_margin=float(os.environ.get("FRUIT_POLICY_TRIGGER_ACQ_MARGIN", "0.60")),
            acq_cap=float(os.environ.get("FRUIT_POLICY_TRIGGER_ACQ_CAP", "4.50")),
            acq_reach_margin=float(
                os.environ.get("FRUIT_POLICY_TRIGGER_ACQ_REACH", "0.05")
            ),
        )

    @property
    def enabled(self) -> bool:
        return self.mode != "off"

    def summary(self) -> str:
        text = (
            f"trigger={self.mode} lead={self.lead:.2f}s lateral={self.lateral:.3f} "
            f"reach={self.reach:.2f} finger={self.finger:.3f} frame={self.frame} "
            f"encoder={'on' if self.use_encoder else 'off'} "
            f"present={'on' if self.present else 'off'}"
        )
        if self.acq:
            text += (
                f" acq=on(speed={self.acq_speed:.2f},margin={self.acq_margin:.2f},"
                f"cap={self.acq_cap:.2f},reach_margin={self.acq_reach_margin:.2f})"
            )
        return text


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


def acquisition_window(
    settings: TriggerSettings,
    jaw_pos: np.ndarray | None,
    station: np.ndarray | None,
    speed: float,
) -> tuple[float, float]:
    """`(lead, reach)` for this tick, with the adaptive acquisition term (W7-B).

    Off by default: returns the settings' own `lead`/`reach` so the shipped
    behaviour is unchanged. With `FRUIT_POLICY_TRIGGER_ACQ=1` the lead is
    extended by the jaw->station distance over `acq_speed` plus `acq_margin`
    (capped at `acq_cap`), and the reach gate is raised with it - the fire has
    to be *earlier* than the fixed lead, so the fruit is still farther
    upstream than `reach` admits. Both inputs are measured at the tick of the
    decision; no state is carried between ticks.
    """
    if not settings.acq or jaw_pos is None or station is None:
        return settings.lead, settings.reach
    jaw_pos = np.asarray(jaw_pos, dtype=float)
    station = np.asarray(station, dtype=float)
    distance = float(np.linalg.norm(jaw_pos[:2] - station[:2]))
    lead = settings.lead + settings.acq_margin + distance / max(settings.acq_speed, 1e-6)
    lead = min(lead, max(settings.acq_cap, settings.lead))
    reach = settings.reach
    if math.isfinite(speed) and speed > 1e-3:
        reach = max(reach, speed * lead + settings.acq_reach_margin)
    return lead, reach


def should_fire(
    settings: TriggerSettings,
    fruit: np.ndarray,
    jaw: np.ndarray,
    *,
    encoder_speed: float | None = None,
    measured_velocity: np.ndarray | None = None,
    finger: float | None = None,
    jaw_pos: np.ndarray | None = None,
    station: np.ndarray | None = None,
) -> tuple[bool, dict]:
    """Whether the intercept trigger fires now, plus the numbers behind it.

    ``jaw`` is the reference point the arrival time is measured against - the
    nominal station or the current measured jaw, chosen by the env from
    ``settings.frame``. Fires when the fruit is upstream (or barely past),
    laterally aligned with that reference, inside the reach window, and
    predicted to reach its y line within ``lead`` seconds. ``assist``
    additionally needs the policy's finger command below ``settings.finger`` at
    this tick.

    ``jaw_pos``/``station`` are the measured jaw and the captured station
    (W7-B, optional): with `FRUIT_POLICY_TRIGGER_ACQ` on they widen the
    effective lead/reach through `acquisition_window`.
    """
    fruit = np.asarray(fruit, dtype=float)
    jaw = np.asarray(jaw, dtype=float)
    dx = float(fruit[0] - jaw[0])
    dy = float(fruit[1] - jaw[1])
    speed, source = transport_speed(
        fruit, jaw, encoder_speed=encoder_speed,
        measured_velocity=measured_velocity, use_encoder=settings.use_encoder,
    )
    lead, reach = acquisition_window(settings, jaw_pos, station, speed)
    info = {
        "dx": dx,
        "dy": dy,
        "speed": speed,
        "source": source,
        "t_arrive": float("nan"),
        "finger": float("nan") if finger is None else float(finger),
        "lead": lead,
        "reach": reach,
    }
    if not settings.enabled:
        return False, info
    if abs(dx) > settings.lateral:
        return False, info
    if dy > reach or dy < -0.05:
        return False, info
    if speed <= 1e-3:
        # No transport: only an already-arrived fruit qualifies (the policy
        # gate owns the stationary case).
        return False, info
    t_arrive = max(dy, 0.0) / speed
    info["t_arrive"] = t_arrive
    if t_arrive > lead:
        return False, info
    if settings.mode == "assist":
        if finger is None or float(finger) >= settings.finger:
            return False, info
    return True, info
