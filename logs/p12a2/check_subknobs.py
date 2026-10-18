#!/usr/bin/env python3
"""P12-A.2 stub check: the property-realism component split, offline.

Tier-C-level implementation evidence - NOT a substitute for the Tier-A
component batteries (the P12-A.2 lane runs `FRUIT_PHYSICS_REAL_MASS=1` and
`FRUIT_PHYSICS_REAL_COMPLIANCE=1` on the two-line anchor, seeds 11/5/23; those
are a separate lane). Layers:

1. Source checks: each of the four knobs is read exactly once (`meshes.py`,
   the read-once convention) and `fruits.py` never reads the environment; the
   three component resolvers route through `_component_real` (explicit
   sub-knob wins with the exact `== "1"` parse, else the master); the
   consumption points read the right resolver (`fruit_density` -> mass,
   `restitution_range` -> rest, `fruit_contact_stiffness` -> compliance); the
   banner helper gates on the resolved components and keeps the committed
   P12-A text for the master all-on case; the mass formula / authoring sites /
   0.82 discount are unchanged.
2. The knob-off byte-identity (in-process, everything unset): the shipped
   numbers - the F4 density table, tomato 780 / apple stiffness 0.0 / band
   (0.02, 0.2), the draw byte-identical to the literal `uniform(0.02, 0.2)`,
   the tomato mass arithmetic - and the authored material (exactly the three
   shipped attributes, zero `PhysxMaterialAPI` applies, no banner). The
   offline `real=` seam still resolves to the P12-A tables.
3. The 8 component combinations (subprocesses; enumerated through the master +
   explicit sub-knob overrides): the resolved triple, the per-component
   shipped/real values, the authored mass, the authored material attributes
   (the compliant pair present only when the compliance component is on), and
   the banner text.
4. The master + override semantics (subprocesses): each sub-knob alone; an
   explicit `=0` under the master (mass + compliance only - the mission's
   example); the exact `== "1"` parse (`true` = off); sub-knobs-only all-on
   (the component banner, not the committed text); plus the read-once cache.
5. `rl_env.TASKS_MD5 == md5(tasks.py)` and tasks.py untouched.

Note: `logs/p12/check_physics_real.py` pins the committed single-switch P12-A
revision; its banner-gating check (`if physics_real():` exactly once) is the
one assertion the P12-A.2 split supersedes - this stub is the live one.

Run:  python3 logs/p12a2/check_subknobs.py
Exit code 0 = all checks PASS.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import random
import subprocess
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[2]
MESHES = ROOT / "src" / "fruit_sorting" / "meshes.py"
FRUITS = ROOT / "src" / "fruit_sorting" / "fruits.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"

#: The four knobs; the component order used by every expected triple below.
KNOBS = (
    "FRUIT_PHYSICS_REAL",
    "FRUIT_PHYSICS_REAL_MASS",
    "FRUIT_PHYSICS_REAL_REST",
    "FRUIT_PHYSICS_REAL_COMPLIANCE",
)

#: The knob-off configuration is the subject of the in-process layers: the env
#: must be unset before `meshes` caches the read-once constants.
for _knob in KNOBS:
    os.environ.pop(_knob, None)

sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.fruits --------- #
for name in ("pxr", "isaacsim", "isaacsim.core", "isaacsim.core.experimental"):
    sys.modules.setdefault(name, types.ModuleType(name))
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
app_mod = types.ModuleType("isaacsim.core.experimental.utils.app")
app_mod.update_app = lambda **kwargs: None
sys.modules.setdefault("isaacsim.core.experimental.utils.app", app_mod)
sys.modules.setdefault(
    "isaacsim.core.experimental.utils", types.ModuleType("isaacsim.core.experimental.utils")
)
prims_mod = types.ModuleType("isaacsim.core.experimental.prims")
prims_mod.RigidPrim = object
sys.modules.setdefault("isaacsim.core.experimental.prims", prims_mod)

import numpy as np  # noqa: E402

from fruit_sorting import fruits, meshes  # noqa: E402

#: The shipped density table (the P11-A audit F4 row, unchanged by P12-A).
SHIPPED_DENSITY = {
    "strawberry": 700.0,
    "lychee": 850.0,
    "kiwi": 900.0,
    "tomato": 780.0,
    "apple": 850.0,
    "orange": 900.0,
    "peach": 820.0,
    "pear": 880.0,
}
#: The P12-A real density table (audit section 2.1 + the marked estimates).
REAL_DENSITY = {
    "apple": 840.0,
    "pear": 950.0,
    "orange": 1000.0,
    "tomato": 960.0,
    "peach": 1000.0,
    "kiwi": 1050.0,
    "lychee": 1000.0,
    "strawberry": 950.0,
}
#: The P12-A real contact-stiffness table [N/m] (audit sections 2.2/5b.1).
REAL_STIFFNESS = {
    "apple": 27000.0,
    "pear": 15000.0,
    "orange": 13000.0,
    "tomato": 4000.0,
    "peach": 19000.0,
    "kiwi": 7000.0,
    "lychee": 23000.0,
    "strawberry": 3000.0,
}
SHIPPED_BAND = (0.02, 0.2)
REAL_BAND = (0.35, 0.50)
#: The three shipped material attributes and the two the compliant component
#: adds (the fruit-side spring-damper).
SHIPPED_ATTR_KEYS = ("dynamicFriction", "restitution", "staticFriction")
COMPLIANT_KEYS = (
    "physxMaterial:compliantContactDamping",
    "physxMaterial:compliantContactStiffness",
)
COMMITTED_BANNER = (
    "[physics] FRUIT_PHYSICS_REAL=1: real class densities + "
    "restitution 0.35-0.50 + per-class compliant contact (P12-A)"
)

#: The 8 component combinations, enumerated through the master + explicit
#: sub-knob overrides: (label, env overrides, (mass, rest, compliance),
#: banner kind). `components` = the P12-A.2 component line; `committed` = the
#: exact P12-A text (master on and every component resolved on).
COMBINATIONS = (
    ("all off", {}, (0, 0, 0), "none"),
    (
        "mass only (master=1 + rest=0 compliance=0)",
        {"FRUIT_PHYSICS_REAL": "1", "FRUIT_PHYSICS_REAL_REST": "0",
         "FRUIT_PHYSICS_REAL_COMPLIANCE": "0"},
        (1, 0, 0), "components",
    ),
    (
        "rest only (master=1 + mass=0 compliance=0)",
        {"FRUIT_PHYSICS_REAL": "1", "FRUIT_PHYSICS_REAL_MASS": "0",
         "FRUIT_PHYSICS_REAL_COMPLIANCE": "0"},
        (0, 1, 0), "components",
    ),
    (
        "compliance only (master=1 + mass=0 rest=0)",
        {"FRUIT_PHYSICS_REAL": "1", "FRUIT_PHYSICS_REAL_MASS": "0",
         "FRUIT_PHYSICS_REAL_REST": "0"},
        (0, 0, 1), "components",
    ),
    (
        "mass + rest (master=1 + compliance=0)",
        {"FRUIT_PHYSICS_REAL": "1", "FRUIT_PHYSICS_REAL_COMPLIANCE": "0"},
        (1, 1, 0), "components",
    ),
    (
        "mass + compliance (master=1 + rest=0)",
        {"FRUIT_PHYSICS_REAL": "1", "FRUIT_PHYSICS_REAL_REST": "0"},
        (1, 0, 1), "components",
    ),
    (
        "rest + compliance (master=1 + mass=0)",
        {"FRUIT_PHYSICS_REAL": "1", "FRUIT_PHYSICS_REAL_MASS": "0"},
        (0, 1, 1), "components",
    ),
    ("all three (master=1 alone)", {"FRUIT_PHYSICS_REAL": "1"}, (1, 1, 1), "committed"),
)

#: The master + override semantics rows (subprocesses): each sub-knob alone,
#: the exact parse, and the sub-knobs-only all-on (which is NOT the committed
#: banner: the master is not on).
SEMANTICS = (
    ("mass alone (sub-knob only)", {"FRUIT_PHYSICS_REAL_MASS": "1"}, (1, 0, 0), "components"),
    ("rest alone (sub-knob only)", {"FRUIT_PHYSICS_REAL_REST": "1"}, (0, 1, 0), "components"),
    (
        "compliance alone (sub-knob only)",
        {"FRUIT_PHYSICS_REAL_COMPLIANCE": "1"}, (0, 0, 1), "components",
    ),
    (
        "sub-knobs all on (no master)",
        {"FRUIT_PHYSICS_REAL_MASS": "1", "FRUIT_PHYSICS_REAL_REST": "1",
         "FRUIT_PHYSICS_REAL_COMPLIANCE": "1"},
        (1, 1, 1), "components",
    ),
    (
        "explicit sub-knob 0 under the master (the mission's example)",
        {"FRUIT_PHYSICS_REAL": "1", "FRUIT_PHYSICS_REAL_REST": "0"},
        (1, 0, 1), "components",
    ),
    (
        "explicit `true` under the master = off (the exact parse)",
        {"FRUIT_PHYSICS_REAL": "1", "FRUIT_PHYSICS_REAL_REST": "true"},
        (1, 0, 1), "components",
    ),
    (
        "sub-knob `true` alone = off (the exact parse)",
        {"FRUIT_PHYSICS_REAL_MASS": "true"}, (0, 0, 0), "none",
    ),
)

#: The tasks.py revision the P12-A/P12-A.2 baselines carry (the P11-C.3 tree);
#: this lane must not move it.
TASKS_MD5_BASELINE = "810658b802d22bbd63013726fc78af81"

failures: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


# --------------------------------------------------------------------------- #
# The recording fakes for the REAL material-authoring helper (the in-process
# knob-off layer). The subprocess layer carries its own full create-path fakes.
# --------------------------------------------------------------------------- #
ATTRS: dict[str, float] = {}
BINDS: list[tuple[str, str, str, str]] = []
PHYSX_APPLIES = [0]


class _FakeAttr:
    def __init__(self, key: str):
        self._key = key

    def Set(self, value):
        ATTRS[self._key] = value
        return self


class _FakePrim:
    def __init__(self, path: str):
        self.path = path


class _FakeMaterialDef:
    def __init__(self, path: str):
        self.path = path

    def GetPrim(self):
        return _FakePrim(self.path)


class _FakeUsdMaterialAPI:
    def __init__(self, prim):
        self._prim = prim

    def _attr(self, name: str):
        return _FakeAttr(f"{self._prim.path}:{name}")

    def CreateStaticFrictionAttr(self):
        return self._attr("staticFriction")

    def CreateDynamicFrictionAttr(self):
        return self._attr("dynamicFriction")

    def CreateRestitutionAttr(self):
        return self._attr("restitution")


class _FakePhysxMaterialAPI:
    def __init__(self, prim):
        self._prim = prim

    def CreateCompliantContactStiffnessAttr(self):
        return _FakeAttr(f"{self._prim.path}:physxMaterial:compliantContactStiffness")

    def CreateCompliantContactDampingAttr(self):
        return _FakeAttr(f"{self._prim.path}:physxMaterial:compliantContactDamping")


class _FakeBinding:
    def __init__(self, prim):
        self._prim = prim

    def Bind(self, material, strength, purpose):
        BINDS.append((self._prim.path, material.path, str(strength), str(purpose)))


def _physx_apply(prim):
    PHYSX_APPLIES[0] += 1
    return _FakePhysxMaterialAPI(prim)


def install_pxr_fakes() -> None:
    """Install the recording fakes on the stubbed pxr modules `fruits` bound."""
    pxr.UsdPhysics.MaterialAPI = type(
        "MaterialAPI", (), {"Apply": staticmethod(_FakeUsdMaterialAPI)}
    )
    pxr.PhysxSchema.PhysxMaterialAPI = type(
        "PhysxMaterialAPI", (), {"Apply": staticmethod(_physx_apply)}
    )
    pxr.UsdShade.Material = type(
        "Material", (), {"Define": staticmethod(lambda stage, path: _FakeMaterialDef(path))}
    )
    pxr.UsdShade.MaterialBindingAPI = type(
        "MaterialBindingAPI", (), {"Apply": staticmethod(_FakeBinding)}
    )
    pxr.UsdShade.Tokens = types.SimpleNamespace(weakerThanDescendants="weakerThanDescendants")


def author(stiffness: float, friction: float = 0.61, restitution: float = 0.11):
    """Run the REAL helper once and return (attrs, binds, physx applies)."""
    ATTRS.clear()
    BINDS.clear()
    PHYSX_APPLIES[0] = 0
    fruits._author_fruit_physics_material(
        None,
        _FakePrim("/World/Fruits/Fruit_00"),
        "/World/Fruits/Fruit_00",
        friction,
        restitution,
        stiffness,
    )
    return dict(ATTRS), list(BINDS), PHYSX_APPLIES[0]


# --------------------------------------------------------------------------- #
# The subprocess: resolve the knobs in a fresh interpreter and run the REAL
# `_create_fruit` path for one tomato against recording fakes, so the authored
# mass / material attributes are checked per combination.
# --------------------------------------------------------------------------- #
_SUBPROCESS_SCRIPT = """
import json, os, random, sys, types
sys.path.insert(0, os.path.join("@ROOT@", "src"))
for name in ("pxr", "isaacsim", "isaacsim.core", "isaacsim.core.experimental"):
    sys.modules.setdefault(name, types.ModuleType(name))
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType("pxr." + attr))
app_mod = types.ModuleType("isaacsim.core.experimental.utils.app")
app_mod.update_app = lambda **kwargs: None
sys.modules.setdefault("isaacsim.core.experimental.utils.app", app_mod)
sys.modules.setdefault("isaacsim.core.experimental.utils", types.ModuleType("isaacsim.core.experimental.utils"))
prims_mod = types.ModuleType("isaacsim.core.experimental.prims")
prims_mod.RigidPrim = object
sys.modules.setdefault("isaacsim.core.experimental.prims", prims_mod)

