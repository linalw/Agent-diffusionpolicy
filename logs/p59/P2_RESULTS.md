# P59 phase 2 results — the catch-margin arms (both fail E1; the bar is not adjudicable)

**Verdict (Oracle 2): KEEP cap 4. No shipped default change.** The lane closes as
**non-binding**, not as "cap 5 lost": nothing behavioural moves between cap 4 and
cap 5, and E1's 2.57 bar is a third estimator that matches no row of the table.

## The table (45 `[bed-sel]` blocks per cell, pooled)

| cell | `window` mean | `==1` | `==0` | starved (`sel_gap>=169`) | final `skipped` | `on_belt` | `admitted` | below-window/block | placed (report only) | wall s/run (15 picks) |
|---|---|---|---|---|---|---|---|---|---|---|
| burst control (pre-P58) | **2.600** | 4/45 | 0 | 0/42 | 104/107/105 | 5.22 | 5.00 | 0.20 | 33/45 | 444.8 |
| **control cap 4 (shipped)** | **2.378** | 9/45 | 0 | **0/42** | 8/4/9 | 10.93 | 4.69 | 6.24 | 28/45 | 531.1 |
| **A: `BAND_MAX=5`** | **2.533** | **4/45** | 0 | **0/42** | 6/11/4 (21) | 11.82 | 5.33 | 6.47 | 27/45 | 530.2 |
| **B: `TARGET_FROM=0.40`** | 2.267 | 10/45 | 0 | **0/42** | 3/3/2 (8) | 11.62 | 5.09 | 6.49 | 29/45 | 519.9 |

## Why cap 5 does not ship

1. **E1's bar is mis-footed.** 2.57 is the burst cell pooled over **51** blocks - it
   includes the 5-pick aborted run (`logs/p58/p1/A_77_aborted_5picks.log`); every
   other cell is 45 blocks, and on 45 the burst reads **2.600**. The bar sits
   **0.03 below its own cell** and matches no row.
2. **The mean leg has no power at n=45.** A's `window` sd is 0.859 -> SE 0.128,
   95 % CI **[2.282, 2.784]**; the bar sits **0.26 SE inside** A's own interval,
   and two such arms need |delta| >= 0.50 to separate at 95 %.
3. **Nothing behavioural moves.** `window==0` 0/45 and starved rounds 0/42 in all
   four cells; `sel_gap` is the **identical multiset** for cap 4 and cap 5
   ({139x8, 140x25, 141x9}); `skipped` totals **21 = 21**; placed 27 vs 28;
   wall 530.2 vs 531.1 s/run (35.35 vs 35.40 s/pick). Cap 5 moves a counter that no
   behaviour in this scenario reads.
4. The one direction-consistent signal - the marginal share 9/45 -> 4/45, non-worse
   in 3/3 seeds, per-run exact p = 0.125, pooled Fisher p = 0.24 - is real-looking
   and **not resolvable** at this n. It is recorded, not acted on.

## Why `TARGET_FROM=0.40` is rejected mechanically

`window` counts only `usable`/`chosen` (`tasks.py:5515`), so the "below catch floor"
rows live in `admitted`, never in `window`; the arm's registered "12.9 % dead sliver"
rationale targeted the report's **re-derived occupancy**, not the endpoint. On the
real counter B reads **2.244 vs 2.711**, while `below catch floor` **rises 2.31 ->
2.82 per block**: it moves stock **into** the sliver it meant to delete. Its
`skipped` 8 vs 21 at zero starvation is the recorded residual trade.

## The residual (verbatim, per Oracle 2)

> the shipped profile's instantaneous window depth is **2.378 (9/45 marginal
> blocks)** against the pre-P58 burst control's **2.600 (4/45)**, and that gap
> produces **no measurable difference** in `sel_gap`, starvation, `skipped` or the
> placed count in any of the four cells; the registered bar (2.57) is a 51-block
> pool including an aborted run and is 0.26 SE inside cap 5's own 95 % interval,
> so **no depth mean at n=45 ranks the arms**.

## What a reopening needs

1. a **same-tree 45-block control** (this registration named "the P59 phase-1 logs,
   45 selections" - phase 1 ran 2/1/continuous-10/continuous-8 picks and never
   produced one; the substitute was the cross-tree P58 phase-3b cell, `rl_env`
   `ddcb7816` vs `1b1e5cdf`, whose cap-4 membership rests on `A2_header.txt`
   because it predates the `[supply] direct profile` row);
