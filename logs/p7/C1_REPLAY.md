# C1 replay: FPTE terminal-scored selection - Phase-0 offline verdict

Offline Phase-0 gate of `logs/p7/PREREG_FPTE.md` (written first, 2026-10-16), run by
`scripts/204_fpte_replay.py` (read-only text replay + one standalone `_reach_predict`
replica; no simulator, no `src/` change). Evidence: the existing R11-A.1 / R10-A.1 / R11-A
logs only. Full per-slot dump: run `python3 scripts/204_fpte_replay.py` (self-test
`--self-test` PASS). This file records the numbers and the verdict.

## 0. Verdict

**NO-GO to the pre-registered Tier-A battery (A = shipped farthest-upstream vs B =
terminal-scored choice + reach aim, floor kept).** Phase 0 passes its two mechanical
items (splits reproduced exactly; the predictor replica validates), but the re-rank
evidence does not transfer to the pre-registered arm B: the one *aligned* choice flip
(patch a01) prefers a candidate **below the shipped floor** (B is ineligible by §1's
floor invariant), the one clean same-fruit aim flip (acceptance a04) prefers the
**shipped station aim** (B's aim is the reach intercept), P0.3 finds **no terminal
component that separates outcomes**, and the pair-level score is **4 correct / 4
inverted at n = 8** (a coin flip). The failing class is post-catch: the pre-registered
test finds no terminal component separating the outcomes (success and failure ranges
overlap on every one, section 5), and the failures differ from the successes only
downstream of the catch; the left lane, where five of the patch's seven and all five
acceptance failures live, has one placed sample per variant and is untestable under the
frozen n >= 2 rule, not tested-negative. Only the patch slot-1 crush-and-bat is
terminal-anomalous (err -135.5 mm, 73-tick catch-up). The pre-registered rule's letter
(>= 1 correct discriminating pair on a named failing slot) is met by four pairs - the
audit in section 8 shows why none of them is evidence about B. Three named
continuations, each needing its own pre-registration, are in section 9.

## 1. What was replayed

| role | log | md5 | settle |
| --- | --- | --- | --- |
| acceptance floored + diag (M3) | `logs/r11/A1_12_accept_floored_diag.log` | `51b06307...` | 60 ticks |
| acceptance floored, no settle | `logs/r11/A1_13_accept_floored_nosettle.log` | `1a5b867e...` | 0 |
| acceptance control (M4) | `logs/r11/A1_15_accept_control.log` | `85bc83e7...` | 0 |
| R11-A candidate acceptance (4/10) | `logs/r11/12_accept_reach_diag.log` | `7590c1d1...` | 60 |
| patch floored + diag (M5) | `logs/r11/A1_20_patch_floored.log` | `4a4a42de...` | 60 |
| patch control (M7) | `logs/r11/A1_25_patch_control.log` | `1ad74883...` | 0 |
| R10-A.1 arm B (patch, settle 60) | `logs/r10/35_reach_settle60.log` | `58cc8ef7...` | 60 |
| R10-A.1 corrected-band (patch, settle 0) | `logs/r10/34_reach_bandfix.log` | `95ac6131...` | 0 |
| R10-A treatment (patch) | `logs/r10/31_reach.log` | `faa4cd61...` | 0 |
| patch control of record | `logs/r10/30_control.log` | `63501049...` | 0 |

Replay script md5 `27c35ee5...`. Read-only: nothing outside `logs/p7/` is written.
(`A1_13` was run without `FRUIT_REACH_DIAG` and carries no `[reach]` rows; it
contributes no terminal rows and no P0.5 entry.)

## 2. P0.5 - the `_reach_predict` replica (required leg, PASS)

Standalone fixed point, base = `FRUIT_REACH_SETUP_S` 0.60 + settle, hover speed 0.80,
margin 0.15 s, each row's logged `t_desc`; compared to every logged `eq` (the log rounds
`t_desc` to 10 ms, worth up to ~0.6 mm in `eq`):

