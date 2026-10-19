# P18-C: the slide gate's trigger threshold — the data-driven calibration check

**Status.** Offline, read-only analysis (branch `p-supply`, 2026-10-19). No simulator was run;
nothing outside `logs/p17c2/` was written; `src/`, `scripts/`, `configs/` and every existing log
are untouched. Tree as read: `src/fruit_sorting/tasks.py` (the P17-B gate block at lines
640-700 / `_slide_gate_observe` at 10375 / `_slide_gate_tick` at 10538).

**The question.** The P17-B hold/probe-1 slide gate (`FRUIT_DYNAMIC_SLIDE_GATE`, default off)
fires when the payload's hand-frame drift *rate* stays above `FRUIT_DYNAMIC_SLIDE_GATE_MMPS`
(default **60**) for `FRUIT_DYNAMIC_SLIDE_GATE_TICKS` (default **3**) consecutive per-tick samples
while the accumulated hand-frame drift is inside `FRUIT_DYNAMIC_SLIDE_GATE_WINDOW_MM` (default
**60**). The Oracle's Gate review (`logs/p17i/ORACLE_GATE.md` item 8) found the trigger fired on
7/20 attempts at seed 11 including 3 that placed, with peaks up to 275 mm/s — i.e. the 60 mm/s
threshold may sit *inside* the ok population's per-tick transient range. Does a separating
(threshold, ticks, window) triple exist, and what is the best operating point?

---

## 0. The answer in eight lines

1. **A recalibrated operating point exists, but the separation is a thin band, not a gap.** The
   recommended M1c candidate is **`MMPS=90`, `TICKS=2`** (window stays 60 — it never binds):
   on the controls it fires on **4/5 B1 walks with 0/45 ok false fires** (vs the shipped 60/3's
   3/45 ok fires) — the 4/5 ceiling with zero ok fires (the run-length route 60/8-10 also reaches
   it, but on a one-sample margin).
2. **The ceiling is 4/5 B1 (4/8 no-grasp) by any rate rule**: the B1 `s11/14` never walks inside
   the monitored window (hold max 9.0, probe1 max 37.3 mm/s), and the B2 (never-held) class is
   quiet there (only `s11/3` shows a 2-sample spike).
3. **The usable threshold window is (81.5, 94.1] mm/s** for a 2-sample rule: the ok class's worst
   2-sample sustained rate is **81.5** (`s23/11`: a 130.7/81.5 pair) and the weakest walked B1's is
   **94.1** (`s23/3`: a 96/94 pair). 90 sits inside it with a 10 % margin below and 4.5 % above.
4. **The shipped 60 mm/s sits inside the ok transient band**: the ok per-tick (probe-1) max is
   **130.7 mm/s** and its 2-sample sustained max is 81.5, both above 60; the shipped rule's ok
   fires are 3/45 (6.7 %, trace resolution) to 5/45 (11 %, the optimistic hold-alignment bound).
5. **The 3 "oks" the M1 run fired on are not all false positives**: `s11/2` (left orange) is the
   *same physical attempt* as the control's `s11/1` B1 walk — its first nine hold samples are
   identical (9.4 … 130.5 mm/s) and the runs diverge exactly at the gate's trigger (trig@19);
   in the control it is a no-grasp failure, in the gate-ON run it placed. The unbiased FP basis is
   the control corpora's, not the gate-ON run's.
6. **The walk is a sustained slide, the ok fire is a jitter**: every ok fire sits on a flat drift
   (the payload oscillates, 4-27 mm, without walking), every B1 fire sits on a growing drift; the
   ok's longest over-60 stretch is 7 samples, the B1 walks run 11-75 samples with the drift
   growing to 25-166 mm by the end of probe-1.
7. **The window (60 mm) never binds** at any candidate rule (0/60 attempts changed): the triggers
   happen at 4.8-23.3 mm of drift, so the window stays as a safety, not as a tuning knob.
