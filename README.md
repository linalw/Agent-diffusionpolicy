# Agent-DiffusionPolicy: bimanual fruit sorting on a dynamic conveyor

Research code for an Agent + diffusion-policy controller that sorts fruit moving on a
conveyor line, built on NVIDIA Isaac Sim 6.

The long-term design (slow Agent loop, skill-routed diffusion policy, experience memory)
is summarised in [`实现方案总结.md`](实现方案总结.md). This repository holds the working
implementation: the simulation cell, the data pipeline, and the policy training code.

## Current status

| Piece | State |
| --- | --- |
| Isaac Sim headless bring-up on this machine | working (`scripts/smoke_test_isaacsim.py`) |
| Robot: OpenArm bimanual upper body (2x 7-DoF arms + parallel grippers) | loading, articulated, verified |
| Sorting cell: pedestal, conveyor with surface velocity, output bins | built and verified |
| Head RGB-D camera (single camera, wide FOV) | capturing rgb + depth + instance ids |
| Randomized fruit on the moving belt | spawning, transporting, recycling |
| Scripted pick-and-place, sorted by grade into bins | **working (8/8)** |
| Point-tactile sensing on the grippers | **working** (per-finger contact sensors) |
| Demonstration collection | **working** (`scripts/40_collect_demos.py`) |
| Skill-Routed MoE diffusion policy | **implemented + trained** (router accuracy 0.993) |
| Inference speed | 3.4 ms/chunk at 2 DDIM steps, 6.5 ms at 4 (budget is 50 ms) |
| Realistic fruit assets | procedural meshes, per-category shape/colour/friction/density |
| Cleated belt conveyor with friction transport | working |

## Results so far

| Stage | Result |
| --- | --- |
| Scripted pick-and-place (realistic scene) | **8/8**, ~98% over a 46-attempt collection run |
| Demonstrations collected | **210 episodes**, 60,507 frames, all 8 categories, both arms |
| Skill-Routed MoE training | 4.59M parameters, 15 epochs, val loss **0.0156**, router accuracy **0.998** |
| Policy closed-loop evaluation | **5/10** successful cycles |
| Parallel collection throughput | 3 workers x ~1.4 episodes/min (~3x single worker) |
| Policy inference | 3.4 ms/chunk at DDIM 2, 25 ms at DDIM 16 |

The policy tracks the scripted controller imperfectly: 18 demos gave 2/8, 45 gave
4/10, 210 give 5/10. Using more inference compute does not help (DDIM 16 with
re-planning every 4 steps scores the same), so the limit is not sampling.

Two things still separate it from the scripted controller's ~100%:

* demonstration volume - the design document's own guidance is 400-600 episodes
  per skill, and the curve is still rising at 210;
