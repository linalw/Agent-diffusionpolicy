# Platform survey: which dual-arm cell, which tactile, which hand, which policy

**A plan, not a measurement.** Written 2026-11-03 (P101). No simulator run, no
`src/` change, no `configs/` change; the only artifacts are this file and a
`WORKLOG.md` entry. Every external claim is dated and marked:

| mark | meaning |
|---|---|
| **[V]** | **verified today** against the primary source (repo/API/vendor page fetched 2026-11-03); the URL is in §6 |
| **[R]** | **reported** — a secondary source, a vendor claim, or a paper abstract I did not re-derive |
| **[U]** | **unverified** — could not check (no public page, dead link, blocked fetch). **Do not spend money on a [U] row without re-checking it** |

Prices are quoted only where a vendor page printed one on 2026-11-03. Where a
price is absent it is absent — I did not estimate. Where a licence is
non-commercial it is called out, because half of the open-hardware ecosystem is
CC BY-NC and this cell is a *sorting* product, not a paper.

---

## 0. The answer in one page

1. **Do not change the arm.** The dual-arm platform question is already answered
   by the tree: OpenArm is 2 x 7-DoF, 4.1 kg nominal per arm, CAN-FD, **Apache-2.0
   software + CERN-OHL-S-2.0 hardware**, **$6,500 for a complete bimanual
   system** [V], ships an **Isaac Sim 6 USD and an Isaac Lab config**
   (`OPENARM_BI_CFG`) [V], and is a **first-class LeRobot robot, bimanual
   included** (`bi_openarm_follower`) [V]. Nothing else on the list beats that
   combination at that price, and every family this repo has *closed* (force,
   seat, pad geometry, station/rotation, place profile, workstation) is an
   **end-effector or workstation** object, not an arm object (§1.1).
2. **The platform change is the end effector, in two purchases**: a **tactile
   pad on the existing parallel jaw** (GelSight Mini is **$510** [V]; 9DTact is
   MIT and commercial-OK [V]), then a **hand** (ORCA: 17 DoF, **tactile
   integrated**, <2,000 CHF material, IROS 2025 [V]; or LEAP: 16 DoF, $2,000 in
   parts, but **CAD is CC BY-NC-SA** [V]; or Aero Hand Open: 7 DoF/16 joints,
   **$314**, NC design files [V]).
3. **The hand's business case is the 75 % failure class, not speed.** The
   loaded slide is 75 % of this cell's failures (P92 census), the policy owns
   **14.2 %** of the episode (P52) and a 1.5x on the whole policy phase is worth
   at most **4.8 %** (P52) — so a hand cannot pay for itself in cycle time. It
   pays only if `cnp` falls. That is the pre-registered primary in §5.
4. **The policy becomes a hand-conditioned action head**, not a 25-DoF action
   vector: keep the 9-D arm chunk, add an **8-D hand latent** decoded to the
   hand's joints, condition both on the same FiLM vector + a **phase token**
   from the existing 5-expert skill router (§4.3). Data cost: a **recollection**
   (schema change 25-D → 30-40-D), and the measured anchor for that is
   **158 episodes in 2 h 6 min** on this machine (W3, `datasets/v12d_s02`).
5. **Staged plan with kill criteria** is §5. The measured thing to beat:
   **58/80 = 72.5 % placed** pooled over four seeds, interval **10.6-12.2 s**,
   `cnp` **17 of 25 failures**, wall **2.37-2.91 placed/min** [V, P93].
   **Stage (i) has since been measured in sim** (P102, 2026-11-03): the patch
   channel sees the loaded slide **0.17-0.94 s** before the pinch is lost, so its
   **kill does not fire** - and the reason §2.4's "30 Hz is too slow" was wrong is
   that the 0-3 tick number is the *force* channel's last moment, not the slip's
   first. The one open question left in (i) is the **bench** (§3.3 T2), not the
   cell.

---

## 1. Open-source dual-arm robots usable as a sorting cell

### 1.1 What the cell actually needs (derived from this repo, not from a datasheet)

The survey's constraints are the ones the last 90 phases measured:

