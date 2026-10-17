# P11-C PREREG (FROZEN): the re-seat approach geometry - the ejection fix (two-line)

Frozen 2026-10-18 before any Tier-A run. Tree pin recorded at battery time (the implementation
lane's md5). Branch `p-supply`. Evidence: `logs/p11/A_PHYSICS_AUDIT.md`, `logs/p11b/B_EJECTION_PROBE.md`,
`logs/p10e/NOGRASP_DIAGNOSIS.md`, `logs/p11b/C_DECISION.md`.

## Why

The no-grasp class is 52.7 % of the two-line failures / 51.4 % of the failure mass; its B1
chain (60 % of the class) ends in a **kinematic ejection** (13/18 fall 1.3 m to the floor,
4/30 solver blowups). The probe measured: the ejection needs the **descend-at-the-contact-gap
geometry** (the shipped re-seat); the **close-from-open** geometry never ejects; the contact
parameters do not matter.

## The mechanism (the bounded change; default off, two-line-scoped)

The re-seat approach reproduces the close-from-open geometry: descend with the jaws wider
than the blocking span (no descent contact), then close horizontally to the grip depth. New
knob `FRUIT_DYNAMIC_REGRASP_FROM_OPEN` (default 0 = the shipped form, byte-inert), resolved
through `_dynamic_profile` for the two-line only. Optional companions in the same battery as
separate arms if the implementation is cheap: the chase stop (`FRUIT_FORCE_REENTRY=1`) and a
bounded ratchet.

## Arms and scenario (Tier A)

| arm | env | notes |
| --- | --- | --- |
| A | the shipped two-line (the adopted monitor+gate; no env) | the control; the P10-C.3 flip records stand if the no-harm replay holds |
| **B** | A + `FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1` | the treatment; the patch battery at SEED=11 (the hard seed) + SEED=5/23 controls; `FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1` |

`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 HEADLESS=1 FRUIT_MOTION_REPORT=1
FRUIT_CYCLE_REPORT=1`; `scripts/154_claim_run.sh` per run.

## Endpoints (pre-registered)

1. **Primary (the mechanism, the P10-E falsifier): the arrival geometry** - on every B1-class
   attempt, the re-seat's first contact happens from the close-from-open approach (no
   descend-at-the-gap contact): the first keep-gaps >= the live extent and the descent contact
   force ~0. Expected: the ejection signature (the fall, the `lowest payload point` << 0, the
   blowups) is **absent** on arm B.
2. The no-grasp class count and its sub-class split (B1/B2/C) per arm; the falls (the `[carry]`
   `lowest payload point` <= -100 mm rows) count.
3. The outcomes (reported, the draw discipline): the pooled + per-seed successes.
4. The motion budgets (105), the `190` gate (the per-scenario reference; a moved branch is the
   attestation, not a kill), no new failure reasons.
5. The cycle (the sim-clock; the +5 % non-inferiority margin).

## Kills

1. The knob-off byte-inert proof fails (the A records must replay modulo reporting rows);
2. the falls/blowups do NOT disappear on B (the mechanism reading fails);
3. a new failure reason appears;
4. the acceptance no-harm fails (the shipped acceptance 385/385 + `fingerprint: matches`).

## The no-harm bar

The shipped acceptance on the tree: 9/10 + `fingerprint: matches` + 385/385 vs
`logs/p2d/90_accept.log`; the knob-off two-line pair replays the P10-C.3 records modulo
reporting rows; `selfcheck.sh` PASS; `172` PASS.

## What this does NOT do

No physics change (the contact parameters stay; the realism gaps stay documented in P11-A);
no grip improvement (the marginal grip remains; the class may shift, the rate may not improve -
recorded in `C_DECISION.md`); no shipped-default change (the knob is default-off; adoption
would be its own pre-registration with the reference re-records).
