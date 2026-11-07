#!/usr/bin/env python3
"""P114 scenario-descriptor + sort-instruction selftest (offline; selfcheck leg).

Pins the **data layer** that lets a new pipeline be a JSON plus a solve instead
of a code edit, and the **instruction layer** that makes a fruit's destination a
decision rather than the carrying arm's identity:

1. `scenario.load_scenario` - the schema (strict: an unknown key, a duplicate
   id, a side/target contradiction, an unknown reach status and an unknown
   supply schedule all raise), and the shipped reference descriptor
   (`configs/scenarios/shipped_twoline.json`) parses to the two lanes.
2. `scenario.resolve_scenario` - unset/empty is `None` (one environment read; no
   file, no print) and the parse is cached per path.
3. The **shipped-path fallbacks** in `tasks.py`: `_arm_for_destination` keeps
   `bin_index == 0 -> left` when no instruction is armed, `_place_xy_for` keeps
   `cfg.output_belt_drop_points[index]`, the place leg and the two diagnostic
   reads use `_place_xy_for`, both selectors gate on
   `self._instruction is not None`, the ledger runs only under the instruction,
   only `auto` destinations are solved, and the worker dispatches the fruit's
   own destination.
4. The descriptor's **geometry/supply application** in `assets.SceneConfig` /
   `fruits.SupplyPlan.from_env`: the fields move when armed and return to the
   shipped values when unset; an explicit env knob still wins.
5. Scope: the direct/policy env and the hybrid canary **refuse** the knob (they
   have no dispatcher), and the two scripted drivers consult
   `task.sort_destination`.

Exit 0 on pass, 1 on the first failure.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import `fruits.SupplyPlan` ---------- #
# (the same shape as `scripts/211_bed_audit.py`: this leg is offline and the
# module's USD imports are not part of what it pins)
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
from fruit_sorting.fruits import SupplyPlan  # noqa: E402

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


def grab(src: str, name: str) -> str:
    """A module-level function's source (the P94 selftest's helper)."""
    i = src.index(f"def {name}(")
    j = src.find("\ndef ", i + 5)
    return src[i:j if j > 0 else len(src)]


def grab_method(src: str, name: str) -> str:
    """A 4-space-indented method's source (stops at the next method)."""
    i = src.index(f"    def {name}(")
    j = src.find("\n    def ", i + 5)
    k = src.find("\n\n    def ", i + 5)
    ends = [value for value in (j, k) if value > 0]
    return src[i:min(ends) if ends else len(src)]


