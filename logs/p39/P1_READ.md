# P39 phase 1 — the left grip/carry: the corpus, the two levers' geometry, and what is not there

Status: **Tier-C offline, read-only on the tree.** Written 2026-10-25 on `e061d94`
(the P38-final tree; `tasks.py` `cdde6bd2`, `scene.py` `ab85dca2`, `assets.py`
`61baf52b`, `meshes.py` `41efc522`, `kinematic_gripper.py` `e40b1ca2`,
`policy/trigger.py` `b09d3cb2`, `rl_env.py` `dba80de6`,
`configs/motion_reference.json` `25ade92b`,
`configs/motion_reference_twoline.json` `181c9151`; working tree clean).
**No simulator run, no `src/`/`scripts/`/`configs/` edit, no default changed, no
commit.** Every number below is re-derivable by the three scripts in this
directory; the pre-registration is `logs/p39/PREREG.md`.

Re-derivation:

```bash
python3 logs/p39/left_corpus.py --assert    # -> 01_left_corpus.txt   (the per-leg corpus)
python3 logs/p39/finger_geometry.py --assert # -> 02_finger_geometry.txt (the tip/lip/belt algebra)
python3 logs/p39/prepose_audit.py --assert   # -> 03_prepose_audit.txt  (the lane-0 pre-pose)
```

All three `--assert` runs PASS (9 + 10 + 11 pins). The pins are the numbers this
read's verdict depends on; a changed corpus or a changed default fails them
instead of silently re-writing the prose.

---

## 0. The answer in one screen

* **The corpus is the lane-0 configuration, re-derived per leg.** 48 parsed
  attempts over four shipped-scripted families: the left carries **15 cnp + 2
  no-grasp over 22 attempts**, the right **0 cnp over 26**. The frame-free band
  separates with **no overlap** (placed `grasp_lift` 0.041-0.300 m/s, cnp
  0.343-2.022), the post-release force servo reads `F_min = 0.00 N` on **15/15**
  cnp legs and 2.40-4.38 N on **31/31** placed legs, and the left's place leg is
  53-58 cm / 349-384 ticks against the right's 32-41 cm / 209-272 on the same
  symmetric targets.
* **The mechanism is the W8-B loaded slide, and on this line it is a *lip*
  problem, quantified.** At the shipped dynamic aim (jaw at the fruit's centre +
  0.070 m) the physical plate reaches **6.8 mm below the fruit's equator** - that
  6.8 mm is the only material the payload has to walk out of, and the plate's
  tip sits `r - 6.8 mm` above the belt. **Lip + tip-belt clearance = r, exactly**
  (10 pins, `02_finger_geometry.txt`): the two are one purchase, which is why
  every measured grip-direction lever has been negative while every
  clearance-direction lever has been free.
* **Lever 1 (the short tip) is predicted *null on the cnp class* and positive
  only on belt clearance.** Shortening by `delta` removes `delta` of lip 1:1 and
  buys `delta` of belt clearance, and it is **free only up to 4.2 mm** - the
  bound at which the plate's distal edge reaches the contact patch's lower edge
  (the patch is 3.3-5.3 mm tall, not the 85 mm plate). The matched pair (shorten
  `delta` + lower the aim `delta`) is a **geometric null by construction**
  (asserted). The class needs the *opposite* sign: a **longer** plate is the only
  form the measured mechanism rewards, and the belt bounds it at **+7.2 mm** on
  the 2.8 cm pool minimum (8.2 mm on the 3.0 cm lychee the corpus drew).
  Both forms are one signed knob; the brief's shortening is registered as the
  hardware/clearance arm, the extension as the class arm (owner-gated - it is
  not the authorized form).
