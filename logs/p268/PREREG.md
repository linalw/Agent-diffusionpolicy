# P268 pre-registration: the catch-up's **force** exit ("pushing, not closing")

**Pinned 2026-11-25, before any P268 cell was read.**

## The object, and why a clock cannot do it

P266/P267 measured the same class by two different truncations: **the long chase is itself
the damage** (the pads spend the budget in contact with a fruit they are not converging on,
and the *true-stall* rate at 0.12 falls **10/34 -> 3/36** whether the loop is cut by a
plateau clock or by 1 mm more tolerance). **A clock cannot tell a converging chase from a
shoving one** - P266's guard truncated chases that would have placed, and P265's y-sign
reading was withdrawn for the same reason.

**The pads already know.** During the catch-up `follow_centre` tracks the fruit with the pads
**open** at `gap_open`, so any pad force in that window is *contact on a fruit the pads are
not yet around*. A chase that is still closing has no force; a chase that is **pushing** has
force and a residual that is not falling.

## The lever

`FRUIT_CATCH_FORCE_EXIT=<N>` (default **0** = off, the shipped loop bit for bit): break the
catch-up when **`normal_force >= N`** *and* the residual has improved by **less than 0.5 mm**
over the last **30** ticks. One tactile read per tick, **only when the knob is on** (the
`FRUIT_TACTILE_PATCH` precedent: a per-tick tactile read is inert on the scripted line, and
this one is not even present when the knob is off).

## The cells

0.12 m/s (where the stall class lives), `FRUIT_TRACK_DIAG=1` + `FRUIT_CYCLE_REPORT=1` on
**both** arms, seeds 905/906 x **20 picks**, control = P266's `C` cells (6 mm, no guard):

| arm | setting |
|---|---|
| C | unset (shipped) - reused, same batch family |
| T | `FRUIT_CATCH_FORCE_EXIT=2` (2 N, a quarter of the measured 9.8 N pinch) |

## Registered endpoints

**P1 (mechanism, catch level).** The **true-stall rate** (`residual > 20 mm` at the exit)
falls from **10/34 (29 %)** to **<= 5/34**, or the number of `>= 100`-tick rows falls by at
least half. This is the primary: it is a physical state, not a scored outcome, and it is what
P266/P267 both moved.

**P2 (quality, non-inferiority).** `T placed >= C placed - 2` of 40. A bigger fall means the
exit truncated convertible catches.

**P3 (the clock).** `[cycle] total` median **not worse** by more than 0.2 s, and the reported
interval not worse by more than 10 % (P103's price is registered in advance: a reaction that
re-draws the slot loop costs the interval).

## Falsifiers

* **P1 fails** (the stall rate does not fall) -> the force is not the discriminator either,
  and the 0.12 acquisition class closes as **hardware** (the record's `SIM_LIMIT.md` list).
* **P2 fails** -> the exit takes convertible catches; close it.
* **P3 fails** -> it is a clock that the sequencing absorbs (P83/P103's shape); do not
  propose it.

## What a pass licenses

Only **proposing** the knob as an opt-in for a cell with a stall class. It sits on the shared
catch path, so a default owes the two-line gate, both references and every store (P248's
price).

## Read rules

* Both arms carry the same instrumentation.
* 20 picks per seed is one draw; the **catch-level** stall rate is the claim, the count is
  the decision rule and the interval is a report.
* A cell with no stall cannot test P1 and must say so rather than score a tie.
