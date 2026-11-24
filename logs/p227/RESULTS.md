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

## 17. P227s (ii): a routing the shipped grade rule cannot produce

The instruction layer is only *demonstrated* on this cell if it can drive a
delivery the cell could not make otherwise. With the same bins descriptor and

```
size<55 => 1
default => 0
```

(`logs/p227/size_rule.txt`; `262_sort_plan`: **OVERLAP none**, dest 0 78 cells /
dest 1 42; the pool covers dest0=11 / dest1=5) the cell reads:

```
[sort] attempt 1 idx=4  apple  d=6.5cm grade=B arm=left  rule=2 dest=0 (+Y) in_dest=1 dist= 32mm
[sort] attempt 2 idx=14 orange d=6.6cm grade=C arm=left  rule=2 dest=0 (+Y) in_dest=1 dist= 88mm
[sort] attempt 3 idx=12 peach  d=6.9cm grade=A arm=left  rule=2 dest=0 (+Y) in_dest=1 dist= 42mm
[sort] attempt 4 idx=13 kiwi   d=5.4cm grade=A arm=right rule=1 dest=1 (-Y) in_dest=1 dist= 55mm
[sort] attempt 5 idx=6  tomato d=6.6cm grade=A arm=left  rule=2 dest=0 (+Y) in_dest=1 dist= 80mm
[sort] attempt 6 idx=1  lychee d=3.4cm grade=B arm=right rule=1 dest=1 (-Y) in_dest=1 dist=126mm
[sort] ledger: attempts=6 assigned=6 released=6 in_destination=6 mis_sorted=0
```

**6/6 placed, 6/6 in the instructed destination, 0 mis-sorted**, and the
witnesses are exactly what the grade rule cannot do: a **grade-A kiwi (5.4 cm)
into the -Y bin** (grade A goes +Y) and a **grade-B apple / grade-C orange
(6.5/6.6 cm) into the +Y bin** (B/C go -Y). The arm label follows the
destination (`_arm_for_destination`), which on this cell is one physical Panda -
the capability map's bookkeeping, not a second arm. Settled distances 32-126 mm
inside the correct bin.

So the cell's **decision layer** is functional and its **endpoint is
measurable**: the model sorts to where the instruction says, including routings
the shipped rule cannot express, with the ledger's assignment accuracy as the
number.

### 15.5 The starved slots are intermittent, and P99's diagnostic could not catch one

`FRUIT_BED_DIAG=2` (P99's selector instrument: the floor plus one row per live
fruit with its first refusing predicate) was run at seeds 5, 6 and 101 - and
**no cell starved** (`attempt_6_s{6,101}_bed.log`; seed 5's earlier diag cell
also read 0). The class is therefore **intermittent**: it appeared once each at
seeds 5, 6 and 101 in the P227r/P227s runs (1 slot of 6-7), and the state recorded
in those rows is a **pool-position** one, not a defect - the active list at the
starved slot holds fruit at 0.549/0.394 m (the selector floor is ~0.399) with the
rest past the station or on the output side. It is not reproducible on demand, so
the refusal reason stays unmeasured and the class is recorded, not fixed.

## 18. P227t: the first demonstration store for this arm - and the provenance it needed

Option (b) of the owner's choice - put the learned lane on this cell - starts with
the artifact every policy needs: a **demonstration store in this arm's joint
space**. Collected with the shipped collector in its single-arm mode
(`FRUIT_EPISODES=12 FRUIT_DEMO_DIR=datasets/p227_panda FRUIT_ARM_KIND=franka
FRUIT_OUTPUT_BINS=1 FRUIT_BIARM=0 FRUIT_CAMERA_RES=240,424`):

```
[collect] mode=single_arm scheduler[FRUIT_BIARM=0(explicit) FRUIT_BIARM_TWOLINE=0(biarm-off)] episodes=12 dynamic=True
collected 12 successful episodes into datasets/p227_panda (attempts=13) gate_open=0.00s total
```

**`106`: entries=12 files=12 index_frames=2137 file_frames=2137 windows=1933
unique_content=12 OK.** Each episode is `191 x {joint_positions (9), action (9),
goal (8), image_rgb 240x424, depth, target mask, fruit_position, tcp, jaw,
cmd_tcp}`, and the action's arm columns are plainly the Panda's
(`[0.441, -1.038, -0.260, -2.545, -0.225, 1.521, -0.489]`, min/max -2.72/1.88) -
not the OpenArm's.

### The provenance this needed (two arm-specific labels, both fixed)

1. **The store did not name its arm.** `assets.scene_provenance` carried the
   collider set, the camera, the lanes and the finger plate, but **not the arm
   asset**: a Panda store and an OpenArm store differed only by an `assets.py` md5
   that moves for every unrelated edit. It now carries
   `scene.arm = {kind, usd, resolved, labels, arm_joints, finger_joints,
   finger_links, tcp_link, open_value, jaw{offset, per_joint, face_offset}}`,
   built from the resolved `ArmSpec` - one builder, both manifest writers - and it
   degrades to `{kind, usd, resolved: false}` on the CPU manifest probes that have
   no simulator. A manifest without the key predates P227t.
2. **The drive read-back compared against the OpenArm's cap.**
   `_finger_drive_readback` compared every joint's read-back against
   `finger_maxforce_intent()`, whose "asset's own" value is the OpenArm's
   **10 N** - so this arm's manifest read `profile: custom` and
   `readback_matches: false` while its joints read the shipped pair
   (k = 1e5, c = 2000, cap **7.2 N**). A cap is only *intended* when the build
   wrote one (`FRUIT_FINGER_MAXFORCE` set); with it unset the drives keep the
   asset's own caps, so the cap check now runs only then and the k/c check still
   proves the programmed pair. Re-collected store:
   **`profile: finger_damp02`, `readback_matches: true`**, joints
   `panda_finger_joint1 {k 1e5, c 2000, maxForce 7.2}`, `panda_finger_joint2`
   the drive-less mimic (0). The collector's log line now names the read-back's
   own first row, so another arm no longer prints "no finger joints found".

### What this implies for the policy (measured, not assumed)

The action space is **structurally the same** as the OpenArm's (7 arm joints + a
finger scalar) but the **joint values are a different arm's**, so the existing
checkpoints and their anchor store cannot be reused: the lineage fine-tune uses
`demos_v11` as the anchor, and those demonstrations are OpenArm joint
trajectories. P144 measured that dropping the anchor (`--base ""`) on 45 episodes
**destroys the grasp** (0/12 on either camera), so a Panda policy needs either a
much larger from-scratch store than 12 episodes or a different recipe - the
next decision this lane owes, and the reason this phase stops at the artifact
plus its provenance rather than a fine-tune that would be a coin flip.

### 18.1 The long run found a scenario defect: a bins cell never recycles a placed payload

The first 48-episode shard read **17 successes in 144 attempts**
(`collect_panda_c1.log`) - against the gate's 6/6 on the same tree - and the log
carried only **17 `episode N:` rows**: the other 127 iterations were the
collector's **silent `select_target -> None`** (`continue` with no print). The
cause is not the arm: `FruitSpawner.update`'s end-of-line sweep only recognises a
belt's **discharge tray** (`cfg.on_output_tray`), so in a bins cell a placed
payload stays in the bin forever and the **16-fruit pool drains after ~16
placements**. (The gate never sees it: six attempts.)

Fixed in `fruits.py`, scoped to `output_bins`: a payload inside a bin's volume
(`output_lane_of`), nearly still, is discharged after the tray's own dwell
(`output_tray_dwell_s`) with the same `discharged` counter and a
`[bin N]` tag; the shipped belt/tray tests are untouched. Re-run of the same
shard: **48 successes in 49 attempts**, the recycling rows reading
`discharged to the bin at (-0.10,-0.57) (settled 17.6s) [bin 1]` - the dwell is
the collector's update cadence (it pumps the feeder between attempts), so the
payload is recycled at the next attempt boundary, which is what the bin is for.

**The shard**: `datasets/p227_panda_c1`, **48 episodes / 7912 frames / 7096
windows, `106` OK**, `profile: finger_damp02`, `readback_matches: true`,
`scene.arm.kind: franka`, `collection.mode: single_arm`. With
`datasets/p227_panda` (12 episodes) this is the arm's first **60 episodes** of
demonstrations - the precondition for any policy work, and the defect above was
the reason a longer collection could not have been made before.

### 18.2 The learned lane's structural blocker, found by a one-episode smoke