* **Lever 2 (the lane-0 pre-pose) does not exist.** `_prepare_two_line_stations`
  solves a station-specific pre-pose only for an arm whose station is *off* the
  calibrated pick point, and the two-line's **left** station *is* the calibrated
  pick point (`0.0`): the left is skipped and runs the shared `grasp` config -
  the same one the single-arm line runs. Its catch aim is identical too (the
  shipped two-line lead is `0.0`). So the two-line left's 0/10 cnp is **not** a
  pose result and cannot license a pose port; the two-line left differs by the
  *supply*, the *scheduler* and the adopted two-line carry monitor. The only
  remaining pose term on the P33 §2.4 correlate is the **wrist attitude**, whose
  hold-all-legs form is already measured negative (`logs/444`); the
  **lift-only** hold is the unmeasured, bounded form and is what the
  pre-registration carries as L2.
* **Both levers stay default off**; the shipped tree is byte-unchanged by
  construction (L1 authors nothing at `delta = 0`, L2 needs three env vars and
  its scope is a leg name the shipped carry already knows).

---

## 1. The left cnp corpus

### 1.1 The families (generated, `01_left_corpus.txt`)

| family | log | left att / placed / cnp / no-grasp | right |
| --- | --- | --- | --- |
| acceptance, pear-on | `logs/p32/D1_accept_pear.log` | 5 / 1 / **3** / 1 | 5 / 5 / 0 / 0 |
| acceptance, pear-off | `logs/p32/92_accept_raw_pear_off_current.log` | 3 / 0 / **3** / 0 | 7 / 7 / 0 / 0 |
| pear battery, new profile | `logs/p32/90_pear_battery_new.log` | 4 / 1 / **3** / 0 | 5 / 5 / 0 / 0 |
| pear battery, old profile | `logs/p32/91_pear_battery_old.log` | 4 / 1 / **3** / 0 | 5 / 5 / 0 / 0 |
| bed battery, single arm | `logs/p33/20_single_control.log` | 6 / 2 / **3** / 1 | 4 / 4 / 0 / 0 |
| **total** | | **22 / 5 / 15 / 2** | **26 / 26 / 0 / 0** |

Two slots in the pear battery are the *supply* class, not a grasp outcome:
`attempt 7` (`90`) and `attempt 0` (`91`) read `no eligible fruit` and are
counted separately (pinned). They are why the battery reads 9 attempts where 10
were asked.

**The counts are branch labels, not rates** (AGENTS §2): the acceptance families
are three branches of one scenario, the two pear-battery logs are one species
under two finger profiles, and the bed battery is one of the five logs P33
pooled. The *class* is the object; the per-family split is what the
pre-registration's endpoints are defined on.

### 1.2 The per-leg evidence (`01_left_corpus.txt` §"frame-free leg band")

| class | leg | n | `in-hand |v|max` m/s | `slip_max` |
| --- | --- | --- | --- | --- |
| placed | `grasp_lift` | 25 | **0.041 - 0.300** | not quoted (W8-B §1: frame-contaminated) |
| placed | `place0/1` | 25 | 0.069 - 0.182 | not quoted |
| cnp | `grasp_lift` | 12 | **0.343 - 2.022** | not quoted |
| cnp | `place0/1` | 12 | 0.447 - 2.035 | not quoted |

No overlap on either leg: the escape has started on the lift in **12 of 12**
instrumented cases. This reproduces P33 §2.2 exactly (same logs, same bands) and
replaces P33's five-family pooling with a per-attempt table.

The **post-release force servo** is the cleanest consequence in the corpus:
`F_min = 0.00 N` with `gap == sep` on **15/15** cnp legs, `F_min` **2.40-4.38 N**
on **31/31** placed legs. It is a *consequence* (the payload is already out of
the jaws), not a cause - but it is a perfect post-hoc label and it is why a
"force collapse" reading of the class is wrong (W8-B: the force is at the carry
level at the *onset*).

The **close geometry is not the discriminator** on this corpus either.
Commanded closed span minus the labelled diameter: placed median **-1.30 mm**
(n=31, -7.30..-0.60), cnp median **-1.20 mm** (n=15, -3.80..+5.50) - the ranges
overlap almost completely. (P33 §2.3 printed `+0.20 / +0.12 mm` for the same
question on the left only; the quantity's formula is not in that record, so read
the *conclusion* - the close is not commanded looser on the failures - and not
its magnitude. This read's quantity is stated above and pinned only for
overlap.)

### 1.3 The `[carry]`/onset facet: still absent, and where the quote comes from

