# P30-B - the HOME-HUB control flow

Status: **implemented, default off, offline-verified** (Tier C). No simulator run
in this lane: the scene lane P30-A owns the running simulator, so every number
below is either read from the existing logs or derived from the code's own
cadence. The one open item is the simulator measurement (section 7).

The owner's directive, in substance: *grasping being slow is understandable, but
after a successful grasp the carry-to-place can be programmatic to save time:
after a grasp the arm quickly returns to a DEFAULT pose; having acquired a
target it grasps; on success it brings the fruit back to the DEFAULT pose, then
from the DEFAULT pose it rapidly reaches the PLACE point; after placing it
immediately returns to the DEFAULT pose; on failure it also returns to the
DEFAULT pose and re-plans. Many programmatic steps - can this accelerate sorting
and reduce the model's inference cost?*

---

## 1. The finding first: the carry and the place are already programmatic

This decides what a "hub" can and cannot buy, so it is stated before the design.
In the current tree the model never drives the carry or the place, on any path:

| path | who drives the approach | who drives seat -> close -> lift -> place -> release |
| --- | --- | --- |
| scripted single arm (shipped) | nobody (the scripted catch) | `grasp_carry_place` (programmatic) |
| bimanual shared station / two-line | nobody (the scripted catch) | `grasp_carry_place` (programmatic) |
| hybrid policy handover (`60_eval_policy --hybrid`) | the policy, for at most `FRUIT_APPROACH_STEPS=400` control ticks | `grasp_carry_place` (programmatic) |
| direct policy (`110_rl_rollout --presentation direct`) | the policy until its own close | `grasp_carry_place` (programmatic) |

The carry is `PickAndPlaceTask._carry` (`src/fruit_sorting/tasks.py`): a
jerk-limited Cartesian profile (`TrajectoryLimits`, `jerk_limited`, friction-cone
clip while a payload is held) to a named waypoint (`grasp_lift`, `place{0,1}`),
with the kinematic pads leading the arm. The place is the same primitive to the
known drop point (`cfg.output_belt_drop_points`). No `policy.act` is called
between the handover and the release - `_run_primitive` calls
`grasp_carry_place` once and the episode ends inside it.

So the owner's premise holds for the *architecture the code should have*, and the
code already has it. **The model's inference cost is the approach/wait, not the
carry.** Any claim that a hub reduces the model cost has to come from gating the
*approach*, not from moving the carry (section 6).

