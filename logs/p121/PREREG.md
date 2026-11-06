# P121 - PRE-REGISTRATION: the direct/policy line decides its destination

Pinned before any validation cell ran (the only earlier direct run is a single
1-episode build smoke, `logs/p121/smoke_today.log`, used to prove the wiring and
excluded from every table). The scripted acceptance is the no-harm proof, not
part of this registration.

## Question

The owner's requirement has two halves: the cell must be able to decide *where*
a fruit goes from an instruction. P114/P115/P116 built that for the scripted
cell (descriptor, `and` rules, plan/lint, capability map, per-destination
ledger). The direct/policy line **refused** `FRUIT_SORT_INSTRUCTION` because it
selected and placed through its own grade lane. P121 makes the direct env use
the same instruction; this registration measures **whether the destination
decision is carried through selection, arm, goal and place** - not whether the
policy's success rate improves.

## What the code now does (one paragraph, no numbers)

`rl_env.direct_dispatch` replaces `bin_index = 0 if grade == "A" else 1` /
`active = "left" if bin_index == 0 else "right"` with, when an instruction is
armed, the fruit's `sort_destination` and the capability map's
`arm_for_destination`; the selector (`tasks.select_target` with
`_sort_admits`) admits only fruits whose destination is served, `skip`/unmatched
never selected. The goal vector keeps `[xyz, velocity, diameter, bin_index]`;
for destinations 0/1 `bin_index` is the same value the shipped lane produced
(dest 0 = left, dest 1 = right), so the trained input is unchanged. The place
leg reads the thread-local target (`tasks.dispatch_destination` ->
`_place_xy_for`), the leg is named `place<destination>`, and the `[sort]`
attempt row / per-destination ledger are emitted by `sort_ledger_attempt` from
the payload's release position (the same code the scripted path runs). A third
destination makes the goal's `bin_index` an unseen input (2.0): it is refused
unless `FRUIT_SORT_THIRD_DEST=1`, and that cell is declared OOD.

## Cells (all: shipped direct config, 3 seeds x 10 episodes = 30 attempts)

Seeds **77 / 101 / 202**, checkpoint `moe_v13s` (`61da390a`), the P66 phase-3 /
P71 phase-2 / P73-P77 scenario env verbatim (`FRUIT_SUPPLY_SCATTER=1
FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1
FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1`).

| cell | instruction | other | what it must show |
| --- | --- | --- | --- |
| **C** | unset | - | the shipped direct control: no `[sort]` row at all, the recorded failure classes, a count in the family's branch range |
| **T1** | `logs/p114/instructions/today.txt` (`grade=A => 0`, `grade=B => 1`, `grade=C => skip`) | - | destination/arm table equals C's routing; ledger `in_destination/released` = 100 %; C's fruits are never selected |
| **T2** | `size<40 => 1`, `default => 0` (a **non-grade** rule) | - | the destination is independent of the grade: at least one grade-A fruit released on dest 1 (right) **and** at least one grade-B/C fruit released on dest 0 (left) |
| **T3** | `logs/p114/instructions/three_dest.txt` (`grade=A => 2`, `grade=B => 1`) | `FRUIT_SCENARIO=logs/p114/scenarios/three_dest.json`, `FRUIT_SORT_THIRD_DEST=1` | dest 2 (the +Y belt's upstream zone, `reach: auto`) is solved at startup and every dest-2 release lands nearest dest 2; the ledger names dest 0/1/2; the goal value 2 is OOD (stated, not assumed safe) |

Default-off check: a fifth run is **not** spent - the 1-episode `T_third_off`
smoke (the same instruction with `FRUIT_SORT_THIRD_DEST` unset) must raise the
env's refusal before the first attempt; the selfcheck leg pins the same text.

## Endpoints (primary = the ledger, never a rate)

* **P1 assignment accuracy**: `[sort] ledger` `in_destination / released` per
  cell (T1/T2/T3). PASS = 100 % in each cell; a single `in_dest=0` on a placed
  fruit is a mis-sort and fails the phase (the P114 capability rule).
* **P2 per-destination ledger**: the `[sort] ledger dest=N` rows name the
  destinations the instruction assigned, and the counts sum to P1's.
* **P3 grade independence (T2)**: the two-witness clause above, read from the
  `[sort] attempt` rows (`grade=`, `dest=`, `in_dest=`), not from the plan.
* **P4 placed count**: **report only** - the direct loop is not reproducible
  (rendered frames; P37/P43/P54), so a count difference between cells is a
  branch draw. Quote both the count and the failure classes.
* **P5 failure classes**: every C/T failure maps to the recorded set
  (`grasped=False`/`cnp`/`fell off the line`/`timeout`); a new reason key is
  reported, not smoothed. The `[sort]` rows themselves are not failure reasons.
* **P6 no-instruction control**: C prints **zero** `[sort]`/`[scenario]` rows
  and its `[rl] episode` count/classes are in the same-batch family (the
  pre-P121 P77 `C_77` 15-episode cell is the historical reference, quoted as a
  branch, not a rate).
* **P7 goal-channel statement**: destinations 0/1 keep the trained
  `bin_index` values; only T3 writes 2.0, and T3 is labelled OOD.

## Guards

* `scripts/accept.sh` (scripted) = **8/10 + `fingerprint: matches` + `190:
  PASS`**; the env change cannot touch the scripted path (proved by the
  acceptance stream, not by inspection).
* `scripts/selfcheck.sh` PASS with the new `263` leg.
* an instruction mapping to a destination no arm serves (P114's tray,
  `reach_unreachable`) raises before the first attempt (the `263` leg executes
  the capability map and the env's `FRUIT_SORT_THIRD_DEST` refusal).

## Falsifiers (fire = the phase is negative, recorded as such)

1. Any placed fruit whose ledger `in_dest=0`, or a release position nearest a
   destination other than the ledger's `dest=`.
2. A mapped fruit that is never selected while it was catchable (selection
   admission bug) - read from the `[bed-sel]` refusal reason, never inferred.
3. An instruction that moves the shipped (C) routing without `[sort]` rows
   (inert wiring) or prints `[sort]` rows without an instruction (unset path
   moved).
4. The three-destination startup solve marks dest 2 `UNREACHABLE`: that is a
   **scope limit of the cell** (P114 measured it reachable at 6.0 mm), not a
   wiring failure; record it and stop at the two-lane claim.

## Reading rules

No rate is claimed. The direct loop's count is a branch; the endpoint is the
ledger's assignment accuracy and the per-destination table. The scripted
acceptance is the no-harm proof. No motion budget is re-tuned.
