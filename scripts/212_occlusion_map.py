"""P34 phase 1: the analytic visibility map of the main belt's fruit under the
raised output belts (offline, numpy only - no simulator).

    python3 scripts/212_occlusion_map.py                 # the map + the band table
    python3 scripts/212_occlusion_map.py --levers        # + the lever candidates
    python3 scripts/212_occlusion_map.py --json out.json

The scene is the shipped one (`assets.SceneConfig` defaults, restated below so
this script never imports the simulator): the head camera at (0.05, 0, 2.00)
looking at (0.34, 0.22, 1.10) with a 16 mm lens on a 36 x 20.25 mm sensor, the
two output-belt slabs (1.10 x 0.25 x 0.05 m at (0.65, +-0.55), top 1.35), their
side rails and support legs, and the main belt's slab (top 1.17).

A fruit is a sphere of diameter `d` resting on the main belt at (x, y,
1.17 + d/2). For every camera pixel in the fruit's window the ray is cast
against every primitive and the nearest hit decides what is visible; the
**visible fraction** is the fruit's pixel count with the output-belt group
present over the count with that group removed (the same fruit, the same
camera). That is exactly what a rendered with/without-belt pair measures, and
`scripts/213_occlusion_demos.py` checks the camera model against the recorded
demo masks.

Also reported:
  * the *band*: the y-interval where the fruit's top point is blocked, and the
    y where the visible fraction crosses 0.99/0.50/0.01 (both edges);
  * the *bbox* fraction: visible pixels over the fruit's projected bbox;
  * the along-the-belt **visible window** at the shipped 0.12 m/s: from the
    band's downstream edge to the trigger's fire zone (`FIRE_Y` = 0.30, the
    decision zone's upstream end, P31 anatomy);
  * the levers of `.slim/deepwork/p34-occlusion.md` section 3, each with its
    band/window and the geometry it costs.
"""

from __future__ import annotations

import argparse
import json
import math
import os

import numpy as np

# --------------------------------------------------------------------------- #
# The shipped geometry (assets.SceneConfig defaults; restated, not imported)
# --------------------------------------------------------------------------- #
EYE = np.array([0.05, 0.0, 2.00])
TARGET = np.array([0.34, 0.22, 1.10])
FOCAL = 0.016            # 16 mm lens
APERTURE = (0.036, 0.02025)
RES = (240, 424)         # (height, width) - the policy/head-camera resolution

BELT_TOP = 1.17
BELT_X = (0.11, 0.57)
BELT_Y = (-0.80, 0.80)

OUT_CENTER_X = 0.65
OUT_CENTER_Y = 0.55
OUT_TOP_Z = 1.35
OUT_SIZE = (1.10, 0.25, 0.05)
RAIL_THICK = 0.025
RAIL_HEIGHT = 0.05
RAIL_BOTTOM_INSET = 0.015
LEG_SIZE = 0.05
INNER_LEG_X = 0.098 - 0.0125 - 0.010 - 0.025   # 0.0505 (assets property)
OUTER_LEG_X = OUT_CENTER_X + OUT_SIZE[0] / 2.0 - 0.075

#: The trigger's decision zone: the fire zone's upstream end (P31 anatomy:
#: fire dy +0.107..+0.301 m). A fruit is fully past this at the fire.
FIRE_Y = 0.301
#: The shipped belt speed (magnitude).
BELT_SPEED = 0.12


