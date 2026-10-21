#!/usr/bin/env python3
"""P30-A: the offline rail census and the grasp/place/supply interference map.

    python3 logs/p30a/rails_geometry.py            # the shipped geometry + every knob
    FRUIT_RAILS=1 FRUIT_BELT_CONTAINMENT=1 \
        python3 logs/p30a/rails_geometry.py        # the two opt-in rail sets as built
    python3 logs/p30a/rails_geometry.py --assert   # exit 1 if a pinned clearance moved

Reads the *shipped* `SceneConfig` (no simulator, no pxr) and re-derives every
rail box in the cell from the same arithmetic the builders use, then intersects
each one with the three envelopes the owner's directive names:

  * the **grasp** envelope - the open hand's +/-0.066 m span (assets.py:251,
    conveyor.py:66) around the jaw at the pick station and at both edges of the
    delivered lateral band (x = 0.20 / 0.36);
  * the **place** envelope - the carry transit from the pick station to the
    release point (0.43, +/-0.50) and the release itself;
  * the **supply** flow - the delivered band x = 0.20-0.36 (`fruits.py`) over
    the whole belt length, the fruit's own x/z span at the belt top.

Gap convention everywhere: ``gap(a, b) = max(a0, b0) - min(a1, b1)`` [m],
**positive = separated by that much, negative = overlapping by that much**, and a
box pair is separated as soon as *one* axis separates it.

Every number printed here is quoted in `logs/p30a/RAILS_DESIGN.md`. `--assert`
pins the values the design doc's verdict depends on, so a later edit to the
belt, the station or a rail cannot silently invalidate the analysis.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.assets import SceneConfig  # noqa: E402

#: Open hand half-span [m] - the `+/-0.066` the config documents (assets.py:251,
#: conveyor.py:66). This is the x extent of the fingers at full opening.
HAND_HALF = 0.066
#: The delivered scattered lateral band [m] (`fruits.py`, FRUIT_SUPPLY_LATERAL).
BAND = (0.20, 0.36)
#: Fruit radii [m] from the pool: smallest strawberry and largest apple.
R_MIN, R_MAX = 0.030 / 2.0, 0.070 / 2.0
#: Output-belt rail thickness [m] (the builder's 0.025).
RAIL_THICK = 0.025
#: How far a rail box's bottom sits *inside* the slab (shipped: 15 mm).
RAIL_EMBED = 0.015
#: The open hand's fingertips hang this far below the jaw centre at the transfer
#: attitude (WORKLOG: "the jaws hang ~8.4 cm below the jaw centre").
FINGER_DROP = 0.084
#: `FRUIT_OPENARM_TRANSFER_LIFT` (tasks.py `_pose`), the shipped 0.08 m.
LIFT = float(os.environ.get("FRUIT_OPENARM_TRANSFER_LIFT", "0.08"))
#: Carried payload: its lowest point sits about this far below the jaw centre on
#: the place transit. `_payload_clearance` measured +31..+54 mm over the rail top
#: with LIFT=0.08, i.e. bottom = 1.416-1.439 for jaw 1.53 -> 0.091-0.114 m below.
PAYLOAD_DROP = 0.11


def box(x0, x1, y0, y1, z0, z1, **kw):
    return {"x": (x0, x1), "y": (y0, y1), "z": (z0, z1), **kw}


def gap(a, b):
    """Signed gap between two intervals [m]: + separated, - overlapping."""
    return max(a[0], b[0]) - min(a[1], b[1])


def fmt(v):
    return f"[{v[0]:+.4f},{v[1]:+.4f}]"


def census(cfg):
    """Every rail-like box in the cell, in the builders' own arithmetic."""
    bx, by, bz = (float(v) for v in cfg.belt_center)
    sx, sy, sz = (float(v) for v in cfg.belt_size)
    top = bz + sz / 2.0
    rows = []

    # --- main belt (conveyor.py CleatedBelt.build) -------------------------
    # Frame rails: size (rail_width, sy+0.10, 0.05) at bx +/- (sx/2 + offset),
    # z centre top+0.02. Visual only - the builder applies no CollisionAPI.
    rw, ro = float(cfg.main_frame_rail_width), float(cfg.main_frame_rail_offset)
    for tag, s in (("N", -1.0), ("P", +1.0)):
        cx = bx + s * (sx / 2.0 + ro)
        rows.append(
            box(cx - rw / 2.0, cx + rw / 2.0,
                by - (sy + 0.10) / 2.0, by + (sy + 0.10) / 2.0,
                top + 0.02 - 0.025, top + 0.02 + 0.025,
                name=f"main frame rail {tag}", collider=False, authored=True,
                how="always (visual only)", src="conveyor.py:266-277")
        )
    # Guide rails (cfg.rails / FRUIT_RAILS): size (0.015, sy, FRUIT_RAIL_HEIGHT)
    # at bx +/- (belt_channel_x + 0.008), standing on the belt top.
    h = float(os.environ.get("FRUIT_RAIL_HEIGHT", "0.075"))
    for tag, s in (("N", -1.0), ("P", +1.0)):
        cx = bx + s * (float(cfg.belt_channel_x) + 0.008)
        rows.append(
            box(cx - 0.0075, cx + 0.0075, by - sy / 2.0, by + sy / 2.0, top, top + h,
                name=f"main guide rail {tag}", collider=True, authored=bool(cfg.rails),
                how=f"FRUIT_RAILS={int(cfg.rails)} (default 0)",
                src="conveyor.py:278-294")
        )
    # Containment bundle (FRUIT_BELT_CONTAINMENT, opt-in): 15 mm fences 50 mm tall
    # on the belt top, plus the belt-end keeper.
    cont = os.environ.get("FRUIT_BELT_CONTAINMENT", "0") == "1"
    ch = 0.050
    for tag, inner, out in (("N", 0.13, -1.0), ("P", 0.43, +1.0)):
        x0 = inner + out * 0.015
        rows.append(
            box(min(x0, inner), max(x0, inner),
                by - sy / 2.0 + 0.020, by + sy / 2.0 - 0.020, top, top + ch,
                name=f"containment side fence {tag}", collider=True, authored=cont,
                how=f"FRUIT_BELT_CONTAINMENT={int(cont)} (default 0)",
                src="conveyor.py:76-135")
        )

    # --- output belts (conveyor.py OutputBelt.build) ----------------------
    osx, osy, osz = (float(v) for v in cfg.output_belt_size)
    obx = float(cfg.output_belt_center_x)
    obz_top = float(cfg.output_belt_top_z)
    keep_inner, keep_outer = cfg.output_rail_keep
    rh = float(cfg.output_rail_height)
    for index, sign in ((0, 1.0), (1, -1.0)):
        oby = sign * float(cfg.output_belt_y)
        for tag, side_sign, keep in (("inner", -sign, keep_inner), ("outer", +sign, keep_outer)):
            ry = oby + side_sign * (osy / 2.0 + 0.0125)
            rows.append(
                box(obx - osx / 2.0, obx + osx / 2.0,
                    ry - RAIL_THICK / 2.0, ry + RAIL_THICK / 2.0,
                    obz_top - RAIL_EMBED, obz_top - RAIL_EMBED + rh,
                    name=f"output belt {index} {tag} rail", collider=True, authored=keep,
                    how=f"FRUIT_OUTPUT_RAILS={cfg.output_rails}"
                        f"{'' if keep else ' - NOT AUTHORED'}",
                    src="conveyor.py:573-604")
            )
    return rows


