# P7-2 / FORCE-A results: the contact-gated force-mode re-entry (`FRUIT_FORCE_REENTRY`) - the mechanism endpoint lands (chase trips 5 -> 0, gate fires only on the lost-contact class) but the value endpoint fails (carried-not-placed 5 -> 5, zero conversions), the pre-registered non-adoption reading obtains, and the default stays `0`

Branch `p-supply` at `2126522` (tag `p7a-gate`), Tier A solo (one simulator lane via
`scripts/154_claim_run.sh`). This document is the whole battery of
`logs/p7/PREREG_FORCE_A.md` section 5/8 for the **scripted primary**: B0 knob-off
reproduction, the knob-off no-harm acceptance, the knob-on acceptance + diag run,
the kills, and the no-harm chain. The direct-interface endpoint (pre-reg section 5.4,
N=5) is **not** run here (out of this battery's scope; the pre-registration marks it
"only if P7-2 includes the direct path").

**Verdict.** B0 reproduced **bit-identically** on this tree (5 chase signatures,
310/310 physics lines vs `logs/r11/A1_10_accept_floored.log`), so the baseline pin
held and the battery proceeded. With the knob ON: the chase signature **5 -> 0**
(PASS), but **carried-not-placed 5 -> 5, zero slot conversions** (FAIL) and the
acceptance reads 4/9 = 44 % in both arms (the candidate's pre-existing rate; the
floor-0.75 item fails in both arms). No kill fired: zero weak-grip losses, zero
re-seats, all descents inside budget, no new failure reason. The diag reads the
mechanism firing exactly as designed - left failures `entries=1 exits=1
gated≈380-411`, right successes `entries=1 exits=0 gated=0` - and the loss itself is
byte-identical through the moment the payload is out. **Per the pre-registration's
own reading ("trips fall, carried-not-placed flat -> timing, not mode entry, owns
the failure"), the negative is published and no shipped default changes**
(`FRUIT_FORCE_REENTRY` stays `0`).

## 0. Battery at a glance

| step | run | log | reading |
| --- | --- | --- | --- |
| 1 | B0 knob-off candidate acceptance | `logs/p7b/00_b0_accept_floored.log` | **5/5 chase signatures reproduced; 310/310 physics lines IDENTICAL to `logs/r11/A1_10_accept_floored.log`; 4/9 = 44 %** |
| 2 | knob-off shipped acceptance | `logs/p7b/10_accept_noharm.log` | **9/10; gate PASS; `fingerprint: matches`; 365/365 IDENTICAL to `logs/p2d/90_accept.log`; carries 1 signature (attempt-0 kiwi)** |
| 3a | knob-ON candidate acceptance | `logs/p7b/20_accept_reentry.log` | **trips 5 -> 0; carried-not-placed 5 -> 5; 4/9 = 44 %; no kills** |
| 3b | knob-ON + diag | `logs/p7b/25_accept_reentry_diag.log` | **L failures `entries=1 exits=1 gated=380-411`; R successes `entries=1 exits=0 gated=0`; 310/310 identical to 3a modulo the 9 diag rows** |
| 4a | knob-off acceptance | (= step 2) | 9/10 + gate PASS + fingerprint matches |
| 4b | two-line dense re-record | `logs/p7b/30_twoline_dense.log` | **7/10, 9.1 s/attempt; 442/442 full stream IDENTICAL to the W7-A record; `190` PASS** |
| 4c | offline no-harm | `logs/p7b/40_selfcheck.log`, `41_supply_selftest.log` | **selfcheck PASS 0 failures / 1 skip; `172` 74 checks PASS** |
| 4d | patch control (pre-reg section 8.2) | `logs/p7b/50_patch_control.log` | **13/18; 643/643 physics-only (681/681 full) IDENTICAL to `logs/r10/30_control.log`** |

## 1. B0 reproduction (step 1) - the branch did not move

Run: `logs/p7b/00_b0_accept_floored.log` (candidate env, knob off; section 4 for the
exact command). Wall 17:14:56 -> 17:19:05.

* `grep -c "trips=38"` = **5**, all left, at the same `[fruit]` line numbers as the
  record (417 / 449 / 542 / 609 / 669) - attempts 0 / 1 / 4 / 7 / 9;
  `F[0.00,7.73] / [0.00,8.05] / [0.00,33.75] / [0.00,6.35] / [0.00,6.60]` N,
  `gap == sep`, `closed=15.00mm opened=0.00mm trips=38` exactly as pinned.
* `[stats]`: attempts=9 successes=4 `success_rate=44%` `diverted=0`
  `gate_open=0.0s` - the record's 4/9 = 44 %.
* `logs/w4/compare_streams.py --physics-only logs/p7b/00_b0_accept_floored.log
  logs/r11/A1_10_accept_floored.log` -> 310/310 lines, **IDENTICAL**
  (`logs/p7b/23_compare_b0_vs_on.txt` holds the B0-vs-ON compare; the B0-vs-A1_10
  compare is `logs/p7b/03_compare_b0_vs_a1.txt`).
* Gate (`logs/p7b/02_motion_b0.txt`): all 9 descent legs inside budget, worst
  held-grip cone 1.22x (reported), FAIL is rate-only (`success 4/9 below 75%`) -
  the R11-A.1 candidate's own gate read.

The pre-registration's stop condition ("if the count reads != 5, STOP") did not
fire. **The control comparison came in step 2: the shipped control carries exactly
one signature** (`F[0.00,14.92]N gap=39.8mm sep=39.8mm closed=15.00mm trips=38`,
attempt-0 kiwi, line 417) - the discriminating pair is 5 vs 1, as pinned.

## 2. Knob-off no-harm acceptance (step 2)

Run: `logs/p7b/10_accept_noharm.log` (the plain `accept.sh` env, knobs unset).
Wall 17:32:39 -> 17:37:39.

* **9/10** (`success_rate=90%`, 15.2 s/attempt, `diverted=0`).
* `python3 scripts/105_motion_regression.py logs/p7b/10_accept_noharm.log
  --fingerprint configs/motion_reference.json` -> **PASS** and
  `fingerprint: matches configs/motion_reference.json` (`logs/p7b/12_motion_control.txt`).
* `grep -c "trips=38"` = **1** (the attempt-0 kiwi, the identical row below).
* `--physics-only` vs `logs/p2d/90_accept.log` -> 365/365 **IDENTICAL**.

So the tree's knob-off default is byte-identical to the record on this scenario:
the `tasks.py` P7-1 edit (+132 lines, default off) did not move the shipped line.

## 3. Knob-ON battery (step 3)

### 3.1 The primary run and the endpoint table

Runs: `logs/p7b/20_accept_reentry.log` (candidate + `FRUIT_FORCE_REENTRY=1`,
18:13:22 -> 18:17:28) and `logs/p7b/25_accept_reentry_diag.log` (+
`FRUIT_FORCE_REENTRY_DIAG=1`, 18:20:02 -> 18:24:09).

| endpoint | B0 (OFF) | ON | target | verdict |
| --- | --- | --- | --- | --- |
| chase trips (`trips=38` + `closed=15.00` rows) | **5** | **0** | <= 1 | **PASS** |
| carried-not-placed (attempt rows) | **5** | **5** | <= 3 (a 2-slot conversion) | **FAIL** |
| failure moved into a new class | - | none | none | PASS |
| new failure reason | - | none (`notes=[]` on all 9 attempts, both runs) | none | PASS |
| weak-grip losses (`grasped=False` / `N=0` / lift-slip) | 0 | **0** | none | PASS |
| re-seats (`re-seated on the moving fruit`) | 0 | **0** | no rise | PASS |
| descents outside speed/lurch budget (105) | 0 of 9 | **0 of 9** | none | PASS |
| success rate vs the 0.75 floor | 4/9 = 44 % | **4/9 = 44 %** | >= 75 % | **FAIL** (pre-existing; see below) |
| motion gate (rate aside) | all inside | all inside (worst cone 1.22x reported) | pass | PASS |
| knob-ON determinism | - | diag run 310/310 identical modulo its 9 diag rows | - | PASS |

The ON run's failure set is **attempt-for-attempt the same as B0**: kiwi (attempt 0),
tomato (1), kiwi (4), tomato (7), peach (9) - all left, all
`grasped=True placed=False`, all `notes=[]`; the right arm is 4/4 in both. The
44 % rate is the *candidate's own* rate (B0 reads the same); the floor item fails
in both arms and is not informative about the knob.

### 3.2 What the knob actually did (the servo readout)

Every attempt's `[task] force servo:` row differs (9/9), and on the five left
failures the signature is exactly the endpoint:

| left failure (attempt) | B0 | ON |
| --- | --- | --- |
| 0 (kiwi) | `closed=15.00mm trips=38` (gap 39.9 -> **54.5** mm) | `closed=0.40mm trips=1` |
| 1 (tomato) | `closed=15.00mm trips=38` (gap 48.4 -> **63.0** mm) | `closed=0.40mm trips=1` |
| 4 (kiwi) | `closed=15.00mm trips=38` (gap 45.0 -> **60.4** mm) | `closed=0.80mm trips=2` |
| 7 (tomato) | `closed=15.00mm trips=38` (gap 45.1 -> **59.3** mm) | `closed=0.80mm trips=2` |
| 9 (peach) | `closed=15.00mm trips=38` (gap 43.6 -> **56.2** mm) | `closed=2.40mm trips=6` |

The four right-arm (successful) rows keep `closed=0.00mm trips=0`; the small
numeric drifts on them (`ref` 4.00 -> 3.89 on attempt 2; `sep` 80.8 -> 80.6 mm on
attempt 3) are the downstream effect of the branch's <= 0.1 s simulation-time
offset (see 3.4), not gate activity - the diag proves those carries never leave
force mode.

### 3.3 The diag counts (the mode-transition readout)

`[task] force reentry:` rows (only printed when non-zero), one per executed attempt:

* **left failures (5/5): `entries=1 exits=1`** with `gated=` **380 / 400 / 411 /
  397 / 408** - the mode entered once (the close's contact), exited once (the
  payload out), and the gate withheld ~380-411 would-be `close` ticks per lost
  carry. That is the whole 38-trip chase: `closed` collapses 15.00 mm (38 trips)
  -> 0.40-2.40 mm (1-6 trips).
* **right successes (4/4): `entries=1 exits=0 gated=0`** - contact held, the gate
  never withheld a move; the knob is inert on a healthy carry.

So the mode discipline is implemented correctly: it fires exactly on the
lost-contact class and nowhere else, and the "would-be closes" it withholds are
the ones the pre-registration's FARM reading suspected of feeding the slide.

### 3.4 The mechanism reading - the loss is byte-identical through the exit

`logs/p7b/23_compare_b0_vs_on.txt` + the offline diff (`logs/p7b/24_servo_table.txt`):

* B0 vs ON: **138 of 310 physics `[fruit]` lines differ**; the **first difference
  is post-loss**: the attempt-0 kiwi's `carry place0` row (`slip_max` 956.6 ->
  956.7 mm) - everything up to and including the loss (`carry grasp_lift`
  `slip_max=44.3 mm`, `lift +0.279 m grasped=True`, both identical) is byte-for-byte
  the same. The knob's first effect is *after* the payload is out.
