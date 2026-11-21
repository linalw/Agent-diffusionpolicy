# P227i-l: the Panda's jaw, hand frame and grasp gate (measured)

The owner's single-arm cell moved to a real gripper arm (P225-P227: Franka Panda
+ two side bins, `docs/SINGLE_ARM_BINS_PLAN.md` §4 option B). The open item the
last commit named was "the Panda's finger drive is weak or absent - author the
repo's finger drive profile on it". **That diagnosis was wrong**, and this phase
replaced it with four measurements and one code fix.

Everything here is read-only on the build except the arm-spec authoring
(`src/fruit_sorting/control.py`, `scene.py`), which is byte-identical on the
shipped OpenArm path.

## 1. The drive works - the probe's test pose was blocked

`FRUIT_ARM_KIND=franka scripts/run.sh logs/p227/finger_probe.py`

The asset's own finger drive is k = 400 N/m, c = 80 Ns/m, **maxForce 7.2 N**,
and joint2 is a `PhysxMimicJointAPI` with `gearing = -1` and **no drive of its
own** (cap 0). The repo's profile (`finger_damp02`, k = 1e5, c = 2000) is applied
by `ArmController` and reads back live on both joints.

The joints track **exactly**, in one tick:

```
C0-shipped set_gripper(0.000 .. 0.040) -> q 0 -> 0.040, jaw 0 -> 80.0 mm
C1/C2      raised caps 60/300 N         -> identical (the cap does not bind)
C5-asset   k=1e6, c=100                 -> identical
C6-noGain  k=0                          -> identical (the position target is
                                           enough at this mass)
T40        a 0.040 step completes in 1 tick
```

So P227h's 0.0164-0.0195 m reading was the **probe's end pose** - the gripper
test ran after the reach servo, with the pads already inside the bin's rim - not
the drive. `logs/p227/finger_probe.log`.

## 2. The pad faces are 6 mm apart at `q = 0` - this is why the first grasps failed

`FRUIT_ARM_KIND=franka scripts/run.sh logs/p227/pad_geometry.py`

The finger link prims are a **reference** and report no mesh bound without
`Usd.TraverseInstanceProxies` (the same instance-proxy trap the OpenArm's
collision subtree has). With proxies, each finger has one collider mesh:

| | close (plate width) | along (closing axis) | down (below jaw) |
|---|---|---|---|
| open left/right | +-38 mm | +-34 mm | -11 .. +65 mm |
| **closed (q=0)** | +-35 mm | left -3..+29, right -29..+3 | -10 .. +64 mm |

