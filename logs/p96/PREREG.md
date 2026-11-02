# P96 PREREG - the clearance pre-pose: no hand inside another lane's fruit band

**Pinned before any run of this phase.** The md5 of this file is written to
`logs/p96/PREREG.md5` immediately after it is frozen; no run of phase 1 or 2
starts before that file exists. Amendments (if a measurement forces one) go to
`logs/p96/PREREG_A<N>.md` with their own pin, never into this file.

Phase 0 (the **offline** station map) is allowed to run on the tree as it stands
after the pin - it executes no task code path that this phase changes - but its
grid, its modes and its criterion are fixed here, and the phase-1 build does not
start until phase 0's answer is written down.

---

## 0. What this phase is, and what it is not

P95 established the defect and priced the fix (`logs/p95/RESULTS.md` sections 2,
5, 6):

* The two-line's pre-pose is the **calibrated grasp configuration** at the arm's
  own station. Its pad plane ends at `belt_top + 0.029` - i.e. **29 mm below a
  fruit's top** (the tallest fruit's top is `belt_top + 0.0585`) - and the
  pre-pose **blend dives there** from the ready pose (`belt_top + 0.107` pad
  plane), so the pads sweep *through* the fruit band on every attempt.
* The stations are `left y = +0.000` (upstream) and `right y = -0.100`
  (downstream) on a `-y` belt, so a **right**-arm fruit must cross the **left**
  station while the left hand is doing exactly that blend. Measured exposure
  over 40 attempts: right-arm fruit n = 19, closest other-hand pad approach
  median **31.6 mm**, min **0.0 mm**, **5/19 <= 6.4 mm**; left-arm fruit n = 21,
  median 217.2 mm, min 126.3, **0/21**. **1 of 40** attempts is a contact (the
  jaw span is knocked `98.0 -> 59.8 mm` and springs back).
* The class is **structural**, not a rate: 1/40 = 2.5 points against P93's
  power statement of **364 attempts per arm** for 8.75 points at 80 %.

**This phase's argument is the invariant, not the rate.** A hand whose pads are
inside another lane's fruit band at any tick before its own descent leg is a
defect regardless of how often it converts to a failure, which is P94's
precedent. The phase therefore ships on **the invariant plus no lost
placement**, and reports the count as a draw.

## 1. The invariant, stated so it can be falsified

