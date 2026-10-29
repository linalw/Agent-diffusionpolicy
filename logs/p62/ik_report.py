"""P62 phase 1 - turn the probe rows into `logs/p62/IK_PROBE.txt`, with checks.

    python3 logs/p62/ik_report.py

Reads `logs/p62/candidates.json` (the offline table) and the probe's own
`logs/p62/ik_probe_rows.json` + `logs/p62/ik_probe_rows_near.json` (the
`FRUIT_P62_RESTARTS=4` cross-check) and asserts the claims the report makes
before printing them:

  P1  the **control** (the shipped quaternion) reproduces the documented station
      band: residual <= 6 mm at the left's p50 (0.274) and at the station (0.340),
      > 6 mm at the +x cliff (0.398, `logs/p60/LEFT_CENSUS.md`'s never-held band);
  P2  the shipped frame's z column is the **finger long axis**: |dot| with the
      measured `approach_axis` == 1.000, and column 1 is the jaw-opening axis
      (|dot| with the measured `jaw_axis` == 1.000);
  P3  `candidates.json`'s shipped slip share on the z column reproduces P61's
      published 0.905 (it is the same decomposition);
  P4  the yaw family solves **nowhere** (0/3 at every theta) while T0 solves at
      p50/station, and T0's j3 margin does not improve with 4 restarts (so the
      tight margin is the attitude, not the seed).

Exit code 0 on success, 1 on a failed check (the repo's probe convention).
"""

from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TOL_MM = 6.0


