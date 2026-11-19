#!/usr/bin/env python3
"""P222 self-test: the side-conditioned scripted skill.

The scripted B-heavy control places 6/6 right-arm fruit; the learned right is
2/6. `FRUIT_HANDOVER_SIDE=right` routes every right-arm sample to
`_run_scripted`; the left stays learned. Default off, direct + ablate none.
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
    print("P222: the side-conditioned scripted skill")
    env = (ROOT / "src" / "fruit_sorting" / "rl_env.py").read_text(encoding="utf-8")
    check('os.environ.get(\n            "FRUIT_HANDOVER_SIDE", ""' in env,
          "the side knob has an empty default")
    check('("", "right", "left", "both")' in env,
          "the token table is strict")
    check("FRUIT_HANDOVER_SIDE is only defined for presentation='direct'" in env,
          "the scope is direct + ablate none")
    act = env[env.index("    def act("):env.index("\n    def ", env.index("    def act(") + 10)]
    side = act.index("if (self._handover_side")
    ablate = act.index('if self.ablate == "scripted":')
    check(side < ablate, "the side handover is before the scripted ablation")
    check('self._handover_side == self._active' in act,
          "the active arm is the side test")
    check("self._run_scripted()" in act[side:ablate],
          "the side handover runs the scripted skill")
    check('"handover_side": self._handover_side or None' in env,
          "the manifest records the side")
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
