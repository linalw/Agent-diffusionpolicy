# P100 PREREG - is the park return a lever?

Pinned **before** any claimed cell (`logs/p100/{C,T}{5,6,101,202}.log`,
`X5{C,T}`) is run. At pin time only three 2-3-attempt smokes had been read
(`/tmp/opencode/p100_smoke_ready.log`, `p100_smoke_t45.log`,
`p100_smoke_t4590.log`, `p100_smoke_t6075.log`); no 20-attempt cell existed.
`PREREG.md5` holds the md5 of this file.

## 0. The question, and why this is the last non-semantic time item

P99 (`logs/p99/CENSUS.md` §0) names the **park return** as the largest remaining
non-semantic term of the two-line's slot loop: **2.47 s (seed 5) / 2.69 s
(seed 6) of motion per attempt slot**, against a park gate of 0.03 / 0.82 s, a
feed gap of 0.27 / 0.25 s and 0.17 / 0.86 s of starved polls. Halved over two
arms that is **~1.24 / 1.35 s per placement = 13.2 % / 12.2 % of the
9.38 / 11.08 s inter-placement interval**.

Everything else on the clock is spent: the profile blocks (release shipped P87;
place and lift negative P88/P89), the speed union and the fail-fast (P83/P84/
P85-ACC), the candidate planning (P99: the 18.2 % is cross-lane, i.e. a sort
error), and the pre-pose (P96/P97, reverted by P98). The **return is the only
free-space motion left, and it carries no payload** - so unlike the lift/carry/
place legs it is not exposed to `logs/p42/SIM_LIMIT.md`'s loaded-slide class.

## 1. The code path, quoted

```
worker finally:  self._biarm_park(arm)                        # tasks.py:9763
  _biarm_park   : gate loop (station owner / other arm's grip-or-payload-clear)
                  -> self.go_ready(arm)                       # :10240
go_ready        : self._ready_move(name)                      # :7110
_ready_move     : scope = self._active_session is None and not self.two_line_enabled()
                  skip  = scope and FRUIT_READY_SKIP=1        # -> False on the two-line
                  self._transit_to(side, "ready", settle=120 if not scope else ...)
_transit_to     : _catch_up_drive  (20 ticks)                 # :3244
                  -> _ready_transit(ticks=90, settle=120)     # name == "ready"
_ready_transit  : _lift_clear (step cap FRUIT_READY_LIFT_STEP=0.04 rad/tick, <=420)
                  _catch_up_drive (20/40)                     # second re-anchor
                  _blend_to(ready, ticks=90, settle=120)      # :3459
_recover_ready  : only if err > TRANSIT_TOL (0.08)             # :3501
```

So the block is **`catch_up` + `lift` + `blend` + `settle`**, and only the last
two are fixed: `_blend_to` runs a min-jerk ramp of `ticks` samples and then holds
the target for `settle` ticks. The 3-attempt shipped smoke reads
`[ready] … catch_up=20 lift=44-55 blend=90 settle=120` → **274-299 ticks**, which
is exactly the `park moving → park done` interval P99 measures.

**The knobs that already exist, and their status on this path.**
`FRUIT_READY_SKIP` / `_SETTLE` / `_DIAG` / `_TRANSIT` are P9-A's ready-transit
levers, and all three control ones are **single-arm scoped**
(`scope = self._active_session is None and not self.two_line_enabled()`): on the
two-line `skip` is off and the settle is the hardcoded 120, so `_ready_settle()`
is never read. `FRUIT_ARM_PARK` (P43) moved the *inactive direct arm's reset pose*
and is shipped for the direct presentation only; `FRUIT_BIARM_PARK_EARLY` (W6-C,
shipped, W7-A) opens the **gate** earlier - P99 measures that gate at 0.03 / 0.82 s
and it is *not* this block; `FRUIT_BIARM_HOT_ARM` (R3 L3, default off) replaces
the park with a station-side hold and was **measured negative** (the hold's
convergence blend costs the same as the park); `FRUIT_BIARM_PREFETCH` (W6-C L1,
default off, a hook) reserves the next target across the park and was a
**measured null** (0/40 reservations). So no shipped knob moves the park's
*clock*, and the public cell is the profile's.