No `[carry]` row exists in any of the five logs (`FRUIT_CARRY_DIAG` was never
set on the scripted line), and no `[acq]` row (direct path only). So the onset
facet - onset row, force@onset, contacts-at-onset, contact-loss delay - is
**quoted from the W8-B trace corpus on this same OpenArm hand**
(`logs/w8/B_RESULTS.md` §2), not measured here:

* onset force **0.45-12.9 N, median 4.90 N** (the grip's carry level - not a
  collapse); contacts-at-onset **1** (single-sided) on the median leg;
* the pads' **jaws pried to 98-99 mm** in **17 of 31** escapes;
* contact loss **2-132 ticks** after the 2 mm crossing, median **25**;
* onsets **28 of 31 on `grasp_lift`**; displacement dominated by **+z, out
  through the fingertips**;
* **5 of 31** escapes survived their leg at **18-25 mm** of slip (they crossed
  the 2 mm trigger and arrested).

That last bullet is the binding one for lever 1: **the only measured arrest
distances in the corpus are 18-25 mm**, i.e. the same order as the lip plus a
small fruit's radius. It is the reason the pre-registration's expected bounds for
the extension arm are "0-2 of 3-6", not "the class falls".

### 1.4 The arm correlate, re-derived

Placed attempts only (`01_left_corpus.txt` §"place-leg transfer"):

| arm | n | place distance | place ticks |
| --- | --- | --- | --- |
| left | 3 | 53-58 cm | 349-384 |
| right | 22 | 32-41 cm | 209-272 |

Both arms' `jaw_target` are symmetric (`(0.43, ±0.50)`), so the difference is the
arms' own transfer solution - the documented **93.6 deg** left solve over the
output line (`tasks.py:2766`, `logs/428`), with the place point at the reach
boundary (0.4065 m vs the measured ~0.41 m). Within the left the failures span
50-63 cm and the placements 53-58 cm: **overlapping**, so the transfer length is
a correlate, not the cause (P33 §2.4, reproduced). What it *does* establish is
that the left's cycle contains an arm-specific attitude excursion the right's
does not - the only pose term left in the frame, and the one lever 2 must target
if it is to target anything.

### 1.5 The mechanism summary (one paragraph)

A payload is pinched by two flat plates at the fruit's widest section with
~4.2 N of normal force per face (the finger drive's limit) and a 0.2 mm
commanded interference. The grip has **no cavity and 6.8 mm of lip**, so the
payload's walk-out (driven by the pads' own profile, not by gravity: the friction
capacity is `mu * F ~ 8 N` against a fruit weight of a fraction of a newton) is arrested by nothing but the
friction cone and the shape of the fruit. When the local width at the contact
band shrinks - a cone, a pear's neck, a rolling sphere - the force-saturated
drive cannot follow it down, one face loses contact, and the payload leaves
through the fingertips. On this line that happens on the **left** because the
left is the arm whose transfer holds the tool at the flattest attitude for
longest (93.6 deg at the place), i.e. the arm whose palm-face contact
*direction* changes most during the carry; the right's 26/26 says the hand form
sets the margin and the arm's cycle sets the incidence (P33 §4.1 (B)).

---

## 2. Lever 1 — the finger: geometry, the two signed forms, the implementation

### 2.1 The current finger, measured (`02_finger_geometry.txt` §1)

| quantity | value | source |
| --- | --- | --- |
| plate extents, link frame (closing axis / along the belt / down) | **33.3 / 61.0 / 84.9 mm** | the build's own `_finger_face_frame` readout, all four links (`logs/p3face/screen_v.log`) |
| distal extreme (`tip_coord`) | **+80.5 mm** along `e_long` | same |
| face plane (`face_coord`) | **+5.8 mm** along `e_face` | same |
| tip below the jaw centre, near-vertical pose | **76.8 mm** | `logs/166_collision_probe.log` (finger AABB 24 mm *inside* the slab: the distal face is the contact) |
| tip below the jaw centre, tilted pose (P0) | **58.6 mm** | `logs/p30a/10_probe_parts_default.log` (AABB 13 mm *above* the slab: the **corner** leads) |
| the task's model of the same | **60.0 mm** | `tasks.py` `FRUIT_FINGER_LEN` |
| the asset's constant | **76.0 mm** | `assets.py:642` `SceneConfig.finger_length` |
| open face gap / link span | **75.8 / 98.0 mm** | `assets.py:636-640` |
| pried-open link span | **98.1 mm** | W8-B (17/31 escapes) |
| the aim's standoff | **70.0 mm** | `FRUIT_FINGER_LEN` 60 + `PAD_LIFT` 10 |

