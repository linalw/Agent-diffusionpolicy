#!/usr/bin/env python3
"""P211 self-test: the size-conditioned selector floor.

The small-fruit failures in the direct cells (3.0-3.4 cm) begin with the fruit
already level with or behind the hand. The global selector-timing knobs were
negative (P200's uniform +0.18 m floor: 6/12 against 8/12). P211 adds a
**direct-only** extra floor for fruit at or below `FRUIT_SELECT_SMALL_DIA`
(`FRUIT_SELECT_SMALL_EXTRA`, metres, default 0 = shipped).

  [1] the two strict parsers
  [2] `tasks.py` carries the direct gate and the size-conditioned filter, and
      the diag row uses the same per-candidate floor
  [3] the `TASKS_MD5` pin matches the file on disk
  [4] the rollout manifest records the armed values
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def grab(src: str, name: str) -> str:
    i = src.index(f"def {name}(")
    j = src.find("\ndef ", i + 5)
    return src[i:j if j > 0 else len(src)]


CHECKS = {"passed": 0, "failed": 0}



def check(condition, message):
    if condition:
        CHECKS["passed"] += 1
        print(f"  ok: {message}")
    else:
        CHECKS["failed"] += 1
        print(f"  FAIL: {message}")


TASKS_SRC = source("src", "fruit_sorting", "tasks.py")
_NS = {"os": os, "math": math}
exec(grab(TASKS_SRC, "parse_small_select_extra"), _NS)  # noqa: S102
exec(grab(TASKS_SRC, "parse_small_select_dia"), _NS)  # noqa: S102
parse_small_select_extra = _NS["parse_small_select_extra"]
parse_small_select_dia = _NS["parse_small_select_dia"]


def test_parsers():
    print("[1] the parsers")
    for raw, exp in ((None, 0.0), ("", 0.0), ("0", 0.0), ("0.15", 0.15),
                     (" 0.10 ", 0.10)):
        got = parse_small_select_extra(raw)
        check(got == exp, f"extra {raw!r} -> {exp} (got {got})")
    for raw in ("-0.1", "nan", "inf", "small"):
        try:
            parse_small_select_extra(raw)
        except ValueError:
            check(True, f"extra {raw!r} raises")
        else:
            check(False, f"extra {raw!r} must raise")
    for raw, exp in ((None, 0.040), ("", 0.040), ("0.05", 0.05)):
        got = parse_small_select_dia(raw)
        check(abs(got - exp) < 1e-12, f"dia {raw!r} -> {exp} (got {got})")
    for raw in ("0", "-0.04", "nan", "inf", "small"):
        try:
            parse_small_select_dia(raw)
        except ValueError:
            check(True, f"dia {raw!r} raises")
        else:
            check(False, f"dia {raw!r} must raise")


def test_source():
    print("[2] the selector shape")
    tasks = TASKS_SRC
    check("FRUIT_SELECT_SMALL_EXTRA" in tasks,
          "the extra floor is read")
    check("FRUIT_SELECT_SMALL_DIA" in tasks,
          "the diameter cut is read")
    check("if direct:" in tasks and "small_extra = parse_small_select_extra()" in tasks,
          "the knob is gated on the direct/policy path")
    check("if small_extra > 0.0:" in tasks
          and 'item[1].get("diameter", 0.0)) <= small_dia' in tasks,
          "only small fruit get the extra floor")
    check("_floor_i = floor + (" in tasks,
          "the diag row uses the same per-candidate floor")
    check("FRUIT_SELECT_SMALL_EXTRA" in source("src", "fruit_sorting", "rl_env.py"),
          "the rollout manifest records the armed extra")
    check('"small_select": (' in source("src", "fruit_sorting", "rl_env.py"),
          "the manifest has its own block")


def test_pin():
    print("[3] the TASKS_MD5 pin")
    digest = hashlib.md5(
        (ROOT / "src" / "fruit_sorting" / "tasks.py").read_bytes()
    ).hexdigest()
    pin = re.search(r'TASKS_MD5 = "([0-9a-f]{32})"',
                    source("src", "fruit_sorting", "rl_env.py")).group(1)
    check(pin == digest, f"TASKS_MD5 == tasks.py md5 ({digest[:8]})")


def main():
    print("P211: the size-conditioned selector floor")
    test_parsers()
    test_source()
    test_pin()
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