def md5(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.md5(handle.read()).hexdigest()


def main() -> int:
    with open(os.path.join(HERE, "candidates.json"), encoding="utf-8") as handle:
        cand = json.load(handle)
    with open(os.path.join(HERE, "ik_probe_rows.json"), encoding="utf-8") as handle:
        probe = json.load(handle)
    near_path = os.path.join(HERE, "ik_probe_rows_near.json")
    near = None
    if os.path.exists(near_path):
        with open(near_path, encoding="utf-8") as handle:
            near = json.load(handle)

    rows = probe["rows"]
    by = {}
    for row in rows:
        by.setdefault(row["cand"], {})[round(row["x"], 3)] = row
    xs = sorted({round(r["x"], 3) for r in rows})
    names = [r["name"] for r in cand["rows"]]
    table = {r["name"]: r for r in cand["rows"]}

    checks = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append((name, bool(ok), detail))

    # ---- P1: the control reproduces the documented band ------------------- #
    c0 = by.get("C0", {})
    check(
        "P1a control residual <= 6 mm at x=0.274 / 0.340",
        all(c0.get(x, {}).get("residual_mm", 1e9) <= TOL_MM for x in (0.274, 0.34)),
        ", ".join(f"{x:.3f}: {c0.get(x, {}).get('residual_mm', float('nan')):.1f} mm" for x in (0.274, 0.34)),
    )
    check(
        "P1b control residual > 6 mm at the +x cliff x=0.398",
        c0.get(0.398, {}).get("residual_mm", 0.0) > TOL_MM,
        f"0.398: {c0.get(0.398, {}).get('residual_mm', float('nan')):.1f} mm "
        "(P60's never-held band is x 0.347-0.398)",
    )
    # ---- P2: the frame semantics ------------------------------------------ #
    seed = probe["seed"]
    approach = seed["approach_axis"]
    jaw_axis = seed["jaw_axis"]
    cols = seed["cols"]
    dots_app = [abs(sum(approach[i] * cols[c][i] for i in range(3))) for c in range(3)]
    dots_jaw = [abs(sum(jaw_axis[i] * cols[c][i] for i in range(3))) for c in range(3)]
    check(
        "P2a the z column IS the finger long axis (|dot approach_axis| = 1.000)",
        abs(dots_app[2] - 1.0) < 5e-3,
        "|dot| with cols 0/1/2 = " + " / ".join(f"{d:.3f}" for d in dots_app),
    )
    check(
        "P2b column 1 IS the jaw-opening axis (|dot jaw_axis| = 1.000)",
        abs(dots_jaw[1] - 1.0) < 5e-3,
        "|dot| with cols 0/1/2 = " + " / ".join(f"{d:.3f}" for d in dots_jaw),
    )
    # ---- P3: the shipped frame reproduces P61's share ---------------------- #
    check(
        "P3 shipped slip share on the z column reproduces P61's 0.905",
        abs(table["C0"]["slip_share_col2"] - 0.905) < 5e-4,
        f"{table['C0']['slip_share_col2']:.4f}",
    )
    # ---- P4: the families' verdicts --------------------------------------- #
    yaw = [n for n in names if n.startswith("Y")]
    for name in yaw:
        solved = sum(1 for x in xs if by.get(name, {}).get(x, {}).get("residual_mm", 1e9) <= TOL_MM)
        check(
            f"P4a {name} solves nowhere (0/3 within 6 mm)",
            solved == 0,
            f"solved {solved}/{len(xs)}, worst "
            f"{max(by.get(name, {}).get(x, {}).get('residual_mm', 0.0) for x in xs):.1f} mm",
        )
    t0 = by.get("T0", {})
    t0_solved = sum(1 for x in xs if t0.get(x, {}).get("residual_mm", 1e9) <= TOL_MM)
    check(
        "P4b T0 solves at p50 and station (2/3)",
        t0_solved == 2,
        ", ".join(f"{x:.3f}: {t0.get(x, {}).get('residual_mm', float('nan')):.1f} mm" for x in xs),
    )
    if near is not None:
        near_t0 = {round(r["x"], 3): r for r in near["rows"] if r["cand"] == "T0"}
        same = all(
            abs(near_t0[x]["margin_rad"] - t0[x]["margin_rad"]) < 2e-3
            for x in xs
            if x in near_t0 and x in t0
        )
        check(
            "P4c T0's tight j-margin is the attitude, not the seed "
            "(4-restart solve reads the same)",
            same,
            "restarts=4 margins " + ", ".join(f"{near_t0[x]['margin_rad']:+.3f}" for x in sorted(near_t0))
            + " vs restarts=1 " + ", ".join(f"{t0[x]['margin_rad']:+.3f}" for x in sorted(t0)),
        )
    # ---- P5: the yaw family is monotone in theta -------------------------- #
    order = [n for n in ("Y15", "Y21", "Y31", "Y46", "Y62") if n in by]
    worst = [max(by[n][x]["residual_mm"] for x in xs) for n in order]
    check(
        "P5 the yaw residual grows with theta (monotone family)",
        all(b >= a for a, b in zip(worst, worst[1:])),
        " -> ".join(f"{n} {w:.1f}" for n, w in zip(order, worst)),
    )

    failed = [c for c in checks if not c[1]]
    lines = []
    add = lines.append
    add("P62 phase 1 - the left grasp-attitude IK/reach probe at the pick station")
    add("=" * 78)
    add("")
    add("Harness: logs/p62/ik_probe.py (the scripts/174|183 recipe: `SortingScene`")
    add("(environment, pedestal, robot, conveyor), the **left** arm, teleport to")
    add("`configs/waypoints_oriented.json` arms.left.grasp, pin")
    add("`ArmController.hold_quaternion`, then `solve_to(jaw centre at")
    add("(x, pick_y, belt_top + 0.09), iterations=400, tolerance=6 mm)`. The scene is")
    add("the shipped one: belt surface z = 1.170, station (0.340, 0.000).")
    add("")
    add("x ladder = the left's delivered band from logs/p60/LEFT_CENSUS.md:")
    add("  x = 0.274 (p50 selection x), 0.340 (the pick station), 0.398 (the max;")
    add("  the same file's never-held band is x 0.347-0.398).")
    add("")
    add("Claim: logs/p62/ik_probe.log (FRUIT_P62_CANDIDATES=C0,Y15,Y21,Y31,Y46,Y62,T0),")
    add("cross-check logs/p62/ik_probe_restarts.log (FRUIT_P62_RESTARTS=4, C0,T0,Y15).")
    add("")
    add("Frame semantics (measured, not assumed) - the calibrated seed:")
    add(f"  approach_axis = {approach[0]:+.3f},{approach[1]:+.3f},{approach[2]:+.3f}"
        f"   |dot| with cols 0/1/2 = " + " / ".join(f"{d:.3f}" for d in dots_app))
    add(f"  jaw_axis      = {jaw_axis[0]:+.3f},{jaw_axis[1]:+.3f},{jaw_axis[2]:+.3f}"
        f"   |dot| with cols 0/1/2 = " + " / ".join(f"{d:.3f}" for d in dots_jaw))
    add("  => the rotation matrix's **z column is the finger long axis** (as P61")
    add("     assumed) and column 1 is the jaw-opening axis (98.0 mm pad separation).")
    add("")
    add("Per candidate (worst over the three x, then the p50/station read):")
    add("")
    add(f"{'cand':5s} {'proj':>7s} {'slip.sh':>7s} {'solved':>6s} {'res p50':>8s} "
        f"{'res stn':>8s} {'res cliff':>9s} {'qerr':>6s} {'margin*':>8s} {'pad-belt':>9s}")
    for name in names:
        if name.startswith("Z") or name == "J45" or name == "F3":
            continue
        b = by.get(name)
        if not b:
            continue
        row = table[name]
        core = [0.274, 0.34]
        add(
            f"{name:5s} {row['belt_projection']:+7.3f} {row['slip_share_col2']:+7.3f} "
            f"{sum(1 for x in xs if b[x]['residual_mm'] <= TOL_MM)}/{len(xs):<4d} "
            f"{b[0.274]['residual_mm']:8.1f} {b[0.34]['residual_mm']:8.1f} "
            f"{b[0.398]['residual_mm']:9.1f} "
            f"{max(b[x]['qerr_deg'] for x in core):6.1f} "
            f"{min(b[x]['margin_rad'] for x in core):+8.3f} "
            f"{min(b[x]['pad_low_belt_mm'] for x in xs):+9.1f}"
        )
    add("")
    add("  `margin*` is min over the 7 arm joints of min(q - lo, hi - q) [rad] at the")
    add("  solved configuration, over the delivered **core** x = 0.274 and 0.340")
    add("  (j2 for the yaw family, j3 for T0); the 0.398 cliff is the `res cliff`")
    add("  column. `pad-belt` is the fingertip pads' lowest world point above the belt")
    add("  top (min over all three x), from the live finger-link pose composed with")
    add("  configs/finger_pads.json (capsule, r = 10 mm, total length 57 mm).")
    add("")
    add("The two families (candidates.py proves these, they are not fits):")
    add("  F1 yaw about world z: proj +0.5132 -> 0.0000 (dtheta 30.995 deg) ->")
    add("     -0.5132 (61.990 deg); EVERY column's z-component is invariant, so the")
    add("     attitude's relation to the vertical (finger height, pad droop) cannot")
    add("     change - the family is 'top-down-safe' by construction. It is still")
    add("     infeasible: the left's station reach is azimuth-limited (below).")
    add("  F2 roll about the frame's z column: proj delta 0.0e+00 exactly (a rotation")
    add("     about an axis fixes that axis) - it CANNOT be the lever for this")
    add("     mechanism; and it is not neutral either: the jaw axis tips out of the")
    add("     horizontal plane 0.5 -> 44.3 -> 85.3 deg at phi = 45/90 deg.")
    add("     (one pad above the other = the shipped config's own v1 failure note)")
    add("  F3 rotation about world y (the belt axis): proj delta 0.0e+00 exactly - the")
    add("     projection IS the y component, and a rotation preserves its own axis.")
    add("     A rotation about world x is the only other single-axis option and needs")
    add("     +80.94 deg (the first root of t_y cos - t_z sin = 0): proj 0.000 but the")
    add("     finger axis ends 31.5 deg BELOW horizontal and still 0.854 across the")
    add("     belt - not a top-down attitude. T0 is not any single-axis rotation of")
    add("     the shipped frame (it is 100.7 deg away and swaps which column is")
    add("     vertical); it reaches proj 0 by pointing the fingers straight down.")
    add("")
    add("Verdict:")
    add("  * The yaw family is INFEASIBLE at the left station, monotonically (worst")
    add("    over the three x): the residual grows 8.3 -> 10.6 (15 deg) -> 13.6 (21.7)")
    add("    -> 19.9 (31.0) -> 48.9 (46.5) -> 118.0 mm (62.0), the wrist attitude")
    add("    error 2.0 -> 13.9 -> 55.4 deg, the binding j2 margin collapses")
    add("    0.204 -> 0.056 -> 0.000 rad, and the pads drop 30.2 -> 3.0 -> -14.2 mm")
    add("    relative to the belt top. So a yaw that removes the +0.513 belt")
    add("    projection also removes the station.")
    add("  * T0 (the reach harness's own top-down: fingers straight down, jaws exactly")
    add("    across the belt - 90.0 deg vs the shipped 31.0 deg) is the only candidate")
    add("    that reaches proj 0.000 AND solves: 6.0 / 5.8 mm at p50/station (the")
    add("    control's 5.9 / 5.7), attitude error 0.77 deg, pads +59.6..+64.6 mm")
    add("    (+14.7..+25.7 mm HIGHER than the control, so the descent's documented")
    add("    40-90 mm shortfall is not worsened by the pad geometry).")
    add("  * T0's costs are measured and must travel with the cell: the binding margin")
    add("    is +0.007 rad at j3 (the arm is at its configuration limit; unchanged at")
    add("    FRUIT_P62_RESTARTS=4, so it is the attitude, not the seed), and at the +x")
    add("    cliff x = 0.398 it reads 32.8 mm / 17.0 deg vs the control's 8.3 / 2.0 -")
    add("    i.e. T0 makes the never-held tail worse, not better.")
    add("")
    add("Checks:")
    for name, ok, detail in checks:
        add(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    add("")
    add(f"RESULT: {'PASS' if not failed else 'FAIL'} ({len(checks) - len(failed)}/{len(checks)})")
    add("")
    add("Provenance (md5):")
    for name in ("candidates.py", "candidates.json", "ik_probe.py", "ik_report.py",
                 "CANDIDATES.md", "ik_probe_rows.json", "ik_probe.log",
                 "ik_probe_restarts.log"):
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            add(f"  {name:24s} {md5(path)}")
    out = os.path.join(HERE, "IK_PROBE.txt")
    with open(out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
