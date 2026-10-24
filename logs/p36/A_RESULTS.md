# P36 phase 2 — the 2x2: the park's image vs the proprio (the record)

Measured 2026-10-24, one claim 19:39-21:04 (`logs/p36/A_driver.log`), 12
simulator sessions, **`RUN_LIMIT=25200`**, batch wall **5146 s** (85.8 min;
7.1 min/run-cell). **Default off, no shipped default changed**, no commit. The
pre-registration is `logs/p36/PREREG.md` (sections 3, 5, 6, 8a and 10 are the
Gate-1 amendments, made **before** the batch). Tree pins at batch time
(`logs/p36/A_tree_md5_before.txt` = the batch header): `rl_env.py`
**aa54b022** (the phase-1 spoof + the `store_guard_reason` refusal),
`tasks.py` cdde6bd2, `configs/arm_parks.json` 42ab4fb7,
`configs/proprio_spoof.json` 374b88a7, `configs/motion_reference.json`
25ade92b, checkpoint `moe_v13s` `61da390a`. Files after the phase
(`logs/p36/A_tree_md5_after.txt`, batch time): `scripts/219_p36_cells.sh`
**f000f4cb** (**e19fa36d** during the batch: identical except the print-only
`grep` fix of section 7), `scripts/220_p36_report.py` **72f22dd5**,
`scripts/218_proprio_spoof_check.py` **1c584d7f**,
`logs/p36/smoke_check.py` 2591cc65 (unchanged), `logs/p36/ood_proprio.py`
**084c93da**, `logs/p36/power_check.py` **888440eb**. **The Gate-2 edits**
(section 7) move `scripts/218_proprio_spoof_check.py` to **95a3fe28**,
`scripts/219_p36_cells.sh` to **2fe202d7** (the driver md5 header line),
`scripts/220_p36_report.py` to **42dd8339** and `logs/p36/ood_proprio.py` to
**d011f6cf**; `rl_env.py` and `configs/proprio_spoof.json` are unchanged by
Gate 2.

## 1. The batch

The pre-registered design, executed: **4 cells x 3 runs x 15 episodes = 180**
(seeds 77 / 101 / 202, policy seed 11), one cell per simulator session, all
inside **one** `154_claim_run.sh` claim. The cell order is the **randomised
rotation** (`P36_ORDER_SEED=20261024`, base `2 3 1 4`): run 1 `2 3 1 4`, run 2
`3 1 4 2`, run 3 `1 4 2 3` - every cell in three distinct positions. The driver
refuses to start below a 7200 s claim limit (H1) and the report refuses a batch
that is not 3 complete runs of 15 (H2).

| cell | the inactive arm / the obs | the role | right n | left n |
|---|---|---|---|---|
| 1 | `ready` / live `ready` | the control (the P35 C-batch scenario + the four diags) | 27 | 18 |
| 2 | `back` / live `back` | the lever (the P35 reproduction) | 30 | 15 |
| 3 | `back` / written `ready` | the image-only probe | 28 | 17 |
| 4 | `ready` / written `back` | the proprio-only probe | 30 | 15 |

The right share is 115/180 = 64 % (P35: 68 %). Cell 1's right n is 27, not 30,
because the arm follows the fruit's grade and the per-cell fruit mix differs -
which is what the class-standardised read exists for.

## 2. The manipulation check (S1-S4, from the batch's own rows)

**PASS, 180 episodes, no separate instrumented run.** Everything below is
`scripts/220_p36_report.py`'s `[2]`, `logs/p36/A_ab/A_report.txt`.

