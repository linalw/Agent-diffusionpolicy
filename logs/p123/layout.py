"""P123 - the third output destination: candidate layouts, priced offline.

    python3 logs/p123/layout.py            # -> logs/p123/layout.txt

Pure arithmetic on `assets.SceneConfig` and on `logs/p122/SPEC.md`'s measured
release offset. No simulator, no stage. It prices the three candidates the phase
brief names, in its order:

* **A** - a third parallel belt **inboard on -Y**, |y| 0.290..0.405, **x-offset
  downstream** (x 0.48..1.20) so no place transit passes over it; the -Y tray
  narrows to make room for its own tray.
* **B** - **split** the -Y belt into two narrow belts (full x 0.10..1.20) with
  two trays: places at (0.48, -0.35) and (0.38, -0.55).
* **C** - a third belt **outboard**, |y| ~ 0.70.

The four columns per candidate are the ones the registration asks for:

1. **the place point** - inside `logs/p90/station_map.txt`'s `NAT` <= 6 mm set
   (the 50 mm grid; the exact cell is measured by `logs/p123/probe.py`).
2. **the release** - the *delivered* point (commanded + the measured
   `+48 mm x / +-35..37 mm y` offset) against the candidate slab, in sd, and
   against its upstream edge (the `x` term is what decides whether a payload
   falls 180 mm onto the main belt).
3. **the crossing** - the place transit's height at every *other* lane's inboard
   edge, as a **delta against the shipped crossing** (`d clr = d z`, P90
   `cost_map.py`'s expression; the shipped cell is the zero). A body that is
   *downstream in x* of every transit is not crossed at all.
4. **the bodies and the camera** - belt/chute/tray AABBs against each other, the
   pedestal, the main belt and the pick stations; and whether the new body lies
   over the fruit's arrival footprint *outside* the shipped slabs' own footprint
   (an occlusion the shipped line does not already have: the P35/P36 finding).
"""

from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fruit_sorting.assets import SceneConfig  # noqa: E402

# --------------------------------------------------------------------------- #
# The measured terms
# --------------------------------------------------------------------------- #
#: release - commanded: (mean dx, sd dx, mean |dy|, sd |dy|), metres, per side.
OFFSET = {
    "+y": (0.048, 0.008, 0.035, 0.006),
    "-y": (0.048, 0.006, 0.036, 0.008),
}
SD_K = 3.0
#: `jaw_target("grasp_lift")` |y| and the two lift-end heights P90 priced.
LIFT_END_Y = 0.05
LIFT_Z = {"scripted": 1.530, "direct-low": 1.370}
#: The transfer the place leg ends at (`output_place_z` + the OpenArm add).
TRANSFER_ADD = 0.08
#: The P90 gate this phase re-uses (`logs/p90/METHOD.md` section 3) minus its
#: `T0` tilt clause: the phase asks for a *shipping* station, i.e. the shipped
#: cell's own position-only solve, not a top-down fix (P90 closed that lane).
RES_MAX_MM = 6.0
MARGIN_MIN_RAD = 0.05
PAD_MIN_MM = 2.0
#: The place leg's measured achieved tilt (P73 `tilt_end` 78.7-105 deg; the
#: shipped cell reads 77.75 deg in P90's `NAT`): a candidate must stay in this
#: attitude class or the arm is not doing the shipped motion.
TILT_BAND = (60.0, 110.0)
#: P90's `NAT` residual <= 6 mm cells (`station_map.txt`, z = 1.450), |y|, x.
NAT_SOLVES = [
    (0.48, 0.35), (0.43, 0.40), (0.48, 0.40), (0.43, 0.45),
    (0.38, 0.50), (0.43, 0.50), (0.38, 0.55),
]
#: The main belt's delivered lateral band (`FRUIT_SUPPLY_X_MIN/MAX` 0.20..0.36
#: plus the P38 per-instance release offset) and a fruit radius.
FRUIT_X = (0.148, 0.413)
FRUIT_Y = (-0.20, 0.68)
FRUIT_R = 0.035
SLAB_THICKNESS = 0.05
#: The shipped crossing's *measured* clearance at the slab's inboard edge:
#: scripted left +14..+50 mm (median +35, P71 section 3), direct low lift
#: +29..+36 mm (`logs/p71/direct/treat_77.log`, the `[carry] clr` rows).
MEASURED_CLR = {"scripted": 35.0, "direct-low": 32.0}


