"""P39 phase 1 - the finger geometry audit, offline.

No simulator, no USD parse: every number is either a measured constant with a
citation or arithmetic on those constants.  Re-derivable:

    python3 logs/p39/finger_geometry.py            # the tables
    python3 logs/p39/finger_geometry.py --assert   # + the invariants the design rests on

The two quantities the design turns on, in the tool frame (jaw centre J, tool
axis down):

    L      jaw centre -> the plate's lowest point ("tip below jaw")
    s      the commanded jaw standoff above the fruit's centre

so the tip sits at ``C + s - L``, i.e. ``L - s`` below the fruit's centre.  With
``s`` = `FRUIT_FINGER_LEN` (0.060, the *model* value) + `FRUIT_DYNAMIC_PAD_LIFT`
(0.010) = 0.070 and the *physical* plate measured at L = 0.0768 (logs/166, the
near-vertical pose), the tip is 6.8 mm below the fruit's equator: that 6.8 mm is
the only "lip" the pinch has below the widest section, and everything below the
equator is where the walk-out (`logs/w8/B_RESULTS.md` section 2: +z, out through
the fingertips) leaves.  The counterpart is the tip's clearance to the belt,
``r - 0.0068``; the two sum to ``r`` exactly, so on a fixed aim a shorter tip is
a 1:1 purchase of belt clearance paid for in lip, and a longer one the mirror.
"""

from __future__ import annotations

import math
import sys

# --------------------------------------------------------------------------- #
# Measured constants (each with its citation; do not re-derive by hand).
# --------------------------------------------------------------------------- #
BELT_TOP = 1.170  # assets.py: belt_center_z 1.14 + belt_size_z 0.06/2
FRUIT_DIA_MIN, FRUIT_DIA_MAX = 0.028, 0.070  # assets.py:436-452 (28-70 mm -> r 14-35)

#: The model's standoff, i.e. what the *task* believes the tip offset is.
FINGER_LEN_MODEL = 0.060  # tasks.py `FRUIT_FINGER_LEN` default
PAD_LIFT = 0.010  # tasks.py:49 `PAD_LIFT` (FRUIT_DYNAMIC_PAD_LIFT inherits it)
STANDOFF = FINGER_LEN_MODEL + PAD_LIFT  # 0.070 = `_pad_standoff(dynamic=True)`

#: The physical tip below the jaw centre.  Two measured stops, two poses:
#:   * 0.0768 - `logs/166_collision_probe.log`: jaw stops at belt+0.0768, the
#:     finger AABB 24 mm inside the slab (the plate's distal face is the contact);
#:   * 0.0586 - `logs/p30a/10_probe_parts_default.log` (the "P0" stop, the value
#:     `FRUIT_STATION_FLOOR` carries): the same drive, a different wrist
#:     configuration - the AABB bottoms out 13 mm *above* the slab, so there the
#:     *corner* of the tilted plate leads, not the distal face.
TIP_VERTICAL = 0.0768
TIP_TILTED = 0.0586
#: `assets.py:642` `SceneConfig.finger_length` - the model of the same quantity.
FINGER_LEN_ASSET = 0.076

#: The finger plate's link-local extents, from the build's own readout of
#: `_finger_face_frame` (identical on all four links; e.g.
#: `logs/p3face/screen_v.log`): (face, mid, long) = 33.3 / 61.0 / 84.9 mm, the
#: tip at +80.5 mm along e_long, the face plane at +5.8 mm along e_face.
PLATE_FACE, PLATE_MID, PLATE_LONG = 0.0333, 0.0610, 0.0849
PLATE_TIP_COORD, PLATE_FACE_COORD = 0.0805, 0.0058

#: The hand's opening and the pried-open limit.
LINK_SPAN_OPEN = 0.098  # assets.py: link origins at full opening
FACE_GAP_OPEN = 0.0758  # assets.py: faces 75.8 mm apart at full opening
LINK_SPAN_PRIED = 0.0981  # logs/w8/B_RESULTS.md section 2 (17/31 escapes, median)

#: The supply's lateral/along spacings that set the neighbour corridor.
PATCH_SEP = (0.085, 0.120)  # fruits.py / AGENTS: patch sheet 0.085-0.12 m
SCATTER_GAP = (0.100, 0.350)  # fruits.py: scattered supply gaps

