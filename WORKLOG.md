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

## 2026-09-25 - scripted picking (part 2)

### Cell re-laid out around the real gripper geometry

Measurements from `scripts/21_grasp_geometry.py` and `scripts/31_reach_sweep.py`:

* Jaw separation = `0.010 + 2.0 * finger_joint` m (0.010 m closed, 0.098 m open).
* The finger links span about **8 cm below** the jaw centre, so the fingers - not
  the palm - define the grasp height.
* At the pick pose the jaw centre cannot descend below `z ~ 1.20` m with the
  wrist orientation that the pose needs.
* The jaws open along the robot's shoulder axis, so the belt must run along the
  robot's facing direction: fruit travel **toward** the robot along `-X` and
  pass between the jaws.
* The gripper can straddle objects up to ~6.2 cm: 0.098 m opening minus two
  ~0.033 m thick fingers. Larger fruit need a different gripper.

The cell was rebuilt accordingly: belt surface at `z = 1.15` m, belt 1.6 m long
along X, bins on 1.00 m pedestals either side at `y = +/-0.44` m, head camera at
`z = 1.86` m.

### IK

`ArmController` now does 6-DoF damped least-squares IK with an incremental
command (`_q_cmd`) and a *predicted* task error, so the lagging measured pose no
longer winds the integrator up. Two indexing details mattered:

* `Articulation.get_jacobian_matrices()` returns one 6 x n_dof block per link
  **excluding the base link**, so block `k` describes `link_names[k + 1]`
  (verified against a finite-difference Jacobian in `scripts/19_jacobian_map.py`).
* `robot.dof_names` interleaves left/right, so the right arm's DOFs are
  `[1, 3, 5, 7, 9, 11, 13]`, not `[7..13]`.

### Waypoints

`scripts/30_calibrate_waypoints.py` solves and stores `configs/waypoints.json`
(ready / grasp / grasp_lift / bin_above / bin_inside per arm). All poses solve to
about 1 cm. Solving order matters: the low grasp pose only converges when the
solver is warm-started from the ready pose.

### Failures and fixes in this stretch

| Symptom | Cause | Fix |
| --- | --- | --- |
| Every teleport silently did nothing | `dof_positions()` returned a **view** onto the warp buffer, so in-place edits were lost | `np.array(...)` copy |
| Arms stalled at a fixed pose | same aliasing bug | same fix |
| IK oscillated / ran away | error measured at the lagging pose while integrating the commanded joints | predict the task error with the Jacobian |
| IK converged to a wrong configuration | local minima from the hanging pose | random restarts, then warm-started ordering |
| Fruit froze mid-belt | PhysX sleeping bodies ignore conveyor contact forces | sleep threshold 0 + a stalled-fruit keep-alive |
| Fruit launched across the scene | the keep-alive rewrote velocity every step | only nudge fruit whose speed is below 0.05 m/s |
| Waypoints solved in the wrong cell | belt/bin heights were below the arm's reachable band | raise the cell, re-measure with `scripts/31_reach_sweep.py` |

### Verified state

* `scripts/32_hold_test.py`: the arm tracks the calibrated `ready` and `grasp`
  joint configurations to within 0.055 rad and holds the jaw at
  `(0.339, 0.000, 1.242)` m.
* `scripts/33_dof_probe.py`: the gripper tracks commands exactly
  (0.044 -> 9.8 cm, 0.020 -> 5.0 cm, 0.005 -> 2.0 cm, 0.000 -> 1.0 cm).
* `scripts/20_pick_place.py`: reaches the pick pose in 0.52 s (2 mm residual),
  tracks the incoming fruit and detects its arrival between the jaws.

### Open issues

1. The gripper close inside `PickAndPlaceTask.run` does not take effect even
   though the same command works standalone - the finger targets appear to be
   overwritten (or the loop does not advance physics) after the wait loop.
2. `GripperTactile` contact view is invalid: `get_net_contact_forces` asserts,
   so tactile currently reports zero. `Contact`/`IsaacContactSensor` reports
   `is_valid = False` on this build.
3. One `app_utils.update_app(steps=1)` advances several hundred milliseconds of
   simulated time here, so the belt speed is held down to `-0.05 m/s` to keep the
   fruit inside the jaws for a few control iterations. Properly sub-stepping the
   control loop would let the belt run at a realistic speed.
