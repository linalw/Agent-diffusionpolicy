"""Diagnostic: which arm link touches which main-conveyor part along the ready blend?

Standalone probe (no src/ edits). Run through the repo wrapper:

    scripts/run.sh logs/600_stall_fk.py

Prints, for a list of arm configurations (hanging, the measured stall, the
ready pose, and two blend intermediates), every arm link's world AABB and the
AABB of every main-conveyor part, then the overlapping pairs.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Usd, UsdGeom

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.control import ArmController
from fruit_sorting.scene import SortingScene
from isaacsim.core.simulation_manager import SimulationManager

READY = np.array(
    [-1.5005083084106445, -0.3755946457386017, 1.4858945608139038,
     1.3151694536209106, -1.4959912300109863, -0.5879075527191162,
     1.5585992336273193]
)
STALL = np.array([-0.212, -0.364, 1.571, 1.321, -1.475, -0.659, 1.559])
CMD36 = np.array([-0.476, -0.119, 0.472, 0.417, -0.475, -0.187, 0.495])
MID = 0.5 * READY

CONFIGS = {
    "hanging(q=0)": np.zeros(7),
    "blend@0.30(CMD36)": CMD36,
    "blend@0.50": MID,
    "stall(measured)": STALL,
    "ready": READY,
}

CONVEYOR_PARTS = (
    "/World/Conveyor/Belt",
    "/World/Conveyor/FrameN", "/World/Conveyor/FrameP",
    "/World/Conveyor/GuideN", "/World/Conveyor/GuideP",
    "/World/Conveyor/Leg00", "/World/Conveyor/Leg01",
    "/World/Conveyor/Leg10", "/World/Conveyor/Leg11",
    "/World/Conveyor/PulleyTail", "/World/Conveyor/PulleyHead",
)

LINKS = [f"openarm_left_joint{i}_link" for i in range(1, 8)] + [
    "openarm_left_link_base",
    "openarm_left_ee_tcp",
    "openarm_left_left_finger",
    "openarm_left_right_finger",
]


def aabb(cache, stage, path):
    prim = stage.GetPrimAtPath(path)
    if not prim.IsValid():
        return None
    rng = cache.ComputeWorldBound(prim).ComputeAlignedRange()
    if rng.IsEmpty():
        return None
    lo, hi = rng.GetMin(), rng.GetMax()
    return np.array([lo[0], lo[1], lo[2]]), np.array([hi[0], hi[1], hi[2]])


def overlap(a, b, margin=0.0):
    (alo, ahi), (blo, bhi) = a, b
    gap = np.maximum(np.maximum(blo - ahi, alo - bhi), 0.0)
    return float(np.linalg.norm(gap)) <= margin, gap


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot", "conveyor"))
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
    arm = ArmController(scene, "left")
    arm.set_gripper(arm.OPEN)

    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    obstacles = {}
    for path in CONVEYOR_PARTS:
        box = aabb(cache, scene.stage, path)
        if box is not None:
            obstacles[path] = box
    say(f"conveyor parts with geometry: {len(obstacles)}")
    for path, (lo, hi) in obstacles.items():
        say(f"  {path:34s} x=[{lo[0]:+.3f},{hi[0]:+.3f}] "
            f"y=[{lo[1]:+.3f},{hi[1]:+.3f}] z=[{lo[2]:+.3f},{hi[2]:+.3f}]")

    for name, q in CONFIGS.items():
        arm.teleport_joints(np.asarray(q, dtype=float))
        for _ in range(60):
            SimulationManager.step(steps=1)
        say(f"--- config {name}: q={np.round(q, 3).tolist()} "
            f"jaw={np.round(arm.jaw_centre(), 3).tolist()}")
        for link in LINKS:
            box = aabb(cache, scene.stage, f"/World/OpenArm/{link}")
            if box is None:
                continue
            lo, hi = box
            hits = []
            for path, obox in obstacles.items():
                ok, gap = overlap(box, obox)
                if ok:
                    hits.append(path.split("/")[-1])
            if hits:
                say(f"    {link:32s} x=[{lo[0]:+.3f},{hi[0]:+.3f}] "
                    f"y=[{lo[1]:+.3f},{hi[1]:+.3f}] z=[{lo[2]:+.3f},{hi[2]:+.3f}]"
                    f"  CONTACT: {','.join(hits)}")

    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
