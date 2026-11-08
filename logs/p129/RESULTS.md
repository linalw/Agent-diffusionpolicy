# P129 - results: the pad material, and why `mu_pair < 1` is not the ring's lever

**Verdict: KILLED on K2.**  A four-pad ring **centres and loads all four pads at the
measured pair friction 1.35** - the material is not what decides the enclosure.
Bench A shows the pair *is* controllable below 1 (0.43 / 0.63 / 0.82 measured at
targets 0.40 / 0.60 / 0.80) and prices the pinch's trade; bench B shows that
neither the algebra's threshold nor the material changes the class.  **No build,
no cell, no `src/` or `configs/` change.**

The phase's most transferable sentence: **the algebra's centring residual is a
*sub-millimetre* quantity, and the line's problem is a *6-56 mm* one.**  P111's
`delta_inf = mu s` is the offset a payload stops at **when the pads stop moving**;
a position-controlled close does not stop, so the ring centres at any friction.
What actually denies the ring's enclosure is (a) the **first-contact freeze**, which
holds the aperture `2 delta0` too wide, and (b) the **presentation** (55.8 mm
along-belt, P110) - neither is a pad property.

---

## 0. What was asked, and what is answered

The owner's nail (i) (`docs/END_EFFECTOR_DECISION.md` section 4.1): a pad whose
**pair** friction with the fruit is below 1, bench first.  Claim: the four-pad
ring cannot centre at 1.25-1.46 and `mu < 1` would make it.

| the book's three numbers | what this phase measured |
|---|---|
| `mu_pair` at the working normal force | **0.43 / 0.63 / 0.82 / 1.02 / 1.22 / 1.38** at targets 0.40 / 0.60 / 0.80 / 1.00 / 1.20 / 1.36 (flat cube, 4.90 N/face; max error **+0.027**).  The sim averages the pair exactly as P104 measured; the pair is a controllable number. |
| creep at the operating load (0.75 s, not a ramp) | **load-axis `dz` = -0.03 .. +0.03 mm** at every mu and every fruit (the friction term's own direction).  The **total** is 8.5-12.4 mm on pear/orange/lychee and **mu-invariant** (8.47 -> 8.68 -> 8.70 -> 8.55 -> 8.59 over the ladder) - a seat shift along the jaw axis, P117's A6 confirmed on a 2.2x ladder. |
| kill: `mu >= 1`, or creep > 1.0 mm at the centring mu | `mu < 1` is reachable (K1 does not fire); the load-axis creep is 0.03 mm (does not fire); **the ring centres at 1.35 anyway (K2 fires)**. |

**The trade (measured, in case the material is ever wanted elsewhere):** at pair
0.6 the pinch's break-away falls to **0.48x** (pear) / **0.49x** (orange) and the
**34-37 mm fruits are ejected during the seat** - 6 of 6 cells at pair 0.6 and 6 of
6 at 0.8 read 0 loaded pads and a 1.2 m fall.  At pair 1.0 and above, 12/12 cells
hold.  So a shared pad material would cost the jaw the small class; a *ring-only*
material would cost nothing, but buys nothing either (section 3).

## 1. The algebra (`logs/p129/algebra.py`, `algebra.txt`)

**Four pads, re-derived.**  Two opposed pads carry the drive (`2 k delta`), the
perpendicular pair carries the friction (`2 mu k s` - its penetration is `s` at
*any* offset, because the plane's distance from a round payload's centre does not
depend on the tangential offset), so

    delta_inf = mu s      and the far pad leaves at delta = s  ->  mu < 1.

The solver reproduces it to <= 2 % (0.176 / 0.236 mm at mu 0.6 / 0.8 on a 29.6 mm
fruit).  Three pads: **0.51 / 0.63 / 0.73 s** at the same mus, **0.84-0.91 s** over
the measured band (P112's own numbers).

**Two corrections to the record.**

1. **P111's headline formula is not its own solver, and not the geometry.**  The
   decision book quotes `delta_inf = (2 mu - 1) min(s, cap/(2 mu k))`.  P111's
   `closed_form` returns `mu s + mu_b m g/(2k)`; the 2-D geometry gives `mu s`.
   The threshold is `mu = 1` in all three, but the residual differs **2x** at
   `mu = 0.6` (0.2 s vs 0.6 s), and *that* is the number the bench tests.
2. **The four-contact state is a window, not a threshold.**  A pad counts as
   loaded at 0.5 N, so the far pad must penetrate `0.5/k` and the near pad must
   not saturate:

       k >= 0.5/(s(1-mu))     and     k <= cap/(s(1+mu))

   which is empty above **`mu = (cap-0.5)/(cap+0.5) = 0.815`** per fruit and above
   **`0.613`** over the whole pool with one stiffness (`s_max/s_min` = 2.35).  At
   `mu = 0.6` the pool-wide window is **`[4223, 4400] N/m`**, a 1.04x sliver that
   **excludes the shipped 1e5 N/m close**.  At the measured mu the four-pad window
   is **EMPTY**; the three-pad window is `[3113, 3677]`, which contains P111's
   measured `[2.9e3, 3.8e3]` - consistent with P111's window being a *three*-pad
   measurement.
3. **A third condition, and it is the one the line meets.**  Capture from an
   offset larger than `s` needs the near pad's cap to beat the perpendicular
   pair's friction: `mu < cap/(2 k s)` = **1.07-2.51** at `k = 3300`, **0.05-0.12**
   at the shipped `k = 1e5`.  At the shipped rigid close the payload cannot slide
   at all - P111's measured knee.

**The price, predicted:** pinch `2 mu N` = **5.88 N at mu 0.6**, i.e. 3.1x the
cell's worst demand `m(g+5.83)` = 1.92 N (the shipped 13.3 N is 6.9x); a four-pad
ring `4 mu N` = 11.76 N (6.1x).  Neither is a force deficit - P104/P117's escape
is a loaded slide at a 10-20x static margin - so the capacity column prices a
*trade*, not an escape.

**A defect found in P112's `algebra.py`:** its `fixed_point` subtracts the drive
(`d = d - mdir*push`), so every trial runs **away** from the ring's centre (its
`d_inf` column reads 18-29 s).  Its closed forms are unaffected and its *fixture*
is the measurement; this phase's solver moves along the drive and is checked
against both closed forms.

## 2. Bench A - the pinch (`logs/p129/fixture_pinch.py`, `fixture_pinch.log`)

Same rig, same 4.90 N/face, same 0.75 s `m(g+5.83)` hold, same 5 N/s ramp as P117;
the `flat` control reproduces P117's table (pear `creep_op` **8.47** vs 8.62,
orange **9.07** vs 9.07, strawberry **0.98** vs 0.98, lychee **12.42** vs 12.42),
so the instrument is P117's.

