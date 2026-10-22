"""Pure geometry and schedule for the dense 2D "bed" supply (P32 phase 1).

`fruits.py` imports Isaac Sim, so the pack audit (`scripts/211_bed_audit.py`)
cannot import it. Everything the bed *is* - the columns, the **rows**, the row
pitch, the staggered middle column, the bounded upstream shift, the pair-
clearance predicate - lives here and uses the standard library only, so the
audit reproduces the schedule with plain `python3` from the same seed the
spawner uses.

Why the bed. The owner's directive (2026-10-22) is that the belt read like the
reference grading-line screenshots: many fruit abreast, a 2D bed, "enough fruit
to serve as candidates". The shipped schedules are single-file
(`FRUIT_SUPPLY_SCATTER`, `FRUIT_SUPPLY_WAVE`) or 1-2 abreast every 0.14-0.22 m
(`FRUIT_SUPPLY_PATCH`, ~8.9 fruit/m).

Why **rows**. The first bed pass emitted one slot per release and cycled the
three columns, so the belt read as a single wiggly line of alternating x (the
measured defect: `logs/p32/bed_line.png`, 20 live bodies, ~10 visible, the
middle column carrying 5 of 70 slots) - not the photo's rows abreast. A bed is
a *row*: the two edge columns at the same along, 0.16 m apart, wider than the
corridor need of the largest fruit (0.107 m), so an edge pair is always
graspable from both sides; the middle column is staggered by **half a row
pitch** and only joins the row when its diagonal clears the pair rule.

The geometry (constants below, measured on `174`/`183` and in the P32 note):

* the reachable clean columns with the top-down attitude are x = 0.20/0.28/0.36
  m (6 mm residual over x = 0.18-0.39, cliff at x >= 0.42);
* the open jaw needs +/-0.066 m of clear plane around the hand axis, the pads
  are ~6 cm deep along the belt, fruit diameters are 2.8-7.0 cm
  (`SceneConfig.fruit_dimensions`);
* the legacy `_release_clear` floor is 0.08 m in the belt plane.

So a pair `(d, radii)` is graspable only when both `d >= 0.08` and
`d >= 0.066 + max(r_a, r_b) + margin`. The enforced form is the union of the
two ordered one-sided statements (`d >= 0.066 + r_b` for grasping a with b as
its neighbour, and the mirror), so it is never weaker than either.

The consequences, by design:

* **edge pair** (x = 0.20 and 0.36, same along): `d = 0.16` - always clear
  (0.16 - 0.066 - 0.035 - 0.006 = +0.053 m for the largest fruit).
* **same column, next row**: `d = row pitch`; a 7 cm fruit needs
  `0.066 + 0.035 + 0.006 = 0.107 m`, inside the 0.13-0.15 m band (the
  2026-10-22 owner decision widened it from 0.11-0.13 - see `BED_ALONG_MIN`).
* **middle** (x = 0.28, half a row pitch downstream): its nearest edge
  neighbour is diagonal, `sqrt(0.08^2 + (pitch/2)^2)` = 0.103-0.110 m at the
  shipped band, which admits a max radius of 0.031-0.038 m (a 6.2-7.5 cm
  diameter) - at 0.13 only the small classes (lychee 3.1, strawberry 3.7,
  tomato 5.0 cm, kiwi 5.2) pass, at 0.15 most classes do. So the middle is a
  *conditional* third fruit, not a third column at every row, and the
  delivered middle share is a pitch number the audit reports.

A row that cannot clear the live bed at its nominal along is shifted **upstream**
within a small bound (the physical "wait a moment": the fruit ahead moves down
the belt); if the bound is exhausted the row is skipped and counted, exactly
like the legacy pump's `supply_skipped`. At the shipped pitch the lattice
itself never needs it - the same-column distance is 0.13-0.15 m against the
0.107 m a 7 cm fruit needs, and a middle's neighbours are its own row's and the
previous row's edges, both at half a pitch - so the shift is the safety net for
a stray body (a recycled fallback, or a fruit pushed back onto the belt), and
`scripts/211_bed_audit.py` pins the mechanism with a direct probe.

What it measures (`scripts/211_bed_audit.py`, the shipped 40-fruit pool,
SEED=5, 80 due rows, the 0.13-0.15 m pitch): **80/80 rows placed, 51 of 80 with
the middle (64 %), 7.2 rows/m, 19.1 fruit/m**, 24 fruit in the 1.1 m window in
the undisturbed lattice; the old per-slot lattice read 15.7 fruit/m as an
alternating single file. The 0.11-0.13 m pitch placed the middle in 0-4 % of
rows (its diagonal admitted only 5.0-6.2 cm classes); 0.15 admits 7.5 cm, so the
middle is now the common case and the lattice is 3 abreast on 2 rows in 3 - the
pattern the reference photo shows, at a pitch the jaw can grasp. On the fake
belt the 1.1 m spawn window holds ~16 candidates on average at the per-tick
cadence (patch 8.1; the *selector's* window, `>= pick_y + 0.40`, holds 4.0
against the patch's 2.3 = 1.76x) and collapses to **2.8 (selector 0.5) at the
attempt-boundary (16 s) feeder cadence** - the *delivered* count is a
feeder-cadence number, not a lattice number (P32 B2), and the audit reports all
six cadence cells. Since P32 phase A the bed's interlock is its own approach
band (`FRUIT_SUPPLY_BED_STOCK_MAX`), so `FRUIT_QUEUE_MAX` no longer changes the
bed's belt (asserted).

Default off. `BedPlan.from_env` reads the env only when called; `fruits.py`
calls it only when `FRUIT_SUPPLY_BED=1` resolves on, and the bed's random stream
is a separate `random.Random("fruit-bed:<seed>")`, so every legacy schedule
draws exactly the numbers it did before this module existed (pinned by the
audit's bedrock check and `scripts/172_supply_selftest.py`).
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass

#: Half the open parallel-jaw span, measured from the hand axis [m]. The pads
#: are commanded ~2 % inside the fruit diameter, so the *open* span is the
#: clearance that matters when the hand descends next to a neighbour.
OPEN_JAW_HALF_SPAN = 0.066
#: The legacy `_release_clear` floor [m]: no two live fruit closer than this in
#: the belt plane. The bed never relaxes it.
RELEASE_CLEAR = 0.08
#: The measured clean grasp columns across the belt [m] (`174`/`183`: x = 0.20,
#: 0.28, 0.36 hold ~6 mm residual; x >= 0.42 is a 55-96 mm cliff). The first and
#: last columns form the row's edge pair; the interior columns are the staggered
#: middles.
BED_COLUMNS = (0.20, 0.28, 0.36)
#: Along-the-belt pitch between *rows* [m] (edge pair to edge pair). The middle
#: column sits half a pitch downstream of its row.
#:
#: **0.13-0.15, widened from 0.11-0.13 by the 2026-10-22 owner decision**
#: ("the touching pack is not required - widen the spacing slightly so the grasp
#: works; the priority is a normal grasp"). 0.11 was only 3 mm above the largest
#: class's same-column corridor need (0.066 + 0.035 + 0.006 = 0.107 m), so a
#: pair of 7 cm fruit had to be placed to 3 mm and the *simulated* release (a
#: settle, not the audit's exact placement) is where the margin went: the
#: moving catch then closed on a fruit whose neighbour was inside the jaw's
#: 6 mm corridor budget. At 0.13 the same pair holds **+0.023 m** of corridor
#: slack, and at 0.15 the staggered middle's diagonal
#: (`sqrt(0.08^2 + (pitch/2)^2)` = 0.110 m) admits a 7.5 cm fruit instead of
#: 6.2 cm, so the middle column joins far more rows.
#:
#: The two effects on delivered density are opposed and measured in
#: `scripts/211_bed_audit.py`: rows/metre falls 1/0.14 vs 1/0.12 (-14 %) while
#: fruit/row rises (more middles), and the *graspable* density is what the bed
#: is for. The lateral 0.16 m edge pair is unchanged (the owner kept it).
BED_ALONG_MIN = 0.13
BED_ALONG_MAX = 0.15
#: Corridor margin on top of the jaw half-span and the neighbour radius [m].
#: 6 mm matches the catch-up tolerance the reach probes quote as "clean".
BED_MARGIN = 0.006
#: Live pool when the bed is on. Ignored by every other schedule (an explicit
#: `FRUIT_SUPPLY_POOL` still wins).
#:
#: **40, not 28 (P32 B1, 2026-10-22).** 28 equals the belt's *live* capacity at
#: design density, and that is a teleport loop, not a pool. The belt (1.38 m of
#: travel) holds 17 live bodies at the shipped `FRUIT_QUEUE_MAX=6` and 24 at 18
#: (measured, `scripts/211_bed_audit.py`), and the pump draws a burst per call
#: (~3 rows = 9 draws). A 28-fruit pool therefore leaves 4 parked at the q18
#: peak - fewer than one burst - so the draw falls through `_pick_recyclable` to
#: a live mid-belt body and `respawn` teleports it back to the spawn point: a
#: visible jump and a destroyed candidate. The Oracle measured **313/546 = 57 %
#: live-recycled draws** at `FRUIT_QUEUE_MAX=18` on the real loop. 40 leaves 16
#: parked at that peak (23 at q6), so every draw finds a parked body; the audit
#: pins both the fraction (`bed_live_recycled == 0`) and the reserve
#: (`pool - live_peak >= 3 * columns` = one burst's worth of row draws).
#:
#: **Not identically zero in the simulator (P32-A, 2026-10-22):** the cadence arm
#: measured **1/489 = 0.2 %**. `_pick_recyclable` returns the first *downstream*
#: main-belt body it meets, and its x-window test (`|x - belt_center| <= 0.30`)
#: also admits a fruit sitting on the raised output lane (measured
#: `x=0.628, y=-0.583, z=1.377`), so an already-placed fruit can be drawn back
#: to the spawn. The fake belt never produces that geometry, which is why the
#: audit cells stay at zero. The named fix is a bed-scoped z-skip above the main
#: belt top; the battery measures the pre-fix read, so quote `1/489` with the
#: attribution rather than "zero".
BED_POOL = 40
#: Bounded upstream shift of a whole row: try upstream offsets in this step up to
#: this cap, then skip the row. 0.01 m steps are ~1/6 of the pitch, and 0.04 m
#: lifts the middle diagonal from 0.097-0.103 to as much as 0.124 m, which is
#: what lets a 7 cm edge fruit clear the previous row's middle.
BED_SHIFT_STEP = 0.01
BED_SHIFT_MAX = 0.04


def _number(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        # No `say` here: this module stays importable without the log helper
        # (and without importing `fruits`). `fruits.py` prints the resolved bed
        # banner once, which is where a bad value is named.
        return float(default)


def _columns_env(name: str, default: tuple[float, ...]) -> tuple[float, ...]:
    """Parse a comma-separated column list; keep the caller's order."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return tuple(float(v) for v in default)
    try:
        values = tuple(float(part) for part in raw.split(",") if part.strip())
    except ValueError:
        return tuple(float(v) for v in default)
    if len(values) < 2:
        return tuple(float(v) for v in default)
    return values