| check | result |
|---|---|
| **S1** cells 3/4, right-active: `applied=1`, `side=left`, `idx=0,2,4,6,8,10,12`, the `obs` vector == the file's, `drift > 0.30` | **28/28, 30/30** (the substitution bites: drift 0.60) |
| **S1** the counterfactual rows: cells 1/2 (both arms) and cell 4's left-active `applied=0` with `pre_md5 == obs_md5` | **57/57, 18/18, 15/15, 15/15** |
| **S1** cell 3's left-active rows: the right `ready` vector, a no-op, drift <= 0.02 | **17/17** (drift 0.006) |
| **S1c** the probe's vector vs the *physical counterpart's* live pose (`q` at the first non-stale call; per-episode max, bar 0.02 rad) | cell 3 vs 1 **28/28, median 0.0020 / max 0.0020**; cell 4 vs 2 **30/30, median 0.0040 / max 0.0040** |
| **S2** `rest_same=1` (the 25-D with the 7 zeroed, before/after) | **180/180** |
| **S3** the parked arm holds the cell's pose (`park` == ready/back), `m1_hold_ok=1` | **115/115** right-active (left-active rows, the right arm at `ready`: 65/65, reported) |
| **S4** the image follows the *arm*, not the spoof: the inactive arm's pixels inside the target's disc bbox, right-active episodes with a band call | cell 1 **27/27** `arm_px > 0`; cell 2 **30/30** `= 0`; cell 3 **28/28** `= 0`; cell 4 **30/30** `> 0` |
| **S4** the per-call census | cells 1/4 **670/670** and **724/724** calls with `arm_px > 0`; cells 2/3 **0/741**, **0/680**; the no-op side (inactive = right at `ready`) **0/1555** |

The S4 rows are the point of the design: **cell 3's image is the parked one
although its proprio claims `ready`, and cell 4's image is the shipped one
although its proprio claims `back`** - the two channels moved independently, and
the frames say so. The 0.02 rad aggregation is defined per episode
(PREREG section 3): the written vector against the counterpart cell's median live
pose, and it reads 0.002-0.004 rad, i.e. 1-2 % of the 0.603 rad shift.

## 3. The result

Right-arm carried class (**the primary**), per cell:

| cell | role | right ok / carried / no-grasp (n) | carried rate [Wilson 95 %] | effect fraction | band |
|---|---|---|---|---|---|
| 1 | the control | 7 / **18** / 2 (27) | **0.667** [0.478, 0.814] | 0.00 (reference) | - |
| 2 | park / park (the lever) | 29 / **0** / 1 (30) | **0.000** [0.000, 0.114] | **+1.00** | - |
| 3 | park image / ready proprio | 26 / **0** / 2 (28) | **0.000** [0.000, 0.121] | **+1.00** | **full** |
| 4 | ready image / parked proprio | 13 / **17** / 0 (30) | **0.567** [0.392, 0.726] | **+0.15** | **none** |

**The main effects (exact two-sided Fisher, the pre-registered alpha):**

* **image** `((r2+r3)-(r1+r4))/2`: cells {2,3} **0/58** vs {1,4} **35/57**,
  effect **-0.617**, **p = 8.8e-15**;
* **proprio** `((r2+r4)-(r1+r3))/2`: cells {2,4} **17/60** vs {1,3} **18/55**,
  effect **-0.050**, **p = 0.687**;
* **interaction** `(r2-r3)-(r4-r1)` = **+0.100**, within-stratum permutation
  **p = 0.581** (exact enumeration 0.587; 5000 draws, seed 20261024,
  `|T*| >= |did|`) - the pre-registered **redundancy/synergy descriptor only**,
  reading 0 = additive: on its own terms the conjunction **adds nothing
  measurable under the ceiling** (the image cell is already at 0/28 carried, so
  the descriptor cannot exclude a contribution above it, and it is not a second
  channel test).

**The reading: IMAGE-BORNE.** Cell 3 (the parked image with an in-support ready
proprio) reproduces **100 %** of the park's conversion (0/28 carried against the
control's 0.667); cell 4 (the shipped image with the parked proprio) sits at the
control level (+0.15, band **none**) - and that 0.15 is noise (see §4). The
pre-registered decision matrix's **first row** (the image cell converts, the
proprio cell does not) names the **image channel**; *which* image statistic does
the work is not identified here (§5).

**Consistency, not a test** (per run, right arm): the image contrast is negative
in **3/3** runs (-0.631 / -0.611 / -0.625) and the proprio contrast in **2/3**
(-0.169 / -0.056 / +0.125). Per cell per run, cells 2 and 3 read **exactly 0
carried** in every run (0/12, 0/10, 0/8 and 0/10, 0/9, 0/9), cell 1 reads
8/10, 6/9, 4/8 and cell 4 6/13, 5/9, 6/8 - so the pattern is not one run's
accident. Cell 4's effect fraction per run is +0.42 / +0.17 / **-0.50**: across
runs it is indistinguishable from no effect (the pooled +0.15 is the average of
that).

## 4. The composition and the noise floor

