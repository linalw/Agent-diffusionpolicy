# P50 phase 1 — the per-instance release offset (the table, the fits, the tails)

Measured 2026-10-27 with **claimed simulator runs** (seven runs of record, 20-250 s
of simulated time each, plus two smokes and one re-run after a print fix) and an
offline re-derivation (`logs/p50/p1/offset_table.py`). **No `src/` change, no
`configs/` change, no commit, no shipped default changed.** Tree read clean at
HEAD `3a8a581`; `fruits.py` `dff684b1`, `meshes.py` `1ad5af0e`, `tasks.py`
`b6de439c`, `rl_env.py` `93e35ef7`, `scene.py` `27e3d64a`,
`configs/motion_reference.json` `8a399626`, `..._twoline.json` `2246f83c` — i.e.
exactly the P44/P45/P49 pin, so every log below was produced by this source.

The question P38 left as a corollary and P49 named as the next lever: **the
delivered lateral x is `spawn x + offset(instance)` — is that offset a measurable,
stable, per-instance quantity, and can it be compensated at `respawn` so the
delivered x lands inside the 0.18-0.39 band?** The answer is **yes, for 14 of the
16 pool instances exactly, and for the other two within one mode (11-20 mm)** —
and the offset cannot be shipped as a table, it has to be measured per pool.

**The one-line answers.**

1. **The offset is a per-instance constant to 0.00 mm.** Over the 16 instances of
   the shipped pool at seed 5, two independent passes over 48 cells are
   **bit-identical** (max spread **0.00 mm**), a 3-repeat cell is
   `-2.90 / -2.90 / -2.90 mm`, and the offset does not change while the fruit
   rides (settle → station edge: **0.09 mm** over 215-224 ticks — P38's
   `transport = 0.000 mm`, re-confirmed on the delivered path).
2. **It is not a function of the spawn x.** 13/16 instances are x-independent to
   **≤ 0.5 mm** across the whole 0.16 m band; the three exceptions are
   instance-specific *modes*, not a slope (a per-instance linear slope spans
   `+0 / -86 / -93 mm/m`, pool median `-0 mm/m`).
3. **It reproduces in the shipped line.** With the feeder running (the free
   cadence) and **every release attributed** by a `respawn` wrapper, the live
   delivered offset matches the table at the release's own x for **55/65 releases
   to ≤ 0.5 mm and 60/65 to ≤ 2 mm**; the 5 residuals are one kiwi's two modes
   (max 18.2 mm).
4. **It cannot be a shipped (species, diameter) table.** Two strawberries
   **0.9 mm** apart in diameter read **+20.00** and **-24.30 mm** (a 44.3 mm
   within-species spread); the pooled least squares over the 48 cells leaves a
   residual sd of **10.19 mm** and a max |residual| of **31.0 mm**. The offset is
   a property of the **authored mesh**, so it must be measured per pool.
5. **The tail arithmetic closes.** Uncompensated, the shipped `U(0.20, 0.36)`
   draw plus the measured offsets delivers **0.35 %** of releases below 0.180 and
   **0.56 %** above 0.390, min 0.173, max 0.400 — the same order as P38's
   measured census (0.77 % / 1.7 %). Compensated at one x, **0.00 % / 0.00 %**,
   min 0.199, max 0.365; paired on the actual live draws, the 3.08 % above 0.36
   and 1.54 % below 0.20 become **0 / 0** with max 0.360-0.363.

---

## 1. The probe

`logs/p50/p1/offset_probe.py` — the skeleton of `logs/p38/probe_drift.py` (the
shipped scene + `FruitSpawner`, `raise_fd_limit`, and the fixed-step pump
`SimulationManager.step(1)` + `app_utils.update_app(steps=0)`, AGENTS §3b), with
three modes:

