# P10-C.2 IMPLEMENTATION: the slip-magnitude confirmation gate (`FRUIT_CARRY_MONITOR_CONFIRM_MM`)

Lane P10-C.2 implementation (Tier C, offline only), 2026-10-17, branch `p-supply`.
Spawn-time HEAD `523b78e` (tag `p10c-gate`); HEAD advanced to `10109f9f` during
the lane with **logs/-only** commits (the Oracle prereg/C_RESULTS fixes) - `git
diff 523b78e HEAD --stat -- src/` is empty and HEAD's `tasks.py` is the P10-C
version `09c920c9...`, so the implementation base src tree is unchanged. **No
simulator run was made** - the battery is a separate lane that starts only after
the Oracle gate on the frozen pre-registration `logs/p10c/PREREG_CONFIRM_GATE.md`
(the frozen form, including the `FRUIT_CARRY_MONITOR_TWOLINE=1` arm-B env). No
commit; the working tree carries the diff (`logs/p10c2/10_diff.patch`). Writes:
`src/fruit_sorting/tasks.py`, `src/fruit_sorting/rl_env.py` (the metadata-only
`TASKS_MD5` follow), `logs/p10c2/`.

## 1. Diff summary

```
src/fruit_sorting/tasks.py   +109 -21   (the confirm knob + the monitor-path
                                         clean-slip accumulator + the deferred
                                         trip->fire decision + the cancel row)
src/fruit_sorting/rl_env.py  +10  -1    (TASKS_MD5 metadata-only follow + its
                                         history paragraph)
```

`tasks.py` (`git diff`, four hunks):

1. **`__init__`, after the P10-C scope-knob read (new lines 962-980)** - the
   knob read plus its provenance comment:
   ```python
   self._carry_monitor_confirm_mm = float(
       os.environ.get("FRUIT_CARRY_MONITOR_CONFIRM_MM", "0.0")
   )
   ```
   (`float(...)` like every other numeric knob - `FRUIT_CARRY_RELIEF` etc.; the
   `== "1"` truthiness convention applies to the boolean knobs only.)
2. **`_carry`, the per-leg accumulator init (line 2604)** - `mon_slip_ref =
   None`, `mon_slip_max = 0.0` (two pure assignments per leg; no reads).
3. **`_carry`, the per-tick loop (line 2885)** - the new `elif mon_leg is not
   None:` clean-slip accumulator attached to the guard/diag block, and the trip
   tick reduced to a bare `mon_leg.step(...)` call (the trip is a *candidate*
   fire).
4. **`_carry`, the leg boundary (line 3019, after the `[carry]` diag block)** -
   the decision block: the confirmation gate, the fire bookkeeping (moved here
   from the trip tick), the fire row (now carrying `clean_slip_max`), and the
   new `[monitor] cancel` row.

`rl_env.py`: `TASKS_MD5` follows the new `tasks.py` and the pin history gains
the P10-C.2 paragraph. Nothing else.

## 2. The knob semantics