Two readings that decide the lever:

1. **The corner is a real term.** The two measured stops differ by **18.2 mm**;
   a corner drops `half_extent * sin(theta)` below the distal plane, so the
   plate's 16.65 mm half-thickness in the closing direction explains it at
   ~20-30 deg of tool tilt (the 30.5 mm along-belt half would need ~10 deg). The P0 stop is a
   **corner stop**, and the lip in that pose is **negative** (-11.4 mm): the
   plate's distal edge is *above* the equator, so the pinch is on the upper
   half only. **The lip is not a designed quantity today - it varies from
   -11.4 mm to +6.8 mm with the wrist attitude at the close.**
2. **The task's standoff is 16.8 mm shorter than the physical tip**, which is
   the P30-C §3.2 R2 reporting item, restated here as a *grip* fact rather than
   a margin item: the model believes the tips are at the fruit's centre + 10 mm;
   they are at the fruit's centre - 6.8 mm.

### 2.2 The invariant, and the R8-A D2a re-read

With `s` the standoff, `L` the tip below the jaw, `r` the fruit's radius:

```
lip      = L - s                (how far the plate reaches below the equator)
clear    = r - lip              (the tip's height above the belt top)
lip + clear == r                (exact; asserted over every r, L and drop)
```

So on a fixed aim, **a shorter plate is a 1:1 purchase of belt clearance paid for
in lip**. `FRUIT_GRIP_PLANE_DROP` (R8-A D2a) is the same purchase from the other
side: it lowers `s`, so `lip` grows by the drop and `clear` falls by it. The
form is belt-legal only for `r >= lip0 + drop`:

| drop | needs r >= | legal diameter >= |
| --- | --- | --- |
| -4 mm | 10.8 mm | 21.6 mm |
| **-8 mm** (measured) | **14.8 mm** | **29.6 mm** |
| -20 mm | 26.8 mm | 53.6 mm |

The corpus's smallest fruit is the **3.0 cm lychee** (`01_left_corpus.txt`,
`logs/p32/D1` attempt 9), and the pool can draw a 2.8 cm one (`assets.py`
lychee 2.8-3.8 cm): at r = 15.0 mm the -8 mm form leaves **+0.2 mm** of tip
clearance - *at* the belt - and at r = 14.0 mm it is **-0.8 mm**, i.e. the plate
is *in* the slab. **That is not R8-A's attributed
mechanism** - R8-A names the catch-up break-test confound (the drop moves
`catch_target` but not `desired_tip`'s `_dynamic_pad_lift`, so the -8 mm residual
persists and the catch-up caps: 14/15) and the arm's vertical reach boundary.
The belt bound is a **co-existing** limit, and its consequence is the one this
phase acts on: **no grip-plane drop deeper than ~8 mm can be tested on this
supply at all, with this tip.** Any deeper form is a `delta`-coupled design.

### 2.3 The two signed forms

`delta` = the signed change of the plate's distal plane (negative = shorter).

| delta | tip below jaw | lip | tip clear, 2.8 cm | patch | predicted cnp effect |
| --- | --- | --- | --- | --- | --- |
| **-4 mm** (F1) | 72.8 mm | **+2.8 mm** | +11.2 mm | intact | **none** (contact-neutral; the free bound) |
| -6 mm | 70.8 mm | +0.8 mm | +13.2 mm | clips 1.8 mm | not admissible (patch cut) |
| 0 | 76.8 mm | +6.8 mm | +7.2 mm | intact | - (the shipped form) |
| **+4 mm** (F2) | 80.8 mm | **+10.8 mm** | +3.2 mm | intact | **0-2 of 3-6** (the arrest band) |
| +6 mm | 82.8 mm | +12.8 mm | +1.2 mm | intact | 0-2, at the belt limit |
| +7.2 mm | 84.0 mm | +14.0 mm | **0.0 mm** | intact | not admissible (tip at the slab) |

