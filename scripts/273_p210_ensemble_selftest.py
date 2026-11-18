#!/usr/bin/env python3
"""P210 self-test: ACT-style temporal ensembling of overlapping chunks.

P209 measured that executing half a *stochastic* chunk doubles the re-plan
boundaries and makes the command tail worse (p95 0.101 -> 0.182). The classical
remedy is to average the overlapping predictions: the new chunk's first
`steps` waypoints and the previous chunk's not-yet-executed `prev[steps:]`
describe the same future ticks. `FRUIT_POLICY_ENSEMBLE=alpha` (0 = shipped)
blends them; the helper is pure arithmetic.

  [1] the resolver: 0/unset/1, out of range and text raise
  [2] alpha 0 returns the new chunk element for element
  [3] the overlap arithmetic and the non-overlap tail
  [4] alpha 1 is the new chunk, shape mismatch falls back, steps=3 gives one row
  [5] the env wiring: one resolver, per-attempt reset, the act blend before the
      rel anchor, the banner and the manifest block
"""
from __future__ import annotations

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

from fruit_sorting.rl_env import ensemble_action_chunk, resolve_ensemble_alpha  # noqa: E402

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
    for raw, exp in ((None, 0.0), ("", 0.0), ("0", 0.0), ("0.5", 0.5),
                     ("1", 1.0), (" 0.25 ", 0.25)):
        got = resolve_ensemble_alpha(raw)
        check(got == exp, f"{raw!r} -> {exp} (got {got})")
    for raw in ("-0.1", "1.1", "nan", "inf", "half", "0,5"):
        try:
            resolve_ensemble_alpha(raw)
        except ValueError:
            check(True, f"{raw!r} raises")
        else:
            check(False, f"{raw!r} must raise")


def test_identity():
    print("[2] alpha 0 is the new chunk, element for element")
    rng = np.random.default_rng(210)
    for trial in range(6):
        new = rng.normal(size=(4, 9))
        prev = rng.normal(size=(4, 9))
        out = ensemble_action_chunk(prev, new, 2, 0.0)
        check(np.array_equal(out, new), f"trial {trial}: values unchanged")
        check(out.dtype == np.float64, f"trial {trial}: float64 result")
        out_none = ensemble_action_chunk(None, new, 2, 0.5)
        check(np.array_equal(out_none, new), f"trial {trial}: no previous -> new")


def test_blend():
    print("[3] the overlap is alpha*new + (1-alpha)*prev[steps:]")
    prev = np.arange(4 * 2, dtype=float).reshape(4, 2)
    new = np.full((4, 2), 10.0)
    out = ensemble_action_chunk(prev, new, 2, 0.5)
    check(np.allclose(out[:2], 0.5 * new[:2] + 0.5 * prev[2:4]),
          "the first two rows are the average")
    check(np.array_equal(out[2:], new[2:]),
          "the non-overlapping tail is the new chunk")
    out25 = ensemble_action_chunk(prev, new, 2, 0.25)
    check(np.allclose(out25[0], 0.25 * new[0] + 0.75 * prev[2]),
          "alpha weights the new chunk")
    out1 = ensemble_action_chunk(prev, new, 2, 1.0)
    check(np.array_equal(out1, new), "alpha 1 is the new chunk")


def test_edges():
    print("[4] edges")
    new = np.ones((4, 2))
    prev = np.zeros((4, 3))
    out = ensemble_action_chunk(prev, new, 2, 0.5)
    check(np.array_equal(out, new), "a shape mismatch falls back to new")
    prev2 = np.arange(8, dtype=float).reshape(4, 2)
    out3 = ensemble_action_chunk(prev2, new, 3, 0.5)
    check(np.allclose(out3[0], 0.5 * new[0] + 0.5 * prev2[3]),
          "execute 3 leaves one overlapping row")
    check(np.array_equal(out3[1:], new[1:]), "the rest is the new chunk")


def test_wiring():
    print("[5] the env wiring")
    env = source("src", "fruit_sorting", "rl_env.py")
    check("self._ensemble_alpha = resolve_ensemble_alpha(" in env,
          "the knob is resolved once")
    check('os.environ.get("FRUIT_POLICY_ENSEMBLE")' in env,
          "the environment read exists")
    check("self._ensemble_prev: np.ndarray | None = None" in env,
          "the per-attempt state is initialised")
    check("self._ensemble_prev: np.ndarray | None = None" in env
          and "self._ensemble_prev = None" in env,
          "the state is initialised and reset at every attempt")
    check("ensemble_action_chunk(" in env,
          "the helper is called")
    act = env[env.index("    def act("):env.index("\n    def ", env.index("    def act(") + 10)]
    blend = act.index("ensemble_action_chunk(")
    rel = act.index("self._rel_action and chunk is not None")
    check(blend < rel, "the blend happens before the rel anchor uses chunk[0]")
    check("if steps >= _raw_chunk.shape[0]:" in act,
          "an execute_steps that leaves no overlap raises")
    check('"FRUIT_POLICY_ENSEMBLE is only defined for presentation' in env,
          "non-direct presentations are refused")
    check("self.execute_steps >= self.action_horizon" in env,
          "the constructor refuses execute_steps >= action_horizon")
    check("forms are not composed with it" in env,
          "the cartesian/hybrid/dq/rel/posvel/ff forms are refused")
    check('f"[rl] ensemble: alpha=' in env,
          "the banner names the armed alpha")
    check('"ensemble": (' in env and '"overlap": int(' in env,
          "the manifest records alpha/execute/horizon/overlap")


def main():
    print("P210: temporal ensembling of overlapping chunks")
    test_resolver()
    test_identity()
    test_blend()
    test_edges()
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
