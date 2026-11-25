# P273 pre-registration: the tolerance's **difference** endpoint, powered

**Pinned 2026-11-25, before any P273 cell was read.**

## Why this exists

P267/P269/P271 left the catch exit tolerance (6 -> 7 mm) **unresolved**: P269 read the
true-stall rate **19 % -> 9 %** on seeds 907/908 *without* the landing trace, and P271 read
**14 % -> 11 %** on the same seeds *with* it. Two batches disagree, and P271 recorded why the
registration could not settle it:

* P269's **P1 was an absolute bar** (`T <= 15 %`) on a branch-dependent quantity - it can be
  passed by a branch where *both* arms are low (it was: C itself read 14 %);
* and one batch of 40 picks per arm cannot separate a 3-point difference.

**So this registration changes the two things P271 named: the endpoint is a DIFFERENCE, and the
sample is sized for it.**

## The cells

`v = 0.12` (where the class lives), **four fresh seeds 909/910/911/912**, 20 picks per cell,
**8 cells = 80 picks per arm**, `FRUIT_PLACE_TRACE=1` + `FRUIT_CARRY_DIAG=1` +
`FRUIT_TRACK_DIAG=1` on **both** arms:

| arm | setting |
|---|---|
| C | unset (6 mm) |
| T | `FRUIT_DYNAMIC_CATCH_TOL=0.007` |

The trace is on for **both** arms because P271's clause needs it and because it must not be the
difference between the arms.

## Registered endpoints

**P1 (primary, the difference).** The **true-stall rate** (`residual > 20 mm`, over catches)
in T is **at least 5 points lower** than in C, with a **two-sided Fisher p <= 0.20** on the
catch-level 2x2. (At ~150 catches per arm, a 5-point difference from a 15 % base is ~1.4 sigma;
p <= 0.20 is the honest bar for this sample - the record's P93 rule is that a rate claim needs
the power, and 80 picks/arm is what one session buys.)

**P2 (quality).** `T placed >= C placed - 4` of 80, and **no place-leg loss with the payload
present at the release** in T (the corrected clause; `FRUIT_PLACE_TRACE`'s `on_belt`).

**P3 (the clock, report).** The attempt cycle and `s/pick`, per arm.

## Falsifiers

* **P1 fails** -> the tolerance is **not** a class lever at this sample, and it closes as
  **unresolved-closed**: no further cell on it, the shipped 6 mm stands, and the record says the
  class effect could not be reproduced.
* **P2 fails** -> the 1 mm offset costs landings; the tolerance closes.

## What a pass licenses

**Proposing** 7 mm as the exposure's default - which then owes PREREG (P269) §"What a pass
licenses": two more seeds, the **two-line gate**, **both references** and **every store**,
because the catch path is shared. **A pass here does not flip anything.**

## Read rules

* Both arms carry the same instrumentation (the trace is not an arm difference).
* The **difference** is the claim; the counts are the decision rule; the cycle is a report.
* A cell with 0 catches cannot enter the rate; a cell with 0 stalls is reported and does not
  change the difference's sign.