| mode | what it does | why |
| --- | --- | --- |
| `isolated` (default) | parks all 16 bodies, then for each instance × each commanded x: `respawn(sample, along=spawn_y, x=x_cmd)`, steps, reads the settle x | the per-instance table, with the instance under control |
| `live` | the shipped free-cadence feeder (`update` every tick), with `respawn` **wrapped** so every release records `(index, commanded x, tick)`; each body's x is followed from its first tick to the station edge | the shipped condition, **release-attributed** — the thing P38's probe could only guess |
| `along` | one instance dropped at four along positions | is a ladder calibration legal? |

**The scenario** for the table of record: the shipped scattered supply
(`FRUIT_SUPPLY_SCATTER=1`, patch/wave/bed off), pool 16 (two instances per class,
the designed 8/5/3 grade mix), `SEED=5` (the acceptance seed), belt `0.12 m/s`,
`spawn_y = 0.68`, `pick_y = 0.0`, belt top `1.170 m`, dt `1/120 s`. Each fruit is
placed `30 mm` above the belt with `v = (0, 0.12, 0)`, `ω = 0` and identity
orientation — `FruitSpawner.respawn`'s own release, unchanged.

**The probe draws no random number.** `respawn` draws from `self.rng` only when
`x`/`along` are `None`; with an explicit `x` and `along` (and `along_jitter = 0`)
the pool's stream is untouched, so pass A and pass B see **identical instances**.
That is what makes the repeat a determinism test instead of a fresh draw. In live
mode the wrapper draws the lateral uniform itself (`rng.uniform(x_min, x_max)`)
and passes it in, which consumes the *same single call at the same point in the
stream* — the schedule is unchanged, the probe just knows the value.

**The settle window**: 420 ticks = 3.5 s (0.42 m of belt travel). The measured
last tick with any x motion is **137** over 144 spawns, so a 420-tick table is
~3x margin and a **200-tick read is a safe calibration point** (this matters for
the implementation cost, §PREREG).

**The geometry read** (`[offset] geom`): the authored mesh's point cloud is read
back from the stage per instance — the local `z` extent (is the commanded 30 mm
bottom clearance real for this hull?) and the lateral position of the lowest
vertex. The collider is the `convexHull` of exactly these points
(`meshes.author_fruit`), so a release-geometry property should be visible there.
It is not a model, but it is not noise either (n = 16, seed 5): the lowest
vertex's lateral offset is **uncorrelated** with the release offset
(Pearson `-0.09`), the mesh centroid's x weakly correlated (`+0.46`), and the
**commanded bottom clearance `bottom_gap` at `-0.62`** — a hull whose lowest point
starts nearer the belt (or below it) rolls further. That is a named candidate for
a zero-sim predictor (a depenetration-kick mechanism), reported and **not** used
(§11).

**The instrument is read-only**: fruit-pose reads (the documented safe read class),
`SimulationManager.step`, and `spawner.enforce_transport` — no attempt, no control
input, no camera. `logs/p49` §1.2's test (a print-only census inside an arm is
`[fruit]`-identical) is the precedent; here there is no arm to perturb.

## 2. The table (seed 5, the acceptance seed)

Offset = `x(settle) - x(commanded)` in mm, at the spawn band's floor, centre and
ceiling. `pass spread` is the range over the two passes (identical instances).

