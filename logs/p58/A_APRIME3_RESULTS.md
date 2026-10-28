# P58 phase 3c — cell A‴: the DECIDER (`FRUIT_SUPPLY_BAND_INTERLOCK=0`, clock pair only)

Measured **2026-10-28** on HEAD `fdc65d9` (`rl_env.py` `ddcb7816`, `tasks.py`
`c7eef701`, `fruits.py` `55921c46`, checkpoint `moe_v13s` `61da390a` — **the same
15 shared pins as A′'s header, byte-for-byte**, so this is a pure env contrast
against A′/A″). Three runs, one claim each, wall **1712 s**
(`logs/p58/p3c/A3_batch_outer.log`). **No default flip, no `src/`/`configs/`/
`datasets/` write, no checkpoint write, no commit.** Registered in
`logs/p58/PREREG_A_APRIME3.md` (`aa8e4f52`) **before the first run**. Report
`logs/p58/A3_report.txt` (`python3 logs/p58/A3_report.py`), raw logs
`logs/p58/p3c/A3_{77,101,202}.log`.

---

## 0. Verdict

**E2 and E4 PASS; E1 FAILS (5 starved boundaries over 42 = 11.9 %, 5x A′'s one
and against A″'s and the control's zero) and E3 FAILS on both composition bars
(`window` mean **2.20** < 2.38, `window == 1` **12/45** > 9). Per the registered
rule the **first clause that applies is B2**: the starve count is `>= 1`, i.e.
**it starves at least as often as A′** — so **the band interlock is load-bearing
and the flippable unit is the triple (+ `FRUIT_SUPPLY_BAND_MAX=4`)**, with A′'s
one starve carried as a recorded deviation. The clock pair alone is **not**
shippable.

The three numbers that decide it:

| | A‴ (interlock **0**) | A′ (cap 3) | A″ (cap 4) | control | bar |
| --- | --- | --- | --- | --- | --- |
| **starves (`>= 169`)** | **5/42 = 11.9 %** | 1/42 = 2.4 % | 0/42 | 0/42 | 0 (B1) / any (B2) |
| **`on_belt` med / `skipped`** | **11** / **2,0,2** | 9 / 41,36,39 | 11 / 8,4,9 | 5 / 104,107,105 | >= 8 / <= 60 |
| **`window` mean / `== 1`** | **2.20** / **12/45** | 2.02 / 12/45 | 2.38 / 9/45 | 2.60 / 4/45 | >= 2.38 / <= 9 |

Three things this cell settles **beyond** the branch, and they are the reason it
was worth the spend:

1. **The past-station composition is the CLOCK PAIR's, not the interlock's.**
   A‴'s below-window share is **6.24 per `[bed-sel]` block — identical to A″'s
   6.24**, above A′'s 5.20, and far above the control's **0.20**. Registered P3
   predicted < 3.0 and is **FALSIFIED**: removing the interlock does not move the
   composition at all. Every clock-pair arm sits at 5.2-6.2; the arm *without*
   the clock pair sits at 0.2. So Oracle 1's reading (ii) is **half right** — the
   stock gain is transit-like (the catchable window is thinner than the control's
   even with the clock pair demoted to "not load-bearing") — but it attributes
   that composition to the wrong knob: it belongs to keeping the feeder live.
2. **The control's 2.60 / 4 / 0.20 is a *burst* composition, and it is paid for
   in dropped slots.** The control is the only arm with **no clock pair**: its
   pump runs only at the attempt boundary, releases its overdue backlog as one
   burst at the top of the band, and drops the slots whose virtual position is
   already past the station — **104 counted drops = 2.3 per pick**, the largest in
   the family, on a belt holding **5.22** bodies of which **5.00** are in the
   selector's band (`admitted`). Its 2.60/0.20 census is taken 30 ticks after
   that burst. The clock-pair arms census a **stream** at the same +30-tick
   offset: 10.8-10.9 bodies, **~6 past the station floor** (retained, recycled at
   the belt end), **0-2 counted drops**, and a 2.0-2.4 catchable window. The
   comparison is burst-vs-stream, not good-vs-bad composition.
