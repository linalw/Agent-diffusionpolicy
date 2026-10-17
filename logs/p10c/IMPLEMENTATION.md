# P10-C IMPLEMENTATION: the C-3 carry monitor's two-line scope knob (`FRUIT_CARRY_MONITOR_TWOLINE`)

Lane P10-C implementation (Tier C, offline only), 2026-10-17, branch `p-supply`,
base HEAD `13737fd4847bfb9743867955054a82859e8c0969` (the P10-A/P10-B commit;
the lane task's spawn-time HEAD `6635f8e` is its parent). **No simulator run
was made** - the battery is a separate lane that starts only after the Oracle
gate on the frozen pre-registration `logs/p10/PREREG_MONITOR_TWOLINE.md`. No
commit; the working tree carries the diff (`logs/p10c/10_diff.patch`). Writes:
`src/fruit_sorting/tasks.py`, `src/fruit_sorting/rl_env.py` (the metadata-only
`TASKS_MD5` follow), `logs/p10c/`.

## 1. Diff summary

```
src/fruit_sorting/tasks.py   +50 -10   (P10-C scope knob + scope predicate + comments)
src/fruit_sorting/rl_env.py  +11  -1   (TASKS_MD5 metadata-only follow + its history note)
```

`tasks.py` (`git diff`, four hunks; no control-flow change on any default path):

1. **`__init__`, after the P8-2 floor read (new lines 946-959)** - the scope
   knob read:
   ```python
   self._carry_monitor_twoline = (
       os.environ.get("FRUIT_CARRY_MONITOR_TWOLINE", "0") == "1"
   )
   ```
2. **`__init__` monitor comment block (~line 912)** - the P7-2b sentence
   "the scripted line (single arm and two-line) never reaches the monitor"
   corrected to name the P10-C two-line scope and its default-off knob.
3. **`_grasp_carry_place_impl`, the scope site (lines 6419-6442)** - the
   predicate (section 3).
4. **The lift-leg fast-skip comment (`grasp_carry_place` tail, ~line 8885)** -
   one sentence: the same boundary ends a two-line worker attempt when the
   scope knob is on; the worker's park/gate/arbiter path is reached exactly as
   after any early return.

`rl_env.py`: `TASKS_MD5` follows the new `tasks.py` and the pin history gains
the P10-C paragraph (scope-only, default-inert). Nothing else.

## 2. The knob semantics

`FRUIT_CARRY_MONITOR_TWOLINE` (default `"0"`, truthiness `== "1"` exactly like
every other knob): **scope-only**. It does not arm anything by itself.

* `FRUIT_CARRY_MONITOR` unset or `0` → the monitor is off everywhere (unchanged).
* `FRUIT_CARRY_MONITOR=1`, scope knob unset/`0` → **exactly the pre-P10-C
  behavior**: the direct/policy handover only; the two-line never arms
  (byte-inert at the default, asserted over the full 96-row truth table).
* `FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_TWOLINE=1` → additionally arms the
  **two-line scheduler's own scripted moving catch** (`FRUIT_BIARM=1
  FRUIT_BIARM_TWOLINE=1`), i.e. the `run_bimanual`/`_biarm_worker` attempt
  path. The single-arm scripted line, the shared-station pipeline
  (`FRUIT_BIARM=1` without TWOLINE) and the indexed path never arm it.

The load floor and the diag are the **same code, not a two-line copy** (this is
the P10-C requirement "must work identically on the two-line path"):

* the per-leg `_CarryMonitorLeg(self._carry_monitor_load_floor)` call site is
  the single call site; `FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5` reaches the
  two-line legs through it unchanged;
* the fire block is the single `[monitor] fire` block (same `asym@fire` field),
  the attempt summary the single `[monitor] attempt` line, both in the shared
  `_carry` / `grasp_carry_place` code;
* the monitor state (`_carry_monitor_active` / `_skip` / counters) is
  `_AttemptLocal` (thread-local), which is exactly what the two-line's two
  concurrent worker threads need - the two arms' monitors cannot collide;
* the per-tick reads (jaw separation, tactile) are taken under the bimanual
  relay's single run permit (one attempt thread executes at a time), the same
  serialization every existing `_carry` read already relies on.

## 3. The scope predicate (exact)

`_grasp_carry_place_impl`, replacing the old
`bool(self._carry_monitor and direct_capture)` line:

```python
two_line_catch = bool(
    scripted
    and dynamic_capture
    and self._active_session is not None
    and getattr(self._active_session, "twoline", False)
)
self._carry_monitor_active = bool(
    self._carry_monitor
    and (direct_capture or (two_line_catch and self._carry_monitor_twoline))
)
```

Properties (each pinned by `logs/p10c/check_twoline_scope.py`):

* `direct_capture` (= `dynamic_pick and openarm and not scripted`) is the
  shipped direct scope, untouched by the new knob;
* the two-line branch requires all of: `scripted` (the worker's `_run_impl`
  call), `dynamic_capture` (the OpenArm moving catch - the shared scope gate),
  a live session with `session.twoline` true (only `run_bimanual` with
  `FRUIT_BIARM_TWOLINE=1` sets it), **and** the new knob;
* the per-leg arming site in `_carry` is unchanged and has no two-line
  exclusion: `mon_armed = active and hand_is_jaw and self._dynamic_capture_active`;
* knob off → `active == (monitor and direct_capture)` on every row (the
  byte-inert property; the two-line's park/gate/arbiter code is not touched by
  this diff at all).

## 4. The two-line fast-skip: cleanly implementable - no blocker

The pre-registered question ("if the fast-skip cannot end a two-line attempt
cleanly at a leg boundary, STOP and report the blocker") resolves **positive**
by code inspection; the implementation needed no change to the two-line attempt
loop.

* The fast-skip is the primitive's early `return result` inside
  `_grasp_carry_place_impl` at the fired leg's boundary (after `grasp_lift`:
  line 8878; after `placeN`: line 8932). That is the *same shape* as the
  shipped `not result.grasped` early return and every other failed attempt:
  the call stack unwinds `_grasp_carry_place_impl` → `grasp_carry_place` →
  `_run_impl` → `run` → `_biarm_worker` with no two-line code between the leg
  boundary and the worker's end-of-attempt machinery.
* The worker's machinery is all *after* the primitive returns and is reached
  exactly as after a normal failure: `run`'s `finally` (pre-pose lock release,
  episode-deadline clear, `unprotect`, `_biarm_clear_streak` reset, `held`
  clear), the `[biarm] result` line, the worker `finally`
  (`_biarm_park` / hot-hold, prefetch, **capture-token release safety net**),
  the attempt-boundary feed, the next slot.
* The park gate reads only the other arm's grip flag / published payload-clear
  (`_biarm_park`, `_biarm_after_step`); a skipped attempt's payload is handled
  by the shipped `grasped and not placed` conventions (payload not released,
  the next attempt's `arm.set_gripper(arm.OPEN)` opens the jaws, `held`
  cleared in `run`'s finally) - identical to the existing carried-not-placed
  failures that already occur on the two-line (P10-A: 7 of 20 attempts).
* The `[cycle]` marks are shorter (no `place`/`release`/`return` segments);
  the parser is documented to treat missing names as zeros for that attempt
  (`scripts/186_w6_report.py` lines 135-138), and `_cycle_report` itself only
  needs >= 2 marks.
* No new failure-reason string is added (the K4 convention: the skip is named
  by the `[monitor]` diag lines only), so the `113_rl_report.py` baseline
  reason set is untouched by construction.

**One pre-registration alignment note for the battery lane (not a code
blocker).** The frozen pre-reg's arm B env is
`FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5` and does **not**
mention the scope knob. As implemented (the mandated "default 0 that
*additionally* arms"), that literal env is inert on the two-line: arm B must
add `FRUIT_CARRY_MONITOR_TWOLINE=1` (an env-only addition; no code change), or
the Oracle gate must amend the frozen file. Everything else in the pre-reg's
arms/no-harm sections is unaffected.

## 5. Verification (offline only; no simulator)

| # | check | result | evidence |
| --- | --- | --- | --- |
| 1 | `python3 -m py_compile` both touched files | OK | `11_py_compile.txt` |
| 2 | `scripts/selfcheck.sh` (SELFCHECK_LOG under `logs/p10c/`) | **PASS 0 failures, 1 skipped** (the motion-budget leg needs a run log), 31.17 s | `25_selfcheck.txt`, `25_selfcheck_internal.log` |
| 3 | `logs/p7c/verify_monitor_stub.py` (floor 0) | STUB PASS, TP=29 FP=0 FN=2 TN=33, 0/25 no-contact fires | `20_stub_p7c_floor0.txt` |
| 4 | `logs/p8c/verify_monitor_stub_lf.py` (default floor 3.5) | STUB PASS, **28/0/3/33** | `21_stub_lf_floor35.txt` |
| 5 | `logs/p8c/verify_monitor_stub_lf.py STUB_FLOOR=0` | STUB PASS, **29/0/2/33** | `22_stub_lf_floor0.txt` |
| 6 | `logs/p8c/verify_monitor_stub_lf_p81.py` (both pins + wiring) | STUB PASS; min `asym@fire` 0.900 (floor 0) / 3.663 (floor 3.5) | `23_stub_p81_both.txt` |
| 7 | `logs/p9a/check_skip_predicate.py` | RESULT: PASS (all checks) | `24_skip_predicate.txt` |
| 8 | **new** `logs/p10c/check_twoline_scope.py` | RESULT: PASS (below) | `30_scope_stub.txt` |

The new scope stub (`logs/p10c/check_twoline_scope.py`, md5
`e9c9ab9e38a6306c9ee7a2acfca477c0`) is the "stub-level check that the new scope
predicate is exact": it AST-extracts the **real** `two_line_catch` /
`_carry_monitor_active` statements and exec's them against synthetic bindings,
then checks (a) a 96-row truth table against an independent reference
expression, (b) the byte-inert property on every knob-off row
(`active == monitor and direct_capture`), (c) every armed row outside the
direct scope is exactly the structural two-line case, (d) named cases
including: two-line + `FRUIT_CARRY_MONITOR=1` + knob off → **not armed**
(the pre-P10-C behavior), two-line + both knobs → armed, shared-station /
single-arm scripted → never armed, direct scope → unchanged with the knob
either way, (e) the knob read defaults `"0"` / `== "1"`, (f) the per-leg
`mon_armed` site has no two-line exclusion, (g) the single `_CarryMonitorLeg`
call passes the floor and the single fire/attempt diag blocks are shared,
(h) `rl_env.TASKS_MD5 == md5(tasks.py)`.

No simulator runs were made; the battery (pre-reg arms A/B, the double-runs,
the one `FRUIT_CARRY_MONITOR_DIAG=1` run, `190_twoline_gate.sh`, K2, the fire
readout) **is deferred to the separate lane that starts only after the Oracle
gate on `logs/p10/PREREG_MONITOR_TWOLINE.md`**. The pre-reg's own no-harm bar
(knob-off patch pair bit-identical to the P10-A record, knob-off acceptance
365/365 vs `logs/p2d/90_accept.log`) is therefore **not yet demonstrated** and
remains a battery-time obligation.

## 6. Pins and md5s

| item | before | after |
| --- | --- | --- |
| `src/fruit_sorting/tasks.py` | `4ea81c60f92b0c115a86d4c2f7cb87b1` | **`09c920c99b7a6a75d16e5a99dcda1872`** |
| `src/fruit_sorting/rl_env.py` | `383829c5dcb310ca674a3550c750a4d8` | **`9bb43c4c9e8dc2740bd2c7f8e3f7e1c1`** (`TASKS_MD5` = the tasks.py md5, verified matching) |
| `policy/trigger.py` / `policy/runtime.py` / `fruits.py` / `configs/*` | untouched | `d7ec85fc` / `ffb76bfd` / `f5671a65` / `b9e72ca7` (motion reference) |

Evidence artifact md5s: `logs/p10c/40_artifact_md5s.txt`. Tree pins:
`logs/p10c/00_tree_pins.txt` (branch, HEAD, git status: only the two src files
modified; `logs/` is gitignored). The diff: `logs/p10c/10_diff.patch` (md5
`64b635e9d69967f0987293c333a99ed4`).
