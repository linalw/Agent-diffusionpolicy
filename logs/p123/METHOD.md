# P123 - method: how a third output destination is designed, solved, built and read

P122 (`logs/p122/SPEC.md`) fixed the object: a destination is a **physical output
body** - a belt + chute + tray - the cell has two, and a *target* on an existing belt is
the same destination. The binding term for a third is the **place reach** (P90's `NAT`
solve converges only in x 0.38-0.48, |y| 0.35-0.55). The owner chose item 2: build the
body and solve its place point. The owner's constraint holds - the dynamic scattered
pick line is not stopped, diverted, gated or paused, and a belt **downstream** adds no
such element.

This file is the method, in the order it was executed. The registration of the *cell's*
endpoints is `PREREG.md` (md5 `07ae3c90`), pinned before the first cell.

## 1. Survey before design (static, `probe.py` section S -> `survey.txt`)

Build the shipped bodies (`environment`, `pedestal`, `robot`, `conveyor`,
`output_belts`) in one static session, **no arm motion, no attempt loop**, and print
every body's **world AABB from the stage's own bounds cache**
(`UsdGeom.BBoxCache.ComputeWorldBound`), not from config arithmetic. The output deck's
free space is then a read, not an assumption: `|y| 0.000..0.425` inboard (inside the
reach) and `|y| > 0.675` outboard (outside P90's box). Material prims and unbounded
Xforms are dropped from the evidence file (they carry no geometry).

**Why the AABB and not the config**: the walls, chute lips, tray stands and pulley
crowns are authored *derived* geometry (`conveyor.OutputBelt._build_discharge`,
`CleatedBelt.build`); the config's scalars do not name them, and a candidate clears the
scalars while clipping a lip (P69's `+7 mm` floor was measured on the built boxes).

## 2. Candidates priced offline before any body is authored (`layout.py`)

The brief's three, in its order, each with four columns:

1. **the place point** against P90's `NAT` <= 6 mm set (the 50 mm grid), stated as a
   pre-check only - the exact cell is solved in section 3;
2. **the release**: `delivered = commanded + offset` with `logs/p122/SPEC.md`'s measured
   `(+48 mm x, +-35..37 mm y)` and its sd, tested against the candidate slab in **sd**,
   and against the slab's **upstream edge** (the x term decides whether a payload falls
   180 mm onto the main belt);
3. **the crossing**: for every lane's transit, the height at every *other* lane's
   inboard edge, as a **delta from the shipped crossing** (`d clr = d z`, P90
   `COST.md`), including the **payload's own `+48 mm` downstream offset and its radius**
   - a body is crossed only if the payload is over its x span at that moment;
4. **the bodies and the camera**: belt/tray/chute AABB air between distinct lanes, the
   pedestal and the main belt; and whether the new body covers the fruit's arrival
   footprint **outside** the shipped slabs' own footprint (an occlusion the line does
   not already have - the P35/P36 lever).

**Kill rules (pinned)**: a candidate whose place point is outside the reach box, whose
transit clips another lane's body, whose bodies interpenetrate (a tray may not be
shared - that is P122's R0), or which adds supply occlusion, is killed **before** the
build. Results: A passes, B kills on the transit (-9 mm predicted direct-low `clr`), C
kills on the reach (41-108 mm at |y| 0.65) and on body overlap.

## 3. The exact reach solve (`probe.py` section R -> `probe.txt`)

P90's machinery, unchanged: `ArmController.solve_to` with `hold_quaternion = None` (the
position-only solve the shipped place leg actually runs), seeded from the `grasp_lift`
waypoint, at the two heights the place leg uses (1.450 = `output_place_z`, 1.530 = the
transfer the leg ends at for the rigid-tool hand). Per cell: residual, joint margin, the
achieved tilt, and the **pad clearance over the surface actually under the pad** - the
new slab where the cell sits on it, not the main belt (P90's switch charges the main
belt for |y| < 0.40, which is exactly the band a third inboard lane occupies).

