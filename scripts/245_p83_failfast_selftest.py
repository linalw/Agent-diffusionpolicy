#!/usr/bin/env python3
"""P83 fail-fast selftest (offline; a selfcheck leg).

Pins the shape of `FRUIT_FAIL_FAST=<mm>` - the scripted line's "a lost payload
must not cost a whole attempt" knob - without a simulator and without writing to
the tree.

Why the knob exists: P80 measured the shipped cell at `26.72 s = 4.8 s idle +
1.45 attempts x 15.1 s`, and **every** failure was `grasped, not placed`: the
payload is gone mid-carry while the cell still runs the leg out, the place
transfer, the release block and the return. The abort removes only the ticks
after the loss; the class stays `cnp`.

What this leg checks:

1. `tasks.parse_fail_fast` - the whole resolution table: unset/empty/`0` is
   **off** (the shipped path), `mm >= 100` becomes metres, and every inadmissible
   form raises: non-numeric, negative, `nan`, `inf`, and the `0 < mm < 100` band
   the pre-run corpus census forbids (`logs/p83/census.txt`: the worst leg of 249
   placed attempts reads 76.3 mm, so a lower threshold is not separated from a
   clean leg). The floor is pinned as a literal, not as a comment.
2. The trip test is **one** compare on the tracker's own operand
   (`guard_slip_max >= self.fail_fast_m`), it is gated by a plain bool
   (`self._fail_fast_active`), and it sets the latch **once** and `break`s the
   leg loop - a trip that did not break would save nothing.
3. The latch is **attempt-local** (the two-line runs two attempts on two
   threads) and it is cleared on **every** attempt start, together with the
   per-attempt scope resolution `bool(self.fail_fast_m > 0.0 and scripted)` -
   so the direct/policy handover can never reach it and a stale `True` cannot
   leak into the next attempt.
4. The knob **arms** the W8-B tracker block (`guard_armed`'s disjunction
   contains `_fail_fast_active`), because the trip's operand is computed there;
   with the knob off that block is not armed by it (one bool).
5. The two early-exit sites (the lift boundary and the place boundary) read
   **one** predicate, `_attempt_ended_early()`, which is exactly
   `_carry_monitor_skip or _fail_fast_trip` - so the abort reuses the shipped
   P7-2b fast-skip machinery and cannot fork from it.
6. The abort adds **no failure reason**: the trip path contains no
   `result.notes.append` (the class stays whatever the shipped predicate
   scored), and the `[fail-fast]` row is the only new line, printed once per
   trip.
7. The leg tail the abort skips is restored: `arm.max_step` is put back and a
   live `hold_wrist` is cleared before the early return (an abort must not leak
   a step cap into the next attempt).
8. Off-path inertness: with the threshold at 0 the active flag evaluates False
   for every caller, the trip's first operand short-circuits, and nothing else
   in `tasks.py` reads the knob (`parse_fail_fast` has exactly one call site).

Exit 0 on pass, 1 on the first failure.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

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


def block_after(src: str, needle: str, lines: int = 60) -> str:
    """The source from `needle`'s line to `lines` lines later (indent-scoped use)."""
    i = src.index(needle)
    start = src.rfind("\n", 0, i) + 1
    return "\n".join(src[start:].splitlines()[:lines])


