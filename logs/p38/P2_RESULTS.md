# P38 phase 2 — the lateral-refusal harness (the attribution endpoint)

Measured 2026-10-25. Pre-registration: `logs/p38/PREREG.md` + the binding
Gate-1 amendment `logs/p38/PREREG_A1.md` (A1-A6, A2b/A2c/A2d). Phase 1's
measurement record: `P1_RESULTS.md`. The lane: `.slim/deepwork/p38-drift-tail.md`.

**No shipped default changed.** The four knobs (`FRUIT_POLICY_REFUSE_DIAG`,
`..._END`, `..._RESEED`, `..._RESEED_MAX`) are all default **off** and
`presentation == "direct"` only (a `ValueError` on any other presentation). They
are **unset by default and the scripted line never reads them**: M4's
byte-identical `[fruit]` stream is the check, and for *this* change it is
**near-tautological** (`226_p38_m4.sh`'s own header says so - the scripted path
cannot reach the `if self._refuse_knobs` branch). The change that actually needs
evidence is the **trigger** one, and it is pinned by
`scripts/811_trigger_test.py` (the new lateral-refusal truth table and the END
predicate) **plus the analytic reorder equivalence**: moving the lateral check
to the "would-fire" position cannot change the return value for any input, since
it was already a hard `False` and the only thing that moved is *which* tick
carries the marker (`should_fire`'s docstring, §2). M4 did **not** run
`accept_policy.sh` - the four knobs raise on any presentation other than
`direct`, so the hybrid canary cannot read them; what that omission means is
stated in §6.

**The one-line answers.**

1. **The attribution works, deterministically.** On the forced-refusal band the
   `lateral refuse:` note appears on **15/15 episodes of all three arms**
   (P1 PASS), and the named terminal class replaces the unnamed end at a
   **median 510-562 ticks against A's 1335** (P3 PASS). The class is a failure
   (`success=False`) and stays in the rate denominator: the endpoint is
   attribution, not elimination.
2. **The lateral gate does not bind the learned close — measured, not argued.**
   `direct_fire = intercept or (policy_close and gate_refuse is None)` and
   `gate_refuse` is only the opt-in `X_MAX` guard, so a refused candidate can
   still be attempted by the learned close. On the forced band (|dx| = 1-2 cm,
   the fruit reachable) **5/15 and 6/15 episodes fired the close anyway and 3
   placed in each arm** — the trigger refused every episode and the shipped
   interface still succeeded on 3 of them. The END's C3 term ("the close never
   fired") is what keeps the class honest: it declines exactly those episodes
   (B 10/15, C 9/15). **The closure's scope is "no close fired before the
   fruit's departure"**, and the Gate-2 measurement (§3c) shows that is a *real*
   limit, not a formality: on the forced band **1 of 3 closes latched after the
   departure** (tick 506, `dy = -0.074 m`, 7.4 cm past the station - the jaw
   chased it downstream and closed on it), which is exactly `PREREG_A1.md`
   falsifier #1 and it **fires**. So the END's C3 term is **not a total
   closure**: the class over-claims on 1/15 episodes of the forced band (each a
   failure either way - the swap is `close -> did not follow the gripper` to
   `no firable fruit`), and any flip needs either a re-registered wording or a
   post-departure grace window. The shipped-band readout is still owed (the
   B-arm batch).
3. **The re-selection lever cannot act in this harness, and the reason is the
   feeder, not the supply.** The direct harness calls `spawner.update` only in
   the reset's feed loop (`rl_env.py:1602`) and `enforce_transport` every tick
   after it, so **no fruit is released during an episode**: the upstream window
   empties and the same-lane scan returns `None`. Measured: **54 scans in M1
   and 83 in M2, 0 non-empty** (the bound held: max 4 scans/refusal, 0
   adoptions). The endpoint P2a-i is therefore **unexercised, not failed**.
   (The amendment's hypothesis — the lane's ~46 % station starvation — is
   superseded by this measurement; the starvation number is the *free/driver*
   cadence, not the frozen episode.)
4. **On the shipped patch band (M3) the harness was exercised exactly once, and
   it landed in the control arm**: **1 refused episode in 150 = 0.67 %** (A run
   4 / seed 303, ep 14, orange, right, **x = 0.157** — the phase-1 drift tail),
   **0 in C**. So P4 (right-arm placed, run-level gate) **PASSes**
   (A 20/51 = 39 % vs C 25/58 = 43 %, delta **+0.039** [-0.138, +0.220]),
   P6 PASSes (fired-only cycle **-2.0 %**), and **P5 fails** — on the
   symmetric note-level rule, where both A-only keys (`lateral-refuse`,
   `fruit fell off the line`) come from that **one episode** and C had no
   refusal. That is a population artefact of a 1-event class, not a harm
   signal - and it is **structurally** so: an arm-only key at a 0.5-1.2 event
   expectation per 150 is necessarily arm-unique, and the DIAG's own
   `lateral-refuse` key is what trips the rule (§5). The lever performed
   **zero** actions in M3 (0 refusals, 0 adoptions, 0 END). Zero exposure means
   *no exposure*, not "inert by test".
5. **The dominant refused-episode terminal in this harness is not the timeout
   at all**: in M2 arm A it is `fruit fell off the line` (23/28) and the
   close-chase grip loss (5/28); **0 timeouts**. The END can only name the
   non-close ones, which is exactly what it does (19/21 in arm C). On the
   shipped band the same episode reads `lateral refuse:` + `fruit fell off the
   line` — attribution without a new outcome class.

---

## 1. The amendment trail (phase 1 + the Gate-1 review -> the measured design)

| # | the original | the amendment | why (measured) |
| --- | --- | --- | --- |
| **A1** (H1) | "provable refusal" -> "no firable fruit" | the class is named for the **trigger** and gated on a **measured joint closure**: the trigger refuses, `x` is frozen (checked per episode), **and the learned close never fired** from the reset through the fruit passing the station; the END fires at the *departure*, not at the latch | the close is a second fire path the lateral gate has never bound; it fired on 1/4 smoke episodes and 5-6/15 M1 episodes, 3 of them placing |
| **A2** (H2) | supply bands 0.10-0.17 / 0.10-0.36 | **A2b**: no supply band at all — M1 forces the refusal with `TRIGGER_LATERAL=0`, M2 with `0.06` (the P2b-era gate), both on the shipped supply | the 4 cm lane is not a band: delivered x 0.117-0.191 (**12 % above** the 0.173 floor) and the free-cadence envelope 0.080-0.529 (depenetration kicks push fruit off the **low** belt edge only: 0.080 against the 0.110 edge; the 0.529 maximum is still **inside** the 0.570 high edge) |
| **A2c** | 4 scans at the refusal instant | 1 scan per 60 ticks up to the 4-scan budget (a 1.5 s window inside the ~2.5 s to the station) | the same-instant form returned `None` in 3/3 refusals |
| **A2d** | P2 = "the refused episodes that fire" | **P2a-i** (the lever's correctness when a candidate exists) is the gate; **P2a-ii** (the incidence) and **P2b** (the outcome) are reported | "fires" cannot separate A from C: the close fires on refused candidates (2 of 4 refused episodes in the M2-A smoke) |
| **A3** (H3) | P4 `delta > -0.10`; P6 `<= +5 %` | run-level **unanimity**: fail iff all five per-seed-pair deltas are negative **and** the pooled delta <= -0.10 (P6 the mirror: all five > +5 %) | 47 right-arm episodes/arm at a 45 % base -> sd 0.10 -> a 1-sd point rule false-fails ~1 in 6 |
| **A5** | P5 "new in C" | note-level, **symmetric** (an arm-only key either way fails), the attribution notes collapsed to `lateral-refuse` | `113_rl_report.py` digit-normalises whole note strings |
| **A6** | the minors | "every never-fired" -> "every *refused*"; the budget 135 not 90; "10x" -> ~11x clustering; the check order before `x_edge_refusal`; `828`/`811` as prior art | — |

The amendment also corrects the registered M1 table's internal inconsistency
("A: 0 attributed notes" against a diag that is ON in *every* arm,
PREREG §2): A carries the note too, and P1 is read as the predicate's
incidence, not as an A/B contrast.

## 2. The implementation (default off, direct only, `PREREG_A1` §"knob table")

* **`FRUIT_POLICY_REFUSE_DIAG`** — one `lateral refuse: fruit x=... |dx|=...
  > lateral ... (station x=... -> x >= ... admitted; x frozen, permanent)` note
  per candidate at the first **provable** refusal: `should_fire` marks
  `info["lateral_refuse"] = dx` only on a tick that passes **every other gate**
  (`dy <= reach_eff`, `dy >= -0.05`, `speed > 1e-3`, `t_arrive <= lead`, the
  `assist` finger gate), i.e. after reordering the lateral check to the
  "would-fire" position just before `x_edge_refusal`. The return value is
  unchanged in either order, so the fire decision is identical for every input
  and the shipped path is byte-identical (pinned by `scripts/811_trigger_test.py`).
* **`FRUIT_POLICY_REFUSE_END`** — ends the episode at the fruit's **departure**
  (`dy <= -0.05`) with `no firable fruit: the trigger refuses (...) and the
  learned close never fired (best |jaw-fruit|=...cm) through dy=... (the fruit
  passed the station); x drift ...mm since the latch`, `outcome="no_firable"`.
  It re-checks `|dx| > lateral` at the end tick (the measured in-loop drift is
  up to 12.9 mm), so a fruit that drifted back inside the gate is not named.
* **`FRUIT_POLICY_RESEED` + `..._MAX`** — at a provable refusal, up to 4
  same-lane `select_target(..., lane=self._bin_index, exclude=seen)` scans (one
  per 60 ticks), adopting only a candidate that passes the lateral gate now and
  keeps the grade lane (the `Ff` guard); the adoption rebuilds `_goal`,
  `_belt_rest` and the protection exactly as the reset does, and is bounded by
  `..._MAX` = 2 per episode.
* One `[refuse] episode N: refusals= adopted= scans= empty= off= budget_left=
  policy_close_seen= no_firable=` row per episode, and a `refuse:` manifest
  block, so an arm is identified by its record and not by the note text.
* **Gate-2 addition (2026-10-25):** one `[refuse] close: tick=... dy=... (station
  frame; <= -0.05 is past the departure)` print at the learned close, `DIAG`-only
  and once per episode (one fruit-pose read, the documented-safe class). It
  exists so the END's closure can be read where it is claimed - `dy <= -0.05`
  is the END's own gate - and it is what measured falsifier #1 firing (§3c). It
  is a print, not a control read, so it cannot move a run.

## 3. M1 — the forced refusal (shipped supply, `TRIGGER_LATERAL=0`, SEED=5)

`HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1
FRUIT_SIZE_FILTER= FRUIT_SUPPLY_SCATTER=1 FRUIT_POLICY_TRIGGER=arrival
FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_DYNAMIC_PICK=1
FRUIT_RESET_ALIGN_DIAG=1 FRUIT_POLICY_SEED=11`, `moe_v13s` `61da390a`, 15
episodes per arm, one claim (`logs/p38/P2/M1_*.log`).

| arm | knobs | refused | no_firable | timeout | fell-off | close | placed | median ticks | median ticks @class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **A** | diag | **15/15** | 0 | 0 | 12 | 3 | 0 | 1335 | - |
| **B** | diag+end | **15/15** | **10** | 0 | 0 | 5 | 3 | 593 | **562** |
| **C** | diag+end+reseed | **15/15** | **9** | 0 | 0 | 6 | 3 | 553 | **510** |

* **P1 (attribution) PASS**: the note is on 15/15 in every arm; the delivered x
  of the refused candidates spans 0.224-0.397 (A), 0.229-0.369 (B), 0.244-0.365
  (C) — i.e. `lateral=0` refuses the whole shipped band, not just its tail.
* **P3 (the terminal class) PASS**: 0 timeouts in B and C; the class absorbs
  10/15 and 9/15 (the complement are the episodes whose learned close fired, and
  3 of those placed). The END cuts the cycle **1335 -> 562/510 ticks**
  (median), inside the registered <= 600 bar.
* **The bound**: C scanned 54 times (max 4 per episode, exactly the budget),
  **0 adoptions**, `RESEED_MAX` never approached. Fb' clean (no intercept fire
  on a below-gate candidate — there cannot be one: `lateral=0`).
* **The H1 read**: A's 3 closes and B/C's 5/6 are the second path; on the forced
  band they are **reachable** fruit (|dx| = 1-2 cm), so the interface picks them
  and places 3 — an "attempted-anyway" that *works*, and the reason the class
  cannot be defined without C3.
* **A ends by the line, not by the horizon**: 12/15 A episodes end
  `fruit fell off the line` (median 1335 ticks) because the refused fruit rides
  past the end of the belt; the timeout class does not appear at all on this
  band. The END names that class at 510-562 ticks.

### 3c. The Gate-2 reruns — the DIAG's neutrality and the close tick's `dy`

Two 15-episode runs on the M1 band (SEED=5, one claim, `scripts/225_p38_batch.sh
g2`, `logs/p38/G2/`, header `G2_header.txt`): **`G2_diag0` with no refuse knob at
all** and **`G2_diag1` with `FRUIT_POLICY_REFUSE_DIAG=1` only** (the arm the
batch called "A"). They close the two conditions the batch left open. Control
first, so the order is confounded with the loop's own wall-clock drift, as every
direct run here is.

| run | knobs | n | close | fell-off | timeout | placed | median ticks | classes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `G2_diag0` | (none) | 15 | 5 | 10 | 0 | **2** | 1362 | fell-off 10, close-chase 2, carried 1, placed 2 |
| `G2_diag1` | DIAG | 15 | 3 | 12 | 0 | **0** | 1360 | fell-off 12, close-chase 2, carried 1 |
| `M1_A` (the batch) | DIAG | 15 | 3 | 12 | 0 | **0** | 1335 | fell-off 12, close-chase 3 |

* **H4 (does the DIAG act?) - the measured pair, and what it can carry.** The
  pair agrees on **6/15** `(arm, category)` and **9/15** outcome classes, and
  the class counts are close (carried 1/1, close-chase 2/2, fell-off 10/12,
  placed 2/0). It does **not** demonstrate neutrality at n=15: the two DIAG=1
  samples (`M1_A` vs `G2_diag1`) agree on **12/15 and 14/15**, i.e. the loop's
  own run-to-run agreement is *not constant* (the two DIAG arms stayed in one
  attractor to ep 11; `diag0` left it at ep 4, where its ep-3 fell-off ends 90
  ticks earlier and the belt state changes) - so one pair can differ by more
  than a same-knob repeat does. What the pair does show is that the DIAG arm's
  *class* structure is the control's, and the construction argument carries the
  rest: with `END`/`RESEED` off, `_track_refuse` writes only `_notes`, the
  refusal bookkeeping and one fruit-pose read per refusal (the documented-safe
  read class) - none of it is a control input. **The batch's claim "A behaves
  as the control" is therefore replaced by this pair plus that argument**, not
  by a bit-identity claim.
* **H1 (when does the close latch?) - the falsifier fires.** `G2_diag1` prints
  the close tick's own `dy` (`[refuse] close: tick=... dy=...`, `DIAG`-gated,
  one fruit-pose read per episode):

  | close | tick | `dy` (station frame) | reading |
  | --- | --- | --- | --- |
  | ep 2 (kiwi) | 430 | **+0.071 m** | before the departure |
  | ep 9 (pear) | 506 | **-0.074 m** | **after** the departure (the END's gate is `dy <= -0.05`) |
  | ep 13 (kiwi) | 171 | **+0.314 m** | before the departure (the ACQ lead meets it upstream) |

  So the learned close **can** latch after the fruit's departure: on ep 9 the
  jaw chased the fruit 7.4 cm past the station and closed on it
  (`|jaw-fruit| = 5.9 cm`, then `fruit did not follow the gripper`). The END
  would have ended that episode ~24 ticks earlier (`dy = -0.05` at 0.12 m/s),
  i.e. it changes that episode's terminal from a close-chase to
  `no firable fruit`. Both are failures, so the sample's success count does not
  move - but **`PREREG_A1.md` falsifier #1 fires**, and the consequence is
  registered: **the END's C3 is not a total closure.** Read the class as "no
  close fired *before* the departure", and treat a flip as needing a
  re-registered wording (with the measured post-departure close rate, 1/15
  here) or the named post-departure grace window. The shipped-band readout
  stays owed (the B-arm batch).

## 4. M2 — the mixed refusal (shipped supply, `TRIGGER_LATERAL=0.06`, seeds 5/101/202)

| run | arm | n | refused | adopted | converted | placed (refused) | scans | max/ep | refused-episode terminals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A | 15 | 7 | 0 | 0 | 2 | 0 | 0 | close-chase 3, fell-off 4 |
| 1 | C | 15 | 8 | 0 | 0 | 0 | 32 | 4 | no_firable 8 |
| 2 | A | 15 | 11 | 0 | 0 | 0 | 0 | 0 | close-chase 1, fell-off 10 |
| 2 | C | 15 | 7 | 0 | 0 | 0 | 28 | 4 | close-chase 1, no_firable 6 |
| 3 | A | 15 | 10 | 0 | 0 | 0 | 0 | 0 | close-chase 1, fell-off 9 |
| 3 | C | 15 | 6 | 0 | 0 | 1 | 23 | 4 | close-chase 1, no_firable 5 |
| **pool** | **A** | 45 | **28 (62 %)** | 0 | 0 | 2 | 0 | 0 | **fell-off 23, close 5, timeout 0** |
| **pool** | **C** | 45 | **21 (47 %)** | **0** | **0** | 1 | **83** | 4 | **no_firable 19, close 2** |

* **The refused fraction is 62 % (A) / 47 % (C)** — above the registered
  "~28 %" and above the amendment's 35-50 % estimate; the gate admits
  `|dx| <= 0.06` and the shipped `|dx|` distribution puts ~half its mass outside
  it. Reported as measured (A2b's rule).
* **P2a-i UNEXERCISED**: **83 scans, 0 non-empty** — the selector never returned
  a candidate, so the lever's adoption logic was never reached. Bound held
  (4 scans/refusal, 0 adoptions).
* **P2a-ii (reported)**: adoption among refused **0/21**; the *cause* is the
  frozen feeder (see the one-line answers), not the lane's starvation — the
  amendment's 46 % hypothesis is superseded.
* **P2b (reported, not gated)**: placed among refused **A 2/28 (7 %) vs C 1/21
  (5 %)**, one-sided Fisher p = 0.82. Pooled success **9/45 in both arms** — the
  lever moves the attribution, not the outcome, on this probe.
* **The pairing is broken (13/45 agreement)**, as A4 predicted: an early END
  changes the episode's belt state, so episode *k* is a different fruit in A and
  C. The unpaired Fisher is the read; the paired table is descriptive only.
* **Fe clean**: no converted episodes (0 adoptions), so no trade is possible;
  A's overall carried rate is 11/45 (24 %).

## 5. M3 — the shipped patch band (the safety endpoints)

`FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25`, the shipped
gate (`lateral=0.16`), `FRUIT_ARM_PARK` unset (the shipped deployment), seeds
77/101/202/303/404, 15 episodes per run, **A then C interleaved in one claim**
(`logs/p38/P3/M3_*.log`, header `M3_header.txt`).

| run (seed) | arm | n | right n | right placed | right rate | left placed | refused | fired-only median cycle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 (77) | A | 15 | 8 | 2 | 25.0 % | 0 | 0 | 1893 |
| 1 (77) | C | 15 | 10 | 3 | 30.0 % | 0 | 0 | 1820 |
| 2 (101) | A | 15 | 9 | 3 | 33.3 % | 1 | 0 | 1873 |
| 2 (101) | C | 15 | 9 | 2 | 22.2 % | 0 | 0 | 1879 |
| 3 (202) | A | 15 | 8 | 5 | 62.5 % | 0 | 0 | 1807 |
| 3 (202) | C | 15 | 12 | 4 | 33.3 % | 0 | 0 | 1857 |
| 4 (303) | A | 15 | 12 | 3 | 25.0 % | 0 | **1** | 1865 |
| 4 (303) | C | 15 | 14 | 6 | 42.9 % | 0 | 0 | 1828 |
| 5 (404) | A | 15 | 14 | 7 | 50.0 % | 1 | 0 | 1809 |
| 5 (404) | C | 15 | 13 | 10 | 76.9 % | 0 | 0 | 1773 |
| **pool** | **A** | 75 | **51** | **20** | **39.2 %** | 2 | 1 | - |
| **pool** | **C** | 75 | **58** | **25** | **43.1 %** | 0 | **0** | - |

* **P4 (the A3 run-level gate) PASS**: per-pair deltas **+0.050, -0.111,
  -0.292, +0.179, +0.269** — not all negative, so the unanimity condition does
  not hold; pooled **+0.039** with the Newcombe 95 % interval
  **[-0.138, +0.220]**. The original point rule would have read the same
  (PASS) here; the gate's purpose is the false-fail it prevents
  (1-sd ≈ 1-in-6 at 47 episodes/arm), and the per-pair spread (+0.269 to
  -0.292) shows exactly the noise the pooled number hides.
  **The un-parked right-arm base is 39.2 %, not the 45 % the amendment
  assumed** (A 20/51). The P35 mechanism is the *inactive left arm occluding
  the right arm's fruit*, so the un-parked **right** rate is the depressed one;
  the left's own 2/24 (C 0/17) is a separate number that drags the **pooled**
  total (A 22/75), not the right-arm base. The right is the primary as
  registered.
* **Exposure**: **1 refused episode in 150 (0.67 %)**, against the patch-band
  expectation 0.31 % (<0.173) / 0.77 % (<0.180) — the phase-1 number, not the
  pooled 0.06 %. It landed in **A** (run 4, seed 303, ep 14, orange, right,
  **x = 0.157**, `|dx| = 0.176`), so the treatment arm saw **0** refusals and
  the lever executed **no action** in M3 (0 adoptions, 0 END, 0 scans).
* **P5 (note level, symmetric) FAIL**: A-only `lateral-refuse` and
  `fruit fell off the line`; C-only none. Both A-only keys are **the same
  episode** (its notes are `lateral refuse: ...` + `fruit fell off the line`),
  and C had no refusal to attribute. The rule is the pre-registered one and it
  fires; the *substantive* reading is that a 1-event class cannot be compared
  across arms, and that the batch contains no evidence of harm (the lever did
  nothing in C). This is the P37 lesson in the other direction: a mechanical
  rule with no severity.
  **P5 is also structurally a false-fail, and that is worth naming**: an
  arm-only key with a **0.5-1.2 event expectation per 150 episodes** (A5's own
  exposure arithmetic) is **necessarily arm-unique** - a single event lands in
  one arm by construction, so the symmetric rule fires whenever the exposure is
  realised, whichever arm it lands in. Here the DIAG's own `lateral-refuse` key
  is what fires it, i.e. the *diagnostic* counts against the treatment that did
  nothing. The literal read stays **`not adopted`** (the pre-registered rule is
  the rule), and a **power-controlled form** of the reason endpoint - e.g. the
  reason sets conditioned on an exposure-matched sub-population, or the
  refusal-class note compared only where both arms have >= k refusals - belongs
  in the **next registration**, not as a post-hoc repair of this one.
* **P6 (the A3 run-level gate) PASS**: per-pair fired-only cycle
  **-3.9 %, +0.3 %, +2.8 %, -2.0 %, -2.0 %**, pooled **-2.0 %**; not all five
  above +5 %, so no harm signal. (The `no firable fruit` class does not appear
  in M3: 0 in both arms, so the fired-only population is every episode.)
* The total success is **A 22/75 vs C 25/75**; the right-arm arm-mix differs
  (51 vs 58) because **the direct loop is not reproducible, not because the
  lever changed the reset**: A and C draw the same ep-0 fruit (apple, C,
  y = +0.642) and already differ at ep 1 (peach, A, y = +0.532 vs +0.546), and
  C executed zero actions in this batch. The variance is the rendered-frame
  non-reproducibility every direct A/B in this repository carries (AGENTS §3b),
  so the standardised read is P4's paired-per-seed table, not the pooled total.

## 6. M4 — the scripted no-harm

`scripts/accept.sh` twice (knobs unset, then all four set) plus
`selfcheck.sh`, one claim (`logs/p38/M4/`).

| run | knobs | result | `[fruit]` lines | fingerprint |
| --- | --- | --- | --- | --- |
| A | unset | **6/10** (the shipped tree's rate-only result, `diverted=0`, 15.0 s/attempt) | 376 | `matches configs/motion_reference.json` |
| B | `DIAG=1 END=1 RESEED=1 MAX=2` | **6/10**, identical | **376, md5 `bc7ca8f0` both** | `matches` |

* The two `[fruit]` streams are **byte-identical** (`cmp` on
  `A_fruit.txt`/`B_fruit.txt`: identical; the full logs differ only in the
  startup timestamps/pids of lines 1-6).
* The motion gate reads the same 10 descents (worst `|v|max` 0.110 vs budget
  0.160-0.161, lurch 0.017 vs 0.291) and the same carry cone report (worst held
  grip 1.27x, the P32/W8-B class).
* `selfcheck.sh` **PASS: 0 failures, 1 skipped** (`motion budgets`).
* The 6/10 and the `exit=1` are the **shipped tree's** state, not this phase's:
  AGENTS records the same 6/10 + fingerprint-matches pair for P35/P36/P37.
* **What M4 does and does not prove.** It proves the scripted line's `[fruit]`
  stream is unchanged with the knobs set, which is **near-tautological for this
  change** (the scripted path never reaches the refuse branch); the meaningful
  pin for the `trigger.py` edit is `scripts/811_trigger_test.py` plus the
  analytic reorder equivalence (§2). **`accept_policy.sh` was not run**: the
  four knobs raise on any presentation other than `direct`, so the hybrid
  canary is structurally unable to read them. That is an omission of *coverage
  of the shipped default* (the canary would run with the knobs unset, i.e. the
  same bytes it always evaluates) - not evidence about the direct interface.

## 7. The verdict and the recommendation

**The pre-registered decision rule reads `not adopted`** — P5 fails (the 1-event
artefact above) and P2 is unexercised. That is the literal verdict and it is
published as such. Read part by part:

| endpoint | read | what it means |
| --- | --- | --- |
| **P1** attribution | **PASS** (15/15 x3) | the refusal predicate is live, named and deterministic; the DIAG is a note-only instrument - the Gate-2 pair reads 9/15 class agreement (6/15 fruit) against the DIAG=1 repeat's 14/15 (12/15), so neutrality rests on the construction argument, not on a bit-identity claim (§3c) |
| **P3** terminal class | **PASS** (0 timeouts; 10/15 + 9/15 named; median 562/510 vs 1335 ticks) | the class replaces the *unnamed* end and cuts the cycle in half on a forced refusal - **but the closure is partial**: 1 of 3 closes latched *after* the departure (§3c), so `no firable fruit` over-claims on 1/15 and falsifier #1 fires |
| **P2a-i** reselection | **UNEXERCISED** (54 + 83 scans, 0 candidates) | the harness cannot offer an alternative candidate: the feeder does not advance inside an episode |
| **P2b** outcome | reported (0/21 vs 2/28 placed; p = 0.82) | no outcome effect measurable at this n, and none possible without a functioning re-selection |
| **P4** safety | **PASS** (+0.039, [-0.138, +0.220]) | no harm signal; 39.2 % right-arm base, 1-event exposure |
| **P5** reasons | **FAIL** (1 episode's notes, control arm) | a 1-event comparison, not a harm signal; the lever did nothing in M3 |
| **P6** cycle | **PASS** (-2.0 %) | no cycle cost |
| **P7** no-harm | **PASS** (376/376 identical, fingerprint matches, selfcheck) | the scripted/policy-shipped line is untouched |

**Substantive recommendation (no shipped default changes in phase 2):**

1. **`FRUIT_POLICY_REFUSE_DIAG` — recommended as the direct loop's diagnostic**
   (owner sign-off): it is a note-only instrument (§3c: the pair plus the
   construction argument; the measured pair cannot resolve neutrality at n=15
   and does not claim to), it named the shipped band's single refusal
   (`x = 0.157`) that would otherwise have read only `fruit fell off the line`,
   and it is what makes the class measurable at all.
2. **`FRUIT_POLICY_REFUSE_END` — not adopted, keep it as the measurement
   interface.** Its M1 evidence is strong (attribution + 60 % shorter cycle) and
   its M3 exposure was 0, so a shipped-band safety read does not exist yet; the
   named next step is a **B-arm** M3-style batch (A vs B) before any flip.
   **`PREREG_A1.md` falsifier #1 has FIRED on the forced band**: 1 of 3 closes
   latched 7.4 cm past the station (§3c), so C3 is not a total closure and the
   END changes that episode's terminal (a failure either way, but a different
   one). Any flip therefore needs a **re-registered** class definition - the
   measured post-departure close rate quoted with the name, or the
   post-departure grace window - and the **shipped-band readout** of the close
   tick is owed in the B-arm batch's report.
3. **`FRUIT_POLICY_RESEED` — not adopted.** It is **structurally inert** in this
   harness (0 candidates in 137 scans across M1+M2): the direct loop freezes the
   feeder for the episode. A re-selection needs the feeder live (a scenario
   change the checkpoints were not trained on), which is its own phase.
   **What `811` pins is the `should_fire` lateral key and `no_firable_ready`**,
   not the adoption path: the `_goal` rebuild, the protection handover and the
   `Ff` guard have **no offline test** and **no episode exercised them**.
4. **The `no firable fruit` note stays a failure** in every rate; nothing here
   removes an episode from a denominator.

## 8. What this does not show

* **No rate.** M1/M2 are probes on a gate the shipped interface does not run
  (`lateral=0` / `0.06`); their success counts are not the shipped rate.
* **No re-selection behaviour at all.** The adoption path (the `_goal` rebuild,
  the protection handover, the `Ff` guard) is implemented and **not** pinned
  offline (`811` pins `should_fire`'s lateral key and `no_firable_ready` only),
  and **no episode exercised an adoption**: the feeder does not advance inside
  an episode, so the harness cannot offer an alternative candidate. A future
  phase would have to make the feeder live during the policy phase (which
  changes the direct scenario the checkpoints were trained on) — a scene/harness
  change with its own pre-registration.
* **The END's residual is now measured, not hypothetical.** The closure is "no
  close fired **before** the fruit's departure", and §3c finds one close at
  `dy = -0.074 m` (7.4 cm past the station) on the forced band: a close that
  latches **after** the departure happens, and a policy that chased the fruit
  **downstream** afterwards is therefore a live path, not an excluded one. That
  is `PREREG_A1.md` falsifier #1 firing, so the END's class over-claims on 1/15
  of the forced band, and a flip needs the re-registered definition or a
  post-departure grace window. A's behaviour still bounds the *success* side
  weakly: on A the refused fruit are either picked (the close) or lost to the
  line end, and no downstream chase produced a placement in this sample.
* **Three latent defects, named as follow-ups (none fixed here, all
  direct-only and inert at the shipped defaults):**
  **(a)** `_reseed_step` calls `spawner.protect(adopted)` and never unprotects it
  when the episode ends (the reset sets only the scalar `spawner.protected`), so
  an adoption leaks one index into `protected_indices` for the rest of the
  process. It is inert on the direct path (its selection does not exclude the
  set) and it is one more reason the reseed stays direct-only: the
  scripted/bimanual callers *do* read `protected_indices` in their selectors.
  **(b)** the END's `dy` is measured against the captured **station**, while
  `should_fire` measures `dy` in `FRUIT_POLICY_TRIGGER_FRAME`'s frame (default
  `station`; `jaw` moves the trigger's own downstream gate). Inert at
  `FRAME=station`.
  **(c)** the END is evaluated **before** the tick's fire decision and reads
  neither `intercept` nor the P4b2 `present` adoption, and `_policy_best_gap` is
  **per-episode**, so the note's "best |jaw-fruit|" can span a pre-reseed
  candidate. Each is a code comment at the harness (`rl_env.py`, "Known
  defects").
* **The class is rare on the shipped gate** (0.31-0.77 % of patch episodes, P1
  §1[2]); M3 cannot measure its removal, only the absence of harm.
* **The lateral gate's own reach limit** (`FRUIT_POLICY_TRIGGER_X_MAX`) is out
  of scope: the guard was off in every phase-2 run and its high-x refusal class
  is a different, operator-selected one.

## 9. Files, pins, and how to re-check

| artefact | what it is |
| --- | --- |
| `logs/p38/PREREG_A1.md` | the binding Gate-1 amendment (A1-A6, A2b/A2c/A2d) |
| `scripts/224_p38_probes.sh` -> `logs/p38/z1_supply_*.log`, `z2_drift_m1.log` | the H2 supply verification (the bands it rejected) |
| `scripts/225_p38_batch.sh` -> `logs/p38/P2/`, `logs/p38/P3/`, `logs/p38/G2/` | the M1+M2 and M3 batches, and the Gate-2 DIAG=0/1 pair |
| `scripts/226_p38_m4.sh` -> `logs/p38/M4/` | the scripted no-harm pair + selfcheck |
| `logs/p38/p2_report.py` | the report (`--self-test` pins the parsers and the exact tests; `--g2` reads the pair) |
| `logs/p38/P2_report.txt` | this phase's printed analysis |

Tree pins at measurement time: see `logs/p38/MD5.txt` (before/after) and each
batch's `*_header.txt` (`rl_env.py` `f25f6b61`, `policy/trigger.py` `b09d3cb2`,
`tasks.py` `cdde6bd2` unchanged, `scripts/811_trigger_test.py` extended).
**The Gate-2 rerun added one diagnostic print to `rl_env.py`** (the
`[refuse] close:` row, `DIAG`-gated, no control read), so `G2_header.txt` pins
`rl_env.py` **`dba80de6`**, `scripts/225_p38_batch.sh` **`eae2d89a`** and
`scripts/811_trigger_test.py` **`00ebe772`**; the shipped defaults are
unchanged and the M1/M2/M3 evidence keeps its own batch-time pin. `P2_report.txt`
was re-generated with the G2 section after the reruns (its md5 therefore moves;
the M1/M2/M3 sections are byte-identical).
`checkpoints/moe_v13s/policy_best.pt` `61da390a` is the evaluated checkpoint in
every arm.

Re-check:

```bash
python3 logs/p38/p2_report.py --self-test
python3 scripts/811_trigger_test.py
python3 logs/p38/p2_report.py --m12 logs/p38/P2 --m3 logs/p38/P3
python3 logs/p38/p2_report.py --g2 logs/p38/G2
```