@dataclass(frozen=True)
class BedPlan:
    """Resolved bed geometry (env ``FRUIT_SUPPLY_BED_*``); no RNG, no draws."""

    columns: tuple[float, ...]
    along_min: float
    along_max: float
    margin: float
    pool: int
    shift_step: float
    shift_max: float

    @classmethod
    def from_env(cls, cfg=None) -> "BedPlan":
        """Resolve the knobs once, at spawner construction.

        `cfg` is accepted for symmetry with `SupplyPlan.from_env(cfg)` but is not
        read: the bed's geometry is absolute in belt coordinates (columns in x,
        pitch along -Y), and the spawner supplies `spawn_y`/`belt_speed` when it
        places a row.
        """
        along_min = max(0.04, _number("FRUIT_SUPPLY_BED_ALONG_MIN", BED_ALONG_MIN))
        along_max = max(along_min, _number("FRUIT_SUPPLY_BED_ALONG_MAX", BED_ALONG_MAX))
        return cls(
            columns=_columns_env("FRUIT_SUPPLY_BED_COLUMNS", BED_COLUMNS),
            along_min=along_min,
            along_max=along_max,
            margin=max(0.0, _number("FRUIT_SUPPLY_BED_MARGIN", BED_MARGIN)),
            pool=max(1, int(_number("FRUIT_SUPPLY_BED_POOL", BED_POOL))),
            shift_step=max(0.0, _number("FRUIT_SUPPLY_BED_SHIFT_STEP", BED_SHIFT_STEP)),
            shift_max=max(0.0, _number("FRUIT_SUPPLY_BED_SHIFT_MAX", BED_SHIFT_MAX)),
        )

    # ------------------------------------------------------------------ #
    @property
    def edge_columns(self) -> tuple[int, int]:
        """The row's abreast pair: the outermost two columns."""
        return (0, len(self.columns) - 1)

    @property
    def middle_columns(self) -> tuple[int, ...]:
        """The interior columns, staggered by half a row pitch."""
        return tuple(range(1, len(self.columns) - 1))

    @property
    def lateral_min(self) -> float:
        """Smallest gap between adjacent columns [m] (the diagonal's short leg)."""
        return min(abs(b - a) for a, b in zip(self.columns, self.columns[1:]))

    def along_need(self, radius: float) -> float:
        """Along distance a same-column successor needs [m] (lateral offset 0).

        The pads are ~6 cm deep along the belt and the open jaw reaches
        `0.066 + r + margin` from the hand axis, so two fruit in one column need
        that much centre-to-centre. At the shipped band a 7 cm fruit needs
        0.107 m; the row pitch is 0.13-0.15 m.
        """
        return OPEN_JAW_HALF_SPAN + max(0.0, float(radius)) + self.margin

    def diagonal(self, pitch: float) -> float:
        """Nearest edge-to-middle distance for a row pitch [m].

        The middle sits half a pitch downstream of its row's edge pair, so its
        nearest neighbours are diagonal: `sqrt(lateral^2 + (pitch/2)^2)`.
        """
        half = 0.5 * float(pitch)
        return math.hypot(self.lateral_min, half)

    def admitted_radius(self, distance: float) -> float:
        """Largest radius a pair at `distance` admits [m] (the pair rule inverted)."""
        return float(distance) - OPEN_JAW_HALF_SPAN - self.margin

    def corridor_need(self, radius: float) -> float:
        """Along distance a slot next to a fruit of `radius` needs [m].

        A fruit whose body reaches past the jaw half-span forces
        `sqrt((0.066 + r + margin)^2 - lateral^2)` between its centre and the
        next slot's when that slot is in the adjacent column (the middle case).
        At the shipped band a 7 cm fruit needs 0.071 m, a 4.5 cm one 0.050 m;
        the same-column form is `along_need`.
        """
        need = OPEN_JAW_HALF_SPAN + max(0.0, float(radius)) + self.margin
        lateral = self.lateral_min
        if need <= lateral:
            return 0.0
        return math.sqrt(need * need - lateral * lateral)

    def pair_margin(
        self,
        along: float,
        x: float,
        radius: float,
        other_along: float,
        other_x: float,
        other_radius: float,
    ) -> float:
        """Clearance of one pair [m]: `d - 0.066 - max(r_a, r_b) - margin`.

        >= 0 means the pair is graspable from both sides; < 0 is the amount the
        corridor is short. The legacy 0.08 m floor is a separate check
        (`pair_clear`) because its geometry is not the jaw's.
        """
        d = math.hypot(along - other_along, x - other_x)
        return d - OPEN_JAW_HALF_SPAN - max(radius, other_radius) - self.margin

    def pair_clear(
        self,
        along: float,
        x: float,
        radius: float,
        other_along: float,
        other_x: float,
        other_radius: float,
    ) -> bool:
        """True when the pair clears both the corridor rule and the 0.08 m floor."""
        d = math.hypot(along - other_along, x - other_x)
        return d >= RELEASE_CLEAR and self.pair_margin(
            along, x, radius, other_along, other_x, other_radius
        ) >= 0.0

    def declared_pair_margin(
        self,
        along: float,
        x: float,
        other_along: float,
        other_x: float,
        other_radius: float,
    ) -> float:
        """The one-sided form `d - 0.066 - r_other` (the audit's literal read).

        Kept beside the enforced symmetric form so the audit can report both:
        the design statement is asymmetric ("a slot must clear every neighbour's
        radius"), the implementation is the pair-symmetric superset of it.
        """
        d = math.hypot(along - other_along, x - other_x)
        return d - OPEN_JAW_HALF_SPAN - other_radius


