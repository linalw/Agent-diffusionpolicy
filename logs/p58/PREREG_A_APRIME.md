# P58 phase 3a PREREG — cell A′: the supply triple on the SHIPPED per-pick interface

Written **before any run** (2026-10-28), by the delegated lane, on the instruction
of Oracle 1's one bounded precondition for flipping the direct-line defaults.
Nothing here is a shipped-default change; no `src/`, `configs/`, `datasets/` or
checkpoint write; no commit. The deliverable is the measurement and its verdict

## 0. Why this cell exists

P58 phase 1 (`logs/p58/A_RESULTS.md`) measured the **stack as a unit** — the
cadence, the band interlock, the direct feeder **and** the 15-pick multi-pick
episode — against the shipped per-pick line, and read `window>=1` 45/45 in both
arms with the mechanism split on stock depth (`on_belt` 5 -> 10) and scheduler
skips (105 -> 38).

**The confound Oracle 1 named:** every run of the triple so far lived inside
`FRUIT_DIRECT_CONTINUOUS=15`, and the multi-pick episode changes the pick
boundary itself (50/80 ticks instead of the 140-tick reset). So "the triple
carries the stock" and "the harness carries the stock" are not separated by
phase 1 — and the *shipped* interface is the per-pick one.

**Question: does the supply triple alone — no continuous episode — deliver the
stock and the scheduler currency on the interface that would actually ship?**

## 1. The cell (one arm, one claim, ~30 min)

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1
FRUIT_FEED_CADENCE=1 FRUIT_SUPPLY_BAND_INTERLOCK=1 FRUIT_SUPPLY_BAND_MAX=3
FRUIT_DIRECT_FEED=1
scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
    --presentation direct --episodes 15 --seeds <seed>
```

Seeds **77 / 101 / 202**; logs `logs/p58/p3a/Ap_<seed>.log`; one
`scripts/154_claim_run.sh` claim per run (`RUN_LIMIT=1800`).

**Deliberately not set** (they are the shipped `direct` defaults and setting them
would move the cell off the shipped interface — P54/P43):

* `FRUIT_DIRECT_CONTINUOUS` — **not set**; this is the whole point of the cell:
  the shipped per-pick interface (`--episodes 15` = 15 picks = 15 logical
  episodes, each with its own 140-tick reset).
* `FRUIT_POLICY_TRIGGER_ACQ` — not set; resolves **on** for `presentation ==
  "direct"` (P54).
* `FRUIT_ARM_PARK` — not set; resolves **`back`** for `direct` (P43).
* `FRUIT_REGRASPS`, `FRUIT_SUBSTEPS`, `FRUIT_FINGER_STIFFNESS`,
  `FRUIT_FINGER_MAXFORCE` — unset; the P40/P41 shipped values apply.

**Harness block** (the phase-1 block verbatim; outside the contrast, needed to run
headless and to keep the wall comparable):
`HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1
FRUIT_NO_SLEEP=1`, `execute_steps=4`, `ddim=16`, no `--record`.

### 1.1 The control is free: P58 phase 1's arm A

Arm A of phase 1 is the same tree, the same checkpoint, the same scenario block,
the same harness block, the same seeds and `--episodes 15`, **without** the four
supply knobs. It is therefore the paired control for A′, and its numbers are
quoted from `logs/p58/p1/A_{77,101,202}.log` (not re-run):
`on_belt` median **5**, final `skipped` **104 / 105 / 107**, `window>=1`
**45/45**, placed **33/45** (left 1/12, right 32/33), wall **1334 s**.

The other reference is phase 1's arm B (the full stack, continuous episode):
`on_belt` median **10**, final `skipped` **40 / 38 / 36**, `window>=1` **45/45**,
placed **30/45**, wall **1547 s**.

So A′ sits **between** two measured points, and the cell answers a one-line
question: **is the triple's stock/skip gain the triple's, or the continuous
episode's?**

### 1.2 Tree pins (verified before the run, identical to phase 1's header)

`rl_env.py` `ddcb7816`, `tasks.py` `c7eef701`, `fruits.py` `55921c46`,
`scene.py` `27e3d64a`, `control.py` `9384ff4f`, `policy/trigger.py` `b09d3cb2`,
`policy/runtime.py` `379ac706`, `configs/arm_parks.json` `42ab4fb7`,
`configs/motion_reference.json` `8a399626`, `..._twoline.json` `2246f83c`,
checkpoint `moe_v13s` `61da390a`, HEAD `fdc65d9` (phase 2 is docs-only, so the
`src/` pins are phase 1's and the control logs are the same tree).

## 2. Endpoints (registered before the run)

Unit = one pick = one `[rl] episode ... success=` row. 3 seeds x 15 = **45
picks**. A run whose pick count is not 15 is reported and flagged, never pooled.

### E1 — the selection-clock boundary did not starve

`sel_gap_k = 120*(t_{k+1} - t_k) - ticks_k` over consecutive `[bed-sel] attempt`
rows (PREREG §2.2 amendment A1.2's read; the cell has **no `[cont]` rows**, so
this is the only boundary instrument).

*Registered instrument fact, before the run:* `t=` is printed to 2 dp, so
`120*(t_{k+1}-t_k)` carries up to **±1.2 ticks** of print quantization; phase 1
measured A's 42 boundaries at **139-141** for a boundary that is exactly 140.
The reset's feed loop is discrete (each round is 30 ticks), so the realizable
values are `140 + 30k ± 1`; nothing can land in 145-168.

*Pass bar (conjunctive):* **every** gap `<= 141` (i.e. 140 within the 1-tick
quantization) in **all three runs**. The literal count of `> 140` is **reported
beside it** (it is expected to be 0-3 rows, all 141, all one 140-tick boundary).
A gap in `169-171` = **one starved feed round** and is a FAIL; `>= 200` is the
P58 F2 class and is reported as such. A run with a starved reset that exhausted
40 rounds raises and dies; that is a FAIL and a finding.

### E2 — the stock and the scheduler (the owner's object)

Two mechanical reads from the `[bed-sel]` rows (`FRUIT_BED_DIAG=1`), and from
them the phase-1 contrast:

1. **`on_belt` median** — the bodies on the belt at the selection instant,
   **pooled over the 45 selections** of the three runs (per-run medians
   reported beside it).
2. **final cumulative `skipped`** — the last `[bed-sel]` row's `skipped=`
   (cumulative per run), **per run**.

*Pass bar (conjunctive):* pooled `on_belt` median **>= 8** **and** every run's
final cumulative `skipped` **<= 60**. Calibration: control A = 5 / 107; the
continuous stack = 10 / 40. The bar asks A′ to land at least 80 % of the stack's
stock and at most ~57 % of the stack's skips — i.e. that the triple, not the
episode, is doing the work. A′ failing E2 with E1/E3 passing means the
continuous episode is doing work beyond the clock (the registered decision rule,
§3).

### E3 — the per-pick boundary does not reintroduce a starve

`window >= 1` at **45/45** selections (`[bed-sel]` `window=`, pooled).

*Registered instrument fact (P58 A1.1):* the per-pick path prints exactly **one**
`[bed-sel]` row per pick — the *successful* selection — so its starved retry
rounds are **invisible in this census** and are visible only in E1 (each retry
adds 30 ticks). E3 is therefore an upper bound on this arm exactly as it is on
the control, and E1 is the read that sees the hidden rounds. A row count other
than 45 is reported and explained before E3 is read.

### E4 — no new failure reason

Exactly `scripts/113_rl_report.py`'s `reasons()` normalisation (the whole
`notes=[...]` text, every run of `[-+0-9.]+` replaced by `#`), baseline =
P43/P54 (`logs/p43/p3/*.log`, `logs/p54/p1/*.log`) **plus phase 1's arm A**
(the same-scenario control). *Pass bar:* `keys(A') ⊆ keys(A_p1) ∪ baseline`.
Reasons are reported in both directions and the raw fragments listed. A new key
is a FAIL even if the rate is fine (P38/P41/P58 precedent).

