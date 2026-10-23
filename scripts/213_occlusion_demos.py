"""P34 phase 1: the rendered evidence from the recorded demos - the target
mask's visible area vs the fruit's along-distance, the first detectable frame,
and the camera-model check (offline; no simulator).

    python3 scripts/213_occlusion_demos.py                       # both stores
    python3 scripts/213_occlusion_demos.py --store datasets/p33_pear
    python3 scripts/213_occlusion_demos.py --json logs/p34/20_demos.json

Each episode's `.npz` carries `image_rgb` (240x424), `target_mask` (the picked
fruit's instance mask, 255 = the target) and `fruit_position` (the fruit body's
world pose). The visibility read is `area(y) / area_max` inside one episode,
where `area_max` is that episode's largest on-belt mask - a per-episode
calibration that removes the fruit's class/size and the mesh shape from the
comparison, so the curve is the occlusion itself. Frames with the fruit off the
main belt (z > BELT_TOP + 0.10, i.e. carried or placed) are excluded.
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np

BELT_TOP = 1.17
#: The main belt's x band (the belt spans 0.11-0.57; the supply band is 0.20-0.36).
BELT_X = (0.11, 0.57)
#: The camera (scene.py:1390-1402, assets.SceneConfig).
EYE = np.array([0.05, 0.0, 2.00])
TARGET = np.array([0.34, 0.22, 1.10])
FOCAL, APERTURE, RES = 0.016, (0.036, 0.02025), (240, 424)


def basis(eye=EYE, target=TARGET, up=(0.0, 0.0, 1.0)):
    z = np.asarray(eye, float) - np.asarray(target, float)
    z /= np.linalg.norm(z)
    x = np.cross(np.asarray(up, float), z)
    x /= np.linalg.norm(x)
    return np.stack([x, np.cross(z, x), z], axis=1)


def project(p, R=None, fx=None, fy=None, cx=None, cy=None):
    R = basis() if R is None else R
    h, w = RES
    fx = (w / 2.0) * FOCAL / (APERTURE[0] / 2.0) if fx is None else fx
    fy = fx if fy is None else fy
    cx = (w - 1) / 2.0 if cx is None else cx
    cy = (h - 1) / 2.0 if cy is None else cy
    pc = R.T @ (np.asarray(p, float) - EYE)
    if pc[2] >= -1e-9:
        return None
    return np.array([cx + fx * (pc[0] / -pc[2]), cy - fy * (pc[1] / -pc[2])])


def store_rows(store, limit=None):
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
        except Exception:
            continue
        m = z["target_mask"]
        fp = z["fruit_position"]
        if m.ndim != 3:
            continue
        area = (m > 0).reshape(len(m), -1).sum(axis=1)
        on_belt = fp[:, 2] < BELT_TOP + 0.10
        in_x = (fp[:, 0] > BELT_X[0]) & (fp[:, 0] < BELT_X[1])
        keep = on_belt & in_x
        rows.append(dict(
            file=os.path.join(store, rec["file"]), rec=rec,
            area=area, y=fp[:, 1], x=fp[:, 0], z=fp[:, 2], keep=keep,
            station_y=float(rec.get("station_y", 0.0)),
        ))
    return rows


def summarize(rows, tag, band=(0.40, 0.95)):
    print(f"\n## {tag}: {len(rows)} episodes")
    # Camera-model check on the frames with a large mask (unoccluded).
    errs = []
    for r in rows:
        for i in range(len(r["area"])):
            if r["keep"][i] and r["area"][i] >= 80:
                p = project([r["x"][i], r["y"][i], r["z"][i]])
                if p is None:
                    continue
                m = np.load(r["file"])["target_mask"][i] > 0
                ys, xs = np.nonzero(m)
                errs.append(np.linalg.norm(p - np.array([xs.mean(), ys.mean()])))
    errs = np.array(errs)
    if len(errs):
        print(f"camera check (mask centroid vs projected body centre, n={len(errs)}): "
              f"median {np.median(errs):.2f} px, p90 {np.percentile(errs, 90):.2f} px")

    # The visible fraction vs **world y** (the belt's occlusion is fixed in
    # world y; the arm's station is not), distance-normalised: the projected
    # area of a sphere falls as 1/depth^2, so `area * depth^2` is the visibility
    # times a constant. The reference is the episode's own maximum of that
    # product (the fruit is fully visible somewhere below the band).
    bins = np.arange(-0.40, 1.001, 0.05)
    per_bin = {b: [] for b in bins[:-1]}
    zero = {b: [0, 0] for b in bins[:-1]}
    for r in rows:
        areas = r["area"]
        depth = np.linalg.norm(np.stack([r["x"], r["y"], r["z"]], axis=1) - EYE, axis=1)
        norm = areas * depth * depth
        on = norm[(r["keep"]) & (areas > 0)]
        amax = float(on.max()) if len(on) else 0.0
        if amax <= 0:
            continue
        for i in range(len(areas)):
            if not r["keep"][i]:
                continue
            b = bins[np.searchsorted(bins, float(r["y"][i]), side="right") - 1]
            if b not in per_bin:
                continue
            per_bin[b].append(float(norm[i]) / amax)
            zero[b][0] += int(areas[i] == 0)
            zero[b][1] += 1
    print("| world y | n frames | visible frac median | p10 | zero-mask |")
    print("| --- | --- | --- | --- | --- |")
    curve = []
    for b in bins[:-1]:
        v = np.array(per_bin[b])
        if len(v) < 5:
            continue
        zf = zero[b][0] / max(zero[b][1], 1)
        curve.append(dict(y=float(b), n=int(len(v)),
                          med=float(np.median(v)),
                          p10=float(np.percentile(v, 10)), zero=float(zf)))
        print(f"| {b:+.2f} | {len(v)} | {np.median(v):.2f} | "
              f"{np.percentile(v, 10):.2f} | {zf:.2f} |")

    # The first detectable frame of the on-belt phase, per episode.
    firsts = []
    for r in rows:
        idx = np.where(r["keep"] & (r["area"] > 0))[0]
        if len(idx) == 0:
            continue
        i = idx[0]
        firsts.append((float(r["y"][i]) - r["station_y"], float(r["y"][i]),
                       float(r["area"][i]), int(i), r["rec"].get("arm", "?")))
    f = np.array([x[0] for x in firsts])
    if len(f):
        print(f"\nfirst detectable frame (on-belt): n={len(f)} along "
              f"min {f.min():+.3f} p10 {np.percentile(f,10):+.3f} "
              f"p50 {np.median(f):+.3f} p90 {np.percentile(f,90):+.3f} max {f.max():+.3f}")
        arms = {}
        for a, yy, ar, i, arm in firsts:
            arms.setdefault(arm, []).append(a)
        for arm, vals in arms.items():
            vals = np.array(vals)
            print(f"  arm={arm}: n={len(vals)} p50 {np.median(vals):+.3f} "
                  f"p10 {np.percentile(vals,10):+.3f} p90 {np.percentile(vals,90):+.3f}")
    # Frames in the analytic band (world y) with a zero mask.
    in_band = [(float(r["y"][i]), int(r["area"][i]))
               for r in rows for i in range(len(r["area"]))
               if r["keep"][i] and band[0] < float(r["y"][i]) < band[1]]
    if in_band:
        a = np.array([v for _, v in in_band])
        print(f"on-belt frames with world y in ({band[0]:.2f},{band[1]:.2f}): n={len(a)}, "
              f"zero-mask {float((a == 0).mean()):.2f}, median area {np.median(a):.0f} px")
    below = [(float(r["y"][i]), int(r["area"][i]))
             for r in rows for i in range(len(r["area"]))
             if r["keep"][i] and float(r["y"][i]) < 0.40]
    if below:
        a = np.array([v for _, v in below])
        print(f"on-belt frames with world y < 0.40 (below the band): n={len(a)}, "
              f"zero-mask {float((a == 0).mean()):.2f}, median area {np.median(a):.0f} px")
    return curve, firsts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", action="append", default=[])
    ap.add_argument("--json", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    stores = args.store or ["datasets/p33_pear", "datasets/demos_v12"]
    out = {}
    for store in stores:
        rows = store_rows(store, limit=args.limit or None)
        if not rows:
            print(f"{store}: no index/rows")
            continue
        curve, firsts = summarize(rows, store)
        out[store] = dict(curve=curve,
                          first_along=[float(x[0]) for x in firsts])
    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
