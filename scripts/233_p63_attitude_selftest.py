#!/usr/bin/env python3
"""P63 commanded-vs-achieved attitude selftest (offline; a selfcheck leg).

Pins the `hold_drift=` readout added for P62's finding (the left is *commanded*
the top-down attitude and still *achieves* 26.3-28.7 deg of tilt):

1. the `[carry]` row prints `hold_drift=<deg>` next to `slip_xyz`;
2. the drift is `2*acos(|dot(hold_quaternion, tcp_quat)|)` in degrees - the same
   quantity `control.quaternion_error` derives its angle from (w, x, y, z);
3. a leg with no `hold_quaternion` prints the `(no-hold)` marker rather than a
   silent zero;
4. the read is inside the guard/diag branch (`FRUIT_CARRY_DIAG`, default off).

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


def main() -> int:
    src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")

    check('f"hold_drift={guard_drift_max:.1f}deg"' in src,
          "the [carry] row prints hold_drift=<deg>")
    check("2.0 * np.degrees(np.arccos(float(np.clip(_dot, 0.0, 1.0))))" in src,
          "the drift is 2*acos(|dot|) in degrees")
    check("(no-hold)" in src, "a leg without a hold prints (no-hold)")
    check("guard_hold_seen = 1" in src, "the hold's presence is tracked")

    # the arithmetic: identical quaternions -> 0 deg, a known tilt -> that angle
    for ang in (0.0, 10.0, 27.0, 90.0):
        half = math.radians(ang) / 2.0
        q1 = (math.cos(half), math.sin(half), 0.0, 0.0)
        q2 = (1.0, 0.0, 0.0, 0.0)
        dot = abs(sum(a * b for a, b in zip(q1, q2)))
        got = 2.0 * math.degrees(math.acos(min(1.0, dot)))
        check(abs(got - ang) < 1e-6, f"{ang:.0f} deg round-trips ({got:.3f})")

    idx = src.index("guard_drift_max = max(")
    branch = src.rfind("if guard_armed:", 0, idx)
    check(branch != -1 and idx - branch < 3000,
          "the read is inside the guard_armed (diag/guard) branch")

    print("PASS: P63 attitude drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
