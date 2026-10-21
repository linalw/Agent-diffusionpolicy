#!/usr/bin/env python3
"""The per-species fruit contact sheet from the recorded demos (P29, the owner's request).

For each of the 8 species in the supply, take the recorded frame where the target fruit's mask
is largest (the clearest view), crop the mask's bbox with a margin, and compose a labelled sheet.
Read-only over datasets/; writes logs/p29/fruit_sheet.png.
"""
import json
import glob
import numpy as np
from PIL import Image, ImageDraw

STORE = "datasets/ss008"
idx = json.load(open(f"{STORE}/index.json"))
by_cat = {}
for e in idx:
    by_cat.setdefault(e["category"], []).append(e)

CELL = 220
CATS = ["apple", "kiwi", "lychee", "orange", "peach", "pear", "strawberry", "tomato"]
sheet = Image.new("RGB", (CELL * 4, CELL * 2 + 40), (28, 28, 32))
draw = ImageDraw.Draw(sheet)
picked = {}
for i, cat in enumerate(CATS):
    eps = by_cat.get(cat) or []
    best = None
    for e in eps[:4]:
        z = np.load(f"{STORE}/{e['file']}")
        rgb = z["image_rgb"]
        m = z["target_mask"]
        areas = m.reshape(len(m), -1).sum(1)
        # prefer the largest mask that is not the whole frame (the scene-wide masks)
        finite = np.where((areas > 30) & (areas < 0.5 * m.shape[1] * m.shape[2]))[0]
        if len(finite) == 0:
            finite = np.argsort(areas)[-5:]
        f = int(finite[np.argmax(areas[finite])])
        if best is None or areas[f] > best[0]:
            best = (float(areas[f]), e, f)
    if best is None:
        continue
    _, e, f = best
    z = np.load(f"{STORE}/{e['file']}")
    img = Image.fromarray(z["image_rgb"][f])
    m = z["target_mask"][f] > 0
    ys, xs = np.where(m)
    if len(ys) == 0:
        crop = img
    else:
        y0, y1 = ys.min(), ys.max()
        x0, x1 = xs.min(), xs.max()
        pad = int(0.45 * max(y1 - y0, x1 - x0)) + 8
        y0, y1 = max(0, y0 - pad), min(img.height, y1 + pad)
        x0, x1 = max(0, x0 - pad), min(img.width, x1 + pad)
        crop = img.crop((x0, y0, x1, y1))
    crop = crop.resize((CELL, CELL), Image.LANCZOS)
    col, row = i % 4, i // 4
    sheet.paste(crop, (col * CELL, row * CELL + 40))
    draw.text((col * CELL + 8, row * CELL + 24), f"{cat}  ({e['grade']}, {e['diameter']*100:.1f} cm)", fill=(240, 240, 240))
sheet.save("logs/p29/fruit_sheet.png")
print("saved logs/p29/fruit_sheet.png")
for cat in CATS:
    print(cat, "episodes:", len(by_cat.get(cat) or []))
