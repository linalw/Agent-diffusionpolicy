#!/usr/bin/env python3
"""P143 A: is the fruit more visible from a **side** camera than from the top?

Builds the shipped scene, seats one fruit at the pick station, drives the arm to the
grasp pose with the primitive's own per-tick `ik_step`, and renders four cameras with
**depth** at that instant:

* `head` - the policy's camera (shipped pose),
* `side_x` - downstream of the station, looking back along -x,
* `side_y` - from the +Y side, looking across the belt,
* `oblique` - the +x/+y pose the recorder uses for `gripper.mp4`.

For each camera the same z-test as `occlusion.py`: project the fruit's centre, read
the depth there, compare with the fruit's own distance. The depth at the centre pixel
is the fruit's surface, so "occluded" is `z - depth > radius + 20 mm`.

    scripts/run.sh logs/p143/side_probe.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from isaacsim import SimulationApp

HEADLESS = os.environ.get("HEADLESS", "1") == "1"
from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()
simulation_app = SimulationApp({"headless": HEADLESS, "width": 1280, "height": 720})

import numpy as np  # noqa: E402

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
from isaacsim.core.rendering_manager import RenderingManager  # noqa: E402
from isaacsim.core.simulation_manager import SimulationManager  # noqa: E402
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera  # noqa: E402
from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.common import (  # noqa: E402
    install_failure_handler,
    look_at_quat,
    say,
    to_numpy,
)
from fruit_sorting.fruits import FruitSpawner  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402
from fruit_sorting.tactile import GripperTactile  # noqa: E402
from fruit_sorting.tasks import PickAndPlaceTask  # noqa: E402

install_failure_handler("side_probe")
DT = 1.0 / 120.0
W, H = 424, 240
FOCAL, APERTURE = 0.016, (0.036, 0.02025)

CAMS = {
    "head": ((0.05, 0.0, 2.00), (0.34, 0.22, 1.10)),
    "side_x": ((1.45, 0.10, 1.55), (0.30, 0.02, 1.18)),
    "side_y": ((0.34, 1.35, 1.55), (0.34, 0.00, 1.18)),
    "oblique": ((0.93, 0.62, 1.42), (0.34, 0.0, 1.19)),
}


def quat_matrix(q) -> np.ndarray:
    w, x, y, z = [float(v) for v in q]
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()
    # The recorder's own order: scene -> tactile -> start -> spawner -> pool.
    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()
    spawner = FruitSpawner(scene.stage, cfg, seed=3, two_line=False)
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    spawner.prime(count=4)
    task = PickAndPlaceTask(scene, spawner, tactile, cfg)
    task.go_ready()
    app_utils.update_app(steps=10)

    sample = next(s for s in spawner.active if not s.parked)
    # Seat it at the station, the way the primitive does before a grasp.
    belt_top = float(scene.belt.belt_top)
    rest = np.asarray([cfg.pick_x, cfg.pick_y, belt_top + sample.diameter / 2.0])
    spawner.place(sample, rest)
    for _ in range(30):
        SimulationManager.step(steps=1)
    say(f"[probe] fruit {sample.category} d={sample.diameter * 100:.1f} cm at "
        f"{np.round(rest, 3).tolist()}")

    cameras = {}
    for name, (eye, target) in CAMS.items():
        cam = RtxCamera(
            f"/World/Probe_{name}",
            tick_rate=0.0,
            positions=[eye],
            orientations=[look_at_quat(eye, target)],
        )
        cam.camera.set_focal_lengths(FOCAL)
        cam.camera.set_apertures(APERTURE)
        cam.camera.set_clipping_ranges(0.01, 50.0)
        cameras[name] = (eye, target, CameraSensor(
            cam, resolution=(W, H), annotators=["rgb", "distance_to_image_plane"]
        ))
    app_utils.update_app(steps=4)

    def measure(tag: str) -> None:
        fruit = np.asarray(spawner.position(sample), dtype=float)
        radius_mm = sample.diameter * 500.0
        for name, (eye, target, sensor) in cameras.items():
            RenderingManager.render()
            raw = sensor.get_data("distance_to_image_plane")
            depth = to_numpy(raw)
            if depth is None:
                say(f"[probe] {tag} {name}: no depth")
                continue
            depth = np.asarray(depth)
            if depth.ndim == 4:  # (batch, H, W, 1)
                depth = depth[0]
            if depth.ndim == 3:  # (H, W, 1)
                depth = depth[..., 0]
            if depth.shape[:2] == (W, H):  # the sensor hands back (width, height)
                depth = depth.T
            if depth.shape[:2] != (H, W):
                say(f"[probe] {tag} {name}: depth shape {depth.shape} != {(H, W)}")
                continue
            eye = np.asarray(eye, dtype=float)
            rot = quat_matrix(look_at_quat(eye, np.asarray(target, dtype=float)))
            forward, right, up = -rot[:, 2], rot[:, 0], rot[:, 1]
            d = fruit - eye
            z = float(d @ forward)
            f_px = FOCAL / (APERTURE[0] / 2.0) * (W / 2.0)
            u = int(round(W / 2 + (float(d @ right) / z) * f_px))
            v = int(round(H / 2 - (float(d @ up) / z) * f_px))
            inside = 1 <= u < W - 1 and 1 <= v < H - 1
            near = float(np.nanmin(depth[v - 1 : v + 2, u - 1 : u + 2])) if inside else float("nan")
            short = (z - near) * 1000.0 if np.isfinite(near) else float("nan")
            occluded = bool(np.isfinite(short) and short > radius_mm + 20.0)
            say(
                f"[probe] {tag:6s} {name:8s} px=({u:3d},{v:3d}) inside={int(inside)} "
                f"z={z * 1000:6.0f}mm depth={near * 1000:6.0f}mm "
                f"short={short:7.1f}mm r={radius_mm:4.1f} "
                f"-> {'OCCLUDED' if occluded else 'visible'}"
            )

    measure("ready")
    # Drive the jaws onto the fruit with the primitive's own per-tick IK step.
    arm = task.arms["left"]
    grip = np.asarray(spawner.position(sample), dtype=float) + np.array([0.0, 0.0, 0.070])
    arm.hold_quaternion = None
    for _ in range(260):
        arm.ik_step(arm.tcp_target_for_jaw(grip))
        SimulationManager.step(steps=1)
    err = float(np.linalg.norm(np.asarray(arm.jaw_centre(), dtype=float) - grip))
    say(f"[probe] at the grasp pose: jaw err {err * 1000:.0f} mm")
    measure("grasp")
    say("DONE")
    app_utils.pause()
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