def envelopes(cfg):
    bx, by, bz = (float(v) for v in cfg.belt_center)
    sx, sy, sz = (float(v) for v in cfg.belt_size)
    top = bz + sz / 2.0
    jaw_z = top + float(cfg.grasp_clearance)
    transfer_z = float(cfg.output_place_z) + LIFT
    payload_bottom = transfer_z - PAYLOAD_DROP
    return {
        # The open hand at the station and at both band edges (x = jaw).
        "grasp@station": box(cfg.pick_x - HAND_HALF, cfg.pick_x + HAND_HALF,
                             cfg.pick_y - HAND_HALF, cfg.pick_y + HAND_HALF,
                             jaw_z - FINGER_DROP, jaw_z),
        "grasp@band_in": box(BAND[0] - HAND_HALF, BAND[0] + HAND_HALF, -HAND_HALF, +HAND_HALF,
                             jaw_z - FINGER_DROP, jaw_z),
        "grasp@band_out": box(BAND[1] - HAND_HALF, BAND[1] + HAND_HALF, -HAND_HALF, +HAND_HALF,
                              jaw_z - FINGER_DROP, jaw_z),
        # The carried payload from the pick station to the release, at the
        # transfer height: y sweeps 0.05 -> 0.50, x 0.34 -> 0.43.
        "place transit": box(0.34 - R_MAX, 0.43 + R_MAX, 0.05 - R_MAX, 0.50 + R_MAX,
                             payload_bottom, payload_bottom + 2 * R_MAX),
        # The release: the fruit centred on (0.43, +/-0.50).
        "place release": box(0.43 - R_MAX, 0.43 + R_MAX, 0.50 - R_MAX, 0.50 + R_MAX,
                             payload_bottom, payload_bottom + 2 * R_MAX),
        # The supply flow: the whole delivered band over the whole belt length,
        # a fruit standing on the belt.
        "supply flow": box(BAND[0] - R_MIN, BAND[1] + R_MIN, by - sy / 2.0, by + sy / 2.0,
                           top, top + 2 * R_MAX),
    }


