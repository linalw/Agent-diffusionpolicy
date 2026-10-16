# P7-2b RESULTS: the C-3 carry monitor - the fast-skip interval endpoint lands hard, but K2 kills the form on 5 clean-leg aborts (cap 2); the default stays `0`, B-prime is not run

Lane P7-2b, Tier A solo, 2026-10-16, branch `p-supply` (uncommitted working
tree at `b06c948` + this lane's diff). Executed per the frozen pre-registration
`logs/p7/PREREG_CARRY_MONITOR.md` (md5 `5b31b3c3315572c4bce56d9319a1151b`)
against the Phase-0 replay gate `logs/p7/C3_REPLAY.md` (GO: macro-F1 0.969,
FP 2/33). Battery driver: `logs/p7c/run_p7c.sh`, outer
`logs/p7c/00_outer.log` (19:40:56 -> 20:55:07).

**Verdict.** The pre-registered B endpoints all pass and the primary is large:
the interval on A's failed-carried attempts **falls -24.0 %** (paired
both-carried 33-0, sign p = 0.0000; fired subset -30.8 %), lock-on +2.7 %,
cycle -26.8 %, zero new failure reasons. **But K2 fires**: the monitor aborted
**5 would-be placements** on clean legs (`clean_slip_max` 0.1-1.0 mm) against
the frozen cap of **2** per battery - the exact one-sided low-force clean-hold
class the Phase-0 replay flagged as the FP boundary (its failure mode 1), at a
higher live rate (5 of 19 clean attempts vs the replay's 1 of 20). Per the
pre-registration's own ordering, **B does not pass; the monitor is not
adopted, the knob stays default-off, and B-prime (the bounded re-seat form) is
not run** (it is conditional on B passing). The recorded next step on a K2
falsification is JCAC's conformal action-space risk (`logs/p7/C3_REPLAY.md`
section 3), **not a re-tune of this classifier** - no re-tune happened.

## 0. Battery at a glance

| step | run | log | reading |
| --- | --- | --- | --- |
| 1 | knob-off shipped acceptance | `logs/p7c/10_accept_noharm.log` | **9/10, 15.2 s/attempt; gate PASS; `fingerprint: matches`; 365/365 IDENTICAL to `logs/p2d/90_accept.log`** |
| 2 | knob-off two-line dense re-record | `logs/p7c/30_twoline_dense.log` | **7/10, 9.1 s/attempt; 442/442 IDENTICAL to `logs/w7/10_dense_twoline_1.log`; `scripts/190_twoline_gate.sh` PASS** |
| 3 | N=5 paired direct A/B | `logs/p7c/B_direct_ab/` | **A 26/75 vs B 14/75; B1 interval -24.0 % (33-0 paired); B2 +2.7 %; B3 -26.8 %; B4 none; K2 5 > 2 -> KILL** |
| 4 | offline stub test | `logs/p7c/10_monitor_stub.txt` | **STUB PASS** (embedded constants == refit <= 1e-9; 89/89 legs match; TP29/FP0/FN2/TN33 gated; 0/25 no-contact fires) |
| 5 | selfcheck (final tree) | `logs/p7c/40_selfcheck.txt` | **PASS 0 failures, 1 skip** |
| 6 | ops self-check start/mid/end | `logs/p7c/01_`, `02_`, `02b_`, `03_` | all **OK** |

## 1. What was implemented (Part 1)

`FRUIT_CARRY_MONITOR`, default **off**, in `src/fruit_sorting/tasks.py`
(+256 lines, no deletions):

* **The frozen model, embedded.** The six-feature logistic scorer
  (`sep`, `sep - gap_cmd`, `dsep/dt`, `min(ft)`, `sum(ft)`, `contacts`) with
  the constants fitted by the *same* code as the Phase-0 replay
  (`scripts/203_c3_monitor_replay.py::fit_logreg`: lr 0.5, 3000 full-batch
  steps, L2 1e-3, zero init, per-tick standardization), run once on all ticks
  of the frozen 89-leg corpus (the pooled training population of the
  leave-one-trace-out folds). Extraction and its record:
  `logs/p7c/extract_carry_monitor.py` -> `logs/p7c/05_monitor_extract.txt`;
  the constants and provenance are documented at their definition.
  **No runtime training**; with the knob off no feature is read.
