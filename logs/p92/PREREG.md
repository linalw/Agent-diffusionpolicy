# P92 PREREG — the scenario-side loss: the delivered-x top of the supply band

**Pinned before any run.** md5 in `logs/p92/PREREG.md5`. Census that chose it:
`logs/p92/CENSUS.md` (from `logs/p92/census.py` → `census.txt`; offline, no
simulator, the records only).

## 0. What the census says, in one paragraph

The shipped two-line cell's 40 distinct attempts (seeds 5 and 6; every other
same-tree log is a byte-identical replay of one of them) read **28 placed =
70 %** and **12 failures**, split **9 `cnp` (75 %) + 3 never-held (25 %)**, with
**0 `fell off the line`**, **0 lost slots** (every run ran its full 20 attempts),
**1-2 `diverted`** (book-keeping: a *pool slot* retired after two failed
attempts, not an attempt class) and **no other class**. The `cnp` class is the
closed loaded slide (`logs/p42/SIM_LIMIT.md`): **counted, not chased**. The
never-held class is the only scenario-addressable one, and it is *exactly* the
set whose `dynamic catch-up: residual` exceeds the 6 mm tolerance: **3/3 failed
vs 0/37** at or below it (residuals 87.6 / 251.0 / 480.6 mm). Two of the three
sit at the **delivered x = 0.386 / 0.391 m**, i.e. at or past the record's
**0.39 m clean lateral edge** (`logs/r10/A_RESULTS.md`, P48: `|x| >= 0.390` is
6/6 failed), and the delivered x spans **0.1998-0.3908 m against a designed
0.20-0.36 m band** - the *top* overflows the designed band by 31 mm while the
*bottom* has **zero** events (the delivered minimum is 0.1998 m, 20 mm above the
left arm's 0.180 m admission floor).

**So P38b's registered-not-run lever is at the wrong end for this corpus.** That
lever bought margin for a *low* tail (`logs/p38/P1_RESULTS.md`: a 0.237 m floor
against a -0.057 m excursion). This scenario has **no low-tail events at all**
in 40 attempts, and the only two x-side failures are at the **top**. This phase
registers the same *kind* of lever - a margin purchase - at the end the census
actually shows.

## 1. The change (one line, no code)

```
FRUIT_SUPPLY_X_MAX=0.33        # shipped 0.36 (fruits.SUPPLY_X_MAX)
```

The supply's lateral band becomes **x = 0.20-0.33 m** (a 13 cm band instead of
16 cm). `FRUIT_SUPPLY_X_MIN` stays at the shipped 0.20.

**Why this is a clean, single-variable manipulation.** `respawn` draws
`x = uniform(x_min, x_max)` - one RNG draw whose *value* the bounds map
affinely and whose *count* they do not change, and no code branches on x
(`fruits.py:1417-1426`). `_release_clear` applies its 0.08 m rule in the
*along* direction only on the wave/scatter path (`x is None`), so the release
schedule cannot move either. The treatment is therefore **the identical draw
stream, laterally compressed by 0.8125**: same species, same diameters, same
grade, same release times, same along positions, same seed - only the lateral
position differs. That is the cleanest A/B this scenario admits, and it makes
the *paired* read by attempt slot meaningful for as long as the branches track.

**Manipulation check (built in, not inferred):** the `[supply] ... lateral
x=0.20-0.33 m` build row, plus the delivered-x distribution per arm. The
treatment's **delivered** maximum must be <= 0.362 m (the shipped band's
measured top offset is +31 mm: designed 0.36 -> delivered 0.391).

## 2. Endpoints

**Primary (a class count, not a rate): the never-held class over the pooled
40 attempts.** Shipped **3** (seed 5: 2, seed 6: 1). The class is read from the
attempt's own `[carry]` row plus its result row (`census.py`'s rule: no pinch
ever - `contacts@onset == 0`, `force@onset == 0.00 N`, `fmax == 0.00 N` - and
not placed).

**Prediction, stated before the run:**
* seed 5: never-held **2 -> 0** (both are presented at x 0.386/0.391, i.e.
  designed ~0.355/0.360, excluded by the 0.33 top);
* seed 6: never-held **1 -> 1** (its event is a **cross-belt flick**, not an x
  tail: `close: fruit drifted 379 mm off the pick centre (cross-belt)` with a
  58.15 N / 99.1 mm-span dry close, at x = 0.273 - mid-band);
* pooled **3 -> 1**; placed **28 -> 29-30** (the two removed presentations
  re-draw at x <= 0.33 and place at ~the cell's base rate, so the expected
  gain is ~1.5, not 2).

**Secondary (read, not gated on its own):** the placed count per seed and
pooled; the class-standardised placed rate at the control's own species x arm
mix; the inter-placement interval (**pooled and per arm**) with **both
denominators** (placement window and batch span) and the **wall** column
(`logs/p80/stamp.py` stamps, `placed/min wall`); the `cnp` class count (a
guard); the landing (`FRUIT_PLACE_TRACE` `on_belt` on every payload present at
the release); the motion budgets.

## 3. Guards (all must pass)

* **G1 the closed class must not rise**: `cnp` pooled <= 9 (seed 5 <= 2,
  seed 6 <= 7). A rise cancels the adoption even if the primary passes.
* **G2 the landing**: every payload-present release lands `on_belt=True`
  (`release_bottom >= 0`; the upstream-lost rows are reported separately, as
  P86/P87 do). The change does not touch the place leg, so any regression here
  is a branch accident and must be named as one.
