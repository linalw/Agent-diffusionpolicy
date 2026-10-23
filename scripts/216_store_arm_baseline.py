"""P34-B: the per-arm occluded-visibility baseline of the training stores.

Offline (numpy only; no simulator). For each store and **arm** it reads the
recorded `target_mask`, `fruit_position` and `joint_positions` and reports:

  * the first view: frame 0's along/x/diameter and mask, the first detectable
    frame (the first frame with a non-zero mask while the fruit is on the
    main belt), and the zero-mask share in the first-view window
    (along 0.40-0.50) vs the decision zone (along 0.15-0.30);
  * the rendered visible fraction vs (along, x): the mask area over the
    analytic **unoccluded** projected area of `212_occlusion_map.py` at the
    same (x, y, d), calibrated by the store's own p99.5 ratio (that is the
    segmentation-per-ray scale; a fully visible fruit sits at 1.0);
  * the belt-only expectation (`212`'s visible fraction) in the same bins, so
    `1 - rendered/212` isolates the foreground (arm) occlusion;
  * the frame-0 arm pose per arm: the active arm's joints (the robot's dof
    vector is interleaved left/right: [L1, R1, L2, R2, ...]), its distance to
    the `grasp` and `ready` waypoints of `configs/waypoints.json`, and the
    correlation of the pose with the fruit's along at frame 0 (a fixed grasp
    pose does not move with the fruit; a dynamic hover does);
  * `--ab DIR`: the direct env's rendered first call per arm from the
    `[align]` rows of an A/B batch (`logs/p34/A_ab/{A,B}_N.log`), joined to
    the `[rl] episode ... arm=` header - the same rendered measure, from the
    policy's own frames;
  * `--match ALONG,X,D`: the store frames within +-0.02 m of a pose, so the
    direct env's first call can be compared with the store at the *same*
    (along, x) - the Gate-2 B2 check.

Usage:

    python3 scripts/216_store_arm_baseline.py                 # both stores
    python3 scripts/216_store_arm_baseline.py --json out.json
    python3 scripts/216_store_arm_baseline.py --ab logs/p34/A_ab
    python3 scripts/216_store_arm_baseline.py --match 0.399 0.219 0.058
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import re

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BELT_TOP = 1.17
BELT_X = (0.11, 0.57)
#: The first-view window and the decision zone (P34 phase 1's windows).
FIRST_VIEW = (0.40, 0.50)
DECISION = (0.15, 0.30)


def load_map():
    path = os.path.join(ROOT, "scripts", "212_occlusion_map.py")
    spec = importlib.util.spec_from_file_location("occlusion_map_212", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BeltGrid:
    """Nearest-pose lookup of `212`'s belt-only visibility and unoccluded area.

    The analytic ray cast costs ~13 ms per pose; the stores carry tens of
    thousands of frames, so the map is sampled on a grid (x 0.04 m, along
    0.02 m, six diameters) and the frames take the nearest sample. The ratio
    `area / area_without` is smooth in x and d; along the band edges a 0.02 m
    nearest sample can misstate the belt fraction, which is why the bins are
    0.05 m wide and the medians are reported.
    """

    XS = np.arange(0.18, 0.401, 0.04)
    ALONGS = np.arange(0.10, 0.561, 0.02)
    DS = np.array([0.030, 0.040, 0.050, 0.060, 0.070, 0.080])

    def __init__(self, omap):
        self.omap = omap
        self.vis = np.full((len(self.XS), len(self.ALONGS), len(self.DS)), np.nan)
        self.area = np.full_like(self.vis, np.nan)

    def build(self) -> None:
        for i, x in enumerate(self.XS):
            for j, a in enumerate(self.ALONGS):
                for k, d in enumerate(self.DS):
                    r = self.omap.visible_fraction(float(x), float(a), float(d))
                    self.vis[i, j, k] = float(r.get("vis", np.nan))
                    self.area[i, j, k] = float(r.get("area_without", np.nan))

    def lookup(self, x: float, along: float, d: float):
        i = int(np.abs(self.XS - x).argmin())
        j = int(np.abs(self.ALONGS - along).argmin())
        k = int(np.abs(self.DS - d).argmin())
        return float(self.vis[i, j, k]), float(self.area[i, j, k])


def store_rows(store, limit=None):
    """Per-episode on-belt frames: along/x/d, mask area, active-arm q."""
    index = os.path.join(store, "index.json")
    if not os.path.exists(index):
        return []
    recs = json.load(open(index, encoding="utf-8"))
    if limit:
        recs = recs[:limit]
    rows = []
    for rec in recs:
        path = os.path.join(store, rec["file"])
        if not os.path.exists(path):
            continue
        try:
            z = np.load(path)
            mask = z["target_mask"]
            fp = np.asarray(z["fruit_position"], dtype=float)
            dof = np.asarray(z["joint_positions"], dtype=float)
        except Exception:
            continue
        if mask.ndim != 3:
            continue
        area = (mask > 0).reshape(len(mask), -1).sum(axis=1).astype(float)
        on_belt = (fp[:, 2] < BELT_TOP + 0.10) & (fp[:, 0] > BELT_X[0]) & (fp[:, 0] < BELT_X[1])
        arm = str(rec.get("arm", "?"))
        # The dof vector interleaves the two arms ([L1, R1, L2, R2, ...]);
        # the two-line stores label the arm per episode, so the active arm's
        # joints are every other entry of the first 14.
        q = dof[:, 0:14:2] if arm == "left" else dof[:, 1:14:2]
        rows.append(dict(
            file=path, rec=rec, area=area, y=fp[:, 1], x=fp[:, 0], z=fp[:, 2],
            d=float(rec.get("diameter", 0.0)), keep=on_belt, q=q,
            station_y=float(rec.get("station_y", 0.0) or 0.0), arm=arm,
        ))
    return rows


def frames(rows, grid):
    """Flatten the on-belt frames with the belt-only lookup."""
    out = []
    for r in rows:
        for i in np.where(r["keep"])[0]:
            along = float(r["y"][i]) - r["station_y"]
            x = float(r["x"][i])
            v212, aw = grid.lookup(x, along, r["d"])
            out.append(dict(arm=r["arm"], along=along, x=x, d=r["d"],
                            area=float(r["area"][i]), vis212=v212, aw=aw,
                            frame=int(i), file=r["file"]))
    return out


def scale_of(fr) -> float:
    """Segmentation px per analytic ray px: the store's p99.5 area/area_without."""
    ratio = [f["area"] / f["aw"] for f in fr
             if f["area"] > 0 and f["aw"] and f["aw"] > 0]
    return float(np.percentile(ratio, 99.5)) if ratio else 1.0


