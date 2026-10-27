#!/usr/bin/env python3
"""P50 phase 2 offline check of the release-offset knob (no simulator).

Stubs `pxr`/`isaacsim` the way `scripts/172_supply_selftest.py` does, then pins the
four things the phase-2 claim rests on that do not need physics:

1. **the tables parse and cover their pool**: `configs/release_offsets_accept_s5.json`
   and `..._pear_s5.json` load through `fruits.load_release_offset_table`, and every
   instance the phase-1 probe measured has a signature entry (16/16 each);
2. **the mode rule** is the pre-registered one: the two rollers read the midpoint of
   their extreme live modes (kiwi +44.80 mm, strawberry -28.91 mm) and the other 14
   read their live mean;
3. **the arithmetic**: `x_spawn = planned - offset/1000`, no clamp, and the resulting
   excursion over the shipped `U(0.20, 0.36)` band is `0.165..0.387 m` - inside the
   belt (`x = 0.11..0.57`), which is why the band is not clamped;
4. **the unset contract**: with `FRUIT_RELEASE_OFFSET` unset the module resolves to
   inactive, `_release_offset` returns the planned x, and no `offset_*` counter is
   created - the shipped `stats` dict is unchanged (the byte-identity itself is
   proved by the M4 acceptance, not here).

Run: `python3 logs/p50/p2/offset_knob_selftest.py`
"""

from __future__ import annotations

import os
import sys
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- stub pxr / isaacsim just enough to import fruit_sorting.fruits --------- #
for name in ("pxr", "isaacsim", "isaacsim.core", "isaacsim.core.experimental"):
    sys.modules.setdefault(name, types.ModuleType(name))
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
app_mod = types.ModuleType("isaacsim.core.experimental.utils.app")
app_mod.update_app = lambda *a, **k: None
sys.modules.setdefault("isaacsim.core.experimental.utils.app", app_mod)
utils_mod = types.ModuleType("isaacsim.core.experimental.utils")
sys.modules.setdefault("isaacsim.core.experimental.utils", utils_mod)
prims_mod = types.ModuleType("isaacsim.core.experimental.prims")
prims_mod.RigidPrim = object
sys.modules.setdefault("isaacsim.core.experimental.prims", prims_mod)

from fruit_sorting import fruits  # noqa: E402
import make_offset_table as maker  # noqa: E402

ACCEPT = os.path.join(ROOT, "configs", "release_offsets_accept_s5.json")
PEAR = os.path.join(ROOT, "configs", "release_offsets_pear_s5.json")

failures = 0


