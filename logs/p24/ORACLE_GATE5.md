# Oracle Gate 5 — the B1c adoption, the release closure, and the next arcs (2026-10-21)

Read-only review of the P22/P23 closes and the P24 question set. No simulator run, no `src/`
change, no default change, no other file touched; the only write is this file. Branch `p-supply`,
HEAD `d9bd2cf`. Everything below that is a number is either quoted from a record with its log or
re-derived offline from the logs in `logs/p20i/` and `logs/p21i/` (the checks are listed in §1 so
they can be repeated).

**Verdict in ten lines.**

1. **The B1c's mechanism is exact, and it is the best-instrumented result in the P-series.** The
   skip fires on 20/20 attempts per run, the credit is 20 × 230 ticks with a cumulative ladder,
   and the credited 230 ticks (1.917 s) equals the measured gap saving (1.90/1.95/1.90 s on the
   three seeds) to the logs' 0.05 s resolution.
2. **Its timing channel is clean, per-seed, placebo-isolated — and unreported.** Derived here
   with `186`: window rate **2.13 → 2.54 placed/min (+19 %)**, pooled interval **28.20 → 23.63 s**,
   p90 42.5-45.4 → 36.7-40.3 s, idle **25-27 % → 17-20 %**, batch rate 2.09 → 2.48; the placebo P
   reads 2.15 / 28.45 s, i.e. **A**. This is the lever's adoptable content and no record states it.
3. **Its census channel is not established.** B's per-slot gain over A is +1/+3/0 (46/60 vs
   42/60) while the placebo's own displacement is **-4/+2/+1** — larger than the lever's. B vs P
   is 2-1 on seeds (p = 0.5 two-sided); and 3 seeds cannot reach p ≤ 0.05 by construction
   (3/3 wins would be p = 0.125). A ~5-point pooled gain would need ~680 attempts/arm, ~11× the
   battery.
4. **So the record's load-bearing sentence is wrong**: "the +4 of B over both is the re-anchor".
   The placebo isolates the *clock* (it holds 5.10-5.20 s, exactly as designed); it does **not**
   isolate the *census*.
5. **The adoption is not yet justified — but the tree caveat is the weakest open item, not the
   strongest.** `65_sa_A` is **681/681 `[fruit]`-line identical** to the frozen pre-registration
   control `logs/p9a/96_pat_A_1.log` once the `[ready]` diag rows are dropped, so A is the frozen
   branch, `FRUIT_READY_DIAG` is print-only, and the mid-battery tree change is measured-inert at
   the range's end. A "clean single-tree replication" cannot even be a comparison at s11 (there is
   no s11 historical patch control to compare against).
6. **What is actually missing is the design's own primary endpoint**: no `FRUIT_SUPPLY_DIAG` run
   exists anywhere in the B1c battery. Endpoint 1 — "B's per-poll `late_lo` tracks A's with zero
   drift", which the design itself calls *the only endpoint that can tell a correct re-anchor from
   a lucky branch* — was never measured, so the acceptance-floor miss cannot be attributed the way
   the design requires before it is called a draw.
7. **The missing acceptance seeds are the second real gap**: the design pre-registered the
   acceptance at **three** seeds (5/11/23) precisely because the shipped control itself is 4/10 at
   SEED=23; only the default seed was run. The floor objection currently rests on one draw.
8. **The third is the consumer set**: a flip also moves the **single-arm collector** and the
   **hybrid policy canary** branches (both reach `go_ready` under the single-arm scope). Neither is
   measured; the W7-B guardrail is the precedent that this is inventoried *before* a flip.
9. **On the shipped scenario the lever's realized throughput is negative on its one sample**
   (acceptance: 9/10 → 7/10, 2.69 → 2.29 batch placed/min, wall -8.8 %), while on the patch sheet
   it is +19 %. The sign of the rate flips with the scenario — which is why the two missing reads
   decide the flip, and why "adopt for throughput" cannot be argued from the patch battery alone.
10. **Release family: right verdict, one wrong cell, one over-narrow residual.** The pooled
    "BR vs B ≈ -2 points" is a miscompute — BR is **+4.3 points** over the trim (56.0 % vs 51.7 %);
    "the nominal-credit mismatch" names one of two live residuals; and the release credit is
    **unobservable in every BR log** (no `credit=` print on that path), which is a one-line fix.

---

## 1. The checks I ran (all offline, all reproducible)