### Reported only (no gate)

* **placed** per run and pooled, with the per-arm split (`arm=left/right` on each
  row). **No rate claim in either direction**: A vs A′ are different scenarios
  (the supply changes which fruit are presented), the loop is not reproducible
  (rendered frames), and AGENTS §2 forbids a cross-configuration success-rate
  comparison. The left arm's 0-3/12 is the closed grip/`cnp` class
  (`logs/p42/SIM_LIMIT.md`), not a supply effect.
* **wall per pick** (the `[rl] run wall end ... duration Xs` / picks).
* **`admitted`** median, `lag` median, `rebased`/`dropped`, and the `[feed]`
  pump rows' `updates=`/`ticks=` (did the cadence actually run at this
  interface, where the policy phase is per pick?).
* The per-run `window` distribution (the interlock's `_BAND_MAX=3` ceiling
  should show as `max(window) <= 3`).

## 3. Decision rule (registered)

* **E1-E4 pass** -> the triple is **flippable for `direct`**: it delivers the
  stock and the scheduler currency on the interface that would ship, so the
  continuous episode is not load-bearing for the owner's intent.
* **E2 fails with E1/E3 passing** -> the **continuous episode is doing work
  beyond the clock**; the full stack (episode included) is the owner's call and
  the triple alone is not.
* **E3 fails** -> **do not flip**.

## 4. Supply provenance check (read-only, no gate)

Per log: the `[supply]` row must read `patch=on` (with its
`slice=`/`pair=`/`sep=` fields) and the balanced `grades=A:0.375,B:0.375,C:0.25`;
`[bed-sel]` rows must carry the `skipped=` column; `[feed]` rows must exist (the
cadence ran). Any mismatch is reported as a finding and E2's `skipped` read is
void for that run.

## 5. Falsifiers (each is reported, and stops the cell's conclusion)

* **G1** a run does not deliver 15 picks (wedge / timeout / RuntimeError) ->
  report, retry **once** on the same seed, record the retry.
* **G2** `[cont]` rows appear in any log -> the cell is not the shipped
  interface; void (construction check: `FRUIT_DIRECT_CONTINUOUS` is unset).
* **G3** the tree pins moved between the first and last run -> the three runs are
  not one cell; void.

## 6. Read rules carried into the report

1. **Branches, not rates.** Placed counts are counts. The A vs A′ comparison is a
   **mechanism** contrast (stock, skips, boundary), never a throughput delta.
2. **The instrument is inside the contrast.** `FRUIT_BED_DIAG=1` is set on both
   sides (phase 1's A also ran it), so the census is symmetric.
3. **One cell, three seeds.** Three runs of a non-reproducible loop: a per-run
   consistency read (does the direction hold 3/3?) is the statement; no
   confidence interval is claimed from 45 picks for a mechanism endpoint.
4. **Continuity is not throughput** (P58 §4.4). E2 measures what is on the belt
   and whether the release clock is current; it says nothing about how fast a
   pick is.

## 7. Files

`logs/p58/PREREG_A_APRIME.md` (this file), `logs/p58/run_aprime.sh` ->
`logs/p58/p3a/Ap_batch_outer.log`, `logs/p58/p3a/Ap_{77,101,202}.log`,
`logs/p58/p3a/Ap_header.txt`, `logs/p58/p3a/Ap_tree_md5_after.txt`,
`logs/p58/Ap_report.py` -> `logs/p58/Ap_report.txt`,
`logs/p58/A_APRIME_RESULTS.md`.