With 60 episodes on disk the next question was whether the **direct env** can run
this arm at all. It starts
(`FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 FRUIT_OBS_SPEED=1
scripts/run.sh scripts/110_rl_rollout.py --presentation direct --episodes 1
--seeds 901 --ckpt checkpoints/p177_full/policy_best.pt`): the checkpoint loads,
`[rl] env ready`, the episode picks a lychee - and then the policy's normaliser
rejects the observation: **shapes (13,) against (26,)**.

The proprio is the **whole articulation's DOF vector** + the finger + the two
tactile forces (`rl_env.proprio`), i.e. **25 on the bimanual OpenArm** (22 joints)
and **13 on the single Panda** (9 joints + 1 + 2 + the speed channel). But the
**store** declared `PROPRIO_DIM = 25` as a module constant
(`policy/data.py`), while its own windows concatenate the *actual* arrays
(`joint_positions` 9 + finger + tactile = **12**). So a store from this arm
declared 25 and produced 12, and no checkpoint of either width can train on it.

Fixed: `EpisodeStore.proprio_dim` is now the **store's own** width - derived from
its first episode (`joint_positions.shape[1] + 1 + 2 [+ speed] [+ cmd]`), with a
raise if the episodes disagree, and the constant keeps serving as the empty-store
fallback. Measured: `datasets/p227_panda_c1` -> **12** (9 + 3; 13 with the speed
channel), `datasets/demos_v11` -> **25** (22 + 3) unchanged. `selfcheck` PASS (the
P28/P141 width legs hold).

**What remains for the lane** is a training run whose model is built for 12/13-D
*and* whose recipe does not use the OpenArm anchor (`demos_v11` is another arm's
joint space; P144: `--base ""` on 45 episodes destroys the grasp, 0/12) - with 60
episodes the honest form is a small **from-scratch** cell whose endpoint is the
interface end to end (train -> deploy -> episodes), not a rate.

## 19. P227v/w: the model is trained *for this arm* - recollect, retrain, deploy

The owner's instruction for this draft was explicit: **recollect with the new
arm, and change the model to fit the single arm**. That is now the measured
pipeline, end to end.

**1. Recollect (P227u fixed the blocker; P227t the provenance).** The arm's store
is `datasets/p227_panda` (12) + `datasets/p227_panda_c1` (**48**, 7912 frames,
7096 windows, `106` OK) = **60 episodes**, collected at **48 successes in 49
attempts** once the bins cell recycled its payloads.

**2. Change the model (two width defects, both arm-constant).**

* the **store** declared `PROPRIO_DIM = 25` (the OpenArm's 22 joints + 3) while
  its windows concatenate the store's own arrays: the Panda's 9 + 3 = **12**
  (P227v);
* the **env's** checkpoint guard compared against the same constant, so the
  arm's own 12-D artifact was refused ("this environment builds 25-D proprio",
  P227w) - it now derives the width from its own articulation (`len(dof_names) +
  1 + 2 [+ speed] [+ cmd]`).

With those, `scripts/50_train_policy.py` - the **from-scratch** trainer that
sizes the network from the store - is the arm's own recipe:

```
[train] 48 episodes, 7096 windows; proprio_dim=12 goal_dim=8 speed_trace=0/48
[train] skill label histogram: {'approach': 2980, 'grasp': 707, 'lift': 4215, 'place': 10}
[train] device=cuda parameters=4.59M
epoch 20/20 train=0.0341 val=0.0386 router_acc=0.994
[train] best val loss 0.0325; checkpoint in checkpoints/p227_panda1
```

**3. Deploy (the interface, end to end).** `110_rl_rollout.py --presentation
direct --episodes 2 --seeds 901 --ckpt checkpoints/p227_panda1/policy_best.pt`
loads the 12-D artifact, `[rl] env ready`, and both episodes run to their horizon
(1266 / 1386 ticks, `[rl] episode` rows with outcomes). Both fail
(`fruit fell off the line`) - a 20-epoch model on 48 episodes is not a policy;
what this cell proves is the **lane**: recollect -> train in the arm's own space
-> deploy -> episodes, with no OpenArm anchor anywhere.

**What the next unit owes**: more data (the lineage's from-scratch runs used
150-200+ episodes; 60 is a first cell), then the learning curve on this arm - and
note the skill histogram the trainer printed: `place` has **10** labelled windows
against 4215 `lift`, so the place phase is under-represented in 60 episodes and
the next collection should be sized for it (or the label weighting revisited).

## 20. P227x: 156 episodes, a trained model, and the two measured blockers of the lane

**The store.** `datasets/p227_panda` (12) + `_c1` (48) + `_c2` (**96 in 100
attempts**, seed 902) merged into `datasets/p227_panda_all`: **156 episodes /
25775 frames / 23123 windows, `106` OK**. The merge first **lost the provenance**
(the merged manifest read `scene.arm: null` while every shard carried
`kind: franka`); `41_merge_demos.py` now carries the shards' descriptive blocks
(`scene`, `physics`, `supply`, `camera_res`, `fixed_stepping`, `episodes_target`,
`seed`) when they agree and **reports the ones that disagree** - here only
`episodes_target` (12/48/96, by design). The merged store reads
`arm: franka`, `panda_joint1/2`, `profile: finger_damp02`.

**The model.** From scratch, sized by the store (`50_train_policy.py`):
`proprio_dim=12 goal_dim=8`, **4.59 M parameters**, 12 epochs at batch 64 -
`epoch 12/12 train=0.0286 val=0.0276 router_acc=0.990`, best val **0.0276**
(against 0.0325 for the 48-episode model; the OpenArm lineage's fine-tunes sit at
0.013-0.026). Checkpoint `checkpoints/p227_panda156`.

**The deployment** (3 episodes, seed 901): the interface is complete - the 12-D
artifact loads, `env ready`, and every episode closes on the fruit
(`policy closed on the fruit (finger=0.0075..0.0267, |jaw-fruit|xy=14.8..15.0
cm)`) - but **at 148-150 mm**, i.e. exactly at the `FRUIT_POLICY_CLOSE_DIST=0.15`
gate and then "fruit did not follow the gripper". That is P143's finding on the
other arm, and its cause is here too: **the demonstrations start at the pick
pose** (the collector records from the pre-pose), so the policy's first
observation is a state the demos only hold - it has no approach to clone, and the
episode starts where the demos start. P145b's fix is the one this arm needs:
collect and deploy from the **wait** pose (`FRUIT_DIRECT_START=wait` + the
`wait` waypoint this arm already calibrated) so the approach exists in the data.

**One more property the trainer reports**: the skill histogram over 156 episodes
is `approach 9662 / grasp 2336 / lift 13735 / place 42` - the place phase is
**0.18 %** of the windows even after 2.6x the data, so it is a labelling/window
property of this episode shape (the labeller's `place` band is narrow), not a
missing phase: the episodes do reach the bin (fruit y 0.50 -> -0.55, z settles
1.11). A place-weighted cell (or a wider label band) is the training-side lever
if the place phase is what the next checkpoint must own.

## 21. P227y: the deployment's start pose - three hard-coded sources, one fixed by measurement

An **offline** check of the store showed the demonstrations are right (the finger
command drops below 0.030 at **`|jaw-fruit|xy` 1.4 mm** p50 over 156 episodes), so
the deployment's close at **14.8-15.0 cm** had to be an interface mismatch. The
first recorded episode compared against a demo settled it: the rollout's frame-0
joints were **~4 rad** from the demos' (`[-0.804,-0.078,1.329,...]` against
`[0.441,-1.037,-0.261,...]`). Three sources are hard-coded for the OpenArm:

1. **`rl_env` loaded `configs/waypoints.json`** for its own start/park poses
   (3497) instead of the task's file, so the reset teleported the Panda to the
   **OpenArm's joint values**. Fixed: `self.waypoints = self.task.waypoints`
   (the task already resolved `FRUIT_WAYPOINTS`/the arm's default; on the OpenArm
   both are the same file). Measured: the residual start-pose distance fell
   **~4 rad -> 0.456 rad** (left/bin-0, similar fruit x).
2. **The demos' frame 0 is a linear family in the fruit's x** (P160's
   `configs/start_pose_family.json`, fitted on the OpenArm). Fitted **this arm's**
   family on the 156 episodes - `q_j(x) = a_j + b_j x`, **rms 0.006-0.018 rad**
   (mean 0.011, the OpenArm's own is 0.014-0.017) - into
   `configs/start_pose_family_panda.json`, used with
   `FRUIT_DIRECT_START_ALIGN=1 FRUIT_START_FAMILY=...`.
3. **`119_rl_fidelity.py`'s width feed** only accepted 25/26, refusing this arm's
   12-D artifact; it now feeds the checkpoint's own width from the store (a width
   the store cannot supply still refuses). The readout then measures the model:
   **0.100 rad / finger 0.0010 / phase 95 %** (approach 100 %, grasp 100 %,
   lift 90 %) - the model *is* usable on its demonstrations.

