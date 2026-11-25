# P269 pre-registration: the powered cell for the catch exit tolerance (6 -> 7 mm)

**Pinned 2026-11-25, before any P269 cell was read.**

## Why, and what is already known

P267 measured the tolerance's effect on the class it belongs to: at **0.12**, the *true-stall*
rate (a catch whose exit residual is **> 20 mm**) read **10/34 (29 %) at 6 mm** against
**3/36 (8 %) at 7 mm**, with the count moving the right way (**+8**) but on diverged branches.
That is one draw per arm and the promoted claim needs power. **P48's 6 mm boundary** is the
registered risk: it measured `8/8 no-grasp above 6 mm`, but on the **pre-axis-exit** loop
where the norm was the whole test; the shipped loop allows `|z| <= 10` (P243), so the 6 mm is
now a **y-only** bound.

## The cells

**Fresh seeds 907/908** (neither appears in P266's or P267's arms), `v = 0.12`,
`FRUIT_TRACK_DIAG=1` + `FRUIT_CYCLE_REPORT=1` on **both** arms, **20 picks per cell = 40 per
arm**:

| arm | setting |
|---|---|
| C | unset (the shipped 6 mm) |
| T | `FRUIT_DYNAMIC_CATCH_TOL=0.007` |

## Registered endpoints

**P1 (primary, catch level).** The **true-stall rate** (`residual > 20 mm`, over catches)
falls by **at least half** - P267 read 29 % -> 8 %, so the registered bar is **T <= 15 %** of
catches.

**P2 (quality).** `T placed >= C placed - 2` of 40, **and no place-side loss** in T (a
`grasped=True placed=False` row would mean the 1 mm further offset at the close is costing
landings).

**P3 (the clock, report).** The attempt cycle and the picked interval, per arm.

## Falsifiers

* **P1 fails** -> the 7 mm exit is not a class lever and the tolerance stays at 6 mm; the
  0.12 acquisition story remains P268's ("free-space chase" -> arrival side or axis).
* **P2 fails** -> the 1 mm offset costs landings; the tolerance closes.

## What a pass licenses, and what it does not

A pass licenses **proposing** 7 mm as the exposure's default, which owes (i) a **third and
fourth seed** at this shape (P93's rule: two seeds can over-state), (ii) the **two-line gate**
+ both references + every store, because the catch path is shared, and (iii) the **0.08
re-check** (the 6 mm is the y-only bound there too, and the 0.08 cells' catches read
`y ~ +-5.8`, i.e. inside both) - the 0.08 deployment number must not move.

## Read rules

* Both arms carry the same instrumentation.
* The **catch-level** stall rate is the claim; the count is the decision rule; the cycle is a
  report.
* 20 picks per cell is one draw; two cells per arm is what "40 per arm" means here, and a
  cell with 0 stalls cannot test P1.