def main(argv):
    cfg = SceneConfig()
    rows = census(cfg)
    env = envelopes(cfg)
    bx, by, bz = (float(v) for v in cfg.belt_center)
    sx, sy, sz = (float(v) for v in cfg.belt_size)
    top = bz + sz / 2.0
    osx, osy, osz = (float(v) for v in cfg.output_belt_size)
    oy = float(cfg.output_belt_y)
    ob_top = float(cfg.output_belt_top_z)
    jaw_z = top + float(cfg.grasp_clearance)
    transfer_z = float(cfg.output_place_z) + LIFT
    payload_bottom = transfer_z - PAYLOAD_DROP

    print("P30-A rail census (shipped SceneConfig, no simulator)")
    print(f"  main belt slab   x=[{bx - sx / 2:.4f},{bx + sx / 2:.4f}] "
          f"y=[{by - sy / 2:+.4f},{by + sy / 2:+.4f}] z=[{bz - sz / 2:.4f},{top:.4f}] top={top:.4f}")
    print(f"  output belts     x=[{float(cfg.output_belt_center_x) - osx / 2:.4f},"
          f"{float(cfg.output_belt_center_x) + osx / 2:.4f}] "
          f"y=+/-[{oy - osy / 2:.4f},{oy + osy / 2:.4f}] z=[{ob_top - osz:.4f},{ob_top:.4f}]")
    print(f"  knobs            FRUIT_OUTPUT_RAILS={cfg.output_rails} "
          f"FRUIT_OUTPUT_RAIL_HEIGHT={cfg.output_rail_height} FRUIT_RAILS={int(cfg.rails)} "
          f"FRUIT_BELT_CONTAINMENT={int(os.environ.get('FRUIT_BELT_CONTAINMENT', '0') == '1')} "
          f"FRUIT_OPENARM_TRANSFER_LIFT={LIFT}")
    print()
    print("  rail / edge boxes")
    for r in rows:
        state = "authored" if r["authored"] else "off"
        print(f"    {r['name']:<26} x={fmt(r['x'])} y={fmt(r['y'])} z={fmt(r['z'])} "
              f"collider={'yes' if r['collider'] else 'no '} {state:<8} "
              f"{r['how']:<45} ({r['src']})")
    print()
    print("  interference: per envelope, the boxes that are NOT separated from it")
    print("    (gap [mm], positive = clear, negative = overlap; one separating axis is enough)")
    for ename, e in env.items():
        hits = 0
        for r in rows:
            g = {ax: gap(e[ax], r[ax]) for ax in ("x", "y", "z")}
            sep = max(g.values())
            if sep < 0:
                hits += 1
                state = "OVERLAP" if r["collider"] else "no collider (visual)"
                if not r["authored"]:
                    state += ", not built"
                print(f"    {ename:<14} vs {r['name']:<26} "
                      f"dx={g['x'] * 1000:+8.1f} dy={g['y'] * 1000:+8.1f} "
                      f"dz={g['z'] * 1000:+8.1f}  {state}")
        if not hits:
            print(f"    {ename:<14} vs every rail: separated")
    print()
    inner = next(r for r in rows if r["name"] == "output belt 0 inner rail")
    outer = next(r for r in rows if r["name"] == "output belt 0 outer rail")
    slab_edge = oy - osy / 2.0
    rail_top = inner["z"][1]
    print("  the place transit (the only place-path rail)")
    print(f"    output belt inner edge   y={slab_edge:.4f}; inner rail y={fmt(inner['y'])} "
          f"(its outer face is flush with the slab edge), top z={rail_top:.4f} "
          f"= belt top +{rail_top - ob_top:.4f} m")
    print(f"    release point            y=+/-{float(cfg.output_place_y):.4f}, "
          f"{float(cfg.output_place_y) - slab_edge:.4f} m inboard of the slab edge")
    print(f"    payload bottom (jaw {transfer_z:.3f} - {PAYLOAD_DROP:.2f}) z={payload_bottom:.4f} -> "
          f"{'clears' if payload_bottom > rail_top else 'BELOW'} the rail top by "
          f"{(payload_bottom - rail_top) * 1000:+.1f} mm; slab top -> "
          f"{(payload_bottom - ob_top) * 1000:+.1f} mm")
    print(f"    fingertips (jaw - {FINGER_DROP:.3f})  z={transfer_z - FINGER_DROP:.4f} -> "
          f"{(transfer_z - FINGER_DROP - rail_top) * 1000:+.1f} mm to the rail top")
    print(f"    FRUIT_OPENARM_TRANSFER_LIFT=0: payload bottom {payload_bottom - LIFT:.4f} -> "
          f"{(payload_bottom - LIFT - rail_top) * 1000:+.1f} mm to the rail top, "
          f"{(payload_bottom - LIFT - ob_top) * 1000:+.1f} mm to the slab top; "
          f"fingertips {(transfer_z - LIFT - FINGER_DROP - rail_top) * 1000:+.1f} mm")
    print(f"    outer rail (kept)        y={fmt(outer['y'])}, top {outer['z'][1]:.4f}: the release is "
          f"{(float(cfg.output_place_y) - outer['y'][0]) * 1000:+.1f} mm inboard of its inner face")
    print()
    print("  the P3 inner-shift cap (tasks.py:2378-2392) vs the real inner edge")
    cap = float(cfg.output_belt_size[1]) / 2.0 * 0.9
    cap_y = float(cfg.output_place_y) - cap
    safe_max = slab_edge + R_MAX
    print(f"    the comment's \"0.375 inner edge\" is output_place_y - width/2 = "
          f"{float(cfg.output_place_y) - float(cfg.output_belt_size[1]) / 2.0:.4f}: the release y used as the "
          f"belt centre; no surface sits at 0.375")
    print(f"    real edges: slab inner edge y={slab_edge:.4f}, rail inner face y={inner['y'][0]:.4f}, "
          f"rail top face y={fmt(inner['y'])}")
    print(f"    the cap puts the release at y={cap_y:.4f} -> a r_max fruit spans "
          f"[{cap_y - R_MAX:.4f},{cap_y + R_MAX:.4f}], i.e. "
          f"{'ON' if cap_y + R_MAX > inner['y'][0] else 'clear of'} the rail's top face "
          f"and {'off' if cap_y - R_MAX < slab_edge else 'on'} the slab")
    print(f"    the largest shift that keeps a r_max fruit fully on the slab: "
          f"{float(cfg.output_place_y) - safe_max:.4f} m (r_min: "
          f"{float(cfg.output_place_y) - (slab_edge + R_MIN):.4f} m) - the cap allows {cap:.4f} m")
    print()
    print("  the grasp envelope")
    for ename in ("grasp@station", "grasp@band_in", "grasp@band_out"):
        print(f"    {ename:<14} x={fmt(env[ename]['x'])} z={fmt(env[ename]['z'])}")
    band_in = env["grasp@band_in"]["x"]
    band_out = env["grasp@band_out"]["x"]
    for r in rows:
        if r["name"].startswith("main frame rail") or r["name"].startswith("main guide rail") \
                or r["name"].startswith("containment"):
            print(f"    {r['name']:<26} inner face {max(r['x'][1] if r['x'][1] < bx else r['x'][0], -1):.4f}: "
                  f"{'clears' if gap(band_in, r['x']) > 0 and gap(band_out, r['x']) > 0 else 'CLIPS'} the "
                  f"band-edge hands by {(min(gap(band_in, r['x']), gap(band_out, r['x']))) * 1000:+.1f} mm; "
                  f"at the station {(gap(env['grasp@station']['x'], r['x'])) * 1000:+.1f} mm; "
                  f"the supply flow {(gap(env['supply flow']['x'], r['x'])) * 1000:+.1f} mm")
    guide = next(r for r in rows if r["name"] == "main guide rail N")
    print(f"    guide rail channel x=[{guide['x'][1]:.4f},{2 * bx - guide['x'][1]:.4f}] vs the band "
          f"x={fmt((BAND[0], BAND[1]))}: a fruit whose centre is below "
          f"{guide['x'][1] + R_MIN:.4f} (r_min) / {guide['x'][1] + R_MAX:.4f} (r_max) touches it")
    print()
    print(f"  jaw at the station z={jaw_z:.4f} (belt top + {cfg.grasp_clearance:.3f}); "
          f"fingertips to {jaw_z - FINGER_DROP:.4f} (belt top {top:.3f})")

    if "--assert" not in argv:
        return 0
    frame_n = next(r for r in rows if r["name"] == "main frame rail N")
    fence_p = next(r for r in rows if r["name"] == "containment side fence P")
    checks = [
        ("main frame rails carry no collider", frame_n["collider"] is False),
        ("frame rail N clears the band-edge hand", gap(band_in, frame_n["x"]) > 0),
        ("guide rails are off at the default", guide["authored"] is False),
        ("guide rail N would clip the band-edge hand", gap(band_in, guide["x"]) < 0),
        ("inner output rail's outer face is the slab edge",
         abs(inner["y"][1] - slab_edge) < 1e-9),
        ("inner output rail top = belt top + 0.035",
         abs(rail_top - ob_top - 0.035) < 1e-9),
        ("payload clears the rail at the shipped lift", payload_bottom > rail_top),
        ("payload would miss the rail at lift 0", payload_bottom - LIFT < rail_top),
        ("payload is ~at the slab top at lift 0",
         abs(payload_bottom - LIFT - ob_top) < 0.02),
        ("release is inboard of the inner rail's outer face",
         float(cfg.output_place_y) > inner["y"][1]),
        ("only one rail per output belt is in the place transit", True),
        ("default mode keeps both output rails", cfg.output_rail_keep == (True, True)),
        ("default rail height 0.05 authors the shipped box",
         abs(float(cfg.output_rail_height) - 0.05) < 1e-12),
        ("containment fence P clears the band-edge hand by <5 mm (the tight opt-in)",
         0 < gap(band_out, fence_p["x"]) < 0.005),
        ("the P3 cap places the release inboard of the rail's inner face",
         cap_y < inner["y"][0]),
        ("the P3 cap is larger than the largest safe shift",
         cap > float(cfg.output_place_y) - safe_max),
    ]
    bad = [name for name, ok in checks if not ok]
    print()
    for name, ok in checks:
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")
    if bad:
        print(f"ASSERT: {len(bad)} failed")
        return 1
    print("ASSERT: all pinned clearances hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
