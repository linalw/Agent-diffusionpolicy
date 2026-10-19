### P14-B grip-margin diagnostic (2026-10-19, branch `p-supply`, Tier C offline): the offline mining finds no aggregate separator for the no-grasp class — but the existing W5-C per-tick trace corpus separates and phase-localizes it (ok drift 0.0-20.5 mm vs fail 313.2-1992.0 mm, disjoint); the P10-E keep-gap arithmetic is refreshed to a non-discriminator (a success carries a full-chase re-seat); the trace-run pre-registration sketch is delivered

**Scope: read-only, no simulator** (the P14-A canary chain was running in `logs/p14/` throughout
and was not touched; no simulator command, no `src/`/`scripts/`/`configs/`/`datasets/`/`Paper/`
write; no commit). All artifacts under `logs/p14b/`. Tree pins: `tasks.py`
`810658b802d22bbd63013726fc78af81` (unchanged by P12/P13; the last commit touching it is `30cde55`),
`fruits.py` `d28546d2`, `scene.py` `ab85dca2`, `meshes.py` `0e32b1ad`.

**The mandate.** The P12-B.2 scoping (`logs/p12b/SCENE_OPTIONS.md`, "the strongest reason any of
them could fail") named the cheap diagnostic: the existing `FRUIT_DYNAMIC_TRACE=1` per-tick rows
on the base's B1 attempts. This lane does the offline half: (1) mine every existing log for the
pad-fruit geometry signals that exist; (2) design the trace run as a frozen pre-registration
sketch; (3) name the levers the geometry would discriminate.

**1. The mass-base mining (task 1).** The base = `logs/p12a2/{10_seed11,11_seed5,12_seed23}_mass.log`
(the two-line patch battery + `FRUIT_PHYSICS_REAL_MASS=1`, 3x20 attempts): **ok 45 / carried 7 /
no-grasp 8** (seed 11: 11/2/**7**; seed 5: 17/3/0; seed 23: 17/2/1); the class splits **B1 5 + B2 3**
(P10-E classify rules; no A, no C); the B1s all run 3 regrasps and 4 of 5 fall to the floor; the
B2s (no regrasp row at all, grip phase 1.77-1.95 s) stay at belt level. The P10-E §2.1 separator
table refreshed on the base: **every continuous pre-outcome row overlaps** (close ticks/force/span/
freeze, freeze-extent, G-D, catch-up, moving jump, pad error, descent wait, servo Fmax, carry-onset
fields, cycle phases, cone); the only disjoint columns are outcome-consequent (`clean_slip_max` NG
123.2-95724.3 vs ok 0.0-40.5 mm; the legacy `slip_max` likewise). The incidence tests (8 NG vs 45
ok, Fisher): the regrasp incidence 5/8 vs 5/45 **p=0.0037**, the cycle grip phase >= 3 s the same,
the servo `Fmin=0` 6/8 vs 7/45 **p=0.0016**, the servo `closed>0.5` 6/8 vs 8/45 **p=0.0027** — real
*associations* with the probe/regrasp cycle and the chase, but **not separators**: 5 of the 45 ok
attempts run the same cycle. **The P10-E B1 keep-gap arithmetic is refreshed to a
non-discriminator**: among the regrasp-bearing attempts the first keep-gap depth does not separate
(3/5 NG vs 1/5 ok, p=0.52), and the load-bearing counterexample is `11_seed5_mass` a15 (right
apple, **ok**): one regrasp re-seated at **49.3 mm kept on a 65.2 mm fruit (-15.9 mm, the servo's
whole 15 mm range)** and the attempt held (clean_slip 0.1 mm, lift +0.381) — verified against the
raw log window (lines 1123-1150). So a sub-extent re-seat is not sufficient for the ejection, and
the command arithmetic cannot identify the class's geometric driver — the exact gap the trace
fills.

**2. The existing per-tick corpus that DOES separate (mined, same task).** The only
`FRUIT_DYNAMIC_TRACE=1` corpus on the two-line scripted catch is the W5 arc's: five 10-attempt
runs of the dense W3 sheet at SEED 5 (`logs/w5/traces_dense` = cfg0 + `30_traces_{fs0,fs0sq0,
track02,lockx}` = the W5-C screen configs; **50 attempts, 35 ok / 15 fail**). Re-mined here
(`logs/p14b/trace_mine.py` + `trace_corpus_summary.py`) with the payload's cumulative hand-frame
drift (`hand_rel`, the W8-B frame) from the last `hold` row: **ok 0.0-20.5 mm (only 5 of 35 exceed
2 mm) vs fail 313.2-1992.0 mm — disjoint**, and the first-departure phase localizes every failure
(as computed: takeoff 4, probe 5, carry 6; cfg3 `t09`'s hold already reads `Fmin=0/cmin=0`, so the
true split is **hold 1, takeoff 4, probe 4, carry 6**). The two cfg0 failures: `trace_05` (hold 0,
probe 0, **takeoff 27.8 mm** at F 3.94 N, carry 312 mm — a belt-break onset) and `trace_08` (**hold
4.9 mm, probe 12.9 mm with F=0/contacts 0**, carry 1099 mm — a hold/probe onset). The lane's own
`logs/w5/21_mech_summary.txt`/`20_mech_failures.txt` report the same onsets independently. Two
further mined facts the design needs: (i) `logs/w5/20_dense_mech_trace.log` (trace-on) vs the
trace-off record `logs/w4/20_dense_repeat.log`: **0 `[fruit]` lines missing or changed** (63 extra
trace/banner rows only) — the trace was **run-neutral** on the dense two-line, contradicting the
blanket AGENTS §2 warning for this path (the mass base must re-test it); (ii) the `grip` row's
`hand_rel` is **junk** (`fruit=rest` at its call site, `tasks.py:8263`) — the analysis must use the
last `hold` row; and **the re-seat loops carry no trace call at all** (`tasks.py:8721-8742`,
`8756-8781`), so the re-seat is only *bracketed* (last probe row of cycle N to the first row of
cycle N+1/carry). `FRUIT_ACQ_DIAG` is a no-op on the scripted line (`tasks.py:6622`).

**3. The trace-run pre-registration sketch (task 2).** `logs/p14b/GRIP_DIAGNOSTIC.md` §2: the env =
the mass base verbatim + `FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR=logs/p14b/traces_s<SEED>`
(the dump writes labelled `trace_NN_{arm}_{scripted}_{ok|fail}.json`; the flush's
`logs/dynamic_trace_NN.json` is empty on this path — verified on the current tree), `ATTEMPTS=20`,
SEED 11 primary + 5/23 controls, 1 primary run + 1 seed-11 repeat (or a control-seed second run).
The per-tick rows listed with fields (the 11 phases: descent/catchup/close/hold/dwell/grip/
takeoff_probe/takeoff/pluck_dwell/carry/handover; `offset`, `hand_rel`, `sep`, `gap_cmd`, `force`,
`contacts`, `ft`, `fruit_vel`, `fruit_omega`, ...); the readouts (the freeze geometry, the per-tick
pad-fruit distance/angle, the blocking-span check `sep-gap_cmd`, the first departure > 2 mm from
the last-hold reference, the per-phase cumulative drift, the re-seat bracket, the carry
cross-check); the analysis (attempt pairing by arm x the `[run] attempt` sim window; within-run
NG-vs-ok per-phase distributions); the expected movement (the B1 losses in the probe/re-seat
bracket or the probe, the B2 in the takeoff, the ok drift at the W5-C scale); the falsifiers F1-F5
(the re-seat is not the ejector / the close is not visible / the probe owns it / the belt-break
owns B2 / the analysis fails); the cost (~9 min per trace-off battery measured 8 m 20 s-9 m 35 s;
the W5-A trace-on 10-attempt dense run 5 m 8 s; ~8 MB of JSON per 20-attempt run).

**4. The levers the geometry would discriminate (task 3).** Conditional on the phase readout:
re-seat window -> **`FRUIT_DYNAMIC_REGRASP_FLOOR`** (the P11-A §5a keep-gap + ratchet floor, named
but never built; the P11-C arrival family as-is is measured negative — from-open 35/60, +chase-stop
31/60, +range-cut 30/60); close/hold -> the close-side family (R11-B C1 `FRUIT_CLOSE_LOAD_RATE`,
the squeeze-side knobs — closed on the direct interface by R6-B/W8-B, not on the two-line); probe
-> the probe's shape (`FRUIT_DYNAMIC_PROBE`/`_TICKS`) with the W5-C probe screens standing as
negatives; belt-break (the B2 shape) -> the takeoff/belt-break timing family; carry -> the carry
guard family (measured closed); no separation -> the physics/containment/supply lanes.

**Deliverables (uncommitted, all under `logs/p14b/`)**: `GRIP_DIAGNOSTIC.md` (the mining tables,
the trace design, the candidates); the tooling `census.py` (the P10-E tool copied verbatim, md5
`3345de7c`), `mine_mass.py`, `keepgap_table.py`, `trace_mine.py`, `trace_corpus_summary.py`; the
raw outputs `mass_mining.txt`, `keepgap_run.out`, `trace_mine_*.txt`,
`trace_corpus_summary.txt`; this entry.

**No-harm / tree state**: no tree change at all (read-only lane; the single-arm default is
untouched; the running P14-A canaries were not touched). The P14-B trace run itself is a sketch —
it is not launched from this lane.