**Class-standardised** (direct standardisation to cell 1's right-arm species
mix; coverage 1.00 / 0.85 / 0.93 / 0.96): crude -> standardised **ok** 0.259 ->
0.259, 0.967 -> 0.957, 0.929 -> 0.940, 0.433 -> 0.403; **carried** 0.667 ->
0.667, 0.000 -> 0.000, 0.000 -> 0.000, 0.567 -> **0.597**; the **standardised
fractions** are therefore **+1.00 / +1.00 / +0.10** (cells 2/3/4). The mix does
not make the result: cell 4 moves *up* to 0.597 when standardised and the image
cells stay at 0.

The per-class table (right arm, `A_report.txt` `[5]`) shows the conversion is
class-wide: every species with a cell-1 episode carries 1-4 times in cell 1 and
0 times in cells 2/3 (cell 3 has no peach episode and a single pear; cell 4's
carried mass is orange 6/6, apple 4/6, lychee 2/5, peach 2/3, pear 2/2,
strawberry 1/5, tomato 0/3).

**The noise floor - the left arm, a no-op in all four cells.** Its carried rate
is **0.889 / 0.800 / 0.882 / 0.733** (16/18, 12/15, 15/17, 11/15): the left arm
is at the *ceiling* of the carried class on this interface (1-4 ok per cell), so
it is a **one-sided** noise floor, not a symmetric null. Read honestly: the same
contrasts computed on it are image **+0.030**, proprio **-0.119**, interaction
**+0.073**, with a cell spread of **0.156**. **The proprio main effect (-0.050)
is smaller than the no-op population's own proprio contrast (-0.119)** - a null
of the size seen here is what this batch's noise produces without any treatment.

**Secondary** (right arm): the composite (carried + no-grasp) 20/27, 1/30, 2/28,
17/30; pooled ok 7/45, 32/45, 27/45, 17/45; the cycle median 1867/1796/1781/1850
ticks and ok-only 1756/1796/1781/1768 (flat, <= 5 %); **model calls per attempt**
63.0 / 60.5 / 60.0 / 60.5 (medians, ranges 29-91) - the probe cells cost no extra inference;
**no new failure reason** in any cell (the notes sets are subsets of cell 1's
after `113`'s number normalisation).

## 5. What this does and does not license

* **The park's win travels down the image channel.** *Which* image statistic
  carries it is **not separated**: the fruit's **sightline** (the P35 occlusion
  census: the arm's pixels inside the target's disc bbox 100 % -> 0 %, the
  band's fully-hidden calls 68.1 % -> 0 %) is the leading **unseparated**
  candidate, because the probe moves the parked arm's silhouette as well as the
  fruit's pixels.
* **The image-only cell is synthetic** (the parked image with the ready
  proprio): it names the channel, it does not ship (PREREG section 8). The
  shipping path remains a **recollection's own A/B**, where the park fixes both
  channels at once. This read is **consistent with** that spend (a recollection
  that fixed only the pixels would be expected to keep the win; one that fixed
  only the proprio would not) - it does not substitute for the recollection's
  own A/B, and the recollection's A/B is the measurement that decides.
* **The proprio null is weak evidence on its own**: cell 4 writes a proprio whose
  **j2 (-0.978 rad) is the one channel outside both reference populations'
  observed ranges** ([-0.777, +0.175] of `r9_awr`, [-0.792, +0.175] of
  `demos_v11`; PREREG section 8a), so the probe presents an out-of-range input.
  The 4-5-sigma summary is a **mixture statistic** (the pooled population
  includes the left-active episodes) and is not what the read rests on. It is
  *not* the whole argument either: the cell-4 response is at the control level
  *and* inside the batch's no-op noise (0.15 vs the left's 0.12), so the honest
  statement is "the image carries it; no proprio contribution is measurable at
  this n", not "the proprio is proven irrelevant".
* **N = 3 runs is a probe, not a rate.** The **WS-4.2 convention** (N = 5 runs x
  15 episodes, interleaved, per-carried-class endpoint) governs any *adoption*
  or rate claim; this 2x2 is a mechanism probe on 180 episodes with ~30
  right-arm episodes per cell, so the recollection's own A/B must be run at
  **N = 5**.
* **The named next step**: separating the sightline from the arm-as-context needs
  the P34-B/P35 occlusion instruments run as their own design (a new phase), not
  this read - the probe's image channel is a static scene change.
* **Cell 1 is not the shipped default** (the P35 scenario + `TRIGGER_ACQ=1` +
  the four diags): its carried rate 0.667 is this batch's control, not a
  shipping claim.