| requirement | why, from this repo | consequence |
|---|---|---|
| **two 7-DoF arms on one base** | the shipped cell is `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, two stations 0.10 m apart on one belt | a single arm + a second station is not the same scenario (P85) |
| **>= 3 kg payload per arm** | fruit is 30-70 g, but the **hand** is 0.4-1.0 kg and the cell runs a 0.20 m lift at 0.30-0.37 m/s | a 1 kg hand leaves 3.1 kg on OpenArm's 4.1 kg nominal [V] |
| **>= 0.65 m reach, top-down at the station** | TCP reach is **~0.68 m** (`scripts/12_reach_calibration.py`, README) [V]; the place station has **no** top-down IK cell in ±0.15 m (P90) | reach is already marginal at the *place*; a shorter arm is out |
| **a fieldbus that can command at >= 1 kHz** (CAN-FD / EtherCAT) | the sim runs 120 Hz control and the catch is calibrated to it; a lagging bus re-times the catch | USB-servo arms (SO-101, Koch) are 30-60 Hz class |
| **replaceable fingers** | the whole P41-P79 force/geometry family is a *pad* question | OpenArm 2.0's fingers are explicitly replaceable [V] |
| **an in-hand or wrist camera path** | the policy's only exteroception is one head camera (§4.1) | a hand blocks the head camera's view of the grasp |

That last row is the one nobody quotes: **the current policy sees the grasp from
one 240x424 head camera**, and a 16-DoF hand plus a 1 kg wrist sits between that
camera and the fruit. Any hand stage must add a **wrist/in-hand view**, or the
policy is blind at the exact moment the class happens.

### 1.2 The table

`EE` = end-effector interface; `ctl` = control stack; `sim` = first-party
simulator assets; `tactile` = a *credible* mount path on this platform.

| platform | licence | DoF | payload | reach | EE / ctl | sim assets | tactile path | price | adoption | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **OpenArm 1.0/2.0** (enactic) | SW **Apache-2.0**, HW **CERN-OHL-S-2.0** [V] | **7/arm, 2 arms** [V] | **4.1 kg nominal / 6.0 peak** incl. EE [V] | **~0.68 m** TCP (repo calib.) [V]; vendor reach not published [U] | CAN-FD; ROS 2 (`openarm_ros2`), dora-rs, **LeRobot `bi_openarm_follower`** [V] | **Isaac Sim 6 USD + Isaac Lab `OPENARM_BI_CFG`; MuJoCo `openarm_mujoco`** [V] | **replaceable fingers + in-hand Arducam B0495 (1920x1200@50)** [V] | **$6,500** bimanual; $4,699-$7,080 from 6 vendors [V] | 3,666★, 392 forks, pushed 2026-11-02 [V]; shipped cell here | **keep** |
| **ALOHA / ALOHA 2** (Stanford / Google DeepMind) | **MIT** (`tonyzhaozh/aloha`) [V]; ALOHA 2 hardware open [V] | 6/arm + 1 gripper; Menagerie `aloha` **16 DoF** [V] | not published [U] | ViperX 300, ~0.75 m class [R] | 4 cameras, leader-follower; ACT reference stack | **MuJoCo `aloha` BSD-3 with sysID (ALOHA 2)** [V]; no Isaac asset [V] | custom parallel fingers, 3D-printed → mountable [R] | kit price not checked [U] | 2,361★ + Mobile-ALOHA 4,478★ [V]; the canonical bimanual benchmark | strong #2, worse EE |
| **LeRobot SO-101 / SO-100 bimanual** | **Apache-2.0** [V] | 5+gripper per arm; `bi_so_follower` bimanual [V] | STS3215 class, ~0.2-0.5 kg [U] | ~0.30 m [U] | USB servo bus, 30 fps record [V] | **MuJoCo `robotstudio_so101` 6 DoF + `trs_so_arm100`** [V]; **Isaac Lab `so101.py`** [V] | printed fingers → any pad mount | ~$100-200/arm community BOM [U] | 7,970★ (SO-ARM100) [V]; huge community | too small/weak |
| **Reachy 2** (Pollen) | open HW+SW, **Apache-2.0** SDK/repos [V] | **7/arm**, 2 arms [V] | **3 kg/arm** [V] | human-scale [R] | **ROS 2 Humble + Python SDK**; **LeRobot `reachy2`** [V] | **MuJoCo + Gazebo** [V] | Orbita 2-finger; no native tactile [U] | **$36k-$70k** [R, third-party] | commercial, active | good arm, 5-10x price |
| **Koch v1.1** | **MIT** [V] | 5+gripper [V] | small [U] | ~0.30 m [U] | USB servo; LeRobot `koch_follower` (no `bi_` entry today) [V] | **MuJoCo `low_cost_robot_arm`** [V] | printed | ~€250/arm [R] | 3,419★ [V] | teaching only |
| **i2rt YAM** | **MIT** software [V]; hardware commercial | 6 or **7 DoF**, 0.808 m reach (7-DoF), 5.8 kg [V] | not published [U] | **0.808 m** [V] | CAN, DM motors; bimanual examples in-repo [V] | **MuJoCo MJCF + `yam` in Menagerie (8 DoF, MIT)** [V] | bolt-on EE | not published [U] | new (2026), active | credible cheap 7-DoF |
| **Dexmate Vega-1** | **Apache-2.0 models** (URDF/USD) [V]; robot commercial | humanoid, `f5d6` hand or gripper [V] | not published [U] | not published [U] | URDF/SRDF + USD releases; Isaac Sim/Lab tested [V] | **USD in releases, Isaac-tested** [V] | **F5D6 hand or gripper, factory option** [V] | not published [U] | 14★, new | watch |
| **ARX L5 / xArm 7 / Kinova Gen3 / Franka FR3** | drivers open (BSD/Apache) [V]; arms commercial | 6-7/arm, Menagerie `arx_l5` 8, `xarm7` 13, `gen3` 7, `fr3` 7 [V] | 3-7 kg [R] | 0.6-0.85 m [R] | vendor SDK + ROS 2 (`ros2_kortex` 133★) [V] | **Menagerie models, BSD/Apache** [V]; Franka/URDF Isaac assets exist [R] | wrist FT standard; pad mount DIY | FR3 ~€? [U]; xArm ~$? [U] | industrial, widely used | re-baseline, no gain |
| **TIAGo++ / RBY1** | **Apache-2.0 models** [V]; commercial robots | 25 / 28 DoF [V] | not published [U] | not published [U] | ROS 2 | **Menagerie** [V] | none native | [U] | PAL / Rainbow | mobile, not a cell |
| **Cobot Magic** (AgileX) | mixed; ALOHA-derived [R] | 6/arm + gripper | not published [U] | ~0.6 m [U] | ROS 1/2 | none first-party [U] | printed | ~$? [U] | moderate | not a fit |

**Rows I deliberately did not chase**: Unitree G1 / AgiBot / Fourier (full
humanoids — legs and multi-finger hands, not the brief), and every "open-source
humanoid" whose arms are 5-DoF. The brief is a *sorting cell*, and the cell is
defined by its end effector, not its leg count.

### 1.3 The four that matter, in prose

**OpenArm stays.** The decisive facts are boring and checkable: 7 DoF/arm with
**40/27/7 N.m** joint effort limits and **2.175/2.61 rad/s** velocity limits in
the Isaac Lab config [V] — the sim's own 2.1x headroom note (P44) is the same
number — a **4.1 kg nominal** payload that survives a 1 kg hand, a **$6,500**
bimanual price, **Apache-2.0** software, and **LeRobot bimanual support with a
CAN-FD driver already written** [V]. Changing the arm re-buys all of that to fix
a class the arm does not cause. The one arm-side defect on record — **no
top-down place station anywhere in ±0.15 m** (P90, 0/588 cells) — was worked
around by lowering the lift (P66/P71) and is a *reach-envelope* property that a
different 7-DoF arm would trade for a different envelope, not delete.

**ALOHA 2 is the strongest alternative and still loses on the end effector.** It
is the reference bimanual platform, MIT-licensed, with a **system-identified
MuJoCo model** [V] and 4-camera observation, but its EE is a printed parallel
jaw on a 6-DoF ViperX, i.e. *the same class of contact* this repo has already
measured to death. Buying ALOHA to escape the loaded slide is buying the same
slide with a different serial number.

**Reachy 2 is the "grown-up" option and costs 5-10x.** 7 DoF/arm, 3 kg/arm,
ROS 2 Humble, MuJoCo + Gazebo, LeRobot driver [V]. Third-party price listings
put it at **$36k-$70k** [R]; I did not find an official price page [U]. Its
gripper has no tactile path and its arms are the same DoF count as OpenArm's.

**The cheap 7-DoF arms (i2rt YAM, 0.808 m reach, MIT software, MuJoCo models
[V]) are the interesting 2026 entrants** — longer reach than OpenArm and a
mature MJCF — but they are single-arm products with a bimanual *example*, not a
bimanual *cell*, and their hardware licence and price are not public [U]. Good
second source for a spare arm, not a platform migration.

### 1.4 Verdict for §1

**No arm migration.** The 2026 platform decision is: **keep OpenArm, buy an end
effector.** The only arm-side item worth a purchase order is a **second OpenArm
arm** if the cell ever needs a third station — the same $6,500 buys a known
kinematics, a known Isaac asset and a known LeRobot driver.

---

## 2. Tactile sensing, gripper-mountable, open

### 2.1 What the sim has today, and what a real sensor would replace

The tree's tactile channel is **point contact on the two finger links**
(`src/fruit_sorting/tactile.py`: one `ContactSensor` per finger, aggregated to
`normal_force`, `contact_count`, per-finger forces) and it surfaces in the
policy as **2 of the 25 proprio scalars** and in the `[carry]` row as
`f=(f0,f1)`. That is:

* **2 scalars**, not a field: no contact **location**, no **shear**, no **patch
  shape**;
* sampled **once per control tick** (120 Hz) but *quantised by the physics
  tick*, and the record measured that where the force collapses the payload is
  gone **within 0-3 ticks** (`logs/w5/`, W5-C) — i.e. **25 ms**.

So a real sensor replaces a **2-scalar normal-force estimate** with a
**contact-patch field (location + normal + shear)**, and the honest question is
not "is it better" but **"is it fast enough to act on"**. On this cell's
measured timeline, no vision-based tactile at 30-60 Hz is a reflex channel; it
is a **supervision and slow-loop channel** (§2.4).

### 2.2 The table

`form` = fingertip vs pad vs skin; `if` = host interface; `rate`/`range` only
where the source printed them.

| sensor | open? | form | if | rate | force range | mountable on a parallel jaw? | simulated? | price |
|---|---|---|---|---|---|---|---|---|
| **DIGIT** (Meta) | **HW design CC BY-NC 4.0** [V] — *non-commercial*; firmware binary [V] | fingertip, 20x30 mm class [R] | USB [R] | 30-60 Hz class [R] | [U] | **yes** — it is a fingertip | **TacTO** (MIT) renders DIGIT [V] | build-only [U] |
| **DIGIT 360 / Pinki** (Meta FAIR) | Pinki design **CC BY-NC** [V]; 360 availability [U] | fingertip, omnidirectional | USB-C [R] | "30x human response" [V, marketing] | **1 mN**, **7 um** spatial [V] | yes | no [U] | [U] |
| **GelSight Mini** | SDK **GPL-3.0** (`gsrobotics`) [V]; sensor closed | pad, 30x40 mm class [R] | **USB-C UVC** [V] | ~25-30 Hz [R] | [U] | **yes** — flat pad, screws on | GelSight sim exists [R]; no Isaac path [U] | **$510** [V] |
| **9DTact** | **code + hardware source, MIT, "commercial purposes" explicitly OK** [V] | pad, compact [V] | USB camera [R] | ~30 Hz [R] | 6-D force via learned head [V] | **yes** | no [U] | BOM public [V], price [U] |
| **DenseTact** | **dataset + STL only** (MIT) [V]; full hardware not released [V] | fingertip dome | [U] | [U] | shape reconstruction [R] | yes | no | [U] |
| **AnySkin / ReSkin** | **MIT**, `raunaqbhirangi/anyskin` [V] | **skin** (self-adhering) | **USB-C via QT Py, serial** [V] | not printed [U] | magnetic (shear + normal) [V] | **yes** — it is a skin | no (magnetic) [U] | kit [U] |
| **Tac3D** | paper only (arXiv 2202.06211); **no official open repo found** [U] | pad | [U] | [U] | force **distribution** [R] | yes | no | [U] |
| **uSkin** (Touchence) | **commercial, no open HW found** [U] | skin/pad | [U] | [U] | 3-axis [R] | yes | no | [U] |
| **FlexiTac** (2026) | **open-source, "scalable"** [R — site not fetched] | skin/pad | [R] | [R] | [R] | yes | no | low-cost claim [R] |
| **Pollen tactile_gripper** | **Apache-2.0**, Rust tools + AnySkin + slip LSTM + HF dataset [V] | **a whole parallel-jaw gripper** | USB | [U] | slip detection demo [V] | it *is* the jaw | no | [U] |

### 2.3 The mount on *this* gripper is a mechanical non-problem

OpenArm 2.0's fingers are **designed to be replaced**: "the finger components
are also designed to be easily replaceable, providing a flexible development
platform where users can ... evaluate specialized geometries" [V], and the
gripper already contains an **Arducam B0495 (1920x1200, global shutter, 50 fps,
UVC)** [V]. Two consequences:

* A **GelSight Mini** or **9DTact** bolts to a reprinted finger with a 4-hole
  pattern; the sensor's own camera does the imaging, so the in-hand camera stays
  free for the policy's wrist view.
* The **in-hand camera is already the wrist view** the hand stage will need
  (§1.1) — but only on **2.0**. This tree's sim asset is the **1.0 bimanual
  USD** (`openarm_bimanual.usd`), its Isaac Lab config declares only the arm and
  finger joints, and the direct env reads exactly **one** camera (the mast head
  view, `scene.camera_sensor`) [V]. So the wrist view is a *new* input on both
  sides, and that asymmetry is a re-baselining item, not a blocker.

**What I would buy first**: two **GelSight Mini** ($510 each [V]) because they
are in stock, UVC (no driver), and their SDK is a Python package; or **9DTact**
if the commercial licence matters (MIT, "feel free to use ... for commercial
purposes" [V]) at the cost of a self-built BOM. **DIGIT is disqualified for a
product** by CC BY-NC [V] even though it is the best-documented.

### 2.4 The measured caveat that decides the tactile design

This repo already tried to *use* the tactile channel reactively and failed for a
measured reason: "carry losses keep 2-8 N on one finger (32-46 N on one), and
where the force collapses the payload is out within **0-3 ticks**; a pose-only
key fires on successes" (`logs/w5/`, W5-C; restated in `logs/p42/SIM_LIMIT.md`
§1). At 120 Hz that is a **25 ms** budget. A 30 Hz GelSight gives **33 ms per
frame** — it can *label* the slip, it cannot *catch* it.

> **Corrected by P102 (2026-11-03, `logs/p102/`).** That 0-3 tick number is the
> **normal force's** last moment, not the slip's first. Measured on the shipped
> cell: the payload's in-hand displacement reaches 2 mm **21-113 ticks (median
> 60 = 0.50 s) before** the pinch is lost, and **when the force finally
> collapses the payload is already 4.5-46.4 mm out of position** (6 escapes, 2
> seeds, `logs/p102/RESULTS.md` §3). So the 25 ms budget belongs to the 2-scalar
> channel; the **relative motion a pad images lasts 0.17-0.94 s, i.e. 5-28
> frames at 30 Hz (median 15)**. The conclusion below - that a tactile's defensible uses are
> supervision and slow-loop verification - is **not** supported by the force
> channel's timing and must be re-argued from the pad's own 0.17-0.94 s window
> (§5.1 status).

Therefore the tactile channel has exactly two defensible uses on this cell:


1. **Supervision** — record `slip onset`, `contact patch centroid`, `shear` as
   *labels* and train the policy to avoid the pre-slip state (the P42 finding
   that escapes start from a *centred, two-sided* seat means the useful signal is
   the *shear ramp*, not the seat).
2. **Slow-loop grasp verification** — at the close boundary, where the
   validation ramp alone is **60 ticks = 0.5 s** (P91) and a 30 Hz sensor gets
   **15 samples** of it; a failed probe also costs **+1.53 s** (P40), so there is
   something to win there.

A **magnetic skin (AnySkin, MIT)** is the only family on the list that could be
a fast channel (magnetometer + microcontroller, no camera), but its rate is not
printed on the pages I checked [U] — that is the first thing to measure if a
reflex is ever wanted.

---

## 3. Dexterous hands, open

### 3.1 The table

| hand | open? | DoF / actuation | weight | fingertip tactile | sim assets | grasp evidence | price |
|---|---|---|---|---|---|---|---|
| **LEAP Hand** (CMU) | **code MIT, CAD CC BY-NC-SA** [V] | **16 DoF**, 4 fingers, Dynamixel XC330, tendon [V] | ~? [U] | **none native** (the SDK's readme lists none) [V] | **MuJoCo Menagerie `leap_hand` 16 DoF, MIT** [V]; **no Isaac Lab asset** [V] | RSS 2023; in-hand cube rotation sim2real [R] | **$2,000 parts, 4 h build** [V] |
| **ORCA Hand** (ETH) | **models MIT** (`orcahand_description`) [V]; hardware repo **NOASSERTION** — check before commercial [U] | **17 DoF**, tendon, popping joints [V] | [U] | **integrated tactile sensors** [V] | **MJCF + URDF**, `orca_sim` [V] | IROS 2025; **10,000 cycles / ~20 h** no failure; teleop, IL, zero-shot sim2real [V] | **<2,000 CHF material, <8 h build** [V] |
| **Aero Hand Open** (Chestnut/TetherIA) | **SDK Apache-2.0, design CC BY-NC-SA** [V] | **7 DoF / 16 joints**, tendon, 5 fingers [V] | **389 g** [V] | no [V] | **MuJoCo**, `mujoco_playground` RL tools [V]; no Isaac [U] | arXiv 2608.28578 (2026) [V] | **$314 kit** [V] |
| **DexHand 021** (DexRobot) | **commercial**; SDK/URDF open [V] | **19 DoF (12 active + 7 passive)**, tendon [V] | **1 kg** [V] | **yes: 23 sensors, 0-20 N, 0.1 N, >=50 Hz** [V] | "high-fidelity sim models" [R] | vendor: in-hand cube rotation [R] | not published [U] |
| **DexHand V1.0** (The Robot Studio) | **open** (NOASSERTION) [V] | ~? [U] | [U] | no | no [U] | hobby-grade [R] | low [R] |
| **Yale OpenHand** (T/T42/O/Q/M2/GR2) | **open hardware**; software repo **deprecated 2019**, ROS node `openhand_node` [V] | underactuated, 1-2 motors [R] | [U] | no | no | classic underactuated-grasp literature [R] | low [R] |
| **Allegro Hand V3** (Wonik) | **commercial**; **Menagerie BSD-2** model [V] | **16 DoF**, 4 fingers [V] | ~1.1 kg [R] | optional [U] | **MuJoCo Menagerie + Isaac Lab `allegro.py`, `kuka_allegro.py`** [V] | standard RL benchmark [R] | ~$15k class [U] |
| **Shadow Hand E3M5 / DEX-EE** | **commercial**; **Menagerie Apache-2.0** models [V] | **24 DoF** / **12 DoF** [V] | [U] | DEX-EE has tactile [R] | **Menagerie + Isaac Lab `shadow_hand.py`** [V] | the reference dexterous platform [R] | ~£100k class [U] |
| **Ability Hand** (PSYONIC) | **commercial** [V] | 5 fingers + powered thumb rotation, 6 motors [R] | **490 g** [V] | **integrated pressure sensors** [V] | none official [U] | prosthetic-grade durability, IP64 [V] | [U] |
| **Sharpa Wave** | **commercial**; **Menagerie Apache-2.0** model, **22 DoF** [V] | 22 DoF [V] | [U] | [U] | **Menagerie** [V] | new (2026) [R] | [U] |

### 3.2 The owner's hypothesis, stated honestly

**Hypothesis**: a dexterous hand is *more stable/firm* than a parallel jaw, so
it should hold the fruit the two flat pads lose.

**What the evidence actually supports.**

* **Theory supports it, and precisely for this failure mode.** A grasp resists a
  disturbance wrench iff the contact wrenches positively span the wrench space
  (force closure; Bicchi & Kumar, *Robotic grasping and contact: a review*,
  ICRA 2000 [R]). A two-pad pinch on a curved fruit gives at most two small
  frictional patches; the repo's own mechanism record is the textbook outcome —
  *"the pads hold and the payload slides"*, one-sided contact on 18 of 32 escape
  samples (`logs/p42/SIM_LIMIT.md` §0.4), payload walking **along the tool axis**
  off the distal lip (P61: `(-0.351,+0.240,+0.905)`, 25.2 deg from the tool
  axis). More independent contacts **on the far side of the fruit** is exactly
  what closes that direction.
* **The repo's own data says the *number* of contacts is not sufficient.**
  P41 raised the pinch 2.2x and the class did not convert; P76 raised it to
  **60 N** (6x) and the class shrank but did not close (P77: 7 -> 3 left escape
  legs, and the residue moved to a **3.4-7.9 mm axial** opening). A hand at
  **12 N fingertip** (DexHand 021 spec [V]) has *less* per-contact force than
  the 60 N cell. So the hand must win by **geometry (envelopment), not force** —
  which is testable and is the thing to test.
* **The counter-evidence is real**: the right arm places **96 %** with the same
  2-pad gripper (P59/P60); the class is arm/attitude-specific (left), not
  universal. And the policy already emits **10.9 % of joint steps out of range**
  on 7 DoF (P53) — a 16-DoF hand is 16 more joints for the same policy to get
  wrong.

**Verdict on the hypothesis: plausible, mechanism-consistent, and *unmeasured*.
Do not buy a hand on it.** Buy the measurement first — it costs a day in sim and
one bench rig (§3.3), not a purchase order.

### 3.3 The test that decides it (do this before any hand purchase)

**T1 — sim, offline, no policy**: on the existing fruit meshes, place a 2-pad
pinch and a 3-finger and a 4-finger+thumb grasp on the same 8 classes at the
same seat, and apply a **lateral + axial force ramp** to the payload until
`clean_slip > 2 mm`; report the **critical wrench** per grasp. If the hand does
not beat the pinch by **>= 1.5x** in the axial direction (the measured escape
direction, P61), the hypothesis is dead for **< $0**, and no hardware is bought.
Caveat to state in the report: the sim's pads are rigid and adhesion-free
(`SIM_LIMIT` §3), so **the sim can only falsify, never confirm** — a positive T1
is necessary, not sufficient.

**T2 — bench, one afternoon**: a GelSight Mini on a printed finger + a luggage
scale + the same fruit, pull until slip. Critical force for 2-pad vs a 3D-printed
3-finger cradle. This is the *real* test and it costs **~$1,020** (two Minis) plus
printing.

**T3 — only if T1 and T2 both pass**: the hand.

---

## 4. What the policy must become

### 4.1 The current model, exactly (so the delta is legible)

| item | value | source |
|---|---|---|
| denoiser | `ConditionalUNet1D`, 1-D conv, FiLM conditioning, **5 skill experts** with a router (hard routing then soft) | `policy/model.py` [V] |
| action | **9-D**: `action[:7]` arm joint targets, `action[7]` finger opening (clip `[0, 0.044]`), `action[8]` a mirror of 7 (recorded only) | `rl_env.py` docstring [V] |
| chunk | **16** actions, `obs_horizon` **2** | `moe_v13s` config [V] |
| proprio | **25-D** = 22 joint positions + finger opening + **2 tactile normal forces** | `rl_env.proprio()` [V] |
| goal | **8-D** `[pos(3), vel(3), diameter, bin_index]` | `moe_v13s` config [V] |
| vision | **one** head camera, **240x424** -> **128x128**, per frame **5 channels** (RGB 3 + depth 1 + instance mask 1), 2 frames -> **10 input channels** | `policy/data.py` [V] |
| schedule | DDPM train / **DDIM 100-step** sample, cosine betas | `policy/diffusion.py` [V] |
| checkpoint | `moe_v13s`, md5 `61da390a` | AGENTS [V] |

**Correction to the brief**: the direct env builds **one** camera, not two
(`scene.camera_sensor`, `scripts/60_eval_policy.py:304` reads `rgb` +
`distance_to_image_plane` from it; `policy/data.py:519-533` stacks RGB + depth +
mask per frame). The second camera only exists as an **option** on OpenArm 2.0's
gripper hardware [V]. Any hand stage must *add* the wrist view, and that is a
schema change on its own.

### 4.2 Four architectures and what each costs

Notation: `A` = arm DoF (7), `H` = hand DoF (7-17), `P` = proprio, `T` = tactile
channels.

**(a) Hand-conditioned action head — arm chunk + low-dim hand latent**

```
image ─┐
goal  ─┼─> condition (FiLM) ──> UNet1D ──> 9-D arm chunk (unchanged)
prop  ─┘            │
                    └─> phase token (from the 5-way router)
                          └─> hand head: 8-D latent z_h  ──decoder──> H joints
