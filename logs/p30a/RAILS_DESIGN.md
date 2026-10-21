# P30-A: the belt's side rails / edges - the census, the envelopes, and whether they interfere

Owner's directive (verbatim): *"if the conveyor's side rails/edges interfere with fruit
grasping and placing, remove the belt's side rails/edges."* Scope fixed by the mission: the
**rails/fences only** - not the frame, not the belt slab; and the scattered dynamic supply
stays (no feeder, no nest).

This document is the geometry/interference half. The runs are in `RESULTS.md`; the offline
re-computation of every number below is `logs/p30a/rails_geometry.py` (`--assert` pins the
values the verdict depends on).

**Verdict in one line.** On the shipped line **no rail interferes with grasping** (the
descent's obstruction is the belt *slab*, and the two rail sets that would touch the hand are
already off / opt-in), and the one rail in the **placing** path - the output belts' *inner*
rail - is crossed by the payload with a retained clearance of **21-54 mm** and, where a
release lands short, acts as a **catch ledge** (97 % placed over 232 measured releases) rather
than a blocker. Removing it is delivered as `FRUIT_OUTPUT_RAILS=outer` (default `both`,
byte-inert) and measured (`RESULTS.md`); the measured case for a default change is **negative**,
so the default is unchanged.

---

## 1. The census: every rail-like box in the cell, where it comes from, whether it collides

Re-derived from the shipped `SceneConfig` by `rails_geometry.py`; the builder lines are the
code's own. `x` is across the main belt, `y` along it (fruit travel is -Y), `z` up. The main
belt slab is `x=[0.110, 0.570]`, `y=[-0.800, +0.800]`, `z=[1.110, 1.170]` (top **1.170**);
each raised output belt is `x=[0.100, 1.200]`, `y=+/-[0.425, 0.675]`, `z=[1.300, 1.350]`
(top **1.350**).

| # | box | x [m] | y [m] | z [m] | collider | built when | code |
|---|-----|-------|-------|-------|----------|-----------|------|
| 1 | main **frame rail N** | 0.0855 .. 0.1105 | -0.850 .. +0.850 | 1.165 .. 1.215 | **no** | always | `conveyor.py:266-277` |
| 2 | main **frame rail P** | 0.5695 .. 0.5945 | -0.850 .. +0.850 | 1.165 .. 1.215 | **no** | always | `conveyor.py:266-277` |
| 3 | main **guide rail N** | 0.1945 .. 0.2095 | -0.800 .. +0.800 | 1.170 .. 1.245 | yes | `FRUIT_RAILS=1` | `conveyor.py:278-294` |
| 4 | main **guide rail P** | 0.4705 .. 0.4855 | -0.800 .. +0.800 | 1.170 .. 1.245 | yes | `FRUIT_RAILS=1` | `conveyor.py:278-294` |
| 5 | **containment fence N** | 0.1150 .. 0.1300 | -0.780 .. +0.780 | 1.170 .. 1.220 | yes | `FRUIT_BELT_CONTAINMENT=1` | `conveyor.py:76-135` |
| 6 | **containment fence P** | 0.4300 .. 0.4450 | -0.780 .. +0.780 | 1.170 .. 1.220 | yes | `FRUIT_BELT_CONTAINMENT=1` | `conveyor.py:76-135` |
| 7 | **output belt inner rail** (x2) | 0.100 .. 1.200 | +0.400 .. +0.425 / -0.425 .. -0.400 | 1.335 .. 1.385 | yes | **always** (`both`) | `conveyor.py:573-611` |
| 8 | **output belt outer rail** (x2) | 0.100 .. 1.200 | +0.675 .. +0.700 / -0.700 .. -0.675 | 1.335 .. 1.385 | yes | **always** (`both`) | `conveyor.py:573-611` |

Three facts about this table drive everything else:

* **The main belt's "side rails/edges" are already not in the way.** The *frame* rails (#1/#2,
  `main_frame_rail_width`/`_offset`, `assets.py:414-415`) are **outside the slab** and carry
  **no `CollisionAPI`** - they are render only (`conveyor.py:269-277` applies
  `_define_box`/`_set_color` and nothing else). The *guide* rails (#3/#4, `assets.py:230`,
  `FRUIT_RAIL_HEIGHT` default 0.075) are **off by default**: `FRUIT_RAILS` defaults to `0`
  (`assets.py:230`), so `conveyor.py:280` never authors them. The guide rails were the
  original interference and were removed in the v2 belt work: *"Guide rails were 0.09 m apart
  while the open gripper spans 0.132 m. The fingers were jammed against the rails at the open
  position and could never close"* (WORKLOG "why the belt got wider", line 701) and the taller
  variant was a measured regression ("Taller guide rails", WORKLOG line 1851). The owner's
  "remove the side rails" was, for the main belt, already delivered in 2026-09.
* **The only always-built rail colliders in the cell are the output belts' four side rails
  (#7/#8).** They are real colliders with a metal friction material (`conveyor.py:594-598`),
  25 mm thick, 50 mm tall, standing 35 mm proud of the raised belt top, spanning the belts'
  whole 1.10 m length.
* **The containment bundle (#5/#6) is opt-in** and its fences sit *outside* the fruit band
  with only 4 mm to the open hand at the band edges (section 3).

## 2. The three envelopes the directive names

### (a) The grasp envelope

The open hand's x span is `jaw +/- 0.066 m` (`assets.py:251`, `conveyor.py:66`; the finger
plates hang ~0.084 m below the jaw centre on this hand, WORKLOG "the jaws hang ~8.4 cm below
the jaw centre"). At the shipped station the jaw is `(0.34, 0.00, belt_top + 0.095)`
(`assets.py:258-263`, `grasp_clearance`), so the fingers span `x=[0.274, 0.406]`,
`z=[1.181, 1.265]`. The delivered scattered band is `x = 0.20-0.36`
(`fruits.py`, `FRUIT_SUPPLY_LATERAL`), so the *worst* cases are the band edges:

| envelope | hand x span | nearest rail | gap |
|---|---|---|---|
| grasp at the station | 0.274 .. 0.406 | frame P inner face 0.5695 / guide P 0.4705 | **+163.5 / +64.5 mm** |
| grasp at the band's inner edge (jaw x=0.20) | 0.134 .. 0.266 | frame N inner face **0.1105** | **+23.5 mm**, *no collider* |
| grasp at the band's inner edge (jaw x=0.20) | 0.134 .. 0.266 | guide N inner face **0.2095** (if `FRUIT_RAILS=1`) | **-15.0 mm (overlap)** |
| grasp at the band's outer edge (jaw x=0.36) | 0.294 .. 0.426 | frame P / guide P / fence P | +143.5 / +44.5 / **+4.0 mm** |

So:

* **No rail touches the grasp at the station** - the nearest is a *visual-only* frame rail
  163 mm away.
* The **band edge is where the guide rails would bite**: with `FRUIT_RAILS=1` the N rail's
  inner face (0.2095) is inside the open hand's span at a band-edge grasp by 15 mm, and it is
  inside the *supply band* itself - a fruit centre below `x=0.2245` (smallest fruit) or
  `x=0.2445` (largest) touches it, i.e. **the lower 25-45 mm of the 160 mm band is
  physically blocked**. That is why the knob must stay off, and the probe in `RESULTS.md`
  measures what happens when it is not: the descent ends **18 mm higher and 56 mm off in x**,
  with the finger's final box inside the P rail.
* The **descent's actual boundary is the belt slab, not a rail.** `scripts/47_robot_collision.py`
  drives the jaw straight down from the grasp pose: the jaw stops at z=1.229 (59 mm above the
  belt top) with both finger boxes **inside the slab** (z down to 1.183 against a belt top of
  1.170), identically with the output belts present and with their inner rails removed
  (`RESULTS.md` section 1). This is the same mechanism as `logs/166` vs `logs/167` (23 cm of
  travel with the belt removed, 3.8 cm with it present) and as the 40-90 mm descent shortfall:
  the pick pose is outside the arm's reachable band, the arm runs to its boundary and the
  fingers end up inside the slab. **A rail removal cannot fix it and was not attempted** - the
  slab is out of scope by the mission.

### (b) The place envelope

The place path is the pick station -> the transfer pose -> the release, then the finger-capped
descent (`tasks.py::_place_low`). The release is at `(0.43, +/-0.50)` (`assets.py:361-372`),
the transfer z is `output_place_z + FRUIT_OPENARM_TRANSFER_LIFT = 1.45 + 0.08 = 1.53`
(`tasks.py:2350-2363`, 2395-2402), and the carried payload's lowest point sits **0.091-0.114 m
below the jaw centre** (from the measured `_payload_clearance` rows: +31..+54 mm over a rail
top of 1.385, jaw 1.53).

The transit sweeps `y = 0.05 -> 0.50`, so it **must cross `y = 0.4125`** - the inner rail's
centreline. The inner rail's outer face is *flush with the slab's inner edge* (0.425) and its
top is **1.385 = the belt top + 35 mm**:

| quantity | value | vs the inner rail's top (1.385) |
|---|---|---|
| payload bottom at the shipped transfer z (1.53) | ~1.420 | **+35 mm** (measured +31..+54) |
| open-hand fingertips at the transfer (1.53-0.084) | 1.446 | **+61 mm** |
| payload bottom with `FRUIT_OPENARM_TRANSFER_LIFT=0` | ~1.340 | **-45 mm** (and -10 mm vs the *slab top*) |
| fingertips with `FRUIT_OPENARM_TRANSFER_LIFT=0` | 1.366 | **-19 mm** |

**This is the interference the owner's directive is about, and the code already carries the
repair.** The +80 mm lift exists *because* the fingers used to sweep the rail: *"The transfer
dragged the fingers through the output rail. The jaws hang ~8.4 cm below the jaw centre, so at
the original lift height the fingertips swept the rail on the way to the line: a 48 m/s^2 spike
and 4 cm of payload slip (`logs/445`). The openarm lift/place targets ride 8 cm higher
(`FRUIT_OPENARM_TRANSFER_LIFT`), which also clears the rail by +49 mm (`logs/449`)"*
(WORKLOG line 7043). `logs/445_placefix.log` still carries the pre-fix signature: place
clearances of **-3 mm and -5 mm to the output rail** with the payload landing at y=0.448/0.502.

So the *active* cost of the inner rail on the shipped line is **+35 mm of transfer height and
the +80 mm lift that buys it** - not a contact. The rail is also the surface the P2-3 report
measures against (`tasks.py:2417-2438`: `y <= 0.46` -> `output_belt_top_z + 0.035`,
"the rail is what the payload crosses when it moves from the pick station to the output line").

**The rail is also, measured, a catch ledge - which is why removal is not free.** Across every
log in the repo there are **10 126 `[task] released at` rows**; binning them by the released
`|y|` against the rail's footprint:

| released `|y|` | n | share | placed=True |
|---|---|---|---|
| `< 0.400` (inboard of the rail, over the gap) | 548 | 5.4 % | **48.0 %** |
| `0.400 .. 0.425` (**on the rail's 25 mm top face**) | 232 | 2.3 % | **97.0 %** |
| `0.425 .. 0.460` (on the slab, near its edge) | 518 | 5.1 % | 95.4 % |
| `> 0.460` (on the slab) | 8 828 | 87.2 % | 86.2 % |

A release that lands on the rail's top face succeeds **97 %** of the time (it topples the 35 mm
onto the belt, which is 25 mm away); a release that lands *inboard of the rail* succeeds 48 %.
**Removing the inner rail would convert the 2.3 % rail-band releases into gap releases** - the
same geometry with nothing under them - so the measured case for removal is not merely "no
gain", it is **negative** for the placement path. The `48 %` inboard class is *not* a rail
problem: it is a short lateral release (P3's territory), and it happens with or without the
rail.

The **outer** rail (#8) is 175 mm outboard of the release and 100+ mm from the open hand: no
envelope touches it in any configuration measured here, and it is the only thing between a
fruit that rolls outward and the discharge side of the belt, so it is the one that must stay.

### (c) The supply flow

The delivered band is `x = 0.20-0.36` at the belt top, `z = 1.170 .. 1.240` for the largest
fruit. Against that band:

* frame rails (#1/#2): **+74.5 / +194.5 mm** clear - and no colliders;
* guide rails (#3): **-15 mm overlap** for `x < 0.2245-0.2445` (see (a)) - off by default;
* containment fences (#5/#6): +55 mm clear on both sides;
* output rails (#7/#8): 165+ mm above the belt top, no contact.

So the supply flow's only rail conflict is the guide-rail set that is already off. Note this is
the same conclusion the v9 supply change reached from the other direction: the scattered band
was chosen *inside* the measured reach band (`x = 0.18-0.39`, `scripts/174_station_reach.py`),
and a rail at 0.2095 would cut into it.

## 3. The margin the opt-in containment bundle runs at

`FRUIT_BELT_CONTAINMENT=1` (P12-B.2 S4, default off) adds 15 mm fences at inner faces
`x = 0.130 / 0.430`, 50 mm tall, from `y = -0.78` to `+0.78` (`conveyor.py:55-73`). The
config's own note says the fences "clear those by 4 mm each (the scoping's `x <= 0.13 / >=
0.43` bound, at its tight values)". The offline census reproduces it exactly: the **P fence's
inner face (0.430) is 4.0 mm from the open hand at the band's outer edge (jaw x=0.36 ->
fingertip 0.426)** and 24.0 mm from it at the station. The scattered supply's outer band edge
is *inside* the fence, so the fence itself is not wrong - but a dynamic catch that aims at
`x = 0.36` runs with 4 mm of fingertip clearance. This is a documented **opt-in** margin, not
a shipped one; no change is proposed (the fences are the containment design and the band is
inside them).

## 4. The `0.375` inner edge in `tasks.py` is not a surface

`tasks.py:2378-2392` (the P3 inner-shift cap; the `0.375 inner edge` claim is line 2391) says the release "only has to be *over* the belt:
its inner edge is at `|y| = 0.50 - 0.125`" and calls that `0.375` the invariant the cap
protects. The arithmetic uses the **release's** y as the belt's centre. The shipped belt centre
is `output_belt_y = 0.55` (`assets.py:303`), so:

* slab inner edge: `|y| = 0.55 - 0.125 = **0.425**`;
* innermost hard edge: the **inner rail's inner face at 0.400** (the rail protrudes 25 mm
  inboard of the slab edge, 35 mm above it);
* `0.375` is where nothing is: it is `output_place_y - width/2`, i.e. 50 mm inboard of the rail
  and 50 mm inboard of the slab.

Consequence for the closed P3 phase: its cap puts the release at `|y| = 0.3875`, a r_max fruit
spans `0.3525 .. 0.4225` - **on the rail's top face and off the slab**; the largest shift that
keeps a r_max fruit fully on the slab is `0.040 m` (r_min: `0.060 m`) against the cap's
`0.1125 m`. That is part of why `FRUIT_PLACE_INNER_SHIFT` collapsed the rate 90 % -> 30 %
(AGENTS P3 paragraph); the belt's "inner edge" it was aimed at is the rail, not the slab. P3
stays closed - this is recorded so the next attempt at the place leg does not re-derive the
wrong edge.

## 5. What is changed

Delivered, **default = the shipped geometry, byte-inert**:

| knob | default | effect |
|---|---|---|
| `FRUIT_OUTPUT_RAILS` (`assets.py:340-348`, `output_rail_keep` at 516) | `both` | `both` \| `outer` (drop the robot-side rail, keep the far one) \| `inner` \| `none` |
| `FRUIT_OUTPUT_RAIL_HEIGHT` (`assets.py:349-355`) | `0.05` | the rail box's height; its bottom stays 15 mm inside the slab, so `0.05` = the shipped 35 mm proud of the belt |

`OutputBelt.build` (`conveyor.py:573-611`) authorises exactly the same boxes at the defaults -
`rail_bottom = output_belt_top_z - 0.015`, `centre_z = rail_bottom + h/2` reproduces
`output_belt_top_z + 0.01` for `h = 0.05` - and prints a `[fruit] output belt rails ...` audit
line **only when a knob is off its default**, so the shipped stream is byte-identical (measured,
`RESULTS.md`).

`FRUIT_RAILS=0` + `FRUIT_RAIL_HEIGHT` already cover the main belt's guide rails (#3/#4) and are
untouched; the containment fences (#5/#6) are untouched.

Why nothing is flipped: the measurement says the rails interfere with **neither** envelope on
the shipped path (the grasp never sees them; the place crosses the inner rail at +21..+54 mm and
lands on it, when it lands short, 97 % of the time), and the one place where they *do* cost
something - the +80 mm transfer lift - is a knob in `tasks.py`, outside this phase's write
scope, and its own A/B (section 3 of `RESULTS.md`) is a wash. Flipping the default would trade
a measured catch ledge for a measured margin nobody is currently short of.
