# Portability and instructions: how to move this cell to another pipeline and tell it where to put fruit

**Scope.** This document is the close-out of the portability/instruction arc
(P114-P127). It answers two questions the owner asked:

1. *can this two-finger cell be moved to a different pipeline?* - **yes, as
   data**: a scenario is a JSON descriptor plus a calibration solve; an
   instruction is a text file; the physical cell is unchanged.
2. *can it decide where to put each fruit from an instruction?* - **yes, on both
   the scripted line and the direct/policy line**, with a per-destination ledger
   that says whether the payload landed where the instruction said.

It also records the one thing the arc could **not** make free: a **third physical
destination** costs the shipped cell **17.5 points** of its scripted success rate
(P127), because a scene's collider set re-draws every grasp. The third lane is
built and works per-run; it is **opt-in**.

Every number below traces to a `logs/` phase; the evidence map is section 10.

---

## 0. The one-page version

| question | answer | phase |
| --- | --- | --- |
| a new pipeline, how much code? | **none**: copy `configs/scenarios/shipped_twoline.json`, change the stations/pick/place/destinations/supply, solve the `auto` targets | P114 |
| a new sorting rule? | **a text file**: `grade=A => 0`, `size<40 => 1`, `species=apple and size>=66 => 2`, `default => 0`, `skip`, `!=` | P114-P116 |
| does an instruction ever mis-sort silently? | **no**: the parser refuses unknown attributes / destinations / unreachable targets; `FRUIT_SORT_STRICT=1` refuses an instruction that leaves fruit unmatched | P114/P115 |
| can I see the decision before a run? | **yes, offline**: `scripts/262_sort_plan.py` prints the rule table, the **overlap pairs with the winner**, the partition over 120 attribute cells and the unmatched cells | P116 |
| does the ledger prove the destination? | **yes**: `[sort] attempt ... dest=<d> ... in_dest=<0/1>`, per destination and per rule, `in_dest` from the payload's measured release | P114-P116 |
| the direct/policy line? | **yes**: `rl_env.direct_dispatch` decides the destination and the arm, feeds it in the goal, places through the thread-local override, and logs the same ledger; the action interface is untouched (7 joints + 1 finger) | P121 |
| a third destination? | **a physical output body** (belt + chute + own tray) - built and correct (25/25 tray agreements) but **-17.5 points** on the shipped cell, so **opt-in** (`FRUIT_OUTPUT_LANES=3`) | P122-P127 |
| what is not portable? | **perception** (colour is not a per-instance attribute; grade/ripeness are drawn labels), the tactile/force channels, and the hand's own limits | P114/P121 |

The shipped default is unchanged: two lanes, grade A -> lane 0 (left), B -> lane 1
(right), C -> skip, acceptance **8/10**, two-line **58/80 = 72.5 %** at four seeds.

---

## 1. What "portable" means here

The cell has three kinds of coupling (audited with file:line in
`logs/p114/COUPLING.md`):

* **geometry** - the stations, the pick/place points, the belt, the output
  bodies and the tray;
* **the fruit -> destination rule** - before P114 the arm was the lane was the
  grade, fixed in four places (`rl_env.py:3529`, `tasks.py:11947`, the worker's
  `bin_index`, the grade-pure selector);
* **the supply** - band, mix, schedule.

A pipeline is the first and third; the rule is the second. The cell is portable
when all three are data. The one thing that cannot be data is the **physical
reach**: which arm can put a payload where, on this robot, at this station.

That is the **capability map**: left serves `+y`, right serves `-y`, and a
destination the arm cannot reach is **refused**, never attempted.

---

## 2. The scenario descriptor

`FRUIT_SCENARIO=<json>` (`src/fruit_sorting/scenario.py`). Strict: unknown keys,
duplicate ids, a side/target contradiction, an unknown reach status or schedule
all raise. The shipped cell is `configs/scenarios/shipped_twoline.json`:

```json
{
  "schema": "fruit-sorting-scenario/1",
  "name": "shipped_twoline",
  "stations": {"left": 0.0, "right": -0.1},
  "pick":   {"x": 0.34, "y": 0.0},
  "belt":   {"speed_m_s": 0.12},
  "place":  {"x": 0.43, "y": 0.5},
  "destinations": [
    {"id": 0, "name": "lane0_plus_y", "side": "+y", "kind": "belt",
     "target": [0.43, 0.5],
     "reach": {"status": "verified", "residual_mm": 14.9, "source": "logs/p90"}},
    {"id": 1, "name": "lane1_minus_y", "side": "-y", "kind": "belt",
     "target": [0.43, -0.5],
     "reach": {"status": "verified", "residual_mm": 14.9, "source": "logs/p90"}}
  ],
  "supply": { ... }   // band, mix, schedule (optional; env knobs win)
}
```

`reach`:

* **`verified`** - a solved place point, no startup cost;
* **`auto`** - solved at startup with the place leg's own position-only IK at a
  **25 mm** bar (the live leg's `res_end` is 13-34 mm); the run prints
  `reachable`/`UNREACHABLE`;
* **`unreachable`** - refused before the first attempt.

**A destination is a physical output body.** `conveyor._build_discharge` builds
**one tray per belt**, so two targets on one belt are the *same* destination
(`logs/p122/SPEC.md` R0). A third destination is a third body - see section 6.

**What a new pipeline costs:** copy the JSON, change the fields, run once with
`FRUIT_SCENARIO=<path>`: the `auto` destinations solve, the stations become the
two-line defaults, the supply block applies as defaults. The motion references
and the stores are **per scenario** - a new pipeline re-records its own.

---

## 3. The instruction language

`FRUIT_SORT_INSTRUCTION=<path|inline>`. One rule per line,
`condition => destination`; **first match wins**; `default` must be last;
`skip` means "never select this fruit".

```text
# today's scripted routing
grade=A => 0
grade=B => 1
grade=C => skip

# a size class
size<40 => 1
default => 0

# `and` (up to three terms), `!=` (the rest of a class)
species=apple and size>=66 => 2
species=apple and grade!=A => 1
default => 0
```

Attributes: `grade`, `species`/`class`/`category`, `size` (mm, `< <= > >= =`),
`ripeness`, `defective`. **`colour` is refused** - the sim has no per-instance
colour; that is a perception gap, not a syntax gap.

Refusals (all **before** the first attempt, naming file and line): an unknown
attribute, an unknown/negative destination, a destination no arm serves, a
destination declared unreachable, a grade/species the pool cannot produce, a
second `default`, a rule after `default`, a `default` carrying a condition, an
empty instruction.

**`FRUIT_SORT_STRICT=1`** turns an unmatched fruit into a startup refusal (a
deliberate `skip` is still allowed). Use it when a dropped fruit is a defect.

**Plan before you run** (`scripts/262_sort_plan.py`):

```
P116 plan - instruction configs/instructions/owner_a_left_apples_right.txt
  rule 1: grade=A => 0 arm=left
  rule 2: species=apple => 1 arm=right
  rule 3: default => skip

  OVERLAP: 1 pair(s) - the earlier rule wins:
    rule 1 (grade=A => 0) x rule 2 (species=apple => 1): 5 cell(s); rule 1 wins
      e.g. apple 62mm grade A -> dest 0 (not 1)

  PARTITION over 120 attribute cells: dest 0 40 / dest 1 10 / skip 70
```

`--strict-overlap` exits 1 on any overlap. `or` is written as more rules
(first match wins).

---

## 4. The capability map and the ledger

**Capability**: `left=[+y destinations]`, `right=[-y destinations]`; an `auto`
destination is provisional until its solve. The selector admits a fruit only if
its destination is in the carrying arm's map; the dispatcher places on the
destination's arm.

**Ledger** (per attempt, and per destination / per rule at the end):

```
[sort] attempt 16 idx=4 apple d=7.0cm grade=C ripeness=0.55 arm=right rule=1 \
       dest=1 target=(0.43,-0.50) placed=1 release=(0.47,-0.54,1.46) \
       on_belt=1 side=-y nearest=1 dist=53mm in_dest=1
[sort] ledger: attempts=20 assigned=20 released=12 in_destination=12 \
       mis_sorted=0 not_placed=8 refused=0 (pool unassigned=0 skip=0)
```

`in_dest` is measured from the **payload's release position** against the
destination targets. **The endpoint is the ledger's assignment accuracy, never
the placed count** (a count is a branch).

---

## 5. The direct/policy line

P121 removed the refusal and wired the instruction into `SortingRLEnv`:

* `direct_dispatch(target, armed, sort_destination, arm_for_destination)` -
  unset is the shipped `grade A -> block 0 -> left, else block 1 -> right`
  expression **byte for byte**; armed is the fruit's destination and the map's
  arm;
* the **goal** keeps `[xyz, velocity, diameter, bin_index]` - 0/1 are the trained
  values (the destination's lane is the lane the arm uses), **2 is a declared
  OOD input**;
* the **place** goes through `tasks.dispatch_destination` (the thread-local
  `place_xy` override `_place_xy_for` reads), the leg is `place<dest>`, and the
  same `[sort]` ledger is emitted;
* a destination beyond the two shipped lanes raises before the first attempt
  unless `FRUIT_SORT_THIRD_DEST=1`; the handoff presentation still refuses (it
  has no dispatcher).

Measured (3 seeds x 10 episodes, the shipped direct config): today's routing
18/18 and 22/22 in destination, a size rule 20/20 (including **7 grade-B and 4
grade-C decisions on the left**, a destination grade routing cannot produce),
and a third destination 22/23 - the one miss a **separation** limit, not a
wiring one (section 6).

**The action interface is unchanged**: 7 joint targets + 1 finger. The policy
still only grasps; the destination is the harness's decision.

---

## 6. A third destination: built, correct, and **opt-in**

`FRUIT_OUTPUT_LANES=3` (default 2 = no body authored, byte for byte) adds a
third output body **inboard on -Y**, `|y| 0.280..0.395`, **x 0.480..1.200**
(downstream of every place transit), with its own chute and tray (the -Y tray
narrows 0.34 -> 0.20 m). The place point `(0.48, -0.30)` solves at **6.0 mm /
+0.457 rad / +70 mm pad clearance / 92.7 deg**; the startup solve reads 11.5 mm
against the 25 mm bar.

**It works**: P123's cells read **25/25 tray agreements** (dest 0 -> tray 0,
dest 1 -> tray 1, dest 2 -> tray 2) and the ledger **0 mis-sorts**.

**It costs**: P127's four-seed 20-attempt battery on the shipped two-line reads
**44/80 = 55.0 % on three lanes against 58/80 = 72.5 % on two** - **-17.5
points, worse at every seed**. The mechanism is P71's: a scene's collider set
re-draws the release geometry and the solver order, so every grasp moves; a body
140 mm from the pick station is not physics-neutral. The acceptance's 10
attempts (7/10 vs 8/10) did not see it.

So the lane is **opt-in**, and the rule for a scene flip is: **a 20-attempt
battery at >= 2 seeds with same-seed controls**; the acceptance is a smoke, the
tray census proves the destination (not the cell), and the canary is an
interface check.

**Attribution if two zones share one body** (not recommended): calibrate the
release offset (**+48 mm x, +-35..37 mm y**), then separate **along x by >= 50
mm** (0/20 000 calibrated); **never uncalibrated** (50 mm reads 33 % wrong) and
**never a (50,50) diagonal** (2.1 %; P121's 1/23).

---

## 7. The migration recipe (what a new pipeline actually needs)

1. **Copy** `configs/scenarios/shipped_twoline.json`, edit `stations`, `pick`,
   `place`, `belt`, `destinations` (with `reach: auto` for anything not on the
   shipped map) and `supply`.
2. **Solve the reach**: `scripts/run.sh logs/p123/probe.py`-style solve (or the
   `auto` startup solve) at the new place points; a cell that fails residual 6
   mm / margin 0.05 rad / pad 2 mm is a **kill before the build**.
3. **Write the instruction** (or start from `configs/instructions/`), and run
   `scripts/262_sort_plan.py --instruction <file> --strict-overlap` to see the
   partition and the overlaps.
4. **Run once** and read the ledger: the per-destination table is the acceptance
   of the mapping; the placed count is a branch.
5. **Re-record** the motion references of the new scenario (they are per
   scenario) and note the store's manifest (`scene.output_lanes`, `supply.band`).

What stays the same: the arms, the gripper, the catch, the place primitives, the
ledger, the instruction language. What changes: the JSON, the instruction file,
the references.

---

## 8. What is not portable

| gap | why | where it lands |
| --- | --- | --- |
| **the fruit's state** | **closed as a module (P135)**: `FRUIT_TRACK_SOURCE=depth` measures the centre (4.7 mm median) and the diameter (3.4 mm) from the rendered RGB-D + instance mask through the camera's authored lens and prim pose; the grasp aim and the close can read it (`FRUIT_PERCEPTION_CLOSE`) | the remaining limits are measured: the hand **occludes** the fruit as it descends (the fit's z drifts 11 -> 44 mm as the mask shrinks), so a wrist camera or a second view is the next spend; the error is a systematic +y bias (a sphere fit through an ellipsoid's cap), which is a reference-sphere calibration. `docs/TRACKING.md` |
| **colour / appearance** | no per-instance colour in the sim; `grade`/`ripeness`/`defective` are **drawn labels** | a classifier that emits the same attribute dict; the parser already refuses a missing attribute |
| **tactile / force channels** | hand-specific (`tactile.py`, per-pad readers) | a hand-specific extension of the descriptor, not built |
| **the hand's own limits** | `docs/END_EFFECTOR_DECISION.md` (nine routes, two sanctions left) | a new pad asset or a real-jaw force anchor |
| **a third physical lane** | it changes the scene's physics (this document, section 6) | a scene build + a 20-attempt battery |
| **the policy's destination channel** | the action is 7 joints + 1 finger; the destination is an input | a policy that outputs a destination is a different interface, not built |

---

## 9. The read rules that bite

1. **A destination is a physical body**; a target on an existing belt is the
   same destination.
2. **The ledger is the endpoint**; a placed count is a branch (the same control
   swings 16 -> 10 between seeds).
3. **A scene flip needs a 20-attempt battery**; the acceptance cannot see a
   -17-point scene cost (P127).
4. **The canary is an interface check**, not a scene instrument (P125: 56.7 % vs
   55.0 % on the two scenes).
5. **`FRUIT_SORT_STRICT=1`** when a dropped fruit is a defect; `skip` when it is
   a decision.
6. **Overlaps are precedence**, not errors - read them with the linter, and
   prefer `!=` over order when the semantics must not depend on line order.
7. **A rule that carries `and`** must be read by the **per-rule histogram**
   (`logs/p115/p115_report.py --ledger`), not the destination totals.

---

## 10. Evidence map

| phase | what it established | evidence |
| --- | --- | --- |
| P114 | the descriptor, the instruction parser, the capability map, the ledger; the unset path byte-identical (421/421) | `logs/p114/` |
| P115 | `and` terms, the rule table, `rule=` in the ledger, `FRUIT_SORT_STRICT` | `logs/p115/` |
| P116 | the offline plan/lint, overlap precedence, `!=`, the owner's two-rule example (`owner_precise`) | `logs/p116/` |
| P121 | the direct/policy dispatcher (18/18, 22/22, 20/20; the third destination 22/23) | `logs/p121/` |
| P122 | a destination is a physical body; the release offset; the spacing spec (50 mm x calibrated) | `logs/p122/` |
| P123 | the third body built, 25/25 tray agreements | `logs/p123/` |
| P124/P125 | the flip, its revert, the recollection (196 episodes, 3 lanes) and the canary correction | `logs/p124/`, `logs/p125/` |
| P126/P127 | the flip re-shipped, then reverted on the 20-attempt battery (-17.5 points) | `logs/p126/`, `logs/p127/` |