#: The commanded interference of the closed grip (the closed span is 0.2 mm
#: *inside* the measured diameter on the placed legs; `01_left_corpus.txt`).
INTERFERENCE = 0.0002

#: The two measured grip-plane drops of the R8-A D2a screen.
D2A_DROPS = (-0.008, -0.004)

#: The supply's own diameters, from the P39 corpus (`01_left_corpus.txt`).
CORPUS_DIA = [0.030, 0.034, 0.037, 0.054, 0.056, 0.059, 0.061, 0.063, 0.065,
              0.066, 0.068, 0.069, 0.070]


def patch_half_height(r: float, interference: float = INTERFERENCE) -> float:
    """Half the height of the contact patch: where the sphere is inside the span."""
    return math.sqrt(max(r * r - (r - interference / 2) ** 2, 0.0))


def neutral_bound() -> float:
    """The largest shortening that leaves the contact patch intact on every fruit.

    The patch's lower edge is `patch_half_height(r)` below the equator; a plate
    whose distal edge is above that edge clips the patch.  The worst fruit is the
    largest (its patch is the tallest), so the bound is `lip0 - h(35 mm)`.
    """
    return lip(FRUIT_DIA_MAX / 2) - patch_half_height(FRUIT_DIA_MAX / 2)


def lip(r: float, tip: float = TIP_VERTICAL, drop: float = 0.0) -> float:
    """How far the plate reaches below the fruit's equator [m]."""
    return tip - (STANDOFF - drop)


def clearance(r: float, tip: float = TIP_VERTICAL, drop: float = 0.0) -> float:
    """The tip's clearance above the belt top [m] (negative = inside the slab)."""
    return r - lip(r, tip, drop)


