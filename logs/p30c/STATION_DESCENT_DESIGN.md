# P30-C — the reachable pick station and the boundary-respecting descent

Status: **Tier-C offline design, read-only on the tree.** No simulator run, no `src/`/`scripts/`
`configs/` edit, no default changed, no commit; every write is under `logs/p30c/`. Branch
`p-supply`, 2026-10-21/22.

**The mission.** The owner approved component **1** (a pick station the arm can reach) and
component **3** (a boundary-respecting descent) and explicitly **rejected any feeder/nest
regularisation** - the scattered dynamic supply stays. This lane designs the bounded,
measurable form of the two approved components.

**The inputs read.** `AGENTS.md` §2 (the boundary paragraphs), `README.md` "Known limit",
`scripts/183_reach_intercept.py` + `logs/r10/reach_intercept_{left,right}.json` +
`logs/r10/{11_reach_left,12_reach_right}.log`, `scripts/174_station_reach.py` +
`logs/v1/61_station_reach_seeded.log`, `scripts/47_robot_collision.py` + `logs/166`,
`logs/167`, `logs/p30a/10_probe_parts_default.log`, `logs/160`/`logs/161` (the v1 `end=`),
`logs/fast/16_accept_indexed_v7.log`, `logs/p30a/{RESULTS,RAILS_DESIGN}.md`,
`logs/p12a2/A2_RESULTS.md` (the mass base), `logs/p16/BOUNDARY_DESIGN.md` (the completed
descent, pick (a)), `logs/r8/A_RESULTS.md` (D3), `logs/p12b/SCENE_OPTIONS.md` (the
fruit-relative derivation), and the descent/aim code in `tasks.py` (read-only).

**Pins as read** (the tree is dirty with the P30-A/P30-B work; these are the on-disk md5s):
`tasks.py` `e27b18a4`, `assets.py` `d820710d`, `conveyor.py` `c837f9a1`, `scene.py`
`ab85dca2`, `rl_env.py` `59150f85`, `fruits.py` `d28546d2`, `configs/waypoints.json`
`d81c6f1c`; git HEAD `e1b9936`.

**This lane's own measurement** (all re-derivable offline): `logs/p30c/reach_geometry.py`
-> every table below, `--assert` pins **14** numbers the verdict depends on (PASS).

---

## 0. The answer in one screen

* **The premise has to be corrected before it can be designed against: on the current tree the
  pick pose is *inside* the reachable band, and the 40-90 mm record is v1 history.** The
  station ladder reads **3.9 mm** (left) / **6.0 mm** (right) IK residual at the pick point,
  clean to x=0.39 and a hard cliff at x=0.42 (55.3/55.2 mm); the along-belt aim (station
  +17.3 mm) is **17.3 mm inside** the measured band on both arms. The shipped descents measure
  `end=` **8.3-10.8 mm** (dynamic, median 9.4, n=10) and **1.9-5.2 mm** (the current indexed
  line, median 4.8) - the **40.4-89.7 mm (median 49.1, n=20)** is the *v1* tree, whose
  pre-grasp target was the *fruit's centre* rather than the reachable pick height.
* **The surviving reach deficit is vertical and it is a *hand* term, not a station term.** The
  measured jaw floor is `belt_top + 0.0586` (P0, current tree) / `+0.0768` (`logs/166`); the
  fruit's centre is `belt_top + r` with r = 14-35 mm. So a command that puts the TCP *at the
  fruit's centre* is **23.6-44.6 mm** (P0) / **41.8-62.8 mm** (166) below the floor. The
  shipped commands already avoid it: the dynamic aim is `fruit + 0.070` = **+26.4..+44.5 mm
  above the floor** on the logged fruit centres (the r-range algebra reads +25.4..+46.4 mm),
  and the indexed target is `belt_top + grasp_clearance` = **+36.4 mm**.
