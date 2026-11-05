# P114 - results

The owner's requirement: the two-finger-gripper cell must be **portable** to
different pipeline scenarios, and it must decide **where to put a fruit from an
instruction** ("它要可以根据指示自己判断把果蔬分拣放到什么位置"). The physics/
end-effector lane is closed (`docs/END_EFFECTOR_DECISION.md`); this phase is the
software architecture. **No shipped default changed; no `configs/` reference
moved.** The one new `configs/` file is
`configs/scenarios/shipped_twoline.json` - the shipped cell written as data,
needed as the reference descriptor the loader and validation (ii) test against.

## 1. The coupling audit

`logs/p114/COUPLING.md`: every site that ties the cell to one pipeline, in four
groups - (i) scenario geometry, (ii) the fruit→destination rule, (iii) the
supply, (iv) the calibration - each with its file:line, what a new scenario
changes, and whether it is a constant, a solved quantity or a code path. The two
hardest:

1. **arm = grade = lane** is one object written in four places
   (`rl_env.py:3529`, `tasks.py:11947`, the worker's `bin_index`, and the
   selector's grade-pure predicate at `:9251`). P114 splits it: the destination
   is a function of the fruit (`sort_destination`), the arm is a function of the
   destination (the capability map).
2. **the place target is derived from the place leg's *name***
   (`tasks.py:5032-5033` `index = 0 if "0" in name else 1`), so a `place1` *is*
   lane 1 and there is nowhere a "destination with its own target" can exist.
   P114 adds one indirection (`_place_xy_for`) at that site and the two
   diagnostic reads.

## 2. The validation

All cells are the shipped scripted two-line (P85/P87 clock, P71 geometry), one
claim per run, `[sort]` rows only when the instruction is armed. The endpoint is
the **ledger's assignment accuracy**, not the placed count.

| cell | knobs | placed | released | **in the instructed destination** | mis-sorted | refusals | gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| (i) shipped, default off | none | **8/10** | - | - | - | - | `fingerprint: matches`, `190: PASS` |
| (ii) today's routing as an instruction | `FRUIT_SORT_INSTRUCTION=today.txt` | **8/10** | 8 | **8/8 = 100 %** | 0 | 0 | `fingerprint: matches`, `190: PASS` |
| (iii-b) size-class rule | `FRUIT_SORT_INSTRUCTION=size40.txt` | 7/10 | 7 | **7/7 = 100 %** | 0 | 0 | budgets PASS (`|v|max` 0.114/0.160); fingerprint DIFFERS by construction |
| (iii-a) 3-destination cell | `FRUIT_SCENARIO=three_dest.json` + `three_dest.txt`, 20 attempts | 13/20 | 13 | **13/13 = 100 %** (dest 1 7/7, dest 2 6/6) | 0 | 0 | budgets PASS (`|v|max` 0.110/0.160) |
| refusal | `FRUIT_SCENARIO=tray_unreachable.json` + `tray.txt` | 0 | 0 | - | - | **1 (before any attempt)** | run aborts with `ScenarioError` |

**(i) byte-identity.** `logs/p114/accept_off.log` is **421/421 `[fruit]` lines
identical** to `logs/p110/accept_noharm.log` (same md5
`1ac8febefa45c3212ef7d4151613a318`), and the log contains **no `[sort]` and no
`[scenario]` row at all** - the unset path is the shipped code path, not a
disabled branch. `8/10`, `fingerprint: matches configs/motion_reference.json`,
`190: PASS`.

**(ii) the instruction that reproduces today's routing** (`grade=A => 0`,
`grade=B => 1`, `grade=C => skip`) is **byte-identical to (i)**: 421/421
`[fruit]` lines with the `[sort]` rows dropped
(`logs/p114/compare_off_vs_today.txt`), same `[stats]` (8/10, 89.9 s, 9.0
s/attempt) and the same `fingerprint: matches`. The compiled predicate is the
shipped grade-pure predicate, so the same fruit is selected by the same arm in
the same order; only the ledger rows are new. This is the strongest form of "the
instruction layer changes nothing when it says what the code already did".

**(iii-b) the size-class rule on the shipped geometry** (`size<40 => 1`,
`default => 0`): the coverage row reads `mapped=16 unassigned=0 skip=0
(dest0=12, dest1=4)` - 12 fruit go to the left lane and 4 (the small classes) to
the **right** - and the ledger's 7 releases land 7/7 in the instructed
destination, 0 mis-sorted. The arm carries fruit it would never have taken under
grade routing: a **grade-C strawberry (3.6 cm) travels to lane 1 on the right**
(attempt 1) and a **grade-A kiwi (5.4 cm) travels to lane 0** (attempt 9) - the
destination is independent of the grade, which is the requirement. The run is a
different attractor (7/10 vs the reference branch), so `190` fails on the
fingerprint **only**; the motion budgets pass (`|v|max` 0.114 against
0.160-0.161, lurch 0.018 against 0.291). No rate is claimed.