| idx | species | dia mm | off @0.20 | off @0.28 | off @0.36 | max \|Δx\| mm | pass spread mm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 00 | lychee | 29.6 | -3.00 | -2.90 | -2.98 | 0.10 | 0.00 |
| 01 | lychee | 34.4 | +4.30 | +4.30 | +4.30 | 0.00 | 0.00 |
| 02 | kiwi | 55.8 | **+54.61** | **+35.06** | **+39.80** | **19.55** | 0.00 |
| 03 | peach | 65.1 | +5.42 | +5.42 | +5.42 | 0.00 | 0.00 |
| 04 | apple | 65.2 | -0.71 | -0.71 | -0.71 | 0.00 | 0.00 |
| 05 | strawberry | 37.2 | **-22.01** | **-24.30** | **-35.71** | **13.70** | 0.00 |
| 06 | tomato | 66.1 | +6.72 | +6.71 | +6.72 | 0.01 | 0.00 |
| 07 | tomato | 61.8 | -6.26 | -6.26 | -6.26 | 0.00 | 0.00 |
| 08 | strawberry | 36.3 | +18.75 | +20.00 | +18.76 | 1.25 | 0.00 |
| 09 | pear | 68.1 | +2.57 | +2.58 | +2.58 | 0.01 | 0.00 |
| 10 | orange | 63.6 | -26.96 | -26.97 | -26.97 | 0.01 | 0.00 |
| 11 | pear | 60.6 | +0.52 | +0.52 | +0.52 | 0.00 | 0.00 |
| 12 | peach | 68.9 | +6.45 | +6.42 | +6.44 | 0.03 | 0.00 |
| 13 | kiwi | 53.8 | +53.13 | +53.12 | +53.08 | 0.05 | 0.00 |
| 14 | orange | 65.8 | -0.39 | -0.39 | -0.40 | 0.01 | 0.00 |
| 15 | apple | 69.6 | -2.52 | -2.52 | -2.52 | 0.00 | 0.00 |

**What the table says.** 13 of 16 instances carry a single constant to ≤ 0.5 mm
across the whole band. The three that do not are **one kiwi (idx 02, 19.6 mm) and
two strawberries (idx 05, 13.7; idx 08, 1.25)** — the roughest small hulls
(`meshes.FRUIT_SHAPES`: kiwi `bumpy=0.030` and the pool's highest friction
`0.75-1.05`, strawberry `bumpy=0.035`): they land, the belt drags them, and a
lopsided hull converts that into a slow lateral roll of 20-55 mm over ~1 s
(`last_step_tick` 100-137 vs 20-96 for the rest). **The roll ends in one of a few discrete modes**,
and which mode a given release takes depends on the release's exact initial
condition — not on a smooth x field.

That is why the "is it x-independent" question has a two-part answer:

* **for the 13 non-rollers: yes**, to ≤ 0.5 mm (the largest, idx 08, is 1.25 mm);
* **for the rollers: the offset is not a function of x either** — it is a
  *selection among modes*. The same strawberry (idx 05) reads `-35.71` at
  `x = 0.36` **and** at `along = 0.50` (see §6), i.e. one mode reached from two
  different starting points, while `-22.0` is its most common mode.

The **shipped-condition table** (what the compensation should use) is the wake
variant, §4: it differs from this one on exactly one instance, kiwi idx 13
(`+35.03` instead of `+53.12`).

## 3. Reproducibility

| read | value |
| --- | --- |
| the 3-repeat cell (idx 00, x 0.28, three fresh drops) | `-2.90 / -2.90 / -2.90 mm` → spread **0.00 mm** |
| pass A vs pass B, all 48 cells | max spread **0.00 mm**, mean 0.000 mm |
| settle → station edge (3 instances, 215-224 ticks) | max x motion **0.09 mm** |
| seed 77, two processes × two settle windows (180 / 420 ticks) | every cell ≤ **0.15 mm** (e.g. kiwi idx 14: `+69.41/+70.20/+41.89` vs `+69.32/+70.11/+41.93`) |
| last tick with any x motion (144 spawns) | **137** |

So the probe has **no measurable noise floor at the print precision**: a fixed
`(instance, x, along)` reproduces its offset bit-identically, in the same process
and across processes. Everything that looks like variance in §4 is a *different
initial condition*, not instrument noise.

## 4. The shipped line: the wake loop and the live reconciliation

Two things the shipped feeder does that a bare `respawn` does not:

* **`enforce_transport`** (`fruits.py:2325`) wakes a fruit whose along speed has
  dropped below `0.02 m/s` by re-applying `belt_speed * 0.40` **and zeroing its
  angular velocity** — i.e. it can arrest a roll. It runs from `update`, which the
  driver calls in its between-attempt feed window — the window the settle happens
  in. Adding it to the probe (`FRUIT_OFFSET_WAKE=1`) changes **exactly one**
  instance: kiwi idx 13 `+53.12 → +35.03` (Δ 18.1 mm); the other 15 are
  bit-identical.
* the releases themselves (a neighbour 0.10-0.35 m downstream).

**The live run settles which is the shipped value.** The feeder ran free for
120 s with the release attributed: **65 releases across all 16 instances**
(4-5 per instance), and the per-row residual against the wake table at that
release's own x is **≤ 0.5 mm in 55/65, ≤ 2 mm in 60/65**, max 18.23 mm. The
per-instance picture, and the three that carry the residual:

| idx | species | live n | live min / max mm | residual vs table mm | what it is |
| --- | --- | --- | --- | --- | --- |
| 02 | kiwi 55.8 | 4 | **+34.98 / +54.63** | **18.23** | **two modes**: `+54.6` twice, `+35.0`, `+39.7` |
| 05 | strawberry 37.2 | 4 | **-35.73 / -22.10** | **11.37** | two modes: `-22.1` ×2, `-35.7`, `-24.3` |
| 08 | strawberry 36.3 | 4 | +18.69 / +18.69 | 1.26 | one mode, table at 0.28 |
| 12 | peach 68.9 | 4 | +6.37 / +6.64 | 0.21 | one mode |
| the other 12 | — | 4-5 | span ≤ 0.27 | ≤ 0.21 | one mode, exact |

**So the shipped condition is the wake table for 15/16 instances**, and kiwi idx 02
is **bimodal in the line itself** (two of its four releases at +54.6, one at
+35.0, one at +39.7, at nearly the same x). Its value cannot be predicted — only
bounded.

**Cross-check against P38 (an independent probe, an independent run).** P38's
per-class table at seed 77 lists kiwi `-20.20/+15.04`, peach `-10.53/+0.72`,
tomato `+3.88/+4.59`, apple `+0.39/+2.58`, orange `-1.23/-2.66`, pear
`+1.24/+2.24`, lychee `-0.17/+6.40`, strawberry `-0.17/+3.48`. This probe at the
same seed measures (per *instance*) apple `+0.35/+2.57`, pear `+1.29/+2.22/+2.23`,
peach `-10.68/-1.49`, lychee `-0.29/-0.21/+9.00/+9.19`, orange `-5.44/-2.71`,
tomato `+2.23/+6.82`, strawberry `+30.04/+4.43`, kiwi `-52.82/+69.32`. The small
classes agree to **0.04-0.15 mm**; the kiwis do not — and they cannot: **P38's
transit splitter restarts `x_first` mid-roll**, so one 60-70 mm roll is split into
two small `spawn→edge` increments. P38's own text carries the evidence: its
out-of-band list has `x=+0.401 spawn=+0.359 (+42.0 mm) kiwi dia 64` and its §2
quotes "`+69.2 mm` for a kiwi drawn at 0.343 and delivered at 0.413" — those are
this table's `+41.9` and `+69.3`. **P38's per-class kiwi row is an artifact of its
transit boundaries, not the instance offset**; the mechanism claim (a fixed
per-instance offset) is right, the per-class numbers for the rolling classes are
not.

## 5. A table or a fit? — a fit cannot carry it

The decisive read is the within-species spread at (nearly) one diameter:

| species | instances (dia mm → offset @0.28) | spread mm |
| --- | --- | --- |
| strawberry | 36.3 → **+20.00**, 37.2 → **-24.30** | **44.3** |
| orange | 63.6 → -26.97, 65.8 → -0.39 | 26.6 |
| kiwi | 53.8 → +53.12, 55.8 → +35.06 | 18.1 |
| tomato | 61.8 → -6.26, 66.1 → +6.71 | 13.0 |
| lychee | 29.6 → -2.90, 34.4 → +4.30 | 7.2 |
| pear | 60.6 → +0.52, 68.1 → +2.58 | 2.1 |
| apple | 65.2 → -0.71, 69.6 → -2.52 | 1.8 |
| peach | 65.1 → +5.42, 68.9 → +6.42 | 1.0 |

A pooled least squares `offset = a + b·dia + c·(x-0.28) + per-species intercept`
over the 48 cells reads residual sd **10.19 mm**, R² **0.744**, max |residual|
**31.0 mm**, `b = +0.70 mm/mm`, `c = -11.2 mm/m` — i.e. a 31 mm worst-case error,
larger than the 20 mm the band has to spare on the low side. **The physical
reason**: the offset is set by the authored mesh's lateral asymmetry
(`build_mesh_points`' `bias_a`/`bias_b`, uniform in `0.94-1.06` per instance, plus
the `bumpy` hull noise), which the seed draws per instance and (species, diameter)
does not determine.

And a **fresh seed is a different instance set**: seed 6's live line reads offsets
`-8.4 .. +34.8 mm`, with one kiwi at `+15.4/+34.8` and one apple at
`+16.6/+22.3`. So the compensation must **measure the pool it is given** — a
per-pool calibration (or a per-pool frozen table), never a shipped
species/diameter table. That is the design constraint the PREREG carries.

## 6. Does the offset depend on the *along* position? (ladder legality)

A ladder calibration (all 16 instances dropped at once at different along
positions) would cost one settle window instead of sixteen, so it is worth
asking. x = 0.28, four instances, four along positions:

| idx | species | off @along 0.68 / 0.50 / 0.32 / 0.14 | spread mm |
| --- | --- | --- | --- |
| 02 | kiwi 55.8 | +35.06 / +35.07 / +35.07 / **+38.37** | 3.31 |
| 05 | strawberry 37.2 | -24.30 / **-35.71** / -22.01 / -22.02 | **13.70** |
| 10 | orange 63.6 | -26.97 / -26.97 / -26.97 / -26.99 | 0.02 |
| 13 | kiwi 53.8 | +53.12 / +52.98 / +53.43 / +52.63 | 0.80 |

The orange is flat to 0.02 mm over 0.54 m and the kiwis to ≤ 3.3 mm, but the
strawberry reaches its `-35.71` mode again at `along = 0.50` — the same value it
reaches at `x = 0.36`. **This is the quantity's honest structure: one or a few
discrete modes per instance, selected by the release geometry.** A ladder
calibration is therefore legal for 14/16 instances and carries a one-mode error on
the rollers; it is a legitimate optimisation, not an equivalence.

## 7. The tail arithmetic

**The model** — integrate the measured per-instance offset over the shipped
`U(0.20, 0.36)` draw (piecewise linear in x). `compensated` = a per-instance table
measured at **one** x (0.28) and applied at every planned x — the realistic
calibration form. `±20 mm` adds the kiwis' measured mode ambiguity as an extra
error on those two instances.

| model | min | p50 | max | < 0.173 | < 0.180 | < 0.200 | > 0.360 | > 0.390 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **uncompensated** (shipped) | 0.173 | 0.284 | 0.400 | 0.00 % | **0.35 %** | 2.44 % | 4.60 % | **0.56 %** |
| compensated (one-x table) | 0.199 | 0.280 | 0.365 | 0.00 % | **0.00 %** | 0.06 % | 0.18 % | **0.00 %** |
| compensated + kiwis' +20 mm | 0.199 | 0.283 | 0.385 | 0.00 % | 0.00 % | 0.05 % | 1.70 % | 0.00 % |
| compensated + kiwis' -20 mm | 0.180 | 0.278 | 0.360 | 0.00 % | 0.00 % | 0.86 % | 0.00 % | 0.00 % |

