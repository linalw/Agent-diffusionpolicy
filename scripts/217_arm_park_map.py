"""P35 phase 1: the offline arm-park / camera sightline map.

Answers one question with numbers: *for a fruit on the main belt, how much of it
does the inactive arm hide from the camera, and which park (or camera) removes
that?*

The input is `logs/p35/park_probe.py`: one rendered frame per candidate park at
the shipped head camera, each with the inactive arm's instance mask **and** the
depth frame. The fruit's disc is the analytic projection of a sphere at
(x, along) - the same camera model as `212_occlusion_map.py` - and a pixel
counts as covering it only if the arm's depth there is **in front of the fruit's
surface** (`depth < |eye - centre| - r`). The quoted coverage is therefore an
occlusion, not "an arm pixel shares the bbox" (the P34-B measure could not tell
those apart).

Everything is reported next to the two references:

  * **belt-only** = `212`'s own visible fraction at the same pose, so
    `visible = belt * (1 - arm_cover)` and the two occluders stay separable;
  * **the shipped park** (`ready`, candidate 0), which is the pose every
    recorded single-arm demo carries.

The camera poses are *rendered* too (`PROBE_CAMERAS_PASS=1`, one `RtxCamera` per
pose, the shipped pose included as its own camera for the equivalence check).
An analytic capsule model of the arm was written first and rejected: against the
rendered silhouette it read up to +1.00 optimistic on the left arm (mean +0.37
over the measured grid) because a link's area-fitted capsule is thinner than the
real link housing. The numbers here are the renders.

    python3 scripts/217_arm_park_map.py                # the park table
    python3 scripts/217_arm_park_map.py --cameras      # + the camera table
    python3 scripts/217_arm_park_map.py --json logs/p35/20_map.json

Offline (numpy only, no simulator).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWEEP = os.path.join(ROOT, "logs/p35/park_sweep.json")
MASKS = os.path.join(ROOT, "logs/p35/park_masks.npz")
BELT_TOP = 1.17

#: The fruit stream the map scores. `x` is across the belt (the supply's band is
#: 0.21-0.36, the reach band 0.18-0.39); `along` is the fruit's y minus the pick
#: station. The first view is 0.40-0.50, the approach 0.30-0.45, the trigger's
#: decision zone 0.15-0.30 (`logs/p34/B_READ.md`; `212`'s FIRE_Y 0.301).
XS = (0.19, 0.21, 0.23, 0.26, 0.30, 0.34, 0.36)
ALONGS = (0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55)
DIAMETERS = (0.045, 0.058)
OUTER_X = 0.26          # the surviving P34-B occlusion band: x < 0.26
PEAR = (0.219, 0.399, 0.068)   # x, along, d - the P34-B right-arm fruit (68 mm)


def zkey(key: str) -> str:
    """`park_masks.npz` key for a `side:park[:tag]` name (numpy forbids `:`)."""
    return key.replace(":", "__")


def load_212():
    path = os.path.join(ROOT, "scripts", "212_occlusion_map.py")
    spec = importlib.util.spec_from_file_location("occlusion_map_212", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fruit_disc(omap, cam, x, y, d):
    """Boolean pixel mask of a sphere at (x, y, BELT_TOP + d/2)."""
    eye = np.asarray(cam.get("eye", omap.EYE), float)
    target = np.asarray(cam.get("target", omap.TARGET), float)
    res = tuple(int(v) for v in cam.get("res", omap.RES))
    fx, fy, cx, cy = omap.intrinsics(res, cam.get("focal", omap.FOCAL),
                                    cam.get("aperture", omap.APERTURE))
    R = omap.basis(eye, target)
    r = d / 2.0
    centre = np.array([x, y, BELT_TOP + r])
    pc = omap.project_point(centre, R, eye, fx, fy, cx, cy)
    if pc is None:
        return None, centre, float("inf")
    win = omap._window(pc[0], pc[1], half=60)
    if win is None:
        return None, centre, float("inf")
    rows, cols = win
    dirs = omap.ray_dirs(cols.astype(float) + 0.5, rows.astype(float) + 0.5,
                         R, fx, fy, cx, cy)
    t = omap.ray_sphere(eye, dirs, centre, r)
    hit = np.isfinite(t)
    mask = np.zeros(res, dtype=bool)
    mask[rows[hit], cols[hit]] = True
    return mask, centre, float(np.linalg.norm(centre - eye))


def arm_cover(mask, depth, disc, centre, r, eye):
    """Fraction of the fruit's disc covered by *front* arm pixels."""
    if disc is None:
        return float("nan"), 0
    n = int(disc.sum())
    if n == 0:
        return float("nan"), 0
    if depth.shape != disc.shape:
        return float("nan"), n
    d_fruit = float(np.linalg.norm(np.asarray(centre, float) - np.asarray(eye, float)))
    front = depth < (d_fruit - r - 0.002)
    return float((mask & disc & front).sum()) / float(n), n


