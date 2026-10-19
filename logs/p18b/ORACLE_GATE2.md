# ORACLE GATE 2 — the P17-B closure verification and the P18 plan review

**Status.** Read-only gate (branch `p-supply`, HEAD `79825b1`, 2026-10-19). No simulator run by
this lane; no file written outside this one. Inputs read: `logs/p17i/` (`P_RESULTS.md`,
`SCREEN_RESULTS.md`, `60_stage_p_read.txt`, `71_k4_diff.txt`, `run_k4_replay.sh`,
`run_stage_p.sh`, `read_stage_p.py`, `ORACLE_GATE.md`, `IMPLEMENTATION.md`); the on-disk
battery/control logs (`logs/p17i/50..55_*`, `logs/p12a2/{10,11,12}_*_mass.log`,
`logs/p17i/70_k4_control_replay.log` + driver); `logs/p15/OUTCOME_RESULTS.md` (the
CORRECTION); `logs/p17/CAPTURE_LEVER_DESIGN.md`; `.slim/deepwork/sorting-pipeline-v3.md`
(the P18 PLAN, the P9 candidates, the WS-4.2 endpoint text); `logs/r11/` (the
pre-registration, `B_RESULTS.md`, `B_N/STOPPED.md`, `B_N_driver.log`);
`docs/papers/UPDATE_2026_10.md` §1/§3/§4; the running batteries: `logs/p18b/run_n5.sh` +
`90_driver.log` + `N5/A_1.log` + `N5/raw/A_1/**/manifest.json` (read while A run 1 finished
and B run 1 started), and the offline lane `logs/p17c2/threshold_analysis.py` +
`threshold_tables.txt`. The R11-B's old launch env is `logs/r11/B_N_driver.log` line 5; the
old run's manifest is `logs/r11/B_N/raw/{A_1,B_1}/direct_none_seed77/manifest.json`.

---

## 0. The answer in ten lines

1. **The P17-B closure is sound and the record reproduces.** I independently re-derived the
   control census (45/8/7 = 11/7/2 + 17/0/3 + 17/1/2), the gate census (37/10/13 =
   10/5/5 + 15/1/4 + 12/4/4), K3 (all three doubles identical on the `[trace]`-excluded
   `[fruit]` stream: 1016/1068/1067), and K4 (the current-tree knob-off replay is 950/950
   `[fruit]` lines vs `logs/p12a2/10_seed11_mass.log`, 0 diff lines, driver exit=0, tree
   `tasks.py` `3d88408d`). K2 fires on every letter. **The knob stays default-off.**
