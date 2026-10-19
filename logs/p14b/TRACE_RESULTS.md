# P14-B: the trace-run analysis — the three seed runs (60 attempts), the phase-localized grip loss, and the branch the data selects

Status: **offline, read-only analysis** (branch `p-supply`, 2026-10-19). The three trace runs were
already on disk (`logs/p14b/10_seed11_trace.log`, `11_seed5_trace.log`, `12_seed23_trace.log` +
`traces_s11/`, `traces_s5/`, `traces_s23/`); this lane ran **no simulator**, wrote nothing outside
`logs/p14b/`, and did not touch `src/`, `scripts/`, `configs/`, `datasets/`, `Paper/`, or the
running P14-A canary chain. All writes are under `logs/p14b/`. Tree pins as read: `tasks.py`
`810658b802d22bbd63013726fc78af81`, `fruits.py` `d28546d26137d4540421caa7fa34a139`.

The design this analysis executes is `logs/p14b/GRIP_DIAGNOSTIC.md` §2 (the trace run's
pre-registration: the metric, the readouts, the decision tree, the falsifiers F1–F5); the method is
the W5-C corpus mining of §1.5 (`trace_mine.py`). The run logs and the traces pair 1:1 (60/60) and
the runs **replay the mass base byte-identically** (§1.2) — the corpus analysed here *is* the mass
base of `logs/p12a2/`, now with per-tick geometry.

---

## 0. The answer in one screen