### A0 - the pair friction, measured (flat cube, a known normal force)

| pair target | pad mu | sum N (2 pads) | F @ 2 mm | `mu_measured` | error |
|---|---|---|---|---|---|
| 0.40 | 0.10 | 9.80 | 4.19 | **0.427** | +0.027 |
| 0.60 | 0.50 | 9.80 | 6.15 | **0.627** | +0.027 |
| 0.80 | 0.90 | 9.80 | 8.06 | **0.823** | +0.023 |
| 1.00 | 1.30 | 9.80 | 10.02 | **1.023** | +0.023 |
| 1.20 | 1.70 | 9.80 | 11.98 | **1.223** | +0.023 |
| 1.36 | 2.02 | 9.80 | 13.44 | **1.375** | +0.015 |

The mapping is linear with a constant **+0.02** offset (the ramp's first 2 mm of
travel), so `mu_measured = target + 0.02` to 0.03.  **`mu_pair < 1` is a real,
controllable number in this sim** - the whole phase rests on it and it holds.

### A1 - the pinch's trade (medians of 3; mm and N)

| profile | pair | fruit | pads | `creep_g` | `creep_op` | **load `dz`** | lateral | F @ 2 mm | F exit |
|---|---|---|---|---|---|---|---|---|---|
| flat | 1.26 | pear | 2 | 4.24 | 8.47 | **+0.008** | 8.47 | 2.61 | 9.45 |
| flat | 1.40 | orange | 2 | 4.53 | 9.07 | **-0.024** | 9.07 | 2.75 | 13.29 |
| flat | 1.41 | strawberry | 2 | 0.48 | 0.98 | **+0.025** | 0.98 | 12.78 | 13.24 |
| flat | 1.34 | lychee | 2 | 6.21 | 12.42 | **-0.007** | 12.42 | 1.35 | 11.06 |
| pair06 | 0.60 | pear | 2 | 4.34 | 8.68 | **-0.028** | 8.68 | 2.57 | **4.49** |
| pair06 | 0.60 | orange | 2 | 5.08 | 10.15 | **-0.022** | 10.15 | 2.58 | **6.46** |
| pair06 | 0.60 | strawberry | **0** | 1244.7 | 1244.7 | -1215.4 | - | - | **ejected** |
| pair06 | 0.60 | lychee | **0** | 1235.0 | 1235.0 | -1215.4 | - | - | **ejected** |
| pair08 | 0.80 | pear / orange | 2 | 4.35 / 4.81 | 8.70 / 9.62 | +0.008 / -0.009 | - | 2.57 / 2.66 | **5.32 / 8.21** |
| pair08 | 0.80 | strawberry / lychee | **0** | 1214.9 / 1284.5 | - | -1215 | - | - | **ejected** |
| pair10 | 1.00 | pear / orange / strawberry / lychee | 2 | - | 8.55 / 9.34 / 0.78 / 12.35 | -0.020 / -0.007 / +0.010 / -0.009 | - | 2.57 / 2.71 / 8.61 / 1.40 | 7.74 / 9.96 / **9.53** / **8.90** |
| pair12 | 1.20 | pear / orange / strawberry / lychee | 2 | - | 8.59 / 9.23 / 5.75 / **17.86** | +0.004 / -0.032 / -0.021 / -0.007 | - | 2.57 / 2.71 / 2.78 / 1.02 | 11.99 / 11.71 / 11.40 / 11.60 |

