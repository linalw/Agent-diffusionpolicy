# P243 pre-registration: the exit criterion should be the direction the catch needs

**Pinned 2026-11-25, before any `FRUIT_CATCH_TOL_AXIS` cell was read.**

## The measurement this starts from

P241 added the residual's components; P239/P240/P242 established:

```
shipped exit at 0.08:  (x=-0.1, y=+0.5, z=-6.6) mm, ticks=200, seat=1.67 s
```

The loop's exit condition is the **3-D norm < 6 mm**. The **y** part is already
0.5 mm; the **z** part is a **6.6 mm steady-state vertical error** - a
gravity/reach limit the position controller does not remove - and it is 0.6 mm
outside the tolerance. **So the loop waits for a number that never arrives and
exits on its 200-tick budget.**

P242 fixed the time by offsetting the **command** (+6.6 mm) and bought an
**11 % runaway class** with it.

## The lever

`FRUIT_CATCH_TOL_AXIS=1` (default off) replaces the exit with **two per-axis
conditions**:

```
|y| <= FRUIT_DYNAMIC_CATCH_TOL         (6 mm, unchanged - the belt direction)
|z| <= FRUIT_CATCH_TOL_Z               (10 mm, default; contains the measured 6.6)
```

**The command is not moved.** That is the whole point: the runaway region P242
entered is the *command's*, and this lever never goes there.

## The cells

`v=0.08`, `FRUIT_CYCLE_REPORT=1` + `FRUIT_TRACK_DIAG=1`, seeds 901/902 x 6.
Controls: P239/P240's shipped cells (same instrumentation, 6 attempts) and P242's
FF cells (12 attempts) as the comparator for the runaway class.

## Predictions

**P1 (the mechanism).** `ticks` collapses from 200 to **22-35 on every attempt**
- not 89 % of them - because the exit no longer depends on the z droop. If any
attempt still reads 200 with `|z|` inside 10 mm, the y condition is what is failing
and the components row will say so.

**P2 (the advantage - the reason this is better than P242).** **Zero runaways**
(`residual > 50 mm`) in 12 attempts. The command is byte-identical to the shipped
one, so if a runaway appears here it is **not** the offset's and P242's
"associated with the offset" reading is wrong.

**P3 (the quality guard).** Placed does not fall below **11/12**.

**P4 (the cycle).** `seat` 1.67 -> **~0.2 s** on every attempt, i.e. **-1.44 s of
~13.3 (-11 %)**, now *without* a quality price.

## Falsifier

If `ticks` stays at 200 with `|y| <= 6` and `|z| <= 10`, the loop is exiting on
something else entirely (a per-tick break upstream of the criterion) and the block
report's `seat` is not the pursuit - the next step is then to mark the loop's start
and end, not to tune the bound.

## What is not claimed

That 10 mm of vertical error is acceptable **as a grasp**. The pads are 61 mm plates
and the fruit 30-70 mm, so 10 mm of height error moves the seat but does not lift
the pads off the fruit - that is an argument, not a measurement, and P3's placed
count is the measurement that has to hold.