Gate (`PREREG.md` section 1): `res <= 6 mm`, `margin >= 0.05 rad`, `pad >= 2 mm`,
`tilt` 60-110 deg (the shipped place leg's own measured class, P73's `tilt_end`
78.7-105 deg - P90's stricter `tilt <= 5 deg` belongs to the *top-down* question it
closed, not to this one).

**Two operational facts this cost, recorded so the next reader does not repeat them**:
`restarts > 1` makes a failed cell re-solve from a **random** pose, which can wedge a
link inside a kinematic slab and grind the physics for minutes (the first run was
killed at 4+ min on one cell); and **park an arm before the next one solves** (a solved
place pose leaves a link in contact, and the second arm's solve on top of that wedges
the same way - the fix is one `teleport_joints` to the `ready` waypoint between arms).

## 4. The build (default off, one table)

`FRUIT_OUTPUT_LANES=3`; default 2 authors no body, no print, no `stats` key and no
`[tray N]` suffix. One table, `SceneConfig.output_lane_layout()`, feeds the builder
(`conveyor.OutputBelt` takes a lane dict), the scene, the belt/tray/discharge tests, the
arms' drop points and `assets.scene_provenance`, so a lane cannot be half-added. With
two lanes every entry resolves to the shipped scalar **exactly** - that is the property
the `264` leg executes against the pre-P123 expressions on a dense grid.

The third body must carry everything the others do: its own slab as a **kinematic rigid
body** with `PhysxSurfaceVelocityAPI` (a static collider does not carry - `logs/171`),
its own chute with lips, its **own tray** and stand, and its own prim root
(`/World/OutputBelt2`). The shipped -Y tray narrows because two trays may not overlap
and a shared tray is not a destination.

`tasks._payload_clearance` walks the lane list **signed and x-gated**: a lane charges a
sample only when the sample is over *that lane's x span* and on *that lane's side*. Both
terms are load-bearing - unsigned, a +Y transit would be charged the -Y lane's plane;
ungated, the payload crossing a new lane's |y| band **upstream of its x span** would be
charged a plane that is not under it (the design deliberately puts it there).

## 5. The cell

20 attempts, the shipped scripted two-line, two seeds, **same-seed controls on the same
tree**, one claim per run, P92's four instruments in every arm. The instruction is
linted first (`scripts/262_sort_plan.py`: rule table with arms, overlaps with the
winning rule, the partition over the 120-cell attribute space) so that every destination
is reachable by the rule before the run.

**The endpoints, in this read order** (`p123_report.py`):

1. **the tray census** - which *physical* tray each payload ended in: join each
   `[sort] attempt idx=N dest=D` to the `[belt] ... (index N) discharged to the tray ...
   [tray T]` row the spawner prints when the fruit settles (P123 adds `[tray T]` only
   when a third lane exists). The `final=` position of the place trace names the belt
   independently;
2. **the ledger** - `in_destination / released / mis_sorted`, per destination;
3. **the placed count** - report only. A 20-attempt two-line count is a branch
   (P80/P84/P93): this phase's two seeds read -6 and +2, pooled p = 0.19;
4. **the guards** - every payload-present release on a belt; the descent budgets via
   `105 --min-success-rate 0`; `clr`/`clr_edge` > 0 on every held place leg; no new
   failure-reason key.

**No-harm** is the unset acceptance (`scripts/accept.sh`): 8/10, `fingerprint: matches`,
`190: PASS`, and its `[fruit]` stream byte-identical to the previous phase's record.

## 6. Read rules

* **A destination is a tray.** Quote the tray census and the ledger, never a distance to
  a target: P122 measured that the ledger's uncalibrated `nearest` is the mis-sort.
* **The place reach is the gate and it is per side.** A new body on -Y does not move the
  +Y lane's edge or place point; the report's `_output_belt_edge_y` is per side.
* **An x-offset body is free only while the payload's downstream offset plus its radius
  stays upstream of the body's edge** - quote both numbers, and re-measure the offset on
  the new pose (it is attitude-dependent: `+50..60 mm` on the shipped lanes,
  `+20..30 mm` here).
* **A scene change moves the collider set**, so a treatment cell is its own branch: no
  fingerprint comparison, and no count claim.
* **A 20-attempt two-line count is a branch**; two seeds or nothing.
