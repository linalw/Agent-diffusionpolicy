# P8-2 B3 RESULTS: the load-floor C-3 carry monitor - the offline fix clears the P7-2b K2 kill (5 -> 0 clean aborts; 43/43 fires on escaping legs) and the B1 interval lands (-21.8 %, paired 32-1), but **B2 lock-on fails at +8.8 %** (> +5 %): B does not pass, the form is not adopted (+ a mid-battery tree-drift audit)

Lane P8-2 "B3", Tier A solo (one simulator, every step under its own
`scripts/154_claim_run.sh` claim), 2026-10-17 01:01:28 -> 02:21:16 +0800,
branch `p-supply` at HEAD `402ad8a`. Battery driver `logs/p8d/run_p8d.sh`,
outer log `logs/p8d/00_outer.log`. Executed against the FROZEN
pre-registration `logs/p8/PREREG_CARRY_MONITOR_LF.md` (md5
`b3604b7fb30e825a1f5c9c9b2a285fb6`, re-verified at battery time). Writes only
under `logs/p8d/`; no commit, no shipped-default change.

**FLAG first - the frozen-tree premise was violated mid-battery by a
concurrent lane.** At 01:58:53/01:59:18 (during the A/B batch) the P9-A lane
wrote `src/fruit_sorting/tasks.py` (12feced3 -> 255f2819) and `rl_env.py`
(7bd07b66 -> e4670067) - its default-off `FRUIT_READY_*` ready-transit knobs
(the working-tree diff equals `logs/p9a/10_diff.patch` byte-for-byte). The
per-run manifests pin the split: **runs 1-4 = the frozen tree, run 5 = the
drift tree**. Section 5 audits it; the cohort re-read shows **every
pre-registered verdict is unchanged** (the binding B2 failure holds a fortiori
on the frozen cohort: +10.0 %, and K2 = 0 there too). The whole-battery pin
(prereg 7.8) is invalidated as such; the per-run manifests and the
frozen-cohort read are the reads of record.

## 0. Battery at a glance

| # | step | log | reading |
| --- | --- | --- | --- |
| 0 | pins + ops start | `00_*`, `01_ops_start.txt` | tree at 402ad8a clean; ops **OK** |
| 1 | stub gate, both frozen pins (frozen tree) | `10_`..`13_` | **PASS** - floor=0 -> 29/0/2/33; floor=3.5 -> 28/0/3/33 (4 harness runs) |
| 2 | knob-off acceptance (frozen tree) | `20_accept_noharm.log` + `22_`/`23_` | **9/10, 15.2 s/attempt; gate PASS; `fingerprint: matches`; 365/365 IDENTICAL** |
| 3 | N=5 paired direct A/B | `B_direct_ab/`, `C_endpoints.txt`, `B_monitor_report.txt` | **B1 PASS (-21.8 %, paired 32-1) - B2 FAIL (+8.8 %) - B3 PASS (-25.6 %) - B4 PASS - K2 PASS (0 aborts, was 5)** -> **B does not pass** |
| 4 | no-harm chain (drift tree) | `40_`..`43_`, `50_`, `51_` | **442/442 IDENTICAL + `190` PASS; selfcheck PASS 0 failures; `172` 74 checks** |
| 5 | ops mid/end | `02_ops_mid.txt`, `03_ops_end.txt` | **OK / OK** (plus a manual OK mid-batch) |
| - | tree-drift audit | `92_tree_drift_audit.txt`, `B_cohort_split.txt` | runs 1-4 frozen / run 5 drift; **no verdict changes** |

## 1. Stub gate - both frozen pins on the frozen tree (PASS; STOP condition cleared)

Run at 01:01:35, ~57 min before the drift write; the harnesses extract the
constants/scorer/state machine from the live `tasks.py` (the committed
`12feced3` at that moment):

