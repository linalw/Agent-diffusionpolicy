"""Record MP4 videos of the sorting cell so the behaviour can be watched.

    $ISAAC_SIM_DIR/python.sh scripts/70_record_video.py

Writes:
  logs/video/observer.mp4  - fixed external view of the whole cell
  logs/video/head.mp4      - what the robot's head camera sees (the policy input)
  logs/video/side_by_side.mp4 - both views stacked
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 1280, "height": 720})

import cv2
import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.rendering_manager import RenderingManager
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, look_at_quat, say, to_numpy
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene
from fruit_sorting.tactile import GripperTactile
from fruit_sorting.tasks import PickAndPlaceTask

install_failure_handler("70_record_video")

DT = 1.0 / 120.0
CYCLES = int(os.environ.get("FRUIT_CYCLES", "3"))
OUT_DIR = os.environ.get("FRUIT_VIDEO_DIR", "logs/video")
FPS = float(os.environ.get("FRUIT_VIDEO_FPS", "30"))
#: Render every Nth physics step; the video plays back at 30 fps.
RENDER_EVERY = int(round((1.0 / FPS) / DT))


def frame_of(sensor, annotator: str = "rgb"):
    data = sensor.get_data(annotator)
    array = to_numpy(data)
    if array is None:
        return None
    array = np.asarray(array)
    if array.ndim == 4:
        array = array[0]
    if array.shape[-1] == 4:
        array = array[..., :3]
    return np.ascontiguousarray(array.astype(np.uint8))


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = SceneConfig()
    scene = SortingScene(cfg).build()

    # Fixed external view of the whole cell.
    eye = (1.75, 1.55, 2.35)
    observer = RtxCamera(
        "/World/ObserverCamera",
        tick_rate=0.0,
        positions=[eye],
        orientations=[look_at_quat(eye, (0.45, 0.0, 1.05))],
    )
    observer.camera.set_focal_lengths(0.016)
    observer.camera.set_apertures((0.036, 0.02025))
    observer.camera.set_clipping_ranges(0.01, 50.0)
    observer_sensor = CameraSensor(observer, resolution=(540, 960), annotators=["rgb"])

    tactile = GripperTactile()
    tactile.attach(stage=scene.stage)
    scene.start(physics_dt=DT, warmup_steps=60)
    tactile.refresh()

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "3")))
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.reset()
    spawner.prime(count=6)

    task = PickAndPlaceTask(scene, spawner, tactile, cfg)
    task.go_ready()
    app_utils.update_app(steps=10)

    observer_frames: list[np.ndarray] = []
    head_frames: list[np.ndarray] = []
    step_counter = 0

    def capture() -> None:
        nonlocal step_counter
        step_counter += 1
        if step_counter % RENDER_EVERY:
            return
        RenderingManager.render()
        obs = frame_of(observer_sensor)
        head = frame_of(scene.camera_sensor)
        if obs is not None:
            observer_frames.append(obs)
        if head is not None:
            head_frames.append(head)

    captured = 0
    attempts = 0
    while captured < CYCLES and attempts < CYCLES * 3:
        attempts += 1
        for _ in range(120):
            SimulationManager.step(steps=1)
            spawner.enforce_transport()
            capture()
        state = task.select_target(spawner.state())
        if state is None:
            continue
        bin_index = 0 if state["grade"] == "A" else 1
        say(f"[video] cycle {captured}: {state['category']} grade={state['grade']} bin={bin_index}")

        # Run the task while capturing; the task's own loops are patched below by
        # monkey-patching its step hooks through the recorder-free path.
        task.frame_callback = capture
        result = task.run(state, bin_index, verbose=True)
        say(f"[video] cycle {captured} result grasped={result.grasped} placed={result.placed}")
        if result.success:
            captured += 1
        task.go_ready()
        for _ in range(40):
            SimulationManager.step(steps=1)
            capture()

    say(f"captured {len(observer_frames)} observer and {len(head_frames)} head frames")

    def write(path: str, frames: list[np.ndarray]) -> None:
        if not frames:
            return
        height, width = frames[0].shape[:2]
        writer = cv2.VideoWriter(
            path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (width, height)
        )
        for image in frames:
            if image.shape[:2] != (height, width):
                image = cv2.resize(image, (width, height))
            writer.write(cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        writer.release()
        say(f"wrote {path} ({len(frames)} frames, {len(frames) / FPS:.1f}s)")

    write(os.path.join(OUT_DIR, "observer.mp4"), observer_frames)
    write(os.path.join(OUT_DIR, "head.mp4"), head_frames)

    # Side-by-side: scale both to the same height and stack horizontally.
    if observer_frames and head_frames:
        height = 480
        paired = []
        for index in range(min(len(observer_frames), len(head_frames))):
            left = cv2.resize(
                observer_frames[index], (int(960 * height / 540), height)
            )
            right = cv2.resize(head_frames[index], (int(848 * height / 480), height))
            paired.append(np.hstack([left, right]))
        write(os.path.join(OUT_DIR, "side_by_side.mp4"), paired)

    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
