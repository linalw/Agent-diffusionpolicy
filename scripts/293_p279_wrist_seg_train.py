#!/usr/bin/env python3
"""P279: train the wrist segmenter from labelled wrist frames.

The collection pass (`FRUIT_WRIST_LABELS=<dir>`) authors the wrist camera with the
**instance annotator** - the one annotated camera this build allows - and writes
`<side>_<i>_rgb.npy`, `_depth.npy`, `_mask.npy` per frame while the hand works.

This trains a tiny encoder/decoder on (RGB + depth) -> fruit mask. It is not a
research model: 160x120, ~60 k parameters, and the point is to answer one question
with a measurement - **does a fruit-only mask let the wrist see the fruit while
the pads are on it?** The colour gate (P277) reached 6-9 mm but only on 12-16 % of
frames, and its rejections are `rms 4-9 mm` on blobs of thousands of pixels, i.e.
the fruit is *there* and merged with something.

Usage:
  python3 scripts/293_p279_wrist_seg_train.py --labels logs/p279/labels \
      --out checkpoints/wrist_seg.pt [--epochs 25] [--limit 0]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np

H, W = 120, 160          # the network's input resolution
DEPTH_SCALE = 0.30       # metres -> ~[0, 1] at the wrist's working range


def pool(img: np.ndarray) -> np.ndarray:
    """(..., H0, W0) -> (..., H, W) by mean pooling when larger."""
    a = np.asarray(img, dtype=np.float32)
    h0, w0 = a.shape[-2:]
    fy, fx = h0 // H, w0 // W
    if fy > 1 or fx > 1:
        a = a[..., : fy * H, : fx * W]
        a = a.reshape(*a.shape[:-2], H, fy, W, fx).mean(axis=(-3, -1))
    return a


def load(labels: str, limit: int = 0):
    stems = sorted(
        p[: -len("_rgb.npy")] for p in glob.glob(os.path.join(labels, "*_rgb.npy"))
    )
    if limit:
        stems = stems[:limit]
    xs, ys = [], []
    for stem in stems:
        try:
            rgb = np.load(stem + "_rgb.npy")
            depth = np.load(stem + "_depth.npy")
            mask = np.load(stem + "_mask.npy")
        except OSError:
            continue
        #: channels-first before pooling: `pool` works on the last two axes, and an
        #: HWC array would have its *channel* axis pooled as if it were height
        #: (measured: the loader produced 241 input channels).
        rgb = pool(np.asarray(rgb).transpose(2, 0, 1)) / 255.0
        d = pool(depth)
        d = np.clip(np.nan_to_num(d, nan=1.0), 0.0, DEPTH_SCALE) / DEPTH_SCALE
        x = np.concatenate([rgb, d[None]], axis=0)  # (4, H, W)
        y = (pool(mask.astype(np.float32)) > 0.5).astype(np.float32)[None]
        xs.append(x.astype(np.float32))
        ys.append(y)
    if not xs:
        raise SystemExit(f"no frames under {labels}")
    return np.stack(xs), np.stack(ys)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="logs/p279/labels")
    ap.add_argument("--out", default="checkpoints/wrist_seg.pt")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--val", type=float, default=0.15)
    args = ap.parse_args(argv)

    import torch
    import torch.nn as nn

    x, y = load(args.labels, args.limit)
    n = len(x)
    n_val = max(1, int(round(n * args.val)))
    idx = np.arange(n)
    rng = np.random.default_rng(0)
    rng.shuffle(idx)
    va, tr = idx[:n_val], idx[n_val:]
    print(f"frames {n}  (train {len(tr)}, val {len(va)})  input 4x{H}x{W}")

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  array {x.shape} {x.dtype} = {x.nbytes / 1e6:.0f} MB (stays on CPU; "
          f"batches go to {dev})")
    xt = torch.from_numpy(np.ascontiguousarray(x))
    yt = torch.from_numpy(np.ascontiguousarray(y))

    class TinySeg(nn.Module):
        def __init__(self):
            super().__init__()
            self.e1 = nn.Sequential(nn.Conv2d(4, 16, 3, padding=1), nn.ReLU(),
                                    nn.Conv2d(16, 16, 3, padding=1), nn.ReLU())
            self.e2 = nn.Sequential(nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.ReLU(),
                                    nn.Conv2d(32, 32, 3, padding=1), nn.ReLU())
            self.e3 = nn.Sequential(nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(),
                                    nn.Conv2d(64, 64, 3, padding=1), nn.ReLU())
            self.d2 = nn.ConvTranspose2d(64, 32, 2, stride=2)
            self.d1 = nn.ConvTranspose2d(64, 16, 2, stride=2)
            self.out = nn.Conv2d(32, 1, 1)

        def forward(self, z):
            a = self.e1(z)
            b = self.e2(a)
            c = self.e3(b)
            u = torch.cat([torch.relu(self.d2(c)), b], 1)
            v = torch.cat([torch.relu(self.d1(u)), a], 1)
            return self.out(v)

    net = TinySeg().to(dev)
    params = sum(p.numel() for p in net.parameters())
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    bce = nn.BCEWithLogitsLoss()

    def iou(pred, targ):
        p = (torch.sigmoid(pred) > 0.5).float()
        inter = (p * targ).sum().item()
        union = ((p + targ) > 0.5).float().sum().item()
        return inter / max(union, 1.0)

    best = -1.0
    for ep in range(args.epochs):
        net.train()
        perm = np.random.default_rng(ep).permutation(len(tr))
        tot = 0.0
        for i in range(0, len(tr), args.batch):
            sel = tr[perm[i:i + args.batch]]
            xb = xt[sel].to(dev, non_blocking=True)
            yb = yt[sel].to(dev, non_blocking=True)
            opt.zero_grad()
            logits = net(xb)
            loss = bce(logits, yb)
            prob = torch.sigmoid(logits)
            dice = 1.0 - (2 * (prob * yb).sum() + 1.0) / (prob.sum() + yb.sum() + 1.0)
            (loss + dice).backward()
            opt.step()
            tot += float(loss) * len(sel)
        net.eval()
        with torch.no_grad():
            xv = xt[va].to(dev)
            yv = yt[va].to(dev)
            logits = net(xv)
            vloss = float(bce(logits, yv))
            vious = [iou(logits[k:k + 1], yv[k:k + 1]) for k in range(len(va))]
        v_iou = float(np.mean(vious))
        print(f"  ep {ep:2d}  train {tot / max(len(tr),1):.4f}  val {vloss:.4f}  "
              f"val IoU {v_iou:.3f}")
        if v_iou > best:
            best = v_iou
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
            torch.save(net.state_dict(), args.out)
            meta = {"h": H, "w": W, "depth_scale": DEPTH_SCALE, "params": params,
                    "val_iou": v_iou, "frames": int(n), "input": "rgb+depth"}
            with open(os.path.splitext(args.out)[0] + ".json", "w") as fh:
                json.dump(meta, fh, indent=2)
    print(f"saved {args.out} (best val IoU {best:.3f}, {params} params)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
