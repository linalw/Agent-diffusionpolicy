"""Offline regression test for the scattered supply (v9/V1), no simulator.

`fruits.py` imports Isaac Sim, so this test stubs the heavy modules first and
then exercises the pure supply logic plus a fake-physics pump:

* the weighted mix allocation (A:0.5,B:0.3,C:0.2 over 16 -> 8/5/3; eight
  equal classes -> two each);
* the resolved `SupplyPlan` defaults (`scatter`, gaps 0.10-0.35, lateral 0.12,
  pool 16) and the env overrides;
* the W3 wave schedule: default off for the single arm, auto-on when
  `FRUIT_BIARM_TWOLINE=1`, and the gap pattern (`wave_size - 1` tight gaps
  then one separation);
* `prime` fills the selector window with sampled gaps (the first wave when the
  wave schedule is on) and never stacks;
* `_pump_supply` releases the backlog without ever placing a fruit within
  0.06 m of a live one, and the scatter=0 path keeps the old 1.6 s cadence.

Run: `python3 scripts/172_supply_selftest.py` (a `selfcheck.sh` leg).
"""

from __future__ import annotations

import os
import sys
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

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
utils_mod = types.ModuleType("isaacsim.core.experimental.utils")
sys.modules.setdefault("isaacsim.core.experimental.utils", utils_mod)
prims_mod = types.ModuleType("isaacsim.core.experimental.prims")
prims_mod.RigidPrim = object
sys.modules.setdefault("isaacsim.core.experimental.prims", prims_mod)

import numpy as np  # noqa: E402

from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.fruits import (  # noqa: E402
    FruitSample,
    FruitSpawner,
    SupplyPlan,
    _mix_allocate,
)


class FakeStage:
    def DefinePrim(self, path, typ):  # noqa: N802
        return None


class FakeRigid:
    def __init__(self):
        self.pos = np.zeros(3)
        self.vel = np.zeros(3)

    def set_world_poses(self, positions=None, orientations=None):
        self.pos = np.asarray(positions[0], dtype=float).copy()

    def set_velocities(self, linear_velocities=None, angular_velocities=None):
        self.vel = np.asarray(linear_velocities[0], dtype=float).copy()

    def get_world_poses(self):
        return [self.pos.copy()], [np.array([1.0, 0.0, 0.0, 0.0])]

    def get_velocities(self):
        return [self.vel.copy()], [np.zeros(3)]


def make_spawner(scatter: bool, seed: int = 5, pool: int = 16):
    os.environ["FRUIT_SUPPLY_SCATTER"] = "1" if scatter else "0"
    os.environ["FRUIT_SUPPLY_POOL"] = str(pool)
    cfg = SceneConfig()
    spawner = FruitSpawner(FakeStage(), cfg, seed=seed)
    categories = list(cfg.fruit_dimensions.keys())
    for i in range(pool):
        spawner.samples.append(
            FruitSample(
                index=i,
                prim_path=f"/World/Fruits/Fruit_{i:02d}",
                category=categories[i % len(categories)],
                diameter=0.05,
                mass=0.1,
                friction=0.7,
                grade="A",
                ripeness=0.8,
                defective=False,
                parked=True,
            )
        )
        spawner._rigids[i] = FakeRigid()
    return spawner, SupplyPlan.from_env(cfg)


