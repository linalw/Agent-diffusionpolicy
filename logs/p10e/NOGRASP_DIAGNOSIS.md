# P10-E: the two-line scripted catch's no-grasp class — census, mechanism, levers (offline diagnosis)

Status: **offline analysis of the existing P10-C/C.2/C.3 logs** (no simulator run; the P10-D.1
policy battery was running on the same machine throughout). Read-only over `src/`; all
artifacts under `logs/p10e/`. Date 2026-10-18 (analysis of the 2026-10-17 batteries).

Evidence base (all read, none re-run): `logs/p10c/10_armA_diag`, `20_armB_1`, `22_armB_diag`,
`50..53_seed*`; `logs/p10c2/60..63`; `logs/p10c3/70..74`; the run drivers' env
(`run_battery.sh` / `run_seeds.sh`); `src/fruit_sorting/tasks.py` (row semantics);
`logs/w8/B_metric.py` + `logs/w8/B_RESULTS.md` (the carry metric and its corpus);
`logs/w7/C_class_split.py` / `C_acq_forces.py` (the class-split *method*); `logs/r10/A_RESULTS.md`
(the catch mechanics); `logs/r11/B_RESULTS.md` (the close-load record); `docs/papers/MECHANISMS.md`
(the menu, rows 1/3/10); `logs/p7b/WORKLOG_entry.md` (the force-reentry measurement).

Tooling (this directory, all read-only re-derivations): `parse_logs.py` (row taxonomy),
`census.py` (per-attempt pairing), `classify.py` (the mechanism classification),
`aggregate.py` (the class shares), `md_table.py` (the markdown tables), `dump_rows.py`
(the row dumps; `seed11_A_rows.txt`). Raw outputs: `NG_all.txt`, `classify_out.txt`,
`aggregate_out.txt`, `md_table.txt`.

**The class under study.** A two-line attempt is a **no-grasp** when the primitive's own lift
check fails: `result.grasped = peak_lift > 0.05` (`tasks.py:9028`, the peak-hold over the
take-off + first carry) and the result carries `notes=['fruit did not follow the gripper']`
(`tasks.py:9079`). It is the second of the two failure classes on this line (the other is
`grasped=True placed=False`, "carried-not-placed"). On the hard seed it is the largest single
class: **10/20 attempts at seed 11 (A)**, 8/20 (B gated), 5/20 (B ungated), against 1/20 at
seeds 5 and 23.

---

## 1. The class census (task 1)

### 1.1 Per run (all listed logs; the `[run]` summary rows + the `[biarm] result` rows)

| run | arm | seed | ok | carried-not-placed | no-grasp | no-grasp span s | no-grasp share of the failure mass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `p10c/10_armA_diag` | A (knob off) | 5 | 12 | 7 | **1** | 11.2 | 9.6 % |
| `p10c/20_armB_1` | B (monitor) | 5 | 13 | 3 | **4** | 43.6 | 52.8 % |
| `p10c/22_armB_diag` | B + diag | 5 | 13 | 3 | 4 | 43.6 | (bit-identical to `20` modulo the diag rows) |
| `p10c/50_seed11_A` | A | 11 | 9 | 1 | **10** | 131.9 | 88.5 % |
| `p10c/51_seed11_B` | B | 11 | 7 | 8 | **5** | 59.2 | 40.7 % |
| `p10c/52_seed23_A` | A | 23 | 17 | 2 | **1** | 14.7 | 34.3 % |
| `p10c/53_seed23_B` | B | 23 | 16 | 3 | **1** | 14.7 | 31.1 % |
| `p10c2/61_seed5_B_gate` | B + gate | 5 | 13 | 3 | 4 | 43.6 | (bit-identical to `20`; the gate inert at seed 5) |
| `p10c2/62_seed11_B_gate` | B + gate | 11 | 10 | 2 | **8** | 93.4 | 78.6 % |
| `p10c2/63_seed23_B_gate` | B + gate | 23 | 16 | 3 | 1 | 14.7 | (bit-identical to `53`) |
| `p10c3/70..72` (flip) | = `61`/`62`/`63` | 5/11/23 | — | — | — | — | the flip reproduces them bit-identically (C.3 §1) |

The share is `no-grasp span / (carried span + no-grasp span)` in attempt-seconds (the failed
attempts only; `[cycle] total` sums per attempt). **The class is seed-dominated**: 10/20 at
seed 11 A vs 1/20 at seeds 5 and 23 A. The branch re-draws it (A 10 -> B 5 -> B-gated 8 at
seed 11), which is the P9-A "one configuration is one sample" caveat, not a lever effect: the
monitor/gate only truncates doomed *carry* legs; the no-grasp leg is decided before the carry.

### 1.2 Aggregate

* All 10 listed runs (with the bit-identical duplicates counted): 126 ok / 35 carried / **39 no-grasp**.
  No-grasp = **52.7 % of the failure count** and **51.4 % of the failure mass** (471 of 915
  attempt-seconds).
* The 7 distinct runs (`10/20/50/51/52/53/62`; `61 = 20`, `63 = 53`, `70-72 = 61/62/63`,
  `22 = 20`): 84 ok / 26 carried / **30 no-grasp**; **53.6 % of the count**, **52.5 % of the
  mass** (369 of 703 attempt-seconds).
* **Side / grade**: left 20 / right 10 (unique). The left arm takes grade A only and the right
  grade B only (W3 pure routing), so this is also A 20 / B 10 — the class is left/A-leaning
  (2:1) but present on both arms.
* **Species (unique 30)**: tomato 8, apple 6, orange 5, peach 5, kiwi 2, lychee 2, pear 1,
  strawberry 1. The mid-size round fruits (tomato/apple/orange/peach = 24/30) dominate; the
  small fruits (kiwi/lychee/strawberry = 5) and the elongated pear (1) are rarer. This is a
  *population* statement (the A/B mix feeds those species), not a per-fruit probability.

### 1.3 Per-attempt census (the `[biarm] result` + `[carry]` + `[motion] carry` + `[task]`
close/catch-up + `[cycle]` rows; see `md_table.txt` for the same table; the `70..72` rows duplicate `61/62/63` bit-identically)

