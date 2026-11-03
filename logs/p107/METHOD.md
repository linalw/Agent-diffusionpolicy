# P107 method - the radial four-pad cage retrofit (M2b + M3)

Written 2026-11-03. **The owner's decision**: after P106's licence for the *shape*
(a radial/enveloping grasp, not a product), build that shape in simulation and run
the two milestones the plan reserves for it - **M2b** (does it *approach* a belt
fruit without batting it) and **M3** (does the scripted line run it). Default off,
a separate hand kind, `configs/` untouched.

* the plan: `docs/HAND_STAGE_PLAN.md` §5.2-§5.3 (M2b, M3) and §6 (the table);
* the licence: `logs/p104/RESULTS.md` (the 4-pad radial form clears 1.5x on both
  legs on every fruit: sustained **1.98 / 1.87 / 2.05x**, 2 mm **1.82 / 1.80 /
  2.10x**, creep **0.25 / 0.15 / 0.11 mm** against the pinch's **3.20 / 0.85 /
  2.68**) and `logs/p106/RESULTS.md` (the anthropomorphic 3+1 hand is a **2-3
  contact** grasp on a 37-66 mm payload at every posture in a 4x4 sweep);
* the class it has to answer: **a loaded slide along the tool axis**
  (`logs/p42/SIM_LIMIT.md`, P61/P75/P102), which more contacts + a lip resist and
  more *force* does not (P76), a re-grip does not (P103), a pre-pose does not
  (P96/P97, reverted).

---

## 1. What was built

`src/fruit_sorting/cage_hand.py` - **`FRUIT_GRIPPER_KIND=cage4`**, a fifth hand
kind beside `openarm` (shipped), `kinematic`, `actuated`. It is authored by
`scene.build` **before `play()`** (the contact-tracking flags its tactile readers
need have to exist before the physics views are built), and driven by
`tasks.PickAndPlaceTask` through the same hand interface the shipped hand uses -
`follow_centre(centre, quat, gap)`, `pad_centre()`, `pad_faces()` - so the grasp,
close, carry and release code is **unchanged**. Four consequences of that choice,
each of which had to be made explicit in `tasks.py`:

| what | how |
|---|---|
| the hand is **rigid on the tool** (there is no assisted "pad frame") | `RIGID_TOOL_HANDS = ("openarm", "cage4")`; the eight `kind == "openarm"` sites that meant "the pads ride the arm" now read `rigid_tool_hand(hand)`. The shipped hand is a *subset* of the new predicate, so its behaviour cannot move |
| the **tool offset** replaces `_pad_standoff` | `CageHand.grasp_standoff`, read by `_pad_standoff` and `_fingertip_offset`. It is **70.0 mm** - and it is *derived*, not copied: the plate's distal plane is at 80.5 mm below the jaw centre and the lip is 10.5 mm, so the payload's equator sits 70.0 mm below the jaw centre. The radial synergy does not move it (**measured spread 0.00 mm over 9 apertures**, §3) |
| the **close** is one scalar | the task's `gap` is the **aperture** (opposite-face distance); one number drives all four pads - the synergy |
| the **grip span** is the cage's, not the jaws' | `_hand_separation(side)` feeds `sep`, `sep@onset`, `sep@loss`, `sep_end` and the R6-B relief cap from `CageHand.separation()` (the four measured faces), so the diagnostics keep meaning "how far apart are the gripping faces" |
| the hand must **ride the arm every tick** | `CageHand.track_arm()`, called from `_step_sim` (two attribute reads when no such hand is active). The shipped OpenArm hand needs no such call because its fingers *are* the arm's links; without it the cage stays where the last `follow_centre` left it - measured as 5 fruit knocked off the belt and 2 starved slots (`smoke8.log`) |

**Geometry, all of it from the record and every cut measured (§3).**

| quantity | value | why |
|---|---|---|
| pads | **4** at 0/90/180/270 deg | the brief; P104's `quad` form |
| plate face | **26.000 x 60.000 mm** (from the shipped 61.000 x 84.902) | §2 iterations 1-2 |
| plate distal plane | **80.500 mm** below the jaw centre - *unchanged* | keeps the lip and the tool offset |
| lip | **10.5 mm** below the payload's equator - *unchanged* | the shipped pinch's own |
| aperture | **120.0 mm open -> 26.0 mm closed**, measured = commanded | §2 iteration 6 |
| closure | **one scalar**, four radial targets | the synergy |
| drive | k = 1e5 N/m, c = **100** Ns/m, cap **4.90 N/pad** | §2 iteration 4; P104's own near-critical pair |
| pad material | mu 2.0, restitution 0, no compliance | the shipped pads; PhysX averages the pair (P104) |
| tool offset | **70.00 mm**, constant | §3 |

