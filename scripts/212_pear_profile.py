"""Pear silhouette against the reference photo (P32 phase 3, offline).

    python3 scripts/212_pear_profile.py              # metrics + the figure
    python3 scripts/212_pear_profile.py --no-photo   # the shipped table only
    python3 scripts/212_pear_profile.py --photo X.jpg --out /tmp/x.png

No simulator: `meshes.py` imports pxr at module level, so this script stubs it
the way `scripts/211_bed_audit.py` does and imports the *real* `pear_profile`.

What it answers (the owner's "the simulated pear is a faceted bucket"):

* **the reference**: the photo's pear body is masked from the white studio
  background by chroma (`max(rgb) - min(rgb) > 60/255`), which drops the
  achromatic watermark by construction. The outer contour is the per-row
  `[min x, max x]` envelope (the pear is single-valued in this view); the stem
  is cut where a row is narrower than 0.10 of the widest row (the stem is
  0.04-0.06 W, the body neck >= 0.10 W), and the contact shadow where a row is
  narrower than 0.25 W (the shadow is <= 0.14 W, the base's last contour row
  0.42 W). Everything is normalised to the *body* height, so the stem is not
  part of the pear's H/W;
* **the profile as shipped** before P32 (`legacy_pear_profile`, copied from
  `meshes.py` at commit `31e75a4`) with the same metrics - that is the gap;
* **the new profile** (`meshes.PEAR_CONTROL` + `meshes.pear_profile`): the same
  metrics, the lathe invariants (r >= 0, one pole per end, a single-valued
  body), the solid's volume against the 4/3 pi r^3 sphere the mass proxy uses,
  and the lathe cost (rings x azimuth segments);
* **the figure** `logs/p32/pear_profile.png`: the photo's contour against the
  new profile at the same height scale, plus the metric table.

Exit code 1 when the new profile misses the photo by more than 5 % on H/W or on
any 0.05 H row's r/r_max, or when a lathe invariant fails. A missing photo is
not a failure: the measured table is compared against `REFERENCE` and the run
says so.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

# --- stub pxr just enough to import fruit_sorting.meshes ------------------- #
for name in ("pxr",):
    sys.modules.setdefault(name, types.ModuleType(name))
pxr = sys.modules["pxr"]
for attr in ("Gf", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from fruit_sorting import meshes  # noqa: E402

PHOTO = os.path.expanduser("~/图片/截图/4315455_113747057037_2.jpg")
OUT = os.path.join(ROOT, "logs", "p32", "pear_profile.png")

#: The pear body against the white studio background: the yellow-green fruit has
#: a chroma of 150-160/255, the contact shadow 26-44, the watermark 0.
CHROMA_THRESHOLD = 60
#: The stem is 0.04-0.06 of the widest row and the body neck >= 0.10; the
#: contact shadow is <= 0.14 of it and the base's last contour row 0.42.
TOP_WIDTH_FRACTION = 0.10
BASE_WIDTH_FRACTION = 0.25
#: The watermark band: achromatic anyway, cropped so no antialiased grey can
#: ever enter the mask (the pear ends at y = 967, the text starts at y = 985).
BOTTOM_CROP = 0.96

#: The measured rows, `z/H -> r/r_max`, and H/W (photo 1024 px, body rows
#: 210..967, widest row 734, W 659 px). Re-derived every run when the photo is
#: present; the figure falls back to them so the PNG stays re-checkable without
#: the JPEG.
REFERENCE = {
    0.00: 0.4188, 0.05: 0.7254, 0.10: 0.8407, 0.15: 0.9165, 0.20: 0.9697,
    0.25: 0.9954, 0.30: 1.0000, 0.35: 0.9909, 0.40: 0.9681, 0.45: 0.9256,
    0.50: 0.8741, 0.55: 0.8118, 0.60: 0.7390, 0.65: 0.6692, 0.70: 0.5994,
    0.75: 0.5372, 0.80: 0.4826, 0.85: 0.4385, 0.90: 0.3900, 0.95: 0.3187,
    1.00: 0.1153,
}
REFERENCE_HW = 1.1502


def legacy_pear_profile(samples: int = 40) -> list[tuple[float, float]]:
    """The pre-P32 pear (a squeezed sphere with a dimple), for the comparison.

    Copied verbatim from `meshes.pear_profile` at commit `31e75a4`; it is not
    imported because the module no longer carries it. Its rows run top ->
    bottom and carry a radial *step* between the upper cylinder and the lower
    bowl - the bucket in `logs/p29/fruit_pear.png`.
    """
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):
        t = i / samples
        theta = math.pi * t
        r = math.sin(theta)
        z = math.cos(theta)
        neck = 0.55 + 0.45 * math.cos(theta) ** 2 if math.cos(theta) > 0 else 1.0
        r *= neck if math.cos(theta) > 0 else 1.0
        r *= 1.0 + 0.12 * max(0.0, -math.cos(theta))
        if theta < 0.6:
            k = 1.0 - theta / 0.6
            z -= 0.12 * k**1.5
            r *= 1.0 - 0.35 * k**2
        pts.append((r, z))
    return pts


# --------------------------------------------------------------------------- #
# 1. The reference: the photo's silhouette
# --------------------------------------------------------------------------- #
def extract_reference(photo: str) -> dict:
    """Mask the pear, cut the stem and the contact shadow, read the contour."""
    rgb = np.asarray(Image.open(photo).convert("RGB"), dtype=np.float32)
    height_px = rgb.shape[0]
    crop = int(round(BOTTOM_CROP * height_px))
    rgb = rgb[:crop]
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    fg = chroma > CHROMA_THRESHOLD
    left = np.full(rgb.shape[0], -1)
    right = np.full(rgb.shape[0], -1)
    for y in range(rgb.shape[0]):
        xs = np.where(fg[y])[0]
        if len(xs):
            left[y], right[y] = xs.min(), xs.max()
    width = np.where(left >= 0, right - left + 1, 0)
    widest = int(width.max())
    widest_y = int(np.argmax(width))
    body = np.where(width >= TOP_WIDTH_FRACTION * widest)[0]
    y_top = int(body.min())
    base = body[width[body] >= BASE_WIDTH_FRACTION * widest]
    y_bottom = int(base.max()) if len(base) else int(body.max())
    height = y_bottom - y_top + 1
    contour = [(y, int(left[y]), int(right[y])) for y in range(y_top, y_bottom + 1)]
    table = {}
    for i in range(21):
        z = i / 20.0
        y = int(round(y_bottom - z * (height - 1)))
        table[z] = width[y] / float(widest)
    return {
        "H": height, "W": widest, "H/W": height / widest,
        "r_max/H": (widest / 2.0) / height,
        "y_top": y_top, "y_bottom": y_bottom, "widest_y": widest_y,
        "widest_z": (y_bottom - widest_y) / float(height - 1),
        "table": table, "contour": contour, "crop_bottom": crop,
        "bottom_row_width": width[y_bottom] / float(widest),
        "next_row_width": width[min(y_bottom + 1, crop - 1)] / float(widest),
        "top_row_width": width[y_top] / float(widest),
    }


# --------------------------------------------------------------------------- #
# 2. The profiles
# --------------------------------------------------------------------------- #
def split_body(profile: list[tuple[float, float]]):
    """(r, z) arrays plus the z-min / z-max row indices of a lathe profile.

    The calyx basin and the stem cavity reverse z, so the body is the stretch
    between the lowest and the highest row (`min`/`max` index either way round:
    the pre-P32 profile is authored top -> bottom).
    """
    r = np.asarray([p[0] for p in profile], dtype=float)
    z = np.asarray([p[1] for p in profile], dtype=float)
    return r, z, int(np.argmin(z)), int(np.argmax(z))


def metrics(profile: list[tuple[float, float]]) -> dict:
    """H/W, the 0.05 H radius rows and the named shape points of a profile."""
    r, z, rim, lip = split_body(profile)
    lo, hi = min(rim, lip), max(rim, lip)
    zb, rb = z[lo:hi + 1], r[lo:hi + 1]
    order = np.argsort(zb)
    zb, rb = zb[order], rb[order]
    height = float(zb[-1] - zb[0])
    r_max = float(r.max())
    table = {}
    for i in range(21):
        f = i / 20.0
        table[f] = float(np.interp(zb[0] + f * height, zb, rb)) / r_max
    out = {
        "H/W": height / (2.0 * r_max), "r_max": r_max, "H": height,
        "r/H_max": r_max / height, "table": table,
        "widest_z": (float(z[int(np.argmax(r))]) - zb[0]) / height,
        "neck": table[0.80], "base": table[0.05], "lip": table[1.00],
        "rows": len(profile), "z_min": float(z.min()), "z_max": float(z.max()),
    }
    out["cavity_depth"] = (float(z.max()) - profile[-1][1]) / height
    out["cavity_lip"] = r[int(np.argmax(z))] / r_max
    return out


def lathe_checks(profile: list[tuple[float, float]]) -> list[tuple[bool, str]]:
    """The invariants a lathe profile has to satisfy (all must be True)."""
    r, z, rim, lip = split_body(profile)
    lo, hi = min(rim, lip), max(rim, lip)
    poles = [i for i in range(len(r)) if r[i] <= 1e-4]
    body_z = z[lo:hi + 1] if rim < lip else z[hi:lo - 1:-1] if lo else z
    return [
        (bool(np.all(r >= 0.0)), f"r >= 0 everywhere (min {r.min():.4f})"),
        (bool(np.all(np.diff(body_z) > 0.0)),
         f"z monotone on the body (rim row {rim} -> lip row {lip})"),
        (poles == [0, len(r) - 1], f"one pole per end (poles at {poles})"),
        (abs(r.max() - 1.0) < 1e-6, "widest radius == 1.0 (the class radius)"),
        (abs(z.min() + 1.0) < 1e-3,
         f"base rim at z = -1.0 (the spawner's assumption, got {z.min():+.4f})"),
        (abs(z.max() - (2.0 * meshes.PEAR_HEIGHT_RATIO - 1.0)) < 1e-3,
         f"lip at z = {2.0 * meshes.PEAR_HEIGHT_RATIO - 1.0:+.3f} "
         f"(H/W {meshes.PEAR_HEIGHT_RATIO:.2f})"),
    ]


def volume_fraction(profile: list[tuple[float, float]]) -> dict:
    """Solid of revolution of the profile, against the sphere the mass uses.

    `fruits.py` prices mass as `density * 4/3 pi (d/2)^3 * 0.82`, so the
    reference volume here is the sphere of radius r_max (the class radius) and
    the fraction says how far the 0.82 discount is from this solid. Everything is
    expressed in `r_max^3` units: the legacy profile's own maximum is 1.0063 (not
    exactly 1), and a raw integral would compare it against a sphere it does not
    fill. The integral is signed by the row order (the legacy profile runs top ->
    bottom) and the cavity rows subtract, so the solid is |integral|.
    """
    r = np.asarray([p[0] for p in profile], dtype=float)
    z = np.asarray([p[1] for p in profile], dtype=float)
    integral = 0.0
    area = 0.0
    for i in range(len(profile) - 1):
        dz = z[i + 1] - z[i]
        integral += dz * (r[i] ** 2 + r[i] * r[i + 1] + r[i + 1] ** 2) / 3.0
        area += math.pi * (r[i] + r[i + 1]) * math.hypot(r[i + 1] - r[i], dz)
    solid = abs(math.pi * integral) / float(r.max()) ** 3
    sphere = 4.0 / 3.0 * math.pi
    return {"solid": solid, "sphere": sphere, "fraction": solid / sphere,
            "mass_vs_proxy": solid / (0.82 * sphere), "area": area}


def mesh_cost(profile: list[tuple[float, float]], segments: int = 28) -> dict:
    """Vertices, triangles and the azimuthal facet sagitta at the unit radius.

    The triangle count is `meshes.build_mesh_points`' own: a row pair costs
    `2 * segments`, except a pair that touches a pole row - the profile's ends -
    which is a fan of `segments`. The old `2 * segments * (rows - 1)` ignored
    both fans and read 4200/2240 instead of 4144/2184.
    """
    pole = [r <= 1e-4 for (r, _) in profile]
    vertices = sum(1 if p else segments for p in pole)
    triangles = sum(
        segments if (pole[i] or pole[i + 1]) else 2 * segments
        for i in range(len(profile) - 1)
    )
    return {"vertices": vertices, "triangles": triangles, "segments": segments,
            "sagitta_r": max(r for (r, _) in profile) * (1.0 - math.cos(math.pi / segments))}


def stem_checks(profile: list[tuple[float, float]], name: str) -> list[tuple[bool, str]]:
    """`author_stem`'s convention: the last profile row is the stem-cavity floor.

    `meshes.author_stem` reads `profile[-1][1]` as the cavity floor and seats the
    stalk above it, so a profile authored the other way round (the pre-P32 pear
    ran top -> bottom) gets its stem authored inside the *base* - the buried stem
    the P32 change removed. These checks assert the convention on the shipped
    profile; run on the legacy profile they say why it fails.
    """
    z = [p[1] for p in profile]
    lo, hi = min(z), max(z)
    return [
        (z[-1] > lo + 0.5 * (hi - lo),
         f"{name}: profile[-1] is in the top half (z {z[-1]:+.3f} of {lo:+.3f}..{hi:+.3f})"),
        (z[-1] < z[-2],
         f"{name}: profile[-1] closes downward into the cavity (z[-2] {z[-2]:+.3f} -> "
         f"z[-1] {z[-1]:+.3f})"),
    ]


# --------------------------------------------------------------------------- #
# 3. The figure
# --------------------------------------------------------------------------- #
def _font(size: int, bold: bool = False, mono: bool = False):
    base = "/usr/share/fonts/truetype/dejavu"
    name = "DejaVuSansMono.ttf" if mono else ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    try:
        return ImageFont.truetype(os.path.join(base, name), size)
    except OSError:
        return ImageFont.load_default()


def _outline(draw, cx, y_base, h_px, extent, fill, outline, width=2):
    """Fill a mirrored silhouette; `extent` is [(r/H, z/H)] bottom -> top."""
    pts = [(cx + r * h_px, y_base - z * h_px) for (r, z) in extent]
    pts += [(cx - r * h_px, y_base - z * h_px) for (r, z) in reversed(extent)]
    draw.polygon(pts, fill=fill, outline=outline, width=width)


def figure(ref: dict, new, old, m_ref, m_old, m_new, vol, cost, path) -> None:
    canvas_w, canvas_h = 1600, 1200
    img = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f_title, f_sub = _font(26, True), _font(15)
    f_lab, f_small, f_mono = _font(13), _font(12), _font(12, mono=True)
    f_head, f_note = _font(13, True), _font(11)

    d.text((70, 18), "P32 phase 3 - pear silhouette: reference photo vs the new profile",
           font=f_title, fill=(20, 20, 20))
    d.text((70, 52),
           "both panels at the same scale (1 H = 420 px): x = r/H mirrored about the axis, "
           "y = z/H up from the base rim. Re-run: scripts/212_pear_profile.py",
           font=f_sub, fill=(90, 90, 90))

    panels = [(70, 92, 760, 640), (800, 92, 1490, 640)]
    h_px = 420.0
    for (x0, y0, x1, y1) in panels:
        d.rectangle([x0, y0, x1, y1], outline=(205, 205, 205))

    # --- panel 1: the photo contour ------------------------------------- #
    x0, y0, x1, y1 = panels[0]
    cx, y_base = (x0 + x1) // 2, y1 - 70
    d.line([(cx, y0 + 8), (cx, y_base)], fill=(228, 228, 228), width=1)
    if ref.get("contour"):
        contour, h_photo = ref["contour"], float(ref["H"])
        ext = [(0.5 * (right - left) / h_photo, (ref["y_bottom"] - y) / (h_photo - 1))
               for (y, left, right) in contour]
        _outline(d, cx, y_base, h_px, ext, (238, 240, 205), (120, 130, 60))
        for i in range(21):
            z = i / 20.0
            y = int(round(ref["y_bottom"] - z * (h_photo - 1)))
            _, left, right = contour[y - ref["y_top"]]
            half = 0.5 * (right - left) / h_photo
            for sign in (-1, 1):
                px, py = cx + sign * half * h_px, y_base - z * h_px
                d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(110, 120, 50))
        d.text((x0 + 16, y0 + 12), "reference photo - the extracted body contour",
               font=f_lab, fill=(60, 70, 30))
        d.text((x0 + 16, y0 + 32),
               f"H/W {ref['H/W']:.3f}  ({ref['W']} x {ref['H']} px)  r_max/H "
               f"{ref['r_max/H']:.3f}", font=f_small, fill=(90, 90, 90))
        d.text((x0 + 16, y1 - 44), "stem cut at 0.10 W, contact shadow at 0.25 W,",
               font=f_small, fill=(130, 130, 130))
        d.text((x0 + 16, y1 - 26), "dots: the 21 rows at the 0.05 H steps",
               font=f_small, fill=(130, 130, 130))
    else:
        ext = [(REFERENCE[i / 20.0] * (0.5 / REFERENCE_HW), i / 20.0) for i in range(21)]
        _outline(d, cx, y_base, h_px, ext, (238, 240, 205), (120, 130, 60))
        d.text((x0 + 16, y0 + 12), "reference (the shipped table; photo not read)",
               font=f_lab, fill=(60, 70, 30))
        d.text((x0 + 16, y0 + 32), f"H/W {REFERENCE_HW:.3f}", font=f_small,
               fill=(90, 90, 90))

    # --- panel 2: the new profile, the photo and the pre-P32 one --------- #
    x0, y0, x1, y1 = panels[1]
    cx, y_base = (x0 + x1) // 2 + 20, y1 - 70
    d.line([(cx, y0 + 8), (cx, y_base)], fill=(228, 228, 228), width=1)

    def extent(profile):
        r_p, z_p, rim_p, lip_p = split_body(profile)
        height = z_p[lip_p] - z_p[rim_p]
        return [(r_p[i] / height, (z_p[i] - z_p[rim_p]) / height) for i in range(len(r_p))]

    ext_old = extent(old)
    pts = [(cx + r * h_px, y_base - z * h_px) for (r, z) in ext_old]
    pts += [(cx - r * h_px, y_base - z * h_px) for (r, z) in reversed(ext_old)]
    d.line(pts + [pts[0]], fill=(160, 160, 160), width=2)

    ext_new = extent(new)
    _outline(d, cx, y_base, h_px, ext_new, (176, 208, 88), (70, 96, 20))
    # the reference contour over the new profile: the match is the point
    if ref.get("contour"):
        ref_ext = [(0.5 * (right - left) / float(ref["H"]),
                    (ref["y_bottom"] - y) / (float(ref["H"]) - 1))
                   for (y, left, right) in ref["contour"]]
    else:
        ref_ext = [(REFERENCE[i / 20.0] * (0.5 / REFERENCE_HW), i / 20.0) for i in range(21)]
    line = [(cx + r * h_px, y_base - z * h_px) for (r, z) in ref_ext]
    line += [(cx - r * h_px, y_base - z * h_px) for (r, z) in reversed(ref_ext)]
    d.line(line + [line[0]], fill=(196, 128, 40), width=2)
    scale = 2.0 * meshes.PEAR_HEIGHT_RATIO
    for (r_c, z_c) in meshes.PEAR_CONTROL:
        px = cx + (r_c / scale) * h_px
        py = y_base - z_c * h_px
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(40, 60, 10))
    widest = max(ext_new, key=lambda p: p[0])
    d.line([(cx - widest[0] * h_px, y_base - widest[1] * h_px),
            (cx + widest[0] * h_px, y_base - widest[1] * h_px)],
           fill=(20, 90, 30), width=1)
    d.text((x0 + 16, y0 + 12), "new profile (PEAR_CONTROL) over the photo's contour",
           font=f_lab, fill=(40, 70, 10))
    d.text((x0 + 16, y0 + 32),
           f"H/W {m_new['H/W']:.3f}  widest {m_new['widest_z']:.3f} H  "
           f"neck {m_new['neck']:.3f}  base {m_new['base']:.3f}  (r/rmax)",
           font=f_small, fill=(90, 90, 90))
    d.text((x0 + 16, y1 - 44),
           f"grey: the pre-P32 profile (H/W {m_old['H/W']:.3f}, the radial step is the "
           f"bucket)", font=f_small, fill=(130, 130, 130))
    d.text((x0 + 16, y1 - 26),
           "ochre: the photo contour; dots: control points; green: the widest row",
           font=f_small, fill=(130, 130, 130))

    # --- the metric table ------------------------------------------------ #
    ty = 672
    d.text((70, ty), "metrics", font=_font(18, True), fill=(20, 20, 20))
    cols = [70, 300, 470, 640]
    for x, text in zip(cols, ("metric", "reference (photo)", "current (pre-P32)", "new (P32)")):
        d.text((x, ty + 30), text, font=f_head, fill=(40, 40, 40))
    d.line([(70, ty + 48), (1010, ty + 48)], fill=(160, 160, 160))
    cost_old = mesh_cost(old)
    vol_old = volume_fraction(old)
    worst = max(abs(m_new["table"][f] - m_ref["table"][f]) for f in m_ref["table"])
    hw_err = (m_new["H/W"] - m_ref["H/W"]) / m_ref["H/W"]
    rows = [
        ("H / W", f"{m_ref['H/W']:.3f}", f"{m_old['H/W']:.3f}", f"{m_new['H/W']:.3f}"),
        ("widest at z/H", f"{m_ref['widest_z']:.3f}", f"{m_old['widest_z']:.3f}",
         f"{m_new['widest_z']:.3f}"),
        ("widest r/H", f"{m_ref['r/H_max']:.3f}", f"{m_old['r/H_max']:.3f}",
         f"{m_new['r/H_max']:.3f}"),
        ("neck r/rmax @0.80H", f"{m_ref['neck']:.3f}", f"{m_old['neck']:.3f}",
         f"{m_new['neck']:.3f}"),
        ("base r/rmax @0.05H", f"{m_ref['base']:.3f}", f"{m_old['base']:.3f}",
         f"{m_new['base']:.3f}"),
        ("lip r/rmax @1.00H", f"{m_ref['lip']:.3f}", f"{m_old['lip']:.3f}",
         f"{m_new['lip']:.3f}"),
        ("top cavity depth / H", "-", "-", f"{m_new['cavity_depth']:.3f}"),
        ("solid volume / r_max^3", "-", f"{vol_old['solid']:.3f}",
         f"{vol['solid']:.3f}"),
        ("volume / sphere", "-", f"{vol_old['fraction']:.4f}", f"{vol['fraction']:.4f}"),
        ("rows (rings)", "-", f"{m_old['rows']}", f"{m_new['rows']}"),
        ("azimuth segments", "-", f"{cost_old['segments']}", f"{cost['segments']}"),
        ("vertices / triangles", "-", f"{cost_old['vertices']} / {cost_old['triangles']}",
         f"{cost['vertices']} / {cost['triangles']}"),
        ("max |d r/rmax| vs photo", "-",
         f"{max(abs(m_old['table'][f] - m_ref['table'][f]) for f in m_ref['table']):.3f}",
         f"{worst:.4f}"),
    ]
    for i, (label, a, b, c) in enumerate(rows):
        bold = label in ("H / W", "max |d r/rmax| vs photo")
        for x, text in zip(cols, (label, a, b, c)):
            d.text((x, ty + 60 + i * 25), text,
                   font=f_small if x == cols[0] else f_mono, fill=(30, 30, 30))
    print_scale = 0.064
    shape = meshes.FRUIT_SHAPES["pear"]
    sphere_d = (4.0 / 3.0) * math.pi * (print_scale / 2.0) ** 3
    mass_g = shape.density * sphere_d * 0.82 * 1000.0
    notes = [
        f"H/W: the owner's band is 1.2-1.3; the new profile uses the band floor, "
        f"{hw_err * 100:+.1f} % on the photo's {m_ref['H/W']:.3f} (the 5 % bar).",
        "widest: the photo and the new profile are both a third of the way up; the "
        "pre-P32 pear's maximum sits at mid-height on its radial step.",
        f"cavity: {m_new['cavity_depth'] * 100:.1f} % of H deep, lip "
        f"{m_new['cavity_lip']:.3f} r_max; the stem is authored inside it.",
        f"volume: the new solid is {vol['fraction']:.4f} of the 4/3 pi r^3 sphere "
        f"({vol['solid']:.3f} r_max^3); the pre-P32 one {vol_old['fraction']:.4f} "
        f"({vol_old['solid']:.3f}) - {vol['solid'] / vol_old['solid']:.3f}x at the "
        f"same diameter.",
        f"mass is unchanged ({mass_g:.1f} g at 6.40 cm), so the solid's effective "
        f"density falls to {mass_g / 1000.0 / (vol['fraction'] * sphere_d):.0f} kg/m^3 "
        f"from {mass_g / 1000.0 / (vol_old['fraction'] * sphere_d):.0f} (report only).",
        f"cost: {m_new['rows']} rings x {cost['segments']} segments = "
        f"{cost['triangles']} triangles ({cost_old['triangles']} before; the pole fans "
        f"counted); the azimuthal facet sagitta is "
        f"{cost['sagitta_r']:.4f} r_max ({cost['sagitta_r'] * 32.5:.3f} mm at 65 mm).",
        "pass bar: every 0.05 H row within 0.05 r/rmax of the photo (< 0.005 here).",
    ]
    for i, text in enumerate(notes):
        d.text((70, ty + 60 + len(rows) * 25 + 12 + i * 16), text, font=f_note,
               fill=(110, 110, 110))

    # --- the 0.05 H rows -------------------------------------------------- #
    tx = 1050
    d.text((tx, ty), "r / r_max at the 0.05 H rows", font=_font(16, True),
           fill=(20, 20, 20))
    for j, text in enumerate(("z/H", "ref", "current", "new", "new-ref", "cur-ref")):
        d.text((tx + 8 + j * 82, ty + 30), text, font=f_head, fill=(40, 40, 40))
    d.line([(tx + 8, ty + 46), (tx + 8 + 5 * 82 + 72, ty + 46)], fill=(160, 160, 160))
    for i in range(21):
        f = i / 20.0
        d_new = m_new["table"][f] - m_ref["table"][f]
        d_old = m_old["table"][f] - m_ref["table"][f]
        vals = (f"{f:.2f}", f"{m_ref['table'][f]:.3f}", f"{m_old['table'][f]:.3f}",
                f"{m_new['table'][f]:.3f}", f"{d_new:+.3f}", f"{d_old:+.3f}")
        for j, text in enumerate(vals):
            colour = (30, 30, 30)
            if j == 4 and abs(d_new) > 0.035:
                colour = (170, 30, 30)
            if j == 5 and abs(d_old) > 0.2:
                colour = (160, 120, 120)
            d.text((tx + 8 + j * 82, ty + 54 + i * 16), text, font=f_mono, fill=colour)

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path)


# --------------------------------------------------------------------------- #
def _ref_profile(ref: dict) -> list[tuple[float, float]]:
    """The reference contour as a (r, z) lathe profile in the mesh frame."""
    scale = 2.0 * ref["H/W"]
    if ref.get("contour"):
        out = []
        for (y, left, right) in ref["contour"]:
            out.append((0.5 * (right - left) / ref["H"] * scale,
                        (ref["y_bottom"] - y) / (ref["H"] - 1) * scale))
        return out
    return [(REFERENCE[i / 20.0], i / 20.0 * scale) for i in range(21)]


def stem_span(profile: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Where `author_stem` puts the stalk: (centre lo, centre hi, top lo, top hi).

    The builder's math with d/2 = 1: `top_z` = the highest row, `cavity_floor` =
    `profile[-1]`, length = 0.30-0.45 d = 0.60-0.90 r_max, centre = the two
    rows' midpoint + 0.30 x length. The top span is what says whether the stalk
    clears the body at all (the long stalk also has the long half-height).
    """
    top = float(max(z for (_, z) in profile))
    floor = float(profile[-1][1])
    centres = [(top + floor) / 2.0 + 0.30 * length for length in (0.60, 0.90)]
    return min(centres), max(centres), centres[0] + 0.30, centres[1] + 0.45


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--photo", default=PHOTO)
    ap.add_argument("--no-photo", action="store_true", help="use the shipped table")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    if not args.no_photo and os.path.exists(args.photo):
        ref = extract_reference(args.photo)
        print(f"reference: {args.photo}")
        print(f"  mask chroma > {CHROMA_THRESHOLD}/255, bottom crop {BOTTOM_CROP:.0%}; "
              f"body rows y {ref['y_top']}..{ref['y_bottom']}, widest row "
              f"{ref['widest_y']}, W {ref['W']} px, H {ref['H']} px")
        print(f"  stem cut at row width < {TOP_WIDTH_FRACTION:.2f} W (the top kept row "
              f"is {ref['top_row_width']:.3f} W); shadow cut at < "
              f"{BASE_WIDTH_FRACTION:.2f} W (the bottom row {ref['bottom_row_width']:.3f} W, "
              f"the next {ref['next_row_width']:.3f} W)")
        print(f"  H/W {ref['H/W']:.4f}, r_max/H {ref['r_max/H']:.4f}, widest at "
              f"{ref['widest_z']:.3f} H")
        drift = max(abs(ref["table"][f] - REFERENCE[f]) for f in REFERENCE)
        print(f"  vs the shipped REFERENCE table: max |d r/rmax| {drift:.4f}"
              + ("  (OK)" if drift < 0.015 else "  << DRIFT - check the extraction"))
    else:
        why = "--no-photo" if args.no_photo else f"missing {args.photo}"
        print(f"reference: the shipped table ({why})")
        ref = {"H/W": REFERENCE_HW, "table": REFERENCE, "contour": None, "W": 0,
               "H": 0, "y_top": 0, "y_bottom": 0, "r_max/H": 1.0 / (2 * REFERENCE_HW),
               "widest_z": 0.307}
        if not args.no_photo:
            print("  NOTE: the photo is the primary evidence; the shipped table is "
                  "what the figure is drawn from.")

    new = meshes.pear_profile()
    old = legacy_pear_profile()
    ref_profile = _ref_profile(ref)
    m_ref, m_old, m_new = metrics(ref_profile), metrics(old), metrics(new)
    # the reference's own H/W is the photo's (the mesh frame above is only a
    # scaling); keep the measurement, not the reconstruction
    m_ref["H/W"] = ref["H/W"]
    m_ref["r/H_max"] = 1.0 / (2.0 * ref["H/W"])
    vol, cost = volume_fraction(new), mesh_cost(new)
    vol_old, cost_old = volume_fraction(old), mesh_cost(old)
    # the mass proxy's own arithmetic (`fruits.py`): density x 4/3 pi r^3 x 0.82
    shape = meshes.FRUIT_SHAPES["pear"]
    mass_d = 0.064
    sphere_d = (4.0 / 3.0) * math.pi * (mass_d / 2.0) ** 3
    mass_g = shape.density * sphere_d * 0.82 * 1000.0
    density_new = mass_g / 1000.0 / (vol["fraction"] * sphere_d)
    density_old = mass_g / 1000.0 / (vol_old["fraction"] * sphere_d)

    print()
    print(f"{'z/H':>5} {'ref':>7} {'current':>8} {'new':>7} {'new-ref':>8} {'cur-ref':>8}")
    for i in range(21):
        f = i / 20.0
        print(f"{f:5.2f} {m_ref['table'][f]:7.3f} {m_old['table'][f]:8.3f} "
              f"{m_new['table'][f]:7.3f} {m_new['table'][f] - m_ref['table'][f]:+8.3f} "
              f"{m_old['table'][f] - m_ref['table'][f]:+8.3f}")
    print()
    print(f"  H/W           ref {m_ref['H/W']:.4f}  current {m_old['H/W']:.4f}  "
          f"new {m_new['H/W']:.4f}")
    print(f"  widest at z/H ref {m_ref['widest_z']:.3f}  current {m_old['widest_z']:.3f}  "
          f"new {m_new['widest_z']:.3f}")
    print(f"  neck @0.80H   ref {m_ref['neck']:.3f}  current {m_old['neck']:.3f}  "
          f"new {m_new['neck']:.3f}   (r/rmax)")
    print(f"  base @0.05H   ref {m_ref['base']:.3f}  current {m_old['base']:.3f}  "
          f"new {m_new['base']:.3f}   (r/rmax)")
    print(f"  lip @1.00H    ref {m_ref['lip']:.3f}  current {m_old['lip']:.3f}  "
          f"new {m_new['lip']:.3f}   (r/rmax)")
    print(f"  stem cavity   new: {m_new['cavity_depth'] * 100:.2f} % of H deep inside a "
          f"{m_new['cavity_lip']:.3f} r_max lip; current: none")
    stem_old, stem_new = stem_span(old), stem_span(new)
    print(f"  stem (author_stem, r_max units, d/2 = 1): current centre "
          f"{stem_old[0]:+.2f}..{stem_old[1]:+.2f} and top {stem_old[2]:+.2f}"
          f"..{stem_old[3]:+.2f} under the body's {m_old['z_max']:+.2f} -> buried; new "
          f"centre {stem_new[0]:+.2f}..{stem_new[1]:+.2f}, top {stem_new[2]:+.2f}"
          f"..{stem_new[3]:+.2f} over the lip {m_new['z_max']:+.2f} -> "
          f"{stem_new[2] - m_new['z_max']:.2f}..{stem_new[3] - m_new['z_max']:.2f} "
          f"r_max visible (the photo reads ~0.47)")
    print(f"  rows          current {m_old['rows']} (z {m_old['z_min']:+.3f}"
          f"..{m_old['z_max']:+.3f}, top -> bottom); new {m_new['rows']} (z "
          f"{m_new['z_min']:+.3f}..{m_new['z_max']:+.3f}, bottom -> top)")
    print()
    print(f"  solid volume  new {vol['solid']:.3f} r_max^3 = {vol['fraction']:.4f}x the "
          f"4/3 pi r^3 sphere; current {vol_old['solid']:.3f} = "
          f"{vol_old['fraction']:.4f}x -> the new solid is "
          f"{vol['solid'] / vol_old['solid']:.3f}x the old at the same diameter")
    print(f"  mass (0.82 x sphere, `fruits.py`): {mass_g:.1f} g at {mass_d * 100:.2f} cm; "
          f"the solid's effective density is {density_new:.0f} kg/m^3 new vs "
          f"{density_old:.0f} old (the shape changed, the mass did not; the mass proxy "
          f"is x{vol['mass_vs_proxy']:.3f} the new solid - report only)")
    print(f"  surface {vol['area']:.3f} r_max^2; lathe {cost['segments']} segments x "
          f"{m_new['rows']} rings -> {cost['vertices']} verts / {cost['triangles']} tris "
          f"(current {cost_old['vertices']} / {cost_old['triangles']}, the pole fans "
          f"counted); facet sagitta at "
          f"the widest row {cost['sagitta_r']:.4f} r_max "
          f"({cost['sagitta_r'] * 0.065 / 2.0 * 1000:.2f} mm on a 65 mm pear)")
    print()
    checks = lathe_checks(new)
    for ok, text in checks:
        print(f"  [{'ok' if ok else 'FAIL'}] {text}")
    # m12: `author_stem` reads `profile[-1]` as the cavity floor - assert the
    # convention on the shipped profile and show where the legacy one breaks it.
    stem_ok = stem_checks(new, "new")
    for ok, text in stem_ok:
        print(f"  [{'ok' if ok else 'FAIL'}] {text}")
    print(f"  author_stem seats the stalk on profile[-1]: new "
          f"{new[-1][1]:+.3f} r_max (the cavity floor, "
          f"{new[-2][1] - new[-1][1]:.3f} below the lip); legacy "
          f"{old[-1][1]:+.3f} r_max (its base pole -> the stem is authored inside "
          f"the base, the buried stem)")
    worst = max(abs(m_new["table"][f] - m_ref["table"][f]) for f in m_ref["table"])
    hw_err = abs(m_new["H/W"] - m_ref["H/W"]) / m_ref["H/W"]
    print(f"  [{'ok' if worst <= 0.05 else 'FAIL'}] max |d r/rmax| vs the photo "
          f"{worst:.4f} (bar 0.05)")
    print(f"  [{'ok' if hw_err <= 0.05 else 'FAIL'}] H/W off the photo by "
          f"{hw_err * 100:.1f} % (bar 5 %)")
    ok = all(c[0] for c in checks) and all(c[0] for c in stem_ok) and worst <= 0.05 and hw_err <= 0.05
    print(f"  verdict: {'PASS' if ok else 'FAIL'}")

    figure(ref, new, old, m_ref, m_old, m_new, vol, cost, args.out)
    print(f"  figure: {os.path.relpath(args.out, ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