* After that, a <= 0.1 s simulation-time offset (`[stats]` `sim=129.3s` -> `129.2s`)
  accumulates because the held gap slightly changes the kinematic gripper state;
  the subsequent attempt rows drift in their last decimal (lift heights
  0.291 -> 0.176 m etc.) but the class and outcome are identical on every attempt.
* ON vs diag: **310/310 physics lines identical modulo the 9 diag rows** - the
  diag is run-neutral here and the knob-ON branch is deterministic.

The pre-registered falsification reading is the measured one: **the chase is a
symptom, not the cause.** The servo's post-loss closes do not feed the slide - the
payload is already out when the gate can act, removing the closes changes nothing
(5 -> 5 carried-not-placed, zero conversions), and the outcome is timing-owned.

### 3.5 The kills, applied one by one

1. **Trips unchanged** - **NOT fired**: 5 signature legs -> 0 (per-leg trips
   38 -> 1/2/6, `closed` 15.00 -> 0.40-2.40 mm; diag `gated` 380-411).
2. **Weak-grip losses appear** - **NOT fired**: 0 `grasped=False` in all runs, 0
   `N=0`, no lift-slip notes (`notes=[]` throughout); the four successes read
   N=4.46-4.99 vs B0's 4.47-4.99 (<= 0.02 N); right arm 4/4 in both arms.
