# P69 phase A — the pad asset (the short-tip finger): the static read, the contact invariant, and the registration

Written 2026-10-30, started on HEAD `d2b8f66`; phase C's docs commit **`c5c8f25`**
landed while this phase was running and touches only `docs/LEFT_ARM.md`,
`README.md` and `项目总结报告.md`, so no pin below moves. **Tier A: the static
read is free (three robot-only builds, 54 s total) and one short geometry probe
was spent (two 1-attempt scripted runs, 90 s).** No `src/` or `configs/` edit, no
default change, no commit.

---

## 0. Verdict (read this, then §1)

**The authorized magnitude cannot grip. The pad-asset lane is registrable only
inside a band 1.8-10.8x smaller than the magnitude that was authorized, and
inside that band every admissible move is 4.1-10.9 % of the walk on the patch-intact band and 6.0-16.0 % on the any-contact band (the earlier "5-13 %" traced the negative half only) of the phenomenon it would have
to stop.**

1. **The static read is exact.** `FRUIT_FINGER_TIP_DELTA` authors the four finger
   plates' boxes at **84.902 / 80.902 / 60.902 / 49.902 / 39.902 mm** for
   `0 / -4 / -24 / -35 / -45 mm`, the **distal plane** rises by exactly
   `|delta|*cos(theta)` (**856.399 → 860.399 / 880.399 / 891.399 / 901.399 mm**)
   and the proximal plane does not move (**941.301 mm** on all four links, all
   five arms). `theta = 0.0000 deg` at the authored pose, so the identity
   `S - M == |delta|*cos(theta)` holds to **9.7e-7 mm** (§2).