8. **Max-recall variant** if a 1-FP budget is acceptable: `MMPS=80`, `TICKS=2` → 5/8 no-grasp
   (4/5 B1 + 1/3 B2) at 1/45 ok FP. The run-length route (`60 mm/s`, 8-10 samples) also gives
   0/45 FP but with a knife-edge margin (the ok's worst stretch is exactly 7 samples).

---

## 1. Method

### 1.1 The corpora

| corpus | runs | traces | attempts | labels |
| --- | --- | --- | --- | --- |
| **controls** (P14-B, unbiased) | `logs/p14b/{10_seed11,11_seed5,12_seed23}_trace.log` | `traces_s11/s5/s23` | 60 | ok 45 / carried 7 / **B1 5 / B2 3** (the P14-B rule, `trace_p14b_analysis.py:369`) |
| **gate-ON** (Stage-P, branch-shifted) | `logs/p17i/{50,52,54}_seed*_slide.log` | `traces_p_s11/s5/s23` | 60 | ok 37 / carried 13 / **no-grasp 10** (the `[run]`/`[biarm]` rows) |

`logs/p17i/traces_m1` **is** `logs/p17i/traces_p_s11`: all 20 files byte-identical, combined
md5 `9a5ab829b9ceb075e43fa5f1143d5325` both, and the two logs' `[fruit]` streams are identical
modulo the `[slide]` rows — the M1 screen run *is* the Stage-P seed-11 primary.

The controls are the unbiased sample (the gate-ON branch is shifted by the gate's own responses,
and by the two-line scheduler's shared-tick coupling — the first divergence between the seed-11
control and the gate-ON run is the *right* arm's attempt-0 regrasp gap, 51.9 vs 65.3 mm, i.e.
after the left arm's first response).  All separability numbers below are on the controls.

### 1.2 The rate recipe (the gate's own) and the recomputation

`_slide_gate_observe` computes, every tick:

```
rel_world(t) = fruit(t) − pads(t)                  [world frame, m]
rate(t)      = |rel_world(t) − rel_world(t−1)| / CONTROL_DT       [mm/s]
drift(t)     = |rot(t)ᵀ·rel_world(t) − ref|       ref = the phase span's first sample  [mm]
```

On this asset the OpenArm hand's `pad_centre()` *is* `arm.jaw_centre()`
(`kinematic_gripper.OpenArmHand`), and the trace's `jaw` field is the same
`(jaw_left + jaw_right)/2` from `arm.jaw_positions()` — so the trace reproduces the gate's
`rel_world` exactly, and its `hand_rel` field is the gate's `rel_frame`.  The mission's
hand-frame variant `|hand_rel(t) − hand_rel(t−1)| / dt` is computed as a sensitivity column.

**Sampling.** The trace samples `hold` every **2 ticks** (24 rows / 48 ticks) and the first
`takeoff_probe` block (`probe1`) every **tick** (60 rows / 60 ticks, matching the gate's
`ticks=60`).  The hold's 2-tick sampling is a resolution limit carried through the whole
analysis: it can only *understate* the gate's hold-phase peaks.

### 1.3 The validation (the recomputation vs the gate's own `[slide]` rows)

Per gate-ON attempt/phase, my recomputed max rate and drift vs the gate's `rate_max`/`drift_max`:

| phase | n | trace/gate rate ratio (median, min, max) | trace/gate drift ratio (median) |
| --- | --- | --- | --- |
| `probe1` (per-tick) | 60 | **0.992** (0.562, 2.065) | **1.000** |
| `hold` (2-tick) | 60 | **0.838** (0.355, 1.243) | 0.990 |

The `probe1` phase reproduces the gate sample-for-sample (the few ratios > 1 are sub-3 mm/s
rounding noise: the trace rounds positions to 0.01 mm).  The hold's 0.838 is the 2-tick
smoothing of the per-tick peak.

**The trace detector vs the gate's actual fire decisions** (the gate-ON corpus, 12 actual fires
from the `[slide]` response rows):

| rule | gate fires | trace fires | agree | missed by trace | trace-only |
| --- | --- | --- | --- | --- | --- |
| (60, 3, 60) | 12 | 11 | 11 | 1 (`s11/16`, an ok hold fire) | 0 |
| (80, 2, 60) | 12 | 9 | 9 | 3 | 0 |
| (90, 2, 60) | 12 | 8 | 8 | 4 | 0 |

The trace detector at the shipped rule reproduces 11/12 of the gate's real fires with zero
extras; its single miss is an ok hold spike the 2-tick sampling smoothed below 60.  So the
trace-level **ok-FP count is a lower bound** on the gate's — the direction that argues for a
*higher* threshold, which is what the search below finds.

---

## 2. The distributions (controls, hold + probe-1)

### 2.1 Per-tick rate

| class | n | att-max p50 | att-max p90 | att-max max | sample p50 | sample p90 | sample p99 | sample max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ok | 45 | 22.5 | 62.4 | **130.7** | 3.7 | 18.4 | **54.5** | 130.7 |
| carried | 7 | 37.1 | 160.3 | 254.1 | 6.7 | 47.4 | 127.4 | 254.1 |
| **B1** | 5 | **226.0** | 310.2 | **310.2** | 53.3 | 217.9 | 286.0 | 310.2 |
| B2 | 3 | 60.6 | 83.6 | 83.6 | 1.7 | 29.1 | 59.6 | 83.6 |

**The raw per-tick distributions overlap**: the ok's *sample* p99 (54.5) sits at the B1's p50
(53.3), and the ok's max (130.7) is above the B2's max and inside the B1's band.  On this axis
alone there is no separation.

### 2.2 Per phase (per-attempt max)

| class | n | hold p50 | hold p90 | hold max | probe1 p50 | probe1 p90 | probe1 max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ok | 45 | 14.0 | 42.8 | **65.3** | 14.8 | 52.3 | **130.7** |
| carried | 7 | 33.4 | 35.4 | 37.1 | 15.0 | 160.3 | 254.1 |
| B1 | 5 | **197.5** | 310.2 | 310.2 | 226.0 | 290.1 | 290.1 |
| B2 | 3 | 8.1 | 9.7 | 9.7 | 60.6 | 83.6 | 83.6 |

The hold is the cleaner phase for the *walked* B1s (197.5-310.2 mm/s on the 2-tick samples vs the
ok's max 65.3), but two of the five B1s never walk in the hold either (`s23/3` 7.4, `s11/14` 9.0),
and the gate's design window is hold **+** probe-1, so the joint read is what matters.

### 2.3 The sustained rate (the resolution-robust statistic)

The highest rate a run of ≥ L consecutive samples holds, per attempt:

| class | L=2 p50 / max | L=3 p50 / max | L=5 p50 / max | L=10 p50 / max |
| --- | --- | --- | --- | --- |
| ok | 16.5 / **81.5** | 13.5 / 71.3 | 10.8 / 69.5 | 7.0 / **59.7** |
| carried | 32.2 / 210.1 | 30.8 / 157.1 | 28.5 / 106.2 | 25.0 / 83.5 |
| **B1** | 207.8 / 287.6 | 191.0 / 286.0 | 109.7 / 279.5 | 105.7 / 267.3 |
| B2 | 58.9 / 80.9 | 14.1 / 58.3 | 5.9 / 58.0 | 5.6 / 46.6 |

**This is where the separation lives.**  At L=10 no ok attempt sustains 60 mm/s (max 59.7) while
three B1s sustain 105-267; at L=2 the ok tops out at 81.5 vs the B1s' 94-288.  The ok's
over-threshold stretches are **short** (≤ 7 samples) and sit on a **flat drift**; the B1 walks
are **long** (11-75 samples) with the drift growing monotonically.

### 2.4 The max sustained run above candidate thresholds (median per class, samples)

| class | phase | ≥40 | ≥60 | ≥80 | ≥100 | ≥120 | ≥150 | ≥200 | ≥250 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ok | hold | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| ok | probe1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| carried | probe1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| **B1** | hold | **17.0** | **10.0** | **6.0** | **5.0** | 3.0 | 3.0 | 0.0 | 0.0 |
| **B1** | probe1 | **36.0** | **11.0** | **8.0** | 4.0 | 4.0 | 2.0 | 1.0 | 0.0 |
| B2 | probe1 | 2.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

and the class **maxima** of the same statistic (the worst case each class reaches):

| class | ≥40 | ≥60 | ≥80 | ≥100 | ≥120 | ≥150 |
| --- | --- | --- | --- | --- | --- | --- |
| ok | 38 | **7** | 2 | 1 | 1 | 0 |
| carried | 29 | 13 | 11 | 5 | 4 | 3 |
| **B1** | 78 | **75** | **74** | **65** | **65** | **55** |
| B2 | 10 | 2 | 2 | 0 | 0 | 0 |

The ok class's worst case is a **38-sample drag at ≥ 40 mm/s** (a slow pull that never reaches
60) and a **7-sample stretch at ≥ 60**; the B1s hold 55-75 samples above 150.

**The key answer: 3/45 ok attempts (6.7 %) have a ≥3-sample run above 60 mm/s** — `s11/20`
(lychee, 7 samples at 63-74), `s23/11` (orange, a 130.7/81.5 pair), `s5/16` (apple, an 85/60/63
spike).  At the optimistic hold-alignment bound the count rises to 5/45 (11 %) by adding two
single-hold-sample fires (`s11/11`, `s11/15`).  **The shipped 60 mm/s does sit inside the ok
per-tick transient range.**

### 2.5 What the fires look like (the mechanism read)

| attempt | class | max rate | the over-threshold stretch | drift over the stretch |
| --- | --- | --- | --- | --- |
| `s11/20` | ok (lychee) | 74.4 | 7 samples at 63-74 in probe-1 | 22 → 27 mm, **flat** |
| `s23/11` | ok (orange) | 130.7 | 2 samples (130.7, 81.5) | 11 mm, **flat** |
| `s5/16` | ok (apple) | 85.4 | 3 samples (85, 60, 63) | 4 → 5 mm, **flat** |
| `s11/1` | B1 (orange) | 310.2 | 17 samples ≥ 60 in the hold | 48 → 52 mm, growing |
| `s11/7` | B1 (tomato) | 226.0 | 70 samples ≥ 60 | 56 → 100 mm |
| `s11/9` | B1 (orange) | 290.1 | 75 samples ≥ 60 | 98 → 166 mm |
| `s23/3` | B1 (strawberry) | 96.1 | a 96/94 spike then 8 samples at 60-71 | 4 → 23 mm |
| `s11/14` | B1 (tomato) | **37.3** | — (no walk in the window) | 6.6 mm |

Every ok fire is a **jitter** (the payload oscillates at 60-130 mm/s without net displacement);
every B1 fire is a **walk** (the drift grows monotonically).  `s11/14`'s loss happens outside the
monitored window — no rate rule can reach it.

---

## 3. The separability search (controls)

### 3.1 The search space

420 triples (thr 40-300 × ticks 1-8 × window 40/60/80/100/off) on the span-level detector, plus
the phase-aware evaluation with both hold-alignment bounds (`hold_weight=2` = a 2-tick hold
sample counts 2 ticks, the trigger-happy bound; `hold_weight=1` = the conservative bound).
**320 of 420 triples satisfy "≤ 1 FP on ok"** — the criterion is not selective; the interesting
question is what recall the FP-free ones keep.

### 3.2 The candidate table (controls; fires = ≥1 response on the attempt)

| rule (mm/s, samples) | ok FP | B1 | B2 | carried | no-grasp | fires in hold / probe1 |
| --- | --- | --- | --- | --- | --- | --- |
| **60, 3 (shipped)** | **3/45** (5/45 at hw=2) | 4/5 | 0/3 | 3/7 | 4/8 | 3 / 7 |
| 80, 2 | 1/45 | 4/5 | 1/3 | 2/7 | 5/8 | 3 / 5 |
| **90, 2** | **0/45** | **4/5** | 0/3 | 2/7 | 4/8 | 3 / 3 |
| 60, 8 | 0/45 | 4/5 | 0/3 | 2/7 | 4/8 | 3 / 3 |
| 60, 10 | 0/45 | 4/5 | 0/3 | 1/7 | 4/8 | 3 / 3 |
| 80, 4 | 0/45 | 3/5 | 0/3 | 2/7 | 3/8 | 3 / 2 |
| 100, 3 | 0/45 | 3/5 | 0/3 | 2/7 | 3/8 | 3 / 2 |

Per-seed at (90, 2): s11 ok 0/11, B1 3/4; s5 ok 0/17; s23 ok 0/17, B1 1/1 — no seed carries a
false fire.

### 3.3 The threshold margin (the usable window)

The ok's 2-sample sustained boundary and the B1 ladder:

| thr | ok FP (a 2-sample run) | B1 caught | B2 caught |
| --- | --- | --- | --- |
| ≤ 81 | 1/45 | 4/5 | 1/3 |
| **82-94** | **0/45** | **4/5** | 0/3 |
| 95-207 | 0/45 | 3/5 | 0/3 |
| 208-224 | 0/45 | 2/5 | 0/3 |
| 225-287 | 0/45 | 1/5 | 0/3 |
| > 287 | 0/45 | 0/5 | 0/3 |

The ok's worst 2-sample pair is 81.5 (`s23/11`) and the weakest walked B1's is 94.1 (`s23/3`),
so **the usable threshold window is (81.5, 94.1] mm/s** for a 2-sample rule.  The run-length route
(keeping 60 mm/s, raising the ticks) works only because `s23/3` also drags at 60-71 for a further
8 samples — but the ok's worst stretch is exactly 7 samples, so that route sits on a
one-sample margin.

### 3.4 The confusion matrix of the recommendation (controls)

**(90 mm/s, 2 samples, window 60 mm):**

| | fired | not fired |
| --- | --- | --- |
| **B1 (target)** | **4** (`s11/1`, `s11/7`, `s11/9`, `s23/3`) | 1 (`s11/14` — no in-window walk) |
| B2 | 0 | 3 |
| carried | 2 (`s11/6`, `s11/12`) | 5 |
| **ok** | **0** | **45** |

Same matrix at the trigger-happy hold bound (`hold_weight=2`) — the recommendation is robust to
the hold's 2-tick sampling ambiguity.

**The max-recall variant (80 mm/s, 2 samples, window 60 mm):** fires on the 4 B1s plus the B2
`s11/3` (a 2-sample spike at 83.6/80.9, drift flat at 1.4 mm) and on **1/45 ok** (`s23/11`).

### 3.5 What a higher threshold would still catch (the fail-side ladder)

The B1 walks' 2-sample sustained rates are 287.6, 224.5, 207.8, 94.1 and 27.2, so the fail-side
ladder is exact: **thr ≤ 27 → 5/5; 27 < thr ≤ 94 → 4/5; 94 < thr ≤ 208 → 3/5;
208 < thr ≤ 224 → 2/5; 224 < thr ≤ 288 → 1/5; > 288 → 0/5.**  The B2s: only `s11/3` (80.9) is
reachable at thr ≤ 81; the other two never exceed 61 in the window.  **No threshold catches all
the no-grasp failures** — the class's losses are not all walks.

---

## 4. The gate-ON corpus (branch-shifted) and the M1 read

**The gate's own 12 fires** (from the `[slide]` rows; the gate-ON corpus's `seed/k` numbering,
which differs from the controls' after the branch shift): 3 ok, 3 carried, 6 no-grasp —
`s11/2` ok, `s11/6` no-grasp, `s11/7` carried, `s11/13` ok, `s11/14` no-grasp, `s11/16` ok,
`s11/19` no-grasp, `s5/16` no-grasp, `s23/1` carried, `s23/3` no-grasp, `s23/11` carried,
`s23/13` no-grasp.

**One of the three s11 ok fires is a converted would-be B1.**  The control's seed-11 left
attempt 1 (orange) is a no-grasp failure whose payload walks at up to 310 mm/s through the hold
(the `s11/1` B1); the gate-ON run's left attempt 1 is the *same physical attempt* — its first
nine hold samples are identical (9.4, 13.3, 19.8, 32.2, 64.7, 46.6, 65.9, 90.3, 130.5 mm/s) and
they diverge exactly at the gate's trigger (`trig@19 rate=114.2mm/s`) — and it **placed**
(lift +0.304, `[slide] ... events=2`, post-response rates 19.5/57.9 mm/s).  The Oracle's "fired
on 3 oks" therefore overstates the false-positive rate: at least one was a true catch.  The
unbiased FP basis is the controls' 3/45 (6.7 %) at the shipped rule.

The gate-ON corpus's own ok fires (2/37 trace-level, 3/37 actual) are consistent with the
controls' rate (6.7 %); the branch shift makes them a secondary read, not the primary one.

---

## 5. The verdict

**(a) A recalibrated operating point exists.**  It is a chosen point on a continuous trade, not a
clean gap: the ok class's transient band reaches 81.5 mm/s (2-sample sustained) / 130.7 (single
sample), and the weakest walked B1 sits at 94.1.

