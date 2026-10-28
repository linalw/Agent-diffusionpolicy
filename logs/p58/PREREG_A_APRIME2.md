# P58 phase 3b PREREG — cell A″: A′ plus ONE free knob (`FRUIT_SUPPLY_BAND_MAX=4`)

Written **before any run** (2026-10-28), by the delegated lane. Nothing here is a
shipped-default change; no `src/`, `configs/`, `datasets/` or checkpoint write; no
commit. The deliverable is the measurement and its verdict.

## 0. Why this cell exists

A′ (`logs/p58/A_APRIME_RESULTS.md`) measured the supply triple on the **shipped
per-pick** interface and read **E2/E3/E4 PASS, E1 FAIL on exactly one boundary**:
of A′'s 42 pick boundaries, **41 read 139-141 ticks** (the 140-tick reset within
the 2-dp print quantisation) and **one read 170.2** (seed 101, boundary 8 -> 9) =
**one starved 30-tick feed round**.

A′'s own mechanism section names the object the event tracks: the band interlock
**thins the station window**. Pooled `window` mean **2.02** vs the control's
**2.57**, `window == 1` at **12/45** vs **4/45**, and `max(window) = 3` in both
A′ and the stack — i.e. **the interlock's `_BAND_MAX = 3` ceiling shows up as a
hard maximum on the window census**. The starved boundary took a fruit at
`along = +0.680` = `spawn_y` (just released) with `on_belt` 9 / `live` 10 /
`admitted` 3 / `window` 2 — so it waited **~0.25 s for the next release**, not for
stock.

The phase-2 map (`.slim/deepwork/p58-continuous-supply.md`) named this knob in
advance: **"`FRUIT_SUPPLY_BAND_MAX` 3 -> 4-6 … (free, unmeasured, first response
to any starve with a `skipped` increment); phase 3 owns the tuning cell if A's
battery leaves `window=0` >= 5 % or any starve with a `skipped` increment."**
A′'s E1 event carries `skipped` **+4** across it, so **that condition is MET** and
this cell is the registered response.

**Question: is the starve the `_BAND_MAX = 3` ceiling's, or the schedule's?**
The two predict the same 0.25 s wait on one event. The discriminator is the
census the ceiling actually moves (the window distribution) plus the starve count
at the higher ceiling.

## 1. The cell (one arm, one claim per run, ~28 min)

**Cell A′ exactly, plus ONE env var.** The A′ block is reproduced verbatim and the
only difference is `FRUIT_SUPPLY_BAND_MAX=3` -> **`4`**:

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1
FRUIT_FEED_CADENCE=1 FRUIT_SUPPLY_BAND_INTERLOCK=1 FRUIT_SUPPLY_BAND_MAX=4
FRUIT_DIRECT_FEED=1
scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
    --presentation direct --episodes 15 --seeds <77|101|202>
