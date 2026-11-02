#!/usr/bin/env python3
"""P106 M1 step 2: measure the Allegro's geometry as the simulator settles it.

The asset's joint limits are authored in **degrees** (USD revolute convention), its
drives are `k=1e7, c=1e5, maxForce=21 N.m`, and none of its links carries a
collider of its own (the mesh prims do). This probe reads the *world* poses of the
links at the asset's rest posture and at a commanded curl, so the mount frame and
the grasp centre are measured numbers, not a guess from the xform tree.

    scripts/run.sh logs/p106/allegro_geometry.py
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 200, "height": 150})

import numpy as np
from pxr import UsdGeom

from isaacsim.core.experimental.prims import Articulation, RigidPrim

from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import say
from fruit_sorting.fdlimit import raise_fd_limit
from fruit_sorting.scene import SortingScene

raise_fd_limit()

LOCAL = "/tmp/allegro.usd"
FINGERS = ("index", "middle", "ring")
SLOTS = {
    "index": (0.0255, -0.0383),
    "middle": (-0.0064, -0.0064),
    "ring": (-0.0383, 0.0255),
}


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("environment",))
    stage = scene.stage

    root = stage.DefinePrim("/World/Allegro", "Xform")
    root.GetReferences().AddReference(LOCAL)
    scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)

    robot = Articulation("/World/Allegro")
    names = list(robot.dof_names)
    links = list(robot.link_names)
    say(f"dof_names ({len(names)}): {names}")
    say(f"link_names ({len(links)}): {links}")

    from isaacsim.core.simulation_manager import SimulationManager

    def step(n: int = 1) -> None:
        for _ in range(max(1, int(n))):
            SimulationManager.step(steps=1)

    def prim(name: str) -> RigidPrim:
        paths = robot.link_paths
        if isinstance(paths[0], (list, tuple)):
            paths = paths[0]
        path = paths[links.index(name)]
        if isinstance(path, (list, tuple)):
            path = path[0]
        return RigidPrim(str(path))

    handles = {n: prim(n) for n in links}

    def world(name: str) -> np.ndarray:
        pos = handles[name].get_world_poses()[0]
        return np.asarray(pos.numpy(), dtype=float)[0]

    def dump(tag: str) -> None:
        pos = {n: world(n) for n in links}
        say(f"--- {tag} ---")
        for n in ("allegro_mount", "palm_link",
                  "index_link_3",
                  "middle_link_3", "middle_biotac_tip",
                  "ring_link_3", "ring_biotac_tip",
                  "thumb_link_0", "thumb_link_3", "thumb_biotac_tip"):
            say(f"  {n:20s} {np.round(pos[n], 4)}")
        # The asset ships a biotac tip link on middle/ring/thumb only; the index
        # chain ends at `index_link_3`, so that is its contact body.
        tips = {"index": pos["index_link_3"], "middle": pos["middle_biotac_tip"],
                "ring": pos["ring_biotac_tip"], "thumb": pos["thumb_biotac_tip"]}
        keys = list(tips)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                d = float(np.linalg.norm(tips[keys[i]] - tips[keys[j]]))
                say(f"  tip {keys[i]:6s}-{keys[j]:6s} {d*1000:7.1f} mm")
        c = np.mean([tips[k] for k in keys], axis=0)
        say(f"  tip centroid {np.round(c, 4)}  palm->centroid "
            f"{np.round(c - pos['palm_link'], 4)} |{np.linalg.norm(c - pos['palm_link'])*1000:.1f} mm|")
        # The three fingers' bases: a plane fit gives the palm face normal.
        bases = np.array([pos[f"{k}_link_0"] for k in FINGERS])
        n = np.cross(bases[1] - bases[0], bases[2] - bases[0])
        n /= np.linalg.norm(n)
        if np.dot(n, pos["thumb_link_0"] - pos["palm_link"]) < 0:
            n = -n
        say(f"  palm normal (toward thumb side) {np.round(n, 4)}")

    dump("rest (all drives target 0)")
    say("achieved joints: " + " ".join(
        f"{n}={v:+.3f}" for n, v in zip(names, np.asarray(robot.get_dof_positions().numpy())[0])))

    for k in FINGERS:
        for j in (1, 2, 3):
            idx = names.index(f"{k}_joint_{j}")
            robot.set_dof_position_targets(np.array([[1.2]]), dof_indices=np.array([idx]))
    for j in (1, 2, 3):
        idx = names.index(f"thumb_joint_{j}")
        robot.set_dof_position_targets(np.array([[0.9]]), dof_indices=np.array([idx]))
    step(240)
    dump("curl: fingers 1.2 rad, thumb 0.9 rad")
    say("achieved joints: " + " ".join(
        f"{n}={v:+.3f}" for n, v in zip(names, np.asarray(robot.get_dof_positions().numpy())[0])))
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    sys.exit(code)
