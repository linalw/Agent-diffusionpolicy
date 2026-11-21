# Single gripper arm + two side bins: what this cell allows (measured)

The owner's request: replace the two output conveyors with a bin on each side of
the robot, run a gripper-type single arm, and use the reduced occlusion to
improve the learned lane. The old scene is backed up at
`logs/p225/scene_belts_backup/` (assets/conveyor/scene + configs; the code
stays the shipped default, nothing deleted).

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
