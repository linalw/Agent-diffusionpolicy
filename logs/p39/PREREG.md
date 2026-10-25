# P39 PREREG — the finger tip (`delta`) and the lift-only wrist hold

Registered 2026-10-25, **before any asset or `tasks.py` edit**, on the
P38-final tree `e061d94` (`tasks.py` `cdde6bd2`, `scene.py` `ab85dca2`,
`assets.py` `61baf52b`, `kinematic_gripper.py` `e40b1ca2`; working tree clean).
Companion: `logs/p39/P1_READ.md` (the diagnosis), `01_left_corpus.txt`,
`02_finger_geometry.txt`, `03_prepose_audit.txt`.

Everything here is a **scripted-line** measurement. Neither lever touches the
direct/policy interface, no checkpoint or store is read, and both levers stay
**default off**.

---

## 0. The two levers, as phase 1 re-specifies them

| # | knob | form | scope |
| --- | --- | --- | --- |
| **L1** | `FRUIT_FINGER_TIP_DELTA=<m>` (`scene.py`, signed, default `0`) | disable the four finger links' shipped mesh colliders and re-author each plate as a convex box on the same face plane, the same across width, the distal plane at `tip_coord + delta` | all four links (a hardware change; it cannot be left-only) |
| **L2** | `FRUIT_CARRY_HOLD_QUAT=1` + `FRUIT_CARRY_HOLD_QUAT_LEGS=grasp_lift` + `FRUIT_CARRY_HOLD_QUAT_ARM=left` (`tasks.py`, default off) | pin the wrist at the grip attitude through the **lift** leg only (the shipped form holds it through the place too, and that is measured negative, `logs/444`) | the left arm's lift legs, **inactive on a two-line session** (so the two-line is a byte-identity prediction rather than a burden) |

**Arms.**

| arm | setting | what it is |
| --- | --- | --- |
| **C** | shipped, both knobs unset | the same-batch control; its numbers must reproduce `01_left_corpus.txt`'s pins |
| **F1** | `FRUIT_FINGER_TIP_DELTA=-0.004` | the brief's **short tip**: contact-neutral by the algebra (the patch stays intact), +4 mm of belt clearance |
| **F2** | `FRUIT_FINGER_TIP_DELTA=+0.004` | the **lip** form (the mechanism-derived direction); **owner-gated** - see §6 |
| **W** | the lift-only wrist hold | the replacement for the ported pre-pose, which does not exist (`03_prepose_audit.txt`) |

F1 and F2 are separate arms, not a sweep: F1 is the one-bit lip test and the
hardware/clearance form; F2 is the class arm. Neither is a fallback for the
other.

---

## 1. Endpoints

Per AGENTS §2 the scripted outcome is **quantized**, so the count is a branch
label and the *class* is the object. Every endpoint below is a count on a fixed
attempt set, not a rate.

### 1.1 Primary — the left's composite failure mass

**`cnp + no-grasp` on the left, over the two batteries of record** (the
acceptance, 10 attempts; the species-locked pear battery, 18 attempts - the
`90` + `91` protocol). Control values from `01_left_corpus.txt`: acceptance left
5 attempts (1 placed / 3 cnp / 1 no-grasp) or 3 (0 / 3 / 0) depending on the
profile, pear battery left 8 attempts (2 / 6 / 0).

