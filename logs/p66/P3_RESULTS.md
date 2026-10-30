# P66 phase 3 results — the N=5 rung batch, completed to N=4 (the fifth seed was lost to a server restart)

Written by the orchestrator after the phase-3 lane was cancelled by a server
restart. The batch is intact in `logs/p66/p3/`; **seed 404's runs were interrupted**
(`control_404.log` is partial, no `C24_404`/`C20_404`), so the table is **N=4**
(seeds 77/101/202/303 x 3 arms), which the doc states rather than rounding up.

Registration: `logs/p66/PREREG_P2.md` (the rung test the gate asked for, plus the
place-transit `clr` gate). Dispositions: `logs/p66/DEVIATION.md`.

## The table (N=4; the left's `grasp_lift` legs)

| arm | lift end | `drift_end` median [range] | **left placed** | right placed |
|---|---|---|---|---|
| **control (shipped)** | 0.36 | **25.2 [20.3-62.1]** | **0/19 (0 %)** | 41/41 (100 %) |
| **C24** | 0.24 | **3.4 [2.0-23.8]** | **11/23 (47.8 %)** | 36/37 (97.3 %) |
| **C20** | 0.20 | **0.7 [0.6-24.9]** | **11/19 (57.9 %)** | 35/41 (85.4 %) |

**The class effect is large and one-sided**: 0/19 vs 11/23 (Fisher **p ~ 3e-4**) and
0/19 vs 11/19 (p ~ 1e-4). **The rung reads flat**: C24 and C20 are
indistinguishable (47.8 vs 57.9 %, Fisher p ~ 0.75), so **0.24 is the economical
rung** - the lowered lift costs the place leg less and buys the same class.

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