def table_along(fr, k, lo=0.10, hi=0.55, step=0.05):
    bins = np.arange(lo, hi + 1e-9, step)
    table = []
    for b in bins:
        sel = [f for f in fr if b <= f["along"] < b + step]
        if len(sel) < 10:
            continue
        area = np.array([f["area"] for f in sel], float)
        aw = np.array([f["aw"] for f in sel], float)
        v212 = np.array([f["vis212"] for f in sel], float)
        vis = np.where(aw > 0, np.minimum(1.0, area / (k * aw)), 0.0)
        ok = np.isfinite(v212)
        table.append(dict(along=float(b), n=len(sel), zero=float((area == 0).mean()),
                          vis=float(np.median(vis)), vis_p10=float(np.percentile(vis, 10)),
                          vis212=float(np.nanmedian(v212[ok])) if ok.any() else float("nan")))
    return table


def table_cross(fr, k, window, xs=(0.18, 0.26, 0.32, 0.38)):
    table = []
    for i in range(len(xs) - 1):
        sel = [f for f in fr if window[0] <= f["along"] < window[1]
               and xs[i] <= f["x"] < xs[i + 1]]
        if not sel:
            continue
        area = np.array([f["area"] for f in sel], float)
        aw = np.array([f["aw"] for f in sel], float)
        vis = np.where(aw > 0, np.minimum(1.0, area / (k * aw)), 0.0)
        table.append(dict(x=(xs[i], xs[i + 1]), n=len(sel),
                          zero=float((area == 0).mean()), vis=float(np.median(vis))))
    return table


def first_detectable(rows):
    out = []
    for r in rows:
        idx = np.where(r["keep"] & (r["area"] > 0))[0]
        if len(idx) == 0:
            continue
        i = idx[0]
        out.append(dict(along=float(r["y"][i]) - r["station_y"], x=float(r["x"][i]),
                        frame=int(i), area=float(r["area"][i]), d=r["d"]))
    return out


