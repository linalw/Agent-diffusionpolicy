#!/usr/bin/env python3
"""P61 slip-direction selftest (offline; a `scripts/selfcheck.sh` leg).

Pins the **direction-resolved** carry-slip instrument added for P60's open
question (why the left arm's payload leaves at a 47x rate on the same hand):

1. the `[carry]` row prints `slip_xyz=(x,y,z)mm` next to `clean_slip_max`;
2. the vector is captured **at the maximum** (the code stores it only when the
   running norm grows), so the identity `|slip_xyz| == clean_slip_max` holds to
   the print's 0.1 mm - checked here on the arithmetic, and live by the P61 cell;
3. the capture is inside the `guard_armed` (diag/guard) branch, so it costs
   nothing on a shipped run (`FRUIT_CARRY_DIAG` default off);
4. the vector is in the **leg's own frame** (`rel_frame - guard_ref`), the same
   frame `clean_slip_max` uses.

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def indented_body_contains(src: str, header: str, needle: int) -> bool:
    """True when `needle` (a character offset) lies in `header`'s indented body.

    Structural, not a character budget: the first later line indented **at or
    below** the header's own indentation ends the block. (P66 phase 2 replaced
    the original `idx - branch < 2500` window with this - the guarded branch grew
    two legitimate instrument blocks and the window became a false failure; the
    `235` leg already made the same correction, `logs/p66/P2_RESULTS.md`.)
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

    check('f"slip_xyz=({guard_slip_at_max[0] * 1000:.1f},"' in src,
          "the [carry] row prints slip_xyz=(x,y,z)mm")
    check("guard_slip_at_max = _slip_vec.copy()" in src,
          "the vector is captured when the running maximum grows")
    check("_slip_vec = rel_frame - guard_ref" in src,
          "the vector is the same framed quantity clean_slip_max norms")
    check("guard_slip_at_max = np.zeros(3, dtype=float)" in src,
          "the vector is initialised (a leg with no slip prints zeros)")

    # the identity, on the arithmetic the code uses
    for vec in ((0.171, 0.0, 0.0), (0.0, -0.121, 0.0), (0.03, -0.16, 0.05)):
        norm_mm = math.dist((0.0, 0.0, 0.0), vec) * 1000.0
        printed = f"({vec[0] * 1000:.1f},{vec[1] * 1000:.1f},{vec[2] * 1000:.1f})mm"
        body = printed[:-2] if printed.endswith("mm") else printed
        parts = [float(x) for x in body.strip("()").split(",")]
        check(abs(math.dist((0.0, 0.0, 0.0), parts) - norm_mm) <= 0.1,
              f"|slip_xyz| == clean_slip_max to 0.1 mm for {vec}")

    # 3: the capture lives in the diag/guard branch and the knob is default off
    idx = src.index("guard_slip_at_max = _slip_vec.copy()")
    check(indented_body_contains(src, "if guard_armed:", idx),
          "the capture is inside the guard_armed (diag/guard) branch")
    diag_default = 'os.environ.get("FRUIT_CARRY_DIAG", "0")' in src
    check(diag_default, 'FRUIT_CARRY_DIAG still defaults to "0" (off)')

    print("PASS: P61 slip direction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
