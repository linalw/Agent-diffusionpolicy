# ORACLE GATE — the C.3 attribution verdict, the P17-B Stage-M design, and the next-arc ranking

**Status.** Read-only gate review (branch `p-supply`, 2026-10-19, HEAD `36b1dff`). No simulator
run by this lane; the only file written is this one. Inputs read: `AGENTS.md` §2/§3b; `logs/p14c/`
(`C3_RESULTS.md`, `IMPLEMENTATION.md`, `50_c3_read.txt`, `read_c3.py`, `run_ablations.sh`,
`run_screen.sh`, `A1/A2/A3_train.log`, `B_ab/`); `logs/p13/` (`B_RESULTS.md`, `B_mech.txt`,
`run_b.sh`, `B_ab/A_1.log`, `B_ab/B_1.log`, `40_train_ev1.log`); `logs/p17/CAPTURE_LEVER_DESIGN.md`;
`logs/p17i/` (`IMPLEMENTATION.md`, `run_screen.sh`, `run_outcome.sh`, `check_slide_gate.py`,
`20_m1_trace.log` + `traces_m1/`, `21_m2_trace.log` + `traces_m2/`); `docs/papers/UPDATE_2026_10.md`
§3/§5; `logs/p14b/TRACE_RESULTS.md` + `GRIP_DIAGNOSTIC.md` + `trace_p14b_analysis.py` +
`traces_s11/`; the P15/P16 records (`OUTCOME_RESULTS.md`, `SCREEN_RESULTS.md`,
`CLOSE_HOLD_DESIGN.md`, `logs/p16/BOUNDARY_DESIGN.md`, `logs/p16i/SCREEN_RESULTS.md`); the
`logs/p12a2/*_mass.log` mass base; the `logs/p15/*_m2*.log` outcome runs; the relevant
`tasks.py`/`finetune.py` code sites.

**Screen state at review time.** The Stage-M screen is on disk: **M1 completed 19:03:48**
(`logs/p17i/20_m1_trace.log` + `traces_m1/`, 20 traces) and **M2 completed 19:12:21**
(`logs/p17i/21_m2_trace.log` + `traces_m2/`, 20 traces). §2's screen-state paragraph is **this
gate's own provisional pre-read** (the P14-B rule re-implemented by hand; it reproduces the
control's record exactly); the screen lane's formal read is the record.

---

## 0. The answer in ten lines

1. **C.3 verdict: sound** at N=1 — the movement is 35–50× the control (178.2 vs 3.0–5.1 mm left
   close-start median), the pre-registered falsifier (the 6-epoch control reproduces the
   movement) obtained, and the flags' semantics are verified at three levels (runtime payload,
   provenance, weight-delta). **No further run is worth it for attribution.**
2. Confounds that remain are named in §1: the reused P13 control (cross-tree), N=1 eval (policy
   frames are not bit-reproducible), and the sufficiency-vs-mechanism nuance (the heads still move
   the proprio encoder 5× more — the endpoints are over-determined by *any* top-up).
3. **The P17-B promotion path is right in structure** (mechanism gate first, conservation-aware
   outcome battery second, the P15/P16i precedent, run-neutral trace), but **five endpoints/gaps
   must be closed before the Stage-N read** (§2): the falls accounting, the control census, the
   arrest check, the fruit-identity rule, and the `run_outcome.sh` gaps.
