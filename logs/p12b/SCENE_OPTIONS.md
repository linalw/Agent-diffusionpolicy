# P12-B.2 SCOPING (Tier C offline): the scene-side iteration for the two-line — the design space, the recommendation, the honest constraints

Status: **offline scoping, read-only** (branch `p-supply`, 2026-10-18; no simulator run — the
P12-B.1 compound battery was running in `logs/p12a2/92_compound_driver.log` throughout and was
not touched; no `src/`, `scripts/`, `configs/`, `datasets/`, `Paper/` write; all writes under
`logs/p12b/`). Tree pins as read (`logs/p12b/00_tree_md5.txt`): `tasks.py`
**810658b802d22bbd63013726fc78af81** (== the P11-C battery pin), `scene.py`
`ab85dca250cdd09cc7cbd9893c58fca3` (== the R8-A pin), `conveyor.py`
`2c1a0620d00e329588a7fd87404ff085`, `assets.py` `c27f7440fc09727e5c32e278e7d7c1f4`,
`fruits.py` `d28546d26137d4540421caa7fa34a139`; HEAD `e6e7a46`.

**The mandate.** The owner's directive ("修改场景或属性...在上面的基础上修改完善") sanctions scene
changes; the two-line anchor is the **only re-measured reference**. The P11-C close-out names the
remaining path: "a pick station / an approach geometry that never requires the
descend-onto-the-fruit re-seat" (`logs/p11c/C3_RESULTS.md` §"The conclusion").

**The read list (all read for this scoping).** `logs/p11c/C_RESULTS.md`, `C2_RESULTS.md`,
`C3_RESULTS.md`, `PREREG_REGRASP_ARRIVAL.md`; `logs/p11b/C_DECISION.md`, `B_EJECTION_PROBE.md`
(+ the corrected-plow rows `logs/p11b/90_plow_fix_tomato.log`, `91_plow_fix_apple.log`);
`logs/p11/A_PHYSICS_AUDIT.md`; `logs/p10e/NOGRASP_DIAGNOSIS.md` (+ the raw rows
`logs/p10c/50_seed11_A.log`); `logs/r8/A_RESULTS.md`; `logs/r10/A_RESULTS.md`,
`logs/r10/A1_RESULTS.md`; `logs/r11/A_RESULTS.md`, `A1_RESULTS.md`; `logs/w2/RESULT.md`;
`logs/v1/61_station_reach_seeded.log`; `logs/p12a2/A2_RESULTS.md`; the tree
(`scene.py`, `conveyor.py`, `assets.py`, `fruits.py`, `tasks.py`, `bimanual.py` — read-only).

---

## 0. The answer in one screen

**The finding that decides the design space (derived here, geometry).** The moving catch's
commanded geometry is **fruit-relative**: the aim is the fruit's measured `(x, z)` at
`station_y + lead` (`tasks.py:4473-4494`), the grip/hover points add a **fixed** standoff
(`tasks.py:4517-4526`), the catch-up's break test is the fruit + the pad lift (`tasks.py:7562`,
`8797`), and the re-seat's descent target is the fruit + the same standoff (`tasks.py:8728-8737`).
The only **absolute** constraints in the loop are the belt/surface under the fingers and the
arm's reachable set. **Therefore a station that raises the fruit and its support surface
together (a deck/platform/raised belt section) moves every target and the collision together —
the catch, the close and the re-seat are geometrically invariant; only the absolute heights and
the surface identity change (risk without mechanism).** A station can reach the catch geometry
only by (i) raising the fruit *without* raising the surface under the fingers (a narrow
cradle/ridge the fingers straddle), (ii) changing the fruit's lateral freedom (containment), or
(iii) changing the fruit's *surface drive* — and (i) is measured unstable in its static form
(the nest's own note: 46 mm drifts) and (ii) does not move the close (the jaw is already on the
fruit's measured axis).

**The ranked options (expected movement / cost).**

| # | option (the mission's letter) | the exact change | the expected movement | the cost | verdict |
| --- | --- | --- | --- | --- | --- |
| **S3** | **the approach-height change** [(d), + the (e) pairing] | env-only: `FRUIT_DYNAMIC_PAD_LIFT=+0.020` (the standoff 70 -> 90 mm; the existing knob, `tasks.py:729`) | the finger–belt margin **+20 mm** (certain); the pads' contact ~7 mm nearer the equator (measured mapping); the no-grasp class **unknown** (the probe reads flat in the static case); the falls unknown | one battery arm; zero code | **the pick** (the only lever with a live mechanism on the close's contact geometry) |
| **S4** | **the containment bundle** [(b)/(c), sharpened] | scene: a **belt-end keeper** (a 40–60 mm lip at the main belt's end, `conveyor.py`) + two **side fences** at x <= 0.13 / >= 0.43 (clear of the open hand's ±0.066 span, `assets.py:251`) | the falls **near-certainly down** (the measured exit path is the belt end within the attempt); the class/outcomes **0** (stated) | ~15 lines + one battery arm | **the companion arm** (the certain win; grip-null) |
| **S2** | **the self-centring cradle** [(a) kerbed + (b) containment, merged] | scene: two rails along Y at the station (a flared upstream funnel; static low-kerb form first, a **driven** V form if the lift is wanted), a default-off knob | the re-seat's **lateral escape capped** (the corrected plow's escapes are lateral, dz ~0); the class **maybe** (the contained fruit stays for the later regrasp cycles); the falls down | the highest scene cost; the D3 supply risk | **the named follow-on**, gated on S3 + a trace read |
| **S1** | **the raised station deck** [(a), the raised form] | scene: a full-band raised deck (driven, ramped) at the station | **geometry-null for the catch** (the derivation above); the D3 obstruction class | high | **rejected by analysis** (recorded negative) |
| **S5** | **the station-side backstop / gate** [(b), the strict form] | scene: a per-fruit kerb pair or a stop at the station | a per-fruit backstop is **geometrically infeasible** on the scattered band; a gate **starves the downstream station** (the two-line semantics) | — | **rejected** (recorded negative) |

