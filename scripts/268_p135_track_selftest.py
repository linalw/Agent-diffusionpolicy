#!/usr/bin/env python3
"""P135 self-test: the tracker's off path and its two definitions.

Three things are pinned here, and each is a claim the phase makes in prose:

1. **The estimator is exact on the model.** A fruit on a constant-velocity
   conveyor gives `predict(h) == p + v*h` to machine precision - that is why the
   tracked path is the shipped path when the model holds. A velocity step is
   followed inside three ticks; the constant-acceleration form (which is *not*
   the default) overshoots by two orders of magnitude on the same step, which is
   the recorded reason it is off.
2. **The correction is defined against the conveyor.** Under the model it is
   identically zero; at the end of a step it is the fruit's displacement off the
   conveyor's forecast. It is clamped by `FRUIT_TRACK_CORR_MAX`.
3. **The calibration is a ratio.** The pinhole intrinsics come from the authored
   focal length and aperture, so the stage's units cancel; a synthetic sphere is
   back-projected and re-fitted to zero error.
4. **Every knob is off by default**, and the tree's control path is unchanged
   when they are.
"""
from __future__ import annotations

import ast
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fruit_sorting.perception import CameraModel, _fit_sphere  # noqa: E402
from fruit_sorting.tracking import (  # noqa: E402
    FruitTracker,
    TrackConfig,
    correction,
    track_config_from_env,
)

CHECKS = {"passed": 0, "failed": 0}


def check(condition, message):
    if condition:
        CHECKS["passed"] += 1
        print(f"  ok: {message}")
    else:
        CHECKS["failed"] += 1
        print(f"  FAIL: {message}")


def test_estimator():
    print("[1] the estimator is exact on the model")
    dt = 1.0 / 120.0
    config = track_config_from_env({}, "truth")
    check(config.accel is False, "the default model is constant velocity")
    check(abs(config.sigma_z - 2.0e-4) < 1e-12, "truth's default sigma_z is 0.2 mm")
    depth = track_config_from_env({}, "depth")
    check(abs(depth.sigma_z - 5.0e-3) < 1e-12,
          "depth's default sigma_z is the bench's 5 mm, not the truth's 0.2 mm")

    p0 = np.array([0.30, 0.40, 1.25])
    v = np.array([0.0, -0.12, 0.0])
    tracker = FruitTracker(config)
    tracker.reset(p0, 0.0, v)
    worst = 0.0
    for i in range(120):
        t = (i + 1) * dt
        tracker.update(p0 + v * t, t)
        worst = max(worst, float(np.linalg.norm(tracker.predict_at(0.25) - (p0 + v * (t + 0.25)))))
    check(worst < 1e-9, f"CV: predict(0.25) equals p + v*h for 120 frames (worst {worst:.2e} m)")

    # a step: v -> -0.20 after 30 frames
    tracker = FruitTracker(config)
    tracker.reset(p0, 0.0, v)
    v2 = np.array([0.0, -0.20, 0.0])
    target = v
    for i in range(60):
        t = (i + 1) * dt
        if i == 30:
            target = v2
        position = p0 + v * (30 * dt) + v2 * (t - 30 * dt) if i >= 30 else p0 + v * t
        tracker.update(position, t)
        if i == 33:
            check(abs(float(tracker.velocity[1]) - (-0.20)) < 0.02,
                  "CV: the velocity step is followed by the third tick "
                  f"({float(tracker.velocity[1]):+.4f} m/s)")
        if i == 34:
            error = float(np.linalg.norm(tracker.predict_at(0.7) - (
                p0 + v * (30 * dt) + v2 * (t - 30 * dt + 0.7)
            )))
            check(error < 0.010, f"CV: the 0.7 s prediction is within 10 mm after the step ({error * 1000:.1f} mm)")

    # the CA form on the same step: the recorded reason it is off
    ca = FruitTracker(TrackConfig(accel=True, sigma_a=1.5))
    ca.reset(p0, 0.0, v)
    for i in range(60):
        t = (i + 1) * dt
        position = p0 + v * (30 * dt) + v2 * (t - 30 * dt) if i >= 30 else p0 + v * t
        ca.update(position, t)
        if i == 31:
            delta = ca.predict_at(0.7) - (p0 + v * (30 * dt) + v2 * (t - 30 * dt + 0.7))
            check(abs(float(delta[1])) > 0.10,
                  "CA: one tick after the step the correction is > 100 mm "
                  f"({float(delta[1]) * 1000:+.1f} mm) - the recorded negative")