def main() -> int:
    checks = 0

    def check(condition: bool, text: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise AssertionError(text)

    # Mix allocation: the documented examples.
    grades = _mix_allocate((("A", 0.5), ("B", 0.3), ("C", 0.2)), 16)
    check(grades.count("A") == 8 and grades.count("B") == 5 and grades.count("C") == 3, "grade mix 8/5/3")
    balanced = _mix_allocate((("A", 0.375), ("B", 0.375), ("C", 0.25)), 16)
    check(
        balanced.count("A") == 6 and balanced.count("B") == 6 and balanced.count("C") == 4,
        "W3 balanced mix 6/6/4",
    )
    uniform = _mix_allocate(tuple((f"c{i}", 1.0) for i in range(8)), 16)
    check(all(uniform.count(f"c{i}") == 2 for i in range(8)), "eight classes -> two each")

    # Resolved defaults + env override.
    cfg = SceneConfig()
    for key in list(os.environ):
        if key.startswith("FRUIT_SUPPLY_"):
            del os.environ[key]
    plan = SupplyPlan.from_env(cfg)
    check(plan.scatter, "scatter default on")
    check(abs(plan.gap_min - 0.10) < 1e-9 and abs(plan.gap_max - 0.35) < 1e-9, "gap defaults")
    check(abs(plan.x_min - 0.20) < 1e-9 and abs(plan.x_max - 0.36) < 1e-9, "lateral band defaults")
    check(plan.target == 0, "approach-segment top-up default off")
    check(plan.pool == cfg.num_fruits == 16, "pool default 16")
    os.environ["FRUIT_SUPPLY_GAP_MIN"] = "0.08"
    check(abs(SupplyPlan.from_env(cfg).gap_min - 0.08) < 1e-9, "gap env override")
    del os.environ["FRUIT_SUPPLY_GAP_MIN"]

    # W3 wave schedule: off for the single arm, auto-on for the two-line, and
    # explicitly overridable both ways.
    check(not plan.wave, "wave schedule default off on the single arm")
    os.environ["FRUIT_BIARM_TWOLINE"] = "1"
    two_line_plan = SupplyPlan.from_env(cfg)
    check(two_line_plan.wave, "wave auto-on when FRUIT_BIARM_TWOLINE=1")
    check(
        dict(two_line_plan.grades) == {"A": 0.375, "B": 0.375, "C": 0.25},
        "two-line wave default mix is balanced (A/B 37.5 %, C 25 %)",
    )
    # The single-arm default keeps the shipped mix.
    os.environ.pop("FRUIT_BIARM_TWOLINE", None)
    check(
        dict(SupplyPlan.from_env(cfg).grades) == {"A": 0.5, "B": 0.3, "C": 0.2},
        "single-arm default mix unchanged (50/30/20)",
    )
    os.environ["FRUIT_BIARM_TWOLINE"] = "1"
    os.environ["FRUIT_SUPPLY_WAVE"] = "0"
    check(
        not SupplyPlan.from_env(cfg).wave,
        "FRUIT_SUPPLY_WAVE=0 overrides the two-line default",
    )
    os.environ["FRUIT_SUPPLY_WAVE"] = "1"
    wave_plan = SupplyPlan.from_env(cfg)
    check(
        wave_plan.wave
        and wave_plan.wave_size == 5
        and abs(wave_plan.wave_gap_min - 0.10) < 1e-9
        and abs(wave_plan.wave_gap_max - 0.16) < 1e-9
        and abs(wave_plan.wave_sep_min - 0.09) < 1e-9
        and abs(wave_plan.wave_sep_max - 0.12) < 1e-9,
        "dense-sheet defaults 5 / 0.10-0.16 / 0.09-0.12",
    )
    check(
        wave_plan.wave_sep_max <= wave_plan.wave_gap_max
        and wave_plan.wave_gap_max <= 0.16 + 1e-9,
        "cluster-boundary gaps do not exceed the within-cluster band "
        "(continuous sheet, no empty stretch)",
    )
    # The gap pattern: `size - 1` tight gaps, then one separation, repeating.
    os.environ["FRUIT_SUPPLY_WAVE_SIZE"] = "4"
    spawner, plan = make_spawner(scatter=True)
    pattern = [spawner._release_gap() for _ in range(8)]
    tight = [gap for index, gap in enumerate(pattern) if index % 4 != 3]
    seps = [gap for index, gap in enumerate(pattern) if index % 4 == 3]
    check(
        all(plan.wave_gap_min - 1e-9 <= gap <= plan.wave_gap_max + 1e-9 for gap in tight),
        f"within-cluster gaps inside the band ({['%.3f' % g for g in tight]})",
    )
    check(
        all(plan.wave_sep_min - 1e-9 <= gap <= plan.wave_sep_max + 1e-9 for gap in seps),
        f"cluster-boundary gaps inside the band ({['%.3f' % g for g in seps]})",
    )
    check(
        max(pattern) <= plan.wave_gap_max + 1e-9,
        f"no gap exceeds the within-cluster band, i.e. no empty stretch "
        f"({['%.3f' % g for g in pattern]})",
    )
    del os.environ["FRUIT_SUPPLY_WAVE_SIZE"]
    del os.environ["FRUIT_SUPPLY_WAVE"]
    del os.environ["FRUIT_BIARM_TWOLINE"]

    # Wave prime: the pre-load is the first wave (all tight gaps).
    os.environ["FRUIT_SUPPLY_WAVE"] = "1"
    spawner, plan = make_spawner(scatter=True)
    spawner.prime(count=6)
    wave_ys = sorted(
        (spawner.position(s)[1] for s in spawner.samples if not s.parked), reverse=True
    )
    check(len(wave_ys) >= 3, "wave prime places >= 3 fruit")
    check(
        all(a - b <= plan.wave_gap_max + 1e-9 for a, b in zip(wave_ys, wave_ys[1:])),
        f"wave prime gaps are the burst's tight gaps ({['%.3f' % (a - b) for a, b in zip(wave_ys, wave_ys[1:])]})",
    )
    del os.environ["FRUIT_SUPPLY_WAVE"]

    # Prime: sampled gaps, inside the selector's upstream window.
    spawner, plan = make_spawner(scatter=True)
    spawner.prime(count=4)
    ys = sorted(
        (spawner.position(s)[1] for s in spawner.samples if not s.parked), reverse=True
    )
    check(len(ys) >= 3, "prime places >= 3 fruit")
    check(all(y >= cfg.pick_y + 0.12 - 1e-9 for y in ys), "prime upstream of the station")
    check(
        all(0.09 <= a - b <= 0.36 for a, b in zip(ys, ys[1:])),
        "prime gaps inside the sampled range",
    )

    # scatter=0 keeps the old 0.30 m ladder bit-for-bit.
    spawner, plan = make_spawner(scatter=False)
    spawner.prime(count=4)
    ys0 = [round(spawner.position(s)[1], 6) for s in spawner.samples if not s.parked]
    check(ys0 == [0.68, 0.38, 0.08, -0.22], "scatter=0 prime ladder unchanged")

    # Fake-physics run: the pump must never stack fruit and must keep the
    # scheduled release magnitude.
    spawner, plan = make_spawner(scatter=True)
    spawner.prime(count=4)
    dt = 1.0 / 120.0
    min_sep = 1.0
    violations = 0
    for tick in range(int(120.0 / dt)):
        spawner.update(tick * dt)
        for sample in list(spawner.active):
            if sample.parked or sample.held:
                continue
            pos = spawner.position(sample)
            pos[1] += cfg.belt_speed * dt
            spawner._rigids[sample.index].pos = pos
            if pos[1] < cfg.despawn_y:
                spawner.park(sample)
                spawner.active.remove(sample)
        live = sorted(
            spawner.position(s)[1]
            for s in spawner.active
            if not s.parked
            and abs(spawner.position(s)[0] - cfg.belt_center[0]) < 0.30
        )
        for a, b in zip(live, live[1:]):
            min_sep = min(min_sep, abs(a - b))
            if abs(a - b) < 0.06:
                violations += 1
    check(violations == 0, f"no fruit placed closer than 0.06 m (min {min_sep:.3f})")
    check(spawner.stats["released"] >= 24, "scattered feeder releases >= 24 fruit in 120 s")
    check(spawner.stats["supply_skipped"] > 0, "backlog slots past the station are skipped, not stacked")

    # scatter=0 keeps the old fixed cadence.
    spawner, plan = make_spawner(scatter=False)
    spawner.prime(count=4)
    for tick in range(int(30.0 / dt)):
        spawner.update(tick * dt)
        for sample in list(spawner.active):
            if sample.parked or sample.held:
                continue
            pos = spawner.position(sample)
            pos[1] += cfg.belt_speed * dt
            spawner._rigids[sample.index].pos = pos
    releases = spawner.stats["released"] - 4
    check(18 <= releases <= 19, f"scatter=0 fixed 1.6 s cadence ({releases} in 30 s)")

    for key in list(os.environ):
        if key.startswith("FRUIT_SUPPLY_"):
            del os.environ[key]
    os.environ.pop("FRUIT_BIARM_TWOLINE", None)
    print(f"supply selftest ok ({checks} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
