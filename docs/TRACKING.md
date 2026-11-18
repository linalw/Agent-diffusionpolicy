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
* **The error is a systematic mounting offset**: the fitted centre sits
  **+6.5 mm** in `+y` of the rigid body's origin on this camera, stable across the
  pool and independent of the fruit's shape (a spheroid fit is a measured
  negative). `configs/perception_calibration.json` carries it and the module
  subtracts it, which takes the bench from **6.79 mm median to 1.98 mm** (p90
  10.01 -> 5.63) at an unchanged 2.4 mm diameter error. The wrong-sign control
  (subtract -6.5 mm) moves the error to 13.16 mm, which is what proves it is a
  constant and not a fitted curve. A different mount or lens needs its own number
  (`FRUIT_PERCEPTION_BIAS=x,y,z`); the diameter's 2.4 mm is the fruit being an
  ellipsoid and is not removed by an offset.

## 3b. The eye-in-hand camera

`FRUIT_WRIST_CAMERA=1` authors a second RGB-D camera per arm and drives it from
the jaw centre and approach axis on every rendered frame. The head camera's
weakness is geometric - 0.8 m away, with the arm between it and the fruit - so
the wrist should not have it, and **aimed forward it does not**:

| aim | mask | refusals | position | diameter |
|---|---|---|---|---|
| at the grasp point (3 cm past the jaw) | 94-402 px | 729 | 7.7 mm | 5.8 mm |
| **12 cm past the jaw** | 1684-3241 px | 2-3 | **3.54 mm** | **0.90 mm** |

Aimed at the grasp point the fruit - 10 cm upstream when the leg starts - leaves
the frame; aimed forward the mask *grows* as the hand closes. That is the best
measurement in the project (2.6x the head's diameter accuracy).

It is **not yet a closed-loop sensor**: attempt 0 is clean and attempt 1 diverges
in every configuration tried - the hand drives through the fruit and the catch
ends 0.3-3 m away. Eight variants are recorded in `logs/p135/RESULTS.md` §9:
three aims (3 cm, 6 cm, 12 cm past the jaw), a wider lens, an aim that tracks the
estimate (which is *worse* - the view and the estimate form a feedback loop), a
belt-velocity prior, a measurement gate and a relative anchor. The last three are
**real estimator improvements and are kept** (they also make the head loop faster:
5 ticks on its second attempt), but they do not convert the wrist.

**The mount model was wrong, and that is the phase's last finding**: `look*axis`
is the *tool* axis, so "12 cm past the jaw" is 12 cm **below the hand**, not up the
conveyor - and the fruit arrives from the belt, 10-30 cm upstream and 7 cm lower.
That is why the 12 cm mount measures beautifully when it sees anything and why it
only sees the fruit when it is close: **the wrist is a contact-phase sensor, not an
approach one**. Two consequences, both kept: a mask that touches the image border
is **refused** (`FRUIT_PERCEPTION_CLIP_PX`) because a truncated cap reads a perfect
rms and diameter with a 24-32 mm centre error; and tilting upstream
(`FRUIT_WRIST_UPSTREAM`) is a measured negative (1-6 frames per attempt - the aim
then sits above the belt). A fixed mount cannot be both far upstream and low
without a real tilt, which is what a bracket would buy. The head camera keeps the
approach and the wrist the contact. The handover is **built and hardened** - a
**workcell ROI** (a wrong lock 0.8 m from the fruit passed the innovation gate and
put the aim a metre away), a **bounded wait for a first measurement** instead of a
blind descent, the **band-centre fallback** and the **border-clip gate** - and it
is **not validated**: with two render products alive the second attempt accepts
**zero** frames, while the same attempt on the head-only tree accepts 51 and the
wrist-only cells accept 13 and 28-75. The sensor is sound; this build's per-sensor
`instance_id_segmentation` is not. A **per-attempt choice** is implemented
(`FRUIT_WRIST_MODE=pick`: the wrist gets the first look at the descent's start and
whichever camera sees the fruit is that attempt's only sensor) and the cell reads
**11 ticks at 5.6 mm on attempt 0, then 1 and 0 accepted frames**. The decisive
control is that authoring the wrist cameras and **never reading them** drops the
head camera from 75 accepted frames (27/51) to **27 (19/0)** - *mere authorship*
of a second annotated camera takes the first one's mask away. **This build
supports one annotated camera per run.** The remaining step is a scene-pipeline
one (a second render product with an independent annotator graph), not a tracking
one. The head camera plus the estimator stays the working loop.

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


## P213 update - the two-camera blocker was the annotator

P135's "authoring a second annotated camera takes the head's instance mask away" is
narrowed: with `FRUIT_WRIST_ANNOTATORS=rgb,distance_to_image_plane` (no instance mask on
the wrist) the head's `[percept]` counters are unchanged (ep0 18/300 both arms; ep1
255/271 within the branch). The conflict is the second **instance_id_segmentation**
render product, not the camera. The wrist RGB+depth is therefore available as a second
sensor; the direct env does not read it yet (a goal-guided depth window is the next
step). Evidence `logs/p213/`.

## P214 update - the mask-free wrist depth window is not usable

With the P213 RGB+depth wrist (no instance mask), a 35-px depth disk around the head
estimate's projection fits the **hand**, not the fruit: fitted radius 55-73 mm and rms
10-12 mm against a 6.5 cm fruit (32.5 mm radius), centre error **44-62 mm** while the
head estimate on the same ticks is **1.7-2.1 mm**. P135's 3.54 mm wrist result used the
instance mask; without one, the depth window cannot separate the fruit from the fingers.
The remaining second-view options are a **colour segmenter** or a learned mask-free
detector; the probe is default-off and reporting-only. Evidence `logs/p214/`.
