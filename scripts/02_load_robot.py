"""Load the OpenArm bimanual robot, inspect its articulation, and render a preview.

    $ISAAC_SIM_DIR/python.sh scripts/02_load_robot.py
"""

from __future__ import annotations

import os
import traceback

HEADLESS = os.environ.get("HEADLESS", "1") == "1"
PREVIEW_PATH = os.environ.get("PREVIEW_PATH", "logs/preview_openarm.png")

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": HEADLESS, "width": 1280, "height": 720})

import numpy as np
from pxr import Gf, Usd, UsdGeom

import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.objects import DistantLight, GroundPlane
from isaacsim.core.experimental.prims import Articulation
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

ASSET_ROOT = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0"
ROBOT_USD = f"{ASSET_ROOT}/Isaac/Robots/OpenArm/openarm_bimanual/openarm_bimanual.usd"


def say(msg: str) -> None:
    print(f"[robot] {msg}", flush=True)


def to_numpy(value):
    """Convert warp arrays / numpy arrays to numpy (warp arrays reject item indexing)."""
    if value is None:
        return None
    # CameraSensor.get_data() returns (array, metadata) tuples.
    if isinstance(value, tuple):
        value = value[0]
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value)


def look_at_quat(eye, target, up=(0.0, 0.0, 1.0)) -> list[float]:
    """Quaternion (w, x, y, z) for a USD camera at `eye` looking at `target`."""
    eye = np.asarray(eye, dtype=float)
    target = np.asarray(target, dtype=float)
    z_axis = eye - target
    z_axis /= np.linalg.norm(z_axis)
    x_axis = np.cross(np.asarray(up, dtype=float), z_axis)
    x_axis /= np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    rot = np.stack([x_axis, y_axis, z_axis], axis=1)
    trace = float(np.trace(rot))
    w = np.sqrt(1.0 + trace) / 2.0
    x = (rot[2, 1] - rot[1, 2]) / (4.0 * w)
    y = (rot[0, 2] - rot[2, 0]) / (4.0 * w)
    z = (rot[1, 0] - rot[0, 1]) / (4.0 * w)
    return [float(w), float(x), float(y), float(z)]


def world_bounds(stage: Usd.Stage, path: str) -> tuple[np.ndarray, np.ndarray]:
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    box = cache.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
    return np.array(box.GetMin()), np.array(box.GetMax())


def main() -> int:
    stage_utils.create_new_stage()
    stage = stage_utils.get_current_stage()
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    GroundPlane("/World/GroundPlane", positions=[0.0, 0.0, 0.0])
    DistantLight("/World/DistantLight", positions=[0.0, 0.0, 10.0]).set_intensities(600.0)
    say("stage created")

    robot_prim = stage.DefinePrim("/World/OpenArm", "Xform")
    robot_prim.GetReferences().AddReference(ROBOT_USD)
    say("robot USD referenced (downloads on first use)")
    app_utils.update_app(steps=5)

    prim = stage.GetPrimAtPath("/World/OpenArm")
    say(f"robot prim valid={prim.IsValid()}")
    children = [c.GetName() for c in prim.GetChildren()]
    say(f"top-level children: {children}")
    lo, hi = world_bounds(stage, "/World/OpenArm")
    say(f"world bounds min={np.round(lo, 4).tolist()} max={np.round(hi, 4).tolist()}")
    say(f"size={np.round(hi - lo, 4).tolist()}")

    camera = RtxCamera("/World/HeadCamera", tick_rate=30.0)
    camera.camera.set_focal_lengths(24.0)
    camera.camera.set_clipping_ranges(0.01, 100.0)
    eye = (1.35, 1.15, 1.05)
    camera.set_world_poses(
        positions=[eye],
        orientations=[look_at_quat(eye, (0.0, 0.0, 0.40))],
    )
    sensor = CameraSensor(
        camera,
        resolution=(720, 1280),
        annotators=["rgb", "distance_to_image_plane"],
    )

    SimulationManager.set_backend("torch")
    SimulationManager.switch_physics_engine("physx")
    SimulationManager.set_physics_dt(1.0 / 60.0)
    app_utils.play(commit=True)
    app_utils.update_app(steps=30)

    robot = Articulation("/World/OpenArm")
    links = list(robot.link_names)
    joints = list(robot.joint_names)
    say(f"num links={len(links)} num joints={len(joints)}")
    say(f"links: {links}")
    say(f"joints: {joints}")

    lower, upper = robot.get_dof_limits()
    lower = np.asarray(lower.numpy() if hasattr(lower, "numpy") else lower)
    upper = np.asarray(upper.numpy() if hasattr(upper, "numpy") else upper)
    for name, lo_i, hi_i in zip(joints, lower[0], upper[0]):
        say(f"  joint {name:36s} limits [{lo_i:+.3f}, {hi_i:+.3f}]")

    rgb = to_numpy(sensor.get_data("rgb"))
    depth = to_numpy(sensor.get_data("distance_to_image_plane"))
    say(f"rgb={None if rgb is None else rgb.shape}")
    say(f"depth={None if depth is None else depth.shape}")
    if depth is not None:
        valid = depth[depth > 0.0]
        say(f"depth valid px={valid.size} range=[{valid.min() if valid.size else -1:.3f}, "
            f"{valid.max() if valid.size else -1:.3f}]")

    if rgb is not None:
        from PIL import Image

        os.makedirs(os.path.dirname(PREVIEW_PATH) or ".", exist_ok=True)
        Image.fromarray(np.asarray(rgb)[..., :3].astype(np.uint8)).save(PREVIEW_PATH)
        say(f"saved preview -> {PREVIEW_PATH}")

    app_utils.pause()
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:
        with open("logs/02_traceback.txt", "w") as fh:
            traceback.print_exc(file=fh)
        say("FAILED - see logs/02_traceback.txt")
        code = 1
    finally:
        simulation_app.close()
    raise SystemExit(code)