* **The separator holds and the no-grasp class is disjoint.** Total hand-frame payload drift (the
  design's metric, from the last `hold` row): **ok 0.0–27.2 mm (n=45, median 1.5) vs no-grasp
  294.8–95 403.7 mm (n=8, median 1 506)** — no overlap; the *carried* (placed=False) class
  **3.4–1 407.3 mm** overlaps both because its loss is a different one (the carry/place escape).
  The W5-C corpus's separator (0–20.5 vs 313–1 992 mm) reproduces on the mass base with the bands
  shifted by scenario (§5).
* **The first departure is dominated by the first probe cycle — with the hold as the walk's
  origin.** By the pre-registered 2 mm rule, of the 8 no-grasp failures **4 first cross in probe
  block 1, 2 in the hold** (the payload already out at the probe's first sample), 1 in the
  takeoff, 1 in the takeoff→carry gap. But on 3 of the 5 B1 attempts the payload had already
  **walked 32–55 mm during the hold** (a loaded capture transient at ~belt speed with the force
  still 3.4–15 N), so the honest localization is **hold + probe-1**, not the probe alone.
* **The loss completes (sustained F<0.5 N ∧ contacts==0):** hold 2, probe-1 2, **re-seat window 2**
  (both with the payload already 22.4/25.8 mm out at the window's near edge), the takeoff→carry
  gap 1, the carry 1 (no-grasp, n=8); the carried class completes in the carry (4), the gap (1),
  or beyond the trace (2, the place).
* **No re-seat window ever released a held payload.** Across the whole corpus (60 attempts, 22
  untraced windows) the only re-seat-window "loss" is one **ok** attempt (s11 t04: 0.9→12.5 mm,
  still gripped, placed); the windows instead show **re-grabs** (a13's window 1→2 re-seated a
  4.3 mm-out payload at F=19.97 N; s11 t20's and s5 t16's windows re-grabbed 26.9→11.6 and
  8.4→12.0 mm). **F1 is confirmed: the re-seat-floor lever (`FRUIT_DYNAMIC_REGRASP_FLOOR`) is dead
  as the initiator.**
* **The branch the data selects: the close/hold grip-margin family (the capture transient), with
  the probe's shape as the secondary** — per the pre-registered mapping the **R11-B C1 family
  (`FRUIT_CLOSE_LOAD_RATE`) first**; the belt-break/takeoff branch holds only for the B2 minority
  (2/3); the carry/place branch for the carried class. The trace cannot choose among the
  close-side actuators (C1 vs the squeeze family vs the freeze criterion) — it localizes.
* **The trace is run-neutral**: all three trace runs' `[fruit]` lines are **byte-identical** to the
  mass base (950/1047/1084 lines, exact); the trace-on branch replays the trace-off record.

---

## 1. The corpus and the pairing verification

### 1.1 The runs

| seed | log | traces | attempts | ok / carried / no-grasp | class split (P10-E rules, re-derived from the traces) |
| --- | --- | --- | --- | --- | --- |
| 11 | `10_seed11_trace.log` | `traces_s11/` (20 files) | 20 | 11 / 2 / **7** | B1 4 (a01 orange, a06 tomato, a08 orange, a13 tomato) + B2 3 (a02 peach, a04 tomato, a07 tomato) |
| 5 | `11_seed5_trace.log` | `traces_s5/` (20 files) | 20 | 17 / 3 / 0 | — (3 carried: tomato, tomato, kiwi) |
| 23 | `12_seed23_trace.log` | `traces_s23/` (20 files) | 20 | 17 / 2 / **1** | B1 1 (a02 strawberry, right) |
| pooled | — | 60 files | 60 | **45 / 7 / 8** | **B1 5 / B2 3** |

The split matches the GRIP_DIAGNOSTIC §1.1 census exactly. Trace-based B1/B2 = the probe-block
count from the trace itself (B1 = 3 probe cycles / 3 regrasp windows; B2 = 1), which agrees with
the P10-E log rules on every attempt (the 3 B1s in seed 11 are the 3-regrasp attempts; the 3 B2s
are the no-regrasp attempts with the 1.77–1.95 s grip phase).

### 1.2 The trace-on run replays the mass base (the no-harm re-test of §2.3)

```
10_seed11_trace.log vs logs/p12a2/10_seed11_mass.log: exact-identical=True n=950  [fruit] lines
11_seed5_trace.log  vs logs/p12a2/11_seed5_mass.log : exact-identical=True n=1047 [fruit] lines
12_seed23_trace.log vs logs/p12a2/12_seed23_mass.log: exact-identical=True n=1084 [fruit] lines
```

Every `[fruit]` line (including the `sim=` values) is byte-identical; the only extra lines are the
`[trace]` dump/flush rows (and the ~20 empty `logs/dynamic_trace_NN.json` files the flush leaves).
So the trace's per-tick readback did **not** move the branch on this scenario — the W5-A evidence
generalizes to the mass base, and the corpus analysed here is the mass base itself. (Wall overhead
of the trace: +8 s/+8 s/+7 s per run, ~1.5 %; the simulated timeline is identical.)

### 1.3 The pairing (60/60 verified)

The dump sequence `NN` in `trace_NN_<arm>_scripted_<outcome>.json` is the global **completion
counter**, so the NN-th file pairs with the NN-th `[biarm] result` line. Verified per attempt:
the file's `arm` == the result's side (60/60); the file's `outcome` == `placed` (60/60: ok ⇔
placed=True; fail covers both grasped=False and placed=False); the `[run] attempt N` window
contains the trace rows' t-range (60/60); the `[run]` and `[biarm]` lines agree on
species/grasped/placed/lift (60/60). The full verification table is
`trace_p14b_tables.txt` §"seed s11/s5/s23".

Two pairings that could have gone wrong and did not: the two `[run]` attempts numbered out of
completion order (attempt numbers are global **start** order: left starts attempt 2 while right is
still on attempt 0) — the window containment resolves them; and the `[carry]` rows are paired
per arm by rank (the k-th `grasp_lift` row of a side = that side's k-th attempt in start order),
which matches every trace's carry block (`clean_slip_max` cross-check in §3.1).

---

## 2. The method (per the design's §2.4, as implemented)

* **The metric.** Per attempt, the payload's displacement in the hand frame,
  `drift(t) = |hand_rel(t) − ref|` in mm, `hand_rel = Rᵀ(fruit − jaw)`; **`ref` = the LAST `hold`
  row** (never the `grip` row — its `hand_rel` is junk, `fruit=rest` at its call site). The
  **total** = the max over the attempt (the hold segment included, so a pre-probe onset is
  visible); the **hold walk** = the drift change across the hold segment (measured from the last
  close row, the freeze); the **probe-1 lift** = the fruit's z rise over the first probe block.
* **The phases** (as the code emits them): descent ×1, catchup ×N, close ×84, hold ×24 (every 2nd
  tick), grip ×1 (junk), `takeoff_probe` ×60 per probe cycle, takeoff ×54 (the belt-break ramp),
  carry ×N (the `grasp_lift` leg).
* **The untraced windows.** The probe cycles are separated by **101-tick (0.842 s) untraced
  re-seat windows** (the two re-seat loops carry no trace call), and there is a **0.78–1.01 s
  untraced gap between the takeoff's last row and the carry's first row**. The probe→probe and
  probe→takeoff t-jumps are the re-seat windows; a B1 attempt therefore has 3 probe blocks and
  3 windows (the third ends at the takeoff's first row).
* **The first departure** = the first post-`ref` row with drift > 2 mm (the W8-B crossing scale),
  with its bracket (the last row ≤ 2 mm before it): same phase ⇒ inside that phase; different
  phase ⇒ inside the untraced gap between the two rows. The two cases where the payload is
  already out at the probe's first sample (no in-phase predecessor) are labelled **hold (walk
  pre-probe)** — the W5-C convention (cfg3 t09's "true onset is the hold").
* **The release** = the first post-freeze row whose contact is out for ≥ 4 consecutive rows
  (`force < 0.5 N ∧ contacts == 0`) — the completion event; the row before it is the near edge.
* **The tooling** (all read-only, under `logs/p14b/`): `trace_p14b_analysis.py` →
  `trace_p14b_tables.txt` (the pairing verification, the per-attempt tables, the phase tables,
  the distributions, the brackets, the per-failure decompositions, the W5-C comparison);
  `master_table.md` (the 60-row master table); `curves/<seed>_trace_NN_*.csv` (the per-row drift
  curves, 60 files: row, phase, t, drift_mm, force, contacts).

---

## 3. The results

### 3.1 The 60-row master table

(`first departure (design rule)` = the pre-registered first >2 mm row, with the two pre-probe
cases labelled; `release` = the sustained contact loss, `gap->` = the release is bracketed to the
untraced window before that row.)

<!-- master table -->
| # | seed | file | arm | out | cls | blocks | total mm | hold walk mm | probe1 dz mm | first departure (design rule) | release (sustained out) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | s11 | 01_left_fail | left | fail | B1 | 3 | 1723.2 | 38.1 | 0.9 | takeoff_probe t=20.3 d=2.2 | takeoff_probe t=20.4 dfz=43 |
| 2 | s11 | 02_right_ok | right | ok | ok | 1 | 0.5 | 0.0 | 8.6 | - | - |
| 3 | s11 | 03_left_fail | left | fail | B2 | 1 | 344.8 | 0.7 | 7.1 | takeoff t=36.2 d=2.4 | gap->carry t=37.5 dfz=87 |
| 4 | s11 | 04_right_ok | right | ok | ok | 2 | 12.8 | 0.6 | 2.5 | takeoff_probe t=39.9 d=12.5 | takeoff_probe t=40.0 dfz=12 |
| 5 | s11 | 05_left_fail | left | fail | B2 | 1 | 338.4 | 0.0 | 7.8 | takeoff->carry t=54.1 d=69.5 | gap->carry t=54.1 dfz=70 |
| 6 | s11 | 06_right_fail | right | fail | carried | 1 | 31.8 | 2.6 | 8.8 | takeoff_probe t=60.4 d=2.7 | - |
| 7 | s11 | 07_left_fail | left | fail | B1 | 3 | 95403.7 | 31.9 | -0.5 | hold (walk pre-probe) t=64.2 d=3.2 | hold t=64.2 dfz=23 |
| 8 | s11 | 08_right_fail | right | fail | B2 | 1 | 294.8 | 1.8 | 5.2 | takeoff_probe t=77.9 d=2.1 | takeoff_probe t=78.2 dfz=9 |
| 9 | s11 | 09_left_fail | left | fail | B1 | 3 | 1924.9 | 54.8 | -1.2 | hold (walk pre-probe) t=84.1 d=4.0 | hold t=84.0 dfz=37 |
| 10 | s11 | 10_right_ok | right | ok | ok | 2 | 10.0 | 0.9 | 0.0 | takeoff_probe t=91.6 d=2.2 | - |
| 11 | s11 | 11_left_ok | left | ok | ok | 1 | 12.9 | 12.8 | 13.8 | - | - |
| 12 | s11 | 12_right_fail | right | fail | carried | 1 | 234.9 | 5.8 | 13.1 | takeoff_probe t=118.5 d=2.3 | carry t=121.2 dfz=34 |
| 13 | s11 | 13_left_ok | left | ok | ok | 1 | 0.8 | 0.8 | 10.1 | - | - |
| 14 | s11 | 14_right_fail | right | fail | B1 | 3 | 1458.1 | 1.6 | 0.0 | takeoff_probe t=136.2 d=2.0 | gap->takeoff_probe t=138.7 dfz=250 |
| 15 | s11 | 15_left_ok | left | ok | ok | 1 | 10.0 | 9.8 | 15.2 | - | - |
| 16 | s11 | 16_right_ok | right | ok | ok | 1 | 0.0 | -0.0 | 38.2 | - | - |
| 17 | s11 | 17_left_ok | left | ok | ok | 1 | 0.0 | 0.0 | 8.4 | - | - |
| 18 | s11 | 18_right_ok | right | ok | ok | 1 | 18.7 | -0.0 | 7.0 | takeoff->carry t=178.9 d=8.7 | carry t=179.0 dfz=15 |
| 19 | s11 | 19_left_ok | left | ok | ok | 1 | 5.8 | 0.0 | 8.5 | takeoff->carry t=181.0 d=3.9 | - |
| 20 | s11 | 20_right_ok | right | ok | ok | 2 | 27.2 | 0.0 | 0.6 | takeoff_probe t=193.5 d=2.3 | - |
| 21 | s5 | 01_left_fail | left | fail | carried | 1 | 3.4 | 3.3 | 14.4 | - | - |
| 22 | s5 | 02_right_ok | right | ok | ok | 1 | 3.3 | 1.3 | 25.7 | - | - |
| 23 | s5 | 03_left_ok | left | ok | ok | 1 | 0.6 | 0.4 | 5.5 | - | - |
| 24 | s5 | 04_right_ok | right | ok | ok | 1 | 1.4 | 1.2 | 6.1 | - | - |
| 25 | s5 | 05_left_fail | left | fail | carried | 1 | 281.7 | 5.1 | 17.1 | carry t=56.1 d=2.0 | carry t=56.7 dfz=49 |
| 26 | s5 | 06_right_ok | right | ok | ok | 1 | 0.3 | -0.1 | 5.4 | - | - |
| 27 | s5 | 07_right_ok | right | ok | ok | 1 | 5.1 | 4.6 | 7.8 | takeoff_probe t=72.8 d=2.3 | - |
| 28 | s5 | 08_left_ok | left | ok | ok | 1 | 1.8 | 1.3 | 6.8 | - | - |
| 29 | s5 | 09_left_ok | left | ok | ok | 1 | 4.6 | 3.1 | 16.7 | takeoff_probe t=92.4 d=2.0 | - |
| 30 | s5 | 10_right_ok | right | ok | ok | 1 | 0.4 | 0.1 | 7.9 | - | - |
| 31 | s5 | 11_left_fail | left | fail | carried | 1 | 272.1 | 3.5 | 15.6 | takeoff t=118.3 d=2.4 | carry t=119.9 dfz=35 |
| 32 | s5 | 12_right_ok | right | ok | ok | 1 | 0.8 | 0.2 | 7.0 | - | - |
| 33 | s5 | 13_left_ok | left | ok | ok | 1 | 0.5 | 0.4 | 7.9 | - | - |
| 34 | s5 | 14_right_ok | right | ok | ok | 1 | 0.7 | -0.6 | 5.8 | - | - |
| 35 | s5 | 15_left_ok | left | ok | ok | 1 | 0.4 | 0.0 | 8.4 | - | - |
| 36 | s5 | 16_right_ok | right | ok | ok | 2 | 12.0 | 2.3 | -0.4 | takeoff_probe t=161.0 d=2.1 | takeoff_probe t=161.2 dfz=8 |
| 37 | s5 | 17_left_ok | left | ok | ok | 1 | 7.5 | 6.7 | 21.1 | - | - |
| 38 | s5 | 18_right_ok | right | ok | ok | 1 | 0.1 | -0.0 | 67.5 | - | - |
| 39 | s5 | 19_left_ok | left | ok | ok | 1 | 2.9 | 2.2 | 7.9 | - | - |
| 40 | s5 | 20_right_ok | right | ok | ok | 1 | 0.2 | 0.0 | 7.5 | - | - |
| 41 | s23 | 01_right_fail | right | fail | carried | 1 | 1407.3 | 5.0 | 17.8 | takeoff_probe t=19.2 d=2.2 | gap->carry t=21.1 dfz=1237 |
| 42 | s23 | 02_left_ok | left | ok | ok | 1 | 5.2 | 4.7 | 16.5 | - | - |
| 43 | s23 | 03_right_fail | right | fail | B1 | 3 | 1554.6 | 0.1 | -0.8 | takeoff_probe t=38.5 d=2.1 | gap->takeoff_probe t=39.6 dfz=116 |
| 44 | s23 | 04_left_ok | left | ok | ok | 1 | 4.4 | 3.5 | 14.6 | - | - |
| 45 | s23 | 05_right_ok | right | ok | ok | 1 | 0.0 | 0.0 | 21.0 | - | - |
| 46 | s23 | 06_left_fail | left | fail | carried | 1 | 314.4 | 4.3 | 16.0 | carry t=71.7 d=2.5 | carry t=72.1 dfz=62 |
| 47 | s23 | 07_right_ok | right | ok | ok | 1 | 17.6 | 0.0 | 5.9 | takeoff t=75.2 d=2.0 | carry t=76.6 dfz=12 |
| 48 | s23 | 08_left_ok | left | ok | ok | 1 | 6.3 | 5.4 | 17.2 | - | - |
| 49 | s23 | 09_right_ok | right | ok | ok | 1 | 0.5 | 0.0 | 13.1 | - | - |
| 50 | s23 | 10_left_ok | left | ok | ok | 1 | 0.1 | 0.1 | 6.7 | - | - |
| 51 | s23 | 11_right_ok | right | ok | ok | 1 | 25.1 | 1.6 | 5.0 | takeoff_probe t=117.6 d=2.0 | takeoff_probe t=117.8 dfz=11 |
| 52 | s23 | 12_left_ok | left | ok | ok | 1 | 0.0 | 0.0 | 8.6 | - | - |
| 53 | s23 | 13_right_ok | right | ok | ok | 1 | 10.3 | 0.1 | 5.8 | takeoff->carry t=146.2 d=4.1 | - |
| 54 | s23 | 14_left_ok | left | ok | ok | 1 | 2.3 | 1.9 | 10.7 | - | - |
| 55 | s23 | 15_right_ok | right | ok | ok | 1 | 0.0 | 0.0 | 17.8 | - | - |
| 56 | s23 | 16_left_ok | left | ok | ok | 1 | 1.5 | 0.9 | 7.9 | - | - |
| 57 | s23 | 17_right_ok | right | ok | ok | 1 | 0.0 | 0.0 | 36.2 | - | - |
| 58 | s23 | 18_left_ok | left | ok | ok | 1 | 1.1 | 0.9 | 8.4 | - | - |
| 59 | s23 | 19_right_ok | right | ok | ok | 1 | 0.0 | -0.0 | 23.4 | - | - |
| 60 | s23 | 20_left_ok | left | ok | ok | 3 | 2.5 | 0.1 | 1.6 | takeoff_probe t=212.2 d=2.0 | - |
<!-- /master table -->

Notes on the table:

* **The `release` column fires on 4 ok attempts too** (s11 t04/t18, s5 t16, s23 t07, s23 t11):
  those are transient 4-tick contact gaps that **recover** (the attempt still places) — the ok
  class's marginal grips flicker. The *no-grasp* releases are the ones that never recover (their
  drift then explodes in the carry).
* **The `probe1 dz` is a grip test, not a 6 mm command** (verified in `tasks.py:8600-8650`): the
  probe's aim = the fruit's live position + a 6 mm z-ramp, so a gripped fruit rides the feedback
  up (ok up to 67.5 mm) while a slipping one stays on the belt (dz ≈ 0). The no-grasp B1s read
  **−1.2…+0.9 mm** — the fruit never rises.
* The `[carry]` log cross-check: every trace's carry drift matches the log's
  `[carry] … clean_slip_max` (e.g. a01 1723.2 vs 1683.0 mm, the frame difference = the payload's
  displacement at the leg's first tick; ok attempts 0.0–0.5 vs 0.0–0.2).

### 3.2 The ok-vs-fail separation

| class | n | total drift mm (min/med/max) | >2 mm | hold walk mm | probe1 dz mm |
| --- | --- | --- | --- | --- | --- |
| ok | 45 | **0.0 / 1.5 / 27.2** | 21 | −0.6 / 0.2 / 12.8 | −0.4 / 8.4 / 67.5 |
| carried | 7 | 3.4 / 272.1 / 1 407.3 | 7 | 2.6 / 4.3 / 5.8 | 8.8 / 15.6 / 17.8 |
| B1 | 5 | 1 458.1 / 1 723.2 / 95 403.7 | 5 | 0.1 / 31.9 / 54.8 | −1.2 / −0.5 / 0.9 |
| B2 | 3 | 294.8 / 338.4 / 344.8 | 3 | 0.0 / 1.4 / 2.4 | 5.2 / 7.1 / 7.8 |
| **no-grasp (B1+B2)** | **8** | **294.8 / 1 506.4 / 95 403.7** | 8 | — | — |

Per seed: s11 ok 0.0/10.0/27.2 vs fails 31.8/344.8/95 403.7; s5 ok 0.1/0.8/12.0 vs fails
3.4/272.1/281.7; s23 ok 0.0/1.5/25.1 vs fails 314.4/1 407.3/1 554.6.

**Reading.** The **no-grasp class is disjoint from ok** (≥ 294.8 vs ≤ 27.2 mm — an order of
magnitude), reproducing the W5-C claim on the mass base. The **carried class overlaps both**: its
loss is the W8-B carry/place escape (5 of 7 release in the carry, 2 beyond the trace), and its
in-trace drift can be small (s5 t01, 3.4 mm — the payload never slipped before the place). The
ok band is wider than W5-C's (27.2 vs 20.5 mm) and 21/45 oks exceed 2 mm — the **hold walk is
universal**, not a failure signature by itself; its *magnitude* and its *fate* are the signals.

**The two candidate pre-outcome signals** (per class, §H of the tables file):

* **The hold walk** (the capture transient): ok ≤ 12.8 mm (median 0.2); the three hold-walk B1s
  31.9/38.1/54.8 mm; the other 5 no-grasp ≤ 2.4 mm. So it separates **3 of 8** no-grasp attempts
  at a >2.5× margin (12.8 → 31.9), and it is the B1 majority's initiation.
* **The probe-1 lift** (the fruit's z rise): the no-grasp B1s −1.2…+0.9 mm (the fruit never
  rises); the B2s +5.2…+7.8 and the carried +8.8…+17.8 (the fruit rises — held through the
  probe); the oks −0.4…+67.5 (median 8.4) — **but 5 ok attempts' first probes read ≤ 2.5 mm and
  recovered via a re-seat** (s11 t04/t10/t20, s5 t16, s23 t20: the 2–3-block oks), so a failed
  first probe is not specific to the losses.

### 3.3 The first-departure and release histograms (the failures)

**First departure (the pre-registered 2 mm rule, with the pre-probe cases labelled):**

| phase | no-grasp (8) | carried (7) | all fails (15) |
| --- | --- | --- | --- |
| hold (walk pre-probe) | 2 (a06, a08) | 0 | 2 |
| probe block 1 | 4 (a01, a07, a13, strawberry) | 4 (t06, t12, s23 t01, s23 t03) | 8 |
| takeoff | 1 (a02) | 1 (s5 t11) | 2 |
| gap takeoff→carry | 1 (a04) | 0 | 1 |
| carry | 0 | 2 (s5 t05, s23 t06) | 2 |
| none (≤2 mm) | 0 | 1 (s5 t01) | 1 |

(The all-fails column includes the carried class's benign 2.0–2.7 mm walks — the 2 mm threshold
fires on 12 ok attempts too, so the rule localizes rather than separates.)

**The release (the sustained contact loss — where the payload is actually gone):**

| release bracket | no-grasp (8) | carried (7) |
| --- | --- | --- |
| hold | 2 (a06 t=64.18, a08 t=84.03) | 0 |
| probe block 1 | 2 (a01 t=20.36, a07 t=78.20) | 0 |
| re-seat window | 2 (a13 w2→3 t=138.71; strawberry w1→2 t=39.63) | 0 |
| gap takeoff→carry | 1 (a04 t=54.14) | 1 (s23 t01 t=21.09) |
| carry | 1 (a02 t=37.48) | 4 (t12, s5 t05, s5 t11, s23 t06) |
| none in trace (the place) | 0 | 2 (t06, s5 t01) |

### 3.4 The mechanism: the capture transient and the three no-grasp shapes

The trace rows pin the mechanism the aggregate logs could not (§1.2 of the design). At the
freeze (the close's last row) **every attempt's payload is moving at ~0.10 m/s — the belt speed**
(a01 −0.099, a10 −0.101, a06 −0.102 m/s in y). The hold is where the pads must arrest that motion;
whether they do is the ok/fail line:

* **ok**: the payload decelerates to the hand's velocity within the hold; the relative walk is
  ≤ 12.8 mm and stops (a10: 11.2 mm over the hold, then constant through probe/takeoff/carry);
  the force stays ~4 N, the servo does not chase (`trips=0`).
* **Shape A — the hold walk (3/5 B1: a01 orange, a06 tomato, a08 orange)**: the payload walks
  32–55 mm during the 0.4 s hold **with the force still 3.4–15 N** (a loaded slide; the hand also
  translates ~30 mm as the post-descent solver finishes the approach), the force servo chases the
  payload through its **whole range** (`closed=18.0–19.2 mm`, `trips=54–60`), and the contact
  collapses — inside the hold (a06 at t=64.18, a08 at t=84.03, both read F=0/c=0 while the hold
  still has rows) or at the probe's first ticks (a01, F 2.90→0.52→0.00 in 2 ticks). The three
  probe cycles then run with nothing (the drift grows 288→477→648 mm — the fruit riding the belt
  and the servo chasing air).
* **Shape B — the probe's lift (2/5 B1: a13 tomato, s23 a02 strawberry)**: the hold is clean
  (walk 0.1/1.6 mm), the fruit does **not rise with the probe's lift** (dz 0.0/−0.8), the pads
  **pry to their 98–99 mm limit** with force spikes (a13: sep 62→98 mm at 33–88 N in probe 2;
  strawberry: sep 48→98 mm at 17–43 N in probe 1) and the payload walks out (a13 to 22.4 mm,
  strawberry to 25.8 mm — both still single-sided contact); the release then completes across the
  next re-seat window.
* **The B2s (3)**: clean holds, the fruit **rises** with the probe (dz +5.2…+7.8), and the loss is
  later — a02 walks in the takeoff and releases in the carry; a04 (held at 0.0 mm through the
  takeoff, the fruit lifted 29 mm) releases in the untraced takeoff→carry gap; a07 (risen 5.2 mm)
  releases at the probe's end (t=78.20).
* **The carried class (7)**: clean holds, the probe lifts the fruit (+8.8…+17.8), the payload
  holds through probe/takeoff, and the loss is the carry/place (5 in the carry — including s23
  t01, whose 1242.6 mm displacement lands in the takeoff→carry gap — and 2 at the place).

### 3.5 The re-seat brackets (the F1 test)

Every untraced window's near edge (the last row before) → far edge (the first row after) is in
`trace_p14b_tables.txt` §D. The no-grasp windows:

| attempt | window | near edge: drift/F/c | far edge: drift/F/c | verdict |
| --- | --- | --- | --- | --- |
| a01 (B1) | w1 (probe→probe) | 16.0 / 0.00 / 0 | 192.8 / 15.20 / 1 | already out (F=0) |
| a01 | w2 | 288.4 / 18.09 / 1 | 393.7 / 28.94 / 2 | already out |
| a06 (B1) | w1 | 77.6 / 78.85 / 2 | 196.0 / 36.35 / 1 | already out |
| a06 | w2 | 297.6 / 24.37 / 1 | 415.8 / 50.56 / 1 | already out |
| a08 (B1) | w1 | 118.4 / 6.62 / 1 | 249.6 / 30.24 / 1 | already out |
| a08 | w2 | 341.5 / 47.05 / 1 | 441.6 / 45.56 / 2 | already out |
| a13 (B1) | w1 | **4.3 / 0.10 / 1** | **3.0 / 19.97 / 2** | **re-grab** (drift 4.3→3.0, F 20 N) |
| a13 | w2 | 22.4 / 98.52 / 1 | 248.3 / 0.00 / 0 | released in the window (payload already 22.4 mm out) |
| strawberry (B1) | w1 | 25.8 / 36.63 / 1 | 114.7 / 0.00 / 0 | released in the window (already 25.8 mm out) |
| a04 (B2) | (probe→takeoff) | 0.0 / 4.46 / 2 | 0.0 / 4.41 / 2 | held through |
| a02 (B2) | (probe→takeoff) | 1.4 / 5.20 / 1 | 2.0 / 4.66 / 1 | held through |
| a07 (B2) | (probe→takeoff) | 6.7 / 0.00 / 0 | 6.7 / 0.00 / 0 | already out (at the probe's end) |

The ok/carried windows for comparison: the only re-seat-window movement of a *held* payload is
s11 t04 (ok, w1: 0.9/4.30/2 → 12.5/0.80/1 — moved 11.9 mm, stayed gripped, placed); the other
ok windows show re-grabs (s11 t20: 26.9/37.89/1 → 11.6/4.48/2; s5 t16: 8.4/0.00/0 →
12.0/47.44/1) or held-through (s23 t20, s23 t13's 4.1 mm).

**Verdict on the re-seat (F1):** **no re-seat window ever released a payload that was held
(≤ 2 mm, two-sided, ~4 N) at its near edge.** The three B1s' payloads were gone before the first
window; a13's and the strawberry's were already 22.4/25.8 mm out (single-sided, force-spiked)
when their windows started; and the windows re-grab as often as they shear. The re-seat-floor
lever's premise has zero instances. The residual: for the 2 window-bracketed releases, a shallower
re-seat *might* have re-grabbed the partially-out payload (a13's w1 shows a re-grab is possible) —
unproven, and it needs the window's own per-tick rows (a `src/` addition, §2.9 of the design).

### 3.6 The untraced takeoff→carry gap (a new finding)

The design flagged the re-seat windows as the only untraced gap; the trace shows a **second one:
the 0.78–1.01 s between the takeoff's last row and the carry's first row** (no call site). It
hosts **two real releases** — a04 (B2; near edge held 0.0/4.46/2, far edge 69.5 mm out) and s23
t01 (carried; near edge held 2.9/4.00/2, far edge 1242.6 mm out) — and four ok small departures
(s11 t18 0.3→8.7, s11 t19 0.8→3.9, s23 t13 0.0→4.1, s23 t07 2.9→11.8 mm, all placed). So the
gap's shear is real (up to ~12 mm on oks) and its tail owns 2/15 failures. If the takeoff branch
is ever pursued, this window needs a trace call site too.

### 3.7 The curves' summaries

The 60 per-row curves are in `logs/p14b/curves/<seed>_trace_NN_*.csv` (row, phase, t, drift_mm,
force, contacts). Their shapes, per class:

* **ok**: flat (|slope| ≈ 0 through probe/takeoff/carry), with a small hold segment (0–12.9 mm)
  that settles; the max is the hold walk itself.
* **hold-walk B1**: a steady ramp through the hold (slope ≈ 0.08–0.14 m/s ≈ belt speed), then a
  monotone climb through the probe cycles and the carry (the fruit left behind); the force drops
  to 0 within 0–3 ticks of the ramp's end.
* **probe-walk B1**: flat hold, then a step-and-ramp inside probe 1 (the pads prying, sep→98 mm),
  a partial pull-back at a re-grab, and a second ramp; the final fall is a near-vertical step
  (the untraced window) followed by a flat plateau (the fruit on the belt).
* **B2**: flat through hold/probe (the fruit rising with the probe), the departure in the takeoff
  or the takeoff→carry gap.
* **carried**: flat through hold/probe/takeoff, the ramp confined to the carry (or absent — the
  place escapes).

---

## 4. The conditional verdict (the design's decision tree)

**Which branch does the data select?**

* **The re-seat window → `FRUIT_DYNAMIC_REGRASP_FLOOR`: NOT SELECTED.** Zero no-grasp losses
  initiate in a re-seat window; no window ever released a held payload; 3/5 B1s were gone before
  the first window; the 2 window-bracketed releases had already-walking payloads (22.4/25.8 mm,
  single-sided, 36.6–98.5 N spikes); one window demonstrably re-grabbed. **F1 is confirmed** — the
  floor lever is dead as the initiator (it stays, at most, an unproven secondary for the 2
  partially-out cases, and only after the window's own rows exist).
* **The close/hold → the close-side family (the pre-registered mapping's `FRUIT_CLOSE_LOAD_RATE`,
  R11-B C1): SELECTED for the B1 majority's initiation.** 3/5 B1s' payloads walk 32–55 mm during
  the hold *with the force present* and the servo chasing its full range; the class's first
  observable divergence is exactly this capture transient (ok arrests ≤ 12.8 mm, these do not).
  The close-phase *summary* geometry overlaps (the freeze `sep−gap_cmd` 4.5–13.3 vs ok −0.0–14.7;
  the close-start offset 10.7–14.8 vs 8.8–15.5 mm) — consistent with the design's §1.2: the
  actuator is dynamic (the load vs the margin), not a static row.
* **The probe → the probe's shape: the secondary (co-selected for the completion).** 2/5 B1s
  (a13, strawberry) and 1/3 B2s (a07) complete at the probe's lift/end; the probe's lift is a
  genuine grip test (the fruit never rises on any B1). But a failed first probe also occurs on 5
  ok attempts that recovered via a re-seat — the probe's shape acts on an already-marginal grip.
* **The belt-break/takeoff → the takeoff path: the B2 minority only (2/3: a02, a04)** — and note
  a04's release is in the *untraced takeoff→carry gap*, not in the takeoff itself.
* **The carry → the carry family: the carried class (5/7 in the carry, 2/7 at the place)** — a
  different failure (the W8-B carry escape), not the no-grasp class.

**The honest form: the data cannot select a single phase for the no-grasp class — it is
heterogeneous (3 hold-walk B1s + 2 probe-walk B1s + 3 B2s) — but it selects the pre-lift family
(close/hold + probe) over the re-seat branch, and the *initiation* is the close/hold capture
transient for the B1 majority.** The pre-registered lever order therefore is: **(1) the close-side
family — C1 `FRUIT_CLOSE_LOAD_RATE` first, the squeeze-side knobs (unmeasured on the two-line) and
the freeze criterion as its alternatives; (2) the probe's shape (`FRUIT_DYNAMIC_PROBE`/`_TICKS`);
(3) nothing for the re-seat floor.** The trace localizes; it cannot pick among the close-side
actuators (that is an A/B, and C1's own scripted battery read 12/20 vs 13/18 — unconfirmed).

**The falsifiers, as measured:**

* **F1 (the re-seat is not the ejector): CONFIRMED** (§3.5).
* **F2 (the close is not a geometry these rows can see): PARTIAL.** The close-phase distributions
  overlap (as F2 says) and the separation is dynamic; but the "the first-departure phases are the
  same" clause does not obtain (the fails' hold/probe-1 dominance vs the oks' mostly no crossing).
* **F3 (the probe owns it): PARTIAL.** 3/8 no-grasp complete at the probe's lift/end, but 3/5
  B1s' losses precede the probe and ok first probes also fail to lift (5 recovered via re-seat).
* **F4 (the belt-break owns the B2): PARTIAL.** 2/3 B2s (a02 takeoff walk, a04 the gap); a07's
  B2 loss is at the probe's end.
* **F5 (the analysis fails): NOT OBTAINED.** The ok population's drift is small (≤ 27.2 mm vs
  no-grasp ≥ 294.8), and the trace-on run replays the mass base exactly (the NG population is the
  mass base's own).

**Named next items** (in the pre-registered order): (1) a C1 A/B on this battery (or a
squeeze-side A/B on the two-line, unmeasured there) with the **hold walk** and the carried class
as the endpoints; (2) the probe's shape A/B; (3) only if the 2 window-bracketed releases are
pursued: the re-seat trace call site (4 lines, `src/`) — and note the takeoff→carry gap needs its
own call site if that branch is pursued.

---

## 5. The W5-C corpus comparison

Same analysis (`trace_mine.py`), same metric:

| corpus | n | ok drift mm (min/med/max) | fail drift mm (min/med/max) | fail onsets (first-departure phase) |
| --- | --- | --- | --- | --- |
| p14b s11 | 20 | 0.0 / 10.0 / 27.2 | 31.8 / 344.8 / 95 403.7 | carry, takeoff, takeoff_probe |
| p14b s5 | 20 | 0.1 / 0.8 / 12.0 | 3.4 / 272.1 / 281.7 | -, carry, takeoff |
| p14b s23 | 20 | 0.0 / 1.5 / 25.1 | 314.4 / 1 407.3 / 1 554.6 | carry, takeoff_probe |
| w5 cfg0 (shipped) | 10 | 0.0 / 0.6 / 4.6 | 379.1 / 735.8 / 1 092.5 | takeoff, takeoff_probe |
| w5 cfg1 (servo-off) | 10 | 0.0 / 0.7 / 1.5 | 1 158.2 / 1 275.9 / 1 508.3 | carry, takeoff, takeoff_probe |
| w5 cfg2 (fs0+sq0) | 10 | 0.0 / 0.3 / 1.6 | 379.1 / 714.7 / 1 050.3 | takeoff |
| w5 cfg3 (track0.2) | 10 | 0.0 / 1.1 / 20.3 | 313.2 / 758.8 / 1 276.9 | carry, takeoff_probe |
| w5 cfg4 (lock-x) | 10 | 0.0 / 0.2 / 20.5 | 1 068.3 / 1 242.9 / 1 992.0 | carry, takeoff_probe |

**The comparison.** (1) **The same separator**: the per-tick hand-frame drift from the last hold
row separates ok from fail on both corpora, and the no-grasp class is disjoint on both (the new
294.8–95 403.7 vs the W5-C 313.2–1 992.0). (2) **The ranges move with the scenario**: the new ok
band's upper tail is ~7 mm wider (27.2 vs 20.5 — the mass base's hold walk), and the new fail
tail is ~50× longer (the a06 tomato's 95 403.7 mm blow-up; W5-C's max 1 992). Per the design's
§2.9/§1.6, quote each corpus's own range, not the other's. (3) **The onsets differ in mix**: the
W5-C corpus's 15 fails onset hold 1 / takeoff 4 / probe 4 / carry 6 (the dense W3 sheet's carry
escapes dominate), while the new corpus's 15 onset hold 2 / probe-1 8 / takeoff 2 / gap 1 /
carry 2 / none 1 — the mass base's class is the grip loss (early onsets), the W5-C corpus's the
carry escape. **The scenarios differ**: the W3 dense sheet + the W5-C screen configs + the
pre-W7-A tree vs the W6-A patch sheet + `FRUIT_PHYSICS_REAL_MASS=1` + the shipped tree (the
W7-A park gate on). The analysis transfers; the numbers do not.

---

## 6. The limits (honest)

1. **n = 8 no-grasp** (5 B1 + 3 B2), all but one at seed 11. The class is heterogeneous (3
   hold-walk + 2 probe-walk B1s + 3 B2s), and the hold-walk class is left-arm-only (3/3) while
   the probe-walk B1s are right-arm (2/2) — at this n that is **not** a measured arm effect.
2. **The trace's `outcome` field = placed**, so "fail" mixes the no-grasp and the carried (place
   escape) classes; this report separates them. The no-grasp class is the design's target.
3. **The untraced windows bracket, they do not explain.** The re-seat windows (101 ticks) and the
   takeoff→carry gap (0.78–1.01 s) have no per-tick rows; 2 no-grasp releases complete inside the
   former (with the payload already out) and 1 in the latter. The mechanism *inside* them is
   unmeasured.
4. **The reference choice.** `ref` = the last hold row understates the pre-reference walk; the
   hold column (measured from the freeze) catches it. The 2 mm threshold is not a separator by
   itself (it fires on 12 ok attempts and 5 carried); the separation is the magnitude.
5. **One scenario, one tree.** The patch sheet + real-mass physics at the shipped tree; a moved
   branch would still keep the within-run ok-vs-fail comparison valid (both classes measured by
   the same instrumentation), but no cross-run rate is quoted here. The trace was run-neutral on
   this scenario (byte-identical `[fruit]` lines) — that is a measured fact of *this* scenario.
6. **The metric is a displacement, not a force decomposition.** The trace cannot split the walk
   between the belt drag and the hand's own settling motion; the "capture transient" reading is
   the measured relative displacement with the force present, nothing more.
7. **No simulator run by this lane**; the three runs were executed by the P14-B run lane (their
   logs/driver logs are the provenance). This lane read them and wrote only under `logs/p14b/`.

---

## 7. Reproduction and artifacts (all under `logs/p14b/`)

```bash
python3 -B logs/p14b/trace_p14b_analysis.py > logs/p14b/trace_p14b_tables.txt   # the full tables
python3 -B logs/p14b/trace_p14b_analysis.py                                     # also rewrites curves/
```

| file | what it is |
| --- | --- |
| `trace_p14b_analysis.py` | the analysis (pairing verification, the metric, the brackets, the tables, the W5-C comparison) |
| `trace_p14b_tables.txt` | the full output (pairing tables, per-attempt/per-phase tables, distributions, gap brackets, per-failure decompositions, the W5-C comparison) |
| `master_table.md` | the 60-row master table |
| `curves/<seed>_trace_NN_*.csv` | the per-row drift curves (60 files) |
| `TRACE_RESULTS.md` | this report |
| `WORKLOG_entry_trace_analysis.md` | the WORKLOG entry |
| (inputs) `10_seed11_trace.log`, `11_seed5_trace.log`, `12_seed23_trace.log`, `traces_s11/`, `traces_s5/`, `traces_s23/` | the runs (by the run lane) |
| (inputs) `logs/p12a2/{10_seed11,11_seed5,12_seed23}_mass.log` | the trace-off record the runs replay |
| (inputs) `logs/w5/traces_dense`, `logs/w5/30_traces_*` | the W5-C corpus |
| (design) `GRIP_DIAGNOSTIC.md`, `trace_mine.py`, `trace_corpus_summary.py` | the pre-registration + the W5-C tooling |
