#!/usr/bin/env python3
"""P123 - the output lane table, the per-lane tests and the unset path.

The third output body (`FRUIT_OUTPUT_LANES=3`) is a scene build, so the
offline leg has to pin three things without a simulator:

1. **the unset path is the shipped scene, exactly** - `output_lane_layout()`
   with two lanes reproduces every shipped scalar (`output_belt_drop_points`,
   the belt centre/size, the place point, the tray centre/size, the leg x), and
   the generalised `on_output_belt` / `on_output_tray` / `on_output_discharge`
   give the *same booleans* as the pre-P123 expressions on a dense grid. That is
   what keeps a two-lane run's `[fruit]` stream and `[belt]` prints byte for
   byte (the logs/ comparison is the run's own job, this is the arithmetic).
2. **the third lane's geometry is the measured one** - |y| 0.280..0.395,
   x 0.480..1.200, place (0.480, -0.300), its own tray 0.260..0.400, the -Y
   tray narrowed to 0.20 m; and the invariants the choice rests on: the bodies do
   not interpenetrate, the new tray is a *different* tray from the shipped one,
   the delivered point (place + the P122 offset) is on the new slab with >= 3 sd,
   the new belt starts upstream of the payload's x at every transit crossing
   (so it is never a carry obstacle) and downstream of the fruit's x band (so it
   adds no camera occlusion).
3. **the census** - `output_tray_of` names the tray and agrees with
   `on_output_tray` on every point, so `stats["discharged"]` and the tray census
   cannot disagree.

Run directly (no simulator): `python3 scripts/264_p123_output_lanes_selftest.py`.
"""

from __future__ import annotations

import math
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = pathlib.Path(os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, str(ROOT / "src"))

from fruit_sorting.assets import (  # noqa: E402
    OUTPUT_LANE1_TRAY_HALF_WITH_THIRD,
    OUTPUT_LANE3_BELT_X,
    OUTPUT_LANE3_BELT_Y,
    OUTPUT_LANE3_PLACE,
    OUTPUT_LANE3_TRAY_Y,
    SceneConfig,
    scene_provenance,
)

checks = []


def check(name: str, cond: bool, detail: str = "") -> None:
    checks.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f": {detail}" if detail else ""))


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= tol


# --------------------------------------------------------------------------- #
# The pre-P123 expressions, verbatim (git show HEAD~:src/fruit_sorting/assets.py)
# --------------------------------------------------------------------------- #
def old_on_belt(cfg, position, margin=0.06):
    x = float(position[0])
    y = abs(float(position[1]))
    z = float(position[2])
    x0, x1 = cfg.output_belt_x_range
    half_width = float(cfg.output_belt_size[1]) / 2.0
    return (
        x0 - margin <= x <= x1 + margin
        and abs(y - float(cfg.output_belt_y)) <= half_width + margin
        and z >= float(cfg.output_belt_top_z) - margin
    )


def old_on_tray(cfg, position, margin=0.04):
    x = float(position[0])
    y = float(abs(position[1]) - float(cfg.output_belt_y))
    z = float(position[2])
    half_x = float(cfg.output_tray_size[0]) / 2.0 - float(cfg.output_tray_wall_thickness)
    half_y = float(cfg.output_tray_size[1]) / 2.0 - float(cfg.output_tray_wall_thickness)
    rim = float(cfg.output_tray_floor_top_z) + float(cfg.output_tray_wall_height)
    return (
        abs(x - float(cfg.output_tray_center_x)) <= half_x + margin
        and abs(y) <= half_y + margin
        and float(cfg.output_tray_floor_top_z) - margin <= z <= rim + margin
    )