**The pick: S3 — the approach-height change (`FRUIT_DYNAMIC_PAD_LIFT=+0.020`, two-line battery
arm), with S4's belt-end keeper as the same battery's companion arm.** Rationale: S3 is the only
lever that changes the fruit-relative contact geometry without a surface change, it costs one env
arm, and it is the **screen** any scene build (S2) needs anyway (if the approach height moves
nothing, the cradle's lift mechanism is doubtful too). S4 rides along because it is nearly free
and it is the only *certain* movement available. The pre-registration sketch is §3.

**The strongest reason any of them could fail.** The class's geometric driver is **not
identified by the records**: the no-grasp and ok populations overlap on every logged row
(`logs/p10e/NOGRASP_DIAGNOSIS.md` §2.1), the per-tick pad–fruit geometry was never recorded on
these runs, and the P11-C precedent (the arrival fix moved the mechanism, halved the falls at the
primary, and the class re-drew with a pooled -4) is what a geometry change on this class has
actually done. Every grip-side option here (S1/S2/S3) is therefore a hypothesis test whose most
likely single-battery outcome is a class re-draw without a rate gain; and the **static probe
already reads flat** on the approach-height axis (`padp20`: the plow escape 0.203 m/s / 36.5 mm,
bit-identical to the shipped run, `logs/p11b/B_EJECTION_PROBE.md` §4) — if that flatness carries
to the dynamic close, the whole named-path geometry family closes (hand-side and scene-side) and
the measured wins remain the containment (S4) and the physics lane (P12-A).

---

## 1. The geometry that decides the design space

Everything below is either (M) measured in the cited record or (D) derived here from the tree +
the records. The derivation matters because it *deletes* options before they cost a battery.

### 1.1 The catch is fruit-relative (D)

| command | formula | site |
| --- | --- | --- |
| the aim | `[fruit_x, station_y + lead, fruit_z]` | `tasks.py:4473-4494` (`_dynamic_aim`) |
| the grip point | the aim + `[0, 0, finger_len + pad_lift]` (a **fixed** 70 mm standoff at the shipped values) | `tasks.py:4517-4519`, `4508-4512` |
| the hover | the grip + `FRUIT_DYNAMIC_HOVER` (0.06 m) | `tasks.py:4521-4526` |
| the catch-up break test | `fruit + _dynamic_pad_lift` | `tasks.py:7562`, `8797` |
| the re-seat descent | `fruit + [0,0,standoff] + [0, vy*lead, 0]` | `tasks.py:8728-8737` |

So the entire close/hold/re-seat chain is the fruit's measured pose plus constants. The only
absolute geometry: the belt/surface under the fingers (the collision that stops the deepest
descent, `scripts/47_robot_collision.py`: the jaw stops at z = 1.247 = belt_top + 0.077 with the
finger geometry inside the belt), the arm's reachable set (the IK residual), and the pre-pose.

### 1.2 The measured constraints the design must respect (M)

* **The blocking span**: the pads stop on the fruit at a link span of **extent + ~11 mm**
  (tomato 51.0 -> 62.3 mm; apple 64.5 -> 75.6 mm); the standoff is 70.0 mm; the fingertips hang
  81.4 mm below the jaw centre; the pads' contact sits near the tips (59–66 mm below the jaw),
  on the fruit's tapered lower region (`logs/p11b/B_EJECTION_PROBE.md` §1).
* **The ejection geometry**: the **close-from-open never ejects** (belt 0/3, air 0/3 at every
  delta); the **descend-at-the-contact-gap does**, at the deeper interferences — corrected plow
  (M): tomato stays at delta -15..+5, escapes at +10/+15; apple stays at delta <= 0, escapes at
  +2..+15; the escape displacements 20–75 mm (the classified escapes 20–58 mm; one `out_of_span`
  at 75 mm), **lateral** (dx ±18–32 mm, dz ~0–3 mm), the deep descents' finger force 114–175 N
  (tomato) / 12–23 N (apple) (`logs/p11b/90/91_plow_fix_*`).
  The P10-E keep-gaps were 1.7–17.5 mm **inside** the extent in 15/18 B1 cases (`logs/p10e/`).
* **The reach band at the grip height** (`scripts/174_station_reach.py`, `logs/v1/61_...`): the
  IK residual is **5.7–6.0 mm against the 6 mm tolerance across the whole delivered band**
  (dx -0.16..+0.05, x = 0.186–0.386) with the **hard cliff at x = 0.426 (55.3 mm)**; the supply
  band is x = 0.20–0.36 (`fruits.py:232-233`), and the belt's own drift reaches x = 0.148.
  The per-arm reachable-intercept bands (R10-A, relative to each arm's station, 6 mm, inset by
  `FRUIT_REACH_Y_INSET`; `tasks.py:506-528`): **left** x=0.20 -0.10..+0.15, x=0.28 -0.05..+0.10,
  x=0.36 0.00..+0.10; **right** x=0.20 -0.10..+0.10, x=0.28 -0.10..+0.05, x=0.36 -0.10..0.00.
* **The catch-up's floor** is 5.3–6.0 mm (the loop's threshold-crossing value, `logs/r8/A_RESULTS.md`
  §2) and the two-line patch descents end **8.3–13.6 mm short** (`logs/p11c/10_seed11_A.log`,
  `end=` rows) — the boundary strain on this scenario is small; the AGENTS §2 "40–90 mm short"
  is the older shipped-acceptance record, not this battery's.
