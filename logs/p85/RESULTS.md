# P85 results - the shipped scripted cell is the bimanual two-line

Parent: `logs/p85/PREREG.md` (`ba98029d`), `logs/p85/PREREG_ACCEL.md`
(`50b02576`), both pinned before any run. Battery: `logs/p85/run_p85.sh`, one
`scripts/154_claim_run.sh` claim per cell, sequential; header (`logs/p85/header.txt`)
carries the tree and the config md5s.

## 0. The change

| knob | shipped before P85 | shipped now | restore |
| --- | --- | --- | --- |
| `FRUIT_BIARM` | unset = off | **`1`, defaulted** | `FRUIT_BIARM=0` |
| `FRUIT_BIARM_TWOLINE` | unset = off (opt-in) | **`1`, defaulted** | `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0` (shared station) |

Resolvers: `src/fruit_sorting/bimanual.py` `resolve_biarm` / `resolve_twoline`
(one per knob, `defaulted` origin flag) and `biarm_resolution()` (the single call
every consumer uses). `tasks.bimanual_enabled()` and `run_bimanual()` read it;
`tasks.two_line_enabled()` became the **session** predicate
(`session.twoline`, False outside a session) with `two_line_resolved()` as the
ambient form; the supply package (`fruits.SupplyPlan.from_env(cfg, two_line=...)`)
follows the same resolution. The log says which cell it ran:

```
[fruit] [biarm] scheduler: FRUIT_BIARM=1(default) FRUIT_BIARM_TWOLINE=1(default)
[fruit] [biarm] two-line scheduler: left station y=+0.000, right station y=-0.100 (separation 0.100 m)
```

**Scope.** The three scripted entries (`20_pick_place.py`, `40_collect_demos.py`,
`70_record_video.py`) pass the resolution to their spawner. `SortingRLEnv` and
`scripts/60_eval_policy.py` pin `two_line=False`: neither is the scripted cell,
so neither can see the flip and their cells are byte-identical. The hybrid
canary is additionally out of reach by construction (`accept_policy.sh` builds
its own `FruitSpawner`/`PickAndPlaceTask` and never constructs `CoopSession`), so
it was **not re-run** as an acceptance.

## 1. The flip is resolution-only (P1: PASS, both seeds)

| cell | log | vs the pre-flip opt-in record |
| --- | --- | --- |
| 20 attempts, seed 5, default | `logs/p85/base20_s5.log` | **865/865 `[fruit]` physics lines identical to `logs/p80/T20.log`** |
| 20 attempts, seed 6, default | `logs/p85/base20_s6.log` | **814/814 identical to `logs/p80/T6.log`** |
| 20 attempts, seed 5, `FRUIT_SPEED_ALL=1` | `logs/p85/speed20_s5.log` | **799/799 identical to `logs/p80/V20.log`** (the union's opt-in two-line arm) |

The comparison drops only the phase's instrumentation rows (the `[carry]`
tracker, its `[diag] carry-assist` rows, and the one new scheduler banner). That
the *treatment* arm also replays its P80 record line for line is the strongest
form of the claim: the flip changed reachability, not physics.

The delivered numbers are therefore P80's, with P82's wall:

| cell | placed | sim s/attempt | pooled interval | placed/min (window / batch) | wall/pick | placed/min wall |
| --- | --- | --- | --- | --- | --- | --- |
| **base20_s5** (shipped) | **16/20 = 80 %** | **9.70** | **10.77** s (p90 18.00) | **5.57 / 4.96** | **16.57 s** | **2.90** |
| base20_s6 | 10/20 = 50 % | 9.70 | 19.34 s (p90 35.60) | 3.10 / 3.11 | 15.58 s | 1.93 |
| single arm, pre-P85 record (`logs/p80/S20.log`) | 12/19 = 63 % | 15.10 | 26.72 s | 2.25 / 2.08 | 25.2 s | 1.50 |

Per-arm at seed 5: left 9/10, right 7/10, idle 18.1 % / 21.4 %, lock-on
3.83 s / 4.54 s (19 retry polls each) - P80's numbers exactly. The wall is
**331.4 s against T20's 497.2 s** because P82's wake-on-request is the arbiter's
default; wall/sim 1.71x.

## 2. The acceptance moves to the two-line scenario (P2: PASS)

`scripts/accept.sh` (10 attempts, shipped default), recorded by the battery as
`logs/p85/accept10.log` and then re-run end to end by the shipped command
(`logs/p85/accept_final.log`):

* **7/10 placed, 9.2 s/attempt, 92.4 s sim**, `diverted=1`, all failures the
  `fruit did not follow the gripper` (never-grasped) class;
* **424/424 `[fruit]` physics lines identical to `logs/p80/T10.log`**, the
  pre-flip opt-in two-line 10-attempt run;
* `190_twoline_gate.sh -m 0.60` against
  `configs/motion_reference_twoline.json` (`eb697f23`): **PASS**.

So the acceptance's new scenario **is** the two-line dense scenario the repo
already had a reference for. The re-record:

| file | before | after | archive |
| --- | --- | --- | --- |
| `configs/motion_reference.json` | `8952c320` (single arm, 6/9) | **`eb697f23`** (two-line, 7/10) | `logs/p85/motion_reference_single_pre_p85.json` |
| `configs/motion_reference_single.json` | - | **`8952c320`** (the restore path's own reference) | same bytes as the archive |
| `configs/motion_reference_twoline.json` | `eb697f23` | **untouched** | - |

`105 --write-fingerprint` refuses a motion-budget failure but writes through a
rate-only one; it wrote this file and reported the single-arm 0.75 floor as the
reason it is not a 105-gate (the two-line floor is 0.60, applied by 190).

**The gate is honest now.** `scripts/accept.sh` reads the session from the log:
a two-line session goes through `scripts/190_twoline_gate.sh -r configs/motion_reference.json
-m 0.60` (the scenario pin + the two-line floor + the per-scenario reference, one
definition, not a second floor inside 105); anything else keeps 105 with
`configs/motion_reference_single.json`. `scripts/selfcheck.sh`'s optional
motion-budgets leg takes the same branch.

## 3. The restore path is byte-identical (P3: PASS)

`FRUIT_BIARM=0`, same batch, same instrumentation (`logs/p85/single10.log`):

* **6/9 placed, 14.8 s/attempt, 133.6 s sim**;
* **346/346 `[fruit]` lines identical to `logs/p71/accept_rails_none.log`**, the
  record the archived reference was written from;
* `105 --fingerprint logs/p85/motion_reference_single_pre_p85.json`:
  **fingerprint: matches** (the FAIL is the standing rate clause: 6/9 < 0.75 is
  this tree's branch since P32/P71, not a P85 effect).

The shared-station restore (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`) is pinned
offline by `scripts/246_p85_selftest.py` (the label reads `twoline=0(explicit)`
and `two_line_enabled()` is `session.twoline`), not re-run: it shares the same
session code the two-line drives, and its own rate record is pre-P85.

## 4. The collector inherits the flip and names it (P5: PASS)

`scripts/40_collect_demos.py` resolves through `biarm_resolution()`; its shard
manifest now carries, in the `collection` block:

```
"biarm_resolved": 1, "biarm_twoline_resolved": 1,
"biarm_defaulted": true, "biarm_twoline_defaulted": true
```

next to the raw `biarm`/`biarm_twoline` strings (which read `"0"` when unset and
would otherwise make a post-flip defaulted shard look exactly like a pre-flip
single-arm one). A manifest **without** these four keys predates P85. The
pre-existing `park_early`, `supply.wave`/`supply.patch` and `scene` blocks are
unchanged and still resolve the package. A two-episode defaulted shard was
collected to prove the writer end to end: `logs/p85/collect_probe/`.

## 5. What else moved, and what did not

* `scripts/153_biarm_rates.sh`: modes are explicit (`two-line` = the shipped
  cell, `shared` = the pre-P85 `FRUIT_BIARM=1`, `single`); `logs/biarm/` is the
  shared-station history.
* `scripts/126_branch_probe.sh` pins `FRUIT_BIARM=0` - it probes the legacy
  single-arm branch it was written for.
* `scripts/demo_2min.sh` runs the shipped cell (3-pick two-line smoke **1/3**,
  `logs/demo_picks.log`; clip `logs/video_demo/`, 1705 frames / 56.8 s) and its
  motion gate **PASS**es on the budgets with the scenario's own floor.
* No `src/` physics, no `configs/` file other than the two references above, no
  store and no checkpoint moved. `scripts/accept_policy.sh` was not run (see §0).

## 6. Falsifiers

* F1 (a default run that does not replay T20/T6): **not fired** - 865/865 and
  814/814.
* F2 (the single-arm restore diverging): **not fired** - 346/346 + fingerprint.
* F3 (a direct/policy path reading the two knobs): **not fired** -
  `rl_env.py` and `60_eval_policy.py` pin `two_line=False`, pinned by the `246`
  AST legs.
* F4 (a shard manifest that cannot tell pre- from post-flip): **not fired** -
  the four new keys.

## 7. Re-baseline (the sentence every later number carries)

**Every rate, acceptance, collector shard and store recorded before P85 is a
single-arm (or explicitly opt-in two-line) number.** The shipped scripted cell is
now the bimanual two-line. Reproduce a pre-P85 number with
`FRUIT_BIARM=0` (all scripted paths) and, for the direct/policy interface, the
pre-P85 restores composed as before (`FRUIT_ARM_PARK=ready` for pre-P43,
`FRUIT_POLICY_TRIGGER_ACQ=0` for pre-P54, `FRUIT_FEED_CADENCE=0
FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=0` for the pre-P58 burst
profile). The two references still name the scenario they were recorded from:
`configs/motion_reference.json` = the shipped (two-line) acceptance,
`configs/motion_reference_single.json` = the single-arm restore,
`configs/motion_reference_twoline.json` = the same two-line scenario's own file
(identical bytes to the shipped acceptance reference).