```

Seeds **77 / 101 / 202** (the A′ seeds, so the contrast is paired by seed); logs
`logs/p58/p3b/A2_<seed>.log`; one `scripts/154_claim_run.sh` claim per run
(`RUN_LIMIT=1800`).

### 1.1 The single-variable discipline (registered)

* **ONE change: `FRUIT_SUPPLY_BAND_MAX` 3 -> 4.**
  `FRUIT_SUPPLY_TARGET_FROM` is **NOT set** (it is the *substitute* lever named
  beside this one in the phase-2 map — the 0.35 -> 0.40 band start that deletes
  the 0.049 m dead sliver). Setting both would make this cell two variables and
  its starve read unattributable. `FRUIT_SUPPLY_TARGET_FROM` stays at its
  shipped value, identical to A′ and to phase 1.
* Everything else is A′ verbatim, including the harness block
  (`HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1
  FRUIT_NO_SLEEP=1`, `execute_steps=4`, `ddim=16`, no `--record`).
* **Deliberately not set** (the shipped `direct` defaults; P54/P43):
  `FRUIT_DIRECT_CONTINUOUS` (**the shipped per-pick interface — this is the
  point of the cell family**), `FRUIT_POLICY_TRIGGER_ACQ` (resolves on for
  `direct`), `FRUIT_ARM_PARK` (resolves `back` for `direct`),
  `FRUIT_REGRASPS`/`FRUIT_SUBSTEPS`/`FRUIT_FINGER_STIFFNESS`/
  `FRUIT_FINGER_MAXFORCE` (the P40/P41 shipped values).

`fruits.py:938-941` registers the knob: `self._band_max = max(1, int(
os.environ.get("FRUIT_SUPPLY_BAND_MAX", "3")))`, consumed by `_interlock_max`
(`fruits.py:1891-1897`) only when `bed_schedule is None and _band_interlock`, so
the raise touches **the band interlock's ceiling and nothing else**. No source
edit: the knob already exists (it is A′'s own env var, costed at one integer).

### 1.2 The controls are free and paired

* **A′** = `logs/p58/p3a/Ap_{77,101,202}.log` — the same tree, same scenario, same
  seeds, same harness, `--episodes 15`, triple at `BAND_MAX=3`. **The paired
  control for A″.** `on_belt` pooled median **9**, final `skipped` **41/36/39**,
  `window` **{1:12, 2:20, 3:13}** (mean 2.02), starves **1/42**, placed **24/45**
  (left 3/23, right 21/22), wall **1533 s / 45 = 34.07 s/pick**.
* **Phase 1's arm A** (`logs/p58/p1/A_*.log`) — per-pick, no triple: `on_belt` **5**,
  `skipped` **104/107/105**, `window` **{1:4, 2:20, 3:11, 4:10}** (mean 2.57),
  starves **0/42**, placed **33/45**, wall **1334 s / 45 = 29.66 s/pick**.
* **Phase 1's arm B** (`logs/p58/p1/B_*.log`) — the full stack, 15-pick episode:
  `on_belt` **10**, `skipped` **40/36/38**, `window` **{1:10, 2:21, 3:14}**,
  placed **30/45**, wall **1547 s / 45 = 34.37 s/pick**.

Nothing is re-run to produce them.

### 1.3 Tree pins (verified before the run; expected identical to A′'s header)

`rl_env.py` `ddcb7816`, `tasks.py` `c7eef701`, `fruits.py` `55921c46`,
`scene.py` `27e3d64a`, `control.py` `9384ff4f`, `meshes.py` `1ad5af0e`,
`policy/trigger.py` `b09d3cb2`, `policy/runtime.py` `379ac706`,
`configs/arm_parks.json` `42ab4fb7`, `configs/motion_reference.json` `8a399626`,
`..._twoline.json` `2246f83c`, checkpoint `moe_v13s` `61da390a`, HEAD `fdc65d9`.
**No `src/` edit in this cell** — the pins are A′'s, which makes A″ a pure env
contrast against A′ (registered so a moved pin is read as a void cell, G3).

## 2. Endpoints (registered before the run; the A′ endpoint set, E1 re-stated)

Unit = one pick = one `[rl] episode ... success=` row. 3 seeds x 15 = **45 picks**;
boundaries = 42. A run whose pick count is not 15 is reported and flagged, never
pooled.

### E1 — zero starved feed rounds (the registered read, `>= 169` form)

`sel_gap_k = 120*(t_{k+1} - t_k) - ticks_k` over consecutive `[bed-sel] attempt`
rows (A′'s instrument, unchanged).

*Registered instrument facts (from A′, measured, not assumed):* `t=` is 2-dp, so
the read carries **±1.2 ticks** of print quantisation; A′ and the control both
read **139-141** on boundaries that are exactly 140 (the realizable grid is
`140 + 30k`). **Therefore 139-141 is NOT a failure and is not counted as one
this time** — the A′ registration's `<= 141` literal bar is replaced by the
starve-only form below, exactly as instructed.

*Pass bar:* **zero** gaps `>= 169` in **all three runs** (169-171 = one starved
30-tick feed round; `>= 200` = the P58 F2 class, reported as such and a FAIL),
**and** the pooled **starved-round count = 0**. Reported beside it:
* the pooled starve count (`>= 169` rows) with its seed, boundary index and the
  surrounding `[bed-sel]` row's `on_belt`/`live`/`admitted`/`window`/`skipped`;
* the full gap distribution (min / median / max, and the literal `> 140` count);
* the **139-141 count** (expected 42/42 on a clean cell — reported, not gated).

### E2 — the stock and the scheduler (the owner's object; unchanged)

* **pooled `on_belt` median >= 8** (per-run medians reported), **and**
* **every run's final cumulative `skipped` <= 60**.

Calibration: A′ 9 / 41-36-39; control 5 / 104-107-105; stack 10 / 40-36-38.
**This is the endpoint that catches a cap raise that buys the window by
over-stocking**: a `BAND_MAX=4` that pushes `on_belt` past the stack's level or
inflates `skipped` is a degradation even if E1 passes.

### E3 — `window >= 1` at every selection (unchanged)

**45/45** (`[bed-sel]` `window=`, pooled). A row count other than 45 is reported
and explained before E3 is read. (The per-pick path prints one row per pick, the
successful selection, so a starved retry round is invisible here and visible only
in E1 — P58 amendment A1.1.)

### E4 — no new failure reason (unchanged)

Exactly `scripts/113_rl_report.py`'s `reasons()` normalisation (the whole
`notes=[...]` text with every `[-+0-9.]+` run replaced by `#`), baseline =
P43/P54 (`logs/p43/p3/*.log`, `logs/p54/p1/*.log`) **plus phase 1's arm A**.
*Pass bar:* `keys(A'') ⊆ keys(A_p1) ∪ baseline`. Reported in both directions, raw
fragments listed, **and additionally `keys(A'') - keys(A')`** (the knob's own
signature, if any). A new key is a FAIL even if the rate is fine (P38/P41/P58
precedent).

### Reported only (no gate) — the header reads the parent asked for