Column notes: `leg ticks`/`slip_max` are the `[motion] carry grasp_lift` leg values — **the
legacy `slip_max` is frame-contaminated** (W8-B §1: up to 104.7 mm of ghost slip on placed
carries) and is quoted only as the legacy number; the honest metric is the `[carry]` line's
`clean_slip_max` (`csl`) and `in-hand vmax`. `F@o`/`sep@o`/`c@o`/`minC`/`Fmin`/`loss`/`gap0`
are the W8-B live-row fields at the carry-start onset (`loss`/`gap0` = contact-loss row and the
commanded gap at the leg start). `grip_s` = the `[cycle]` grip-phase seconds (the probe +
belt-break proxy: 1.7-2.0 s = the probe passed, 3.1-3.3 s = one failed probe, 5.2-5.5 s = the
regrasp loop exhausted). `lowest mm` = the payload's lowest point vs the belt (a fall to the
floor reads ≈ −1350, a fruit left at belt level −1..−4).

| run | att | fruit | span s | leg ticks | slip_max mm (legacy) | clean_slip mm | in-hand vmax | close t/F/span/freeze | catch-up mm | grip_s | F@o | sep@o | c@o | minC | Fmin | loss | gap0 | lowest mm | fate | class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10_armA_diag | a14 L | lychee A | 11.2 | 177 | 316.6 | 352.3 | 0.345 | 20/4.18/42.7/32.3 | 6.0 | 3.15 | 0.00 | 15.0 | 0 | 0 | 0.00 | 2 | 28.2 | -216 | fell | B1_probe_cycle |
| 20_armB_1 | a04 L | tomato A | 9.1 | 166 | 297.6 | 306.6 | 0.339 | 21/4.47/68.4/63.5 | 5.8 | 1.95 | 0.00 | 59.7 | 0 | 0 | 0.00 | 2 | 60.1 | -2 | stayed | B2_belt_break |
| 20_armB_1 | a11 L | tomato A | 8.9 | 163 | 263.4 | 253.2 | 0.308 | 19/4.31/73.8/68.9 | 5.8 | 1.75 | 0.00 | 62.9 | 0 | 0 | 0.00 | 2 | 63.3 | -1 | stayed | B2_belt_break |
| 20_armB_1 | a12 R | pear B | 12.1 | 161 | 100414.0 | 100751.2 | 12021.991 | 17/4.26/79.3/72.6 | 5.2 | 3.28 | 3.24 | 98.3 | 1 | 0 | 0.00 | 65 | 64.7 | -51609 | blowup | C_carry_leg_escape |
| 20_armB_1 | a18 R | strawberry B | 13.5 | 201 | 30818.0 | 30900.8 | 26.439 | 24/4.07/40.9/38.0 | 6.0 | 5.45 | 0.00 | 10.0 | 0 | 0 | 0.00 | 1 | 14.7 | -35813 | blowup | B1_probe_cycle |
| 50_seed11_A | a01 L | orange A | 13.6 | 216 | 1449.0 | 1396.5 | 4.790 | 20/4.30/73.7/69.9 | 5.9 | 5.45 | 11.73 | 9.9 | 1 | 0 | 0.00 | 57 | 69.9 | -1353 | fell | B1_probe_cycle |
| 50_seed11_A | a02 L | peach A | 8.9 | 162 | 240.9 | 232.2 | 0.285 | 31/4.37/69.2/58.4 | 5.9 | 1.79 | 0.00 | 56.4 | 0 | 0 | 0.00 | 2 | 58.4 | -2 | stayed | B2_belt_break |
| 50_seed11_A | a04 L | tomato A | 9.2 | 164 | 282.4 | 286.6 | 0.850 | 23/4.58/74.4/64.3 | 6.0 | 1.72 | 4.65 | 73.4 | 1 | 0 | 0.00 | 32 | 61.6 | -3 | stayed | C_carry_leg_escape |
| 50_seed11_A | a06 L | apple A | 13.6 | 217 | 1662.0 | 1793.2 | 4.806 | 17/4.63/80.2/74.0 | 5.8 | 5.45 | 29.33 | 9.6 | 1 | 0 | 0.00 | 56 | 71.4 | -1354 | fell | B1_probe_cycle |
| 50_seed11_A | a07 R | peach B | 14.5 | 174 | 200.4 | 1491.0 | 0.302 | 20/4.45/77.9/68.5 | 6.0 | 5.45 | 0.00 | 40.7 | 0 | 0 | 0.00 | 1 | 55.7 | -1352 | fell | B1_probe_cycle |
| 50_seed11_A | a10 L | orange A | 13.2 | 214 | 80968.7 | 81395.0 | 9356.214 | 16/3.74/80.2/73.9 | 6.0 | 5.45 | 38.65 | 98.4 | 1 | 0 | 0.00 | 49 | 69.9 | -54509 | blowup | B1_probe_cycle |
| 50_seed11_A | a11 R | tomato B | 14.4 | 179 | 48.4 | 496.2 | 0.172 | 20/3.96/64.9/59.3 | 6.0 | 5.45 | 0.00 | 25.4 | 0 | 0 | 0.00 | 1 | 40.4 | -1353 | fell | B1_probe_cycle |
| 50_seed11_A | a12 L | tomato A | 12.8 | 217 | 1484.3 | 1418.5 | 4.835 | 19/3.47/74.8/65.9 | 5.9 | 5.45 | 7.53 | 10.2 | 1 | 0 | 0.00 | 58 | 64.6 | -1354 | fell | B1_probe_cycle |
| 50_seed11_A | a13 L | apple A | 13.6 | 211 | 1450.6 | 1851.3 | 4.890 | 17/4.59/80.4/74.0 | 5.8 | 5.45 | 0.00 | 69.2 | 0 | 0 | 0.00 | 1 | 68.6 | -1358 | fell | B1_probe_cycle |
| 50_seed11_A | a14 R | lychee B | 18.1 | 312 | 382.9 | 1068.4 | 1.163 | - | 517.4 | 5.45 | 0.00 | 10.0 | 0 | 0 | 0.00 | 1 | 16.0 | -1352 | fell | A_pre_close_miss |
| 51_seed11_B | a01 L | orange A | 13.4 | 216 | 1462.0 | 1371.4 | 4.868 | 20/4.30/73.7/69.9 | 5.9 | 5.45 | 11.73 | 9.9 | 1 | 0 | 0.00 | 57 | 71.5 | -1365 | fell | B1_probe_cycle |
| 51_seed11_B | a06 L | peach A | 8.6 | 158 | 267.2 | 311.0 | 0.329 | 24/4.47/71.1/62.9 | 5.8 | 1.75 | 0.00 | 51.4 | 0 | 0 | 0.00 | 2 | 59.4 | -4 | stayed | B2_belt_break |
| 51_seed11_B | a10 L | apple A | 13.6 | 214 | 1484.8 | 1646.1 | 4.937 | 17/4.12/80.3/74.0 | 5.8 | 5.45 | 40.45 | 75.0 | 1 | 0 | 0.00 | 40 | 71.4 | -1378 | fell | B1_probe_cycle |
| 51_seed11_B | a12 L | apple A | 14.0 | 214 | 1445.6 | 1612.2 | 5.008 | 17/4.68/80.2/74.0 | 5.8 | 5.45 | 46.78 | 98.3 | 1 | 0 | 0.00 | 49 | 71.4 | -1368 | fell | B1_probe_cycle |
| 51_seed11_B | a15 R | tomato B | 9.6 | 174 | 199.5 | 318.9 | 0.416 | 20/4.06/65.0/59.3 | 6.0 | 1.95 | 2.45 | 98.7 | 1 | 0 | 0.00 | 52 | 52.6 | -1352 | fell | C_carry_leg_escape |
| 52_seed23_A | a05 R | kiwi B | 14.7 | 449 | 563.2 | 556.9 | 0.857 | 36/4.16/71.7/60.5 | 5.9 | 5.20 | 0.00 | 30.5 | 0 | 0 | 0.00 | 3 | 45.5 | -384 | fell | B1_probe_cycle |
| 53_seed23_B | a05 R | kiwi B | 14.7 | 449 | 563.2 | 556.9 | 0.857 | 36/4.16/71.7/60.5 | 5.9 | 5.20 | 0.00 | 30.5 | 0 | 0 | 0.00 | 3 | 45.5 | -384 | fell | B1_probe_cycle |
| 61_seed5_B_gate | a04 L | tomato A | 9.1 | 166 | 297.6 | 306.6 | 0.339 | 21/4.47/68.4/63.5 | 5.8 | 1.95 | 0.00 | 59.7 | 0 | 0 | 0.00 | 2 | 60.1 | -2 | stayed | B2_belt_break |
| 61_seed5_B_gate | a11 L | tomato A | 8.9 | 163 | 263.4 | 253.2 | 0.308 | 19/4.31/73.8/68.9 | 5.8 | 1.75 | 0.00 | 62.9 | 0 | 0 | 0.00 | 2 | 63.3 | -1 | stayed | B2_belt_break |
| 61_seed5_B_gate | a12 R | pear B | 12.1 | 161 | 100414.0 | 100751.2 | 12021.991 | 17/4.26/79.3/72.6 | 5.2 | 3.28 | 3.24 | 98.3 | 1 | 0 | 0.00 | 65 | 64.7 | -51609 | blowup | C_carry_leg_escape |
| 61_seed5_B_gate | a18 R | strawberry B | 13.5 | 201 | 30818.0 | 30900.8 | 26.439 | 24/4.07/40.9/38.0 | 6.0 | 5.45 | 0.00 | 10.0 | 0 | 0 | 0.00 | 1 | 14.7 | -35813 | blowup | B1_probe_cycle |
| 62_seed11_B_gate | a01 L | orange A | 13.4 | 216 | 1449.0 | 1396.5 | 4.790 | 20/4.30/73.7/69.9 | 5.9 | 5.45 | 11.73 | 9.9 | 1 | 0 | 0.00 | 57 | 69.9 | -1353 | fell | B1_probe_cycle |
| 62_seed11_B_gate | a02 L | peach A | 9.0 | 162 | 264.9 | 290.0 | 0.323 | 31/4.37/69.2/58.4 | 5.9 | 1.77 | 0.00 | 56.4 | 0 | 0 | 0.00 | 2 | 58.4 | -2 | stayed | B2_belt_break |
| 62_seed11_B_gate | a05 L | orange A | 13.4 | 214 | 1423.7 | 1631.8 | 4.784 | 20/4.32/73.6/69.9 | 5.8 | 5.45 | 55.60 | 77.9 | 1 | 0 | 0.00 | 52 | 69.9 | -1326 | fell | B1_probe_cycle |
| 62_seed11_B_gate | a06 L | peach A | 8.0 | 163 | 259.7 | 263.7 | 0.600 | 31/4.37/69.4/58.4 | 5.9 | 1.73 | 4.38 | 70.0 | 1 | 0 | 0.00 | 51 | 58.4 | -3 | stayed | C_carry_leg_escape |
| 62_seed11_B_gate | a10 L | apple A | 12.2 | 217 | 1440.2 | 1330.1 | 4.940 | 17/4.70/80.2/74.0 | 5.8 | 5.45 | 7.52 | 10.0 | 1 | 0 | 0.00 | 57 | 71.4 | -1357 | fell | B1_probe_cycle |
| 62_seed11_B_gate | a11 R | tomato B | 13.5 | 188 | 1293.1 | 1255.4 | 4.787 | 20/3.98/64.9/59.3 | 6.0 | 5.27 | 2.18 | 66.3 | 1 | 0 | 0.00 | 91 | 56.6 | -1382 | fell | C_carry_leg_escape |
| 62_seed11_B_gate | a17 R | tomato B | 10.1 | 181 | 18798.2 | 34752.0 | 19.784 | 20/3.97/65.0/59.3 | 6.0 | 1.95 | 0.00 | 86.7 | 0 | 0 | 0.00 | 1 | 55.0 | -71226 | blowup | B2_belt_break |
| 62_seed11_B_gate | a18 L | apple A | 13.8 | 208 | 1447.7 | 1862.2 | 5.052 | 17/4.31/80.2/74.0 | 5.8 | 5.45 | 0.00 | 67.2 | 0 | 0 | 0.00 | 1 | 67.0 | -1372 | fell | B1_probe_cycle |
| 63_seed23_B_gate | a05 R | kiwi B | 14.7 | 449 | 563.2 | 556.9 | 0.857 | 36/4.16/71.7/60.5 | 5.9 | 5.20 | 0.00 | 30.5 | 0 | 0 | 0.00 | 3 | 45.5 | -384 | fell | B1_probe_cycle |
| 70_flip_seed5 | a04 L | tomato A | 9.1 | 166 | 297.6 | 306.6 | 0.339 | 21/4.47/68.4/63.5 | 5.8 | 1.95 | 0.00 | 59.7 | 0 | 0 | 0.00 | 2 | 60.1 | -2 | stayed | B2_belt_break |
| 70_flip_seed5 | a11 L | tomato A | 8.9 | 163 | 263.4 | 253.2 | 0.308 | 19/4.31/73.8/68.9 | 5.8 | 1.75 | 0.00 | 62.9 | 0 | 0 | 0.00 | 2 | 63.3 | -1 | stayed | B2_belt_break |
| 70_flip_seed5 | a12 R | pear B | 12.1 | 161 | 100414.0 | 100751.2 | 12021.991 | 17/4.26/79.3/72.6 | 5.2 | 3.28 | 3.24 | 98.3 | 1 | 0 | 0.00 | 65 | 64.7 | -51609 | blowup | C_carry_leg_escape |
| 70_flip_seed5 | a18 R | strawberry B | 13.5 | 201 | 30818.0 | 30900.8 | 26.439 | 24/4.07/40.9/38.0 | 6.0 | 5.45 | 0.00 | 10.0 | 0 | 0 | 0.00 | 1 | 14.7 | -35813 | blowup | B1_probe_cycle |
| 71_flip_seed11 | a01 L | orange A | 13.4 | 216 | 1449.0 | 1396.5 | 4.790 | 20/4.30/73.7/69.9 | 5.9 | 5.45 | 11.73 | 9.9 | 1 | 0 | 0.00 | 57 | 69.9 | -1353 | fell | B1_probe_cycle |
| 71_flip_seed11 | a02 L | peach A | 9.0 | 162 | 264.9 | 290.0 | 0.323 | 31/4.37/69.2/58.4 | 5.9 | 1.77 | 0.00 | 56.4 | 0 | 0 | 0.00 | 2 | 58.4 | -2 | stayed | B2_belt_break |
| 71_flip_seed11 | a05 L | orange A | 13.4 | 214 | 1423.7 | 1631.8 | 4.784 | 20/4.32/73.6/69.9 | 5.8 | 5.45 | 55.60 | 77.9 | 1 | 0 | 0.00 | 52 | 69.9 | -1326 | fell | B1_probe_cycle |
| 71_flip_seed11 | a06 L | peach A | 8.0 | 163 | 259.7 | 263.7 | 0.600 | 31/4.37/69.4/58.4 | 5.9 | 1.73 | 4.38 | 70.0 | 1 | 0 | 0.00 | 51 | 58.4 | -3 | stayed | C_carry_leg_escape |
| 71_flip_seed11 | a10 L | apple A | 12.2 | 217 | 1440.2 | 1330.1 | 4.940 | 17/4.70/80.2/74.0 | 5.8 | 5.45 | 7.52 | 10.0 | 1 | 0 | 0.00 | 57 | 71.4 | -1357 | fell | B1_probe_cycle |
| 71_flip_seed11 | a11 R | tomato B | 13.5 | 188 | 1293.1 | 1255.4 | 4.787 | 20/3.98/64.9/59.3 | 6.0 | 5.27 | 2.18 | 66.3 | 1 | 0 | 0.00 | 91 | 56.6 | -1382 | fell | C_carry_leg_escape |
| 71_flip_seed11 | a17 R | tomato B | 10.1 | 181 | 18798.2 | 34752.0 | 19.784 | 20/3.97/65.0/59.3 | 6.0 | 1.95 | 0.00 | 86.7 | 0 | 0 | 0.00 | 1 | 55.0 | -71226 | blowup | B2_belt_break |
| 71_flip_seed11 | a18 L | apple A | 13.8 | 208 | 1447.7 | 1862.2 | 5.052 | 17/4.31/80.2/74.0 | 5.8 | 5.45 | 0.00 | 67.2 | 0 | 0 | 0.00 | 1 | 67.0 | -1372 | fell | B1_probe_cycle |
| 72_flip_seed23 | a05 R | kiwi B | 14.7 | 449 | 563.2 | 556.9 | 0.857 | 36/4.16/71.7/60.5 | 5.9 | 5.20 | 0.00 | 30.5 | 0 | 0 | 0.00 | 3 | 45.5 | -384 | fell | B1_probe_cycle |

