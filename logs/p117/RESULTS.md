# P117 results - the scene, fixture-first: the pad face and the friction are closed, the station pocket promotes

**VERDICT (first line).** The owner's new authorisation is "change the scene", and
this phase asks the record's three unspent scene candidates with **fixtures**, not
attempts. Two of them close and one promotes:

* **(1) The pad face: NO.** Four concave faces (`arc06`, `arc09`, `v90`, `cradle90`,
  the last one the only one with an axial normal) were built per fruit and measured
  at the shipped 4.90 N/face, and **none reduces the creep**: on the pear - the
  tree's cleanest escape fruit - they are **1.56-2.89x worse**, and every one is
  also **0.62-0.76x worse on the axial break-away** (0.62-0.76x, the opposite of
  P104's "more contacts" prediction). No promotion (`PREREG` A3).
* **(2) The pad's friction: the number rises, the class does not move.** Pad mu
  2 -> 3 -> 4 raises the static axial capacity **1.35-1.84x** (pear 9.78 -> 14.32
  -> 14.20 N; orange 13.33 -> 17.96 -> 23.33 N) and changes the creep by
  **-5 % to +23 %** (pear 8.62 -> 8.38 -> 8.21 mm). **`PREREG` A6 fires**: the creep
  is *not* friction-limited, so the friction lane is dead.
* **(3) The station pocket: YES, on its mechanics.** A 100 mm-deep drop-out pocket
  with a belt-like shutter holds **16/16** fruits with a **0.000-0.024 mm** hold,
  **0/16 expelled**, the shutter closes in **0.54-0.64 s** (inside the 0.833 s fast
  cadence), and the stream **passes 4/4 over the closed shutter at 1.00x the belt
  speed** at both cadences with **3/3 followers passing** while the occupant holds
  0.008-0.019 mm. It **promotes to a station build** - with two named gates
  (the reach at a 100 mm-lower pick pose, and the shutter's actuation path).

**And the phase corrects the record's own creep endpoint.** P104's "creep at the
operating load" (3.20 mm on the pear) is **entirely lateral** (`dx = -3.20`,
`dz = +0.02`): it is a **seat shift along the jaw axis, not a slide along the load**.
This fixture reproduces the shape (the load axis is `dz = -0.05..+0.28 mm` in **every
cell of the battery**, the total being lateral) - so at 1.66 N the payload does not
creep along the load in *any* configuration, and the class the cell loses is not a
static creep at all. That is consistent with P75's mechanism (the pry with the pads
at their 98.1 mm stop) and with P76/P78's finding that 60 N deletes the pry but not
the class.

**Nothing is adopted.** No `src/` change, no default change, no `configs/` edit, no
reference re-recorded, no commit of a shipped change. `PREREG.md` md5
**`5caae5d28c6ad5ae92a2977f89141596`**, pinned at 04:34:54Z before any cell.

---

## 0. What this phase is, and what the record already had

The brief's premise for candidates 1 and 2 is **wrong on one point and must be
recorded before the numbers**: the tree *has* the concave face and the pad friction
as knobs - `FRUIT_FINGER_FACE` (`v`/`h`/`x`/`c` additive, `v2`/`h2`/`x2` recessed,
`p` plate; `scene._add_contact_faces`) and `FRUIT_FINGER_MU` - and the
`logs/p3face` phase measured both. Read **against its own flat control** the
recessed `h2` is a **draw** (6/10 vs 6/10) and `v2`/`x2` are worse (3/10, 1/10);
against the later chosen `flat + k30` arm (7/10) all are worse. `FRUIT_FINGER_MU=8`
"re-ejected A4" (a *close* event, not a carry one). What that phase **never**
measured is the **creep at the operating load**, and its rate was taken at the
**pre-P41 force** (4.42 N delivered) and on the **single-arm dynamic catch**, not
the shipped two-line at 9.75-9.9 N. So this phase is a **re-test at the shipped
force with a different endpoint**, and the honest sentence is "measured negative
once on a rate, never on the creep", not "never tested".

For candidate 3 the record fixes the geometry before any build: the delivered x is
**0.188-0.397** (`logs/p49`, `p60`) and the top-down grip band is **x <= 0.320
clean, x = 0.398 fails at 32.8 mm residual / 17.0 deg** (`logs/p66/STATION_SWEEP.md`,
150 cells). A pocket *beside* the belt must be outside the delivered band to not
catch the stream, so it is **outside the pickable band**: the intersection is empty.
The only pocket that stays pickable is a pocket **under** the line - a drop-out
section - which is also the only form that gives the descent back the **40-90 mm**
it loses to the conveyor (`logs/166` 23 cm free vs `logs/167` 3.8 cm with the belt).
The diverter-siding form is therefore **refuted by arithmetic, not built**.