4. **The falls are a severity overlay on already-counted failures, not an additive class** (every
   fall row is a carry-leg clearance row, so it sits on an already-failing attempt; P16i measured
   H1's 7 falls as all-B1 no-grasp attempts). As written, K2 can let a carried→drop trade pass.
   The total must be `nc + carried` (attempts) with the falls/partials as a **non-rise** condition.
5. **The control census quoted in the design §1.3 (and the P15 table it copies) is wrong against
   the on-disk mass base**: nc is 7/0/1 (not 7/3/3) and carried is 2/3/2 (not 2/0/2); the design's
   own numbers are internally inconsistent (13 + 4 ≠ 60 − 45). Corrected, **the P15 M2 outcome
   battery lost pooled mass on every class** (nc 8→10, carried 7→12, ok 45→38) — it was not a
   "conserved trade"; the nc win (7→4) is seed-11-only. Re-derive the control columns before the
   Stage-N kills are read (§2, gap B).
6. **The arrest check as implemented is near-tautological**: the release fires on the first
   below-band sample, so `post ≤ band` ⇔ "a release happened" (M1's own rows release at 54.2–57.9
   mm/s and the payload still walks 132 mm in probe-1). The promotion rule needs the post-release
   drift trajectory / the converted attempt's survival (§2, gap C).
7. **Provisional screen read (this gate's own): the strict K1 fails on both arms** — the tracked
   three hold-walk attempts read 1 of 3 ≤ 20 mm on each arm (M1: orange 31.9 / orange 15.6 /
   tomato 37.5; M2: orange 38.1 / orange 47.5 / tomato 0.0-converted, the last **not
   gate-attributable** — its `[freeze2]` commit is at the same tick/depth as the shipped record),
   M1's nc fell 7→5 without a tracked conversion, M2's nc rose 7→8, and both seed-11 censuses are
   adverse (M1 ok 11→10, carried 2→5; M2 ok 11→8, carried 2→4, falls 3→7).
8. **The M1 trigger fired on 7/20 attempts including 3 oks** (rate_max up to 168 mm/s on an ok
   attempt): the 60 mm/s threshold sits inside the ok population's *per-tick* transient range; the
   design's specificity claim used the average walk bands, not the per-tick rates.
9. **Ranking if K1 fails: L3 (stage-N completion) > L2 (attribution-routed iteration) >
   D3-proper (owner-gated)** — L3 is the only shipped-knob lever aimed at the binding residual
   (the carried class is the direct interface's single failure mode) and its battery is half-run;
   L2 is cheaper to kill (offline curation census first) but excludes the binding class by
   construction; D3 is the structural fix but owner-gated. Runners-up: the selection refit (offline
   first) and the `go_ready` transit (§3).
10. **If K1 passes:** spend Stage P first (the arc's own completion); the ranking above applies
    only after a K2 fail, and a K2 fail would add a fourth pooled-loss instance to the
    close-side prior.

---

## 1. The C.3 attribution verdict

### 1.1 What was verified

* **The read reproduces its inputs.** `read_c3.py` → `50_c3_read.txt` on
  `logs/p13/B_ab/A_1.log` + `logs/p14c/B_ab/{A1,A2,A3}_1.log` gives the table in `C3_RESULTS.md`
  §2; the A arm's left close-start median (178.2 mm) sits 0.3 mm from the P13's pooled report
  (178.5 mm; `logs/p13/B_mech.txt` line 52, n=17 pooled — a parser-consistency check, not a
  re-run).
* **The ablation flags are semantics-verified, not assumed.** `logs/p14c/50_runtime_check.txt`:
  the shipped `PolicyRunner` loads all three checkpoints (strict `load_state_dict`); A1 carries
  the 8-tensor `event_heads` block, A2/A3 carry none; A3's provenance has no event fields. The
  weight-delta read shows the heads' design intent is real (`condition.proprio` max |Δ| 0.1518
  ev1 / 0.1509 A1 vs 0.0294 A2 / 0.0313 A3) — and **A2's transition-weight stats reproduce
  ev1's to the digit** (`mean_weight` 1.157966809817727 / 1.1602292812634964; 4710/29612 and
  1500/9378), a code-path cross-check.
* **The training seed is shared.** All four fine-tunes ran with no `--seed` (default 0 via
  `SEED`), the same base (`moe_v13s` `61da390a`), the same stores (`demos_v12` 158/158 +
  `demos_v11` base), the same `--epochs 6 --lr 5e-5 --weight-mode ones`; the save rule is
  "last epoch" for every arm (`finetune.py:458`), so there is **no best-val selection confound**.
* **The eval env is script-matched.** The C.2 runs replicate `112_rl_ab.sh`'s env exactly
  (`FRUIT_POLICY_TRIGGER=arrival`, `..._LEAD=0.9`, `FRUIT_DYNAMIC_PICK=1`, `FRUIT_SUPPLY_SCATTER=0`,
  `FRUIT_POLICY_TRIGGER_LATERAL=0.06`, `FRUIT_ACQ_DIAG=1`, `FRUIT_CAMERA_RES=240,424`,
  `FRUIT_POLICY_SEED=11`, `FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1`, `--episodes 15 --seeds 77`).
* **The margins are large and the movement is distributional, not a median artifact.** Control
  left |y| median/p90/max 178.2/275.0/275.0 vs the ablations' 3.0–5.1/4.9–5.3/~1 m (the tails are
  the reach-cliff flail, unchanged — C3 §4 says so); chases 4 → 1; no-contact 5 → 1/1/2.

### 1.2 The confounds that could still make the heads the carrier

1. **Flags' semantics — closed.** The one bundling left (A1 = heads + aux loss; A2 = transition
   weight + gamma) cannot carry the movement because **both off (A3) reproduces it**. A1's
   `weighted == mse` by construction; A2's stats equal ev1's.
