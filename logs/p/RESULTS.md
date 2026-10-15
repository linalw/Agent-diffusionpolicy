# P1 RESULTS: the supply-density lever (the owner's #1)

Branch `p-supply` (from main `465941a`, tag `v0.16`). Pre-registration: `logs/p/PREREGISTRATION.md`
(written before any run). Tier A solo. Evidence: `logs/p/*.log`, the battery report
`logs/p/50_battery_report.txt`, the no-harm acceptance `logs/p/60_accept_noharm.log` +
`62_accept_claim.log`.

## 1. The lever

`FRUIT_SUPPLY_PATCH_DENSITY` (D, default 1.0) in `src/fruit_sorting/fruits.py`: on the patch
schedule the along-slice gaps divide by D (floor 0.085 m = `_release_clear`'s 0.08 m separation
rule + a margin) and the abreast probability rises toward 1 (`pair + (1-pair)*min(D-1,1)`).
D=1.5 -> slice 0.093-0.147 m, pair 0.80 (~8.9 -> ~15 fruit/belt-m). Default off: D=1 is
byte-identical (the 172 supply selftest, 52 checks, PASS; the acceptance below).

## 2. The battery (two-line, patch sheet, ATTEMPTS=20, SEED=5, balanced mix, park default on)

| config | success | placed/min | interval mean | p50 | p90 | per-attempt arm span | bit-identical double |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 00 control (D=1, 0.12 m/s) | 12/20 = 60 % | 3.64 | 16.53 s | 17.30 | 19.90 | 15.13 s | - |
| 10 D=1.5 | **15/20 = 75 %** | **4.48** | **13.34 s** | 13.50 | 23.60 | 15.04 s | yes (11: IDENTICAL) |
| 20 D=2.0 | 5/20 = 25 % | 1.53 | 39.22 s | 38.10 | 46.90 | - | yes (21: IDENTICAL) |
| 30 D=1.5 + 0.15 m/s | **17/20 = 85 %** | **5.31** | **11.10 s** | 11.50 | 20.50 | 15.09 s | - |
| 40 D=2.0 + 0.18 m/s | 10/20 = 50 % | 2.82 | 20.56 s | 18.60 | 40.60 | - | - |

**Dose-response with an optimum at D~1.5.** vs the control: the throughput **+23 %** (D=1.5) and
**+46 %** (D=1.5 + 0.15 m/s); the interval **-19 %** and **-33 %**; the success **+15** and **+25
points**. D=2.0 overshoots hard (25 %, the interval nearly triples).

## 3. The mechanism (what actually moved)

The `[cycle]` decomposition (the 186 report, the left arm, 10 attempts):

| segment | control | D=1.5 | D=1.5 + 0.15 |
| --- | --- | --- | --- |
| prepose / hover | 0.71 / 0.78 | 0.71 / 0.77 | 0.71 / 0.77 |
| descent | 3.03 | 2.99 | **2.25** |
| close / grip | 1.20 / 2.05 | 1.20 / 1.74 | 1.19 / 1.75 |
| lift | 1.77 | 1.77 | 1.79 |
| place / release | 3.09 / 1.90 | 3.28 / 1.94 | **3.78 / 2.17** |
| **arm span** | **15.13 s** | **15.04 s** | **15.09 s** |

And the placement-interval decomposition (the left arm):

| config | mean inter-placement | idle | attempts inside |
| --- | --- | --- | --- |
| control | 50.7 s | 10.3 s (20 %) | **40.4 s** |
| D=1.5 | **20.1 s** | 4.4 s (22 %) | **15.7 s** |
| D=1.5 + 0.15 | 22.4 s | 5.1 s (23 %) | 17.3 s |

**Reading (this corrects the W6-B/R3 "arrival-bound" framing):** the per-attempt arm span is
**constant (~15 s)** in every config - the density does **not** speed the cycle, and the
**lock-on latency does not fall** (left mean 3.73 -> 4.57 -> 4.27 s; right 5.27 -> 5.01 ->
6.08 s). The gain is that the **failed/empty attempts between two placements disappear**: the
left's inter-placement interval falls 50.7 -> 20.1 s (2.5x) with the idle fraction unchanged
(~22 %). So the interval was never purely arrival-bound; it was **cadence x success**, and the
density raises the success at a constant cadence. At D=1.5 + 0.15 the placement interval (11.10 s)
is within 15 % of the 9.6 s attempt span - **the per-attempt span is now the binding term**, not
the supply.

The faster belt trades **descent 3.03 -> 2.25 s** against **place + release 4.99 -> 5.95 s**
(the placed fruit accumulate in the lane faster, so the place leg has to clear them), net zero on
the span - and it costs the right arm's lock-on (5.01 -> 6.08 s).

**The failure classes (no new class):**

| config | "fruit did not follow the gripper" (pre-lift squeeze) | other |
| --- | --- | --- |
| control | 2 | carried-not-placed + no-grasp |
| D=1.5 | 2 | 2 carried-not-placed, 1 no-grasp |
| D=2.0 | 18 (~9 attempts) | mostly **no-grasp** - the crowding breaks the acquisition (the jaws meet the neighbours) |
| D=1.5 + 0.15 | **0** | 3 failures, all **carried-not-placed** (the W8-B loaded-slide class; lift 0.136-0.217 m) |
| D=2.0 + 0.18 | 12 | mixed |

