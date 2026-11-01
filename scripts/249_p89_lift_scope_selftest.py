#!/usr/bin/env python3
"""P89 selftest: the lift raise is a **two-line-scoped** cell whose default is OFF.

    python3 scripts/249_p89_lift_scope_selftest.py

No simulator (the `225` / `247` / `248` stub-the-imports pattern): the **real**
`lift_speed_resolution` / `speed_cell_defaults` run, and the manifest builder's
own block is built through the real `scene._lift_provenance`.

Why each item matters. After P87's release trim and P88's place measurement the
`lift` block is the **last unspent** one of the three (1.65-1.70 s of the per-arm
span), and P44's **S3-v** (`logs/p44/P2_RESULTS.md` §9: `v_max` 0.30 -> 0.37 with
the shipped `a_max` 1.0; the acceleration raise bought 0.00 s and spent transient)
is its measured arm. The cap is read at the **shared** `_carry_leg`
(`grasp_lift` branch), so - exactly like the release and the place - a *global*
default would also move the single arm, the shared-station pipeline, the hybrid
canary and the direct/policy presentation. P89 built the session-scoped form and
measured it; **the gate failed on the delivered side** (the block falls as the
profile's arithmetic prices it, but the interval does not follow at either seed,
`logs/p89/RESULTS.md`), so `LIFT_TWO_LINE_DEFAULT` is **False** and the shipped
tree is inert. This leg pins the scope and the not-shipped default:

1. **Unset, no session = the shipped strings.** `speed_cell_defaults()` (and
   `speed_cell_defaults(False)`) must still return `_SPEED_SHIPPED` *exactly*
   (string-for-string), so `os.environ.get` falls back to the same literal and
   the single arm, the shared-station pipeline, the hybrid canary and the
   direct/policy presentation cannot move.
2. **Unset + two-line = the shipped cap** - the P89 default is **off**
   (`LIFT_TWO_LINE_DEFAULT is False`): the shipped tree resolves 0.30/1.0 on
   every path and the measured arm is the explicit `FRUIT_SPEED_LIFT=0.37`
   (0.37 / **1.0**, 162 -> 136 ticks at the named 0.21 m reference, saved 26 =
   -0.217 s at 120 Hz).
3. **The overrides, and the S3/S13 pairs are NOT moved.** `FRUIT_SPEED_LIFT=1`
   and `FRUIT_SPEED_ALL=1` keep their measured **0.36 / 1.9** (P44's S3 and the
   S13 union); an explicit `0` restores the shipped cap even on the two-line and
   beats the union; `FRUIT_SPEED_LIFT_AMAX` pins the acceleration; a value equal
   to 0.37 resolves the **shipped** acceleration however it is written
   (`0.3700` too) - the cell must not mean two different accelerations.
4. **The cells are independent.** Setting only `FRUIT_SPEED_LIFT` moves the two
   lift keys and nothing else; an unset two-line scope moves the three release
   keys only (P87's `247`), and the place cell stays off (P88's `248`).
5. **The clock is the profile's own.** `_carry_profile_ticks` reproduces
   `motion.jerk_limited` (the same generator the leg runs) at the reference
   distance and at a short one, and the two cells' regimes are the arithmetic's:
   below the switch distance (0.148 m shipped / 0.225 m raised) nothing is saved
   (both are jerk/acceleration-limited), above it the saving grows with distance.
6. **The scope is the session predicate**, at both scoped consumers (AST), and
   the lift branch reads the resolver's `lift_vmax`/`lift_amax` (never a `min()`
   against `FRUIT_CARRY_VMAX` - `limited_by_cone` is the only clip).
7. **The row exists and names the resolution** in `run_bimanual` (both modes), in
   the `[biarm] release/place profile:` form, and **never** on the single-arm
   path.
8. **The provenance.** `scene._lift_provenance` writes
   `physics.lift={v_max,a_max,ticks,shipped_ticks,saved_ticks,reference_distance_m,
   origin,two_line}` and matches the resolver for both scopes; **both** manifest
   writers pass their own scope into `finger_physics_provenance`.
9. **`TASKS_MD5` provenance** is the `rl_env` metadata pin (reported; the
   shipped selfcheck asserts the equality).

Exit 0 on pass, 1 on the first failure. Run by `scripts/selfcheck.sh`.
"""
from __future__ import annotations

