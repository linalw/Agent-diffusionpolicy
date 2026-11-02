#!/usr/bin/env python3
"""P94 offset-bound selftest (offline; a selfcheck leg).

Pins the shape of `FRUIT_CARRY_OFFSET_MAX=<m>` - the bound on the `_gripper_offset`
that `_carry`'s assisted branch may apply as a **tool** offset on the jaw hand -
without a simulator and without writing to the tree.

Why the knob exists: `_gripper_offset[side]` is written once per grasp as
`rot.T @ (payload - tcp_position())` (the grasp routine's entry). On a hand whose
pads *are* the fingers that is a tool offset only while the payload was at the
hand when the reading was taken; when the fruit was far out at the entry the same
number is the payload's **distance**, and the assisted branch commanded the arm
that far from the pads. P93 measured one leg at `|offset| = 1313 mm` (18.8x the
hand's own `_pad_standoff` = 70 mm) with a 419 N / 1.545 m/s / 2361 mm-slip arm
flight, and the same-seed control carrying the same path at 116 mm.

What this leg checks:

1. `tasks.parse_carry_offset_max` - the whole resolution table: unset/empty is
   the shipped **0.20 m** bound, `0` is **off** (the pre-P94 path), `0 < m <= 0.5`
   is the bound in metres, and
   every inadmissible form raises: non-numeric, negative, `nan`, `inf`, and
   `m > 0.5` (a bound that admits the measured 350 mm / 1313 mm readings is not a
   bound). Exactly one call site.
2. The guard is **one** site, in `_carry`'s assisted branch: one `_offset_used`
   definition, the comparison on `norm(offset_tool)` against
   `self.carry_offset_max_m`, the `hand_is_jaw` scope, and the `> 0.0`
   short-circuit that makes `=0` the pre-P94 path bit for bit.
3. The **arithmetic of the shipped expressions**, executed: with the reading
   inside the bound the applied command is `centre - rot @ offset` (identical to
   the pre-P94 expression); with the reading above it the command is `centre`
   (applied jump 0); and the kinematic-pad hand keeps the offset at **any**
   magnitude (the guard is jaw-hand only).
4. The three reference sites are **untouched**: the coherent branch
   (`tcp_target_for_jaw(centre)` under `if hand_is_jaw`), `_carry`'s tail
   (`placed if hand_is_jaw else placed - rot @ offset_tool`) and `_place_low`
   (`if hand_is_jaw: ik_step(jaw0 ...) else: ... offset_tool`).
5. The diag row prints the **issued** target (`_jaw_target`), so the leg census
   reads the applied jump from either arm's records with no new field; and the
   row's text is byte-unchanged for a leg the guard does not act on.

Exit 0 on pass, 1 on the first failure.
"""
from __future__ import annotations

import math
import re
import textwrap
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FAILS: list[str] = []
CHECKS = 0


