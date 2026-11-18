# P207 pre-registration - the emitted joint target's rate cap

**Question.** The owner reports occasional distorted poses and jitter. The P201/P202
clips measure the emitted target's per-waypoint step as p50 0.018-0.021 rad, p95
0.055-0.19 rad, maximum 0.275-3.37 rad, while the arm only *achieves* a p95 of
0.27-1.98 rad/s. Is the step itself the visible defect, and does capping the
emitted target's joint rate reduce it without losing placements?

**Cells.** The adopted direct recipe (`checkpoints/p177_full`, contact servo
0.10/0.20, place servo vmax 0.20, clamp 60 N, release endpoint, joint clamp,
action hold 4, execute 4, horizon 2600), one simulator session per arm:

| arm | `FRUIT_POLICY_TARGET_RATE` |
|---|---|
| C | unset (the shipped untouched target) |
| R2 | 2.0 rad/s |
| R1 | 1.0 rad/s |

Screen: seed 303, 6 episodes per arm. Confirmation (only if the mechanism moves):
seed 808, 6 episodes per arm. A 6-episode count is a branch draw; the mechanism
endpoints are the paired `[cmd]` rows, not the count.

**Mechanism endpoints (paired, same seed and fruit sequence as the code's own
selection allows).**
- P1 the per-waypoint target step (`max_j |dtgt|`) p95 and max fall at R2 and R1
  against C;
- P2 the fraction of decisions with a `>0.10 rad` joint step falls;
- P3 the lag-1 autocorrelation of the per-joint target step is unchanged in sign
  (a cap is not a low-pass; the test is that it does not *increase* the
  correlation, i.e. it does not merely delay);
- P4 the achieved/target step ratio rises (the drive follows more of the command)
  rather than the achieved motion collapsing.

**Delivery endpoints.** placed count non-inferior (C - 1 at 6 episodes), and the
emitted-target `out_pre` count from `FRUIT_EMIT_DIAG` is unchanged by the cap
(the cap is after the range clip, so it cannot hide an out-of-range sample).

**Falsifiers.** F1: P1 does not move at either rung -> the step is not the
visible defect. F2: placed falls by more than 1 at both rungs -> the cap costs
the task. F3: the achieved p95 falls by more than 35 % -> the cap is a speed
limit, not a smoother, and is not adopted at that rung.

**Read rule.** A rate cap changes the command, not the scenario; but the direct
loop is not bit-reproducible, so the count is one draw and the mechanism is the
paired command stream. No motion reference or store is touched by a knob that is
default off. Adoption requires the mechanism P1-P4 plus a non-inferior count.

## Amendment A1 (before any rate arm was read; after the control arm finished)

The control cell and an independent review changed three instruments, not the
question:

1. **`[cmd]` rows are differenced only across `dt == 4` ticks.** A servo hand-back
   skips many ticks between two printed rows; three of the control's 780 adjacent
   pairs spanned 248/696/940 ticks and owned its 0.508/1.078 rad "max". The
   filtered control reads p50 0.0210 / p95 0.1358 / max 0.660 rad, with 6.2 % of
   steps > 0.10 rad. The achieved/target ratio excludes measured steps above the
   arm's own 5.45 rad/s limit (a physics/teleport event, not a tracking read);
   unfiltered it read impossible ratios > 1.
2. **P3 (lag-1 autocorrelation) is withdrawn as a gate.** A saturating rate cap
   emits runs of same-sign steps by construction, so its autocorrelation *rises*
   without the command being worse. The cap's own signature replaces it: the
   request-to-target residual (`req - tgt`) p95 and the fraction of ticks the cap
   binds.
3. **A fourth arm, R4 = 4.0 rad/s, is added** as a near-inert control: at 4 rad/s
   the per-waypoint cap is 0.133 rad, above the control's p95 (0.136) and only
   binding the tail. R2 = 2.0 rad/s is the plausible ship rung; R1 = 1.0 rad/s is
   a deliberately strong cap (it is near the *achieved* p95, so it is a negative
   control for "the cap is a speed limit"). Order: C (done, **3/6**), R2, R4, R1.