* grasp fidelity - the OpenArm finger colliders do not reliably hold fruit in
  this build, so the demonstrations (and therefore the policy's training target)
  use a modelled grasp. The evaluator applies the same model so the comparison is
  like-for-like.

## Scene realism

**Fruit** (`src/fruit_sorting/meshes.py`) are procedural meshes, not spheres. Each
is a surface of revolution generated **at its final size in metres** - never via
a Scale xform op, because PhysX mis-cooks scaled collision shapes (a scaled
sphere ends up with no collider that the robot can touch at all; see WORKLOG).

| Category | Profile | Colour | mu | Density |
| --- | --- | --- | --- | --- |
| apple | hand-traced silhouette, stem cavity, 5-lobe lobing | red / green / golden | 0.45-0.70 | 850 |
| pear | narrow neck, bulbous base | yellow-green | 0.45-0.70 | 880 |
| orange | sphere, dimple, bumpy peel | orange | 0.70-1.00 | 900 |
| tomato | flattened sphere | red | 0.50-0.75 | 780 |
| peach | soft dimple | pink-orange | 0.55-0.85 | 820 |
| kiwi | elongated, strong surface noise | brown | 0.75-1.05 | 900 |
| lychee | small, bumpy | red-brown | 0.55-0.85 | 850 |
| strawberry | conical, pointed | deep red | 0.55-0.85 | 700 |

Every instance gets its own deformation, colour jitter and friction sample, so no
two fruit are identical. Apple and pear also get a stalk. Mass follows the real
density: a 6.4 cm apple is 94 g, a 3.7 cm strawberry is 15 g.

**Conveyor** (`src/fruit_sorting/conveyor.py`) is a cleated track belt rather
than a sliding slab:

* a rubber belt surface with `PhysxSurfaceVelocityAPI` plus a friction material,
  so fruit are carried by **friction**;
* 8 transverse cleats as kinematic bodies travelling with the belt, which push
  the fruit along the way a real cleated conveyor does;
* head and tail pulleys, an aluminium frame, and low guide rails that keep
  produce on the centre line.

Measured transport is about 0.28 m/s with fruit staying within a few millimetres
of the centre line.

**Lighting** is a studio setup: sky dome, a 2.5-degree sun with soft shadows, a
large rectangular fill panel, a concrete floor and a backdrop wall.

## Policy architecture

The policy follows the design discussion rather than a single monolithic net:

```
head-camera RGB + depth + target mask   goal: pose, velocity, size, bin
              │                                    │
        VisualEncoder                        ConditionEncoder  ──┐
              └──────────────┬───────────────────────┘            │
                       condition vector                         proprioception
                             │                                    │
                    Skill Router (5 classes)                      │
                             │                                    │
     action chunk → shared 1-D UNet backbone ←─────────────────────┘
                             │
          + Σ_k w_k · Expert_k(features)      (residual adapters)
                             │
                        predicted noise
```

* **Skill Router**: 5 classes (approach / grasp / lift / place / recovery).
  Labels come from robot state rules in `policy/skills.py` - no manual annotation.
* **Experts**: lightweight residual adapters initialised as no-ops, so the routed
  model starts identical to the shared backbone.
* **Training**: first 2 epochs **hard routing** (the labelled expert is forced),
  then **soft routing** with a router cross-entropy and a load-balancing loss.

Measured training run (26 episodes, 6379 windows, 4.59M parameters):

| Epoch | Routing | Router accuracy | Val loss |
| --- | --- | --- | --- |
| 1 | hard | 0.536 | 0.169 |
| 2 | hard | 0.770 | 0.115 |
| 3 | soft | 0.923 | 0.096 |
| 5 | soft | 0.989 | 0.076 |
| 8 | soft | **0.993** | **0.056** |

## Inference speed

`scripts/80_benchmark_policy.py` on the RTX 5090, single action chunk:

| Variant | ms/chunk | Control rate if re-planned every step |
| --- | --- | --- |
| eager fp32, DDIM 16 | 25.2 | 40 Hz |
| eager fp32, DDIM 8 | 12.8 | 78 Hz |
| eager fp32, DDIM 4 | 6.5 | 155 Hz |
| eager fp32, DDIM 2 | 3.4 | 299 Hz |
| fp16, DDIM 8 | 13.3 | 75 Hz |
| torch.compile, DDIM 8 | 12.4 | 81 Hz |

The dominant lever is the DDIM step count, not precision: this model is small
enough that fp16 and `torch.compile` are overhead-bound. Because the policy
produces an action chunk and only re-plans every N steps, the amortised cost is
`ms/chunk / N` - at DDIM 8 with N = 8 that is **1.6 ms per control step**, far
inside the 50 ms / 20 Hz sorting budget.

## Robot choice

The task calls for an **upper-body-only, dual-arm, gripper** robot. The OpenArm bimanual
platform ([enactic/openarm](https://github.com/enactic/openarm)) is an open-source humanoid
upper body with two 7-DoF arms and a 1-DoF parallel gripper per arm, and it ships as an
official Isaac Sim 6 asset with an Isaac Lab configuration. Full humanoids in the asset
catalogue (Unitree G1, AgiBot A2D, Tien Kung, Fourier GR-1) either include legs or use
multi-finger hands rather than grippers, so they do not match the brief.

Since OpenArm has no head, the cell adds a short mast with a single wide-angle RGB-D camera
in the position a humanoid head would occupy. That camera is the policy's only exteroceptive
sensor.

## Layout

Robot at the origin facing `+X`; the conveyor runs along `Y` in front of it.

```
                        infeed (+X)
   [ bin A (+Y) ]   ===== conveyor, fruit travel -X ====
                        [ pedestal + OpenArm ]  (head camera on mast)
   [ bin B (-Y) ]        pick station at x = 0.34
```

The belt runs **end-on** to the robot: the OpenArm jaws open along the shoulder
axis, so fruit have to arrive perpendicular to that to pass between the fingers.

Cell dimensions were derived from a measured reachability sweep
(`scripts/12_reach_calibration.py`): shoulders sit at `(0, +/-0.0935, 1.448)` m with a TCP
reach of ~0.68 m, and the TCP cannot descend below `z = 0.90` m. The belt surface is
therefore at `z = 1.15` m and the output bins stand on 1.00 m pedestals.

Grasp geometry, measured in `scripts/36_static_grasp.py`:

| Quantity | Value |
| --- | --- |
| Finger faces at full opening | 0.0758 m apart |
| Finger link origins at full opening | 0.098 m apart |
| Finger span below the jaw centre | 0.076 m |
| Largest fruit the gripper can straddle | ~0.072 m |

## Environment

| Item | Path / value |
| --- | --- |
| Isaac Sim (built from source) | `/home/ubuntu/linalw/App/isaacsim`, launcher `_build/linux-x86_64/release/python.sh` |
| Isaac Sim version | 6.0.1-rc.7 |
| Isaac Lab | `/home/ubuntu/linalw/App/IsaacLab/IsaacLab` |
| GPU | RTX 5090 32 GB, driver 580 |
| Asset root | `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0` |

All scripts are run with the Isaac Sim Python launcher, from the repository root:

```bash
export ISAAC_SIM_DIR=/home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/release
export OMNI_KIT_ACCEPT_EULA=YES
$ISAAC_SIM_DIR/python.sh scripts/10_build_scene.py
```

Set `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` first if the asset server is slow.

## Reproducing the pipeline

```bash
export ISAAC_SIM_DIR=/home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/release
export OMNI_KIT_ACCEPT_EULA=YES FRUIT_CAMERA_ANNOTATORS=rgb,distance_to_image_plane

# 1. Calibrate the arm waypoints for the current cell (writes configs/waypoints.json)
$ISAAC_SIM_DIR/python.sh scripts/30_calibrate_waypoints.py

# 2. Collect scripted demonstrations
FRUIT_EPISODES=28 FRUIT_DEMO_DIR=datasets/demos_v1 \
  $ISAAC_SIM_DIR/python.sh scripts/40_collect_demos.py

# 3. Train the diffusion policy (plain PyTorch; no Isaac Sim needed)
EPOCHS=8 /home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python \
  scripts/50_train_policy.py --data datasets/demos_v1 --out checkpoints/policy_v1

# 4. Evaluate closed loop in the cell
FRUIT_CKPT=checkpoints/policy_v1/policy_best.pt FRUIT_EPISODES=10 \
  $ISAAC_SIM_DIR/python.sh scripts/60_eval_policy.py
```

`datasets/` and `checkpoints/` are gitignored; regenerate them with the commands above.

## Seeing it run

**Watch it live.** Every run script takes `HEADLESS=0`, which opens the Isaac Sim
GUI on the machine's display:

```bash
HEADLESS=0 $ISAAC_SIM_DIR/python.sh scripts/20_pick_place.py   # scripted cycles
HEADLESS=0 $ISAAC_SIM_DIR/python.sh scripts/70_record_video.py # and record
```

**Watch a recording.** `scripts/70_record_video.py` writes:

| File | Content |
| --- | --- |
| `logs/video/observer.mp4` | fixed external view of the whole cell |
| `logs/video/head.mp4` | what the robot's head camera sees (the policy input) |
| `logs/video/side_by_side.mp4` | both views stacked |

**Look at stills.** `scripts/20_pick_place.py` with `FRUIT_CAPTURE=1` saves
`logs/pick_observer.png` and `logs/pick_head.png` after the cycles finish.

**Inspect the data.** Each episode in `datasets/*/` is a compressed `.npz` with
`image_rgb`, `image_distance_to_image_plane`, `joint_positions`, `tactile`,
`goal`, `action` and `fruit_position`, plus an `index.json` summary.

## Scripts

| Script | Purpose |
| --- | --- |
| `scripts/smoke_test_isaacsim.py` | Minimal launch check: physics, RGB-D capture |
| `scripts/02_load_robot.py` | Load OpenArm, print joints/limits/TCPs |
| `scripts/03_camera_debug.py` | Verify camera optics from several viewpoints |
| `scripts/10_build_scene.py` | Build the full cell, run the belt, capture frames |
| `scripts/11_bisect_scene.py` | Build selected scene parts (crash bisection) |
| `scripts/12_reach_calibration.py` | Sample the arm workspace |
| `scripts/20_pick_place.py` | Scripted pick-and-place cycles, sorted into bins |
| `scripts/30_calibrate_waypoints.py` | Solve and save `configs/waypoints.json` |
| `scripts/31_reach_sweep.py` | Reachable jaw heights at the pick pose |
| `scripts/32_hold_test.py` | Hold a waypoint; verify joint tracking |
| `scripts/36_static_grasp.py` | Grasp geometry and finger-face mapping |
| `scripts/40_collect_demos.py` | Collect scripted demonstrations into `datasets/demos` |
| `scripts/50_train_policy.py` | Train the diffusion policy (runs outside Isaac Sim) |
| `scripts/60_eval_policy.py` | Closed-loop policy evaluation in the cell |

## Package layout

```
src/fruit_sorting/
  assets.py    SceneConfig (cell geometry) and robot/asset constants
  common.py    numpy/warp helpers, look-at quaternion, logging
  scene.py     SortingScene: builds and drives the cell
  fruits.py    FruitSpawner: randomized fruit, belt release/recycle, state readout
  tactile.py   (planned) contact sensors on the gripper fingers
```

## Known issues in this Isaac Sim build

* The `instance_segmentation` and `pointcloud` camera annotators segfault the headless app
  (6.0.1-rc.7). `instance_id_segmentation`, `semantic_segmentation`,
  `bounding_box_2d_tight` and `normals` work. The cell uses `instance_id_segmentation`.
* `occlusion` and `camera_params` annotators raise on creation.
* Camera optics are expressed in tenths of a scene unit, so on a metre stage a 16 mm lens
  is `0.016` and a 36 mm sensor is `0.036`.
* Kit's fast shutdown discards buffered stdout; every log line is flushed.
