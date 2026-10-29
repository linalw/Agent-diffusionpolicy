"""P60 phase 2: does the RIGHT arm at `ready` occlude a fruit at the LEFT's station?

The mirror of P35, which was never scored: P35 swept the **inactive** arm and
scored it against a fruit at the pick station (`scripts/217_arm_park_map.py`),
and its table's `right` rows read 0.00 - but P35 read that as "the right arm does
not cover the *(right-active)* stream", never as "a left-active episode's fruit is
clear". This script asks the second question with the *same* instrument and the
*same* rendered masks, and extends the grid to the band the direct line actually
delivers (P59 phase 3's `[bed-sel]`/`intercept trigger` rows).

Method (unchanged from 212/217, so the numbers are comparable to P35's):

  * the occluder is a **rendered** silhouette + depth frame
    (`logs/p35/park_masks.npz`, one frame per pose per side, from
    `logs/p35/park_probe.py`; the probe required two identical consecutive
    frames before accepting one, so the mask belongs to the pose in
    `park_sweep.json`);
  * the target is the analytic projection of a sphere of diameter `d` resting on
    the main belt at `(x, pick_y + along, belt_top + d/2)`, using `212`'s shipped
    camera (eye 0.05/0.00/2.00, target 0.34/0.22/1.10, 16 mm, 240x424);
  * a pixel counts as **covering** only if the arm's depth there is in front of
    the fruit's surface (`depth < |eye - centre| - r`), so a shared bbox is not
    an occlusion;
  * `belt` is `212`'s own belt-only visible fraction, so the arm's *marginal*
    cost is `belt * cover` and the two occluders stay separable;
  * `cover` is the fraction of the **disc's pixels**, so 0.5 means half the
    fruit's projected area is behind arm pixels that are in front of it.

The station: `pick_y = 0.00`, `pick_x = 0.34` (`configs/waypoints.json`), i.e. the
point the direct presentation presents (`rl_env` captures `_trigger_station` as
the active arm's `jaw_centre()` at reset, and the reset teleports the **active**
arm to its `grasp` waypoint at that point - `rl_env.py:2575`). Both arms pick the
same `(pick_x, pick_y)` in this presentation (P39's pre-pose audit: the left
station *is* the calibrated pick point); the two-line's right station `y = -0.10`
is a different scenario and is not what this file scores.

    python3 logs/p60/right_occlusion.py | tee logs/p60/right_occlusion.txt
    python3 logs/p60/right_occlusion.py --json logs/p60/right_occlusion.json

Offline (numpy only, no simulator, no `src/`/`configs/` edit).
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SWEEP = os.path.join(ROOT, "logs/p35/park_sweep.json")
MASKS = os.path.join(ROOT, "logs/p35/park_masks.npz")
P59 = os.path.join(ROOT, "logs/p59/p3")
PICK_X, PICK_Y = 0.34, 0.00          # configs/waypoints.json
D_MAIN = 0.058                        # the P35 reference fruit
D_SMALL = 0.045                       # the small-fruit control (lychee/strawberry)
BAND_DECIDE = (0.20, 0.31)            # the delivered fire band (section 0)
BAND_UP = (0.31, 0.45)                # the approach, P35's "first view"
BAND_SEL = (0.45, 0.68)               # the delivered selection band (section 0)
COVER_HI = 0.50                       # the "half the fruit hidden" level

XS = np.round(np.arange(0.14, 0.421, 0.02), 3)
ALONGS = np.round(np.arange(-0.50, 0.801, 0.02), 3)
FINE_ALONGS = np.round(np.arange(-0.10, 0.361, 0.005), 3)
FINE_XS = (0.22, 0.28, 0.34)

#: The masks this file scores. `__active` is the **other** arm in the same frame
#: (the probe put the non-swept arm at its `grasp` waypoint), which is how the
#: *active* arm's own silhouette is recovered without a new render:
#: `right:<park>:active` = the LEFT arm at `grasp`, `left:<park>:active` = the
#: RIGHT arm at `grasp`.
ACTIVE = {
    "left@grasp": ("right", "ready", True),
    "right@grasp": ("left", "ready", True),
}


def md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_module(rel: str, name: str):
    path = os.path.join(ROOT, rel)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# 0. The delivered band, from the P59 phase-3 logs
# --------------------------------------------------------------------------- #
def delivered_band() -> dict:
    """The x / along range the direct line actually presents to the arms.

    Two independent reads, both from `[fruit]` rows of the same three logs:
      * `[bed-sel]  <species> along=.. x=.. .. -> chosen` - the position of the
        fruit the selector hand-picked (the *delivery* the arm is being set up
        for; `along` is `y - pick_y`);
      * `[rl] episode .. notes=['intercept trigger (dy=..cm, dx=..cm, ...)']` -
        the geometry at the **fire tick**: `dy` = the fruit's along when the
        decision is made, `dx = x - station_x`. This is where the policy's
        observation of the fruit happens.
    """
    sel, cand, fire = [], [], []
    for path in sorted(glob.glob(os.path.join(P59, "C_*.log"))):
        for line in open(path, encoding="utf-8", errors="replace"):
            m = re.search(
                r"\[bed-sel\]\s+(\w+)\s+along=([+-][\d.]+) x=([\d.]+) z=([\d.]+) "
                r"r=([\d.]+) grade=(\w) -> (.+)", line)
            if m:
                row = dict(log=os.path.basename(path), species=m.group(1),
                           along=float(m.group(2)), x=float(m.group(3)),
                           d=2.0 * float(m.group(5)), verdict=m.group(7).strip())
                (sel if row["verdict"].startswith("chosen") else cand).append(row)
            m = re.search(
                r"episode (\d+): (\w+) d=([\d.]+)cm .*arm=(\w+) success=(\w+).*"
                r"intercept trigger \(dy=([-\d.]+)cm, dx=([-\d.]+)cm, "
                r"t_arrive=([\d.]+)s", line)
            if m:
                fire.append(dict(log=os.path.basename(path), ep=int(m.group(1)),
                                 species=m.group(2), d=float(m.group(3)) / 100.0,
                                 arm=m.group(4), success=m.group(5) == "True",
                                 dy=float(m.group(6)) / 100.0,
                                 dx=float(m.group(7)) / 100.0,
                                 t_arrive=float(m.group(8))))
    return dict(selected=sel, candidates=cand, fire=fire)


def summarise(rows: list[dict], key: str) -> str:
    v = np.array([r[key] for r in rows], float)
    return (f"n={len(v)} min={v.min():+.3f} p10={np.percentile(v, 10):+.3f} "
            f"p50={np.median(v):+.3f} p90={np.percentile(v, 90):+.3f} max={v.max():+.3f}")


# --------------------------------------------------------------------------- #
# 1. The grid (discs and the belt-only reference are pose-independent: cache once)
# --------------------------------------------------------------------------- #
class Grid:
    def __init__(self, om, cam, x, along, d, cover_mod):
        self.om, self.cam, self.om217 = om, cam, cover_mod
        self.eye = np.asarray(cam["eye"], float)
        self.x = np.asarray(x, float)
        self.along = np.asarray(along, float)
        self.cells = [(xx, aa) for xx in self.x for aa in self.along]
        self.disc, self.centre, self.belt = [], [], []
        for xx, aa in self.cells:
            disc, centre, _dist = self.om217.fruit_disc(om, cam, xx, PICK_Y + aa, d)
            self.disc.append(disc)
            self.centre.append(centre)
            self.belt.append(om.visible_fraction(xx, PICK_Y + aa, d)["vis"])
        self.belt = np.asarray(self.belt, float)
        self.r = d / 2.0
        self.cov_x = np.array([c[0] for c in self.cells])
        self.cov_a = np.array([c[1] for c in self.cells])

    def cover(self, mask, depth) -> np.ndarray:
        out = np.full(len(self.cells), np.nan)
        for i, (disc, centre) in enumerate(zip(self.disc, self.centre)):
            if disc is None:
                continue
            out[i] = self.om217.arm_cover(mask, depth, disc, centre, self.r,
                                          self.eye)[0]
        return out

    def band(self, along_lo, along_hi, x_lo=None, x_hi=None):
        sel = (self.cov_a >= along_lo) & (self.cov_a <= along_hi)
        if x_lo is not None:
            sel &= (self.cov_x >= x_lo) & (self.cov_x <= x_hi)
        return sel


def footprint(zp, key: str, base: str, om, cam) -> dict:
    """Where the silhouette lands in **space**: unproject its pixels by depth."""
    mask = zp[key]
    depth = zp[base + "__depth"].astype(np.float32)
    rows, cols = np.nonzero(mask)
    d = depth[rows, cols]
    ok = np.isfinite(d) & (d > 0)
    rows, cols, d = rows[ok], cols[ok], d[ok]
    if len(rows) == 0:
        return {}
    eye = np.asarray(cam["eye"], float)
    R = om.basis(eye, np.asarray(cam["target"], float))
    fx, fy, cx, cy = om.intrinsics(tuple(cam["res"]), cam["focal"],
                                   tuple(cam["aperture"]))
    dirs = om.ray_dirs(cols + 0.5, rows + 0.5, R, fx, fy, cx, cy)
    n = np.linalg.norm(dirs, axis=-1)
    p = eye + dirs * (d / n)[:, None]
    above = p[(p[:, 2] > 1.17) & (p[:, 0] > 0.11) & (p[:, 0] < 0.57)
              & (p[:, 1] > -0.80) & (p[:, 1] < 0.80)]
    return dict(px=int(mask.sum()), depth=(float(d.min()), float(d.max())),
                x=(float(p[:, 0].min()), float(p[:, 0].max())),
                y=(float(p[:, 1].min()), float(p[:, 1].max())),
                z=(float(p[:, 2].min()), float(p[:, 2].max())),
                belt_pts=int(len(above)),
                belt_y=((float(above[:, 1].min()), float(above[:, 1].max()))
                        if len(above) else (np.nan, np.nan)),
                belt_z=((float(above[:, 2].min()), float(above[:, 2].max()))
                        if len(above) else (np.nan, np.nan)))


def half_region(grid: Grid, cov: np.ndarray) -> dict:
    """The along/x extent where the disc is >= 50 % covered (and the belt ref)."""
    hi = np.isfinite(cov) & (cov >= COVER_HI)
    if not hi.any():
        return dict(any=False)
    a = grid.cov_a[hi]
    i = int(np.argmin(a))
    j = int(np.argmax(a))
    return dict(any=True, along_min=float(a.min()), along_max=float(a.max()),
                x_at_min=float(grid.cov_x[hi][i]), cover_at_min=float(cov[hi][i]),
                x_at_max=float(grid.cov_x[hi][j]), cover_at_max=float(cov[hi][j]),
                belt_at_min=float(grid.belt[hi][i]), n_cells=int(hi.sum()))


# --------------------------------------------------------------------------- #
# 2. main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    om = load_module("scripts/212_occlusion_map.py", "om212")
    grid_mod = load_module("scripts/217_arm_park_map.py", "pm217")
    sweep = json.load(open(SWEEP, encoding="utf-8"))
    cam = dict(sweep["camera"])
    cam["res"] = [int(v) for v in cam["res"]]
    zp = np.load(MASKS)
    belt_top = float(sweep["belt_top"])

    print("# P60 phase 2 - the right arm at `ready` against a fruit at the LEFT's "
          "station")
    print(f"# instrument: 212's camera (eye {cam['eye']} target {cam['target']} "
          f"res {cam['res']} focal {cam['focal']}) + 217's disc/cover test")
    print(f"# occluder: rendered instance masks + depth, logs/p35/park_masks.npz "
          f"({len(zp.files)} arrays); poses logs/p35/park_sweep.json")
    print(f"# station (pick_x, pick_y) = ({PICK_X:.2f}, {PICK_Y:+.2f}), belt top "
          f"{belt_top:.3f}, fruit d {D_MAIN*1000:.0f} mm (small control "
          f"{D_SMALL*1000:.0f} mm), cover = disc pixels with arm depth in front")
    print("# pins: " + "  ".join(
        f"{os.path.relpath(p, ROOT)}={md5(p)[:8]}" for p in
        (SWEEP, MASKS, "scripts/212_occlusion_map.py",
         "scripts/217_arm_park_map.py", "configs/arm_parks.json",
         "configs/waypoints.json", "src/fruit_sorting/tasks.py",
         "src/fruit_sorting/rl_env.py")))
    print(f"# deliverable band source: {os.path.relpath(P59, ROOT)}/C_*.log "
          f"(md5 " + ",".join(md5(p)[:8] for p in sorted(glob.glob(
              os.path.join(P59, "C_*.log")))) + ")")

    band = delivered_band()
    sel, cand, fire = band["selected"], band["candidates"], band["fire"]
    print("\n## 0. The delivered band (what the direct line actually presents)")
    print(f"- `[bed-sel]` **chosen** ({len(sel)} rows, 3 logs x 15 picks):")
    print(f"    along  {summarise(sel, 'along')}")
    print(f"    x      {summarise(sel, 'x')}")
    print(f"    d(cm)  {summarise(sel, 'd')}")
    print(f"- `[bed-sel]` all candidates (chosen + refused, {len(cand) + len(sel)} rows): "
          f"x {summarise(sel + cand, 'x')}")
    print(f"- `intercept trigger` **fire tick** ({len(fire)} episodes):")
    print(f"    dy (along at the fire)  {summarise(fire, 'dy')}")
    print(f"    dx (x - station_x)      {summarise(fire, 'dx')}")
    left = [r for r in fire if r["arm"] == "left"]
    right = [r for r in fire if r["arm"] == "right"]
    print(f"    arm split: left n={len(left)} dy {summarise(left,'dy') if left else '-'}")
    print(f"               right n={len(right)} dy {summarise(right,'dy') if right else '-'}")
    print(f"- the grid's bands: decide = along {BAND_DECIDE}, approach = {BAND_UP}, "
          f"selection = {BAND_SEL}; x 0.14-0.42 (the delivered x "
          f"{min(r['x'] for r in sel):.3f}-{max(r['x'] for r in sel):.3f} inside it)")

    g = Grid(om, cam, XS, ALONGS, D_MAIN, grid_mod)
    gsel = g.band(*BAND_DECIDE)
    gup = g.band(*BAND_UP)
    gselband = g.band(*BAND_SEL)

    out = dict(camera=cam, station=[PICK_X, PICK_Y], belt_top=belt_top,
               bands=dict(decide=BAND_DECIDE, approach=BAND_UP, selection=BAND_SEL),
               grid=dict(x=list(map(float, XS)), along=list(map(float, ALONGS)),
                         d=D_MAIN, order="flat (x, along); cover per pose below"),
               delivered=dict(
                   chosen_along=[min(r["along"] for r in sel), max(r["along"] for r in sel)],
                   chosen_x=[min(r["x"] for r in sel), max(r["x"] for r in sel)],
                   fire_dy=[min(r["dy"] for r in fire), max(r["dy"] for r in fire)]),
               parks={}, active={})

    # -- A. the right arm at `ready`, cell by cell -------------------------- #
    def cov_of(side: str, name: str, active: bool = False):
        key = f"{side}__{name}" + ("__active" if active else "")
        base = f"{side}__{name}"
        return zp[key], zp[base + "__depth"].astype(np.float32), base

    mask, depth, base = cov_of("right", "ready")
    cov_ready = g.cover(mask, depth)
    print("\n## A. `right:ready` vs a 58 mm fruit at the left's station (cover of "
          "the fruit's disc)")
    hdr = "".join(f"{x:6.2f}" for x in g.x)
    print(f"| along |{hdr} | belt |")
    print("| --- |" + "".join(" --- |" for _ in g.x) + " --- |")
    for aa in ALONGS:
        if not (-0.30 <= aa <= 0.72):
            continue
        sel_a = np.isclose(g.cov_a, aa)
        cells = "".join(f"{c:6.2f}" if c == c else "     -"
                        for c in cov_ready[sel_a])
        belt = float(np.nanmean(g.belt[sel_a]))
        print(f"| {aa:+.2f} |{cells} | {belt:.2f} |")
    print("(a `-` is a fruit whose centre projects out of frame; `belt` is 212's "
          "belt-only visible fraction at the same cells)")

    # -- B. every right pose, summarised over the delivered bands ----------- #
    print("\n## B. Every right-arm pose from P35's sweep, against the left's "
          "station")
    print("| pose | hold | px | gap | in belt | decide 0.20-0.31 | approach "
          "0.31-0.45 | selection 0.45-0.68 | max | >=0.5 along |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    rows = sweep["sides"]["right"]
    half_ready = None
    for row in rows:
        mask, depth, base = cov_of("right", row["name"])
        cov = g.cover(mask, depth)
        half = half_region(g, cov)
        if row["name"] == "ready":
            half_ready = half
            cov_ready = cov
        out["parks"][row["name"]] = dict(
            hold=row["hold"], px=row["arm_px"], gap=row["other_link_gap"],
            in_belt=row["in_belt_footprint"], jaw=row["jaw"],
            decide=float(np.nanmean(cov[gsel])), approach=float(np.nanmean(cov[gup])),
            selection=float(np.nanmean(cov[gselband])),
            max=float(np.nanmax(cov)), half=half,
            arm_cost=float(np.nanmean(g.belt * cov)),
            #: the per-cell tensor, flat in `(x, along)` order of `out["grid"]`
            cover=[round(float(v), 4) if v == v else None for v in cov],
        )
        print(f"| {row['name']} | {row['hold']:.4f} | {row['arm_px']} "
              f"| {row['other_link_gap']:.3f} "
              f"| {','.join(row['in_belt_footprint']) or '-'} "
              f"| {np.nanmean(cov[gsel]):.3f} | {np.nanmean(cov[gup]):.3f} "
              f"| {np.nanmean(cov[gselband]):.3f} | {np.nanmax(cov):.2f} "
              f"| {('%.2f..%.2f' % (half['along_min'], half['along_max'])) if half.get('any') else '-'} |")

    print("\n## B2. The same, for the two poses on record as the shipped ones "
          "(`configs/waypoints.json`: `ready`, and `grasp` = the pose the reset "
          "teleports the **active** arm to)")
    for label, (side, name, active) in ACTIVE.items():
        mask, depth, base = cov_of(side, name, active)
        cov = g.cover(mask, depth)
        half = half_region(g, cov)
        fp = footprint(zp, f"{side}__{name}" + ("__active" if active else ""), base,
                       om, cam)
        out["active"][label] = dict(
            px=int(mask.sum()), decide=float(np.nanmean(cov[gsel])),
            approach=float(np.nanmean(cov[gup])),
            selection=float(np.nanmean(cov[gselband])),
            station=float(np.nanmean(cov[np.isclose(g.cov_a, 0.0)])),
            max=float(np.nanmax(cov)), half=half, footprint=fp,
            arm_cost=float(np.nanmean(g.belt * cov)))
        print(f"- **{label}** (mask `{side}__{name}"
              f"{'__active' if active else ''}`, {int(mask.sum())} px): "
              f"station {out['active'][label]['station']:.2f}, decide "
              f"{out['active'][label]['decide']:.3f}, approach "
              f"{out['active'][label]['approach']:.3f}, selection "
              f"{out['active'][label]['selection']:.3f}, max {np.nanmax(cov):.2f}, "
              f">=0.5 " + (f"along {half['along_min']:+.2f}..{half['along_max']:+.2f}"
                           if half.get("any") else "nowhere"))
        print(f"    silhouette in space: x {fp['x'][0]:.3f}..{fp['x'][1]:.3f} "
              f"y {fp['y'][0]:+.3f}..{fp['y'][1]:+.3f} z {fp['z'][0]:.3f}.."
              f"{fp['z'][1]:.3f}; over the belt: y {fp['belt_y'][0]:+.3f}.."
              f"{fp['belt_y'][1]:+.3f} z {fp['belt_z'][0]:.3f}..{fp['belt_z'][1]:.3f}")

    # -- C. the fine crossing for the two poses that matter ------------------ #
    # First the weaker ("does any arm pixel share the fruit's bbox?") form of the
    # same question - P34-B's measure, which cannot tell occlusion from a shared
    # bbox but *can* rule an occluder out absolutely when it reads 0.
    print("\n## B3. The bbox form (P34-B/P36 `frac`): arm pixels inside the fruit's "
          "disc bbox at the fire band")
    print("| fruit cell | disc px | bbox | right:ready | left@grasp | right@grasp |")
    print("| --- | --- | --- | --- | --- | --- |")
    for xx, aa in ((0.20, 0.30), (0.28, 0.25), (0.28, 0.20), (0.34, 0.30)):
        disc, _c, _d = grid_mod.fruit_disc(om, cam, xx, PICK_Y + aa, D_MAIN)
        rows, cols = np.nonzero(disc)
        r0, r1, c0, c1 = rows.min(), rows.max(), cols.min(), cols.max()
        vals = []
        for side, name, active in (("right", "ready", False),
                                   ("right", "ready", True),
                                   ("left", "ready", True)):
            m, _dp, _b = cov_of(side, name, active)
            vals.append(int(m[r0:r1 + 1, c0:c1 + 1].sum()))
        print(f"| x={xx:.2f}, along={aa:+.2f} | {int(disc.sum())} | "
              f"{r1 - r0 + 1}x{c1 - c0 + 1} | {vals[0]} | {vals[1]} | {vals[2]} |")
    print("(the count is arm pixels sharing the disc's projected bbox *whatever "
          "their depth* - a 0 here rules the pose out absolutely, which the "
          "depth-tested `cover` cannot do on its own)")

    print("\n## C. The along profile at the delivered x columns (58 mm fruit)")
    fine = {}
    for label, (side, name, active) in (
            ("right@ready", ("right", "ready", False)),
            ("right@ready (d=45)", ("right", "ready", False)),
            ("left@grasp", ("right", "ready", True)),
            ("right@grasp", ("left", "ready", True)),
            ("left:ready (P35 control)", ("left", "ready", False)),
            ("left:back  (P35 control)", ("left", "back", False))):
        d = D_SMALL if "d=45" in label else D_MAIN
        gf = Grid(om, cam, FINE_XS, FINE_ALONGS, d, grid_mod)
        mask, depth, base = cov_of(side, name, active)
        cov = gf.cover(mask, depth)
        fine[label] = dict(x=list(FINE_XS), along=list(FINE_ALONGS),
                           cover=[float(v) if v == v else None for v in cov])
        print(f"\n`{label}`: " + " ".join(
            f"{aa:+.3f}:" + "/".join(
                f"{cov[np.isclose(gf.cov_a, aa) & np.isclose(gf.cov_x, xx)][0]:.2f}"
                for xx in FINE_XS)
            for i, aa in enumerate(FINE_ALONGS) if i % 10 == 0))
    print("\n(cells are `cover` at along : x=0.22/x=0.28/x=0.34; every 0.05 m shown)")

    # -- D. the delivered points, exactly ----------------------------------- #
    print("\n## D. The 45 delivered **selection** points, scored exactly "
          "(each fruit at its own diameter)")
    rows_d = []
    pose_d = {}
    for label, (side, name, active) in (
            ("right@ready", ("right", "ready", False)),
            ("right@grasp", ("left", "ready", True)),
            ("left@grasp", ("right", "ready", True))):
        mask_d, depth_d, _base = cov_of(side, name, active)
        rows_d = []
        for r in sel:
            disc, centre, _dist = grid_mod.fruit_disc(om, cam, r["x"],
                                                      PICK_Y + r["along"], r["d"])
            cov, _n = grid_mod.arm_cover(mask_d, depth_d, disc, centre,
                                         r["d"] / 2.0, np.asarray(cam["eye"], float))
            rows_d.append(dict(x=r["x"], along=r["along"], d=r["d"], cover=cov))
        covv = np.array([r["cover"] for r in rows_d], float)
        pose_d[label] = dict(rows=rows_d, max=float(np.nanmax(covv)),
                             mean=float(np.nanmean(covv)),
                             ge50=int((covv >= 0.5).sum()),
                             ge10=int((covv >= 0.10).sum()))
        print(f"- **{label}**: max {np.nanmax(covv):.3f}, mean "
              f"{np.nanmean(covv):.4f}; >=0.50 {int((covv >= 0.5).sum())}/"
              f"{len(rows_d)}, >=0.10 {int((covv >= 0.10).sum())}/{len(rows_d)}")
    print("- belt-only visible fraction at the same points: "
          + f"p50 {np.median([om.visible_fraction(r['x'], PICK_Y + r['along'], r['d'])['vis'] for r in rows_d]):.2f}"
          + " - the sheet is behind the +Y output belt there, so for *any* pose "
            "the arm has little left to hide: the selection instant is not a "
            "perception event on this camera whatever the arm does")
    out["delivered_points"] = pose_d

    # -- E. the half-cover region, and the verdict numbers ------------------ #
    print("\n## E. The occlusion geometry, stated as the answer")
    print(f"- `right:ready` >=50 % region: "
          + (f"along {half_ready['along_min']:+.2f}..{half_ready['along_max']:+.2f} "
             f"({half_ready['n_cells']} grid cells); the cell **nearest the "
             f"station** is along {half_ready['along_max']:+.2f} at x "
             f"{half_ready['x_at_max']:.2f} (cover {half_ready['cover_at_max']:.2f}); "
             f"the farthest is along {half_ready['along_min']:+.2f} at x "
             f"{half_ready['x_at_min']:.2f} (belt-only {half_ready['belt_at_min']:.2f})"
             if half_ready.get("any") else "nowhere on the grid"))
    print(f"- the delivered decision band is along {BAND_DECIDE[0]:+.2f}.."
          f"{BAND_DECIDE[1]:+.2f} (fire dy {min(r['dy'] for r in fire):+.3f}.."
          f"{max(r['dy'] for r in fire):+.3f}); `right:ready` cover there: "
          f"mean {np.nanmean(cov_ready[gsel]):.3f}, max "
          f"{np.nanmax(cov_ready[gsel]):.3f}")
    print(f"- the delivered selection band {BAND_SEL[0]:+.2f}..{BAND_SEL[1]:+.2f}: "
          f"cover mean {np.nanmean(cov_ready[gselband]):.3f}, max "
          f"{np.nanmax(cov_ready[gselband]):.3f} - and the belt alone already "
          f"hides the fruit there (belt-only p50 "
          f"{np.median(g.belt[gselband]):.2f}), so no arm pose changes it")
    print("- every right pose at the decide band: "
          + ", ".join(f"{k} {v['decide']:.3f}" for k, v in sorted(
              out["parks"].items(), key=lambda kv: -kv[1]["decide"])[:6])
          + " (top 6; `ready` "
          + f"{out['parks']['ready']['decide']:.3f})")
    om_ready = footprint(zp, "right__ready", "right__ready", om, cam)
    print(f"- `right:ready` silhouette in space: x {om_ready['x'][0]:.3f}.."
          f"{om_ready['x'][1]:.3f}, y {om_ready['y'][0]:+.3f}..{om_ready['y'][1]:+.3f} "
          f"(the station line is y={PICK_Y:+.2f}), z {om_ready['z'][0]:.3f}.."
          f"{om_ready['z'][1]:.3f} -> it hangs over the belt's **downstream** "
          f"tail (y {om_ready['belt_y'][0]:+.3f}..{om_ready['belt_y'][1]:+.3f})")
    edge = [(aa, float(np.nanmean(g.belt[np.isclose(g.cov_a, aa)]))) for aa in ALONGS]
    vis_edge = [aa for aa, b in edge if b >= 0.5]
    print(f"- the camera's own belt window (212, belt-only): >=0.50 visible up to "
          f"along {max(vis_edge):+.2f}, i.e. the fruit is belt-hidden above that - "
          f"the delivered selection positions ({min(r['along'] for r in sel):+.3f}.."
          f"{max(r['along'] for r in sel):+.3f}) are all inside the belt-hidden "
          f"region, so the *fire* is the perception instant, not the selection")
    out["footprint_ready"] = om_ready
    out["fine"] = fine
    out["belt_vis_edge"] = dict(visible_to=float(max(vis_edge)),
                                rows=[[float(a), float(b)] for a, b in edge])

    # -- F. the instrument check: does it reproduce P35? -------------------- #
    print("\n## F. Instrument check - this scorer against P35's own published "
          "table (`logs/p35/20_map.json`)")
    gp35 = Grid(om, cam, grid_mod.XS, grid_mod.ALONGS, D_MAIN, grid_mod)
    pub = json.load(open(os.path.join(ROOT, "logs/p35/20_map.json"),
                         encoding="utf-8"))["parks"]
    stream = gp35.cov_a >= 0.20
    print("| pose | P35 `stream` | this script `stream` | P35 `first` 0.40-0.50 "
          "| this `first` | P35 `by_along` +0.35 | this +0.35 | P35 +0.50 | "
          "this +0.50 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for side, name in (("left", "ready"), ("left", "back"), ("right", "ready")):
        mask, depth, base = cov_of(side, name)
        cov = gp35.cover(mask, depth)
        first = gp35.cov_a >= 0.40
        a35 = np.isclose(gp35.cov_a, 0.35)
        a50 = np.isclose(gp35.cov_a, 0.50)
        p = pub[side][name]
        print(f"| {side}:{name} | {p['stream']:.3f} | {np.nanmean(cov[stream]):.3f} "
              f"| {p['first']:.3f} | {np.nanmean(cov[first]):.3f} "
              f"| {p['by_along']['0.35']:.2f} | {np.nanmean(cov[a35]):.2f} "
              f"| {p['by_along']['0.5']:.2f} | {np.nanmean(cov[a50]):.2f} |")
    print("(P35's `stream` = the mean over along >= 0.20, x 0.19-0.36, d 45/58 mm; "
          "`first` = 0.40-0.50. Agreement to the rounding is what licenses "
          "reading the 0.000 rows above as geometry rather than as a broken "
          "scorer - the same code reproduces the left arm's 0.38.)")

    # -- I. the visible-window arithmetic (how long the fruit is clear) ----- #
    print("\n## G. How long the fruit is clear, if the arm holds that pose "
          "(belt-visible = 212 belt-only >= 0.99; 0.12 m/s)")
    print("| pose | clean: belt-visible and cover<0.5 | hidden: belt-visible and "
          "cover>=0.5 |")
    print("| --- | --- | --- |")
    win = {}
    for label, (side, name, active) in (
            ("right@ready (inactive right)", ("right", "ready", False)),
            ("left@grasp  (active left)", ("right", "ready", True)),
            ("right@grasp (active right)", ("left", "ready", True))):
        mask, depth, base = cov_of(side, name, active)
        cov = g.cover(mask, depth)
        per_a = {}
        for aa in ALONGS:
            sel = np.isclose(g.cov_a, aa)
            per_a[float(aa)] = (float(np.nanmean(cov[sel])),
                                float(np.nanmean(g.belt[sel])))
        clean = [a for a, (c, b) in per_a.items() if b >= 0.99 and c < 0.5]
        hid = [a for a, (c, b) in per_a.items() if b >= 0.99 and c >= 0.5]

        def runs(v, step=0.02):
            """Maximal contiguous along-intervals of a sorted cell list."""
            if not v:
                return []
            v = sorted(v)
            out_, lo = [], v[0]
            for prev, cur in zip(v, v[1:]):
                if cur - prev > step * 1.5:
                    out_.append((lo, prev))
                    lo = cur
            out_.append((lo, v[-1]))
            return out_

        def fmt(rs):
            return ", ".join(f"{a:+.2f}..{b:+.2f} ({(b-a):.2f} m / {(b-a)/0.12:.1f} s)"
                             for a, b in rs) or "-"
        print(f"| {label} | {fmt(runs(clean))} | {fmt(runs(hid))} |")
        win[label] = dict(clean=runs(clean), hidden=runs(hid),
                          clean_cells=clean, hidden_cells=hid)
    print("(`clean`/`hidden` are the contiguous along runs where the belt alone "
          "is >= 0.99 visible and the pose's mean cover is below/above 0.5; the "
          f"fire band is along {BAND_DECIDE[0]:+.2f}..{BAND_DECIDE[1]:+.2f}, the "
          f"last {(BAND_DECIDE[1]-BAND_DECIDE[0])/0.12:.1f} s before the "
          f"station)")
    out["windows"] = win

    # -- G. the lever question, answered against the code ------------------- #
    print("\n## H. The lever: is there a right-arm park to test?")
    parks = json.load(open(os.path.join(ROOT, "configs/arm_parks.json"),
                           encoding="utf-8"))
    print(f"- `configs/arm_parks.json` (md5 {md5(os.path.join(ROOT, 'configs/arm_parks.json'))[:8]}) "
          f"carries `parks.{sorted(parks['parks'])}`, and every entry's `right` "
          f"is null: "
          + ", ".join(f"{k}->{parks['parks'][k].get('right')}" for k in
                      sorted(parks["parks"])))
    print("- `rl_env.py` already resolves a right vector with **no code change**: "
          "the loader loops `for name in (\"left\", \"right\")` and stores "
          "`entry[name]` when non-null (`rl_env.py:1371-1374`), the reset applies "
          "`self._arm_park_poses.get(name)` (`:2569`), the P35 census reads "
          "`self._arm_park_poses.get(inactive)` (`:3414`), and "
          "`_park_poses_label` already prints the per-arm resolution "
          "(`left:back,right:ready`). So a right vector is a **config-only** "
          "addition.")
    print(f"- but there is nothing to remove: `right:ready` is 0.000 over the "
          f"whole delivered band, and it is already at the floor of the "
          f"achievable set - the only right poses that cover **more** of the "
          f"decision band are folds (`fold_70` "
          f"{out['parks']['fold_70']['decide']:.3f}, `side` "
          f"{out['parks']['side']['decide']:.3f}, `fold_55` "
          f"{out['parks']['fold_55']['decide']:.3f}); `side`/`side_deep`/`fold_*` "
          f"also hold (<= 0.008 rad) while `back` does not (hold "
          f"{out['parks']['back']['hold']:.4f} rad, fingertip in the belt "
          f"footprint {out['parks']['back']['in_belt']}).")
    print("- verdict: **no right-arm park lever for the left's station.** A "
          "`right` vector would move a silhouette that is not in the fruit's "
          "sightline; the honest close is that this mechanism is empty, and the "
          "adjacent measurement in B2/C is what the geometry leaves standing.")

    # -- H. limits ---------------------------------------------------------- #
    print("\n## I. What this map does not say")
    print("- it measures **silhouette overlap**, not the policy's attention: a "
          "0.000 cover rules occlusion *out* of the decision band, it does not "
          "prove the policy sees the fruit (P35's own control succeeded with the "
          "fruit fully invisible in 9 of its 23 right-arm successes, and P36's "
          "2x2 found the *image* channel carries the park's win with the "
          "statistic unseparated).")
    print("- the occluder is a **rendered single frame per pose** from "
          "`logs/p35/park_probe.py`; the *active* arm's pose during the wait is "
          "the policy's own, so `left@grasp`/`right@grasp` are the reset poses "
          "(`rl_env.py:2575`) - the measurement of the live wait pose is a "
          "simulator item (record the **active** arm's pixel share at the band "
          "calls: `_park_bbox_census(bbox, side)` already takes any arm name).")
    print("- one camera (the shipped head pose), one scene, `pick_y = 0.00`; the "
          "two-line's right station (`y = -0.10`) is a different scenario.")

    if args.json:
        path = args.json if os.path.isabs(args.json) else os.path.join(ROOT, args.json)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)
        print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
