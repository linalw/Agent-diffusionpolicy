# P58 phase 3b — cell A″: A′ plus ONE free knob (`FRUIT_SUPPLY_BAND_MAX=4`)

Measured **2026-10-28** on HEAD `fdc65d9` (`rl_env.py` `ddcb7816`, `tasks.py`
`c7eef701`, `fruits.py` `55921c46`, checkpoint `moe_v13s` `61da390a` — **identical
to A′'s header on all 15 shared files**, so this is a pure env contrast). Three
runs, one claim each, wall **1711 s** (`logs/p58/p3b/A2_batch_outer.log`). **No
default flip, no `src/`/`configs/`/`datasets/` write, no checkpoint write, no
commit.** Registered in `logs/p58/PREREG_A_APRIME2.md` (`f70de0a4`) **before the
first run**. Report `logs/p58/A2_report.txt` (`python3 logs/p58/A2_report.py`),
raw logs `logs/p58/p3b/A2_{77,101,202}.log`.

---

## 0. Verdict

**E1, E2, E3 and E4 all PASS. Per the registered rule (§4, first clause) the
triple + `FRUIT_SUPPLY_BAND_MAX=4` is the flippable unit for `direct`: the
continuous episode is not load-bearing, and the per-pick boundary is free at the
higher ceiling.** Both registered predictions about the *mechanism* also hold, so
the pass is attributed rather than merely observed:

* **The cap was the binding term (P1 HOLDS).** `max(window)` **3 -> 4**
  (`window == 4` at **8/45**), pooled `window` mean **2.02 -> 2.38**, `window == 1`
  **12/45 -> 9/45**. No triple run had ever produced a 4 (A′ and the stack both
  max at 3); the control, which has no interlock at all, is 2.60.
* **The starve is gone (E1, P2 HOLDS).** **0 starved feed rounds over 42
  boundaries** (A′: 1), every run **14/14 in 139-141**.
* **A second and larger effect was not in the registration's headline: the
  interlock's release-block counter collapses.** Cumulative `skipped` **41/36/39
  -> 8/4/9** (feed-row sums **31/27/30 -> 5/2/7**), i.e. **~5x fewer slots
  dropped per run**, while stock rises (`on_belt` median **9 -> 11**).
* **The one cost: the wall (P4 FAILS).** **34.07 -> 35.40 s/pick (+3.9 %)** at a
  **flat simulated span** (1 833 -> 1 824 ticks/pick, −0.5 %), i.e. **+4.5 % per
  sim-second** with the band carrying ~2 more live bodies (live median **10 -> 12**).
  This is a **reported** prediction, not a gate: E2's bars are met, and the price
  is the same order the full stack already pays (34.37 s/pick).

| endpoint | verdict | the number |
| --- | --- | --- |
| **E1** zero starved feed rounds (`>= 169` form; 139-141 is quantisation) | **PASS** | **0/42** starves; 42/42 boundaries at 139-141 (per run 14/14); A′ **1/42** |
| **E2** stock + scheduler | **PASS** | `on_belt` pooled median **11** (per run **11/11/11**; A′ 9, stack 10, control 5); final `skipped` **8 / 4 / 9** (bar <= 60; A′ 41/36/39, control 104/107/105) |
| **E3** `window>=1` at every selection | **PASS** | **45/45**; distribution `{1: 9, 2: 18, 3: 10, 4: 8}` |
| **E4** no new failure reason | **PASS** | A″ keys **=** A′ keys (2, identical); new vs phase-1 A + P43/P54 baseline: **none** |
| **P1** the cap binds | HOLDS | max `window` **4**, mean **2.38** > 2.02 |
| **P2** starves 1/42 -> 0/42 | HOLDS | 0/42 |
| **P3** no over-stock | HOLDS | `on_belt` 11 (in 9-11), `skipped` 8/4/9 |
| **P4** wall <= 35.1 s/pick | **FAILS** | **35.40** (+3.9 % on A′), span flat |
| **placed** | reported | **28/45** (left 4/19, right 24/26) vs A′ 24/45 (3/23, 21/22) — **arm mix**, no rate claim |

**Decision:** the registered all-pass condition is **met**, and neither of the
other two branches fires (E1 does not fail, `on_belt`/`skipped` do not degrade).
The caveat that belongs beside it is in §5: **E1's pass is a null at low power**
(0 events where the base rate was 2.4 % is 36 % likely under "unchanged"), which
is exactly why P1's window read and the `skipped` collapse carry the attribution
rather than the count alone.

## 1. The cell (as registered and as run)

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1
FRUIT_FEED_CADENCE=1 FRUIT_SUPPLY_BAND_INTERLOCK=1 FRUIT_SUPPLY_BAND_MAX=4
FRUIT_DIRECT_FEED=1
scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
    --presentation direct --episodes 15 --seeds <77|101|202>
```

**One variable against A′: `FRUIT_SUPPLY_BAND_MAX` 3 -> 4.**
`FRUIT_SUPPLY_TARGET_FROM` is **not set** (G4 clear — it is the substitute lever,
and setting both would have made the starve read unattributable);
`FRUIT_DIRECT_CONTINUOUS`, `FRUIT_POLICY_TRIGGER_ACQ`, `FRUIT_ARM_PARK` and the
P40/P41 knobs are unset (the shipped `direct` defaults; every run prints
`park=back(default)` and `acq=on(...)`).

Construction checks: **15 picks per run** (`{77: 15, 101: 15, 202: 15}`), **0
`[cont]` rows** (G2 clear — the shipped per-pick interface), 15/15 `[bed-sel]`
rows with `patch=on` and `grades=A:0.375,B:0.375,C:0.25` each, **`[feed]` rows
14 / 15 / 15** (seed 77's episode 5 is the `grasped=False` attempt —
`ticks=949` — that ended before its release segment; the same construction note
A′ recorded for its 202 run), **G3 clear** (17 header pins, 0 moved; all 15
shared files identical to A′'s header), all three exits **0**, no wedge, no retry
(G1 does not fire).

Controls are free and paired: **A′** (`logs/p58/p3a/`, the same tree and scenario
at `BAND_MAX=3`) is the paired control; phase 1's arm A (per-pick, no triple) and
arm B (full stack, 15-pick episode) are the calibration points. Nothing was
re-run to produce them.

## 2. The table

Unit = one pick = one `[rl] episode ... success=` row. 15 picks per run, 45 per arm.

| run | picks | placed (left/right) | `on_belt` med | `skipped` final | longest `sel_gap` | wall | s/pick |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A″ 77 | 15 | **9** (1/6, 8/9) | 11 | **8** | 141 | 531.9 s | 35.5 |
| A″ 101 | 15 | **7** (1/8, 6/7) | 11 | **4** | 141 | 543.7 s | 36.2 |
| A″ 202 | 15 | **12** (2/5, 10/10) | 11 | **9** | 141 | 517.6 s | 34.5 |
| **A″ pooled** | 45 | **28** (4/19, 24/26) | **11** | 8/4/9 | **141** | 1593 s | **35.40** |
| A′ (`BAND_MAX=3`) | 45 | 24 (3/23, 21/22) | 9 | 41/36/39 | **170 (1/42)** | 1533 s | 34.07 |
| control (P1 arm A) | 45 | 33 (1/12, 32/33) | 5 | 104/107/105 | 141 (0/42) | 1334 s | 29.66 |
| stack (P1 arm B) | 45 | 30 (3/16, 27/29) | 10 | 40/36/38 | n/a (`[cont]`) | 1547 s | 34.37 |

## 3. The window distribution — the object the cap moves

Pooled over 45 selections (`[bed-sel] window=`):

| arm | distribution | mean | `window==1` | `window>=3` | max |
| --- | --- | --- | --- | --- | --- |
| **A″ (`BAND_MAX=4`)** | `{1: 9, 2: 18, 3: 10, 4: 8}` | **2.38** | **9/45** | 18/45 | **4** |
| A′ (`BAND_MAX=3`) | `{1: 12, 2: 20, 3: 13}` | 2.02 | 12/45 | 13/45 | 3 |
| phase-1 B (stack, `BAND_MAX=3`) | `{1: 10, 2: 21, 3: 14}` | 2.09 | 10/45 | 14/45 | 3 |
| phase-1 A (control, **no interlock**) | `{1: 4, 2: 20, 3: 11, 4: 10}` | 2.60 | 4/45 | 21/45 | 4 |

The window depth is **monotone in the cap**, and the interlock's thinning is only
*partly* the ceiling: at cap 3 the interlock reads 2.02-2.09 against the
control's 2.60; at cap 4 it recovers to 2.38, so **roughly half of the
control-vs-interlock window gap is the cap itself** and the rest is the band
definition. Per run: A″ 77 `{1: 2, 2: 8, 3: 2, 4: 3}` (mean 2.40), 101
`{1: 2, 2: 5, 3: 5, 4: 3}` (2.60), 202 `{1: 5, 2: 5, 3: 3, 4: 2}` (2.13) — the
direction holds **3/3**.

## 4. The larger effect: `skipped` collapses ~5x

The `[bed-sel] skipped=` column is the **cumulative interlock/scheduler drop
counter** (`fruits.py`'s `supply_skipped`: a release blocked by the line-full
interlock, or a slot whose due fruit was delivered late). At cap 3 the band sits
**at or above its ceiling most of the time** — `window` max 3, `admitted` median
4 — so the block fires almost every pick: **41 / 36 / 39** per run. At cap 4 it
barely fires: **8 / 4 / 9** (the `[feed]` row sums say the same thing: **31 / 27
/ 30 -> 5 / 2 / 7**). The already-differing counter at attempt 0 (A″ 0, A′ 1) says
the block was binding from the first release, i.e. this is not a drift.

So the `_BAND_MAX = 3` ceiling was doing **two** things at once, and A′'s
registration only named the first: it thinned the station window *and* it was
continuously re-basing the release clock (~2.4 dropped slots per pick). The
starve A′ measured is the second effect's rare visible tail. This is the P33
aperture reading ("the aperture is a stock-depth ceiling") reproduced on the
single-arm direct line, at the ceiling's own number.

## 5. What this does and does not show

* **It does show** the cap is the binding term (P1's 4-class `window` signature,
  3/3 runs), that the boundary starve is gone under the `>= 169` read (0/42),
  and that stock and scheduler are at or better than the stack's level
  (`on_belt` 11 vs 10, `skipped` 7 vs 38) **without** the multi-pick episode.
* **E1's pass alone is a weak null.** A′'s event rate was 1/42 = 2.4 %, and
  `P(0 events in 42 | rate unchanged) = 0.36`. The count is necessary, not
  sufficient; the attribution rests on P1 + the `skipped` collapse, which are
  the same mechanism measured twice.
* **There is no same-boundary replay.** The branch diverges at attempt 1 (A″
  takes `strawberry@0.575`, A′ `apple@0.607`), so A′'s starved boundary 8 -> 9
  does not exist as such in A″; the read is the aggregate + the mechanism, never
  a per-boundary before/after.
* **The wall is the price and it is real** (P4 FAIL): **+1.33 s/pick (+3.9 %)**,
  with the span flat (1 824 vs 1 833 ticks/pick) — so it is **per-sim-second**
  (+4.5 %: 0.01941 vs 0.01858 s/tick), consistent with the deeper band carrying
  ~2 more live bodies (live median **12** vs 10; the association over the four
  configurations is monotone — control 6 -> 0.0162, A′ 10 -> 0.0186, stack 11 ->
  0.0186, A″ 12 -> 0.0194). It is the same order the full stack already pays
  (34.37 s/pick), and it buys ~5x fewer dropped slots; but it is a cost, not free.
* **Not covered:** `BAND_MAX` 5-6 (the phase-2 map's range is 4-6; only 4 was
  registered here), `FRUIT_SUPPLY_TARGET_FROM` 0.35 -> 0.40 (the substitute
  lever, deliberately unset), the hybrid canary (`60_eval_policy.py` never
  constructs `SortingRLEnv`), the two-line scheduler (its own pump/band path),
  any store collected under this configuration (no `--record`), and the
  acceptance/motion references (untouched — no `src/` change, so
  `fingerprint: matches` would be an import guard here, P38-M4 style).
* **Three runs of a non-reproducible loop.** The direction holds 3/3 on
  `on_belt` (11/11/11), `skipped` (8/4/9), the window mean and the starve count;
  placed is a count with an arm split, **not** a rate (A″ drew 19 left attempts
  of 45 against A′'s 23, and the left is 4/19 — the closed grip/`cnp` class —
  while the **right**, the arm the belt feeds, reads **24/26 = 92.3 %** against
  A′'s 21/22 = 95.5 %). Per AGENTS §2 no cross-configuration success rate is
  claimed.

## 6. Files

`logs/p58/PREREG_A_APRIME2.md`, `logs/p58/run_aprime2.sh` ->
`logs/p58/p3b/A2_batch_outer.log`, `logs/p58/p3b/A2_{77,101,202}.log`,
`logs/p58/p3b/A2_header.txt`, `logs/p58/p3b/A2_tree_md5_after.txt`,
`logs/p58/A2_report.py` -> `logs/p58/A2_report.txt`, this file.
**Nothing was flipped, edited in `src/`, recorded to a store, or committed.**
