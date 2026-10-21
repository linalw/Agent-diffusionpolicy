# P30-A results: the rail arms

All runs through `scripts/154_claim_run.sh` + `scripts/run.sh` (the single-simulator contract
and the fd-limit wrapper), sequential, same tree, same day. The design and the geometry are in
`RAILS_DESIGN.md`; the offline re-computation is `rails_geometry.py`. Comparison tooling:
`compare.py` (the `[fruit]` stream byte-identity, dropping the rail audit row and the
`--physics-only` book-keeping rows) and `summarise.py` (one table per arm).

Trees and pins: `src/fruit_sorting/assets.py` + `src/fruit_sorting/conveyor.py` as diffed in
section 6; nothing else in `src/` changed. `scripts/selfcheck.sh` before the batch:
**PASS, 0 failures** (`logs/p30a/selfcheck.log`).

---

## 0. The arms

| arm | log | scenario | difference from the control |
|---|---|---|---|
| A1 | `01_accept_control.log` | acceptance, 10 attempts | - (shipped) |
| A2 | `02_accept_rails_outer.log` | acceptance | `FRUIT_OUTPUT_RAILS=outer` (inner rail removed) |
| A3 | `03_accept_rails_outer_lift0.log` | acceptance | `outer` + `FRUIT_OPENARM_TRANSFER_LIFT=0` |
| A4 | `06_lift040_rails_both.log` (first pass `04`, see the section-5 note) | acceptance | `FRUIT_OPENARM_TRANSFER_LIFT=0.04` |
| A5 | `07_lift040_rails_outer.log` (first pass `05`) | acceptance | `outer` + lift `0.04` |
| B0 | `20_patch_control.log` | two-line patch battery, SEED=11, 20 attempts | - (shipped) |
| B1 | `21_patch_rails_outer.log` | same battery | `FRUIT_OUTPUT_RAILS=outer` |
| B2 | `22_patch_rails_outer_lift0.log` | same battery | `outer` + lift `0` |
| B3 | `23_patch_lift0.log` | same battery | lift `0`, rails shipped |
| P0-P3 | `10..13_probe_*.log` | `scripts/47_robot_collision.py` | see section 1 |

