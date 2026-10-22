# P31-A implementation - the WAIT GATE (default off)

Branch `p-supply`. Base commit `b1acbfe`. No simulator run: this lane is offline
by instruction. Everything below is `py_compile`, `scripts/selfcheck.sh`, the
P30-B stub and the new stub over the real sources.

## 1. What changed

| file | md5 | change |
| --- | --- | --- |
| `src/fruit_sorting/rl_env.py` | `01278a54acd379d701b5a5061617a131` | `WaitGateSettings` + the four gate methods + the skip + the tick booking + the outcome keys + the manifest block |
| `src/fruit_sorting/tasks.py` | `e27b18a455b2094aa611b36fd6cec168` | **unchanged** (`TASKS_MD5` pin untouched) |
| `scripts/110_rl_rollout.py` | `b5d05ea3b2e39cdc94da6147ec5ed2d8` | **unchanged** (the `[gate]` row is emitted by the env's `_finalize` through `_say`, so the driver's `[rl]` parsing is not touched) |
| `logs/p31/check_wait_gate.py` | `460fc298a082e40ff37e662b44772821` | the offline stub (95 checks) |
| `logs/p31/30_wait_anatomy.py` | `47743f352b52406bee5274f2b306305f` | the measurement (read-only) |

The full diff is `logs/p31/10_diff.patch` (351 lines, one file, **284
insertions and 0 deletions** - the change is purely additive, so no shipped
statement was rewritten at all, which is the strongest form of the default-off
argument below). No config, dataset, checkpoint, scene, asset, conveyor or
collector file is touched.

### `WaitGateSettings` (frozen dataclass)

```python
enabled: bool = False      # FRUIT_WAIT_GATE (1 = on; anything else = off)
dist: float = 0.35         # FRUIT_WAIT_GATE_DIST   [m, upstream of the station]
past: float = 0.0          # FRUIT_WAIT_GATE_PAST   [m, 0 = off]
warm: int = 1              # FRUIT_WAIT_GATE_WARM   [chunks executed before holding]
diag: bool = False         # FRUIT_WAIT_GATE_DIAG   (one `[gate]` row/episode)
```

* `from_env()` returns `cls()` **on its first line** unless
  `FRUIT_WAIT_GATE == "1"`, so the sub-knobs are never parsed (and a malformed
  value cannot raise) while the gate is off.
* `skips(along, warm=True)` is the pure predicate - the whole decision logic,
  unit-testable without a simulator. Strict `>` / `<`, NaN-safe, `dist <= 0`
  disables the upstream term, `past <= 0` disables the downstream term.
* `summary()` is the banner/manifest line.

### `SortingRLEnv`

* `__init__`: resolve once, cache `_wait_gate_on`, zero the counters
  (`skipped`, `held`, `hold_chunk`, `open`, `resumed`, `along0`).
* `sample_chunk`: two new statements, both inside `if self._wait_gate_on:`,
  placed **after** the `ready` / `ablate` / `rtc` guards and **before**
  `policy.act` - so a held call cannot sample, and the zero ablation, the
  scripted ablation, the RTC chunker and the handoff presentation keep their
  shipped code path.
* `_wait_gate_active`: the scope table (direct, synchronous, real model, no
  dagger, no event lever, no active recorder).
* `_wait_gate_along`: `fruit.y - _expert_jaw_y` - one rigid-body pose read per
  4-tick chunk (the same read `_episode_events` already does every tick).
* `_wait_gate_hold`: the skip; returns
  `np.repeat(self._last_action, action_horizon)` and books the counters.
* `_wait_gate_report`: the `[gate]` row.
* `act`: after the loop, `if self._wait_gate_hold_chunk: _wait_gate_held += executed`
  and clear the flag.
* `_finalize`: `wait_gate_skipped` / `wait_gate_held_ticks` /
  `wait_gate_resumed` in the outcome (only when the knob is on) and the row
  under `_DIAG`.
* `reset`: zero the per-episode counters.
* `_build_manifest`: `"wait_gate": asdict(...) if enabled else None` - the A/B
  provenance block.

## 2. Default-off (byte-inert) argument

Three layers, all checked by `logs/p31/check_wait_gate.py`:

1. **The flag**: `from_env` returns the defaults on its first line, so an unset
   or `=0` gate never reads `_DIST`/`_PAST`/`_WARM`/`_DIAG` (proved by injecting
   `FRUIT_WAIT_GATE_DIST=not-a-number` with the gate off: no raise).
2. **The statement identity vs `b1acbfe`** for the three functions whose body
   matters (`sample_chunk`, `act`, `_finalize`): every base *simple* statement
   survives verbatim and every base branch condition survives verbatim (so no
   shipped behaviour was rewritten); every *new* simple statement is dominated by
   `self._wait_gate_on` or `self._wait_gate_hold_chunk` (2 + 2 + 4 statements,
   respectively). The four new methods are reachable only through the gate
   (call-site domination plus a callee fixpoint).
3. **The runtime consequence**: with the gate off, the only executed addition is
   one False `if` per model call (`once per 4 ticks`), one False `if` per `act`,
   and no new sensor/articulation read. `policy.act`'s call count, the action
   stream, the reward's `decision`, the outcome dict and the recorder are
   unchanged.

