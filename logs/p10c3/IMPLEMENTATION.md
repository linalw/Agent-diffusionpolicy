# P10-C.3 IMPLEMENTATION: the two-line carry-monitor default flip + the collector manifest field

Lane P10-C.3 implementation (Tier C, offline only), 2026-10-17, branch `p-supply`.
Spawn-time HEAD `f2cdadd` (tag `p10c2-gate`); HEAD advanced to `275e8f1c` during
the lane with the frozen pre-registration commit (logs-only - `git diff f2cdadd
HEAD --stat -- src/ scripts/` is empty, so the implementation base src tree is
the P10-C.2 tree, `tasks.py` `22cc5b31`). **No simulator run was made** - the
Tier-A battery (`logs/p10c2/PREREG_ADOPT_FLIP.md`) starts only after this
implementation is verified and is a separate lane. No commit; the working tree
carries the diff (`logs/p10c3/10_diff.patch`). Writes: `src/fruit_sorting/tasks.py`,
`src/fruit_sorting/rl_env.py` (the metadata-only `TASKS_MD5` follow),
`scripts/40_collect_demos.py` (the manifest field), `logs/p10c3/`.

## 1. Diff summary

```
src/fruit_sorting/tasks.py     +68 -1   (the __init__ note; the
                                         `_resolve_carry_monitor_knobs`
                                         helper; its call in
                                         `grasp_carry_place`)
src/fruit_sorting/rl_env.py    +11 -1   (TASKS_MD5 metadata-only follow + its
                                         P10-C.3 history paragraph)
scripts/40_collect_demos.py    +8  -0   (the `collection.carry_monitor`
                                         manifest field)
```

`tasks.py` (`git diff`, three hunks):

1. **`__init__`, after the confirm-knob read (new lines 981-991)** - a comment
   block only: the four monitor reads above stay the **env/shipped base** and
   point at the per-attempt resolution helper. No read or default is touched
   (the P10-C/P10-C.2 stubs' text pins on the four `os.environ.get(...)` calls
   still hold).
