# P10-D.1 stage-1 RESULTS (2026-10-18): the GDP OoD sampling (K=2) - a measured null on the direct interface

Pre-registration: `logs/p10d1/PREREG_GDP_AB.md` (+ amendments 1-3). Tree: `runtime.py`
**379ac7064fd49df8417e94dbf6ed2616** (the GDP implementation; `tasks.py` `6574d92e...` /
`TASKS_MD5` matching). Branch `p-supply`.

## 1. The battery (the W7-B boundary pin, N=3x15, seeds 77/101/202, interleaved)

**The wedge saga.** The 112 chain's sessions wedged 5/6 (a known renderer/physics freeze class
- one `carb.tasking` worker spinning with the GPU idle; the W7-B ran 6/6 clean two days ago).
A side watchdog killed each wedge so the chain proceeded; a fill-in queue then re-ran every
incomplete session (3 attempts each) and recovered all five: **A_1 (try2), B_1 (try1), B_2
(try1), A_3 (try1), B_3 (try1)**, with A_2 complete in the chain. **All six sessions are
complete (15/15 episodes)**; the retries are legitimate new trajectories (the RTX frame
variance makes them non-deterministic replays).

## 2. The endpoints (pre-registered order)

1. **Primary: the close-start tip-fruit |y| offset** (the W7-B report; `logs/p10d1/stage1_mech.txt`):

| arm | left (n=18) | right (n=27) |
| --- | --- | --- |
| A | median **169.1** mm, p90 **247.8**, max 917.5 | median 5.0, p90 5.7 |
| B | median **25.3** mm, p90 **575.0**, max 955.5 | median 4.6, p90 5.6 |

   The prereg's positive form: "the median falls or holds with the p90 non-worse and the
   no-fire count non-worse". **The median improves strongly (169.1 -> 25.3) but the p90
   worsens (247.8 -> 575.0) -> the primary endpoint FAILS.** The left distribution is
   dominated by the known far-downstream-close class (the W7-B's left deficit; both arms carry
   900+ mm extremes); with n=18 the median/p90 move together with which episodes' closes land
   in the tail - the honest reading is that the GDP moved the left close-start *distribution's
   shape* without a clean directional win.
2. The no-fire count: no new failure reasons on either arm (`stage1_outcome.txt`); the failure
   reasons' normalized sets are identical.
3. **The outcomes (reported): pooled A 27/45 (60 %) vs B 27/45 (60 %)** - identical; paired
   23 both-ok / 14 both-fail / 4 B-only / 4 A-only (sign p = 0.6367); the per-class cells
   within +/-1 episode; the median cycle A 1841 vs B 1842 ticks (+0.1 %).
4. **The wall cost (measured offline, `logs/p10d1/10_wall_cost.txt`)**: one DDIM-16 chain
   24.8-26.6 ms (2.1-2.2x the menu's ~12 ms claim); K=2 `act()` 49.7-52.9 ms = 1.96x K=1 =
   1.5-1.6x the 33.3 ms re-plan window (wall only; the stepped sim clock is unaffected). The
   honest cost is **2x the policy-sampling wall for zero measured benefit**.

## 3. The kills (pre-registered)

| kill | verdict |
| --- | --- |
| 1. the knob-off byte-inert proof fails | **clear**: the 40-check stub + the real-checkpoint check prove off == shipped == K=1 (chunks + generator states) |
| 2. a new failure reason | **clear**: none |
| 3. the cycle rises > +5 % | **clear**: +0.1 % |
| 4. the offline stub suite fails | **clear**: PASS |

No kill fired; the **primary endpoint did not pass**, so per the prereg there is **no stage 2**.

## 4. The verdict

**The GDP OoD-scored population selection (K=2) is a measured null on this interface: the
outcomes are identical (27/45 vs 27/45), the cycle is identical, and the mechanism endpoint is
mixed (median better, p90 worse). The negative is published; the lane closes.** The
mechanism fidelity remains the paper's own (the Stein-family min-score reduction, faithfully
ported and byte-inert at default); what failed is the *value* proposition on this
state-conditioned policy - consistent with the P6 adversarial re-read's own limitation note
("on Robomimic, improving denoising buys little because the bottleneck is conditioning of the
noise model"). K=3 was not run (the prereg's named follow-up only if K=2 passed).

**Named residuals:** (i) the left close-start tail is the known acquisition class (the W7-B
left deficit), not a GDP effect - a mechanism run with `FRUIT_POLICY_GDP_DIAG=1` joining
`[gdp]` scores to per-episode outcomes remains the falsifier's unrun half (Amendment 3);
(ii) the frame-vs-noise attribution half of that falsifier is not testable from the row as
implemented (recorded, untested); (iii) the policy's real bottleneck is the conditioning
(the P6 note) - the event-structure heads (menu #6) are the conditioning-side candidate if
this lane is ever re-entered.

## 5. The no-harm bar

| item | status |
| --- | --- |
| the shipped acceptance on the GDP tree (GDP default off) | **PASS**: 9/10 + `fingerprint: matches` + `logs/accept.log` 385/385 vs `logs/p2d/90_accept.log` (the `logs/p10d1/95` chain) |
| `selfcheck.sh` | **PASS** (the same chain; also the implementation lane's) |
| the knob-off byte-inert (the stub + the real checkpoint) | **PASS** |

The two-line dense re-record (the F3-amended no-harm leg) is the named follow-up on the
post-P10-C.3 branch; it is not part of this battery's run set and is recorded as such.
