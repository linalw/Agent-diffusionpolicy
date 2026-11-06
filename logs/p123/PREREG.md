# P123 - a real third output destination: registration, pinned before any cell

P122 (`logs/p122/SPEC.md`) fixed two things: a destination is a **physical output
body** (belt + chute + tray; two targets on one belt feed the *same* tray), and the
binding term for a third body is the **place reach** (P90: `NAT` converges only in
x 0.38-0.48, |y| 0.35-0.55). The owner chose item 2: build the third body and solve
its place point. The owner's constraint stands - the dynamic scattered pick pipeline
must not be stopped, diverted, gated or paused; a third belt **downstream** adds no
such element.

This file pins the **cell** before it ran. The design measurements (the layout
arithmetic and the static reach solve) were taken first and are evidence, not
results: `logs/p123/layout.txt` (offline, `layout.py`) and `logs/p123/probe.txt`
(`probe.py`, one static session).

## 1. What was measured before this registration (inputs, not claims)

* **The scene survey** (`probe.txt` section S): belt/chute/tray AABBs from the
  stage's own bounds cache. The output deck (z 1.30-1.35) carries slabs at
  |y| 0.425..0.675 on both sides, x 0.10..1.20; the free bands inside the reach box
  are |y| 0..0.425 (inboard) and |y| > 0.675 (outboard, outside P90's box).
* **The three candidates** (`layout.txt`), in the brief's order:
  * **A** third belt **inboard on -Y**, |y| 0.280..0.395, **x-offset downstream**
    (0.480..1.200), own tray |y| 0.260..0.400, the -Y tray narrowed 0.34 -> 0.20 m:
    **passes every offline gate** (place in the reach box; delivered point 56-59 mm
    inside the slab = 7 sd of the P122 spread; **no transit crosses it** - the
    payload, radius included, is at x <= 0.469 where a transit crosses its band,
    11 mm upstream of the belt's edge; 30 mm of air to the -Y belt, 50 mm to its
    tray, 16 mm between chutes; 0 cm^2 of new camera occlusion: the body is
    downstream of the supplied fruit's x band 0.148..0.413).
  * **B** split the -Y belt into two narrow belts (full x): the reach passes at both
    places (0.48, -0.35) and (0.38, -0.55) but the **transits cross**: lane 2's
    transit crosses lane 1's edge at a direct-low `clr` of **-9 mm** (predicted
    contact), and both narrow belts stay over the fruit's x band -> **KILL**.
  * **C** third belt outboard (|y| ~0.68-0.70): P90's `NAT` residual is 41-108 mm at
    |y| = 0.65, the belts overlap, and it occludes the arrival -> **KILL**.
* **The reach solve** (`probe_rows.json`): the exact cells, both arms, both heights,
  the gate `res <= 6 mm`, `margin >= 0.05 rad`, `pad >= 2 mm` over the *surface
  actually under the pad* (the new slab where the cell sits on it), `tilt`
  60-110 deg (the shipped place leg's own measured class, P73 `tilt_end` 78.7-105).
  Grid: x 0.38-0.48, |y| 0.30-0.55, z 1.450 (the place height) and 1.530 (the
  transfer the leg ends at).

**Kill rule for the build**: if no cell inside the proposed third slab passes, or if
the chosen cell's body intersects the arm's carry path or the pick station, the
phase **stops at a kill** and nothing is built. `layout.txt` + `probe.txt` decide
that before the build; this file records the decision.

## 2. The build (default off, no shipped default moved)

`FRUIT_OUTPUT_LANES=3` authors a third output body: belt x 0.480..1.200, |y|
0.280..0.395, top 1.350 (the same plate, speed, friction, surface velocity and
discharge as the other two), its **own** chute and its **own** tray (x 1.35..1.95,
|y| 0.260..0.400); the -Y tray narrows to 0.20 m (centred) so the two trays have
50 mm of air. Unset = 2 lanes = the shipped scene, byte for byte, no body authored.

The place point is a **P114 descriptor destination** (`logs/p123/three_dest.json`,
destination 2, `reach: auto`), so the startup solve - the place leg's own
position-only IK, `tasks._calibrate_sort_destinations` - is what admits it, and a
run whose solve fails is **refused before the first attempt** (P114's rule). The
capability map keeps its physical meaning: destination 2 is `-y`, so the **right**
arm serves it (`left = +y, right = -y`).

## 3. The cell (pinned)

* **Scenario**: the shipped scripted two-line (`FRUIT_BIARM`/`FRUIT_BIARM_TWOLINE`
  default on since P85, `FRUIT_SPEED_RELEASE` trim, P71 geometry), 20 attempts,
  seeds **5 and 6**, one claim per run.
* **Instrumentation, identical in every arm**: `FRUIT_MOTION_REPORT=1
  FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1` (P92's four).
* **Cells**: `C5`/`C6` = the shipped scene, no descriptor, no instruction;
  `T5`/`T6` = `FRUIT_OUTPUT_LANES=3` + `FRUIT_SCENARIO=logs/p123/three_dest.json` +
  `FRUIT_SORT_INSTRUCTION=logs/p123/three_dest.txt`
  (`grade=A => 0`, `grade=B and size<66 => 2`, `grade=B => 1`, `grade=C => skip`).
* **Endpoints, in this read order**:
  1. **the tray census** - which *physical* tray each released payload ended in
     (`[belt] ... discharged ... [tray N]`, joined to the ledger's `idx`). The
     endpoint is the tray, not the target (`logs/p122/SPEC.md` R0).
  2. **the ledger** - `[sort] attempt ... in_dest=` and the per-destination table:
     released / in_destination / mis_sorted, per destination.
  3. **the placed count** - report only, a branch (P80/P92/P93).
  4. **guards**: every payload-present release lands on *some* belt
     (`on_belt=1`, i.e. `release_bottom >= 0`); the descent budgets (not
     re-tuned); the crush guard (`sep@loss - dia >= -15 mm`); and the
     **arm-to-new-body clearance** on the carry transit - the `[carry]` `clr` and
     P72's `clr_edge` per held place leg, with the new lane's own surface under
     the pads (`_payload_clearance` is lane-aware since this phase), no leg <= 0.
* **No-harm (the shipped scene must not move)**: `scripts/accept.sh` with the knob
  unset reads **8/10 + `fingerprint: matches` + `190: PASS`** and its **421
  `[fruit]` lines are byte-identical** to `logs/p121/accept_final.log`. `C5` must
  also replay `logs/p92/C5.log` on its `[fruit]` stream modulo the phase's own
  rows, which proves the lane table itself inert on the two-lane path.
* **Adoption**: **not** this phase. The knob is default off; on it the scene moves
  by construction, so a flip would owe both motion references, a scripted
  re-baseline and every store (`logs/p90/COST.md` §6). The owner decides.

## 4. Decision rules (pinned)

* **D1 (the body works)**: at least one payload is discharged into **tray 2**, and
  the ledger's `in_destination` for destination 2 counts it. The failure modes are
  named: a payload that lands between the belts (a fall - `on_belt=0`), or on the
  wrong belt (a tray-census mismatch).
* **D2 (the destinations separate)**: on the treatment's releases,
  `in_destination / released >= 0.90` **and** the tray census agrees with the
  ledger on every joined payload (no release in a tray other than its
  destination's).
* **D3 (no acquisition cost)**: the treatment's placed count is reported, never
  gated (a 20-attempt count is a branch). What **is** gated: a **new failure-reason
  key** in the treatment's `[run]`/reason census that the same-seed control does
  not carry, and a treatment `[carry]` leg with `clr <= 0` or `clr_edge <= 0`
  (contact with the new body).
* **D4 (the scene manifest names the set)**: `assets.scene_provenance(...)
  ["output_lanes"]` has 3 entries with destination 2's geometry, and a two-lane
  run's `[fruit]` stream is byte-identical to the record.

If D1 or D4 fails, the phase reports a **kill on the built form** (the body is not
a destination); if D2 fails, the separation is the finding (the spacing was not the
problem - the physical landing was); if D3 fails, the new body costs the line and
nothing is shipped.

## 5. What is not claimed

No throughput number, no rate, no "the third destination makes the cell faster".
The environment's own history (P80/P81/P92/P93) says a 20-attempt two-line count is
one draw of a quantised outcome. The claim this phase makes is geometric and
mechanical: **a third physical destination exists, its place point is reachable,
its payloads land in its own tray, and the two-lane scene is unchanged**.
