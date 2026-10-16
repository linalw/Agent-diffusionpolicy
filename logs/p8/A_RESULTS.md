# P8 A RESULTS: `FRUIT_SUPPLY_TRICKLE_LATE_S=1.2` on the shipped single-arm scattered line and the two-line patch battery - both regress; the H1 win does not transfer; recommendation: **neither line**

Branch `p-supply`, HEAD `0a48ce9` (tag `p7-gate`), Tier-A solo (one simulator
lane via `scripts/154_claim_run.sh`), 2026-10-16/17. Every simulator step ran
under its own claim; ops self-check start/mid/end (`01_ops_start`:
STALLED-CHAIN on an idle pre-battery machine, report-only; `02_ops_mid` and
`03_ops_end`: OK; `04_ops_final` after the extras: STALLED-CHAIN, report-only,
idle finished machine). No `src/` or `scripts/` edit, no shipped-default
change, writes only under `logs/p8/`. Parent evidence: `logs/p4c/H1_ACTUATOR.md` +
`logs/p4c/H1_RESULTS.md` (the knob's positive, measured **only** on the starved
single-arm apple D=1.6 branch: empty 70 % -> 0 %), `logs/p4/A_DIAGNOSIS.md`
(the burst-drain mechanism; the two-line inheritance of `_pump_supply` was
disclosed untested there), AGENTS.md sections 1, 2, 3b.

## 0. Verdict up front

| # | battery item | verdict |
| --- | --- | --- |
| 1 | no-harm acceptance, knob OFF | **PASS** - 9/10, motion gate PASS, `fingerprint: matches`, 365/365 identical to `logs/p2d/90_accept.log` |
| 2 | shipped single-arm scattered line + trickle 1.2 | **FAIL** - not inert; 2/10 empty slots (record 0/10), 4/8 = 50 % < 0.75 floor, stream differs (293 vs 365) |
| 3 | two-line patch battery + trickle 1.2 | **FAIL** - 7/20 = 35 % vs control 12/20 (floor 0.5), starved polls 41 -> 81, both 105 and 190 fail |
| 4 | no-harm chain | **PASS** - dense 442/442 identical + `190` PASS; `selfcheck.sh` PASS 0 failures; `172` 74 checks OK |

**Adoption: neither line** (the single-arm-scoped variant is also not
supported - the regression is on exactly the shipped single-arm acceptance).
The knob stays default `0`; its measured positive survives only in the H1
starved-D=1.6 scope. Details, mechanism and the (hypothetical) re-baseline list
below.

## 1. Exact commands and env

Battery driver `logs/p8/run_p8.sh` (returns; `.log`s in `logs/p8/`), extras
driver `logs/p8/run_p8_extras.sh`, both via the claim wrapper. Base acceptance
env = `accept.sh`'s own (`HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10`);
patch battery env = the W6-B/W7-A shape (`HEADLESS=1 FRUIT_MOTION_REPORT=1
FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5 FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1
FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25`).

```
# 1  no-harm acceptance, knob OFF                              (RUN_LIMIT=2400)
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p8/10_accept_noharm.log \
    HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10 \
    scripts/run.sh scripts/20_pick_place.py
python3 scripts/105_motion_regression.py logs/p8/10_accept_noharm.log \
    --fingerprint configs/motion_reference.json
python3 logs/w4/compare_streams.py --physics-only \
    logs/p8/10_accept_noharm.log logs/p2d/90_accept.log

# 2  single-arm shipped scattered line, knob ON                 (RUN_LIMIT=2400)
... same + FRUIT_SUPPLY_TRICKLE_LATE_S=1.2 FRUIT_SUPPLY_DIAG=1
#    (log logs/p8/20_accept_trickle12.log; gate 22_; compare 23_; readout 24_)

# 2b knob-ON double, no DIAG                                    (RUN_LIMIT=2400)
... + FRUIT_SUPPLY_TRICKLE_LATE_S=1.2        (log logs/p8/25_accept_trickle12_b.log)
# 2c knob-OFF + DIAG control (extras)                          (RUN_LIMIT=2400)
... + FRUIT_SUPPLY_DIAG=1                    (log logs/p8/55_accept_control_diag.log)

# 3a two-line patch CONTROL on this tree                        (RUN_LIMIT=5400)
RUN_LIMIT=5400 scripts/154_claim_run.sh logs/p8/36_patch_control.log \
    HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5 \
    FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_PATCH=1 \
    FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 \
    scripts/run.sh scripts/20_pick_place.py
# 3b two-line patch battery, knob ON                            (RUN_LIMIT=5400)
... same + FRUIT_SUPPLY_TRICKLE_LATE_S=1.2 FRUIT_SUPPLY_DIAG=1
#    (log logs/p8/30_patch_trickle12.log)
python3 scripts/186_w6_report.py logs/p8/30_patch_trickle12.log \
    logs/p8/36_patch_control.log logs/w6/31_lever_park_1.log --label p8
python3 scripts/105_motion_regression.py logs/p8/30_patch_trickle12.log \
    --min-success-rate 0.5
TWOLINE_REF=configs/motion_reference_patch.json TWOLINE_FLOOR=0.5 \
    scripts/190_twoline_gate.sh logs/p8/30_patch_trickle12.log
# 3c knob-ON double, no DIAG                                    (RUN_LIMIT=5400)
... + FRUIT_SUPPLY_TRICKLE_LATE_S=1.2        (log logs/p8/39_patch_trickle12_b.log)

# 4  no-harm chain                                              (RUN_LIMIT=3600)
RUN_LIMIT=3600 scripts/154_claim_run.sh logs/p8/40_twoline_dense.log \
    HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 SEED=5 \
    FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10 \
    scripts/run.sh scripts/20_pick_place.py
scripts/190_twoline_gate.sh logs/p8/40_twoline_dense.log
python3 logs/w4/compare_streams.py logs/p8/40_twoline_dense.log \
    logs/w7/10_dense_twoline_1.log
scripts/selfcheck.sh ; python3 scripts/172_supply_selftest.py
```

