# P240 pre-registration: zero the catch-up's following error with its own lead

**Pinned 2026-11-24, before any `FRUIT_DIRECT_CATCH_LEAD` cell was read.**

## The measured gap (P239)

At 0.08 m/s the catch-up's exit residual is **6.6-6.7 mm** against
`FRUIT_DYNAMIC_CATCH_TOL = 6 mm`, so the loop **exits on its 200-tick budget, not
on convergence**, and costs **1.67 s** on four of six attempts. The two attempts
whose error crossed 5.7-5.8 mm cost 0.22 and 0.81 s.

`6.6 mm at 0.08 m/s = 82 ms of lag`.

## The lever

`FRUIT_DIRECT_CATCH_LEAD` (default **0.25 s**) is the lead the direct catch-up
closes on. Its docstring already records the mechanism: *"the commanded target ran
28 mm (0.23 s) ahead of the achieved tip, so a 0.18 s lead left the tip riding ~6-7
mm behind the fruit - just outside the 6 mm tolerance, 200 ticks of grazing
contact"*. **That sentence is P239's measurement**, written as a design note years
earlier and never verified by the block report.

If the achieved tip trails the commanded one by a fixed time, adding that time to
the lead should zero the residual.

## The cells

`v=0.08`, `FRUIT_CYCLE_REPORT=1` + `FRUIT_TRACK_DIAG=1` on **both** arms, seed 901
x 3 episodes:

| arm | `FRUIT_DIRECT_CATCH_LEAD` |
|---|---|
| C | 0.25 (shipped) |
| T | **0.33** (+82 ms, the measured lag) |

## Predictions

**P1 (the endpoint, branch-free).** T's `[catch] residual` falls **below 6 mm**
(the tolerance) and its `catch ticks` collapses from 200 to **<= 60**. If the
residual does not fall, the lag is not a pure time delay and the lever is wrong -
report the negative.

**P2 (the block).** T's `seat` median falls from **1.67 s** to **<= 0.4 s** in the
same cell. The block report is the reason this is measurable at all (P236/P237).

**P3 (the count, a guard).** Placed does **not** fall on 3 attempts; a 3-episode
cell cannot show an improvement, only a harm, and that is what it is here for.

**P4 (the risk, named).** The lead commands the tip further downstream
(`v x 82 ms` = 6.6 mm at 0.08). The direct path's own cap is
`FRUIT_DIRECT_CATCH_MAX = 0.035 m` downstream of the tip, so 6.6 mm is inside it -
but a lead that is too large **overshoots** and the pads arrive past the fruit, so
P1 is only a win if the residual falls **without** the residual's *sign* flipping.
The `[catch]` row prints a magnitude only; the sign check is the placed count and
the catch-up's own re-seat count in `[carry]`.

## Falsifier

If `residual` falls but `seat` does not, the loop is exiting on something else and
P239's mechanism is incomplete. If the residual falls but placements fall, the lead
overshoots - the fix then needs a lead **and** a rate term, which is a different
cell.
