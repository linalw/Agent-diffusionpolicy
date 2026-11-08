# P132 results - the serrated pad face: no shape promotes, and the static pad-asset lane closes

**VERDICT (first line).** The owner's last geometric route - a **new pad asset** - was
tested fixture-first. Four faces (`flat`, `serr` = 5 ridges / 1.0 mm / 8 mm pitch /
60 deg flanks, `serr45` = the same at 45 deg flanks, `lip20` = the flat face with a
20 mm lip) were measured at the shipped 4.90 N/face on the pool's own fruit, 4 fruits
x 3 repeats. **No shape promotes**, and the reason is the instrument as much as the
shapes:

* **the sustained axial walk is at the rig's floor for the incumbent and for both
  serrations** - |walk| <= 0.03 mm on every cell except `lip20`'s pear, so the
  promotion rule's first clause (`<= 0.6 x flat`) has **no resolvable signal**;
* **the 2 mm break-away is a draw to worse on the small classes** - `serr` is
  **0.77x** on the strawberry and **0.35x** on the lychee, `serr45` **0.75x** on
  the strawberry - and the only large positive (the orange, 3.44x) is one species
  whose full break-away is 0.98x;
* **the one measurable walk is `lip20`'s pear: -2.82 mm** (down, the load's
  direction) with its 2 mm break-away at **0.50x** - the deep cup is a negative,
  and it is fixture-only anyway (the belt is below the shipped distal plane).

**Nothing was built on the robot and no two-line cell was run.** The pad-asset lane
is closed on the record's own terms (a pad can only act on the static walk, which is
zero, or the static break-away, which the serration does not raise consistently, and
the force lane already showed capacity does not convert). The **dynamic residual** is
named, not hidden: the class is a dynamic pry and this rig is a static pull, so the
verdict is about the *static* pad-asset lane; a blind dynamic cell is the only test
that could overturn it, and the phase's registered rule does not license one on an
unpromoted shape. The workstation route is excluded by the owner's constraint.

