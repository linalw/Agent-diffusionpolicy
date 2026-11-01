#!/usr/bin/env python3
"""P88 selftest: the place raise is a **two-line-scoped** cell whose default is OFF.

    python3 scripts/248_p88_place_scope_selftest.py

No simulator (the `225` / `247` stub-the-imports pattern): the **real**
`place_speed_resolution` / `speed_cell_defaults` run, and the manifest builder's
own block is built through the real `scene._place_provenance`.

Why each item matters. After P87's release trim the `place` block is the largest
remaining block of the per-arm span (3.14-3.19 s against `release` 1.70 and
`lift` 1.65), and P44's S1 cell (`FRUIT_SPEED_PLACE=0.52`, `v_max` 0.35 -> 0.52
at the shipped `a_max` 1.089) is the only unspent one of the three. The cap is
read at the **shared** `_carry` leg, so - exactly like the release - a *global*
default would also move the single arm, the shared-station pipeline, the hybrid
canary and the direct/policy presentation. P88 built the session-scoped form and
measured it; **the gate failed on delivery** (the interval rose at both seeds,
`logs/p88/RESULTS.md`), so `PLACE_TWO_LINE_DEFAULT` is **False** and the shipped
tree is inert. This leg pins the scope and the not-shipped default:

1. **Unset, no session = the shipped strings.** `speed_cell_defaults()` (and
   `speed_cell_defaults(False)`) must still return `_SPEED_SHIPPED` *exactly*
   (string-for-string), so `os.environ.get` falls back to the same literal and
   the single arm, the shared-station pipeline, the hybrid canary and the
   direct/policy presentation cannot move.
2. **Unset + two-line = the shipped cap** - the P88 default is **off**
   (`PLACE_TWO_LINE_DEFAULT is False`): the gate failed on delivery
   (`logs/p88/RESULTS.md`), so the shipped tree resolves 0.35/1.089 on every
   path and the measured arm is the explicit `FRUIT_SPEED_PLACE=0.52`
   (`0.52` / `1.089`, 362 -> 244 ticks at the named 0.55 m reference, saved
   118 = -0.98 s at 120 Hz).
3. **The overrides.** `FRUIT_SPEED_PLACE=0` restores the shipped cap *even on
   the two-line*; an explicit speed wins **globally** (the single arm too);
   `FRUIT_SPEED_ALL=1` (S13) wins globally; an explicit `0` beats the union; a
   caller's own speed scales `a_max` on the shipped shape; `..._AMAX` pins it.
4. **The cells are independent.** Setting only `FRUIT_SPEED_PLACE` moves the
   two place keys and nothing else; setting only `FRUIT_SPEED_RELEASE` moves the
   three release keys and nothing else (the release's own `247` leg).
5. **The clock is the profile's own.** `_place_profile_ticks` reproduces
   `motion.jerk_limited`'s tick count (the same generator the leg runs) at the
   reference distance and at a short one, where the acceleration term binds
   instead of the speed term - so the tick fields are a like-for-like clock,
   never a guess.
6. **The scope is the session predicate**, at both scoped consumers (AST), and
   the place branch reads the resolver's `place_vmax`/`place_amax` (one cap
   assignment, never a `min()` against `FRUIT_CARRY_VMAX`).
7. **The row exists and names the resolution** in `run_bimanual` (both modes),
   in the `[biarm] release profile:` form, and **never** on the single-arm path.
8. **The provenance.** `scene._place_provenance` writes
   `physics.place={v_max,a_max,ticks,shipped_ticks,saved_ticks,origin,two_line}`
   and matches the resolver for both scopes; **both** manifest writers pass
   their own scope into `finger_physics_provenance`.
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
    _PLACE_REFERENCE_DISTANCE,
    _SPEED_SHIPPED,
    PLACE_TWO_LINE_DEFAULT,
    _place_profile_ticks,
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
    "FRUIT_SPEED_PLACE",
    "FRUIT_SPEED_PLACE_AMAX",
    "FRUIT_SPEED_RELEASE",
    "FRUIT_SPEED_RELEASE_SETTLE",
    "FRUIT_SPEED_ALL",
)

PLACE_KEYS = ("place_vmax", "place_amax")
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
        return place_speed_resolution(two_line)

    def defaults(self, two_line: bool) -> dict:
        return speed_cell_defaults(two_line)

    def __exit__(self, *exc):
        for name in ENVS:
            os.environ.pop(name, None)
        return False


def moved(base: dict, other: dict) -> set[str]:
    return {k for k in base if base[k] != other[k]}


def main() -> int:
    print("P88 - the place raise is a two-line-scoped default")
    print("=" * 78)

    # [1] unset + no session = the shipped strings, exactly.
    with cells() as c:
        plain = c.defaults(False)
        check(plain == _SPEED_SHIPPED,
              f"unset/no-scope resolves to the shipped dict exactly "
              f"({tuple(plain[k] for k in PLACE_KEYS)})")
        check(all(isinstance(v, str) for v in plain.values()),
              "every shipped default is still a string (no float round-trip)")
        check((plain["place_vmax"], plain["place_amax"]) == ("0.35", "1.089"),
              "the shipped place pair is 0.35 / 1.089")
        res = c.resolution(False)
        check(res["on"] is False and res["origin"] == "scope-off",
              "unset/no-scope is off with origin `scope-off`")
        check(res["shipped_ticks"] == 362 and res["ticks"] == 362
              and res["saved_ticks"] == 0,
              "the shipped clock at the reference distance is 362 ticks and "
              "saves nothing")

    # [2] the default is OFF (P88's gate failed); the explicit arm is P44's S1.
    check(PLACE_TWO_LINE_DEFAULT is False,
          "PLACE_TWO_LINE_DEFAULT is False - the measured cell is not shipped")
    with cells() as c:
        res = c.resolution(True)
        d = c.defaults(True)
        check((d["place_vmax"], d["place_amax"]) == ("0.35", "1.089"),
              "unset inside a two-line session resolves the shipped pair (0.35/1.089)")
        check(res["on"] is False and res["origin"] == "scope-off",
              "the two-line scope alone does not turn the cell on (`scope-off`)")
        check(res["profile"] == "shipped", "the profile reads `shipped`")
    with cells(FRUIT_SPEED_PLACE="0.52") as c:
        res = c.resolution(True)
        d = c.defaults(True)
        check((d["place_vmax"], d["place_amax"]) == ("0.52", "1.089"),
              "the measured arm is the explicit FRUIT_SPEED_PLACE=0.52")
        check(res["on"] is True and res["origin"] == "explicit",
              "… with origin `explicit`")
        check(res["ticks"] == 244 and res["shipped_ticks"] == 362
              and res["saved_ticks"] == 118,
              "the raised clock is 244 ticks at 0.55 m (saved 118 = -0.98 s)")
        check(abs(-res["saved_ticks"] / 120.0 + 0.983) < 0.01,
              "… i.e. -0.98 s per place leg at the reference distance")
        check(_PLACE_REFERENCE_DISTANCE == 0.55,
              "the reference distance is named and 0.55 m")
        check(res["label"] == "FRUIT_SPEED_PLACE=0.52(explicit)",
              f"the label is the P43 form ({res['label']})")

    # [3] the override table.
    with cells(FRUIT_SPEED_PLACE="0") as c:
        check((c.defaults(True)["place_vmax"], c.defaults(True)["place_amax"])
              == ("0.35", "1.089"),
              "an explicit =0 is the shipped cap on the two-line line")
        check(c.resolution(True)["origin"] == "explicit",
              "an explicit 0 is labelled `explicit`")
    with cells(FRUIT_SPEED_PLACE="off") as c:
        check(c.defaults(True)["place_vmax"] == "0.35",
              "an explicit `off`/`false`/`no` also restores the shipped cap")
    with cells(FRUIT_SPEED_PLACE="0.52") as c:
        check(c.defaults(False)["place_vmax"] == "0.52",
              "an explicit speed wins globally (the single-arm line too)")
        check(c.defaults(True)["place_vmax"] == "0.52",
              "… and on the two-line line")
    with cells(FRUIT_SPEED_PLACE="1") as c:
        check(c.defaults(False)["place_vmax"] == "0.52",
              "the `1`/`on` form means the registered speed")
    with cells(FRUIT_SPEED_ALL="1") as c:
        check(c.defaults(False)["place_vmax"] == "0.52",
              "FRUIT_SPEED_ALL=1 (the S13 union) turns the cell on globally")
        check(c.resolution(False)["origin"] == "speed-all",
              "the union's origin is `speed-all`")
    with cells(FRUIT_SPEED_ALL="1", FRUIT_SPEED_PLACE="0") as c:
        check(c.defaults(False)["place_vmax"] == "0.35",
              "an explicit =0 beats the union (225's own precedence rule)")
    with cells(FRUIT_SPEED_PLACE="0.61") as c:
        res = c.resolution(False)
        check(res["a_max"] == f"{0.20 * (0.61 / 0.15) ** 2:.4f}",
              "a caller's own speed scales `a_max` on the shipped shape")
    with cells(FRUIT_SPEED_PLACE="0.61", FRUIT_SPEED_PLACE_AMAX="1.089") as c:
        check(c.resolution(False)["a_max"] == "1.089",
              "FRUIT_SPEED_PLACE_AMAX pins the acceleration")

    # [4] the cells are independent, and the scope moves the release keys only.
    with cells(FRUIT_SPEED_PLACE="0.52", FRUIT_SPEED_RELEASE="0") as c:
        check(moved(c.defaults(False), c.defaults(True)) == set(),
              "the place cell is global when explicit (the scope moves nothing)")
        check(c.defaults(True)["place_vmax"] == "0.52",
              "… and the explicit value wins on the two-line line too")
    with cells() as c:
        check(moved(c.defaults(False), c.defaults(True)) == set(RELEASE_KEYS),
              "the two-line scope moves the release keys only (the place default "
              "is off)")
    with cells(FRUIT_SPEED_PLACE="0") as c:
        check(moved(c.defaults(False), c.defaults(True)) == set(RELEASE_KEYS),
              "the release cell still moves the three release keys only")
        check(release_speed_resolution(False)["ticks"] == 188
              and release_speed_resolution(True)["ticks"] == 112,
              "the release clock is unaffected by the place cell (188 / 112)")

    # [5] the clock is the profile's own generator, at both regimes.
    with cells() as c:
        shipped = c.resolution(False)
    with cells(FRUIT_SPEED_PLACE="0.52") as c:
        raised = c.resolution(True)
        imports = ("TrajectoryLimits", "jerk_limited")
        check(all(name in TASKS_SRC for name in imports),
              "the resolver reuses `motion.jerk_limited` (the leg's own generator)")
    for distance, regime in ((_PLACE_REFERENCE_DISTANCE, "speed-limited"),
                             (0.30, "acceleration-limited at 0.52")):
        check(_place_profile_ticks(distance, shipped["v_max"], shipped["a_max"])
              == _place_profile_ticks(distance, "0.35", "1.089"),
              f"{distance:.2f} m ({regime}) reproduces the shipped generator")
        check(_place_profile_ticks(distance, raised["v_max"], raised["a_max"])
              < _place_profile_ticks(distance, shipped["v_max"], shipped["a_max"]),
              f"{distance:.2f} m ({regime}) is strictly shorter when raised")
    with cells() as c:
        short = _place_profile_ticks(0.30, "0.52", "1.089") - _place_profile_ticks(
            0.30, "0.35", "1.089")
        long_ = _place_profile_ticks(0.55, "0.52", "1.089") - _place_profile_ticks(
            0.55, "0.35", "1.089")
        check(long_ < short,
              f"a long leg saves more than a short one ({long_} vs {short} ticks) - "
              "the acceleration term binds on the short one")
        check(_place_profile_ticks(_PLACE_REFERENCE_DISTANCE, "0", "1.089") is None,
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
    enabled = next((n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "two_line_enabled"), None)
    check(enabled is not None, "`two_line_enabled` exists")
    norm = ast.unparse(enabled).replace("'", '"')
    check('getattr(session, "twoline", False)' in norm and "session is None" in norm,
          "`two_line_enabled` is session-scoped (None outside a CoopSession)")
    carry = next((n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_carry_leg"), None)
    check(carry is not None and 'speed_cell_defaults(self.two_line_enabled())'
          in ast.unparse(carry),
          "the place-carrying leg (`_carry_leg`) is the consumer that reads the pair")
    place_read = ["_speed[\"place_vmax\"]" in TASKS_SRC,
                  "_speed[\"place_amax\"]" in TASKS_SRC]
    check(all(place_read), "the place branch reads the resolver's pair")

    # [7] the row: in `run_bimanual`, naming the resolution, never on the single arm.
    check("[biarm] place profile:" in TASKS_SRC,
          "the row prints in the `[biarm] ...` form")
    run_bi = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "run_bimanual"), None)
    check(run_bi is not None and "[biarm] place profile:" in ast.unparse(run_bi),
          "the row is inside `run_bimanual` (so only a bimanual session prints it)")

    def _prints_row(fn) -> bool:
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "say"):
                text = ast.unparse(node)
                if "[biarm] place profile:" in text:
                    return True
        return False

    printers = sorted(n.name for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and _prints_row(n))
    check(printers == ["run_bimanual"],
          f"only `run_bimanual` prints the row ({printers}) - the single-arm "
          "path stays silent and therefore byte-identical")
    check("place_speed_resolution(" in ast.unparse(run_bi),
          "the row reads the one resolver, not a re-derived cap")

    # [8] the provenance: one builder, both writers, the required keys.
    check("def _place_provenance" in SCENE_SRC,
          "the block has one builder in `scene.py`")
    check('"place": _place_provenance(two_line)' in SCENE_SRC,
          "`finger_physics_provenance` writes it under `physics`")
    check("from .tasks import place_speed_resolution" in SCENE_SRC,
          "the builder reads the same resolver the run does")
    check("two_line=TWO_LINE" in COLLECT_SRC,
          "the collector passes its own scheduler mode")
    check("two_line=False" in RL_ENV_SRC,
          "the direct env passes False (it never runs a CoopSession)")

    from fruit_sorting.scene import _place_provenance  # noqa: E402

    with cells() as c:
        shipped = _place_provenance(False)
        scoped_off = _place_provenance(True)
        check((str(shipped["v_max"]), str(scoped_off["v_max"])) == ("0.35", "0.35"),
              "the shipped tree records 0.35 on both paths (the default is off)")
        check((shipped["origin"], scoped_off["origin"]) == ("scope-off", "scope-off"),
              "the block names the origin (a pre-P88 manifest has no key at all)")
    with cells(FRUIT_SPEED_PLACE="0.52") as c:
        raised = _place_provenance(False)
        keys = ("v_max", "a_max", "ticks", "shipped_ticks", "saved_ticks",
                "origin", "two_line", "reference_distance_m")
        check(all(k in raised for k in keys),
              f"the measured arm's block carries the required keys ({', '.join(keys)})")
        check(str(raised["v_max"]) == "0.52" and raised["origin"] == "explicit",
              "… records the measured cap and its `explicit` origin")
        check((shipped["ticks"], raised["ticks"], raised["saved_ticks"])
              == (362, 244, 118),
              "the block's clock matches the resolver (362 / 244 / saved 118)")
        check(raised["reference_distance_m"] == _PLACE_REFERENCE_DISTANCE,
              "the block names the distance its clock is priced at")
        check(raised["two_line"] is False and scoped_off["two_line"] is True,
              "the block names its scope (the two-line flag is the caller's)")

    # [9] the pin, reported (the shipped selfcheck asserts the equality).
    from fruit_sorting.rl_env import TASKS_MD5  # noqa: E402

    actual = hashlib.md5(TASKS.read_bytes()).hexdigest()
    check(TASKS_MD5 == actual, f"TASKS_MD5 follows tasks.py ({TASKS_MD5[:8]})")

    print("=" * 78)
    print("PASS: the place cell is scoped, its default is OFF, and the measured arm is explicit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
