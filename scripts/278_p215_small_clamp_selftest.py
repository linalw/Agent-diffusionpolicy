#!/usr/bin/env python3
"""P215 self-test: the size-dependent direct finger cap.

`FRUIT_FINGER_MAXFORCE_DIRECT_SMALL` overrides the 60 N real-jaw spec only for
fruit at/below `..._SMALL_DIA` (default 0.040 m); 0/unset keeps the global cap.
The small-fruit class is the residual and may be squeezed out at 60 N.

Pins: the two env reads, the per-sample selection, the `[drive]` tag, the
manifest block, and the global-only path when the small cap is unset.
"""
from __future__ import annotations

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
    print("P215: the size-dependent direct finger cap")
    env = (ROOT / "src" / "fruit_sorting" / "rl_env.py").read_text(encoding="utf-8")
    check('os.environ.get("FRUIT_FINGER_MAXFORCE_DIRECT_SMALL", "0")' in env,
          "the small cap is read")
    check('os.environ.get("FRUIT_FINGER_MAXFORCE_DIRECT_SMALL_DIA", "0.040")' in env,
          "the small diameter cut is read")
    start = env.index("    def _apply_direct_finger_cap")
    end = env.index("\n    def ", start + 10)
    body = env[start:end]
    check("cap = float(self._finger_cap_direct)" in body,
          "the global cap is the default")
    check('self._sample.diameter) <= self._finger_cap_small_dia' in body,
          "only a fruit at/below the diameter cut uses the small cap")
    check('tag = "FRUIT_FINGER_MAXFORCE_DIRECT_SMALL"' in body,
          "the [drive] row names the small cap")
    check("if cap <= 0.0:" in body, "a zero cap still does nothing")
    check('"finger_maxforce": (' in env, "the manifest records the armed block")
    check('"small": float(self._finger_cap_small)' in env,
          "the manifest names the small cap")
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
