# P11-B: the "ejection" mechanism, measured directly (the squeeze probe)

Status: **probe runs, standalone** (branch `p-supply`, 2026-10-18; no shipped
default changed; all writes under `logs/p11b/` plus the new
`scripts/210_squeeze_probe.py`). The probe is not a battery: one fruit instance
per class, one arm, one pose, a **stopped belt** and no task loop. It measures
the contact mechanism the P11-A audit (`logs/p11/A_PHYSICS_AUDIT.md`) reads out
of the tree and the P10-E logs.

**The question.** The audit's mechanism sentence: the control can command the
jaws to a keep-gap **1.7-17.5 mm narrower than the fruit** (up to -18.4 mm in
the enumerated P10-E pairs) under a saturated 10 N drive; the rigid fruit cannot
absorb the interference, so it "becomes fruit motion" - a wedge launch the audit
estimates at **50-200 m/s^2** (>1 m/s in a few ticks), with only **0.33 mm** of
elastic give at the 30 kN/m contact. P11-B measures the interference -> motion
transfer directly, plus the sensitivity to the contact parameters and the
free-fall baseline the log falls are attributed to.

## 0. The answer in one screen

* **The escape-threshold interference: there is no commanded gap that launches
  the fruit.** The jaws **stop at the fruit's surface** (a link-origin span of
  **62.3-62.7 mm** on the 51.0 mm tomato; **75.6 mm** on the 64.5 mm apple)
  whatever gap is commanded below that: over **20 mm of commanded interference**
  (delta = -5 ... 15 mm, commanded gaps 56 down to 36 mm) the `air` and `plow`
  groups are **bit-identical** - the achieved state does not depend on the
  commanded depth at all. The threshold that exists is the **blocking span**
  (extent + ~11 mm of link span for this hand + fruit); commanded gaps at or
  above it (`-15` anchors: 66.0 mm) leave the pads 0.14 N / no motion.
* **The peak velocities (plow: WITHDRAWN per R1 - see the amendment).** The plow
  group's **0.202 m/s peak, 35.8 mm displacement, +31.9 mm up** measured the
  probe's own rise-and-return, not the shipped re-seat descent; the corrected
  re-run decides what a true descent does. The `air` climb (**0.082 m/s, 13.1 mm
  in 1.5 s**; 46.6 mm total from the settle) and the `belt` no-motion stand. The held-fruit climb (`air`) is **0.082 m/s, 13.1 mm in 1.5 s**.
  The supported fruit (`belt`) does not move (0.0 mm; its 0.01-0.08 m/s "peak"
  is a tick-scale rattle). The implied acceleration is **~10-20 m/s^2** - 2.5-10x
  below the audit's lower bound, because the real contact force is ~4.5 N and
  the wedge at the tapered tips is shallower than the audit's 30-45 deg.
* **The compliance/substeps do not move it.** Across the four parameter
  variants (substeps 4, finger k 4 kN/m, fruit-side k 4 kN/m, restitution 0.5)
  the re-seat escape is **0.190-0.203 m/s** (±3 %) and the displacement
  32.1-36.0 mm. What *does* move: the **force reading** doubles at 480 Hz
  (4.5 -> **10.1 N**, the drive cap) and the supported-case rattle halves at
  k = 4 kN/m (0.015 -> 0.007 m/s). The grip-depth geometry is flat in the clean
  range (+20 mm: identical; -10 mm: the fingertips enter the belt slab, a jam).
