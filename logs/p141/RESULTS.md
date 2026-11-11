# P141 - the belt state becomes an observation

**Scope.** The policy's condition was blind to the conveyor: the goal was a
selection-time snapshot `[xyz, v(3), diameter, bin_index]` and the 26th proprio
scalar was the *pin* (`0.12`), a per-episode constant. On a belt whose speed
changes - the record's `FRUIT_BELT_WAVE` cells, 0.04 m/s at 0.5 Hz - two frames
33 ms apart differ by ~1.3 mm, inside the camera's own 2 mm position error, so
the wave is **not observable from the image horizon** at any horizon length that
fits the encoder. It has to be an input.

Nothing here changes the shipped default: every new term is behind a gate that
is off unless asked for, and the acceptance proves it.

---

## 0. The defect the first wave collection exposed

A 3-episode collection under the wave recorded `belt_speed` with
**ptp = 0.0000** (every frame exactly 0.1200). The channel was reading
`Conveyor.encoder_speed`, which is derived from the **cleat phase** - and the
cleats have been off by default since the P43/P71 era, so `Conveyor.step` returns
before recomputing it. `encoder_speed` is a **setpoint echo**: it reports the
value it was initialised with no matter what the surface does.

`Conveyor.surface_speed` (new) returns `self.speed`, the value `_apply_speed`
actually writes into `PhysxSurfaceVelocityAPI`, and `tasks._belt_speed_estimate`
now reads it. On the shipped constant belt the two are the same number, which is
why the acceptance is byte-identical (section 3). Under a wave, only the new one
is the belt that is moving.

