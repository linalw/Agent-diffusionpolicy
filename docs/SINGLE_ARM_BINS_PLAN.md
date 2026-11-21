# Single gripper arm + two side bins: the delivered cell (measured)

**Status: DELIVERED (2026-11-21, `logs/p227/`).** The cell exists and sorts:
a Franka Panda (one arm) with a bin on each side of the belt, scripted moving
catch, **23/24 = 96 % placed across seeds 5/6/101/202 at 14.4-14.9 s/attempt**,
the single remaining loss the 6.9 cm pear. It is **opt-in** and nothing shipped
moved: `FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 FRUIT_BIARM=0`
(`logs/p227/run_attempt.sh 6 <seed>`), the OpenArm acceptance byte-identical
(458/458 `[fruit]` lines to `logs/p136/accept_final.log`), no motion reference
re-recorded.

## How to run it

```bash
scripts/run.sh logs/p227/franka_waypoints.py     # writes configs/waypoints_franka.json
SKIP_SELFCHECK=1 bash logs/p227/run_attempt.sh 6 5
```

The recipe is the scripted dynamic catch with the **per-fruit** standoff
(`tasks._pad_standoff` -> 42 mm measured), the bins as the places
(`tasks._place_xy_for` under `output_bins`), the calibrated place transit
(`_carry_leg`: vertical clear -> joint blend to `bin{index}_above` -> the
Cartesian leg), the release trim defaulted on for the single-arm asset, and the
two close/catch criteria made arm-aware. Each mechanism, its number and its
negative controls are in AGENTS.md's P227i-P227r paragraphs and
`logs/p227/RESULTS.md`.

## What the cell measured, in one table

