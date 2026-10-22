### P31-A (2026-10-22, branch `p-supply`, `logs/p31/`): the WAIT GATE - the far-fruit wait is 30-69 % of a fired attempt's model calls (14 of 17 log cells 47-69 %), the decision zone ends at 0.301 m, and the gate skips everything above 0.35 m; built default-off, AST byte-inert, 95-check stub PASS, no simulator

**The directive** (owner, via P30-B's named lever): the model's per-attempt
inference is 123 chunks on a success, 134-136 on a close-and-drop and **309-349 on
a no-fire**; the waste is the *wait*, where the direct loop calls the model every
`execute_steps=4` ticks while the target fruit is still far upstream and the chunk
is a no-op hold. Build a deterministic wait gate.

**The anatomy, measured** (`logs/p31/30_wait_anatomy.py` ->
`logs/p31/31_wait_anatomy.txt`; 148 direct episodes over 11 existing logs at the
shipped 0.12 m/s belt, plus the 3 per-step `RL_ENV_DEBUG` traces at 0.12 and three
0.06 trace corpora for shape). The first model call happens with the fruit
**+0.455..+0.551 m** upstream of the station (`[rl] episode` `y=` minus a measured
**0.096-0.107 m** of post-selection travel inside `reset` - header vs step-0
fruit position, ÷ the measured 1.000 mm/tick belt slope); one call = **4.0 mm** of
belt travel. The reconstructed along-distance reproduces the fire tick and the
fire distance to the centimetre (reconstructed `along@fire` +0.054 m against the
logged `|jaw-fruit|xy = 5.9-6.0 cm`; 328 reconstructed calls against
`decision=1313 -> 328`). **The decision zone ends at 0.301 m**: the encoder
trigger fires at `lead*speed` (90 logged fires: **0.107-0.301 m**, the low end the
fixed 0.9 s lead x 0.12 = 0.108, the high end the W7-B adaptive lead whose
`|jaw-station|/0.20` term grows as the policy walks the jaw up to **+0.395 m**
upstream), the learned close gate at `|jaw-fruit|xy < 0.06` (~0.054 m along), and
the trigger's own past bound is `dy >= -0.05`. Everything above 0.301 m is a
region where neither channel can act.

**Threshold**: `FRUIT_WAIT_GATE_DIST = 0.35 m` = the measured maximum fire
distance (0.301) + one 4-tick quantum (0.0048) + 4.6 cm = **12 chunks (0.41 s) of
margin**, so the model is live before either channel can act. The ladder (0.12 +
0.06 trace corpus): 0.15 -> 44-83 % skipped but inside the fire band; 0.25 ->
still inside the ACQ band; 0.35 -> above every measured fire; 0.40/0.50 -> 7-16 %
of the saving left on the table.

**Built** (`FRUIT_WAIT_GATE=1`, default 0; sub-knobs `_DIST` 0.35, `_PAST` 0.0,
`_WARM` 1, `_DIAG` 0): a frozen `WaitGateSettings` (resolver + a **pure
`skips(along, warm)` predicate** + banner line), and in `rl_env.py` the skip at
the single model-call site (`sample_chunk`, after the ready/ablate/RTC guards,
before `policy.act`) behind `if self._wait_gate_on:`, the four gate methods
(`_wait_gate_active` scope, `_wait_gate_along` = `fruit.y - _expert_jaw_y` in the
**station** frame, `_wait_gate_hold`, `_wait_gate_report`), the held-tick booking
in `act`, the outcome keys + the `[gate]` row in `_finalize`, the per-episode
reset, and the manifest block. **Hold semantics: the last applied action repeated
over the action horizon** - chosen over `act(None)` (which would skip `_apply`,
and `_apply` is where the learned gate, the trigger and the `PRESENT` adoption
run every tick) and over a zero action (absolute joint targets -> all seven joints
to their zero configuration) and over a neutral grasp-pose action (it commands a
motion; a different experiment). The freeze is of a state the policy is already
in: over the far wait the traced jaw moves only **-72..+19 mm** and the commanded
finger is **0.018-0.024** (< 0.030) at the boundary; the +0.395 m walk happens
*inside* the zone, which the gate leaves untouched. **No hysteresis**: the
predicate is a step function of a monotone signal (station frame), so a full
transit makes exactly 1 transition (one-sided) or 2 (with `past`), verified; a
feeder recycle re-arms it (a new wait is a new hold); a pile-up crossing the
threshold costs one chunk per crossing.

**Expected reduction** (`31_wait_anatomy.txt` section 6 + the stub's loop
replay): **25-48 chunks (mean ~39) of a fired attempt's 52-135 = 30.7-68.7 %,
14 of 17 log-class cells in 47-69 %** - the P30-B logged success 123 -> 80
(34.9 %, it fired late at 0.054 m) - and **30-39 of a no-fire's 325-335
(9.2-11.5 %)**; pooled over the 148-episode corpus **37.8 chunks/episode,
31.1 %** (that pool contains P28's 12-no-fire run). The saving is
`(along0 - 0.35)/(along0 - fire_distance)`: a third when the fire is late in the
zone, two thirds when it is early. At the measured `policy_ms = 50.3-55.6`/chunk:
**1.3-2.7 s per fired attempt (mean ~2.0)**, 400-770 UNet forwards. **The honest limit**: the one-sided gate
barely touches a no-fire attempt because its cost is the *post-miss tail* - 0.78
of the 1.36 m the fruit travels lies past -0.10 m, i.e. **195 of 326 chunks
(60 %)**, where the fruit can no longer be caught (the trigger's own bound is
-0.05). That is the optional `FRUIT_WAIT_GATE_PAST` (at `past=0.10` a no-fire
attempt would save ~70 %); it ships **0** because it interacts with
`FRUIT_POLICY_TRIGGER_PRESENT`' adoption and needs its own pre-registration. So
the one-sided headline is: a third to a half of a fired attempt's inference, and
almost nothing on a no-fire attempt.

**Byte-inertness** (the P30-B pattern, three layers, all in the stub): the
resolver returns on its first line unless `FRUIT_WAIT_GATE=1` (a malformed
`_DIST` cannot raise while off); against `b1acbfe` every base simple statement
and every base branch condition of `sample_chunk`/`act`/`_finalize` survives
verbatim, every new statement (2+2+4) is dominated by `_wait_gate_on`/
`_wait_gate_hold_chunk`, and the four new methods are reachable only through the
gate; at runtime the shipped path adds one False `if` per chunk and no
sensor/articulation read.

**Verification (offline only)**: `py_compile` on the five files (exit 0); the
module imports and resolves offline (`wait_gate=off`); `scripts/selfcheck.sh`
**PASS 0 failures**; `logs/p30b/check_home_hub.py` **PASS** (the P30-B stub still
pins the tree); the new `logs/p31/check_wait_gate.py` **PASS 95 checks** - the knob
matrix incl. the malformed-off case and the `warm`/`past` clamps, the base-commit
statement identity, the predicate edges + a full transit's transition count, the
real `_wait_gate_hold` executed (the exact 16x9 held array, not-zero, the
counters, `along0`, the resume latch, the recycle re-arm, 7 scope refusals), two
loop replays of the measured transits (the accounting invariant
`held == 4*skipped` and `skipped + calls == chunks`; fired 50/79 = 63 %, no-fire
34/341 = 10 %), the skip-site source order, the `[gate]` row executed, and
`TASKS_MD5 == md5(tasks.py)` (unchanged - this phase does not touch `tasks.py`).

**Pins**: `rl_env.py` `01278a54acd379d701b5a5061617a131`, `tasks.py`
`e27b18a455b2094aa611b36fd6cec168` (unchanged), `110_rl_rollout.py`
`b5d05ea3b2e39cdc94da6147ec5ed2d8` (unchanged), `check_wait_gate.py`
`460fc298a082e40ff37e662b44772821`, `30_wait_anatomy.py`
`47743f352b52406bee5274f2b306305f`; base commit `b1acbfe`; diff
`logs/p31/10_diff.patch` (351 lines, one file). No config, dataset, checkpoint,
scene/asset/conveyor or collector change.

**Owed (the next simulator block, `WAIT_GATE_DESIGN.md` section 8)**: the N=5
paired direct A/B (`moe_v13s` `61da390a`, seeds 77/101/202, interleaved,
`_DIAG=1` on the treatment arm) with the endpoints *`policy_inferences` and the
`[gate]` counters*, *the fire tick / fire channel*, *the outcome classes (the
carried-class pairing, 6-0 = p<=0.05 at N=5)* and the cycle non-inferiority +
no-harm acceptance; then the `_DIST` ladder, then the `_PAST` pre-registration
(with the `PRESENT` interaction resolved), then the tree-level fingerprint. Kill
criterion: a paired no-fire increase 5-0 or worse, or any new failure reason,
retires the knob without a rate claim. Named interaction: with the gate on the
policy no longer walks the jaw upstream during the far wait, so the W7-B ACQ lead
loses its `|jaw-station|/0.20` term and the trigger's fire distance should shrink
toward ~0.18 m - a measured prediction for the A/B, not a regression.
