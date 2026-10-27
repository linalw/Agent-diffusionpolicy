# P52 phase 1 — MODEL_CENSUS: the action plumbing, what speed the actions carry, and the re-timing headroom

Measured **offline** 2026-10-27 (no simulator, no `src/` edit, no commit). Tree: HEAD
**`da0c914`**. Reproduce every number with

```bash
python3 logs/p52/model_census.py --write        # ~2 min, one GPU pass over the checkpoint
```

which prints (`logs/p52/model_census_out.txt`, 197 lines) **A** the plumbing, **B1** the
demos' action stream, **B2** the policy's own chunks (`policy_chunks.npz`, cached),
**B3** the recorded executed stream, **C** the `[motion]` legs, **D** the re-timing
arithmetic, **E** the failure classes. The only non-offline step is B2, which loads
`checkpoints/moe_v12` and samples it on **demo observations** (torch only - no Isaac,
no camera, no physics).

**The four sentences this census exists to support.**

1. The policy emits **9 absolute joint positions** (7 arm joints [rad] + the finger
   opening [m]) and the env writes them **straight to the drive targets** - there is no
   IK, no Cartesian clamp and no joint clamp on this path (`rl_env.py:3033-3039`).
2. One decision = **4 control ticks = 33.3 ms of sim** and executes **4 of the 16**
   predicted actions, i.e. the chunk is replayed at **30 Hz of sim** with a 0.533 s
   planning horizon (`rl_env.py:2945, 2978-2990`; `60_eval_policy.py:288, 344`).
3. **A successful direct episode is 54-60 % policy phase**: 8.46-9.07 s of policy motion
   plus 5.64-6.50 s of scripted primitive, and only **2.08-2.23 s (25 %)** of the policy
   phase is the belt's own transport floor - so **6.4-6.8 s per episode is arm motion a
   time-scale can touch** (11-15 % of the whole episode at s = 1.25-1.5).
4. **The legal joint-velocity headroom for that re-timing is 2.3-3.3x**; the binding
   object is **j4** (its p99 emitted step is 2.14 rad/s against a 5.45 rad/s limit) and
   the *worst single emitted step already sits at 1.14x* - so 1.25 and 1.5 are inside
   the legal envelope and 2.0 is a different regime.

---

## 1. (A) The action plumbing - the exact path

### 1.1 The action vector

`checkpoints/moe_v12` (shipped) and `moe_v13s` carry the **same config**:

| field | value |
| --- | --- |
| `action_dim` | **9** |
| `action_horizon` | **16** |
| `obs_horizon` | 2 |
| `proprio_dim` / `goal_dim` | 25 (22 joints + finger + 2 tactile) / 8 |
| `image_size`, channels | 128 x 128, 5 (RGB + depth + target mask) |
| training chain / inference | `num_diffusion_steps` 100 (cosine) / **DDIM-16** |

The 9 channels, in the checkpoint's own normaliser units (rad for the arm, m for the
finger):

```
action_mean [j1..j7, finger, finger] = +0.259 +0.023 -0.287 +0.883 +0.227 +0.113 -0.252 +0.035 +0.035
action_std  =                          1.439 0.255 1.513 0.246 1.235 0.647 1.333 0.012 0.012
```

`action[:7]` are the **active arm's seven absolute joint POSITIONS [rad]**,
`action[7]` is the finger opening [m] clipped to `[0, 0.044]`, and `action[8]` mirrors it
and is only recorded - the interface is stated in `rl_env.py:62-64` and implemented at
`rl_env.py:3036-3045`. **Not deltas. Not Cartesian. Not normalised at execution time**:
`denormalize_action` runs inside `PolicyRunner.act` (`runtime.py:770-771`), so what the
env sees is already in rad/m.

### 1.2 The path, in order

