# P248 pre-registration: the powered cell for the axis-aware exit

**Pinned 2026-11-25, before any P248 cell was read.**

## What is being decided

P243 + P247 measured the axis-aware exit at **26/28 placed** with the catch-up at
**21-42 ticks** (against the shipped 200) and the `seat` block at **0.17-0.34 s**
(against 1.67). The promotion to default owes a **powered cell** (P93's rule).

**The claim is not "quality is better"** - the mechanism removes work, not margin,
and the counts are at parity. The claim is **non-inferior quality + a branch-free
1.44 s**. So the cell is designed for **non-inferiority on the count** and for the
**mechanism** (which is per-attempt and does not need the count's power).

## The cells

`v=0.08`, **seeds 901/902 x 20 episodes = 40 attempts per arm**, the same
instrumentation on both arms (`FRUIT_CYCLE_REPORT=1` + `FRUIT_TRACK_DIAG=1`), so
placed, `seat`, `catch ticks`, `s/attempt` and the runaways all come from one batch:

| arm | `FRUIT_CATCH_TOL_AXIS` |
|---|---|
| C (control) | unset (shipped 3-D norm, 6 mm) |
| T | **1** (`|y| <= 6`, `|z| <= 10`, command untouched) |

## Registered endpoints

**P1 (quality, non-inferiority).** `T placed >= C placed - 2` of 40. The shipped
arm's own 0.08 rate is 11/12 and P247's T was 15/16, so a 2-attempt margin is the
honest bar for "does not cost quality" at this n.

**P2 (mechanism, branch-free).** `T`'s catch-up median **<= 45 ticks** and `seat`
median **<= 0.40 s**, against `C`'s 200 and 1.67. This is the claim that does not
depend on the count.

**P3 (the cycle).** `T`'s `s/attempt` is **>= 0.8 s lower** than `C`'s. The
mechanism predicts 1.44 s; 0.8 s allows the acquisition's own jitter to absorb half
of it (P88/P89's shape).

**P4 (the open class, reported).** Runaways (`residual > 50 mm`) per arm. P246 bound
them at **at most one per run, at the first episode**; the prediction is **<= 1 per
arm** (two runs each) and, if present, on episode 0. **Not gated** - it is the
class the record has already closed as unexplained, and gating it would turn an
unattributed event into a verdict.

## Falsifier

**P1 fails** (`T < C - 2`) -> the lever costs quality and is **closed**, whatever
the mechanism says. **P2 fails** (the catch-up does not collapse) -> the lever does
not do what P243/P247 measured and the earlier cells were a branch.

## What a pass licenses, and what it does not

A pass licenses **proposing** the flip. It does **not** flip anything by itself: the
knob is on the shared `_carry_leg`/catch path, so a default owes the **two-line
gate** (`scripts/190_twoline_gate.sh`), **both motion references re-recorded** from
same-batch runs, and **every store re-baselined** - and the objective's owner
decides.

## Read rules

* Both arms carry the same instrumentation, so no arm is measured with a diagnostic
  the other lacks (P230/P232/P244's lesson).
* A 40-attempt count is **still one draw per seed** in the strict sense; the
  non-inferiority bar is a decision rule, not a rate.
* No cross-arm rate claim beyond P1's margin.