**The paired read, on the draws the run actually presented** (65 attributed
releases; `compensated` = the release would have been commanded at
`draw - table`, and delivered at `draw + (true - table)`):

| pool | releases | < 0.173 | < 0.180 | < 0.200 | > 0.360 | > 0.390 | min | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s5 **uncompensated** | 65 | 0.00 % | 0.00 % | **1.54 %** | **3.08 %** | 0.00 % | 0.190 | 0.365 |
| s5 wake table, compensated | 65 | 0.00 % | 0.00 % | 0.00 % | 0.00 % | 0.00 % | 0.202 | 0.360 |
| s5 live-mean LOO, compensated | 65 | 0.00 % | 0.00 % | 0.00 % | 1.54 % | 0.00 % | 0.202 | 0.362 |
| s6 uncompensated (fresh pool) | 64 | 0.00 % | 0.00 % | **3.12 %** | 3.12 % | **1.56 %** | 0.195 | 0.392 |
| s6 live-mean LOO, compensated | 64 | 0.00 % | 0.00 % | 0.00 % | 1.56 % | 0.00 % | 0.202 | 0.363 |

**The spawn excursion the compensation asks for**: `planned - offset(0.28)` runs
**0.165 .. 0.387 m** — outside the 0.20-0.36 *spawn* band by 27 mm low / 35 mm
high, still inside the belt (x 0.11-0.57) with ≥ 54 mm to the near edge. The band
the metric is about is the **delivered** one.

**Why the compensation keeps the band even with the mode error**: the delivered x
is `planned + (true - table)`, and with a one-x table the residual is bounded by
the instance's mode spread (≤ 20 mm as measured, §4) against **20 mm of margin on
each side** of `[0.20, 0.36]` inside `[0.18, 0.39]`. Worst case: `0.36 + 0.020 =
0.380 < 0.390`, `0.20 - 0.020 = 0.180`. The table row `+ the kiwis' ±20 mm` above
is that worst case written out.

## 8. The pear pool (the PREREG's second arm)

`FRUIT_SUPPLY_SPECIES=pear` at seed 5 draws **16 pear instances** whose offsets are
**-3.33 .. +2.69 mm**, all x-independent to ≤ 0.02 mm. Uncompensated the pear's
delivered x is the draw itself (`0.197-0.363`): **0.00 %** below 0.180 and
**0.00 %** above 0.390. Compensated: the same.

So **the pear scenario has no release tail to remove**. Its arm in phase 2 is an
**inertness / no-harm control**, not a conversion test — and its predicted result
is that the two arms differ only through the branch the compensation's own spawn
shift creates.

## 9. What this changes in the record

* **P38's per-class drift table is a sample of transit *increments*, not the
  per-instance offset**, for the rolling classes (its own out-of-band rows carry
  the values this probe measures: `+42.0` → `+41.9`, `+69.2` → `+69.3`). The
  mechanism sentence stands unchanged; the per-class numbers for kiwi (and the
  gate that reads "the worst measured instance offset is -35.9 mm", P38 §4.3)
  understate the real range: **the measured per-instance range at seed 77 is
  -52.8 .. +69.3 mm**, and at seed 5 **-35.7 .. +54.6 mm**. P38's floor-raise
  arithmetic (`>= 0.237`) was computed from `-0.057`; from this table the correct
  worst low-side excursion is **-35.7 mm** at seed 5 (`-52.9` at seed 77), so that
  arithmetic keeps its conclusion but for a smaller reason than the
  attempt-loop residual it named.
* **P49's "the drift is P38's per-instance release offset" is confirmed on the
  delivered path**, and the two tail events it could not attribute are the two
  kiwis of the seed-5 pool: E1 (`0.3969`, kiwi 5.6 = idx 02, offsets
  `+35.1 .. +54.6`) and E3 (`0.3908`, kiwi 5.4 = idx 13, `+35.0` in the shipped
  condition) are what those offsets produce from draws at the **top of the spawn
  band** (`0.356-0.357`), which is the shape P49's census needed and could not
  see from a selection read.
