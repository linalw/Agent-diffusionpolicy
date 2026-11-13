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
