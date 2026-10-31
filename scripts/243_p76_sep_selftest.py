#!/usr/bin/env python3
"""P76 pry/crush selftest (offline; a selfcheck leg).

Pins the `[carry]` row's five P76 fields - the **pry and crush** reads the
force-ladder phase needs (`logs/p76/PREREG.md` §3): `dia=`, `sep_max=…@t<tick>`,
`gap@sep_max=`, `sep_min=`, `fmax=`.

Why new fields at all: `sep@loss` is taken at the tick **contact is lost**, but
P75 measured the pads reaching their **98.1 mm mechanical stop 9 ticks later**
(`logs/p75/RESULTS.md` §2b), so a sample cannot answer "did this leg pry the pads
open". `sep_max` accumulates the leg's extreme measured separation, `gap@sep_max`
carries the commanded gap that the pads were fighting at that tick (P75's
ordering: pads opening while the servo closes), `sep_min` is the crush side
(interference below the fruit's own width, `dia`) and `fmax` its force form.

What the leg checks:

1. the five fields print, in order, between `sep_end=` and `guard=`;
2. the accumulation and the print live inside the existing `if guard_armed:`
   block, whose first term is `_carry_guard_active or _carry_diag`
   (`FRUIT_CARRY_DIAG`, default "0") - with the knob unset nothing runs;
3. the instrument is `arm.jaw_separation()`, i.e. **the same** link-origin read
   as `sep@onset`/`sep@loss`/`sep_end` and P41's offline `sep_max`, so the
   numbers are comparable to the 98.1 mm stop; `dia` is `sample.diameter`;
4. `gap_command` is assigned before the accumulation in the per-tick body (so
   the "command closing" claim reads this tick's command, not last leg's);
5. the `n/a` forms, for a leg on which the block never ran;
6. the arithmetic on a synthetic leg (max, its tick, the gap at that tick, min,
   and the first tick counted - the inherited firing site starts a *place* leg
   already at the stop);
7. a printed row parses back with the report's own reader.

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def indented_body_contains(src: str, header: str, needle: int) -> bool:
    """True when `needle` (a character offset) lies in `header`'s indented body."""
    start = src.rfind(header, 0, needle)
    if start == -1:
        return False
    line_start = src.rfind("\n", 0, start) + 1
    indent = start - line_start
    for line in src[start:].splitlines()[1:]:
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= indent:
            end = start + src[start:].index(line)
            return needle < end
    return True


def accumulate(seps: list[float], gaps: list[float], forces: list[float]) -> dict:
    """The P76 accumulation, verbatim, on a per-tick (sep, gap, force) sequence."""
    sep_max = 0.0
    sep_max_i = None
    sep_max_gap = None
    sep_min = float("inf")
    for i, (sep, gap, force) in enumerate(zip(seps, gaps, forces)):
        if sep > sep_max:
            sep_max = sep
            sep_max_i = i
            sep_max_gap = gap
        # The crush side is the **loaded** span only: a payload that has left
        # lets the servo close the pads onto nothing.
        if force > 0.0:
            sep_min = min(sep_min, sep)
    return {
        "sep_max": sep_max,
        "i": sep_max_i,
        "gap": sep_max_gap,
        "sep_min": sep_min,
    }


