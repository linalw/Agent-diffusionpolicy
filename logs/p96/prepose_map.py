"""P96 phase 0 - does each two-line station admit a **clearance pre-pose**?

    scripts/run.sh logs/p96/prepose_map.py            # both arms, the whole grid
    scripts/run.sh logs/p96/prepose_map.py            # -> logs/p96/prepose_rows.json

A **copy** of `logs/p66/ik_probe_sweep.py`'s recipe (itself a copy of
`logs/p62/ik_probe.py`; both kept byte-untouched so their artifacts stay
reproducible), retargeted from the pick band to the **two-line stations' pre-pose
question**. The registration is `logs/p96/PREREG.md` (grid, modes, criterion and
falsifier pinned before this ran).

What it asks: `_prepare_two_line_stations` solves each arm's pre-pose at
`(pick_x, station_y, belt_top + grasp_clearance)` - and **skips the left
entirely** because the left station *is* the calibrated pick point, so the left's
pre-pose is the calibrated `grasp` configuration, whose pad plane ends
`belt_top + 0.029` (P95). The invariant needs a pose whose achieved jaw reaches
`belt_top + 0.155` at every station. Does the arm offer one?

Differences from the P66 probe, all of them the retarget:

* **x is the station column** (`0.32/0.34/0.36`; `0.34` is `cfg.pick_x`, the
  value `_prepare_two_line_stations` uses), and `y` is the arm's own station
  (`left +0.000`, `right -0.100`) - not a swept band.
* **z is a depth ladder above the belt top**: `0.095` (the shipped
  `grasp_clearance`, i.e. today's right-station solve depth), `0.13`, `0.155`
  (the invariant), `0.165` (the candidate solve target), `0.18`, `0.20`.
* **two modes**: `T0` = the attitude `_prepare_two_line_stations` pins
  (`mirror_across_xz(top_down_quaternion("x"))` for the left, the un-mirrored
  one for the right); `NAT` = `hold_quaternion = None`, the position-only solve
  the *place* leg runs ("if a staging pose does not care about attitude, what
  does the arm offer?").
* **both arms**, each solved from `configs/waypoints_oriented.json`'s own
  `arms.<side>.grasp` seed - the seed `_prepare_two_line_stations` uses.
* **the shipped baseline is measured, not assumed**: the calibrated `grasp`
  configuration is teleported to and its jaw z read, for each arm. For the left
  that *is* the shipped pre-pose (the skip), and it is the number P95 recorded.

Env: `FRUIT_P96_{ARMS,X,Z,MODES,SEED,RESTARTS,TOL,JSON}`.
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
from fruit_sorting.motion import mirror_across_xz, top_down_quaternion
from fruit_sorting.scene import SortingScene

install_failure_handler("p96_prepose_map")

DT = 1.0 / 120.0
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

#: P39 phase 2 / `tasks.FINGER_TIP_BELOW_JAW`: the pad point hangs this far below
#: the jaw centre, so the pad plane = jaw z - this. Restated as a literal so the
#: probe does not import the module the phase is about to change.
PAD_DROP = 0.0805
#: The tallest fruit's top above the belt top (P95 section 5: the hover's pad
#: plane at `belt_top + 0.072` is 13.5 mm above it).
FRUIT_TOP = 0.0585
#: P95's clearance number: `jaw_z >= belt_top + 0.155`, i.e. pad plane + 0.0745.
CLEARANCE_J = 0.155
#: This phase's robustness floor for a pose held 65 ticks per attempt.
MARGIN_MIN_RAD = 0.02
TOL = float(os.environ.get("FRUIT_P96_TOL", "0.006"))
RESTARTS = int(os.environ.get("FRUIT_P96_RESTARTS", "1"))
SEED_NAME = os.environ.get("FRUIT_P96_SEED", "grasp").strip() or "grasp"
ARMS = tuple(a.strip() for a in os.environ.get("FRUIT_P96_ARMS", "left,right").split(",") if a.strip())
XS = tuple(float(v) for v in os.environ.get("FRUIT_P96_X", "0.32,0.34,0.36").split(","))
ZS = tuple(
    float(v)
    for v in os.environ.get(
        "FRUIT_P96_Z", "0.095,0.13,0.155,0.165,0.18,0.20"
    ).split(",")
)
MODES = tuple(m.strip() for m in os.environ.get("FRUIT_P96_MODES", "T0,NAT").split(",") if m.strip())
JSON_OUT = os.environ.get("FRUIT_P96_JSON", os.path.join(HERE, "prepose_rows.json"))

#: The shipped stations (`run_bimanual`'s defaults).
STATION_Y = {"left": 0.0, "right": -0.10}


def hold_for(side: str) -> np.ndarray:
    """The attitude `_prepare_two_line_stations` pins for this side."""
    q = top_down_quaternion(os.environ.get("FRUIT_HAND_AXIS", "x"))
    return mirror_across_xz(q) if side == "left" else q


def main() -> int:
    t_start = time.time()
    with open(os.path.join(ROOT, "configs", "waypoints_oriented.json"), encoding="utf-8") as fh:
        waypoints = json.load(fh)

    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(
        f"[p96] belt_top={belt_top:.4f} pick=({cfg.pick_x:.3f},{cfg.pick_y:+.3f}) "
        f"grasp_clearance={cfg.grasp_clearance:.4f} "
        f"(=> shipped station solve jaw = belt_top+{cfg.grasp_clearance:.4f}) "
        f"clearance criterion jaw>=belt_top+{CLEARANCE_J:.3f} "
        f"cand={'/'.join(MODES)} x={','.join(f'{v:.2f}' for v in XS)} "
        f"z={','.join(f'{v:.3f}' for v in ZS)} seed={SEED_NAME} restarts={RESTARTS} "
        f"cells={len(ARMS) * len(MODES) * len(XS) * len(ZS)}"
    )

    rows = []
    t0 = time.time()
    for side in ARMS:
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=40)
        seed = np.asarray(waypoints["arms"][side][SEED_NAME], dtype=float)
        station_y = float(STATION_Y[side])

        # ---- the shipped baseline: the calibrated grasp config, teleported to -- #
        # (for the left this IS the shipped pre-pose - `_prepare_two_line_stations`
        #  skips a station on the pick point - and it is P95's measured pose.)
        arm.hold_quaternion = None
        arm.teleport_joints(seed)
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=20)
        base_jaw = np.asarray(arm.jaw_centre(), dtype=float)
        margins = np.minimum(seed - arm.arm_lo, arm.arm_hi - seed)
        base = {
            "arm": side,
            "cand": "CFG",
            "station_y": station_y,
            "x": float(base_jaw[0]),
            "y": float(base_jaw[1]),
            "z_above_belt": float(base_jaw[2] - belt_top),
            "jaw_z_belt_mm": 1000 * (float(base_jaw[2]) - belt_top),
            "pad_z_belt_mm": 1000 * (float(base_jaw[2]) - PAD_DROP - belt_top),
            "pad_clear_of_fruit_top_mm": 1000
            * (float(base_jaw[2]) - PAD_DROP - belt_top - FRUIT_TOP),
            "margin_rad": float(margins[int(np.argmin(margins))]),
            "margin_joint": int(np.argmin(margins)) + 1,
            "config": [float(v) for v in seed],
            "solved": True,
            "note": "the calibrated 'grasp' config teleported to (the shipped pre-pose)",
        }
        rows.append(base)
        say(
            f"[p96] {side} baseline CFG: jaw z-belt={base['jaw_z_belt_mm']:+.1f}mm "
            f"pad z-belt={base['pad_z_belt_mm']:+.1f}mm "
            f"(pad - fruit top = {base['pad_clear_of_fruit_top_mm']:+.1f}mm) "
            f"margin={base['margin_rad']:+.3f} rad @j{base['margin_joint']}"
        )

        for mode in MODES:
            q = hold_for(side) if mode == "T0" else None
            for z in ZS:
                for x in XS:
                    target = np.array([x, station_y, belt_top + z], dtype=float)
                    arm.teleport_joints(seed)
                    arm.hold_quaternion = q
                    arm.set_gripper(arm.OPEN)
                    app_utils.update_app(steps=20)
                    config, residual = arm.solve_to(
                        target, iterations=400, tolerance=TOL, restarts=RESTARTS, seed=7
                    )
                    jaw = np.asarray(arm.jaw_centre(), dtype=float)
                    _, quat = arm.tcp_pose()
                    qerr = (
                        float("nan")
                        if q is None
                        else float(np.degrees(np.linalg.norm(quaternion_error(q, quat))))
                    )
                    mg = np.minimum(config - arm.arm_lo, arm.arm_hi - config)
                    joint = int(np.argmin(mg))
                    row = {
                        "arm": side,
                        "cand": mode,
                        "station_y": station_y,
                        "x": x,
                        "y": station_y,
                        "z_above_belt": z,
                        "z_world": float(target[2]),
                        "residual_mm": 1000 * float(residual),
                        "qerr_deg": qerr,
                        "jaw_z_belt_mm": 1000 * (float(jaw[2]) - belt_top),
                        "pad_z_belt_mm": 1000 * (float(jaw[2]) - PAD_DROP - belt_top),
                        "pad_clear_of_fruit_top_mm": 1000
                        * (float(jaw[2]) - PAD_DROP - belt_top - FRUIT_TOP),
                        "jaw_dz_mm": 1000 * (float(jaw[2]) - float(target[2])),
                        "margin_rad": float(mg[joint]),
                        "margin_joint": joint + 1,
                        "config": [float(v) for v in config],
                        "solved": bool(float(residual) <= TOL),
                        "reach_ok": bool(float(jaw[2]) - belt_top >= z - TOL),
                        "invariant_ok": bool(
                            float(jaw[2]) - PAD_DROP - belt_top >= CLEARANCE_J - PAD_DROP
                        ),
                        "pass": bool(
                            float(residual) <= TOL
                            and float(jaw[2]) - belt_top >= z - TOL
                            and float(mg[joint]) >= MARGIN_MIN_RAD
                            and float(jaw[2]) - PAD_DROP - belt_top
                            >= CLEARANCE_J - PAD_DROP
                        ),
                    }
                    rows.append(row)
                    say(
                        f"[p96] {side} {mode:>3} x={x:.2f} z=+{z:.3f}: "
                        f"res={row['residual_mm']:5.1f}mm qerr={qerr:5.1f}deg "
                        f"jaw_z={row['jaw_z_belt_mm']:+6.1f} pad_z={row['pad_z_belt_mm']:+6.1f} "
                        f"margin={row['margin_rad']:+.3f}@j{row['margin_joint']} "
                        f"{'PASS' if row['pass'] else '-'}"
                    )
        arm.hold_quaternion = None

    with open(JSON_OUT, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)

    # ---- the verdict, printed so the driver log carries it -------------------- #
    say("")
    say(f"[p96] {len(rows)} rows -> {JSON_OUT} ({time.time() - t0:.1f}s, "
        f"total {time.time() - t_start:.1f}s)")
    for side in ARMS:
        pass_z = [
            r for r in rows
            if r["arm"] == side and r["cand"] != "CFG" and r["pass"]
        ]
        best = max(
            (r for r in rows if r["arm"] == side and r["cand"] != "CFG"),
            key=lambda r: r["jaw_z_belt_mm"],
        )
        say(
            f"[p96] {side}: {len(pass_z)} passing cells; highest achieved jaw "
            f"{best['jaw_z_belt_mm']:+.1f}mm (pad {best['pad_z_belt_mm']:+.1f}mm) at "
            f"{best['cand']} x={best['x']:.2f} z=+{best['z_above_belt']:.3f} "
            f"res={best['residual_mm']:.1f}mm margin={best['margin_rad']:+.3f}@"
            f"j{best['margin_joint']}"
        )
        admissible = [
            r for r in pass_z if r["jaw_z_belt_mm"] >= 1000 * CLEARANCE_J - 1e-6
        ]
        if admissible:
            top = max(admissible, key=lambda r: r["margin_rad"])
            say(
                f"[p96] {side}: CLEARANCE PRE-POSE ADMISSIBLE - {len(admissible)} cells at "
                f"jaw>=belt_top+{CLEARANCE_J:.3f}; most robust {top['cand']} x={top['x']:.2f} "
                f"z=+{top['z_above_belt']:.3f} margin={top['margin_rad']:+.3f} rad "
                f"res={top['residual_mm']:.1f}mm"
            )
        else:
            say(f"[p96] {side}: NO admissible clearance pre-pose cell (F1 for this arm)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