i.e. the **pad faces are 3 mm either side of the jaw centre when the joints are
closed - a 6 mm gap**. `gripper_value_for_separation(span)` assumed the faces sit
on the link origins (the OpenArm's measured law), so every close was commanded
**6 mm too wide**: the pads reached the commanded span and never touched the
fruit. That is exactly the observed "`sep` == command, nothing held".

`ArmSpec.finger_face_offset` now carries it per arm (OpenArm 0.0, Panda -0.006)
and `ArmController` reads it into `FINGER_FACE_OFFSET`. `logs/p227/pad_geometry.log`.

## 3. The hand frame: `td-x` is the Panda's pick attitude

`FRUIT_ARM_KIND=franka scripts/run.sh logs/p227/hand_frame.py`

At the hanging pose and at the grasp pose the measured axes agree:

* the closed fingers separate along the hand's **-Y**;
* the jaw centre is **+58.4 mm along the hand's +Z** from the TCP (`panda_hand`);
* `top_down_quaternion("x")` - the OpenArm's pick attitude - maps hand -Y to
  world -X and hand +Z to world -Z: **closing across the belt, fingers down**,
  reached at **0.8 mm / 0.11 deg**;
* `top_down_quaternion("y")` is **154 mm / 29 deg** out of reach at the station
  (a wrist-limit pose), and a quaternion built from the measured axes is
  165 mm / 30 deg out (it asked for the fingers *up*).

So the OpenArm's `"x"` attitude transfers; no new attitude was needed.
`logs/p227/hand_frame.log`.

## 4. The reach floor is the attitude, not the gains

`FRUIT_ARM_KIND=franka scripts/run.sh logs/p227/ik_probe.py`

Walking the jaw target down 20 mm at a time at the pick column, attitude held:

| goal jaw z | achieved | attitude error | margin |
|---|---|---|---|
| 1.300 - 1.240 | 0.9 mm | 0.12 deg | 0.72 -> 0.56 rad @ j4 |
| 1.220 | 1.223 | **49.8 deg** | 0.51 |
| 1.200 | 1.223 (23.6 mm xy) | 43.2 deg | 0.47 |

The servo is not the limit (it holds 0.9 mm to 1.240); the **wrist cannot keep
top-down below ~1.24** at this station. The repo's tuned Cartesian drive
(`FRUIT_TUNE_GAINS`: k = 1500, c = 60) adds a constant **-7.6 mm** lag and does
not help. This is P227f's "15.6 mm high" seen as a function of the target.

## 5. The grasp gate: 12/12 held (4 fruits x 3 standoffs)

`FRUIT_ARM_KIND=franka scripts/run.sh logs/p227/hand_frame.py`

A **static** gate (the belt's surface velocity written to 0 - `SortingScene.step`
is `update_app`, so the belt's own `step()` never runs in a probe and the fruit
would otherwise ride 0.12 m during the close): seat the fruit at the pick
station, hold `td-x`, servo the jaw centre to `fruit + dz`, close on the measured
pinch extent at 0.98, lift 100 mm.

| fruit | d | dz=0.035 | dz=0.042 | dz=0.050 |
|---|---|---|---|---|
| apple | 65.2 | HOLD 99.0, slip 21.5 | HOLD 99.4, slip 1.2 | HOLD 99.4, slip 1.6 |
| orange | 65.8 | HOLD 99.2, slip 15.7 | HOLD 99.4, slip 1.1 | HOLD 99.3, slip 0.5 |
| strawberry | 37.2 | HOLD 99.2, slip 4.7 | HOLD 99.5, slip 2.1 | HOLD 99.5, slip 2.1 |
| lychee | 34.4 | HOLD 99.2, slip 1.8 | HOLD 99.4, slip 0.5 | HOLD 99.4, slip 0.7 |

**12/12** at each standoff (lift in mm, slip in mm); the measured link-origin
span at the close is **3.0-3.5 mm wider** than the command on the big fruits
(67.4 vs 64.3 on the apple at 0.042) - the force-capped drive pressing into the
fruit, which is what a hold looks like. `logs/p227/hand_frame.log`.

The contact census (`grasp_contacts.py`, apple, belt stopped) reads the close
**two-sided** and the lift clean: pads [4.04, 4.06] N = 8.10 N total, fruit rises
**+95 mm** with the hand.

## 6. Two things this does NOT settle

* **A fixed jaw height is not equivalent to the per-fruit standoff.** At a fixed
  jaw z = 1.240 only the apple holds (**1/4**) - the small fruits need the jaw
  ~42 mm above *their* centre, and a fixed world height is 10 mm off for a 37 mm
  strawberry. So the Panda's pick aim must be **`jaw = fruit_centre + 0.042`**,
  not the OpenArm's fixed `belt_top + grasp_clearance`. The task's dynamic pick
  already has such a target (`_dynamic_grip_target`); the scripted fixed-pose
  path does not. **No default was changed** - `grasp_clearance` stays 0.095.
* **The moving belt is the next question, not the grasp.** On the live belt the
  close lags the fruit (~30 mm), contacts one pad first and drags the fruit
  110 mm downstream before both pads load; the lift then loses it. That is the
  catch/lead problem the OpenArm solves with `_dynamic_grip_target` + the P143
  moving catch, not a hand defect.

## 7. What shipped

* `ArmSpec` gains `finger_face_offset` (0.0 / -0.006), `joint_root` and
  `link_root`, and `arm_specs()` (two OpenArms, or the one Panda).
* The build's finger **material**, **drive-cap writer**, **cap readback** and
  **header** walk `arm_specs()` instead of hard-coded `openarm_*` prim paths -
  the first Franka build authored neither material nor cap for that reason.
* A real hand of either arm defaults to the measured pad pair `mu = 2.0`.
* `ArmController.FINGER_FACE_OFFSET` reads the spec.
* The cell wiring the bin attempt needs, each scoped to its own cell:
  `tasks._pad_standoff` returns the Panda's **measured 42 mm** tool offset
  (`FRUIT_FRANKA_GRASP_STANDOFF`) instead of `finger_len + PAD_LIFT`'s 70 mm;
  `tasks._place_xy_for` returns the **bin** place point when
  `cfg.output_bins` (it returned the *belts'* lane point, so a bin attempt
  released over the belt); and the waypoint default follows the arm
  (`configs/waypoints_franka.json` for the Panda, the OpenArm file byte-
  identically when unset).
* `logs/p227/franka_waypoints.py` - the repo's calibration flow for one arm,
  writing `configs/waypoints_franka.json` (one arm's `ready`/`wait`/`grasp`/
  `grasp_lift` + each bin's above-pose; both arm labels carry the same
  configurations because the task always builds two controllers and the Panda
  resolves both to its one arm).
* `scripts/282_p227i_arm_spec_selftest.py` + a selfcheck leg; `265`'s material
  pin now accepts the hand-keyed default.

The OpenArm's set, order, offsets and profile are unchanged; `accept.sh` with
every knob unset reads **7/10 = 70 %, 9.5 s/attempt, `fingerprint: matches`,
`190: PASS`**, and its **459 `[fruit]` lines are 458/458 identical** to
`logs/p136/accept_final.log` once the one pre-existing P227 build print
(`robot referenced ... kind=openarm base_z=0.790`) is dropped
(`logs/p227/accept_noharm.log`); `selfcheck.sh` **PASS (0 failures, 1 skipped)**,
`106` OK, `107` PASS (21 checks).

## 8. The cell runs: 4/12 placed, and the failure class is the catch's lead

`bash logs/p227/run_attempt.sh 6 5` / `... 6 6` (`FRUIT_ARM_KIND=franka
FRUIT_OUTPUT_BINS=1 FRUIT_BIARM=0`, the scripted dynamic catch, one arm):

| seed | placed | per attempt |
|---|---|---|
| 5 | 3/6 = 50 % | apple (right) 15.3 s, strawberry (right) 17.0, apple (right) 16.6; peach/lychee/tomato (left) miss |
| 6 | 1/6 = 17 % | lychee (right) 15.3 s; strawberry (right) + 4 left miss |
| pooled | **4/12 = 33 %** | right **4/8**, left **0/7** |

The successful place is **in a bin**: `released at (-0.004, -0.606, 1.129),
placed=True` is inside bin N (x -0.27..0.07, |y| 0.40..0.70), and the cell's
`_place_xy_for` returned the bin, not a belt lane. `logs/p227/attempt_6_s5.log`,
`attempt_6_s6.log`.

The 8 failures are **one class**, and it is not the hand: the handover fires
with the fruit already inside the lead window (`dy=+0.122..0.131 m` against
`lead=0.189`), so the settle loop runs **0 steps**, `coherent axis
1-cos=0.0107-0.0138` is reported **FAILED** ("closing anyway"), the fingertips
are **130-137 mm** from the fruit at the close's start, and the catch-up ends
**1329-1550 mm** out with the payload dragged **1170 mm** across the belt. The
successes are the attempts whose wait loop ran (206 steps on the lychee, 131 on
the apple), where `1-cos = 0.0000` and the fingertips are **34-40 mm** away.
So the Panda cell's next lever is the **catch's lead/settle for this arm**
(one arm, so a fixed lead cannot serve both fruit phases) - not the grip, not
the hand, and not the bins.

## 9. Named next

1. **The catch's lead/settle on this arm**: the failures are all "the handover
   fired with the fruit already inside the lead, 0 settle steps, attitude
   1-cos 0.011-0.014 FAILED, fingertips 130 mm", and the successes are the ones
   that waited. A per-attempt settle (or a lead that adapts to the measured
   approach time) is the lever; `FRUIT_DYNAMIC_LEAD_MARGIN` / the P54 `ACQ`
   formula are the existing knobs, and the record's per-arm lead question
   (P173-P190: left 0.10 s / right 0.20 s on the OpenArm) is the same object one
   arm later.
2. The per-fruit pick aim in the **indexed** path (`jaw_target("grasp")` is a
   fixed height, which holds 1/4 on the static gate) - the dynamic catch already
   uses the measured 42 mm standoff, so this only matters if the indexed
   primitive is ever used on the Panda.
3. Throughput/rate: 12 attempts is a direction, not a rate (P93's rule); a
   claimed rate needs >= 2 seeds with the class ledger on the same tree.

## 10. The selector-floor lever is a measured negative on this cell

The failures say "commit earlier", so the existing knob was tried:
`FRUIT_DYNAMIC_SELECT_S=3.5` (the selector floor 1.5 -> 3.5 s of setup = 0.55 m
of belt at 0.12 m/s), seed 6, 6 attempts (`attempt_6_s6_select35.log`):

```
attempt 1..5: no eligible fruit; active=[('pear', 0.169/0.109/0.049/-0.011/-0.071), ...]
attempt 0:   grasped=False (the same strawberry class), 14.9 s
summary: 0/1 successful
```

so the larger floor **starves the line** - the stocked belt's candidates sit at
0.05-0.39 m, below it, and the arm has nothing to commit to for five slots. That
is the P56/P58 aperture class (the catchable sliver, not the stock). The lever
therefore needs to shorten the **pre-pose** (or settle in place), not widen the
commitment window; a bigger `FRUIT_DYNAMIC_OVERHEAD_S` alone cannot help either,
because the handover is evaluated *after* the pre-pose and the fruit is already
inside the lead by then.
