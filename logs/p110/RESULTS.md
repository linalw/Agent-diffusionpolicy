# P110 results - the presentation lane: the gate works and still cannot enclose the ring

Owner's item: P108's routes 1 + 2's gate - **the last unspent term** of the
end-effector lane (P109 closed the descent margin, P108 the aperture and the
spacing).  Registered in `logs/p110/PREREG.md` (md5 **`cce8838c`**, pinned at
23:05 before any simulator run).  **Nothing adopted, no default changed,
`configs/` untouched, no `src/` change, no commit.**

**The one-sentence answer.**  An **8 mm kerb across the belt holds every fruit in
the pool at 0.12 m/s with the belt running (16/16, a 0.85-1.83 mm hold,
0.11-1.05 N of steady drag)** - and it still cannot make the cage enclose,
because the ring's single radial synergy needs the payload centred to
**0.6 mm** while the gate's own hold is **1.8 mm** and its parking position
spans **17.5 mm** across the pool.  **The presentation is a real mechanism and
it is not the ring's term.**  The enclosure is `2/74` clean, not P107/P108's
`11/74` - the phase's re-census finds that bucket's majority is *jam* and
*crush*.

## 0. Admissibility: the phase changes no `src/` file, so the tree is its own control

Both instruments are `logs/`-only: `census.py` is offline (records + code
arithmetic) and `fixture_gate.py` builds its **own** scene
(`SortingScene(cfg).build(parts=("environment", "conveyor"))`) and its **own**
spawner, so no cell, store or reference can move.  The no-harm is therefore the
shipped acceptance itself:

| check | result |
|---|---|
| `scripts/accept.sh` (every knob unset) | **8/10, 9.0 s/attempt, `fingerprint: matches configs/motion_reference.json`, `190: PASS`** |
| its `[fruit]` stream vs `logs/p109/accept_final.log` | **byte-identical** (420 lines, same md5; P109 quoted 419 under one more dropped row) |
| `scripts/selfcheck.sh` | **PASS (0 failures, 1 skipped)** |
| `python3 scripts/211_bed_audit.py` | **ok (115 checks)** |

## 1. The census: the 56 mm is a descent property, and the lateral term is 2.6 mm

`logs/p110/CENSUS.md` is the phase's first half; the four numbers it fixes here:

* the **split at the band entry** is **55.8 mm along-belt / 2.6 mm lateral**
  (p50; the 11.8 mm the record quotes is the **max over the window**, the arm's
  x-tracking lag).  The along-belt share is **92.5 %** at the entry.
* **`fruit dy = speed * t_desc` = 83.0 mm** p50 (114 descents): the belt travels
  83 mm while the hand descends 56-60 mm.  The margin cancels inside it (P109),
  so a faster margin cannot shorten it either.
