# P7-1 L1: C-3 carry monitor - Phase-0 offline replay results

Lane P7-1 L1, Tier C offline, 2026-10-16. Inputs: `docs/papers/MECHANISMS.md`
item 1; `logs/p6/SYNTHESIS.md` section 2 item 1 + section 4 item (1); the
source lane's monitor card `logs/p6/B3b_reread.md` card 11 (M-0, Sentinel-VLA
#66); `logs/w8/B_RESULTS.md` + `logs/w8/B_metric.py`; `AGENTS.md` section 2.
Protocol frozen first in `logs/p7/PREREG_CARRY_MONITOR.md` (md5
`5b31b3c3315572c4bce56d9319a1151b`); executed by the one new offline script
`scripts/203_c3_monitor_replay.py` (md5 `a4d906958ff43b75df61d1eb8b0947e4`,
read-only, writes nothing, deterministic, ~3 min). No simulator, no `src/`
change, no commit.

**Reproduce:** `python3 scripts/203_c3_monitor_replay.py` from the repo root.

## Verdict: **GO to the live phase**

The pre-registered Phase-0 gate **PASSES** on both items:

| gate item | bar | measured | verdict |
| --- | --- | --- | --- |
| Sentinel critical-state F1 (Normal excluded) | macro-F1 >= 0.86 | **0.969** | PASS |
| FP on the 33 clean legs (denominator fixed in the pre-reg) | <= 2 | **2** (6.1 %) | PASS at the cap |

Leg-level, leave-one-trace-out (54 folds; 89 legs = 33 clean / 31 escape / 25
no-contact / 0 jitter - the corpus invariant matched the pre-registration
exactly, so the frozen denominators stand): **TP=31, FP=2, FN=0, TN=31**;
escape P=0.939 R=1.000 F1=0.969; clean P=1.000 R=0.939 F1=0.969. The corpus
reproduced the W8-B class split exactly (33/31/25/0).

The two FPs are the **two legs of one clean attempt** (`logs/w8/B_traces_mech/
trace_10_right_direct_ok.json`), so at the live action granularity (an attempt
is skipped iff any of its legs fires) the replay reads **28/28 escape attempts
detected, 1 false skip of 20 clean attempts**. The four-corpus breakdown:
`w7` 9 clean/3 escape perfect, `w5` scripted 16/1 perfect, `w8 run1` 5/11
perfect, `w8 mech` 3 clean/16 escape with the 2 FPs (F1e 0.941, F1c 0.500).

Secondary per-state (tick-level) readout, reported not gated: seated ticks
P=0.940 R=0.923, escaping ticks P=0.747 R=0.796, macro-F1 0.851 - below the
leg-level figure because the monitor fires early on escape legs (see failure
modes); the clean-leg tick hot fraction is 411/7212 = 5.7 %, **all of it from
the two FP legs**.

## 1. What was measured (the frozen protocol, one pass)

Six online-only features per tick (`sep`, `sep - gap_cmd`, `dsep/dt`,
`min(ft)`, `sum(ft)`, `contacts`); per-tick labels from the W8-B `clean_slip`
(> 2.0 mm), which is label-side only; logistic regression (standardized,
zero-init, full-batch GD lr 0.5, 3000 steps, L2 1e-3; final mean loss 0.132,
max|grad| 1.4e-4); leave-one-trace-out CV; threshold 0.5 with a 2-tick
persistence. One run, no rescue. One corpus file (`w8 run1/trace_14`) has no
carry leg of >= 2 rows, so the CV has 54 folds over 55 trace files - a
mechanical detail, not a protocol change.