The intended remaining proof is the tree-level acceptance fingerprint
(`scripts/accept.sh`) once this lane is allowed a simulator; the statement
identity is the offline stand-in, exactly as P30-B did it.

## 3. Verification run here

```
$ python3 -m py_compile src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
      scripts/110_rl_rollout.py logs/p31/check_wait_gate.py \
      logs/p31/30_wait_anatomy.py            # exit 0 (logs/p31/40_compile.txt)

$ PYTHONPATH=src python3 -c "import fruit_sorting.rl_env; ..."
import OK: wait_gate=off
skips(0.5)= False skips(0.1)= False
on: wait_gate=on dist=0.350 past=0.000 warm=1 diag=on skips(0.5)= True

$ scripts/selfcheck.sh
... all 22 checks PASS, motion budgets SKIP (no run log)
PASS: 0 failures, 1 skipped        # logs/p31/30_selfcheck.log

$ python3 logs/p30b/check_home_hub.py
PASS: all checks                   # the P30-B stub still pins the tree

$ python3 logs/p31/check_wait_gate.py
PASS: all checks                   # logs/p31/32_stub.txt (95 checks)
```

`scripts/selfcheck.sh` is outside this lane's write scope, so the new stub is
**not registered**; it is written to be registrable later:

```sh
run_check "wait gate test" "$python" logs/p31/check_wait_gate.py
```

The stub's layers (95 checks):

1. **Knob resolution** - the real `from_env`, exec'd, over 8 env rows (unset, 0,
   `off`, `true`, 1, the sub-knobs, the `warm` floor, the `past` clamp) plus the
   malformed-value-off/on pair; frozen dataclass; the default threshold pinned.
2. **Default-off byte inertness** - the `b1acbfe` statement/test identity of
   `sample_chunk`/`act`/`_finalize`, the domination of every new statement, and
   the call-site reachability of the four new methods.
3. **The predicate** - `dist` at/below/above, NaN, the `warm` gate, `past` off /
   at / past the bound, `dist=0`, and the full-transit transition count (1 and 2).
4. **The hold semantics** - the real `_wait_gate_hold` on a fake env: the exact
   held array (16x9, every row the last action), not-zero, the counters,
   `along0`, the resume latch, the recycle re-arm, the warm guard, and the 7
   scope refusals.
4b. **The accounting invariant** - two loop replays of the measured transits
   (a fired attempt 0.545 -> 0.234 m and a no-fire 0.482 -> -0.88 m): every
   skipped call is 4 held ticks, `skipped + calls == chunks`, one resume, and the
   counts match the anatomy (50 of 79 = 63 %; 34 of 341 = 10 %).
5. **The skip site** - the source order in `sample_chunk` (after ready / ablate /
   RTC, before `policy.act`), one model call site, one counter increment.
6. **The `[gate]` row** - the real printer executed: the eight fields, the
   `along0=-` rule.
7. **Provenance** - the manifest block, the outcome keys, `_DIAG`-only printing,
   the per-episode reset, `inference_calls` unchanged, the tick booking, and
   `TASKS_MD5 == md5(tasks.py)`.

## 4. The `[gate]` row

```
[gate] episode 7 skipped=40 held=160 calls=83 along0=+0.545 dist=0.350 past=0.000 resumed=1
```

`skipped` = model calls replaced this episode, `held` = control ticks executed on
a held chunk (nominally `4 x skipped`), `calls` = the P30-B counter
(`inference_calls`, the calls that *did* run), `along0` = the fruit's along
distance at the first held call (`-` when the gate never held), `resumed` = the
gate held and then reopened. The saving is `skipped / (skipped + calls)`.

## 5. What was not done, and why

* **No simulator run** (accept / canary / demo / A/B): the lane is offline by
  instruction. The owed measurement is `WAIT_GATE_DESIGN.md` section 8.
* **No `WORKLOG.md` edit**: this lane's write scope is the two sources and
  `logs/p31/`. The append-ready entry is `logs/p31/WORKLOG_ENTRY.md`.
* **No selfcheck registration** (`scripts/selfcheck.sh` out of scope).
* **`FRUIT_WAIT_GATE_PAST` stays 0** - measured as the bigger share of a no-fire
  attempt (60 % of its chunks) but it interacts with
  `FRUIT_POLICY_TRIGGER_PRESENT`' adoption and needs its own pre-registration.
* **No `act(None)` hold** - it would skip `_apply`, and `_apply` is where the
  fire machinery runs (design section 3).
* **No neutral grasp-pose action** - it commands a motion, so it is a different
  experiment (design section 3).
* **No change to `tasks.py`** - nothing in the gate needs the task, and the
  `TASKS_MD5` pin therefore stays (`e27b18a4...`).

## 6. Blocker / next

Blocker: none for the implementation. The measurement needs a simulator slot; the
lane was told to stay offline, so the A/B is the next block's first item.

Next, in order: (1) the N=5 paired direct A/B with `FRUIT_WAIT_GATE_DIAG=1` on the
treatment arm (design section 8); (2) the `FRUIT_WAIT_GATE_DIST` ladder 0.25 /
0.35 / 0.45 on the same battery if the primary endpoints hold; (3) the
`FRUIT_WAIT_GATE_PAST` pre-registration (the no-fire tail, with the `PRESENT`
interaction resolved first); (4) the tree-level no-harm acceptance.