import ast
import hashlib
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import fruit_sorting.tasks + scene --- #
for name in (
    "pxr",
    "isaacsim",
    "isaacsim.core",
    "isaacsim.core.experimental",
    "isaacsim.sensors",
    "isaacsim.sensors.experimental",
    "isaacsim.core.experimental.utils",
    "isaacsim.core.experimental.objects",
    "isaacsim.core.experimental.utils.app",
    "isaacsim.core.experimental.utils.stage",
    "isaacsim.core.experimental.prims",
):
    module = sys.modules.setdefault(name, types.ModuleType(name))
    module.__path__ = []  # a package, so the submodule imports below resolve
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
sys.modules["isaacsim.core.experimental.utils.app"].update_app = lambda **kwargs: None
sys.modules["isaacsim.core.experimental.utils.stage"].create_prim = lambda *a, **k: None
prims_mod = sys.modules["isaacsim.core.experimental.prims"]
prims_mod.RigidPrim = object
prims_mod.Articulation = object
objects_mod = sys.modules["isaacsim.core.experimental.objects"]
objects_mod.DistantLight = object
objects_mod.GroundPlane = object
sys.modules.setdefault(
    "isaacsim.core.simulation_manager",
    types.SimpleNamespace(SimulationManager=types.SimpleNamespace(step=staticmethod(lambda **kw: None))),
)
sys.modules.setdefault(
    "isaacsim.core.rendering_manager",
    types.SimpleNamespace(RenderingManager=types.SimpleNamespace(render=staticmethod(lambda: None))),
)
sensors_mod = types.ModuleType("isaacsim.sensors.experimental.physics")
sensors_mod.Contact = object
sensors_mod.ContactSensor = object
sys.modules.setdefault("isaacsim.sensors.experimental.physics", sensors_mod)
rtx_mod = types.ModuleType("isaacsim.sensors.experimental.rtx")
rtx_mod.CameraSensor = object
rtx_mod.RtxCamera = object
sys.modules.setdefault("isaacsim.sensors.experimental.rtx", rtx_mod)

from fruit_sorting.tasks import (  # noqa: E402
    _LIFT_REFERENCE_DISTANCE,
    _LIFT_SCOPED_VMAX,
    _SPEED_SHIPPED,
    LIFT_TWO_LINE_DEFAULT,
    _carry_profile_ticks,
    lift_speed_resolution,
    place_speed_resolution,
    release_speed_resolution,
    speed_cell_defaults,
)

TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
SCENE = ROOT / "src" / "fruit_sorting" / "scene.py"
COLLECT = ROOT / "scripts" / "40_collect_demos.py"
RL_ENV = ROOT / "src" / "fruit_sorting" / "rl_env.py"
TASKS_SRC = TASKS.read_text(encoding="utf-8")
SCENE_SRC = SCENE.read_text(encoding="utf-8")
COLLECT_SRC = COLLECT.read_text(encoding="utf-8")
RL_ENV_SRC = RL_ENV.read_text(encoding="utf-8")

ENVS = (
    "FRUIT_SPEED_LIFT",
    "FRUIT_SPEED_LIFT_AMAX",
    "FRUIT_SPEED_PLACE",
    "FRUIT_SPEED_PLACE_AMAX",
    "FRUIT_SPEED_RELEASE",
    "FRUIT_SPEED_RELEASE_SETTLE",
    "FRUIT_SPEED_ALL",
)

LIFT_KEYS = ("lift_vmax", "lift_amax")
RELEASE_KEYS = ("release_dwell", "release_pad_hold", "release_finger_hold")


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


class cells:
    """Set exactly the given speed-cell env vars for the duration of the block."""

    def __init__(self, **env: str):
        self.env = env

    def __enter__(self):
        for name in ENVS:
            os.environ.pop(name, None)
        for name, value in self.env.items():
            os.environ[name] = str(value)
        return self

    def resolution(self, two_line: bool) -> dict:
        return lift_speed_resolution(two_line)

    def defaults(self, two_line: bool) -> dict:
        return speed_cell_defaults(two_line)

    def __exit__(self, *exc):
        for name in ENVS:
            os.environ.pop(name, None)
        return False


def moved(base: dict, other: dict) -> set[str]:
    return {k for k in base if base[k] != other[k]}