def table() -> list[str]:
    out: list[str] = []
    out.append("## 1. The tip, the lip and the belt\n")
    out.append(
        "`lip` = how far the plate reaches below the fruit's equator; "
        "`clear` = the tip's height above the belt top.  Their sum is `r`.\n"
    )
    out.append("| source | tip below jaw | lip | clear, 3.0 cm | clear, 5.6 cm | clear, 7.0 cm |")
    out.append("|---|---|---|---|---|---|")
    for label, tip in (
        ("measured, near-vertical pose (`logs/166`)", TIP_VERTICAL),
        ("measured, tilted pose (P0, `logs/p30a/10`)", TIP_TILTED),
        ("the task's model (`FRUIT_FINGER_LEN` 60 mm)", FINGER_LEN_MODEL),
        ("`SceneConfig.finger_length` (76 mm)", FINGER_LEN_ASSET),
    ):
        cells = []
        for d in (0.030, 0.056, 0.070):
            r = d / 2
            cells.append(f"{clearance(r, tip) * 1000:+.1f} mm")
        out.append(
            f"| {label} | {tip * 1000:.1f} mm | {lip(0.030 / 2, tip) * 1000:+.1f} mm | "
            + " | ".join(cells)
            + " |"
        )
    out.append("")

    out.append("## 2. A signed tip change `delta` at the shipped aim\n")
    out.append(
        "`delta` < 0 shortens the plate (the P39 brief's short tip), `delta` > 0 "
        "extends it.  The lip and the belt clearance move 1:1 in opposite "
        "directions; the belt bound is `delta <= r - lip0` for the smallest fruit.\n"
    )
    out.append("| delta mm | tip below jaw | lip mm | clear 2.8 cm | clear 5.6 cm | clear 7.0 cm | legal on the 2.8 cm pool min | patch (7.0 cm worst) |")
    out.append("|---|---|---|---|---|---|---|---|")
    for dmm in (-20, -10, -6, -3, 0, 3, 6, 8, 10):
        d = dmm / 1000.0
        tip = TIP_VERTICAL + d  # delta < 0 = a shorter plate (a smaller tip-below-jaw)
        cells = [f"{clearance(dd / 2, tip) * 1000:+.1f}" for dd in (0.028, 0.056, 0.070)]
        c28 = clearance(0.028 / 2, tip)
        ok = ("yes" if c28 >= 0.002 else "**marginal (<2 mm)**" if c28 >= 0 else "**NO (tip in the slab)**")
        clip = patch_half_height(FRUIT_DIA_MAX / 2) - lip(0.028 / 2, tip)
        pc = "intact" if clip <= 0.0 else f"**clipped {clip * 1000:.1f} mm**"
        out.append(
            f"| {dmm:+d} | {tip * 1000:.1f} | {lip(0.028 / 2, tip) * 1000:+.1f} | "
            + " | ".join(cells) + f" | {ok} | {pc} |"
        )
    out.append("")
    out.append(
        f"- The extension bound is `delta <= r - lip0`: **"
        f"{(FRUIT_DIA_MIN / 2 - lip(FRUIT_DIA_MIN / 2)) * 1000:.1f} mm** on the "
        f"{FRUIT_DIA_MIN * 100:.1f} cm pool minimum (the binding fruit: `assets.py` "
        f"lychee 2.8-3.8 cm), {(0.030 / 2 - lip(0.030 / 2)) * 1000:.1f} mm on the "
        f"3.0 cm lychee the P39 corpus actually drew, "
        f"{(0.034 / 2 - lip(0.034 / 2)) * 1000:.1f} mm on the 3.4 cm strawberry, "
        f"{(FRUIT_DIA_MAX / 2 - lip(FRUIT_DIA_MAX / 2)) * 1000:.1f} mm on the 7.0 cm apple."
    )
    out.append(
        f"- **The free-shortening bound is `delta >= -(lip0 - h_max)` = "
        f"{-neutral_bound() * 1000:.1f} mm**: below that the plate's distal edge "
        f"rises above the contact patch's lower edge and clips it (the patch is "
        f"{2 * patch_half_height(FRUIT_DIA_MAX / 2) * 1000:.1f} mm tall on the "
        f"largest fruit, and its lower edge sits "
        f"{patch_half_height(FRUIT_DIA_MAX / 2) * 1000:.1f} mm below the equator)."
    )
    out.append("")

    out.append("## 3. The R8-A D2a grip-plane drop, re-read against the tip\n")
    out.append(
        "`FRUIT_GRIP_PLANE_DROP` lowers the *jaw command* (a smaller standoff), so it "
        "costs exactly `drop` of tip clearance and buys exactly `drop` of lip.  The "
        "form is belt-legal only for `r >= lip0 + drop`.\n"
    )
    out.append("| drop mm | needs r >= | legal dia >= | flails / battery (measured) |")
    out.append("|---|---|---|---|")
    for d in D2A_DROPS:
        need = lip(FRUIT_DIA_MIN / 2) + abs(d)
        out.append(f"| {d * 1000:+.0f} | {need * 1000:.1f} mm | {2 * need * 1000:.1f} mm | see R8-A |")
    out.append(
        f"| {-20:+d} | "
        f"{(lip(FRUIT_DIA_MIN / 2) + 0.020) * 1000:.1f} mm | "
        f"{2 * (lip(FRUIT_DIA_MIN / 2) + 0.020) * 1000:.1f} mm | not measured |"
    )
    out.append("")

    out.append("## 4. The corridor: the neighbour and the jaws\n")
    out.append(
        "At the pick the jaws close along world **X** (the `top_down_x` posture: "
        "`mirror_across_xz(top_down_quaternion(\"x\"))`), so `e_face` = the closing axis "
        "= **across** the belt and `e_mid` = **along** the belt travel (Y).  The plate "
        "is therefore `PLATE_FACE` 33.3 mm *thick* in the closing direction and "
        "`PLATE_MID` 61.0 mm *along* the belt.  A neighbour at spacing `s` along the "
        "belt is clear of the plate's near edge by `s - r_n - PLATE_MID/2`.\n"
    )
    out.append("| spacing | neighbour r | plate edge clearance (along the belt) | verdict |")
    out.append("|---|---|---|---|")
    for s in (*PATCH_SEP, *SCATTER_GAP):
        for rn in (0.015, 0.035):
            gap = s - rn - PLATE_MID / 2
            out.append(f"| {s * 1000:.0f} mm | {rn * 1000:.0f} mm | {gap * 1000:+.1f} mm | "
                       + ("clear" if gap > 0 else "**overlap**") + " |")
    out.append("")
    out.append(
        f"- The free corridor *between* the open faces is **{FACE_GAP_OPEN * 1000:.1f} mm**, "
        f"i.e. {(FACE_GAP_OPEN - FRUIT_DIA_MAX) * 1000:.1f} mm wider than the largest fruit "
        f"and {(FACE_GAP_OPEN - FRUIT_DIA_MIN) * 1000:.1f} mm wider than the smallest."
    )
    out.append(
        f"- The pried-open span is {LINK_SPAN_PRIED * 1000:.1f} mm between link origins "
        f"(the finger drive's limit), which is what an escaping payload wedges against."
    )
    out.append("")

    out.append("## 5. The corner term (why the two measured stops differ)\n")
    out.append(
        "At a tool tilt `theta` the plate's lowest point is a corner, not the distal "
        "face, and it drops by `half_extent * sin(theta)` below the distal plane.  The "
        "two candidate half-extents are the plate's half-thickness in the closing "
        "direction and its half-length along the belt.\n"
    )
    out.append("| theta deg | closing-axis half (16.65 mm) | along-belt half (30.5 mm) |")
    out.append("|---|---|---|")
    for deg in (2, 5, 10, 20):
        s = __import__("math").sin(__import__("math").radians(deg))
        out.append(f"| {deg} | {PLATE_FACE / 2 * s * 1000:.1f} mm | {PLATE_MID / 2 * s * 1000:.1f} mm |")
    out.append("")
    out.append(
        f"- The measured spread `TIP_VERTICAL - TIP_TILTED` = "
        f"**{(TIP_VERTICAL - TIP_TILTED) * 1000:.1f} mm** is the same order as the "
        f"face-half term at 20-30 deg: the P0 stop is a *corner* stop."
    )
    out.append("")

    out.append("## 6. The contact band and the contact patch\n")
    out.append(
        "**The contact patch has a height.**  With `PLATE_LONG` the plate's length "
        "is not the patch: the faces are commanded `INTERFERENCE` 0.2 mm inside the "
        "measured diameter, so the sphere's local width is within the interference "
        "only over `|h| <= sqrt(r^2 - (r - INTERFERENCE/2)^2) ~ sqrt(INTERFERENCE*r)` "
        "about the equator.\n"
    )
    out.append("| fruit | contact patch height (both faces) | lip below the patch |")
    out.append("|---|---|---|")
    for d in (0.028, 0.034, 0.056, 0.070):
        r = d / 2
        h = math.sqrt(max(r * r - (r - INTERFERENCE / 2) ** 2, 0.0))
        out.append(f"| {d * 100:.1f} cm | {2 * h * 1000:.1f} mm | "
                   f"{(lip(r) - h) * 1000:+.1f} mm |")
    out.append("")
    out.append(
        "So the *patch* is a band 3.3-5.3 mm tall about the equator and at most "
        f"`PLATE_MID` {PLATE_MID * 1000:.1f} mm wide; the plate's length is *not* the "
        "patch - it only fixes the height of the distal edge, i.e. the lip.\n"
    )
    for dmm in (-6, 0, 6):
        tip = TIP_VERTICAL + dmm / 1000.0
        lo, hi = -(tip - STANDOFF), PLATE_LONG - (tip - STANDOFF)
        out.append(f"- delta {dmm:+d} mm: the face spans {lo * 1000:+.1f} .. {hi * 1000:+.1f} mm "
                   f"about the equator; the equator is {(-lo) * 1000:+.1f} mm above the distal edge.")
    out.append("")
    return out


