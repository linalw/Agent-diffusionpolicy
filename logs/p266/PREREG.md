# P266 pre-registration: the catch-up's **behind-the-fruit stall guard**

**Pinned 2026-11-25, before any P266 cell was read.**

## The measured object

P265's census at 0.12 (two 10-pick cells, `FRUIT_TRACK_DIAG=1`): the **converged** catches
read **20-28 ticks / 7.8-8.8 mm** with the hand **downstream** (`y ~ -5.8`), and every
**stalled** one burns the **full 200-tick budget** with the hand **upstream**
(`y` **+10.6 .. +37.6 mm**). At 0.12 the fruit moves 1 mm/tick, so a 30 mm deficit needs
200 ticks of chasing - the budget is spent and the attempt is lost.

**So the object is not a success lever** (the catch cannot be won from behind at 0.12) - it
is a **time** object: 200 ticks (1.67 s) plus the close and the re-grasps are spent on an
attempt that is already decided.

## The lever

`FRUIT_CATCH_STALL_TICKS=<n>` (default **0** = off, the shipped loop bit for bit): after
`n` ticks, if the hand is still **upstream** of the fruit (`tip_y > fruit_y`) **and** the
residual has not improved by more than **0.5 mm** over the preceding `n` ticks, the
catch-up **breaks** - the loop has stopped converging and cannot, at this belt speed.

Nothing else changes: the close, the probe and the re-grasps run exactly as they do today
(they already run after a 200-tick stall). So the change is a **pure clock** on attempts
the geometry has already lost.

## The cells

0.12 m/s (where the class lives), `FRUIT_TRACK_DIAG=1` + `FRUIT_CYCLE_REPORT=1` on **both**
arms, seeds 905/906 x **20 picks**:

| arm | setting |
|---|---|
| C | unset (the shipped 200-tick loop) |
| T | `FRUIT_CATCH_STALL_TICKS=60` |

`n = 60` because the converged catches finish in 20-28 ticks, so 60 is 2x the slowest good
one and cannot truncate a catch that would have made it.

## Registered endpoints

**P1 (mechanism, branch-free).** On the **stalled** attempts, `catch ticks` falls from
**200** to **<= 70**. This is the claim; it does not depend on the count.

**P2 (the clock).** `[cycle] total` median **>= 0.3 s lower** on the arm that has the
stalls; if neither cell has a stall, the endpoint is **not evaluable** and the phase
reports that (the 0.12 stall rate is ~5 in 20 catches, so one cell of 20 may miss).

**P3 (quality, non-inferiority).** `T placed >= C placed - 2` of 20. The attempt fails
either way; a loss beyond 2 would mean the guard truncated a catch that would have made it.

**P4 (the interval, reported not gated).** The picked interval and the attempt count. P103
measured that a reaction which re-draws the slot loop costs **+15 %** interval while saving
**0 ticks** - so a guard that saves ticks but re-draws the loop is **not** a win, and this
phase must show the interval, not just the ticks.

## Falsifiers

* **P1 fails** (the stalled attempts still run 200) -> the guard is not wired where the
  stall is, and the phase closes as an instrument defect.
* **P3 fails** -> the guard truncates convertible catches; close it.
* **P4 shows the interval worse** -> the guard is a clock that the sequencing absorbs
  (P103/P83's shape); do not propose it.

## What a pass licenses

A pass licenses **proposing** the knob as an opt-in for cells with a stall class. It does
**not** flip a default: the knob sits on the shared catch path, so a default owes the
two-line gate, both references and every store (P248's price).

## Read rules

* Both arms carry the same instrumentation, so no arm is measured with a diagnostic the
  other lacks.
* 20 picks per seed is one draw each; the count is a decision rule, not a rate.
* The stall count per cell is small (~5 of 20 catches); a cell with 0 stalls cannot test
  P1 and must say so rather than score a tie.
