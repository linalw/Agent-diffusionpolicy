### P27-A (2026-10-21, branch `p-supply`, offline): the owner's belt-speed premise audited - the encoder is a setpoint echo in the shipped build, the policy has no speed input, and the slow side is unmeasured because the carry escape is not belt-fed

**Scope: offline, read-only.** No simulator run; no `src/`/`scripts/`/`configs/`
write; no commit; writes only under `logs/p27/`. Tree pins as read:
`tasks.py` `b54b54064607c50f7ed0adc906c97a45`, `rl_env.py`
`6c859b9927bff65e119d11e0c364b6a9`, `policy/trigger.py`
`d7ec85fca5661a54473f7c6a69445fbc`, `conveyor.py`
`40b04d2da12a80cb209551916c60cc14`, `fruits.py`
`d28546d26137d4540421caa7fa34a139`, `assets.py`
`ab6d1204f5c4d72a219d6921e3856960`; HEAD `5268a8c` (the P26 default flip).
Deliverable: `logs/p27/SPEED_ADAPT_AUDIT.md` (the trace + the observations +
the prediction + the sweep design).

**The premise.** "I introduced the belt speed encoder so the model adapts to
different belt speeds; at slower speeds the grasp/sort success should hold or
improve." The audit's three answers:

**1. What the encoder adapts (and what it is).** It reaches the *schedule*, not
the model: `rl_env.py:1471-1490` reads `spawner.belt.encoder_speed` and passes it
to `should_fire(encoder_speed=...)`; `trigger.py:198-222 transport_speed()` makes
it the approach speed (falling back to the measured fruit `vy`), and
`trigger.py:335-338` fires at `t_arrive = dy/v <= lead`. The same quantity drives
`_dynamic_pick_lead` (`tasks.py:4348-4369`), `_dynamic_select_floor`
(`4254-4287`), the descent's hover deadline (`7430-7437`) and the ACQ reach
(`trigger.py:246-250`). **In the shipped build it is not a measurement:** with
`FRUIT_CLEATS` unset (the default) `Conveyor.step` returns at
`conveyor.py:488-489` *before* the encoder update, so `encoder_speed` stays at
`float(cfg.belt_speed)`; the runner's own `[stats]` line says so
(`tasks.py:1484-1488`, "no cleats to measure travel"; e.g.
`logs/p26/10_accept_015.log` -> `encoder=-0.150 m/s nominal`). With cleats on it
differences the *commanded* phase, so it reproduces the applied speed by
construction. So the premise, today, is "the `FRUIT_BELT_SPEED` value is
threaded through the schedule" - belt-speed *parameterised*, not belt-speed
*adaptive*. The schedule itself is a **time** schedule: every `v` appears as
`v*(fixed seconds)` (the catch lead is 1.325 s of travel, the floor 1.5 s + setup,
the trigger 0.9 s), so a slower belt does **not** give the hand more time; the
handover starts 1.325 s before arrival at every speed (derived:
`t_desc(0.06,0.15,0.8)=0.775 s`). Related finding: `assets.py:214` defaults the
belt to **0.15** (P26, `5268a8c`) while its own comment and the documents say
0.12 - the acceptance `[stats]` line is the only artifact that records which.

**2. The policy does not see the speed.** The input is 2 x 128x128 RGB-D+mask +
25-D proprio + 8-D goal (`rl_env.py:57-64`, `1213-1240`, `policy/model.py:112-117`);
no speed scalar. The only correlated channel is `goal[3:6]`, the **target's
measured velocity at selection**, episode-constant (within-episode sd 0.0000),
rolling-contaminated, and ~1 sd of the training spread per 0.04 m/s: the
per-episode mean `vy` tracks the store (0.06: -0.054..-0.061; 0.12:
-0.115..-0.120; 0.15: -0.154). The checkpoints' normalizer is **0.06-centred**
(`goal_mean[vy] -0.0570`, sd 0.0366) so 0.08 sits at z -0.63 and the *deployment*
0.12 at z -1.72 - the channel cannot be the mechanism either way. The learned
close is a *distance* criterion (`finger < 0.030` + 6 cm; `[acq]` close-start
offsets 3-6 mm), while the trigger is a *time* criterion: the two paths adapt in
different variables. **The observed "adaptation" is the trigger's timing plus the
scripted primitive's schedule underneath** - and in the *shipped* policy handover
(`FRUIT_DYNAMIC_PICK` unset) the primitive is the **indexed** pick (belt stopped
at the station), so there the belt speed only changes *when* the fruit arrives.

