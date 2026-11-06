# P117 pre-registration - the scene, fixture-first

**Pinned before any fixture cell.**  Owner directive: *keep raising the sorting speed
and success rate, and if the limit is the simulation scene, change or improve the
scene.*  This is a new authorisation: every earlier phase treated the scene as fixed
(references per scenario).  Its scope is bounded twice - to the terms the record
names as the limit, and to **fixture-first** (P107/P112: a passive support let a
0.1 kg payload sink 2 mm and creep 4-5 mm with **zero pad force**).

Pins at registration: `tasks.py` `9e3e657b`, `rl_env.py` `bf4c56fa`, `bimanual.py`
`9b7fc33f`, `fruits.py` `dcabe16b`, `scene.py` `a0199097`, `cage_hand.py`
`ac7c7c0f`, `configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`**,
`..._single.json` = **`8952c320`**, checkpoint `moe_v13s` `61da390a`.  Nothing is
adopted, no default changes, `configs/` is untouched.

## 0. What the shipped cell reads (quoted, not re-derived)

Scripted two-line: **28-29/40 = 70-72.5 %** at a **10.6-11.1 s** interval, window
**5.66** / batch **5.05** placed/min, wall **2.95** placed/min.  The failure split is
**75 % loaded slide (`cnp`) + 25 % acquisition** (`logs/p92/CENSUS.md`), so the class
ceiling is **93.8 %**.  The interval is **sequencing-bound**: a shorter attempt span
does not shorten it (P80/P88/P89/P99/P100).

## 1. The three candidates, and the one this phase changes

1. **The pad's face (75 %).**  P75: the payload is *pried out* through a widening gap
   (the pads reach their 98.1 mm stop while the payload walks along the tool axis).
   P61: the walk is 25 deg from the tool axis.  P104: at the operating load the
   shipped pinch creeps **3.20 mm** (pear), 1.6-1.9x the 2 mm escape threshold, while
   its static capacity is 10-20x the demand - so the binding quantity is the creep.
2. **The pad's friction (75 %).**  The pad's authored mu is 2.0; the pair reads
   1.25-1.46 (PhysX *averages*, P104 §7a).  A higher-friction elastomer (mu 3/4) is
   plausible in reality.  **Kill:** if creep does not fall with mu, the creep is not
   a friction slide (the failure is the wedge) - publish that and drop the lane.
3. **The presentation (25 % + speed).**  The acquisition class is the fruit
   **55.8 mm along-belt** at the band entry (P108) against a **6 mm** catch
   tolerance, and the descent ends **40-90 mm short** because the hand hits the
   conveyor (AGENTS §2; `47_robot_collision.py`: 23 cm free, 3.8 cm with the belt).
   A **stationary pocket** removes the moving handover and the descent's blocked
   boundary at once.

## 2. The record's contradiction, recorded before the runs

The brief says the concave/V-groove face "has never been tested".  **The tree has
it**: `FRUIT_FINGER_FACE` (`v`/`h`/`x`/`c` additive, `v2`/`h2`/`x2` recessed,
`p` plate) exists in `scene._add_contact_faces` and was measured in the
`logs/p3face` phase.  Matched against its **own** flat control the recessed
`h2` is a **draw** (6/10 vs 6/10) and `v2`/`x2` are worse (3/10, 1/10); against the
later chosen `flat + k30` arm (7/10) all are worse.  That measurement is the
**single-arm dynamic catch at the pre-P41 force (4.42 N delivered)**, not the
shipped two-line at 9.75-9.9 N, and it is a **rate**, not a creep.  So this phase is
a **re-test at the shipped force with the never-measured creep endpoint**, and the
report must say so - not "never tested".  `FRUIT_FINGER_MU` is likewise existing,
and `FRUIT_FINGER_MU=8` was measured to re-eject A4 (a *close* event the fixture
cannot see).

## 3. Fixture 1 - the pad face (`logs/p117/fixture.py`)

