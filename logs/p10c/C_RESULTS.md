# P10-C RESULTS (2026-10-17): the carry monitor extended to the two-line scripted catch - all pre-registered endpoints clear, all kills clear, on this branch

Pre-registration: `logs/p10/PREREG_MONITOR_TWOLINE.md` (+ the frozen amendment). Tree at
battery time: `tasks.py` **09c920c99b7a6a75d16e5a99dcda1872**, `rl_env.py`
**9bb43c4c9e8dc2740bd2c7f8e3f7e1c1** (the `TASKS_MD5` match verified); `trigger.py d7ec85fc`,
`runtime.py ffb76bfd`, `fruits.py` unchanged. Branch `p-supply`.

## 1. The battery (4 runs; identities proven)

| run | env | result |
| --- | --- | --- |
| `10_armA_diag` | the patch shape + `FRUIT_CARRY_DIAG=1`, knob off | 12/20, 197.7 s, 3.64 batch / 3.63 window |
| `20_armB_1` | + `FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_TWOLINE=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5` | 13/20, 196.7 s, 3.97 / 3.98 |
| `21_armB_2` | the same as 20 | **bit-identical to 20** (0 diff lines on the `[fruit]` stream) |
| `22_armB_diag` | the same as 20 + `FRUIT_CARRY_MONITOR_DIAG=1` | **bit-identical to 20 modulo the `[carry]`/`[monitor]` rows** (0 diff lines) - the diag is run-neutral |

Scenario: `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 SEED=5 HEADLESS=1
FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1`; `scripts/154_claim_run.sh` per
run.

**The knob-off byte-inertness of the P10-C diff**: the arm-A diag run replays the P10-A
record (`logs/p10/10_twoline_1.log`, measured pre-implementation) **0 diff lines** on the
`[fruit]` stream modulo the `[carry]`/`[monitor]`/`[ready]`/`[diag]` reporting rows. The
two-line knob-off path is byte-unchanged by the diff.

## 2. The endpoints (pre-registered order)

