# P9-A PREREG (FROZEN): the go_ready skip-when-ready lever (B1) - the passive no-op blend

Frozen 2026-10-17 by the orchestrator from `logs/p9/GOREADY_OFFLINE.md` section 5 (drafted by the Tier-C decomposition lane, BEFORE any Tier-A run; the tree pin is re-taken at battery time).

## 5. Pre-registration skeleton (for the orchestrator to freeze)

**Question.** Does removing the passive arm's no-op ready transit (B1), alone or
with the settle trim (B2), shorten the wall inter-attempt gap and the pooled
inter-placement interval without moving the per-leg motion, the failure taxonomy,
or the shipped defaults?

**Tree pin (freeze before any run).** md5 of `src/fruit_sorting/tasks.py`,
`scripts/20_pick_place.py`, `src/fruit_sorting/fruits.py`,
`configs/waypoints.json`, `configs/motion_reference.json`; branch name; and the
frozen control log for the stream comparison (the phase's shipped acceptance,
e.g. `logs/r11/B_accept.log` / `logs/w8/R2_accept.log`). Knob names as frozen:
`FRUIT_READY_SKIP` (B1), `FRUIT_READY_SETTLE` (B2), `FRUIT_DRIVER_FEED_TICKS`
(B3), all default off.

**Arms.**
* A = shipped defaults (env unset) - the control; double-run.
* B = the lever: `FRUIT_READY_SKIP=1` (and optionally `+FRUIT_READY_SETTLE=30`);
  default off. Interleave A/B within one stretch where the harness allows
  (`scripts/154_claim_run.sh`); otherwise alternate and probe the branch
  (AGENTS 3b rule 1).

