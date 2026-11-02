#!/usr/bin/env python3
"""P106 M1 step 1: what *is* the Allegro USD? (read-only census)

Opens the asset (remote root the tree already reads), walks every prim, and
prints the facts the mount has to be authored against: the default prim, the
link tree with its world-ish translates, every joint (type/axis/bodies/limits/
drive), every rigid body's mass, and every collider.

    scripts/run.sh logs/p106/inspect_allegro.py
"""

from __future__ import annotations

import sys

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 200, "height": 150})

from pxr import Usd, UsdGeom, UsdPhysics

URL = (
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/"
    "Assets/Isaac/6.0/Isaac/Robots/WonikRobotics/AllegroHand/allegro.usd"
)
LOCAL = "/tmp/allegro.usd"


def say(msg: str) -> None:
    print(f"[p106] {msg}", flush=True)


def fmt(v) -> str:
    try:
        return "(" + ",".join(f"{float(x):+.4f}" for x in v) + ")"
    except TypeError:
        return str(v)


def main() -> int:
    stage = Usd.Stage.Open(LOCAL, Usd.Stage.LoadAll)
    if stage is None:
        say(f"FAILED to open {LOCAL}")
        return 1
    say(f"stage {LOCAL} default_prim={stage.GetDefaultPrim().GetPath()} "
        f"up={UsdGeom.GetStageUpAxis(stage)} mpu={UsdGeom.GetStageMetersPerUnit(stage)}")

    n_coll = 0
    n_mesh = 0
    bodies = []
    joints = []
    for prim in stage.Traverse():
        t = prim.GetTypeName()
        p = str(prim.GetPath())
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            n_coll += 1
        if t == "Mesh":
            n_mesh += 1
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            mass = None
            if prim.HasAPI(UsdPhysics.MassAPI):
                a = UsdPhysics.MassAPI(prim).GetMassAttr()
                mass = a.Get() if a else None
            bodies.append((p, mass, prim.HasAPI(UsdPhysics.CollisionAPI)))
        if "Joint" in t:
            joints.append((p, t, prim))
        if t in ("Xform", "Scope") and not p.count("/"):
            say(f"root-level: {p} ({t})")

    say(f"prims: colliders={n_coll} meshes={n_mesh} rigid_bodies={len(bodies)} joints={len(joints)}")
    say("rigid bodies (path, mass kg, has own CollisionAPI):")
    for p, m, c in bodies:
        say(f"  {p:60s} mass={m} coll={c}")

    say("joints:")
    for p, t, prim in joints:
        j = UsdPhysics.Joint(prim)
        b0 = [str(x) for x in (j.GetBody0Rel().GetTargets() or [])]
        b1 = [str(x) for x in (j.GetBody1Rel().GetTargets() or [])]
        extra = ""
        if t == "PhysicsRevoluteJoint":
            r = UsdPhysics.RevoluteJoint(prim)
            extra = f"axis={r.GetAxisAttr().Get()}"
            lo, hi = r.GetLowerLimitAttr().Get(), r.GetUpperLimitAttr().Get()
            extra += f" limits=({lo},{hi})"
        elif t == "PhysicsPrismaticJoint":
            pr = UsdPhysics.PrismaticJoint(prim)
            extra = f"axis={pr.GetAxisAttr().Get()}"
            lo, hi = pr.GetLowerLimitAttr().Get(), pr.GetUpperLimitAttr().Get()
            extra += f" limits=({lo},{hi})"
        drives = []
        for which in ("linear", "angular"):
            if prim.HasAPI(UsdPhysics.DriveAPI, which):
                d = UsdPhysics.DriveAPI(prim, which)
                drives.append(
                    f"{which}:type={d.GetTypeAttr().Get()} "
                    f"k={d.GetStiffnessAttr().Get()} c={d.GetDampingAttr().Get()} "
                    f"maxF={d.GetMaxForceAttr().Get()} target={d.GetTargetPositionAttr().Get()}"
                )
        say(f"  {p:44s} {t:24s} {extra} bodies=({b0},{b1}) drives={drives or 'NONE'}")

    say("articulation root(s):")
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            say(f"  {prim.GetPath()}")

    # The link tree with local translations, depth-limited, so a mount frame can
    # be picked from the real numbers rather than guessed.
    say("xform tree (translate/scale):")
    for prim in stage.Traverse():
        if prim.GetTypeName() not in ("Xform", "Scope"):
            continue
        g = UsdGeom.Xformable(prim)
        ops = []
        for op in g.GetOrderedXformOps():
            try:
                ops.append(f"{op.GetOpName()}={op.Get()}")
            except Exception:  # noqa: BLE001
                ops.append(op.GetOpName())
        if ops:
            say(f"  /{str(prim.GetPath()).lstrip('/'):52s} {' '.join(ops)}")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    sys.exit(code)