def basis(eye=EYE, target=TARGET, up=(0.0, 0.0, 1.0)):
    z = np.asarray(eye, float) - np.asarray(target, float)
    z /= np.linalg.norm(z)
    x = np.cross(np.asarray(up, float), z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


def intrinsics(res=RES, focal=FOCAL, aperture=APERTURE):
    h, w = res
    fx = (w / 2.0) * focal / (aperture[0] / 2.0)
    fy = fx  # square pixels; the 20.25 mm vertical aperture gives 0.6 % more
    return fx, fy, (w - 1) / 2.0, (h - 1) / 2.0


def ray_dirs(cols, rows, R, fx, fy, cx, cy):
    """World-space (unnormalised) ray directions through the given pixels."""
    u = (cols - cx) / fx
    v = -(rows - cy) / fy
    d_cam = np.stack([u, v, -np.ones_like(u)], axis=-1)
    return d_cam @ R.T


# --------------------------------------------------------------------------- #
# Primitives: axis-aligned boxes and spheres
# --------------------------------------------------------------------------- #
def boxes_for(y_sign, *, belt_y=OUT_CENTER_Y, top_z=OUT_TOP_Z,
              size=OUT_SIZE, rails=True, legs=True):
    """The output-line boxes on one side (y_sign = +1 -> the +Y belt)."""
    sx, sy, sz = size
    bx, by = OUT_CENTER_X, y_sign * belt_y
    bz = top_z - sz / 2.0
    out = [("slab", (bx - sx / 2, bx + sx / 2,
                     by - sy / 2, by + sy / 2,
                     bz - sz / 2, bz + sz / 2))]
    if rails:
        rail_bottom = top_z - RAIL_BOTTOM_INSET
        for side in (-1.0, 1.0):
            ry = by + side * (sy / 2.0 + RAIL_THICK / 2.0)
            out.append((f"rail{'+' if side > 0 else '-'}",
                        (bx - sx / 2, bx + sx / 2,
                         ry - RAIL_THICK / 2, ry + RAIL_THICK / 2,
                         rail_bottom, rail_bottom + RAIL_HEIGHT)))
    if legs:
        leg_h = top_z - sz
        for lx in (INNER_LEG_X, OUTER_LEG_X):
            for ly in (by - (sy / 2.0 - 0.03), by + (sy / 2.0 - 0.03)):
                out.append((f"leg@{lx:.2f},{ly:.2f}",
                            (lx - LEG_SIZE / 2, lx + LEG_SIZE / 2,
                             ly - LEG_SIZE / 2, ly + LEG_SIZE / 2,
                             0.0, leg_h)))
    return out


def ray_boxes(origin, dirs, boxes):
    """Nearest positive hit distance per ray (inf where none)."""
    tmin = np.full(dirs.shape[:-1], np.inf)
    for _name, (x0, x1, y0, y1, z0, z1) in boxes:
        lo = np.array([x0, y0, z0])
        hi = np.array([x1, y1, z1])
        with np.errstate(divide="ignore", invalid="ignore"):
            inv = 1.0 / dirs
            t0 = (lo - origin) * inv
            t1 = (hi - origin) * inv
        tlo = np.nanmin(np.stack([t0, t1]), axis=0)
        thi = np.nanmax(np.stack([t0, t1]), axis=0)
        enter = np.max(tlo, axis=-1)
        exit_ = np.min(thi, axis=-1)
        hit = (exit_ >= np.maximum(enter, 0.0)) & (enter > 1e-6)
        tmin = np.where(hit & (enter < tmin), enter, tmin)
    return tmin


def ray_sphere(origin, dirs, center, radius):
    oc = origin - np.asarray(center, float)
    a = np.einsum("...i,...i", dirs, dirs)
    b = 2.0 * np.einsum("...i,...i", dirs, oc)
    c = oc @ oc - radius * radius
    disc = b * b - 4 * a * c
    t = np.full(dirs.shape[:-1], np.inf)
    ok = disc >= 0.0
    if np.any(ok):
        sq = np.sqrt(disc[ok])
        t0 = (-b[ok] - sq) / (2 * a[ok])
        t1 = (-b[ok] + sq) / (2 * a[ok])
        tt = np.where(t0 > 1e-6, t0, np.where(t1 > 1e-6, t1, np.inf))
        t[ok] = tt
    return t


def _window(cols_center, rows_center, half=60):
    h, w = RES
    c0 = int(max(0, math.floor(cols_center - half)))
    c1 = int(min(w - 1, math.ceil(cols_center + half)))
    r0 = int(max(0, math.floor(rows_center - half)))
    r1 = int(min(h - 1, math.ceil(rows_center + half)))
    if c1 < c0 or r1 < r0:
        return None
    rows, cols = np.mgrid[r0:r1 + 1, c0:c1 + 1]
    return rows, cols


def project_point(p, R, eye, fx, fy, cx, cy):
    pc = R.T @ (np.asarray(p, float) - eye)
    if pc[2] >= -1e-9:
        return None
    return np.array([cx + fx * (pc[0] / -pc[2]), cy - fy * (pc[1] / -pc[2])])


def visible_fraction(x, y, d, *, y_sign=1.0, cam=None, out_kw=None, rails=True,
                     legs=True, res_px=1.0):
    """Visible fraction of a fruit at (x, y) of diameter d, plus diagnostics.

    `cam` = dict(eye, target, focal, aperture, res) so a lever can move it.
    `out_kw` = overrides for `boxes_for` (belt_y, top_z, size, rails, legs).
    """
    cam = cam or {}
    eye = np.asarray(cam.get("eye", EYE), float)
    target = np.asarray(cam.get("target", TARGET), float)
    res = cam.get("res", RES)
    fx, fy, cx, cy = intrinsics(res, cam.get("focal", FOCAL),
                                cam.get("aperture", APERTURE))
    R = basis(eye, target)
    radius = d / 2.0
    center = np.array([x, y, BELT_TOP + radius])
    pc = project_point(center, R, eye, fx, fy, cx, cy)
    if pc is None:
        return dict(vis=float("nan"))
    win = _window(pc[0], pc[1], half=int(60 * res_px) + 10)
    if win is None:
        # The fruit's centre projects outside the frame: not visible at all.
        return dict(vis=0.0, area_with=0.0, area_without=0.0, bbox=(np.nan,) * 4,
                    bbox_frac=0.0, top_blocked=False, center_px=pc, out_of_frame=True)
    rows, cols = win
    if res_px != 1.0:
        # Supersample by casting several sub-pixel rays and averaging.
        sub = np.linspace(-0.5 + 0.5 / res_px, 0.5 - 0.5 / res_px, int(res_px))
        rr, cc = [], []
        for dr in sub:
            for dc in sub:
                rr.append(rows + dr)
                cc.append(cols + dc)
        rows = np.concatenate([r.ravel() for r in rr]).reshape(len(rr), -1)
        cols = np.concatenate([c.ravel() for c in cc]).reshape(len(cc), -1)
        shape = rows.shape
        rows = rows.ravel()
        cols = cols.ravel()
        n_sub = len(sub) ** 2
    else:
        shape = rows.shape
        n_sub = 1
    dirs = ray_dirs(cols.astype(float) + 0.5, rows.astype(float) + 0.5, R, fx, fy, cx, cy)
    out_boxes = boxes_for(y_sign, **(out_kw or {}))
    main_box = [("belt", (BELT_X[0], BELT_X[1], BELT_Y[0], BELT_Y[1],
                          BELT_TOP - 0.06, BELT_TOP))]
    t_fruit = ray_sphere(eye, dirs, center, radius)
    t_main = ray_boxes(eye, dirs, main_box)
    t_out = ray_boxes(eye, dirs, out_boxes) if (rails or legs or out_kw is not None
                                                or y_sign) else np.full_like(t_main, np.inf)
    # With the output group present: nearest of fruit / main belt / output group.
    t_with = np.minimum(np.minimum(t_fruit, t_main), t_out)
    finite = np.isfinite(t_fruit)
    is_fruit_with = finite & (t_fruit <= t_with + 1e-9)
    # Without the output group.
    t_without = np.minimum(t_fruit, t_main)
    is_fruit_without = finite & (t_fruit <= t_without + 1e-9)
    a_with = float(is_fruit_with.sum()) / n_sub
    a_without = float(is_fruit_without.sum()) / n_sub
    # The projected bbox of the sphere (sampled over its surface).
    uu = np.linspace(0, 2 * np.pi, 48)
    vv = np.linspace(0, np.pi, 24)
    sx = center[0] + radius * np.outer(np.cos(uu), np.sin(vv))
    sy = center[1] + radius * np.outer(np.sin(uu), np.sin(vv))
    sz = center[2] + radius * np.outer(np.ones_like(uu), np.cos(vv))
    proj = [project_point([a, b, c], R, eye, fx, fy, cx, cy)
            for a, b, c in zip(sx.ravel(), sy.ravel(), sz.ravel())]
    proj = np.array([p for p in proj if p is not None])
    bbox = (proj[:, 0].min(), proj[:, 0].max(), proj[:, 1].min(), proj[:, 1].max())
    bbox_area = max(0.0, bbox[1] - bbox[0]) * max(0.0, bbox[3] - bbox[2])
    # The top point's own visibility (the ray to the sphere's crown).
    top = center + np.array([0.0, 0.0, radius])
    d_top = top - eye
    t_top_out = ray_boxes(eye, d_top[None, :], out_boxes)[0]
    t_top_fruit = ray_sphere(eye, d_top[None, :], center, radius)[0]
    top_blocked = bool(t_top_out < t_top_fruit - 1e-9)
    return dict(
        vis=a_with / a_without if a_without > 0 else float("nan"),
        area_with=a_with,
        area_without=a_without,
        bbox=bbox,
        bbox_frac=a_with / bbox_area if bbox_area > 0 else float("nan"),
        top_blocked=top_blocked,
        center_px=pc,
    )


# --------------------------------------------------------------------------- #
# The band and the window
# --------------------------------------------------------------------------- #
def band(x, d, *, y_sign=1.0, ys=None, cam=None, out_kw=None, rails=True,
         legs=True, res_px=1.0):
    """Scan y and return the band edges + the visible window."""
    # The scan stops at y=-0.40: below that the fruit's centre leaves the
    # head camera's frame (its projection at x=0.28, z=1.20 is row 230 at
    # y=-0.50 and 316 at y=-0.90, outside the 240-row image), so a 0 there
    # would be "out of frame", not "occluded by the belt".
    if ys is None:
        # The +Y belt occludes upstream of the station; the -Y belt downstream.
        ys = (np.arange(-0.40, 0.951, 0.005) if y_sign > 0
              else -np.arange(0.40, 0.951, 0.005))
    rows = [visible_fraction(x, y, d, y_sign=y_sign, cam=cam, out_kw=out_kw,
                             rails=rails, legs=legs, res_px=res_px) for y in ys]
    vis = np.array([r["vis"] for r in rows])
    top = np.array([r["top_blocked"] for r in rows])

    def cross(level, ascending):
        # the y where vis crosses `level` on the near (ascending) or far edge
        idx = np.where(vis < level)[0]
        if len(idx) == 0:
            return float("nan")
        return float(ys[idx[0]] if ascending else ys[idx[-1]])

    blocked = ys[top]
    return dict(
        ys=ys, vis=vis, top=top,
        band_top=(float(blocked.min()), float(blocked.max())) if len(blocked) else (np.nan, np.nan),
        # the downstream (near) edge: vis falls below 0.99 / 0.50 / 0.01
        near99=cross(0.99, True), near50=cross(0.50, True), near01=cross(0.01, True),
        # the upstream (far) edge: vis rises above 0.01 / 0.50 / 0.99
        far01=cross(0.01, False), far50=cross(0.50, False), far99=cross(0.99, False),
    )


def window_at(b, fire_y=FIRE_Y, speed=BELT_SPEED):
    """Visible window (m and s) from the near band edge to the fire zone."""
    near = b["near99"]
    if not np.isfinite(near):
        return dict(win_m=float("nan"), win_s=float("nan"))
    return dict(win_m=float(near - fire_y), win_s=float((near - fire_y) / speed))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--levers", action="store_true")
    ap.add_argument("--res", type=float, default=1.0, help="sub-pixel supersample")
    args = ap.parse_args()

    out = {"camera": dict(eye=EYE.tolist(), target=TARGET.tolist(),
                          focal=FOCAL, aperture=list(APERTURE), res=list(RES)),
           "geometry": dict(belt_top=BELT_TOP, out_center_y=OUT_CENTER_Y,
                            out_top_z=OUT_TOP_Z, out_size=list(OUT_SIZE),
                            out_center_x=OUT_CENTER_X),
           "fire_y": FIRE_Y, "belt_speed": BELT_SPEED}
    fx, fy, cx, cy = intrinsics()
    print(f"# camera: eye={EYE.tolist()} target={TARGET.tolist()} "
          f"res={RES} focal={FOCAL} aperture={APERTURE}")
    print(f"# intrinsics: fx=fy={fx:.2f}px cx={cx:.1f} cy={cy:.1f} "
          f"hfov={2*math.degrees(math.atan(APERTURE[0]/2/FOCAL)):.2f}deg")
    print(f"# fire zone upstream end y=+{FIRE_Y:.3f}, belt {BELT_SPEED:.2f} m/s")

    xs = [0.20, 0.28, 0.34, 0.36]
    ds = [0.031, 0.045, 0.058, 0.069]
    print("\n## 1. The band (the +Y belt; the -Y belt is its mirror)")
    print("| x | d | top blocked y | vis<0.99 | vis<0.50 | vis<0.01 | vis>0.01 | vis>0.50 | vis>0.99 | window m | s |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    rows = []
    for x in xs:
        for d in ds:
            b = band(x, d, y_sign=1.0, res_px=args.res)
            w = window_at(b)
            rows.append(dict(x=x, d=d, band_top=b["band_top"], near99=b["near99"],
                             near50=b["near50"], near01=b["near01"],
                             far01=b["far01"], far50=b["far50"], far99=b["far99"],
                             **w))
            print(f"| {x:.2f} | {d*1000:.0f} | {b['band_top'][0]:+.3f}..{b['band_top'][1]:+.3f} "
                  f"| {b['near99']:+.3f} | {b['near50']:+.3f} | {b['near01']:+.3f} "
                  f"| {b['far01']:+.3f} | {b['far50']:+.3f} | {b['far99']:+.3f} "
                  f"| {w['win_m']:.3f} | {w['win_s']:.2f} |")
    out["band"] = rows

    print("\n## 2. The visible fraction at the policy's waypoints")
    print("| waypoint | y | " + " | ".join(f"x={x:.2f}" for x in xs) + " |")
    print("| --- | --- | " + " | ".join("---" for _ in xs) + " |")
    waypoints = [("spawn", 0.68), ("far edge", 0.82), ("first call hi", 0.551),
                 ("first call lo", 0.455), ("band exit", 0.50),
                 ("pre-fire", 0.35), ("fire hi", 0.301), ("fire lo", 0.107),
                 ("station", 0.0)]
    wp = {}
    for name, y in waypoints:
        vals = []
        for x in xs:
            v = visible_fraction(x, y, 0.058, y_sign=1.0, res_px=args.res)
            vals.append(v["vis"])
        wp[name] = dict(y=y, vis=vals)
        print(f"| {name} | {y:+.3f} | " + " | ".join(f"{v:.2f}" for v in vals) + " |")
    out["waypoints"] = wp

    print("\n## 2b. The bbox fraction and the top-point visibility (d=58 mm, x=0.28)")
    print("| y | vis (silhouette) | vis (bbox) | top point |")
    print("| --- | --- | --- | --- |")
    bbox_rows = []
    for y in (0.40, 0.45, 0.50, 0.55, 0.65, 0.75, 0.82, 0.87, 0.90, 0.95):
        v = visible_fraction(0.28, y, 0.058, y_sign=1.0, res_px=args.res)
        bbox_rows.append(dict(y=y, vis=v["vis"], bbox_frac=v["bbox_frac"],
                              top_blocked=v["top_blocked"]))
        print(f"| {y:+.2f} | {v['vis']:.2f} | {v['bbox_frac']:.2f} | "
              f"{'blocked' if v['top_blocked'] else 'visible'} |")
    out["bbox"] = bbox_rows

    print("\n## 3. The -Y (downstream) belt: mirrored, and mostly out of frame")
    for x in (0.28,):
        for d in (0.058,):
            b = band(x, d, y_sign=-1.0, res_px=args.res)
            print(f"x={x:.2f} d={d*1000:.0f}mm: top blocked "
                  f"{b['band_top'][0]:+.3f}..{b['band_top'][1]:+.3f}, "
                  f"vis>0.99 at {b['far99']:+.3f}, vis<0.99 at {b['near99']:+.3f}")
            out["band_minus"] = dict(x=x, d=d, band_top=b["band_top"],
                                     near99=b["near99"], far99=b["far99"])
    # The camera's own coverage of the belt centre line.
    R = basis()
    print("\n## 3b. The head camera's frame on the belt centre line (x=0.28, z=1.20)")
    for y in (-0.70, -0.60, -0.50, -0.45, -0.40, 0.0, 0.40, 0.60, 0.80, 0.95, 1.00):
        p = project_point([0.28, y, 1.20], R, EYE, fx, fy, cx, cy)
        inside = (p is not None and 0 <= p[0] <= RES[1] - 1 and 0 <= p[1] <= RES[0] - 1)
        print(f"y={y:+.2f}: pixel=({p[0]:6.1f},{p[1]:6.1f}) "
              f"{'in frame' if inside else 'OUT OF FRAME'}")
        out.setdefault("frame_coverage", []).append(
            dict(y=y, px=(None if p is None else p.tolist()), inside=bool(inside)))

    if args.levers:
        print("\n## 4. The lever candidates (the +Y belt; x=0.28, d=58 mm)")
        base = band(0.28, 0.058, res_px=args.res)
        base_w = window_at(base)
        print(f"shipped: near99={base['near99']:+.3f} far99={base['far99']:+.3f} "
              f"window={base_w['win_m']:.3f} m / {base_w['win_s']:.2f} s")
        levers = []
        # 4a. the belt's y (upstream). The place releases at |y| p10 0.512/0.541,
        #     p50 0.564/0.566, max 0.647 (n=2385/5273 placed releases).
        for dy in (0.04, 0.08, 0.12):
            b = band(0.28, 0.058, out_kw=dict(belt_y=OUT_CENTER_Y + dy),
                     res_px=args.res)
            w = window_at(b)
            levers.append(dict(name=f"belt_y +{dy:.2f}", near99=b["near99"],
                               far99=b["far99"], win_m=w["win_m"], win_s=w["win_s"],
                               cost=f"place release p10 |y|=0.512/0.541 vs new rail "
                                    f"inner face {0.400+dy:.3f}; release p50 0.564"))
            print(f"belt_y +{dy:.2f}: near99={b['near99']:+.3f} far99={b['far99']:+.3f} "
                  f"window={w['win_m']:.3f} m / {w['win_s']:.2f} s "
                  f"(rail inner face -> {0.400+dy:+.3f}, release p10 0.512)")
        # 4b. the belt's height.
        for dz in (0.05, 0.10, 0.15):
            b = band(0.28, 0.058, out_kw=dict(top_z=OUT_TOP_Z + dz),
                     res_px=args.res)
            w = window_at(b)
            levers.append(dict(name=f"belt_top_z +{dz:.2f}", near99=b["near99"],
                               far99=b["far99"], win_m=w["win_m"], win_s=w["win_s"],
                               cost=f"place transfer lift {0.08+dz:.2f} m "
                                    f"(shipped 0.08 clears the 35 mm rail)"))
            print(f"belt_top_z +{dz:.2f}: near99={b['near99']:+.3f} far99={b['far99']:+.3f} "
                  f"window={w['win_m']:.3f} m / {w['win_s']:.2f} s "
                  f"(transfer lift -> {0.08+dz:.2f})")
        # 4c. the width, narrowed from the robot side (the inner edge moves).
        for dyi in (0.025, 0.05):
            # inner edge 0.425 -> 0.425+dyi, outer edge fixed: shift the centre
            # and shrink the width by the same amount.
            new_width = OUT_SIZE[1] - dyi
            new_center = OUT_CENTER_Y + dyi / 2.0
            b = band(0.28, 0.058,
                     out_kw=dict(belt_y=new_center, size=(OUT_SIZE[0], new_width, OUT_SIZE[2])),
                     res_px=args.res)
            w = window_at(b)
            levers.append(dict(name=f"inner edge +{dyi:.3f}", near99=b["near99"],
                               far99=b["far99"], win_m=w["win_m"], win_s=w["win_s"],
                               cost=f"release p10 0.512 vs rail inner face {0.400+dyi:.3f}"))
            print(f"inner edge +{dyi:.3f} (width {new_width:.2f}): near99={b['near99']:+.3f} "
                  f"far99={b['far99']:+.3f} window={w['win_m']:.3f} m / {w['win_s']:.2f} s")
        # 4d. the camera (the policy OOD cost).
        for name, cam in (
            ("cam z 1.80", dict(eye=[0.05, 0.0, 1.80])),
            ("cam z 2.20", dict(eye=[0.05, 0.0, 2.20])),
            ("cam y -0.25", dict(eye=[0.05, -0.25, 2.00])),
            ("cam y +0.25", dict(eye=[0.05, 0.25, 2.00])),
            ("cam x -0.10", dict(eye=[-0.10, 0.0, 2.00])),
        ):
            b = band(0.28, 0.058, cam=cam, res_px=args.res)
            w = window_at(b)
            levers.append(dict(name=name, near99=b["near99"], far99=b["far99"],
                               win_m=w["win_m"], win_s=w["win_s"],
                               cost="frame-conditioned policy: OOD"))
            print(f"{name}: near99={b['near99']:+.3f} far99={b['far99']:+.3f} "
                  f"window={w['win_m']:.3f} m / {w['win_s']:.2f} s")
        out["levers"] = levers

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
