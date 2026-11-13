#!/usr/bin/env python3
"""P143: how often is the target fruit actually occluded in the policy's camera?

Rigorous, offline, on the recorded rollouts: for every frame project the fruit's
centre into the head camera and read the depth buffer at that pixel. If the measured
depth is meaningfully **less** than the fruit's own distance along the optical axis,
something (the arm) is between the camera and the fruit.

The camera pose is `SceneConfig`'s: eye `(head_camera_forward, 0, head_camera_z)`,
looking at `head_camera_target`, focal 0.016, aperture 0.036, and the frame's own
shape gives the intrinsics (the store records the resolution).

    python3 logs/p143/occlusion.py datasets/p143_dagger/direct_none_seed77
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fruit_sorting.common import look_at_quat  # noqa: E402

# SceneConfig's shipped head camera.
EYE = np.array([0.05, 0.0, 2.00])
TARGET = np.array([0.34, 0.22, 1.10])
FOCAL, APERTURE = 0.016, (0.036, 0.02025)
#: A depth shortfall this large is an occluder, not depth noise on a sphere.
OCCLUDE_MM = 20.0


def quat_matrix(q) -> np.ndarray:
    w, x, y, z = [float(v) for v in q]
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


def main() -> int:
    store = sys.argv[1] if len(sys.argv) > 1 else "datasets/p143_dagger/direct_none_seed77"
    index = json.load(open(os.path.join(store, "index.json")))
    rot = quat_matrix(look_at_quat(EYE, TARGET))
    # `look_at_quat` builds a basis whose **-col2** looks at the target (measured:
    # col2 . (target - eye) = -0.971 for the shipped pose).
    forward = -rot[:, 2]
    right, up = rot[:, 0], rot[:, 1]

    rows = []
    for entry in index:
        # The depth at the fruit's centre pixel is the fruit's **own surface**, i.e.
        # `z - near ~ radius`, so the occluder threshold is the radius plus a margin.
        radius_mm = 0.5 * float(entry.get("diameter", 0.06)) * 1000.0
        limit_mm = radius_mm + OCCLUDE_MM
        data = np.load(os.path.join(store, entry["file"]))
        # The **measured** fruit, not the goal: the store's goal is a
        # selection-time snapshot (constant per episode), so projecting it samples
        # one fixed pixel for the whole episode (measured: constant shortfall).
        fruit = data["fruit_position"]
        depth = data["image_distance_to_image_plane"]
        if depth.ndim == 4:
            depth = depth[..., 0]
        frames, height, width = depth.shape
        f_px = FOCAL / (APERTURE[0] / 2.0) * (width / 2.0)
        shortfalls = []
        for t in range(frames):
            p = np.asarray(fruit[t, :3], dtype=float)
            d = p - EYE
            z = float(d @ forward)
            if z <= 1e-3:
                continue
            u = int(round(width / 2 + (float(d @ right) / z) * f_px))
            v = int(round(height / 2 - (float(d @ up) / z) * f_px))
            if not (1 <= u < width - 1 and 1 <= v < height - 1):
                continue
            patch = depth[t, v - 1 : v + 2, u - 1 : u + 2]
            if not np.isfinite(patch).any():
                continue
            near = float(np.nanmin(patch))
            if not np.isfinite(near):
                continue
            shortfalls.append((z - near) * 1000.0)
        if not shortfalls:
            continue
        s = np.asarray(shortfalls)
        rows.append(
            {
                "index": int(entry["index"]),
                "success": bool(entry.get("success")),
                "frames": len(s),
                "occluded_frac": float((s > limit_mm).mean()),
                "shortfall_p50": float(np.median(s)),
                "shortfall_p90": float(np.percentile(s, 90)),
                "shortfall_max": float(s.max()),
            }
        )

    if not rows:
        print("[occ] no frames")
        return 1
    occ = np.array([r["occluded_frac"] for r in rows])
    p50 = np.array([r["shortfall_p50"] for r in rows])
    p90 = np.array([r["shortfall_p90"] for r in rows])
    mx = np.array([r["shortfall_max"] for r in rows])
    print(f"[occ] {len(rows)} episodes, {sum(r['frames'] for r in rows)} frames, "
          f"occluder threshold radius+{OCCLUDE_MM:.0f} mm")
    print(f"[occ] per-episode occluded fraction: median {np.median(occ) * 100:.1f}%, "
          f"p90 {np.percentile(occ, 90) * 100:.1f}%, max {occ.max() * 100:.1f}%")
    print(f"[occ] depth shortfall where occluded: p50 {np.median(p50):.0f} mm, "
          f"p90 {np.median(p90):.0f} mm, worst episode {mx.max():.0f} mm")
    for r in rows[:8]:
        print(f"        ep{r['index']:2d} success={str(r['success'])[:5]:>5} "
              f"occluded={r['occluded_frac'] * 100:5.1f}%  "
              f"p50={r['shortfall_p50']:6.0f}mm max={r['shortfall_max']:6.0f}mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