So D=2.0's collapse is a **crowding/acquisition** mechanism (not a starvation one), and the best
config's residual is the single carried-not-placed class that R8-B named.

## 4. The verdict against the pre-registered criteria

- **Primary (the throughput improves AND the starvation/lock-on move as predicted): throughput
  PASS (+23 % / +46 %), interval PASS (-19 % / -33 %), the left's inter-placement 2.5x. The
  **lock-on does NOT fall** and the idle fraction does not fall (~22 %) - the pre-registered
  prediction was half right: the gain is the removal of the wasted attempts, not a faster lock-on.
  Published as measured, with the mechanism above.
- **Secondary (the success non-inferior within <= 15 points): PASS by a wide margin** - the
  success *rose* (+15 / +25 points). The owner's 不破不立 allowance was not needed.
- **Fail conditions:** (a) the starvation does not fall - the *starved-slot* count rises in
  absolute terms (41 -> 54 "no eligible fruit" lines at D=1.5) but that is the **denominator
  effect**: more selection instants fire per attempt because more attempts succeed; the
  rate-normalized read (the idle fraction 20 -> 22 %) is flat, so this item is read as
  **not-failed on the normalized metric, flagged on the raw count**; (b) no new class - **PASS**;
  (c) the motion budgets - **PASS** (`105_motion_regression.py` on 10 and 30: "every descent is
  inside its profile's speed and lurch bound"; the carry cones are reported on the dynamic line,
  not gated - the D=1.5 worst cone 4.58x and the 30's 1.86x, matching the pre-existing dynamic
  branch's reported range); (d) no crash or wedge - **PASS** (7/7 runs exit 0).
- **Determinism:** 10/11 and 20/21 are **bit-identical** (the `[fruit]` physics streams), so each
  config is one sample of a deterministic branch, as the project's convention requires.

## 5. The no-harm

- **Acceptance** (`logs/p/60_accept_noharm.log`): **9/10 = 90 %** (floor 75 %), 15.2 s/attempt,
  **motion gate PASS**, **`fingerprint: matches configs/motion_reference.json`**, exit 0. The
  single-arm shipped default is byte-unchanged (the density knob reads only on the patch schedule).
- `scripts/172_supply_selftest.py`: **52 checks PASS** (D=1 byte-identity of the patch-off
  scatter/wave/fixed streams preserved).

## 5b. The clearance on the D=1.5 branch (the per-config report)

`logs/p/31_density15_trace.log` (the trace-on run; it replays `10_density15.log`'s outcome
**bit-identically**: 20 attempts, 15 successes, 201.1 s span, 10.1 s/attempt, 13.4 s/success,
4.48 fruits/min):

> `[biarm] clearance trace: min link separation 0 mm at t=178.95s (openarm_left_hand vs
> openarm_right_hand), 22906 samples`

**One** event, at the hand-vs-hand link pair. **The attribution is the shared park pose, not a
reach conflict**: `_biarm_park` returns both arms to the *same* named pose
(`self._pose(arm, "ready")`, `tasks.py:4753` - the pose does not depend on the arm or the station),
so the two hands can coincide exactly. This is the same class as the W2 pre-W1 6.8 mm figure ("the
old branch's 10 s post-attempt freeze") and the W7-A 2.59 mm reading. Standing conditions hold: **no
arm-arm contact is possible in this build** (`openarm_flat_deinst.usda`
`enabledSelfCollisions=0`), and **no attempt failed by arm-arm contact** in this run. Read the
figure as **min 0 mm at the shared park**, not as a reach clearance; per the 2026-10-13 R5 decision
the clearance stays a per-config report and the F2 45 mm / zero-under-30 mm convention is **not**
re-imposed as a gate.

The D=2.0 / D=1.5+belt-0.15 branches were **not** trace-run (the battery's runs are trace-off); if
either is adopted, its own clearance pass is required before the reference is re-recorded.

## 6. Pins

`src/fruit_sorting/fruits.py` `88b76b572b16224313a0ff3860e2940c` (the density knob; `tasks.py`
unchanged at `3b15f3ff59e8923fea2b245adc7824b4`, `rl_env.py` unchanged at
`874349039e16ef75e68f75eeffa8b850`, so no `TASKS_MD5` follow is needed),
`scripts/199_p1_battery.sh` `3ff675c7772b737d9be9234669074289`.

## 7. The decision this hands over

Both D=1.5 configs pass the pre-registered gate. The **stronger** one (D=1.5 + belt 0.15 m/s,
85 %, 5.31 placed/min, 11.10 s interval) is a **scenario change on two axes** (supply density +
belt speed), so it needs its own scenario reference before it can be gated by
`190_twoline_gate.sh`. The **minimal** one (D=1.5 alone) is a single knob on the shipped patch
schedule. **Neither is flipped here**: per the standing owner decisions, a two-line supply change
is a scenario default and the flip is the owner's. The named recommendation: **adopt D=1.5 as the
two-line patch default, keep the belt at 0.12 m/s** (the speed axis buys +4.5 points at the cost
of the right arm's lock-on and a second reference), and re-record
`configs/motion_reference_patch.json` for the adopted branch.

The next binding term, measured here for the first time: **the per-attempt span (~15 s per arm,
9.6-10.1 s wall)**, of which the descent is 2.25-3.03 s, the place+release 4.99-5.95 s and the
grip 1.74-2.05 s. With the supply no longer binding, that is where the next lever belongs.