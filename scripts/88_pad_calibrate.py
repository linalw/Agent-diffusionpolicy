"""Calibrate explicit fingertip pad colliders.

The OpenArm finger collision mesh only covers the upper half of each finger: the
world-space collision cloud of a finger spans about +-3 cm around the jaw centre
(scripts/49_gripper_geometry.py) while the visible finger is 7.6 cm long. A fruit
sitting on the belt has its equator 2-4 cm *below* the jaw centre, i.e. below the
collision geometry entirely - the pads press down on the fruit's shoulder instead
of pinching it, which is what `logs/gripper_view/close_front.png` shows.

This script computes the *local* transforms (in each finger link's frame) that put
a thin pad box on the inner face of each finger, extending 2.8 cm below the jaw
centre. The numbers are printed so they can be hard-coded in `scene.py`.

    $ISAAC_SIM_DIR/python.sh scripts/88_pad_calibrate.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Gf, Usd, UsdGeom

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

CONFIG = json.load(open(os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints_oriented.json"),
                        encoding="utf-8"))


def mat_to_quat(r):
    trace = float(np.trace(r))
    if trace > 0.0:
        s = np.sqrt(trace + 1.0) * 2.0
        q = [0.25 * s, (r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s]
    else:
        i = int(np.argmax(np.diag(r)))
        if i == 0:
            s = np.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2.0
            q = [0.25 * s, (r[2, 1] - r[1, 2]) / s, (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s]
        elif i == 1:
            s = np.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2.0
            q = [(r[0, 2] - r[2, 0]) / s, (r[0, 1] + r[1, 0]) / s, 0.25 * s, (r[1, 2] + r[2, 1]) / s]
        else:
            s = np.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2.0
            q = [(r[1, 0] - r[0, 1]) / s, (r[0, 2] + r[2, 0]) / s, (r[1, 2] + r[2, 1]) / s, 0.25 * s]
    q = np.asarray(q, dtype=float)
    return q / np.linalg.norm(q)


def frame(position, x_axis, y_axis):
    """4x4 transform whose columns are the given axes and origin."""
    x = np.asarray(x_axis, dtype=float)
    x = x / np.linalg.norm(x)
    y = np.asarray(y_axis, dtype=float)
    y = y - x * float(x @ y)
    y = y / np.linalg.norm(y)
    z = np.cross(x, y)
    m = np.eye(4)
    m[0:3, 0] = x
    m[0:3, 1] = y
    m[0:3, 2] = z
    m[0:3, 3] = np.asarray(position, dtype=float)
    return m


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0
    say(f"belt_top={belt_top:.3f}")

    out = {}
    for side in ("left", "right"):
        arm = ArmController(scene, side)
        target = np.array([cfg.pick_x, 0.0, belt_top + 0.055])
        arm.teleport_joints(np.asarray(CONFIG["arms"][side]["grasp"], dtype=float))
        arm.set_gripper(arm.OPEN)
        for _ in range(80):
            SimulationManager.step(steps=1)
        _c, residual = arm.solve_to(target, iterations=700, tolerance=0.004)
        if residual > 0.012:
            _c, residual = arm.solve_to(target, iterations=700, tolerance=0.004,
                                        restarts=4, seed=7)
        for _ in range(30):
            SimulationManager.step(steps=1)

        left_f, right_f = arm.jaw_positions()
        left_f = np.asarray(left_f, dtype=float)
        right_f = np.asarray(right_f, dtype=float)
        centre = (left_f + right_f) / 2.0
        axis = right_f - left_f
        axis = axis / max(float(np.linalg.norm(axis)), 1e-9)  # closing axis (+ = toward right finger)
        approach = arm.tcp_position() - centre
        approach = approach / max(float(np.linalg.norm(approach)), 1e-9)
        say(f"=== {side}: jaw={np.round(centre, 4).tolist()} residual={residual * 1000:.1f}mm "
            f"axis={np.round(axis, 3).tolist()} approach={np.round(approach, 3).tolist()}")

        # Pad: thin plate on the inner face of each finger, 4.5 cm along the
        # approach axis, extending 2.8 cm below the jaw centre.
        pad_length = float(os.environ.get("FRUIT_PAD_LENGTH", "0.045"))
        pad_thickness = float(os.environ.get("FRUIT_PAD_THICKNESS", "0.010"))
        pad_band_lo = float(os.environ.get("FRUIT_PAD_LO", "-0.028"))
        pad_band_hi = float(os.environ.get("FRUIT_PAD_HI", "0.012"))
        out[side] = {}
        for sign, link_path in ((-1.0, f"/World/OpenArm/openarm_{side}_left_finger"),
                                (1.0, f"/World/OpenArm/openarm_{side}_right_finger")):
            prim = scene.stage.GetPrimAtPath(link_path)
            link_world = np.array(
                UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            ).reshape(4, 4).T
            link_origin = link_world[0:3, 3]
            # The pad is a plate centred on the finger link origin (so half of its
            # thickness sits inside the finger and it protrudes a few millimetres
            # inboard - the link origin is ~4 mm outside the inner face), pushed
            # `forward` along the approach axis towards the fingertip and shifted
            # vertically so the plate spans the wanted world-z band.
            forward = float(os.environ.get("FRUIT_PAD_FORWARD", "0.010"))
            band_centre = (pad_band_lo + pad_band_hi) / 2.0
            pad_centre = link_origin + approach * forward + np.array([0.0, 0.0, band_centre])
            pad_world = frame(pad_centre, approach, axis)
            local = np.linalg.inv(link_world) @ pad_world
            translate = local[0:3, 3]
            quat = mat_to_quat(local[0:3, 0:3])
            # Box axes: x along the approach (length), y along the closing axis
            # (thickness), z across (height) - so size is (len, thick, band).
            size = (pad_length, pad_thickness, pad_band_hi - pad_band_lo)
            out[side][link_path.split("/")[-1]] = {
                "translate": [round(float(v), 6) for v in translate],
                "quat": [round(float(v), 6) for v in quat],
                "size": [round(float(v), 6) for v in size],
                "band_world_z": [
                    round(float(centre[2] + pad_band_lo), 6),
                    round(float(centre[2] + pad_band_hi), 6),
                ],
            }
            say(f"  {link_path.split('/')[-1]}: pad_world={np.round(pad_centre, 4).tolist()} "
                f"size={np.round(size, 4).tolist()} "
                f"local_t={np.round(translate, 4).tolist()} local_q={np.round(quat, 4).tolist()}")

    with open("configs/finger_pads.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    say("wrote configs/finger_pads.json")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