What the shipped cycle therefore looks like, from the `[cycle]` report
(`FRUIT_CYCLE_REPORT=1`; AGENTS.md's mass base and a logged success row):

| segment | AGENTS mass base | logged row (attempt 18) | who |
| --- | --- | --- | --- |
| prepose | 0.71 s | 0.71 s | programmatic (blend to the grasp configuration) |
| hover | 0.8 s | 0.72 s | programmatic |
| descent | 3.1-3.6 s | 3.35 s | programmatic (arrival-synchronised catch) |
| close | 1.2 s | 1.62 s | programmatic (policy decides *when* on the direct path) |
| grip | 1.7-5.4 s | 1.81 s | programmatic |
| lift (`grasp_lift`) | 1.7-2.2 s | 1.85 s | programmatic |
| place | 2.4 s | 2.32 s | programmatic |
| release | 2.3 s | 2.27 s | programmatic |
| return | 0.5-0.7 s | 0.67 s | the 60-tick retreat (programmatic) |
| **total** | | **15.31 s** | |

Between attempts the driver calls `task.go_ready()`: a staged `ready` transit
measured at **295-299 ticks = 2.46-2.49 s** (`[ready] catch_up=40 lift=45-49
blend=90 settle=120`, `logs/p9a`), plus the 30-tick feed pump (`advance(30)`).

So the "default pose" already exists twice in the code: `grasp_lift` is where the
payload goes after the grasp (the place leg departs from it), and `ready` is
where the arm waits between attempts. The hub is an *explicit* state machine over
those two poses, not a new motion primitive.

---

## 2. The two hubs, and why one pose cannot serve both

Geometry, from `configs/waypoints.json` + `assets.SceneConfig`
(`belt_center=(0.34,0,1.14)`, `belt_size_z=0.06` -> `belt_top=1.17`;
`output_belt_top_z=1.35`; the OpenArm fingers hang ~0.08 m below the jaw centre,
the `FRUIT_OPENARM_TRANSFER_LIFT` default):

| pose | jaw z | hand underside | clears the output belt top? | role |
| --- | --- | --- | --- | --- |
| `ready` | 1.37 | ~1.29 | **no** | waiting hub (empty hand) |
| `grasp_lift` | 1.45 / 1.53 (OpenArm +0.08) | 1.37 / 1.45 | yes | carrying hub |

A single hub at `ready` would drag a carried payload through the output belt
(its underside is 6 cm below the belt top); a single hub at `grasp_lift` would
park the empty arm 0.36-0.44 m above the pick station, which is where the next
fruit has to arrive. The shipped solution is already the two-pose one. P30-B
names it, bounds it, and makes the return part of the attempt.

```
                 acquire (scripted catch or policy)
   waiting hub  ─────────────────────────────────►  grasp
   (ready)                                            │
      ▲                                               │ close
      │                                               ▼
      │                                          carrying hub
      │                                          (grasp_lift)
      │                                               │
      │                                               │ place leg (programmatic)
      │                                               ▼
      └──────────── release ◄──────────────────────  place
                    │
                    └── failure (not grasped): from the carrying hub directly
```

---

## 3. The implemented flow (single-arm scripted line)

`FRUIT_HOME_HUB=1`, default **0**. Resolution:
`PickAndPlaceTask.home_hub_enabled(scripted)` - true only for the single-arm
**scripted** line (no `FRUIT_BIARM` session, no `FRUIT_BIARM_TWOLINE`). The
predicate is the only new env read; unset/`=0` returns on the first line.

### Legs and code sites

1. **acquire** - unchanged. `_run_impl`: pre-pose/hover/descent/close, then
   `grasp_carry_place(..., scripted=True)`.
2. **grasp -> carrying hub** - the existing `_carry(arm_name, sample,
   "grasp_lift")` leg. Under the knob it records `hub_marks["hub_carry"]` at its
   end (the acquire -> hub boundary). No motion change.
3. **carrying hub -> place** - the existing `_carry(arm_name, sample,
   f"place{bin_index}")` leg, unchanged; `hub_marks["hub_place"]` at its end.
4. **release** - unchanged (relax, dwell, pad ramp, finger ramp; `_place_low`
   still runs).
5. **place -> waiting hub** - new: `_hub_return(arm_name)` replaces the 60-tick
   retreat/settle block and runs *inside* the attempt. It calls `go_ready(side)`,
   i.e. the exact measured between-attempt transit (open the gripper, staged
   `ready` transit, `FRUIT_READY_SETTLE` tail, `_recover_ready`). The 60-tick
   retreat is subsumed: `_lift_clear` raises the hand 0.20 m and to at least
   `belt_top + 0.30` before the blend, which is more clearance than the retreat.
   `hub_marks["hub_wait"]`, `result.at_hub = True`,
   `result.hub_return_s = <the transit's seconds>`.
6. **failure (not grasped)** - new: the arm is already at the carrying hub (the
   `grasp_lift` leg just ran), so `_hub_return` runs before the early return, and
   the next attempt re-plans from the waiting hub. Same `at_hub` /
   `hub_return_s` / row bookkeeping. The two carry-monitor fast-skip paths
   (`FRUIT_CARRY_MONITOR`, P7-2b/P10-C safety stops) deliberately keep their
   shipped early return: they are "stop and let the harness park" paths, and the
   monitor is a separate default-off lever.

The driver's post-attempt `task.go_ready()` is skipped when `result.at_hub`
(`scripts/20_pick_place.py`), so the hub does not depend on
`FRUIT_READY_SKIP` being on. With the skip default (`=1`) the call is a
2-joint-read no-op anyway; with `FRUIT_READY_SKIP=0` it would hold the ready pose
for another 210 ticks (1.75 s), which the explicit guard removes.

### What stays model-driven vs programmatic

| stage | P30-B owner | note |
| --- | --- | --- |
| arrival/handover timing | **model** on the direct/hybrid path; scripted catch on the shipped line | unchanged by the hub |
| the close decision | **model** (direct) / scripted | unchanged |
| grasp->hub, hub->place, place->hub, failure->hub | **program** | `_carry` / `_hub_return`, no `policy.act` |
| release | program | unchanged |
| re-plan after a failure | program (return to the hub) + the next attempt's selection | unchanged selection logic |

The hub's model boundary is therefore: **the model owns the acquire only; the
program owns everything from the grip to the next acquire.** On the shipped line
that boundary already exists; the hub makes the return part of it (before
`note_result`), so the collector and the drivers see the same post-condition.

---

## 4. The diagnostic row

One `[hub]` line per contact attempt, only under `FRUIT_HOME_HUB=1` (pure
reporting: two `SimulationManager` time reads per boundary, the non-invasive
class of AGENTS section 2):

```
[hub] attempt 4 flow=ok arm=left carry_in=1.00s hub_to_place=2.00s place_to_hub=2.50s infer=7 placed=1 at_hub=1
[hub] attempt 4 flow=fail arm=left carry_in=1.00s hub_to_place=- place_to_hub=- infer=n/a placed=0 at_hub=1
```

(the two rows are the stub's execution of the real `_hub_report` with synthetic
marks). `carry_in` = grasp -> carrying hub, `hub_to_place` = carrying hub ->
place, `place_to_hub` = release -> waiting hub, `infer` = the model's action
chunks for the attempt (`n/a` when no model ran), `at_hub` = the attempt ended at
the waiting hub.

The model count is published by `SortingRLEnv`: `_infer_calls` increments at the
single synchronous sampling site (`policy.act` in `sample_chunk`), the RTC
chunker's `chunks_sampled` is added, `_run_primitive` copies it to
`task.policy_inference_calls` before `grasp_carry_place`, and the outcome dict
gains `policy_inferences`. One call = one DDIM chain = `ddim_steps` denoising
steps (16 by default).

**Accounting trap, handled.** Moving the between-attempt transit inside the
attempt would book it in `result.sim_span`, so `[stats] s/attempt` would read
~2.5 s *slower* while the cell is faster. `note_result` subtracts
`result.hub_return_s` from `sim_end` (only when non-zero, so the default path is
untouched), and the `[hub]` row / `[cycle] return` segment still report the leg in
full. The comparable end-to-end metric stays `[stats] sim_time / attempts`.

---

## 5. Expected timing

Per **successful** attempt, with the shipped transit:

| item | value | source |
| --- | --- | --- |
| removed: the `[cycle] return` segment (the 60-tick retreat) | **0.50-0.70 s** | AGENTS mass base; logged 0.67 s |
| added: none (the hub return is the transit the driver already ran) | 0 s | `go_ready` 295-299 ticks both ways |
| moved: the 2.46-2.49 s return from the between-attempt gap into the attempt | 0 s net | `[ready]` logs |
| **net per success** | **-0.50 to -0.70 s** | 3.3-4.6 % of 15.31 s |

The post-grasp leg itself (1.7-2.2 s) is not a hub choice: it is the existing
`grasp_lift` carry, speed-capped by the grip's friction cone (0.18 m/s indexed,
0.30 m/s dynamic). Making *that* faster is the grip work (W8-B/R6-B), not this
flow; the hub only fixes where the arm goes after it.