def build_grid(omap, cam):
    grid = []
    for x in XS:
        for a in ALONGS:
            for d in DIAMETERS:
                disc, centre, dist = fruit_disc(omap, cam, x, a, d)
                belt = float(omap.visible_fraction(x, a, d)["vis"])
                grid.append(dict(x=x, along=a, d=d, disc=disc, centre=centre,
                                 dist=dist, belt=belt))
    return grid


def score(grid, mask, depth, cam):
    eye = np.asarray(cam["eye"], float)
    cov = np.array([arm_cover(mask, depth, g["disc"], g["centre"], g["d"] / 2.0, eye)[0]
                    for g in grid])
    xs = np.array([g["x"] for g in grid])
    al = np.array([g["along"] for g in grid])
    dd = np.array([g["d"] for g in grid])
    belt = np.array([g["belt"] for g in grid])
    stream = (dd > 0.05) & (al >= 0.20)
    outer = stream & (xs < OUTER_X)
    first = stream & (al >= 0.40)
    decide = stream & (al < 0.30)
    return dict(
        stream=float(np.nanmean(cov[stream])),
        outer=float(np.nanmean(cov[outer])),
        first=float(np.nanmean(cov[first])),
        decide=float(np.nanmean(cov[decide])),
        worst=float(np.nanmax(cov[stream])),
        #: The arm's *marginal* cost: the share of the stream the belt alone
        #: would have shown and the arm hides. `visible` is what is left, both
        #: occluders in: `belt * (1 - cover)`. A park that only hides the
        #: belt-hidden upstream corner has a near-zero cost.
        arm_cost=float(np.nanmean(belt[stream] * cov[stream])),
        visible=float(np.nanmean(belt[stream] * (1.0 - cov[stream]))),
        belt_lost=float(np.nanmean(1.0 - belt[stream])),
        by_along={str(a): float(np.nanmean(cov[stream & (al == a)])) for a in ALONGS},
        by_x={str(x): float(np.nanmean(cov[stream & (xs == x)])) for x in XS},
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--cameras", action="store_true")
    args = ap.parse_args()

    omap = load_212()
    sweep = json.load(open(SWEEP, encoding="utf-8"))
    zp = np.load(MASKS)
    cam = dict(sweep["camera"])
    cam["res"] = [int(v) for v in cam["res"]]
    print(f"# 217: probe {os.path.relpath(SWEEP, ROOT)} "
          f"({len(sweep['sides'].get('left', []))} left / "
          f"{len(sweep['sides'].get('right', []))} right parks), masks "
          f"{os.path.relpath(MASKS, ROOT)} ({len(zp.files)} arrays)")
    print(f"# camera eye={cam['eye']} target={cam['target']} res={cam['res']} "
          f"focal={cam['focal']}")
    print(f"# grid: x {XS} x along {ALONGS} x d {DIAMETERS} "
          f"({len(XS) * len(ALONGS) * len(DIAMETERS)} poses/arm)")

    grid = build_grid(omap, cam)
    # The pear: reported separately at its own diameter.
    pear_disc, pear_centre, pear_dist = fruit_disc(omap, cam, PEAR[0], PEAR[1], PEAR[2])
    pear_belt = float(omap.visible_fraction(PEAR[0], PEAR[1], PEAR[2])["vis"])

    out = {"camera": cam, "grid": dict(x=list(XS), along=list(ALONGS),
                                       d=list(DIAMETERS),
                                       pear=dict(x=PEAR[0], along=PEAR[1], d=PEAR[2],
                                                 belt=pear_belt)),
           "parks": {}}

    for side, rows in sweep["sides"].items():
        parks = {}
        print(f"\n## {side} (inactive arm) - shipped head camera, rendered")
        print("| park | hold | px | zmin | in belt | gap active | gap body | ee clr | "
              "arm cost | stream cover | outer | first | decision | pear |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | "
              "--- | --- | --- |")
        for row in rows:
            mask = zp[zkey(f"{side}:{row['name']}")]
            depth = zp[zkey(f"{side}:{row['name']}:depth")].astype(np.float32)
            s = score(grid, mask, depth, cam)
            pc, pn = arm_cover(mask, depth, pear_disc, pear_centre, PEAR[2] / 2.0,
                               np.asarray(cam["eye"], float))
            # The hand's height: the ee_tcp is the fingertip level (it sits
            # 0.078 m below the jaw centre), so `ee_z - BELT_TOP` is the
            # clearance of the lowest point when the hand is over the belt.
            ee = np.asarray(row["poses"]["ee_tcp"], float)
            hand_over_belt = (0.11 <= ee[0] <= 0.57) and (-0.80 <= ee[1] <= 0.80)
            ee_clear = float(ee[2] - BELT_TOP) if hand_over_belt else float("nan")
            parks[row["name"]] = dict(
                hold=row["hold"], px=row["arm_px"], zmin=row["zmin"],
                in_belt=row["in_belt_footprint"], gap=row["other_link_gap"],
                body_gap=row.get("body_gap", float("nan")),
                jaw=row["jaw"], ee=ee.tolist(), ee_clear=ee_clear,
                pear=float(pc), pear_visible=float(pear_belt * (1.0 - pc)),
                pear_belt=pear_belt, **{k: v for k, v in s.items()})
            print(f"| {row['name']} | {row['hold']:.4f} | {row['arm_px']} "
                  f"| {row['zmin']:.3f} | {','.join(row['in_belt_footprint']) or '-'} "
                  f"| {row['other_link_gap']:.3f} | {row.get('body_gap', float('nan')):.3f} "
                  f"| {'%.3f' % ee_clear if ee_clear == ee_clear else 'out'} "
                  f"| {s['arm_cost']:.3f} | {s['stream']:.2f} | {s['outer']:.2f} "
                  f"| {s['first']:.2f} | {s['decide']:.2f} | {pc:.2f} |")
        out["parks"][side] = parks

    # The along/x profiles of the best few parks, so a relocation of the
    # occlusion cannot hide behind a single mean.
    print("\n## Where the occlusion is (stream coverage by along, d=58 mm rows)")
    print("| side | park | " + " | ".join(f"{a:+.2f}" for a in ALONGS) + " |")
    print("| --- | --- | " + " | ".join("---" for _ in ALONGS) + " |")
    for side, rows in sweep["sides"].items():
        ranked = sorted(rows, key=lambda r: out["parks"][side][r["name"]]["stream"])
        for row in [r for r in rows if r["name"] == "ready"] + ranked[:4]:
            s = out["parks"][side][row["name"]]
            print(f"| {side} | {row['name']} | " +
                  " | ".join(f"{s['by_along'][str(a)]:.2f}" for a in ALONGS) + " |")

    if args.cameras and "cameras" in sweep:
        print("\n## The camera alternatives (rendered; inactive arm at `ready`)")
        print("| side | camera | stream cover | outer | first | pear 68 mm | arm cost "
              "| visible (belt+arm) | belt-only loss |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        out["cameras"] = {}
        for side in sweep["sides"]:
            for cname, spec in sweep["cameras"].items():
                key = zkey(f"cam:{side}:ready:{cname}")
                if key not in zp.files:
                    continue
                mask = zp[key]
                depth = zp[zkey(f"cam:{side}:ready:{cname}:depth")].astype(np.float32)
                gcam = dict(eye=spec["eye"], target=spec["target"], focal=spec["focal"],
                            aperture=spec["aperture"], res=spec["res"])
                g = build_grid(omap, gcam)
                s = score(g, mask, depth, gcam)
                pd, pc_, _ = fruit_disc(omap, gcam, PEAR[0], PEAR[1], PEAR[2])
                pcover, _ = arm_cover(mask, depth, pd, pc_, PEAR[2] / 2.0,
                                      np.asarray(gcam["eye"], float))
                out["cameras"].setdefault(side, {})[cname] = dict(
                    stream=s["stream"], outer=s["outer"], first=s["first"],
                    pear=float(pcover), arm_cost=s["arm_cost"],
                    visible=s["visible"], belt_lost=s["belt_lost"])
                print(f"| {side} | {cname} | {s['stream']:.2f} | {s['outer']:.2f} "
                      f"| {s['first']:.2f} | {pcover:.2f} | {s['arm_cost']:.3f} "
                      f"| {s['visible']:.2f} | {s['belt_lost']:.2f} |")
        # The equivalent-camera check: the shipped pose through its own camera
        # against the head camera's own mask.
        print("\n## The extra-camera check (shipped pose, shipped camera vs "
              "`shipped` RtxCamera)")
        for side in sweep["sides"]:
            ka, kb = zkey(f"{side}:ready"), zkey(f"cam:{side}:ready:shipped")
            a = zp[ka] if ka in zp.files else None
            b = zp[kb] if kb in zp.files else None
            if a is None or b is None:
                continue
            inter = int((a & b).sum())
            print(f"| {side} | head {int(a.sum())} px | RtxCamera {int(b.sum())} px "
                  f"| IoU {inter / max(int((a | b).sum()), 1):.3f} |")

    if args.json:
        path = args.json if os.path.isabs(args.json) else os.path.join(ROOT, args.json)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)
        print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