* **The open hand's span**: ±0.066 m (`assets.py:251`) — any station device in the catch's
  descent volume must clear it.
* **The two-line geometry**: stations y = 0.0 / -0.10 (0.10 m apart, `tasks.py:4802-4804`); the
  moving catch rides the belt ~0.15–0.22 m through its dwell (W2), longer than the reachable
  station separation (<= 0.18 m); clearance min 13.9 mm / 62 of 10672 samples < 30 mm on the W2
  branch, min 2.59 mm / 8.6 % on the W7-A dense branch; **no arm–arm contact is possible**
  (`enabledSelfCollisions = 0`, the asset line 6782) and no attempt has ever failed by contact.
* **The supply**: the W6-A patch sheet (0.14–0.22 m along-slices, 1–2 fruit abreast, pair
  probability 0.6, 0.085–0.12 m separation) fed by the scattered feeder; the feeder and the
  recycle run at **attempt boundaries only** (`tasks.py:5226`, `5232`).
* **The D3 lesson** (M): a 100 mm-wide platform (x = 0.29–0.39) with 20 mm side faces in the
  flow path obstructed the moving supply — `recirculated` 0 -> 13, battery 1/20 x2, a new note
  "fruit never settled at the pick point", the direct no-contact 2 -> 12 (`logs/r8/A_RESULTS.md` §4).

### 1.3 What the derivation buys (D)

1. **A wide raised station (a deck, a platform, a raised belt section) is catch-null**: the
   targets and the local surface rise together; the close, the catch-up and the re-seat are
   unchanged. The naive "raise the pick station" (the README's "Known limit" direction, the
   R8-A D3 form) does **not** by itself change the grip geometry — it only adds supply risk.
2. **A narrow raised cradle (the fingers straddle it) does change the margin**: the targets rise
   while the surface under the fingers stays low — but a **static** narrow ridge is measured
   unstable (46+ mm drifts, the nest's note) and it **gates** (a fruit on a static, undriven
   surface stops — the v2 `FRUIT_PICK_STOP` semantics). The stable/undriven form is a wide
   platform (catch-null); the driven form is a new build (S2).
3. **A centring device does not change the close's relative geometry**: the jaw is already on the
   fruit's measured axis (the catch descends onto the fruit's measured x). What centring can buy
   is a *uniform* absolute x — but the reach residual is at the tolerance across the whole band,
   so the margin gain is ~0. What it *does* buy is containment (S2) and the supply's
   repeatability.
4. **The only fruit-relative lever without a surface change is the standoff** — i.e. the hand's
   approach height (S3). The probe's mapping: +20 mm of standoff moves the pads' lower edge from
   15.4 to 8.5 mm below the equator (6.9 mm of contact-height change per 20 mm), and raises the
   fingertips 20 mm relative to the belt (`logs/p11b/B_EJECTION_PROBE.md` §4).