Per **failure** (not grasped): the arm already ends at the carrying hub, and the
waiting-hub return is the same transit the driver ran. **Net 0 s**; the value is
structural (the collector and non-`20_pick_place` consumers get the
post-condition without their own `go_ready`).

A Cartesian reverse of the place corridor (no payload, same 45-49 cm, at the
`FRUIT_DYNAMIC_PLACE_VMAX=0.35` limit instead of the staged joint transit) is the
named follow-up: its profile is ~204 ticks (1.7 s) against 295-299, i.e. another
**~0.8 s/attempt (5 %)**. It is **not** implemented: it is a new corridor and
needs its own reach/clearance probe (section 7).

What would *not* pay: a new hub off the grasp->place corridor. A hub 0.3 m off
the line adds two ~0.3 m legs at 0.35 m/s plus two full stops (jerk-limited,
v/a ~ 0.32 s per stop), i.e. **~1.5-2.2 s**, which swamps the 0.5 s the return
saves. The measured place leg
is distance-proportional (45.5-48.5 cm at ~6.6 ticks/cm, P3), so total distance
is conserved; a hub only pays if it lies on the corridor or removes a staging
step.

### The inference delta

Cadence, from the code: `execute_steps=4` -> one chunk per 4 control ticks (30
chunks/s of simulated time); each chunk is one `PolicyRunner.act`, i.e. a
`ddim_steps=16` DDIM chain = 16 UNet forwards.

