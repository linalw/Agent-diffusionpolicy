# P10-D LOCKON_ATTRIBUTION: why left +4.3 % / right +26 % on the P10-C treatment branch (Task B)

Status: Tier C, offline, **no simulator run** (the live batteries were not touched;
every number below is text parsing of the P10-C logs on disk). Written 2026-10-17
under `logs/p10d/`. Raw output: `logs/p10d/20_lockon_attribution.txt`.

Question (from the P10-C result, `logs/p10c/C_RESULTS.md` endpoint 6): the
carry-monitor fast-skip moved the pooled interval -8.8 % and the window rate
+9.6 %, but the **lock-on latency** (previous attempt end -> station acquired; the
186 report's per-arm metric) moved **left 3.73 -> 3.89 s (+4.3 %)** and
**right 5.27 -> 6.65 s (+26 %)**. Is that a mechanism cost of the fast-skip, or a
draw/phase artifact of the moved branch?

## 1. The metric and the decomposition

186's lock-on interval for attempt i is `acq_i - t1_{i-1}` (station acquired minus
the previous attempt's end). The interval's composition, from the two-line worker
(`_biarm_worker`):

```
lock = park (gate wait + go_ready transit) + feed gap (30 ticks = 0.25 s)
       + retries x 0.5 s + selection epsilon
```

* each starved poll ("no eligible fruit") is a 60-tick step loop = **exactly
  0.5 s** (measured: the acquisition stream during a burst is 0.5 s apart,
  e.g. 48.6 / 49.1 / 49.6 / 50.1 s);
* the park term is **measured exactly for A** from the P10-A diagnostic log
  (`logs/p10/30_diag_twoline.log`, `FRUIT_BIARM_PARK_TRACE=1`; its schedule is
  bit-identical to the P10-C A run modulo reporting rows - `logs/p10/44_compare_diag_vs_pair.txt`
  861/861 and `C_RESULTS.md` section 1). The trace gives `park wait start ->
  park moving -> park done` per park; matching each park to the interval that
  contains it reproduces the residual to 0.01-0.02 s (left: measured parks mean
  **2.47 s** vs residual mean **2.48 s**; right: measured **3.77 s** vs residual
  **3.79 s**) - the decomposition closes;
* for B (no park trace on that branch) the park term is implied:
  `park = lock - 0.25 - 0.5*retries`.

This is the brief's three terms with their measured names: the **wait/retry
term** (the starved polls per interval), the **park term** (the return transit
that follows the previous attempt's end - its start time moves with the skip,
its duration moves only via the gate/transit class), and the **draw term** (the
intervals themselves are a different set: the per-arm attempt split re-drew).

## 2. The per-interval tables

**A (control, monitor off), right arm** - `logs/p10c/10_armA_diag.log`:

| interval | t1_prev | acq | lock | retries | retry term | park+eps (measured park) |
| --- | --- | --- | --- | --- | --- | --- |
| 0->3 | 29.3 | 32.1 | 2.80 | 0 | 0.00 | 2.55 |
| 3->5 | 45.8 | 53.1 | 7.30 | 9 | 4.50 | 2.55 |
| 5->7 | 68.6 | 79.1 | 10.50 | 9 | 4.50 | **5.75** (gate wait) |
| 7->9 | 94.9 | 97.7 | 2.80 | 0 | 0.00 | 2.55 |
| 9->11 | 113.1 | 115.9 | 2.80 | 0 | 0.00 | 2.55 |
| 11->13 | 130.4 | 133.2 | 2.80 | 0 | 0.00 | 2.55 |
| 13->15 | 148.9 | 153.8 | 4.90 | 4 | 2.00 | 2.65 |
| 15->17 | 168.8 | 176.7 | 7.90 | 0 | 0.00 | **7.65** (gate wait) |
| 17->19 | 191.4 | 197.0 | 5.60 | 0 | 0.00 | **5.35** (gate wait) |
| mean | | | **5.27** | 22 | 1.22 | 3.79 |

**B (treatment, fast-skip), right arm** - `logs/p10c/20_armB_1.log` (the double
`21_armB_2.log` is bit-identical, table in `20_lockon_attribution.txt`):

| interval | t1_prev | acq | lock | retries | retry term | park+eps (implied) |
| --- | --- | --- | --- | --- | --- | --- |
| 0->3 | 29.3 | 32.1 | 2.80 | 0 | 0.00 | 2.55 |
| 3->5 | 48.6 | 54.3 | 5.70 | 0 | 0.00 | **5.45** |
| 5->7 | 68.1 | 79.3 | 11.20 | 9 | 4.50 | **6.45** |
| 7->9 | 96.1 | 98.8 | 2.70 | 0 | 0.00 | 2.45 |
| 9->12 | 113.7 | 119.8 | 6.10 | 7 | 3.50 | 2.35 |
| 12->14 | 132.0 | 142.5 | 10.50 | 9 | 4.50 | **5.75** |
| 14->16 | 158.1 | 169.5 | 11.40 | 8 | 4.00 | **7.15** |
| 16->18 | 184.8 | 187.6 | 2.80 | 0 | 0.00 | 2.55 |
| mean | | | **6.65** | 33 | 2.06 | 4.34 |

Left arm (both logs, full tables in the raw output): A n=9 mean **3.73 s**
(retry term 1.00, residual 2.48 - all residuals 2.35-2.65); B n=10 mean
**3.89 s** (retry term 0.85, residual 2.79 - two elevated: **4.95** on 1->2 and
**3.05** on 11->13).

## 3. The attribution of the deltas

| arm | lock-on | retry/wait term | park+eps term | retry share |
| --- | --- | --- | --- | --- |
| **right** | 5.27 -> 6.65 (**+1.38 s, +26.3 %**) | 1.22 -> 2.06 (**+0.84 s**; retries/interval 2.44 -> 4.12) | 3.79 -> 4.34 (**+0.54 s**) | **61 %** |
| **left** | 3.73 -> 3.89 (**+0.16 s, +4.2 %**) | 1.00 -> 0.85 (**-0.15 s**; 2.00 -> 1.70) | 2.48 -> 2.79 (**+0.31 s**) | n/a (negative) |

**Right arm.** The retry term carries 61 % of the +26 %: the right's starved
polls went 22 -> 33, concentrated in four intervals (9/7/9/8 retries) against
A's three (9/9/4). The park+eps term carries the remaining 39 %, and its
composition re-drew rather than its class changing: A has 3 gate-wait parks of 9
intervals (5.75/7.65/5.35 s residuals), B has 4 of 8 (5.45/6.45/5.75/7.15) -
the clean transit class is identical in both (2.35-2.65 s).

**Left arm.** The retry term fell slightly (-0.15 s) and the park term rose
(+0.31 s); the rise is two elevated parks, and both sit **immediately after a
skipped attempt** (1->2 follows the 9.0 s tomato skip; 11->13 follows the 8.9 s
tomato skip) - while the third skip (slot 4) parks clean (2.25 s). So a
post-skip park-transit channel (the arm is left at a mid-lift pose when the
monitor fires) is *possible* but **not established** on this sample, and B has no
park trace to separate "longer transit" from "gate wait" (`FRUIT_BIARM_PARK_TRACE=1`
on a B run is the named instrument if this sub-channel is ever pursued).

## 4. The draw evidence (why the retry term moved at all)

* The per-arm split re-drew: A left 10 attempts / right 10 -> B left 11 /
  right 9 (`[run]` tables), and the placements moved 4/8 -> 8/5 - the W7-C
  "compare per-arm classes, not per-arm rates" caveat.
* The starvation bursts are at different phases: B's right adds bursts at
  116.3-119.3, 138.0-142.0 and 165.5-169.0 s that A does not have (A's burst at
  74.6-78.6 s is shared). A starvation burst is the arm waiting for the next
  B-lane fruit to enter its window; which polls land in empty phases is set by
  the arm's schedule, which the fast-skip moved (the paired tomato attempt
  14.94 -> 8.94 s is the anchor event).
