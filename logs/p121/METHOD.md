# P121 - METHOD: the direct/policy line decides its destination

## 0. The requirement, and the state it found

The owner's requirement is that the cell decide **where** each fruit goes from
an instruction. P114/P115/P116 built that chain for the scripted cell; the
direct/policy line refused it (`rl_env.py:1708-1716`, "FRUIT_SORT_INSTRUCTION is
scripted-only"), because the policy interface had no dispatcher: the **arm was
the grade was the lane**, fixed before the fruit was seen.

Every line below was read on the tree this phase started from (`tasks.py`
`0a703d1b`, `rl_env.py` `df148d84`) and re-read after the edit:

| site | before | after |
| --- | --- | --- |
| `rl_env.py` `_begin_pick` | `bin_index = 0 if grade == "A" else 1`; `active = "left" if bin_index == 0 else "right"` | `direct_dispatch(...)`: unset keeps that expression **byte for byte**; armed reads `task.sort_destination(target)` and `task.arm_for_destination(dest)` |
| `rl_env.py` `_goal` | `[fruit xyz, velocity, diameter, bin_index]` | unchanged shape; armed writes the instruction's destination as the last element (0/1 = the trained values, 2 = the declared OOD value) |
| `rl_env.py` `_apply` | 7 joint targets + 1 finger | unchanged - **no destination channel was invented** |
| `rl_env.py` `_run_primitive` | `task.grasp_carry_place(active, sample, bin_index, result)` | same call, plus the thread-local place target and the ledger **only when armed** |
| `tasks.py` `_place_xy_for` | already honours the thread-local `place_xy` override (P114) | unchanged; the direct env now sets it (`dispatch_destination`) |
| `tasks.py` `_run_impl` | `jaw_target` reads `_place_xy_for`, leg named `place{bin_index}` | unchanged; `sort_ledger_attempt` is the public form of the same two calls |
| `tasks.py` reselect block | recomputed the presented fruit's **grade lane** | armed: adopts only a presented fruit the **current arm** can deliver to, and re-points the place leg at its own destination; unarmed: the shipped text, unchanged |
| `rl_env.py` `_reseed_step` | `lane=int(self._bin_index)` (a grade lane) | armed: `lane=None` + the capability-arm check; unarmed: unchanged |

## 1. The wiring, in the order the loop runs it

1. **Selection.** `tasks.select_target` already has the instruction branch
   (P114): `sort_mode` replaces the grade predicate with `_sort_admits`, so a
   fruit is admitted iff its destination is not `skip`/unmatched and (for a
   lane-scoped caller) servable by that lane. The direct env calls it with
   `lane=None` - the single-arm form - so any **mapped** destination is
   admissible; the arm is chosen **after** selection, from the destination.
   `skip` and unmatched fruit are never selected.
2. **Arm.** `direct_dispatch` -> `task.arm_for_destination(dest)` -> the
   capability map (`scenario.instruction_against` / `capability_map`, left
   serves +y, right serves -y, `unreachable` refused, `auto` provisional). The
   arm is therefore a property of the destination, not of the grade.
3. **Goal.** `self._goal`'s last element is `float(bin_index)`: for the shipped
   two lanes it is `0.0` for a +Y fruit and `1.0` for a -Y fruit - the same
   value the grade lane produced - so T1's instructed run is the trained
   interface. A third destination writes `2.0`, a value the policy has never
   seen; that is stated, not assumed safe (see §3).
4. **Place.** `task.dispatch_destination(result, dest)` sets
   `self._sort_ctx.place_xy = (x, y)` (thread-local, per attempt),
   `result.destination`, `result.place_xy`; the place leg's `jaw_target` reads
   it through `_place_xy_for`. The leg is still named `place<destination>`, and
   `_place_xy_for(index)`'s shipped fallback (`output_belt_drop_points[index]`)
   is never reached while an instruction is armed. `clear_dispatch()` runs in a
   `finally`, so a failed attempt cannot leak a target into the next one.
5. **Ledger.** `task.sort_ledger_attempt(result)` = `_sort_ledger_coverage()`
   (once) + `_sort_ledger_row(result)` (per attempt). The row names the rule
   (`rule=`), the destination, the target, the arm, and - on a placed attempt -
   the payload's **measured release position**, `on_belt`, the nearest
   destination on that side, the distance and `in_dest`. This is the same code
   the scripted `run()` calls after its `finally`, so the two paths cannot
   diverge. The per-destination summary prints at run end
   (`report_summary` -> `sort_ledger_report`), as the scripted drivers do.
6. **Side paths.** The P4b2 presented-fruit adoption and the P38 reseed retry
   both re-derive the destination/arm under an instruction (the arm cannot
   change mid-attempt, so an unservable presented fruit is a refusal, not a
   cross-lane place). `carry_and_release` takes the destination target, because
   its shipped `output_belt_drop_points[bin_index]` is a two-lane index.

## 2. The scope, stated as code

* `FRUIT_SORT_INSTRUCTION` is **direct-only** in `rl_env`; the handoff
  presentation still refuses (it has its own grade lane, and no dispatcher).
* Unset: `_sort_armed` is False, `direct_dispatch` returns the shipped
  `(bin_index, arm)`, `_goal`/`_run_primitive`/`_finalize`/manifest take no new
  branch, and `[sort]` prints nothing. The selfcheck leg pins the expression.
* An instruction mapping to a destination **no arm serves** (an `unreachable`
  descriptor destination) raises at `_refresh_sort_capability` in the task's
  constructor - before the first attempt - exactly as P114's tray cell does.
* A destination **beyond the two shipped lanes** raises in the env unless
  `FRUIT_SORT_THIRD_DEST=1`; the message names the goal-channel reason.

## 3. The goal channel, stated not assumed

`bin_index` is an **input** to the policy, not an output: the action is 7 joint
targets + 1 finger. For destinations 0/1 the instructed value equals the lane
the arm will use, so T1 is in-distribution by construction. For destination 2
the value is `2.0`; the policy never saw it in `demos_v11`/`v12`/`v13s`, so T3
is an **OOD** cell: its fire rate is measured, and it is reported as such, not
quoted as a rate. The alternative (an extra action channel) was explicitly not
built: the action has no destination channel and P121 does not invent one.

## 4. Validation design

The direct loop is **not reproducible** (rendered frames; P37/P43/P54), so
nothing here is byte-identity and no rate is claimed. Four cells, 3 seeds x 10
episodes each, same direct configuration (the P66-phase-3/P71/P73-P77 cell
verbatim), same batch:

* **C** un-instructed control;
* **T1** today's routing as an instruction;
* **T2** a non-grade rule (`size<40 => 1`);
* **T3** the third destination (`logs/p114/scenarios/three_dest.json`,
  `FRUIT_SORT_THIRD_DEST=1`).

Endpoints: the ledger's `in_destination/released` per cell, the
per-destination table, the grade/arm/dest witness rows, the placed count
(report only), the failure classes, and the C cell's absence of any `[sort]`
row. The scripted acceptance is the no-harm proof; no motion budget is touched.

## 5. Tools

* `logs/p121/one_run.sh` - one cell (claim the simulator, the P77 harness env).
* `logs/p121/run_p121.sh` - the four cells, one session each, 3 seeds.
* `logs/p121/p121_report.py` - parses `[rl] episode`, `[sort] attempt`,
  `[sort] ledger`; `--check` enforces 0 mis-sorts, the count identity, T1's
  exact grade-lane mapping, T2's two grade-independence witnesses, and the
  un-instructed cell's silence.
* `scripts/263_p121_env_sort_selftest.py` - the offline leg (dispatch table,
  OOD gate, capability map, source wiring).
