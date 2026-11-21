#!/usr/bin/env python3
"""P227: load the Franka Panda USD and dump what an integration needs.

    scripts/run.sh logs/p226/franka_probe.py

Prints the articulation's DOF names/limits, the link names and the world poses
of the hand and the two finger links, plus the default prim and its bbox. No
cell is built; this is the asset read the layout and the controller are designed
from.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from pxr import Gf, Usd, UsdGeom, UsdPhysics  # noqa: E402

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
from isaacsim.core.experimental.prims import Articulation  # noqa: E402
from fruit_sorting.common import say, to_numpy  # noqa: E402

URL = os.environ.get(
    "FRANKA_USD",
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0/"
    "Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd",
)
ROOT = "/World/FrankaProbe"
BASE_Z = float(os.environ.get("FRANKA_BASE_Z", "0.0"))


def main() -> int:
    stage = omni.usd.get_context().get_stage()
    prim = stage.DefinePrim(ROOT, "Xform")
    prim.GetReferences().AddReference(URL)
    UsdGeom.Xformable(prim).ClearXformOpOrder()
    UsdGeom.Xformable(prim).AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, BASE_Z))
    say(f"[franka] referenced {URL} at z={BASE_Z}")

    app_utils.update_app(steps=60)
    robot = Articulation(ROOT)
    names = [str(n) for n in robot.dof_names]
    links = [str(n) for n in robot.link_names]
    say(f"[franka] dofs={len(names)} links={len(links)}")
    say(f"[franka] dof_names={names}")
    say(f"[franka] links={links}")
    try:
        q = np.asarray(robot.get_dof_positions().numpy())[0]
        limits = robot.get_dof_limits()
        lo = np.asarray(limits[0].numpy())[0]
        hi = np.asarray(limits[1].numpy())[0]
        say(f"[franka] q={np.array2string(q, precision=4)}")
        for i, n in enumerate(names):
            say(f"[franka]   {i:2d} {n:24s} limits=[{lo[i]:+.4f},{hi[i]:+.4f}]")
    except Exception as exc:  # noqa: BLE001
        say(f"[franka] dof read failed: {exc}")
    from isaacsim.core.experimental.prims import RigidPrim

    paths = robot.link_paths
    if paths and isinstance(paths[0], (list, tuple)):
        paths = paths[0]
    for i, name in enumerate(links):
        try:
            path = paths[i]
            if isinstance(path, (list, tuple)):
                path = path[0]
            pos, _ = RigidPrim(str(path)).get_world_poses()
            p = np.asarray(pos.numpy())[0]
            say(f"[franka] link {i:2d} {name:26s} pos=({p[0]:+.3f},{p[1]:+.3f},{p[2]:.3f})")
        except Exception as exc:  # noqa: BLE001
            say(f"[franka] link {i:2d} {name:26s} pose read failed: {exc}")
    simulation_app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