@dataclass(frozen=True)
class BedSlot:
    """One placed bed slot, in the spawner's frame."""

    index: int
    column: int
    x: float
    along: float
    radius: float
    #: `min(pair_margin)` against every live fruit at placement time [m].
    margin: float
    #: "edge" (the abreast pair) or "middle" (the staggered interior column).
    role: str


@dataclass(frozen=True)
class BedRow:
    """One released row: the edge pair at `along` plus the middles that cleared.

    `slots` are ordered edge-first (the caller's radii order), so the spawner can
    zip them with the samples it drew for the row. A row is all-or-nothing for
    the pair: the edges share one along, and a row whose pair does not clear at
    any shift is refused whole (`place_row` returns None).

    `pitch` is the drawn advance to the **next** row (the schedule's `next_gap`
    semantics); `stagger` is the half pitch the middle sits *downstream* of
    `along`, taken from the **previous** row's pitch so the middle is exactly
    midway between its row and the row before it.
    """

    index: int
    along: float
    pitch: float
    stagger: float
    shift: float
    slots: tuple[BedSlot, ...]

    @property
    def fruit_count(self) -> int:
        return len(self.slots)

    @property
    def has_middle(self) -> bool:
        return any(slot.role == "middle" for slot in self.slots)

    @property
    def middle_along(self) -> float:
        """The middle column's along (half a row pitch downstream of the pair)."""
        return self.along - self.stagger