3. **`skipped` cannot see the interlock-off arm's own throttle, so E2's pass is
   not a scheduler win.** The block path is silent: `fruits.py`'s
   `depth >= bed_band_max` branch only sets `queue_hit` and re-bases
   `_next_release` — it increments **no counter** (the Oracle noted this; this
   cell shows the consequence). A‴'s `skipped` **2/0/2** therefore means "almost
   nothing was counted", not "almost nothing was lost": the feeder blocks against
   a region that is **90 % unusable** (its 6 slots span `along -0.05..+0.45`,
   whose catchable part `0.399..0.45` holds **0.42 bodies** on average, measured
   on 45 blocks), while the resource the selector consumes sits *outside* that
   region. Measured consequence: the same release rate as A″ (**1.09 vs 1.11
   releases/sim-s**) but **3 of the 5 starve events** occur with the station
   window at **4-5 of its 6 slots and 0-1 catchable bodies in its own sliver**.

| endpoint | verdict | the number |
| --- | --- | --- |
| **E1** starved feed rounds (`>= 169`; 0 = pass) | **FAIL** | **5/42 = 11.9 %** (77: 1 at 169; 101: 3 at 380/170/289; 202: 1 at 291) — waits of 1, 8, 1, 5, 5 thirty-tick reset rounds (0.25-2.00 s). A′ 1/42, A″ 0/42, control 0/42 |
| **E2** stock + scheduler | **PASS** | `on_belt` pooled median **11** (per run **11/11/11**; A′ 9, A″ 11, control 5); final `skipped` **2 / 0 / 2** (bar <= 60) — with the §3.3 caveat that this counter cannot see the blocking path |
| **E3** `window>=1` + composition | **FAIL** | `window>=1` **45/45** PASS; `window` mean **2.20** (bar 2.38) FAIL; `window == 1` **12/45** (bar <= 9) FAIL; distribution `{1: 12, 2: 20, 3: 6, 4: 6, 5: 1}`, sd 1.05 |
| **E4** no new failure reason | **PASS** | A‴'s 2 keys **=** A″'s 2 keys exactly; no key outside phase-1 A + the P43/P54 baseline; no new fragment |
| **P1** the clock pair runs | **fails on the letter** | `[feed]` rows **15 / 15 / 13**; seed 202's episodes 4 and 14 are `grasped=False` and never reached a release segment — every attempt that released has a row |
| **P2** the station window is the binding pacer | **FALSIFIED as stated** | `skipped` 2/0/2, not `> 39`: the block path is uncounted (§3.3). The *rate* is unchanged (1.09/sim-s), so the loss is in *where/when*, not *how much* |
| **P3** the interlock owns the past-station composition | **FALSIFIED** | below-window **6.24** per block, not `< 3.0`; identical to A″ |
| **P4** wall <= 35.40 s/pick | **fails by 0.08 %** | **35.43** vs A″'s 35.40 at a flat span (1829 vs 1824 ticks/pick) — equal, not a wall regression |
| **placed** | reported | **28/45** (left 3/19, right 25/26) vs A″'s 28/45 (4/19, 24/26) — same count, different arm split; **no rate claim** |

---

## 1. The cell (as registered and as run)

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1
FRUIT_FEED_CADENCE=1 FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=1
scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
    --presentation direct --episodes 15 --seeds <77|101|202>
