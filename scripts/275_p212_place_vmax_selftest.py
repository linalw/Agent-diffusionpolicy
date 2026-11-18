#!/usr/bin/env python3
"""P212 self-test: the place transit's per-arm speed.

The adopted 0.20 m/s is a global P173 peak; the right arm (~48 %) and left (~70 %)
have different paths and failure classes. `FRUIT_PLACE_SERVO_VMAX_LEFT/RIGHT`
override the global per arm, falling back to it when unset. This leg pins the
source shape without a simulator:
  [1] the two attrs resolve from their env names with the global fallback
  [2] `_apply_place_servo` selects by side and the reference step uses it
  [3] the banner prints only when an arm differs
  [4] the manifest records the armed values only when they differ
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {"passed": 0, "failed": 0}


def check(condition, message):
    if condition:
        CHECKS["passed"] += 1
        print(f"  ok: {message}")
    else:
        CHECKS["failed"] += 1
        print(f"  FAIL: {message}")


def main():
    print("P212: the per-arm place transit speed")
    env = (ROOT / "src" / "fruit_sorting" / "rl_env.py").read_text(encoding="utf-8")
    check('os.environ.get("FRUIT_PLACE_SERVO_VMAX_LEFT", "")' in env,
          "the left override is read")
    check('os.environ.get("FRUIT_PLACE_SERVO_VMAX_RIGHT", "")' in env,
          "the right override is read")
    check("or self._place_vmax" in env,
          "both fall back to the global value")
    start = env.index("    def _apply_place_servo")
    end = env.index("\n    def ", start + 10)
    servo = env[start:end]
    check("self._place_vmax_right if side == \"right\" else self._place_vmax_left" in servo,
          "the servo selects the value by the active side")
    check("_step = float(_place_vmax) * (1.0 / 120.0)" in servo,
          "the reference step uses the per-arm value")
    check('f"[rl] place servo: vmax=' in env,
          "the banner exists")
    check("self._place_vmax_left != self._place_vmax" in env
          and "self._place_vmax_right != self._place_vmax" in env,
          "the banner/manifest gate on an arm differing from the global")
    check('"place_servo": (' in env, "the manifest has its own block")
    check('"vmax_left": float(self._place_vmax_left)' in env
          and '"vmax_right": float(self._place_vmax_right)' in env,
          "the manifest names both arms")
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