* **The station (component 1) has no non-null geometry under the owner's own rule.** Any
  support that raises the fruit *and* the surface under the fingers moves both terms by the
  same Δ - the deficit `finger_drop − r` is invariant (this is the P12-B.2 "the catch is
  fruit-relative" derivation in the z axis, and it is why S1/D3 were catch-null). The only
  support that clears the fingers is narrower than the closed pad gap (~the fruit's own
  diameter) - i.e. a **longitudinal ridge**, which *centres the fruit laterally*: exactly the
  regularisation the owner rejected, and its record precedent (the 8 mm v2 `FRUIT_PICK_STOP`
  ridge at x=0.371) **gated the fruit and was removed in v3**. The pick is therefore **no new
  geometry**: the station is delivered as a *measured reachable height + a per-attempt boundary
  query* (`FRUIT_STATION_FLOOR`, pure reporting), with the one *hardware* candidate named and
  costed for a later phase (a **short-tip finger**, section 2.3).
* **The descent (component 3) is down to two bounded residuals**, because the "command that
  respects the boundary" is already in the tree (`free[2] = belt_top + cfg.grasp_clearance`,
  `tasks.py:8861`): (i) the **arrival** - the dynamic line's 8.3-10.8 mm settle against the
  6 mm catch-up tolerance, which the P16 (a) completed-descent loop (built, default off)
  closes; (ii) the **reporting** - `[boundary] belt_margin` divides by `FRUIT_FINGER_LEN`
  (60 mm) instead of the measured floor, so it is **16.8 mm optimistic** at the `logs/166`
  pose and reports **+24 mm** for the smallest fruit where the true clearance is **+7.2 mm**.
* **The strongest risk is not mechanical, it is that this closes the *sim* and not the
  *robot*.** The pads are kinematic and teleported; the reason the deficit is invisible in
  production is that the *command* was moved up, not that the hand got closer. On hardware
  the hand must physically reach the fruit, and `finger_drop` (59-77 mm) > `r` (14-35 mm) is a
  **gripper** fact. Any claim that P30-C "delivers the pick station" would be a misread.

---

## 1. The reach map, quantified

All numbers from `logs/p30c/reach_geometry.py` (run it; `--assert` re-checks them).

### 1.1 The lateral band (x) - the station is inside it

`scripts/174_station_reach.py` at the station (y = pick_y, jaw z = belt_top + 0.09, 6 mm
tolerance), `logs/v1/61_station_reach_seeded.log`:

| dx from pick_x | -0.16 | -0.12 | -0.08 | -0.05 | -0.03 | **0.00** | +0.03 | +0.05 | +0.08 | +0.12 | +0.16 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| left residual mm | 6.0 | 5.7 | 5.9 | 6.0 | 5.9 | **3.9** | 5.9 | 5.9 | 55.3 | 74.9 | 96.5 |
| right residual mm | 5.9 | 5.8 | 5.7 | 5.8 | 5.9 | **6.0** | 5.9 | 6.0 | 55.2 | 74.9 | 96.5 |
| x | 0.18 | 0.22 | 0.26 | 0.29 | 0.31 | **0.34** | 0.37 | 0.39 | 0.42 | 0.46 | 0.50 |

* **Clean band: x = 0.18 .. 0.39** (both arms), **cliff at x = 0.42** (55.2-55.3 mm), x = 0.50
  -> 74.9-96.5 mm. The pick point x = 0.34 is the *best* column on the left (3.9 mm) and 6.0 mm
  on the right - i.e. **at the solver's tolerance, not at a boundary**.
* The delivered supply band is x = 0.20-0.36 (`fruits.py`, the v9 design), so the *whole*
  delivered band lies inside the clean band: **20 mm** at the inner edge (0.20 vs 0.18) and
  **30 mm** at the outer (0.36 vs 0.39).
* Note what the band *means*: the solver stops at its 6 mm tolerance, so every clean column
  reads 5.7-6.0 mm - the band is "solvable to <= 6 mm", and its edge is where the residual
  jumps to 55 mm, not where it starts to grow.
* **Answer to "how far outside": 0 mm laterally**; the nearest cliff is 80 mm (x) beyond the
  station (0.42 vs 0.34) and 60 mm beyond the delivered band's outer edge (0.42 vs 0.36).

### 1.2 The along-belt band (y) and the aim's margin

`logs/r10/reach_intercept_{left,right}.json` (grip residual <= 6 mm; dy from `pick_y`; the
columns nest, `tasks.py:500-539`):

| x column | left clean dy | right clean dy |
| --- | --- | --- |
| <= 0.20 | -0.10 .. +0.15 | -0.10 .. +0.10 |
| <= 0.28 | -0.05 .. +0.10 | -0.10 .. +0.05 |
| > 0.28 (0.36) | **0.00 .. +0.10** | **-0.10 .. 0.00** |

