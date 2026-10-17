# P9-B RESULTS: the B1 `FRUIT_READY_SKIP` A/B on the frozen prereg - the lever is a measured NO-OP on this tree (the skip predicate under-fires: the parked arm's drive target is still `ready`, `dg = 0.0131-0.0135 > 0.01`), arm B is byte-identical to arm A on both scenarios, the gap p50 does not move at all, and the pre-registered kill applies

Tier-A solo battery, 2026-10-17, branch `p-supply` @ `59c90b5` (tree pins
`logs/p9b/00_tree_pin.txt` / `06_tree_pin_end.txt`: unchanged end-to-end).
Frozen prereg: `logs/p9/PREREG_GOREADY_B1.md`; implementation:
`logs/p9a/IMPLEMENTATION_B1.md`; the practice-side falsifier: `logs/p9e/EXTERNAL_A_MOTION.md` F3.

**Verdict against the frozen prereg: FAIL on the primary endpoint, kill #3
applied ("the gap p50 does not fall by >= 1.5 s - the lever is then not the
mechanism claimed").** The measured cause is the exact F3 falsifier: every
parked-arm entry reads `pre_err` 0.0131-0.0135 (inside `READY_SKIP_TOL` 0.03)
but `dg` 0.0131-0.0135 (outside `READY_SKIP_SYNC_TOL` 0.01), so the predicate
never fires - **0 firings across all 22 (acceptance) / 38 (patch) audited
per-side go_ready rows**, and `FRUIT_READY_SKIP=1` produces logs
**byte-identical** to the shipped arm. No
shipped default changed; no adoption (there is nothing to adopt: the knob is
env-inert on this tree's steady state). The no-harm bar holds in full.

## 1. What was run (exact)

All runs through the sanctioned single lane `scripts/154_claim_run.sh` (Tier-A
solo), one simulator, distinct log names; ops selfcheck at start / mid / end
(`01_ops_start.txt` 02:33 STALLED-CHAIN(0, only the previous lane's stale chain
log), `02_ops_mid.txt` 03:06 OK, `04_ops_end.txt` 03:54 OK).

| log | scenario | env (beyond the scenario set) | claim window |
| --- | --- | --- | --- |
| `10_accept_A1.log` | acceptance (i) | - (arm A run 1, no-harm baseline) | 02:36:15-02:41:13 |
| `11_accept_A2.log` | acceptance (i) | - (arm A double) | 02:41:49-02:46:46 |
| `20_accept_B1.log` | acceptance (i) | `FRUIT_READY_SKIP=1` | 02:47:06-02:52:03 |
| `21_accept_B2.log` | acceptance (i) | `FRUIT_READY_SKIP=1` (double) | 02:52:23-02:57:19 |
| `22_accept_B_diag.log` | acceptance (i) | `FRUIT_READY_SKIP=1 FRUIT_READY_DIAG=1` | 02:57:39-03:02:36 |
| `30_patch_A1.log` | patch battery (ii) | - (arm A run 1) | 03:02:56-03:11:43 |
| `31_patch_A2.log` | patch battery (ii) | - (arm A double) | 03:12:03-03:20:47 |
| `40_patch_B1.log` | patch battery (ii) | `FRUIT_READY_SKIP=1` | 03:21:07-03:29:49 |
| `41_patch_B2.log` | patch battery (ii) | `FRUIT_READY_SKIP=1` (double) | 03:30:09-03:38:53 |
| `42_patch_B_diag.log` | patch battery (ii) | `FRUIT_READY_SKIP=1 FRUIT_READY_DIAG=1` | 03:39:13-03:47:42 |
| `50_dense_twoline.log` | no-harm chain | `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1` | 03:49:19-03:53:40 |

Scenario env, verbatim (driver `run_battery.sh`):
* acceptance (i): `HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10`
  (`scripts/accept.sh`'s own recipe) + arm env;
* patch battery (ii): `HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
  ATTEMPTS=20 SEED=5 FRUIT_BIARM=0 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
  FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25` + arm env (the W6-A/W6-B single-arm
  battery, the R11 `PATCHB` env; `SCATTER=1` is the shipped default, written
  explicitly per the frozen prereg);
* dense re-record: `HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
  SEED=5 FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10`.

Driver: `bash logs/p9b/run_battery.sh <noharm|accept|patch|dense>`
(`16_stage2_driver.log`, `12_noharm_driver.log`, `17_dense_driver.log`); each
run `RUN_LIMIT=2400` (accept) / `5400` (patch) / `3600` (dense). Offline pass:
`bash logs/p9b/offline_checks.sh` (all compares/gates/readout; rc=0),
`python3 logs/p9b/ready_summary.py 22_accept_B_diag.log 42_patch_B_diag.log`
(the convergence readout), `python3 logs/p9b/readout.py ... --json 90_readout.json`.

Pins (unchanged start->end): `tasks.py` `255f28195191c53e414582f303d177d0`,
`rl_env.py` `e46700671b589ba0c2a48322e4b5c5c7`, `fruits.py` `f5671a65...`,
`scripts/20_pick_place.py` `88fa42bf...`, `configs/waypoints.json`
`d81c6f1c...`, `configs/motion_reference.json` `b9e72ca7...`,
`configs/motion_reference_twoline.json` `181c9151...`; HEAD `59c90b5`; `git
status` clean apart from the ignored `logs/p9b/` additions.

## 2. Primary endpoint: the wall inter-attempt gap (201 grammar) - A vs B

Clean gap = `< 7 s` (recovery gaps excluded); `fires` = `[task] <side> ready
blend stopped` lines. A = shipped (env unset); B = `FRUIT_READY_SKIP=1`.
Every B number is identical to its A twin (see section 5: byte identity).

| scenario | arm / log | clean p50 | clean mean | clean n | all-mean | max | recover fires | span mean (min-max) | wall/real (span+gap) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acceptance | A `10` | **5.2** | 5.162 | 8 | 5.489 | 8.1 | 1 | 15.16 (13.4-16.6) | 20.65 |
| acceptance | A `11` | 5.2 | 5.162 | 8 | 5.489 | 8.1 | 1 | 15.16 | 20.65 |
| acceptance | B `20` | **5.2** | 5.162 | 8 | 5.489 | 8.1 | 1 | 15.16 | 20.65 |
| acceptance | B `21` | 5.2 | 5.162 | 8 | 5.489 | 8.1 | 1 | 15.16 | 20.65 |
| acceptance | B diag `22` | 5.2 | 5.162 | 8 | 5.489 | 8.1 | 1 | 15.16 | 20.65 |
| patch | A `30` | **5.2** | 5.153 | 15 | 5.500 | 8.1 | 2 | 15.239 (13.9-16.4) | 20.74 |
| patch | A `31` | 5.2 | 5.153 | 15 | 5.500 | 8.1 | 2 | 15.239 | 20.74 |
| patch | B `40` | **5.2** | 5.153 | 15 | 5.500 | 8.1 | 2 | 15.239 | 20.74 |
| patch | B `41` | 5.2 | 5.153 | 15 | 5.500 | 8.1 | 2 | 15.239 | 20.74 |
| patch | B diag `42` | 5.2 | 5.153 | 15 | 5.500 | 8.1 | 2 | 15.239 | 20.74 |

* **p50 fall: 0.00 s on both scenarios** (threshold >= 1.5 s for B1) - the
  pre-registered kill applies. The pre-registered prediction (**5.20 -> <= 3.7**)
  is not observed; neither is the intermediate prediction (wall ~19.0 s).
* The per-gap lists are byte-for-byte the shipped ones
  (`89_readout.txt`): acceptance `[5.2, 5.2, 5.2, 5.2, 5.0, 5.2, 5.1, 5.2]` +
  the 8.1 s recovery gap; patch `[5.1, 5.1, 5.2, ..., 5.0, 5.2]` + the two 8.1 s
  recovery gaps.
* Span stayed flat (15.16 / 15.239), recovery counts unchanged (1 / 2), each
  arm's double-run bit-identical (section 5).

## 3. The wall per real attempt, the interval, and the gates

| endpoint | acceptance A (= B) | patch A (= B) | source |
| --- | --- | --- | --- |
| span mean | 15.16 s | 15.239 s | `[run] sim=t0-t1` |
| clean-gap p50 / mean | 5.2 / 5.162 s | 5.2 / 5.153 s | same |
| wall/real (span + gap mean) | 20.65 s | 20.74 s | same |
| pooled inter-placement interval | n=8 mean **20.73** p50 20.5 p90 24.1 min 18.6 max 24.1 | n=12 mean **27.62** p50 20.9 p90 42.5 min 18.9 max 61.7 | `scripts/186_w6_report.py` |
| window / batch throughput | **2.90** / 2.69 placed/min | **2.17** / 2.12 placed/min | 186 |
| success | 9/10 (attempt 0 kiwi place miss) | 13/18 = 72 %, 2 empty slots | `[stats]` |
| `gate_open` / `diverted` | 0.0 s / 0 | 0.0 s / 1 | `[stats]` |
| catch-up chases (residual > tol) | 0 / 10 | 0 / 18 | `[task] dynamic catch-up` |
| carry re-seats (`recoveries>0`) | 0 / 20 legs | 0 / 36 legs | `[motion] carry` |
| failure classes | 1x `grasped=True placed=False notes=[]`, 9x success | 5x `grasped=True placed=False notes=[]`, 13x success | attempt rows |

The 186 numbers reproduce the frozen controls exactly (acceptance 20.73 /
2.90; patch 27.62 / 2.17 - `logs/w6/BASELINE.md`, `logs/p4/A_DIAGNOSIS.md`),
which is the same statement as section 2: B never leaves the shipped branch.

**Gates (`105`).** Acceptance: A1/`10` and A2/`11` **PASS + `fingerprint:
matches configs/motion_reference.json`**; B1/`20` and B2/`21` **PASS** (9/10,
dynamic floor 0.75 - the B fingerprint is trivially also a match because the
logs are byte-identical, but per the prereg the fingerprint is quoted for arm A
only). Patch battery (budgets-only, `--min-success-rate 0`): all four A/B logs
**PASS** (every descent inside its speed/lurch bound; worst held-grip cone
1.22x reported, not gated). Plain 105 on the patch battery reads the only FAIL
as the scenario rate (13/18 = 72 % < the single-arm 75 % floor - the W6-B
record has the same shape; scenario-rate question, not a motion failure).
Dense: see section 6.

## 4. The convergence readout (`FRUIT_READY_DIAG`) - the F3 falsifier confirmed

`85_ready_summary.txt` (from `22_accept_B_diag.log` / `42_patch_B_diag.log`;
the diag runs are bit-identical to their clean twins modulo the `[ready]` rows,
compare `68_*` - so the rows describe the measured B branch exactly):

| scenario | side | go_ready rows | `skip=1` | `would=1` | err passes, dg blocks | parked entry (pre_err, dg) |
| --- | --- | --- | --- | --- | --- | --- |
| acceptance | left | 11 | **0** | 0 | **7** | (0.0135, 0.0135) x7 |
| acceptance | right | 11 | **0** | 0 | **3** | (0.0131, 0.0131) x3 |
| patch | left | 19 | **0** | 0 | **12** | (0.0135, 0.0135) x12 |
| patch | right | 19 | **0** | 0 | **6** | (0.0131, 0.0131) x6 |

* **Zero firings.** Every parked-arm entry passes the residual test
  (`pre_err` 0.0131-0.0135 <= 0.03) and fails the sync test
  (`dg` 0.0131-0.0135 > 0.01) - **dg == pre_err exactly**, because the parked
  arm's last commanded drive target *is* the ready pose: the steady-state droop
  (0.0131-0.0135 rad, the same residual `logs/610` measured) shows up as
  |target - measured|, and the `dg <= 0.01` term (borrowed from
  `_catch_up_drive`'s no-op threshold) is unsatisfiable in that state without
  also demanding `err <= 0.01`. The p9a stub check had already flagged the
  discriminator `(0.0135, 0.0135) -> no fire`; the tree's actual steady state
  is that state (F3: "if dg ~0.0135 at entry the skip under-fires" - confirmed).
* The no-op still costs what it always did: the parked arm runs
  `catch_up=20 + blend=90 + settle=120 = 230 ticks` on every gap [corrected 2026-10-17 from an earlier 210 that omitted the catch_up 20; the Oracle's re-derivation] (per-side sums: acceptance
  11x(90,120); patch 19x(90,120)); the two arms' ready transits remain the
  3.5 s of the 5.20 s clean gap that `GOREADY_OFFLINE` sections 2-3 budgeted -
  B1 removes none of it.
* **B2 calibration pair (recorded, B2 not run - see section 8):** parked
  transits converge nowhere (`ramp_err` 0.0168 left / 0.0163 right ->
  `post_err` 0.0136 / 0.0130 - the settle trims 0.003 rad of an already-in-band
  residual), while the active/staged transits read `ramp_err` up to 0.5064
  (accept left) / 1.3694 (accept right, one recovery fires) and the 120-tick
  settle is visibly what converges them. A settle trim on *all* transits (the
  frozen B2 form) therefore risks the active arm; a parked-only trim would be
  the safe ~0.75 s/gap form (named next probe, not tested here).

## 5. Determinism and byte identity

`compare_streams.py` (physics and full streams), all IDENTICAL:
* acceptance A double `10` vs `11`; acceptance B double `20` vs `21`;
  patch A double `30` vs `31`; patch B double `40` vs `41` (both stream modes);
* **arm B vs arm A**: `10` vs `20` and `30` vs `40` are **IDENTICAL on the full
  `[fruit]` stream** - `FRUIT_READY_SKIP=1` changes not one line. Arm B is
  therefore not a "moved branch": it is the same branch, and the moved-branch
  disclosure of the prereg is moot (no new fingerprint, no new attractor).
* diag vs clean: `22` vs `20` and `42` vs `40` IDENTICAL modulo the `[ready]`
  rows (the diag is branch-neutral).

File sizes corroborate (acceptance A/B 66,961 B; patch A/B 102,447 B; the diag
runs larger by their `[ready]` rows only).

## 6. No-harm chain (knob off) - all PASS

| item | result | file |
| --- | --- | --- |
| acceptance `10` vs frozen control `logs/p2d/90_accept.log` | **365/365 physics IDENTICAL** (385/385 full), 9/10 + `fingerprint: matches` + 105 PASS | `14_compare_noharm.txt`, `13_motion_noharm.txt`, `64*` |
| patch `30` vs W6-B single-arm record `logs/w6/20_battery_single.log` | **643/643 physics IDENTICAL** (681/681 full); also identical to `logs/r10/30_control.log` | `65*`, `66*` |
| two-line dense `50` vs W7-A record `logs/w7/10_dense_twoline_1.log` | **442/442 full IDENTICAL** (422/422 physics-only) | `67*` |
| `scripts/190_twoline_gate.sh` on `50` | **PASS** (7/10 = 70 %, `fingerprint: matches configs/motion_reference_twoline.json`, floor 0.60) | `80_twoline_gate.txt` |
| `scripts/selfcheck.sh logs/p9b/10_accept_A1.log` | **PASS, 0 failures** (incl. the motion-budget check) | `70_selfcheck.txt`, `70_selfcheck_internal.log` |
| `python3 scripts/172_supply_selftest.py` | **PASS (74 checks)**; patch sheet x1.0 numbers unchanged | `71_supply_selftest.txt` |
| `configs/*` untouched | md5s identical start->end | `00_tree_pin.txt`, `06_tree_pin_end.txt` |

## 7. The kills, applied exactly

| # | kill | measured | verdict |
| --- | --- | --- | --- |
| 1 | any descent outside its motion budget, or a new failure reason | all 9 descents inside both arms' acceptance logs; patch budgets PASS; failure classes/notes identical to A (B is byte-identical); chases 0; re-seats 0 | not triggered |
| 2 | the acceptance floor missed in either arm (0.75 of ten) | A 9/10, B 9/10 (dynamic floor 0.75) | not triggered |
| 3 | the gap p50 does not fall by >= 1.5 s (B1) | **fall 0.00 s** (5.2 -> 5.2, both scenarios) | **APPLIES -> B1 falsified as implemented; the lever is not the mechanism claimed** |
| 4 | the knob-off arm is not byte-identical to the frozen control | 365/365 + 643/643 + 442/442 identical | not triggered |
| 5 | (B3 only) supply statistics move | B3 not run; supply stats byte-identical anyway | n/a |

Named residual from the kill's cause: the frozen predicate's
`READY_SKIP_SYNC_TOL=0.01` is stricter than the tree's steady-state
`dg = err ~ 0.0135`; any repaired form (e.g. `dg <= err + 0.01`, or a
`READY_SKIP_SYNC_TOL ~ 0.02`) is a **code change and needs its own
pre-registration** - not made here (this lane is frozen read-only on `src/`),
and not implied by this measurement alone (the entry state is part of a
shipped branch).

## 8. What was not run / named next

* **B2 (`FRUIT_READY_SETTLE=30`) was not run**: the prereg makes it the
  *optional* half of the B arm (its stated prerequisite was the diag
  calibration, which is recorded in section 4), and B1's kill already fired.
  The diag pair says the safe B2 operand is the parked-only settle
  (~0.75 s/gap by construction, `ramp_err` already in band) while the frozen
  knob binds all ready transits (active-arm `ramp_err` up to 1.37 rad) - so a
  B2 attempt should be pre-registered with the motion gate as its arbiter, and
  it is a *different* lever from B1.
* **B3** (`FRUIT_DRIVER_FEED_TICKS`) is not implemented (driver-script scope,
  `logs/p9a/IMPLEMENTATION_B1.md` section 6) and was not run.
* The F2/F3 alternatives (blend-through-ready; completion-as-predicate) remain
  the ranked frontier from `logs/p9e/EXTERNAL_A_MOTION.md`; this battery
  delivered their prerequisite (pinned no-op budget + the entry-state
  readout) and one negative.

## 9. Provenance incidents (disclosed in full)

1. **A duplicate orchestrator chain (`99_chain.sh`, launched 02:41:58, 28 s
   after this lane's job) called the same `run_battery.sh` phases and queued a
   second `154_claim_run` on `logs/p9b/20_accept_B1.log` (started 02:41:58,
   still waiting at 03:07) which would have re-run and OVERWRITTEN that
   completed log when the simulator went idle.** This lane stopped that
   duplicate tree at 03:08 (TERM to its wrapper/run_battery/chain pids; this
   lane's chain pgid 1419689 and its sim process verified untouched; no other
   simulator, log or claim affected). Evidence: `03_dup_chain_incident.txt`
   (pre-stop ps tree + post-stop verification). A `RUNNER_LOCK` (pgid of this
   lane's chain) + a guard in `run_battery.sh` refuse a foreign caller while
   the owner is alive; a late relaunch is harmless anyway because every run
   log now exists (the runner skips non-empty logs).
2. **A mid-flight edit to `logs/p9b/run_battery.sh`** (adding that guard,
   ~03:08) landed while the patch-phase shell was still reading the script;
   the shell mis-read the file only at the end of its `case` block - all five
   patch runs had already completed exit=0 - and died with a syntax error
   before printing its phase line. The chained `&&` therefore stopped before
   `dense`, which this lane ran as a separate step (03:48:59-03:53:40,
   exit=0). No simulator log was written by the confused shell (`[claim_run]`
   calls appear only in the driver logs); every battery log ends with the
   normal `Simulation App Shutting Down` tail and the crash scan is empty
   (`offline_checks.sh` final step).
3. The claim timeline is monotone and exclusive (`16_stage2_driver.log`:
   claimed 02:41:49 / 02:47:06 / 02:52:23 / 02:57:39 / 03:02:56 / 03:12:03 /
   03:21:07 / 03:30:09 / 03:39:13; `17_dense_driver.log`: 03:49:19), no
   `overlap` or `TIMEOUT` line exists in any battery log, and the no-harm
   stream identities (365/643/442) prove the logs are the shipped branch.

## 10. Artifact index (all under `logs/p9b/`)

* `RESULTS.md` (this file), `WORKLOG_ENTRY.md` (orchestrator-facing, ready to
  append), `05_prereg_targets.md` (frozen targets + kills, copied pre-run).
* Tree pins: `00_tree_pin.txt`, `06_tree_pin_end.txt`; ops: `01_ops_start.txt`,
  `02_ops_mid.txt`, `04_ops_end.txt`.
* Drivers: `12_noharm_driver.log`, `16_stage2_driver.log`,
  `17_dense_driver.log`.
* The 11 simulator logs (`10`/`11`/`20`/`21`/`22`, `30`/`31`/`40`/`41`/`42`,
  `50`) + their `readout.py`/`ready_summary.py`-derived `*_noready.log` twins.
* Checks: `13_motion_noharm.txt`, `14_compare_noharm.txt`, `60-68*` compares,
  `70-79*` 105 gates, `80_twoline_gate.txt`, `85_ready_summary.txt`,
  `89_readout.txt`, `90_readout.json`, `70_selfcheck.txt`,
  `70_selfcheck_internal.log`, `71_supply_selftest.txt`.
* Tooling (written by this lane under `logs/p9b/`): `readout.py`,
  `ready_summary.py`, `run_battery.sh`, `offline_checks.sh`.
* Incident: `03_dup_chain_incident.txt`, `RUNNER_LOCK`.