| log | rows | median abs delta | p95 | max | <= 1.5 mm | y_int (same tol) |
| --- | --- | --- | --- | --- | --- | --- |
| acceptance floored | 9 | 0.49 mm | 0.55 | 0.59 | 100 % | 9/9 |
| R11-A candidate | 10 | 0.60 mm | 0.68 | 0.69 | 100 % | 10/10 |
| patch floored | 17 | 0.51 mm | 0.60 | 0.61 | 100 % | 17/17 |
| patch arm B | 20 | 0.63 mm | 0.73 | 0.77 | 100 % | 20/20 |
| R10-A.1 bandfix | 20 | 0.55 mm | 0.76 | 0.79 | 100 % | 20/20 |
| R10-A treatment | 20 | 0.59 mm | 0.76 | 0.79 | 100 % | 20/20 |

The pre-registered `y_int` "exactly" check was applied at the same 1.5 mm tolerance
(boundary rows cannot be exact under `t_desc` rounding); no row misses even there.
The replica can therefore score terminals offline from logged inputs.

## 3. P0.1 - splits reproduction (required leg, PASS on every item)

Re-derived from the diag logs vs the R11-A.1 section-2 table:

| reading | R11-A.1 says | replayed |
| --- | --- | --- |
| acceptance instants reach/shipped/eligible | 9/9/9 | 9/9/9 |
| acceptance sums feasible/eligible/shipped | 16/12/12 | 16/12/12 |
| acceptance chosen `along` min/p50/max | +0.449/+0.501/+0.619 | +0.449/+0.501/+0.619 |
| acceptance chosen inside floor | 0 | 0 |
| acceptance aims min/p50/max | +0.03/+0.08/+0.13 | +0.03/+0.08/+0.13 |
| patch instants reach/shipped/eligible | 19/17/17 | 19/17/17 |
| patch sums feasible/eligible/shipped | 58/40/40 | 58/40/40 |
| patch chosen `along` min/p50/max | +0.406/+0.491/+0.656 | +0.406/+0.491/+0.656 |
| patch chosen inside floor | 0 | 0 |
| patch aims min/p50/max | -0.02/+0.03/+0.125 | -0.02/+0.03/+0.125 |
| arm B sums feasible/shipped | 69/52 | 69/52 |
| arm B chosen `along` min/p50/max | +0.257/+0.346/+0.535 | +0.257/+0.346/+0.535 |
| arm B chosen inside floor | 13/20 | 13/20 |
| arm B aims min/p50/max | -0.08/-0.010/+0.08 | -0.08/-0.010/+0.08 |

The floor invariant (`eligible == shipped` per slot) holds: the patch's two extra
reach-rule instants carry `eligible=0`, and the sums are equal (40/40).

## 4. P0.2 - the per-slot record (the data the logs carry)

`scripts/204_fpte_replay.py` prints the full table; the fields are the select row,
the chosen fruit's catch row (`y_int`, `eq`, band, `t_desc`), the `met` row (`err`,
`waited`, catch-up), the descent row, the outcome and the starved `active=` lists.
**The limitation, confirmed: the eligible candidate sets are not printed** - only the
counts and the chosen candidate. The `active=` lists exist only on the no-eligible
path. The offline re-rank below is therefore an *observed-choices* test across
variants, not a reconstructed-set test.

Two rows that carry the whole argument (from the printout):

* acceptance floored a01 (left tomato, failure): `met err=+14.4 mm`, `cu 13t/6.0 mm`,
  `waited 62` - a clean terminal; the loss is later (the left hold).
* patch floored a01 (right strawberry, failure): `met err=-135.5 mm`, `cu 73t/6.0 mm`
  - the one failure with an anomalous terminal (the late arrival / crushed close).

## 5. P0.3 - separation (patch battery; required leg, NEGATIVE)

Both patch lanes have both outcomes (floored left 1P/5F, right 9P/2F; arm B left
1P/4F, right 12P/3F), and **no pre-registered component separates** them. The
right-lane ranges:

| component | floored placed (n=9) | floored failed (n=2) | arm B placed (n=12) | arm B failed (n=3) |
| --- | --- | --- | --- | --- |
| `m_band` [m] | -0.288..-0.040 | -0.084..-0.082 | -0.133..+0.054 | -0.027..+0.027 |
| `m_res` [m] | 0.040..0.288 | 0.082..0.084 | 0.000..0.133 | 0.000..0.027 |
| `err` [m] | 0.010..0.014 | 0.011..0.136 | 0.000..0.017 | 0.001..0.003 |
| catch-up ticks | 10..14 | 12..73 | 10..19 | 12..34 |
| catch-up res [mm] | 5.7..6.0 | 6.0..6.0 | 5.6..6.0 | 5.8..5.9 |
| `waited` | 63..82 | 60..77 | 60..78 | 60..60 |
| deadline headroom [m] | 0.001..0.018 | 0.001..0.042 | 0.001..0.064 | 0.012..0.034 |
| `t_c` [s] | 3.28..4.98 | 3.17..3.66 | 2.93..4.23 | 2.95..2.99 |