The `[task] force servo:` row of each attempt (the attempt's own side entry; read at the
attempt boundary, so the gap/sep fields are post-release — the diagnostic fields are
`F[min,max]`, `closed`/`opened`, `trips`; the per-attempt rows are exact, `-` = no row emitted
for that attempt):

| att | force-servo entry | reading |
| --- | --- | --- |
| 20 a04 (tomato) | `left: F[0.00,4.57] closed=15.00 opened=0.00 trips=38` | chase |
| 20 a11 (tomato) | `left: F[0.00,13.12] closed=15.00 trips=38` | chase |
| 20 a12 (pear) | `right: F[0.00,176.81] gap=67.7 sep=98.5 closed=9.20 opened=12.20 trips=54` | chase + 4 backoffs (tip-wedge) |
| 20 a18 (strawberry) | `right: ref=0.00 F[0.00,0.00] gap=-0.3 sep=10.0 closed=15.00 trips=38` | chase to the clamp |
| 50 a01 / 62 a01 (orange) | `left: F[0.00,123.98] gap=54.9 closed=18.00 opened=3.00 trips=54` | chase + backoff |
| 51 a01 (orange) | `left: F[0.00,123.98] gap=56.5 closed=18.00 opened=3.00 trips=54` | chase + backoff |
| 50 a02 (peach) | `left: F[0.00,11.83] closed=15.00 trips=38` | chase |
| 51 a06 (peach) | `left: F[0.00,7.03] closed=15.00 trips=38` | chase |
| 62 a02 (peach) | `left: F[0.00,10.46] closed=15.00 trips=38` | chase |
| 50 a04 (tomato) | `left: F[0.00,7.74] closed=15.00 trips=38` | chase |
| 50 a06 (apple) | `left: F[0.00,108.67] closed=19.20 opened=4.20 trips=60` | chase + backoff |
| 50 a10 (orange) | `left: F[0.00,106.93] closed=18.00 opened=3.00 trips=54` | chase + backoff |
| 50 a11 (tomato) | `right: ref=0.00 F[0.00,0.00] gap=25.4 closed=15.00 trips=38` | pure chase |
| 50 a14 (lychee, class A) | `right: F[0.00,0.00] gap=1.0 sep=10.0 closed=15.00 trips=38` | chase to the clamp |
| 51 a10 (apple) | `left: F[0.00,115.36] gap=56.4 closed=18.00 opened=3.00 trips=54` | chase + backoff |
| 52/53/63 a05 (kiwi) | `right: F[0.00,0.00] gap=30.5 closed=15.00 trips=38` | pure chase |
| 62 a10 (apple) | `left: F[0.00,0.00] gap=41.4 closed=15.00 trips=38` | pure chase |
| 62 a11 (tomato) | `right: F[0.00,176.48] gap=42.4 sep=65.2 closed=18.00 opened=3.80 trips=56` | chase + backoff |
| 62 a17 (tomato) | `right: ref=3.71 F[0.00,186.69] gap=58.4 sep=98.3 closed=18.60 opened=21.60 trips=102` | chase + 7 backoffs (tip-wedge) |
| 62 a18 (apple) | `left: F[0.00,110.28] gap=52.0 closed=26.00 opened=11.00 trips=94` | chase across resets |
| 10 a14, 50 a07, 50 a12, 50 a13, 51 a12, 51 a15, 62 a05, 62 a06 | `-` (no row emitted) | — |