* The **seed controls** (P10-C.1, `logs/p10c/50..53`, 186-verified counts):

| run | left lock (retries) | right lock (retries) |
| --- | --- | --- |
| seed 5 A | 3.73 (18) | 5.27 (22) |
| seed 5 B | 3.89 (17) | **6.65 (33)** |
| seed 11 A | 4.97 (33) | 6.93 (7) |
| seed 11 B | 4.69 (24) | **5.51 (22)** |
| seed 23 A | 3.39 (12) | 3.99 (0) |
| seed 23 B | 3.71 (18) | 3.86 (0) |

At seed 11 the right's lock-on **falls** 6.93 -> 5.51 (-20 %) while its retries
rise 7 -> 22 - the opposite direction to seed 5, with the same lever. At seed 23
the lever is inert on the right (0 retries on both arms' right intervals; lock
3.99 -> 3.86). The starved-poll split across A runs is (19,22) / (35,7) / (13,0)
for seeds 5/11/23: the starvation itself is a per-seed draw, and the lock-on
follows it.

## 5. Verdict

**The right-arm +26 % is dominated by a draw/phase artifact of the moved branch,
not a mechanism cost of the fast-skip.** Evidence: (1) 61 % of it is the
retry/wait term - the arm's polls landing in empty phases of the *same* B-lane
supply stream, which the skip's schedule shift re-phased; (2) the remaining 39 %
is the park/gate-wait class re-drawing its composition (4 long parks vs 3), with
the clean transit class identical (2.35-2.65 s) and no gate-logic change (the
monitor does not touch the park predicate or the selection); (3) the direction
does not reproduce - at seed 11 the same lever moves the right's lock-on
**down** 20 % while the retries rise, and at seed 23 the lever is inert on the
right's lock-on (0 retries on both branches). The left-arm +4.3 % is park-term
and *consistent with* a small post-skip park-transit channel, but the sample is
2 elevated parks out of 3 skips and it is unmeasured without a B park trace -
recorded as an open sub-channel, not a claim.

