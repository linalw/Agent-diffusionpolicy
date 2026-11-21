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

## 11. P227n: the left label's mirrored attitude, the place prim paths, and the calibrated place transit

The P227m cell failed on the **left** label (0/7) and placed on the right (4/8).
Three measurement-led fixes convert it - the pre-pose/settle question P227m
named was the wrong lever; the real defect is an **arm-asset assumption leaking
through the arm *label***.

### 11.1 The left label got the OpenArm's mirrored pick attitude

`logs/p227/acq_diag_3_s6.log` (3 attempts, `FRUIT_ACQ_DIAG=1
FRUIT_HANDOVER_DIAG=1`):

```
attempt 0 (right)  premove err =   8 mm  jaw=[0.323, 0.0004, 1.280]
attempt 1 (left)   premove err = 144 mm  jaw=[0.157, 0.1109, 1.301]
```

The premove (the catch's first move to the hover) *stalls* 144 mm out on the
left, with a 111 mm lateral error, and the attempt then closes 137 mm behind the
fruit. The cause is the attitude: the moving catch sets
`hold = top_down_quaternion("x")` and then **mirrors it for the `left` arm**
(`if arm_name == "left": hold = mirror_across_xz(hold)`) - correct for the
bimanual OpenArm (two mirrored arms; `scripts/97_reach_probe.py`: 2.1 mm with
the mirror against 28 mm without), **wrong for the single-arm Panda**, which
authors one arm serving both labels: the mirrored quaternion asks for the pads to
close *along the belt*, the pose that P227j measured at 154 mm / 29 deg out of
reach. `mirrored_arms()` now gates all three sites (`_run_impl`'s indexed hold,
the catch's wait-at-hover hold, the coherent block), so the OpenArm is unchanged
and the Panda gets `td-x` on both labels. Measured: the left premove **144 ->
7 mm**, and the left's first grasp holds (`lift +0.384 m`, `slip 2.5 mm`,
`force 7.46 N`).

Probe that rules out the two obvious alternatives (`premove_probe.py`): the same
target converges to **18-19 mm** from the calibrated `grasp` pose at x = 0.249 /
0.316 / 0.34, with and without an IK-integrator sync, and after the *other*
label drove the shared arm - so it is neither the target's x nor a stale
`_q_cmd`; it is the attitude.

### 11.2 The place leg crashed on the OpenArm's finger prims

`_fingertip_lowest_z` hard-coded `/World/OpenArm/openarm_<side>_{left,right}_finger`.
On the Panda that is a null prim and `UsdGeom.BBoxCache.ComputeWorldBound`
raises - the attempt dies **after** a good carry
(`logs/p227/attempt_6_s6_fix.log`). It now walks `arm_spec(side).finger_link_names`
at `link_root` (the OpenArm's four prims, same order, so its stream is
unchanged) and skips an invalid prim instead of raising.

### 11.3 The +Y bin is unreachable by the Cartesian servo, reachable from the calibrated pose

`logs/p227/place_reach_probe.log` drives the carry's own primitive
(`move_to`, 900 steps, 10 mm tolerance) from the calibrated `grasp_lift`:

| bin | x | z | final distance |
|---|---|---|---|
| +Y | -0.10 / -0.02 / +0.06 | 1.38 / 1.30 | **181-223 mm** (every cell) |
| -Y | same cells | same | 18-31 mm |

and two routed waypoints only bring +Y to **148 mm**
(`place_reach_routes.log`). From the waypoint file's own `bin0_above`
configuration (already solved at 3.2 mm) the same servo reaches **9.1-10.0 mm**
(`place_reach_staged.log`). So the place leg now **blends the joints** to that
calibrated configuration (min-jerk, the pre-poses' own primitive, payload in the
pads) and then runs the shipped Cartesian transit - scoped to the single-arm
asset, so the OpenArm's place legs keep their Cartesian-only path.

### 11.4 The cell

`run_attempt.sh 6 <seed>` (the scripted dynamic catch, one arm, `FRUIT_BIARM=0`):

| seed | placed | grasped | note |
|---|---|---|---|
| 5 | **6/6 = 100 %** | 6/6 | both labels, both bins |
| 6 | **3/5** | 4/5 | one wedge (RTX) after 5; the strawberry at 31.13 N is the closed small-fruit class |
| 101 (fresh) | **6/6 = 100 %** | 6/6 | both labels, both bins |
| pooled | **15/17 = 88 %** | 16/17 | vs **4/12 = 33 %** before the three fixes |

`logs/p227/attempt_6_s5_fix2.log`, `attempt_6_s6_fix3.log`,
`attempt_6_s101_fix.log`. No rate is claimed beyond these samples (P93's rule);
what is claimed is the mechanism: the acquisition class (left attitude) and the
+Y place class are gone, and the residual is the closed small-fruit grip.

## 12. P227o: two closed-loop criteria calibrated for the other hand

With §11's fixes the cell read 15/17 and the residual was the **3.1 cm
strawberry** (seed 6, `attempt_6_s6_fix3.log`): `dynamic close: sustained
contact after 4 ticks (force=29.88 N, span=85.9 mm); freezing the closing
command at 87.9 mm` on a **31.4 mm** fruit - i.e. the close was frozen *wide
open*. Two shipped criteria assume the OpenArm's pad geometry:

1. **The freeze** (`freeze_close`): force + a stalled span. The docstring already
   records that force alone false-fires on a 3 cm berry at an 89 mm span
   (`logs/p2b_diag_before_1` A4); the single-arm hand adds the second term - its
   76 mm plates and the drive's breakaway hold the span for the first ticks - so
   both are true before the pads are near the fruit. A freeze **wider than the
   fruit** is not a loaded pinch: the criterion now also requires
   `sep <= pinch_width + 10 mm` on the single-arm asset (`mirrored_arms()` gates
   it; the OpenArm keeps the shipped test). Measured: the strawberry then freezes
   at **58.3 mm / 7.37 N / span 63.2 mm** and places (31.26 N spike, real grip).

2. **The catch-up's stop point** (`desired_tip = fruit + _dynamic_pad_lift`):
   the shipped 10 mm is the OpenArm's pad lift under its jaw offset. The
   single-arm hand puts the pads 0-65 mm below the jaw centre and the grasp aim
   42 mm above the fruit's centre, so the loop was asked for a point **33 mm**
   away from any correctly-aimed hand and chased a phantom: the row printed
   **27-29 mm on every attempt, successes included** (`attempt_6_s6_cs05.log`),
   and the diag shows the hand was actually within **~1 mm** in x/y. Using the
   arm's own pair (`_pad_standoff(True) - _fingertip_offset`) makes the residual
   the real error: **27 -> 4.8-5.9 mm** (inside the 6 mm tolerance) and the
   attempt falls **17.0 -> 14.2-14.8 s** (the phantom chase was ~2 s/attempt).

**The cell on the final tree** (`run_attempt.sh 6 <seed>`): seed 5 **6/6**,
seed 6 **6/6**, seed 101 **4/5**, seed 202 **6/6** - **22/23 = 96 % placed**,
14.2-14.8 s/attempt, against **4/12 = 33 %** at the start of the P227i arc.

**Two knobs tested and not adopted** (env only, no code): the descent margin
`FRUIT_DYNAMIC_DESCEND_MARGIN=0.25` reads 5/6 with residuals unchanged
(21-29 mm), and `FRUIT_TRACK_CATCH_SPEED=0.05` reads 6/6 on one seed with the
residuals identical to the digit - a branch draw, not a mechanism (P93's rule);
the diag shows the catch was already accurate, so neither was the lever.

**The residual class is the 6.9 cm pear** (3 instances in 23 attempts, e.g.
seed 101 attempt 2: `grasped=False`, contact 7.32 N, `lift +0.000`): the hand
reaches it, closes on its extent, and the payload does not follow the lift -
the record's loaded-slide class at the pool's largest, tapered fruit.