2. a **behavioural endpoint** (`sel_gap`, a starve, or a skip), never a depth mean.

**Cap 6 is predicted flat** (dose-response saturated: cap 3 -> 4 = +0.36, 4 -> 5 =
+0.156; the aperture is bounded by the 0.399 m catch floor and P33's ~1.8 eligible
per grade-pure lane), and it must not be registered on a depth mean.

## Artifact

`logs/p59/p2_report.py` runs **exit 0** on its six logs (the arm check matches the
`[supply] direct profile` row, not the scatter row) and writes
`logs/p59/p2_report.txt`; the table above is its output.

## Measured evidence behind the verdict (phase-2 lane)

### Tree, scenario, regime

* **Pins measured** (`logs/p59/p2/header.txt`, re-checked after the batch as
  `tree_md5_after.txt` — **stable, 0 moved**): HEAD **`ee522c1`**;
  `rl_env.py` **`1b1e5cdf`** (the P59 gate-1 row/manifest edit, committed as
  `be5e41c` — *not* the pre-gate-1 `6d7cb329`), `tasks.py` **`8ad8ddc8`**,
  `fruits.py` **`c7461d41`**, `scene.py` `27e3d64a`, `control.py` `9384ff4f`,
  `meshes.py` `1ad5af0e`, `policy/trigger.py` `b09d3cb2`,
  `policy/runtime.py` `379ac706`, `scripts/110_rl_rollout.py` `abd2b5f1`,
  checkpoint `moe_v13s` **`61da390a`**; `configs/*` untouched
  (`8a399626` / `2246f83c`). `scripts/230` PASS on this tree.
* **Scenario** (identical in both arms and to the P58 cells):
  `FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
  FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival
  FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_BED_DIAG=1`;
  harness `HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER=
  FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 FRUIT_POLICY_SEED=11`;
  `110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt
  --presentation direct --episodes 15 --seeds {77,101,202}`, one claim per run,
  six runs exit 0. `FRUIT_DIRECT_CONTINUOUS`, `FRUIT_POLICY_TRIGGER_ACQ`,
  `FRUIT_ARM_PARK` **unset** (P58/P54/P43 defaults): `[cont]` rows 0 in all six,
  `env ready ... park=back(default)` in all six.
* **One variable each, proven from the artefacts** (the gate-1 row; the run
  stops if this fails). Identical in all three runs of each arm:
  * A: `direct profile: cadence=on(default) band=on(5(explicit))(default)
    feed=on(default) target_from=0.35(default)`
  * B: `direct profile: cadence=on(default) band=on(4)(default)
    feed=on(default) target_from=0.40(explicit)`
* **Control**: `logs/p58/p3b/A2_*.log`, re-read not re-run; it **predates the
  profile row**, so its cap-4 membership comes from `A2_header.txt`'s
  `BAND_MAX=4` triple and its own tree pins (`rl_env.py` `ddcb7816`,
  `tasks.py` `c7eef701`, `fruits.py` `55921c46`) — the cross-tree caveat the
  reopening condition names.

### Reading rules (PREREG_P2 §"The reading rules") applied verbatim

* placed = the per-episode `success/grasped/placed` rows, never the running
  counter;
* starvation from the **absence** of `waiting for a candidate` / `no candidate`
  lines (**0 in all six logs**; also 0 `no graspable fruit reached the selection
  window` retries) and from `sel_gap >= 169` (**0/42 per arm**; every gap
  <= 141, the 140-tick boundary within the 2-dp print quantisation);
* `supply_skipped` is **not** read as the drop counter;
* `on_belt` is **not** a catch metric: the identity
  `on_belt = admitted + below_window + above_belt` holds on **45/45 blocks in
  all four tables** (0 mismatches).

### Per-seed detail (`window` sum / mean / `==1` / final `skipped`)

| seed | control cap 4 | **A cap 5** | **B 0.40** |
|---|---|---|---|
| 77 | 36 / 2.40 / 2 / 8 | 39 / 2.60 / 1 / 6 | 35 / 2.33 / 3 / 3 |
| 101 | 39 / 2.60 / 2 / 4 | 39 / 2.60 / 2 / 11 | 32 / 2.13 / 4 / 3 |
| 202 | 32 / 2.13 / 5 / 9 | 36 / 2.40 / 1 / 4 | 35 / 2.33 / 3 / 2 |