def main() -> int:
    print("P89 - the lift raise is a two-line-scoped cell whose default is OFF")
    print("=" * 78)

    # [1] unset + no session = the shipped strings, exactly.
    with cells() as c:
        plain = c.defaults(False)
        check(plain == _SPEED_SHIPPED,
              f"unset/no-scope resolves to the shipped dict exactly "
              f"({tuple(plain[k] for k in LIFT_KEYS)})")
        check(all(isinstance(v, str) for v in plain.values()),
              "every shipped default is still a string (no float round-trip)")
        check((plain["lift_vmax"], plain["lift_amax"]) == ("0.30", "1.0"),
              "the shipped lift pair is 0.30 / 1.0")
        res = c.resolution(False)
        check(res["on"] is False and res["origin"] == "scope-off",
              "unset/no-scope is off with origin `scope-off`")
        check(res["shipped_ticks"] == 162 and res["ticks"] == 162
              and res["saved_ticks"] == 0,
              "the shipped clock at the reference distance is 162 ticks and "
              "saves nothing")

    # [2] the default is OFF (P89's gate failed); the measured arm is P44's S3-v.
    check(LIFT_TWO_LINE_DEFAULT is False,
          "LIFT_TWO_LINE_DEFAULT is False - the measured cell is not shipped")
    check(_LIFT_SCOPED_VMAX == "0.37",
          "the scoped cell's value is P44's S3-v (0.37)")
    with cells() as c:
        res = c.resolution(True)
        d = c.defaults(True)
        check((d["lift_vmax"], d["lift_amax"]) == ("0.30", "1.0"),
              "unset inside a two-line session resolves the shipped pair (0.30/1.0)")
        check(res["on"] is False and res["origin"] == "scope-off",
              "the two-line scope alone does not turn the cell on (`scope-off`)")
        check(res["profile"] == "shipped", "the profile reads `shipped`")
    with cells(FRUIT_SPEED_LIFT="0.37") as c:
        res = c.resolution(True)
        d = c.defaults(True)
        check((d["lift_vmax"], d["lift_amax"]) == ("0.37", "1.0"),
              "the measured arm is FRUIT_SPEED_LIFT=0.37 -> 0.37 / 1.0 (S3-v: the "
              "acceleration is NOT raised)")
        check(res["on"] is True and res["origin"] == "explicit",
              "… with origin `explicit`")
        check(res["ticks"] == 136 and res["shipped_ticks"] == 162
              and res["saved_ticks"] == 26,
              "the raised clock is 136 ticks at 0.21 m (saved 26 = -0.217 s)")
        check(abs(-res["saved_ticks"] / 120.0 + 0.217) < 0.005,
              "… i.e. -0.22 s per lift leg at the reference distance")
        check(_LIFT_REFERENCE_DISTANCE == 0.21,
              "the reference distance is named and 0.21 m")
        check(res["label"] == "FRUIT_SPEED_LIFT=0.37(explicit)",
              f"the label is the P43 form ({res['label']})")

    # [3] the override table: S3/S13 keep their measured pair, and the cell's
    #     own value means the shipped acceleration however it is written.
    with cells(FRUIT_SPEED_LIFT="0") as c:
        check((c.defaults(True)["lift_vmax"], c.defaults(True)["lift_amax"])
              == ("0.30", "1.0"),
              "an explicit =0 is the shipped cap on the two-line line")
        check(c.resolution(True)["origin"] == "explicit",
              "an explicit 0 is labelled `explicit`")
    with cells(FRUIT_SPEED_LIFT="off") as c:
        check(c.defaults(True)["lift_vmax"] == "0.30",
              "an explicit `off`/`false`/`no` also restores the shipped cap")
    with cells(FRUIT_SPEED_LIFT="1") as c:
        check((c.defaults(False)["lift_vmax"], c.defaults(False)["lift_amax"])
              == ("0.36", "1.9"),
              "the `1`/`on` form is still S3's measured 0.36 / 1.9 (not moved)")
        check(c.resolution(False)["origin"] == "explicit", "… labelled `explicit`")
    with cells(FRUIT_SPEED_ALL="1") as c:
        check((c.defaults(False)["lift_vmax"], c.defaults(False)["lift_amax"])
              == ("0.36", "1.9"),
              "FRUIT_SPEED_ALL=1 (the S13 union) keeps its measured 0.36 / 1.9")
        check(c.resolution(False)["origin"] == "speed-all",
              "the union's origin is `speed-all`")
    with cells(FRUIT_SPEED_ALL="1", FRUIT_SPEED_LIFT="0") as c:
        check(c.defaults(False)["lift_vmax"] == "0.30",
              "an explicit =0 beats the union (225's own precedence rule)")
    with cells(FRUIT_SPEED_LIFT="0.36") as c:
        check(c.resolution(False)["a_max"] == "1.9",
              "a non-0.37 explicit speed keeps P44's acceleration default (1.9) - "
              "the recorded S3/S13 semantics")
    with cells(FRUIT_SPEED_LIFT="0.3700") as c:
        res = c.resolution(False)
        check((str(res["v_max"]), str(res["a_max"])) == ("0.3700", "1.0"),
              "0.3700 resolves the same pair as 0.37 (numeric, not string, match)")
    with cells(FRUIT_SPEED_LIFT="0.37", FRUIT_SPEED_LIFT_AMAX="1.9") as c:
        check(c.resolution(False)["a_max"] == "1.9",
              "FRUIT_SPEED_LIFT_AMAX pins the acceleration")
    with cells(FRUIT_SPEED_LIFT="0.37") as c:
        check(c.defaults(False)["lift_vmax"] == "0.37",
              "an explicit speed wins globally (the single-arm line too)")

    # [4] the cells are independent.
    with cells(FRUIT_SPEED_LIFT="0.37") as c:
        check(moved(c.defaults(False), c.defaults(True)) == set(RELEASE_KEYS),
              "an explicit lift cell is global (the scope moves the release keys "
              "only, never the lift's)")
        check(moved(c.defaults(False), dict(_SPEED_SHIPPED)) == {"lift_vmax"},
              "and it moves `lift_vmax` only (`a_max` stays the shipped 1.0, which "
              "is the S3-v point)")
    with cells() as c:
        check(moved(c.defaults(False), c.defaults(True)) == set(RELEASE_KEYS),
              "the two-line scope moves the release keys only (place and lift "
              "defaults are off)")
        check(release_speed_resolution(True)["ticks"] == 112,
              "the release clock is unaffected by the lift cell (188 / 112)")
        check(place_speed_resolution(True)["on"] is False,
              "the place cell is still off (P88)")

    # [5] the clock is the profile's own generator, at both regimes.
    with cells() as c:
        shipped = c.resolution(False)
    with cells(FRUIT_SPEED_LIFT="0.37") as c:
        raised = c.resolution(True)
    for distance, regime in ((_LIFT_REFERENCE_DISTANCE, "the reference"),
                             (0.05, "a short leg (jerk-limited)"),
                             (0.50, "a long leg (speed-limited at 0.30)")):
        check(_carry_profile_ticks(distance, shipped["v_max"], shipped["a_max"])
              == _carry_profile_ticks(distance, "0.30", "1.0"),
              f"{distance:.2f} m ({regime}) reproduces the shipped generator")
    check(_carry_profile_ticks(0.10, "0.37", "1.0")
          == _carry_profile_ticks(0.10, "0.30", "1.0"),
          "below the raised cell's switch distance (0.225 m) the short leg saves "
          "nothing - the acceleration term binds, not the cap")
    for distance in (0.20, 0.21, 0.22, 0.50):
        ship = _carry_profile_ticks(distance, "0.30", "1.0")
        raise_ = _carry_profile_ticks(distance, "0.37", "1.0")
        check(raise_ < ship,
              f"{distance:.2f} m is strictly shorter when raised ({ship} -> {raise_} ticks)")
    check(_carry_profile_ticks(0.50, "0.37", "1.0") - _carry_profile_ticks(0.50, "0.30", "1.0")
          < _carry_profile_ticks(0.21, "0.37", "1.0")
          - _carry_profile_ticks(0.21, "0.30", "1.0"),
          "a long leg saves more than the reference one (the cap, not the jerk "
          "term, is what binds there)")
    check(_carry_profile_ticks(_LIFT_REFERENCE_DISTANCE, "0", "1.0") is None,
          "an unparsable cap yields no clock (None), never a wrong one")

    # [6] the scope is the session predicate, at both scoped consumers.
    tree = ast.parse(TASKS_SRC)
    scoped_calls = [n for n in ast.walk(tree)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "speed_cell_defaults"]
    check(len(scoped_calls) == 2,
          f"two consumers build the resolver dict ({len(scoped_calls)})")
    check(all(n.args and ast.unparse(n.args[0]) == "self.two_line_enabled()"
              for n in scoped_calls),
          "both consumers pass the session predicate (`self.two_line_enabled()`)")
    carry = next((n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_carry_leg"), None)
    check(carry is not None and 'speed_cell_defaults(self.two_line_enabled())'
          in ast.unparse(carry),
          "the lift-carrying leg (`_carry_leg`) is the consumer that reads the pair")
    check('_speed["lift_vmax"]' in TASKS_SRC and '_speed["lift_amax"]' in TASKS_SRC,
          "the lift branch reads the resolver's pair")
    check("FRUIT_DYNAMIC_LIFT_VMAX" in TASKS_SRC
          and "os.environ.get(\"FRUIT_DYNAMIC_LIFT_VMAX\", _speed[\"lift_vmax\"])"
          in TASKS_SRC,
          "an explicit FRUIT_DYNAMIC_LIFT_VMAX still wins over the cell")

    # [7] the row: in `run_bimanual`, naming the resolution, never on the single arm.
    check("[biarm] lift profile:" in TASKS_SRC,
          "the row prints in the `[biarm] ...` form")
    run_bi = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "run_bimanual"), None)
    check(run_bi is not None and "[biarm] lift profile:" in ast.unparse(run_bi),
          "the row is inside `run_bimanual` (so only a bimanual session prints it)")
    check("lift_speed_resolution(" in ast.unparse(run_bi),
          "the row reads the one resolver, not a re-derived cap")

    def _prints_row(fn) -> bool:
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "say"):
                if "[biarm] lift profile:" in ast.unparse(node):
                    return True
        return False

    printers = sorted(n.name for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and _prints_row(n))
    check(printers == ["run_bimanual"],
          f"only `run_bimanual` prints the row ({printers}) - the single-arm "
          "path stays silent and therefore byte-identical")

    # [8] the provenance: one builder, both writers, the required keys.
    check("def _lift_provenance" in SCENE_SRC,
          "the block has one builder in `scene.py`")
    check('"lift": _lift_provenance(two_line)' in SCENE_SRC,
          "`finger_physics_provenance` writes it under `physics`")
    check("from .tasks import lift_speed_resolution" in SCENE_SRC,
          "the builder reads the same resolver the run does")
    check("two_line=TWO_LINE" in COLLECT_SRC,
          "the collector passes its own scheduler mode")
    check("two_line=False" in RL_ENV_SRC,
          "the direct env passes False (it never runs a CoopSession)")

    from fruit_sorting.scene import _lift_provenance  # noqa: E402

    with cells() as c:
        shipped_block = _lift_provenance(False)
        scoped_off = _lift_provenance(True)
        check((str(shipped_block["v_max"]), str(scoped_off["v_max"])) == ("0.30", "0.30"),
              "the shipped tree records 0.30 on both paths (the default is off)")
        check((shipped_block["origin"], scoped_off["origin"]) == ("scope-off", "scope-off"),
              "the block names the origin (a pre-P89 manifest has no key at all)")
    with cells(FRUIT_SPEED_LIFT="0.37") as c:
        raised_block = _lift_provenance(False)
        keys = ("v_max", "a_max", "ticks", "shipped_ticks", "saved_ticks",
                "origin", "two_line", "reference_distance_m")
        check(all(k in raised_block for k in keys),
              f"the measured arm's block carries the required keys ({', '.join(keys)})")
        check(str(raised_block["v_max"]) == "0.37"
              and str(raised_block["a_max"]) == "1.0"
              and raised_block["origin"] == "explicit",
              "… records the S3-v pair (0.37 / 1.0) and its `explicit` origin")
        check((shipped_block["ticks"], raised_block["ticks"], raised_block["saved_ticks"])
              == (162, 136, 26),
              "the block's clock matches the resolver (162 / 136 / saved 26)")
        check(raised_block["reference_distance_m"] == _LIFT_REFERENCE_DISTANCE,
              "the block names the distance its clock is priced at")
        check(raised_block["two_line"] is False and scoped_off["two_line"] is True,
              "the block names its scope (the two-line flag is the caller's)")

    # [9] the pin, reported (the shipped selfcheck asserts the equality).
    from fruit_sorting.rl_env import TASKS_MD5  # noqa: E402

    actual = hashlib.md5(TASKS.read_bytes()).hexdigest()
    check(TASKS_MD5 == actual, f"TASKS_MD5 follows tasks.py ({TASKS_MD5[:8]})")

    print("=" * 78)
    print("PASS: the lift cell is scoped, its default is OFF, and the measured arm is explicit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