1. **The `window` distribution** — pooled and per run: `{k: n}`, mean, and the
   `window == 1` count. **This is the object the cap moves**, so it is the cell's
   primary *mechanism* read even though only E1-E4 gate. Compare A′
   `{1:12, 2:20, 3:13}` (mean 2.02, max 3) against A″: a cap that binds must show
   **a non-zero count at 4** (A′ and the stack both read **max 3**, so 4 is a
   signature no triple run has produced yet) and a mean moving toward the
   control's 2.57.
2. **placed split** — per run and pooled, with `arm=left/right`. **No rate claim
   in any direction** (different scenario, non-reproducible loop, AGENTS §2);
   the left's count is the closed grip/`cnp` class (`logs/p42/SIM_LIMIT.md`).
3. **wall per pick** (`[rl] run wall end ... duration` / picks), and the
   simulated span (`ticks`/pick) so the wall's pump-vs-sim attribution stays
   readable (A′: +14.9 % wall at a flat +0.3 % span).
4. `admitted` median, `lag` median, `rebased`/`dropped`, the `[feed]` rows'
   `updates=`/`ticks=`, `live` median — A′'s mechanism columns.

## 3. Registered predictions (so the mechanism can be read, not just the verdict)

Written before the run; each is checked in the report:

* **P1 (the cap binds).** `max(window) = 4` appears at least once and the pooled
  `window` **mean rises** from A′'s 2.02. If the distribution is **unchanged**
  from A′'s `{1:12, 2:20, 3:13}`, the cap is **not** the binding term on this
  interface and the starve is the **schedule's** — this is the falsifier for the
  "cap is the cause" hypothesis and it is read **even if E1 passes**.
* **P2 (the starve is the cap's).** Starves fall from **1/42 to 0/42**.
* **P3 (no over-stock).** `on_belt` median stays **9-11** (not above the stack's
  10 by more than +1) and final `skipped` stays **<= 60** in every run.
* **P4 (the cap raise is not free wall).** wall/pick stays within **+0-3 %** of
  A′'s 34.07 s (i.e. **<= 35.1 s/pick**); the simulated span stays flat.

## 4. Decision rule (registered)

* **E1-E4 all pass** -> the **triple + `BAND_MAX=4`** is the **flippable unit**
  for `direct` (the continuous episode is not load-bearing, and the boundary is
  free at the higher ceiling).
* **`window >= 1` improves but E1 still fails** -> **report the remaining
  starve's mechanism** (which boundary, which fruit, `on_belt`/`window`/`skipped`
  at the preceding selection) and **do not flip**: the starve is then not the
  ceiling's.
* **`on_belt` or `skipped` degrades** (E2 fails in either clause) -> **say so and
  stop**: the cap raise is buying the window by over-stocking and is not a
  shippable change at any E1 result.
* **E3 fails** -> **do not flip** (unchanged from A′).
* **E4 fails** -> **do not flip**.

## 5. Falsifiers (each reported; a firing falsifier stops the cell's conclusion)

* **G1** a run does not deliver 15 picks (wedge / timeout / RuntimeError) ->
  report, **retry once on the same seed**, record the retry.
* **G2** `[cont]` rows appear in any log -> the cell is not the shipped interface;
  void (`FRUIT_DIRECT_CONTINUOUS` unset).
* **G3** tree pins moved between the first and last run, **or** differ from A′'s
  header -> the runs are not one cell against A′; void.
* **G4** `FRUIT_SUPPLY_TARGET_FROM` appears in an env print -> two variables;
  void.

## 6. Read rules carried into the report

1. **Branches, not rates.** Placed counts are counts; A′ vs A″ is a **mechanism**
   contrast (window, starve, stock, skips), never a throughput delta.
2. **The instrument is inside the contrast.** `FRUIT_BED_DIAG=1` is on both sides
   (A′ ran it), so the census is symmetric.
3. **One cell, three seeds.** Three runs of a non-reproducible loop: the statement
   is the per-run consistency read (does the direction hold 3/3?); no confidence
   interval is claimed from 45 picks for a mechanism endpoint.
4. **The starve's power is its count, and it is small.** A′'s event is **1 in 42**
   (2.4 %). A null in A″ (0 starves in 42) is consistent with a real fix **and**
   with a ~2.4 % event rate, so **E1's pass is necessary, not sufficient** — that
   is exactly why P1's window-distribution check is registered as the mechanism
   falsifier, and why the report must quote both.
5. **Continuity is not throughput** (P58 §4.4). Nothing here is a rate.

## 7. Files

`logs/p58/PREREG_A_APRIME2.md` (this file), `logs/p58/run_aprime2.sh` ->
`logs/p58/p3b/A2_batch_outer.log`, `logs/p58/p3b/A2_{77,101,202}.log`,
`logs/p58/p3b/A2_header.txt`, `logs/p58/p3b/A2_tree_md5_after.txt`,
`logs/p58/A2_report.py` -> `logs/p58/A2_report.txt`,
`logs/p58/A_APRIME2_RESULTS.md`.
