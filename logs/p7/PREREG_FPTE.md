# P7 pre-registration: FPTE terminal-scored selection (C-1) - offline Phase-0 replay gate and the Tier-A battery plan

Written 2026-10-16, **before** the first run of `scripts/204_fpte_replay.py` and before any
number in `logs/p7/C1_REPLAY.md` was computed. Tier-C offline task: no simulator, no `src/`
change, no commits; writes scoped to `logs/p7/PREREG_FPTE.md`, `logs/p7/C1_REPLAY.md` and the
one replay script. R11-A.1 (`logs/r11/A1_RESULTS.md`) is the anchor: it closed the floor leg
and named the missing third leg - *which* of "which fruit" (choice) and "aimed where" (aim)
costs the accepted failure set. This document fixes the mechanism the third leg is built on
(#9 FPTE, `docs/papers/MECHANISMS.md` item 2; `logs/p6/B1_reread.md` section 9 + top-5 item 1),
the offline gate that decides whether it is worth a simulator battery, and the battery's
endpoints, kill rules and no-harm bar, all before looking.

## 0. The mechanism, in one paragraph

FPTE's transferable rule: for a slot, plan **all** candidates to their terminals (K <= 3-5),
score each **at the achieved terminal** - never reject a plan because it fell short of its
target - and execute the best-scoring one; cache the plan so it costs no ticks. Our plan step
already exists in-tree (`_reach_predict`, R10-A: the clipped fixed-point interception for the
moving catch) and the terminal map exists (`scripts/183_reach_intercept.py` bands, corrected
by R10-A.1). The off-policy part - "evaluate at the terminal" - is what R11-A.1's
choice-vs-aim decomposition waits for: the floored variant changed **which** floored fruit is
taken (min-travel instead of farthest-upstream) **and where the catch aims** (off-station
intercept instead of the station) at once, so the acceptance collapse 9/10 -> 4/9 is
unattributed between the two (A1_RESULTS.md section 5.3).

## 1. Arms (the battery's; B is not built in P7)

* **A = shipped farthest-upstream selection.** The shipped moving-catch selector
  (`select_target`, `_prefer_upstream`: farthest upstream among candidates at/above
  `_dynamic_select_floor()`), shipped station-relative aim. Comparator; in-scenario knob-off
  is byte-identical to the shipped default.
* **B = terminal-scored selection, default-off `FRUIT_FPTE_SELECT` (env `=1` enables; no
  shipped default change).** Same eligibility as A (the R11-A.1 shipped floor and the band
  feasibility stand: the floor is a *safety* invariant, not a score). For the K <= 5
  most-upstream eligible candidates compute `_reach_predict(fruit, vy, arm, base)` and score
  each at its planned terminal with the pre-registered lexicographic score
  ```
  S(c) = ( m_band(c),  m_res(c),  m_t(c) )
      m_band = min(up - eq, eq - dn)        # reach margin of the planned terminal, [m]; larger better
      m_res  = -|eq - y_int|                # predicted descent-end residue (the clip the catch-up must
                                            #   absorb), [m]; larger (0) better
      m_t    = -t_c(c)                      # earliest intercept, [s]; tie-break only
  ```
  and executes the max-S candidate's **clipped interception aim** (`y_int`) - the FPTE form:
  the executed terminal *is* the scored one. `eq`, `dn/up` from `_reach_predict`; `t_c` is the
  existing `travel_s` key. The **velocity-matched close margin** is treated as a *filter*, not
  a ranker: it is ~invariant on this catch (the handover is velocity-matched by construction -
  every logged handover reads ratio 1.00x), so a candidate whose measured handover ratio
  leaves [0.5, 1.5]x is flagged in the battery log and down-ranked (none expected). **Fallback
  reading (pre-registered, not a separate arm):** if Phase 0 shows the terminal *aim* is the
  unsafe half, the battery may be scoped to B0 = terminal-scored **choice** with the shipped
  station aim - one line, same score, aim = station - and the result reported under that name.
* **C = B + learned critic** (NavDP-style privileged contrastive critic over the terminal
  quantities; `logs/p6/B1_reread.md` #28) - built only if B's splits fail to move. **Not built
  in P7.**

Scope: scripted OpenArm moving-catch path only (`_prefer_upstream`), like the reach knob;
two-line and direct/policy paths never read the score. The literal R11-A.1 named
discriminators - *choice-pinned* (shipped farthest-upstream **choice** + reach **aim**) and
*aim-pinned* (reach **choice** + shipped **aim**) - are **not in any log**: the offline
Phase 0 substitutes the two observed proxies below (same-fruit-different-aim for the aim
lever; same-aim-different-fruit for the choice lever); if the gate is GO, the battery must
add the literal pair as its own arms.

## 2. Phase-0 gate (offline; decides GO/NO-GO to the battery)

All of it is text replay of existing logs via `scripts/204_fpte_replay.py` + one standalone
replica of `_reach_predict` (pure arithmetic; no simulator, no imports from
`fruit_sorting`). **Evidence set** (all existing, read-only):
`logs/r11/A1_12_accept_floored_diag.log` (M3, acceptance floored + diag),
`logs/r11/A1_15_accept_control.log` (M4 control), `logs/r11/A1_20_patch_floored.log`
(M5 patch floored + diag), `logs/r10/35_reach_settle60.log` (R10-A.1 arm B, patch),
`logs/r11/12_accept_reach_diag.log` (R11-A candidate diag, acceptance), and for context
`logs/r10/34_reach_bandfix.log`, `logs/r10/30_control.log`,
`logs/r11/A1_25_patch_control.log`, `logs/r10/31_reach.log`. The replica constants are the
source defaults (`_reach_setup_s` 0.60, `_reach_select_s` 1.5, hover speed 0.80, margin
0.15, `FRUIT_REACH_Y_INSET` 0.02, settle 60 ticks = 0.50 s where the run armed it), per
`tasks.py` lines 356-434.

**P0.1 - splits reproduction (exact match required).** Reproduce from the diag logs the
R11-A.1 section 2 table: acceptance instants 9/9/9 (feasible/shipped/eligible), sums
16/12/12; patch instants 19/17/17, sums 58/40/40; arm B (`logs/r10/35`) sums feasible 69 /
shipped 52 (no eligible field - pre-A1 format; report as "-"). Also: chosen `along`
min/p50/max (acceptance +0.449/+0.501/+0.619; patch +0.406/+0.491/+0.656; arm B
+0.257/+0.346/+0.535), chosen inside the floor (acceptance 0; patch 0; arm B 13/20), and the
catch-row aims (acceptance +0.03/+0.08/+0.13; patch -0.02/+0.03/+0.125; arm B
-0.08/-0.010/+0.08). Mismatch on any item = the replay is not on the R11-A.1 battery ->
**STOP (blocker)**, no verdict.

**P0.2 - per-slot observable record (no verdict, the table).** Per attempt of every run:
the select row (counts, chosen idx, `along`, `t_c`), the chosen fruit's catch row (`y_fruit`,
`vy`, `y_int`, `eq`, band, `t_desc`), the `met` row (`err`, `waited`, `catchup`), the
catch-up row (ticks, residual), the `dynamic descent` row (aim shift, fruit `dy`, `deadline`),
the attempt outcome (arm, grasped/placed, notes) and the starved-slot `active=` lists.
**Stated limitation, pre-registered as part of the finding:** the eligible *candidate sets*
are not in the logs (only counts and the chosen candidate's terminal; the `active=` list
exists only on the no-eligible path). The offline flip test therefore runs on *observed
choices across variants*, not on reconstructed sets; a candidate-set reconstruction needs a
new diag (named in C1_REPLAY.md as the battery prerequisite if the gate is GO).

**P0.3 - separation test.** On the patch battery (both lanes have both outcomes: right 9/11,
left 1/6), per arm, pre-registered components: `m_band`, `m_res`, `err`, catchup ticks,
catch-up residual, `waited`, deadline headroom (deadline - |fruit `dy`|), `t_c`. A component
*separates* iff the placed class's range and the failed class's range are disjoint with >= 2
samples per class (simple, honest at these n's; no p-values). Acceptance is reported but not
used (no lane has both outcomes there: left 0/5, right 4/4 - all failures are left, all
successes right).

**P0.4 - re-rank test (the missing third leg).** Two observed pair families:
* **(X) choice-varying, aim-held** - floored patch vs arm B patch, attempt by attempt, both
  reach runs (same aim machinery, different choice/floor rule). Fully aligned pool only up to
  the first divergent choice (documented: attempt 1 - arm B peach idx 12 `along=0.346`,
  `t_c` 2.932 s vs floored strawberry idx 5 `along=0.5334`, `t_c` 3.658 s); later attempts are
  cross-branch and labelled so.
* **(A) aim-varying, choice-held** - same fruit at the same attempt in two variants with
  different aims (control station aim +0.0172 vs floored reach aim, acceptance attempt 0 kiwi
  is the documented one; class-matched proxies elsewhere are labelled approximate). For these
  only `m_band(aim)` is computable on both sides (the control logs no `eq`), pre-registered as
  the only aim-side comparator.
For every pair: each candidate's score, each side's observed outcome; a pair is
**discriminating** iff the outcomes differ, **correct** iff the score prefers the observed
success, **tie** iff |score difference| is below the stated per-key resolution (m_band/m_res
1 mm, m_t 1 ms). Counts of pairs / discriminating / correct / inverted are the headline
numbers.

**P0.5 - predictor replication (required for P0.3/P0.4 to be admissible).** The standalone
replica must reproduce each logged catch row's `eq` from the logged inputs (`y_fruit`, `vy`,
`t_desc`, band) within **1.5 mm on >= 95 % of rows** (log rounding of `t_desc` at 2 decimals
alone moves `eq` by up to ~0.6 mm) and the `y_int` clip exactly; median |delta| reported.
Failure = **STOP (blocker)**.

**Decision rule (pre-registered).** GO to the Tier-A battery iff P0.1 passes AND P0.5 passes
AND P0.4 has >= 1 **correct discriminating** pair that involves a named R11-A.1 failing slot
(acceptance attempts 0/1/4/7/9; patch failures as logged), or, if P0.4 finds no
discriminating pair at all, P0.3 separates on >= 1 lane/component. **NO-GO in every other
case**, including: discriminating pairs exist but none is correct (the score ranks the winner
down), or no flips and no separation (the terminal quantities the score would use do not
separate the failing class - the failure set is post-catch, cf. W8-B/R6-B, and selection-time
terminal scoring has no measured headroom). A NO-GO is published with the failing leg named;
it is not repairable inside P7 (the score is fixed here; a variant needs its own
pre-registration).

## 3. The Tier-A battery (runs only if GO; no shipped default changes)

* Scenario pins: the two R11-A.1 batteries exactly - `accept.sh`'s scenario (single arm,
  scattered supply, 10 attempts, seed 5) and the W6-A patch battery (single arm, 20 attempts,
  seed 5); `CAND`-style reach arming per arm B's definition; Tier A solo via
  `scripts/154_claim_run.sh`; arms interleaved in one stretch, **N = 5 batteries per arm**
  (the house paired protocol for scripted claims; a single run is one quantized sample).