Four readings, and the first is the important one:

1. **The pinch never creeps along the load, at any mu.**  `dz` is -0.03..+0.03 mm
   on all 20 rows.  The decision book's creep clause, read on the axis the load
   acts along, passes **even at pair 0.6** - because the capacity is still 3.1x
   the demand and the escape class is not a static-creep deficit (P117's
   correction, confirmed on a 2.2x friction ladder).
2. **The total creep is mu-invariant** (pear 8.47 -> 8.68 -> 8.70 -> 8.55 -> 8.59),
   i.e. the book's *letter* ("creep > 1.0 mm") fails every material including the
   incumbent.  That is why the registered reading is the load-axis component; the
   total is reported, not gated.
3. **The axial break falls with mu as `2 mu N`:** pear 9.45 -> 4.49 (0.48x),
   orange 13.29 -> 6.46 (0.49x), pear 5.32 (0.56x) at 0.8, 7.74 (0.82x) at 1.0.
   The prediction is exact at the low rungs; `pair12`'s 1.27x on the pear is the
   A0 offset (its measured pair is 1.20 but the ramp's transient dominates) and is
   reported, not explained away.
4. **Retention is the real cost:** at pair 0.6 and 0.8 the two smallest fruits are
   **ejected during the seat** (0 loaded pads, 1.2 m fall) - 12 of 12 cells at
   those two rungs - because this rig commands a **5 mm interference** (P117's
   constant-force design) and the squeeze-out along the plate's 61 mm width is
   resisted by friction alone.  At pair 1.0+ no cell loses a fruit.  **The rig's
   5 mm seat is harsher than the line's 1 % seat**, so this is a squeeze-out at
   *that* seat, not a prediction of the line; it is still the honest price of a
   *shared* material, and it is why the phase scopes any low-mu pad to the ring.

## 3. Bench B - the ring (`logs/p129/fixture_ring.py`, `fixture_ring_cage4.log`)

**Support proof: PASS.**  Pads home -> the payload does not move (drift
**0.0000 mm** over 200 ticks); a frictionless payload (mu 0.0) closed from 10 mm ->
`off_end` **0.02 mm** (the algebra predicted 0.13).  The read observes a slide.

**A sphere cannot test this, and that is a finding** (build smoke, recorded): every
sphere cell centred to 0.00 mm with 4/4 pads at both pair 0.6 and 1.35.  A sphere's
surface retreats from the perpendicular pair as it transits and the pair's contact
patch leaves the **26 mm plate** beyond `delta ~ 9 mm`, so the payload slides in
**friction-free whatever the material**.  The payload is therefore a **square
prism**, the algebra's own 2-D case.

### The class table (8 cells per row: 2 prisms x 4 arrivals; clean = all pads loaded and `off_end <= 1.5 mm`)

| pair | close k | protocol | **clean** | centred-unloaded | frozen off-centre | all pads | median `off_end` @ 20 mm |
|---|---|---|---|---|---|---|---|
| 0.60 | 4300 | full close | **8/8** | 0 | 0 | 8 | 0.28 |
| 0.60 | 4300 | freeze | 2/8 | 2 | 4 | 2 | 31.14 |
| 0.60 | 1e5 | full close | **8/8** | 0 | 0 | 8 | 0.38 |
| 0.60 | 1e5 | freeze | **5/8** | 1 | 2 | 5 | 4.41 |
| 0.80 | 4300 | full close | **8/8** | 0 | 0 | 8 | 0.15 |
| 0.80 | 4300 | freeze | 2/8 | 3 | 3 | 2 | 32.01 |
| 0.80 | 1e5 | full close | **8/8** | 0 | 0 | 8 | 0.36 |
| 0.80 | 1e5 | freeze | **5/8** | 1 | 2 | 5 | 3.32 |
| 1.00 | 4300 | full close | **8/8** | 0 | 0 | 8 | 0.32 |
| 1.00 | 4300 | freeze | 2/8 | 1 | 5 | 2 | 31.46 |
| 1.00 | 1e5 | full close | **8/8** | 0 | 0 | 8 | 0.11 |
| 1.00 | 1e5 | freeze | 4/8 | 2 | 2 | 4 | 5.18 |
| 1.20 | 4300 | full close | **8/8** | 0 | 0 | 8 | 0.50 |
| 1.20 | 4300 | freeze | 2/8 | 1 | 5 | 2 | 28.65 |
| 1.20 | 1e5 | full close | **8/8** | 0 | 0 | 8 | 0.39 |
| 1.20 | 1e5 | freeze | 3/8 | 3 | 2 | 3 | 5.06 |
| **1.35 (control)** | 4300 | full close | **8/8** | 0 | 0 | 8 | 0.35 |
| **1.35 (control)** | 4300 | freeze | 2/8 | 1 | 5 | 2 | 33.41 |
| **1.35 (control)** | 1e5 | full close | **8/8** | 0 | 0 | 8 | 0.44 |
| **1.35 (control)** | 1e5 | freeze | 3/8 | 3 | 2 | 3 | 5.29 |

**Three readings.**

1. **The full close encloses at every friction, both stiffnesses** - 80 of 80 cells
   are clean (`off_end` 0.00-0.86 mm, all pads loaded).  **The algebra's `mu < 1`
   threshold is not what the closure realises.**  The reason is the algebra's own
   third condition: a position-controlled close keeps pushing (the near pad is at
   its cap, 4.9 N) while the friction is `2 mu N_perp` (0.8-2.1 N), so the payload
   slides in and the four pads load.  `delta_inf = mu s` is the offset a payload
   stops at **when the pads stop** - and they do not.
2. **The freeze is the term that denies the enclosure**, and it is not the
   material: at the shipped rigid close (`k = 1e5`) the clean count is 5/8 at pair
   0.6-0.8 and 3/8 at the control 1.35 - a **+2 of 8** gain from the material,
   confined to the 0/5 mm arrivals, and **0** at the soft close (2/8 at every mu).
   Under a full close the material's gain is **0** (8/8 already).
3. **The 20 mm column is where the line lives**: with the freeze, the median
   residual at 20 mm is 3.3-33 mm at every mu; the low-mu pad does not move it
   out of that class.  The line's arrival is **55.8 mm** (P110), i.e. 2.8x the
   largest arrival this fixture can serve at all.

**cage3 was not evaluable on this payload** (recorded deviation D1,
`logs/p129/PREREG_D1.md`): the support
proof failed - a three-fold ring cannot centre a four-fold face set (10 mm ->
5.19 mm).  The three-pad algebra is P112's measurement (0.84-0.91 s, `pads == 3`
on 18/30 fixture cells) and this phase's re-derivation reproduces it; the phase's
question was the four-pad nail, and P112 already prices the three-jaw.

