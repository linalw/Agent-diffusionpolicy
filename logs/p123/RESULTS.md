# P123 - the third output destination: built, reachable, and its payloads land in its own tray

The owner's item 2 (`logs/p122/SPEC.md` R2): build a **real third output body** - a
third belt + chute + tray - and solve its place point. The answer:

* **it is buildable where P122 said it had to be** - inboard, `|y| 0.280..0.395`, with
  the slab **x-offset downstream** (0.480..1.200) so that no place transit passes over
  it. That x-offset is the design's load-bearing move: it is what makes the third body
  **not a carry obstacle** (the payload, radius included, is at x 0.469 where any
  transit crosses its band) and **not a camera occluder** (it sits downstream of the
  supplied fruit's x band 0.148..0.413). Without it, inboard bodies lose 0.30 mm of
  direct-low-lift clearance per mm (`logs/p90/COST.md` §1) - 44 mm for this band - and
  the split-belt form (candidate B) measures a predicted **contact**.
* **the place solve passes** at the exact cell: `(0.48, -0.30)` reads res **6.0 mm**,
  joint margin **+0.457 rad**, pads **+70 mm** over the new slab, tilt **92.7 deg** at
  the place height and **6.0 mm / +143 mm / 100.5 deg** at the transfer. In the live
  cell the startup solve reports **11.5 mm** against the 25 mm bar - the same scale as
  the shipped lanes' `verified` 14.9 mm.
* **the destination works**: 25/25 payload-present releases across the two treatment
  cells landed on some belt, the ledger reads **`in_destination=25, mis_sorted=0`**, and
  the **tray census agrees on 25/25**: dest 0 -> tray 0 (13), dest 1 -> tray 1 (5),
  **dest 2 -> tray 2 (7)** on the physical trays.
* **the count moved and is not attributed**: seed 5 **17 -> 11**, seed 6 **12 -> 14**
  (pooled **29/40 -> 25/40**, Fisher p = 0.19) - **the sign flips between seeds**, and the
  treatment's extra failures on seed 5 are the tree's closed loaded-slide class **at the
  lift** (`lift=+0.077..0.088`, the P10-C monitor's 8 mm truncation), not at the new
  place point. A 20-attempt count is a branch (P80/P84/P93); the scene is a different
  collider set and a collider set moves the solver ordering (P30-A/P71).
* **the shipped scene is untouched**: the acceptance with the knob unset is **8/10,
  `fingerprint: matches`, `190: PASS`** with its **421 `[fruit]` lines 421/421
  byte-identical** to `logs/p121/accept_final.log`.

Nothing ships: `FRUIT_OUTPUT_LANES` defaults to **2**, which authors no new body.

## 1. The scene survey (the free space)

`logs/p123/survey.txt` - one static session, the stage's own bounds cache, no arm
motion, no attempt loop (`logs/p123/probe.py` section S):

| body | x | y | z |
|---|---|---|---|
| pedestal | -0.300 .. +0.100 | -0.350 .. +0.350 | 0 .. 0.790 |
| main belt (with frame) | +0.085 .. +0.595 | -0.864 .. +0.864 | 0 .. 1.215 |
| `OutputBeltP` (belt+chute+tray) | +0.025 .. +1.950 | +0.380 .. +0.720 | 0 .. 1.365 |
| `OutputBeltN` | +0.025 .. +1.950 | -0.720 .. -0.380 | 0 .. 1.365 |
| its slab | +0.100 .. +1.200 | +-0.425 .. 0.675 | 1.300 .. **1.350** |
| its legs | +0.0255 .. +0.0755 / +1.100 .. +1.150 | at the belt's y edges | 0 .. 1.300 |
| its chute (+ lips) | +1.196 .. +1.388 | +-0.418 .. 0.682 | 1.116 .. 1.365 |
| its tray / stand | +1.350 .. +1.950 | +-0.380 .. 0.720 | 0.900/0.920 .. 1.060 |
| robot at rest | -0.155 .. +0.095 | +-0.238 | 0.790 .. 1.563 |

**The free space at the output deck (z 1.30-1.35)** is `|y| 0.000..0.425` (inboard,
inside the arm's reach) and `|y| > 0.675` (outboard, **outside P90's reach box**). The
only inboard room that is both reachable and clear of the shipped bodies is the band
between the pedestal/slab edge and the -Y slab, i.e. **|y| 0.28-0.40 at x >= 0.48** -
because in `x < 0.48` a new slab would sit under the place transits (section 3).

## 2. The candidates, priced offline before any body was authored

`logs/p123/layout.py` -> `layout.txt`. Four columns per candidate: the place point,
the release (delivered = commanded + the P122 offset), the crossing (each transit's
height at every *other* lane's inboard edge, as a **delta from the shipped crossing**),
and the bodies/camera.

| | place | release (3 sd) | crossing (direct-low dclr) | camera | verdict |
|---|---|---|---|---|---|
| **A** third belt inboard on -Y, x-offset downstream | (0.48,-0.30) in the reach box | on the 0.115 m slab, 48/59 mm margins = 7-8 sd | **none** - the payload is at x 0.469 (radius incl.) when it crosses, 11 mm upstream of the body | 0 cm^2 new occlusion (downstream of the fruit band) | **PASS**, built |
| **B** split the -Y belt into two (full x) | (0.48,-0.35) and (0.38,-0.55), both in the reach box | both 5.7-5.8 sd | **crosses**: lane 2's transit over lane 1's edge is **-9 mm** predicted contact; lane 0's over lane 1 is +2 | both belts stay over the fruit band: 0 cm^2 *new* only because the shipped slab already covers them | **KILL** |
| **C** third belt outboard, \|y\| ~0.70 | (0.43,-0.68) | on its slab | crosses the shipped edge at +115 mm | covers the arrival band | **KILL** - P90 `NAT` is 41-108 mm at \|y\|=0.65, and the new belt overlaps the shipped one |

A also needed the -Y **tray** narrowed (0.34 -> 0.20 m, still centred) so the two trays
have 50 mm of air: a third *target* on an existing belt is the same destination
(`logs/p122/SPEC.md` R2), a third *tray* is one.

## 3. The reach solve (the exact cells)

`logs/p123/probe.txt` / `probe_rows.json` - one static session, P90's `NAT` mode
(`hold_quaternion=None`, the position-only solve the shipped place leg runs), seed
`grasp_lift`, restarts 1, 160 cells (x 0.38-0.48 x |y| 0.30-0.55 x z 1.450/1.530 x 2
arms). Gate (`PREREG.md`): `res <= 6 mm`, `margin >= 0.05 rad`, `pad >= 2 mm` over the
surface actually under the pads, `tilt` 60-110 deg. **93/160 pass**; the inboard band
passes at **x 0.43-0.48** (res 5.6-6.0 mm, pads +49..+56 mm left / +63..+70 mm right
over the new slab, margins 0.42-0.49 rad, tilt 78-105 deg) and **x = 0.38 fails**
(8.2-8.4 mm) - so the band has a hard inboard-x edge, which is why the place x is 0.48
and not further in.

The chosen cell, both heights:

| z | res | margin | pad over the new slab | tilt |
|---|---|---|---|---|
| 1.450 (place height) | **6.0 mm** | +0.457 rad @ j2 | **+70.2 mm** | 92.7 deg |
| 1.530 (the transfer the leg ends at) | **6.0 mm** | +0.569 rad | +143 mm | 100.5 deg |

Live startup solve (`[sort] reach arm=right dest=2 ... residual=11.5mm tol=25mm ->
reachable`): the same cell, the place leg's own call, accepted at the descriptor's
`place_tolerance_mm: 25` - the shipped lanes' `verified` residual is 14.9 mm.

## 4. The build (default off)

`FRUIT_OUTPUT_LANES=3` (default 2 = **no body authored**). One table,
`SceneConfig.output_lane_layout()`, feeds the builder (`conveyor.OutputBelt` takes a
lane), the scene (`scene._add_output_belts` iterates it), the belt/tray/discharge
tests, the arms' drop points and the store manifest - so a lane cannot be half-added.
With 3 lanes the -Y side gets:

* belt `x 0.480..1.200`, `|y| 0.280..0.395`, top 1.350 (same plate, speed 0.12 m/s,
  friction, `PhysxSurfaceVelocityAPI`, discharge as the other two);
* its own chute (0.10 m wide) and its **own tray** (`0.60 x 0.14 m`, x 1.35..1.95,
  `|y| 0.260..0.400`, floor 0.92, rim 1.06);
* the shipped -Y tray narrows to 0.20 m;
* 30 mm of air to the -Y belt, 50 mm to its tray, 16 mm between the chutes.

`logs/p123/manifest_scene_{two,three}_lane.json`: `scene.output_lanes` has 2 entries
shipped and 3 with the body, and the only difference in the first two entries is the
-Y tray width (0.34 -> 0.20). `assets.scene_provenance` is the one builder both manifest
writers call (the P41/P72 rule, pinned by `239`).

The destination is a P114 descriptor entry (`logs/p123/three_dest.json`, id 2,
`reach: auto`) and the capability map keeps its physical meaning: destination 2 is
`-y`, so the **right** arm serves it (`left=[0] right=[1, 2]`).

## 5. The cell

20 attempts, the shipped scripted two-line, seeds 5 and 6, P92's four instruments in
every arm (`FRUIT_MOTION_REPORT FRUIT_CYCLE_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`),
one claim per run. Instruction (`logs/p123/three_dest.txt`):
`grade=A => 0`, `grade=B and size<66 => 2`, `grade=B => 1`, `grade=C => skip` - so
**every destination gets traffic on the shipped 8A/5B/3C pool** (`[sort] coverage:
pool=16 mapped=12 unassigned=0 skip=4 (dest0=6, dest1=2, dest2=4)`), and the split is
linted first (`scripts/262_sort_plan.py`: 120 cells, dest0 40 / dest1 11 / dest2 29 /
skip 40, one ordered overlap that rule 2 wins).

| cell | scene | placed | s/attempt | ledger released / in_dest / mis | tray census |
|---|---|---|---|---|---|
| C5 | shipped 2 lanes | 17/20 | 9.1 | - | - |
| **T5** | **3 lanes + instruction** | **11/20** | 9.6 | **11 / 11 / 0** | dest0->tray0 x4, dest1->tray1 x5, **dest2->tray2 x2** |
| C6 | shipped 2 lanes | 12/20 | 9.1 | - | - |
| **T6** | 3 lanes + instruction | **14/20** | 9.2 | **14 / 14 / 0** | dest0->tray0 x9, **dest2->tray2 x5** |
| pooled | | **29/40 -> 25/40** (p = 0.19) | | **25 / 25 / 0** | **25 joins, 25 agree** |

Per destination: T5 dest 0 attempts 9 / placed 4, dest 1 7 / 5, **dest 2 4 / 2**; T6
dest 0 10 / 9, **dest 2 10 / 5** (T6's pool drew no B fruit above 66 mm, so its
`coverage` row reads `dest0=6, dest2=6` and destination 1 gets that seed's zero - the
rule, not the lane, decides). The settled-position read (`place trace ... final=`) names
the same belts: T5 lane 0 4 / lane 1 5 / **lane 2 2**; T6 lane 0 9 / **lane 2 5**. The
tray census joins each `[sort] attempt idx=N dest=D` to the `[belt] ... (index N)
discharged to the tray ... [tray T]` row: **25 joins across both cells, 25 agree, 0
mismatched**, and **7 payloads physically ended in tray 2** over the two treatment
cells. The ledger's `nearest` read and the tray agree because the two -Y destinations
are 0.2 m apart (`dist=29-32mm` to dest 2, ~0.22 m to dest 1), well outside the P122
offset's spread.

**The count is a coin flip, not a cost**: seed 5 reads -6, seed 6 reads +2, and the
pooled 29/40 -> 25/40 is Fisher **p = 0.19** (per seed 0.06 and 0.33). The scene *is* a
different collider set - a new kinematic slab, chute and tray - and a collider set moves
the solver ordering (P30-A/P71), which is why the same-tree control can swing this much
between seeds (P93's four controls read 16/12/15/15). Nothing about throughput is
claimed.

**The new lane's failures are not at the new place point.** Of its 4 attempts, 2 were
truncated at the **lift** (`grasped=1 placed=0`, `lift=+0.088 / +0.077 m`,
`clean_slip_max >= 8 mm` -> the P10-C monitor ends the lift and the attempt), i.e. the
closed loaded-slide class (`logs/p42/SIM_LIMIT.md`), and the 2 that reached the place
leg **both landed in tray 2**, at `(0.50,-0.32)` and `(0.51,-0.31)`.

**A measured correction to the release offset**: on the shipped lanes T5's releases
read `(+50..60, +-30) mm` from the commanded point (P122's `+48, +-35..37`), but on the
new lane they read **`(+20..30, -10..-20) mm`** - because the offset is
`0.070 x tool_axis` and the new pose's attitude differs (tilt 90 deg vs 78 deg at the
shipped place). The slab was sized on the *shipped* (larger) offset, so the delivered
point still sits 20-30 mm inside its upstream edge - but that is **2.5-4 sd, not 8**,
and it is the one number a future form should widen (move the belt's upstream end to
x = 0.46, or verify on more releases; n = 2 here).

## 6. The guards

| guard | C5 (shipped) | T5 (3 lanes) |
|---|---|---|
| payload-present releases on a belt | 17/17, 12/12 | **11/11, 14/14** |
| descent budgets (`105 --min-success-rate 0`) | PASS, 20 legs | **PASS, 20 legs** (not re-tuned) |
| arm-to-body clearance, held place legs | `clr` min +57 / +73 mm | **`clr` min +76 / +69 mm, `clr_edge` min +75 / +70 mm** |
| new failure-reason key | - | **none** (`fruit did not follow the gripper` only, in both) |
| loaded-slide census (`force_min == 0` legs) | 3 / 37 and 6 / 44 carry legs | 9 / 31 and 5 / 44 |
| crush proxy `sep@loss - dia` on held-loss legs | **-28.4 mm** | **-20.4 mm** |

The clearance floor is the phase's own gate and it passes with 75-76 mm of air on
every held place leg - the new body is *never* the binding surface, which is what the
x-offset was for. The crush proxy **fails its -15 mm letter in both arms** (the
control too): `sep@loss` on these legs is the pads closing past the fruit *after* the
payload has left (the servo's chase), which is P76's A1/A3 caveat and P100's A4
precedent - recorded, not re-read, and not attributable to this phase.

## 7. No-harm

* `scripts/accept.sh` (knob unset): **8/10, `fingerprint: matches
  configs/motion_reference.json`, `190: PASS`**, and its **421 `[fruit]` lines are
  421/421 byte-identical** to `logs/p121/accept_final.log` (`logs/p123/accept_noharm.log`).
* `scripts/selfcheck.sh` PASS (the new `P123 output lanes` leg, 34 checks); `106` OK;
  `107` PASS (21 checks).
* The two-lane scene manifests carry 2 lanes; `FRUIT_OUTPUT_LANES` unset authors no
  body, no new print, no new `stats` key and no `[tray N]` suffix.

**Recorded deviation** (PREREG §3, second bullet): the clause "C5 replays
`logs/p92/C5.log`" is not achievable - that record is 31 phases old and predates
P100's park profile, P102's tactile and P115's `rule=` field, so the *stream* cannot be
identical by construction. The substitute is stronger and same-scenario: the acceptance
(10 attempts, the same two-line cell) is byte-identical to the immediately-preceding
phase's record, which fixes the loop's first ten attempts; the remaining ten follow
deterministically from them.

## 8. What is not claimed, and what an adoption owes

No throughput claim: the sign flips between the two seeds (-6 / +2, pooled p = 0.19)
and the extra failures on seed 5 are the closed grip class, not the new lane. What *is* claimed is geometric and mechanical: the body exists, its place
point is reachable, its payloads land in its own tray, the shipped scene does not move
and no held place leg comes within 75 mm of it.

An adoption (default 3 lanes) is the owner's call and owes: both motion references
re-recorded from same-batch runs, the acceptance and the two-line gate re-based, every
store re-baselined (a 3-lane store is a different collider set - its manifest says so),
and the direct/policy interface measured (it shares `SceneConfig`, so it would read
the 3-lane `on_output_belt`/`on_output_tray` too).

## 9. Files and pins

`logs/p123/`: `METHOD.md`, `PREREG.md` (+`.md5`), this file, `layout.py`/`layout.txt`,
`probe.py`/`probe.log`/`probe.txt`/`probe_rows.json`, `survey.txt`,
`three_dest.json`, `three_dest.txt`, `one_run.sh`, `run_p123.sh`, `chain.sh`,
`p123_report.py`/`p123_report.txt`, `manifest_scene_{two,three}_lane.json`, the cells
`{C5,T5,C6,T6}.{log,stamps,driver}`.
`src/`: `assets.py` (the lane table, the generalised tests, `output_tray_of`,
`scene_provenance.output_lanes`), `conveyor.py` (`OutputBelt` takes a lane),
`scene.py` (the lane loop), `tasks.py` (`_payload_clearance` walks the lanes signed and
x-gated; `_output_belt_edge_y` per side), `fruits.py` (the tray census, 3-lane only).
`scripts/`: `264_p123_output_lanes_selftest.py` (new leg), `selfcheck.sh`, the re-pins
in `238`/`239`. `configs/` untouched (`motion_reference.json` =
`..._twoline.json` = `30fb99f8`, `..._single.json` = `8952c320`).
