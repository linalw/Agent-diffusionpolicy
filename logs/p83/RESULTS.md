# P83 — fail fast: the abort halves the failed attempt, and the cell's throughput does not follow

Registered in `logs/p83/PREREG.md` (**md5 `1e1e6345c0d23166691f195f40657269`**, pinned
before the phase's first run, unchanged since). **Nothing adopted, no default
changed, no commit, `configs/` untouched** (`8952c320` / `eb697f23` both stand).

Owner directive: *the cell pays a full attempt for every failure; fail fast.*

## 0. The answer in one table

Shipped scripted scenario, `ATTEMPTS=20`, the P80 instrumentation set
(`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`), one claim per run;
`FRUIT_FAIL_FAST=150 FRUIT_CARRY_DIAG=1` on the treatment arms.

| arm | seed | executed | placed | s/attempt | interval mean / p90 | **failed attempt** | placed/min **window** | placed/min **batch** | wall/pick | wall/sim | placed/min **wall** | trips |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **C5** control replay | 5 | 19 | 12 | 15.10 | 26.72 / 36.90 s | **15.16 s** (1819 tk) | **2.25** | 2.08 | 25.33 s | 1.39 | 1.50 | 0 |
| **D5** tracker only | 5 | 19 | 12 | 15.10 | 26.72 / 36.90 s | 15.16 s | 2.25 | 2.08 | 25.59 s | 1.41 | 1.48 | 0 |
| **F5** fail-fast 150 mm | 5 | 14 | 6 | **12.30** | **35.26 / 87.30 s** | **10.01 s** (1202 tk) | **1.70** | 1.68 | 21.62 s | 1.41 | 1.19 | **7** |
| **D6** tracker only | 6 | 19 | 13 | 15.00 | 26.12 / 38.50 s | 14.57 s (1748 tk) | 2.30 | 2.27 | 25.48 s | 1.41 | 1.61 | 0 |
| **F6** fail-fast 150 mm | 6 | 20 | 11 | **12.80** | **27.38 / 55.40 s** | **9.42 s** (1131 tk) | **2.19** | 2.08 | 22.30 s | 1.41 | 1.48 | **8** |

* **The mechanism works, and it replicates exactly.** The failed attempt's mean
  span falls **15.16 → 10.01 s** at seed 5 and **14.57 → 9.42 s** at seed 6: the
  same **-5.14 s = -617 ticks** at both seeds. `s/attempt` falls -2.80 / -2.20 s
  and wall/pick -14.6 / -11.5 %.
* **The throughput does not follow.** The pooled interval is **+32.0 %** worse at
  seed 5 and **+4.8 %** worse at seed 6, and placed/min falls at both seeds on
  **both** denominators (window 2.25 → 1.70 / 2.30 → 2.19; batch 2.08 → 1.68 /
  2.27 → 2.08). The count falls 12 → 6 and 13 → 11.
* **Why:** the interval is `attempts/placement × attempt span + idle`. The span
  term fell and the other two rose: attempts/placement **1.583 → 2.333** (seed 5)
  and **1.462 → 1.818** (seed 6), and the idle term **2.81 → 6.56 s** at seed 5
  (six starved slots) against **4.19 → 4.11 s** at seed 6 (none). So the abort
  bought 5.14 s per failed attempt and the branch spent 6-9 s more per placement.
* **The registered rule's verdict is not adopted**, on T1/T2/T3 at both seeds
  (§8); the mechanism gate M1/M2 passes and M3 fails on G6's letter (§6).

## 1. What the abort is, and what it is not

`FRUIT_FAIL_FAST=<mm>` (`tasks.py`, `parse_fail_fast`), **unset/0 = off = the
shipped path.** The trip is one compare on the W8-B tracker's own per-leg
operand (`clean_slip_max`, the payload's displacement in the leg's frame — the
number the `[carry]` row already prints) against the threshold, taken **inside
the carry leg's tick loop**. On a trip:

* the leg **breaks at that tick** (the rest of the profile and the leg's 50-tick
  tail — the 30-tick settle plus the `FRUIT_CARRY_FREEZE` ramp — do not run);
* the attempt then ends at one of the **two early-exit sites the P7-2b monitor
  already uses** (the lift boundary, and the place boundary which is *before*
  the release/retreat block), through the same one predicate
  `_attempt_ended_early() = _carry_monitor_skip or _fail_fast_trip`;
* **no note is added** to `result.notes`, so the failure-reason parser sees what
  the run-out would have seen: `grasped` is still computed by the shipped
  peak-lift predicate and `placed` stays `False` → the class stays `cnp`;
* the payload is recycled by `run()`'s own `finally` (`held = False`, unprotect)
  and the arm's next pre-pose is the driver's `go_ready` → `_goto` teleport,
  the path every shipped failure already takes. **No new exception type**, so
  `20_pick_place.py`, the collector and the two-line worker handle it exactly
  as they handle a `not grasped` return. The direct/policy handover cannot reach
  it (`_fail_fast_active = threshold > 0 and scripted`).

**It is a clock lever on a loss that already happened.** It does not fix the
grip, does not convert a `cnp` into a placement, and changes no failure class.

### The threshold: 150 mm, and why that number is not arbitrary

The pre-run corpus census (`logs/p83/census.py` → `census.txt`; 43 scripted logs
that already carry `[carry]` rows, **249 placed attempts / 165 failed**), joined
per attempt to its own outcome row:

| population | n | p50 | p90 | p99 | **max** |
| --- | --- | --- | --- | --- | --- |
| **placed** attempts, worst leg | 249 | 0.1 mm | 11.6 | 62.1 | **76.3 mm** |
| **failed** attempts, worst leg | 165 | 1152.5 mm | 1402.3 | 1683.0 | 3830.7 mm |

`>= 150 mm`: **0/249** placed, **164/165** failed. So 150 mm is a **1.97x margin
over the worst placed leg** ever measured on this line, and the code **refuses
any value below 100 mm** (a 1.31x margin) at task construction — a "fail fast"
that can end a leg that was going to place is not a lever, it is a coin flip.

## 2. The aborted-leg audit (E9) — it fires only on a payload that is already gone

**15 trips across the two treatment arms** (F5 7, F6 8), every one of them:

| arm | leg | trip tick / leg | clean_slip | sep / gap | force at trip | force_min | contacts | onset → loss |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F5 | grasp_lift | **t143 / 163** | 157.9 mm | 61.4 / 60.7 | **0.00 N** | 0.00 N | **0** | 93 → 127 |
| F5 | grasp_lift | **t159 / 161** | 157.0 | 55.6 / 54.9 | **0.00** | 0.00 | 0 | 133 → 138 |
| F5 | grasp_lift | **t7 / 171** | 168.6 | 22.2 / 22.2 | **0.00** | 0.00 | 0 | 1 → 1 |
| F5 | place0 | **t106 / 386** | 150.6 | 48.6 / 48.6 | **0.00** | 0.00 | 0 | 2 → 2 |
| F5 | place0 | **t116 / 390** | 158.5 | 60.5 / 59.7 | **0.00** | 0.00 | 0 | 77 → 96 |
| F5 | grasp_lift | **t143 / 166** | 154.9 | 55.4 / 54.6 | **0.00** | 0.00 | 0 | 109 → 129 |
| F5 | grasp_lift | **t137 / 160** | 152.9 | 58.1 / 57.4 | **0.00** | 0.00 | 0 | 55 → 115 |
| F6 | grasp_lift | **t140 / 161** | 156.8 | 57.3 / 56.5 | **0.00** | 0.00 | 0 | 104 → 126 |
| F6 | place0 | **t92 / 403** | 150.8 | 49.8 / 49.8 | **0.00** | 0.00 | 0 | 2 → 2 |
| F6 | grasp_lift | **t127 / 162** | 158.2 | 60.9 / 60.2 | **0.00** | 0.00 | 0 | 63 → 110 |
| F6 | grasp_lift | **t124 / 160** | 157.7 | 62.1 / 61.4 | **0.00** | 0.00 | 0 | 95 → 108 |
| F6 | place0 | **t121 / 375** | 157.0 | 53.9 / 53.2 | **0.00** | 0.00 | 0 | 62 → 94 |
| F6 | grasp_lift | **t158 / 162** | 151.6 | 55.2 / 54.4 | **0.00** | 0.00 | 0 | 133 → 144 |
| F6 | grasp_lift | **t143 / 159** | 162.4 | 60.5 / 59.8 | **0.00** | 0.00 | 0 | 65 → 123 |
| F6 | place0 | **t110 / 399** | 150.2 | 47.1 / 47.1 | **0.00** | 0.00 | 0 | 3 → 3 |

**15/15 trips fire with `force = 0.00 N` *and* `contacts = 0` at the trip tick**,
and `force_min = 0.00 N` over the leg: the pinch is already gone when the trip
fires. The `[carry]` row of each aborted leg prints `ticks=<trip>/<total>` — the
log's own proof the leg was cut (e.g. `ticks=8/171`).

Two trip families, and both are real losses:

* **9 of 15** trip near the end of the **lift** (t124-t159 of 159-171). These are
  the W8-B loaded slide: onset at 55-133, contact lost 2-49 ticks later, then the
  displacement keeps growing to the threshold.
* **5 of 15** trip **inside the place leg** (t92-t121 of 375-403), three with
  `onset_row = 2-3` — a payload that was *already* out at the place leg's start
  (`sep ≈ gap`, `contacts = 0` from tick 2), i.e. the loss happened at the end of
  the lift and the place leg was pure run-out. Those are the legs the abort
  saves the most: 253-310 ticks of it.
* **1 of 15** (F5 t7/171) is a **never-held** payload (the tenth `grasp_lift` trip): `sep = gap = 22.2 mm` on a
  53.8 mm fruit, `onset_row = 1`, `loss_row = 1`, and the leg's own record reads
  `stored pad centre 415 mm from the measured pads` — the left arm's pre-contact
  acquisition failure (P47/P48's catch-up class), not a carry loss. The abort
  fires because a payload that is not in the hand moves 150 mm relative to it in
  ~7 ticks. It is harmless (that attempt was already lost) but it is why G6's
  reason clause fires (§6).

### None of them would have placed (G4/G5)

* **G4** passes: 7/7 and 8/8 trips with `force = 0.00 N` or `contacts = 0`, and
  `force_min = 0.00 N` on every one of the 15.
* **G5** passes: on the treatment's **17 placed attempts**, all **34 carry legs
  read `ticks = X/X`** (not one was shortened), and the worst placed-leg
  `clean_slip_max` is **0.1 mm (F5) / 19.8 mm (F6)** — against the 150 mm
  threshold. Across the two seeds the placed population sits at 0.3-13 % of the
  trip value.
* The corpus census above says the same thing offline: **0/249** placed attempts
  ever reach 150 mm on any leg, and the threshold is 1.97x the worst of them.

**So the class is the outcome, not the abort**: every aborted attempt scored
`cnp` (7/8 in F5, 8/9 in F6; the ninth in each is the never-held one, which the
shipped peak-lift predicate scores `fruit did not follow the gripper`).

## 3. The cost of a failed attempt (E3) — the lever's own arithmetic

| | control | treatment | delta |
| --- | --- | --- | --- |
| seed 5, failed attempt mean span | 15.157 s (7 attempts) | **10.013 s** (8) | **-5.144 s = -617 ticks** |
| seed 6, failed attempt mean span | 14.567 s (6) | **9.422 s** (9) | **-5.144 s = -617 ticks** |
| seed 5, all attempts `s/attempt` | 15.10 | 12.30 | -2.80 s |
| seed 6, all attempts `s/attempt` | 15.00 | 12.80 | -2.20 s |

The **-5.144 s / -617 ticks** is identical at both seeds because it is
arithmetic, not a draw: an aborted leg skips **1-310 ticks of its own running
profile** plus its 50-tick tail, and the attempt then skips the whole release
block (~253 ticks) and the retreat (~76) — so a trip in the *lift* (9 of 15, plus the never-held one)
saves the place leg as well, and a trip inside the *place* leg (5 of 15) keeps
its already-spent part. The per-trip ledger in the `[fail-fast]` rows reads
`leg_left + 50` = **69 / 51 / 213 / 329 / 323 / 72 / 72** ticks at seed 5 and
**70 / 360 / 84 / 85 / 303 / 53 / 65 / 338** at seed 6.

**A placed attempt does not get slower or faster** (E5): 15.05 → 15.45 s at seed
5 and 15.15 → 15.48 s at seed 6 — and that +0.3-0.4 s is **the branch's leg mix**,
not the abort: the per-leg durations of the placed attempts are the same to the
tick (`grasp_lift` 170.0 vs 169.9 ticks at seed 5; `place1` 257.0 vs 248.4), but
F5 drew 6 `place1` legs and no `place0` while D5 drew 11 `place1` + 1 `place0`
(366 ticks).

## 4. The interval and both denominators — the throughput does not follow

The interval is `attempts/placement × attempt span + idle` (my own decomposition,
same parser; the "idle" term is what is left, including the starved slots):

| arm | interval | attempts/placement | × span | idle | starved slots |
| --- | --- | --- | --- | --- | --- |
| C5 | 26.72 s | 1.583 | 23.90 | 2.81 | 1 |
| **F5** | **35.26 s** | **2.333** | 28.70 | **6.56** | **6** |
| D6 | 26.12 s | 1.462 | 21.94 | 4.19 | 1 |
| **F6** | **27.38 s** | **1.818** | 23.28 | 4.11 | **0** |

**The span term fell and the other two rose.** If the attempts/placement ratio had
stayed at the control's, the -2.80 / -2.20 s per attempt would have taken the
interval to ~22.3 s (seed 5) and ~23.0 s (seed 6) — i.e. the abort *is* worth
**-16 % / -12 %** of the interval at the control's own failure rate. What it
cannot do is set that rate.

* **Seed 5** is the worse draw: **6 of 20 slots starved** (`no eligible fruit`,
slots 14-19, after slot 13), and the idle term rose with them. The treatment also
executed only 14 attempts, so its count is 6/14.
* **Seed 6** is the clean comparison: **20/20 slots executed, 0 starved**, and the
whole interval rise is the ratio term (1.462 → 1.818) while idle is flat
(4.19 → 4.11 s).

**The count is a draw, and it is reported as one (R0/R1).** Pooled the two seeds
read 25/38 (65.8 %) control vs 17/34 (50.0 %) treatment; the failure *class* is
unchanged in kind (`cnp` everywhere except the one never-held attempt per arm),
but the treatment's branches presented a stream on which the line failed more
often (seed 5: 8 failures where the control had 7; seed 6: 9 where the control had
6). **Two seeds cannot separate "the abort's re-timed presentation is harder" from
"the branch draw is harder"**, and the registration forbids reading a count
difference as the lever's. That is the honest limit of this phase.

## 5. The wall (E7) — measured per line, never inferred

| arm | wall | wall/pick | sim/pick | wall/sim | placed/min wall |
| --- | --- | --- | --- | --- | --- |
| C5 | 481.3 s | 25.33 s | 18.2 s | 1.39 | 1.50 |
| D5 | 486.2 s | 25.59 s | 18.2 s | 1.41 | 1.48 |
| **F5** | **302.7 s** | **21.62 s** | 15.3 s | 1.41 | **1.19** |
| D6 | 484.1 s | 25.48 s | 18.1 s | 1.41 | 1.61 |
| **F6** | **446.1 s** | **22.30 s** | 15.9 s | 1.41 | **1.48** |

**wall/pick falls (-14.6 % / -11.5 %) and `placed/min wall` falls too**
(1.50 → 1.19, 1.61 → 1.48), because a run with fewer picks divides a much smaller
wall by a smaller count. The wall/sim factor is **flat at 1.41** in all four
instrumented arms: the abort changes no harness cost (the tracker's own wall cost
is C5 481.3 → D5 486.2 s = +1.0 %, inside the stamp's noise). **Quote the wall
rate, not wall/pick**, or the number flatters a run that placed less.

## 6. The guards (PREREG §5) — every one measured

| # | guard | verdict | evidence |
| --- | --- | --- | --- |
| **G1** | off-path inertness | **PASS** | `logs/p82/p82_report.py --same logs/p80/S20.log logs/p83/C5.log` → `IDENTICAL`, **710/710** `[fruit]` lines |
| **G2** | tracker neutrality | **PASS at both seeds** | `D5` = `C5` and `D6` = `S6` on **710/710** and **708/708** physics lines (the `[carry]`/`[diag] carry-assist` rows dropped) — the W8-B tracker (`tcp_pose`, `jaw_separation`, `joint_positions`, one tactile set per tick) is **run-neutral on the scripted line**, so `F` vs `C` differs by the abort alone |
| **G3** | in-batch prefix identity | **PASS** | F5's first **57** physics lines and F6's first **59** are identical to the control's, and the first trip sits exactly at the boundary (the trip row is the first line that is not in the control) |
| **G4** | trip = lost payload | **PASS** | 15/15 trips: `force = 0.00 N` or `contacts = 0`, `force_min = 0.00 N` |
| **G5** | no placed leg shortened | **PASS** | 34/34 carry legs of the 17 placed attempts read `ticks = X/X`; worst placed-leg `clean_slip_max` 0.1 / 19.8 mm |
| **G6** | no new failure reason | **FAIL by its letter** | 1 new text, `fruit did not follow the gripper`, in **both** treatment arms — see below |
| **G7** | motion budgets | **PASS** | `105`: worst descent `|v|max` 0.113 (C5) / 0.120 (F5) / 0.110 (F6) against budgets 0.160-0.161; lurch 0.017-0.027 against 0.291; carry cone reported (the dynamic line's convention); the only FAIL is the standing 0.75 rate floor |
| **G8** | accounted, no wedge | **PASS** | 19 = 12+7, 19 = 12+7, 14 = 6+8, 19 = 13+6, 20 = 11+9; no run wedged, no retry storm, `diverted` 1/1/2/1/1 |
| **G9** | the 10-attempt acceptance (the AGENTS step for a `tasks.py` change) | **PASS** | `SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p83/accept_noharm.log FRUIT_MOTION_REPORT=1 scripts/accept.sh` → **6/9, `fingerprint: matches configs/motion_reference.json`**, and its **346/346 `[fruit]` lines are byte-identical to `logs/p80/S10.log`**; the only FAIL is the standing 0.75 rate floor |

**G6's one failure is a letter, and the measurement says so.** The new text comes
from **one attempt per treatment arm** that was **never held**: F5's trip
`t7/171` (`sep = gap = 22.2 mm`, `onset_row = 1`, `stored pad centre 415 mm from
the measured pads`, `force servo: gap=22.2 sep=22.2 closed=15.00 trips=38` — the
R11-A.1 left pre-contact acquisition signature). Its `grasped` is decided by the
**shipped** peak-lift predicate (`lift = +0.000 m`), i.e. the run-out would have
scored exactly the same class, and **the seed-6 control itself carries that
reason** (S6/D6: 1 `fruit did not follow the gripper`). So the reason set is not
new to the line — it is new to *that branch*. The registered rule fires anyway,
and §8 reports it as a failure; it does not change the recommendation, which
T1/T2/T3 already fail.

## 7. The mechanism the phase measured, and one that it did not expect

* **The trip is a clean, force-free checkpoint.** `clear_slip >= 150 mm` and
  `force = 0.00 N` agree on 15/15 trips: by the time the displacement reaches
  1.97x the worst placed leg, the pads are empty. Quote the pair, not the slip
  alone.
* **The leg cut is visible in the leg's own row** (`ticks=<trip>/<total>`) and
  the leg's `[motion]` row reads `steps=<trip+1>` — a batch report can audit every
  abort without a new instrument.
* **The freed time does not become picks** (seed 6 is the clean read: 0 starved
  slots, -2.20 s/attempt, +1.3 s of interval). The cell's placement rate is set by
  the presentation, which is the P33/P58 "aperture/cadence" finding arriving from
  the other side: **the wait is not where the time goes *and* the failure is not
  where the throughput is.**
* **Seed 5's six starved slots are a supply-state read, not a trip effect.** They
  are six consecutive slots at the *end* of the run (14-19), while the four
  remaining live fruit sat at along 0.105 / 0.339 / 0.626 (plus one past the
  station at -0.56), and the pool's counters read `released = 54, fell_off = 43`
  against C5's `23 / 17` — the belt delivered far more fruit than the arm took
  and shed the rest over the end (`[bed-fall]` rows: `y = -0.92..-1.08`, `z ~ 0.02`
  = unattended belt losses, P32's cadence artifact, not payloads dropped by the
  abort). The probe that names the refusing predicate is
  `logs/p83/probe_bed.log` (§7b).

### 7b. The starvation probe (post-hoc, not an arm)

`logs/p83/probe_bed.sh` re-runs F5's scenario verbatim with `FRUIT_BED_DIAG=1`
(the tree's own pure-reporting read added in P32 phase A: one row per candidate
with the **first predicate that refused it**, plus one `[bed-sel]` summary per
selection). It reproduces F5 exactly — 14 attempts, 6 placed, 7 trips, the same
fruit sequence, `sim = 172.8 s` — so it is a read of that branch, not a new one.

At each of the six starved slots the live set is the same four bodies, and the
diag names every refusal:

```
[bed-sel] attempt 14  live=4 on_belt=3 admitted=2 window=0 pick=none skipped=85
    strawberry along=-0.560 x=1.082 z=1.364 -> off belt (output conveyor)
    peach      along=+0.626 x=0.282 z=1.197 -> diverted (max_retries)
    apple      along=+0.105 x=0.301 z=1.199 -> below catch floor 0.105 < 0.399
    pear       along=+0.339 x=0.360 z=1.200 -> below catch floor 0.339 < 0.399
```

* the **only** body above the 0.399 m catch floor (the peach, 0.626) is
  **diverted** — it failed twice and the reject policy (`FRUIT_MAX_RETRIES`) took
  it off the line;
* the apple (0.105) and the pear (0.339) are **inside** the catch floor and only
  drift downstream as the slots burn (0.06 m per starved slot — a starved slot
  does not advance the belt loop, so the whole pool creeps);
* the strawberry is on the **output conveyor** (`x = 1.08`, `z = 1.364`), refused
  as off-belt by the shipped rule;
* the feeder has **nothing to release** (`admitted = 2-0`, `skipped = 85`,
  `pump_next` within 0.01 s of `t` at the last slot), because the driver pumps
  the supply only at an attempt boundary.

**So the six lost slots are a pool state — a diverted upstream fruit plus two
inside the catch floor — not an effect of the abort.** The abort does not touch
the feeder, the diverter or the belt; and the seed-6 arm starves **0/20 slots**
while showing the same 5.14 s saving, which is the control for that reading. What
the probe does add is the mechanism of the *idle* term: at this turn-around the
catchable band is 0.40-0.85 m (0.45 m ≈ 3.75 s of belt travel) and a slot that
finds it empty cannot refill until the next attempt boundary pumps the supply.

## 8. The registered decision (PREREG §6)

**Mechanism gate:**
* **M1 = G4 + G5 → PASS** (15/15 trips are empty-pinch; 34/34 placed legs complete).
* **M2 = the failed-attempt cost falls >= 3.0 s → PASS** at both seeds, and by the
  same amount: **-5.144 s = -617 ticks**.
* **M3 = G1, G2, G3, G6, G7, G8 → FAIL** on G6's letter only (one new reason
  text, §6).

**Throughput gate:** all three fail at both seeds.

| | seed 5 | seed 6 | bar |
| --- | --- | --- | --- |
| **T1** interval | 26.72 → **35.26 s** (**+32.0 %**) | 26.12 → **27.38 s** (**+4.8 %**) | <= -8 % → **FAIL** both |
| **T2** count | 12/19 → 6/14 | 13/19 → 11/20 | >= control - 1 → **FAIL** both |
| **T3** placed/min | window 2.25 → 1.70, batch 2.08 → 1.68 | window 2.30 → 2.19, batch 2.27 → 2.08 | improve both → **FAIL** both |

> **Verdict: NOT ADOPTED.** The lever does exactly what it was built to do —
> a lost payload costs **5.14 s / 617 ticks less** per failure, at both seeds, to
> the tick — and the cell's throughput **does not improve**, because the interval's
> other two terms (attempts per placement and idle) rose, and the count is a
> branch draw that two seeds cannot attribute. `FRUIT_FAIL_FAST` stays
> **default off**; no default changes and nothing is committed.

**What would reopen it.** A scenario where the *presentation* is not the binding
term — e.g. the two-line, where the scheduler overlaps two arms and a parked arm
waits on the other rather than on the belt (P80/P81: its clock is 1.87x and its
per-attempt span is the single arm's). With a spare slot per failure the abort's
5.14 s is a duty-cycle gain rather than re-drawn fruit. That is its own
pre-registration.

## 9. What this phase does not claim (residuals)

* **No default change, no adoption, no commit, `configs/` untouched.**
* **The count is not a rate** (R0/R1): the two seeds read 25/38 vs 17/34, and the
  per-arm/presentation mix moves with the branch.
* **The abort's effect on *which* fruit the branch presents is not separated from
  the branch draw.** A third seed would halve the ambiguity; it was not spent.
* **The direct/policy path is out of scope** — the knob resolves to off there by
  construction, and its own P10-C monitor is a *leg-boundary* classifier skip that
  cannot save the leg's remainder.
* **The two-line inherits the knob** (it runs the scripted primitive), but it was
  not measured here.
* **The starved slots at seed 5 are a supply-state observation**, not attributed
  to the abort (§7b).
* **The 0.75 motion-gate rate floor fails on every arm including the control** —
  it is the standing P71/P72 branch (63-68 %), not this phase's.

## 10. Evidence and pins

* PREREG `logs/p83/PREREG.md` (**`1e1e6345…`**, `PREREG.md5`), the pre-run corpus
  census `logs/p83/census.py` + `census.txt`, the battery driver
  `logs/p83/run_p83.sh` + `battery_driver.log`, `logs/p83/one_run.sh` (the P80
  stamp contract), the report `logs/p83/p83_report.py` + `p83_report.txt`
  (`--check` runs every registered guard and **exits 1 by design** here: G6's
  letter fires, §6), the motion gates `logs/p83/{C5,F5,F6}.gate`.
* Logs + wall stamps: `logs/p83/{C5,D5,F5,D6,F6}.log` / `.stamps` /
  `.driver.log`; the probe `logs/p83/probe_bed.log` (+ `probe_bed.sh`).
* Selfcheck leg `scripts/245_p83_failfast_selftest.py` (65 checks: the resolver
  table, the 100 mm floor, the single trip site, the attempt-local latch, the
  `scripted` scope, the `guard_armed` arming clause, the one-predicate early exit,
  no `notes` entry, the restored step cap, the one call site). `scripts/selfcheck.sh`
  **PASS, 0 failures**.
* Acceptance (no-harm, 10 attempts, the shipped scenario):
  `logs/p83/accept_noharm.log` (+ `.driver`) — **6/9, `fingerprint: matches`**,
  **346/346 `[fruit]` lines identical to `logs/p80/S10.log`**.
* Pins: `tasks.py` **`f1e44af6`**, `rl_env.py` **`d786279c`** (the metadata-only
  `TASKS_MD5` follow), `scripts/245_p83_failfast_selftest.py` **`086c6022`**,
  `scripts/selfcheck.sh` **`39b8916f`**; `configs/motion_reference.json`
  **`8952c320`** and `configs/motion_reference_twoline.json` **`eb697f23`** both
  **untouched** (no reference re-recorded: the scripted line is byte-unchanged,
  `C5` and the acceptance prove it).
