# P145 - the honest interface: no handover, no trigger, no truth goal, no encoder

The owner's requirement, restated as a testable interface:

> approach, grasp and place from **vision and touch only**. The belt-speed encoder
> is auxiliary at most; the camera and the tactile must genuinely matter; no
> external trigger, no truth goal and no hand-over to the scripted primitive,
> because none of those exist in a real cell.

This phase builds that interface and measures the first two honest cells.

## 1. What "honest" means here, in switches

| channel | honest setting | what it removes |
|---|---|---|
| grasp handover | `FRUIT_POLICY_HANDOVER=0` | the scripted primitive never grabs; `_run_primitive` cannot fire |
| trigger | `FRUIT_POLICY_TRIGGER=off` (default) | no encoder/aim-based fire of any kind |
| goal | `FRUIT_GOAL_SOURCE=perception` | the goal is the **depth camera's** measurement, not `spawner.position` |
| belt prior | `FRUIT_TRACK_BELT_TAU` unset / 0 | the tracker measures the velocity; it is not told the belt speed |
| encoder | not read by the policy path | `FRUIT_OBS_GOAL_AUX` unset, no 26th channel |
| scoring | the payload's own rise and landing | `grasped`/`placed` are read from the fruit, not from `result` |

Two new switches are added, both default-inert:

* **`FRUIT_POLICY_HANDOVER=0`** - the policy's own 7 joints + finger do the cycle.
* **`FRUIT_GOAL_SOURCE=truth|perception`** - `truth` is the shipped behaviour,
  byte for byte; `perception` measures the fruit on the frame `_observe` already
  rendered (RGB-D + `instance_id_segmentation` -> trimmed sphere fit ->
  `tracking.FruitTracker`), and writes position, velocity and **diameter** into
  the goal every observation tick.

With the primitive off, `result.grasped` never exists, so the outcome is read
from the payload: `lifted` = the fruit rose more than **50 mm** above its belt
rest, and `placed` = it is on an output line at finalize. This is the same
physical definition the scripted ledgers use and it cannot be satisfied by the
primitive (there is none).

## 2. The no-handover baseline: the policy closes 69-172 mm short

`moe_v13s`, direct presentation, 4 episodes x 3 seeds, `FRUIT_POLICY_HANDOVER=0`,
the **truth** goal (the shipped interface minus the primitive). Seven episodes
completed before the cell was stopped to free the GPU for the DAgger collection:

| episode | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| `gap_min` [mm] | 149 | 69 | 105 | 138 | 69 | 140 | 138 |
| `gap_close` [mm] | 149 | 69 | 105 | 139 | 69 | 140 | 138 |
| lifted | no | no | no | no | no | no | no |

`gap_close` (the distance at the ticks the policy is **already closing**) equals
`gap_min` on every episode: the model does close, and it closes **7-15 cm** from
the fruit. That is the same 13 cm P143 measured through the handover gate - but
now there is no primitive to rescue it, so the cell is **0/7 with zero lifts**.

The mechanism is in the interface, not the sensor: the goal is the **selection-
time snapshot** of the fruit (`spawner.position` at reset), so the policy has no
per-tick information about where the fruit is now. It learned a **timed**
trajectory from the demonstrations (which share that static goal), and it fires
the close on that clock.

## 3. The perception goal: 1.9-9.5 mm, 12 % velocity error

The measurement, on the shipped head camera, 240x424, depth + instance mask +
trimmed sphere fit + constant-velocity tracker (no belt prior):

| episode | accepted frames | rejected | `err` p50 | `err` p90 | velocity estimate | fitted dia |
|---|---|---|---|---|---|---|
| 0 (pear 6.1 cm) | 189 | 134 | **9.5 mm** | 10.6 mm | (-0.005, **-0.135**, -0.008) m/s | 53.2 mm |
| 1 (tomato 5.3 cm) | 167 | 152 | **1.9 mm** | 3.1 mm | (+0.004, **-0.124**, +0.002) m/s | 47.6 mm |

* the **position** error is 1.9-9.5 mm p50 against the 69-149 mm the policy's own
  close needs to fix: **the camera is not the bottleneck**;
* the **velocity** comes out at 0.124-0.135 m/s against the belt's 0.120 (3-12 %
  high) with no encoder read, and the tracker is fed a depth-source `sigma_z`
  of 5 mm (`tracking.track_config_from_env(..., "depth")`);
* the **diameter** is 4-13 % small (a sphere fitted to a non-sphere), which is
  the known `_fit_sphere` bias, not a calibration fault;
* 47-59 % of frames are refused (occlusion, border clip, < 60 px) and the filter
  **predicts through them** - the P135 contract (`None` never returns a cached
  sample).

With this goal the policy still closes at **172 mm** and does not lift: the
measurement is good and the policy does not use it, because it was trained on a
static goal. **Training on the moving goal is the next cell.**

## 4. The training interface: DAgger labels on the policy's own states

The expert is the **scripted pick controller** (`rl_env._expert_action`, the
`--dagger` path that already exists): hold the calibrated grasp pose while the
fruit is outside the tracking window, then track its centre with position-only IK
and run the 60-tick close ramp. It is a **teacher**, not a controller:

* `FRUIT_DAGGER_NO_TAKEOVER=1` (new) - the expert **never** takes the arm. The
  shipped `--expert-tolerance 99` still let the early-close term hand over for
  one tick at exactly the close (`interventions=88/322`); with this switch the
  arm is 100 % the policy's and only the labels are recorded
  (`interventions=0/322`, `expert_ticks=0/1290`).
* every frame carries `dagger_valid` (new): the expert's command is the
  behaviour to clone only up to the end of the 60-tick close ramp. After it the
  expert holds an already-grasped fruit, which is not the carry the demos teach,
  so those frames are dropped by the window loader (`policy/data.py`), not
  trained on.

The goal mismatch between the anchor and the new store is handled **without a
recollection**: `FRUIT_TRAIN_GOAL=moving` rebuilds every store's goal from its
own per-frame `fruit_position` trace (position + 30 Hz finite-difference velocity
+ the stored diameter/bin) unless the store was recorded with
`goal_source=perception`, in which case the measured goal is kept. The
demonstrations' snapshot goal is a timer; the rebuilt one is the fruit's current
state, which is the same channel the deployed policy sees.

Store: `datasets/p145_dagger`, 30 episodes (10 x seeds 77/101/202), direct
presentation, `FRUIT_POLICY_HANDOVER=0 FRUIT_GOAL_SOURCE=perception
FRUIT_DAGGER_NO_TAKEOVER=1`, ~110 valid frames per episode.

## 5. Reproduce

```bash
# honest baseline (no primitive, truth goal)
FRUIT_POLICY_HANDOVER=0 FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 \
  scripts/run.sh scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
  --presentation direct --episodes 4 --seeds 77,101,202 --out logs/p145_base

# measured goal (depth + mask + tracker, no encoder)
FRUIT_GOAL_SOURCE=perception FRUIT_PERCEPTION_DIAG=1 FRUIT_POLICY_HANDOVER=0 \
FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 \
  scripts/run.sh scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
  --presentation direct --episodes 4 --seeds 77,101,202 --out logs/p145_percept

# DAgger collection (labels only)
FRUIT_GOAL_SOURCE=perception FRUIT_POLICY_HANDOVER=0 FRUIT_DAGGER_NO_TAKEOVER=1 \
FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 \
  scripts/run.sh scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
  --presentation direct --episodes 10 --seeds 77,101,202 \
  --dagger --expert-tolerance 99 --expert-window 0 --record --out datasets/p145_dagger
```

## 6. The DAgger store, as collected

`datasets/p145_dagger`: **30 episodes** (10 x seeds 77/101/202), 9,791 frames,
**0/30 lifts**, `interventions=0`, `expert_ticks=0` on every episode (the arm is
100 % the policy's; only the labels are the expert's). With
`FRUIT_DAGGER_FOCUS=20` the 9,791 frames reduce to **600 training windows**, of
which **263 contain the close ramp** - the store is the correction, not a replay
of the wait.

Why the focus: a pick episode is ~100 frames of "hold the grasp pose" plus a
15-frame close ramp. The hold is already in the anchor (and the policy starts
there); the ramp is the only thing the policy cannot do.

## 7. The fine-tuning matrix, and what each arm measured

All arms start from `moe_v13s` (`61da390a`); the metric in the "close fidelity"
column is the offline **joint error on the DAgger close windows**
(`logs/p145/close_fidelity.py`, 60 windows, DDIM-16, fixed seeds).

| arm | data / base | close weight | epochs | close joint err (1st step) | closed loop |
|---|---|---|---|---|---|
| A | DAgger + demos_v11 | 1 | 8 | - | `gap_min` 5-70 mm but `gap_close` **124-398 mm**: tracks, closes late |
| B | A + close weight | 10 | 12 | 0.276 rad | `gap_min` 1-43 mm, `gap_close == gap_min` (timing fixed); **jaw 9 cm above the fruit**; 0 lifts |
| C | DAgger + base **carry-only** | 10 | 10 | 0.190 rad | tracking worse (jaw drifts to y=-0.10), finger oscillates |
| D | first-N mask (wrong axis) | 10 | 10 | 0.736 rad | discarded (the mask hit the action dimension, not the horizon) |
| E | DAgger only | 10 | 10 | 0.324 rad | underfit (600 windows, 190 steps) |
| **F** | **DAgger only** | **10** | **200** | **0.068 rad** | **offline fits the ramp** (chunk min 0.0277 vs label 0.0276, 54/60 close); closed loop still 0 lifts |

**Two things are now separated, and they are different problems.**

1. **The tracking and the close timing convert.** A/B move the closest xy gap from
   the baseline's **69-149 mm** to **1-43 mm**, and `gap_close` becomes equal to
   `gap_min` on 4 of 5 episodes - the policy closes *at* the closest approach, not
   13 cm late. The measured goal is what it follows: `goal_y` equals the truth
   `fruit_y` to 1-2 mm on every traced tick (sections 3 and the `[policy-trace]`
   rows).
2. **The grasp does not**, and the mechanism is **action precision**, not the
   sensor. The best offline fit is **0.068 rad** (arm F) against the base's
   **0.084 rad**; 0.07 rad is ~3-5 cm at the TCP, and the catch needs ~2 cm. The
   closed loop shows it directly: the jaw holds **x = 0.28** (the station line)
   while the fruit is at **x = 0.20-0.36**, and the jaw **z = 1.29** while the
   fruit's centre is **1.20** (the pads' distal plane 1.21). The pads close
   **2-12 cm** from the fruit - air.

A third term is execution, not learning: with the shipped `execute_steps=4` the
chunk's early ramp values are re-sampled before the finger advances
(`finger_min` 0.034-0.040, the ramp never completes). Applying the whole chunk
(`--execute-steps 16`) closes the finger (0.013-0.019) at the closest approach,
but the hand is still 22-116 mm from the fruit, because the chunk's arm plan was
computed from a different state. **A chunked policy trained on per-state feedback
labels has to be executed as feedback (one step at a time), and the current
chunks are 16 steps long** - the named representation problem.

## 8. What the interface now is, against the owner's requirement

| requirement | state |
|---|---|
| no external trigger | `FRUIT_POLICY_TRIGGER=off`; `should_fire` is never called |
| no handover to the scripted primitive | `FRUIT_POLICY_HANDOVER=0`; the primitive never runs |
| no truth goal | `FRUIT_GOAL_SOURCE=perception`; position/velocity/diameter measured (1.9-9.5 mm) |
| no belt encoder | the tracker is not given a belt prior; velocity converges to 0.124-0.135 m/s from the camera |
| camera genuinely matters | the goal **is** the camera's measurement; the policy tracks it (goal = truth to 1-2 mm) |
| touch matters | the tactile is in the observation; the ablation knobs exist (`FRUIT_TACTILE_ZERO=1`, `FRUIT_IMAGE_FREEZE=1`) and are the next cell |
| approach + grasp + place by the policy | **approach yes** (gap 1-43 mm), **grasp no** (precision), **place not reached** |

## 9. The next lever, priced

The sensor, the trigger and the goal are no longer the limiting terms. The
limiting term is the policy's **action precision on the corrective phase**:

1. **A larger DAgger store** (>= 150 episodes, ~2 h at 1 min/episode) with the same
   recipe. The endpoint is the offline joint error on the close windows
   (`logs/p145/close_fidelity.py`): the target is **< 0.03 rad**, which is ~1-2 cm
   at the TCP. This is the cheapest next spend and it attacks the measured term.
2. **A feedback-shaped action representation** (one executed step per decision, or
   a cartesian delta), which is a training-schema change and its own phase.
3. **A tactile close refinement** (the pad force says a grasp is empty; re-open and
   re-approach) - a policy-level reflex, named and not built.

No shipped default changed, no reference re-recorded: the acceptance is
**7/10, `fingerprint: matches`, `190: PASS`**, and its **459 `[fruit]` lines are
459/459 byte-identical** to `logs/p136/accept_final.log`; `selfcheck.sh` PASS
(0 failures, 1 skipped); `106` OK.

## 10. Reproduce the training cells

```bash
# the store
FRUIT_GOAL_SOURCE=perception FRUIT_POLICY_HANDOVER=0 FRUIT_DAGGER_NO_TAKEOVER=1 \
FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 \
  scripts/run.sh scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
  --presentation direct --episodes 10 --seeds 77,101,202 \
  --dagger --expert-tolerance 99 --expert-window 0 --record --out datasets/p145_dagger
python3 logs/p145/merge_shards.py datasets/p145_dagger datasets/p145_dagger_all

# the arms (A is base 1.0/no close weight; B adds --close-weight; F is DAgger-only 200 epochs)
FRUIT_TRAIN_GOAL=moving FRUIT_DAGGER_FOCUS=20 \
  /home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python scripts/111_rl_finetune.py \
  --ckpt checkpoints/moe_v13s/policy_best.pt --rollouts datasets/p145_dagger_all \
  --base "" --close-weight 10 --close-lead 12 --close-tail 15 \
  --out checkpoints/p145_dagger_f --epochs 200 --lr 5e-5 --weight-mode ones \
  --batch-size 32 --seed 0

# the offline precision endpoint
FRUIT_DAGGER_FOCUS=20 P145_WINDOWS=60 \
  /home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python logs/p145/close_fidelity.py \
  checkpoints/p145_dagger_f/policy_best.pt datasets/p145_dagger_all
```

## 11. P145b - scaling the store found two interface defects that dominate the data volume

The planned >=150-episode DAgger store was started three ways; the useful result
is that the **interface**, not the data count, was the binding term. The
collection itself is fine: 8/8 episodes in 5 min with `--horizon 520`, while the
760-tick episode wedges in the post-close phase (2/8, CPU busy, GPU 2 %), so the
chunked runner (`logs/p145/collect_chunks2.sh`, 16 episodes per timeout-guarded
chunk) is the supported shape.

### 11.1 Defect (a): the direct episode started at the **close** pose

`configs/waypoints.json`'s `grasp` is the scripted line's *close* pose. The
demonstrations' frame 0 is a different pose - the wait/pre-pose - measured from
`demos_v11/episode_00000.npz` (left) and `episode_00001.npz` (right):

| arm | demo frame-0 action (`wait`) | config `grasp` | difference |
|---|---|---|---|
| left | `[-1.390,-0.143,1.536,1.168,-1.379,-0.542,1.506]` | `[-1.270,-0.062,1.571,0.928,-1.185,-0.667,1.324]` | 0.35 rad |
| right | `[1.406,0.122,-1.540,1.104,1.392,0.586,-1.503]` | `[1.235,0.082,-1.566,0.969,1.163,0.640,-1.325]` | 0.33 rad |

So the policy's first observation was a state the demonstrations only reach at
the close, with the fruit 0.4 m upstream - and the DAgger expert's wait label was
that same close pose. **The demos and the DAgger store taught two different wait
poses**, which is the "stay vs descend" average the earlier arms measured.

Fix: the two `wait` poses are added to `configs/waypoints.json` (+18 lines, no
existing value moved; P64's config pin re-pinned to `6d2843a3`), and
**`FRUIT_DIRECT_START=wait`** starts the direct episode there (default `grasp`,
byte-inert; a bad value raises). The DAgger expert's wait label follows the same
pose.

### 11.2 Defect (b): a 30 Hz demonstration stream played at 120 Hz

The demonstrations are recorded at **30 Hz** (one waypoint per 4 control ticks).
`act` executes one chunk waypoint per control tick, so the 16-waypoint chunk is
replayed at **120 Hz** - a 4x compression of the trajectory the model was trained
on (the P53 census already read this mismatch as a 10x command dither and a
19.3 mm same-tick residual; its C2 cell took the first half-step, `hold=2`).

**`FRUIT_POLICY_ACTION_HOLD=4`** holds each waypoint for 4 ticks - the exact
training cadence (a decision covers `execute_steps * hold` ticks).

### 11.3 With both fixed: the xy tracking converts, the catch-up does not

A horizon-4 fine-tune on `demos_v11` alone (`FRUIT_TRAIN_GOAL=moving`,
`--close-weight 10`, 40 epochs, loss **0.0145**, checkpoint
`checkpoints/p145_demo_h4`, md5 `bcff04e6`), evaluated at the wait start with
`--execute-steps 4 FRUIT_POLICY_ACTION_HOLD=4`:

| cell | gap_min | gap_close | lift |
|---|---|---|---|
| 2-episode probe, episode 0 (pear, left) | **9 mm** | **9 mm** | no |
| 12 episodes (seeds 77/101/202) | **32-41 mm** left, **64-94 mm** right | = gap_min | **0/12** |

The trace says what remains: the jaw tracks the fruit in x/y to 9-41 mm, then
**stops at the config's grasp waypoint (z = 1.29)** and never makes the last
**8-9 cm** to the fruit's centre (z = 1.20); it also closes early (fruit
`y ≈ +0.055` against the demonstrations' `+0.003`), lifts, and lifts nothing.

The offline instrument puts the fit at the same floor as every earlier arm: on
the demonstrations' close windows the horizon-4 model reads **0.065 rad** joint
error at the first step and **0.059 rad** at the last (finger 0.0008), i.e.
**~3 cm at the TCP**. The missing catch-up is 8-9 cm (0.1-0.15 rad). The fit
floor is unchanged between the 10k-window demonstrations (0.065) and the
600-window DAgger arm at 200 epochs (0.068) - a **representation** limit, not a
data-count limit.

### 11.4 Verdict and the named next step

The sensors and the honest interface are solved: the goal is the depth camera's
measurement (1.9-9.5 mm), no handover/trigger/encoder, and the policy's own arm
now tracks the fruit to **9-41 mm** in the grasp plane. The remaining two terms
are **phase timing** (it closes ~0.4 s early and descends during the wait) and
the **final approach's precision** (3 cm fit floor against a 2 cm catch), and
they are coupled: the policy averages the "hold" and "dive" modes.

**The next step is therefore a phase-gated policy or a cartesian-delta action**,
not another collection of the same shape:

* the model already has a 5-skill router (`label_episode`); pin its phase at the
  demonstration's own boundary and let each phase own its chunk, or
* predict a **cartesian delta** and solve the IK exactly, so the 3 cm behaviour-
  cloning error does not sit on top of a 0.1 rad joint average, and
* the tactile channel is live but not yet ablated: `FRUIT_TACTILE_ZERO=1` and
  `FRUIT_IMAGE_FREEZE=1` are built for the cell that decides whether touch is
  load-bearing.

No shipped default moved. `selfcheck.sh` PASS (0 failures, 1 skipped) after the
P64 config re-pin; the references are `61fb5202` / `61fb5202` / `18b101bf`.

## 12. P145c - the phase gate, the perfect goal, and the close-only model: the residual is the policy's fit

Three separating measurements, all on `p145_demo_h4` + `FRUIT_DIRECT_START=wait` +
`FRUIT_POLICY_ACTION_HOLD=4`, and one literature review (DynamicVLA, arXiv:2601.22153).

### 12.1 The router is not the site: the mean is in the shared backbone

`FRUIT_POLICY_PHASE=dy` forces the phase from the perceived fruit's along-distance
and the jaw (the demos close at `|dy| <= 0.05`), instead of the learned router. The
`[route]` row shows `approach` all the way to `goal_y = -0.065`, and the finger
**still closes to 0.000**. The MoE experts are *residual adapters* on a shared
denoiser (`policy/model.py`), so hard-routing the phase changes the residual, not
the base action: the "hold vs dive" mean lives in the backbone. **The phase-gate
lane is closed by this measurement.**

### 12.2 A perfect goal does not fix it: the perception is not the residual

`FRUIT_GOAL_SOURCE=truth_moving` (bench only: the goal rebuilt every tick from the
simulator's own fruit state - the exact training distribution, zero measurement
error) reads **0/2, gap 16-47 mm, finger 0.0-0.024**, i.e. the same failure as the
perception goal (0/12, 32-94 mm). **The 1.9-9.5 mm sensor is not the limiting term
by a factor of two.**

### 12.3 A close-only model does not fit the close better: not the phase mixture

The close-start windows (`[close-5, close+10]`, 16 per episode, 800 total) are the
task. A model trained on **only** those windows for 100 epochs fits its own
training set to **0.0362 rad** first step, against the phase-mixed model's
**0.0406** on the same instrument. Removing the wait phase from the loss does not
move the fit. The close-start joint error is therefore **~2 cm at the TCP** in
every model measured, and the catch needs ~2 cm - the closed loop then compounds
it (16-47 mm).

### 12.4 The ambiguity filter is not evaluable here

The "Curse of Precision" lever (unambiguous demonstrations lower the limit
precision) needs re-open/re-seat ambiguity in the close. Measured on `demos_v11`:
**0 of 50 episodes** re-open the finger after the close (the store is
successes-only; failed probes were discarded). The lever has nothing to filter.

### 12.5 DynamicVLA (arXiv:2601.22153) - the mechanism is two orders too small here

The paper's LAAS discards the stale prefix of an action chunk; its own ablation is
30.27 -> 36.11 (LAAS) -> 39.72 (continuous inference) -> 47.06 (both) on a
25 Hz / 0.226 s-latency cell, where the object moves 34-170 mm during inference.
This cell's inference is 26 ms and the fruit moves **3.2 mm**; the misalignment to
fix is **0.4 s (48 mm) of *phase*, 15x the inference latency**. The same family is
already in the tree and measured negative: RTC -20 pt, VLASH -31 pt, A2C2 -20 pt.
**Not implemented; the transferable principle (re-index to execution time) is
already what `FruitTracker` does for the object.**

### 12.6 What is left

The fit floor (~0.036 rad) is invariant to phase, goal and (measured) data count.
The remaining hypotheses, in order:

1. **Optimization/capacity**: a 500-epoch run on the same 800 close windows
   (`checkpoints/p145_close500`) decides whether 0.036 is underfitting or the
   mapping's own noise.
2. **Action representation**: the 0.036 rad is a *joint* metric on a redundant
   7-DoF arm; a cartesian-delta head with the exact IK is the task-space test
   (the pre-check is an FK->IK->FK round trip < 1 mm on 20 demo poses).
3. **A final-approach servo** (learned or the scripted IK) is the only remaining
   mechanism if both above fail; it is the "combine joint + Cartesian" result
   (Implicit Kinematic Policies, arXiv:2203.01983) applied to the last 2 cm.

No shipped default moved; all P145c knobs are default-off (`FRUIT_POLICY_PHASE`,
`FRUIT_PERCEPTION_COAST_S`, `FRUIT_GOAL_SOURCE=truth_moving` is bench-only,
`FRUIT_CLOSE_ONLY`). References `61fb5202` / `61fb5202` / `18b101bf`.

### 12.7 A direct MLP on the close windows: fittable, but not with 800 samples

A 33-D input (`[fruit xyz, vel, diameter, bin, 22 joints, finger, tactile]`) and a
7-joint target, trained on the close windows (640 train / 160 held out, random
split, 3000 epochs): **train |err| median 0.015 rad**, but **held-out 2.9 rad**.
The MLP memorises 640 windows and does not generalise across them - 800 close
windows is too few for a 20k-parameter regressor, and the same small-sample
regime is what the diffusion model's 0.036 on its own training windows reflects.
This experiment is **inconclusive about the mapping's noise floor** and is
recorded as such; it is not evidence for a deterministic close head at this data
size. The remaining honest option on this lane is **more close-phase data**
(the scripted collector is wedge-free at ~45 episodes/35 min; ~300 episodes would
give ~4,800 close windows), or the cartesian-delta representation with the
FK->IK pre-check.

**Stopped**: `checkpoints/p145_close500` (500 epochs) was cancelled when the
100-epoch close-only run had already plateaued (0.0362 rad); its log is
`logs/p145_close500.log` (epoch 58, loss 0.0177).

### 12.8 Pooled close data (140 single-arm episodes) does not rescue the direct regressor

Pooling the close windows of `demos_v11` + `p144_up` + `p144_down` (140 episodes,
2,236 windows, episode-level 80/20 split, 64x64 MLP, weight decay 1e-3, early
stopping): **train |err| median 0.335 rad, held-out 2.44 rad**. The fit is worse
than the 50-episode run's 0.015 (which was itself an overfit), so the pooled
stores are **not** interchangeable for this feature set - the three collections
differ in the goal's semantics (p144's goal is the static snapshot) and the
policies' reference frames, and this experiment is **inconclusive about the
mapping's noise floor**. Recorded, not built on. The clean version would need one
collection, one schema (the moving goal) and a held-out **arm-balanced** split.

