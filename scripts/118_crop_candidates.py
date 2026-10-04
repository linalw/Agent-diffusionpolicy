"""Which policy input crop keeps the fruit? Measured on the raw `demos_v8` masks.

The head camera is 240x424 and the policy consumes 128x128.  The shipped
`_downsample` took the top-left 128x128 (rows 0..127, cols 0..383) and cut the
pick station out of the input (WORKLOG "P4 follow-up diagnosis": 47 % of the
plausible target blobs extended past row 127, 27 % sat entirely below it).

This script re-runs the containment audit for the candidates and reports, per
candidate:

  * containment - the fraction of plausible-blob frames whose mask is *fully
    inside* the candidate's source support (for a crop: no blob pixel cut off;
    for a resize: the whole frame is the support by construction);
  * visibility  - the fraction where a blob survives in the 128x128 output
    (>= 1 pixel at >= 0.5 after resampling) and the output blob size;
  * the mapped bbox percentiles in the 128x128 frame.

Writes `logs/743_crop_candidates.txt`.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.policy.data import downsample_frame

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DEMOS = os.path.join(REPO, "datasets", "demos_v8")
OUT = os.path.join(REPO, "logs", "743_crop_candidates.txt")

#: A plausible target blob: 0.05 % .. 20 % of the frame (same band as logs/740).
BLOB_LO, BLOB_HI = 0.0005, 0.2


def center_crop(mask: np.ndarray, size: int = 128) -> tuple[np.ndarray, tuple[slice, slice]]:
    h, w = mask.shape[:2]
    y0 = (h - size) // 2
    x0 = (w - size) // 2
    sl = (slice(y0, y0 + size), slice(x0, x0 + size))
    return mask[sl], sl


def top_left(mask: np.ndarray, size: int = 128, stride_x: int = 3) -> tuple[np.ndarray, tuple[slice, slice]]:
    return mask[:size, : size * stride_x][::1, ::stride_x], (slice(0, size), slice(0, size * stride_x))


def band_resize(mask: np.ndarray, size: int = 128) -> tuple[np.ndarray, tuple[slice, slice]]:
    """Keep the fruit rows at native resolution, resize the full width to `size`."""
    sl = (slice(56, 56 + size), slice(0, mask.shape[1]))
    band = mask[sl]
    return downsample_frame(band, size), sl


def resize(mask: np.ndarray, size: int = 128) -> tuple[np.ndarray, tuple[slice, slice]]:
    return downsample_frame(mask, size), (slice(0, mask.shape[0]), slice(0, mask.shape[1]))


CANDIDATES = {
    "top_left (shipped)": top_left,
    "center_crop": center_crop,
    "band_width_resize": band_resize,
    "full_resize": resize,
}


def main() -> int:
    with open(os.path.join(DEMOS, "index.json"), encoding="utf-8") as fh:
        entries = [e for e in json.load(fh) if e.get("success")]
    stats = {
        name: {"n": 0, "contained": 0, "visible": 0, "pix": [], "max": [], "y0": [], "y1": [], "x0": [], "x1": []}
        for name in CANDIDATES
    }
    total_frames = 0
    for entry in entries:
        with np.load(os.path.join(DEMOS, entry["file"])) as data:
            mask = data["target_mask"]
        frac = mask.reshape(mask.shape[0], -1).mean(axis=1) / 255.0
        total_frames += mask.shape[0]
        for i in np.flatnonzero((frac >= BLOB_LO) & (frac <= BLOB_HI)):
            blob = mask[i] >= 128
            if not blob.any():
                continue
            ys, xs = np.nonzero(blob)
            for name, fn in CANDIDATES.items():
                out, sl = fn(mask[i])
                s = stats[name]
                s["n"] += 1
                cut = blob.copy()
                cut[sl] = False  # any blob pixel outside the crop support stays True
                contained = not cut.any()
                out01 = np.asarray(out, dtype=np.float32)
                if out01.max() > 1.5:  # 0/255 mask input -> bring to 0/1
                    out01 = out01 / 255.0
                visible_blob = out01 >= 0.5
                visible = bool(visible_blob.any())
                s["contained"] += int(contained)
                s["visible"] += int(visible)
                s["pix"].append(int(visible_blob.sum()))
                s["max"].append(float(out01.max()))
                if visible:
                    oy, ox = np.nonzero(visible_blob)
                    s["y0"].append(int(oy.min())); s["y1"].append(int(oy.max()))
                    s["x0"].append(int(ox.min())); s["x1"].append(int(ox.max()))
    lines = [
        f"# Policy-input crop candidates on {DEMOS}",
        f"# {total_frames} frames, plausible target blobs "
        f"({BLOB_LO:.4f} <= mean mask <= {BLOB_HI}) counted per candidate",
        "",
        "candidate            n       contained        visible      blob px (p50)  out max (p50)  "
        "out bbox rows p10/50/90   cols p10/50/90",
    ]
    for name, s in stats.items():
        n = max(s["n"], 1)
        def pct(values, q):
            return np.percentile(values, q) if values else float("nan")
        rows = [pct(s["y0"], 10), pct(s["y0"], 50), pct(s["y0"], 90),
                pct(s["y1"], 10), pct(s["y1"], 50), pct(s["y1"], 90)]
        cols = [pct(s["x0"], 10), pct(s["x0"], 50), pct(s["x0"], 90),
                pct(s["x1"], 10), pct(s["x1"], 50), pct(s["x1"], 90)]
        lines.append(
            f"{name:20s} {s['n']:5d}   {100*s['contained']/n:5.1f}%       "
            f"{100*s['visible']/n:5.1f}%      {pct(s['pix'],50):6.0f}        "
            f"{pct(s['max'],50):.3f}        "
            + " ".join(f"{v:4.0f}" for v in rows)
            + "   " + " ".join(f"{v:4.0f}" for v in cols)
        )
    lines += [
        "",
        "contained = every blob pixel is inside the candidate's source support;",
        "visible   = the resampled 128x128 mask still has >=1 pixel at >= 0.5;",
        "bbox columns report the blob extent inside the 128x128 policy input.",
    ]
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