**A fixture defect was found and fixed, and it changes the flat control.** P117's
`author_pad` built the facet frame as `(tan, nf, w_axis)`; that is **left-handed for
one pad of every pair**, and the quaternion extraction rotated that box 90 deg - the
right pad carried **62.2 mm on the thickness axis** and its fruit-facing face sat
30 mm behind its body. The measured world extents: `flat S00L (10.0/62.2/84.9)` vs
`flat S00R (62.2/10.0/84.9)`. The first battery's small fruits fell on the
*long-axle* profiles including `lip20`, which is a flat face with no ridges - the
facet, not the serration. The one-line fix (`w = cross(tan, nf)`) makes every facet
10 mm thick; the **corrected flat control** then reads pear `creep_op` **6.70**,
strawberry **12.22**, lychee **12.05** mm (P117's 8.62 / 0.98 / 12.42 were that
asymmetric rig's, and the strawberry's 0.98 was the 62 mm block's cradle). The A/B
below is on the corrected rig for **all** profiles.

## 1. The support proof (A1, gate)

| cell | ticks | reading | verdict |
|---|---|---|---|
| weight-compensated, pad cap 0 | 200 | drift **0.000 mm**, dz +0.000 | PASS |
| no compensation, pad cap 0 | 40 | falls **613 mm** | PASS |

The fixture's read is exact and its only support is the commanded clamp. A2: every
real cell loads **2 pads** (48/48 cells; no one-pad cell), at **4.38-4.93 N** of
the 4.90 N cap. **Deviation A2-D1**, recorded: the one pad at 4.38-4.39 N is the
serrated pair's off-side pad (the ridge contact splits the load), 0.15 N (3 %)
below P117's registered 4.54 N lower edge; the gate's intent (both pads loaded at
the shipped force) is met, and no verdict rests on the band. A3: every facet's
world x extent is **10.0 mm** (the corrected frame).

## 2. The table (medians of 3; `python3 logs/p132/p132_report.py`)

`F2mm` / `Fexit` are the axial break-away at 2 mm / 30 mm; `settle_dz` is the
load-axis part of the weight settle; `walk` is the load-axis displacement **during
the 0.75 s `m(g+5.83)` hold** (the phase's primary); `creep_g`/`creep_op` are the
total (lateral) displacement; `crush` is the commanded contact span minus the
payload's width.

| profile | fruit | F2mm [N] | Fexit [N] | settle_dz [mm] | walk [mm] | creep_g [mm] | creep_op [mm] | crush [mm] |
|---|---|---|---|---|---|---|---|---|
| flat | pear | 3.07 | 9.20 | -0.00 | +0.03 | 3.35 | 6.70 | -10.00 |
| flat | orange | 3.75 | 14.12 | -0.00 | -0.00 | 4.38 | 8.76 | -10.00 |
| flat | strawberry | 12.15 | 13.03 | -0.02 | +0.00 | 11.48 | 12.22 | -10.00 |
| flat | lychee | 5.85 | 12.94 | +0.00 | -0.00 | 10.02 | 12.05 | -10.00 |
| serr | pear | 3.57 | 12.66 | +0.01 | +0.01 | 2.74 | 5.47 | -10.05 |
| serr | orange | 12.91 | 13.87 | -0.01 | +0.00 | 5.65 | 9.71 | -10.10 |
| serr | strawberry | 9.36 | 13.53 | -0.00 | +0.00 | 11.00 | 11.22 | -10.03 |
| serr | lychee | 2.06 | 13.02 | +0.00 | -0.00 | 3.92 | 7.86 | -10.10 |
| serr45 | pear | 4.74 | 12.61 | +0.01 | +0.01 | 1.92 | 3.85 | -10.03 |
| serr45 | orange | 3.75 | 13.91 | -0.01 | +0.00 | 3.77 | 7.55 | -10.06 |
| serr45 | strawberry | 9.15 | 13.65 | +0.02 | +0.02 | 11.18 | 11.18 | -10.02 |
| serr45 | lychee | 6.60 | 12.77 | -0.01 | +0.00 | 10.43 | 11.06 | -10.06 |
| lip20 | pear | 1.53 | 12.57 | -1.51 | **-2.82** | 4.41 | 7.12 | -10.00 |
| lip20 | orange | 7.79 | 14.08 | -0.01 | +0.01 | 1.10 | 2.19 | -10.00 |
| lip20 | strawberry | 13.11 | 13.57 | -0.01 | -0.00 | 5.77 | 11.53 | -10.00 |
| lip20 | lychee | 5.98 | 13.44 | -0.01 | -0.00 | 6.20 | 11.86 | -10.00 |

Ratios to flat (walk / F2mm / Fexit):

| profile | pear | orange | strawberry | lychee |
|---|---|---|---|---|
| `serr` | floor / 1.16x / 1.38x | floor / **3.44x** / 0.98x | floor / **0.77x** / 1.04x | floor / **0.35x** / 1.01x |
| `serr45` | floor / 1.54x / 1.37x | floor / 1.00x / 0.99x | floor / **0.75x** / 1.05x | floor / 1.13x / 0.99x |
| `lip20` | **-2.82 mm / 0.50x** / 1.37x | floor / 2.08x / 1.00x | floor / 1.08x / 1.04x | floor / 1.02x / 1.04x |

"floor" = both the flat and the shape read |walk| <= 0.05 mm (the rig's support
tolerance); a ratio there is noise, not a reduction.

## 3. The promotion test (the brief's rule)

| shape | walk <= 0.6 x flat | break-away >= flat | no crush | promote |
|---|---|---|---|---|
| `serr` | **no** (floor; and 0.35-0.77x on the small classes) | **no** (strawberry 0.77x, lychee 0.35x; Fexit 0.98x on the orange) | yes | **no** |
| `serr45` | **no** (floor) | **no** (strawberry 0.75x; Fexit 0.99x) | yes | **no** |
| `lip20` | **no** (-2.82 mm; 94x the flat) | **no** (pear 0.50x) | yes | **no** |

**No shape promotes.** Per the pre-registration: **no build, no cell.**

## 4. What the fixture says about the class (and what it cannot)

**The sustained walk is not the class's static footprint.** P117/P129 found the
*creep* is lateral (a seat shift along the jaw axis); this phase adds that the
**load-axis** walk under the cell's own load is **zero for the incumbent** (pear
+0.03, orange -0.00, strawberry +0.00, lychee -0.00 mm). So the static rig cannot
certify a pad against the dynamic pry, and the promotion rule's first clause is
**not satisfiable by evidence** - the phase records that as the instrument's limit,
not as a pad property.

**The serration acts, but on the wrong quantity.** It reduces the **total/lateral**
creep on the pear and lychee (6.70 -> 5.47, 12.05 -> 7.86) and *not* on the orange
(8.76 -> 9.71), and it *lowers* the 2 mm break-away on the two small classes
(0.77x / 0.35x) while raising it on the orange (3.44x) and the pear (1.16x). That
is a *seat* effect, not a ratchet: a 1 mm tooth on a 37 mm fruit is a large step,
the contact sits on a crest with less wrap, and the wave above the contact does not
catch the downward walk. The nonzero `lip20` walk (-2.82 mm, down) is the same story
from the other side: extra face below the equator gives the payload *more room* to
seat, not less.

**The teeth that matter are the ones below the contact, and the pad has no room for
them.** The face below the fruit's widest row is the shipped 10.5 mm lip (the pear's
widest is 2.5 mm above the distal plane), less than one 8 mm pitch. The 5-ridge
pattern is anchored at the seat tooth and runs up the plate; the four upper teeth
are the ones an *upward* walk would meet. The fixture's geometry check pins this:
the pear's seat is at u* = -39.9 mm, the pad's distal edge at -42.45 mm; the
strawberry's at -29.1 mm. A 5-ridge **downward** ratchet is not buildable inside the
shipped lip - which is the same belt constraint P39/P69 measured from the other side.