Wall times (outer logs): step 1 exit 23:03:07, step 2 23:07:25, 3a 23:16:25,
3b 23:25:38, 3c 23:34:49, 2b 23:39:05, step 4 23:43:46, selfcheck/172 23:44:18;
extras 2c 23:44:43 -> 23:49:46. All runs `exit=0`, `[fruit] DONE`, no wedge.

## 2. Pins (start = end, `00_tree_pins.txt` = `90_tree_pins_end.txt`)

| file | md5 |
| --- | --- |
| `src/fruit_sorting/fruits.py` (the trickle live here) | **f5671a65d6f72eb69a81e12ac6e0bf53** |
| `src/fruit_sorting/tasks.py` | `7489f302c14e65aa9771f674e4ee199b` |
| `src/fruit_sorting/rl_env.py` | `75b315d3c9a2680d973dabeac045b631` |
| `scripts/172_supply_selftest.py` | `45e18029556969cb744cc3c763684b1e` |
| `scripts/105_motion_regression.py` | `16a3d790ca5fbc06d8afe3229daaec37` |
| `scripts/186_w6_report.py` | `492428759291f779cf65cf26fc974790` |
| `scripts/190_twoline_gate.sh` | `a24cfc5b610cde99366a4044cc15490b` |
| `scripts/154_claim_run.sh` | `1a5adba65df4e4e825ad798287de12eb` (reaping fix b06c948 included) |
| `logs/w4/compare_streams.py` | `f912521c94a00d286857ca0a8a41f507` |
| `configs/motion_reference.json` | `b9e72ca79f6004c9a7e81219fe71b114` |
| `configs/motion_reference_twoline.json` | `181c9151d65cf2c1f5be16b4c37c8f1e` |
| `configs/motion_reference_patch.json` | `b08dd3e934c3a74a0f63aac9c211dd9a` |

`configs/*` untouched. Parallel-lane note: `scripts/205_c3_fp_retry.py`
(mtime 23:26) and `logs/p8/B_OFFLINE.md` / `logs/p8/PREREG_CARRY_MONITOR_LF.md`
(23:41/23:44) are the parallel **P8 B-lane's** offline C-3 carry-monitor work
(Tier C, no simulator); no overlap with this battery's runs, not touched by
this battery.

## 3. The batteries

### 3.1 Step 1 - no-harm acceptance, knob OFF

| endpoint | reading |
| --- | --- |
| success | **9/10 = 90 %** (`[stats]` 15.2 s/attempt, `diverted=0`, `gate_open=0.0`) |
| motion gate | **PASS**, all 10 descents inside budget (worst `\|v\|max` 0.116 vs 0.160-0.161; lurch 0.017 vs 0.291); 5 reported cone warnings, the record's own |
| fingerprint | **`fingerprint: matches configs/motion_reference.json`** |
| stream | `--physics-only` vs `logs/p2d/90_accept.log`: **365/365 IDENTICAL** |

### 3.2 Step 2 - shipped single-arm scattered line + trickle 1.2 (FAIL)

The knob is **not inert** here: `logs/p8/20_accept_trickle12.log` is a different
branch (293 vs 365 physics lines; first difference line 32 = the
`[supply] trickle feed:` banner; the stream diverges from the first pump).

