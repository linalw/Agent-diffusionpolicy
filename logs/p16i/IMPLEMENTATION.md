# P16-I implementation: the completed descent (pick (a)) — `FRUIT_DYNAMIC_ARRIVE_TOL` / `_MAX` + the `[arrive]`/`[boundary]` rows (default off, dynamic-capture scoped)

Status: **implemented and verified offline only** (branch `p-supply`, 2026-10-19). No simulator run,
no commit; writes only to `src/fruit_sorting/tasks.py`, `src/fruit_sorting/rl_env.py` (the
`TASKS_MD5` pin) and `logs/p16i/`. The Stage-M screen (`logs/p16/BOUNDARY_DESIGN.md` section 4) is
a separate lane and is **not run here** — this lane delivers the `src/` change and its offline
identity/stub evidence.

The design this implements: `logs/p16/BOUNDARY_DESIGN.md` section 2.1 (option (a) "the completed
descent — the arrival closed-loop at the aim") + the pick in section 4. The mission: after the
jerk-limited descent profile, re-command the aim until the measured TCP error ≤ the tolerance or
the tick cap runs, **before** the catch-up/capture; plus the `[arrive]`/`[boundary]` observability.

---

## 1. The diff summary

| file | before md5 | after md5 | diff |
| --- | --- | --- | --- |
| `src/fruit_sorting/tasks.py` | `810658b802d22bbd63013726fc78af81` | `54f70584b07fa249418f1efe30f30af0` | +179 / −2 lines |
| `src/fruit_sorting/rl_env.py` | `9a2c38721b32f0af91371ca3e8809196` | `be0248e0c3b88b28b0ec47ff28e1b68c` | +1 / −1 line (the `TASKS_MD5` pin only) |

Unchanged pins (verified): `src/fruit_sorting/fruits.py` `d28546d26137d4540421caa7fa34a139`,
`src/fruit_sorting/meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`. No other file is modified
(`git status`: the two files above only). The full diff is `logs/p16i/implementation.diff`.

The change has four pieces (all default-off and byte-inert at default):

1. **The knob block** (`PickAndPlaceTask.__init__`, tasks.py:609-641): `self._dynamic_arrive_tol`,
   `self._dynamic_arrive_max`, `self._dynamic_arrive_diag` — three env knobs, read exactly once
   each with the shipped defaults.
2. **`_arrive_hold`** (a new method, tasks.py:10088-10126): the bounded closed-loop arrival.
3. **`_approach` integration** (tasks.py:10129-10132 signature, 10429 the call, 10431-10446 the
   diag-only `end=` readback, 10488 the return): the moving catch passes the knobs; every other
   `_approach` call keeps the defaults and is byte-unchanged. With the loop active the motion
   row's `end=` is the **settled** gap (the completed descent's residual).
4. **The moving-catch call site + the rows** (tasks.py:7302-7374): the knobs are passed only under
   `dynamic_capture`; the `[arrive]`/`[boundary]` rows print under `FRUIT_DYNAMIC_ARRIVE_DIAG=1`.

## 2. The knob semantics

| knob | default | meaning |
| --- | --- | --- |
| `FRUIT_DYNAMIC_ARRIVE_TOL` | `"0.0"` | Arrival tolerance [m]. `> 0` **and** `_MAX > 0` enables the loop; `0` (or any negative, clamped) = **off** = the shipped profiled descent byte-for-byte. The pre-registered battery value is `0.006`. |
| `FRUIT_DYNAMIC_ARRIVE_MAX` | `"0"` | Tick cap of the arrival loop. `0` = off (either knob can disable). The pre-registered battery value is `24`. |
| `FRUIT_DYNAMIC_ARRIVE_DIAG` | `"0"` | `=1` prints the pure-reporting `[arrive]` row (per dynamic descent that ran the loop) and the `[boundary]` row (per dynamic descent, control included). Off = no new output. |

**The loop** (check-then-command, one `ik_step` + one physics tick per used tick):

```
residual = tcp_position() - target;  gap = |residual|
for up to max_ticks:
    if gap <= tol: break
    arm.ik_step(target); self._step_sim(1); ticks += 1
    residual = tcp_position() - target; gap = |residual|
```

- the residual is the same quantity the motion monitor reports as `end=`: the measured TCP against
  `arm.tcp_target_for_jaw(grip)` computed once at the leg start;
- the loop stops early at the tolerance (`<=`, 0 ticks when already inside) and never exceeds the
  cap; the returned tuple is `(start_gap_m, settled_gap_m, ticks, residual_vec)`;
