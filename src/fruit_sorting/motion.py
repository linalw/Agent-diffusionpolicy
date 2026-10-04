"""Trajectory shaping: bounded-jerk references and a friction-cone acceleration budget.

The pipeline used to move the gripper with piecewise-linear interpolation
(`centre = start + (finish - start) * i / steps`). That reference has a step in
velocity at both ends of every segment, i.e. an unbounded acceleration demand,
which a real mechanism cannot follow and which looks - and is - jerky.

Two classical ideas are applied here:

1. **Jerk-limited (S-curve) time parameterisation.**  The reference is generated
   by integrating a bounded acceleration command through a jerk limiter, so
   ``|v| <= v_max``, ``|a| <= a_max`` and ``|j| <= j_max`` hold by construction
   (Biagiotti & Melchiorri, *Trajectory Planning for Automatic Machines and
   Robots*, ch. 3).  This is what industrial motion controllers emit.

2. **Friction-cone acceleration budget while a payload is held.**  The fruit is
   carried by pad friction only, so the inertial load must stay inside the
   friction cone: with a worst-case normal force ``N = m g`` (ignoring any
   squeeze margin) the transport is non-slipping iff

       |a + g z| <= mu_s * g        (z = world up)

   For a move along unit direction ``u`` this bounds the achievable acceleration
   to ``a_max(u) = g (sqrt(u_z^2 + mu_eff^2 - 1) - u_z)`` with
   ``mu_eff = FRUIT_MU_SAFETY * mu``.  Grasp-stability condition from Murray,
   Li & Sastry, *A Mathematical Introduction to Robotic Manipulation*, ch. 5;
   the same budget appears in modern dynamic-grasping work.

Quintic (minimum-jerk) blends are also provided for the jaws, whose opening is a
degree of freedom of its own and should be C2 as well (Flash & Hogan 1985).

The module deliberately imports nothing from Isaac Sim so it can be unit tested
with any Python: see ``scripts/96_motion_check.py``.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np

STANDARD_GRAVITY = 9.81


def top_down_quaternion(closing_axis: str = "y") -> np.ndarray:
    """Tool quaternion whose fingers point straight down (w, x, y, z).

    The gripper places its pads from the tool rotation: column 1 is the closing
    axis and column 2 the direction the fingers extend. A fruit on a belt wants
    column 2 = (0, 0, -1) so the fingers hang vertically and the jaws close
    horizontally. Measured with `scripts/97_reach_probe.py`: at the pick station
    both arms reach that attitude with a straight-down tool axis (2.1 mm residual)
    either way, provided each arm is given the *mirrored* attitude of the other
    (`mirror_across_xz`) - feeding both the same quaternion made the left arm's
    solver drift into a near-horizontal tool. The function is pure numpy so it can
    be unit tested.
    """
    if closing_axis == "x":
        rot = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])
    else:
        rot = np.array([[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]])
    m = rot
    if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        w, x, y, z = (m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        w, x, y, z = (m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        w, x, y, z = (m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s
    return np.array([w, x, y, z])


def mirror_across_xz(q) -> np.ndarray:
    """Mirror a tool quaternion across the robot's symmetry plane (x-z, y -> -y).

    The two OpenArm arms are mirror images, so a left-arm grasp attitude is the
    right arm's reflected through the plane y = 0. Pure numpy (unit tested).
    """
    w, x, y, z = (float(v) for v in q)
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return _mirror_quat(w, x, y, z)


def _mirror_quat(w: float, x: float, y: float, z: float) -> np.ndarray:
    """M R M with M = diag(1, -1, 1), done in matrix space then back to a quaternion."""
    r = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )
    m = np.diag([1.0, -1.0, 1.0])
    r = m @ r @ m
    trace = float(np.trace(r))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        out = [0.25 * s, (r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s]
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = math.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2.0
        out = [(r[2, 1] - r[1, 2]) / s, 0.25 * s, (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s]
    elif r[1, 1] > r[2, 2]:
        s = math.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2.0
        out = [(r[0, 2] - r[2, 0]) / s, (r[0, 1] + r[1, 0]) / s, 0.25 * s, (r[1, 2] + r[2, 1]) / s]
    else:
        s = math.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2.0
        out = [(r[1, 0] - r[0, 1]) / s, (r[0, 2] + r[2, 0]) / s, (r[1, 2] + r[2, 1]) / s, 0.25 * s]
    out = np.asarray(out, dtype=float)
    return out / np.linalg.norm(out)


def min_jerk_ramp(start: float, end: float, steps: int) -> np.ndarray:
    """Quintic blend from `start` to `end` with zero velocity and acceleration at both ends."""
    steps = max(int(steps), 1)
    u = np.linspace(0.0, 1.0, steps + 1)[1:]
    s = 10.0 * u**3 - 15.0 * u**4 + 6.0 * u**5
    return float(start) + (float(end) - float(start)) * s


def accel_budget(direction, mu_eff: float, g: float = STANDARD_GRAVITY) -> float:
    """Largest acceleration along `direction` that keeps the load inside the cone.

    `direction` need not be normalised. Returns a non-negative scalar [m/s^2].
    """
    u = np.asarray(direction, dtype=float)
    norm = float(np.linalg.norm(u))
    if norm < 1e-12:
        return 0.0
    u = u / norm
    if mu_eff <= 1.0:
        # A cone this tight cannot even hold the payload against gravity unless
        # the acceleration points with gravity; allow the free-fall side only.
        return max(0.0, -u[2] * g)
    root = math.sqrt(max(u[2] ** 2 + mu_eff**2 - 1.0, 0.0))
    return max(0.0, g * (root - u[2]))


def cone_scale(accel, mu_eff: float, g: float = STANDARD_GRAVITY) -> float:
    """Largest s in [0, 1] with |s * accel + g z| <= mu_eff * g."""
    a = np.asarray(accel, dtype=float)
    q = float(a @ a)
    if q < 1e-12:
        return 1.0
    b = 2.0 * float(a[2]) * g
    c = g * g * (1.0 - mu_eff * mu_eff)
    disc = b * b - 4.0 * q * c
    if disc < 0.0:
        return 0.0
    s = (-b + math.sqrt(disc)) / (2.0 * q)
    return float(min(max(s, 0.0), 1.0))


@dataclass
class TrajectoryLimits:
    """Kinematic envelope for one point-to-point move."""

    v_max: float = 0.30   # [m/s]
    a_max: float = 2.00   # [m/s^2]
    j_max: float = 25.0   # [m/s^3]
    dt: float = 1.0 / 120.0

    @classmethod
    def from_env(cls, dt: float = 1.0 / 120.0) -> "TrajectoryLimits":
        return cls(
            # A minimum-jerk profile cruises at only 60 % of its peak speed
            # (max s' = 1.875 over an average of 1), so 0.38 m/s peak reproduces
            # the ~0.23 m/s average of the old constant-velocity transfer legs
            # without their velocity steps.
            v_max=float(os.environ.get("FRUIT_CARRY_VMAX", "0.38")),
            a_max=float(os.environ.get("FRUIT_CARRY_AMAX", "2.0")),
            j_max=float(os.environ.get("FRUIT_CARRY_JMAX", "25.0")),
            dt=dt,
        )

    def limited_by_cone(self, direction, mu_eff: float) -> "TrajectoryLimits":
        budget = accel_budget(direction, mu_eff)
        if budget <= 0.0:
            return self
        a_max = min(self.a_max, budget)
        # Keep the ramp gentle too: a jerk budget proportional to the
        # acceleration gives a roughly fixed-duration blend.
        j_max = min(self.j_max, max(a_max * 10.0, 1.0))
        v_max = min(self.v_max, 2.0 * a_max)
        return TrajectoryLimits(v_max=v_max, a_max=a_max, j_max=j_max, dt=self.dt)


def jerk_limited(
    distance: float,
    limits: TrajectoryLimits,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Jerk-limited 1-D profile covering `distance` metres in one direction.

    Returns ``(positions, velocities, accelerations)`` sampled at ``limits.dt``,
    starting and ending at rest. The profile always reaches `distance` exactly
    (the final sample is pinned), and respects all three bounds by construction.

    Construction: the minimum-jerk quintic ``s(u) = 10u^3 - 15u^4 + 6u^5`` has
    ``max|s'| = 1.875``, ``max|s''| = 5.774`` and ``max|s'''| = 60``, so scaling
    it to cover `distance` in time ``T`` gives

        |v| <= 1.875 d/T,   |a| <= 5.774 d/T^2,   |j| <= 60 d/T^3.

    Choosing ``T`` as the largest of the three limits' implied durations (with a
    2 % margin, and rounded up to a whole number of control ticks) therefore
    satisfies every bound while keeping the reference C2 and exactly on target -
    a jerk-limited, time-scaled minimum-jerk profile.
    """
    d = float(distance)
    dt = float(limits.dt)
    if abs(d) < 1e-9 or dt <= 0.0:
        zeros = np.zeros(1)
        return zeros, zeros.copy(), zeros.copy()

    target = abs(d)
    v_max = max(float(limits.v_max), 1e-3)
    a_max = max(float(limits.a_max), 1e-3)
    j_max = max(float(limits.j_max), 1e-3)

    duration = max(
        1.875 * target / v_max,
        math.sqrt(5.774 * target / a_max),
        (60.0 * target / j_max) ** (1.0 / 3.0),
    )
    duration *= 1.02
    steps = max(int(math.ceil(duration / dt)), 2)
    span = steps * dt

    u = np.linspace(0.0, 1.0, steps + 1)
    shape = 10.0 * u**3 - 15.0 * u**4 + 6.0 * u**5
    shape_v = (30.0 * u**2 - 60.0 * u**3 + 30.0 * u**4) / span
    shape_a = (60.0 * u - 180.0 * u**2 + 120.0 * u**3) / (span * span)

    sign = 1.0 if d > 0 else -1.0
    pos = sign * target * shape
    vel = sign * target * shape_v
    acc = sign * target * shape_a
    return pos, vel, acc