def check(ok: bool, label: str, detail: str = "") -> None:
    global failures
    if not ok:
        failures += 1
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def main() -> int:
    print("P50 phase 2 - the release-offset knob, offline")
    print(f"tree: {ROOT}")

    # 1. the tables parse and cover their pool ----------------------------- #
    print("\n1. the tables")
    accept = fruits.load_release_offset_table(ACCEPT)
    pear = fruits.load_release_offset_table(PEAR)
    check(len(accept) == 16, "acceptance table has 16 instance signatures", f"{len(accept)}")
    check(len(pear) == 16, "pear table has 16 instance signatures", f"{len(pear)}")
    accept_pool = maker.read_live("offset_live_s5.log")
    pear_pool = maker.read_cells("offset_pear_s5.log")
    accept_sigs = {maker.signature(r["cat"], r["dia_mm"]) for r in accept_pool.values()}
    pear_sigs = {maker.signature(r["cat"], r["dia_mm"]) for r in pear_pool.values()}
    check(accept_sigs <= set(accept), "acceptance keys cover the probe's 16 instances",
          f"{len(accept_sigs & set(accept))}/16")
    check(pear_sigs <= set(pear), "pear keys cover the probe's 16 instances",
          f"{len(pear_sigs & set(pear))}/16")
    check(all(v == 0.0 for v in pear.values()), "the pear table is identity")

    # 2. the mode rule ------------------------------------------------------ #
    print("\n2. the mode rule (PREREG section 2)")
    modes = {maker.signature(r["cat"], r["dia_mm"]): (r, value, rule)
             for r, (value, rule) in ((maker.read_live("offset_live_s5.log")[i],
                                       maker.instance_value(
                                           maker.read_live("offset_live_s5.log")[i]["offsets"]))
                                      for i in maker.read_live("offset_live_s5.log"))}
    kiwi = modes["kiwi|55.8"]
    straw = modes["strawberry|37.2"]
    check(abs(kiwi[1] - 44.805) < 1e-6 and "mode-midpoint" in kiwi[2],
          "kiwi|55.8 = midpoint of [+34.98, +54.63]", f"{kiwi[1]:+.2f} mm")
    check(abs(straw[1] + 28.915) < 1e-6 and "mode-midpoint" in straw[2],
          "strawberry|37.2 = midpoint of [-35.73, -22.10]", f"{straw[1]:+.2f} mm")
    single = [key for key, (_, _, rule) in modes.items() if "mode-midpoint" not in rule]
    check(len(single) == 14, "the other 14 instances are single-mode (live mean)", f"{len(single)}")
    check(abs(accept["kiwi|55.8"] - 44.805) < 1e-6, "the applied table carries the rule")

    # 3. the arithmetic ----------------------------------------------------- #
    print("\n3. the arithmetic (planned -> spawn)")
    spawner = fruits.FruitSpawner.__new__(fruits.FruitSpawner)
    spawner.supply = types.SimpleNamespace(patch=False, bed=False)
    spawner.stats = {"offset_shifted": 0, "offset_misses": 0, "offset_scoped_off": 0}
    spawner._release_offsets = dict(accept)
    spawner._release_table_path = "configs/release_offsets_accept_s5.json"
    saved = fruits.RELEASE_OFFSET_ACTIVE, fruits.RELEASE_OFFSET_DIAG
    fruits.RELEASE_OFFSET_ACTIVE, fruits.RELEASE_OFFSET_DIAG = True, False
    sample = types.SimpleNamespace(index=2, category="kiwi", diameter=0.0558)
    planned = 0.3512
    spawn = spawner._release_offset(sample, planned)
    check(abs(spawn - (planned - 0.044805)) < 1e-9,
          "kiwi|55.8 at planned 0.3512 spawns at planned - 44.805 mm", f"{spawn:+.5f}")
    check(spawner.stats["offset_shifted"] == 1 and spawner.stats["offset_misses"] == 0,
          "the shift is counted")
    miss = types.SimpleNamespace(index=99, category="dragonfruit", diameter=0.05)
    check(spawner._release_offset(miss, planned) == planned
          and spawner.stats["offset_misses"] == 1,
          "a signature miss is uncompensated and counted")
    spawner.supply.patch = True
    check(spawner._release_offset(sample, planned) == planned
          and spawner.stats["offset_scoped_off"] == 1,
          "the patch/bed scope gate skips and counts")
    spawner.supply.patch = False
    lo = 0.20 - max(accept.values()) / 1000.0
    hi = 0.36 - min(accept.values()) / 1000.0
    belt = (0.11, 0.57)  # cfg.belt_center[0] +/- belt_size[0]/2 at the shipped scene
    check(belt[0] < lo < hi < belt[1],
          "the unclamped spawn excursion stays on the belt",
          f"{lo:.3f}..{hi:.3f} m inside {belt[0]}-{belt[1]} m")
    fruits.RELEASE_OFFSET_ACTIVE, fruits.RELEASE_OFFSET_DIAG = saved

    # 4. the unset contract ------------------------------------------------- #
    print("\n4. the unset contract")
    check(fruits.RELEASE_OFFSET_ACTIVE is False,
          "FRUIT_RELEASE_OFFSET unset resolves to inactive")
    check(fruits.RELEASE_OFFSET_TABLE_PATH == "", "no table path is read when unset")
    bare = fruits.FruitSpawner.__new__(fruits.FruitSpawner)
    bare.supply = types.SimpleNamespace(patch=False, bed=False)
    bare.stats = {"released": 0, "reached_end": 0, "fell_off": 0, "discharged": 0,
                  "supply_skipped": 0}
    before = dict(bare.stats)
    check(bare._release_offset(sample, planned) == planned,
          "the unset path returns the planned x untouched")
    check(bare.stats == before,
          "the unset path adds no stats key (172's stats comparison is safe)")
    source = open(os.path.join(ROOT, "src", "fruit_sorting", "fruits.py"),
                  encoding="utf-8").read()
    check(source.count("x = self._release_offset(sample, float(x))") == 1,
          "exactly one compensation call site, inside respawn")
    check("FRUIT_RELEASE_OFFSET=1 needs FRUIT_RELEASE_OFFSET_TABLE" in source,
          "a knob-on run without a table refuses to start")

    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} failure(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