## 2. The lever

**A two-line-scoped park profile**: `FRUIT_BIARM_PARK_BLEND` (the `_blend_to`
ramp, ticks) and `FRUIT_BIARM_PARK_SETTLE` (its convergence hold), resolved by
one function `tasks.park_profile_resolution(two_line)` that returns the **shipped
90/120 on every path that is not a two-line session** - including the driver's
own pre-session prime transit - so the single arm, the shared-station pipeline,
the hybrid canary and the direct/policy presentation are byte-identical **by
construction**. `PARK_TWO_LINE_DEFAULT = False`: the shipped tree resolves
90/120 on every path and the measured arm is the explicit pair.

**The cell: `blend=60 settle=75` = 135 ticks against the shipped 210, i.e.
-75 ticks = -0.625 s (-29.8 % of the fixed clock).** Chosen from the smoke
ladder, not from the model, with two pre-registered clauses:

* the achieved post-park pose residual `post_err` must stay **<= 0.05 rad** on
  every park (the shipped achieved value is 0.013-0.017; the recovery bound
  `TRANSIT_TOL` is 0.08, and `_recover_ready` - which would pay an extra
  lift + blend - is the failure mode a short settle invites);
* the peak **commanded** per-tick joint step (`q_step`, arithmetic:
  `1.875 * max|target-start| / blend`, reported on the `[ready]` row) must stay
  **<= 0.15 rad/tick**, the posture probe's own threshold
  (`tasks.py:3396`; the arm's `maxJointVelocity` is 5.45 rad/s = 0.045 rad/tick).

The smoke ladder (one 3-attempt seed-5 cell each, read as mechanism only):

| blend / settle | ticks | park blocks (s) | `post_err` | `rec` | `q_step` max |
| --- | --- | --- | --- | --- | --- |
| 90 / 120 (shipped) | 210 | 2.2 / 2.5 / 2.2 | 0.0131-0.0169 | 0 | 0.0094-0.0650 |
| 45 / 120 | 165 | - | 0.0131-0.0206 | 0 | 0.1298 |
| 45 / 90 | 135 | 1.6 / 1.9 / 1.8 | 0.0095-0.0295 | 0 | 0.1284 |
| **60 / 75** | **135** | **1.6 / 1.9 / 1.8** | **0.0137-0.0423** | **0** | **0.0963** |
| 45 / 45 | 90 | - | 0.0621-**0.1222** | **1** | 0.0812 |

`45/45` is the arm that shows the failure mode: one park ended 0.122 rad from
ready and paid `_recover_ready` (`rec=1`). `45/90` buys the same −75 ticks with
two thirds of the settle left in a *hold* and a 33 % larger `q_step`; `60/75`
spends the same total on **motion** with more posture margin, so it is the
registered form. **The same joint-space line is walked** - `_blend_to`
interpolates the two configurations in a time-warped min-jerk ramp, so a shorter
ramp visits the same configurations in the same order and only their timing
changes; the settle is a hold at the ramp's target. What the lever changes is
therefore *when* the arm is where, not *where* it goes.

## 3. Expected value, stated up front

The park is a **motion, not a wait**: P99 measures the gate at 0.03 / 0.82 s and
only 0.44 s of feed + polls behind the park, so the arm starts returning
immediately after it places and the return sits on **its own** critical path.

* **mechanism**: the park block falls **-0.625 s ± 0.03** at every seed and on
  both arms, by exactly the profile arithmetic;
* **per-attempt slot dead time**: 2.94 → 2.32 s (seed 5), 4.62 → 4.00 s (seed 6);
* **per-arm cycle** (attempt span 15.08 s + dead time): 18.02 → 17.40 s (−3.5 %);
* **pooled interval**: **-0.31 s (−3.3 %)** if the overlap is flat - two arms
  halve the per-arm saving - so 9.38 → 9.07 s (seed 5). Seed 6's interval is not
  cycle/2 (its arms are not saturated), so its prediction is the weaker
  "≤ -0.31 s";
* **floor on the claim**: P99's lesson is that *a wait is not the interval*. The
  honest downside is **0.0 s**: if the arms' slack absorbs the return (idle
  18-21 % per arm in P80), the interval does not move.

