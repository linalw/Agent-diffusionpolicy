# P10-C.2 PREREG (FROZEN): the slip-magnitude confirmation gate for the two-line carry monitor

Frozen 2026-10-17 before any Tier-A run (the orchestrator). Tree pin recorded at battery time
(the implementation lane's md5). Branch `p-supply`; the P10-C.1 wrap at `523b78e`.

## Why (the P10-C/P10-C.1 fire accounting, `logs/p10c/C_RESULTS.md`)

The two-line carry monitor's fast-skip has a measured, seed-invariant **timing** mechanism (the
paired same-attempt cases: -6.0 s at seed 5, -5.0 s at seed 23, both with the same outcome
class) but the classifier's precision fails in the **marginal-slide zone**: of 15 fires across
the 3-seed battery, 13 were escapes (>= 13.1 mm; 11 of the 13 >= 53 mm) while **2 were ground-truth false
positives** - a place1 leg at 0.4 mm (counted by the frozen K2) and the seed-11 right pear at
6.3 mm **that the control placed** (the same leg, bit-identical to 161 ticks). The frozen K2
rule (<= 2.0 mm) misses the pear because the mild-slide zone (0.4-6.3 mm) did not exist in the
direct-interface validation (clean 0.02-1.43 mm, escapes 17.9+ mm).

## The one mechanism

`FRUIT_CARRY_MONITOR_CONFIRM_MM` (default **0** = the shipped form, byte-inert): when > 0, a
classifier trip counts as a fire **only if the leg's running `clean_slip_max` reaches the
threshold by the fast-skip site** (the decision point already exists; the tracker is the same
one `FRUIT_CARRY_DIAG` uses, proven run-neutral: the P10-C diag runs are bit-identical to
their non-diag pairs). The battery value: **8.0 mm** - calibrated on the fire table (false
positives 0.4/6.3 mm; the 12 held-leg correct fires 13.1-1646.1 mm plus the seed-5 no-grasp
leg 100751.2 mm; the 8 mm threshold sits in the measured gap, 1.7 mm above the largest false
positive (6.3 mm) and 5.1 mm below the smallest correct fire (13.1 mm)).

## Arms and scenario (Tier A)

| arm | env | notes |
| --- | --- | --- |
| A (controls) | the P10-C.1 A records at seeds 5/11/23 stand (knob off) | verified byte-inert vs the P10-C.2 diff by the knob-off replay (the no-harm bar) |
| **B** | the patch battery + `FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_TWOLINE=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5 FRUIT_CARRY_MONITOR_CONFIRM_MM=8.0` | 3 runs (SEED=5/11/23), all with `FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1` |

`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1 FRUIT_MOTION_REPORT=1
FRUIT_CYCLE_REPORT=1`; `scripts/154_claim_run.sh` per run.

## Endpoints (pre-registered)

1. **Primary: zero false positives** - (a) the frozen K2 aborts (fired legs with
   `clean_slip_max <= 2.0 mm`) = **0**, AND (b) zero first-fire ground-truth false positives
   (the paired-leg method: the first fired leg's control counterpart placed in the same-seed A
   record).
2. **The fire retention: >= 10 of the 15 P10-C.1 fires** (the 13 clear escapes; the two
   marginal fires cancelled by construction; the gray zone 8-13 mm may cost one).
3. The pooled interval per seed (reported; the P10-C.1 A records as the reference).
4. The outcomes per seed (reported).
5. The fire table: per seed, the fired legs' `clean_slip_max` + the cancelled trips.

## Kills (any one; applied exactly)

1. Any ground-truth false positive (a first fire whose control counterpart placed) - the
   primary endpoint failing;
2. the fire retention < 10/15;
3. the frozen K2 > 2/60;
4. a new failure reason appears;
5. any descent outside its motion budget (`105_motion_regression.py --min-success-rate 0.5`;
the seed-11 rate floor is a scenario property - both arms below 0.5, the P10-C.1 precedent;
the kill is the descent budgets).

## The no-harm bar

The knob-off two-line pair replays the P10-C record byte-identically (modulo reporting rows);
the knob-off acceptance 385/385 vs `logs/p2d/90_accept.log` (9/10 + fingerprint matches);
`selfcheck.sh` PASS; `172`.

## What this does NOT do

It does not touch the shipped defaults (all three knobs default off; the gate default 0 keeps
the P10-C behavior byte-for-byte); it does not re-open the outcome question (the seed table
stands - the outcome effect is draw-dominated); it does not change the park/routing/selection
logic.


---

## Pre-battery amendment (2026-10-17, the Oracle gate's required corrections; frozen before the battery)

The calibration sentence is corrected in place (the real margins are 1.7 mm above the largest
false positive and 5.1 mm below the smallest correct fire; the retention count includes the
seed-5 no-grasp leg). Kill 5 carries the seed-11 rate-floor carve-out. The escape count is
corrected to "13 escapes >= 13.1 mm; 11 >= 53 mm". Nothing else changes.