### 12.9 The cartesian precondition passes (5.1 mm systematic, 0.2 mm repeatability)

`logs/p145/ik_precheck.py`: 20 real (close-start pose, fruit close position) pairs
from `demos_v11`, the arm teleported to the demo's start, the **same
position-only `ik_step` the scripted close uses** run for 120 ticks to
`fruit + [0, 0, 0.080]`:

| metric | value |
|---|---|
| achieved jaw vs commanded point | **median 5.1 mm, p90 5.2, max 5.2** |
| spread across the 20 pairs | **0.2 mm** |
| `<= 20 mm` (the catch tolerance band) | **20/20** |
| `<= 2 mm` | 0/20 |

The 5.1 mm is **systematic**, not a tracking error: the effective pad standoff is
~75 mm, not the 80 mm the probe commanded, and every pair lands on the same
offset. The IK's *repeatability* is 0.2 mm, and its absolute placement is 5 mm -
inside the 6 mm catch tolerance. **A cartesian action head is viable**: the
servo, not the representation, is the part that already works.

The build it licenses (its own phase): (i) one simulator pass to convert the
demos' joint commands to TCP targets (`jaw_centre` at the commanded joints, or
the arm's own FK), (ii) a new `action_dim` (3-D absolute TCP + finger, held
attitude) and a from-scratch training on the demonstrations (the 9-D checkpoint's
input layer does not fit), (iii) the env applies the TCP target with `ik_step`
at the decision rate, (iv) the same 12-episode honest cell. Expected mechanism:
the 0.04 rad joint average becomes a 5 mm task-space servo.

## 13. P145d: the cartesian head, as labelled by the achieved pose, is a negative

The pre-check (section 12.9) licensed the representation: the IK servo reaches the
demonstrations' close targets to 5.1 mm systematic with 0.2 mm spread. The build:

* `tasks._record` now writes `tcp` and `jaw` per frame (collector only);
  `datasets/p145_tcp`, **50 single-arm episodes**, `success=True`;
* `FRUIT_ACTION=jaw` makes the store's action `[jaw xyz, finger]` of the **next
  30 Hz sample** (`policy/data.py`), 9,423 windows at horizon 4;
* a 4-D seed from `moe_v13s` (`logs/p145/make_cart_seed.py`): 119 of 122 tensors
  copied, only `action_in` and the 4-D output head fresh, the normalizer's action
  statistics from the TCP store;
* training: 40 epochs, loss 0.0203, `checkpoints/p145_cart`;
* the env applies the 4-D action with `ik_step(tcp_target_for_jaw(jaw))` + the
  finger, the episode's captured attitude held (`rl_env._apply`, `FRUIT_ACTION=jaw`,
  default off).

Closed loop (2 episodes, wait start, perception goal, no handover, hold 4):

| policy | `gap_min` | jaw z at the close | lift |
|---|---|---|---|
| joint 9-D (`p145_demo_h4`) | 9-47 mm | 1.25-1.29 | 0 |
| **cartesian 4-D (`p145_cart`)** | **70-128 mm** | **1.36-1.41 (rising)** | **0** |

The trace shows the jaw **rising** during the approach while the fruit descends
to the belt: the policy is not tracking. **The label is the achieved pose, not
the expert's command** - the recorded `jaw` is the servo's response (a one-sample
lag), so a policy trained to predict it learns to reproduce the *response*, and
the IK then chases that, one step behind. The 5.1 mm servo was never the problem;
the **target** is.

**The next iteration must record the commanded TCP**, not the achieved one: the
scripted close's aim (`tasks._run_impl`'s `_dynamic_grip_target` / the DAgger
expert's `fruit + [0,0,pad_lift]`) evaluated through the arm's forward
kinematics, or a collector that records the IK target it just issued. Until then
the cartesian lane is **not a lever** - the joint policy's 9-47 mm remains the
best closed-loop result on the honest interface.

No shipped default moved: `FRUIT_ACTION` is default-off, the loader's jaw mode is
default-off, and the 9-D guard keeps a 4-D checkpoint from being run on the
shipped path. `selfcheck.sh` PASS (0 failures, 1 skipped) after the changes.

## 14. P145d.1 - the enforced command, two implementation defects, and the fresh head

The review agents (oracle/explorer) read the P145d path and found two defects that
the "achieved pose" diagnosis had hidden:

1. **The tool offset was applied twice.** `cmd_tcp` is a **TCP** command, and the
   env applied it through `tcp_target_for_jaw()`, which adds the ~78 mm lever
   offset - so the arm was commanded 7.8 cm high. `FRUIT_ACTION=tcp` now calls
   `ik_step(target)` directly; `FRUIT_ACTION=jaw` keeps the old path.
2. **The IK integrator was reset every deploy tick.** The scripted close carries
   `_q_cmd` across ticks (an incremental servo); the env called
   `sync_command_to_measured()` every tick. The integrator is now seeded once at
   the episode start and carried, matching the demonstrations.

The collector now records the **enforced command** (`cmd_tcp` = the exact
`ik_step` argument, `cmd_fresh`); the loader and the 4-D seed prefer it when the
IK ran and fall back to the achieved `tcp` during the static wait hold.
`dataset/p145_tcp2`, 50 episodes, 140/189 fresh frames (the IK is live through
the close/carry, not during the hold).

**The first TCP cell is still negative, and the cause is now visible at frame 0.**
With the 40-epoch model (`p145_cart2`, loss 0.0239) the first trace row has the
jaw at z 1.315 (a TCP of 1.393) while the demonstrations' wait TCP is **1.241**:
the policy starts **15 cm high**, then drifts up. The 4-D seed's action head is
**freshly initialised** (only `action_in` and `head.2` are new; 119/122 tensors
warm-start), and 40 epochs on 9,423 windows is not enough for it to learn the new
action space - the model outputs near the action mean (1.364) instead of the
conditional wait target. Gap 98-131 mm.

**The cell that decides it**: the same seed and data, 100 epochs at lr 1e-4
(`checkpoints/p145_cart3`, running). The endpoint is the **first-frame action**
(the wait-state TCP against 1.241) before any closed-loop claim; if it converges,
the closed-loop cell follows. This is the librarian's R1/R3 (label the enforced
command; decompose policy error from the 5 mm servo), not a new mechanism.

The wait-phase label remains the achieved `tcp` (a static hold); the oracle flags
that as a label-definition switch, and the clean form is the FK of the hold's
joint targets. That is a collector/kinematics change of its own and is deferred
until the first-frame check says the head can fit the space at all.

## 15. The 100-epoch cartesian head fits the wait state (4.3 mm) and still drifts in the loop

`checkpoints/p145_cart3` (100 epochs, lr 1e-4, loss 0.0158) on the enforced-command
store, scored offline on the **first observation of every demonstration**
(`logs/p145/first_frame.py`, 50 episodes):

| metric | value |
|---|---|
| recorded TCP mean | (0.270, -0.002, 1.236) |
| predicted TCP mean | (0.270, -0.005, 1.238) |
| per-axis median | x -0.1 mm, y -2.2 mm, z **+1.6 mm** |
| `|xyz|` | **median 4.3 mm, p90 8.3, 50/50 <= 20 mm** |
| finger | 0.0440 recorded / 0.0441 predicted |

So the 40-epoch failure was **training length, not the representation**: the fresh
4-D head needed ~100 epochs to fit the new space. The closed loop is still a
negative, and the trace says where: the first frame is correct (jaw z 1.315), then
the policy drifts to the **ready/high pose** (jaw z 1.48-1.78, `gap` 89-201 mm)
while the fruit passes. The `dy` phase gate does not change it (gap 93-201 mm,
jaw 1.48-1.49): the drift is in the shared backbone again, not the router.

**The common failure across joint and cartesian clones is now singular**: the
policy fits the demonstration states (joint: 0.036-0.041 rad; cartesian: 4.3 mm at
frame 0) and, once its own output moves it off that narrow manifold, it commits to
another mode (the ready pose / the close), and the phase gate cannot bring it back.

**The standard fix for exactly this is DAgger on the interface's own drift
states** - and the daemon store collected in P145 was at the *old* grasp start
with `ACTION_HOLD=1`, i.e. not the interface that drifts. The next cell is the
aligned one: the `p145_demo_h4` policy (wait start + hold 4) as the driver, the
scripted expert's labels only (`FRUIT_DAGGER_NO_TAKEOVER=1`), the moving goal, and
a fine-tune of the same h4 checkpoint. It is the cheapest remaining mechanism and
it targets the measured drift directly.

## 16. The aligned wait-start DAgger solves the close geometry (gap 1-2 mm); the lift is the remaining term

The P145 DAgger store had been collected at the **old** grasp start with
`ACTION_HOLD=1`, i.e. not on the interface that drifts. This cell is the aligned
one: the `p145_demo_h4` policy (wait start + `ACTION_HOLD=4`) as the driver, the
scripted expert's labels only (`FRUIT_DAGGER_NO_TAKEOVER=1`:
`interventions=0/130`, `expert_ticks=0/520`), the perception goal, 40 episodes
(seeds 77/101, horizon 520), then a fine-tune of the same h4 checkpoint with the
**whole valid wait + close** (not the 20-frame focus: the early drift is the state
to correct) plus `demos_v11` at weight 1.0, 14,348 windows, 40 epochs, loss
0.0185 (`checkpoints/p145_wait_dagger`).

Closed loop, 2 episodes (wait start, perception, no handover, hold 4):

| episode | `gap_min` | `gap_close` | jaw z at the close | finger | lift |
|---|---|---|---|---|---|
| 0 (pear 6.1 cm) | 75 mm | - | 1.30 -> 1.26 | 0.037-0.044 | no |
| **1 (kiwi 6.4 cm)** | **1 mm** | **2 mm** | **1.251-1.258** | **0.025-0.030** | **no** |

Episode 1 is the **best closed-loop grasp geometry this project has measured**:
the jaw is on the fruit to **1-2 mm** in x/y, at the seat height (jaw 1.25 with the
pads' distal plane 1.17, straddling the fruit's 1.20 centre), and the finger
command 0.025-0.030 is the demonstrated grip gap for a 6.4 cm kiwi. The joint
clone's best was 9-47 mm; the cartesian best 89-175. **The geometry lane is
solved.**

What does **not** happen is the lift: the jaw stays at 1.25-1.26 and the fruit at
z 1.20 for the rest of the episode; the finger oscillates 0.025 -> 0.040 -> 0.030
across chunks instead of settling at the ramp's end. The next cell is the
**close-to-lift transition**: the demonstrations' ramp ends at 0.027 and the
`grasp_lift` follows; the model re-opens. The route diag and a lift-phase cell are
the instruments, and the same wait-start DAgger store already contains the labels
(the expert's close ends at the ramp and the base demos carry the lift at weight
1.0).

No shipped default moved; the DAgger cell is env-only.

## 17. The commanded-finger labels restore the grasp class; the close/lift transition is still the term