| # | check | result |
| --- | --- | --- |
| 0 | `python3 logs/p20i/read_singlearm.py` | reproduces B1C_RESULTS §1 exactly: A 42/58, B 46/59, P 41/57; gaps 5.20/3.30/5.20; credits B `230..4600` step 230, P `0` |
| 1 | per-run census over the 9 `*_sa_*` logs (own parser) | A 16/13/13, B 17/16/13, P 12/15/14 — and the **per-slot** denominators: 42/60, 46/60, 41/60 (each run offers 20 slots; an empty poll silently removes an attempt row, so the reported n = 20 − empties) |
| 2 | per-seed **gap p50** (the reader's own formula, per run) | A 5.10 / 5.20 / 5.20; B 3.20 / 3.25 / 3.30; P 5.10 / 5.15 / 5.20 → the design's endpoint 3 (**≥1.5 s on every seed**) passes on all three, and P holds the shipped clock on all three |
| 3 | per-seed **wall per attempt** (span p50 + gap p50) | A 20.50 / 20.50 / 20.85 s; B 18.70 / 18.55 / 18.55 s → **-8.8 to -11.0 %**, the Gate-3 corrected endpoint, still unreported |
| 4 | **A-side validity vs the frozen control** | `logs/p20i/65_sa_A.log` vs `logs/p9a/96_pat_A_1.log`: **681 / 681** `[fruit]` lines identical (0 diff) once only the new `[ready]` diag rows are dropped — including the `[run] attempt … sim=t0-t1` windows (643/643 on the physics-only view). Three facts follow: the A arm **is** the pre-registration's frozen branch (design §5 kill item 6 satisfied), `FRUIT_READY_DIAG=1` is **fully print-only** (not merely physics-neutral), and the design's **patch-A no-harm bar (681/681 vs `96_pat_A_1`) is met** |
| 5 | `186` over the three A runs / three B runs / three P runs (seed order s11 / s5 / s23) | window 2.21/2.17/2.01 · 2.59/2.64/2.40 · 1.78/2.20/2.46 placed/min; pooled interval mean 27.09/27.62/29.90 · 23.18/22.69/25.01 · 33.78/27.22/24.35 s; p90 44.6/42.5/45.4 · 40.3/37.6/36.7 · 61.9/41.2/42.6; idle 27/25/25 · 20/17/18 · 25/27/26 % |
| 6 | `186` over the three acceptance logs | A 2.69 batch / 2.90 window placed/min, span 201.0 s, idle 25 %; B **2.29 / 2.40**, 183.2 s, 18 %; P 2.38 / 2.52, 201.3 s |
| 7 | acceptance census (own parser) | A 9/10 (carried at **0**), B 7/10 (carried at **0, 4, 6**), P 8/10 (carried at **0, 5**) — attempt 0 is carried in **all three arms**, so the lever-relevant subpopulation is slots 1-9: A 9/9, P 8/9, B 7/9 |
| 8 | `105` with the **correct** floors on all nine patch logs | **9/9 PASS** on the speed/lurch budgets (`-m 0.5`): worst `\|v\|max` 0.111-0.142 vs 0.160-0.162, lurch 0.017-0.080 vs 0.291, `a_win5` 0.72-4.77 reported-not-gated |
| 9 | `105` with the **quoted** flags (default 0.75 floor, `motion_reference_patch.json`) on the three logs P23 quotes | FAIL on all three (fingerprint differs everywhere; the 0.75 floor too on `723`, 13/20 = 65 %; A's own `623` fails the same floor by the same arithmetic) — this is the *wrong invocation*, not a finding (§5.2) |
| 10 | provenance of `configs/motion_reference_patch.json` | **7b028049**, re-recorded in **P10-C.3** from `logs/p10c3/70_flip_seed5` — a **two-line** run. `_pre_p10c3` (b08dd3e9) is the R5 two-line write; `_patch_mass` (df5db0cb) is the P13 **two-line mass** reference. **There is no single-arm patch reference on disk.** The file is also the `190` two-line gate's reference (ROADMAP pin) |
| 11 | `configs/motion_reference_patch.json` vs its own documented source | it does **not** match `logs/r5/20_patch_battery_1.log` leg-for-leg (that log's legs are 89/87/89/91/**96**, the file's 89/87/89/88/88) — consistent with check 10's P10-C.3 re-record, i.e. the R5 md5 in ROADMAP is the *pre*-P10-C.3 file |
| 12 | `105 --fingerprint configs/motion_reference.json logs/p21i/50_accept_noharm.log` | **PASS + "fingerprint: matches"**; the log carries 385 `[fruit]` lines. G5 is real, and it needs the `--fingerprint` argument to be a fingerprint check at all (the log itself prints no fingerprint line) |
| 13 | BR census re-derivation (`[biarm] result`) | s11 B 11/20 ×2 = 22/40, BR 10/20; s5 B 7/20 ×2 = **14/40**, BR **13/20 ×2 = 26/40**; s23 B 13/20 ×2 = 26/40, BR **10/20 ×2 = 20/40**. Control 17/17 at s5/s23 and 11/11 at s11, all ×2. P23's census table is otherwise reproducible |
| 14 | `credit=` rows in the BR logs | **0 in every BR/relB log** — the release credit is printed nowhere (the print is gated on `_ready_skip_resync`) |
| 15 | the two-line patch reference's own gate convention | `logs/r5/run_patch_battery.sh` header, verbatim: *"the patch battery is 10-12/20, below 105's single-arm 0.75 floor - the two-line gate is 190 with -m 0.5"* — P23's G4 used exactly the invocation the project already documented as wrong |

---

## 2. Q1 — is the B1c's evidence enough for a default flip?

### 2.1 The evidence, split by channel (the split is the finding)

The B1c mixes three kinds of evidence and they do not have the same strength. Read separately:

| channel | measurement | strength |
| --- | --- | --- |
| **the mechanism** | skip 20/20 per run; credit 230, 460, … 4600 (20 debits, cumulative, P credits 0); gap −1.90/−1.95/−1.90 s per seed; credited 1.917 s ≈ measured 1.90 s | **deterministic and exact.** No statistic involved; a content check, not a draw |
| **the timing** | wall/attempt −8.8…−11.0 % on every seed; idle 25-27 → 17-20 %; interval mean −16 %; window rate +19 %; P unmoved (2.15 / 28.45 s ≈ A's 2.13 / 28.20) | **clean, per-seed, placebo-isolated.** The placebo does exactly its job here |
| **the census** | per-slot B ≥ A on every seed (+1/+3/0); pooled 46/60 vs 42/60; **P's own displacement −4/+2/+1** | **not separable.** The placebo's displacement is larger than the lever's |
| **the guards** | G4 budgets 9/9 PASS (check 8); G5 acceptance 9/10 + 385 lines + `105` PASS + fingerprint matches (check 12); A-side identity 681/681 on the full stream (check 4) — i.e. the design's own patch-A no-harm item is met too | **pass, and stronger than the record says** |

The census is the one that has to carry an adoption argument, and it is the one that cannot. That
is not a reason to reject the lever; it is a reason to stop claiming the census and to adopt (or
not) on the timing endpoint with a non-inferiority guard.

### 2.2 Numbers that decide it

* **Power.** 60 slots/arm at a 70 % base rate: a +5-point effect needs ~680 attempts/arm for 80 %
  power. The design's 3 × 20 cannot see it. A 3/3 sign-test win is p = 0.125. **The census endpoint
  as specified cannot be falsified by this battery** — and that is true of the census-endpoint style
  across the P-series (3 seeds is a direction, not an effect; the B1's 6/10 acceptance kill is the
  same kind of one-draw verdict at n = 10).
* **The placebo's spread is the yardstick.** P is *designed* to be A's clock (hold = 230 cancels
  the skip's debt one-for-one) and it reads 41/57 vs A's 42/58 pooled, but −4/+2/+1 per seed. The
  correct inference from the B1c is: *at n = 20, this scenario's census moves ±4 on micro-history
  alone.* B's +1/+3/0 sits inside that band. The exact same argument is what the Gate-4 used
  against the *release* trim (§3.5 there), and it applies to the B1c's positive with the same force.
* **The wall is the independent endpoint.** B's per-attempt wall is −1.8/−1.95/−2.30 s on the three
  seeds, and it is the only endpoint that is (i) per-seed, (ii) one-signed, (iii) mechanism-exact
  and (iv) unmoved in the placebo. On the patch sheet it converts to a +19 % batch rate; on the
  acceptance it is swamped by a −2 census draw (−15 %). Both are single samples; **neither is a
  throughput result, and the record claims neither.** That is the gap to close.

### 2.3 What the B1C record overclaims

1. **"the +4 of B over both is the re-anchor"** (§2). Not supported: the placebo isolates the
   clock, not the census (§2.2). The supportable sentence is *"the wall saving is the re-anchor's;
   the census difference is inside the placebo's own micro-history spread."*
2. **"the empty-poll class shrinks 2 → 1"** (§2). Design endpoint 2 is **zero** in B on both
   scenarios; B has **1** on the patch, and P has **3**. Counts of 1-3 events over ~58 attempts are
   not a class, and the design's own §7.3 says the empty-poll rate is under-powered at 6/130. The
   frozen bar was quietly softened from "zero" to "shrinks".
3. **"the design says the floor is a branch draw to be reported, not the verdict"** (§3). The
   design does not say that; it says the **orchestrator must decide** the ordering before freezing
   (§5's last paragraph, §6's last paragraph), it keeps "the pooled placement B < A" in its kill
   list, and its endpoint 4 makes the floor "**the gate of record**". Reading the design as having
   pre-waived the floor is the one place where the record converts a *decision* into a *given*.
4. **"the census is not worse on any seed" → "positive"** (Status line). The *mechanism* is
   positive; the *outcome* is at best non-inferior, and the outcome endpoint's composition-
   standardised / per-class report (design §5 item 4) was never produced.

### 2.4 What is missing (ordered by what it costs to close)

1. **Endpoint 1, the presentation stream — unrun.** No `FRUIT_SUPPLY_DIAG` run exists in the
   battery (§1's grep finds the knob only in the lane's `IMPLEMENTATION.md`). The design calls this
   "the only endpoint that can tell a correct re-anchor from a lucky branch", and its kill list
   makes a monotone drift the decisive kill for the form. Without it, the acceptance-floor miss
   cannot be attributed, and §2.3's claim 3 has no basis. **3 runs.**
2. **The acceptance at 3 seeds — 1 of 3 run.** The design's §5 item 1 and item 4 both ask for
   5/11/23; the battery ran the default seed only (`run_b1c_battery.sh`: `ACC=(HEADLESS=1
   ATTEMPTS=10 …)` with no `SEED`). The design's own §6.3 is the argument for 3 seeds: the shipped
   control is **4/10 at SEED=23**, so the floor is a draw — but a floor can only be shown to be a
   draw by *more draws*. **4 runs.**
3. **The consumer set — unmeasured.** `go_ready` is the single-arm ready phase; with the skip on,
   both the **collector** (`40_collect_demos.py`, single-arm, `_active_session is None`) and the
   **hybrid policy canary** handover primitive take the skip. A flip therefore moves the
   demo-collection branch (a new dataset lineage, cf. the W7-B guardrail) and the policy canary's
   branch. Nothing in either record names this. **0 runs to state, and it belongs in the adoption
   package.**
4. **The double-run endpoint — unmet for B and P.** Design item 6 asks each arm to be double-run
   identical. B and P have one run per seed. (A's "double" is the historical control — and it is a
   *stronger* check, since it is cross-tree, check 4.)
5. **The `DG = 0.02` calibration — a shipped scalar with a post-hoc value.** The lever only fires
   when `dg ≤ FRUIT_READY_SKIP_DG`; the shipped default 0.01 missed the measured 0.0131-0.0135
   (the B1's byte-identical null battery) and 0.02 is 1.5× the measured value. A flip ships that
   number. It happens to fire on 100 % of attempts in both batteries, so the operational risk here
   is low — but a default flip should state *why* 0.02, not inherit it from a battery that needed
   it to fire at all.
6. **The single-tree replication — not the binding gap.** See §2.5.

### 2.5 On the "clean single-tree replication" caveat

B1C_RESULTS §3 says the tree changed mid-battery and "a clean single-tree replication is the honest
confirmation". My check 4 shows this is the *cheapest-looking but least informative* of the open
items:

* A at seed 5 on `62cdbb7f` is **byte-identical** to the frozen control at seed 5 on `3d88408d`, so
  the endpoints of the tree range are measured-inert on this path (and the `[ready]` diag is
  print-only, which the battery's own A arm needed).
* s11's A began before the knob landed (the record's reading: `455f1a33`) and its B/P after
  (`62cdbb7f`); `455f1a33`'s only delta is the default-off B1c knob (stub-verified in the lane). A
  re-run of s11 on one tree would produce **a new draw**, not a comparison — there is no s11
  historical patch control on disk (`logs/p9a/` ran SEED=5 only).
* So the tree caveat is *already answered to the standard the rest of the project uses* (a
  byte-identity across the range's ends + a structural argument for the middle). It should be
  demoted in the record, not promoted into the confirmation run.

### 2.6 The smallest decisive confirmation

**7 runs, ~50 min, no code, no new knob** — the two pre-registered endpoints, run as one block
(sketch, in the battery's own shape; the actual chain should claim the simulator as
`154_claim_run.sh` did and pin the tree md5s):

```
# endpoint 1 (the design's primary): the acceptance at seed 5, the presentation stream
FRUIT_SUPPLY_DIAG=1 SEED=5 HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 \
  FRUIT_READY_DIAG=1  scripts/run.sh scripts/20_pick_place.py        # A
   … + FRUIT_READY_SKIP=1 FRUIT_READY_SKIP_DG=0.02 FRUIT_READY_SKIP_RESYNC=1   # B
   … + FRUIT_READY_SKIP_HOLD=230                                     # P
# endpoint 4 (the floor, 3 seeds): the acceptance at 11 and 23, A vs B
#   (the same two lines, SEED=11 then SEED=23, A then B)  -> 4 runs
```

**Decision rule, frozen before the runs:**

* **Endpoint 1 passes** (B's per-poll `late_lo` tracks A's within one release period, no monotone
  drift — read it as a *difference of distributions per slot*, not the two-line's ambiguous scalar;
  the single-arm runs have one arm, no arbitration, so the metric is cleaner here) **and** the
  acceptance reads B ≥ 8/10 on ≥ 2 of 3 seeds → **flip, on the timing endpoint, with the census as
  a non-inferiority guard** (pooled per-slot B ≥ A − 2 slots of 60). Re-baseline: the interval/wall
  read, the collector lineage note, no motion reference change (the B1c moves no motion profile —
  design §5 item 5 expects B to *match* A).
* **Endpoint 1 passes and the acceptance stays 7/10-ish on 3 seeds** → the floor is a property of
  the lever on the shipped scenario; **do not flip**; publish the timing gain as a measured lever
  available behind the env (the B1c's value then is the model, not the shipped line), and take the
  question to the owner as a *bar* decision ("the shipped default's acceptance floor vs +10 % wall").
* **Endpoint 1 fails (drift)** → the re-anchor is mis-counted on the single-arm path too and the
  whole form is not understood; **stop the family** and fix the credit's accounting first (the same
  missing-`credit=`-print item as §3.2). No flip.

Do **not** spend the block on the single-tree replication (§2.5) or on more patch-battery seeds
(§2.2 power).

### 2.7 The scope, stated so the flip cannot be misread

* The skip is `_active_session is None and not two_line_enabled()`: it touches **only** the
  single-arm line. `FRUIT_BIARM=1` (shared-station) and `FRUIT_BIARM_TWOLINE=1` never skip, so the
  two-line's numbers and the R5 "opt-in" decision are untouched by any B1c default change.
* The **two-line default stays opt-in** (R5-1) and this gate does not reopen it. The belt screen
  below (§4) is a two-line question and is separately owner-gated.
* A flip is **not** a no-harm event for the *data*: the single-arm collector's episodes land on a
  new branch, exactly as the W7-A two-line flip did (`collection.park_early: "auto"` is the
  precedent for recording it in the shard manifest).

---

## 3. Q2 — the release family: is "closed negative, the nominal-credit mismatch the named
residual" the right record?

**The verdict is right. Two corrections, one of them a number.**

### 3.1 The pooled cell is miscomputed (and it matters for the story)

P23 §2's table reads `pooled | 90/120 | 62/120 | 56/100 | ~ -2 points`. Re-derived (check 13):

| arm | pooled | rate | vs trim |
| --- | --- | --- | --- |
| control A | 90/120 | 75.0 % | — |
| trim B | 62/120 | **51.7 %** | — |
| trim+resync BR | 56/100 | **56.0 %** | **+4.3 points** |

So the resync is **+4.3 points over the trim pooled**, not −2. The
narrative already says "recovers s5 strongly and loses s23", so the verdict does not change — but
the table contradicts the narrative and a reader who checks the cell will find the record
internally inconsistent. Fix the cell: **+4.3 points, still −19 points vs the control (−25 %
relative)**. Per seed: s5 **+6/20 per run (+12 pooled)**, s23 **−3/20 (−6)**, s11 **−1**.

### 3.2 The residual is under-named, and it is unmeasured

"the nominal-credit mismatch" is a *hypothesis with a mechanism*. It is not the only live one, and
nothing in the P23 battery measures it. The two live residuals:

1. **the credit is nominal** — 120 ticks assumed per released attempt (the release-hold arithmetic
   says the tail goes 196 → 76, so 120 is probably exact, but the *actual* per-attempt debit is
   never printed);
2. **the phase is not the only mediator** — the shared-station arbitration / the arm's micro-history.
   The B1's own placebo (clock held, branch still re-drawn 8/10 vs 9/10) is the direct evidence, and
   the M1 read (`late_lo` p50 BR 0.365 vs A 0.600) is consistent with *either* residual.

The record should name both and say which is testable: **(1) is one print away.** Check 14: there
are **zero `credit=` rows in every BR/relB log** — the print is inside `_ready_report`, gated on
`_ready_skip_resync`, which the release battery does not set. Gate-4 §4.4 asked for exactly this
("a `credit` sum == 120 × releases") and also flagged the unlocked `-=` on a shared float from two
workers, where a lost update is 43 % of the usable band. **A one-line print at the release credit
site is the cheapest remaining item in the whole release family, and it is the guard against the
thread-safety failure the Gate-4 already identified.**

### 3.3 What is left to claim, and what stays withdrawn

Claim (all measured, some still unreported):

* the resync's **s5 recovery is 60 % of the trim's loss** (12 of 20 attempts) — the record says
  "+12" but not the fraction, and the fraction is the interesting number;
* **both BR arms are census-identical doubles** (13/13 at s5, 10/10 at s23) — a determinism datum
  the record does not state;
* the **trim's own wall saving** (batch 1279 → 1182 s, −7.6 %) and its **clean landing guards**
  (roll 206→102, bounce 3.3→1.5, skid 70→54, off 267→164, `return` 0.67 unchanged) — already in the
  Gate-4 correction, still correct, still the exoneration of the *release*;
* **no new failure reason** in the trim or the BR stream.

Withdrawn (unchanged from the Gate-4, do not re-derive):

* "the loss is the branch" as an attribution (the actuator is unnamed);
* the `falls` census and the `settle` direction (both corrected in P21's CORRECTION block);
* "any wall change re-rolls the presentation" as a law (its own placebo refutes it).

### 3.4 The form the closure does not cover — and it is now cheap

The family is closed on the **two-line**, the one line where a supply-clock credit cannot be the
whole story (arbitration + two workers sharing the cursor). The one form that was never run is the
trim + resync on the **single-arm** line — the line whose re-anchor the B1c has just verified to a
tick (credit 230 = 1.917 s vs measured 1.90 s). It is the discriminating experiment:

* if TR+RESYNC holds the census on the single arm and takes 1.0 s off the 2.31 s release block, the
  **release is exonerated and the phase model is validated** — a second wall lever (−2.9 s of
  20.5 s = −14 % with the skip) and the two-line's failure is arbitration-side (a *finding*);
* if it loses the census there too, the credit model is wrong or the phase is not the mediator —
  and the two-line's −25 % is arm-side, not supply-side.

That is one pre-registration and ~6 runs (3 seeds × A/TR on the patch + 2 acceptance), ~75 min.
The knobs already exist (`FRUIT_RELEASE_RESYNC=1`; `armed=True` was added for this path).

---

## 4. Q3 — the next-arc ranking for the throughput goal

Ranking rule: **goal value per run-hour, counting only what can start without a new owner decision
first** — because two of the strongest candidates are bars, not data (below), and a bar question
should be asked once, not serialised behind runs.

| rank | arc | measured value | cost | why here |
| --- | --- | --- | --- | --- |
| **1** | **Finish the B1c** (§2.6: endpoint 1 + 2 acceptance seeds) | the only positive lever on the board: wall −9…−11 % per seed, window rate +19 % on the patch, no-harm byte-clean | **7 runs ~50 min**, no code | it is 90 % paid for; the two reads are the *pre-registered* ones; and it converts an ambiguous record into either a shippable lever or an honest close. Nothing else on the list has this value/price |
| **2** | **Release trim + resync on the single arm** (§3.4) | either +1.0 s/attempt (≈ +5 % wall, −14 % with the skip) *and* the phase model validated, or a decisive negative on the P21 systemic finding | **6 runs ~75 min** + one pre-registration | the knob exists, the credit is verified exact on this line, and there is no arbitration confound. It is the only cheap way to settle a question that currently holds up *every* wall lever in the project |
| **3** | **Belt 0.15** (owner-gated) | **+29 % window rate on the goal line** (3.63 → 4.69 placed/min), interval 16.53 → 12.80 s, per-leg clean (catch peak 0.108-0.116, `end` 8.2-12.2 mm) — the mechanism is the *descent block's arrival wait* falling 3.19 → 2.40 s | **2 runs ~25 min** + a re-baseline if shipped | the biggest goal-line number on the board and it is *blocked on a decision, not on data*. If the owner says yes it jumps to rank 1. It also needs the per-speed selection floor (R3 §4: the 1.5 s floor covers 0.18 m at 0.15, so the usable band narrows 0.45 → 0.27 m — that is the 0.18 starvation mechanism, and the named form is a *scenario-calibrated floor per speed*) |
| **4** | **The descent boundary / D3-proper** (owner-gated) | the two-line's remaining *span*: descent+hover 3.19 s of 15.08, **of which ~1.7 s is the arrival wait** (the belt lever's target) and ~1.5 s the descent motion (40-90 mm ended short every leg, finished by the solver); close+grip 2.8 s (families closed), lift 1.8 s, place 3.2 s (closed by P3's geometry) | multi-day; three failed proxies (R8-A D2a/D2b/D3) | it buys the *same waiting time* the belt lever buys for 1/20th the cost, and its own gate (the `\|v\|max` budget) cannot distinguish a boundary strain from a push. Do it after the belt number exists, not before |
| **5** | **L3 / C1 class-matched (strawberry 8/15, apple 5/15)** | the pre-registered endpoint read **negative** (degenerate pairing, 58/74 unpaired, class confound); the stratified re-analysis (carried 48→27, p = 0.0026) is hypothesis-grade and carries a **+4 no-contact re-draw** | 10-12 runs ~3 h + a pre-registration; tomato is scenario-blocked (2/15 < 4/15) | it is a *direct/policy-interface* lever (R5-5 makes that interface mechanism-research), the shipped hybrid canary never runs the trigger, and the single-species pool itself perturbs the supply (P1c). Nothing on the scripted line the goal is measured with |

**The two bar decisions to ask for in one message (they are both bars, not data):**

* **the B1c's adoption bar** — "is the shipped default's acceptance floor (0.75 of ten) the gate,
  or is the pooled placement + the mechanism stream the verdict?" The design says the orchestrator
  must decide; the data cannot. (§2.6 gives the runs that make either answer well-posed.)
* **the belt 0.15** — "may the shipped two-line scenario move to 0.15 m/s?" (+29 % measured, but it
  is a new scenario: references, the per-speed floor, the collector/canary branches).

**Not ranked, and why:** the two-line's *release* block (closed, §3), the two-line's *place* block
(closed by P3's geometry: a 30 mm inner shift = 0.2 s = 1.3 % of the span, against a 4 % bar), the
carry/close/capture families (5-6 negatives), and the interval/lock-on levers L2/L3-hot-arm
(measured null: bit-identical, or worse on a moved branch).

**One synthesis worth writing down:** the two-line's remaining span is dominated by *waiting for
fruit to arrive at the station* — the descent block's hover wait (1.7 s) plus the starvation/idle
(18-24 %). The belt screen is the only measured lever that attacks both at once, which is why it
outranks a faster descent profile even though "the descent is the biggest motion block".

---

## 5. Q4 — over- and underclaimed in the two records

### 5.1 `logs/p20i/B1C_RESULTS.md`

**Overclaimed**

1. §2.4 / Status: "the +4 of B over both is the re-anchor" — the placebo isolates the clock, not
   the census (§2.2). The supportable form: *the wall saving is the re-anchor's; the census delta is
   inside the placebo's own ±4/seed micro-history band.*
2. §2.3 "the empty-poll class shrinks 2 → 1" — the frozen bar was **zero**; B has 1, P has 3; n = 1-3
   events. Report it as a count, drop the class claim.
3. §3 "the design says the floor is a branch draw to be reported, not the verdict" — the design says
   the orchestrator must *decide* the ordering (§5 last ¶, §6 last ¶) and keeps the floor as "the
   gate of record" (§5 item 4). Do not read a decision as a waiver.
4. Status "the mechanism **and the multi-seed outcome** are positive" — the mechanism is positive;
   the outcome is non-inferior at best, and the design's composition-standardised report (endpoint
   4) is absent.
5. §1 "B >= A on every seed" as a support — true, but 2 wins + 1 tie is p = 0.25 (and 3/3 would be
   0.125). Quote it as a direction, never as an effect.

**Underclaimed (all measured, none in the record)**

1. **The throughput/interval read** (check 5): window 2.13 → 2.54 placed/min (+19 %), interval mean
   28.20 → 23.63 s, p90 42.5-45.4 → 36.7-40.3, idle 25-27 → 17-20 %, batch 2.09 → 2.48 — with the
   placebo at A's level. This is the lever's strongest evidence and the record does not contain it.
2. **The A-side identity** (check 4): **681/681** `[fruit]` lines vs the frozen pre-registration
   control, including the attempt windows — the design's own kill item 6 **and** its patch-A
   no-harm bar (design §5), the validity proof of the battery, and the proof that
   `FRUIT_READY_DIAG` is print-only. It also demotes the tree caveat (§2.5).
3. **The wall per attempt**, per seed: 20.50/20.50/20.85 → 18.70/18.55/18.55 (−8.8…−11.0 %) — the
   Gate-3-corrected endpoint for the B1, still missing for the B1c.
4. **The gap per seed** (5.10/5.20/5.20 → 3.20/3.25/3.30; P 5.10/5.15/5.20). Endpoint 3 asks for
   "every seed"; the record gives the pooled p50.
5. **The per-slot denominators** (42/60, 46/60, 41/60) and the per-slot success (70.0 / 76.7 /
   68.3 %). An empty poll removes an *attempt row*, so the reported 42/58 vs 46/59 excludes from the
   denominator exactly the outcome under study. Report x/60.
6. **The credit's exactness as a measurement**: 230 ticks = 1.917 s vs a measured 1.90 s/gap. The
   record says "the credit ladder holds"; the stronger statement is that the credit equals the
   saving to the logs' resolution — that is what makes the re-anchor *exact* rather than *active*.
7. **G4 on the whole battery, with the right floors** (check 8: 9/9 PASS). P23 quotes three logs
   and the wrong invocation (see 5.2).

### 5.2 `logs/p21i/P23_RESULTS.md`

**Overclaimed**

1. §3 "the patch fingerprint mismatch is the stale reference (`configs/motion_reference_patch.json`,
   the W6-A-era scenario…)" — **wrong twice.** That file (7b028049) is the **two-line** patch
   reference re-recorded in **P10-C.3** from `logs/p10c3/70_flip_seed5` (check 10), and it is the
   `190` two-line gate's reference. A single-arm patch run *cannot* match it: there is **no
   single-arm patch reference on disk** (all three patch references are two-line: `patch` P10-C.3,
   `_pre_p10c3` R5, `_patch_mass` P13). The mismatch is a **wrong-scenario** comparison, not
   staleness. Worse, the *remedy it implies* — "re-record it on adoption", borrowed from the AGENTS
   P1c density note — would overwrite the two-line gate's reference and break `190` for every
   two-line scenario. **The B1c needs no reference re-record at all**: it moves no motion profile,
   and design §5 item 5 expects B to *match* A's fingerprint.
2. §3 "G4 (motion budgets): PASS" — the budgets pass, but the quoted invocation
   (`105` with the default 0.75 floor and that reference) is the one the project already documented
   as wrong for this scenario (`logs/r5/run_patch_battery.sh` header, check 15), and it *fails* two
   of the battery's own runs (`623`, `723`: 13/20 = 65 %) — including an **A** run. A and B both
   have a 13/20 run, so the failure is the bar, not the lever. The correct G4 is `105 -m 0.5`
   **without** a fingerprint (9/9 PASS, check 8), or a new single-arm reference written from an A
   run.
3. §3 "the B1c therefore stands as the first lever in the P-series to pass **its battery** and the
   guard set" — it passes its *mechanism* and its *budget/no-harm* guards; endpoints 1 (unrun),
   4-proper (no per-class report), 6 (no B/P doubles) and the 3-seed acceptance are unmet (§2.4).
   The stronger, accurate sentence: "the first lever to pass its mechanism and its guards, with the
   outcome non-inferior and the census not separable from the placebo."
4. §2 table "BR vs B ≈ −2 points" — miscomputed; it is **+4.3** (§3.1).

**Underclaimed**

1. **The resync recovered 60 % of the trim's s5 loss** (12 of 20) — that is the quantitative
   statement about the re-anchor, and it is absent.
2. **Both BR arms are census-identical doubles** (13/13, 10/10) — a determinism datum.
3. **The release credit is unobservable** (check 14: zero `credit=` rows on that path), which is
   simultaneously the reason the "nominal credit" residual cannot be tested and the reason the
   Gate-4's thread-safety caveat is unguarded (§3.2).
4. **The untested cheap form** (trim + resync on the single arm, §3.4) — the closure reads as if the
   family's whole space were covered; it is not.

**Both records**

* Neither carries the **consumer inventory** a flip requires (collector, hybrid canary) — §2.4.3.
* Both use "the branch" as a shorthand for two different things (a *draw* vs an *unattributed
  actuator*). The Gate-4 already asked for the distinction; the P23 text still slips ("the trim's
  loss is not the nominal-credit mismatch a re-anchor fixes" is fine; "the branch" alone is not).

---

## 6. Bottom line

* **B1c: do not flip yet; it is one 50-minute block away from being decidable.** The mechanism and
  the timing channel are the strongest measured lever in the P-series (wall −9…−11 % per seed,
  interval −16 %, window rate +19 %, placebo-isolated, no-harm byte-clean, A-side identity 681/681).
  The census channel is inside the placebo's own spread and should stop being claimed. The two
  pre-registered endpoints that decide the interpretation (the `late_lo` stream) and the floor (the
  3-seed acceptance) were never run; run them, freeze the decision rule in §2.6, and hand the owner
  a *bar* question with the numbers attached.
* **Release: closed negative, correctly — with a corrected pooled cell (+4.3, not −2), two named
  residuals instead of one, and one one-line print (the release `credit=`) that both tests the
  nominal-credit hypothesis and guards the unlocked shared cursor.** The one cheap untested form is
  the single-arm trim+resync, and it is worth one battery because it settles a question that is
  currently blocking every wall lever.
* **Ranking: B1c finish (50 min) → single-arm trim+resync (75 min) → belt 0.15 (owner, 25 min) →
  the descent boundary / D3-proper (owner, multi-day) → the L3 class-matched (last).** Ask the two
  owner decisions together; they are both bars, and neither is a data gap any more.
* **The one number to fix before this document is quoted again:** `configs/motion_reference_patch.json`
  is the *two-line* reference. A single-arm run cannot match it, no re-record can fix that, and
  re-recording it would break `190`.