3. **Any descent outside its speed/lurch budget** - **NOT fired**: the 105 FAIL
   list is rate-only on both B0 (`02_motion_b0.txt`) and ON (`22_motion_reentry.txt`);
   `9 descent leg(s)` all inside.
4. **A re-seat rise** - **NOT fired**: 0 `re-seated on the moving fruit` occurrences
   in B0, ON, diag (and 0 in the control and patch control).
5. **A new failure reason** - **NOT fired**: `notes=[]` on all attempts in both
   knob-ON runs; the failure set is class-identical (5 carried-not-placed, left).
6. **Knob-ON acceptance below the dynamic floor 0.75** - **the rate item fails
   (44 % < 75 %), but it fails identically with the knob OFF (B0 = 44 %)** - it is
   the R11-A.1 candidate's pre-existing rate on this scenario, already recorded as
   the candidate's rate-only gate FAIL; it is not a knob-induced collapse. Per the
   pre-registration's adoption reading the negative is required by the *conversion*
   endpoint (2) regardless.

## 4. The no-harm chain (step 4 + pre-reg section 8)

| item (pre-reg section 8) | reading | verdict |
| --- | --- | --- |
| 8.1 acceptance 9/10 + gate PASS + fingerprint matches + 365/365 vs `logs/p2d/90_accept.log` | run 2 above; `--physics-only` 365/365 IDENTICAL | **PASS** |
| 8.2 patch control 643/643 vs `logs/r10/30_control.log` | `logs/p7b/50_patch_control.log` 13/18; `--physics-only` 643/643 IDENTICAL; full stream 681/681 IDENTICAL | **PASS** |
| 8.3 two-line dense 442/442 vs the W7-A record + `190` PASS | `logs/p7b/30_twoline_dense.log` 7/10, 9.1 s/attempt; full stream 442/442 IDENTICAL (`--physics-only` 422/422 IDENTICAL, the record's 442 includes the 20 `[run] attempt` rows) to `logs/w7/10_dense_twoline_1.log`; `scripts/190_twoline_gate.sh` **PASS** (floor 0.60; the 3 reported cone warnings 1.03x/1.28x/1.38x are the record's own) | **PASS** |
| 8.4 `scripts/selfcheck.sh` PASS; `172_supply_selftest.py` (pre-reg says "52 checks") | selfcheck **PASS 0 failures, 1 skip** (`40_selfcheck.log`); `172` **74 checks PASS** (`41_supply_selftest.log`) - the "52" is stale in the pre-reg: P4-C1's H1 added the trickle leg (172 -> 74 checks) on 2026-10-16 | **PASS** |