tactile ─> small encoder ─> adds to condition (not to the action)
```

* **Action space stays 9-D diffusion**, so the sampler, the RTC path
  (`policy/runtime.py`), the chunk turnover and the latency budget (71 ms,
  h <= 7, P52) are **untouched**.
* The hand decoder is trained **supervised** on the recorded hand joints (an
  autoencoder), so the diffusion model sees an **8-D** target, not 17. Sample
  complexity scales with the *diffused* dimension, which is the point.
* **New failure surface**: a decoder that maps two similar latents to different
  joint configurations; mitigate by decoding to a *phase-relative* hand pose
  (open / pre-close / closed / release) — 4 prototypes + residual.
* Cost: ~0.3-0.5 M params, **no change to the 25-D**; the *data* cost is the
  hand's joints in the episode schema.

**(b) Two-stage policy — arm chunk + a grasp-pose policy at the close**

* Stage 1 is the shipped policy, unchanged, up to `close` (the `[cycle]` blocks
  measured in P91: descent 3.64 s, grip 2.36 s, close 1.36 s, hover 0.75 s,
  prepose 0.71 s).
* Stage 2 is a **small policy** (MLP or 4-step diffusion) that sees the wrist
  image + tactile patch at `close` and emits the **hand configuration** (a
  pre-grasp synergy + a close command), not a 16-D trajectory.
* **Best property**: it cannot corrupt the arm's 72.5 %; if stage 2 is bad, the
  cell degrades to today's behaviour.
* **Worst property**: the hand cannot help during `lift`/`place`, which is
  exactly where the `cnp` class happens (`loss_row` 103-150 of a ~160-tick leg,
  P71; onsets 105/140/142/159 in P75) — so
  it can only fix the *seat*, and P42 measured the seat to be already centred
  (1.4-4.6 mm). **This architecture is predicted to fail on this cell**, and
  that prediction is a useful pre-registration.
* Cost: one small model, one new phase boundary, no schema change to the arm.

**(c) Single high-DoF policy — hand joints in the action vector + tactile fusion**

* `action_dim` 9 -> 9 + (H - 1) = **15-25**, diffusion over all of it.
* **The measured facts are against it**: P52 found the chunks are **noise, not a
  trajectory** (within-chunk min p50 **2.44 rad/s**, **0/60** below 0.30 rad/s,
  `|2nd|/|1st|` 1.16) and P53 found **10.9 %** of joint steps out of range with
  a clamp that is free but **null** on the class. Diffusing 16 more dims with
  that emission quality is how a hand gets damaged on the first real run.
* It is the *right* architecture for in-hand manipulation later (the hand must
  act *during* the carry, and only (c) can), but it is the wrong **first**
  architecture.
* Cost: full recollection, a bigger denoiser, and a joint-limit clamp that must
  be **structural** (not a post-hoc clip), plus a safety envelope per finger.

**(d) No-tactile-first hand — what the observation becomes**

* Proprio: **22 + H + 2** = **25 + (H - 1)**. For LEAP/ORCA (16-17 DoF) that is
  **40-41-D**; for Aero (7) it is **31-D**. The finger-opening scalar is
  *replaced* by the hand's joints, not added.
* Vision: **+ a wrist camera** (the hand occludes the head view at the grasp).
  That is 5 channels per frame per view -> **8-10 across two views**, or two
  separate encoders summed into the condition (cheaper, and the right call: the head
  camera's global context and the wrist's local patch are different statistics).
* **Which measured lessons still bind**:
  1. **Emission tests bind harder.** Clamp the hand's targets to
     `get_dof_limits()` **by construction** (a `tanh`-scaled output), because
     P53's clamp was free but a *post-hoc* clamp on a 16-DoF hand is a hardware
     risk, not a null.
  2. **Phase structure binds.** The 5-expert router already encodes the phases;
     the hand must be **inert outside `grip`/`close`/`release`** (a mask, not a
     learned preference) — the hand's job in `descent`/`hover` is to be open and
     out of the camera.
  3. **The 14.2 % share binds the business case.** A hand cannot buy throughput
     (P52's 4.8 % ceiling on the whole policy phase). Its ROI is the **75 %
     failure class**.
  4. **The 71 ms / h <= 7 latency budget does not bind** — the UNet cost is
     dominated by the visual encoder, and an 8-D head adds microseconds; a
     *second camera* is the real cost (+1 encoder pass).

### 4.3 Recommendation for this repo's next stage

**Adopt (a), with (b) as the safety net and (c) as the later research arm.**

Why (a) and not (c): the diffused dimension is the *sample complexity*, and this
repo's scarcest resource is **demonstrations on a hand that does not exist yet**.
(a) keeps the 9-D problem the tree has already solved (158 + 180 episodes of
evidence, a 5-expert router, a working RTC path) and puts the new DoF behind a
**supervised decoder** that can be trained on *scripted* hand poses before any
policy sees them. It also keeps the failure mode **bounded**: a bad latent is a
bad hand pose, not a bad arm trajectory.

Why not (b) alone: P42 measured the seat to be centred (1.4-4.6 mm) and the walk
to be 104-276 mm — a stage-2 policy that only fixes the seat is fixing the term
that is already 30-60x too small.

**Data cost, concretely.**

| item | today | after a hand | note |
|---|---|---|---|
| episode schema | 25-D proprio, 9-D action, 1 camera | **40-D proprio, 9-D action + 8-D latent, 2 cameras** | every store is invalid |
| store | `datasets/demos_v12` **158 episodes**; `p33_pear` **180 episodes / 32,670 windows** | **>= 150 episodes** of the new schema (the v12 number, because the hand adds a failure mode) |  |
| collection wall | **2 h 6 min for 158 episodes** (W3, one shard, no wedge) | **~2-4 h** (the wrist camera adds render time; the bimanual scheduler pays 1.69x wall/sim after P82's wake fix, 2.57x before it) | measured anchor, not an estimate |
| fine-tune | `moe_v12 -> moe_v13s`, 6 epochs, loss 0.0261 | same recipe from `moe_v13s` |  |
| references | `30fb99f8` / `30fb99f8` / `8952c320` | **all three re-recorded** (the hand moves the scene's collider set, P71's precedent) |  |

The honest sentence: **a hand is a recollection, and the recollection is the
cheap part (2-4 h); the expensive part is that every number in AGENTS §2 becomes
a pre-hand number.**

---

## 5. The recommendation: a staged path with kill criteria

### 5.0 The baseline the new platform must beat

Measured on the shipped tree (P93's four control seeds, 20 attempts each):

| metric | value |
|---|---|
| placed | **58/80 = 72.5 %** |
| failures | **25**: `cnp` **17** (68 %), never-held 5, other 3 |
| interval (pooled per seed) | **10.59 / 11.08 / 12.16 / 11.53 s** |
| s/attempt | **9.50 / 9.10** (seeds 5/6) |
| wall rate | **2.37-2.91 placed/min** (the four control cells) |
| acceptance | **8/10, 9.0 s/attempt**, `fingerprint: matches` (P98) |

Note the brief's "9.4-11.1 s" is the **two-seed** subset (9.4 s/attempt ≈ the
shipped acceptance; 10.59/11.08 s interval); the four-seed range is **10.6-12.2 s**.
The class share is **75 %** on the P92 census (9 of 12) and **68 %** on P93's
four-seed pool — quote the range, not one number.

### 5.1 Stage (i) — tactile on the current gripper  *(cheapest; tests the tactile hypothesis with the existing policy)*

**Build**: two GelSight Mini (**$510 each** [V]) or two 9DTact (MIT [V]) on
reprinted OpenArm 2.0 fingers; record `slip onset`, `patch centroid`, `shear` at
the sensor's native rate; keep the existing 2-scalar channel as the fallback.

**Sim first (free)**: upgrade the sim's tactile channel from 2 scalars to a
**contact-patch field** (contact points + normals from the existing
`ContactSensor`, aggregated to a 4x4 patch per finger). That is the *same
information* a real pad gives, it needs no asset, and it lets the policy work be
done before the hardware ships. The sim **cannot confirm** a sensor (it has no
visuotactile renderer), but it *can* prove the plumbing and falsify the
policy-side claim at **$0** — which is why it runs first.

**Endpoints (pre-registered; a 2-seed x 20-attempt screen, then the P93
four-seed harness to confirm):**
* **P1 (mechanism)**: slip onset is detectable **>= 10 ticks (83 ms)** before
  `clean_slip > 2 mm`, on **>= 70 %** of escapes. Below 50 % → the sensor is a
  labeller, go to P2.
* **P2 (policy)**: `cnp` falls **>= 30 % relative** (17 -> <= 12 of 80 pooled) and
  placed rises **>= +8 points** (72.5 -> >= 80.5 %).
* **P3 (no harm)**: interval not worse by **> 5 %**; landing 100 %.

**Kill**: P2 fails at both seeds → tactile on a parallel jaw is a *labeling*
channel on this cell; do **not** put tactile on the hand first (stage iii is
deferred until the hand exists and its class is re-measured).

**Cost**: ~$1,020 sensors + printing + ~1 week. **Sim-vs-real**: the patch
channel and the policy plumbing are sim; the *sensor* claim is real-only.

#### Status: the mechanism is **CONFIRMED** by measurement (P102, 2026-11-03, `logs/p102/`) — the sensor is not

The free sim half of this stage ran (`logs/p102/RESULTS.md`). On the shipped cell,
40 attempts, 2 seeds:

| read | value |
|---|---|
| the payload's in-hand displacement reaches **2 mm** | **21-113 ticks before the pinch is lost** - median **60 ticks = 0.50 s**, min **21 = 0.17 s**, 6/6 escapes |
| the patch's state when the walk starts | `frac` 0.52-0.79, `edge` +4.0..+17.2 mm - **on the pad** |
| the walk's rate | 7-189 mm/s → **a 30 Hz pad gets 5-28 frames (median 15)**, a 60 Hz pad 10-56 |
| the payload's position **when the force collapses** | already **4.5-46.4 mm** out |
| false positives (60 held legs) | 2 at 2.12 mm, **both placed**; occupancy thresholds 0/60 |
| the class it can reach | **6 of the 11 failures** (all seated slides on `cnp` attempts, 0 of 29 placed attempts); the **4 acquisition failures are unreachable by any pad** |

**So P1 passes in its decision-relevant form and stage (i)'s kill does NOT
fire** — but **P1 as written is not evaluable**: it asks for a lead over
`clean_slip > 2 mm`, and the patch centroid's displacement *is* that
displacement (`dc/clean` 0.77-1.00), so it crosses on the same tick. The
reference that matters is "before the pinch is lost", and it is 0.17-0.94 s.
**This also corrects §2.4 below**: W5-C's 0-3 ticks is the **normal force's**
last moment, not the slip's first.

**What is still to buy, and it is small**: the sim's patch is derived from the
payload's *ground-truth pose* (rigid, adhesion-free pads; no visuotactile
renderer), so the **duration and magnitude** of the relative motion transfer and
**"does a soft pad image 2 mm"** does not. That is §3.3's **T2 bench** — one
GelSight, one printed finger, the same eight fruit, ~an afternoon — and it is
now the only open question in this stage. The **next sim spend is the reaction,
not the sensor** (registered, not built): a re-grip at `dc >= 2 mm` fires on 8 of
70 legs and costs **0.25 s/attempt worst case = 2.6 %** of a 9.7 s attempt, to be
scored on P2 (`cnp` 6 → <= 4 of 40) and P3.


### 5.2 Stage (ii) — a dexterous hand, no tactile

**Build**: **ORCA** (17 DoF, <2,000 CHF, integrated tactile *already*, MJCF/URDF
MIT) is the best value but its **hardware licence is NOASSERTION** [U] — resolve
that before a product decision. **Aero Hand Open** ($314, 7 DoF/16 joints, MJCF +
ROS 2, design CC BY-NC-SA) is the cheap pilot. **LEAP** ($2,000, 16 DoF, MJCF
MIT) is the best-documented for RL but its **CAD is CC BY-NC-SA** [V] — fine for
research, not for a product. **DexHand 021** is the one with **native tactile
(0-20 N, >= 50 Hz)** but it is commercial and priced by quote [U].

**Sim first**: **there is no Isaac Sim USD for LEAP or ORCA** [V: Isaac Lab's
asset list has `allegro.py`, `shadow_hand.py`, `kuka_allegro.py`, `openarm.py`,
`so101.py` — no LEAP, no ORCA]. Two routes:
* **Cheap**: convert the MJCF (LEAP/ORCA) with Isaac Sim's MJCF importer; the
  MuJoCo models are MIT and well-formed. Costs a week of asset work and a
  `253`-style selfcheck leg pinning the joint names.
* **Fast**: use **Allegro 16-DoF** (already an Isaac Lab asset [V]) as a
  *stand-in* for the class test, then buy the real hand. Allegro is the wrong
  geometry and the right DoF count; it answers "does a 16-DoF hand hold this
  fruit better" without an asset pipeline.

**Endpoints**: run **T1** (§3.3) first — if the sim hand does not beat the pinch
by 1.5x axially, **kill before purchase**. Then, if purchased: recollection of
**>= 150 episodes**, and
* **P4**: placed **>= 82.5 %** pooled (>= +10 points over 72.5 %) at **2 seeds**.
* **P5**: `cnp` falls **>= 50 %** (17 -> <= 8).
* **P6**: interval **<= +10 %** (a hand is heavier; a small regression is
  acceptable if P4/P5 pass).

**Kill**: P4 or P5 missed at both seeds → the hand does not fix this class; the
residue is `SIM_LIMIT`'s pad *face* geometry and the next spend is a custom pad,
not a hand.

### 5.3 Stage (iii) — tactile on the hand

Only after (ii) passes. **ORCA's integrated tactile** is the zero-integration
path [V]; otherwise 9DTact/Mini pads on the fingertips.

**Endpoint**: **P7**: the tactile-fused policy beats the *same hand* without
tactile by **>= +5 points** placed. Below that, tactile is not paying for its
wiring.

**Kill**: P7 missed → ship the hand without tactile and keep tactile as a
data-collection instrument.

### 5.4 Why this order, in one line each

* (i) is **$1k and reuses the entire policy** — it tests the *tactile* half of the
  hypothesis before the *hand* half, and its failure mode is "we learned the
  slip is unobservable in time", which is decision-grade on its own. **That half
  is now measured and it is not the failure mode** (P102, `logs/p102/`): the
  relative motion is observable for **0.17-0.94 s**, so what (i) now buys is the
  *sensor* confirmation (§3.3 T2) plus the reaction the sim can price for free.
* (ii) is **$0.3k-$2k** and tests the *geometry* half, which is the half the
  theory and `SIM_LIMIT` actually support.
* (iii) is the only stage that needs **both** and it is the only one that cannot
  be simulated today (no visuotactile renderer in the loop).

### 5.5 What would make me reverse the recommendation

* **T1 negative** (a hand does not beat the pinch by 1.5x axially in sim): the
  hypothesis is dead; spend the money on a **custom pad** (the `SIM_LIMIT`
  sanction) instead.
* **ORCA's hardware licence** turning out non-commercial **and** the product
  needing one: switch to Aero ($314) for the pilot and Allegro (commercial,
  Isaac-native) for the product, and re-price.
* **A second camera is not affordable** on the compute budget: then (a) cannot
  see the hand, and the fallback is (b) + the in-hand camera only.

---

## 6. Sources (all fetched 2026-11-03 unless stated)

**Primary, verified**

* `https://github.com/enactic/openarm` — repo, Apache-2.0, 3,666★/392 forks, pushed 2026-11-02; README: "$6,500 USD for a complete bimanual system"; sub-repo licences (hardware CERN-OHL-S-2.0, description/can/ros2/mujoco/isaac_lab Apache-2.0).
* `https://docs.openarm.dev/` and `/hardware/openarm-2.0/general` — 7 DoF/arm, 4.1 kg nominal / 6.0 kg peak incl. EE, CAN-FD, QDD.
* `https://docs.openarm.dev/hardware/openarm-2.0/gripper` — replaceable fingers, in-hand Arducam B0495 (1920x1200@50 fps, UVC, 95 deg DFOV).
* `https://docs.openarm.dev/purchase/` — vendor price list, $4,699-$7,080.
* `https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_assets/isaaclab_assets/robots/openarm.py` — `OPENARM_BI_CFG`, USD path `Robots/OpenArm/openarm_bimanual/openarm_bimanual.usd`, effort 40/27/7 N.m, velocity 2.175/2.61 rad/s, finger effort 333.33.
* `https://github.com/isaac-sim/IsaacLab/tree/main/source/isaaclab_assets/isaaclab_assets/robots` — asset list: `openarm.py`, `allegro.py`, `shadow_hand.py`, `kuka_allegro.py`, `so101.py`, `kinova.py`, `franka.py`. **No LEAP, no ORCA.**
* `https://huggingface.co/docs/lerobot/openarm` — `openarm_follower`, `bi_openarm_follower`, `openarm_leader`, CAN FD, 30 fps record.
* `https://github.com/huggingface/lerobot/tree/main/src/lerobot/robots` — `bi_openarm_follower`, `bi_so_follower`, `koch_follower`, `reachy2`, `unitree_g1`, `hope_jr`.
* `https://github.com/huggingface/lerobot/tree/main/src/lerobot/policies` — act, diffusion, pi0, pi05, smolvla, tdmpc, vqbet, rtc.
* `https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/main/README.md` — DoF + licence per model: `aloha` 16 BSD-3, `leap_hand` 16 MIT, `wonik_allegro` 16 BSD-2, `shadow_hand` 24 Apache-2.0, `shadow_dexee` 12, `sharpa_wave` 22, `tetheria_aero_hand_open` 16 Apache-2.0, `robotstudio_so101` 6, `trs_so_arm100` 6, `low_cost_robot_arm` 6, `i2rt_yam` 8 MIT, `agilex_piper` 8 MIT, `arx_l5` 8, `ufactory_xarm7` 13, `kinova_gen3` 7, `franka_fr3` 7, `pal_tiago_dual` 25, `rainbow_robotics_rby1` 28.
* `https://arxiv.org/abs/2304.13705` — ALOHA: 6 tasks, 50 demos, 80-90 % success, ACT.
* `https://arxiv.org/abs/2405.02292` — ALOHA 2: open hardware + **MuJoCo model with system identification**.
* `https://github.com/tonyzhaozh/aloha` MIT 2,361★; `https://github.com/MarkFzp/mobile-aloha` MIT 4,478★.
* `https://github.com/TheRobotStudio/SO-ARM100` Apache-2.0 7,970★; `https://huggingface.co/docs/lerobot/so101` — 6x STS3215, USB bus.
* `https://pollen-robotics.com/reachy-2/` — 7 DoF/arm, 3 kg/arm, ROS 2 Humble, open HW+SW.
* `https://github.com/pollen-robotics/reachy2_core` Apache-2.0; `reachy2-sdk` Apache-2.0.
* `https://raw.githubusercontent.com/i2rt-robotics/i2rt/main/README.md` — MIT; YAM 7-DoF 0.808 m reach, 5.844 kg; MuJoCo models; bimanual examples.
* `https://raw.githubusercontent.com/dexmate-ai/dexmate-urdf/main/README.md` — Apache-2.0 models, Vega-1, F5D6 hand / gripper, USD releases, Isaac-tested.
* `https://github.com/Kinovarobotics/ros2_kortex` NOASSERTION 133★.
* `https://raw.githubusercontent.com/facebookresearch/digit-design/main/README.md` — **CC BY-NC 4.0**, DIGIT + DIGIT Pinki, firmware binary.
* `https://digit.ml/` — DIGIT 360: 18+ sensing features, 7 um, 1 mN.
* `https://www.gelsight.com/product/gelsight-mini-system/` — **$510**, USB, 4-week lead (page last modified 2026-08-12).
* `https://github.com/gelsightinc/gsrobotics` GPL-3.0 206★.
* `https://raw.githubusercontent.com/linchangyi1/9DTact/main/README.md` — MIT, code + hardware source, "commercial purposes", RAL 2023, ROS.
* `https://raw.githubusercontent.com/armlabstanford/DenseTact/main/README.md` — dataset + STL only.
* `https://raw.githubusercontent.com/raunaqbhirangi/anyskin/main/README.md` — MIT, QT Py USB-C serial, `pip install anyskin`; paper arXiv 2409.08276 (NeurIPS 2024).
* `https://raw.githubusercontent.com/pollen-robotics/tactile_gripper/main/README.md` — Apache-2.0, AnySkin + slip LSTM + HF dataset.
* `https://raw.githubusercontent.com/leap-hand/LEAP_Hand_API/main/readme.md` — 16 DoF class, Dynamixel XC330, USB serial <= 500 Hz, 300/550 mA, **code MIT / CAD CC BY-NC-SA**; `leaphand.com` — **$2,000 parts, 4 h**.
* `https://arxiv.org/abs/2504.04259` — ORCA: 17 DoF, **integrated tactile**, <2,000 CHF, <8 h, IROS 2025, 10,000 cycles.
* `https://github.com/orcahand` — `orcahand_hardware` (NOASSERTION), `orcahand_description` (MIT), `orca_sim`, `orca_ui`; also a **fork of openarm**.
* `https://raw.githubusercontent.com/TetherIA/aero-hand-open/main/README.md` — 7 DoF/16 joints, 389 g, **$314**, Apache-2.0 SDK / CC BY-NC-SA design, MuJoCo, ROS 2, arXiv 2608.28578.
* `https://www.dex-robot.com/en/productionDexhand` — DexHand 021: 19 DoF (12+7), 1 kg, >=12 N fingertip, >=38 N grasp, CAN FD, tactile 0-20 N @ >=50 Hz, 23 sensors.
* `https://raw.githubusercontent.com/grablab/openhand-software/master/README.md` — deprecated 2019, `openhand_node` successor.
* `https://www.psyonic.io/ability-hand` — 490 g, integrated pressure sensors, IP64.