* **Primary endpoints (conversion):** no-fire slots (attempts with no eligible fruit) and
  chase slots (200-tick catch-ups, `[reach] fallback` fires) per arm vs A - pre-registered:
  A's 0 chase / control's no-fire counts must not rise; paired carried-not-placed (the
  `grasped=True placed=False` class) conversion, pooled over the 5 batteries, per arm.
* **Lock-on / timing:** `scripts/186_w6_report.py` lock-on latency and per-attempt span;
  non-inferiority bound <= +5 % vs A on the same stretch.
* **Per-leg motion:** every descent inside the shipped profile budgets (the `105`-style
  motion gate; the budget is 1.10x the profile peak) - **any** descent outside budget kills.
* **Per-scenario gate + fingerprint:** `accept.sh` (dynamic floor 0.75) + `fingerprint:
  matches`; the patch battery's own gate/reference (`105_motion_regression.py` with the
  scenario's reference, `-m` adjusted only as the two-line precedent allows); the single-arm
  reference is **not** re-recorded during the battery (only if adoption is ever decided).
* **Kill rules (any one stops the battery, no adoption):** any new failure reason; any
  descent outside budget; a chase/re-seat rise (the R11-A signature 0 -> 10 re-seats is the
  stated bar); a no-fire-slot increase; a carried-class rise. Rate deltas across
  configurations are **not** quoted as effects (quantized outcome, AGENTS section 2) - the
  battery quotes the per-leg motion, the splits and the fingerprints.

