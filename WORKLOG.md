# Worklog

Running notes for the implementation. Newest entry first.

## 2026-09-25 - simulation cell bring-up

### Feature -> skill mapping

| Needed capability | Skill / reference used |
| --- | --- |
| Drive a built Isaac Sim from a script | `$ISAAC_SIM/skills/isaac-sim-orchestrator`, `meta-skills` |
| Create cameras + annotators | `$ISAAC_SIM/skills/isaac-camera` |
| Contact / force sensors | `$ISAAC_SIM/skills/isaac-sim-sensor` |
| Robot asset choice + robot config | `$ISAAC_SIM/skills/urdf-mjcf-to-usd-conversion`, `IsaacLab/source/isaaclab_assets` |

### Environment discovered

* Isaac Sim 6.0.1-rc.7 built from source at
  `/home/ubuntu/linalw/App/isaacsim`; launcher at
  `_build/linux-x86_64/release/python.sh`.
* Isaac Lab checkout: `/home/ubuntu/linalw/App/IsaacLab/IsaacLab`.
* RTX 5090 32 GB, driver 580, CUDA 13.0. Warp 1.13, CUDA toolkit 12.9.
* Public asset root reachable through the local proxy.
* Isaac Sim starts headless in ~6 s; full scene build + 30 s of simulation in ~60 s.

### Robot selection

Requirements: upper body only, two arms, grippers (not multi-finger hands), a single
head-mounted RGB-D camera, point tactile at the grippers.

Surveyed the Isaac 6.0 asset catalogue (S3 listing + thumbnails). OpenArm bimanual is the
only asset that is simultaneously (a) upper-body only, (b) dual-arm, (c) parallel grippers,
(d) open source. Unitree G1, AgiBot A2D, Tien Kung and BoosterT1 are full humanoids with
hands; Galbot G1 is a wheeled base.

OpenArm bimanual (`openarm_bimanual.usd`): 23 links, 22 joints, 2x 7-DoF arms, per-arm
`finger_joint1/2` with a 0.044 m stroke, `ee_tcp` link per arm. Bounds 0.25 x 0.475 x 0.773 m.

### Calibration

`scripts/12_reach_calibration.py` sampled joint space:

* Shoulders at `(0, +/-0.0935, 1.448)` m with the robot base at `z = 0.75` m.
* TCP reach radius max 0.678 m, p90 0.634 m.
* TCP cannot descend below `z ~ 0.898` m.

Consequences for the cell: belt surface at `z = 0.95` m, belt width 0.32 m centred at
`x = 0.28` m (the reachable band at belt height is only ~0.46 m wide), output bins raised on
0.80 m pedestals.

### Failures and fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Script produced no output but exited 0 | Kit fast shutdown discards buffered stdout | flush every log line (`common.say`) |
| `SimulationManager.set_dt` AttributeError | API renamed in 6.0 | `set_physics_dt`; `set_backend("torch")`; `switch_physics_engine("physx")` |
| `RigidPrim.get_world_poses()[0][0]` TypeError | returns `wp.array`, item indexing unsupported | `.numpy()` first |
| Camera view appeared inside the model | OpenUSD optics are in tenths of a scene unit | 16 mm lens = `0.016` on a metre stage |
| `CameraSensor.get_data()` returned a tuple | API returns `(array, metadata)` | unwrap `[0]` |
| `instance_segmentation` annotator segfaults headless | build bug in 6.0.1-rc.7 | use `instance_id_segmentation` (+ `semantic_segmentation`, `bounding_box_2d_tight` are fine); `pointcloud` also segfaults; `occlusion`/`camera_params` raise |
| `Articulation.initialize()` AttributeError | wrapper initialises lazily | construct after `play()` |
| `Articulation.get_world_poses()` returned 1 pose | only root poses are batched | wrap link paths in `RigidPrim` |
| Fruit exploded across the scene | every parked fruit was teleported to the same point and interpenetrated | give each fruit its own far-away parking slot |
| Almost all fruit "fell off" the belt | `spawn_y` was 0.30 m beyond the upstream end of the belt | belt lengthened to 2.40 m, spawn at y = -1.05 |
| Belt transport slower than commanded | surface-velocity solver clamps tangential force by Coulomb friction | commanded 0.30 m/s yields ~0.20 m/s of transport |

### Verified state

* `scripts/10_build_scene.py`: cell builds, robot articulates, belt transports and recycles
  fruit, head camera captures RGB + depth + instance ids. 42 fruit released over 40 s of
  simulated time: 35 recycled at the end, 0 dropped, ~7 live on the belt.
* `scripts/13_belt_test.py`: three fruit of different sizes ride the belt at the correct
  height and constant velocity.

### Next

Point-tactile sensors on the gripper fingers, then a scripted pick-and-place state machine
to generate demonstrations.
