# P135 results - what the tracker converted, and what it did not

All cells are the scripted single-arm line (the two-line's own checks are §5),
seed 5, 3 attempts per cell unless stated, one `scripts/run.sh` invocation per
cell. `C` = every P135 knob unset. `T` = `FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1`.
`W` = `T` + `FRUIT_TRACK_WAIT=1`. `A` = `T` with the constant-acceleration form.
`F` = `T` + `FRUIT_TRACK_CATCH_SPEED=0.20`.

A count on this loop is a branch draw, so the *mechanism* numbers are the ones
read below: the catch-up's **residual** against its 6 mm tolerance and the
**ticks** it took, both printed by the shipped code (`[catch]`, default-off
`FRUIT_TRACK_DIAG=1`).

## 1. The estimator is the shipped path when the model holds

`scripts/268_p135_track_selftest.py` (30 checks): `predict(h)` equals
`p + v*h` to **1.8e-15 m** over 120 frames; a 80 mm/s velocity step is followed
by the **third tick** and its 0.7 s prediction is within **10 mm**; the
constant-acceleration form is **-147 mm** one tick after the same step, which is
the recorded reason it is not the default.

## 2. A fruit-level impulse is damped by the belt - it is not a tracking test

`FRUIT_PERTURB_DX/DY` at descent tick 20 (a scripted stand-in for P95's
collision). The fruit slides a few millimetres and re-settles onto the belt
within ~30 ms, so by the time the descent ends the fruit is back on the
conveyor's line.

| cell | grasp | placed | catch residual mm | catch ticks | corr asked |
|---|---|---|---|---|---|
| C dx 0.10 | 3/3 | 1 | 5.9 [5.8, 5.9] | 10/13/11 | - |
| T dx 0.10 | 3/3 | 2 | 5.8 [5.5, 5.9] | 10/13/12 | 30 |
| C dx 0.20 | 3/3 | 2 | 5.9 [5.2, 6.0] | 9/13/12 | - |
| T dx 0.20 | 3/3 | 2 | 5.8 [5.4, 6.0] | 10/13/12 | 74 |
| C dx 0.35 | 3/3 | 0 | 5.9 [5.6, 6.0] | 9/24 | - |
| T dx 0.35 | 2/3 | 0 | 5.9 [5.8, 5.9] | 9/13/10 | 80 (clamped) |
| C dy -0.10/-0.20/-0.30 | 9/9 | 0 | 5.8-5.9 | 9-24 | - |
| T dy -0.10/-0.20/-0.30 | 9/9 | 3 | 5.8-5.9 | 9-13 | 30 / 74 / 80 |

**The catch-up absorbs every impulse in <= 24 ticks.** The tracker asks for a
30-80 mm correction (the clamp binds at `dy = -0.30`), but the fruit's excursion
has already been damped, so the correction buys no ticks. What the impulse does
cost is the **grasp quality**: at `dx = 0.35` the pads close on a fruit sliding
at 0.35 m/s, all three attempts grasp, and none places - the closed loaded-slide
class (`logs/p42/SIM_LIMIT.md`), which no tracker touches. So the impulse cell is
a *negative for tracking* and a *confirmation of the class split*.

## 3. The non-uniform conveyor: the handover gate is the term

A belt whose speed varies is the transport itself being non-uniform; the fruit
ride it (no slip), so their velocity is exactly the belt's and it is not
constant. `FRUIT_BELT_WAVE_AMP` / `_HZ` drive the surface.

| cell | wave | grasp | placed | catch residual mm | catch ticks |
|---|---|---|---|---|---|
| C | 0.04 / 0.5 Hz | 1/3 | 1 | **297.9, 338.7**, 5.9 | **200, 200**, 11 |
| T | 0.04 / 0.5 Hz | 1/3 | 0 | 5.9, 5.8, **338.7** | 8, 12, **200** |
| A | 0.04 / 0.5 Hz | 1/3 | 0 | 5.9, 5.8, 338.7 | 14, 19, 200 |
| **W** | 0.04 / 0.5 Hz | **2/3** | 0 | **5.6, 5.4, 5.9** | **17, 16, 16** |
| C | 0.08 / 0.3 Hz | 2/3 | 2 | **407.1**, 5.6, 5.8 | **200**, 14, 19 |
| T | 0.08 / 0.3 Hz | 2/3 | 0 | 5.9, 5.9, **407.1** | 10, 13, **200** |
| A | 0.08 / 0.3 Hz | 2/3 | 1 | **407.1**, 4.9, 5.7 | **200**, 14, 19 |
| **W** | 0.08 / 0.3 Hz | 2/3 | 1 | 5.9, 5.6, 5.5 | 16, 15, 17 |

**This is the phase's result.** Under a varying belt the shipped gate
(`fruit_now - grip <= speed*(t_desc + margin)`, a *speed* formula) starts the
descent at the wrong time: the fruit arrives **298-407 mm** from the hand, the
catch-up spends its whole 200-tick budget (its reach is ~200 mm at 1-2 mm/tick)
and the attempt is a `never_held`. The re-aim alone (`T`) cannot fix it - the
correction is clamped at 80 mm and the miss is created *before* the descent
starts. `W`'s gate asks the estimator where the fruit **will be when the leg
ends** and starts the leg when that point is at the catch position: **every**
catch then converges in 15-17 ticks at 5.4-5.9 mm, at both wave rungs, and the
timeouts go 2 -> 0 and 1 -> 0.

Under the nominal belt the same gate is the shipped one with the margin
expressed in position rather than time - `predicted - grip = (fruit - grip) -
v*t_desc <= 0.02` against the shipped `fruit - grip <= v*(t_desc + 0.15)` =
`0.018` - so it is not a new tuning, it is the same margin re-derived from the
estimate. The nominal cell is measured in §4.

The `A` arm (constant acceleration) does **not** help: on a 0.3 Hz wave its
prediction is better in principle, but the term that binds is the handover, not
the descent, and its transient behaviour on a step is the recorded negative (§1).

## 4. The nominal cell

`nom_w` (3 attempts, no wave, `W`): see `logs/p135/close/nom_w.log`. The catch
residuals and the placed count are the control's; the gate is the shipped gate
re-expressed, so this is the expected result and the check is that it holds.

## 5. Perception: the measurement is good enough to drive the tracker

`FRUIT_TRACK_SOURCE=depth` + `FRUIT_TRACK_APPLY=0`: the estimate runs, the
perception measures on every rendered frame, and **every control input stays on
the shipped path**. The bench is 2 attempts, 44 frames, the shipped pool.

| quantity | median | p90 | max | registered bar |
|---|---|---|---|---|
| position error | **4.70 mm** | **6.41 mm** | 233.8 mm (first frame, the fruit entering the frame) | median <= 5, p90 <= 10 |
| diameter error (abs) | **3.42 mm** | **4.29 mm** | 6.68 mm | <= 5 mm |
| sphere-fit rms | 0.11-0.23 mm | - | 0.62 mm | - |

The fit is exact on a synthetic sphere (`268`: 7.8e-12 mm), so the residual
error is the *fruit* being an ellipsoid, not the geometry: the fitted sphere is
1.6-4.1 mm smaller than the nominal diameter, consistently.

**A defect the bench found and the fix it forced**: with the truth source the
filter's `sigma_z` is 0.2 mm, and telling it that a 5 mm measurement is that good
makes it fit the noise - the velocity read **0.026 m/s on a 0.12 m/s fruit** over
an attempt. `FRUIT_TRACK_SOURCE=depth` now defaults `sigma_z` to the bench's
5 mm; the position/diameter table above is measured under that setting.

**In the loop** (`perception/inloop7.log`, 2 attempts, every P135 knob on,
`FRUIT_PERCEPTION_CLOSE=1`): **2/2 grasped**, 1 placed, the catch converged in
**13 and 38 ticks at 5.9 mm**, the filter's error at its last update **5.3 and
3.6 mm**, its velocity **0.116 and 0.118 m/s** against the belt's 0.120. 61
accepted frames and 17 refused for occlusion over the two attempts - the
estimator carried the descent through the refusals. The lost placement is the
closed loaded-slide class, not a tracking miss. (A 2-attempt smoke: no rate.)

Two integration defects this path needed, recorded because both are easy to
re-introduce:

* **The descent's start must force a frame.** The camera runs at 30 Hz and the
  control at 120 Hz, so a single-tick anchor lands inside the camera period three
  times out of four; with a rate-limited anchor the filter is **never created**
  and every aim falls back to the station's nominal x - up to 140 mm from a fruit
  at the band's edge. `measure(force=True)` at the anchor fixed it.
* **A refused frame must return `None`, not the cached estimate.** A cached
  position fed back as a measurement is a lie the filter cannot see, and inside
  the camera period it is counted four times at 120 Hz.

**The occlusion fix, measured.** Once a full cap (`FRUIT_PERCEPTION_FULL_PX` 120)
has set the fruit's radius, a smaller cap fits **only the centre with the radius
held** (`_fit_sphere_known_radius`: Gauss-Newton on `|p-c| = r`). The radius is a
property of the fruit, not of the frame; freeing it on a 20-40 px sliver is what
let the z drift. Re-run of the same in-loop cell
(`perception/inloop8.log`): **2/2 grasped, 1 placed**, catch 13 and 37 ticks at
5.7-6.0 mm, 64 accepted frames and 17 refused, filter error 5.5/6.6 mm - the
residual error is now almost entirely the systematic **+y bias (median +6.0 mm,
dx -0.15, dz +0.70)**, i.e. the ellipsoid's cap, not the fit's conditioning.

**Calibration closes it.** `configs/perception_calibration.json` carries the
installation's offset (measured on the bench: the fitted centre is **+6.5 mm** in
`+y` of the rigid body's origin on this mount, stable across the pool) and
`perception` subtracts it. Same bench, same frames:

| cell | err median | err p90 | dx | dy | dz | dia median |
|---|---|---|---|---|---|---|
| uncalibrated | 6.79 | 10.01 | +0.80 | **+6.55** | +0.10 | 2.37 |
| **+6.5 mm bias** | **1.98** | **5.63** | +0.80 | **+0.05** | +0.10 | 2.37 |
| -6.5 mm bias (the control) | 13.16 | 15.56 | +0.80 | +13.05 | +0.10 | 2.37 |

The wrong-sign row is the proof that the term is a real constant, not a fitted
curve: shifting by -6.5 mm moves the error by exactly +6.5 mm. In the loop
(`perception/inloop9.log`, 2 attempts) the filter's error at its last update is
then **3.4 and 1.3 mm**, the bench over the cell **2.65 median / 4.30 p90**, and
the catch converges in **14 and 22 ticks at 6.0/5.8 mm**.

**A shape model is a measured negative.** `FRUIT_PERCEPTION_SHAPE=spheroid`
(two radii, the long one along the belt - the fruit rolls) reads err 6.85 vs 6.79
and a *worse* diameter (3.52 vs 2.37 median, p90 7.21 vs 3.98), so the sphere
stays the default: the +y term is the mount, not the fruit's shape.

**The remaining perception item is calibration, not modelling.** The offset is
systematic and depends on the fruit's shape (a 65 mm peach +3.5..+6.3 mm, a 30 mm
strawberry +7.4..+7.9), so a single constant is not the fix: the bench that would
close it is a **reference sphere at the station** (a known ball, the way a real
cell calibrates a wrist camera), which the record does not yet have. Until then
the module is a *measurement*, not a metrology instrument, and its 5-6 mm is the
same order as the 6 mm catch tolerance - which is why the in-loop cells lean on
the estimator (the velocity is exact, 0.117 vs 0.120).

