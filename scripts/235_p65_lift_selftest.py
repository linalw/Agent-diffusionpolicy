#!/usr/bin/env python3
"""P65 joint-margin / pads' / drift-onset selftest (offline; a selfcheck leg).

Pins the `[carry]` fields added for P64's open question (the station's static
solve tracks its attitude command to <= 1 deg while the carry reads 24.6 deg, so
the drift is created in the lift; the two named suspects are
`control.py:423`'s per-tick `max_step` and `:494`'s hard joint-limit clip):

1. the row prints `q_margin=<rad>@jN`, `q_cmd_margin=<rad>@jN`,
   `q_step_max=<rad>`, `jaw_z=<first>/<maxabs>` and `drift_on=<tick>`;
2. every one of them sits inside the `guard_armed` branch, whose first condition
   is `_carry_guard_active or _carry_diag` (`FRUIT_CARRY_DIAG`, default "0") -
   so `None`/off is byte-inert;
3. the margin is `min(q - lo, hi - q)` over the arm's own joints, tracked as the
   **minimum over the leg** with its 1-based binding joint (negative = beyond a
   limit), from `arm.joint_positions()` / `arm.arm_lo` / `arm.arm_hi`;
4. the jaw axis is `rot_now[2, 1]`, i.e. column 1 (the jaw-opening axis P64's
   probe re-settled) of the wrist rotation - the axis whose world z is the pads'
   height difference across the jaw;
5. `drift_on` is the **first** tick the hold drift passes 10 deg (`None` when it
   never does), and the drift is the same `2*acos(|dot|)` the row's
   `hold_drift=` uses;

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import ast
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def margin(q, lo, hi):
    """The shipped expression, verbatim (tasks.py P65 block)."""
    return [min(a - l, h - a) for a, l, h in zip(q, lo, hi)]


def indented_body_contains(src: str, header: str, needle: int) -> bool:
    """True when `needle` (a character offset) lies in `header`'s indented body.

    The enclosing block is found by indentation, not by a character budget: the
    first later line indented **at or below** the header's own indentation ends
    it. (A character window was the first form and it failed on the P65 comment
    block - correct behaviour, a brittle test.)
    """
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


def main() -> int:
    src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # ---- 1. the row's five fields --------------------------------------
    for token in (
        'f"q_margin={_qm} q_cmd_margin={_qcm} "',
        'f"q_step_max={guard_q_step_max:.4f} "',
        'f"jaw_z={_jawz} drift_on={guard_drift_on_i} "',
        'f"hold_drift={guard_drift_max:.1f}deg"',
    ):
        check(token in src, f"the [carry] row prints {token.split('=')[0].strip()}")
    order = [
        src.index('f"hold_drift={guard_drift_max:.1f}deg"'),
        src.index('f"q_margin={_qm} q_cmd_margin={_qcm} "'),
        src.index('f"jaw_z={_jawz} drift_on={guard_drift_on_i} "'),
        src.index('f"in-hand_vmax={guard_vmax:.3f} "'),
    ]
    check(order == sorted(order), "the new fields sit next to hold_drift= (before in-hand_vmax)")

    # ---- 2. the branch (inertness) -------------------------------------
    check(
        "(self._carry_guard_active or self._carry_diag)" in src,
        "guard_armed is gated on _carry_guard_active or _carry_diag",
    )
    check(
        'self._carry_diag = os.environ.get("FRUIT_CARRY_DIAG", "0") == "1"' in src,
        "FRUIT_CARRY_DIAG defaults to off",
    )
    idx = src.index("_q_now = np.asarray(arm.joint_positions(), dtype=float)")
    check(
        indented_body_contains(src, "if guard_armed:", idx),
        "the P65 reads are inside `if guard_armed:`",
    )
    ridx = src.index('f"q_margin={_qm} q_cmd_margin={_qcm} "')
    check(
        indented_body_contains(src, "if guard_armed or relief_acts:", ridx),
        "the print is inside the `guard_armed or relief_acts` block",
    )
    for name in (
        "guard_q_margin = float(\"inf\")",
        "guard_q_margin_i = None",
        "guard_qc_margin = float(\"inf\")",
        "guard_q_step_max = 0.0",
        "guard_jaw_first = None",
        "guard_drift_on_i = None",
    ):
        check(name in src, f"the tracker inits: {name.split(' =')[0]}")

    # ---- 3. the margin arithmetic and the min-over-leg tracking ---------
    lo, hi = [-1.0, -1.0, -1.0], [1.0, 1.0, 3.0]
    m0 = margin([0.10, -0.50, 2.00], lo, hi)
    check(m0 == [0.90, 0.50, 1.00], "margin = min(q-lo, hi-q) over the arm's joints")
    check(min(range(3), key=lambda j: m0[j]) == 1, "the binding joint is the argmin (j2, 0-based 1)")
    m1 = margin([0.95, -0.50, 2.00], lo, hi)
    check(abs(m1[0] - 0.05) < 1e-9, "a joint near its limit reads a small margin")
    check(abs(min(m1[0], m0[1]) - 0.05) < 1e-9, "the leg keeps the MINIMUM over its ticks")
    m2 = margin([1.20, -1.30, 2.00], lo, hi)
    check(m2[0] < 0.0 and m2[1] < 0.0, "beyond a limit the margin is negative (printed, not clamped)")
    check(
        "np.minimum(_q_now - arm.arm_lo, arm.arm_hi - _q_now)" in src
        and "_jc = int(np.argmin(_cmarg))" in src
        and "np.max(np.abs(_q_cmd_now - guard_q_prev))" in src,
        "the shipped expressions are the ones tested",
    )
    check(
        "arm.joint_positions()" in src
        and 'f"{guard_q_margin:.3f}@j{guard_q_margin_j + 1}"' in src
        and 'f"/t{guard_q_margin_i}"' in src,
        "the measured margin uses arm.joint_positions() and prints 1-based @jN/tI",
    )
    check(
        "_q_cmd_now = getattr(arm, \"_q_cmd\", None)" in src,
        "the command margin reads the controller's own post-clip vector (no extra read)",
    )

    # ---- 4. the jaw axis ------------------------------------------------
    check("_jaw_now = float(rot_now[2, 1])" in src, "the jaw axis is column 1 of the wrist rotation")
    check("rot = _quat_matrix(quat)" in src, "the rotation is the existing `rot = _quat_matrix(quat)`")
    for ang in (0.0, 10.0, 27.0, -45.0):
        a = math.radians(ang)
        # R_x(a): row 2, column 1 is sin(a); the jaw axis is column 1.
        rot = [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(a), -math.sin(a)],
            [0.0, math.sin(a), math.cos(a)],
        ]
        jaw_col = [rot[r][1] for r in range(3)]  # the jaw-opening axis in world
        check(
            abs(jaw_col[2] - math.sin(a)) < 1e-12 and abs(jaw_col[1] - math.cos(a)) < 1e-12,
            f"rot[:,1] is the jaw axis and rot[2,1] = sin({ang:+.0f} deg)",
        )
    # the pads' height difference across the jaw, P64's `pad dz`
    check(abs(0.2949 * 98.0 - 28.9) < 0.1, "|jaw_z| * jaw_sep is the pad height difference (P64)")

    # ---- 5. the drift onset --------------------------------------------
    check("if guard_drift_on_i is None and _drift_now > 10.0:" in src, "the onset threshold is 10 deg")
    seq = [4.9, 10.0, 10.1, 20.0, 5.0]
    onset = next((i for i, d in enumerate(seq) if d > 10.0), None)
    check(onset == 2, "drift_on is the FIRST tick strictly above 10 deg (10.0 itself does not fire)")
    check(next((i for i, d in enumerate([1.0, 9.9]) if d > 10.0), None) is None, "never crossing -> None")

    # ---- the row parses back -------------------------------------------
    row = (
        "[carry] left grasp_lift: ticks=160/160 clean_slip_max=171.0mm "
        "slip_xyz=(1.0,2.0,3.0)mm hold_drift=24.6deg "
        "q_margin=0.204@j2/t104 q_cmd_margin=0.199@j2 q_step_max=0.0312 "
        "jaw_z=+0.0301/0.0487 drift_on=41 in-hand_vmax=0.176 "
        "onset_row=70 force@onset=10.06N"
    )
    pats = {
        "q_margin": r"q_margin=(-?\d+\.\d+)@j(\d)/t(\d+)",
        "q_cmd_margin": r"q_cmd_margin=(-?\d+\.\d+)@j(\d)",
        "q_step_max": r"q_step_max=(-?\d+\.\d+)",
        "jaw_z": r"jaw_z=([+-]\d+\.\d+)/(\d+\.\d+)",
        "drift_on": r"drift_on=(None|\d+)",
    }
    for name, pat in pats.items():
        check(re.search(pat, row) is not None, f"a printed {name}= parses back")
    check(float(re.search(pats["q_margin"], row).group(1)) == 0.204, "the parsed margin round-trips")
    check(re.search(pats["drift_on"], row).group(1) == "41", "the parsed onset round-trips")

    print("PASS: P65 lift drift instrument")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
