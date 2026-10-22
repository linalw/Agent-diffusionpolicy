"""Offline audit of the dense 2D bed supply (`FRUIT_SUPPLY_BED`, P32 phase 1).

    python3 scripts/211_bed_audit.py

No simulator: `fruits.py` imports Isaac Sim, so this script stubs pxr/isaacsim
the way `scripts/172_supply_selftest.py` does, imports the *real* spawner and
drives it on a fake belt (pure -Y translation, one consumer every 5.6 s). The
schedule itself comes from the pxr-free `fruit_sorting.bed`, which is what makes
the pattern reproducible here and in the spawner from the same seed.

What it answers (the P32 phase-1 gate, revised by Gate 1 and by phase A):

* **the rows**: fruit per row (the abreast edge pair at x = 0.20/0.36 plus the
  conditional staggered middle at x = 0.28), rows per metre, the mean pitch, the
  within-row separations (the 0.16 m edge pair and the 0.103-0.110 m middle
  diagonal), the stagger (half a row pitch) and the same-along clusters - a
  single-file zigzag reads as all-singleton clusters, which is the defect this
  schedule replaces;
* **the pack**: columns, every pairwise distance, the per-pair grasp-corridor
  margin (`d - 0.066 - max(r_i, r_j) - margin`, the OpenArm open-jaw envelope),
  the refused rows, the grade mix, the count per metre and the 1.1 m
  spawn-window envelope;
* **the corridor**: no released pair is closer than 0.08 m (the legacy
  `_release_clear` floor) or than `0.066 + max(r_i, r_j) + margin` (the jaw's
  open span plus the 6 mm margin), so a touching pack is *not* produced;
* **the delivered belt**: the real spawner on a fake belt, at the shipped
  `FRUIT_QUEUE_MAX=6` and at 18, each at the per-tick / 3 s / attempt-boundary
  (16 s) `update` cadence. Reports the mean candidate count in **both** windows -
  the 1.1 m spawn window (all ticks and at pick ticks) and the **selector
  window** the moving catch actually draws from (`>= pick_y + 0.40`, see
  `CATCH_FLOOR`) - plus the **delivered density from `bed_placed`** (placements,
  not draws), the live-recycle fraction (`bed_live_recycled / bed_draws`, must
  be 0), the completed spawn -> despawn transits, the body-gap and row-gap
  distributions, the delivered class/grade mix and the live pairwise
  separations. Since P32 phase A the bed's interlock is its own approach band,
  so the two queue depths deliver the same belt - asserted;
* **the two Gate-A residuals (R1/R2, fixed here)**: a bed-scoped z-skip that
  refuses a placed fruit on a raised output lane (a `_pick_recyclable` draw must
  never take one) with the same two bodies at main-belt height as the positive
  control, and the **belt-end despawn probe** - one boundary pump then 14 s of
  belt travel with the sweep off (the class reproduces: bodies reach the floor
  and the next pump charges them `fell_off`, `reached_end` 0) and on (every one
  is recycled at `despawn_y` as `reached_end`, nothing reaches the floor), with
  the between-belts payload staying `fell_off` in both. `integrated` cannot
  produce this class: its own tick loop despawns at `despawn_y`. The two guards
  are that a sweep never touches a mid-belt body and that a bed-off spawner's
  `scan_despawn` is inert;
* **the bedrock**: with `FRUIT_SUPPLY_BED` unset the legacy scatter / wave /
  patch / fixed slot streams hash to the values recorded on the pre-bed tree,
  i.e. the bed draws no legacy RNG and changes no legacy slot;
* **the defaults**: bed off, bed requires the scattered feeder, bed pool 40 (an
  explicit `FRUIT_SUPPLY_POOL` wins), and when several schedules are set the bed
  wins (bed > patch > wave > scatter).

`--fast` is the selfcheck leg (45 s per cell, 2 of the 3 cadences); the full run
is the record and must stay under ~10 s.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import math
import os
import random
import sys
import types
from collections import Counter
from dataclasses import replace

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
from fruit_sorting.bed import (  # noqa: E402
    OPEN_JAW_HALF_SPAN,
    RELEASE_CLEAR,
    BedPlan,
    BedSchedule,
)
from fruit_sorting.fruits import (  # noqa: E402
    FruitSample,
    FruitSpawner,
    SupplyPlan,
    _mix_allocate,
)

#: Slot-stream digests recorded on the tree *before* the bed existed
#: (`src/fruit_sorting/fruits.py` at commit `7f9eb34`-era working tree, the same
#: fake-belt harness: 4-slot prime, 120 s, SEED=5, pool 16). The audit recomputes
#: them on the current tree with the bed off; a mismatch means the bed branch
#: touched a legacy RNG draw or a legacy slot position.
PRE_CHANGE_DIGESTS = {
    "scatter": ("a9f310a9ec1d4baadea3fd999104173e1716cba2e3e415a665ea0f8fac44c248", 122),
    "wave": ("c67cbc5fb1b03839e3417dacda3c70d5cd35ff2b1375df532b62c8d5f0724f8a", 236),
    "patch": ("711b6f481dde03758457c77b0006d029dc681484692bb19ada1ee22e6290941b", 240),
    "fixed": ("7f5f2cace85af43e0a590c0b68e1169753d37f64761ac949025119eff7b7ec8a", 83),
}

#: The P32 work note's declared columns and **row pitch** band (the shipped
#: defaults); the audit asserts the resolved plan carries them so a drifted
#: default is caught rather than silently printed.
EXPECT_COLUMNS = (0.20, 0.28, 0.36)
EXPECT_ALONG = (0.13, 0.15)

SEED = 5
#: The shipped bed pool (`bed.BED_POOL` = 40): 2x the measured live capacity of
#: a packed belt, so a draw never has to recycle a live body (gate finding B1).
POOL = 40
ROWS = 80
WINDOW = 1.10
#: The selector's own window, measured from the pick station: `select_target`
#: refuses a moving-catch candidate below `pick_y + _dynamic_select_floor()`,
#: which on the shipped line resolves to ~0.40 m (`_dynamic_pick_lead` 0.19 +
#: belt speed x 1.5 s setup + 0.03 margin). The Gate-1 B2 read used the 1.1 m
#: *spawn* window, which includes the fruit downstream of the station that the
#: selector can never take; the stock band is the number the sim starves on
#: (`logs/p32/52_bed_pipeline2.log` attempt 9: 11 live fruit, window 0). The
#: audit reports both.
CATCH_FLOOR = 0.40
#: Same-along tolerance for the "abreast" read: two slots within this along
#: distance are one row on the belt (the edge pair is at one along by
#: construction; the middle is half a pitch away).
ABREAST_TOL = 0.005


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


def clear_supply_env() -> None:
    for key in list(os.environ):
        if key.startswith("FRUIT_SUPPLY_") or key.startswith("FRUIT_BIARM_"):
            del os.environ[key]
    os.environ["FRUIT_BELT_SPEED"] = "0.12"


def synthetic_pool(cfg: SceneConfig, pool: int, seed: int, grades) -> list[tuple[str, float, str]]:
    """A deterministic stand-in for `create_pool`'s pool.

    The real pool's *arrival order* cannot be reproduced offline: `_create_fruit`
    draws diameters, colours, stem noise and materials from the spawner's RNG
    before `create_pool` shuffles the samples, and the mesh authoring consumes a
    varying number of draws. The audit therefore draws the same *composition*
    (one diameter per class band, the designed grade mix) from its own seed and
    says so; the corridor statistics then have the pool's real size distribution
    (2.8-7.0 cm, half of the classes >= 5.8 cm), which is what the rule is
    sensitive to.
    """
    rng = random.Random(seed)
    names = list(cfg.fruit_dimensions)
    allocated = _mix_allocate(grades, pool)
    rng.shuffle(allocated)
    out = []
    for i in range(pool):
        name = names[i % len(names)]
        lo, hi = cfg.fruit_dimensions[name]
        out.append((name, rng.uniform(lo, hi), allocated[i]))
    # The spawner shuffles its samples too (`create_pool`), so the arrival order
    # is a random permutation of the pool's radii - the schedule's skip rate
    # depends on that order, which is why the audit also reports a band over
    # several permutations below.
    rng.shuffle(out)
    return out


def make_spawner(cfg: SceneConfig, pool_items, seed: int = SEED) -> FruitSpawner:

    spawner = FruitSpawner(FakeStage(), cfg, seed=seed)
    for i, (name, diameter, grade) in enumerate(pool_items):
        spawner.samples.append(
            FruitSample(
                index=i,
                prim_path=f"/World/Fruits/Fruit_{i:02d}",
                category=name,
                diameter=diameter,
                mass=0.1,
                friction=0.7,
                grade=grade,
                ripeness=0.8,
                defective=False,
                parked=True,
            )
        )
        spawner._rigids[i] = FakeRigid()
    return spawner


# --------------------------------------------------------------------------- #
# 1. The pure schedule (bed.py only): the rows' packing.
# --------------------------------------------------------------------------- #
def pure_rows(plan: BedPlan, radii, seed: int, due_rows: int, shift_room: bool = True):
    """Run the row schedule in travel time - the steady-drip pump, no simulator.

    Every on-time row is released at the spawn point, so what the schedule
    really produces is a sequence of *times*: row k is released after `s_k`
    metres of belt travel. At a common instant the belt position is
    `spawn_y - (S - s_k)` (S = the newest row's travel), i.e. **monotone in
    s_k**: an earlier row sits further downstream. Recording positions as `+s`
    therefore reproduces the pair geometry exactly (a pair distance is a
    difference) and keeps "upstream" = `+along`, the same direction the pump's
    bounded shift uses (`along_max = spawn_y`); the report converts the
    coordinates to the t=T belt frame afterwards. The row's middle is placed
    half of the *previous* pitch downstream of its pair in the same call
    (`s - prev_pitch/2`), i.e. exactly midway between this row and the one
    before it, which is where a real half-period of travel puts it.

    The pump's levers are modelled: the drawn row pitch (`next_gap`), the pair
    rule against every live slot (`BedSchedule.place_row`), the bounded
    upstream shift and the skip. `shift_room=True` gives the row its shift
    budget (the pump's backlog room); `False` is the on-time bound
    (`along_max=along`, no room), which is what a per-tick driver without a
    backlog gives the schedule.
    """
    schedule = BedSchedule(plan, seed=seed)
    width = len(plan.columns)
    travelled = 0.0
    rows = []
    slots = []
    refused = 0
    due = 0
    while due < due_rows:
        pitch = schedule.next_gap()
        due += 1
        row_radii = [radii[(width * (due - 1) + i) % len(radii)] for i in range(width)]
        along = travelled
        row = schedule.place_row(
            along,
            row_radii,
            [(slot.along, slot.x, slot.radius) for slot in slots],
            along_max=None if shift_room else along,
        )
        if row is None:
            refused += 1
            travelled += pitch
            continue
        rows.append(row)
        slots.extend(row.slots)
        travelled += pitch
    return rows, slots, schedule, {"due": due, "rows": len(rows), "refused": refused}


def belt_frame(rows, spawn_y: float = 0.68):
    """Convert the travel-time positions (`+s`) to the t=T belt snapshot.

    The last row sits at the spawn point and every earlier one downstream by the
    travel it has accumulated since, which is the belt's actual arrangement at
    that instant (the pair distances are unchanged by the shift).
    """
    if not rows:
        return [], []
    latest = max(row.along for row in rows)
    offset = spawn_y - latest
    framed_rows = [
        replace(
            row,
            along=row.along + offset,
            slots=tuple(replace(slot, along=slot.along + offset) for slot in row.slots),
        )
        for row in rows
    ]
    return framed_rows, [slot for row in framed_rows for slot in row.slots]


def pair_census(plan: BedPlan, placed) -> dict:
    """Every pairwise distance and both corridor-margin readings."""
    distances = []
    slacks = []  # d - 0.066 - max(r_i, r_j) - margin  (the enforced rule)
    literal = []  # min over ordered pairs of d - 0.066 - r_other
    violations = 0
    for i, first in enumerate(placed):
        for second in placed[i + 1:]:
            d = math.hypot(first.along - second.along, first.x - second.x)
            slack = plan.pair_margin(
                first.along, first.x, first.radius,
                second.along, second.x, second.radius,
            )
            ordered = min(
                plan.declared_pair_margin(
                    first.along, first.x, second.along, second.x, second.radius
                ),
                plan.declared_pair_margin(
                    second.along, second.x, first.along, first.x, first.radius
                ),
            )
            distances.append(d)
            slacks.append(slack)
            literal.append(ordered)
            if not plan.pair_clear(
                first.along, first.x, first.radius,
                second.along, second.x, second.radius,
            ):
                violations += 1
    distances.sort()
    slacks.sort()
    return {
        "pairs": len(distances),
        "min_d": distances[0] if distances else float("nan"),
        "p10_d": distances[max(0, len(distances) // 10)] if distances else float("nan"),
        "median_d": distances[len(distances) // 2] if distances else float("nan"),
        "min_slack": slacks[0] if slacks else float("nan"),
        "min_literal": min(literal) if literal else float("nan"),
        "violations": violations,
        "distances": distances,
    }


def row_census(plan: BedPlan, rows, slots) -> dict:
    """The row structure: fruit per row, rows/m, within-row gaps, stagger."""
    counts = Counter(row.fruit_count for row in rows)
    has_middle = sum(1 for row in rows if row.has_middle)
    row_ys = sorted(row.along for row in rows)
    rows_span = row_ys[-1] - row_ys[0] if len(row_ys) > 1 else float("nan")
    mean_pitch = rows_span / (len(row_ys) - 1) if len(row_ys) > 1 else float("nan")
    rows_per_m = (len(row_ys) - 1) / rows_span if rows_span > 0 else float("nan")
    within: list[float] = []
    edge_pairs: list[float] = []
    diagonals: list[float] = []
    for row in rows:
        for i, first in enumerate(row.slots):
            for second in row.slots[i + 1:]:
                d = math.hypot(first.along - second.along, first.x - second.x)
                within.append(d)
                if first.role == "edge" and second.role == "edge":
                    edge_pairs.append(d)
                else:
                    diagonals.append(d)
    stagger = [
        row.along - slot.along
        for row in rows
        for slot in row.slots
        if slot.role == "middle"
    ]
    within.sort()
    stagger.sort()
    band = (plan.along_min / 2.0 - 1e-9, plan.along_max / 2.0 + 1e-9)
    slots_ys = sorted(slot.along for slot in slots)
    span = slots_ys[-1] - slots_ys[0] if len(slots_ys) > 1 else float("nan")
    return {
        "counts": counts,
        "has_middle": has_middle,
        "rows_span": rows_span,
        "mean_pitch": mean_pitch,
        "rows_per_m": rows_per_m,
        "within": within,
        "edge_pairs": edge_pairs,
        "diagonals": diagonals,
        "stagger": stagger,
        "inside": (
            sum(1 for gap in stagger if band[0] <= gap <= band[1]) / len(stagger)
            if stagger
            else 0.0
        ),
        "density": len(slots) / span if span > 0 else float("nan"),
        "span": span,
    }


def column_census(plan, placed, cfg) -> dict:
    """Per-column **size** histogram of the placed lattice [m].

    The middle column is a **class filter** by geometry, not a free column: its
    diagonal admits a maximum radius of 31-38 mm at the shipped pitch, so at the
    narrow end only the small classes can join and at the wide end most can.
    The audit's pool model draws diameters per class, but the class bands
    overlap (kiwi/tomato 5.0-6.8 cm, apple 6.2-7.0), so a diameter cannot name
    a class unambiguously; the report therefore bins the **diameters** and says
    what actually joined the middle, beside the geometric admission band.
    """
    del plan, cfg  # the caller names the columns; kept for a uniform signature
    edges = (0.040, 0.050, 0.058, 0.064)
    out: dict[int, dict] = {}
    for column, slots in sorted(_column_slots(placed).items()):
        dias = sorted(2.0 * float(slot.radius) for slot in slots)
        bins: Counter = Counter()
        for dia in dias:
            index = sum(1 for edge in edges if dia >= edge)
            bins[index] += 1
        out[column] = {
            "n": len(dias),
            "bins": bins,
            "min": dias[0] if dias else float("nan"),
            "median": dias[len(dias) // 2] if dias else float("nan"),
            "max": dias[-1] if dias else float("nan"),
        }
    return out


def _column_slots(placed):
    """{column index: [slots]} without importing a dict-of-lists default."""
    grouped: dict[int, list] = {}
    for slot in placed:
        grouped.setdefault(int(slot.column), []).append(slot)
    return grouped


def size_bin_label(index: int) -> str:
    """One fixed diameter bin's label (cm): `<4.0`, `4.0-5.0`, ... `>=6.4`."""
    edges = (4.0, 5.0, 5.8, 6.4)
    if index <= 0:
        return f"<{edges[0]:.1f}"
    if index >= len(edges):
        return f">={edges[-1]:.1f}"
    return f"{edges[index - 1]:.1f}-{edges[index]:.1f}"


def abreast_census(slots, tol: float = ABREAST_TOL) -> Counter:
    """Fruit per same-along cluster: the belt's visible "abreast" structure.

    A single-file zigzag puts every slot at its own along, so every cluster is a
    singleton. The row schedule's edge pair shares an along, so the histogram
    must carry 2-fruit clusters.
    """
    ordered = sorted(slots, key=lambda slot: slot.along)
    groups: list[list] = []
    for slot in ordered:
        if groups and abs(slot.along - groups[-1][-1].along) <= tol:
            groups[-1].append(slot)
        else:
            groups.append([slot])
    return Counter(len(group) for group in groups)


def histogram(counter: Counter) -> str:
    return " ".join(f"{key}x{counter[key]}" for key in sorted(counter))


# --------------------------------------------------------------------------- #
# 2. The integrated run: the real spawner on a fake belt.
# --------------------------------------------------------------------------- #
def integrated(
    cfg: SceneConfig,
    pool_items,
    seconds: float = 90.0,
    consume_s: float = 5.6,
    update_every_s: float = 0.0,
    prime_rows: int = 4,
    sample_every: int = 5,
):
    """Drive the real spawner on a fake belt and census what it **delivers**.

    The belt is a pure -Y translation at `cfg.belt_speed` plus one consumer every
    `consume_s` (the stand-in for an attempt's pick), and `spawner.update` is
    called at `update_every_s` - 0 is the per-tick feeder, 16 s is the shipped
    attempt-boundary cadence (one `update` per attempt), 3 s is in between.

    What is measured, all from the spawner's own state:

    * the **placements** (`spawner.respawn`, which is what actually puts a fruit
      on the belt) with class, grade, radius and position. `stats["released"]`
      counts *draws* (`release_next`), and a bed row draws one sample per column
      but usually places only its two edges, so draws run ~1.5x the delivered
      fruit; `stats["bed_placed"]` is the placement counter and this list must
      agree with it (checked);
    * **transits**: a body that was placed at the spawn point and later reached
      `despawn_y`. Without this the belt can look busy while every "release" is
      a teleport of the same bodies (the pre-B1 pool failure mode);
    * the **live-recycle** counters `bed_draws` / `bed_live_recycled` the
      spawner keeps (a live body drawn means the pool was exhausted);
    * the 1.1 m spawn window's candidate count per tick *and* at each consume
      tick (the moment a selector would read the belt);
    * every live pairwise distance and corridor margin (the safety properties);
    * the **body gaps** (consecutive live fruit along the belt: design
      0.055-0.065 m because of the staggered middle) and the **row gaps**
      (consecutive abreast edge-pair clusters: design 0.11-0.13 m). The Oracle's
      q6 read is a p90 row gap of 598 mm - the interlock oscillator, not the
      lattice.

    Positions are read once per live body per tick and cached; `position()`
    rebuilds a numpy array on every call, which dominated the old 90 s run.
    """
    spawner = make_spawner(cfg, pool_items)
    placed: list[dict] = []
    despawned: list[int] = []
    original = spawner.respawn
    clock = [-1]  # tick of the placement being recorded (-1 = the pre-load)

    def hook(sample, along=None, x_jitter=0.10, x=None):
        original(sample, along=along, x_jitter=x_jitter, x=x)
        pos = spawner.position(sample)
        placed.append(
            {
                "index": int(sample.index),
                "category": sample.category,
                "grade": sample.grade,
                "radius": 0.5 * float(sample.diameter),
                "y": float(pos[1]),
                "x": float(pos[0]),
                "tick": clock[0],
            }
        )

    spawner.respawn = hook
    spawner.prime(count=prime_rows)
    step = 1.0 / 120.0
    consume_ticks = max(1, int(round(consume_s / step)))
    update_ticks = max(1, int(round(update_every_s / step))) if update_every_s > 0 else 1
    min_sep = math.inf
    window_counts: list[int] = []
    window_at_pick: list[int] = []
    stock_counts: list[int] = []
    stock_at_pick: list[int] = []
    live_peak = 0
    live_min_margin = math.inf
    max_abreast = 0
    abreast_members = 0
    abreast_total = 0
    body_gaps: list[float] = []
    row_gaps: list[float] = []
    for tick in range(int(round(seconds / step))):
        clock[0] = tick
        if tick % update_ticks == 0:
            spawner.update(tick * step)
        # One position read per live body, used by every census below.
        live: list[tuple[int, float, float, float]] = []
        live_by_index = {}
        for sample in list(spawner.active):
            if sample.parked or sample.held:
                continue
            pos = spawner.position(sample).copy()
            pos[1] += cfg.belt_speed * step
            spawner._rigids[sample.index].pos = pos
            if pos[1] < cfg.despawn_y:
                spawner.park(sample)
                spawner.active.remove(sample)
                despawned.append(int(sample.index))
                continue
            if abs(float(pos[0]) - cfg.belt_center[0]) < 0.30:
                live.append(
                    (
                        int(sample.index),
                        float(pos[1]),
                        float(pos[0]),
                        0.5 * float(sample.diameter),
                    )
                )
                live_by_index[int(sample.index)] = sample
        live_peak = max(live_peak, len(live))
        for i, (_, ya, xa, ra) in enumerate(live):
            for _, yb, xb, rb in live[i + 1:]:
                d = math.hypot(ya - yb, xa - xb)
                min_sep = min(min_sep, d)
                live_min_margin = min(live_min_margin, d - OPEN_JAW_HALF_SPAN - max(ra, rb))
        ys_desc = sorted((y for _, y, _, _ in live), reverse=True)
        # The visible structure: consecutive live fruit share a row only when
        # they are abreast (an edge pair), otherwise they are the middle's
        # half-pitch neighbour.
        sizes: list[int] = []
        row_ys: list[float] = []
        run: list[float] = []
        for y in ys_desc:
            if run and abs(y - run[-1]) <= ABREAST_TOL:
                run.append(y)
            else:
                if run:
                    sizes.append(len(run))
                    if len(run) >= 2:
                        row_ys.append(sum(run) / len(run))
                run = [y]
        if run:
            sizes.append(len(run))
            if len(run) >= 2:
                row_ys.append(sum(run) / len(run))
        max_abreast = max(max_abreast, max(sizes, default=0))
        abreast_members += sum(size for size in sizes if size >= 2)
        abreast_total += len(ys_desc)
        if tick % sample_every == 0:
            # Distinct along positions only: the edge pair of a row shares an
            # along (gap 0), which would swamp the distribution's p10/p50.
            body_gaps.extend(
                ys_desc[i] - ys_desc[i + 1]
                for i in range(len(ys_desc) - 1)
                if ys_desc[i] - ys_desc[i + 1] > ABREAST_TOL
            )
            row_gaps.extend(
                row_ys[i] - row_ys[i + 1] for i in range(len(row_ys) - 1)
            )
        window = sum(1 for y in ys_desc if cfg.spawn_y - WINDOW <= y <= cfg.spawn_y)
        window_counts.append(window)
        stock = sum(1 for y in ys_desc if y >= cfg.pick_y + CATCH_FLOOR)
        stock_counts.append(stock)
        if tick > 0 and tick % consume_ticks == 0 and live:
            window_at_pick.append(window)
            stock_at_pick.append(stock)
            picked_index = min(live, key=lambda item: abs(item[1] - cfg.pick_y))[0]
            picked = live_by_index[picked_index]
            spawner.park(picked)
            if picked in spawner.active:
                spawner.active.remove(picked)
    return {
        "spawner": spawner,
        "placed": placed,
        "despawned": despawned,
        "min_sep": min_sep,
        "margin": live_min_margin,
        "window": window_counts,
        "window_at_pick": window_at_pick,
        "stock": stock_counts,
        "stock_at_pick": stock_at_pick,
        "max_abreast": max_abreast,
        "abreast_share": abreast_members / abreast_total if abreast_total else 0.0,
        "live_peak": live_peak,
        "body_gaps": body_gaps,
        "row_gaps": row_gaps,
        "seconds": seconds,
    }


def gap_stats(gaps: list[float]) -> dict:
    """Quantiles of a gap sample [m]; empty-safe so a starved cell still prints."""
    if not gaps:
        return {"n": 0}
    ordered = sorted(gaps)
    return {
        "n": len(ordered),
        "p10": ordered[int(0.10 * (len(ordered) - 1))],
        "p50": ordered[len(ordered) // 2],
        "p90": ordered[int(0.90 * (len(ordered) - 1))],
        "max": ordered[-1],
    }


def fmt_gaps(stats: dict) -> str:
    if not stats["n"]:
        return "none"
    return (
        f"n={stats['n']} p10={stats['p10']*1000:.0f} "
        f"p50={stats['p50']*1000:.0f} p90={stats['p90']*1000:.0f} "
        f"max={stats['max']*1000:.0f} mm"
    )


# --------------------------------------------------------------------------- #
# 3. Bedrock: the legacy slot streams, bed off.
# --------------------------------------------------------------------------- #
def legacy_lines(env: dict, seconds: float = 120.0):
    for key in list(os.environ):
        if key.startswith("FRUIT_SUPPLY_") or key.startswith("FRUIT_BIARM_"):
            del os.environ[key]
    os.environ["FRUIT_BELT_SPEED"] = "0.12"
    os.environ.update(env)
    cfg = SceneConfig()
    categories = list(cfg.fruit_dimensions.keys())
    spawner = make_spawner(
        cfg,
        [(categories[i % len(categories)], 0.05, "A") for i in range(16)],
    )
    # `make_spawner` uses 0.05 m diameters; the legacy stream's *positions* do
    # not depend on the diameter (the scatter draws x and gaps only), so this is
    # the same harness the pre-change digests were recorded with.
    lines = []
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
    for tick in range(int(round(seconds / step))):
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
    return lines


def end_of_line_equivalence(cfg: SceneConfig, spawner) -> list[tuple[str, object, object]]:
    """`_end_of_line` vs the shipped predicate, transcribed (P32 R2).

    The R2 fix split `update`'s despawn block into `_end_of_line` +
    `_recycle_end` so the bed's sweep reuses it. That refactor must not change
    what a *shipped* line counts, and the shipped acceptance does not exercise
    the branch (its belt traffic is all tray `discharged`), so the equivalence is
    pinned here instead: the reference below is the **pre-split code**
    transcribed line for line (`fell_off` first, the discharge suppression, then
    `along < despawn_y`, `fell_off` winning a tie), and every case must agree.
    The cases cover the belt, the despawn line from both above and below it, the
    chute's z band (0.87-0.89, where the suppression actually flips the answer),
    and a held body - `held` suppresses the discharge test but never the floor
    test, as shipped.
    """
    from fruit_sorting.fruits import FruitSample

    belt = float(cfg.belt_center[2])
    on_despawn = float(cfg.despawn_y)
    cases = [
        ("main belt mid", (0.30, 0.20, belt + 0.05), False),
        ("main belt, past despawn", (0.30, on_despawn - 0.02, belt + 0.05), False),
        ("floor mid-belt", (0.30, 0.20, 0.03), False),
        ("floor past despawn", (0.30, on_despawn - 0.02, 0.03), False),
        ("held, floor level", (0.30, 0.20, 0.03), True),
        ("chute band, z=0.88", (1.20, 0.50, 0.88), False),
        ("chute band, held", (1.20, 0.50, 0.88), True),
        ("chute band, past despawn", (1.20, on_despawn - 0.02, 0.88), False),
    ]
    sample = FruitSample(
        index=0,
        prim_path="/World/Fruits/Probe_00",
        category="apple",
        diameter=0.06,
        mass=0.1,
        friction=0.7,
        grade="A",
        ripeness=0.8,
        defective=False,
        parked=False,
    )
    rows = []
    for label, pos, held in cases:
        sample.held = held
        # The pre-split predicate, transcribed from `update` (do not refactor it
        # to call the new helper: this is the independent second opinion).
        fell_off = float(pos[2]) < belt - 0.25
        if fell_off and not held and cfg.on_output_discharge(pos):
            fell_off = False
        if float(pos[1]) < on_despawn or fell_off:
            shipped = "fell_off" if fell_off else "reached_end"
        else:
            shipped = None
        rows.append((label, spawner._end_of_line(sample, pos, float(pos[1])), shipped))
    return rows


def despawn_sweep_probe(
    cfg: SceneConfig, pool_items, seconds: float = 14.0, sweep_s: float = 0.25
) -> dict:
    """The belt-end despawn gap (P32 Gate-A residual R2): reproduction + fix.

    `integrated` despawns inside its own tick loop, so it **cannot** produce the
    class the simulator measured. This probe reproduces the driver's cadence
    instead: one `spawner.update` (the attempt-boundary pump) and then
    `seconds` of belt travel with **no** pump - what `_step_sim` does inside an
    attempt. A body that crosses the belt's physical end is put on the floor,
    because that is what the simulator's physics does (nothing carries a body
    past -0.80 m); the next pump then charges it `fell_off`.

    Three cells, all on the same primed belt:

    * **control** (`sweep=False`, the pre-fix behaviour): `fell_off > 0` with
      `reached_end == 0` - the simulator's read on runs 77/78/79;
    * **fix** (`sweep=True`, `scan_despawn` on every control tick): every one of
      those bodies is recycled at `despawn_y` as `reached_end`, `fell_off == 0`
      and **no body ever reaches the floor**;
    * **residual**: a released failure payload between the belts
      (`x=0.735, y=-0.195, z=0.047`, the measured row) is still `fell_off` in
      both cells - the fix must not swallow the genuine floor class.

    Plus two guards: a mid-belt body is never touched by a sweep, and a bed-off
    spawner's `scan_despawn` is inert (its `stats` dict does not even gain a
    key).
    """
    step = 1.0 / 120.0
    belt_end = float(cfg.belt_center[1]) - float(cfg.belt_size[1]) / 2.0
    floor_z = 0.03
    out: dict = {}

    # Guard 1: the sweep touches nothing that is still on the belt.
    guard = make_spawner(cfg, pool_items)
    guard.prime(count=4)
    guard_live = sorted(
        int(s.index) for s in guard.active if not s.parked and not s.held
    )
    for _ in range(int(round(2 * sweep_s / step))):
        guard.scan_despawn(1)
    guard_after = sorted(
        int(s.index) for s in guard.active if not s.parked and not s.held
    )
    out["guard_live"] = guard_live
    out["guard_after"] = guard_after
    out["guard_reached"] = int(guard.stats.get("reached_end", 0))
    out["guard_sweeps"] = int(guard.stats.get("bed_sweeps", 0))

    # Guard 1b: a body resting in a discharge tray is `update`'s business (its
    # dwell needs `update`'s own `dt`); the sweep must leave it alone. The tray
    # floor (z=0.92) is *above* the fell-off threshold, so only the tray test
    # keeps it - which is exactly the guard being pinned.
    tray = make_spawner(cfg, pool_items)
    tray_body = tray.samples[0]
    tray_body.parked = False
    tray._rigids[tray_body.index].pos = np.array([1.65, 0.50, 0.95])
    if tray_body not in tray.active:
        tray.active.append(tray_body)
    tray_before = dict(tray.stats)
    for _ in range(60):
        tray.scan_despawn(1)
    out["tray_active"] = any(
        s is tray_body for s in tray.active if not s.parked
    )
    # The sweep counters (`bed_sweeps`/`bed_swept`) are its own bookkeeping; every
    # *accounting* key must be untouched, and nothing may be reaped.
    out["tray_stats_unchanged"] = all(
        tray.stats.get(key) == value for key, value in tray_before.items()
    ) and not int(tray.stats.get("bed_swept", 0))

    for label, sweep in (("control", False), ("fix", True)):
        spawner = make_spawner(cfg, pool_items)
        spawner.prime(count=4)
        # The residual: one body on the floor between the belts, exactly where
        # run 78's `[bed-fall] peach idx=6 x=0.735 y=-0.195 z=0.047` sat.
        # Attached *after* the pre-load so the feeder cannot draw it.
        residual = spawner.samples[-1]
        residual.parked = False
        spawner._rigids[residual.index].pos = np.array([0.735, -0.195, floor_z])
        if residual not in spawner.active:
            spawner.active.append(residual)
        residual_index = int(residual.index)
        kinds: dict[int, str] = {}
        original_recycle = spawner._recycle_end

        def recorder(sample, kind, pos, along, _original=original_recycle, _kinds=kinds):
            _kinds[int(sample.index)] = kind
            _original(sample, kind, pos, along)

        spawner._recycle_end = recorder
        on_floor: set[int] = set()
        min_along = math.inf
        for _tick in range(int(round(seconds / step))):
            for sample in list(spawner.active):
                if sample.parked or sample.held:
                    continue
                if int(sample.index) == residual_index:
                    continue  # on the floor, not on the belt
                rigid = spawner._rigids[sample.index]
                pos = np.asarray(rigid.pos, dtype=float).copy()
                pos[1] += float(cfg.belt_speed) * step
                if pos[1] < belt_end:
                    pos[2] = floor_z
                    on_floor.add(int(sample.index))
                rigid.pos = pos
                min_along = min(min_along, float(pos[1]))
            if sweep:
                spawner.scan_despawn(1)
        # The next attempt-boundary pump: the only scan on the pre-fix line.
        spawner.update(seconds)
        stats = spawner.stats
        out[label] = {
            "fell_off": int(stats.get("fell_off", 0)),
            "reached_end": int(stats.get("reached_end", 0)),
            "residual_kind": kinds.get(residual_index),
            "belt_end_kinds": sorted(
                kind for index, kind in kinds.items() if index != residual_index
            ),
            "on_floor": sorted(on_floor),
            "min_along": min_along,
            "sweeps": int(stats.get("bed_sweeps", 0)),
            "swept": int(stats.get("bed_swept", 0)),
            "live": sum(1 for s in spawner.active if not s.parked and not s.held),
        }

    # Guard 2: with the bed off, `scan_despawn` is inert.
    saved = os.environ.pop("FRUIT_SUPPLY_BED", None)
    try:
        legacy = make_spawner(cfg, pool_items)
        legacy.prime(count=4)
        legacy_before = dict(legacy.stats)
        legacy_live = sorted(
            int(s.index) for s in legacy.active if not s.parked and not s.held
        )
        for _ in range(60):
            legacy.scan_despawn(1)
        out["legacy_stats_unchanged"] = dict(legacy.stats) == legacy_before
        out["legacy_live_unchanged"] = (
            sorted(int(s.index) for s in legacy.active if not s.parked and not s.held)
            == legacy_live
        )
        out["legacy_sweep_keys"] = sorted(
            key for key in legacy.stats if key.startswith("bed_")
        )
    finally:
        if saved is not None:
            os.environ["FRUIT_SUPPLY_BED"] = saved
    out["belt_end"] = belt_end
    out["despawn_y"] = float(cfg.despawn_y)
    out["sweep_s"] = sweep_s
    return out


LEGACY_SCENARIOS = {

    "scatter": {"FRUIT_SUPPLY_SCATTER": "1", "FRUIT_SUPPLY_POOL": "16"},
    "wave": {
        "FRUIT_SUPPLY_SCATTER": "1",
        "FRUIT_SUPPLY_POOL": "16",
        "FRUIT_BIARM_TWOLINE": "1",
        "FRUIT_SUPPLY_WAVE": "1",
    },
    "patch": {"FRUIT_SUPPLY_SCATTER": "1", "FRUIT_SUPPLY_POOL": "16", "FRUIT_SUPPLY_PATCH": "1"},
    "fixed": {"FRUIT_SUPPLY_SCATTER": "0", "FRUIT_SUPPLY_POOL": "16"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stretch",
        action="store_true",
        help="retired: the old per-slot gap-stretch variant (the row schedule replaced it)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help=(
            "short battery for the selfcheck leg: 45 s per cell and 2 of the 3 "
            "update cadences (per-tick + attempt boundary); the full run is the "
            "record (logs/p32/bed_audit.txt)"
        ),
    )
    args = parser.parse_args()

    checks = 0

    def check(condition: bool, text: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise AssertionError(text)

    def say(msg: str) -> None:
        print(f"[211] {msg}", flush=True)

    say("bed audit (P32 phase 1, offline): rows, corridor, density, bedrock")
    if args.stretch:
        say(
            "--stretch is retired: the measured gap-stretch belonged to the "
            "per-slot lattice, and the row schedule (pair + conditional "
            "staggered middle) is what ships; nothing below is a stretch run"
        )

    # --- the resolved plan + the env precedence --------------------------- #
    say("env probes (the [fruit] [supply] warnings below are the probes' own)")
    clear_supply_env()
    cfg = SceneConfig()
    default = SupplyPlan.from_env(cfg)
    check(not default.bed, "the bed must default OFF (FRUIT_SUPPLY_BED unset)")
    check(default.schedule == "scatter", f"the default schedule is scatter ({default.schedule})")

    os.environ["FRUIT_SUPPLY_BED"] = "1"
    bed_plan = SupplyPlan.from_env(cfg)
    check(bed_plan.bed, "FRUIT_SUPPLY_BED=1 enables the bed")
    check(bed_plan.schedule == "bed", f"the bed names itself ({bed_plan.schedule})")
    plan = bed_plan.bed_plan
    assert plan is not None
    check(
        tuple(round(x, 6) for x in plan.columns) == EXPECT_COLUMNS,
        f"columns are the measured {EXPECT_COLUMNS} ({plan.columns})",
    )
    check(
        abs(plan.along_min - EXPECT_ALONG[0]) < 1e-9
        and abs(plan.along_max - EXPECT_ALONG[1]) < 1e-9,
        f"row pitch band is {EXPECT_ALONG} ({plan.along_min}-{plan.along_max})",
    )
    check(bed_plan.pool == POOL, f"bed pool default {POOL} ({bed_plan.pool})")
    os.environ["FRUIT_SUPPLY_POOL"] = "9"
    check(
        SupplyPlan.from_env(cfg).pool == 9,
        "an explicit FRUIT_SUPPLY_POOL still wins over FRUIT_SUPPLY_BED_POOL",
    )
    del os.environ["FRUIT_SUPPLY_POOL"]
    os.environ["FRUIT_SUPPLY_BED_POOL"] = "30"
    check(SupplyPlan.from_env(cfg).pool == 30, "FRUIT_SUPPLY_BED_POOL sets the bed pool")
    del os.environ["FRUIT_SUPPLY_BED_POOL"]
    os.environ["FRUIT_SUPPLY_SCATTER"] = "0"
    check(
        not SupplyPlan.from_env(cfg).bed,
        "the bed requires the scattered feeder (SCATTER=0 ignores it)",
    )
    os.environ["FRUIT_SUPPLY_SCATTER"] = "1"
    os.environ["FRUIT_SUPPLY_PATCH"] = "1"
    precedence = SupplyPlan.from_env(cfg)
    check(
        precedence.bed and not precedence.patch,
        "precedence: bed wins over patch (patch resolves off)",
    )
    del os.environ["FRUIT_SUPPLY_PATCH"]
    os.environ["FRUIT_SUPPLY_WAVE"] = "1"
    os.environ["FRUIT_BIARM_TWOLINE"] = "1"
    precedence = SupplyPlan.from_env(cfg)
    check(
        precedence.schedule == "bed",
        "precedence: bed wins over wave (the two-line wave default)",
    )
    del os.environ["FRUIT_SUPPLY_WAVE"]
    os.environ.pop("FRUIT_BIARM_TWOLINE", None)
    os.environ["FRUIT_SUPPLY_TARGET"] = "3"
    check(
        SupplyPlan.from_env(cfg).target == 0,
        "the approach-segment top-up is refused on the bed (it packs its own rows)",
    )
    del os.environ["FRUIT_SUPPLY_TARGET"]
    say(
        f"plan: columns={','.join(f'{x:.2f}' for x in plan.columns)} "
        f"rows=2 abreast ({plan.columns[-1] - plan.columns[0]:.2f} m) + mid, "
        f"pitch={plan.along_min:.3f}-{plan.along_max:.3f} m "
        f"(mid staggered {plan.along_min/2*1000:.0f}-{plan.along_max/2*1000:.0f} mm) "
        f"margin={plan.margin:.3f} m shift<={plan.shift_max:.2f} m "
        f"pool={bed_plan.pool} corridor=+/-{OPEN_JAW_HALF_SPAN:.3f} m "
        f"floor={RELEASE_CLEAR:.2f} m"
    )

    # --- the banner the spawner prints ------------------------------------ #
    # Gate-1 finding: the bed reused the scatter line's `gaps=0.10-0.35 m`
    # banner, which is the wrong schedule on a row lattice. Pin the replacement:
    # the bed names its **rows** and its pitch, and never the scatter gaps.
    # `create_pool` prints the lines; `_create_fruit` is stubbed because this
    # audit has no USD (the banner is pure string formatting over the plan).
    banner_spawner = make_spawner(cfg, synthetic_pool(cfg, POOL, 7, bed_plan.grades))
    banner_spawner._create_fruit = lambda *a, **k: None
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        banner_spawner.create_pool()
    banner_lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    for line in banner_lines:
        say(f"  banner | {line}")
    banner_text = "\n".join(banner_lines)
    check(
        "gaps=0.10-0.35 m" not in banner_text,
        "the bed banner does not claim the scatter line's gaps=0.10-0.35 m",
    )
    check(
        "rows=2 abreast" in banner_text
        and f"pitch={plan.along_min:.3f}-{plan.along_max:.3f} m" in banner_text,
        "the bed banner prints the row geometry (rows=..., pitch=...)",
    )
    check(
        "conditional mid" in banner_text and "pair rule" in banner_text,
        "the bed banner names the middle rule (conditional, pair-rule gated)",
    )

    # --- grade mix -------------------------------------------------------- #
    shipped = _mix_allocate(bed_plan.grades, bed_plan.pool)
    say(
        "grade mix (pool "
        f"{bed_plan.pool}, schedule={bed_plan.schedule}): "
        f"A={shipped.count('A')} B={shipped.count('B')} C={shipped.count('C')} "
        "(" + ",".join(f"{k}:{w:g}" for k, w in bed_plan.grades) + ")"
    )
    os.environ["FRUIT_BIARM_TWOLINE"] = "1"
    balanced = SupplyPlan.from_env(cfg)
    balanced_mix = _mix_allocate(balanced.grades, balanced.pool)
    say(
        "grade mix (two-line balanced): "
        f"A={balanced_mix.count('A')} B={balanced_mix.count('B')} "
        f"C={balanced_mix.count('C')} "
        f"(pool {balanced.pool}, "
        + ",".join(f"{k}:{w:g}" for k, w in balanced.grades) + ")"
    )
    os.environ.pop("FRUIT_BIARM_TWOLINE", None)
    check(
        dict(balanced.grades) == {"A": 0.375, "B": 0.375, "C": 0.25},
        "the bed honours the two-line balanced mix",
    )

    # --- the pure row schedule -------------------------------------------- #
    pool_items = synthetic_pool(cfg, POOL, 20261022, bed_plan.grades)
    radii = [diameter / 2.0 for _, diameter, _ in pool_items]
    raw_rows, raw_slots, schedule, pure_stats = pure_rows(
        bed_plan.bed_plan, radii, SEED, ROWS, shift_room=False
    )
    rows, placed = belt_frame(raw_rows)
    census = pair_census(bed_plan.bed_plan, placed)
    structure = row_census(bed_plan.bed_plan, rows, placed)
    clusters = abreast_census(placed)
    ys = sorted(slot.along for slot in placed)
    window = [slot for slot in placed if ys[-1] - WINDOW <= slot.along <= ys[-1]]
    window_x = [
        sum(1 for slot in window if slot.column == column)
        for column in range(len(bed_plan.bed_plan.columns))
    ]
    say(
        f"pure schedule (bed.py, seed={SEED}, {ROWS} due rows, pool model "
        f"{POOL} fruit {min(2*r for r in radii)*100:.1f}-{max(2*r for r in radii)*100:.1f} cm, "
        "on-time: no shift room):"
    )
    say(
        f"  rows: due {pure_stats['due']}, placed {pure_stats['rows']}, "
        f"skipped {pure_stats['refused']}; fruit/row "
        f"{histogram(structure['counts'])} "
        f"(full rows with the middle {structure['has_middle']}); "
        f"middle refused by the pair rule {schedule.middle_refused}"
    )
    say(
        "  abreast clusters (same along <= "
        f"{ABREAST_TOL*1000:.0f} mm): {histogram(clusters)} "
        "(a single-file zigzag reads 1x all)"
    )
    say(
        "  columns: "
        + "  ".join(
            f"x={x:.2f} {n} slots"
            for x, n in zip(bed_plan.bed_plan.columns, schedule.column_hits)
        )
        + f"  (rows shifted {schedule.shifted})"
    )
    columns = column_census(bed_plan.bed_plan, placed, cfg)
    say(
        "  per-column size histogram (the middle is a class filter by "
        "geometry, not a free column):"
    )
    for column, info in columns.items():
        say(
            f"    x={bed_plan.bed_plan.columns[column]:.2f} n={info['n']:3d} "
            f"dia {info['min']*100:.1f}-{info['max']*100:.1f} cm "
            f"(median {info['median']*100:.1f}) "
            + " ".join(
                f"{size_bin_label(index)}:{info['bins'][index]}"
                for index in sorted(info["bins"])
            )
        )
    edge_cols = list(bed_plan.bed_plan.edge_columns)
    middle_cols = list(bed_plan.bed_plan.middle_columns)
    if middle_cols and all(columns[c]["n"] for c in middle_cols):
        edge_median = sum(columns[c]["median"] for c in edge_cols) / len(edge_cols)
        middle_median = sum(columns[c]["median"] for c in middle_cols) / len(middle_cols)
        admitted_lo = 2.0 * bed_plan.bed_plan.admitted_radius(
            bed_plan.bed_plan.diagonal(bed_plan.bed_plan.along_min)
        )
        admitted_hi = 2.0 * bed_plan.bed_plan.admitted_radius(
            bed_plan.bed_plan.diagonal(bed_plan.bed_plan.along_max)
        )
        say(
            "  class filter read: middle median diameter "
            f"{middle_median*100:.1f} cm vs the edge pair's "
            f"{edge_median*100:.1f} cm; the diagonal admits "
            f"{admitted_lo*100:.1f}-{admitted_hi*100:.1f} cm dia, so at the "
            "narrow pitch only the small classes join and at the wide pitch "
            "most do (which is why the delivered middle share is a pitch "
            "number)"
        )
    say(
        f"  pitch: {structure['rows_per_m']:.1f} rows/m, mean "
        f"{structure['mean_pitch']*1000:.1f} mm over {structure['rows_span']:.2f} m; "
        f"density {structure['density']:.1f} fruit/m over "
        f"{structure['span']:.2f} m ({len(placed)} fruit)"
    )
    within_parts = []
    if structure["within"]:
        within_parts.append(
            f"{len(structure['within'])} pairs, min "
            f"{min(structure['within'])*1000:.1f} / median "
            f"{structure['within'][len(structure['within'])//2]*1000:.1f} / max "
            f"{max(structure['within'])*1000:.1f} mm"
        )
    if structure["edge_pairs"]:
        within_parts.append(
            f"edge pair {min(structure['edge_pairs'])*1000:.1f}-"
            f"{max(structure['edge_pairs'])*1000:.1f} mm"
        )
    if structure["diagonals"]:
        within_parts.append(
            f"middle diagonal {min(structure['diagonals'])*1000:.1f}-"
            f"{max(structure['diagonals'])*1000:.1f} mm"
        )
    say("  within-row separations: " + ("; ".join(within_parts) or "none"))
    say(
        "  stagger: "
        + (
            f"{len(structure['stagger'])} middles, median "
            f"{structure['stagger'][len(structure['stagger'])//2]*1000:.0f} mm, "
            f"p90 {structure['stagger'][int(0.9*(len(structure['stagger'])-1))]*1000:.0f} mm, "
            f"{structure['inside']*100:.0f} % inside the drawn half-pitch "
            f"({bed_plan.bed_plan.along_min/2*1000:.0f}-"
            f"{bed_plan.bed_plan.along_max/2*1000:.0f} mm)"
            if structure["stagger"]
            else "none (no row's middle cleared: the mixed pool's edges are "
            "6-7 cm; see the small-class probe below)"
        )
    )
    say(
        "  pairwise (all pairs): "
        f"{census['pairs']} pairs, min d={census['min_d']:.4f} m "
        f"(p10 {census['p10_d']:.4f}, median {census['median_d']:.4f}), "
        f"min d-0.066-r_other={census['min_literal']:.4f} m vs the enforced "
        f"{plan.margin:.3f} m margin, min slack {census['min_slack']:+.4f} m, "
        f"violations {census['violations']}"
    )
    say(
        "  layout (newest 4 rows, belt frame): "
        + " | ".join(
            ",".join(f"y={slot.along:.3f} x={slot.x:.2f}{slot.role[0]}" for slot in row.slots)
            for row in rows[-4:]
        )
    )
    say(
        f"  window: {WINDOW:.2f} m spawn window [{ys[-1]-WINDOW:+.2f}, {ys[-1]:+.2f}]: "
        f"{len(window)} fruit = {len(window)/WINDOW:.1f}/m "
        "(per column " + ", ".join(f"{n}" for n in window_x) + ")"
    )
    say(
        "  corridor geometry: a 7.0 cm fruit needs "
        f"{bed_plan.bed_plan.along_need(0.035)*1000:.0f} mm in its own column "
        f"(row pitch {bed_plan.bed_plan.along_min*1000:.0f}-"
        f"{bed_plan.bed_plan.along_max*1000:.0f} mm), and a 4.5 cm one "
        f"{bed_plan.bed_plan.along_need(0.0225)*1000:.0f} mm; the middle's diagonal "
        f"{bed_plan.bed_plan.diagonal(bed_plan.bed_plan.along_min)*1000:.1f}-"
        f"{bed_plan.bed_plan.diagonal(bed_plan.bed_plan.along_max)*1000:.1f} mm "
        f"admits a max radius of "
        f"{bed_plan.bed_plan.admitted_radius(bed_plan.bed_plan.diagonal(bed_plan.bed_plan.along_min))*1000:.1f}-"
        f"{bed_plan.bed_plan.admitted_radius(bed_plan.bed_plan.diagonal(bed_plan.bed_plan.along_max))*1000:.1f} mm "
        f"({2*bed_plan.bed_plan.admitted_radius(bed_plan.bed_plan.diagonal(bed_plan.bed_plan.along_min))*100:.1f}-"
        f"{2*bed_plan.bed_plan.admitted_radius(bed_plan.bed_plan.diagonal(bed_plan.bed_plan.along_max))*100:.1f} cm diameter)"
    )
    check(census["violations"] == 0, f"no violating pair ({census['violations']})")
    check(
        census["min_d"] >= RELEASE_CLEAR - 1e-9,
        f"the 0.08 m floor holds ({census['min_d']:.4f})",
    )
    check(census["min_slack"] >= -1e-9, f"the corridor rule holds ({census['min_slack']:+.4f})")
    check(
        pure_stats["rows"] + pure_stats["refused"] == pure_stats["due"],
        "every due row is placed or skipped",
    )
    check(
        bool(rows) and min(row.fruit_count for row in rows) >= 2,
        "every placed row carries the abreast edge pair "
        f"({min((row.fruit_count for row in rows), default=0)})",
    )
    check(
        max(clusters, default=0) >= 2,
        f"the delivered lattice is abreast, not a single-file line ({histogram(clusters)})",
    )
    check(
        min(x for x in bed_plan.bed_plan.columns) - 1e-9
        <= min(slot.x for slot in placed)
        and max(slot.x for slot in placed) <= max(bed_plan.bed_plan.columns) + 1e-9,
        "every slot is inside the measured column band",
    )
    if structure["stagger"]:
        check(
            structure["inside"] == 1.0,
            "every middle sits inside the drawn half-pitch stagger band "
            f"({structure['inside']*100:.0f} %)",
        )
        check(
            min(structure["diagonals"]) >= RELEASE_CLEAR - 1e-9,
            "every middle clears the 0.08 m plane floor "
            f"({min(structure['diagonals']):.4f})",
        )
    # The bounded upstream shift (the "wait a moment" lever) is a safety net at
    # the shipped pitch: 0.11 m already clears the 0.107 m a 7 cm fruit needs in
    # its own column, and the middle's neighbours are its own row's and the
    # previous row's edges (both at half a pitch), so the delivered lattice has
    # no conflicting pair for the shift to repair. Pin the mechanism directly.
    probe = BedSchedule(bed_plan.bed_plan, seed=0)
    probe.next_gap()
    blocker = [(-0.05, 0.28, 0.030)]  # a 6 cm middle 5 cm downstream of the row
    no_room = probe.place_row(0.0, [0.035, 0.035], blocker, along_max=0.0)
    with_room = probe.place_row(0.0, [0.035, 0.035], blocker, along_max=0.05)
    check(no_room is None, "a blocked pair is refused when the row has no room")
    check(
        with_room is not None and with_room.shift > 0.0,
        "the same pair is placed upstream when the shift bound has room "
        f"({None if with_room is None else with_room.shift})",
    )
    say(
        "  shift probe: a 7 cm pair 5 cm downstream of a 6 cm middle -> "
        f"refused with no room, placed at +{with_room.shift*1000:.0f} mm with the "
        f"{bed_plan.bed_plan.shift_max:.2f} m bound (the delivered lattice needs "
        "none: 0 rows shifted)"
    )
    check(
        min(ys) >= ys[-1] - ROWS * bed_plan.bed_plan.along_max - 1e-9
        and max(ys) <= 0.68 + 1e-9,
        "the rows start at the spawn point and run downstream",
    )

    # The skip rate depends on the pool's arrival order (which fruit lands next
    # to which). The real pool is a shuffle, so the numbers above are one sample:
    # report the band over eight permutations rather than a single figure.
    band = []
    for order_seed in range(1, 9):
        order = synthetic_pool(cfg, POOL, order_seed, bed_plan.grades)
        order_radii = [diameter / 2.0 for _, diameter, _ in order]
        run_rows, _, _, run_stats = pure_rows(
            bed_plan.bed_plan, order_radii, SEED, ROWS
        )
        if not run_rows:
            continue
        run_slots = [slot for row in run_rows for slot in row.slots]
        run_structure = row_census(bed_plan.bed_plan, run_rows, run_slots)
        band.append(
            (
                run_stats["refused"] / run_stats["due"],
                run_structure["density"],
            )
        )
    skips = [item[0] for item in band]
    dens = [item[1] for item in band]
    say(
        f"  pool-order band (8 permutations): skipped {min(skips)*100:.0f}-"
        f"{max(skips)*100:.0f} % of rows, density {min(dens):.1f}-{max(dens):.1f} fruit/m"
    )

    # The shift budget is the pump's backlog room (a late row has space upstream
    # of its virtual along). At the shipped pitch the lattice is clear by
    # construction, so the budget is a safety net - the direct probe above pins
    # it - and this run reports whether any arrival order needs it.
    room_rows, room_slots, room_schedule, room_stats = pure_rows(
        bed_plan.bed_plan, radii, SEED, ROWS, shift_room=True
    )
    if room_slots:
        room_structure = row_census(bed_plan.bed_plan, room_rows, room_slots)
        say(
            f"  with the shift budget ({bed_plan.bed_plan.shift_max:.2f} m, the "
            f"pump's backlog room): rows placed {room_stats['rows']}, skipped "
            f"{room_stats['refused']}, {room_schedule.shifted} rows shifted, "
            f"density {room_structure['density']:.1f} fruit/m "
            f"(full rows {room_structure['has_middle']})"
        )

    # The middle is designed for the small classes: with the shipped mixed pool
    # its four diagonal neighbours are usually 6-7 cm, which the pair rule
    # refuses. Pin the designed case: an all-small pool (strawberry/lychee, the
    # classes the half-pitch diagonal admits) must produce full rows.
    small_rng = random.Random(20261023)
    small_names = ("strawberry", "lychee")
    small_radii = []
    for i in range(POOL):
        lo, hi = cfg.fruit_dimensions[small_names[i % len(small_names)]]
        small_radii.append(small_rng.uniform(lo, hi) / 2.0)
    small_rows, small_slots, small_schedule, small_stats = pure_rows(
        bed_plan.bed_plan, small_radii, SEED, 60, shift_room=False
    )
    small_structure = row_census(bed_plan.bed_plan, small_rows, small_slots)
    say(
        "  small-class probe (strawberry/lychee pool, the middle's designed "
        f"classes, 60 rows): fruit/row {histogram(small_structure['counts'])}, "
        f"full rows {small_structure['has_middle']}, "
        f"stagger median "
        f"{small_structure['stagger'][len(small_structure['stagger'])//2]*1000:.0f} mm "
        f"({small_structure['inside']*100:.0f} % inside the band), "
        f"diagonal {min(small_structure['diagonals'])*1000:.1f}-"
        f"{max(small_structure['diagonals'])*1000:.1f} mm, "
        f"density {small_structure['density']:.1f} fruit/m "
        f"(skipped {small_stats['refused']})"
    )
    check(
        small_structure["has_middle"] > 0,
        "the middle column is placed for the small classes",
    )
    check(
        small_structure["inside"] == 1.0,
        "every small-class middle sits inside the drawn half-pitch band",
    )
    check(
        small_structure["density"] > structure["density"],
        "the small-class bed is denser than the mixed one "
        f"({small_structure['density']:.1f} vs {structure['density']:.1f} fruit/m)",
    )

    # --- the pre-load ---------------------------------------------------- #
    ready = make_spawner(cfg, pool_items)
    ready.prime(count=4)
    preloaded = [
        s for s in ready.active if not s.parked and not s.held
    ]
    pre_pos = [ready.position(s) for s in preloaded]
    pre_min = min(
        (
            float(np.hypot(a[0] - b[0], a[1] - b[1]))
            for i, a in enumerate(pre_pos)
            for b in pre_pos[i + 1:]
        ),
        default=float("inf"),
    )
    pre_along = sorted(float(pos[1]) for pos in pre_pos)
    say(
        f"pre-load (prime 4 rows): {len(preloaded)} fruit on the belt, "
        f"min planar separation {pre_min:.4f} m, stats={dict(ready.stats)}"
    )
    check(
        len(preloaded) >= 6,
        f"the bed pre-load places the first rows ({len(preloaded)} fruit; a row "
        "carries 2-3 and the pair rule can refuse a middle)",
    )
    check(pre_min >= RELEASE_CLEAR - 1e-9, f"the pre-load clears the 0.08 m floor ({pre_min:.4f})")
    # A reset replays the same rows (the schedule is recreated from the same
    # seed), which is what a per-episode battery relies on.
    ready.reset()
    ready.prime(count=4)
    replayed = [
        tuple(round(float(v), 6) for v in ready.position(s)[:2])
        for s in ready.active
        if not s.parked and not s.held
    ]
    first = [
        tuple(round(float(v), 6) for v in pos[:2])
        for pos in pre_pos
    ]
    say(f"  reset replay: {len(replayed)} fruit, positions match={replayed == first}")
    check(replayed == first, "a reset replays the pre-load positions bit-identically")

    # --- the live-recycle counter is live, not vacuous --------------------- #
    # The six cells below assert `bed_live_recycled == 0`. A counter that never
    # fires proves nothing, so drive the exhausted case directly: a bed spawner
    # whose *whole* pool is on the belt has no parked body to draw, and
    # `_pick_recyclable` must fall through to a live one (the pre-B1 teleport).
    # This is also why the capacity invariant below is the regression test for
    # B1 rather than the zero itself: this fake belt peaks at 24 live bodies, so
    # at the old pool of 28 it happened to keep ~4 parked and read 0 here while
    # the real loop (whose pump draws a burst per call) read 57 %.
    probe_spawner = make_spawner(cfg, pool_items[:2])
    for sample in probe_spawner.samples:
        probe_spawner.respawn(sample)
        if sample not in probe_spawner.active:
            probe_spawner.active.append(sample)
    probe_before = int(probe_spawner.stats.get("bed_live_recycled", 0))
    probe_draw = probe_spawner.release_next(place=False)
    probe_fired = int(probe_spawner.stats.get("bed_live_recycled", 0)) - probe_before
    say(
        f"live-recycle counter probe (2-body pool, all 2 live): draw "
        f"{'took a LIVE body' if probe_fired else 'found nothing'} -> "
        f"bed_live_recycled={probe_fired}/"
        f"{probe_spawner.stats.get('bed_draws', 0)}"
    )
    check(
        probe_draw is not None and probe_fired == 1,
        "the live-recycle counter fires when the pool is exhausted "
        f"({probe_fired})",
    )

    # --- the output-lane draw path (P32-A R1, now refused) ---------------- #
    # The sim measured 1/489 live recycles on the cadence arm: the drawn body was
    # a *placed* fruit on the raised output lane (`x=0.628, y=-0.583, z=1.377`),
    # which `_pick_recyclable`'s x-window (`|x - 0.34| <= 0.30`) admits. The fake
    # belt never places there, so this probe is the reproduction. Since the R1
    # fix (a bed-scoped z-skip above `belt_top + 0.10` = 1.27 m) the draw must
    # **refuse** it; the same two bodies at main-belt height must still be
    # drawn, so the fix is scoped to the raised lane and not to height in
    # general. `bed_draws` proves the probe really reached the predicate.
    lane_z = 1.377
    belt_top = float(cfg.belt_center[2]) + float(cfg.belt_size[2]) / 2.0
    for label, z, expect_draw in (
        ("raised output lane", lane_z, False),
        ("main belt", belt_top + 0.06, True),
    ):
        lane_spawner = make_spawner(cfg, pool_items[:2])
        for sample in lane_spawner.samples:
            sample.parked = False
            lane_spawner._rigids[sample.index].pos = np.array([0.628, -0.583, z])
            if sample not in lane_spawner.active:
                lane_spawner.active.append(sample)
        draws_before = int(lane_spawner.stats.get("bed_draws", 0))
        lane_before = int(lane_spawner.stats.get("bed_live_recycled", 0))
        lane_draw = lane_spawner.release_next(place=False)
        lane_fired = int(lane_spawner.stats.get("bed_live_recycled", 0)) - lane_before
        lane_draws = int(lane_spawner.stats.get("bed_draws", 0)) - draws_before
        say(
            f"output-lane draw probe ({label}: 2 bodies at x=0.628, y=-0.583, "
            f"z={z:.3f} vs the {belt_top + 0.10:.3f} m cut, nothing parked): "
            f"draw {'took a body' if lane_draw is not None else 'skipped both'} "
            f"-> bed_live_recycled={lane_fired} (draws +{lane_draws})"
        )
        check(lane_draws == 1, f"the {label} probe reached the draw predicate ({lane_draws})")
        if expect_draw:
            check(
                lane_draw is not None and lane_fired == 1,
                "a main-belt body at the same x/y is still drawn "
                f"(draw={lane_draw is not None}, fired={lane_fired})",
            )
        else:
            check(
                lane_draw is None and lane_fired == 0,
                "a body on the raised output lane is NOT recycled "
                f"(draw={lane_draw is not None}, fired={lane_fired}) - R1 fixed",
            )

    # --- the belt-end despawn gap (P32-A R2, now swept) -------------------- #
    # The simulator's second residual: the end-of-line recycle lived only inside
    # `update`, which the driver calls at the attempt boundary, so belt travel
    # *inside* an attempt carried fruit past `despawn_y` and over the belt's
    # physical end before the next pump counted it (`fell_off` 5 on the cadence
    # arm, 102 - 96 past the end - on the 20-attempt control, `reached_end=0`).
    # The fix is a scan-only sweep on the driver's tick (`scan_despawn`). The
    # integrated cells above cannot produce the class (their own tick loop
    # despawns at `despawn_y`), so this probe is the reproduction.
    probe = despawn_sweep_probe(cfg, pool_items)
    belt_end = probe["belt_end"]
    travel_s = (probe["despawn_y"] - belt_end) / abs(float(cfg.belt_speed))
    say(
        f"belt-end despawn probe (one boundary pump, then 14 s of belt travel; "
        f"belt end {belt_end:+.3f} m, despawn {probe['despawn_y']:+.3f} m = "
        f"{travel_s:.2f} s of travel at {abs(float(cfg.belt_speed)):.2f} m/s; "
        f"sweep {probe['sweep_s']:.2f} s):"
    )
    for label in ("control", "fix"):
        cell = probe[label]
        say(
            f"  {label:7s}: fell_off {cell['fell_off']} reached_end "
            f"{cell['reached_end']} sweeps {cell['sweeps']} swept {cell['swept']}; "
            f"bodies on the floor {len(cell['on_floor'])} "
            f"(min along {cell['min_along']:+.3f} m); residual "
            f"{cell['residual_kind']}; belt-end kinds "
            f"{cell['belt_end_kinds'][:4]}"
            + ("..." if len(cell["belt_end_kinds"]) > 4 else "")
        )
    control, fixed = probe["control"], probe["fix"]
    check(
        len(control["on_floor"]) >= 1 and control["reached_end"] == 0,
        "the control reproduces the belt-end class: bodies reach the floor and "
        f"the next pump charges them fell_off ({len(control['on_floor'])} on the "
        f"floor, fell_off {control['fell_off']}, reached_end {control['reached_end']})",
    )
    check(
        control["min_along"] < belt_end - 1e-9,
        f"the control's belt travel passes the belt end ({control['min_along']:+.3f})",
    )
    check(
        not fixed["on_floor"] and fixed["min_along"] > belt_end,
        "the sweep recycles before the belt end - no body reaches the floor "
        f"({len(fixed['on_floor'])} on the floor, min along {fixed['min_along']:+.3f})",
    )
    check(
        fixed["reached_end"] >= 1
        and fixed["reached_end"] == len(fixed["belt_end_kinds"])
        and all(kind == "reached_end" for kind in fixed["belt_end_kinds"]),
        "the swept bodies are counted reached_end, not fell_off "
        f"({fixed['reached_end']} reached_end, kinds {sorted(set(fixed['belt_end_kinds']))})",
    )
    check(
        fixed["fell_off"] == 1 and control["fell_off"] == fixed["fell_off"] + len(
            control["on_floor"]
        ),
        "the genuine floor class is unchanged: the between-belts residual is "
        f"fell_off in both cells (control {control['fell_off']}, fix "
        f"{fixed['fell_off']}), and the fix converts only the belt-end bodies",
    )
    check(
        fixed["residual_kind"] == "fell_off" and control["residual_kind"] == "fell_off",
        "a released payload between the belts is fell_off in both cells "
        f"({control['residual_kind']}/{fixed['residual_kind']})",
    )
    check(
        fixed["sweeps"] >= int(14.0 / probe["sweep_s"]) - 2,
        f"the sweep ran at its stride ({fixed['sweeps']} sweeps in 14 s at "
        f"{probe['sweep_s']:.2f} s)",
    )
    check(
        probe["guard_after"] == probe["guard_live"] and probe["guard_reached"] == 0,
        "the sweep never touches a mid-belt body "
        f"({len(probe['guard_live'])} live before/after, reached_end "
        f"{probe['guard_reached']})",
    )
    check(
        probe["legacy_stats_unchanged"] and probe["legacy_live_unchanged"],
        "with the bed off, `scan_despawn` is inert (stats and live set unchanged)",
    )
    check(
        probe["legacy_sweep_keys"] == [],
        "a bed-off spawner gains no sweep counter "
        f"({probe['legacy_sweep_keys']})",
    )
    check(
        probe["tray_active"] and probe["tray_stats_unchanged"],
        "the sweep leaves a body in a discharge tray to `update`'s dwell "
        f"(active={probe['tray_active']}, stats unchanged="
        f"{probe['tray_stats_unchanged']})",
    )
    # The refactor behind R2 (`_end_of_line`/`_recycle_end`, shared by `update`
    # and the sweep) must classify exactly as the pre-split code did. The shipped
    # acceptance does not exercise the branch, so pin it here.
    rows = end_of_line_equivalence(cfg, make_spawner(cfg, pool_items))
    for label, got, shipped in rows:
        check(
            got == shipped,
            f"`_end_of_line` matches the shipped predicate on '{label}' "
            f"({got} vs {shipped})",
        )
    say(
        "  classification equivalence (the R2 refactor vs the pre-split code, "
        f"{len(rows)} cases): "
        + ", ".join(f"{label}->{got}" for label, got, _ in rows)
    )
    stride_s = max(1, int(round(probe["sweep_s"] * 120.0))) / 120.0
    check(
        stride_s <= 0.8 * travel_s,
        f"the sweep stride ({stride_s:.2f} s) is inside the belt-end margin "
        f"({travel_s:.2f} s of travel from despawn to the end)",
    )

    # --- the integrated run (real spawner, fake belt) --------------------- #
    # The four-cell-per-queue battery the Gate-1 finding B2 asks for: the
    # delivered candidate count at the shipped queue depth and at 18, each at
    # the per-tick / 3 s / attempt-boundary (16 s) update cadence. `--fast` (the
    # selfcheck leg) keeps the two per-tick cells and the 16 s cell at 45 s; the
    # record run carries all six at 90 s.
    seconds = 45.0 if args.fast else 90.0
    cadences = [
        ("per-tick", 0.0),
        ("3 s", 3.0),
        ("16 s (attempt boundary)", 16.0),
    ]
    if args.fast:
        cadences = [cadences[0], cadences[2]]
    say(
        f"integrated (real FruitSpawner, fake belt, {SEED=}, prime 4 rows, "
        f"{seconds:.0f} s, one consumer / 5.6 s, "
        f"{len(cadences)} cadences x 2 queue depths"
        + (", --fast)" if args.fast else "):")
    )
    saved_queue = os.environ.get("FRUIT_QUEUE_MAX")
    results = {}
    try:
        for queue_max in ("6", "18"):
            os.environ["FRUIT_QUEUE_MAX"] = queue_max
            for label, update_every in cadences:
                results[(queue_max, label)] = integrated(
                    cfg, pool_items, seconds=seconds, update_every_s=update_every
                )
    finally:
        if saved_queue is None:
            os.environ.pop("FRUIT_QUEUE_MAX", None)
        else:
            os.environ["FRUIT_QUEUE_MAX"] = saved_queue

    table = {}
    stock_table = {}
    for (queue_max, label), result in results.items():
        tag = f"q{queue_max} {label}"
        spawner = result["spawner"]
        stats = dict(spawner.stats)
        placed = result["placed"]
        draws = int(stats.get("bed_draws", 0))
        live_recycled = int(stats.get("bed_live_recycled", 0))
        bed_placed = int(stats.get("bed_placed", 0))
        live = [s for s in spawner.active if not s.parked and not s.held]
        window = result["window"]
        at_pick = result["window_at_pick"]
        per_s = bed_placed / seconds
        per_m = per_s / abs(float(cfg.belt_speed))
        spawned = {
            int(item["index"])
            for item in placed
            if item["y"] >= float(cfg.spawn_y) - 0.02
        }
        despawned = set(result["despawned"])
        # `transit` is the strict form (spawn point -> belt end). A late pump
        # call places its backlog at the position the row *would* have reached,
        # i.e. mid-belt, and the consumer takes the spawn-point bodies first, so
        # the low-cadence cells hold no strict transit; `any_transit` (any
        # placement -> belt end) is the invariant every cell must show, and the
        # strict form is asserted on the on-time (per-tick) cells.
        transits = spawned & despawned
        any_transits = {int(item["index"]) for item in placed} & despawned
        body = gap_stats(result["body_gaps"])
        rows_gaps = gap_stats(result["row_gaps"])
        classes = Counter(item["category"] for item in placed)
        grades = Counter(item["grade"] for item in placed)
        mean_window = sum(window) / len(window)
        mean_pick = sum(at_pick) / len(at_pick) if at_pick else float("nan")
        at_pick_stock = result["stock_at_pick"]
        mean_stock = sum(result["stock"]) / len(result["stock"])
        mean_stock_pick = (
            sum(at_pick_stock) / len(at_pick_stock) if at_pick_stock else float("nan")
        )
        table[(queue_max, label)] = (mean_window, mean_pick)
        stock_table[(queue_max, label)] = (mean_stock, mean_stock_pick)
        say(
            f"  [{tag}] placed {bed_placed} slots "
            f"({per_s:.2f}/s = {per_m:.1f} fruit/m of belt travel) from "
            f"{draws} draws ({draws/bed_placed:.2f}x), transits "
            f"{len(transits)} spawn-point ({len(any_transits)} placed->despawn, "
            f"{len(result['despawned'])} despawns), live {len(live)} "
            f"(peak {result['live_peak']}, reserve {POOL - result['live_peak']} "
            f"parked of pool {POOL})"
        )
        say(
            f"  [{tag}] window 1.1 m: mean {mean_window:.1f} "
            f"p10 {sorted(window)[int(0.10*(len(window)-1))]} "
            f"max {max(window)}; at pick mean {mean_pick:.1f} "
            f"| body gaps {fmt_gaps(body)} | row gaps {fmt_gaps(rows_gaps)}"
        )
        say(
            f"  [{tag}] selector window (>={cfg.pick_y + CATCH_FLOOR:.2f} m): "
            f"mean {mean_stock:.1f} min {min(result['stock'])} "
            f"max {max(result['stock'])}; at pick mean {mean_stock_pick:.1f} "
            f"min {min(at_pick_stock) if at_pick_stock else 0}"
        )
        say(
            f"  [{tag}] live-recycled {live_recycled}/{draws} "
            f"({live_recycled*100.0/draws if draws else 0.0:.1f} %), "
            f"abreast max {result['max_abreast']} "
            f"({result['abreast_share']*100:.0f} % paired), "
            f"min live sep {result['min_sep']:.4f} m, "
            f"min corridor margin {result['margin']:+.4f} m, "
            f"classes " + ",".join(f"{k}:{v}" for k, v in sorted(classes.items()))
            + " grades " + ",".join(f"{k}:{v}" for k, v in sorted(grades.items()))
        )
        check(
            stats.get("bed_refused", 0) + stats.get("bed_rows", 0) > 0,
            f"[{tag}] the bed feeder ran",
        )
        check(
            bed_placed == len(placed),
            f"[{tag}] `bed_placed` matches the placement hook "
            f"({bed_placed} vs {len(placed)})",
        )
        # B1: the pool is sized above the belt's live capacity, so no draw may
        # fall through to a live body (a teleport of a mid-belt candidate).
        # The **capacity** half is the part that would have caught the 28-pool:
        # a pump call may release `burst_max` (6) slots, i.e. ~3 rows' worth of
        # draws (one per column = 9), and those must all come from parked bodies.
        reserve = POOL - result["live_peak"]
        check(
            reserve >= 3 * len(plan.columns),
            f"[{tag}] the pool keeps a burst's worth of rows parked "
            f"(reserve {reserve} >= {3 * len(plan.columns)}; peak live "
            f"{result['live_peak']} of {POOL})",
        )
        check(
            live_recycled == 0,
            f"[{tag}] no draw recycles a LIVE body (bed_live_recycled="
            f"{live_recycled}/{draws})",
        )
        # ...and the belt must actually be a line, not a reshuffle: a body has
        # to complete a placement -> despawn transit (B1's second assertion).
        check(
            len(any_transits) >= 1,
            f"[{tag}] at least one body completed a placement -> despawn "
            f"transit ({len(any_transits)})",
        )
        if update_every == 0.0:
            check(
                len(transits) >= 1,
                f"[{tag}] at least one body completed a spawn-point -> despawn "
                f"transit ({len(transits)})",
            )
        check(
            result["min_sep"] >= RELEASE_CLEAR - 1e-9,
            f"[{tag}] the delivered belt never violates the 0.08 m floor "
            f"({result['min_sep']:.4f})",
        )
        check(
            result["margin"] >= -1e-9,
            f"[{tag}] the delivered belt never violates the corridor rule "
            f"({result['margin']:+.4f})",
        )
        check(
            int(stats.get("bed_rows", 0)) >= 4,
            f"[{tag}] the feeder delivered rows after the pre-load "
            f"({stats.get('bed_rows', 0)} rows, {bed_placed} slots)",
        )
        if update_every == 0.0:
            check(
                result["max_abreast"] >= 2,
                f"[{tag}] the delivered belt carries fruit abreast, not a "
                f"single-file line (max {result['max_abreast']})",
            )
        if queue_max == "18" and update_every == 0.0:
            check(
                mean_window >= 8.0,
                f"[{tag}] the spawn window holds >= 8 candidates on average "
                f"({mean_window:.1f})",
            )
        if update_every == 0.0:
            check(
                mean_stock_pick >= 3.0,
                f"[{tag}] the selector window holds >= 3 candidates at pick "
                f"({mean_stock_pick:.1f})",
            )

    # P32 phase A: the bed's line-full interlock is its **approach band**
    # (`FruitSpawner._bed_stock_depth`, `FRUIT_SUPPLY_BED_STOCK_MAX=10`), not the
    # station window, so the two queue depths must deliver the same belt. This
    # is the assertion that would catch a regression to `_queue_depth` (measured
    # before the change: q6 delivered 2.6 selector-window candidates against
    # q18's 4.8, and the sim starved 8/10 attempts).
    check(
        abs(table[("6", "per-tick")][0] - table[("18", "per-tick")][0]) < 1e-9
        and abs(table[("6", "per-tick")][1] - table[("18", "per-tick")][1]) < 1e-9,
        "the bed paces on its own stock band - q6 and q18 deliver the same "
        f"belt (q6 {table[('6', 'per-tick')][0]:.1f}, "
        f"q18 {table[('18', 'per-tick')][0]:.1f} in the 1.1 m window)",
    )

    say("  candidate table (mean fruit in the 1.1 m spawn window, all ticks / at pick):")
    say(
        "    queue     "
        + "".join(f"{label:<24s}" for label, _ in cadences)
    )
    for queue_max in ("6", "18"):
        cells = "".join(
            f"{table[(queue_max, label)][0]:>13.1f} /{table[(queue_max, label)][1]:>9.1f}"
            for label, _ in cadences
        )
        say(f"    q{queue_max:<8s}" + cells)
    say(
        "  selector-window table (mean fruit at/above the catch floor, "
        "all ticks / at pick):"
    )
    say(
        "    queue     "
        + "".join(f"{label:<24s}" for label, _ in cadences)
    )
    for queue_max in ("6", "18"):
        cells = "".join(
            f"{stock_table[(queue_max, label)][0]:>13.1f} "
            f"/{stock_table[(queue_max, label)][1]:>9.1f}"
            for label, _ in cadences
        )
        say(f"    q{queue_max:<8s}" + cells)

    # B2's same-harness baseline: the patch sheet (the previous densest
    # schedule, 1-2 abreast every 0.14-0.22 m) at the shipped queue depth and
    # per-tick cadence. Reported, not asserted: the two schedules present
    # different species/grade mixes and the class mix is not held fixed.
    os.environ["FRUIT_SUPPLY_BED"] = "0"
    os.environ["FRUIT_SUPPLY_PATCH"] = "1"
    os.environ["FRUIT_QUEUE_MAX"] = "6"
    try:
        patch_run = integrated(
            cfg,
            synthetic_pool(cfg, 16, 20261022, (("A", 0.5), ("B", 0.3), ("C", 0.2))),
            seconds=seconds,
        )
    finally:
        os.environ.pop("FRUIT_SUPPLY_PATCH", None)
        os.environ["FRUIT_SUPPLY_BED"] = "1"
        if saved_queue is None:
            os.environ.pop("FRUIT_QUEUE_MAX", None)
        else:
            os.environ["FRUIT_QUEUE_MAX"] = saved_queue
    patch_window = patch_run["window"]
    patch_mean = sum(patch_window) / len(patch_window)
    patch_stock = sum(patch_run["stock"]) / len(patch_run["stock"])
    bed_mean = table[("6", "per-tick")][0]
    bed_stock = stock_table[("6", "per-tick")][0]
    say(
        f"  patch baseline (q6 per-tick, its own 16-fruit pool): window mean "
        f"{patch_mean:.1f} p10 {sorted(patch_window)[int(0.10*(len(patch_window)-1))]} "
        f"max {max(patch_window)}, selector window mean {patch_stock:.1f}, placed "
        f"{patch_run['spawner'].stats.get('released', 0)} draws "
        f"| bed/patch window ratio {bed_mean/patch_mean:.2f}x "
        f"(selector window {bed_stock/patch_stock:.2f}x) at the same cadence"
    )

    # --- bedrock: the legacy streams, bed off ---------------------------- #
    say("bedrock: legacy slot streams with FRUIT_SUPPLY_BED unset")
    for name, env in LEGACY_SCENARIOS.items():
        lines = legacy_lines(env)
        digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
        expected, expected_lines = PRE_CHANGE_DIGESTS[name]
        ok = digest == expected and len(lines) == expected_lines
        say(
            f"  {name:8s} {len(lines):3d} lines sha256={digest[:16]}... "
            f"{'ok' if ok else 'MISMATCH vs ' + expected[:16]}"
        )
        check(ok, f"legacy {name} stream is byte-identical to the pre-bed tree")

    # --- the final `[bed] stats` row (m3) ---------------------------------- #
    # The run's zero-live-recycle / zero-fell-off claim has to be visible in the
    # *simulator* log, not only in this audit: the row is printed after the
    # driver's summary, and the legacy path prints nothing.
    bed_row = results[("6", "per-tick")]["spawner"].bed_stats_line()
    patch_row = patch_run["spawner"].bed_stats_line()
    say(f"  final [bed] stats row: {bed_row}")
    check(
        bed_row is not None
        and "live_recycled=" in bed_row
        and "fell_off=" in bed_row
        and "late_dropped=" in bed_row,
        "the bed prints its final [bed] stats row (zero-recycle/fell-off evidence)",
    )
    check(
        patch_row is None,
        "a non-bed spawner prints no [bed] stats row (legacy logs byte-identical)",
    )

    clear_supply_env()
    print(f"[211] ok ({checks} checks)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"[211] FAIL: {error}", flush=True)
        raise SystemExit(1)
