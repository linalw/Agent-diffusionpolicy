"""P66 phase 1b - the **static-pose read of the authored finger-tip collider prims**.

    FRUIT_FINGER_TIP_DELTA=0      scripts/run.sh logs/p66/collider_read.py
    FRUIT_FINGER_TIP_DELTA=-0.004 scripts/run.sh logs/p66/collider_read.py

This is the instrument `logs/p39/PREREG.md` amendment A3 (and `logs/p39/p3/
RESULT.md` section 10.1.3) says is the **valid** one for the belt-clearance bit:
"a static-pose read of the authored collider prims (`S - F1` must differ by
`4*cos(theta)`), with no attempt loop and no jam". P39's `scripts/47_robot_collision.py`
never reached the distal plane (it jammed laterally 0.13-0.17 m in x for
0.03-0.06 m of z), which is why the claim was withdrawn to *untested*.

**No physics and no attempt loop**: it builds the **robot part only**
(`parts=("robot",)`, the smallest build that contains the fingers) and never
calls `scene.start()`, so the stage is a static USD scene. What it reads:

* every `.../finger/contact_faces/tip_delta` prim `scene._author_finger_tip_delta`
  authored - its `UsdGeom.Cube` `size`, its authored `scale`/`orient`/`translate`
  and its local-to-world transform;
* from those: the box's three dimensions in its **own** frame, its long axis in
  the **link** frame (pose-independent) and in the **world** frame, the tilt
  `theta` of that axis from the vertical, the box's world AABB (so the world-z
  extent), and the two face planes' world z (proximal / distal).

The two identities this file checks, on all four finger links:

1. `long(S) - long(F1) == 4.000 mm` in the box's own frame (its long axis);
2. `z_extent(S) - z_extent(F1) == 4*cos(theta)` in world z, `theta` = the tilt of
   the box's long axis from world z - the projection the register's formula names
   (the 4 mm tip shift projects onto the *vertical* by `cos(theta)`).

Writes `logs/p66/collider_read_<delta>.json` (delta tag from the env value, `none`
when the knob is unset - the shipped mesh-collider build).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Gf, Usd, UsdGeom, UsdPhysics

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.scene import SortingScene

install_failure_handler("p66_collider_read")

HERE = os.path.dirname(os.path.abspath(__file__))
TAG = os.environ.get("FRUIT_FINGER_TIP_DELTA")
TAG_NAME = "none" if TAG is None else TAG.replace("-", "m").replace(".", "p")
JSON_OUT = os.path.join(HERE, f"collider_read_{TAG_NAME}.json")
SIDES = ("left", "right")
WHICH = ("left", "right")


def quat_matrix(q) -> np.ndarray:
    w, x, y, z = (float(v) for v in q)
    n = np.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def read_box(prim: Usd.Prim) -> dict | None:
    """One authored Cube's dimensions, axes and world box, from the prim itself."""
    if not prim or not prim.IsValid():
        return None
    cube = UsdGeom.Cube(prim)
    if not cube:
        return None
    size = float(cube.GetSizeAttr().Get())
    xf = UsdGeom.Xformable(prim)
    orient = np.array([1.0, 0.0, 0.0, 0.0])
    scale = np.ones(3)
    translate = np.zeros(3)
    for op in xf.GetOrderedXformOps():
        name = op.GetOpName()
        value = op.Get()
        if name == "xformOp:orient":
            if hasattr(value, "GetReal"):
                imag = value.GetImaginary()
                orient = np.array([value.GetReal(), imag[0], imag[1], imag[2]], dtype=float)
            else:
                orient = np.array([float(v) for v in value], dtype=float)
        elif name == "xformOp:scale":
            scale = np.array([float(v) for v in value], dtype=float)
        elif name == "xformOp:translate":
            translate = np.array([float(v) for v in value], dtype=float)
    r_local = quat_matrix(orient)
    dims = np.abs(scale) * size  # (face/thick, across/width, along/length) in the box frame
    world = xf.ComputeLocalToWorldTransform(Usd.TimeCode(0))
    # `Gf` accessors, not `matrix[r][c]` indexing: `np.array(matrix)`/nested indexing
    # disagree about row/column conventions across the bindings, and a silently
    # transposed matrix loses exactly the translation column.
    t_world = np.array(world.ExtractTranslation(), dtype=float)
    q_world = world.ExtractRotationQuat()
    r_world = quat_matrix(
        [q_world.GetReal(), q_world.GetImaginary()[0],
         q_world.GetImaginary()[1], q_world.GetImaginary()[2]]
    )
    # A unit cube's corners at +/-0.5 scaled by `dims`, transformed by the prim's
    # own local-to-world matrix (rotation + translation; the scale is `dims`).
    corners = np.array(
        [
            [sx * dims[0] / 2.0, sy * dims[1] / 2.0, sz * dims[2] / 2.0]
            for sx in (-1.0, 1.0)
            for sy in (-1.0, 1.0)
            for sz in (-1.0, 1.0)
        ]
    )
    world_pts = (r_world @ corners.T).T + t_world
    lo = world_pts.min(axis=0)
    hi = world_pts.max(axis=0)
    long_world = r_world @ np.array([0.0, 0.0, 1.0])
    long_world = long_world / np.linalg.norm(long_world)
    # The link's own frame: the box is rigid in the link frame, so its long axis
    # there is pose-independent (the read the register asks for).
    parent = prim.GetParent().GetParent()
    pworld = UsdGeom.Xformable(parent).ComputeLocalToWorldTransform(Usd.TimeCode(0))
    pq = pworld.ExtractRotationQuat()
    pr = quat_matrix(
        [pq.GetReal(), pq.GetImaginary()[0], pq.GetImaginary()[1], pq.GetImaginary()[2]]
    )
    long_link = pr.T @ long_world
    # local +z is `e_g`, which `_author_flat_face` makes parallel to `e_long`
    # (toward the fingertip), so the +z face is the **distal** one. The point is
    # given in the prim's *local* units (the unit cube's face at +/-size/2) because
    # `world` carries the authored scale as well as the rotation.
    half = np.array([0.0, 0.0, 0.5 * size])
    distal_world = np.array(world.Transform(Gf.Vec3d(*half)), dtype=float)
    proximal_world = np.array(world.Transform(Gf.Vec3d(*(-half))), dtype=float)
    theta = float(np.degrees(np.arccos(min(1.0, abs(float(long_world[2]))))))
    return {
        "path": str(prim.GetPath()),
        "cube_size": size,
        "scale": [float(v) for v in scale],
        "dims_own_mm": [1000 * float(v) for v in dims],
        "translate": [float(v) for v in translate],
        "orient_quat": [float(v) for v in orient],
        "long_axis_world": [float(v) for v in long_world],
        "long_axis_link": [float(v) for v in long_link],
        "theta_from_vertical_deg": theta,
        "z_extent_mm": 1000 * float(hi[2] - lo[2]),
        "world_aabb_mm": [[1000 * float(v) for v in lo], [1000 * float(v) for v in hi]],
        "proximal_world_z_mm": 1000 * float(proximal_world[2]),
        "distal_world_z_mm": 1000 * float(distal_world[2]),
        "vertical_span_mm": 1000 * float(abs(proximal_world[2] - distal_world[2])),
        "collision_api": bool(prim.HasAPI("PhysicsCollisionAPI")),
    }