## 6. No-harm

* **The scripted acceptance**: `logs/p36/A2_accept.log` (the gate output) +
  `logs/p36/A2_accept_raw.log`; its **`[fruit]` stream is byte-identical** to the
  P35 record (`logs/p35/C_accept_no_harm.log`, 376 lines) - see
  `logs/p36/A2_accept_identity.txt`. It reads **6/10 + `fingerprint: matches
  configs/motion_reference.json`** (the pre-existing P32 pear-on branch, so the
  rate-only `exit=1` is expected).
* **`scripts/selfcheck.sh`**: **PASS, 0 failures, 1 skipped** (the motion-budget
  leg, supplied by the acceptance); the `proprio spoof check` leg now also pins
  the **store guard** (`record` + spoof refused) offline.
* The tree md5s are unchanged before/after except the phase's own files
  (`A_tree_md5_before/after`).

## 7. Post-batch note (print-only and analysis-side)

Five changes were made **after** the batch and are recorded here so the read's
provenance is legible; none of them is a data-dependent choice:

1. `scripts/219_p36_cells.sh`'s per-cell summary line used
   `grep -c '\[rl\] episode [0-9]*:'`, which also counts the env's
   `[rl] episode N: <fruit> grade=... y=...` presentation row, so it printed
   `episodes 30` for a 15-episode run. **The report's parser was never affected**
   (it requires `success=...`, `113`'s regex). The grep was tightened to
   `'\[rl\] episode [0-9]*: .* success='` after the batch; **no number in this
   document comes from it**. The same file's header now pins the **driver
   itself** (`md5sum "$0"`), so a future batch records which driver ran it.
2. The Fisher helper's **absolute** `+1e-12` tolerance (inherited from `113`'s
   era) counted every table below 1e-12 as "at least as extreme", reading
   `8.1e-13` on a table whose exact tail is `8.8e-15`. It is a *correctness*
   fix (a relative tolerance), verified against an independent `Fraction`
   enumeration of the same table, and pinned by the self-test. The proprio p is
   unchanged (0.6866); the decision is unchanged either way. **This is the
   disclosed post-batch item 8 of `PREREG.md` section 10** - the file's 21:20
   mtime is that edit, and items 1-7 there are the pre-batch amendments.
3. The **per-class table** (PREREG section 4's composition read) was missing
   from the first renderer and was added before the report was read; it is a
   pre-registered endpoint, not a new one. Cell 4's standardised carried rate
   and the reading do not depend on it.
4. `logs/p36/ood_proprio.py` (edited 19:43, i.e. four minutes **into** the
   batch) is **data-independent**: it reads the two reference stores
   (`datasets/rl_rollouts/r9_awr`, `datasets/demos_v11`) and never the batch's
   outputs, so its 19:43 edit could not see an outcome. Its summary now also
   prints the **range verdict** (how many of the 7 channels sit outside the
   reference store's *observed range*, not only beyond 1.7 sigma) and its
   READING rests on j2's range violation; re-run against the same two stores,
   the numeric table is **byte-identical** to the 19:43 output.
5. `logs/p36/power_check.py` is **design-only** (the power of the
   pre-registered design at p1 = 0.49; no outcome data), so its 19:43 mtime
   carries no data dependence either.

The Gate-2 record fixes (the channel-vs-sightline wording, the OOD summary
restated on j2's range, the interaction's descriptor status, the manipulation
gate's count invariance, the N=3/N=5 convention) are recorded as item 9 of
`PREREG.md` section 10; **no number and no decision changed**.

## 8. Files

`logs/p36/A_ab/` (12 logs, `A_header.txt`, `A_driver.txt`, `A_report.txt`,
`raw/`), `logs/p36/A_driver.log`, `A_tree_md5_before.txt` /
`A_tree_md5_after.txt`, `A2_accept*.log`, `A2_accept_identity.txt`,
`A2_selfcheck.log`,
`ood_proprio.py` + `ood_proprio.txt`, `power_check.py` + `power_check.txt`,
`PREREG.md` (sections 3/5/6/8a/10 amended pre-batch; items 8/9 of section 10
post-batch, disclosed above), `P1_IMPL.md` (phase 1),
`scripts/219_p36_cells.sh`, `scripts/220_p36_report.py`,
`scripts/218_proprio_spoof_check.py`, `src/fruit_sorting/rl_env.py`
(`store_guard_reason` + the guard).