## 6. What the tree does when the knobs are unset

`FRUIT_TRACK` unset: no estimator, no callback, no perception, the catch-up reads
the rigid body exactly as before, and `_step_sim` carries one bool test for each
of the two instruments. §7 of the phase's guard list is the acceptance.

## 7. The shipped two-line session runs it

One 2-attempt smoke on the shipped cell (`FRUIT_BIARM`/`FRUIT_BIARM_TWOLINE`
unset = both on, `logs/p135/twoline_try.log`), every tracking knob on, truth
source:

| attempt | arm | catch | outcome |
|---|---|---|---|
| 0 | right | 15 ticks, 5.8 mm, corr 1.4 mm | placed |
| 1 | left | 200 ticks, 247.1 mm, corr 4.3 mm | never-held |

The scheduler runs both arms' attempts through the tracker (the `[catch]` and
`[track]` rows appear per arm), and under the nominal belt the correction is
**1.4 and 4.3 mm** - the tracked path *is* the shipped path, as designed. The
left attempt is the **left arm's known reach class** (the fruit ran past its
downstream band and the catch-up saturated at 247 mm), not a tracker effect; the
shipped cell's own left deficit is the record's (`logs/p60`, `logs/p79`). A
2-attempt smoke is not a rate: the acceptance with the knobs unset is the shipped
control (§6).

