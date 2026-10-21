# P30-B implementation - the HOME-HUB flow (default off)

Branch `p-supply`. Base commit `e1b9936`. No simulator run: the scene lane
P30-A holds the simulator and AGENTS section 1 forbids a second Isaac process.
Everything below is `py_compile`, `scripts/selfcheck.sh` and the new offline
stub over the real sources.

## 1. What changed

| file | md5 | change |
| --- | --- | --- |
| `src/fruit_sorting/tasks.py` | `e27b18a455b2094aa611b36fd6cec168` | the hub flow + the diagnostic + the span accounting |
| `src/fruit_sorting/rl_env.py` | `59150f857c417eddd7b22f5adaf3e507` | inference counter + `TASKS_MD5` pin follow |
| `scripts/20_pick_place.py` | `798e71132100bfcc3dc7816a33381109` | `at_hub` guard on the post-attempt `go_ready` |
| `src/fruit_sorting/policy/runtime.py` | `379ac7064fd49df8417e94dbf6ed2616` | **unchanged** (the counter lives at the env's call site) |
| `logs/p30b/check_home_hub.py` | `85c49461864ed1b61bfb0c92f2447f4e` | the offline stub |

The full diff is `logs/p30b/10_diff.patch` (366 lines, three files). No config,
dataset, checkpoint, scene, asset, conveyor or collector file is touched.

### `tasks.py`

* `EpisodeResult.at_hub: bool` and `EpisodeResult.hub_return_s: float` - the
  attempt ended at the waiting hub, and how long the return leg took.
* `PickAndPlaceTask.policy_inference_calls: int | None` - published by the RL
  env before the primitive; read only by the row.
* `home_hub_enabled(scripted=True)` - the only new env read
  (`FRUIT_HOME_HUB`, default `0`), plus the single-arm scripted scope predicate
  (no `_active_session`, no `two_line_enabled()`, `scripted=True`). Returns on
  the first line when unset.
* `_hub_return(side)` - `go_ready(side)` with a sim-time bracket; returns the
  seconds spent. This is the measured staged `ready` transit, not a new profile.
* `_hub_report(result, flow, marks)` - the `[hub]` row (format in section 4).
* `_grasp_carry_place_impl`:
  * `hub = self.home_hub_enabled(scripted)`, `hub_marks = {}` at the top;
  * `hub_marks["grasp"]` after the grip mark, `["hub_carry"]` after
    `_carry("grasp_lift")`, `["hub_place"]` after `_carry("placeN")`;
  * the failure branch `if hub:` (inside `if not result.grasped:`) returns to
    the hub and emits `flow=fail`;
  * the success tail is `if hub: <return> elif retreat > 0.0: <shipped>
    else: <shipped settle>`; the shipped branches are AST-identical to the base
    commit;
  * the success row is emitted after `result.placed` is computed.
* `note_result` subtracts `hub_return_s` from `sim_end` (only when non-zero) so
  `[stats] s/attempt` keeps its shipped meaning.

### `rl_env.py`

* `_infer_calls` per episode: `+1` at the single synchronous `policy.act` site
  (`sample_chunk`), zeroed in `__init__` and `reset`.
* `inference_calls()` adds the RTC chunker's `chunks_sampled` (0 when off).
* `_run_primitive` publishes `task.policy_inference_calls` immediately before
  `grasp_carry_place`; `reset` clears it to `None`.
* `_finalize` adds `"policy_inferences"` to the outcome dict (no change to the
  `[rl] episode` line, so `113_rl_report.py` is unaffected).
* `TASKS_MD5` follows the new `tasks.py`
  (`b54b54064607c50f7ed0adc906c97a45` -> `e27b18a455b2094aa611b36fd6cec168`).

### `20_pick_place.py`

One guard: `if not getattr(result, "at_hub", False): task.go_ready()`. With
`FRUIT_READY_SKIP=1` (default) the call was already a 2-joint-read no-op; the
guard makes the hub independent of that knob (`FRUIT_READY_SKIP=0` would
otherwise hold the ready pose for 210 more ticks). The bimanual batch path and
the startup call are unchanged.

## 2. Default-off (byte-inert) argument

`FRUIT_HOME_HUB` unset -> `home_hub_enabled` returns `False` on its first line.
Under that:

* the only executed new statements are `hub = ...` and `hub_marks = {}` (a bool
  and an empty dict); every other P30-B statement is inside `if hub:` (the stub
  proves this by AST domination - `hub` assignment, 5 `hub_marks` writes, the
  `at_hub`/`hub_return_s` writes, both `_hub_report` calls);
* the success tail evaluates `if hub` (False) then the shipped
  `elif retreat > 0.0:` / `else:` bodies. Those bodies are AST-identical to the
  base commit's; the stub checks the multiset of base statements and the exact
  `orelse` node;
* no `[hub]` row, no extra `_sim_time()` read (the hub marks are guarded), no
  change to `sim_end` (`hub_return_s == 0`), no change to the driver's
  `go_ready` (`at_hub` False);
* `rl_env` reads none of the new counter except to increment a Python int at a
  site it already visits.

The intended remaining proof is the tree-level acceptance fingerprint
(`scripts/accept.sh`) once the simulator is free; the statement identity above
is the offline stand-in.

## 3. Verification run here

```
$ python3 -m py_compile src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
      scripts/20_pick_place.py src/fruit_sorting/policy/runtime.py \
      logs/p30b/check_home_hub.py        # exit 0  (logs/p30b/40_compile.txt)

$ scripts/selfcheck.sh
... all 22 checks PASS, motion budgets SKIP (no run log)
PASS: 0 failures, 1 skipped         # logs/p30b/30_selfcheck.log
```

`selfcheck.sh` does not have a P30-B leg: `scripts/selfcheck.sh` is outside this
lane's write scope, so the stub is **not registered**. Run it directly:

```
$ python3 logs/p30b/check_home_hub.py
PASS: all checks                     # logs/p30b/20_stub.txt
```

The stub's layers (40 checks):

1. **Knob resolution** - the real `home_hub_enabled`, extracted by AST and
   exec'd, over `FRUIT_HOME_HUB` (unset/0/1) x scripted (T/F) x session (none/
   object) x two-line (F/T): exactly one enabled row.