class BedSchedule:
    """Deterministic **row** generator: the bed's own RNG stream and state.

    The spawner calls `next_gap()` once per *due row* (whether or not it is
    placed - the feeder's clock advances regardless) and `place_row()` with the
    radii of up to one row's worth of drawn fruit plus the live neighbours. The
    schedule never touches the spawner's `random.Random`, so the legacy arrival
    streams are unchanged.

    State: `row` is the ordinal of the *next* due row, `index` the row being
    placed. The row pitch is drawn once per row from `along_min..along_max`; the
    middle column is placed at `along - prev_pitch/2`, i.e. exactly midway
    between this row and the row before it, so the fruit order on the belt is
    edge pair, middle, edge pair, middle, ... A refused row does not re-draw the
    pitch (the lattice keeps its rhythm); it leaves a hole, exactly like the
    legacy pump's `supply_skipped`.
    """

    def __init__(self, plan: BedPlan, seed: int = 0):
        self.plan = plan
        #: Separate stream: a *string* seed makes `random.Random` use its stable
        #: sha512 path, so the schedule is identical across processes and the
        #: audit reproduces the spawner's numbers from the same seed.
        self.rng = random.Random(f"fruit-bed:{int(seed)}")
        self.row = 0
        self.index = 0
        self._pitch = plan.along_min
        self._prev_pitch: float | None = None
        #: Slots placed (edge + middle fruit), rows that carried at least one
        #: slot, rows that carried a middle, and middles refused by the pair rule.
        self.placed = 0
        self.rows_placed = 0
        self.full_rows = 0
        self.middle_refused = 0
        #: Rows that needed the bounded upstream shift.
        self.shifted = 0
        #: Per-column accepted-slot counts (the audit's structure read).
        self.column_hits = [0] * len(plan.columns)

    # ------------------------------------------------------------------ #
    def next_gap(self) -> float:
        """Nominal along advance from *this* due row to the next one [m].

        The pump draws it before it places the row (its `_next_release +=
        period` is what schedules the following release), so the value belongs
        to the gap *after* the row about to be placed. One row pitch per row.
        The **previous** value is kept: that is the distance from the row before
        to this one, so half of it is where this row's middle sits.
        """
        index = self.row
        self.row += 1
        self.index = index
        self._prev_pitch = self._pitch
        self._pitch = self.rng.uniform(self.plan.along_min, self.plan.along_max)
        return self._pitch

    def place_row(
        self,
        along: float,
        radii,
        neighbours,
        along_max: float | None = None,
    ) -> BedRow | None:
        """Choose the row's slots for the current row, or None after the bound.

        `radii` are the drawn fruit's radii in draw order: `radii[0]` and
        `radii[1]` are the edge pair (x = first/last column), `radii[2:]` the
        middles. Fewer than two radii (pool exhaustion) degrades the row to the
        one fruit that was drawn; a middle is only attempted for a complete pair.

        `neighbours` is an iterable of `(along, x, radius)` for every live fruit
        in the belt plane. `along_max` caps the upstream shift (the release point
        of an on-time row is already at `spawn_y`, so there is no room); the
        spawner passes `cfg.spawn_y`.

        Candidate order per row:

        1. the nominal along, both edges, then the staggered middles;
        2. upstream offsets `shift_step, 2*shift_step, ...` up to `shift_max`,
           as a **whole row** (the pair stays abreast). The shift is the
           physical "wait a moment": the slot is released that much later, so
           the fruit ahead has moved down the belt by the same amount, and the
           spawner pushes its clock by the same time so the *following* pitch
           stays the drawn one.

        Every candidate is tested with the pair rule against *every* live
        neighbour and against the row's own already-placed fruit, so a violating
        pair is never released. A middle the rule refuses is skipped (counted in
        `middle_refused`) and the row keeps its pair. Returns None when no
        candidate along admits the pair; the caller skips the row (the samples go
        back to the feeder's pool and re-enter later) and counts it.
        """
        live = [(float(a), float(x), float(r)) for a, x, r in neighbours]
        available = [float(r) for r in radii]
        if not available:
            return None
        pair = min(2, len(available), len(self.plan.columns))
        edge_columns = self.plan.edge_columns[:pair]

        candidates: list[tuple[float, float]] = [(along, 0.0)]
        if self.plan.shift_step > 0.0 and self.plan.shift_max > 0.0:
            steps = int(math.floor(self.plan.shift_max / self.plan.shift_step + 1e-9))
            for step in range(1, steps + 1):
                shifted = along + step * self.plan.shift_step
                if along_max is not None and shifted > along_max + 1e-9:
                    break
                candidates.append((shifted, step * self.plan.shift_step))

        for row_along, shift in candidates:
            row_slots: list[BedSlot] = []
            ok = True
            for slot_index, column in enumerate(edge_columns):
                margin = self._fit(
                    row_along, column, available[slot_index], live, row_slots
                )
                if margin is None:
                    ok = False
                    break
                row_slots.append(
                    self._slot(column, row_along, available[slot_index], margin, "edge")
                )
            if not ok:
                continue  # the pair must clear together; try the next shift
            stagger = 0.5 * (
                self._pitch if self._prev_pitch is None else self._prev_pitch
            )
            if pair >= 2:
                middle_along = row_along - stagger
                for k, column in enumerate(self.plan.middle_columns):
                    if 2 + k >= len(available):
                        break
                    margin = self._fit(
                        middle_along, column, available[2 + k], live, row_slots
                    )
                    if margin is None:
                        self.middle_refused += 1
                        continue
                    row_slots.append(
                        self._slot(
                            column, middle_along, available[2 + k], margin, "middle"
                        )
                    )
            row = BedRow(
                index=self.index,
                along=row_along,
                pitch=self._pitch,
                stagger=stagger,
                shift=shift,
                slots=tuple(row_slots),
            )
            self._commit(row)
            return row
        return None

    # ------------------------------------------------------------------ #
    def _fit(self, along: float, column: int, radius: float, live, row_slots) -> float | None:
        """Min pair margin of a candidate slot, or None when it violates a pair."""
        x = self.plan.columns[column]
        margin = math.inf
        for other_along, other_x, other_radius in live:
            d = math.hypot(along - other_along, x - other_x)
            if d < RELEASE_CLEAR:
                return None
            pair = self.plan.pair_margin(
                along, x, radius, other_along, other_x, other_radius
            )
            if pair < 0.0:
                return None
            margin = min(margin, pair)
        for slot in row_slots:
            d = math.hypot(along - slot.along, x - slot.x)
            if d < RELEASE_CLEAR:
                return None
            pair = self.plan.pair_margin(
                along, x, radius, slot.along, slot.x, slot.radius
            )
            if pair < 0.0:
                return None
            margin = min(margin, pair)
        return margin

    def _slot(
        self, column: int, along: float, radius: float, margin: float, role: str
    ) -> BedSlot:
        return BedSlot(
            index=self.index,
            column=column,
            x=self.plan.columns[column],
            along=along,
            radius=float(radius),
            margin=float(margin) if math.isfinite(margin) else float("inf"),
            role=role,
        )

    def _commit(self, row: BedRow) -> None:
        self.rows_placed += 1
        self.placed += len(row.slots)
        for slot in row.slots:
            self.column_hits[slot.column] += 1
        if row.has_middle:
            self.full_rows += 1
        if row.shift > 0.0:
            self.shifted += 1
