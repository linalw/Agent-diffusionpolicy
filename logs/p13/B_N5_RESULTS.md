# P13-B.2 N=5 RESULTS (2026-10-19): the mechanism-only result - the acquisition/chase channels move strongly, the outcome +6 does not reach the pre-registered significance bar

The frozen rule: `logs/p13/run_n5.sh.readout.md` (+ the Oracle's clarifications), frozen before
the read. The battery: the W7-B boundary pins on the current tree, RUNS=5, seeds
77/101/202/303/404, policy seed 11, both arms ACQ_DIAG.

## The endpoints

| endpoint | A (moe_v13s) | **B (ev1)** | verdict |
| --- | --- | --- | --- |
| **primary: the pooled paired outcome + the exact sign test** | 43/75 (57 %) | **49/75 (65 %)**; paired 39/22/**10 B-only**/4 A-only; **p = 0.0898** (discordant 14) | **FAIL** (p > 0.05; the +6 is directional) |
| the cycle | median 1836 ticks | 1857 | +1.1 % (non-inferior) |
| the strawberry | 40 % | 70 % | non-inferior (better) |
| **the mechanism: the left close-start \|y\|** | median 5.7, **p90 266.8**, max 530.0 | median 4.2, **p90 5.5**, max 915.9 | **PASS** (the median holds, the p90 collapses; the tail persists) |
| **the mechanism: the catch-up chases** | **15** | **4** | **PASS** (-73 %) |
| the re-seat markers | 0 | 0 | (structurally unreadable on the direct interface) |
| the new reasons | - | the composite note `policy closed on the fruit (...)` + `fruit did not follow the gripper` | flagged: a composite of two KNOWN classes (the R5/WS-4.6 policy-gate path + the no-grasp); the decomposition is in the class-transition table - not a new mechanism (recorded as the strict flag) |

## The verdict (per the frozen combination rule)

**A mechanism-only result: the mechanism leg passes (the left acquisition p90 266.8 -> 5.5;
the chases 15 -> 4) and the primary fails (p = 0.0898) - so no adoption**; the +6 outcome
(65 % vs 57 %) is the directional read the N=5 was powered to test, and it sits just above
the p <= 0.05 bar's reach at this N (the N=3's 5-2 pairing pointed the same way). The named
controls (the heads+aux-only; the transition-weight+gamma-only; the knob-off 6-epoch re-run)
remain the attribution step; the policy-side no-harm (the canary) is the separate read
(`logs/p13/71_accept_policy.log` - the canary's 2/10 on the pinned supply vs the record's
8/10, with the pre-P13 control in flight, `logs/p13/72_accept_policy_pre.log`).