## 4. The kill

| clause | reading | verdict |
|---|---|---|
| **K1** the material cannot be made (pair `>= 1` at the ladder's pad values) | measured **0.43 / 0.63 / 0.82** at targets 0.4 / 0.6 / 0.8 | **does not fire** |
| **K2** the material is not needed (the shipped pair already encloses under a full close) | the control (pair 1.35, k 1e5, full close) is **clean on 4/4 cells** at 10 and 20 mm, `off_end` **<= 1.5 mm** | **FIRES** |
| **K3** the line's protocol denies the enclosure at every mu | 34/40 freeze cells at >= 10 mm lack a pad, but not all (5/8 clean at pair 0.6-0.8, k 1e5) | not uniform |

**K2 fires -> the negative is published and no cell is spent.**  The purchase the
nail proposed (a low-friction face material) does not buy the ring's enclosure;
the term that does is the **close protocol** (and, upstream of it, the delivery).

## 5. What the record now says (corrections)

* **P111's `delta_inf = (2 mu - 1) min(s, cap/(2 mu k))` is not its own solver's
  number** and not the 2-D geometry: the four-pad residual is `mu s`.  The
  threshold `mu < 1` is right; the residual is 2x smaller at `mu = 0.6`.
* **The four-pad enclosure's friction ceiling is 0.815, not 1** (the 0.5 N trigger
  and the cap set it), and **0.613 pool-wide** for one stiffness.  The material
  requirement is *tighter* than the book's, not looser - which makes K2's result
  stronger, not weaker: even at the incumbent 1.35 the ring encloses.