2. **Three record fixes, none verdict-changing**: the quoted falls "7 → 11 rows" includes one
   blow-up per side (the read's `falls()` counts ≤ −1000 mm including the −55 282/−52 107 mm
   rows); under the design's own F6 convention it is **6 → 10** (still a rise). The read's
   "N fired attempts" line is a unique-`(side, idx)` count, not attempts (s11 prints 5; the
   record's 7 is right). "The fourth instance" parenthetical omits P11-C.2. Two mandatory
   co-reports are collected but unreported: the interval and the per-leg motion budgets.
3. **Q2a — the fresh full battery is the right call** (tree drift 3b15f3ff → 3d88408d; the
   WS-4.2 interleaving rule; the frame-conditioned loop makes each run a sample; reusing the
   old A run saves ~7 min of ~4 h and buys a cross-tree confound). The old A_1 (6/15) is a
   cross-check anchor only.
4. **Q2b — the battery in flight is INVALID and must be stopped and relaunched.** The
   `run_n5.sh` env omits the stage-N scenario of record: `FRUIT_DYNAMIC_PICK=1`,
   `FRUIT_POLICY_TRIGGER=arrival` + `_LEAD=0.9`, and `FRUIT_SUPPLY_SCATTER/PATCH/GRADES`
   (the R11-B's own launch, `logs/r11/B_N_driver.log` line 5, carried all of them).
5. **The evidence is direct**: A_1's manifest reads `trigger=None` (the old run's reads
   `mode=arrival, lead=0.9, acq=True`); 0 `[carry]` lines (the diag is gated by
   `_dynamic_capture_active`, `tasks.py:2669`) vs the old 29; the success notes read
   "policy closed on the fruit (…)" — the **policy-gate** path — vs the old "intercept
   trigger (…)"; A_1 finished **3/15** vs the protocol's 6/15, with a different fruit stream
   and an 8/11 "fruit fell off the line" failure profile.
6. **Consequence**: with `FRUIT_DYNAMIC_PICK` unset, `_dynamic_pick_mode(openarm,
   scripted=False)` is False → the P1 indexed handover; C1 is read only under
   `dynamic_capture` (`tasks.py:8084`) → **arm B ≡ arm A** (both `moe_v13s`, same env);
   `FRUIT_POLICY_TRIGGER_ACQ=1` is inert (trigger off); the mechanism half (`clean_slip`) is
   unmeasured; the scenario is the default scatter/mix, not the patch/balanced sheet. An
   A/A null would be published as an L3 negative — a false negative.
7. **The fix**: stop the battery now (B_1 is running the same inert env); relaunch with the
   full stage-N env (template: `logs/r11/B_N_driver.log` line 5); add a **manifest
   precondition check after run 1** (`trigger.mode=="arrival"` and `acq=True`, `[carry]`
   count > 0, `[acq]` rows present, the notes read "intercept trigger", A_1 in the 6/15
   band); record the re-open as a deviation (stage N was conditional on a Stage-P positive).
8. **Q3 — the P18-C design is sound; the tables already show the answer's shape**: no
   amplitude separator (ok attempt-max reaches 130.7 mm/s, above the B1 minimum 37.3 and the
   B2 max 83.6); the **run-length** dimension separates the walker class ((60 mm/s, ≥8
   samples): 4/5 B1, 0/45 ok FP; (80, 2): 5/8 no-grasp, 1/45 ok, 2/7 carried); the **window
   is inert** (0/60; drift at fire 4–23 mm vs window 60); and the **phase is the real
   specificity lever** — every ok/carried fire is probe-1, so a hold-only scope at the
   shipped threshold reads 3 B1 / 0 ok / 0 carried. The verdict must convert trace samples
   to gate ticks, add drift@fire/latency, and not fit on the gate-ON corpus.
9. **Q4 — the ranking for bimanual throughput**: (1) **D3-proper** (owner-gated, L) — the
   only structural item on the binding terms (station + boundary-respecting descent + the
   grip class); (2) **the `go_ready` transit decomposition + bounded lever** (S–M, runnable;
   the biggest unclaimed wall term, ~4.3–4.7 s ≈ 25 %); (3) **L2** (S–M; offline curation
   census first; capped at acquisition, the binding carried class excluded); (4) **M1c**
   (S–M; only if P18-C lands a clean phase-scoped point; the response's outcome is
   measured-negative).
10. **No other file was touched; no commit; no default changed.**

---

## 1. Q1 — the P17-B closure: verified, sound; three record fixes

### 1.1 The independent re-derivation

| item | the record | re-derived here (method) |
| --- | --- | --- |
| control census | 45 ok; nc 8; carried 7 | **45/8/7** — `[run] attempt` rows, `logs/p12a2/{10,11,12}_*_mass.log` (11/7/2 + 17/0/3 + 17/1/2) |
| gate census | 37 ok; nc 10; carried 13 | **37/10/13** — same regex on `logs/p17i/{50,52,54}_*` (10/5/5 + 15/1/4 + 12/4/4) |
| K3 doubles | identical, 1016/1068/1067 | **identical** — `[fruit]` minus `[trace]` lines, `50↔51`, `52↔53`, `54↔55` |
| K4 replay | byte-identical, 0 diff | **950/950** `[fruit]` lines vs the mass base, `diff` = 0 lines, driver `exit=0 21:39:35`; current `tasks.py` = `3d88408dd5e82614dec7768faa17f77a`, `rl_env.py` = `60f462367b1dcaf926d83ecbb260bc88` (matches the P_RESULTS pins) |
| K2 letters | total 15→23; carried 7→13; nc 8→10 | **all three fire**; per-seed ok 11→10, 17→15, 17→12 |
| responses | 18 (12/1/5) | 12 `response=` rows in the s11 log; the P18-C `gate_own` table independently counts **7 fired attempts at s11** (matching the screen's 7-attempt figure) |

The pre-registered K2 ("the total failure mass does not fall, or the carried grows ≥ 2, or
the no-grasp grows ≥ 2") is met on all three branches simultaneously — no reading of the
letters rescues the arm. The verdict "negative, not adopted; the knob stays default-off" is
correct.

### 1.2 Doubts and their disposition

* **K4 covers seed 11 only.** The s5/s23 controls are on-disk (same `p12a2` battery as the
  s11 control, whose seed-11 replay is byte-identical). Given the scripted line's
  determinism, the residual is small — but the record should say "the control anchor is a
  single-seed replay" rather than the stronger "the tree drift since the mass-base battery
  is zero" (the P17-B diff is +521/−24; K4 proves *behavioural* identity on this path/seed,
  not tree identity).
* **The read's "N fired attempts" line is mislabeled** (`read_stage_p.py` dedupes by
  `(side, idx)`; one fruit re-attempted several times collapses). The record's 7-attempt
  figure comes from the screen's own analysis and is right; fix the read's label or print
  the attempt count from the `[slide]` summary rows (the P18-C `gate_own` pairing already
  does this correctly).
* **The falls number violates the design's own convention.** The design fixed the F6/A2
  convention: falls = `lowest payload point` rows ≤ −1000 mm **with blow-ups excluded**;
  partials −100…−1000 mm separately. `read_stage_p.py:falls()` counts all ≤ −1000 mm, so the
  quoted "7 → 11 rows" carries one blow-up per side (s11 control −55 282 mm; s11 gate
  −52 107 mm). F6-correct: **control 3/0/3 = 6, gate 4/1/5 = 10** — the falls still rise
  (the non-rise condition still fails), so the verdict is unchanged; the number should be
  corrected (or printed in the three bands).
* **"The fourth mechanism-win / outcome-negative instance (P11-C, P15-M2, and this)"** — the
  count needs P11-C.2 (the design's §1.3 names three priors: P11-C, P11-C.2, P15-M2). Fix
  the parenthetical.
* **"Each seed run twice (K3 doubles)"** reads as both arms; the doubles are the treatment
  arm only (controls are the on-disk mass base). Wording only.

### 1.3 What is unclaimed (should be claimed) and overclaimed (cut)

* **Unclaimed — the interval.** The battery ran `FRUIT_CYCLE_REPORT=1`; the L1 design lists
  the interval as a mandatory co-report ("reported, not the endpoint"); the P_RESULTS does
  not report it. The data is on disk — add the pooled interval (the P15 M2 battery's +8 %
  was part of its negative case; the same read belongs here).
* **Unclaimed — the per-leg motion budgets.** The battery ran `FRUIT_MOTION_REPORT=1`; the
  earlier gate's Gap E(iv) asked for the treatment branch's motion budgets as a K-condition
  co-report. Cheap: run `105_motion_regression.py`-style budget reads (or `199`) on the six
  logs. The M1/M2 branches change the hold/probe commands, so "no descent over budget" is a
  live question, not a formality.
* **Overclaimed — none material.** The wording nits above (falls count, "every class" is
  pooled-only — at s11 the no-grasp *improved* 7→5 while the carried grew 2→5; the
  mechanism section states this correctly) are precision fixes, not retractions.

**Verdict (Q1): the closure and the record are trustworthy; adopt with (i) the falls-number
fix, (ii) the read-label fix, (iii) the interval + motion co-reports, (iv) the two wording
nits.**

---

## 2. Q2 — the P18-B (L3 stage-N): the fresh battery is right; the battery in flight is invalid

### 2.1 Fresh vs reuse — fresh, and the reason is not the tree alone

The old A run 1 (6/15) was run on `tasks.py` `3b15f3ff` with the full stage-N env; the
current tree is `3d88408d`. Three reasons a fresh battery is right anyway:

1. **The WS-4.2 protocol's own rule**: "both arms in one instrumented batch", interleaved
   A,B,A,B. A run re-used across sessions/trees breaks the batch and the pairing (the
   per-`(run, episode index)` pairing needs both arms from the same run index and stretch).
2. **The direct loop is frame-conditioned** (the rendered frames are not bit-reproducible;
   AGENTS §3b) — every run is one sample of a stochastic interface; the 5-vs-5 design needs
   five *fresh* samples per arm from the same stretch.
3. **The saving is trivial**: ~7 min of a ~4 h battery; the confound is not.

Keep the old A_1 as a **band anchor** (6/15 with "intercept trigger" notes): the relaunched
A_1 should land in that band and carry the same note form — a cheap env-sanity check.

### 2.2 The defect: the battery in flight is not the stage-N protocol — stop and relaunch

`logs/p18b/run_n5.sh` sets `AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_ACQ_DIAG=1
FRUIT_CARRY_DIAG=1"` and `ARM_B_ENV="FRUIT_CLOSE_LOAD_RATE=0.04"` — and nothing else. The
R11-B's own launch of record (`logs/r11/B_N_driver.log` line 5) carried the full scenario:

```
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1
```

The in-flight run is missing `FRUIT_DYNAMIC_PICK=1`, the trigger pair, and the supply
triple. The evidence is on disk (all read at 21:50, A run 1 complete, B run 1 running):

| probe | old stage-N A_1 (protocol) | the in-flight A_1 |
| --- | --- | --- |
| manifest `trigger` | `mode=arrival, lead=0.9, acq=True` | **`trigger=None`** (trigger off) |
| `[carry]` diag rows | 29 | **0** (the diag is gated by `_dynamic_capture_active`, `tasks.py:2669`) |
| success note | "intercept trigger (…)" | "policy closed on the fruit (…)" — the **policy-gate** path |
| result | 6/15 (wall 411 s) | **3/15** (wall 592.7 s) |
| failure notes | carried-not-placed (the interface's class) | 8/11 "fruit fell off the line" |
| fruit stream | kiwi/tomato/strawberry/peach/… (no apple) | orange/tomato/pear/kiwi/…/apple — a **different supply/mix** |

**Impact.** With `FRUIT_DYNAMIC_PICK` unset, `_dynamic_pick_mode(openarm, scripted=False)`
returns False (`tasks.py:4198-4209`) → the handover runs the **P1 indexed primitive**; C1 is
read only under `dynamic_capture` (`tasks.py:8084`) → **arm B's `FRUIT_CLOSE_LOAD_RATE=0.04`
is inert; arm B ≡ arm A**. `FRUIT_POLICY_TRIGGER_ACQ=1` is inert with the trigger off; the
mechanism half (`clean_slip`/onset rows) cannot be read; the scenario is the shipped
scatter/50-30-20, not the patch/balanced sheet of the W8-A/W8-B/R11-B interface. A 5-vs-5
A/A null would be read and published as an **L3 negative** — a false negative on the
rank-1 candidate.

**The fix.** Stop the battery now (B_1 is running the same inert env; every further run is
wasted). Relaunch with the full stage-N env above. Add a **precondition check after run 1**
(read-only): the manifest's `trigger.mode == "arrival"` with `acq == true`; `[carry]` rows
> 0; `[acq]` rows present; the success notes read "intercept trigger"; A_1 in the 6/15
band; the fruit stream on the patch/balanced sheet. Kill the block if any fails (the R11-B
kill criterion 4: a contaminated run is discarded, never quoted).

### 2.3 The endpoint read (what must be printed, and one protocol note)

The pre-registration's exact stage-N endpoint: **pooled rate not below the batch's own
control arm** AND the **paired carried-class conversion** candidate-positive (one-sided sign
p ≤ 0.05) AND **cycle non-inferiority** (the P4 rule: paired sign p ≤ 0.05 with the
strawberry bucket non-inferior, or median cycle ≥ 5 % lower with success non-inferior) AND
**no new failure reason**; plus the **mechanism half measured and published regardless**
(the `clean_slip` signature: held <2 mm / escape >5 mm, onset rows, `force@onset`,
`contacts@onset`, `sep@onset`, loss rows, treatment vs control in the same block).

* The P18 plan's shorthand ("the carried-class conversion + the total mass + the cycle")
  **omits the mechanism half** — with CARRY_DIAG on (correctly set) the `[carry]` rows are
  there to read; include them.
* **Tooling**: the endpoint read is `scripts/113_rl_report.py` (pooled, paired sign test,
  per-class, cycle, failure reasons) **plus `logs/w8/A_pairs.py`** (the carried-class
  transition matrix, the same-fruit pairing, the strawberry bucket) — the W8-A tool the
  carried-class endpoint was built on. Both exist; no new tool is needed.
* **Convention note**: the "6-0 discordant split is the edge" wording is conservative — the
  report's sign test is P(X ≥ better) over the discordant pairs, so a 5-0 carried split is
  p = 0.031 ≤ 0.05 and a 5-1 is p = 0.109. State which convention the read applies (the
  pre-registered 6-0 edge, or the arithmetic edge) before the numbers land.
* **Protocol note (record it)**: the pre-registration says "Stage N (**only after a Stage-P
  positive**)". The stage-P read closed *not positive in substance* (the same-battery
  reading; `logs/r11/B_RESULTS.md` §5/§7), and the R11-B recorded its stage-N stop as the
  phase's deviation (§0). The P18-B re-run is therefore a **re-open of a closed phase** —
  legitimate under the owner's L3 directive / the Oracle's rank-1, but it must carry a
  one-line deviation note (the conditional was not met; the endpoint wording unchanged) per
  the R11-B's own discipline.

---

## 3. Q3 — the P18-C threshold analysis: sound design; what the tables show; the ambiguity list

### 3.1 The design (sound)

`logs/p17c2/threshold_analysis.py` recomputes the gate's own quantity (the world-frame
`fruit − jaw` per-tick rate, and the hand-frame drift for the window), validates it against
the gate's `[slide]` rows (11/12 agreement at the shipped rule, 0 trace-only fires),
pairs traces to attempts with 0 mismatches, searches `(threshold, ticks, window)` on the
**unbiased control corpus** (60 attempts; ok 45 / carried 7 / B1 5 / B2 3), and keeps the
treatment-branch corpus as a separate calibration read. That is the right shape: the gate's
own logic is replayed (`detect()`), the target is the walk class, the false positives are
counted on the ok population.

