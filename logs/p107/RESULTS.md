# P107 results - the radial four-pad cage retrofit: built, measured, and M3 fails

**VERDICT (first line).** The cage is **built, mounted and measured, and M3's kill
fires**: on the shipped scripted cell it places **2/10 at seed 5** and **1/7 at
seed 6** against the **same-tree, same-seed shipped-hand controls' 6/9 and 7/9**
(pooled **3/17 = 17.6 % against 13/18 = 72.2 %**), and its carry legs are the
**no-contact / ejection** class (`force_min == 0` on **29 of 43** legs,
`clean_slip > 100 mm` on the same 29, median slip **407-614 mm**) where the
shipped hand's failures are the closed loaded slide. **M2b's letter passes and its
mechanism fails**: the no-contact rate is **1/15** (the plan's `<= 1/15`, so the
kill does **not** fire and M3 was licensed), but the **enclosure is 2/15 at >= 3
pads** against the ">= 3 expected by construction", the payload is displaced
**15.1-106.9 mm** relative to the belt on 7/15 closes, and the **cage-vs-fruit
clearance on the descent is negative on 7/15** (`-0.3` to **`-33.4 mm`**) - i.e.
the face planes go **through** the fruit rather than around it. The asset itself
is exact: **aperture 120.0 -> 26.0 mm measured = commanded, tool offset 70.00 mm
with a 0.00 mm spread over 9 apertures, 4 pads, one scalar closure**, the shipped
lip (10.5 mm) and distal plane (80.5 mm) intact, the drive at its **4.90 N/pad**
cap (median delivered 4.90 N).

**So the retrofit does not answer the loaded slide on this cell, and the reason is
the aim, not the pad.** The number that decides it: the cage's face planes sit
**45-60 mm** from its axis while the fruit can enter the descent **24 mm** off
that axis, so the open cage must be **>= 2 x (24 + 35) = 118 mm** wide to swallow
the pursuit error - which is why the aperture is 120 mm - and a 120 mm cage on a
supply whose along-belt spacing is **85-120 mm** is already touching its
neighbours. **A radial cage needs a centring step before the descent, or a
workstation where the fruit is presented to it; neither is a pad.**

---

## 0. The asset (M1, `m1_cage.txt`)

One deterministic probe, no attempt loop, no belt: the cage on the calibrated
`grasp` pose, nine apertures, the measured face geometry off the built prims.

| quantity | measured |
|---|---|
| pad count | **4**, at 0/90/180/270 deg around the tool axis |
| plate face | **26.000 x 60.000 mm** (the shipped 61.000 x 84.902 cut twice, §2 of `METHOD.md`; the distal plane, the lip, the thickness and the mu are the shipped ones) |
| aperture: command -> measured | 120 -> **120.0**, 80 -> **80.0**, 70 -> **70.0**, 60 -> **60.0**, 45 -> **45.0**, 36 -> **36.0**, 30 -> **30.0** mm, on **both** axes (`0.0 mm` error; a command above the open aperture clips to it) |
| closure | **one scalar** -> four radial targets; the four pads' radii are equal to 0.1 mm at every rung |
| **tool offset** (replaces `_pad_standoff`) | **70.00 mm**, and **spread 0.00 mm** across the nine apertures - the radial synergy does not move it. This is the number P106 could not have on the Allegro (its fingertip centroid read **100-216 mm** across a posture sweep) |
| plate distal plane | **80.500 mm** below the jaw centre (unchanged) |
| lip below the payload's equator | **10.5 mm** (unchanged) |
| pad-pad corner gap | **+66.5 mm** open -> **+2.8 mm** at a 30 mm aperture: **no self-intersection anywhere** (the 61 mm plate intersected below 61 mm - `METHOD.md` iteration 1) |
| drive | k = 1e5 N/m, c = 100 Ns/m, **cap 4.90 N/pad**; delivered per-pad force median **4.90 N** over the 48 loaded pad-ticks of §3, max **87.85 N** (only where the fruit does not fit the closed ring) |

**The two geometric facts the design has to live with**, both measured here and
both about the *real* hand, not the sim:

