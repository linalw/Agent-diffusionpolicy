#!/usr/bin/env python3
"""P129 selfcheck leg - the pad-material knobs' **unset path**, and the algebra.

The phase ships no code: the knobs it needs already existed
(`FRUIT_FINGER_MU`, `FRUIT_CAGE_PAD_MU`, `FRUIT_CAGE_CLOSE_STIFFNESS`,
`FRUIT_CAGE_HOLD_STIFFNESS`, plus `FRUIT_DYNAMIC_CLOSE_FREEZE` for the protocol).
What it owes is a guard that the shipped path is what the record says it is, so a
later edit cannot quietly move the material, the close profile or the hard stop
under the numbers this phase publishes.

1. `cage_hand.PAD_MU` / `CLOSE_STIFFNESS` / `HOLD_STIFFNESS` / `PAD_STIFFNESS` read
   2.0 / 0 / 0 / 1e5 with the environment unset, and re-read the environment when
   it is set (the module's own `_f`, reloaded - pxr is stubbed, no simulator).
2. The openarm finger material's default is 2.0 (0.0 for the kinematic hand) at
   **both** `scene.py` sites, read from the source so the rule cannot drift.
3. The pair arithmetic the record rests on: PhysX averages, so the shipped pad
   (2.0) against the pool's 0.51-0.92 fruit gives **1.26-1.46** - P104's measured
   `mu_app` band.
4. The algebra's thresholds are reproduced by `logs/p129/algebra.py`'s own
   functions: `mu_ceiling(4) = 0.815` per fruit and the pool-wide window closing
   at `0.613` (s_max/s_min = 2.35).

    python3 scripts/265_p129_material_selftest.py
"""

from __future__ import annotations

import importlib
import os
import re
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "logs", "p129"))

# --- stub pxr just enough to import fruit_sorting.cage_hand ----------------- #
for name in ("pxr", "isaacsim", "isaacsim.core", "isaacsim.core.experimental"):
    sys.modules.setdefault(name, types.ModuleType(name))
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))

checks = 0


def ok(cond, what):
    global checks
    checks += 1
    assert cond, f"FAILED: {what}"
    print(f"  ok  {what}")


def cage_with(env):
    """Import (or reload) `cage_hand` under `env` and return its constants."""
    keep = {}
    for k in ("FRUIT_CAGE_PAD_MU", "FRUIT_CAGE_CLOSE_STIFFNESS",
              "FRUIT_CAGE_HOLD_STIFFNESS", "FRUIT_CAGE_PAD_STIFFNESS"):
        keep[k] = os.environ.pop(k, None)
    os.environ.update({k: v for k, v in env.items() if v is not None})
    try:
        from fruit_sorting import cage_hand

        importlib.reload(cage_hand)
        return (cage_hand.PAD_MU, cage_hand.CLOSE_STIFFNESS,
                cage_hand.HOLD_STIFFNESS, cage_hand.PAD_STIFFNESS)
    finally:
        for k in ("FRUIT_CAGE_PAD_MU", "FRUIT_CAGE_CLOSE_STIFFNESS",
                  "FRUIT_CAGE_HOLD_STIFFNESS", "FRUIT_CAGE_PAD_STIFFNESS"):
            os.environ.pop(k, None)
        for k, v in keep.items():
            if v is not None:
                os.environ[k] = v


print("P129 pad material: the unset path")
base = cage_with({})
ok(base[0] == 2.0, f"cage pad mu unset -> 2.0 (got {base[0]})")
ok(base[1] == 0.0, f"close stiffness unset -> 0, the single-profile drive (got {base[1]})")
ok(base[2] == 0.0, f"hold stiffness unset -> 0, no hard stop (got {base[2]})")
ok(base[3] == 1.0e5, f"the shipped pad drive is 1e5 N/m (got {base[3]})")

