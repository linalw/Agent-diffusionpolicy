# P114 - the coupling audit

What ties the shipped cell to *one* pipeline, quoted from the tree this phase
ran on (`tasks.py` **15d2348a**, `assets.py` after the P114 edit, `fruits.py`,
`rl_env.py`). Line numbers are this tree's; every site was read, not assumed.
The last section names the **two hardest couplings** and what the P114 data
layer does about each.

## (i) Scenario geometry - where the cell is

| site | file:line | today | a new scenario changes | kind |
| --- | --- | --- | --- | --- |
| pick station | `assets.py:251` `pick_x = 0.34`, `:253` `pick_y = 0.0` | one station on the main belt | station x/y (the reach band is x 0.20-0.36, y per arm) | **constant**, read by every consumer |
| two-line stations | `tasks.py:10499-10517` (`FRUIT_BIARM_STATION_L/R` default `0.0 / -0.10`) | left upstream, right downstream on the same belt | station pair, separation, and which arm owns which | **constant** + **solved** (the pre-pose below) |
| station pre-pose | `tasks.py:10240-10340` `_prepare_two_line_stations`, target at `:10330-10331`, `solve_to` `:10334` | per-arm joint config solved from the calibrated `grasp` seed at `(pick_x, station_y, belt_top + grasp_clearance)` | automatically re-solved when the station/pick moves | **solved** (once per batch, cached per station pair) |
| pick height | `assets.py:273-275` `grasp_clearance` (`FRUIT_GRASP_Z`, 0.095) | jaw centre 95 mm above the belt | a new belt height/gripper needs its own reach check | **constant** |
| main belt | `assets.py:210-229` `belt_center`, `belt_size`, `belt_speed` (0.12 m/s) | 1.60 m along Y, 0.46 m wide, `-Y` at 0.12 | belt length/width/speed/direction | **constant**, read by the schedule and the catch |
| spawn/despawn | `assets.py:245` `spawn_y = 0.68`, `:249` `despawn_y = -0.70` | the release window | upstream/downstream extents | **constant** |
| output belts | `assets.py:315` `output_belt_y = 0.55`, `:334` `output_belt_top_z = 1.35`, `:339-341` centre/size | exactly **two** raised belts, one per side | more lanes = a scene build (`conveyor.OutputBelt`, `:507-560` builds one body per side) | **code path** (a third belt is not a data edit) |
| release points | `assets.py:412-416` `output_place_x = 0.43`, `output_place_y = 0.50`; derived `:545-548` `output_belt_drop_points` = `(x, +y), (x, -y)` | two points, symmetric about the belt | per-destination release points (P114's `destination.target`) | **constant**, now overridable per destination |
| place height | `assets.py:534` `output_place_z = output_belt_top_z + 0.10`; `tasks.py:5032-5080` `jaw_target`'s `place*` branch adds `FRUIT_OPENARM_TRANSFER_LIFT` 0.08 for the jaw hand | one height for every destination | a destination at another height needs a per-destination z (not built) | **constant** |
| tray/discharge | `assets.py:438-450` tray, `:692-700` `on_output_tray`; `conveyor.py:507-560` | one tray per belt at `x = 1.65` | tray count/position, or remove the belt | **code path** |
| output lane → arm | `tasks.py:11947` `arm_name = self._arm_for_destination(bin_index)`; before P114 `"left" if bin_index == 0 else "right"` | lane 0 = left (+Y), lane 1 = right (-Y) | the **capability map** (P114) | **code path** (now data-driven) |
| place pose from the leg name | `tasks.py:4987-5080` `jaw_target`: `index = 0 if "0" in name else 1`, then `cfg.output_belt_drop_points[index]` | the destination is the *leg name's digit* | P114: `_place_xy_for(index)` reads the attempt's destination | **code path** (now data-driven) |

**What is still a code/scene edit after P114**: a *new physical lane* (a third
belt/tray body), a new camera view, a different hand. Those are hardware/scene
objects, not descriptor fields - `logs/p114/DESIGN.md` says so explicitly.

## (ii) The fruit → destination rule - the coupling this phase removes

| site | file:line | today | a new rule changes | kind |
| --- | --- | --- | --- | --- |
| scripted driver | `scripts/20_pick_place.py:270` `bin_index = 0 if grade == "A" else 1` | grade A→lane 0, rest→lane 1 | the rule | **code path** (P114: `task.sort_destination(target)`, `:265`) |
| collector | `scripts/40_collect_demos.py:755` same expression | same | the rule | **code path** (P114: `:751`) |
| hybrid canary | `scripts/60_eval_policy.py:219` same expression | same | the rule | **code path** (P114: refuses the instruction, no dispatcher) |
| direct/policy env | `rl_env.py:3529-3530` `bin_index = 0 if grade == "A" else 1; active = "left" if bin_index == 0 else "right"` | grade = lane = arm | the rule | **code path** (out of P114's scope; refuses) |
| carry-and-release helper | `rl_env.py:1511-1519` `carry_and_release(cfg, bin_index)` | a lane index into the drop points | a destination target | **code path** (direct path only) |
| selector eligibility | `tasks.py:9251-9290` `pure_grade` / `wanted_grade` / `grade_lane`; `_reach_anywhere_select` `:9852-9865` | grade-pure per arm (A left, B right, C never) | the mapping | **code path** (P114: `_sort_admits` replaces it) |
| two-line dispatch | `tasks.py:10871` `_biarm_worker(..., bin_index)` and `:11072-11083` | the arm's own lane is the place lane | the fruit's destination | **code path** (P114: `sort_destination(state)`) |
| cross-lane reselect | `tasks.py:13097-13130` | the presented fruit is taken onto the arm's own lane and a sort error is noted | an instruction would have to refuse a cross-capability presentation | **code path** (only the indexed path; the two-line's moving catch skips it, `:12930` `not dynamic_capture`) |
| failure booking | `tasks.py:10142-10215` `run()` | `bin_index` is the goal vector's last element | the destination id | **code path** (unchanged shape; the id is now the instruction's) |

