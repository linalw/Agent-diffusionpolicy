"""Measure the gripper's *collision* geometry, not its link origins.

Every earlier physical-grasp probe inferred the jaw geometry from
``jaw_centre()`` (the midpoint of the two finger link origins) plus a constant
"face offset". That constant is only valid at one opening, and it hides which
part of the finger actually collides. This probe reads the world-space point
cloud of every collision-enabled prim under each finger, so the inner face, the
grip band and the usable opening come out directly.

    $ISAAC_SIM_DIR/python.sh scripts/49_gripper_geometry.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Usd, UsdGeom, UsdPhysics

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

CONFIG = json.load(open("configs/waypoints.json", encoding="utf-8"))
FINGERS = {
    "left": ("openarm_left_left_finger", "openarm_left_right_finger"),
    "right": ("openarm_right_left_finger", "openarm_right_right_finger"),
}


def collision_roots(stage: Usd.Stage, root_path: str) -> list[str]:
    """Prims under `root_path` that carry the collision API."""
    out = []
    root = stage.GetPrimAtPath(root_path)
    if not root.IsValid():
        return out
    # The OpenArm asset is instanceable: the collision meshes only exist as
    # instance proxies, so a plain PrimRange walks straight past them.
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    for prim in Usd.PrimRange(root, proxies):
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            enabled = UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()
            if enabled is not False:
                out.append(str(prim.GetPath()))
    return out


def shape_points(stage: Usd.Stage, path: str) -> np.ndarray:
    """World-space vertices of one geom prim (mesh points or shape params)."""
    prim = stage.GetPrimAtPath(path)
    if not prim.IsValid():
        return np.zeros((0, 3))
    time = Usd.TimeCode.Default()
    xform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(time)
    m = np.array(xform).reshape(4, 4).T

    if prim.IsA(UsdGeom.Mesh):
        pts = np.asarray(UsdGeom.Mesh(prim).GetPointsAttr().Get(), dtype=float)
    elif prim.IsA(UsdGeom.Sphere):
        r = float(UsdGeom.Sphere(prim).GetRadiusAttr().Get())
        u = np.linspace(0, np.pi, 8)
        v = np.linspace(0, 2 * np.pi, 12)
        uu, vv = np.meshgrid(u, v, indexing="ij")
        pts = np.stack(
            [r * np.sin(uu) * np.cos(vv), r * np.sin(uu) * np.sin(vv), r * np.cos(uu)], axis=-1
        ).reshape(-1, 3)
    elif prim.IsA(UsdGeom.Cube):
        s = float(UsdGeom.Cube(prim).GetSizeAttr().Get()) / 2.0
        pts = np.array([[x, y, z] for x in (-s, s) for y in (-s, s) for z in (-s, s)])
    elif prim.IsA(UsdGeom.Cylinder):
        c = UsdGeom.Cylinder(prim)
        r = float(c.GetRadiusAttr().Get())
        h = float(c.GetHeightAttr().Get()) / 2.0
        pts = np.array(
            [
                [r * np.cos(a), r * np.sin(a), z]
                for a in np.linspace(0, 2 * np.pi, 16)
                for z in (-h, h)
            ]
        )
    else:
        return np.zeros((0, 3))
    if pts.size == 0:
        return np.zeros((0, 3))
    homo = np.concatenate([pts, np.ones((len(pts), 1))], axis=1)
    return (homo @ m.T)[:, :3]


def finger_points(stage: Usd.Stage, link_path: str) -> tuple[np.ndarray, list[str]]:
    """World-space collision point cloud of a finger link.

    The collision geometry lives under a ``collisions`` Xform as child meshes,
    so every collision root is expanded into its full subtree.
    """
    roots = collision_roots(stage, link_path)
    clouds: list[np.ndarray] = []
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    for root_path in roots:
        for prim in Usd.PrimRange(stage.GetPrimAtPath(root_path), proxies):
            pts = shape_points(stage, str(prim.GetPath()))
            if len(pts):
                clouds.append(pts)
    return (np.concatenate(clouds) if clouds else np.zeros((0, 3))), roots


def profile(stage: Usd.Stage, side: str, arm, label: str) -> None:
    names = FINGERS[side]
    left, left_paths = finger_points(stage, f"/World/OpenArm/{names[0]}")
    right, right_paths = finger_points(stage, f"/World/OpenArm/{names[1]}")
    if not len(left) or not len(right):
        say(f"{label}: no collision points ({names})")
        return

    jaw_left, jaw_right = arm.jaw_positions()
    axis = np.asarray(jaw_right, dtype=float) - np.asarray(jaw_left, dtype=float)
    axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
    # `neg` is the finger at the low end of the closing axis.
    if float((left @ axis).mean()) < float((right @ axis).mean()):
        neg, pos, neg_paths, pos_paths = left, right, left_paths, right_paths
    else:
        neg, pos, neg_paths, pos_paths = right, left, right_paths, left_paths

    neg_u = neg @ axis
    pos_u = pos @ axis
    gap = float(pos_u.min() - neg_u.max())
    say(
        f"{label}: cmd={arm.finger_opening():.4f} origin_sep={arm.jaw_separation() * 100:.2f}cm "
        f"face_gap={gap * 100:.2f}cm colliders={len(neg_paths)}/{len(pos_paths)} "
        f"axis={np.round(axis, 3).tolist()}"
    )
    say(f"    collider roots: {[p.split('/')[-1] for p in neg_paths + pos_paths]}")

    z_lo = max(float(pos[:, 2].min()), float(neg[:, 2].min()))
    z_hi = min(float(pos[:, 2].max()), float(neg[:, 2].max()))
    say(f"    overlap in z: {z_lo:.4f} .. {z_hi:.4f} ({z_hi - z_lo:.4f} m)")
    say("      z[m]    gap[cm]   depth[cm]  n_neg n_pos")
    for z in np.arange(z_lo, z_hi + 1e-9, 0.004):
        band = 0.004
        p = pos[np.abs(pos[:, 2] - z) < band]
        n = neg[np.abs(neg[:, 2] - z) < band]
        if len(p) < 2 or len(n) < 2:
            continue
        slice_gap = float((p @ axis).min() - (n @ axis).max())
        xs = np.concatenate([p[:, 0], n[:, 0]])
        say(f"    {z:7.4f}   {slice_gap * 100:6.2f}   {np.ptp(xs) * 100:6.2f}  {len(n):5d} {len(p):5d}")


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    belt_top = cfg.belt_center[2] + cfg.belt_size[2] / 2.0

    def dump(side_name: str, arm_ctl) -> None:
        names = FINGERS[side_name]
        poses = arm_ctl.jaw_positions()
        for tag, name, pos in zip(("a", "b"), names, poses):
            cloud, roots = finger_points(scene.stage, f"/World/OpenArm/{name}")
            lo = cloud.min(axis=0) if len(cloud) else np.zeros(3)
            hi = cloud.max(axis=0) if len(cloud) else np.zeros(3)
            say(
                f"    {name} rigid={np.round(np.asarray(pos), 4).tolist()} "
                f"collision_bbox x=[{lo[0]:.4f},{hi[0]:.4f}] y=[{lo[1]:.4f},{hi[1]:.4f}] "
                f"z=[{lo[2]:.4f},{hi[2]:.4f}] centre={np.round((lo + hi) / 2, 4).tolist()}"
            )
        say(f"    jaw_centre={np.round(arm_ctl.jaw_centre(), 4).tolist()}")
        say(f"    tcp={np.round(arm_ctl.tcp_position(), 4).tolist()}")

    stage = scene.stage
    finger_root = "/World/OpenArm/openarm_left_left_finger"
    say(f"robot root valid: {stage.GetPrimAtPath('/World/OpenArm').IsValid()}")
    say(f"left finger valid: {stage.GetPrimAtPath(finger_root).IsValid()}")
    say(f"collisions valid: {stage.GetPrimAtPath(finger_root + '/collisions').IsValid()}")
    proxy = [str(p.GetPath()) for p in Usd.PrimRange(stage.GetPrimAtPath(finger_root))]
    say(f"subtree ({len(proxy)} prims): {proxy[:8]}")
    same = [
        str(p.GetPath())
        for p in Usd.PrimRange(
            stage.GetPrimAtPath(finger_root), Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
        )
    ]
    say(f"subtree with instance proxies ({len(same)} prims): {same[:8]}")

    for side in ("left", "right"):
        arm = ArmController(scene, side)
        target = np.array([cfg.pick_x, 0.0, belt_top + 0.055])
        arm.teleport_joints(np.asarray(CONFIG["arms"][side]["grasp"], dtype=float))
        arm.set_gripper(arm.OPEN)
        for _ in range(40):
            SimulationManager.step(steps=1)
        # Freeze the *calibrated* wrist orientation before refining position:
        # position-only IK will happily rotate the wrist (and therefore point the
        # fingers somewhere else) while keeping the jaw centre on target.
        arm.capture_hold_pose()
        before = np.asarray(arm.jaw_positions()[1]) - np.asarray(arm.jaw_positions()[0])
        say(f"  {side}: axis after teleport = {np.round(before / np.linalg.norm(before), 3).tolist()}")
        _cfg, residual = arm.solve_to(target, iterations=800, tolerance=0.004)
        for _ in range(20):
            SimulationManager.step(steps=1)
        after = np.asarray(arm.jaw_positions()[1]) - np.asarray(arm.jaw_positions()[0])
        say(f"  {side}: axis after IK       = {np.round(after / np.linalg.norm(after), 3).tolist()}")
        say(f"  {side}: geometry dump")
        dump(side, arm)
        jaw = arm.jaw_centre().copy()
        say(
            f"=== {side} arm jaw={np.round(jaw, 4).tolist()} "
            f"residual={residual * 1000:.1f}mm belt_top={belt_top:.3f}"
        )
        for cmd in (arm.OPEN, 0.030, 0.020, 0.010, 0.0):
            arm.set_gripper(cmd)
            for _ in range(90):
                SimulationManager.step(steps=1)
            profile(scene.stage, side, arm, f"  cmd={cmd:.3f}")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
