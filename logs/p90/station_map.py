"""P90 - the output place-station map: can the left hold top-down at the place station?

    scripts/run.sh logs/p90/station_map.py

A **copy** of `logs/p66/ik_probe_sweep.py` (itself a copy of `logs/p62/ik_probe.py`,
kept byte-untouched so the P62/P64/P66 artifacts stay reproducible), retargeted from
the **pick** station to the **place** station. The registration is
`logs/p90/METHOD.md` (criterion, grid, modes and ranking pinned before this ran).

Differences from the P66 probe, all of them the retarget:

* **the target is the place pose the code commands**, not a swept pick point:
  `(x, y, z)` with `z` taken in **world** metres from the two heights the config
  produces - `output_place_z` (1.450, the place height) and
  `output_place_z + the OpenArm transfer add` (1.530, the transfer the place leg
  ends at). P66's `z` was metres *above the main belt top*; here it is absolute.
* **both arms** (`FRUIT_P90_ARMS`, default `left,right`), each in its own lane
  (`y` goes to `+` for the left, `-` for the right).
* **three modes** (`FRUIT_P90_MODES`):
    - `T0`  - hold the top-down attitude (candidates.json's `T0` for the left,
              `mirror_across_xz(T0)` for the right) - *can the arm hold top-down
              at this station?*
    - `NAT` - `hold_quaternion = None`, i.e. the **position-only** solve the
              shipped place leg actually runs - *what would the leg achieve here
              with no code change?*
    - `C0`  - hold the arm's own `configs/waypoints_oriented.json`
              `grasp_quaternion` (the P66 continuity control: the belt-aligned
              attitude the arm falls back to).
* **the achieved `tilt`** (`acos(-rot[2,2])`, `[attitude]`'s and P73's own
  expression: 0 deg = tool axis straight down) is recorded on every row, because
  for `NAT` it *is* the read.
* **the pad clearance is against the surface under the pads**, using
  `tasks._payload_clearance`'s own switch (`|y| < 0.40` -> the main belt top,
  otherwise the output-belt top), plus the absolute pad height so a cell below the
  slab is visible.

The scene is P66's build - `("environment", "pedestal", "robot", "conveyor")`, with
**no output-slab geometry** - so a residual is a kinematic residual and not a
contact. That is deliberate (METHOD §5): the map asks whether a pose is reachable,
not whether the arm can get there through the line.

Env: `FRUIT_P90_{ARMS,MODES,X,Y,Z,SEED,RESTARTS,TOL,JSON}`. `SEED` names the
`configs/waypoints_oriented.json` `arms.<side>.<SEED>` configuration every cell is
solved from; the default is `grasp_lift`, the place leg's own start.
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.control import ArmController, quaternion_error
from fruit_sorting.motion import mirror_across_xz
from fruit_sorting.scene import SortingScene

install_failure_handler("p90_place_station_map")

DT = 1.0 / 120.0
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

ARMS = tuple(
    a.strip() for a in os.environ.get("FRUIT_P90_ARMS", "left,right").split(",") if a.strip()
)
MODES = tuple(
    m.strip().upper()
    for m in os.environ.get("FRUIT_P90_MODES", "T0,NAT,C0").split(",")
    if m.strip()
)
XS = tuple(
    float(v) for v in os.environ.get("FRUIT_P90_X", "0.28,0.33,0.38,0.43,0.48,0.53,0.58").split(",")
)
YS = tuple(
    float(v) for v in os.environ.get("FRUIT_P90_Y", "0.35,0.40,0.45,0.50,0.55,0.60,0.65").split(",")
)
ZS = tuple(float(v) for v in os.environ.get("FRUIT_P90_Z", "1.450,1.530").split(","))
TOL = float(os.environ.get("FRUIT_P90_TOL", "0.006"))
RESTARTS = int(os.environ.get("FRUIT_P90_RESTARTS", "1"))
SEED_NAME = os.environ.get("FRUIT_P90_SEED", "grasp_lift").strip() or "grasp_lift"
PAD_RADIUS = float(os.environ.get("FRUIT_PAD_RADIUS", "0.010"))
JSON_OUT = os.environ.get("FRUIT_P90_JSON", os.path.join(HERE, "station_rows.json"))

BELT = np.array([0.0, -1.0, 0.0])

#: METHOD §3 - the pass clause, pinned before the run.
RES_MAX_MM = 6.0
QERR_MAX_DEG = 2.0
MARGIN_MIN_RAD = 0.05
PAD_MIN_MM = 2.0
#: METHOD §3 - the NAT clause's stand-in for `qerr`: the achieved tilt must be
#: top-down at the `drift_end` scale (the 0.24 rung reads 3.4 deg).
TILT_MAX_NAT_DEG = 5.0

#: `tasks._payload_clearance`'s own switch: below this |y| the surface under the
#: pads is the main belt, at or above it the output belt.
SURFACE_SWITCH_Y = 0.40


def quat_matrix(q) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    q = q / np.linalg.norm(q)
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def tilt_deg(q) -> float:
    """`acos(-rot[2,2])`: the angle of the tool axis off straight-down (0 = T0)."""
    r = quat_matrix(q)
    return float(np.degrees(np.arccos(max(-1.0, min(1.0, -float(r[2, 2]))))))


def att_reads(q) -> tuple[float, float, float]:
    """(belt projection of the tool axis, jaw-axis z, tool-axis y)."""
    r = quat_matrix(q)
    return float(r[:, 2] @ BELT), float(r[2, 1]), float(r[1, 2])


def pad_lowest_z(link_pos, link_quat, spec) -> float:
    """Lowest world point of an authored capsule pad rigidly tied to a finger link."""
    r_link = quat_matrix(link_quat)
    r_local = quat_matrix(spec["quat"])
    centre = np.asarray(link_pos, dtype=float) + r_link @ np.asarray(spec["translate"], dtype=float)
    axis = r_link @ r_local @ np.array([0.0, 0.0, 1.0])
    height = max(float(spec["size"][2]) - 2.0 * PAD_RADIUS, 0.005)
    return float(centre[2] - 0.5 * height * abs(float(axis[2])) - PAD_RADIUS)


def main() -> int:
    t_start = time.time()
    with open(os.path.join(HERE, "..", "p62", "candidates.json"), encoding="utf-8") as handle:
        candidates = {row["name"]: row for row in json.load(handle)["rows"]}
    with open(os.path.join(ROOT, "configs", "waypoints_oriented.json"), encoding="utf-8") as handle:
        waypoints = json.load(handle)
    with open(os.path.join(ROOT, "configs", "finger_pads.json"), encoding="utf-8") as handle:
        pads = json.load(handle)

    cfg = SceneConfig()
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    out_top = float(cfg.output_belt_top_z)
    edge_y = abs(float(cfg.output_belt_y)) - float(cfg.output_belt_size[1]) / 2.0
    out_outer = abs(float(cfg.output_belt_y)) + float(cfg.output_belt_size[1]) / 2.0
    x_lo, x_hi = cfg.output_belt_x_range

    # ---- the attitudes, per arm -------------------------------------------- #
    q_t0 = np.asarray(candidates["T0"]["quat"], dtype=float)
    q_t0 = q_t0 / np.linalg.norm(q_t0)
    hold: dict[tuple[str, str], np.ndarray | None] = {}
    for side in ("left", "right"):
        q_file = np.asarray(waypoints["grasp_quaternion"][side], dtype=float)
        q_file = q_file / np.linalg.norm(q_file)
        q_down = q_t0 if side == "left" else mirror_across_xz(q_t0)
        hold[(side, "T0")] = q_down
        hold[(side, "C0")] = q_file
        hold[(side, "NAT")] = None
        say(
            f"[p90] {side}: T0 tilt={tilt_deg(q_down):.2f}deg proj={att_reads(q_down)[0]:+.4f} | "
            f"C0 tilt={tilt_deg(q_file):.2f}deg proj={att_reads(q_file)[0]:+.4f} | "
            f"|dot(T0,C0)|={abs(float(q_down @ q_file)):.6f}"
        )
    say(
        f"[p90] belt_top={belt_top:.3f} output_top={out_top:.3f} "
        f"slab|y|={edge_y:.3f}..{out_outer:.3f} x={x_lo:.2f}..{x_hi:.2f} "
        f"place=({cfg.output_place_x:.3f},{cfg.output_place_y:.3f}) "
        f"place_z={cfg.output_place_z:.3f} transfer={cfg.output_place_z + 0.08:.3f} "
        f"surface_switch|y|={SURFACE_SWITCH_Y:.2f} seed={SEED_NAME} restarts={RESTARTS} "
        f"tol={TOL * 1000:.1f}mm arms={','.join(ARMS)} modes={','.join(MODES)} "
        f"cells={len(ARMS) * len(MODES) * len(XS) * len(YS) * len(ZS)}"
    )

    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)

    arms = {}
    for side in ARMS:
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        arms[side] = arm
    app_utils.update_app(steps=40)

    # ---- the seed under each arm's shipped attitude (the frame check) ------- #
    seeds = {}
    for side in ARMS:
        arm = arms[side]
        seed = np.asarray(waypoints["arms"][side][SEED_NAME], dtype=float)
        seeds[side] = seed
        arm.teleport_joints(seed)
        arm.hold_quaternion = hold[(side, "C0")]
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=20)
        jaw_seed = np.asarray(arm.jaw_centre(), dtype=float)
        _, quat_seed = arm.tcp_pose()
        say(
            f"[p90] {side} seed({SEED_NAME}) jaw=[{jaw_seed[0]:+.4f},{jaw_seed[1]:+.4f},"
            f"{jaw_seed[2]:.4f}] tilt_seed={tilt_deg(quat_seed):.2f}deg "
            f"qerr_vs_C0={np.degrees(np.linalg.norm(quaternion_error(hold[(side, 'C0')], quat_seed))):.2f}deg"
        )
        arm.hold_quaternion = None

    # ---- the sweep --------------------------------------------------------- #
    rows = []
    t_sweep = time.time()
    for side in ARMS:
        arm = arms[side]
        sign = 1.0 if side == "left" else -1.0
        pad_specs = list(pads[side].values())
        for mode in MODES:
            q_cmd = hold[(side, mode)]
            proj_cmd = None if q_cmd is None else att_reads(q_cmd)[0]
            jawz_cmd = None if q_cmd is None else att_reads(q_cmd)[1]
            for z in ZS:
                for y_abs in YS:
                    y = sign * y_abs
                    surface = belt_top if abs(y) < SURFACE_SWITCH_Y else out_top
                    for x in XS:
                        t_cell = time.time()
                        arm.teleport_joints(seeds[side])
                        arm.hold_quaternion = q_cmd
                        arm.set_gripper(arm.OPEN)
                        app_utils.update_app(steps=20)
                        target = np.array([x, y, z], dtype=float)
                        config, residual = arm.solve_to(
                            target, iterations=400, tolerance=TOL, restarts=RESTARTS, seed=7
                        )
                        tcp, quat = arm.tcp_pose()
                        jaw = np.asarray(arm.jaw_centre(), dtype=float)
                        qerr = (
                            float("nan")
                            if q_cmd is None
                            else float(np.degrees(np.linalg.norm(quaternion_error(q_cmd, quat))))
                        )
                        proj_ach, jawz_ach, tool_y_ach = att_reads(quat)
                        tilt_ach = tilt_deg(quat)
                        jaw_sep = float(
                            np.linalg.norm(
                                np.asarray(arm.jaw_positions()[1]) - np.asarray(arm.jaw_positions()[0])
                            )
                        )
                        margins = np.minimum(config - arm.arm_lo, arm.arm_hi - config)
                        joint = int(np.argmin(margins))
                        pos_l, quat_l = arm._finger_prims[0].get_world_poses()
                        pos_l = np.asarray(pos_l)[0]
                        quat_l = np.asarray(quat_l)[0]
                        pos_r = np.asarray(arm._finger_prims[1].get_world_poses()[0])[0]
                        pad_low_z = min(
                            pad_lowest_z(pos_l, quat_l, pad_specs[0]),
                            pad_lowest_z(pos_r, quat_l, pad_specs[1]),
                        )
                        pad_mm = 1000.0 * (pad_low_z - surface)
                        margin = float(margins[joint])
                        res_mm = 1000.0 * residual
                        if mode == "NAT":
                            passed = bool(
                                res_mm <= RES_MAX_MM
                                and tilt_ach <= TILT_MAX_NAT_DEG
                                and margin >= MARGIN_MIN_RAD
                                and pad_mm >= PAD_MIN_MM
                            )
                        else:
                            passed = bool(
                                res_mm <= RES_MAX_MM
                                and qerr <= QERR_MAX_DEG
                                and margin >= MARGIN_MIN_RAD
                                and pad_mm >= PAD_MIN_MM
                            )
                        row = {
                            "arm": side,
                            "mode": mode,
                            "x": x,
                            "y": y,
                            "z_world": z,
                            "restarts": RESTARTS,
                            "seed_name": SEED_NAME,
                            "residual_mm": res_mm,
                            "qerr_deg": qerr,
                            "tilt_ach_deg": tilt_ach,
                            "belt_proj_cmd": proj_cmd,
                            "belt_proj_ach": proj_ach,
                            "jaw_z_cmd": jawz_cmd,
                            "jaw_z_ach": jawz_ach,
                            "tool_y_ach": tool_y_ach,
                            "jaw_sep_mm": 1000.0 * jaw_sep,
                            "jaw_pad_dz_mm": 1000.0 * abs(jawz_ach) * jaw_sep,
                            "margin_rad": margin,
                            "margin_joint": joint + 1,
                            "config": [float(v) for v in config],
                            "jaw": [float(v) for v in jaw],
                            "jaw_dz_mm": 1000.0 * (float(jaw[2]) - z),
                            "surface_z": surface,
                            "surface": "main belt" if abs(y) < SURFACE_SWITCH_Y else "output belt",
                            "pad_low_z": pad_low_z,
                            "pad_above_surface_mm": pad_mm,
                            "pad_above_outbelt_mm": 1000.0 * (pad_low_z - out_top),
                            "on_slab_y": bool(edge_y <= abs(y) <= out_outer),
                            "solved": bool(residual <= TOL),
                            "pass": passed,
                            "wall_s": time.time() - t_cell,
                        }
                        rows.append(row)
                        say(
                            f"[p90] {side:5s} {mode:3s} z={z:.3f} y={y:+.2f} x={x:.3f} "
                            f"res={res_mm:6.1f}mm qerr="
                            f"{'   n/a' if q_cmd is None else f'{qerr:5.2f}'}deg "
                            f"tilt={tilt_ach:6.2f}deg margin={margin:+.3f}rad@j{joint + 1} "
                            f"pad={pad_mm:+7.1f}mm({row['surface'][:4]}) "
                            f"proj_ach={proj_ach:+.4f} tool_y={tool_y_ach:+.4f} "
                            f"PASS={int(passed)} wall={row['wall_s']:.2f}s"
                        )
    t_sweep = time.time() - t_sweep

    # ---- the verdict grids ------------------------------------------------- #
    say("[p90] ---- pass grid ----")
    say(
        f"[p90] criteria: T0/C0 res<={RES_MAX_MM:.0f}mm qerr<={QERR_MAX_DEG:.0f}deg "
        f"margin>={MARGIN_MIN_RAD:.2f}rad pad>={PAD_MIN_MM:.0f}mm | "
        f"NAT res<={RES_MAX_MM:.0f}mm tilt<={TILT_MAX_NAT_DEG:.0f}deg "
        f"margin>={MARGIN_MIN_RAD:.2f}rad pad>={PAD_MIN_MM:.0f}mm"
    )
    summary = {}
    for side in ARMS:
        for mode in MODES:
            for z in ZS:
                cells = [r for r in rows if r["arm"] == side and r["mode"] == mode and r["z_world"] == z]
                if not cells:
                    continue
                passed = [r for r in cells if r["pass"]]
                best = max(cells, key=lambda r: r["margin_rad"])
                summary[f"{side}|{mode}|{z:.3f}"] = {
                    "pass": len(passed),
                    "of": len(cells),
                    "best_margin_rad": best["margin_rad"],
                    "min_tilt_deg": min(r["tilt_ach_deg"] for r in cells),
                    "min_residual_mm": min(r["residual_mm"] for r in cells),
                    "solved": sum(1 for r in cells if r["solved"]),
                }
                say(
                    f"[p90] {side:5s} {mode:3s} z={z:.3f} pass={len(passed)}/{len(cells)} "
                    f"best_margin={best['margin_rad']:+.3f}rad@j{best['margin_joint']} "
                    f"tilt={min(r['tilt_ach_deg'] for r in cells):.2f}.."
                    f"{max(r['tilt_ach_deg'] for r in cells):.2f}deg "
                    f"res={min(r['residual_mm'] for r in cells):.1f}.."
                    f"{max(r['residual_mm'] for r in cells):.1f}mm "
                    f"solved={sum(1 for r in cells if r['solved'])}/{len(cells)}"
                )
            # the grid, one line per (arm, mode): rows = z, cols = x, cells = best y
            for z in ZS:
                for x in XS:
                    ys = [
                        r
                        for r in rows
                        if r["arm"] == side and r["mode"] == mode and r["z_world"] == z and r["x"] == x
                    ]
                    if not ys:
                        continue
                    ok = [f"{r['y']:+.2f}" for r in ys if r["pass"]]
                    bt = min(ys, key=lambda r: r["tilt_ach_deg"])
                    say(
                        f"[p90]   {side:5s} {mode:3s} z={z:.3f} x={x:.3f} pass_y=[{','.join(ok) if ok else '-'}] "
                        f"min_tilt={bt['tilt_ach_deg']:.2f}@y{bt['y']:+.2f} "
                        f"margin={bt['margin_rad']:+.3f}@j{bt['margin_joint']} "
                        f"res={bt['residual_mm']:.1f}"
                    )

    wall = time.time() - t_start
    say(
        f"[p90] cells={len(rows)} sweep_wall={t_sweep:.1f}s total_wall={wall:.1f}s "
        f"per_cell={t_sweep / max(1, len(rows)):.2f}s"
    )

    with open(JSON_OUT, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "belt_top": belt_top,
                "output_belt_top_z": out_top,
                "output_slab_edge_y": edge_y,
                "output_slab_outer_y": out_outer,
                "output_belt_x_range": [x_lo, x_hi],
                "output_place": [cfg.output_place_x, cfg.output_place_y],
                "output_place_z": cfg.output_place_z,
                "transfer_z": cfg.output_place_z + 0.08,
                "pick": [cfg.pick_x, cfg.pick_y],
                "xs": list(XS),
                "ys": list(YS),
                "zs": list(ZS),
                "arms": list(ARMS),
                "modes": list(MODES),
                "seed_name": SEED_NAME,
                "restarts_setting": RESTARTS,
                "tol": TOL,
                "surface_switch_y": SURFACE_SWITCH_Y,
                "pass_criteria": {
                    "res_max_mm": RES_MAX_MM,
                    "qerr_max_deg": QERR_MAX_DEG,
                    "margin_min_rad": MARGIN_MIN_RAD,
                    "pad_min_mm": PAD_MIN_MM,
                    "tilt_max_nat_deg": TILT_MAX_NAT_DEG,
                },
                "quats": {
                    f"{side}|{mode}": (
                        None if hold[(side, mode)] is None else [float(v) for v in hold[(side, mode)]]
                    )
                    for side in ARMS
                    for mode in MODES
                },
                "rows": rows,
                "summary": summary,
                "wall": {"sweep_s": t_sweep, "total_s": wall,
                         "per_cell_s": t_sweep / max(1, len(rows))},
            },
            handle,
            indent=1,
        )
    say(f"[p90] wrote {JSON_OUT}")
    say("[p90] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