* **The drop baseline confirms the log falls' attribution**: a 1.17 m free fall
  lands at **4.74-4.82 m/s** (expected 4.791 + the integrator's `g*dt/2`),
  against the P10-E in-hand |v|max band 4.78-5.05 m/s.


---

## AMENDMENT (2026-10-18, the Oracle gate's R1-R5; BEFORE the corrected plow re-run)

**R1 (blocking) - the `plow` group did NOT run the shipped geometry.** The probe's plow
closed the pads to the sweep gap **at the grip pose (on the fruit)** and its descent loop's
first target sat +40 mm above the jaw's start, so the jaws **rose first and returned**,
carrying the fruit. The probe's own trace proves the escape precedes any descent
(`04_trace_tomato.log` plow-d15-r0: tick=0, |v|=0.172, dx=-5.0 mm, F=4.73 N - the fruit is
already moving at the loop's start). **Therefore the "the descending jaws eject the fruit"
reading is WITHDRAWN; the plow's 0.202 m/s / 35.8 mm numbers are the probe's rise artifact,
not the re-seat's mechanism.** The probe is patched (the jaw raises to the +40 start BEFORE
the pads close on air, so the loop is a pure descent) and the corrected plow re-run is queued
(logs/p11b/90_plow_fix_*.log); this report will be updated from it. **What stands:** the
"no commanded gap launches the fruit" negative (the pads stop at the surface; the flat sweep);
the `belt`/`air` close-from-open groups never ejecting; the parameter insensitivity; the drop
baselines. **What the corrected run must decide:** whether a true descend-onto-the-fruit at a
contacting gap ejects (the P10-E log evidence says the shipped re-seat does; the probe must
now reproduce the geometry to confirm).
**R2** - the identity claims are scoped to delta 0..+15; the -5 cells differ (air 0.081 vs
0.082; plow -5-r0 0.218/44.9); no field is bit-identical across cells - "identical in the
quoted state fields".
**R3** - the probe pin: the record's `dfa3c935` is the delivered file; the pinned copy
`51b1c91c` covered runs 10/20 only (the 02:34:51 edit falls inside `20_sweep_apple`); runs
30-80 ran the delivered version.
**R4** - the `air` group's reference is taken after its 50 mm lift (every air row
`lift_dz_mm=+33.5`), while the plow's is pre-close: the air/plow "0/3 vs 3/3" is partly a
windowing asymmetry; the air's total fruit climb (46.6 mm) exceeds the plow's (35.8 mm).
**R5** - the "because the real contact force is ~4.5 N" clause is the instrument's under-read
(at `FRUIT_SUBSTEPS=4` the same escape reads 10.1 N); the variant spread is -6 %..+0.5 %; the
shipped close is the two-phase 24+60-tick shape; the 50 mm lift is the probe's own; the
finger-belt jam at pad-lift -10 (F 26.3-89.1 N) is a jam, not a clean no-shove.

## 1. The probe (what it does, and the geometry it reproduces)

`scripts/210_squeeze_probe.py` (new file, no existing script edited) builds the
shipped cell (`environment`, `pedestal`, `robot`, `conveyor`; the same parts as
`55_grasp_sweep` / `144_contact_face_probe`), poses the **left** arm at the
calibrated grasp seed and refines the jaw centre to
`fruit + (FRUIT_FINGER_LEN + FRUIT_PAD_LIFT)` - the shipped dynamic grip
standoff, `tasks.py` `_pad_standoff` - and runs one case per (group, delta,
repeat):

* **`belt`** - the fruit rests on the (stopped) belt at the pick station; the
  jaws close on it from open with the shipped close's min-jerk shape (45 ticks)
  to a hold gap, then the **sweep gap** `extent - delta` is commanded in one
  step and held 0.5 s; the response is measured for 1 s.
* **`air`** - the same close/hold, then the arm lifts 50 mm (the shipped
  close -> probe lift -> regrasp sequence) so the fruit is held with nothing
  under it, then the sweep gap is commanded.
* **`plow`** - the shipped re-seat geometry: the jaws are **already at the
  sweep gap** (closed on air) and descend 40 mm onto the fruit, tracking its
  measured position (the `keep_gap` re-seat loop). This is the P10-E census's
  actual trigger: a position command below the fruit's width, driven into the
  fruit.
* **`drop`** - the fruit is dropped from the belt-top height (1.17 m to the
  floor) as the free-fall baseline.
* **`baseline`** - the jaws close with nothing between them (the
  `55_grasp_sweep` hard-stop control).