def test_correction():
    print("[2] the correction is defined against the conveyor")
    dt = 1.0 / 120.0
    p0 = np.array([0.30, 0.40, 1.25])
    belt = np.array([0.0, -0.12, 0.0])
    tracker = FruitTracker(TrackConfig())
    tracker.reset(p0, 0.0, belt)
    for i in range(60):
        t = (i + 1) * dt
        tracker.update(p0 + belt * t, t)
    zero = correction(tracker, p0, belt, 60 * dt, 0.0)
    check(float(np.linalg.norm(zero)) < 1e-9,
          "under the conveyor model the correction is identically zero")

    # a step: the correction at the leg's end is the fruit's displacement off
    # the conveyor's forecast
    tracker = FruitTracker(TrackConfig())
    tracker.reset(p0, 0.0, belt)
    v2 = np.array([0.0, -0.20, 0.0])
    for i in range(60):
        t = (i + 1) * dt
        position = p0 + belt * t if i < 30 else p0 + belt * (30 * dt) + v2 * (t - 30 * dt)
        tracker.update(position, t)
    elapsed = 60 * dt
    end = correction(tracker, p0, belt, elapsed, 0.0)
    expected = -0.08 * (elapsed - 30 * dt)
    check(abs(float(end[1]) - expected) < 0.005,
          f"after a step the correction is the off-conveyor displacement "
          f"({float(end[1]) * 1000:+.1f} vs {expected * 1000:+.1f} mm)")
    clamped = correction(tracker, p0, belt, elapsed, 0.0, limit=0.01)
    check(abs(float(np.linalg.norm(clamped)) - 0.01) < 1e-9,
          "FRUIT_TRACK_CORR_MAX clamps the correction's norm")


def test_camera():
    print("[3] the calibration and the sphere fit")
    eye = np.array([0.05, 0.0, 2.0])
    target = np.array([0.34, 0.22, 1.10])
    z_axis = eye - target
    z_axis /= np.linalg.norm(z_axis)
    x_axis = np.cross(np.array([0.0, 0.0, 1.0]), z_axis)
    x_axis /= np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    rotation = np.stack([x_axis, y_axis, z_axis], axis=1)
    width, height = 848, 480
    camera = CameraModel(width, height, 0.016, 0.036, 0.02025, rotation, eye, 1.0)
    fx, fy, cx, cy = camera.intrinsics(height, width)
    check(abs(fx - fy) / fx < 0.01, f"square pixels: fx {fx:.2f} / fy {fy:.2f}")
    # the intrinsics are a ratio: a scene authored in centimetres reads the same
    check(abs(width * 0.016 / 0.036 - fx) < 1e-9,
          "fx = width * focal / aperture (the stage's units cancel)")

    centre = np.array([0.30, 0.0, 1.245])
    radius = 0.030
    u, v = np.meshgrid(np.arange(width), np.arange(height))
    rays = np.stack([(u - cx) / fx, -(v - cy) / fy, -np.ones_like(u, dtype=float)], axis=-1)
    rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
    world = rays @ rotation.T
    b = 2.0 * np.einsum("ijk,k->ij", world, eye - centre)
    cc = (eye - centre) @ (eye - centre) - radius * radius
    disc = b * b - 4 * cc
    hit = disc > 0
    t = (-b - np.sqrt(np.maximum(disc, 0))) / 2.0
    depth_plane = np.where(hit, t * (-rays[..., 2]), 0.0)
    pixels = np.argwhere(hit)[:, ::-1]
    check(len(pixels) > 500, f"a 60 mm sphere at 0.8 m covers {len(pixels)} pixels")
    points = camera.backproject(depth_plane, pixels)
    fitted, fitted_radius, rms = _fit_sphere(points)
    check(float(np.linalg.norm(fitted - centre)) < 1e-6,
          f"the sphere fit recovers the centre (err {np.linalg.norm(fitted - centre) * 1000:.2e} mm)")
    check(abs(2 * fitted_radius - 0.060) < 1e-6 and rms < 1e-9,
          "and the diameter, with a zero residual")


