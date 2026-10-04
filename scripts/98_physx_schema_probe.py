"""List the PhysX knobs this build actually exposes for contact stability.

    $ISAAC_SIM_DIR/python.sh scripts/98_physx_schema_probe.py

Prints the rigid-body / material / scene attributes whose names look like
contact-compliance, damping, solver or depenetration controls, so the grip model
can be tuned with settings that exist rather than ones that sound plausible.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import carb
from pxr import PhysxSchema

KEYS = ("ompliant", "amping", "epenetration", "olver", "ontact", "Stiffness", "Iteration")


def report(label: str, obj) -> None:
    names = [n for n in dir(obj) if any(k in n for k in KEYS)]
    print(f"== {label} ({len(names)} matches) ==")
    for name in names:
        print("   ", name)


report("PhysxRigidBodyAPI", PhysxSchema.PhysxRigidBodyAPI)
report("PhysxMaterialAPI", getattr(PhysxSchema, "PhysxMaterialAPI", object))
report("PhysxSceneAPI", getattr(PhysxSchema, "PhysxSceneAPI", object))
report("PhysxCollisionAPI", getattr(PhysxSchema, "PhysxCollisionAPI", object))
report("PhysxShapeAPI", getattr(PhysxSchema, "PhysxShapeAPI", object))

settings = carb.settings.get_settings()
print("== relevant carb settings ==")
for path in (
    "/physics/solverType",
    "/physics/numPositionIterations",
    "/physics/numVelocityIterations",
    "/physics/updateToUsd",
    "/persistent/physics/solverType",
):
    print(f"    {path} = {settings.get(path)}")
print("solverType meaning: 0 = PGS (default), 1 = TGS")

simulation_app.close()
