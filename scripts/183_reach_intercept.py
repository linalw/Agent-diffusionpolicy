"""R10-A: the reachable *intercept* map of the top-down moving catch.

    scripts/run.sh scripts/183_reach_intercept.py

`174_station_reach.py` measured the reachable lateral band (x) at the shipped
station (y = pick_y): residual <= 6 mm over x = 0.18-0.39, a hard cliff at 0.42
(`logs/v1/61_station_reach_seeded.log`). The R10 owner correction asks the
moving catch to generalize over the arm's reachable workspace - any (x, y), on
the fly - so this probe extends that approach along the belt (y) and adds the
two *dynamic* terms the catch's schedule depends on:

1. **The grip/hover map**: for a grid of along-belt offsets (y) x the lateral
   band (x), solve the top-down catch pose the way the catch holds it - jaw
   centre at `(x, pick_y + y, belt_top + z_grip)` for the grip and `+hover`
   for the hover - seeding from the calibrated grasp configuration exactly like
   `174` (a cold start put the right arm in a local minimum). The residual per
   point is the reach number; the joint-limit margin of the solved
   configuration is reported alongside (the boundary the residual alone cannot
   show).
2. **The sweep reach**: after the catch takes the fruit it keeps tracking it
   downstream through the close/hold (~0.15-0.22 m of belt travel). The probe
   solves the same pose `sweep` metres further downstream (`FRUIT_REACH_SWEEP`,
   default 0.15 m) at the grip height, so the map can distinguish an intercept
   that is merely touchable from one whose whole contact window is in reach.
3. **The setup cost vs the intercept offset**: the hover move from the
   calibrated pre-pose to the hover point is the catch's setup; its duration is
   belt travel the timing must pay. The probe times `move_to(hover(y))` from
   the grasp seed for the same y ladder (ticks at 120 Hz), plus the calibrated
   `jerk_limited` descent estimate for the hover -> grip leg.

No control code runs here; this is the measurement the R10-A design is
parameterised from. Prints one `[reach]` line per solved point and a summary
map per arm; `FRUIT_REACH_JSON` writes the raw rows for re-derivation.

Env knobs: `FRUIT_REACH_X` / `FRUIT_REACH_DY` (ladders), `FRUIT_REACH_SIDE`
("left,right"), `FRUIT_REACH_Z_GRIP` (0.09), `FRUIT_REACH_HOVER` (0.06),
`FRUIT_REACH_SWEEP` (0.15), `FRUIT_REACH_TOL` (0.006), `FRUIT_REACH_TIME`
(1 = run the setup-timing ladder too).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.simulation_manager import SimulationManager
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.control import ArmController
from fruit_sorting.motion import TrajectoryLimits, jerk_limited, mirror_across_xz, top_down_quaternion
from fruit_sorting.scene import SortingScene

install_failure_handler("183_reach_intercept")

DT = 1.0 / 120.0
CONTROL_DT = DT

#: The lateral ladder: the delivered band x = 0.20-0.36 plus its measured
#: edges (0.18 reachable, 0.39 the last clean column, 0.42 the hard cliff).
X_LADDER = tuple(
    float(v)
    for v in os.environ.get(
        "FRUIT_REACH_X", "0.18,0.20,0.24,0.28,0.32,0.36,0.39,0.42,0.45"
    ).split(",")
    if v.strip()
)
#: The along-belt ladder: world y = pick_y + dy, dy from upstream (+) to
#: downstream (-). 0.05 m steps over +/-0.30 m cover the whole measured static
#: reach with a margin on both ends.
Y_LADDER = tuple(
    float(v)
    for v in os.environ.get(
        "FRUIT_REACH_DY",
        "0.30,0.25,0.20,0.15,0.10,0.05,0.00,-0.05,-0.10,-0.15,-0.20,-0.25,-0.30",
    ).split(",")
    if v.strip()
)
SIDES = tuple(
    side.strip()
    for side in os.environ.get("FRUIT_REACH_SIDE", "left,right").split(",")
    if side.strip()
)
Z_GRIP = float(os.environ.get("FRUIT_REACH_Z_GRIP", "0.09"))
HOVER = float(os.environ.get("FRUIT_REACH_HOVER", "0.06"))
SWEEP = float(os.environ.get("FRUIT_REACH_SWEEP", "0.15"))
TOL = float(os.environ.get("FRUIT_REACH_TOL", "0.006"))
TIME_LADDER = os.environ.get("FRUIT_REACH_TIME", "1") == "1"
#: The measured constants the catch's own schedule uses (tasks.py): the hover
#: move runs at FRUIT_HOVER_STEP, the descent profile at these limits.
HOVER_STEP = float(os.environ.get("FRUIT_HOVER_STEP", "0.04"))
DESC_VMAX = float(os.environ.get("FRUIT_DYNAMIC_APPROACH_VMAX", "0.15"))
DESC_AMAX = float(os.environ.get("FRUIT_APPROACH_AMAX", "0.8"))


def descent_ticks(distance: float) -> int:
    limits = TrajectoryLimits.from_env(CONTROL_DT)
    limits.v_max = DESC_VMAX
    limits.a_max = DESC_AMAX
    positions, _, _ = jerk_limited(max(float(distance), 1e-3), limits)
    return len(positions)


def reach_point(arm, seed, hold, target, reset: bool = True):
    """One solve: optionally reset to the calibrated seed, hold the attitude, solve."""
    if reset:
        arm.teleport_joints(seed)
    arm.hold_quaternion = hold
    arm.set_gripper(arm.OPEN)
    app_utils.update_app(steps=20)
    config, residual = arm.solve_to(np.asarray(target, dtype=float), iterations=400,
                                    tolerance=TOL)
    jaw = np.asarray(arm.jaw_centre(), dtype=float)
    margins = np.minimum(config - arm.arm_lo, arm.arm_hi - config)
    joint = int(np.argmin(margins))
    return config, float(residual), jaw, float(margins[joint]), joint


def main() -> int:
    with open(
        os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json"), encoding="utf-8"
    ) as handle:
        waypoints = json.load(handle)
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=DT, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(
        f"[reach] belt_top={belt_top:.3f} pick=({cfg.pick_x:.3f},{cfg.pick_y:.3f}) "
        f"z_grip={Z_GRIP:.3f} hover={HOVER:.3f} sweep={SWEEP:.3f} tol={TOL * 1000:.1f}mm"
    )
    rows: list[dict] = []
    for side in SIDES:
        arm = ArmController(scene, side)
        arm.set_gripper(arm.OPEN)
        app_utils.update_app(steps=40)
        hold = top_down_quaternion(os.environ.get("FRUIT_HAND_AXIS", "x"))
        if side == "left":
            hold = mirror_across_xz(hold)
        seed = np.asarray(waypoints["arms"][side]["grasp"], dtype=float)
        # ---- 1/2. the grip/hover/sweep map --------------------------------- #
        for dy in Y_LADDER:
            for x in X_LADDER:
                y = cfg.pick_y + dy
                # Grip first (the intercept pose): only a clean grip is worth
                # the hover/sweep solves, and the unreachable corners cost the
                # full 400-iteration budget.
                grip_target = (x, y, belt_top + Z_GRIP)
                cfg_g, res_g, jaw_g, margin_g, joint_g = reach_point(
                    arm, seed, hold, grip_target
                )
                res_h = res_s = float("nan")
                if res_g <= TOL:
                    hover_target = (x, y, belt_top + Z_GRIP + HOVER)
                    _, res_h, _, margin_h, _ = reach_point(arm, seed, hold, hover_target)
                    sweep_target = (x, y - SWEEP, belt_top + Z_GRIP)
                    _, res_s, _, margin_s, _ = reach_point(arm, seed, hold, sweep_target)
                rows.append(
                    dict(
                        side=side, dy=dy, x=x,
                        hover_residual=res_h, grip_residual=res_g,
                        sweep_residual=res_s,
                        grip_margin=margin_g, grip_joint=joint_g,
                        jaw_grip=jaw_g.tolist(),
                    )
                )
                sweep_txt = "   n/a" if res_s != res_s else f"{res_s * 1000:6.1f}"
                say(
                    f"[reach] {side:5s} dy={dy:+.2f} x={x:.2f} "
                    f"grip_res={res_g * 1000:6.1f} hover_res={res_h * 1000:6.1f} "
                    f"sweep_res={sweep_txt} mm "
                    f"grip_margin={margin_g:+.3f} rad@j{joint_g} "
                    f"jaw=[{jaw_g[0]:+.3f},{jaw_g[1]:+.3f},{jaw_g[2]:.3f}]"
                )
        if TIME_LADDER:
            # ---- 3. the setup cost vs the intercept offset ---------------- #
            # The catch's hover move: calibrated pre-pose -> hover(y). Time it
            # in physics ticks (the real move_to controller, same max_step).
            arm.hold_quaternion = hold
            previous_max_step = arm.max_step
            arm.max_step = HOVER_STEP
            for dy in Y_LADDER:
                y = cfg.pick_y + dy
                arm.teleport_joints(seed)
                arm.set_gripper(arm.OPEN)
                app_utils.update_app(steps=20)
                hover_target = (cfg.pick_x, y, belt_top + Z_GRIP + HOVER)
                target_tcp = arm.tcp_target_for_jaw(np.asarray(hover_target, float))
                ticks = 0
                residual = float("inf")
                for _ in range(600):
                    residual = arm.ik_step(target_tcp)
                    SimulationManager.step(steps=1)
                    ticks += 1
                    if residual <= 0.008:
                        break
                jaw_now = np.asarray(arm.jaw_centre(), dtype=float)
                tcp = np.asarray(arm.tcp_position(), dtype=float)
                d_desc = float(np.linalg.norm(arm.tcp_target_for_jaw(np.asarray(
                    (cfg.pick_x, y, belt_top + Z_GRIP), float)) - tcp))
                say(
                    f"[reach] {side:5s} setup dy={dy:+.2f}: hover_move={ticks} ticks "
                    f"({ticks * DT:.2f}s) res={residual * 1000:.1f}mm "
                    f"jaw_dy={float(jaw_now[1]) - y:+.4f} "
                    f"descent_est={descent_ticks(d_desc)} ticks "
                    f"({descent_ticks(d_desc) * DT:.2f}s, d={d_desc:.3f}m)"
                )
            arm.max_step = previous_max_step
        arm.hold_quaternion = None
        app_utils.update_app(steps=30)

    # ---- summary: the reachable map -------------------------------------- #
    say("[reach] ---- grip map (residual <= tol = clean) ----")
    for side in SIDES:
        say(f"[reach] {side}: x -> clean dy range at grip (tol {TOL * 1000:.0f} mm)")
        for x in X_LADDER:
            clean = [
                r["dy"]
                for r in rows
                if r["side"] == side and abs(r["x"] - x) < 1e-9
                and r["grip_residual"] <= TOL
            ]
            if clean:
                say(
                    f"[reach]   {side:5s} x={x:.2f}: clean dy {min(clean):+.2f}..{max(clean):+.2f} "
                    f"({len(clean)}/{len(Y_LADDER)})"
                )
            else:
                say(f"[reach]   {side:5s} x={x:.2f}: none clean")
        clean_sweep = [
            (r["dy"], r["x"])
            for r in rows
            if r["side"] == side and r["sweep_residual"] == r["sweep_residual"]
            and r["sweep_residual"] <= TOL
        ]
        n_clean = sum(
            1 for r in rows if r["side"] == side and r["grip_residual"] <= TOL
        )
        say(
            f"[reach] {side}: clean grips {n_clean}/"
            f"{sum(1 for r in rows if r['side'] == side)}; "
            f"sweep-end (dy-{SWEEP:.2f}) clean points {len(clean_sweep)}"
        )
    out = os.environ.get("FRUIT_REACH_JSON", "logs/r10/reach_intercept.json")
    if out:
        if len(SIDES) == 1:
            root, ext = os.path.splitext(out)
            out = f"{root}_{SIDES[0]}{ext}"
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=1)
        say(f"[reach] raw rows -> {out}")
    say("[reach] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
