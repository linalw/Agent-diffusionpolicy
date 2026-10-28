# P56 phase 2 — `FRUIT_DIRECT_CONTINUOUS` (the multi-pick continuous-sorting episode)

Phase 2 of P56 (`.slim/deepwork/p52-model-lane.md` §9): the implementation of
`logs/p56/DESIGN.md` §3 and the pre-registered battery of `logs/p56/PREREG.md`,
with the two implementation deviations recorded in `logs/p56/PREREG_A1.md`.
Default **off**; no `configs/` file touched; no commit.

**Verdict.** The mode **works** and delivers the accounting and the scenario wiring
(15 picks in one episode, 15 distinct recorder indices/files, one reward, the belt
live throughout, `[bed-sel]` census at every selection), and it removes
**53.6 ticks = 0.45 s = 2.7 % of a pick** of sim time - inside the census's
2.97-4.45 % ceiling. **Nothing is adopted**: **P1 fails on its max** (median 80 at
the bar, max 110 > 90) because the 30-tick feed round the mode removes is
**load-bearing for the supply** - 8 of 14 transitions pay a 30-tick starvation
round, and **P6 fails as registered** (the continuation's start pose is outside
the 0.011 rad bar on 11/15 picks - but so is the **shipped** line's, on 14/15, so
the finding is *the bar*, plus two right-arm continuation outliers the batch does
not separate). By **F1** (P6 fails) the P2/P3/P4 readings are **void**; they are
reported as measured. P4, P5 pass; P3 fails on its own bar.

---

## 1. What was built (`src/fruit_sorting/rl_env.py`, md5 `10ac8773` -> `cfbce71d`)

`tasks.py` `b6de439c`, `control.py` `9384ff4f`, `scene.py` `27e3d64a`,
`fruits.py` `e81051c1`, `policy/runtime.py` `379ac706`, `policy/trigger.py`
`b09d3cb2` - all **unchanged**. The whole feature is one file, ~470 added lines
(≈150 code, the rest comments).