The sweep is `delta in {-15, -5, 0, 2, 5, 10, 15} mm` (negative = the commanded
gap is *wider* than the fruit, the no-contact anchor), 3 repeats each.

Measured geometry (tomato: the first tomato of the seeded pool, `d = 51.5 mm`,
45.9 g; the apple run repeats this on its own sample, `d = 63.0 mm`, 91.2 g):

| quantity | tomato | apple |
|---|---|---|
| `extent` (true collider support along the closing axis, from the mesh points) | 51.0 mm | 64.5 mm |
| standoff (jaw centre above the fruit's centre) | 70.0 mm | 70.0 mm |
| measured fingertip depth below the jaw centre | 81.4 mm | 81.4 mm |
| fruit centre vs the fingertip (pads' lower edge below the equator) | +15.4 mm | +18.6 mm |
| pads' hard stop, nothing between them | 12.0 mm | 12.0 mm |
| pads' stop on the fruit (link span) | 62.3-62.7 mm | 75.6 mm |

**The pad-face span is not the link span.** With the fruit present the pads stop
**11.3 mm (tomato) / 11.1 mm (apple) wider than the fruit's extent** while the
same jaws close to 12.0 mm with nothing between them: the stop is the fruit,
contacted by the fingers' *tapered lower region* (~5.5 mm per side inboard of
the link origins at the equator's height). `55_grasp_sweep`'s "the pad surfaces
are essentially at the link origins" was measured at the *jaw-centre* height;
the probe's contacts sit 59-66 mm lower, near the tips. The report quotes the
achieved **link span** and this offset explicitly.

## 2. The drop baseline (the log falls' attribution)

Free fall from the belt top (1.17 m to the floor), 3 repeats per run, 8 runs:
**4.742 m/s @ tick 52** or **4.823 m/s @ tick 53** depending on which tick the
floor contact lands in (the two differ by exactly `g*dt` = 0.082 m/s), against
`sqrt(2*9.81*1.17)` = **4.791 m/s** and the P10-E in-hand |v|max band
**4.78-5.05 m/s**. The build reproduces the free-fall speed the P10-E falls are
attributed to.

## 3. The sweep: the commanded sub-width gap is not realized

`logs/p11b/10_sweep_tomato.log` (shipped contact parameters, 3 repeats each;
`logs/p11b/parse.py` re-derives the table and the two derived interference
columns it quotes: `intf_cmd = extent - gap_cmd`, the commanded interference,
and `intf_span = extent - span_end`, the achieved interference in link-span
terms - **-11.3 mm at delta 0**, i.e. the pads stop 11.3 mm wider than the
fruit):

| group | delta [mm] | gap cmd [mm] | achieved link span [mm] | outcome (n=3) | peak |v| fast [m/s] | displacement [mm] | dz [mm] | F finger [N] |
|---|---|---|---|---|---|---|---|---|
| belt | -15 | 66.0 | 66.0 | 3 stayed | 0.007-0.008 | 0.0 | 0.0 | 0.14 |
| belt | -5 | 56.0 | **62.3** | 3 stayed | 0.010 | 0.0 | 0.0 | 4.54 |
| belt | 0 | 51.0 | **62.3** | 3 stayed | 0.013-0.015 | 0.0 | 0.0 | 4.54 |
| belt | 2 | 49.0 | **62.3** | 3 stayed | 0.026-0.028 | 0.0 | 0.0 | 4.55 |
| belt | 5 | 46.0 | **62.3** | 3 stayed | 0.027-0.034 | 0.0 | 0.0 | 4.55 |
| belt | 10 | 41.0 | **62.3** | 3 stayed | 0.032 | 0.0 | 0.0 | 4.55 |
| belt | 15 | 36.0 | **62.3** | 3 stayed | 0.032-0.033 | 0.0 | 0.0 | 4.55 |
| air | -15 | 66.0 | 66.0 | 3 hold_failed | 0.002-0.024 | 0.2-0.7 | 0.0 | 0.00 |
| air | -5 | 56.0 | **62.4** | 3 stayed | 0.081 | 13.1 | +13.0 | 4.56 |
| air | 0..15 | 51..36 | **62.4** | 3 stayed each | 0.082 | 13.1 | +13.0 | 4.49 |
| plow | -15 | 66.0 | 66.0 | 3 stayed | 0.025-0.048 | 11-15 | 0.0 | 3.5-4.3 |
| plow | -5 | 56.0 | 61.5-62.7 | **3 escaped** | 0.202-0.218 | 35.4-44.9 | +31.9 | 4.6-4.7 |
| plow | 0..15 | 51..36 | **62.6-62.7** | **3 escaped each** | **0.202** | **35.8** | **+31.9** | 4.59-4.71 |

**The result is the flatness.** Across 20 mm of commanded interference the
**achieved** state is the same to the third digit in the `air` and `plow` groups
(13.1 mm / +13.0 mm / 0.082 m/s; 35.8 mm / +31.9 mm / 0.202 m/s, bit-identical
repeats), and in the `belt` group the net displacement is 0.0 mm at every delta.
The jaws **stop at the fruit's surface**, not at the commanded gap, and the
drive's force cap means the extra commanded depth changes nothing (the force
reads 4.5-4.7 N at every delta; see the instrument caveat in section 6).

The **escape threshold** is therefore not a property of the commanded gap: it is
the **blocking span**, measured at **extent + ~11 mm of link span** for this
hand + fruit. A commanded gap above it (the `-15` anchors: 66.0 mm) leaves the
pads short of the fruit in the close geometry (0.14 N, no motion; the `plow`
group's descent at the same gap still brushes the fruit for 11-15 mm as the
jaws pass its flanks), and every commanded gap below it produces the *same*
saturated contact. The audit's picture ("the commanded interference becomes
fruit motion") does not hold in the close geometry: the interference is **not
realized at all**; what the fruit receives is a contact at its surface with a
saturated drive.

What motion there is:

* `belt` (the fruit supported): **no net motion** (0.0 mm). The 0.01-0.03 m/s
  "peak" is the payload's tick-scale **rattle** inside the closed pads (the
  trace alternates 0.011 <-> 0.079 m/s and 0.1 mm of z every tick - the same
  impulse contact the WORKLOG's "payload rattles at 0.3-0.7 m/s" describes),
  and its amplitude grows mildly with the commanded depth while the position
  does not move.
* `air` (the fruit held): the fruit **climbs out of the pinch** at a decaying
  0.03-0.08 m/s, 13.1 mm in the 1.5 s window - a slow wedge lift, not a launch.
  It starts at the *hold*, before the sweep command (the trace's tick 0 already
  reads 0.082 m/s), which is why the sweep is inert here.
* `plow` (the re-seat geometry): the strike displaces the fruit **35.8 mm at
  0.202 m/s peak** (dz +31.9 mm up, dx -16 mm across the belt; `v_esc`
  0.176 m/s at the 20 mm crossing, tick 12). This is the fastest squeeze-out the
  probe produces, and the only group where the case classification changes
  (`escaped`). It is a *squeeze-out*, not a launch: the fruit ends resting on
  the pads' lower edges, ~32 mm above its start, and the whole displacement is
  36 mm.

The **measured acceleration** implied by the plow: 0 to 0.17 m/s in one control
tick (8.3 ms) = **~20 m/s^2**, and the peak 0.202 m/s two ticks later; the air
climb is ~10 m/s^2. The audit's estimate is **50-200 m/s^2** - the measured
transfer is **2.5-10x below its lower bound**, because the actual contact force
is ~4.5 N (not 10-20 N) and the effective wedge angle at the tapered tips is
smaller than the audit's assumed 30-45 deg.

## 4. The parameter sensitivity

Every variant repeats the full sweep (63 cases). The escape speed is the `plow`
group's peak (the strongest squeeze-out); the "belt rattle" is the supported
case's tick-scale peak.

| run | change | achieved link span (belt, delta 0) | belt peak [m/s] | air climb [mm] | plow peak [m/s] / disp [mm] | F finger [N] |
|---|---|---|---|---|---|---|
| `10_sweep_tomato` | shipped (k=30 000 N/m, substeps 1, e=0.02-0.2) | 62.3 | 0.013-0.015 | 13.1 | 0.202 / 35.8 | 4.5 |
| `30_sweep_tomato_substeps4` | `FRUIT_SUBSTEPS=4` (480 Hz physics) | 62.2 (extent 51.2) | 0.035-0.039 | 13.4 | **0.190** / 32.1 | **10.0-10.3** |
| `40_sweep_tomato_k4000` | finger compliance 30 000 -> **4 000** N/m | 62.3 | **0.007-0.009** | 13.1 | 0.203 / 35.6 | 4.5 |
| `50_sweep_tomato_fruitsoft` | fruit-side compliant material **4 000** N/m | 62.3 | 0.014 | 13.1 | 0.201 / **34.8** | 4.6 |
| `60_sweep_tomato_rest05` | fruit restitution **0.5** | 62.3 | 0.022 | 13.1 | 0.202 / 36.0 | 4.5 |
| `70_sweep_tomato_padm10` | grip depth **-10 mm** (`FRUIT_PAD_LIFT`; fingertips 0.6 mm inside the belt slab) | 66.7 (a belt jam) | 0.002 | 12.9 | 0.51-0.59 / **2.2** (rattle, no displacement) | 27-89 |
| `80_sweep_tomato_padp20` | grip depth **+20 mm** (pads' lower edge 8.5 mm below the equator) | 62.4 | 0.007 | 13.1 | 0.203 / 36.5 | 4.5 |
| `20_sweep_apple` | apple (d 63.0 mm, extent 64.5 mm) | 75.6 | 0.05-0.077 | 13.1 | 0.202 (one repeat 0.302) / 38.0 | 4.8-5.1 |

**What moves, and what does not.**

* **Substeps (1 -> 4): the force reading doubles, the outcome does not.** At
  480 Hz the tactile reads the full **10.0-10.3 N** drive cap at the saturated
  stop; at the shipped 1/120 s single substep the same stop reads **4.5 N**.
  The escape speed *falls* slightly (0.202 -> 0.190 m/s, -6 %) and the plow
  displacement 35.8 -> 32.1 mm (-10 %); the sweep is still flat in delta. So the
  audit's "the 1/120 s step turns the contact into an impulse" is visible in the
  **force instrument** (a ~2.2x under-read at the shipped step) but not in the
  motion: the fruit does not launch at either rate.
* **Finger compliance (30 kN/m -> 4 kN/m): the rattle halves, the escape does
  not move.** The supported case's tick-scale peak falls 0.013-0.015 ->
  0.007-0.009 m/s (a softer contact jitters less), the air climb is unchanged
  (13.1 mm) and the plow escape is unchanged (0.203 m/s / 35.6 mm). The audit's
  "0.33 mm of elastic give at the force limit" is a *compliance* statement: it
  damps the contact rattle but does not govern whether the fruit leaves.
* **Fruit-side compliance (authorable post-play per material): a 3 % effect.**
  The per-material `physxMaterial:compliantContactStiffness` on the fruit's own
  material prim takes effect (the plow displacement moves 35.8 -> 34.8 mm with
  the pose identical) and leaves everything else unchanged. It is *not* a fix
  for the escape at the probe's forces.
* **Restitution (0.02-0.2 -> 0.5): inert**, as the audit predicted - the
  escape velocities and displacements are identical within the repeat spread.
  (The restitution shapes the bounce *after* a fall; the probe's falls are the
  drop baseline, where the landing speed is unchanged.)
* **Grip depth (the wedge angle): flat in the clean range.** At +20 mm
  (the pads' lower edge 8.5 mm below the equator instead of 15.4 mm) every
  number matches the shipped run (0.203 m/s / 36.5 mm). At -10 mm the
  *fingertips* (0.6 mm) enter the belt slab and the run becomes a finger-belt
  jam: 27-89 N of contact force, a 0.51-0.59 m/s rattle with **2.2 mm** of
  displacement and no lift - the deep grip is a jam, not a stronger ejection.
  This is the probe's counterpart of the shipped `s1_padm8`/`s2_padm15` screens
  (4/10, 2/10: deeper grips were *worse* on the line).
* **The class**: the apple (63.0 mm, 91.2 g) reproduces the tomato's numbers
  almost exactly - same flat sweep, air climb 13.1 mm, plow 0.202 m/s / 38.0 mm
  (one repeat of the delta-0 case strikes the apple 10 mm off-centre and reads
  0.302 m/s / 7.5 N, still `escaped`) - so the mechanism is not a light-fruit
  artifact (the apple is 2x the mass).

## 5. Against the P11-A audit's predictions

| audit claim | probe measurement | verdict |
|---|---|---|
| the control commands a keep-gap 1.7-17.5 mm narrower than the fruit; the interference "becomes fruit motion" | the jaws **stop at the fruit's surface** (link span 62.3-62.7 mm on a 51.0 mm fruit; 75.6 mm on a 64.5 mm apple) and the response is **flat** over 20 mm of commanded interference (bit-identical `air`/`plow` rows from delta -5 to 15) | **revised**: the commanded interference is not *realized*; the pads stop at first contact and the force-capped drive makes the extra depth inert. The census's "keep_gap 1.7-17.5 mm inside the fruit" is a **command** number, not an achieved one |
| a 10-20 N push at a 30-45 deg wedge = **50-200 m/s^2**, ">1 m/s in a few ticks" | the fastest squeeze-out (plow) is **0.202 m/s** (0 -> 0.17 m/s in one tick = ~20 m/s^2); the held-fruit climb is 0.082 m/s (~10 m/s^2); the supported fruit does not move | **not reproduced**: 2.5-10x below the audit's lower bound; the actual contact force is ~4.5 N (tactile) and the effective wedge angle at the tapered tips is smaller than 30-45 deg |
| the elastic give is **0.33 mm** at the 10 N limit (k = 30 kN/m), so the interference cannot be absorbed | at 4 kN/m the supported-case rattle halves (0.015 -> 0.007 m/s) and the escape is unchanged; at 30 kN/m the pads' stop is the same | **consistent as a statement about absorption, but it does not gate the ejection**: the compliance absorbs the *jitter*, not the *outcome*; the stop is geometric (the pads meet the fruit), not elastic |
| the B1 falls end ~1.3 m below the belt top with in-hand |v|max 4.78-5.05 m/s = free fall from 1.17 m | the drop baseline reproduces **4.74-4.82 m/s** for a 1.17 m fall (expected 4.791 + the integrator's `g*dt/2`) | **confirmed**: the log falls are free-fall speeds of a fruit that has left the grip; the probe shows the squeeze itself leaves the fruit *in* the pinch (13-36 mm of displacement), so the fall follows the grip loss, not a ballistic launch |
| the 4/30 solver blowups (|v|max up to 12 km/s, clean_slip up to 100 m) | no blowup in the 8 probe runs (504 cases + 24 drops + 8 hard stops); the largest fruit speed is 0.586 m/s (the deep-grip jam) | the probe's geometry does not reach the blowup branch (no 15 mm *realized* interference); the blowups live in the shipped re-seat's own state, not in a static squeeze |

## 6. Honest limits

1. **A probe is not the battery.** One fruit instance per class (the first of the
   seeded pool), the left arm, one pose, a **stopped belt** and no task loop. The
   shipped B1 runs mid-carry: the hand is moving, the belt is running, the
   payload is already in a marginal grip, and the re-seat is preceded by the
   force-servo chase. The probe reproduces the *contact geometry* of the
   re-seat (jaws at a sub-width gap descending onto the fruit) and measures the
   transfer; it does not reproduce the chase's timing or the carry motion.
2. **The pad-face span is not the link span.** The fingers taper: the jaws stop
   11.3 mm wider than the fruit's extent (51.0 -> 62.3 mm; apple 64.5 -> 75.6),
   so the contacting surfaces sit ~5.5 mm per side inboard of the link origins at
   the equator's height. The report quotes the **achieved link span** and the
   measured offset; the per-side AABB clearance readout is asymmetric
   (+10.6/+23.8 mm) and is quoted only as a hint.
3. **The force instrument under-reads at the shipped step.** The finger drive is
   capped at 10 N per joint; the tactile reads 4.5 N at the saturated stop at
   `FRUIT_SUBSTEPS=1` and 10.1 N at `FRUIT_SUBSTEPS=4`. The achieved span is the
   mechanical truth; the force column is the shipped instrument's reading. The
   fruit-side net contact force could not be read at all in this probe (the
   fruit prims are authored before `play()` for the material knob, so their
   contact view is invalid; `F_fruit` reads 0.0 in every row).
4. **The deep-grip variant is confounded**: at `FRUIT_PAD_LIFT=-0.010` the
   fingertips sit 0.6 mm inside the belt slab at this standoff, so its
   27-89 N forces and 0.5 m/s rattle are a finger-belt jam; only its
   *displacement* result (2.2 mm, no lift) is interpreted, and the clean
   geometry contrast is the +20 mm variant.
5. **The probe's own determinism.** Each case re-places the fruit and re-seats
   the arm, so the repeats are near-identical (bit-identical in most cells);
   the first case of a group can differ slightly (e.g. `plow-d-5-r0` 44.9 mm vs
   the later 35.8 mm) because the arm's IK state carries over.
6. **Provenance note.** The batch's tree pin (`logs/p11b/00_tree_pins.txt`)
   records `scripts/210_squeeze_probe.py` at md5
   `dfa3c9358c4ab29eff98155ba557c71d`, the delivered file's md5. During the
   batch the probe's header docstring and comments were revised (no behavioural
   line changed - the unused `FRUIT_SQUEEZE_LIFT_TICKS` constant was dropped and
   the header text brought up to date), so the runs and the delivered file are
   the same code path.
7. **No shipped number is touched.** The probe is env-only, it edits no existing
   script, and it makes no claim about the acceptance line or the two-line rate.

## 7. Runs and reproduction

| log | class / variant | cases | wall |
|---|---|---|---|
| `10_sweep_tomato.log` | tomato, shipped | 63 + baseline + 3 drops | 4.5 min |
| `20_sweep_apple.log` | apple, shipped | 63 + baseline + 3 drops | 4.6 min |
| `30_sweep_tomato_substeps4.log` | tomato, `FRUIT_SUBSTEPS=4` | 63 + baseline + 3 drops | 13.2 min |
| `40_sweep_tomato_k4000.log` | tomato, `FRUIT_FINGER_COMPLIANCE=4000` | 63 + baseline + 3 drops | 4.4 min |
| `50_sweep_tomato_fruitsoft.log` | tomato, `FRUIT_SQUEEZE_FRUIT_COMPLIANCE=4000` | 63 + baseline + 3 drops | 4.4 min |
| `60_sweep_tomato_rest05.log` | tomato, `FRUIT_SQUEEZE_FRUIT_RESTITUTION=0.5` | 63 + baseline + 3 drops | 4.4 min |
| `70_sweep_tomato_padm10.log` | tomato, `FRUIT_PAD_LIFT=-0.010` | 63 + baseline + 3 drops | 18.9 min (the claim waited) |
| `80_sweep_tomato_padp20.log` | tomato, `FRUIT_PAD_LIFT=+0.020` | 63 + baseline + 3 drops | 4.3 min |

Every run: `scripts/154_claim_run.sh <log> ENV=... scripts/run.sh
scripts/210_squeeze_probe.py` (the driver is `logs/p11b/run_sweeps.sh` /
`run_padlift.sh`; the tree pins are `logs/p11b/00_tree_pins.txt`).

Design-validation runs (not part of the tables, kept for the traces):
`00_smoke_tomato.log` (the first end-to-end smoke), `01_smoke_tomato.log`
(the contact-view fix), `02_diag_tomato.log` / `03_diag2_tomato.log` (the
clearance/baseline diagnostics that found the arm-restore bug), `04_trace_tomato.log`
(the per-tick `[squeeze-t]` traces quoted in section 3), `05_smoke_nc_tomato.log`
(the no-contact anchor check).

Re-derive the tables (the combined output is archived at
`logs/p11b/99_all_tables.txt`):

```bash
python3 logs/p11b/parse.py logs/p11b/10_sweep_tomato.log logs/p11b/20_sweep_apple.log \
    logs/p11b/30_sweep_tomato_substeps4.log logs/p11b/40_sweep_tomato_k4000.log \
    logs/p11b/50_sweep_tomato_fruitsoft.log logs/p11b/60_sweep_tomato_rest05.log \
    logs/p11b/70_sweep_tomato_padm10.log logs/p11b/80_sweep_tomato_padp20.log
```

One case, verbatim (`logs/p11b/10_sweep_tomato.log`):

```
[squeeze] case=plow-d15-r0 group=plow class=tomato extent_mm=51.0 gap_cmd_mm=36.0
sep_end_mm=62.7 span_end_mm=62.7 off_tool_mm=+68.3 off_axis_mm=+6.3 in_span=1
peak_v_fast=0.202@2 peak_v_all=0.202@2 v_esc=0.176@12 disp_mm=35.8 dx_mm=-16.3
dy_mm=-1.9 dz_mm=+31.9 F_finger_peak=4.59N F_fruit_peak=0.00N contacts=2
clear_l=-1.7 clear_r=+36.0 finger_z=[-52.6,+34.1] outcome=escaped
```

## 8. What this means for the control-side fix (P11-C)

The audit's control-side recommendation (floor the keep-gap at the measured
extent, stop the chase, cap the ratchet) is **only partly supported by the
probe**, and the probe sharpens where the lever actually is:

* The **commanded** keep-gap is not the lever. Over 20 mm of commanded
  interference (including a gap 5 mm *wider* than the fruit) the re-seat shove
  is identical (35.8 mm at 0.202 m/s, 3/3 bit-identical). A floor at the
  *extent* (the audit's `max(squeeze_gap, live_extent - margin)`, margin 0-1 mm)
  would command ~51 mm for this 51.0 mm tomato - still **11 mm below the
  blocking span** (62.3 mm) at which the pads meet the fruit - so it would not
  change the arrival contact in this geometry.
* The lever the probe *does* see is the **arrival geometry** - but with R1's
  correction the probe's own plow cannot yet demonstrate it: the measured shove
  was the probe's rise artifact; the `belt`/`air` negatives (close-from-open
  never ejects) stand, and the corrected plow re-run must show whether a true
  descend-at-a-contacting-gap ejects. The P10-E log chain remains the task-level
  evidence for the re-seat's ejection.
  For this hand + fruit the blocking span is `extent + ~11 mm` of link span; a
  keep-gap floor would have to sit there, or the re-seat must approach without
  driving the pads into the fruit at all.
* The probe cannot speak to the **chase** (the 15 mm force-servo walk) or the
  **ratchet**: those live in the shipped task loop's state, not in a static
  squeeze. The audit's argument for stopping them (they create the sub-width
  command in the first place) is untouched by this probe - but the probe's
  evidence is that the *command* is not what displaces the fruit.

The probe also gives the P11-C physics-side option (a) a measured baseline: the
fruit-side compliance is authorable per material and moves the re-seat
displacement by 3 %; it does not stop the squeeze-out. The parameters that move
the *instrument* (substeps 4: the force reading; k 4 kN/m: the rattle) do not
move the *outcome*.