2. **Training seeds — closed.** Shared seed 0, shared data order; a seed artifact would need
   three different-flag arms to coincide at the same endpoint (the opposite of a confound).
3. **Eval env — matched at the script level, with one residual:** the A/B controls are the P13's
   own records (P13 tree) while A1/A2/A3 ran on the current tree (`tasks.py` `3d88408d`; the
   P17-B knobs present and default-off). The default-off byte-inertness is verified offline (the
   P17-B stub; the P16-I executed-identity pattern) and the direct path reaches the knobs only
   with `FRUIT_DYNAMIC_PICK=1` and them set — but **no fresh control was run on the current
   tree**. Given the 35–50× margin this is not decisive; a fresh `moe_v13s` seed-77 run is the
   optional no-harm hardening, not an attribution run.
4. **N=1 per arm and the policy loop's frame variance.** The *mechanism* endpoints are large
   margin (the standing rule: quote mechanism, not rate); the *class composition* is not:
   A3 leaves nc 2 / carried 2 where ev1/A1 leave nc 1 / carried 5 — within single-sample noise at
   n=15 (Fisher two-sided p ≈ 0.5 for the 1/5 vs 2/2 split), and the pooled outcomes (9–11/15) sit
   in the known band.
   Do not read the composition difference as an arm effect.