## 2. The seven design iterations, all measured, all necessary

Built as "four instances of the shipped plate on the flange", the cage **destroyed
every payload** (69-1433 N per pad against a 4.9 N cap). Each iteration below is a
measured defect with the run that shows it; the order is the order they appeared.

1. **A 61 mm plate at 4 x 90 deg physically intersects below a 61 mm aperture.**
   Adjacent faces meet when the face radius equals the plate's half width
   (`pad_width <= aperture`). With *dynamic* pads they do not merely overlap - they
   **collide with each other**, jam the cage and crush the payload (69-100 N per
   pad; `smoke4.log`). **Cut the width to `2 x MIN_FACE_R` = 26 mm.** The Coulomb
   capacity `n * mu * N` is area-independent (P104 §2), so the licensed 4-contact
   number is unaffected - only the lip's *width* shrinks.
2. **The shipped plate's proximal end sits 4.4 mm *above* the jaw centre** -
   inside the hand it is bolted to. With dynamic pads that is a hard contact with
   the OpenArm's own palm: `|v|max` 20 m/s, `|a|max` 2421 m/s2, the payload
   ejected (`smoke5.log`). **Cut the length to 60 mm while keeping the distal plane
   at 80.5 mm** - which moves the proximal end to 20.5 mm below the jaw centre and
   changes neither the lip nor the tool offset.
3. **The OpenArm's finger plates keep their _asset_ colliders even with
   `FRUIT_FINGER_COLLIDERS=0`** (that flag only *adds* the flat faces). The cage's
   pads sit inside the fingers' volume and jam against them: 4.3-30.8 N per pad
   with the aperture **frozen at 89 mm** (`smoke6.log`). **Disable them** - the
   `KinematicGripper` recipe (an attribute override reaches the instanced asset
   where a new prim does not). *This is the single fix that first produced a
   hold* (`smoke7.log`: `grasped=True placed=True lift=+0.304 m`).
4. **The shipped fingers' drive damping (c = 2000 Ns/m) is numerically unstable
   for a 0.020 kg pad on a standalone prismatic joint at 120 Hz** - the cage's
   pads did not track their targets and put 90-100 N into the payload
   (`smoke3.log`). **c = 100**, which is P104's own default and its stated reason
   (`2*sqrt(k*m)` = 89 Ns/m for this pad) and therefore the exact pair that
   produced the licensed 1.87-2.05x.
5. **A hand mounted on the tool has to be on the tool every tick** (see the table
   above) - otherwise it parks at the previous grip pose, at belt height, in the
   supply's path.
6. **The open aperture has to swallow the line's pursuit error.** The arm reaches
   the *aim* to 8 mm, but the fruit can sit **24 mm off the cage's axis** when the
   descent starts (the shipped aim is a point hand's; its 98 mm jaws give ~14 mm
   of slack). A 90 mm aperture leaves 12 mm and the pads **hit the fruit on the way
   down** (`clr = -20.5 mm`, a 546 mm bat, `smoke9.log`). **120 mm**, which is 25
   mm of radial slack.
7. **A radial close must use the payload's widest horizontal extent**, not the
   two-jaw chord: with the chord (2 % inside one axis) the cage stops 2-4 mm wide
   on a non-round fruit, one or two pads load and the rest read zero
   (`pads=1/4`). `tasks.pinch_width` returns `max(extent(x), extent(y))` for a
   radial hand (`getattr(hand, "apertures")` - no shipped hand has it).

**Two things this mount cannot have, stated because they bound the result.** A
joint tree on a **teleported kinematic base** launches its dynamic children: the
first placement is a pose step of metres and the implied base velocity is hundreds
of m/s (measured: pad positions at 1e4-1e8 m). The fix used here is to **zero the
pads' velocities on a jump** (> 20 mm) and to park on the arm rather than at a far
home; the *proper* fix is an **articulation welded to the flange** (P106's Allegro
pattern), which is the named next step and is **not** in this phase. And the
closure is a **force-capped drive**, so the delivered force is the cap - but the
payload is trapped in a closed ring, so the *contact* force is whatever the
geometry needs when the fruit does not fit (§4).

## 3. The cells