def first_view_frames(rows, grid, k):
    """Per episode: frame 0 and the first detectable frame, with rendered vis."""
    out = []
    for r in rows:
        idx = np.where(r["keep"] & (r["area"] > 0))[0]
        pick = [0] + ([int(idx[0])] if len(idx) and int(idx[0]) != 0 else [])
        for i in pick:
            along = float(r["y"][i]) - r["station_y"]
            x = float(r["x"][i])
            v212, aw = grid.lookup(x, along, r["d"])
            vis = (min(1.0, float(r["area"][i]) / (k * aw))
                   if aw and aw > 0 and r["area"][i] > 0 else 0.0)
            out.append(dict(frame=int(i), along=along, x=x, d=r["d"],
                            area=float(r["area"][i]), vis=vis, vis212=v212))
    return out


def pose_stats(rows, waypoints):
    """The active arm's frame-0 joints vs the grasp/ready waypoints."""
    arm = rows[0]["arm"] if rows else "?"
    q0 = np.array([r["q"][0] for r in rows])
    along0 = np.array([float(r["y"][0]) - r["station_y"] for r in rows])
    grasp = np.asarray(waypoints["arms"][arm]["grasp"], float)
    ready = np.asarray(waypoints["arms"][arm]["ready"], float)
    dg = np.abs(q0 - grasp[None, :]).max(axis=1)
    dr = np.abs(q0 - ready[None, :]).max(axis=1)
    # Which joint moves with the fruit's along at frame 0? (a fixed grasp pose
    # does not; the scripted dynamic hover does - it hovers at the intercept.)
    corr = []
    for j in range(q0.shape[1]):
        if q0[:, j].std() > 1e-9 and along0.std() > 1e-9:
            corr.append(float(np.corrcoef(q0[:, j], along0)[0, 1]))
        else:
            corr.append(0.0)
    return dict(arm=arm, n=len(rows),
                q0_mean=[float(v) for v in q0.mean(0)],
                q0_sd=[float(v) for v in q0.std(0)],
                to_grasp_max=[float(v) for v in dg],
                to_ready_max=[float(v) for v in dr],
                to_grasp_p50=float(np.median(dg)),
                to_ready_p50=float(np.median(dr)),
                corr_along=corr)


