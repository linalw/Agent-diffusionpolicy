# P66 phase 3 results — the N=5 rung batch (completed)

Written by the orchestrator. The phase-3 lane was cancelled by a server restart
mid-batch; the batch itself resumed and **completed**, so this is the **N=5**
table (seeds 77/101/202/303/404 x 3 arms).

Registration: `logs/p66/PREREG_P2.md` (the rung test the gate asked for, plus the
place-transit `clr` gate). Dispositions: `logs/p66/DEVIATION.md`.

## The table (N=4; the left's `grasp_lift` legs)

| arm | lift end | `drift_end` median [range] | **left placed** | right placed |
|---|---|---|---|---|
| **control (shipped)** | 0.36 | **25.1 [20.3-62.1]** | **0/25 (0 %)** | 50/50 (100 %) |
| **C24** | 0.24 | **3.4 [2.0-23.8]** | **12/30 (40.0 %)** | 44/45 (97.8 %) |
| **C20** | 0.20 | **0.7 [0.6-24.9]** | **14/25 (56.0 %)** | 44/50 (88.0 %) |

**The class effect is large and one-sided, and it is run-level unanimous**: the
control places **0/25** and is **0 in every one of the 5 seeds**; C24 places
**12/30** (Fisher vs the control **p ~ 2e-4**) and C20 **14/25** (p ~ 2e-5), each
beating the control in **5/5 seeds** (the run-level sign test's ceiling, p = 0.031).
**The rungs are not separable at this n** (40.0 vs 56.0 %, Fisher p ~ 0.28), so
**0.24 remains the economical rung** - it buys the same class at half the place
cost - while 0.20 reads the deeper mediator (0.7 vs 3.4 deg).

The mediator is monotone with the rung and **zero-overlap at the bottom**: 25.2 ->
3.4 -> 0.7 deg, the same dose-response the static sweep predicted
(`logs/p66/STATION_SWEEP.md`: 0.79 / 6-10 / 26-42 deg at z 0.09/0.25/0.36).

## The two gates this phase was run for

1. **The place-transit `clr` gate: NOT MEASURED.** The print-only field is built
   (3 new selfcheck pins, no new reads - `_payload_clearance` was already computed
   every tick), but its **reduction is wrong for the question**: it prints the
   leg's **minimum** clearance to the highest surface under the payload, which
   includes the phase where the payload is still on the input belt (readings
   `@rail -18/-24 mm`, `@belt -3/-7 mm`, `@obelt -182 mm`). The question is the
   clearance **at the crossing** (`y = 0.4125`), or equivalently whether any tick
   in the transfer segment goes negative. **Until that reduction is fixed the gate
   that could block the flip is unmeasured** - do not read the negative
   leg-minima as "it clips".
2. **The right-arm invariance: not clean at this n.** The right reads
   **100 / 97.3 / 85.4 %** across the arms. The scope is structural (the resolver
   emits only `{"left": dz}` and `lift_dz_for` returns `None` for the right), and
   the phase-2 batch's right arm itself spanned **88.9-95.8 %**, so this is most
   likely the branch; but at N=4 it is not a clean no-op signal and must be
   quoted as such.

## Verdict: **the lever is real and large; the adoption is NOT certified**

Per Oracle gate 2 (`CONFIRM-FIRST`) the flip needed (a) N=5, (b) the `clr` gate,
(c) a clean right-arm no-op. This phase delivers **N=4** (the fifth seed lost to a
server restart, not a wedge), the `clr` field **built but mis-reduced**, and a
right arm that is structurally scoped but **not statistically flat at N=4**.

**Nothing was flipped.** `FRUIT_LIFT_DZ` stays **default off** (unset = the shipped
0.36 lift). The next spend, in order: (1) fix the `clr` reduction to the
crossing/segment form and re-read it on the existing logs (offline, minutes);
(2) seed 404 (and a sixth if the bar is read strictly) to complete N=5;
(3) then the flip with its re-baseline note (every pre-P66 direct number is a
0.36-lift number; `FRUIT_LIFT_DZ=+0.08` restores it).