## 1. Fixture 1 - the support proof and the manipulation check

`fixture.py`, one app session, 28 pad pairs on one bench, 84 cells, **182 s** wall.

**A1 (support, gate).** Two dedicated zero-force cells:

| cell | what it proves | reading |
|---|---|---|
| weight-compensated, pads at cap 0, 200 ticks | the rig's read/seat is not the motion source | **0.000 mm** |
| no compensation, pads at cap 0, 40 ticks | the cell is not a frozen world | falls **613 mm** |

The first read is **exactly 0.0000 mm** once the 2-tick settle is excluded from the
window (the settle itself is 2.04 mm of free fall = the solver's semi-implicit
first steps; `smoke5.log`'s four-case matrix: no-force 27.25 mm, compensated 0.0000,
double-compensated +27.25, compensated-free -27.25 mm over 40 ticks). So the fixture's
pose read is exact and the *only* support in the real cells is the commanded clamp.

**A2 (manipulation, gate).** Every one of the 28 (profile x fruit) pairs loads
**2 pads**, each at **4.54-4.99 N** of the 4.90 N cap at the settle (`pads=2`,
`padN` in `p117_report.txt`) - i.e. every profile really is measured at the same
delivered normal force, not at the same span. That is what forced the **closure**
change: a groove is not a drop-in pad, the pads must close
`r - sqrt(r^2 - R^2)` deeper per pad (6.1 mm at `arc06`, 17.1 mm at `arc09` on the
60.6 mm pear; the fixture computes it from its own authored polyline,
`contact_travel`). Without it the groove grips **nothing** - the face never reaches
the fruit.

## 2. Fixture 1 - the pad table, and what it says

