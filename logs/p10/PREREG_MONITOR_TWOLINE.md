# P10-C PREREG (FROZEN): the C-3 carry monitor's fast-skip extended to the two-line scripted catch

Frozen 2026-10-17 before any Tier-A run (the orchestrator). Tree pin: `p-supply` at the
battery-time HEAD (re-pinned by the lane); `tasks.py` md5 recorded at battery time.

## Why (the P10-A map, `logs/p10/A_RESULTS.md`)

The current-tree bimanual baseline: the two-line places **3.63 window placed/min vs the
single arm's 2.17 (1.67x)** but the **carry/grip failure mass is the top bottleneck: 8/20
attempts = 116.6 attempt-seconds = 38.7 % of all attempt time** (1 takeoff grip loss + 7
carried-not-placed; the left A-stream carries 6 of the 8), and the attempts-per-placement
multiplier (left 2.50) is the interval's first-order driver. The P10-B KB's blocker #2 (the
two-line's own no-op transit) is resolved: every per-gap park transit is load-bearing, so the
go_ready skip family dies on the two-line - the monitor's fast-skip is the lever pointed at
the measured top bottleneck instead.

## The one mechanism

The already-measured C-3 monitor (`logs/p7/PREREG_CARRY_MONITOR.md` + the P8-B load-floor fix,
`FRUIT_CARRY_MONITOR` + `FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5`): a tiny classifier over the
online grip signals fires on a doomed carry and ends the attempt at the next leg boundary
(fast-skip, no re-seat). Measured on the direct interface: the interval on the failed-carried
set **-21.8 % (paired 33 = 32 faster / 1 slower, p = 0.0000)**, K2 **0 clean-leg aborts**
(43/43 fires on escaping legs). The blocker there: the lock-on +8.8 % (B2 bar +5 %) - a
two-line read is a **different scenario** and is the measurement this battery makes. B2/B3
(lock-on, cycle) are **reported, not gated** on this moved branch, per the demotion.

**The bounded change**: `FRUIT_CARRY_MONITOR_TWOLINE=1` (default 0) extends the monitor's
scope from `direct_capture` to the **two-line scripted catch** (a `_carry_monitor_active`
scope predicate; the two-line's park/station logic stays untouched; default off, byte-inert at
default - the 96-row scope truth table in `logs/p10c/` verifies it).

## Arms and scenario (Tier A solo)

| arm | env | notes |
| --- | --- | --- |
| **A** | the W6-B/W7-A two-line patch shape, unset | the control, double-run (the P10-A pair stands if bit-identical) |
| **B** | A + `FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_TWOLINE=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5` (see the amendment below: the scope knob is required) | the treatment; double-run; one `FRUIT_CARRY_MONITOR_DIAG=1` run for the fire readout |

`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 SEED=5 HEADLESS=1
FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1` (the diag on **both** arms -
the frozen K2 definition classifies aborts via the live `[carry]` `clean_slip_max <= 2.0` and
endpoint 5 needs the fired-leg class; arm A's P10-A record is diag-off, so its diag run is
verified to replay the pair modulo the `[carry]` rows, the compare_ready pattern);
`scripts/154_claim_run.sh` per run.

## Endpoints (pre-registered)

1. **Primary: the pooled inter-placement interval** (186; the two-line's own reference form).
   The prediction: the failed-attempt truncation shortens it; the two-line's park dynamics may
   absorb the lock-on cost that failed on the direct interface.
2. **The interval on the failed-carried attempts** (the direct-interface primary form, for
   comparability) + the per-arm placement counts.
3. **The window placed/min** (186) - reported, not the primary (the moved-branch discipline).
4. **K2: <= 2 clean-leg aborts across the treatment battery** (3 runs x 20 = 60 attempts;
   the per-attempt rate reported - the frozen cap was 2 per 75 attempts, so the denominator is
   pinned here to avoid a silent 3.75x loosening; the load-floor form read 0 on the direct
   interface).
5. **The fire readout**: fires, the fired-leg class (escaping vs clean), `asym@fire` min.
6. The cycle (`_recycle`-free per-attempt ticks), the starved polls, the gate waits.

## Kills (any one; applied exactly)

1. **The treatment arm's motion budgets / success floor FAIL** (`105_motion_regression.py
   --min-success-rate 0.5` on the treatment pair); a `190` *fingerprint* mismatch on the moved
   branch is recorded as the attractor statement, **not** a kill (a working fast-skip moves the
   branch by construction); the acceptance floor applies to the shipped acceptance, which the
   knob-off path must still pass;
2. **K2 fires** (clean-leg aborts > 2);
3. a new failure reason appears;
4. any descent outside its motion budget;
5. the primary interval does not fall by >= 5 % (the moved-branch floor).

## The no-harm bar

The knob-off two-line pair is **bit-identical to the P10-A record** (expect 861/861 vs
`logs/p8/36_patch_control.log`); the knob-off acceptance is **365/365** vs
`logs/p2d/90_accept.log` (9/10 + fingerprint matches); `selfcheck.sh` PASS; `172`.

## What this does NOT do

It does not touch the shipped defaults (both knobs default off); it does not re-seat (the B'
success-rate form needs its own pre-registration); it does not change the routing semantics or
the park gate.

---

## Amendment (FROZEN 2026-10-17, BEFORE the battery; orchestrator)

**The arm-B env needs the scope knob.** This pre-registration was written before the
implementation named the scope switch; as implemented (default-off semantics), the literal
arm-B env above (`FRUIT_CARRY_MONITOR=1 FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5`) is **inert on
the two-line path**. **Arm B is therefore: `FRUIT_CARRY_MONITOR=1
FRUIT_CARRY_MONITOR_LOAD_FLOOR=3.5 FRUIT_CARRY_MONITOR_TWOLINE=1`** (env-only; no code
change; the implementation lane flagged it in `logs/p10c/IMPLEMENTATION.md` section 4, and
its 96-row scope truth table verifies the knob-off path is byte-inert on every row). All
other arms, endpoints, kills and the no-harm bar are unchanged. Tree at battery time:
`tasks.py` `09c920c99b7a6a75d16e5a99dcda1872`, `rl_env.py` `9bb43c4c9e8dc2740bd2c7f8e3f7e1c1`
(the `TASKS_MD5` match verified).