| # | endpoint | A (control) | B (treatment) | reading |
| --- | --- | --- | --- | --- |
| 1 | **primary: the pooled inter-placement interval** (186) | mean **16.53 s** (n=11, p50 17.30, p90 19.90, min 7.40, max 38.50) | mean **15.07 s** (n=12, p50 16.90, p90 25.00, min 0.10, max 32.30) | **-8.8 % (PASS, bar >= 5 %)**; the p90 rises (the branch's interval shape is bimodal) |
| 2 | the failed-carried class spans | carried-not-placed n=7, mean 15.05 s (attempt 1: 14.94 s) | carried-not-placed n=3, mean 13.03 s; **the paired same-attempt/fruit case: attempt 1 tomato 14.94 -> 8.94 s (-6.0 s)** | the fast-skip truncation is visible on the clean paired case; the class n shrank 7 -> 3 (the draw) |
| 3 | the window placed/min (reported) | 3.63 (batch 3.64) | **3.98 (batch 3.97)** | +9.6 % window, +9.1 % batch, in a near-identical batch span (197.7 -> 196.7 s) |
| 4 | **K2: clean-leg aborts <= 2 / 60 attempts** | - | **0** (2 fires; both on legs with `clean_slip_max` 19.0 mm and 100751.2 mm, i.e. escapes by the frozen <= 2.0 mm rule) | **PASS**; note fire-2's leg was a *no-grasp* leg (`grasped=False`, the fruit never held) - an escape by the metric, semantically not a held clean carry |
| 5 | the fire readout | - | 2 fires: `left grasp_lift tick=138/160 z=+1.80 asym@fire=4.71` (the carried escape, onset row 136) and `right grasp_lift tick=2/161 z=+0.64 asym@fire=3.85` (the no-grasp leg) | both fires early/late as the signal allowed; no re-seat (the frozen form) |
| 6 | the cycle / starved / gate | cycle mean 15.08 s; lock-on left 3.73 / right 5.27; starved polls left 19 / right 22; gate_open 0.0 s | cycle mean **14.58 s**; lock-on left 3.89 / right 6.65; starved polls (the 186 report); gate_open 0.0 s | cycle -3.3 %; lock-on left +4.3 % / right +26 % - **reported, not gated** (the Oracle's B2/B3 demotion; the direct interface read +8.8 % the same way) |

The per-arm split re-drew: A left 4/10 right 8/10 -> B left 8/10 right 5/10 (the W7-C
"compare per-arm classes, not per-arm rates" caveat - the fire timing re-phases the schedule
and re-draws the composition; the pooled numbers are the reading).

## 3. The kills (pre-registered; applied exactly)

| kill | verdict |
| --- | --- |
| 1. the treatment's motion budgets / floor FAIL (`105 --min-success-rate 0.5`) | **clear**: 105 PASS on 20 and 21 (13/20 = 65 % >= 50 %; every descent inside its profile's speed and lurch bound); `190` (patch reference, floor 0.5): success PASS, the fingerprint **differs** - recorded as the **attractor statement, not a kill** (the amended F2; a working fast-skip moves the branch by construction) |
| 2. K2 fires > 2 | **clear**: 0 clean-leg aborts |
| 3. a new failure reason appears | **clear**: the failure classes are the same two (carried-not-placed, the empty-notes class; "fruit did not follow the gripper", the no-grasp class); the counts moved 7+1 -> 3+4 |
| 4. any descent outside its motion budget | **clear**: 105 PASS on both treatment runs |
| 5. the primary interval does not fall by >= 5 % | **clear**: -8.8 % |

## 4. The mechanism

The fast-skip ends a doomed attempt at the lift-leg boundary, skipping the place leg and the
escape handling. Two fires per run: (i) the left carried escape (slip onset row 136/160, fired
at 138) - the paired same-attempt/fruit comparison against the control is **-6.0 s** (14.94 ->
8.94 s); (ii) the right no-grasp pear leg (fired at tick 2; the primitive's own no-grasp path
already shortens such attempts, so this fire's saving is not isolated). The batch then
delivers **+1 placement in the same span** (+8.8 % batch rate). The lock-on regression
(+26 % right) is the direct-interface B2 pattern reappearing on the two-line - the coupling
class: the fast-skip re-phases the schedule and re-draws the composition (left/right 4/8 ->
8/5), so per-arm rates move with the draw; the pooled rate and the interval are the honest
readings.

## 5. The no-harm bar

| item | status |
| --- | --- |
| the knob-off two-line pair bit-identical to the P10-A record | **PASS**: 0 diff lines modulo the reporting rows (the diag-filtered stream) |
| the B pair bit-identical | **PASS**: 20 vs 21, 0 diff lines |
| the diag run-neutral | **PASS**: 22 vs 20, 0 diff lines modulo `[carry]`/`[monitor]` |
| the knob-off acceptance (9/10 + `fingerprint: matches`; 365/365 vs `logs/p2d/90_accept.log`) | **pending** (`logs/p10c/30_accept_noharm.log`, running) |
| `selfcheck.sh` PASS | **pending** (the same chain) |
| `172` | **PASS**: 74 checks |

## 6. Verdict and the adoption path

**The lever passes its pre-registered gate on this branch: the primary interval -8.8 %
(>= 5 %), the rate +8.8-9.6 %, K2 0, no new reasons, the motion budgets clean, and the
knob-off tree byte-inert.** Per the standing discipline (one configuration is one sample of a
deterministic branch - the P9-A lesson), this is a positive *branch* result, not yet an
adoption: **the multi-seed confirmation (P10-C.1) is running** - the same battery at SEED=11
and SEED=23, A vs B, both with the diag (`logs/p10c/50..53`). If B is >= A pooled across the
seeds (and no kill fires), the adoption case is solid and the next step is a new
pre-registration for the two-line default flip (or the owner decision), with the re-baseline
list (the patch reference + the per-scenario fingerprints re-recorded).

**Caveats for any quotation:** (i) the pooled mean interval falls while the p90 rises - quote
both; (ii) the per-arm split re-drew (left 4/8 -> 8/5) - quote the pooled numbers and the
class split, not per-arm rate deltas; (iii) fire-2 was a no-grasp leg - the K2 count follows
the frozen slip metric (escapes), and the semantic no-grasp fire is recorded here; (iv) the
lock-on moved +26 % right (reported, not gated; the B2 pattern); (v) this is the patch
scenario at SEED=5 - one sample.
