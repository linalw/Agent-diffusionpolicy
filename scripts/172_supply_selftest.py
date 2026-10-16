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
  0.06 m of a live one, and the scatter=0 path keeps the old 1.6 s cadence;
* the P4-C1 H1 trickle feed (`FRUIT_SUPPLY_TRICKLE_LATE_S`, default off):
  consume-and-skip with a lateness cap - at most one slice per pump window,
  only fresh positions, the stale backlog counted (`supply_trickled`).

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

    # --- W6-A: the 2D patch sheet (FRUIT_SUPPLY_PATCH, default off) --------- #
    # Resolved defaults and env parsing first, then the 2D-ness invariants on
    # a 90 s free-cadence run, then the patch-off byte-identity fingerprints.
    for key in list(os.environ):
        if key.startswith("FRUIT_SUPPLY_"):
            del os.environ[key]
    os.environ.pop("FRUIT_BIARM_TWOLINE", None)
    check(not SupplyPlan.from_env(cfg).patch, "patch default off (old supplies unchanged)")
    # --- P1/P2 density knob (added 2026-10-16: the Oracle review found the
    # selftest never exercised `FRUIT_SUPPLY_PATCH_DENSITY`, so the "byte-identical
    # at D=1" claim rested on code inspection rather than a check).
    # (a) D=1.0 must leave the wave schedule's four gap bands at the defaults.
    os.environ["FRUIT_SUPPLY_WAVE"] = "1"
    os.environ["FRUIT_SUPPLY_PATCH_DENSITY"] = "1.0"
    d1_wave = SupplyPlan.from_env(cfg)
    check(
        abs(d1_wave.wave_gap_min - 0.10) < 1e-9
        and abs(d1_wave.wave_gap_max - 0.16) < 1e-9
        and abs(d1_wave.wave_sep_min - 0.09) < 1e-9
        and abs(d1_wave.wave_sep_max - 0.12) < 1e-9,
        "density D=1.0 leaves the wave gap bands at the defaults",
    )
    # (b) D=1.5 divides the wave bands by 1.5, floored at the 0.085 m separation
    # rule: gap 0.10/1.5 -> 0.085 (the floor), 0.16/1.5 -> 0.107, and both boundary
    # bands onto the same floor.
    os.environ["FRUIT_SUPPLY_PATCH_DENSITY"] = "1.5"
    d15_wave = SupplyPlan.from_env(cfg)
    check(
        abs(d15_wave.wave_gap_min - 0.085) < 1e-9
        and abs(d15_wave.wave_gap_max - 0.10666666666666667) < 1e-6
        and abs(d15_wave.wave_sep_min - 0.085) < 1e-9
        and abs(d15_wave.wave_sep_max - 0.085) < 1e-9,
        "density D=1.5 scales the wave bands to 0.085-0.107 / 0.085-0.085",
    )
    check(
        d15_wave.wave_gap_min >= 0.085 - 1e-9
        and d15_wave.wave_sep_min >= 0.085 - 1e-9,
        "density never breaches the 0.085 m separation floor (wave)",
    )
    os.environ.pop("FRUIT_SUPPLY_PATCH_DENSITY")
    os.environ.pop("FRUIT_SUPPLY_WAVE")
    os.environ["FRUIT_SUPPLY_PATCH"] = "1"
    patch_plan = SupplyPlan.from_env(cfg)
    check(
        patch_plan.patch and patch_plan.scatter,
        "FRUIT_SUPPLY_PATCH=1 enables the patch sheet",
    )
    # (c) D=1.0 leaves the patch slice band and the pair probability at the
    # defaults; (d) D=2.0 drives the slice band onto the 0.085 m floor and the
    # abreast probability to 1.0 (every slice carries a pair).
    os.environ["FRUIT_SUPPLY_PATCH_DENSITY"] = "1.0"
    d1_patch = SupplyPlan.from_env(cfg)
    check(
        abs(d1_patch.patch_slice_min - 0.14) < 1e-9
        and abs(d1_patch.patch_slice_max - 0.22) < 1e-9
        and abs(d1_patch.patch_pair - 0.6) < 1e-9,
        "density D=1.0 leaves the patch slice band and pair probability alone",
    )
    os.environ["FRUIT_SUPPLY_PATCH_DENSITY"] = "2.0"
    d2_patch = SupplyPlan.from_env(cfg)
    check(
        abs(d2_patch.patch_slice_min - 0.085) < 1e-9
        and abs(d2_patch.patch_slice_max - 0.11) < 1e-9
        and abs(d2_patch.patch_pair - 1.0) < 1e-9,
        "density D=2.0 floors the slice band at 0.085-0.110 and pairs every slice",
    )
    os.environ.pop("FRUIT_SUPPLY_PATCH_DENSITY")
    check(
        abs(SupplyPlan.from_env(cfg).patch_slice_min - 0.14) < 1e-9,
        "the patch slice band returns to its default when the density env is removed",
    )
    # --- P1c species lock: the composition-controlled test needs a one-species
    # pool, and neither mix knob can express one (`_mix_env` rejects a weight of
    # 0, so `FRUIT_SUPPLY_CLASSES` must list every species with a positive
    # weight; `FRUIT_SUPPLY_GRADES` is the grade mix, not the species mix).
    all_species = len(cfg.fruit_dimensions)
    check(
        len(SupplyPlan.from_env(cfg).classes) == all_species,
        "the species mix defaults to the full pool (the lock is off by default)",
    )
    os.environ["FRUIT_SUPPLY_SPECIES"] = "apple"
    locked = SupplyPlan.from_env(cfg)
    check(
        locked.classes == (("apple", 1.0),),
        "FRUIT_SUPPLY_SPECIES=apple locks the pool to that one species",
    )
    os.environ["FRUIT_SUPPLY_SPECIES"] = "durian"
    unknown = SupplyPlan.from_env(cfg)
    check(
        len(unknown.classes) == all_species,
        "an unknown FRUIT_SUPPLY_SPECIES falls back to the full pool",
    )
    os.environ.pop("FRUIT_SUPPLY_SPECIES")
    os.environ["FRUIT_SUPPLY_GRADES"] = "apple:1"
    check(
        SupplyPlan.from_env(cfg).grades
        == tuple((g, w) for g, w in zip(cfg.grades, (0.5, 0.3, 0.2))),
        "an invalid FRUIT_SUPPLY_GRADES spec is rejected and the default mix is used",
    )
    os.environ["FRUIT_SUPPLY_GRADES"] = "A:1,B:1,C:1"
    check(
        SupplyPlan.from_env(cfg).grades == (("A", 1.0), ("B", 1.0), ("C", 1.0)),
        "a valid FRUIT_SUPPLY_GRADES spec is applied",
    )
    os.environ.pop("FRUIT_SUPPLY_GRADES")
    check(
        abs(patch_plan.patch_slice_min - 0.14) < 1e-9
        and abs(patch_plan.patch_slice_max - 0.22) < 1e-9,
        "patch slice band defaults 0.14-0.22",
    )
    check(abs(patch_plan.patch_pair - 0.6) < 1e-9, "patch pair probability default 0.6")
    check(
        abs(patch_plan.patch_sep_min - 0.085) < 1e-9
        and abs(patch_plan.patch_sep_max - 0.12) < 1e-9,
        "patch lateral separation default 0.085-0.12 (above the 0.08 m rule)",
    )
    os.environ["FRUIT_BIARM_TWOLINE"] = "1"
    check(
        dict(SupplyPlan.from_env(cfg).grades) == {"A": 0.375, "B": 0.375, "C": 0.25},
        "two-line patch default mix is balanced (A/B 37.5 %, C 25 %)",
    )
    os.environ.pop("FRUIT_BIARM_TWOLINE", None)
    check(
        dict(SupplyPlan.from_env(cfg).grades) == {"A": 0.5, "B": 0.3, "C": 0.2},
        "single-arm patch mix unchanged (50/30/20)",
    )
    os.environ["FRUIT_SUPPLY_PATCH_SLICE"] = "0.18"
    scalar = SupplyPlan.from_env(cfg)
    check(
        abs(scalar.patch_slice_min - 0.14) < 1e-9
        and abs(scalar.patch_slice_max - 0.22) < 1e-9,
        "FRUIT_SUPPLY_PATCH_SLICE scalar is a centre +/-0.04",
    )
    os.environ["FRUIT_SUPPLY_PATCH_SLICE"] = "0.12,0.20"
    band = SupplyPlan.from_env(cfg)
    check(
        abs(band.patch_slice_min - 0.12) < 1e-9
        and abs(band.patch_slice_max - 0.20) < 1e-9,
        "FRUIT_SUPPLY_PATCH_SLICE band LO,HI",
    )
    del os.environ["FRUIT_SUPPLY_PATCH_SLICE"]
    os.environ["FRUIT_SUPPLY_SCATTER"] = "0"
    check(
        not SupplyPlan.from_env(cfg).patch,
        "patch requires the scattered feeder (SCATTER=0 ignores it)",
    )

    # 2D-ness invariants on a 90 s free-cadence run. A consumer takes one fruit
    # from the station every 5.6 s (the delivered two-line attempt cadence):
    # without one the queue interlock stalls the line, because the offline
    # belt has no arm to consume it.
    os.environ["FRUIT_SUPPLY_SCATTER"] = "1"
    spawner, plan = make_spawner(scatter=True)
    pair_seps: list[float] = []
    released_x: list[float] = []
    orig_slot = spawner._release_patch_slot

    def patch_slot_hook(along, queue_max, released):
        before = len(released)
        ok = orig_slot(along, queue_max, released)
        xs = [float(spawner.position(s)[0]) for s in released[before:]]
        if len(xs) == 2:
            pair_seps.append(abs(xs[0] - xs[1]))
        released_x.extend(xs)
        return ok

    spawner._release_patch_slot = patch_slot_hook
    spawner.prime(count=4)
    dt = 1.0 / 120.0
    min_planar = 1.0
    plane_violations = 0
    approach_frames = 0
    approach_big = 0
    consume_ticks = int(5.6 / dt)
    for tick in range(int(90.0 / dt)):
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
        if tick > 0 and tick % consume_ticks == 0:
            candidates = [
                s for s in spawner.active
                if not s.parked and not s.held
                and abs(float(spawner.position(s)[0]) - cfg.belt_center[0]) < 0.30
                and float(spawner.position(s)[1]) <= cfg.pick_y + 0.10
            ]
            if candidates:
                picked = min(
                    candidates,
                    key=lambda s: abs(float(spawner.position(s)[1]) - cfg.pick_y),
                )
                spawner.park(picked)
                spawner.active.remove(picked)
        live = [
            s for s in spawner.active
            if not s.parked and not s.held
            and abs(float(spawner.position(s)[0]) - cfg.belt_center[0]) < 0.30
        ]
        for i, first in enumerate(live):
            pa = spawner.position(first)
            for second in live[i + 1:]:
                pb = spawner.position(second)
                min_planar = min(
                    min_planar, float(np.hypot(pa[0] - pb[0], pa[1] - pb[1]))
                )
                if abs(float(pa[1] - pb[1])) < 0.08 and abs(float(pa[0] - pb[0])) < 0.08:
                    plane_violations += 1
        seg = sorted(
            (
                float(spawner.position(s)[1])
                for s in live
                if float(spawner.position(s)[1]) >= cfg.pick_y + 0.10
            ),
            reverse=True,
        )
        if len(seg) >= 2:
            approach_frames += 1
            if max(a - b for a, b in zip(seg, seg[1:])) > 0.40:
                approach_big += 1

    check(len(pair_seps) >= 8, f"patch run has >= 8 abreast slices ({len(pair_seps)})")
    check(
        all(
            plan.patch_sep_min - 1e-9 <= sep <= plan.patch_sep_max + 1e-9
            for sep in pair_seps
        ),
        f"pair separations inside 0.085-0.12 "
        f"({['%.3f' % s for s in pair_seps[:8]]})",
    )
    check(
        min(released_x) <= plan.x_min + 0.02 and max(released_x) >= plan.x_max - 0.02,
        f"lateral coverage reaches both band edges "
        f"(min {min(released_x):.3f} max {max(released_x):.3f})",
    )
    check(
        plane_violations == 0,
        f"the 0.08 m release-clear rule holds in the belt plane "
        f"({plane_violations} violations)",
    )
    check(min_planar >= 0.079, f"no two live fruit closer than 0.08 m ({min_planar:.4f})")
    check(
        approach_frames > 0 and approach_big <= approach_frames * 0.02,
        f"station approach gap > 0.40 m in <= 2 % of frames "
        f"({approach_big}/{approach_frames})",
    )
    # Schedule level (the W3 wave check's analogue): every drawn slice gap is
    # inside the band, so the sheet has no long empty stretch by construction.
    fresh, fresh_plan = make_spawner(scatter=True)
    pattern = [fresh._release_gap() for _ in range(40)]
    check(
        all(
            fresh_plan.patch_slice_min - 1e-9 <= gap <= fresh_plan.patch_slice_max + 1e-9
            for gap in pattern
        ),
        f"slice gaps inside 0.14-0.22 ({['%.3f' % g for g in pattern[:8]]})",
    )
    del os.environ["FRUIT_SUPPLY_PATCH"]
    del os.environ["FRUIT_SUPPLY_SCATTER"]

    # Patch off: the old release streams stay byte-identical. The expected
    # lines are pinned from the pre-patch tree (captured before the patch code
    # existed; the full logs are archived in the W6-A report).
    def release_lines(scatter: bool, seconds: float, wave: bool = False):
        os.environ["FRUIT_SUPPLY_SCATTER"] = "1" if scatter else "0"
        os.environ["FRUIT_SUPPLY_POOL"] = "16"
        os.environ.pop("FRUIT_SUPPLY_PATCH", None)
        if wave:
            os.environ["FRUIT_BIARM_TWOLINE"] = "1"
            os.environ["FRUIT_SUPPLY_WAVE"] = "1"
        else:
            os.environ.pop("FRUIT_BIARM_TWOLINE", None)
            os.environ.pop("FRUIT_SUPPLY_WAVE", None)
        spawner, _plan = make_spawner(scatter=scatter)
        lines: list[str] = []
        original = spawner.respawn

        def hook(sample, along=None, x_jitter=0.10, x=None):
            original(sample, along=along, x_jitter=x_jitter, x=x)
            pos = spawner.position(sample)
            lines.append(
                f"release idx={sample.index} cat={sample.category} {sample.grade} "
                f"y={float(pos[1]):+.6f} x={float(pos[0]):+.6f}"
            )

        spawner.respawn = hook
        spawner.prime(count=4)
        step = 1.0 / 120.0
        for tick in range(int(seconds / step)):
            spawner.update(tick * step)
            for sample in list(spawner.active):
                if sample.parked or sample.held:
                    continue
                pos = spawner.position(sample)
                pos[1] += cfg.belt_speed * step
                spawner._rigids[sample.index].pos = pos
                if pos[1] < cfg.despawn_y:
                    spawner.park(sample)
                    spawner.active.remove(sample)
        return lines, dict(spawner.stats)

    expected_scatter = [
        "release idx=0 cat=strawberry A y=+0.680000 x=+0.350792",
        "release idx=0 cat=strawberry A y=+0.680000 x=+0.318384",
        "release idx=1 cat=lychee A y=+0.680000 x=+0.347572",
        "release idx=1 cat=lychee A y=+0.424275 x=+0.204641",
        "release idx=2 cat=kiwi A y=+0.680000 x=+0.274500",
        "release idx=2 cat=kiwi A y=+0.138828 x=+0.350937",
        "release idx=3 cat=tomato A y=+0.680000 x=+0.218113",
        "release idx=3 cat=tomato A y=+0.679244 x=+0.275051",
        "release idx=4 cat=apple A y=+0.680000 x=+0.287002",
        "release idx=4 cat=apple A y=+0.679469 x=+0.291831",
        "release idx=5 cat=orange A y=+0.680000 x=+0.234677",
        "release idx=5 cat=orange A y=+0.679112 x=+0.244717",
    ]
    lines, stats = release_lines(scatter=True, seconds=120.0)
    check(
        lines[:12] == expected_scatter,
        "patch-off scatter release stream byte-identical (first 12)",
    )
    check(
        stats.get("released") == 61
        and stats.get("supply_skipped") == 1
        and stats.get("fell_off", 0) == 0
        and stats.get("reached_end", 0) == 0,
        f"patch-off scatter run stats unchanged ({sorted(stats.items())})",
    )
    expected_wave = [
        "release idx=0 cat=strawberry A y=+0.680000 x=+0.350792",
        "release idx=0 cat=strawberry A y=+0.680000 x=+0.318384",
        "release idx=1 cat=lychee A y=+0.680000 x=+0.347572",
        "release idx=1 cat=lychee A y=+0.542626 x=+0.204641",
        "release idx=2 cat=kiwi A y=+0.680000 x=+0.274500",
        "release idx=2 cat=kiwi A y=+0.398119 x=+0.350937",
    ]
    lines, stats = release_lines(scatter=True, seconds=120.0, wave=True)
    check(
        lines[:6] == expected_wave,
        "patch-off wave release stream byte-identical (first 6)",
    )
    check(
        stats.get("released") == 118 and stats.get("supply_skipped") == 1,
        f"patch-off wave run stats unchanged ({sorted(stats.items())})",
    )
    expected_fixed = [
        "release idx=0 cat=strawberry A y=+0.680000 x=+0.341229",
        "release idx=0 cat=strawberry A y=+0.680000 x=+0.342418",
        "release idx=1 cat=lychee A y=+0.680000 x=+0.342952",
        "release idx=1 cat=lychee A y=+0.380000 x=+0.344425",
    ]
    lines, stats = release_lines(scatter=False, seconds=60.0)
    check(
        lines[:4] == expected_fixed,
        "patch-off fixed line release stream byte-identical (first 4)",
    )
    check(
        stats.get("released") == 42,
        f"patch-off fixed line stats unchanged ({sorted(stats.items())})",
    )

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

    # --- P4-C1 H1: trickle feed (`FRUIT_SUPPLY_TRICKLE_LATE_S`, default off) --
    # The actuator is consume-and-skip with a lateness cap: a due slot older
    # than the cap is dropped (`supply_skipped` + the lazy `supply_trickled`)
    # instead of delivered late near/below the moving catch's selection floor.
    # Resolve default / parse / clamp first, then drive the pump on a
    # driver-shaped clock (0.5 s of per-tick pumps, then a 15.5 s no-pump gap).
    os.environ["FRUIT_SUPPLY_SCATTER"] = "1"
    os.environ["FRUIT_SUPPLY_POOL"] = "16"
    os.environ.pop("FRUIT_SUPPLY_PATCH", None)
    os.environ.pop("FRUIT_SUPPLY_PATCH_DENSITY", None)
    os.environ.pop("FRUIT_SUPPLY_TRICKLE_LATE_S", None)
    check(SupplyPlan.from_env(cfg).trickle_late_s == 0.0, "trickle default is off (0.0)")
    os.environ["FRUIT_SUPPLY_TRICKLE_LATE_S"] = "1.2"
    check(
        abs(SupplyPlan.from_env(cfg).trickle_late_s - 1.2) < 1e-9,
        "trickle cap parsed from FRUIT_SUPPLY_TRICKLE_LATE_S",
    )
    os.environ["FRUIT_SUPPLY_TRICKLE_LATE_S"] = "-3"
    check(
        SupplyPlan.from_env(cfg).trickle_late_s == 0.0,
        "a negative trickle cap is clamped to off",
    )
    os.environ.pop("FRUIT_SUPPLY_TRICKLE_LATE_S", None)

    def driver_clock(trickle: str | None, patch: bool = False):
        """Pump on the driver's clock: 0.5 s per-tick windows, 15.5 s gaps.

        Returns `(spawner, rows, positions)` with `rows` the bodies released
        per window and `positions` the along-y of every respawned body (so a
        freshness invariant applies to the trickle's deliveries).
        """
        if trickle is None:
            os.environ.pop("FRUIT_SUPPLY_TRICKLE_LATE_S", None)
        else:
            os.environ["FRUIT_SUPPLY_TRICKLE_LATE_S"] = trickle
        if patch:
            os.environ["FRUIT_SUPPLY_PATCH"] = "1"
            os.environ["FRUIT_SUPPLY_PATCH_DENSITY"] = "1.60"
        else:
            os.environ.pop("FRUIT_SUPPLY_PATCH", None)
        spawner, _plan = make_spawner(scatter=True)
        positions: list[float] = []
        spawner.prime(count=4)
        # Hook installed after the prime so `positions` carries only the
        # pump's own deliveries (the prime places the ladder anywhere down to
        # ~0.05 m by design).
        original = spawner.respawn

        def hook(sample, along=None, x_jitter=0.10, x=None):
            original(sample, along=along, x_jitter=x_jitter, x=x)
            positions.append(float(spawner.position(sample)[1]))

        spawner.respawn = hook
        step = 1.0 / 120.0
        t = 0.0
        rows: list[int] = []

        def advance_ticks(n: int) -> None:
            for _ in range(n):
                for sample in list(spawner.active):
                    if sample.parked or sample.held:
                        continue
                    pos = spawner.position(sample)
                    pos[1] += cfg.belt_speed * step
                    spawner._rigids[sample.index].pos = pos
                    if float(pos[1]) < cfg.despawn_y:
                        spawner.park(sample)
                        spawner.active.remove(sample)

        def window() -> None:
            nonlocal t
            rel0 = spawner.stats["released"]
            for _ in range(60):
                advance_ticks(1)
                t += step
                spawner.update(t)
            rows.append(spawner.stats["released"] - rel0)

        window()  # the batch-start window
        for _ in range(2):
            advance_ticks(int(round(15.5 / step)))
            t += 15.5
            window()
        return spawner, rows, positions

    control_pump, control_rows, control_pos = driver_clock(None)
    check(
        max(control_rows) >= 2 and min(control_pos) < 0.45,
        f"shipped pump delivers a multi-body backlog burst that reaches down "
        f"toward the station ({control_rows}, min y {min(control_pos):.3f})",
    )
    check(
        "supply_trickled" not in control_pump.stats,
        "the off path never creates the supply_trickled counter (stats byte-identical)",
    )
    trickle_pump, trickle_rows, trickle_pos = driver_clock("1.2")
    check(
        max(trickle_rows) <= 2,
        f"trickle delivers at most one slice (<=2 bodies) per pump window ({trickle_rows})",
    )
    check(
        trickle_pump.stats.get("supply_trickled", 0) > 0,
        "trickle consumes the stale backlog (supply_trickled > 0)",
    )
    check(
        all(y >= 0.68 - 1.2 * 0.12 - 1e-6 for y in trickle_pos),
        f"every trickle delivery is fresh (y >= spawn_y - cap*v = 0.536; "
        f"min {min(trickle_pos):.3f})",
    )
    # The uniform schedule's periods run to 2.92 s (> the 1.2 s cap), so a
    # window may legitimately deliver nothing there; the H1 scenario is the
    # patch sheet at D=1.6, whose widest slice period is 0.1375 m / 0.12 m/s =
    # 1.146 s < cap - hence every post-gap window delivers at least one slice
    # (<=2 slices = <=4 bodies).
    patch_pump, patch_rows, patch_pos = driver_clock("1.2", patch=True)
    check(
        max(patch_rows) <= 4 and min(patch_rows[1:]) >= 1,
        f"trickle on the patch sheet: <=2 slices per window and >=1 slice at "
        f"every post-gap window ({patch_rows})",
    )
    check(
        all(y >= 0.68 - 1.2 * 0.12 - 1e-6 for y in patch_pos),
        f"every patch trickle delivery is fresh (min {min(patch_pos):.3f})",
    )
    check(
        patch_pump.stats.get("supply_trickled", 0) > 0,
        "trickle on the patch sheet consumes the stale backlog",
    )
    os.environ.pop("FRUIT_SUPPLY_PATCH", None)
    os.environ.pop("FRUIT_SUPPLY_PATCH_DENSITY", None)
    os.environ.pop("FRUIT_SUPPLY_TRICKLE_LATE_S", None)

    for key in list(os.environ):
        if key.startswith("FRUIT_SUPPLY_"):
            del os.environ[key]
    os.environ.pop("FRUIT_BIARM_TWOLINE", None)
    print(
        f"patch sheet (offline run): {len(pair_seps)} pair slices, separations "
        f"{min(pair_seps):.3f}-{max(pair_seps):.3f} m, x {min(released_x):.3f}-"
        f"{max(released_x):.3f} m, min live planar separation {min_planar:.3f} m, "
        f"approach gaps >0.40 m {approach_big}/{approach_frames} frames"
    )
    print(f"supply selftest ok ({checks} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