The catch's aim is `station + lead`, the logged lead is **+0.0172..+0.0177 m** (the
`dynamic descent: ... intercept=` rows of `logs/p30a/01_accept_control.log`). Evaluated in the
map's own frame:

| arm | station | x | measured margin dn / up | code's 20 mm-inset margin dn / up |
| --- | --- | --- | --- | --- |
| left | 0.00 | 0.34 | **+17.3 / +82.7 mm** | **-2.7** / +62.7 mm |
| left | 0.00 | 0.39 | +17.3 / +82.7 | -2.7 / +62.7 |
| right | -0.10 | 0.34 | +17.3 / +82.7 | -2.7 / +62.7 |
| right | -0.10 | 0.39 | +17.3 / +82.7 | -2.7 / +62.7 |

* **Against the measured band the aim is 17.3 mm inside** on every arm and column.
* **Against the code's band (inset by `FRUIT_REACH_Y_INSET` = 20 mm) it is 2.7 mm outside.**
  That is a *reporting* artefact - the inset (20 mm) exceeds the lead (17.3 mm) - and it means
  the P16 `[boundary]` row prints `reach_dn=-2.7mm` on **every** attempt. Read it as "the
  inset, not the reach"; do not gate on it. (The reach selector that consumes the band is
  default-off; nothing in the shipped control reads it.)
* Second reporting caveat: `[boundary]` compares the aim *station-relative*
  (`grip[1] - station_y`) while the band tuple was measured in world dy from `pick_y`. For the
  right two-line station (y = -0.10) that shifts the printed number by 100 mm. Both caveats are
  one-line fixes in a *reporting* arm (section 3.3), not control changes.

### 1.3 The vertical band (z) - the only real deficit, and it is `finger_drop − r`

