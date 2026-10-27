# P53 pre-registration — the policy's own emission defect (C1 the clamp, C2 the hold)

Written **before** the battery's first arm finished (the header file
`logs/p53/p3/P3_header.txt` is timestamped at the batch start; this file is
committed only as evidence and changes nothing the batch reads). The tree at
registration: HEAD `b4a7899` (P52 close) + this phase's default-off edit to
`src/fruit_sorting/rl_env.py`; `configs/` untouched.

## 1. What is registered

`logs/p52/P2B_FEASIBILITY.md` §1.6 measures the policy's **own** emissions:
**13.1 % of joint-steps out of the joint range (3 087/23 548), on 74.3 % of
ticks** (j3 1 750, j2 981, j7 256), by a small overshoot (2.8-3.2 deg p50,
8.2-8.6 deg p90, <= 21 deg), while the measured joint sits **at the stop**
(0.03 deg away on j3) and there is **no clamp** on this path
(`rl_env.py:3033-3040`). The same lane measures a **19.3 mm p50** same-tick
task-space residual and names its mechanism: the training stream is recorded at
30 Hz (one frame per 4 control ticks) but the loop applies **one waypoint per
control tick**, i.e. replays it at **120 Hz**, and the drive is a 0.2 s low-pass
- a 10x command dither that buys no motion.

Two cells, both **default off** (`unset` = the shipped emission, proven
byte-identical below):

| cell | knob | what it does | cost |
| --- | --- | --- | --- |
| **C1** | `FRUIT_POLICY_JOINT_CLAMP=1` | clip the 7 absolute joint targets into the arm's own `arm_lo`/`arm_hi` (`control.py:197-202`, read from `get_dof_limits()` at construction) after the A2C2/track shapers and before `set_dof_position_targets` | zero time |
| **C2** | `FRUIT_POLICY_ACTION_HOLD=2` | execute each chunk waypoint over 2 control ticks (`np.repeat` the chunk, so the shipped `arr[index]` lookup stays the lookup), i.e. 60 Hz of sim, `execute_steps*hold = 8` ticks per decision | 2x the ticks per decision, half the decisions |

`FRUIT_POLICY_ACTION_HOLD` is the **hold** the P2B lane registered ("`h_sim` = 2
... a hold counter with `execute_steps = 16`"): `execute_steps = 8` alone would
halve the decisions but keep the command rate at 120 Hz, which is the *other*
half of the mismatch, so the registered cell is the true repeat and its tick
budget is the same 8 ticks per decision.

## 2. The battery

The P43 protocol verbatim: `checkpoints/moe_v13s/policy_best.pt` (`61da390a`) on
all arms, the W6-A/W8-A patch sheet (`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`,
balanced A:B:C 0.375/0.375/0.25), `FRUIT_POLICY_TRIGGER=arrival`,
`FRUIT_POLICY_TRIGGER_LEAD=0.9`, `FRUIT_POLICY_TRIGGER_ACQ=1`,
`FRUIT_DYNAMIC_PICK=1`, the park default (`back`, P43), **N = 3 runs x 15
episodes** per arm, seeds 77/101/202, policy seed 11, arms interleaved
T0 -> C1 -> C2 per seed, one `154_claim_run.sh` claim for the whole batch.

Instruments on **all three arms** (AGENTS §3b: the instrument sits inside the
contrast): `FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1` (the failure classes) and the
new `FRUIT_EMIT_DIAG=1` (one `[emit]` row per episode: applied ticks, policy
decisions, out-of-range joint-steps before/after the clamp, the count of ticks
with an overshoot, the largest overshoot), plus `--record` on every run so the
same-tick `(action, joint_positions)` pair exists for the dither, measured with
`logs/p52/p2b_feasibility.py`'s own formula (`p50 |cmd - achieved| x 0.30 m`).

## 3. Endpoints (registered)

**E1 - C1 is no-harm, and the count falls.**
(a) `placed >= T0 - 1` of 15 **in every run** (the per-run bar; the direct loop
is not bit-reproducible, AGENTS §3b, so a run-level bar is the only honest
form), and (b) **no failure reason T0 never produced**. (c) The out-of-range
count falls: the clamped arm's `out_post` is 0 by construction, so the *check*
is that its `out_pre` matches T0's `out` (same policy, same suppression) and
that T0's own count reproduces the census's order (13.1 % of joint-steps).

**E2 - C2 buys placements or not, with the ticks as the reported cost.**
`placed >= T0` pooled, and the per-run minimum `>= T0 - 1`; the reported cost
columns are `ticks` per placed episode, `decisions` per episode (predicted
~halved: 64 -> 32), the wall per episode, and the dither.

**Prediction (falsifiable, registered before the run).** C1: no placement change
(the census's own split reads **65.2 mrad inside vs 64.0 mrad on the out-of-range
ticks**, so the stop is not the residual's mechanism), `out_post = 0`. C2: the
dither p50 **falls** (the boundary jump stays but occurs half as often, and half
the recorded frames become intra-chunk ones), the decisions **halve**, the sim
ticks are **flat** (the episode is tick-clocked by the belt floor and the
primitive), and the wall falls slightly (half the model calls). If the dither
does **not** fall, P2B §2.5's replay-rate mechanism is not supported and that is
recorded as a negative mechanism result even if the placements hold.

**F1 - the model lane closes** if both cells are null (C1 no-harm with no
mechanism change *and* C2 neither buying nor costing placements while its own
predicted mechanism - the dither - fails to move).

## 4. Reading rules (the standing ones)

* No count here is a rate: N = 3 runs x 15 per arm on a non-reproducible loop.
  The `-1/15` per-run bar is a **no-harm** bar (a 15-episode binomial at
  p ~ 0.7 has sd ~ 2.5 episodes), so E1/E2 are "did the cell cost placements",
  not "did it gain them"; a gain claim would need the WS-4.2 N = 5 convention.
* The two bars are **success-first** (the owner's directive: the policy's speed
  is worth nothing that costs placements).
* T0 is the in-batch control; the P43 corpus is *not* a baseline (different
  instrument set, different branch).
* Nothing is adopted without its own gate; a pass is a measurement, not a flip
  (the P44/P52 practice: every flip is a separate owner decision).

## 5. Byte-identity of the shipped path

`unset` leaves two `if` guards false (`if self._joint_clamp:` in `_apply`,
`if self._action_hold > 1:` in `act`), so the shipped expressions run verbatim;
`scripts/229_p53_emit_selftest.py` pins that offline (the clamp helper is
element-identical inside the range and never edits its input; `hold_index(t, 1)
= t`; the shipped `action = arr[index]` text survives; both resolvers return the
shipped constants when unset). On the simulator it is proven with the
deterministic vehicle the tree has for this loop: `--ablate zero` applies a
fixed chunk and conditions on no rendered frame, so the run *is* bit-reproducible
(WORKLOG "The hybrid loop's variation is the rendered frames"). The pre-edit and
post-edit runs of that command are compared in `P53_RESULTS.md` §2.