- it reuses the profile's own primitives (`ik_step` + `_step_sim`), so under `FRUIT_DYNAMIC_TRACE`
  / proximity tracing it steps through the same wrapped `self._step_sim` the profile uses;
- the catch-up (the post-descent solver) is untouched: same 6 mm tolerance, same
  `FRUIT_DYNAMIC_CATCH_TICKS` budget; it simply starts from the arrived pose.

**The scope** (exact, by construction):

- the knobs are passed to `_approach` **only** from the moving catch's call (tasks.py:7315-7330)
  and **only** when `dynamic_capture` is true (`... if dynamic_capture else 0.0` / `else 0`);
- the pre-grasp `_approach(arm, free, verbose=verbose)` call (in `_run_impl`) passes nothing →
  the signature defaults `arrive_tol=0.0, arrive_max=0` → the helper returns `None` immediately;
- the direct/policy handover keeps its `skip_approach` default (no descent → no arrival); with
  `FRUIT_DIRECT_SKIP_APPROACH=0` it is a dynamic capture and the knob applies (documented scope);
- the `[arrive]`/`[boundary]` rows are gated on `self._dynamic_arrive_diag and dynamic_capture
  and (not skip_approach)`.

**The byte-inert proof at default** (offline): with `tol=0` or `max=0` the helper's first
statement returns `None`; the stub executes the real method against an arm/hook that raise on any
attribute access and shows neither is touched. `report_end` is `False` at default (the diag is
off), so `_approach` performs no extra `tcp_position()` read either. The only default-path change
is one no-op method call + two local assignments.

## 3. The code sites (at the new md5 `54f70584`)

| site | lines | what |
| --- | --- | --- |
| `__init__` knob block | 609-641 | the three knobs, one read each, negative-clamped |
| moving-catch call site | 7302-7374 | `end_gap_m, arrive_info = self._approach(..., arrive_tol=..., arrive_max=..., report_end=...)` under `dynamic_capture`; the row block |
| `_arrive_hold` | 10088-10126 | the bounded arrival loop (the design's `ik_step(target)` + `_step_sim(1)`) |
| `_approach` | 10129 (signature), 10429 (the call), 10431-10446 (`report_end` readback), 10488 (return) | the call sits right after the if/elif/else profile branches and **before** the monitor block, so the motion row's `end=` is the settled gap when the loop ran |
| pre-grasp call (unchanged) | `_run_impl` `self._approach(arm, free, verbose=verbose)` | passes no arrival keywords |

## 4. The observability rows (both `FRUIT_DYNAMIC_ARRIVE_DIAG=1`)

```
[arrive] <arm> idx=<i> start=<s>mm settled=<f>mm ticks=<n> dx=<+x>mm dy=<+y>mm dz=<+z>mm
[boundary] <arm> idx=<i> end=<e>mm reach_dn=<+d>mm reach_up=<+u>mm belt_margin=<+m>mm
```

- `[arrive]` — per dynamic descent **that ran the loop** (`arrive_info is not None`): the
  pre-arrival `end=` gap (`start=`, the shipped shortfall), the settled gap (`settled=`), the
  ticks used, and the settled residual's signed direction in mm. When the loop ran with 0 ticks
  (the descent already inside the tolerance) the row prints `ticks=0` with `start == settled`.
- `[boundary]` — per dynamic descent, control included (arrival off prints the shipped shortfall):
  `end=` is the completed descent's residual (exactly the number the motion row's `end=` reports —
  the same target, the same recipe); `reach_dn`/`reach_up` are the aim's station-relative y against
  the shipped `_reach_band_for` R10 column for the fruit's measured x (positive = inside the
  band); `belt_margin` is the design's finger–belt margin `aim jaw z − (belt_top + finger_len)`
  (the fingertip height above the belt top at the aim; positive = clear).
- Both rows are pure reads at a phase boundary (one fruit-pose read for the band column); no
  per-tick readback, no control effect (pinned by the stub: no `self.<attr> =`, no `ik_step`, no
  `_step_sim` inside the row block).

## 5. What the screen lane needs (the screen is deferred)

The Stage-M screen (`logs/p16/BOUNDARY_DESIGN.md` section 4) is **not run by this lane**. When the
screen lane runs it:

- **H1's env line** should add `FRUIT_DYNAMIC_ARRIVE_DIAG=1` to the design's reporting env (the
  rows are diag-gated per the repo convention), i.e.
  `FRUIT_DYNAMIC_ARRIVE_TOL=0.006 FRUIT_DYNAMIC_ARRIVE_MAX=24 FRUIT_DYNAMIC_ARRIVE_DIAG=1`;