2. **The grip touches iff the plate's lower edge reaches the fruit's equator**,
   and that is the number the authorized magnitude spends. At the shipped aim
   (jaw standoff `0.070 m`) the shipped lip is **10.5 mm** and the contact patch
   is **1.67-2.64 mm** tall. At `-24 / -35 / -45 mm` the plate's lower edge sits
   **+13.5 / +24.5 / +34.5 mm ABOVE the equator**: the pads close **without
   touching any of the 8 pool classes** (closest approach **+2.6 mm** on the
   7 cm apple, and still **+0.3 mm** under the most aggressive measured seat).
   The admissible band is **`+3.5 … -7.9 mm`** (patch intact) or
   **`+3.5 … -13.1 mm`** (any contact at all) — so the authorized magnitudes are
   **1.8x / 2.7x / 3.4x** past the last magnitude that touches anything, and
   **3.1x / 4.5x / 5.7x** past the last one that keeps the patch intact
   (**5.8x / 8.4x / 10.8x** on P39's conservative 76.8 mm convention).
3. **What each magnitude buys, and where.** At the **descent** (`0.8 deg`):
   **+24.0 / +35.0 / +45.0 mm** of tip-belt clearance — *unconsumed*, because the
   tip already clears the belt by 3.5-24.5 mm and the descent's residual is a
   **jaw-plane** number (8.1-10.3 mm). At the **carry** (`24.6 deg`): +21.8 /
   +31.8 / +40.9 mm vertically and 10.0 / 14.6 / 18.7 mm upstream — and that
   vertical gain **is** the lip it removes, 1:1, which is the only material the
   payload has to walk out of. At the **rail crossing: exactly 0.0 mm**, because
   `clr=` / `clr_win=` are **payload** clearances and the payload hangs 3.5-24.5
   mm *below* the plate tip on every class (§4).
4. **The do-no-harm arithmetic is a no-op.** The brief's 40-90 mm descent
   shortfall is **v1 history**: the current tree's dynamic residual is
   **8.1-10.3 mm** (`[motion] approach … end=`), and `-35 mm` does not move it,
   because the residual is measured at the **jaw** and the tip is not the
   contact. The probe confirms it: **`end=8.1 mm` and `belt_margin=+37.4 mm` in
   both arms, to the digit** (§6).
5. **The probe (one claim, spent): the shortened plate does not touch the
   fruit.** Same seed, same fruit (a peach), same `end=8.1 mm`: control
   `grasped=True, lift=+0.289 m, force 10.00 N, min_contacts=2, sep_end 70.6 mm`;
   `-24 mm` arm `grasped=False, lift=+0.000 m, force_min=0.00 N,
   contacts@onset=0, force@onset=0.00 N`, and the pads ran to a **32.3 mm** span
   — **38 mm inside** the span that held the same fruit one arm earlier (§6).
6. **The registration.** `G0` (the contact invariant) **FAILS** at the
   authorized magnitude, so **no battery is registered at `-24/-35/-45 mm`**.
   What *is* registrable: **G1** the in-bound short tip (`-0.004`, P39's F1,
   already run once and **not evaluable**), predicted null on the class; **G2**
   the class-indicated **extension** (`+0.0035`, the belt bound on the 2.8 cm
   pool minimum), owner-gated and predicted null at 1.3-3.4 % of the measured
   104-276 mm walk. §7 carries the arms, endpoints, falsifiers, N and cost;
   §7.5 states the hardware-class terms and the **one instrument that would
   measure the belt bit**, which today's record does not have.

---

## 1. The lever, its sites, and what it is not

| layer | site | what it does |
|---|---|---|
| knob | `scene.build` → `_author_finger_tip_delta` | **presence-gated**: unset = the shipped mesh colliders, byte-identical |
| authoring | `_author_flat_face` (`scene.py:1332`) | one `UsdGeom.Cube` per finger link at `.../contact_faces/tip_delta`, from the plate's proximal end to `tip_coord + delta`; `UsdPhysics.CollisionAPI` only |
| what it replaces | `_disable_finger_plate_colliders` | the `visuals/` and `collisions/` subtrees of the four finger links (8 prims), by path; the palms are read and reported unchanged |
| reach | every consumer of the stage | the **scripted** line, the **direct/policy** path, the **two-line** scheduler and the hybrid canary all build through `scene.py`, so all four see it |
| scope | build time, not run time | it changes the **contact**, not a command — the aim, the standoff, the close target and the descent are untouched |

**It is not the control's `=0`.** `FRUIT_FINGER_TIP_DELTA=0` re-authors the plate
as its own AABB (P39's arm **S**), which is a *different collider* from the
shipped mesh one. The control is the knob **unset**. Every arm below is either
`C` (unset) or a signed value.

**And it is a hardware-class change, not a knob.** The finger plate is the
hardware; a 24-45 mm cut is a new finger, and it carries the whole grip
re-baseline (R6-B's drive-saturated pinch, W8-B's `clean_slip` bands, the S3/D2a
standoff axis) — P30-C's own framing, which this phase does not overturn. The
one thing the sim can do that a hardware change cannot is *author the collider
without the mesh*, which is exactly why the lever exists and why §7.5's
instrument is needed before any clearance claim travels.

---

## 2. A1 — the static read (`logs/p69/tip_geometry.txt` §1/§2)

The instrument is P66's (`logs/p66/collider_read.py`, the A3-named valid one): a
**robot-only** build (`parts=("robot",)`), **no `scene.start()`, no physics
step, no attempt loop**; it reads the authored boxes off
`ComputeLocalToWorldTransform(Usd.TimeCode(0))`. Three new builds at the P30-C
magnitudes, 18 s each (`logs/p69/collider_<delta>.log`).

All four finger links are identical, so the table is per magnitude:

| delta mm | face | mid | **long** | d_long | theta | **distal plane z** | d_distal | proximal z | prims |
|---|---|---|---|---|---|---|---|---|---|
| unset / 0 | 33.261 | 61.000 | **84.902** | — | 0.0000 | **856.399** | — | 941.301 | 1/3 |
| -4 | 33.261 | 61.000 | **80.902** | −4.000 | 0.0000 | **860.399** | +4.000 | 941.301 | 1/3 |
| **-24** | 33.261 | 61.000 | **60.902** | −24.000 | 0.0000 | **880.399** | +24.000 | 941.301 | 1/3 |
| **-35** | 33.261 | 61.000 | **49.902** | −35.000 | 0.0000 | **891.399** | +35.000 | 941.301 | 1/3 |
| **-45** | 33.261 | 61.000 | **39.902** | −45.000 | 0.0000 | **901.399** | +45.000 | 941.301 | 1/3 |

* **The change is purely axial**: face `33.261 mm` and mid `61.000 mm` are
  bit-identical across all five arms, and the proximal plane is `941.301 mm`
  everywhere (to 0.001 mm).
* **Exactly one collider is enabled per finger link** (`1/3`) at every
  magnitude — the box is the collider; the visual mesh and the asset's convex
  proxy are disabled. So the plate is replaced, not doubled.
* **The identity**: the shift is along the plate's long axis, so the vertical
  part is `|delta|*cos(theta)`. At the authored pose `theta = 0`, and the read is
  `|delta|` exactly (`max err 9.7e-7 mm`). The two operating attitudes project
  it as

  | delta | theta = 0 (read) | 0.8 deg (descent) | 24.6 deg (carry) | along-belt @ 24.6 |
  |---|---|---|---|---|
  | −24 | 24.000 | **23.998** | **21.822** | 9.991 |
  | −35 | 35.000 | **34.997** | **31.823** | 14.570 |
  | −45 | 45.000 | **44.996** | **40.916** | 18.733 |

  (0.8 deg = P62's T0 attitude error at its own 2/3 solves — the descent's
  commanded attitude; 24.6 deg = P63's median `hold_drift` on the left's
  **failing** carry legs, 25.1 deg on P66's control rung.) At 28.6 deg — the
  *measured* left `grasp_lift` tool axis in P62's own cell — `cos` is 0.878 and
  the vertical gains are 21.1/30.7/39.5 mm: the conclusion is insensitive to
  which of these is quoted.

---

## 3. A1 — the contact invariant, which is what decides it

The gripping surface is the plate's **face plane** (unchanged by `delta`, at
`face_coord` 5.8 mm) over the plate's **axial extent**. `lip` is how far that
extent reaches below the fruit's equator at the shipped aim:

```
lip(delta)  = (TIP_FACE + delta) - STANDOFF          TIP_FACE = 80.5 mm (authored
                                                     distal plane below the jaw)
                                                    STANDOFF = 70.0 mm (measured
                                                     69.3-71.7, P42)
            = 10.5 mm + delta
face span   = [ -lip , -lip + (84.902 mm + delta) ]   about the fruit's equator
contact     iff  lip >= -h(r)      patch intact iff  lip >= +h(r)
h(r)        = sqrt(r^2 - (r - interference/2)^2)      interference = 0.2 mm
```

`h(r)` is **1.67 mm** on the 2.8 cm pool minimum and **2.64 mm** on the 7.0 cm
maximum, so the **largest fruit binds both bounds**:

| criterion | bound on `\|delta\|` | what it means |
|---|---|---|
| patch **intact** on every class | **7.86 mm** | the designed pinch: both faces on the patch |
| **any contact** at all | **13.14 mm** | the plate's lower edge still reaches the patch's upper edge |
| P39's registered `neutral_bound` | **4.16 mm** | the same "intact" criterion on the 76.8 mm **belt-stop** tip (an AABB-corner lead, P39 §5) — the conservative form |

| delta mm | tip below jaw | lip | plate lower edge | face span about the equator | any contact? | closest face-to-fruit gap |
|---|---|---|---|---|---|---|
| unset / 0 | 80.5 | **+10.5** | −10.5 | −10.5 … +74.4 | **yes** | −0.1 (designed interference) |
| −4 | 76.5 | **+6.5** | −6.5 | −6.5 … +74.4 | **yes** | −0.1 … −0.1 |
| **−24** | 56.5 | **−13.5** | **+13.5** | +13.5 … +74.4 | **NO** | **+2.6 … +10.2 mm** |
| **−35** | 45.5 | **−24.5** | **+24.5** | +24.5 … +74.4 | **NO** | **+9.9 … +22.5 mm** |
| **−45** | 35.5 | **−34.5** | **+34.5** | +34.5 … +74.4 | **NO** | **+14.0 … +34.0 mm** |

The last column runs over the eight pool classes; on the smallest classes the
plate is entirely above the fruit and the value is the class's own radius. `-0.1
mm` is the *shipped* grip's designed interference at the equator, so `<= 0` is
contact and every authorized magnitude is off the scale on the other side.

**Sensitivity — the verdict is not a property of one standoff.** The closest
class (the 7.0 cm apple) at each magnitude:

| convention | standoff | at −24 | at −35 | at −45 |
|---|---|---|---|---|
| the model (`_pad_standoff`) | 70.0 mm | **+2.6 mm** | +9.9 mm | +29.0 mm |
| measured low end (P42) | 69.3 mm | **+2.3 mm** | +9.2 mm | +25.8 mm |
| measured high end (P42) | 71.7 mm | **+3.4 mm** | +11.7 mm | +35.0 mm |
| the most aggressive measured seat (D2a −8 mm) | 62.0 mm | **+0.3 mm** | +4.0 mm | +12.0 mm |

So `-24 mm` clears the payload on *every* class under *every* measured seat, and
`-35/-45 mm` clear it by 4-35 mm. **This is not a degraded grip. The pads close
on air and the fruit stays on the belt.**

---

## 4. A1 — what each magnitude buys, and the cost side

### 4.1 Buys

| delta mm | **descent** (0.8 deg), tip-belt | **carry** (24.6 deg), vertical | carry, along-belt | **rail crossing** |
|---|---|---|---|---|
| −24 | **+24.0 mm** | +21.8 mm | 10.0 mm upstream | **+0.0 mm** |
| −35 | **+35.0 mm** | +31.8 mm | 14.6 mm upstream | **+0.0 mm** |
| −45 | **+45.0 mm** | +40.9 mm | 18.7 mm upstream | **+0.0 mm** |

* **The rail number is zero by construction.** `clr=` / `clr_win=` reduce
  `_payload_clearance`, which is the **payload's** lowest point
  (`fruit_z - support_radius`) against the rail top (`tasks.py:3323`); the plate
  tip is `STANDOFF + r - TIP_FACE` = **3.5 … 24.5 mm above** the payload's bottom
  on every class, so the payload sets the crossing and the tip cannot. A shorter
  tip raises the tip further out of the way and moves nothing. (The rail's *own*
  geometry is not the constraint either: the crossing is at 1.53 m and the rail
  top at `output_belt_top_z + 0.035` = **1.385 m**, so the hand clears it by
  ~145 mm and only the payload's hang is in play — its `clr` reads +48 mm on the
  probe's own control.)
* **The descent number is real and unconsumed.** At the shipped aim the tip is
  already `r - 10.5` = **+3.5 … +24.5 mm** above the belt (and, on the measured
  76.8 mm stop, +7.2 … +28.2), and the descent's residual is **above** the aim.
  Nothing on the shipped line spends belt clearance at the tip.
* **The carry number is the cost.** The vertical part it buys *is* the lip it
  removes, 1:1 by construction (`lip + clearance == r` is an identity on every
  class and magnitude, `max err 3.5e-18 m`). The lip is the only material the
  payload has to walk out of (`logs/w8/B_RESULTS.md`,
  `logs/p61/P2_RESULTS.md`), and the walk is 104-276 mm (P42).

### 4.2 Costs

1. **The contact patch — 3.3-5.3 mm tall, not 85 mm.** The plate's *length* is
   not the patch (P39 §6): the faces are `r - 0.2 mm` apart, so the sphere is
   within the interference over `|z| <= 1.67 … 2.64 mm`. A 24-45 mm shortening
   does not shrink a contact patch, it **deletes** it (§3).
2. **Mass and inertia do not move.** The box is authored with
   `UsdPhysics.CollisionAPI` only; the finger link's `physics:mass` is authored in
   `assets/openarm_flat/openarm_flat_deinst.usda`, so a shorter collider changes
   no dynamic term. Verified at the code and the asset, **not measured** — the
   one cost item here that is a code fact rather than a measurement.
3. **The authored collider and the visual mesh diverge by `|delta|`** — the P39
   A3 caveat, here 24-45 mm on an 84.9 mm plate. The `visuals/` subtree is never
   touched, so **the rendered hand is unchanged** while the physics hand is a
   fifth to a half shorter. On the scripted line that is irrelevant; on the
   **direct/policy** path the policy conditions on an image of a hand it does not
   have — and P36 measured that the image channel is the one that carries the
   park's win.
4. **The matched pair is a null, so there is no free form.** `lip = (tip + delta)
   - (standoff - drop)`: shortening by `d` *and* lowering the aim by `d` leaves
   both `lip` and the belt clearance **exactly** unchanged (P39 check 2,
   re-asserted on the face tip, 4/4 combinations). **The pad asset has exactly one
   degree of freedom and it trades lip for belt clearance 1:1** — which is why
   P30-C's "cut it so the pads sit at the fruit's centre" and P39's "the matched
   pair is a geometric null" are the same statement.

---

## 5. A2 — the do-no-harm arithmetic: the descent does not move

**The premise needs correcting first, and the correction is load-bearing.**
`logs/160/161`'s *40-90 mm* shortfall is v1 history: P30-C re-measured it ("the
pick pose is *inside* the band on the current tree"), and the current scripted
line's dynamic residual is **8.1-10.3 mm** over ten attempts
(`logs/p68/accept_noharm.log`, the `[motion] approach … end=` rows; P30-C's
`[boundary] end=` reads 8.3-10.8 mm over the same family).

With that:

* **`end=` is a jaw-plane quantity.** It is the TCP's residual against the aim.
  The tip is `TIP_FACE` below the jaw, so a tip shortening moves the tip's world
  height by `|delta|*cos(theta)` and moves the **jaw** by 0. The shortfall is
  therefore **unchanged at 8.1-10.3 mm** — the same, not "the same amount at the
  tip only", because the two quantities are on different planes.
* **A 24-45 mm shorter tip clears the belt at the descent trivially, because the
  shipped tip already does.** At the aim the tip is `r - 10.5` = **+3.5 mm** on
  the 2.8 cm pool minimum and **+24.5 mm** on the 7.0 cm maximum; the brief's
  "can it clear the belt" is answered **+27.5 … +48.5 mm after a 24 mm cut**,
  against a requirement of zero. The P39 `47` probe's measured "3.8 cm with the belt
  present vs 23 cm without" is a **commanded −0.35 m plunge** — 350 mm below any
  shipped aim — so it measures the belt contact of a pose the shipped line never
  enters; the shortening raises that stop by 24-45 mm and *nothing else on the
  tree consumes it*.
* **The new shortfall reads 8.1-10.3 mm, i.e. the same number**, and the *new*
  problem is §3: the pads no longer reach the fruit. The probe confirms the first
  half to the digit: `end=8.1 mm` and `belt_margin=+37.4 mm` in **both** arms
  (§6). Note that `belt_margin` is invariant **by construction** — it subtracts
  `FRUIT_FINGER_LEN` (60 mm), not the authored tip — which is exactly why it
  cannot serve as the belt-clearance endpoint (§7.3, §7.5).

---

## 6. A4 — the one probe, its claim and its result

**The claim (registered before the run):** *a plate shortened by 24 mm does not
touch a fruit of the class that comes closest, and leaves the descent untouched.*

**The cell:** one scripted attempt, seed 5 (the acceptance's default), `20_pick_place.py`
with `ATTEMPTS=1`, the same four reporting-only diagnostics in both arms
(`FRUIT_DYNAMIC_ARRIVE_DIAG` / `FRUIT_CLOSURE_DEBUG` / `FRUIT_CARRY_DIAG` /
`FRUIT_CARRY_ATTITUDE`), arm `C` = knob unset, arm `T` = `-0.024`. One claim, two
runs, **90 s** (`logs/p69/probe_{C,T}.log`).

| read | **C** (unset) | **T** (−24 mm) |
|---|---|---|
| `[run] attempt 0: picking` | peach grade A | peach grade A |
| `[boundary] … end=` | **8.1 mm** | **8.1 mm** |
| `[boundary] … belt_margin=` | **+37.4 mm** | **+37.4 mm** |
| `[carry] grasp_lift force@onset` | n/a (seated) | **0.00 N** |
| `[carry] … contacts@onset / min_contacts` | — / **2** | **0 / 0** |
| `[carry] … force_min` | **10.00 N** | **0.00 N** |
| `[carry] … sep_end` | **70.6 mm** | **32.3 mm** |
| `[task] lift` / `[run] attempt 0` | **+0.2894 m**, grasped ✓ placed ✓ | **+0.0000 m**, grasped ✗ placed ✗ (`fruit did not follow the gripper`) |
| attempt span | 14.6 s | 11.1 s |

**Read it as two statements, both of which the arithmetic predicted.**

1. **No contact.** The pads closed to **32.3 mm** — **38 mm inside** the 70.6 mm
   span that held the same fruit one arm earlier — with zero contact force and
   zero contact count on the way. To reach 32.3 mm with the fruit between them
   the pads would have had to pass *through* it. The `clean_slip` bookkeeping
   prints 502.4 mm on this leg, and it is **not** a loaded slide: it is the
   contact-agnostic `[carry]` relative-displacement field on a leg that never
   seated (`contacts@onset = 0`, the W8-B reading rule). **Read `[carry]` rows by
   `contacts@onset` first.**
2. **The descent is untouched.** `end` and `belt_margin` are identical to the
   digit, so the tip collider is not in the descent's contact loop and A2's
   "the tip plane is not the jaw plane" holds in the sim as well as on paper.

**Caveats, stated.** (i) One attempt, one seed, one class — but it is the
**closest** class (§3's +2.6 mm), so it is the worst case, and the claim is
categorical, not a rate. (ii) `C` and `T` are **not bit-identical**: they differ
from the pre-pose onward (`jaw z` 1.2706 vs 1.2762 m, the wait 51 vs 55 steps,
the fruit 3 mm along the belt), which is this tree's standing rule that a
configuration change moves the branch — so the pair is a **same-batch
comparison**, never a byte-identity. (iii) `C` also differs from the recorded
acceptance's attempt 0 (51 vs the acceptance's wait steps): the four diagnostics
perturb the branch, which is why both arms carry them.

**Why no further probe.** The deciding quantity is an **exact inequality on
authored geometry**, and it now has both a derivation (§3) and a measurement
(§6). The remaining number that is *not* offline is the **achieved tip world z at
the grip pose** — the belt bit — and it needs a different instrument than any of
this tree's probes (§7.5), not another attempt loop.

---

## 7. The registration

### 7.1 The decision rule, and the gate that fires

> **R0.** A pad-asset arm is registrable only if its magnitude is inside the
> contact-preserving band (§3) **and** its endpoint is a quantity the tree can
> measure. Both halves fail for the authorized form, and they fail for different
> reasons: the magnitudes are outside the band (§3, §6), and the one quantity
> they would move — tip-belt clearance — has **no valid instrument** (§7.5).

**G0 (the contact invariant, decided here, free): FAILS.** `-24/-35/-45 mm` are
**1.8x/2.7x/3.4x** past the contact-preserving bound and **3.1x/4.5x/5.7x** past
the patch-intact one (5.8x/8.4x/10.8x past P39's conservative form). **No battery
is registered at the authorized magnitude.** What follows is the only
registration the geometry admits.

### 7.2 The arms that are registrable

| arm | `FRUIT_FINGER_TIP_DELTA` | why it is the one | expected |
|---|---|---|---|
| **C** | unset | the shipped mesh collider — the only valid control | — |
| **G1** | `-0.004` | the **only** authorized-direction magnitude with a contact-preserving patch (P39's F1) | **null on the class** (the lip loss is 1:1 and the class needs the opposite sign); +4 mm of belt clearance nothing consumes |
| **G2** | `+0.0035` | the **class-indicated** direction (a longer plate = more lip), bounded by the belt on the 2.8 cm pool minimum (`delta <= r_min - lip0`) | **null**: +3.5 mm of lip is **1.3-3.4 %** of the 104-276 mm walk (P42) |

`G2` is **owner-gated**: it is P39's F2 direction, which P39 A3 records as "not
the authorized form" and this phase does not re-authorize. `G1` has been run
once (P39: arms C/S/F1, 5 acceptance runs + a species-locked battery) and its
verdict was **not evaluable** — the left's attempt count moved 2 (S) vs 4 (F1),
so A1.3's count invariance failed and F1's acceptance was inadmissible. A re-run
is therefore a *power* question, not a geometry one, and it is registered below
with the population cell that removes the count problem.

### 7.3 The endpoints

The cell is the **population cell** (all-grade-A supply, `FRUIT_SUPPLY_GRADES=A:0.96,B:0.02,C:0.02`
→ every attempt is the left, the P67/P68 convention), 8 picks/run, both arms
interleaved in one claim, plus the shipped acceptance and the two-line gate for
no-harm.

| # | endpoint | field / instrument | control (of record) | the arm must show |
|---|---|---|---|---|
| **P1** | **the left's cnp count** (primary) | `[rl] episode … grasped=… placed=…` (direct) / the `[run]` per-attempt rows (scripted); cnp = grasped ∧ ¬placed | P60's left **7 placed / 58 cnp / 4 never-held (n=69)**; P66 P3's control **0/25 placed** | a **fall of >= 10 points** absolute, in **4/5 runs** agreeing in sign |
| **P2** | **the place-leg loaded slide** | `[carry] … clean_slip_max`, `contacts@onset`, `loss_row` (`FRUIT_CARRY_DIAG=1`) | P67's pair **8/16 held** (= 8/16 lost); P66 P3's control **0/25** | held legs **+>= 3 of 16**, with `clean_slip` p50 unmoved on the placed ones |
| **P3** | **the descent's shortfall** | `[motion] approach … end=` and `[boundary] end=` (`FRUIT_DYNAMIC_ARRIVE_DIAG=1`) | **8.1-10.3 mm** | **unchanged within 2 mm** — this is the *no-harm* half, and F3 fires if it moves |
| **P4** | **the belt clearance** | **declared, not measured**: `[boundary] belt_margin` − (authored tip − `FRUIT_FINGER_LEN`) = printed − 20.5 mm; the arm's shift is **exactly** the authored `delta` | tip at `+3.5 … +24.5 mm` (control), `+27.5 … +48.5 mm` at −24 | the number **is** `r - lip0 - delta`; a *measurement* requires §7.5's instrument, and until then this endpoint is a statement about the model, not about the world |
| **P5** | **the grip's `clean_slip`** | `[carry] … clean_slip_max` p50 on the **placed** legs (`FRUIT_CARRY_DIAG=1`) | clean legs **0.02-1.43 mm** (W8-B); escapes 17.9-957 mm | p50 **not worse than +0.5 mm** |
| **P6** | **the rail crossing**, both lift heights | `[carry] clr=` / `clr_win=` with `FRUIT_LIFT_DZ=+0.08` (shipped 0.36 m) and `-0.08` (0.20 m) | shipped control **+30/+29 mm** (left), **+50 [+35..+60]** (right); low lift **+5/+0 mm** | **>= +33 mm** on every held left leg — the floor of record; expected **0 mm of movement**, since the payload sets the crossing (§4.1) |
| **P7** | **no-harm, scripted** | `accept.sh` + `105_motion_regression.py --fingerprint`; the two-line `scripts/190_towline_gate.sh` | `C` = **6/10 + `fingerprint: matches`**, `377/377` `[fruit]` lines identical to `logs/p66/p2/accept_noharm.log`; two-line 8/10 at the 0.60 floor (P41's own re-record, `2246f83c`) | **C reproduces byte-identically**; the **arm** is a moved branch and needs **both references re-recorded from its own runs** (`8a399626` and `2246f83c` both move) |
| **P8** | **provenance** | the manifest's `sources` | `scene.py` is in `rl_env._MANIFEST_SOURCES` | a post-change shard/rollout is identifiable by `scene.py`'s md5; **no store may be pooled across the collider** |

P1 is the primary because the class is what the lane is for; P2 is the mechanism;
P3/P7/P8 are the guard; P4 is the honest gap.

### 7.4 Falsifiers

* **F1 (contact).** Any attempt at an authorized magnitude with a tactile contact
  at the close (`min_contacts > 0` **and** `force@onset > 1 N`) — the §3
  inequality is then wrong and the whole registration stops. *Already tested
  once* (§6: 0 contacts, 0.00 N).
* **F2 (the consequence).** `grasped=True` with `lift > 0.02 m` at an authorized
  magnitude. *Already tested once* (§6: `lift=+0.0000`).
* **F3 (the descent invariance).** `|Δ end|` > **2 mm** between the arms at the
  same seed and fruit — the tip collider is then in the descent's contact loop
  and A2's plane argument is wrong. *Tested once* (§6: 0.0 mm).
* **F4 (the belt bit).** A static-pose read at the achieved grip pose (§7.5)
  whose tip-to-belt distance differs from `r - lip0 - delta` by **> 1 mm**.
* **F5 (the class prediction, for G1/G2).** The left's cnp count falling by
  >= 10 points **in the registered direction** — i.e. the class responding to
  the *short* side — would falsify "the class needs the opposite sign".
* **F6 (do-no-harm).** `C`'s acceptance not reading `6/10 +
  fingerprint: matches`, or its `377/377` `[fruit]` stream moving, or the two
  references not being re-recorded **from the arm's own runs**.

### 7.5 Equipment, cost and the hardware-class terms

**N and cost.**

| item | N | wall |
|---|---|---|
| G0 (this phase) | 3 static builds + 1 probe pair | **144 s** (spent) |
| G1 battery (direct, the WS-4.2 convention) | **5 runs x 15 episodes per arm x 2 arms** = 150 episodes, one claim, `moe_v13s` `61da390a`, seeds 77/101/202/303/404 | **~72 min** at P43's 28.6 s/episode (+ one build) |
| G1 battery (scripted population cell) | 5 runs x 8 picks per arm = 80 attempts | **~20 min** |
| the scripted cost of *any* magnitude | `accept.sh` (10 attempts) + `190` (two-line) + `selfcheck.sh` + **two reference re-records** | **~12 min** per arm |
| the belt-bit instrument (§7.5) | 1 build + 1 pose per arm | **~25 s** |

**The hardware-class terms, plainly.**

* The change is **authored geometry**, not a control parameter: it reaches the
  scripted line, the direct/policy path and the two-line scheduler, and it is
  invisible in the rendered image (§4.2.3). Any policy number measured across it
  is a *transfer*, not a comparison.
* **The belt bit has no valid instrument today.** P39 A3 withdrew the claim to
  *untested* because `scripts/47_robot_collision.py` jams laterally (0.13-0.17 m
  in x, 0.16-0.18 m in y for 0.03-0.06 m of z), ends 90 deg rotated, and **prints
  no tool axis**, so `delta*cos(theta)` has no measured `theta`. The static read
  fixes the arithmetic but not the contact: it has no belt in the scene.
* **What would measure it** — and it is one small extension of the instrument
  this phase already ran: **a static-pose read of the enabled collider prims at
  the achieved grip pose.** Take a logged `[grasp]` / `[closure]` TCP pose (or the
  joint vector a `[carry]` row implies), call `set_joint_positions` on a
  **robot-only** build with `scene.start()` never called, and report
  `min(world z of the finger link's enabled collider prims) - belt_top` per link
  (and the same for a placed fruit prim, for the payload's own number). Because
  the box is **rigid in the link frame** and the read is off
  `ComputeLocalToWorldTransform`, that is exact — no physics, no attempt loop, no
  jam. It costs ~25 s per pose and it would also settle P42's `[seat] tool=`
  constant (69.3-71.7 mm) at the achieved pose, which the record currently
  assumes rather than reads.

**What would make the pad asset worth a phase** (so the lane is closed with a
reopen condition, not an opinion):

1. **a real-jaw clamp-force anchor** — the other `SIM_LIMIT.md` sanction. The
   force family is already closed at 4.4-9.9 N and the 60 N cap crushes a 3.7 cm
   strawberry, so this is the only measurement that could re-open the class from
   the force side;
2. an **owner authorization for `G2`** (the extension) *with* 7.5's instrument,
   because it is the only direction the measured mechanism rewards;
3. a **new pad asset** (material or shape — a compliant cup, a different contact
   face), which is a different registration: the tip-length form of the pad
   asset closes here.

**And the arithmetic that closes it**: the whole admissible band is `+3.5 … -13.1
mm` against a measured **104-276 mm** mid-lift walk. The lever's entire range is
**5-13 % of the phenomenon**, on a class whose onset is at the *carry force level*
already (W8-B: the force is at its carry value at the onset; the slide is
geometric). A 24-45 mm cut is not a bigger version of that lever — it is past the
point where the grip exists.

---

## 8. Pins and reproduce

```bash
# the static read (three builds, 18 s each; the instrument is P66's, unmodified)
for d in -0.024 -0.035 -0.045; do
  FRUIT_FINGER_TIP_DELTA=$d scripts/run.sh logs/p66/collider_read.py > logs/p69/collider_$d.log 2>&1
done
cp logs/p66/collider_read_m0p0{24,35,45}.json logs/p69/
python3 logs/p69/tip_geometry.py --assert      # -> logs/p69/tip_geometry.txt  (12/12 PASS)

# the probe pair
HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=1 FRUIT_DYNAMIC_ARRIVE_DIAG=1 \
  FRUIT_CLOSURE_DEBUG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 \
  FRUIT_FINGER_TIP_DELTA=0 scripts/run.sh scripts/20_pick_place.py > logs/p69/probe_C.log 2>&1
# ... and the same with FRUIT_FINGER_TIP_DELTA=-0.024 -> logs/p69/probe_T.log
```

**Pins** (`md5` first 8, `logs/` is gitignored — `git add -f` at the close-out):
`logs/p69/tip_geometry.py` **`a82a0e33`** (this phase's only new code, and it runs
no simulator), `tip_geometry.txt` `3bedc9fb`, `collider_-0.024.log` `c7ecb3d8` /
`-0.035` `df1262cc` / `-0.045` `685be0e4`, `collider_read_m0p024.json`
`d46a1e87` / `m0p035` `8224c05e` / `m0p045` `d6b94e28` (copied from the
instrument's own output path, `logs/p66/`), `probe_C.log` `f35e4ee2`,
`probe_T.log` `ad794b8c`. Unchanged and untouched: `scene.py` **`27e3d64a`**,
`tasks.py` **`e5168578`**, `rl_env.py` **`d88c3729`**, `control.py` **`9384ff4f`**,
`configs/motion_reference.json` **`8a399626`**,
`configs/motion_reference_twoline.json` **`2246f83c`**, checkpoint `moe_v13s`
**`61da390a`**, HEAD **`c5c8f25`** at the close-out.

**Nothing was adopted, no default moved, no `src/` or `configs/` file was edited,
and no reference was re-recorded.**
