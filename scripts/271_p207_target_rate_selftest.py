#!/usr/bin/env python3
"""P207 self-test: the emitted joint target's rate cap.

The knob is `FRUIT_POLICY_TARGET_RATE` in **rad/s** (0/unset = the shipped
untouched target). The measured defect: `[cmd]` rows show per-waypoint steps with
p95 0.055-0.19 rad and a maximum 0.275-3.37 rad, while the arm only achieves a
p95 of 0.27-1.98 rad/s - a command transient no servo can follow smoothly.

This leg pins the pure arithmetic and the wiring, no simulator:
  [1] the resolver (0/positive; negative, NaN, inf, text raise)
  [2] the identity at rate 0 (element for element, a new float64 array)
  [3] one tick moves each joint by at most rate*dt, and an in-cap request is exact
  [4] a 0.275 rad step is spread over ceil(0.275/(rate*dt)) ticks (rate 1 rad/s)
  [5] the wiring: one resolver, the per-attempt re-seed, one call site in `_apply`
      before `set_dof_position_targets`, the servo hand-back, the banner/manifest
"""
from __future__ import annotations

import math
import os
import sys
import unittest.mock as mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
for _name in (
    "pxr", "isaacsim", "isaacsim.core", "isaacsim.core.experimental",
    "isaacsim.core.experimental.utils", "isaacsim.core.experimental.utils.app",
    "isaacsim.core.experimental.prims",
):
    sys.modules.setdefault(_name, mock.MagicMock())

import numpy as np  # noqa: E402

from fruit_sorting.rl_env import rate_limit_target, resolve_target_rate  # noqa: E402

CHECKS = {"passed": 0, "failed": 0}


def check(condition, message):
    if condition:
        CHECKS["passed"] += 1
        print(f"  ok: {message}")
    else:
        CHECKS["failed"] += 1
        print(f"  FAIL: {message}")


def source(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def test_resolver():
    print("[1] the resolver")
    for raw, expected in ((None, 0.0), ("", 0.0), (" ", 0.0), ("0", 0.0),
                          ("0.0", 0.0), ("1", 1.0), ("1.5", 1.5), ("2.5", 2.5)):
        got = resolve_target_rate(raw)
        check(got == expected, f"{raw!r} -> {expected} rad/s (got {got})")
    for raw in ("-1", "-0.5", "nan", "inf", "-inf", "slow", "1,5"):
        try:
            resolve_target_rate(raw)
        except ValueError:
            check(True, f"{raw!r} raises")
        else:
            check(False, f"{raw!r} must raise, not read as the shipped path")


def test_identity():
    print("[2] rate 0 is the shipped target, element for element")
    rng = np.random.default_rng(207)
    for trial in range(8):
        req = rng.normal(size=7).astype(np.float32 if trial % 2 else np.float64)
        before = req.copy()
        out = rate_limit_target(rng.normal(size=7), req, 0.0)
        check(np.array_equal(out, req), f"trial {trial}: values unchanged")
        check(out.dtype == np.float64, f"trial {trial}: float64 result")
        check(np.array_equal(req, before), f"trial {trial}: the request is untouched")
    req = np.array([0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 0.25])
    out = rate_limit_target(None, req, 0.0)
    check(np.array_equal(out, req) and np.signbit(out[1]) == np.signbit(req[1]),
          "signed zeros survive the off path")


def test_arithmetic():
    print("[3] one tick moves each joint by at most rate*dt")
    prev = np.zeros(7)
    req = np.array([1.0, -1.0, 0.2, -0.2, 0.0, 0.01, -0.01])
    for rate, expected in ((12.0, 0.1), (0.6, 0.005), (120.0, 1.0)):
        out = rate_limit_target(prev, req, rate, 1.0 / 120.0)
        check(np.allclose(out, np.clip(req, -expected, expected)),
              f"rate {rate}: each joint <= {expected:.4f} rad")
    inside = np.array([0.001, -0.002, 0.0, 0.003, -0.001, 0.0, 0.002])
    out = rate_limit_target(prev, inside, 1.0, 1.0 / 120.0)
    check(np.array_equal(out, inside), "an in-cap request is emitted exactly")
    try:
        rate_limit_target(np.zeros(6), np.zeros(7), 1.0)
    except ValueError:
        check(True, "a shape mismatch raises")
    else:
        check(False, "a shape mismatch must raise")


def test_step_spread():
    print("[4] a 0.275 rad step is ramped, not stepped")
    req = np.array([0.275, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    rate, dt = 1.0, 1.0 / 120.0
    prev = np.zeros(7)
    reached = None
    mono = True
    for k in range(1, 200):
        out = rate_limit_target(prev, req, rate, dt)
        if mono and out[0] + 1e-12 < prev[0]:
            mono = False
        prev = out
        if out[0] >= 0.275 - 1e-12:
            reached = k
            break
    expected = int(math.ceil(0.275 / (rate * dt)))
    check(mono, "the ramp is monotone")
    check(reached == expected, f"reaches the target in {reached} ticks (expected {expected})")
    check(expected > 1, "the 0.275 rad step is not emitted in one tick")


def test_wiring():
    print("[5] the env wiring")
    env = source("src", "fruit_sorting", "rl_env.py")
    check("self._target_rate = resolve_target_rate(" in env,
          "the knob is resolved once in the constructor")
    check('os.environ.get("FRUIT_POLICY_TARGET_RATE")' in env,
          "the environment read exists")
    check("self._rate_prev: dict[str, np.ndarray] = {}" in env,
          "the per-arm state is initialised once")
    check("self._rate_prev = {" in env and "a.joint_positions()" in env,
          "the state is re-seeded from the measured joints at every attempt")
    check("target7 = rate_limit_target(" in env,
          "the emitted target goes through the pure helper")
    start = env.index("    def _apply(self, action")
    end = env.index("\n    def ", start + 10)
    apply = env[start:end]
    check(apply.count("rate_limit_target(") == 1,
          "one rate-limit call site")
    call = apply.index("rate_limit_target(")
    write = apply.index("[np.asarray(target7, dtype=float).tolist()]")
    check(call < write, "it sits before the joint drive write")
    check("self._rate_prev.pop(self._active, None)" in apply,
          "a servo hand-back re-seeds the limiter")
    check("must not be composed with it" in env and "_posvel_action" in env,
          "the cartesian/hybrid/dq/rel/posvel/ff forms are refused, not silently inert")
    check("FRUIT_POLICY_TARGET_RATE are only " in env,
          "non-direct presentations are refused")
    check('f"target_rate={self._target_rate:.3f}rad/s "' in env,
          "the [emit] banner names the armed rate")
    check('{"target_rate": float(self._target_rate)}' in env,
          "the manifest records the armed rate")
    check("if self._target_rate > 0.0 and (" in env,
          "the cartesian guard is behind the armed condition")
    check('_joint_clamp_raw = os.environ.get("FRUIT_POLICY_JOINT_CLAMP")' in env,
          "the canonical joint-clamp name is read once")
    check('if _joint_clamp_raw is None and presentation == "direct":' in env
          and 'os.environ.get("FRUIT_JOINT_CLAMP")' in env,
          "the short recipe spelling is a direct-only alias, not a silent no-op")


def main():
    print("P207: the emitted target's rate cap")
    test_resolver()
    test_identity()
    test_arithmetic()
    test_step_spread()
    test_wiring()
    failed = CHECKS["failed"]
    total = CHECKS["passed"] + failed
    print(f"\n{CHECKS['passed']}/{total} checks passed")
    if failed:
        print(f"FAIL: {failed} check(s)")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
