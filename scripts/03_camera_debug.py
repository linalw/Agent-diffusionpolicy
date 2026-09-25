"""Render the OpenArm scene from several viewpoints to validate camera placement.

    $ISAAC_SIM_DIR/python.sh scripts/03_camera_debug.py
"""

from __future__ import annotations

import os
import traceback

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 1280, "height": 720})

import numpy as np
from PIL import Image
from pxr import Usd, UsdGeom

import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.objects import DistantLight, GroundPlane
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

ASSET_ROOT = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0"
ROBOT_USD = f"{ASSET_ROOT}/Isaac/Robots/OpenArm/openarm_bimanual/openarm_bimanual.usd"
OUT_DIR = "logs/camera_debug"


def say(msg: str) -> None:
    print(f"[cam] {msg}", flush=True)


def to_numpy(value):
    if value is None:
        return None
    if isinstance(value, tuple):
        value = value[0]
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value)


def look_at_quat(eye, target, up=(0.0, 0.0, 1.0)) -> list[float]:
    eye = np.asarray(eye, dtype=float)
    target = np.asarray(target, dtype=float)
    z_axis = eye - target
    z_axis /= np.linalg.norm(z_axis)
    x_axis = np.cross(np.asarray(up, dtype=float), z_axis)
    x_axis /= np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    rot = np.stack([x_axis, y_axis, z_axis], axis=1)
    trace = float(np.trace(rot))
    w = np.sqrt(max(1.0 + trace, 0.0)) / 2.0
    if w < 1e-8:
        return [1.0, 0.0, 0.0, 0.0]
    x = (rot[2, 1] - rot[1, 2]) / (4.0 * w)
    y = (rot[0, 2] - rot[2, 0]) / (4.0 * w)
    z = (rot[1, 0] - rot[0, 1]) / (4.0 * w)
    return [float(w), float(x), float(y), float(z)]


def save_rgb(arr, path: str) -> None:
    Image.fromarray(np.asarray(arr)[..., :3].astype(np.uint8)).save(path)


def save_depth(arr, path: str) -> None:
    d = np.asarray(arr)[..., 0].astype(np.float32)
    valid = d[d > 0.0]
    if valid.size == 0:
        Image.fromarray(np.zeros(d.shape, dtype=np.uint8)).save(path)
        return
    lo, hi = float(np.percentile(valid, 1)), float(np.percentile(valid, 99))
    norm = np.clip((d - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    norm[d <= 0.0] = 0.0
    Image.fromarray((norm * 255).astype(np.uint8)).save(path)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    stage_utils.create_new_stage()
    stage = stage_utils.get_current_stage()
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    GroundPlane("/World/GroundPlane", positions=[0.0, 0.0, 0.0])
    DistantLight("/World/DistantLight", positions=[0.0, 0.0, 10.0]).set_intensities(400.0)

    robot_prim = stage.DefinePrim("/World/OpenArm", "Xform")
    robot_prim.GetReferences().AddReference(ROBOT_USD)
    app_utils.update_app(steps=5)

    cam = RtxCamera("/World/Cam", tick_rate=30.0)
    # OpenUSD camera optics are expressed in tenths of a scene unit, so on a
    # meter stage a 24 mm lens is 0.024 and a 36 mm sensor is 0.036.
    cam.camera.set_focal_lengths(0.024)
    cam.camera.set_apertures((0.036, 0.02025))
    cam.camera.set_focus_distances(2.0)
    cam.camera.set_clipping_ranges(0.01, 100.0)
    sensor = CameraSensor(cam, resolution=(720, 1280), annotators=["rgb", "distance_to_image_plane"])

    SimulationManager.set_backend("torch")
    SimulationManager.switch_physics_engine("physx")
    SimulationManager.set_physics_dt(1.0 / 60.0)
    app_utils.play(commit=True)
    app_utils.update_app(steps=20)

    views = {
        "front_2m": ((2.0, 0.0, 1.0), (0.0, 0.0, 0.4)),
        "diag_2m": ((1.6, 1.6, 1.2), (0.0, 0.0, 0.4)),
        "diag_4m": ((3.0, 3.0, 2.2), (0.0, 0.0, 0.4)),
    }
    for name, (eye, target) in views.items():
        cam.set_world_poses(positions=[eye], orientations=[look_at_quat(eye, target)])
        app_utils.update_app(steps=12)
        pose = cam.get_world_poses()
        pos = to_numpy(pose[0])[0]
        quat = to_numpy(pose[1])[0]
        rgb = to_numpy(sensor.get_data("rgb"))
        depth = to_numpy(sensor.get_data("distance_to_image_plane"))
        save_rgb(rgb, f"{OUT_DIR}/{name}_rgb.png")
        save_depth(depth, f"{OUT_DIR}/{name}_depth.png")
        d = depth[..., 0]
        valid = d[d > 0.0]
        say(
            f"{name}: cam_pos={np.round(pos, 3).tolist()} quat={np.round(quat, 3).tolist()} "
            f"depth=[{valid.min():.2f},{valid.max():.2f}] mean={valid.mean():.2f}"
        )

    app_utils.pause()
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:
        with open("logs/03_traceback.txt", "w") as fh:
            traceback.print_exc(file=fh)
        say("FAILED - see logs/03_traceback.txt")
        code = 1
    finally:
        simulation_app.close()
    raise SystemExit(code)
