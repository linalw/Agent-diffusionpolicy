# P114 - the scenario descriptor + the instruction layer, designed

Two objects, both **default off**, both data:

* a **scenario descriptor** (`FRUIT_SCENARIO=<path>`) - the stations, the pick
  and place points, the belt, the destinations and their physical release
  targets, the supply mix/band/schedule. Geometry and supply are applied at
  `SceneConfig` / `SupplyPlan` construction; the destinations are the
  dispatcher's address book. A new target marked `auto` is **solved at startup**,
  so "a new pipeline is a new JSON plus a solve" is literal.
* a **sort instruction** (`FRUIT_SORT_INSTRUCTION=<path|inline>`) - an ordered
  mapping from fruit attributes to destination ids. The resolver validates it
  against the descriptor and the capability map, and the **place dispatcher**
  uses the fruit's own destination instead of the arm's lane.

The code is `src/fruit_sorting/scenario.py` (pure data/parse/capability, no
simulator) plus ~20 small hooks in `tasks.py` (`logs/p114/COUPLING.md` lists the
sites). Every hook is gated on `self._instruction is not None` or
`self._scenario is not None`; unset is the shipped path byte for byte (proved in
`RESULTS.md` §2).

## 1. The descriptor

`configs/scenarios/shipped_twoline.json` is the reference - the shipped cell
expressed as data. A new pipeline copies it and edits fields:

```json
{
  "schema": "fruit-sorting-scenario/1",
  "name": "shipped_twoline",
  "stations": {"left": 0.0, "right": -0.10},
  "pick":     {"x": 0.34, "y": 0.0},
  "belt":     {"speed_m_s": 0.12},
  "place":    {"x": 0.43, "y": 0.50},
  "destinations": [
    {"id": 0, "name": "lane0_plus_y", "side": "+y", "kind": "belt",
     "target": [0.43, 0.50],
     "reach": {"status": "verified", "residual_mm": 14.9, "source": "logs/p90/..."}},
    {"id": 1, "name": "lane1_minus_y", "side": "-y", "kind": "belt",
     "target": [0.43, -0.50],
     "reach": {"status": "verified", "source": "..."}}
  ],
  "supply": {"x_min": 0.20, "x_max": 0.36,
             "grades": {"A": 0.375, "B": 0.375, "C": 0.25},
             "schedule": "wave"},
  "calibration": {"place_tolerance_mm": 25.0}
}
```

The loader is strict: an unknown key, a no-schema file, a duplicate id, a
destination whose target y-sign contradicts its `side`, an unknown `reach.status`
or an unknown `supply.schedule` all raise (`scenario.load_scenario`). A typo
must fail the build, not author the shipped geometry (the P30-A rule).

**What each block changes**

| block | applied at | env still wins |
| --- | --- | --- |
| `pick`, `belt`, `place` | `SceneConfig.__post_init__` (`assets.py`) | yes (`FRUIT_GRASP_Z`, `FRUIT_BELT_SPEED`, `FRUIT_OUTPUT_PLACE_*`) |
| `stations` | `run_bimanual`'s two-line station defaults (`tasks.py:10499`) | yes (`FRUIT_BIARM_STATION_L/R`) |
| `supply` | `SupplyPlan.from_env` defaults (band, grade/class mix, schedule) | yes (every `FRUIT_SUPPLY_*`) |
| `destinations` | the place dispatcher + the capability map | - |

**The calibration.** A destination's `reach` is one of:

* `verified` - trusted, with provenance (the shipped lanes read 14.9 mm on P90's
  static map; the live place leg's own `res_end` is 13-34 mm). No startup solve,
  which is what keeps an instruction that reproduces today's routing
  *byte-identical* to the un-instructed run.
* `auto` - **solved at startup** by
  `PickAndPlaceTask._calibrate_sort_destinations`: the arm on the destination's
  side is seeded at its `grasp_lift` pose and `ArmController.solve_to` targets
  `(x, y, output_place_z [+ the OpenArm transfer add])`, the same position-only
  IK the place leg runs (P90's `NAT` mode). Reachable iff the residual is within
  `calibration.place_tolerance_mm` (default 25 mm - the live place leg's own
  13-34 mm scale, not a precision claim), and the achieved jaw/pad height,
  tilt and joint margin are printed. A failed solve removes the destination from
  the map; an instruction that names it is **refused**.
* `unreachable` - declared; refused at parse.

The station pre-poses were already solved per scenario
(`_prepare_two_line_stations`, `tasks.py:10240`), so moving `pick`/`stations`
re-solves them with no extra work. P114 adds the _destination_ solve, which is
the other half of a station move.

## 2. The instruction

A rule file (or inline text; `;` separates rules in an inline string):

```
# comments and blank lines are ignored
grade=A => 0          # left lane
grade=B => 1          # right lane
grade=C => skip       # never selected (today's pure routing)
```

```
size<40 => 1          # millimetres, strict: 39.9 -> 1, 40.0 -> 0
default => 0
```

Grammar, in precedence order (first match wins; `default` must be last):

| lhs | meaning |
| --- | --- |
| `grade=<A|B|C>` | the sample's grade label |
| `species=<name>` / `class=` / `category=` | the pool category |
| `size<40`, `size<=40`, `size>40`, `size>=40`, `size=40` | diameter in **millimetres** |
| `ripeness<0.5`, `defective=0` | the sim's two drawn labels (see §5) |
| `default` | every unmatched fruit |

Right-hand side: a destination id in the descriptor, or `skip`.

The parser (`scenario.parse_instruction`) refuses, with the file and line:

* a destination that is not in the descriptor;
* a destination no arm can serve (wrong side, `unreachable`, or an `auto` solve
  that failed);
* an unknown attribute (e.g. `colour`), a bad operator, a non-integer id, a
  negative id;
* a grade or species the pool cannot produce (the vocabulary is `cfg.grades` /
  `cfg.fruit_dimensions`);
* a second `default`, a rule after `default`, an empty file.

A fruit that matches **no** rule and has no default is *unassigned*: the
selectors never choose it and the coverage row reports it. It is not guessed
onto a lane. That is the degradation rule for a rule set that does not cover the
pool.

## 3. The capability map and the dispatcher

The physical fact the audit found: **an arm only reaches the output belt on its
own side**; the left cannot cross the body to the -Y belt and vice versa
(`tasks.py` "the arm cannot change lanes mid-attempt", the two-line worker's
`bin_index` is both its selector lane and its place lane). A payload cannot
cross to the other belt, so a destination is not free for every arm.

The capability map is therefore

```
arm(destination) = the side-matching arm, if its reach is not refused
left  serves +y destinations   right serves -y destinations
```

and the instruction resolver asks it twice:

1. **static** (`parse_instruction`): every named destination must exist and be
   servable by *some* arm.
2. **measured** (after the `auto` solves): `_refresh_sort_capability` rebuilds
   the map and raises `ScenarioError("[sort] REFUSED: the instruction maps a
   fruit to destination 3 ... but no arm can deliver there")` **before the first
   attempt**. The tray cell measured this: the solve read 1138.3 mm against the
   25 mm bar and the run aborted with no attempt and no mis-sort.

At run time the selectors filter each candidate by
`destination in capability[this arm]` (`_sort_admits`), and the worker dispatches
the fruit's own destination (`sort_destination(state)`) to `_run_impl`, where
`_arm_for_destination` turns it back into the one arm that can serve it. The
same fruit therefore cannot be picked by an arm that cannot deliver it.

**What this deliberately does not do**: it does not re-route a fruit to another
arm mid-attempt (the arm is committed at selection), and it does not move the
place lane after the lift. A "sort by destination regardless of arm" cell needs
a destination reachable from both arms - i.e. a station where both arms' place
targets overlap, which this geometry does not have (P90: the place station is at
the corner of the solvable box).

## 4. The blockers, stated

* **The lane is the arm.** A third *physical* lane (a third belt, a tray served
  by its own conveyor) is a scene build (`conveyor.OutputBelt`), not a
  descriptor field. The descriptor can add a *target on an existing lane* (P114's
  `dest 2` at `(0.38, +0.55)`) and that is what the validation measures; a new
  belt is a hardware/scene change.
* **One place height.** `destination.target` is `(x, y)` at the cell's
  `output_place_z`; a destination at a different height would need a per-
  destination z and its own descent, which is not built.
* **The instruction is scripted-only.** The direct/policy env
  (`rl_env.py`) and the hybrid canary (`60_eval_policy.py`) refuse it: they
  select through their own trigger/grade lane and have no dispatcher. A policy
  cell would need the dispatcher threaded through the primitive handover.
* **The arm cannot serve the other side.** That is physics, and the refusal is
  the honest answer.

## 5. What the fruit attributes can support - and what they cannot

At pick time the sim exposes (`FruitSample`, `spawner.state()`):

| attribute | source | can an instruction use it? |
| --- | --- | --- |
| species/category | the pool draw | yes (measured geometry/class) |
| diameter | the pool draw, measured on the body | yes (size) |
| grade | **drawn at spawn** (`_mix_allocate`), not perceived | yes, but it is a *label* in the sim |
| ripeness | drawn at spawn (`random`) | yes, but it is a *label*, not a measurement |
| defective | drawn at spawn | yes, but it is a *label* |
| colour | **not an attribute**: `FruitSpawner.CATEGORY_STYLE` is a per-category constant visual colour, not a per-instance measurement | **no** - a colour rule would need a vision pipeline that measures it |
| position/velocity | measured | not a sorting attribute (the selector already uses them) |

So the instruction layer is exact for **species, size and the sim's labels**,
and it is a **labelling interface** for grade/ripeness/defective: on a real cell
the same attribute dict must come from a classifier (the camera the cell already
has), not from the spawn draw. That is the honest boundary - the phase validates
the *routing*, not perception. A `colour=>...` rule is refused by the parser
rather than silently sorting by category colour.

**Degradation ladder** (all measured in the validation):

1. an attribute the cell does not have -> refused at parse;
2. a destination no arm can reach -> refused at startup (the tray cell);
3. a fruit no rule covers -> never selected (unassigned);
4. a rule that covers the pool -> the arm carries to the instructed destination,
   and the ledger checks the landing.

## 6. The portability contract

| | before P114 | after P114 |
| --- | --- | --- |
| a new station / pick point / belt speed | edit `assets.SceneConfig` + the two-line station defaults | descriptor fields |
| a new destination on an existing lane | edit `SceneConfig.output_place_*`, `jaw_target`, the driver's lane expression | `destinations[]` entry + `reach: auto` |
| a new sorting rule | edit `rl_env.py` / `20_pick_place.py` / `40_collect_demos.py` / `60_eval_policy.py` + the selector's grade-pure predicate | an instruction file |
| a new mix/band/schedule | `FRUIT_SUPPLY_*` (or code for a new schedule) | descriptor `supply` block |
| the gate | the motion reference + `accept.sh` | the same gate + the ledger's assignment accuracy |
| a new physical lane / hand / camera | scene/hardware code | still scene/hardware code |

A new pipeline is therefore: **copy the JSON, edit it, mark every new target
`auto`, write the instruction, run the acceptance and read the ledger**. No
default changes; P114 ships no flip.
