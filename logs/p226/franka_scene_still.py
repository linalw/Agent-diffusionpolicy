#!/usr/bin/env python3
"""P227: a still of the single-arm cell (Franka + belt + side bins), no policy.

    FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 FRUIT_FRANKA_BASE_Z=0.79 \
        scripts/run.sh logs/p226/franka_scene_still.py /tmp/opencode/franka

Builds the scene parts only (robot + conveyor + bins + camera), renders a plan
view and the observer pose, and prints the shoulder-to-pick / shoulder-to-bin
distances so the layout is readable from the log.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 1280, "height": 720})

import numpy as np  # noqa: E402

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
from isaacsim.core.rendering_manager import RenderingManager  # noqa: E402
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera  # noqa: E402
from isaacsim.core.experimental.prims import Articulation, RigidPrim  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.common import look_at_quat, say, to_numpy  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402

PREFIX = sys.argv[1] if len(sys.argv) > 1 else "/tmp/opencode/franka"


def frame_of(sensor):
    data = to_numpy(sensor.get_data("rgb"))
    if data is None:
        return None
    arr = np.asarray(data)
    if arr.ndim == 4:
        arr = arr[0]
    if arr.ndim < 3 or arr.shape[-1] not in (3, 4):
        return None
    if arr.shape[-1] == 4:
        arr = arr[..., :3]
    return np.ascontiguousarray(arr.astype(np.uint8))


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(
        parts=("environment", "pedestal", "robot", "conveyor", "output_belts")
    )
    app_utils.update_app(steps=60)
    robot = Articulation("/World/OpenArm")
    links = list(robot.link_names)
    paths = robot.link_paths
    if paths and isinstance(paths[0], (list, tuple)):
        paths = paths[0]

    def pos(name):
        i = links.index(name)
        p = paths[i]
        if isinstance(p, (list, tuple)):
            p = p[0]
        wp, _ = RigidPrim(str(p)).get_world_poses()
        return np.asarray(wp.numpy())[0]

    try:
        hand = pos("panda_hand")
        lf = pos("panda_leftfinger")
        rf = pos("panda_rightfinger")
        say(
            f"[franka] hand=({hand[0]:+.3f},{hand[1]:+.3f},{hand[2]:.3f}) "
            f"finger_mid=({0.5*(lf[0]+rf[0]):+.3f},"
            f"{0.5*(lf[1]+rf[1]):+.3f},{0.5*(lf[2]+rf[2]):.3f})"
        )
        shoulder = pos("panda_link1")
        for label, p in (
            ("pick", (cfg.pick_x, cfg.pick_y, cfg.belt_top + 0.03)),
            ("binP", (cfg.bin_center_x, cfg.bin_center_y, cfg.bin_floor_top_z + 0.10)),
            ("binN", (cfg.bin_center_x, -cfg.bin_center_y, cfg.bin_floor_top_z + 0.10)),
        ):
            d = float(np.linalg.norm(np.asarray(p, dtype=float) - shoulder))
            say(f"[franka] shoulder->{label}={d:.3f} m  target={p}")
        if cfg.output_bins:
            say(
                f"[franka] bins x={cfg.bin_center_x:+.2f} |y|={cfg.bin_center_y:.2f} "
                f"floor={cfg.bin_floor_top_z:.2f} rim={cfg.bin_floor_top_z + cfg.bin_wall_height:.2f}"
            )
        say(f"[franka] belt x={cfg.belt_center[0]:.2f} top={cfg.belt_top:.3f}")
    except Exception as exc:  # noqa: BLE001
        say(f"[franka] geometry read failed: {exc}")

    views = {
        "plan": ((0.02, 0.0, 3.30), (0.12, 0.0, 1.00)),
        "obs": ((1.75, 1.55, 2.35), (0.34, 0.0, 1.12)),
    }
    import cv2

    for name, (eye, target) in views.items():
        cam = RtxCamera(
            f"/World/StillCam{name}",
            tick_rate=0.0,
            positions=[eye],
            orientations=[look_at_quat(eye, target)],
        )
        cam.camera.set_focal_lengths(0.016)
        cam.camera.set_apertures((0.036, 0.02025))
        cam.camera.set_clipping_ranges(0.01, 50.0)
        sensor = CameraSensor(cam, resolution=(720, 1280), annotators=["rgb"])
        frame = None
        for _ in range(40):
            RenderingManager.render()
            frame = frame_of(sensor)
            if frame is not None:
                break
        if frame is None:
            say(f"[still] {name}: no frame")
            continue
        path = f"{PREFIX}_{name}.png"
        cv2.imwrite(path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        say(f"[still] {name}: {path}")
    simulation_app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
