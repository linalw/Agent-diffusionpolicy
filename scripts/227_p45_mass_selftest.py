"""Offline selftest of the P45 mass-scale knob (`FRUIT_MASS_SCALE`).

    python3 scripts/227_p45_mass_selftest.py

No simulator. The **real** `_parse_mass_scale` / `mass_scale` /
`_mass_scale_banner` functions run (the `224` / `213` / `225` stub-the-imports
pattern), so what is pinned is the code the battery reads.

Why each item matters:

1. **Unset = byte-identical.** `mass_scale()` is `1.0` and the banner is
   `None`, and the two mass sites are written `if scale != 1.0:` - so the
   shipped float path is skipped *entirely*, not multiplied by `1.0`. That is
   the difference between "byte-identical by construction" and "byte-identical
   if the float round trip happens to be exact".
2. **The resolution table.** `0.5` / `0.25` parse; `1` / `1.0` / blank are the
   shipped value; `0`, a negative, `inf`/`nan` and a non-number are hard errors
   (a zero-mass body is not a scenario, and a silent fallback would let a typo
   read as the control arm).
3. **Both mass sites, both guarded.** `_create_fruit` (the pool build) and
   `rescale` (the recycled fruit - the site that is easy to miss) each multiply
   the authored mass behind the `!= 1.0` guard, and **nothing else in `src/`**
   multiplies a fruit mass: the knob is read at exactly one site
   (`meshes._MASS_SCALE_RAW`) and consumed through the resolver.
4. **The size does not move.** The knob appears in no `diameter`, `dimension`,
   mesh-authoring or `pinch_width` path - `grep`-level: the string
   `FRUIT_MASS_SCALE` occurs in `meshes.py` once and in no other `src/` file.
   That is the experiment: mass is the only variable.
5. **The inertia is derived, not authored.** `fruits.py` authors no
   `physics:diagonalInertia` / `CreateDiagonalInertiaAttr`, so PhysX derives the
   tensor from the collider at the authored mass (the census §1.4 derivation),
   and the one-shot runtime read-back (`_probe_mass_inertia`) exists and is
   gated on the knob - which is how the battery measures the claim instead of
   asserting it.

Run by `scripts/selfcheck.sh`.
"""

from __future__ import annotations

import ast
import os
import re
import sys
import types
from pathlib import Path

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.meshes/fruits --- #
for name in ("pxr", "isaacsim", "isaacsim.core", "isaacsim.core.experimental"):
    sys.modules.setdefault(name, types.ModuleType(name))
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
app_mod = types.ModuleType("isaacsim.core.experimental.utils.app")
app_mod.update_app = lambda **kwargs: None
sys.modules.setdefault("isaacsim.core.experimental.utils.app", app_mod)
sys.modules.setdefault("isaacsim.core.experimental.utils", types.ModuleType("isaacsim.core.experimental.utils"))
prims_mod = types.ModuleType("isaacsim.core.experimental.prims")
prims_mod.RigidPrim = object
sys.modules.setdefault("isaacsim.core.experimental.prims", prims_mod)

from fruit_sorting.fruits import _mass_scale_banner  # noqa: E402
from fruit_sorting.meshes import (  # noqa: E402
    _MASS_SCALE,
    _parse_mass_scale,
    mass_scale,
)

MESHES_SRC = Path(ROOT, "src", "fruit_sorting", "meshes.py").read_text(encoding="utf-8")
FRUITS_SRC = Path(ROOT, "src", "fruit_sorting", "fruits.py").read_text(encoding="utf-8")
SRC = Path(ROOT, "src", "fruit_sorting")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok: {message}")


def raises(raw: str) -> str:
    try:
        _parse_mass_scale(raw)
    except RuntimeError as exc:
        return str(exc)
    raise AssertionError(f"FRUIT_MASS_SCALE={raw!r} was accepted; it must be a hard error")


def mass_sites() -> list[ast.Assign]:
    """The two fruit-mass assignments in `fruits.py` (create + rescale).

    Matched on the shipped formula (`fruit_density(shape)`) rather than on the
    target name, so the old dead `mass = 700*V` line above the create site and
    the read-back's own local `mass` are not counted as mass sites.
    """
    tree = ast.parse(FRUITS_SRC)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [ast.unparse(t) for t in node.targets]
        if targets in (["mass"], ["sample.mass"]) and "fruit_density(shape)" in ast.unparse(node.value):
            out.append(node)
    return out