* **F1 (`-4 mm`) is the brief's form and it is a *diagnostic*, not a grip
  lever.** The commanded interference is 0.2 mm, so the contact patch is only
  **3.3-5.3 mm tall** about the equator (`02_finger_geometry.txt` §6) and its
  lower edge sits 1.7-2.6 mm below the equator. A shortening of up to
  **4.2 mm** therefore leaves the patch **intact on every fruit** - the free
  bound, `lip0 - h_max` - and removes material that is provably *not in contact*.
  (At `-6 mm` the distal edge rises above the patch's lower edge and clips
  1.8 mm of the largest fruit's patch: a real, if small, mechanism change, so
  `-6 mm` is not the neutral form and is not the arm.) F1's expected
  scripted stream is **byte-identical** to the control. That identity is a
  one-bit test of whether the lip is load-bearing *below the patch*: if the
  stream moves, it is, and the class-relevant direction is the extension; if it
  does not, the lip is inert in that band and no shortening/extension argument
  can claim the class on the lip alone. Either answer is worth the run, and it
  is the cheapest arm in the phase. What it also delivers, unconditionally:
  **+4 mm of tip clearance** (7.2 -> 11.2 mm on the 2.8 cm pool minimum,
  8.2 -> 12.2 mm on the 3.0 cm lychee the corpus drew) and the *hardware* truth
  that the physical tip is 16.8 mm longer than the model.
* **F2 (`+4 mm`) is the mechanism-derived form and it is *not* the authorized
  lever.** The measured mechanism is a walk-out through the fingertips; the only
  passive geometry that resists it is material *below* the equator, which is
  exactly what a longer plate adds. The belt bounds it at **+7.2 mm** on the
  2.8 cm pool minimum (+8.2 mm on the 3.0 cm lychee the corpus drew, +10.2 mm on
  the 3.4 cm strawberry, +28.2 mm on the 7.0 cm apple), so `+4 mm` is legal on
  the whole supply with 3.2 mm to spare on the worst fruit - and at `+4 mm` the
  patch is also *intact* (the distal edge moves away from it), so F1 and F2 are
  the same magnitude either side of the shipped form. It is registered as an arm
  and flagged: the owner
  authorized "the short-tip finger"; running the extension needs the same
  sign-off the short form has.
* **What is *not* proposed, and why.** P30-C §2.3's **24-45 mm cut** is the
  *hardware* form ("so the pads can physically reach a small fruit's centre"):
  on the sim line it would put the distal edge 17-38 mm *above* the equator,
  i.e. remove the lip entirely and then some, and it is predicted **negative**
  for the cnp class. The two questions are different - P30-C asks *can the hand
  reach*, P39 asks *does the grip hold* - and the record should not let the
  first stand in for the second. The **belt slot** stays rejected on P30-C's own
  arithmetic (a 20 mm slot under a 28 mm lychee leaves ~4 mm of bearing per
  side). The **scoop/ledge** (R8-A D2b) is a measured negative (the ledge bats
  the payload: no-contact 2 -> 9, battery 12/20 -> 6/20 x2), the **additive face
  plate** is a measured negative on the direct path (5/10 at a 12 mm protrusion;
  7/10 co-planar-only, R8-A §2), and the **soft pad** is a measured negative
  (7/10, A2 held 240 ticks then slid 313.1 mm, A6 never gripped) - the whole
  material-into-the-entry-envelope family is closed, which is why F2 moves the
  *distal plane* and adds nothing to the face.

### 2.4 The implementation path

**Scene-level, default off, signed:**

`FRUIT_FINGER_TIP_DELTA=<m>` in `scene.build`, after `_add_finger_colliders`
(which must keep running first, both for its verdict and so
`assert_finger_colliders` sees the shipped count), for each of the four links:

