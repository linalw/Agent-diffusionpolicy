# The hand stage: asset, schema, architecture, data, milestones

**A plan, not a measurement.** Written 2026-11-03 (P105). No simulator run, no
`src/` change, no `configs/` change; the artefacts are this file and a
`WORKLOG.md` entry. Every number below is either measured in this repo (with the
file that carries it), derived from measured numbers by arithmetic shown here, or
marked as an estimate. Nothing here is a rate.

| mark | meaning |
|---|---|
| **[M]** | **measured** in this repo; the file and (where it exists) the line are named |
| **[D]** | **derived** here from [M] numbers by the arithmetic printed beside it |
| **[E]** | **estimate** - a price or a quantity this phase did not measure. Do not quote it as a result |
| **[U]** | **unverified** - needs a fetch, a purchase or a bench run before it can decide anything |

The three things this plan must not re-derive, because they are settled:

1. **The hand is justified on the mechanism, at 1.5-2.0x, and it is necessary
   not sufficient.** `logs/p104/RESULTS.md` §3/§5: a 4-contact grasp reads
   **1.87-2.05x** the shipped pinch's sustained axial break-away, a 3-contact one
   **1.33-1.64x** (and *fails* the same survey's 2 mm criterion at 1.05/0.94/1.48x
   because it re-seats), and at the **operating load** the pinch creeps
   **3.20-3.84 mm** on the pear against 0.15-0.44 mm for 3/4 contacts - **9-15x**.
2. **The tactile is a supervision channel, not a reflex.** `logs/p102` sees the
   slide 0.17-0.94 s early; `logs/p103` gives a *perfect detector* for free and
   the reaction still converts **0 of 5** same-instance `cnp`s and **destroys 2 of
   2** placements, at **+15.3 %** interval. The binding term is the two-line's own
   P10-C monitor at **8.0 mm**.
3. **The policy owns 14.2 % of the episode and its chunks are noise.**
   `logs/p52/P2A_RESULTS.md`: 256 of 1800 ticks, a 1.5x on the whole phase is
   worth at most **4.8 %**; `logs/p52/P2B_FEASIBILITY.md`: within-chunk minimum
   p50 **2.44 rad/s**, **0/60** chunks below 0.30 rad/s, `|2nd|/|1st|` **1.16**.
   `logs/p53/P53_RESULTS.md`: **10.9-11.0 %** of joint steps out of range
   (8 341 of 76 587), and the clamp removes **all** of it at **zero time cost**
   for **zero class gain**.

---

## 0. The answer in one page

