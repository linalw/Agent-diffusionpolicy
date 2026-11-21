#!/usr/bin/env python3
"""P226: two stills of the cell layout (bins or belts) - a plan view and an oblique.

    FRUIT_OUTPUT_BINS=1 scripts/run.sh logs/p225/scene_still.py /tmp/opencode/x

The scene is the direct env's own build (`SortingRLEnv.reset` feeds the belt), so
the stills show the stocked line. No policy step is taken.
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

from isaacsim.core.rendering_manager import RenderingManager  # noqa: E402
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera  # noqa: E402

from fruit_sorting.common import look_at_quat, say, to_numpy  # noqa: E402
from fruit_sorting.rl_env import RewardConfig, SortingRLEnv  # noqa: E402

PREFIX = sys.argv[1] if len(sys.argv) > 1 else "/tmp/opencode/scene"


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
    env = SortingRLEnv(
        reward=RewardConfig(horizon=2600),
        presentation="direct",
        seed=77,
        ablate="none",
        checkpoint="checkpoints/p177_full/policy_best.pt",
        record=False,
        out_dir="/tmp/opencode/still_store",
        execute_steps=4,
        ddim_steps=8,
    )
    env.reset(seed=77)
    env.advance(40)
    views = {
        "plan": ((0.02, 0.0, 3.30), (0.12, 0.0, 1.00)),
        "obs": ((1.75, 1.55, 2.35), (0.34, 0.0, 1.12)),
    }
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
        import cv2

        path = f"{PREFIX}_{name}.png"
        cv2.imwrite(path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        say(f"[still] {name}: {path} ({frame.shape[1]}x{frame.shape[0]})")
    simulation_app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
