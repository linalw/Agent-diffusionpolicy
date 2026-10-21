### P30-B (2026-10-21, branch `p-supply`, `logs/p30b/`): the HOME-HUB flow - the carry/place is already programmatic, so the hub is a structural 0.5-0.7 s lever and the model's cost is the approach, not the carry; built default-off and offline-verified, the simulator measurement is owed to the P30-A lane

**The directive** (owner, in substance): after a grasp the arm should return to a
default pose, and from there reach the place point rapidly; after placing, return
to the default pose; on failure return and re-plan - "many programmatic steps -
can this accelerate sorting and reduce the model's inference cost?"

**The finding that decides the design.** The carry and the place are *already*
programmatic on every path: `_carry` is a jerk-limited Cartesian profile with the
kinematic pads leading, and `grasp_carry_place` is entered once per attempt and
contains the seat/close/lift/place/release. No `policy.act` is called between the
handover and the release on the hybrid path (`_run_primitive` calls the primitive
and the episode ends inside it) or on the direct path. The demo `[cycle]` mass
base is prepose 0.71 + hover 0.8 + descent 3.1-3.6 + close 1.2 + grip 1.7-5.4 +
lift 1.7-2.2 + place 2.4 + release 2.3 + return 0.5-0.7 = ~15.3 s, and every leg
is scripted; the only model in the loop drives the approach. So the owner's
architecture already holds, and the *inference* question is about the approach
(hybrid `APPROACH_STEPS=400` -> <=100 chunks at `execute_steps=4`, each a 16-step
DDIM chain = <=1,600 UNet forwards; the direct env's `logs/p28/probe_A.log`
rows: `decision=490` on its success -> 123 chunks, `decision=536-541` on the
close-and-drop failures -> 134-136, `decision=1235-1395` on no-fires -> 309-349). The carry/place's model share is zero.

**Two hubs, because one pose cannot do both** (measured geometry:
`belt_top=1.17`, `output_belt_top_z=1.35`, OpenArm fingers ~0.08 below the jaw
centre): the *carrying* hub is `grasp_lift` (jaw 1.45/1.53, underside 1.37/1.45 -
clears the output belt; it is where the shipped line already carries the payload
after the grasp and where the place leg departs) and the *waiting* hub is `ready`
(jaw 1.37, underside ~1.29 - a carried payload would sit inside the output belt;
it is the between-attempt `go_ready` target). The shipped line already uses both
poses; P30-B names the state machine and makes the return part of the attempt.

**Built** (`FRUIT_HOME_HUB=1`, default 0; single-arm scripted scope only - no
`_active_session`, no `FRUIT_BIARM_TWOLINE`): `home_hub_enabled`, `_hub_return`
(the measured staged `ready` transit `go_ready(side)`, 295-299 ticks, bracketed
for its duration), `_hub_report` (one `[hub]` row: `carry_in`, `hub_to_place`,
`place_to_hub`, `infer`, `at_hub`), and in `_grasp_carry_place_impl` the hub
marks plus (a) the success tail `if hub: <return> elif retreat > 0: <shipped>
else: <shipped settle>` and (b) the failure branch inside `if not
result.grasped:`; the 60-tick retreat is subsumed by `_lift_clear`'s 0.20 m lift.
`note_result` subtracts `hub_return_s` from the span so `[stats] s/attempt` keeps
its meaning (otherwise the moved transit would read ~2.5 s slower while the cell
is faster). `20_pick_place.py` skips its post-attempt `go_ready` on `at_hub`, so
the hub does not depend on `FRUIT_READY_SKIP=1` (it is a no-op there anyway; with
the knob off it would hold ready for 210 more ticks). `rl_env.py` adds the
inference counter at the single `policy.act` site (+ RTC chunks), publishes it to
the task before `grasp_carry_place`, adds `policy_inferences` to the outcome, and
follows the pin. No two-line hub (park gate/station/arbiter), no policy wait
gate (separate pre-registration), no `runtime.py` change.

**Expected timing**: -0.50 to -0.70 s per successful attempt (the removed
`[cycle] return` segment, 3.3-4.6 % of 15.31 s) and 0 s on failures (the failure
arm already ends at the carrying hub; the transit is the same one the driver
ran). The Cartesian reverse of the place corridor is the named follow-up
(~0.8 s/attempt, 5 %) and needs its own reach/clearance probe; a hub *off* the
corridor would add ~1.5 s of travel and two stops and is rejected by arithmetic.

**Verification (offline only; P30-A holds the simulator)**: `py_compile` on the
four sources; `scripts/selfcheck.sh` PASS 0 failures; the new stub
`logs/p30b/check_home_hub.py` PASS 40 checks - the knob truth table (exec'd real
predicate), the default-off statement identity vs `e1b9936` (every base statement
survives; the single changed container is the extended `if not result.grasped:`
block; the shipped retreat/settle branch is AST-identical and is the hub `if`'s
`orelse`), every P30-B statement dominated by `if hub:`, the leg ordering, the
failure path, the row executed with synthetic marks, the counter/pin chain and
the two-hub geometry. `[hub]` row example (from the stub's execution of the real
printer): `[hub] attempt 4 flow=ok arm=left carry_in=1.00s hub_to_place=2.00s
place_to_hub=2.50s infer=7 placed=1 at_hub=1`.

**Pins**: `tasks.py` `e27b18a455b2094aa611b36fd6cec168`, `rl_env.py`
`59150f857c417eddd7b22f5adaf3e507` (`TASKS_MD5` follow
`b54b54064607c50f7ed0adc906c97a45` -> `e27b18a4...`), `20_pick_place.py`
`798e71132100bfcc3dc7816a33381109`, `check_home_hub.py`
`85c49461864ed1b61bfb0c92f2447f4e`; base commit `e1b9936`. No config, dataset,
checkpoint, scene/asset/conveyor or collector change.

**Owed (next simulator block, after P30-A)**: the ten-attempt `FRUIT_HOME_HUB=0`
vs `=1` cycle pair at one seed (confirm -0.5 to -0.7 s in `[stats] s/attempt` and
the `[hub]` legs), the hub-off acceptance fingerprint, the Cartesian-return
reach probe, then the wait-gate pre-registration on the direct interface (N=5
paired; endpoints: model calls and the fire-timing classes). The hub-enabled
collector store would be a different branch - the collector manifest has no
`home_hub` field and the collector is out of this lane's write scope - so the
knob stays off for collection.
