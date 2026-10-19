### P16-I (2026-10-19, branch `p-supply`, offline): the completed descent (P16 pick (a)) implemented — `FRUIT_DYNAMIC_ARRIVE_TOL`/`_MAX` (default off, dynamic-capture scoped) + the `[arrive]`/`[boundary]` rows; the Stage-M screen is a separate lane and is deferred

**Scope: offline implementation + verification only.** No simulator run; writes only to
`src/fruit_sorting/tasks.py`, `src/fruit_sorting/rl_env.py` (the `TASKS_MD5` pin) and `logs/p16i/`;
no commit. This is the execution of `logs/p16/BOUNDARY_DESIGN.md` section 2.1 / the pick in
section 4 (option (a), the only option that moves the descent's `end=` — the quantity no prior
lever moved — and it sits **upstream of the capture**, so a conversion cannot trade by
construction). The pre-registered Stage-M screen at SEED 11 (H1 against the on-disk traced
control, one promoted arm → the outcome battery at SEED 11/5/23) is **not run here**: it needs
the simulator and is a separate lane. Deliverable: `logs/p16i/IMPLEMENTATION.md` + the diff
(`logs/p16i/implementation.diff`) + the new stub (`logs/p16i/check_arrive.py`).

**What shipped (all default-off, byte-inert at default).** (i) The three knobs read once in
`__init__`: `FRUIT_DYNAMIC_ARRIVE_TOL` (default `"0.0"`, negative-clamped), `FRUIT_DYNAMIC_ARRIVE_MAX`
(default `"0"`), `FRUIT_DYNAMIC_ARRIVE_DIAG` (default `"0"`, pure-reporting rows only). (ii) The new
`_arrive_hold(arm, target, tol, max_ticks)` method: the bounded closed-loop arrival — re-command
the aim (`arm.ik_step(target)` + one `self._step_sim(1)` per tick, the profile's own primitives)
until the **measured** TCP error against the aim is ≤ tol or the cap has run; returns
`(start_gap, settled_gap, ticks, residual_vec)`; the off gate is the first statement
(`if tol <= 0.0 or max_ticks <= 0: return None`), so with the shipped defaults neither the arm
nor the stepping hook is touched. (iii) The `_approach` integration: three new default-off
parameters (`arrive_tol=0.0`, `arrive_max=0`, `report_end=False`) and the `_arrive_hold` call
placed **after** the jerk-limited profile and **before** the monitor block — so with the loop
active the motion row's `end=` is the *settled* gap (the completed descent's residual), and the
return is `(end_gap_m, arrive_info)`. Only the moving catch's call site (tasks.py:7315-7330)
passes the knobs, and only under `dynamic_capture` (`... if dynamic_capture else 0.0`/`else 0`);
the pre-grasp `_approach(arm, free, verbose=verbose)` call passes nothing and is byte-unchanged.
(iv) The observability: `[arrive] <arm> idx=<i> start=<mm> settled=<mm> ticks=<n>
dx/dy/dz=<±mm>` per dynamic descent that ran the loop, and `[boundary] <arm> idx=<i>
end=<mm> reach_dn=<±mm> reach_up=<±mm> belt_margin=<±mm>` per dynamic descent (control included:
`end=` is then the shipped shortfall) — the aim's station-relative y against the shipped
`_reach_band_for` R10 column at the fruit's measured x, and the design's finger–belt margin
`aim jaw z − (belt_top + finger_len)`. Both rows are behind `FRUIT_DYNAMIC_ARRIVE_DIAG=1`, pure
reads at a phase boundary, no control effect.

**Verification (offline; all PASS).** `python3 -m py_compile` OK; `scripts/selfcheck.sh` **PASS
0 failures / 1 skipped** (the skip is the run-log motion gate); the five existing stubs
(`logs/p10c/check_twoline_scope.py`, `logs/p10c2/check_confirm_gate.py`,
`logs/p9a/check_skip_predicate.py`, `logs/p10c3/check_flip_resolution.py`,
`logs/p11c/check_regrasp_from_open.py`) all PASS; the new stub `logs/p16i/check_arrive.py`
PASS. The new stub pins the knob resolution (unset / the battery values 0.006+24 / off /
negatives clamped), the default-off byte-identity (the real `_arrive_hold` returns None for
every off combination against a raising arm/hook; the signature defaults; the pre-grasp call
has no arrival keywords; the row block is silent with the diag off / non-dynamic / skipped
descent), the arrival loop's logic on synthetic residuals against an independent
check-then-command reference (converges and stops at the tol; already arrived → 0 ticks; edge
equality → 0 ticks; caps at the max; overshoot; off-diagonal direction; one command + one tick
per used tick), the rows' exact format and margin arithmetic (including negative margins), and
`rl_env.TASKS_MD5 == md5(tasks.py)`.

**Pins.** `tasks.py` `810658b802d22bbd63013726fc78af81` → **`54f70584b07fa249418f1efe30f30af0`**
(+179/−2 lines); `rl_env.py` `9a2c38721b32f0af91371ca3e8809196` →
**`be0248e0c3b88b28b0ec47ff28e1b68c`** (the `TASKS_MD5` follow, +1/−1 line); `fruits.py`
`d28546d26137d4540421caa7fa34a139` and `meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`
unchanged. The design's pins (`logs/p16/BOUNDARY_DESIGN.md` header) were read at the pre-change
`tasks.py`; the design's line citations shift by the diff (the sites are re-listed in
`logs/p16i/IMPLEMENTATION.md` section 3).

**What the screen lane needs.** H1's env line should add `FRUIT_DYNAMIC_ARRIVE_DIAG=1` to the
design's reporting env (the rows are diag-gated per the repo convention). The pre-registered
mechanism endpoint "(i) the descent's `end=`" is read from the motion rows' `end=` (settled when
H1 runs) and/or `[arrive] settled=`; the like-for-like control baseline is the `[arrive] start=`
column (equal to the control's `end=`). The H1 risk check reads `[boundary] belt_margin`
(must not go negative on the small fruit). The motion monitor's `steps`/`|v|max`/`a_*` still
describe the profile leg only — the arrival ticks are not folded into the motion row (they are
visible in `[arrive] ticks=`), which is the interpretation to use if the gate is pointed at an
H1 log.

**Honest notes.** No simulator evidence in this lane: the arrival's *effect* (the `end=` moving,
the catch-up's inherited residual, the hold walk, the belt margin) is exactly what the Stage-M
screen measures. The knob-off tree is byte-unchanged by construction and the offline stub
proves the off gate performs no reads/steps; the no-harm items of the pre-registration (the
acceptance 9/10 + fingerprint, the two-line dense re-record + `190`, the mass-base control
replay) remain for the screen lane, which is where they belong.
