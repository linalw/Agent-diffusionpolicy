# P31-A - the WAIT GATE: skip the model's calls while the fruit is far

Status: **implemented, default off, offline-verified** (Tier C). No simulator run
in this lane; every number is read from the existing logs or derived from the
code's own cadence, and the one owed measurement is the A/B in section 8.

The owner's directive (P30-B's named lever): the model's per-attempt inference
cost is 123 chunks on a success, 134-136 on a close-and-drop and 309-349 on a
no-fire, and the waste is the **wait**, where the loop calls the model every
`execute_steps=4` ticks while the fruit is still far upstream and the chunk it
produces is a no-op hold. Build a deterministic wait gate that skips those calls.

---

## 1. The wait anatomy, measured

Two independent reads, both from existing logs (`logs/p31/30_wait_anatomy.py`,
output `logs/p31/31_wait_anatomy.txt`).

### 1a. Where the fruit is when the model is called

The episode-row corpus is 148 direct episodes over 11 logs (P28's `probe_A`,
R11-A.1 `B_N/*`, R7-A, R9-A, W7-B, W4's debug run), all at the shipped 0.12 m/s
belt:

| stage | value | source |
| --- | --- | --- |
| fruit along-distance at the **first model call** | **+0.455 .. +0.551 m** (per log-cell p50) | `[rl] episode` `y=` minus the measured post-selection travel |
| post-selection travel inside `reset` | **0.096-0.107 m** | the 3 per-step traces: header `y=` vs the fruit's `y` at step 0, ÷ 1 mm/tick |
| belt travel per model call | **4.0 mm** | `execute_steps=4` × 1.0 mm/tick (measured slope -1.000 mm/tick) |
| chunks per fired attempt | 52-135 (per-log means 63-85; 123 on P30-B's success) | `decision / 4` |
| chunks per no-fire attempt | 325-335 | `ticks / 4` (the fruit rides to the belt end) |

The along-distance is *not* a proxy: the three per-step traces at 0.12 m/s
(`logs/w4/51_direct_debug_rlenv.log`, 1251/1242/1235 rows) reproduce the fire
tick and the fire distance to the centimetre (reconstructed `along@fire` +0.054 m
against the logged `|jaw-fruit|xy = 5.9-6.0 cm`, and the reconstructed call count
328 vs `decision=1313 → 328`).

### 1b. Where the decision happens

| channel | fire condition | measured fire distance |
| --- | --- | --- |
| encoder intercept trigger (`FRUIT_POLICY_TRIGGER`) | `t_arrive = dy/speed <= lead`, `|dx| <= lateral`, `dy <= reach` | **0.107 .. 0.301 m** (n = 90 logged fires; the low end is the fixed 0.9 s lead × 0.12 m/s = 0.108, the high end the W7-B adaptive-acquisition lead whose `|jaw-station|/0.20` term grows as the policy walks the jaw upstream) |
| learned close gate (`policy_close`) | `finger < 0.030 and |jaw-fruit|xy < 0.06` | **~0.054 m** along (the 6 cm ball minus the measured 1-3 cm lateral offset) |
| the trigger's own past bound | `dy >= -0.05` | the trigger refuses a fruit further downstream than 5 cm |

So the **decision zone is `along <= 0.301 m`**, and everything above it is a
region in which neither channel can act: the model cannot change the fire tick,
cannot close, and cannot move the arm anywhere that matters (the far wait is
within ±72 mm of a static hold - section 3).

### 1c. The threshold

`FRUIT_WAIT_GATE_DIST = 0.35 m` (default):

* above the measured maximum fire distance by **49 mm = 12 chunks** of belt
  travel (0.41 s), so the model is live before either channel can act even in
  the widest measured fire (the ACQ lead at 0.301 m);
* exactly one chunk-quantum plus margin above the *un-gated* band, so it stays
  valid if a future A/B changes the lead: the gate never sets the fire timing,
  it only ensures the model was running before it;
* the ladder (`31_wait_anatomy.txt` section 3, 0.12+0.06 trace corpus): at 0.15 m
  the gate would skip 44-83 % of the calls but is inside the fire band; at 0.25 m
  it is still inside the ACQ band; at 0.35 m it is above every measured fire; at
  0.40 m the skip falls to 13-37 % and at 0.50 m to 6-19 %, because the whole far
  wait is only 0.10-0.20 m above 0.35 on a fired attempt.

One caveat, stated up front: with the gate on the policy no longer walks the jaw
upstream during the far wait (section 3), so the **ACQ lead's `|jaw-station|`
term stays ~0 and the gated run's fire distance should shrink toward
`(0.9 + 0.6) × 0.12 = 0.18 m`**. That makes the gate *more* conservative, not
less, but it means the *un-gated* 0.301 m is the number the threshold has to
clear - and it does.

---

## 2. The predicate

```
skip(call) := FRUIT_WAIT_GATE=1
              and scope_ok                      (direct, synchronous, model, no dagger/recorder/event)
              and at least `warm` chunks sampled (the first chunk has executed)
              and along > 0.35 m              (or, with FRUIT_WAIT_GATE_PAST>0, along < -past)
```

`along` is `fruit.y - _expert_jaw_y`, i.e. the fruit's distance **upstream of the
pick station**, in the station frame captured at reset. Not the current-jaw
frame: the measured jaw walks up to **+0.395 m** upstream over a long wait (the
policy's own tracking), so a jaw-relative distance would open the gate late and
drift with the arm. The station frame makes the predicate monotone in simulated
time, which is what removes the need for hysteresis.

`warm >= 1` is not a tuning knob but a correctness guard: `_last_action` is
zeros at reset, and a zero action is a real command (all seven joints to their
zero configuration). The gate may only hold once a real chunk has executed.

**Hysteresis: none, and here is why.** The predicate is a step function of a
monotone signal. Over a full transit (0.60 → -0.20 m in 1 mm steps) the
one-sided gate makes exactly **one** transition and the two-sided (with `past`)
exactly **two**, with a contiguous zone (`check_wait_gate.py` layer 3). A fruit
that is recycled to the upstream end re-arms the gate, which is correct - that
*is* a new wait. The only chatter source is a pile-up nudging a fruit a few
millimetres across the threshold, which costs one chunk per crossing (the patch
sheet spaces fruit 0.085-0.12 m apart, so the queue does contact).

### The scope (`_wait_gate_active`)

| guard | reason |
| --- | --- |
| `presentation == "direct"` | the handoff presentation teleports the fruit to the station; no far wait exists |
| `rtc is None` | with RTC the sampler lives inside `next_action`; there is no per-chunk call to skip |
| `ablate == "none"` | the zero ablation already samples nothing; the scripted ablation never samples |
| `dagger is None` | the expert label, the takeover statistics and the recorded `policy_action` are per-decision data |
| `not _event` | the event lever picks each chunk's horizon from chunk-to-chunk continuity; a held chunk would pollute its online median |
| no active recorder | a gated recording would lose the held frames and keep a held label - a different store, not this lever |

---

## 3. The hold semantics

**Chosen: the last applied action, repeated over the whole action horizon**
(`np.repeat(self._last_action, action_horizon)`).

Why not `act(None)` (which the shipped loop already uses before the policy is
ready, and which holds the drive's last target by simply not writing a new one)?
Because `act(None)` skips `_apply`, and `_apply` is where the **fire machinery**
lives: the learned close gate, the intercept trigger and the
`FRUIT_POLICY_TRIGGER_PRESENT` adoption are all evaluated there, every tick. A
held chunk keeps all of that on exactly the ticks it ran on before - only
`policy.act` disappears. The difference matters: with `act(None)` a trigger fire
or a presented-fruit adoption inside the skipped window would be silently lost,
and the gate would become a fire-timing lever instead of an inference lever.

Why not a **zero** action: `_apply` writes `action[:7]` as *absolute joint
position targets*, so zeros command all seven joints to their zero
configuration. That is a wild motion, not a neutral one.

Why not a **neutral grasp-pose** action: it is a *motion* command (the arm may be
0.4 m away when it engages) and it is a new closed-loop behaviour of its own.
The grasp pose is where the demos' wait phase holds, so it is the natural
alternative - but it is a different experiment, and the last-action hold is the
strictly smaller change.

**What the freeze actually freezes** (the 3 per-step traces at 0.12 m/s): over
the far wait (`along > 0.35`) the jaw moves **-72 .. +19 mm** and the commanded
finger is **0.018-0.024** (< 0.030) at the boundary. So the far wait is already
a near-static hold with the finger pre-closed; the big upstream walk (+0.395 m)
happens *inside* the zone, which the gate leaves untouched. The hold therefore
freezes a state the policy is already in - it does not create one.

**The 4-tick cadence, the physics, the episode length and the reward's
`decision` are unchanged**: a held chunk still occupies the same 4 ticks and
advances `_step` the same way, so the gate moves the inference cost and nothing
else. That is what makes its A/B cleaner than the home hub's.

---

## 4. The expected inference reduction

One chunk = one `PolicyRunner.act` = one `ddim_steps=16` DDIM chain = 16 UNet
forwards; a chunk is 4 control ticks = 33 ms of simulated time = 4 mm of belt.

| attempt class | chunks now | skipped at 0.35 m | chunks after | saving |
| --- | --- | --- | --- | --- |
| fired (success / carried / close-drop), 17 log-class cells | 52-135 | **25-48** (mean ~39) | 27-87 | **30.7-68.7 %**, 14 of 17 cells in 47-69 % |
| P30-B's logged success (`probe_A`, `decision=490`) | 123 | **43** | 80 | **34.9 %** |
| no-fire (`fruit fell off the line` / the 1500-tick horizon), 4 cells | 325-335 | **30-39** | 292-296 | **9.2-11.5 %** |

The pinned success's lower share is the fire distance, not the gate: it fired at
0.054 m (the learned gate) out of a 0.521 m along0, so 0.29 m of the transit is
inside the zone where the model has to run; the 47-69 % cells fired at
0.19-0.30 m (the ACQ trigger). **The saving is therefore
`(along0 - 0.35) / (along0 - fire_distance)`**: a third of the attempt when the
fire is late in the zone, two thirds when it is early.

Pooled over the 148-episode corpus: **37.8 chunks/episode skipped, 31.1 %**
(`31_wait_anatomy.txt` section 6), with the *shape* of that pool deciding the
number: it contains P28's pathological 12-no-fire run.

In wall time, at the measured `policy_ms = 50.3-55.6` per chunk
(`logs/rtc/diag_e2/E2_rtc0_timing.log`, `moe_v9`, 16 DDIM steps): **1.3-2.7 s per
fired attempt (mean ~2.0 s), 1.5-2.2 s per no-fire attempt, ~2.1 s pooled**. In
UNet forwards: 400-770 per fired attempt.

**The honest limit of the one-sided gate**: a no-fire attempt's cost is *not* the
far wait. Its fruit travels 0.48 m to the station and 0.88 m past it, and only
the first 0.13 m is above the threshold - the remaining **0.78 m past the
station (195 of 326 chunks, 60 %) is the post-miss tail**, where the fruit can no
longer be caught (the trigger's own bound is `dy >= -0.05`) and the model is
still called. That is what `FRUIT_WAIT_GATE_PAST` addresses (skip when
`along < -past`; at `past = 0.10` a no-fire attempt would drop to ~70 % saved).
It ships **default 0** because it interacts with `FRUIT_POLICY_TRIGGER_PRESENT`
(a presented fruit at the station is firable while the selected sample is past,
and a held tick would not adopt it) and needs its own pre-registration. So the
one-sided gate's headline is: *a third to a half of a fired attempt's inference,
and almost nothing on a no-fire attempt.*

---

## 5. Failure modes, ranked

1. **Fire timing / close-start (the real risk).** The gate changes what the arm
   does during the far wait (from a slow upstream walk to a hold) and the finger
   state at the resume boundary. If the model's post-resume chunk does not
   command `finger < 0.030` before the fruit reaches 6 cm, the learned gate can
   miss. Measured margin: from the episode start the model closes the finger
   within ~60 ticks (15 chunks); after the resume it has 74 chunks before the 6
   cm ball and, with the trigger on, 12 chunks before the earliest measured
   trigger fire. Pre-registered endpoint: the per-episode fire-tick delta and the
   no-fire count, not the rate.
2. **ACQ lead shrinkage (a branch shift, not a bug).** With the jaw held at the
   station, the W7-B adaptive lead loses its `|jaw-station|/0.20` term, so the
   trigger fires *later* than in an un-gated ACQ run (0.18 m instead of up to
   0.301 m). Do not read that as a regression: it is the gate doing what it says
   (no model-driven jaw walk during the wait). If an A/B wants the old lead, the
   gate must be off or the lead pinned.
3. **A held finger below 0.030 for the whole wait.** `policy_close` still needs
   `|jaw-fruit|xy < 0.06`, so no early fire - but a *presented* fruit at the
   station can be within 6 cm while the selected sample is far, so check the
   `PRESENT` interaction before enabling both (the scope guard does not cover it;
   `past = 0` keeps the case identical to today because the gate is upstream-only).
4. **The tracking lever.** With `FRUIT_POLICY_TRACK=1` the GEM feed-forward is
   added to the held action every tick, so the "hold" still moves the arm with
   the fruit. That is the tracking knob's own behaviour, but an A/B must not
   have both on and attribute the result to the gate. Likewise
   `FRUIT_RTC_REPORT=1` books the held ticks into the executed-stream statistics
   as zero deltas - truthful (the stream *is* constant there) but it changes the
   boundary median, so a rate A/B keeps the report off as usual.
5. **The dataset.** A gated recording is a different store (fewer frames, held
   labels). The scope refuses an active recorder, so this cannot happen by
   accident; a gated collection would need a manifest field and its own
   pre-registration.
6. **Pile-up chatter** (section 2): one extra chunk per threshold crossing;
   bounded and measured-zero on the shipped supply so far.

---

## 6. Code sites

| site | change |
| --- | --- |
| `WaitGateSettings` (`rl_env.py`) | the knob resolver (`from_env`), the pure predicate (`skips`), the banner line (`summary`), frozen |
| `SortingRLEnv.__init__` | resolve once; cache `_wait_gate_on`; the counters; the manifest block |
| `SortingRLEnv.sample_chunk` | the skip: `held = self._wait_gate_hold()` behind `if self._wait_gate_on:` - before `policy.act`, after the ready/ablate/RTC guards |
| `SortingRLEnv._wait_gate_active/along/hold/report` | the scope, the station-frame distance, the held chunk + counters, the `[gate]` row |
| `SortingRLEnv.act` | book the held ticks (`executed`) and clear the flag |
| `SortingRLEnv._finalize` | the outcome keys and the `[gate]` row (under `_DIAG`) |
| `SortingRLEnv.reset` | zero the per-episode counters |

`tasks.py` is **not touched** (`TASKS_MD5` unchanged), `scripts/110_rl_rollout.py`
is **not touched** (the row comes from the env's `_finalize` via `_say`, so the
driver's `[rl]` parsing is unaffected).

---

## 7. Verification (offline)

* `py_compile` on the four touched sources + the two new scripts
  (`logs/p31/40_compile.txt`).
* `scripts/selfcheck.sh` **PASS, 0 failures** (`logs/p31/30_selfcheck.log`).
* `logs/p30b/check_home_hub.py` **PASS** (the P30-B stub still pins the tree).
* `logs/p31/check_wait_gate.py` **PASS, 95 checks** (`logs/p31/32_stub.txt`):
  the knob matrix (including the malformed-sub-knob-off case and the `warm`/
  `past` clamps), the base-commit statement identity of `sample_chunk`/`act`/
  `_finalize` (every base statement and every base branch condition survives;
  every new statement gate-dominated; the new methods reachable only through the
  gate), the predicate edges + a full transit's transition count, the hold path
  executed on a fake env (the scope refusals, the warm guard, the exact held
  array, the counters, the resume latch), a loop replay of both measured
  transits (the accounting invariant and the expected chunk counts), the
  `[gate]` row executed, and the provenance/pin chain.

**No `accept.sh`, no `accept_policy.sh`, no `demo_2min.sh`**: this lane is offline
by instruction. The byte-inert default is argued at the statement level and
still owes the tree-level acceptance fingerprint.

---

## 8. The owed measurement (the A/B)

Direct interface, the WS-4.2 N=5 protocol (`logs/r8/A_RESULTS.md` §7), paired at
one seed per pair, interleaved, `moe_v13s` (`61da390a`):

```
FRUIT_WAIT_GATE=0 vs =1 (dist 0.35), FRUIT_WAIT_GATE_DIAG=1 on the treatment arm
EPISODES=15 seeds 77,101,202 x 5 pairs   -> scripts/112_rl_ab.sh style
```

Primary endpoints:

1. **`policy_inferences` per episode** (`skipped + calls`), and the `[gate]` row's
   `skipped/held/resumed` - the predicted 40-50 on a fired attempt, 30-34 on a
   no-fire.
2. **the fire tick and the fire channel** per episode (the note suffix): the
   predicted no change in the *fired* attempts' fire distance with the trigger
   off, and the predicted ACQ-lead shrinkage with it on (failure mode 2).
3. **the outcome classes** (success / carried / close-drop / no-fire) with the
   pre-registered carried-class pairing (6-0 at N=5 is the p <= 0.05 edge).
4. the cycle non-inferiority margin (`decision` per attempt, which the gate does
   not move by construction) and the no-harm acceptance (`FRUIT_WAIT_GATE=0`
   byte-identical to the pre-phase acceptance, fingerprint match).

Kill criteria: a `no-fire` class increase paired 5-0 or worse, or any new failure
reason, retires the knob without a rate claim.

---

## 9. Files

* `src/fruit_sorting/rl_env.py` - `WaitGateSettings`, the four gate methods, the
  skip, the tick booking, the outcome keys, the reset, the manifest. The whole
  diff is 284 inserted lines and 0 deleted (`logs/p31/10_diff.patch`).
* `logs/p31/30_wait_anatomy.py` / `31_wait_anatomy.txt` - the measurement.
* `logs/p31/check_wait_gate.py` / `32_stub.txt` - the stub.
* `logs/p31/WAIT_GATE_DESIGN.md` (this file), `IMPLEMENTATION.md`,
  `WORKLOG_ENTRY.md`, `10_diff.patch`, `00_md5s.txt`, `30_selfcheck.log`,
  `40_compile.txt`.