class Lane:
    """One output body: a belt rectangle, a place point, a tray and a chute."""

    def __init__(self, lid, side, belt, place, tray, chute_y=None):
        self.id = int(lid)
        self.side = side
        self.sign = 1.0 if side == "+y" else -1.0
        self.belt = belt                              # (x0, x1, y0, y1)
        self.place = place                            # (x, y) commanded
        self.tray = tray                              # (x0, x1, y0, y1)
        self.chute_y = chute_y                        # (y0, y1) incl. lips

    @property
    def y_inner(self):
        return min(abs(self.belt[2]), abs(self.belt[3]))

    @property
    def y_outer(self):
        return max(abs(self.belt[2]), abs(self.belt[3]))

    def slab(self):
        """The belt band normalised to |y| (what a release must land between)."""
        return (self.belt[0], self.belt[1], self.y_inner, self.y_outer)

    def delivered(self):
        dx, _sdx, dy, _sdy = OFFSET[self.side]
        return (self.place[0] + dx, self.sign * (abs(self.place[1]) + dy))


def rect_overlap(a, b):
    return not (a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2])


def rect_gap(a, b):
    """Air between two rectangles (negative = overlap)."""
    return max(b[0] - a[1], a[0] - b[1], b[2] - a[3], a[2] - b[3])


def crossing(z_lift, z_transfer, y_edge, y_place):
    """P90's crossing: z at `y_edge` on the straight line lift-end -> place."""
    if abs(y_place) <= y_edge:
        return None
    t = (y_edge - LIFT_END_Y) / (abs(y_place) - LIFT_END_Y)
    return z_lift + t * (z_transfer - z_lift)


def projection(points, eye=(0.05, 0.0, 2.00), target=(0.34, 0.22, 1.10),
               focal=0.016, aperture=(0.036, 0.02025), res=(480, 848)):
    """Pinhole projection into the head camera's pixels (`scene._add_head_camera`)."""
    def norm(v):
        n = math.sqrt(sum(c * c for c in v)) or 1.0
        return tuple(c / n for c in v)

    fwd = norm((target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]))
    right = norm((fwd[1], -fwd[0], 0.0))
    up = (right[1] * fwd[2] - right[2] * fwd[1],
          right[2] * fwd[0] - right[0] * fwd[2],
          right[0] * fwd[1] - right[1] * fwd[0])
    out = []
    for p in points:
        d = (p[0] - eye[0], p[1] - eye[1], p[2] - eye[2])
        z = sum(d[i] * fwd[i] for i in range(3))
        x = sum(d[i] * right[i] for i in range(3))
        y = sum(d[i] * up[i] for i in range(3))
        u = res[1] / 2.0 + (x / z) * (focal / (aperture[0] / 2.0)) * (res[1] / 2.0)
        v = res[0] / 2.0 - (y / z) * (focal / (aperture[1] / 2.0)) * (res[0] / 2.0)
        out.append((u, v, z))
    return out