def main() -> int:
    scene = SortingScene(SceneConfig()).build(parts=("robot",))
    stage = scene.stage
    say(
        f"[p66b] robot-only build (no scene.start, no physics): "
        f"FRUIT_FINGER_TIP_DELTA={TAG!r}"
    )

    boxes = {}
    collision_report = {}
    for side in SIDES:
        for which in WHICH:
            link = stage.GetPrimAtPath(f"/World/OpenArm/openarm_{side}_{which}_finger")
            box = read_box(stage.GetPrimAtPath(f"{link.GetPath()}/contact_faces/tip_delta"))
            boxes[f"openarm_{side}_{which}_finger"] = box
            enabled = []
            for prim in Usd.PrimRange(link):
                if not prim.HasAPI(UsdPhysics.CollisionAPI):
                    continue
                api = UsdPhysics.CollisionAPI(prim)
                flag = api.GetCollisionEnabledAttr().Get()
                enabled.append(bool(True if flag is None else flag))
            collision_report[f"openarm_{side}_{which}_finger"] = {
                "collision_prims": len(enabled),
                "collision_prims_enabled": sum(1 for v in enabled if v),
            }
            if box is not None:
                say(
                    f"[p66b] {side}/{which}: dims(own)="
                    f"{box['dims_own_mm'][0]:.2f}/{box['dims_own_mm'][1]:.2f}/"
                    f"{box['dims_own_mm'][2]:.2f} mm (face/mid/long)  "
                    f"theta={box['theta_from_vertical_deg']:.3f} deg  "
                    f"long_world=[{box['long_axis_world'][0]:+.4f},"
                    f"{box['long_axis_world'][1]:+.4f},{box['long_axis_world'][2]:+.4f}]  "
                    f"z_extent={box['z_extent_mm']:.3f} mm  "
                    f"proximal_z={box['proximal_world_z_mm']:.3f} mm  "
                    f"distal_z={box['distal_world_z_mm']:.3f} mm  "
                    f"vertical_span={box['vertical_span_mm']:.3f} mm  "
                    f"collision={box['collision_api']}  "
                    f"link collision prims enabled="
                    f"{collision_report[f'openarm_{side}_{which}_finger']['collision_prims_enabled']}/"
                    f"{collision_report[f'openarm_{side}_{which}_finger']['collision_prims']}"
                )
            else:
                say(f"[p66b] {side}/{which}: no tip_delta box (the knob is unset or "
                    f"the re-author was skipped); link collision prims enabled="
                    f"{collision_report[f'openarm_{side}_{which}_finger']['collision_prims_enabled']}/"
                    f"{collision_report[f'openarm_{side}_{which}_finger']['collision_prims']}")

    payload = {
        "finger_tip_delta_env": TAG,
        "parts": ["robot"],
        "physics_started": False,
        "boxes": boxes,
        "collision_report": collision_report,
    }
    with open(JSON_OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
    say(f"[p66b] wrote {JSON_OUT}")
    say("[p66b] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