def main() -> int:
    print("P45 phase 2 - the mass-scale knob's offline contract")
    print("=" * 78)

    # [1] unset = the shipped value, and no banner (so no line in the stream).
    check(mass_scale() == 1.0, "unset resolves to 1.0 (the shipped mass)")
    check(_MASS_SCALE == 1.0, "the import-time constant is 1.0 when unset")
    check(_mass_scale_banner() is None, "unset prints no banner (byte-identical stream)")
    check(_parse_mass_scale(None) == 1.0 and _parse_mass_scale("") == 1.0
          and _parse_mass_scale("  ") == 1.0, "unset/blank/whitespace all resolve to 1.0")

    # [2] the resolution table.
    check(_parse_mass_scale("0.5") == 0.5, "0.5 parses to half mass")
    check(_parse_mass_scale("0.25") == 0.25, "0.25 parses to quarter mass")
    check(_parse_mass_scale("1") == 1.0 and _parse_mass_scale("1.0") == 1.0,
          "1 and 1.0 are the shipped value (the explicit control form)")
    check(_parse_mass_scale(" 0.5 ") == 0.5, "surrounding whitespace is tolerated")
    for raw in ("0", "-1", "-0.25", "inf", "nan"):
        message = raises(raw)
        check("finite and > 0" in message, f"{raw!r} is a hard error ({message[:46]}...)")
    message = raises("half")
    check("not a number" in message, f"a non-number is a hard error ({message[:46]}...)")

    # [3] both mass sites, guarded, and no other consumer.
    sites = mass_sites()
    check(len(sites) == 2, f"exactly two mass sites in fruits.py (found {len(sites)})")
    for node in sites:
        target = ast.unparse(node.targets[0])
        body = "\n".join(ast.unparse(n) for n in ast.walk(node))
        check("fruit_density(shape)" in body and "0.82" in body,
              f"{target}: still the shipped density*volume*0.82 formula")
    guarded = [
        node for node in ast.walk(ast.parse(FRUITS_SRC))
        if isinstance(node, ast.If)
        and "scale != 1.0" in ast.unparse(node.test)
    ]
    check(len(guarded) == 2,
          f"exactly two `if scale != 1.0:` guards in fruits.py (found {len(guarded)})")
    multiplied = [node for node in guarded if "*= scale" in ast.unparse(node)]
    check(len(multiplied) == 2,
          "both guards multiply in place (`mass *= scale` / `sample.mass *= scale`)")
    check("_rescale" not in FRUITS_SRC, "rescale is a method on the spawner (no stray copy)")
    # the recycled fruit is site two: `rescale` must reach the multiply.
    rescale = FRUITS_SRC.split("def rescale(")[-1].split("\n    def ")[0]
    check("sample.mass *= scale" in rescale,
          "rescale (the recycled fruit) applies the scale - the easy-to-miss site")

    # exactly one env read, in meshes.py, and no other src file consults it.
    reads = {
        path.name: path.read_text(encoding="utf-8").count('os.environ.get("FRUIT_MASS_SCALE")')
        for path in sorted(SRC.glob("*.py"))
    }
    reads = {name: count for name, count in reads.items() if count}
    check(reads == {"meshes.py": 1},
          f"the knob is read from the environment exactly once, in meshes.py: {reads}")
    check("def mass_scale(" in MESHES_SRC and "_MASS_SCALE = _parse_mass_scale(" in MESHES_SRC,
          "the resolver is `meshes.mass_scale()`, parsed once at import")

    # [4] the size does not move: no mass scale in any length path.
    for name in ("assets.py", "scene.py", "tasks.py"):
        text = (SRC / name).read_text(encoding="utf-8")
        check("FRUIT_MASS_SCALE" not in text and "mass_scale(" not in text,
              f"{name} does not read the mass scale (sizes/pinch spans untouched)")

    # [5] the inertia is derived, not authored - and the read-back exists.
    tree = ast.parse(FRUITS_SRC)
    authored = [
        ast.unparse(node.func) for node in ast.walk(tree)
        if (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("Create")
            and "nertia" in node.func.attr)
    ]
    # `physics:diagonalInertia` would be spelled as a string attribute author.
    code_lines = [
        line.split("#", 1)[0] for line in FRUITS_SRC.splitlines()
    ]
    string_authoring = [
        line.strip() for line in code_lines
        if "diagonalInertia" in line and "no fruit authors" not in line
        and "no `physics" not in line
    ]
    check(authored == [] and string_authoring == [],
          f"fruits.py authors no inertia (call or attribute), so PhysX derives it: "
          f"{authored + string_authoring}")
    check(re.search(r"def _probe_mass_inertia\(", FRUITS_SRC) is not None,
          "the one-shot mass/inertia read-back exists (census §9's open item)")
    probe_call = FRUITS_SRC.split("def refresh_rigids(")[-1].split("\n    def ")[0]
    check("_probe_mass_inertia()" in probe_call,
          "refresh_rigids calls the read-back (it runs before the attempt loop)")
    probe = FRUITS_SRC.split("def _probe_mass_inertia(")[-1].split("\n    def ")[0]
    check("if scale == 1.0" in probe,
          "the read-back is gated on the knob (no extra tensor call when shipped)")
    check("get_masses(" in probe and "get_inertias(" in probe,
          "the read-back reads BOTH mass and inertia from the tensor API")

    # the banner names the scale so every log can be grepped for its arm.
    check("mass_scale=" in FRUITS_SRC,
          "the build banner carries `mass_scale=<x>`")
    check("a physics experiment, not a " in FRUITS_SRC and '"fidelity claim; P45)"' in FRUITS_SRC,
          "the build banner says it is a physics experiment, not a fidelity claim")
    check("not a fidelity claim" in MESHES_SRC and "205-225 kg/m^3" in MESHES_SRC,
          "the named-file note says the same and names what 0.25x means physically")

    print("=" * 78)
    print("PASS: the mass knob is default-off, harsher-than-silent on a bad value, "
          "applied at both mass sites only, and the size cannot move")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