`FRUIT_CARRY_MONITOR_CONFIRM_MM` (float, **default 0.0**; the battery value
8.0): when > 0, a classifier trip counts as a fire only if the fired leg's
running `clean_slip_max` has reached this threshold [mm] **by the leg
boundary**; a trip below the threshold is **cancelled** - nothing is counted or
latched, one `[monitor] cancel` diag row is printed, and the attempt runs on to
its normal end (the place leg / release still run). At the default 0.0 (and at
any value <= 0) the gate's first operand short-circuits (`<= 0.0`): every trip
confirms and the decision behavior is exactly the P10-C form - fires, skip
latch, counters - and no `cancel` row is ever emitted. The knob is scope-free:
it applies to whichever scope the monitor is armed on (direct/policy handover,
or the two-line worker's scripted catch under `FRUIT_CARRY_MONITOR_TWOLINE=1`).

**The decision point (the prereg's "reaches the threshold by the fast-skip
site").** The gate is evaluated at the end of the fired leg, inside `_carry`,
which is the last statement before the two fast-skip sites
(`_grasp_carry_place_impl` lines 8966 / 9020) consume the confirmed latch.
There are no leg ticks between the evaluation and the sites, so the operand is
exactly "the leg's running `clean_slip_max` at the fast-skip site". The two
sites themselves are **unchanged** (they still read only
`self._carry_monitor_skip`; the impl never reads the confirm knob) - a
cancelled trip simply never sets the latch.

**What moved and what that means for byte-identity.** In the P10-C form the
trip tick itself counted the fire, set the latch and printed the fire row. Now
those three happen at the leg boundary. At knob 0 the *decisions* are
identical (every trip confirms; the latch is set before the same fast-skip
sites; the counters and the fired list carry the same entries), and the only
reporting differences on the monitor-on path are (a) the `[monitor] fire` row
prints at the leg boundary (after the leg's `[carry]` row) instead of mid-leg,
and (b) the row gains ` clean_slip_max=...` at the end. The knob-off
*monitor-off* form - the no-harm bar's A records - is fully inert: with
`FRUIT_CARRY_MONITOR` unset the accumulator never runs (it needs
`mon_leg is not None`), the decision block never runs, and the only new work
is one `float(os.environ.get(...))` in `__init__` plus two local assignments
per leg, so no simulator read, print or branch is added.

## 3. The tracker's liveness and cost

The confirmation's operand is the same per-leg `clean_slip_max` the `[carry]`
diag row reports, read as:

```python
leg_slip_max = guard_slip_max if guard_armed else mon_slip_max
```

* when the guard/diag tracker is live (`guard_armed`, i.e. `FRUIT_CARRY_GUARD`
  or `FRUIT_CARRY_DIAG` on the direct path) the gate reads that tracker - the
  same number the `[carry]` row prints, to the digit;
* otherwise the gate reads the new **monitor-path accumulator**, live whenever
  the leg is monitored. The P10-C tracker is diag-gated, so without this the
  gate would read a dead tracker with `FRUIT_CARRY_DIAG` off and cancel every
  trip.

The accumulator is the `elif mon_leg is not None:` branch of the guard/diag
block, so it is **live exactly when the leg is monitored and the guard/diag
tracker is not**; it is not gated on the diag or on the confirm knob, and it
stays live after a trip (`mon_leg.done` does not stop it) because the gate
confirms on the slip's growth after the trip. It takes the same two reads as
the tracker - the **post-step** wrist quaternion (`arm.tcp_pose()[1]`; the
loop's `rot` is the pre-step wrist, a measured 34-88 mm artifact on a held
payload) and the payload/pad positions already in hand - and the same
reference-at-first-tick convention, so its value equals the `[carry]` row's
`clean_slip_max`.

**Cost:** one `tcp_pose()` read + one 3x3 matmul per monitored tick, and only
on the monitor path (itself opt-in) with the guard/diag tracker off; the
battery's arm B runs with `FRUIT_CARRY_DIAG=1`, so there the accumulator is
off entirely and the guard tracker is the operand. The computation is
run-neutral: the P10-C arm-A diag run (which computes this clean slip every
tick) replays the P10-A record bit-identically on the `[fruit]` stream
(`logs/p10c/C_RESULTS.md` section 1).

## 4. The diag rows (the battery's fire table)

* **Fire (confirmed):** unchanged P10-C fields, plus the slip operand:
  `[monitor] fire <side> <leg>: tick=T/N z=... asym@fire=... hot=... blocked=...
  min_contacts=... clean_slip_max=X.Xmm`
  The prefix up to `min_contacts` is byte-compatible with the P8-2 report's
  regex (`logs/p8d/p8d_monitor_report.py`), so the historical parsers still
  match.
* **Cancel (gate withheld the fire):**
  `[monitor] cancel <side> <leg>: tick=T/N clean_slip=X.Xmm < T.Tmm`
  The `[monitor] attempt` summary is unchanged; a cancelled trip is absent
  from its `fired=[...]` list and its `fires=` count, and is named by the
  cancel row only (no new failure-reason string - the K4 convention holds).
* Both rows are gated by `FRUIT_CARRY_MONITOR_DIAG=1` like the rest of the
  monitor traffic.

## 5. Verification (offline only; no simulator)

| # | check | result | evidence |
| --- | --- | --- | --- |
| 1 | `python3 -m py_compile` both touched files | OK | `11_py_compile.txt` |
| 2 | `scripts/selfcheck.sh` (SELFCHECK_LOG under `logs/p10c2/`) | **PASS 0 failures, 1 skipped** (the motion-budget leg needs a run log) | `25_selfcheck.txt`, `25_selfcheck_internal.log` |
| 3 | `logs/p7c/verify_monitor_stub.py` (floor 0) | STUB PASS (the P7-2b pin) | `19_stub_p7c_floor0.txt` |
| 4 | `logs/p8c/verify_monitor_stub_lf.py` (default floor 3.5) | STUB PASS, 28/0/3/33 | `20_stub_lf_floor35.txt` |
| 5 | `logs/p8c/verify_monitor_stub_lf.py STUB_FLOOR=0` | STUB PASS, 29/0/2/33 (identical output to 3 - the same pin) | `21_stub_lf_floor0.txt` |
| 6 | `logs/p8c/verify_monitor_stub_lf_p81.py` (both pins + wiring + `asym@fire`) | STUB PASS | `22_stub_p81_both.txt` |
| 7 | `logs/p9a/check_skip_predicate.py` | RESULT: PASS (all checks) | `23_skip_predicate.txt` |
| 8 | `logs/p10c/check_twoline_scope.py` (the P10-C scope stub) | RESULT: PASS | `24_scope_stub.txt` |
| 9 | `scripts/172_supply_selftest.py` | supply selftest ok (74 checks) | `31_supply_selftest.txt` |
| 10 | **new** `logs/p10c2/check_confirm_gate.py` | RESULT: PASS (56 checks, below) | `30_confirm_gate_stub.txt` |

The new stub (`logs/p10c2/check_confirm_gate.py`, md5
`9e9943cccb8f8ba86a7c27e547329ce7`) exec's the **real** statements from
`tasks.py` by AST - no re-implementation:

* **(a) the knob-off path is exactly the P10-C logic:** the real gate
  expression (`self._carry_monitor_confirm_mm <= 0.0 or leg_slip_max * 1000.0
  >= self._carry_monitor_confirm_mm`) is evaluated over a 72-row truth table
  (6 confirm values x 12 slip values) against an independent reference; the
  knob-off rows confirm every trip regardless of slip, and the short-circuit
  is *proven* by evaluating with a slip operand whose `__mul__` raises - at
  0.0 it is never touched (the result is True), at 8.0 it is evaluated
  (the exception fires). The knob read is exec'd: unset -> 0.0, `"8.0"` ->
  8.0, `"0"` -> 0.0.
* **(b) below the threshold cancels, at/above confirms:** the real boundary
  `if` statement is exec'd end-to-end with synthetic bindings - the battery's
  0.4/6.3 mm cases cancel (nothing counted, latch clear, the exact cancel row),
  13.1/19.0/1646.1 mm and the inclusive 8.000 mm edge confirm (fire counted,
  latch set, fired list appended, the fire row with `clean_slip_max`); a
  0.4 mm slip still fires at knob 0; a no-trip leg and an absent `mon_leg` do
  nothing; the operand selection is pinned by a discriminating decoy pair
  (`guard_armed` -> `guard_slip_max`, else `mon_slip_max`).
* **(c) the cancel diag row renders:** the real `say(...)` statement renders
  exactly `[monitor] cancel left grasp_lift: tick=138/160 clean_slip=6.3mm <
  8.0mm` (full-string equality).
* the accumulator's liveness is pinned structurally (one
  `elif mon_leg is not None:` attached to `if guard_armed:`; not gated on the
  diag or the knob; no `done` in its guard) and functionally (the real block
  is replayed over synthetic ticks against `max_t ||d_t - d_0||`, identity and
  fixed-90-deg quats agree to < 1e-12 mm, first tick contributes zero).
* `rl_env.TASKS_MD5 == md5(tasks.py)` (verified matching).

No simulator runs were made. **The Tier-A battery is deferred to the separate
lane that starts only after the Oracle gate on the frozen
`logs/p10c/PREREG_CONFIRM_GATE.md`** (arms: the standing P10-C.1 A records +
the 3-seed B runs with the gate at 8.0, both with
`FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1`; the no-harm bar: the
knob-off replay pair and the knob-off acceptance vs `logs/p2d/90_accept.log`,
`selfcheck.sh` PASS, `172`). The pre-reg's no-harm and endpoint obligations
are therefore **not yet demonstrated** and remain battery-time work.

## 6. Alignment notes for the battery lane (env-only; no code change needed)

* The frozen arm-B env already carries the scope knob and the gate:
  `FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_TWOLINE=1
  FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5 FRUIT_CARRY_MONITOR_CONFIRM_MM=8.0`.
* With `FRUIT_CARRY_DIAG=1` (the battery's common env) the gate's operand is
  the guard tracker, i.e. exactly the `[carry]` row's `clean_slip_max` - the
  K2 report (`logs/p10c/k2_report.py`, which pairs the attempt summary with
  the `[carry]` rows) keeps working unchanged, and its `fires` count now
  reflects confirmed fires only.
* The **cancelled trips are not in the summary's `fired=[...]`**; they are the
  `[monitor] cancel` rows. The fire table (prereg endpoint 5) reads: confirmed
  fires from the fire rows' `clean_slip_max`, cancelled trips from the cancel
  rows. The prereg's primary endpoint 1(a) (frozen K2 aborts = 0) is measured
  on confirmed fires; the ground-truth false-positive read (1(b)) is measured
  on the cancel rows against the same-seed A records.
* Expected retention on the P10-C.1 fire table: the two marginal fires
  (0.4 / 6.3 mm) cancel by construction; the 13 clear fires (>= 13.1 mm) are
  above the 8.0 threshold with >= 5 mm margin on both sides, so the expected
  count is 13/15 (the kill floor is >= 10/15).

## 7. Pins and md5s

| item | before (the P10-C record) | after |
| --- | --- | --- |
| `src/fruit_sorting/tasks.py` | `09c920c99b7a6a75d16e5a99dcda1872` | **`22cc5b31a510ddcb747436d713f5604c`** |
| `src/fruit_sorting/rl_env.py` | `9bb43c4c9e8dc2740bd2c7f8e3f7e1c1` | **`d8a5790786b99471e0f6c2aa1f097d86`** (`TASKS_MD5` = the tasks.py md5, verified matching) |
| `policy/trigger.py` / `policy/runtime.py` / `fruits.py` / `configs/*` | untouched | `d7ec85fc` / `ffb76bfd` / `f5671a65` / `b9e72ca7` (motion reference) |

Evidence artifact md5s: `logs/p10c2/40_artifact_md5s.txt`. Tree pins:
`logs/p10c2/00_tree_pins.txt` (branch, HEAD, git status: only the two src files
modified; `logs/` is gitignored). The diff: `logs/p10c2/10_diff.patch` (md5
`c400afad1dcd085ab767573e57295f91`).