### 3.2 What the tables already establish

* **No amplitude-only separator.** ok attempt-max p90 = 62.4, max = 130.7 mm/s; B1 range
  37.3–310.2; B2 max 83.6. The classes overlap on amplitude.
* **The run-length dimension separates the walkers.** At ≥60 mm/s: B1 max-run 11–75 samples
  vs ok ≤ 7. The best points: **(60, ≥8 samples) → 4/5 B1, 0/45 ok FP, 2/7 carried**;
  **(80, 2) → 5/8 no-grasp, 1/45 ok, 2/7 carried**. 320/420 triples clear FP ≤ 1 — the
  frontier, not a point, is the honest output.
* **The window is inert.** 0/60 attempts change their fire count between window 60 mm and
  window off; the fires happen at drift 4–23 mm (max drift in the span is 165.7 mm). The
  window parameter should be declared measured-inert.
* **The phase is the real specificity lever.** At the shipped rule, *every* ok fire (3) and
  *every* carried fire (3) is probe-1; the hold-phase fires are B1-only (3/5 — the three
  hold-walk B1s, all s11). A **hold-only scope at the shipped threshold reads 3 B1 / 0 ok /
  0 carried** on the controls — cleaner than any (threshold, ticks) refit, and it is the
  scope change, not a threshold change, that removes the probe-1 harm site the P17-B screen
  flagged (fruit 12 peach, 2 ok → 2 carried with probe-1 fires).