| quantity | value | source |
| --- | --- | --- |
| belt top | 1.170 | `assets.py:201-205` (`belt_center_z` 1.14 + `belt_size_z` 0.06/2) |
| measured jaw floor (drive-down stop) | **1.2286 = belt_top + 0.0586** | `logs/p30a/10_probe_parts_default.log`, current tree |
| same, older pose (`grasp` seed 1.285) | **1.2468 = belt_top + 0.0768** | `logs/166_collision_probe.log` |
| with the belt removed | **1.0490** (23.1 cm of travel) | `logs/167_collision_noconveyor.log` |
| fruit diameter | 28-70 mm -> r 14-35 mm | `assets.py:436-452` |
| fruit centre | belt_top + r = 1.184..1.205; logged **1.185-1.203** | the `fruit_z=` rows of `logs/p30a/{01_accept_control,20_patch_control}.log` (n=180) |
| shipped standoff (jaw above the fruit's centre) | 0.060 (`FRUIT_FINGER_LEN`) + 0.010 (`PAD_LIFT`) = **0.070** | `tasks.py:49`, `_pad_standoff` |
| **deficit** for a TCP target *at* the fruit's centre | **23.6-44.6 mm** (P0) / **41.8-62.8 mm** (166) | this lane's algebra |
| shipped dynamic aim above the floor | **+26.4 .. +44.5 mm** measured (r-range algebra: +25.4 .. +46.4) | `fruit_z + 0.070` minus the P0 floor; `fruit_z` = 1.185-1.203 (n=180 rows) |
| shipped indexed target above the floor | **+36.4 mm** | `free[2] = belt_top + grasp_clearance` (0.095), `tasks.py:8861` |

Two readings that matter:

1. **The slab binds; the joints do not.** With the belt removed the same drive reaches
   z = 1.049, i.e. **180 mm below** the P0 stop. So no change to the arm's mounting, the belt's
   height, the joint limits or the IK seed can lower the jaw: the stop is a contact between the
   finger meshes and the slab, and it moves with the slab (see the invariant, 2.1).
2. **`finger_drop` (58.6-76.8 mm) > r (14-35 mm) is the whole deficit**, and it is a property
   of the hand asset, not of the station. The hand's finger faces are documented 76 mm apart at
   full open (`assets.py:440-442`) and the pads are commanded ~2 % inside the fruit's diameter,
   which is why the grip is modelled kinematically and the arm carries the finger *meshes* as
   the physical tool.

### 1.4 What the shipped tree actually commands (the premise correction)

| line | TCP target | measured `end=` | n |
| --- | --- | --- | --- |
| dynamic, shipped (`FRUIT_DYNAMIC_PICK` unset) | fruit + 0.070 (jaw) | **8.3-10.8 mm, median 9.4** | 10 (`logs/p30a/01_accept_control.log`, current tree) |
| dynamic, mass base (two-line, patch sheet) | same | **8.1-15.3 mm, median 9.2** | 60 (`logs/p12a2/1*_mass.log`) |
| indexed, current tree (`FRUIT_DYNAMIC_PICK=0`) | `belt_top + 0.095` (jaw) | **1.9-5.2 mm, median 4.8** | 10 (`logs/fast/16_accept_indexed_v7.log`) |
| indexed, **v1** (`logs/160`/`161`) | the **fruit's centre** | **40.4-89.7 mm, median 49.1** | 20 |

The v1 decomposition, from the `pads aimed at ... align=(dx,dy,dz)` rows (n=20): **|dz| median
34.0 mm, lateral median 14.3 mm** - i.e. the 40-90 mm was the z deficit (34 mm, inside the
23.6-44.6 mm range for that geometry) plus the fruit's lateral offset from the station
(14 mm; the v1 log itself records `picking the fruit 41 mm from the pick centre`). **On the current
tree both terms are gone from the command**: the client sends the jaw to the reachable pick
height, and the 8-11 mm that remains is the *profile's own settle*, not a boundary strain - the
achieved/commanded ratio on the descents is 0.92-0.96 in an isolated cell (`logs/155`) and the
`|v|max` is 0.105-0.118 against the 0.161 budget.

**So AGENTS §2's "every descent ends 40-90 mm short" and "the descents are commanded into the
belt" describe the v1 primitive.** They remain true of `logs/160/161/166/167` and of the
*model* if a path ever sends the TCP to a pad target, but they are *not* true of either shipped
descending line today. This is the premise correction the design rests on, and it is
re-derivable in one command (`grep -o 'end=[0-9.]* mm' logs/fast/16_accept_indexed_v7.log`).

### 1.5 The minimal geometric change, per term

| term | needs | minimal change that moves it | verdict |
| --- | --- | --- | --- |
| x (lateral) | nothing | - | already inside: 50 mm to the clean edge (0.34 -> 0.39) |
| y (along belt) | nothing | - | inside by 17.3 mm (reported as -2.7 by the inset) |
| z (vertical) | +23.6..44.6 mm of *relative* lift | (a) the TCP target: **already done** on both lines; (b) the pads' plane (command, `FRUIT_GRIP_PLANE_DROP`): measured closed (S3 +20 mm negative at every seed; D2a -8 mm negative, -10 mm a jam); (c) raise the fruit *relative to the surface under the fingers*: a ridge/nest (rejected); (d) shorten `finger_drop`: a hand asset change | only (a) is free, and it is shipped |

The three changes the mission names, answered with the same numbers: **raise the belt** = null
(both terms move by Δ, 2.1); **lower the arm's mounting** = null (the jaw's floor is a contact
with the slab, not a joint limit: with the belt removed the same drive travels **180 mm
further**, so the arm has the range it needs and the mount is not the binding term); **move the
stations** = nothing to buy (the aim is 17.3 mm inside the measured band at every column, and
the right two-line station (y = -0.10) already sits on its band's inner edge, so a y move trades
one edge for the other; an x move is bounded by the cliff at 0.42, 80 mm away).

---

## 2. The station form (no feeder)

### 2.1 The invariant that decides the family

Let Δ be any uniform elevation of the station surface (a raised belt segment, a deck, a
plinth, a roller bed under the fruit). Then

* the fruit's centre rises by Δ (it rests on the surface),
* the jaw's floor rises by Δ (the finger meshes contact the same surface),

