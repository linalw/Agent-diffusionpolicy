# P135 method - a tracker, not a formula

## 0. What was wrong

The shipped catch is a **formula**, and the record's own numbers say where it
comes from:

| stage | shipped input | assumption |
|---|---|---|
| aim (`_dynamic_aim`, `tasks.py:10174`) | `fruit[x,z]` at the pre-pose, `station_y + lead` | the fruit is where the conveyor says it is |
| descent wait (`tasks.py:13690`) | `speed = abs(_belt_speed_estimate())`, `deadline = speed * (t_desc + margin)` | the fruit's speed *is* the belt's |
| descent (`_approach`, cartesian) | a min-jerk leg to the fixed aim | no re-planning |
| catch-up (`tasks.py:14077`) | `fruit_now + velocity * catch_lead` | constant velocity over the lead |

Every row is exact while the fruit rides a constant-speed belt; none of them
survives a fruit that is struck, rolls, or meets a speed step. `logs/p95`
measured exactly that: the other arm's hand moved an incoming fruit 28 mm off
its line at 0.284 m/s with 4.2 rad/s of spin, the stale aim met it with the
pads, and the attempt ended `never_held`.

The owner's requirement is the general case: *the target's motion is not
guaranteed to be uniform*, and its position and diameter must come from a model,
not from the simulator.

## 1. The estimator (`src/fruit_sorting/tracking.py`)

A Kalman filter over the fruit's centre: position + velocity, with the velocity
allowed to change by `sigma_a * dt` per step (the manoeuvre allowance) and the
allowance inflated by a large normalised innovation.  On a constant-velocity
fruit the mean is the measurement - `predict(h)` equals `p + v*h` to machine
precision - which is what keeps the model-consistent path untouched.

A constant-*acceleration* form exists and is **not** the default: a struck fruit
changes *velocity*, and a CA fit through a step reports a 2-3 m/s^2 transient
that integrates to `0.5 a T^2` = up to 0.7 m over the remaining descent.  Measured:
the CV form's prediction error one tick after an 80 mm/s step is 16 mm, under
3 mm by the third tick; the CA form's first-tick correction is -741 mm with the
sign flipping again 40 ms later.

## 2. The correction is defined against the conveyor

```
correction(t_go) = tracker.predict(t_go) - (p_at_descent_start + belt_v * (elapsed + t_go))
aim(t_go)        = grip + clamp(correction(t_go), corr_max)
```

This is the load-bearing definition. It is **zero when the fruit rides the
belt**, so the descent's geometry, its motion budget and the two-line clearance
are the shipped ones whenever the model holds; the only thing that moves is the
part of the fruit's motion the conveyor does not explain. It needs no new
constant for when the correction starts.

`FRUIT_TRACK_CORR_MAX` (0.08 m) bounds what one descent can spend: a correction
larger than the leg can execute is the catch-up's job, and it measures its own
residual.

## 3. The mid-descent re-aim (`_approach(..., track=...)`)

`_approach` gains an optional callback `t_remaining -> jaw point`, re-evaluated
every tick; the remaining min-jerk profile is spent along the line to the *new*
aim (`point = start + (aim - start) * alpha_i`, with `alpha_i` the shipped
normalised profile). The speed schedule and the zero-arrival-velocity are the
profile's own, so the motion gate sees the shipped leg; only the direction and
the endpoint move.

The moving catch passes `_track_aim`, which is the correction above. A shipped
caller passes nothing and gets the old straight line, bit for bit.

## 4. The catch-up closes on the prediction

`catch_centre = tracker.predict_at(catch_lead_s)` instead of
`fruit_now + velocity * catch_lead_s`. On a belt-riding fruit the two agree (the
filter's mean); on a manoeuvring fruit the prediction is the one that knows the
velocity has changed. The break test stays the **measured** tip-to-fruit
distance, so the residual remains an honest number.

## 5. Perception (`src/fruit_sorting/perception.py`)

`FRUIT_TRACK_SOURCE=depth` replaces the rigid-body read with

1. one render + `rgb`, `distance_to_image_plane`, `instance_id_segmentation`;
2. the target's pixels from the mask (the label is the prim path);
3. back-projection through the **calibration** - the authored focal length and
   aperture (a ratio, so the stage's units cancel) plus the camera prim's world
   pose - into world points;
4. a trimmed least-squares sphere fit -> centre + radius.

The frame's own shape sets the intrinsics, so a `FRUIT_CAMERA_RES` override
cannot desynchronise them. A dropped frame (target out of view, degenerate fit)
returns `None` and the filter predicts through it; it **never** falls back to
the simulator's state, which would make a "perception" run partly a ground-truth
run.

The estimator's `err=` column is the only place the truth is read, and it is
default-off.

## 6. The instrument (`FRUIT_PERTURB_*`)

One velocity impulse on the **selected** fruit, `FRUIT_PERTURB_AT` ticks into the
descent, through `FruitSpawner.impulse`. It is the scripted form of P95's
accident, and it isolates the tracker: the belt keeps running, the supply keeps
feeding, the same fruit is selected. A belt-speed step was rejected as the
instrument because it changes the release schedule and every fruit at once, so a
count difference could not be attributed.

## 7. What the tree does when the knobs are unset

`FRUIT_TRACK` unset -> none of the tracking code runs; `_track_measure` is not
called, `_approach` gets no callback, the catch-up reads the rigid body exactly
as before, and `_step_sim` carries one `if self._perturb_on` test. The no-harm
gate is `scripts/accept.sh` plus a byte-identical `[fruit]` stream.
