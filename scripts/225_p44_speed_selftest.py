"""Offline selftest of the P44 speed cells (`FRUIT_SPEED_PLACE/_RELEASE/_LIFT`).

    python3 scripts/225_p44_speed_selftest.py

No simulator. The **real** `speed_cell_defaults` resolver runs (the `224` / `213`
stub-the-imports pattern), so what is pinned is the code the runs read.

Why each item matters:

1. **Unset = byte-identical.** With no cell set, the resolver returns exactly the
   shipped default *strings* (`_SPEED_SHIPPED`), i.e. the same literals the read
   sites carried before P44 - so `os.environ.get` falls back to the same value
   and the shipped path cannot move. The test asserts the dict equals the
   shipped one **and** that each value is a string (a float formatting round
   trip is the way this could silently drift).
2. **One knob per cell, the registered values.** S1 `place` -> 0.52 (with
   `a_max` left at the shipped 1.089: 0.52 is inside the census's 0.61 m/s
   ceiling, so the acceleration term does not bind and the raise spends no cone
   margin); S3 `lift` -> 0.36 / 1.9 (the 1.962 m/s^2 vertical cone budget's
   ceiling); S2 `release` -> dwell 0 / pad 2 / finger 2.
3. **An explicit per-leg override still wins.** `FRUIT_DYNAMIC_PLACE_VMAX`,
   `FRUIT_DYNAMIC_LIFT_VMAX/_AMAX`, `FRUIT_DYNAMIC_PLACE_AMAX`,
   `FRUIT_RELEASE_DWELL/_PAD_HOLD/_FINGER_HOLD` and
   `FRUIT_SPEED_RELEASE_SETTLE` beat the cell default, which is the contract the
   docstrings state - so a measured cell stays decomposable.
4. **`FRUIT_SPEED_ALL` is the union (S13), and an explicit single cell wins over
   it**; `0`/`off` is off on every cell.
5. **A numeric value is that speed** (the attribution form), and a caller's own
   place speed scales `a_max` on the shipped shape `a = 0.20*(v/0.15)^2`.
6. **The read sites are the resolver's** (AST): the three `FRUIT_RELEASE_*`
   hold reads, the two `FRUIT_DYNAMIC_LIFT_*` reads and the two
   `FRUIT_DYNAMIC_PLACE_*` reads take `_speed[...]` as their default, and the
   place cap is **assigned** (not `min()`'d against `FRUIT_CARRY_VMAX` 0.38,
   which would silently resolve the 0.52 cell to 0.38).
7. **`TASKS_MD5` provenance** is `224`'s item; not duplicated here.

Run by `scripts/selfcheck.sh`.
"""

from __future__ import annotations

import ast
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.tasks ---------- #
for name in (
    "pxr",
    "isaacsim",
    "isaacsim.core",
    "isaacsim.core.experimental",
    "isaacsim.sensors",
    "isaacsim.sensors.experimental",
):
    sys.modules.setdefault(name, types.ModuleType(name))
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
app_mod = types.ModuleType("isaacsim.core.experimental.utils.app")
app_mod.update_app = lambda **kwargs: None
sys.modules.setdefault("isaacsim.core.experimental.utils.app", app_mod)
utils_mod = types.ModuleType("isaacsim.core.experimental.utils")
sys.modules.setdefault("isaacsim.core.experimental.utils", utils_mod)
prims_mod = types.ModuleType("isaacsim.core.experimental.prims")
prims_mod.RigidPrim = object
sys.modules.setdefault("isaacsim.core.experimental.prims", prims_mod)
sim_mod = types.ModuleType("isaacsim.core.simulation_manager")
sim_mod.SimulationManager = SimpleNamespace(step=staticmethod(lambda **kw: None))
sys.modules.setdefault("isaacsim.core.simulation_manager", sim_mod)
render_mod = types.ModuleType("isaacsim.core.rendering_manager")
render_mod.RenderingManager = SimpleNamespace(render=staticmethod(lambda: None))
sys.modules.setdefault("isaacsim.core.rendering_manager", render_mod)
sensors_mod = types.ModuleType("isaacsim.sensors.experimental.physics")
sensors_mod.Contact = object
sensors_mod.ContactSensor = object
sys.modules.setdefault("isaacsim.sensors.experimental.physics", sensors_mod)

from fruit_sorting.tasks import (  # noqa: E402
    _SPEED_SHIPPED,
    speed_cell_defaults,
)

