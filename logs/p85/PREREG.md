# P85 pre-registration - the two-line becomes the shipped default

Pinned **before any simulator run of this phase**. Pin: `logs/p85/PREREG.md5`.

## 0. What the owner authorized

The W3/R5 register held `FRUIT_BIARM_TWOLINE` opt-in because the two-line
replaces the *meaning* of the shipped scripted cell: pure grade lanes (left = A,
right = B, C recycled at `despawn_y`), a supply package that ships with it (the
dense wave sheet + the balanced A:B:C 0.375/0.375/0.25 mix), and a scheduler
that overlaps the two arms' attempts. `docs/THROUGHPUT.md` §"What is left" and
AGENTS' W3/R5 records name the owner's sign-off as the blocker; **the owner gave
it for P85**. This phase is the flip plus its full re-baseline.

## 1. The change (resolution only, no physics)

* `FRUIT_BIARM` defaults to `1`, `FRUIT_BIARM_TWOLINE` to `1`, resolved by
  `bimanual.resolve_biarm` / `resolve_twoline` (one resolver per knob, the
  `resolve_arm_park` / `_dynamic_profile` style), with the origin printed and
  recorded (`FRUIT_BIARM=1(default) FRUIT_BIARM_TWOLINE=1(default)`).
* `FRUIT_BIARM=0` restores the pre-P85 single arm; `FRUIT_BIARM=1
  FRUIT_BIARM_TWOLINE=0` restores the F2 shared-station pipeline. Both must be
  byte-unchanged.
* The **supply package** follows the same resolution (`SupplyPlan.from_env(cfg,
  two_line=...)`, passed by the three scripted entries only). The direct env and
  the hybrid canary pin `two_line=False`: they are not the scripted cell and
  must stay byte-identical.
* `two_line_enabled()` becomes **session-scoped** (it is the scope predicate
  three task sites use); the ambient resolution is `two_line_resolved()`.

## 2. Predictions (registered before the runs)

* **P1 - the flip is resolution-only.** A 20-attempt default run (seed 5,
  `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`, and the phase's `[carry]`
  instrument) replays P80's `T20` `[fruit]` stream **line for line**, modulo two
  instrumentation-only differences: the one new `[fruit] [biarm] scheduler:`
  banner and the `[fruit] [carry]` tracker rows. The tracker's neutrality on
  this line is P84's own result (its `D5`/`D6` replay `T20`/`T6` at 865/865 and
  814/814 with exactly those rows dropped), so a difference on the filtered
  stream is a real physics difference and F1 fires. Seed 6 replays `T6` the same
  way. (T20/T6 were explicit `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`; the flip
  makes them the default.)
* **P2 - the acceptance's new scenario is the two-line dense one.** The
  10-attempt default log therefore matches the existing
  `configs/motion_reference_twoline.json` (`eb697f23`) and reads **7/10**
  (`logs/p80/T10.log`). The re-recorded `configs/motion_reference.json` should
  be byte-identical to that file; if it is not, the two are different
  attractors and the acceptance owns its own record.
* **P3 - the single-arm control is untouched.** `FRUIT_BIARM=0` at 10 attempts
  replays the archived pre-P85 record
  (`logs/p85/motion_reference_single_pre_p85.json`, `8952c320`, 6/9) with its
  `[fruit]` stream **byte-identical**, including the line count.
* **P4 - the direct/policy presentation is untouched.** `SortingRLEnv` and
  `scripts/60_eval_policy.py` pin `two_line=False`; no direct number moves.
  `scripts/accept_policy.sh` is **not run** as an acceptance: it builds its own
  `FruitSpawner`/`PickAndPlaceTask` and never constructs the bimanual session,
  so the flip has no path to it (P58's argument, restated).
* **P5 - the collector inherits the flip and says so.** A defaulted shard's
  manifest records `collection.mode=two_line`, the resolved pair and both
  origin flags; a pre-P85 shard has none of the four new keys.

## 3. Acceptance of the flip (all must hold)

* A1: the acceptance (10 attempts, default) runs, is gated by
  `scripts/190_twoline_gate.sh -r configs/motion_reference.json -m 0.60`, and
  its fingerprint is **the re-recorded file** (written from that same-batch
  log). The pre-P85 file is archived to
  `logs/p85/motion_reference_single_pre_p85.json` first.
* A2: `FRUIT_BIARM=0` (same batch) matches the archive.
* A3: seed-5 and seed-6 default rate runs replay `T20`/`T6` (P1).
* A4: `scripts/selfcheck.sh` PASS, `scripts/106_index_audit.py` and
  `scripts/107_collect_merge_test.py` PASS.
* A5: `scripts/demo_2min.sh` still runs (its own motion gate, adapted to the
  scenario it ran - a 3-pick smoke is not the acceptance).
* A6: no `configs/` file moves except the two references the flip legitimately
  moves (`motion_reference.json` -> the acceptance's two-line record, plus
  `motion_reference_single.json` = the pre-P85 archive for the restore path).
  `configs/motion_reference_twoline.json` is **not** touched: the flip's
  acceptance scenario *is* its scenario, so it stays the two-line file's own
  record (see P2).

## 4. Falsifiers

* F1: a default 20-attempt run that does **not** replay `T20`/`T6` - the flip
  then changed behaviour, not just reachability, and the moved attributes must
  be named before any rate is quoted.
* F2: `FRUIT_BIARM=0` diverging from the archive - the single-arm restore is
  broken.
* F3: any direct/policy path reading the two knobs.
* F4: a shard manifest that cannot tell a pre-flip shard from a post-flip one.

## 5. Read rules carried in from the record

* A count is one draw of a deterministic branch; quote it with its fingerprint.
* Two-line and single-arm numbers are different scenarios; the two-line floor is
  0.60 (P39/P71/P80 convention), the single arm's 0.75 stays 105's.
* Every pre-P85 number is a single-arm (or opt-in two-line) number; the restores
  are `FRUIT_BIARM=0` (all paths) and, composed with it,
  `FRUIT_ARM_PARK=ready` / `FRUIT_POLICY_TRIGGER_ACQ=0` / the P58 burst profile
  for the direct/policy interface.