5. **The D2a's asymmetry is a *loop-equilibrium* effect, not a contact-height effect**: the
   `FRUIT_GRIP_PLANE_DROP` moves the commanded target (the standoff) but **not** the catch-up's
   break test (`desired_tip`), so the loop's equilibrium shifts by the drop — the 14/15 catch-up
   caps are expected even with a reachable target (R8-A's own reading). A `FRUIT_DYNAMIC_PAD_LIFT`
   change moves **both** the standoff and the break test (`_pad_standoff` uses
   `_dynamic_pad_lift`; the break test uses `_dynamic_pad_lift`) — **no equilibrium shift**. That
   makes S3 a *clean* geometry change where D2a was a confounded one.

---

## 2. The design space (5 options, bounded)

### S1 — the raised station deck [the mission's (a), the raised form]

* **Exact change.** `conveyor.py`: a new default-off builder (e.g. `FRUIT_STATION_DECK=1`) — a
  kinematic deck with `PhysxSurfaceVelocityAPI` at the belt speed (the belt's own authoring
  pattern, `conveyor.py:115-130`, incl. the `_surface_attr_speed` scaled-frame division), top at
  belt_top + 0.015–0.025 m, spanning the delivered band (x ~= 0.185–0.41), driven ramps both Y
  ends (a static ramp stops the fruit: mu 0.8–0.9 decelerates a fruit at ~6–9 m/s^2 — a 15 mm
  rise is a 13 ms stop; that is the v2 gate). Fields in `assets.py::SceneConfig` (the existing
  `nest_*` family, `assets.py:276-285`).
* **The mechanism claim.** The named path: the hand reaches the fruit clear of the belt; the
  descent's boundary strain drops; the pads contact nearer the equator.
* **The mechanism, measured against the derivation.** Catch-null (§1.3.1): the fruit-relative
  targets and the local surface rise together; the *relative* contact, the catch-up and the
  re-seat are unchanged. The only absolute changes: the transfer heights (the lift to the output
  belt shortens — negligible) and the surface's identity (a new drive element). The D2a's
  -8 mm catastrophe does **not** predict a +20 mm benefit (that was an equilibrium shift, §1.3.5).
* **The expected movement.** The falls/class/outcomes: **~0 by construction**; the descents'
  `end=`/budgets: unchanged (the commanded pose is fruit-relative); the risk: the supply.
* **The cost.** The scene builder + the standard two-line battery x2 per arm + the acceptance
  no-harm; the highest implementation risk of the scene options (a driven deck + ramps + the
  belt-deck transitions).
* **The risks.** The D3 obstruction lesson is *the* risk: any edge/step in the moving supply's
  path (the ramps' ends, the deck's side faces) is the measured failure class; the deck's
  surface-velocity authoring on rotated ramp bodies; the deck's transitions perturbing small
  fruit (the drift tail x = 0.148); the two-line's dwell sweep riding *through* the deck's edges.
* **The falsifier.** A battery that shows the class/falls unchanged (expected) **or** the supply
  moving (`recirculated` up, a "never settled" note, a rate collapse — the D3 replay). Either
  outcome closes the form.

### S2 — the self-centring cradle [the mission's (a) kerbed + (b) containment, merged]

* **Exact change.** `conveyor.py`: a default-off cradle builder (`FRUIT_STATION_CRADLE=1` +
  sub-knobs: the channel width, the kerb height, the V angle, driven/static) — two rails along Y
  at the station spanning both stations' dwell (y ~= +0.15..-0.35), a flared upstream funnel to
  bring the scattered band (x = 0.20–0.36) into the channel. **The static form**: kerb tops at or
  below the finger tips' height (fruit-relative: r - 11.4 mm + ΔS; 3.6 mm for a 28 mm lychee,
  23.6 mm for a 70 mm apple) so the descending fingers clear. **The driven form**: two kinematic
  strips with the surface velocity (the belt pattern), whose V contact lifts the fruit ~0.4r
  above the belt while keeping it driven.
* **The mechanism.** (i) *Containment*: the corrected plow's escapes are lateral (dx ±18–32 mm,
  dz ~0–3) — a V/kerb at the fruit's lower flank blocks the slide; a contained fruit stays under
  the pads for the later regrasp cycles (the W1 profile runs up to 3 re-seats) and is recycled
  instead of riding to the belt end. (ii) *Lift* (driven form only): the fruit rises relative to
  the belt, so the fingers' clearance and the reach margin grow — the *only* scene realization of
  §1.3.2's live form. (iii) *Centring*: null for the close's relative geometry (§1.3.3); it buys
  supply repeatability. **The mission's (e) is already measured and is this option's anchor**: the
  side-approach re-seat exists in the tree (`FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1`, descend with the
  jaws wider than the blocking span, then close horizontally — the probe's ejection-free
  geometry), and the P11-C battery measured it (the falls 7 -> 3 at seed 11, the interval -21 %,
  pooled 35/60 vs the anchor 39/60, the class re-drew; **not adopted**). The cradle's scene delta
  over (e) is the *room* (the finger–belt clearance at the open descent) and the *containment*;
  (e) alone is closed.