## 4. No-harm bar (must hold for every run, and for the tree)

* Knob-off control replays **byte-identically**: the acceptance's physics `[fruit]` stream vs
  the R11-A.1 control records (385/385) and the patch control vs `logs/r10/30_control.log`
  (643/643); B must not touch any path while `FRUIT_FPTE_SELECT` is unset.
* Knob-on acceptance reads **9/10 + `fingerprint: matches configs/motion_reference.json`**
  (or the battery's pre-registered floor if the knob-on branch is the treatment; the
  control arm of record is 9/10).
* Two-line untouched: the dense re-record 442/442 `[fruit]` lines vs the W7-A record and
  `scripts/190_towline_gate.sh` PASS.
* `scripts/selfcheck.sh` PASS; `configs/*` untouched.

## 5. Cost / cache estimate protocol (Phase 0, reported in C1_REPLAY.md)

Time the standalone replica over the logged inputs and report: microseconds per
`_reach_predict` evaluation, x K = 5 = planning cost per slot, as a fraction of one physics
tick (1/120 s); plus the cache statement (one transient pred dict per candidate at selection;
the chosen aim cached per attempt exactly like `_reach_aim_point`, so **no per-tick reads and
no added ticks on the critical path**). The observed max eligible per slot from P0.1/P0.2
bounds the practical K; the score is O(K) pure arithmetic.

## 6. Anti-goals and write scope

No simulator, no `src/` edit, no commits; writes only `logs/p7/PREREG_FPTE.md`,
`logs/p7/C1_REPLAY.md`, `scripts/204_fpte_replay.py`. No rate comparison across
configurations; every cross-branch read labelled; the R11-A.1 arm-B/floored rows keep their
records; the literal choice-pinned/aim-pinned arms are named as battery additions, not
invented offline.
