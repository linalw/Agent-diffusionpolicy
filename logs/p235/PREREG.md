# P235 pre-registration: the place block at 0.08 - is P227r's negative speed-dependent?

**Pinned 2026-11-24, before any `FRUIT_SPEED_PLACE` cell at 0.08 was read.**

## Why this cell

The objective asks for **分拣速度** after success, and the cycle is
**≈14.5 s/attempt**, of which `place` is the largest block (**≈4.0 s**). P227r
measured the faster place (`FRUIT_SPEED_PLACE=0.52`, the P44 **S1** cell) on this
cell at **0.12 m/s**: place **4.0 -> 2.8-3.2 s**, the mixed cell **5/5**, but the
**pear cell 5/6 -> 3/6** with two place-leg payload losses. It was not adopted.

That negative has a **speed** in it: the place leg carries the payload while the
belt drags it at `v`, and 0.12 is where the measured loaded slide begins to bite
(P229's usable ceiling is 0.18-0.20). **At 0.08 the relative velocity is two
thirds of that**, so the same faster profile has more margin - and if it holds,
the block is ~1 s cheaper per attempt (~7 % of the cycle).

## The cells

`FRUIT_BELT_SPEED=0.08`, `FRUIT_CYCLE_REPORT=1` on **both** arms, 6 episodes per
cell:

| arm | `FRUIT_SPEED_PLACE` | seeds |
|---|---|---|
| C (control) | unset (0.35) | 901, 902 |
| T (treatment) | **0.52** | 901, 902 |

## Predictions

**P1 (mechanism, branch-free).** The `[cycle] place=` median falls from ~4.0 s to
**2.8-3.2 s** in T, and the per-leg tick count matches `motion.jerk_limited` at the
printed distance (P88's check). If the block does not move, the knob did not take.

**P2 (the count, a direction).** Placed does **not** fall below **9/12** pooled.
P227r's loss was at 0.12; the registered hypothesis is that it is
**velocity-dependent**, so 0.08 should be clean.

**P3 (the class, if it does fall).** The failures are **place-leg payload losses**
(`clean_slip` large, `grasped=True placed=False`) - the class P227r saw - and
**not** acquisition. If the class is acquisition, the speed of the place leg is
not implicated and the negative is a branch.

**P4 (the cycle).** `s/attempt` falls by **>= 0.6 s** (the block saving) and the
interval/immediate throughput improves **without** the count falling. If the
interval does not move, the saving is being absorbed - the shape P86/P88/P89 kept
finding - and the honest read is "the block moved, the delivery did not".

## Falsifiers

* If T's place block does not fall, the cell is not the P44 S1 cell here (the
  place cap might be overridden by the dynamic path) and nothing is measured.
* If T loses placements **with the same class as P227r at 0.12**, the negative is
  **not** speed-dependent and the place profile is closed at every speed.
* If T loses placements with a **different** class, the difference is a branch at
  n = 12 and no claim is made.

## What is not claimed

That the profile should ship. Even a clean cell at 0.08 needs 0.12/0.18's own
cells before any default, and the place block is on the shared `_carry_leg` path.
