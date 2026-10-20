# P22-A B1c results: the feeder re-anchor on the single-arm line (2026-10-20)

Status: **the mechanism and the multi-seed outcome are positive** — the skip fires, the resync's
credit ladder holds, the gap falls 5.20 → 3.30 s, and the census is **not worse on any seed**
(46 vs 42 placed; total failures 13 vs 16). The appointment is not adoption: the acceptance gate
(7/10 under the lever) and the Gate-4 guard set (G4/G5) still have to run.

## 1. The battery (corrected)

The first multi-seed part used the two-line env and is void (the skip is single-arm-scoped:
`tasks.py` `scope = _active_session is None and not two_line_enabled()`; the runs never skipped,
`credit=0`, census == control). The corrected battery: the **single-arm patch scenario**
(`FRUIT_BIARM=0` + the W6-A patch supply), arms A/B/P x seeds 11/5/23, `FRUIT_READY_DIAG=1`
(`logs/p20i/run_b1c_singlearm.sh`).

| arm | seed 11 | seed 5 | seed 23 | pooled | gap p50 | empty polls |
| --- | --- | --- | --- | --- | --- | --- |
| A shipped | 16/20 | 13/18 | 13/20 | **42/58** | 5.20 s | 2 |
| B skip+DG+RESYNC | 17/20 | 16/19 | 13/20 | **46/59** | **3.30 s** | **1** |
| P placebo (HOLD=230) | 12/20 | 15/19 | 14/18 | 41/57 | 5.20 s | 3 |

**B >= A on every seed** (17>=16, 16>=13, 13==13), total failures A 16 / **B 13** / P 16, nc A 1 /
B 2 / P 2, carried A 15 / **B 11** / P 14.

## 2. The mechanism (what the rows show)

* **The skip fires**: 59 `[ready] skip=1` rows in B, 57 in P, 0 in A; the gap p50 5.20 → **3.30 s**
  (the -1.9 s the B1 measured).
* **The resync credits exactly**: B's `credit=` ladder reads 230, 460, 690, ..., 4600 ticks (20
  credits, 230 each, the cumulative debt zero after each) — the re-anchor is active and exact.
  **The placebo credits 0** (it holds the clock by construction) and its gap stays 5.20 s.
* **The empty-poll class shrinks** 2 → **1** (P: 3) — the B1's empty-slot mechanism is what the
  re-anchor was designed to remove.
* **The placebo isolates the effect**: P (the identical skip with the clock held) reads 41/57, no
  better than A's 42/58 — so the **+4 of B over both is the re-anchor**, not the skip's removal of
  ticks. This is the design's prediction: the wall saving needs the supply-clock credit to keep
  the branch.

## 3. The caveats and the outstanding guards

* The **acceptance reads A 9/10, B 7/10, P 8/10** (the earlier single-seed run) — the design's own
  predicted branch (7/10 < the 0.75 floor), and the design says the floor is a branch draw to be
  reported, not the verdict. It is still a gate that has not passed.
* The tree changed mid-battery when the release-resync knob landed (`455f1a33` → `62cdbb7f`, both
  default-off paths byte-inert); the runs are consistent, but a clean single-tree replication is
  the honest confirmation.
* The Gate-4 guard set (`logs/p22/ORACLE_GATE4.md` 4.5) still to run: **G4** the motion gate on
  the patch reference (`scripts/190_twoline_gate.sh -m 0.5 -r configs/motion_reference_patch.json`
  is two-line; the single-arm equivalent is the `105` patch reference) and **G5** the no-harm
  (`accept.sh` 9/10 + fingerprint; `selfcheck.sh` PASS).

## 4. Provenance

* Runs: `logs/p20i/{611,711,811,65,75,85,623,723,823}_sa_{A,B,P}.log` (chain
  `run_b1c_singlearm.sh`; driver `91_driver_sa.log`); read `read_singlearm.py`.
* Pins: `tasks.py` `455f1a33` (the first run) → `62cdbb7f` (the rest; inert deltas), `rl_env.py`
  followed; the checkpoint N/A (scripted line).