from fruit_sorting import fruits, meshes
from fruit_sorting.assets import SceneConfig

MASSES = {}
MATERIAL_ATTRS = {}
PHYSX_APPLIES = [0]

class AnyAttr:
    def __getattr__(self, name):
        return lambda *a, **k: self

class AnyPrim:
    def __init__(self, path="", *a, **k):
        self.path = path
    def GetPrim(self):
        return self
    def __getattr__(self, name):
        if name.startswith("Create") or name.endswith("Attr"):
            return lambda *a, **k: AnyAttr()
        return lambda *a, **k: AnyPrim()

class RecAttr:
    def __init__(self, sink, key):
        self._sink = sink
        self._key = key
    def Set(self, value):
        self._sink[self._key] = value
        return self

class RecMaterialAPI:
    def __init__(self, prim):
        self._prim = prim
    def _attr(self, name):
        return RecAttr(MATERIAL_ATTRS.setdefault(self._prim.path, {}), name)
    def CreateStaticFrictionAttr(self):
        return self._attr("staticFriction")
    def CreateDynamicFrictionAttr(self):
        return self._attr("dynamicFriction")
    def CreateRestitutionAttr(self):
        return self._attr("restitution")

class RecPhysxMaterialAPI:
    def __init__(self, prim):
        self._prim = prim
    def CreateCompliantContactStiffnessAttr(self):
        return RecAttr(MATERIAL_ATTRS.setdefault(self._prim.path, {}),
                       "physxMaterial:compliantContactStiffness")
    def CreateCompliantContactDampingAttr(self):
        return RecAttr(MATERIAL_ATTRS.setdefault(self._prim.path, {}),
                       "physxMaterial:compliantContactDamping")

