"""Quick camera-model check against recorded demo masks (offline, exploratory)."""
import json
import math
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EYE = np.array([0.05, 0.0, 2.00])
TARGET = np.array([0.34, 0.22, 1.10])


def basis(eye=EYE, target=TARGET, up=(0.0, 0.0, 1.0)):
    eye = np.asarray(eye, float)
    target = np.asarray(target, float)
    z = eye - target
    z /= np.linalg.norm(z)
    x = np.cross(np.asarray(up, float), z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)  # columns


def project(p, R, eye, fx, fy, cx, cy):
    pc = R.T @ (np.asarray(p, float) - eye)
    if pc[2] >= -1e-6:
        return None
    u = cx + fx * (pc[0] / -pc[2])
    v = cy - fy * (pc[1] / -pc[2])
    return np.array([u, v])


def load_episodes(root, limit=12):
    idx = json.load(open(os.path.join(root, "index.json")))
    out = []
    for rec in idx[:limit]:
        z = np.load(os.path.join(root, rec["file"]))
        out.append((rec, z))
    return out


def main():
    root = os.path.join(REPO, "datasets/p33_pear")
    R = basis()
    eps = load_episodes(root, limit=6)
    # Collect (fruit center, mask centroid) for frames where the fruit is on the belt
    # and the mask is reasonably large (unoccluded-ish).
    pairs = []
    for rec, z in eps:
        m = z["target_mask"]
        fp = z["fruit_position"]
        for i in range(len(m)):
            mm = m[i] > 0
            area = int(mm.sum())
            if area < 60:
                continue
            if fp[i][2] > 1.26:  # not on the main belt (carried / placed)
                continue
            ys, xs = np.nonzero(mm)
            pairs.append((fp[i].astype(float), np.array([xs.mean(), ys.mean()]), area, rec["file"], i))
    print("pairs", len(pairs))
    # Fit fx, fy, cx, cy by least squares (linear in 1/z for a fixed pose).
    # u = cx + fx * X/(-Z)  -> linear in (cx, fx)
    A_u, b_u, A_v, b_v = [], [], [], []
    for p, uv, area, f, i in pairs:
        pc = R.T @ (p - EYE)
        X, Y, Z = pc
        if Z >= -0.1:
            continue
        A_u.append([1.0, X / -Z])
        b_u.append(uv[0])
        A_v.append([1.0, Y / -Z])
        b_v.append(uv[1])
    A_u = np.array(A_u); A_v = np.array(A_v)
    cu, fu = np.linalg.lstsq(A_u, np.array(b_u), rcond=None)[0]
    cv, fv = np.linalg.lstsq(A_v, np.array(b_v), rcond=None)[0]
    print(f"fit: cx={cu:.2f} fx={fu:.2f}  cy={cv:.2f} fy={fv:.2f}")
    # residual for the nominal model
    for fx, fy, cx, cy, tag in [
        (188.44, 188.44, 211.5, 119.5, "h-aperture 36mm"),
        (189.63, 189.63, 211.5, 119.5, "v-aperture 20.25mm"),
        (fu, fv, cu, cv, "fit"),
    ]:
        errs = []
        for p, uv, area, f, i in pairs:
            q = project(p, R, EYE, fx, fy, cx, cy)
            if q is None:
                continue
            errs.append(np.linalg.norm(q - uv))
        errs = np.array(errs)
        print(f"{tag}: n={len(errs)} median={np.median(errs):.2f}px p90={np.percentile(errs,90):.2f} max={errs.max():.2f}")


if __name__ == "__main__":
    main()
