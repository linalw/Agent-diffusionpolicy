# P53 results — the emit cells (the joint clamp, the action hold)

Measured 2026-10-28 on the P52-final tree (`dae1256` at the batch header; `rl_env.py`
`a1ae217a`), the P43 protocol verbatim (`moe_v13s` `61da390a`, the patch sheet,
`FRUIT_POLICY_TRIGGER=arrival` lead 0.9, `ACQ=1`, `FRUIT_DYNAMIC_PICK=1`, the park
default), **N = 3 runs x 15 episodes, seeds 77/101/202**, one claim per run
(`logs/p53/p3/batch_outer.log`). **Both cells default off; nothing adopted.**

## 1. The nine runs

| seed | T0 (control) | C1 (joint clamp) | C2 (action hold) |
| --- | --- | --- | --- |
| 77 | **11/15** | **12/15** (+1) | **11/15** (0) |
| 101 | **10/15** | **9/15** (-1) | **9/15** (-1) |
| 202 | **9/15** | **8/15** (-1) | **6/15** (-3) |
| **pooled** | **30/45** | **29/45** (-1) | **26/45** (-4) |

## 2. The mechanisms (read from the logs, not inferred)

- **C1 the joint clamp**: `[emit] episode 0: clamp=1 ... out_pre=101/2093 (4.8 %)
  out_post=0/2093 (0.0 %) ticks_with_overshoot=101` - the clamp removes the
  out-of-range emissions **completely** at zero time cost. The overshoot was
  therefore real and is now gone; the **placed count does not move** (-1 pooled,
  +1/-1/-1 per seed).
- **C2 the action hold**: `[rl] emit: ... action_hold=2 execute_steps=4
  ticks_per_decision=8 hz=60.0` - the hold halves the decision rate (120 -> 60 Hz)
  and reads **-4** pooled (0/-1/-3): the slower policy loses placements.

## 3. The verdicts

- **C1 is a NULL on the class**: the mechanism works exactly (4.8 % -> 0.0 %), the
  placements do not move. So the policy's out-of-range emissions were **not** the
  binding term for the right arm's remaining ~5 % - that residue belongs to the
  **scripted close/handover/grip** class (P35-P43), not to the policy's targets.
- **C2 is NEGATIVE**: the hold costs placements and nothing else.
- **Nothing is adopted**; `FRUIT_POLICY_JOINT_CLAMP` and
  `FRUIT_POLICY_ACTION_HOLD` stay **default off** (the unset path is byte-identical,
  pinned by `scripts/229_p53_emit_selftest.py`).

## 4. With P52 this closes the model lane

The policy owns **14.2 %** of a placed episode (its speed lever is bounded at
**<= 4.8 %**, measured -2.9 % / -5.0 %); its supervision is sound (0/581 455 labels
out of range); its chunks carry no phase structure (PACE dies offline); and
clamping its own emissions is free but gains nothing (this phase). The model-side
levers that remain are the **interface** ones already measured: the park default,
`FRUIT_POLICY_EVENT=1` (+6.7 pt at N = 3, never at N = 5), and the ACQ question
the shipped direct config leaves untested (`FRUIT_POLICY_TRIGGER_ACQ` is off at the
shipped default while the 94.6 %/4.8 % split was measured at ACQ=1).

## 5. Caveats

- `scripts/113_rl_report.py` exited 1 for the T0/C1 and T0/C2 pairs
  (`batch_outer.log`); the **raw per-run logs and the `[rl] rollout success N/15`
  lines stand** - the counts above are read from those, not from the failed report.
- The three seeds are three branches; the counts are **counts**, not rates (AGENTS
  §2). The pooled C1 delta of -1 is one episode, i.e. inside the branch noise; the
  honest read is "null", not "slightly negative".
- Evidence: `logs/p53/p3/{T0,C1,C2}_{1..3}.log`, `batch_outer.log`,
  `logs/p53/02_smoke_c1c2.log`, `00_id_pre.log`.