2. **Default-off statement identity vs `e1b9936`** - every base statement of
   `_grasp_carry_place_impl` survives; the one changed node is the
   `if not result.grasped:` container, extended by the hub branch (its children
   survive); the shipped retreat/settle branch is the hub `if`'s `orelse` and is
   AST-identical to the base.
3. **Leg ordering** - `grasp_lift` -> `hub_carry` -> `place` -> `hub_place`, and
   `release` -> hub return -> `hub_wait` -> `return` mark; the success row after
   `result.placed`.
4. **Failure path** - the hub return, the `at_hub` write and the `flow=fail` row
   are inside `if not result.grasped:` and before `return result`.
5. **The row** - executed with synthetic marks: the success layout
   (`carry_in=1.00s hub_to_place=2.00s place_to_hub=2.50s infer=7 at_hub=1`) and
   the failure layout (`-` legs, `infer=n/a`); the driver's `at_hub` guard.
6. **The policy counter** - one increment after `policy.act`, two zero sites,
   the RTC addition, the publish before `self.task.grasp_carry_place(`, the
   `policy_inferences` key, and `TASKS_MD5 == md5(tasks.py)`.
7. **Hub geometry** - the carrying hub clears the output belt top with the
   hand's 8 cm drop, the waiting hub does not, both are calibrated waypoints.

## 4. The `[hub]` row

```
[hub] attempt 4 flow=ok arm=left carry_in=1.00s hub_to_place=2.00s place_to_hub=2.50s infer=7 placed=1 at_hub=1
[hub] attempt 4 flow=fail arm=left carry_in=1.00s hub_to_place=- place_to_hub=- infer=n/a placed=0 at_hub=1
```

`infer` is the RL env's action-chunk count (`n/a` when no model ran - the
scripted line; the direct/hybrid path publishes it). One chunk = one
`PolicyRunner.act` = `ddim_steps` (16) denoising steps; with `execute_steps=4`
that is one chunk per 4 control ticks.

## 5. What was not done, and why

* **No simulator run** (accept/canary/demo): collision with the P30-A scene lane.
  The owed measurements are listed in `HOME_HUB_DESIGN.md` section 7.
* **No `WORKLOG.md` edit**: the lane's write scope is the three source files,
  `policy/runtime.py` and `logs/p30b/`. The append-ready entry is
  `logs/p30b/WORKLOG_ENTRY.md`.
* **No selfcheck registration**: `scripts/selfcheck.sh` is out of scope; the
  stub is a one-command run and is written to be registrable there later
  (`run_check "home hub test" "$python" logs/p30b/check_home_hub.py`).
* **No two-line hub**: the two-line/shared-station scopes are excluded by the
  predicate (park gate, station ownership, shared-tick arbiter). The worker's
  `_biarm_park` is already a hub-like return; folding it in needs the W2/W6
  clearance battery.
* **No policy wait gate**: the model's inference cost is the approach, not the
  carry (design section 1/5). The gate is a separate pre-registration; the
  counter delivered here is its measurement hook.
* **No Cartesian return profile**: the named follow-up (~0.8 s/attempt) needs its
  own reach/clearance probe.

## 6. Blocker / next

Blocker: the simulator is held by P30-A, so this lane cannot measure the timing
delta (`[stats] s/attempt`, the `[hub]` legs, the fingerprint no-harm). The
offline work is complete and default-off, so it does not block P30-A.

Next (after the simulator frees, in order): the ten-attempt hub-off/hub-on cycle
pair at one seed; the hub-off acceptance fingerprint; the Cartesian-return
probe; then the wait-gate pre-registration (direct interface, N=5 paired).