**What is still misaligned, measured**: the residual 0.456 rad sits on j4/j6/j7
(the aligned teleport lands where the family says, then the reset's settle and the
first action move it), and the deployment still closes at the gate distance
(`policy closed on the fruit (finger=0.0046, |jaw-fruit|xy=14.9cm)`), now with
`fruit left the pick station during the close (494 mm)` instead of the earlier
"did not follow". The instrument for the next pass is the recorded pair
(`logs/p227/obs_cmp2/` against `datasets/p227_panda_all/`): per-channel diffs at
frame 0 and after the first action, which is exactly how the two fixed sources
above were found.

## 22. P227z: the learned lane on this arm - 0/7 -> 11/12 placed, from six interface defects

The demonstrations were already right (the finger command drops below 0.030 at
`|jaw-fruit|xy` **1.4 mm** p50 over 156 episodes), so a deployment that closed at
**14.8-15.0 cm** had to be an interface mismatch. Section 21 fixed the first two
sources; this one found four more and then closed the lane. Every fix is
**measured**, and the instrument is always the same pair: one recorded rollout
(`--record`) diffed against the store's own frame 0, channel by channel.

### 22.1 The six defects

| # | defect | evidence | fix |
|---|---|---|---|
| 1 | `rl_env` loaded `configs/waypoints.json` (the **OpenArm's** joints) for its own start/park poses | rollout frame 0 was **~4 rad** from the demos' | `self.waypoints = self.task.waypoints` |
| 2 | the start family had **only a `left` key** while the one Panda serves both labels, so every `right` episode fell through to the IK form | `|q0 - family|` = 0.002 rad on `left` episodes, **0.468 rad** on `right` | the family is written under both keys (verified: the two bins fit the same line, rms 0.010/0.011 rad) |
| 3 | `FRUIT_DIRECT_START_ALIGN`'s gate accepted only the literal `"1"` while its dispatch wanted `family`/`demo` - **the family mode was unreachable** | `FRUIT_DIRECT_START_ALIGN=family` skipped the whole block | the gate accepts any non-off value; `"1"` keeps the IK form |
| 4 | the deployment rendered at the scene default **480x848**, the store at **240x424** | `image_rgb` shapes differed by 4x in pixels | `FRUIT_CAMERA_RES=240,424` |
| ~~5~~ | **withdrawn - the mask was never wrong.** See 22.7: the "255x" reading came from the *offline replay*, which fed the stored uint8 `target_mask` straight into `push_frame`, bypassing the 0/1 normalisation both real callers do | the replay read 0.0902 where the loader read 0.0004, but `rl_env._observe` and `60_eval_policy.py` both build `(seg == target_id).astype(float32)` first | no change: `push_frame`'s contract is a 0/1 mask (the divide was added, measured as a canary collapse, and reverted) |
| 6 | `FRUIT_POLICY_ACTION_HOLD=1` replays a 16-waypoint chunk at **120 Hz** while the demonstrations are **30 Hz** (one frame per 4 control ticks) | the demos hold their start pose for ~50 frames; the deployment consumed the same chunk in 12 | `=4` |

**The observation can be made provably equal to the training observation, and
that check is what caught the phase's one wrong turn.** Replaying a store window
through `runtime.push_frame` reproduces the loader's `image` tensor to **1.4e-7**
on five windows spanning three episodes - *provided the replay feeds what the
callers feed*. The first version of that check fed the stored uint8
`target_mask` (0/255) directly and read `maxdiff 1.0` (a whole channel), which
looked like a deployment defect and produced a `/255` in `push_frame`; section
22.7 is how it was caught and reverted.

**A withdrawn claim, recorded rather than deleted**: the phase first reported
"the deployment's mask is 255x too large, project-wide". It is not. Both real
callers already normalise (`rl_env._observe` and `60_eval_policy.py:335` build
`(seg == target_id).astype(np.float32)`), so `push_frame`'s contract is a 0/1
mask and the divide made the deployment **wrong** rather than right. The
hybrid canary is what refused it - 3/10 against its 5-8/10 band - and the change
is reverted; `policy/runtime.py` differs from its pre-phase state by comments
only.

**The frame order is NOT a defect** (checked, then reverted): the loader builds
`[t-1, t]` (`for k in range(obs_horizon-1, -1, -1)`), which is what
`push_frame`'s append-and-drop-the-head already produced. A first pass changed
it and the same replay test showed the store's frame 0 was the *older* one, so
the change was backed out.

### 22.2 What the model does on its own demonstrations

`119_rl_fidelity.py` had to accept this arm's **12-D** proprio first (it
whitelisted 25/26). Then, on 128 sampled windows: **0.100 rad** arm error,
finger **0.0010**, phase agreement **95 %** (approach 0.061 rad / grasp 0.117 /
lift 0.138).

**The control that mattered**: the same statistic measured through the training
loader on *hold* windows (the label repeated for 3 waypoints) reads p50 **0.050
rad** for the OpenArm's `moe_v13s` on `demos_v11` and **0.061 rad** for
`p227_panda156` on its own store - i.e. this arm's model is **as good as the
shipped one** on the phase that decides the wait. So the lane's remaining
problem was not model quality.

### 22.3 The mechanism the wait exposes, and why the trigger is part of the recipe

The demos are **exactly stationary** for their first ~50 frames
(`|q(t)-q(0)|max = 0.000 rad` at t=20/50). The deployment drifts **0.3-1.3 rad**
over the same window, because the model's hold output carries a **deterministic**
bias of 0.06 rad (std across sampler seeds ~0.001-0.02; DDIM 8/16/32/64 all read
0.13-0.26, so it is not sampler noise). Chained over 25 decisions that bias is
the whole drift, and the drifted arm then closes at the 0.15 m gate
(`policy closed on the fruit (... |jaw-fruit|xy=14.9cm)`) instead of at the
fruit.

Two cheaper repairs were tested offline and **do not work**: a higher DDIM
budget does not move a bias, and a delta-servo on the chunk's own differences is
identically the chunk's displacement (the differences telescope), so it cannot
cancel it. The `rel`/`dq` action forms would need a retrain and are the record's
measured nulls (P173-P190) - and those nulls were themselves measured under the
255x mask.

