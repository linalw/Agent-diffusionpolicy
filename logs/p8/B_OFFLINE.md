# P8 B-lane offline: an FP-fix retry variant for the C-3 carry monitor - the load-floor gate clears the frozen bars

Lane P8 B (offline), Tier C, 2026-10-16. Inputs: `logs/p7/PREREG_CARRY_MONITOR.md`
(the frozen monitor: 6 features, threshold + 2-tick persistence, the loaded-contact
gate, the FP cap 2 of 33, K1-K5), `logs/p7/C3_REPLAY.md` (the Phase-0 gate PASS with
FP exactly at the cap; the FP class = one clean one-sided low-force hold,
`w8/B_traces_mech/trace_10`), `logs/p7c/B_RESULTS.md` (the battery: B1 interval
-24.0 % paired 33-0, but K2 killed the form at 5 clean-leg aborts > cap 2; live
FP 5/19 vs replay 1/20), `scripts/203_c3_monitor_replay.py` (the frozen fit/replay,
reused), `logs/p6/B1_reread.md` section 1 (JCAC's conformal action-space risk as the
named second signal), `docs/papers/MECHANISMS.md` item 1. One new read-only analysis
script: `scripts/205_c3_fp_retry.py` (md5 `47c1eabe6f609d3f671bfc3f1ec92a92`).
No simulator, no `src/` change, no commit. Reproduce:
`python3 scripts/205_c3_fp_retry.py` (~26 s, deterministic, prints only).

**Verdict: a clearing variant exists.** The recommended fixed monitor - the frozen
scorer, threshold and persistence, plus a **one-sided load floor**:

```
hot(t) = z(t) >= 0 AND [ contacts(t) == 0 OR asym(t) >= 3.5 N ]
asym   = force - 2*ft_min = |ft0 - ft1|
```

- **frozen Phase-0 protocol (leave-one-trace-out, the gate of record): TP=31, FP=0,
  FN=0, TN=33; macro-F1 1.000** (frozen form: 31/2/0/31, macro 0.969). FP = **0 of
  33** clean legs against the cap of 2; **all 31 escapes detected**.
