"""v3 layout probe: clearances, output-belt transport and place reach.

    scripts/run.sh scripts/422_v3_layout_probe.py

The v3 layout replaces the output bins with two raised output conveyors. Three
questions decide whether it is sound, and none of them should be answered by
reading the code:

1. **Do the clearances hold?** The output belts run *above* the main belt, so
   their underside has to clear the main belt top and the tallest fruit on it,
   and their frames have to clear the robot pedestal, the main belt and the
   camera mast. The static numbers come from `SceneConfig`; this prints them.
2. **Does the raised belt actually carry fruit?** Same measurement as
   `scripts/170_transport_probe.py` does for the main belt: put fruit on each
   output belt and read their speed against the commanded one, plus the spin
   ratio (`|omega|*r / |v|`; 1.0 = rolling, 0 = sliding).
3. **Can each arm reach the release point above its own belt, and does the arm
   stay clear of the belt at the pick pose?** The release point is deliberately
   *not* the belt centre: the measured TCP reach is 0.678 m from the shoulder
   (`logs/12_reach.log`) and the centre at (0.65, +-0.55) is 0.79 m away. This
   solves the IK for a ladder of candidate points and reports the residual, then
   measures the smallest world-space gap between any arm link and the belt
   surface at the pick pose.

`FRUIT_PLACE_CANDIDATES` overrides the ladder, e.g.
``FRUIT_PLACE_CANDIDATES="0.65,0.55;0.43,0.55"`` (x,y;...).
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
from pxr import Usd, UsdGeom

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.simulation_manager import SimulationManager

DT = 1.0 / 120.0


def report_clearances(cfg: SceneConfig) -> None:
    """Static clearances of the raised output line (metres)."""
    main_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    underside = cfg.output_belt_top_z - cfg.output_belt_size[2]
    tallest = max(hi for _, hi in cfg.fruit_dimensions.values())
    pedal_x0 = cfg.pedestal_center_xy[0] - cfg.pedestal_size[0] / 2.0
    pedal_x1 = cfg.pedestal_center_xy[0] + cfg.pedestal_size[0] / 2.0
    pedal_y1 = abs(cfg.pedestal_center_xy[1]) + cfg.pedestal_size[1] / 2.0
    belt_x0 = cfg.belt_center[0] - cfg.belt_size[0] / 2.0
    belt_x1 = cfg.belt_center[0] + cfg.belt_size[0] / 2.0
    cx = cfg.output_belt_center_x
    half_l = cfg.output_belt_size[0] / 2.0
    half_w = cfg.output_belt_size[1] / 2.0
    leg_x = (cfg.output_belt_inner_leg_x, cfg.output_belt_outer_leg_x)
    leg_half = cfg.output_belt_leg_size / 2.0
    leg_y = cfg.output_belt_y - (half_w - 0.03)
    rail_outer = (
        cfg.belt_center[0] - cfg.belt_size[0] / 2.0 - cfg.main_frame_rail_offset
    ) - cfg.main_frame_rail_width / 2.0
    chute_top = cfg.output_chute_top
    chute_bottom = cfg.output_chute_bottom
    mast_x = cfg.head_camera_forward - 0.12  # scene.py: mast 3 cm wide, 12 cm behind the lens
    say("[audit] ---- v3 output-line clearances ----")
    say(
        f"[audit] output belt: centre=({cx:.3f},+-{cfg.output_belt_y:.3f}), "
        f"top={cfg.output_belt_top_z:.3f}, size={cfg.output_belt_size}, "
        f"speed={cfg.output_belt_speed:+.3f} m/s along +X"
    )
    say(
        f"[audit] underside z={underside:.3f} vs main belt top {main_top:.3f}: "
        f"clear {underside - main_top:+.3f} m"
    )
    say(
        f"[audit] underside vs tallest fruit on the main belt "
        f"({tallest * 100:.0f} cm -> z={main_top + tallest:.3f}): "
        f"clear {underside - (main_top + tallest):+.3f} m"
    )
    say(
        f"[audit] belt body x=[{cx - half_l:.3f},{cx + half_l:.3f}] vs camera mast "
        f"x=[{mast_x - 0.015:.3f},{mast_x + 0.015:.3f}]: clear "
        f"{(cx - half_l) - (mast_x + 0.015):+.3f} m in x"
    )
    say(
        f"[audit] inner edge y={cfg.output_belt_y - half_w:.3f} vs pedestal "
        f"y<= {pedal_y1:.3f}: clear {(cfg.output_belt_y - half_w) - pedal_y1:+.3f} m; "
        f"legs at y>={leg_y - 0.025:.3f}: clear {(leg_y - 0.025) - pedal_y1:+.3f} m"
    )
    say(
        f"[audit] inner legs x=[{leg_x[0] - leg_half:.4f},{leg_x[0] + leg_half:.4f}] vs main "
        f"belt frame rail outer face x={rail_outer:.4f}: clear "
        f"{(rail_outer - (leg_x[0] + leg_half)) * 1000:+.1f} mm; vs slab edge x={belt_x0:.3f}: "
        f"clear {belt_x0 - (leg_x[0] + leg_half):+.3f} m; outer legs "
        f"x=[{leg_x[1] - leg_half:.3f},{leg_x[1] + leg_half:.3f}] beyond the main belt "
        f"x<={belt_x1:.3f} and clear of the discharge (x>={cfg.output_belt_end_x:.3f})"
    )
    say(
        f"[audit] discharge chute {cfg.output_chute_angle_deg:.0f} deg from "
        f"({chute_top[0]:.3f},{chute_top[1]:.3f}) to ({chute_bottom[0]:.3f},{chute_bottom[1]:.3f}); "
        f"tray {cfg.output_tray_size[0]:.2f}x{cfg.output_tray_size[1]:.2f} m centre "
        f"x={cfg.output_tray_center_x:.2f}, floor z={cfg.output_tray_floor_top_z:.2f}, rim "
        f"z={cfg.output_tray_floor_top_z + cfg.output_tray_wall_height:.2f}"
    )
    say(
        f"[audit] pick point ({cfg.pick_x:.2f},{cfg.pick_y:.2f}) is {cfg.output_belt_y - half_w:.3f} m "
        f"in y from the nearest belt surface; release at "
        f"({cfg.output_place_x:.2f},+-{cfg.output_place_y:.2f},{cfg.output_place_z:.3f})"
    )


def belt_aabb(cfg: SceneConfig, sign: float):
    half_l = cfg.output_belt_size[0] / 2.0
    half_w = cfg.output_belt_size[1] / 2.0
    half_t = cfg.output_belt_size[2] / 2.0
    cx = cfg.output_belt_center_x
    cy = sign * cfg.output_belt_y
    cz = cfg.output_belt_top_z - half_t
    return (
        np.array([cx - half_l, cy - half_w, cz - half_t]),
        np.array([cx + half_l, cy + half_w, cz + half_t]),
    )


def aabb_gap(a, b) -> float:
    lo = np.maximum(np.maximum(a[0] - b[1], b[0] - a[1]), 0.0)
    return float(np.linalg.norm(lo))


def min_link_gap(scene, arm, cfg, sign: float, names=None) -> tuple[float, str]:
    """Smallest bbox gap between any arm link and one output belt body."""
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    target = belt_aabb(cfg, sign)
    best = (float("inf"), "")
    paths = arm.robot.link_paths
    if paths and isinstance(paths[0], (list, tuple)):
        paths = paths[0]
    for index, name in enumerate(arm.robot.link_names):
        if names is not None and name not in names:
            continue
        if f"_{arm.spec.side}_" not in name:
            continue
        path = paths[index]
        if isinstance(path, (list, tuple)):
            path = path[0]
        prim = scene.stage.GetPrimAtPath(str(path))
        if not prim.IsValid():
            continue
        rng = cache.ComputeWorldBound(prim).ComputeAlignedRange()
        box = (
            np.asarray(rng.GetMin(), dtype=float),
            np.asarray(rng.GetMax(), dtype=float),
        )
        gap = aabb_gap(box, target)
        if gap < best[0]:
            best = (gap, name)
    return best


def main() -> int:
    cfg = SceneConfig()
    report_clearances(cfg)
    scene = SortingScene(cfg).build(
        parts=("environment", "pedestal", "robot", "conveyor", "output_belts")
    )
    scene.start(physics_dt=DT, warmup_steps=60)
    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    for _ in range(30):
        SimulationManager.step(steps=1)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()

    # ---------------------------------------------------------------- #
    # 2. Transport on the raised belts.
    # ---------------------------------------------------------------- #
    say("[transport] ---- does the raised belt carry fruit? ----")
    samples = sorted(spawner.samples, key=lambda s: float(s.diameter))
    for index, sign in ((0, 1.0), (1, -1.0)):
        sample = samples[(0 if index == 0 else 5) % len(samples)]
        x0, _ = belt_aabb(cfg, sign)
        start = np.array([x0[0] + 0.15, sign * cfg.output_belt_y,
                          cfg.output_belt_top_z + sample.diameter / 2.0 + 0.01])
        spawner.place(sample, start)
        for _ in range(20):
            SimulationManager.step(steps=1)
        speeds: list[float] = []
        spins: list[float] = []
        velocities: list[float] = []
        for tick in range(int(3.0 / DT)):
            SimulationManager.step(steps=1)
            vel = np.asarray(spawner.velocity(sample), dtype=float)[:3]
            angular = np.asarray(spawner.angular(sample), dtype=float)[:3]
            speeds.append(float(np.linalg.norm(vel)))
            velocities.append(float(vel[0]))
            spins.append(float(np.linalg.norm(angular)) * float(sample.diameter) / 2.0)
        command = abs(float(cfg.output_belt_speed))
        med_vx = float(np.median(velocities))
        med_speed = float(np.median(speeds))
        med_spin = float(np.median(spins))
        final = np.asarray(spawner.position(sample), dtype=float)
        ratio = med_vx / max(command, 1e-6)
        roll = med_spin / max(med_speed, 1e-6)
        say(
            f"[transport] belt{index} ({'P' if sign > 0 else 'N'}): "
            f"{sample.category} d={sample.diameter * 100:.1f}cm placed at x={start[0]:.3f} "
            f"-> x={final[0]:.3f} | median vx={med_vx:+.4f} m/s vs commanded "
            f"{command:+.3f} ({ratio:.2f}x), spin |omega|*r={med_spin:.4f} "
            f"-> roll ratio {roll:.2f} (0 = sliding, 1 = rolling)"
        )
        spawner.park(sample)
        for _ in range(10):
            SimulationManager.step(steps=1)

    # ---------------------------------------------------------------- #
    # 3. Place reach per arm, and arm clearance at the pick pose.
    # ---------------------------------------------------------------- #
    with open(os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json"), encoding="utf-8") as fh:
        waypoints = json.load(fh)
    ladder_env = os.environ.get("FRUIT_PLACE_CANDIDATES", "")
    if ladder_env:
        ladder = [
            tuple(float(v) for v in item.split(","))
            for item in ladder_env.split(";")
            if item.strip()
        ]
    else:
        ladder = [
            (cfg.output_belt_center_x, cfg.output_belt_y),
            (0.55, cfg.output_belt_y),
            (0.50, cfg.output_belt_y),
            (cfg.output_place_x, cfg.output_belt_y),
            (cfg.output_place_x, cfg.output_belt_y - 0.05),
            (0.34, cfg.output_belt_y),
        ]
    say("[reach] ---- place-point reach (position-only IK, as the carry uses) ----")
    for side, sign in (("left", 1.0), ("right", -1.0)):
        arm = ArmController(scene, side)
        arm.teleport_joints(np.asarray(waypoints["arms"][side]["grasp"], dtype=float))
        for _ in range(30):
            SimulationManager.step(steps=1)
        for x, y in ladder:
            target = np.array([x, sign * y, cfg.output_place_z])
            arm.teleport_joints(np.asarray(waypoints["arms"][side]["grasp"], dtype=float))
            config, residual = arm.solve_to(
                target, iterations=900, tolerance=0.008, restarts=4, seed=7
            )
            gap, link = min_link_gap(scene, arm, cfg, sign)
            say(
                f"[reach] {side:5s} target=({x:.2f},{sign * y:+.2f},{cfg.output_place_z:.2f}) "
                f"residual={residual * 1000:6.1f}mm jaw={np.round(arm.jaw_centre(), 3).tolist()} "
                f"link[{link}] to belt body {gap * 1000:6.1f}mm"
            )
        # Pick-pose clearance towards the belt on this arm's side.
        arm.teleport_joints(np.asarray(waypoints["arms"][side]["grasp"], dtype=float))
        for _ in range(30):
            SimulationManager.step(steps=1)
        gap, link = min_link_gap(scene, arm, cfg, sign)
        say(
            f"[reach] {side:5s} at the calibrate grasp pose: nearest link [{link}] to the "
            f"belt body is {gap * 1000:.0f} mm clear"
        )

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
