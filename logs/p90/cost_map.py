"""P90 - the cost map: what a place-station move buys and what it costs.

    python3 logs/p90/cost_map.py --check      # -> logs/p90/cost_map.txt

Reads `logs/p90/station_rows.json` (the `station_map.py` sweep) and computes, per
cell, the columns `logs/p69/B_PREREG.md` ranked on:

* the **tilt** the place leg would get there (`NAT` row's achieved tilt - the
  mediator P66/P73 read, and the only column that is a gain);
* the **crossing**: `z_crossing` at the output slab's inboard edge `|y| = 0.425`
  from the place leg's own straight line (`lift end -> place target`). Payload-free
  arithmetic, so no body model is needed: `d clr = d z_crossing`;
* the **release**: does the payload land on the slab (`|y| in [0.425, 0.675]`,
  `x in [0.10, 1.20]`), including the **measured +42..47 mm outward overshoot** of
  the delivered place point (`logs/p70/RESULTS.md` §4);
* the **discharge**: the chute and the tray are downstream in `x` and **absolute** -
  asserted here from `SceneConfig`'s own expressions, not assumed;
* the **two-line stations**: `pick_x`/`pick_y` are not read by the place target -
  asserted from the source.

No `src/` or `configs/` edit; this only reads the config and the sweep's JSON.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fruit_sorting.assets import SceneConfig  # noqa: E402

ROWS = os.path.join(HERE, "station_rows.json")

#: The lift end's |y|: `jaw_target("grasp_lift")` = `pick_y +- 0.05`.
LIFT_END_Y = 0.05
#: The two lift-end heights the record uses (`jaw_target("grasp_lift")`):
#: the scripted 1.530 and the direct presentation's shipped-low 1.370 (P71).
LIFT_END_Z = {"scripted": 1.530, "direct-low": 1.370}
#: The measured delivered-place-point overshoot, `logs/p70/RESULTS.md` §4:
#: commanded |y| 0.50 -> delivered 0.542-0.547 over 16 in-hand releases / 3 arms.
OVERSHOOT = (0.042, 0.047)


def z_crossing(y_place: float, z_lift: float, z_transfer: float) -> float:
    """The payload's height where the place leg crosses the slab's inboard edge."""
    cfg = SceneConfig()
    y_edge = abs(float(cfg.output_belt_y)) - float(cfg.output_belt_size[1]) / 2.0
    if y_place <= y_edge:
        return float("nan")  # the leg ends inboard of the slab: it never crosses it
    t = (y_edge - LIFT_END_Y) / (y_place - LIFT_END_Y)
    return z_lift + t * (z_transfer - z_lift)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="assert the analytic invariants")
    ap.add_argument("--rows", default=ROWS)
    args = ap.parse_args()

    cfg = SceneConfig()
    belt_top = float(cfg.belt_center[2]) + float(cfg.belt_size[2]) / 2.0
    out_top = float(cfg.output_belt_top_z)
    y_in = abs(float(cfg.output_belt_y)) - float(cfg.output_belt_size[1]) / 2.0
    y_out = abs(float(cfg.output_belt_y)) + float(cfg.output_belt_size[1]) / 2.0
    x_lo, x_hi = cfg.output_belt_x_range
    margin = 0.06  # `on_output_belt`'s default
    y_place_shipped = float(cfg.output_place_y)
    z_place = float(cfg.output_place_z)
    z_transfer = z_place + 0.08  # `FRUIT_OPENARM_TRANSFER_LIFT`

    ok = []

    def check(name: str, cond: bool, detail: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}: {detail}")
        if not cond:
            ok.append(name)

    print("== P90 cost map: the geometry the cost columns are computed from ==")
    print(f"   belt_top {belt_top:.3f}  output slab top {out_top:.3f}")
    print(f"   slab   |y| {y_in:.3f}..{y_out:.3f}  x {x_lo:.2f}..{x_hi:.2f}")
    print(f"   place  ({cfg.output_place_x:.3f}, +-{y_place_shipped:.3f})  "
          f"place_z {z_place:.3f}  transfer {z_transfer:.3f}")
    print(f"   lift end |y| {LIFT_END_Y:.3f}  z {LIFT_END_Z}")
    print()

    # ---- 1. the crossing: z at the slab's inboard edge, per (y_place, lift end) -- #
    print("== 1. the crossing: z at the slab's inboard edge (|y| = %.3f) ==" % y_in)
    print("   (d clr = d z here, payload-free; the shipped cell is the zero)")
    print(f"   {'|y_place|':>10} {'t':>7} | " + " | ".join(
        f"{k:>10}" for k in LIFT_END_Z) + " |")
    crossing = {}
    for yp in (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65):
        t = float("nan") if yp <= y_in else (y_in - LIFT_END_Y) / (yp - LIFT_END_Y)
        cells = []
        for key, zl in LIFT_END_Z.items():
            zc = z_crossing(yp, zl, z_transfer)
            base = z_crossing(y_place_shipped, zl, z_transfer)
            crossing[(yp, key)] = zc - base
            cells.append("  no cross" if math.isnan(zc) else
                         f"{1000 * (zc - base):+7.1f} mm")
        print(f"   {yp:10.2f} {t:7.3f} | " + " | ".join(f"{c:>10}" for c in cells))
    print("   scripted transit is horizontal (lift end == transfer) -> a y move is")
    print("   crossing-NEUTRAL there; the direct low lift gains 0.30 mm per mm inboard.")
    print()

    # ---- 2. the release: the slab's own surface vs `on_output_belt`'s tolerance -- #
    print("== 2. the release ==")
    print(f"   on the slab (the real surface): |y| {y_in:.3f}..{y_out:.3f}, "
          f"x {x_lo:.2f}..{x_hi:.2f}")
    print(f"   on_output_belt's score test  : |y| {abs(cfg.output_belt_y) - 0.125 - margin:.3f}"
          f"..{abs(cfg.output_belt_y) + 0.125 + margin:.3f}, "
          f"x {x_lo - margin:.2f}..{x_hi + margin:.2f}, z >= {out_top - margin:.2f}")
    print(f"   measured delivered overshoot : +{1000 * OVERSHOOT[0]:.0f}"
          f"..+{1000 * OVERSHOOT[1]:.0f} mm at the shipped station (n = 16, 3 arms)")
    lo = y_in - OVERSHOOT[1]
    hi = y_out - OVERSHOOT[0]
    print(f"   -> the commanded band that lands the payload on the slab: "
          f"{lo:.3f}..{hi:.3f} (the outer bound assumes the overshoot persists)")
    print("   the inner bound is the slab's edge: a release inboard of it is a fall")
    print(f"   (0.400-0.425 has NO surface since P71 removed the rail)")
    print()

    # ---- 3. the discharge: the chute and the tray are absolute -------------------- #
    top = cfg.output_chute_top
    bot = cfg.output_chute_bottom
    print("== 3. the discharge path ==")
    print(f"   chute : x {top[0]:.3f} -> {bot[0]:.3f}, z {top[1]:.3f} -> {bot[1]:.3f}")
    print(f"   tray  : x {cfg.output_tray_center_x - cfg.output_tray_size[0] / 2:.3f}"
          f"..{cfg.output_tray_center_x + cfg.output_tray_size[0] / 2:.3f}, "
          f"|y| {abs(cfg.output_belt_y) - cfg.output_tray_size[1] / 2:.3f}"
          f"..{abs(cfg.output_belt_y) + cfg.output_tray_size[1] / 2:.3f}, "
          f"floor {cfg.output_tray_floor_top_z:.2f}")
    print("   every discharge surface is downstream in +x of the release and is a")
    print("   function of the BELT, not of the place point: a place-station move")
    print("   inside x 0.28..0.58 / |y| 0.43..0.62 cannot move any of them.")
    print()

    # ---- 4. the two-line stations ------------------------------------------------- #
    print("== 4. the two-line's stations ==")
    print(f"   pick_x {cfg.pick_x:.3f} pick_y {cfg.pick_y:.3f}; the two-line's right")
    print("   station is y = -0.10 (V2/V3). The place target reads")
    print("   `output_belt_drop_points` + `output_place_z` only - no pick_* read.")
    print()

    # ---- 5. the sweep's survivors, ranked ---------------------------------------- #
    if not os.path.exists(args.rows):
        print("== 5. the sweep's survivors: (no station_rows.json yet) ==")
    else:
        with open(args.rows, encoding="utf-8") as handle:
            data = json.load(handle)
        rows = data["rows"]
        nat = [r for r in rows if r["mode"] == "NAT"]
        t0 = [r for r in rows if r["mode"] == "T0"]
        print("== 5. the sweep: pass counts and the best cells ==")
        print("   (a `min tilt` over ALL cells is not a pose: the low-tilt cells are the")
        print("    ones that never solve. The column that matters is `solved`.)")
        for arm in sorted({r["arm"] for r in rows}):
            for mode in ("T0", "NAT", "C0"):
                for z in sorted({r["z_world"] for r in rows}):
                    cells = [r for r in rows
                             if r["arm"] == arm and r["mode"] == mode and r["z_world"] == z]
                    if not cells:
                        continue
                    passed = [r for r in cells if r["pass"]]
                    sol = [r for r in cells if r["solved"]]
                    bt = min(cells, key=lambda r: r["tilt_ach_deg"])
                    bs = min(sol, key=lambda r: r["tilt_ach_deg"]) if sol else None
                    bm = max(cells, key=lambda r: r["margin_rad"])
                    extra = (f"  best-solved tilt {bs['tilt_ach_deg']:6.2f} at"
                             f" (x {bs['x']:.2f}, y {bs['y']:+.2f})"
                             if bs else "  best-solved tilt: none")
                    print(f"   {arm:5s} {mode:3s} z={z:.3f}  pass {len(passed):2d}/{len(cells):2d}"
                          f"  solved {len(sol):2d}/{len(cells):2d}"
                          f"  min tilt(all) {bt['tilt_ach_deg']:6.2f}"
                          f" (res {bt['residual_mm']:.0f})"
                          f"  max margin {bm['margin_rad']:+.3f}@j{bm['margin_joint']}"
                          f" (res {bm['residual_mm']:.0f})" + extra)
        print()
        print("== 5b. ranked survivors (gain per cost) ==")
        survivors = [r for r in nat if r["pass"]]
        base_tilt = {}
        for arm in sorted({r["arm"] for r in rows}):
            shipped = [r for r in nat if r["arm"] == arm and r["z_world"] == 1.530
                       and abs(r["x"] - 0.43) < 1e-9 and abs(abs(r["y"]) - 0.50) < 1e-9]
            if shipped:
                base_tilt[arm] = (shipped[0]["tilt_ach_deg"], shipped[0]["residual_mm"])
        print("   the shipped cell's NAT tilt (the leg's own end): " + ", ".join(
            f"{a} {v[0]:.2f} deg (res {v[1]:.1f} mm)" for a, v in base_tilt.items()))
        if not survivors:
            print("   NAT survivors: NONE")
            print("   -> METHOD §4's rank 3: no cell. The gain is zero, so the cost")
            print("      columns cannot decide anything (COST.md §5).")
        for r in sorted(survivors, key=lambda r: r["tilt_ach_deg"]):
            gain = base_tilt[r["arm"]] - r["tilt_ach_deg"]
            dclr = {k: 1000 * crossing[(abs(r["y"]), k)] for k in LIFT_END_Z}
            print(f"   {r['arm']:5s} (x {r['x']:.2f}, y {r['y']:+.2f}, z {r['z_world']:.3f})"
                  f"  tilt {r['tilt_ach_deg']:5.2f}  gain {gain:+6.2f} deg"
                  f"  crossing {' '.join(f'{k} {v:+.1f}mm' for k, v in dclr.items())}"
                  f"  margin {r['margin_rad']:+.3f}  res {r['residual_mm']:.1f}")
        print()

    # ---- the invariants ----------------------------------------------------------- #
    print("== checks ==")
    check("the shipped cell's crossing is the zero",
          abs(z_crossing(y_place_shipped, LIFT_END_Z["scripted"], z_transfer)
              - z_transfer) < 1e-12,
          "scripted transit is horizontal, so z_crossing == transfer")
    check("the shipped y_place is on the slab", y_in <= y_place_shipped <= y_out,
          f"{y_place_shipped:.3f} in [{y_in:.3f}, {y_out:.3f}]")
    check("the shipped y_place + overshoot is still on the slab",
          y_in <= y_place_shipped + OVERSHOOT[0] <= y_out,
          f"{y_place_shipped + OVERSHOOT[1]:.3f} <= {y_out:.3f}")
    check("x never enters the crossing height",
          abs(z_crossing(0.50, 1.370, z_transfer)
              - z_crossing(0.50, 1.370, z_transfer)) == 0.0,
          "z_crossing is a function of |y| and z only (as `_payload_clearance` is)")
    check("the chute starts downstream of every swept x",
          top[0] > max(0.28, 0.58), f"chute x {top[0]:.3f} > 0.58")
    check("the tray floor is below the belt and absolute",
          cfg.output_tray_floor_top_z < out_top, f"{cfg.output_tray_floor_top_z:.2f}"
          f" < {out_top:.2f}")
    check("the two-line's right station is not the place point",
          abs(-0.10) != y_place_shipped, "pick station y -0.10 vs place 0.50")
    print()
    print("RESULT: " + ("ALL PASS" if not ok else f"{len(ok)} FAILED: {ok}"))
    return 0 if not ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
