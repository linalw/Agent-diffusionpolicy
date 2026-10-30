"""P66 phase 1a report - read the sweep JSONs and print the tables the doc quotes.

    python3 logs/p66/sweep_report.py            # -> logs/p66/sweep_report.txt
    python3 logs/p66/sweep_report.py --check    # structural assertions only

No simulator. Every number in `logs/p66/STATION_SWEEP.md` comes from here, so the
doc's tables are re-derivable from the raw rows (`sweep_rows.json`,
`restart_rows.json`, `liftseed_rows.json`).
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
QERR_MAX = 2.0
MARGIN_MIN = 0.05
PAD_MIN = 2.0


def load(name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def passes(row) -> bool:
    return (
        row["qerr_deg"] <= QERR_MAX
        and row["margin_rad"] >= MARGIN_MIN
        and row["pad_low_belt_mm"] >= PAD_MIN
    )


def best(rows):
    """Highest-margin row (ties broken by the smaller attitude error)."""
    return max(rows, key=lambda r: (round(r["margin_rad"], 6), -r["qerr_deg"]))


def fmt_row(r) -> str:
    return (
        f"x={r['x']:.3f} y={r['y']:+.2f} z={r['z_above_belt']:.3f} "
        f"res={r['residual_mm']:6.1f}mm qerr={r['qerr_deg']:6.2f}deg "
        f"margin={r['margin_rad']:+.3f}rad@j{r['margin_joint']} "
        f"pad={r['pad_low_belt_mm']:+7.1f}mm jaw_z={r['jaw_z_ach']:+.4f} "
        f"proj_ach={r['belt_proj_ach']:+.4f} pass={int(r['pass'])}"
    )


def main() -> int:
    check_only = "--check" in sys.argv
    main_run = load("sweep_rows.json")
    restart = load("restart_rows.json")
    lift = load("liftseed_rows.json")
    if main_run is None:
        print("missing sweep_rows.json", file=sys.stderr)
        return 2

    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)
        if not check_only:
            print(text)

    rows = main_run["rows"]
    xs = main_run["xs"]
    ys = main_run["ys"]
    zs = main_run["zs"]
    crit = main_run["pass_criteria"]
    wall = main_run["wall"]

    out("P66 phase 1a - the left station feasibility sweep (T0 vs the shipped control)")
    out(f"grid: {len(xs)} x {len(ys)} x {len(zs)} depths x 2 attitudes = {len(rows)} cells")
    out(
        f"criterion: qerr <= {crit['qerr_max_deg']:.1f} deg AND margin >= "
        f"{crit['margin_min_rad']:.2f} rad AND pad >= {crit['pad_min_mm']:.1f} mm"
    )
    out(f"|dot(C0, waypoints_oriented.left)| = {main_run['control_dot_file']:.9f}")
    out(
        f"wall: sweep {wall['sweep_s']:.1f} s over {len(rows)} cells "
        f"({wall['per_cell_s']:.2f} s/cell), total {wall['total_s']:.1f} s"
    )
    out(
        f"LIFT_HEIGHT={main_run['lift_height']:.2f} m -> depths {', '.join(f'{z:.3f}' for z in zs)} "
        "m above the belt top (0.090 grip, 0.250 grip+LIFT_HEIGHT, 0.360 shipped "
        "jaw_target('grasp_lift') = belt_top + 0.28 + FRUIT_OPENARM_TRANSFER_LIFT 0.08)"
    )
    out()

    # ---- the question ------------------------------------------------------ #
    out("== the question, per attitude and depth ==")
    for cand in ("T0", "C0"):
        for z in zs:
            cells = [r for r in rows if r["cand"] == cand and r["z_above_belt"] == z]
            if not cells:
                continue
            npass = sum(1 for r in cells if passes(r))
            b = best(cells)
            out(
                f"{cand:3s} z={z:.3f}: pass {npass}/{len(cells)}  "
                f"best margin {b['margin_rad']:+.3f} rad @j{b['margin_joint']} "
                f"(x={b['x']:.3f} y={b['y']:+.2f})  "
                f"qerr range {min(r['qerr_deg'] for r in cells):.2f}.."
                f"{max(r['qerr_deg'] for r in cells):.2f} deg  "
                f"pad range {min(r['pad_low_belt_mm'] for r in cells):+.1f}.."
                f"{max(r['pad_low_belt_mm'] for r in cells):+.1f} mm  "
                f"solved {sum(1 for r in cells if r['solved'])}/{len(cells)}"
            )
    out()

    t0 = [r for r in rows if r["cand"] == "T0"]
    c0 = [r for r in rows if r["cand"] == "C0"]
    out("== T0: every cell (the answer to 'is there any station point') ==")
    out(
        f"T0 pass {sum(1 for r in t0 if passes(r))}/{len(t0)} | "
        f"margin range {min(r['margin_rad'] for r in t0):+.3f}.."
        f"{max(r['margin_rad'] for r in t0):+.3f} rad | "
        f"qerr range {min(r['qerr_deg'] for r in t0):.2f}.."
        f"{max(r['qerr_deg'] for r in t0):.2f} deg | "
        f"pad range {min(r['pad_low_belt_mm'] for r in t0):+.1f}.."
        f"{max(r['pad_low_belt_mm'] for r in t0):+.1f} mm"
    )
    bt0 = best(t0)
    out(f"T0 BEST POINT: {fmt_row(bt0)}")
    out(
        f"T0 cells with margin >= 0.05 rad: "
        f"{sum(1 for r in t0 if r['margin_rad'] >= MARGIN_MIN)}/{len(t0)}; "
        f">= 0.02 rad: {sum(1 for r in t0 if r['margin_rad'] >= 0.02)}/{len(t0)}; "
        f">= 0.01 rad: {sum(1 for r in t0 if r['margin_rad'] >= 0.01)}/{len(t0)}"
    )
    bc0 = best(c0)
    out(f"C0 pass {sum(1 for r in c0 if passes(r))}/{len(c0)} | C0 BEST POINT: {fmt_row(bc0)}")
    out()

    # ---- the y marginal ---------------------------------------------------- #
    out("== does y help? (T0, per y; all x and the grip depth 0.090) ==")
    for y in ys:
        cells = [r for r in t0 if r["y"] == y and r["z_above_belt"] == min(zs)]
        out(
            f"y={y:+.2f}: margin {min(r['margin_rad'] for r in cells):+.3f}.."
            f"{max(r['margin_rad'] for r in cells):+.3f} rad  "
            f"qerr {min(r['qerr_deg'] for r in cells):.2f}.."
            f"{max(r['qerr_deg'] for r in cells):.2f} deg  "
            f"solved {sum(1 for r in cells if r['solved'])}/{len(cells)}  "
            f"joints {sorted({r['margin_joint'] for r in cells})}"
        )
    out()

    # ---- the delivered band ------------------------------------------------ #
    out("== delivered-band coverage (P60: x 0.188-0.398, p50 0.274) ==")
    for cand in ("T0", "C0"):
        for z in zs:
            per_x = []
            for x in xs:
                cells = [r for r in rows if r["cand"] == cand and r["z_above_belt"] == z and r["x"] == x]
                ok = [r["y"] for r in cells if passes(r)]
                per_x.append(f"{x:.3f}:[{','.join(f'{v:+.2f}' for v in ok) if ok else '-'}]")
            covered = sum(1 for x in xs if any(
                passes(r) for r in rows
                if r["cand"] == cand and r["z_above_belt"] == z and r["x"] == x
            ))
            out(f"{cand:3s} z={z:.3f} x-columns covered {covered}/{len(xs)}  " + " ".join(per_x))
    out()

    # ---- the lift end ------------------------------------------------------ #
    out("== the lift's end pose (z = 0.360 = the shipped jaw_target('grasp_lift')) ==")
    for cand in ("T0", "C0"):
        cells = [r for r in rows if r["cand"] == cand and abs(r["z_above_belt"] - max(zs)) < 1e-9]
        out(
            f"{cand:3s}: qerr {min(r['qerr_deg'] for r in cells):.2f}.."
            f"{max(r['qerr_deg'] for r in cells):.2f} deg, "
            f"res {min(r['residual_mm'] for r in cells):.1f}.."
            f"{max(r['residual_mm'] for r in cells):.1f} mm, "
            f"achieved belt projection {min(r['belt_proj_ach'] for r in cells):+.3f}.."
            f"{max(r['belt_proj_ach'] for r in cells):+.3f} "
            f"(commanded {cells[0]['belt_proj_cmd']:+.3f}), "
            f"pass {sum(1 for r in cells if passes(r))}/{len(cells)}"
        )
    out()

    # ---- the robustness arms ---------------------------------------------- #
    if restart is not None:
        rr = restart["rows"]
        out("== robustness A: T0 at the grip depth with RESTARTS=4 (P62's seed check, over y) ==")
        for r in rr:
            out("  " + fmt_row(r))
        b = best(rr)
        out(f"  best margin {b['margin_rad']:+.3f} rad @j{b['margin_joint']} "
            f"(x={b['x']:.3f} y={b['y']:+.2f}); pass {sum(1 for r in rr if passes(r))}/{len(rr)}")
        out(f"  wall {restart['wall']['total_s']:.1f} s over {len(rr)} cells")
        out()
    if lift is not None:
        lr = lift["rows"]
        out("== robustness B: solved FROM the grasp_lift seed, RESTARTS=3, z=0.360 ==")
        for r in lr:
            out("  " + fmt_row(r))
        for cand in ("T0", "C0"):
            cells = [r for r in lr if r["cand"] == cand]
            b = best(cells)
            out(f"  {cand:3s}: pass {sum(1 for r in cells if passes(r))}/{len(cells)} | "
                f"best margin {b['margin_rad']:+.3f} rad @j{b['margin_joint']} | "
                f"qerr {min(r['qerr_deg'] for r in cells):.2f}..{max(r['qerr_deg'] for r in cells):.2f} deg")
        out(f"  wall {lift['wall']['total_s']:.1f} s over {len(lr)} cells")
        out()

    # ---- structural assertions -------------------------------------------- #
    checks = []
    checks.append(("150 main cells", len(rows) == 150))
    checks.append(("both attitudes at every depth", all(
        len([r for r in rows if r["cand"] == c and r["z_above_belt"] == z]) == len(xs) * len(ys)
        for c in ("T0", "C0") for z in zs
    )))
    checks.append(("T0 passes nothing", sum(1 for r in t0 if passes(r)) == 0))
    checks.append(("T0's best margin is < 0.05 rad", best(t0)["margin_rad"] < MARGIN_MIN))
    checks.append(("T0's best margin is >= 0.005 rad (it is not a zero-margin artefact)",
                   best(t0)["margin_rad"] >= 0.005))
    checks.append(("every T0 cell at the grip depth solves <= 6 mm inside the reach band "
                   "(x <= 0.320, y=0)", all(
                       r["solved"] for r in t0
                       if r["z_above_belt"] == min(zs) and r["y"] == 0.0 and r["x"] <= 0.320)))
    checks.append(("no T0 cell at the lift depth solves",
                   not any(r["solved"] for r in t0 if abs(r["z_above_belt"] - max(zs)) < 1e-9)))
    checks.append(("C0 covers the whole band at the grip depth",
                   all(any(passes(r) for r in c0 if r["z_above_belt"] == min(zs) and r["x"] == x)
                       for x in xs)))
    checks.append(("the control IS the file quaternion", main_run["control_dot_file"] > 0.999999))
    checks.append(("pad is never the binding clause (T0 min pad > 2 mm)",
                   min(r["pad_low_belt_mm"] for r in t0) > PAD_MIN))
    if restart is not None:
        checks.append(("restarts do not lift T0 above 0.01 rad",
                       best(restart["rows"])["margin_rad"] < 0.01))
    if lift is not None:
        checks.append(("from the lift seed T0 still passes nothing",
                       sum(1 for r in lift["rows"] if r["cand"] == "T0" and passes(r)) == 0))

    out("== structural checks ==")
    for name, ok in checks:
        out(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    npass = sum(1 for _n, ok in checks if ok)
    out(f"  {npass}/{len(checks)}")

    if not check_only:
        path = os.path.join(HERE, "sweep_report.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        print(f"wrote {path}")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