* **The expected movement.** The falls: down (the contained fruit + the recovery); the no-grasp
  class: **maybe** (the containment's recovery is the mechanism; the close itself is unchanged);
  the outcomes: maybe.
* **The cost.** The highest scene cost: the cradle + the funnel + (driven form) the strips and
  their authoring; the battery x2 per arm + one trace-on mechanism run.
* **The risks.** (i) **The D3 lesson** — the funnel is a device in the moving supply's path *by
  design*; it changes the transport (friction, timing) and the feeder's sparse cadence; a slowed
  fruit interacts with the selection floor (the v9 pre-fix collapse condition: a 0.10–0.18 m
  fruit handed to the catch read 1/10, `logs/v1/pre_fix/`; the R11-A re-measure of the same
  window removal: the shipped acceptance 9/10 -> 4/10, `logs/r11/A_RESULTS.md`). (ii)
  The finger clearance is size-dependent and tight (3.6–23.6 mm of kerb height for the pool's
  28–70 mm fruit; the open span ±0.066 m). (iii) The fruit's ride on the strips (spin/derail —
  unmeasured). (iv) The two-line clearance: the dwell sweep rides through the cradle's span; the
  device must not enter the *hand's* sweep (not the arms' — no arm–arm contact is possible).
* **The falsifier.** The supply breaks (recirculated/never-settled/a rate collapse) or the fruit
  derails/spins or the fingers jam -> the form closes; and with the supply intact, the class/falls
  flat -> the containment's recovery mechanism is refuted.

### S3 — the approach-height change [the mission's (d); the (e) pairing]