1. `self._disable_link_colliders(link)` - the same call the recessed-face path
   uses (`scene.py:723`) to turn off the shipped finger-mesh colliders;
2. author one replacement plate as a convex box on the **same face plane**
   (`face_coord`), with the same across width (`PLATE_MID`), a body thickness
   that covers the plate's face extent, and its **distal plane** at
   `tip_coord + delta` - i.e. `_author_flat_face`'s frame and material path
   (`scene.py:861`), which already binds `FRUIT_FINGER_MU`,
   `FRUIT_FINGER_COMPLIANCE` and `FRUIT_FINGER_CONTACT_DAMPING`;
3. `say(...)` the authored numbers (distal plane, face plane, width, thickness)
   so the build log carries the change.

Why this path and not the asset:

* `assets/openarm_flat/openarm_flat_deinst.usda` is **1.1 GB, gitignored, and
  regenerated** - an edit there is not a committed artifact and not reproducible
  on a fresh checkout, while the *collision* geometry is re-authored at build
  time anyway (`_add_finger_colliders` applies CollisionAPI to the *visual*
  meshes);
* the shipped visual mesh stays as-is, so the **rendered image does not change**.
  That is a controlled comparison for the scripted A/B (which never reads the
  image) and a stated confound for the policy interface (a policy conditioned on
  a long visible tip and a short physical one is a sim-only artifact) - and it is
  the reason the finger arms are **scripted-line only** and must not be run
  behind the policy evaluator;
* `delta = 0` authors nothing at all, so the shipped tree's byte-identity is by
  construction (the `FRUIT_FINGER_FACE=flat` build already authors no faces).

**Not offered:** scoping the change to the left arm. It is a hardware change, so
it applies to all four links; the right lane's **26/26** (and the acceptance's
12/12) is the price of admission and is a pre-registered no-harm endpoint, not a
detail.

### 2.5 The offline checks, and the pick battery

| # | check | instrument | pass |
| --- | --- | --- | --- |
| O1 | the signed table is belt-legal on the whole measured supply | `finger_geometry.py --assert` | PASS (already) |
| O2 | the build authors the distal plane at `tip + delta` | the new `say(...)` line | +-0.5 mm |
| O3 | the tip's world height moves by exactly `delta` | `scripts/47_robot_collision.py`, conveyor on, one run per arm: the **difference** of the two jaw floors is the read (the absolute floor is pose-dependent - 58.6 vs 76.8 mm on two historical calibrations - so only the delta is quotable) | +-1.5 mm |
| O4 | the grasp still finds the payload | `scripts/430_openarm_grip_probe.py` (or `431`) on a static fruit at the aim: contact force, `sep` at contact, fingertip-to-fruit | force 3-6 N, no "never gripped" |
| O5 | the corridor is unchanged | the build's `say(...)` width vs `PLATE_MID` | equal |
| P1 | the pick battery: `scripts/accept.sh` + the species-locked pear battery + `scripts/190_twoline_gate.sh` | one `154_claim_run.sh` claim per arm-pair | per `PREREG.md` |

---

## 3. Lever 2 — the lane-0 pre-pose: the artifact is not there

### 3.1 What the audit finds (`03_prepose_audit.txt`)

| term | two-line left | single-arm left | same? |
| --- | --- | --- | --- |
| pick station y | +0.00 (default) | `cfg.pick_y` = +0.00 | **yes** |
| station-specific pre-pose | **none** - the solve is skipped at the pick point | none | **yes** |
| pre-pose fallback | the calibrated `grasp` config | the calibrated `grasp` config | **yes** |
| catch aim | `station_y + lead` (lead **0.0** by default) | `station_y` | **yes** |
| hand | OpenArm, the same four links | same | **yes** |
| grade routing | pure: left takes A only | lane 0 = A | **yes** |
| supply | the dense wave sheet, balanced A:B:C | the scattered pool, A:B:C 0.5/0.3/0.2 | no |
| concurrency | concurrent right arm, one shared tick | single arm | no |
| carry monitor | adopted (P10-C.3, `CONFIRM_MM=8`) | never armed | no |

