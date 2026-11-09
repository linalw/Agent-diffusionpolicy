# P135 pre-registration - a tracker that does not assume the conveyor

**Pinned before the treatment cells of the envelope ladder were read.** The first
control rung (`dx = 0.10 m/s`, 3 attempts) had been seen when this file was
written; every other cell below (the higher rungs, the `dy` ladder, the nominal
pair, the perception bench and the two-line no-harm) was registered before it ran.
That is recorded as a screening deviation, not hidden.

## 0. The question

The shipped catch is a formula: the aim is `[fruit_x, station_y + lead, fruit_z]`
computed once at the pre-pose, the descent is an open-loop min-jerk leg to it,
the wait is timed on the belt scalar, and the post-arrival catch-up commands
`fruit + v * lead`. Every one of those is exact while the fruit rides a
constant-speed belt.

**Does a model-based tracker - an estimator fed by measurements, a mid-descent
re-aim derived from its prediction, and a catch-up that closes on the prediction
rather than on `position + velocity*lead` - widen the envelope when the fruit's
motion is not the model?**

The owner's requirement is stronger than "the belt speed may change": the cell
is told a target, and the target's motion is not guaranteed. So the test is a
fruit whose velocity changes *during the attempt*, which is what a collision, a
rolling fruit or a speed step looks like at the hand.

## 1. The instrument

`FRUIT_PERTURB_DX/DY/DZ` (m/s), `FRUIT_PERTURB_AT` (ticks into the descent),
`FRUIT_PERTURB_ARM` (`both` by default). One write to the selected fruit's rigid
body velocity, once per attempt, through `FruitSpawner.impulse`. Nothing else in
the line changes: the belt keeps running, the supply keeps feeding, the same
fruit is selected. Off by default; on the shipped path it is one bool test per
tick in `_step_sim`.

Why a fruit-level impulse rather than a belt-speed step: a belt step changes the
release schedule, the feed and every fruit at once, so a count difference could
not be attributed to the tracker. The impulse isolates the tracker, and it is
the mechanism `logs/p95` measured by accident (the other arm's hand displacing an
incoming fruit 28 mm at 0.284 m/s with 4.2 rad/s of spin).

## 2. The arms

* **C** - every P135 knob unset (the shipped formula tracker).
* **T** - `FRUIT_TRACK=est FRUIT_DESCENT_TRACK=1`.

Both arms run the same seed, the same attempt count, the same instrumentation.
The tracked descent's correction is defined against the **conveyor model**
(position at the descent start + belt velocity x elapsed), so under the model it
is zero and T *is* C up to the filter's sub-millimetre estimate.

## 3. Endpoints

1. **Per attempt: `grasped`** (the pads closed on the payload; from the shipped
   predicate) and **`placed`**. A count is a **branch draw** on this loop, so the
   per-cell count is reported, never a rate difference across configurations.
2. **The catch-up residual** - `[task] dynamic catch-up: residual=` - the
   measured fingertip-to-fruit distance at the end of the catch loop, against its
   6 mm tolerance. This is the tracking number, and it is branch-free per leg.
3. **The correction the tracker asked for** - `[track] corr_max=` - which says
   the mechanism engaged, and how much of the leg's budget it spent.
4. Guards: motion budgets on every cell (not re-tuned), the descent's `end=`,
   the landing (`on_belt`), and the acceptance with every knob unset.

## 4. The decision rule

The screen's ladder is `dx` in {0.10, 0.20, 0.35} m/s at descent tick 20 (a
lateral impulse: the payload slides across the belt) and `dy` in {-0.15, -0.30}
m/s (downstream: the fruit speeds up, which is the class the catch-up cannot
close, because the gap grows at `v_fruit - v_tip`).

* **H1 (the mechanism).** The shipped catch's envelope is set by the fruit's
  *extra downstream travel* during the descent plus the catch-up's reach budget
  (200 ticks at the measured ~1 mm/tick = 200 mm, `logs/p48`: the failed
  acquisitions read 220-481 mm = 1.1-2.4x that budget). A rung that adds more
  than that must lose the grasp.
* **H2 (the tracker).** At a rung where C loses at least 2 of 3 attempts, T must
  grasp at least 2 more attempts, with `corr_max` non-zero on those attempts.
* **H3 (the nominal).** With no impulse, T and C must read the same placed count
  and the same catch-up residuals (within 1 mm), and every descent must stay
  inside its motion budget.
* **H4 (no harm).** With every P135 knob unset, `scripts/accept.sh` must read
  8/10 + `fingerprint: matches` + `190: PASS` with its `[fruit]` stream
  byte-identical to `logs/p127/accept_restored.log`, and `scripts/selfcheck.sh`
  must pass.

**Falsifiers.** If H2 fails at every rung, the re-aim is a null and the tracker is
published as a measurement interface only (the estimator and the perception are
still the answer to "where does the target come from", but not a rate lever). If
H3 fails, the tracked descent changes the nominal cell and owes a re-baseline
before any other claim. If H4 fails, nothing ships.

## 5. Perception (phase 3, registered separately below when its bench is built)

The estimator is only half the answer: its *measurements* are the simulator's
rigid-body state. `FRUIT_TRACK_SOURCE=depth` replaces them with a sphere fit on
the rendered RGB-D inside the target's instance mask, through the camera's
authored lens and prim pose. Its bench is `FRUIT_TRACK_APPLY=0` - the estimator
and the perception run, every control input stays on the shipped path - so the
measurement is scored (`[track] err=`) without the cell moving.

Registered endpoint: **median and p90 of `err`** over the measured frames, and
the diameter error against the truth diameter, on a cell whose fruit are the
shipped pool. The bar for putting perception in the control loop is **median
<= 5 mm and p90 <= 10 mm** in position and **<= 5 mm** in diameter, which is half
the catch-up tolerance and a tenth of the shortest fruit.
