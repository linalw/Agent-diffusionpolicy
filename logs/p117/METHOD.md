# P117 method - two fixtures, and the support proof that makes them admissible

**Registered** in `PREREG.md` (md5 **`5caae5d28c6ad5ae92a2977f89141596`**, pinned
2026-11-06T04:34:54Z, before any cell). This file records *how* the two fixtures
work and the four build defects that cost the phase's first hour, because those are
the reusable part.

## 0. The rule this phase inherits

Two fixtures in this project lied (P107/P112: a passive support let a 0.1 kg payload
sink 2 mm and creep 4-5 mm with **zero pad force**), so a fixture is admissible only
after its **support** is proven, and a break-away number is never a creep number.
Both fixtures therefore open with a zero-force cell and neither spends a real cell
until it reads the answer.

## 1. Fixture 1 - the pad face (`fixture.py`)

**Rig** (P104's, unchanged where it could be): one fruit from the shipped pool (its
own mesh, mass and friction draw), two pads on prismatic drives, the measured pad
face **61.000 x 84.900 mm** with its distal plane 80.5 mm below the jaw centre
(`logs/p66/COLLIDER_READ.md`, `tasks.FINGER_TIP_BELOW_JAW`), the shipped drive
`k = 1e5 N/m`, cap **4.90 N** per pad (the measured 9.75-9.9 N pinch over two
faces), and the jaw-centred seat at `PAD_STANDOFF` 70 mm.

**One session, 28 pad pairs.** The stations are laid out 0.20 m apart on one bench
and the fruit is teleported between them, so the whole battery is **one** app
session (182 s) instead of 7. The pad set is **per (profile, fruit)** because a
groove's radius is a fraction of *that* fruit's radius (`0.6 r` / `0.9 r`): a fixed
groove is size-specific by construction, and that is stated as the profile's price.

**The face as a polyline, then as convex boxes.** `depth_polyline(profile, r, half)`
returns `(u, depth)` breakpoints - `depth` is the surface's outward offset from the
shipped face plane, 0 at the rims - and `author_pad` authors **one convex box per
facet** with the box's outer face exactly on the facet (local X = the facet tangent,
Y = its outward normal, Z = the groove axis). A concave profile cannot be one convex
hull, so boxes are the only honest primitive; the ridges are then real geometry, and
the facet count (`ARC_FACETS` 18 → 10 deg ridges) bounds the contact-angle error at
5 deg (<= 0.7 % on `cos theta`).

**The closure is computed, not assumed** (`contact_travel`): the first contact is
`min_u [HOME + depth(u) - sqrt(r^2 - u^2)]`, and the cell closes
`travel = that + INTERFERENCE` (P104's 5 mm). This is load-bearing: a groove closed
at the *flat* target has the fruit 6-17 mm short of the face and **grips nothing**,
because the rim is further from the jaw axis than the fruit's surface at that
offset. `PREREG` A3.

**The support proof, and what it took to get one.** Three rows in the phase's smoke
log are the whole story: (i) a free payload under a *compensated* weight drifts
27.25 mm in 40 ticks - `apply_forces` lands one tick late relative to the position
integration, so the first tick of gravity is never cancelled; (ii) with the velocity
pinned each tick the same cell reads **0.0000 mm**, i.e. the compensation is exact
and the pose read is exact; (iii) the un-compensated cell falls 613 mm, so (ii) is
not a frozen world. The registered 0.05 mm bar is met **only** in form (ii), and
`RESULTS.md` A1 records that.

**Endpoints.** close (150 ticks, min-jerk) -> pin (230, the fruit teleported each
tick, P104's trick) -> release -> **settle 90 ticks** (`creep_g`) -> **the operating
load `m*(g + 5.83)` for 90 ticks** -> **`creep_op` = the total displacement from the
release** -> axial ramp 5 N/s to 40 N (`F2mm`, `Fexit`). The `+5.83` is the largest
single-tick `|a|max` a carry leg reports (`logs/p40/GRIP_CENSUS.md` §4.1).

**The endpoint had to be changed once, before the battery.** The first version read
the loaded phase *alone*; on the pear `arc06` walked 13.63 mm during the settle and
0.03 mm after it, so the sequential read would have promoted a profile that is 1.6x
*worse* than the control. `creep_op` is therefore cumulative - that is `RESULTS.md`
A2, and the smoke that showed it is kept (`smoke10.log`).

## 2. Fixture 2 - the station pocket (`fixture_station.py`)

**Why a drop-out section.** The delivered x is 0.188-0.397 and the top-down grip
band ends at 0.320 clean / fails at 0.398 (`logs/p66/STATION_SWEEP.md`), so a pocket
beside the belt is either inside the stream or outside the reach - an empty
intersection. A pocket *under* the line is the only pickable form.

**Geometry.** The shipped belt's own authoring split into two segments at the
station (`belt_friction` 0.9, kinematic body + `PhysxSurfaceVelocityAPI`,
-0.120 m/s, never stopped), a **0.148 m** gap, a **belt-like shutter** filling it
(0.020 m thick, top flush) that is teleported to a park to open, and a **100 mm**
deep pocket under it with the belt end faces as its along-belt walls and two x walls
at the reach band. The depth is *forced*: the shutter must close over the occupant,
so `depth >= 0.020 + 69.6 mm` = 89.6 -> 100 mm.

**Three build defects, each measured and each kept as evidence.**

1. **The surface velocity is in the collider's scaled local frame.** A 0.726 m
   segment commanded -0.120 carried the fruit at **0.087 m/s**; the 0.148 m shutter
   at **0.018 m/s**. The value must be `speed / y_length` (the tree's
   `conveyor._surface_attr_speed`). Fixed -> **0.120 m/s = 1.00x**.
2. **A flush shutter is not optional.** `set_world_poses(z = bz)` (the *slab's*
   centre) put the shutter's top 20 mm low; the fruit rested 19 mm down in the step
   and the stream stopped dead. The authored pose is `belt_top - thickness/2`.
3. **The door-clearance predicate must be geometric, not a radius.**
   `far_from_gap(distance < 0.09)` refuses to close once the occupant is *in* the
   pocket (it is 70-90 mm below the belt top, inside the radius). The predicate is
   now "no fruit whose top is above the shutter's underside and whose y is inside
   the mouth", which is what the teleport actually needs.

**Cells and timings.** `support` (the pocket floor, a 1200-tick drift trace at
200/400/800/1200 to separate jitter from creep), `closed` (4 fruit over the closed
shutter at 1.875 s and 0.833 s), `drop` (all 16 pool fruits: open at `y <= pick_y +
0.12`, close once the occupant's top clears the shutter's underside), `stream` (one
drop + 3 followers at both cadences). The shutter opens **0.54-0.64 s** before it
must close again, against the **0.833 s** fast cadence.

## 3. What a fixture here can and cannot say

Both fixtures are **offline**: no arm, no scheduler, no attempt loop, no camera.
They measure contact mechanics and, in fixture 2, the belt's transport. They cannot
measure the approach, the close's ejection, the arm's reach at a new pose, or the
policy. Everything they *do* say is reproducible from `p117_report.py` alone.

The two clean negatives are therefore stated as mechanism, not as rates: a groove
does not reduce the loaded creep and it weakens the pear's axial grip; mu raises the
static capacity 1.45-1.84x and moves the creep by 5 %. The one positive (the pocket)
is stated as a **licence to build a station**, gated on the reach and the actuator,
not as a rate.