`_prepare_two_line_stations` (`tasks.py:5795`) skips a side whose station equals
`cfg.pick_y` **on purpose** ("shared station: the calibrated config is correct"),
and the two-line's left station is exactly that. So the two-line left's 0/10 cnp
(P33 §1.2) is not a pose result: the three things that *do* differ are the
supply, the scheduler and the adopted carry monitor - and all three are
scenario/timing, not pre-pose.

### 3.2 What is left, and why it is the wrist

The one pose term the corpus still surfaces is §1.4's attitude excursion: the
left's place solve swings the tool to **93.6 deg from vertical**, the flattest
posture in the cycle and the only tilt the posture probe raises (`logs/428`).
The tree already carries the lever for it: `FRUIT_CARRY_HOLD_QUAT=1` pins the
wrist at the attitude the grip was taken with - and it is **measured negative in
its shipped form**, because it is held through the *place* leg too: "the IK
stalls ~12 cm short of the output line and the fruit drops beside it"
(`logs/444`, quoted in the code comment at `tasks.py:2745-2749`).

The bounded, unmeasured form is therefore **the same hold scoped to the
`grasp_lift` leg**, where 28 of the 31 measured onsets are (`logs/w8/B_RESULTS.md`
§2). The scope mechanism already exists in the tree as a convention
(`FRUIT_CARRY_GUARD_LEGS` is an exact per-leg-name match), so this is a two-line
change: `FRUIT_CARRY_HOLD_QUAT_LEGS` (default empty = every leg, the shipped
behaviour) and `FRUIT_CARRY_HOLD_QUAT_ARM` (default empty = both arms), both read
only when `FRUIT_CARRY_HOLD_QUAT=1`. The lever should also be **inactive on a
two-line session** (`not session.twoline`): it is a lane-0 single-arm item, and
that exclusion is what makes the two-line's byte-identity a *prediction* in the
pre-registration rather than a burden.

### 3.3 The OOD / re-record cost

* The hold moves the **branch** (the arm's configuration through the lift
  changes), so the acceptance needs its **own** `configs/motion_reference.json`
  re-record - the shipped `25ade92b` is per-scenario and cannot certify a new
  branch. The same is true of lever 1 (the finger is global). Two new
  references, not one; they must be archived alongside, not overwritten
  (`scripts/105_motion_regression.py --write-fingerprint` writes a new file).
* **The right lane and the two-line are the no-harm burden**: the right's 26/26
  placed (12/12 on the acceptance) and the two-line's 442/442 `[fruit]` stream
  (`logs/w7/10`) + `190` PASS. L2's arm scope makes the right lane's identity a
  *prediction* (it can be stated before the run); L1's cannot be, so its
  right-lane non-inferiority is a measured endpoint.
* **The policy/direct interface is untouched**: neither lever changes what the
  direct loop does (L1 changes the physics the policy would see, but the finger
  arms are scripted-only by construction - §2.4), and no checkpoint, store or
  `rl_env` path is read.

---

## 4. What phase 1 changes and what it does not

* Changes: nothing outside `logs/p39/`. No `src/`, `scripts/` or `configs/`
  edit; no shipped default; no commit.
* `AGENTS.md` is **not** edited: phase 1 measures no outcome and changes no
  default, so it has no §2 claim to add. Phase 3/4 own that edit.
* The one thing this phase *closes* by argument, not by measurement: the
  briefed lane-0 pre-pose port (§3.1). It is a null by construction, and the
  pre-registration carries the replacement arm instead.

### 4.1 Provenance (md5, on the tree above)

| file | md5 |
| --- | --- |
| `left_corpus.py` | the generator; `01_left_corpus.txt` `10728bb2` |
| `finger_geometry.py` | the generator; `02_finger_geometry.txt` `3527b69a` |
| `prepose_audit.py` | the generator; `03_prepose_audit.txt` `27451a04` |

`logs/` and `.slim/deepwork/` are gitignored (`.gitignore:7`, `:29`), so
`git status` is clean; the evidence lives in this directory. The three
`--assert` runs are deterministic (re-run before this file was written).
