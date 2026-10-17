# P10-C.2 RESULTS (2026-10-17): the slip-confirmation gate - all pre-registered endpoints clear, the pooled outcome now >= the control

Pre-registration: `logs/p10c/PREREG_CONFIRM_GATE.md` (frozen + the Oracle amendment). Tree at
battery time: `tasks.py` **22cc5b31a510ddcb747436d713f5604c**, `rl_env.py`
**d8a5790786b99471e0f6c2aa1f097d86** (the `TASKS_MD5` match verified); the P10-C pins otherwise.

## 1. The battery (5 runs)

| run | env | result |
| --- | --- | --- |
| `60_armA_noharm` | the patch shape, monitor off | **0 diff lines vs the P10-C record** modulo reporting rows - the P10-C.2 diff is byte-inert on the knob-off path |
| `61_seed5_B_gate` | the monitor + the gate at 8.0 mm | 13/20, 196.7 s, 3.97 batch / 3.98 window - **identical to the ungated P10-C B** (the gate inert: 0 cancels) |
| `62_seed11_B_gate` | the same | **10/20, 183.4 s, 3.27 / 3.21** - vs A 9/20 (2.64) and the ungated B 7/20 (2.40) |
| `63_seed23_B_gate` | the same | 16/20, 184.7 s, 5.20 / 5.35 - identical to the ungated B (the gate inert: 0 cancels) |
| `70_accept_noharm` | the shipped acceptance | 9/10 + `fingerprint: matches`; `logs/accept.log` **0 diff / 385/385** vs `logs/p2d/90_accept.log` |

## 2. The fire/cancel tables (`logs/p10c2/fire_table.py`)

| seed | fires | cancels | fired legs' clean_slip |
| --- | --- | --- | --- |
| 5 | 2 | 0 | 19.0 mm (the doomed tomato), 100751.2 mm (the no-grasp leg) |
| 11 | 6 | **1** | 263.7 / 312.8 / 1255.4 / 1330.1 / 1396.5 / 1631.8 mm; **the cancel = the right pear at 6.3 mm** (`[monitor] cancel right grasp_lift: tick=20/161 clean_slip=6.3mm < 8.0mm`) |
| 23 | 2 | 0 | 1421.6 mm, 805.4 mm |

## 3. The endpoints (pre-registered order)

1. **Primary: zero false positives - PASS.** (a) the frozen K2 aborts (fires with
   `clean_slip_max <= 2.0 mm`): **0** (the smallest fire is 19.0 mm); (b) the first-fire
   ground-truth: seed 5 the 19.0 mm doomed tomato (control: carried-not-placed), seed 11 the
   first fire is a 1396.5 mm escape (**the pear is cancelled** - the control placed it, and in
   the gated run it places again: `right pear placed=True 15.07s`, matching the control's
   15.1 s), seed 23 the 1421.6 mm escape. **0 ground-truth false positives.**
2. **The fire retention >= 10/15 - PASS.** The gated battery fires **10 times**, all on clear
   escapes (>= 19.0 mm). The seed-11 branch re-phased after the cancel (6 fires + 1 cancel
   there), so the count is read as the retained clean-fire population, not a leg-for-leg
   match.
3. The pooled intervals: **seed 5 15.07 s (= ungated) / seed 11 18.70 s (vs A 22.74, the
   ungated 23.92) / seed 23 11.22 s (= ungated, vs A 10.91)**; pooled mean **14.99 s vs the
   A controls' 16.73 s (-10.4 %)**.
4. The outcomes: **39/60 (gated) vs 38/60 (A) vs 36/60 (ungated)**; per seed 13/10/16 vs the
   controls' 12/9/17.
5. The fire table: section 2.

## 4. The kills (pre-registered; applied exactly)

| kill | verdict |
| --- | --- |
| 1. any ground-truth false positive | **clear**: 0 |
| 2. the fire retention < 10/15 | **clear**: 10 fires retained, all clear escapes |
| 3. the frozen K2 > 2/60 | **clear**: 0 |
| 4. a new failure reason | **clear**: the classes are the same two (carried-not-placed; the no-grasp class) on all three seeds |
| 5. a descent outside its motion budget | **clear**: 105 PASS on all three gated runs (13/20 = 65 %, 10/20 = 50 %, 16/20 = 80 % >= the 0.5 override; every descent inside its speed and lurch bound) |

## 5. The no-harm bar

| item | status |
| --- | --- |
| the knob-off two-line anchor replays the P10-C record | **PASS**: 0 diff lines modulo reporting rows |
| the knob-off acceptance | **PASS**: 9/10 + `fingerprint: matches` + `logs/accept.log` 385/385 identical to `logs/p2d/90_accept.log` |
| `selfcheck.sh` PASS | **PASS** (the implementation lane: 0 failures, 1 skipped) |
| `172` | **PASS** (74 checks; the implementation lane) |

## 6. Verdict and the adoption path

**All pre-registered endpoints and kills clear.** The gate does exactly what it was built to
do: it cancels the marginal-slide trips (the 6.3 mm pear - the placement-killer - and the
0.4 mm place1 leg at seed 11 in the ungated branch) while retaining every clear escape
(10 fires, all >= 19 mm); on the two seeds where no trip fell below the gate it is **inert**
(the branches are identical to the ungated runs); and where it acted (seed 11) the branch
re-phased into the best reading of the battery (10/20 vs the control's 9, interval 18.70 vs
22.74). The pooled outcome now reads **39/60 >= the control's 38/60 > the ungated 36/60**, and
the pooled interval **-10.4 %**.

**The adoption case is met** (the P10-C.1 pre-committed framework: B >= A pooled on the
interval with no kill firing). The next step is the **P10-C.3 adoption**: a new
pre-registration for the two-line default flip (the W7-A park-gate pattern: the monitor + the
gate resolve on for a two-line session with the env unset; an explicit `=0` restores), with
the re-baseline list (the two-line/patch references re-recorded) and the collector manifest
field (`collection.carry_monitor`, the W7-C.1 park_early pattern). The shipped single-arm
line is untouched (the acceptance is byte-identical).

**Caveats:** (i) the threshold 8.0 mm was calibrated on the 3-seed fire table (margins
1.7/5.1 mm); the Oracle's robustness note (9.5 mm, the gap midpoint) leaves the tested
results unchanged but is untested; (ii) the outcome +1/60 pooled is thin - the adoption rests
on the interval + the mechanism, not the placement count; (iii) three seeds remain three
samples.