**The force servo reads `F_min = 0.00 N` and closes its range on every no-grasp attempt that
prints a row** — the R11-A.1 "chase" subtype. Its role in the mechanism is analyzed in §2.4
(it is causal in the B1 chain and a symptom in B2/C).

---

## 2. The mechanism per attempt (task 2)

### 2.1 What does NOT separate the class (measured, from the same rows)

The no-grasp attempts are **not** acquisition or timing misses. On `50_seed11_A`
(the hard seed), the no-grasp vs ok populations overlap completely:

| row | no-grasp | ok |
| --- | --- | --- |
| catch-up residual | 5.8–6.0 mm (9/10; a14 517.4) | 5.4–6.0 mm |
| coherent `fingertip-to-fruit` | 59.2–69.6 mm | 58.2–61.1 mm |
| `moving pick` jump | 151–241 mm | 189–212 mm |
| descent wait | 0 and 66–84 ticks (9/10) | 50–83 ticks |
| close freeze force | 3.47–4.63 N (9/10) | 1.16–6.35 N |
| close freeze tick | 16–31 | 7–24 |
| freeze span − fruit extent | +5.4…+12.2 mm | +5.8…+64.3 mm (a05 lychee +64.3) |
| grip width `G` vs extent `D` (0.98×) | −0.2…+3.3 mm interference | +0.7…+2.5 mm |

