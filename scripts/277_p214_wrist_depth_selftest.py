#!/usr/bin/env python3
"""P214 self-test: the mask-free wrist depth probe stays a bench.

The probe projects the head estimate into the wrist frame, fits a depth disk and
prints `[wrist-depth]`. It must be default-off, direct-only, and must not write
the goal, the percept state or any control target.
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
    print("P214: the mask-free wrist depth probe")
    env = (ROOT / "src" / "fruit_sorting" / "rl_env.py").read_text(encoding="utf-8")
    check('os.environ.get("FRUIT_WRIST_DEPTH_PROBE", "0")' in env,
          "the probe has its own default-off knob")
    check("FRUIT_WRIST_DEPTH_PROBE is only defined for presentation='direct'" in env,
          "it is direct-only")
    start = env.index("    def _wrist_depth_tick")
    end = env.index("\n    def ", start + 10)
    body = env[start:end]
    check("self.scene.set_wrist_pose" in body, "it drives the wrist camera")
    check("_fit_sphere" in body, "it fits the local depth patch")
    check("[wrist-depth]" in body, "it prints the probe row")
    for forbidden in ("self._goal[", "self._percept_pos =", "set_dof_position_targets"):
        check(forbidden not in body, f"it does not write {forbidden!r}")
    check("if self._wrist_depth_probe:\n            self._wrist_depth_tick()" in env,
          "the probe is called from _observe behind its flag")
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