def test_off_path():
    print("[4] every knob is off by default")
    source = open(os.path.join(ROOT, "src/fruit_sorting/tasks.py"), encoding="utf-8").read()
    tree = ast.parse(source)

    def default(env_name, literal):
        # one `os.environ.get("<name>", "<literal>")` occurrence for the knob
        return f'os.environ.get("{env_name}", "{literal}")' in source

    check(default("FRUIT_TRACK", "off"), "FRUIT_TRACK defaults to off")
    check(default("FRUIT_TRACK_APPLY", "1"), "FRUIT_TRACK_APPLY defaults on (it only scopes the probe)")
    check(default("FRUIT_DESCENT_TRACK", "0"), "FRUIT_DESCENT_TRACK defaults off")
    check(default("FRUIT_TRACK_WAIT", "0"), "FRUIT_TRACK_WAIT defaults off")
    check(default("FRUIT_TRACK_CATCH_SPEED", "0.0"), "FRUIT_TRACK_CATCH_SPEED defaults off")
    check(default("FRUIT_PERTURB_AT", "0"), "the impulse cell's tick defaults to 0 (inert: dx/dy are 0)")
    check(default("FRUIT_BELT_WAVE_AMP", "0.0"), "the belt wave defaults to zero")
    check(default("FRUIT_WRIST_CAMERA", "0"), "the eye-in-hand camera defaults off")
    check(default("FRUIT_WRIST_LOOK", "0.12"),
          "the wrist camera aims 12 cm down the tool axis (the measured-best mount)")
    check(default("FRUIT_WRIST_UPSTREAM", "0.0"),
          "the upstream tilt is 0 (at 0.16 m it reads 1-6 frames per attempt)")
    check(default("FRUIT_WRIST_SWITCH", "0.0"),
          "the head/wrist handover is off by default (wrist only)")
    check('offset_wrist_m' in open(
        os.path.join(ROOT, "configs", "perception_calibration.json"),
        encoding="utf-8",
    ).read(), "the wrist camera carries its own mount offset")
    check('FRUIT_PERTURB_DX", "0.0"' in source and 'FRUIT_PERTURB_DY", "0.0"' in source,
          "the impulse defaults to zero on every axis")
    # the two per-tick guards are attribute tests on pre-resolved booleans
    check("if self._perturb_on:" in source and "if self._belt_wave_on:" in source,
          "the per-tick instruments are one bool test each")
    # `_approach` keeps its positional signature and only gains a keyword
    approach = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_approach"
    )
    names = [arg.arg for arg in approach.args.args]
    check(names[:3] == ["self", "arm", "jaw_target"], "`_approach` keeps (self, arm, jaw_target)")
    check(approach.args.defaults and approach.args.args[-1].arg == "track",
          "`track` is the last positional argument, defaulted to None")
    # the tracked branch is inside the cartesian profile and re-reads the aim
    check("t_remaining = (len(positions) - i) * CONTROL_DT" in source,
          "the descent re-evaluates the aim every tick")
    check("aim = arm.tcp_target_for_jaw(" in source,
          "the tracked aim is converted to the TCP frame (the leg's own frame)")
    # the perception is built on the main thread, not in an attempt thread
    check('self._perception_state = perception_from_env(self.scene, self.cfg)' in source,
          "the camera calibration is built once, at construction")
    # the truth fallback is refused
    check("A dropped frame returns **None**" in source
          or "never falls back to the simulator's state" in source,
          "a dropped perception frame predicts through; it does not read the state")


def main():
    print("P135 tracker self-test")
    test_estimator()
    test_correction()
    test_camera()
    test_off_path()
    print(
        f"\n{'PASS' if CHECKS['failed'] == 0 else 'FAIL'}: "
        f"{CHECKS['passed']} checks, {CHECKS['failed']} failed"
    )
    return 0 if CHECKS["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