| harness | pin | reading |
| --- | --- | --- |
| `logs/p7c/verify_monitor_stub.py` | floor=0 (default) | **STUB PASS**, `TP=29 FP=0 FN=2 TN=33`, 0/25 no-contact fires |
| `logs/p8c/verify_monitor_stub_lf.py` | floor=3.5 (default) | **STUB PASS**, `TP=28 FP=0 FN=3 TN=33`, 0/25 no-contact fires |
| `logs/p8c/verify_monitor_stub_lf.py` | `STUB_FLOOR=0` | **STUB PASS**, `TP=29 FP=0 FN=2 TN=33` |
| `logs/p8c/verify_monitor_stub_lf_p81.py` | both | **STUB PASS**, floor=0.0 -> 29/0/2/33 (min `asym@fire` 0.900, n=29); floor=3.5 -> 28/0/3/33 (min `asym@fire` 3.663, n=28); knob wiring + `asym@fire` field pinned against the real source |

Both frozen pins reproduce exactly (`logs/p8d/10_`..`13_`); no mismatch, so
the battery proceeded. Note: `logs/p8c/verify_monitor_stub_lf.py` now carries
md5 `9fef279a73594afce35bc6966eb728fb` (it was updated at 00:46 to parameterize
its expected-counts assertion for `STUB_FLOOR=0`; P81_DETAIL quotes the earlier
`6965d2ad...`). Both its paths pass.

## 2. Knob-off no-harm acceptance (PASS; frozen tree)

`RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p8d/20_accept_noharm.log
HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10 scripts/run.sh
scripts/20_pick_place.py` (01:02 -> 01:07:07):

* **9/10 = 90 %**, 15.2 s/attempt, `diverted=0`, `gate_open=0.0 s`,
  `queue_peak=0`, `recirculated=0` - the shipped record's own line.