5. **The sufficiency/necessity nuance (the honest residual).** The experiment shows the heads are
   **not necessary** for the behavioural movement (A3 suffices). It does not show the heads have
   *no* route: they move the proprio encoder 5× more than the plain top-up, so ev1's weight path
   is head-shaped while the endpoint is over-determined by "any 6-epoch top-up". The practical
   consequence: **use A3-style plain top-ups as the L2 baseline; do not attribute ev1's mechanism
   to the heads.** The C.3 wording ("the P13 heads-attribution is refuted") is fair — P13 itself
   labelled the reading "supportive but not a single-factor attribution" (`B_RESULTS.md` line 32)
   and pre-registered exactly this control (the KB §2d D2 falsifier: "if the 6-epoch control
   reproduces the movement, the heads are not the cause").

### 1.3 Worth one more run?

**No — not for attribution.** The falsifier obtained at a 35–50× margin, the flags are
semantics-verified, the seed/env are controlled, and per the standing rule a second eval seed
would add a rate/class-composition sample, not an attribution test. If a spend is wanted, the two
candidates are (i) the optional fresh control on the current tree (cross-tree hardening, ~30 min)
and (ii) the **N=5 paired outcome protocol on the plain top-up vs control** — which is the question
C.3 explicitly leaves open and belongs to the L2 lane, not to another ablation.

---

## 2. The P17-B Stage-M design

### 2.1 Is the promotion path right?

**Yes in structure.** The design does what the arc's own lessons demand: a mechanism gate at the
only seed with B1 mass (11) against the on-disk traced control; the trace is measured run-neutral
on this scenario (the P14-B three-run replay is byte-identical on `[fruit]` lines), so mechanism
and outcome come off the same runs; the outcome battery (11/5/23) is read as a class census, not a
rate; the K3 double protects the deterministic scripted line; the K1-before-P order stops the
spend at the mechanism negative. That is the P15/P16i precedent, correctly reused. The gaps below
are endpoints/plumbing, not a wrong shape.

### 2.2 Gap A — the falls accounting (the conserved-mass trade can pass K2)

The falls rows are a **severity overlay on attempts already counted in nc/carried**, not an
additive class: every fall row is a `carry grasp_lift`/`place` clearance row (the control's s11
regular falls are −1361/−1353/−1353 mm, `logs/p12a2/10_seed11_mass.log`), so it can only be
emitted on a failing attempt, and P16i measured H1's falls as growing with the B1 (3-probe)
no-grasp class (4 → 6). As
written, "the TOTAL failure mass = the no-grasp + the carried … **plus the falls**" either
double-counts or leaves the falls outside K2 — so a treatment that converts carried-not-placed
into floor-drops (counts flat, falls up) can pass "the total does not fall". **Fix:** K2's total =
failing attempts (`nc + carried` = 60 − placed), per seed and pooled; the falls rows/attempts and
the partials (−100…−1000 mm) are a **non-rise condition** inside K2; blowups excluded (the F6
convention). Report the rows *and* the attempts.

### 2.3 Gap B — the control census is mis-transcribed (fix before the Stage-N read)

The on-disk mass base (three independent reads: the `[run]` lines, the P14-B trace classes, the
P15 M2 runs' own logs):

| record | s11 | s5 | s23 | pooled |
| --- | --- | --- | --- | --- |
| mass base ok/nc/carried | 11/7/2 | 17/**0**/**3** | 17/**1**/2 | 45/8/7 |
| design §1.3 + P15 table ("nc", "carried") | 7/2 ✓ | "3"/"0" ✗ | "3"/2 (nc ✗) | — |
| mass base falls (regular) | 3 (+1 partial, +1 blowup) | **0** | 3 | 6 (+1 partial, +1 blowup) |
| P15 table falls ("10", per seed 3/3/3) | 3 | 3 ✗ | 3 | 10 ✗ |
| M2 outcome ok/nc/carried | 12/4/4 | 10/4/6 | 16/2/2 | 38/10/12 |
| M2 falls (regular) | 1 (+2 partial) | 3 (+3 partial, +1 blowup) | 2 (+1 partial) | 6 (+6 partial, +1 blowup) |

Consequences to fix before freezing the Stage-N thresholds: (i) the design's own numbers are
internally inconsistent (`nc 13 + carried 4 = 17 ≠ 60 − 45 = 15`); (ii) the P15 headline
"the falls 10 → 6" is wrong — regular falls are **6 → 6** and the partials rose 1 → 6; (iii) the
P15 headline "the carried 0 → 6 (s5)" is wrong — **3 → 6**; (iv) corrected, **the M2 outcome
battery lost pooled mass on every class** (nc 8→10, carried 7→12, ok 45→38; the seed-11 nc win
7→4 is the only win). The "conserved mass" prior should be restated for the P17 read: the
close-side lever's only outcome battery **grew** the failure total (15 → 22 failures), so K2's
"the total must fall" bar is right and no "trade" should be expected. Affected files:
`logs/p15/OUTCOME_RESULTS.md` (the table), `logs/p16/BOUNDARY_DESIGN.md` line 500,
`logs/p17/CAPTURE_LEVER_DESIGN.md` §1.3/§5.4, `AGENTS.md` §2 (the P15 paragraph). The P15 verdict
itself (NOT ADOPTED) is unchanged — the correction strengthens it. (The P11-C/P11-C.2 conservation
instances were not re-audited here; re-derive them before quoting the conservation law.)

### 2.4 Gap C — the arrest check is near-tautological as implemented

`_slide_gate_observe`: the release fires on the **first** below-band sample
(`if book["latched"]: if book["rate"] < band: release`), and `post=` is the rate at that tick. So
the promotion clause "≥ 1 converted attempt's post-response drift rate ≤ the ok band" is
equivalent to "a release happened at least once" — it cannot separate an arrest from a momentary
dip. M1's own rows show the failure mode: attempt 6's second response released at `post`
54.2 mm/s and the payload then walked 132.1 mm in probe-1; the ok attempt 2 released at
57.9 mm/s (both just under the 60 band); the attempt-14 response kept the hold drift to 16.3 mm
and the attempt **still failed** (nc). **Fix:** gate the
mechanism confirmation on the **post-release drift trajectory** (does the drift resume?) and the
converted attempt's survival (the release bracket / the total drift to takeoff), not the
instantaneous post rate.

### 2.5 Gap D — the fruit-identity promotion rule under a moved branch

The rule ("≤ 20 mm on ≥ 2 of the control's three hold-walk attempts, tracked by fruit identity")
is hostage to the three fruits recurring: both control hold-walk oranges are pool index 0 (the
pairing is ambiguous), and the branch demonstrably moves (M1's completion order differs; M2's
tomato converted). **Fix:** apply the rule as written *and* report the treatment's own per-class
walk distribution (all nc attempts), so the K1 verdict is readable when a tracked fruit is missed
or converts. (The P15 screen used the same identity-tracking convention successfully; keep it as
the primary read, add the distribution as the co-read.)

### 2.6 Gap E — `run_outcome.sh` plumbing

(i) **No doubles** — the design requires "each with a bit-identical double" (K3); the script runs
one run per seed. Either run the seed-11 double (the P15 F5 precedent: K3 at seed 11 only) or
amend the design. (ii) **No trace env** — the design's mechanism co-report on Stage-P runs needs
`FRUIT_DYNAMIC_TRACE=1` (measured run-neutral), or the mechanism read should be declared
Stage-M-only. (iii) The **knob-off control replay on the current tree** (the `[fruit]`
byte-identity vs `logs/p12a2/10_seed11_mass.log`) is listed in the no-harm half — make it a
**precondition** of the screen: the control traces were run on the P14-B tree (`tasks.py`
`810658b8`), the treatment on `3d88408d`. (iv) Minor: the KB's L1 kill list includes "any descent
over budget"; the design co-reports the per-leg motion but does not gate it — the M1/M2 branches
change the hold/probe commands, so add the treatment branch's own motion budgets as a K-condition
(co-report at minimum).

### 2.7 Provisional screen pre-read (this gate's own; the screen lane's record governs)

Method: the P14-B hold-walk rule re-implemented by hand (`ref` = last close row; walk = dfz(last
hold) − dfz(first hold)); it **reproduces the control's record exactly** (38.1/31.9/54.8; ok max
12.8; medians), and the traces pair by the completion counter (verified against the `[biarm]`
result order).

| arm | census (ok/nc/carried) | falls regular | tracked-three walks (mm) | ≤ 20 mm | nc count |
| --- | --- | --- | --- | --- | --- |
| control s11 | 11/7/2 | 3 (+1 partial, +1 blowup) | orange 38.1 / tomato 31.9 / orange 54.8 | 0/3 | 7 |
| M1 | 10/5/5 | 4 (+1 blowup) | orange 31.9 / orange 15.6 / tomato 37.5 | 1/3 | 7→5 (no tracked conversion) |
| M2 | 8/8/4 | 7 (+1 blowup) | orange 38.1 / orange 47.5 / tomato 0.0 (converted) | 1/3 | 7→8 |

* **Strict K1 fails on both arms** (the rule's object is the control's three attempts; the OR
  clause needs the nc fall *with* the tracked conversions — M1 has the fall without the
  conversions, M2 neither). The distribution co-read is kinder to M1 (3/5 nc walks ≤ 20 mm) but
  the class medians rise (nc median 1.8 → 15.6/25.6 mm), so the mechanism movement is not clean.
* **M2's one converted tracked attempt is not gate-attributable**: its `[freeze2]` row reads
  `commit=straddle tick=26 depth=60.3mm … ship=26t/60.3mm` — the two-sided condition obtained at
  the same tick/depth the shipped criterion would have frozen, so the gate was a no-op on that
  attempt (the conversion is branch movement). The rows show a mix otherwise (later commits,
  `ship=none` straddles, one fallback) — the screen lane should classify them before reading any
  conversion.
* **The M1 trigger's specificity is poor in practice**: it fired on 7/20 attempts — 3 ok (one
  with rate_max 168.0 mm/s), 3 nc, 1 carried — because the per-tick rate spikes inside the ok
  population (the pads' settling at the hold's start); the design's "ok ≈ 0.01 m/s vs B1
  0.08–0.14" gap is an *average* band, not the per-tick distribution the threshold reads. This is
  a calibration finding for the record even if the phase closes.