**Count is report-only.** At 6 episodes a 3/6 control has a 95 % interval of
roughly [0.12, 0.88]; the adoption rule is the mechanism (P1/P2/P4) plus no gross
harm on the close and the placed class. The named harm endpoints are added: the
close-latch tick relative to the first policy tick, `gap_close`, and the
post-servo `[cmd]` window analysed separately (a servo hand-back is not a policy
step). A real count needs the WS-4.2 shape (N = 5 x 15 per arm).

## Results A2 (seed 303, 6 episodes; written before the seed-808 cells)

| arm | placed | emitted step p95 / max | >0.10 | request step p95 / max | residual p95 / max | binding |
|---|---|---|---|---|---|---|
| C | **3/6** | 0.136 / 0.660 | 6.2 % | - | - | - |
| R2 (2.0) | **1/6** | 0.067 / 0.067 | 0.0 % | 0.185 / 1.024 | 0.278 / 1.043 | **76.6 %** |
| R4 (4.0) | **2/6** | 0.061 / 0.134 | 2.6 % | 0.087 / 0.730 | 0.058 / 0.681 | 24.7 % |

The cap does exactly what it is for: R4 cuts the emitted p95 by **55 %** and the max by
**80 %** without lowering the achieved/target RMS ratio (0.14-0.35 against C's
0.14-0.36), and it binds only 24.7 % of waypoints. R2 also smooths, but it binds
**76.6 %**: at 2 rad/s the cap is a **speed limit**, not a tail smoother, and its
1/6 is not a count claim (the fruit sequence diverges after the first attempt).

**R1 (1.0 rad/s) is withdrawn** before running: it is strictly stronger than R2, whose
binding fraction is already 76.6 %, so it cannot be the ship rung and would spend a
cell to confirm a foregone negative. The seed-808 pair is **C vs R4** only.

**The count is still not the claim**: C 3/6 vs R4 2/6 is -1 and the arms' selected
fruit diverge after the first attempt (same first orange, then different station
occupants because the attempt durations differ). The seed-808 pair is the
confirmation; adoption is the mechanism plus no systematic harm in the close/latch
rows, not the 6-episode rate.

## Amendment A3: P208 and the R5 rung

The servo hand-back is a **state bug** the rate cap only smooths: at
`logs/p207/C_s303.log` t=996 the chunk generated before the place servo commands
j1 -1.066 against measured +0.684 (1.75 rad). `FRUIT_REPLAN_ON_SERVO_END=1` drops
the remaining chunk, forces a fresh observation and re-plans. Measured at seed
808 (6 episodes, R4 as the control):

| arm | placed | emitted p95 / max | residual p95 / max | binding | replans |
|---|---|---|---|---|---|
| R4 | 4/6 | 0.134 / 0.156 | 1.289 / 2.259 | 54.7 % | 0 |
| R4P | 3/6 | 0.134 / 0.134 | **0.344 / 2.431** | 46.1 % | 10 |

P208 is a smoothness fix, not a count fix: the residual p95 falls 73 %, the residual
max *rises* 7.6 % (a new 2.46 rad request after the replan, not a stale chunk), but
the count is -1 and the branch differs (R4's ep2 kiwi failed at
2190; R4P's ep2 apple placed). **No adoption on the count.**

The R4/P cells show the cap is still a speed limit (binding 46-55 %) because the
policy's *new* chunks can legitimately request 2.4-2.6 rad reconfigurations. A
rung at the arm's own joint-speed limit is the principled upper bound:
**R5 = 5.45 rad/s** (0.181 rad per waypoint; the `maxJointVelocity` 312 deg/s
already in `control.py`). It clips only requests above the physical joint limit,
so it should preserve the natural motion while removing the 2.6 rad outlier.
Run R5 at seed 808 (the C/R4 control pair is 4/6 both).