## (iii) The supply - what arrives and with what label

| site | file:line | today | a new scenario changes | kind |
| --- | --- | --- | --- | --- |
| grade mix | `fruits.py:261` `SUPPLY_GRADES = A .5 / B .3 / C .2`, `:269` balanced `A .375 / B .375 / C .25` | balanced on the two-line (pure routing) | the mix | **constant** (`FRUIT_SUPPLY_GRADES` / descriptor `supply.grades`) |
| lateral band | `fruits.py:253-254` `SUPPLY_X_MIN/MAX = 0.20/0.36` | 0.16 m band inside the reach band | the band | **constant** (env / descriptor) |
| gap schedule | `fruits.py:225` `SUPPLY_GAP_MIN = 0.10`; wave/patch/bed constants `:228-250`; `SupplyPlan.from_env` `:436-760` | dense wave sheet on the two-line | schedule + gaps | **constant** (env / descriptor `supply.schedule`) |
| pool & grade labels | `fruits.py:1057-1080` `create_pool` (`_mix_allocate` `:359`), `:1152-1200` `_create_fruit` draws diameter/grade/ripeness/defective | 16 fruit, balanced mix, random labels | count/mix, and **how a grade is obtained** (sim: drawn; real: vision) | **constant** + **code path** (a real perception classifier is the missing source) |
| recycle/rescale | `fruits.py:1440-1500` `respawn`, `:1301` `rescale` | a recycled fruit keeps/redraws its attributes | identity semantics across a recycle | **code path** |

The supply is the *only* source of `grade`, `ripeness` and `defective` in the
sim, and it draws them at spawn - see `DESIGN.md` §5.

## (iv) The calibration - the reference frames and the solves

| site | file:line | today | a new scenario changes | kind |
| --- | --- | --- | --- | --- |
| grasp/pre-pose seeds | `configs/waypoints.json`, `waypoints_oriented.json`; `tasks.py:4082-4140` `_pose` / `_grasp_quat` | calibrated joint configs + the top-down attitude | a new station needs a new seed/solve | **solved** (`_prepare_two_line_stations`) |
| attitude hold | `tasks.py:4116` `_grasp_quat`; `:12930-12960` the coherent block's `hold_quaternion` and the left mirror | T0 top-down, jaws along X, left mirrored | a new geometry may need a new attitude | **code path** + **constant** |
| place reach | `tasks.py:4987-5080` `jaw_target`; `_place_low` `:16204-16370` | position-only IK to `(x, y, 1.53)`, then a finger-bounded descent | a new target must be reach-checked | **solved** (P90's map; P114's `auto` solve) |
| fingerprint references | `configs/motion_reference*.json`; `scripts/105`, `scripts/190` | per-scenario, per-attempt-count | every scenario move re-records its own | **constant** (a gate, not a runtime input) |
| hand/tool | `tasks.py:91-100` `rigid_tool_hand`, `:2127-2150` `FRUIT_GRIPPER_KIND`; `_pad_standoff` `:10080-10110` | the OpenArm jaw hand, 70 mm tool offset | a new hand needs its own offset/reach | **code path** |

## The two hardest couplings

**1. `arm = grade = lane` is one object written in four places.** `rl_env.py:3529`
sets `active` from the grade; `tasks.py:11947` (pre-P114 `11460`) sets the arm
from `bin_index`; the two-line worker passes its own `bin_index` as both the
selector's `prefer_lane` and the place lane (`tasks.py:10995-11083`); and
`jaw_target` (`:5032`) reads the lane from the leg name. Because the selector's
eligibility is grade-pure (`:9251-9290`), the arm that *can* carry a fruit is
decided before the fruit is seen. **P114 breaks the object in two**: the
destination is a function of the fruit's attributes (`sort_destination`), and
the arm is a function of the destination (the capability map). The arm/lane
identity survives only as the **capability** ("left reaches +Y, right reaches
-Y"), which is physics, not policy - and it is why an unreachable instruction is
refused rather than executed.

**2. The place target is derived from the place leg's *name*, not from a
destination object.** `jaw_target`'s place branch does
`index = 0 if "0" in name else 1; px, py = cfg.output_belt_drop_points[index]`
(`tasks.py:5032-5033`), so a leg called `place1` *is* lane 1 and there is no
place in the code where "a destination with its own target" can exist. P114 adds
one indirection (`_place_xy_for`, thread-local per attempt) at exactly that site
and at the two diagnostic reads (`:15670`, `:15754`), so a `place2` can be a
target that is not lane 2 - without moving any shipped leg's command.

## What this audit means for portability

* Everything in group (i) that is a **constant** is now a descriptor field or a
  solve: pick, stations, belt speed, release points, per-destination targets.
* Everything in group (ii) is now the **instruction** (a rule file) plus one
  capability check.
* Group (iii)'s mix and band are descriptor fields; the **schedule** is a
  descriptor field too (scatter/wave/patch/bed). The attribute *source* is not
  portable: the sim draws labels, a real cell needs vision (DESIGN §5).
* Group (iv)'s station pre-pose already re-solves from the station; P114 adds a
  **destination reach solve** for targets marked `auto`.
* Still a code/scene edit: a third physical belt/tray, a new camera, a new hand,
  a different place height. Those are named in `DESIGN.md` §4 and priced in
  `RESULTS.md` §6.