1. **The first asset is the Allegro 16-DoF hand, mounted on
   `openarm_{side}_hand`** - and it is the *only* candidate that is both
   Isaac-native and **direct-drive** (16 motors, no tendon). Its USD is
   **verified present** on the asset root this tree already reads:
   `…/Assets/Isaac/6.0/Isaac/Robots/WonikRobotics/AllegroHand/allegro.usd`
   (HTTP 200, 1 626 251 B; the survey's "no LEAP, no ORCA USD" stands). The
   conversion route (MJCF/URDF → USD) is **not spent at M1**.
2. **But the Allegro is a *mount and topology probe*, not the purchase
   candidate.** Its geometry is **3 fingers + 1 opposed thumb**; the fixture that
   passed the bar was a **radial 4 x 90 deg** quad. **No candidate hand is
   radial** (ORCA 5 fingers, LEAP/ALLEGRO 3+1, DexHand 5) - so P104's 2.0x is a
   property of a grasp topology **nobody can buy**. The plan therefore runs the
   in-scene pull test on **two forms**: the Allegro (mounted, real) and a
   **4-pad surrogate** (the fixture's radial geometry, in-scene). It is the
   surrogate that licenses a purchase, and the prediction is that the Allegro
   lands **at or below** the 1.5x bar (1.2-1.6x, §1.7).
3. **The observation widens 25 → 34-D, not to 40.** v1's 22 joint channels
   include **4 that carry no information** (measured: < 1 mrad of motion over 40
   episodes, §2.2); v2 = **14 arm + 16 active-hand + 4 tactile = 34**. The
   inactive hand is **not** carried, because P36 measured the inactive arm's
   proprio to be null (the win is the image).
4. **The action vector does not widen.** It stays **9-D** (7 arm + the finger
   channel, which becomes the hand's **synergy scalar**). The hand's 16 joints are
   decoded from an **8-D latent** emitted by a second head on the same UNet trunk
   and trained **supervised**; the diffused dimension stays 9, which is P52's
   "the chunk is noise" read taken seriously.
5. **The hand acts at the decision rate, not the physics rate**: 4 ticks/decision
   shipped (33 Hz, `execute_steps=4`), or 8 ticks (15 Hz) as P53's measured
   `action_hold=2` cell (-7.1 % wall, decisions 61 → 29). The first cell runs
   **4 ticks**; the 8-tick form is a measured wall lever for later, and both need
   the shipped **RTC** path once the wrist view takes a decision to ~95 ms (§3.5).
6. **Every store is invalid, and the collector cannot produce a usable one**:
   `dataset.py:147-152` **discards every failed attempt**. A hand store built
   through the collector would contain no `cnp` example at all - the exact defect
   P33 phase 3 recorded ("successes-only, 52 carried-not-placed discarded"). The
   store must come from the **direct-rollout path with failures kept**.
7. **The recollection is 2.5-3 h against the 2 h 6 min W3 anchor**: 158 episodes /
   2 h 6 min with one camera [M]; a wrist view adds one render per recorded frame
   (32 298 frames in `demos_v12`) → **2.5-3 h and ~15 GB** [E]. The fine-tune is
   **< 1 GPU-hour** (6 epochs x 201 s at 38 990 windows [M]).
8. **The architecture is (a) hand-conditioned head**, chosen against (c) for a
   measured reason: (c) diffuses 16 more dimensions with the same emission quality
   that already puts 10.9 % of joint steps out of range (§3.1).
9. **The ceiling is arithmetic and must be quoted with every result.** On P93's
   four-seed baseline (58/80 = 72.5 %, **22** failures = 17 `cnp` + 5 never-held)
   the hand attacks **17 of 22 failures**; all of them converting is **93.8 %**,
   the P102-measured seated-slide share of that class (6 of 7) is **91.3 %**, and
   the **5 never-held are acquisition failures no contact count can reach**
   (§5.0). *The survey's "25 failures, `cnp` 68 %" is a mis-derivation* - 58 + 17
   + 5 = 80, so `cnp` is **77 % of the failures**, and the P4 bar of 82.5 % needs
   exactly **8 of the 17** to convert.
10. **The five milestones** M1 asset → M2 in-scene pull test → M3 scripted hand →
    M4 policy → M5 adoption, each with a kill, in §5; total **170-265 h labour,
    ~26 h simulator wall, ~17 GPU-hours, **0 hardware before M3** [E] - M2 licenses
    the geometry, M3 licenses the purchase.

---

## 1. The asset

### 1.1 What the tree already owns, as a contact the hand must beat

| quantity | value | source |
|---|---|---|
| plate face | **61.000 x 84.902 mm** (AABB 33.261 thick) | `logs/p66/COLLIDER_READ.md` §2; constants at `tasks.py:1402-1422` |
| distal plane below the jaw centre | **80.5 mm** (`FINGER_TIP_BELOW_JAW`) | `tasks.py:79` |
| commanded standoff (grasp centre) | **70.0 mm** = `FRUIT_FINGER_LEN` 60 + `PAD_LIFT` 10 | `tasks.py:9404-9427` |
| lip past the grasp centre | **10.5 mm** = 80.5 - 70.0 | [D] |
| drive | `k` **1e5 N/m**, `c` **2000 Ns/m**, `maxForce` **10 N**, `c/k` **0.02** | `control.py:62-64`, `scene.apply_finger_maxforce` |
| delivered pinch | **9.75-9.9 N over two faces = 4.90 N per face** | `logs/p41/P2_RESULTS.md`; `logs/p104/RESULTS.md` §3 (fixture at 4.90) |
| pad friction / contact damping / compliance | **2.0** / **60** / **0** | `scene.py:626-648`, `_add_physics_material` `scene.py:116-160` |
| fruit friction draw | 0.52-0.81, per-class | `meshes.FRUIT_SHAPES`, reported in the `physics` block |
| **the pair rule** | PhysX combines by **average**, implied `mu_app` **1.05-1.45** | `logs/p104/RESULTS.md` §7(a) - and `scene._add_physics_material`'s comment says *minimum*, which that measurement contradicts |
| sustained axial capacity | **11.03 / 14.21 / 12.69 N** (pear / orange / strawberry) | `logs/p104/RESULTS.md` §3 |
| creep at the operating load | **3.20-3.84 mm** on the pear | `logs/p104/RESULTS.md` §5 |
| the escape | along the **tool axis** `(-0.351, +0.240, +0.905)`, 25.2 deg off it | `logs/p61/P2_RESULTS.md` |

The hand must be authored so that **the comparison at M2 is the contact count and
not the force** - that is, **same per-contact normal force (4.90 N), more
contacts**. P76/P77 already measured what a *force* raise buys: 30 N does not
relieve the pry, 60 N shrinks the escape class 7 → 3 without closing it, and a
global 60 N cap moves the scripted acceptance at attempt 0 and both references
(`logs/p77/RESULTS.md`). A hand authored at 12 N per fingertip would be a
*weaker* force test than the shipped pinch's 4.9 N per face - it must not be used
as one.

### 1.2 The mount, concretely (and the defect it exposes)

The arm's articulation is **22 DOF** in a fixed order, measured from a log
(`[fruit] dof_names: …`, `num_dofs=22`):

```
 0-13  openarm_{left,right}_joint1..7        (interleaved: L1,R1,L2,R2,...)
14-15  openarm_left_finger_joint1, joint2     (prismatic, the two pads)
16     openarm_left_hand                      <- a joint, not a link
17-18  openarm_right_finger_joint1, joint2
19     openarm_right_hand
20-21  openarm_{left,right}_ee_tcp_joint
```

`openarm_left_hand` is a **PhysicsRevoluteJoint** from `openarm_left_link7` to
`openarm_left_hand` with `axis = "Z"`, `stiffness = 0`, `damping = 0`,
`maxForce = 3.4e38` (`assets/openarm_flat/openarm_flat_deinst.usda:3845-3857`),
and `openarm_left_ee_tcp_joint` is the same thing again from the hand to the TCP
(`:3869-3880`). So **the gripper is mounted on an undriven revolute joint about
the tool axis, and the TCP is a second one**. This is not a detail:

* it is why the 4 dead proprio channels exist (§2.2) - they are that joint's angle
  and the TCP frame's, and they move < 1 mrad because nothing drives them;
* **a 1.1 kg 16-DoF hand must be welded on**, not bolted to a free joint: the
  hand's own inertia plus four contact wrenches would spin it. The mount is
  therefore `PhysicsFixedJoint` (or a driven revolute held at 0), and that removes
  **2 DOF per arm**;
* the **TCP frame the whole control stack commands** is `openarm_{side}_ee_tcp`
  (`control.arm_spec`, `control.py:43-49`), i.e. the *pad* frame. A hand changes
  what that frame means, so the grasp-centre offset must be re-derived, exactly as
  `_pad_standoff` was.

**DOF arithmetic after the mount** (one hand on both arms): 22 − 4 finger − 2
hand joint − 2 TCP joint + 32 hand = **46**. Per arm: 7 arm + 16 hand = 23.

**The flange bolt pattern is [U]**: this repo has no drawing of the OpenArm
wrist's bolt circle, and neither does the survey. It is a bench measurement, not
something a sim phase can settle - and it is the **only** hardware fact M1 cannot
simulate. Price it as one afternoon with the arm and a caliper, and note that the
survey already establishes the thing that matters: OpenArm's **fingers are
replaceable by design** and the OpenArm 2.0 gripper carries an in-hand camera
[V], so an end-effector swap is the vendor's intended use.

### 1.3 Collision and friction authoring

The tree's proven route is `scene._add_finger_colliders` (`scene.py:1046-1090`):
walk `{link}/visuals`, apply `CollisionAPI` + `PhysxConvexHullCollisionAPI` to each
mesh, and **assert** the verdict in `openarm` mode
(`assets.assert_finger_colliders`, `assets.py:143`) because a collider-less build
is the old "fruit floats" configuration. Two measured caveats travel with it:

1. **The palms have no colliders at all** - the P39/P66/P69 build prints all read
   `palms unchanged: openarm_left_hand=0 prims, openarm_right_hand=0 prims`
   (`logs/p66/collider_S.log:355`). So authoring a hand's palm collider is **new
   geometry in the contact set**, and by P71's precedent (`logs/p71/RESULTS.md`
   §1: removing two rail boxes moved the release `y` by 8 mm at stripped line 121
   and the fingerprint DIFFERS) it **re-baselines every reference**. A hand stage
   that does not add a palm collider keeps one variable out; the plan therefore
   **does not author the palm's collider at M1** and adds it only if M2's contact
   census shows the palm is needed.
2. **The finger plates are authored boxes, not meshes** (`_author_finger_tip_delta`
   → `_author_flat_face`, `scene.py:1297/1332`), and P39's `FRUIT_FINGER_TIP_DELTA`
   showed the authored size is exact (`84.902 → 80.902 mm`, `4*cos(0)` to
   < 0.001 mm). For a hand the same instrument exists (the visual mesh), and the
   analogue of the lip is the **fingertip body's distal plane**.

**Friction is the one place the hand's authoring can silently change the
comparison.** `mu = 2.0` on the pads, 0.52-0.81 on the fruit, and the engine's
**average** combine (measured, `logs/p104` §7a) gives 1.26-1.41. A hand whose
fingertips are authored at a different `mu` is a different contact, and the
per-contact force would no longer be the only variable. **Rule: the hand's
fingertip material is `FRUIT_FINGER_MU` (2.0) and the same
`FRUIT_FINGER_FRICTION_COMBINE` (unset = engine default = average).** Both already
travel in `physics.finger_contact` (`scene.py:626-648`), so the manifest can prove
it.

### 1.4 The drive: a force cap is not a torque cap

The pinch's `maxForce = 10 N` is a **prismatic** force cap on a joint whose
displacement is the gap. The Allegro's 16 joints are **revolute**; their drives
carry torque. Isaac Lab's own Allegro config sets `joint_effort_limit = 0.5` N.m
(`isaaclab_assets/…/allegro.py`, fetched 2026-11-03). Two consequences:

* the numbers are **not comparable**, and copying 10 into a torque field is a
  unit error that would deliver a wildly different contact force;
* **the delivered contact force is not the cap anyway** - P41's mechanism is the
  ratio `c/k` at the 120 Hz step (the asset's own `k=1e6, c=100` delivers 22 % of
  its cap; `c/k = 0.02` delivers 50 %). A revolute hand has 16 such ratios.

**So the hand's drive is tuned to a *measured* target, not to a number**: the
per-contact normal force at the close is read back (`tactile`/`[drive]` rows, the
P40 instrument) and the stiffness/damping pair is chosen so that a seated
fingertip reads **4.90 ± 0.25 N**, the pinch's own per-face value. That is M1's
manipulation check, and it is the one thing that makes M2's comparison a
contact-count test.

### 1.5 The candidate first-assets

| asset | Isaac USD | actuation | geometry | licence | what it is good for | what it is not |
|---|---|---|---|---|---|---|
| **Allegro 16-DoF** | **YES, verified 2026-11-03** (`WonikRobotics/AllegroHand/allegro.usd`, 1.63 MB, listed in the 6.0 bucket) | **16 direct motors** (no tendon) | 3 fingers + thumb, ~1.1 kg [R] | commercial; model BSD-2 | the **mount + topology** probe, M1/M2 | the purchase: wrong scale (its links are ~20 mm against a 61 mm pad) and not a 4-contact radial grasp |
| **4-pad surrogate** (authored) | n/a - built in `scene.py` | the **existing** pad drive (10 N, `c/k` 0.02) | **radial 4 x 90 deg**, the P104 `quad` | ours | **the licensed measurement**: M2's decisive cell, because it is the only form whose 1.87-2.05x is already measured | not a hand: it cannot approach, and it cannot do the 3+1 comparison |
| **LEAP 16-DoF** (converted) | **no** (MJCF MIT in Menagerie; CAD CC BY-NC-SA) | **tendon-coupled** (Dynamixel XC330) | 3 + 1 | code MIT, CAD NC | the **product** candidate | needs an MJCF→USD conversion whose tendon mapping is the schedule risk |
| **ORCA 17-DoF** (converted) | **no** (MJCF + URDF, `orca_sim`) | **tendon**, popping joints | 5 fingers | models MIT, hardware NOASSERTION [U] | the **product** candidate, tactile integrated | same conversion risk, plus a licence to resolve before a product decision |

**Recommendation: Allegro first, surrogate second, no conversion before M2
passes.** The reason is not "it is cheapest" - it is that the Allegro is the only
candidate whose **16 joints map 1:1 to 16 PhysX drives**, so M1 measures the
*mount, the contact and the grasp topology* with **zero** tendon modelling. LEAP
and ORCA are tendon-driven, and a tendon in MJCF is a constraint the Isaac
importer must translate; that is where a two-week schedule disappears, and it
would be spent **before** the question M2 asks.

### 1.6 What the simulator's hand is, in one sentence per stage

* **M1/M2: the Allegro USD**, mounted and welded, drives tuned to 4.90 N per
  contact, fingertip material 2.0, no palm collider. It answers *can a hand be
  mounted in this cell without breaking the station* and *what does a real 3+1
  topology read*.
* **M2's decisive cell: the 4-pad surrogate**, because the fixture's pass belongs
  to a radial quad and the surrogate is the only in-scene form that reproduces it.
* **M3/M4/M5: the Allegro - or the hand the surrogate licenses - if M2 passes on
  it.** The surrogate *licenses the purchase*; it cannot run the pipeline (it has
  no fingers to approach with, and no precision grasp).

### 1.7 The topology prediction (the plan's central risk, pre-registered here)

P104's `quad` is **4 pads at 90 deg around the payload**. Every candidate hand is
**anthropomorphic**: three fingers curl around one side and a thumb opposes. On a
60 mm sphere the three finger contacts' normals point roughly the same way (toward
the palm), so under an **axial** pull they behave as **one friction cluster plus
the thumb** - effective `n ≈ 2` in P104's own arithmetic (`F_crit = n · mu · N_c`),
i.e. **≈ 1.0x**, unless the fingertips **hook past the equator** (form closure).

**Prediction, written before the run**: the Allegro's sustained axial capacity on
the pear reads **1.2-1.6x** the pinch, i.e. **at or below** the bar, while the
radial surrogate reads **1.87-2.05x** as the fixture did. If that holds, then:

* the hand's win is **form closure (envelopment), not the contact count**, and the
  tree has already measured a form-closure aid as a **pipeline negative**:
  `FRUIT_FINGER_SCOOP`'s distal ledges **bat the payload** and take no-contact
  from 2 to 9 of 15 attempts (`logs/r8/A_RESULTS.md` §3). **A static win is not a
  pipeline win** - `logs/p104/RESULTS.md` §3 says the same thing about the lip;
* the decisive question moves from "how many contacts" to "**can a fingertip
  approach a 37-70 mm fruit and hook under its equator without striking it
  first**", which is an approach-geometry question, and therefore **M2 must
  include an approach-and-close cell**, not only a seated pull (§5.2).

This is the single largest risk in the stage and it is why M2 has two forms.

### 1.8 What the asset costs

| item | hours [E] | note |
|---|---|---|
| author the mount (remove 4 finger joints, weld 2 hand joints, re-derive the TCP → grasp-centre offset) | 8-12 | the offset is the analogue of `_pad_standoff`; it is a **measurement**, not a constant to copy |
| collision authoring + the drive tune to 4.90 N | 8-16 | the `_add_finger_colliders` route is proven; the drive tune iterates |
| build print + a `253`-style selfcheck leg pinning the 16 joint names, the mount, the DOF count (46) and the offset | 8-12 | the leg is what makes the asset reproducible |
| the M1 smoke script | 4 | one close on one fruit, one tactile read |
| **total M1** | **24-40** | 0 GPU; < 1 h simulator wall |

The conversion route, *if* it is taken later: **40-80 h** [E] plus the tendon risk;
it is explicitly **not** in M1-M2's budget.

---

## 2. The schema

### 2.1 v1, exactly - and what of it is dead

| item | value | source |
|---|---|---|
| proprio | **25-D** = 22 joint positions (all DOF, articulation order) + 1 finger opening (active arm's mean of two joints) + 2 tactile normal forces | `rl_env.proprio()`, `rl_env.py:3898-3991` |
| action | **9-D** = 7 arm joint targets + finger opening clipped `[0, 0.044]` + a recorded mirror of 7 | `rl_env.py:4945-4957` |
| goal | **8-D** `[pos(3), vel(3), diameter, bin_index]` | `rl_env.py` docstring; `moe_v13s` config |
| image | **5 channels x 2 frames** at 128x128: RGB + depth + instance mask, **one** camera | `policy/data.py:37, 275`; `scene.camera_sensor` |
| rate | one action per control tick; `execute_steps=4` → **4 ticks/action** (33 Hz); `_observe()` every 4 ticks | `rl_env.act`, `rl_env.py:4694-4727` |
| horizon | obs **2**, action **16** | `moe_v13s/policy_best.pt` config |
| recorded frames | every **4** ticks (30 Hz) | `scripts/40_collect_demos.py:680` |

**Measured: 4 of the 25 channels carry nothing.** Over 40 episodes of
`datasets/demos_v12`, the per-channel range of `joint_positions` is
**6.8e-4 / 8.7e-4 rad** at indices 16 and 19 (`openarm_{side}_hand`) and
**2.2e-7 / 9.4e-7 rad** at 20 and 21 (`openarm_{side}_ee_tcp_joint`); every arm
channel ranges 0.43-3.12 rad. So v1's effective information is **21-D**, and the
hand stage should not carry the four dead ones forward.

### 2.2 v2 proprio: 34-D, derived

```
[ 0:14]  openarm_{left,right}_joint1..7   interleaved, v1's own order and slots
[14:30]  the ACTIVE hand's 16 joints      the Allegro actuation order
[30:34]  four fingertip normal forces     index / middle / ring / thumb
```

**25 → 34 = +9**, and the arithmetic is worth printing because the survey's "~40"
is not this number:

| block | v1 | v2 | why |
|---|---|---|---|
| arm joints | 14 | 14 | unchanged, same slots, so the arm half of the normaliser is reusable |
| finger joints (2/arm) | 4 | **0** | the hand replaces them |
| `hand` + `ee_tcp` joints (2/arm) | 4 | **0** | dead (< 1 mrad) and, after the weld, not joints at all |
| finger opening scalar | 1 | **0** | the hand's joints *are* the opening |
| hand joints | 0 | **16** | the active hand only |
| tactile | 2 | **4** | one per fingertip |
| **total** | **25** | **34** | |

**Why the active hand only (34, not 50 or 56).** The inactive arm's 7 proprio
channels were measured to contribute **nothing** (P36's 2x2: park image 0/58 vs
35/57 carried, `p = 8.8e-15`; park-proprio 17/60 vs 18/55, `p = 0.687`,
`logs/p36/A_RESULTS.md:82-85`). Carrying the inactive hand's 16 joints would be the same
untested bet at 16x the width. **The inactive hand gets nothing**, and that is a
documented decision with a measurement behind it, not an omission.

### 2.3 Vision: two encoders, not ten channels

The hand **occludes the head camera at the grasp** (survey §1.1: a 16-DoF hand
plus a ~1 kg wrist between a 240x424 mast camera and the fruit). So v2 needs a
**wrist view** - and the tree reads exactly **one** camera today
(`scene.camera_sensor`; `policy/data.py:519-533` stacks RGB + depth + mask per
frame from it).

**Design: two separate visual encoders, summed into the same conditioning
vector** - not 10 stacked channels into one encoder. The head camera's global
context and the wrist's local patch are different statistics, and stacking them
into one first conv means the encoder cannot specialise. Concretely:

* head: 5 channels x 2 frames = **10** input channels (unchanged);
* wrist: 3 channels (RGB + depth; no mask - the mask exists to isolate the
  selected fruit in a wide view and is not needed at 60 mm) x 2 frames = **6**;
* `cond = goal + proprio + vis_head + vis_wrist + time`.

This is a **new render product** on the sim side and a **new encoder pass** on the
model side; both are priced in §3.5.

### 2.4 The action: 9-D chunk + 8-D hand latent, and nothing diffused beyond 9

```
sample (9-D, diffused, horizon 16)          -> arm joints 1..7 + synergy
condition (goal, proprio, vis, time)
  ├── head A: Conv1d(prev, 9)   -> the denoised arm chunk      (the shipped head)
  └── head B: Conv1d(prev, 8)   -> the hand latent chunk       (regressed, not diffused)
                                     └── decoder 8 -> 16 joints (supervised, tanh-clamped)
```

**The finger channel becomes the hand's synergy scalar.** That is the single most
important simplification in the schema: `action[7]` already is "the gripper's
opening" and the whole tree - the scripted primitive, the collector, the 9-D
store, the `_action9` packer (`tasks.py:7191-7212`), the hybrid evaluator's
`early_close` test (`rl_env.py:5618`) - reads it that way. A **synergy** is a fixed
map `q_hand = q_open + s * (q_closed - q_open)` with `s = 1 - action[7]/0.044`, so
**the hand closes when the pinch would close**, and M3 can run the whole scripted
pipeline unchanged. The 16-D precision comes from the **latent**, which refines
the synergy per finger at the grasp.

**Why the latent is not diffused** - the measured argument, not a preference:

* P52 measured the arm chunks to be **noise** (within-chunk min p50 2.44 rad/s,
  0/60 below 0.30 rad/s, `|2nd|/|1st|` 1.16). Diffusing 16 more dimensions with
  that emission quality is 16 more chances to damage a hand on the first real run.
* P53 measured **10.9-11.0 %** of joint steps **out of range** with **no clamp**;
  the clamp is **free** (0 of 70 938) and gains nothing on the class. For a hand,
  a post-hoc clamp is not a null - it is a **hardware event**. A `tanh`-scaled
  decoder is in-range **by construction**, which the diffused path cannot be.
* The hand's useful window is short: `close` **1.36 s** + `release` **1.70 s** =
  **3.06 s = 20 %** of the 15.34 s attempt (`logs/p91/AUDIT.md` §2). A 16-D
  diffusion over a 20 % window is a poor use of the sample budget the tree does
  not have (no hand demonstrations exist yet).

**The latent is masked, structurally**: outside `grip | close | release` the hand
head's output is forced to the **open** synergy (a mask on the phase token, not a
learned preference). The hand's job in `descent`/`hover` is to be open and out of
the camera, and the survey's rule 2 says exactly this.

### 2.5 The rate

| stream | v1 | v2 | why |
|---|---|---|---|
| policy decision | 4 ticks (33 Hz) | **4 ticks** for the first cell | keeps the loop off the latency bound (§3.5) |
| the 8-tick alternative | - | `action_hold=2` = **8 ticks (15 Hz)** | P53's measured cell: **-7.1 % wall**, decisions 61 → 29, **right arm 26/26**; its cost is a thinner RTC margin, not a new failure (§3.5) |
| hand command | - | at the **decision** rate | the decoder is one MLP; the hand holds its target between decisions |
| hand's *fast* ramp | - | a **fixed synergy ramp** (24 ticks) in the executor, not a policy output | the close is a template; the tree's own pattern is `_close_step`'s ramp, and the policy should not be asked to learn a 0.2 s ramp |
| tactile | 120 Hz scalar (1 per face) | **30 Hz**, 4 channels | a real pad is 25-60 Hz; P102 measured 5-28 frames of the slide at 30 Hz |

### 2.6 The store change

`datasets/demos_v12`'s npz keys are `joint_positions`, `finger_opening`, `goal`,
`tactile`, `action`, `image_rgb`, `image_distance_to_image_plane`,
`target_mask`, `fruit_position` (`tasks._record`, `tasks.py:7224-7269`).

**v2 adds four, keeps the rest, and renames none:**

| key | shape | note |
|---|---|---|
| `hand_joints` | (F, 16) | the active hand's measured joints - **required** |
| `tactile_hand` | (F, 4) | per-fingertip normal force |
| `wrist_image_rgb` | (F, H, W, 3) | the second view |
| `wrist_image_distance_to_image_plane` | (F, H, W) | depth only; no mask |

`joint_positions` stays **22-wide** in the store (the *recorded* row), and the
**loader** assembles the 34-D v2 vector from `joint_positions[:, 0:14]` +
`hand_joints` + `tactile_hand`. That keeps the recorded array honest (it is what
the arm actually had) while the model's input is an assembly, which is the pattern
`EpisodeStore.proprio` already uses (`policy/data.py:476-497`).

**The index row** (`dataset._append_index`, `dataset.py:171-184`) gains
`obs_version` and `hand_dofs`; `frames`, `station_y`, `success`, `notes` are
unchanged, so `106_index_audit.py` keeps working.

### 2.7 Old stores are provably old - the four precedents, applied

This repo has added a dimension to a store **four times** and each time the rule
was the same: **a new observation dimension gets its own manifest key, and a store
without the key is not silently reinterpreted.**

| precedent | key | rule |
|---|---|---|
| P28-B belt speed (25 → 26) | `supply.belt_speed` | the loader resolves the pin **per episode**; an unpinned store with no declared value **raises** (`policy/data.py:346-356`) |
| P41 finger drive | `physics` | the block names the drive, the substeps and the read-back |
| P72/P87/P93/P96 | `scene`, `physics.release/place/lift/takeoff/park`, `supply.band` | a manifest **without** the key **predates** the phase |
| P96/P97 pre-pose | `collection.prepose_clear` | three keys, one per quantity that can differ |

**v2's key, and it is the only one that can be exact:**

```json
"observation": {
  "version": 2,
  "proprio": {"dim": 34, "hand": "allegro", "hand_dofs": 16,
              "layout": "arms14,active_hand16,tactile4"},
  "cameras": ["head", "wrist"],
  "action": {"dim": 9, "hand_latent": 8, "synergy": "open_to_closed"},
  "record_hz": 30
}
```

**The rule**: `observation.version` absent → **v1 (25-D), read as v1**; present and
`!= 2` → **raise**; `== 2` and the hand name disagrees with the checkpoint's →
**raise**. There is no "legacy declaration" escape hatch, because unlike the belt
speed a hand store and a pinch store are **not** convertible into each other - the
last 16 channels have no v1 counterpart. That is stronger than P28-B and it is
justified by the asymmetry.

### 2.8 The file list for the schema

| file | change |
|---|---|
| `src/fruit_sorting/hand.py` | **new**: the mount spec, the synergy, the latent decoder interface, the joint limits |
| `src/fruit_sorting/rl_env.py` | `proprio()` → 34-D (keeps the `FRUIT_OBS_SPEED` 26-D path behind its own flag); `act()` splits arm/latent; the second camera |
| `src/fruit_sorting/policy/data.py` | `PROPRIO_DIM = 34`, the version check, the `hand_joints` assembly |
| `src/fruit_sorting/dataset.py` | the four new arrays, the two index fields |
| `src/fruit_sorting/assets.py` | `hand_provenance()` beside `scene_provenance` |
| `scripts/40_collect_demos.py` | the `hand` block; `--keep-failures` (§4.2) |
| `configs/hand_allegro.json` | **new**: the mount pose, the joint-name order, the synergy endpoints, the fingertip bodies |
| `scripts/257_p105_hand_selftest.py` | **new**: pins the order, the counts, the clamp, the manifest keys |

---

## 3. The architecture

### 3.1 The three candidates, scored on this repo's own measurements

| | (a) arm chunk + hand latent | (b) two-stage, hand policy at the close | (c) single high-DoF diffusion |
|---|---|---|---|
| diffused dim | **9** (unchanged) | 9 (stage 1 unchanged) | **15-25** |
| new failure surface | a bad latent → a bad hand pose | a bad stage 2 → **today's behaviour** (safe) | a bad hand joint → hardware |
| can act during `lift`/`place` | **yes** (the latent is per chunk, the hand holds) | **no** - the hand is set at the close | yes |
| cost | 1 head + 1 decoder + 1 supervised loss | 1 small model + 1 phase boundary | a bigger denoiser + a structural clamp + a safety envelope |
| the measured objection | none of P52/P53 binds | **P42**: the seat is already centred (1.4-4.6 mm) and the walk is 104-276 mm - stage 2 fixes the term that is 30-60x too small. **P75**: 4 of 6 escapes fire *inside* the place leg, which (b) cannot reach | P52: chunks are noise; P53: 10.9 % out of range with a null clamp |

**Pick (a).** (b) is predicted to fail on a measurement the tree already has
(`logs/p42/SEAT_CENSUS.md`, `logs/p75/RESULTS.md`), so it is the *safety net*, not
the design. (c) is the right architecture for in-hand manipulation later and the
wrong first one: it multiplies the diffused dimension by 2-3 with the emission
quality P52/P53 measured, before a single hand demonstration exists.

### 3.2 The model, exactly

| tensor | v1 | v2 |
|---|---|---|
| `action_dim` (in/out of the UNet, the diffused sample) | 9 | **9** (unchanged) |
| `proprio_dim` | 25 | **34** |
| `image_channels` (head) | 5 | 5 |
| second encoder | - | **6 channels x 2 frames**, `out_dim = 128`, summed |
| `goal_dim` | 8 | 8 |
| hand head | - | `Conv1d(prev, 8)` on the same trunk, per waypoint |
| hand decoder | - | `Linear(8, 64) -> SiLU -> Linear(64, 16) -> tanh`, scaled to each joint's limits |
| params | **4 594 926** [M, `moe_v13s`] | +**~0.27 M** [D]: the wrist encoder ~0.26 M (5 convs at 6→32→64→128→128, plus the 128→128 projection) and the head + decoder **~8 k** |

`ConditionalUNet1D` already takes `action_dim`/`proprio_dim`/`image_channels` as
constructor arguments (`policy/model.py:111-132`), so **the trunk is unchanged** -
two added modules and one extra conditioning term. The 0.27 M is a **0.6 %** weight
change, which is why the fine-tune is cheap and why the arm half cannot be
corrupted by capacity.

### 3.3 The loss

```
L = L_diffusion(arm chunk, 9-D)                      # the shipped objective
  + 0.1 * L_router  + 0.01 * L_balance               # the shipped router terms
  + λ_h * || decoder(z_hat) - q_hand ||^2            # the hand, supervised
  + λ_c * relu(|decoder(z_hat)| - q_limit)^2         # zero by construction
```

`λ_h = 1.0`, and the latent target `z*` is produced **once, offline** by the
encoder half of the autoencoder trained on the recorded hand joints, then frozen.
That is what makes the latent a *function of the data* rather than a second thing
that can drift. Acceptance for the latent: **reconstruction error p95 <= 0.05 rad**
on the collected hand joints; if it misses, widen 8 → 12 (and re-check the
latency, §3.5).

### 3.4 Training recipe: fine-tune, not scratch - with one exception

**Fine-tune from `moe_v13s` (`61da390a`)**, because the arm half is exactly the
problem that checkpoint already solves and the new head is additive. The recipe is
the measured one (`logs/w3/50_finetune_v13s_dense.log`): **6 epochs, lr 5e-5,
batch 32, `weight_mode=ones`, base = the previous demo store**, ~201 s/epoch on
this machine.

**But the store must be loaded with `only_successful=False` and the fine-tune run
with the failure weight on.** That is the one departure from the W3 recipe, and it
is forced: the hand's whole purpose is the class a successes-only store does not
contain, and P33 phase 3 measured what that costs (52 carried-not-placed + 56
no-grasp attempts discarded, "no example of the class the deficit is in").

**Scratch is not indicated**: it costs 4-6x the GPU and would discard the 5-expert
router, whose phase labels are what mask the hand (§2.4).

### 3.5 The inference budget

Measured: **71 ms per decision** = model 47.4 + render 20.0 + camera 3.6
(`logs/p43/P2_RESULTS.md:264`, `logs/p43/RATE_LEDGER.md:330`, restated in
`logs/p52/FRONTIER.md:516`); the latency bound is **h <= 7** waypoints at the
shipped one-waypoint-per-tick replay.

| addition | cost | verdict |
|---|---|---|
| the hand head + decoder (8-D, one MLP) | **< 0.5 ms** [E] - the UNet cost is dominated by the visual encoder | negligible |
| the **wrist encoder** pass | **+3-8 ms** [E] - a second `VisualEncoder` at 128x128 whose first conv is 6 channels | small |
| the wrist **render** | one more `RenderingManager.render()` per decision; P43 measured the head's at **20.0 ms** | **+20 ms** [E] |
| total | **71 → ~95 ms/decision** | **+34 % of the decision, which is only +3-4 % of the episode wall** |

**Read the two denominators, because they differ by an order of magnitude.** A
decision is **71 ms** and it is **10.6 %** of the episode wall
(`logs/p43/P2_RESULTS.md:264`: model 47.4 = 10.6 %, render+camera 23.6 = the
rest of the 10.7 % pause). So the wrist view's +24 ms is **+34 % of a decision**
and **+3.6 % of an episode** - it is affordable, and the thing that is *not*
affordable is a second *frame rate* (reading it every tick instead of every 4).

**What it does cost is the latency margin, and that is a real number**: the
measured bound is **h <= 7** frozen waypoints of a 16-waypoint chunk at 71 ms
(P52 §4.2). At 95 ms it becomes **h <= 11 of 16** - still inside the chunk, so
the shipped **RTC** path (`policy/runtime.py`) still hides it, with 5 waypoints of
margin instead of 9. **No correctness change; a wall cost and a thinner margin.**

**Consequence, stated plainly**: the hand stage runs the **RTC (async) path**,
and if the wrist render cannot be afforded the fallback is the survey's §5.5
item: (a) cannot see the hand → architecture (b) with the in-hand camera only.

### 3.6 The training/eval cost

| item | cost | source |
|---|---|---|
| the fine-tune | **6 x 201 s = 20 min** at 38 990 windows | `logs/w3/50_finetune_v13s_dense.log:9-14` |
| with the wrist view + a ~40 k-window store | **30-40 min** [E] | the visual encoder is ~half the epoch |
| the latent autoencoder | **< 5 min** [E] | 16-D in, 8-D out |
| one 15-episode direct eval | 15 x ~60 decisions x 95 ms = **~1.5 min** of model + the sim wall (P58: ~35 s/pick) | `logs/p58` |

---

## 4. The data plan

### 4.1 Every store is invalid, and the arithmetic

| store | what it is | why the hand invalidates it |
|---|---|---|
| `datasets/demos_v12` | 158 episodes, 32 298 frames, 29 612 windows, 7.5 GB [M] | no hand, no wrist view, 25-D |
| `datasets/p33_pear` | 180 episodes, 32 670 windows [M] | same, and **successes-only** |
| `datasets/rl_rollouts/*` | direct rollouts (P37 `p37_park`: 90 episodes) | same, but these **keep failures** - the only usable *shape* |

The training store for the hand is therefore **new data, not a re-labelled store**.
`moe_v13s` remains valid as the **base** (the arm half is unchanged) and as the
**control arm** of every A/B.

### 4.2 The collector cannot produce it - a measured defect

`EpisodeRecorder.save` (`dataset.py:147-152`):

```python
if not success:
    # Failed attempts would otherwise overwrite the previous attempt's
    # file, since the index is the success count.
    state.meta = None; state.frames = []
    return None
```

**Every failed attempt is discarded.** A hand store collected through
`scripts/40_collect_demos.py` therefore contains **zero** `cnp` examples, and
`cnp` is **75-77 %** of this cell's failures (9 of 12 in `logs/p92/CENSUS.md`'s
two-seed population, 17 of 22 in `logs/p93`'s four-seed one). This
is exactly the limitation P33 phase 3 recorded about `p33_pear` ("52
carried-not-placed + 56 no-grasp attempts discarded - no example of the class the
deficit is in", AGENTS §2 P33).

**Two routes, and the plan takes the second first:**

1. add `--keep-failures` to the collector (index rows gain `success=false`; the
   merge and `106` already tolerate it, because the direct-rollout path already
   writes failures) - **8 h** [E], and it changes a shipped script, so it owes
   `107_collect_merge_test.py` + `106_index_audit.py`;
2. use the **direct-rollout path** (`scripts/110_rl_rollout.py --record`, which
   already writes failed episodes and already carries the `physics`/`scene`/
   `supply.band` blocks) for the hand's first store - **0 h**, and it is the path
   P35-P43 measured.

**But note the interface**: the direct path presents one fruit per episode and has
no two-line scheduler. The hand's *adoption* cell is the two-line (P85's default),
so M5 needs route 1 eventually. Plan: **route 2 for M4's first checkpoint, route 1
before M5.**

### 4.3 The size, and the wall

The measured anchor: **158 episodes in 2 h 6 min, one shard, no wedge**
(`logs/w3/HANDOFF.md:10-11`), 204 frames/episode mean, 7.5 GB.

| change | effect | estimate |
|---|---|---|
| the wrist camera | +1 render + 1 read per recorded frame | **+15-25 % wall**, i.e. **2.5-3 h** [E] - 32 298 frames x (render ~20 ms + read ~4 ms) ≈ 13 min of pure camera, plus the readback and the write |
| the store size | two views instead of one | **~15 GB** [E] - and the machine's budget is the constraint AGENTS §2 already names ("the v12+v10 stores exceed this 125 GB machine") |
| the hand's own failures | a heavier hand fails differently | the episode count must cover a **new** class, so **>= 150 episodes** is the floor, not the target |

**Recommendation: 150-200 episodes at 30 Hz, one or two shards.** Not more: the
W3 anchor is 158 for a store that fine-tuned to a working checkpoint, and the
hand adds one failure mode, not a new task.

### 4.4 The success criterion for a *usable* store

A store is usable only if it contains the class the hand is for. Registered here
because "we collected 158 episodes" says nothing:

| clause | bar | why |
|---|---|---|
| **loaded-slide legs** (`force_min == 0.00 N` with `contacts@onset >= 1`) | **>= 15 % of carry legs**, and **>= 20 legs absolute** | the shipped two-line reads 4-11 of ~40 (10-27 %, `logs/p87/RESULTS.md`); a store below this cannot train the class |
| **`cnp` attempts** | **>= 15 %** of episodes | 17/80 = 21 % is the shipped rate; a store that is mostly placements is a successes store in disguise |
| **never-held attempts** | present, **>= 5** | the acquisition class must be in the data even though the hand cannot fix it, or the loss learns to ignore it |
| **landing** | every recorded release `on_belt` | P86/P87's guard; a store with off-belt landings is a broken scenario |
| **hand joints** | p95 reconstruction **<= 0.05 rad** through the 8-D latent | §3.3 |

**And the class mix must be reported per arm.** The left arm is 47x the right's
escape rate on this interface (`logs/p60/P3_RESULTS.md:179`) and `rl_env.py:2516` sets
arm = grade, so a store that is 90 % right-arm episodes has no left data.

### 4.5 Provenance

The hand writes **one new block** and extends two:

```json
"hand": {
  "asset": "allegro", "usd": "…/WonikRobotics/AllegroHand/allegro.usd",
  "usd_md5": "…", "dof": 16, "joint_order": ["index_joint_0", "…"],
  "mount": {"joint": "openarm_{side}_hand", "type": "fixed",
            "grasp_centre_m": 0.0, "distal_plane_m": 0.0},
  "drive": {"k": 0.0, "c": 0.0, "max_force": 0.0, "readback_matches": true},
  "contact": {"mu": 2.0, "combine": null, "damping": 60, "compliance": 0.0},
  "synergy": {"open": [], "closed": [], "source": "scripted M3"},
  "latent": {"dim": 8, "recon_p95_rad": 0.0}
}
```

`mount.grasp_centre_m` and `distal_plane_m` are the `_pad_standoff` /
`FINGER_TIP_BELOW_JAW` analogues and are **required**, because they are the two
numbers every scripted aim reads. `contact.combine: null` means "the engine
default", which P104 measured to be the **average** - a store must not be read as
if it were minimum.

**Also inherited unchanged**: `physics` (the finger drive), `scene` (the collider
set - and a hand **is** a collider-set change, P71's precedent), `supply.band`
(P93). A hand store's `scene` block is the one that will move most, so the M1 build
must populate it **before** the first collection, not after.

### 4.6 Fine-tune vs scratch, priced

| | fine-tune from `moe_v13s` | scratch |
|---|---|---|
| GPU | **30-40 min** [E] | 3-5 h [E] |
| the arm half | inherited (the tree's own solved 9-D problem) | relearned from a new store |
| the router | inherited (its phase labels mask the hand) | relearned, and 5 experts on 150 episodes will collapse |
| risk | a new head on a frozen trunk can under-fit | the store is too small for scratch - 158 episodes is what *fine-tuned* a working checkpoint, not what trained one |

**Fine-tune. Scratch is not indicated and the store size is the reason.**

---

## 5. The milestones and the kills

### 5.0 The baseline, and the ceiling the hand can even reach

**Baseline** (P93's four control seeds, 20 attempts each, `logs/p93/RESULTS.md`):

| metric | value |
|---|---|
| placed | **58/80 = 72.5 %** |
| failures | **22** = `cnp` **17** (77 %) + never-held **5** (23 %) |
| interval | 10.59 / 11.08 / 12.16 / 11.53 s |
| wall rate | 2.37-2.91 placed/min |
| acceptance | **8/10, 9.0 s/attempt**, `fingerprint: matches` (P98) |

*The counts are read off `logs/p93/RESULTS.md:147-157` (control arm), and they
close: 58 + 17 + 5 = 80. `docs/PLATFORM_SURVEY.md` §5.0 lists "25 failures:
`cnp` 17 (68 %), never-held 5, other 3" - that is three failures too many and the
68 % follows from the wrong denominator (`17/25`; it is `17/22 = 77 %`). Nothing
in the survey's conclusion changes; the ceiling arithmetic below is corrected.*

**What each failure class is reachable by** (P102's attempt join, 40 attempts,
`logs/p102/RESULTS.md` §0/§4):

* **`cnp` / seated loaded slide - reachable by a contact-count change.** On
  P102's 40 attempts there are **7 `cnp`**, of which **6 carry a seated escape**
  (86 %) and 1 is a never-seated leg (a failed catch that closed on air); 0 of 29
  placed attempts carried a seated escape; every attempt's outcome is joined to
  its own carry legs, so the attribution is exact. That is also **6 of the 11
  failures** - the 55 % figure the survey quotes is the share of *all* failures,
  not of the `cnp` class.
* **never-held - acquisition, not contact.** All 4 no-grasp attempts carried a
  never-held leg; the discriminator is the `dynamic catch-up: residual` above its
  6 mm tolerance, **8/8 no-grasp vs 3.6 % below it** (`logs/p47/ACQ_CENSUS.md`),
  and the failing values are **220-481 mm** - a **hand-over timing** failure, two
  orders of magnitude outside any pad geometry's reach (`logs/p48`). **No contact
  count touches this class, and a heavier hand makes it harder.**

**The ceiling arithmetic** (all on P93's 80):

| scenario | placed | % | residual failures |
|---|---|---|---|
| today | 58 | 72.5 % | 22 |
| **+8 `cnp`** (what the P4 bar of 82.5 % actually requires) | 66 | **82.5 %** | 14 |
| **+15 `cnp`** (the measured seated-slide share, 86 %) | 73 | **91.3 %** | 7 |
| **every `cnp` converts** | **75** | **93.8 %** | 5 (never-held) |
| every failure converts | 80 | 100 % | 0 - impossible, 5 are acquisition |

**Two consequences the milestones must carry:**

1. **The survey's P4 bar (placed >= 82.5 %) is 8 of the 17 conversions - 47 % of
   the class - not a near-ceiling number.** It is reachable in principle and it is
   still the wrong *primary*, because a placed count cannot separate "the hand
   worked" from "this seed drew fewer failures": the class is 17 of 80 and **one
   binomial sd on 80 attempts at 72.5 % is 5.0 points** (sqrt(0.725·0.275/80)),
   i.e. **half the 10-point bar**.
   **M5's primary is therefore the `cnp` rate (17/80 → <= 8/80) with placed as a
   non-inferiority clause** - the same threshold, measured on the class that can
   actually move.
2. **Quote 93.8 % as the arithmetic ceiling and 91.3 % as the measured-share
   ceiling in every hand result**, or a 78 % will read as a failure when it is
   the reachable maximum at a worse branch.

### 5.1 M1 - the asset in scene

**Build**: the Allegro USD mounted on `openarm_{side}_hand` (welded), the 4 finger
joints removed, the grasp-centre offset measured, the fingertip colliders
authored, the drives tuned to **4.90 N per contact**, the joint-name/DOF/offset
selfcheck leg, one smoke.

**Gate (all must hold):**
* the hand closes on a **pear and a strawberry** and lifts them **>= 50 mm**, read
  by the shipped grasp test (`fruit_z - z_before > 4 mm`, the primitive's own
  criterion, not a force read);
* the per-fingertip normal force reads **4.90 ± 0.25 N** on a seated contact;
* the **tactile channels read**: 4 channels, non-zero on contact, zero in free
  space (the P102 patch instrument already exists to check the projection);
* the build print names the asset, the joint order and the read-back, and the
  selfcheck leg passes;
* **the shipped station is still reachable**: the pick pose at x 0.20-0.36,
  y ±0.10 solves with the hand's TCP inside the R10-A clean-grip band, and the
  P96 pre-pose map (`logs/p96/prepose_map.py`) admits a clearance pose for the
  hand's envelope - a hand is **wider** than the 98 mm jaw, and P96's band
  `[0.155, 0.25]` above the belt top was solved for pads.

**Kill**: the station does not admit the hand's envelope (no pre-pose cell clears
the fruit band with `margin >= 0.05 rad`), or the hand cannot be welded without
losing the TCP frame the whole stack commands, or the DOF count/order cannot be
pinned by a leg. **Any of those is a station/asset redesign, not a tuning loop** -
stop and re-plan the mount.

**Cost**: 24-40 h [E]; < 1 h simulator; 0 GPU.

**Measured (P106, `logs/p106/`).** The **mount passes structurally and the
close+lift gate fails as a rate (1 of 4 cells)**, and the two numbers the plan
owed are in: the asset is **2.135 kg** over 21 bodies (not ~1.1 kg), and the tool
offset that replaces `_pad_standoff`'s 70 mm is **170.7 mm along the tool axis**
(100-216 mm across the posture sweep). The DOF count after the mount is
**38 = 22 + 16**, the hand's half pinned by name/order/limits, and the merged
articulation is proved in one command (`+0.300` -> `+0.2894`, radians). Two
defects are recorded because they cost the phase: the asset's `root_joint` is a
**world** anchor that survives `RemovePrim` through a reference (it destroyed the
articulation - arm joint 1 read -82.19 rad), and `ArmController.move_to` stalls
186-326 mm short from the hanging pose, so the probe teleports to `ready` instead.
The gate's failure is not a force shortfall: the fingers **knock the payload out
of the seat as they close**, and the one pear that did hold (lift **+59.7 mm**)
had already crept **39.75 mm** under 0.82 N - 12x the pinch and 40x the 1.0 mm
bar. The drive tune the plan asks for is **not achievable through a torque cap**:
at the asset's k=1e7 the pear reads **no contact at 0.46 N.m and 10.5 N per
contact at 0.48** - a step function, which is §1.4's warning measured.

### 5.2 M2 - the in-scene pull test (P104 transferred to the mounted hand)

**Two cells, and both are required:**

* **M2a, the seated pull** - the P104 protocol in-scene: the arm holds the hand at
  the pick pose, the hand closes on a pinned payload, a **5 N/s axial ramp** to
  40 N, `clean_slip > 2 mm` and sustained break recorded; 3 fruits x 3 repeats;
  **creep at the operating load** (0.75 s settle under the payload's own weight)
  is the second endpoint.
* **M2b, the approach-and-close** - the cell P104 could not run and R8-A says is
  decisive: the hand **approaches** the fruit from above at the scripted descent's
  speed and closes; the endpoints are the **no-contact rate** and the
  **displacement at first contact** (R8-A's ledges measured 2 → 9 of 15
  no-contact; a hand that bats the fruit is a pipeline negative no matter what it
  can hold).

**Gate:**
* **axial sustained break >= 1.5x the pinch on every fruit**, *or* - if only the
  surrogate passes - the **surrogate** is what licenses the purchase and the
  Allegro's number is recorded as the 3+1 topology's own;
* **creep <= 1.0 mm** at the operating load (the pinch's is 3.20-3.84 mm; 1.0 mm
  is a 3.2x win and the number the class actually lives on);
* **M2b: no-contact <= 1 of 15** and the first-contact displacement recorded.

**Kill**: the mounted hand reads **< 1.5x** *and* the surrogate does too → the
geometry does not survive contact + mount; **stop, buy no hand**, and the next
spend is `SIM_LIMIT`'s pad-face sanction (a custom pad), not a hand. If the
surrogate passes and the Allegro does not, the kill **does not fire** - it says
the topology was wrong, which is §1.7's prediction and a *design input* for which
hand to buy.

**Cost**: 16-24 h (M2a) + 8-16 h (M2b) [E]; ~4 h simulator wall; ~4 GPU-hours.

**Measured (P106, `logs/p106/RESULTS.md`).** One batch, the controls re-run from
P104's fixture unchanged: the **4-pad radial surrogate passes on both legs on
every fruit** - sustained **21.81 / 26.59 / 25.97 N = 1.98 / 1.87 / 2.05x**, the
2 mm criterion **1.82 / 1.80 / 2.10x**, creep **0.25 / 0.15 / 0.11 mm** against
the pinch's **3.20 / 0.85 / 2.68**, pry 0.30-0.75 mm - so **M2a's kill does not
fire**. The **Allegro is not evaluable**: its cell cannot be brought to the
pinch's 4.90 N per contact (the cap is a step function; a softer drive gives
2-6 N but no trustworthy force instrument on this asset), one of four draws held
(lift +59.7 mm, 2 mm at **13.20 N = 1.24x**, bounded >40 N sustained) and three
dropped the payload at the first release. The predicted **1.2-1.6x** is therefore
**neither confirmed nor refuted**; what is measured is its mechanism - the
fingertips span **116-123 mm**, so **at most 3 of the 4 can touch one 37-66 mm
payload at any posture in a 4x4 sweep** (2 for the pear at most postures, 2 for
the strawberry). The licensing sentence is the plan's own: *if only the surrogate
passes, the surrogate licenses the purchase and the Allegro's number is recorded
as the 3+1 topology's own* - i.e. the form to buy is radial/enveloping, not
anthropomorphic, and the purchase stays the owner's (M3 is untouched).

### 5.3 M3 - the scripted hand pick-and-place

**The tree's rule is that a scripted primitive comes before any policy**, and
this stage is where the hand's cost is: a hand changes **the aim, the close, the
carry and the release**, and each of those has a measured analogue.

| what | v1 site | v2 |
|---|---|---|
| grasp centre | `_pad_standoff` **0.070 m** (`tasks.py:9404`) | `hand_grasp_centre` (measured) |
| distal plane | `FINGER_TIP_BELOW_JAW` **0.0805** (`tasks.py:79`) | the fingertip body's distal plane (reporting) |
| close | the prismatic ramp + the 60-tick validation probe | the **synergy** ramp + the same probe |
| pre-pose | `_prepare_two_line_stations`, band `[0.155, 0.25]` (P96) | re-solved for the hand's envelope |
| release | the 112-tick trimmed block (P87) | the hand **opens**: its own ramp, re-measured |
| carry diag | `force_min`, `sep_max`, `contacts@onset` | per-finger equivalents, same fields |

**Gate:**
* the scripted hand's acceptance on the **same scenario** is **not worse than the
  shipped 8/10** - and because a hand moves the collider set, the comparison is
  **budgets + rate**, never a fingerprint (P71's rule);
* the **pre-leg pad/finger census** (P95/P96's instrument) reads **0 contacts and
  0 rows within 6 mm** - the invariant P96 bought;
* **landing 100 %** `on_belt` (P86/P87's guard).

**Kill**: the scripted hand cannot match 8/10 at any tuning, or the clearance
census shows the hand in the fruit band (`>= 1` contact in 40 attempts by the P95
definition) → **the hand cannot run this cell**; the station is too tight, and the
answer is a workstation change (a new station, a longer reach), not a policy.

**Cost**: **80-120 h** [E] - the largest item of the five, because it touches the
aim, the pre-pose, the close, the carry and the release. ~10 h simulator; ~10 GPU.

### 5.4 M4 - the policy on the hand

**Build**: the 34-D observation, the wrist camera, the 9-D + latent action, the
recollection (§4), the fine-tune, the A/B against `moe_v13s` on the **same hand**.

**Gate** (the tree's WS-4.2 protocol: N = 5 runs x 15 episodes per arm,
interleaved, one claim):
* **the hand-specific increment**: the hand policy beats the **hand with a
  scripted close** by **>= +8 points** placed, or the policy is not adding
  anything to M3's primitive;
* **no new failure reason**;
* **cycle <= +5 %** on the fired-only set.

**Kill**: the hand policy is not better than the scripted hand → **ship the
scripted hand** (this tree has done exactly that: the two-line default is a
scripted primitive). The policy is a later stage on a cell that works.

**Cost**: 24-40 h labour [E]; 2.5-3 h collection + ~6 h of A/B wall; < 2 GPU-hours.

### 5.5 M5 - the adoption gate

**The shipped cell's own bar**, which after P85 is the **two-line scheduler**:

| clause | bar |
|---|---|
| **placed** | **>= 58/80 (non-inferiority)** on 4 seeds x 20 attempts, 2 fresh (P93's rule) |
| **the closed class** | `cnp` **<= 8/80** (a 47 % conversion of the 17 - the same threshold the P4 bar implies) |
| **both denominators + the wall** | interval, window and batch placed/min, `placed/min wall`; **reported, not gated**, because P88/P89/the union/the fail-fast each moved the block exactly and the interval not at all |
| **landing** | 100 % `on_belt` on payload-present releases |
| **the three references** | all re-recorded from same-batch runs |

**And the references, explicitly**: `configs/motion_reference.json` and
`configs/motion_reference_twoline.json` are both **`30fb99f8`** today and
`configs/motion_reference_single.json` is **`8952c320`** (verified by md5 this
phase). A hand **is** a collider-set change, so by P71's precedent **all three
move** - and a moved reference is not a failure, but an **unmoved** one after a
hand mounts is evidence the hand was not in the scene.

**Kill**: `cnp` > 8/80 at 4 seeds, or placed below 58/80, or the references cannot
be re-recorded within one re-baseline window (i.e. the acceptance moves every
time). Any of those → **do not ship**; the measured residue goes into
`docs/LEFT_ARM.md`'s register and the next spend is the pad-face sanction.

**Cost**: 16-24 h labour [E]; 4 seeds x 20 attempts at **16.3 s/attempt wall**
(P87's `T5`: 325 s for 20) ≈ 25 min per arm, plus the single-path and `accept.sh`;
**~2 h simulator, ~1 GPU-hour**.

### 5.6 The five in one table

| | what it decides | gate | kill | labour [E] | sim [E] | GPU [E] |
|---|---|---|---|---|---|---|
| **M1** | can a hand be mounted in this cell | close+lift, 4.90 N/contact, tactile reads, **station still reachable** | the station or the TCP frame breaks | 24-40 h | 1 h | 0 |
| **M1 measured (P106)** | mount **PASS** (38 DOF, 2.135 kg, tool offset 170.7 mm), close+lift **1 of 4** | - | not fired: the mount is sound, the grasp is not | - | - | - |
| **M2a** | does the mounted hand beat the pinch (P104 transferred) | **>= 1.5x** sustained axial, **creep <= 1.0 mm** | both forms < 1.5x → buy no hand | 16-24 h | 2 h | 2 |
| **M2a measured (P106)** | surrogate **1.87-2.05x** sustained / creep **0.11-0.25 mm**; Allegro **not evaluable** (<= 3 of 4 tips reach one payload) | surrogate **PASS**; Allegro no result | **not fired** (the surrogate passes) | - | - | - |
| **M2b** | does it *approach* without batting the fruit | no-contact **<= 1/15** | the hand is a pipeline negative | 8-16 h | 2 h | 2 |
| **M3** | can the scripted line run it | acceptance **not worse than 8/10**, 0 clearance contacts, landing 100 % | cannot match 8/10, or 1+ contact | 80-120 h | 10 h | 10 |
| **M4** | does the policy add anything over the scripted hand | **+8 points** vs the scripted hand, no new reason, cycle <= +5 % | ship the scripted hand | 24-40 h | 9 h | 2 |
| **M5** | does it beat the shipped cell | `cnp` **<= 8/80**, placed **>= 58/80**, landing 100 %, 3 references | do not ship | 16-24 h | 2 h | 1 |
| | | | **total** | **170-265 h** | **~26 h** | **~17** |

### 5.7 What would reverse this plan

* **M1 fails on the station**: a hand's envelope does not fit the pick pose at
  x 0.20-0.36 (R10-A's cleaned band) → the stage needs a **workstation** phase
  first (P90 measured the place station closed; the pick station would be next),
  and a hand is premature.
* **M2 reads the 3+1 topology below the bar and the surrogate above it**: that is
  §1.7's prediction, and it means **the purchase must be a radial or a
  strongly-enveloping hand**, not an anthropomorphic one - which changes which
  vendor, not whether to buy.
* **P104 §7(a)'s pair-friction reading is a by-product, not a cone measurement.**
  It implies the engine's **average** combine gives `mu_app` **1.05-1.45** and that
  the tree's `mu_eff` 0.45 is 2.3-3.2x **pessimistic**. If a re-measure contradicts
  it and the pair is *weaker* than the fixture assumed, the pinch's absolute
  capacity (11-14 N) falls and **M2's 4.90 N per-contact target must be re-derived** -
  the *ratios* would not move (they are `mu`-free) but the force the hand must
  match would. The re-measure is one offline cell and it is a **precondition of
  M1's drive tune**.
* **The wrist render cannot be afforded**: ~95 ms/decision thins the RTC margin to
  h <= 11 of 16 and, if it goes further, forces architecture (b) with the in-hand
  camera only - which §3.1 predicts will fail.

---

## 6. What this plan does not price

* **The hardware.** No purchase is made before **M3**. The purchase point is
  explicit: **M2 says the geometry is worth 1.5x** and **M3 says a scripted hand can
  run this cell at all**; only then is a hand a purchase rather than a probe. The
  candidates are ORCA (**< 2,000 CHF** material [R], hardware licence
  **NOASSERTION** [U]) or LEAP (**$2,000** parts, CAD **CC BY-NC-SA** [V]). The
  flange bolt pattern, the tendon routing and the wrist cable path are **bench**
  work and are **[U]**.
* **The conversion** (MJCF/URDF → USD) - **40-80 h** [E], and the tendon mapping
  is the schedule risk that the Allegro-first choice exists to avoid.
* **The real jaw's clamp force.** P104/P76 both say the sim's force is not
  anchored to a real jaw; a real hand's fingertip force at the current limit is
  a datasheet number, not a measurement.
* **A visuotactile renderer.** There is none in the loop (`logs/p42/SIM_LIMIT.md`
  §3), so "does a soft pad image 2 mm" stays the survey's T2 bench and is
  **[U]** here.
* **The wrist camera's optics.** The sim has one mast camera; a wrist view's
  intrinsics, occlusion and depth noise are a new sensor model and are not priced.

---

## 7. The one-paragraph summary for a reader who will not read the rest

The hand is justified at **1.87-2.05x** static axial and **9-15x** on creep, and
that pass belongs to a **radial 4-contact** grasp that **no purchasable hand has** -
so the first sim hand is the **Allegro USD** (verified, Isaac-native, direct-drive,
16 joints) as a **mount and 3+1-topology probe**, with a **4-pad surrogate** as the
form that actually licenses a purchase. The observation goes **25 → 34-D** (14 arm
+ 16 active hand + 4 tactile; the four dead channels go), the action stays **9-D**
with the finger channel as the hand's **synergy** and the 16 joints decoded from an
**8-D supervised latent**, and every store is invalid so the recollection is
**150-200 episodes, 2.5-3 h, ~15 GB** through the **rollout path with failures
kept** - because the collector currently discards them. Five milestones, each with
a kill, at **170-265 h labour and ~17 GPU-hours**; the arithmetic ceiling the
hand can even reach is **93.8 %** (all 17 `cnp` convert) and the measured seated-slide
share puts it at **91.3 %**, with the 5 never-held attempts an acquisition class no
contact count can touch - and the P4 bar of 82.5 % is only **8 of those 17**.
