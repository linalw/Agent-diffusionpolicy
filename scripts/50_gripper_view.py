"""Render both grippers at their calibrated grasp pose, next to a fruit-sized ball.

Numbers alone have been ambiguous about how the OpenArm gripper is oriented at
the "grasp" waypoint, so this renders close-ups from four directions with a
5 cm ball sitting where a fruit would sit and a red dot at the jaw centre.

    $ISAAC_SIM_DIR/python.sh scripts/50_gripper_view.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 1280, "height": 720})

import numpy as np
from PIL import Image
from pxr import Gf, Usd, UsdGeom

import isaacsim.core.experimental.utils.app as app_utils
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import look_at_quat, say, to_numpy
from fruit_sorting.control import ArmController
from fruit_sorting.scene import SortingScene, _set_color
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

CONFIG = json.load(open("configs/waypoints.json", encoding="utf-8"))
OUT_DIR = "logs/gripper_view"


def ball(stage: Usd.Stage, path: str, centre, radius: float, colour) -> None:
    sphere = UsdGeom.Sphere.Define(stage, path)
    sphere.GetRadiusAttr().Set(float(radius))
    xf = UsdGeom.Xformable(sphere)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in centre]))
    _set_color(sphere, tuple(colour))


def save(sensor, path: str) -> None:
    rgb = to_numpy(sensor.get_data("rgb"))
    if rgb is None:
        say(f"{path}: no rgb")
        return
    Image.fromarray(np.asarray(rgb)[..., :3].astype(np.uint8)).save(path)
    say(f"saved {path}")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    stage = scene.stage
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    target = np.array([cfg.pick_x, 0.0, belt_top + 0.055])

    cam = RtxCamera("/World/ViewCam", tick_rate=30.0)
    cam.camera.set_focal_lengths(0.024)
    cam.camera.set_apertures((0.036, 0.02025))
    cam.camera.set_focus_distances(0.5)
    cam.camera.set_clipping_ranges(0.01, 50.0)
    sensor = CameraSensor(cam, resolution=(720, 1280), annotators=["rgb"])

    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)

    # A fruit-sized ball where a fruit would rest, and a dot at the jaw centre.
    for side in ("left", "right"):
        arm = ArmController(scene, side)
        arm.teleport_joints(np.asarray(CONFIG["arms"][side]["grasp"], dtype=float))
        arm.set_gripper(arm.OPEN)
        for _ in range(120):
            SimulationManager.step(steps=1)
        arm.capture_hold_pose()
        _cfg, residual = arm.solve_to(target, iterations=800, tolerance=0.004)
        for _ in range(40):
            SimulationManager.step(steps=1)
        jaw = arm.jaw_centre().copy()
        say(
            f"{side}: jaw={np.round(jaw, 4).tolist()} residual={residual * 1000:.1f}mm "
            f"finger_q={np.round(arm.dof_positions()[arm.finger_dofs], 4).tolist()}"
        )
        ball(stage, f"/World/Marker_{side}_fruit", [jaw[0], jaw[1], belt_top + 0.025], 0.025,
             (0.95, 0.15, 0.10) if side == "left" else (0.15, 0.35, 0.95))
        ball(stage, f"/World/Marker_{side}_jaw", jaw, 0.006, (1.0, 0.9, 0.1))
        say(f"{side}: marker ball at {np.round([jaw[0], jaw[1], belt_top + 0.025], 4).tolist()}")
        # Leave this arm in place for the render.
        arm.set_gripper(arm.OPEN)

    # Close-up of the left gripper around a 5.5 cm fruit-sized ball, which is what
    # the grasp geometry has to straddle.
    view_arm = ArmController(scene, "left")
    jaw = view_arm.jaw_centre()
    left_f, right_f = view_arm.jaw_positions()
    centre = (np.asarray(left_f, dtype=float) + np.asarray(right_f, dtype=float)) / 2.0
    approach = view_arm.tcp_position() - centre
    approach = approach / max(float(np.linalg.norm(approach)), 1e-9)
    pad_centre = centre + approach * 0.010 + np.array([0.0, 0.0, -0.0165])
    seat = belt_top + cfg.nest_height
    fruit_z = seat + 0.0277
    ball(stage, "/World/Ball_CloseUp", [pad_centre[0], pad_centre[1], fruit_z], 0.0277,
         (1.0, 0.25, 0.15))
    say(f"close-up fruit placed at ({pad_centre[0]:.4f},{pad_centre[1]:+.4f},{fruit_z:.4f}) "
        f"jaw={np.round(jaw, 4).tolist()} approach={np.round(approach, 3).tolist()}")

    app_utils.update_app(steps=20)
    focus = np.array([cfg.pick_x, 0.0, belt_top + 0.05])
    views = {
        "front": focus + np.array([0.55, 0.0, 0.10]),
        "side_y_neg": focus + np.array([0.05, -0.50, 0.10]),
        "side_y_pos": focus + np.array([0.05, 0.50, 0.10]),
        "top": focus + np.array([0.06, 0.0, 0.55]),
    }
    close = np.array([jaw[0], jaw[1], belt_top + 0.03])
    views.update(
        {
            "close_front": close + np.array([0.30, 0.0, 0.05]),
            "close_side": close + np.array([0.0, -0.28, 0.06]),
            "close_top": close + np.array([0.04, 0.0, 0.30]),
        }
    )
    for name, eye in views.items():
        cam.set_world_poses(positions=[eye.tolist()], orientations=[look_at_quat(eye, focus)])
        for _ in range(12):
            app_utils.update_app(steps=1)
        save(sensor, f"{OUT_DIR}/{name}.png")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