The oracle's census found the label defect behind the re-open: the **measured**
finger at the loaded close sits **+6.0 mm** above the command (p50: command
0.0269, measured 0.0304-0.0328), and `label_episode`'s 0.030 threshold labels the
whole loaded close `approach` - **24/50 demos_v11 episodes have zero `grasp`
frames**. The approach expert therefore contains the close, and the 4/16-waypoint
re-plan re-establishes the ramp from an aliased, lagged state (the measured value
means "free ramp" or "loaded squeeze" depending only on the fruit's width).

**Fix**: label the skill on the **commanded** finger (the action's channel). The
class is restored (demos_v11: **grasp 0 -> 1581 frames**, approach 3455, lift 3000,
place 2192) and the horizon-16 retrain fits better (loss 0.0119 -> 0.0093 at
epoch 20, weighted 0.0129 final).

**The first closed-loop cell after the fix is a draw, not a conversion** (2
episodes, wait start, perception, hold 4, execute 16): pear gap 56 mm, kiwi gap
**33 mm**, both no lift and no re-open seen at the sampled ticks. The previous h16
cell (same data, old labels) reached **1 mm** on the same kiwi and then re-opened
at the re-plan. The two cells differ by the class labels alone; at n=2 this is a
branch, not a verdict, and the honest reading is that **the label fix is correct
by construction (the measured finger cannot separate free ramp from loaded
squeeze) and its closed-loop effect needs a larger cell**.

**A second early-episode term surfaced**: the kiwi's first perception measurement
arrived **~1.5 s late** (frames 107, rejected 43; the small fruit at the camera's
far range is under `FRUIT_PERCEPTION_MIN_PX`), so the goal stayed at the nominal
`pick_y + 0.45` until the fruit was close. The wait phase tolerates it, but the
nominal is 3.6 cm off the kiwi's actual selection y, and the tracking starts late.

**Where this leaves the honest interface**: the close geometry is solved (1-2 mm,
the seat, the grip gap); the **close/lift transition** - the finger's 0.025 ->
0.040 re-open and the missing lift - is the one unconverted term, and it is now
attributable to the phase/label aliasing and the open-loop ramp, not to the
sensor, the goal, the action space or the data count.

## 18. P145d.5: the closed-loop terms are now geometry, timing and actuation - and only the last two are open

The command channel (P145d.4) and the committed close ramp (P145d.5) were added:

* **`FRUIT_OBS_CMD=1`**: one proprio column = the commanded finger (the previous
  action; the demos' action stream at training, `_last_finger` at deployment).
  The 3-seed cell (12 episodes, 3 parallel sims, 5 min): gaps **1-75 mm**, **8/12
  <= 18 mm**, best 1-3 mm - the geometry is stable. **0 lifts.**
* **`FRUIT_CLOSE_RAMP=1`** (default off): when the policy's own finger command
  crosses 0.035, execute the demonstrations' **60-tick min-jerk ramp** to the grip
  gap and hold it; the arm/approach/lift stay the policy's. The finger now holds
  0.025 (no 0.023<->0.043 oscillation) in the pear cell - the actuation is fixed.

**What the two ramp cells expose is the timing, not the actuation**: the pear
(gap 68-69 mm) is the aim tail, and the apple episode has `gap_min = 17 mm` but
**`gap_close = 139 mm`** - the hand was 17 mm from the fruit at its closest, and
the policy's finger only crossed the close threshold **139 mm** away, i.e. after
the fruit had gone. The ramp latches on the policy's closing command, so it
actuates at the wrong moment.

So the three closed-loop terms are now separable and measured:

| term | state |
|---|---|
| geometry (approach aim) | solved on most draws (1-3 mm; 8/12 <= 18 mm) |
| actuation (the close ramp) | solved by the committed ramp (holds 0.025) |
| **close timing** | **open**: the policy's close command is late/off (139 mm on the apple), and the lift never starts |

The next cell is therefore **close-timing supervision**: the demos close when the
fruit is within the tracking window; the policy's own command is not that. The
honest options are (i) a DAgger store focused on the arrival states with the
expert's close command as the label, or (ii) a phase feature that carries the
fruit's along-distance relative to the jaw (the scripted window as a *learned*
phase boundary). Both are training-side changes; the sensor, the goal, the action
space and the data count are no longer the limit.

## 19. P145d.6/d.7: the binding term is the **lateral aim**, and the observation is not the problem

Twelve-episode cells (3 seeds x 4, three parallel sims, ~5 min) with the phase
trigger + committed ramp, `[close]` rows on every latch (3-D certificate) and
`[cmd]` rows (the applied joint target vs the measured, with the joint margin):

* **`dz` at the latch is the seat, not an error**: +46..+101 mm, median +67 mm,
  against the 70 mm the pads' geometry defines (`_pad_standoff` + the distal
  plane). The vertical aim is right on every episode.
* **`dx` at the latch is the failure**: -10..-95 mm lateral. Every episode whose
  `|dx| <= 10 mm` **grasped** (peach 6 mm gap, kiwi 6 mm, orange 3 mm); every
  larger offset closed on air. `gap_min` and `gap_close` agree when the ramp
  latches before the closest approach, so the earlier "geometry 1-3 mm" was the
  **xy** minimum, not the grasp.
* **The goal is right**: `goal_x` tracks `fruit_x` to 1-3 mm on every trace row
  (`[policy-trace]` gained `jaw_x`/`fruit_x`/`goal_x`). The perception is not the
  term.
* **The arm holds the station x**: `jaw_x` sits at 0.321-0.324 for 300+ ticks
  while `fruit_x` is 0.225, makes one 35 mm excursion at the descent, and
  **returns**. The demos' descent is a 100 mm lateral leg; the loop reproduces
  35 % of it and then goes back.
* **The commands are consistent but the endpoint is the band mean**: the applied
  joint targets step p50 0.006-0.011 rad, p90 0.047-0.100, with healthy joint
  margins (+0.05..+0.25 rad, no saturation); `[cmd]` shows the arm tracking the
  target to p50 0.004-0.011 rad. The descent's *endpoint* is 0.27, i.e. the mean
  of the demos' aims (0.20-0.36) - the absolute-target action predicts the
  averaged endpoint and the closed loop cannot correct it.
* **Three inference-side fixes are nulls**: `--execute-steps 4/8` (0 latches /
  1 latch), `FRUIT_POLICY_GDP=1 K=4` (1 latch, 50 mm off), and
  `FRUIT_POLICY_FIXED_NOISE=1` (deterministic chunks, command p90 step
  0.100 -> 0.047, target-measured gap p50 0.011 -> 0.004 - **consistency
  improves, the aim does not**). So it is not noise, not the re-plan rate and not
  a joint limit.
* **Offline, at the demo's close state the policy is fine**: the lift is commanded
  (+20.4 mm over its first 16-step chunk against the demo's +2.3 mm immediate
  command; the +5 cm rise is at 1.03 s, which is 2 chunks, and the episode has
  200+ ticks after the close), and its reach amplitude is 1.13x the demo's. What
  it does not command is the grip gap (0.0345, the channel mean, against the
  demo's 0.026-0.027) - which the committed ramp supplies.

**So the pyramid is now: aim (open) -> close actuation (solved) -> grasp (works
when aimed) -> lift (commanded) -> place (untested).** The fix this phase
implements is the **joint-delta action** (`FRUIT_ACTION=dq`): the policy's 7 arm
channels become a per-waypoint step from the *measured* joints
(`q_target = q_meas + dq`), so the aim error is a residual the next observation
corrects instead of an absolute endpoint that averages over the band. The finger
stays absolute; the phase gate, the ramp, the goal and the data are unchanged.

## 20. P145d.8: the delta action is not the fix either - the aim needs the **state**, not another representation

Three more measured cells (8-12 episodes per arm, three parallel sims, one claim
per run).

* **`FRUIT_ACTION=dq`** (the joint-delta servo, trained 30 epochs from `moe_v13s`
  on the aligned store + `demos_v11`, weighted 0.0150 / demo_val 0.0069): the aim
  does **not** improve (12 episodes, gaps 5-115 mm, 5/12 <= 20 mm, **0 grasps**)
  and the **timing breaks** - the delta model's finger sits at the channel mean
  early, so the learned phase gate (goal + finger) fires `grasp` at t = 104-300
  with the fruit **0.2-0.47 m** away (12/12 latches, dz +95..+114). So a delta
  action changes the finger's phase behaviour without fixing the aim: the aim is
  not an action-representation artefact.
* **`FRUIT_POLICY_PHASE=dy`** (the action routing and the ramp latch on the
  measured along-window 0.05 m instead of the learned classifier): the absolute
  model reads **2/8 grasped** (pear 76 mm, peach 50 mm / dz +112), gaps 5-60 mm;
  the dq model **0/8**. No rate change from the routing.
* **The causal goal-x test** (`FRUIT_GOAL_X_OFFSET=0.10`, a diagnostic only): the
  gaps move to 25-74 mm (from 25-76 at the same seeds) - i.e. the +100 mm goal
  shift does **not** propagate to the jaw; the policy's aim is only weakly
  conditioned on the goal's lateral position in the closed loop, even though
  offline a +-50 mm nudge moves its chunk by 0.12-0.15 rad.
* **Offline the same policy is fine** at the store's descent windows: the reach
  direction agrees with the demo (cos p50 0.99) and the amplitude is 1.13x; the
  endpoint differs by 0.122 rad p50 (0.356 p90), which is ~3.5 cm at the TCP -
  the record's representation floor. So the residual is not "the model cannot
  move"; it is that its *aim error* is not corrected by the closed loop.

**What is settled**: geometry is a **lateral aim** problem (the jaw holds the
station x 0.32 while the fruit is at 0.20-0.36; the z/seat is right, the goal is
right), the close actuation and the ramp are right, and the lift is commanded
offline. **What is not**: the aim does not respond to representation (absolute
vs delta), inference (noise, GDP, re-plan rate) or routing (`dy` vs learned).
The remaining term is **state coverage of the aim**: the demonstrations reach the
lateral aim in the last ~0.5 s (a 10 cm leg), and the policy's own descent states
are labelled by an expert whose pre-window label is the **fixed grasp pose** - so
neither source teaches an early lateral alignment. The named next spend is
therefore a **pre-aligned approach**: either a demonstration set whose wait pose
tracks the selected fruit's x (a scripted-side change, both references
re-recorded), or a relative-aim observation channel (goal - jaw, requiring the
FK that `logs/p145` validated to 0.001 mm) with a focused recollection.

No shipped default moved: `FRUIT_ACTION` unset = the absolute path bit for bit,
`FRUIT_POLICY_FIXED_NOISE` off, the `[cmd]`/`[close]` rows only under
`FRUIT_POLICY_TRACE=1`, `FRUIT_GOAL_X_OFFSET` 0. selfcheck PASS (0 failures,
1 skipped).

## 21. P145d.9: a pre-aligned expert cannot be taught with labels-only DAgger

The aim's named fix - pre-align the lateral offset during the wait instead of in
the last 0.5 s - was implemented as an expert *label*
(`FRUIT_EXPERT_PREALIGN=1`, x-only IK toward the fruit at the pose's height,
lead 0.25 m) and collected (18 episodes, three parallel sims, seeds 77/101/202,
`FRUIT_DAGGER_NO_TAKEOVER=1`).

**The store cannot carry it, and the reason is structural**: the expert's label
is **one `ik_step` from the measured joints**, and with labels-only DAgger the
arm never executes that step, so the measured pose stays where the policy put it.
The recorded label therefore moves **once** (measured: j1 -1.390 -> -1.508 at the
fruit's y = 0.205 and flat for the next 1.2 s) instead of integrating the 0.35 rad
the 0.10 m lateral needs. The same applies to the shipped post-window chase - it
is a per-tick increment, not a trajectory, so a policy cloning it reproduces a
fraction of the leg whenever its own state lags.

**So the pre-align is a demonstration-side change, not a label-side one**: the
scripted collector's wait has to hold the selected fruit's x (a `tasks.py` change
that moves the scripted line, owes both references and a re-record), and the
demos then show the lateral move as a slow integrated motion. That is the next
phase's first item, with the relative-aim observation channel (goal - jaw) as its
companion if the demos alone are not enough.

`FRUIT_EXPERT_PREALIGN` stays default off; no shipped path reads it.

## 22. The aim's root cause: the anchor's **support**, not the policy

A store survey (`logs/p145` script, median fruit x per episode) put the whole arc
in one table:

| store | episodes | fruit x mean | p10-p90 | range |
|---|---|---|---|---|
| `demos_v11` (the anchor) | 50 | **0.337** | **0.325-0.353** | 0.295-0.391 |
| `demos_v7`/`v8`/`v9`/`v10` | 42-80 | 0.337-0.340 | 0.324-0.354 | 0.295-0.381 |
| `demos_v12`/`v13p` (two-line) | 80 | 0.353 | 0.28-0.449 | 0.064-0.477 |
| `p145_dagger_wait` (direct) | 40 | 0.287 | 0.224-0.349 | 0.197-0.428 |
| `p145_tcp` (scripted, single arm) | 50 | **0.300** | **0.220-0.363** | 0.174-0.451 |
| the cell's supply (`FRUIT_SUPPLY_X_MIN/MAX`) | - | - | **0.20-0.36** | - |

**The anchor is the pre-v9 fixed line** (a 28 mm lateral band), and the cell
supplies the v9 scatter (a 160 mm band): about **12 cm of the deployment band is
outside the demonstrations' support**. The policy is not aiming "wrong"; it
returns the anchor's mean behaviour and extrapolates ~35 % of the offset - which
is the classic *out-of-support* failure of behaviour cloning, and matches the
literature's named signature for absolute-target BC ("moves toward one of the
demonstrated configurations once the plant comes into view", arXiv 2602.23408).

**The causal test** (the same checkpoint, `FRUIT_SUPPLY_X_MIN=0.315
X_MAX=0.355` = the anchor's support, 3 seeds x 4, the shipped band as the
control): the lateral gap at the closest approach goes **25-76 mm -> 2-13 mm**
(8/12 <= 5 mm, 10/12 <= 13 mm against 0/4 <= 20 mm on the full band) and the
grasps **2/12 -> 4/12**. The aim is a *support* problem, not a capacity, sensor,
noise or action-space problem (all of those were measured null in §19-§21).

**The next term is visible in the same cell**: with the aim at 2-5 mm, only 4 of
the 8 aimed episodes grasped, and the latch's `dz` reads +79..+131 mm against the
70 mm seat - the vertical aim/close timing becomes co-binding.

Fixes, ranked by cost and by the literature (three parallel reviews):
1. **an in-band anchor** (`p145_tcp`: 50 scripted episodes at 0.22-0.363, with
   `tcp`/`jaw`) or a recollection on the shipped band - the direct data-coverage
   fix; training now.
2. **chunk-wise delta actions** (the 13k-rollout study's strongest representation
   result; our step-wise `dq` was the weaker form, `O(k)` error growth).
3. **a relative-error observation** (goal - jaw) and a **goal-swap probe** (same
   proprio, two goals 10 cm apart) to separate trajectory replay from feedback.
4. **DART-style perturbed expert labels** (query the IK expert at 20-100 mm
   offsets) or **expert-in-control corrective segments** - the corrective states
   the labels-only store cannot contain.
Not indicated: temporal ensembling (averages modes), longer chunks, a classical
visual servo (violates the brief), or more same-distribution DAgger episodes.

## 23. The precise classic problem: the **initial state** was out of the demonstrations' support

The store survey's last piece: **the demonstrations' frame 0 is not a fixed
pose.** In `demos_v11` (45 right-arm episodes) the first action's j4 and j6 are a
**1-D family in the selected fruit's x**: j4 = 3.036 - 5.741 x, j6 = -0.857 +
4.299 x, **r = -0.994 / -0.997**, and at x = 0.34 it reproduces the `wait`
waypoint to 0.007-0.020 rad on all seven joints. The same family is in
`p145_tcp` (r -0.994) and in a fresh collection (`p146_anchor`, r -0.998): **the
scripted line's hover pre-aligns the wait pose to the fruit's x**. The direct
env's `FRUIT_DIRECT_START=wait` teleported to the **fixed** `wait` (j4 1.104),
i.e. to x = 0.33 - so at a fruit x = 0.225 the policy's first observation was
**0.66 rad out of the demonstrations' support**, and the 10 cm lateral descent it
was asked for **does not exist in the demonstrations at that state** (they start
already aligned and only make the residual). That is the classic *initial-state
distribution mismatch* (the data-coverage/covariate-shift family), and it is a
precise mechanism for the "35 % then return" measurement: the policy is
extrapolating its start pose, not failing to see the goal.

Two code fixes, both default off:

* **`FRUIT_DIRECT_START_ALIGN=1`**: at reset, one position-only IK solve of the
  wait pose at the selected fruit's x, then a teleport (the demonstrations'
  frame 0). Measured (seed 77, 4 episodes, the h16c checkpoint): the closest
  lateral gap **25-76 mm -> 1-55 mm, 3/4 <= 12 mm**; the start's jaw x 0.254 for
  a fruit at 0.225 (a 29 mm residual is the IK's own convergence).
* **`FRUIT_CLOSE_RAMP_DY`** (default 0.05 = the old behaviour): the ramp's
  **own** along-distance, separate from `FRUIT_PHASE_DY` (the descent's start).
  The demos close at fruit y +0.014 (the timing census), so a 0.05 ramp latches
  ~0.3 s early with the hand still descending. `=0.014`: the latch moves to
  xy **14-30 mm** and `[close] dz` **+100 -> +59 mm** (median; range
  +46..+110). Also fixed: in `phase` trigger mode the policy's own finger no
  longer latches the ramp (its channel sits on the action mean 0.0345 and
  crossed the 0.035 threshold at arbitrary times - one apple latched at t=104
  with the fruit 167 mm away).

**The in-band pre-aligned anchor** (`datasets/p146_anchor_all`: 51 scripted
single-arm episodes, fruit x p10-p90 0.212-0.346, j4 0.97-1.82, 50/50 success)
and a 30-epoch fine-tune from it (`checkpoints/p146_anchor`, weighted 0.0182):
with the aligned start it reads gaps 97/24/**8**/89, 59/34/14/35, 63/74/**5**,
**0 grasps** - i.e. the anchor alone does not move the aggregate; the remaining
term is the **descent's vertical completion and the lift transition** (the
latches read dz +94..+124, and a near-perfect close - xy 14 mm, dx -6 mm - still
ends with the fruit on the belt and the jaw at 1.254: no lift).

**So the decomposition stands, one level deeper**: aim -> (initial-state
mismatch, fixed by the aligned start) -> vertical descent + close timing (the
two windows separated; partly fixed) -> **lift transition (open)**: the policy's
`grasp` expert holds at the deployed close state instead of emitting the
demonstrated test lift, and the `dy` routing keeps the skill at `grasp` after the
close (a design defect of that mode; the learned classifier is used instead).

## 24. The "no lift" is really a **world-static hold** - the demos track the belt

Two offline instruments (FK validated to 0.00000 m against `p146_anchor`'s
recorded `tcp`/`jaw`) and an oracle review settle the lift term:

* **The demos' 17-frame post-close hold is a tracking hold**: the jaw travels
  **37-67 mm downstream** (p50 49 mm, ~0.086 m/s) while the hand-frame drift is
  only **2.5-5.2 mm**. The deployed policy holds the **world** pose, so at
  0.12 m/s the fruit leaves the pads in ~0.1 s (measured: the gap grows 14 mm ->
  360 mm while the jaw stays at 1.254). The distinguisher is hand-frame drift
  (demo 2.5-5.2 mm, P102 held legs 0.02 mm, this failure ~360 mm) - a
  world-static hold on a moving belt is a loaded slide, not a hold.
* **The "pop" is a command transient**: the achieved jaw moves only 1.5-4.1 mm on
  that frame, and the scripted test lift is 6-10 mm (`tasks.py:16330`) while the
  outcome needs 50 mm - so cloning the pop cannot convert by itself.
* **No expert ever sees "closed at the belt -> track -> lift"**: the `carried`
  rule (`skills.py:46`, z > rest + 0.06) puts the `lift` class's first frame at
  **close+32 (close+16..+34), z +58 mm**, i.e. ~15 frames *after* the pop; the pop
  itself is labelled `grasp` on 26/50 episodes and `approach` on 22/50 (the
  measured finger at the close is 0.0307, above the 0.030 threshold).

**The fix (default off, labels only - a retrain is the whole change)**:
`FRUIT_SKILL_LIFT_RAMP=1` makes the `lift` class start at the **committed ramp's
settle** (`close + 5` frames) instead of the 6 cm rule, so one expert owns the
tracking hold, the pop and the ramp. The gate retrains with the same rule
(`checkpoints/p146_phase`, val 98.3 %, `grasp->lift` 15/50 at the boundary) and
the policy retrain is from `p145_wait_h16c` at lr 3e-5 (`p146_liftlabel`).

**The runtime switch alone does not convert**: `FRUIT_CLOSE_RAMP_LIFT=1` (route to
the `lift` expert once the ramp completes) reads **1/12** with the learned gate
and **0/8** with `FRUIT_PHASE_DY=0.10` - consistent with the expert being out of
distribution at the close state. The decisive measurement is the oracle's:
replay one failing close state with skill 1 vs 2 and read the chunk's cross-belt
displacement over 17 waypoints against the demos' 37-67 mm; if both are ~0, the
lift must come from a supervisor or from the relabelled expert (this retrain).

## 25. The lift label retrain: direction fixed, magnitude still 42 %

`FRUIT_SKILL_LIFT_RAMP=1` (the `lift` class starts at the committed ramp's
settle, so one expert owns the tracking hold + the pop + the ramp) retrained from
`p145_wait_h16c` at lr 3e-5 (`checkpoints/p146_liftlabel`, weighted 0.0099,
`proprio_dim 26`, `cmd_channel true`). The FK replay at the closed states (n=26,
jaw-centre FK accurate to 0.0004 mm):

| skill at a **closed** state | dy (downstream) | dz (up) |
|---|---|---|
| demos' tracking hold (close+6 -> +22) | **+41.4 mm** | +0.6 |
| old `lift` expert | +0.8 mm | +28.0 |
| **retrained `lift` expert** | **+17.5 mm** (p90 +38.9) | +10.0 |
| `grasp` expert | +25.1 mm | -19.0 |

So the relabel moved the expert from *upstream* to *downstream* (the direction is
fixed) but it executes **42 %** of the demonstrated hold speed. The same
under-execution is the lateral aim's measured 35 % - i.e. **the model
systematically under-executes the demonstrations' motions at the contact
states**, which is the conditional-mean behaviour the 13k-rollout study fixes
with *chunk-wise delta* actions (our `dq` was the weaker step-wise form).

The cell (3 seeds x 4, aligned start, ramp dy 0.014, the retrained gate
`p146_phase`, the retrained model): gaps **68/22/13/6, 62/1/7/63, 53/62/16/70**,
**1/12 grasped** - the aim is good on half the draws and the lift still does not
convert, consistent with the 42 % hold.

**A real bug was found and fixed on the way**: a fine-tune started from a 26-D
*command-channel* artifact inferred `speed_channel` from `proprio_dim > 25`,
widened it again to 27-D and the env refused the artifact at construction
(`RuntimeError: ... proprio_dim=27 but this environment builds 26-D`). The
inference now prefers the recorded `speed_channel`/`cmd_channel` flags, then the
env's own `FRUIT_OBS_CMD` gate, then the legacy width rule; the new artifacts
record both flags.

## 26. The under-execution is systematic - the chunk-relative action (in progress)

Two independent measurements of the *same* behaviour at contact states: the
lateral aim executes **35 %** of the demonstrated offset (§22) and the post-close
tracking hold **42 %** (17.5 of the demos' 41.4 mm downstream, §25). The FK
replay also shows the direction can be right while the magnitude is not
(`+0.8 -> +17.5 mm` after the label fix). The demos' own hold is a tight
distribution (+41.4 p50 / +52.7 p90 downstream, dz +0.6), so the target is
learnable; what is wrong is the **absolute anchor** the policy predicts and the
env applies.

`FRUIT_ACTION=rel` (default off) implements the 13k-rollout study's chunk-wise
relative form: the 16 waypoints are **offsets from the window's first frame**
(`data.py`, the per-window transform + a sampled relative normaliser), and the
env re-anchors each chunk to the **measured joints at the chunk's start**
(`q_target = base + (waypoint - waypoint[0])`, `rl_env.act`/`_apply`). The
checkpoint records `action_mode` and the env refuses a mismatch. Verified
offline: `action[0, :7] == 0` exactly, the offsets span 0.59 rad at a sampled
window, the 26-D width is unchanged, and `selfcheck.sh` is PASS with the mode off
(the default path is untouched).

## 27. The label mix is the close-state mechanism; the descent is still short

The 16-frame joint offset at close+6 separates the two stores by **3.7x**:
`demos_v11` **0.734 rad** (the tracking hold + pop) against
`p145_dagger_wait` **0.199 rad** (the labels-only expert's one IK step). With
`close_weight=10` on both, the rollout store dominates the close-state fit -
which is the measured 42 % hold and 35 % aim in one number.

Three controls, all with the aligned start, the ramp dy 0.014, the retrained
gate (`p146_phase`) and `FRUIT_SKILL_LIFT_RAMP=1`:

| arm | aim (gap_min) | `[close] dz` | grasp |
|---|---|---|---|
| absolute, full DAgger + demos (`p145_wait_h16c`) | 1-68 mm | +55..+128 | 1-2/12 |
| **chunk-relative** (`FRUIT_ACTION=rel`, `p147_rel`) | **6-50, 8/12 <= 19** | +136 | 0/12 |
| demos-only (`p148_baseonly`) | 6-84 | +147 | 0/12 |
| DAgger pre-close + demos close (`FRUIT_DAGGER_STOP_BEFORE_CLOSE=16`, `p149_mix`) | 8-110 | +123 | 0/12 |

**The relative action's aim is the best measured (8/12 <= 19 mm) and its FK hold
is the best of the learned arms, but every non-DAgger arm loses the vertical
descent** (`[close] dz` +123..+147 against the 70 mm seat): the descent's
completion is the same under-execution one axis over, and the DAgger store is
what teaches it (its pre-close label is the fixed grasp pose *at* the seat).

So the remaining failure is a single class - **the contact-phase motions are
executed at 35-42 % of the demonstration** - and the store mix trades one axis
for another. The record's next spend is therefore a **contact-phase store with
the expert in control** (HG-DAgger/IWR: the labels-only store cannot contain the
corrected states, measured in §21/§24), not another weighting.

## 28. The contact store, and the research synthesis: the hold is a **velocity** task

The expert-in-control contact collection (`FRUIT_DAGGER_CONTACT_TAKEOVER=1`) was
fixed per the oracle's code review (the takeover from the tracking window 0.05,
the expert **carrying** `_q_cmd` and aiming at `fruit + v*lead` instead of a
per-tick `sync_command_to_measured`), and the store quality was measured with the
oracle's regression, `d(jaw_y - fruit_y)/dframe` over the 17 post-close frames
(FK validated on the asset):

| store | slope p50 | jaw/fruit travel | tracking / escape |
|---|---|---|---|
| P151 (frozen pose + lagging chase) | -1.84 mm/frame | 0.174 | 3/18 / 4/18 |
| P152 (carry + lead 0.18 s) | -1.06 | 0.465 | 8/18 / 1/18 |
| **P153 (carry + lead 0.38 s)** | **-0.60** | **0.613** | **15/18 / 0/18** |
| demos `demos_v11` | -0.095 | **0.965** | 50/50 / 0/50 |

The **label** tracks at 1.00; the achieved states do not. The lead is a
proportional-control feed-forward: 0.18 -> 0.38 s (2.1x) bought only 1.32x
(K ~ 2.6 /s, saturating near 47 mm/s against the demos' ~100 mm/s).

Three learned arms (the same 3x4 cell, the aligned start, the ramp dy 0.014):
`p149_mix` (the DAgger pre-close + the demos) **0/12, dz +123**; `p153_contact`
(the P153 store + the demos) **0/12, dz +192**; the full-DAgger arms `1-2/12, dz
+55..+128`. The DAgger store's **pre-close** label is the fixed grasp pose *at the
seat* - the only supervision that puts the hand down; its **post-close** label is
one IK step (0.199 rad) against the demos' tracking hold (0.734 rad). The two
stores therefore teach the descent and the hold respectively, and every weighting
trades one for the other.

**The literature (two parallel reviews) names the class**: absolute position
actions for quasi-static contact vs **velocity/feed-forward for tracking a moving
reference** (the split is regime, not a universal winner); a **stiff position
loop converts a tracking error into contact force** (Hogan), and the belt's drag
on a held 100 g fruit is only `mu_b m g` = 0.05-0.5 N - i.e. a world-static hold
should *stick within 1-2 mm or never stick* (a sustained 100 mm/s slide is a
torque/wedge or a relative-motion effect, not a squeeze deficit); and the
**teacher's actuation lag corrupts the labels** (HG-DAgger's own argument) with
the *exceed share* as the predictor (RACE/merge-cap).

Ranked fixes: (1) **velocity feed-forward through the existing chunks** -
differentiate the predicted waypoints and lead the drive command (the measured
precedent is a 205 -> 47 ms lag reduction; no action-space change, the metric is
the hold's `|v|/100 mm/s` ratio >= 0.8 and a hand-frame drift < 1 mm); (2)
**relabel to the achieved states + an exceed-share filter** (the teacher promises
a ramp the plant delivers at 0.61x); (3) a **phase-scoped velocity action** for
the hold/carry only; (4) a **belt-frame hold target** (or lift clear of the belt,
the industrial move); and **before any of these, measure the drive saturation** -
the 47 mm/s ceiling may be a torque/velocity limit that a feed-forward cannot
exceed.

## 29. Velocity feed-forward on the chunk is a null - because the chunk's velocity is ~0

`FRUIT_POLICY_FF=<ticks>` leads the applied joint command by that many ticks of
the chunk's own per-tick velocity (no retraining, no action-space change). The A/B
(2 seeds x 4, the aligned start, the ramp dy 0.014, the gate, the lift label,
`p145_wait_h16c`), read with the loop's own post-close tracking regression
(`logs/p145/loop_track.py`: the slope of `jaw_y - fruit_y` over the 17 frames
after the `[close]` latch, from the existing `[policy-trace]` rows):

| arm | slope (mm/frame) | jaw travel (17 frames) | fruit travel |
|---|---|---|---|
| FF off, seed 77 / 101 | **+2.91 / +4.25** | +8.0 / -5.5 mm | -34.5 / -64.0 mm |
| FF 2 ticks, seed 77 / 101 | +3.54 / +3.10 | -2.5 / -1.5 mm | -62.5 / -51.5 mm |
| demos (reference) | **-0.095** | +57 mm | -59 mm |

**A positive slope is the world-static hold** (the fruit moves, the jaw does not);
the demos track at -0.095. The feed-forward cannot help because the *chunk the
policy predicts* at the hold travels only ~8 mm over 17 frames - 0.5 mm/frame
against the demos' 3.4 - i.e. the command itself carries ~1/7 of the velocity, so
leading it by a few ticks moves nothing. The policy's contact-phase prediction,
not the drive's following error, is the binding term.

This closes the "it is a servo/feed-forward problem" hypothesis (it is the
oracle's/agent's #1) and leaves the two larger builds: the **achieved-state
relabel** (RACE: label the state the plant reaches, not the command it is given -
the exceed-share family) and a **velocity action** scoped to the hold/carry.

## 30. A 32-waypoint chunk (1.07 s) is also a null: the transient under-executes at every horizon

`--action-horizon 32` (the denoiser is fully convolutional over the action axis,
so the pre-trained head is reused; the store's 32-step windows are half beyond
what the 16-step base saw) with `--execute-steps 32` x hold 4 = **128 ticks per
decision**, so the descent + close (30 frames) fit inside one chunk. Cell, 3 x 4:

| | aim (gap_min) | `[close] dz` | tracking slope | grasp |
|---|---|---|---|---|
| h16 (`p145_wait_h16c`) | 1-68 | +55..+128 | +2.9..+4.3 | 1-2/12 |
| **h32 (`p156_h32`)** | 2-88 | **+74..+213** | **+2.8..+5.1** | **0/12** |

No improvement: the close is still 4-14 cm high and the post-close hold is still
world-static (a positive slope = the fruit moves, the jaw does not). With §25-§29
this closes the "one more chunk can cover it" hypothesis as well.

**The cumulative picture** (every arm measured, one cell each): the contact phase
- the descent's completion, the close's height, the hold's velocity - is
reproduced at 35-42 % of the demonstrations by the monolithic 30 Hz joint-position
policy, and the under-execution is invariant to the label mix (§27), the action
representation (§26 rel, §19 dq), the store (§25 base-only, §28 contact), the
skill routing (§24), the inference (GDP/noise/re-plan rate, §19) and the chunk
length (§30). Offline, the same model reproduces the hold at the **demos'** states
(+43.5 mm of the demos' +41.4, §26) but not at the states its own descent
produces - so the residual is the *state* the under-executed descent creates, and
the descent itself is under-executed at every horizon.

**What that leaves** (both larger than one phase): (a) a **velocity/impedance
action scoped to the contact phase** (a 14-D position+delta head, or a
joint-velocity action integrated by the env) - the literature's regime split says
the approach wants position and the hold wants velocity; (b) a **state-matched
contact store**, i.e. the expert in control from the pre-aligned start through the
transient with the tracking ratio verified (the P153 store reaches 0.613 against
the demos' 0.965; a velocity-profiled teacher would reach higher).

## 31. The 16-D position+velocity action works mechanically and moves the hold 2-3x - but 30 epochs is not enough

`FRUIT_ACTION=posvel` implements the regime split the literature names: the action
is `[pos(7), finger, finger, delta(7)]`, where the delta is the demonstrations'
**per-frame command velocity** (a *supervised* velocity, not a feed-forward of the
position's own ~0 velocity), and the env leads the applied joint command by
`FRUIT_ACTION_DELTA_LEAD` frames of it (default 1.0). The layout keeps `action[7]`
/`action[8]` as the finger, so every existing consumer (`skills`, the cmd channel,
the recorder, the close ramp) is unchanged.

Mechanics: `widen_action` pads the input conv's channels **and** the output
conv's rows with zeros (the artifact starts exactly as its parent; the head is
`action_in` + `head.2`), the normaliser gains `(0, 0.05)` for the 7 new dims, the
checkpoint records `action_mode="posvel"`, and the env refuses a mismatch. Store
smoke: `action.shape == (16, 16)`, the delta mean |0.0082| rad/frame, std 0.0228.

The first cell (2 seeds x 4, everything else as the h16 arm):

| | tracking slope (mm/frame) | jaw travel | `[close] dz` | grasp |
|---|---|---|---|---|
| position-only (h16) | +2.9 / +4.3 | +8.0 / -5.5 mm | +55..+128 | 1-2/12 |
| **posvel, 30 epochs** | **+1.62 / +1.25** | +3.5 / -19.0 mm | +45..+104 | 0/8 |

The hold moves **2-3x closer to tracking**, so the channel carries signal - but
the training loss only fell 0.46 -> 0.34 (the 7 delta channels' normalised
residual is still ~0.8, i.e. the head predicts mostly the mean) and the grasp is
still 0/8. The delta head is **undertrained**: the position head is pre-trained
while the 7 new output rows start at zero, which is the same shape as the P145d
cartesian head (100 epochs to fit). The next cell is a 100-epoch run (or a
separate, higher lr for the new rows), with the same readout.

## 32. The 16-D action is fit offline and **inert in the loop** - the closing null

With the delta head actually converged (60 epochs at lr 1e-4: the weighted loss
0.46 -> 0.0257, `demo_val` 0.0147 - the 7 delta channels are fit), the cell reads:

| posvel arm | tracking slope | jaw travel | `[close] dz` | grasp |
|---|---|---|---|---|
| 30 epochs (undertrained) | +1.62 / +1.25 | +3.5 / -19.0 | +45..+104 | 0/8 |
| 60 epochs (converged) | +3.44 / +4.31 | -4.5 / +3.5 | +72..+155 | 0/12 |
| 60 epochs, **lead 0** (control) | +3.37 / +3.87 | -8.5 / -3.5 | - | 0/8 |
| position-only (h16) | +2.9 / +4.3 | +8.0 / -5.5 | +55..+128 | 1-2/12 |

**Two things**: the 30-epoch "2-3x closer to tracking" was the *undertrained*
head's noise (the converged head is back at the position-only level), and the
lead-0 control is the same as lead 1.0 - **the delta channel does not change the
closed loop at all**, although it is fit to 0.0257 offline.

That is the same signature as §19/§26/§29/§30: **the closed-loop behaviour is
insensitive to supervision and representation changes that the offline fit
clearly sees.** The policy's action in the loop is dominated by a component that
none of these channels reach - the loop's own state trajectory (an under-executed
descent feeding an out-of-distribution close), which reproduces at 35-42 % of the
demos no matter what the head is trained on.

**Verdict for this phase**: the contact phase is **not reachable by supervision,
representation, routing, inference or chunk-length changes on this data** (all
measured, §19-§32). What is left is structural: a phase-split policy whose
contact model is conditioned on a **state-matched handoff** (the approach model's
own end state, not the demos'), or the record's hardware/workstation sanctions
(`docs/LEFT_ARM.md`, `logs/p42/SIM_LIMIT.md`, P90's place-station map).

## 33. The start pose, fixed properly: the demos' own linear family (the IK alignment was 5-8 cm high)

A support check (jaw-centre FK, frame 0 of every episode) found the alignment's
defect: the deployment's aligned start read **jaw_z 1.373-1.385**, while *every*
store's frame-0 jaw_z is **1.300-1.326** - the IK alignment reproduced x but sat
5-8 cm high, so the episode still began out of support. `0/9` of the deployment's
start points fell within 1 cm of any frame-0 point in `demos_v11` **or**
`p146_anchor_all`.

`FRUIT_DIRECT_START_ALIGN=family` replaces the IK with the demonstrations' own
**frame-0 family**: a least-squares linear map per arm
(`configs/start_pose_family.json`, fitted on `p146_anchor_all`: right n=38,
x 0.210-0.354, **rms 0.0168 rad**; left n=13, rms 0.0138), `q0 = a + b*fruit_x`.
Verified in the loop: the start now reads **jaw_z 1.314** (inside the stores'
band) on every arm.

The cell (h16c, 2 seeds x 4): the aim 67/21/21/12 and 31/19/11, **1 grasp**
(orange, 11 mm), the tracking slope +1.70 / +3.30 - the start is in support and
the aim is good on the near draws, but the hold is still static and the close's dz
still +100. The in-band anchor + the pre-close DAgger + the lift labels together
with the family start (`p159_inbandmix`, 30 epochs) reads **0/8** with dz +126 and
the slope +3.56.

## 34. The oracle's review, and the end of the supervision search

Three findings from the review that the measurements support:

1. **The model is a replay from the start pose, not a goal-conditioned aim.** §20's
   causal test (a +100 mm goal-x offset) did not propagate to the jaw, while the
   offline probe moves 0.12-0.15 rad per 50 mm - so the loop's own state, not the
   goal, decides the action.
2. **The mix's two wait labels disagree**: the anchor's aligned hold against the
   expert's fixed `_expert_grasp`; `p146`'s first applied command is that blend
   (the target j4 1.266 against the measured 1.668).
3. **`FRUIT_DAGGER_STOP_BEFORE_CLOSE` has a real cost**: it deletes the
   policy-distribution states nearest contact (the oracle's recommendation is to
   keep them and down-weight or relabel the close), and the cut is exact only
   when the stop >= the horizon (16 = H is fine; 32 would not be).

**Phase verdict, final for this session**: the contact phase is not reachable by
any supervision, representation, routing, inference, chunk-length, start-pose or
velocity-channel change measured in §19-§34. The one causal chain that survives
all of them is: the descent under-executes (35-42 %) -> the close happens 4-14 cm
high -> the model, at that out-of-support state, holds the world frame instead of
tracking the belt. Offline the same model reproduces the demos' hold (+43.5 of
+41.4 mm) at the demos' own close states, and the demos' own close state is the
one its descent never reaches.

## 35. What the policy actually sees: the fruit is 1-4 px, the RGB is nearly grey, the mask is empty

Dumped the model's image input (the first frame, a pre-close frame, and a demo's
first frame) with the exact loader transforms:

| channel | content | fruit share |
|---|---|---|
| RGB 240x424 | the robot's own gripper fills the centre; the belt is dark grey; the fruit is a 2-4 px coloured dot | **4 px** (0.004 %) pre-close; 138 px (0.14 %) at frame 0; **0 px** at a demo's frame 0 |
| depth | the belt plane + the gripper; the fruit is a shallow step (0.79-0.87 m) | no separate structure |
| `target_mask` | that same 4 px dot, often 0 | 0-0.14 % |
| **the model's 128x128** | the above, downsampled (x0.30 linear, x0.09 area) | **0-1 px, sub-token** |

The scene's RGB is also **nearly grey**: the whole-image per-pixel channel spread
is **2.05/255** (the fruits are the only saturated pixels), and the palette makes
the fruit a tiny coloured dot on a dark belt. At 128x128 a 1-4 px target is below
every measured regime in the camera literature - which is exactly why the goal
vector and proprio do the work, and why the policy behaves as a replay from its
own pose (§20, §34).

**The `down_x_160` camera override renders black in the collector**: a 12-episode
x 3-shard recollection at `FRUIT_HEAD_CAMERA=down_x_160` produced `image_rgb` all
zero on every frame (mean 0, spread 0) - the override's eye/target is applied to
the prim but the render product does not follow, so that collection is void (the
mask is empty for the same reason). The override needs its own fix before it can
be used for a recollection.

**The literature's ranking for this exact regime** (a 128x128 budget, the policy
must grasp): (1) a **fixed wide view + goal/EE-centred crops** - the measured
"fisheye + EE crops" cell reads 72/84/82 % against 42/30/28 % for random crops, and
FoveaVLA's external + foveal crop 70.8 % against 25.0 % external-only; (2) a
**wrist camera** (+18-30 pp over external-only, the standard in pi0/ALOHA/DROID,
but a raw 128x128 wrist view is a contact-phase sensor); (3) the shipped top-down
+ a crop only (pixel density only - the hand still occludes). A 1-4 px target at
128 is sub-token, so the camera swap must come with the crop and a same-batch
retrain; the zero-shot camera tests (P144 4/12 vs 9/24) are distribution shifts
and cannot decide.

## 36. The camera path: the mechanics are in place; the new camera's own stores are the missing piece

Built and validated this round: the head-camera housing/mast fix (black render when
the camera does not look toward +x), `down_x_160` (81.4 % visible; the fruit 14-46 px
against the shipped 4 px / 0 px at a demo's frame 0), the **foveal crop**
(`FRUIT_IMAGE_FOVEA`, a `crop_and_resize` around the target with the projection
validated to **1.3 px median / 2.1 p90** against the instance mask; the loader and
the env share the same code), and a `near_x_80` close pose that **wedges the
renderer** (measured: "sim clock advanced 0.49 s in 600 s wall" in
`RenderingManager.render()`, while a same-batch shipped-camera control reads 2/2
episodes - the pose is retired).

Two new-camera arms, one cell each (3 x 4, the family start, the ramp dy 0.014, the
gate, the lift labels, the interaction crop at 128):

| arm | aim (gap_min) | `[close]` latch | grasp |
|---|---|---|---|
| 35 episodes, base-only | 10-137 | none | 0/12 |
| 72 episodes, base-only | 11-162 | none | 0/12 |
| 72 + an 18-episode new-camera DAgger store | **1-92 (8/12 <= 30)** | none (the ramp never reaches dy 0.014) | 0/12 |

The crop's mechanics are visible in the numbers (the aim returns once the DAgger
store exists), but the ramp never latches: the approach is still too coarse for the
0.014 m trigger. The old camera's recipe (the anchor + the DAgger store **of the
same camera**) is what the new camera now has too - so the next read needs the
larger data the literature puts on the steep part of the curve (35 -> 75 ->
150 episodes: +10-25 then +0-10 points), not another 12-episode draw.

The literature's confirmation of the design: a fruit-only crop can suppress the
close (the interaction crop must hold the gripper + the fruit - ours does), crops
alone measured +35.4 points (31.3 -> 66.7) and a full view without a crop 6.3 % vs
70.8 % with it (FoveaVLA), a second view adds +6.3 at ~2x latency (last), and a
camera change is a scale/FOV shift that needs a fine-tuned stem and tens of episodes.

## 37. The single-camera trade-off: `down_x_160` buys visibility and loses the approach

The 150-episode data rung landed at **112 demos + 36 same-camera DAgger
episodes** (the shards stopped at 37/38/37 when their seeds exhausted), trained
with `FRUIT_IMAGE_FOVEA=128` and a **crop augmentation** (`FRUIT_IMAGE_AUG=0.2`,
the literature's scale/translation remedy: 0.7x scale reads 0 -> 0.725 with
0.7-1.3 augmentation), 30 epochs, weighted 0.0165. Cell, **10 episodes x 3 seeds**
(the WS-4.2 scale rather than the 12-episode draws):

| arm | aim (gap_min) | latch | grasp |
|---|---|---|---|
| 35 ep, base-only, no aug | 10-137 | none | 0/12 |
| 72 ep + 18 DAgger | 1-92 | none | 0/12 |
| **112 ep + 36 DAgger + aug** | **1-172 (many 100-170)** | none | **0/30** |

The aim **degraded** with the larger data: the cells' typical gap is 100-170 mm
against the old camera's 1-70. The reason is geometric, not statistical:
`down_x_160` looks along the belt from downstream, so it sees the fruit at the
close (81.4 % visible, the hand no longer on the ray) but **foreshortens the
approach band** - and the foveal crop follows the *fruit's* projection, which
early in the approach is at the frame's edge or in the void, so the early crop
carries nothing. The shipped top-down camera has the opposite trade (a good
approach view, the hand occluding the close at 4 px).

**That is a single-camera impossibility for this cell**, and it is the one
structural conclusion the whole camera arc (P144, P161-P164) supports: the
approach needs a wide/top-down view of the band, the close needs a view off the
hand-fruit ray. The literature's fix is exactly this pair - a second view adds
+6.3 points at ~2x latency with late fusion, and it is the *last* spend in the
ranking only because a single good cropped view normally suffices; here it does
not (one view cannot be both).

Next build (the only remaining camera route): **two views, separate encoders,
late fusion** - the shipped head camera (or the top-down) for the approach and
`down_x_160` for the close, each with its own crop; the 5-channel image stack
becomes two stacks; the model's visual encoders are independent (the literature
is explicit that early/pixel-concat fusion underperforms late fusion), and the
latency doubles (~26 -> 50 ms per chunk, still inside the 0.53 s decision).

## 38. The shipped camera + a 64-px crop restores the close latch - the descent's completion is still the term

The best single-view configuration is the **shipped camera with a 64-px foveal
crop** (the fruit 0-760 px in the crop against 0-4 px in the full frame, and the
approach geometry intact - `down_x_160` loses it, §37). Trained on the in-band
pre-aligned anchor (51 episodes) + the same-camera DAgger store (40) + the crop
augmentation (0.2), 30 epochs (weighted 0.021):

| arm | latch (`[close]` rows) | `dz` at the latch | tracking slope | grasp |
|---|---|---|---|---|
| old camera, full frame (h16) | 1-2/12 | +55..+128 | +2.9..+4.3 | 1-2/12 |
| old camera, **crop 64** | **28/30 episodes** | **+49..+137 (p50 +96..+119)** | +3.2..+3.9 | **0/30** |

The crop's effect is on the *latch* (the ramp now fires on 28 of 30 episodes
against 1-2 of 12), i.e. the policy's along-belt tracking is good enough to reach
the 0.014 m trigger; what remains is the **vertical completion**: the jaw closes
**2.6-5 cm above the 70 mm seat**, so the pads straddle the fruit off-centre and
the post-close hold is world-static (the fruit leaves). This is the same
under-execution measured in §19-§34, now with the latch firing on almost every
attempt - i.e. the failure has been isolated from the approach and the timing to
the **descent's last 2-5 cm**.

The record's own limit note is consistent but not the cause at the seat: the jaw
centre cannot descend below `belt_top + 0.05` (assets.py:299), the seat is
`belt_top + 0.10`, and the pads' lower end at the seat sits 62 mm above the belt -
so the belt is not blocking the seat; the arm simply stops 2-5 cm short of the
commanded descent, exactly the profile-boundary shortfall the scripted line's
post-descent solver corrects and the policy does not reproduce.

## 39. The descent's shortfall is (mostly) the arm's reach envelope - measured

Two arms and one probe settle it:

| arm | latch | `dz` at the latch | grasp |
|---|---|---|---|
| tail weighting (`--close-lead 25 --close-tail 20 --close-weight 20`, 40 ep) | 24/30 | **+103** (p50) | 0/30 |
| + **one-shot seat commit** (`FRUIT_CLOSE_RAMP_SEAT=1`: one position-only IK to `[jaw_x, jaw_y, fruit_z+0.070]` at the latch, held for the ramp) | 20/30 | **+141** (worse) | 1/30 |

**The probe**: the seat commit's own IK residual, at the latch, reads **13-38 mm**
(one 92) - and the oracle's calibration was "<= 6 mm = policy, 20-50 mm =
geometric". The record's static station sweep (`logs/p66/STATION_SWEEP.md`, 150
cells) agrees from the other side: at the **grip depth** the reach is 5.8-6.0 mm
across x 0.188-0.320 for y >= -0.05 - **with `j3` at its limit everywhere it
works** - and at the **lift's end** (z = 0.360) *no* cell solves within 6 mm (the
best is 45.8-81.8 mm). So the station is at the arm's reach edge: the grip can be
solved but not from every pose (the position-only IK from the latched, j3-limit
pose leaves 13-38 mm), and the lift's end is outside the envelope at every tested
cell.

**That is the record's "Known limit" measured on this tree**, and it reframes
§19-§34: the "under-execution" that was invariant to every supervision and
representation change has a geometric floor at the descent's end and the lift's
end. The seat commit (B) made it *worse*, because committing to an unreachable
point drives the arm into its own boundary (dz +141 against +103).

The one scene lever that could move it - the pick station - was swept in P66 and
does not rescue the lift's end (no cell at z = 0.360), so a station shift buys the
grip's margin (j3) at most. The remaining levers are the record's two hardware
sanctions (a new pad asset, a real-jaw clamp-force anchor) or a workstation that
shortens the lift/transfer - not another policy or camera change.

## 40. CORRECTION of §39, and the answer to "why does the scripted line work": the feedback form

The scripted line's descent also ends 40-90 mm short, and it still places 7-8/10
because of its **post-descent solver**: a 120 Hz position-only IK that re-aims at
the fruit's *measured* centre plus a velocity lead (`centre_now + v*lead`) and lets
the wrist rotate, so it **reconfigures out of the j3-limit pose over several
ticks**. §39's "geometric floor" was too strong: the grip is reachable at 5.8-6.0
mm (P66's grid) - just not from the latched boundary pose with a *single* solve
(the seat commit's 13-38 mm). The obstruction is the **form of the controller**
(open-loop chunk vs re-aiming feedback), not an unreachable point.

Measured on this tree (the crop model, 10 episodes x 2 seeds per arm):

| arm | decisions | grasp | `dz` | tracking slope |
|---|---|---|---|---|
| control (execute_steps 16) | 7.5 Hz | **0/30** | +103 | +3.2..+3.9 |
| execute_steps 8 | 15 Hz | **2/20** | +119 | +1.5..+5.1 |
| execute_steps 4 | 30 Hz | **1/20** | +104 | +2.0..+2.9 |
| + goal lead 0.12 s | 30 Hz | 0/20 | +114 | +2.3..+3.0 |
| + goal lead 0.25 s | 30 Hz | 1/20 | +93 | +2.0..+2.8 |

**The re-plan rate is the first lever since the crop with a direction** (3/20 pooled
against 0/30 at the trained cadence), and the goal lead is a null at both rungs.
The `dz` does not move with the rate (~100-120 in every arm) - the vertical
reconfiguration needs the *wrist-freedom + measured re-aim* the scripted solver
has, which a 16-waypoint joint chunk does not express. The named next form is a
**contact-phase head**: a short action horizon (4 waypoints) trained on the
contact windows and executed at 30 Hz, i.e. the learned analogue of the scripted
catch-up (the RDP/PACE direction, not a faster replay of the same chunk).

## 41. The 4-waypoint contact head: the best `dz` of the session, the same count

A contact head with `--action-horizon 4` (the short chunk = a 0.13 s prediction),
trained on the same anchor + DAgger + crop with the close weight 20/lead 25/tail
20, 40 epochs (weighted 0.0174), 10 episodes x 2 seeds per arm:

| arm | decisions | grasp | `dz` at the latch | tracking slope |
|---|---|---|---|---|
| 16-waypoint head, es8 | 15 Hz | 2/20 | +119 | +1.5..+5.1 |
| **4-waypoint head, es4 (whole chunk)** | 8 Hz | **2/20** | **+92 (the session's lowest)** | +3.1..+3.7 |
| 4-waypoint head, es2 | 15 Hz | 0/20 | +107 | +2.7..+3.7 |

The short chunk buys the **vertical**: `dz` +92 against +103..+119 for the
16-waypoint head (an 11-27 mm improvement, the closest to the 70 mm seat the
session has measured), but the count is the same 2/20 and the post-close hold is
still world-static (+3.1..+3.7 mm/frame against the demos' -0.095).

**The session's best direct-loop configuration** (all measured, all default-off):
the shipped camera + the 64-px foveal crop + the in-band pre-aligned anchor (51) +
the same-camera DAgger store (40) + the lift labels + the phase gate + the family
start + the ramp dy 0.014 + the 4-waypoint head executed whole - **2/20 = 10 %**
(a direction; the WS-4.2 scale is ~40 per arm), against the scripted line's 8/10.

**What separates the two, measured**: the scripted line's 120 Hz **position-only**
catch-up re-aims at the measured fruit plus a lead **with a free wrist** and
reconfigures out of the j3-limit pose; the policy's 7-joint chunk commands the
wrist too, so it cannot. The one action-space form not yet tried is the learned
analogue: a **free-wrist Cartesian target** (`FRUIT_ACTION=jaw` with
`hold_quaternion=None` - the current jaw path *holds* the captured attitude, which
removes exactly the freedom the scripted solver uses).

## 42. The free-wrist Cartesian action: implemented, first read 1/8, and the latch does not fire

Built the action form the scripted catch-up actually uses: a **4-D jaw target**
`[x, y, z, finger]` applied through a **position-only IK with the wrist free**
(`FRUIT_ACTION=jaw` + `FRUIT_ACTION_FREE_WRIST=1`; the jaw path otherwise holds the
captured attitude, which removes exactly the freedom the solver uses). The 4-D
seed is `logs/p145/make_cart_seed.py` on `p145_tcp` (50 episodes, the jaw
recorded, the shipped camera, in-band 0.22-0.363, the wait-at-x start) - a
same-camera, same-start store; trained 60 epochs (weighted 0.0148).

A real integration defect surfaced and was fixed: the env's `action_mode` guard
knew `dq`/`rel`/`posvel` but **not `jaw`/`tcp`**, so a jaw artifact was refused at
construction (`action_mode='jaw' but FRUIT_ACTION resolves to ''`).

First cell (8 episodes, seed 77, the 4-waypoint head, the crop, the family start):
**1 grasp** (orange, 24 mm), gaps 11/55/59/24/107/6/103/51 - and **no `[close]`
latch at all**, i.e. the jaw action's along-belt error never reaches the 0.014 m
trigger (the joint arms latch 24-28 of 30). So the free wrist buys the vertical
reconfiguration the catch-up has, but the position-action approach is coarser
along the belt - the two forms are complementary, not one replacing the other:
the joint action times the catch (the latch), the jaw action reconfigures (the
descent). The named composition is a **hybrid action** (the joint 7-D for the
approach and the latch, the free-wrist jaw 4-D for the descent's last 2-5 cm),
which is a model head change (9-D + 4-D channels) rather than a runtime switch.

## 43. The two-model hybrid: mechanically sound, the dz improves, the count does not

`FRUIT_POLICY_CKPT2=<jaw head>` selects the free-wrist jaw head for the 60 ticks
after the latch and the joint head everywhere else (the two checkpoints share the
26-D proprio; the second runner gets its own frame buffer and reset - two
integration defects found and fixed: the second runner's `_frames` was never
pushed and its `phase_gate` was not inherited).

Cell (8 episodes, seed 77, the joint head `p171_tail`, the jaw head
`p169_freewrist`, the 4-waypoint horizon, the crop):

| measure | joint only | **hybrid** |
|---|---|---|
| `dz` at the latch | +92..+119 | **+58..+136 (p50 +114, two at +58/+72)** |
| tracking slope | +3.1..+3.7 | +3.8 |
| grasp | 2/20 | **0/8** |

So the jaw phase does move the hand toward the seat (two latches within 12 mm of
the 70 mm seat, the closest of the session), but the **post-close hold stays
world-static** and no attempt places. The reason is the one the record has measured
repeatedly: the jaw head was trained on `p145_tcp`'s *scripted* states, and the
joint head's latch state is out of its distribution - the switch changes the
action's *form* but not the model's *state coverage*.

**The honest end-point of the pure-learning lane on this tree**: the best direct
configuration (the shipped camera + the 64-px crop + the in-band anchor + the
same-camera DAgger + the lift labels + the family start + the ramp dy 0.014 + the
4-waypoint contact head) reads **2/20 = 10 %** against the scripted line's 8/10;
the measured separators are, in order, the **initial-state/band coverage** (fixed
by the crop + the anchor + the family start), the **close timing** (fixed by the
ramp's own dy), and the **contact-phase feedback** - the scripted line's 120 Hz
free-wrist position-only catch-up, which no 8-15 Hz chunked model reproduces and
which the two-model hybrid only half-approximates. The remaining build that could
still be argued is a **single 12-D head** trained jointly on both action groups
(the joint 7-D + the jaw 4-D) on one state distribution; everything cheaper has
been measured.

## 44. The per-tick contact servo: the alignment term converts (2/8 -> 5/8), and the place becomes the frontier

The P172 probe put numbers on the contact phase: the sampler's own spread at a
fixed close-start state is **18.4 mm** TCP-equivalent (p90 31.3), the mean's error
against the label is **24.4 mm**, and the belt travels **32 mm** per 16-tick
decision. So half the error is variance. Two variance levers were measured and are
**nulls**: `FRUIT_POLICY_GDP=1 GDP_K=4` (min-OoD selection of 4 candidates) reads
1/8 and `FRUIT_POLICY_ENSEMBLE_K=4` (mean of 4 draws) reads 1/8, both against 1/8
for the same-batch control, with `dz` unmoved (+100..+111). Averaging cannot fix a
**bias**.

**The bias has a location, and it is not the last centimetre.** The `[servo]` row's
own geometry (`d = tcp - aim`) decomposes the latch state: the vertical was already
within 13 mm of the seat while the **lateral was 75-86 mm** - the shipped ramp
latches on a *one-dimensional* criterion (the jaw's y within `FRUIT_CLOSE_RAMP_DY`
= 14 mm of the fruit's y) so the fingers close while the hand is 8 cm to the side of
the fruit. That is why the model's approach held the station's x (P145 §40's "the
jaw holds x = 0.28 while the fruit is at 0.20-0.36") and still latched.

**The build** (`FRUIT_CONTACT_SERVO=1`, default off): inside the contact window the
arm's command is re-derived **every tick** from the *perceived* fruit (the P135/P145
tracker's `predict_at`, the same estimator that feeds the goal) and applied with one
position-only differential-IK step (`hold_quaternion = None`, the scripted catch-up's
form); the committed ramp still owns the finger and is **gated on the aim being
reached** (so it cannot close on air); the servo **arms 0.20 m upstream** because a
~1 mm/tick wrist needs the correction to start before the fruit is at the station.
The aim is **frozen** when the tracker is older than `FRUIT_PERCEPTION_COAST_S` -
without that guard the aim locked onto the hand and ran to x = 0.05 (off the belt),
carrying the payload out of the lane (`fruit fell off the line`).

| measure | control (3 cells) | **servo** |
|---|---|---|
| `[close] xy` | 83 / 86 / 104 mm median | **17 / 20 mm median, max 21-24** |
| `[close] dz` | +99..+122 (median +111) | **+70..+81** (seed 101 median **+70** = the seat) |
| grasp, seed 77 / 8 | **2/8** | **5/8** |
| grasp, seed 101 / 8 | (not run) | 1/8 |

So the term the record called "the contact-phase feedback" is worth **+3 grasps of
8 at seed 77** and the latch geometry is fixed by a 4-5x reduction in the lateral
error. **Honest scope**: this is a *hierarchical* composition, not a pure
end-to-end policy - the model's phase gate decides *when* the contact phase begins
and the ramp decides the close, while a geometric servo on the *perceived* target
serves the aim. It contains no handover, no external trigger and no truth read, but
it also does not pretend that a 7-15 Hz chunk owns the last centimetres.

**Two harness defects were found by it, and both were suppressing the lane's
numbers.** (a) `--horizon 900` (7.5 s) is **shorter than the scripted pick+place**
(12-15 s), so every episode ended mid-carry: the session's "0 placed" was partly a
budget artefact, not a policy failure. (b) The horizon note read
`timeout: no grasp within 900 ticks` on episodes with `grasped=True`; it now reads
`timeout: horizon reached while carrying (...)` when the payload rose off the belt,
and keeps the shipped key otherwise (so no ledger's class set moves on the old
behaviour).

**The frontier has therefore moved to the place.** At `--horizon 2000` a grasped
payload is held and **never placed**: 2 of 8 attempts ran 1700 ticks while carrying
and the `[cmd]` trace shows the arm oscillating in the pick area (j1 -0.98..-1.56
with the measured pose lagging) or collapsing, never transiting to a bin. Two
structural candidates are named, both measured in the design rather than assumed:
the **64-px foveal crop** (which is what fixed the approach) removes the output bins
from the view; and the **goal is the fruit's position**, which is degenerate once
the fruit is in the hand (the demos' `FRUIT_TRAIN_GOAL=moving` rebuild follows the
fruit, so the place phase is conditioned on "the fruit is here"). The next cell is a
phase-dependent view (`crop` for the approach/contact, the wide frame for the place)
with the goal's destination channel or the bin's own visual cue.

## 45. The place, measured in pieces: the transit is predicted, the carry and the release are not

With the contact servo converting the grasp (P173), the place became the frontier. It
was instrumented two ways - offline (`logs/p145/place_fit.py`: the model's chunk
against the label at *carrying/transiting* windows) and in the loop (two new
reporting fields on the episode row, `final=` and `fing=`).

**Offline, the model does predict the transit.** At 20 carrying/transit windows the
first-step error is **48.4 mm** TCP-equivalent (p90 138) and the predicted travel over
the chunk is **0.91x** the label's, with **0 %** of windows predicting "hold". So the
failure is per-step *pose accuracy*, not a missing place motion.

**The phase-dependent view is a measured negative.** The hypothesis was that the
64-px crop (which fixed the approach) removes the output bins from the place's view.
`FRUIT_IMAGE_FOVEA_PHASE=1` crops the pre-close frames and feeds the wide frame once
the label's finger is closed (the env switches on its own latch; the phase is already
in the router's conditioning). Retrained on the same recipe: the offline place error
**rises 48.4 -> 68.7 mm** (the travel ratio goes 0.91 -> 0.99, i.e. it moves *more*
and further off), and in the loop the payloads end **on the floor** (z 0.90-0.92 at
x 0.04-0.40) against the control's place-side positions. **Not adopted**, default off.
The build did expose a real defect: the wide frame's depth carries `inf` where the
raycast missed (**26 %** of `p169_demo_all`'s pixels), and the wide path resampled
before clipping, so `inf - inf` produced **NaN** in the encoder input. Sanitised
before the resample **on the phase path only**, so the shipped wide path stays
byte-identical for the models trained on it.

**In the loop, with the servo, the arm reaches the place's neighbourhood and never
releases.** Four of eight attempts carried the payload to `(0.51, -0.30..-0.72,
1.19)` - the -Y output belt's own x and low place height - but `on_out=0` on all
eight, and the **finger at finalize is 0.025-0.030 (closed) on every episode**: the
model never emits the release. What it holds, it either keeps in the pinch or loses
to the closed loaded-slide class (`logs/p42/SIM_LIMIT.md`).

**So the end-to-end loop decomposes, each term with its own instrument:**

| term | state | instrument |
|---|---|---|
| approach / acquisition | **fixed** (crop + family start + band anchor) | `gap_min`, the close latch's xy |
| contact (the latch + the seat) | **fixed** (P173 servo) | `[close] xy 17 mm`, `dz +70..+81` |
| place transit | **reached within ~±20 cm** of a 25 cm belt | `final=`, the offline place fit |
| carry (holding the payload) | **open** - the closed loaded slide | the payload leaves the closed pinch |
| release | **open** - never emitted | `fing` at finalize 0.025-0.030 |

The two open terms are both **tick-level** (a slip grows over tens of ticks; a release
is a commanded ramp), and a 7.5 Hz chunk that must predict 32 mm of motion per decision
with a 30 mm error (P172) cannot own them. That is the lane's honest boundary, and it
names the one remaining *learned* build: a **per-tick controller** trained on 120 Hz
demonstration states (an architecture change - the demos are recorded at 30 Hz, so it
also needs a 120 Hz store), rather than another chunk, knob or store. The alternative
is the two hardware sanctions in `logs/p42/SIM_LIMIT.md`.

## 46. The defect behind the place: no demonstration in the project contains a release

The loop's last readout was the finger **0.025-0.030 at finalize on every episode**
(P173b): the model never opens. `logs/p145/release_fit.py` was written to ask whether
that is a fit problem or a labelling one, and it returned the sharper answer - **there
are no release windows to fit**:

| store | episodes | frames p50 | last-frame finger | episodes ending open |
|---|---|---|---|---|
| `demos_v11` | 50 | 200 (7.9 s) | 0.0246 | **0** |
| `demos_v12` | 158 | 209 (8.5 s) | 0.0221 | **0** |
| `v12d_s02` | 158 | 209 (8.5 s) | 0.0221 | **0** |
| `p146_anchor_all` | 51 | 195 (6.5 s) | 0.0238 | **0** |
| `p169_demo_all` | 112 | 196 (6.5 s) | 0.0238 | **0** |
| `p145_dagger_wait` | 40 | 126 (4.2 s) | 0.0279 | 4 (failed attempts) |

Every stored episode ends with the finger **closed**; the finger's maximum (0.044) is
the *start* of the episode. **366 demonstrations, zero releases.**

**The mechanism is one missing call.** `_record` samples the recorder at the 30 Hz
decimation and is wired into the approach, the close and the place; the release's
finger ramp - `min_jerk_ramp(fingers, arm.OPEN, 16)` at the end of the place - runs
`_step_sim(1)` in a loop **without** it. The stores end 0.9-1.0 s before the attempt
does (7.9-8.5 s stored against 9.0-9.4 s per attempt), which is exactly the release
block (the 16-step finger ramp x2-3 ticks per step, the pad ramp, the dwell).

**Consequence, and it is the honest explanation of the whole place series**: no
checkpoint in this project - including `moe_v13s` - has ever seen a release, so the
place could not be learned from these stores, and that is why the recollections,
DAgger rounds, action forms and stores never moved the place.

**The fix** is one guarded call inside the release's finger ramp
(`_record(self._action9(self._commanded_arm(arm), arm, float(value)))`, behind
`if self.recorder is not None and self.recorder.recording`), so a run without a
recorder is untouched - the scripted acceptance does not attach one. Verified on a
2-episode smoke store: the last-frame finger now reads **0.0439 / 0.0440** with an
open tail (against 0/366 before). A top-up store (`datasets/p173_release`) and a
fine-tune are the next cell; every store recorded before this fix is a
no-release store.

## 47. A release top-up store and a release-weighted objective: the signal exists, the loop still does not release

The P173c fix was verified end to end. A top-up collection (`FRUIT_EPISODES=16`,
over-run to **24 successful episodes** of 48 attempts, `datasets/p173_release`) now
ends with the finger **open** on every episode, and merged with `p146_anchor_all` it
gives `datasets/p173_all` (**75 episodes**). A release objective was added to the
fine-tune - `--release-weight / --release-lead 40 / --release-tail 20`, weighting the
windows around the recorded release's **open tail** (read from the end, so a
mid-episode re-grasp reopen is not mistaken for a release):
`release_start_frames` finds **24 of 75** episodes with a tail, and the band holds
**947 of 14 968** base windows (**6.3 %**).

Fine-tune `p174_fasthead` -> **`p176_release`** (30 epochs, weighted 0.0245, router
0.989, `demo_val` 0.0177). Cell (8 episodes x seeds 77/101, the servo, horizon 2000):

- **0/16 placed**;
- the finger at finalize is **0.019-0.044**, mostly **0.024-0.030** (closed);
- the payloads end at the belt's far end on the floor (`y -0.87..-0.91`, `z
  0.90-0.92`) - either the un-grasped fruit's own resting place or a payload lost in
  the carry, never a bin.

**Read it as two terms, not one.** The release signal is now in the data but 24
episodes of a 2-4-frame tail is **6 % of the windows**, and the loop's place transit
carries **+-20 cm** of scatter (P173b: x 0.51, y -0.30..-0.72 against a 25 cm belt) -
a payload released 20 cm beside the belt still misses it. So the two are
**simultaneously** required, and neither is a knob:

1. a **full recollection with the recorder fix** - every store recorded before P173c
   is a no-release store (0 of 366 episodes ended open), so the project's
   demonstration corpus has to be re-recorded before the place can be learned at all;
2. the place's **transit accuracy** (48 mm per decision offline), which is the same
   class as the contact phase's and has the same answer - a measured-target servo or
   a per-tick learned controller (P173's boundary).

**Durable outcomes of this round**: the recorder samples the release; the
release-weighted objective exists and is opt-in; and a store's *finger tail* is now a
provenance read - an episode that ends closed is a pre-P173c store.

## 48. The full recollection with the recorder fix: 60 episodes, all ending open - and the loop still does not release

The P173c fix was taken to a full collection: two shards, 48 attempts each, **60
successful episodes** (24 + 36) into `datasets/p174_s1` / `p174_s2`, merged as
`p174_all`. Every episode now **ends with the finger open** (24/24 and 36/36 of the
open-tail read) and is **8.5-8.6 s** long against the 7.9-8.5 s of the pre-fix
stores - the extra half second is the release ramp plus the settle, both newly
sampled.

Fine-tune `p174_fasthead` -> **`p177_full`** on `p174_all` with the release objective
(`--release-weight 20 --release-lead 40 --release-tail 20`, 40 epochs, weighted
0.0293, router 0.992, `demo_val` 0.0355). **Offline the model now emits the
release**: at the release window it predicts **0.0393** against the label's 0.0400
(`p176`: 0.0357).

**In the loop it still does not.** Cell (8 episodes x seeds 77/101, the contact
servo, horizon 2000): **0/16 placed**; `fing` at finalize **0.012-0.044**, mostly
**0.021-0.030** (closed); the grasped payloads end at `z 1.19-1.32` (still in the
hand) or on the floor, never on a belt. The contact phase is unaffected and stays
good: `[close] xy` **12-22 mm**, `dz +59..+84` on all six latches.

**The phase gate is not the blocker.** Re-run with `FRUIT_POLICY_PHASE` unset (the
model's own router decides the skill) reads **3 grasped / 0 placed** with the finger
still closed at finalize - so neither the perception gate nor the router is holding
the finger shut.

**Verdict.** The release is now *in the data*, *in the model's offline output*, and
*not in its closed-loop output*, because the loop's carry/place states never match
the demonstrations': the transit carries **48 mm of error per decision** over a
~0.9 m move (P173b's `final` scatter: x 0.51, y -0.30..-0.72 against a 25 cm belt),
so the hand never occupies the state the release label belongs to. The place is a
**closed-loop accuracy** term of exactly the class the contact phase had before
P173's servo - and the same two answers apply to it: a measured-target loop (the
destination is the task's own `output_place_xy`, not truth about the fruit) or a
per-tick learned controller trained on 120 Hz states. Both reduce the *policy* to
the decision layer for the place, which is why this is stated as a decision for the
owner rather than slipped in as another knob.

**Durable results of the round**: the recorder samples the release (and the settle),
the stores now carry it, a store's finger tail is a provenance read, and the
release-weighted objective exists.

## 49. The place as a measured-target loop: the trajectory and the release work; the cells do not place because the grasp does not hold

Step 3 of the P174 plan. Two candidates were on the table - a measured-target loop to
the destination, or a per-tick learned controller. The cheapest learned variant was
measured first and is **not** it: a **horizon-1** model (`p178_h1`, one 30 Hz
waypoint per decision, `--execute-steps 1 --action-hold 4`) removes the 32 mm
prediction requirement entirely and still reads **2/8 grasped, 0/8 placed** with
`fing` closed - the contact is unaffected (`[close] dz` median **+70**, xy 18 mm).

So the place was built as a measured-target loop (`FRUIT_PLACE_SERVO=1`, default
off), the same form as the contact servo: lift clear (`belt_top + 0.30`), transit
over the destination's own pose (`task.jaw_target("place{bin}")` - a pose the cell
knows, not truth about the fruit), lower by `FRUIT_PLACE_SERVO_DROP` (0.10), and
open the pads on a 40-tick ramp. Each phase advances on a **measured** error, not a
clock.

**Mechanically it works, and this is the session's first working place trajectory**
(`[pservo]` rows, seed 77):

| tick | phase | aim | jaw | error |
|---|---|---|---|---|
| 444 | 0 lift | current xy, z 1.470 | z 1.321 | 149 mm |
| 492 | 0 lift | current xy, z 1.470 | z 1.433 | 37 mm |
| 540 | 1 transit | (0.430, 0.500, 1.470) | (0.263, 0.412, 1.424) | far 188 mm |
| 588 | 1 transit | as above | (0.399, 0.493, 1.439) | far **32 mm** |
| 636 | 1 at place | (0.430, 0.500, 1.430) | (0.429, 0.491, 1.439) | far **9 mm** |

and the release ramp runs **0.0250 -> 0.0421 -> 0.0440** on the last two samples -
i.e. the hand arrives **within 9 mm** of the +Y bin's place point and opens.

**The cells still do not place**: 0/4, 0/8 and 0/4 at seed 77/101, because the grasp
yields first - 1-2 of 8 grasp and the payload leaves the pads during the carry (the
`logs/p42/SIM_LIMIT.md` closed loaded-slide class), so the servo transits an empty or
half-held hand. Two further defects the cell exposed were fixed:

- the servo must not run on a **miss** (it drove an empty hand through the pick
  station and knocked the fruit off: `final=(-0.03, +0.09, 0.92)`, x outside the
  belt); it now requires the payload to be **within 12 cm of the jaw** before it
  takes the arm;
- the place was **scored at the wrong moment**: a payload put on an output belt is
  carried away and despawned before `_finalize`, so `on_output_belt(final)` reads
  False on a good place (`final=(+63.0, 0.0, -50.0)` is the spawner's park slot).
  The **release event** (the finger's closed -> open transition) is now a sticky
  score sampled from the position `_episode_events` already reads. Built but not yet
  exercised by a cell, because no cell has yet placed a payload.

**Verdict on step 3**: the place's *control* is solved (9 mm and a release ramp), and
its *score* is now read at the right moment; what remains is the **grasp's hold**,
which is the class `logs/p42/SIM_LIMIT.md` closes - not a place, goal, phase, view,
horizon, re-plan-rate or store problem. That is where the end-to-end cell now
stands: an approach, a contact and a place that all work, gated by a carry that
holds 1-2 attempts in 8.

**Gates on the final tree of the round** (`d9a7f48`): `scripts/selfcheck.sh`
**PASS (0 failures, 1 skipped)**; `scripts/accept.sh` **fingerprint: matches
`configs/motion_reference.json`** with **`190: PASS`** (the shipped two-line
scenario untouched); `scripts/accept_policy.sh` twice - **5/10 (50 %, FAIL on the
rate only, 5 grip losses)** and **7/10 (70 %, PASS)** - two samples of the
non-reproducible hybrid loop, `moe_v12` on the fixed pre-v9 supply, i.e. the bottom
and the middle of its recorded **5-8/10** spread; the canary builds its own
`FruitSpawner`/`PickAndPlaceTask` (`scripts/60_eval_policy.py`) and never constructs
`SortingRLEnv`, and the round's `tasks.py` change is behind
`if self.recorder is not None and self.recorder.recording`, so it cannot read any of
it - the 50 % sample is the loop's own draw, and the pair is the honest statement.
`configs/motion_reference.json` / `..._twoline.json` = **`30fb99f8`** and
`..._single.json` = **`8952c320`** stand; every new knob defaults off.

## 50. The hardware answer: the end-to-end cell needs a ~60 N clamp

The owner authorised the hardware route. The record's own ranking puts the clamp
force first: P41 measured that the delivered pinch **follows the cap** (4.4 -> 9.75-9.9
N when the profile was fixed), and P76's ladder measured the mechanism - the pads are
**back-driven to their open stop** below ~30 N and the pry is **deleted at 60 N**
(0/26 pried, 0/26 escaped on that cell). P120's null was the **global cap on the
scripted two-line**, where the count is dominated by classes the cap cannot touch;
this phase asks the same question on the **direct end-to-end cell**, where the
carry's hold *is* the binding term.

**The build** (`FRUIT_FINGER_MAXFORCE_DIRECT=<N>`, default 0 = the shipped build
cap): a runtime write of the active arm's `joint1` drive cap for the whole attempt,
**written by the task** (`attempt_finger_cap` / `..._restore`, the scoped carry caps'
own live-view path) so the environment never touches a drive - the P78/P79
architectural pin holds. Direct presentation only, so the scripted acceptance, the
collector and the hybrid canary cannot read it and no reference is owed. The
`[drive]` row proves it per attempt: **`left attempt finger cap 10.00 -> 60.00 N`**
and the restore at finalize.

**The cell** (the best stack of this round: `p177_full`, the contact servo, the place
servo, `FRUIT_SCORE_ENDPOINT=release` - which is the honest scorer here, because a
placed payload is carried off the belt before `_finalize`), 8 episodes x **4 seeds**
(77/101/202/404), cap 10 N against 60 N, same batch, same knobs:

| seed | 10 N | **60 N** |
|---|---|---|
| 77 | 1/8 | **5/8** |
| 101 | 1/8 | 1/8 |
| 202 | 0/8 | 1/8 |
| 404 | 0/8 | 1/8 |
| **pooled** | **2/32 = 6.3 %** | **8/32 = 25.0 %** |

and the grasp **survives the carry** on **6/32 (19 %)** at 10 N against **14/32
(44 %)** at 60 N. **3 of 4 seeds better, 1 tied, none worse**; Fisher two-sided
**p = 0.082** on the count and **p = 0.058** on the survival; the sign test's ceiling
at N=4 is 0.0625, so the direction is as consistent as four seeds can show without a
larger one.

**What it means as a hardware requirement**: a real jaw must deliver **~55-60 N at
the contact** (the delivered pinch, not the cap - P41's law puts ~53-56 N at a 60 N
cap) for this payload class to survive the carry. At the shipped 10 N the end-to-end
cell places **6 %** of attempts; at 60 N, **25 %**, with the best seed at 5/8.

**Caveats, stated rather than implied**: (1) the **crush guard is not readable on
this interface** - the direct path has no `[carry]` rows without the primitive, the
same gap P120 recorded; the bound on the risk is P76's own 60 N row (the binding
3.6 cm strawberry at `sep@loss - dia` **+0.5 mm**, i.e. not crushed) and this sim has
no bruise model at all; (2) **8/32 against 2/32 is a direction, not a certificate** -
P93's power note puts 8.75 points at ~364 attempts/arm, and P120's replication after a
similar screen (66/80 vs 58/80) went null, which is exactly why this read is pooled
over four seeds with the mechanism named; (3) the 60 N write is a **specification
applied at runtime**, so it is not the same object as re-authoring the drive at build
time (that would owe both references and every store).

## 51. The new binding term is the right arm: 0 grasps in 31, and it is not the station

With the clamp fixed (P176: 8/32 placed, 14/32 grasped), the per-arm split of the
same cells names the next term: **right 0/31 grasps, left 21/35**. Every placement in
the round is the left arm. Four measurements narrow it:

1. **The latch is geometrically the same on both arms** (`[close]` rows): right
   `xy 14-16 mm`, `dz +66..+77`; left `xy 16-20`, `dz +68..+72`. So the acquisition
   timing and the seat are not it.
2. **The grasp station is not it.** The demonstrations the policy is trained on put
   the right station at **y = -0.10** while the direct environment grasps both arms
   at `cfg.pick_y` (0.00) - a 10 cm difference, five times the pads' slack for a 6 cm
   fruit (`datasets/p174_all` index: `right: -0.10` 31 episodes, `left: 0.0` 29).
   Tested with a caller-owned `grasp_station_dy` kwarg and an all-right instruction
   (`default => 1`): **0/6 at 0.00 and 0/6 at -0.10**. The kwarg was reverted
   (measured, not adopted).
3. **The same close command produces a different pad span on the two arms.** The new
   `[close-hold]` row (`FRUIT_CLOSE_RAMP_DIAG=1`, one row per attempt, the tick the
   ramp completes) reads `fing=0.0295` -> **`sep=69.1 mm` on the right** and
   **`77.4 mm` on the left**. Both are wider than the command's own 49 mm (the fruit
   blocks them), but the 8 mm disagreement is systematic: 69.1 mm is a 7.0 cm apple's
   own diameter (pads on the fruit), 77.4 mm is 9 mm clear of a 6.5-6.8 cm fruit.
4. **Same batch, same knobs, 3/3 against 0/3** (all-left vs all-right instruction, 60
   N, seed 101): left `g=3/3`, right `g=0/3`.

The finger mapping constants are **class-level** (`JAW_SEPARATION_OFFSET 0.010`,
`JAW_SEPARATION_PER_JOINT 2.0`, `FINGER_FACE_OFFSET 0.0`), so the arms cannot differ
in arithmetic - the difference must be in the finger bodies, the mimic joint, or the
`jaw_separation()` measure on a mirrored arm. That is the named next item, and it is
worth **44 % of the cell** (14 of the 32 episodes at 60 N are right-arm attempts).

**Shipped this phase**: the `[close] sep=` field (the measured span at the latch, one
read per attempt - a commanded grip that does not close the pads was otherwise
invisible) and the `[close-hold]` row (default off). Both are reporting only and the
direct path is the only one that prints them.

## 52. The right arm closes on air: measured, and the finger law is identical on both arms

Two probes settle what P177 could only bound.

**1. The finger command -> pad span law is the same on both arms** (`logs/p145/
finger_probe.py`, no attempt loop: both arms built from the scene, one ladder of
commands, each held 40 ticks). Every rung reads `sep = 2*cmd + 0.010` to **0.00 mm**
on *both* arms - 98.00 / 90.00 / 80.00 / 70.00 / 60.00 / 50.00 / 40.00 / 30.00 mm - and
the two measured joint positions follow the command exactly (`j1 = j2 = cmd`). At the
direct cell's own `cmd=0.0295`: **left 69.00 mm, right 69.00 mm, delta 0.00**. So the
P177 "69.1 vs 77.4 mm" difference is **not** a mapping or mirroring defect: 69 mm is
the command's own span (nothing between the pads) and 77 mm is *blocked*.

**2. In the loop, the right closes on air each time** (`[close-hold]`, the tick the
ramp completes, with the tactile read the project already owns):

| arm | `sep` at the ramp's end | tactile | spans |
|---|---|---|---|
| **left** | 76.9-77.6 mm (blocked > the 69 mm command) | **F = 50.5-57.3 N, n = 2** | 4/4, 2/2 grasped |
| **right** | 69.1 mm (exactly the command) | **F = 0.00 N, n = 0** | 0/4, 1/2 grasped |

So on the right the fruit is **not between the pads** at the close, while the latch
row reads the same geometry on both arms (`xy 14-16 mm`, `dz +66..+77`, `dx -10..+5`
against the left's `xy 16-20`, `dz +68..+72`, `dx -13..-15`).

**What is left, and it is per-arm**: the **jaw (closing) axis** at the close. Read on
the same row: right `(-0.91, -0.31, +0.27)`, left `(+0.91, -0.09, -0.39)`. Both are
"across the belt" in the x sense (the shipped attitude), but the right's axis is
tilted **+16 deg up** and **-18 deg along the belt** against the left's **-23 deg
down** and **-5 deg** - i.e. the pads' *faces* are rolled in opposite directions, and
with a 15 mm centre offset and a 67-87 mm fruit only 12-40 % of the payload's height
sits inside the 80.5 mm plate. That is the same class as P63's finding (an
arm-common ~25 deg attitude residual with an **arm-specific azimuth**), now read at
the close on the direct interface.

**Named next check** (one probe, no attempt loop): the plates' overlap with the
payload along the tool axis at the latch, per arm - the `[close]` row's `dz` and the
plate's distal plane (80.5 mm below the jaw centre) already give it arithmetically,
and the discriminating cell is a `dz` ladder on the right arm alone.

**Shipped**: the `[close-hold]` row now also carries `F=`, `n=` and `jax=` (default
off, `FRUIT_CLOSE_RAMP_DIAG=1`), and `[close]` carries the measured `sep=`. Both are
reporting only.

## 53. The right arm's close is not perception, and the pads stop 20 mm short of their own command

The P178 bench switch `FRUIT_CONTACT_SERVO_SOURCE=truth` aims the contact servo at
the **rigid body** instead of the estimator (never shipped; default `percept`). On the
all-right instruction, three episodes at `truth`: `sep=69.1 mm`, **`F=0.00 N, n=0`**,
`jax=(-0.93,-0.25,+0.25)` - **identical to the perception arm**. So the right arm's
failure is **not** the tracker, the camera or the goal.

With perception, the mapping and the station all ruled out, the remaining read is the
close's *own* numbers, and they disagree with each other:

- the command is `grip = 0.0295`, i.e. a **49 mm** target span
  (`gripper_value_for_separation`'s inverse: `2*0.0295 + 0.010`), derived from
  `pinch_width(sample, quat) * 0.98` at the latch;
- at the ramp's end (60 ticks = 0.5 s) the measured span is **69.1 mm** - **20 mm
  short of the target** - with **no force and no contacts**;
- the **left** arm, the same command, is **blocked at 76.9-77.6 mm** with **F = 50-57 N
  over 2 contacts**.

Two readings fit, and the single `[close-hold]` row cannot separate them: either (a)
the right's ramp **stalls part-way** (a 49 mm travel in 60 ticks = 98 mm/s under load,
which the drive may not deliver) and the tactile reads zero because the pads are still
a couple of millimetres short; or (b) `pinch_width` returns a *smaller* chord on the
right because its jaw axis is tilted **+16 deg up** against the left's **-23 deg down**
(the P178 axis read), so the commanded gap is wrong in the other direction and the
pads meet at 69 mm with the fruit elsewhere.

The discriminating instrument is one time series, not one row: `[close-hold]` printed
every 4 ticks through the ramp on each arm (the row exists, it is printed once). If the
right's span is still moving at the ramp's end, it is (a) - and the fix is the close's
own clock or a contact dwell after the ramp (the scripted line's 200-tick catch-up is
the measured precedent). If it is flat at 69 mm, it is (b) - and the fix is
`pinch_width`'s attitude term.

## 54. The close's squeeze scale: the geometry says it should matter, the cell says 1/4

`[close-ramp]` (the per-4-tick series P178 asked for) settles the (a)/(b) question in
one cell each arm (all-right and all-left instruction, 60 N, seed 101):

| tick | right `sep` (F) | left `sep` (F) |
|---|---|---|
| i=4 | 98.0 mm (0.00 N) | 97.8 mm (1.75 N, n=1) |
| i=20 | 93.1 (0.00) | 93.1 (0.22) |
| i=36 | 79.9 (0.00) | 80.0 (0.90) |
| i=40 | 76.6 (0.00) | **77.5 (38.4 N, n=2)** |
| i=56 | **69.3 (0.00)** | **77.7 (49.8 N, n=2)** |

So the right's pads **follow their command exactly** (98 -> 69 mm, no force, no
contacts) and the left's **jam at 77.6 mm** with 50 N. Reading (a) - a stalled ramp -
is **refuted**; the pads on the right are not blocked, they simply have **nothing
between them**. The left's fruit is ~77.6 mm across at the contact height; the right's
67-70 mm apple is *not* between pads whose centre is 15 mm from its centre.

**The geometry that explains it, and the knob it implies.** Pads at `+-s` with the
payload offset `dy` along the belt touch a sphere of radius `r` only while
`s <= sqrt(r^2 - dy^2)`. The shipped close is `s = 0.98 r`, i.e. `dy <= 0.199 r` =
**6.8 mm** for a 34 mm radius - while the latch's measured `dy` is **8-18 mm** on both
arms. The larger fruits (the left's, r = 38.8) therefore touch (their `dy <= 0.239 r`)
and the smaller ones (the right's grade B/C stream, r = 34) do not, which is the whole
left/right asymmetry without any per-arm defect.

The knob existed but only the DAgger expert read it: the policy path's committed close
had `* 0.98` hardcoded (`rl_env.py:5083`). It now reads **`FRUIT_GRIPPER_SQUEEZE`**
(default 0.98 = the shipped expression byte for byte). Cell, all-right, 4 episodes
each: **0.98 -> 0/4, 0.90 -> 1/4, 0.92 -> 1/4**. A direction, not a fix - the
arithmetic predicts contact for `dy <= 0.436 r` (14.8 mm) at 0.90 and the measured
`dy` reaches 18.3 mm, so the scale cannot cover the tail on its own. **Not adopted**
for the default (the shipped 0.98 stands); the named next read is `dy` **conditioned on
the fruit's radius** (one census over the cells already on disk: `[close]` prints `xy`
and `dx`, so `dy` is `sqrt(xy^2 - dx^2)` and the radius is the episode's own diameter),
which says whether a *scale* is the right lever or the latch's `dy` window is.

## 55. The right arm is 3 % against the left's 61 % at the same fruit size - and the span measure itself is now suspect

A census over every cell on disk with both an outcome and a latch (`logs/p176`,
`p177`, `p179`; 120 outcomes, 110 latched) settles the arm question and, in doing
so, indicts the instrument:

| comparison | result |
|---|---|
| by arm | left **34/52 (65 %)**, right **2/68 (3 %)** |
| diameter, by arm | left p50 **6.1 cm**, right p50 **6.3 cm** (same class) |
| **size-matched, 6.0-7.0 cm** | left **14/23 (61 %)**, right **1/38 (3 %)** |
| by size band (both arms) | 0-4.5 cm 3/21, 4.5-5.5 4/6, 5.5-6.5 16/46, 6.5-9 13/47 |
| `dy/r` at the latch (the pads' geometric reach) | nothing below 0.199; 11 rows in (0.199, 0.30] at 36 %, 99 above at 32 % |

So it is **the arm, not the fruit class** - and the `dy/r` model, which P179 proposed,
is **flat** (36 % against 32 % across its two bands) and never predicts contact at the
shipped 0.98 scale, i.e. it explains why contact is hard but not why one arm converts.

**The two pad points say the measure is not the pad faces.** One row each, same
episode index (`[close-hold]`, now printing `pL=`, `pR=`, `fruit=`):

| arm | pL | pR | fruit centre | pinched |
|---|---|---|---|---|
| **left** | (0.162, 0.115, 1.285) | (0.232, 0.108, 1.254) | (0.167, 0.105, 1.205) | **56.8 N, n = 2** |
| **right** | (0.268, 0.085, 1.260) | (0.205, 0.064, 1.278) | (0.226, 0.059, 1.202) | 0.00 N, n = 0 |

The **left** holds the fruit with its centre **outside** the two reported points in x
(0.167 vs the 0.162-0.232 span), and the **right** misses with the fruit's centre
**between** them (0.226 in 0.205-0.268). That is only possible if
`jaw_positions()`/`jaw_separation()` trace the **finger link origins**, not the 61 x
84.9 mm pad plates - which the record has in fact suspected before (P64: "the jaw axis
was never printed, `tasks.py`'s `rot[:,1]` is free").

Consequence for the lane: every span-based inference taken through this measure -
including P178's "identical finger law" (self-consistent, but of the link origins) and
the `dy/r` reach model - describes the links, not the faces. **The next instrument must
read the pad plates** (the colliders, `tasks.pad_centre()` / the tactile pads) and
re-derive both the reach condition and the per-arm comparison from them. That is the
named next step, and it is cheap: one row with the two plate centres and the payload.

**Shipped**: `pL=`, `pR=`, `fruit=` on the `[close-hold]` row (default off,
`FRUIT_CLOSE_RAMP_DIAG=1`), reporting only.

### 55a. Correction (same day): the pad points *are* the face centres, so the observation stands but the mechanism is withdrawn

`kinematic_gripper.OpenArmHand` is explicit: `pad_centre()` **is** `arm.jaw_centre()`,
`pad_faces()` **is** `arm.jaw_positions()`, and the class carries
`pad_face_offset = 0.0` with the comment *"the OpenArm pads are at the finger link
origins; no thickness offset"*. So §55's "the measure traces the links, not the pad
faces" is **wrong as a mechanism and withdrawn**: the two reported points are the
centres of the two 61 x 84.9 mm plate faces.

The *observation* that made me doubt it stands and is explained by the plates being
**planes, not points**: a payload's centre can sit outside the segment between two face
centres in x and still be in contact with a plate (the left pinches at 56.8 N with its
centre 5 mm outside the 0.162-0.232 span), and it can sit *between* them and touch
nothing (the right misses with the centre at 0.226 inside 0.205-0.268). What decides
contact is the plate's **own extent** along the tool axis, and that is the read the
lane does not yet have: at the latch both arms put the face centres **65-67 mm above
the payload's centre** with the plate 84.9 mm long, so the overlap depends on the
pads' tilt - and the two arms' jaw axes are mirrored differently (`jax` z **-0.40**
left against **+0.27** right).

**Named next read** (one probe, no attempt loop): the plates' vertical extent and the
payload's overlap per arm, from the plate collider's own size and the face centre -
`p66/COLLIDER_READ.md` already holds the plate's dimensions, so this is arithmetic plus
one pose read.

## 56. The latch window is not the right arm's answer either (0.014 -> 0/4, 0.03 -> 1/4, 0.05 -> 1/4)

The mechanism the reach map suggests: R10-A's intercept map puts the right arm's usable
band at **y in [-0.10, 0.00]** and the left's at **[0.00, +0.10]**, so every fruit
crosses the left's band first and the right meets it **late** - and the committed ramp
latches at `FRUIT_CLOSE_RAMP_DY = 0.014`, **3.5x tighter than the demonstrations' own
`FRUIT_TRACK_START = 0.05`** ("the demos close when the fruit is within 0.05 m of the
jaw line"). If that were the term, a wider window would close the pads *before* the
fruit arrives on the right.

All-right instruction, 4 episodes each, 60 N, everything else shipped:

| `FRUIT_CLOSE_RAMP_DY` | grasped | success |
|---|---|---|
| 0.014 (shipped) | 0/4 | 0/4 |
| 0.030 | 1/4 | 0/4 |
| 0.050 (the demos' window) | 1/4 | 1/4 |

**Not adopted** (the shipped 0.014 stands). A direction of the same size as the squeeze
scale's, not a mechanism - so the right arm's 3 % has now had **six** candidates ruled
out: the clamp (60 N), the station (-0.10), the perception (truth-aim), the finger law
(identical), the squeeze scale (0.90/0.92), and the latch window (0.03/0.05). Each
moves at most 0 -> 1 of 4, which is the branch noise this project has measured
repeatedly at n=4.

**Where that leaves the cell**: left 34/52 (65 %), right 2/68 (3 %) at the same fruit
size - and the end-to-end cell as a whole **8/32 = 25 %** at 60 N against 2/32 = 6.3 %
at the shipped 10 N (P176). The right arm is the single largest unspent term (44 % of
the attempts) and the next instrument is the one named in 55a: the plate's vertical
overlap per arm from the plate collider's own size and the face centre, at the latch.

## 57. The right arm's answer: the contact servo's lead, measured against the pad plate's width

The instrument P55a asked for - the payload's offset resolved **in the tool axis** -
found it in one row. `[close-hold]` now prints `tax=` (the approach/tool axis),
`tilt=`, `dax=` (the payload's distance along that axis, against the plate's
**84.902 mm** length from the finger link origin) and `dlat=` (its lateral distance,
against the plate's **61.000 mm** width, half **30.5 mm**):

| arm | tilt | `dax` | **`dlat`** | contact |
|---|---|---|---|---|
| **right** | 24.7 deg | +60.8 mm | **33.5 mm** | **F = 0.00 N, n = 0** |
| **left** | 24.2 deg | +71.4 mm | **1.8 mm** | F = 57.3 N, n = 2 |

The tilt and the axial coverage are the **same** on both arms; the lateral offset is
**33.5 mm on the right against 1.8 mm on the left**, and the plate is 61 mm wide - so
the right's payload sits **3 mm past the plate's trailing edge** when the pads finish
closing. Decomposed, that offset is almost purely **-y** (`perp = (+10.2, -30.1,
-11.7) mm`): the right meets every fruit **late**, exactly as R10-A's band map says
(right `y in [-0.10, 0.00]`, left `[0.00, +0.10]`).

**The lever is the servo's own lead, and it moves `dlat` monotonically.** All-right
arm, 4 episodes per cell, 60 N:

| lead | `dlat` at the close | contact | grasped | success |
|---|---|---|---|---|
| 0.10 s (the shipped single value) | 33.5 mm | 0.00 N, n=0 | **0/4** (seed 202) | 0/4 |
| 0.15 s | 19.1 mm | 53.7 N, n=2 | **4/4** (seed 101) | 4/4 |
| 0.20 s | 6.6 mm | 60.0 N, n=2 | 4/4 (202), 2/4 (404) | 4/4, 2/4 |

Pooled **all-right at 0.20 s: 10/12 (83 %)** against **0-1/14 at 0.10 s** - the arm
that read 2/68 in the census, at three seeds including a fresh one.

**But one global lead cannot serve both arms**, and that is the confirmation rather
than a complication - on the *mixed* supply (same seeds 77/101):

| lead | left | right | pooled |
|---|---|---|---|
| 0.10 (shipped) | **6/10** | 0/6 | 6/16 |
| 0.20 | 3/11 | **3/5** | 6/16 |
| **per arm: left 0.10, right 0.20** | **5/11** (grasped **10/11**) | **3/5** | **8/16 = 50 %** |

So the lead is now a **per-arm** knob (`FRUIT_CONTACT_SERVO_LEAD_RIGHT`, default = the
single value, so unset is the shipped path): the left's reach band is upstream and
0.10 s already centres it (`dlat` 1.8 mm), the right's is downstream and needs 0.20 s.
The cell reads **8/16 = 50 %** on the two shared seeds, against 6/16 at either global
value and 6/16 at P176's 10 N - and with the right converted, the *left* is now the
term that fails at the **place** (grasped 10/11, placed 5/11), not at the grasp.

## 58. The left arm's residual is the meas place transit: the hold grows mid-flight (72 -> 96 mm)

The `hold=` read (how far the payload is from the jaw centre; a seat is 70-80 mm, a
lost payload grows without bound) is now on both servo rows. All-left, 60 N, the
per-arm lead, 4 episodes (2 placed, 2 not):

| ep | fruit | seat phase (`hold`) | place transit (`hold`) | outcome |
|---|---|---|---|---|
| 0 | apple | 250 -> 86 -> **70-71** | 71 flat to t=708, then **87** (release) | **placed** |
| 1 | tomato | 123 -> 70 -> **68** | 68 flat to the end of the trace | not placed |
| 2 | apple | 246 -> 82 -> **69** | 69 flat to t=688, then **89** (release) | **placed** |
| 3 | tomato | 223 -> 108 -> **73-72** | 72 at t=560, **96** at t=600 | not placed |

So the left's grasp is solid (**10/11** in the per-arm cell) and the loss happens in
the **place transit**, on the two tomatoes: one keeps the payload to the end of the
servo trace and fails later, the other's hold **grows 72 -> 96 mm at t=600** - a
loaded slide inside the transit, at a 60 N clamp and a 50-57 N measured pinch.

That is `logs/p42/SIM_LIMIT.md`'s class on the *place* leg again, now with a per-tick
handle on it: the same row that says where the payload is also says that the transit
is where it goes. The two named levers, both already in the tree: the place servo's
own speed (the transit runs ~300 ticks at the jerk-limited IK step) and the clamp
(already at 60 N, and P76's ladder put the pry's deletion at that cap on the *scripted*
line - the soft-fruit class survives it here).

**Not claimed**: n = 4, one seed. The instrument is the result: `hold=` turns "grasped
but not placed" into a timestamp and a leg.

## 59. The place transit's speed limit: the left's residual converts, 8/16 -> 12/16

The `hold=` trace (P183) put the left's loss inside the place transit, and the transit
was the direct aim: the position-only IK step at its own clip carries the payload
~0.6 m in ~300 ticks (0.24 m/s at the jaw). `FRUIT_PLACE_SERVO_VMAX=<m/s>` bounds the
**reference** the arm follows (the aim advances at most `v*dt` per tick; the IK still
does one step per tick, so nothing else in the loop changes). Default 0 = the shipped
direct aim.

All-left, 8 episodes, 60 N, the per-arm lead:

| place transit | grasped | placed | pservo ticks |
|---|---|---|---|
| shipped direct aim | 6/8 | **5/8** | 591 |
| `VMAX=0.15` m/s | 8/8 | **8/8** | 1478 |

and on the shipped **mixed** supply, the same two seeds as P182's 50 %:

| config | left | right | **pooled placed** |
|---|---|---|---|
| per-arm lead, shipped aim | s5/11 (g10/11) | s3/5 (g3/5) | **8/16 = 50 %** |
| **+ `VMAX=0.15`** | **s9/11 (g10/11)** | s3/5 (g3/5) | **12/16 = 75 %** |

The left converts (**5/11 -> 9/11**) and the right is unchanged (3/5), exactly as the
per-arm diagnosis predicts - the right's place already worked, so the speed limit can
only help the arm that was sliding.

**The cell as a whole, in order of what each phase cost**: 6.3 % at the shipped 10 N
(P176's 10 N arm) -> 25 % at 60 N (P176) -> 50 % with the per-arm servo lead (P182) ->
**75 % with the place transit's speed limit** (n = 16, two seeds, the same stack:
`p177_full` + the contact servo + the place servo + the release endpoint).

**Caveats**: n = 16 over two seeds; the throughput price is real and measured (the
transit takes 2.5x the ticks, 1478 vs 591 rows, so the attempt is longer and the
horizon has to be raised to 2600); and `FRUIT_PLACE_SERVO_LIFT` (0.30 m, P66's height
ladder's motivation) is built but **not yet measured**.

**Not claimed**: a rate - two seeds at n=8 per arm; the next confirmation is the same
cell at two fresh seeds.

### 59a. Four seeds: 20/32 = 62.5 %, every seed at or above 50 %

The same cell at two **fresh** seeds (202, 404) plus the two already run:

| seed | placed |  |
|---|---|---|
| 77 | **6/8** | |
| 101 | **6/8** | |
| 202 | 4/8 | fresh |
| 404 | 4/8 | fresh |
| **pooled** | **20/32 = 62.5 %** | |

Fisher against the round's own arms: **p = 0.0051** against 60 N with the single lead
(8/32 = 25 %), **p < 1e-5** against the shipped 10 N (2/32 = 6.3 %), and **p = 0.54**
against the per-arm lead alone (8/16 = 50 %) - i.e. the two fresh seeds give back part
of the two-seed gain, the same shape every fresh-seed check in this record has shown,
and the cell still sits at **62.5 % over four seeds with no seed below 4/8**.

The per-arm split at four seeds: **left 15/19 (79 %)**, **right 5/13 (38 %)** - the right
is now the weaker arm on the *grasp* (5/13), not on the place.

**The end-to-end arc of the direct policy lane, one number per phase fixed**:

| configuration | placed |
|---|---|
| shipped 10 N, single lead, direct aim | **2/32 = 6.3 %** |
| + real-jaw clamp 60 N (P176) | **8/32 = 25 %** |
| + per-arm contact lead (P182) | **8/16 = 50 %** |
| + place transit's speed limit (P184) | **20/32 = 62.5 %** |
| *(the scripted two-line, for scale)* | *58/80 = 72.5 %* |

## 60. Five seeds on the adopted stack: 25/40 = 62.5 %; the transit clearance is a measured negative at 0.20; the right's lead peaks at 0.20

Three cells close the round's open items.

**1. A fresh mixed seed reproduces the rate.** Seed 303 (never used in this lane):
left **4/5**, right **1/3** -> **5/8**. Pooled over five seeds (77, 101, 202, 303,
404): **25/40 = 62.5 % placed**, **left 19/24 (79 %)**, **right 6/16 (38 %)**, every
seed at or above 50 %.

**2. The place transit's clearance is a measured negative.** `FRUIT_PLACE_SERVO_LIFT`
0.30 -> **0.20 m** (P66's height ladder's low rung, the value the *scripted* direct
interface ships) reads **0/8** on the same seed - left 0/5 and right 0/3, and not one
grasp either, so the payload does not survive the servo's own lift at that clearance.
**Not adopted**; the servo keeps 0.30. (The two heights serve different purposes: the
model's own lift is the scripted 0.20 m rung, while this servo's *transit* needs the
0.30 m clearance to clear the pick station and the output rail.)

**3. The right arm's lead peaks at 0.20.** All-right, seed 202, 4 episodes each:
lead 0.18 -> **2/4**, 0.20 -> **4/4** (P182), 0.22 -> 0/4 (1 grasp). The `dlat`
arithmetic says why there is an optimum: too short and the payload is past the plate's
trailing edge, too long and the pads wait downstream of where the fruit's own tracking
puts it.

**Where the lane stands (all of it measured, every negative kept)**:

| configuration | placed |
|---|---|
| shipped 10 N, single lead, direct aim | 2/32 = 6.3 % |
| + real-jaw clamp 60 N | 8/32 = 25 % |
| + per-arm contact lead (0.10 left / 0.20 right) | 8/16 = 50 % |
| **+ place transit's speed limit 0.15 m/s** | **25/40 = 62.5 %** (5 seeds) |
| *(the scripted two-line, for scale)* | *58/80 = 72.5 %* |

Negatives recorded this round and not adopted: the global 60 N alone (a draw at four
seeds), the squeeze scale (0.90/0.92 -> 1/4 of 4), the latch window (0.03/0.05 -> 1/4),
the phase view (P173b), the transit clearance 0.20 (0/8), lead 0.18 and 0.22, and the
station offset (0/6 at both values).

## 61. The right arm's `dlat` distribution: a knee at ~22 mm, and the pad's 61 mm width is the binding hardware term

With `[close-hold]` now printing once per attempt (the diag's latch was not reset at the
second site), the all-right arm at the adopted stack (seed 202, 8 episodes, 6 latches):

| `dlat` | tactile | grasped |
|---|---|---|
| **14.2 mm** | 52.3 N, n=2 | yes |
| **17.9** | 47.6 N, n=2 | yes |
| **19.3** | 45.2 N, n=2 | yes |
| **20.3** | 49.8 N, n=2 | yes |
| 25.3 | **8.1 N, n=1** | no |
| 26.2 | **0.0 N, n=0** | (scored later) |

**`dlat <= 20.3 mm` gives a solid two-sided pinch at 45-52 N on 4/4; `dlat >= 25.3` is
marginal or empty.** The knee is **~22 mm**, against the plate's geometric half-width of
**30.5 mm** - i.e. the effective coverage is ~0.72 of the half-width, which is what a
sphere meeting a plane's edge does (only its equator touches). The current lead's
`dlat` p50 is ~19 with a tail to 26, so the arm is **right at the boundary**.

**Consequence, in hardware units**: covering the observed tail (p90 ~28 mm) needs a pad
**~2 x 28 / 0.72 = 78 mm** wide along the belt against the shipped **61 mm**. The
shipped pad is the **finger link's own box** (`FRUIT_FINGER_TIP_DELTA` re-authors the
*length*; `FRUIT_FINGER_FACE=plate` adds a raised patch whose width is capped at
`0.9 * extents[1]` = 54.9 mm, i.e. narrower), so **a wider pad is a new asset, not a
knob** - this is the right arm's hardware answer, the same shape as the clamp's.

**A software lever in the same direction**: the close ramp's own length sets how long
the pads take to arrive. `FRUIT_CLOSE_RAMP_TICKS = 45` (shipped 60), all-right, 4
episodes: **3/3 grasps at `dlat` 17.0 / 18.6 / 18.6** (F 30.7-49.9 N) against the
60-tick arm's 5/6 with a tail to 26. A direction at n=3-4, **not adopted** - P91's
warning is about the *probe* ramp's validation margin, not this one, but the same
caution applies until it is measured at four seeds.

## 62. The close ramp's length, paired at two fresh seeds: a wash on the right, a possible negative on the left - not adopted

P61's 45-tick ramp was a direction at n=3-4. Paired against the shipped 60 ticks,
all-right, two fresh seeds, 4 episodes each (and one all-left guard):

| cell | latches | grasps | `dlat` at the latch |
|---|---|---|---|
| right, 202, **45** | 4 | **3/4** | 16.1, 18.7, 20.1, 102.3 |
| right, 202, 60 | 4 | 1/4 | 11.9, 16.0, 18.3, 23.3 |
| right, 404, **45** | 3 | 3/3 | 11.5, 13.1, 16.8 |
| right, 404, 60 | 3 | 3/3 | 9.3, 14.1, 21.2 |
| **left, 202, 45** | 4 | **2/4** | 2.4, 5.6, 8.3, 21.2 |

Pooled all-right: **45 -> 6/7, 60 -> 4/7** - an edge inside the noise at n=7, and the
`dlat` distributions are **not** systematically lower at 45. The left guard reads 2/4,
below its usual ~89 % grasp, i.e. the shorter ramp may cost the arm that did not need
it (a shorter ramp is a smaller validation window, which is exactly P91's mechanism for
the probe).

**Not adopted**; the shipped 60 ticks stand. So the software lane for the right arm is
exhausted: the lead is at its optimum (0.18/0.20/0.22 = 2/4, 4/4, 0/4), the squeeze
scale and the latch window are directions at best, the ramp is a wash, and the station,
the perception, the finger law and the clamp are ruled out. **The right arm's remaining
term is the pad's 61 mm width along the belt** - a new asset (~78 mm by P61's arithmetic),
which is the round's second hardware item after the 60 N clamp.

**Where the lane closes this round**: **25/40 = 62.5 %** end-to-end on the adopted stack
(five seeds, every seed at or above 50 %), left 19/24 (79 %), right 6/16 (38 %), against
the scripted two-line's 58/80 (72.5 %) - with every lever that moved it measured, and
every lever that did not recorded.

## 63. The pad's width: built non-destructively, measured a wash - and the certificate reads 39/64 = 60.9 %

**The hardware item, authored without touching the asset.** `FRUIT_FINGER_PAD_WIDE=<m>`
widens the **build-time authored** finger plate (`scene._author_finger_tip_delta`'s
`tip_delta` box, which `FRUIT_FINGER_TIP_DELTA=0` already re-authors at the shipped
dimensions) - the USD asset is **never edited**, so the change is reversible, and
`assets.scene_provenance` gained a `finger = {pad_wide, tip_delta}` block so a store or a
checkpoint names the pad it was recorded with. Verified statically (P66's instrument, no
physics): `box face/mid/long = 33.3 / **78.0** / 84.9 mm (mid authored: shipped 61.0,
FRUIT_FINGER_PAD_WIDE=0.078)`.

**The paired read, all-right, seeds 202 + 404, 8 episodes each:**

| plate | grasped | 
|---|---|
| shipped **mesh**, 61 mm | **4/8** |
| box control, **61 mm** (`TIP_DELTA=0`) | **5/8** |
| box, **78 mm** (`PAD_WIDE=0.078`) | **4/8** |

So P186's `dlat` arithmetic - cover the tail, the arm converts - **does not hold**: the
width is a wash, and the box-for-mesh substitution is a wash too. The `dlat` correlation
was confounded (the low-`dlat` attempts are also the ones where the servo converged for
its own reasons). **Not adopted**; `FRUIT_FINGER_PAD_WIDE` defaults to 0 (the shipped
extent) and it is recorded as the second **negative** hardware item after P132's pad
shapes.

**The certificate run** (the adopted stack, shipped mixed supply, three fresh seeds):

| seeds | placed |
|---|---|
| 505 / 606 / 707 | 3/8, 5/8, 6/8 = **14/24** |
| **pooled with P185's 40** | **39/64 = 60.9 %** over **8 seeds** |
| per arm (all 64) | left 19/24 + 7/13 -> **26/37 = 70 %**; right 6/16 + 7/11 -> **13/27 = 48 %** |

So the lane's end-to-end number at n=64 over eight seeds is **60.9 %**, with the left at
70 % and the right at 48 % - against the scripted two-line's 58/80 (72.5 %).

## 64. The place transit's speed is a peak, not a floor: 0.15 -> 0.20 -> 0.25 reads 8 / 14 / 7 of 16, and the certificate at 0.20 is 22/32 = 68.8 %

The user's item 3 (test the throughput trade, then decide) turned into the round's best
number. The same two seeds (303, 505) at three transit speeds - the *only* change is
`FRUIT_PLACE_SERVO_VMAX`:

| transit limit | seed 303 | seed 505 | pooled |
|---|---|---|---|
| 0.15 m/s (P184's adopted value) | 5/8 | 3/8 | **8/16** |
| **0.20 m/s** | **8/8** | **6/8** | **14/16 = 87.5 %** |
| 0.25 m/s | 2/8 | 5/8 | **7/16** |

A **peak with both neighbours at half** - the shape a real optimum makes and a branch
draw does not. 0.15 was too slow (the payload hangs in the transit longer than it needs
to) and 0.25 is too close to the direct aim's own ~0.24 m/s (which had read 5/11 on the
left). **0.20 is the adopted value.**

**The certificate at 0.20**, four seeds (two of them fresh for this setting):

| seed | placed | attempt p50 |
|---|---|---|
| 303 | 8/8 | 2322 ticks |
| 505 | 6/8 | 2374 |
| 606 (fresh) | 4/8 | 2064 |
| 707 (fresh) | 4/8 | 1812 |
| **pooled** | **22/32 = 68.8 %** | |

against **19/32 = 59.4 %** for the same four seeds at 0.15. The fresh pair again gives
back part of the gain (4/8 each), the same shape every fresh-seed check in this record
has shown; the pooled number at four seeds is **68.8 %**.

**The adopted direct-policy recipe** (every knob opt-in, no default flipped, `configs/`
and the references untouched):

```
FRUIT_CONTACT_SERVO=1 FRUIT_CONTACT_SERVO_LEAD=0.10 FRUIT_CONTACT_SERVO_LEAD_RIGHT=0.20
FRUIT_PLACE_SERVO=1 FRUIT_PLACE_SERVO_VMAX=0.20 FRUIT_FINGER_MAXFORCE_DIRECT=60
FRUIT_SCORE_ENDPOINT=release
```
on `checkpoints/p177_full` with the shipped crop / start family / ramp / phase gate.

**The lane, in order of what each phase cost** (each number from its own cell):

| configuration | placed |
|---|---|
| shipped 10 N, single lead, direct aim | 2/32 = 6.3 % |
| + real-jaw clamp 60 N | 8/32 = 25 % |
| + per-arm contact lead | 8/16 = 50 % |
| + place transit 0.15 m/s | 25/40 = 62.5 % |
| **+ place transit 0.20 m/s** | **22/32 = 68.8 %** (4 seeds) |
| *(the scripted two-line, for scale)* | *58/80 = 72.5 %* |

## 65. The force-controlled close: a force-*triggered* position loop is a wash, and the reading says why

`FRUIT_CLOSE_FORCE=<N>` (default 0 = off) keeps the committed close going past its
geometric target - at a bounded rate (24 mm/s of span) and with a tick cap - until the
**measured** tactile pinch reaches the target. This is the cheap approximation of the form
`docs/END_EFFECTOR_DECISION.md` names (stiff in the approach, compliant inside the
closure); the drive stays a position drive with a force cap, so it is a *force-triggered*
loop, not a force-controlled joint.

All-right (the arm whose pads reached their command with nothing between them), target
45 N, 4 episodes per seed:

| cell | placed | grasped | `[close-force]` F p50 / max |
|---|---|---|---|
| seed 202 | **3/4** | 3/4 | **0.00 N / 24.8 N** |
| seed 404 | 1/4 | 1/4 | **0.00 N / 28.4 N** |
| pooled | **4/8** | 4/8 | |

against the position ramp's 4/8 (mesh 61) and 5/8 (box 61) at the same seeds - a **wash**.

**The force read is the finding**: the closing **never reached 45 N** (p50 0.00 N, max
24.8-28.4 N even at the cap's end), i.e. the extra ~20 mm of travel did not find the
payload either. So the right arm's term is **not the closure depth**: the pads are
**beside** the payload (`dlat` 19-26 mm) and no amount of closing grips a fruit that is
not between them. That is the same reading as the pad width's (a wash at 78 mm) and it
closes the closure-form family for this arm: what remains is a **different pad shape** or a
**true force-controlled joint** (a drive that holds a force while the gap varies), neither
of which is a knob.

**Not adopted**; `FRUIT_CLOSE_FORCE` defaults to 0.

## 66. P193 verification: **not reproduced at fresh seeds**, and the residual is the acquisition class, not the two servos

The pre-registered rule (`logs/p193/PREREG.md`) asked for pooled >= 10/16 at seeds 808/909
with neither seed below 3/8. What came back:

| seed | placed | notes |
|---|---|---|
| 808 | **4/8** | **8/8** failures `fruit fell off the line` |
| 909 | **1/4 readable** | 4 of 8 episodes produced no outcome (two runs stalled; the first wedged 72 min, the second hit its own 66-min budget) |
| pooled (readable) | **5/12 = 42 %** | |

So the **falsifier's letter fires**: at fresh seeds the recipe reads **42-50 %**, not
68.8 %. The number in §64 stands as the *best measured* four-seed cell; it is **not a
verified rate**, and the record must say so.

**What the failures are, and it changes the diagnosis.** Across every adopted-stack cell,
`fruit fell off the line` is **15 of 16** failures (P190's cells) and **11 of 12** in P193.
That string means *the selected fruit reached the belt's end before the attempt grasped it*
(the payload's `final` is on the floor at `y -0.86..-0.89`, past `despawn_y`) - i.e. the
**acquisition/handover class**, not the contact or place classes that the clamp, the leads
and the transit limit were tuned on. The recipe converts the attempts it takes; the
residual is **taking them**.

**The gap window was the first guess and it is a wash.** A per-attempt census of
`[policy-trace] gap` shows every success with a **minimum gap of 106-116 mm** and the
failures at 1 / 8 / 53 / 60 / 69 / 213 mm, which reads like a close-time window at
~110 mm. `FRUIT_CLOSE_GAP_MIN/MAX` (the model's close honoured only inside a window, the
hand otherwise held open for the servo's own latch) then reads **808 4/8 -> 5/8** and
**303 8/8 -> 7/8**: a wash of one each way, and 28-40 `[acq]` rows per cell confirm the
model's close does arrive outside the window. **The reason it cannot work is the
instrument**: `gap` is the *handover diag*'s distance, and its *minimum* over an attempt is
106-116 mm even on successes - it is not the gap at the fire tick, so the correlation was a
misread (a success's minimum cannot be larger than a failure's if it is measuring the same
approach).

**Not adopted** (`FRUIT_CLOSE_GAP_MIN` defaults to 0 = off). **The named next instrument**:
one row at the *fire tick* - the trigger's `dy`, `dx`, the gap and the finger value at the
moment the model's close is first evaluated - because the acquisition class is now the
binding term and *nothing in the tree logs its decision state*.

## 67. The acquisition census: every latched attempt places, and the residual is the small-fruit class

The `[fire]` row P193 asked for landed twice, and the first version was wrong in an
instructive way. **The model's finger is not the close decision**: that channel hovers at
the action mean (0.0345, P145d.11) and crosses 0.035 at random - measured, it "fires" at
t = 124 with the fruit **335 mm** away. The decision is the **committed ramp's latch**, so
the row now logs there (and at the attempt's end when it never latches), one row per
attempt.

**The census** (the adopted recipe, seeds 808 and 303, 8 episodes each, paired row-to-
outcome):

| seed | episodes | placed | latched | un-latched |
|---|---|---|---|---|
| 808 | 8 | **6/8** | 6 | **2: lychee 3.1 cm, strawberry 3.3 cm** |
| 303 | 8 | **6/8** | 6 | **2: strawberry 3.1, 3.4 cm** |

**Every latched attempt placed - 12 of 12** - and **every failure is a small fruit
(3.1-3.4 cm) that never latched**. The latched rows are tight: `gap` **120-122 mm** at the
latch on all twelve, `[close] xy` in the usual 12-22 mm band.

So the recipe's residual at these seeds is not the carry, the place, the clamp or the
leads: it is **the small-fruit acquisition**, a class at the latch.

**Widening the latch's alignment gate is the wrong fix**: `FRUIT_CONTACT_SERVO_GATE` 30 ->
**50 mm** reads **3/8** (808) and **4/8** (303) against the 30 mm arm's 6/8 and 6/8 - and
the failures move to *large* fruit (peach 6.8, orange 7.0), i.e. the wider gate lets the
latch fire too early. **Not adopted**; 30 mm stands.

**The honest current estimate**, pooling every cell at the adopted recipe (P190's 32,
P193's 12 readable, P194's 16): **39/60 = 65 %** over 7-9 seeds, with a per-seed spread of
**4-8 of 8** - two runs of *the same seed and configuration* read 6/8 and 4/8 (808), which
is the non-reproducible loop's own noise and the reason the pooled read is the statement.

**Named next lever, now specific**: the **small-fruit latch** (fruits <= 3.4 cm never
latch at a 30 mm gate; widening the gate trades them for early latches on large fruit).
The instrument is in place; what it needs is a *size-dependent* seat or gate, which is a
registration of its own.

## 68. The small-fruit class is a *late* acquisition, and the latch's `dy` is not the fruit's

The servo trace of the un-latched 3.1 cm lychee (`FRUIT_CONTACT_SERVO_DIAG=1`, seed 808)
is the finding:

```
[servo] t=676  err=+268mm d=[105, 240,  53]mm aim=(0.227,-0.242,1.255) jaw=(0.332,-0.002,1.308) hold=290mm
[servo] t=980  err=+542mm d=[191, 506, -35]mm aim=(0.231,-0.558,1.250) jaw=(0.422,-0.052,1.215) hold=536mm
```

The aim's **y runs away downstream at 1 mm/tick (the belt's own speed)** while the jaw is
**500 mm behind**, for the servo's whole 149-tick window, and it never latches. So the
attempt was armed **after the fruit had passed** (`dy0 = -0.24 m`), and the servo spent its
window chasing a fruit it cannot catch.

**The arming condition has the wrong shape**: `dy0 <= arm_dy (0.20)` is satisfied by any
*negative* `dy` too. P198 required the fruit to be upstream (`-0.02 <= dy0 <= 0.20`):

| cell | placed | latched |
|---|---|---|
| seed 808, upstream-only arming | **4/8** | 8/8 |
| seed 303, upstream-only arming | **5/8** | 8/8 |
| the same seeds, arming as shipped (P194) | 6/8 + 6/8 = **12/16** | 12/16 |

**Negative, not adopted.** But it is informative twice over: with the chase suppressed
**every** attempt latches (16/16) - so the "0 latch" class was the *chase* masking it -
and the small fruit then fails **after** the latch (three 3.1 cm lychees at seed 808, two
at 303), i.e. **the small-fruit residual is a late acquisition that no downstream action
fixes**, exactly as the pad-width and closure-depth washes said from the other side.

**The instrument insight that explains why the latch looks arbitrary**: `[fire]`'s `dy
(fruit - jaw)` at the twelve successful latches is **+84 .. +144 mm** (fruit upstream),
while the ramp's own latch condition is `goal[1] - jaw[1] <= 0.014` - the **goal**
(perception), which sits ~0.1 m downstream of the true fruit. So the latch is not gated on
where the fruit is; it is gated on where the estimator says it is, and the two differ by
the estimator's own lead. That is the quantity a size-dependent gate or seat would have to
be written against, and it is now measured.

**Named next, precise**: the acquisition needs an **earlier** decision, not a wider one -
the successes latch with the fruit 84-144 mm upstream, so the ramp's condition should be
expressed in the **fruit's** frame (or the goal's lead compensated) rather than the
estimator's. That is a registration of its own; the three cells above say widening and
chasing both lose.

## 69. The goal's coast is load-bearing: the acquisition's timing device is the estimator's lead

P68 showed the successful latches happen with the **true** fruit 84-144 mm upstream while
the ramp latches on `goal - jaw <= 14 mm`, and the goal is `predict_at(age)` capped by
`FRUIT_PERCEPTION_COAST_S` (1.0 s = 120 mm of travel). The obvious reading was "the goal
leads by the coast, so shorten it". Measured, on the same two seeds (8 episodes each):

| coast | seed 808 | seed 303 | `dy` (true fruit - jaw) at the latch |
|---|---|---|---|
| **1.0 s (shipped)** | **6/8** | **6/8** | +84 .. +144 (P194's twelve) |
| 0.2 s | **3/8** | **2/8** | **-848 .. +96** |

So the long coast is **load-bearing**, and the reason is now unambiguous: it makes the goal
**lead** the fruit, which is exactly the *intercept* the latch needs - the pads start
closing while the fruit is still 8-14 cm away and arrive as it does. A tight goal makes the
latch fire on stale measurements at random times (the `dy` range to **-0.85 m**) and the
placements collapse.

**Not adopted**; the shipped 1.0 s stands. (And `[fire]`'s range is the proof that the
latch is *not* gated on the fruit: it is gated on the estimator, by design.)

**What that leaves.** The acquisition's window on this interface is "**the goal ahead of the
fruit by ~0.1 m**", and the failures are the attempts whose fruit is already at or behind
the hand when the attempt begins - a **selection-timing** condition, not a close, servo,
perception or geometry one. Every knob in those four families has now been measured on this
lane (adopted: the clamp, the per-arm lead, the transit speed; refused: the pad width, the
closure depth and the force-triggered close, the 50 mm gate, the upstream-only arming, the
latch window, the squeeze scale, the 45-tick ramp, the transit clearance, the station, the
phase view, the short coast). The next spend is the **selector/supply timing** (P58's
profile, the band, or a "don't offer a fruit already level with the hand" condition), which
is a registration of its own.

## 70. The selector's floor fails its pre-registered rule: selecting earlier does not make the latch land better

P200's registration (`logs/p200/PREREG.md`, pinned before the runs) bet that the acquisition
fails because the *selector* offers fruit too late for the model's approach, and that
raising `FRUIT_DYNAMIC_SELECT_S` from 1.5 s (floor ~0.40 m) to 3.0 s (floor ~0.58 m) would
put the fruit 0.18 m further upstream at selection. One batch, two seeds, 6 episodes each:

| cell | placed | latched | **upstream-at-latch** | `dy` (true) at the latch |
|---|---|---|---|---|
| control 1.5 s, 808 | 3/6 | 6 | 4/6 | -240, -61, **19, 74, 106, 109** |
| treat 3.0 s, 808 | 3/6 | 5 | **1/5** | **-853**, -92, -74, -62, 95 |
| control 1.5 s, 303 | 5/6 | 6 | 3/6 | -103, -65, -57, **81, 93, 106** |
| treat 3.0 s, 303 | 3/6 | 6 | 4/6 | **-405**, -29, 54, 66, 101, 101 |
| **pooled** | **8/12 vs 6/12** | | **7/12 vs 5/11** | |

**Both endpoints fall: the primary (6/12 against 8/12) and the mechanism (the
upstream-at-latch fraction, 5/11 against 7/12).** Per its own rule the registration
**FAILS** and the knob is **not adopted**.

**Why, and it is the arc's conclusion**: under a floor 0.18 m larger the latch's true `dy`
still spans **-853 .. +109 mm** - i.e. selecting earlier does not make the arming land
better, it only makes the hand **wait** longer. The latch fires when the *goal* comes within
14 mm of the jaw, and the goal is the estimator's output: its per-attempt error (a
wrong/stale lock, up to the 1.0 s coast) is what moves the true `dy` about. Every
*decision-side* knob - the floor (this cell), the alignment gate (50 mm), the upstream-only
arming, the coast (0.2 s), the latch window (0.03/0.05), the gap window - either does nothing
or hurts.

So the acquisition's residual is **estimator-driven per-attempt noise**, and the next spend
is the estimator itself (a second view, a tighter fit, or the honest acceptance of the lane
at its measured rate), not another decision rule.

**Where the lane closes this arc**: **39/60 = 65 %** pooled over the adopted-stack cells
(7-9 seeds, a 4-8 of 8 per-seed spread), with **12/12 latched attempts placed**, and the
acquisition's variance attributed to the estimator.

## 71. The "it stops and twitches": 9.9 s of post-task idling, and the emission jitter triples there

The owner's report from the video: occasional very distorted actions, and after a completed
sort the arm stays put and twitches. Both are measured in the P201 clip's own log.

**The idling.** The direct episode ends on the fruit (a despawn) or the horizon, not on the
task. In the P201 clip episode 1's release is at **t = 1208** and the episode runs to
**t = 2400** - **1192 ticks (9.9 s)** of deciding with an empty hand and a stale goal.

**The twitch is that idling, in numbers.** The emitted joint targets' per-decision step
(`|dtgt|` per printed 4 ticks, max over the seven joints):

| window | p50 | p95 |
|---|---|---|
| before the release (in-task) | **0.0180 rad** | 0.0595 rad |
| after the release (idle) | **0.0620 rad** | **0.2200 rad** |

**3.4x the median and 3.7x the p95** - at p95 that is 0.22 rad in 4 ticks = 6.6 rad/s at a
joint, which is exactly what a viewer calls twitching. And the *same* channel is the
"distorted action" source in-task: its p95 there is 0.06-0.31 rad per decision, and P52/P53
measured **10.9-11 % of emitted joint steps outside the arm's own limits** with **no clamp**
on this path (`FRUIT_JOINT_CLAMP` default 0) - so a single out-of-distribution sample can
command the arm into a stop and make it flail.

**The two hygiene fixes, and the one that mis-fires.**
`FRUIT_JOINT_CLAMP=1` is P53's C1: out-of-range 11 % -> **0**, **zero time cost**, and a
null on the success class - safe hygiene, default off.
`FRUIT_EPISODE_END=release` (end the episode on the release) **mis-fires twice and is not
adopted**: with the P175 scoring's finger-crossing as the detector it ended three episodes
at **t = 292** (0.6 s, `0/3`), and with `_max_lift > 0.05` added it read `0/3` again with one
episode reporting **`placed=True, grasped=False`** - i.e. the finger channel, which hovers at
the action mean (0.0345, P145d.11), is **not a release detector**, and a false positive in it
poisons both the score and the episode boundary. The physical detectors are the place servo's
own `at_place` + its 40-tick open ramp (both geometric), or the payload's measured clearance
from the pads; neither is wired to the episode boundary yet.

**Named next**: a **physical release event** (the place servo's `_place_open >= 1`, or the
payload's drop) feeding *both* the score (P175) and the episode end - one detector, two
consumers - which removes the twitch from every clip and closes the false-positive path in
the score.

## 72. One sort = one episode: the physical release event ends the attempt, and the 9.9 s idle is gone

The owner's semantics: after a place there is nothing left to do with that fruit, so the
attempt is over. P202's two misfires had already shown what *not* to use as the detector
(the model's finger command hovers at the action mean and crosses its thresholds at
random). **The detector is now physical, and one detector feeds two consumers**:

* **the place servo's own commit** - `_place_open >= 1` means its 40-tick open ramp finished
  at the destination it drove to; or
* **the payload left the hand** - it had been lifted (`_max_lift > 0.05`, the same test
  `grasped` uses) and is now further from the jaw than any seat (0.25 m) with the fingers
  open; that is the model's own place path.

Both consumers read it: the **score** (`on_output_belt(pos)` at that moment, so
`FRUIT_SCORE_ENDPOINT=release` no longer depends on a channel crossing) and the **episode
boundary** (implied by the `release` endpoint, since that endpoint *defines* the attempt as
finished; `FRUIT_EPISODE_END=release` forces it under the `final` endpoint too).

**Measured, same seed (303) and the same recipe, one change**:

| | episodes' `ticks` | outcome |
|---|---|---|
| before (P201 clip) | **2371 / 2402 / 506** | 2/3 |
| **with the release boundary** | **1290 / 1316 / 957** | **3/3** |

The 1192-tick (9.9 s) post-task idle is gone from every episode, and the clip is 30.6 s
instead of 44.9 s. (The 2/3 -> 3/3 is a branch, not the boundary's doing - the boundary
changes *when* the episode stops, not what it scored.)

**The remaining visible defect is the in-task outlier, not the idle**: the emitted-joint
step is p50 0.018-0.021 / p95 0.055-0.100 rad per decision, with one episode carrying a
**0.275 rad** step - the "distorted action". `FRUIT_JOINT_CLAMP=1` (P53's C1, zero time
cost) is in the clip's recipe as hygiene; a *rate* limit on the command is the named next
(it changes the achieved rate, so it is its own cell).

**No-harm**: the endpoint is opt-in, so the shipped default (`final`) keeps its success
definition (`on_output_belt(final)`); the only change on that path is that the printed
`placed=` now reflects the physical release instead of a channel crossing.

**Correction (P207)**: the `FRUIT_JOINT_CLAMP=1` named above is P53's canonical
`FRUIT_POLICY_JOINT_CLAMP`; the short spelling was silently inert, so this clip ran
**unclamped**. P207 adds the short name as a direct-only alias and records the correction
in the clip README.

## 73. P207/P208: the command tail is capped at the arm's joint speed, and the clamp knob that was never on

The owner's second report on the video was the occasional **distorted pose**. P202 had
removed the post-sort idle; this phase is the in-task command. The instrument is the
`[cmd]` row (`FRUIT_POLICY_TRACE=1`, one row per 4-tick waypoint). In the control cells the
**per-waypoint target step (max over the seven joints)** is p50 0.021-0.028 rad, p95
0.136-0.198, and **max 0.660-2.633 rad** - a step the arm cannot follow (its own joint
limit is 5.45 rad/s = 0.182 rad per 4 ticks). That outlier is the visible pose.

**The cap.** `FRUIT_POLICY_TARGET_RATE=<rad/s>` (default 0 = untouched) ramps each joint
from the last emitted target by at most `rate/120` per control tick; the state is per arm
and re-seeded from the measured joints at every attempt and after a servo. A request
inside the cap is emitted exactly, so it is not a filter. At **5.45 rad/s** (the arm's own
`maxJointVelocity`, 312 deg/s): pooled seeds 303/808 (6 episodes each) **7/12 placed
against the control's 7/12**, emitted **max 2.633 -> 0.182 / 0.660 -> 0.182 rad**, p95
**0.198 -> 0.181 / 0.136 -> 0.093**, binding only **16-24 %** of waypoints. R4 (4.0) is a
stronger smoother but a speed limit on some branches (6/12); R2 (2.0) binds **76.6 %** and
is measured out. The count is a branch draw (see below), but the mechanism is exact.

**The clamp that was never on.** Every recipe (including the P202/P204 clips) exported
`FRUIT_JOINT_CLAMP=1`, but P53's canonical knob is **`FRUIT_POLICY_JOINT_CLAMP`**. The
short spelling was silently inert, so those clips ran **unclamped**. P207 makes it a
direct-only alias (the canonical name wins when both are set; a non-direct wrapper stays
inert instead of aborting). The C cells here are the first direct cells with the clamp
actually on: `[emit]` out_pre 4.9 % -> out_post 0.0 % on the episode that had overshoot.

**The state bug the cap exposed.** At `logs/p207/C_s303.log` t=996, after the place servo
declined, the chunk generated *before* the servo commands j1 -1.066 against measured
+0.684 (1.75 rad) - the arm is sent back to its pre-place pose. The cap smooths that into
a ~1 s sweep but cannot remove it. `FRUIT_REPLAN_ON_SERVO_END=1` drops the remaining chunk,
forces one fresh observation (the hand-back can land between 4-tick observation phases) and
re-plans: residual p95 **1.289 -> 0.344 rad**, achieved step p95 0.091 -> 0.049, but the
count is 3/6 against 4/6 on a different branch and the residual max *rises* to 2.431 (a
new request after the replan, not a stale one). **Smoothness-only; not in the ship recipe.**

**The counts are branch draws, stated so they are not overread.** Same seed does not
select the same fruit after the first attempt: the attempt's duration changes which fruit
is at the station. At seed 303 C and R4 both start with the same failing orange; C's next
is a kiwi, R4's a 3.1 cm strawberry. At seed 808 the first 3.1 cm lychee fails in every
arm and the later sequences diverge. The 6-episode counts are reports; the pooled 12 is
the only count quoted.

**The clip.** `p207_smooth_4of6_s303/` (4/6, 56.6 s) is the same line with the cap and the
real clamp: emitted p95 **0.046 rad**, max **0.182**, > 0.10 rad **1.7 %**, cap binding
12.1 %. It is in the media index beside the earlier clips.

**Gates**: `selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new `271`/`272` legs;
`accept.sh` **7/10 + `fingerprint: matches` + `190: PASS`** (the scripted line never
constructs `SortingRLEnv`, so it is an import guard, as P203's release boundary was);
`106` OK, `107` PASS (21 checks). References **`30fb99f8` / `30fb99f8` / `8952c320`** and
`configs/` untouched. No default was flipped; the recipe settings are opt-in.

**Pins.** `rl_env.py` **`906021c1`**, `scripts/271_p207_target_rate_selftest.py`
**`a4e2bfae`**, `scripts/272_p208_replan_selftest.py` **`41b87613`**, `selfcheck.sh`
**`978a311c`**; evidence `logs/p207/{PREREG.md,RESULTS.md,analyze.py,run_p207.sh}` and the
cells `C_s303`, `R2_s303`, `R4_s303`, `C_s808`, `R4_s808`, `R4P_s808`, `R5_s303`,
`R5_s808`; clip `logs/video_p207/`.

## 74. P209/P210: the chunk-length lane is closed - execute half is negative, and ensembling only rescues it

The action-chunk literature's "predict long, execute about half" does **not** transfer to
this policy unchanged, because each chunk is a fresh DDIM sample. Seed 808, 6 episodes,
P207 R5 recipe, the only difference `--execute-steps` and (for the third arm)
`FRUIT_POLICY_ENSEMBLE=0.5`:

| arm | placed | emitted p95 / max | >0.10 | residual p95 / max | binding |
|---|---|---|---|---|---|
| E4 (execute 4) | **4/6** | **0.101 / 0.182** | **5.2 %** | **0.110 / 0.626** | 25.2 % |
| E2 (execute 2) | 2/6 | 0.182 / 0.182 | 15.5 % | 0.409 / 2.021 | 45.4 % |
| E2T (execute 2 + TE 0.5) | **4/6** | 0.122 / 0.182 | 6.5 % | 0.153 / 1.533 | 24.7 % |

**P209** measured the negative: doubling the re-plan rate doubles the chunk boundaries,
and every boundary is a new stochastic sample, so the emitted p95 rises 0.101 -> 0.182
and the cap binds 45 % instead of 25 %. **P210** implemented ACT-style temporal
ensembling (`ensemble_action_chunk`: the new chunk's first `steps` waypoints and the
previous chunk's unexecuted `prev[steps:]` are averaged; `FRUIT_POLICY_ENSEMBLE=alpha`,
default 0). It recovers the count (2/6 -> 4/6) and the residual (0.409 -> 0.153), but it
does **not** beat execute 4: the full chunk is already coherent, and the extra 15 Hz
decisions cost the tail (0.122 against 0.101) and wall. **F3 fires: keep E4.** The
chunk-length lane is closed; the remaining success residual is the small-fruit/right-arm
class, not the execution horizon.

**Pins (P209/P210).** `rl_env.py` **`8ec7c03e`**,
`scripts/273_p210_ensemble_selftest.py` **`b30c3660`**, `selfcheck.sh`
**`2b88c0d2`**; evidence `logs/p209/{PREREG,RESULTS}.md` + the E4/E2 cells, and
`logs/p210/{PREREG,RESULTS}.md` + the E2T cell. No default flipped, no reference
re-recorded; the P207 R5 recipe stands.

## 75. P211: the small-fruit selector floor binds but does not convert the small class

The last software lever for the 3.0-3.4 cm class is selection timing. `FRUIT_SELECT_SMALL_EXTRA`
(direct-only, default 0) adds a size-conditioned floor to the moving catch: a fruit at or
below `FRUIT_SELECT_SMALL_DIA` (default 0.040 m) must be that much further upstream, else
the selector refuses it and waits for/chooses another. The `[bed-sel]` rows prove it binds
(0.184/0.255/0.403 < 0.549 at extra 0.15). It does **not** convert:

| cell | seed | placed | small attempted / placed |
|---|---|---:|---|
| control E4 | 808 | 4/6 | 1/0 |
| extra 0.15 | 808 | **5/6** | 1/0 |
| extra 0.25 | 808 | 3/6 | 1/0 |
| control E4 | 303 | 3/6 | 0/0 |
| extra 0.15 | 303 | 3/6 | 1/0 |

The 0.15 seed-808 5/6 is a **selection effect**: one small attempt, five large ones, all
five place. The admitted small fruit still fail - including a **3.3 cm strawberry at
+0.673**, 0.27 m above the normal floor - so the class is not "too close"; it is the
hand/perception limit on a small object. A floor high enough to skip the class entirely
(> 0.45 m) would discard 3-5 of the 16-fruit pool, a yield trade. Pooled 0.15 is **8/12
against 7/12** (+1, one attempt), 0.25 is **3/6** (-1): a draw. **Not adopted.** The
`TASKS_MD5` pin moves because the selector carries the two parsers; the scripted path's
`direct=False` branch keeps the shipped expression.

**Pins.** `tasks.py` **`d1b18e2a`**, `rl_env.py` **`d6198b9a`** (the P211 tree; the P210
tree was `8ec7c03e`), `scripts/274_p211_small_select_selftest.py` **`56f12c8e`**,
`selfcheck.sh` **`a3d85726`**; evidence
`logs/p211/{PREREG,RESULTS}.md` and the S/S25 cells. No default flipped, no reference
moved.

## 76. P212: the right arm's place transit speed is not the lever

A B-heavy pool (`A:0.10,B:0.80,C:0.10`) makes almost every episode the right arm; seed
808, 6 episodes per arm, only `FRUIT_PLACE_SERVO_VMAX_RIGHT` differs. **Control 0.20 2/6,
treatment 0.15 2/6**; the slower transit doubles the `[pservo]` rows (428 -> 887) and the
`hold=` (the payload's distance from the jaw) is already **115-120 mm** in both arms
before the place point. The payload is out of the pinch in the lift/carry, so the place
transit cannot be the cause. F1 and F3 fire; **not adopted**. The per-arm knob
(`FRUIT_PLACE_SERVO_VMAX_LEFT/RIGHT`, default-inert) stays as a measurement capability.

**Pins.** `rl_env.py` **`b7a2698a`**, `tasks.py` **`d1b18e2a`** (unchanged),
`scripts/275_p212_place_vmax_selftest.py` **`409c56e6`**, `selfcheck.sh` **`82dda3df`**;
evidence `logs/p212/{PREREG,RESULTS}.md`, `R020_s808`, `R015_s808`. No default flipped.

## 77. P213 probe: the two-camera conflict is the second instance annotator, not the camera

P135 left the second view blocked on a scene-pipeline fix ("mere authorship of a second
annotated camera takes the head's instance mask away"). The probe authors the wrist pair
with `FRUIT_WRIST_ANNOTATORS=rgb,distance_to_image_plane` and leaves the head's own
instance mask. Two episodes, seed 808: the head's `[percept]` counters are **18/300 in
episode 0 in both arms** and **255 vs 271 accepted in episode 1** (the branch's own
timing), so the head mask survives. The conflict is the second
`instance_id_segmentation` render product, not the camera. The direct env does not read
the wrist sensor yet and there is no mask-free segmenter; the named next step is a
goal-guided depth window (project the head estimate, fit the local depth patch) or a
colour segmenter. No default change: `FRUIT_WRIST_ANNOTATORS` defaults to the head's list.
**Pins.** `scene.py` **`a766b770`**, `scripts/276_p213_wrist_annotators_selftest.py`
**`4bcabbbd`**, `selfcheck.sh` **`cd9e728d`**; evidence `logs/p213/`.

## 78. P214: the mask-free wrist depth window is not usable

P213 removed the annotator blocker, so the next question was whether the wrist depth is
usable without an instance mask. The probe projects the head estimate into the wrist
frame, samples a 35-px depth disk and fits a sphere. Seed 808, one episode (the result is
categorical): the head `[percept] err` is **1.74-2.13 mm**, the wrist `[wrist-depth] err`
is **44.3-61.8 mm**, `fit_r` 55.5-73.2 mm (a 6.5 cm fruit's radius is 32.5 mm), `rms`
10.2-12.0 mm. The disk is the **hand/fingers**, not the fruit; the P135 wrist-only
3.54 mm used the instance mask. **The mask-free depth window fails**; the remaining
second-view options are a colour segmenter or a learned mask-free detector. The probe is
default-off, direct-only, reporting-only. **Pins.** `rl_env.py` **`9c41fd7a`**,
`scripts/277_p214_wrist_depth_selftest.py` **`8cf07989`**, `selfcheck.sh`
**`798761bf`**; evidence `logs/p214/`.

## 79. P215: the small-fruit class is not force-limited

Lychee-only supply (3.1-3.7 cm), seed 808, 6 episodes per arm, P207 R5 recipe; the global
direct cap is 60 N and only the <= 4 cm branch differs. **60 N: 1/6; 20 N: 1/6**; both
successes are the same 3.7 cm lychee, and the 3.1/3.1/3.1/3.4/3.6 cm fruit fail at both.
The `[drive]` rows prove the 20 N cap (`10.00 -> 20.00 N (..._SMALL)`). The head estimate
on the 3.1 cm fruit is 1.74-2.13 mm (P214), so it is not perception; with 20-60 N both
failing, it is not force. The remaining term is the **pad/finger geometry on a 3 cm
object** - the hardware/new-pad class, not a software knob. **Not adopted**; the
size-dependent cap stays default-off. **Pins.** `rl_env.py` **`f7ebb7cb`**,
`scripts/278_p215_small_clamp_selftest.py` **`ef36266f`**, `selfcheck.sh`
**`1b51e26b`**; evidence `logs/p215/`.

## 80. P216: the phase close was one-sided; fixing it exposes the small-fruit policy failure

The P215 small-fruit `[close]` rows read `xy=442 mm` and `[fire] dy=-442 mm`: the phase
gate closed the pads with the fruit **behind** the hand. The trigger was `dy <= 0.014`,
true for any negative dy. P216 adds `FRUIT_CLOSE_RAMP_DY_LO` (default `-inf`, the shipped
one-sided path) and measures `-0.02` (the contact servo's own "level or just behind"
window). Lychee-only, seed 808:

| arm | placed | close | `[fire]` on 3.1-3.4 cm |
|---|---:|---|---|
| control (P215, `-inf`) | 1/6 | one at `xy=442 mm` | `fired=1`, gap 459 mm, dy -442 |
| `-0.02` | 0/4 partial | one at `xy=25 mm` (3.4-3.7 cm) | **`fired=0`, gap 647-1180 mm, dy -554..-1145** |

The bug is gone (no close with dy < -20 mm), and the real state is exposed: the policy
**never approaches** the 3.1-3.4 cm fruit; at the attempt's end the fruit is 0.65-1.18 m
behind the hand. The P215 force comparison is **confounded** - the small fruit never
reached the pads - and its "pad/hand geometry" sentence is **withdrawn**. The 3.7 cm
lychee closes at 25 mm and places at both caps. The next spend is the **policy**: a
size-aware phase gate/retrain or a cartesian action that actually approaches a 3 cm
fruit. `FRUIT_CLOSE_RAMP_DY_LO=-0.02` is a correctness setting; the default stays `-inf`.
**Pins.** `rl_env.py` **`8f3c350f`**, `scripts/279_p216_close_lo_selftest.py`
**`281521ec`**, `selfcheck.sh` **`69c566b2`**; evidence `logs/p216/`, `logs/p217/`.

## 81. P217: the scripted line grasps 5/6 lychees - the small-fruit failure is the policy

The decisive control for P215/P216. Same hand, same 3.1-3.4 cm lychee-only pool, seed 808,
the shipped **scripted** dynamic catch (single arm, 6 attempts): **5/6 = 83 %**, placed at
9.65-10.61 N, lifts 0.312-0.382 m. The one failure is a carry/place escape at 29 N, not
acquisition. The learned direct line on the same class is 1/6 (60 N), 1/6 (20 N) and 0/4
(two-sided close, `fired=0` at 0.65-1.18 m). **The hand can hold a 3 cm lychee at 10 N;
the policy never approaches it.** The small-fruit residual is the **policy
approach/phase**, not force, pad geometry or the second view. The next spend is a
size-aware phase gate/retrain, a cartesian action, or a size-conditioned handover to the
scripted primitive (5/6) while the learned policy keeps the large fruit. Evidence
`logs/p216/scripted_lychee.log`.

## 82. P218/P219: a size-conditioned scripted skill places the small fruit

P216/P217 showed the learned policy never approaches a 3.1-3.4 cm fruit, while the shipped
scripted catch places 5/6 lychees at 10 N. P218 adds `FRUIT_SMALL_HANDOVER=1`: a fruit at
or below 0.040 m runs `_run_scripted()` (the same `task.run` as `--ablate scripted`); the
learned policy keeps every larger fruit.

* **Lychee-only, seed 808, 6 episodes**: small handover **5/6**, `decision=0` on every
  scripted attempt, matching the scripted control 5/6 against the learned 1/6.
* **Mixed pool, seed 303, 6 episodes**: **5/6** - learned large 4/4 (orange, kiwi, peach,
  peach), scripted small 1/1 (3.0 cm lychee), one 7.0 cm right apple failure on the
  learned path. The learned control at the same seed was 3/6 (C303) / 4/6 (R5 303).
* **Mixed pool, seed 808, 6 episodes**: **4/6**, equal to its control; the small class is
  2/2 (3.1 lychee, 3.1 strawberry), the learned large 2/4 (a tomato and a 6.9 cm pear
  fail). The earlier 808 attempt wedged at 3/4 after the renderer; the rerun is complete.

The hybrid is **not a learned small-fruit policy**; it is a skill route. The class
mechanism is strong and the seed-303 cell is positive, but the mixed count is a branch
(+1 at 303, equal at 808) and the right-arm large class is untouched. The scripted small
attempts cost 1700-1900 ticks against the learned 1100-1300 (~10-15 % on the branch).
`FRUIT_SMALL_HANDOVER` is default-off; the recipe setting is opt-in.
**Pins.** `rl_env.py` **`bd1bf141`**, `scripts/280_p218_small_handover_selftest.py`
**`24c8bfad`**, `selfcheck.sh` **`a9314fe9`**; evidence `logs/p218/`, `logs/p219/`.

## 83. P220: the small-fruit handover is continuous-ready

The continuous loop's `_finalize` starts the next pick; the question was whether the
scripted skill's finalize does the same. **It does.** Lychee-only, one continuous episode,
6 picks, seed 808, `FRUIT_SMALL_HANDOVER=1`: pick 1 fails, picks 2-6 place, every small
attempt `decision=0` (the learned policy is not used). `[cont] episode 5: picks=6/6
placed=5 ... ticks=10290 gap_ticks=76.0 gaps=[100,70,70,70,70]` - **5/6**, 15.3 s/pick,
against the learned continuous P204's **2/6**. The `[cont] pick k/6` rows 2..6 prove the
scripted finalize returns to the next pick.

The mixed continuous run (seed 505) started pick 2/6 and **wedged** in the learned
large-fruit post-close phase after 12+ min; the lychee-only all-scripted episode
completes. The handover is not the cause; the learned large path is the known
continuous-mode wedge (P145b). The mixed per-episode cell is 5/6 at seed 303 (P219).
**The small-fruit handover is continuous-ready; the mixed continuous loop needs the
timeout-guarded/chunked runner or the post-close fix before it is a stable demo.**