* **Exact change.** **Env-only**: `FRUIT_DYNAMIC_PAD_LIFT=+0.020` (the existing knob,
  `tasks.py:729`; the standoff 70 -> 90 mm; the companion existing knob
  `FRUIT_DYNAMIC_PAD_LIFT_FRAC` caps it by the fruit's diameter). The shipped default stays 0;
  the battery sets it per arm. No code, no scene edit.
* **The mechanism.** The only lever that changes the fruit-relative contact geometry without a
  surface change (§1.3.4): the fingers' tips +20 mm relative to the belt (the collision margin),
  the descent 20 mm shorter (the profile), the pads' contact ~7 mm nearer the equator (M: the
  probe's +20 mapping), and — unlike D2a — **no catch-up equilibrium shift** (the break test moves
  with the standoff, §1.3.5). If the marginal close is a *contact-height* property (the pads on
  the tapered shoulder vs the equator — the nest's own design statement for the pad hand), this
  is the geometry that reaches it.
* **The expected movement.** The margins: certain (per-leg `end=`, the finger–belt clearance).
  The no-grasp class: **unknown** — the probe's static escape is flat at +20 mm
  (`padp20`: 0.203 m/s / 36.5 mm, bit-identical to shipped) and the -10 mm direction is a
  measured **belt jam** (the fingertips 0.6 mm inside the slab, 27–89 N, 2.2 mm displacement —
  the mission's cited `pad-lift -10` result; the live direction is **+**). The falls: unknown
  (the ejection's displacement vs the standoff is unmeasured).
* **The cost.** One battery arm; zero code; the same battery as the other arms.
* **The risks.** The higher grip on the fruit (the carry's stability at a higher hold point —
  unmeasured; the probe's flatness is the caution); the `FRUIT_DYNAMIC_PAD_LIFT` knob is global,
  so the arm is a battery-level env (the shipped default stays 0; the single-arm line is not run
  with it unless wanted).
* **The falsifier.** B/C read flat on the mechanism endpoints (the close's freeze geometry, the
  first keep-gaps vs the live extent, the ejection signature) **and** on the class/falls -> the
  approach-height hypothesis closes; then S2's lift mechanism (the same family, a scene
  realization) is doubtful too and the named path's geometry family is exhausted.

### S4 — the containment bundle [the mission's (b)/(c), sharpened by the fall path]

* **Exact change.** `conveyor.py`: (i) a **belt-end keeper** — a real collider lip (~40–60 mm
  tall, the belt's width) at the main belt's downstream end (y ~= -0.79); the **precedent is in
  the tree**: the output belts already carry "a small keeper at the outer edges of the slab, so a
  fruit that lands slightly off-centre meets a rail rather than the floor" (`conveyor.py:425-445`);
  (ii) two **side fences** along Y at x <= 0.13 and x >= 0.43 (outside the open hand's ±0.066 m
  span at the band's edges: the fingers at x = 0.20 span 0.134–0.266; at x = 0.36 they span
  0.294–0.426). Default-off knob (`FRUIT_CONTAINMENT=1`).
* **The mechanism — the measured fall path (M + D).** The falls are not a station event: the
  B1 fruit, ejected at the station, **rides the belt to the end and drops within the same
  attempt** — the recycle/despawn runs only at attempt boundaries (`tasks.py:5226`, `5232`; the
  belt end is y = -0.80 vs `despawn_y` -0.70, `assets.py:240`; 0.80 m at ~0.12 m/s ~= 6.7 s, and
  the attempts run 9–15 s), and the free-fall signature matches a 1.17–1.35 m drop (in-hand
  |v|max 4.78–5.05 m/s vs the probe's belt-top drop 4.74–4.82, `logs/p11b/` §2). The keeper holds
  the fruit until the next `update()` recycles it (`reached_end` instead of `fell_off`); the
  fences catch the lateral roll-offs (the 3/18 "short drops" at -216..-384 mm). *The derivation's
  caveat*: the per-tick path is not in the logs (the clearance row is a per-leg minimum) — the
  trace settles it (S4's own arm can carry `FRUIT_DYNAMIC_TRACE=1`).
* **The expected movement.** The falls: **down, near-certainly** (the anchor's 14 pooled; the B1
  floor falls are the bulk); the no-grasp class: **0**; the outcomes: **0** (stated — the
  ejection still happens; the containment changes where the fruit ends up).
* **The cost.** ~15 lines of scene code + one battery arm (the falls read off the existing
  `[carry]`/clearance rows).
* **The risks.** A fruit pile/spin at the keeper within an attempt (up to a few fruit arriving
  before the next update); the fences' clearance (a few mm against the open hand's ±0.066 m span
  at the band's edges) and the supply's drift tail (x = 0.148 against the -X fence); the
  single-arm stream changes (per the owner's directive the two-line anchor is the only re-measured
  reference; the single-arm acceptance is *reported*, not byte-barred).
* **The falsifier.** The falls do not move (then the exit path is not the belt end — the trace
  settles it, and the containment family loses its target); or a pile/new artifact appears (a new
  failure note).

### S5 — the station-side backstop / gate [the mission's (b), the strict form]

* **The exact change.** A per-fruit kerb pair at the station's fruit flanks, or a stop/gate.
* **The mechanism, measured against the geometry.** A **per-fruit** backstop is infeasible on the
  scattered band: the fruit's x spans 0.20–0.36 (0.16 m) — a fixed kerb cannot sit at every
  fruit's flanks; and any kerb that can contact the fruit laterally at the pinch height is inside
  the fingers' descent volume (the open span ±0.066 m; the pads close to the fruit's extent; the
  fingers' tips hang to r - 11.4 mm). The only *station-wide* kerb positions (x <= 0.13 / >= 0.43)
  are too far from the pinch to block a 20–40 mm escape — they only contain gross displacement
  (that is S4's fences). A **gate** stops the fruit: it is the v2 `FRUIT_PICK_STOP` semantics
  (removed in v3 for the never-stop line) and it **starves the downstream station** — the left
  station (y = 0.0) would hold fruit that the right station (y = -0.10) must catch, and grade C
  must pass both stations to `despawn_y` (W3 pure routing). Incompatible with the two-line.
* **The falsifier that would revive it.** A fruit-size-matched channel *plus* a driven feeder
  surface (the full D3-proper form) — i.e. exactly S2's driven realization, which is where this
  option's live content already sits.

---

## 3. The recommendation

### 3.1 The ranking, with the ratio argument

1. **S3 (the approach-height change)** — the highest ratio among the **grip** options: the only
   lever with a live mechanism on the close's fruit-relative contact geometry (§1.3.4), zero code,
   one battery arm; its one uncertain endpoint (the class) is exactly what the battery measures.
2. **S4 (the containment bundle)** — the highest ratio overall: the falls are the one headline
   metric with a *measured, near-certain* mechanism (the belt-end exit path), at ~15 lines; it is
   grip-null and stated as such.
3. **S2 (the self-centring cradle)** — the named scene form; the only scene device that can
   contain the re-seat's lateral escape at the station; the highest cost and the D3 supply risk;
   gated on S3's screen and a trace read.
4. **S1 (the raised station deck)** — catch-null by derivation (§1.3.1) with the D3 supply risk:
   **not worth a battery**; recorded so the named path's naive form is closed by analysis.
5. **S5 (the station-side backstop/gate)** — infeasible on the scattered band / incompatible with
   the two-line; recorded.

### 3.2 The pick: S3, with S4's keeper as the companion arm

**Why S3 as the treatment of record.** It is the only change that reaches the fruit-relative
contact geometry (the derivation), it composes with the running P12-B.1 compound (an env arm on
top of the current best base), and it is the go/no-go screen for the whole named-path geometry
family: if the approach height moves the close's mechanism endpoints, the scene form (S2) is
worth building; if it is flat, no scene geometry can reach the same axis more cheaply.

**Why S4 rides along.** It cannot interact with the catch (the keeper is at the belt's end, the
fences outside the hand's span), it is the only *certain* movement available, and it gives the
battery a second, independent endpoint (the falls) that no geometry arm can fake. If the owner's
priority is the *falls* rather than the class, S4 is the arm to promote; the pick's order
(S3 first) follows the mission's named path.

### 3.3 The pre-registration sketch (one paragraph; to be frozen before any Tier-A run)

**P12-B.2 PREREG (sketch) — the approach-height screen + the containment companion on the
two-line anchor.** *The scenario*: the two-line patch battery (`FRUIT_BIARM=1
FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`, the balanced A:B:C
0.375/0.375/0.25 mix, `ATTEMPTS=20`, SEED 11 primary + SEED 5/23 controls, Tier A solo via
`scripts/154_claim_run.sh`, `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`). *The anchor*: **the
current best two-line base** — the P12-B.1 compound (mass + from-open) if it lands positive,
else the shipped two-line; the base is **the same for every arm**, and the shipped-line anchor
numbers of record are A = 39/60 pooled (10/13/16), falls 14 (7/4/3), no-grasp 8/4/1
(`logs/p11c/C_RESULTS.md`, `logs/p12a2/A2_RESULTS.md`). *The arms*: **A** the base (the
knob-off replay must be 0-diff against the base's records, modulo reporting rows); **B** A +
`FRUIT_DYNAMIC_PAD_LIFT=+0.020`; **C** A + the belt-end keeper (the S4 scene arm, a default-off
knob; it cannot interact with the catch); one **trace-on** mechanism run per arm
(`FRUIT_DYNAMIC_TRACE=1` — a moved branch; the mechanism only, per AGENTS §2). *The endpoints*:
**primary (the mechanism)**: on the B1-class attempts, the per-tick close geometry (the
fingertip–fruit offset at the freeze, the measured sep vs the commanded gap) and the first
keep-gaps vs the live extent (the P10-E falsifier: every B1 arrival at/above the blocking span),
plus the ejection signature (the `[carry]` lowest payload point during the leg); **secondary
(reported, the one-sample discipline)**: the pooled outcomes vs the base, the no-grasp census
split (B1/B2/C), the falls (the `lowest payload point` <= -1000 mm rows; the anchor 14), the
interval/cycle, the descents' `end=` and the motion budgets. *The kills*: (1) the A replay fails;
(2) a new failure reason; (3) the motion budgets (`105`) or the `190` two-line gate's rate floor;
(4) the no-harm. *The no-harm*: the A arm = the base's records (0-diff); the two-line reference
`configs/motion_reference_patch.json` via `scripts/190_twoline_gate.sh` (a moved branch is the
attestation, not a kill — the P11-C convention); the single-arm acceptance **reported** (its
outcome + the motion gate; the fingerprint compare documented, not byte-barred) per the
2026-10-18 owner directive that the two-line anchor is the only re-measured reference;
`selfcheck.sh` PASS. *The
decision rule*: a mechanism-positive, class/falls-non-worsening B is a candidate for a
confirmation batch under the N=5 protocol — **no adoption on one batch** (the program's rule);
S2 (the cradle) is pre-registered as the gated follow-on if B's mechanism endpoints move, with
its own battery.

---

## 4. The honest constraints (what the records already rule out)

1. **The control-side space is closed** (P11-C arc, four arms, three batteries): the from-open
   arrival (+3 at seed 11, the falls 7 -> 3, -21 % interval — but the controls move against it,
   pooled 35/60), the chase stop (`FRUIT_FORCE_REENTRY=1`, 31/60), the range cut (30/60) — every
   variant loses pooled against the anchor (39/60) and the no-grasp class re-draws (the
   pre-registered kill 2 fires in C2/C3). **Do not re-run the arrival/depth/chase family as-is**;
   the scene path exists because of this closure.
2. **The D3 lessons**: (i) a raised platform in the moving supply's path obstructs it (the
   bounded proxy is measured negative — the side faces, `recirculated` 0 -> 13, 1/20); (ii) the
   properly-scoped station form needs a **self-centring feeder + a multi-seed IK** (the README
   "Known limit"); (iii) `FRUIT_NEST=0.05` alone was measured at a **610 mm IK residual**
   (`logs/242`) — a raised station without the feeder/IK work is not a drop-in.
3. **The reach bands** (R10/R11 + `174`): the catch's IK residual is 5.7–6.0 mm at the 6 mm
   tolerance **across the whole delivered band**; the cliff is at x = 0.426 (55.3 mm); the
   band-relative floors that admitted fruit inside the shipped selection window collapsed the
   shipped acceptance 9/10 -> 4/10 (R11-A) and the floored variant still read 4/9 (R11-A.1) —
   **any station device that changes the fruit's arrival timing (a funnel, a slowed ride)
   interacts with the selection floor and inherits this collapse risk**.
4. **The two-line's clearance**: the catch rides ~0.22 m through its dwell (the reachable station
   separation <= 0.18 m); the shipped branch's min is 13.9 mm (62/10672 < 30 mm) and the dense
   branch's 2.59 mm (8.6 % < 30 mm); the W2 screens show the clearance levers trade the rate ~1:1;
   no arm–arm contact is possible. **A station device must clear the hand's dwell sweep** (the
   fingers' ±0.066 m span plus the sweep) — that is the binding geometric budget, not the arms.
5. **The supply interactions**: the patch sheet's abreast pairs (0.085–0.12 m), the scatter
   0.20–0.36 + the drift tail 0.148, the feeder's attempt-boundary cadence; **any device that
   touches the fruit changes the transport** (AGENTS: a fruit change must be re-measured at
   `scripts/170_transport_probe.py`).
6. **The two-line semantics**: grade C passes both stations to `despawn_y` (W3 pure routing) and
   the right station (y = -0.10) must receive what the left does not take — **a gate at either
   station breaks the two-line** (S5).
7. **The no-harm bar has moved**: per the owner's directive the two-line anchor is the only
   re-measured reference — a scene edit cannot keep the single-arm acceptance's `[fruit]` stream
   byte-identical (the acceptance becomes a reported 9/10 + the gate), and the two-line's own
   byte bars apply only to the knob-off A arms.
8. **The physics lane is live and composes**: the P12-A.2 mass-only base measured +6 pooled
   (45/60) with the falls 14 -> 10 and is the refinement's base; the P12-B.1 compound (mass +
   from-open) is in flight. The scene battery should run **on the current best base**, not on the
   bare shipped line, or it re-measures a superseded anchor.

---

## 5. The strongest reason any of them could fail

**The single strongest (the pick's kill, and the family's):** the no-grasp class's geometric
driver is **not identified by the records** — the no-grasp and ok populations overlap on every
logged row (`logs/p10e/` §2.1), the per-tick pad–fruit geometry was never recorded on these runs,
and the static probe reads **flat** on the approach-height axis (the `padp20` escape is
bit-identical to shipped). If the dynamic close's marginality is not a contact-height property —
if it is the belt-break shear, the 120 Hz impulse resolution, or the lumpy fruit mesh's first
contact — then B/C read flat, the approach-height hypothesis closes, and with it the whole
named-path geometry family (S2's lift is the same axis, more expensively). The named diagnostic
before a scene build is the existing opt-in **`FRUIT_DYNAMIC_TRACE=1`** per-tick rows (the
fingertip vs the fruit, the sep vs the commanded gap, the force, `hand_rel` — `tasks.py:3358-3441`):
one trace run on the base's B1 attempts names the driver, and the P11-C precedent (a mechanism
win with a class re-draw and a pooled -4) is the cost of skipping it.

**Per option, the sharpest kill:**

* **S1 (the deck)**: already killed by the derivation — the catch is fruit-relative and the local
  surface rises with the fruit; a battery would buy the D3 obstruction risk for no mechanism.
* **S2 (the cradle)**: the D3 lesson at its strongest — the funnel is a device in the moving
  supply's path *by design*; a slowed or deflected fruit breaks the transport and/or the
  selection timing (the v9/R11 collapse class), and the containment's recovery mechanism is
  unmeasured (the corrected plow's escape is 20–58 mm; whether a contained fruit re-grips in the
  later cycles is the open question).
* **S3 (the pick)**: the flat static probe — the class may not be a contact-height problem; and
  the knob is global, so a positive read still needs its two-line scoping decided (the
  `_dynamic_profile` pattern) before any default flip.
* **S4 (the keeper)**: the fall path is *derived*, not logged — if some B1 falls are the fruit
  dropping from the pads mid-carry over the floor (the alternative reading the per-leg clearance
  row cannot exclude), the keeper does not catch those; the trace settles it, and the fences'
  few-mm finger clearance at the band's edges is a jam risk.
* **S5**: infeasible/incompatible by construction (the scattered band; the two-line starvation).

---

## 6. Reads and reproduction (read-only)

```bash
# the catch is fruit-relative (the derivation of §1.1)
sed -n '4473,4526p;7562p;8728,8741p' src/fruit_sorting/tasks.py
# the close/re-seat chain and the falls' exit path
sed -n '8691,8788p;5226,5234p' src/fruit_sorting/tasks.py
sed -n '1108,1113p' src/fruit_sorting/fruits.py          # the end-of-line recycle
sed -n '232,285p' src/fruit_sorting/assets.py            # the band, the nest fields
sed -n '104,133p;167,192p;210,262p;415,445p' src/fruit_sorting/conveyor.py  # belt/nest/rails/keepers
# the probe tables and the corrected plow
python3 logs/p11b/parse.py logs/p11b/10_sweep_tomato.log logs/p11b/80_sweep_tomato_padp20.log \
    logs/p11b/70_sweep_tomato_padm10.log
grep -h 'case=plow' logs/p11b/90_plow_fix_tomato.log logs/p11b/91_plow_fix_apple.log
# the station reach band
grep -h '\[reach\]' logs/v1/61_station_reach_seeded.log
# the two-line anchor's descents/end= and the falls
grep -h 'approach(cartesian)' logs/p11c/10_seed11_A.log | grep -oE 'end=[0-9.]+ mm'
grep -h 'clearance' logs/p10c/50_seed11_A.log | grep 'lowest payload'
```

**What this document did NOT do**: no simulator run, no `src/`/`scripts/`/`configs/` edit, no
default changed, no battery launched. The P12-B.1 compound battery (`logs/p12a2/92_compound_driver.log`)
was not touched. All writes are under `logs/p12b/`.
