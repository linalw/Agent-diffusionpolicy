# Tracking a target whose motion is not the conveyor's

*The design note for P135. Every number below is measured on this tree; the cell
logs are `logs/p135/`.*

## 1. The problem, stated the way the cell has it

The shipped catch is a **formula**, and every term of it is a conveyor
assumption:

```
aim      = [fruit_x, station_y + lead, fruit_z]        # computed once, at the pre-pose
wait     = fruit_y - grip_y <= speed * (t_desc + 0.15) # speed = the belt encoder
descent  = a min-jerk leg to the fixed aim             # open loop
catch-up = fruit_now + velocity * 0.25                 # constant velocity
```

That is exact while the fruit rides a constant-speed belt. It is wrong the
moment the fruit does not: a collision, a fruit rolling, a conveyor whose speed
varies.

**The cell was measured under a varying belt** (`FRUIT_BELT_WAVE_AMP=0.04` m/s at
0.5 Hz, the fruit riding it with no slip). The catch-up is not the term that
fails - it is fast (10-20 ticks) - the **handover** is: the gate above uses the
*instantaneous* speed, the fruit's travel during the descent is an *integral* of
the speed, and the two disagree by 300-400 mm. The hand then descends 300-400 mm
from the fruit, the catch-up spends its whole 200-tick budget, and the attempt is
a `never_held`:

| arm | catch residual (3 attempts) | catch ticks |
|---|---|---|
| shipped | 298, 339, 5.9 mm | 200, 200, 11 |
| + re-aim | 5.9, 5.8, 339 mm | 8, 12, 200 |
| **+ prediction-gated wait** | **5.6, 5.4, 5.9 mm** | **17, 16, 16** |

## 2. What replaced it

### 2.1 A state estimate, not a number
`tracking.FruitTracker`: a Kalman filter over the centre, constant velocity with
an **adaptive process noise** so a velocity change is followed inside two or
three frames. On a fruit riding the belt `predict(h)` equals `p + v*h` to
1.8e-15 m - that exactness is what makes the tracked path the shipped path when
the model holds. The constant-*acceleration* form is not the default: a struck
fruit changes velocity, and a CA fit through the step reports a 2-3 m/s²
transient that integrates to 0.1-0.7 m over the remaining descent.

### 2.2 A correction defined against the conveyor
```
correction(t_go) = predict(t_go) - (position_at_descent_start + belt_v * (elapsed + t_go))
aim(t_go)        = grip + clamp(correction, FRUIT_TRACK_CORR_MAX)
```
It is **zero under the model**, so the descent's geometry, its motion budget and
the two-line clearance are the shipped ones whenever the belt is the belt. The
only thing that moves is the part of the fruit's motion the conveyor does not
explain. `FRUIT_TRACK_CORR_MAX` (0.08 m) bounds what one leg can spend.

### 2.3 A re-aimed descent
`_approach` takes an optional `t_remaining -> jaw point` callback, re-evaluated
**every tick**; the remaining min-jerk profile is spent along the line to the new
aim. Same speed schedule, same zero-arrival velocity, moved endpoint.

### 2.4 The handover is a prediction, not a speed
`FRUIT_TRACK_WAIT=1` starts the descent when the estimate says the fruit will be
at the catch position **when the leg ends** - the shipped margin, re-derived from
the state instead of from `speed * time`. On the nominal belt this is the shipped
gate (`predicted - grip <= 0.02` vs `fruit - grip <= v*(t_desc+0.15)` = `0.018`),
which is why the nominal cell does not move; under a varying belt it is the
difference between a 300-400 mm miss and a 6 mm catch.

## 3. Where the measurement comes from

`FRUIT_TRACK_SOURCE=depth` builds the estimate from the head camera:
render -> RGB + `distance_to_image_plane` + the target's instance mask ->
back-project through the **calibration** (the authored focal length and aperture;
a ratio, so the stage's units cancel; the camera prim's world pose) -> a trimmed
least-squares **sphere fit**.

Measured (2 attempts, 44 frames, the shipped pool):

| quantity | median | p90 |
|---|---|---|
| centre error | **4.7 mm** | **6.4 mm** |
| diameter error | **3.4 mm** | **4.3 mm** |

With that measurement driving the aim and the close (`FRUIT_PERCEPTION_CLOSE=1`)
the cell places **2/2** on a 2-attempt cell, with **no fallback to the
simulator's state** on the aim path.

Two limits, measured, that a real installation has to design around:

* **The hand occludes the target exactly when it matters.** As the descent
  proceeds the mask shrinks 48 -> 22 px; a *free* sphere fit then has no curvature
  to work with and its centre drifts along the view axis (z error 11 -> 44 mm).
  Two things fix it: the radius is a property of the fruit, not of the frame, so
  once a full cap (`FRUIT_PERCEPTION_FULL_PX` 120) has measured it, a smaller cap
  fits **only the centre with the radius held**; and a cap below
  `FRUIT_PERCEPTION_MIN_PX` (60) is **refused** outright, with the estimator
  predicting through the occlusion. A wrist camera or a second view is still the
  fix for the window itself - the remaining error is 6 mm, half of it the
  systematic `+y` bias below.
* **The error is a systematic +y bias** (3.5-6.3 mm upstream) on a large fruit,
  and grows for a 30 mm fruit (9 mm): a sphere fit through an *ellipsoid's*
  visible cap displaces the centre along the long axis. That is a **calibration**
  item (a reference sphere at the station measures the offset once), not a
  modelling error - and it is why the registered bar was 5 mm rather than 1.

## 4. What is a tracker *not* for

A velocity impulse on the fruit (the scripted form of the collision `logs/p95`
measured) is **damped by the belt in ~30 ms**: the fruit slides a few
millimetres and re-settles. The catch-up absorbs every rung of the ladder
(0.10-0.35 m/s lateral, 0.10-0.30 m/s downstream) in **<= 24 ticks**, and 17 of 18
lateral grasps succeed. What the impulse costs is the **grasp
quality** - the pads close on a sliding fruit and the payload escapes during the
carry (0-2 of 3 placed) - and that is the closed loaded-slide class
(`logs/p42/SIM_LIMIT.md`), which no tracker touches. The impulse is a *negative*
for tracking, and a confirmation of the class split.

## 5. What it costs when it is off

`FRUIT_TRACK` unset: no estimator, no callback, no perception; the catch-up reads
the rigid body exactly as before; `_step_sim` carries one bool test for each of
the two test instruments (the impulse and the belt wave). The no-harm gate is
`scripts/accept.sh` with a byte-identical `[fruit]` stream.