**Practical reading.** The lock-on rise is the same freed time the interval gain
came from, re-labelled by the metric: the skip ends a doomed attempt early, the
arm then waits (starved polls) at a phase of the lane that is empty, and the
metric counts that wait. It is *reported, not gated* (the Oracle's B2/B3
demotion, `C_RESULTS.md` endpoint 6), and it must be quoted per branch/per seed,
never as a lever signature. The honest lever readout stays the pooled interval
(-8.8 % at seed 5) with its own multi-seed confirmation, and the starved-poll
count with the phase-coupling caveat (see `SELECTION_REPLAY.md` section 4).

## 6. Provenance

```bash
python3 logs/p10d/lockon_attribution.py > logs/p10d/20_lockon_attribution.txt
python3 scripts/186_w6_report.py --label p10d-A-vs-B \
    logs/p10c/10_armA_diag.log logs/p10c/20_armB_1.log logs/p10c/21_armB_2.log \
    > logs/p10d/00_186_A_B.txt          # cross-check: counts/means match exactly
python3 scripts/186_w6_report.py --label seeds \
    logs/p10c/50_seed11_A.log logs/p10c/51_seed11_B.log \
    logs/p10c/52_seed23_A.log logs/p10c/53_seed23_B.log \
    > logs/p10d/01_186_seeds.txt
```

Inputs: the P10-C logs above; `logs/p10/30_diag_twoline.log` (A park trace,
bit-identical schedule, `logs/p10/44_compare_diag_vs_pair.txt`). Tree pins as in
`C_RESULTS.md` (`tasks.py` 09c920c9...). No `src/` or `scripts/` file was
modified; the only writes are under `logs/p10d/`.

Caveats: (1) one deterministic branch per configuration - the seed table is the
sampling discipline, not a rate; (2) B's park term is implied, not measured (no
park trace on the B branch); (3) log resolution 0.1 s on the timestamps; the
0.5 s retry quantum and the 0.25 s feed are exact tick counts (60 / 30 ticks at
120 Hz); (4) the seeds chain finished 17:50:05, so all six seed logs are in the
tables.
