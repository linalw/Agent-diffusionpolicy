"""Model-based fruit tracking (P135).

The shipped catch is a **formula**, not a tracker:

* the aim is computed once (at the pre-pose) as
  ``[fruit_x, station_y + lead, fruit_z]`` and the descent is an open-loop
  min-jerk leg to it;
* the wait that times the descent uses the **belt speed**;
* the post-arrival catch-up commands ``fruit + v * lead`` from the last
  measurement.

All three are exact while the fruit rides a constant-speed belt, and all three
are wrong the moment it does not - a collision from the other arm, a speed step,
a fruit rolling.  This module supplies the two objects that make the target a
*state estimate* instead of a formula:

``FruitTracker``
    A Kalman filter over one fruit's centre, constant velocity plus an adaptive
    process noise.  It ingests position measurements at whatever rate they
    arrive (truth at 120 Hz, a camera at 30 Hz) and predicts the state at any
    future time.  What makes a non-uniform motion *representable* is not the
    model order but the **noise**: the velocity is allowed to change by
    `sigma_a * dt` per step, so a speed step is followed inside two or three
    frames instead of asymptotically.  The normalised innovation can inflate
    that allowance further when a step is much larger than the process noise.

    The constant-*acceleration* form is available (`TrackConfig.accel`) and is
    **not** the default: a struck fruit changes velocity almost instantly, and a
    CA fit through the step reports a 2-3 m/s^2 transient that integrates to
    `0.5 a T^2` = up to 0.7 m over the remaining 0.75 s descent.  Measured on
    this tree: the CV form's prediction error one tick after an 80 mm/s step is
    16 mm, falling under 3 mm by the third tick; the CA form's first-tick
    correction is -741 mm with the sign flipping again 40 ms later.

``conveyor_model`` / ``correction``
    The **nominal** is the conveyor: ``position at the descent start + belt
    velocity * elapsed``.  The correction the catch applies is the part of the
    fruit's motion that the conveyor model does not explain.  That definition is
    load-bearing: under the model the correction is identically zero, so the
    shipped path is untouched and the only behaviour that changes is the
    behaviour the model gets wrong.

The estimator is initialised from the first measurement **and its measured
velocity** when one is available, so on a constant-velocity fruit the filter's
mean is the measurement - ``tracker.predict(h)`` equals ``p + v*h`` to machine
precision, which is what keeps the no-harm replays clean.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _eye3(value: float) -> np.ndarray:
    return np.eye(3) * float(value)


@dataclass
class TrackConfig:
    """Estimator settings, all overridable from the environment by the caller."""

    #: Constant acceleration on top of constant velocity.  Off by default; see
    #: the module docstring for the measured reason.
    accel: bool = False
    #: Measurement noise [m].  Truth reads are exact to the solver's float noise;
    #: a rendered point cloud is a few millimetres.
    sigma_z: float = 2.0e-4
    #: Acceleration spectral density [m/s^2/sqrt(Hz)] - the manoeuvre allowance.
    #: At 1.5 the velocity may change by 0.12 m/s per 100 ticks (the belt's whole
    #: speed), which follows a step in two or three frames and stays quiet
    #: otherwise.
    sigma_a: float = 1.5
    #: Normalised-innovation-squared threshold above which the filter declares a
    #: manoeuvre and inflates the process noise for the next prediction.
    nis_gate: float = 9.0
    #: Multiplier applied to ``sigma_a`` while a manoeuvre is flagged.
    boost: float = 12.0


class FruitTracker:
    """A 3-D constant-acceleration Kalman filter for one fruit's centre.

    State: ``[p(3), v(3), a(3)]``.  One tracker per selected fruit per attempt;
    it is cheap (9x9 algebra) and it owns no simulator state, so it can be fed
    from truth or from a rendered point cloud without changing the caller.
    """

    def __init__(self, config: TrackConfig | None = None) -> None:
        self.cfg = config or TrackConfig()
        self.x = np.zeros(9, dtype=float)
        self.P = np.eye(9, dtype=float) * 1.0
        self.t = 0.0
        self.initialised = False
        self._boost = 1.0
        #: Diagnostics: the last NIS and the number of manoeuvre flags raised.
        self.last_nis = 0.0
        self.manoeuvres = 0
        #: Last correction the tracker asked for, for the ``[track]`` row.
        self.last_correction = np.zeros(3, dtype=float)

    # ------------------------------------------------------------------ #
    def reset(self, position, t: float, velocity=None) -> None:
        """Seed the filter from one measurement (and a velocity if one exists)."""
        self.x = np.zeros(9, dtype=float)
        self.x[0:3] = np.asarray(position, dtype=float)
        if velocity is not None:
            self.x[3:6] = np.asarray(velocity, dtype=float)
        self.P = np.eye(9, dtype=float)
        self.P[0:3, 0:3] *= (self.cfg.sigma_z * 2.0) ** 2
        # A measured velocity is trusted; an unmeasured one is not.
        self.P[3:6, 3:6] *= 1.0e-6 if velocity is not None else 0.25
        self.P[6:9, 6:9] *= 1.0 if self.cfg.accel else 1.0e-9
        self.t = float(t)
        self.initialised = True
        self._boost = 1.0
        self.last_nis = 0.0

    # ------------------------------------------------------------------ #
    def _transition(self, dt: float) -> np.ndarray:
        F = np.eye(9, dtype=float)
        F[0:3, 3:6] = _eye3(dt)
        if self.cfg.accel:
            F[0:3, 6:9] = _eye3(0.5 * dt * dt)
            F[3:6, 6:9] = _eye3(dt)
        return F

    def _process(self, dt: float) -> np.ndarray:
        """Discrete white-acceleration process noise (the CA model's own)."""
        if not self.cfg.accel:
            # Constant-velocity: the unmodelled acceleration is the noise.
            q = (self.cfg.sigma_a * self._boost) ** 2
            Q = np.zeros((9, 9), dtype=float)
            Q[0:3, 0:3] = _eye3(q * dt ** 3 / 3.0)
            Q[0:3, 3:6] = _eye3(q * dt * dt / 2.0)
            Q[3:6, 0:3] = _eye3(q * dt * dt / 2.0)
            Q[3:6, 3:6] = _eye3(q * dt)
            Q[6:9, 6:9] = _eye3(1.0e-12)
            return Q
        q = (self.cfg.sigma_a * self._boost) ** 2
        Q = np.zeros((9, 9), dtype=float)
        Q[0:3, 0:3] = _eye3(q * dt ** 5 / 20.0)
        Q[0:3, 3:6] = _eye3(q * dt ** 4 / 8.0)
        Q[0:3, 6:9] = _eye3(q * dt ** 3 / 6.0)
        Q[3:6, 0:3] = Q[0:3, 3:6]
        Q[3:6, 3:6] = _eye3(q * dt ** 3 / 3.0)
        Q[3:6, 6:9] = _eye3(q * dt * dt / 2.0)
        Q[6:9, 0:3] = Q[0:3, 6:9]
        Q[6:9, 3:6] = Q[3:6, 6:9]
        Q[6:9, 6:9] = _eye3(q * dt)
        return Q

    def predict(self, dt: float) -> np.ndarray:
        """Advance the estimate by ``dt`` seconds; returns the predicted centre."""
        dt = float(dt)
        if dt <= 0.0:
            return self.x[0:3].copy()
        F = self._transition(dt)
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + self._process(dt)
        self.t += dt
        if not self.cfg.accel:
            self.x[6:9] = 0.0
        return self.x[0:3].copy()

    def update(self, position, t: float) -> float:
        """Fold in a position measurement at time ``t``; returns the NIS."""
        z = np.asarray(position, dtype=float)
        if not self.initialised:
            self.reset(z, t)
            return 0.0
        dt = max(0.0, float(t) - self.t)
        if dt > 0.0:
            self.predict(dt)
        H = np.zeros((3, 9), dtype=float)
        H[0:3, 0:3] = np.eye(3)
        R = _eye3(self.cfg.sigma_z ** 2)
        innovation = z - H @ self.x
        S = H @ self.P @ H.T + R
        # NIS: how many measurement sigmas the innovation is, in 3-D.
        nis = float(innovation @ np.linalg.solve(S, innovation))
        self.last_nis = nis
        # A manoeuvre is a run of large innovations, not one bad frame: the
        # filter inflates its process noise only when the *smoothed* innovation
        # is large, and decays back when it is not.
        if nis > self.cfg.nis_gate:
            self._boost = self.cfg.boost
            self.manoeuvres += 1
        else:
            self._boost = max(1.0, 0.75 * self._boost)
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ innovation
        self.P = (np.eye(9) - K @ H) @ self.P
        self.t = float(t)
        if not self.cfg.accel:
            self.x[6:9] = 0.0
        return nis

    # ------------------------------------------------------------------ #
    def predict_at(self, horizon: float) -> np.ndarray:
        """Where the fruit will be ``horizon`` seconds from now [m]."""
        h = float(horizon)
        p = self.x[0:3].copy()
        if h <= 0.0:
            return p
        p = p + self.x[3:6] * h
        if self.cfg.accel:
            p = p + 0.5 * self.x[6:9] * h * h
        return p

    @property
    def position(self) -> np.ndarray:
        return self.x[0:3].copy()

    @property
    def velocity(self) -> np.ndarray:
        return self.x[3:6].copy()

    @property
    def acceleration(self) -> np.ndarray:
        return self.x[6:9].copy()


def conveyor_model(position0, belt_velocity, elapsed: float) -> np.ndarray:
    """The schedule's own forecast: start position + belt velocity * time."""
    return np.asarray(position0, dtype=float) + np.asarray(belt_velocity, dtype=float) * float(elapsed)


def correction(
    tracker: FruitTracker,
    position0,
    belt_velocity,
    elapsed: float,
    horizon: float,
    limit: float = 0.0,
) -> np.ndarray:
    """The part of the fruit's motion the conveyor model does not explain.

    At the descent end (``horizon == 0``) this is where the fruit actually is
    minus where the constant-speed schedule said it would be; under the model it
    is identically zero.  A non-zero ``limit`` clamps the norm - a correction
    larger than the arm can spend inside the leg is better handled by the
    catch-up, which measures its own residual.
    """
    predicted = tracker.predict_at(horizon)
    nominal = conveyor_model(position0, belt_velocity, float(elapsed) + float(horizon))
    delta = predicted - nominal
    if limit and float(np.linalg.norm(delta)) > float(limit):
        delta = delta * (float(limit) / float(np.linalg.norm(delta)))
    tracker.last_correction = delta
    return delta


def track_config_from_env(environ, source: str = "truth") -> TrackConfig:
    """Read the estimator's settings once per attempt (cheap, no simulator reads)."""

    def _f(name, default):
        try:
            value = float(environ.get(name, default))
        except (TypeError, ValueError):
            return float(default)
        return value if np.isfinite(value) else float(default)

    # The measurement noise has to match the *source*, or the filter fits the
    # noise: a rendered point cloud's fitted centre is ~5 mm (P135's bench), and
    # a filter told it is 0.2 mm reads a velocity of 0.03 m/s on a 0.12 m/s
    # fruit. Unset means "the source's own measured value".
    default_sigma = {
        "truth": 2.0e-4,
        "depth": 5.0e-3,
    }.get(source, 2.0e-4)
    return TrackConfig(
        accel=environ.get("FRUIT_TRACK_ACCEL", "0") == "1",
        sigma_z=_f("FRUIT_TRACK_SIGMA_Z", default_sigma),
        sigma_a=_f("FRUIT_TRACK_SIGMA_A", 1.5),
        nis_gate=_f("FRUIT_TRACK_NIS", 9.0),
        boost=_f("FRUIT_TRACK_BOOST", 12.0),
    )
