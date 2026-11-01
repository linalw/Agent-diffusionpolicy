# P89 - the lift raise: the block is exact, the delivery is not, and the class does not improve

Measured 2026-11-01. **Nothing adopted, no default changed** - `FRUIT_SPEED_LIFT`
stays an **off-by-default** cell (P44's S3-v); the phase's gate **failed**, so
`LIFT_TWO_LINE_DEFAULT` is `False` and the shipped tree resolves the 0.30/1.0 cap
on **every** path. What the phase ships is the **instrument**: one resolver
(`tasks.lift_speed_resolution`), the `[biarm] lift profile:` row, the
`physics.lift` manifest block, the `249` selfcheck leg, and the measured arm
reproducible as `FRUIT_SPEED_LIFT=0.37` (which resolves 0.37 / **1.0**).

PREREG `logs/p89/PREREG.md` (**`30d8941c...`**) + one amendment:
`PREREG_A1.md` (**`14c73afd...`**, pinned **while the first cell was still
running**, before any log was compared - G0's replay targets are P88's **C5/C6**
(its place-0.35 cells), not its T5/T6, which carried the place raise).
Cells `logs/p89/{C5,T5,C6,T6}.{log,stamps,driver}` (one claim each,
`logs/p89/run_p89.sh`), read by `logs/p89/p89_report.py` ->
`p89_report.txt`; gates in `logs/p89/gates.sh`.

**This closes the profile-block table.** Release: measured (P86) and shipped
scoped (P87). Place: measured, negative (P88). **Lift: measured here, negative.**
All three blocks of the shipped two-line cell are now priced with the same
instrument and the same read rules (`docs/THROUGHPUT.md`).

---

## 0. The change, and what did not ship

| | PREREG's scoped form | **shipped after the gate** |
| --- | --- | --- |
| `FRUIT_SPEED_LIFT` unset, two-line session | 0.37 / 1.0 (`origin=default`) | **0.30 / 1.0** (`origin=scope-off`) |
| unset, every other path | 0.30 / 1.0 | 0.30 / 1.0 (unchanged) |
| `=0` / `off` | 0.30 / 1.0 | 0.30 / 1.0 |
| `=0.37` (S3-v) | 0.37 / 1.0 | **same** (global, explicit) |
| `=1` / `on` / any other speed | 0.36 / 1.9 (S3) | **same** (S3's measured pair is not moved) |
| `FRUIT_SPEED_ALL=1` (S13) | 0.36 / 1.9 | **same** |
| manifest `physics.lift` | written | **written** (records the shipped 0.30 today) |
| `[biarm] lift profile:` row | prints in a bimanual session | **prints** (says which cap ran) |

The resolver, the scope plumbing and the provenance stay because they are the
measurement's own instruments and the re-entry is one constant
(`LIFT_TWO_LINE_DEFAULT`) plus this gate; the shipped physics is byte-identical
to P88's (proven in §6).

## 1. The mechanism: exact to the profile's own arithmetic

The `grasp_lift` leg is one `jerk_limited` profile. At 0.37 with the shipped
`a_max` 1.0 the chain is `j = min(25, 10a) = 10`, `v = min(0.37, 2a) = 0.37`,
`a = min(1.0, 1.962) = 1.0`, so the duration is
`1.02 * max(1.875 d/0.37, sqrt(5.774 d), (60 d/10)^(1/3))` - and the two regimes
switch at **d = 0.225 m** (0.148 m shipped), which is why the saving is *not* the
1.233x speed ratio.

| seed | control `lift` mean | treatment | **delta** | predicted | control median | treatment | delta (predicted) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 1.684 s | **1.510 s** | **-0.175 s** | -0.177 | 1.770 s | 1.550 s | -0.220 (-0.222) |
| 6 | 1.768 s | **1.595 s** | **-0.173 s** | -0.193 | 1.735 s | 1.540 s | -0.195 (-0.188) |

**P1a passes at both seeds** (the mean is within **0.002 / 0.020 s** of the
prediction built from each control attempt's own printed `grasp_lift` distance;
the band was ±0.08 s). At the reference **d = 0.21 m** the profile is
**162 -> 136 ticks = -26 ticks = -0.217 s**, which is what `physics.lift`
records.

**P1b passes on every leg** (PREREG A1's leg-relative form):

* the per-leg tick count against the profile re-generated at 0.37/1.0 from that
  leg's own printed distance: **median 0.0 ticks, max |5|** (the control's own
  regeneration at the shipped cap reads median 0.0, max |3| - the printed
  centimetre is truncated, so ±4 is the instrument's resolution);
* the leg's `|v|cmd` against that profile's own peak `1.875 d/((ticks-1)/120)`:
  **max |0.013| m/s** (median|v|cmd 0.350 / 0.345 against the control's 0.293);
* the remainder `[cycle] lift= - ticks/120` reads **0.412-0.422 s** in **both**
  arms - the cell moved the profile and nothing else.

**The span moved with the block, and slightly more**: `s/attempt` 9.50 -> 8.90
(seed 5) and 9.10 -> 9.00 (seed 6), i.e. -0.60 / -0.10 s against the block's
-0.175 / -0.173. That is the branch's own acquisition re-draw (P86 §3's
residual), reported, never a second mechanism.

## 2. The gate, seed by seed

`ATTEMPTS=20`, seeds 5/6, the shipped scenario; controls explicit
`FRUIT_SPEED_LIFT=0`, treatments unset (which resolved 0.37/1.0 in this
battery); the release and place cells unset everywhere (their own defaults).

| clause | seed 5 (C5 -> T5) | seed 6 (C6 -> T6) | verdict |
| --- | --- | --- | --- |
| **P1a** block mean | 1.684 -> 1.510 = **-0.175 s** (pred. -0.177) | 1.768 -> 1.595 = **-0.173 s** (pred. -0.193) | **PASS** both |
| **P1b** materialised | ticks median 0.0 (max 5), peak err <= 0.013, remainder 0.412-0.422 | 0.0 (max 3), <= 0.008, 0.413-0.422 | **PASS** |
| **P2** pooled interval | 10.59 -> **13.43 s (+2.83)** | 11.08 -> **12.38 s (+1.30)** | **FAIL** both |
| **P3** landing | 16/16 -> **12/12** on belt | 12/12 -> **14/14** | **PASS** |
| **P4a** new reason key | `grasped, not placed (no note)` x1 | none | **FAIL** (5) |
| **P4b** lift-leg escapes | 2/20 -> **6/20** (left 0 -> **3**) | 5/20 -> **4/20** (left 3 -> 2) | **FAIL** (5) |
| **P4c** all-leg escapes | 2 -> 6 (+4 < 5) | 6 -> 4 | **PASS** |
| **P6** descent budgets | 0/20 over -> **0/20** | 1/20 over (leg 12) -> **0/20** | **PASS** (the C6 leg is the standing seed-6 branch property P86-P88 recorded) |
| P5 (reported) | 16 -> **12** placed; window 5.66 -> 4.47; batch 5.05 -> 4.03; **wall rate 2.95 -> 2.45** | 12 -> **14**; 5.41 -> 4.85; 3.94 -> **4.69**; **2.37 -> 2.74** | one draw, never gated |

**The verdict is the letter: FAIL** - P2 at both seeds, P4a and P4b at seed 5.
Pooled: **28 -> 26 placed of 40**, interval **10.84 -> 12.91 s**, `placed/min
wall` **2.67 -> 2.60** on 629 -> 601 s of wall.

## 3. Why the delivered side did not follow - two different terms

The interval is `attempts/placement x attempt span + idle`, so the two seeds
failed it for **two different reasons** (read rule 5/7):

* **seed 5 - the count.** 16 -> 12 placements while the attempt got *faster*
  (9.50 -> 8.90 s): `attempts/placement` 1.25 -> 1.67. The left arm is the whole
  of it (**9/10 -> 5/10**), and the left's lift legs are where its three new
  escapes are (`left:grasp_lift` escaped 0/10 -> 3/10).
* **seed 6 - the window.** The count *rose* (12 -> 14) and the interval rose
  anyway, because the placements spread over a **wider** window (121.9 -> 160.9
  s). This is P88's seed-6 pattern exactly: `mean_gap = window/(n-1)`, so more
  placements over a wider window reads a worse interval.

So the cell buys **-0.175 s of a ~9 s attempt (1.9 %)** and the delivered side
is dominated by the two terms the lift does not touch. **A null on the interval
was the registered expectation** (PREREG §6: P85's union re-pricing put the lift
at -0.13 s of its -1.00 s); the measured **+2.83 / +1.30 s** is the branch, not
a cost of the faster leg - the *mechanism* is exact and the *span* fell.

## 4. The class: P44's improvement does not reproduce, and this is not P75's site

The phase registered two readings - **"the class improves"** (P44's S3-v dropped
the `force_min == 0` legs 5 vs 7 and added no failure row on the single arm) and
**"the class moves"** (P75: 2 of 6 place-leg escapes fire at the **end of the
lift**). Neither is what the two-line measures:

| arm-seed | lift legs | escaped | never-held | `force_min == 0` |
| --- | --- | --- | --- | --- |
| C5 | 20 | 2 | 2 | 2 |
| T5 | 20 | **6** | 1 | **6** |
| C6 | 20 | 5 | 1 | 5 |
| T6 | 20 | **4** | 2 | 4 |
| **pooled C** | 40 | **7** | 3 | 8 |
| **pooled T** | 40 | **10** | 3 | 10 |

* **The count is a draw, the kind is not.** One seed worse (2 -> 6), one better
  (5 -> 4), pooled **7 -> 10 of 40** - at n = 20 lift legs per arm that is inside
  the class's own spread (the control alone draws 2 at seed 5 and 5 at seed 6).
  **P44's improvement does not transfer**: the two-line's `force_min == 0` legs
  read 8 -> 10 pooled, not down.
* **The escapes are take-off, not the lift's end.** Every escape's `onset_row`
  is **early in its leg** - treatment onsets 1, 2, 2, 2, 11, 42, 21, 15, 5, 9
  against leg lengths of 133-175 ticks (median share **0.05** of the leg; the
  control's median share 0.08 over its 7). P75's signature (a place leg that
  *starts* with one face at `0.00 N` because the payload left at the lift's
  **end**) does not appear: the treatment's **place-leg escapes are 0/27**
  against the control's **1/29**, so no place leg inherited a broken pinch.
  What the cell touches is the **take-off** loaded slide P41/P60/P75 documented,
  and it neither creates nor removes it.
* **The one new reason key** is a single `grasped, not placed (no note)` row at
  seed 5 - the bucket P88's and P81's cells also draw; it counts in P4a's letter.

## 5. What the phase changes in the record

* **The profile-block table is closed.** `release` 1.70 s (shipped trim, P87),
  `place` 3.14-3.19 s (measured, P88, not shipped), `lift` 1.65-1.70 s (measured,
  here, not shipped). Every block has the same instrument (`[biarm] … profile:`
  row + `physics.<block>` manifest + the per-leg tick read) and the same three
  gates (mechanism, delivery, class).
* **The lift's arithmetic**: 26 ticks / 0.217 s at the 0.21 m reference, and the
  regime switch at 0.225 m is why short legs save nothing - **a lever smaller
  than the block it prices**, which is why the delivered side cannot follow it.
* **`[cycle] lift=` is a leg plus a constant** (0.412-0.422 s) in both arms -
  the third block to decompose that way, after the release's fixed clock (P87)
  and the place's `transit + 0.583 s` (P88).
* **Nothing re-baselined**: `configs/motion_reference.json` / `..._twoline.json`
  = **`423896f7`** and `..._single.json` = **`8952c320`** are untouched, and the
  measured arm stays explicit (`FRUIT_SPEED_LIFT=0.37`).

## 6. Admissibility

* **G0 - the resolver is inert when off, and the control is the shipped cell.**
  `C5` is **868/868** `[fruit]` lines byte-identical to `logs/p88/C5.log` and
  `C6` **821/821** to `logs/p88/C6.log` (diag rows and all three profile rows
  dropped, `p89_report.py --same`). The **diagnostic** half of A1 also holds: the
  same control against P88's **T** cells (which carried the place raise)
  **DIFFERS at line 160**, on a `place1` row - so the filter is not hiding the
  physics, it is hiding exactly the rows the phase owns.
* **G1 - motion.** The 20-attempt references in `logs/` are pre-P87-clock
  records, so `190` is **recorded** for all four cells (a treatment is DIFFERS by
  construction) and **P6's per-leg budget** is the substantive check: **0 legs
  over** in C5/T5/T6 and the known seed-6 leg 12 (0.164 vs 0.160) in C6, which is
  the same branch property P86, P87 and P88 recorded. The descent profile was
  **not** re-tuned (AGENTS §2).
* **G2 - the scope's inertness** (the P87/P88 template, all on the **final**
  tree, i.e. with `LIFT_TWO_LINE_DEFAULT = False`):
  * **(a) the single arm**: `FRUIT_BIARM=0 scripts/accept.sh` **346/346 raw**
    `[fruit]` lines identical to `logs/p71/accept_rails_none.log`,
    `fingerprint: matches configs/motion_reference_single.json`, and **0**
    profile rows printed (the accept's own exit is the standing rate-only FAIL,
    6/9 < 75 %, this branch's record since P32).
  * **(b) the shared station** (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`, 4 attempts,
    `unset` vs `FRUIT_SPEED_LIFT=0`): **218/218 identical** with the profile rows
    dropped, and the **clock the same in both** (`--profile`: v_max 0.30, a_max
    1.0, 162 ticks). The raw comparison differs at **one line only** - the row's
    `origin` (`scope-off` vs `explicit`) - which is the label doing its job.
  * **(c) the final tree's default**: a fresh **unset** 20-attempt run (`N5`)
    replays `C5` **868/868** and prints `FRUIT_SPEED_LIFT=0.30(scope-off)` -
    which is what makes "the shipped default is the shipped clock" true after
    the flip.
  Evidence: `logs/p89/{single_accept.*,shared_*,N5.log,gates.out}`.

## 7. Not measured / out of scope

A third seed; a two-line **collection** shard under the cell (the collector
inherits it and would record `physics.lift`); the hybrid canary (it never builds
a `CoopSession`, so the cell has no path there); a saturated machine; the
`grasp_lift` leg's own `a_max`/cone (the cell does not raise the acceleration -
P44 §9 priced that at 0.00 s and transient spent); a **global** default (measured
only as the S3/S13 pair on the single arm, P44).

## 8. The end-of-phase checks on the final tree

* `scripts/selfcheck.sh`: **PASS, 0 failures, 1 skipped** (`logs/selfcheck.log`;
  the new leg is `P89 lift scope`).
* `scripts/106_index_audit.py`: **OK** - every index matches the files it
  describes; `scripts/107_collect_merge_test.py`: **PASS, all 21 checks**.
* `scripts/accept.sh` (the shipped two-line scenario, ten attempts,
  `logs/p89/accept_final.log`): **7/10 = 70 %, `fingerprint: matches
  configs/motion_reference.json`, `190: PASS`** - the shipped branch, unchanged
  by the phase (nothing was flipped, so no reference was re-recorded). Its own
  `[biarm] lift profile:` row reads **`FRUIT_SPEED_LIFT=0.30(scope-off)`**, i.e.
  the shipped acceptance runs the shipped lift clock.
* `logs/p89/gates.sh` -> `gates.out`: every admissibility clause (G0/G1/P6,
  G2a/G2b/G2c) passes; the script's non-zero exit is the **registered verdict**
  (`p89_report.py --blocks` -> the gate FAIL), which is the phase's outcome, not
  a check failure.
* A second same-tree draw at ten attempts (`logs/p89/accept10.log`, run by
  `run_p89_extra.sh`'s default selection) reads **7/10, 9.40 s/attempt, interval
  10.47 s, window 5.73 / batch 4.47 placed/min, `placed/min wall` 2.67, 10/10
  descents inside budget** with the shipped lift row - the shipped cell's numbers,
  reported as a draw, not a rate.