## 8. The eye-in-hand camera (added at the owner's request)

Two RGB-D cameras (`FRUIT_WRIST_CAMERA=1`, `240x424`, the head's three
annotators) are authored at build time and **driven from the arm's own jaw centre
and approach axis** on every rendered frame. The head camera's problem is
geometric - it is 0.8 m away and the arm passes between it and the fruit - so a
camera 0.1-0.2 m from the grasp point should not have it.

**Where it looks decides everything.** A camera aimed *at* the grasp point (3 cm
past the jaw) loses the fruit during the descent, because the fruit is 10 cm
upstream when the leg starts:

| aim | mask | refusals (1 attempt) | position err | diameter err |
|---|---|---|---|---|
| 3 cm past the jaw | 94-402 px | **729** | 7.7 mm | 5.8 mm |
| **12 cm past the jaw** | **1684-3241 px** | **2-3** | **3.54 mm** (p90 4.80) | **0.90 mm** (p90 2.63) |

Aimed forward it is the **best sensor in the project**: twice the head camera's
position accuracy and **2.6x its diameter accuracy**, and the mask *grows* as the
hand closes instead of shrinking - the occlusion problem the head camera has is
gone. Its mount offset is its own (+0.75, +2.60, -0.25 mm) and lives beside the
head's in `configs/perception_calibration.json`.

