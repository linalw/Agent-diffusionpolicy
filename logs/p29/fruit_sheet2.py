#!/usr/bin/env python3
"""The per-species fruit contact sheet across the stores (prefer the 240x424 stores)."""
import json, os
import numpy as np
from PIL import Image, ImageDraw

STORES = ["datasets/demos_v13p", "datasets/demos_v11", "datasets/ss012", "datasets/ss015", "datasets/demos_v10"]
CELL = 240
CATS = ["apple", "kiwi", "lychee", "orange", "peach", "pear", "strawberry", "tomato"]
need = {c: None for c in CATS}
for st in STORES:
    ip = f"{st}/index.json"
    if not os.path.exists(ip):
        continue
    for e in json.load(open(ip)):
        cat = e.get("category")
        if cat in need and need[cat] is None:
            need[cat] = (st, e)
sheet = Image.new("RGB", (CELL * 4, CELL * 2 + 46), (26, 26, 30))
draw = ImageDraw.Draw(sheet)
for i, cat in enumerate(CATS):
    if need[cat] is None:
        draw.text((i % 4 * CELL + 8, i // 4 * CELL + 26), f"{cat}: none", fill=(255, 120, 120))
        continue
    st, e = need[cat]
    z = np.load(f"{st}/{e['file']}")
    rgb, m = z["image_rgb"], z["target_mask"]
    areas = m.reshape(len(m), -1).sum(1)
    lim = 0.5 * m.shape[1] * m.shape[2]
    ok = np.where((areas > 30) & (areas < lim))[0]
    if len(ok) == 0:
        ok = np.argsort(areas)[-5:]
    f = int(ok[np.argmax(areas[ok])])
    img = Image.fromarray(rgb[f])
    mm = m[f] > 0
    ys, xs = np.where(mm)
    if len(ys):
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        pad = int(0.45 * max(y1 - y0, x1 - x0)) + 8
        img = img.crop((max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad)))
    img = img.resize((CELL, CELL), Image.LANCZOS)
    col, row = i % 4, i // 4
    sheet.paste(img, (col * CELL, row * CELL + 46))
    draw.text((col * CELL + 8, row * CELL + 28), f"{cat} ({e['grade']}, {e['diameter']*100:.1f} cm)", fill=(240, 240, 240))
sheet.save("logs/p29/fruit_sheet_all.png")
print("saved logs/p29/fruit_sheet_all.png")