**(iii-a) the 3-destination cell**: the descriptor adds
`dest 2 = (0.38, +0.55)` on the +Y belt, `reach: auto`. The startup solve reads
**6.0 mm** against the 25 mm bar and the capability row moves from
`2:auto->pending` to `2:auto->reachable`; the left arm's map becomes
`[0, 2]`, the right's stays `[1]`. The instruction (`grade=A => 2`,
`grade=B => 1`, C unmatched) gives `coverage ... unassigned=4 (dest1=6,
dest2=6)`: the 4 grade-C fruit match no rule and are **never selected** (the
selector's own diagnostic names them; the ledger counts them as unassigned, not
as a guess). 20 attempts split 10/10 between dest 2 and dest 1; 13 releases land
**13/13 in the instructed destination, 0 mis-sorted**. The two destinations are
71 mm apart; the measured release clouds are ~78 mm apart and every release is
26-32 mm nearer its own target than the other (`nearest=2, dist=58-62 mm`
against ~90 mm to dest 0). The payload hangs ~(+50, +40) mm from the commanded
jaw point (the recorded tool-offset geometry), which is why the ledger
classifies the **payload** at the release, not the jaw.

**The refusal**: `tray_unreachable.json` adds `dest 3 = (1.65, +0.50)` (the
output tray) as `auto`. The solve reads **1138.3 mm** against the 25 mm bar,
prints `-> UNREACHABLE`, rebuilds the map without it, and `_refresh_sort_
capability` raises

```
[sort] REFUSED: the instruction maps a fruit to destination 3 (plus_y_tray,
side +y, reach auto) but no arm can deliver there
```

**before the first attempt** (`logs/20_pick_place_traceback.txt`). Zero
attempts, zero placements, zero mis-sorts. That is the required behaviour: an
unreachable mapping is rejected, not executed.

**What the fixed reach bar is** (stated so the reader does not over-read it):
25 mm is the live place leg's own `res_end` scale (13-34 mm, P90), not a
precision claim. The shipped lane reads 14.9 mm on P90's static map and is marked
`verified`, so it costs no solve; the new target reads 6.0 mm; the tray reads
1138 mm. The gap between "servable" and "not" is three orders of magnitude, so
the exact bar does not decide any cell here.

## 3. The design in one screen

`logs/p114/DESIGN.md`:

* **descriptor** (`FRUIT_SCENARIO=<path>`) - stations, pick/place, belt,
  destinations with physical `(x, y)` targets and a `reach` status
  (`verified` / `auto` / `unreachable`), supply band/mix/schedule, calibration
  tolerance. Applied at `SceneConfig.__post_init__` / `SupplyPlan.from_env`;
  stations become `run_bimanual`'s defaults; `auto` destinations are solved at
  startup. Strict loader: unknown keys/ids/schedules raise.
* **instruction** (`FRUIT_SORT_INSTRUCTION=<path|inline>`) - ordered
  `condition => destination` rules (`grade=A => 0`, `size<40 => 1`,
  `apple => 2`, `default => 0`, `skip`), first match wins, `default` last.
  Parsed and validated against the descriptor's destinations and the pool's
  grades/species; every refusal names the file and line.
* **capability map** - `left` only serves `+y`, `right` only `-y`, and only if
  the destination's reach is not refused. The selector admits a fruit only if
  its destination is in the carrying arm's map; the worker dispatches the
  fruit's own destination; `_run_impl` maps the destination back to the one arm
  that can serve it. The in-attempt arm/lane identity is therefore preserved as
  *physics* (a payload cannot cross to the other belt) while the *rule* is free.
* **degradation** - an attribute the cell lacks (colour) is refused; an
  unreachable destination is refused at startup; a fruit no rule covers is never
  selected. Grade/ripeness/defective are **labels drawn at spawn** in this sim,
  so the instruction layer is exact for species/size and a *labelling interface*
  for the rest until a real classifier feeds the same attribute dict.

## 4. The portability price

