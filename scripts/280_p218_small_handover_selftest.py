#!/usr/bin/env python3
"""P218 self-test: the size-conditioned scripted skill.

The learned policy never approaches a 3.1-3.4 cm fruit (P216); the shipped
scripted catch places 5/6 lychees at 10 N (P217). `FRUIT_SMALL_HANDOVER=1` routes
a fruit at/below `..._DIA` (default 0.040 m) to `_run_scripted` (the same
`task.run` as `--ablate scripted`); the learned policy keeps the large fruit.
Default off; direct + ablate none only.
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
    print("P218: the size-conditioned scripted skill")
    env = (ROOT / "src" / "fruit_sorting" / "rl_env.py").read_text(encoding="utf-8")
    check('os.environ.get("FRUIT_SMALL_HANDOVER", "0")' in env,
          "the handover is default-off")
    check('os.environ.get("FRUIT_SMALL_HANDOVER_DIA", "0.040")' in env,
          "the diameter cut is 0.040 m")
    check("FRUIT_SMALL_HANDOVER is only defined for presentation='direct'" in env,
          "the scope is direct + ablate none")
    act = env[env.index("    def act("):env.index("\n    def ", env.index("    def act(") + 10)]
    branch = act.index("if (self._small_handover and self._sample is not None")
    ablate = act.index('if self.ablate == "scripted":')
    check(branch < ablate, "the handover is evaluated before the scripted ablation")
    check("self._run_scripted()" in act[branch:ablate],
          "the handover runs the scripted skill")
    check("float(self._sample.diameter) <= self._small_handover_dia" in act,
          "only a small fruit is routed")
    check('"small_handover": (' in env, "the manifest records the armed block")
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
