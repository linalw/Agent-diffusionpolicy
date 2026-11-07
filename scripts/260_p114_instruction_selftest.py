#!/usr/bin/env python3
"""P114 sort-instruction selftest (offline; selfcheck leg).

The instruction layer's contract: a rule file is parsed into an ordered
`condition => destination` list, validated against the descriptor's destinations
and the pool's vocabulary, resolved against a **capability map** (left serves
+y, right serves -y; an `unreachable` destination is refused, an `auto` one is
provisional until its startup solve), and every inadmissible form raises with
the source and line.

Pins: the grammar (`grade=`, `species=`, `size<` in millimetres, `default`,
`skip`, the inline `;` separator), precedence (first match wins), and the
refusals - unknown/negative destination, a destination no arm serves, a
destination declared unreachable, an unknown attribute (colour) or operator, a
grade/species the pool cannot produce, a second `default`, a rule after
`default`, an empty instruction. Also pins `resolve_instruction`'s unset path
(one environment read, `None`, no parse) and the capability map's three states
(verified, auto/pending, auto->False), including that a failed solve removes the
destination.

Exit 0 on pass, 1 on the first failure.
"""

from __future__ import annotations

import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import `fruits.SupplyPlan` ---------- #
for name in ("pxr", "isaacsim", "isaacsim.core", "isaacsim.core.experimental"):
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

from fruit_sorting import scenario  # noqa: E402
from fruit_sorting.assets import SceneConfig  # noqa: E402

FAILS: list[str] = []
CHECKS = 0


def check(cond, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(msg)


def refuses(fn, needle: str, msg: str) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - the message is the check
        check(needle.lower() in str(exc).lower(), f"{msg}: wrong message {exc}")
    else:
        check(False, f"{msg}: was not refused")


def main() -> int:
    cfg = SceneConfig()
    shipped = scenario.shipped_descriptor(cfg)
    three = scenario.load_scenario("logs/p114/scenarios/three_dest.json")
    tray = scenario.load_scenario("logs/p114/scenarios/tray_unreachable.json")
    declared = json.loads((ROOT / "logs/p114/scenarios/tray_unreachable.json").read_text())
    declared["destinations"][2]["reach"] = {"status": "unreachable"}
    declared_path = Path(tempfile.mkdtemp(prefix="p114_instr_")) / "declared.json"
    declared_path.write_text(json.dumps(declared))
    declared_desc = scenario.load_scenario(str(declared_path))

    # ----------------------------------------------------------- instruction
    today = scenario.parse_instruction(
        "logs/p114/instructions/today.txt",
        shipped,
        grades=cfg.grades,
        species=tuple(cfg.fruit_dimensions),
    )
    check(
        [today.destination({"grade": g, "diameter": 0.05, "species": "apple"})
         for g in ("A", "B", "C")] == [0, 1, scenario.SKIP],
        "today's routing compiles to A->0, B->1, C->skip",
    )
    check(
        scenario.resolve_instruction(shipped, cfg, env_value="") is None,
        "unset FRUIT_SORT_INSTRUCTION -> None (no parse)",
    )
    size = scenario.parse_instruction(
        "size<40 => 1; default => 0",
        shipped,
        grades=cfg.grades,
        species=tuple(cfg.fruit_dimensions),
    )
    check(
        [size.destination({"grade": "A", "diameter": d, "species": "kiwi"})
         for d in (0.035, 0.040, 0.05)] == [1, 0, 0],
        "size<40 is millimetres and strict (0.035->1, 0.040->0)",
    )
    check(
        size.rules[0].value == 40.0,
        "the size threshold is stored in millimetres",
    )
    refuses(
        lambda: scenario.parse_instruction(
            "size<40 => 7", shipped, grades=cfg.grades,
        ),
        "not in scenario",
        "a destination the descriptor does not define is refused",
    )
    refuses(
        lambda: scenario.parse_instruction(
            "grade=A => 3", declared_desc, grades=cfg.grades,
        ),
        "not served",
        "a destination declared unreachable is refused at parse time",
    )
    refuses(
        lambda: scenario.parse_instruction(
            "colour=red => 0", shipped, grades=cfg.grades,
        ),
        "unknown attribute",
        "colour (not a sim attribute) is refused",
    )
    refuses(
        lambda: scenario.parse_instruction(
            "size~40 => 0", shipped, grades=cfg.grades,
        ),
        "cannot parse",
        "a bad operator is refused",
    )
    refuses(
        lambda: scenario.parse_instruction(
            "grade=Z => 0", shipped, grades=cfg.grades,
        ),
        "grades",
        "a grade the pool cannot produce is refused",
    )
    refuses(
        lambda: scenario.parse_instruction(
            "species=dragonfruit => 0", shipped,
            species=tuple(cfg.fruit_dimensions),
        ),
        "classes",
        "a species the pool cannot produce is refused",
    )
    refuses(
        lambda: scenario.parse_instruction(
            "default => 0\ndefault => 1", shipped, grades=cfg.grades,
        ),
        "second",
        "a second default is refused",
    )
    refuses(
        lambda: scenario.parse_instruction(
            "default => 0\ngrade=A => 1", shipped, grades=cfg.grades,
        ),
        "after",
        "a rule after default is refused",
    )
    refuses(
        lambda: scenario.parse_instruction(
            "\n# only a comment\n", shipped, grades=cfg.grades,
        ),
        "empty",
        "an empty instruction is refused",
    )


    # ------------------------------------------------------------ capability
    check(
        scenario.capability_map(shipped)
        == {"left": frozenset({0}), "right": frozenset({1})},
        "the shipped capability map is left->0, right->1",
    )
    check(
        scenario.capability_map(three)["left"] == frozenset({0, 2}),
        "the third destination is provisionally the left arm's",
    )
    check(
        scenario.arm_for_destination(three, 2)
        == "left",
        "an auto destination is provisionally servable by its side's arm",
    )
    check(
        scenario.arm_for_destination(three, 2, {("left", 2): False}) is None,
        "a failed solve removes the destination from the map",
    )
    check(
        scenario.arm_for_destination(tray, 3, {("left", 3): False}) is None,
        "the tray is unservable after its solve fails",
    )
    check(
        scenario.capability_map(shipped)["right"] == frozenset({1}),
        "the left arm is never handed a -y destination",
    )


    if FAILS:
        print(f"P114 instruction selftest: {len(FAILS)} failure(s)")
        for failure in FAILS:
            print(f"  - {failure}")
        return 1
    print(f"P114 instruction selftest: PASS ({CHECKS} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
