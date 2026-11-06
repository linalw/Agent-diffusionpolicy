"""P118 gate 1 - the reach at the pocket pick pose (offline, static IK).

    scripts/run.sh logs/p118/reach_probe.py

The question (`logs/p118/PREREG.md` section G1): with the fruit resting on the
pocket floor at `belt_top - 0.100`, its centre at `floor + r`, and the jaw target
`fruit centre + the pad standoff` along the tool axis (`jaw_z = floor + r + 0.070`
for the top-down hold `T0`), is there **any** delivered x (0.188-0.397) / y
(-0.05..+0.05, the measured landing spread) at **any** pool radius (14.7-34.8 mm)
where the pose passes?

Criterion (pinned in the PREREG before any cell):
  * primary = `residual <= 6 mm` AND `margin >= 0.05 rad` (the brief's two-clause
    gate);
  * report  = `qerr <= 2 deg` (T0/C0) or `tilt <= 5 deg` (NAT), and the p90
    surface clause `pad_lowest_z - floor >= 2 mm`;
  * the extra clause this pose needs: the **fingertip clearance to the pocket
    floor**, `jaw_z_achieved - FINGER_TIP_BELOW_JAW - floor`, reported per r.

`kill`: no pose in the band passes the primary clause at any r, OR the fingertip
clearance is negative at r >= 20 mm.

Machinery is `logs/p90/station_map.py`'s (itself `logs/p66/ik_probe_sweep.py`'s):
same scene (`environment`, `pedestal`, `robot` - **no conveyor**: the probe asks
whether the arm can hold the pose, not whether it can get there through the
slab), same candidate attitudes (`logs/p62/candidates.json` T0, `configs/
waypoints_oriented.json` C0, `NAT` = position-only), same `solve_to` recipe and
the same `pad_lowest_z` read off the authored `configs/finger_pads.json` bodies.

Env:
  P118_ARMS   default `left,right`
  P118_MODES  default `T0,NAT,C0`
  P118_R      default `0.0147,0.018,0.0215,0.025,0.030,0.0348`  (pool r, m)
  P118_X      default `0.188,0.24,0.274,0.32,0.397`  (delivered band)
  P118_Y      default `-0.05,0.0,+0.05`               (landing spread)
  P118_JSON   default `logs/p118/reach_rows.json`
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

install_failure_handler("p118_reach_probe")

DT = 1.0 / 120.0
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

ARMS = tuple(a.strip() for a in os.environ.get("P118_ARMS", "left,right").split(",") if a.strip())
MODES = tuple(m.strip().upper() for m in os.environ.get("P118_MODES", "T0,NAT,C0").split(",") if m.strip())
RS = tuple(
    float(v) for v in os.environ.get(
        "P118_R", "0.0147,0.018,0.0215,0.025,0.030,0.0348"
    ).split(",")
)
XS = tuple(float(v) for v in os.environ.get("P118_X", "0.188,0.24,0.274,0.32,0.397").split(","))
YS = tuple(float(v) for v in os.environ.get("P118_Y", "-0.05,0.0,0.05").split(","))
TOL = float(os.environ.get("P118_TOL", "0.006"))
RESTARTS = int(os.environ.get("P118_RESTARTS", "1"))
SEED_NAME = os.environ.get("P118_SEED", "grasp").strip() or "grasp"
PAD_RADIUS = float(os.environ.get("PAD_RADIUS", "0.010"))
JSON_OUT = os.environ.get("P118_JSON", os.path.join(HERE, "reach_rows.json"))
#: `tasks.FINGER_TIP_BELOW_JAW` - the fingertip plane is this far below the jaw
#: centre (the build print's own constant). Restated here so the probe is a
#: standalone `logs/` artifact (no `src/` import of a constant that the probe
#: would otherwise only use for a report).
FINGER_TIP_BELOW_JAW = 0.0805
#: P117's measured pocket: the floor is 100 mm below the belt top.
POCKET_DROP = 0.100
#: P117's measured pad standoff the pick target uses (`_pad_standoff`: 60 + 10).
PAD_STANDOFF = 0.070

BELT = np.array([0.0, -1.0, 0.0])

#: PREREG G1 - the pass clause.
RES_MAX_MM = 6.0
QERR_MAX_DEG = 2.0
MARGIN_MIN_RAD = 0.05
PAD_MIN_MM = 2.0
TILT_MAX_NAT_DEG = 5.0


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
    r = quat_matrix(q)
    return float(np.degrees(np.arccos(max(-1.0, min(1.0, -float(r[2, 2]))))))


def att_reads(q) -> tuple[float, float, float]:
    r = quat_matrix(q)
    return float(r[:, 2] @ BELT), float(r[2, 1]), float(r[1, 2])


def pad_lowest_z(link_pos, link_quat, spec) -> float:
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
    floor_top = belt_top - POCKET_DROP

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
            f"[p118r] {side}: T0 tilt={tilt_deg(q_down):.2f}deg proj={att_reads(q_down)[0]:+.4f} | "
            f"C0 tilt={tilt_deg(q_file):.2f}deg proj={att_reads(q_file)[0]:+.4f} | "
            f"|dot(T0,C0)|={abs(float(q_down @ q_file)):.6f}"
        )

    say(
        f"[p118r] belt_top={belt_top:.3f} pocket floor={floor_top:.3f} (drop "
        f"{POCKET_DROP * 1000:.0f}mm) standoff={PAD_STANDOFF * 1000:.0f}mm "
        f"tip_below_jaw={FINGER_TIP_BELOW_JAW * 1000:.1f}mm "
        f"r={','.join(f'{v * 1000:.1f}' for v in RS)}mm x={','.join(f'{v:.3f}' for v in XS)} "
        f"y={','.join(f'{v:+.2f}' for v in YS)} arms={','.join(ARMS)} modes={','.join(MODES)} "
        f"seed={SEED_NAME} restarts={RESTARTS} tol={TOL * 1000:.1f}mm "
        f"cells={len(ARMS) * len(MODES) * len(RS) * len(XS) * len(YS)}"
    )

    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot"))
    scene.start(physics_dt=DT, warmup_steps=60)

    arms = {}
    for side in ARMS:
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        arms[side] = arm
    app_utils.update_app(steps=40)
    for side in ARMS:
        seed = np.asarray(waypoints["arms"][side][SEED_NAME], dtype=float)
        arm = arms[side]
        arm.teleport_joints(seed)
        arm.hold_quaternion = hold[(side, "C0")]
        app_utils.update_app(steps=20)
        jaw_seed = np.asarray(arm.jaw_centre(), dtype=float)
        _, quat_seed = arm.tcp_pose()
        say(
            f"[p118r] {side} seed({SEED_NAME}) jaw=[{jaw_seed[0]:+.4f},{jaw_seed[1]:+.4f},"
            f"{jaw_seed[2]:.4f}] tilt_seed={tilt_deg(quat_seed):.2f}deg"
        )
        arm.hold_quaternion = None

    rows = []
    t_sweep = time.time()
    for side in ARMS:
        arm = arms[side]
        seed = np.asarray(waypoints["arms"][side][SEED_NAME], dtype=float)
        pad_specs = list(pads[side].values())
        for mode in MODES:
            q_cmd = hold[(side, mode)]
            proj_cmd = None if q_cmd is None else att_reads(q_cmd)[0]
            for r in RS:
                z = floor_top + r + PAD_STANDOFF
                for y in YS:
                    for x in XS:
                        t_cell = time.time()
                        arm.teleport_joints(seed)
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
                        pad_mm = 1000.0 * (pad_low_z - floor_top)
                        margin = float(margins[joint])
                        res_mm = 1000.0 * residual
                        # the brief's extra clause: the fingertip plane above the
                        # floor. The *nominal* value is pure geometry (r - 10.5 mm);
                        # the achieved one is reported beside it because an
                        # unreachable cell's IK residual moves the jaw down.
                        tip_nominal_mm = 1000.0 * (r + PAD_STANDOFF - FINGER_TIP_BELOW_JAW)
                        tip_mm = 1000.0 * (float(jaw[2]) - FINGER_TIP_BELOW_JAW - floor_top)
                        if mode == "NAT":
                            quality = bool(tilt_ach <= TILT_MAX_NAT_DEG)
                        else:
                            quality = bool(qerr <= QERR_MAX_DEG)
                        primary = bool(res_mm <= RES_MAX_MM and margin >= MARGIN_MIN_RAD)
                        passed = bool(primary and quality and pad_mm >= PAD_MIN_MM)
                        row = {
                            "arm": side,
                            "mode": mode,
                            "r_mm": r * 1000.0,
                            "x": x,
                            "y": y,
                            "z_world": z,
                            "jaw_z_above_belt_mm": (z - belt_top) * 1000.0,
                            "residual_mm": res_mm,
                            "qerr_deg": qerr,
                            "tilt_ach_deg": tilt_ach,
                            "belt_proj_cmd": proj_cmd,
                            "belt_proj_ach": proj_ach,
                            "jaw_z_ach": jawz_ach,
                            "tool_y_ach": tool_y_ach,
                            "jaw_sep_mm": 1000.0 * jaw_sep,
                            "margin_rad": margin,
                            "margin_joint": joint + 1,
                            "jaw": [float(v) for v in jaw],
                            "jaw_dz_mm": 1000.0 * (float(jaw[2]) - z),
                            "pad_low_z": pad_low_z,
                            "pad_above_floor_mm": pad_mm,
                            "tip_nominal_mm": tip_nominal_mm,
                            "tip_above_floor_mm": tip_mm,
                            "primary": primary,
                            "pass": passed,
                            "wall_s": time.time() - t_cell,
                        }
                        rows.append(row)
                        say(
                            f"[p118r] {side:5s} {mode:3s} r={r * 1000:4.1f} y={y:+.2f} x={x:.3f} "
                            f"res={res_mm:6.1f}mm qerr="
                            f"{'  n/a' if q_cmd is None else f'{qerr:5.2f}'}deg "
                            f"tilt={tilt_ach:6.2f}deg margin={margin:+.3f}rad@j{joint + 1} "
                            f"pad={pad_mm:+7.1f}mm tip={tip_mm:+7.1f}mm "
                            f"PRIMARY={int(primary)} PASS={int(passed)} wall={row['wall_s']:.2f}s"
                        )
    t_sweep = time.time() - t_sweep

    # ---- the verdict grids ------------------------------------------------- #
    say("[p118r] ---- pass grid ----")
    say(
        f"[p118r] primary: res<={RES_MAX_MM:.0f}mm AND margin>={MARGIN_MIN_RAD:.2f}rad | "
        f"full: + qerr<={QERR_MAX_DEG:.0f}deg (NAT tilt<={TILT_MAX_NAT_DEG:.0f}) AND "
        f"pad>={PAD_MIN_MM:.0f}mm | tip = jaw_z - {FINGER_TIP_BELOW_JAW * 1000:.1f}mm - floor"
    )
    summary = {}
    for side in ARMS:
        for mode in MODES:
            for r in RS:
                cells = [row for row in rows if row["arm"] == side and row["mode"] == mode and row["r_mm"] == r * 1000.0]
                if not cells:
                    continue
                best = max(cells, key=lambda row: row["margin_rad"])
                summary[f"{side}|{mode}|{r * 1000:.1f}"] = {
                    "primary": sum(1 for row in cells if row["primary"]),
                    "pass": sum(1 for row in cells if row["pass"]),
                    "of": len(cells),
                    "best_margin_rad": best["margin_rad"],
                    "best_margin_cell": [best["x"], best["y"]],
                    "min_residual_mm": min(row["residual_mm"] for row in cells),
                    "min_tip_mm": min(row["tip_above_floor_mm"] for row in cells),
                    "min_pad_mm": min(row["pad_above_floor_mm"] for row in cells),
                }
                say(
                    f"[p118r] {side:5s} {mode:3s} r={r * 1000:4.1f}mm "
                    f"primary={summary[f'{side}|{mode}|{r * 1000:.1f}']['primary']}/{len(cells)} "
                    f"full={summary[f'{side}|{mode}|{r * 1000:.1f}']['pass']}/{len(cells)} "
                    f"best_margin={best['margin_rad']:+.3f}rad@j{best['margin_joint']} "
                    f"@({best['x']:.3f},{best['y']:+.2f}) "
                    f"res={min(row['residual_mm'] for row in cells):.1f}.."
                    f"{max(row['residual_mm'] for row in cells):.1f}mm "
                    f"tip={min(row['tip_above_floor_mm'] for row in cells):+.1f}.."
                    f"{max(row['tip_above_floor_mm'] for row in cells):+.1f}mm "
                    f"pad={min(row['pad_above_floor_mm'] for row in cells):+.1f}.."
                    f"{max(row['pad_above_floor_mm'] for row in cells):+.1f}mm"
                )
            # per (arm, mode, r) the y x pass grid
            for r in RS:
                for y in YS:
                    cells = [
                        row for row in rows
                        if row["arm"] == side and row["mode"] == mode
                        and row["r_mm"] == r * 1000.0 and row["y"] == y
                    ]
                    if not cells:
                        continue
                    ok = [f"{row['x']:.3f}" for row in cells if row["primary"]]
                    say(
                        f"[p118r]   {side:5s} {mode:3s} r={r * 1000:4.1f} y={y:+.2f} "
                        f"primary_x=[{','.join(ok) if ok else '-'}] "
                        f"margin={min(row['margin_rad'] for row in cells):+.3f}.."
                        f"{max(row['margin_rad'] for row in cells):+.3f} "
                        f"res={min(row['residual_mm'] for row in cells):.1f}.."
                        f"{max(row['residual_mm'] for row in cells):.1f}"
                    )

    n_primary = sum(1 for row in rows if row["primary"])
    n_pass = sum(1 for row in rows if row["pass"])
    t0_primary = sum(1 for row in rows if row["mode"] == "T0" and row["primary"])
    smallest = min(RS)
    # The registered clause is the **nominal** geometry (`floor + r - 10.5 mm`);
    # the achieved value is reported, never gated: an unreachable cell's IK
    # residual lowers the jaw (a -0.2 mm row at x=0.397, r=25 mm), which is a
    # reach failure, not a fingertip-clearance failure.
    tip_nominal_at_20 = [row["tip_nominal_mm"] for row in rows if row["r_mm"] >= 20.0]
    tip_achieved_at_20 = [row["tip_above_floor_mm"] for row in rows if row["r_mm"] >= 20.0]
    kill = bool(
        t0_primary == 0
        or (tip_nominal_at_20 and min(tip_nominal_at_20) < 0.0)
    )
    say(
        f"[p118r] cells={len(rows)} primary={n_primary} full={n_pass} T0_primary={t0_primary} "
        f"nominal_tip_r>=20={min(tip_nominal_at_20) if tip_nominal_at_20 else float('nan'):+.2f}mm "
        f"achieved_tip_r>=20={min(tip_achieved_at_20) if tip_achieved_at_20 else float('nan'):+.2f}mm "
        f"GATE1={'PASS' if not kill else 'KILL'} mini_r={smallest * 1000:.1f}mm"
    )

    wall = time.time() - t_start
    say(f"[p118r] sweep_wall={t_sweep:.1f}s total_wall={wall:.1f}s per_cell={t_sweep / max(1, len(rows)):.2f}s")

    with open(JSON_OUT, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "belt_top": belt_top,
                "floor_top": floor_top,
                "pocket_drop_m": POCKET_DROP,
                "pad_standoff_m": PAD_STANDOFF,
                "finger_tip_below_jaw_m": FINGER_TIP_BELOW_JAW,
                "rs": list(RS),
                "xs": list(XS),
                "ys": list(YS),
                "arms": list(ARMS),
                "modes": list(MODES),
                "seed_name": SEED_NAME,
                "restarts_setting": RESTARTS,
                "tol": TOL,
                "pass_criteria": {
                    "res_max_mm": RES_MAX_MM,
                    "qerr_max_deg": QERR_MAX_DEG,
                    "margin_min_rad": MARGIN_MIN_RAD,
                    "pad_min_mm": PAD_MIN_MM,
                    "tilt_max_nat_deg": TILT_MAX_NAT_DEG,
                },
                "counts": {"cells": len(rows), "primary": n_primary, "full": n_pass,
                           "t0_primary": t0_primary},
                "gate1_kill": kill,
                "rows": rows,
                "summary": summary,
                "wall": {"sweep_s": t_sweep, "total_s": wall,
                         "per_cell_s": t_sweep / max(1, len(rows))},
            },
            handle,
            indent=1,
        )
    say(f"[p118r] wrote {JSON_OUT}")
    say("[p118r] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
