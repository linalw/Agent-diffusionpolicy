# WORKLOG entry — P18-C: the slide gate's trigger threshold (2026-10-19, branch `p-supply`)

### The 60 mm/s slide-gate threshold sits inside the ok transient band; the recalibrated point is 90 mm/s / 2 ticks

**The question.** The P17-B hold/probe-1 slide gate (`FRUIT_DYNAMIC_SLIDE_GATE`, default off) fires
when the payload's hand-frame drift rate exceeds `FRUIT_DYNAMIC_SLIDE_GATE_MMPS` (60) for
`FRUIT_DYNAMIC_SLIDE_GATE_TICKS` (3) consecutive samples while the accumulated drift is inside
`FRUIT_DYNAMIC_SLIDE_GATE_WINDOW_MM` (60). The Oracle's Gate review found the trigger fired on
7/20 attempts at seed 11 including 3 that placed — is 60 mm/s inside the ok per-tick transient
range, and is there a better operating point?

**The method.** Read-only recomputation of the gate's own rate recipe from the on-disk traces
(`fruit − jaw` in the world frame per tick; the trace's `jaw` *is* the OpenArm hand's
`pad_centre()`), on the unbiased P14-B control corpora (`logs/p14b/traces_s{11,5,23}`, 60
attempts, the P14-B class labels: ok 45 / carried 7 / B1 5 / B2 3) and the gate-ON Stage-P
corpora (`logs/p17i/traces_p_s{11,5,23}`, 60 attempts, ok 37 / carried 13 / no-grasp 10;
`traces_m1` ≡ `traces_p_s11`, all 20 files byte-identical).  Validation against the gate's own
`[slide]` rows: the per-tick `probe1` phase reproduces the gate's `rate_max` at a median ratio
0.992 and the drift at 1.000; the `hold` phase (the trace samples it every 2 ticks) at 0.838 —
a measured resolution limit, carried through the analysis.  The trace detector at the shipped
rule reproduces 11 of the gate's 12 actual fires with zero extras (the miss: an ok hold spike the
2-tick sampling smoothed).

**The findings.**

* **The ok band reaches above 60**: the ok per-tick (probe-1) max is 130.7 mm/s and its
  *2-sample sustained* max is 81.5 (`s23/11`: a 130.7/81.5 pair).  The shipped rule fires on
  **3/45 ok attempts (6.7 %)** at the trace resolution (5/45 = 11 % at the trigger-happy hold
  bound) — `s11/20` (a 7-sample 63-74 stretch), `s23/11`, `s5/16`.  Every ok fire sits on a
  **flat drift** (a jitter, 4-27 mm); every B1 fire sits on a **growing drift** (a walk).
* **The B1 walks separate by their sustained rate and length**: 2-sample sustained 94-288 mm/s
  over 11-75 samples (hold runs 17-75 samples at 137-310 mm/s), drift to 52-166 mm.
  `s11/14` is the unreachable one (hold max 9.0, probe1 max 37.3 — its loss is outside the
  monitored window), so **4/5 B1 is the ceiling** for any rate rule; the B2 (never-held) class is
  quiet in the window (only `s11/3` has a 2-sample spike).
* **The M1 "3 oks fired" is not all false positives**: `s11/2` (left orange) is the *same
  physical attempt* as the control's `s11/1` B1 walk — the first nine hold samples are identical
  (9.4 … 130.5 mm/s) and the runs diverge exactly at the gate's trigger (`trig@19
  rate=114.2mm/s`); in the control it is a no-grasp failure, in the gate-ON run it placed.
  The unbiased FP basis is the controls'.
* **The window (60 mm) never binds** (0/60 attempts changed at any candidate rule): the triggers
  land at 4.8-23.3 mm of drift.
* **The usable threshold window is (81.5, 94.1] mm/s for a 2-sample rule** (the ok's worst
  sustained pair vs the weakest walked B1's).  90 is the recommended point: on the controls it
  fires on **4/5 B1 walks with 0/45 ok fires** — the 4/5 ceiling with zero collateral, and the
  same confusion at both hold-alignment bounds.  The shipped rule's run-length alternative
  (60 mm/s, 8-10 samples) also reaches 0/45 with 4/5 but on a one-sample margin (the ok's worst
  stretch is exactly 7, `s23/3`'s catch needs exactly 8).  The max-recall variant (80 mm/s,
  2 ticks) gives 5/8 no-grasp (adds the `s11/3` B2 spike) at 1/45 ok.

**The verdict.** A recalibrated operating point exists — **`MMPS=90`, `TICKS=2`, window 60** —
and it is the M1c screen candidate.  It is a chosen point on a continuous trade, not a clean gap:
the ok's transient band reaches 81.5 mm/s (2-sample sustained), the weakest walked B1 sits at
94.1, and the FP ≤ 1 criterion is satisfied by 320/420 triples, so the evidence for "60 is too
low" is the direction and the mechanism (flat-drift jitters vs growing-drift walks), not a
significance result at 45 oks / 5 B1s.  No shipped default was changed by this analysis (it is
offline and read-only).

**Provenance.** `logs/p17c2/{threshold_analysis.py,phase_split.py}` →
`{threshold_tables.txt,phase_split_tables.txt}`; the report is `logs/p17c2/THRESHOLD_ANALYSIS.md`.
Inputs: `logs/p14b/` (the control corpora + `TRACE_RESULTS.md`), `logs/p17i/`
(`{50,52,54}_seed*_slide.log` + `traces_p_*`, `20_m1_trace.log` + `traces_m1`, `P_RESULTS.md`,
`ORACLE_GATE.md`), `src/fruit_sorting/{tasks.py,kinematic_gripper.py}`.  No simulator run; no
write outside `logs/p17c2/`.
