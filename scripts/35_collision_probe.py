"""Check which parts of the OpenArm have enabled collision geometry.

    $ISAAC_SIM_DIR/python.sh scripts/35_collision_probe.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

from pxr import Usd, UsdPhysics

import isaacsim.core.experimental.utils.stage as stage_utils
from fruit_sorting.assets import OPENARM_BIMANUAL_USD
from fruit_sorting.common import say


def main() -> int:
    stage_utils.create_new_stage()
    stage = stage_utils.get_current_stage()
    prim = stage.DefinePrim("/World/OpenArm", "Xform")
    prim.GetReferences().AddReference(OPENARM_BIMANUAL_USD)
    for _ in range(10):
        simulation_app.update()

    count = 0
    for p in Usd.PrimRange(stage.GetPrimAtPath("/World/OpenArm")):
        if p.HasAPI(UsdPhysics.CollisionAPI):
            attrs = {}
            for name in ("physics:collisionEnabled", "physics:approximation", "purpose"):
                attr = p.GetAttribute(name)
                attrs[name] = attr.Get() if attr.IsValid() else None
            say(f"{p.GetPath()} -> {attrs}")
            count += 1
    say(f"total collision prims: {count}")

    say("--- finger subtrees ---")
    for path in (
        "/World/OpenArm/openarm_left_left_finger",
        "/World/OpenArm/openarm_right_right_finger",
    ):
        for p in Usd.PrimRange(stage.GetPrimAtPath(path)):
            say(f"  {p.GetPath()} type={p.GetTypeName()} schemas={list(p.GetAppliedSchemas())}")

    from pxr import UsdGeom

    for purpose in (UsdGeom.Tokens.default_, UsdGeom.Tokens.proxy):
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [purpose])
        for path in (
            "/World/OpenArm/openarm_left_left_finger",
            "/World/OpenArm/openarm_left_right_finger",
        ):
            rng = cache.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
            lo, hi = rng.GetMin(), rng.GetMax()
            say(
                f"bbox[{purpose}] {path.split('/')[-1]}: "
                f"x=[{lo[0]:.4f},{hi[0]:.4f}] y=[{lo[1]:.4f},{hi[1]:.4f}] z=[{lo[2]:.4f},{hi[2]:.4f}]"
            )

    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
