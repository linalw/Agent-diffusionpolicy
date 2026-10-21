# P25 results: the B1c's decisive 7-run block (2026-10-21) + the owner's bar decisions

## 1. The block (the Gate-5 2.6 design, the frozen rule)

| run | seed | arm | acceptance |
| --- | --- | --- | --- |
| a2 | 5 | A | **9/10** |
| a3 | 5 | B | 7/10 |
| a4 | 5 | P | 8/10 |
| a5 | 11 | A | 7/10 |
| a6 | 11 | B | 7/10 |
| a7 | 23 | A | **4/10** |
| a8 | 23 | B | **6/10** |

**Endpoint 1 (the design's primary mechanism endpoint, the seed-5 supply-diag triple): PASS.**
The per-poll `late_lo` distributions: A p50 **3.33 s** (n=14, 0.01-4.68), B **3.31 s** (n=14,
0.0-4.42), P 3.51 s (n=13). The re-anchor keeps the presentation stream on the control's schedule
(a 0.02 s difference, far inside one release period) with no monotone drift - **the correct
re-anchor, not a lucky branch.**

**Endpoint 4 (the acceptance, 3 seeds): the floor is not met.** B reads 7/7/6 - never >= 8/10 -
while the control itself reads **9/7/4** (the shipped line is 4/10 at SEED=23). B vs A: -2 / 0 /
+2: the lever is not worse on two of three seeds and the floor is not a stable property of the
shipped line.

## 2. The owner's bar decisions (2026-10-21)

* **The B1c: adopt by the mechanism + throughput** (the user's instruction), i.e. the timing
  endpoint is the verdict and the census is a non-inferiority guard. The implementation flips the
  defaults: `FRUIT_READY_SKIP=1`, `FRUIT_READY_SKIP_DG=0.02`, `FRUIT_READY_SKIP_RESYNC=1`
  (explicit `=0` restores the shipped transit). The stubs (`check_skip_predicate`,
  `check_resync`) are updated to the flipped defaults.
* **The belt 0.15: the shipped two-line scenario moves to 0.15 m/s** (the user's instruction).
  The implementation: `assets.py` `FRUIT_BELT_SPEED` default `0.12` -> `0.15` (the lead/floor are
  already belt-speed-aware via `_belt_speed_estimate()`); the supply selftest pins its own 0.12
  golden scenario (its job is the supply logic, not the scenario); the simulator batteries carry
  the scenario verification.

## 3. Provenance

* The block: `logs/p20i/a{2..8}_acc_*.log` (chain `run_b1c_final.sh`; driver
  `92_driver_final.log`); the supply-diag rows parsed from the a2/a3/a4 logs.
* The decisions: the user's deepwork instruction of 2026-10-21.