---

## 3. The next-arc ranking

### 3.1 If K1 fails (the likely branch per §2.7)

1. **L3 — the pre-onset load path stage-N completion (the R11-B carried class).** *Worth it.* The
   carried-not-placed class is the direct interface's single failure mode (W7-C: 32 of 33
   failures) and the conserved residual of the whole arc; `FRUIT_CLOSE_LOAD_RATE` (C1) is the one
   **shipped-knob** scripted lever aimed at it, its mechanism readout is the strongest of the
   R11-B three (freeze-zone face speed 188.7 → 39.9 mm/s, cnp −6/−6), and the N=5 paired endpoint
   is pre-registered. Cost M (the battery stopped incomplete — run 1 of the N=5 protocol per arm);
   prior adverse (stage-P 12/20 vs 13/18, never-grasped 0 → 5) but decisive either way, and it is the
   last scripted path to the residual before the owner-gated scene work. Kill on the
   stage-P signature (late-freeze/never-grasped growth) or no paired conversion.
2. **L2 — the attribution-routed policy iteration.** *Worth it, cheaper, but capped.* One curation
   + one fine-tune + the N=5 paired battery; the C.3 read lowers its cost (the plain top-up is the
   carrier — no heads needed; A3-style baselines suffice). Its cap is structural: the
   policy-attributable slice is the fire-path/acquisition class, which the plain top-up + the
   W7-B ACQ knob already move (close-start 178 → 3–5 mm, nc 5 → 1–2), while the binding carried
   class is scripted-owned and must be kept out of the update. Do the **offline curation census
   first** (the "empty attributed subset" kill is checkable without a run); if non-empty, train.