| item | number | evidence |
|---|---|---|
| static grasp gate (4 fruits x 3 standoffs) | **12/12 held**, 99.0-99.5 mm lift, slip 0.5-2.1 mm | `logs/p227/hand_frame.log` |
| the pad faces at q=0 | **6 mm apart** (the first closes missed by exactly that) | `logs/p227/pad_geometry.log` |
| the hand frame | closing = hand -Y; `td-x` = 0.8 mm / 0.11 deg; `td-y` 154 mm / 29 deg out | `logs/p227/hand_frame.log` |
| the reach floor | jaw z **1.240** at 0.9 mm, attitude breaks at **1.22** | `logs/p227/ik_probe.log` |
| the +Y bin by the Cartesian servo | **181-223 mm** (148 mm routed); **9-10 mm** from the calibrated above-pose | `logs/p227/place_reach_*.log` |
| the cell | **23/24 = 96 %**, 14.4-14.9 s/attempt | `logs/p227/attempt_6_s*_rel.log` |
| the pear (6.9 cm, the pool's largest) | **the only class**: 60 mm holds, 65-70 mm fails at a 4.3-6.1 mm closing-axis offset | `logs/p227/pear_6_s6_hd.log` |

## The limits, named

* **The pear** (65-70 mm in a 76 mm plate, +-3.5 mm centring against a 4.8-5.9 mm
  servo residual) is `logs/p42/SIM_LIMIT.md`'s loaded-slide class; four software
  levers are measured negative (catch tolerance, interference, descent margin,
  close x-lock). The levers are hardware: a wider plate, a force-controlled
  finger, or a sub-3 mm presentation.
* **Two slots starve in 3 of 4 cells** (one `no eligible fruit` each): the
  P56/P58 aperture class, not a cell defect.
* The **learned lane is not on this cell**: the policy lane runs the OpenArm's
  joint space, so a Panda policy needs its own collection (a phase of its own).

---

The owner's request: replace the two output conveyors with a bin on each side of
the robot, run a gripper-type single arm, and use the reduced occlusion to
improve the learned lane. The old scene is backed up at
`logs/p225/scene_belts_backup/` (assets/conveyor/scene + configs; the code
stays the shipped default, nothing deleted).

## Background: the pre-integration analysis (OpenArm, 2026-11-21)

The sections below are the **original plan's analysis on the OpenArm** - the
reason the arm was changed rather than the bins moved: the side-bin place pose is
outside that arm's workspace at any reachable bin height, so the cell needed a
longer-reach arm. They are kept as the decision record; the delivered cell and
its numbers are the status section above.

## 1. The direct lane is already a single arm

`SortingRLEnv` runs **one active arm per attempt** (`self._active`, chosen from
the fruit's grade); the other arm is parked. The bimanual scheduler is the
scripted two-line (`FRUIT_BIARM=1`) and is not on the learned path. So the
dual-arm complexity the request wants to remove is already absent from the
policy lane; what remains is the **output-belt geometry**.

## 2. The side-bin place pose is not reachable by this arm

The place point must be where the arm can hold a pose. P90's map put the
reachable place box at `x 0.38-0.48`, `|y| 0.35-0.55`, **z 1.450** (the belt
top + 0.10). A bin whose rim sits **below the belt's fruit top** (z <= 1.18) is
what would remove the occlusion, so the side-bin place height was probed with
P90's own instrument (`NAT`, the position-only solve the place leg runs):

```
FRUIT_P90_Z=1.05,1.15 FRUIT_P90_X=0.33,0.38,0.43,0.48 \
FRUIT_P90_Y=0.40,0.45,0.50,0.55,0.60 FRUIT_P90_MODES=NAT
```

**0 of 60 cells pass.** The best residuals are **105-225 mm** (the 6 mm bar),
with joint margins at 0.00-0.04 rad: at |y| 0.40-0.60 the wrist runs into its
limits when the target drops 0.3-0.4 m below the shipped place height. The
shoulder-to-target distance is inside the 0.68 m reach - the **pose**, not the
distance, is what fails.

A bin at the only reachable height (z ~1.30-1.45) has its rim **above** the
belt's fruit top (1.20), i.e. it shadows the approach exactly as the output
belts do (measured: the top-down camera sees the fruit 14.6 % of the cycle, and
the downstream camera that can see it resolves a 6 cm fruit at 2.2 m to 5.1 px,
below the fit floors - `logs/p225/RESULTS.md` 4r).

## 3. What the request therefore needs

A **longer-reach gripper arm** (UR5e / UR10e / Franka class, ~0.85-1.3 m) whose
wrist can hold a place pose at |y| ~0.5 and z ~1.0-1.1 beside the belt. This
install has **no such asset**: the repo's only robot is the OpenArm
(`assets/openarm_flat`), and a search of the Isaac Sim extension tree finds no
Franka/UR USD (only test scripts that reference them; the asset packs are not
installed). Integrating one is a project, not a configuration change:

1. **Asset**: import the arm's USD (asset pack or network), author it in
   `assets.py` beside `OPENARM_*` (joint names, DOF order, gripper, TCP).
2. **Controller**: `ArmController`'s joint/tcp/finger interface for the new DOF
   order and gripper command; `gripper_value_for_separation` re-measured.
3. **Calibration**: pick/place/above/lift waypoints via the existing
   `scripts/52_calibrate_waypoints*.py` flow, then the P90 place map and the P66
   pick map on the new arm (the criterion and grid are already registered).
4. **Scene**: side bins at the now-reachable low height (floor ~1.0, rim
   <=1.18), the output belts removed (the bins default becomes the scene).
5. **Re-baseline**: both motion references, the acceptance, the two-line gate
   and every store; the policy's camera view changes (new arm geometry in
   frame), so the direct lane needs its own collection or a view-preserving
   camera mount.

## 4. The two options on the table

* **A - keep the cell** (the shipped deliverable): single active arm, two output
  belts, **0.15 = 83.3 %** and **0.12 = 62.5 %** placed, 6.8-11.4 s per placed
  fruit, no scripted skill route. The occlusion is real but the perception's
  goal is accurate enough for these rates.
* **B - the requested cell**: source and integrate a longer-reach arm, then the
  bins at a low height and the occlusion gain. Scoped by the checklist above;
  the first gate is the asset (does an importable UR5e/Franka USD exist in this
  environment?), the second is the P90-style place map on it.