The same holds on `20_armB_1` and `62_seed11_B_gate` (see `classify_out.txt`). The one
exception is `50_seed11_A` a14 (`cu = 517.4 mm` — the class-A acquisition miss, below).
**So the class is decided after the close, not at the catch.**

### 2.2 The four sub-mechanisms (per-attempt classification)

Rules (implemented in `classify.py`; every fingerprint is read from the paired rows):

* **A — pre-close acquisition miss**: catch-up residual > 20 mm, or no close row at all.
* **B — post-close, pre-carry loss**: the close found contact (F ≈ 4 N), but the fruit was
  not in the pads at the carry-start onset. Split by the probe outcome (`[cycle]` grip phase):
  * **B1 — probe/regrasp cycle**: grip phase ≥ 3.0 s (the probe failed ≥ 1×, the regrasp loop ran);
  * **B2 — belt-break**: grip phase ≤ 2.1 s (the probe passed, the fruit lost in the
    belt-break/settle).
* **C — carry-leg escape**: a pinch-scale contact at the carry start (`0 < F@o ≤ 6 N`,
  `c@o ≥ 1`) and `loss_row > 10` (held into the carry, lost there).

Unique-attempt split (30 attempts, 7 distinct runs; the duplicates of §1.1 excluded):

| class | n | share | span (attempt-s) | share of the class mass |
| --- | --- | --- | --- | --- |
| A pre-close miss | 1 | 3.3 % | 18.1 | 4.9 % |
| **B1 probe/regrasp cycle** | **18** | **60.0 %** | 243.6 | **66.1 %** |
| B2 belt-break | 6 | 20.0 % | 54.6 | 14.8 % |
| C carry-leg escape | 5 | 16.7 % | 52.4 | 14.2 % |

**The dominant sub-mechanism is B1: the fruit is lost in the probe/regrasp cycle, before the
carry.** It is also the sub-mechanism that produces the falls: of B1's 18 attempts, **13 end
with the payload ≈ 1.3 m below the belt (a fall to the floor; in-hand |v|max 4.78–5.05 m/s,
which is free fall from the belt top 1.17 m, √(2·9.81·1.17) = 4.79 m/s)**, 3 more end below
the belt (−216 and −384 mm ×2 — a short drop/roll-off, |v|max 0.35/0.86), 2 are physics
blowups, and none stays at belt level. In B2 the opposite: 5/6 stay at belt level
(−1…−4 mm), 1 blows up.

### 2.3 The canonical reconstructions (raw rows)

