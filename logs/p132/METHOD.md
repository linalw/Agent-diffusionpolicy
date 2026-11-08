# P132 method - the serrated pad face, fixture first

**What this is.** The owner picked the last geometric route: a **new pad asset** for
the loaded-slide class (`logs/p42/SIM_LIMIT.md`'s own sanction; the decision book
`docs/END_EFFECTOR_DECISION.md` §4). The hypothesis this phase tests is the one
geometric form the record has not: **ridges perpendicular to the walk** - across
the pad's width, spaced along the tool axis - i.e. a ratchet against the payload's
axial walk. P117's grooves run the *other* way (a valley along the width, which the
payload can slide along), and every form the record already measured acts on the
wrong axis: force (`p76`-`p79`, `p120`: 60 N is a draw at six seeds), friction
(`p117`: capacity 1.45-1.84x, creep -5 %), the concave/V face (`p117`: 1.56-2.89x
*worse* on the pear).

**The fixture earns its keep or the phase does not spend a cell.** The record's
measured class is a *dynamic* pry (`p75`: a 0.3 mm slide then the force collapses;
the pads reach their 98.1 mm stop while the payload is 4.5-46.4 mm out) and its
static footprint is **not** a load-axis creep: P117/P129 measured the load-axis
`dz` at **-0.03..+0.03 mm** under the cell's `m(g+5.83)` hold while the *total*
creep (8.5-12.4 mm) is a lateral seat shift. So the fixture's job is to measure
whether a serration changes the **load-axis** response at the cell's load, and to
price its break-away and its small-fruit safety. If the incumbent's load-axis walk
is already at the rig's floor, no shape can be *shown* to reduce it - that is a
result about the instrument, and the phase records it rather than reading a null
as a pad property.

## 1. The rig

`logs/p132/fixture.py`, P117's fixture verbatim in its mechanics: one fruit, two
force-capped position pads, the pool's own mesh/mass/friction draw, the measured
**61.0 x 84.9 mm** plate, the per-face force **4.90 N** (the measured per-face
pinch, P104/P107), drive **k = 1e5 N/m**, c = 100 Ns/m, the pad's mass 0.02 kg,
the same **150-tick min-jerk close**, 230-tick pin, release, 90-tick gravity
settle, **90-tick `m(g+5.83)` hold** (the cell's largest single-tick acceleration,
P40 §4.1), then the **5 N/s axial ramp** to 40 N. No arm, no scheduler, no
attempt, no camera. 4 profiles x 4 fruits x 3 repeats = 48 cells, one session,
**112 s** wall.

### The endpoints

| column | what it is | why it is the endpoint |
|---|---|---|
| `F2mm` | the sustained axial force at the **2 mm** displacement (applied + weight) | P104's escape threshold and P75's trigger: the payload is lost after a **0.3 mm** slide, so the force that buys the first 2 mm is the class's own |
| `Fexit` | the force at the **30 mm** exit | P104's break-away, for continuity with P117/P129 |
| `settle_dz` | the load-axis component of the weight settle (90 ticks) | P104's "creep"; split from the lateral part because P117/P129 showed the total is a seat shift |
| `walk` | the **load-axis displacement during the 0.75 s sustained pull** | the phase's primary: it is the direction P61/P75 record the payload leaving in |
| `creep_g`, `creep_op` | the total (lateral) weight settle and release-to-end displacement | reported only; P117's dead end, and the promotion rule says a lateral move is not a promotion |
| `crush` | the commanded contact span - the payload's width | P76's `sep - dia >= -15 mm`; the drive is capped at 4.90 N, so the delivered penetration is `cap/k` = 0.049 mm |

## 2. A fixture defect found while building (and the corrected control)