TASKS_SRC = Path(ROOT, "src", "fruit_sorting", "tasks.py").read_text(encoding="utf-8")
SPEED_ENVS = (
    "FRUIT_SPEED_PLACE",
    "FRUIT_SPEED_PLACE_AMAX",
    "FRUIT_SPEED_RELEASE",
    "FRUIT_SPEED_RELEASE_SETTLE",
    "FRUIT_SPEED_LIFT",
    "FRUIT_SPEED_LIFT_AMAX",
    "FRUIT_SPEED_ALL",
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok: {message}")


class cells:
    """Set exactly the given speed-cell env vars for the duration of the block."""

    def __init__(self, **env: str):
        self.env = env

    def __enter__(self):
        for name in SPEED_ENVS:
            os.environ.pop(name, None)
        for name, value in self.env.items():
            os.environ[name] = str(value)
        return speed_cell_defaults()

    def __exit__(self, *exc):
        for name in SPEED_ENVS:
            os.environ.pop(name, None)
        return False


def main() -> int:
    print("P44 phase 2 - the speed cells' offline contract")
    print("=" * 78)

    # [1] unset = the shipped strings, exactly.
    with cells() as d:
        check(d == _SPEED_SHIPPED, f"unset resolves to the shipped dict {_SPEED_SHIPPED}")
        check(all(isinstance(v, str) for v in d.values()),
              "every shipped default is a string (no float round-trip)")
        check(d["place_vmax"] == "0.35" and d["place_amax"] == "1.089",
              "the place pair is the shipped 0.35 / 1.089")
        check(d["lift_vmax"] == "0.30" and d["lift_amax"] == "1.0",
              "the lift pair is the shipped 0.30 / 1.0")
        check((d["release_dwell"], d["release_pad_hold"], d["release_finger_hold"])
              == ("20", "3", "3"), "the three release holds are the shipped 20 / 3 / 3")
    with cells(FRUIT_SPEED_ALL="0", FRUIT_SPEED_PLACE="0", FRUIT_SPEED_LIFT="0",
               FRUIT_SPEED_RELEASE="0") as d:
        check(d == _SPEED_SHIPPED, "an explicit 0 on every cell is off (shipped dict)")

    # [2] the registered cells.
    with cells(FRUIT_SPEED_PLACE="1") as d:
        check(d["place_vmax"] == "0.52", "S1: place v_max -> 0.52")
        check(d["place_amax"] == "1.089",
              "S1 keeps a_max at the shipped 1.089 (0.52 < the census's 0.61 m/s ceiling)")
        check(d["lift_vmax"] == "0.30" and d["release_dwell"] == "20",
              "S1 does not touch the lift or the release")
    with cells(FRUIT_SPEED_LIFT="1") as d:
        check(d["lift_vmax"] == "0.36" and d["lift_amax"] == "1.9",
              "S3: lift 0.36 / 1.9 (the 1.962 m/s^2 vertical cone ceiling)")
        check(d["place_vmax"] == "0.35" and d["release_dwell"] == "20",
              "S3 does not touch the place or the release")
    with cells(FRUIT_SPEED_RELEASE="1") as d:
        check((d["release_dwell"], d["release_pad_hold"], d["release_finger_hold"])
              == ("0", "2", "2"), "S2: dwell 20 -> 0, pad/finger settle 3 -> 2")
        check(d["place_vmax"] == "0.35" and d["lift_vmax"] == "0.30",
              "S2 does not touch the profiles")

    # [3] the explicit per-leg overrides still win (the documented contract).
    with cells(FRUIT_SPEED_PLACE="1", FRUIT_DYNAMIC_PLACE_VMAX="0.61",
               FRUIT_SPEED_LIFT="1", FRUIT_DYNAMIC_LIFT_VMAX="0.33") as d:
        check(d["place_vmax"] == "0.52" and d["lift_vmax"] == "0.36",
              "the resolver is the *default*; an explicit FRUIT_DYNAMIC_* wins at the read site")
    with cells(FRUIT_SPEED_RELEASE="1", FRUIT_SPEED_RELEASE_SETTLE="1") as d:
        check((d["release_pad_hold"], d["release_finger_hold"]) == ("1", "1"),
              "the 3 -> 1 form is one value (FRUIT_SPEED_RELEASE_SETTLE=1)")
    with cells(FRUIT_SPEED_RELEASE="1", FRUIT_SPEED_RELEASE_SETTLE="3") as d:
        check(d["release_dwell"] == "0" and d["release_pad_hold"] == "3",
              "the settle alone is overridable (the dwell is the cell's other half)")

    # [4] S13 is the union; an explicit single cell wins over it.
    with cells(FRUIT_SPEED_ALL="1") as d:
        check((d["place_vmax"], d["lift_vmax"]) == ("0.52", "0.36"),
              "S13: the place and the lift cells are on")
        check((d["release_dwell"], d["release_pad_hold"], d["release_finger_hold"])
              == ("0", "2", "2"), "S13: the release cell is on")
    with cells(FRUIT_SPEED_ALL="1", FRUIT_SPEED_PLACE="0.61") as d:
        check(d["place_vmax"] == "0.61" and d["lift_vmax"] == "0.36",
              "an explicit single cell overrides S13")

    # [5] a numeric value is that speed, and scales the pair on the shipped shape.
    with cells(FRUIT_SPEED_PLACE="0.61") as d:
        check(d["place_vmax"] == "0.61", "a numeric place value is that speed")
        check(abs(float(d["place_amax"]) - 0.20 * (0.61 / 0.15) ** 2) < 5e-5,
              f"a caller's own place speed scales a_max on a = 0.20*(v/0.15)^2 "
              f"({d['place_amax']})")
    with cells(FRUIT_SPEED_LIFT="0.371") as d:
        check(d["lift_vmax"] == "0.371", "a numeric lift value is that speed")
    with cells(FRUIT_SPEED_LIFT="0.36", FRUIT_SPEED_LIFT_AMAX="1.0") as d:
        check(d["lift_amax"] == "1.0", "the lift acceleration pin is the grip-risk control")
    with cells(FRUIT_SPEED_PLACE="nonsense") as d:
        check(d == _SPEED_SHIPPED, "a non-numeric value leaves the cell off")

    # [6] the read sites take the resolver's defaults (AST).
    tree = ast.parse(TASKS_SRC)
    calls: list[tuple[str, str, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            continue
        if len(node.args) < 2 or not isinstance(node.args[0], ast.Constant):
            continue
        name = node.args[0].value
        if not isinstance(name, str) or not name.startswith("FRUIT_"):
            continue
        default = node.args[1]
        uses = (
            isinstance(default, ast.Subscript)
            and isinstance(default.value, ast.Name)
            and default.value.id == "_speed"
        )
        if name in (
            "FRUIT_DYNAMIC_PLACE_VMAX", "FRUIT_DYNAMIC_PLACE_AMAX",
            "FRUIT_DYNAMIC_LIFT_VMAX", "FRUIT_DYNAMIC_LIFT_AMAX",
            "FRUIT_RELEASE_DWELL", "FRUIT_RELEASE_PAD_HOLD",
            "FRUIT_RELEASE_FINGER_HOLD",
        ):
            calls.append((name, ast.unparse(default), uses))
    names = {name for name, _, uses in calls if uses}
    check(names == {
        "FRUIT_DYNAMIC_PLACE_VMAX", "FRUIT_DYNAMIC_PLACE_AMAX",
        "FRUIT_DYNAMIC_LIFT_VMAX", "FRUIT_DYNAMIC_LIFT_AMAX",
        "FRUIT_RELEASE_DWELL", "FRUIT_RELEASE_PAD_HOLD", "FRUIT_RELEASE_FINGER_HOLD",
    }, f"all seven read sites default to the resolver ({len(calls)} reads)")
    check(all(uses for _, _, uses in calls),
          "every one of those reads takes `_speed[...]`, not a literal")

    # the place cap is assigned: a min() against FRUIT_CARRY_VMAX (0.38) would
    # silently resolve the 0.52 cell to 0.38.
    assign = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Name)
            and node.value.id == "place_v"
            and isinstance(node.targets[0], ast.Attribute)
            and node.targets[0].attr == "v_max"
        ):
            assign = node
    check(assign is not None, "the place cap is assigned (`limits.v_max = place_v`), not min()'d")
    check("_speed = speed_cell_defaults()" in TASKS_SRC,
          "both consumers build the resolver dict (`_speed = speed_cell_defaults()`)")

    print("=" * 78)
    print("PASS: the speed cells are default-off, one knob each, and the shipped strings win when unset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
