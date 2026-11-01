"""Offline selftest of the P85 flip: the shipped scripted cell is the two-line.

    python3 scripts/246_p85_selftest.py

No simulator. The **real** resolvers and the real supply plan run (the `224` /
`225` stub-the-imports pattern), so what is pinned is the code the runs read.

Why each item matters:

1. **The resolver table.** `FRUIT_BIARM` and `FRUIT_BIARM_TWOLINE` both default
   `1` (unset = the bimanual two-line, `defaulted=True`), `FRUIT_BIARM=0` is the
   pre-P85 single arm, and `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0` is the F2
   shared-station pipeline. The origin flag is what the collector's manifest
   records, so it is asserted too.
2. **The supply package follows the scheduler.** The two-line ships the dense
   wave sheet and the balanced A:B:C mix (P81's "package"); `two_line=False`
   returns the pre-P85 single-arm plan (65-35-20 mix, wave off), and
   `two_line=None` keeps the raw env read so every probe, the direct env and the
   hybrid canary stay byte-identical. An explicit `FRUIT_SUPPLY_WAVE=0` still
   wins.
3. **`two_line_enabled()` is session-scoped.** It is the scope predicate three
   task sites use ("is the two-line scheduler *running*"), so it must be False
   outside a `CoopSession` even with the defaulted pair on - that is what keeps
   the single-arm and shared-station paths byte-identical - and it follows
   `session.twoline` inside one. The *ambient* resolution is
   `two_line_resolved()`, which `run_bimanual` reads.
4. **The consumers pass the resolution explicitly** (AST): the three scripted
   entry scripts construct `FruitSpawner(..., two_line=...)`, and the direct
   env / the hybrid canary pin `two_line=False` because they are not the
   scripted cell.
5. **The collector's manifest can tell a post-flip shard from a pre-flip one**:
   the `collection` block carries the resolved pair and both origin flags
   (a manifest without them is pre-P85).
6. **The acceptance gates the scenario it ran** (`scripts/accept.sh`): the
   two-line branch goes through `190_twoline_gate.sh` with the two-line floor,
   the single-arm branch keeps 105 and its own reference file.

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

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.bimanual import (  # noqa: E402
    BIARM_DEFAULT,
    TWOLINE_DEFAULT,
    biarm_resolution,
    resolve_biarm,
    resolve_twoline,
)
from fruit_sorting.fruits import FruitSpawner, SupplyPlan  # noqa: E402
from fruit_sorting.tasks import PickAndPlaceTask  # noqa: E402

TASKS_SRC = Path(ROOT, "src", "fruit_sorting", "tasks.py").read_text(encoding="utf-8")
SCHED_ENVS = ("FRUIT_BIARM", "FRUIT_BIARM_TWOLINE")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok: {message}")


class scheduler:
    """Set exactly the given scheduler env vars for the duration of the block."""

    def __init__(self, **env: str):
        self.env = env

    def __enter__(self):
        for name in SCHED_ENVS:
            os.environ.pop(name, None)
        for name, value in self.env.items():
            os.environ[name] = str(value)
        return biarm_resolution()

    def __exit__(self, *exc):
        for name in SCHED_ENVS:
            os.environ.pop(name, None)
        return False


class FakeStage:
    def DefinePrim(self, path, typ):  # noqa: N802
        return None


def function_node(name: str) -> ast.FunctionDef:
    tree = ast.parse(TASKS_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"tasks.py has no function {name!r}")


def referenced_names(node: ast.AST) -> set[str]:
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            names.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            names.add(sub.attr)
    return names


def env_reads(node: ast.AST) -> set[str]:
    """Every constant key passed to `os.environ.get(...)` inside `node`."""
    keys = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if not isinstance(func, ast.Attribute) or func.attr != "get":
            continue
        owner = func.value
        if not isinstance(owner, ast.Attribute) or owner.attr != "environ":
            continue
        if sub.args and isinstance(sub.args[0], ast.Constant):
            keys.add(str(sub.args[0].value))
    return keys


def spawner_two_line_kwargs(path: str) -> list[ast.expr]:
    tree = ast.parse(Path(ROOT, path).read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name != "FruitSpawner":
            continue
        for keyword in node.keywords:
            if keyword.arg == "two_line":
                found.append(keyword.value)
    return found


def manifest_collection_keys() -> set[str]:
    tree = ast.parse(
        Path(ROOT, "scripts", "40_collect_demos.py").read_text(encoding="utf-8")
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "collection"
                    and isinstance(value, ast.Dict)
                ):
                    return {
                        str(k.value)
                        for k in value.keys
                        if isinstance(k, ast.Constant)
                    }
    raise AssertionError("the collector's manifest has no collection block")


def main() -> int:
    print("P85 - the shipped cell is the bimanual two-line")
    print("=" * 78)

    # 1. The resolver table.
    check((BIARM_DEFAULT, TWOLINE_DEFAULT) == ("1", "1"), "the shipped defaults are 1/1")
    check(resolve_biarm(None) == (True, True), "FRUIT_BIARM unset -> on, defaulted")
    check(resolve_biarm("1") == (True, False), "FRUIT_BIARM=1 -> on, explicit")
    check(resolve_biarm("0") == (False, False), "FRUIT_BIARM=0 -> the pre-P85 single arm")
    check(
        resolve_twoline(None, biarm=True) == (True, True),
        "FRUIT_BIARM_TWOLINE unset (biarm on) -> two-line, defaulted",
    )
    check(
        resolve_twoline("0", biarm=True) == (False, False),
        "FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0 -> the shared-station pipeline",
    )
    check(
        resolve_twoline(None, biarm=False) == (False, False),
        "biarm off -> FRUIT_BIARM_TWOLINE is inert (single arm unchanged)",
    )
    with scheduler() as resolved:
        check(resolved["biarm"] and resolved["twoline"], "unset env resolves to the two-line")
        check(
            resolved["label"] == "FRUIT_BIARM=1(default) FRUIT_BIARM_TWOLINE=1(default)",
            "the P43-style label names both origins",
        )
    with scheduler(FRUIT_BIARM="0") as resolved:
        check(
            not resolved["biarm"] and not resolved["twoline"],
            "FRUIT_BIARM=0 resolves the single arm",
        )
        check(
            resolved["label"] == "FRUIT_BIARM=0(explicit) FRUIT_BIARM_TWOLINE=0(biarm-off)",
            "the label distinguishes the biarm-off twoline from an explicit one",
        )
    with scheduler(FRUIT_BIARM="1", FRUIT_BIARM_TWOLINE="0") as resolved:
        check(
            resolved["biarm"] and not resolved["twoline"],
            "the shared-station pair resolves as before P85",
        )
        check(
            not resolved["biarm_defaulted"] and not resolved["twoline_defaulted"],
            "explicit values are not flagged as defaulted",
        )

    # 2. The supply package follows the scheduler (the same `SupplyPlan.from_env`).
    cfg = SceneConfig()
    plan_two = SupplyPlan.from_env(cfg, True)
    plan_single = SupplyPlan.from_env(cfg, False)
    check(plan_two.wave, "two-line plan: the dense wave sheet is on by default")
    check(not plan_single.wave, "single-arm plan: wave off (pre-P85)")
    grades_two = dict(plan_two.grades)
    grades_single = dict(plan_single.grades)
    check(
        grades_two == {"A": 0.375, "B": 0.375, "C": 0.25},
        f"two-line plan: the balanced A:B:C mix ({grades_two})",
    )
    check(
        grades_single == {"A": 0.5, "B": 0.3, "C": 0.2},
        f"single-arm plan: the shipped 50/30/20 mix ({grades_single})",
    )
    os.environ["FRUIT_SUPPLY_WAVE"] = "0"
    try:
        check(
            not SupplyPlan.from_env(cfg, True).wave,
            "an explicit FRUIT_SUPPLY_WAVE=0 still wins over the package",
        )
    finally:
        os.environ.pop("FRUIT_SUPPLY_WAVE", None)
    # ... and `None` keeps the pre-P85 raw read (every non-scripted consumer).
    check(not SupplyPlan.from_env(cfg, None).wave, "two_line=None + unset env -> wave off")
    os.environ["FRUIT_BIARM_TWOLINE"] = "1"
    try:
        check(
            SupplyPlan.from_env(cfg, None).wave,
            "two_line=None + FRUIT_BIARM_TWOLINE=1 -> wave on (the pre-P85 opt-in)",
        )
    finally:
        os.environ.pop("FRUIT_BIARM_TWOLINE", None)
    spawner = FruitSpawner(FakeStage(), cfg, seed=5, two_line=False)
    check(not spawner.supply.wave, "FruitSpawner forwards two_line to the supply plan")

    # 3. `two_line_enabled` is session-scoped; `two_line_resolved` is ambient.
    check(
        not PickAndPlaceTask.two_line_enabled(SimpleNamespace(_active_session=None)),
        "two_line_enabled() is False outside a session (single arm unchanged)",
    )
    check(
        PickAndPlaceTask.two_line_enabled(
            SimpleNamespace(_active_session=SimpleNamespace(twoline=True))
        ),
        "two_line_enabled() follows session.twoline=True",
    )
    check(
        not PickAndPlaceTask.two_line_enabled(
            SimpleNamespace(_active_session=SimpleNamespace(twoline=False))
        ),
        "two_line_enabled() follows session.twoline=False (shared station)",
    )
    check(
        PickAndPlaceTask.two_line_resolved(SimpleNamespace())
        and not str(os.environ.get("FRUIT_BIARM", "")) == "0",
        "two_line_resolved() is the ambient resolution (defaulted on)",
    )
    check(
        not env_reads(function_node("two_line_enabled")),
        "two_line_enabled() reads no environment variable",
    )
    check(
        "biarm_resolution" in referenced_names(function_node("bimanual_enabled")),
        "bimanual_enabled() resolves through biarm_resolution()",
    )
    check(
        not env_reads(function_node("bimanual_enabled")),
        "bimanual_enabled() reads no scheduler env var directly",
    )
    check(
        "two_line_resolved" in referenced_names(function_node("run_bimanual")),
        "run_bimanual() takes the ambient resolution",
    )

    # 4. The consumers pass the resolution explicitly.
    for path in ("scripts/20_pick_place.py", "scripts/40_collect_demos.py",
                 "scripts/70_record_video.py"):
        kwargs = spawner_two_line_kwargs(path)
        check(len(kwargs) == 1, f"{path}: exactly one FruitSpawner two_line= kwarg")
    for path in ("src/fruit_sorting/rl_env.py", "scripts/60_eval_policy.py"):
        kwargs = spawner_two_line_kwargs(path)
        check(len(kwargs) == 1, f"{path}: the spawner pins a two_line= value")
        value = kwargs[0]
        check(
            isinstance(value, ast.Constant) and value.value is False,
            f"{path}: pins two_line=False (not the scripted cell)",
        )
    collector = Path(ROOT, "scripts", "40_collect_demos.py").read_text(encoding="utf-8")
    check(
        "biarm_resolution()" in collector,
        "the collector resolves the scheduler through the shared resolver",
    )

    # 5. The manifest can tell a post-flip shard from a pre-flip one.
    keys = manifest_collection_keys()
    for key in (
        "biarm_resolved",
        "biarm_twoline_resolved",
        "biarm_defaulted",
        "biarm_twoline_defaulted",
    ):
        check(key in keys, f"the shard manifest records collection.{key}")

    # 6. The acceptance gates the scenario it ran.
    accept = Path(ROOT, "scripts", "accept.sh").read_text(encoding="utf-8")
    check(
        "190_twoline_gate.sh -r" in accept,
        "accept.sh gates a two-line session through 190 (its own floor)",
    )
    check(
        "motion_reference_single.json" in accept,
        "accept.sh keeps the single-arm reference for the restore path",
    )

    print("P85 selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