def main() -> int:
    tasks_src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")

    # ------------------------------------------------------------------ 1
    ns: dict = {"os": __import__("os"), "math": math}
    exec(grab(tasks_src, "parse_fail_fast"), ns)  # noqa: S102 - pinned source
    parse = ns["parse_fail_fast"]

    check(parse("") == 0.0, "unset/empty -> 0.0 (off, the shipped path)")
    check(parse("0") == 0.0, "explicit 0 -> off")
    check(parse("0.0") == 0.0, "explicit 0.0 -> off")
    check(parse("  ") == 0.0, "whitespace -> off")
    check(parse("150") == 0.150, "150 mm -> 0.150 m (the registered arm)")
    check(parse("100") == 0.100, "100 mm -> 0.100 m (the floor itself is admissible)")
    check(parse("1000") == 1.0, "1000 mm -> 1.0 m")
    check(abs(parse("150") - 0.15) < 1e-12, "the operand is metres, not millimetres")

    def raises(fn, *a) -> bool:
        try:
            fn(*a)
        except ValueError:
            return True
        except Exception:  # noqa: BLE001
            return False
        return False

    for bad in ("abc", "150mm", "-5", "-0.1", "nan", "inf", "-inf"):
        check(raises(parse, bad), f"parse({bad!r}) raises ValueError")
    for low in ("1", "10", "76.3", "99", "99.9"):
        check(raises(parse, low),
              f"parse({low!r}) raises: 0 < mm < 100 is the refused band")
    parse_src = grab(tasks_src, "parse_fail_fast")
    check("mm < 100.0" in parse_src, "the 100 mm floor is a literal in the resolver")
    check("76.3" in parse_src, "the resolver names the corpus number that sets the floor")
    # the environment is the shipped read, and an explicit raw value wins (testability)
    ns["os"].environ["FRUIT_FAIL_FAST"] = "150"
    check(parse() == 0.150, "unset raw reads FRUIT_FAIL_FAST from the environment")
    check(parse("200") == 0.200, "an explicit raw value wins over the environment")
    del ns["os"].environ["FRUIT_FAIL_FAST"]

    # ------------------------------------------------------------------ 2
    # one trip site, one compare on the tracker's own operand, a break - and the
    # sites' behaviour in the two directions.
    check(tasks_src.count("self._fail_fast_trip = True") == 1,
          "exactly one trip latch site")
    trip = block_after(tasks_src, "self._fail_fast_trip = True", 45)
    _i = tasks_src.index("and not self._fail_fast_trip")
    _line = tasks_src.rfind("\n", 0, _i)
    _prev = tasks_src.rfind("\n", 0, _line)
    around = "\n".join(tasks_src[_prev:].splitlines()[:7])
    check("guard_slip_max >= self.fail_fast_m" in around,
          "the trip compares the tracker's own clean_slip operand to the threshold")
    check("self._fail_fast_active" in around,
          "the trip is gated by the per-attempt scope flag (a plain bool)")
    check("break" in trip, "the trip breaks the leg loop (otherwise it saves nothing)")
    check("notes.append" not in trip,
          "the trip adds no result note (the failure reason must not change)")
    check("<=" not in re.search(r"guard_slip_max >= self\.fail_fast_m", tasks_src).group(0),
          "the comparison is >= (a clean leg at 0.0 mm can never satisfy it)")

    # ------------------------------------------------------------------ 3
    check('_fail_fast_trip = _AttemptLocal("_fail_fast_trip", False)' in tasks_src,
          "the latch is attempt-local (two concurrent attempts in the two-line)")
    check('_fail_fast_info = _AttemptLocal("_fail_fast_info")' in tasks_src,
          "the audit record is attempt-local too")
    check(tasks_src.count("self._fail_fast_trip = False") == 1,
          "the latch is cleared at exactly one site")
    clear = block_after(tasks_src, "self._fail_fast_trip = False", 4)
    check("self._fail_fast_info = None" in clear, "the audit record is cleared with it")
    check("self._fail_fast_active = bool(self.fail_fast_m > 0.0 and scripted)" in
          tasks_src, "the scope is `threshold > 0 and scripted` - one expression")
    # the scope's own truth table (the expression above, evaluated)
    scope = lambda m, scripted: bool(m > 0.0 and scripted)
    check(scope(0.0, True) is False, "threshold 0 -> off on the scripted line")
    check(scope(0.15, False) is False, "any threshold -> off on the direct/hybrid path")
    check(scope(0.15, True) is True, "150 mm + scripted -> armed")
    check(scope(-1.0, True) is False, "a negative threshold is inert rather than armed")
    check("parse_fail_fast()" in tasks_src, "the task resolves the knob once")
    check(tasks_src.count("parse_fail_fast()") == 1,
          "exactly one call site: no code path can read the knob again")

    # ------------------------------------------------------------------ 4
    armed = block_after(tasks_src, "guard_armed = bool(", 8)
    check("self._fail_fast_active" in armed,
          "the knob arms the W8-B tracker block (the trip's operand lives there)")
    check("or self._place_onset_trace > 0" in armed,
          "the P75 trace's own arming clause is untouched")

    # ------------------------------------------------------------------ 5
    pred = grab(tasks_src, "_attempt_ended_early")
    check("self._carry_monitor_skip or self._fail_fast_trip" in pred,
          "one predicate: the P7-2b monitor skip OR the P83 trip")
    check(tasks_src.count("if self._attempt_ended_early():") == 2,
          "the two early-exit sites (lift boundary, place boundary) both read it")
    check(tasks_src.count("self._carry_monitor_skip") >= 3,
          "the monitor's own latch is still read where it was")

    # ------------------------------------------------------------------ 6
    ff_rows = tasks_src.count('f"[fail-fast]')
    check(ff_rows == 1, f"exactly one [fail-fast] row site (found {ff_rows})")
    check('say(self._fail_fast_text())' in tasks_src,
          "the row is printed AT the trip (inside the tick loop), not at the leg tail")
    check("_fail_fast_text" in tasks_src and tasks_src.count("def _fail_fast_text") == 1,
          "one formatter for the row")
    _row_start = tasks_src.index('f"[fail-fast] {info.get(')
    _row_begin = tasks_src.rfind("\n", 0, _row_start)
    row = "\n".join(tasks_src[_row_begin:].splitlines()[:22])
    for field in ("trip=t", "clean_slip=", "sep=", "gap=", "force=", "force_min=",
                  "contacts=", "onset_row=", "loss_row=", "leg_left="):
        check(field in row, f"the audit row carries {field}")
    check("notes" not in row, "the row does not touch result.notes")

    # ------------------------------------------------------------------ 7
    tail = block_after(tasks_src, "if self._fail_fast_trip:\n", 40)
    check("arm.max_step = previous_carry_step" in tail,
          "the abort restores the carry step cap")
    check("arm.hold_quaternion = None" in tail or "hold_wrist" in tail,
          "the abort clears a live wrist hold")

    # ------------------------------------------------------------------ 8
    check(tasks_src.count("self.fail_fast_m") >= 2,
          "the threshold is stored once and read at the trip")
    knob = block_after(tasks_src, "FRUIT_FAIL_FAST", 2)
    check("FRUIT_FAIL_FAST" in knob, "the knob name is the registered one")
    check("self.fail_fast_m = parse_fail_fast()" in tasks_src,
          "the task stores the resolved metres (0.0 = off)")

    if FAILS:
        print(f"[p83-selftest] FAIL {len(FAILS)} of {CHECKS} checks")
        for msg in FAILS:
            print(f"  - {msg}")
        return 1
    print(f"[p83-selftest] PASS {CHECKS} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