| | before P114 | after P114 |
| --- | --- | --- |
| new station / pick / belt | edit `assets.SceneConfig` + `run_bimanual`'s station defaults + re-solve | descriptor fields (the pre-pose re-solves itself) |
| new destination on an existing lane | edit `SceneConfig.output_place_*`, `jaw_target`'s name→lane rule, the driver's lane expression | one `destinations[]` entry with `reach: auto` |
| a new sorting rule | edit `rl_env.py:3529`, `20_pick_place.py:270`, `40_collect_demos.py:755`, `60_eval_policy.py:219` and the selector's grade predicate | one instruction file |
| new mix / band / schedule | `FRUIT_SUPPLY_*` (or code for a new schedule) | descriptor `supply` block |
| the gate | motion reference + `accept.sh` | the same + the ledger's assignment accuracy |

**Still not portable, and named**:

* a **new physical lane** (a third belt/tray body) is a scene build
  (`conveyor.OutputBelt`), not a descriptor field; the descriptor can add a
  target *on* an existing lane (which is what dest 2 is);
* a destination at a **different height** needs a per-destination `z` and its own
  descent (not built);
* the **tactile/force channels** are hand-specific (`tactile.py`, the per-pad
  readers) and are not part of the descriptor;
* **colour** and any vision-derived attribute: the sim has no per-instance
  colour measurement (`CATEGORY_STYLE` is a per-category constant), and
  grade/ripeness/defective are drawn labels - a real cell needs a classifier;
* the **end effector's own limits** (`docs/END_EFFECTOR_DECISION.md`) are
  untouched by this phase - portability of the software does not widen the
  hand.

## 5. Verdict

**The software architecture is portable and the instruction layer works; no
default is flipped.** The shipped cell is byte-identical when both knobs are
unset (421/421), an instruction that restates the shipped routing is
byte-identical to the un-instructed run (421/421), a size-class rule routes
across the grade (7/7 in-destination), a third destination on an existing lane
is solved and used (13/13 in-destination), and an unreachable target is refused
before the first attempt (1138.3 mm -> refused). The price of a new pipeline is
a JSON + a solve + one gate; a new physical lane/hand/camera is still hardware.

**Named next steps** (not built):

1. **A vision attribute source** - a classifier that emits
   `{species, grade, size, ripeness, colour}` per fruit; the instruction parser
   already refuses `colour` rather than guessing, so the interface is defined.
2. **A second place height / a third belt** - if a real pipeline needs it, the
   descriptor needs a per-destination `z` and the scene needs the body; that is a
   station/scene phase with both references and every store re-baselined.
3. **The direct/policy dispatcher** - the scripted cell is covered; the policy
   loop still selects and places through its own grade lane and refuses the
   instruction (by design). Threading the ledger through the primitive handover
   is the policy-side version of the same design.
4. **An overlap station** - a station where both arms' place targets overlap
   would let one destination be served by either arm (the capability map would
   have two entries); P90 measured the shipped place point at the corner of the
   solvable box, so this is a workstation change.

## 6. Files and pins

`src/fruit_sorting/scenario.py` **674194fe** (new: descriptor loader, instruction
parser/resolver, capability map); `tasks.py` **15d2348a** (the ~20 hooks:
`_place_xy_for`, `_calibrate_sort_destinations`, `_sort_admits`,
`_arm_for_destination`, `_sort_ledger_*`, the thread-local attempt context, the
worker dispatch, the `auto` solve); `assets.py` **165328af** (descriptor
geometry); `fruits.py` **e807216c** (descriptor supply defaults);
`rl_env.py` **476d5782** (`TASKS_MD5` follow + the scripted-only refusal);
`scripts/20_pick_place.py` **986d726d** (single-arm destination + ledger);
`scripts/40_collect_demos.py` **65683b8f**; `scripts/60_eval_policy.py`
**22ca84f2** (refusal); `scripts/selfcheck.sh` **c833520f**;
`scripts/259_p114_scenario_selftest.py` **fd6afd02** (39 checks) and
`scripts/260_p114_instruction_selftest.py` **a537cf09** (19 checks).
Descriptors: `configs/scenarios/shipped_twoline.json` **290b8a0a**,
`logs/p114/scenarios/three_dest.json` **35707bf3**,
`logs/p114/scenarios/tray_unreachable.json` **2ebb722e**. Instructions:
`logs/p114/instructions/{today,size40,three_dest,tray}.txt`. Reports:
`logs/p114/p114_report.py`, `run_p114.sh`, `compare_off_vs_today.txt`,
`ledger_accept_{today,size40,three_dest}.txt`, `refusal.txt`,
`accept_*.{log,driver}`, `accept_{size40,three_dest}.budgets`.

`scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new `P114
scenario descriptor` and `P114 sort instruction` legs; `scripts/106_index_audit.py` OK;
`scripts/107_collect_merge_test.py` PASS; references
`configs/motion_reference.json` = `configs/motion_reference_twoline.json` =
**`30fb99f8`** and `configs/motion_reference_single.json` = **`8952c320`** stand.