* **The V-block that P111/P112 measured on the line is not a friction object.**
  It is the **widest-extent aperture law** (the perpendicular pair is 1-6 mm short
  on an anisotropic fruit, so it is *never* in contact whatever the material) plus
  the **first-contact freeze**.  The fixture reproduces both: the full close on a
  round payload loads 4/4 at 1.35; the freeze at 1.35 reads 3/8 clean.
* **The decision book's creep clause cannot discriminate a material** if it is
  read on the total displacement: the pinch's total creep is a mu-invariant seat
  shift (8.5-12.4 mm).  The load-axis component is 0.00-0.03 mm at every mu.
* **P112's `algebra.py` `fixed_point` has a sign error** (it runs away from the
  centre); its closed forms and its fixture are unaffected.

## 6. Named next (priced, not registered here)

1. **The ring with the freeze off** - the fixture says the *shipped* material
   envelopes a 0-20 mm arrival with all four pads when the close is not frozen
   (8/8 clean, 80/80 cells).  On the line that is one existing knob
   (`FRUIT_DYNAMIC_CLOSE_FREEZE=0`), a single-arm `cage4` cell at 2 seeds x 20
   attempts, endpoints P110's clean enclosure + the placed count, guards crush /
   landing / descent budgets.  **This is the cell the material was supposed to
   justify, and it needs no pad.**
2. **The delivery** remains the binding term for the line's 55.8 mm arrival
   (P110's §3.2: 6 mm / 3.4-4.5 mm / 1.8 mm / 17.5 mm against the ring's 0.6 mm).
   No closure change reaches it.
3. **If a low-mu pad is ever wanted for another reason**, its price is bench A1:
   the pinch's break-away falls to 0.48-0.49x and the 34-37 mm fruits are ejected
   at P117's 5 mm seat; the load-axis creep does not move.  Scope it to the ring.

## 7. Guards

* **No-harm:** `scripts/accept.sh` with every knob unset reads **8/10 = 80 %,
  `fingerprint: matches configs/motion_reference.json`, `190: PASS`**
  (`logs/p129/accept_noharm.log`), and its **421 `[fruit]` lines are 421/421
  byte-identical** to `logs/p127/accept_restored.log`
  (`python3 logs/p129/p129_report.py --same`).  This is an import guard - the
  scripted line never constructs the cage - but it is the run the tree owes.
* `scripts/selfcheck.sh` - PASS with the new `P129 pad material` leg
  (`scripts/265_p129_material_selftest.py`, 18 checks: the unset path of the four
  cage knobs, the openarm finger material's two default sites, the pair
  arithmetic 1.25-1.46, and the algebra's 0.815 / 0.613 / 4223-4400 thresholds).
* `python3 scripts/106_index_audit.py` -> **OK: every index matches the files it
  describes**; `python3 scripts/107_collect_merge_test.py` -> **PASS: all 21
  checks**.
* **No `src/` or `configs/` change**, so no reference was owed or re-recorded:
  `configs/motion_reference.json` = `..._twoline.json` = `30fb99f8`,
  `..._single.json` = `8952c320`.

## 8. Pins and evidence

Pins (unchanged by this phase): `tasks.py` `50fd799d`, `cage_hand.py` `42c4eb64`,
`scene.py` `b3bf8067`, `assets.py` `24d29679`, `rl_env.py` `3aed67b9`,
`conveyor.py` `fb2c58c6`, `fruits.py` `dcabe16b`, `control.py` `9384ff4f`,
`bimanual.py` `9b7fc33f`; refs **`30fb99f8` / `30fb99f8` / `8952c320`**;
ckpt `moe_v13s` `61da390a`.

New in `logs/p129/`: `algebra.py` + `algebra.txt`, `fixture_pinch.py` +
`fixture_pinch.log`, `fixture_ring.py` + `fixture_ring_cage4.log`,
`p129_report.py` + `p129_report.txt`, `run_p129_pinch.sh`, `run_p129_ring.sh`,
`METHOD.md`, `PREREG.md` (+ `.md5`), `PREREG_D1.md`, `RESULTS.md`; `scripts/265_p129_material_selftest.py`
and the selfcheck leg.