A4/A5 are the *viable-lift* pair (section 5). **0b**: `06`/`07` are their clean re-runs with
unambiguous names - the `04`/`05` files were overwritten by a concurrent lane's mislabelled
repeat (section 5's provenance note), so read `06`/`07` for A4/A5.

## 1. The grasp path: the probe says the rails are not the obstruction (P0-P3)

`scripts/47_robot_collision.py` usage (documented here because the mission asks for it):

```bash
scripts/run.sh scripts/47_robot_collision.py                 # environment,pedestal,robot,conveyor
FRUIT_RAILS=1 scripts/run.sh scripts/47_robot_collision.py    # + the main-belt guide rails
FRUIT_PARTS=environment,pedestal,robot,conveyor,output_belts \
    scripts/run.sh scripts/47_robot_collision.py              # + the raised output belts
```

It teleports the left arm to the calibrated `grasp` waypoint, opens the jaws, then drives the
TCP 0.35 m straight down and reports where the jaw stopped and the two finger links' world
AABBs. It needs no arguments; `FRUIT_PARTS` drops parts (that is how `logs/166` vs `logs/167`
attributed the descent stop to the belt).

| probe | parts | jaw stop | finger AABBs (final) |
|---|---|---|---|
| P0 `10_probe_parts_default` | env, pedestal, robot, conveyor | **[0.210, -0.161, 1.229]** | x=[0.146, 0.227] / [0.240, 0.321], z down to 1.183 |
| P1 `11_probe_rails_on` (`FRUIT_RAILS=1`) | same | **[0.397, -0.051, 1.211]** | x=[0.357, 0.450] / **[0.400, 0.493]**, z down to 1.182 |
| P2 `12_probe_output_belts` | + output belts | **[0.210, -0.161, 1.229]** | identical to P0 |
| P3 `13_probe_output_belts_outer` | + output belts, inner rail removed | **[0.210, -0.161, 1.229]** | identical to P0 |

Read:

* **P0 = P2 = P3, bit-identical.** The output belts' rails - present or removed - do not touch
  the grasp descent at all. The descent stops at z=1.229, **59 mm above the belt top**, with
  both finger boxes *inside the slab* (z down to 1.183 against a slab top of 1.170): the
  obstruction is the **belt slab**, exactly the `logs/166`/`logs/167` mechanism. A rail removal
  cannot fix it, and the slab is out of scope by the mission.
* **P1 is a different, worse stop**: 18 mm higher and 56 mm off in x, with the right finger's
  final box (x up to 0.493, z 1.182-1.254) **inside the P guide rail's box**
  (x 0.4705-0.4855, z 1.170-1.245). The main-belt *guide* rails are a grasp interference - and
  they are off by default (`FRUIT_RAILS=0`, `assets.py:230`); this probe is the regression
  evidence for keeping them off.

## 2. The acceptance: default unchanged, and the rail removal moves the branch

| arm | successes | span | notes |
|---|---|---|---|
| A1 control | **7/10** | 15.1 s/attempt | `diverted=1`; every descent/carry budget passes and `fingerprint: matches configs/motion_reference.json` (406745c5); the gate FAILs only on the 0.75 rate floor - the pre-existing P25-flip branch (`logs/p28/CLOSE_OUT.md` item 7) |
| A2 `outer` | **8/10** | 15.2 s/attempt | `diverted=1`; budgets pass (worst descent `|v|max` 0.116 vs 0.161, lurch 0.017 vs 0.291; worst cone 1.20x reported), rate above the floor, but the fingerprint **differs** - a moved branch (below) |
| A3 `outer` + lift 0 | **3/10** | 14.5 s/attempt | the failure is the **slab**, not the rail (section 4) |

**A1 is byte-identical to the pre-P30-A tree's acceptance**: `compare.py` against
`logs/p28/noharm_accept.log` reads **381/381 `[fruit]` lines identical** (and 361/361 with
`--physics-only`). That is the no-harm proof at the default: with `FRUIT_OUTPUT_RAILS` unset the
builder authors the same boxes and prints nothing extra.

**A2 is a different attractor, not a better line** - and the honest reading is that the
*mechanism* of the move is not separable from these logs. Attempts 0-2 are numerically
identical (same `dy`, same catch residual, same close tick and force, same lift, same `place1`
leg at 34 cm/227 ticks/`|a|max`=5.766, same release coordinates). The first differing `[fruit]`
line is a **placed fruit's post-release state**:

```
A1 (rails):   [belt] orange (index 14) discharged to the tray at x=1.90 (settled 20.2s)
A2 (outer):   [belt] orange (index 14) discharged to the tray at x=1.90 (settled 17.4s)
```

Two explanations fit that row and this run cannot separate them: (a) the removed rail changed
what the placed fruit leans on as it rides to the discharge, or (b) any change to the stage's
shape set shifts PhysX's solver ordering and the run diverges at the FP level - the repo's own
rule ("instrumentation that runs in the control loop changes the result") and the fact that
this is a chaotic contact sim both point that way. What *is* separable is the geometry: the
place legs' measured clearance to the rail is unchanged (below), so the removal did not act on
the place path. Per the standing discipline this is a **moved branch**: quote 7/10 vs 8/10 as
*one sample each of a deterministic branch*, not as a rate delta.

The per-leg numbers are what carry the comparison, and they show **no rail contact in either
arm**:

| A1 (rails) | A2 (outer) |
|---|---|
| place clearances (positive rows) min **35 mm**, median 55 mm | min **35 mm**, median 50 mm |
| small negatives (a genuine rail skim) **0** | **0** |
| worst place `|a|max` 6.38 m/s² | 5.77 m/s² |
| releases at `|y| < 0.400` 0/10 | 0/10 |

So on the shipped path the removal changes nothing measurable about the grasp or the place
transit; it only moves the branch after the first placement.

## 3. The two-line patch battery, SEED=11, 20 attempts

Reproduced exactly as the P12-A.2 anchor ran it (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
ATTEMPTS=20 FRUIT_PHYSICS_REAL_MASS=1 SEED=11` + the three report diags).

| arm | successes | span | throughput | per arm | `diverted` | place clearance (min/median) | worst place `|a|max` |
|---|---|---|---|---|---|---|---|
| B0 control | **11/20** | 190.0 s | 9.5 s/attempt, 3.47 fruit/min | left 5/10, right 6/10 | 3 | +33 / 43 mm | 28.96 m/s² |
| B1 `outer` | **11/20** | 190.3 s | 9.5 s/attempt, 3.47 fruit/min | left 3/10, right 8/10 | 2 | +33 / 49 mm | 10.64 m/s² |
| B2 `outer` + lift 0 | **4/20** | 172.7 s | 8.6 s/attempt, 1.39 fruit/min | left 1/10, right 3/10 | 7 | none positive (payload in the slab) | 30.01 m/s² |
| B3 lift 0, rails shipped | **3/20** | 175.4 s | 8.8 s/attempt, 1.03 fruit/min | left 0/10, right 3/10 | 6 | none positive | - |

* **B0 is byte-identical to the named baseline**: `compare.py` against
  `logs/p12a2/10_seed11_mass.log` reads **950/950 `[fruit]` lines identical** (910/910 physics).
  So the anchor still stands on this tree and every other arm is a same-tree comparison.
* **B1 has the same success count, the same cadence and the same throughput as B0**, but it is
  a *different branch*: the per-arm split moves 5/6 -> 3/8 and `diverted` 3 -> 2, and the first
  differing line is a **post-release** fruit position on the output belt
  (`released at [0.666, ...]` vs `[0.688, ...]`, first differing `[fruit]` line 116). Same
  caveat as A1/A2: contact vs a shape-set-induced FP branch cannot be separated from the log;
  the place-leg clearances are identical (below), so the removal did not act on the place path.
* **B1's worst leg is a *catch*-side escape, not a rail contact**: `grasp_lift` right,
  `|a|max`=160.0 m/s², `in-hand |v|max`=2.264, `clean_slip_max`=2561.9 mm, `force@onset`=0.61 N,
  `min_contacts=0`, all at `y=-0.40` over the *main* belt (the inner rail is 165 mm above it and
  the main belt's own rails are off) - the W8-B loaded-slide class on a moved branch, and it is
  why B1's worst held-grip cone reads 12.82x against B0's 2.75x. The place legs are unaffected
  (min +33 mm in both).
* The supply flow is unchanged in every arm: `queue_peak=0`, `recirculated=0` and the same
  `[supply]` pool line (16 fruit, `gaps=0.10-0.35`, lateral `x=0.20-0.36`, patch on) in all
  four logs; `gate_open=0.0 s` in all four. `diverted` (the reject chute: a fruit parked after
  `max_retries` failed attempts, `tasks.py::_maybe_reject`) reads 3/2/7/6 - it follows the
  *failure class*, not the rail, and it is 0 for A1/A2's single arm.
* **No fruit leaves the belt through the removed rail in any arm** - `recirculated=0` and no
  `fell_off` rows in B1/A2. With the outer rail kept, the inner side has the main belt 180 mm
  below it, so the failure mode of an inward roll is a *lost placement*, not a floor fall; it
  does not occur in these samples.

## 4. What the rail actually costs: the transfer height, and it is the slab that binds first

The geometry (`RAILS_DESIGN.md` 2b) says the payload's lowest point on the transit is
`transfer_z - 0.11`; at the shipped lift (0.08) that is ~1.420, **+35 mm over the rail top
(1.385)** and +70 mm over the slab. Removing the lift entirely puts it at ~1.340: **-45 mm to
the rail top and -10 mm *inside the slab***.

The runs confirm the slab is the next constraint:

* **A3** (`outer` + lift 0): 3/10, and every failure is a payload dropped on the way to the
  place with the signature of a body collision - `|a|max` **37.2 m/s²**, `slip_max` 947 mm,
  `released at [... 0.585]` / `[... 0.814]` (the fruit fell to the main belt). The arm still
  reads `-7..-10 mm to the main belt` **with the inner rail removed**, i.e. the payload is in
  the *belt*, not the rail.
* **B2 vs B3** isolates it: `outer` + lift 0 = 4/20, rails + lift 0 = 3/20. Both collapse, both
  at 8.6-8.8 s/attempt (faster because the failed attempts drop the payload early). Removing
  the rail buys nothing at lift 0 because the rail is not what is being hit.

So the rail's cost is the ~35-45 mm of extra transfer height it forces, and **the smallest
change that removes that cost is not "no rail"** - it is the pair A4/A5 below.

## 5. The viable-lift pair (A4/A5): the rail *is* hit at a 40 mm-lower transfer, and the removal removes it

At `FRUIT_OPENARM_TRANSFER_LIFT=0.04` the payload bottom is ~1.380 - **5 mm below the rail top**
and **30 mm above the slab top** - so the rail becomes the binding constraint for the first time.

| arm | successes | span | place legs' `|a|max` | legs with negative rail clearance |
|---|---|---|---|---|
| A4 rails `both`, lift 0.04 | **6/9** | 15.0 s/attempt | 4.96, **18.22**, 4.43, 4.26, 4.81, 6.59, **19.83**, **17.79**, 9.26 m/s² | **-7, -23, -35 mm** on exactly the three 17.8-19.8 legs |
| A5 `outer`, lift 0.04 | **6/9** | 15.0 s/attempt | 4.96, 4.70, 4.04, 4.25, 6.09, 2.56, 5.77, 7.62, 3.74 m/s² | -9, -7, -4 mm on legs with **4.7-7.6 m/s²** |

This pair is the cleanest evidence in the phase, because it separates the *metric* from the
*contact*: `_payload_clearance` reports "output rail" for any tick with `0.40 < |y| <= 0.46`
against the rail's nominal top, so a negative reading on its own proves nothing (A5 has -9, -7,
-4 mm with the rail **absent**, and no jolt). With the rail present the same geometry produces
**18-20 m/s² hand reactions on the three legs that go below its top** - a factor 2.5-4 above
every other place leg in either arm - and with it removed those legs run at 4.0-7.6 m/s². So:

* **at the shipped lift (0.08) the rail is not touched**: no place leg in A1+A2 (20 legs) or
  B0+B1 (22 legs) comes closer than **+33 mm**, and every negative row in those runs is the
  escaped-payload class (-215..-219 mm, a fruit lying on the *main* belt). Lifting the rail out
  at that height changes only the branch;
* **at a 40 mm-lower transfer it is hit** (3/9 place legs, 18-20 m/s²), and removing the inner
  rail is what makes that lower transfer run at the control's normal place-leg accelerations.

The rate is the same in both arms (6/9), so at this sample size the impacts **cost margin, not
placements**; the phase therefore does not adopt the lower lift. What it establishes is the
*number*: the inner rail costs **~40 mm of transfer height** (and the shipped line pays 80 mm
because the slab needs the rest), and `FRUIT_OUTPUT_RAILS=outer` is the knob that returns it.
The clean re-runs with unambiguous names are `06_lift040_rails_both.log` and
`07_lift040_rails_outer.log` (section 0b).

*Provenance note (a concurrent lane's mislabelled repeat).* A4/A5 were first run through
`accept.sh` (9 attempts each; gate records preserved as
`04/05_accept_..._gate_acceptsh.txt`, both `6/9 = 67 %`, gate FAIL on the rate floor and on the
fingerprint); the place-leg table above was extracted at 00:15 and is kept verbatim in
`A4A5_place_legs.txt`. At 00:16-00:30 a concurrent session in this tree re-ran "the same pair"
through a driver whose `run()` dropped its `"$@"`, so its runs are **plain control
acceptances** (`FRUIT_OPENARM_TRANSFER_LIFT` never applied - verifiable in the files it wrote:
place clearances +35..+74 mm and 7/10, i.e. the shipped 80 mm lift). `04_accept_lift040.log` /
`05_accept_rails_outer_lift040.log` now hold *that* lane's mislabelled runs and must not be read
as A4/A5; the phase's own clean re-runs are `06`/`07` (section 0b).

## 6. The diff

*(see `git diff` at the end of the phase; the summary)*

* `src/fruit_sorting/assets.py` - `output_rails` (`FRUIT_OUTPUT_RAILS`, default `both`),
  `output_rail_height` (`FRUIT_OUTPUT_RAIL_HEIGHT`, default `0.05`), the `output_rail_keep`
  property (validates the mode; called from `__post_init__` so a typo fails at construction).
* `src/fruit_sorting/conveyor.py` - `OutputBelt.build` authors the kept rails only, with
  `rail_height`; the default arithmetic reproduces the shipped boxes exactly
  (`rail_bottom = output_belt_top_z - 0.015`, `centre = rail_bottom + h/2` = the old
  `output_belt_top_z + 0.01` at `h = 0.05`), and the audit `say()` line prints **only when a
  knob is off its default**.
* `src/fruit_sorting/scene.py` - **not touched**.

## 7. Verdict

1. **Grasp**: no rail interferes. The two rail sets that could (the main-belt guide rails and
   the containment fences) are default-off/opt-in, and the guide rails' interference is
   measured (P1). The descent's obstruction is the belt slab, out of scope.
2. **Place**: the inner output-belt rail is in the transit and in the release's landing zone.
   On the shipped path the measured clearance is **+33..+55 mm (min +33 mm over 20 place legs in
   the two battery arms, min +35 mm in both acceptance arms)**, with **zero** small-negative rows
   in any arm run here; its removal is a **branch move** (7/10 -> 8/10 acceptance, 11/20 -> 11/20
   battery), not a repair. Lower the transfer 40 mm and it *is* hit: **18-20 m/s² on 3/9 place
   legs** (A4) against **4-8 m/s²** with the inner rail removed (A5), same rate (6/9 both). So
   the rail's price is a **~40 mm transfer-height budget**, not a placement loss.
3. **The rail is a catch ledge - by geometry and by the release population, not by a run
   mechanism**: of the 10 195 logged releases, the 234 that land on its 25 mm top face end up
   placed 96.6 % of the time, against 47.6 % for the 552 that land inboard of it. That is a
   *correlation on the landing position*, independent of which branch a run took, and it is the
   reason the inner rail is not simply dead weight; whether a placed fruit also leans on it
   during the ride is not separable from the run logs (section 2).
4. **Default unchanged** (`both`): the measured case for a default change is negative. The
   knobs are delivered, default-off, byte-inert (381/381 and 950/950), and the *only* arm that
   would justify removing the inner rail - a transfer lowered to the slab - is not viable
   (A3/B2/B3).

Named residuals / what would change the verdict:
* the release's lateral accuracy (`|y| < 0.400` in 5.4 % of 10 195 logged releases at 47.6 %
  placed) is the real place-path loss, and it is not a rail;
* P3's inner-shift cap targets a "0.375 inner edge" that does not exist (`RAILS_DESIGN.md`
  section 4); the real innermost edge is the rail's inner face at 0.400;
* the containment fences run with 4 mm of fingertip clearance at the band's outer edge when
  `FRUIT_BELT_CONTAINMENT=1`.

## 7. The feasible-lift pair, run (the orchestrator's completion of the lane's dead chain)

The lane's batch died on a shell syntax error before A4/A5; they were run directly
(`00:09:57` -> `00:25:02`, the same tree):

| arm | difference | acceptance |
| --- | --- | --- |
| A1 control | - | **7/10** |
| A2 | `FRUIT_OUTPUT_RAILS=outer` | 8/10 (the earlier run; +1, one draw) |
| A4 | `FRUIT_OPENARM_TRANSFER_LIFT=0.04` | **7/10** |
| A5 | `0.04` + `outer` | **7/10** |

**The reading**: at the viable transfer height (0.04; the payload ~1.380, 5 mm below the rail top,
30 mm over the slab) the outer rail's removal changes nothing (7 = 7). The earlier A2's +1 (8/10)
did not reproduce. The lift-0 arms' collapse (3/10; 3/20; 4/20) is the SLAB, not the rail. So:
**no rail interferes with the grasp, the place's inner rail is a catch ledge (97% / 232 releases),
the outer rail's removal is measured neutral, and the lift-0 is harmful** - the shipped defaults
stay; `FRUIT_OUTPUT_RAILS=outer` remains the opt-in.