P117's `author_pad` built the facet frame as `(tan, nf, w_axis)` and passed it to
`_quat_from_columns`. That frame is **left-handed for one pad of every pair**
(tan = +y, nf = +x, w = +z gives `tan x nf = -z`), and the quaternion extraction
turned the box **90 deg**: the right pad's box carried its **62.2 mm length on the
x (thickness) axis** and its **10 mm thickness on y**. Measured after authoring:
`flat S00L world_extent=(10.0/62.2/84.9) mm` but `flat S00R
world_extent=(62.2/10.0/84.9) mm`. The consequence is mechanical, not cosmetic:
the misoriented box's **fruit-facing face sat 30 mm behind its body** instead of
10 mm, so a small fruit never reached it (the drive target was `travel0 + 5` and
the face was 20 mm too far back) and fell - exactly what the first battery read:
`flat` held the strawberry, `flatlong`/`lip20` did not, and `flatlong` is a *flat
face* with no ridges. The fix is one line in the fixture: build the frame as
`(tan, nf, cross(tan, nf))`, right-handed by construction, for every segment.

**The corrected rig changes the flat control's small-fruit numbers.** P117's flat
table (pear `creep_op` 8.62, strawberry **0.98**, lychee 12.42) was measured with
the 62 mm block on one side; on the corrected rig the flat control reads pear
**6.70**, strawberry **12.22**, lychee **12.05** (medians; table §4). The pear's
2 mm break-away moves 2.57 -> **3.07 N**, the strawberry 12.78 -> **12.15 N**. So
P117/P129's *absolute* flat numbers are that rig's, not a clean flat-face
measurement; the **relative** comparisons in P117 (grooves vs flat) were measured
on the same asymmetric rig and stand as that phase's record, but this phase does
not quote them as a clean baseline. The corrected rig is the one this phase uses
for **all** profiles, so the A/B is internally consistent.

## 3. The four faces

All teeth are placed at the **fruit's widest row** (`u0`), not at the pad's face
centre: the pad's face centre sits **31.95 mm above** the fruit's equator on the
shipped standoff (the 10.5 mm lip is the distance from the equator to the distal
plane), and the widest row moves with the fruit's shape (pear -8.0 mm below the
pose origin, strawberry +2.8 mm above it, orange ~0). P117's `contact_travel` used
`sqrt(r^2 - u^2)` with `u` from the pad's face centre and `asin(|u*|/r)`; both are
corrected here (`u - u0`), which is what makes the serration sit on the contact.

| profile | face | build |
|---|---|---|
| `flat` | the shipped plate | one 10 mm facet, the control |
| `serr` | **5 ridges, 1.0 mm high, 8 mm pitch, 60 deg flanks**, across the pad's width (the ridge line is y, the pitch is z) | 13 facet boxes, valleys on the face plane, crests 1.0 mm toward the payload |
| `serr45` | the same ridges at **45 deg flanks** (the flank control; the brief's "at 45 deg" is read as the flank angle, not a 45-deg rotation of the ridge line - that variant is not built) | 13 facet boxes |
| `lip20` | the flat face with a **20 mm distal lip** - 9.5 mm more face below the equator than the shipped 10.5 mm | one facet, plate 94.4 mm long, centre 4.75 mm lower |

`lip20` is **fixture-only**: it extends 9.5 mm below the shipped distal plane, and
the belt is there (P39/P69: a shorter pad clears 4 mm, a longer one hits the belt;
the fingertip is the binding dimension). It prices the "deep cup" mechanism, it is
not a candidate to build. **No shape extends *above* the palm or below the shipped
distal plane on the hand**; the phase builds nothing on the hand (see §5).

The serration is **not a drop-in pad**: its crests protrude 1 mm, so the pads must
close 1 mm less per side than the flat for the same delivered normal force. The
fixture computes `contact_travel` from its own authored polyline and adds the 5 mm
interference, so every profile is measured at the **same 4.90 N delivered force**,
not at the same commanded span. Every cell's `pads` column is 2 (A2 manipulation
check); no cell loaded one pad.

## 4. The table

Medians of 3, `python3 logs/p132/p132_report.py` (nothing hand-copied):