One fruit, two force-capped position pads, the pool's own mesh/mass/friction draw,
the measured pad face **61.000 x 84.900 mm** with its distal plane 80.5 mm below the
jaw centre, the measured per-face force **4.90 N**, the shipped drive stiffness
**k = 1e5 N/m**, cap 4.90 N.  Profiles (`P117_PROFILE`), the padding per fruit
(`0.6 r` / `0.9 r` of **that** fruit, because a groove is size-specific):

| profile | face | contact |
|---|---|---|
| `flat` | the shipped plate | 1 / pad, radial |
| `arc06` | semicircular groove, radius 0.6 r | 2 rims / pad at 36.9 deg |
| `arc09` | semicircular groove, radius 0.9 r | 2 rims / pad at 64.1 deg |
| `v90` | 90 deg V, half-opening 0.85 r | 2 walls / pad at 45.0 deg |
| `cradle90` | the same V with its valley across the pad | 2 walls / pad, the **only axial normal** |
| `flat_mu3` / `flat_mu4` | `flat` at pad mu 3.0 / 4.0 | 1 / pad |

Each cell: close (150 ticks, min-jerk) -> pin (230) -> release -> **gravity settle 90
ticks** (`creep_g`, P104's endpoint) -> **operating load `m*(g+5.83)` for 90 ticks**
(`creep_op`, the primary) -> axial ramp 5 N/s to 40 N (`F2mm`, `Fexit`).  4 fruits
(pear, orange, strawberry, lychee) x 3 repeats.

**The closure is computed, not assumed.**  `contact_travel` reads the first contact
from the fixture's own authored polyline and adds P104's 5 mm interference, so every
profile is measured at the same delivered normal force.  The *cost* is recorded: a
groove needs the pads `r - sqrt(r^2-R^2)` **deeper per pad** (6 mm at `arc06`, 19 mm
at `arc09` on a 60 mm fruit) - i.e. a grip-law change, not a pad swap.

### A1 - the support proof (gate, before any real cell)

* (i) pad cap **0**, the payload's weight cancelled by an applied force, 200 ticks:
  drift **<= 0.05 mm**.
* (ii) pad cap **0**, no cancellation, 40 ticks: the payload **falls >= 20 mm**.

Both must pass or **no real cell is spent** (the fixture is invalid, `PREREG` A1).
(i) proves the read/seat is not the source of the motion; (ii) proves (i) is not a
frozen world.

### A2 - the manipulation check (gate)

Every profile must load **>= 2 pads at >= 3.5 N** of the 4.90 cap at the settle.
A profile that closes on air is reported as **no grip** and excluded from the
ranking (its creep is meaningless) - not silently pooled.

### A3 - the creep promotion (primary)

Same-batch flat control, per fruit.  **Promote** if either

* `creep_op(pear) <= 1.0 mm` **and** `creep_op_flat(pear) >= 3.0 mm`; or
* `creep_op <= 0.5 * creep_op_flat` on **both** the pear and the orange.

### A4 - break-away

**Reported, never gated** (P104 §3: the 2 mm break is not the binding event, and a
3-contact form re-seats after 2 mm).

### A5 - crush / consistency (guard)

`fmax <= 3 x 4.90 = 14.7 N` on every cell, the pads never cross
(`span > 10 mm`), and `A2` holds.  **Bruising is not modelled** in this sim - a
constant per-pad force at a smaller contact area is a *pressure* claim the fixture
cannot make; it is stated, not claimed.

### A6 - the mu diagnostic

If, on the pear, `creep_op(mu4) > 0.5 * creep_op(mu2)` **and**
`creep_op(mu3) > 0.7 * creep_op(mu2)`, the creep is **not** friction-limited: the
friction lane is published as dead and dropped.

### A7 - what a promotion would and would not license

A promoting profile licenses a **two-line battery** at the shipped cell (2 seeds x 20
attempts, then 2 fresh seeds, P93's rule), endpoints the **carried class** (`cnp` +
`clean_slip > 100 mm` escapes) and the **placed count**, the attempt span and the
interval quoted **separately** (the interval is sequencing-bound, so no interval
claim), guards: crush (`sep@loss - dia`), landing (`FRUIT_PLACE_TRACE`: every
payload-present release `on_belt`), descents not re-tuned, and the no-harm
acceptance.  It does **not** license a default change: the pad is a hardware change
that needs a per-size pad **and** a grip law (A3's cost).

## 4. Fixture 2 - the station pocket (`logs/p117/fixture_station.py`)

**Why not "a diverter beside the belt".**  The record already fixes the geometry:
the delivered x is **0.188-0.397** (P49/P60) and the top-down grip band is
**x <= 0.320 clean, x = 0.398 fails at 32.8 mm / 17.0 deg** (P66's 150-cell sweep).
A pocket *outside* the delivered band is therefore *outside* the pickable band: the
intersection is empty.  So the only pocket that stays pickable is a pocket **under**
the line - a **drop-out section of the belt** (a flap door, belt-like when closed,
opening under the selected fruit), which is also what gives the descent its missing
40-90 mm.  This is the form measured; the diverter-siding form is **refuted by
arithmetic before a build**, and that is recorded.

Setup: the shipped belt's own authoring split into two segments (kinematic body +
`PhysxSurfaceVelocityAPI`, `belt_friction` 0.9, -0.120 m/s, **never stopped**) with a
**0.12 m** gap at the station; the gap is filled by a **door** that is itself a
belt-like kinematic body (so a fruit rolls over it at belt speed, not dragging), and
the door swings down about its upstream edge to open.  Under the gap: a pocket floor
**40 mm** below the belt top with a shallower V floor, x walls at the picked pose.
Cells: all 16 pool fruit through the drop; the support cell; the stream with the door
closed; the stream with one drop, at the shipped **1.875 s** cadence and the fast
**0.83 s** cadence.

### B1 - the support proof (gate)

A fruit at rest on the pocket floor, **no door and no diverter contact**, 200 ticks:
drift **<= 0.05 mm**.  This is exactly P107/P112's test - if the floor lets a payload
sink or creep, the fixture is invalid and no cell is spent.

### B2-B6 - the pocket's endpoints

| id | endpoint | bar |
|---|---|---|
| B2 | the occupant's hold after the drop, 200 ticks | **<= 1.0 mm** |
| B3 | expulsion, all 16 fruit | **0/16** |
| B4 | the stream over the **closed** door, both cadences | **4/4 pass** (end y < -0.20), no follower < 0.06 m/s for > 3 ticks while on the door |
| B5 | the stream with **one** drop, both cadences | **3/3 followers pass** and the occupant holds <= 1.0 mm |
| B6 | the door's peak contact force on the occupant | **<= 10 N** |

**B7 (reported, not gated):** the landing x spread over the 16 fruit - if the pocket
centres the fruit at the station's x, it also removes P48/P49's delivered-x tail.

**Promotion:** B1-B6 pass => the pocket promotes to a **station build** (a new
scenario: the belt with a drop-out section, a door actuator, the pick pose 40 mm
lower, the selector/scheduler on a static target).  It is **not** a knob and is not
built in this phase.

## 5. The work

1. write the two fixtures; 2. pin this file's md5; 3. run fixture 1 -> support, then
the cells; 4. run fixture 2 -> support, then the cells; 5. if a pad profile or mu
promotes, the two-line battery (A7) - otherwise nothing is built; 6. `RESULTS.md`,
`METHOD.md`, the AGENTS/WORKLOG paragraphs, and the four gates
(`selfcheck.sh`, `accept.sh`, `106`, `107`).

**No default change, no `configs/` edit, no reference re-recorded** in any outcome
except a shipped change, which this phase does not license.
