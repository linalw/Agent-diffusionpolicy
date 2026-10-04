"""Audit the fingertip pad prims: do they exist, with collision, and how big?

    $ISAAC_SIM_DIR/python.sh scripts/86_pad_audit.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np
from pxr import Usd, UsdGeom, UsdPhysics

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.scene import SortingScene
from isaacsim.core.experimental.prims import RigidPrim


def main() -> int:
    os.environ.setdefault("FRUIT_FINGER_PADS", "1")
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment", "pedestal", "robot"))
    stage = scene.stage
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    for side in ("left", "right"):
        for which in ("left", "right"):
            link_path = f"/World/OpenArm/openarm_{side}_{which}_finger"
            say(f"--- {link_path}")
            link_prim = stage.GetPrimAtPath(link_path)
            say(
                f"    link: valid={link_prim.IsValid()} instance={link_prim.IsInstance()} "
                f"instanceProxy={link_prim.IsInstanceProxy()} "
                f"parentInstance={link_prim.GetParent().IsInstance() if link_prim.GetParent() else None}"
            )
            root = stage.GetPrimAtPath("/World/OpenArm")
            say(
                f"    robot root: instance={root.IsInstance()} instanceable={root.IsInstanceable()} "
                f"children={[ (c.GetName(), c.IsInstance(), c.IsInstanceProxy()) for c in list(root.GetChildren())[:4] ]}"
            )
            for prim in Usd.PrimRange(stage.GetPrimAtPath(link_path), proxies):
                if not prim.HasAPI(UsdPhysics.CollisionAPI):
                    continue
                enabled = UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()
                extra = ""
                if prim.IsA(UsdGeom.Capsule):
                    cap = UsdGeom.Capsule(prim)
                    extra = (
                        f" radius={cap.GetRadiusAttr().Get()} height={cap.GetHeightAttr().Get()} "
                        f"axis={cap.GetAxisAttr().Get()}"
                    )
                elif prim.IsA(UsdGeom.Cube):
                    extra = f" size={UsdGeom.Cube(prim).GetSizeAttr().Get()}"
                tf = UsdGeom.Xformable(prim)
                ops = [op.GetOpName() for op in tf.GetOrderedXformOps()]
                say(
                    f"    {prim.GetPath()} type={prim.GetTypeName()} "
                    f"collisionEnabled={enabled}{extra} ops={ops} "
                    f"approx={UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get() if prim.HasAPI(UsdPhysics.MeshCollisionAPI) else None}"
                )
    # Do the pad bodies actually simulate? A fixed joint between a standalone
    # body and an articulation link is not guaranteed to be accepted; if it is
    # dropped the pad simply falls under gravity and never touches anything.
    try:
        scene.start(physics_dt=1.0 / 120.0, warmup_steps=10)
        bodies = {}
        for side in ("left", "right"):
            for which in ("left", "right"):
                name = f"openarm_{side}_{which}_finger"
                bodies[name] = RigidPrim(f"/World/GraspPads/{name}")
        start = {k: np.asarray(v.get_world_poses()[0][0].numpy()) for k, v in bodies.items()}
        for _ in range(120):
            from isaacsim.core.simulation_manager import SimulationManager

            SimulationManager.step(steps=1)
        for k, v in bodies.items():
            now = np.asarray(v.get_world_poses()[0][0].numpy())
            say(
                f"    pad body {k}: start={np.round(start[k], 3).tolist()} "
                f"now={np.round(now, 3).tolist()} moved={np.linalg.norm(now - start[k]) * 1000:.1f}mm"
            )
    except Exception as exc:  # noqa: BLE001
        say(f"    pad body motion check failed: {exc}")
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