class MotionMonitor:
    """Accumulates a trajectory and reports the smoothness/realism metrics."""

    def __init__(self, label: str = "", mu_eff: float | None = None,
                 g: float = STANDARD_GRAVITY):
        self.label = label
        self.mu_eff = mu_eff
        self.g = g
        self.times: list[float] = []
        self.points: list[np.ndarray] = []
        self.payloads: list[np.ndarray] = []

    def add(self, t: float, point, payload=None) -> None:
        self.times.append(float(t))
        self.points.append(np.asarray(point, dtype=float))
        if payload is not None:
            self.payloads.append(np.asarray(payload, dtype=float))

    def _derivatives(self, samples: np.ndarray, times: np.ndarray):
        if len(samples) < 3:
            empty = np.zeros(0)
            return empty, empty, empty
        dt = np.diff(times)
        dt[dt <= 0.0] = 1e-3
        vel = np.diff(samples, axis=0) / dt[:, None]
        acc = np.diff(vel, axis=0) / dt[1:, None]
        jerk = np.diff(acc, axis=0) / dt[2:, None]
        return vel, acc, jerk

    def summary(self) -> dict:
        times = np.asarray(self.times, dtype=float)
        samples = np.asarray(self.points, dtype=float)
        out: dict[str, float] = {"label": self.label, "steps": float(len(samples))}
        if len(samples) < 3:
            return out
        vel, acc, jerk = self._derivatives(samples, times)
        out["v_max"] = float(np.linalg.norm(vel, axis=1).max())
        out["a_max"] = float(np.linalg.norm(acc, axis=1).max())
        out["j_max"] = float(np.linalg.norm(jerk, axis=1).max())
        # Where the peak sits matters as much as its value. A leg whose only
        # large sample is the first or last one is not a rough leg; it is a leg
        # with a start/stop transient, and the two need completely different
        # fixes. `a_med` is the honest "how rough is the body of the motion".
        magnitude = np.linalg.norm(acc, axis=1)
        out["a_med"] = float(np.median(magnitude))
        out["a_peak_at"] = float(int(np.argmax(magnitude)) + 1) / float(len(magnitude))
        window = max(1, len(magnitude) // 10)
        out["a_first10"] = float(magnitude[:window].max())
        out["a_last10"] = float(magnitude[-window:].max())
        # `|a|max` differences two consecutive 1/120 s samples, so on a leg whose
        # steps are tenths of a millimetre it mostly measures jitter: a 1 mm/tick
        # wobble at 0.06 m/s reads as 14 m/s^2. `a_win` smooths over `A_WINDOW`
        # control ticks, which is the timescale a contact actually transmits force
        # over, and is the number to quote for a slow leg.
        A_WINDOW = 5
        span = min(A_WINDOW, len(vel))
        if span >= 2:
            spacing = float(np.median(np.diff(times))) if len(times) > 1 else 1.0 / 120.0
            span_time = max(spacing * (span - 1), 1e-6)
            smoothed = (vel[span - 1:] - vel[: len(vel) - span + 1]) / span_time
            out["a_win"] = float(np.linalg.norm(smoothed, axis=1).max())
        # The velocity *step* at the two ends is what a payload has to absorb in a
        # single control tick: a constant-velocity ramp starts and stops at the
        # cruise speed, a jerk-limited profile starts and stops at (almost) zero.
        dt0 = float(times[1] - times[0]) or 1e-3
        out["v_start"] = float(np.linalg.norm(vel[0]))
        out["v_end"] = float(np.linalg.norm(vel[-1]))
        out["a_step"] = max(out["v_start"], out["v_end"]) / dt0
        if self.mu_eff is not None and len(acc):
            load = acc + np.array([0.0, 0.0, self.g])
            need = np.linalg.norm(load, axis=1) / (self.mu_eff * self.g)
            out["cone_max"] = float(need.max())
            out["cone_over"] = float((need > 1.0).mean())
            out["cone_over_steps"] = float((need > 1.0).sum())
        if len(self.payloads) >= 2:
            payload = np.asarray(self.payloads, dtype=float)
            # Drift of the fruit relative to the pads: a non-slipping grip keeps
            # this constant, so any growth is lost grip.
            rel = payload - samples[: len(payload)]
            drift = rel - rel[0]
            out["payload_drift_mm"] = float(np.linalg.norm(drift, axis=1).max() * 1000.0)
        return out

    @staticmethod
    def format(summary: dict) -> str:
        label = summary.get("label", "")
        parts = [
            f"steps={int(summary.get('steps', 0))}",
            f"|v|max={summary.get('v_max', 0.0):.3f} m/s",
            f"|a|max={summary.get('a_max', 0.0):.3f} m/s^2",
            f"|j|max={summary.get('j_max', 0.0):.1f} m/s^3",
        ]
        if "cone_max" in summary:
            parts.append(
                f"cone={summary['cone_max']:.2f}x budget "
                f"({int(summary['cone_over_steps'])} pct over)"
            )
        if "v_start" in summary:
            parts.append(
                f"ends |v|={summary['v_start']:.3f}/{summary['v_end']:.3f} m/s "
                f"(a_step={summary['a_step']:.2f})"
            )
        if "a_med" in summary:
            parts.append(
                f"a_med={summary['a_med']:.2f} peak@{summary['a_peak_at']:.2f} "
                f"(first10={summary['a_first10']:.2f} last10={summary['a_last10']:.2f}) m/s^2"
            )
        if "a_win" in summary:
            parts.append(f"a_win5={summary['a_win']:.2f} m/s^2")
        if "end_gap_mm" in summary:
            # The measured pad centre against the pose the leg was sent to.
            parts.append(f"end={summary['end_gap_mm']:.1f} mm")
        if "payload_drift_mm" in summary:
            parts.append(f"slip={summary['payload_drift_mm']:.1f} mm")
        return f"[motion] {label}: " + ", ".join(parts)