A is **non-worse in 3/3 seeds** and strictly better in 2/3 (one tie at 39).
The verdict's `p = 0.125` is the 3/3 form; the ties-dropped one-sided sign test
on these three pairs reads **p = 0.25**, and the pooled permutation test on the
45 vs 45 means reads **p = 0.50** (A vs burst p = 0.82; B vs control p = 0.67,
B vs burst p = 0.12). Direction unchanged; not resolvable at this n.

### The aperture mechanism (why the depth is flat)

`[bed-sel]` candidate rows reproduce `window` from raw positions: counting live
bodies with `along >= 0.399` gives **117 / 108 / 114 / 102** against the
`window` column's **117 / 107 / 114 / 102** (burst / cap 4 / A / B) — exact on
three tables, one row apart on the control (a body printed at `along=+0.399`
refused as `below catch floor 0.399 < 0.399`). So `window` **is** the census of
the catchable **0.281 m** of belt (`_dynamic_select_floor()` 0.399 -> spawn
0.68), which a body crosses in **2.34 s** at 0.12 m/s.

| | past station (<0) | 0..0.15 | 0.15..0.399 | **0.399..0.68 (aperture)** | > 0.68 |
|---|---|---|---|---|---|
| burst (pre-P58) | 0.4 % | 13.7 % | 35.9 % | **50.0 %** | 0 % |
| control cap 4 | 48.8 % | 10.6 % | 18.7 % | **22.0 %** | 0 % |
| A cap 5 | 48.2 % | 11.3 % | 19.0 % | **21.5 %** | 0 % |
| B 0.40 | 50.1 % | 9.6 % | 20.7 % | **19.6 %** | 0 % |

* The shipped profile carries **2.1x** the burst control's bodies
  (`on_belt` 10.93 vs 5.22) but keeps only **2.40** in the catchable 0.281 m:
  **48.8 %** have ridden past the station. Neither arm moves that share.
* **Cap 5's +0.40 counted bodies buy +0.13 aperture bodies.** The interlock
  counts `_approach_depth` (floor `TARGET_FROM`), i.e. **0.33 m** at the shipped
  0.35 — it includes the **0.049 m sliver (0.35..0.399) the catch cannot draw
  from**. Counted-band occupancy 2.71 -> 3.11, aperture 2.40 -> 2.53: about one
  in three extra bodies lands in the catchable part, the rest in the sliver.
* **B counts exactly the aperture** (band length 0.28 m, occupancy 2.24 ~= the
  aperture's 2.27), so refusals collapse (`skipped` 21 -> 8 total, 1.11 ->
  1.18 releases/sim-s) — and the aperture *falls* to 2.27 while
  `below catch floor` rises **2.31 -> 2.82 per block** (A: 2.80): the arm feeds
  the sliver it meant to delete. This is the P33/P56 aperture ceiling.
* Wall does not gate: **530.2 vs 531.1 s/run** (35.35 vs 35.40 s/pick) and the
  simulated span is flat (1817 vs 1824 ticks/pick) at live bodies 13 vs 12.

### Endpoints as the PREREG words them

| endpoint | bar | A | B |
|---|---|---|---|
| E1 mean | >= 2.57 | 2.53 FAIL (114/45) | 2.27 FAIL (102/45) |
| E1 `==1` | <= 4/45 | 4/45 PASS | 10/45 FAIL |
| E2 starved rounds | 0 | 0/42 PASS | 0/42 PASS |
| E3 final `skipped` | <= 20 each | 6/11/4 PASS | 3/3/2 PASS |
| E4 new reason | none | none PASS | none PASS |
| E5 wall | reported | 530.2 s/run | 519.9 s/run |

E4 detail: every failed pick in all four cells carries the same
`intercept trigger (...)` diagnostic (the only note on those rows); 1 (A) / 2
(B) add the `fruit did not follow the gripper` composite, the control none — so
113's normalised key set is unchanged.

### Files

`logs/p59/run_p2.sh`; `logs/p59/p2/{A,B}_{77,101,202}.log`, `header.txt`,
`tree_md5_after.txt`, `batch_outer.log`; `logs/p59/p2_report.py` ->
`logs/p59/p2_report.txt`. `logs/` is gitignored (`.gitignore:7`): the phase-1
evidence was committed with `git add -f`, and these files need the same if they
are to be tracked. **This phase committed nothing.**