3. **D3-proper — the scene redesign.** *Not this phase's cost without the owner.* The only
   structural fix for the descent boundary + station + span, but R8-A put it out of scope and its
   proxy failed on the supply obstruction; rank it as the owner-decision item, not a runnable arc.

Runners-up (not arcs on their own): the two-line primary-then-conditional selection refit
(offline replay first; E1's look-ahead is the falsifier design; throughput, not failure mass);
the `go_ready` transit (~4–5 s/attempt, the only non-gated span item — the binding term is the
per-attempt span); the B2 takeoff→carry-gap/probe-shape family (low n; needs its own trace call
site before any lever).

### 3.2 If K1 passes

Nothing outranks finishing the arc: **run Stage P on the promoted arm** (fix gaps A–E first), then
the shipping path if the total falls (two-line-scoped default + reference re-record + no-harm).
The ranking above applies only if Stage P fails K2; a K2 fail would add a fourth pooled-loss
instance to the close-side prior and would *strengthen* L3/L2's case (the scripted capture side
exhausted, the residual paths remaining).

---

## 4. Provenance and limits

* This gate ran **no simulator**; the provisional reads in §2.7 are ad-hoc re-implementations of
  the P14-B rule on the on-disk M1/M2 traces (they reproduce the control's record exactly; the
  screen lane's `trace_p14b_analysis.py`-derived read is the formal record).
* The census corrections in §2.3 are re-derivable from `logs/p12a2/{10,11,12}_*_mass.log`,
  `logs/p14b/TRACE_RESULTS.md` §1.1, and `logs/p15/{20,22,23}_*_m2.log`; the falls counts use the
  F6 convention (rows −1…−20 m, blowups excluded, partials −100…−1000 mm reported separately).
* No file outside this one was written; no commit; no default changed.
