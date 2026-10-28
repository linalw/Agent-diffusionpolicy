# P56 PREREG — `FRUIT_DIRECT_CONTINUOUS` (the multi-pick continuous-sorting episode)

Written **before** any run, from the phase-1 census (`logs/p56/DESIGN.md`,
`logs/p56/CENSUS.txt`). The offline phase established the arithmetic; this file
fixes what the simulator phase is allowed to conclude.

## 0. The question

Does a **multi-pick episode** (one `reset` per *n* picks; the belt and the
feeder live throughout; a re-selection after every place) turn the direct
interface into a continuous sorting cell **without costing placements**, and
does it deliver the scenario properties (a stocked belt at every pick, one
logical episode, one reward)?

The census pre-registers the ceiling: the reset is **140 ticks = 1.167 s of sim
per pick (6.4-6.7 % of the span)** and 50-80 of those ticks are load-bearing, so
the mode can save at most **2.97-4.45 % of a pick (≈ +3.5 % placed/min)**. **No
endpoint below asks for more than that**, and the rate endpoint is a
non-inferiority, not a gain.

## 1. The arms

| arm | env | what it isolates |
|---|---|---|
| **A** control | `FRUIT_DIRECT_FEED=1` (per-episode loop) | "continuous supply, per-pick episode" — the shipped driver shape with the feeder on |
| **B** treatment | `FRUIT_DIRECT_CONTINUOUS=15 FRUIT_DIRECT_FEED=1` | "continuous supply **and** continuous episode" |

**The feeder is identical in both arms** (`FRUIT_DIRECT_FEED=1`): the census
measured the feeder as its own object (+11 mm stock, +11.1 % wall) and P56 must
not re-measure it by accident. `FRUIT_DIRECT_CONTINUOUS` implies the feeder
(§3.2 of the design), and arm A sets it explicitly so the two arms differ in
exactly one thing.

**Arm C (report only, not re-spent):** the shipped default (feeder unset) is
already measured — `logs/p54/video_continuous` (12 picks, 8/12, gap 140,
`spawner.update` on 1.56 % of ticks). It is the reference for "what the shipped
line's supply looks like", not a third batch.

**Configuration fixed in both arms** (the P43/P54 protocol, verbatim):
`checkpoints/moe_v13s/policy_best.pt` (`61da390a`) on both; `execute_steps=4`,
`ddim=16`, camera 240×424; `FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25`; the trigger defaults
(`FRUIT_POLICY_TRIGGER=arrival`, lead 0.9, lateral 0.16) **with ACQ on** (the
P54 shipped default for `direct`); the park default (`FRUIT_ARM_PARK` unset →
`back`, P43); `FRUIT_BED_DIAG=1` **in both arms** (§2 P3 needs the `[bed-sel]`
`window` count, and an asymmetric instrument is not a measurement).

**Seeds / structure:** `RUNS=3`, seeds `77 101 202`, policy seed 11, interleaved
**A then B** per seed (the P54 batch shape), one claim per run, one
`logs/p56/P0_header.txt` recording the tree md5s (the `rl_env.py` pin will
differ from `a1ae217a` — the mode is a `src/` change once the gate funds it).

**The driver's episode count differs between the arms, and this is the easiest
way to wreck the batch:** arm A runs `--episodes 15` (15 picks = 15 episodes);
arm B runs **`--episodes 1`** with `FRUIT_DIRECT_CONTINUOUS=15` (1 episode = 15
picks). Using `--episodes 15` on arm B would deliver **225 picks**, and the two
arms would then differ in run length as well as structure. The batch driver must
assert `picks_seen == 15` per run from the `[rl] episode` rows before it reports
anything.

**Unit:** one **pick** = one `[rl] episode` row (success or failure). 3 × 15 =
**45 picks per arm**, 90 picks total.

## 2. Endpoints (the decision rule, written first)

**P1 — the per-pick gap (primary; mechanical, deterministic).**
The sim ticks from one pick's `_finalize` to the next pick's first `act` must
fall from **140** (measured, both source runs, 11/11) to **≤ 80** (the
arm-switch case; the same-arm case is 50). Measured from the `[cont]`/`[bed-sel]` rows'
`gap_ticks` and cross-checked against consecutive episode `start_tick`s.
*Pass bar:* median ≤ 80 and max ≤ 90.

**P2 — placed/min (non-inferiority, reported with its interval).**
Placed picks per **sim** minute = `placed / (total sim span / 60)`, where the
span **includes** the inter-pick gaps (that is the term the mode removes), per
arm, pooled and per run.
*Pass bar:* the pooled placed count is within **4 picks** of the control's
(≈ 9 points) **and** no single seed is worse by more than **3 picks**.
*Power, stated up front:* at 45 picks/arm and a ~55-60 % base the binomial sd is
~3.3 picks, so a −5 % *relative* bar would false-fail ~1 run in 3. **P2 is
therefore deliberately loose** — it exists to catch a *collapse* (the ACQ-style
regression that reads 16/45 vs 34/45), not to certify a 3 % gain. **No speed
claim is made from P2 in either direction.**

**P3 — the belt stock (the scenario claim).**
From the `[bed-sel]` blocks (an existing format: `tasks.py:5469-5518`), per
selection: **`window`** = the candidates at/above the catch floor (`usable +
chosen`, the "usable" count the endpoint means), `on_belt`, `live`, and the
chosen row's `along`. Cross-check: `spawner._queue_depth()` (fruit in
`[pick_y−0.05, pick_y+0.45]`, `fruits.py:1862`) is the width of the station
buffer.
*Pass bar:* `window ≥ 2` at **≥ 90 %** of the picks in arm B, and the arm-B
median `on_belt` ≥ the control's. (`window ≥ 2` = "one being picked, one behind
it" — the operational meaning of a stocked line.) Today's logs cannot report it,
which is why `FRUIT_BED_DIAG` is in the fixed configuration.

