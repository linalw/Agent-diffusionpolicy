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

## 13. P227p: the place blend must lift clear, and the pear class is a hand-vs-fruit geometry question

### 13.1 The place blend could dip the payload below the line

A pear-only supply (`FRUIT_SUPPLY_SPECIES=pear`, seed 5, 6 attempts,
`pear_6_s5.log`) reads **3/6**, and the three failures are three *different*
mechanisms:

* attempt 2: the catch left the wrist at `tilt0=106.7 deg` with `q_margin=-0.724
  @j7` (a joint beyond its limit) -> `res_end=311 mm`, `force_min=0.00` (the
  catch class);
* attempt 4: `force@onset=0.00`, `contacts@onset=0`, `sep_min=0.2 mm`,
  `fmax=213 N` - the pads met **each other** (the fruit was not between them);
* attempt 3: a **clean lift** (`clean_slip 0.8 mm`, `force_min 6.48 N`,
  `sep_end 64.0 mm`) and then `place0` loses it: `clean_slip_max=318 mm`,
  `onset_row=1`, `clr_win=-74 mm@belt` - the payload went **74 mm below the belt
  top** during the place leg.

The third is the joint blend added in P227n: a joint-space line from the lift
pose to `bin0_above` can sweep the hand through the main belt. The park's own
transit already has the shape this needs (`_ready_transit`: lift clear, then
blend), so the place leg now makes a short **vertical clear move** (`+0.10 m`,
`FRUIT_PLACE_CLEAR`) before the blend. Measured: the pear cell **3/6 -> 5/6**
(`pear_6_s5_clear.log`), and the general cell **23/24** across seeds 5/6/101/202
at **15.1-15.6 s/attempt** (the clear move costs ~0.4 s).

### 13.2 The pear is the pool's marginal fruit, and it is seed-dependent

Pear-only, the class reads **5/6 (seed 5)** and **1/6 (seed 6)** - the largest
fruit (69.9 mm) is the one the hand is marginal on: the finger plate is **76 mm**
wide along the belt (`pad_geometry.log`), i.e. **+-3.5 mm** of centring against
its 69.9 mm, while the catch-up converges to the 6 mm tolerance (4.8-5.9 mm).
The failures carry contact (N 0.96-7.36 N) and no lift (`+0.000..+0.006 m`),
i.e. the payload is contacted and not carried.

**Two levers tested and not adopted**: a tighter catch tolerance
(`FRUIT_DYNAMIC_CATCH_TOL=0.003`) reads **3/6** at seed 6 against the default's
**1/6** but never converges (residuals 2.9-7.7 mm; the loop burns its budget),
and at seed 5 the default already reads 5/6 - a seed flip, not a mechanism.
The close *does* track the fruit per tick (`ik_step` with `frozen_x` and the
fruit's live y/z), so the miss is not a stale aim.

**Named next**: the `FRUIT_DYNAMIC_TRACE=1` per-tick record of a pear close (the
P93 instrument) to separate "the pads missed along the belt" from "the pear
squeezed out", then the hand-geometry price (a wider plate along the belt is the
only lever that changes the +-3.5 mm, and the OpenArm's +17 mm width cell was a
measured negative, `logs/p190`).

## 14. P227q: the pear class is *size + closing-axis offset*, and three levers are negative

Pear-only (`FRUIT_SUPPLY_SPECIES=pear`, 6 attempts), with the handover and carry
diagonals (`pear_6_s6_hd.log`), the catch-up's own numbers separate the class:

| # | outcome | catch residual | jaw - fruit (x, y, z) mm | fruit |
|---|---|---|---|---|
| 0 | FAIL | 5.0 | (+0.1, -4.8, +49.5) | 65-70 mm |
| 1 | FAIL | 17.1 | (+6.1, -8.1, +56.1) | 65-70 mm |
| 2 | FAIL | 11.7 | (+4.9, -0.5, +50.8) | 65-70 mm |
| 3 | FAIL | 10.2 | (+4.0, -3.6, +50.8) | 65-70 mm |
| 4 | FAIL | 10.3 | (+4.3, +0.3, +51.3) | 65-70 mm |
| 5 | **PASS** | 5.8 | (+0.1, -5.6, +49.4) | **60.0 mm** |