| endpoint | shipped record (`p2d/90`) | trickle 1.2 | verdict |
| --- | --- | --- | --- |
| success | 9/10 = 90 % | **4/8 = 50 %** | FAIL (floor 0.75) |
| slots / empty slots | 10 / **0** | 10 / **2** (attempts 2, 3; `active=[]`) | FAIL (no-regression) |
| 105 per-leg budgets | all inside | **all 8 descents inside** (worst `\|v\|max` 0.1130 vs 0.160-0.161; lurch 0.017 vs 0.291) | PASS (the FAIL is rate-only) |
| catch taxonomy | 9 placed / 1 grasped-not-placed (kiwi, `trips=38`) / 0 never-grasped | 4 placed / 3 grasped-not-placed (all `trips=38`) / 1 never-grasped (`fruit did not follow the gripper`, `trips=54 opened=3.00`) | same classes, more of them; **no new reason string** |
| supply readout (DIAG) | 2c control: 14 windows, due=106, **rel=28** (hist 1:4, 2:6, 3:4), past=78, **late=0.01-4.68 s** | 13 windows, due=89, **rel=10** (hist 0:3, 1:10), past=65, **late=0.00-1.12 s**, stale=14 consumed | knob active, delivery thinned |
| double (2b, no DIAG) | - | **293/293 IDENTICAL** | determinism + DIAG neutrality |

Empty-slot rows carry the spawner stats at both: `released=4 fell_off=3
discharged=1 supply_skipped=26 supply_trickled=6` - the budget was not the
issue; the belt simply held no selectable fruit at the poll.

### 3.3 Step 3 - two-line patch battery + trickle 1.2 (FAIL)

Control provenance: `logs/p8/36_patch_control.log` is **861/861 identical** to
`logs/w6/31_lever_park_1.log` (= `logs/w7/20_patch_battery_1.log`; the
`configs/motion_reference_patch.json` branch - extras `39_patch_control_105.txt`
exit=0 and `39b_patch_control_190.txt` PASS verify it on this tree). The P7
default-off additions are byte-inert on this path.

| endpoint | control (w6/31 = 3a) | trickle 1.2 (3b) | verdict |
| --- | --- | --- | --- |
| success | **12/20 = 60 %** | **7/20 = 35 %** | FAIL (floor 0.5) |
| per arm | left 4/10, right 8/10 | left 2/10, right 5/10 | both arms down |
| starved polls (`no eligible fruit`) | left 19 / right 22 = **41** | left 43 / right 38 = **81** | FAIL (x1.98) |
| pooled inter-placement interval | 16.53 / 17.30 / 19.90 s (mean/p50/p90, n=11) | 27.38 / 28.65 / 37.70 s (n=6) | descriptive (denominators moved with the count) |
| placement-window rate | 3.63 placed/min (181.8 s) | 2.19 placed/min (164.3 s) | FAIL-side |
| per-attempt span (186) | 15.08 s | 15.26 s | flat (the loss is availability, not cadence) |
| lock-on latency L/R | 3.73 / 5.27 s | 6.24 / 5.20 s | left starves (retries [2,0,3,0,2,6,20,0,9]) |
| idle fraction L/R | 18 % / 24 % | 28 % / 23 % | - |
| failure classes | 8 = 1 never-grasped + 7 grasped-not-placed | **13 = 3 never-grasped + 10 grasped-not-placed** | same classes, more of them |
| `105`/`190` (patch reference) | PASS (extras) | **FAIL** - rate (7/20 < 50 %) and fingerprint differs (16/20 legs; a different attractor, expected for a moved branch) | FAIL |
| descents | - | all 20 inside (worst `\|v\|max` 0.110 vs 0.160-0.161; lurch 0.019) | budgets clean |
| supply readout (DIAG) | - | 50 windows, due=153, **rel=75** (hist 0:5, 1:15, 2:30), past=64, stale=43, queue=1, **late=0.00-1.09 s** | thinned clumps |
| double (3c, no DIAG) | - | **892/892 IDENTICAL** | determinism + DIAG neutrality |

`gate_open=0.0 s`, `queue_peak=0`, `recirculated=0`, zero `indexed:` in both
runs - the never-stop invariant holds; the regression is acquisition, not the
gate.

### 3.4 Step 4 - no-harm chain (PASS)

