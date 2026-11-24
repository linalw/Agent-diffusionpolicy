# P230 pre-registration: why the pads close on air at speed

**Pinned 2026-11-24, before any `FRUIT_CLOSE_TRACE` cell was read.**

## The gap this closes

P229 traced the `v >= 0.22` failure to acquisition: `contacts@onset = 0`,
`force@onset = 0.00 N`, `sep_end = 0.0 mm` on a 40.0 mm fruit with
`gap_start = 14.1 mm` - **the pads closed on air**. That trace has one row per
**leg**, so it cannot say *when* the emptiness began, and two very different
mechanisms produce the same leg row:

* **(a) aim offset** - the close's aim is `fruit + v x lead` (a *time* lead
  converted at the belt speed). If `v x lead` approaches the pad's half-opening,
  the commanded point sits outside the span and the fruit is never between the
  pads: `n = 0` for **every** close tick.
* **(b) outrun** - the aim is on the fruit at the start, the pads load
  (`n >= 1`), and the fruit then leaves during the ramp: `n > 0` then `0`.

The fix is different: (a) is a lead that must shrink with speed (or a close that
aims at the *predicted* contact, not the fruit plus a lead); (b) is a faster
close or a wider pad.

## The instrument

`FRUIT_CLOSE_TRACE=1` (default off, added this phase) prints one row per **close
tick**, after the physics step:

```
[close-trace] t=<tick> step=<i> cmd=<mm> aim_minus_fruit=<mm> x_off=<mm> n=<contacts> f=<N>
```

`aim_minus_fruit` is exactly `v x lead` at that tick, so it reads the lead
directly in millimetres; `n`/`f` are this pad's own load. One tactile read per
tick; **no rate is quoted from an armed cell** (AGENTS section 2).

## Cells

* **T** - `FRUIT_BELT_SPEED=0.24`, `FRUIT_BELT_UPSTREAM=0.10` (the cell P229
  traced as 0/3 with `contacts@onset = 0`), 3 episodes, seed 901.
* **C** - `FRUIT_BELT_SPEED=0.12` (the shipped speed, 10/12), 2 episodes, seed
  901 - the control: what a close that works looks like tick by tick.

## Predictions

**P1 (the control).** At 0.12 the aim offset stays well inside the pad's span,
`n` becomes `>= 1` before `cmd` falls below the fruit's width, and the force
holds to the end of the ramp.

**P2 (the discrimination).** At 0.24 exactly one of:

* **(a)** `n = 0` on **every** close tick, with `aim_minus_fruit` at or beyond
  roughly half the pad opening - the aim is beside the fruit. This is the
  hypothesis the shipped `lead` structure predicts (a **constant time** lead x a
  speed that doubled since it was tuned).
* **(b)** `n >= 1` at some point and then `0`, with the aim offset small at the
  start - the fruit outran the ramp.

**P3 (the lead's shape).** `aim_minus_fruit` is `v x lead` with a *constant*
`lead`, so the median offset should be about **2x** larger at 0.24 than at 0.12.
If it is not, the close is not using the shipped lead and that has to be found
before any fix.

## Falsifier

If `aim_minus_fruit` is near zero and `n` is zero at 0.24, neither story holds:
the aim was on the fruit and the pads still missed, which points at the arm not
following the aim (the command is `follow_centre`, and `pad_error = 25 mm` at the
close's start is the only number P229 has on that). Then the next instrument is
the measured pad position, not the command - and this phase says so instead of
guessing.

## What is not claimed

No rate (P93: 3 episodes is a mechanism cell). No claim that fixing this raises
the count - the objective's ordering is success first, speed second, and this is a
success term at speeds the shipped 0.08-0.12 does not reach.