All three cells are the **shipped scripted scenario** (`scripts/20_pick_place.py`,
`FRUIT_BIARM=0` so the hand, not the two-line scheduler, is the variable), one
claim per run, `FRUIT_CAGE_PROBE=1` **on every cage cell** so the arms are
compared inside one instrumented batch (the tree's own rule):

| cell | what | run |
|---|---|---|
| **M1** | the asset census: aperture vs command, the tool offset across 9 apertures, the pad-pad corner gap, the distal plane, the lip | `m1_cage.py` -> `m1_cage.txt` |
| **M2b** | **15 attempts, seed 5**: the approach-and-enclose census (no-contact, batting, enclosure, cage-vs-fruit clearance on the descent) | `m2b_s5.log` |
| **M3** | **10 attempts at the acceptance's two seeds, 5 and 6**, with the controls **on the same tree at the same seeds** (the shipped hand) | `m3_s5.log`, `m3_s6.log` vs `ctl_s5.log`, `ctl_s6.log` |

The census (`FRUIT_CAGE_PROBE=1`, default off) adds, per tick in the window
**one fruit-position read, one base-pose read and one tactile set** - the same
read class as P102's `[tactile]` instrument, which replayed 3,334 `[fruit]` lines
unchanged - and prints one row per attempt:

```
[cage] idx=.. arm=.. species=.. dia=..mm approach=..t clr=+..mm aper_min=..mm
       close=..t bat=+..mm bat_rel=+..mm pads=n/4 f=(..) F=..N aper=..mm no_contact=0|1
```

* `clr` = the closest **pad surface to payload surface** distance over the
  approach (the payload as the sphere proxy the tree already uses; positive =
  separated, negative = the face planes are inside the fruit);
* `bat` = the payload's displacement over the close window; `bat_rel` = that
  displacement **minus the belt's own travel**, i.e. the part the cage did
  (0.0 mm = the fruit rode the belt untouched);
* `pads` = how many of the four measured pad forces are above 0.5 N (the close's
  own contact threshold) - the **enclosure**;
* `no_contact` = none of the four is loaded.

## 4. What this can and cannot decide - before the numbers

**It can decide** whether this **retrofit** - four radial pads on the OpenArm's
tool point, closed by one scalar, driven through the shipped hand interface -
can *approach* a belt fruit and *carry* it on this cell. That is exactly M2b and
M3, and it is the only question this phase registers.

**It cannot decide**, and none of these is an execution defect:

1. **Whether a radial 4-contact hand is worth buying.** P104/P106 measured the
   *shape* on a fixture with the payload free to move and the pads on independent
   force-capped drives. This phase puts that shape on **this cell's aim**, and the
   answer is about the aim at least as much as about the pads.
2. **The delivered force.** The pads are force-capped at 4.90 N, but a payload
   inside a *closed ring* is statically indeterminate: when the fruit does not fit
   the aperture the solver resolves the constraint, and the measured per-pad force
   is 2-194 N (§5). The P104 fixture's `F_crit = n * mu * N` assumes the payload
   is free along the pull; a cage that closes *onto* the payload is not that
   experiment.
3. **A real hand's compliance, tactile or synergy mechanics.** The pads are rigid
   and adhesion-free (`logs/p42/SIM_LIMIT.md` §3), the closure is a position drive
   per pad, and there is no tactile in the loop.
4. **Anything about the two-line scheduler.** The cage is not run there; the
   `[biarm]` path refuses a non-`openarm` hand by construction
   (`tasks.py:9543`) and that refusal is untouched.
5. **The landing.** §5 says why: the M3 cells were not armed with
   `FRUIT_PLACE_TRACE`, so P86/P87's `on_belt` guard is **not measured** here.

## 5. Deviations, recorded not smoothed

* **The plate is cut twice** (26 x 60 mm from 61 x 84.9): §2 iterations 1-2, both
  forced by measurement. The **face geometry that matters is kept** (the distal
  plane, the lip, the mu, the thickness), and the capacity is area-independent.
* **The drive damping is 100, not the shipped fingers' 2000** (§2 iteration 4).
* **The M2b/M3 cells ran with the cage probe on** - all of them, so the cells are
  comparable to each other, but a cage count is *not* compared to a control count
  as if the instrumentation were identical (the control cells are the shipped
  hand without the probe). The no-harm proof is the acceptance replay (§5 of
  `RESULTS.md`), which is byte-identical.
* **The `[cage]` enclosure count is a lower bound.** The per-pad force comes from
  the tactile's `ContactSensor` path (the same one the tree uses), and one
  **placed** attempt reads `pads=0/4, F=0.00` (`m3_s6` attempt 2, lift +0.261 m) -
  a read that cannot be true. So `pads >= 3` is reported as "at least", never as
  an upper bound, and the *positive* rows are the trustworthy ones.
* **`[cage]` phase B (the M1 probe's pinned-fruit force cell) is not evaluable**:
  at the *static* `grasp` pose the jaw is only 52 mm above the belt top, so the
  cage's grasp centre (70 mm below the jaw) is 18 mm *inside* the belt and the
  pinned fruit is ejected. Recorded; the force question is answered by the
  pipeline rows instead.
