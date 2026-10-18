# P11-C.3 RESULTS (2026-10-18) + the P11-C arc close-out: the control-side ejection-fix space is measured closed

Pre-registration: `logs/p11c/PREREG_C3_DEPTH_FLOOR.md` (the env-only variant: `FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1`
+ the chase range cut `FRUIT_DYNAMIC_FORCE_RANGE` 0.015 -> 0.002 m).

## The C3 battery

| seed | A (the anchor) | C3 B | falls A -> B |
| --- | --- | --- | --- |
| 11 (primary) | 10/20 | 9/20 | 7 -> 4 |
| 5 | 13/20 | 13/20 | 4 -> 3 |
| 23 | 16/20 | **8/20** | 3 -> 8 |
| pooled | **39/60** | 30/60 | 14 -> 15 |

**Verdict: negative.** The primary endpoint (the falls fall >= 2/3 at seed 11) fails (4 vs 7);
the pooled outcomes are the worst of the four arms; the seed-23 branch collapses (16 -> 8, the
falls 3 -> 8). The cut range is not the depth instrument either.

## The arc's close-out (four arms, three batteries, one anchor)

| arm | seed 11 | seed 5 | seed 23 | pooled | falls |
| --- | --- | --- | --- | --- | --- |
| A (the shipped anchor) | 10 | 13 | 16 | **39/60** | 14 |
| P11-C B (from-open arrival) | **13** | 10 | 12 | 35 | **10** |
| C2 B (+ the chase stop) | 6 | 13 | 12 | 31 | 15 |
| C3 B (+ the cut range) | 9 | 13 | 8 | 30 | 15 |

**Every control-side variant loses pooled against the anchor.** The one genuine positive - the
from-open arrival at the primary seed (13 vs 10, the falls 7 -> 3, the interval -21 %) - does
not survive the controls (the marginal grips are disturbed; the class re-draws). The two depth
instruments (the chase stop, the cut range) each break a different branch.

**The conclusion:** the ejection (and the no-grasp class behind it) is **not reachable from the
control-side knob space as it exists** - the arrival, the depth and the force-servo behavior
are coupled, and every partial fix trades one branch for another. The named paths remaining:
(a) the **scene-level design** (a pick station / an approach geometry that never requires the
descend-onto-the-fruit re-seat - the D3-proper form the owner has gated), and (b) the
**physics-side realism** - now unblocked for iteration by the owner's directive (the two-line
anchor as the only reference; the full re-baseline deferred to adoption), with P12-A (the
property realism batch) already in flight. The probe's corrected reading bounds the physics
hope: the contact parameters do not move the ejection (P11-B), so the physics path's value is
the *fidelity* (masses, restitution, compliance) and any second-order performance effects, not
the ejection itself.

**The no-harm (this battery)**: the A runs replay the P10-C.3 flip records 0 diff (the P11-C
verification); the acceptance 9/10 + `fingerprint: matches` + 385/385 (the C2 chain's run).
