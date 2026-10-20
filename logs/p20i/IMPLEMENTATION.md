# P20-C implementation: the B1c feeder re-anchor (`FRUIT_READY_SKIP_RESYNC`)

Status: **implemented, default off, offline-verified; Tier-C implementation lane
(2026-10-20).** No simulator run was made in this lane (a Tier-A battery is in
flight), so the pre-registered no-harm bar (acceptance 9/10 + `fingerprint:
matches`, the 385/385 `[fruit]` identity) is **not re-measured here** - it is the
battery's first job (section 7). The design is `logs/p20/B1C_DESIGN.md` section
4.1 (form (b), the recommended form).

Branch `p-supply`. Pins at hand-off:

| file | md5 |
| --- | --- |
| `src/fruit_sorting/tasks.py` | `455f1a33b9e943d18fffae797053ebd6` |
| `src/fruit_sorting/rl_env.py` (`TASKS_MD5` follow) | `88bcde2748b76dcfa5782266987b6ec9` |
| `src/fruit_sorting/fruits.py` (**untouched**) | `d28546d26137d4540421caa7fa34a139` |
| `configs/motion_reference.json` (**untouched**) | `b9e72ca7` (the design's pin) |
| `configs/motion_reference_twoline.json` (**untouched**) | `181c9151` |

The pin before this lane was `tasks.py` `3d88408d` (the design's pin) /
`rl_env.py` `97a40185`. **Concurrent-tree caveat:** a second lane is editing the
same file in this checkout (`FRUIT_RELEASE_PAD_HOLD` / `FRUIT_RELEASE_FINGER_HOLD`
in `_release_pads`/`_release_gripper`, both defaulting to the shipped literal
`3`; they are the two FOREIGN hunks in `logs/p20i/05_diff.patch`, excluded from
`logs/p20i/06_diff_mine_only.patch`). Its pin attempt (`97a40185`) did not match
any tree state this lane can reconstruct (`HEAD` + those two hunks = `f0fa5d6e`).
`rl_env.py`'s `TASKS_MD5` is therefore set to the **hand-off** md5 above; if that
lane edits `tasks.py` again, re-follow the pin (the new stub fails loudly until
someone does).

---

## 1. What changed (the whole diff)

`logs/p20i/05_diff.patch` is the full working-tree diff; `logs/p20i/06_diff_mine_only.patch`
is this lane's 9 hunks with the other lane's 2 hunks removed. Mine, in order:

| site | lines | what |
| --- | --- | --- |
| `PickAndPlaceTask.__init__` | 743-757 | `self._ready_skip_resync` (one env read, default off) and `self._ready_skip_credit = 0` |
| class constants | 1634-1648 | `READY_TRANSIT_BLEND_TICKS = 90`, `READY_CATCH_UP_TICKS = 20`, `READY_CATCH_UP_TOL = 0.01` + the comment pinning them to `_transit_to` / `_catch_up_drive` |
| `_ready_transit_ticks(dg)` | 3811-3824 | the exact skipped-tick count |
| `_resync_supply_clock(ticks)` | 3826-3871 | the credit: `spawner._next_release -= ticks * CONTROL_DT` |
| `_ready_move` skip branch | 3941-3944 | `if self._ready_skip_resync: debt = ...; if debt > 0: self._resync_supply_clock(debt)` |
| `_ready_move` docstring | 3892-3897 | the knob's semantics |
| `go_ready` docstring | 3748-3752 | the knob in the P9-A knob list |
| `_ready_report` | 3966-3988 | the `credit=<ticks>` diag field, gated on the knob |

`rl_env.py` is the one-line `TASKS_MD5` follow. `fruits.py` is byte-untouched
(md5 unchanged; the stub asserts that no `_supply_shift` /
`advance_supply_clock` exists, so the design's form cannot later be added on top
and double-credit).

## 2. Semantics

### 2.1 What the lever does to the supply

The scattered feeder releases on an **absolute** schedule
(`FruitSpawner._next_release`, one drawn gap per due slot) and the driver pumps
it only inside each attempt's 60-tick feed window, so the presentation at every
poll is a pure function of the **pump instant** against that grid:

```
period = _release_gap()/v            (a gap drawn in metres, 0.10-0.35 m)
late   = sim_time - _next_release    (the age of the newest due slot)
along  = spawn_y - min(late*v, 1.60) (a backlog slot is delivered where it
                                      would have reached)
```

A skip that removes `D` ticks from the gap moves the pump instant `D` ticks
earlier on the grid. Because the skip fires at **every** gap, the offset is
cumulative: `230 ticks = 1.917 s = 0.230 m` = 82 % of the selector's usable
band (0.281 m) per gap, 1.84 m by slot 8. That is the B1 empty-poll class
(`logs/p20/B1C_DESIGN.md` sections 2-3).

### 2.2 The fix

Credit the same `D` to the feeder's *schedule* clock at the skip site: the pump
instant is then the same **virtual** time the shipped run had it, i.e. the
supply is pre-delivered by exactly the dead time the lever removed, while the
arm's gap keeps the saving. Nothing waits (`logs/p20/B1C_DESIGN.md` section 9,
disagreement 1).

### 2.3 The debit is code-exact, not a constant

`_ready_transit_ticks(dg)` returns what the shipped transit would actually have
run for that arm:

| stage | ticks | condition |
| --- | --- | --- |
| `_catch_up_drive` | 20 | only when its measured gap > 0.01 rad - the same `dg` the skip predicate reads (`_ready_residuals` returns exactly `_catch_up_drive`'s `max|q_target - q_measured|`) |
| `_blend_to` ramp | 90 | always (`_transit_to`'s `ticks` default) |
| `_blend_to` settle | `_ready_settle()` | shipped 120, `FRUIT_READY_SETTLE` overrides |
| `_ready_transit`'s lift | 0 | not reached: it returns early below `READY_STAGE_ERR` 0.35, far above the skip's `READY_SKIP_TOL` 0.03 |

So `K = 210` when `dg <= 0.01` and `K = 230` when `dg > 0.01` (the battery runs
`FRUIT_READY_SKIP_DG=0.02` and measures `dg` 0.0131-0.0135, so its rows are the
230 ones; a `FRUIT_READY_SETTLE` override rides along: 60 -> 170).

### 2.4 The placebo stays byte-identical

`debt = K - max(0, hold)` and the `FRUIT_READY_SKIP_HOLD` loop runs **before**
the credit, so:

* `HOLD=230` (`dg > 0.01`): the hold inserts 230 ticks of dead sim time and the
  credit is 0 - the arm's gap is the shipped one *and* the pump instant is the
  shipped one, i.e. exactly the P9-A P arm;
* `HOLD=0`: the gap shrinks by `K` and the pump instant does not move.

The identity is worth stating because it is the whole difference between this
form and the placebo: with the hold, `sim + hold + credit = sim + K` either way,
so the **pump phase is invariant to the hold** and the hold only spends wall
time.

### 2.5 The algebraic form (the deviation)

The design asks for `FruitSpawner.advance_supply_clock(dt)` - a `_supply_shift`
added to `sim_time` at the pump's four schedule sites. This lane may only write
`tasks.py`, so the shift is applied to the **other** side of the same four
comparisons, once, at the skip site:

```
spawner._next_release -= ticks * CONTROL_DT      # == t -> t + shift at the pump
```

The two forms are the same operation. Every one of the four sites is affine in
the cursor:

| pump site (`fruits.py`) | with the design's shift `s` | with `cursor' = cursor - s` |
| --- | --- | --- |
| `while sim_time >= _next_release` | `sim + s >= cursor` | `sim >= cursor - s` |
| `late = sim_time - _next_release` | `late = sim + s - cursor` | `late = sim - (cursor - s)` |
| `max(_next_release, sim_time + period)` (queue interlock) | `max(cursor, sim + s + p)` | `max(cursor - s, sim + p)` |
| `max(_next_release, sim_time + _release_period())` (top-up) | idem | idem |

Every read/write of the cursor is one of those four (the stub pins that by AST:
the only writers are `__init__`, `reset`, `update` (the pre-v9 fixed branch) and
`_pump_supply`), and everything real-time (`_last_sim_time`, `_waited`,
`_tray_dwell`, the recycle/despawn position tests) stays on `sim_time` in both
forms, so nothing physical moves. The stub proves the equivalence end to end on
the shipped gap band: the control stream and the shift-form stream and the
cursor-form stream produce identical `late`/`along`/due/released/past/consumed
draws over 10 slots (section 5, layer 6).

The credit is also gated to the **scattered pump** (`supply.scatter and
supply.stream`, exactly `FruitSpawner.update`'s own gate): the pre-v9 fixed line
resets its cursor on every release, has no phase to preserve, and must not
inherit a shift.

### 2.6 The reference is the pump instant, not the position

The re-anchor makes the **presentation** equal to the shipped branch's, not the
arm's micro-history: `logs/p20/B1C_DESIGN.md` section 2.6 measures a 15 mm
lateral / 3 mm along / 0.6 s-span perturbation at an identical clock, which
re-phases the next poll by ~0.07 m. So the expected outcome is "zero systematic
debt, plus-or-minus 0.07 m of per-attempt wander" - the battery's endpoint 1
(the presentation stream) is the only readout that can tell a correct re-anchor
from a lucky branch.

## 3. The readout (the battery's check that the re-anchor took)

Behind `FRUIT_READY_DIAG=1` (the existing ready gate), each `[ready]` line gains
one trailing field **only when the knob is on**:

```
[ready] left skip=1 staged=0 pre_err=0.0131 dg=0.0135 catch_up=0 lift=0
        blend=0 settle=0 ramp_err=0.0000 post_err=0.0131 rec=0 end_err=0.0131
        credit=230
```

`credit=` is the session-cumulative tick credit (an integer sum of the exact
debits, so it is checkable against the slot count: slot `k` should read
`k * 230` on the acceptance). With the knob off the line is byte-identical to
the P9-A format (the stub checks the base field string; `logs/p9b/ready_summary.py`'s
regex is unanchored, so the new trailing field does not disturb it).

The design's own falsifier (`late_lo` per poll from `FRUIT_SUPPLY_DIAG=1`) is
readable **unchanged**: this lane did not touch `fruits.py`, so the
`[supply-diag]` line keeps its format and the re-anchor shows up as the `late=`
band tracking arm A's instead of ramping by 1.92 s per gap.

## 4. Verification (offline; every artifact under `logs/p20i/`)

| check | result | artifact |
| --- | --- | --- |
| `python3 -m py_compile src/fruit_sorting/{tasks,rl_env}.py` | PASS | `01_py_compile.txt` |
| `scripts/selfcheck.sh` (all 21 legs) | **PASS: 0 failures, 1 skipped** (the motion leg needs a run log) | `02_selfcheck.txt`, `02_selfcheck.log` (via `SELFCHECK_LOG=`) |
| the seven existing stubs (p10c, p10c2, p9a, p10c3, p11c, p16i, p17i) | 7/7 PASS | `03_stubs.txt` |
| **new** `logs/p20i/check_resync.py` | PASS (all checks) | `04_check_resync.txt` |

The new stub's layers, and what each one pins:

1. **Source.** One env read with default `"0"`; the P9-A knobs keep one read
   each (SKIP / SKIP_DG / SKIP_HOLD / SETTLE); both helpers defined once; the
   debit expression appears once and *inside* the knob guard; the guard sits
   inside the skip branch, after the placebo hold, before its `return`; the
   `[ready]` suffix is gated while the P9-A fields are intact; the constants
   still equal the real call-site defaults (`_transit_to` `ticks=90`,
   `_catch_up_drive` `ticks=20`) and `_catch_up_drive`'s `gap <= 0.01` early-out
   is still the literal; `fruits.py` has no `_supply_shift` /
   `advance_supply_clock`; the cursor's writers are the shipped four; the pump's
   four sites are still on `sim_time`.
2. **Knob resolution** (the REAL `__init__` statement, exec'd): unset / `"0"` /
   `"1"` / `"true"` / `"yes"` -> `False` except the literal `"1"` (the P9-A
   convention, so a typo cannot arm a physics change).
3. **The debit** (the REAL `_ready_transit_ticks`, exec'd) over the battery's
   `dg` band, the `dg = 0.01` edge, and the settle override, against an
   independent reference: 210 / 230 / 170 / 150. It states the deviation
   explicitly: the design's flat `20 + 90 + 120 = 230` over-credits the
   `dg <= 0.01` rows by 20 ticks.
4. **The credit** (the REAL `_resync_supply_clock`, exec'd): knob off -> 0 and a
   raising spawner mock proves nothing is touched; knob on -> the cursor moves
   by exactly `ticks/120` s, accumulates exactly (230 + 210 = 440), `ticks <= 0`
   / no spawner / non-pump supply credit 0 and leave the cursor alone.
5. **The skip site** (the REAL guarded block, exec'd): one skip credits 230
   exactly once; `HOLD=230` credits 0 and leaves the cursor at 0.0 (the placebo);
   `HOLD=100` credits 130; `dg <= 0.01` credits 210; five skips credit 1150 with
   no drift; knob off runs neither helper (booby-trapped) and leaves the cursor
   untouched.
6. **End to end** (a faithful model of `_pump_supply`'s algebra over the shipped
   gap band, 10 slots): the control and the re-anchored stream (driven through
   the REAL `_resync_supply_clock`) have identical due/released/past, identical
   `late`/`along` and identical draw consumption (29 released slots, 108 gaps
   drawn); the design's `_supply_shift` form is identical to the cursor form; the
   un-anchored lever is **not** the control stream; the virtual pump instant
   equals the control's at every slot (max delta 0.0 s); the debt ladder is
   0.23/0.46/.../1.84 m at slots 0-7.

`logs/p20i/03_stubs.txt` records the seven pre-existing stubs as PASS **after**
this change, including `logs/p9a/check_skip_predicate.py` (which pins the B1
predicate, the scope gate and the placebo text) - i.e. the P9-A lever is
untouched.

**What is NOT verified offline, stated plainly:** the acceptance no-harm
(9/10 + `fingerprint: matches` + the 385/385 `[fruit]` identity), the two-line
dense re-record, and any claim about the poll class, the wall or the outcome.
The offline evidence is that the *default* tree executes none of the new code
and that the shipped artifacts (`fruits.py`, `configs/*`) are byte-identical; the
behavioural no-harm needs the battery's arm A.

## 5. Scope and known limits

* Single arm only, by the skip's own predicate (`self._active_session is None
  and not self.two_line_enabled()`, unchanged). The two-line paths never reach
  the credit.
* Meaningful only with `FRUIT_READY_SKIP=1 FRUIT_READY_SKIP_DG=0.02` (the
  pre-registered B arm). Alone the knob does nothing.
* The credit accumulates per skip for the life of the spawner's schedule. The
  shipped driver calls `spawner.reset()` **once, before the first `go_ready`**
  (`scripts/20_pick_place.py:115` then `:119`), so the absolute schedule and the
  credit start together; `scripts/60_eval_policy.py:140` and
  `rl_env.py:706` reset at construction for the same reason. A caller that
  resets the spawner mid-session would lose the offset (the schedule restarts
  from 0, which is the correct anchor) while the *readout* kept its total - no
  shipped path does that.
* `FRUIT_READY_SKIP_HOLD` keeps its P9-A meaning; `HOLD=230` with
  `SETTLE<120` over-compensates (the hold is a constant, the debt is not),
  unchanged from P9-A.
* The knob is not routed through `_dynamic_profile`: the whole P9-A family is
  plain env (`SKIP`, `SKIP_DG`, `SKIP_HOLD`, `SETTLE`), so a future adoption flip
  would be a new decision, not a one-literal edit.

## 6. What the battery should run (unchanged from the design's section 5)

```
A  (shipped)
B  FRUIT_READY_SKIP=1 FRUIT_READY_SKIP_DG=0.02 FRUIT_READY_SKIP_RESYNC=1
P  B + FRUIT_READY_SKIP_HOLD=230          # now credits 0 -> reproduces P9-A P
diag  FRUIT_READY_DIAG=1 FRUIT_SUPPLY_DIAG=1   (one run per arm, run-neutral)
```

with endpoint 1 (the presentation stream) as the mechanism verdict, the
empty-poll count, the clean-gap p50 (`>= 1.5 s` saving per seed), the pooled
3-seed placement, and the `credit=` ladder as the "it took" check. The
no-harm bar: acceptance 9/10 + fingerprint + 385/385 vs
`logs/p9a/90_acc_A_1.log`, patch A 681/681 vs `logs/p9a/96_pat_A_1.log`, the
two-line dense 442/442 + `scripts/190_twoline_gate.sh`, `selfcheck.sh`.

## 7. Provenance

Design: `logs/p20/B1C_DESIGN.md` (sections 0, 1, 4.1, 5). Prior record:
`logs/p9a/B1_RESULTS.md`, `logs/p9a/PREREG_ADDENDUM_DG.md`,
`logs/p9/PREREG_GOREADY_B1.md`. Stub: `logs/p20i/check_resync.py`. Artifacts:
`logs/p20i/{00_tree_pins,01_py_compile,02_selfcheck,03_stubs,04_check_resync}`,
`logs/p20i/{05_diff,06_diff_mine_only}.patch`, `logs/p20i/WORKLOG_ENTRY.md`.