def ab_rows(path):
    """Per-arm first-call rows from an A/B batch's `[align]` lines."""
    out = []
    for name in sorted(glob.glob(os.path.join(path, "*.log"))):
        arm = "?"
        for line in open(name, encoding="utf-8", errors="replace"):
            m = re.search(r"\[rl\] episode (\d+): .* arm=(left|right) ", line)
            if m:
                arm = m.group(2)
            if "[align]" not in line:
                continue
            kv = dict(re.findall(r"(\w+)=([-\w.+]+)", line))
            try:
                out.append(dict(log=os.path.basename(name), arm=arm,
                                first=float(kv["first"]), x=float(kv["x"]),
                                d=float(kv["first_d"]), px=int(kv["first_px"]),
                                knob=int(kv["knob"]), calls=int(kv["calls"]),
                                reset=float(kv["reset"])))
            except (KeyError, ValueError):
                continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", action="append", default=[])
    ap.add_argument("--json", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ab", default="")
    ap.add_argument("--match", nargs=3, type=float, default=None,
                    metavar=("ALONG", "X", "D"))
    args = ap.parse_args()

    stores = args.store or ["datasets/demos_v11", "datasets/p33_pear"]
    omap = load_map()
    grid = BeltGrid(omap)
    grid.build()
    wp = json.load(open(os.path.join(ROOT, "configs", "waypoints.json"),
                        encoding="utf-8"))
    out = {"grid": dict(x=list(map(float, BeltGrid.XS)),
                        along=list(map(float, BeltGrid.ALONGS)),
                        d=list(map(float, BeltGrid.DS)))}

    for store in stores:
        rows = store_rows(store, limit=args.limit or None)
        if not rows:
            print(f"{store}: no index/rows")
            continue
        fr = frames(rows, grid)
        k = scale_of(fr)
        print(f"\n## {store}: {len(rows)} episodes, {len(fr)} on-belt frames, "
              f"segmentation scale k={k:.2f}")
        out[store] = {"k": k, "episodes": len(rows), "frames": len(fr), "arms": {}}
        for arm in ("left", "right"):
            rr = [r for r in rows if r["arm"] == arm]
            if not rr:
                continue
            fa = fr if False else [f for f in fr if f["arm"] == arm]
            fd = first_detectable(rr)
            ps = pose_stats(rr, wp)
            along0 = np.array([float(r["y"][0]) - r["station_y"] for r in rr])
            x0 = np.array([float(r["x"][0]) for r in rr])
            a0 = np.array([float(r["area"][0]) for r in rr])
            first = [f for f in fa if f["along"] >= FIRST_VIEW[0] - 0.05]
            dec = [f for f in fa if DECISION[0] <= f["along"] < DECISION[1]]
            print(f"\n### {arm}: n={len(rr)}")
            print(f"  frame 0: along p10 {np.percentile(along0,10):+.3f} p50 "
                  f"{np.median(along0):+.3f} p90 {np.percentile(along0,90):+.3f}; "
                  f"x p50 {np.median(x0):.3f}; zero-mask {(a0==0).mean():.2f}; "
                  f"median area {np.median(a0):.0f} px")
            if fd:
                a = np.array([f["along"] for f in fd])
                print(f"  first detectable: n={len(fd)} along min {a.min():+.3f} "
                      f"p10 {np.percentile(a,10):+.3f} p50 {np.median(a):+.3f} "
                      f"p90 {np.percentile(a,90):+.3f} max {a.max():+.3f}")
            for tag, sel in (("first view 0.40-0.50", first), ("decision zone 0.15-0.30", dec)):
                if not sel:
                    continue
                area = np.array([f["area"] for f in sel], float)
                aw = np.array([f["aw"] for f in sel], float)
                v212 = np.array([f["vis212"] for f in sel], float)
                vis = np.where(aw > 0, np.minimum(1.0, area / (k * aw)), 0.0)
                print(f"  {tag}: n={len(sel)} zero-mask {float((area==0).mean()):.2f} "
                      f"rendered vis p50 {np.median(vis):.2f} p10 {np.percentile(vis,10):.2f} "
                      f"| belt-only 212 p50 {np.nanmedian(v212):.2f} "
                      f"-> arm loss p50 {1-np.median(vis)/max(np.nanmedian(v212),1e-6):+.2f}")
            print(f"  frame-0 pose: |q-grasp|max p50 {ps['to_grasp_p50']:.3f} "
                  f"(max over episodes {max(ps['to_grasp_max']):.3f}); "
                  f"|q-ready|max p50 {ps['to_ready_p50']:.3f}")
            print("    q0 mean " + " ".join(f"{v:+.3f}" for v in ps["q0_mean"]))
            print("    q0 sd   " + " ".join(f"{v:.3f}" for v in ps["q0_sd"]))
            print("    corr(q0_j, along0) " + " ".join(f"{v:+.2f}" for v in ps["corr_along"]))
            ta = table_along(fa, k)
            fv = first_view_frames(rr, grid, k)
            f0 = [f for f in fv if f["frame"] == 0]
            fdf = [f for f in fv if f["frame"] != 0]
            for tag, grp in (("frame 0", f0), ("first detectable frame", fdf)):
                if not grp:
                    continue
                vis = np.array([f["vis"] for f in grp], float)
                al = np.array([f["along"] for f in grp], float)
                print(f"  {tag}: n={len(grp)} along p50 {np.median(al):+.3f} "
                      f"x p50 {np.median([f['x'] for f in grp]):.3f} "
                      f"rendered vis p50 {np.median(vis):.2f} "
                      f"p10 {np.percentile(vis, 10):.2f} "
                      f"zero-mask share {float((vis < 0.01).mean()):.2f}")
            print("\n    | along | n | zero | rendered vis p50 | p10 | 212 belt vis p50 |")
            print("    | --- | --- | --- | --- | --- | --- |")
            for t in ta:
                print(f"    | {t['along']:+.2f} | {t['n']} | {t['zero']:.2f} | "
                      f"{t['vis']:.2f} | {t['vis_p10']:.2f} | {t['vis212']:.2f} |")
            tc_f = table_cross(fa, k, FIRST_VIEW)
            tc_d = table_cross(fa, k, DECISION)
            print("    x split, first view 0.40-0.50: " + "; ".join(
                f"x{t['x'][0]:.2f}-{t['x'][1]:.2f} n={t['n']} zero={t['zero']:.2f} vis={t['vis']:.2f}"
                for t in tc_f) if tc_f else "    x split: (no frames)")
            print("    x split, decision 0.15-0.30: " + "; ".join(
                f"x{t['x'][0]:.2f}-{t['x'][1]:.2f} n={t['n']} zero={t['zero']:.2f} vis={t['vis']:.2f}"
                for t in tc_d) if tc_d else "    decision: (no frames)")
            out[store]["arms"][arm] = dict(
                n=len(rr), frame0_along=[float(np.percentile(along0, 10)),
                                         float(np.median(along0)),
                                         float(np.percentile(along0, 90))],
                frame0_x=float(np.median(x0)), frame0_zero=float((a0 == 0).mean()),
                first_detectable=[float(f["along"]) for f in fd],
                pose=ps, along_table=ta, first_x=tc_f, decision_x=tc_d,
                frame0=[dict(along=f["along"], x=f["x"], d=f["d"],
                             area=f["area"], vis=f["vis"]) for f in f0],
                first_detect=[dict(along=f["along"], x=f["x"], d=f["d"],
                                   area=f["area"], vis=f["vis"]) for f in fdf],
            )
            if args.match:
                a_m, x_m, d_m = args.match
                sel = [f for f in fa if abs(f["along"] - a_m) <= 0.02
                       and abs(f["x"] - x_m) <= 0.02]
                area = np.array([f["area"] for f in sel], float)
                aw = np.array([f["aw"] for f in sel], float)
                vis = np.where(aw > 0, np.minimum(1.0, area / (k * aw)), 0.0)
                print(f"  -- MATCH along {a_m:+.3f}+-0.02, x {x_m:.3f}+-0.02: "
                      f"n={len(sel)} zero-mask {float((area==0).mean()) if len(sel) else float('nan'):.2f} "
                      f"rendered vis p50 {np.median(vis) if len(sel) else float('nan'):.2f}")
                out[store]["arms"][arm]["match"] = dict(
                    n=len(sel), along=list(map(float, [f["along"] for f in sel])),
                    x=list(map(float, [f["x"] for f in sel])),
                    area=list(map(float, area)), vis=list(map(float, vis)))

    if args.ab:
        rows = ab_rows(args.ab)
        if rows:
            print(f"\n## {args.ab}: {len(rows)} first calls")
            out["ab"] = {}
            for arm in ("left", "right"):
                sel = [r for r in rows if r["arm"] == arm]
                if not sel:
                    continue
                vis = []
                for r in sel:
                    v212, aw = grid.lookup(r["x"], r["first"], r["d"])
                    r["vis212"], r["aw"] = v212, aw
                    vis.append(min(1.0, r["px"] / aw) if aw > 0 and r["px"] > 0 else 0.0)
                r0 = [r for r in sel if r["knob"] == 0]
                r1 = [r for r in sel if r["knob"] == 1]
                print(f"\n### {arm}: n={len(sel)}")
                for tag, grp in (("control (knob 0)", r0), ("aligned (knob 1)", r1)):
                    if not grp:
                        continue
                    first = np.array([r["first"] for r in grp])
                    vv = np.array([min(1.0, r["px"] / r["aw"]) if r["aw"] > 0 and r["px"] > 0 else 0.0
                                   for r in grp])
                    print(f"  {tag}: n={len(grp)} first along p50 {np.median(first):+.3f} "
                          f"x p50 {np.median([r['x'] for r in grp]):.3f} "
                          f"d p50 {np.median([r['d'] for r in grp])*1000:.0f}mm "
                          f"first_px p50 {np.median([r['px'] for r in grp]):.0f} "
                          f"rendered vis p50 {np.median(vv):.2f} "
                          f"(zero-mask share {float((vv < 0.01).mean()):.2f}) "
                          f"vis>=0.9 share {float((vv >= 0.9).mean()):.2f}")
                    out["ab"].setdefault(arm, {})[tag] = dict(
                        n=len(grp), first=[float(v) for v in first],
                        x=[float(r["x"]) for r in grp], px=[int(r["px"]) for r in grp],
                        vis=[float(v) for v in vv])

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