* **The two constraints of AGENTS §2 are unaffected**: this phase measures a
  mechanism (a per-instance offset), not a rate, and every number above is a
  deterministic property of a fixed instance set.

## 10. Files, pins, and how to re-check

| artefact | md5 |
| --- | --- |
| `logs/p50/p1/offset_probe.py` | see `logs/p50/MD5.txt` |
| `logs/p50/p1/offset_table.py` | idem |
| `logs/p50/p1/offset_probe_s5.log` (table of record, 2 passes) | idem |
| `logs/p50/p1/offset_probe_s5_wake.log` (wake variant) | idem |
| `logs/p50/p1/offset_live_s5.log` (65 attributed releases) | idem |
| `logs/p50/p1/offset_probe_s77.log` (P38 cross-check) | idem |
| `logs/p50/p1/offset_live_s6.log` (fresh pool) | idem |
| `logs/p50/p1/offset_pear_s5.log` (the pear pool) | idem |
| `logs/p50/p1/offset_along_s5.log` (ladder legality) | idem |
| `logs/p50/p1/offset_table_out.txt` (the full re-derivation) | idem |

Re-check:

```bash
python3 logs/p50/p1/offset_table.py            # -> offset_table_out.txt, ~0.2 s
SEED=5 scripts/154_claim_run.sh logs/p50/p1/offset_probe_s5.log \
    scripts/run.sh logs/p50/p1/offset_probe.py                       # ~2 min
SEED=5 FRUIT_OFFSET_MODE=live scripts/154_claim_run.sh \
    logs/p50/p1/offset_live_s5.log scripts/run.sh logs/p50/p1/offset_probe.py
SEED=5 FRUIT_OFFSET_WAKE=1 FRUIT_OFFSET_PASSES=1 scripts/154_claim_run.sh \
    logs/p50/p1/offset_probe_s5_wake.log scripts/run.sh logs/p50/p1/offset_probe.py
```

## 11. What this does not show

* **No implementation, no rate.** The compensation is phase 2 (`PREREG.md`); the
  tail shares in §7 are an arithmetic prediction from the measured offsets plus a
  paired counterfactual on the measured draws, not a run of the compensated line.
* **The rollers' mode selection is not attributed.** kiwi idx 02 takes `+54.6` and
  `+35.0` at nearly the same x in the live line while the isolated cell repeats to
  0.00 mm. The named candidates — the wake loop's firing tick (it fires only while
  `|v_along| < 0.02 m/s`, so its tick depends on the roll's own phase) and an
  along-contact with a neighbour — are **not separated** here.
* **The geometry read is a correlation, not a predictor.** `bottom_gap`
  correlates with the offset at **-0.62** on 16 instances (and `x_at_zmin` at
  -0.09, `centroid_x` at +0.46) — suggestive of a depenetration kick, far too weak
  to replace the measurement, and never used here as one. A zero-sim predictor
  would need its own pre-registered study (more pools, a force/contact read).
* **The scope is the shipped single-file schedules.** The patch/bed supplies put
  two fruit **abreast** 0.085-0.12 m apart (`fruits.SUPPLY_PATCH_*`), so a
  per-instance lateral shift of up to ±55 mm changes a pair's separation; the
  compensation must be gated off (or pair-guarded) there until that is measured.
* **The `dz_settle` diagnostic is a bound, not a measurement.** The hull's lowest
  authored vertex reads `-1.7 .. -9.4 mm` relative to `belt_top` at rest, which
  mixes a real penetration with the convex-hull approximation and the belt-top
  assumption; it is reported and not interpreted.
* **No force/contact mechanism.** The claim that the mesh's lateral asymmetry
  causes the roll is inferred from the instance structure and the class ordering,
  not measured as a contact sequence.
