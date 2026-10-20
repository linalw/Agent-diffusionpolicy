# P23 results: the no-harm acceptance, the release+resync at the discriminating seeds, the B1c guards

## 1. The standing no-harm acceptance (the shipped path) - PASS

`logs/p21i/50_accept_noharm.log`: **9/10** (151.9 s, 15.2 s/attempt), the `[fruit]` stream 385
lines (the acceptance's standing length), `scripts/105_motion_regression.py` **PASS** (every
descent inside its speed/lurch bound; the 5 carry-cone rows are the dynamic line's reported-not-
gated warnings), and the default-reference fingerprint matches (no "different attractor" line).

## 2. The release + supply-clock resync at the discriminating seeds - the resync does NOT restore the branch

| seed | control A | trim B | trim+resync BR | BR vs B |
| --- | --- | --- | --- | --- |
| 11 | 22/40 | 22/40 (null) | 10/20 (1 run) | ~neutral |
| 5 | 34/40 | **14/40** | **26/40** | **+12** (the best evidence for the resync) |
| 23 | 34/40 | 26/40 | 20/40 | **-6** |
| pooled | 90/120 | 62/120 | 56/100 | ~ -2 points (still ~ -25 % vs the control) |

The resync recovers s5 strongly and loses s23; the pooled outcome stays far below the control.
**The release family closes negative** (the trim's loss is not the nominal-credit mismatch a
re-anchor fixes; the design's own caveat - the credit is the nominal saving, not the per-attempt
actual - is the named residual). The knobs stay default-off.

## 3. The B1c's guard set (Gate-4 4.5, the single-arm line)

* **G4 (motion budgets): PASS** on the B1c's runs - the worst descents |v|max 0.1340 / 0.1420 /
  0.1130 m/s against the 0.160-0.162 budget; the lurch 0.080/0.077/0.017 against 0.291
  (`105` on `logs/p20i/{611,711,723}_sa_*.log`). The **patch fingerprint mismatch is the stale
  reference** (`configs/motion_reference_patch.json`, the W6-A-era scenario; the AGENTS' P1c note
  already flags the patch reference as needing re-recording on adoption) - not a budget failure.
* **G5 (no-harm): PASS** - the shipped path reads 9/10 + the gate PASS (section 1), i.e. the
  default-off tree is byte-clean.

**The B1c therefore stands as the first lever in the P-series to pass its battery (46/59 vs A
42/58, B >= A on every seed) and the guard set**, with its own recorded caveats: the acceptance
branch 7/10 (the design's predicted branch), the mid-battery tree change (inert), and the stale
patch fingerprint. Its adoption (a default flip on the shipped single-arm line) remains an
owner-facing decision for the gate, not an automatic consequence of the pass.

## 4. Provenance

* The acceptance: `logs/p21i/50_accept_noharm.log`; the 105 gates as quoted.
* The BR: `logs/p21i/{40,41}_seed5_BR_*.log`, `{42,43}_seed23_BR_*.log`, `33_seed11_BR.log`
  (chain `run_p23.sh`; driver `93_driver_p23.log`).
* The B1c: `logs/p20i/B1C_RESULTS.md`; the guards as quoted above.