2. **`_resolve_carry_monitor_knobs` (new, before `grasp_carry_place`)** - the
   four resolution statements, each a `_dynamic_profile(name, shipped,
   two_line)` call (the W7-A park-gate pattern's exact shape):
   ```python
   self._carry_monitor = (
       self._dynamic_profile("FRUIT_CARRY_MONITOR", "0", "1") == "1"
   )
   self._carry_monitor_twoline = (
       self._dynamic_profile("FRUIT_CARRY_MONITOR_TWOLINE", "0", "1") == "1"
   )
   self._carry_monitor_confirm_mm = float(
       self._dynamic_profile("FRUIT_CARRY_MONITOR_CONFIRM_MM", "0.0", "8.0")
   )
   self._carry_monitor_load_floor = float(
       self._dynamic_profile("FRUIT_CARRY_MONITOR_LOAD_FLOOR", "0.0", "3.5")
   )
   ```
3. **`grasp_carry_place`** - one call `self._resolve_carry_monitor_knobs()` at
   the top of the body (before the `_grasp_carry_place_impl` call), plus the
   docstring sentence and the call-site comment.

`rl_env.py`: `TASKS_MD5` follows the new `tasks.py`; the pin history gains the
P10-C.3 paragraph. Nothing else.

`scripts/40_collect_demos.py`: the `collection` block of the shared
`write_manifest` gains `"carry_monitor": os.environ.get("FRUIT_CARRY_MONITOR",
"auto")` directly after `park_early`. Nothing else.

## 2. The resolution semantics (the prereg's flip)

| knob | shipped default (`__init__` read) | two-line, env unset | env set |
| --- | --- | --- | --- |
| `FRUIT_CARRY_MONITOR` | `"0"` -> `False` | **`"1"` -> `True`** | env wins (`== "1"`) |
| `FRUIT_CARRY_MONITOR_TWOLINE` | `"0"` -> `False` | **`"1"` -> `True`** | env wins (`== "1"`) |
| `FRUIT_CARRY_MONITOR_CONFIRM_MM` | `"0.0"` -> `0.0` | **`"8.0"` -> `8.0`** | env wins (`float(env)`) |
| `FRUIT_CARRY_MONITOR_LOAD_FLOOR` | `"0.0"` -> `0.0` | **`"3.5"` -> `3.5`** | env wins (`float(env)`) |

Session kinds (the `_dynamic_profile` session test, `getattr(session, "twoline",
False)`):

| session | resolution |
| --- | --- |
| two-line (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) | env, else the two-line value (the flip) |
| shared-station bimanual (`FRUIT_BIARM=1`, no TWOLINE; `session.twoline=False`) | env, else shipped (byte-inert) |
| single-arm scripted line (`_active_session is None`) | env, else shipped (byte-inert) |
| direct/policy handover (no session) | env, else shipped (byte-inert) |

**The explicit restores (all pinned by the stub):**

* `FRUIT_CARRY_MONITOR_TWOLINE=0` -> the scope knob `False`; the scope
  predicate's scripted two-line arm (`two_line_catch and knob`) never arms ->
  the pre-flip two-line behavior (no monitor). The master still resolves `1`
  when unset - harmless: the scripted two-line path needs the scope knob.
* `FRUIT_CARRY_MONITOR_CONFIRM_MM=0` -> the gate `0.0`, which short-circuits
  (`<= 0.0`) -> the **ungated** monitor (every classifier trip confirms,
  exactly the P10-C form). This is the env that reproduces the P10-C ungated
  record `logs/p10c/51_seed11_B.log` (see the flag in section 5).
* `FRUIT_CARRY_MONITOR=0` -> the master `False` -> no arming on any scope (the
  master wins), two-line included.

**Where it resolves, and why there.** The monitor's read sites are all pinned
by the P10-C/P10-C.2 stubs and must keep their exact text: the four `__init__`
reads, the scope statements `two_line_catch = bool(...)` /
`_carry_monitor_active = ...` in `_grasp_carry_place_impl` (exec'd by
`logs/p10c/check_twoline_scope.py`), the `_CarryMonitorLeg(self._carry_monitor_load_floor)`
call and the boundary confirmation gate in `_carry`. The confirm knob may not
even be *mentioned* in `_grasp_carry_place_impl`
(`logs/p10c2/check_confirm_gate.py`: `"_carry_monitor_confirm_mm" not in
ast.unparse(impl)`). So the flip cannot resolve at any of the read sites; it
resolves once, before all of them: `grasp_carry_place` is the common attempt
entry (the scripted line via `_run_impl` and the two-line worker, the
direct/policy path via the evaluator's `task.grasp_carry_place(...)`), and
`_grasp_carry_place_impl` is only ever called from it, so the resolution
precedes every monitor read and every attempt re-resolves from the env
(a later non-two-line attempt in the same process cannot inherit the flip).

**Byte-inertness of the untouched scopes.** For a non-two-line session the
resolution returns exactly the values the `__init__` reads produced for the
same env (env wins; else the shipped default); for a two-line session with an
explicit env the same holds. The stub proves this by exec'ing the real
resolution statements and the real `__init__` read statements and comparing
per knob over the full sweep - only the two-line-unset rows differ, and there
they read the pre-registered two-line values. `FRUIT_CARRY_MONITOR_DIAG` is
deliberately **not** resolved (trace-only; the flip run simply prints no
`[monitor]` rows, which the battery reads as "modulo reporting rows").

**Run-neutrality.** The resolution adds four `os.environ.get` calls per
attempt; no simulator read, no print, no new branch on any path. The monitor's
own work (features, fire, skip) is unchanged and still gated by the scope
predicate.

## 3. The collector manifest field

`scripts/40_collect_demos.py`, `write_manifest` (the single shared writer for
both collector modes), the `collection` block, directly after `park_early`:

```python
"carry_monitor": os.environ.get("FRUIT_CARRY_MONITOR", "auto"),
```

`"auto"` = the env was unset = the flip (on for a two-line session; the
`collection.mode` field says whether the shard is two-line); an explicit `0`/`1`
records the override. A post-flip two-line recollection is a **new branch** and
this field identifies it next to the `tasks.py` md5 pin (the W7-B lesson / the
W7-C.1 `park_early` pattern). Note `scripts/107_collect_merge_test.py` does not
read the manifest at all; the field is pinned offline by the new stub's layer 4
(AST shape + the real expression evaluated for unset/0/1).

## 4. The verification (offline only)

| check | result | record |
| --- | --- | --- |
| `python3 -m py_compile` (tasks, rl_env, 40_collect) | OK | `11_py_compile.txt` |
| **new stub** `logs/p10c3/check_flip_resolution.py` | **PASS, 37 checks** | `20_stub_flip_resolution.txt` |
| `logs/p10c/check_twoline_scope.py` (P10-C scope) | PASS | `21_stub_twoline_scope.txt` |
| `logs/p10c2/check_confirm_gate.py` (P10-C.2 gate) | PASS | `22_stub_confirm_gate.txt` |
| `logs/p9a/check_skip_predicate.py` | PASS | `23_stub_skip_predicate.txt` |
| the monitor-family historical stubs (`logs/p7c/verify_monitor_stub.py` floor 0; `logs/p8c/verify_monitor_stub_lf.py` default + `STUB_FLOOR=0`; `logs/p8c/verify_monitor_stub_lf_p81.py`) | PASS | `24*_stub_*.txt` |
| `scripts/selfcheck.sh` | **PASS, 0 failures, 1 skipped** (motion budgets - no run log offline) | `25_selfcheck.txt` |
| `scripts/107_collect_merge_test.py` | PASS, all 15 checks | `30_107_collect_merge_test.txt` |
| `scripts/172_supply_selftest.py` | PASS, 74 checks | `31_172_supply_selftest.txt` |

The new stub (`logs/p10c3/check_flip_resolution.py`) is the flip's truth-table
evidence, built like the historical stubs (real statements extracted by AST and
exec'd, never re-typed):

1. source checks - the four `__init__` reads unchanged (one env read each,
   defaults pinned); `_resolve_carry_monitor_knobs` defined once, called once,
   the only other writer of the four attributes; the call precedes the
   `_grasp_carry_place_impl` call in `grasp_carry_place`; the four statements
   are `_dynamic_profile` calls with the exact `(name, shipped, two-line)`
   triples; the diag is not resolved; the impl still never reads the confirm
   knob;
2. **the resolution truth table** - the real `_dynamic_profile` method + the
   real four resolution statements, re-evaluated over 4 sessions x 4 knobs x
   the unset/0/1/8.0 env states (64 rows) plus an extended grid, against an
   independent reference; the flip rows (52) read the two-line values and
   differ from the shipped ones; every non-flip row is byte-inert vs the real
   `__init__` reads;
3. **the restores, end-to-end** - the resolved values are fed into the real
   scope predicate (`two_line_catch` + `_carry_monitor_active`): the two-line
   no-env row arms; `FRUIT_CARRY_MONITOR_TWOLINE=0` / `FRUIT_CARRY_MONITOR=0`
   do not; `FRUIT_CARRY_MONITOR_CONFIRM_MM=0` arms at gate 0.0; the
   shared-station, single-arm and direct scopes resolve to the shipped values
   and never arm from the flip (the direct scope with `FRUIT_CARRY_MONITOR=1`
   still arms, unchanged); 14 named rows;
4. the collector manifest field (shape + unset/0/1 evaluation, `park_early`
   sibling);
5. `rl_env.TASKS_MD5 == md5(tasks.py)`.

## 5. The battery (deferred) and two flags for the battery lane

**The Tier-A battery is deferred** - it starts only after this implementation
is verified, and is a separate lane. Its pre-registered expectations are the
prereg's table: `flip_seed5/11/23` (no relevant env) bit-identical to the
P10-C.2 gated records (`61/62/63_*_gate.log`, modulo reporting rows - the flip
resolves to the tested config, which this lane's truth table pins offline);
the restore run bit-identical to the P10-C ungated `51_seed11_B.log`; the
acceptance 9/10 + `fingerprint: matches` + 385/385 vs `logs/p2d/90_accept.log`;
the re-baseline of `configs/motion_reference_patch.json`. Nothing here ran the
simulator.

Two flags (prereg wording, not implementation questions):

1. **The prereg's battery-table row 4 is internally inconsistent.** It labels
   the restore run `restore_seed11 - FRUIT_CARRY_MONITOR_TWOLINE=0` but expects
   bit-identity to `51_seed11_B.log`, which is the **ungated monitor** record
   (it ran with `FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_TWOLINE=1
   FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5`, monitor ON). Under the prereg's own
   resolution block (`FRUIT_CARRY_MONITOR_TWOLINE=0` -> the pre-flip behavior,
   no monitor) a no-monitor run cannot be bit-identical to a monitor-on
   record. The env that *does* reproduce `51_seed11_B.log` is
   `FRUIT_CARRY_MONITOR_CONFIRM_MM=0` (the "ungated monitor" restore named in
   the same block; endpoint 1's "the restore run bit-identical to the ungated
   record" points at it). Both restores are implemented and stub-pinned; the
   battery lane should confirm the intended env (expected: the row's env is a
   typo for `FRUIT_CARRY_MONITOR_CONFIRM_MM=0`).
2. **The load floor.** The prereg's "(already the shipped default)" for
   `FRUIT_CARRY_MONITOR_LOAD_FLOOR -> 3.5` does not match the shipped code
   (the `__init__` default is `0.0`, the P7-2b rule; 3.5 is the P8-2/P10-C
   battery value). The flip therefore resolves the floor to `3.5` explicitly,
   so the flip runs (no relevant env) reproduce the gated records - which all
   ran with `FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5` - bit-for-bit.

## 6. Pins (live)

```
tasks.py                 6574d92eafe38f1025b880d39a9410f9   (was 22cc5b31a510ddcb747436d713f5604c)
rl_env.py                8413fece2203c1bccd84b0d5c3830eb3   (TASKS_MD5 = 6574d92e...; was d8a5790786b99471e0f6c2aa1f097d86)
scripts/40_collect_demos.py  59cbe06443ecf18695856daa962a5f3e   (was abf3e09da9a4bea6efda497509a92165)
trigger.py d7ec85fc, runtime.py ffb76bfd, fruits.py f5671a65   (unchanged)
```

## 7. Files in this lane

```
logs/p10c3/00_tree_pins.txt           the pins + the diff summary
logs/p10c3/00_md5s.txt                the live md5s
logs/p10c3/10_diff.patch              the working-tree diff (3 files)
logs/p10c3/11_py_compile.txt          py_compile record
logs/p10c3/20_stub_flip_resolution.txt  the new stub (37 checks, PASS)
logs/p10c3/21_stub_twoline_scope.txt  the P10-C stub (PASS)
logs/p10c3/22_stub_confirm_gate.txt   the P10-C.2 stub (PASS)
logs/p10c3/23_stub_skip_predicate.txt the P9-A stub (PASS)
logs/p10c3/24*_stub_*.txt              the P7c/P8c monitor-family stubs (PASS)
logs/p10c3/25_selfcheck.txt (+_internal.log)  selfcheck (PASS, 0 failures, 1 skipped)
logs/p10c3/30_107_collect_merge_test.txt  the collect/merge regression (PASS, 15 checks)
logs/p10c3/31_172_supply_selftest.txt     the supply selftest (PASS, 74 checks)
logs/p10c3/check_flip_resolution.py   the new stub
logs/p10c3/IMPLEMENTATION.md          this record
logs/p10c3/WORKLOG_entry.md           the WORKLOG entry
```
