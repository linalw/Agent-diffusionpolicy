# P232 pre-registration: does the cell hold 91.7 % when the line speed varies?

**Pinned 2026-11-24, before any wave cell was read.**

## Why this disturbance first

The objective asks for **抗扰动能力** and the record has one measured disturbance
that a real line actually has: the conveyor does not run at a constant speed.
P135 built `FRUIT_BELT_WAVE` (a sine on the surface speed) and measured that the
shipped **speed** gate lost the handover by 298-407 mm under it while the
prediction gate converted every one - but that cell was the scripted two-line /
direct line at **0.12 m/s**. The single-arm bins lane has never been run under a
wave, and it is the lane the objective's 0.08 m/s band lives on.

## The cells

`FRUIT_BELT_SPEED=0.08`, `FRUIT_BELT_WAVE_AMP=0.04` m/s at
`FRUIT_BELT_WAVE_HZ=0.5` (so the surface speed sweeps **0.04-0.12 m/s**),
`FRUIT_EVAL_LATENCY=auto`, seeds {901, 902} x 6 episodes.

The comparison is P230's `0.08` cell (**11/12 = 91.7 %**, `logs/p230/base08/`) -
a **different batch**, so it is a direction, not a paired test (the direct loop
conditions on rendered frames).

## Predictions

**P1 (manipulation).** The cell really waves: the encoder/surface-speed read in
the log varies within `0.08 +- 0.04`, and the fire's `t_arrive` is computed from
the *instantaneous* speed (`t_arrive = dy / v`), so `dy = t_arrive x v` still
holds while `dy` itself now scatters more than in the constant-speed cell.

**P2 (the band).** Placed does **not** fall below **9/12**. The prediction gate is
shipped (P136: `FRUIT_TRACK` on for the scripted line, and the direct lane's
trigger already leads on the acquisition window), so the mechanism that fixed the
0.12 wave is present here.

**P3 (the mechanism, if it does fall).** The failures are **acquisition** (a
catch-up residual / never-held), not the grip class: the disturbance is a **timing**
one - the belt speeds up and slows down under a hand that is already moving - and
the grip is a separate object that P229/P230/P231 have just mapped.

**P4 (the falsifier that matters).** If placed falls **below 6/12**, the lane is
not disturbance-robust at the objective's own starting speed, and that - not the
speed ceiling - becomes the next blocker to work on.

## Read rules

* 6 episodes x 2 seeds is a **draw** (P93); the mechanism columns are the claim.
* `FRUIT_EVAL_LATENCY=auto` on every cell, as P228 requires.
* No comparison against the 0.12 wave cell (different arm, cell and supply).

## What is not claimed

That the lane is robust to *other* disturbances (lateral scatter, mass, occlusion).
This is the first rung of a ladder, chosen because it is the one a real conveyor
actually presents and because the tree already has a measured instrument for it.