| loop | model calls per attempt | UNet forwards | carry/place share |
| --- | --- | --- | --- |
| hybrid canary (`60_eval_policy --hybrid`, `APPROACH_STEPS=400`) | <=100 chunks | <=1,600 | **0** (the primitive owns ~9-13 s of the episode) |
| direct env, a logged success (`110_rl_rollout`, `decision=490`) | 123 chunks | 1,968 | 0 |
| direct env, close-and-drop failures (`decision=536-541`) | 134-136 chunks | 2,144-2,176 | 0 |
| direct env, no-fire failures (`decision=1235-1395`) | 309-349 chunks | 4,944-5,584 | 0 |

**The hub does not change any of these numbers**, because it does not touch the
approach. The lever that would is a deterministic wait gate: park at the waiting
hub and do not sample the policy until the fruit is inside the acquire window
(the trigger/lead the scripted line already computes). Then the model's cost is
the acquire only - the same ~490 ticks on the success it does fire on (no
gain), but 0 instead of ~330 chunks on the no-fire class. That is a closed-loop change with an
OOD risk (section 6) and is a separate pre-registration, not this lane.

---

## 6. Risks, ranked

1. **The throughput claim is small** (0.5-0.7 s, 3-5 %), because the carry/place
   was already programmatic. Do not present the hub as a step change; the big
   programmatic legs are the descent (3.1-3.6 s), grip (1.7-5.4 s) and place
   (2.4 s), and the first is the documented conveyor-boundary item AGENTS says
   not to re-tune.
2. **The inference saving needs the wait gate, not the hub.** The gate changes
   *when* the policy starts, i.e. its fire timing - the exact channel the W4/W7-B/
   W8-A work measured as the fragile one. Pre-register it as an A/B on the direct
   interface with the same N=5 paired protocol; do not fold it into this knob.
3. **Two-line and shared-station park invariants.** Excluded by scope. The
   two-line's `_biarm_park` is already a hub-like return, but it is coupled to
   the park gate (`FRUIT_BIARM_PARK_EARLY`), station ownership and the
   arbiter's one-tick cadence; an in-attempt hub return there would land inside
   the gate window and needs the W2/W6 clearance battery, not a rename.
4. **Collector data distribution.** With the knob on, the last 0.5-0.7 s of every
   recorded episode is the hub return instead of the retreat, and the collector's
   manifest has no `home_hub` field (the collector is out of this lane's write
   scope). A hub-enabled store is therefore a different branch and must not be
   merged with the shipped stores. The knob stays off for collection.