low = cage_with({"FRUIT_CAGE_PAD_MU": "0.5", "FRUIT_CAGE_CLOSE_STIFFNESS": "4300",
                 "FRUIT_CAGE_HOLD_STIFFNESS": "100000"})
ok(low[0] == 0.5, f"FRUIT_CAGE_PAD_MU=0.5 -> {low[0]}")
ok(low[1] == 4300.0, f"FRUIT_CAGE_CLOSE_STIFFNESS=4300 -> {low[1]}")
ok(low[2] == 100000.0, f"FRUIT_CAGE_HOLD_STIFFNESS=100000 -> {low[2]}")
ok(low[3] == 1.0e5, "the pad drive itself does not move with the material")
ok(cage_with({})[0] == 2.0, "and it goes back to 2.0 when the knobs are unset again")

print("P129 pad material: the openarm finger material's default")
src = open(os.path.join(ROOT, "src", "fruit_sorting", "scene.py"), errors="replace").read()
hits = re.findall(
    r'FRUIT_FINGER_MU", "2\.0" if (?:kind == "openarm"|openarm_hand) else "0\.0"', src
)
ok(len(hits) == 2, f"both finger-material sites default openarm to 2.0 (found {len(hits)})")
ok("FRUIT_FINGER_FRICTION_COMBINE" in src,
   "the combine-mode override exists (the sim's default is the average, P104)")

print("P129 pad material: the pair arithmetic")
muts = []
for line in open(os.path.join(ROOT, "logs", "p110", "fixture.txt"), errors="replace"):
    m = re.search(r"mu=\s*([0-9.]+)\s+pair\(belt\)", line)
    if m:
        muts.append(float(m.group(1)))
ok(len(muts) == 16, f"the pool table reads 16 fruits (got {len(muts)})")
band = sorted(0.5 * (2.0 + v) for v in (min(muts), max(muts)))
ok(abs(band[0] - 1.26) < 0.02 and abs(band[1] - 1.46) < 0.02,
   f"the shipped pair is {band[0]:.2f}-{band[1]:.2f} (P104's measured 1.25-1.46)")

print("P129 pad material: the algebra's thresholds")
import algebra  # noqa: E402  (logs/p129/algebra.py, offline)

ok(abs(algebra.mu_ceiling(4) - 0.815) < 0.002,
   f"the four-pad friction ceiling is 0.815 (got {algebra.mu_ceiling(4):.3f})")
pool = algebra.pool()
ds = sorted(r["d"] for r in pool)
lo, hi = 0.0, 1.0
for _ in range(200):
    mid = 0.5 * (lo + hi)
    w = min(algebra.k_bounds(d, mid, 4)[1] for d in ds) - max(
        algebra.k_bounds(d, mid, 4)[0] for d in ds)
    if w > 0.0:
        lo = mid
    else:
        hi = mid
ok(abs(lo - 0.613) < 0.003, f"the pool-wide window closes at mu = {lo:.3f}")
k_lo = max(algebra.k_bounds(d, 0.6, 4)[0] for d in ds)
k_hi = min(algebra.k_bounds(d, 0.6, 4)[1] for d in ds)
ok(abs(k_lo - 4223.0) < 3.0 and abs(k_hi - 4400.0) < 3.0,
   f"the mu 0.6 window is [{k_lo:.0f}, {k_hi:.0f}] N/m")
s0 = algebra.s_of(0.060)
ok(abs(algebra.closed_form_4(s0, 1.36) / s0 - 1.36) < 1e-9,
   "the four-pad residual is `mu s` (1.36 s at the shipped pair)")
band3 = [algebra.closed_form_3(s0, m) / s0 for m in (1.25, 1.46)]
ok(abs(band3[0] - 0.838) < 0.005 and abs(band3[1] - 0.915) < 0.005,
   f"the three-pad residual is {band3[0]:.2f}-{band3[1]:.2f} s over the shipped "
   f"pair band (P112's 0.84-0.91)")

print(f"\nP129 pad material: {checks} checks, all ok")