| # | step | site |
| --- | --- | --- |
| 1 | the driver samples a chunk every 4 ticks: `chunk = env.sample_chunk()` | `110_rl_rollout.py:261-263` |
| 2 | the camera frame is pushed on the same 4-tick grid, then `PolicyRunner.act(proprio, goal, num_steps=16)` | `rl_env.py:2337-2367` |
| 3 | DDIM-16 from one noise draw (seeded by `FRUIT_POLICY_SEED`), `(1, 9, 16)` in normalised units, then denormalised | `runtime.py:750-771` |
| 4 | `env.act(chunk, execute_steps=4)` executes up to 4 actions, **one physics tick each** | `rl_env.py:2924-2931` |
| 5 | optional shapers (all default off): RTC/VLASH chunker, `FRUIT_POLICY_TRACK`, `FRUIT_A2C2`, DAgger | §1.5 |
| 6 | `_apply(action)`: `set_dof_position_targets([action[:7]], arm_dofs)` and `[[finger, finger]]` on the finger dofs | `rl_env.py:3020-3045` |
| 7 | `advance(1)` = `SimulationManager.step(1)` + `update_app(steps=0)` | `rl_env.py:1716`, `common.py` |

**There is no IK on this path.** `ik_step` (and with it `FRUIT_IK_MAX_STEP = 0.5 rad`,
`FRUIT_IK_GAIN`, `FRUIT_IK_DAMPING`, `control.py:146-147, 423, 494`) belongs to the
scripted primitive; the direct loop never calls it. The policy's targets go to the
articulation's position drives, whose own limits are the USD `maxForce`
(40/27/7 N·m) and the joint ranges - and the drive is a **torque source** at the real
operating point (measured 8.1-10.4 mm lag = 17-97x past saturation,
`logs/p44/CAP_CENSUS.md` §1.1).

### 1.3 The cadence arithmetic

| quantity | value | site |
| --- | --- | --- |
| control/physics tick | 1/120 s, `FRUIT_SUBSTEPS` 1 | `control.py:30`, `common.py` |
| observation + model call | every **4th** tick -> **30 Hz of sim** | `rl_env.py:2945` (`if self._step % 4 == 0`) |
| `execute_steps` | **4** (one action per control tick) | `rl_env.py:900`, `2931` |
| **one decision** | **4 ticks = 33.3 ms of sim**, 4 of 16 actions executed (25 %) | `rl_env.py:2942-2993` |
| chunk coverage | 16 actions x 33.3 ms = **0.533 s of geometric path** | - |
| DDIM | 16 denoising steps per decision | `60_eval_policy.py:49` |
| policy horizon | 1500 control steps = **12.5 s of sim**, then the primitive | `rl_env.py:457-481` |
| demo cadence | 30 Hz (4-tick decimation) - the same grid | `_record_tick`, `rl_env.py:3767-3772` |

So **the model is asked 30 times per second of simulated time and each answer is
re-timed over 33.3 ms**; the planning horizon is 4x what is executed (the LeRobot
receding-horizon convention).

### 1.4 What one episode is actually made of (P43 park A/B, 150 episodes)

| arm (park) | n | ticks/ep | sim s/ep | decisions | policy phase | placed: policy + scripted | app wall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A (`ready`) | 75 | 1827 | 15.22 | 259 | 1034 ticks (57 %) | 9.07 s + 5.64 s | 28.0 s/ep |
| B (`back`) | 75 | 1812 | 15.10 | 246 | 985 ticks (54 %) | 8.46 s + 6.50 s | 28.2 s/ep |

**And within the policy phase, the belt floor** (the fruit travels 0.25-0.27 m at
0.120 m/s between the first model call and the trigger's fire tick, so that interval
cannot be shortened by any arm change):

| arm | belt floor | as a share of the policy phase | **arm motion** | s=1.25 saves | s=1.5 saves |
| --- | --- | --- | --- | --- | --- |
| A | 2.23 s | 25 % | **6.84 s** | 1.71 s = **12 % of the 14.71 s episode** | 2.28 s = 15 % |
| B | 2.08 s | 25 % | **6.38 s** | 1.60 s = **11 % of the 14.96 s episode** | 2.13 s = 14 % |