What does work is the architecture the OpenArm lane already uses: **the learned
model approaches, the scripted primitive catches and places.**
`FRUIT_POLICY_TRIGGER=arrival` fires the primitive on the fruit's arrival
(`t_arrive <= lead`, the ACQ-adjusted lead this arm's own select lead reads),
independent of the model's own close. Every one of the 12 episodes below fires
it (`intercept trigger (... t_arrive=1.5-2.4s ...)`).

### 22.4 The cell

The recipe is `scripts/284_single_arm_policy_gate.sh` (six settings, each named
with the defect it repairs). `FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1
FRUIT_BIARM=0`, `--execute-steps 4`, `--ddim 16`, `checkpoints/p227_panda156`.

| arm | placed | detail |
|---|---|---|
| **seed 901** | **6/6** | lychee 2.8, tomato 5.1, strawberry 4.0, pear 6.7, strawberry 4.4, apple 6.3 |
| **seed 902** | **6/6** | strawberry 3.1, lychee 3.7, peach 6.1, lychee 3.7, peach 6.2, pear 6.5 |
| **pooled** | **12/12** | `scripts/284_single_arm_policy_gate.sh`, floors 0.60 and 0.80, both PASS |

The first reading of this cell was **11/12**, measured while the withdrawn mask
divide was in place (22.7). On the reverted tree it is **12/12** - one more
placement, which is the direction the revert predicts and is **not** a rate
claim (two 6-episode arms; P93's rule).

Before this section the same checkpoint read **0/7** (`deploy_panda1`,
`deploy_panda156`, `record1`, `record2`), and every episode fired its own close
at 12.9-15.0 cm. **No rate is claimed** beyond these two arms (P93's rule): the
loop conditions on rendered frames. What is claimed is the class shift - the
failures are now the closed loaded-slide class on one small fruit
(`logs/p42/SIM_LIMIT.md`), not "the arm never reached the fruit".

The one failure is the class the record has closed from force, pad face,
friction, seat, attitude, lift height and speed (`logs/p133/`), so it is named
rather than chased: a 4.0 cm strawberry, `grasped=True placed=False`.

### 22.5 No-harm

* **The scripted line is inert**, and it is proved rather than argued: the fix
  lives in `policy/runtime.py`, which the scripted entries never import.
  `scripts/accept.sh` reads **7/10 = 70 %, 9.5 s/attempt, `fingerprint: matches
  configs/motion_reference.json`, `190: PASS`**, and its **459 `[fruit]` lines
  are 458/459 identical** to `logs/p136/accept_final.log`
  (`logs/p227/accept_p227z_stream.log`). The single difference is line 7, the
  build print `robot referenced -> local flattened asset (...)` which now
  carries ` kind=openarm base_z=0.790` - P227i's arm-spec header, not this
  phase.
* `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**; `python3
  scripts/106_index_audit.py` **OK** (its one warning, `p225_small`'s 26 groups
  of byte-identical episodes, is a pre-existing merge artefact).
* Both motion references are untouched: `configs/motion_reference.json` =
  `..._twoline.json` = **`61fb5202`**, `..._single.json` = **`18b101bf`**.

### 22.6 The continuous clip, and a latent abort it exposed

The owner's first ask after the per-episode clips was a **continuous** one - no
reset, no teleport. That path already exists (`FRUIT_DIRECT_CONTINUOUS`,
P56/P58; and `FRUIT_CONTINUOUS_TRANSIT`, P225n, whose docstring names exactly
this: "the per-pick reset teleports the arm; in a continuous episode that is a
~1 m snap from the output line back over the belt in one tick, the one frame a
viewer reads as impossible"). The recipe is the six settings plus
**`FRUIT_CONTINUOUS_TRANSIT=1`** and `--continuous 4`.

**The first attempt aborted after pick 1**, and the defect is this phase's own
to fix: `_begin_pick`'s transit branch read

```python
self._continuous_return(active, self._aligned_start() or start)
```

and `_aligned_start()` returns an **ndarray**, so `or` raised
`ValueError: The truth value of an array with more than one element is
ambiguous` (`logs/121_policy_video_traceback.txt`). Two opt-in features had
never been run together - the continuous transit and a start alignment - so the
expression was never exercised. Fixed by reading it into a variable and testing
`is None`; the shipped per-episode reset never reaches the branch (`_transit`
requires `FRUIT_CONTINUOUS_TRANSIT=1` *and* a continuation), so no measured cell
moves. Pinned by the selfcheck leg **`P227z continuous return`** (the forbidden
`_aligned_start() or` form is absent, the `is None` form is present).

**The clip** (`logs/video_panda_cont/`, archived under
`.../log/video/p227z_panda_policy/continuous/`): **3/4 picks placed in one
episode** - strawberry 3.1, lychee 3.7, peach 6.1 cm, then a lychee 3.7 that is
`grasped=False placed=False` - 54.8 s at 30 fps, 1645 frames, all four on the
same side (`bin=0 arm=left`), so the run contains no arm switch at all. The
inter-pick gap is **263 ticks (~2.2 s)** for every transition, which is the
return transit (lift clear -> catch-up drive -> min-jerk blend -> settle).

**Read the count as a draw.** The first version of this clip - drawn while the
withdrawn mask divide was in place - placed **4/4**; on the reverted tree it is
**3/4**. Same recipe, same seed, same four fruits, different outcomes: the
continuous loop is not reproducible (it conditions on rendered frames), so the
clip is an artefact, not an arm.

**"No flash" is measured, not asserted**: ffmpeg's scene-change detector over
`observer.mp4` reports **zero** frames above a 0.10 score, and the highest score
anywhere in the clip is **0.0214**. A teleport moves the arm ~1 m across the
frame in one tick and would score far above that.

### 22.7 The one wrong turn, and what refused it

Recorded in full because the shape will recur: an **offline instrument that
bypasses a caller's normalisation** will report the normalisation as a defect.

**What was claimed.** Diffing a recorded rollout against the store showed the
mask channel's mean at 0.0902 in the deployment and 0.0004 in the store, i.e.
255x. The loader does divide (`data.py`: `target_mask.astype(float32) / 255.0`),
so the reading looked like a deployment bug and `push_frame` was changed to
divide too. The change was written up as project-wide, because `push_frame` is
shared by the OpenArm lane, the hybrid canary and the video script.

**Why it was wrong.** Neither real caller passes a raw mask. `rl_env._observe`
builds `mask = (seg == target_id).astype(np.float32)` and
`60_eval_policy.py:335` builds the same expression - both are 0/1 already, which
is exactly the training scale. The 0.0902 reading came from *my replay*, which
fed the stored uint8 `target_mask` (0/255) straight into `push_frame`; the
instrument skipped the step the callers perform.

**What refused it: the gate, not the reasoning.** `scripts/accept_policy.sh`
(the hybrid canary, the interface of record) reads **3/10 = 30 %** with the
divide in place - **below its 0.60 floor**, against a recorded spread of 5-8/10
across this checkpoint's history. A 10-episode canary cannot resolve a few
points, but a fall out of a 5-8/10 band into 3/10 is the shape a wrong-layer fix
makes. The canary is the *only* cell in the project that exercises
`push_frame` through a caller that normalises, which is why it is the cell that
catches this and the single-arm lane (whose numbers were measured with the
divide in place) does not.

**The revert.** The `/255` is out of both `push_frame` paths;
`policy/runtime.py`'s diff against its pre-phase state is **comments only**
(verified with `git diff | grep -v '^+' ...`: no functional line). The comment
left in place names the contract - *the mask arrives as 0/1* - so the next
reader cannot re-add the divide.

**The instrument rule this yields.** An offline replay is only a control for the
deployment when it enters through the same door: the same normalisation, the
same channel order, the same dtype. `logs/p114`'s and `logs/p136`'s replays
carried that discipline explicitly (`--same` on the `[fruit]` stream); this one
did not, and the canary paid for it. The corrected form of the useful half is
still in section 22.1: the frame *order* was checked the same way and found
already correct, so nothing changed there either.

**Numbers re-measured on the reverted tree** (these replace the arms first
quoted in 22.4, which were measured with the divide in place):

| arm | result | gate |
|---|---|---|
| seed 901, 6 episodes | **6/6 placed** | `284 ... 6 901 0.60` PASS |
| seed 902, 6 episodes | **6/6 placed** | `284 ... 6 902 0.80` PASS |
| hybrid canary, 10 episodes | **4/10 = 40 %** | below the 0.60 floor - see below |

**The canary is the one number that does not return to its band, and it is
recorded as NOT ADJUDICABLE this phase.** Measured: **3/10 = 30 %** with the
mask divide in place, **4/10 = 40 %** without it, against a 5-8/10 band from the
record. The same-batch control (the four changed files `git stash`ed, the
pre-phase tree) **wedged twice with zero episode rows**, both times right after
the `=== policy closed loop ===` header - the same failure the phase's first
canary run hit, and this machine has other `dynvla` simulators holding ~16 GB of
the GPU. A 10-episode loop is one draw (P93) and the two readings it did produce
are consistent with one distribution, but the honest statement is that a control
was attempted twice and the infrastructure refused.

**What decides it instead is mechanical inertness**, which is stronger than a
10-episode arm: the phase's changes cannot reach the canary. `policy/runtime.py`
differs from its pre-phase state by **comments only** (`git diff | grep -v '^+'`
returns no functional line); `rl_env.py`'s diff is `FRUIT_DIRECT_START_ALIGN`
gating (unset resolves `"0"` -> skip, the same decision the old `!= "1"` made),
the `_aligned_start()` `is None` fix (only under `FRUIT_CONTINUOUS_TRANSIT=1`),
and prints behind `FRUIT_DIRECT_START_DIAG=1`; the family JSON is read only when
`FRUIT_START_FAMILY` names it. The canary sets none of those. **The 4/10 is
therefore a property of this tree's canary, not of this phase** - and it is worth
saying that the tree has moved a long way since the 5-8/10 readings (the
three-lane flip and its revert, the park default, the release clock), so the band
itself is stale rather than contradicted.

### 22.8 A five-minute continuous run: 16/26, and the deficit is one transition

The owner asked for a **5-minute** continuous clip. Two things had to be built
for it, and the run produced a mechanism the short clips could not show.

**The instrument.** `121_policy_video.py` buffers every captured frame before it
encodes, so 5 minutes x 4 views is **~60 GB of RAM**. It gained **`--views`**
(capture a subset; unrequested cameras are no longer authored, so they cost
neither a render nor a buffer) and the existing `--capture-every` already keeps
real time at 15 fps (`fps = 30 / stride`, `render_every = 4 * stride`). The clip
is `--capture-every 2 --views observer,overhead`, which is ~21 GB. A source-shape
pin (`P227z video views`) keeps the cameras conditional and the `side_by_side`
guard in place.

**The clip** (`logs/video_panda_5min/`, archived under
`.../log/video/p227z_panda_policy/continuous_5min/`): **26 picks in one episode**,
one reset, **350.07 s (5 min 50 s)**, 5251 frames at 15 fps, 960x540, two views.
**16/26 placed = 61.5 %** - a draw, not a rate (P93).

**The deficit is one transition class, measured.** Joining each pick to its own
trigger row:

| class | n | placed |
|---|---|---|
| arrival trigger fired with **`t_arrive < 0.5 s`** (the fruit was already at or inside the station) | **5** | **1** |
| arrival trigger with a real lead | **21** | **15 (71 %)** |

Fisher two-sided **p = 0.055**, one-sided **0.0275**. The mechanism is a priori -
no lead means no catch-up room - so this is a mechanism read rather than a
search. The 3 remaining failures are the `fruit fell off the line` upstream-lost
class and 2 are the model's own close at 8.4-11.3 cm.

**The first reading of the gap was wrong, and the same-recipe control says so.**
The 26-pick clip has **263 ticks** on 7 transitions and 489-644 on the starved
ones, which reads as "a short gap means the next fruit was already waiting". A
second cell on the same recipe with a **10**-pick episode refutes it: gaps
**120-150 ticks** (shorter than any of the 26-pick ones) and **9/10 placed**,
with every `t_arrive` at **1.56-2.81 s** - no late fire at all. So the gap is
**not** the mechanism; the late fire is the *approach's own timing*, i.e. how
long the model's chunks take before the primitive gets the fruit (a 26-pick run
gives it 26 chances to be slow, a 10-pick run few). Recorded as a correction
rather than deleted, because the correlation was real in that sample and the
inference from it was not.

What is *not* in doubt is the class: 5 picks fired with `t_arrive < 0.5 s` and
placed 1/5 against 15/21 with a lead. A station-side queue or hold would remove
the class and is excluded by the owner's "preserve the dynamic pipeline"
constraint; the software lever is the **skip rule** (22.9), which is also the
owner's own cell semantics - several arms share a line, and a fruit already
inside this arm's window belongs to another one.

**No cut**: ffmpeg's scene-change detector reports **zero** frames above 0.10 over
the whole 350 s; the highest score anywhere is **0.0204**.

### 22.9 The arm's "weird" motion: it is the doomed attempt, and two rules remove it

The owner's first question was a safety one: the arm occasionally makes a
strange, twisted motion, which on real hardware is dangerous. Measured on the 22
recorded episodes of this phase (per-tick joint traces), the answer is
unambiguous: **the motion exists only on failed attempts.**

| class | n | single-joint range p50 | worst | direction reversals p50 | worst |
|---|---|---|---|---|---|
| placed | 17 | **0.10 rad** | 0.61 | **9** | 19 |
| failed | 5 | **1.18 rad** | **1.77** | **44** | **604** |

The worst episode is the kiwi whose fruit left the line: the fruit was gone, the
loop kept the policy's commands running to the horizon, and the arm oscillated
**604 times** over 288 frames - 12x the joint excursion and up to 60x the
reversal count of a placed attempt.

**Where the command comes from.** The policy emits absolute 7-joint targets, and
its per-tick step is p50 0.16 rad with a **maximum 0.89 rad** in this corpus -
i.e. up to **20x the arm's own 0.0454 rad/tick** (5.45 rad/s) joint-speed limit.
`resolve_target_rate`'s docstring already names the consequence ("a command
transient no servo can follow smoothly; the arm's visible response is the 'weird
pose'"), and P207 built the fix; this phase measured *when* it happens and put
the fix in the recipe.

**Three rules, in order of effect.**

1. **Don't run a doomed attempt** (the owner's own cell semantics). On a line with
   several arms nothing has to catch every passing fruit: a fruit already inside
   the window a descent can meet belongs to another arm. `FRUIT_SKIP_LATE=<s>`
   (P227aa, **default off**) ends the attempt on the tick the arrival trigger
   fires with `t_arrive` below the threshold, with the note
   `skipped: no lead (the fruit is already inside the catch window, ...) - not
   this arm's`. It is the class 22.8 identified (5 picks, 1/5 placed) turned from
   a chase into a hand-off.
2. **Bound the command** (defence in depth, and the only rule that helps when an
   attempt goes wrong for a reason nobody predicted):
   `FRUIT_POLICY_TARGET_RATE=5.45` (the arm's own `maxJointVelocity`, P207) ramps
   the emitted target so no tick can demand more than the joint can deliver -
   measured on this cell at **6/6 placed**, so the cap costs nothing in count.
3. **Never command outside the joint limits**: `FRUIT_POLICY_JOINT_CLAMP=1`
   (P53 C1) clips the 7 targets to the arm's own `get_dof_limits()` (measured
   free, and it removes the 11 % out-of-range emissions P53 censused).

**The single-arm recipe is now the six interface settings (22.1) plus these
three**, and `scripts/284_single_arm_policy_gate.sh` should be run with them:
`FRUIT_SKIP_LATE=0.5 FRUIT_POLICY_TARGET_RATE=5.45 FRUIT_POLICY_JOINT_CLAMP=1`.
A related bookkeeping warning that is **not** the motion: the `[task] carry ...
stored pad centre N mm from the measured pads; re-anchoring` rows (38 in the
26-pick run, 470-941 mm) are a stale cross-pick `_grip_centre` being corrected
before the leg runs - the correction is what keeps the leg sane, and the drift is
one carry leg's length, i.e. the previous pick's centre.

### 22.10 The three rules measured: 25/26 placed and the flail gone

The 26-pick continuous cell re-run with the safety envelope and the skip rule
(`FRUIT_SKIP_LATE=0.5 FRUIT_POLICY_TARGET_RATE=5.45 FRUIT_POLICY_JOINT_CLAMP=1`,
seed 902, one reset, `--record`):

| metric | 22.8 (no rules) | 22.10 (three rules) |
|---|---|---|
| placed | 16/26 = 61.5 % | **25/26 = 96.2 %** |
| joint range, p50 / worst | 1.18 / **1.77 rad** | **0.12 / 0.85 rad** |
| direction reversals, p50 / worst | 44 / **604** | **12 / 27** |
| `[skip]` fires | - | **0** |
| worst episode | 288 frames, 604 reversals | 43 frames, 7 reversals |

**CONFOUNDED, and corrected in 22.14**: this cell (`skip26`) was recorded
**without `FRUIT_CONTINUOUS_TRANSIT=1`** - the same dropped variable that 22.13
finds behind the missing return - so its pick boundaries **teleported**, and a
teleport returns the arm instantly, which is exactly what a starving line does
not have. The 16 -> 25 delta therefore mixes the three rules with the teleport
and **cannot be attributed**; 22.14 re-measures with the transit on.

**Read the count as a branch, and the motion as the result.** The two runs are
different draws (a 26-pick episode re-times every presentation), so 16 -> 25 is
not the rules' count: what the rules changed is the **shape** - the failure set's
1.18 rad / 44-reversal signature is gone from the whole run (worst 0.85 / 27,
which is the *placed* class's own tail), and the worst episode is 43 frames long
instead of 288, i.e. nothing runs to the horizon with the fruit gone any more.
The one remaining failure is a normal-lead catch (`t_arrive=1.99 s`), not the
late class.

**The skip rule was not exercised by that cell** (0 fires - this branch never put
a fruit inside the window), so its mechanism is proved separately: with
`FRUIT_SKIP_LATE=3.0` - above every arrival lead this cell produces - **all 3
attempts of a 3-pick continuous cell skip** (`0/3 placed`, three `[skip]` rows,
`picks placed 0/3`), the loop advances to the next pick each time, and nothing
raises. So the rule is a real hand-off, not a silent no-op: at a threshold the
cell can meet it does nothing, at a threshold it cannot it hands every fruit on.

**The recipe is therefore** the six interface settings of 22.1 plus
`FRUIT_SKIP_LATE=0.5 FRUIT_POLICY_TARGET_RATE=5.45 FRUIT_POLICY_JOINT_CLAMP=1`,
and `scripts/284_single_arm_policy_gate.sh` runs it that way. `FRUIT_SKIP_LATE`'s
resolver is pinned by the selfcheck leg `P227aa skip rule` (unset/`""` -> 0.0,
`0.5` -> 0.5, and `-1`/`abc`/`nan`/`inf` all refused, the `resolve_target_rate`
precedent).

### 22.11 The five-minute clip with the rules on

Re-recorded on the final recipe (six interface settings + the three rules),
`--continuous 26 --capture-every 2 --views observer,overhead`, seed 902:
**5 min 27 s** (327.40 s, 4911 frames at 15 fps, 960x540), **25/26 placed**,
**0 skips**, and **zero** scene-change frames above 0.10 over the whole clip.
Archived with a README at
`.../log/video/p227z_panda_policy/continuous_5min_safe/`, beside the "before"
clip (`continuous_5min/`, the same recipe without the rules).

The motion numbers quoted in 22.10 come from the `--record` cell of the same
recipe (`logs/p227/skip26`), not from the clip - the clip has no per-tick joint
trace (`121_policy_video.py` records video, not rollouts). Two different draws,
same recipe: both read **25/26**.

### 22.12 A negative worth keeping: slowing the return does not smooth the clip, it starves the line

The owner reported a "position jump" in the continuous clip. **My first reading of
it was wrong, in the direction that matters**: I measured the frame-to-frame mean
absolute difference over the whole frame, saw **1.05** in the window (and 0.86 at
30 fps) against a whole-clip p99 of 0.78, and concluded the image did not jump. A
fixed-size mean dilutes a localized change, and the arm is a small part of the
frame. The **block-max** metric (the worst 16x16 block) raises peaks of 45-49 in
that window, and I then read the top ones as "one block at a fixed spot", i.e. a
cosmetic artefact. **The metric does not separate the two cases at all** - measured
on the two 26-pick clips: **67 events above 20 grey levels** in the clip that has
the return transit and **79** in the one that teleports, with 242 and 165 frames
over the threshold. A closing gripper, a catch and a snap all look alike to it. So
the image was never the instrument; the question that settles it is **was the
per-pick return transit running at all?** Section 22.13 answers that from
`gap_ticks`, and the answer is no: those 30 fps and 5-minute "safe" clips were
recorded **without `FRUIT_CONTINUOUS_TRANSIT=1`**, so each pick boundary teleported
the arm.

The obvious hypothesis - the per-pick **return transit** is fast (a 90-tick
min-jerk blend plus an IK lift) - was tested and **fails**, in the informative
direction:

| arm | clip | placed | 145-170 s frame diff p99 / max |
|---|---|---|---|
| standard return (90 ticks) | 5 min 15 s | **25/26** | 0.77 / 0.86 |
| slow return (180 ticks, settle 90) | 4 min 46 s | **9/26** | 0.76 / 0.85 |

**Slowing the return did not make the clip smoother at all (identical frame
differences) and cost 16 of 26 placements.** A slower return means the arm is
still travelling when the next fruit arrives, so the arrival trigger has no lead
and the catch is lost - the same starvation mechanism the sign-off paragraph of
22.8 describes from the other side. **Do not slow `FRUIT_CONTINUOUS_TRANSIT_TICKS`
as a smoothness measure**; the 90-tick default is load-bearing for throughput.

What *did* change is the capture rate: the deliverable clip is **30 fps**
(`--capture-every 1`, 9442 frames, 5 min 15 s, 25/26 placed), which halves the
per-frame joint travel and is the only lever here that costs nothing.
`121_policy_video.py` also drops the raw observer buffer once the frames are
annotated (nothing below reads it), which is what lets a 30 fps multi-minute clip
fit in RAM.

### 22.13 The missing return motion: a dropped env var in the recording command

The owner's report was exact: from `video_panda_5min_safe` onward the arm **no
longer travels from the output bin back to the belt** - it appears beside the belt.
The cause is not in the code, it is in the command I used to record those clips:
when I added the three safety rules I dropped `FRUIT_CONTINUOUS_TRANSIT=1`, so
`_begin_pick`'s `_transit` was False and every pick boundary fell back to
`teleport_joints` - a joint-space snap from the bin to the wait pose.

**The discriminator is one number, and it is already in the log.** `[cont] pick N`
prints `gap_ticks`, the simulated time between the end of one pick and the start
of the next - it contains the selection round and `_begin_pick`, whose transit is
**150 ticks** (90 blend + 60 settle) plus a 20-tick settle:

| clip | `gap_ticks` |
|---|---|
| `video_panda_cont` (4 picks) | 263 on all of them |
| `video_panda_5min` (26 picks) | 245-644 |
| **`video_panda_5min_safe`** (26) | **120 / 139 / 150** |
| **`video_panda_30fps`** (26) | **120 / 135 / 150** |

A gap below the transit's own 150 ticks is only possible if the transit did not
run. So the arm really was snapping, the block-max events in 22.12 **were** those
snaps, and the earlier "the image does not jump" reading is withdrawn.

**A guard, at the one call site a demo uses**: `121_policy_video.py` now warns
when `--continuous` is used without `FRUIT_CONTINUOUS_TRANSIT=1`
(`[video] WARNING: --continuous without FRUIT_CONTINUOUS_TRANSIT=1 - every pick
boundary will TELEPORT the arm back to the wait pose ...`). The knob stays opt-in
in the environment (P225n's scope is unchanged, and a default flip would move
every measured continuous cell); the warning is a usability guard, not a
behaviour change.

**The clip that replaces the bad ones** (`logs/video_panda_final/`, 30 fps, 26
picks, one reset, the six interface settings + the three safety rules +
`FRUIT_CONTINUOUS_TRANSIT=1`) reads `gap_ticks` **245-642** on every transition -
the return is there.

**Read rule for this family, and it is the phase's least obvious lesson**: a
continuous clip's continuity is proved by **`gap_ticks` in the log** (150 ticks is
the transit's own floor) or by a **joint trace**, and **never by an image
metric** - whole-frame means dilute a localized snap, and block-maxima cannot tell
a teleport from a closing gripper (67 vs 79 events above threshold in the two
clips, i.e. no separation). The image is for a human to judge; the log is for the
claim.

### 22.14 Un-confounded: the return transit costs the count, the rules do not buy it

Three 26-pick continuous cells, seed 902, one reset each, **the only variables
being the return transit and the three rules**:

| cell | return transit | three rules | placed | `gap_ticks` |
|---|---|---|---|---|
| 22.8 (`video_panda_5min`) | **on** | off | **16/26** | 245-644 |
| 22.10 (`skip26`, **confounded**) | **off** (teleport) | on | 25/26 | 120-150 |
| 22.14 (`video_panda_final`) | **on** | **on** | **13/26** | 263-647 |

**CORRECTED (22.17): the "16 vs 13" comparison uses the wrong denominator.** The
raw placed-per-offered count treats a **hand-off as a failure**, which is exactly
what the owner's multi-arm semantics say it is not. Counted properly, the skip rule
is doing its job:

| cell | offered | placed | skipped (`no lead`) | attempted | **placed / attempted** | handed off |
|---|---|---|---|---|---|---|
| rules off (22.8) | 26 | 16 | 0 | 26 | **16/26 = 62 %** | 0 % |
| rules on | 26 | 13 | **10** | **16** | **13/16 = 81 %** | **38 %** |

So the line **places 81 % of what it attempts** (against 62 % when it attempts
everything) and **hands off 38 %** of the offered fruit to the next arm - the
behaviour the owner asked for. The class ledger says the same: `grip/carry loss`
**7 -> 1** (Fisher **p = 0.0496** on offered fruit), i.e. attempting a fruit that
has already arrived late is what produces the grip failures.

**What is still not claimed**: the placed-per-attempted difference (13/16 vs 16/26)
is **p = 0.30** at n=26 - a direction, not a rate. What *is* claimed is the
hand-off (10/26) and the grip-loss reduction (p = 0.05), and that the earlier
"the rules do not buy anything" sentence was measured on a denominator that
penalises the very behaviour the rules implement.

**The clip that carries the return** (`logs/video_panda_final/`, 3965 frames,
**4 min 24 s** at 15 fps, `gap_ticks` 263-647 on every transition, 13/26 placed)
is the deliverable; `video_panda_5min_safe/` and `video_panda_30fps/` are kept as
the **error reference** - both recorded without `FRUIT_CONTINUOUS_TRANSIT=1` - and
their READMEs now say so.

### 22.15 "The arm reaches under the bin": measured, and it does not

The owner reported the arm reaching below the side bins, and a posture a normal
sort should never show. Both were traced to one failed attempt in the delivered
clip (pick 4, `T` 43.8-59.8 s) and then measured across the cell.

**The hand never enters the bin zone.** With `RL_ENV_DEBUG=1` on 8 episodes of
the bins cell (177 sampled decisions):

| jaw axis | measured | the bins |
|---|---|---|
| `y` | **-0.108 .. +0.011** | at `|y| = 0.55`, inner face **0.40** |
| `z` | **1.259 .. 1.335** | floor **1.10**, rim **1.26** |
| `x` | 0.212 .. 0.381 | the belt band |

**Zero** samples below the bin floor, **zero** with `|y| > 0.40`, and 8/177 within
1 mm of the rim (that is the release, which sits above the rim on purpose). The
nearest bin wall is **0.29 m** away. What reads as "under the bin" is the camera:
the bins sit **behind** the robot (`x = -0.10`, `|y| = 0.55`) while the arm works
at `x` 0.21-0.38 and `|y| <= 0.11`, so in a side or overhead view the arm's
silhouette overlaps the bin at a depth 0.3-0.4 m away.

**The posture is the chase, and the chase had no bound.** Pick 4's record:

```
[task] close: fruit drifted 380 mm off the pick centre (cross-belt); re-closing on it where it is
[task] carry grasp_lift: stored pad centre 131 mm from the measured pads; re-anchoring
episode 3: lychee ... success=False grasped=False placed=False ticks=1931
```

The re-close follows the fruit to wherever it drifted (`gripper.follow_centre(
fruit_now)`) and only the **last** attempt aborted; the earlier ones reached as far
as the fruit had moved. On that attempt the arm's **j4 extended 0.85 rad** where
placements span **0.42-0.46**, so the "posture a normal sort never shows" is a
recovery reach, not a sorting motion.

**`FRUIT_CLOSE_DRIFT_MAX=<m>`** (new, **default off** = the shipped path bit for
bit) caps that reach: a re-close whose drift exceeds the threshold takes the
**existing abort path** (`... aborting the attempt instead of chasing it`) with its
own note `fruit drifted N mm during the close (chase cap M mm)`, so the attempt
ends cleanly instead of reaching.

**A separate defect found on the way, and deliberately not changed**:
`_place_low`'s floor is `cfg.output_belt_top_z` **unconditionally** (1.35), while
the bins are a 1.10 m floor with a 1.26 m rim. On a bins cell `need = bottom -
1.35 - 0.025` is **-0.057 .. -0.073**, so the accompanied descent is **skipped**
and the payload is released ~5 cm above the rim and **falls 0.20 m** to the bin
floor (measured `fingertip_z` 1.312-1.317, `below_rim` +0.052 .. +0.057, `low_drop`
0.000). Honouring the bin floor would drive the pads **into** the box (floor+25 mm
= 1.125, i.e. 0.19 m lower) - the opposite of the owner's complaint - so the
release stays above the rim and the free fall is recorded as a named trade, not
fixed. `FRUIT_PLACE_HEIGHT_DIAG=1` prints the row that measured it
(`[place] bin=... floor=... rim=... jaw_z=... payload_bottom=... fingertip_z=...
low_need=... low_drop=... below_floor=... below_rim=...`).

**The cap's own status, stated honestly**: it is implemented, strict-parsed and
pinned by shape, but **not exercised end to end**. The re-close path is rare -
`close: fruit drifted ... re-closing` fired **once in the delivered clip's 26
picks** and **not at all** in 8+8 episodes at seed 5 (0 fires at 0.10 m) or in 3
episodes at a forced 1 mm threshold, because the first close succeeded in every
one of them. What *is* measured is the body it reuses: the abort in the same `if`
is the shipped "fruit left the pick station ... aborting the attempt instead of
chasing it" path, which the 22.9-22.14 cells run. So the cap converts that
abnormal reach into the already-measured clean abort; its effect on a cell that
actually draws a disturbed close is the open item, and the delivered clip's pick 4
is the case to replay when one is available.

**Owner decision B, taken 2026-11-24: the place height is the BIN's, not the
belt's.** The first pass framed this as a trade (release above the rim vs an
accompanied descent) and the owner rejected the framing: *the height should be
decided by the bin itself - why is it still the belt?* They are right, and the code
now does it: `_place_low` takes the **destination's** surface, `bin_floor_top_z`
(1.10) when the destination is a bin and `output_belt_top_z` otherwise, with the
destination threaded in as `bin_index`. The belt was never under the payload at
that pose, so the old floor made `need = bottom - 1.35 - 0.025` negative on every
bins leg and silently skipped the descent.

Measured after the change (6 episodes, **6/6 placed**):

```
[place] bin=1 floor=1.100 rim=1.260 jaw_z=1.198 payload_bottom=1.139
        fingertip_z=1.143 low_need=+0.193 low_drop=0.193 bin_hold=1
        below_floor=+0.043 below_rim=-0.117
[place] bin=0 ... low_need=+0.197 low_drop=0.197 payload_bottom=1.139
        below_floor=+0.040 below_rim=-0.120
```

So `low_drop` goes **0.000 -> 0.182-0.197 m**, the payload stops **3.8-3.9 cm above
the bin floor** (it used to be released ~5 cm above the rim and fall 0.20 m), and
the fingertips stop **4.0-5.5 cm above the floor / 10.5-12.0 cm below the rim** -
inside the mouth, clear of the walls (the bin's inner half-width is 0.15-0.17 m
against a 0.061 m plate) and clear of the floor by the fingertip margin. The
**belt/rail cells are untouched**: the branch needs `cfg.output_bins` *and* a
destination index, so `output_bins=0` takes the belt exactly as before (the
acceptance is the no-harm gate). Pinned by the selfcheck leg
`P227ac place floor (bin)`.

### 22.16 Owner decision C: a shallow rim, so the accompanied descent stays above it

Decision B took the place height from the bin's own floor, which is right, but its
consequence was that the hand went **10.5-12.0 cm below the rim** on every place
(fingertips at `floor + 0.040..0.055`). The owner's answer: make the bin a
**shallow-rim** one. Done - `bin_wall_height` **0.16 -> 0.030** (rim **1.26 ->
1.13**), overridable with `FRUIT_BIN_WALL_HEIGHT` for a cell that wants the deep
form.

Measured on 8 episodes of the bins cell (seed 5), with the accompanied descent
unchanged:

| quantity | deep rim (0.16) | **shallow rim (0.030)** |
|---|---|---|
| `low_drop` | 0.182-0.197 | 0.179-0.193 |
| `payload_bottom` | 1.139 | 1.139-1.140 (floor + 39-40 mm) |
| `fingertip_z` | 1.143-1.155 | 1.143-1.158 |
| **`below_rim`** | **-0.105 .. -0.120** | **+0.013 .. +0.028** |
| placed | 8/8 | 7/8 |

So the pads now stay **1.3-2.8 cm above the rim** while the payload still descends
to **~3.9 cm above the bin floor**: the free fall stays ~0.04 m (the reason for
decision B) and the hand no longer enters the box (the reason for decision C).

**The one loss is not the rim.** It is a `grasped=False` attempt (a 3.0 cm lychee -
the grip class), and the recycle census shows every placed payload settling **at
the bin centres** (`discharged to the bin at (-0.10..-0.11, +-0.54..+0.55)`,
settled 3.0 s), i.e. a 3 cm lip does hold them.

**The margin is 13 mm and it is a design pair, not a coincidence**: the descent
stops the payload at `FRUIT_PLACE_LOW_CLEARANCE` (25 mm) above the floor and the
fingertips sit ~4 mm higher, so a rim at `floor + 30 mm` leaves ~13 mm. Lowering
`FRUIT_PLACE_LOW_CLEARANCE` below ~0.020 would put the pads under the rim again -
that pair is the thing to keep together if either value is ever retuned.

Pinned by the selfcheck leg `P227ac shallow rim` (the default resolves to 0.030 and
`FRUIT_BIN_WALL_HEIGHT` overrides it).

### 22.17 The denominator question, raised by the owner's "is the model even driving?" question

Answering "what does the model actually do" forced a recount of the delivered clip,
and the recount found that **the skip rule fired 10 times in it** (the owner's
question surfaced this: 12 rows with `decision == ticks` are the 16-tick skips, not
model failures). That exposed a measurement error of mine: 22.14 compared the two
cells on **placed per offered**, which counts a deliberate hand-off as a failure.
The correct table, with `skipped: no lead` separated:

| cell | offered | placed | skipped | attempted | placed/attempted | handed off |
|---|---|---|---|---|---|---|
| rules off (22.8) | 26 | 16 | 0 | 26 | **62 %** | 0 % |
| rules on (delivered clip) | 26 | 13 | **10** | **16** | **81 %** | **38 %** |

`grip/carry loss` **7 -> 1** (Fisher **p = 0.0496**), i.e. the failures that
disappear are the ones caused by attempting a fruit that had already arrived.
**The placed-per-attempted difference is p = 0.30** at n=26: a direction, not a
rate; the hand-off count and the grip-loss reduction are the claims.

**Read rule, and it is the same mistake as 22.12/22.13's image metric in a
different coat**: a cell with a **hand-off** has three outcomes, not two -
placed / failed / not-this-arm's - and a two-way denominator silently books the
third as the second. Any comparison of two cells that differ in *whether they hand
off* must either exclude the hand-offs from both denominators or report all three
counts.

### 22.18 Route A: removing the skill router costs parameters, not compute, and does not help the phase that is used

The owner's observation: with the scripted primitive owning the contact phase, the
model only ever executes its **approach** chunk - so are the other four skill
experts dead weight? Measured on the router itself (400 random store windows,
`last_router_weights`):

| true phase | mean router weights (approach, grasp, lift, place, recovery) | argmax |
|---|---|---|
| approach (n=143) | **[0.982**, 0.009, 0.006, 0.002, 0] | 143/143 -> expert 0 |
| grasp (n=39) | [0.027, **0.925**, 0.046, 0.002, 0] | 38/39 -> expert 1 |
| lift (n=218) | [0.001, 0.005, **0.992**, 0.002, 0] | 217/218 -> expert 2 |
| **place** | **0 windows sampled** (the store has **42 of 23 123**) | - |
| **recovery** | **0 windows** | - |

So the router works (0.93-0.99 confidence by phase), and at deployment **expert 0
is the only one whose output is executed** - the other four are computed-and-
discarded, and two of them are barely trained (place = 0.18 % of the store,
recovery = none). The observation is correct.

**Route A was trained and measured**: `--num-skills 1` (new; with one expert the
router losses are switched off, because `cross_entropy(1 logit, label 3)` is an
out-of-range index - on CUDA that surfaces as `device-side assert triggered` at the
next kernel, which is how the first attempt died). Same store, same 12 epochs, same
recipe:

| | 5 experts (shipped) | **1 expert** |
|---|---|---|
| parameters | 4.59 M | **3.80 M** (-17 %) |
| best val loss | 0.0276 | **0.0266** |
| inference p50 / p95 (DDIM 16) | **29.3 / 62.8 ms** | 36.5 / 65.0 ms |
| action error, all windows | **0.100 rad** | 0.105 |
| action error, **approach** (the phase deployed) | **0.061 rad** | 0.075 |
| phase agreement | 95 % | **97 %** |

**The compute is unchanged, and that is the finding**: `_mix_experts` **skips any
expert whose weight is ~0**, so the 5-expert model already runs **one** expert per
forward. The MoE costs **parameters, not time**, and its removal does not make
inference faster (the quoted p50 difference is within this box's spread - p95s
agree). The approach phase - the only one executed - is **0.014 rad worse**.

**The lane endpoint, both routes measured** (6 episodes per arm, the shipped cell):

| cell | model | goal / trigger source | seed 5 | seed 902 | total |
|---|---|---|---|---|---|
| A (baseline) | 5 experts | truth | 6/6 | 6/6 | **12/12** |
| B (route A) | **1 expert** | truth | 6/6 | 5/6 | **11/12** |
| C (perception) | 5 experts | **tracker estimate** | 5/6 | 5/6 | **10/12** |

All three clear the 0.60 floor. **The differences are a draw at these n** (12 vs 11
vs 10 of 12; Fisher on 12/12 against 10/12 is p ~ 0.5), so:

* **Route A is a simplification, not a win.** -17 % parameters, a slightly better
  val loss (0.0266 vs 0.0276), the same latency, and **0.014 rad worse on the
  approach phase** - the one phase deployment executes. **The default stays the
  5-expert model**; `--num-skills 1` is the documented, measured smaller form (and
  the honest one: with the primitive owning contact, four of the five experts are
  computed-and-discarded, two of them barely trained).

### 22.19 The decision layer now runs with no simulator truth in it

The owner's other directive: the fruit's position and velocity must come from the
model's own estimate, because reality will not hand them over. Two wires were
needed:

1. **the goal** - `FRUIT_GOAL_SOURCE=perception` (already existed): depth + instance
   mask -> trimmed sphere fit -> `FruitTracker`, published **every observation
   tick** as `predict_at(horizon)` (a predicted *current* position, coast-capped),
   so the policy conditions on the estimate and not on a stale measurement;
2. **the fire decision** - new `_fruit_for_trigger()` (P227ad): with the perception
   goal armed, **both** `should_fire` call sites take the tracker's estimate for the
   position and the velocity instead of `spawner.position/velocity`, and the attempt
   prints one `[fire] source=percept|truth` row so a log cannot confuse them. Unset,
   the helper returns the simulator's state exactly as before.

**Measured (cells C1/C2)**: 6/6 `[fire] source=percept` per cell, **5/6 placed at
both seeds** (10/12 pooled, against 12/12 with truth - a draw at n=12). The estimate
itself: velocity **-0.118 .. -0.122 m/s** against the belt's **-0.120** (1.7 %),
diameters 28.4-61.0 mm against a 29.6-69.6 mm pool, sphere-fit rms **0.21-0.51 mm**,
`missing=0` frames, 0-2 `rejected` per attempt. The two losses are **`grasped=False`
at normal leads** (`t_arrive` 2.04 and 2.06 s) - the grip class the record already
owns, not a perception failure.

**What is still truth, stated so the claim is not over-read**: the **contact
layer** - `grasp_carry_place` still reads `spawner.position/velocity` (117 sites).
The split that now holds is *decision* (goal + fire, model-derived) versus *contact*
(scripted, truth-fed). Closing the second half means giving the primitive its own
hand-state + force path rather than a fruit position - which is the `SIM_LIMIT.md`
work, and is the named next step, not something this cell claims.

### 22.20 The contact layer without truth: a three-tier ladder, and the bottleneck is measurement availability

The owner's directive was that the fruit's position and velocity must come from the
model, and then that the primitive must stop reading the simulator too. Both were
built and measured; the ladder is now complete.

| tier | goal / trigger | primitive's pre-grasp reads | camera during contact | placed |
|---|---|---|---|---|
| **A** (shipped) | truth | truth | - | **12/12** |
| **C** | tracker | truth | - | **10/12** |
| **G** | tracker | **tracker** | **on, 30 Hz** | **2/6** |
| **D/E/F** | tracker | tracker | **off** | **0/12** |

**D/E/F's zero has a named cause, and it is not the estimator**: the primitive runs
**2226-2519 ticks (18.6-21.0 s)** and `_observe` fired only in the policy loop, so
the tracker's last update was **~10 s old**; the coast cap correctly refuses to
extrapolate that far and every attempt reported `close: fruit drifted **1170-1210
mm**` - 1.17 m is exactly 9.7 s of belt travel, i.e. the staleness, not an error.

**G fixes the staleness and pays elsewhere.** Two wiring defects had to be found
first, both worth recording: `task.frame_callback` fires at only **15 named legs**
(so a capture-style hook stayed silent - the frame count did not move), and
`_step_sim` - the primitive's own tick path - deliberately does not render. The
hook therefore lives in **`_step_sim`** (`primitive_tick_hook`, opt-in), and
`_observe(force=True)` bypasses the `_observed_step == _step` guard, because `_step`
is the *policy* tick and does not advance inside the primitive. With that, the drift
rows **disappear** and the cell moves **0/6 -> 2/6**.

**The mechanism of the remaining loss is a census, not an opinion**: per attempt the
camera produced **rejected = 242-322** frames against **accepted frames = 45-61**,
i.e. **~15-18 % usable**, with `missing = 0` (the instance id is always in frame, so
the refusals are the fit gates: the hand occluding the pad region, a small fruit, a
clip). The tracker therefore coasts **0.1-0.2 s** into the contact instant - 12-24 mm
of belt travel at 0.12 m/s - against a **6 mm** catch tolerance. The remaining
failures are all `fruit did not follow the gripper`, i.e. the hold, not the aim.

**Verdict**: the *decision* layer runs with no simulator truth (tier C, 10/12, and
it is the same code path the shipped lane uses with the lever unset). The *contact*
layer can be made truth-free only at a cost the record can now price: **a usable
measurement in ~1 of 6 in-contact frames**, which needs the wrist view the build
cannot annotate (P135: authoring a second annotated camera takes the first one's
mask) or a force-first close (`SIM_LIMIT.md`'s lane) - not a better estimator, since
the estimator already reads 4.70 mm when it can see the fruit.

**Levers** (all default off, unset = the shipped path bit for bit):
`FRUIT_GOAL_SOURCE=perception` (goal + fire from the tracker),
`FRUIT_PRIMITIVE_ESTIMATE=1` (pre-grasp reads from it; **requires** the perception
goal and raises otherwise), `FRUIT_PRIMITIVE_PERCEPT=1` (keep the camera running
inside the primitive, 30 Hz, installed on `_step_sim`). Pinned by
`P227ad trigger source` and `P227ad primitive estimate` (the second asserts the
**pre/post-grasp split**: 17 pre-grasp reads routed, 36 post-grasp reads still on the
simulator, because after the grasp the payload follows the hand).
