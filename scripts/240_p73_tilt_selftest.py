#!/usr/bin/env python3
"""P73 rotation-schedule selftest (offline; a selfcheck leg).

Pins the `[carry]` row's six P73 fields - the **rotation schedule** the place-leg
question needs (`logs/p73/PREREG.md` §3): `tilt0=`, `tilt_end=`, `tilt_max=`,
`t45=`, `t75=`, `tilt_rate=`.

Why the schedule and not the endpoint: the leg-end `[attitude]` tilt is
**saturated by the place pose** - 80.8-94.6 deg across both the placed and the
lost legs of the P71 corpus, and the right reaches it too - so it cannot be the
mediator. What can is *when* and *how fast* the wrist turns.

What the leg checks:

1. the six fields print, in order, between `jaw_z=` and `drift_on=`;
2. they live inside the existing `if guard_armed:` block, whose first condition
   is `_carry_guard_active or _carry_diag` (`FRUIT_CARRY_DIAG`, default "0") -
   so with the knob unset nothing runs (byte-inert);
3. the tilt is `acos(-rot[2,2])`, i.e. **the same expression** `[attitude]`
   prints, so the two instruments are comparable and the leg-end value can be
   cross-checked;
4. the accumulation adds **no articulation read**: no `tcp_pose()` /
   `joint_positions()` call appears in the P73 block (`rot_now` is the block's
   own read for `clean_slip`);
5. the arithmetic: first tick at/above 45 and 75 deg, the max, the signed
   per-tick step and its tick, on a synthetic sequence;
6. a printed row parses back (the report's own reader).

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import math
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


def tilt_of(rot) -> float:
    """`acos(-rot[2][2])` in degrees - the `[attitude]` expression, verbatim."""
    return math.degrees(math.acos(max(-1.0, min(1.0, -float(rot[2][2])))))


def schedule(tilts: list[float]) -> dict:
    """The P73 accumulation, verbatim, on a per-tick tilt sequence."""
    first = None
    prev = None
    tmax = 0.0
    t45 = None
    t75 = None
    rate = 0.0
    rate_i = None
    end = None
    for i, tilt in enumerate(tilts):
        if first is None:
            first = tilt
        else:
            dtilt = tilt - float(prev)
            if abs(dtilt) > abs(rate):
                rate = dtilt
                rate_i = i
        prev = tilt
        if t45 is None and tilt >= 45.0:
            t45 = i
        if t75 is None and tilt >= 75.0:
            t75 = i
        tmax = max(tmax, tilt)
        end = tilt
    return {
        "tilt0": first,
        "tilt_end": end,
        "tilt_max": tmax,
        "t45": t45,
        "t75": t75,
        "rate": rate,
        "rate_i": rate_i,
    }


def main() -> int:
    src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")

    # ---- 1. the fields, in order, on the row ---------------------------
    check(
        'f"jaw_z={_jawz} {_tilt_sched} drift_on={guard_drift_on_i} "' in src,
        "the row prints {_tilt_sched} between jaw_z= and drift_on=",
    )
    for token in (
        'f"tilt0={guard_tilt_first:.1f} tilt_end={guard_tilt_end:.1f} "',
        'f"tilt_max={guard_tilt_max:.1f} t45={_t45} t75={_t75} "',
        'f"tilt_rate={_trate}"',
    ):
        check(token in src, f"the schedule line prints {token.split('=')[0].replace('f\"', '')}")
    check(
        'tilt0=n/a tilt_end=n/a tilt_max=n/a t45=- t75=- tilt_rate=-' in src,
        "an unarmed leg prints the n/a form (the block never ran)",
    )

    # ---- 2. containment (inertness) ------------------------------------
    idx = src.index("_tilt_now = math.degrees(")
    check(
        indented_body_contains(src, "if guard_armed:", idx),
        "the P73 accumulation is inside `if guard_armed:`",
    )
    pidx = src.index('f"jaw_z={_jawz} {_tilt_sched} drift_on={guard_drift_on_i} "')
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

    # ---- 3. the same expression as [attitude] --------------------------
    check(
        "math.acos(max(-1.0, min(1.0, -float(rot_now[2, 2]))))" in src,
        "the tilt is acos(-rot_now[2,2]) on the guarded block's own rotation",
    )
    att = src.index("tilt_rad = math.acos(max(-1.0, min(1.0, -float(tool[2]))))")
    check(
        "tool = rot[:, 2]" in src[att - 200 : att + 200],
        "[attitude] reads the tool axis as rot[:,2] and acos(-tool[2]) - the same number",
    )
    for ang in (0.0, 45.0, 90.0, 135.0):
        # A rotation about world Y by (pi - ang) puts the tool axis (column 2)
        # at (sin ang, 0, -cos ang): ang = 0 is straight down, ang = 90 is
        # horizontal - exactly the place leg's traverse.
        th = math.pi - math.radians(ang)
        rot = [
            [math.cos(th), 0.0, math.sin(th)],
            [0.0, 1.0, 0.0],
            [-math.sin(th), 0.0, math.cos(th)],
        ]
        check(
            abs(rot[2][2] - (-math.cos(math.radians(ang)))) < 1e-12
            and abs(tilt_of(rot) - ang) < 1e-9,
            f"a {ang:.0f} deg tool axis reads back as {ang:.0f} deg",
        )

    # ---- 4. no new articulation read -----------------------------------
    start = src.index("guard_tilt_first = None")
    end = src.index("guard_tilt_rate_i = None")
    block = src[start:end]
    check("tcp_pose()" not in block, "the P73 init adds no pose read")
    start2 = src.index("_tilt_now = math.degrees(")
    end2 = src.index("guard_tilt_end = _tilt_now")
    block2 = src[start2:end2]
    for forbidden in ("tcp_pose()", "joint_positions()", "jaw_centre()", "tactile.read()"):
        check(forbidden not in block2, f"the accumulation calls no {forbidden} - pure arithmetic")

    # ---- 5. the arithmetic ---------------------------------------------
    # A place leg: starts top-down, rotates through 45 and 75 deg, ends ~90.
    seq = [0.0, 5.0, 20.0, 44.9, 45.1, 60.0, 74.9, 75.2, 80.0, 90.0]
    s = schedule(seq)
    check(s["tilt0"] == 0.0, "the first tick is the reference (tilt0)")
    check(s["tilt_end"] == 90.0, "tilt_end is the LAST tick, not the max")
    check(s["tilt_max"] == 90.0, "tilt_max is the max over the leg")
    check(s["t45"] == 4, "t45 latches the FIRST tick at/above 45 deg (44.9 does not fire)")
    check(s["t75"] == 7, "t75 latches the FIRST tick at/above 75 deg (74.9 does not fire)")
    check(
        abs(s["rate"] - 24.9) < 1e-9 and s["rate_i"] == 3,
        "the rate is the signed max per-tick step (0 -> 5 -> 20 -> 44.9: +24.9 at tick 3)",
    )
    flat = schedule([90.0, 90.0, 89.8])
    check(flat["t45"] == 0 and flat["t75"] == 0, "a leg that starts past the thresholds latches tick 0")
    check(abs(flat["rate"] - (-0.2)) < 1e-9, "a falling tilt gives a negative rate")
    never = schedule([10.0, 20.0, 30.0])
    check(never["t45"] is None and never["t75"] is None, "never crossing -> '-' on the row")
    check(
        # a transient above 75 that comes back down leaves tilt_max > tilt_end
        schedule([0.0, 80.0, 40.0])["tilt_max"] == 80.0
        and schedule([0.0, 80.0, 40.0])["tilt_end"] == 40.0,
        "tilt_max and tilt_end are different fields (a transient does not fool tilt_end)",
    )

    # ---- 6. the row parses back ----------------------------------------
    row = (
        "[carry] left place0: ticks=431/431 clean_slip_max=0.0mm "
        "q_step_max=0.0152 jaw_z=+0.0129/0.6413 tilt0=0.0 tilt_end=90.4 "
        "tilt_max=90.4 t45=142 t75=331 tilt_rate=+0.6200/t168 drift_on=None "
        "in-hand_vmax=0.063 clr=+34mm@obelt/t330"
    )
    pats = {
        "tilt0": r"tilt0=(-?\d+\.\d)",
        "tilt_end": r"tilt_end=(-?\d+\.\d)",
        "tilt_max": r"tilt_max=(-?\d+\.\d)",
        "t45": r"t45=(-|\d+)",
        "t75": r"t75=(-|\d+)",
        "tilt_rate": r"tilt_rate=([-+]\d+\.\d+)/t(\d+)",
    }
    for name, pat in pats.items():
        check(re.search(pat, row) is not None, f"a printed {name}= parses back")
    check(float(re.search(pats["tilt_rate"], row).group(1)) == 0.62, "the parsed rate round-trips")
    check(re.search(pats["t45"], row).group(1) == "142", "the parsed t45 round-trips")

    print("PASS: P73 rotation schedule instrument")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
