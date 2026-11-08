# P131 method - the ring's over-closure, and the aperture law

The question, from P130: `cage4` + `FRUIT_DYNAMIC_CLOSE_FREEZE=0` converts the
rate (+28.7 points) but the record's over-closure count (22/40, "the aperture is
below `dia - 4 mm`") is now the dominant failure.  Is the ring **driven** inside
the fruit by the force-capped drive, or is the **aperture law** wrong (the
horizontal extent at the freeze, wrong for a tilted ellipsoid)?  The rule: fix
the law if it is the law; publish the negative if it is the drive.

## 0. The order of work, and the files

1. **Census first, offline** (`census.py` -> `census.txt`), before any code edit:
   72 record rows from P130's freeze-off cells and P108's freeze-on controls,
   each joined to its approach's `end=`, its `grasp_lift` `[carry]` row and its
   `[run] attempt` outcome, with the fruit's extents recomputed from the pool's
   own mesh profiles (`meshes.axis_extent`; the `pxr` import is stubbed - the
   profile is pure arithmetic).  This is the phase's decision instrument.
2. The **build** (default off, the shipped expression bit for bit), with a
   selfcheck leg (`scripts/266_p131_cage_aperture_selftest.py`).
3. The **cells** (`PREREG.md`, pinned before them), the **report** and the
   **gates**.

## 1. The census: what the ring actually closes to

The record's `pinch_width` law for the four-pad ring is `0.98 x the widest
horizontal extent` (P107).  The dynamic close, however, is the two-jaw two-phase
ramp: a fast traverse to `wide = 1.02 x max(pinch_width, d)`, then a load ramp
to

    deep = FRUIT_DYNAMIC_CLOSE_DEEP x min(radial, axial)     (0.97 default)

and with `FRUIT_DYNAMIC_CLOSE_FREEZE=0` the loop always runs to `deep`.  On an
**upright** fruit (every class here is a surface of revolution standing on the
belt) the radial extent `R` is the width and the axial extent `A` is the
**height**; for a flat fruit `A < R`, so `deep` is below the ring's own law.
The census computes

    ramp = 0.97 min(R, A)           the two-jaw target the close ran to
    law  = 0.98 R                   the ring's stated law

and compares the commanded `aper` with both, per row.

Two metric corrections are needed before P110's split is readable, and both are
in the census (and in `PREREG.md` section 1, i.e. registered before the cells):

* **`dia` is not the width for every class.**  The strawberry's class diameter
  is its **height**: `R / dia = 0.792`, so `aper < dia - 4 mm` flags every
  strawberry grasp although `aper / R` is 0.95-0.98.  The corrected term is
  `aper < R - 4 mm`.
* **A missed ring is not an over-closure.**  A ring whose payload sits
  `off > 15 mm` from its axis at the close's end also reads `aper < dia - 4 mm`,
  but there is no fruit between its pads.  The census separates `miss` first
  (P107's aim class); every seated row in the record reads `off <= 10.1 mm`,
  every miss `off >= 92 mm`, so 15 mm is the empty middle.

The census also runs the **drive test**: the commanded `aper` is the pad-face
separation the position drives target, and the P130 rows' `sep_end` (the carry
leg's end) is at or above it, never below.  The P131 cells add the honest
close-time measurement: `sep`, the measured pad span at the flush.

## 2. The build

`cage_hand.py`:

* `APERTURE_MODES = ("shipped", "max_extent", "pad_axes")`, `aperture_mode()`
  (`FRUIT_CAGE_APERTURE`, strict: an unknown value raises).
* `CageHand.aperture_extent` keeps the shipped four-pad expression **bit for
  bit** when unset/`shipped`; `max_extent` returns `max(radial, axial)`;
  `pad_axes` returns the max over the ring's **own four pad axes** in the cage
  base frame (the TCP rotated by the constant tool correction `track_arm`
  caches every tick; a standalone call is the top-down case).  The three-pad
  law is untouched by every mode.
* The build print names the resolved law.

`tasks.py`:

* `cage_law_armed = (the hand is a radial ring) and aperture_mode() != "shipped"`.
* When armed, the close's load target becomes
  `deep = pinch_width x FRUIT_GRIPPER_SQUEEZE` (the hand's stated extent at the
  shipped 0.98) and the live clamp drops the two-jaw **2.5 mm interference
  floor** (`min_interference = 0`, so the clamp is `0.97 x live_extent`).  The
  floor is why the variant has to touch both: the ring's drive reaches its
  cap at `cap/k` = 0.049 mm, so a 2.5 mm absolute floor is 8.5 % of a 29 mm
  berry and would over-close the small fruit even under the right law.
* Unset: the shipped expression (`min_extent x FRUIT_DYNAMIC_CLOSE_DEEP`) and
  the 2.5 mm floor, bit for bit, on every hand.
* The `[cage]` probe row gains `law= ext= deep= sep=`: the resolved law, the
  hand's stated extent, the load target and the **measured** span at the flush
  (one `hand.separation()` call per attempt, inside the default-off probe).

The selfcheck leg pins the unset path (the P107 loop recomputed independently),
the two laws (including the tilted-base case), the cage3 invariance, the two
routing branches, the row fields and the PREREG md5.

## 3. The cells

`logs/p131/cells.sh` / `run_p131.sh`: the scripted single arm, the shipped
supply **package** exactly as P130's `F5`/`F6` ran it (`FRUIT_BIARM` left
unset: the default two-line scheduler is refused by the cage hand with one
`[biarm] ... ignored: hand is 'cage4'` row, but its dense wave + balanced mix is
what the supply gets), `ATTEMPTS=20`, the P108/P110 instrumentation on both
arms, `FRUIT_GRIPPER_KIND=cage4 FRUIT_DYNAMIC_CLOSE_FREEZE=0`.

| cell | seed | law |
|---|---|---|
| `U5`, `U6` | 5, 6 | unset (`shipped`) - the same-tree control |
| `P5`, `P6` | 5, 6 | `pad_axes` |
| `M5` | 5 | `max_extent` (the screen) |

**Why the control is fresh, not P130's `F5`/`F6`.**  The pre-registered replay
(`U5` == `F5`) is **not available**: two identical unset runs diverge at
attempt 0 (`at pick pose` 0.84 vs 0.86 s, the same fruit's `fruit_y` 0.4832 vs
0.4812), so the cage cell is **not bit-reproducible** - a new mode, the P39
`F1` precedent.  `U5`/`U6` are therefore the same-tree same-scenario controls,
and `F5`/`F6` are the pre-phase context.  Recorded as D1 in `RESULTS.md`.

## 4. Reading rules

* The **clean enclosure** is the endpoint (P110's structure, the two metric
  corrections above, the raw pad count is not it); the placed count is a
  **branch**, reported not gated.
* The over-closure is a **command/target** term, measured as `aper` against
  `R`; the drive is measured as `sep` against `aper` at the close's flush.
* The law's gain is read against the **same-seed freeze-off control** on the
  same tree (`U5`/`U6`), never the old freeze-on records.
* A variant that turns one failure into another is not a conversion: the
  clean-enclosure count, the class histogram and the `off0` are quoted together.