**3. The record and the prediction.** The same 0.12 -> 0.15 step changes sign
with the base - two-line patch pre-mass 12/20 -> 14/20 (`logs/w8/R3_RESULTS.md`
s4, the descent block 3.19 -> 2.40 s, the catch leg flat), real mass same seed
11/20 -> 10/20 (`logs/p12/A_RESULTS.md` vs `logs/p26/211_patch015_seed11.log`),
direct/hybrid 32/45 -> 31/45 and 30/45 after a 0.15 fine-tune
(`logs/p2b/ladder015_*`), scripted collection 72 % -> 55.6 % - so the rate cannot
carry the speed question. The only *mechanism* readings are the arrival
structure (monotone) and the 0.18 floor/starvation explosion (115 starved left
slots; the fixed 1.5 s floor is 0.27 m of belt there) which **does not apply at
the slow end** (the floor falls to 0.286 m and the band grows 25 %). The P26
acceptance 3/9 is a *contact* set (4 carried-not-placed, 2 plucks at 56.2/89.2 N,
one drift blowup, two 49.8/12.2 N closes vs 0.12's ten closes at 3.68-4.77 N),
not isolated from the B1c flip (P27-B in flight, `logs/p27/10_acc_012_flip.log`).
**Nothing exists at 0.08/0.10 on any interface.** Prediction: **flat on success,
a real cost on throughput** - the hover wait per attempt grows ~1.3 s (the R3
descent-block slope), the arrival cadence and the recycle loop stretch 1.5x.

**The strongest reason the expectation could fail: the escape is not belt-fed.**
The dominant direct failure is carried-not-placed (32/33 failures W7-C; 49/54
W8-A), a *hand-frame* displacement of 17.9-957 mm (median 278 mm) reached in ~25
ticks (0.21 s) - a median hand-frame slip rate ~1.3 m/s, 11x the 0.12 belt
(W8-B). The belt can add at most `v*0.21 s`: **24 mm at 0.12, 17 mm at 0.08, i.e.
<= 10 % of the median escape** (an upper bound: the payload is belt-matched
during the close and the takeoff `match_s`). The driver is the arm/pad relative
motion and the drive-saturated pinch (R6-B: the command 11.9 mm inside the
payload's span) - invariant to `v`, which is why the grip-side levers were all
nulls (W8-B guard, R6-B relief/retune, R8-A geometry). So "holds" is plausible;
"improves" is not, and the one slow-side mechanism that can *lose* success is
unmeasured (the open jaws parked in the approach line ~1.5x longer).

**The sweep (design in the audit, s5; `logs/p27/run_p27.sh` is the running
subset).** S1 scripted single arm 0.08/0.10/0.12/0.15 x 20; S2 direct `moe_v13s`
patch sheet ACQ=1 4 speeds x 3x15 (the 0.12 control must reproduce W8-A `A_1` =
4/15, seed 77); S2b the same with `TRIGGER=off` (the **model**-adaptation test:
does the learned close's `dy/v` stay constant?); S2c `TRIGGER_ENCODER=0`; S3
two-line real mass 0.08/0.10 x 2 seeds (0.12/0.15 in the record); S4
`scripts/170_transport_probe.py` at each speed (the encoder's validity
precondition - it assumes `v_fruit ~ v_belt`); S5 the supply time-normalised
(gaps/slices scaled by `v`) to separate the feeder's `1/v` cadence from the belt.
Primaries are per-leg (E1 the `intercept trigger` note: `dy` scales, `t_arrive`
constant; E2 the `[acq]` close-start/setup; E3 the `[carry]` `clean_slip` vs the
belt-fed bound; E4 the descent/catch), the rate is E7 with the class split. A
"model adaptation" claim needs six things the repo does not have: a speed input,
a time-coded close, >= 2-speed training on one tree, the same weights at each
speed, the trigger-off measurement, and a null against the primitive's own
ceiling (P2b: 71.1 % vs the scripted 73.3 %).

**Gaps named for the next block.** (1) `encoder_speed` should be a real readback
and must not silently fall back to `cfg.belt_speed` (`tasks.py:4371-4377` hides
exactly the mismatch the owner wants to detect). (2) **No manifest records the
belt speed** - `rl_env.py:927-935` stores the trigger block but not
`FRUIT_BELT_SPEED`; the collection manifests record `collection.*`/`supply.*` and
no belt field, so no store can be assigned a speed from its own artifact (the
goal `vy` is the only in-artifact witness). A sweep needs a sidecar `env.txt` or
a new `scenario.belt_speed` field. (3) Three sources of the same quantity
(encoder / `cfg.belt_speed` for the feeder + prepose / measured `vy` for the
reach aim + takeoff) agree only because all are the same number today. (4)
`assets.py` comment (0.12) vs default (0.15). (5) `enforce_transport` still
rescues a stalled fruit to `0.40*belt.speed` (`fruits.py:1443`), the superseded
transport efficiency; at 0.08 that is 0.032 m/s - a low-speed artefact for the
transport probe to watch.
