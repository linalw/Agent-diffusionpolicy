#!/usr/bin/env python3
"""P216 self-test: the phase close's along-belt window is two-sided.

The shipped trigger was `dy <= hi`; a fruit **behind** the hand has negative dy,
so the phase gate closed the pads at -0.44 m on the small-fruit cells. The
default `lo=-inf` is the shipped path; `lo=-0.02` is the measured window.
"""
from __future__ import annotations

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fruit_sorting.rl_env import close_phase_trigger  # noqa: E402

CHECKS = {"passed": 0, "failed": 0}


def check(condition, message):
    if condition:
        CHECKS["passed"] += 1
        print(f"  ok: {message}")
    else:
        CHECKS["failed"] += 1
        print(f"  FAIL: {message}")


def main():
    print("P216: the phase close's two-sided along window")
    check(close_phase_trigger(-0.442, 0.014, -math.inf) is True,
          "the shipped -inf still fires at -0.442 m")
    check(close_phase_trigger(-0.442, 0.014, -0.02) is False,
          "the measured -0.02 refuses -0.442 m")
    check(close_phase_trigger(0.010, 0.014, -0.02) is True,
          "a fruit 10 mm upstream fires")
    check(close_phase_trigger(-0.010, 0.014, -0.02) is True,
          "a fruit 10 mm behind fires")
    check(close_phase_trigger(0.020, 0.014, -0.02) is False,
          "a fruit 20 mm upstream is outside the upper bound")
    check(close_phase_trigger(-0.030, 0.014, -0.02) is False,
          "a fruit 30 mm behind is outside the lower bound")
    env = open(os.path.join(ROOT, "src", "fruit_sorting", "rl_env.py"),
               encoding="utf-8").read()
    check('FRUIT_CLOSE_RAMP_DY_LO", "-inf"' in env,
          "the default is the shipped -inf")
    check("phase_trigger = close_phase_trigger(" in env,
          "the phase trigger calls the pure helper")
    check('"close_ramp": (' in env, "the manifest records the window")
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
