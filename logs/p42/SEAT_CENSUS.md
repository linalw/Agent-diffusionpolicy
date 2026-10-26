# P42 phase 1 — the seat census: the pads are centred on the payload at the
# freeze, and the escape is a mid-lift walk, not a seating error

Measured 2026-10-26 on `c2760bf` + this phase's (uncommitted) `tasks.py` /
`rl_env.py` change. **No commit, no `configs/` change** (both references still
read **8a399626** and **2246f83c**). Six claimed runs, ~30 min of simulator wall,
all sequential through `scripts/154_claim_run.sh` (every command in §8). Scope:
the scripted single-arm moving catch (`20_pick_place.py`); the two-line, the
direct/policy handover and the hybrid canary were **not** run this phase.

---

## 0. The short answer

* **The seat is centred.** At the close freeze the pads' midpoint is
  **1.36-4.65 mm** from the fruit's centre in x/y on **every one of the 20 grips**
  in both corpora (median 1.7-2.4 mm), and the contact is **two-sided on 20/20**
  (`n=2`, per-pad force split `asym` median 6-17 %, max 35 %).
* **The only systematic axis is z, and it is commanded, not an error**: the pads
  sit **+69.3..+71.7 mm** above the fruit's centre, which is
  `_pad_standoff(True, sample)` (`FRUIT_FINGER_LEN` 60 mm + the dynamic pad lift)
  - i.e. the fruit's centre rides ~10 mm above the pads' distal stop
  (`lip ≈ +10 mm` in the `[attitude]` vocabulary). Nothing in `x/y` is off-seat.
* **The offset does not predict the escape.** On the species-locked pear battery
  the four escapes are the **tightest seat cluster in the corpus**
  (|d_xy| 1.36-2.06 mm, median 1.72) while the corpus's **largest** lateral
  offset (+4.2, +2.0 mm = 4.65 mm) **placed**. Acceptance: escapes 1.82-3.47 mm
  vs placed 1.62-2.69 mm - the ranges overlap and the escape median is the
  *higher* one by 0.4 mm, i.e. noise at n = 4/6.
* **What does separate is the walk, and it separates late.** By the last lift
  sample the payload's displacement in the hand frame is **104-276 mm** on the
  pear escapes vs **28-58 mm** on the placed legs, and one pad has lost contact
  on **18 of 32** escape carry samples vs **0 of 48** placed carry samples.
  At the first lift sample (2 % of the leg) both classes read the same
  (|d| 2.8-9.9 mm, two-sided). Seven of the eight escapes lose the grip *inside*
  the lift; the eighth (an acceptance peach) survives the lift at 24.3 mm and
  goes on the place leg's first ticks.
* **Consequence for the lever**: the pre-close centring registered in
  `logs/p42/PREREG.md` is registered *against* a measurement that already denies
  its premise (§6, falsifier F1). Its whole available correction is the
  catch-up tolerance itself (6 mm) minus the ~2-4 mm the catch-up leaves, and
  the thing that loses the payload is a 100-350 mm walk that starts *after* a
  centred freeze.

---

## 1. The mimic: "one finger lags" is ruled out by construction

`assets/openarm_flat/openarm_flat_deinst.usda:3822-3843`: each hand's second
finger joint is a **`PhysxMimicJointAPI:rotY`** block with
`physxMimicJoint:rotY:gearing = -1`, `naturalFrequency = 0`, `dampingRatio = 0`,
`offset = 0`, `referenceJoint = </World/OpenArm/joints/openarm_<side>_finger_joint1>`.
`naturalFrequency = 0` is PhysX's rigid mimic: the mimic joint is a **hard
constraint** on the reference joint, not a spring. So `joint2` cannot lag,
cannot carry its own drive (`joint2` has no `PhysicsDriveAPI:linear` at all -
P41 phase 3 §1 reads `maxForce = 0.0 N` on it), and the two finger links are
**geared 1:1 in opposition by construction**. The jaw is symmetric.

Therefore `pad_centre()` - the midpoint of the two finger links, and for this
hand literally the jaw centre (`kinematic_gripper.py`, `OpenArmGripper.pad_centre`
returns `arm.jaw_centre()`) - **cannot** be biased by a finger asymmetry. Any
non-zero pad-centre-minus-fruit-centre vector is the *seat*, and nothing else.
The measurement agrees: **every freeze in both corpora reads both pads in
contact** (`n=2` on 20/20) and the per-pad split is 0.01-0.35 (§4), so there is
no "one finger never arrived" signature at the seat. **A dual drive, a
follower lag or a "one finger closes first" hypothesis is moot for this asset.**