**But it is not yet a closed-loop sensor.** In the loop (`FRUIT_TRACK_SOURCE=depth
FRUIT_WRIST_CAMERA=1`, 2 attempts) one attempt of **two runs** diverges: the hand
drives through the fruit (`125.9 N`), the filter then sees a 6.4 m/s object and
the catch ends 0.4-11 m away. Attempt 0 is clean (17-18 ticks, 6.0 mm). Attempt 1
is the one that fails in both runs, and the two candidate causes measured so far
are not it: the per-fruit radius carry-over was real and is fixed
(`FruitPerception.reset()` at every attempt, which is correct on its own), and the
instance mask cannot pick the wrong fruit (the prim names are zero-padded). The
remaining hypothesis is a **mount/aim that cannot serve both phases**: the
approach needs the camera looking down the corridor, the contact needs it looking
at the jaw, and a single fixed aim is a compromise that one of them loses.

So: **the wrist camera is the right sensor and the wrong bracket**. The next
steps, in order: (a) tilt the mount (or use a wider lens) so the corridor and the
jaw are both inside one frame; (b) switch the aim by phase if the bracket cannot
be tilted; (c) a lens-distortion calibration - the 96-degree lens is used
off-centre, and while the forward aim happens to centre the fruit, a real
installation needs the coefficients. The head camera plus the estimator remains
the working in-loop combination (§5-§6) and the shipped path is untouched: with
`FRUIT_WRIST_CAMERA` unset no camera is authored at all.