**(a) B1, `50_seed11_A` a01 (left orange, `logs/p10c/50_seed11_A.log`).** Close: `dynamic
close: sustained contact after 20 ticks (force=4.30 N, span=73.7 mm); freezing at 69.9 mm`
(line 430) → grip `6.69cm around a 6.83cm fruit` (435). Then **three regrasps**:
`re-seated in place (gap 51.9 mm kept)` (436), `(gap 69.9)` (441), `(gap 69.9)` (450) — i.e.
the probe failed 3× (the cycle grip phase 5.45 s). The first keep-gap 51.9 mm is **16.4 mm
narrower than the fruit** (the grip row's 6.83 cm extent): the force servo had chased the force collapse to its range floor
(anchor 66.9 − `FRUIT_DYNAMIC_FORCE_RANGE` 15 mm = 51.9). The carry then starts with the pads
clamped on each other: `[carry] left grasp_lift: onset_row=1 force@onset=11.73N sep@onset=9.9mm
contacts@onset=1 min_contacts=0 force_min=0.00N loss_row=57` (460), `lift +0.0016 m,
grasped=False` (463), `clearance: lowest payload point −1353 mm` (462) — the orange fell to
the floor (in-hand |v|max 4.79).

**(b) B2, `50_seed11_A` a02 (left peach).** Close: `31 ticks (force=4.37 N, span=69.2 mm);
freezing at 58.4 mm` (498) → grip `5.84cm around a 6.17cm fruit` (506). **No regrasp row** —
the probe passed (the fruit rose ≥ 4 mm under the 6 mm test lift). Carry start: `onset_row=2
force@onset=0.00N sep@onset=56.4mm contacts@onset=0 min_contacts=0 loss_row=2` (515), the pads
at the commanded gap with no contact; `lowest payload point −2 mm` — the peach stayed on the
belt while the hand lifted away. The force servo's `closed=15.00 trips=38` here happens
*after* the loss (the carry chase) — a symptom.

**(c) C, `50_seed11_A` a04 (left tomato).** Close `23 ticks (force=4.58 N, span=74.4 mm);
freezing at 64.3 mm` (572); no regrasp (probe passed). Carry: `onset_row=4 force@onset=4.65N
sep@onset=73.4mm contacts@onset=1 ... loss_row=32` (590) — the tomato was in a light contact
(4.65 N) through the first 32 of 164 ticks (0.27 s) of the lift, then lost; `lowest payload
point −3 mm` (it dropped back onto the belt). This is the only sub-class where the loss
completes inside the carry leg; its fingerprint (a weak 2–5 N contact at a span ~8–10 mm wider
than the fruit) is a *tip/marginal* contact, not a centred pinch.

**(d) A, `50_seed11_A` a14 (right lychee).** `dynamic descent: waited 0 ticks, intercept=
−0.1300 m (station −0.1000, shift −0.0300 m), fruit dy=−0.2541 m` (999) — the fruit was
**254 mm downstream of the station when the descent started** (a late fallback aim), the
catch-up then ends `residual=517.4 mm` (1010), the close never finds contact (**no close row** —
the only one in 20 attempts), the pads close on air, the 3 probes fail, the regrasps re-seat at
16.0 mm (17.5 mm narrower than the 33.5 mm lychee), and the carry runs with the fruit gone
(the lychee leaves the line: its lowest point −1352 mm below the output belt, |v|max 1.16 —
a roll-off down the line end, not the free-fall signature of the B1 drops).
This is the R10-A "descent/fallback chase" class, not the post-close class.

### 2.4 The B1 chain (the dominant mechanism), with the actuator evidence

1. **The close takes a marginal grip.** All B1 attempts have a real close (F 3.47–4.87 N) —
   but the freeze fires at the *first sustained contact* (force + span stall), and the span at
   detection is +3.7…+35.1 mm wider than the fruit: a **tip/edge contact**, not a centred pinch. The
   logs cannot expose the pad–fruit geometry that makes it marginal (the `FRUIT_ACQ_DIAG`
   per-tick rows are off in these runs); the W8-B corpus records the same class on the direct
   interface as the "marginal zone" (the 0.4–6.3 mm clean_slip band, P10-C.1 §"paired-leg
   ground truth").
2. **The 6 mm probe fails** (the fruit does not rise ≥ 4 mm) → the primitive runs the
   W1 two-line regrasp profile. Evidence: the cycle grip phase 5.2–5.45 s and the `dynamic
   regrasp: re-seated in place` rows, 1–3 per attempt.
3. **The force servo has already chased the collapse.** When the payload starts leaving, the
   tactile force collapses to 0 and the servo's integral law closes at `0.4 mm / 3 ticks` up to
   `FRUIT_DYNAMIC_FORCE_RANGE = 15 mm` (each regrasp re-anchors and re-arms another 15 mm).
   Evidence: every no-grasp attempt's servo row reads `F_min = 0.00 N` and `closed` 15.0–26.0 mm;
   the regrasp keep-gaps are the chased values (51.9 = 66.9 − 15; 16.0 = 31.0 − 15).
4. **The re-seat drives the pads back onto the fruit at the chased (sub-fruit) gap.** The
   `regrasp_keep=1` profile (two-line) descends the pads onto the fruit's measured centre *at
   keep_gap*. **In 15 of the 18 B1 attempts the first keep-gap is 1.7–17.5 mm narrower than
   the fruit extent** (measured, unambiguous per attempt: 51.9 vs 68.3 = −16.4; 61.8 vs 68.2 =
   −6.4; 64.7 vs 66.4 = −1.7; 53.4 vs 68.2 = −14.8; 16.0 vs 33.5 = −17.5; 32.7 vs 37.2 =
   −4.5; 49.7 vs 68.1 = −18.4; 41.8 vs 57.0 = −15.2; 53.8 vs 68.7 = −14.9; the concurrent
   pair 50_a11/a12 shares the first row 53.8 (narrower than both fruits under either split);
   and the three exceptions 32.0 vs 29.6 = +2.4 and 45.5 vs 36.6 = +8.9 ×2) — the pads are commanded
   *inside* the fruit while descending onto it, with the drives' full squeeze; the fruit is
   ejected (it falls off the belt in 13/18 to the floor, 3 more below it). The squeeze ratchet
   (`fingers -= FRUIT_DYNAMIC_REGRASP_STEP` 1.5 mm per cycle) adds to the interference.
   The later regrasps often recover (the servo backs off when the pad–pad clamp force exceeds
   `FRUIT_DYNAMIC_FORCE_MAX = 12 N`), but by then the fruit is gone.
5. **The carry runs with the fruit gone** — the pads clamp on each other (`sep@onset ≈ 10 mm`,
   `force@onset` 7–56 N) or sit on air at the commanded gap; `grasped=False`.

**Honest confidence per attempt**: the *class* (B1/B2/C/A) is a row-fingerprint statement and
is high-confidence (the probe outcome is unambiguous via the regrasp rows + the cycle grip
phase; the carry-start state is the W8-B live row). The *chain* (steps 3–4 as the ejector) is
medium-confidence: it is supported by the keep-gap arithmetic and the fall kinematics, but the
logs do not carry per-tick pad/fruit geometry, so an alternative actuator (the probe's own
lift shearing the marginal grip, with the pads clamping shut only afterwards) cannot be
excluded from these logs alone. The named falsifier for the chain is in §3.1.

**The blowups (physics divergence, sub-tag of (c) in the mission's list).** Four attempts show
a solver divergence rather than a fall: `20_armB_1` a12 (in-hand |v|max 12022 m/s, clean_slip
100.4 m), `50_seed11_A` a10 (9356 m/s, 81.4 m), `20_armB_1` a18 (26.4 m/s, 30.9 m),
`62_seed11_B_gate` a17 (19.8 m/s, 34.8 m). All four have a real close (F 3.97–4.70 N) and a
carry-start contact or clamp; the divergence happens in the lift leg (the `[motion] carry`
row's `|j|max` 4112–847.9 m/s³). These are tracker/physics events, not a distinct control
mechanism; they are counted in their phase class (B1/B2/C) with the `blowup` tag.

### 2.5 What the logs say about the *root* of the marginal grip

Not determined by these logs. The close rows, the acquisition rows and the grip widths do not
separate the no-grasp attempts from the successes (table in §2.1); the difference is only
visible in what happens under load. The W8-B corpus (four trace corpora, 55 attempts; 33 clean + 31 escape legs) separates clean
(0.02–1.43 mm clean_slip, n = 33) from escape (17.9–957 mm, n = 31) and excludes **25 legs
that never had the payload at all** as the "reach-cliff / catch-miss class"
(`logs/w8/B_RESULTS.md` §1; `B_metric.py`'s `no-contact` rule: `|hand_rel(0)| > 0.5 m` or a
zero loaded contact through the leg). **This census revises that reading for the two-line
scripted line**: of the 30 no-grasp legs here, 29 have a real close (a sustained 3.5–4.9 N
contact) and are lost *after* the close — they are not reach-cliff misses; only 1/30 is the
acquisition class. So the never-held family is two families, and the dominant one is the
post-close load path.

---

## 3. The candidate levers + falsifiers (task 3)

Ranked by the sub-mechanism they target (B1 = 66 % of the class mass; B2/C/A = the rest).
Every lever below is an existing, default-off knob (or an existing mechanism); the falsifier
is the row pattern that would refute the mechanism claim, and the expected movement is the
change in the census counts. All measurements must be two-line-scoped (the shipped single-arm
line is byte-identical and must stay so) and pre-registered with the patch battery at
**seed 11** (the hard seed; 8–10 no-grasp attempts per run) as the primary, seeds 5/23 as the
controls.

### 3.1 Lever 1 (top): stop the force servo from chasing into the regrasp — `FRUIT_FORCE_REENTRY=1`

*Targets*: B1 step 3–4 (the chased keep-gap). The knob (default off; `tasks.py` `_force_servo_step`,
menu row 3 "FARM Port A") enters force mode only on confident contact and **holds the commanded
gap** when the contact estimate is gone, so `squeeze_gap` stays at the recorded depth and the
regrasp re-seats at the grip depth instead of the chased one.
*Evidence it applies here*: the chase signature is universal in the class (`F_min = 0.00`,
`closed` 15–26 mm); the keep-gaps are the chased values (51.9 = 66.9 − 15 etc.).
*Falsifier (offline, on the re-run logs)*: with the knob on, the **first regrasp keep-gap of
every B1 attempt should stay ≥ (grip depth − 2 mm)**. If the keep-gaps stay ≥ the fruit extent
and the class does not move (the same attempts still `grasped=False`), the re-seat is not the
ejector and the claim is refuted — the named alternative (the probe's shear) then owns the
class.
*Expected movement*: B1's floor-fall count (13/18) should fall; in the limit the class loses up to
the B1 mass (66 % of it). *Prior*: P7-2a measured this knob on the **single-arm acceptance**
(`logs/p7b/WORKLOG_entry.md`): chase 5 → 0, but carried-not-placed 5 → 5, zero conversions —
"the chase is a symptom". That measurement's failures were the *carried* class on a different
branch; it neither confirms nor refutes the B1 role, and it is the reason this must be a
two-line-scoped measurement with its own pre-registration.

### 3.2 Lever 2: bound the regrasp cycles — `FRUIT_REGRASPS=1` (or 0)

*Targets*: B1 step 4 (the ratchet/ejection cycles) by removing the repetition.
*Falsifier*: if with `FRUIT_REGRASPS=0` the same attempts still lose the fruit at the same
phase (the first probe alone), the cycle is not the ejector and Lever 1's chain is weakened.
*Expected movement*: the ejection cycles stop, but the marginal grip then faces the belt-break
— expect the B1 mass to move toward B2/C (a *diagnostic* lever, not a fix; cheap, one line,
already default-parameterised). No-harm risk: the W1 profile's measured gain used the regrasp
loop (the two-line 6/10 → 7/10), so this lever is also a measurement of what the regrasp
buys.

### 3.3 Lever 3: gentler/deeper close — the squeeze-side family

`FRUIT_DYNAMIC_CLOSE_DEEP` (0.97 → 0.95), `FRUIT_GRIPPER_SQUEEZE` (0.98 → 0.96),
`FRUIT_MIN_INTERFERENCE` (0 → 1–2 mm). *Targets*: the marginal grip itself (§2.5) by adding
interference at the close.
*Falsifier*: the clean legs' `clean_slip_max` must stay ≤ 1.43 mm (the W8-B clean range) and
the clean legs' force must stay ≤ 4.9 N; if the no-grasp count does not move with +1–2 mm of
interference, the marginal grip is a *geometry* (tip-contact) problem, not a depth problem —
which the R6-B/W8-B "squeeze-side family closed by measurement" reading predicts for the
direct interface.
*Expected movement*: small; the historical record (the `FRUIT_GRIPPER_PRELOAD` /
`FRUIT_MIN_INTERFERENCE` tests on small fruit) changed nothing.

### 3.4 Lever 4: the close's load rate — R11-B C1 `FRUIT_CLOSE_LOAD_RATE=0.04`

*Targets*: the close's contact dynamics (the freeze row 18 → 55.5, the freeze-zone face speed
188.7 → 39.9 mm/s, measured in `logs/r11/B_RESULTS.md`). *Falsifier*: already partially
falsified — the stage-P scripted battery read 12/20 vs the control 13/18 with the
never-grasped class 0 → 5 (the late freeze lets the fruit ride the faces). *Expected
movement*: negative prior; only worth re-testing if a close-side lever is needed.

### 3.5 Lever 5: the take-off screens (W5-C)

`FRUIT_DYNAMIC_TAKEOFF_SQUEEZE=0`, `FRUIT_DYNAMIC_TAKEOFF_TRACK=0.2`,
`FRUIT_DYNAMIC_TAKEOFF_LOCK_X=1` (and `FRUIT_DYNAMIC_FORCE_SERVO=0`). *Targets*: the probe's
squeeze / the belt-break's x-tracking. *Falsifier*: W5-C already measured all four on the
dense two-line as **negative** (every config leaves the left class alive; the servo's removal
is inert on the replicated attempt; TRACK/LOCK_X destroy the signature's specificity). They
stay in the menu as recorded negatives; only `FORCE_SERVO=0` overlaps Lever 1 (cruder: it also
drops the squeeze maintenance on healthy grips).

### 3.6 Lever 6: the acquisition-side fix for the class-A attempt — menu #10 `FRUIT_DYNAMIC_TRACE_AIM`

*Targets*: `50_seed11_A` a14 only (the late fallback: the fruit 254 mm past the station at the
descent start, the 517 mm catch-up). *Falsifier*: the chase/fallback count on the R11-A
battery (the knob's own endpoint) + no descent over budget. *Expected movement*: 1/30 attempts;
ranked last for the class, but it is the only named lever for the acquisition sub-class.

### 3.7 Not applicable / scoped elsewhere

The P10-C monitor + confirm gate (now the shipped two-line default) truncates doomed *carry*
legs and is orthogonal to this class (it fires on some no-grasp legs — the seed-5 fire-2 was a
no-grasp pear — but changes no outcome); the W7-B `FRUIT_POLICY_TRIGGER_ACQ` and the R2 knobs
are direct/trigger-scoped (the scripted catch never runs the trigger); `FRUIT_REACH_*` is the
default-off single-arm reach branch.

---

## 4. The class ceiling (task 4)

* **The no-grasp class is 52–54 % of the total failure mass on this scenario** — 369 of 703
  failed attempt-seconds (unique runs), 471 of 915 across all listed runs. The other failure
  class (carried-not-placed) holds the rest. So the class is the single largest failure family
  on the two-line patch scenario, and its hard-seed incidence (10/20) is 5–10× the soft seeds'.
* **Within the class, B1 (the probe/regrasp cycle) is 60 % of the count and 66 % of the mass.**
  A lever that converts B1's floor-falls (13/18) has the largest ceiling: up to ≈ 2/3 of the class
  ≈ 35 % of the total failure mass on the hard seed. B2 (20 %) and C (17 %) are the residuals
  a B1 fix would likely *grow* (the marginal grip faces the belt-break instead of the probe) —
  the pre-registration should therefore name the **B1→B2/C conversion** as the falsifier of a
  partial fix, not just the pooled count.
* The class's seed dependence (10 vs 1–4 per 20) says the *population* matters: the hard seed
  draws more of the mid-size round fruits into the marginal-contact geometry. Any rate claim
  needs ≥ 3 seeds (the P9-A/P10-C.1 precedent), and the census (not the rate) is the stable
  readout across seeds.

---

## 5. Honest measurement limits

1. **No per-tick pad–fruit geometry in these logs.** `FRUIT_ACQ_DIAG` was off; the
   `FRUIT_CARRY_DIAG` `[carry]` row is a per-leg summary. The claim "a tip/edge contact, not a
   centred pinch" is inferred from the freeze span − extent (+3.7…+35.1 mm) and the W8-B marginal
   zone, not read directly. A re-run with `FRUIT_ACQ_DIAG=1` (run-neutral, W7-C evidence)
   would expose `close_start`, `contact`, `freeze`, `span` per attempt and settle §2.5.
2. **The close-row attribution has a ±1 ambiguity** when two attempts close concurrently
   (e.g. `50_seed11_A` a00/a01: closes at lines 430/433, grips 434/435). The assignment used
   here (the next unclaimed close before the attempt's grip row) satisfies the hard constraint
   `grip G ≤ close freeze` for all 20 attempts, and the swapped alternative would change
   nothing in this document (both rows are real-contact closes, F 4.30/4.75 N). The grip-row
   pairing is pinned by the servo-anchor arithmetic (`gap0 = G + opened`, verified on a00/a01).
3. **The regrasp count per attempt is a window estimate** (`(grip_line, carry_line]` can catch
   the other arm's rows when the two attempts interleave); the *reliable* probe-failure signal
   is the `[cycle]` grip-phase seconds (bimodal: ≤ 2.1 s vs ≥ 3.0 s). The keep-gap *values*
   quoted in §2.4 are matched to their attempts by the last-gap = `gap0` fingerprint, which is
   exact for the single-arm-grouped rows and verified per attempt in §2.4's list.
4. **`slip_max` in the `[motion] carry` row is not physics** (W8-B §1: frame-contaminated on
   the OpenArm hand, 25.6–104.7 mm of ghost slip on placed carries). This document uses the
   `[carry]` row's `clean_slip_max` and `in-hand |v|max`; the `slip_max` column is quoted only
   as the legacy number, and the huge values in the no-grasp rows (up to 100.4 m) are the
   frame artifact *plus* a fallen payload, not a grip measurement.
5. **The fall inference** (13 B1 attempts "fell to the floor"; 16 B1 attempts below the
   belt) rests on two independent readouts: the `clearance` row's lowest payload point
   (−1326…−1382 mm vs the output-belt top) and the in-hand |v|max 4.78–5.05 m/s = the
   free-fall speed from the belt top (4.79).
   Both are consistent; the exact impact is not observable in these logs.
6. **One sample per configuration.** Every number here is from one deterministic run per
   branch; the C.1/C.2 records show the branches are bit-identical within a config, and the
   seed/branch re-draws move the class (10 vs 5 vs 8 at seed 11). Treat the counts as branch
   censuses, not rates.
7. **The 5 cm threshold is part of the class definition.** `grasped = peak_lift > 0.05` means a
   payload pushed up 40 mm without being held counts as no-grasp; a loss at 60 mm of lift
   counts as carried-not-placed. The same physical escape can therefore appear in either class
   depending on *when* it happens — the reason §4's ceiling must name the B1→B2/C conversion.

---

## Appendix: the reproduction commands

```bash
cd logs/p10e
python3 census.py ../p10c/50_seed11_A.log          # the paired per-attempt table
python3 classify.py                                 # the mechanism classification + counts
python3 aggregate.py                                # the per-run census + class shares
python3 md_table.py                                 # the markdown census table (md_table.txt)
python3 dump_rows.py ../p10c/50_seed11_A.log        # the raw row dump (seed11_A_rows.txt)
```