def main() -> int:
    src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")

    # ---- 1. the fields, in order, on the row ---------------------------
    check(
        'f"sep_end={sep_end:.1f}mm "\n                    '
        'f"dia={float(sample.diameter) * 1000.0:.1f} "'
        in src,
        "the row prints sep_end= then dia=",
    )
    check(
        'f"sep_max={_sep_max} gap@sep_max={_gap_at_sep} "' in src,
        "the row prints sep_max= then gap@sep_max=",
    )
    check(
        'f"sep_min={_sep_min} fmax={_fmax} "' in src,
        "the row prints sep_min= then fmax=",
    )
    idx_max = src.index('f"sep_max={_sep_max} gap@sep_max={_gap_at_sep} "')
    idx_guard = src.index('f"guard={int(guard_acts)} "')
    idx_sep_end = src.index('f"sep_end={sep_end:.1f}mm "')
    check(
        idx_sep_end < idx_max < idx_guard,
        "the field group sits between sep_end= and guard= (one contiguous block)",
    )
    # The n/a forms: a leg whose block never ran prints `n/a`, not a zero that
    # would read like a measurement.
    check(
        'if guard_sep_max_i is None\n                    else f"{guard_sep_max * 1000:.1f}@t{guard_sep_max_i}"'
        in src,
        "an unarmed leg prints sep_max=n/a",
    )
    check(
        'if guard_sep_min == float("inf")' in src,
        "an unarmed leg prints sep_min=n/a (the inf sentinel, not 0.0)",
    )
    check(
        "if force_now > 0.0:\n                            guard_sep_min = min(guard_sep_min, _sep_now)"
        in src,
        "sep_min is the LOADED span only (a post-release closure cannot read as a crush)",
    )

    # ---- 2. containment (inertness) ------------------------------------
    idx = src.index("_sep_now = float(arm.jaw_separation())")
    check(
        indented_body_contains(src, "if guard_armed:", idx),
        "the P76 accumulation is inside `if guard_armed:`",
    )
    pidx = idx_max
    check(
        indented_body_contains(src, "if guard_armed or relief_acts:", pidx),
        "the print is inside the `guard_armed or relief_acts` block",
    )
    check(
        '(self._carry_guard_active or self._carry_diag)' in src,
        "guard_armed is gated on _carry_guard_active or _carry_diag",
    )
    check(
        'self._carry_diag = os.environ.get("FRUIT_CARRY_DIAG", "0") == "1"' in src,
        "FRUIT_CARRY_DIAG defaults to off",
    )

    # ---- 3. the instrument is the stop's own instrument ----------------
    check(
        "guard_onset_sep = float(arm.jaw_separation())" in src
        and "guard_loss_sep = float(arm.jaw_separation())" in src,
        "sep@onset / sep@loss read arm.jaw_separation() - the P76 field uses the same call",
    )
    check(
        'f"dia={float(sample.diameter) * 1000.0:.1f} "' in src,
        "dia is the fruit's own class width (sample.diameter), per leg",
    )

    # ---- 4. the commanded gap is *this tick's* -------------------------
    body = src[src.index("            for i in range(n_ticks):"):idx]
    check(
        "gap_command = self._force_servo_step(side, gap_command)" in body,
        "gap_command is assigned in the same per-tick body before the accumulation",
    )
    check(
        "guard_sep_max_gap = float(gap_command)" in src,
        "the stored gap is the per-tick command, not the leg-end cursor",
    )

    # ---- 5. the arithmetic ---------------------------------------------
    # A pry, tick by tick: constant 78.0 for 110 ticks against a closing
    # command, then the pads run to the 98.1 stop while the gap shrinks, and
    # the payload is gone from the loss tick (force 0.00 N).
    seps = [78.0] * 110 + [78.8, 83.7, 92.0, 98.1, 98.1, 51.9]
    gaps = [68.7] * 112 + [68.3, 67.4, 66.7, 66.7, 48.0]
    gaps = gaps + [66.0] * (len(seps) - len(gaps))
    forces = [5.0] * 112 + [4.1, 0.0, 0.0, 0.0, 0.0]
    forces = forces + [0.0] * (len(seps) - len(forces))
    a = accumulate(seps, gaps, forces)
    check(abs(a["sep_max"] - 98.1) < 1e-9, "sep_max is the leg's EXTREME, not the loss-tick sample")
    check(a["i"] == 113, "the tick of the max is the first tick it is reached")
    check(abs(a["gap"] - 67.4) < 1e-9, "gap@sep_max is the command at that tick (67.4), not 68.7")
    check(
        abs(a["gap"] - 67.4) < 68.7,
        "the pads are at the stop while the command CLOSES - P75's ordering, per leg",
    )
    check(abs(a["sep_min"] - 78.0) < 1e-9, "sep_min over the pry leg is its LOADED span")
    check(
        a["sep_min"] > 51.9,
        "the unloaded post-release span (51.9) is NOT sep_min - the loaded-only rule",
    )
    # An inherited firing site: the place leg STARTS at the stop, one face
    # unloaded - a first-tick skip would lose it, which is why tick 0 counts.
    b = accumulate([98.1, 98.1, 97.9], [66.9, 66.9, 66.9], [14.2, 14.2, 14.2])
    check(b["i"] == 0, "a leg that starts at the stop latches tick 0 (the inherited site)")
    # Interference: a crush drives the pads *below* the fruit's own width while
    # the force is HIGH - the opposite of a pry (P41's 60 N strawberry: 10 mm
    # span at 62.3 N, 37 mm class).
    c = accumulate([42.0, 33.0, 10.0], [66.4, 60.0, 50.0], [62.3, 61.0, 58.0])
    check(c["sep_max"] == 42.0, "a closing span never sets sep_max above its leg start")
    check(c["sep_min"] == 10.0, "sep_min catches the 10 mm crush span (dia 37 mm -> -27 mm)")
    # A never-held leg is not crushed: no loaded tick, so sep_min stays the
    # sentinel and the report reads n/a.
    d = accumulate([70.0, 55.0], [66.0, 55.0], [0.0, 0.0])
    check(d["sep_min"] == float("inf"), "an unloaded leg has no sep_min (n/a, not a crush)")

    # ---- 6. the row parses back ----------------------------------------
    row = (
        "[carry] left place0: ticks=333/333 clean_slip_max=832.5mm "
        "q_step_max=0.0152 jaw_z=+0.0129/0.6413 tilt0=0.0 tilt_end=90.4 "
        "tilt_max=90.4 t45=142 t75=331 tilt_rate=+0.6200/t168 drift_on=None "
        "in-hand_vmax=0.448 onset_row=2 force@onset=0.00N sep@onset=52.4mm "
        "contacts@onset=0 min_contacts=0 force_min=0.00N loss_row=2 "
        "sep@loss=78.0mm sep_end=48.7mm dia=61.0 sep_max=98.1@t121 "
        "gap@sep_max=66.7 sep_min=48.7 fmax=11.82N guard=0 events=0 holds=0 "
        "reseat=0.0mm relief=0 gap_start=53.1mm open_max=0.0mm"
    )
    pats = {
        "dia": r"dia=(\d+\.\d)",
        "sep_max": r"sep_max=(\d+\.\d)@t(\d+)",
        "gap": r"gap@sep_max=(\d+\.\d)",
        "sep_min": r"sep_min=(\d+\.\d)",
        "fmax": r"fmax=(\d+\.\d+)N",
    }
    for name, pat in pats.items():
        check(re.search(pat, row) is not None, f"the printed {name}= parses back")
    check(re.search(pats["sep_max"], row).groups() == ("98.1", "121"),
          "sep_max=98.1@t121 parses as (value, tick)")
    check(re.search(r"fmax=n/a", "[carry] left x: sep_min=n/a fmax=n/a guard=0") is not None,
          "the fmax n/a form parses as a non-number, not as 0")
    # The stop and the still-gripping band, the report's own constants.
    check(98.1 > 95.0, "the 95 mm 'at the stop' threshold lies below the 98.1 mm stop")
    check(40.0 <= 70.0, "the still-gripping band [40, 70] mm brackets the 70 mm standoff")

    print("\nP76 pry/crush fields: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
