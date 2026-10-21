#!/usr/bin/env python3
"""P30-C: the pick station's reach geometry, re-derived offline.

    python3 logs/p30c/reach_geometry.py            # every table the design quotes
    python3 logs/p30c/reach_geometry.py --assert   # exit 1 if a pinned number moved

No simulator, no pxr: this reads the *shipped* `SceneConfig`, the two committed
reach maps (`logs/r10/reach_intercept_{left,right}.json`), the collision probes
(`logs/p30a/10_probe_parts_default.log`, `logs/166`, `logs/167`), the v1 indexed
acceptance (`logs/161`, `logs/160`) and the mass base (`logs/p12a2/1*_mass.log`),
and re-derives:

  1. **the reachable band per arm per x column** - raw (6 mm tolerance) and the
     code's effective band (`FRUIT_REACH_Y_INSET` = 2 cm, `tasks.py:500-539`);
  2. **the aim's margin** against both, for the single-arm station (y = 0.00)
     and the two-line stations (left 0.00 / right -0.10);
  3. **the vertical deficit** - the measured jaw floor above the belt top vs the
     fruit's centre (r = diameter/2, `assets.py:436-452`), i.e. *why* the indexed
     primitive's TCP target sits below the physical floor;
  4. **the indexed descent's `end=`** and its z/lateral decomposition (the
     `pads aimed at ... align=(dx,dy,dz)` rows);
  5. **the same-battery controls**: the dynamic line's `end=` (acceptance) and the
     mass base's (60 rows), so the design's baselines are the current ones.

Every number printed here is quoted in `logs/p30c/STATION_DESCENT_DESIGN.md`.
`--assert` pins the values the verdict depends on (the band edges, the floor, the
deficit range, the two baselines), so an edit to the belt, the station, the hand
or the inset cannot silently invalidate the analysis.

Provenance of each constant is given inline; nothing here is fitted.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.assets import SceneConfig  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

#: The measured jaw floor above the belt top [m]. Two probes, two poses:
#:   P0 `logs/p30a/10_probe_parts_default.log` (current tree, 2026-10-21):
#:      start jaw z = 1.262, stop z = 1.2286, belt top 1.170 -> +0.0586
#:   `logs/166_collision_probe.log` (older pose, jaw start 1.285):
#:      stop z = 1.2468 -> +0.0768
#: With the belt removed the same drive reaches z = 1.049 (`logs/167`) - i.e.
#: 0.180 m *below* the P0 stop, so the slab binds and the joints do not.
FLOOR_P0 = 0.0586
FLOOR_166 = 0.0768
NO_BELT_STOP = 1.049

#: The shipped standoff: jaw target = fruit centre + finger_len + PAD_LIFT
#: (`tasks.py:49` PAD_LIFT 0.010, `FRUIT_FINGER_LEN` default 0.060).
PAD_LIFT = 0.010
FINGER_LEN = 0.060
STANDOFF = FINGER_LEN + PAD_LIFT

#: The catch's along-belt lead at the aim: the intercept rows of the current
#: acceptance read +0.0172..+0.0177 m (`logs/p30a/01_accept_control.log`,
#: `dynamic descent: ... intercept=+0.017x m`).
AIM_LEAD = 0.0173

#: `FRUIT_REACH_Y_INSET` (`tasks.py:524`): the code's band is the measured band
#: inset by this on both sides.
INSET = 0.02

#: The measured grip-clean bands (6 mm tolerance) from
#: `logs/r10/reach_intercept_{left,right}.json` + the map summaries in
#: `logs/r10/{11_reach_left,12_reach_right}.log`. Columns are
#: (x_hi, dn, up) with x_hi = None for the last column (`tasks.py:500-517`).
MEASURED = {
    "left": ((0.20, -0.10, 0.15), (0.28, -0.05, 0.10), (None, 0.00, 0.10)),
    "right": ((0.20, -0.10, 0.10), (0.28, -0.10, 0.05), (None, -0.10, 0.00)),
}

#: The station ladder (`scripts/174_station_reach.py`, x = pick_x + dx, y = the
#: station, jaw z = belt_top + 0.09), `logs/v1/61_station_reach_seeded.log`.
STATION_LADDER = {
    "left": [(-0.16, 6.0), (-0.12, 5.7), (-0.08, 5.9), (-0.05, 6.0), (-0.03, 5.9),
             (0.00, 3.9), (0.03, 5.9), (0.05, 5.9), (0.08, 55.3), (0.12, 74.9),
             (0.16, 96.5)],
    "right": [(-0.16, 5.9), (-0.12, 5.8), (-0.08, 5.7), (-0.05, 5.8), (-0.03, 5.9),
              (0.00, 6.0), (0.03, 5.9), (0.05, 6.0), (0.08, 55.2), (0.12, 74.9),
              (0.16, 96.5)],
}

#: The two-line stations (`tasks.py::station_y_for`, the V2 two-line rework).
STATIONS = {"left": 0.0, "right": -0.10}


def band_for(arm: str, x: float, inset: float = INSET):
    """The band `(dn, up)` the code uses for a fruit at `x` (station-relative)."""
    cols = MEASURED[arm]
    for x_hi, dn, up in cols:
        if x_hi is None or x <= x_hi:
            return dn + inset, up - inset
    raise AssertionError("unreachable")


def reach_margin(arm: str, station: float, x: float, inset: float = INSET):
    """The aim's (dn, up) margins [m]; negative = outside the band.

    Both terms are in the **map's own frame** (world dy from `cfg.pick_y`), which
    is the frame the bands were measured in. The aim is `station + AIM_LEAD`.
    (The code reports the same margin *station-relative*: it computes
    `grip[1] - station_y` and compares against the band tuple as if the band had
    been measured at that arm's station. For the right two-line station
    (y = -0.10) that shifts the *reported* number by 100 mm - see section 2's
    caveat; it is a reporting convention, not a control input, because the reach
    selector is off by default.)
    """
    dn, up = band_for(arm, x, inset)
    aim = station + AIM_LEAD
    return aim - dn, up - aim


def load_rows(pattern: str):
    rows = []
    for name in sorted(os.listdir(os.path.join(ROOT, "logs"))):
        if not re.fullmatch(pattern, name):
            continue
        with open(os.path.join(ROOT, "logs", name), errors="ignore") as handle:
            rows.extend(handle.readlines())
    return rows


def end_values(text_rows):
    out = []
    for line in text_rows:
        m = re.search(r"approach\(cartesian\): ([\d.]+) cm.*?end=([\d.]+) mm", line)
        if m:
            out.append((float(m.group(1)), float(m.group(2))))
    return out


def aligned_rows(text_rows):
    out = []
    for line in text_rows:
        m = re.search(
            r"residual=([\d.]+)mm align=\(([-+\d.]+),([-+\d.]+),([-+\d.]+)\)mm", line
        )
        if m:
            res, ax, ay, az = (float(v) for v in m.groups())
            out.append((res, abs(ax), abs(ay), abs(az)))
    return out


def read(path: str) -> list[str]:
    with open(os.path.join(ROOT, path), errors="ignore") as handle:
        return handle.readlines()


def main(argv) -> int:
    cfg = SceneConfig()
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    dims = cfg.fruit_dimensions
    d_min = min(lo for lo, _ in dims.values())
    d_max = max(hi for _, hi in dims.values())
    r_min, r_max = d_min / 2.0, d_max / 2.0

    print("=" * 78)
    print("P30-C reach geometry (offline re-derivation)")
    print("=" * 78)
    print(f"SceneConfig: belt_top={belt_top:.3f} pick=({cfg.pick_x:.3f},{cfg.pick_y:.3f}) "
          f"grasp_clearance={cfg.grasp_clearance:.3f}")
    print(f"fruit: diameter {d_min * 1000:.0f}-{d_max * 1000:.0f} mm -> r "
          f"{r_min * 1000:.0f}-{r_max * 1000:.0f} mm")
    print(f"standoff (jaw above fruit centre) = {FINGER_LEN:.3f} + {PAD_LIFT:.3f} "
          f"= {STANDOFF:.3f} m")
    print(f"measured jaw floor above belt_top: {FLOOR_P0 * 1000:.1f} mm (P0, current) / "
          f"{FLOOR_166 * 1000:.1f} mm (logs/166)")
    print(f"no-belt stop z={NO_BELT_STOP:.3f} -> "
          f"{(belt_top + FLOOR_P0 - NO_BELT_STOP) * 1000:.0f} mm of unused arm travel")

    # ---- 1. the lateral band (the station ladder) -------------------------- #
    print("\n1. the station ladder (x = pick_x + dx, y = station, 6 mm tol)")
    for arm in ("left", "right"):
        row = " ".join(f"{dx:+.2f}:{res:5.1f}" for dx, res in STATION_LADDER[arm])
        print(f"   {arm:5s} {row}")
    for arm in ("left", "right"):
        clean = [dx for dx, res in STATION_LADDER[arm] if res <= 6.0]
        cliff = [dx for dx, res in STATION_LADDER[arm] if res > 50.0][0]
        print(f"   {arm:5s}: clean x = {cfg.pick_x + min(clean):.3f} .. "
              f"{cfg.pick_x + max(clean):.3f}; cliff at x={cfg.pick_x + cliff:.3f} "
              f"(dx=+{cliff:.2f})")

    # ---- 2. the along-belt band and the aim's margin ---------------------- #
    print("\n2. the along-belt band (world dy) and the aim "
          f"(station + {AIM_LEAD * 1000:.1f} mm)")
    print("   arm    x     station  measured dn..up   inset dn..up    "
          "aim margin dn / up (measured)   (inset)")
    margins = {}
    for arm in ("left", "right"):
        for x in (0.24, 0.34, 0.39):
            dn, up = band_for(arm, x, 0.0)
            cdn, cup = band_for(arm, x, INSET)
            mdn, mup = reach_margin(arm, STATIONS[arm], x, 0.0)
            idn, iup = reach_margin(arm, STATIONS[arm], x, INSET)
            margins[(arm, x)] = (mdn, mup, idn, iup)
            verdict = "inside" if mdn >= 0 and mup >= 0 else "OUTSIDE"
            print(f"   {arm:5s} {x:.2f}  {STATIONS[arm]:+.2f}  "
                  f"{dn:+.2f}..{up:+.2f}      {cdn:+.2f}..{cup:+.2f}     "
                  f"{mdn * 1000:+6.1f} / {mup * 1000:+6.1f} mm  {verdict:7s}"
                  f" {idn * 1000:+6.1f} / {iup * 1000:+6.1f}")
    print("   caveat: the code's `[boundary]` row compares the aim "
          "*station-relative*, so the right two-line\n   station (y=-0.10) reports "
          "the same margin shifted by its station offset - read the row with the\n"
          "   station in hand; the reach selector that consumes the band is "
          "default-off.")

    # ---- 3. the vertical deficit ------------------------------------------ #
    print("\n3. the vertical deficit: touch the fruit's centre vs the jaw floor")
    print("   r [mm]  fruit centre z   jaw floor z (P0 / 166)   deficit P0 / 166 [mm]")
    deficit_p0 = []
    deficit_166 = []
    for r in (r_min, (r_min + r_max) / 2, r_max):
        fc = belt_top + r
        d0 = (belt_top + FLOOR_P0) - fc
        d1 = (belt_top + FLOOR_166) - fc
        deficit_p0.append(d0)
        deficit_166.append(d1)
        print(f"   {r * 1000:5.1f}   {fc:.4f}         "
              f"{belt_top + FLOOR_P0:.4f} / {belt_top + FLOOR_166:.4f}       "
              f"{d0 * 1000:+5.1f} / {d1 * 1000:+5.1f}")
    print("   -> the shipped dynamic aim (fruit + 0.070) sits ABOVE the floor by "
          f"{(r_min + STANDOFF - FLOOR_P0) * 1000:.0f}-"
          f"{(r_max + STANDOFF - FLOOR_P0) * 1000:.0f} mm (P0); the indexed "
          "primitive's TCP target\n      (the fruit's centre) sits BELOW it by the "
          "same deficit.")
    print("   -> the code's `[boundary] belt_margin` = grip_z - belt_top - "
          f"finger_len = r + {(STANDOFF - FINGER_LEN) * 1000:.0f} mm, i.e. "
          f"{(FLOOR_166 - FINGER_LEN) * 1000:.0f} mm optimistic against the 166 floor")

    # the *measured* fruit centres (the `[task] ... fruit_z=` rows of the current
    # acceptance + the two-line patch control), so the aim's margin is a
    # measurement and not only the r-range algebra.
    fz = []
    for path in ("logs/p30a/01_accept_control.log", "logs/p30a/20_patch_control.log"):
        for line in read(path):
            for m in re.finditer(r"fruit_z=([\d.]+)", line):
                fz.append(float(m.group(1)))
    aim_lo, aim_hi = min(fz) + STANDOFF, max(fz) + STANDOFF
    margin_lo = aim_lo - (belt_top + FLOOR_P0)
    margin_hi = aim_hi - (belt_top + FLOOR_P0)
    print(f"   measured fruit centres (n={len(fz)}): z {min(fz):.3f}-{max(fz):.3f} "
          f"-> the shipped aim {aim_lo:.3f}-{aim_hi:.3f} = "
          f"+{margin_lo * 1000:.1f}..+{margin_hi * 1000:.1f} mm over the P0 floor")

    # ---- 4. the indexed descent ------------------------------------------- #
    v1 = read("logs/161_accept_endmetric.log") + read("logs/160_endgap028.log")
    ends = end_values(v1)
    dec = aligned_rows(v1)
    print(f"\n4. the indexed primitive (FRUIT_DYNAMIC_PICK=0): n={len(ends)} descents")
    print(f"   end= {min(e for _, e in ends):.1f}-{max(e for _, e in ends):.1f} mm, "
          f"median {statistics.median(e for _, e in ends):.1f}")
    print(f"   distance {min(d for d, _ in ends):.1f}-{max(d for d, _ in ends):.1f} cm")
    print(f"   pads-aimed rows n={len(dec)}: residual median "
          f"{statistics.median(d[0] for d in dec):.1f} mm, |dz| median "
          f"{statistics.median(d[3] for d in dec):.1f} mm, lateral median "
          f"{statistics.median((d[1] ** 2 + d[2] ** 2) ** 0.5 for d in dec):.1f} mm")

    # ---- 4b. the *current* indexed line ----------------------------------- #
    # `logs/fast/16_accept_indexed_v7.log` is the v7-default indexed acceptance
    # (`FRUIT_DYNAMIC_PICK=0`). On the current tree the pre-grasp target is
    # `free[2] = belt_top + cfg.grasp_clearance` (`tasks.py:8861`), i.e. the
    # reachable pick height - not the fruit's centre. This is the number that
    # decides whether the v1 40-90 mm still has a live instance.
    cur = read("logs/fast/16_accept_indexed_v7.log")
    cur_ends = end_values(cur)
    print(f"\n4b. the current indexed line (`logs/fast/16_accept_indexed_v7.log`): "
          f"n={len(cur_ends)}, end= {min(e for _, e in cur_ends):.1f}-"
          f"{max(e for _, e in cur_ends):.1f} mm, median "
          f"{statistics.median(e for _, e in cur_ends):.1f}")
    print(f"    its TCP target z = belt_top + grasp_clearance = "
          f"{belt_top + cfg.grasp_clearance:.4f} -> "
          f"{(cfg.grasp_clearance - FLOOR_P0) * 1000:.0f} mm above the P0 floor")

    # ---- 5. the baselines ------------------------------------------------- #
    acc = read("logs/p30a/01_accept_control.log")
    acc_ends = end_values(acc)
    mass = []
    for seed in ("10_seed11", "11_seed5", "12_seed23"):
        mass.extend(end_values(read(f"logs/p12a2/{seed}_mass.log")))
    print(f"\n5. baselines")
    print(f"   dynamic acceptance (`logs/p30a/01_accept_control.log`): n={len(acc_ends)}, "
          f"end= {min(e for _, e in acc_ends):.1f}-{max(e for _, e in acc_ends):.1f} mm, "
          f"median {statistics.median(e for _, e in acc_ends):.1f}")
    print(f"   mass base (`logs/p12a2/1*_mass.log`): n={len(mass)}, "
          f"end= {min(e for _, e in mass):.1f}-{max(e for _, e in mass):.1f} mm, "
          f"median {statistics.median(e for _, e in mass):.1f}")

    if "--assert" not in argv:
        return 0

    # ---- the pinned checks ------------------------------------------------ #
    print("\nASSERT")
    checks = [
        ("the pick point x=0.34 is inside the station band on both arms (<=6 mm)",
         all(res <= 6.0 for arm in ("left", "right")
             for dx, res in STATION_LADDER[arm] if abs(dx) < 1e-9)),
        ("the station band is clean to x=0.39 and cliffs at x=0.42 (>50 mm)",
         all(res <= 6.0 for arm in ("left", "right")
             for dx, res in STATION_LADDER[arm] if abs(dx - 0.05) < 1e-9)
         and all(res > 50.0 for arm in ("left", "right")
                 for dx, res in STATION_LADDER[arm] if abs(dx - 0.08) < 1e-9)),
        ("the aim is 17.3 mm inside the *measured* band at x=0.34..0.39, both arms",
         all(abs(m[0] - 0.0173) < 1e-3 and abs(m[1] - 0.0827) < 1e-3
             for key, m in margins.items() if key[1] >= 0.34)),
        ("the aim is 2.7 mm outside the code's 20 mm-inset band (both arms)",
         all(abs(m[2] + 0.0027) < 1e-3 for key, m in margins.items()
             if key[1] >= 0.34)),
        ("the vertical deficit at the P0 floor is 23.6-44.6 mm",
         abs(min(deficit_p0) - (FLOOR_P0 - r_max)) < 1e-9
         and abs(max(deficit_p0) - (FLOOR_P0 - r_min)) < 1e-9
         and 0.023 < min(deficit_p0) and max(deficit_p0) < 0.045),
        ("the dynamic aim clears the P0 floor by 25.4-46.4 mm over the r range",
         abs((r_min + STANDOFF - FLOOR_P0) - 0.0254) < 1e-3
         and abs((r_max + STANDOFF - FLOOR_P0) - 0.0464) < 1e-3),
        ("the measured fruit z is 1.185-1.203, so the aim clears the P0 floor by "
         "26.4-44.5 mm",
         abs(min(fz) - 1.1850) < 1e-3 and abs(max(fz) - 1.2031) < 1e-3
         and abs(margin_lo - 0.0264) < 1e-3 and abs(margin_hi - 0.0445) < 1e-3),
        ("the code's belt_margin is 17 mm optimistic against the 166 floor",
         abs((FLOOR_166 - FINGER_LEN) - 0.0168) < 1e-3),
        ("the indexed end= median is 40-90 mm (the v1 record)",
         40.0 <= statistics.median(e for _, e in ends) <= 90.0),
        ("the CURRENT indexed line's end= is <= 6 mm (the v1 record does not "
         "reproduce)",
         max(e for _, e in cur_ends) <= 6.0),
        ("the current indexed TCP target clears the P0 floor by 36 mm",
         abs((cfg.grasp_clearance - FLOOR_P0) - 0.0364) < 1e-3),
        ("the indexed end= is dominated by z (|dz| >= 30 mm)",
         statistics.median(d[3] for d in dec) >= 30.0),
        ("the mass-base end= median is 8-10 mm",
         8.0 <= statistics.median(e for _, e in mass) <= 10.0),
        ("the dynamic acceptance end= median is 8-12 mm",
         8.0 <= statistics.median(e for _, e in acc_ends) <= 12.0),
    ]
    bad = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")
    if bad:
        print(f"ASSERT: {len(bad)} failed")
        return 1
    print("ASSERT: all pinned numbers hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