| profile | fruit | F2mm [N] | Fexit [N] | settle_dz [mm] | **walk [mm]** | creep_g [mm] | creep_op [mm] | crush [mm] | pads |
|---|---|---|---|---|---|---|---|---|---|
| flat | pear | 3.07 | 9.20 | -0.00 | **+0.03** | 3.35 | 6.70 | -10.00 | 2 |
| flat | orange | 3.75 | 14.12 | -0.00 | **-0.00** | 4.38 | 8.76 | -10.00 | 2 |
| flat | strawberry | 12.15 | 13.03 | -0.02 | **+0.00** | 11.48 | 12.22 | -10.00 | 2 |
| flat | lychee | 5.85 | 12.94 | +0.00 | **-0.00** | 10.02 | 12.05 | -10.00 | 2 |
| serr | pear | 3.57 | 12.66 | +0.01 | **+0.01** | 2.74 | 5.47 | -10.05 | 2 |
| serr | orange | 12.91 | 13.87 | -0.01 | **+0.00** | 5.65 | 9.71 | -10.10 | 2 |
| serr | strawberry | 9.36 | 13.53 | -0.00 | **+0.00** | 11.00 | 11.22 | -10.03 | 2 |
| serr | lychee | 2.06 | 13.02 | +0.00 | **-0.00** | 3.92 | 7.86 | -10.10 | 2 |
| serr45 | pear | 4.74 | 12.61 | +0.01 | **+0.01** | 1.92 | 3.85 | -10.03 | 2 |
| serr45 | orange | 3.75 | 13.91 | -0.01 | **+0.00** | 3.77 | 7.55 | -10.06 | 2 |
| serr45 | strawberry | 9.15 | 13.65 | +0.02 | **+0.02** | 11.18 | 11.18 | -10.02 | 2 |
| serr45 | lychee | 6.60 | 12.77 | -0.01 | **+0.00** | 10.43 | 11.06 | -10.06 | 2 |
| lip20 | pear | 1.53 | 12.57 | -1.51 | **-2.82** | 4.41 | 7.12 | -10.00 | 2 |
| lip20 | orange | 7.79 | 14.08 | -0.01 | **+0.01** | 1.10 | 2.19 | -10.00 | 2 |
| lip20 | strawberry | 13.11 | 13.57 | -0.01 | **-0.00** | 5.77 | 11.53 | -10.00 | 2 |
| lip20 | lychee | 5.98 | 13.44 | -0.01 | **-0.00** | 6.20 | 11.86 | -10.00 | 2 |

**The support proof (A1, gate).** Zero pad force + the weight compensated, 200
ticks: **0.000 mm**. Zero pad force + no compensation, 40 ticks: **613 mm** fall.
The fixture's read is exact and its only support is the commanded clamp.

**The mechanism, read in this order.**

1. **The load-axis walk is at the rig's floor for the incumbent and for both
   serrations**: |walk| <= 0.04 mm on every cell except `lip20`'s pear. So the
   first promotion clause ("at most 60 % of flat") has **no resolvable signal**:
   the flat is +0.03 mm (pear) / -0.00 (others), and 60 % of that is inside the
   noise. The serration does not move the sustained axial walk; it cannot, because
   the incumbent's walk is zero. **This is P117/P129's result one level further**:
   the class is not a static load-axis creep, and a static rig cannot certify a
   pad against it.
2. **The one measurable walk is `lip20`'s pear: -2.82 mm** (down, the load's
   direction), with a -1.51 mm settle. The deeper lip gives the payload *more room*
   to seat down (the extra face is below the equator and adds no normal until the
   payload has moved ~10 mm), and its 2 mm break-away falls to **1.53 N (0.50x
   flat)**. The deep cup is a **negative**, not a fix.
