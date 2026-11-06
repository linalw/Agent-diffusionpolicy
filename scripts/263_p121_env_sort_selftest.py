#!/usr/bin/env python3
"""P121 direct-env sort-instruction selftest (offline; selfcheck leg).

The P114 instruction layer was scripted-only: `SortingRLEnv` refused
`FRUIT_SORT_INSTRUCTION` because the direct/policy loop selected and placed
through its own grade lane (`bin_index = 0 if grade == "A" else 1`, the arm
chosen before the fruit was seen). P121 makes the direct env **use** the same
instruction, default off, with the unset path the shipped expression.

This leg pins, with no simulator:

* `direct_dispatch` - the un-instructed table (A -> 0/left, else 1/right, the
  shipped byte-identical path), today's routing as an instruction (the same
  table, so the goal channel keeps its trained value), a **non-grade** rule
  (destination independent of grade), and the refusal of a fruit the selector
  should never hand over (`skip` / unmatched -> `ValueError`, never a mis-sort).
* `unseen_destinations` - the goal channel's OOD gate (0/1 = trained, 2+ is the
  declared third-destination cell) and the env's refusal text.
* the **capability map**'s arm choice, including the existing P114 refusal of a
  destination no arm serves (the tray) - checked through `scenario`.
* the source wiring: `_begin_pick` dispatches through `direct_dispatch` and
  keeps `[fruit xyz, velocity, diameter, bin_index]`; `_run_primitive` sets the
  task's thread-local place target (`dispatch_destination`) and clears it in a
  `finally`; the ledger is called once per attempt; `_place_xy_for` stays the
  single place reader; the `bin_index` is an **input**, never an action channel
  (`_apply` is 7 joints + 1 finger).
* the handoff presentation still refuses (it has no dispatcher), and the direct
  env refuses an unseen destination unless `FRUIT_SORT_THIRD_DEST=1`.

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

# --- stub pxr / isaacsim just enough to import `assets`/`scenario` ---------- #
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
from fruit_sorting.rl_env import (  # noqa: E402
    TASKS_MD5,
    _md5,
    direct_dispatch,
    unseen_destinations,
)

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


def grab_method(src: str, name: str) -> str:
    """The method body from its `def` to the next same-indent `def`."""
    start = src.index(f"    def {name}(")
    end = src.find("\n    def ", start + 1)
    return src[start:end if end != -1 else len(src)]


def main() -> int:
    cfg = SceneConfig()
    shipped = scenario.shipped_descriptor(cfg)
    three = scenario.load_scenario(str(ROOT / "logs/p114/scenarios/three_dest.json"))

    today = scenario.parse_instruction(
        "grade=A => 0; grade=B => 1; grade=C => skip",
        shipped,
        grades=cfg.grades,
        species=tuple(cfg.fruit_dimensions),
    )
    by_size = scenario.parse_instruction(
        "size<40 => 1; default => 0",
        shipped,
        grades=cfg.grades,
        species=tuple(cfg.fruit_dimensions),
    )
    three_instr = scenario.parse_instruction(
        "grade=A => 2; grade=B => 1",
        three,
        grades=cfg.grades,
        species=tuple(cfg.fruit_dimensions),
    )

    def arm_of(descriptor, reach=None):
        table = scenario.instruction_against(descriptor, reach)
        caps = scenario.capability_map(descriptor, reach)
        return table, caps

    today_arm, today_caps = arm_of(shipped)
    three_arm, three_caps = arm_of(three)

    # ---------------------------------------------------------- 1 dispatch
    def fruit(grade, dia=0.06, species="apple"):
        return {
            "index": 0,
            "grade": grade,
            "category": species,
            "diameter": dia,
            "position": (0.30, 0.20, 1.27),
            "velocity": (0.0, -0.12, 0.0),
        }

    # un-instructed: the shipped expression, bit for bit
    for grade, expected in (("A", (0, "left")), ("B", (1, "right")),
                            ("C", (1, "right"))):
        check(
            direct_dispatch(fruit(grade), False, None, None) == expected,
            f"un-instructed {grade} -> {expected} (the shipped lane)",
        )

    # today's routing as an instruction: the same destination/arm table
    for grade, expected in (("A", (0, "left")), ("B", (1, "right"))):
        check(
            direct_dispatch(
                fruit(grade), True,
                lambda s: today.destination(today_attrs(s, today)),
                lambda d: today_arm[int(d)],
            ) == expected,
            f"today's instruction {grade} -> {expected} (no OOD goal value)",
        )
    # grade C is `skip`: the instructed selector never returns it; a caller
    # that hands it over anyway must refuse, not place.
    refuses(
        lambda: direct_dispatch(
            fruit("C"), True,
            lambda s: scenario.SKIP,
            lambda d: today_arm[int(d)],
        ),
        "REFUSED",
        "a skipped fruit is refused by the dispatcher",
    )
    refuses(
        lambda: direct_dispatch(
            fruit("B"), True,
            lambda s: None,
            lambda d: today_arm[int(d)],
        ),
        "REFUSED",
        "an unmatched (unassigned) fruit is refused by the dispatcher",
    )

    # a NON-grade instruction: the destination follows size, not grade - a
    # grade-A 35 mm fruit goes right and a grade-C 65 mm fruit goes left.
    check(
        direct_dispatch(
            fruit("A", 0.035), True,
            lambda s: by_size.destination(today_attrs(s, by_size)),
            lambda d: today_arm[int(d)],
        ) == (1, "right"),
        "size<40 sends a grade-A strawberry to the RIGHT lane (non-grade rule)",
    )
    check(
        direct_dispatch(
            fruit("C", 0.065), True,
            lambda s: by_size.destination(today_attrs(s, by_size)),
            lambda d: today_arm[int(d)],
        ) == (0, "left"),
        "the default sends a grade-C large fruit to the LEFT lane (non-grade rule)",
    )

    # third destination: the capability map's arm (left, +y), and the goal
    # value 2 is an unseen input -> the env's OOD gate names it.
    check(
        direct_dispatch(
            fruit("A"), True,
            lambda s: three_instr.destination(today_attrs(s, three_instr)),
            lambda d: three_arm[int(d)],
        ) == (2, "left"),
        "a third destination on +y is dispatched to the left arm",
    )
    check(three_caps["left"] == frozenset({0, 2}) and
          three_caps["right"] == frozenset({1}),
          "the capability map is left={0,2}, right={1}")
    check(unseen_destinations([0, 1]) == [], "0/1 are the trained goal values")
    check(unseen_destinations([0, 2]) == [2],
          "destination 2 is named an unseen goal value")
    check(unseen_destinations(three_instr.assigned_destinations()) == [2],
          "the three-destination instruction names 2 as OOD")

    # an unreachable destination (the tray) is not in the capability map - the
    # P114 refusal the env inherits. The shipped file marks the tray `auto`; the
    # refusal cell declares the startup solve's verdict (`unreachable`), which is
    # the state `_refresh_sort_capability` consumes.
    declared = json.loads(
        (ROOT / "logs/p114/scenarios/tray_unreachable.json").read_text()
    )
    declared["destinations"][2]["reach"] = {"status": "unreachable"}
    declared_path = Path(tempfile.mkdtemp(prefix="p121_tray_")) / "declared.json"
    declared_path.write_text(json.dumps(declared))
    tray = scenario.load_scenario(str(declared_path))
    tray_arm, tray_caps = arm_of(tray)
    check(3 not in tray_arm and 3 not in tray_caps["left"] and
          3 not in tray_caps["right"],
          "destination 3 (the unreachable tray) has no arm")
    refuses(
        lambda: direct_dispatch(
            fruit("A"), True,
            lambda s: 3,
            lambda d: tray_arm[int(d)],
        ),
        "3",
        "a destination with no arm refuses at dispatch",
    )

    # ------------------------------------------------------- 2 source wiring
    rl_src = (ROOT / "src/fruit_sorting/rl_env.py").read_text(encoding="utf-8")
    tasks_src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")
    begin = grab_method(rl_src, "_begin_pick")
    check(
        "bin_index, active = direct_dispatch(" in begin
        and "self._sort_armed" in begin,
        "_begin_pick dispatches through direct_dispatch",
    )
    check(
        "float(bin_index)," in begin
        and "self._goal = np.array(" in begin,
        "the goal channel keeps [xyz, velocity, diameter, bin_index]",
    )
    primitive = grab_method(rl_src, "_run_primitive")
    check(
        "self.task.dispatch_destination(result, self._bin_index)" in primitive
        and "self.task.clear_dispatch()" in primitive
        and "self.task.sort_ledger_attempt(result)" in primitive
        and "self._bin_index = int(result.destination)" in primitive,
        "_run_primitive sets/clears the place target, records the ledger, and "
        "adopts a mid-attempt re-dispatch",
    )
    apply_fn = grab_method(rl_src, "_apply")
    check(
        "action[:7]" in apply_fn and "action[7]" in apply_fn
        and "self.scene.robot.set_dof_position_targets(" in apply_fn
        and "action[7] = finger" in apply_fn
        and "action[8] = finger" in apply_fn,
        "the action is 7 joints + 1 finger (+ the recorded mirror): "
        "no destination channel",
    )
    check(
        "if presentation != \"direct\":" in rl_src
        and "FRUIT_SORT_INSTRUCTION is direct-only" in rl_src,
        "the handoff presentation still refuses the instruction",
    )
    check(
        "FRUIT_SORT_THIRD_DEST" in rl_src
        and "beyond the two shipped lanes" in rl_src,
        "the env gates an unseen destination behind FRUIT_SORT_THIRD_DEST",
    )
    dispatch_fn = grab_method(tasks_src, "dispatch_destination")
    check(
        'self._sort_ctx.place_xy = target' in dispatch_fn
        and "result.destination = int(destination)" in dispatch_fn
        and "result.place_xy =" in dispatch_fn,
        "dispatch_destination writes the thread-local target and the ledger fields",
    )
    armed_fn = grab_method(tasks_src, "instruction_armed")
    check("return self._instruction is not None" in armed_fn,
          "instruction_armed reads the resolved instruction")
    arm_fn = grab_method(tasks_src, "arm_for_destination")
    check("return self._arm_for_destination(int(destination))" in arm_fn,
          "arm_for_destination wraps the capability map")
    ledger_fn = grab_method(tasks_src, "sort_ledger_attempt")
    check(
        "self._sort_ledger_coverage()" in ledger_fn
        and "self._sort_ledger_row(result)" in ledger_fn,
        "sort_ledger_attempt is coverage + one attempt row",
    )
    place_fn = grab_method(tasks_src, "_place_xy_for")
    check(
        'override = getattr(self._sort_ctx, "place_xy", None)' in place_fn,
        "the place leg keeps reading the thread-local override",
    )
    check(
        "place_xy: tuple[float, float] | None = None" in rl_src,
        "carry_and_release takes a destination target (no lane-index IndexError)",
    )
    check(
        "self._sort_armed" in grab_method(rl_src, "_reseed_step")
        and "candidate_arm != self._active" in rl_src,
        "the reseed retry checks the capability arm, not the grade lane",
    )
    check(
        "_sort_provenance" in rl_src and '"sort": self._sort_provenance()' in rl_src,
        "a manifest recorded under an instruction carries the sort block",
    )
    check(
        TASKS_MD5 == _md5(str(ROOT / "src/fruit_sorting/tasks.py")),
        "rl_env.TASKS_MD5 matches tasks.py",
    )

    if FAILS:
        print(f"P121 direct-env sort selftest: {len(FAILS)} failure(s)")
        for msg in FAILS:
            print(f"  - {msg}")
        return 1
    print(f"P121 direct-env sort selftest: PASS ({CHECKS} checks)")
    return 0


def today_attrs(state: dict, instruction) -> dict:
    """The attribute dict `SortInstruction.destination` expects (dict form)."""
    return {
        "species": state.get("category", ""),
        "grade": state.get("grade", ""),
        "diameter": float(state.get("diameter", 0.0)),
        "ripeness": 0.0,
        "defective": 0.0,
    }


if __name__ == "__main__":
    raise SystemExit(main())