Medians of 3 repeats (`p117_report.py` -> `p117_report.txt`). `creep_g` = the
weight-only settle (P104's endpoint, 90 ticks), `creep_op` = the **total** walk from
the release to the end of the 0.75 s `m(g + 5.83)` hold, `dz` = its component along
the load axis, `Fexit` = the sustained axial break-away (applied + weight).

| profile | pear 60.6 mm | orange 65.8 | strawberry 37.2 | lychee 34.4 |
|---|---|---|---|---|
| `flat` creep_g | 4.31 | 4.53 | 0.48 | 6.21 |
| `flat` creep_op | **8.62** | **9.07** | **0.98** | **12.42** |
| `flat` Fexit | **9.78** | **13.33** | **13.24** | **11.06** |
| `arc06` creep_op / Fexit | 13.65 / 7.45 | 11.57 / 16.25 | 6.07 / 23.78 | 9.84 / 24.31 |
| `arc09` creep_op / Fexit | 16.63 / 6.32 | 15.58 / 19.29 | 12.75 / 19.40 | 5.76 / 14.56 |
| `v90` creep_op / Fexit | 24.90 / 6.11 | 14.26 / 16.25 | 5.60 / 14.36 | 16.33 / 13.81 |
| `cradle90` creep_op / Fexit | 13.43 / 6.86 | **6.57** / 13.58 | 9.76 / 12.78 | 17.08 / 11.73 |
| `flat_mu3` creep_op / Fexit | 8.38 / **14.32** | 9.22 / **17.96** | 12.97 / 18.03 | 15.29 / 16.35 |
| `flat_mu4` creep_op / Fexit | **8.21** / **14.20** | 9.34 / **23.33** | 8.10 / 20.74 | 14.01 / 20.31 |

Ratios to flat (creep / break-away), the promotion test:

| profile | pear | orange | strawberry | lychee |
|---|---|---|---|---|
| `arc06` | **1.58 / 0.76** | 1.28 / 1.22 | 6.19 / 1.80 | 0.79 / 2.20 |
| `arc09` | **1.93 / 0.65** | 1.72 / 1.45 | 13.01 / 1.47 | 0.46 / 1.32 |
| `v90` | **2.89 / 0.62** | 1.57 / 1.22 | 5.71 / 1.08 | 1.31 / 1.25 |
| `cradle90` | **1.56 / 0.70** | **0.72 / 1.02** | 9.96 / 0.97 | 1.38 / 1.06 |
| `flat_mu3` | 0.97 / **1.46** | 1.02 / **1.35** | 13.23 / 1.36 | 1.23 / 1.48 |
| `flat_mu4` | 0.95 / **1.45** | 1.03 / **1.75** | 8.27 / 1.57 | 1.13 / 1.84 |

* **No face profile is under 1.0 on the pear** - the cleanest, most deterministic
  fruit (all four `flat` cells and all four pear groove cells are bit-identical
  across repeats). The one cell that beats flat anywhere is `cradle90` on the
  orange (**0.72x**) and it is **1.56x worse on the pear**: a wash, and `A3`
  requires both.
* **The break-away says the same thing from the other side**: on the pear every
  groove is **0.62-0.76x** - a groove *weakens* the axial grip there, which is the
  opposite of the `n mu N` prediction. The grooves do help on the round fruit
  (orange/lychee 1.22-2.20x), i.e. the effect is fruit-shape-dependent, and the
  pear's lobes make a groove a wedge *out*.
* **The strawberry's ratios are not readable**: its flat base is **0.98 mm**, so
  6-13x is 6-13 mm on a fruit that moves < 1 mm in the control. Quote the absolute.
* **Repeatability/limits**: `flat` is bit-identical on all four fruits (8.62/9.07/
  0.98/12.42 x3); the grooves are bit-identical on the pear/orange and spread
  2-4x on the strawberry/lychee (`cradle90` strawberry 4.72-16.81 mm) - a bistable
  seat on the small fruits, the same class P104 §3 found on the lobed pear.
* **The mu ladder is monotone in the *capacity* and flat in the *creep***: pear
  9.78 -> 14.32 -> 14.20 N (+46 %/+45 %) against 8.62 -> 8.38 -> 8.21 mm (-2.8 %/
  -4.8 %). **`A6` fires**: `creep_op(mu4) = 0.95 x creep_op(mu2) > 0.5` and
  `creep_op(mu3) = 0.97 > 0.7`. **The creep is not a friction quantity.**

### 2.1 The correction: P104's creep is lateral, and the load-direction creep is ~0

`p117_report.txt`'s third table splits every cell into `dz` (the load axis) and the
lateral remainder. **`dz` is -0.05 to +0.28 mm in all 28 cells** - the entire
3-25 mm walk is lateral. P104's own row is the same shape: `settle=3.20mm
(dx=-3.20 dy=-0.02 dz=+0.02)` (`fixture.txt`, pear, `pinch_plate`), and its pads
close along **x** - so P104's headline 3.20 mm is a **shift along the jaw axis**, a
seat/centring motion, not the payload sliding down the tool axis under load.

**That is the phase's most transferable sentence: at the operating load the shipped
pinch does not creep along the load - it re-seats across it.** The class the cell
loses (`cnp`, 75 % of failures) is therefore not a static-creep deficit at 1.66 N;
it is the **dynamic** event P75 traced (the pads driven to their 98.1 mm stop while
the payload walks out), which is why P76/P78 could buy 1.45-1.84x of static capacity
and 2x of creep *ratio* without converting one `cnp`.

## 3. Fixture 2 - the station pocket

`fixture_station.py`: the shipped belt's own authoring (kinematic body +
`PhysxSurfaceVelocityAPI`, `belt_friction` 0.9, -0.120 m/s) split into two segments
with a **0.148 m** gap at the station; the gap is filled by a **shutter** that is
itself a belt-like kinematic body (a *static* plate would drag a fruit to a stop in
`v^2/(2 mu g)` = 0.6 mm - measured as "a static door cannot pass a stream"), and
under it a pocket floor with the shutter's underside as its ceiling constraint. The
shutter's **actuation path is not modelled** (it is teleported between the gap and a
park 2.4 m away, only when no fruit is within the clearance box); its **timing**, the
pocket's mechanics and the stream are.

Three build lessons are part of the result and each was measured:

1. **`PhysxSurfaceVelocityAPI` is in the collider's *scaled* local frame**
   (`conveyor._surface_attr_speed`): an un-divided command on a 0.726 m segment
   carried the fruit at **0.087 m/s** and on the 0.148 m shutter at **0.018 m/s**
   (`st_plate.log`). Divided by the box's y-length: **0.120 m/s = 1.00x**
   (`st_plate3.log`).
2. **The shutter must be flush**: `set_world_poses(z = bz)` put its top 20 mm below
   the belt top and stopped the stream dead (`st_plate2.log`, the fruit resting
   19 mm low). The authored pose is `belt_top - thickness/2`; the fixed cell reads
   **4/4 pass, v = 0.120**.
3. **The pocket's depth is forced by the shutter, not chosen**: the shutter must
   close *over* the occupant, so `depth >= shutter_thickness + max_diameter` =
   20 + 69.6 = **89.6 mm** → **100 mm**.

**B1 (support, gate) - a recorded deviation.** The registered 0.05 mm bar is **below
this sim's contact-jitter floor**: the pocket-floor drift is **0.364 / 0.261 / 0.518
/ 0.635 mm at 200/400/800/1200 ticks**, i.e. **non-monotone** - jitter, not creep -
and a fruit **riding the driven belt** deviates **0.018-0.382 mm** from a straight
line over the same window (the same-fruit control in the same session). P107/P112's
failure was a **2 mm sink + 4-5 mm monotone creep**, 5-8x this floor. So B1 is
judged **against the belt the line already uses** - the pocket is inside the belt's
own band - and the 0.05 mm bar is reported as unattainable on this physics. The
5.58 mm "settle" is the pear **rolling onto a flatter side** on the flat floor
(centre drop), not penetration.

**B2-B7 (the endpoints).**

| id | endpoint | reading | bar | verdict |
|---|---|---|---|---|
| B2 | the occupant's hold after the drop, 200 ticks | **0.000-0.024 mm** (16 drops), 0.008-0.019 mm (stream) | <= 1.0 mm | **PASS** |
| B3 | expulsion, 16 pool fruits | **16/16 in the pocket, 0 expelled** | 0/16 | **PASS** |
| B4 | the stream over the **closed** shutter, 4 fruit | **4/4 pass at 1.875 s AND 4/4 at 0.833 s**, v = **0.120 m/s = 1.00x**, belt jitter 0.018-0.382 mm | 4/4 | **PASS** |
| B5 | one drop + 3 followers | **3/3 pass at both cadences**, the occupant holds 0.019 / 0.008 mm | 3/3 | **PASS** |
| B6 | the shutter's contact force on the occupant | **0.00 N** (the mouth is open before the fruit arrives) | <= 10 N | **PASS** |
| B7 | the landing's x spread (reported) | **-58.7..+29.5 mm, span 88.2 mm** | - | **reported** |

The pocket's landing also gives `y -49.9..+41.0` mm and `z -69.4..-87.6` mm (i.e. a
100 mm-deep pocket whose occupant sits ~70-88 mm below the belt top), and the
shutter's **open window 0.54-0.64 s** against the **0.833 s** fast cadence - a
0.19-0.29 s margin, measured.

**What B7 means:** the pocket's mouth is 0.352 m wide in x, so it does **not** centre
the fruit: the landing x spans the delivered band. So the pocket removes the *moving
handover* and the *descent's blocked boundary*, but **not** P48/P49's delivered-x
tail. A centring floor (a V) is the named next element; it is not built.

## 4. What promotes, and what it does not license

**The pad face and the pad friction do not promote.** `A3` fails (no profile under
1.0 on the pear; the best cell is a wash), and `A6` fires (mu moves the capacity
1.45-1.84x and the creep 5 %). No battery, no `FRUIT_PAD_PROFILE`, no
`FRUIT_PAD_FRICTION`: the shipped knobs (`FRUIT_FINGER_FACE`, `FRUIT_FINGER_MU`)
already exist and the fixture says neither is the lever. **Read the two together**:
a 1.45-1.84x static-capacity gain that moves the creep by 5 % is the same
"capacity is 10-20x the demand" statement P104 made, measured again on the
friction axis.

**The station pocket promotes to a build, with two gates named:**

1. **The reach at the new pick pose.** The pick moves from the fruit's centre
   `belt_top + r` to `belt_top - 0.100 + r` (a 100 mm lower jaw) at the *same* x/y
   band. That is a **static IK probe** (`logs/p66/station_map.py`'s machinery, the
   pocket's centre as the target, the T0/C0/NAT modes) - **not spent**. The
   geometry is favourable (the jaw lands at ~`belt_top` for a 60 mm fruit, and the
   pads' distal plane at `floor + 0.5 mm`), but it is unmeasured.
2. **The shutter's actuation.** A 0.148 m belt-like plate that leaves and returns
   in 0.54-0.64 s needs a real mechanism (a drop-out section on a linear actuator);
   the fixture teleports it. The *timing* is measured, the *mechanism* is not.

**What the pocket buys, priced from the record:** the descent's 40-90 mm shortfall
goes to ~0 (the hand's plates reach the pocket floor instead of stopping on the
belt), the handover target is **stationary** (the acquisition class is
`dy 55.8 mm` against a 6 mm tolerance, `logs/p108`), and the pick pose is
**inside** the reach band by construction. **What it costs**: a cut belt, a shutter
actuator, a 100 mm-deep pit, and a re-calibrated pick pose - a **scenario change**,
which by this file's own rule owes both motion references, every store and the
acceptance re-baseline. **Not built in this phase.**

## 5. Deviations, recorded not re-read

* **A1 (fixture 1, support).** The registered "cap 0 + compensated weight, drift
  <= 0.05 mm" is met **only when the velocity is pinned each tick** (0.0000 mm);
  a *free* body under a compensated weight drifts 27.25 mm/40 ticks (a 1-tick
  application lag), and the 2.04 mm pre-roll was initially counted. The support
  proof is therefore: a **2-tick settle excluded**, the velocity pinned, 200 ticks,
  **0.000 mm**, plus the uncompensated control falling 613 mm (`smoke5`-`smoke7`).
* **A2 (fixture 1, the creep's definition).** `creep_op` is the **total** from the
  release to the end of the loaded hold, not the loaded phase alone. The smoke on
  the pear showed why: `arc06` walks **13.63 mm during the settle** and **0.03 mm**
  afterwards, so a sequential read would have promoted it spuriously
  (`smoke10.log`). This is a pre-battery fix; the battery was run after it.
* **A3 (fixture 1, the closure).** Each groove cell is closed `+INTERFERENCE` past
  its **computed** first contact, i.e. 6.0-19.2 mm deeper than the flat target. A
  groove measured at the flat closure grips nothing - the finding, not a defect.
  `arc09` on the 34-37 mm fruits closes to a **2.7-4.9 mm face span** - the pads'
  faces nearly touch, i.e. the pads envelop the fruit out to its equator. The joint
  range allows it and the finger bodies sit *behind* their faces, so it is
  realisable; it is simply the extreme end of the closure cost and it is the worst
  cell on the strawberry. Reported, not excluded.
* **B1 (fixture 2, support).** Above - the 0.05 mm bar is under the jitter floor.
* **B2 (fixture 2, the form).** The brief's "a diverter takes one fruit into a
  pocket beside it" is replaced by a **drop-out section under the line**, because
  the delivered band (0.188-0.397) and the top-down band (<= 0.320 clean) do not
  intersect outside it (§0). The diverter form is refuted by that arithmetic.
* **B3 (fixture 2, the shutter).** Its actuation path is a teleport; only its
  timing and its surface are measured.

## 6. Files, pins, and what was not run

**Files** (`logs/p117/`): `PREREG.md` (**5caae5d2**), `PREREG.md5`,
`fixture.py`, `fixture_station.py`, `p117_report.py` -> `p117_report.txt`,
`run_p117.sh`, `METHOD.md`, `RESULTS.md`; the logs `fixture1.log` (84 rows),
`smoke5..10.log` (the support/diagnostic path), `st_support2.log`,
`st_closed4.log`, `st_closed_fast.log`, `st_drop2.log`, `st_stream.log`,
`st_plate3.log` (the shutter's transport), and the **rejected** cells
`st_plate{,2}.log` (the two build defects, kept as the evidence for §3's lessons
1-2) and `st_drop{,2}_diag.log` (the 420-tick window that never reached the mouth,
and the debugging cell) - `p117_report.py` reads a **pinned** file list, so a
rejected cell cannot leak into a table.

**Tree pins (unchanged - this phase is `logs/`-only):** `tasks.py` `9e3e657b`,
`rl_env.py` `bf4c56fa`, `bimanual.py` `9b7fc33f`, `fruits.py` `dcabe16b`,
`scene.py` `a0199097`, `cage_hand.py` `ac7c7c0f`; `configs/motion_reference.json` =
`..._twoline.json` = **`30fb99f8`**, `..._single.json` = **`8952c320`**;
checkpoint `moe_v13s` `61da390a`. `git status --short src configs` is empty.

**Run.** `bash logs/p117/run_p117.sh` (fixture 1: one session, 182 s; fixture 2:
five sessions, ~2 min); `python3 logs/p117/p117_report.py`;
`scripts/selfcheck.sh`; `scripts/accept.sh`; `106`; `107`.

**No-harm, measured.** `scripts/accept.sh` with every knob unset reads **8/10,
9.0 s/attempt, `fingerprint: matches configs/motion_reference.json`, `190: PASS`**
(`accept_final.log`), and its **421 `[fruit]` lines are 421/421 byte-identical** to
`logs/p110/accept_noharm.log`; `scripts/selfcheck.sh` **PASS (0 failures, 1
skipped)**, `106` **OK**, `107` **PASS (21 checks)**.

**Not run, deliberately.** No arm, no attempt loop, no scheduler, no policy: both
fixtures are offline by design. No `configs/` re-record (nothing shipped), no
`190` two-line gate, no recollection, no `FRUIT_PAD_PROFILE` (no promotion), and
no station build (a scenario change, gated on §4's two items).