| item | reading |
| --- | --- |
| dense two-line knob-off re-record (`40_twoline_dense.log`) | 7/10, 9.1 s/attempt, 4.60 fruits/min, left 2/5 right 5/5; `--physics-only` **442/442 IDENTICAL** to `logs/w7/10_dense_twoline_1.log`; `190` **PASS** (fingerprint matches the two-line reference, floor 0.60) |
| `scripts/selfcheck.sh` | **PASS 0 failures, 1 skipped** (`50_selfcheck.txt`; `logs/selfcheck.log`) |
| `scripts/172_supply_selftest.py` | **74 checks, ok** (`51_supply_selftest.txt`) |
| ops | mid OK, end OK (`02_ops_mid.txt`, `03_ops_end.txt`) |

## 4. The mechanism (measured, not inferred)

**The cap cuts the band the shipped pump uses as its supply.** On the shipped
scattered line the paired first pump window (same `t=6.833 s`, same `due=5`,
same `past=2`) reads:

* control (knob off): `rel=3  late=0.49-2.47 s` - it delivers the three due
  slices at their virtual positions, 0.49-2.47 s of belt travel upstream;
* trickle: `rel=1  late=0.04 s  stale=2` - it drops exactly the 0.49-2.47 s
  slices and keeps only the freshest.

Whole-run bands: control `late=0.01-4.68 s`, trickle `0.00-1.12 s`. The two
empty slots are the pump windows where the fresh window contained nothing
(`t=51.900`: `due=9 past=7 stale=2 late=none`; `t=95.8` similar) - with the
backlog consumed-and-skipped, the poll finds `active=[]`. That is the *v9
stocked-line* design working in reverse: the shipped line deliberately stocks
the approach segment with fruit that is 1.2-4.8 s late, and that is precisely
the band the cap removes.

**The two-line patch battery shows the same mechanism through the worker.** Its
worker parks and re-polls every ~0.5 s, so starvation surfaces as retries, not
forfeited slots (P4-A): starved polls 41 -> 81 (+98 %), left lock-on 3.73 ->
6.24 s (one interval with 20 retries), placements 12 -> 7 with the per-attempt
span flat (15.08 -> 15.26 s). The delivered shape (<= 2 bodies/window from a
0.00-1.09 s band) cannot feed two stations that the shipped pump's 6-body
clumps fed.

**Why H1 was positive and this is negative (same actuator, opposite sign):**
H1's scenario (single-species apple, D=1.6, single arm) had a 70 % empty
fraction caused by one 6-body clump topping out at 0.375 m - *below* the
0.399 m selection floor - so the lateness beyond 1.2 s was the *defect*, and
the fresh-only delivery landed above the floor. On the shipped scatter and the
patch sheet the 1.2-4.8 s band is the *stock* the poll/worker consumes. The cap
is scenario-tuned (1.2 s > the widest D=1.6 slice period 1.146 s, H1's design
invariant); the supplied scenarios' own arrival structure (scatter gap periods
0.83-2.92 s; patch slice periods 1.17-1.83 s) is not covered by that invariant.

**Quantized-outcome caveat (AGENTS section 2):** every success count here is a
single deterministic branch. The primary reads are the structural ones - empty
slots, starved polls, delivered-lateness bands - not cross-configuration rate
deltas.

## 5. Verdict per endpoint

| battery item | endpoint | verdict |
| --- | --- | --- |
| 1 | 9/10 + gate PASS + fingerprint matches + 365/365 | **PASS** |
| 2 | no regression vs the shipped record (success >= dynamic floor) | **FAIL** (4/8 = 50 % < 75 %; 2 empty slots where the record has 0) |
| 2 | per-leg budgets via 105 | **PASS** (rate-only FAIL) |
| 2 | catch taxonomy | no new reason; more grasp/carry-class failures |
| 2 | record empty-slot count + supply readout | done (2/10; diag tables above) |
| 2 | "if the knob is inert" | it is **not** inert |
| 3 | starvation counts | **FAIL** (41 -> 81) |
| 3 | pooled interval | reported (16.53 -> 27.38 s mean; denominators moved) |
| 3 | success | **FAIL** (7/20 < 50 %) |
| 3 | per-scenario gate | **FAIL** (rate + branch fingerprint; budgets clean) |
| 4 | 442/442 + 190 + selfcheck + 172 | **PASS** |

## 6. Adoption recommendation and the (would-be) re-baseline list

**Recommendation: neither line.** The one-line default change
(`FRUIT_SUPPLY_TRICKLE_LATE_S=1.2`) is not supported for the single arm -
it regresses exactly the shipped single-arm acceptance line (the line it would
ship on) - and not for the two-line (it regresses the W6-A patch battery with
the never-stop invariant intact). The knob is global in `_pump_supply`, so a
"single-arm only" variant would also require a new scope gate in code (the
`_dynamic_profile` pattern), which buys a regression. Keep the default `0`;
the knob remains a measurement instrument for starved dense supplies (its H1
D=1.6 win stands in that scope only).