The success is the **60 mm** pear; the failures are the **65-70 mm** ones, and
their closing-axis (x) offsets are **4.3-6.1 mm** against a 76 mm plate on a
69.9 mm fruit (+-3.5 mm of centring). The `[carry] grasp_lift` rows show the
consequence: `force@onset=0`, `contacts@onset=0`, `sep@onset=54.7 mm` on a
66.7 mm fruit (the pads are 12 mm inside the fruit's width with **no** contact -
the payload is not between them), while the 60 mm success reads
`force_min=7.47 N`, `sep_min=56.8 mm` on a 60.0 mm fruit.

**Three levers, all measured negative**:

* `FRUIT_DYNAMIC_CATCH_TOL=0.003` (aim tighter): 3/6 at seed 6 against 1/6, but the
  residual never converges (2.9-7.7 mm) and the loop burns its budget; at seed 5
  the default already reads 5/6 (a seed flip).
* `FRUIT_DYNAMIC_MIN_INTERFERENCE=0.005` (close deeper): **1/5**, the same class -
  a deeper squeeze cannot fix an off-centre fruit (the near pad presses 5.5 mm
  in while the far pad stays 4.5 mm out).
* `FRUIT_DYNAMIC_DESCEND_MARGIN=0.25` (start earlier): 5/6 with residuals
  unchanged (P227o §12).
* `FRUIT_DYNAMIC_CLOSE_LOCK_X=0` (let the close re-centre x instead of pinning
  it at the first close tick - the pin is the term that leaves the fruit
  off-centre): **2/6** at seed 6 against the pinned 1/6 (`pear_6_s6_nolock.log`),
  i.e. one attempt more on one cell - a wash, not adopted; the pin itself is a
  measured OpenArm property (P2b).

The regrasp path already re-aims at the fruit's live centre (`ik_step` with the
fruit's x/y/z, no frozen x) and still does not convert the class, and the close
*does* track y/z per tick. **So this is the record's closed class at the pool's
largest fruit**: `logs/p42/SIM_LIMIT.md`'s loaded slide needs a new pad asset, a
force-controlled finger, or a sub-3 mm presentation - and the only lever on the
+-3.5 mm is a **wider plate along the belt**, which the OpenArm's +17 mm width
cell measured as a negative (`logs/p190`).

**The instrument gap this phase found**: `FRUIT_DYNAMIC_TRACE` writes **0 rows**
on the scripted path (`logs/dynamic_trace_0*.json`, all empty) - its
`_AttemptLocal` buffer lives in the attempt thread while `_dynamic_trace_flush`
runs in `run()` on the driver thread, so the flush sees a different (empty)
thread-local. The tracer works on the direct env (one thread). On the scripted
path use `FRUIT_HANDOVER_DIAG`/`FRUIT_CARRY_DIAG`, or fix the buffer's lifetime
(a phase of its own).

## 15. P227r: a throughput pass - the release trim was never on this path, the place clock is the wrong spend

### 15.1 The cycle split

The cell's `[cycle]` rows (23 attempts, seeds 5/6/101/202) are stable to the
hundredth:

| block | s | note |
|---|---|---|
| prepose | **0.71** | fixed blend |
| hover | 0.32-0.80 | `move_to` to the hover |
| descent | 1.86-4.32 | the fruit-arrival wait + the leg (P99: not compressible) |
| close | 1.13-1.18 | the ramp + the freeze commit |
| grip | 1.57-1.59 | the validation ramp |
| lift | 1.82-2.01 | the profile block |
| **place** | **4.00-4.13** | the largest |
| **release** | **1.63** | the **shipped, untrimmed** open-loop holds |
| return | 0.50 | |
| total | 14.2-16.6 | |

### 15.2 The release trim: -0.63 s, exact, and it was never enabled here

P86 measured the S2 trim (`FRUIT_SPEED_RELEASE`: dwell 20 -> 0, the pad/finger
ramps 3 -> 2 = **-76 ticks = -0.633 s**) and P87 shipped it **two-line-scoped**.
The single-arm cell is not a two-line session, so its `[cycle] release=` stayed
**1.63 s**. Measured here (`attempt_6_s5_rel1.log`): **1.63 -> 1.00 s**
(-0.63, exact), **6/6 placed**, and the place-trace landings are **6/6
`on_belt=True`** with `release_bottom` -7..-24 mm (the bin's floor is 70 mm below
the belt top, so a negative bottom is *inside* the bin), impact -1.8..-2.1 m/s.
It now resolves **on** for the single arm (`tasks._single_arm_asset()` ->
`release_speed_resolution`), with the OpenArm and two-line scopes unchanged:
`247`/`248`/`249` pass, and the acceptance is **458/458** identical.