* `105_motion_regression.py --fingerprint configs/motion_reference.json`:
  **PASS**, `fingerprint: matches configs/motion_reference.json`; 5 warnings
  (the record's own reported carry-cone class; not gating).
* `compare_streams.py --physics-only` vs `logs/p2d/90_accept.log`:
  **365/365 IDENTICAL**.

## 3. The N=5 paired direct A/B (step 3)

Design = prereg 7.1 verbatim: patch sheet
(`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25`),
arrival trigger lead 0.9, shipped lateral gate 0.16 (unset), dynamic never-stop
handover, `FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1` on both arms,
`FRUIT_CARRY_DIAG=1` on both arms; `RUNS=5 EPISODES=15`, seeds
`77 101 202 303 404`, policy seed 11, interleaved, via `scripts/112_rl_ab.sh`
under one claim (01:07:31 -> 02:15:58, ~68 min; the wrapper exit=1 is
`113_rl_report.py`'s documented negative-verdict path).

* **Arm A** = `moe_v13s` `61da390a` unset.
* **Arm B** = the same checkpoint +
  `FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5 FRUIT_CARRY_MONITOR_DIAG=1`.

### 3.1 Outcomes and classes (single-branch counts; branch caveat applies)

| run (seed) | A ok | B ok | B fires |
| --- | --- | --- | --- |
| 1 (77) | 5/15 | 4/15 | 9 |
| 2 (101) | 7/15 | 4/15 | 10 |
| 3 (202) | 3/15 | 2/15 | 12 |
| 4 (303) | 3/15 | 5/15 | 9 |
| 5 (404) | 7/15 | 9/15 | 3 |
| pooled | **25/75 (33 %)** | **24/75 (32 %)** | 43 |

Classes: A ok=25 / no-contact=4 / carried-not-placed=46; B ok=24 /
no-contact=4 / carried=47. The fruit streams diverge from B's first fire, so
**55 of 75 (run, episode) pairs have a different fruit**; on the 20 same-fruit
pairs: both ok 5, both fail 9, B-only ok 3, A-only ok 3 (sign p = 0.6562);
carried-class conversions 3 B-only / 3 A-only; strawberry A 5/9 vs B 6/12.
The rate delta is **not** quoted as a monitor effect.

### 3.2 The pre-registered endpoints (`logs/p8d/C_endpoints.txt`)

| # | endpoint | bar | measured | verdict |
| --- | --- | --- | --- | --- |
| B1 | interval on A's failed-carried attempts (primary) | mean must **fall** | A n=46: mean **1896.7** / med 1906 t -> B mean **1483.0** / med 1360 t = **-413.7 t (-21.8 %)**; paired both-carried n=33: **32 faster / 1 slower**, mean -510.3 t, sign p = **0.0000** | **PASS** |
| B1c | fired / non-fired control | report | fired n=30: **-554.8 t (-29.4 %)**; no-fire control n=16: -149.2 t (-7.8 %, branch/instrumentation) | report |
| B2 | lock-on (`premove+axis+hover+wait`, median) | <= +5 % | 2.830 -> 3.080 s (**+8.8 %**); W7-B decomposition park 0.65 -> 0.71 s, hold 0.86 -> 0.80 s | **FAIL** |
| B3 | pooled median per-attempt ticks | <= +5 % | 1854 -> 1380 t (**-25.6 %**) | **PASS** |
| B4 | zero new failure reasons | none new | **none** (both arms: trigger note only / + "fruit did not follow the gripper") | **PASS** |
| 6 | fire -> boundary remainder + re-seats | record | median **63 t** (mean 71; 43 fires; 3 at tick 0); re-seats **0/0** (both arms; `FRUIT_CARRY_GUARD` off) | recorded |
| K2 | monitor aborts of would-be placements | <= 2 per 75 | **0** (section 3.3) | **PASS** |
| K4 | any new failure reason | none | none | PASS |
| K5 | no-harm drift | byte-identical | 365/365 + 442/442 + all gates PASS | PASS |

B2's per-run spread (median delta): +7.1 %, +31.0 %, +9.4 %, -1.8 %, +3.7 % -
four of five runs positive; the pooled median-of-attempts is the pre-registered
reading and it is over the bar. The P7-2b battery's same-shaped pair read
+2.7 %; these two batteries are two samples (the direct loop conditions on
rendered frames), and the frozen bar is applied to this battery's reading:
+8.8 % (frozen cohort +10.0 %) -> **FAIL**, which is the binding negative.

### 3.3 K2 and the `asym@fire` diagnostics - the point of P8-2

K2's frozen definition: a fire on a leg whose live `[carry]` line reads
`clean_slip_max <= 2.0 mm` and the attempt ends not-placed by the skip; kill
when **> 2 per battery**.

| read | P7-2b (killed) | P8-2 (this battery) |
| --- | --- | --- |
| fires / fired attempts | 56 | 43 / 43 (one per attempt) |
| fires on clean carry legs | **5** | **0** |
| K2 aborts | **5 > 2 -> KILL** | **0 <= 2 -> PASS** |
| fired-leg `clean_slip_max` (min) | 0.1-1.0 mm (the clean class) | **17.9 mm** (9x the clean threshold) |
| `asym@fire` at the clean-class fires | n/a (no floor) | none; min over all fires **3.53** (an escape leg), frozen-cohort min **3.74**, median 5.17, max 12.33 |
| fires with `asym@fire < 3.5` (exemption path) | n/a | **0** |

Every one of the 43 fires landed on an **escaping** leg (clean_slip_max
17.9-2061.7 mm; 41 classed carried-not-placed, 2 classed no-contact with the
payload fully gone). The clean-leg population that killed P7-2b (one-sided
low-force holds, `force_min` 1.51-3.26 N there) **never fired** here: clean-leg
denominator **49/105** B carry legs (A 47/146); clean attempts **25/75** B (A
22/75). The offline fix's prediction ("expected live clean aborts 0-2, was 5")
is confirmed live at **0**, and the K2 kill class is cleared.

Fire denominators: all 43 fires are `grasp_lift` legs; `[monitor] attempt`
vs fire-line counts agree on every attempt (0 mismatches); 43 skipped attempts
= the 43 fired attempts (each fired attempt ended not-placed at the leg
boundary).

### 3.4 Mechanism reads

* **The skip is the truncation** (as pre-registered): fired-subset interval
  -554.8 t vs the no-fire control -149.2 t; the fast-skip writes off the
  marginal recoverable escapes - A placed **3 of 53** escape-lift attempts
  (6 %; slips 10.5->25.5 mm class) while B placed **0 of 50**, and both arms
  placed 100 %/96 % of clean-lift attempts (A 22/22, B 24/25; B's single
  clean-lift non-placed is run4 ep11 lychee with **no fire and no skip** - not
  a monitor event). This is the P7-2b-decomposed cost class, unchanged.
* **No new reasons** (`113`: both reason sets identical; verdict "no measured
  improvement of B over A" - rate 32 % vs 33 %, sign p = 0.6562).
* The B2 cost is a whole-system measure of enabling the monitor (its per-tick
  tactile+logit reads during carry legs plus the skip action); this battery
  does not separate instrumentation from action (AGENTS section 2 warns
  per-tick loop work shifts runs; P7-2b's B2 read +2.7 % with the same
  coupling).

## 4. No-harm chain (step 4; drift tree - see section 5)

| item | reading |
| --- | --- |
| two-line dense knob-off re-record (`40_twoline_dense.log`) | **7/10, 9.1 s/attempt**; `--physics-only` **442/442 IDENTICAL** to `logs/w7/10_dense_twoline_1.log`; `190` **PASS** (`fingerprint: matches configs/motion_reference_twoline.json`, floor 0.60) |
| `scripts/selfcheck.sh` (`SELFCHECK_LOG` under `logs/p8d/`) | **PASS 0 failures, 1 skipped** |
| `scripts/172_supply_selftest.py` | **74 checks ok** |
| ops | mid **OK** (01:07:11), end **OK** (02:21:16); a manual mid-batch check (01:20) also OK; no stall, no wedge, all runs `[fruit] DONE` |

The monitor's own default-off byte-inertness on the direct path is held by
section 2 (365/365); on the two-line path by the 442/442 (the `[monitor]`
lines: **0 in arm A**, and none outside direct-capture scope).

## 5. The tree-drift audit (freeze violation; `92_tree_drift_audit.txt`)

* The frozen-tree premise broke at **01:58:53 (tasks.py) / 01:59:18
  (rl_env.py)**: the P9-A lane's edit (default-off, single-arm-scoped
  `FRUIT_READY_SKIP`/`SETTLE` + pure-reporting `FRUIT_READY_DIAG`; the
  working-tree diff == `logs/p9a/10_diff.patch`) landed while the A/B batch was
  running. HEAD is still `402ad8a`; the drift is uncommitted.
* Per-run provenance (the RL env hashes the live `tasks.py` and refuses a
  mismatched tree, so each raw manifest pins the code actually imported):
  **runs 1-4 (A and B) pinned `12feced3` (the frozen tree); run 5 pinned
  `255f2819` (the drift tree)**. No run started inside the 25-second mismatch
  window (B_4 imported at 01:55:40; A_5 at 02:02:05).
* Cohort re-read (`logs/p8d/B_cohort_split.txt`, reusing the pinned
  `C_endpoints.py` parser):

| endpoint | frozen cohort (runs 1-4, 120 attempts) | drift cohort (run 5, 30 attempts) | full battery |
| --- | --- | --- | --- |
| B1 pooled | **-23.2 %** (paired 29-1, p=0.0000) | -13.8 % (3-0) | -21.8 % |
| B2 lock-on | **+10.0 % FAIL** | +3.7 % | +8.8 % FAIL |
| B3 cycle | -27.6 % | -3.8 % | -25.6 % |
| B4 new reasons | none | none | none |
| K2 aborts | **0** (40 fires, all escapes) | 0 (3 fires) | 0 (43 fires) |

**The binding negative (B2 > +5 %) and the K2 clearance both hold on the
frozen cohort alone**, so every pre-registered verdict is unchanged. Steps
1-2 (stub gate, acceptance) ran entirely on the frozen tree; the no-harm chain
tail (two-line/selfcheck/172/reports) ran on the drift tree, and its 442/442
byte-identical stream is itself evidence the P9-A edit is inert on that path.
Consequence: the whole-battery pin (prereg 7.8, `00 == 90`) is invalidated as
such; the per-run manifests and the frozen-cohort read are the reads of
record. Process note: `154_claim_run.sh` serializes *simulators*, not `src/`
writers - a future battery needs its freeze window coordinated (the re-pin
"after all writers stop" was not achievable here).

## 6. Verdict against the pre-registration (7.4/7.5)

| item | threshold | measured | verdict |
| --- | --- | --- | --- |
| K1 offline gate | macro-F1 >= 0.86, FP <= 2/33 | in hand: macro-F1 1.000, FP 0/33, escapes 31/31; stub pins re-verified at battery time | PASS |
| B1 primary | interval must fall | **-21.8 %** pooled; paired **32-1**, p = 0.0000 | PASS |
| B2 lock-on | <= +5 % | **+8.8 %** (+10.0 % frozen cohort; per-run +7.1/+31.0/+9.4/-1.8/+3.7) | **FAIL** |
| B3 cycle | <= +5 % | -25.6 % | PASS |
| B4 new reasons | none | none | PASS |
| K2 clean-leg aborts | <= 2 | **0** (was 5) | PASS |
| K3 re-seat rise | B' only | B' not run (conditional) | n/a |
| K4 new reason | none | none | PASS |
| K5 no-harm | byte-identical | acceptance 9/10 + fingerprint + 365/365; two-line 442/442 + `190`; selfcheck; `172` | PASS |

**Verdict: B does not pass; publish the negative.** The load-floor fix does
exactly what it was built to do - the K2 clean-leg kill class is gone
(**5 -> 0**; 43/43 fires on escaping legs; the pre-registered "0-2 expected"
read 0) and the B1 interval lands hard (-21.8 %, paired 32-1) - but the
pre-registered **B2 lock-on bar (+5 %) is missed at +8.8 %** (frozen cohort
+10.0 %), so the form is **not adopted**: `FRUIT_CARRY_MONITOR` stays unset,
`FRUIT_CARRY_MONITOR_LOAD_FLOOR` stays `0.0`, and no shipped default changes.
B-prime remains not run (conditional on B passing; its re-seat form is not
built). The named residual for any successor: keep the clean-fire clearance
and the interval while not paying the lock-on (the monitor's per-tick
instrumentation + skip coupling, unseparated here), and note the P7-2b battery
read +2.7 % on the same bar - the B2 endpoint is the noisy one of the set
(4/5 runs positive here).

## 7. Exact commands and env

```
# 1  stub gate (offline; frozen tree)
python3 logs/p7c/verify_monitor_stub.py                > logs/p8d/10_stub_p7c_floor0.txt
python3 logs/p8c/verify_monitor_stub_lf.py             > logs/p8d/11_stub_lf_floor35.txt
STUB_FLOOR=0 python3 logs/p8c/verify_monitor_stub_lf.py > logs/p8d/12_stub_lf_floor0.txt
python3 logs/p8c/verify_monitor_stub_lf_p81.py         > logs/p8d/13_stub_p81_both.txt

# 2  knob-off shipped acceptance (RUN_LIMIT=2400)
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p8d/20_accept_noharm.log \
    HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10 \
    scripts/run.sh scripts/20_pick_place.py
python3 scripts/105_motion_regression.py logs/p8d/20_accept_noharm.log \
    --fingerprint configs/motion_reference.json
python3 logs/w4/compare_streams.py --physics-only \
    logs/p8d/20_accept_noharm.log logs/p2d/90_accept.log

# 3  the N=5 paired direct A/B (RUN_LIMIT=18000; one claim)
RUNS=5 EPISODES=15 AB_SEEDS="77 101 202 303 404" AB_POLICY_SEED=11 \
  AB_DIR=logs/p8d/B_direct_ab \
  ARM_A="--ckpt checkpoints/moe_v13s/policy_best.pt" \
  ARM_B="--ckpt checkpoints/moe_v13s/policy_best.pt" \
  ARM_B_ENV="FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5 FRUIT_CARRY_MONITOR_DIAG=1" \
  AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_CARRY_DIAG=1" \
  bash scripts/112_rl_ab.sh
# reports (offline, read-only):
python3 logs/p7c/C_endpoints.py --dir logs/p8d/B_direct_ab --a A --b B     # C_endpoints.txt
python3 logs/p8d/p8d_monitor_report.py --dir logs/p8d/B_direct_ab --a A --b B  # B_monitor_report.txt
python3 logs/p8d/p8d_cohort_split.py --dir logs/p8d/B_direct_ab            # B_cohort_split.txt
python3 logs/p8d/p8d_skip_cost.py --dir logs/p8d/B_direct_ab --a A --b B   # B_skip_cost.txt
python3 logs/w7/B_ab_report.py   --dir logs/p8d/B_direct_ab --a A --b B    # B_mech.txt
python3 logs/w8/A_pairs.py       --dir logs/p8d/B_direct_ab --a A --b B    # B_pairs.txt
python3 scripts/113_rl_report.py logs/p8d/B_direct_ab --a A --b B          # B_verdict.txt

# 4  no-harm chain (RUN_LIMIT=3600)
RUN_LIMIT=3600 scripts/154_claim_run.sh logs/p8d/40_twoline_dense.log \
    HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 SEED=5 \
    FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10 \
    scripts/run.sh scripts/20_pick_place.py
scripts/190_twoline_gate.sh logs/p8d/40_twoline_dense.log
python3 logs/w4/compare_streams.py logs/p8d/40_twoline_dense.log logs/w7/10_dense_twoline_1.log
SELFCHECK_LOG=logs/p8d/50_selfcheck_internal.log scripts/selfcheck.sh
python3 scripts/172_supply_selftest.py
```

## 8. Pins

| item | start (01:01:28) | end (02:21) |
| --- | --- | --- |
| HEAD / branch | `402ad8a` / `p-supply` | unchanged |
| `tasks.py` | `12feced3b6204f06bb32cb878efb5e15` | **`255f28195191c53e414582f303d177d0` (drifted, P9-A)** |
| `rl_env.py` | `7bd07b662595c56fa45ca12e7a87a7ff` | **`e46700671b589ba0c2a48322e4b5c5c7` (drifted, P9-A)** |
| `trigger.py` / `runtime.py` / `fruits.py` | `d7ec85fc` / `ffb76bfd` / `f5671a65` | unchanged |
| checkpoint `moe_v13s` | `61da390a85fa209496b54477a8255d23` | unchanged |
| `configs/*` | untouched | untouched |
| per-run manifests | - | runs 1-4 `tasks_md5=12feced3`; run 5 `255f2819` (section 5) |

## 9. Named residuals

1. **The B2 cost is a whole-system read** (monitor per-tick reads + skip
   action); not separated by this battery. A successor lever needs the
   interval/K2 wins without the lock-on cost.
2. **B2's sample variance**: +2.7 % (P7-2b) vs +8.8 % here (frozen +10.0 %);
   the per-run spread is +7.1..+31.0(vs -1.8); the frozen bar applied to this
   battery's reading is the verdict of record.
3. The marginal-escape write-off (A recovered 3/53 escape lifts; B 0/50) is
   inherent to any fast-skip at this trigger (P7-2b's residual, unchanged).
4. **Process**: the frozen-tree premise was violated by a concurrent offline
   lane (section 5). The verdicts survive the cohort split, but neither the
   whole-battery pin nor a clean re-run on `12feced3` is possible now (the
   working tree carries the P9-A WIP); a re-run is NOT required to settle the
   negative (the frozen cohort alone fails B2 and clears K2).

## 10. Artifact list (`logs/p8d/`)

`00_outer.log`, `00_head.txt`, `00_git_status.txt`, `00_tree_pins.txt`,
`00_harness_pins.txt`, `01_ops_start.txt` / `02_ops_mid.txt` / `03_ops_end.txt`;
step 1: `10_stub_p7c_floor0.txt`, `11_stub_lf_floor35.txt`,
`12_stub_lf_floor0.txt`, `13_stub_p81_both.txt`; step 2:
`20_accept_noharm.log`, `21_accept_driver.log`, `22_motion_noharm.txt`,
`23_compare_noharm.txt`; step 3: `B_direct_ab/` (A_1..5, B_1..5 + `raw/`
manifests), `B_driver.log`, `C_endpoints.txt`, `B_monitor_report.txt`,
`B_cohort_split.txt`, `B_skip_cost.txt`, `B_mech.txt`, `B_pairs.txt`,
`B_verdict.txt`, `B_carry_lines_ab.txt`, `B_monitor_lines.txt`; step 4:
`40_twoline_dense.log`, `41_twoline_driver.log`, `42_twoline_gate.txt`,
`43_compare_twoline.txt`, `50_selfcheck.txt` (+ `50_selfcheck_internal.log`),
`51_supply_selftest.txt`; audit: `92_tree_drift_audit.txt`;
pins: `90_tree_pins_end.txt`, `91_git_status_end.txt`; tools: `run_p8d.sh`,
`p8d_monitor_report.py`, `p8d_cohort_split.py`, `p8d_skip_cost.py`;
this file + `WORKLOG_entry.md`.