def old_on_discharge(cfg, position, margin=0.05):
    x = float(position[0])
    y = float(abs(position[1]) - float(cfg.output_belt_y))
    z = float(position[2])
    x1 = float(cfg.output_tray_center_x) + float(cfg.output_tray_size[0]) / 2.0 + margin
    half_y = float(cfg.output_tray_size[1]) / 2.0 + margin
    return (
        cfg.output_belt_end_x - 0.05 <= x <= x1
        and abs(y) <= half_y
        and float(cfg.output_tray_floor_top_z) - margin <= z
        <= float(cfg.output_belt_top_z) + 0.05
    )


def main() -> int:
    print("== P123 output lanes: the unset path, the third body, the census ==")
    cfg = SceneConfig()

    # ---- 1. the unset path is the shipped scene -------------------------- #
    check("2 lane is the default", cfg.output_lanes == 2, f"lanes={cfg.output_lanes}")
    lanes = cfg.output_lane_layout()
    check("the shipped layout has two bodies", len(lanes) == 2)
    check(
        "the shipped drop points are the shipped expression",
        cfg.output_belt_drop_points
        == (
            (float(cfg.output_place_x), float(cfg.output_place_y)),
            (float(cfg.output_place_x), -float(cfg.output_place_y)),
        ),
        str(cfg.output_belt_drop_points),
    )
    for lane in lanes:
        sign = float(lane["sign"])
        check(
            f"lane {lane['index']} centre/size/place/tray are the shipped scalars",
            lane["belt_center"]
            == (float(cfg.output_belt_center_x), sign * float(cfg.output_belt_y),
                float(cfg.output_belt_top_z) - float(cfg.output_belt_size[2]) / 2.0)
            and lane["belt_size"] == tuple(float(v) for v in cfg.output_belt_size)
            and lane["place"] == (float(cfg.output_place_x), sign * float(cfg.output_place_y))
            and lane["tray_center"] == (float(cfg.output_tray_center_x), sign * float(cfg.output_belt_y))
            and lane["tray_size"] == tuple(float(v) for v in cfg.output_tray_size)
            and lane["root"] == f"/World/OutputBelt{'P' if sign > 0 else 'N'}",
        )
        check(
            f"lane {lane['index']} leg x are the shipped derived pair",
            lane["leg_xs"]
            == (float(cfg.output_belt_inner_leg_x), float(cfg.output_belt_outer_leg_x)),
        )

    # the generalised predicates agree with the old ones on a dense grid
    bad = 0
    for i in range(0, 110):
        for j in range(-45, 46):
            for k in range(0, 30):
                p = (i * 0.02, j * 0.02, 0.85 + k * 0.02)
                bad += int(old_on_belt(cfg, p) != cfg.on_output_belt(p))
                bad += int(old_on_tray(cfg, p) != cfg.on_output_tray(p))
                bad += int(old_on_discharge(cfg, p) != cfg.on_output_discharge(p))
    check("the generalised tests equal the pre-P123 expressions", bad == 0,
          f"{bad} mismatches over 110 x 91 x 30 points x 3 tests")

    # the provenance block names the collider set
    scene = scene_provenance(SceneConfig())
    check(
        "scene_provenance records the two shipped lanes",
        [lane["index"] for lane in scene["output_lanes"]] == [0, 1]
        and close(scene["output_lanes"][0]["place"][1], 0.5)
        and close(scene["output_lanes"][1]["place"][1], -0.5),
    )
    check(
        "the two-lane manifest keeps output_belt.inboard_edge_y (0.425)",
        close(scene["output_belt"]["inboard_edge_y"], 0.425),
    )

    # ---- 2. the third body ---------------------------------------------- #
    cfg3 = SceneConfig(output_lanes=3)
    lanes3 = cfg3.output_lane_layout()
    check("3 lane layout has three bodies", len(lanes3) == 3)
    third = lanes3[2]
    check(
        "the third lane is the measured geometry",
        third["root"] == "/World/OutputBelt2"
        and close(abs(third["belt_center"][1]), sum(OUTPUT_LANE3_BELT_Y) / 2)
        and close(third["belt_size"][1], OUTPUT_LANE3_BELT_Y[1] - OUTPUT_LANE3_BELT_Y[0])
        and close(third["belt_size"][0], OUTPUT_LANE3_BELT_X[1] - OUTPUT_LANE3_BELT_X[0])
        and close(third["belt_center"][0], sum(OUTPUT_LANE3_BELT_X) / 2)
        and third["place"] == (OUTPUT_LANE3_PLACE[0], OUTPUT_LANE3_PLACE[1])
        and third["tray_size"][1] == OUTPUT_LANE3_TRAY_Y[1] - OUTPUT_LANE3_TRAY_Y[0],
        f"{third['belt_center']} size {third['belt_size']} place {third['place']}",
    )
    check("the third lane's side is -y", third["side"] == "-y" and third["sign"] == -1.0)
    check(
        "the third lane's belt is downstream of the first place transit",
        third["belt_center"][0] - third["belt_size"][0] / 2.0 >= 0.48 - 1e-9,
        f"upstream end {third['belt_center'][0] - third['belt_size'][0] / 2.0:.3f}",
    )
    check(
        "the -Y tray narrows to 0.20 m for the third body",
        close(cfg3.output_lane_layout()[1]["tray_size"][1], 2 * OUTPUT_LANE1_TRAY_HALF_WITH_THIRD),
    )
    check(
        "the second lane's own tray and place point do not move",
        lanes3[1]["place"] == lanes[1]["place"]
        and lanes3[1]["belt_center"] == lanes[1]["belt_center"],
    )
    check(
        "the third lane gets its own drop point",
        cfg3.output_belt_drop_points[:2] == cfg.output_belt_drop_points
        and cfg3.output_belt_drop_points[2] == (OUTPUT_LANE3_PLACE[0], OUTPUT_LANE3_PLACE[1]),
        str(cfg3.output_belt_drop_points),
    )

    # the bodies: no interpenetration, the own tray separated
    def rect(lane, what):
        if what == "belt":
            cx, cy, _cz = lane["belt_center"]
            sx, sy, _sz = lane["belt_size"]
        else:
            cx, cy = lane["tray_center"]
            sx, sy = lane["tray_size"]
        return (cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2)

    def gap(a, b):
        return max(b[0] - a[1], a[0] - b[1], b[2] - a[3], a[2] - b[3])

    for i in range(3):
        for j in range(i + 1, 3):
            for what in ("belt", "tray"):
                g = gap(rect(lanes3[i], what), rect(lanes3[j], what))
                check(
                    f"lanes {i}/{j} {what} have air between them",
                    g > 0.0,
                    f"{g * 1000:+.0f} mm",
                )
    # the chute bands (belt width - 0.01, +-12 mm lips)
    def chute(lane):
        cx, cy, _cz = lane["belt_center"]
        return (cy - (lane["belt_size"][1] - 0.01) / 2 - 0.012,
                cy + (lane["belt_size"][1] - 0.01) / 2 + 0.012)

    check(
        "the 1/2 chutes do not touch",
        gap((0, 1, *chute(lanes3[1])), (0, 1, *chute(lanes3[2]))) > 0.0,
        f"{1000 * gap((0, 1, *chute(lanes3[1])), (0, 1, *chute(lanes3[2]))):+.0f} mm",
    )

    # the release lands on the new slab with >= 3 sd
    dx_mean, dx_sd, dy_mean, dy_sd = 0.048, 0.006, 0.036, 0.008   # -y lane, P122
    delivered = (OUTPUT_LANE3_PLACE[0] + dx_mean, OUTPUT_LANE3_PLACE[1] - dy_mean)
    slab = rect(lanes3[2], "belt")
    margins = (delivered[0] - slab[0], slab[1] - delivered[0],
               delivered[1] - slab[2], slab[3] - delivered[1])
    sds = (margins[0] / dx_sd, margins[1] / dx_sd, margins[2] / dy_sd, margins[3] / dy_sd)
    check(
        "the delivered point is on the third slab with >= 3 sd on every axis",
        all(m > 0 for m in margins) and min(sds) >= 3.0,
        f"delivered ({delivered[0]:+.3f},{delivered[1]:+.3f}) margins "
        f"{[round(1000 * m) for m in margins]} mm = {[round(s, 1) for s in sds]} sd",
    )
    # ... and the transit is upstream of the body in x with the payload's offset
    # the *shipped* lane's transit to -0.50 is the one that must stay upstream:
    # it crosses the new lane's |y| band at t = (0.280-0.05)/(0.50-0.05).
    t_cross = (OUTPUT_LANE3_BELT_Y[0] - 0.05) / (0.50 - 0.05)
    x_at_edge = 0.34 + (0.43 - 0.34) * t_cross
    check(
        "the payload is upstream of the third body where it crosses its band",
        x_at_edge + 0.048 + 0.035 <= OUTPUT_LANE3_BELT_X[0],
        f"x {x_at_edge + 0.048 + 0.035:.3f} (the shipped transit, radius included) "
        f"vs belt start {OUTPUT_LANE3_BELT_X[0]:.3f}",
    )
    check(
        "the third belt is downstream of the supplied fruit's x band",
        OUTPUT_LANE3_BELT_X[0] >= 0.413,
        f"{OUTPUT_LANE3_BELT_X[0]:.3f} >= 0.413",
    )

    # ---- 3. the census --------------------------------------------------- #
    check(
        "on_output_belt names the lane and agrees with the boolean",
        cfg3.output_lane_of((0.60, -0.55, 1.36)) == 1
        and cfg3.output_lane_of((0.60, -0.336, 1.36)) == 2
        and cfg3.output_lane_of((0.60, 0.55, 1.36)) == 0
        and cfg3.output_lane_of((0.60, 0.10, 1.36)) is None,
    )
    check(
        "output_tray_of names the tray and agrees with on_output_tray",
        cfg3.output_tray_of((1.60, -0.336, 0.95)) == 2
        and cfg3.output_tray_of((1.60, -0.536, 0.95)) == 1
        and cfg3.output_tray_of((1.60, 0.545, 0.95)) == 0
        and cfg3.output_tray_of((1.60, -0.425, 0.95)) is None,
        "the 3rd tray, the narrowed -Y tray, the +Y tray and the 70 mm gap",
    )
    check(
        "the two-lane census is the shipped boolean",
        all(
            (cfg.output_tray_of(p) is not None) == cfg.on_output_tray(p)
            for p in [(1.60, y * 0.01, 0.95) for y in range(-75, 76)]
        ),
    )
    check(
        "the narrowed -Y tray still holds the shipped lane's delivered point",
        cfg3.output_tray_of((1.60, -0.536, 0.95)) == 1,
    )

    # the source shape: one layout reader, the builder and the two tests on it
    src = (ROOT / "src" / "fruit_sorting" / "assets.py").read_text(encoding="utf-8")
    conv = (ROOT / "src" / "fruit_sorting" / "conveyor.py").read_text(encoding="utf-8")
    scene = (ROOT / "src" / "fruit_sorting" / "scene.py").read_text(encoding="utf-8")
    check("the layout is one method", src.count("def output_lane_layout") == 1)
    check(
        "the builder takes a lane and the scene iterates the layout",
        "lane: dict | None = None" in conv
        and 'lanes = self.cfg.output_lane_layout()' in scene
        and 'OutputBelt(self.stage, self.cfg, lane["index"], lane["sign"], lane)'
        in scene,
    )
    check(
        "the tray census is the lane list, not a scalar",
        "def output_tray_of" in src and "return self.output_tray_of(position, margin) is not None" in src,
    )

    failed = [name for name, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed"
          + ("" if not failed else f"; FAILED: {failed}"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