def main() -> int:
    # P126 flipped the default scene to three lanes; these legs are the
    # P114 record's two-lane cell, so they build it explicitly.
    cfg = SceneConfig(output_lanes=2)
    shipped = scenario.shipped_descriptor(cfg)
    three = scenario.load_scenario("logs/p114/scenarios/three_dest.json")
    tray = scenario.load_scenario("logs/p114/scenarios/tray_unreachable.json")

    # ------------------------------------------------------------------ 1
    check(shipped.ids == (0, 1), "shipped descriptor has the two lanes")
    check(
        [d.side for d in shipped.destinations] == ["+y", "-y"],
        "shipped lanes are +y (left) and -y (right)",
    )
    ref = scenario.load_scenario("configs/scenarios/shipped_twoline.json")
    check(ref.ids == (0, 1), "the reference descriptor parses to the two lanes")
    check(three.ids == (0, 1, 2), "the 3-destination descriptor has three ids")
    check(
        three.destination(2).reach == "auto",
        "the third destination is reach-checked at startup (`auto`)",
    )

    good = json.loads(Path("configs/scenarios/shipped_twoline.json").read_text())
    tmp = Path(tempfile.mkdtemp(prefix="p114_"))

    def write(name: str, payload) -> str:
        path = tmp / name
        path.write_text(json.dumps(payload) if not isinstance(payload, str) else payload)
        return str(path)

    refuses(
        lambda: scenario.load_scenario(write("bad_schema.json", {**good, "schema": "x"})),
        "schema",
        "a wrong schema tag is refused",
    )
    refuses(
        lambda: scenario.load_scenario(write("unknown.json", {**good, "colour": 1})),
        "unknown top-level",
        "an unknown top-level key is refused",
    )
    dup = json.loads(json.dumps(good))
    dup["destinations"][1]["id"] = 0
    refuses(
        lambda: scenario.load_scenario(write("dup.json", dup)),
        "unique",
        "a duplicate destination id is refused",
    )
    flip = json.loads(json.dumps(good))
    flip["destinations"][0]["side"] = "-y"
    refuses(
        lambda: scenario.load_scenario(write("side.json", flip)),
        "contradicts",
        "a side/target y-sign contradiction is refused",
    )
    reach = json.loads(json.dumps(good))
    reach["destinations"][0]["reach"] = {"status": "maybe"}
    refuses(
        lambda: scenario.load_scenario(write("reach.json", reach)),
        "reach.status",
        "an unknown reach status is refused",
    )
    sched = json.loads(json.dumps(good))
    sched["supply"]["schedule"] = "vibrate"
    refuses(
        lambda: scenario.load_scenario(write("sched.json", sched)),
        "supply.schedule",
        "an unknown supply schedule is refused",
    )

    # ------------------------------------------------------------------ 2
    saved = os.environ.pop("FRUIT_SCENARIO", None)
    try:
        check(scenario.resolve_scenario() is None, "unset FRUIT_SCENARIO -> None")
        check(scenario.resolve_scenario("") is None, "empty FRUIT_SCENARIO -> None")
        os.environ["FRUIT_SCENARIO"] = "configs/scenarios/shipped_twoline.json"
        first = scenario.resolve_scenario()
        second = scenario.resolve_scenario()
        check(first is second, "the descriptor parse is cached per path")
    finally:
        os.environ.pop("FRUIT_SCENARIO", None)
        if saved is not None:
            os.environ["FRUIT_SCENARIO"] = saved

    # ------------------------------------------------------------------ 5
    tasks_src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")
    run_impl = grab_method(tasks_src, "_run_impl")
    check(
        "arm_name = self._arm_for_destination(bin_index)" in run_impl,
        "_run_impl maps the destination through the capability map",
    )
    arm_fn = grab_method(tasks_src, "_arm_for_destination")
    check(
        'if self._instruction is None:' in arm_fn
        and '"left" if int(destination) == 0 else "right"' in arm_fn,
        "the un-instructed arm mapping is the shipped `0 -> left` expression",
    )
    place_fn = grab_method(tasks_src, "_place_xy_for")
    check(
        'override = getattr(self._sort_ctx, "place_xy", None)' in place_fn
        and "return self.cfg.output_belt_drop_points[index]" in place_fn,
        "_place_xy_for falls back to the shipped lane drop point",
    )
    jaw = grab_method(tasks_src, "jaw_target")
    check(
        "px, py = self._place_xy_for(index)" in jaw
        and "cfg.output_belt_drop_points[index]" not in jaw,
        "the place leg's target is read through _place_xy_for",
    )
    check(
        tasks_src.count("self._place_xy_for(bin_index)") == 2,
        "the place-over-belt print and the landing trace use _place_xy_for",
    )
    check(
        tasks_src.count(
            'sort_mode = getattr(self, "_instruction", None) is not None'
        ) == 2,
        "both selectors gate on the instruction (getattr, so a stub task is safe)",
    )
    check(
        tasks_src.count("not self._sort_admits(state, lane_index)") == 2,
        "both selectors filter through _sort_admits",
    )
    check(
        "sort_mode or" in tasks_src or "if pure_grade or sort_mode:" in tasks_src,
        "the instructed selector takes the nearest admitted fruit",
    )
    check(
        "dispatch = self.sort_destination(state)" in tasks_src,
        "the two-line worker dispatches the fruit's own destination",
    )
    check(
        "self._sort_ledger_row(result)" in tasks_src
        and "if self._instruction is not None:" in tasks_src,
        "the ledger is emitted only under an instruction",
    )
    cal = grab_method(tasks_src, "_calibrate_sort_destinations")
    check(
        'pending = [d for d in descriptor.destinations if d.reach == "auto"]'
        in cal,
        "only auto destinations are solved",
    )
    check(
        "self._calibrate_sort_destinations()" in tasks_src
        and "self.sort_ledger_report()" in tasks_src,
        "run_bimanual calls the calibration and the ledger report",
    )

    # ------------------------------------------------------------------ 6
    assets_src = (ROOT / "src/fruit_sorting/assets.py").read_text(encoding="utf-8")
    post = grab_method(assets_src, "__post_init__")
    check(
        "scenario = resolve_scenario()" in post
        and "self.pick_x = float(scenario.pick[\"x\"])" in post
        and "self.belt_speed = -abs(float(scenario.belt[\"speed_m_s\"]))" in post
        and "self.output_place_x = float(scenario.place[\"x\"])" in post,
        "SceneConfig applies the descriptor's pick/belt/place",
    )
    fruits_src = (ROOT / "src/fruit_sorting/fruits.py").read_text(encoding="utf-8")
    from_env = grab_method(fruits_src, "from_env")
    check(
        "supply_block = dict(_scenario.supply)" in from_env
        and 'supply_block.get("x_min"' in from_env
        and 'supply_block.get("grades")' in from_env,
        "SupplyPlan.from_env applies the descriptor's supply as defaults",
    )

    desc = json.loads(json.dumps(good))
    desc["pick"] = {"x": 0.36, "y": 0.02}
    desc["belt"] = {"speed_m_s": 0.10}
    desc["place"] = {"x": 0.45, "y": 0.52}
    desc["supply"] = {"x_min": 0.22, "x_max": 0.34, "grades": {"A": 0.5, "B": 0.5, "C": 0.0}}
    # A zero weight is rejected by the loader (the same rule `_mix_env` has).
    desc["supply"]["grades"] = {"A": 0.5, "B": 0.5}
    path = write("moved.json", desc)
    base = SceneConfig()
    os.environ["FRUIT_SCENARIO"] = path
    try:
        moved = SceneConfig()
        plan = SupplyPlan.from_env(moved, two_line=True)
        check(
            (moved.pick_x, moved.pick_y) == (0.36, 0.02),
            "an armed descriptor moves the pick station",
        )
        check(moved.belt_speed == -0.10, "an armed descriptor moves the belt speed")
        check(
            (moved.output_place_x, moved.output_place_y) == (0.45, 0.52),
            "an armed descriptor moves the release point",
        )
        check(
            (plan.x_min, plan.x_max) == (0.22, 0.34),
            "an armed descriptor moves the supply band",
        )
        check(
            dict(plan.grades) == {"A": 0.5, "B": 0.5},
            "an armed descriptor moves the grade mix",
        )
        os.environ["FRUIT_SUPPLY_X_MAX"] = "0.40"
        try:
            env_wins = SupplyPlan.from_env(moved, two_line=True)
            check(
                env_wins.x_max == 0.40,
                "an explicit FRUIT_SUPPLY_X_MAX still wins over the descriptor",
            )
        finally:
            os.environ.pop("FRUIT_SUPPLY_X_MAX", None)
    finally:
        os.environ.pop("FRUIT_SCENARIO", None)
    back = SceneConfig()
    check(
        (back.pick_x, back.pick_y) == (base.pick_x, base.pick_y)
        and (back.output_place_x, back.output_place_y)
        == (base.output_place_x, base.output_place_y)
        and back.belt_speed == base.belt_speed,
        "unsetting FRUIT_SCENARIO restores the shipped geometry",
    )

    # ------------------------------------------------------------------ 7
    rl_src = (ROOT / "src/fruit_sorting/rl_env.py").read_text(encoding="utf-8")
    check(
        # P121 supersedes P114's blanket refusal: the direct env dispatches the
        # instruction; only the handoff presentation (a different dispatcher)
        # still refuses it.
        "FRUIT_SORT_INSTRUCTION is direct-only" in rl_src
        and "direct_dispatch(" in rl_src
        and "unseen_destinations(" in rl_src,
        "the direct env dispatches the instruction; handoff still refuses",
    )
    eval_src = (ROOT / "scripts/60_eval_policy.py").read_text(encoding="utf-8")
    check(
        "FRUIT_SORT_INSTRUCTION is scripted-only" in eval_src,
        "the hybrid canary refuses the instruction knob",
    )
    for name in ("scripts/20_pick_place.py", "scripts/40_collect_demos.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        check(
            "task.sort_destination(" in text,
            f"{name} consults task.sort_destination",
        )

    # ------------------------------------------------------------------ report
    if FAILS:
        print(f"P114 scenario/instruction selftest: {len(FAILS)} failure(s)")
        for failure in FAILS:
            print(f"  - {failure}")
        return 1
    print(f"P114 scenario/instruction selftest: PASS ({CHECKS} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
