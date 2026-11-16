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
