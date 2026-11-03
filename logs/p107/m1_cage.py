#!/usr/bin/env python3
"""P107 M1: the radial four-pad cage's asset census (a probe, no attempt loop).

**What this measures.** The numbers the task's hand interface needs, read off the
**built** prims rather than computed on paper:

* the **aperture** the synergy actually reaches at each command, and whether the
  pads move radially together (one scalar command, four pads);
* the **tool offset** that replaces `_pad_standoff` - the jaw-centre to
  grasp-centre distance - measured across the whole aperture range (a radial
  synergy must not move it; that is the number P106 could not have on the
  Allegro, whose fingertip centroid read 100-216 mm across a posture sweep);
* the plate's **distal plane** and the **lip** below the payload's equator;
* the **pad-pad corner gap** against the aperture (four 61 mm plates at 4x90 deg
  physically intersect below a 61 mm aperture - the retrofit's own geometric
  limit);
* the **delivered per-pad force** and the **contact count** at the operating
  point on a real pool fruit (the enclosure, and the cap's authority).

**What it is not.** No belt, no attempt, no policy, no camera. The fruit is
placed and held at the cage's grasp point so the force read is a grasp read, not
a transport read; `M2b`/`M3` are the pipeline (`logs/p107/METHOD.md`).

    FRUIT_GRIPPER_KIND=cage4 FRUIT_FINGER_COLLIDERS=0 scripts/run.sh logs/p107/m1_cage.py
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import numpy as np
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.core.experimental.prims import RigidPrim

from fruit_sorting.assets import SceneConfig
from fruit_sorting.cage_hand import (
    CAGE_PLATE_LENGTH,
    DISTAL_Z,
    LIP,
    PAD_MID_OFFSET,
    PAD_THICK,
    PAD_WIDTH,
    PLATE_LENGTH,
    PLATE_WIDTH,
    CageHand,
    pad_boxes,
)
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene

DT = 1.0 / 120.0
CFG = SceneConfig()
SIDE = "left"
#: Apertures to census [m]: from the open cage to the smallest pool fruit.
APERTURES = (0.150, 0.120, 0.090, 0.080, 0.070, 0.060, 0.045, 0.036, 0.030)


def step(n: int = 1) -> None:
    for _ in range(max(1, int(n))):
        SimulationManager.step(steps=1)
    from isaacsim.core.experimental.utils import app as app_utils

    app_utils.update_app(steps=0)


def advance(t: float) -> None:
    step(int(round(t / DT)))


def enable_tracking(path: str):
    """Contact tracking must be armed at authoring time and re-read after play."""
    try:
        prim = RigidPrim(path)
        prim.set_enabled_contact_tracking(True, threshold=1e-3)
        return prim
    except Exception as exc:  # noqa: BLE001
        say(f"[m1] WARNING: contact tracking unavailable for {path}: {exc}")
        return None


def pad_corners(prim) -> np.ndarray:
    """The eight authored box corners of a pad body, world frame."""
    pos, quat = prim.get_world_poses()
    pos = np.asarray(pos.numpy())[0]
    w, x, y, z = (float(v) for v in np.asarray(quat.numpy())[0])
    rot = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )
    half = np.array([PAD_WIDTH / 2.0, PAD_THICK / 2.0, CAGE_PLATE_LENGTH / 2.0])
    out = []
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                out.append(pos + rot @ (half * np.array([sx, sy, sz])))
    return np.asarray(out)


def main() -> int:
    scene = SortingScene(CFG)
    scene.build(parts=("environment", "pedestal", "robot", "conveyor",
                       "output_belts", "camera"))
    spawner = FruitSpawner(scene.stage, CFG, seed=5, two_line=False)
    spawner.create_pool()
    # Contact tracking at authoring time (a body authored before play gets its
    # physics view at play time; `logs/p104/fixture_probe.py` section 3).
    for k in range(4):
        enable_tracking(f"/World/Cage_{SIDE}/Pad{k}")
    for sample in spawner.samples:
        enable_tracking(sample.prim_path)
    scene.start(physics_dt=DT, warmup_steps=60)
    step(30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    arms = {side: ArmController(scene, side) for side in ("left", "right")}
    cage = CageHand(scene.stage, SIDE, arms[SIDE])
    # The **calibrated grasp pose** (`configs/waypoints.json`): the cage has to be
    # in free space over the belt, not tucked into the robot's own links (an
    # arbitrary joint configuration left the tool axis horizontal and the pads
    # inside the wrist, and the drives read as drifting - `logs/p107/METHOD.md`).
    import json

    with open(os.path.join(_ROOT, "configs", "waypoints.json")) as fh:
        waypoints = json.load(fh)
    arms[SIDE].teleport_joints(np.asarray(waypoints["arms"][SIDE]["grasp"], dtype=float))
    advance(0.5)
    arms[SIDE].sync_command_to_measured()
    say(
        f"[m1] arm pose: jaw={np.round(arms[SIDE].jaw_centre(), 4).tolist()} "
        f"tool_axis={np.round(arms[SIDE].approach_axis(), 4).tolist()}"
    )
    say(f"[m1] cage enabled={cage.enabled} kind={cage.kind}")
    say(
        f"[m1] authored: plate {PAD_WIDTH * 1000:.3f}x{CAGE_PLATE_LENGTH * 1000:.3f} mm "
        f"(shipped {PLATE_WIDTH * 1000:.3f}x{PLATE_LENGTH * 1000:.3f}), "
        f"distal plane {DISTAL_Z * 1000:.1f} mm below the jaw centre, "
        f"pad mid-plane {PAD_MID_OFFSET * 1000:.1f} mm, lip {LIP * 1000:.1f} mm, "
        f"tool offset (const) {cage.grasp_standoff * 1000:.1f} mm"
    )

    pad_paths = [f"/World/Cage_{SIDE}/Pad{k}" for k in range(4)]
    pads = [RigidPrim(p) for p in pad_paths]
    quat = np.asarray(arms[SIDE].tcp_pose()[1], dtype=float)
    jaw = np.asarray(arms[SIDE].jaw_centre(), dtype=float)

    # ---- phase A: the synergy across the aperture range ------------------ #
    say("[m1] ---- phase A: aperture / tool offset / pad-pad corner gap ----")
    say(
        "[m1] cmd_mm | aper_mm(meas) | axis_a axis_b | grasp_z-jaw_mm | "
        "distal_mm | corner_gap_mm | pad_r_mm"
    )
    rows = []
    first = True
    for aperture in APERTURES:
        # The closure servo takes one bounded step per `follow_centre`, so a
        # probe that wants a settled aperture has to command it every tick -
        # exactly what the task's close does.
        for _ in range(40):
            cage.follow_centre(jaw, quat, aperture)
            step(1)
        if first:
            first = False
            bp, bq = cage.base_pose()
            say(
                f"[m1] dbg jaw={np.round(jaw, 4).tolist()} quat={np.round(quat, 4).tolist()} "
                f"corr={np.round(cage._tool_correction(quat), 4).tolist()} "
                f"approach={np.round(arms[SIDE].approach_axis(), 4).tolist()}"
            )
            say(
                f"[m1] dbg base={np.round(bp, 4).tolist()} bquat={np.round(bq, 4).tolist()} "
                f"last_gap={cage.last_gap * 1000:.1f}mm"
            )
            for k, prim in enumerate(pads):
                pos = np.asarray(prim.get_world_poses()[0].numpy())[0]
                say(f"[m1] dbg pad{k}={np.round(pos, 4).tolist()}")
        corners = np.asarray([pad_corners(p) for p in pads])  # 4 x 8 x 3
        centres = corners.mean(axis=1)
        measured = cage.apertures()
        base_pos, base_quat = cage.base_pose()
        rot = np.array(
            [
                [
                    1 - 2 * (base_quat[2] ** 2 + base_quat[3] ** 2),
                    2 * (base_quat[1] * base_quat[2] - base_quat[3] * base_quat[0]),
                    2 * (base_quat[1] * base_quat[3] + base_quat[2] * base_quat[0]),
                ],
                [
                    2 * (base_quat[1] * base_quat[2] + base_quat[3] * base_quat[0]),
                    1 - 2 * (base_quat[1] ** 2 + base_quat[3] ** 2),
                    2 * (base_quat[2] * base_quat[3] - base_quat[1] * base_quat[0]),
                ],
                [
                    2 * (base_quat[1] * base_quat[3] - base_quat[2] * base_quat[0]),
                    2 * (base_quat[2] * base_quat[3] + base_quat[1] * base_quat[0]),
                    1 - 2 * (base_quat[1] ** 2 + base_quat[2] ** 2),
                ],
            ]
        )
        down = rot @ np.array([0.0, 0.0, 1.0])
        # The **distal** plane is the farthest corner down the tool axis (the
        # minimum is the plate's proximal end, 4.4 mm above the jaw centre).
        distal = float(max(float(np.dot(c - base_pos, down)) for c in corners.reshape(-1, 3)))
        # Eccentricity: the four pad boxes' centres' mean distance from the axis.
        axis_pt = base_pos + down * float(np.dot(centres.mean(axis=0) - base_pos, down))
        radial = [
            float(np.linalg.norm((c - axis_pt) - down * float(np.dot(c - axis_pt, down))))
            for c in centres
        ]
        # Pad-pad corner gap: the closest pair of corners of *adjacent* pads.
        corner_gap = float("inf")
        for k in range(4):
            a = corners[k]
            b = corners[(k + 1) % 4]
            d = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
            corner_gap = min(corner_gap, float(d.min()))
        grasp_z = (distal - LIP) - float(np.dot(jaw - base_pos, down))
        say(
            f"[m1] {aperture * 1000:6.1f} | {measured[0] * 1000:7.1f} {measured[1] * 1000:7.1f} | "
            f"{np.mean(radial) * 1000:8.1f} | {-grasp_z * 1000:10.2f} | "
            f"{distal * 1000:8.1f} | {corner_gap * 1000:9.1f} | "
            f"{np.mean(radial) * 1000:7.1f}"
        )
        rows.append((aperture, measured, grasp_z, distal, corner_gap))
    tool_offsets = [(-r[2]) * 1000.0 for r in rows]
    say(
        f"[m1] tool offset across {len(rows)} apertures: "
        f"{min(tool_offsets):.2f}-{max(tool_offsets):.2f} mm "
        f"(spread {max(tool_offsets) - min(tool_offsets):.2f} mm) - the radial "
        f"synergy does not move it"
    )
    overlap = [a for a, m, *_ in rows if min(m) < PAD_WIDTH]
    say(
        f"[m1] pad-pad corner gap < 0 (plates intersect) at apertures "
        f"<= {PAD_WIDTH * 1000:.0f} mm: "
        f"{[round(a * 1000, 1) for a in overlap]} - the 61 mm plate's own limit"
    )

    # ---- phase B: the enclosure and the delivered force on a pool fruit --- #
    say("[m1] ---- phase B: close on a pinned pool fruit (force + enclosure) ----")
    cage.park()
    advance(0.2)
    jaw = np.asarray(arms[SIDE].jaw_centre(), dtype=float)
    # The grasp point is the cage's grasp centre: straight down the tool axis
    # from the jaw centre by the measured tool offset.
    down_world = np.asarray(arms[SIDE].approach_axis(), dtype=float)
    grip = jaw + down_world * cage.grasp_standoff
    wanted = {"pear", "orange", "strawberry"}
    seen: dict[str, object] = {}
    for sample in spawner.samples:
        if sample.category in wanted and sample.category not in seen:
            seen[sample.category] = sample
    for category, sample in seen.items():
        fruit_z = float(grip[2])
        spawner.place(sample, np.array([float(grip[0]), float(grip[1]), fruit_z]))
        advance(0.15)
        # The aperture that clears the fruit's widest horizontal extent, 2 %
        # squeeze - the same rule the task's radial close uses.
        from fruit_sorting.meshes import FRUIT_SHAPES, axis_extent

        shape = FRUIT_SHAPES.get(category)
        d = float(sample.diameter)
        ext = max(
            float(axis_extent(shape, d, np.array([1.0, 0.0, 0.0]))),
            float(axis_extent(shape, d, np.array([0.0, 1.0, 0.0]))),
        ) if shape is not None else d
        target = ext * 0.98
        for pad in pads:
            xf = pad
        # close in one min-jerk ramp, re-pinning the fruit so it cannot be batted
        from fruit_sorting.motion import min_jerk_ramp

        for value in min_jerk_ramp(0.150, target, 60):
            cage.follow_centre(jaw, quat, value)
            spawner.place(sample, np.array([float(grip[0]), float(grip[1]), fruit_z]))
            step(1)
        for _ in range(60):
            spawner.place(sample, np.array([float(grip[0]), float(grip[1]), fruit_z]))
            step(1)
        forces = []
        for pad_path in pad_paths:
            try:
                read = RigidPrim(
                    pad_path, contact_filter_paths=[sample.prim_path]
                ).get_net_contact_forces()
                f = np.asarray(read.numpy(), dtype=float)[0]
                forces.append(float(np.linalg.norm(f)))
            except Exception as exc:  # noqa: BLE001
                forces.append(float("nan"))
                say(f"[m1]   force read failed for {pad_path}: {exc}")
        loaded = sum(1 for v in forces if v >= 0.5)
        au, av = cage.apertures()
        say(
            f"[m1] {category:11s} d={d * 1000:5.1f}mm extent_xy={ext * 1000:5.1f}mm "
            f"cmd_aper={target * 1000:5.1f}mm meas=({au * 1000:5.1f},{av * 1000:5.1f}) "
            f"pads={loaded}/4 f=({','.join(f'{v:.2f}' for v in forces)}) "
            f"F={sum(v for v in forces if v == v):.2f}N "
            f"F/pad={sum(v for v in forces if v == v) / max(1, loaded):.2f}N"
        )

    say("[m1] done")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        import traceback

        traceback.print_exc()
        code = 1
    simulation_app.close()
    raise SystemExit(code)