> **INV**: at every control tick between an attempt's start and its descent
> leg's start, the hand that is **not** taking that fruit has **no pad contact**
> with the fruit, and its pad plane is at or above `belt_top + 0.0745`
> (`jaw_z >= belt_top + 0.155`, P95's number: the pad point hangs
> `FINGER_TIP_BELOW_JAW = 0.0805` below the jaw centre, P39's measured identity).

Two readings, in this order:

1. **The contact census** (P95's own criterion, `logs/p95/METHOD_A1.md` A1.2): a
   **contact** is `pad gap <= 6 mm` **and** that hand's **measured jaw-span swing
   `>= 2 mm` within +-4 ticks** of the closest tick. The span is the verdict - a
   commanded close cannot produce 2 mm of span change (the finger drive is
   stiffness-limited to 0.1 mm at P41's `k = 1e5 N/m` and the 10 N cap) - and the
   gap is a **+-5 mm indicator** because the finger plates are angled at a 98 mm
   span. The census counts, per attempt: the closest pad-point gap, and whether
   any pre-leg window is a contact.
2. **The pose reading** (a log field, not a trace): the pre-pose's own achieved
   jaw height at each station, `jaw_z - 0.0805 >= belt_top + 0.0745`.

Both must hold for the invariant to be restored. (1) alone could pass by luck on
two seeds; (2) alone does not prove the pads are clear of the *fruit* (a hand can
be high and still be beside one) - which is why (1) is primary and (2) is the
mechanism.

## 2. Phase 0 - the offline station map (no battery, no task code path)

**Question:** does each two-line station admit a **clearance pre-pose** at all -
a joint configuration whose achieved jaw sits at `belt_top + z`, `z >= 0.155`,
solved to `<= 6 mm` with the arm's own joints inside their limits?

**Grid** (`logs/p96/prepose_map.py`, a copy of `logs/p66/ik_probe_sweep.py`'s
recipe - same scene build `("environment", "pedestal", "robot", "conveyor")`,
same seed `configs/waypoints_oriented.json` `arms.<side>.grasp`, same
`iterations=400, tolerance=6 mm`):

* **arm x station**: `left @ y=+0.000`, `right @ y=-0.100` (the shipped pair).
* **x**: `0.32, 0.34, 0.36` (`0.34` is `cfg.pick_x`, the column the station solve
  actually uses).
* **z above belt top**: `0.095` (the shipped `grasp_clearance`, i.e. today's
  right-station solve depth), `0.13`, `0.155` (the criterion), `0.165` (the
  candidate solve target), `0.18`, `0.20`.
* **modes**: `T0` = hold top-down (`mirror_across_xz(top_down_quaternion("x"))`
  for the left - what `_prepare_two_line_stations` pins, P62 verified this *is*
  the left's calibrated attitude; mirrored for the right); `NAT` =
  `hold_quaternion = None`, the position-only solve the *place* leg runs, i.e.
  "if the staging pose does not care about attitude, what does the arm offer?".
* **the shipped baseline** is measured on the same scene: the calibrated `grasp`
  configuration's own jaw z (that is the left's pre-pose today) and the right
  station's `0.095` solve.

**Criterion for a cell: `residual <= 6 mm` AND `jaw_z_achieved >= belt_top + z -
6 mm` AND every joint margin `>= 0.0 rad`.** The pass set is then read against
the invariant: the candidate is **admissible** iff at least one cell at the
station reaches `jaw_z_achieved >= belt_top + 0.155` with `margin >= 0.02 rad`
(the 0.02 is this phase's robustness floor for a pose held 65 ticks per attempt;
it is *not* P66's 0.05 design bar for a static sweep).

**Falsifier F1 (stops the phase before any battery):** if **neither** mode at the
**left** station reaches `jaw_z >= belt_top + 0.155` with `residual <= 6 mm`,
the station does **not** admit a clearance pre-pose. The written answer is then
that the clearance must come from the **transit path** (a park/transfer bias, i.e.
the arm waits at a clear pose and descends only inside its own lane) or from the
**station geometry**, and **no phase-2 battery is spent** - the map's rows are
the evidence, and the two-line's rate stays untouched.

## 3. The change (phase 1), and how the shipped path stays reachable

One new resolver, `tasks.prepose_clear_resolution(two_line)` (the P87/P88/P89/P91
pattern: one resolution, one print, one manifest field):

| value | meaning |
| --- | --- |
| unset / empty | **the shipped pre-P96 path, bit for bit** while the flip decision is open (`0`); after a *ship* decision it resolves **on for a two-line session** and off everywhere else |
| `0` | off, explicit: the pre-P96 path (`station == pick_y` skips its solve, others solve at `belt_top + grasp_clearance`) |
| `1` | on: **every** two-line station solves its pre-pose at `belt_top + FRUIT_BIARM_PREPOSE_CLEAR_Z` |
| `FRUIT_BIARM_PREPOSE_CLEAR_Z` | the solve height above the belt top, default **0.165**; `< 0.155` or `> 0.25` raises at task construction (a "clearance" pose below the invariant is not a clearance pose, and the phase-0 map's ceiling is 0.20) |

The behaviour when on:

1. `_prepare_two_line_stations` solves **both** stations at the clearance height
   - the left included, which is the whole point (P39: the left station *is* the
     calibrated pick point, so today it has no solve at all).
2. A failed solve at the **left** station is **loud** (`[biarm] station left:
   clearance pre-pose NOT achieved ...`) and is *not* silently replaced by the
   shared grasp configuration: the invariant is then not restored and the census
   will say so. The right station keeps the shipped fallback (its pre-pose is not
   the exposure).
3. One `[biarm] pre-pose` row per station per batch, at the solve, carrying the
   **achieved** jaw height (`jaw_z - 0.0805` = the pad plane) so section 1's
   reading (2) is a log field.
4. **Nothing else moves**: the descent, the hover, the close, the carry, the
   place, the release clock, the feeder, the station selection and the pre-pose
   blend's tick count (45 + 20) are untouched. The pre-pose is a *staging pose*;
   the hover move after it is IK and re-aims as shipped.

The pre-pose is also the pose `_prepared_return` (P32 phase 2, default off) and
`_biarm_hot_hold` (W8-R3 L3, default off) read - they read
`_station_prepose_target`, so they inherit the clearance pose; both are off on
the shipped cell, and neither is re-measured here (named residual).

**Provenance**: a store recorded under a clearance pre-pose is a different branch
- the pre-pose is held for 65 ticks at the start of *every* attempt. The
collector's `collection` block gains `prepose_clear` (resolved 0/1),
`prepose_clear_defaulted` (bool) and `prepose_clear_z` (the height above the
belt). **A manifest without `prepose_clear` predates P96.** The stations
themselves are already carried (`collection.station_l/station_r`), so no
station field is owed; the **pose** is, and that is what these three keys are.

## 4. Phase 2 - the battery

**Cells** (the shipped two-line default, `ATTEMPTS=20`, one claim per run,
instrumentation identical in all four:
`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_PLACE_TRACE=1 FRUIT_FRUIT_TRACE=2500 FRUIT_FRUIT_TRACE_ARM=1`):

| cell | seed | `FRUIT_BIARM_PREPOSE_CLEAR` |
| --- | --- | --- |
| `C5` | 5 | `0` (the shipped branch; must replay `logs/p92/C5.log`) |
| `T5` | 5 | `1` |
| `C6` | 6 | `0` (must replay `logs/p92/C6.log` = P94's `T6`) |
| `T6` | 6 | `1` |

Rationale for the instrumentation: the trace cells are the *only* cells that can
read the invariant, and P95 proved this read set branch-neutral (fruit-only
**970/970**, and the two-arm link read **970/970 / 974/974** on the same seeds).
`FRUIT_CARRY_DIAG` is P83-measured neutral (`D5` = `C5`, 710/710) and
`FRUIT_PLACE_TRACE` is P86-measured inert, so the count/class/interval read comes
from the **same** cells as the census - no second battery, and no cell whose
admissibility is assumed.

**Expectation, registered up front: no treatment cell replays any record.** A
clearance pre-pose is held on every attempt, so the treatment is a **moved
branch** by construction; it is gated on **motion budgets only**
(`105 --min-success-rate 0.0`), and its count is a **draw**, never a rate. The
*control* cells are the ones that must replay, and their replay is what makes the
treatment's difference the lever's.

## 5. Guards and the decision rule

| guard | reading | pass |
| --- | --- | --- |
| **G0** admissibility | the control cells' `[fruit]` streams vs `logs/p92/{C5,C6}.log`, dropping the phase's own diag rows | identical end to end, both seeds |
| **G1** the invariant (primary) | the pre-leg contact census, both seeds | **0 contacts / 40**; and the `<= 6 mm` count lower than the control's |
| **G2** the pose | the `[biarm] pre-pose` rows: achieved pad plane at **both** stations | `>= belt_top + 0.0745` (jaw `>= belt_top + 0.155`), both arms, both cells |
| **G3** no lost placement | placed count per seed and pooled | pooled `>=` control **and** neither seed lower by more than 1 |
| **G4** no new class | the failure-reason keys per cell | the control's key set only |
| **G5** motion + landing | `105` budgets on all four cells (the treatment budgets-only); `FRUIT_PLACE_TRACE`'s `on_belt` on every payload-present release | every descent inside its per-leg budget (the treatment must not add an over-budget leg); `on_belt` **100 %** of payload-present releases, the upstream-lost rows reported separately |
| **G6** delivered side (report, never gated) | interval pooled and per arm, both denominators, wall and `placed/min wall`, `[cycle]` blocks by median | reported; **never** the argument |

**Decision rule.**

* **G1 and G2 pass and G3 passes** -> the invariant is restored without losing a
  placement: **ship** (flip the resolver's two-line default, re-record both
  references from same-batch runs, re-base the acceptance).
* **G1/G2 pass and G3 fails** -> the fix restores the invariant at a placement
  cost: **the owner's decision**. Nothing is flipped; the numbers are published
  with the trade stated.
* **G1 or G2 fails** -> **not adopted**; the phase publishes which clause failed
  and why (the pose is unreachable, or the pads are still in the band), and the
  named next forms are the transit/park bias and the station geometry.
* **F1** (phase 0) fires -> no battery at all; the answer is the transit path.

**What would make this a false positive, named now:** a treatment that "passes"
G1 because the *branch* moved the fruit away (the count read is a draw), or
because the census window shrank (a faster pre-pose ends the blend earlier). The
second is checked by G2 - the pose is a per-attempt log field, not a window
statistic - and the first by reporting the treatment's own attempt/fruit table
next to the count.

## 6. What ships if it ships (the full package, priced before the run)

1. `FRUIT_BIARM_PREPOSE_CLEAR` resolves **on for a two-line session** and off on
   every other path (the single arm, the shared station, the hybrid canary, the
   direct/policy interface and the collector's single-arm mode do not construct a
   two-line session and cannot read it).
2. **Both** motion references re-recorded from same-batch acceptance runs
   (`configs/motion_reference.json` and `configs/motion_reference_twoline.json`
   are the same scenario on this tree; the pre-P96 pair is archived under
   `logs/p96/`), and the acceptance re-based: its own `=0` A/B must reproduce the
   P94 record **8/10 + `fingerprint: matches 30fb99f8`**.
3. **Every two-line store re-baselined**: a shard without
   `collection.prepose_clear` predates P96 and is a pre-clearance pre-pose
   number.
4. The 20-attempt two-line references in `logs/` (P80's seed-5 file, P86's seed-6
   file) are **not** re-recorded - they belong to their own phases' batteries -
   but every post-P96 cell must be gated against a reference of its **own**
   branch, which for a moved branch means budgets only.
5. `scripts/selfcheck.sh` gains a leg pinning the resolver table, the
   single-sited solve, the skip condition, and the seed's own arithmetic.

## 7. The report

`logs/p96/{PREREG.md,PREREG.md5,RESULTS.md}`, the map (`prepose_map.py` +
`prepose_rows.json` + `prepose_map.txt`), the census (`pg_census.py` +
`pg_census.txt`, with the per-attempt pad-gap table), the report (`p96_report.py`
+ `p96_report.txt`) and the four cells' `{log,stamps,budgets}`. Ends with
`scripts/selfcheck.sh`, `scripts/accept.sh`, `scripts/106_index_audit.py`,
`scripts/107_collect_merge_test.py`, the AGENTS/WORKLOG paragraphs and the two
docs that name the success-rate lane (`docs/THROUGHPUT.md`, `docs/LEFT_ARM.md`).