**Reported / secondary**

* `https://robotsguide.com/robots/reachy` — Reachy 2: $36k-$70k, 166 cm, 50 kg.
* `https://www.trossenrobotics.com/post/robot-hand-types-guide` — LEAP ~$2,000; ORCA <2,000 CHF.
* `https://arxiv.org/html/2511.03481v1` — DexHand 021: 12 active + 7 passive DoF.
* `https://github.com/linchangyi1/Awesome-Touch` — tactile index (Tac3D, CrystalTac, FlexiTac).
* `https://flexitac.github.io/` — FlexiTac 2026 open tactile (not fetched).
* `https://github.com/facebookresearch/tacto` — MIT, DIGIT simulator.

**Could not verify (explicit)**

* **OpenArm reach**: no vendor figure on any page I fetched; the only number is
  this repo's own TCP reach **~0.68 m** (`scripts/12_reach_calibration.py`,
  README §"Robot choice"). Marked [V] *as a repo measurement*, [U] as a spec.
* **OpenArm gripper stroke / pinch force**: not published on the 2.0 pages;
  the sim's 44 mm stroke and 10 N/joint are the repo's parameters [V, in-repo].
* **ALOHA kit price**, **Cobot Magic price**, **Koch/SO-101 vendor price**,
  **Allegro / Shadow / Ability / DexHand prices**: no official page checked
  printed one; not estimated.
