"""P69 phase A1 - the finger-tip collider read at the P30-C magnitudes, and what
each magnitude buys and costs, offline.

    FRUIT_FINGER_TIP_DELTA=0      scripts/run.sh logs/p66/collider_read.py   # arm S (P66, re-used)
    FRUIT_FINGER_TIP_DELTA=-0.024 scripts/run.sh logs/p66/collider_read.py   # P30-C lower
    FRUIT_FINGER_TIP_DELTA=-0.035 scripts/run.sh logs/p66/collider_read.py   # P30-C mid
    FRUIT_FINGER_TIP_DELTA=-0.045 scripts/run.sh logs/p66/collider_read.py   # P30-C upper
    python3 logs/p69/tip_geometry.py            # the tables
    python3 logs/p69/tip_geometry.py --assert   # + the invariants the verdict rests on

The instrument is P66's (`logs/p66/collider_read.py`, extension A3 of P39): a
**robot-only** build, no `scene.start()`, no physics step, no attempt loop, that
reads the **authored** `.../contact_faces/tip_delta` boxes. This file adds no
simulator code - it reads the four JSONs and does arithmetic.

Everything below is in the **jaw frame**: `J` = the jaw centre (the plane the
command `_pad_standoff` sets), the tool axis `+z` = up (so "below the jaw" is
negative), and `r` = the fruit's radius.

The two numbers the whole question turns on, both from the record:

* `TIP_FACE = 80.5 mm` - the authored distal plane below the jaw centre, i.e.
  the plate tip. It is the *geometry*: `_author_flat_face` authors the box from
  the plate's proximal end to `tip_coord + delta`, `tip_coord = 80.5 mm`, and
  the jaw centre and the finger link origin share their position along the tool
  axis (the closing axis is x), so the box's distal plane is 80.5 mm below J.
* `STANDOFF = 70.0 mm` - `_pad_standoff(dynamic=True)` = `FRUIT_FINGER_LEN`
  (60) + `PAD_LIFT` (10); P42 measured the live value at 69.3-71.7 mm.

Hence the shipped **lip** (how far the plate reaches below the fruit's equator)
is `lip0 = TIP_FACE - STANDOFF = 10.5 mm`, and the plate's tip sits
`r - lip0` above the belt: 3.5-24.5 mm on the 2.8-7.0 cm pool. The measured
76.8 mm stop (`logs/166`) is 3.7 mm shorter because the *AABB corner* leads the
distal plane at a tilt (`logs/p39/P1_READ.md` section 5) - it is the **belt**
contact number, and it enters here only as the conservative bound.
"""

from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P66 = os.path.join(HERE, "..", "p66")

# --------------------------------------------------------------------------- #
# Measured / authored constants (each with its citation; do not re-derive).
# --------------------------------------------------------------------------- #
BELT_TOP = 1.170  # assets.py: belt_center_z 1.14 + belt_size_z 0.06/2

#: The authoring site's own tip coordinate (`scene._finger_face_frame` ->
#: `PLATE_TIP_COORD`), i.e. the box's distal plane at `delta = 0`.
TIP_FACE = 0.0805
#: The measured near-vertical belt stop (`logs/166`), 3.7 mm shorter: the AABB
#: corner leads the distal plane at a tilt (P39 P1_READ section 5).
TIP_MEAS = 0.0768

STANDOFF = 0.070  # `_pad_standoff(dynamic=True)`; measured 0.0693-0.0717 (P42)
INTERFERENCE = 0.0002  # the closure record's placed-face interference (P39)

#: The pool, `assets.py:441-454` (min/max diameter m).
POOL = {
    "lychee": (0.028, 0.038),
    "strawberry": (0.030, 0.045),
    "kiwi": (0.050, 0.068),
    "tomato": (0.050, 0.068),
    "peach": (0.058, 0.070),
    "pear": (0.058, 0.070),
    "orange": (0.060, 0.070),
    "apple": (0.062, 0.070),
}

#: The two operating attitudes. The descent is commanded T0 (fingers straight
#: down); P62's static T0 solve tracks it to 0.8 deg. The carry's measured tilt
#: on the left's *failing* legs is 24.6 deg (P63), 25.1 on P66's control rung.
THETA_DESCENT_DEG = 0.8
THETA_CARRY_DEG = 24.6