If an owner decision ever overrides this, the full re-baseline list would be:

* **single arm**: `configs/motion_reference.json` re-recorded (the acceptance
  lands in a different attractor: 293/365 lines, empty slots 0 -> 2), the
  `p2d/90`-class acceptance records and the AGENTS section 2 v9 paragraph, and
  any new `40_collect_demos.py` single-arm store becomes a new branch
  (manifest pins);
* **two-line**: `configs/motion_reference_patch.json` re-recorded (patch
  branch), `configs/motion_reference_twoline.json` re-recorded (the dense path
  inherits `_pump_supply`), the `190` floors, the two-line rate claims, and the
  collector's two-line manifests;
* **both**: the supply-scenario docs (`logs/w6/`, `logs/p8/`) and the H1 note
  scoping its positive to the starved D=1.6 branch.

## 7. Unresolved items / limits

1. The dense two-line branch with the knob ON was **not** run (the adoption
   question is closed by the patch + single-arm negatives; named only if the
   knob is ever reconsidered).
2. The cap is tied to the widest D=1.6 slice period (1.146 s < 1.2 s); on the
   shipped scatter, gap periods run to 2.92 s, so windows with no fresh slice
   exist (3/13 measured, two of them the empty slots). The named generalisation
   is a schedule-adaptive cap (or a deliver-the-selectable-band rule), not
   built (H1_RESULTS section 8).
3. The trickle's patch failure classes include 3 never-grasped vs 1 in the
   control - a baseline grip class, not isolated here from the acquisition
   starvation.
4. One scenario + one seed per configuration; single-branch counts (AGENTS
   section 2). No cross-configuration success-rate delta is claimed as a
   result.
5. The two-line worker absorbs starvation as idle (P4-A), so the comparable
   read is the raw starved-poll count; per-arm idle (18/24 % -> 28/23 %) and
   lock-on are reported above.
6. The claim wrapper's watchdog reap (b06c948) was exercised on all 7 runs;
   every wrapper reaped cleanly (no orphan `sleep`).
7. The parallel P8 B-lane's offline artifacts (`scripts/205_c3_fp_retry.py`,
   `logs/p8/B_OFFLINE.md`, `logs/p8/PREREG_CARRY_MONITOR_LF.md`) share this
   log area; they are Tier C (no simulator) and did not overlap this battery's
   runs; this battery did not touch them.

## 8. Artifact list (`logs/p8/`)

`00_outer.log`, `00_head.txt`, `00_git_status.txt`, `00_tree_pins.txt` +
`90_tree_pins_end.txt` (identical), `91_git_status_end.txt`, `01_ops_start.txt`
/ `02_ops_mid.txt` / `03_ops_end.txt` / `04_ops_final.txt`; step 1: `10_accept_noharm.log`,
`11_accept_driver.log`, `12_motion_noharm.txt`, `13_compare_noharm.txt`;
step 2: `20_accept_trickle12.log`, `21_trickle_driver.log`,
`22_motion_trickle.txt`, `23_compare_trickle_vs_record.txt`,
`24_trickle_readout.txt`, `25_accept_trickle12_b.log`,
`26_trickle_b_driver.log`, `27_compare_trickle_double.txt`;
step 3: `36_patch_control.log`, `37_patch_control_driver.log`,
`38_compare_patch_control.txt`, `30_patch_trickle12.log`,
`31_patch_trickle_driver.log`, `32_patch_report.txt`, `33_motion_patch_trickle.txt`,
`34_patch_twoline_gate.txt`, `35_patch_trickle_readout.txt`,
`39_patch_trickle12_b.log`, `40_patch_trickle_b_driver.log`,
`41_compare_patch_double.txt`, `39_patch_control_105.txt`,
`39b_patch_control_190.txt`;
step 4: `40_twoline_dense.log`, `41_twoline_driver.log`, `42_twoline_gate.txt`,
`43_compare_twoline.txt`; offline: `50_selfcheck.txt`, `51_supply_selftest.txt`;
extras: `55_accept_control_diag.log`, `56_control_diag_driver.log`,
`57_compare_control_diag.txt`, `58_control_diag_readout.txt`;
tools: `run_p8.sh`, `run_p8_extras.sh`, `60_diag_agg.py`;
the WORKLOG entry text: `WORKLOG_entry.md` (this battery writes only under
`logs/p8/`, so the root `WORKLOG.md` append is left to the wrap step - the
entry is ready verbatim).