Every row overlaps; the failures differ from the successes only downstream of the
catch (the carry/place outcome). The acceptance cannot be used for separation (its
left lane is 0/5, its right 4/4 - no lane has both outcomes), exactly as
pre-registered. Quantitatively: the acceptance's failure terminal errors are
+11.3/+14.4/+12.9/+11.8/+12.8 mm vs the successes' +11.1/+10.9/+11.4/+10.9 mm -
overlapping ranges, and every catch-up residual is 5.8-6.0 mm with zero 200-tick
chases and zero re-seats.

## 6. P0.4 - the re-rank test (the missing third leg)

27 observed pairs, **8 discriminating** (outcomes differ), of which **4 correct /
4 inverted**; 19 pairs are outcome-equal (non-discriminating).

**Type X - choice varies, aim held (patch floored vs patch arm B).** The pools are
identical through attempt 0 (same tomato, same score, both placed); the first divergent
choice is attempt 1. 17 usable pairs, 5 discriminating:

| slot | floored choice | arm B choice | verdict |
| --- | --- | --- | --- |
| a01 *aligned* | strawberry idx5 along 0.5334, S(-81.7, -81.7) mm | peach idx12 along 0.346, S(+32.2, -0.0) mm | **CORRECT** (arm B placed; strawberry failed) |
| a08 | apple idx15 placed | orange idx10 failed | INVERTED |
| a14 | lychee idx1 failed | pear idx11 placed | CORRECT |
| a15 | pear idx9 placed | strawberry idx8 failed | INVERTED |
| a17 | orange idx10 failed | pear idx11 placed | CORRECT |

The score systematically prefers the arm B (below-floor, short-travel) candidates
because the floored candidates' planned terminals sit 13-288 mm **beyond** the band's
upstream edge (clipped), while the below-floor candidates' plans are interior. The
aligned pair is the genuine same-pool comparison - and its preferred pick is exactly
the candidate the shipped floor refuses.

**Type A - same fruit (arm+class+grade+diameter signature), aim varies.**

* vs the acceptance control: 6 signature pairs; 1 discriminating: a04 (kiwi A 5.6 left,
  both runs) - reach aim +0.08 (`m_band` 0.0 mm) **failed**, station aim +0.0173
  (`m_band` +47.3 mm) **placed** -> CORRECT for the station aim. The other five are
  outcome-equal (incl. the documented a00 kiwi: both fail).
* vs the R11-A candidate (4/10, a different branch): 4 signature pairs; 2
  discriminating, both attributed INVERTED (the floored run placed where the
  candidate failed) - but this branch's pools are unaligned from a00 (its a00 is an
  apple, the floored a00 a kiwi), so these two are the weakest evidence in the set.

**Aim interiority (all executed aims).** The acceptance's floored aims are clipped at
the band edge on **9/9** attempts (planned-terminal `m_band` -155.3/-98.1/-13.0 mm
min/p50/max); the patch's on 15/17 (-287.9/-81.7/+5.1 mm); arm B's on 7/20
(-132.9/+10.3/+65.9 mm). The control's station aims read `m_band` +12.1..+97.3 mm -
interior. So a score that ranked **aims** at their terminals would pick the shipped
station aim on every acceptance slot.