This is a **defect fix, not a knob**: before it, every reader of
`_belt_speed_estimate` (the trigger, the descent's schedule, the 26th channel)
saw 0.12 while the belt ran 0.08-0.16.

## 1. What the model gets now

| stream | shipped | P141 | gate |
|---|---|---|---|
| goal | 8-D `[xyz, v(3), dia, bin]` | **10-D** + `(v_belt, a_belt)`, refreshed **every tick** | `FRUIT_OBS_GOAL_AUX=1` |
| proprio | 25-D | **26-D**, 26th column **per frame** when the store carries the trace | `FRUIT_OBS_SPEED=1` |
| image | `obs_horizon=2` x 5 ch | **4** frames (config) | `--obs-horizon 4` |
| exec | `execute_steps=4`, DDIM 16 | env knobs | `FRUIT_POLICY_EXEC_STEPS`, `FRUIT_POLICY_DDIM` |

`a_belt` is a first-order low-passed derivative (tau 0.05 s) with **one**
implementation, `data.belt_accel_trace`, used by the store loader; the live loop
(`rl_env._belt_state`) runs the same filter, so the recorded and deployed
functions agree.

**Units are fixed, never store statistics** (the P28-B rule): `v_belt` is the
proprio channel's own `(0.12, 0.05)` pair, `a_belt` is `(0.0, 0.15)`. On a
constant belt every training frame has `a = 0`, so a derived std would divide by
~1e-6.

## 2. Warm starts (the function is unchanged at step 0)

| widening | mechanism | identity |
|---|---|---|
| prose 25 -> 26 | one **zero** column on `condition.proprio.0.weight` (P28-B, existing) | the channel contributes `0 * x` |
| goal 8 -> 10 | two **zero** columns on `condition.goal.0.weight` | same |
| horizon 2 -> 4 | `new_w = 0.5 * [old_w, old_w]` on `visual.net.0.weight` | a static window reproduces the 2-frame embedding to **4.8e-07** |

The horizon identity is the design: the visual encoder folds the horizon into
its channels, so a repeated kernel is the "temporal average of two windows" warm
start, and on a static scene it is exact.

## 3. No-harm (measured)

* `scripts/accept.sh` with every knob unset: **7/10 = 70 %**, 9.5 s/attempt,
  `fingerprint: matches configs/motion_reference.json`, `190: PASS`, and its
  **459 `[fruit]` lines are 459/459 byte-identical** to
  `logs/p136/accept_final.log` - twice: after the observation plumbing and again
  after `Conveyor.surface_speed`.
* `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new
  `P141 observation aux` leg (**47 checks**: the gate table, the per-frame
  column vs the pin, the 10-D goal, the fixed normaliser, all three wideners,
  a static-window identity, a real `moe_v13s` loading and forwarding at
  10/26/4, and the single-sited wiring).
* references **`61fb5202` / `61fb5202`** and **`18b101bf`** untouched.

## 4. Data

`datasets/p141_wave` - the single-arm collector under
`FRUIT_BELT_WAVE_AMP=0.04 FRUIT_BELT_WAVE_HZ=0.5`, `FRUIT_OBS_SPEED=1`, so every
episode carries a per-frame `belt_speed` array. (The single arm is the
configuration the wave instrument was measured on, P135.)

**Filled in after the collection**: episodes, frames, the trace's min/max, and
the fine-tune.

## 5. The store

`datasets/p141_wave` - the single-arm collector, `FRUIT_BIARM=0`,
`FRUIT_BELT_WAVE_AMP=0.04 FRUIT_BELT_WAVE_HZ=0.5`, `FRUIT_OBS_SPEED=1`:

| | |
|---|---|
| episodes | **10** (1733 windows) |
| recorded frames | 1923 |
| `belt_speed` | **0.0800 - 0.1600**, median per-episode **ptp 0.0800** |
| manifest | `supply.belt_speed=0.12`, `scene`, `physics.tracking`, `collection` |

The trace is the wave: before the `surface_speed` fix the same cell recorded
**ptp 0.0000** at a constant 0.1200.

## 6. The fine-tune

`checkpoints/p141_wave` from `moe_v13s` + the wave store + `demos_v11`
(`--goal-aux --obs-horizon 4`, 6 epochs, lr 5e-5, ones, batch 32):
windows **11011** (wave 1733 + base 9278), final loss **0.0149**, router acc
**0.993**, best `demo_val` **0.0133**, `val_loss` 0.0061.

The three wideners print their own rows and the saved artifact carries them:

```
[finetune] P141 goal: widened 8 -> 10 with (v_belt, a_belt), zero columns,
           normaliser (0.12, 0.0) / (0.05, 0.15)
[finetune] P141 horizon: visual encoder 2 -> 4 frames (kernel repeated, halved)
config: goal_dim=10 proprio_dim=26 obs_horizon=4   params 4.603 M (was 4.595)
visual.net.0.weight: (32, 20, 5, 5)               normaliser 10 / 26
```

## 7. Does the model use the channels? (measured, not asserted)

`logs/p141/probe_belt_channel.py` - offline, deterministic sampler (the same
condition gives the same chunk: **0.00000 rad** on a repeat, and a 1e-6 goal
nudge is below float32 resolution), 12 windows spread over the 10 episodes.
The perturbation replaces the belt channels with the **constant-belt belief**
(`v = 0.12`, `a = 0`, 26th proprio `= 0.12`):

| perturbation | median mean `|dAction|` |
|---|---|
| repeat the same observation | **0.00000 rad** |
| 1e-6 goal nudge (numerical floor) | **0.00000 rad** |
| **goal pair `(v_belt, a_belt)`** | **0.00084 rad** |
| **proprio 26th column** | 0.00043 rad |
| **both** (the shipped-belief swap) | **0.00094 rad** (max 0.00227) |

**Calibration against the input the policy was already conditioned on**:

| reference shift | median `|dAction|` |
|---|---|
| goal `x` +1 mm | 0.00054 rad |
| goal `x` +5 mm | 0.00231 rad |
| goal `diameter` +1 mm | 0.00091 rad |

So the belt state moves the action as much as **~2 mm of fruit position** - the
same order as the camera's own position error (1.98 mm) and a third of the catch
tolerance (6 mm). Both channels are used, the goal pair is the larger term, and
the sum is sub-additive. **It is a real but modest input**, and that is the
honest size of it; the record's failures are the closed loaded-slide class, which
no conditioning can reach.

## 8. Latency (the budget `execute_steps` trades against)

Same probe, 12 timings per budget on the RTX 5090, one `act` each:

| denoising steps | p50 | p95 |
|---|---|---|
| 16 (shipped) | **26.4 ms** | 27.3 ms |
| 8 | **13.4 ms** | 14.2 ms |

**`FRUIT_POLICY_EXEC_STEPS=2` needs the p95 under 16.7 ms** (two physics ticks at
120 Hz), and at 16 steps it is 27.3 ms - the loop would be inference-bound and
the roll would buy nothing, which is the plan's own precondition. At **8 steps
the p95 is 14.2 ms**, so the coherent fast-rolling pair is
`FRUIT_POLICY_EXEC_STEPS=2 FRUIT_POLICY_DDIM=8`. The pair is implemented and
resolves from the environment; it is **not** adopted as a default (nothing here
measured its effect on the task).

## 9. Integration (one live episode)

`110_rl_rollout --presentation direct` with
`FRUIT_OBS_SPEED=1 FRUIT_OBS_GOAL_AUX=1 FRUIT_BELT_WAVE_AMP=0.04`:

```
[rl] loaded checkpoints/p141_wave/policy_best.pt (obs_horizon=4, action_horizon=16)
[rl] env ready: presentation=direct ... tasks_md5=c83fd7c5
[rl] episode 0: pear grade=A d=6.1cm bin=0 arm=left y=+0.559
```

The width guards pass, the 4-frame buffer fills, `_goal_vector` assembles the
10-D goal from the live belt state and the episode steps. The episode itself then
hits **P139's park-slot defect** (`fingertips 103342 mm`, `[belt] recirculating
... waited 60s`) - that is the direct lane's standing item, unchanged by this
phase, and it is why no episode count is quoted here.

## 10. What is *not* claimed

* **No success-rate A/B.** The wave store is 10 episodes of the single arm; a
  rate needs the WS-4.2 N=5 protocol on the direct lane, which is blocked by the
  P139 park-slot defect and the `on_output_belt(final)` scorer.
* **No "the policy is faster" claim.** Section 8 prices the latency budget; it
  does not measure a task-time gain (`execute_steps` is not flipped).
* **The 1 mrad sensitivity is not a guarantee of behaviour.** It says the
  channels are *used at a physically meaningful scale*; whether a wave-aware
  policy places more fruit is the open A/B.
* **The wave collection is single-arm only.** The two-line collector wedged in
  the first attempt of the wave cell (the known renderer bridge class), so the
  two-line wave store is not built.