def _physx_apply(prim):
    PHYSX_APPLIES[0] += 1
    return RecPhysxMaterialAPI(prim)

class RecMassAPI:
    def __init__(self, prim):
        self._prim = prim
    def CreateMassAttr(self):
        return RecAttr(MASSES, self._prim.path)

pxr.UsdGeom.Mesh = types.SimpleNamespace(Define=staticmethod(lambda stage, path: AnyPrim(path)))
pxr.UsdGeom.Cylinder = types.SimpleNamespace(Define=staticmethod(lambda stage, path: AnyPrim(path)))
pxr.UsdGeom.Xformable = staticmethod(lambda obj: obj)
pxr.UsdGeom.Tokens = types.SimpleNamespace(vertex="vertex")
pxr.UsdPhysics.RigidBodyAPI = types.SimpleNamespace(Apply=staticmethod(lambda prim: AnyAttr()))
pxr.UsdPhysics.MassAPI = types.SimpleNamespace(Apply=staticmethod(RecMassAPI))
pxr.UsdPhysics.CollisionAPI = types.SimpleNamespace(Apply=staticmethod(lambda prim: AnyAttr()))
pxr.UsdPhysics.MeshCollisionAPI = types.SimpleNamespace(Apply=staticmethod(lambda prim: AnyAttr()))
pxr.UsdPhysics.MaterialAPI = types.SimpleNamespace(Apply=staticmethod(RecMaterialAPI))
pxr.PhysxSchema.PhysxRigidBodyAPI = types.SimpleNamespace(Apply=staticmethod(lambda prim: AnyAttr()))
pxr.PhysxSchema.PhysxMaterialAPI = types.SimpleNamespace(Apply=staticmethod(_physx_apply))
pxr.UsdShade.Material = types.SimpleNamespace(Define=staticmethod(lambda stage, path: AnyPrim(path)))
pxr.UsdShade.MaterialBindingAPI = types.SimpleNamespace(Apply=staticmethod(lambda prim: AnyAttr()))
pxr.UsdShade.Shader = types.SimpleNamespace(Define=staticmethod(lambda stage, path: AnyPrim(path)))
pxr.UsdShade.Tokens = types.SimpleNamespace(weakerThanDescendants="weakerThanDescendants")
pxr.Sdf.ValueTypeNames = types.SimpleNamespace(Color3f="Color3f", Float="Float")
pxr.Gf.Vec3f = lambda *a: tuple(a)
pxr.Gf.Vec3d = lambda *a: tuple(a)

