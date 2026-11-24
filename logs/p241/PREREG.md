# P241 pre-registration: feed forward the 6.6 mm vertical droop

**Pinned 2026-11-24, before any `FRUIT_CATCH_Z_FF` cell was read.**

## What was measured (P241's first half, already committed to the row)

The `[catch]` row now carries the residual's **components**. At 0.08 m/s:

```
ticks=200 residual=6.6mm (x=-0.1 y=+0.5 z=-6.6)
ticks=200 residual=6.7mm (x=-0.2 y=+0.3 z=-6.7)
ticks= 26 residual=5.8mm (x=+0.6 y=-3.8 z=-4.4)     <- the only fast attempt
```

**The belt direction is already tracked** (`y` 0.3-0.5 mm). The floor is **z**: the
hand sits **6.6 mm below** the commanded standoff as a steady-state error, 0.6 mm
outside the 6 mm tolerance, so the loop exits on its 200-tick budget.

This also retires P240's question and confirms its suspicion.

## The lever

`FRUIT_CATCH_Z_FF=<mm>` (default **0**) raises the catch-up's **command** by that
much, leaving the residual's reference where it is - so the arm is asked for the
point it has been missing by. `6.6` is the measured droop. Zero is the shipped
path byte for byte.

## The cells

`v=0.08`, `FRUIT_CYCLE_REPORT=1` + `FRUIT_TRACK_DIAG=1`, seeds 901/902 x 3,
`FRUIT_CATCH_Z_FF=6.6`. The controls are P239/P240's shipped cells (same
instrumentation) and this phase re-reads its own control above.

## Predictions

**P1 (the mechanism, branch-free).** The residual's `z` goes to ~0 and the norm
falls **below 6 mm**, so `ticks` collapses from 200 to **<= 60** and `seat` from
1.67 s to **<= 0.4 s**. If `z` does not move, the command offset is not reaching the
servo and the lever is void.

**P2 (the guard - and the discriminator).** Placed does **not** fall. This is the
prediction that decides what the 6.6 mm **is**:

* if it is **arm droop** (a steady-state error), raising the command puts the real
  pads where the model already thought they were, and the grasp is unchanged or
  better;
* if it is a **model error** (the model's `tip` sits above the real pad point),
  then the loop was already converging the *real* pads correctly and this offset
  lifts them 6.6 mm too high - **the grasp degrades**, and the honest fix is to
  correct `_pad_standoff` / `finger_len`, not to bias the command.

**P3 (the block).** With `seat` at ~0.22 s the cycle falls from ~13.3 to **~11.9 s**
(-11 %), measurable in the same `[cycle]` rows.

## Falsifier

If the residual falls and placements fall, P2's second branch holds: **report the
offset as a measurement bug, revert the lever, and record that the 6 mm tolerance
was correct all along** - the 200-tick tax would then be the price of a *correct*
tolerance against a *wrong model*, and the fix belongs in the geometry constants.

If the residual falls and placements hold, the cycle has a free 1.44 s and the
lever is a candidate default (needing the two-line gate, both references and a
store re-baseline).