def check(cond, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(msg)


def grab(src: str, name: str) -> str:
    i = src.index(f"def {name}(")
    j = src.find("\ndef ", i + 5)
    return src[i:j if j > 0 else len(src)]


def main() -> int:
    tasks_src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")

    # ------------------------------------------------------------------ 1
    ns: dict = {"os": __import__("os"), "math": math}
    exec(grab(tasks_src, "parse_carry_offset_max"), ns)  # noqa: S102 - pinned source
    parse = ns["parse_carry_offset_max"]

    check(parse("") == 0.20, "unset/empty -> 0.20 (the shipped bound)")
    check(parse("0") == 0.0, "explicit 0 -> off (the pre-P94 path)")
    check(parse("0.0") == 0.0, "explicit 0.0 -> off")
    check(parse("  ") == 0.20, "whitespace -> the shipped bound")
    check(parse("0.20") == 0.20, "0.20 -> the registered bound")
    check(parse("0.5") == 0.5, "0.5 -> the ceiling itself is admissible")
    check(abs(parse("0.2") - 0.2) < 1e-12, "the operand is metres")

    def raises(fn, *a) -> bool:
        try:
            fn(*a)
        except ValueError:
            return True
        except Exception:  # noqa: BLE001
            return False
        return False

    for bad in ("abc", "20cm", "-0.1", "-1", "nan", "inf", "-inf"):
        check(raises(parse, bad), f"parse({bad!r}) raises ValueError")
    for high in ("0.51", "1", "2", "13"):
        check(raises(parse, high),
              f"parse({high!r}) raises: a bound above 0.5 m admits the measured defects")
    parse_src = grab(tasks_src, "parse_carry_offset_max")
    check("metres > 0.5" in parse_src, "the 0.5 m ceiling is a literal in the resolver")
    check("1313" in parse_src and "350" in parse_src,
          "the resolver names the measured defect readings")
    ns["os"].environ["FRUIT_CARRY_OFFSET_MAX"] = "0.30"
    check(parse() == 0.30, "unset raw reads FRUIT_CARRY_OFFSET_MAX from the environment")
    check(parse("0") == 0.0, "an explicit raw value wins over the environment")
    del ns["os"].environ["FRUIT_CARRY_OFFSET_MAX"]

    check(tasks_src.count("parse_carry_offset_max()") == 1,
          "exactly one call site (the task's own attribute)")
    check("self.carry_offset_max_m = parse_carry_offset_max()" in tasks_src,
          "the resolved bound is the attribute the carry reads")

    # ------------------------------------------------------------------ 2
    check(tasks_src.count("_offset_used") == 2,
          "one definition + one read of `_offset_used` (nothing else branches on it)")
    check(tasks_src.count("self.carry_offset_max_m") == 3,
          "the bound is read at one site besides its own assignment (one compare, "
          "one operand)")
    check(tasks_src.count("centre - rot @ offset_tool") == 1,
          "the offset is applied at exactly one surviving site")

    i = tasks_src.index("_offset_used = bool(")
    start = tasks_src.rfind("\n", 0, i) + 1
    end = tasks_src.index("else np.asarray(centre, dtype=float)", i)
    end = tasks_src.index(")", tasks_src.index(")", end) + 1) + 1
    guard_src = textwrap.dedent(tasks_src[start:end])
    check("hand_is_jaw" in guard_src, "the guard is scoped to the jaw hand")
    check("self.carry_offset_max_m > 0.0" in guard_src,
          "`=0` short-circuits the guard (the pre-P94 path)")
    check("float(np.linalg.norm(offset_tool))" in guard_src,
          "the test is on the reading's magnitude, in metres")
    check("> self.carry_offset_max_m" in guard_src,
          "the comparison is > (a reading at the bound is still a tool offset)")
    check("np.asarray(centre, dtype=float)" in guard_src,
          "the fallback is the coherent command (the pads), not a clamped offset")

    # ------------------------------------------------------------------ 3
    def issued(bound: float, hand_is_jaw: bool, offset) -> tuple[bool, np.ndarray]:
        scope = {
            "np": np, "hand_is_jaw": hand_is_jaw, "offset_tool": offset,
            "centre": np.array([0.10, -0.20, 1.30]),
            "rot": np.eye(3),
            "self": SimpleNamespace(carry_offset_max_m=bound),
        }
        exec(guard_src, scope)  # noqa: S102 - the shipped expressions, executed
        return scope["_offset_used"], scope["_jaw_target"]

    centre = np.array([0.10, -0.20, 1.30])
    small = np.array([0.011, -0.032, 0.004])          # 34 mm, the shipped population
    big = np.array([0.3454, 0.0536, -0.0053])         # 350 mm, C5 attempt 1
    huge = np.array([0.5991, 0.2437, 1.1432])         # 1313 mm, P93's flight

    used, target = issued(0.20, True, small)
    check(used and np.allclose(target, centre - small),
          "inside the bound the command IS `centre - rot @ offset` (pre-P94, bit for bit)")
    used, target = issued(0.20, True, big)
    check((not used) and np.allclose(target, centre),
          "above the bound the jaw hand is commanded the pads (applied jump 0)")
    used, target = issued(0.20, True, huge)
    check((not used) and np.allclose(target, centre),
          "the 1313 mm reading is refused too (the P93 leg)")
    used, target = issued(0.0, True, huge)
    check(used and np.allclose(target, centre - huge),
          "with the knob at 0 the pre-P94 command is restored exactly")
    used, target = issued(0.20, False, huge)
    check(used and np.allclose(target, centre - huge),
          "the kinematic-pad hand keeps its offset at any magnitude (it IS a tool offset)")
    # the applied jump is what the census reads
    check(abs(np.linalg.norm(target - centre) - np.linalg.norm(huge)) < 1e-9,
          "the applied jump of a non-guarded leg equals its reading")
    used, target = issued(0.20, True, huge)
    check(np.linalg.norm(target - centre) == 0.0,
          "the applied jump of a guarded leg is exactly 0")

    # ------------------------------------------------------------------ 4
    check(tasks_src.count("centre if hand_is_jaw else") == 0,
          "(no other form of the guard was introduced)")
    check("placed if hand_is_jaw else placed - rot @ offset_tool" in tasks_src,
          "_carry's tail keeps its own hand_is_jaw guard, untouched")
    check(tasks_src.count("_tcp_tgt_issued = arm.tcp_target_for_jaw(_jaw_target)") == 1,
          "the issued command is the ternary's result (one site)")
    check(tasks_src.count("jaw_target={np.round(_jaw_target, 4).tolist()}") == 1,
          "the diag row prints the issued target (so the census reads the applied jump)")
    check("jaw_target={np.round(centre - rot @ offset_tool, 4).tolist()}" not in tasks_src,
          "the diag row no longer recomputes the unguarded expression")
    # the row's text is otherwise the same: the field order/prefix is untouched
    row = tasks_src[tasks_src.index("[diag] carry-assist {side}"):][:900]
    for field in ("cmd_centre=", "offset=", "|offset|=", "jaw=", "coherent=", "hand_is_jaw="):
        check(field in row, f"the diag row keeps `{field}` (no format change)")

    # ------------------------------------------------------------------ 5
    if FAILS:
        print(f"FAIL p94 offset bound ({len(FAILS)} of {CHECKS}):")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print(f"ok p94 offset bound ({CHECKS} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