* **G3 the motion budgets**: `scripts/190_twoline_gate.sh` on each cell with
  `-m 0.0` (see G5) - every descent inside its per-leg budget, the carry cone
  reported (not gated on the dynamic line), the lurch inside 0.291 m/s.
* **G4 no new failure reason**: the notes' key set must stay inside the
  control's (`fruit did not follow the gripper` only).
* **G5 the gate is budgets-only for the treatment, by construction.** A supply
  change moves the scenario, so the treatment's fingerprint **DIFFERS by
  construction** and is gated on budgets only (`105 --min-success-rate 0.0`);
  the *control* cell must match `configs/motion_reference_twoline.json`'s
  attempt-count rule - it is a 20-attempt cell, so its reference is
  `logs/p80/motion_reference_twoline_p80_20.json` (seed 5) and
  `logs/p86/motion_reference_twoline_C6_20.json` (seed 6) - **and** must replay
  the P91 control byte-for-byte on the `[fruit]` stream (dropping this phase's
  no new rows - there are none).
* **G6 no starvation**: every cell runs 20 attempts with zero lost slots; the
  `no eligible fruit` poll count is reported, not gated (it is a wait, not a
  loss).
* **G7 the tree is inert with the knob unset**: `scripts/selfcheck.sh` PASS,
  and `scripts/accept.sh` on the shipped tree unchanged (`fingerprint: matches`,
  its `[fruit]` stream byte-identical to the P87/P89 record).
* **G8 for a supply change**: `python3 scripts/211_bed_audit.py` PASS/OK.

## 4. Decision rule (fixed now)

**Adopt only if all of:**
1. the pooled never-held class falls (**3 -> <= 1**) **and** neither seed rises;
2. the placed count does not fall at either seed (28 -> >= 28 pooled, and no
   seed below its control);
3. G1-G8 all pass.

Otherwise **not adopted** and the numbers are published as a negative.

**What this rule cannot do, said up front.** The count is a **draw**: the same
control swings **16 -> 12** placed between these two seeds (and 16 -> 10 in the
pre-P87 clock, P80/P84), so no rate delta here is a rate. The primary is
therefore a **class count**, and with 3 events in the control a *perfect*
conversion is **3 -> 0**, which is Fisher p = 0.12 at n = 40 - **informative as
a mechanism and not as a rate**. The phase is registered to measure *whether
the class's x-side mechanism is real on this interface*, not to certify a
success-rate gain. If it converts, the shipping path is a re-baseline of every
supply-dependent artefact (both motion references, every store), which this
phase will price and **not** execute.

## 5. Falsifiers (any one kills the lever as stated)

* **F1** the treatment's delivered x maximum exceeds **0.362 m** - the band did
  not take effect, so nothing is measured.
* **F2** the never-held class does not fall (**3 -> 3**, or rises).
* **F3** the placed count falls at a seed with the classes otherwise unchanged
  (the truncation cost supply/geometry).
* **F4** a `cnp` rise above the G1 bound, or a new failure reason.
* **F5** a motion-budget failure or a landing regression on a payload-present
  release.
* **F6** the control cell fails to replay the P91 record (the tree moved; then
  no comparison is admissible and the phase stops).

## 6. Scope, provenance, and what would be re-baselined

* The change is the **supply geometry for every scripted path** (the band is
  global, not two-line-scoped): if adopted it moves the single-arm line, the
  acceptance's scenario, the two-line scenario and every store. That is why it
  is measured with the env knob first and **`configs/` is untouched** until the
  rule passes; adoption owes `configs/motion_reference{,_single,_twoline}.json`
  re-records from same-batch runs plus a `supply.x` block in the manifests
  (there is none today: the manifests record `supply.scatter/patch/wave` but
  **not** `x_min/x_max`, so a store under a different band is currently
  indistinguishable - named as a follow-up, not built here).
* The direct/policy interface (`SortingRLEnv`) builds its own supply profile and
  reads the same `SupplyPlan.from_env`, so it would inherit the band; no direct
  number is measured in this phase and none is claimed.
* Nothing here writes `src/`, `configs/`, `datasets/` or a checkpoint.

## 7. Cells (one claim per run, 20 attempts, the P91 instrumentation on all)

| cell | env | role |
| --- | --- | --- |
| `C5` | `ATTEMPTS=20 SEED=5` | the tree check: must replay `logs/p91/C5.log` |
| `T5` | `+ FRUIT_SUPPLY_X_MAX=0.33` | the treatment, seed 5 |
| `C6` | `ATTEMPTS=20 SEED=6` | the tree check: must replay `logs/p91/C6.log` |
| `T6` | `+ FRUIT_SUPPLY_X_MAX=0.33` | the treatment, seed 6 |

Instrumentation, identical on all four cells and identical to P91's:
`HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_PLACE_TRACE=1`.

## 8. Statistics, pre-committed

* The primary is a **count of a named class** at a fixed attempt budget; the
  units are attempts and the pooled n is 40. Fisher's exact test is quoted for
  transparency only - **the decision is the count**, per section 4.
* The interval is read **per seed and pooled**, on **both denominators**, with
  the wall column; a supply change is not expected to move any of them and the
  pre-committed reading is "flat within the branch spread, and any movement is
  a branch draw, not the lever".
* The paired read is by **attempt slot** (same seed, same release schedule by
  construction, section 1): the same species and diameter at the same slot is
  the pair; a slot whose branches have diverged keeps the standardised read
  only.
