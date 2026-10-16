# P8-2 PREREG (FROZEN): the fixed C-3 carry monitor (load-floor form), B fast-skip only

Frozen 2026-10-16 by the orchestrator from `logs/p8/B_OFFLINE.md` section 7 (drafted after the offline FP search, BEFORE the battery ran; bars and structure inherited verbatim from `logs/p7/PREREG_CARRY_MONITOR.md` with the single bounded change: the decision rule). The offline gate is measured (FP 0/33, escapes 31/31, macro-F1 1.000; stub pins floor=0 -> 29/0/2/33, floor=3.5 -> 28/0/3/33).

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