* **The decision rule** (`_carry_monitor_logit`, `_CarryMonitorLeg`):
  z >= 0 for **2 consecutive ticks** (the frozen persistence), each hot tick
  carrying the **loaded-contact gate** (`min_contacts > 0`, the W8-B guard's
  running-minimum form), so a never-held payload can never fire. One instance
  per dynamic carry leg.
* **Scope**: the direct-capture/hybrid path only, the same scope gate as the
  W8-B guard (`direct_capture` set in `_grasp_carry_place_impl`);
  `_carry` additionally requires the OpenArm jaw hand on a dynamic capture.
  The scripted single arm and the two-line scheduler never reach it.
* **The fast-skip action**: a fire only latches a skip flag; the attempt ends
  **at the fired leg's boundary** - after `grasp_lift` the place leg and the
  release/retreat tail do not run, after `placeN` the release/retreat does not
  run; no re-seat, no command change mid-leg, no new failure-reason string
  (the K4 rule; the skip is named by the diag, not by `notes`).
* **Counts-only diag** (`FRUIT_CARRY_MONITOR_DIAG=1`, trace-only): one
  `[monitor] fire ...` line per fired leg (side/leg/fire tick counts + the
  fire tick's z) and one `[monitor] attempt: legs=/fires=/skip=/fired=[...]`
  line per attempt.
* **Byte-inert default**: all reads/writes guarded; the knob-off acceptance is
  365/365 identical (section 2).

### Offline stub verification

`logs/p7c/verify_monitor_stub.py` extracts the constants, scorer and state
machine from `tasks.py` by AST (no simulator import) and: (1) re-runs the
documented fit and asserts the embedded constants match it to <= 1e-9;
(2) replays all 89 frozen legs through the *real* `_CarryMonitorLeg` - 0
per-leg mismatches against an independent reference, and the gated leg readout
**TP=29 FP=0 FN=2 TN=33, 0/25 no-contact fires** (the gate blocks exactly the
two escapes whose first fire lands at their contact-loss row - no lead time to
reclaim; recorded in the extract output); (3) pins the synthetic semantics
(2-tick run fires on its first tick; pre-contact hot ticks are withheld and
close the gate for the leg; a cold tick breaks the run; no second fire).
The live read sites themselves are exercised by the battery, not the stub.

## 2. No-harm (knob off)

* **Acceptance** (`logs/p7c/10_accept_noharm.log`): **9/10** (90 %), 15.2
  s/attempt, `diverted=0`, `gate_open=0.0 s`; `scripts/105_motion_regression.py
  ... --fingerprint configs/motion_reference.json` -> **PASS** and
  `fingerprint: matches`; `logs/w4/compare_streams.py --physics-only` vs
  `logs/p2d/90_accept.log` -> **365/365 IDENTICAL** (`logs/p7c/12_`, `13_`).
* **Two-line dense re-record** (`logs/p7c/30_twoline_dense.log`): **7/10, 9.1
  s/attempt**; fingerprint matches `configs/motion_reference_twoline.json`;
  **442/442 IDENTICAL** to `logs/w7/10_dense_twoline_1.log`; `190` gate PASS
  (`logs/p7c/32_`, `33_`).
* `scripts/selfcheck.sh` **PASS** (0 failures, 1 skip) on the final tree
  (`logs/p7c/40_selfcheck.txt`, `logs/selfcheck.log`).
* Tree pins unchanged across the whole battery (`logs/p7c/00_tree_pins.txt` ==
  `90_tree_pins_end.txt`): `tasks.py` **5ee8d55d51bff211d6a33e8f217a45dc**,
  `rl_env.py` **7f00382ea1f1f3ff557084cbffed4286** (the metadata-only
  `TASKS_MD5` follow to `5ee8d55d`, verified matching), `trigger.py`
  `d7ec85fc`, `runtime.py` `ffb76bfd`, `fruits.py` `f5671a65`; checkpoint
  `moe_v13s` **61da390a**; `configs/*` untouched. Every raw rollout manifest
  pins `tasks_md5=5ee8d55d`, `acq=true`, `lateral=0.16`, `lead=0.9`.

## 3. The N=5 direct A/B (Part 2)

Design (the pre-reg section 1, W8-A/W8-B shape): 5 runs/arm x 15 episodes,
seeds `77 101 202 303 404`, sampler seed 11, interleaved A,B,A,B...; patch
sheet (`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`, balanced A:B:C
0.375/0.375/0.25), arrival trigger lead 0.9, shipped lateral 0.16, dynamic
never-stop handover, `FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1` on both
arms, `FRUIT_CARRY_DIAG=1` on **both** arms (the symmetric FP readout).
Arm A = `moe_v13s` 61da390a unset; arm B = the same checkpoint +
`FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_DIAG=1`. One
`154_claim_run.sh` claim (19:51:15 -> 20:55:03, ~64 min; the driver exit=1 is
`113_rl_report.py`'s documented negative-verdict path).

### 3.1 Outcomes and classes (branch caveat applies; AGENTS section 2)

| run (seed) | A ok | B ok | A escape-lift | B fires |
| --- | --- | --- | --- | --- |
| 1 (77) | 4/15 | 1/15 | 11 | 12 |
| 2 (101) | 6/15 | 2/15 | 11 | 13 |
| 3 (202) | 4/15 | 8/15 | 13 | 5 |
| 4 (303) | 5/15 | 1/15 | 10 | 14 |
| 5 (404) | 7/15 | 2/15 | 10 | 12 |
| pooled | **26/75 (35 %)** | **14/75 (19 %)** | 55 | 56 |

Classes: A ok=26 / no-contact=4 / carried-not-placed=45 (left 6/29, right
20/46); B ok=14 / no-contact=6 / carried=55 (left 2/27, right 12/48). The
arms' fruit streams diverge from B's first fire (episode 0 of every B run in
four of five runs), so **56 of 75 (run, episode) pairs have different fruit**;
on the 19 same-fruit pairs: 2 both ok, 9 both fail, 3 B-only ok, 5 A-only ok
(sign p = 0.8555); carried-class conversions 3 B-only / 3 A-only; strawberry
A 7/11 vs B 3/8. The rate delta is **not** quoted as a monitor effect.

The mechanism's own decomposition, however, is exact on each arm's own stream
(carry-line classes, `clean_slip_max > 5 mm` = escape):

* **A**: 26 = **20/20 clean-lift attempts placed + 6/55 escape-lift attempts
  ended placed** (five recovered holds with lift slips 10.5-25.5 mm, plus one
  204.9 mm slide whose attempt still ended on the output belt - run5 ep4 pear,
  A_5).
* **B**: 14 = **14/14 non-aborted clean-lift attempts placed + 0/56
  escape-lift attempts + 0/5 clean aborted** - every B attempt whose lift read
  clean and was not aborted placed; every fired attempt failed; no escape
  recovered.

### 3.2 The pre-registered endpoints (B fast-skip)

| # | endpoint | bar | measured | verdict |
| --- | --- | --- | --- | --- |
| B1 | interval on A's failed-carried attempts (primary) | mean must **fall** | A n=45: mean **1870.5** / median 1855 t -> B mean **1421.7** / median 1338 t = **-448.8 t (-24.0 %)**; paired both-carried n=33: **33 faster / 0 slower**, mean -548.2 t, sign p = **0.0000** | **PASS** |
| B1c | fired-subset / non-fired control | report | fired n=33: -574.3 t (-30.8 %); B fires=0 subset n=12: -103.7 t (-5.5 %, instrumentation/branch only) | report |
| B2 | lock-on (`premove+axis+hover+wait`, median) | <= +5 % | 2.930 -> 3.010 s (**+2.7 %**); W7-B park/hold decomposition 0.69/0.80 -> 0.69/0.84 s | **PASS** |
| B3 | pooled median per-attempt ticks | <= +5 % | 1823 -> 1335 t (**-26.8 %**) | **PASS** |
| B4 | zero new failure reasons | none new | new in B: **none** (both arms: trigger note only / + "fruit did not follow the gripper") | **PASS** |
| K2 | monitor aborts of would-be placements | <= 2 per 75 | **5** (details 3.3) | **KILL** |
| K3 | re-seat rise without conversion | B' only | **B' not run** (conditional on B passing) | n/a |
| K4 | any new failure reason | none | none | PASS |
| K5 | acceptance/two-line drift | byte-identical | 365/365 + 442/442 + gates PASS | PASS |

Fast-skip timing (endpoint 6, partial): 56 fires, all on `grasp_lift`; fire ->
leg boundary remainder median **68.5 ticks** (mean 80; 10/56 fired at tick 0);
re-seat counts **0/0** (both arms; `FRUIT_CARRY_GUARD` off).

### 3.3 K2: the five clean-leg aborts (the failure mode the replay flagged)

All five are B `grasp_lift` legs that the live `[carry]` line reads **clean**
(`clean_slip_max` 0.1-1.0 mm, `onset_row=None`), one-sided and low-force
(`min_contacts=1`, `force_min` 1.51-3.26 N against the healthy 4.2-4.5 N):
the C3_REPLAY failure mode 1 signature. Fire z at the boundary was modest
(+0.74..+1.16); **four of the five fired in the first two ticks** (tick 0),
where the model cannot see any slip yet.

| abort (run, ep) | fruit | fire | z | `clean_slip_max` | `force_min` | placed | A same (run, ep) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| (4, 8) | kiwi | `grasp_lift@138/155` | +1.16 | 1.0 mm | 3.26 N | False | tomato ok (branch) |
| (4, 9) | tomato | `grasp_lift@0/163` | +1.04 | 0.7 mm | 2.12 N | False | strawberry carried (branch) |
| (5, 0) | tomato | `grasp_lift@0/166` | +0.91 | 0.1 mm | 1.51 N | False | **tomato ok - a confirmed same-fruit conversion to failure** |
| (5, 3) | peach | `grasp_lift@0/163` | +0.74 | 0.1 mm | 1.79 N | False | tomato ok (branch) |
| (5, 12) | peach | `grasp_lift@0/157` | +0.74 | 0.1 mm | 1.81 N | False | orange carried (branch) |

Clean-leg denominators (K2's reported readout): **B 33/90 carry legs clean,
A 44/146** (the counts differ because a skip removes the place legs; 90 vs 146
carry legs). At the attempt granularity the live FP rate is **5 of 19 clean B
attempts (26 %)** - the Phase-0 replay's analogue was **1 of 20** (its FP pair
was the *only* such attempt in the four corpora; the w8-mech corpus carried
just 3 clean legs, 2 of them the FP), so the replay under-weighted this class
on the battery's supply. The additional observed cost beyond K2's clean-leg
letter: A had **6/55 escape-lift attempts end placed** (five recovered holds
with slips 10.5-25.5 mm plus one 204.9 mm slide whose attempt still ended on
the output belt); B had **0/56**, so the fast-skip also writes off the
marginal-escapable lifts. The frozen K2 counts only the clean-leg aborts
(5); both are reported because both are would-be placements.

## 4. Verdict against the pre-registration

* **B fails the K2 kill (> 2 clean aborts; measured 5).** The monitor is **not
  adopted**; `FRUIT_CARRY_MONITOR` stays **default off** and byte-inert.
* **B-prime is not run** (conditional on B passing, per the pre-reg section 1);
  its bounded re-seat form was not built beyond the fast-skip (Part-1 scope:
  "NO re-seat in arm B").
* The recorded next step on a K2 falsification is **JCAC's conformal
  action-space risk** (`logs/p7/C3_REPLAY.md` section 3 / pre-reg section 3.4),
  **not a re-tune of this classifier**; no re-tune was attempted (one pass).
* The mechanism itself is measured and positive: detection is fast (fire ->
  boundary median 68.5 t; the span falls -24 %, paired 33-0) and the
  scheduling action is clean (zero re-seats, zero new reasons, lock-on +2.7 %),
  but the frozen action converts 5 clean carries per battery into aborts - the
  detector's discrimination, not the action, is the binding residual.

**Unresolved / named residuals.** (1) The live one-sided low-force clean-hold
population is larger than the replay corpora showed; a carry monitor that
meets K2 needs a cleaner one-sided-but-seated discriminator (replay failure
mode 1; the trivial `contacts/force` rule was worse and the tactile-only
probe equals the full model, `C3_REPLAY` section 2). (2) The marginal-escape
write-off (11 % of escape lifts were recoverable on A) is inherent to any
fast-skip at this trigger. (3) The B1 primary is measured on a diverged fruit
stream after the first fire (the pre-reg's branch caveat); the n=12 non-fired
subset is outcome-mixed (8 B-ok / 3 no-contact / 1 carried; B fires on 51 of its
56 escape attempts), so it is not a same-class control - the same-class no-fire
population is n=1; the pooled B1 set is A-defined (B there: 33 carried / 8 ok /
4 no-contact) and the paired 33-0 is the fast-skip truncation at the fired leg
boundary (32/33 fired), i.e. the pre-registered timing endpoint, not a
success-rate effect.

## 5. Exact commands and env

All simulator steps via `RUN_LIMIT=... scripts/154_claim_run.sh <sim-log> ...`
with the wrapper's stdout to `<step>_driver.log` (Tier A solo); see
`logs/p7c/run_p7c.sh` for the full chain.

```
# 1  knob-off shipped acceptance (RUN_LIMIT=2400)
HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10 scripts/run.sh scripts/20_pick_place.py
# 2  knob-off two-line dense re-record (RUN_LIMIT=3600)
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 SEED=5 FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10
# 3  the A/B batch (RUN_LIMIT=18000; one claim)
RUNS=5 EPISODES=15 AB_SEEDS="77 101 202 303 404" AB_POLICY_SEED=11 \
  AB_DIR=logs/p7c/B_direct_ab \
  ARM_A="--ckpt checkpoints/moe_v13s/policy_best.pt" \
  ARM_B="--ckpt checkpoints/moe_v13s/policy_best.pt" \
  ARM_B_ENV="FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_DIAG=1" \
  AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_CARRY_DIAG=1" \
  bash scripts/112_rl_ab.sh
# offline: 105/190 + compare_streams; reports:
python3 logs/w7/B_ab_report.py --dir logs/p7c/B_direct_ab --a A --b B     # B_mech.txt
python3 logs/w8/A_pairs.py      --dir logs/p7c/B_direct_ab --a A --b B   # B_pairs.txt
python3 scripts/113_rl_report.py logs/p7c/B_direct_ab --a A --b B        # B_verdict.txt
python3 logs/p7c/C_endpoints.py --dir logs/p7c/B_direct_ab --a A --b B   # C_endpoints.txt
python3 logs/p7c/verify_monitor_stub.py                                  # 10_monitor_stub.txt
```

## 6. Deliverables and pins

* Implementation: `src/fruit_sorting/tasks.py` `5ee8d55d51bff211d6a33e8f217a45dc`
  (+256 lines, default off; the P7-2b diff), `src/fruit_sorting/rl_env.py`
  `7f00382ea1f1f3ff557084cbffed4286` (metadata-only `TASKS_MD5` follow).
* This lane's logs: `logs/p7c/` (`run_p7c.sh`, `extract_carry_monitor.py`,
  `verify_monitor_stub.py`, `C_endpoints.py`, the battery logs and reports).
* `WORKLOG.md`: the P7-2b entry.
* No shipped default changed; `configs/*` untouched; no commit (working tree
  only).