- identical under the deployed (embedded) constants: TP=31, FP=0.
- The only clean legs that move are the frozen form's FP pair
  (`w8/B_traces_mech/trace_10_right_direct_ok` legs #0/#1 - one clean attempt);
  no other clean leg changes, and no clean leg starts firing.
- Live-implementation replay (embedded constants + the live `vsep` convention + the
  running-min loaded gate): **TP=28, FP=0, FN=3, TN=33** (the frozen rule reads
  29/0/2/33 - reproduced exactly). Two of the three FNs are the frozen rule's own
  no-lead-time pair; the third (`w8/B_traces_mech_run1/trace_12` #0) loses a 4-tick
  lead because the floor defers its fire to its contact-loss row.
- Fired-window margins: tightest +0.16 N (one leg, `trace_08`); lowest first-fire
  window 3.98 N (+0.48 over the floor). Fire shift: 5 of 31 fires deferred (max
  +134 ticks); median remainder 67 ticks vs 70 (frozen) - the skip keeps ~0.56 s of
  the doomed leg.
- Estimated live FP: all five observed clean-hold aborts (leg force-min 1.51-3.26 N)
  sit below 3.5 N under the stationary-hold assumption (the trace_10 analogue is
  flat) -> expected K2 aborts 0 of 19 clean attempts (was 5). The residual is a
  clean one-sided hold sustaining >= 3.5 N - not observed; the closest is the kiwi
  at 3.26 N (0.24 N below the floor). This is a mechanism-based estimate, not a
  proof: the corpus cannot represent the live FP class (section 1).

The best-by-trade band and the alternates are section 4; the honest live-risk
reasoning is section 5; the draft pre-registration for the bounded battery is
section 7.

## 1. Why a retry, and what the offline gate can and cannot say

The frozen form passed its own Phase-0 gate at the cap (FP 2/33) and then failed
K2 live: 5 monitor-triggered aborts of would-be placements on clean legs
(`clean_slip_max` 0.1-1.0 mm, one-sided, low-force) of 19 clean attempts, against
the cap of 2 per battery. The pre-registered next step was JCAC's conformal signal.
This lane instead searches **bounded decision-rule fixes** on the same scorer -
three pre-specified families, all evaluated on the unchanged frozen corpus.

Two honest facts frame everything below:

1. **The live FP class is not in the corpus.** Under the deployed constants the
   frozen rule fires FP=0/33 on the corpus (`legmax` of the clean class -0.29); the
   five live clean holds fired at z 0.74-1.16. So the corpus clean class is not the
   live clean class: the live one-sided holds are a heavier-tailed version of the
   same signature (replay FP 1/20 clean attempts vs live 5/19). **No offline FP
   count - for any variant - bounds the live FP rate.** What offline evidence can
   do is (a) keep the frozen bars clear with margin, and (b) supply the mechanism
   (which physical signal separates the suspect class) that the battery then
   measures.
2. **The replay's FP pair is the boundary class by construction** (`C3_REPLAY`
   failure mode 1): the corpus holds exactly two one-sided clean legs (one attempt),
   and the fold models cross on exactly those two. The corpus cannot teach
   "one-sided but seated" robustly - which is why the fix must lean on a physical
   condition (load), not on a re-tune of the fitted boundary.

## 2. Method and reproducibility

`scripts/205_c3_fp_retry.py` imports `scripts/203_c3_monitor_replay.py` and reuses
its corpus loader, its W8-B labels and its leave-one-trace-out fit unchanged, then
evaluates decision-rule variants over the **same per-fold scores** (no new fitting
except the deployed-constants readout). Three conventions are reported:

| convention | what it is | used for |
| --- | --- | --- |
| **fold** | the frozen Phase-0 protocol (203): LOTO folds, `vsep` from the row `t`, no loaded gate | gate-comparable bars (macro-F1, FP/33, recall/31) |
| **deployed** | the all-data fit (the constants embedded in the live monitor), same feature/vsep convention, no gate | the live-model analogue of the same rule |
| **live implementation** | deployed constants + `CONTROL_DT` `vsep` + the running-min loaded-contact gate (`_CarryMonitorLeg` semantics) | the expected live/stub readout |

Corpus invariant reproduced exactly: 55 traces (54 CV folds), 89 legs =
held 33 / escape 31 / no-contact 25 / jitter 0. The `frozen` row reproduces
`C3_REPLAY` (TP=31 FP=2 macro 0.969) and the `live implementation` frozen row
reproduces the P7-2b stub exactly (TP=29 FP=0 FN=2 TN=33) - two anchors that pin
the machinery. The script writes nothing.

## 3. Candidate families: the measured trade

All rows are the fold protocol unless said otherwise. "Live-conv" = the live
implementation replay (28+ means it fires on at least that many of the 31 escapes
and keeps a pre-loss window; "anchors blocked" = of the five observed live FP
aborts, how many the rule suppresses at the observed fire site / under the
stationary-hold assumption - section 5).

| variant | family | fold TP/FP/FN | macro-F1 | clean legs changed | fold fire shift (later n / max delta / rem p50) | live-conv TP/FN | anchors blocked |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frozen (z>=0, P2) | - | 31/2/0 | 0.969 | 2 FP (trace_10 #0/#1) | 0 / - / 70 | 29 / 2 | 0 |
| persist 3 | a | 31/2/0 | 0.969 | none | 0 / - / 70 | 29 / 2 | 0 |
| persist 5 | a | 30/2/1 | 0.953 | none | 1 FN | - | - |
| margin 0.5 | a | 31/2/0 | 0.969 | none | - | - | 0 |
| margin 0.75 | a | **31/0/0** | **1.000** | trace_10 pair stops | 2 / +4 / 70 | 28 / 3 | 2 of 5 (z) |
| margin 1.0 | a | **31/0/0** | **1.000** | trace_10 pair stops | 4 / +75 / 70 | 28 / 3 | 3 of 5 (z) |
| margin 1.106 (boundary) | a | 31/0/0 | 1.000 | trace_10 pair stops | 5 / +114 / 67 | 28 / 3 | 4 of 5 (z) |
| margin 1.25 | a | 30/0/1 | 0.984 | - | kills `w8mech trace_12`#0 | - | 5 of 5 (z) |
| force 2.58 (= conformal b2) | b/c | **31/0/0** | **1.000** | trace_10 pair stops | 4 / +134 / 67 | 29 / 2 | 4 of 5 (fmin) |
| **force 3.5 (pick)** | c | **31/0/0** | **1.000** | trace_10 pair stops | 5 / +134 / 67 | **28 / 3** | **5 of 5 (fmin)** |
| force 3.75 | c | **31/0/0** | **1.000** | trace_10 pair stops | 6 / +134 / 67 | 28 / 3 | 5 of 5 |
| force 4.0 | c | **31/0/0** | **1.000** | trace_10 pair stops | 7 / +134 / 67 | 27 / 4 | 5 of 5 |
| force 4.32 (boundary) | c | 31/0/0 | 1.000 | trace_10 pair stops | 5 / +114 / 69 | 26 / 5 | 5 of 5 |
| force 4.5 | c | 30/0/1 | 0.984 | - | kills `run1 trace_13`#0 | - | 5 of 5 |
| joint 1.0 + 4.0 | a+c | 31/0/0 | 1.000 | trace_10 pair stops | 8 / +134 / 67 | 26 / 5 | 5 of 5 |
| confirm-at-fire 4.0, m=2 | c | 31/0/0 | 1.000 | trace_10 pair stops | **31 / +130 / 66** | - | 5 of 5 |
| conformal b1 (score-level) | b | 31/2/0 | 0.969 | none | - | - | 0 |

(`force af` = hot tick requires `z >= 0 AND (contacts==0 OR asym >= af)`,
persistence 2. `confirm-at-fire` = frozen stage-1 fire, then 2 consecutive load
ticks at/after the fire tick. Live-conv TP is the *reclaimable* count under the
running-min gate; the other FNs are stated per row in the script output.)

### 3.1 Family (a): persistence and decision margin

- **Persistence alone is dead.** The two FP legs are hot for their entire length
  (every tick of both, 166 and 245 ticks, at z >= 0.5). P=3 is bit-identical to
  frozen; P=5 only starts eating escapes (FN=1). No N-tick persistence change can
  separate the class.
- **The margin family clears** in a measured band: fold clean max +0.649 /
  escape binding min +1.106 (the binding escape is `w8mech trace_12`#0, whose best
  2-consecutive window has min z = 1.106); deployed band (-0.350, +1.124]. tau
  in (0.649, 1.106] -> FP=0/33, TP=31/31, macro 1.000. P=3 at any tau cannot
  clear (fold P3: clean max 0.648 > escape min 0.621).
- Costs: tau=1.0 defers 4 fires (max +75); under the live gate it loses
  `w5 trace_08` (its fire would move to its loss row). It also changes the frozen
  threshold - the frozen scorer's own semantics - and its live-FP suppression is
  the weakest of the clearing row (3 of 5 observed at their fire sites; the 1.04
  and 1.16 fires pass).

### 3.2 Family (b): the JCAC-style conformal second signal

Two cheap surrogates were measured; both are negative as *FP fixes*:

- **b1, score-level conformal.** Calibrate the conformal radius from the clean
  legs (per fold, the other traces' clean legs; the deployed analogue = the
  all-clean max). The radius is **-1.84** (z units) at the trace_10 fold (the
  other clean legs are all deeper negatives) and -0.29 deployed; the leg-max
  readout (base fire AND legmax >= tau) is TP=31/31 **FP=2/33 - no FP
  reduction**. The structural reason: the FP legs are *members of the only clean
  calibration population*, so the conformal quantile cannot exclude its own tail,
  and the guarantee is coverage, not discrimination.
- **b2, one-sided force radius.** The per-feature surrogate *does* carry the
  mechanism: the maximum `asym` over the clean-leg one-sided ticks (411 ticks, the
  two trace_10 legs) is **2.58 N**, and requiring it separates the corpus (FP=0,
  TP=31/31). It is a valid but live-fragile floor: 2.58 N sits below the heaviest
  live clean hold (3.26 N), so it blocks only 4 of the 5 observed. The designed
  floor (family c) is the same mechanism, placed inside the measured band.

**b1's honest form therefore cannot clear**; the useful "second signal" is the
same-channel load bound, not the classifier score.

### 3.3 Family (c): the load-floor confirm (recommended)

`asym` is the single-pad load: `force - 2*ft_min`; for a one-sided hold it *is*
the loaded pad's force; for a healthy two-sided hold it is the imbalance
(~0.1-0.5 N). The physics is the W8-B mechanism: the escape is a **loaded slide**
(pad force at its carry level, median 4.90 N at onset); the clean one-sided hold
carries the payload at ~2 N (trace_10: force 1.89-2.58 N flat over 166/245 ticks).
The measured feasible band:

- **fold, best-window**: clean max 2.47 N -> escape min 4.32 N (`run1 trace_13`#0).
- **live convention, first-fire windows** (the live-relevant one): the lowest
  first-fire window among the 31 is **3.98 N** (`run1 trace_02`#0; next 4.04,
  4.24, 4.32); `w8mech trace_08` fires through a 3.66 N window at tick 117 but
  still fires at 119/4.51 when the floor exceeds 3.66.
- **live clean ceiling observed**: 3.26 N (the kiwi abort's force_min, the
  heaviest of the five).

The grid (section 3 table): af in {2.58, 2.75, 3.0, 3.5, 3.75, 4.0, 4.32} all clear
the fold bar with FP=0/33, TP=31/31, macro 1.000; af=4.5 fails (FN=1). Under the
live gate: 2.58/2.75 are recall-free (29/31), 3.0-3.75 cost one leg
(`run1 trace_12`#0, 4-tick lead), 4.0 costs two (`+ run1 trace_02`#0, 12-tick
lead), 4.32 costs three.

**Why 3.5 N is the pick.** It is the smallest half-grid value strictly above the
heaviest observed live clean hold (3.26 N), keeps >= 0.4 N below the lowest corpus
escape first-fire window (3.98 N), and keeps the extra gated leg that 4.0 loses.
The FP-safe alternates are 3.75/4.0 (named in the draft pre-reg); 2.58 is the
conformal surrogate (recall-free, but leaves the kiwi-class clean holds live).
The joint (margin + floor) and the confirm-at-fire form were both measured and are
dominated: the joint adds no live-FP power over the floor alone while costing
another gated leg; confirm-at-fire latching adds >= 1 tick to every fire (31/31
deferred, remainder 66 vs 67) because it ignores the load evidence inside the
stage-1 window.

## 4. The recommended variant: numbers

Rule: frozen scorer, `z >= 0`, persistence 2, loaded-contact gate, direct scope,
fast-skip action - plus `hot` additionally requires
`contacts == 0 OR asym >= 3.5 N` (the `contacts==0` exemption is *live-inert*:
a contacts==0 tick closes the running-min gate in the same tick; it is kept only
so the offline 203-protocol readout stays continuous with the frozen rule).

- **fold (gate of record)**: TP=31 FP=0 FN=0 TN=33; escape P/R/F1 = 1.000;
  clean P/R/F1 = 1.000; macro-F1 1.000. FP 0/33 <= cap 2.
- **deployed, no gate**: TP=31 FP=0 FN=0 TN=33; macro 1.000.
- **live implementation**: TP=28 FP=0 FN=3 TN=33. FNs: `w8mech trace_13`#1 (frozen
  None, loss 98) and `w8mech trace_15`#0 (frozen None, loss 135) - the frozen
  rule's own no-lead-time pair - plus `run1 trace_12`#0 (frozen fire 121, loss
  125: the floor defers the fire 4 ticks to the loss row).
- **Clean legs moved**: exactly the two FP legs stop firing
  (`w8/B_traces_mech/trace_10_right_direct_ok` #0 and #1); no other clean leg
  changes state; none starts firing. Under the deployed constants these legs never
  fired (FP=0), so the change is only visible in the fold readout - which is the
  gate's convention.
- **Load margins at the fire windows**: tightest +0.16 N (`w8mech trace_08`'s
  3.66 window); lowest first-fire window 3.98 N (`run1 trace_02`#0, +0.48);
  `run1 trace_13`#0 4.32 (+0.82).
- **Added latency (fold)**: 26 of 31 fires at the frozen tick; 5 deferred -
  `w7 trace_03` +4, `run1 trace_04` +134, `run1 trace_09` +87, `run1 trace_12`
  +4, `run1 trace_13` +114 - all still fire before their loss rows; **remainder
  median 67 ticks vs 70 (frozen)**. (`w8mech trace_08` is a 3.75+ deferral only:
  +2 at floors above its 3.66 N window.) Live-convention: 4 deferred, max +134,
  remainder 67. (The action is post-window scheduling; the onsets themselves are
  the closed 0-2 tick window - latency only prices the skip's own reclaimed time,
  and ~0.5 s of the doomed leg remains.)
- Per-leg detail for all 31 escapes and the full table are in the script output
  (reproduce command above).

## 5. Estimated live FP risk (honest)

- **The shift is real and large**: replay FP 1 of 20 clean attempts vs live 5 of
  19 (5 distinct attempts; all one-sided, `force_min` 1.51-3.26 N, fire z
  0.74-1.16). Under the deployed constants the corpus FP is *zero*; the live class
  is not represented. Nothing below is a proof; the battery measures.
- **The fixed rule's kill condition on the live class** is the one-sided pad load.
  The five observed holds read leg-min force 3.26 / 2.12 / 1.51 / 1.79 / 1.81 N;
  the trace_10 analogue is a flat hold (1.89-2.58 N over its whole length). Under
  the stationary-hold assumption, each observed hold's fire window stays below
  3.5 N and the skip never latches: **5 of 5 suppressed -> expected K2 aborts 0**
  (cap 2; was 5). The residual: a clean one-sided hold sustaining >= 3.5 N for 2
  consecutive ticks - not observed; the kiwi (3.26 N min) is 0.24 N below the
  floor. One such hold would abort it (expected 1 abort, still passing); two would
  kill. The honest bound is *conditional*: the `[carry]` line exposes only
  `force_min` (`force@fire >= force_min`), so a non-stationary hold could slip past.
- **Why not the margin instead**: the margin (tau=1.0) suppresses 3 of the 5
  observed fires (0.91/0.74/0.74 < 1.0; the 1.04/1.16 fires pass) and has no
  revisit evidence for their later windows; the floor targets the class's physical
  signature and covers all five.
- **The healthy class is untouched**: two-sided healthy holds read z ~ -3.6 through
  the scorer (they never enter the suspect state), so their ~4.2-4.5 N load never
  meets the floor's condition; the floor only gates the *one-sided* suspect state.
- **B1-side risk**: the stricter window defers 5 (fold) / 4 (live) fires by
  +4..+134 ticks and removes one further gated fire (`run1 trace_12`#0, 4-tick
  lead). Against the frozen battery's B1 headroom (-24.0 %, paired 33-0), a ~1/31
  detection-loss term is small; the battery measures it.
- **FN risk on live escapes**: the corpus's lowest escape first-fire window is
  3.98 N, and no escape's pre-loss windows fall below 3.5 N except
  `run1 trace_12`#0's (which the gate therefore defers past its loss); the two
  other gated FNs are the frozen rule's own no-lead-time pair. A live escape whose
  only pre-loss windows sit below 3.5 N cannot be acted on - the same class as the
  frozen rule's no-lead-time pair.
- **Scale caveat**: pad load scales with fruit weight (the kiwi is the heaviest
  clean hold observed). Both classes shift together (the loaded slide's onset was
  4.90 N median in W8-B), but the floor is not weight-invariant - a heavy-fruit
  clean hold is the class to watch in the battery's per-abort table.

## 6. Residuals (named)

1. A clean one-sided hold sustaining >= 3.5 N (not observed; kiwi 3.26 N) - the
   one named way K2 can still trip.
2. Live escapes whose pre-loss one-sided load never reaches 3.5 N (none in the
   corpora below 3.66 N for a fired window).
3. The corpus is scenario-bound (four trace corpora: dense-dispatch, patch-sheet
   direct, scripted); the floor's band is a corpus measurement.
4. The `run1 trace_12`#0 detection loss (4-tick lead) and the four deferred fires
   are the leash on B1.
5. The scaled-fruit-weight caveat above.

## 7. Draft pre-registration block (for the orchestrator to freeze)

**P8-2 battery: the fixed C-3 carry monitor (load-floor form), B fast-skip only.**
Draft written after the offline search; the search families were pre-specified by
the lane task (a: persistence/margin; b: conformal surrogate; c: load confirm), the
bars and structure below are `logs/p7/PREREG_CARRY_MONITOR.md`'s with exactly one
bounded change: the monitor's decision rule.

**7.1 Arms and scenario (verbatim W8-A/W8-B battery).** Patch sheet
(`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`,
`FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25`), arrival trigger lead 0.9, shipped
lateral gate (0.16), dynamic never-stop handover,
`FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1` on both arms, direct presentation,
`RUNS=5 EPISODES=15`, seeds `77 101 202 303 404`, policy seed 11, interleaved, one
`154_claim_run.sh` claim (Tier A solo), via `scripts/112_rl_ab.sh`.
`FRUIT_CARRY_DIAG=1` on **both** arms (the symmetric FP readout).

| arm | checkpoint | env delta | readout |
| --- | --- | --- | --- |
| **A** | `moe_v13s` `61da390a...` | none (ACQ=1 + R7-A pinned) | the reference |
| **B** | same | `FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5 FRUIT_CARRY_MONITOR_DIAG=1` | interval on the failed-attempt set |

**B-only** (the frozen B' re-seat form is not built and not part of this battery;
the success-rate route needs its own pre-registration).

**7.2 The one rule change (bounded).** In `_CarryMonitorLeg.step`, the hot
predicate becomes `z >= 0.0` **and** `(contacts == 0 or force - 2*ft_min >= floor)`
with `floor = FRUIT_CARRY_MONITOR_LOAD_FLOOR` (default **0** = the P7-2b behavior
exactly; 3.5 N on arm B). Persistence 2, the loaded-contact gate, the direct-capture
scope and the fast-skip action are unchanged. The `contacts==0` exemption is
live-inert (the gate closes on the same tick); it exists for offline continuity
with the frozen protocol. The `[monitor] fire` diag line gains the firing window's
`asym` margin (`asym@fire = min over the firing window`), so K2 can classify every
fire from the log.

**7.3 Offline gate (measured, in hand; this lane).** Frozen protocol: TP=31 FP=0
FN=0 TN=33, macro-F1 1.000, FP 0/33 <= the frozen cap 2/33. Implementation replay
pins for the stub test: `floor=0` -> TP=29 FP=0 FN=2 TN=33 (must reproduce P7-2b);
`floor=3.5` -> TP=28 FP=0 FN=3 TN=33 (the third FN is `run1 trace_12`#0; the other
two are the frozen rule's no-lead-time pair). A stub mismatch is a STOP.

**7.4 Endpoints (fixed now, unchanged from the frozen pre-reg).**
1. **B1 primary - interval on A's failed-carried attempts must FALL** (pooled mean
   and median; paired same-(run, episode) subset with the sign split).
2. B1c report: the fired-subset vs non-fired control spans.
3. **B2 lock-on** (`premove+axis+hover+wait` median) <= +5 % vs A.
4. **B3 cycle** (pooled median per-attempt ticks) <= +5 % vs A.
5. **B4 zero new failure reasons** (the 113 parser's baseline set).
6. Record the fire -> leg-boundary remainder and the re-seat count (expect 0/0;
   `FRUIT_CARRY_GUARD` off).

**7.5 Kill criteria (fixed now).** K1 = the offline gate above (PASS in hand:
FP 0/33, all 31 detected). K2 = monitor-triggered aborts of would-be placements
per battery **> 2** (the P7-2b definition: a fire on a leg whose live `[carry]`
line reads `clean_slip_max <= 2.0 mm` and the attempt ends not-placed by the skip;
clean-leg/attempt denominators reported). K3 n/a (B-only). K4 = any new failure
reason. K5 = the no-harm bar (7.6).

**7.6 No-harm bar (knob off / defaults).** `scripts/accept.sh` 9/10 +
`fingerprint: matches` + the `[fruit]` stream identical to the record; the two-line
dense re-record 442/442 + `scripts/190_twoline_gate.sh` PASS; `scripts/selfcheck.sh`
PASS; floor default 0 byte-inert; monitor traffic trace-only.

**7.7 Pre-registered expectations (for the record; not gates).** Expected live
clean aborts 0-2 (was 5); expected fired legs ~28/31-equivalent with the three
named FNs; fire -> boundary remainder ~67 ticks median. The residual risk is the
named one: a clean one-sided hold sustaining >= 3.5 N.

**7.8 Pins.** Battery time re-pins its own tree (P7-2b pattern). Writing-time tree:
HEAD `0a48ce9565c1b88ff3a13496db25a2c71f8a9b4b`; `src/fruit_sorting/tasks.py`
`7489f302c14e65aa9771f674e4ee199b` (the P7-2c tree; P8-1 implements on top and must
re-pin); `rl_env.py` `75b315d3c9a2680d973dabeac045b631`; checkpoint `moe_v13s`
`61da390a85fa209496b54477a8255d23`; `configs/*` untouched.

## 8. Provenance

- Script: `scripts/205_c3_fp_retry.py` (md5 `47c1eabe6f609d3f671bfc3f1ec92a92`,
  read-only, deterministic, ~26 s); reuses `scripts/203_c3_monitor_replay.py`
  (`a4d906958ff43b75df61d1eb8b0947e4`) and `logs/w8/B_metric.py`
  (`53cbf99b5a8fb8afb019cdd233bb3645`).
- Frozen inputs: `logs/p7/PREREG_CARRY_MONITOR.md`
  (`5b31b3c3315572c4bce56d9319a1151b`), `logs/p7/C3_REPLAY.md`
  (`daf77bdceaa1794e31f6c9f57058c9a1`), `logs/p7c/B_RESULTS.md`
  (`ca999414711e94773d3d475da9e9940f`).
- Corpora (read-only, unchanged): `logs/w7/B_traces_mech`, `logs/w5/traces_dense`,
  `logs/w8/B_traces_mech`, `logs/w8/B_traces_mech_run1`.
- No shipped default changed; no `src/` file touched; no commit.
