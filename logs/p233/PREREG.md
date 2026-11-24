# P233 pre-registration: give the trigger the belt it is actually on

**Pinned 2026-11-24, before any `FRUIT_TRIGGER_SURFACE_SPEED` cell was read.**

## The defect P232 found

Under a belt wave every fire row of every cell printed `speed=0.080m/s/encoder`:
the trigger's approach speed is `Conveyor.encoder_speed`, which P141 measured to
be a **setpoint echo** once the cleats are off (it is only recomputed inside
`step()` while the cleats exist). The belt that actually moves is
`Conveyor.surface_speed` - the value `_apply_speed` writes into the
`PhysxSurfaceVelocityAPI`.

So on a varying line the trigger computes

```
t_arrive = dy / speed_setpoint        # the fruit is moving at 0.02 .. 0.14
```

up to **2x** wrong in the single number the handover is scheduled on. The cells
survived because the primitive's hover and descent use `_belt_speed_estimate()`
(the surface speed), and the hover **absorbs** the error as a wait.

## The lever

`FRUIT_TRIGGER_SURFACE_SPEED=1` (default off) makes the trigger read
`surface_speed` instead of `encoder_speed` at both `should_fire` call sites. One
attribute name; unset is the shipped read byte for byte.

## The cells

`FRUIT_BELT_SPEED=0.18` with `FRUIT_BELT_WAVE_AMP=0.03` at 0.5 Hz (surface sweeps
**0.15-0.21 m/s**, so the crest sits at the measured marginal point and the trough
inside the reliable band), seed 901 x 6 episodes:

| cell | trigger speed source |
|---|---|
| A (control) | `encoder_speed` (setpoint echo) |
| B (treatment) | **`surface_speed`** |

## Predictions

**P1 (manipulation, decisive).** In **B** the fire row's `speed=` **varies**
within `0.15-0.21`; in **A** it is a constant `0.180`. A treatment cell that still
prints one value has not taken the route and measures nothing.

**P2 (the branch-free signature).** `dy` at the fire is `lead x v` when the speed
is correct, so **B's `dy` scatters with the wave** while A's stays near
`lead x 0.18`. This is the number to compare, not the count.

**P3 (the count, a direction).** B places `>= A`. At 6 episodes this is a draw
(P93); the claim is P1+P2.

**P4 (the falsifier that would make this not a fix).** If **B is worse**, the
stale echo was doing something useful - it pins the fire to a constant distance,
which a hover can absorb - and then the honest read is that the tree's
compensation depends on a wrong number, which is a much worse finding than a slow
trigger. Report it as such; do not retune the amplitude to hide it.

## What is not claimed

That the shipped default should change. The cell is one seed, and the fix moves
the branch: it needs the two-line gate and its own references before any flip.