**Pins.** The measured tree (the one every recorded run used,
`logs/p56/p2/P2_header.txt`) is `rl_env.py` **`cfbce71d`**. The close-out edit is
**docstring only** (`_begin_pick`'s description of the continuation), verified by
reconstructing the measured file from the final one and matching the md5
(`cfbce71d`), the P42/R6-B precedent; the final tree is **`1845c2c4`**.

1. **The knob** (`__init__`, beside `_direct_feed`): `FRUIT_DIRECT_CONTINUOUS=<n>`,
   default `0`. Raises unless `presentation == "direct"` **and** `ablate == "none"`,
   and on a negative value. `n > 0` **implies** `FRUIT_DIRECT_FEED=1` (P55's
   feeder) - the two knobs are not separable or the A/B measures two things. A
   `[cont] enabled: picks_target=n feed=on(implied) ...` row is printed once.
2. **`reset` split**: `reset` keeps the run-level half (the `_loop_*` timer, the
   recorder abort, the RNG seed, the multi-pick counters, the 30-tick x rounds
   feed/select loop) and returns `_begin_pick(target)`. `_begin_pick` is the
   **unchanged** per-pick half: `self._episode += 1`, the target bookkeeping, the
   arm setup + settle, the trigger station, the ~45-field per-episode block,
   `policy.reset()` + `rtc.reset()`, `recorder.begin({"index": self._episode})`,
   `_observe()`. The index still increments **per pick** - it is the recorder's
   npz name, and two picks under one index would silently overwrite the first.
   `policy.reset()` being inside `_begin_pick` is what keeps PREREG **F2** from
   firing (the 2-frame obs history never spans two picks).
3. **`_finalize` continues** when the pick budget remains: it prints the pick's own
   `[rl] episode ... success=` row first (one row per pick, never zero, never two),
   accumulates `reward`/`ticks`/`placed`, prints `[cont] pick k/n: ... gap_ticks=`
   and starts pick *k+1*; only the *episode-level* rows (`[loop]`, the `[cont]`
   summary) wait for the real end. `StepResult.reward` stays that pick's own
   reward; the episode total is in `_outcome["continuous"]`.
4. **`_outcome` is cleared in `_begin_pick`** so a new pick cannot inherit the
   previous pick's `StepResult.reward`.
5. **`_begin_next_pick`** re-runs the **same** selection the reset runs -
   `select_target(state, reach_anywhere=False, direct=True)`, which refuses fruit on
   an output conveyor or above the main belt (`tasks.py:5709-5727`) and applies the
   same `_dynamic_select_floor()`, so the fruit just placed cannot be re-picked.
6. **The `[bed-sel]` census reaches the direct env** (`FRUIT_BED_DIAG=1`): the env
   never passed `select_target`'s `diag` list, so "the belt stays stocked" was not
   measurable on this interface at all. It is now printed by `_begin_pick` (and on
   the failed-selection path).
7. **`act` stops at the pick boundary**: `_finalize` sets `_pick_boundary`, `act`
   breaks on `_done or _pick_boundary` after `_apply` (and on the
   `_episode_events` path). Without it the finished pick's remaining 1-3 chunk
   actions would be applied to the **new** pick - a silent, unregistered
   experiment.
8. **The reduced per-pick setup** (continuation only, DESIGN A.1 row 7 "partly"):
   the active arm skips its redundant teleport to `ready` (the `grasp` teleport
   overwrites it) and the inactive arm is re-parked **only when the pick switches
   arms**. Measured both ways: the literal split gives **110, 110** ticks
   (`logs/p56/p0/C3_literal_split.log`: a temporary build with only the two skips
   reverted, the shipped file restored afterwards - `rl_env.py` `1845c2c4`), row
   7's "partly" gives the registered **50 / 80**. `PREREG_A1.md` A1.1.
9. **The starvation contract** (`PREREG_A1.md` A1.2): a failed selection round is
   30 ticks of belt travel (the reset's own unit) and the episode ends only after
   the reset's own bound, 40 rounds; every round prints
   `[cont] pick k/n: waiting for a candidate (round r/40)`. The design's literal
   "end on the first `None`" ended a 3-pick smoke at pick 3 with fruit on the belt.

Two **off-by-default** instruments, used in **both** arms:

- `FRUIT_GRASP_DIAG=1` -> `[grasp] episode N pick=k/n arm=a t0=T q_err_max=E`, one
  per pick: `max|q_arm - grasp|` after the settle (P6) and the pick's clock start
  `t0`; the inter-pick gap is `t0(k+1) - (t0(k) + ticks(k)/120)` in **both** arms.
- `FRUIT_BED_DIAG=1` -> the `[bed-sel]` block per selection (P3).

## 2. The knob-off no-harm (byte identity)

`logs/p56/p0/base_before.sh` / `base_after.sh`: the **identical** command line
before and after the edit, one episode, `--ablate scripted` (deterministic) and
`--ablate none`, seed 77, the patch scenario, `FRUIT_DIRECT_FEED=1`, **no** P56
instrument.

- **scripted: 44/44 `[fruit]` lines byte-identical.** That run goes through
  `reset` -> `_begin_pick` -> `_finalize` with the knob unset, so the refactor is
  inert on the shipped path. Re-run on the **final** tree
  (`logs/p56/p0/S_scripted_final.log`, `rl_env.py` `1845c2c4`): **44/44 identical
  to the pre-edit run again**.
- policy: 1 tick / 1 mm of pad-centre read (1885 vs 1886 ticks). A **same-tree
  repeat** (`R_repeat.log`) differs by **more** than the pre/post pair (9 diff
  lines, 1885 vs 1931 ticks, `grasped` True -> False, an extra `fruit did not
  follow the gripper`), so the pre/post delta is the known rendered-frame
  nondeterminism (AGENTS §3b), not the refactor.
- `scripts/selfcheck.sh`: **PASS, 0 failures** (`logs/selfcheck.log`).

## 3. The battery (`logs/p56/p2/`, one claim, seed 77)

`logs/p56/p2/run_batch.sh`; both arms `--record`, `FRUIT_BED_DIAG=1
FRUIT_GRASP_DIAG=1`; `moe_v13s` `61da390a`; the patch sheet; ACQ on (the P54
default for `direct`); park default (`back`); `FRUIT_POLICY_SEED=11`. Tree
`cfbce71d` (`P2_header.txt`). **A** = `FRUIT_DIRECT_FEED=1 --episodes 15` (15
picks in 15 episodes), **B** = `FRUIT_DIRECT_CONTINUOUS=15 --episodes 1` (15
picks in **1** episode). Wall: A **494.7 s**, B **471.1 s** (batch 1043 s for the
pair, 10:41:11 -> 10:58:34).

| | A (per-pick loop) | B (continuous) |
|---|---|---|
| picks / episodes | 15 / **15** | 15 / **1** |
| inter-pick gap (ticks, 14 transitions) | **140 x14** (unique) | 50, 80 x9, 110 x4 -> **med 80, max 110** |
| starvation rounds | **0** | **8** of 14 transitions (57 %), at picks 4,6,8,9,10,11,13,14 |
| per-pick ticks (sum) | 27 704 | 27 538 |
| sim span (first pick -> last end) | 247.2 s | 239.6 s (**-3.1 %**) |
| placed | **11/15** (0.733) | **8/15** (0.533) |
| placed/min (sim span) | 2.67 | 2.00 (**-25 %**) |
| wall / pick | 33.0 s | 31.4 s (-4.8 %) |
| right arm placed | **10/10** | 8/9 |
| left arm placed | 1/5 | **0/6** |
| `[bed-sel]` `window>=2` | 12/15 = 80.0 % | 11/15 = **73.3 %** |
| `[bed-sel]` on_belt median | 6 | 5 |
| first-tick `|q-grasp|_max` median (max) | 0.0114 (0.0147) | 0.0139 (**0.0330**) |
| recorder | 15 rows / 15 distinct index / 15 npz | **same** |
| `ticks_total` vs `Σ` | n/a | 27 538 == 27 538 |
| `reward_total` | n/a | 7.710133 (== `Σ` by construction; `Σ` from `index.json` = 7.710133333333333) |

`[cont] episode 14: picks=15/15 placed=8 reward=7.710133 ticks=27538
gap_ticks=86.4 gaps=[50, 80, 110, 80, 110, 80, 80, 80, 80, 110, 80, 80, 110, 80]`.

**The gap arithmetic is exact and structural**: `50` = one 30-tick `grasp`
teleport + the 20-tick settle; `+30` per arm switch (the inactive arm's park);
`+30` per starvation round. Mean saving **53.6 ticks/transition** (140 -> 86.4) =
0.45 s = 2.7 % of a 16.5 s pick, against the census's 2.97-4.45 % ceiling - the
mode is *not* faster in wall terms beyond that (B's wall/pick -4.8 % is inside the
feeder's own +11.1 % cost class, which both arms carry).

## 4. The mechanism (the phase's finding)

**The 30-tick feed round is load-bearing for the *supply*, not idle.** The direct
selector's catch floor is `_dynamic_select_floor()` ≈ **0.399 m**
(`_dynamic_pick_lead()` + 0.12 m/s x 1.5 s + 0.03 m), while the line-full
interlock counts the queue over `[pick_y-0.05, pick_y+0.45]` and **holds releases
while that queue is `FRUIT_QUEUE_MAX=6` deep** (`fruits.py:1657,1862`). The
catchable sliver inside the queue window is `[0.399, 0.45]` = **~5 cm = 0.43 s** of
belt travel. One 15 s pick passes the whole sliver; the queue fills with fruit
*below* the floor; the release pump holds and its due backlog is consumed as
`supply_skipped` (8 -> 16 -> 21 within the smoke); the next selection reads
**`window=0` with the belt packed** (`live=8 on_belt=8 admitted=0 window=0`, then
`window=1` one round later). Arm A never starves (0/14) because its reset *always*
spends those 30 ticks; B starves in 8/14 because it does not - and pays the same
30 ticks back whenever it does.

This is P33's aperture finding (AGENTS §1: "the band fills, the catchable window
does not") on the **direct** line, and it is also why the P56 census's "the belt is
already stocked at selection" was an artifact of the reset's own feed round. **The
"continuously stocked belt" the owner asked for is not a schedule property here: it
is a 5 cm aperture between the catch floor and the queue interlock.**

Secondary: the pooled placed delta (11 -> 8) is **not** a mode effect at this n -
the right arm reads 10/10 vs 8/9 and the left 1/5 vs 0/6, so the pooled number is
the arm-mix of the branch (B drew 6 left picks, A 5) plus one right-arm no-grasp.
Per F3/AGENTS §2 the two arms are different attractors from pick 1 (A's pick 1 is a
peach on the **right**, B's on the **left**), so no rate delta is claimed.

## 5. The endpoints (PREREG §2), read in the registered order

**P6 - the policy is in-distribution (read first).** `|q-grasp|_max <= 0.011 rad`
on >= 95 % of picks: A **1/15 = 6.7 %**, B **4/15 = 26.7 %** -> **FAIL** (and the
**shipped** line fails it too, so the bar is below what `teleport_joints` attains;
`PREREG_A1.md` A1.3). On the registered *purpose* (the continuation reproduces the
per-episode start state) the arms are equivalent **on the left** (0.0147 in both,
every pick) and close on the right (median 0.0112 vs 0.0114), with **two
outliers**: picks 5 and 15 at **0.0330 / 0.0217 rad** (3x / 2x the shipped
residual), both right-arm picks re-activated after being parked for exactly one
pick. Not separated at this n; the named discriminator is a per-joint dump in the
`[grasp]` row plus a `FRUIT_RESET_SETTLE` sweep.
**F1 fires on the letter -> P2/P3/P4 are void and nothing is adopted.**

**P1 - the per-pick gap.** median <= 80 **and** max <= 90: median **80** (at the
bar) and max **110** -> **FAIL**. The gap classes are 50 (same arm, 1/14), 80
(switch, 9/14) and 110 (a 30-tick starvation round, 4/14); the 30-tick rounds are
the whole of the failure and they are the mechanism of §4, not a tuning miss. The
literal `_begin_pick` split was measured first at **110 for every transition**
(`C3_literal_split.log`; `PREREG_A1.md` A1.1), so the registered 50/80 ladder is
what row 7's "partly" buys, and without it P1 would have failed outright.

**P2 - placed/min (non-inferiority; underpowered by design).** |placed_B - placed_A|
= **3** <= 4 -> PASS on the letter, at the per-seed bar's edge (+3 = the bar), and
**void** under F1. The rate is **2.00 vs 2.67 placed/min** (-25 %) on a *different
branch*; the arm split (right 8/9 vs 10/10, left 0/6 vs 1/5) says the pooled
delta is the arm mix, not the mode. **No speed claim** in either direction.

**P3 - the belt stock.** `window>=2` at >= 90 % of B's picks **and** B's median
`on_belt` >= A's: **11/15 = 73.3 %** and **5 < 6** -> **FAIL** (void under F1).
Note the bar is above what the **control** delivers (A = 12/15 = 80.0 %), so it
was not attainable by this scenario even without the mode - the honest statement
is that B is **1 pick** short of A (73.3 % vs 80.0 %) and that the census's
`window` distribution is what it is on the patch sheet under the feeder.

**P4 - no new failure reason.** B's normalised key set ⊆ A's ∪ the P43/P54
baseline set: **no new key** (`fruit did not follow the gripper` appears in B and
in the baseline; `fruit fell off the line` likewise) -> **PASS** (void under F1).

**P5 - the accounting.** `done` once per run (`[rl] rollout success 1/1` for B -
one logical episode - and `11/15` for A);
`index.json` **15 rows / 15 distinct `index` / 15 distinct `rollout_*.npz`** in
both arms' stores (the overwrite test: `_episode` increments per pick);
`ticks_total = 27 538 = Σ` exactly; `reward_total` is accumulated from the same
per-pick float (so `== Σ` to 1e-9 by construction - the `index.json` sum is
7.710133333333333, the printed `[cont]` row 7.710133 at 6 dp) -> **PASS**.

**F5 (wall).** Wall per pick **fell** 4.8 % (33.0 -> 31.4 s). No cost to report.
**F4 (supply).** 8 of 14 transitions needed a wait round = **57 %**, far above the
10 % bar -> the "continuous supply" half of the claim is **not** delivered by the
mode on this scenario (it is delivered by the reset's own feed round, which the
mode removes); the census's 0/11 was measured *with* that round.

## 6. What was not spent, and why

Only **seed 77** was claimed. `PREREG.md` §5 explicitly says the 15-pick pre-check
comes first and "if any of [P1's gap decomposition, P5's recorder test, P6's
pose bar] fail, the 51-minute batch is not spent": **P1 and P6 both fail** on the
mechanical read, so seeds 101/202 were not run. The spend is ~28 min of simulator
(the smoke battery, the no-harm pairs, and the A/B pair), one claim, no wedge, no
retry.

## 7. What the next registration would have to look like (named, not done)

1. **Aperture, not continuity.** The binding constraint is the 5 cm gap between the
   catch floor (0.399 m) and the queue interlock's upstream edge
   (`pick_y+0.45`): a continuous cell needs the *queue window* re-sized (a larger
   `FRUIT_QUEUE_MAX`, or an upstream edge that leaves a full catch window dry) -
   its own pre-registration, and it is a supply change, not an episode-structure
   change.
2. **P1's bar** must be registered with the supply's starvation rounds in it
   (e.g. median <= 80 and p90 <= 110), or the mode must be allowed to wait with a
   finer granularity than the reset's 30-tick round (a 4-tick re-check would have
   made 4 of the 4 observed starvation gaps 54 ticks instead of 110 - but that is
   a *post-hoc* tuning and was deliberately not done).
3. **P6's bar** must be set on the shipped residual (`PREREG_A1.md` A1.3) and the
   two right-arm outliers separated (per-joint dump + a settle sweep) before any
   continuity claim can be judged.
4. The **left arm is the class in both arms** (0/6 and 1/5) - the closed
   grip/carry class (`logs/p42/SIM_LIMIT.md`), untouched by this mode.

## 8. Files

- `logs/p56/P56_RESULTS.md` - this file.
- `logs/p56/PREREG_A1.md` - the two implementation deviations + P6's bar.
- `logs/p56/p2/` - `run_batch.sh`, `P2_header.txt`, `A_1.log`, `B_1.log`,
  `P2_report.txt`, `P56_113_A_B.txt`, `batch_outer.log`, `store/{A,B}/direct_none_seed77/`
  (15 npz + `index.json` each).
- `logs/p56/p0/` - `base_before.sh` / `base_after.sh` (+ headers and logs, the
  byte-identity pair), `smoke.sh`, `C5.log` (n=5), `C3.log` (the recorder
  certificate, n=3), `C3_norec.log` (the design-literal starvation build - it
  ends at pick 3), `C3_literal_split.log` (the 110-tick literal split),
  `R_repeat.log` (the same-tree reproducibility probe), `S_scripted_final.log`
  (the byte-identity re-run on the final tree), `rec_smoke{,_2}/`.
- `logs/p56/p2_report.py` - the P1-P6 report (re-derives everything from the logs).
- `logs/p56/DESIGN.md`, `logs/p56/PREREG.md`, `logs/p56/{continuity_census.py,CENSUS.txt}`
  - phase 1, unchanged.

## Addendum (after the close-out): the queue interlock is not the aperture

`logs/p56/P3_QUEUE_MAX.txt` - `FRUIT_QUEUE_MAX=12` (the interlock depth the
DESIGN named as one of the three sliver terms) leaves the 15-pick episode
**exactly as it was**: placed **8/15**, gap classes **[50, 80x9, 110x4]**, only
the stock depth moves (`on_belt` median 5 -> 6, peaks 13-14). The `[bed-sel]`
rows name the real aperture: at a starvation round the belt's fruit are either
**past the station** (5 rows, along -0.514..-0.097) or **inside the 0.399 m
catch floor** (4 rows, along +0.125..+0.284), with only the ~[0.399, 0.55] m
band usable - **0.15 m, 2-4 fruit, against the 1.8 m (15 fruit) one pick
traverses**. So the continuous episode is **starve-limited by the pick's own belt
consumption**, not by the feeder; the fix is a station-geometry / belt-speed /
staged-queue change, each with its own pre-registration.