**Starved slots.** Acceptance a06: the nearest refused fruit (kiwi along 0.374) is
below the floor and borderline infeasible (`eq` +0.0195 vs band edges: feasible only
in the x <= 0.28 columns, `m_band` +49 mm; else-column -1 mm; the select row reads
`candidates_feasible=0`). Patch a05/a06: `candidates_feasible=2` but `shipped_floor_ok=0`
- feasible fruits refused by the floor alone; a07: feasible=0. The terminal score
would not re-open them under the floor; without the floor it would take them (the
R10-A.1 arm's regime).

## 7. K, cost, cache

* **K that suffices**: observed max eligible per slot = 4 (patch; 2 on the
  acceptance), max feasible = 6 (patch). The pre-registered K = 5 covers the floored
  candidate set with one spare; a floor-dropped variant would need K = 6 on the patch.
* **Cost**: the replica runs at **0.39 us/call**; K = 5 -> **2.0 us/slot = 0.024 % of
  one 8.33 ms tick**. Planning is at selection, so **zero added ticks**; the cache is
  one transient pred dict per candidate and the chosen aim per attempt (the existing
  `_reach_aim_point` pattern) - no per-tick reads.

## 8. Pre-registration audit (why the letter does not carry the battery)

The decision rule reads: GO iff P0.1 ^ P0.5 ^ (P0.4 has >= 1 correct discriminating
pair involving a named failing slot), or P0.3 separates if no pairs exist. The letter
is met: a01 (patch slot 1, a named R11-A.1 failure), a14 (slot 14), a17 (slot 17) and
a04 (acceptance attempt 4) are all correct discriminating pairs on named failing
slots. The rule, however, gates the A-vs-B battery defined in §1, and applying §1's
scope to that evidence removes all four:

* a01's preferred candidate (peach, along 0.346) is **below the floor** - arm B keeps
  the floor; B's choice at a01 is the strawberry alone, so B cannot flip it. The
  flip belongs to the floor-dropped design already measured (R10-A.1 arm B: 4/9 on
  the acceptance).
* a14/a17 are cross-branch (different pools; one preference above the floor, one
  below) - no aligned pool.
* a04's preferred alternative is the **shipped station aim**, not B's reach aim; the
  floored+station-aim combination needs its own arm (R2 below), and its choice half
  is unobservable.
* B's own delta (choice re-rank among the floored eligible set) has **no observable
  flip** and P0.3 is negative; the pair-level score is 4C/4I (sign p = 1.0 at n = 8).
* The failing class is post-catch (section 5), so a selection-time score has no
  measured channel to the failures.

## 9. Named continuations (each needs its own pre-registration; none is B)

* **R1 - floor-dropped terminal choice (the FPTE paper form).** Evidence: the aligned
  a01 pair (1/1). Baseline is already measured: R10-A.1 arm B 4/9 on the acceptance,
  13/20 on the patch. Risk: it re-opens the v9 pre-fix condition the floor exists
  for; needs the owner's sign-off on the acceptance cost.
* **R2 - aim interiority under the floored branch.** Evidence: a04 (1/1 same-fruit,
  cross-branch) plus 9/9 acceptance aims clipped at the band edge vs the station's
  interior +12..+97 mm. Risk: cross-branch n=1; the R11-A.1 §5.3 "the loss follows
  the fragile lane" reading is not excluded.
* **R3 - the candidate-set diag** (one `FRUIT_REACH_DIAG` extension printing the
  eligible list per selection; one run per variant): makes the B-scoped re-rank
  measurable at all, which these logs cannot. Cheapest first step if the owner wants
  the B-scoped question answered offline.

## 10. What the Tier-A battery must watch (if any continuation is run)

Per the pre-registration §3: no-fire/chase-slot conversion (attempts with no eligible
fruit, 200-tick catch-ups, fallback fires) per arm; lock-on and per-attempt span
non-inferiority <= +5 % (`186_w6_report.py`); every descent inside the shipped
profile budgets (`105`-style); the per-scenario gate + fingerprint; kill on **any**
new failure reason, **any** descent outside budget, or a chase/re-seat rise (the
R11-A 0 -> 10 re-seat signature). No rate delta is quoted as an effect (quantized
outcome); the splits and the per-leg motion are the evidence. No-harm bar: knob-off
controls byte-identical (acceptance 385/385 `[fruit]` lines; patch 643/643), knob-on
acceptance 9/10 + `fingerprint: matches`, two-line dense 442/442 + `190` PASS.

## 11. Blockers and write scope

* **Blocker (for the B-scoped question)**: the logs carry candidate counts, not
  candidate sets - the within-scope re-rank is not measurable offline (R3 fixes it).
  No pre-registered STOP condition fired (P0.1/P0.5 pass; all evidence files existed).
* Writes: this file, `logs/p7/PREREG_FPTE.md`, `scripts/204_fpte_replay.py` only. No
  simulator, no `src/` change, no commits; the arm B / floor machinery was read, not
  modified.