---

## 2. The instrument (`FRUIT_SEAT_DIAG=1`, default off)

`src/fruit_sorting/tasks.py`:

| piece | where | what |
|---|---|---|
| `self._seat_diag` | `__init__` (next to `FRUIT_GRIP_EFFORT`) | one env read |
| `_seat_read()` | beside `_carry_attitude` (the `[attitude]` site) | prints **one** `[seat]` row |
| `_seat_arm()` | beside it | per-leg sample schedule, `None` when the knob is unset |
| freeze hook | the dynamic close, at the tick `freeze_cmd` commits | sample **t=0** |
| carry hook | the gripper-led carry loop, post-step, at 3 + 1 scheduled ticks | samples 1-4 |

Row (one line, one read-set):

```
[seat] left a=1 idx=12 grasp_lift@97 t=97 d=(+1.5,+6.5,+65.1)mm |d|=65.6mm
  tool=(+0.2,-1.4,-65.6)mm drift=(+0.1,+5.7,-6.6)mm F=(5.1,4.9)N n=2 asym=0.02
  cmd=63.9mm sep=73.9mm faces=+10.0mm tilt=0.4deg
```

* `d=` **world** = `pad_centre() - spawner.position()` (the frame the aim uses);
  `tool=` the same vector in the TCP frame (column 2 = the direction the fingers
  extend), so `tool_z` is the along-finger term and `tool_x` the closing axis;
  `drift=` is `d` minus its freeze value = **minus** the payload's displacement
  in the hand frame.