- the pre-registered mechanism endpoint "(i) the descent's `end=`" is read from the **motion
  rows' `end=`** (now the settled gap when H1 runs) and/or the `[arrive] settled=` column; the
  `[arrive] start=` column equals the control's `end=` (the pre-arrival shortfall), so the
  control's `end=` distribution (8.3-15.3 mm, med 9.4 at seed 11) is the comparison baseline;
- the `[boundary] belt_margin` column is the H1 risk check ("must not drive the small-fruit
  margin negative"); the reach margins are reported for completeness (the aim is inside the band
  on the mass base by the design's section 1.4);
- the motion monitor's `steps`/`|v|max`/`a_*` still describe the **profile** leg only (the arrival
  ticks are not added to the monitor), so the motion-gate budgets read as before; the extra ticks
  are visible in `[arrive] ticks=`.

## 6. The verification (offline; all PASS)

```bash
python3 -m py_compile src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py   # OK
scripts/selfcheck.sh                                                            # PASS 0 failures, 1 skipped (motion budgets: needs a run log)
python3 logs/p16i/check_arrive.py                                               # PASS (new stub)
python3 logs/p10c/check_twoline_scope.py                                        # PASS
python3 logs/p10c2/check_confirm_gate.py                                        # PASS
python3 logs/p9a/check_skip_predicate.py                                        # PASS
python3 logs/p10c3/check_flip_resolution.py                                     # PASS
python3 logs/p11c/check_regrasp_from_open.py                                    # PASS
```

Evidence files: `logs/p16i/check_arrive_output.txt` (the new stub's full output),
`logs/p16i/selfcheck_summary.txt` (the post-change selfcheck legs), `logs/p16i/implementation.diff`
(the full diff).

**The new stub** (`logs/p16i/check_arrive.py`, run-anywhere, no simulator) pins:

1. *the knob resolution*: the three `__init__` statements are exec'd under env values — unset →
   `0.0`/`0`/`False`, the battery values `0.006`/`24`/`1`, `0` → off, negatives clamped to off;
2. *the default-off byte-identity*: `_arrive_hold` returns `None` for every off combination
   (tol 0, max 0, both, negatives) against an arm and a stepping hook that raise if touched; the
   `_approach` signature defaults; the pre-grasp call passes no arrival keywords; the row block
   prints nothing with the diag off / non-dynamic / skipped descent;
3. *the arrival loop's logic on synthetic residuals*: the **real** `_arrive_hold` is exec'd
   against a synthetic first-order arm and compared against an independent check-then-command
   reference — converges and stops at the tol (10 mm → 6 mm in 2 ticks), already arrived (0
   ticks), edge equality (0 ticks), never converges (caps at the max), single-tick overshoot, an
   off-diagonal residual keeps its direction; one `ik_step` + one `_step_sim` per used tick, all
   commands at the aim;
4. *the rows' format*: the **real** `[arrive]`/`[boundary]` statements are exec'd with synthetic
   bindings and compared against an independent reference (exact strings + the margin arithmetic,
   including negative margins outside the band / below the belt); `[arrive]` only prints when the
   loop ran; the control (arrival off) prints only `[boundary]` with the shipped shortfall;
5. the scope source checks (the conditional knob pass, the row gating, the two call sites, the
   monitor `end=` order) and `rl_env.TASKS_MD5 == md5(tasks.py)`.

## 7. Honest notes and limitations

- **No simulator evidence in this lane.** The arrival's *effect* (the `end=` moving, the catch-up's
  inherited residual, the hold walk, the belt margin on small fruit) is exactly what the Stage-M
  screen measures; this lane only establishes the implementation identity and the loop logic.
- **The `end=` semantic under the knob**: with H1 on, the motion row's `end=` is the settled gap
  (the design's "the completed descent"). With the knob off, the number is the shipped shortfall —
  byte-identical. A screen must not compare an H1 `end=` against a control `end=` without noting
  that the former includes the arrival ticks (the `[arrive] start=` column is the like-for-like
  baseline).
- **The monitor's sample count** (`steps=`) still counts the profile's ticks; the arrival ticks
  are not folded into the motion row (the design calls the arrival a bounded settle, not a leg).
  If the motion gate is ever pointed at an H1 log, this is the interpretation to use.
- **The direct handover** reaches the arrival only with `FRUIT_DIRECT_SKIP_APPROACH=0` (its default
  skips the descent); the two-line scripted catch is a dynamic capture and inherits the knob when
  set (documented scope, same as the other dynamic-catch knobs).
- The `[boundary]` reach margins use the shipped `_reach_band_for` (the R10 map inset by
  `FRUIT_REACH_Y_INSET=0.02`); the design's "R10 columns" reading is against that shipped
  accessor.