**What would show the removal does not transfer** (each is a registered read,
not a post-hoc rescue):

1. **the per-arm idle rises by ~as much as the park fell** - the arm reaches
   ready earlier and then waits for fruit (the supply becomes the constraint);
2. **the feed gap grows** - the feeder's schedule is attempt-boundary relative
   (P83's class: the abort shortened the span and the next selection re-phased);
3. **`attempts/placement` rises** - P83's decomposition
   (`interval = attempts/placement × attempt span + idle`);
4. **the attempt span moves at all** - the lever touches no attempt-phase code,
   so a span change is a moved branch, not the lever, and it invalidates the
   `interval` reading rather than the block.

## 4. Cells

`ATTEMPTS=20`, the shipped two-line default, one claim per run
(`scripts/154_claim_run.sh`), instrumentation identical on **both** arms:

```
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_PLACE_TRACE=1 FRUIT_BIARM_PARK_TRACE=1 FRUIT_READY_DIAG=1
```

| cell | seed | park | used for |
| --- | --- | --- | --- |
| `C5` `C6` `C101` `C202` | 5, 6, 101, 202 | unset (shipped 90/120) | the controls |
| `T5` `T6` `T101` `T202` | 5, 6, 101, 202 | `FRUIT_BIARM_PARK_BLEND=60 FRUIT_BIARM_PARK_SETTLE=75` | the treatment |
| `X5C` `X5T` | 5 | as above | the **clearance census only** (`FRUIT_BIARM_TRACE=1 FRUIT_BIARM_TRACE_FILE=…`); an invasive link read, so **no rate comes from these** |

Seeds 5 and 6 are the record's; **101 and 202 are fresh** and are the ones the
count claim would rest on (P93: two seeds reuse the same two control branches).
Two fresh seeds at 20 attempts is the same budget P93/P94 used, and this phase's
count is a **report**: `ATTEMPTS=20` cannot resolve a 3-5 point movement.

## 5. Endpoints and the decision rule

**P1 - the mechanism (primary).** `park done − park moving` per park, mean per
arm per seed. **PASS** iff the delta against the same-seed control lies in
**[-0.69, -0.56] s** on **both arms at all four seeds** (the arithmetic is exact,
so a miss is a finding, not noise). Reported beside it: the `[ready]`
decomposition (`catch_up`, `lift`, `blend`, `settle`), `q_step`, `post_err` and
`rec`.

**P1b - the pose guard.** `post_err <= 0.05` on **every** park of every treatment
cell, `q_step <= 0.15` on every park, and **zero** `rec=1`. A violation is a
FAIL and stops the phase.

**P2 - the delivered interval.** Pooled and per arm, mean and p50/p90, from the
same derivation P99 validated (`attempt end = station-acquired + sim`, placement
= end − `[cycle] return+end`). **PASS** iff the pooled mean falls at **every**
seed. A rise at any seed is a FAIL (`P88`/`P89`'s shape).

**P3 - throughput and wall (reported, one soft clause).** Both `placed/min`
denominators (placement window and batch span) and `placed/min wall` from the
per-line stamps (`logs/p80/stamp.py`). **Clause**: `placed/min wall` must not
fall by more than 3 % at any seed *whose interval improves* (an accounting
sanity check on the wall, not a rate claim).

**P4 - the class ledger (reported).** Reason keys per cell, the `cnp` /
never-held / `fell off the line` counts, and `force_min == 0` legs. **PASS** iff
no **new** reason key appears in a treatment cell that is absent from its
same-seed control. Counts are never gated (P84/P92/P93: a 20-attempt two-line
count is a branch draw whose own control swings 16 → 10 between seeds).

**P5 - the landing (gate).** Every payload-present release reads `on_belt`
(`FRUIT_PLACE_TRACE`; `release_bottom >= 0`). The upstream-lost rows
(`release_bottom = -184 mm`) are reported separately - they are P86/P87's own
class - and are not a landing failure.

**P6 - the motion budgets (gate).** `scripts/105_motion_regression.py
--min-success-rate 0.0` on every treatment cell; a treatment's fingerprint
**DIFFERS by construction** (the park is inside the run's sim clock), so the
gate is budgets only. The controls are gated on budgets and on their
**line-identity replay** (§6 G1).

**P7 - the clearance census (reported, with a stop clause).** The `X5` pair,
read the way W2/W7-A read it: the exact minimum from the JSONL (`min_m`), the
count and share of samples `< 30 mm` and `< 10 mm`, the link pairs, and the
bands' phase attribution (`scripts/179_w2_bands.py`). R5 makes clearance a
**report, not a gate** (no arm-arm contact is possible in this build:
`enabledSelfCollisions=0`) - but a **new minimum below the control's own** is a
stop clause: it is a finding the adoption would have to carry.

**P8 - inertness (gate).** (a) `C5` must replay `logs/p99/C5.log` with the
phase's own `[fruit] [ready]` rows dropped, line for line - in one shot that
proves the tree inert, the control valid and `FRUIT_READY_DIAG` neutral;
(b) `scripts/accept.sh` with the knob unset must read **8/10 + `fingerprint:
matches`** against `configs/motion_reference.json` (`30fb99f8`) with its 419
`[fruit]` lines identical to `logs/p94/accept_final.log`;
(c) with the knob **set** the acceptance *is allowed to move* (the shipped
acceptance runs the two-line, so the park is on its path) - and then a flip owes
both two-line-side references and a `=0` A/B that reproduces the pre-flip record.

**The decision rule.** Ship (flip `PARK_TWO_LINE_DEFAULT = True`, re-record
`configs/motion_reference.json` + `..._twoline.json` from same-batch runs) iff
**P1 ∧ P1b ∧ P2 ∧ P4 ∧ P5 ∧ P6 ∧ (P7's stop clause not fired)**; P3 is reported
and P2 is the delivered clause that matters. Otherwise **no flip**, the measured
arm stays the explicit pair, and the write-up names the clause that failed.

## 6. The two admissibility proofs, defined before the run

**G1 - the control is the shipped branch, and the instrument is neutral.** `C5`
vs `logs/p99/C5.log` with `[fruit] [ready]` rows dropped must be **identical**;
likewise `C6` vs `logs/p99/C6.log`. `logs/p99` is itself a replay of
`logs/p94/{T5,T6}` (974/974, 970/970), so the chain reaches the record.

**G2 - the mechanism is the profile.** Every treatment park must print
`[ready] … blend=60 settle=75`, and the `[biarm] park profile:` row must read
`FRUIT_BIARM_PARK=(1)(explicit) … blend=60 settle=75 (135 ticks; shipped 210,
saved 75)`; every control park must print `blend=90 settle=120` with
`=0(scope-off)`.

## 7. What this phase does not claim

* **no rate**: a 20-attempt two-line count is a branch draw (P84: 16 → 10
  between seeds on the *same* configuration). The count is a report.
* **no clearance change**: the swept *geometry* is the same joint-space line
  (only its timing changes), so any clearance difference is a **timing overlap**
  finding, not a new swept volume - and it is quoted as a report.
* **no attempt-phase change**: the lever is outside `run()`'s attempt; the
  `[cycle]` blocks and the descent budgets are expected to be unchanged, and a
  movement there is a branch, not the lever.
* **wall**: measured, never inferred, and on this box a two-line cell costs
  1.19-1.69× its sim seconds (P82); the wall column is quoted with that caveat.