so the margin `(jaw_floor − fruit_centre) = finger_drop − r` is **unchanged**. This is the z-axis
form of the P12-B.2 derivation ("a station that raises the fruit and its support together moves
every target and the collision together - the catch is invariant"), and it is why the S1/S3/D3
family was catch-null *before* any run. The consequence for the design is blunt: **a station
can only help if the fruit's support is *not* the surface the fingers reach.**

### 2.2 The three candidates, the two record precedents, and the fingerprint

| # | form | geometry | the D3 lesson / record | verdict |
| --- | --- | --- | --- | --- |
| **S1** | **full-band raised segment** (x = 0.18-0.39, a 0.25 m y-window, 24-45 mm tall, ramps <= 15 deg both ends) | the fruit rides up and down; no side face inside the band; the supply keeps its lateral scatter | *not* the D3 failure (D3's deck was 100 mm wide, x = 0.29-0.39, with a **20 mm vertical side face** at x = 0.29 while the fruit can be at x = 0.20: `recirculated` 0 -> 13, battery **1/20** x2, a new "never settled" note) - but **null by 2.1**. Its ramps are the *risk* (a 45 mm rise over 168 mm = 15 deg, tan = 0.27 against mu 0.4-1.1, so climbable in principle - unmeasured on this line) | **null; do not build.** Falsifier available offline: a `47` probe on a raised block must move the jaw stop by exactly Δ |
| **S2** | **partial-width deck** (D3's bounded proxy: `FRUIT_NEST=0.02 FRUIT_NEST_WIDTH=0.05`) | 20 mm tall, 100 mm wide, 160 mm long, 140 mm upstream ramp | measured: battery **12/20 -> 1/20** x2 bit-identical, `recirculated` **0 -> 13**, direct probe no-contact **2 -> 12**, flails **1 -> 11**, close-start y median **-3.8 -> +142.0 mm** (`logs/r8/A_RESULTS.md` §4) | **reject** (obstructs, and a nest) |
| **S3** | **narrow centre ridge** (<= the closed pad gap, i.e. <= ~28 mm wide; 24-45 mm tall; along y at x = pick_x) | the only support the fingers *clear*: the pads close to ~the fruit's diameter, so a ridge narrower than the smallest fruit passes between them and the fruit bridges it | the **precedent is in the record**: the v2 `FRUIT_PICK_STOP` ridge (8 mm tall, 8 mm wide, x = 0.371) **gated the fruit** - arrival error -6..+27 mm - and was removed in v3 with the stop semantics (`README` v2 history). It also *centres the fruit laterally on x = pick_x* -> the supply regularisation the owner rejected, and the static cradle forms drift 46+ mm (`logs/p12b/SCENE_OPTIONS.md`) | **reject by rule**; it is the *only* non-null geometry and it is a nest |
| **S3'** | **the reachable-height station reference** (no new geometry) | the station's *reachable floor* becomes an explicit measured constant (`FRUIT_STATION_FLOOR`, default 0.0586 from the P0 probe) + a per-attempt boundary query + the `[boundary]` row that uses the *measured* floor instead of `FRUIT_FINGER_LEN` | the shipped commands are already above the floor (1.3, 1.4); the row is 16.8 mm optimistic at the 166 pose | **pick** |

**The pick is S3'.** It is the only member that is (a) not a nest, (b) not an obstruction, (c)
not null, and (d) cheap enough to be a *reporting* arm whose no-harm is byte-identity: it adds
one constant, one clamp predicate (which is a no-op on every shipped path, 1.4) and one field in
the existing row. It does **not** claim to close the deficit; it makes the margin *visible and
enforced* so that a future small-fruit regression cannot pass unnoticed.

**Its falsifier (pre-registered):** a `[boundary]` row with a *measured-floor* margin below
**+6 mm** on the shipped band, or any finger-belt contact row in the acceptance, or a `47` probe
whose stop is below `belt_top + 0.0586`. Any of the three means the invariant is being violated
by something the model does not see, and the *station* family re-opens with the belt-slot form
(next paragraph) as the only candidate.

### 2.3 The named hardware candidate (not picked)

A **short-tip finger**: the
meshes' below-jaw length must be <= r (14-35 mm) for the pads to sit at the fruit's centre
without the tips entering the slab, i.e. **cut 24-45 mm off `finger_drop`**. It is not a
station, it does not touch the supply, and it closes the deficit *for real* (it would also let
the coherent-hand path, `FRUIT_COHERENT_HAND=1`, reach without the 2 % overlap ejection,
`logs/325`). Cost: a hand asset edit + the whole grip re-baseline (R6-B's drive-saturated
pinch, W8-B's `clean_slip` bands, the S3/D2a standoff axis) - a phase, not a knob. Also
rejected in bounded form: the **belt slot** (let the finger meshes descend *into* the belt).
The tips must descend on either side of the fruit, ~r from its centre, and the fruit must
still be borne by the remaining surface: a 20 mm slot under a 28 mm lychee leaves ~4 mm of
bearing per side, so the form fails on the smallest fruit before it helps the largest.

---

## 3. The boundary-respecting descent (component 3)

### 3.1 What is already shipped

| piece | site | effect |
| --- | --- | --- |
| the indexed TCP target = the reachable pick height | `tasks.py:8861` `free[2] = belt_top + cfg.grasp_clearance` (0.095) | the TCP is **+36.4 mm** above the P0 floor; `end=` 1.9-5.2 mm |
| the dynamic aim = fruit + the standoff | `_dynamic_grip_point` / `_pad_standoff` (0.070) | **+26.4..+44.5 mm** above the floor; `end=` 8.3-10.8 mm |
| the boundary diagnostic | `[boundary]` row, `tasks.py:7735-7748` (`FRUIT_DYNAMIC_ARRIVE_DIAG=1`) | `end=`, `reach_dn/up`, `belt_margin` per dynamic descent |
| the completed descent | `_arrive_hold`, `tasks.py:10650`; `FRUIT_DYNAMIC_ARRIVE_TOL/_MAX` (default 0/0) | re-commands the aim until <= tol or the tick cap |

So component 3's *form* - "the descent's target retargeted to the reachable boundary + the
final centimetres done by the existing post-descent solver, with `end=` reported and the
boundary strain bounded" - **exists**, in two halves: the retarget is unconditional (the
target *is* the reachable pose), and the arrival is built but default-off.

### 3.2 The two bounded residuals

* **R1 - the arrival (the only behaviour change).** The dynamic line's settle is **8.3-10.8 mm**
  against the catch-up's 6 mm tolerance, so the post-descent solver always starts 3-5 mm plus
  the AIM error away. `FRUIT_DYNAMIC_ARRIVE_TOL=0.006` + `_MAX=24` (the P16 pre-registered
  values) closes it in <= 24 ticks (<= 24 mm of belt travel at 0.12 m/s, 10-25 % of the
  ~96 mm capture window). Expected read: `end=` 8.3-10.8 -> **<= 6.0 mm**, the catch-up's
  first-row residual down, the descent's `|v|max` unchanged (the same profile, a shorter
  remainder), the lurch bound unchanged. **Its value is exactly the P16 open question** (the
  K1 gate: does the shortfall feed the capture? P16 §1.3 says most likely not) - this lane
  does not re-litigate it, it only notes that the lever is built, bounded and cheap.
* **R2 - the reporting (pure, byte-inert).** `_belt_margin = grip[2] - belt_top - finger_len`
  with `finger_len = 0.060` (the *model* standoff) instead of the *measured* floor
  (0.0586-0.0768). At the 166 pose the row is **16.8 mm optimistic**: it reports **+24 mm** for
  the smallest fruit (r = 14 mm) where the true clearance is **+7.2 mm**. Two more
  one-line reporting fixes ride the same arm: the inset/lead artefact (1.2, prints -2.7 mm on
  every attempt) and the station-relative frame for the right two-line station (1.2, 100 mm).

### 3.3 The code sites and the expected read

| # | change | site | scope | default |
| --- | --- | --- | --- | --- |
| 1 | `FRUIT_STATION_FLOOR` (0.0586) replaces `FRUIT_FINGER_LEN` in the row's belt term | `tasks.py:7744-7747` | `[boundary]` only | new constant, row-only |
| 2 | report `reach_dn/up` against the *measured* band (drop the inset from the comparison, keep it in the selector) | `tasks.py:7735-7742` | row-only | row-only |
| 3 | the arrival | `FRUIT_DYNAMIC_ARRIVE_TOL/_MAX` (already built) | dynamic capture only | **off** (the pre-registration's arm) |
| 4 | the clamp on a *pad-target* descent (a guard, not a behaviour change today): `target_z = max(target_z, belt_top + station_floor + clearance)` | the indexed call `tasks.py:8933` | the indexed **non-coherent** path (the coherent hand computes its own fingertip target and is excluded) | off; a no-op on both shipped lines, whose targets sit 36.4 / 26.4-44.5 mm above the floor |

**Expected read of the whole component** (the pre-registration's endpoints, section 4): the
dynamic `end=` median 9.4 / 9.2 -> **<= 6.0**; the achieved/commanded ratio 0.92-0.96 ->
**>= 0.97** on the clean legs; the descent's `|v|max` **inside** the shipped budget (0.105-0.118
vs 0.161) and the lurch bound unchanged; `a_win5` unchanged (the same profile); the indexed
line **unchanged** (1.9-5.2 mm, no clamp fires); the catch rate reported as one branch sample
(AGENTS §2), never as a delta; the failure census, the falls and the total failure mass as the
outcome battery.

---

## 4. The pre-registration sketch

**One paragraph.** On the current tree, with the shipped scattered dynamic supply and the
two-line patch mass base, run a **reporting arm** (S: `FRUIT_STATION_FLOOR` + the two row fixes,
which must be *bit-identical* to the control - the no-harm is the arm's whole point) and a
**behaviour arm** (D: the completed descent, `FRUIT_DYNAMIC_ARRIVE_TOL=0.006
FRUIT_DYNAMIC_ARRIVE_MAX=24`), each on the acceptance and on the two-line patch battery
(SEED=11, the mass base), plus the indexed acceptance (`FRUIT_DYNAMIC_PICK=0`) as the
*predicted-null* control for the clamp. The mechanism endpoints are the `end=` shortfall, the
achieved/commanded ratio and the `[boundary]`/`[arrive]` margins; the outcome endpoints are the
class census, the falls, the total failure mass and the catch rate (quoted as a branch sample).
The station is **not** built; its falsifier is the `[boundary]` margin, and the only hardware
successor is the short-tip finger, which this phase does not touch.

### The structured form

**Scenarios.**

| id | command | n | role |
| --- | --- | --- | --- |
| A | `scripts/accept.sh` (the shipped scattered dynamic line) | 10 | the no-harm + the dynamic `end=` |
| B | the mass base: `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_PHYSICS_REAL_MASS=1 ATTEMPTS=20 SEED=11` | 20 | the two-line `end=` + the class census + the falls |
| C | `FRUIT_DYNAMIC_PICK=0 scripts/accept.sh` (the indexed primitive) | 10 | the clamp's predicted-null control |

**Arms.** C0 = the control (the on-disk P30-A record where the tree is unchanged:
`logs/p30a/01_accept_control.log` 7/10 + `logs/p30a/20_patch_control.log` 11/20); **S** = the
reporting arm (row + constant); **D** = the completed descent; **S+D**. The arm order is
interleaved C0/S/D/S+D where the cost allows, and the double-runs are bit-identical checks
(the scripted line is deterministic).

**Endpoints.**

* **Mechanism (primary).** (i) the dynamic `end=` median (9.4 acceptance / 9.2 mass base ->
  **<= 6.0 mm**); (ii) the catch-up's first-row residual median (P16's 14.6 -> **<= 8**);
  (iii) the achieved/commanded ratio on the clean descents (**>= 0.97**, from 0.92-0.96);
  (iv) the `[boundary]` measured-floor margin per attempt (must stay **>= +6 mm**, the smallest
  fruit's true value +7.2 mm); (v) the indexed `end=` (must **not move**: 1.9-5.2 mm).
* **Motion (reported, gated only where a budget exists).** the descent `|v|max` <= 0.161, the
  lurch bound, `a_win5` unchanged, `cone` for the carry legs (reported, the dynamic default).
* **Outcome (secondary, the class not the rate).** the census (ok / carried-not-placed /
  no-grasp), the falls (`lowest payload point` <= -1000 mm rows, attempts counted separately),
  the total failure mass, `diverted`/`recirculated`, and the catch rate quoted as **one
  deterministic branch sample** per configuration (AGENTS §2).

**Promotion rule.** S is promoted only if it is **bit-identical** on A and B (it is a reporting
arm: any difference is a bug) *and* its row prints the new numbers on both. D is promoted from
the screen to the battery iff (a) the `end=` median falls to <= 6.0 mm on A *and* B, (b) no new
failure reason and no census class grows by >= 2, (c) no motion budget is breached, (d) the
catch-up's residual falls. If (a) holds but the census is flat, that is the P16 K1 answer and
the phase closes with the mechanism note, not with an adoption.

**Kills.** K1 the `end=` does not fall within the cap (the drive cannot settle to 6 mm - the
P16 §5.3 second fail mode; publish as the boundary's true edge). K2 a class re-draw (the
never-grasped/no-grasp >= +2, or a new note) - the P15 conserved-mass lesson. K3 a finger-belt
contact or a `[boundary]` margin < 0. K4 a non-bit-identical double. K5 the no-harm fails.
K6 the clamp fires on a shipped path (it must be a no-op on A and C - if it fires, the
"reachable height" premise is wrong and the station family re-opens).

**No-harm (knobs unset).** `scripts/selfcheck.sh` PASS; the acceptance **byte-identical** to
the P30-A record (381/381 `[fruit]` lines, `fingerprint: matches`, reference `406745c5`, 7/10);
the two-line patch battery **byte-identical** to `logs/p12a2/10_seed11_mass.log` (950/950); the
two-line dense re-record + `scripts/190_twoline_gate.sh` PASS (442/442 vs the W7-A record);
`configs/*` untouched. S's own no-harm is the byte-identity above; D's is the same (its knobs
are 0 by default).

**Cost (Tier A solo, one claim lane).** S: ~20 min offline (`reach_geometry.py` + the 3-line
row patch) + 2 runs (A 5 min, B 8 min) + the byte-identity diff ~10 min. D: ~30 min (env-only,
already built) + the screen (A + B, 13 min) + the battery double (4 runs, ~30 min) + the
no-harm ~15 min. Total **~1.5-2 h**, no scene build, no new asset.

**Pins.** `tasks.py` `e27b18a4` (this lane's read), `assets.py` `d820710d`, `scene.py`
`ab85dca2`, `configs/*` untouched; the tooling `logs/p30c/reach_geometry.py` (`--assert`, 14
pins).

---

## 5. Risks, ranked

1. **This closes the sim, not the robot.** The pads are kinematic; the deficit is invisible in
   production only because the *command* was raised (`grasp_clearance` 0.095 / the +0.070
   standoff). `finger_drop` (58.6-76.8 mm) > `r` (14-35 mm) is a gripper fact, and the only
   real fix is a hand geometry change (the short-tip finger, 2.3) or a station the owner has
   ruled out. **Do not let P30-C be reported as "the pick station is delivered".**
2. **Component 3's behaviour change is a settle, not a rescue.** 8-11 mm of `end=` is the
   *profile's* remainder; the P16 analysis says the shortfall most likely does not feed the
   capture (the B1 failures' handoffs are *cleaner* than the oks'), so D may well read
   `end= <= 6` with a flat census - a mechanism note, not an outcome win. The phase is
   designed so that this negative is cheap and definitive.
3. **The station family is only *analytically* closed, not *experimentally* re-closed here.**
   The invariant is one line of algebra and the D3 replay is measured, but no run in this lane
   touches a raised segment. If a future edit changes the hand's below-jaw length, the belt's
   top or the finger colliders, the closure must be re-derived (`reach_geometry.py --assert`
   fails loudly on exactly those numbers).
4. **Two reporting caveats could be mistaken for findings**: the aim's -2.7 mm against the
   20 mm-inset band, and the right station's 100 mm frame shift. Both are in the row, not in
   the control; the pre-registration pins them so a later gate cannot read them as reach
   failures.
5. **The mass base is the two-line** (the outcome battery), while the boundary question is
   per-leg and single-arm-flavoured. The design therefore reports the `end=` per leg and the
   census per arm, and does not pool the two lines' rates (AGENTS §2: a two-line log is a
   different scenario).

---

## 6. Files, reproduction, and what this lane did not do

```bash
# every number in this document, with the pinned asserts
python3 -B logs/p30c/reach_geometry.py --assert

# provenance spot-checks
grep -o 'end=[0-9.]* mm' logs/fast/16_accept_indexed_v7.log | sort -u     # the indexed line, current
grep -o 'end=[0-9.]* mm' logs/p30a/01_accept_control.log | sort -u        # the acceptance, current
grep -o 'end=[0-9.]* mm' logs/161_accept_endmetric.log | sort -n | head   # the v1 record (40-90)
grep -E 'after driving down|finger +[yz]=' logs/p30a/10_probe_parts_default.log
grep -E 'after driving down' logs/166_collision_probe.log logs/167_collision_noconveyor.log
grep -E 'intercept=|dynamic catch-up' logs/p30a/01_accept_control.log | head
```

* `logs/p30c/reach_geometry.py` - the re-derivation (14 pinned asserts, PASS).
* this file - the design, the pick, the pre-registration sketch.

**What this lane did NOT do**: no simulator run, no `src/`/`scripts/`/`configs/`/`datasets/`
edit, no default changed, no commit, no branch operation; all writes under `logs/p30c/`.