### 3.3 What would make the verdict ambiguous (fix before the verdict lands)

1. **Sample-vs-tick space.** The hold is sampled every 2 ticks in the traces; the live gate
   samples every tick. The `ticks` parameter in the tables is in *trace samples*; the
   calibration shows the trace detector under-fires (misses 1/3/4/7 by rule, branch
   effects). Any operating point must be converted to gate ticks and re-validated against
   the gate's own rows, or the M1c build will not reproduce the offline fire pattern.
2. **In-sample small-n.** The target class is n = 5 (one arm, two seeds); s5 has zero
   no-grasp; the gate-ON corpus is a *treatment branch*, not a holdout. "Separating" here
   means "separates the 4 walkers from the 45 ok transients in this corpus" — quote the
   counts and the per-seed split, never a rate.
3. **Latency vs the recovery window.** The candidate rules fire later than the shipped one
   (ticks 8 vs 3); the design's own recovery argument needs the **drift@fire distribution**
   per candidate (the payload must still be inside the pad span; the P14-B B1s are 4–20 mm
   out through the first half of the hold). The tables print drift@fire for (60,3) only —
   add it for the candidates.
4. **Unreachable sub-classes.** The B2 class (probe-side) never sustains a rate run (max 2
   samples) and the non-walking B1 (s11/14, 37.3 mm/s) never crosses any sensible threshold
   — no rate rule can catch them; the verdict should say the gate's ceiling is 4/5 B1 +
   partial B2, not 8/8 no-grasp.