#: The P30-C magnitudes (the authorized hardware form) and the registration
#: arms this file prices.
MAGNITUDES = ("-0.024", "-0.035", "-0.045")

#: The current tree's dynamic descent residual (`logs/p68/accept_noharm.log`,
#: the `[motion] approach` rows' `end=`), against the v1-era 40-90 mm.
DESCENT_END_MM = (8.1, 10.3)

FILES = {
    "0": ("collider_read_0.json", P66),
    "-0.004": ("collider_read_m0p004.json", P66),
    "-0.024": ("collider_read_m0p024.json", HERE),
    "-0.035": ("collider_read_m0p035.json", HERE),
    "-0.045": ("collider_read_m0p045.json", HERE),
}
LINKS = (
    "openarm_left_left_finger",
    "openarm_left_right_finger",
    "openarm_right_left_finger",
    "openarm_right_right_finger",
)


def load(tag: str) -> dict:
    name, where = FILES[tag]
    with open(os.path.join(where, name), encoding="utf-8") as handle:
        return json.load(handle)


def patch_half(r: float, interference: float = INTERFERENCE) -> float:
    """Half the height of the contact patch implied by `interference` [m]."""
    return math.sqrt(max(r * r - (r - interference / 2.0) ** 2, 0.0))


def lip(r: float, delta: float, tip: float = TIP_FACE) -> float:
    """How far the plate reaches below the fruit's equator [m] (negative = above)."""
    return (tip + delta) - STANDOFF


def clearance(r: float, delta: float, tip: float = TIP_FACE) -> float:
    """The plate tip's height above the belt top at the shipped aim [m]."""
    return r - lip(r, delta, tip)


def face_span(r: float, delta: float, tip: float = TIP_FACE) -> tuple[float, float]:
    """The gripping face's z span about the fruit's equator [m] (lo, hi)."""
    lo = -lip(r, delta, tip)
    return lo, lo + (TIP_FACE + delta - (-0.0044))


def closest_gap(r: float, delta: float, tip: float = TIP_FACE,
                standoff: float = STANDOFF) -> float:
    """The pad face's signed distance to the fruit over the face's own span [m].

    The face plane is commanded at `r - interference/2` from the fruit's axis
    (the pair is `interference` inside the diameter), so the gap where the fruit
    is widest inside the face's span is `(r - interference/2) - max|width|`.
    Negative = interference (the grip's designed condition, `-0.1 mm` at the
    equator); positive = clear of the payload by that much.
    """
    lo = -(tip + delta - standoff)  # the plate's lower edge, above the equator
    hi = lo + (tip + delta + 0.0044)
    z_lo, z_hi = max(lo, -r), min(hi, r)
    if z_lo > z_hi:
        return r  # no z overlap at all: the plate is entirely above the fruit
    z_near = 0.0 if (z_lo <= 0.0 <= z_hi) else min(abs(z_lo), abs(z_hi))
    return (r - INTERFERENCE / 2.0) - math.sqrt(max(r * r - z_near * z_near, 0.0))


def contact(r: float, delta: float, tip: float = TIP_FACE) -> bool:
    """Does the gripping face overlap the contact patch at the shipped aim?

    The face spans `[lo, hi]` about the equator and the sphere is within the
    commanded interference only over `|z| <= h(r)`, so the criterion is
    `lo <= h(r)` (the `hi` side is always satisfied: the plate runs upward).
    """
    lo, _hi = face_span(r, delta, tip)
    return lo <= patch_half(r)