```

**One variable against A′: `FRUIT_SUPPLY_BAND_INTERLOCK` 1 -> 0** (written
explicitly; `fruits.py:940` defaults it to `"0"`, so this is the shipped
station-window pacing and the value is byte-equivalent to unset — it is printed
only so the claim records it). `FRUIT_SUPPLY_BAND_MAX` **not set** (inert with the
interlock off: `_interlock_max` returns `queue_max`), `FRUIT_SUPPLY_TARGET_FROM`
**not set** (the substitute lever, G4), `FRUIT_DIRECT_CONTINUOUS` **not set**
(the shipped per-pick interface, G2), and the shipped `direct` defaults for
`FRUIT_POLICY_TRIGGER_ACQ` (P54 on) and `FRUIT_ARM_PARK` (P43 `back`) — every run
prints `park=back(default)` and `acq=on(...)`.

Construction checks: **15 picks per run**, **0 `[cont]` rows** (G2 clear), 15/15
`[bed-sel]` rows with `patch=on` and the balanced mix each, `[feed]` rows
**15 / 15 / 13**, `FRUIT_SUPPLY_TARGET_FROM` absent (G4 clear), **G3 clear** (all
10 shared pins identical before and after; all 15 shared files identical to A′'s
header), all three exits **0**, no wedge, no retry (G1 does not fire).

## 2. The runs

Unit = one pick = one `[rl] episode ... success=` row. 15 per run, 45 per arm.

| run | placed (left/right) | `on_belt` med | `admitted` med | `skipped` final | longest `sel_gap` | starves | wall | s/pick |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A‴ 77 | 7 (0/8, 7/7) | 11 | 4 | **2** | 169 | 1 | 531.2 s | 35.4 |
| A‴ 101 | 11 (1/5, 10/10) | 11 | 5 | **0** | 380 | 3 | 539.3 s | 36.0 |
| A‴ 202 | 10 (2/6, 8/9) | 11 | 4 | **2** | 291 | 1 | 523.9 s | 34.9 |
| **A‴ pooled** | **28** (3/19, 25/26) | **11** | 4 | 2/0/2 | **380** | **5/42** | 1594 s | **35.43** |
| A′ (cap 3) | 24 (3/23, 21/22) | 9 | 4 | 41/36/39 | 170 | 1/42 | 1533 s | 34.07 |
| A″ (cap 4) | 28 (4/19, 24/26) | 11 | 5 | 8/4/9 | 141 | 0/42 | 1593 s | 35.40 |
| control (P1 A) | 33 (1/12, 32/33) | 5 | 5 | 104/107/105 | 141 | 0/42 | 1334 s | 29.66 |
| stack (P1 B) | 30 (3/16, 27/29) | 10 | 4 | 40/36/38 | n/a (`[cont]`) | n/a | 1547 s | 34.37 |

## 3. E1 — the starve census, and what the events are made of

`sel_gap = 120*(t_{k+1} - t_k) - ticks_k`; the grid is `140 + 30k`, k = extra
30-tick reset feed rounds; 139-141 is print quantisation and is not counted.

| seed | boundary | gap | k | preceding selection (`on_belt`/`admitted`/`window`/`skipped`) | station-window occ / catchable sliver / band | starved pick |
| --- | --- | --- | --- | --- | --- | --- |
| 77 | 1 -> 2 | 169 | 1 | 11 / 6 / 2 / 2 | **5/6 / 0 / 4** | lychee, right |
| 101 | 2 -> 3 | **380** | **8** | 11 / 7 / 4 / 0 | 4/6 / 0 / 4 | lychee, right |
| 101 | 5 -> 6 | 170 | 1 | 11 / 6 / 3 / 0 | **5/6 / 1 / 4** | strawberry, right |
| 101 | 7 -> 8 | 289 | 5 | 10 / 4 / 2 / 0 | **5/6 / 1 / 2** | orange, **left** |
| 202 | 10 -> 11 | 291 | 5 | 10 / 2 / 1 / 2 | 3/6 / 0 / 1 | peach, right |

Wait lengths **1, 8, 1, 5, 5 rounds = 0.25, 2.00, 0.25, 1.25, 1.25 s**; every
event ends with a candidate (`starved_reset` = 0 — the reset never exhausted its
40 rounds). Fisher exact (two-sided): A‴ vs A″ **p = 0.0551**, A‴ vs A′
**p = 0.2016** — so the count is **suggestive, not conclusive on its own**, which
is why §0 puts the mechanism and the composition bars beside it.

Mechanism, measured: **3 of 5** events fire with the station window at **4-5 of
its 6 slots** while its own catchable part holds **0-1** bodies — the throttle is
on a region the selector cannot use (its 6 slots cover 0.50 m of belt of which
the catchable part `0.399..0.45` is 51 mm and holds **0.42 bodies** on average,
against a catchable band `0.35..0.68` mean of **2.69**). The other 2 are the
schedule's own cadence gaps (band 4 and 1 at the boundary). The **rate** is *not*
the difference: A‴ releases **517 slots over 56 894 feed-ticks = 1.09/sim-s**
against A″'s **537 / 1.11** and A′'s **441 / 0.92** — the same stream, more
variable where it lands (A‴'s catchable band reaches **6** because nothing caps
it; A″'s cap stops it at 4, and its `window` distribution is the tighter
`{1: 9, 2: 18, 3: 10, 4: 8}` against A‴'s `{1: 12, 2: 20, 3: 6, 4: 6, 5: 1}`).

## 4. E2 — the stock passes, and the counter caveat

`on_belt` median **11** (bar >= 8; per run **11/11/11**), final `skipped` **2 / 0
/ 2** (bar <= 60). The instrument check registered for exactly this purpose —
**`on_belt = admitted + below_window + above_belt`** — **holds on all 45 blocks**
of every arm, with the third term the raised-output-conveyor/stacked body the
Oracle's two-term form omitted (0 in A″, 1 in A′ and the control, 5 in the
stack); without it the two-term form has 0-5 exceptions, none of which change an
endpoint.

The caveat is §0.3 and it is a **code fact plus a measurement**: the station
window's block branch increments nothing, so `2/0/2` is a *silent* throttle, and
the arm that passes E2b most comfortably is the one whose feeder is pacing on the
wrong region. **E2's two conjuncts are necessary, not sufficient, on this
scenario** — they were passed by A″ *and* by A‴, and only E1 + E3 separate them.

## 5. E3 — `window>=1` passes, both composition bars fail

| arm | distribution | mean | `window == 1` | `>= 3` | max |
| --- | --- | --- | --- | --- | --- |
| **A‴ (interlock 0)** | `{1: 12, 2: 20, 3: 6, 4: 6, 5: 1}` | **2.20** | **12/45** | 13/45 | **5** |
| A′ (cap 3) | `{1: 12, 2: 20, 3: 13}` | 2.02 | 12/45 | 13/45 | 3 |
| A″ (cap 4) | `{1: 9, 2: 18, 3: 10, 4: 8}` | 2.38 | 9/45 | 18/45 | 4 |
| control | `{1: 4, 2: 20, 3: 11, 4: 10}` | 2.60 | 4/45 | 21/45 | 4 |
| stack | `{1: 10, 2: 21, 3: 14}` | 2.09 | 10/45 | 14/45 | 3 |

The bars fail by 0.18 of a mean and 3 episodes, with sd 1.05 vs 1.00 — **not a
confident discriminator on its own**; the registered trigger is the starve count,
and the composition is the second, consistent leg.

Below-window (past-station) share, `[bed-sel]` rows whose reason contains
`below window`, per block and pooled:

| arm | pooled / blocks | per block | share of candidate rows | per run |
| --- | --- | --- | --- | --- |
| **A‴** | 281/45 | **6.24** | 55.2 % of 509 | 6.13 / 6.07 / 6.53 |
| A″ | 281/45 | **6.24** | 54.2 % of 518 | 6.13 / 6.33 / 6.27 |
| A′ | 234/45 | 5.20 | 53.8 % of 435 | 5.07 / 4.93 / 5.60 |
| stack | 243/45 | 5.40 | 53.5 % of 454 | 5.47 / 5.20 / 5.53 |
| control | 9/45 | **0.20** | 3.4 % of 265 | 0.13 / 0.27 / 0.20 |

(The Oracle's control cell prints **0.18**; the same instrument reads **0.176** if
the aborted 5-pick control run is pooled (9/51) and **0.20** at 45 blocks — one
row's difference, same ordering, stated with its denominator.)

## 6. E4 — no new failure reason

A‴'s key set is **exactly A″'s** (2 keys: the benign `intercept trigger (...)`
note and `intercept trigger (...), fruit did not follow the gripper`), with **no
key** outside phase-1 arm A ∪ the P43/P54 baseline, **no** A‴-only key, **no**
A″-only key lost, and **no** new fragment. The only failure class is the closed
grip/`cnp` class (`logs/p42/SIM_LIMIT.md`).

## 7. What this cell does and does not show

* **It does show** that removing the interlock while keeping the clock pair
  starves the boundary **5x as often** (5/42 vs 1/42 vs 0/42), misses both
  registered composition bars, and leaves the release *rate* unchanged — i.e. the
  loss is the *region* the throttle watches, not how much fruit is delivered.
* **It attributes the past-station composition to the clock pair** (A‴ 6.24 ≈ A″
  6.24; control 0.20) and thereby **corrects the Oracle's reading (ii)**: the
  transit-like stock is the live feeder's, not the interlock's. Any future
  composition claim must be made against a same-feeder arm.
* **It bounds E2's meaning**: `skipped` is a counted-slot instrument only (the
  block path is uncounted), so a low `skipped` cannot certify a scheduler, and
  `on_belt` alone cannot certify stock (Oracle 1's point, confirmed).
* **It is not a rate claim.** placed 28/45 is a count on a different branch
  (A‴ left 3/19 vs A″ 4/19, right 25/26 vs 24/26); the wall is A″'s to 0.08 %
  (35.43 vs 35.40 s/pick at a flat span). Per AGENTS §2 nothing here is a
  throughput delta.
* **Three runs of a non-reproducible loop**: the direction holds 3/3 on
  `on_belt` (11/11/11) and on the composition (6.07-6.53), and the starves are
  spread 1/3/1 across seeds — the count is the registered trigger, its power is
  p = 0.055 against A″, and that is stated rather than leaned on.
* **Not covered:** `BAND_MAX` 5-6, `FRUIT_SUPPLY_TARGET_FROM`, the hybrid canary
  (`60_eval_policy.py` never constructs `SortingRLEnv`), the two-line scheduler,
  any store collected under this configuration (no `--record`), and the
  acceptance/motion references (untouched — no `src/` change, so
  `fingerprint: matches` would be an import guard here, P38-M4 style).

## 8. What the branch means for the owner

B2's consequence is **the same practical decision A″ already handed up**: the
flippable unit is the **triple + `BAND_MAX=4`**, and this cell is the evidence
that the interlock cannot be dropped from it (E1 5/42 and both composition bars
against it, with the "interlock-off" arm passing E2 only because its throttle is
uncounted). A′'s single starve remains a **recorded deviation** of that unit, not
a solved endpoint. **Nothing was flipped.**

## 9. Files

`logs/p58/PREREG_A_APRIME3.md`, `logs/p58/run_aprime3.sh` ->
`logs/p58/p3c/A3_batch_outer.log`, `logs/p58/p3c/A3_{77,101,202}.log`,
`logs/p58/p3c/A3_header.txt`, `logs/p58/p3c/A3_tree_md5_after.txt`,
`logs/p58/A3_report.py` -> `logs/p58/A3_report.txt`, this file.
**Nothing was flipped, edited in `src/`, recorded to a store, or committed.**