* **Tac3D** official open-hardware repo: not found; the sensor's paper is
  arXiv 2202.06211 [R] and the `wngfra/tac3d` repo is a *simulation* package.
* **uSkin**: commercial only, no open hardware found.
* **AnySkin sample rate**, **GelSight Mini force range**: not printed on the
  pages checked.
* **ORCA hardware licence**: repo licence is `NOASSERTION`; resolve before a
  commercial decision.
* **Isaac Sim visuotactile rendering**: no verified first-party renderer found
  in the sources checked; TacTO is standalone (not in the Isaac loop).

---

## 7. One-paragraph answer to the owner

**Stay on OpenArm** — it is already the cheapest credible dual-arm cell
($6,500, Apache-2.0, Isaac Lab + LeRobot bimanual), and none of the families
this repo has closed is an arm object. **Buy tactile first** (two GelSight Minis,
$1,020, or 9DTact if the licence must be commercial), and test the *tactile*
half of the hypothesis in sim with a contact-patch channel before the sensors
land. **Then buy a hand** — ORCA (17 DoF, tactile integrated, <2,000 CHF) or
Aero ($314) — but only after the free sim pull-test shows a hand beats the pinch
by 1.5x in the axial direction, which is the direction the payload actually
leaves (P61). **The policy becomes (a)**: the 9-D arm chunk stays, an 8-D hand
latent is decoded to the hand's joints, tactile enters the condition vector, and
the hand is inert outside `grip`/`close`. **The business case is the 75 %
`cnp` class, not the 14.2 % policy phase** — a hand that does not move `cnp` is
a $2,000 paperweight, and the kill criteria in §5 are written to find that out
at the cheapest possible stage.