def table() -> list[str]:
    out: list[str] = []

    out.append("## 1. The authored boxes (P66's instrument, four magnitudes)\n")
    out.append(
        "`d_long` / `d_distal` are against arm S (`delta = 0`); `theta` is the "
        "tilt of the box's long axis from the vertical at the authored pose; the "
        "build print's own `long`/`distal plane` agree to 0.001 mm.\n"
    )
    out.append(
        "| delta mm | link | face | mid | **long** | d_long | **distal z (mm)** | "
        "d_distal | theta deg | prims |"
    )
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    base = load("0")
    for tag in ("0", "-0.004", *MAGNITUDES):
        data = load(tag)
        for link in LINKS:
            box = data["boxes"][link]
            ref = base["boxes"][link]
            d_long = box["dims_own_mm"][2] - ref["dims_own_mm"][2]
            d_dist = box["distal_world_z_mm"] - ref["distal_world_z_mm"]
            prims = data["collision_report"][link]
            out.append(
                f"| {tag} | `{link}` | {box['dims_own_mm'][0]:.2f} | "
                f"{box['dims_own_mm'][1]:.2f} | **{box['dims_own_mm'][2]:.2f}** | "
                f"{d_long:+.3f} | **{box['distal_world_z_mm']:.3f}** | "
                f"{d_dist:+.3f} | {box['theta_from_vertical_deg']:.4f} | "
                f"{prims['collision_prims_enabled']}/{prims['collision_prims']} |"
            )
    out.append("")

    out.append("## 2. The identity, and the projection at the two operating attitudes\n")
    out.append(
        "The shift is along the plate's **long axis**, so the vertical (world z) "
        "part is `|delta|*cos(theta)` and the along-belt part `|delta|*sin(theta)`. "
        "At the authored pose `theta = 0`, so the read is `|delta|` exactly; the "
        "other two rows are arithmetic on the measured attitudes.\n"
    )
    out.append("| delta mm | theta = 0 (authored read) | 0.8 deg (descent) | 24.6 deg (carry) | along-belt @24.6 |")
    out.append("|---|---|---|---|---|")
    for tag in MAGNITUDES:
        d = abs(float(tag))
        data = load(tag)
        got = data["boxes"][LINKS[0]]["vertical_span_mm"] - base["boxes"][LINKS[0]]["vertical_span_mm"]
        out.append(
            f"| {tag} | {abs(got):.3f} (read, the span shrinks) | {d * 1000 * math.cos(math.radians(0.8)):.3f} | "
            f"{d * 1000 * math.cos(math.radians(24.6)):.3f} | "
            f"{d * 1000 * math.sin(math.radians(24.6)):.3f} |"
        )
    out.append("")

    out.append("## 3. The contact invariant: what the shortening does to the grip\n")
    out.append(
        f"`lip0 = TIP_FACE - STANDOFF = {(TIP_FACE - STANDOFF) * 1000:.1f} mm` is the "
        "shipped lip. The gripping face spans `[-lip, -lip + long]` about the "
        "fruit's equator, and the sphere is within the commanded interference only "
        "over `|z| <= h(r)`, so **the grip touches iff `lip >= -h(r)`** and the "
        "patch is **intact** iff `lip >= +h(r)` (P39's `neutral_bound`).\n"
    )
    r_max = max(b for _a, b in POOL.values()) / 2.0
    r_min = min(a for a, _b in POOL.values()) / 2.0
    h_max, h_min = patch_half(r_max), patch_half(r_min)
    out.append(
        f"* contact patch: `h(r)` = {h_min * 1000:.2f} mm on the {2 * r_min * 100:.1f} cm "
        f"pool minimum .. **{h_max * 1000:.2f} mm on the {2 * r_max * 100:.1f} cm "
        f"maximum** (so the largest fruit binds both bounds);\n"
        f"* **no contact at all** beyond `|delta| = lip0 + h_max = "
        f"{(TIP_FACE - STANDOFF + h_max) * 1000:.2f} mm`;\n"
        f"* **patch clipped** beyond `|delta| = lip0 - h_max = "
        f"{(TIP_FACE - STANDOFF - h_max) * 1000:.2f} mm` (P39's registered bound, "
        f"which uses the 76.8 mm belt stop instead of 80.5 mm and therefore reads "
        f"{(TIP_MEAS - STANDOFF - h_max) * 1000:.2f} mm - the conservative form).\n"
    )
    out.append("| delta mm | tip below jaw | lip | plate lower edge above the equator | face span about the equator | any contact? | closest face-to-fruit gap (min .. max over the 8 classes) |")
    out.append("|---|---|---|---|---|---|---|")
    for tag in ("0", "-0.004", *MAGNITUDES):
        d = float(tag)
        lo, hi = face_span(r_max, d)
        gaps = [closest_gap(r, d) for r in sorted({a / 2 for a, _b in POOL.values()} | {b / 2 for _a, b in POOL.values()})]
        any_c = "**yes**" if contact(r_max, d) else "**NO**"
        out.append(
            f"| {tag} | {(TIP_FACE + d) * 1000:.1f} | {lip(r_max, d) * 1000:+.1f} | "
            f"{lo * 1000:+.1f} | {lo * 1000:+.1f} .. {hi * 1000:+.1f} | {any_c} | "
            f"{min(gaps) * 1000:+.1f} .. {max(gaps) * 1000:+.1f} mm |"
        )
    out.append("")
    out.append(
        "The last column is over the eight pool classes (`-0.1 mm` is the shipped "
        "grip's own designed interference at the equator, so `<= 0` is contact). "
        "Even the class that comes closest leaves a **positive** gap, so the close "
        "reaches the commanded span **without touching the payload** - the pads "
        "close on air and the fruit is left on the belt. It is not a degraded grip; "
        "it is no grip.\n"
    )
    out.append(
        "**Sensitivity (the verdict does not turn on one standoff).** The closest "
        "class at `delta = -24 mm` reads a gap of\n"
    )
    out.append("| convention | standoff | closest gap at -24 (7.0 cm apple) | at -35 | at -45 |")
    out.append("|---|---|---|---|---|")
    for label, so in (
        ("the model (`_pad_standoff`)", STANDOFF),
        ("measured low end (P42)", 0.0693),
        ("measured high end (P42)", 0.0717),
        ("the most aggressive measured seat (D2a -8 mm)", STANDOFF - 0.008),
    ):
        cells = " | ".join(
            f"{closest_gap(r_max, float(t), standoff=so) * 1000:+.1f} mm" for t in MAGNITUDES
        )
        out.append(f"| {label} | {so * 1000:.1f} mm | {cells} |")
    out.append("")

    out.append("## 4. What each magnitude buys, and where\n")
    out.append(
        "| delta mm | belt at the **descent** (0.8 deg) | belt at the **carry** (24.6 deg, vertical part) | along-belt at the carry | **rail at the crossing** |")
    out.append("|---|---|---|---|---|")
    for tag in MAGNITUDES:
        d = abs(float(tag))
        out.append(
            f"| {tag} | **+{d * 1000 * math.cos(math.radians(THETA_DESCENT_DEG)):.1f} mm** | "
            f"+{d * 1000 * math.cos(math.radians(THETA_CARRY_DEG)):.1f} mm | "
            f"{d * 1000 * math.sin(math.radians(THETA_CARRY_DEG)):.1f} mm upstream | "
            f"**+0.0 mm** |"
        )
    out.append("")
    out.append(
        "* **The rail number is zero by construction, not by arithmetic.** The "
        "`clr=` / `clr_win=` fields read `_payload_clearance` = the **payload's** "
        "lowest point (`fruit_z - support_radius`) against the rail top; the plate "
        "tip is `STANDOFF + r - TIP_FACE` = "
        f"{(STANDOFF + r_max - TIP_FACE) * 1000:.1f} .. "
        f"{(STANDOFF + r_min - TIP_FACE) * 1000:.1f} mm **above** the payload's "
        "bottom on the pool, so the payload sets the crossing and the tip cannot. "
        "A shorter tip raises the tip further out of the way; it moves nothing.\n"
        "* **The descent number is real but unconsumed.** At the shipped aim the "
        "tip is already `r - lip0` = "
        f"{(r_min - (TIP_FACE - STANDOFF)) * 1000:.1f} "
        f".. {(r_max - (TIP_FACE - STANDOFF)) * 1000:.1f} mm above the belt, and the "
        f"descent's residual is {DESCENT_END_MM[0]:.1f}-{DESCENT_END_MM[1]:.1f} mm "
        "*above* the aim (a jaw error, not a tip contact). Nothing on the shipped "
        "line spends belt clearance at the tip, so the purchase is unspent.\n"
        "* **The carry number is the cost side of the same coin**: the vertical "
        "part it buys is the lip it removes (1:1 with `lip` by construction), and "
        "the lip is the only material the payload has to walk out of "
        "(`logs/w8/B_RESULTS.md`, `logs/p61/P2_RESULTS.md`).\n"
    )

    out.append("## 5. The cost side\n")
    out.append(
        f"1. **The contact patch, which is 3.3-5.3 mm tall, not 85 mm.** The plate's "
        f"length is not the patch (P39 §6): the face is at `r - 0.2 mm`, so the "
        f"sphere can only be within it over `|z| <= {h_min * 1000:.2f}"
        f"..{h_max * 1000:.2f} mm`. Shortening by 24-45 mm does not shrink a "
        f"contact patch - it deletes it (§3).\n"
        "2. **No mass or inertia term moves.** The box is authored with "
        "`UsdPhysics.CollisionAPI` only (`_author_flat_face`, `scene.py:1332`); the "
        "finger link's `physics:mass` is authored in the asset "
        "(`assets/openarm_flat/openarm_flat_deinst.usda`), so a shorter collider "
        "changes no dynamic property. Verified at the code and the asset, not "
        "measured.\n"
        "3. **The authored collider and the visual mesh diverge by `|delta|`** - "
        "the P39 A3 caveat, and here it is 24-45 mm on a 84.9 mm plate. The "
        "rendered hand is unchanged (the `visuals/` subtree is never touched), so "
        "on the **direct/policy** path the image the policy conditions on shows a "
        "hand 24-45 mm deeper than the one that collides - and P36 measured that "
        "the image channel is the one that carries the park's win.\n"
        "4. **The matched pair is a null, so there is no free form of it.** "
        "`lip = (tip + delta) - (standoff - drop)`: shortening by `d` and lowering "
        "the aim by `d` leaves both `lip` and the belt clearance exactly unchanged "
        "(P39 check 2, re-asserted below). The pad asset therefore has exactly one "
        "degree of freedom and it trades lip for belt clearance 1:1.\n"
    )
    return out