* the entry offset is that same clock minus the part of the leg before the
  plate's face is level with the payload's top (`A_y` **182 mm** at p50 with the
  pool's 35 mm `r_max`), and the measured 55.8 sits **below** the 62.8 mm a 6 cm
  fruit predicts **because the plates arrest the payload** - **25 % of the band
  window's ticks run below half the belt speed** (p90 58 %).
* the sign the catch needs is unchanged: the descent ends with the payload
  **upstream** (P109's +10.6 mm), and the close is within its own tolerance
  (`dy` p50 -4.7, `dx` -6.0 mm - the catch-up's 6 mm).  **The 56 mm is an arrival number, not a grasp
  number.**

**Form (a), the lateral guide, is dropped by arithmetic**: `dx -> 0` leaves
`A_y = 182 mm` **unchanged** (the aperture need is per axis and along-belt
dominates), so P108's screen does not move (120 mm 0/8, 160 mm 5/8, 210 mm
7/8), and the guide's only purchase is 39 % of the *close-time* radial.  The
tree's own lateral guides prove the point geometrically: `containment_parts`'
side fences are a **0.300 m channel against a 0.160 m delivered band**, so they
never touch a fruit; a guide that did would have to be narrower than the band,
and the open hand already needs 0.132 m of it.  **Not built, not measured.**

## 2. Form (b): the gate holds the whole pool, at any height from 8 mm

`fixture_gate.py`: the real belt (kinematic body + `PhysxSurfaceVelocityAPI`),
the real pool (`FruitSpawner`, 16 fruits, 29.6-69.6 mm, 9.5-122.8 g, mu
0.51-0.92), and a kinematic kerb across the belt whose upstream face sits 20 mm
downstream of the station.  Each cell runs all 16 fruits singly.

| `h` | held | escaped | gate peak p50 | **steady drag p50** | **hold span p50 / max** | park p50 | park spread | hand |
|---|---|---|---|---|---|---|---|---|
| 8 mm | **16/16** | 0 | 1.27 N | **0.49 N** | 0.85 / 5.00 mm | +0.0024 | 13.1 mm | OK |
| 10 mm | **16/16** | 0 | 1.44 N | 0.50 N | 0.91 / 6.57 mm | +0.0044 | 14.0 mm | OK |
| 12 mm | **16/16** | 0 | 1.50 N | 0.53 N | 1.33 / 6.14 mm | +0.0060 | 15.3 mm | OK |
| **14 mm** | **16/16** | 0 | 1.79 N | **0.55 N** | **1.82 / 5.62 mm** | +0.0078 | **17.5 mm** | OK |
| 20 mm | 16/16 | 0 | 1.86 N | 0.68 N | 1.82 / 4.06 mm | +0.0096 | 19.6 mm | collides |
| 30 mm | 16/16 | 0 | 2.19 N | 1.06 N | 1.22 / 3.72 mm | +0.0115 | 21.5 mm | collides |
| 45 mm | 16/16 | 0 | 2.52 N | 1.15 N | 1.01 / 3.76 mm | +0.0115 | 21.7 mm | collides |

**So `K4` does not fire, and by a wide margin.**  The brief's question "does a
gate hold a 30-70 mm range without crushing" answers **yes at every height
tried, including 8 mm** - i.e. well inside the hand's own **14.5 mm**
(`jaw - 0.0805`) - and there is no crush: the peak force is the *impact*
(1.27-2.52 N p50), the steady drag is **0.11-1.05 N**, and the belt's encoder reads
**-0.120 m/s in every cell: the belt never stops.**

Two by-products worth naming:

* **a taller gate parks the fruit further upstream** (`y_park` +0.0024 at 8 mm
  to +0.0115 at 45 mm): the contact latitude rises with the wall, so the
  cheapest height is also the most accurate one.
* **the shipped line's own nudge is inert against the gate**: `wake=0` (no
  `fruits.enforce_transport`, whose rule forces -0.048 m/s on any fruit below
  0.02 m/s) reads **exactly** the `wake=1` cell (1.82 mm, +0.0078, 1.79 N).
  The PREREG predicted this coupling would matter; it does not.

### 2.1 The queue: it does not singulate, and it ejects one fruit in sixteen

The stream cells release the rest of the pool at the **shipped cadence**
(0.225 m of belt = 1.875 s apart) behind the subject:

| cell | fruits behind | hold span p50 / max | gate peak | expelled |
|---|---|---|---|---|
| `h14` (sole occupant) | 0 | **1.82 / 5.62 mm** | 1.79 N | 0/16 |
| `q2` | 1 | 4.25 / 7.98 mm | 1.93 N | 0/16 |
| `q4` | 3 | **4.87 / 30.78 mm** | 1.88 N | **1/16** |
| `q8` | 7 released, the extra ones stay upstream | 4.87 / 30.78 mm | 1.88 N | 1/16 |

**The next fruit arrives inside the same attempt** - the shipped 0.83-2.9 s
cadence against a 15.1 s pick - and it costs the hold: **1.8 -> 4.3 mm** with one
behind and **4.9 mm** (max **30.8 mm**) with three, where **one of the sixteen is
expelled**
past the gate (a 65.1 mm peach, mu 0.59, parked 501 ticks then pushed 62 mm
through).  That is the cadence cost the arithmetic predicted (8.1 fruit per
15.1 s cycle into a belt that holds ~5) - measured as a *load* and an
*ejection*, not as a jam.

### 2.2 The release

`mu_pair(gate) * steady drag` = **0.16-1.32 N** of extra upward drag on the lift
(the gate's pair reads ~1.35 against the fruit's 0.51-0.92): **1.3-10.4 %** of
the pinch's 12.7 N capacity, median **0.76 N = 6 %**.  The release is **not** the gate's
problem; the *height* is, and 8-14 mm clears the hand.

## 3. Why it still does not enclose the ring - the phase's correction

### 3.1 "Enclosure at >= 3 pads" is 2/74, not 11/74

The P108 `E` cells' `[cage]` rows, joined to each attempt's own descent `end=`
and the ring's own aperture:

| class | rule | n | `end` p50 | `aper` p50 | `F` p50 |
|---|---|---|---|---|---|
| blocked-descent **jam** | `end > 15 mm` | 5 | 79.8 mm | 88.1 mm | **1074 N** |
| over-closure **crush** | `aper < dia - 4 mm` or `F > 4 cap 1.5` | 4 | 9.4 mm | 32.5 mm | **119 N** |
| **clean enclosure** | the rest | **2** | 10.2 mm | 63.9 mm | 13.0 N |

**The clean rate is 2/74 = 2.7 %**, the two clean rows read `clr` **-9.5** and
**+31.7 mm** (so the approach clearance does **not** order them - the jams are
the large-`clr` class at `clr` p50 +32.9 mm), and the modal grasp is **2 pads at
the cap** (22/74, `F` 9.74 N = 1.99 cap-pairs): a V-block, `n = 2`, the **same**
axial capacity as the shipped pinch.  The record's enclosure endpoint is
therefore an artefact of three different events sharing a pad count - and the
phase did not re-tune anything to say so.

### 3.2 The closure's own arithmetic: 0.6 mm, and the line's best is 6 mm

One radial synergy, four force-capped position pads, `a = 0.49 d`, cap 4.90 N,
`k = 1e5 N/m`: the elastic allowance is **0.049 mm**; a payload offset by
`delta` has its near pad commanded `delta + 0.01 d` inside its surface and its
far pad `0.01 d - delta` short of contact, so **the far pads reach only when
`delta < 0.01 d = 0.6 mm`** - above that the near pads push at the cap and the
payload is *launched* (the measured `bat` 27-82 mm / `bat_rel` 9-330 mm).

**The line cannot deliver 0.6 mm:**

| term | value | source |
|---|---|---|
| the catch-up's convergence tolerance | **6 mm** | `FRUIT_DYNAMIC_CATCH_TOL` |
| the measured close-time offset | **8.8 mm lateral / 20.2 mm along** | P108's aim census (726 attempts) |
| the gate's hold, within a fruit | **1.8 mm** (max 5.6) | this fixture |
| the gate's parking position, across the pool | **17.5 mm** | this fixture |

So the ring asks for **3-29x** tighter positioning than anything on the line
delivers, and the gate's *best* case (a sole occupant, 1.8 mm) still misses by
3x.  **The gate removes the *arrival* term (`A_y` 182 -> 70 mm, a precondition
P108's aperture already pays for) and not the *centring* term the closure needs.**

## 4. The decision rule, clause by clause

| clause | registered | measured | verdict |
|---|---|---|---|
| **K1** the guide's `A_y` gain | 0 | 0 mm (`A_y` 182 -> 182) | **fires** - form (a) dropped |
| **K2** the gate's centring vs 0.6 mm | < 0.6 mm | **1.8 mm within / 17.5 mm across** | **fires** |
| **K3** the queue vs the belt | <= the belt's capacity | 8.1 fruit = 1.81 m > 1.60 m; **measured: 1/16 expelled at 3 behind** | **fires** |
| **K4** a <= 14.5 mm kerb holds the pool | all held | **16/16 at 8, 10, 12, 14 mm** | does **not** fire |

**VERDICT: the presentation lane closes - DETECTED (the gate is a working,
cheap, non-crushing mechanism) BUT NOT CONVERTIBLE (it cannot centre the ring,
and it needs a selection rule, a different pick mode and a magazine).**  The
end-effector lane's remaining levers, in the order the record now prices them:

1. **a compliant closure** - per-pad compliance so the ring can absorb a 10 mm
   offset instead of launching it (a `cage_hand.py` change: four springs or four
   independent force targets).  This is the *only* term the phase's arithmetic
   leaves standing, and it is a hand change, not a scene or a control one.
2. **a sub-millimetre catch tolerance** - `FRUIT_DYNAMIC_CATCH_TOL` 6 -> 0.5 mm
   is a one-env-knob experiment *only* with a stationary fruit (a moving one
   cannot be tracked to 0.5 mm at 1 mm/tick), i.e. it rides on the gate and the
   magazine.
3. **`docs/LEFT_ARM.md`'s two sanctions** - a new pad asset and a real-jaw
   clamp-force anchor (P104/P106 measure the shape's capacity; the sim has no
   bruise model, so "60 N works" is a geometry statement).

**What is *not* a lever, and the phase says so:** a bigger aperture (P108), a
lateral guide (this phase, 0 % of `A_y`), a metering gate (this phase, 3-29x
too coarse), the descent margin (P109), the seat (P42), the force cap (P76/P77),
the closure depth (P108), and the profile blocks (P87/P88/P89/P91).

## 5. Deviations

* **D1 - the PREREG's "0-17 mm parking spread" is a *pool* number, and the
  fixture separates it.**  Within one fruit the hold is **1.8 mm**, across the
  pool **17.5 mm**.  Both are above the ring's 0.6 mm, so `K2` stands, but the
  honest statement is the pair, not the single spread.  The PREREG's own figure
  (~0-17 mm from the radius algebra) is confirmed to the mm.
* **D2 - the PREREG predicted `enforce_transport` would fight the gate** (its
  rule forces -0.048 m/s on a fruit below 0.02 m/s).  Measured: `wake=0` and
  `wake=1` are identical.  Recorded, and it removes a coupling from the price.
* **D3 - the `q8` cell is not a deeper queue than `q4`**: the stream releases at
  the shipped 1.875 s cadence and only three fruits reach the gate inside the
  12.5 s run, so `q8` reads `q4`'s numbers.  The *load* claim is therefore
  carried by `q4` (3 behind), and the 8-fruit queue is an argument from the
  *rate* (8.1 per 15.1 s cycle), not a measurement of eight in contact.
* **D4 - the fixture measures contact mechanics, not the arm.**  No attempt, no
  enclosure, no placement.  The four-seed arm battery was **not spent**, and the
  reason is the PREREG's own inequality (`K2`): no arrangement of a passive
  element changes it, and the cage's clean enclosure is 2/74 *without* one.

## 6. What shipping a gate would owe (it is not licensed)

A gate is a **scenario** element (a new collider set), so a flip would owe: both
motion references re-recorded from same-batch 10-attempt runs, the acceptance
re-based, **every store re-baselined**, the **`scene` manifest block** extended
with the gate's geometry (P71/P72's rule - a store must name the collider set;
`assets.scene_provenance` is the one builder), the **selection rule** (the
station window's lower edge) and the **pick mode** documented as part of the
cell, and a magazine or a throttled infeed for the queue.  The phase prices it
and does not ship it: `configs/motion_reference.json` = `..._twoline.json` =
**`30fb99f8`**, `..._single.json` = **`8952c320`**, all untouched.

## 7. Files and pins

`logs/p110/{CENSUS.md,census.py,census.txt,PREREG.md,PREREG.md5,RESULTS.md,
fixture_gate.py,run_p110.sh,p110_report.py,fixture.txt,gates.sh}` and the cells
`fix_{h8,h10,h12,h14,h20,h30,h45,h14_nowake,q2,q4,q8}.log` (+ the drivers).

**The tree is unchanged by this phase** (no `src/`, no `configs/`): `tasks.py`
`d341b0da`, `rl_env.py` `bf4c56fa`, `bimanual.py` `9b7fc33f`, `fruits.py`
`dcabe16b`, `conveyor.py` `fb2c58c6`, `assets.py` `eb30c77a`, `scene.py`
`a0199097`, `cage_hand.py` P107's final; references **`30fb99f8`** /
**`30fb99f8`** / `8952c320`; ckpt `moe_v13s` `61da390a`.