* `F=` is the per-face tactile magnitude (`_freeze2_split`, the P17-B freeze
  gate's own grouping), `n` the contact count, `asym = |F1-F2|/(F1+F2)`;
  `cmd`/`sep`/`faces` are the commanded and measured jaw face separations and
  their difference; `tilt` the tool angle from world -Z.
* **Cost, bounded**: `SEAT_MAX_SAMPLES = 5` per grip (freeze + 3 lift + 1 place),
  one read-set each, one row per read (five rows per grip).
* **x/y are readable without per-tick work** (the brief's fallback is not
  needed): `pad_centre()` on this hand *is* `arm.jaw_centre()` - the midpoint of
  the two **finger-link** world poses - and the fruit's centre is
  `spawner.position(sample)`, a fruit-pose read the workspace notes record as
  neutral. The finger-link read is the one class the notes flag when it is taken
  every tick, but the carry loop **already** takes both every tick for its slip
  bookkeeping (`tasks.py`, `fruit`/`pads`), so the seat read reuses them; the only
  added work at a scheduled tick is one tactile set + one TCP pose, and the net
  effect is **measured zero** (§"Neutrality": 376/376 and 377/377 identical).
* **Schedule - fractions of the leg, not fixed ticks.** `SEAT_TICKS = {"grasp_lift":
  (0.02, 0.60, 0.99), "place0"/"place1": (0.01,)}`, resolved against the leg's own
  `len(commands)`. The first pass used fixed ticks `(2, 8, 20)` and read a
  **constant** offset from tick 2 to 20 (`seat_accept_v1_fixedticks.log`): a
  158-181-tick lift's first 12 % is *before* the measured slip onset
  (`onset_row` 60-149 on the lift legs, this phase's `[carry]` rows), so it could
  not see the walk at all. Both first-pass logs are preserved as the evidence for
  that.
* **Neutrality** (`logs/p42/p2/identity.txt`): with the knob **unset** the tree
  reproduces the P41 record **376/376** `[fruit]` rows
  (`logs/p41/p3/accept_control.log`); with it **set** the acceptance reproduces
  its own knob-off control **376/376** and the pear **377/377** - i.e. the
  instrument changes nothing, not even the branch. `configs/motion_reference.json`
  gate on the knob-off control: `fingerprint: matches` (rate-only FAIL 6/10, the
  documented branch).

---

## 3. The freeze-time seat

`d = pads - fruit`, world mm; `|d_xy|` is the lateral magnitude. Both corpora are
`ATTEMPTS=10 SEED=5`; the pear battery is `FRUIT_SUPPLY_SPECIES=pear` (the
species-locked primary). Per-grip tables: `logs/p42/p2/seat_{accept,pear}_table.txt`.

**Acceptance (mixed supply, 6/10; 6 placed / 4 escape)**

| class | n | dx med [range] | dy med [range] | abs(xy) med [range] | dz med [range] |
|---|---|---|---|---|---|
| placed | 6 | **+0.75** [-0.40, +1.90] | **+1.80** [+1.40, +2.50] | **2.03** [1.62, 2.69] | +70.00 [+69.60, +71.20] |
| escape | 4 | **+0.85** [-0.30, +2.50] | **+2.10** [+1.70, +2.60] | **2.41** [1.82, 3.47] | +70.70 [+69.40, +71.20] |

**Pear (species-locked primary, 6/10; 6 placed / 4 escape - all four escapes left)**

| class | n | dx med [range] | dy med [range] | abs(xy) med [range] | dz med [range] |
|---|---|---|---|---|---|
| placed | 6 | **-0.50** [-1.60, +4.20] | **+1.70** [+0.80, +2.00] | **1.86** [1.73, 4.65] | +70.25 [+69.30, +71.40] |
| escape | 4 | **+1.20** [+1.00, +1.40] | **+1.05** [+0.80, +1.80] | **1.72** [1.36, 2.06] | +70.80 [+69.90, +71.70] |

Read: **x and y are centred to a couple of millimetres on every grip**, the
escapes are *not* the off-centre ones, and the only term with a systematic sign
is `dz`, identical in both classes and equal to the commanded standoff. The
tool-frame decomposition says the same thing: at the freeze `tilt` is 0.4-0.6 deg
and `tool = (+-2.8, +-2.5, -69.3..-71.7)` mm - the offset is **along the finger
axis**, which is the commanded standoff, not lateral drift.

---

## 4. The per-pad force split and the span-vs-command wedge

| corpus | class | asym at freeze med [range] | n (freeze) | `faces = sep - cmd` med [range] |
|---|---|---|---|---|
| acceptance | placed | **0.06** [0.01, 0.27] | 2/2 both pads | +12.5 [+7.4, +15.3] mm |
| acceptance | escape | **0.07** [0.01, 0.31] | 2/2 both pads | +5.6 [+5.1, +15.5] mm |
| pear | placed | **0.17** [0.05, 0.35] | 2/2 both pads | +8.6 [+7.8, +9.4] mm |
| pear | escape | **0.10** [0.04, 0.18] | 2/2 both pads | +9.85 [+7.6, +12.3] mm |

* **Balanced at the seat**: asym 0.01-0.35 (median 0.06-0.17) with both pads
  loaded on 20/20 grips;
  on the pear the escapes are *more* balanced than the placed legs (0.10 vs
  0.17). So the force-split asymmetry is **not** present at the freeze - it is a
  *later* phenomenon (§5).
* The measured span sits **5-16 mm wider than the frozen command** on every grip
  (the pads are force-limited at 10 N/joint, so the payload holds them off the
  commanded depth - the P41 §3 "7-14 mm wider than the frozen command"). This is
  a property of the hand, not of the outcome: the ranges overlap and the pear
  escapes sit 1.3 mm wider than its placed legs.

---

## 5. What actually moves: the drift, freeze -> place leg

`drift = d - d_freeze` (world mm) = **minus** the payload's displacement in the
hand frame; `k` is the sample ordinal within the grip (0 = freeze, 1-3 = the lift
at 2 % / 60 % / 99 % of its profile, 4 = the place leg's first ticks).
`n<2` = samples where fewer than two pads report contact.

**Pear (primary)**

| class | k | leg | n | drift_x med | drift_y med | drift_z med | abs(drift) med [range] | n<2 |
|---|---|---|---|---|---|---|---|---|
| placed | 1 | lift | 6 | +1.2 | +0.6 | -3.9 | **4.3** [2.8, 9.9] | 0/6 |
| placed | 2 | lift | 6 | -7.3 | +0.4 | -4.5 | **10.1** [8.0, 13.7] | 0/6 |
| placed | 3 | lift | 6 | -33.8 | +0.9 | -13.2 | **40.0** [27.9, 58.5] | 0/6 |
| placed | 4 | place | 6 | -36.5 | +0.9 | -15.7 | **46.4** [28.6, 73.8] | 0/6 |
| escape | 1 | lift | 4 | -0.1 | +2.5 | -5.0 | **6.4** [3.0, 8.8] | 0/4 |
| escape | 2 | lift | 4 | -3.5 | +9.1 | +1.2 | **13.3** [11.2, 128.1] | 1/4 |
| escape | 3 | lift | 4 | -39.0 | +44.2 | +185.9 | **194.8** [104.3, 276.0] | 4/4 |
| escape | 4 | place | 4 | -67.9 | +182.8 | +283.5 | **352.6** [302.7, 374.9] | 4/4 |

**Acceptance**

| class | k | abs(drift) med [range] | n<2 |
|---|---|---|---|
| placed | 1 | 4.0 [2.5, 4.6] | 0/6 |
| placed | 3 | 48.3 [33.0, 57.3] | 0/6 |
| placed | 4 | 58.2 [38.4, 74.0] | 0/6 |
| escape | 1 | 5.4 [3.2, 11.0] | 1/4 |
| escape | 3 | 104.2 [30.6, 259.4] | 3/4 |
| escape | 4 | 316.9 [36.5, 342.6] | 3/4 |

So:

1. **Every grip walks.** The first lift sample is a 2.5-9.9 mm relative move -
   almost all of it vertical (`drift_z` -2.5..-9.8 mm, the payload sagging into
   the jaw as the arm accelerates away) - and by the end of a *successful* lift
   the payload has moved **28-74 mm** in the hand. A 40-60 mm walk is survivable.
2. **The escape is that walk running away, not a new mechanism**: at k=3 the
   pear escapes are 104-276 mm and one (or both) pads have lost contact, and at
   k=4 the payload is 280-290 mm *below* the pads (`drift_z` +283..+288) - it has
   fallen out through the bottom of the jaw, which is exactly the loaded slide
   the P41/W8-B corpus describes. **Four of the pear's four escapes lose the grip
   inside the lift; on the acceptance three of four do and the fourth (attempt 1,
   peach) survives the lift (24.3 mm) and goes on the place leg's first ticks
   (`onset_row` 83, `force@onset` 10.10 N) - the same class, one leg later.**
3. **`clean_slip` confirms it from the other side** (`[carry]`, both corpora): on
   the pear escapes `grasp_lift` reads 129.5 / 165.0 / 266.4 / 285.2 mm with
   `onset_row` 60-127 of 158-163, and the *following* `place0` reads
   1258-1461 mm with `force@onset = 0.00 N` and `contacts@onset = 0` at rows 2-6 -
   the grip was already empty when the place leg started. The two pear escapes
   that were **placed** had `grasp_lift` 8.2 / 11.1 mm and `place0` 0.0 mm.
4. The **one-sided** state is a *late* marker, never a seat property: it occurs on
   18 of 32 escape carry samples and 0 of 48 placed ones, and the first
   occurrence is at k=1..3 (i.e. 3-160 ticks into a 160-tick lift), never at the
   freeze.

---

## 6. Does the offset predict the escape? No - and this is a measured null

Four candidate readings were tested against the data, and every one fails:

| candidate | test | result |
|---|---|---|
| lateral seat error | abs(xy) escape vs placed | pear **1.72 vs 1.86** mm medians (escapes *smaller*); acceptance 2.41 vs 2.03 (n = 4/6) - **no separation** |
| vertical seat (lip) | `dz` escape vs placed | pear +70.8 vs +70.2 (range overlap 0.2 mm); acceptance +70.7 vs +70.0 - **no separation**, and both equal the commanded standoff |
| force split at the seat | `asym` escape vs placed | pear **0.10 vs 0.17** (escapes *more balanced*); acceptance 0.07 vs 0.06 - **no separation**, and no grip is one-sided at the freeze |
| "the escaping grip is looser" | `sep - cmd` escape vs placed | pear +9.85 vs +8.60 mm, acceptance +5.55 vs +12.50 mm - overlaps in both directions - **no separation** |

The largest lateral offset anywhere in the 20 grips (+4.2, +2.0 mm) is a **placed
left pear**, and the four pear escapes are the four *tightest* lateral seats in
the corpus. The discriminating quantity is the payload's later displacement
(§5) and the contact count that follows it - i.e. the escape is a **dynamic
walk**, whose trigger is inside the lift, not a static seating error at the
freeze.

**Why the walk starts despite a centred seat** is not settled by this phase, but
the geometry names a candidate: the pads' distal stop is only ~10 mm below the
fruit's centre (`lip ≈ +10 mm`), so a 3-9 mm vertical sag at the lift's start
(measured, §5) consumes a third to most of the vertical margin, and the rest of
the walk runs off the end of the plate. The registered `FRUIT_SEAT_CENTRE` lever
does **not** address that axis (it is x/y only, and z is the commanded standoff;
the grip-plane drop that did address it, D2a, was measured negative in R8-A).

---

## 7. Limits

* **n**: 10 grips per corpus; the pear's escape population is 4 legs, and all
  four are **left-arm** (the pear battery's left attempt count). A per-arm
  comparison is therefore confounded with the species scenario - but the
  *within-left* read still holds (the two left pear *placements* sit at
  |d_xy| 1.84 and 4.65 vs the escapes' 1.36-2.06).
* **One branch each.** The two corpora are single deterministic branches of the
  instrumented configuration; the instrument is proven free (§2) but a *rate*
  would still need several runs. Nothing here is a rate.
* **The samples are five per grip**, so the walk is sampled, not tracked: the
  onset tick is known only from the independent `[carry]` `onset_row`.
* **The freeze offset is a post-close-command instant**: it is read on the tick
  the freeze commits, using the same tactile read the freeze criterion used, and
  the pads/fruit are read at that instant (one tick before that tick's physics
  step, like the criterion itself).
* The instrument is **scripted-scope only this phase**: the two-line scheduler
  and the direct/policy handover were not run with it, so no seat statement
  covers them.
* The place-leg sample is the **first ticks** of that leg, so the escape's final
  geometry (§5 k=4) is the transfer's start, not the release.

---

## 8. The runs, and the files

```
# batch 1 (controls + the fixed-tick first pass)
scripts/154_claim_run.sh logs/p42/p2/control_accept.log \
  ATTEMPTS=10 SEED=5 FRUIT_MOTION_REPORT=1  scripts/run.sh scripts/20_pick_place.py
  ... FRUIT_SEAT_DIAG=1                     -> seat_accept_v1_fixedticks.log
  ... FRUIT_SUPPLY_SPECIES=pear             -> pear_control.log
  ... + FRUIT_SEAT_DIAG=1                   -> seat_pear_v1_fixedticks.log
# batch 2 (the fraction schedule + the per-leg [carry] diag)
  ... FRUIT_SEAT_DIAG=1 FRUIT_CARRY_DIAG=1                                -> seat_accept.log
  ... FRUIT_SUPPLY_SPECIES=pear FRUIT_SEAT_DIAG=1 FRUIT_CARRY_DIAG=1      -> seat_pear.log
python3 logs/p42/p2/seat_parse.py logs/p42/p2/seat_{accept,pear}.log > logs/p42/p2/seat_{accept,pear}_table.txt
python3 logs/p42/p2/identity.py > logs/p42/p2/identity.txt
python3 scripts/105_motion_regression.py logs/p42/p2/control_accept.log --fingerprint configs/motion_reference.json
scripts/selfcheck.sh
```

Code: `src/fruit_sorting/tasks.py` **e34e0f58** (`_seat_read`/`_seat_arm` + the two
hooks + `SEAT_TICKS`/`SEAT_MAX_SAMPLES` + the knob), `src/fruit_sorting/rl_env.py`
**7c438ef7** (`TASKS_MD5` metadata-only follow; the `tasks.py` md5 was
**59b6dfdb** during batch 1 - the batch-2 change is the solve-schedule fix only,
and batch 1's runs are the control for it). `configs/*` untouched
(**8a399626** / **2246f83c**). Evidence `logs/p42/p2/`
(`control_accept`, `pear_control`, `seat_accept`, `seat_pear`, the two
`_v1_fixedticks` first-pass logs, `seat_{accept,pear}_table.txt`,
`identity.txt`, `seat_parse.py`, `identity.py`, `md5_{start,batch2}.txt`,
`batch1_driver.log`, `batch2_driver.log`), `logs/selfcheck.log`.
