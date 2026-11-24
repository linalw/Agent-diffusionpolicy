# P233 results: the trigger now sees the real belt - and the disturbance loss is the speed ceiling, not the schedule

**2026-11-24, `logs/p233/`.** A correctness fix, default off, measured at 0.18
under a wave. **Not adopted** (it moves the branch and owes the two-line gate).

---

## 1. The cells

`FRUIT_BELT_SPEED=0.18`, `FRUIT_BELT_WAVE_AMP=0.03` at 0.5 Hz (surface **0.15-0.21**),
seed 901 x 6 episodes.

| cell | trigger's speed source | placed | `speed=` at fire | `t_arrive` at fire |
|---|---|---|---|---|
| A (shipped) | `encoder_speed` (setpoint echo) | **4/6** | **constant 0.180** (sd 0.0000) | 0.94-1.52 s, **sd 0.20** |
| B (treatment) | **`surface_speed`** | **4/6** | **0.151-0.210** (sd 0.0187) | 1.12-1.56 s, **sd 0.15** |

Both arms: the same two failures, both `fruit did not follow the gripper`.

## 2. P1 PASSES decisively

The treatment's fire row prints five distinct speeds inside the wave band
(0.151 / 0.162 / 0.164 / 0.171 / 0.210) while the control prints one value, six
times. The route works, and the manipulation check is the row itself.

## 3. P2: the signature is `t_arrive`, not `dy` - a correction

The registration predicted that `dy` (= `lead x v`) would scatter in B and not in
A. **It scatters in both** (sd 3.56 vs 3.91 cm) because `lead` is not constant: the
acquisition window adds `|jaw-station| / 0.20`, and the jaw's distance at the fire
varies run to run. That is a **nuisance variable**, the same one P228's correction
found in `t_arrive`.

The field that *is* branch-free is **`t_arrive` itself** - the remaining time the
trigger computes. With the setpoint echo it is wrong by up to 2x; with the surface
speed it is right. Measured: **sd 0.20 s -> 0.15 s** (a 25 % tightening), and the
minimum rises from 0.94 s (a fire that thought it had 0.94 s when the fruit was
actually moving at 0.21) to 1.12 s. At 0.18 m/s, 0.20 s of sd is **36 mm** of
mis-scheduled fruit travel.

## 4. P3/P4: the count is a tie, and the loss is not the schedule

**4/6 vs 4/6**, same class, so neither an improvement nor a harm is established at
n = 6. **But the cell pair produces the phase's real finding**:

| `v` | wave | placed | pooled |
|---|---|---|---|
| 0.18 (P229) | none | **11/12** | 92 % |
| 0.18 (here) | ±0.03 (0.15-0.21) | 4/6 + 4/6 | **8/12 = 67 %** |

**At 0.08 the same instrument is free (11/12 at ±50 % and ±75 %); at 0.18 a ±17 %
wave costs a quarter of the placements.** And the trigger fix does **not** recover
them - because the failure is the **crest**: 0.21 m/s is past the measured usable
ceiling (~0.18-0.20, P229), so a third of the fruit arrive too fast for the grip,
and no scheduling arithmetic changes how fast a fruit is moving.

**So the disturbance tolerance is bounded by the speed ceiling, not by the
trigger.** That is the sentence the ladder was for.

## 5. What this leaves

* `FRUIT_TRIGGER_SURFACE_SPEED` is a **correctness fix** (the timing error halves)
  and a **count-null** at this cell: keep it default off, and if it is ever
  shipped it owes the two-line gate, both references and a store re-baseline - the
  same price as P87's release trim, for a smaller effect.
* The **disturbance ladder** now reads: robust at 0.08 (±75 %), degrading at 0.18
  (±17 %), because the crest crosses the usable ceiling. A deployment's spec is
  therefore "**max surface speed** matters, not the mean" - a line that averages
  0.18 but peaks at 0.21 is a 0.21 line for this hand.
* The **next rung** if the objective's speed is pushed: a **peak-speed limiter**
  (hold the belt at or below the usable ceiling and let the queue absorb the
  crest) - which is a supply/scheduling lever on the *line*, not on the arm, and
  is the kind of thing the papers' schedulers (conveyor PnP, AHEAD's
  `T_lead`) assume rather than test.

## 6. Pins

`rl_env.py` (the knob, the field selection at both `should_fire` sites),
`scripts/selfcheck.sh` (leg `P233 trigger speed`: default off, both field names,
one shared variable); `tasks.py` **`c16c8291`** unchanged; references
**`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint `p227_panda156`
used as-is. Evidence `logs/p233/{PREREG.md, A_stale/, B_surface/}`.