**Scenario.**
* (i) The single-arm acceptance: `HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10`
  through `scripts/run.sh scripts/20_pick_place.py` (accept.sh's scenario),
  each arm.
* (ii) The W6-A/W6-B single-arm patch battery: `FRUIT_SUPPLY_SCATTER=1
  FRUIT_SUPPLY_PATCH=1`, balanced A:B:C 0.375/0.375/0.25, `ATTEMPTS=20 SEED=5`,
  `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`, each arm, double-run for
  determinism. (Reference: `logs/w6/BASELINE.md` single-arm 13/18; control
  643/643 physics lines.)

**Endpoints.**
1. **Primary: the wall inter-attempt gap** - clean-gap p50 and mean plus the
   `_recover_ready` count, from the `[run] attempt ... sim=t0-t1s` windows
   (the `201` grammar / `inter_attempt_gap_s`). Predicted: p50 5.20 -> <= 3.7 (B1),
   <= 4.5 (B2/B3).
2. The wall per real attempt (span + gap; quote both; span must stay flat).
3. The pooled inter-placement interval via `scripts/186_w6_report.py` (window
   denominator; 60/interval mean = the window rate). Predicted interval
   20.7 -> ~19.0 s (B1).
4. Per-leg motion budgets + the per-scenario gate: `scripts/105_motion_regression.py`
   on the acceptance (10 attempts, floor 0.75, and the fingerprint for arm A
   only - arm B is a new branch); budgets-only for the 20-attempt battery
   (a reference is re-recorded only if the branch is adopted, and
   `--write-fingerprint` refuses a motion-budget-failing run).
5. Determinism: each arm's double-run bit-identical on the physics stream
   (`logs/w4/compare_streams.py --physics-only`).

**Kills (any one).**
* Any descent outside its motion budget, or any new failure reason in the
  failure-reason parser's set.
* The acceptance floor missed in either arm (the shipped dynamic floor, 0.75 of
  ten; the gate of record's PASS line).
* The gap p50 does not fall by >= 1.5 s (B1) / >= 0.5 s (B2/B3) - the lever is
  then not the mechanism claimed.
* The knob-off arm is not byte-identical to the frozen control (then the tree
  moved, not the lever).
* (B3 only) supply statistics (`queue_peak`, `released`, `supply_skipped`) or
  empty-slot fraction move without the gap gain.

**No-harm bar (knob off; the acceptance's own recipe).**
* Acceptance **9/10 + `fingerprint: matches configs/motion_reference.json`**
  (via `scripts/accept.sh` or the equivalent manual recipe).
* The acceptance's physics `[fruit]` stream identical to the frozen control
  (the current tree's control reads 385/385 lines, `compare_streams.py
  --physics-only`).
* The two-line dense re-record: `compare_streams.py` vs the phase's frozen
  dense record (442/442 physics lines) **and** `scripts/190_twoline_gate.sh`
  PASS.
* `scripts/selfcheck.sh` PASS; `configs/*` untouched.

**Moved-branch disclosure.** Arm B is a new attractor (the belt/feeder phase
shifts by the saved ticks). Quote the gap, the per-leg motion, the fingerprint
status, and the failure taxonomy - never a B-vs-A rate delta as the mechanism
(AGENTS section 2). If B is adopted, the acceptance reference is re-recorded
from the B branch and the collector's own store (which inherits a global
`go_ready` knob) needs its own branch decision.

**Resource estimate.** 2 scenarios x 2 arms x 2 (double) = 6-8 Tier-A runs,
~1-2 h of simulator time, plus the offline gap re-derivation.

## 6. Blockers / unmeasured terms, and the readout that would clear each

1. **The split inside term 3c (`_catch_up_drive` vs `_lift_clear`) is inferred
   by subtraction, not measured.** Two independent subtractions agree to ~0.2 s
   (114 ticks from the clean gap, 138 from the recovery delta), but the current
   tree has no per-stage counters. Readout: the `FRUIT_READY_DIAG=1` line
   (default off, pure reporting; P4-A section 10 item 1's prescription) printing
   per-arm: pre-transit err, drive gap, staged-route flag, lift ticks,
   catch-up ticks (per call site), ramp-end err, settle-end err, recovery ticks.
   This does not block B1 (its saving is the code-exact 210 ticks) but it is the
   prerequisite for B2's calibration.
2. **No per-gap marks.** `[cycle]` is inside `task.run`, so the gap is only ever
   observed as a subtraction of outcome windows. That is sufficient for the
   endpoint (it is true sim time) but means the transit total is never directly
   printed. A second readout (pure reporting, default off) could stamp the
   `go_ready` entry/exit sim times from the driver; named, not built.
3. **The branch shift is unavoidable** for any gap lever: -1.75 s of belt travel
   per attempt = 0.21 m of phase. The pre-registration must read arm B as a new
   branch (section 5), and the acceptance fingerprint applies to arm A only.
4. **Recovery noise in the mean.** The recovery fires in ~1/9 gaps (+2.9 s), so
   the mean gap is a mixture; the clean p50 plus the recovery count is the
   honest pair. A lever that happens to change the recovery *frequency* (B1
   changes the phase, so the post-place seed could land differently) must report
   both.
5. **The collector and the two-line worker are separate consumers** of
   `go_ready` (`40_collect_demos.py:397,508,519`; two-line park `tasks.py:5239`).
   The pre-registration must state the scope (single-arm driver only) or accept
   the collector's branch change as disclosed collateral.

## 7. Sources (file:line)

* Gap and its resolution: `logs/p4/A_DIAGNOSIS.md` sections 3, 4, 8, 10;
  `scripts/201_p4a_wait_audit.py` (`inter_attempt_gap_s`, `cadence_s_per_attempt`);
  `logs/p4/10_singlearm_availability.json`.
* Driver loop: `scripts/20_pick_place.py:172-177` (feed), `:193-226` (selection /
  `continue`), `:256-257` (`go_ready` + `advance(30)`), `:71-84` (fixed stepping).
* Transit: `src/fruit_sorting/tasks.py:3400-3414` (`go_ready`),
  `:1341-1371` (`_transit_to`), `:1477-1507` (`_ready_transit`),
  `:1416-1475` (`_lift_clear`), `:1509-1527` (`_blend_to`),
  `:1373-1410` (`_catch_up_drive`), `:1536-1561` (`_recover_ready`),
  `:1414` (`READY_STAGE_ERR` 0.35), `:1534` (`TRANSIT_TOL` 0.08).
* Cycle marks and windows: `tasks.py:3369-3393`, marks at `:5764`, `:5821`,
  `:6881`, `:7775`, `:8602`, `:8604`, `:8686`, `:8858`, `:8893`, `:6069`;
  `sim_start`/`sim_end` in `note_result` `:1215-1239`; `t0` at `:5608-5609`.
* Supply: `src/fruit_sorting/fruits.py:1145-1170` (absolute schedule, late
  release); `logs/p4/A_DIAGNOSIS.md` sections 2, 5.
* No-op transit evidence: `logs/610_posture/report.json` (`transit_to_ready`
  210 ticks, `dq_max` 0.0005 rad), `logs/610_posture/stream.jsonl` (per-leg tick
  counts), `logs/610_transit_staged.log` (10 s hold test), `logs/600_transit_min.py`
  (v3b-era staged-transit probe).
* Gates/tools: `scripts/105_motion_regression.py`, `scripts/186_w6_report.py`,
  `scripts/190_twoline_gate.sh`, `logs/w4/compare_streams.py`,
  `scripts/accept.sh`, `scripts/selfcheck.sh`, `logs/w6/BASELINE.md`.

---

## Calibration amendment (FROZEN 2026-10-17, BEFORE the retry battery; orchestrator)

**Why.** The first B1 battery (logs/p9b/, tree `255f2819`) measured a **threshold
under-fire**: the A/B runs are bit-identical (accept 365/365; patch IDENTICAL) and the
`FRUIT_READY_DIAG` readout shows **`skip=0` on all 22 acceptance transits and all patch
transits**. The no-op candidates (staged=0) read `pre_err` 0.0131-0.0135 (inside the 0.03
gate) but **`dg` 0.0131-0.0135, above the 0.01 sync gate** the B1 implementation borrowed
from `_catch_up_drive`. The predicted kill cause is confirmed by the pre-registered
diagnostic ("a dg ~ 0.0135 at entry means B1 under-fires"), so the lever never actuated and
the first battery measured the threshold, not the lever.

**The one bounded change.** The skip's drive-target sync gate becomes an explicit knob,
`FRUIT_READY_SKIP_DG` (default = `READY_SKIP_SYNC_TOL` 0.01, i.e. the shipped P9-A form
byte-unchanged; verified by the extended predicate stub `logs/p9a/check_skip_predicate.py`
including a default-equivalence check). **The retry arm is B' = `FRUIT_READY_SKIP=1
FRUIT_READY_SKIP_DG=0.02`** - 0.02 clears the measured 0.0131-0.0135 entry state with a ~48 %
margin while staying far below the staged-transit `pre_err` (>= 1.28), so the `err <= 0.03`
gate still excludes every real transit. Everything else (the endpoints, the kills, the
no-harm bar, the scenarios) is unchanged from the frozen sections above.

**Retry battery (Tier A, logs/p9c/).** (0) The new tree's knob-off no-harm: the acceptance
A vs `logs/p2d/90_accept.log` (expect 365/365) + the patch A vs `logs/p9b/30_patch_A1.log`
(bit-identity proves the calibration edit is default-inert); (1) accept B' x2; (2) patch B'
x2 + one diag; (3) the two-line dense re-record (442/442 + 190) + selfcheck. The A-arm
endpoints from the first battery stand (the A arms are unchanged by a default-off gate).