def checks() -> list[tuple[str, bool, object]]:
    out: list[tuple[str, bool, object]] = []
    base = load("0")
    # (1) every magnitude authors exactly delta on the long axis, on all 4 links.
    worst = 0.0
    for tag in MAGNITUDES:
        data = load(tag)
        for link in LINKS:
            worst = max(
                worst,
                abs((data["boxes"][link]["dims_own_mm"][2]
                     - base["boxes"][link]["dims_own_mm"][2]) - 1000 * float(tag)),
            )
    out.append(("each magnitude authors |delta| on the long axis, 4/4 links",
                worst < 1e-5, f"max err {worst:.2e} mm (float32 scale)"))
    # (2) the same on the world-z (distal plane) reading, at theta = 0.
    worst = 0.0
    for tag in MAGNITUDES:
        data = load(tag)
        for link in LINKS:
            theta = data["boxes"][link]["theta_from_vertical_deg"]
            want = 1000 * abs(float(tag)) * math.cos(math.radians(theta))
            got = data["boxes"][link]["distal_world_z_mm"] - base["boxes"][link]["distal_world_z_mm"]
            worst = max(worst, abs(got - want))
    out.append(("distal plane moves |delta|*cos(theta) == |delta| at the authored pose",
                worst < 1e-6, f"max err {worst:.2e} mm"))
    # (3) the proximal plane and the other two dimensions do not move.
    ok = True
    for tag in MAGNITUDES + ("-0.004",):
        data = load(tag)
        for link in LINKS:
            b, s = data["boxes"][link], base["boxes"][link]
            ok = ok and abs(b["proximal_world_z_mm"] - s["proximal_world_z_mm"]) < 1e-6
            ok = ok and abs(b["dims_own_mm"][0] - s["dims_own_mm"][0]) < 1e-9
            ok = ok and abs(b["dims_own_mm"][1] - s["dims_own_mm"][1]) < 1e-9
    out.append(("the proximal plane and the face/mid dimensions are invariant", ok, "4 links x 4 arms"))
    # (4) exactly one collider enabled per finger link (the box, not a second one).
    ok = all(
        load(t)["collision_report"][link]["collision_prims_enabled"] == 1
        for t in MAGNITUDES for link in LINKS
    )
    out.append(("exactly one enabled collider per finger link at every magnitude", ok, "1/3"))
    # (5) lip + belt clearance == r, exactly, for every pool class and magnitude.
    worst = 0.0
    for tag in MAGNITUDES + ("0", "-0.004"):
        for _name, (dmin, dmax) in POOL.items():
            for dia in (dmin, dmax):
                r = dia / 2.0
                worst = max(worst, abs(lip(r, float(tag)) + clearance(r, float(tag)) - r))
    out.append(("lip + tip-belt clearance == r (every class, every magnitude)",
                worst < 1e-12, f"max err {worst:.2e} m"))
    # (6) THE VERDICT: no contact on any pool class at any authorized magnitude.
    rows = []
    for tag in MAGNITUDES:
        d = float(tag)
        rows.append(all(not contact(dia / 2.0, d) for _n, (a, b) in POOL.items() for dia in (a, b)))
    out.append(("no contact at all on any of the 8 classes at ANY authorized magnitude",
                all(rows), rows))
    # (6b) and the closest approach is a strictly positive gap (not a graze).
    worst = 1e9
    for tag in MAGNITUDES:
        for _n, (a, b) in POOL.items():
            for dia in (a, b):
                worst = min(worst, closest_gap(dia / 2.0, float(tag)))
    out.append(("the closest face-to-fruit gap is strictly positive", worst > 0.001,
                f"min {worst * 1000:.2f} mm"))
    # (6c) ... and stays positive under the most aggressive measured seat (D2a -8 mm).
    worst_d2a = min(
        closest_gap(dia / 2.0, float(tag), standoff=STANDOFF - 0.008)
        for tag in MAGNITUDES for _n, (a, b) in POOL.items() for dia in (a, b)
    )
    out.append(("... and with the D2a -8 mm seat the -24 mm arm is still clear",
                closest_gap(0.035, -0.024, standoff=STANDOFF - 0.008) > 0, f"min {worst_d2a * 1000:.2f} mm at -24"))
    # (7) the admissible band is far below the authorized one.
    h_max = patch_half(0.070 / 2.0)
    any_c = TIP_FACE - STANDOFF + h_max
    full = TIP_FACE - STANDOFF - h_max
    out.append(("the authorized magnitudes are >= 1.8x beyond even the 'any contact' bound",
                min(abs(float(t)) for t in MAGNITUDES) >= 1.8 * any_c,
                (any_c * 1000, full * 1000, min(abs(float(t)) for t in MAGNITUDES) * 1000)))
    # (8) the matched pair is a null (P39 check 2, re-asserted on the face tip).
    ok = True
    for d in (0.004, 0.024, 0.045):
        for r in (0.014, 0.035):
            a = clearance(r, 0.0)
            b = clearance(r, -d, TIP_FACE)  # shorter tip
            b = b - d  # ... and the aim lowered by the same d
            ok = ok and abs(a - b) < 1e-12
    out.append(("shorten by d + lower the aim by d leaves the tip's height unchanged",
                ok, "4 combinations"))
    # (9) the rail number is zero: the payload hangs below the tip on every class.
    ok = all(STANDOFF + dia / 2.0 - TIP_FACE > 0 for _n, (a, b) in POOL.items() for dia in (a, b))
    out.append(("the payload's lowest point is below the plate tip on every class (rail = tip-free)",
                ok, f"{(STANDOFF + 0.014 - TIP_FACE) * 1000:.1f} .. {(STANDOFF + 0.035 - TIP_FACE) * 1000:.1f} mm"))
    # (10) the tip clears the belt at the shipped aim on every class.
    ok = all(clearance(dia / 2.0, 0.0) > 0 for _n, (a, b) in POOL.items() for dia in (a, b))
    out.append(("the shipped aim already clears the belt at the tip on every class",
                ok, f"{(0.014 - (TIP_FACE - STANDOFF)) * 1000:.1f} .. {(0.035 - (TIP_FACE - STANDOFF)) * 1000:.1f} mm"))
    return out


def main() -> int:
    print("# P69 phase A1 - the finger-tip collider at the P30-C magnitudes\n")
    print("generated by `logs/p69/tip_geometry.py`; inputs are the four")
    print("`collider_read_*.json` from P66's robot-only instrument.\n")
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