def main() -> int:
    cfg = SceneConfig()
    belt_top = float(cfg.belt_center[2]) + float(cfg.belt_size[2]) / 2.0
    out_top = float(cfg.output_belt_top_z)
    under = out_top - SLAB_THICKNESS
    z_place = float(cfg.output_place_z)
    z_transfer = z_place + TRANSFER_ADD
    y_edge = abs(float(cfg.output_belt_y)) - float(cfg.output_belt_size[1]) / 2.0
    x_lo, x_hi = cfg.output_belt_x_range
    tray_x0 = float(cfg.output_tray_center_x) - float(cfg.output_tray_size[0]) / 2.0
    tray_x1 = float(cfg.output_tray_center_x) + float(cfg.output_tray_size[0]) / 2.0
    pedestal = (float(cfg.pedestal_center_xy[0]) - float(cfg.pedestal_size[0]) / 2.0,
                float(cfg.pedestal_center_xy[0]) + float(cfg.pedestal_size[0]) / 2.0,
                float(cfg.pedestal_center_xy[1]) - float(cfg.pedestal_size[1]) / 2.0,
                float(cfg.pedestal_center_xy[1]) + float(cfg.pedestal_size[1]) / 2.0)
    main_belt = (float(cfg.belt_center[0]) - float(cfg.belt_size[0]) / 2.0,
                 float(cfg.belt_center[0]) + float(cfg.belt_size[0]) / 2.0,
                 float(cfg.belt_center[1]) - float(cfg.belt_size[1]) / 2.0,
                 float(cfg.belt_center[1]) + float(cfg.belt_size[1]) / 2.0)
    stations = (("left", 0.00), ("right", -0.10))
    #: the shipped chute envelope (`_build_discharge`: width = belt width - 0.01,
    #: plus a 12 mm lip each side).
    chute_half = (float(cfg.output_belt_size[1]) - 0.01) / 2.0 + 0.012

    print("== P123 layout: the shipped cell's numbers the candidates are built on ==")
    print(f"   main belt   x {main_belt[0]:.3f}..{main_belt[1]:.3f} "
          f"y {main_belt[2]:+.3f}..{main_belt[3]:+.3f}  top {belt_top:.3f}")
    print(f"   pedestal    x {pedestal[0]:.3f}..{pedestal[1]:.3f} "
          f"y {pedestal[2]:+.3f}..{pedestal[3]:+.3f}  top 0.790")
    print(f"   output slab |y| {y_edge:.3f}..{abs(cfg.output_belt_y) + float(cfg.output_belt_size[1]) / 2.0:.3f}"
          f"  x {x_lo:.2f}..{x_hi:.2f}  top {out_top:.3f} underside {under:.3f}")
    print(f"   place       ({cfg.output_place_x:.3f}, +-{cfg.output_place_y:.3f})  "
          f"z {z_place:.3f}  transfer {z_transfer:.3f}")
    print(f"   chute       x {x_hi:.3f}..{float(cfg.output_belt_end_x) + 0.161:.3f}"
          f"  z {out_top - 0.006:.3f}->{float(cfg.output_chute_end_z):.3f}, y ±"
          f"{chute_half:.3f} around the belt centre")
    print(f"   tray        x {tray_x0:.2f}..{tray_x1:.2f}  |y| "
          f"{abs(float(cfg.output_belt_y)) - float(cfg.output_tray_size[1]) / 2.0:.2f}"
          f"..{abs(float(cfg.output_belt_y)) + float(cfg.output_tray_size[1]) / 2.0:.2f}"
          f"  floor {float(cfg.output_tray_floor_top_z):.2f}")
    print(f"   P90 `NAT` <= 6 mm cells (|y|, x): {NAT_SOLVES}")
    print(f"   release offset: +y {OFFSET['+y']}  -y {OFFSET['-y']}  (mean x, sd x, mean |y|, sd |y|)")
    print(f"   measured shipped crossing clr: {MEASURED_CLR}")
    print()

    new = lambda lid, side, belt, place, tray, ch: Lane(lid, side, belt, place, tray, ch)
    candidates = {
        "A  third belt inboard on -Y, x-offset downstream": [
            Lane(0, "+y", (0.10, 1.20, 0.425, 0.675), (0.43, 0.50),
                 (tray_x0, tray_x1, 0.380, 0.720), (0.418, 0.682)),
            Lane(1, "-y", (0.10, 1.20, -0.675, -0.425), (0.43, -0.50),
                 (tray_x0, tray_x1, -0.720, -0.470), (-0.682, -0.418)),
            new(2, "-y", (0.48, 1.20, -0.405, -0.290), (0.48, -0.31),
                (tray_x0, tray_x1, -0.410, -0.270), (-0.412, -0.283)),
        ],
        "B  split the -Y belt into two (full x)": [
            Lane(0, "+y", (0.10, 1.20, 0.425, 0.675), (0.43, 0.50),
                 (tray_x0, tray_x1, 0.380, 0.720), (0.418, 0.682)),
            Lane(1, "-y", (0.10, 1.20, -0.450, -0.340), (0.48, -0.35),
                 (tray_x0, tray_x1, -0.460, -0.330), (-0.467, -0.323)),
            new(2, "-y", (0.10, 1.20, -0.650, -0.540), (0.38, -0.55),
                (tray_x0, tray_x1, -0.660, -0.530), (-0.667, -0.523)),
        ],
        "C  third belt outboard (|y| ~0.70)": [
            Lane(0, "+y", (0.10, 1.20, 0.425, 0.675), (0.43, 0.50),
                 (tray_x0, tray_x1, 0.380, 0.720), (0.418, 0.682)),
            Lane(1, "-y", (0.10, 1.20, -0.675, -0.425), (0.43, -0.50),
                 (tray_x0, tray_x1, -0.720, -0.380), (-0.682, -0.418)),
            new(2, "-y", (0.10, 1.20, -0.765, -0.635), (0.43, -0.68),
                (tray_x0, tray_x1, -0.780, -0.600), (-0.797, -0.603)),
        ],
    }

    verdicts = {}
    for name, lanes in candidates.items():
        print("=" * 78)
        print(f"== candidate {name}")
        ok = True
        reasons = []

        # ---- 1. the place point ------------------------------------------- #
        print("   1. the place point (P90's `NAT` gate minus its `T0` tilt clause:")
        print(f"      res <= {RES_MAX_MM:.0f} mm, margin >= {MARGIN_MIN_RAD:.2f} rad, "
              f"pad >= {PAD_MIN_MM:.0f} mm, tilt {TILT_BAND[0]:.0f}-{TILT_BAND[1]:.0f} deg)")
        for lane in lanes:
            key = (round(lane.place[0], 2), round(abs(lane.place[1]), 2))
            solved = key in NAT_SOLVES
            nearest = min(NAT_SOLVES, key=lambda c: math.dist(
                (c[0], c[1]), (key[0], key[1])))
            dist = 1000 * math.dist((key[0], key[1]), nearest)
            print(f"      lane {lane.id} ({lane.side}) place ({lane.place[0]:+.2f},"
                  f"{lane.place[1]:+.2f}): "
                  + ("P90 map <= 6 mm" if solved else
                     f"outside the 50 mm grid (nearest {nearest} at {dist:.0f} mm) "
                     f"-> the probe measures it"))
            if lane.id >= 2 and not solved:
                # not a kill by itself: the grid's 50 mm spacing is the map's, not
                # the physics'. The probe decides; this line is the pre-check.
                print("        (pre-check only - the exact cell is solved by logs/p123/probe.py)")

        # ---- 2. the release ---------------------------------------------- #
        print("   2. the release: delivered = place + the measured offset, vs the slab")
        for lane in lanes:
            point = lane.delivered()
            slab = lane.slab()
            dx, sdx, dy, sdy = OFFSET[lane.side]
            margins = (point[0] - slab[0], slab[1] - point[0],
                       abs(point[1]) - slab[2], slab[3] - abs(point[1]))
            need = (SD_K * sdx, SD_K * sdx, SD_K * sdy, SD_K * sdy)
            passed = all(m >= n for m, n in zip(margins, need))
            tight = min(margins[2] / sdy, margins[0] / sdx, margins[1] / sdx)
            print(f"      lane {lane.id}: ({lane.place[0]:+.2f},{lane.place[1]:+.2f}) -> "
                  f"({point[0]:+.3f},{point[1]:+.3f})  margins x[{margins[0] * 1000:+.0f},"
                  f"{margins[1] * 1000:+.0f}] |y|[{margins[2] * 1000:+.0f},"
                  f"{margins[3] * 1000:+.0f}] mm, need {SD_K:.0f} sd "
                  f"[{need[0] * 1000:.0f}/{need[2] * 1000:.0f}] -> "
                  f"{'ON' if passed else 'MISS'} (tightest {tight:.1f} sd)")
            if not passed:
                ok = False
                reasons.append(f"lane {lane.id} release misses its slab")

        # ---- 3. the crossing --------------------------------------------- #
        print("   3. the crossing: each transit against every *other* lane's inboard")
        print("      edge, as a delta from the shipped crossing (d clr = d z)")
        z_base = {k: crossing(v, z_transfer, y_edge, 0.50) for k, v in LIFT_Z.items()}
        for lane in lanes:
            for other in lanes:
                if other.id == lane.id:
                    continue
                edge = other.y_inner
                if abs(lane.place[1]) <= edge:
                    print(f"      lane {lane.id} transit vs lane {other.id} "
                          f"(|y|={edge:.3f}): no crossing - the leg ends inboard")
                    continue
                t_edge = (edge - LIFT_END_Y) / (abs(lane.place[1]) - LIFT_END_Y)
                x_edge = float(cfg.pick_x) + (lane.place[0] - float(cfg.pick_x)) * t_edge
                payload_x = x_edge + lane.sign * OFFSET[lane.side][0]
                over = (other.belt[0] - FRUIT_R <= payload_x <= other.belt[1] + FRUIT_R)
                if not over:
                    print(f"      lane {lane.id} transit vs lane {other.id} "
                          f"(|y|={edge:.3f}, x {other.belt[0]:.2f}..{other.belt[1]:.2f}): "
                          f"NO CROSSING - the payload is at x={payload_x:+.3f} "
                          f"(radius included) there, upstream of the body")
                    continue
                cells = []
                worst = 0.0
                for lab, zl in LIFT_Z.items():
                    zc = crossing(zl, z_transfer, edge, lane.place[1])
                    delta = 1000 * (zc - z_base[lab])
                    worst = min(worst, delta)
                    cells.append(f"{lab} {delta:+.0f} mm -> clr "
                                 f"{MEASURED_CLR[lab] + delta:+.0f} mm")
                print(f"      lane {lane.id} transit vs lane {other.id} "
                      f"(|y|={edge:.3f}) CROSSES at x={payload_x:+.3f}: "
                      + "; ".join(cells))
                if lane.id >= 2 or other.id >= 2:
                    ok = False
                    reasons.append(f"lane {lane.id}'s transit crosses lane {other.id}"
                                   f" ({worst:+.0f} mm of clr)")

        # ---- 4. the bodies ------------------------------------------------ #
        print("   4. the bodies: AABB air between distinct lanes, the pedestal and")
        print("      the main belt (negative = interpenetration)")
        for i, lane in enumerate(lanes):
            for other in lanes[i + 1:]:
                print(f"      lane {lane.id}/{other.id} belts: "
                      f"{1000 * rect_gap(lane.belt, other.belt):+.0f} mm air; trays: "
                      f"{1000 * rect_gap(lane.tray, other.tray):+.0f} mm; chutes: "
                      f"{1000 * rect_gap((x_hi, float(cfg.output_belt_end_x) + 0.161, *lane.chute_y), (x_hi, float(cfg.output_belt_end_x) + 0.161, *other.chute_y)):+.0f} mm")
                for what, a, b in (("belt", lane.belt, other.belt),
                                   ("tray", lane.tray, other.tray)):
                    if rect_overlap(a, b) and (lane.id >= 2 or other.id >= 2):
                        ok = False
                        reasons.append(f"lane {lane.id} {what} overlaps lane {other.id}")
            clash = rect_overlap(lane.belt, pedestal)
            print(f"      lane {lane.id} belt vs pedestal: "
                  f"{'OVERLAP' if clash else 'clear'}; vs main belt: "
                  f"{'over it' if rect_overlap(lane.belt, main_belt) else 'clear'}"
                  f" (underside {under:.3f} over top {belt_top:.3f} = "
                  f"{(under - belt_top) * 1000:+.0f} mm)")
            if clash and lane.id >= 2:
                ok = False
                reasons.append(f"lane {lane.id} belt overlaps the pedestal")

        # ---- 5. the camera ------------------------------------------------ #
        print("   5. the camera: does the new body cover the fruit's arrival footprint")
        print(f"      (x {FRUIT_X[0]:.2f}..{FRUIT_X[1]:.2f}, y {FRUIT_Y[0]:+.2f}..{FRUIT_Y[1]:+.2f})")
        print("      *outside* the shipped slabs' own footprint?")
        shipped = [l for l in lanes if l.id < 2]
        for lane in lanes:
            if lane.id < 2:
                continue
            foot = (max(lane.belt[0], FRUIT_X[0]), min(lane.belt[1], FRUIT_X[1]),
                    max(min(lane.belt[2], lane.belt[3]), FRUIT_Y[0]),
                    min(max(lane.belt[2], lane.belt[3]), FRUIT_Y[1]))
            covered = foot[0] < foot[1] and foot[2] < foot[3]
            new_area = 0.0
            if covered:
                # subtract the shipped slabs' footprints (the shipped occlusion)
                new_area = (foot[1] - foot[0]) * (foot[3] - foot[2])
                for s in shipped:
                    sy0, sy1 = min(s.belt[2], s.belt[3]), max(s.belt[2], s.belt[3])
                    sy0, sy1 = max(sy0, foot[2]), min(sy1, foot[3])
                    sx0, sx1 = max(s.belt[0], foot[0]), min(s.belt[1], foot[1])
                    if sx0 < sx1 and sy0 < sy1:
                        new_area -= (sx1 - sx0) * (sy1 - sy0)
            print(f"      lane {lane.id} belt footprint ∩ the band: "
                  f"{'yes' if covered else 'no (outside it)'}"
                  f"; new occlusion area {new_area * 1e4:.0f} cm^2 "
                  f"({'none' if new_area <= 1e-9 else 'NEW blind band'})")
            if new_area > 1e-9:
                ok = False
                reasons.append(f"lane {lane.id} adds {new_area * 1e4:.0f} cm^2 of "
                               f"new supply occlusion")
            pts = [(lane.belt[0], lane.sign * lane.y_inner, under),
                   (lane.belt[0], lane.sign * lane.y_outer, out_top),
                   (lane.belt[1], lane.sign * lane.y_outer, under),
                   (lane.belt[1], lane.sign * lane.y_inner, out_top)]
            proj = projection(pts)
            print(f"        projects to u {min(p[0] for p in proj):.0f}.."
                  f"{max(p[0] for p in proj):.0f} px, v {min(p[1] for p in proj):.0f}.."
                  f"{max(p[1] for p in proj):.0f} px, depth "
                  f"{min(p[2] for p in proj):.2f}..{max(p[2] for p in proj):.2f} m")
        proj = projection([(0.34, y, belt_top) for _n, y in stations])
        print("      pick stations: " + ", ".join(
            f"{n} (u {u:.0f}, v {v:.0f}, depth {z:.2f} m)"
            for (n, _y), (u, v, z) in zip(stations, proj)))

        print(f"   -> {'PASS' if ok else 'KILL'}: "
              f"{'no gate failed' if ok else '; '.join(reasons)}")
        verdicts[name] = ok
        print()

    print("=" * 78)
    print("== verdict (the exact place solve is measured by logs/p123/probe.py)")
    for name, ok in verdicts.items():
        print(f"   {'PASS' if ok else 'KILL'}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