**Recommended M1c screen candidate:**

```
FRUIT_DYNAMIC_SLIDE_GATE_MMPS=90      # was 60
FRUIT_DYNAMIC_SLIDE_GATE_TICKS=2      # was 3
FRUIT_DYNAMIC_SLIDE_GATE_WINDOW_MM=60 # unchanged; never binds
```

Expected effect on the control corpora (60 attempts):

* fires on **4 of the 5 B1 walks** (`s11/1`, `s11/7`, `s11/9` in the hold at 197-310 mm/s;
  `s23/3` in probe-1) — the maximum any rate rule can reach;
* **0 of the 45 ok attempts** (at both hold-alignment bounds) — vs the shipped rule's 3/45
  (6.7 %, trace resolution) to 5/45 (11 %);
* 2 of the 7 carried attempts (both probe-1 fires; a bonus, they are failures anyway);
* drops the shipped rule's three ok fires (`s11/20`, `s23/11`, `s5/16`) and its `s23/1` carried
  fire while losing no B1.

**Max-recall variant** (if a 1-FP budget is acceptable): `MMPS=80`, `TICKS=2` → 5/8 no-grasp
(4/5 B1 + 1/3 B2) at 1/45 ok FP.  **Run-length alternative**: `MMPS=60`, `TICKS=8-10` → same
confusion as the recommendation but with a one-sample margin on both sides (the ok's worst
stretch is 7 samples, `s23/3`'s catch needs exactly 8) — not recommended as the primary.

**Named residuals and the honest limits.**

* The B1 `s11/14` is **unreachable** by any rate rule (its walk is outside the monitored window);
  the B2 class is mostly walk-free in the window.  So the trigger's recall ceiling on this
  scenario is 4/5 B1 = 4/8 no-grasp.
* The controls give **45 oks and 5 B1s**: the FP ≤ 1 criterion is satisfied by 320/420 triples,
  and the difference between 3 FP (shipped) and 0-1 FP (recommended) is a 2-3 attempt movement —
  quote it as the direction (the shipped threshold sits inside the ok band), not as a significance
  result.
* The hold is 2-tick sampled: the trace-level ok-FP count is a **lower bound** on the gate's
  (calibrated at 11/12 of the gate's real fires at the shipped rule, 1 ok hold spike missed).
  The recommendation's margins (10 % above the ok's worst sustained pair, 4.5 % below the weakest
  walked B1) should be read with that in mind.
* The branch-cascade effect (`logs/p17i/P_RESULTS.md` §3) still applies: any response re-shapes
  the remaining attempts, so a cleaner trigger is expected to remove the *mechanism-free* fires,
  not to scale the census movement proportionally.

---

## 6. Provenance and reproduction

```
python3 -B logs/p17c2/threshold_analysis.py > logs/p17c2/threshold_tables.txt   # parts 1, 3, 4
python3 -B logs/p17c2/phase_split.py        > logs/p17c2/phase_split_tables.txt # part 2 + margins
```

| artifact | contents |
| --- | --- |
| `logs/p17c2/threshold_analysis.py` | the corpora loading + pairing, the rate/drift recomputation, the validation vs the `[slide]` rows, the distributions, the separability search, the calibration, the per-attempt detail tables |
| `logs/p17c2/threshold_tables.txt` | its output (pairing checks, validation table, distributions, the shipped-rule confusion, the search, the calibration, the detail tables) |
| `logs/p17c2/phase_split.py` | the phase-aware read: per-phase distributions, the sustained-rate statistic, the candidate table at both hold bounds, the per-seed breakdown, the margin sweep, the fired-attempt census |
| `logs/p17c2/phase_split_tables.txt` | its output |
| `logs/p17c2/WORKLOG_entry.md` | the WORKLOG entry for this phase |

Inputs (read-only): `logs/p14b/{10_seed11,11_seed5,12_seed23}_trace.log` + `traces_s11/s5/s23`
(the P14-B control corpora, `logs/p14b/TRACE_RESULTS.md`); `logs/p17i/{50,52,54}_seed*_slide.log`
+ `traces_p_s11/s5/s23` and `logs/p17i/20_m1_trace.log` + `traces_m1` (the gate-ON corpora,
`logs/p17i/P_RESULTS.md`, `logs/p17i/ORACLE_GATE.md`); `src/fruit_sorting/tasks.py` (the gate
block) and `src/fruit_sorting/kinematic_gripper.py` (`OpenArmHand.pad_centre`).
