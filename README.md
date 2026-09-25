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
| Scripted pick-and-place, sorted by grade into bins | **working (6/6)** |
| Point-tactile sensing on the grippers | blocked by the contact API in this build |
| Demonstration collection + diffusion policy | not yet (planned) |

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