## 5. No-harm

Nothing was built: **no `src/` change, no `configs/` change, no new
`FRUIT_FINGER_FACE` value, no collider change, no default moved**. The shipped hand
is untouched (the new `267` leg asserts `FRUIT_FINGER_FACE` still defaults to
`flat`, the `_add_contact_faces` gate is unchanged, and no `serr` token exists in
`src/fruit_sorting/*.py`).

* `scripts/accept.sh` with every knob unset: **8/10 = 80 %, 9.0 s/attempt,
  `fingerprint: matches configs/motion_reference.json`, `190: PASS`**, and its
  **421 `[fruit]` lines are 421/421 byte-identical** to
  `logs/p127/accept_restored.log` (`logs/p132/accept_noharm_run.log`).
* `scripts/selfcheck.sh`: **PASS (0 failures, 1 skipped)** with the new
  `P132 serrated face` leg (28 checks).
* `scripts/106_index_audit.py`: **OK** (every index matches its files).
* `scripts/107_collect_merge_test.py`: **PASS (21 checks)**.

The fixture's own battery: 48 cells, 112 s wall, one session; the support proof,
the 2-pad manipulation check and the facet-extent check all pass.

## 6. Read rules this phase adds

* **A static axial pull cannot certify a pad against this class.** The incumbent's
  load-axis walk is 0.00-0.03 mm at 1.66 N; a shape's 0.01 mm is noise. The
  resolvable static endpoints are the 2 mm break-away and the lateral seat - and
  the lateral seat is not the class (P117).
* **A fixture's facet frame must be checked against the built prim before its
  table is read.** A left-handed `(tan, nf, w)` frame silently rotates the box 90
  deg and puts the face 20-30 mm behind the pad; a small fruit then falls and the
  table reads as a grip failure. The one-line check is a facet's world extent
  (thickness 10 mm, not 62).
* **The flat control is same-batch.** P117's absolute flat numbers are a rig with
  one 62 mm block; this phase's flat is pear 6.70 / strawberry 12.22 / lychee
  12.05. Quote those when comparing a serration.
* **`crush` is the commanded span** (`dia - 10 mm`, the 5 mm interference per side)
  and the delivered force is the 4.90 N cap; the two together are the P76 guard,
  not the span alone.

## 7. Pins and files

`configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`** and
`..._single.json` = **`8952c320`** untouched; **no reference re-recorded**.
`tasks.py` **`76dbfc6b`**, `rl_env.py` **`b11113fb`**, `scene.py` **`b3bf8067`**,
`assets.py` **`24d29679`**, `fruits.py` **`c8f19228`**, `cage_hand.py`
**`0f56b2ff`**, checkpoint `moe_v13s` **`61da390a`**. New evidence:
`logs/p132/{METHOD.md,PREREG.md,PREREG.md5,RESULTS.md,fixture.py,fixture.log,
p132_report.py,p132_report.txt,run_p132.sh,accept_noharm.log,
accept_noharm_run.log,selfcheck.log,index_audit.log,merge_test.log}`,
`scripts/267_p132_serr_selftest.py`, and the `P132 serrated face` leg in
`scripts/selfcheck.sh`.

**The decision book now has no geometric route left but the workstation**, which
the owner's constraint (the dynamic scattered pipeline must not be stopped,
diverted, gated or paused) excludes. The table's one open number is the dynamic
residual: a blind dynamic cell of the serration, which the phase's own promotion
rule forbids spending without a fixture promotion.
