# P9-A B1/B2 implementation (the `go_ready` ready-transit levers): completion record

Offline implementation lane, 2026-10-17, branch `p-supply` (base HEAD `402ad8a`,
the tree of record for the frozen pre-registrations). No simulator run, no claim,
no shipped-default change. The deliverable is the default-off, single-arm-scoped
set of knobs the frozen pre-registration `logs/p9/PREREG_GOREADY_B1.md` (from
`logs/p9/GOREADY_OFFLINE.md` section 4) specifies, so the Tier-A battery (arms
A/B) can run next.

## 1. The diff in one screen

| file | md5 before | md5 after | lines |
| --- | --- | --- | --- |
| `src/fruit_sorting/tasks.py` | `12feced3b6204f06bb32cb878efb5e15` | **`255f28195191c53e414582f303d177d0`** | +206 / -20 |
| `src/fruit_sorting/rl_env.py` | `7bd07b662595c56fa45ca12e7a87a7ff` | **`e46700671b589ba0c2a48322e4b5c5c7`** | +9 / -1 |

The full diff is preserved at `logs/p9a/10_diff.patch`. Nothing else in the tree
changed (`git status --short` lists exactly these two files).

**`tasks.py` hunks.**

1. `__init__` (~line 609): the pure-reporting flag
   `self._ready_diag = os.environ.get("FRUIT_READY_DIAG", "0") == "1"`, next to
   the existing reach/carry diag flags.
2. The B1 tolerances as class constants next to `READY_STAGE_ERR` (lines
   1431-1440): `READY_SKIP_TOL = 0.03`, `READY_SKIP_SYNC_TOL = 0.01`, with the
   measured-residual provenance in the comment.
3. **Stats plumbing (diag only; `None` at every shipped call site)**: the four
   transit helpers take an optional `stats: dict | None = None` -
   `_transit_to` (1346), `_catch_up_drive` (1382), `_lift_clear` (1442),
   `_ready_transit` (1512), `_blend_to` (1548). The records are:
   * `_catch_up_drive`: `stats["catch_up"] += len(ramp)` (the actual ramp ticks;
     nothing is recorded when the `gap <= 0.01` early-out hits).
   * `_lift_clear`: the IK loop's tick count via the loop index
     (`lift_steps = tick` before the break), recorded as `stats["lift"]`.
   * `_blend_to`: `stats["ramp_err"]` (max |q - target| after the 90-tick ramp,
     before the settle; the exact B2-calibration read), `stats["settle_err"]`,
     `stats["blend"] = len(ramp)`, `stats["settle"] = max(0, settle)`.
   * `_ready_transit`: `stats["staged"] = 1` when the around-the-belt route runs.
   All of this is behind `if stats is not None`; the shipped call graph passes
   `stats=None` everywhere and the loops are unchanged.
4. `go_ready` (3454) plus the five helpers (3498-3600): `_ready_residuals`,
   `_ready_err`, `_ready_settle`, `_ready_move`, `_ready_report`. `go_ready`'s
   per-arm body is now `stats = self._ready_move(name)` -> the unchanged
   recovery check -> the diag report (only when stats is not None). The
   `FRUIT_READY_RECOVERY` behavior is untouched (its return value is now
   captured, which has no control effect).

**`rl_env.py` hunk.** A P9-A paragraph in the pin's provenance comment and
`TASKS_MD5` -> `255f28195191c53e414582f303d177d0`; the match is verified
(section 5).

## 2. The knobs, exactly

### `FRUIT_READY_SKIP=1` (B1, default off)

In `_ready_move`, per arm, before the transit:

```python
scope = self._active_session is None and not self.two_line_enabled()
skip = scope and os.environ.get("FRUIT_READY_SKIP", "0") == "1"
...
if skip and err <= self.READY_SKIP_TOL and dg <= self.READY_SKIP_SYNC_TOL:
    # command the ready pose, re-anchor the integrator, run no ticks
```

