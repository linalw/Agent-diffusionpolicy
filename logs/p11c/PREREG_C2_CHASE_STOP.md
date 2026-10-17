# P11-C.2 PREREG (FROZEN): the from-open arrival + the chase stop together (the measured requirement)

Frozen 2026-10-18 before any run. Branch `p-supply`; the P11-C wrap at `73bb151`.

## Why (the P11-C result's named next iteration)

The P11-C battery measured: the from-open arrival halves the falls at the primary seed
(7 -> 3) and gives +3 outcomes there, but the class re-draws against it at the controls
(no-grasp 4 -> 6, 1 -> 5) and the pooled moves -4 outcomes / +13 % interval. **The mechanism
reading: the arrival is clean, the DEPTH is not** - the horizontal close still runs to the
**chased** `keep_gap` (the force servo walked it up to 15 mm below the recorded depth), so the
marginal grips are disturbed at the deeper depth. The fix therefore needs the **chase stop**
(`FRUIT_FORCE_REENTRY=1`, the contact-gated force mode; `tasks.py:1847` gates it on the
dynamic capture, which the two-line catch runs) so the close lands at the *recorded* depth.

## The mechanism (env-only; no code change - both knobs exist)

Arm B = `FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1` + `FRUIT_FORCE_REENTRY=1`. Arm A = the shipped
two-line (the adopted monitor+gate). The scenario: the patch battery, seeds **11 (primary)**
+ **5/23 (controls)**, the standard env + `FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1`.

## Endpoints (pre-registered)

1. **Primary (the mechanism): the falls/blowups** - the `[carry]` `lowest payload point`
   <= -100 mm rows + the in-hand |v|max blowups, per arm per seed. The pre-registered
   positive form: the falls disappear at the primary seed (0 on B) or fall by >= 2/3.
2. **The class-shift check (the P11-C lesson): the no-grasp class** - B must not rise above
   the control by more than +1 at any seed (the P11-C's controls rose +2/+4).
3. The outcomes and the pooled interval (reported; the draw discipline).
4. The cycle (the +5 % non-inferiority margin; the chase stop shortens the walk).
5. No new failure reasons; the motion budgets (105).

## Kills

1. The falls/blowups do not fall by >= 2/3 at the primary seed;
2. the no-grasp class rises > +1 at any seed;
3. a new failure reason;
4. the cycle rises > +5 % at the primary;
5. the acceptance no-harm fails (385/385 + `fingerprint: matches`).

## The no-harm bar

The knob-off A runs replay the P10-C.3 flip records modulo the reporting rows; the acceptance
9/10 + `fingerprint: matches` + 385/385; `selfcheck.sh` PASS.

## What this does NOT do

No physics change; no grip improvement (the marginal grip remains - the class may still
shift; the rate may not improve); no shipped-default change (both knobs default-off).
