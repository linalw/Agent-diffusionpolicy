# P22-C M1/R0 results: the release+resync mechanism read (2026-10-20)

Status: **R0 PASSES; the s11 mechanism read is mixed and the s11 is the wrong seed to decide
the outcome.** The discriminating seeds (s5's -20 collapse, s23's -8) are running.

## 1. R0 (the current-tree control identity) - PASS

`logs/p21i/30_seed11_R0.log` (the current tree `62cdbb7f`) vs `logs/p21i/10_seed11_relA_1.log`
(the tree `455f1a33`) is **0 diff lines on the `[fruit]` physics stream** once the two diagnostic
row families (`[supply-diag]`, `[supply] diag`) and the `place trace` rows are excluded. The
inert default-off changes are confirmed and the on-disk controls are valid.

## 2. The M1 mechanism read (s11, `FRUIT_SUPPLY_DIAG=1`, traced)

The per-poll `late_lo` distributions (the design's primary falsifier: the resync's polls should
track the control's with no drift):

| arm | supply-diag rows | late_lo p50 | min | max |
| --- | --- | --- | --- | --- |
| A shipped | 29 | 0.600 | 0.020 | 1.660 |
| B trim | 37 | 0.470 | 0.040 | 1.430 |
| BR trim+resync | 36 | **0.365** | 0.070 | 1.750 |

**The BR does not track A** (p50 0.365 vs 0.600) - the endpoint fires as written. Caveat: the
`late` is the pump's lateness against the due grid, and all three arms are late by construction
(the pump runs only inside the 60-tick feed window), so a shift of 0.2 s is not directly the
presentation drift the design meant; the row counts also differ (29/37/36). The read is recorded
as **ambiguous**, not as a clean falsification - the outcome test below is the decider.

## 3. The s11 outcome (the null seed)

`A 11/7/2, B 11/8/1, BR 10/8/2` (the 20-attempt censuses) - consistent with the release battery's
s11 result (the trim is NULL at s11: A 22 / B 22 across the two runs); **the s11 cannot
discriminate the resync**. The discriminating seeds are s5 (A 34 -> B 14) and s23 (A 34 -> B 26):
the BR battery there is running (`logs/p21i/93_driver_p23.log`, 4 runs).

## 4. Provenance

* Runs: `logs/p21i/{30,31,32,33}_seed11_{R0,A,B,BR}.log` (chain `run_m1_gate4.sh`; driver
  `92_driver_m1.log`).
* Pins: `tasks.py` `62cdbb7f` (the R0 confirms the inert delta vs `455f1a33`).