This is the number the phase-2 prediction is built on: **a time-scale touches ~6.4-6.8 s
per episode, and nothing in the scripted phase** (the primitive's carry/place/release is
45 % of an episode and is untouched by any policy-side lever - the P44/P46 speed cells
are the scripted line's own lever, and their cost class is measured).

### 1.5 Every env-side shaper that exists (all default off)

| knob | default | what it does to the applied action | site |
| --- | --- | --- | --- |
| `FRUIT_POLICY_TRACK` | 0 | adds `J^+ v_fruit dt` to the 7 targets (a velocity feed-forward, not a scale) | `rl_env.py:945, 3584-3609` |
| `FRUIT_A2C2` + `_GAIN`/`_CLAMP` | off | a trained 9-D **correction head** added per step | `rl_env.py:1291-1298, 3026-3030`; `policy/correction.py` |
| `FRUIT_POLICY_EVENT` | 0 | picks the **per-decision horizon** from the chunk's continuity (not the action) | `rl_env.py:2939-2940, 3560-3582` |
| `FRUIT_RTC` / `FRUIT_VLASH` | 0 | async chunk switching, one action per tick, freeze + soft inpaint | `runtime.py:100-124` |
| `FRUIT_POLICY_GDP` | 0 | samples K chunks, executes the min-OoD one | `runtime.py:503-598` |
| `FRUIT_WAIT_GATE` | 0 | repeats the last chunk instead of calling the model when the fruit is far | `rl_env.py:2384-2437` |

**There is no clamp and no rate limiter**: the only clip on the applied action is
`finger in [0, 0.044]`. A policy command past a joint limit is therefore *not refused* -
the drive pushes into the limit until the joint stops (the same class the `[acq] ... clip_min`
row reports for the scripted line). **Any time-scale must therefore be a *re-timing* of an
already-unclamped stream, and its guard is the joint-velocity budget, not a code assert.**

---

## 2. (B) What speed the actions carry

### 2.1 The demo's per-leg dynamics (the `[motion]` rows, 6 batteries)

`|v|cmd`/`|a|cmd` = the commanded profile's peak (`tasks.py:4287`); the `steps=` block's
`|v|max` is the **achieved** TCP speed (MotionMonitor). 147 legs over the shipped
single-arm acceptance, the pear, the two-line, the P43 acceptance and the P44 controls.

| leg | n | d | ticks | `|v|cmd` | `|a|cmd` | achieved `|v|max` (median) | cone | legs over cone |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `grasp_lift` | 50 | 21.0 cm | 164 | **0.291** | **0.665** | 0.320 (0.242-1.107) | 1.02x | 8/50 |
| `place0` | 23 | 57.0 cm | 375 | **0.343** | **0.340** | 0.331 | 0.87x | 0/23 |
| `place1` | 24 | 37.7 cm | 248 | **0.343** | **0.527** | 0.317 | 1.01x | **11/24** |
| `approach` (descent) | 50 | 5.7 cm | 89 | 0.150 | 0.800 | **0.109** (ach/cmd **0.73**) | - | - |

Two engine notes that matter for the re-timing:

* **The lift's speed is its cap, and 16/50 legs exceed 1.5x their own command** - those
  are the escape legs (the W8-B loaded slide), not a speed effect: the payload walks out
  and the monitor reads the reaction. The lift's *median* achievement is 0.320 m/s.
* **The descent is the one leg the servo, not the cap, sets**: it achieves 0.109 of its
  0.150 command (ach/cmd 0.73) and ends **9.3 mm short (8.1-10.4)** of the pose it was
  sent to, with `|a|max` median 1.80 m/s² (a boundary interaction, not the 0.8 command).
* **`place1` exceeds the 4.273 m/s² cone budget on 11/24 legs** (1.01x mean, 1.31x max) -
  the unloaded second place leg's transients. The cone is a *report* on this line
  (`--strict-cone` fails on the control too, P44 amend §9).

### 2.2 The demos' action stream (what the policy is trained to imitate)

10178 30 Hz steps over 50 episodes (339 s of demo time); per-joint `|delta|` per step at
30 Hz, with single-tick **mode jumps** split out (a step > 0.05 rad whose both neighbours
are < 0.02 rad - the grasp-config snap / a leg boundary; 9-117 per joint over the corpus).

| joint | p50 | p90 | p99 | p99 [rad/s] | % of limit | smooth max [rad/s] | `v_lim` [rad/s] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| j1 | 0.0020 | 0.0297 | 0.0729 | 2.19 | 13 % | 3.60 | 16.75 |
| j2 | 0.0025 | 0.0162 | 0.1066 | 3.20 | 19 % | 14.49 (a jump) | 16.75 |
| j3 | 0.0000 | 0.0015 | 0.0255 | 0.76 | 14 % | 4.72 | 5.45 |
| j4 | 0.0065 | 0.0344 | 0.0775 | 2.32 | **43 %** | 17.42 (a jump) | 5.45 |
| j5 | 0.0000 | 0.0298 | 0.0642 | 1.93 | 9 % | 4.83 | 20.94 |
| j6 | 0.0000 | 0.0328 | 0.1059 | 3.18 | 15 % | 3.60 | 20.94 |
| j7 | 0.0000 | 0.0540 | 0.1200 | 3.60 | 17 % | 3.94 | 20.94 |

**The whole demo stream commands 2.81 rad/s at p99 (13 % of the tightest limit).** The
finger channel: p99 4.1 mm/step = 0.12 m/s of the 1.0 m/s drive limit (the close is a
48-tick clock, not a speed).

**And the path rate, which is the fair comparison for a chunk:**

| stream | net per 4 steps (summed over 7 joints) | net per 16 steps (summed) |
| --- | --- | --- |
| demo (non-overlapping windows) | **0.141 rad** | **0.769 rad** |
| policy chunk (offline sampling) | **0.183 rad** per decision | **0.648 rad** per chunk |

So **the policy commands the same order of path per unit time as the demos** (1.3x per
4 steps, 0.84x per 16). The policy is not "slower" in the amplitude of what it asks for.

### 2.3 The policy's own chunks (offline, `moe_v12`, DDIM-16, seed 11)

72 chunk pairs on demo observations; per-joint `|delta|` **inside** a chunk (the smooth
part the model emits), on the **3 executed** steps, and across a **re-plan** (chunk k+1's
first action minus chunk k's 4th, i.e. what the env actually replays at 30 Hz):

| object | p50 | p90 | p99 | p99 [rad/s] | max step | worst joint |
| --- | --- | --- | --- | --- | --- | --- |
| intra-chunk (all 15) | 0.004-0.010 | 0.012-0.038 | 0.033-0.078 | **1.0-2.3** (5-43 %) | 0.08-0.16 | j1/j4/j5 |
| intra-chunk (executed 3) | 0.003-0.011 | 0.013-0.037 | 0.045-0.077 | **1.3-2.3** (6-43 %) | 0.08-0.16 | j3 |
| **re-plan boundary** | **0.018-0.045** | 0.043-0.17 | **0.11-0.27** | **3.3-8.1** (16-148 %) | **0.30** | **j4** |

**This is the census's most important structural read.** The emitted chunk is smooth and
slow (p99 1.0-2.3 rad/s, *zero* executed joint-steps over a limit at s = 1.0), while the
**re-plan discontinuity is 3-5x larger than any intra-chunk step** and alone puts **7/504
(1.4 %) boundary joint-steps over a limit at s = 1.0, worst j4 6/72 = 8.3 %**. A
time-scale multiplies the first and leaves the second exactly as it is.

The recorded rollout stores confirm the consequence from the other side (B3): their 30 Hz
stream samples **chunk index 0 only** (`_record_tick` fires when
`_step == _observed_step`, `rl_env.py:3767-3772`), i.e. each recorded pair spans 3 executed
steps *plus* the boundary jump - which is why that stream already reads **2.2-4.2 % of its
joint-steps over a limit at s = 1.0** (p37_park j4 883/5138 = 17.2 %; r9_awr j4 214/3205 =
6.7 %). **Do not read a recorded rollout stream as the intra-chunk rate.**

### 2.4 What a time-scale multiplies, and what it does not

* **Multiplied**: the 15 intra-chunk deltas (the smooth motion) -> joint velocity x s,
  acceleration x s², jerk x s³.
* **Not multiplied**: the re-plan discontinuity (a position step between two plans), the
  belt floor (2.08-2.23 s), the scripted primitive (45 % of the episode), and the
  30 Hz decision cadence (the model is still called every 4 ticks).
* The drive's response to the sum of the two is what the *achieved* speed is; the drive is
  a 0.2 s first-order lag at a saturated torque, so a jump is filtered into a ramp and a
  ramp is tracked. **A re-timed chunk raises the ramp component only** - so the expected
  gain is the ~6.4-6.8 s of arm motion, not the whole policy phase.

---

## 3. (C) The re-timing headroom - per leg, and for the policy's own stream

A time-scale `s` executes the same geometric path in `1/s` of the ticks: **v x s, a x s²,
j x s³**. `s_*` below is the scale at which that one limit is reached.

### 3.1 The demo's legs, against every measured limit

| leg | cmd v | cmd a | `s_joint` (tip 0.79 m/s) | `s_cone` (a-budget) | `s_pay` (v meets a) | **max safe s** | binding |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `grasp_lift` | 0.291 | 0.665 | 2.72 | **1.72** (1.962) | 2.16 | **1.72** | **the vertical friction cone** |
| `place0` | 0.343 | 0.340 | **2.30** | 3.55 (4.273) | 3.15 | **2.30** | **joint velocity** |
| `place1` | 0.343 | 0.527 | **2.31** | 2.85 | 2.56 | **2.31** | **joint velocity** |
| `approach` | 0.150 (ach 0.109) | 0.800 | 5.27 | inf (no payload) | 1.95 | **~1.0 practical** | **the servo** (ach/cmd 0.73) |

**The binding limit on the loaded legs is the lift's friction cone at s = 1.72** - and it
is an *acceleration* budget, so it is reached by `a x s²`, not by speed. The place legs
carry 2.3x of joint-velocity margin. The descent is the honest exception: its cap is
already untracked (0.73) and its end is 9.3 mm short, so **no time-scale can make it
faster** - which is why the P44 census's "do not re-tune the approach budget" stands.

### 3.2 The policy's own stream, per joint

| object | max safe `s` at p99 | binding | max safe `s` at the worst single step | binding |
| --- | --- | --- | --- | --- |
| **emitted intra-chunk** | **3.34** | j4 | 1.14 | j4 (already 1.14x at s=1.0) |
| executed (first 3) | 2.35 | j3 | 1.15 | j4 |
| re-plan boundary | 0.67 | j4 | 0.61 | j4 |

**So for the policy the binding object is j4**, at 2.35 (executed, p99) / 3.34 (all 15,
p99); the *single worst* emitted step is already 1.14x the limit, and the *boundary* is
over it by construction. Exceedance counts on the emitted stream are the operative check:

| s | executed joint-steps over a limit | share |
| --- | --- | --- |
| **1.0** | **0 / 1512** | 0.0 % |
| **1.25** | **1 / 1512** | 0.07 % |
| **1.5** | **1 / 1512** | 0.07 % |
| 2.0 | 2 / 1512 | 0.13 % |

**Verdict: 1.25 and 1.5 sit inside the legal joint-velocity envelope of the emitted
stream** (one worst-case step, 0.07 %, crosses a limit; the smooth band has 2.3-3.3x of
margin). 2.0 starts to be a different regime and is not registered. The *practical*
bound is not the joint limit but whether the drive turns the extra ramp into achieved
speed - that is exactly what phase 2 measures.

### 3.3 The expected episode-level gain (the arithmetic phase 2 is gated on)

`arm motion x (1 - 1/s)`, from §1.4: at **s = 1.25, 1.6-1.7 s of a 14.7-15.0 s episode
(11-12 %)**; at **s = 1.5, 2.1-2.3 s (14-15 %)**. In ticks: 190-205 (s=1.25) / 255-275
(s=1.5) of the ~1800. **This is the pre-registered effect size, and it is an upper
bound** - it assumes the drive's achieved speed scales with the command, which the
re-plan discontinuity may prevent.

---

## 4. (D) The success levers, with their measured status

The current direct interface (`presentation=direct`, **the park is the shipped default
since P43**) splits cleanly. **The batch's scenario block runs
`FRUIT_POLICY_TRIGGER_ACQ=1`** (the P35/P36/P37/P43 `SCEN_ENV`, "arrival + lead 0.9 +
ACQ=1 + dynamic pick"), which is **not** the shipped default (R5 decision 4 keeps ACQ
off) - so everything below is an **ACQ=1** measurement and the shipped default has no
post-park direct measurement at all (§5, and PREREG S2):

| cell | n | placed | carried-not-placed | no-grasp |
| --- | --- | --- | --- | --- |
| **B right (park `back`)** | 56 | **53 = 94.6 %** | **0** | 3 = 5.4 % |
| B left (no park vector; unchanged) | 19 | 0 | 18 = 94.7 % | 1 = 5.3 % |
| A right (park `ready`) | 54 | 32 = 59.3 % | 20 = 37.0 % | 2 = 3.7 % |
| A left | 21 | 1 = 4.8 % | 20 = 95.2 % | 0 |

**The left's 4.8 % is not an open success lever**: 94.7-95.2 % of its failures are
carried-not-placed, i.e. the loaded slide that `logs/p42/SIM_LIMIT.md` closes (2.2x force,
every face, every squeeze depth, a centred seat), and `configs/arm_parks.json` has a
left-only vector so the park arm never moves it (the P43 built-in no-op). On the right,
the residual is 3 no-grasp in 56 - the acquisition class.

| lever | measured status | where |
| --- | --- | --- |
| **the park** (`FRUIT_ARM_PARK=back`) | **ADOPTED** (P43): right carried 20/54 -> 0/56 (Fisher 7.3e-8), right placed 32/54 -> 53/56 (+0.354, one-sided 95 % lower +0.228), run level 5/5, cycle +0.2 %; left is a no-op (1/21 -> 0/19). The mediator is the **image** channel (P36's 2x2: image 0/58 vs 35/57, p=8.8e-15; proprio p=0.687); *which* image statistic is unseparated | P43, P36 |
| **the checkpoint** | **no gain, five times**: `moe_v13p` +1/75 (p=1.0), `p33_pear` −8/45, `p37_park` −0.018 (with the park: 0.959 vs 0.977), `rl_awr1` −7/75, `moe_v13s` vs `moe_v12` mixed across interfaces | P33, P37, R9, W7-C, W8-A |
| **the correction layer** | **exists and is measured negative**: `policy/correction.py` (`CorrectionHead`, 9-D), `FRUIT_A2C2` opt-in, checkpoint `moe_v11_correction` `5d52d1b1` (18 DAgger episodes / 3147 frames, target mean `|delta|` 0.0505 rad) -> **21/45 = 46.7 % vs the base 30/45 = 66.7 %, −20.0 pt, FAIL** (N = 3x15) | WORKLOG path-3 |
| `FRUIT_POLICY_TRACK` | +2.2 pt (31/45 vs 30/45), FAIL; the paired outcome table is 0/0 discordant and the fire geometry is unchanged | path-3 |
| `FRUIT_POLICY_EVENT` | **the best measured arm**: 33/45 = 73.3 % vs 30/45 (+6.7 pt), every run delta >= 0, no new reason, strawberry +5 pt - but below its own pre-registered **+8 pt** bar, so not adopted, and never run at N=5 | path-3 |
| `FRUIT_VLASH` | −31.1 pt (16/45 vs 30/45) plus a new failure class | path-3 |
| **the trigger/handover** (`FRUIT_POLICY_TRIGGER_*`) | defaults lead **0.90 s**, lateral **0.16**, reach **0.20**, finger 0.040, frame `station`, encoder on, `PRESENT` off, **`ACQ` off**. ACQ's measured mechanism is the left's pre-contact class (left no-contact 9 -> 1, close-start median 88.8 -> 1.4 mm) with pooled 26/45 -> 31/45 = **+11 pt, p = 0.0898 at N=3**; R5 decision 4 keeps it a measurement interface - **and it is ON in every park-era batch (P35/P36/P37/P43), so the 94.6 % above is an ACQ=1 number** | W7-B, R5, `trigger.py:108-142` |
| **the catch-up / lead** | the **residual** row (`> 6 mm`) is 8/8 no-grasp vs 3.6 % below it (p=3.3e-11) and explains 42 % of the no-grasp class; but both registered levers (a longer lead, a longer catch-up) **catch 0/4** - the class is the delivered-x tail (|x| >= 0.390 is 6/6 failed) | P47, P48 |
| the lateral refusal / x-ceiling | 0.06 % of episodes; a binding ceiling refuses 0/40 selections | P38, P49 |
| the supply / density / release offset | flat cadence, class-standardised flat, negative on a single-species pool; the P50 compensation is opt-in and its count gate failed | P1c, P50 |

**The canary (the interface of record)**: `accept_policy.sh`, fixed pre-v9 supply, ten
episodes, floor 0.60. Recorded spread **5-8/10** (`moe_v11` 8, `moe_v12` 6, P2b 5 and 6,
P32 D0 5, P41 7). The P41 sample's three losses are **2 grip losses + 1 pick-station
escape** (`fruit left the pick station during the close (1416 mm)`, after a close that had
already drifted the apple 283 mm) - the escape is outside the recorded baseline reason set
(`logs/336_hybrid_v3all.log`), so that sample FAILs on its reason clause alone. **The
canary's policy window is `APPROACH_STEPS = 400` ticks (3.33 s) of a ~74 s/episode wall**,
so it is a placement/no-harm probe for a policy change, **not a speed probe** (`60_eval_policy.py:243-285`).

**What the P44/P46 speed work already established about the *scripted* line** (the demos'
source): the cells are real (−1.45 s/attempt on the union) and their count cost is the
**pre-contact acquisition** class (`sep@onset` 59-63 mm, the miss 219-481 mm) and, on the
two-line, the converged close - and P51's offline map shows the union + the P50
compensation **cannot** be class-clean (1 of 5 events is the tail, 4 are mid-band
converged closes). **So no speed lever on either interface has ever bought placements.**

---

## 5. What this census does **not** claim

* **No rate.** §1.4 and §4's counts are one attractor each (the P43 A/B pair is two
  branches; every other checkpoint sample is one draw). The per-decision and per-joint
  numbers are the measurements.
* **No claim that the emitted stream's 2.3-3.3x joint headroom becomes achieved speed.**
  The re-plan discontinuity is 3-5x the intra-chunk step and is untouched by a time-scale;
  §3.3's 11-12 % is an **upper bound** assuming the drive tracks the extra ramp.
* **No claim that a faster policy fixes anything on the success side.** The right arm is
  at 94.6 % (3 no-grasp of 56) and the left's residual is the **closed** grip class - the
  only open vector is acquisition timing, and P48 measured its lead/catch-up levers as
  0/4.
* **The 94.6 % is an ACQ=1 number.** Every park-era batch runs
  `FRUIT_POLICY_TRIGGER_ACQ=1`; the shipped default is ACQ off (`trigger.py:167`,
  R5-4), so the shipped direct configuration's post-park placement count is
  **unmeasured** - that gap is PREREG S2, and it is a default-consistency question, not
  a new mechanism.
* **B2 is offline on demo observations.** It samples the checkpoint on the training
  distribution with a seeded sampler (`FRUIT_POLICY_SEED=11`) and no closed loop, so it
  measures **what the model emits**, not what the arm achieves.
* **The one thing that would falsify the whole lane** is named: if the achieved joint
  motion does not scale with the command, the re-timing buys ~0 and the lane closes with
  that measurement (the P52 stop rule, `.slim/deepwork/p52-model-lane.md` §4).

---

## 6. Files and pins

| artefact | md5 |
| --- | --- |
| `logs/p52/model_census.py` | `fdd9d4b91077b8d742ea96d8769783dd` |
| `logs/p52/model_census_out.txt` | `3118f87195b174ec07718e3e1cc6134e` |
| `logs/p52/policy_chunks.npz` (B2's cached chunks) | `a852cdc6cb7ecf01724dd993d7f7eb45` |

Source pins used for the code sites: `rl_env.py` `0cefb13d`-era tree at HEAD `da0c914`
(P50/P51 left `src/` untouched), `policy/runtime.py` `379ac706`, `policy/trigger.py`
`b09d3cb2`, `policy/correction.py` (the A2C2 head), `control.py` `9384ff4f`,
`tasks.py` `b6de439c`, `configs/motion_reference.json` `8a399626`.