* **A 4 x 90 deg cage needs `pad width <= aperture`.** Four plates of half-width
  `w/2` meet at the corners when the face radius equals `w/2`. The shipped 61 mm
  plate is therefore legal only above a 61 mm aperture - i.e. for the pool's two
  largest classes - and with dynamic pads it does not merely overlap, it jams.
  The width is cut to 26 mm (the smallest aperture's own width). The **capacity is
  unaffected**: `F_crit = n * mu * N` is area-independent (P104 §2), so the
  licensed 4-contact number is about the count, not the plate.
* **The plate's axial length is bounded above by the hand it is bolted to.** The
  shipped 84.9 mm plate puts its proximal end **4.4 mm above** the jaw centre,
  inside the OpenArm's palm; cutting it to 60 mm keeps the distal plane at 80.5 mm
  (so the lip and the tool offset are untouched) and moves the proximal end to
  20.5 mm below the jaw centre.

## 1. M2b - the approach and the enclose (15 attempts, seed 5, `m2b_s5.log`)

`ATTEMPTS=15 SEED=5`, the shipped scattered supply, one claim, the census on.
`table.txt` is the per-attempt table; the summary:

| endpoint | bar | measured |
|---|---|---|
| **no-contact** (no pad >= 0.5 N at the close's end) | **<= 1/15** | **1/15** - the kill does **not** fire |
| **batting** (payload displacement relative to the belt over the close) | recorded | **0.0 mm on 7/15** (the fruit rode the belt untouched) against **+15.1 to +106.9 mm on 7/15** |
| **enclosure** (pads >= 0.5 N) | **>= 3 expected by construction** | **>= 3 on 2/15**; 2 on 4/15, 1 on 7/15, 0 on 1/15, and one attempt without a census row (a lower bound, `METHOD.md` §5) |
| **cage-vs-fruit clearance on the descent** (surface to surface) | recorded | **-33.4 to +65.3 mm, median -0.3 mm**: the face planes go **through** the fruit's sphere on 7/15 descents |
| placed | - | **2/15** |

**The mechanism is the clearance row, and the no-contact test cannot see it.** An
attempt whose cage closes *through* the fruit still loads a pad, so it is not a
"no contact" - and it still fails, because the pad arrives beside the fruit rather
than around it. That is why M2b's letter passes at 1/15 while the enclosure is
2/15 and the payload is displaced on 7/15: **the endpoint the plan registered
(count of completely unloaded closes) is satisfied by a cage that misses.**

## 2. M3 - the scripted pick-and-place (10 attempts, seeds 5 and 6)

The acceptance's two seeds, the single-arm scenario, the controls on the **same
tree at the same seeds with the shipped `openarm` hand** (no probe):

| cell | attempts (slots) | placed | rate | s/attempt |
|---|---|---|---|---|
| cage, seed 5 | 10 | **2** | **20 %** | 15.3 |
| cage, seed 6 | 7 (3 slots starved) | **1** | **14 %** | 15.9 |
| **cage, pooled** | **17** | **3** | **17.6 %** | 15.6 |
| control, seed 5 (shipped hand) | 9 | **6** | **67 %** | 14.8 |
| control, seed 6 (shipped hand) | 9 | **7** | **78 %** | 14.3 |
| **control, pooled** | **18** | **13** | **72.2 %** | 14.6 |

* **The class is the whole answer.** Every cage carry leg (43 legs over the three
  cells) is scored: **`force_min == 0` on 29**, **`clean_slip > 100 mm` on the same
  29**, median `clean_slip` **407-614 mm**, max 1575-2468 mm. The shipped hand's
  failures are the *closed* loaded slide on a *held* payload (P42's class); the
  cage's are payloads it never had: the pads close into the fruit's side, or the
  fruit is pushed out of the cage during the descent (the 7 negatives in §1).
  The one class the retrofit was supposed to answer - the loaded slide *of a held
  payload* - is **not reached**: it cannot hold long enough to slide.
* **Budgets**: 2 over-budget descents of 20 (seed 5), 1 of 14 (seed 5 M3), 1 of 9
  (seed 6), all at **1.1x** (0.160-0.167 against 0.160-0.161) - P93's measured
  "stochastic branch property at ~2.5 % of legs in either arm", **not re-tuned**.
  The worst *held-grip* cone is **12.00x / 10.09x / 11.25x**, reported not gated
  (the dynamic line's rule) - and they are the legs where the cage is dragging a
  payload it has already lost.
* **The interval is not estimable** at 3 placements; `s/attempt` is the clock
  (the cage is **+0.5 s** at seed 5 and **+1.6 s** at seed 6, which is the arm
  fighting the cage, not the hand's speed).
* **The landing is not measured**: the M3 cells were not armed with
  `FRUIT_PLACE_TRACE`, so P86/P87's `on_belt` guard has no row. Named as a gap,
  not reported as clean.
* **The kill fires**: the plan's M3 bar is "the acceptance is not worse than the
  shipped 8/10"; the cage reads **1-2 of 10** and cannot match even its own
  scenario's shipped-hand control at the same seed (**6/9 and 7/9**). Per §5.3,
  **the hand cannot run this cell**.

## 3. What killed it - seven iterations, in the order they were measured

The full record is `METHOD.md` §2; the numbers, because each is a *finding* and
not a bug report:

1. **61 mm plates at 4 x 90 deg collide below a 61 mm aperture**: with dynamic
   pads, **69-100 N/pad against a 4.9 N cap**, the cage jammed (`smoke4.log`).
   Width cut to 26 mm.
2. **The shipped 84.9 mm plate's proximal end is 4.4 mm above the jaw centre**,
   i.e. inside the OpenArm's palm: **`|a|max` 2421 m/s2, `|v|max` 20 m/s**, the
   payload ejected (`smoke5.log`). Length cut to 60 mm, distal plane unchanged.
3. **The OpenArm's fingers keep their asset colliders** even with
   `FRUIT_FINGER_COLLIDERS=0`: the pads jam against them with the aperture
   **frozen at 89 mm** (4.3-30.8 N/pad, `smoke6.log`). Disabled (the
   `KinematicGripper` recipe). **This is the fix that first produced a hold**
   (`smoke7.log`: `grasped=True placed=True lift=+0.304 m`).
4. **`c = 2000 Ns/m` is numerically unstable for a 0.020 kg pad on a standalone
   prismatic joint at 120 Hz** - the pads did not track and put 90-100 N into the
   payload (`smoke3.log`). `c = 100` = P104's own near-critical value
   (`2*sqrt(k*m)` = 89), i.e. the pair that produced the licensed 1.87-2.05x.
5. **A hand on the tool must ride the arm every tick**: without it the cage parks
   at the previous grip pose, at belt height, in the supply's path - **5 fruit
   knocked off the belt, 2 starved slots** (`smoke8.log`).
6. **The open aperture must swallow the pursuit error**: 90 mm leaves 12 mm
   against a **24 mm** offset, and the pads hit the fruit on the way down
   (`clr = -20.5 mm`, a **546 mm** bat, `smoke9.log`). 120 mm.
7. **A radial close must use the payload's widest horizontal extent**, not the
   two-jaw chord: with the chord, 1-2 pads load and the rest read zero.

**All seven are in the shipped opt-in build.** The residue after all seven is
§1-§2: the cage still arrives beside the fruit on ~half the descents.

## 4. The honest frame - what this licenses and what it does not

**It does not license a hardware purchase, and it does not withdraw P104's
number.** P104/P106 measured the **shape** on a fixture where the payload is free
along the pull and the pads are independent force-capped drives: `F_crit = n mu N`
is a **friction count**, and 4 contacts still give 2x a 2-contact pinch. What P107
adds is the **integration** measurement: **that shape, placed on this cell's aim,
does not enclose a belt fruit**.

**The blocker is quantified and it is not the pad.** Three numbers, all measured
here:

* the pursuit error is **~24 mm** lateral at the descent's start (the shipped aim
  is a point hand's; its 98 mm jaws give ~14 mm of slack - the cage's 120 mm
  aperture gives 25 mm, which is why 120 works and 90 does not);
* a **120 mm** cage is the largest the supply allows: the along-belt spacing is
  **85-120 mm** (v9's `0.10-0.35 m` gaps with 0.085-0.12 m pair separation), so a
  wider cage touches its neighbours;
* the cage's own geometry needs `pad width <= aperture`, so widening the cage
  widens the pads, which then cannot close on a 37 mm strawberry.

**The named next spend is therefore a *centring* step, not a hand**: the tree
already has the machinery for a lateral servo before the close
(`_dynamic_grip_target` / `FRUIT_DYNAMIC_X_TRACK_*` / the x-lock), and a cage whose
axis is brought onto the fruit before the descent would not need a 120 mm
aperture at all. Alternatively a **workstation** where the fruit is presented in a
nest or the belt is cut away, which is the same family as P69/P70's station work.
Either is a registration of its own; neither is a pad and neither is a purchase.

**What the phase does ship.** A default-off fifth hand kind (`cage4`) that is
proven inert on every other path: the shipped two-line acceptance reads
**8/10, 9.0 s/attempt, `fingerprint: matches`**, and its **421 `[fruit]` lines are
421/421 byte-identical** to `logs/p103/accept_final.log`. The seven iterations
above are the retrofit's design record, and the three instruments (the `[cage]`
census, the M1 geometry probe, the per-attempt table) are reusable by the next
hand.

## 5. No-harm

* `scripts/accept.sh` with `FRUIT_GRIPPER_KIND` unset: **8/10, 9.0 s/attempt,
  `fingerprint: matches configs/motion_reference.json`, `190: PASS`**, and the
  `[fruit]` stream is **421/421 byte-identical** to `logs/p103/accept_final.log`
  (`logs/p107/accept_noharm.log` vs `logs/p103/accept_final.log`) - so the
  `openarm` line, its colliders, its drives and its manifests are untouched.
* `configs/` untouched: `motion_reference.json` = `motion_reference_twoline.json`
  = **`30fb99f8`**, `motion_reference_single.json` = **`8952c320`**. No reference
  re-recorded and none owed: the cage is opt-in and the scripted controls replay
  the record.
* `scripts/selfcheck.sh` **PASS** (0 failures, 1 skipped) - the phase adds no
  selfcheck leg (no new default, no new manifest field).
* The cage is **default off** (`FRUIT_GRIPPER_KIND` unset -> `openarm`) and the
  two-line scheduler refuses a non-`openarm` hand by construction
  (`tasks.py:9543`), so the shipped acceptance cannot reach it.

## 6. Pins and the two re-pinned guards

`cage_hand.py` (new), `tasks.py` (the `RIGID_TOOL_HANDS` predicate, `_pad_standoff`,
`_fingertip_offset`, `_hand_separation`, `pinch_width`'s radial branch, the
`track_arm` hook and the `[cage]` census), `scene.py` (the build-time authoring),
`tactile.py` (the four pad readers). `configs/*` untouched.

**Four guards had to move, and only their text did** - `scripts/selfcheck.sh` was
**PASS (0 failures, 1 skipped)** on the final tree:

* `rl_env.TASKS_MD5` `9e3e657b` -> **`d341b0da`** (the metadata-only follow the
  tree's convention requires; the block records why nothing on this env's path
  moves);
* `scripts/236_p66_lift_selftest.py` - the `jaw_target` clearance add is now
  behind `rigid_tool_hand(...)` instead of a literal `== "openarm"`; the shipped
  hand is a **subset** of that predicate, so "unset falls through to the shipped
  add" is the same invariant;
* `scripts/241_p75_place_trace_selftest.py` and `scripts/243_p76_sep_selftest.py`
  - the span reader is `self._hand_separation(arm.spec.side)`, which returns
  `arms[side].jaw_separation()` for **every shipped hand**, so both "the block
  reads the measured span explicitly" and "sep@onset/sep@loss use the same call"
  keep their meaning.

`scripts/selfcheck.sh` on the final tree: **PASS (0 failures, 1 skipped)**.
**Evidence**:
`logs/p107/{METHOD.md,RESULTS.md,m1_cage.py,m1_cage.txt,p107_report.py,table.txt,
m2b_s5.log,m3_s5.log,m3_s6.log,ctl_s5.log,ctl_s6.log,accept_noharm.log,
accept_noharm.driver,smoke1..10.log}`.