### 15.3 The place clock is the wrong spend

The place block is `clear + blend(150 ticks) + settle(40) + transit`. A faster
clock (100/25 with a 0.07 clear) reads `place 4.0 -> 2.8-3.2 s` and the mixed
cell **5/5 placed** (`clean_slip` 0.0-4.4 mm) - but the **pear cell goes 5/6 ->
3/6** with **two place-leg payload losses** (`pear_6_s5_r2.log`), i.e. exactly
the class the cell is already marginal on. Same tree with the safe clock
(150/40/0.10): the pear cell is **4/5** with one place loss. A **middle** clock
(125/32/0.09) reads `place 3.71-3.77 s`, seed 6 **6/6** but seed 5 **5/6** - and
that one loss is a pear **grasp** failure (`N=3.22`), i.e. the pear's own
variance, not a place cost (`attempt_6_s5_mid.log`). So the ladder is **not
resolvable at n=5-6**, and the only *mechanistic* signal (two place-leg payload
losses at 100/25) says do not go faster: **the safe clock stays** (P88/P89's
rule: a speed cell ships only with a demonstrated non-inferior count).

### 15.4 The cell on the final tree

`run_attempt.sh 6 <seed>`: seed 5 **6/6**, seed 6 **6/6**, seed 101 **5/6**,
seed 202 **6/6** - **23/24 = 96 % placed**, **14.4-14.9 s/attempt** (was
15.1-15.6 before the release trim), and the single loss is the **pear** (the
class P227q closed). Two slots starved in seeds 5/6 (the P56/P58 aperture class,
one `no eligible fruit` each); none in 101/202. No rate is claimed beyond these
samples (P93).

## 16. P227s: the instruction layer drives the bins cell - and its ledger scored the wrong pose

The model's *decision* layer (P114-P116's instruction DSL) was never exercised on
this cell. With a descriptor for the two bins (`logs/p227/bins_two_dest.json`:
dest 0 `bin_plus_y` at `(-0.10, +0.55)`, dest 1 `bin_minus_y` at
`(-0.10, -0.55)`, `reach: auto`) and the instruction the cell *is*

```
grade=A => 0
default => 1
```

(`logs/p227/grade_ab.txt`; `262_sort_plan.py` reads it: **OVERLAP none**, dest 0
40 cells / dest 1 80) the run:

```
[scenario] bins_two_dest: 2 destination(s) [0, 1]
[sort] instruction: 2 rule(s), default=1
[sort] capability: left=[0] right=[1]
[sort] rule 1: grade=A => 0 (arm left)   rule 2: default => 1 (arm right)
[sort] coverage: pool=16 mapped=16 unassigned=0 skip=0 (dest0=8, dest1=8)
```

and **6/6 placed** with every fruit dispatched by the rule it should be: 3
grade-A to dest 0 (+Y bin, `arm=left`), 3 grade-B/C to dest 1 (-Y,
`arm=right`) - i.e. the instruction **reproduces the cell's grade routing**, and
the releases land **6-16 mm** from the instructed target.

**But the ledger read `in_destination=0 mis_sorted=6`** - a scoring defect, not a
delivery defect: `_sort_ledger_row` tested `cfg.on_output_belt(release_pos)`, and
a bin release must be **above the rim** (1.36 m vs a 1.26 m rim, the bin's volume
ending at 1.32), so every bin delivery failed the "over the output body" test
while its nearest destination was right (6-16 mm). Fixed by scoring a
**bin** destination at the **settle sample** - the very read `placed` is scored
on, 0.5 s after the release - carried on the result as `settled_pos` (a copy of a
read that already happens, only when an instruction is armed). A **belt**
destination keeps the release pose: the belt carries the payload away, so its
settle sample is 6+ cm downstream. Re-run: **`in_destination=6 mis_sorted=0`**,
measured settled distances 29-146 mm inside the correct bin, **6/6 placed**
(`attempt_6_s5_instr2.log`).

No-harm: the ledger only runs with an instruction armed, and belt destinations
take the old anchor, so P114/P121's cells are unchanged; `accept.sh` **7/10,
`fingerprint: matches`, `458/458`** identical; `selfcheck.sh` **PASS** with the
new pins in `282`; `106` OK, `107` PASS.