**P4 — no new failure reason.**
Normalised through `scripts/113_rl_report.py`'s `reasons()` (digits stripped).
*Pass bar:* the arm-B key set ⊆ the arm-A key set ∪ the P43 baseline set. A new
key is a **FAIL** even if the rate is fine (the P38/P41 precedent).

**P5 — the accounting (mechanical).**
- `done=True` exactly once per run, at pick 15 (or at the honest early end).
- The recorder's `index.json` holds **15 rows with 15 distinct `index` values**
  and 15 distinct `rollout_*.npz` files in one run dir (**the overwrite test**:
  `_episode` must increment per pick, `rl_env.py:1042`).
- `reward_total == Σ` per-pick rewards to 1e-9, and `ticks_total == Σ` per-pick
  ticks.
*Pass bar:* all three exact.

**P6 — the policy is in-distribution (the manipulation check).**
The first control tick of **every** pick reports the active arm within
**0.011 rad** of `grasp` (the demos' own frame-0 bar, `rl_env.py:2303-2306`),
i.e. the continuation reproduced the per-episode loop's start state.
*Pass bar:* ≥ 95 % of picks within bar. **Read P6 before P2/P3/P4.**

## 3. Falsifiers (each stops the phase)

- **F1 (OOD):** if P6 fails, arm B's policy input is not the training
  distribution → P2/P3/P4 are **void**, and the phase reports the mechanism
  (which pose/channel diverged) only. Consistent with P54's lesson that the
  *configuration* was the finding.
- **F2 (the design's own kill):** if the implementation keeps the policy's obs
  history across picks (`policy.reset()` not called per pick) the arms differ in
  the policy's input, not just in the episode structure → **stop, re-scope**;
  the result would be "a multi-pick policy", a different experiment.
- **F3 (branch):** if arms A and B land in different attractors in all three
  seeds, P2 is reported as **per-run place counts with the branch named**
  (AGENTS §2) and the gate carries on P1/P3/P4/P5/P6 alone. No pooled rate.
- **F4 (supply):** if `select_target` returns `None` mid-episode in > 10 % of
  picks in arm B, the feeder is not keeping the belt stocked → P3 FAILS and the
  "continuous supply" half of the claim is not delivered (the continuity is then
  a burst-per-pick line with an n-pick wrapper, which is **not** the owner's
  scenario).
- **F5 (wall):** if wall per pick rises > 5 % over arm A, that is reported as the
  cost; the census already pre-attributes +11.1 % to the feeder, so a *further*
  rise is the mode's own cost and it is a finding, not a surprise.
- **F6 (the ceiling):** if P1 passes but the measured placed/min *falls* by more
  than the P2 bar, the continuity trades placements for ticks — report it as
  such and adopt nothing (the P46/P51 precedent: speed is real, the count is
  branch-drawn).

## 4. What the phase may and may not conclude

**May:** the mode delivers the scenario (P3, P5), the gap falls to the arithmetic
floor (P1), the policy is unharmed (P4, P6), the rate does not collapse (P2).
**May not:** that the cell is *faster* in wall (it is not — the gain is 0.5-0.75 s
of sim inside a 15.7 s cycle and the feeder costs +11.1 % wall), or that it
raises the success rate (nothing in the design touches the grasp), or that it
replaces the hybrid canary as the interface of record (R5-decisions item 5
stands).

**Adoption, if the gate passes:** the mode ships **opt-in** (default 0) with the
`[cont]` + `[bed-sel]` rows, and a *default flip* would be its own pre-registration
at the WS-4.2 **N = 5** convention. If the gate fails, the shipped tree is
unchanged and `FRUIT_DIRECT_FEED` remains the default-off hook it is today.

## 5. N, cost, and the order of the spend

- **Batch:** 6 runs × 15 picks = 90 picks, one claim, interleaved A/B per seed.
  Measured cost of exactly this shape (P54 phase 1, `logs/p54/p1/batch_outer.log`
  `wall=3070s`): **~51 min** for the batch, ~30 s of simulator start per run
  included, on this machine with no video capture. Add ~2 min for the header and
  the report.
- **Cheaper pre-check (recommended first, ~8 min):** a 1-run-per-arm smoke
  (seed 77, 15 picks) that only certifies the **mechanical** items — P1's gap
  decomposition, P5's recorder/overwrite test, P6's grasp-pose bar, and that the
  `[bed-sel]` block prints. If any of those fail, the 51-minute batch is not spent.
- **The prior spend P56 does not cover:** the feeder's own A/B (`FRUIT_DIRECT_FEED`
  on/off, the same seeds). The census gives it a prior (stock +11 mm, wall
  +11.1 %, different branch) but no gate. It is P55's named next measurement and
  it should be **run before or with** P56, because arm A's interpretation
  ("continuous supply, per-pick episode") *is* that measurement's treatment arm.

## 6. The record this phase must leave

`logs/p56/{DESIGN,PREREG}.md`, `logs/p56/{continuity_census.py,CENSUS.txt}`,
then `logs/p56/P0_header.txt`, `logs/p56/{A,B}_{1..3}.log`, `logs/p56/p0_report.py`'s
table, and a WORKLOG "P56" entry quoting: the gap (per pick, per arm), the
`usable`/`queue` distributions, the per-pick wall, the placed counts **per run**,
and the P6 bar. Every number carries its branch.
