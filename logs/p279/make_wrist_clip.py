#!/usr/bin/env python3
"""P279 demo: overlay the trained segmenter's prediction on the wrist's own frame.

`FRUIT_WRIST=learned` writes, per measurement, `wrist_<side>_<i>.ppm` (the RGB the
net saw), `_depth.npy` and `_pred.npy` (its mask). This turns that trio into a
side-by-side clip so a viewer can see *what the segmenter is being asked to do* and
where it succeeds - the demo's honest half, because the mask is the only thing the
deployment adds.

Usage:
  python3 logs/p279/make_wrist_clip.py logs/video_p279/wrist --out logs/video_p279/wrist.mp4
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

import numpy as np


def read_ppm(path: str) -> np.ndarray:
    with open(path, "rb") as fh:
        assert fh.readline().strip() == b"P6"
        line = fh.readline()
        while line.startswith(b"#"):
            line = fh.readline()
        w, h = (int(v) for v in line.split())
        assert int(fh.readline().strip()) == 255
        buf = fh.read(w * h * 3)
    return np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3).copy()


def write_ppm(path: str, img: np.ndarray) -> None:
    h, w = img.shape[:2]
    with open(path, "wb") as fh:
        fh.write(b"P6\n%d %d\n255\n" % (w, h))
        fh.write(np.ascontiguousarray(img).tobytes())


def upscale(mask: np.ndarray, h: int, w: int) -> np.ndarray:
    ys = (np.arange(h) * mask.shape[0] // h).clip(0, mask.shape[0] - 1)
    xs = (np.arange(w) * mask.shape[1] // w).clip(0, mask.shape[1] - 1)
    return mask[ys][:, xs]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", nargs="?", default="logs/video_p279/wrist")
    ap.add_argument("--out", default="logs/video_p279/wrist.mp4")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--scale", type=int, default=2, help="integer upscale for viewing")
    args = ap.parse_args(argv)

    frames = sorted(glob.glob(os.path.join(args.dir, "wrist_*_pred.npy")))
    if not frames:
        print(f"no predictions under {args.dir}", file=sys.stderr)
        return 2
    tmp = os.path.join(os.path.dirname(args.out) or ".", "_wrist_overlay")
    os.makedirs(tmp, exist_ok=True)
    n = 0
    for pred_path in frames:
        stem = pred_path[: -len("_pred.npy")]
        ppm = stem + ".ppm"
        if not os.path.exists(ppm):
            continue
        img = read_ppm(ppm)
        h, w = img.shape[:2]
        pred = upscale(np.load(pred_path).astype(bool), h, w)
        out = img.astype(np.float32)
        # a red wash where the net says "fruit", plus a bright outline
        tint = np.array([255.0, 60.0, 40.0], dtype=np.float32)
        out[pred] = 0.45 * out[pred] + 0.55 * tint
        edge = pred ^ np.roll(pred, 1, axis=0)
        edge |= pred ^ np.roll(pred, 1, axis=1)
        out[edge] = np.array([255.0, 235.0, 120.0], dtype=np.float32)
        cov = 100.0 * pred.mean()
        out[:12, : min(w, 210)] = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        # a 5x7 digit strip is overkill: encode the coverage as a bar width
        bar = int(min(200.0, cov * 4.0))
        out[3:10, 4: 4 + max(1, bar)] = (
            np.array([120.0, 255.0, 120.0], dtype=np.float32)
            if 3.0 <= cov <= 60.0
            else np.array([255.0, 200.0, 60.0], dtype=np.float32)
        )
        out = np.repeat(np.repeat(out, args.scale, axis=0), args.scale, axis=1)
        write_ppm(os.path.join(tmp, f"{n:05d}.ppm"), np.clip(out, 0, 255).astype(np.uint8))
        n += 1
    if n == 0:
        print("no frames written", file=sys.stderr)
        return 2
    cmd = [
        "ffmpeg", "-v", "error", "-y", "-framerate", str(args.fps),
        "-i", os.path.join(tmp, "%05d.ppm"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", args.out,
    ]
    subprocess.run(cmd, check=True)
    print(f"{n} frames -> {args.out}  (green bar = mask coverage %, 3-60 % is the useful band)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
