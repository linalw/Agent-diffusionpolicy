# P58 phase 3c PREREG — cell A‴: the DECIDER (`FRUIT_SUPPLY_BAND_INTERLOCK=0`, clock pair only)

Written **before any run** (2026-10-28), by the delegated lane. Nothing here is a
shipped-default change; no `src/`, `configs/`, `datasets/` or checkpoint write; no
commit. The deliverable is the measurement and its verdict.

## 0. Why this cell exists

Two readings of the same three cells are still standing, and they predict
opposite flips.

* **Reading (i) — the interlock is load-bearing.** A′ (`logs/p58/p3a/`, triple,
  `_BAND_MAX=3`) reads `on_belt` **9** / `skipped` **41/36/39** against the
  control's **5** / **104/107/105**; the control has *no* clock pair and *no*
  interlock. A″ (`logs/p58/p3b/`, `BAND_MAX=4`) reads **11** / **8/4/9**. On this
  reading the interlock is what carries the stock and the scheduler, and the
  flippable unit is the **triple**.
* **Reading (ii) — the interlock's stock is transit.** Oracle 1's composition
  re-derivation (`.slim/deepwork/p58-continuous-supply.md`, "Oracle 1 re-review
  (attempt 2)") shows the identity **`on_belt = admitted + below_window`**
  exactly, with the *catchable* window **falling** 2.60 -> 2.02 and
  `window == 1` tripling 4/45 -> 12/45, while the below-station share rises
  **0.20 -> 5.20**. A″ recovers only to **2.38 / 9/45** at a *worse* below-station
  share **6.24**. On this reading the interlock parks bodies where the selector
  cannot use them and the stock number is being satisfied by transit.

The confound is the **clock pair**: the control lacks `FRUIT_FEED_CADENCE` and
`FRUIT_DIRECT_FEED` as well as the interlock, so no existing cell separates
"feeder live during the attempt" from "release paced on the approach band". This
cell is that separation.

**Question: is the band interlock load-bearing, or is the clock alone enough?**

## 1. The cell (one arm, one claim per run, ~28 min)

**Cell A′ verbatim, minus the interlock** — the shipped station-window pacing
(`_queue_depth` vs `queue_max`, `FRUIT_QUEUE_MAX` default **6**) with only the
clock pair added:

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1
FRUIT_FEED_CADENCE=1 FRUIT_DIRECT_FEED=1
scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
    --presentation direct --episodes 15 --seeds <77|101|202>
```

Seeds **77 / 101 / 202** (the A′/A″/control seeds, so the contrast is paired by
seed); logs `logs/p58/p3c/A3_<seed>.log`; one `scripts/154_claim_run.sh` claim per
run (`RUN_LIMIT=1800`).

### 1.1 The single-variable discipline (registered)

* **ONE change against A′: `FRUIT_SUPPLY_BAND_INTERLOCK` 1 -> 0.** Everything else
  is A′ verbatim, including the harness block (`HEADLESS=1 FRUIT_CAMERA_RES=240,424
  FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1`, `execute_steps=4`,
  `ddim=16`, no `--record`).
* **`=0` is written explicitly and is the shipped default** (`fruits.py:940`:
  `os.environ.get("FRUIT_SUPPLY_BAND_INTERLOCK", "0") == "1"`). It is set rather
  than omitted only so the claim's env print records it; the code path is
  byte-identical to unset (`_interlock_depth` -> `_queue_depth`,
  `_interlock_max` -> `queue_max`).
* **`FRUIT_SUPPLY_BAND_MAX` is NOT set** — with the interlock off its only
  consumer (`_interlock_max`) returns `queue_max`, so the cap is inert here. It is
  omitted deliberately so no reader can attribute a difference to it.
* **`FRUIT_DIRECT_CONTINUOUS` is NOT set** (the shipped per-pick interface — this
  cell family's whole point; G2).
* **`FRUIT_SUPPLY_TARGET_FROM` is NOT set** (the substitute lever; G4).
* Deliberately unset (the shipped `direct` defaults): `FRUIT_POLICY_TRIGGER_ACQ`
  (P54 resolves it on for `direct`), `FRUIT_ARM_PARK` (P43 resolves `back`), and
  the P40/P41 knobs (`FRUIT_REGRASPS`/`FRUIT_SUBSTEPS`/
  `FRUIT_FINGER_STIFFNESS`/`FRUIT_FINGER_MAXFORCE`).

### 1.2 The controls are free and paired (nothing is re-run for them)

| arm | env (relative to the shipped direct defaults) | `on_belt` med | `skipped` final | `window` | `window==1` | below-window / block | starves |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **control** (phase-1 A, `logs/p58/p1/A_*.log`) | none | **5** | 104/107/105 | **2.57** (`{1:4,2:20,3:11,4:10}`) | **4/45** | **0.20** (9/45) | 0/42 |
| **A′** (`logs/p58/p3a/`) | clock pair + interlock 1 (`BAND_MAX=3`) | 9 | 41/36/39 | 2.02 (`{1:12,2:20,3:13}`) | 12/45 | 5.20 (234/45) | **1/42** |
| **A″** (`logs/p58/p3b/`) | clock pair + interlock 1 + `BAND_MAX=4` | **11** | 8/4/9 | **2.38** (`{1:9,2:18,3:10,4:8}`) | **9/45** | **6.24** (281/45) | 0/42 |
| **stack B** (phase-1 B) | clock pair + interlock + `FRUIT_DIRECT_CONTINUOUS` | 10 | 40/36/38 | 2.09 (`{1:10,2:21,3:14}`) | 10/45 | 5.40 (243/45) | n/a (`[cont]`) |

The Oracle's control cell prints **0.18**; the same instrument on the three
control logs reads **0.176** if the aborted 5-pick run is pooled (9/51) and
**0.20** at 45 blocks. Both are the same read and neither changes the ordering;
this report quotes **0.20 (9/45)** and states the denominator.

## 2. Endpoints (registered before the run)

Unit = one pick = one `[rl] episode ... success=` row. 3 seeds x 15 = **45 picks**;
boundaries = **42**. A run whose pick count is not 15 is reported and flagged,
never pooled.

### E1 — starved feed rounds (count 0 = pass)

Instrument (A′'s, unchanged): `sel_gap_k = 120*(t_{k+1} - t_k) - ticks_k` over
consecutive `[bed-sel] attempt` rows.

* `t=` is 2-dp, so the read carries **±1.2 ticks**; the realizable grid is
  `140 + 30k`, and **139-141 is the quantisation of a 140-tick boundary — not a
  failure** (as instructed).
* *Pass bar:* **zero** gaps `>= 169` in all three runs (169-171 = one starved
  30-tick feed round). `>= 200` is the P58 F2 class: reported **as such** and a
  FAIL.
* Reported: the pooled starve count with seed, boundary index and the adjacent
  `[bed-sel]` row's `on_belt`/`live`/`admitted`/`window`/`skipped`; the gap
  distribution (min/median/max, `>140` count); the **139-141 count** (the
  control and A″ both read 42/42); and the `starved_reset` count (the reset's own
  "no graspable fruit reached the selection window" retry path, which is a
  *different* starvation event and is reported, not pooled into E1).

### E2 — the stock and the scheduler

* **every run's final cumulative `skipped` <= 60**, **and**
* **pooled `on_belt` median >= 8** (per-run medians reported).

Calibration: control 5 / 104-107-105 (both clauses fail); A′ 9 / 41-36-39; A″ 11 /
8-4-9.
**`on_belt` alone is not the stock endpoint** (Oracle 1): the report prints the
per-block identity **`on_belt = admitted + below_window`** as the instrument's
validity check, and `admitted` median beside `on_belt`.

### E3 — `window >= 1` at 45/45 **and the composition**

1. **`window >= 1` at 45/45** selections (`[bed-sel]` `window=`, pooled). A row
   count other than 45 is reported and explained before E3 is read.
2. **Composition** (the registered bars are the A″ numbers):
   * pooled **`window` mean >= 2.38** (the cap-4 cell);
   * **`window == 1` <= 9/45**;
   * the **below-window (past-station) share**: `[bed-sel]` candidate rows whose
     reason contains **`below window`**, counted **per `[bed-sel]` block** and
     pooled (total / blocks), with the per-run split and the ratio to all
     candidate rows. Reference: control **0.20**, A′ **5.20**, A″ **6.24**,
     stack **5.40**.
   The first two bars gate B1 (§4); the below-window share is **reported** and is
   the diagnostic that says *where* the stock sits — a `window` >= 2.38 met with a
   below-window share **below** A″'s 6.24 is a better composition at equal depth,
   and one **above** it means the depth was bought the same way the cap-4 cell
   bought it.

### E4 — no new failure reason

Exactly `scripts/113_rl_report.py`'s `reasons()` normalisation (the whole
`notes=[...]` text with every `[-+0-9.]+` run replaced by `#`), baseline = phase
1's arm A **plus** the P43/P54 baseline (`logs/p43/p3/*.log`, `logs/p54/p1/*.log`)
**plus** A′ and A″. *Pass bar:* `keys(A‴) ⊆ keys(A_p1) ∪ baseline`. Reported in
both directions, raw fragments listed, **and** `keys(A‴) - keys(A″)` (this knob's
own signature, if any). A new key is a FAIL even if the rate is fine
(P38/P41/P58 precedent).

### Reported only (no gate)

placed split (per run and pooled, `arm=left/right`; **no rate claim** — AGENTS §2,
the left's count is the closed grip/`cnp` class), wall per pick, simulated
span/ticks per pick, `[feed]` rows (`updates=`/`ticks=`/`stride=`), `admitted`
median, `lag` median, `rebased`/`dropped`, `live` median.

## 3. Registered predictions (mechanism reads, checked in the report)

Written before the run; they attribute a result, they do not gate it.

* **P1 (the clock pair runs).** `[feed]` rows **14-15 per run** (one per attempt
  that reaches a release), as in A′/A″.
* **P2 (the station window is the binding pacer).** With interlock off the pump
  is paced by `_queue_depth` vs `queue_max=6` over `along ∈ [-0.05, +0.45]`, a
  span whose catchable part is the top **5 cm** (the 0.399 m catch floor to the
  0.45 m window edge — the P56 aperture). Prediction: `skipped` sits **above**
  A″'s 8/4/9 and at least A′-like (`> 39` in at least two runs), because the
  pump's slot re-bases when the window fills. *Falsifier:* every run's
  `skipped <= 60` with `on_belt` median >= 8 — then the interlock is **not**
  load-bearing for the scheduler.
* **P3 (the interlock owns the past-station composition).** The below-window
  share falls **materially below A″'s 6.24** (predicted < 3.0), because the
  station window counts the past-station bodies (`-0.05..+0.45`) and therefore
  blocks before they accumulate, while the approach-band depth
  (`+0.35..spawn_y`) does not. *Falsifier:* a below-window share >= A″'s 6.24 —
  then the composition is not the interlock's and that is recorded as such.
* **P4 (the wall follows the live body count).** wall/pick **<= 35.40 s** (A″'s)
  if the belt carries fewer live bodies than A″'s 12; reported only.

## 4. Decision rule (pre-committed, from the Oracle 1 re-review)

Read in this order; the **first** clause that applies decides.

* **B1 — the clock pair is the flippable unit.** **E1, E2, E3 and E4 all pass**
  **and** the pooled `window` mean **>= 2.38** -> **flip `FRUIT_FEED_CADENCE` +
  `FRUIT_DIRECT_FEED`** (the clock pair) for `direct`; the **interlock stays off**
  (documented as unmeasured-here / net-negative on this scenario).
* **B2 — the interlock is load-bearing.** **E2 fails** (either clause: stock or
  skips lost without the interlock) **or** A‴ **starves at least as often as A′**
  (i.e. **starves >= 1/42**) -> the **triple (+ `BAND_MAX=4`)** is the flippable
  unit, with **A′'s one starve carried as a recorded deviation** (the A″ reading
  of §0 stands as the caveat).
* **B3 — no flip.** **E2 holds and starves = 0 but the window does not reach 2.38
  or `window == 1` exceeds 9/45** -> no flip; report and stop (all knobs off;
  `--continuous N` stays opt-in).
* **B3 covers every remaining outcome** (E3's `window >= 1` clause failing at a
  selection, E4 firing a new reason, or any combination not named above):
  **no flip; report and stop.** No branch is invented after the data.

The three numbers that decide it, quoted in the report: **(1)** the starve count
(`>= 169` rows over 42 boundaries), **(2)** `on_belt` median and the per-run final
`skipped`, **(3)** the pooled `window` mean with `window == 1`.

## 5. Falsifiers (each reported; a firing falsifier voids or bounds the cell)

* **G1** a run does not deliver 15 picks (wedge / timeout / RuntimeError) ->
  report, **retry once on the same seed**, record the retry.
* **G2** `[cont]` rows appear in any log -> not the shipped interface; **void**
  (`FRUIT_DIRECT_CONTINUOUS` unset).
* **G3** tree pins move between the first and last run, **or** differ from A′'s
  header (`Ap_header.txt`) -> the runs are not one cell against A′/A″; **void**.
* **G4** `FRUIT_SUPPLY_TARGET_FROM` appears in a log -> two variables; **void**.
* **G5** a `starved_reset` (the reset's own retry) is **not** a void and **not**
  an E1 event: it is counted and reported beside E1 (it says the boundary feed
  round could not find a candidate at all, which is the class under test).

## 6. Read rules carried into the report

1. **Branches, not rates.** Placed counts are counts. A‴ vs A′/A″ is a
   **mechanism** contrast (starve, stock, skips, window, below-window share),
   never a throughput delta.
2. **The instrument is inside the contrast.** `FRUIT_BED_DIAG=1` is on every arm
   in the family (control, A′, A″, A‴), so the census is symmetric.
3. **One cell, three seeds.** The statement is the per-run consistency read
   (does the direction hold 3/3?); no confidence interval is claimed from 45
   picks for a mechanism endpoint.
4. **E1's power is small.** A′'s event is **1 in 42** (2.4 %); a null bounds the
   rate at <= 6.9 % at 95 %. E1's pass is necessary, not sufficient — that is why
   the composition bars gate B1 beside it, and why B2 also fires on E2.
5. **`on_belt` alone is not a stock endpoint** (Oracle 1). The report must print
   `admitted` and the below-window share beside it, and must verify the identity
   `on_belt = admitted + below_window` per block.
6. **No default flip, no `src/` edit, no commit.** This cell is a measurement.

## 7. Files

`logs/p58/PREREG_A_APRIME3.md` (this file), `logs/p58/run_aprime3.sh` ->
`logs/p58/p3c/A3_batch_outer.log`, `logs/p58/p3c/A3_{77,101,202}.log`,
`logs/p58/p3c/A3_header.txt`, `logs/p58/p3c/A3_tree_md5_after.txt`,
`logs/p58/A3_report.py` -> `logs/p58/A3_report.txt`,
`logs/p58/A_APRIME3_RESULTS.md`.