with `err = max|q_measured - ready|` and `dg = max|q_target - q_measured|` - the
exact predicate GOREADY_OFFLINE section 4 (B1) fixes: `err <= 0.03` rad (2x the
measured steady residual 0.0131-0.0135 on j1, `logs/610_transit_staged.log`) and
`dg <= 0.01` rad (`_catch_up_drive`'s own no-op threshold). The measured entry
state comes from `logs/610_posture/stream.jsonl`: the passive arm's
`transit_to_ready` segments run exactly **230 rows (catch_up 20 + blend 90 + settle 120)** [corrected 2026-10-17],
and the absent 20 catch-up ticks *are* the no-op proof - `_catch_up_drive`
returns before its ramp when `gap <= 0.01`, so the entry `dg` was inside the
band on all 5 of those segments (entry `err` 0.0131-0.0139). The stream's
first-row `|qcmd - q|` (0.0004) is one tick of measured drift, not the entry
`dg` - the row count is the evidence.

The skip preserves the shipped post-condition rather than dropping commands:
the drive target is set to the ready pose and `sync_command_to_measured()`
re-anchors the IK integrator - exactly what `_blend_to`'s tail leaves behind
after its 210 ticks. The commanded step is bounded by
`READY_SKIP_TOL + READY_SKIP_SYNC_TOL = 0.04` rad, under the 0.05 rad
leg-boundary bound the posture probe enforces. The saving is then code-exact:
**210 ticks = 1.75 s per gap** when the entry state is the measured one (90
blend + 120 settle; the catch-up is part of the same no-op). Any other entry
state (the active arm's post-place seed, the hanging pose) fails the predicate
and takes the shipped path.

Knob-off (unset or `=0`): the shipped `_transit_to(name, "ready")` runs with the
shipped defaults - byte-identical.

### `FRUIT_READY_SETTLE=N` (B2, default off)

`_ready_settle()` resolves the knob (`unset -> 120`, the shipped value; `N`
clamped at >= 0), and `_ready_move` passes it as the `settle` of the *ready
transit*:

```python
self._transit_to(side, "ready", settle=self._ready_settle() if scope else 120, stats=stats)
```

so it binds both transit routes (the plain blend and the staged route's final
blend). The `_recover_ready` re-blend keeps the shipped 120: it is the
contact-jam fallback (a corrective action, fires ~1/9 gaps and is excluded from
the clean-gap endpoint), and B2 as pre-registered trims "the ready transit's
settle". The calibration pair is measured by the diag: `ramp_err` (the residual
at the 90-tick ramp's end) vs `settle_err` (post-settle); B2 is only worth
flipping if the ramp-end residual is already inside the tolerance the settle
exists to satisfy.

### `FRUIT_READY_DIAG=1` (pure reporting, default off)

One `[ready]` line per arm per `go_ready`, e.g. (an active arm's staged
transit, measured entry values from the 610 stream):

```
[ready] left skip=0 staged=1 pre_err=0.7890 dg=0.4431 catch_up=45 lift=49 blend=90 settle=120 ramp_err=0.0140 settle_err=0.0128 post_err=0.0129 rec=0 end_err=0.0129
```

Fields: `skip` (B1 fired), `staged` (around-the-belt route), `pre_err`/`dg`
(the predicate inputs at entry), `catch_up` (summed ramp ticks of every
`_catch_up_drive` call of the transit), `lift` (`_lift_clear`'s IK ticks),
`blend`/`settle` (the blend's tick counts), `ramp_err`/`settle_err` (the B2
pair), `post_err` (residual before `_recover_ready`), `rec` (recovery fired),
`end_err` (after everything). Reads are stage-boundary joint reads only - no
per-tick reads, nothing inside `ik_step`; when the flag is off (every shipped
run) none of the reads happen. Per AGENTS.md section 2 a trace (and any read
that only exists under it) is mechanism evidence, not a number to quote - the
endpoints come from trace-off runs.

## 3. Scope (single-arm only)

`scope = self._active_session is None and not self.two_line_enabled()`.
Excluded (shipped path kept byte-exact): the two-line scheduler's per-arm park
(`tasks.py:5239`, session active), the shared-station pipeline (session
active), and the two-line station calibration's own `go_ready(side)`
(`tasks.py:4389`, pre-session - excluded by the explicit
`two_line_enabled()` term). Inheriting consumers when the knobs are enabled
(disclosed): the single-arm driver (`scripts/20_pick_place.py`), a single-arm
collector, `scripts/70_record_video.py`, and the probes - all the same
single-arm `go_ready` the levers were derived from. The frozen prereg's
blocker 5 (collector scope) resolves to this rule.

## 4. Byte-inertness at default

With every knob unset: `_ready_move` performs the scope check (two attribute
reads) and calls `self._transit_to(name, "ready", settle=120, stats=None)` -
the same call the shipped code made (default `settle=120`, `stats=None`), with
`_catch_up_drive`/`_lift_clear`/`_ready_transit`/`_blend_to` receiving their
defaults; no joint read is added on the shipped path; the `_lift_clear` loop
index is a pure local. The two-line and shared-station paths keep the shipped
calls (scope False -> `settle=120`). **The byte-identity *proof* is the first
Tier-A step and is not yet run** (section 6) - the argument above is
code-inspection-grade, as the pre-registration requires.

## 5. Verification (offline, all PASS)

* `python3 -m py_compile src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py` - OK.
* `TASKS_MD5` match: `tasks.py` md5
  `255f28195191c53e414582f303d177d0` == the pin (script-verified, section 1).
* `scripts/selfcheck.sh` - **PASS, 0 failures, 1 skipped** (motion budgets skip
  needs an acceptance log): `logs/p9a/selfcheck.log` (run with
  `SELFCHECK_LOG=logs/p9a/selfcheck.log`, so no repo-external file was
  rewritten).
* Stub-level skip-predicate check: `logs/p9a/check_skip_predicate.py`
  (`77ad4bf64fb0c97eee13bfc8030067a3`), output `logs/p9a/40_stub_check.log` -
  **PASS, all checks**. It (a) reads the constants and the exact predicate
  expression out of the source by AST/text (fails if they move), (b) evaluates
  `err <= READY_SKIP_TOL and dg <= READY_SKIP_SYNC_TOL` on synthetic residuals
  including the boundary `(0.03, 0.01)` -> fire, `(0.0301, 0.01)` and
  `(0.03, 0.0101)` -> no fire, the discriminator `(0.0135, 0.0135)` (target
  held at ready with `dg = err`) -> no fire, and the measured active-arm /
  hanging entries -> no fire, and (c) re-derives the 12 `transit_to_ready`
  segments of `logs/610_posture/stream.jsonl`: the 5 measured no-op segments
  (210 rows = 90+120, i.e. the catch-up early-out held, `dg <= 0.01` at entry)
  all pass the predicate with entry `err` 0.0131-0.0139, and every non-no-op
  segment fails it on `err`.
  *What it does not prove:* that the current tree's passive arm enters
  `go_ready` with `dg <= 0.01` (the 610 stream is a v3c-era instrumented run).
  The diag's `pre_err`/`dg` fields are the readout that measures this on the
  current tree in the first Tier-A run; if `dg` reads ~0.0135 there (target
  held at ready rather than tracking the measured pose), the predicate does not
  fire and B1 is a no-op on this tree - that is the pre-registered kill
  ("the gap p50 does not fall"), and the diag names the cause.

## 6. The next Tier-A step (per the frozen prereg; not run here)

1. **Byte-identity control (no-harm, knob off).** One acceptance run
   (`scripts/accept.sh`'s recipe) and the stream comparison
   (`logs/w4/compare_streams.py --physics-only`) against the phase's frozen
   control (the current-tree candidates: `logs/p8/10_accept_noharm.log`,
   `logs/r11/B_accept.log` / `logs/w8/R2_accept.log` - 385/385 physics `[fruit]`
   lines on this lineage), plus `fingerprint: matches`; the two-line dense
   re-record 442/442 + `scripts/190_twoline_gate.sh` PASS. Any mismatch means
   the tree moved, not the lever - stop.
2. **A one-off diag run** (`FRUIT_READY_DIAG=1`, no control knobs) to read the
   entry `pre_err`/`dg` and the `ramp_err`/`settle_err` pair on the current
   tree; this calibrates B2 and confirms B1's firing state before the battery.
   Its reads make it a mechanism run - not a number of record.
3. **The battery** - arms A (shipped, double-run) and B
   (`FRUIT_READY_SKIP=1` and, if the diag pair supports it,
   `+FRUIT_READY_SETTLE=30`) on the acceptance (i) and the W6-A/W6-B patch
   battery (ii), interleaved where the harness allows; endpoints/kills as
   frozen: clean-gap p50 (predicted 5.20 -> <= 3.7 s for B1), wall per attempt,
   the 186 window interval, per-leg motion budgets (arm A fingerprint only -
   arm B is a new branch), determinism double-runs, and the failure taxonomy.
4. Re-pin the tree (`TASKS_MD5`) at battery time if anything else lands first.

B3 (`FRUIT_DRIVER_FEED_TICKS`) is not implemented here: it lives in the driver
script (`scripts/20_pick_place.py`), outside this lane's write scope; the
frozen prereg keeps it as an optional third arm.

## 7. Artifacts

| path | what |
| --- | --- |
| `src/fruit_sorting/tasks.py` | the knobs (this diff) |
| `src/fruit_sorting/rl_env.py` | `TASKS_MD5` follow + provenance comment |
| `logs/p9a/10_diff.patch` | the full diff (only the two files above) |
| `logs/p9a/check_skip_predicate.py` | the stub-level predicate check |
| `logs/p9a/40_stub_check.log` | its output (all PASS) |
| `logs/p9a/selfcheck.log` | `scripts/selfcheck.sh` output (PASS, 0 failures) |
| `logs/p9a/WORKLOG_ENTRY.md` | the orchestrator-facing WORKLOG entry |