5. **The settle tail is inherited.** `_hub_return` uses the shipped
   `FRUIT_READY_SETTLE=120`; trimming it (the remaining ~0.8 s) is unmeasured and
   moves the residual at the next pre-pose. Its A/B is `FRUIT_READY_SETTLE` on
   the hub branch, not a new knob.
6. **The failure path's hand state.** `_hub_return` opens the robot's fingers
   (as `go_ready` does). The coherent pad hand's `_closed_gap` is cleared at the
   next attempt's `park()`, not here, so the hub's failure return is de facto
   scoped to the scripted OpenArm line. Stated in the predicate's docstring.
7. **The span accounting** (fixed): see section 4. Without the subtraction an
   A/B would read a 2.5 s slowdown.

---

## 7. Verification, and what still needs the simulator

Offline (this lane, `logs/p30b/check_home_hub.py`, 40 checks, PASS):

* the knob truth table over `FRUIT_HOME_HUB` x scripted x session x two-line
  (only the single-arm scripted row with `=1` is on);
* the default-off statement identity against `e1b9936`: every base statement of
  `_grasp_carry_place_impl` survives, one container (the `if not
  result.grasped:` block) is extended, zero rewritten; the shipped
  retreat/settle branch is the hub `if`'s `orelse` and is AST-identical to the
  base commit;
* every P30-B statement (`hub`, `hub_marks`, `at_hub`, `hub_return_s`, both
  `[hub]` rows) is dominated by `if hub:`, so the knob-off path cannot print or
  read extra simulation time;
* the leg ordering and the failure path by source line order;
* the row executed with synthetic marks (both flows), and the driver's
  `at_hub` guard;
* the policy counter's single increment site, the RTC addition, the publish
  order, `policy_inferences`, and `TASKS_MD5 == md5(tasks.py)`;
* the two-hub geometry.

Also run here: `py_compile` on the four touched sources; `scripts/selfcheck.sh`
PASS (0 failures, motion budgets skipped - no run log). **No `accept.sh`, no
`accept_policy.sh`, no `demo_2min.sh`**: the scene lane P30-A holds the
simulator, and a second Isaac process collides (AGENTS section 1).

The simulator measurement this lane owes (next block, after P30-A releases the
simulator), in this order:

1. `FRUIT_CYCLE_REPORT=1 FRUIT_HOME_HUB=0` and `=1`, ten attempts each, same
   seed: confirm the `[hub]` legs and that `[stats] s/attempt` moves by
   -0.5 to -0.7 s (the subtraction makes the metric comparable), and that the
   `[cycle] return` segment becomes the 2.46-2.49 s hub transit while the
   between-attempt gap loses exactly that.
2. The no-harm it cannot prove offline: `FRUIT_HOME_HUB=0` acceptance
   (`scripts/accept.sh`) must be byte-identical to the current tree's record
   (fingerprint match is the tree-level check; the knob-off branch is the same
   statements by construction).
3. The Cartesian-return probe (`_lift_clear` vs a reverse place profile from the
   post-release pose): reach, clearance and the joint-step gate, before any
   timing claim.
4. The wait-gate pre-registration (separate): direct interface, N=5 paired,
   model-calls endpoint plus the fire-timing classes.

---

## 8. Files

* `src/fruit_sorting/tasks.py` - `EpisodeResult.at_hub` / `.hub_return_s`;
  `home_hub_enabled`, `_hub_return`, `_hub_report`; the hub marks and branches in
  `_grasp_carry_place_impl`; the `note_result` span correction.
* `src/fruit_sorting/rl_env.py` - the inference counter (`_infer_calls`,
  `inference_calls()`), the publish in `_run_primitive`, `policy_inferences` in
  the outcome, and the `TASKS_MD5` pin.
* `scripts/20_pick_place.py` - the `at_hub` guard on the post-attempt
  `go_ready`.
* `logs/p30b/check_home_hub.py` - the offline stub.
* `logs/p30b/IMPLEMENTATION.md`, this file, `WORKLOG_ENTRY.md`.