`configs/*` untouched (pins in section 6); the battery wrote nothing outside
`logs/p7b/` (plus this lane's `WORKLOG.md` entry). No shipped default changed
anywhere - the knob is off by construction (`FRUIT_FORCE_REENTRY` default `0`).

## 5. Exact commands and env

All via `RUN_LIMIT=... scripts/154_claim_run.sh <log> <env...> scripts/run.sh
scripts/20_pick_place.py` (Tier A solo; driver logs in `logs/p7b/01_`, `11_`,
`21_`, `26_`, `31_`, `51_`). The candidate env `CAND` is
`FRUIT_REACH_ANYWHERE=1 FRUIT_REACH_HOVER_SETTLE=60` (the R11-A.1 floored
selector is the reach branch's default `FRUIT_REACH_SHIPPED_FLOOR=1`).

```
# 1  B0 knob-off candidate acceptance       (RUN_LIMIT=2400)
HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10 CAND

# 2  knob-off shipped acceptance            (RUN_LIMIT=2400)
HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10

# 3  knob-ON candidate + diag               (RUN_LIMIT=2400 each)
HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10 CAND FRUIT_FORCE_REENTRY=1 [FRUIT_FORCE_REENTRY_DIAG=1]

# 4b two-line dense re-record               (RUN_LIMIT=3600)
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 SEED=5 FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10

# 4d patch control                          (RUN_LIMIT=5400)
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5 FRUIT_BIARM=0 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_REACH_ANYWHERE=0 FRUIT_REACH_HOVER_SETTLE=0

# gates (offline)
python3 scripts/105_motion_regression.py <log> [--fingerprint configs/motion_reference.json]
python3 logs/w4/compare_streams.py [--physics-only] <a> <b>
scripts/190_twoline_gate.sh logs/p7b/30_twoline_dense.log
```

## 6. Pins (start and end of the battery; `logs/p7b/00_tree_pins.txt`,
`90_tree_pins_end.txt` - unchanged)

* `src/fruit_sorting/tasks.py` **fec67f004a5ea1d326ed7cf572d824c8** (the P7-1 knob,
  +132 lines, default off; md5 matches the pre-registration's post-edit pin)
* `src/fruit_sorting/fruits.py` `f5671a65d6f72eb69a81e12ac6e0bf53`
* `src/fruit_sorting/rl_env.py` `6145bc96864abaa417dd0cc2f9da9dfd` (`TASKS_MD5` =
  `fec67f00...`, the P7-1 follow; the direct env would start)
* `configs/motion_reference.json` `b9e72ca79f6004c9a7e81219fe71b114`;
  `configs/motion_reference_twoline.json` `181c9151d65cf2c1f5be16b4c37c8f1e`
* tools: `scripts/105_motion_regression.py` `16a3d790...`,
  `scripts/190_twoline_gate.sh` `a24cfc5b...`,
  `logs/w4/compare_streams.py` `f912521c...`

## 7. Verdict against the pre-registration

Pre-reg section 5 adoption reading: *"trips endpoint met AND at least one
carried-class conversion reproduced AND the no-harm bar byte-exact; otherwise the
negative is published and the default stays `0`."*

* trips endpoint: **met** (5 -> 0);
* carried-class conversion: **not met** (5 -> 5, zero conversions; the endpoint
  required <= 3);
* no-harm bar: byte-exact (all four items PASS).

**The negative is published; `FRUIT_FORCE_REENTRY` stays default `0`.** The
pre-registered non-adoption reading is exactly what the battery measured:
*the chase is a symptom of the payload being out; the mode discipline removes it
cleanly and changes nothing about the outcome - timing, not mode entry, owns the
failure* (the B2 falsification, pre-reg section 1). The named follow-up from the
pre-reg ("the strict `CONTACTS=2` variant may be screened as a named follow-up,
not silently") is not screened here: the default `CONTACTS=1` already exits on
every failed carry and is inert on every success, so the strict variant would only
orphan healthy legs (the pre-reg's own expectation) and cannot convert the
outcome - the value channel is not in the mode.

## 8. Anomalies and unresolved items

1. **Foreign working-tree edit (RESOLVED: the orchestrator's harness fix).**
   `scripts/154_claim_run.sh` shows an uncommitted 9-line addition (watchdog reap:
   `pkill -P "$watchdog"` before `kill "$watchdog"`) with mtime **17:32:33**
   2026-10-16. Per the orchestrator: this lane's B0 caller had stalled because the
   wrapper's orphaned `sleep 2400` held the `tee` pipe after the run finished; the
   orchestrator killed the stray sleep (the B0 shell returned) and applied this
   fix before the step-2 launch. Scope: the claim wrapper only - no simulator path
   (`scripts/run.sh`, the entry scripts, `src/*` are untouched, md5-pinned above).
   Impact on this battery: none - the runs' evidence is byte-identical to the
   pre-edit records (B0 = A1_10, control = p2d/90, two-line = w7/10, patch =
   r10/30), and every post-fix wrapper reaped cleanly. The fix stays; this lane
   did not edit it and did not commit anything.
2. **The pre-reg section 8.4 "52 checks" is stale** - `172` now runs 74 checks
   (P4-C1's H1 trickle leg, 2026-10-16); it PASSes.
3. **The rate/floor item** (section 5.3, 44 % < 75 %) is the candidate scenario's
   pre-existing rate (identical OFF and ON); the adoption reading fails on the
   conversion endpoint, not on a knob-induced regression.
4. **Pre-reg section 5.4 (direct N=5) was not run** - out of this battery's scope
   (the task list ends at the scripted battery); the `rl_env.py` pin is in place
   if the owner wants it.
5. The `RUN_LIMIT` watchdog's reaping bug (the reason for the orchestrator's fix)
   bit exactly once: the B0 run's *caller* stalled on the orphaned `sleep 2400`
   holding the `tee` pipe after the wrapper had already exited `exit=0` - the
   orchestrator killed the stray sleep and fixed the wrapper (17:32:33); every
   subsequent wrapper (control, ON, diag, two-line, patch) reaped cleanly, all
   `exit=0` on schedule (wall times: B0 4.2 min, control 5.0, ON 4.1, diag 4.1,
   two-line 4.3, patch 8.6 - all far under their limits).

## 9. Artifact list (`logs/p7b/`)

`00_tree_pins.txt` + `90_tree_pins_end.txt` (pins), `00_b0_accept_floored.log` +
`01_b0_driver.log` (step 1), `02_motion_b0.txt` (B0 gate), `03_compare_b0_vs_a1.txt`
(B0 vs A1_10), `05_foreign_edit.txt` (anomaly 1), `10_accept_noharm.log` +
`11_control_driver.log` + `12_motion_control.txt` (step 2), `20_accept_reentry.log` +
`21_reentry_driver.log` + `22_motion_reentry.txt` (step 3a), `23_compare_b0_vs_on.txt`
+ `24_servo_table.txt` (mechanism), `25_accept_reentry_diag.log` +
`26_reentry_diag_driver.log` (step 3b), `30_twoline_dense.log` + `31_twoline_driver.log`
+ `32_twoline_gate.txt` (step 4b), `40_selfcheck.log` + `41_supply_selftest.log`
(step 4c), `50_patch_control.log` + `51_patch_driver.log` (step 4d).