**PASS** = the left's composite falls by **>= 2** on the acceptance **and** by
**>= 3** on the pear battery, **and** no new failure reason appears in either
arm (a note string absent from the control's set), **and** the left's `placed`
count rises by at least the composite's fall (no class relocation).

Why the composite and not cnp alone: the two-line lead shows a cnp-only endpoint
passing a relocation - it reads 0/10 cnp and still places 6/10, because 4/10
became no-grasp (`logs/p33/51_phase2_read.md` §1.2). That is exactly the trap
this endpoint exists to refuse.

### 1.2 Secondary — the frame-free band

The count of **left carry legs with `in-hand |v|max > 0.34 m/s`** falls by >= 2.
The bands do not overlap (placed `grasp_lift` 0.041-0.300, cnp 0.343-2.022; place
0.069-0.182 vs 0.447-2.035), so the count is the same statement as the class
census read from the other side - it says *which mechanism moved*, and it is
frame-free (no `[carry]` row exists on this line, and `slip_max` must not be
quoted, W8-B §1).

### 1.3 Mechanism readout (reported, not gated)

* the left's `grasp_lift` distance/ticks and the place distance/ticks
  (`[motion] carry` lead-ins) - the §1.4 correlate, so a null can be attributed;
* the `[motion] carry ... clearance: lowest payload point <x> mm to the <obj>`
  rows on every leg - the *physical* witness of the outcome (11 of the 12
  instrumented failures read `-215..-219 mm` **to the output rail**, the twelfth
  `-11 mm` to the main belt, and in all 12 the payload is on the main belt at
  the place-leg end; the placements read `+24..+89 mm`, P33 §2.1);
* the post-release force-servo `F_min` - `0.00 N` on 15/15 cnp legs and
  2.40-4.38 N on 31/31 placed, so it labels the class but cannot test the lever;
* **L1 only:** the tilt of the tool axis at each carry leg's end, from a new
  default-off `[attitude]` print (one read of the `quat` the leg already holds -
  pure reporting, no per-tick work). This is the *only* way to know the lip the
  arm actually achieved: `L` is 58.6-76.8 mm depending on the wrist, so the lip
  is -11.4..+6.8 mm and a `delta` claim without a measured tilt is unfalsifiable.

---

## 2. No-harm (all-or-nothing, every arm)

| # | condition | instrument |
| --- | --- | --- |
| **N1** | the acceptance's **gated** budgets pass (worst descent `|v|max`, lurch, the reported cone) and its **rate is non-inferior to C** - the tree's own control is the **6/10 pear-on branch** under the documented owner exception (`logs/p33/51_phase2_read.md` §4.1 (A)); the fingerprint matches `configs/motion_reference.json` for the arms that stay in branch, or the arm's own re-record for the ones that move (`W`, and `F2` if permitted) | `scripts/accept.sh` |
| **N2** | the **right lane's `placed` count is non-inferior** on both batteries (control: 12/12 acceptance + 10/10 pear) | the corpus script |
| **N3** | **F1/W:** the two-line stream is **byte-identical** to the W7-A record (442/442 `[fruit]` lines) and `190` PASS - a *prediction*, since F1 is contact-neutral and W is inactive on a two-line session. **F2:** `190` PASS on its own reference and the two-line's placed count non-inferior (a global physical change; identity is not predicted) | `scripts/190_twoline_gate.sh`, `scripts/105`/`compare` |
| **N4** | **F1/F2 only:** the `47` probe's jaw floor moves by **exactly `delta` +- 1.5 mm** against the control's | `scripts/47_robot_collision.py`, conveyor on, one run per arm |
| **N5** | **N4 fails => the lever is not what it claims** (the distal plane is not the contacting part, or the box was not authored) => stop, no grip claim, no adoption | - |

A moved branch is **expected** for F2 and for W (both change the arm's
configuration), and is permitted only with **its own** re-recorded
`configs/motion_reference.json` (the shipped `25ade92b` is per-scenario and
cannot certify a new branch), archived beside it - never overwritten. For F1 a
moved branch is a **falsifier** (§4 F-1), because the algebra says nothing in
contact changes.

---

## 3. N, the batch, and the same-batch control

* **N = 2 runs per arm**, both logged, both compared: the scripted line is
  deterministic per configuration (nine bit-identical v1 runs; the P33/P32
  branches replay 376-442/442), so the second run is a **determinism check**, not
  a variance estimate. The decision is the class census, not a rate - a rate
  test needs the N=5 protocol of `WS-4.2`, which this phase does not invoke and
  cannot afford on a 10-attempt acceptance.
* **One `154_claim_run.sh` claim per batch**, arms **interleaved C -> F1 -> F2**
  (and, separately, C -> W) inside the claim, one tree, `SEED` fixed and
  identical across arms.
* **The same-batch control is C in the same claim.** No control is quoted from a
  previous phase's log: the finger change is global, so a cross-batch control
  would confound the tree.
* `FRUIT_CARRY_DIAG` stays **off in every arm** (P33 §2.5: the diag takes a
  per-tick payload/jaw read and is not proven run-neutral). The `[attitude]`
  print (§1.3) is on in every arm once it exists, so it cannot favour one.
* **The batteries in the claim, per arm**: (a) `scripts/accept.sh`'s scenario,
  10 attempts; (b) the species-locked pear battery (`90`/`91`'s protocol), 10
  attempts per profile; (c) the two-line dense gate, 10 attempts (`190`);
  (d) for F1/F2 only, the `47` probe. That is ~40 scripted attempts + 2 probes
  per arm.

---

## 4. Falsifiers (each stops the arm, not the phase)

| # | falsifier | reading |
| --- | --- | --- |
| **F-1** | **F1's `[fruit]` stream is not byte-identical to C** although `delta = -4 mm` is inside the free bound (the patch's lower edge is 1.7-2.6 mm below the equator) | the distal lip *is* load-bearing somewhere in the cycle; the class-relevant direction is the extension, and F1's "contact-neutral" premise fails - re-derive before any grip claim |
| **F-2** | **F2** shows a belt-contact signature: a `47` probe floor below `belt_top + 76.8 + 4 mm`, or a `clearance:` row below 0 mm on a *placed* leg, or a finger-AABB row inside the slab | the extension bound is not `r - lip0` on this supply; stop |
| **F-3** | **W**'s right-arm legs or its place legs are not byte-identical to C | the leg/arm scope is not what the code says; stop (no adoption either way) |
| **F-4** | a **new failure reason** in any arm | the arm relocates the class; not eligible for adoption (the P33 §4.1 rule) |
| **F-5** | a **gated motion budget** fails on a leg C passes (worst descent `|v|max` / lurch) | the arm is out of band; no adoption, and no reference re-record |
| **F-6** | C itself does not reproduce `01_left_corpus.txt`'s pins (the left cnp count, the band separation, `F_min = 0.00` on the cnp legs) | the batch is invalid, not the lever |

A null is a **result**: F1 in particular is *predicted* null on the class (§5),
and a byte-identical stream is the strongest possible confirmation that the lip
is inert - it does not need a "failed" label.

---

## 5. Expected bounds (stated before the run)

| arm | prediction | basis |
| --- | --- | --- |
| **F1** | **0 converts**; the `[fruit]` stream byte-identical to C | the removed 4 mm is provably out of contact (the commanded 0.2 mm interference makes the contact patch 3.3-5.3 mm tall about the equator and its lower edge sits 1.7-2.6 mm below the equator, so a 4.2 mm shortening keeps 100 % of the patch); the deliverable is the lip-inertness bit + 7.2 -> 11.2 mm of tip clearance on the 2.8 cm pool minimum (8.2 -> 12.2 mm on the 3.0 cm fruit the corpus drew) |
| **F2** | **0-2 of the left's 3-6 cnp** convert | the arrest distances in the record are 18-25 mm (5 of 31 escapes survived their leg); a +4 mm lip (6.8 -> 10.8 mm) moves the arrest band by 4 mm, so only escapes arrested in the 7-11 mm band can flip; the belt bound is 7.2 mm on the 2.8 cm pool minimum (8.2 mm on the 3.0 cm lychee the corpus drew), so 4 mm is the largest form with margin |
| **W** | **0-1 of 3** convert | the onset force is already at the carry level (4.90 N median) and single-sided, so the attitude is a *correlate*; the hold's measured negative (`logs/444`) was the place leg, which this arm excludes |

**Power statement, unconditional:** on a 10-attempt acceptance whose left takes
5 attempts, the maximum observable composite change is 4 -> 0; on the pear
battery (8 left attempts) it is 6 -> 0. Neither number is a rate, and no
cross-branch comparison will be made - the verdict is the class census plus the
per-leg band plus the no-harm set.

---

## 6. The decision rule, and what needs the owner

* **L1-F1** may be **adopted** only if it passes N1-N5 and produces no class
  relocation, *and* if its verdict is "null on cnp" it is still adoptable as a
  **hardware/clearance** change (it buys 4 mm of tip clearance on every fruit and
  documents the 16.8 mm model/physical tip gap) - but that is a *hardware*
  recommendation, which is the owner's call, not this lane's.
* **L1-F2** (the extension) is **not the authorized form** ("the short-tip
  finger" is). It is registered so that the result is pre-committed if the owner
  grants the sign-off; it must not run without it. If F1's falsifier F-1 fires,
  F2 becomes the *only* class-relevant form and the sign-off request carries
  F-1's numbers.
* **L2-W** may be adopted only on a primary PASS. Its no-harm is cheap (the arm
  and leg scopes make the right lane's identity a prediction), so a null is a
  clean close rather than an ambiguous one.
* **Nothing here changes a shipped default in phase 2/3.** A flip needs a
  separate owner decision after the A/B, as every previous lane in this tree.

---

## 7. Cost, and what is explicitly out of scope

* Simulator time: 2 claims (the finger batch, the wrist batch); per arm and per
  run the batteries total ~40 scripted attempts (10 acceptance + 20 pear + 10
  two-line) plus 2 probes for F1/F2, and every arm runs twice. The simulated time is
  fixed and small (the acceptance is 150 s of sim for 10 attempts, 15.0 s per
  attempt); the **wall is not predicted here** - the recorded 10-attempt
  acceptance runs range 6-18 min and the W3-supply canary took 17.5 min for ten
  episodes - so the batch must log its own wall and the claim must be sized
  against `154_claim_run.sh`'s limit rather than against a guess.
* Out of scope: the direct/policy A/B (a finger change is a sim-only image
  artifact, §2.4 of the read); D3-proper; the C1 class-matched direct re-run
  (`logs/r11/B_RESULTS.md` §5, still open and still a different interface); any
  re-run of the closed levers (the guard, the relief, the scoop, the groove, the
  soft pad, the AWR pass, the pre-onset path) - the register in
  `logs/p33/51_phase2_read.md` §3 stands.

---

## Amendment A1 (2026-10-25, Oracle gate 1, **before any code or run**)

Gate verdict: PROCEED as amended. Seven changes, recorded here so the original
text above stays readable as the pre-gate registration.

**A1.1 — arm W is withdrawn; lever 2 closes as a code fact.** The shipped
`grasp_lift` leg already holds the commanded top-down attitude: `_carry` clears
`arm.hold_quaternion` only for `name != "grasp_lift"` (`tasks.py:2739-2750`), in
both attempt paths, and it is never cleared before the lift. `FRUIT_CARRY_HOLD_QUAT=1`
therefore does not add a hold - it swaps the hold *target* to `_grip_quat`
(re-derived from the live TCP each tick, `:3227`), a residual-scale change.
`logs/444`'s negative is the place leg. The place-start sub-class already has its
own knob (`FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S`, `:2903-2916`). No W arm is run.

**A1.2 — arm S is added: `FRUIT_FINGER_TIP_DELTA=0` with the re-author forced.**
The knob is **presence-gated**: unset = the shipped mesh colliders (byte-identity);
any value, *including `0`*, = disable the plate colliders and author the boxes.
Without S, F1's null cannot be attributed ("box == mesh" vs "lip inert"), because
the design replaces the mesh with a box. **C / S / F1** is the batch.

**A1.3 — the primary is restated, because the original was unreachable by
construction.** The §1.1 composite asked for ≥2 converts on the acceptance *and*
≥3 on the pear battery; the acceptance's left composite is 4 and the pear's is 3,
so PASS needed ≥5 conversions while F2's own prediction is 0-2. Also the
acceptance's left-attempt count is 5 or 3 by branch, and the two pear profiles
(90/91) are two scenarios that AGENTS §2 forbids pooling. **New primary:** the
**pear battery, one profile (the shipped pear), is the primary**; the acceptance
is a **report**. The verdict is the **class census** (`placed` / `cnp` /
`no-grasp` on the left) and it is **evaluable only if the left-attempt count is
invariant** across C and the arm - otherwise the arm moved the branch (snapshots
and per-leg numbers only, no verdict). The per-leg band (§1.2) is unchanged.

**A1.4 — no-harm, made testable.** N1 gains an explicit margin: the acceptance's
`placed` is **≥ C − 1 on the 10 attempts**. N4 becomes the `47` probe's jaw floor
shifted by **`delta * cos(theta)` relative to S**, with the probe's tilt reported
(the shift is not `delta` on a tilted probe). Byte-identity claims (§2 N3, §4
F-1) are made **only on the print-off runs**.

**A1.5 — the `[attitude]` print is default off, and the batch is split.** The
print (`FRUIT_CARRY_ATTITUDE=1`) reports, once per carry leg at its end, the tool
tilt from vertical **and** the pad-fruit offset (the achieved lip) in one stated
frame - tilt alone does not give the lip. It is off in the class/no-harm batch
(so the identity test is meaningful) and on in a **separate, acceptance-only,
one-run-per-arm mechanism batch**.

**A1.6 — claim sizing.** `154_claim_run.sh`'s `RUN_LIMIT` defaults to 1800 s, so
each battery is its **own claim**: (1) the acceptance, (2) the pear battery,
(3) the two-line gate, (4) the `47` probe, (5) the mechanism batch. No arm's
~40 attempts are packed into one claim.

**A1.7 — scope of a null.** A −4 mm null is **not** evidence against the
authorized P30-C hardware form, whose usable magnitude is 24-45 mm and which the
sim cannot test (the pads are *placed*, not reached). F2 stays withheld and its
sign-off request carries **S + F1's** results, never the algebra alone.

**Batch of record after A1: arms C / S / F1; batteries: pear (primary),
acceptance (report + N1), two-line (N3), `47` (N4/N5); mechanism batch with the
print on.**

---

## Amendment A2 (2026-10-25, Oracle gate 2, **before the first battery**)

Gate 2 verified the phase-2 diff and returned PROCEED after these seven
amendments. A2.1-A2.3 are code, A2.4-A2.7 text; **all are registered before any
battery run**.

**A2.1 — the parse must reject non-finite and absurd values.** `float("nan")`
passes the current `length < 0.005` guard (NaN compares False), and `=1.0` would
author a 1 m plate. Add: non-finite or `|delta| > 0.05` -> the same FATAL path;
echo the accepted value in the build print.

**A2.2 — the new prints must not pollute the `[fruit]` stream.** `say()` prefixes
`[fruit]` unconditionally (`common.py:28-30`), so the phase-2 run reads 98
`[fruit]` lines against a 92-row physics stream, and every byte-identity
criterion in this tree is "*N/N* `[fruit]` lines". From here: the **build print is
a plain `print`** (no `[fruit]` prefix) and the `[attitude]` rows keep the prefix
but are **filtered** by their tag; every report prints both the raw and the
filtered counts, and N3/§4 F-1 are restated as **filtered** (drop
`finger tip delta` and `[attitude]` rows).

**A2.3 — the lip constant is corrected and the axis is printed.** The shipped
collider *is* the visual mesh (convex hull), so the contact plane's tip is the
**build print's 80.5 mm**, not the `logs/166` **contact-stop** 76.8 mm (short by
the stop's penetration/rest offset, ~3.7 mm). The printed lip therefore
under-estimates by `3.7 * cos(tilt)` = 2.6-3.2 mm; the ordering survives. Use
80.5 mm as the geometry constant (provenance in the comment), keep 76.8 mm
documented as a stop, echo `tip=` in the line, print the **tool axis** (three
components, so the corner's azimuth relative to the belt is derivable) and both
candidate corner drops (`16.65 * sin(tilt)`, `30.5 * sin(tilt)`) - at 31-45 deg
that is 8.7-15 mm, larger than the whole 4 mm budget.

**A2.4 — F2's expectation is revised to 0 converts, and F1's wording narrowed.**
The premise (a lip deficit on the lift) is empirically absent: the **left
achieves more lip (11.0 mm) than the right (4.3 mm) and is the failing arm**,
while the right places 12/12 + 10/10. And at the achieved 30-45 deg tilt the
corner term (8.7-15 mm) displaces the belt-clearance bound that sized `+4 mm`.
F2 stays **registered** and owner-gated, expectation **0**. F1's
"contact-neutral" is restated as **plate-frame**, and its clearance gain as
**4 mm along the plate (3.4 mm vertical at 31.6 deg)**, not the vertical-pose
7.2 -> 11.2 mm. F1 is kept: it is unaffected as a construction, and F-1 already
covers the tilt.

**A2.5 — N4b: the `47` floor must also match S vs C within 1.5 mm.** Without it,
N4 cannot separate "`delta` has no effect" from "the re-author never took".

**A2.6 — S is a control, not a verdict arm.** The decision is **F1-vs-S**; a
C-vs-S branch move is expected (AABB corners vs the hull) and must not be read as
harm. A1.3's evaluability rule (invariant left-attempt count) therefore applies
to **F1-vs-S**; C-vs-S is reported as the mesh-to-box step.

**A2.7 — the mechanism batch runs last and includes C.** C is the lip anchor; a
print-on F1 with no print-on C cannot be interpreted. Ordering of the claims:
pear (primary) -> acceptance -> `47` -> mechanism -> two-line. The two-line gate
may be shortened to the arms whose pear/acceptance filtered streams moved, and
that deviation is recorded in the phase-3 result.

**Text corrections (same amendment).** The literal command/env/attempts/SEED per
battery is pinned in the phase-3 note; §1.1's "pear battery, 18 attempts" is
**two 9-attempt profiles** (§3's 10-per-profile launch, one profile of record =
the shipped pear); `01_left_corpus.txt`'s C values are the F-6 pins; "cannot
change an outcome" becomes the tree's measured convention (reads and prints
outside the control loop are run-neutral) with every identity/class claim kept
print-off.

---

## Amendment A3 (post-run withdrawal, 2026-10-25, Oracle gate 3, **after the phase-3 batch**)

A3 changes **no endpoint, no gate and no verdict**. It withdraws one
**recommendation** that §6 made conditional on a claim the batch did not
measure.

**A3.1 - the belt-clearance claim is untested, and §6's hardware/clearance
recommendation is withdrawn.** §6 says L1-F1 "may be **adopted** only if it
passes N1-N5 ..., *and* if its verdict is 'null on cnp' it is still adoptable as
a **hardware/clearance** change (it buys 4 mm of tip clearance on every fruit
and documents the 16.8 mm model/physical tip gap)". **The second clause is
withdrawn:**

* **The instrument did not reach the distal plane.** `scripts/47_robot_collision.py`
  is registered (N4) as a straight `-0.35 m` z descent that seats the plate's
  distal plane on the belt. It instead **jams laterally**: the jaw travels
  0.13-0.17 m in x and 0.16-0.18 m in y for 0.03-0.06 m of z, and C ends in a
  different hand configuration (finger long axes along world X) than S/F1
  (along Y). The jaw-floor difference is therefore a **configuration outcome**.
* **N4 is not computable as registered** in any case: `47` prints no tool axis,
  so `delta*cos(theta)` has no measured `theta` on this probe.
* So the honest state of the clearance bit is **untested (no valid distal-plane
  instrument), not measured-zero**. The geometric re-author *is* proven - the
  build print reads long `84.9 -> 80.9 mm` and distal `80.5 -> 76.5 mm` at
  `delta = -4 mm` - but "4 mm of tip clearance" as a **belt** statement is not
  measured, and a hardware recommendation cannot rest on it.
* The valid instrument, if the bit is ever wanted, is a **static-pose read of
  the authored collider prims** (`S - F1` must differ by `4*cos(theta)`), not
  the collision probe.
* Nothing else moves: F1's class verdict stays **not evaluable** (A1.3's count
  invariance fails on the primary) and **no shipped default changes**. F2 stays
  withheld and owner-gated (A1.7), and its sign-off request carries the
  measured null, not the algebra alone.

The phase-3 readings this amendment rests on are in
`logs/p39/p3/RESULT.md` §0, §3 and §10.1.3.
