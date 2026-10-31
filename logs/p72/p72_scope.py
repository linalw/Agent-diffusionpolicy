#!/usr/bin/env python3
"""P72 §3: the new-frame boundary's arithmetic, derived rather than asserted.

    python3 logs/p72/p72_scope.py

Prints, on the shipped config:

(1) the three |y| thresholds the `[carry]` row's clearance fields use, so the
    reader can see that `clr_edge`'s is the only one at a surface boundary;
(2) the surface algebra - with `FRUIT_OUTPUT_RAILS=none` there is no rail branch
    to enter, so the binding surface at the crossing is the slab's top plane and
    its inboard edge (contact <=> `clr_edge <= 0`);
(3) the crossing-height identity `z_cross = f*z_transfer + (1-f)*z_lift_end` and
    its two slopes (`d/dz_lift = 1-f`, `d/d belt top = f-1`), at the rail
    centreline and at the P72 edge sample;
(4) the bracket from the record: P70 D1 ep8's `clr = -1 mm @obelt` (plane, no
    contact signature) against G0's measured contact population.

Offline: imports only `fruit_sorting.assets` (no simulator). Exit 0.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fruit_sorting.assets import OUTPUT_RAIL_INSET, SceneConfig  # noqa: E402


def main() -> int:
    cfg = SceneConfig()
    belt_main = float(cfg.belt_center[2]) + float(cfg.belt_size[2]) / 2.0
    rail_centre = abs(float(cfg.output_belt_y)) - (
        float(cfg.output_belt_size[1]) / 2.0 + 0.0125
    )
    rail_inner = rail_centre - 0.0125
    edge = abs(float(cfg.output_belt_y)) - float(cfg.output_belt_size[1]) / 2.0
    place_y = abs(float(cfg.output_belt_drop_points[0][1]))
    transfer = float(cfg.output_place_z) + 0.08  # + the hand's add
    lift_end = belt_main + 0.28 - 0.08  # the direct default (P71: -0.08)

    print("=" * 78)
    print("P72 - the new-frame boundary (rails none, direct lift belt_top + 0.20)")
    print("=" * 78)
    print("1. the [carry] clearance thresholds (|y|, m)")
    print(f"   main belt .. {rail_inner:.4f}  the surface switch (the removed rail's INNER face)")
    print(f"   {rail_inner:.4f} .. {rail_centre:.4f}  the rail's former 25 mm footprint (a void now)")
    print(f"   {rail_centre:.4f} .. {edge:.4f}  still inboard of the slab: `clr_win` charges it, conservatively")
    print(f"   >= {edge:.4f}                 the slab's own inboard edge -> `clr_edge` samples here")
    print(f"   (rail inset {OUTPUT_RAIL_INSET:.3f} m; rail box height {cfg.output_rail_height:.3f} m, "
          f"proud {cfg.output_rail_proud:.3f} m)")

    print("\n2. the surfaces that exist with FRUIT_OUTPUT_RAILS=none")
    keep = cfg.output_rail_keep
    print(f"   output_rail_keep = {keep} -> `_payload_clearance`'s rail branch "
          f"(`y <= 0.46 and keep[0]`) is never entered")
    print(f"   main belt top      {belt_main:.3f} m (|y| < 0.400 - inboard of the crossing)")
    print(f"   output belt top    {cfg.output_belt_top_z:.3f} m (the slab, |y| >= {edge:.3f})")
    print("   => contact requires the payload's lowest point BELOW the top plane while")
    print("      horizontally OVER the slab, i.e. `clr_edge <= 0`. No raised surface exists,")
    print("      so no +N mm rail convention transfers to this frame.")

    print("\n3. the crossing height and its two slopes")
    print(f"   z_transfer = output_place_z + hand = {cfg.output_place_z:.3f} + 0.08 = {transfer:.3f} m "
          "(moves 1:1 with the belt top)")
    print(f"   z_lift_end = main belt top + 0.28 - 0.08 = {lift_end:.3f} m "
          "(anchored to the MAIN belt: invariant in the output belt top)")
    for tag, y in (("rail centreline (clr)", rail_centre), ("the P72 edge (clr_edge)", edge)):
        f = y / place_y
        z_cross = f * transfer + (1.0 - f) * lift_end
        clr = z_cross - float(cfg.output_belt_top_z)
        print(f"   {tag:26s} |y|={y:.4f} f={f:.3f} -> z_cross={z_cross:.3f} "
              f"clr={clr * 1000:+.1f} mm | d clr/d(lift)={1 - f:+.3f} "
              f"d clr/d(belt top)={f - 1:+.3f}")
    print("   why: the transfer follows the belt 1:1 while the lift end is anchored to the")
    print("        main belt, so only (1-f) of a lift change reaches the crossing and only")
    print("        f of a belt change does, against an obstacle that moves 1:1 -> |0.175|")
    print("        (0.15 at the edge). Neither lever reaches a zero crossing without the")
    print("        placements (P66 P4, P70 cell B).")
    print("   the ABSOLUTE above is a straight-line envelope, not a prediction: the")
    print("        achieved transfer descends early, so P71's measured `clr` at the rail")
    print("        centreline is +14..+50 mm - 100-140 mm below the envelope. The slopes")
    print("        are the derivable content; the value is measured (`clr_edge`).")

    print("\n4. the bracket in the record")
    print("   P70 D1 ep8 (left, held): clr = -1 mm @obelt / t247, a PLANE sample taken at")
    print("        |y| = 0.4125 (25 mm inboard of the surface): |a|max 0.98 m/s2,")
    print("        sep_end 69.9 mm, slip 0.4 mm -> NO contact signature")
    print("   G0 contact population (rail frame): 14.9-32.7 m/s2, 27-76 mm displacement")
    print("   G0 clean population  (rail frame):  2.6-5.7 m/s2, 0.0-0.1 mm slip")
    print("   => the floor is `clr_edge > 0`, and the record's evidence is a BRACKET,")
    print("      not a contact-calibrated boundary at the corner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
