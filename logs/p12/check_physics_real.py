#!/usr/bin/env python3
"""P12-A stub check: the property-realism batch (`FRUIT_PHYSICS_REAL`), offline.

Tier-C-level implementation evidence - NOT a substitute for the pre-registered
Tier-A battery (`logs/p12/run_battery.sh`: `FRUIT_PHYSICS_REAL=1` on the
two-line anchor, seeds 11/5/23; the battery is a separate lane). Layers:

1. Source checks: the knob is read exactly once (`meshes.py`, the read-once
   convention) and consumed through `physics_real()`; the shipped `FRUIT_SHAPES`
   numbers are unchanged; the mass formula is the shipped one modulo the
   density lookup (the 0.82 discount untouched); the inline restitution draws
   are gone (both sites go through `restitution_range()`); the material
   authoring is the single helper `_author_fruit_physics_material` called from
   both authoring sites; the helper consumes no rng (the draw stays at the
   call site, so the shipped rng stream is unchanged).
2. The value table under both settings: per class the shipped density
   (`real=False`) and the real density (`real=True`), the contact stiffness
   0.0 off / the class value on, the restitution bands, and the mass
   arithmetic at a pinned diameter.
3. The import-time resolution (subprocess): `FRUIT_PHYSICS_REAL` unset / `0` /
   `1` / `true`; and the read-once cache (setting the env after import does
   not move the switch).
4. The authored material (the REAL helper, run against recording fakes):
   knob off authors exactly friction + restitution and never applies
   `PhysxMaterialAPI`; knob on adds the compliant stiffness/damping with the
   class values.
5. `rl_env.TASKS_MD5 == md5(tasks.py)` and tasks.py untouched.

Run:  python3 logs/p12/check_physics_real.py
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

#: The knob-off configuration is the subject of this stub: the env must be
#: unset before `meshes` caches it (the read-once constant).
os.environ.pop("FRUIT_PHYSICS_REAL", None)

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

#: The tasks.py revision the P12-A baseline carries (the P11-C.3 tree; HEAD
#: `0feaf39`, tasks.py unchanged since `99e625c`); this lane must not move it.
TASKS_MD5_BASELINE = "810658b802d22bbd63013726fc78af81"

failures: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


# --------------------------------------------------------------------------- #
# The recording fakes for the REAL material-authoring helper.
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
# The import-time resolution subprocess (the env is read before `meshes`).
# --------------------------------------------------------------------------- #
_SUBPROCESS_SCRIPT = """
import json, os, sys, types
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
out = {
    "on": meshes.physics_real(),
    "raw": meshes._PHYSICS_REAL_RAW,
    "tomato": meshes.fruit_density(meshes.FRUIT_SHAPES["tomato"]),
    "apple_stiffness": meshes.fruit_contact_stiffness(meshes.FRUIT_SHAPES["apple"]),
    "restitution": list(fruits.restitution_range()),
}
print(json.dumps(out))
"""


def run_subprocess(env_state: str | None):
    env = dict(os.environ)
    if env_state is None:
        env.pop("FRUIT_PHYSICS_REAL", None)
    else:
        env["FRUIT_PHYSICS_REAL"] = env_state
    proc = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_SCRIPT.replace("@ROOT@", str(ROOT))],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout.strip().splitlines()[-1])


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
        "the env is read exactly once, into the cached module constant "
        "(`_PHYSICS_REAL_RAW = os.environ.get(\"FRUIT_PHYSICS_REAL\")`)",
        msrc.count('os.environ.get("FRUIT_PHYSICS_REAL")') == 1
        and '_PHYSICS_REAL_RAW = os.environ.get("FRUIT_PHYSICS_REAL")' in msrc,
    )
    check(
        "the exact `== \"1\"` parse (unset/0/other = shipped)",
        'return _PHYSICS_REAL_RAW == "1"' in msrc,
    )
    check(
        "fruits.py never reads the env directly (everything through "
        "`physics_real()`)",
        'os.environ.get("FRUIT_PHYSICS_REAL"' not in fsrc,
    )
    mass_exprs = _mass_exprs(ftree)
    check(
        "the `_create_fruit` mass formula is the shipped one modulo the "
        "density lookup (the preliminary 700 kg/m^3 line is untouched)",
        "float(fruit_density(shape) * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3 * 0.82)"
        in mass_exprs
        and "float(700.0 * (4.0 / 3.0) * np.pi * (diameter / 2.0) ** 3)" in mass_exprs,
    )
    check(
        "the `rescale` mass formula likewise",
        "float(fruit_density(shape) * (4.0 / 3.0) * np.pi * "
        "(sample.diameter / 2.0) ** 3 * 0.82)" in mass_exprs,
    )
    check(
        "the 0.82 sphere-shape discount is unchanged at both sites "
        "(the per-class volume proxy was not taken)",
        fsrc.count("* 0.82") == 2,
    )
    check(
        "the inline shipped restitution draws are gone: both authoring sites "
        "go through `restitution_range()`",
        fsrc.count("uniform(0.02, 0.2)") == 0
        and fsrc.count("uniform(*restitution_range())") == 2,
    )
    check(
        "one material-authoring helper definition + exactly two call sites "
        "(create + rescale)",
        fsrc.count("def _author_fruit_physics_material(") == 1
        and fsrc.count("_author_fruit_physics_material(") == 3,
    )
    check(
        "the compliant contact is authored in exactly one place (the helper)",
        fsrc.count("CreateCompliantContactStiffnessAttr") == 1
        and fsrc.count("CreateCompliantContactDampingAttr") == 1
        and fsrc.count("PhysxSchema.PhysxMaterialAPI") == 1,
    )
    call_args = [
        ast.unparse(call)
        for call in ast.walk(ftree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_author_fruit_physics_material"
    ]
    check(
        "both call sites pass the P12-A resolvers "
        "(`restitution_range()` + `fruit_contact_stiffness(shape)`)",
        len(call_args) == 2
        and all(
            "restitution_range()" in arg and "fruit_contact_stiffness(shape)" in arg
            for arg in call_args
        ),
    )
    helper = next(
        n
        for n in ast.walk(ftree)
        if isinstance(n, ast.FunctionDef) and n.name == "_author_fruit_physics_material"
    )
    check(
        "the helper consumes no rng (the restitution draw stays at the call "
        "site, so the shipped rng stream is unchanged)",
        not any(
            isinstance(n, ast.Attribute) and n.attr == "rng" for n in ast.walk(helper)
        ),
    )
    check(
        "the knob-on banner is gated on `physics_real()` (the knob-off log "
        "stream is byte-identical)",
        fsrc.count("if physics_real():") == 1
        and '"[physics] FRUIT_PHYSICS_REAL=1: real class densities + "' in fsrc,
    )
    check(
        "fruits.py imports the P12-A resolvers from meshes",
        "fruit_contact_stiffness," in fsrc
        and "fruit_density," in fsrc
        and "physics_real," in fsrc,
    )

    # ---- 2. the value table under both settings ------------------------------
    print("== 2. the value table under both settings ==")
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
        "the real density table is the P12-A table "
        "(tomato 780 -> 960; apple 850 -> 840; orange 900 -> 1000; "
        "peach 820 -> 1000; pear 880 -> 950; kiwi 900 -> 1050; "
        "lychee 850 -> 1000; strawberry 700 -> 950)",
        {name: shape.density_real for name, shape in shapes.items()} == REAL_DENSITY,
    )
    check(
        "the real contact-stiffness table is the P12-A table "
        "(tomato 4000; apple 27000; the rest by size/firmness)",
        {name: shape.contact_stiffness_real for name, shape in shapes.items()}
        == REAL_STIFFNESS,
    )
    off_densities = {name: meshes.fruit_density(shape, real=False) for name, shape in shapes.items()}
    on_densities = {name: meshes.fruit_density(shape, real=True) for name, shape in shapes.items()}
    check(
        "`fruit_density`: knob off = the shipped table, knob on = the real "
        "table, all 8 classes",
        off_densities == SHIPPED_DENSITY and on_densities == REAL_DENSITY,
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
        "`fruit_contact_stiffness`: 0.0 (rigid) off, the class value on, "
        "all 8 classes",
        off_stiff == {name: 0.0 for name in shapes} and on_stiff == REAL_STIFFNESS,
    )
    check(
        "the default switch (env unset in this process) resolves to the "
        "shipped numbers: tomato density 780, apple stiffness 0.0",
        meshes.fruit_density(shapes["tomato"]) == 780.0
        and meshes.fruit_contact_stiffness(shapes["apple"]) == 0.0,
    )
    check(
        "`restitution_range`: shipped (0.02, 0.2) / real (0.35, 0.50); the "
        "default (switch off) is shipped",
        fruits.restitution_range(real=False) == (0.02, 0.2)
        and fruits.restitution_range(real=True) == (0.35, 0.50)
        and fruits.restitution_range() == (0.02, 0.2),
    )
    check(
        "the shipped restitution draw is byte-identical to the literal "
        "`uniform(0.02, 0.2)`",
        random.Random(7).uniform(*fruits.restitution_range(real=False))
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
    off_mass = float(meshes.fruit_density(tomato, real=False) * volume)
    on_mass = float(meshes.fruit_density(tomato, real=True) * volume)
    check(
        "the mass arithmetic at a pinned diameter: off == the literal shipped "
        f"780 kg/m^3 mass ({off_mass * 1e3:.1f} g at 59 mm)",
        off_mass == float(780.0 * volume),
    )
    check(
        "knob on: the mass is the literal 960 kg/m^3 mass and is heavier "
        f"({on_mass * 1e3:.1f} g at 59 mm)",
        on_mass == float(960.0 * volume) and on_mass > off_mass,
    )

    # ---- 3. the import-time resolution (subprocess) --------------------------
    print("== 3. the import-time resolution (subprocess) ==")
    rows = {state: run_subprocess(state) for state in (None, "0", "1", "true")}
    check(
        "all four subprocesses ran",
        all(row is not None for row in rows.values()),
    )
    if all(row is not None for row in rows.values()):
        check(
            "env unset: off, tomato 780, apple stiffness 0.0, "
            "restitution (0.02, 0.2)",
            rows[None]["on"] is False
            and rows[None]["raw"] is None
            and rows[None]["tomato"] == 780.0
            and rows[None]["apple_stiffness"] == 0.0
            and rows[None]["restitution"] == [0.02, 0.2],
        )
        check(
            "env 0: the shipped numbers (the explicit off)",
            rows["0"]["on"] is False and rows["0"]["tomato"] == 780.0,
        )
        check(
            "env 1: on, tomato 960, apple stiffness 27000, "
            "restitution (0.35, 0.5)",
            rows["1"]["on"] is True
            and rows["1"]["raw"] == "1"
            and rows["1"]["tomato"] == 960.0
            and rows["1"]["apple_stiffness"] == 27000.0
            and rows["1"]["restitution"] == [0.35, 0.5],
        )
        check(
            "env `true`: off (the exact `== \"1\"` parse, like the other "
            "`FRUIT_*` flags)",
            rows["true"]["on"] is False and rows["true"]["tomato"] == 780.0,
        )
    os.environ["FRUIT_PHYSICS_REAL"] = "1"
    try:
        check(
            "read once: the env set after import does not move the switch "
            "(the cached constant)",
            meshes.physics_real() is False
            and meshes.fruit_density(meshes.FRUIT_SHAPES["tomato"]) == 780.0,
        )
    finally:
        os.environ.pop("FRUIT_PHYSICS_REAL", None)

    # ---- 4. the authored material (the REAL helper, recording fakes) ---------
    print("== 4. the authored material (the REAL helper, recording fakes) ==")
    install_pxr_fakes()
    material_path = "/World/Fruits/Fruit_00_physmat"
    prim_path = "/World/Fruits/Fruit_00"
    attrs_off, binds_off, applies_off = author(0.0)
    check(
        "knob off: exactly the shipped three attributes - static friction, "
        "dynamic friction, restitution - and nothing else",
        attrs_off
        == {
            f"{material_path}:staticFriction": 0.61,
            f"{material_path}:dynamicFriction": 0.61,
            f"{material_path}:restitution": 0.11,
        },
    )
    check(
        "knob off: `PhysxMaterialAPI` is never applied (no compliant "
        "attributes can exist)",
        applies_off == 0,
    )
    check(
        "knob off: the material is bound to the fruit prim with "
        "weakerThanDescendants/physics (the shipped binding)",
        binds_off == [(prim_path, material_path, "weakerThanDescendants", "physics")],
    )
    attrs_on, binds_on, applies_on = author(27000.0)
    check(
        "knob on: the compliant stiffness/damping are added with the class "
        "values (apple 27000 N/m, 80 Ns/m)",
        attrs_on
        == {
            f"{material_path}:staticFriction": 0.61,
            f"{material_path}:dynamicFriction": 0.61,
            f"{material_path}:restitution": 0.11,
            f"{material_path}:physxMaterial:compliantContactStiffness": 27000.0,
            f"{material_path}:physxMaterial:compliantContactDamping": 80.0,
        },
    )
    check(
        "knob on: `PhysxMaterialAPI` applied exactly once, same binding",
        applies_on == 1
        and binds_on == [(prim_path, material_path, "weakerThanDescendants", "physics")],
    )
    attrs_tomato, _, _ = author(4000.0)
    check(
        "knob on: the tomato 4000 N/m value is authored as passed",
        attrs_tomato.get(f"{material_path}:physxMaterial:compliantContactStiffness")
        == 4000.0,
    )

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
        "RESULT: PASS (the knob is read once in meshes.py with the exact "
        "`== \"1\"` parse; every per-class value resolves to the shipped "
        "number off and the real number on; the shipped mass arithmetic and "
        "restitution draw are byte-identical; the REAL material helper "
        "authors exactly friction + restitution off and adds the per-class "
        "compliant stiffness/damping on; the import-time truth table reads "
        "off/off/on/off for unset/0/1/true; tasks.py and the TASKS_MD5 pin "
        "are untouched)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