5. **The response is not the trigger.** P17-B measured the *response* (the in-place
   re-centre) as the trade carrier. A cleaner trigger at best removes the false-fire harm;
   it does not convert. The verdict must be scoped to trigger specificity, and any M1c
   battery needs its own pre-registration with the conservation check.
6. **The gate-ON corpus must not be used for fitting** (branch-shifted by the gate's own
   responses) — only as calibration. The lane's docstring says this; keep it in the verdict.

---

## 4. Q4 — the ranking after P18 (goal: bimanual throughput)

The closure map that bounds the choice: the scripted two-line's failure-mass levers are
exhausted (P11-C, P11-C.2, P15-M2, P17-B — all mechanism-win/outcome-negative or worse);
the direct interface's carried-not-placed class is scripted-owned (R9's branch-invariance;
R11-B's stage-P trade); the binding throughput terms are the **per-attempt span (~15 s, flat
across the density ladder)**, the **`go_ready` transit (~4.3–4.7 s ≈ 25 % of the wall — the
record's "biggest unclaimed term")**, the lock-on/idle (18–26 %), and the two-line flip bar
(1.25x placed/min; the dense supply read 1.19x; the named gap is the grip class).

**1. D3-proper (owner-gated; cost L).** The only structural item that touches the binding
terms: the pick station clear of the belt + a boundary-respecting descent (the named next
span target — every descent ends 40–90 mm short) + the grip class (the two-line's placements
on the dense supply). It is not runnable without the owner; put the boundary/station
evidence in front of them as the recommendation. **If opened, it outranks everything else.**

**2. The `go_ready` transit decomposition + bounded lever (runnable; S–M).** The biggest
measured unclaimed wall term (~25 %; in-house engineering; no paper mechanism). Phase
shape from the record: a **pure-reporting transit decomposition first** (where the 4.3–4.7 s
goes: blend/hold/convergence; re-measure — the P2-2 j1-stall fix post-dates the figure),
then one bounded default-off lever (overlap the transit with the next attempt's pre-pose, or
a shorter profile) with the standard no-harm chain. Caveat to state: it is a **shared** term
(both lines pay it), so it raises absolute placed/min but does not by itself move the
two-line/single **ratio** (the flip bar); the W2/W3 lesson (time-separating levers trade the
span away) applies.

**3. L2 — the attribution-routed policy iteration (S–M; offline curation census first).**
The measured carrier exists (ev1's acquisition movement; C.3 says the plain top-up suffices
— no heads needed), the curation census is offline and cheap, and the N=5 endpoint is
pre-registered. The cap is structural: the policy-attributable slice is the
fire-path/acquisition class, which the W7-B ACQ knob already moves (close-start 178 → 3–5
mm; no-contact 5 → 1–2), while the binding carried class is scripted-owned and must be kept
out of the update (R9's wrong-channel degradation is the in-repo evidence). It moves the
direct interface's capability, **not** the two-line throughput — rank it for a
policy-capability goal, not this one.

**4. M1c — a recalibrated/phase-scoped slide gate (S–M; only if P18-C lands a clean
operating point).** The family's prior is adverse (four mechanism-win/outcome-negative
instances; the response itself is the trade), and the P17-B battery's s5/s23 losses with
1–5 responses show the branch cascade. A phase-scoped (hold-only) recalibration is the one
form P18-C can justify — it removes the probe-1 harm site and the ok false fires — but the
best case is *less harm*, not a conversion, and it needs its own pre-registration with the
conservation check. Fund it only after P18-C's verdict names an operating point in gate
ticks with drift@fire inside the recovery window.

**Runner-ups (not arcs on their own)**: the two-line primary-then-conditional selection
refit (offline replay first; bounded by the flat cadence and the mix confound); the belt
speed as a scenario change (cross-scenario reads; the P1c composition lesson — do not quote
its throughput ladder); `FRUIT_BIARM_PREFETCH` (measured null, stays a hook).

**If L3's relaunched battery lands candidate-positive** (unlikely, but possible on the
direct interface): C1's adoption path opens (its own owner gate + the ≥ 5-run canary; the
defaults stay off regardless) — it then competes as a direct-interface lever, not as a
two-line throughput lever (its two-line screen was negative).

---

## 5. Provenance and limits

* This gate ran **no simulator**; every number above is re-derived from committed logs
  (`logs/p12a2/`, `logs/p17i/`, `logs/r11/B_N/`, `logs/p18b/N5/`, `logs/p17c2/`) or read
  from the code sites named (`tasks.py` 2669/4198-4209/8084; `rl_env.py` 915; `trigger.py`
  `from_env`). The in-flight battery was read at 21:50 (A_1 complete 3/15; B_1 started
  21:50) — the gate's finding is about the *launched env*, not the runs' contents.
* The P18-C review is of the design + the tables on disk at read time; the lane's final
  verdict should be checked against §3.2/§3.3.
* No file outside this one was written; no commit; no default changed; no other repo
  touched.