**Detection latency (31/31 escape legs detected).** Of the 26 with a
contact-loss row: **24 fired before loss, 2 at loss, 0 after**; fire-loss
median **-27 ticks** (-138..0). Fire-onset median -1 tick (-129..+81). The
fire leaves a median **70 ticks (~0.58 s)** of the fired leg; on the 3 escape
*place* legs (a lift loss's aftermath) the remain is 270-373 ticks. The
fast-skip therefore has material to reclaim on every detected escape, and it
never fires after the loss has already happened.

## 2. The features that carried the signal

* **The tactile state carries the signal.** Standardized coefficients (mean
  over folds): `contacts` **-3.06** (sd 0.10), `force` **+1.59** (0.12),
  `ft_min` **-1.07** (0.08), `pry` **-0.71** (0.07), `sep` +0.11 (0.04),
  `vsep` **-0.03** (0.004). Group probes (attribution extension, non-gating):
  **tactile-only (drop the 3 geometry channels) = the full model** (macro
  0.969, FP 2, recall 1.000); **geometry-only (drop the tactile 3) degrades**
  (macro 0.875, FP **3** - it fails the FP cap - recall 0.839). So the
  jaw-geometry side cannot meet the gate on its own.
* **Drop-one ablations are all identical** (every single-feature drop
  reproduces macro 0.969 / FP 2): no one channel is load-bearing - the state
  is redundant across `force`/`contacts`/`ft_min`.
* **`vsep` (jaw velocity) added nothing** on this corpus (coefficient ~0,
  zero ablation effect) - keep it in the live state only as a free channel.
* **`pry`/`sep` are boundary refinement, not the separator**: no single
  ablation changes any decision (all six drop-one runs are identical); their
  coefficients only reflect how the fitted line shaves the one boundary case
  (section 3).
* **The trivial rule is weaker but clean**: "loaded seen, then `contacts == 0`
  or `force < 0.5`" (persistence 2) reads TP=26 FP=0 FN=5, macro 0.921. Its 5
  misses are **exactly the 5 no-contact-loss escapes** (the 17.9-25.4 mm
  partial slides with `cmin=1`) - that incremental 5 is what the fitted model
  buys with its 2 FPs, via the one-sided/prying state.

## 3. Failure modes of the classifier

1. **One-sided low-force clean holds are the boundary class.** Both FPs are
   one clean attempt (`trace_10`) held on a single finger for the whole carry
   (`ft_min = 0`, `contacts = 1`, force 1.9-2.6 N, `pry` ~+29 mm constant).
   In the all-data fit these two legs peak at z ~ -0.3 (just below the line),
   the next-closest clean leg peaks at -1.51 (all others <= -2.08), and the
   nearest one-sided *escape* is at z ~ +0.8 on its first tick; the fold models
   cross the line on exactly these two legs. The corpus contains only these
   two one-sided clean legs (one attempt), so the classifier cannot learn
   "one-sided but seated" robustly - the FP margin is thin by construction.
2. **The partial-slide class is only reachable through the grip-quality
   proxy.** The 5 escapes that never lose contact are detected via the
   one-sided/prying state, not via a loss event; this is the same channel that
   produces failure mode 1, so the two are coupled (the model trades 5 FN for
   2 FP against the trivial rule).
3. **Early fires on escape legs.** 7 of the 31 escapes fire at tick 0 (some
   with the 2 mm crossing 100+ ticks later) because they are one-sided from
   the start - class-correct (the legs are escape legs), but the fire time
   carries no slip information; the tick-level F1 (0.851) is the honest read
   of that.
4. **No-contact legs fire trivially (25/25).** Excluded from the gate as the
   Normal analogue; the live monitor must keep a loaded-contact gate (the
   guard's `min_contacts > 0` form) so it cannot act on a never-held payload.
5. **The corpus is small and scenario-bound** (54 traces, one supply/scenario
   family); the CV is the only generalization evidence available, and the
   `w8 mech` corpus has only 3 clean legs, 2 of which are the trace_10 FPs -
   its per-corpus F1c (0.500) is a small-sample artifact, quoted only to show
   where the FPs live.

**JCAC is not triggered.** The pre-registered second signal (JCAC's conformal
action-space risk, `logs/p6/B1_reread.md` section 1(e)) stays named but **not
built**: the proprio-only monitor cleared the Sentinel-class bar and the FP
cap. If the live phase (K2) falsifies on one-sided clean holds, the recorded
next step is that head, not a re-tune of this classifier.

## 4. What the live battery must watch (P7-2)

* **K2, the FP route.** <= 2 monitor-triggered aborts of would-be placements
  per N=5 battery (75 attempts); the replay analogue is 1 attempt-level false
  skip per 20 clean attempts. The watch class is exactly the one-sided
  low-force clean hold (`ft_min = 0`, `contacts = 1`, force < ~2.6 N, large
  `pry`): count it from the `[carry]` lines on both arms.
* **The loaded-contact gate.** No-contact legs fire trivially; the live
  monitor must require a seen-loaded state before any "not seated" decision.
* **The interval endpoint, per the source lane's split.** B's primary is the
  span on the A-failed-attempt set (the re-seat is B''s route only); watch the
  fast-skip timing (fire -> leg boundary) and the `[carry]` line's
  `clean_slip_max` per fired leg so an abort is classifiable as TP/FP.
* **The usual kill set** (frozen in the pre-reg): any new failure reason,
  cycle <= +5 %, lock-on <= +5 %, acceptance 9/10 + `fingerprint: matches`,
  two-line dense 442/442 + `190` PASS, selfcheck PASS, monitor trace-only.
* **Branch caveat**: the arms draw different fruit after the first
  divergence; quote class counts and intervals, not cross-configuration rate
  deltas (AGENTS section 2).

## 5. Provenance

* Pre-registration: `logs/p7/PREREG_CARRY_MONITOR.md` (written before any
  fitting). Results: this file. Script:
  `scripts/203_c3_monitor_replay.py`.
* Corpora (unchanged, read-only): `logs/w7/B_traces_mech`,
  `logs/w5/traces_dense`, `logs/w8/B_traces_mech`,
  `logs/w8/B_traces_mech_run1`; labels re-derived by `logs/w8/B_metric.py`
  (`53cbf99b...`).
* Tree note: the pre-reg's section-6 pins are the writing-time working tree
  (`tasks.py` `bcb1fb72...`); the parallel L3 lane subsequently edited
  `tasks.py`/`rl_env.py` in the working tree. This lane touched no `src/`
  file, and the live phase (P7-2) re-pins its own tree at battery time.