def checks() -> list[tuple[str, bool, object]]:
    rs = [d / 2 for d in CORPUS_DIA]
    out = []
    # (1) lip + clearance == r, exactly, for every fruit and every tip/drop.
    ok = True
    worst = 0.0
    for r in rs:
        for tip in (TIP_VERTICAL, TIP_TILTED, FINGER_LEN_MODEL):
            for drop in (0.0, 0.004, 0.008, 0.020):
                e = abs((lip(r, tip, drop) + clearance(r, tip, drop)) - r)
                worst = max(worst, e)
                ok = ok and e < 1e-12
    out.append(("lip + tip-belt clearance == r (every r, tip, drop)", ok, f"max err {worst:.2e} m"))
    # (2) the matched pair (shorten by d and lower the aim by d) is a geometric null.
    ok = True
    for d in (0.003, 0.006, 0.020):
        a = clearance(0.030 / 2, TIP_VERTICAL) 
        b = clearance(0.030 / 2, TIP_VERTICAL - d, d)
        ok = ok and abs(a - b) < 1e-12
    out.append(("shorten by d + drop by d leaves the tip's world height unchanged", ok, a))
    # (3) the shipped aim is belt-legal for the smallest fruit at both measured tips.
    out.append(
        (
            "the shipped aim clears the belt on the smallest corpus fruit",
            clearance(FRUIT_DIA_MIN / 2) > 0 and clearance(FRUIT_DIA_MIN / 2, TIP_TILTED) > 0,
            (clearance(FRUIT_DIA_MIN / 2) * 1000, clearance(FRUIT_DIA_MIN / 2, TIP_TILTED) * 1000),
        )
    )
    # (4) the D2a -8 mm drop is at/past the belt on the smallest fruit.
    d2a = clearance(FRUIT_DIA_MIN / 2, TIP_VERTICAL, 0.008)
    d2a30 = clearance(0.030 / 2, TIP_VERTICAL, 0.008)
    out.append(("-8 mm grip-plane drop is at the belt on the 2.8 cm pool minimum "
                "and +0.2 mm on the 3.0 cm corpus fruit",
                abs(d2a) < 0.003 and abs(d2a30 - 0.0002) < 1e-9,
                (d2a * 1000, d2a30 * 1000)))
    # (4b) the free-shortening bound is ~4 mm and a -4 mm form keeps the patch.
    out.append(("-4 mm leaves the contact patch intact on every fruit",
                neutral_bound() >= 0.004
                and all(lip(d / 2, TIP_VERTICAL - 0.004) >= patch_half_height(d / 2) for d in CORPUS_DIA),
                neutral_bound() * 1000))
    out.append(("-6 mm clips the patch on the largest fruit",
                lip(FRUIT_DIA_MAX / 2, TIP_VERTICAL - 0.006) < patch_half_height(FRUIT_DIA_MAX / 2),
                (patch_half_height(FRUIT_DIA_MAX / 2) - lip(FRUIT_DIA_MAX / 2, TIP_VERTICAL - 0.006)) * 1000))
    # (5) the extension bound is the corpus's smallest fruit.
    bound = FRUIT_DIA_MIN / 2 - lip(FRUIT_DIA_MIN / 2)
    out.append(("the legal extension bound >= 6 mm on the whole corpus", bound >= 0.006,
                bound * 1000))
    # (6) the neighbour corridor never binds at the designed spacings.
    worst = min(s - 0.035 - PLATE_MID / 2 for s in PATCH_SEP)
    out.append(("the plate edge clears a 7.0 cm neighbour at the tightest patch spacing",
                worst > 0, worst * 1000))
    # (7) the open face gap clears the largest fruit.
    out.append(("the open face gap clears the largest fruit", FACE_GAP_OPEN > FRUIT_DIA_MAX,
                (FACE_GAP_OPEN - FRUIT_DIA_MAX) * 1000))
    # (8) the model standoff is shorter than the physical tip (the reporting gap).
    out.append(("the task's model tip is shorter than the measured tip by ~16.8 mm",
                abs((TIP_VERTICAL - FINGER_LEN_MODEL) - 0.0168) < 1e-9,
                (TIP_VERTICAL - FINGER_LEN_MODEL) * 1000))
    return out


def main() -> int:
    print("# P39 phase-1 finger geometry (generated by logs/p39/finger_geometry.py)\n")
    for line in table():
        print(line)
    if "--assert" in sys.argv:
        print("## `--assert`\n")
        bad = 0
        for name, ok, got in checks():
            print(f"- {'PASS' if ok else 'FAIL'} {name} (got {got})")
            bad += 0 if ok else 1
        print(f"\n{'PASS' if bad == 0 else f'{bad} FAILED'}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