class FakeStage:
    def DefinePrim(self, path, typ):
        return AnyPrim(path)
    def GetPrimAtPath(self, path):
        return AnyPrim(path)
    def RemovePrim(self, path):
        pass

cfg = SceneConfig()
spawner = fruits.FruitSpawner(FakeStage(), cfg, seed=5)
spawner._create_fruit(0, "tomato")
sample = spawner.samples[0]
attrs = dict(MATERIAL_ATTRS.get(sample.prim_path + "_physmat", {}))

tomato = meshes.FRUIT_SHAPES["tomato"]
apple = meshes.FRUIT_SHAPES["apple"]
band = fruits.restitution_range()
out = {
    "master": meshes.physics_real(),
    "mass": meshes.physics_real_mass(),
    "rest": meshes.physics_real_rest(),
    "compliance": meshes.physics_real_compliance(),
    "raw": {
        "master": meshes._PHYSICS_REAL_RAW,
        "mass": meshes._PHYSICS_REAL_MASS_RAW,
        "rest": meshes._PHYSICS_REAL_REST_RAW,
        "compliance": meshes._PHYSICS_REAL_COMPLIANCE_RAW,
    },
    "tomato_density": meshes.fruit_density(tomato),
    "apple_stiffness": meshes.fruit_contact_stiffness(apple),
    "restitution": list(band),
    "draw": random.Random(7).uniform(*band),
    "diameter": sample.diameter,
    "mass_written": MASSES.get(sample.prim_path),
    "sample_mass": sample.mass,
    "attr_keys": sorted(attrs),
    "attr_values": attrs,
    "physx_applies": PHYSX_APPLIES[0],
    "banner": fruits._physics_banner(),
}
print(json.dumps(out))
"""


def run_case(env_overrides: dict[str, str]):
    """Run the subprocess with the four knobs cleared, plus `env_overrides`."""
    env = dict(os.environ)
    for knob in KNOBS:
        env.pop(knob, None)
    env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_SCRIPT.replace("@ROOT@", str(ROOT))],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        print(proc.stderr[-2000:])
        return None
    return json.loads(proc.stdout.strip().splitlines()[-1])


def check_case(
    label: str,
    env_overrides: dict[str, str],
    expected: tuple[int, int, int],
    banner_kind: str,
) -> float | None:
    """Check one env configuration: resolution, values, executed path, banner."""
    row = run_case(env_overrides)
    if row is None:
        check(f"{label}: the subprocess ran", False)
        return None
    mass_on, rest_on, compliance_on = expected
    master_on = env_overrides.get("FRUIT_PHYSICS_REAL") == "1"
    density = REAL_DENSITY["tomato"] if mass_on else SHIPPED_DENSITY["tomato"]
    stiffness = REAL_STIFFNESS["apple"] if compliance_on else 0.0
    band = REAL_BAND if rest_on else SHIPPED_BAND

    problems: list[str] = []
    got = (row["master"], row["mass"], row["rest"], row["compliance"])
    want = (master_on, bool(mass_on), bool(rest_on), bool(compliance_on))
    if got != want:
        problems.append(f"resolution {got} != {want}")
    want_raw = {
        "master": env_overrides.get("FRUIT_PHYSICS_REAL"),
        "mass": env_overrides.get("FRUIT_PHYSICS_REAL_MASS"),
        "rest": env_overrides.get("FRUIT_PHYSICS_REAL_REST"),
        "compliance": env_overrides.get("FRUIT_PHYSICS_REAL_COMPLIANCE"),
    }
    if row["raw"] != want_raw:
        problems.append(f"raw capture {row['raw']} != {want_raw}")
    if row["tomato_density"] != density:
        problems.append(f"tomato density {row['tomato_density']} != {density}")
    if row["apple_stiffness"] != stiffness:
        problems.append(f"apple stiffness {row['apple_stiffness']} != {stiffness}")
    if tuple(row["restitution"]) != band:
        problems.append(f"band {row['restitution']} != {list(band)}")
    if row["draw"] != random.Random(7).uniform(*band):
        problems.append("the draw is not the literal uniform at the resolved band")
    check(
        f"{label}: resolution {(mass_on, rest_on, compliance_on)}, density "
        f"{density:.0f}, stiffness {stiffness:.0f}, band {band}",
        not problems,
    )
    for item in problems:
        print(f"        ! {item}")

    problems = []
    diameter = row["diameter"]
    expected_mass = float(density * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3 * 0.82)
    if row["mass_written"] != expected_mass:
        problems.append(f"authored mass {row['mass_written']} != {expected_mass}")
    if row["sample_mass"] != expected_mass:
        problems.append(f"sample mass {row['sample_mass']} != {expected_mass}")
    want_keys = sorted(SHIPPED_ATTR_KEYS + (COMPLIANT_KEYS if compliance_on else ()))
    if row["attr_keys"] != want_keys:
        problems.append(f"attr keys {row['attr_keys']} != {want_keys}")
    if row["physx_applies"] != (1 if compliance_on else 0):
        problems.append(f"applies {row['physx_applies']} != {int(compliance_on)}")
    rest_attr = row["attr_values"].get("restitution")
    if rest_attr is None or not (band[0] <= rest_attr <= band[1]):
        problems.append(f"authored restitution {rest_attr} outside {band}")
    if compliance_on:
        if row["attr_values"].get("physxMaterial:compliantContactStiffness") != REAL_STIFFNESS["tomato"]:
            problems.append("authored compliant stiffness != the tomato class value")
        if row["attr_values"].get("physxMaterial:compliantContactDamping") != 80.0:
            problems.append("authored compliant damping != 80 Ns/m")
    check(
        f"{label}: executed create - mass {row['mass_written'] * 1e3:.1f} g, "
        f"{len(row['attr_keys'])} attrs, {row['physx_applies']} applies, "
        f"restitution {rest_attr}",
        not problems,
    )
    for item in problems:
        print(f"        ! {item}")

    if banner_kind == "none":
        want_banner = None
    elif banner_kind == "committed":
        want_banner = COMMITTED_BANNER
    else:
        want_banner = (
            "[physics] FRUIT_PHYSICS_REAL components: "
            f"mass={int(mass_on)} rest={int(rest_on)} "
            f"compliance={int(compliance_on)} (P12-A.2)"
        )
    check(
        f"{label}: banner {'none' if want_banner is None else repr(want_banner)}",
        row["banner"] == want_banner,
    )
    return diameter


def _mass_exprs(tree: ast.Module) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            name = None
            if isinstance(target, ast.Name):
                name = target.id
            elif isinstance(target, ast.Attribute):
                name = target.attr
            if name == "mass":
                out.append(ast.unparse(node.value))
    return out


def main() -> int:
    msrc = MESHES.read_text(encoding="utf-8")
    fsrc = FRUITS.read_text(encoding="utf-8")
    mtree = ast.parse(msrc)
    ftree = ast.parse(fsrc)

    # ---- 1. source checks ----------------------------------------------------
    print("== 1. source checks ==")
    check(
        "meshes.py reads each of the four knobs exactly once into its cached "
        "constant (the read-once convention)",
        msrc.count('os.environ.get("FRUIT_PHYSICS_REAL")') == 1
        and msrc.count('os.environ.get("FRUIT_PHYSICS_REAL_MASS")') == 1
        and msrc.count('os.environ.get("FRUIT_PHYSICS_REAL_REST")') == 1
        and msrc.count('os.environ.get("FRUIT_PHYSICS_REAL_COMPLIANCE")') == 1
        and '_PHYSICS_REAL_RAW = os.environ.get("FRUIT_PHYSICS_REAL")' in msrc
        and '_PHYSICS_REAL_MASS_RAW = os.environ.get("FRUIT_PHYSICS_REAL_MASS")' in msrc
        and '_PHYSICS_REAL_REST_RAW = os.environ.get("FRUIT_PHYSICS_REAL_REST")' in msrc
        and '_PHYSICS_REAL_COMPLIANCE_RAW = os.environ.get("FRUIT_PHYSICS_REAL_COMPLIANCE")' in msrc,
    )
    check(
        "the master parse is the exact `== \"1\"` (unset/0/other = shipped)",
        'return _PHYSICS_REAL_RAW == "1"' in msrc
        and "def physics_real() -> bool:" in msrc,
    )
    check(
        "the three component resolvers exist and route through `_component_real`",
        "def physics_real_mass() -> bool:" in msrc
        and "def physics_real_rest() -> bool:" in msrc
        and "def physics_real_compliance() -> bool:" in msrc
        and msrc.count("return _component_real(_PHYSICS_REAL_MASS_RAW)") == 1
        and msrc.count("return _component_real(_PHYSICS_REAL_REST_RAW)") == 1
        and msrc.count("return _component_real(_PHYSICS_REAL_COMPLIANCE_RAW)") == 1,
    )
    comp = next(
        n
        for n in ast.walk(mtree)
        if isinstance(n, ast.FunctionDef) and n.name == "_component_real"
    )
    comp_src = ast.unparse(comp)
    check(
        "`_component_real`: an explicit sub-knob wins with the exact parse, "
        "else the component follows the master",
        "if sub_raw is not None:" in comp_src
        and "return sub_raw == '1'" in comp_src
        and "return physics_real()" in comp_src,
    )
    check(
        "`fruit_density` reads the mass resolver, not the master "
        "(and no stale `on = physics_real()` consumption remains)",
        "on = physics_real_mass() if real is None else bool(real)" in msrc
        and "on = physics_real() if real is None" not in msrc
        and "on = physics_real() if real is None" not in fsrc,
    )
    check(
        "`fruit_contact_stiffness` reads the compliance resolver, not the master",
        "on = physics_real_compliance() if real is None else bool(real)" in msrc,
    )
    check(
        "fruits.py never reads the environment (all four knobs through the "
        "resolvers)",
        'os.environ.get("FRUIT_PHYSICS_REAL' not in fsrc,
    )
    check(
        "`restitution_range` reads the rest resolver, not the master",
        "on = physics_real_rest() if real is None else bool(real)" in fsrc,
    )
    check(
        "the banner helper exists; the committed P12-A text is kept for the "
        "master all-on case and the component line names the resolved states",
        "def _physics_banner() -> str | None:" in fsrc
        and '"[physics] FRUIT_PHYSICS_REAL=1: real class densities + "' in fsrc
        and '"[physics] FRUIT_PHYSICS_REAL components: "' in fsrc
        and "mass_on = physics_real_mass()" in fsrc
        and "rest_on = physics_real_rest()" in fsrc
        and "compliance_on = physics_real_compliance()" in fsrc
        and "if physics_real() and mass_on and rest_on and compliance_on:" in fsrc,
    )
    check(
        "create_pool prints the banner only when the helper returns one (the "
        "knob-off stream has no line)",
        "banner = _physics_banner()" in fsrc
        and "if banner is not None:" in fsrc
        and fsrc.count("say(banner)") == 1,
    )
    mass_exprs = _mass_exprs(ftree)
    check(
        "the two mass formulas are the shipped ones modulo `fruit_density` "
        "(the 0.82 discount untouched at both sites)",
        "float(fruit_density(shape) * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3 * 0.82)"
        in mass_exprs
        and "float(fruit_density(shape) * (4.0 / 3.0) * np.pi * "
        "(sample.diameter / 2.0) ** 3 * 0.82)" in mass_exprs
        and fsrc.count("* 0.82") == 2,
    )
    check(
        "both authoring sites still pass the component resolvers "
        "(`restitution_range()` + `fruit_contact_stiffness(shape)`)",
        fsrc.count("uniform(*restitution_range())") == 2
        and fsrc.count("fruit_contact_stiffness(shape)") == 2,
    )
    check(
        "one material-authoring helper definition + exactly two call sites; "
        "the compliant authoring in exactly one place",
        fsrc.count("def _author_fruit_physics_material(") == 1
        and fsrc.count("_author_fruit_physics_material(") == 3
        and fsrc.count("CreateCompliantContactStiffnessAttr") == 1
        and fsrc.count("CreateCompliantContactDampingAttr") == 1
        and fsrc.count("PhysxSchema.PhysxMaterialAPI") == 1,
    )

    # ---- 2. the knob-off byte-identity (in-process) --------------------------
    print("== 2. the knob-off byte-identity (in-process, everything unset) ==")
    check(
        "all four knobs resolve off and every raw constant is None",
        meshes.physics_real() is False
        and meshes.physics_real_mass() is False
        and meshes.physics_real_rest() is False
        and meshes.physics_real_compliance() is False
        and meshes._PHYSICS_REAL_RAW is None
        and meshes._PHYSICS_REAL_MASS_RAW is None
        and meshes._PHYSICS_REAL_REST_RAW is None
        and meshes._PHYSICS_REAL_COMPLIANCE_RAW is None,
    )
    shapes = meshes.FRUIT_SHAPES
    check(
        f"all 8 classes present ({sorted(shapes)})",
        set(shapes) == set(SHIPPED_DENSITY),
    )
    check(
        "the shipped `density` values are the audit's F4 table (unchanged)",
        {name: shape.density for name, shape in shapes.items()} == SHIPPED_DENSITY,
    )
    check(
        "the real density table is the P12-A table (unchanged by the split)",
        {name: shape.density_real for name, shape in shapes.items()} == REAL_DENSITY,
    )
    check(
        "the real contact-stiffness table is the P12-A table (unchanged)",
        {name: shape.contact_stiffness_real for name, shape in shapes.items()}
        == REAL_STIFFNESS,
    )
    off_densities = {
        name: meshes.fruit_density(shape, real=False) for name, shape in shapes.items()
    }
    on_densities = {
        name: meshes.fruit_density(shape, real=True) for name, shape in shapes.items()
    }
    check(
        "`fruit_density` (default, all knobs unset) = the shipped table; the "
        "`real=` seam still resolves the P12-A table, all 8 classes",
        {name: meshes.fruit_density(shape) for name, shape in shapes.items()}
        == SHIPPED_DENSITY
        and off_densities == SHIPPED_DENSITY
        and on_densities == REAL_DENSITY,
    )
    off_stiff = {
        name: meshes.fruit_contact_stiffness(shape, real=False)
        for name, shape in shapes.items()
    }
    on_stiff = {
        name: meshes.fruit_contact_stiffness(shape, real=True)
        for name, shape in shapes.items()
    }
    check(
        "`fruit_contact_stiffness`: default/off = 0.0 (rigid), the seam on = "
        "the class value, all 8 classes",
        {name: meshes.fruit_contact_stiffness(shape) for name, shape in shapes.items()}
        == {name: 0.0 for name in shapes}
        and off_stiff == {name: 0.0 for name in shapes}
        and on_stiff == REAL_STIFFNESS,
    )
    check(
        "`restitution_range`: default/off = (0.02, 0.2), the seam on = "
        "(0.35, 0.50)",
        fruits.restitution_range() == SHIPPED_BAND
        and fruits.restitution_range(real=False) == SHIPPED_BAND
        and fruits.restitution_range(real=True) == REAL_BAND,
    )
    check(
        "the shipped restitution draw is byte-identical to the literal "
        "`uniform(0.02, 0.2)`",
        random.Random(7).uniform(*fruits.restitution_range())
        == random.Random(7).uniform(0.02, 0.2),
    )
    check(
        "the real restitution draw is the literal `uniform(0.35, 0.50)`",
        random.Random(7).uniform(*fruits.restitution_range(real=True))
        == random.Random(7).uniform(0.35, 0.50),
    )
    check(
        "the compliant damping is the audit's 80 Ns/m",
        fruits.REAL_CONTACT_DAMPING == 80.0,
    )
    tomato = shapes["tomato"]
    diameter = 0.059
    volume = (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3 * 0.82
    off_mass = float(meshes.fruit_density(tomato) * volume)
    on_mass = float(meshes.fruit_density(tomato, real=True) * volume)
    check(
        "the mass arithmetic at a pinned diameter: default/off == the literal "
        f"780 kg/m^3 mass ({off_mass * 1e3:.1f} g at 59 mm)",
        off_mass == float(780.0 * volume),
    )
    check(
        "the seam on: the mass is the literal 960 kg/m^3 mass and is heavier "
        f"({on_mass * 1e3:.1f} g at 59 mm)",
        on_mass == float(960.0 * volume) and on_mass > off_mass,
    )
    check(
        "the banner is None with everything unset (the knob-off log stream "
        "has no line)",
        fruits._physics_banner() is None,
    )
    install_pxr_fakes()
    material_path = "/World/Fruits/Fruit_00_physmat"
    prim_path = "/World/Fruits/Fruit_00"
    attrs_off, binds_off, applies_off = author(0.0)
    check(
        "the knob-off authored material: exactly the shipped three "
        "attributes and zero `PhysxMaterialAPI` applies",
        attrs_off
        == {
            f"{material_path}:staticFriction": 0.61,
            f"{material_path}:dynamicFriction": 0.61,
            f"{material_path}:restitution": 0.11,
        }
        and applies_off == 0
        and binds_off == [(prim_path, material_path, "weakerThanDescendants", "physics")],
    )

    # ---- 3. the 8 component combinations (subprocesses) ----------------------
    print("== 3. the 8 component combinations (subprocesses, master + overrides) ==")
    diameters: dict[str, float] = {}
    for label, overrides, expected, banner_kind in COMBINATIONS:
        diameter = check_case(label, overrides, expected, banner_kind)
        if diameter is not None:
            diameters[label] = diameter
    check(
        "the drawn tomato diameter is identical in every combination (the "
        "knobs do not touch the rng stream)",
        len(set(diameters.values())) == 1 if diameters else False,
    )

    # ---- 4. the master + override semantics (subprocesses) -------------------
    print("== 4. the master + override semantics ==")
    for label, overrides, expected, banner_kind in SEMANTICS:
        diameter = check_case(label, overrides, expected, banner_kind)
        if diameter is not None:
            diameters[label] = diameter
    check(
        "the drawn tomato diameter is identical across every semantics row too",
        len(set(diameters.values())) == 1 if diameters else False,
    )
    os.environ.update({knob: "1" for knob in KNOBS})
    try:
        check(
            "read once: the env set after import does not move any knob (the "
            "cached constants; all four stay off)",
            meshes.physics_real() is False
            and meshes.physics_real_mass() is False
            and meshes.physics_real_rest() is False
            and meshes.physics_real_compliance() is False
            and meshes.fruit_density(shapes["tomato"]) == 780.0
            and meshes.fruit_contact_stiffness(shapes["apple"]) == 0.0
            and fruits.restitution_range() == SHIPPED_BAND
            and fruits._physics_banner() is None,
        )
    finally:
        for knob in KNOBS:
            os.environ.pop(knob, None)

    # ---- 5. rl_env pin / tasks.py untouched ----------------------------------
    print("== 5. rl_env pin / tasks.py untouched ==")
    tasks_md5 = hashlib.md5(TASKS.read_bytes()).hexdigest()
    pin = None
    for line in RL_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("TASKS_MD5"):
            pin = line.split('"')[1]
    check(f"rl_env TASKS_MD5 == live tasks.py md5 ({tasks_md5})", pin == tasks_md5)
    check(
        "tasks.py is untouched by this lane (the P11-C.3 baseline "
        f"{TASKS_MD5_BASELINE})",
        tasks_md5 == TASKS_MD5_BASELINE,
    )

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s) failed)")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(
        "RESULT: PASS (the four knobs are read once in meshes.py; every one of "
        "the 8 component combinations resolves to the shipped/real values per "
        "component through the master + override rule, and so do the sub-knob "
        "semantics; the executed create path authors the resolved mass, the "
        "shipped or real restitution band and the compliant pair only with "
        "the compliance component on; the knob-off numbers and the draw are "
        "byte-identical to the shipped literals; tasks.py and the TASKS_MD5 "
        "pin are untouched)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