3. **The break-away is a draw to worse on the binding class.** `serr`'s `F2mm` is
   1.16x on the pear, 3.44x on the orange, **0.77x on the strawberry**, **0.35x on
   the lychee**; `serr45` is 1.54x / 1.00x / 0.75x / 1.13x; `lip20` 0.50x / 2.08x
   / 1.08x / 1.02x. `Fexit` is 0.98-1.38x. **No shape clears "break-away not below
   flat" on every fruit**: the strawberry and lychee - the two small classes the
   cell actually loses - are where the ridges *reduce* the 2 mm capacity, because
   a 1 mm ridge on a 37 mm fruit is a large step and the contact sits on a crest
   with less wrap.  The orange's 3.44x is the one large positive and it is a
   single species; the `serr` `Fexit` on that fruit is 0.98x, so even there the
   full break-away is a draw.
4. **The total (lateral) creep falls for `serr`** (pear 6.70 -> 5.47, orange 8.76
   -> 9.71 (up), strawberry 12.22 -> 11.22, lychee 12.05 -> 7.86) - a *lateral*
   seat effect, the direction P117 already closed; it is not monotone across the
   pool (the orange rises), so it is not even a consistent lateral win. The brief's rule says a shape that only moves the lateral seat
   is not promoted; this is exactly that shape's only positive.
5. **Crush**: the commanded contact span is `dia - 10 mm` for every profile (the
   5 mm interference per side; the serration's 1 mm crest is offset by its 1 mm
   deeper close), inside P76's -15 mm rule; the delivered force is the 4.90 N cap
   in every cell (the `pads=2` column). The pool's smallest class is the 34.4 mm
   lychee (the 30 mm bound is not in the pool); the crush clause passes on the
   binding class.

## 5. The promotion decision, and what is not built

The brief's rule: **promote only if the sustained walk is at most 60 % of flat and
the break-away is not below flat and no crush at a 30 mm fruit.** Measured:
`walk` is at the floor (no shape can be shown to reduce it), `break-away` is below
flat on the strawberry/lychee for `serr` and `serr45` and on the pear for `lip20`,
and the crush clause passes. **No shape promotes.** Therefore:

* **nothing is built on the OpenArm hand** (no `scene.py` edit, no new
  `FRUIT_FINGER_FACE` value, no collider change) - the collider set is untouched,
  so there is no two-line cell in this phase;
* **no two-line cell is run** - a cell cannot test a shape the fixture refuses,
  and a pad asset moves the collider set (P71's rule), which would need same-seed
  controls it does not have;
* **the pad-asset lane closes** on the record's own terms: a pad asset can only
  act on the static load-axis walk (zero for the incumbent) or the static
  break-away (the serration does not raise it on the small classes), and the
  force lane already showed capacity does not convert (`p76`-`p79`, `p120`).

**The named residual, stated so it is not over-read**: the class is a *dynamic*
pry (`p75`), and this fixture measures a *static* pull. A serration could still
act on the dynamic roll/slide in a way the static rig cannot see - but that is a
cell, not a fixture, and the phase's registered rule forbids spending it on an
unpromoted shape. The **only** dynamic route left for a pad is a cell with the
serration built blind, which the record's instrument rules (a shape needs a
fixture first) do not license. The workstation route is excluded by the owner's
constraint (the dynamic scattered pipeline must not be stopped/diverted/gated).

## 6. Read rules this phase adds

* **A static axial pull cannot certify a pad against this class.** The incumbent's
  load-axis walk is 0.00 mm at 1.66 N; a shape's "improvement" on it is noise. The
  endpoints that *are* resolvable are the 2 mm break-away and the lateral seat -
  and the lateral seat is not the class (P117).
* **A fixture's facet frame must be checked against the built prim before its
  table is read.** A left-handed `(tan, nf, w)` frame silently rotates the box 90
  deg and puts the face 20 mm behind the pad; a small fruit then falls and the
  table reads as a grip failure. The one-line check is the world extent of a
  facet: thickness on x must be 10 mm, not 62.
* **The flat control is same-batch.** P117's absolute flat numbers are a rig with
  one 62 mm block; quote this phase's flat (pear 6.70, strawberry 12.22) when
  comparing a serration, not the P117 absolute table.
* **`crush` is the commanded span** (`dia - 10 mm`, the 5 mm interference per
  side) and the delivered force is the 4.90 N cap; the two together are the P76
  guard, not the span alone.
