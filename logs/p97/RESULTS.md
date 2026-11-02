# P97 RESULTS - the clearance pre-pose ships as the two-line default; the invariant is the argument

Registrations: `logs/p97/PREREG.md` (md5 `fecf1a283ec3f82d05f5375c03901873`),
pinned before any run. The package's own commands are `logs/p97/run_p97.sh`; the
readouts `python3 logs/p97/p97_report.py` (-> `p97_report.txt`),
`python3 logs/p97/census.py` (-> `census.txt`) and `bash logs/p97/gates.sh`
(-> `gates.out`); the shard probe `scripts/run.sh logs/p97/manifest_probe.py`
(-> `manifest_probe.log`).

**Verdict in one line: the owner's invariant decision is shipped -
`FRUIT_BIARM_PREPOSE_CLEAR` now resolves on for a two-line session, so the
shipped line holds P96's clearance pre-pose (jaw `belt_top + 0.160 / +0.155`,
pad points `+0.079 / +0.075`, margins `+0.020 / +0.013 rad`), the contact
census of the shipped default is **0/20** on seed 5 (P96's pooled **1/40 ->
0/40**), and **no rate is claimed** (P96's two-seed count is the draw **29/40 ->
27/40**). The flip is resolution-only, proved three ways: the `=0` acceptance
reproduces **8/10 + `fingerprint: matches 30fb99f8`** with **419/419** physics
lines identical to `logs/p94/accept_final.log`, the single arm is **346/346**
raw identical to `logs/p71/accept_rails_none.log`, and the default's own
seed-5 cell is **924/924** identical to P96's measured `T5` once its one changed
label row is dropped.**

## 0. What ships, and what it is not

P96 measured the fix and did not ship it because its "no lost placement" clause
failed by its letter (`logs/p96/RESULTS.md` §4). The owner has decided: ship it
as an **invariant fix**. The argument is P95's geometry, not the count:

* the shipped pre-pose is the calibrated grasp configuration at the arm's own
  station - its pad point is **46 mm below the tallest fruit's top** and it sits
  on the **j3 limit (+0.000 rad)**, so the pre-pose blend sweeps through the
  fruit band on **every** attempt;
* the stations are `left y=+0.000` upstream / `right y=-0.100` downstream on a
  `-y` belt, so a **right**-arm fruit must cross the **left** station while that
  hand blends: P95 measured **1 pad contact in 40 attempts** and 5/19 right-arm
  attempts inside 6.4 mm. **A hand inside another lane's fruit band is a defect
  regardless of its rate** (P94's precedent).

The shipped arm is P96's, unchanged: `belt_top + 0.165`, `hold=calib` (the arm's
own **measured** calibrated attitude), achieved jaw **+0.160 left / +0.155
right**, pad points **+0.079 / +0.075**, margins **+0.020 / +0.013 rad**; the
height band `[0.155, 0.25]` still raises outside itself. Nothing else moves -
the descent, hover, close, carry, place, release clock, feeder, selection and
the 45 + 20-tick blend are untouched.

**Not claimed:** a rate. P96's count is **29/40 -> 27/40** (seed 5 **-5**, seed
6 **+3**, per arm **-1 / -1**) - a branch draw at n = 40; P93's power statement
for a 5-point difference is 364 attempts/arm. The sanity cell below is a
**report**, not a rate.

## 1. The flip, and the integration defect the inertness pass found

One constant changes (`tasks.PREPOSE_CLEAR_TWO_LINE_DEFAULT = False -> True`);
the resolver table is P96's:

| `FRUIT_BIARM_PREPOSE_CLEAR` | two-line session | resolves |
| --- | --- | --- |
| unset / empty | yes | **on** (`default`) |
| unset / empty | no | off (`scope-off`) |
| `0`/`off`/`false`/`no` | any | off (`explicit`) - the pre-P96 path, bit for bit |
| `1`/`on`/`true`/`yes` | any | **on** (`explicit`) |

**The first post-flip acceptance was byte-identical to the pre-P97 record - and
that was a bug, not inertness.** `_prepare_two_line_stations` is called *before*
`CoopSession` is created, and it resolved
`prepose_clear_resolution(self.two_line_enabled())`; `two_line_enabled()` is a
**session** predicate, so on the first batch (`_active_session is None`) it reads
False and the defaulted cell silently resolved off.
`logs/p97/accept_inert_pre_fix.log` is that run: **8/10, `fingerprint: matches
30fb99f8`, 419/419** identical to `logs/p94/accept_final.log` - i.e. the flip
was inert. P96 could not see this: every treatment cell set
`FRUIT_BIARM_PREPOSE_CLEAR=1` explicitly, and an explicit value bypasses the
session predicate.

The fix is part of the flip, not a second lever:
`_prepare_two_line_stations(two_line)` now takes `run_bimanual`'s resolved
decision (the same local that becomes `session.twoline` after the solve) and
calls `prepose_clear_resolution(two_line)`; one call site, pinned by the `253`
leg (`_prepare_two_line_stations(two_line)` + `prepose_clear_resolution(two_line)`
in the AST). With it, the default runs the measured pose - the pose rows are
`FRUIT_BIARM_PREPOSE_CLEAR=1(default)` and both stations read `CLEARS`.

## 2. The three identities (the flip is resolution-only)

| proof | reading |
| --- | --- |
| **G1 - the `=0` A/B** (`logs/p97/accept_pre97.log`) | **8/10, 9.0 s/attempt**, `fingerprint: matches configs/motion_reference.json` = **`30fb99f8`**, and **419/419** physics `[fruit]` lines byte-identical to `logs/p94/accept_final.log` |
| **G2 - the single arm** (`logs/p97/accept_single.log`) | **6/9, 14.8 s/attempt**, `fingerprint: matches configs/motion_reference_single.json` = `8952c320`, and **346/346** raw `[fruit]` lines byte-identical to `logs/p71/accept_rails_none.log`; the exit=1 is the standing rate-only floor (6/9 < 0.75), the P32 branch - not this phase's |
| **G3 - the default is the measured arm** (`logs/p97/S5.log` vs `logs/p96/T5.log`) | **924/924** identical after dropping the two `[biarm] pre-pose` rows; the only text difference in those rows is the registered origin label (`1(explicit)` -> `1(default)`) - same target, achieved jaw/pad, tilt, margin and residual |

G3 is what makes the package attributable: the shipped default is not merely
"similar to" P96's treatment, it is the same `[fruit]` stream at the same seed
and instrumentation, so P96's census, clock and landing numbers transfer.

## 3. The shipped default's sanity cell and census (report only)

`S5` - 20 attempts, seed 5, `FRUIT_BIARM_PREPOSE_CLEAR` **unset**, P96's census
instrumentation. It is byte-identical to P96's treatment cell (G3), so its
delivered numbers are P96's clearance-cell numbers and the cell is reported, never
gated:

| reading | value |
| --- | --- |
| placed | **12/20 = 60 %** (left 5/10, right 7/10), `diverted=2` |
| per attempt | **9.70 s/attempt** (sim 193.5 s) |
| interval | mean **16.02 s**, p90 **21.30 s** |
| rates | placement window **3.75** / batch **3.72** placed/min |
| wall | **432.4 s**, wall/pick **21.62 s**, **placed/min wall 1.66** |
| classes | placed 12, never-grasped 4, carried-not-placed 4; reasons `fruit did not follow the gripper` x4, `grasped, not placed (no note)` x4 |
| `[cycle]` p50 | `prepose 0.71` (unchanged), `hover 0.63` (the lean-over no longer exists), `release 1.71`, `place 3.21` |
| landing | **12/12** payload-present releases `on_belt`, 0 upstream-lost traces |
| motion | **0/20** descents over budget (worst held-grip cone 1.69x, reported) |

**The census (the endpoint):**

| set | n | min gap | median | `<= 6 mm` | contacts |
| --- | --- | --- | --- | --- | --- |
| **shipped default, seed 5** | 20 | **+5.9 mm** | +165.1 | **1/20** | **0/20** |
| left (the hand that strikes) | 10 | +155.4 | +256.7 | 0 | 0 |
| right (the exposed lane) | 10 | **+5.9** | +29.0 | 1 | 0 |

The one `<= 6 mm` row is the instrument's own floor (the 6.9 cm pear, 36.9 mm
above a fixed 31 mm proxy radius: `36.9 - 31.0 = 5.9`), with a 0.1 mm span swing -
a proxy tangency, not a near-miss (P96 §3). The control register is P96's:
**min 0.0 mm, `<= 6 mm` 4/40, 1 contact/40 -> min +5.9, 1/40, 0/40**.

## 4. The re-record and the archives

Both two-line-side references moved because every two-line attempt moves. Each
was re-recorded from a **same-batch** 10-attempt run of the new default (the
attempt count each is gated at):

| file | old | new | source |
| --- | --- | --- | --- |
| `configs/motion_reference.json` | `30fb99f8` | **`1490b63e`** | `logs/p97/accept_default.log` |
| `configs/motion_reference_twoline.json` | `30fb99f8` | **`1490b63e`** | `logs/p97/twoline_ref.log` |
| `configs/motion_reference_single.json` | `8952c320` | **`8952c320`** (untouched) | - |

Pre-P97 archives: `logs/p97/motion_reference_pre_p97.json` and
`logs/p97/motion_reference_twoline_pre_p97.json` (both `30fb99f8`). The two
new-default runs are `[fruit]`-identical to each other (the two references are
the same scenario on this tree), and the **final `scripts/accept.sh` run is
byte-identical to the reference-source run** (`logs/p97/accept_final.log` vs
`accept_default.log`, **459/459** physics lines including the two pose rows) -
the re-record is from the branch it gates.

## 5. Provenance and QA

* **A fresh shard** (one-episode collector chunk, seed 21, `/tmp/p97_shard`)
  carries `collection.prepose_clear=1`, `prepose_clear_defaulted=true`,
  `prepose_clear_z=0.165` next to `mode=two_line`, `biarm_twoline_resolved=1`.
  The manifest is kept as `logs/p97/shard_manifest.json` (index
  `shard_index.json`); the 519 MB of episodes were deleted after the read.
* **The same builder without a collection run** (`logs/p97/manifest_probe.py`
  under the simulator python) writes the shipped config's manifest with the same
  three keys (`shard_manifest_probe.json`) - the acceptance is a scripted run and
  writes no manifest, so its witness is the `[biarm] pre-pose` row (`CLEARS` at
  both stations); the probe is how the *shard* path is checked without claiming
  the acceptance wrote one.
* **The `scene` block does not gain a pre-pose field** (PREREG §6): it is the
  scene's **collider set** and the lift rung; the pre-pose is a control pose and
  the collector's `collection` block is its one owner. A duplicate would be a
  second source of truth for the same fact, which P72/P93's "one builder, one
  owner" rule forbids. No field was invented. A store **without**
  `prepose_clear` predates P96; a store with `prepose_clear=0` (and
  `prepose_clear_z=0`) is the pre-clearance-pre-pose path (the P96-era shipped
  store, or an explicit restore); `prepose_clear=1` is the clearance pose, and
  `prepose_clear_defaulted=true` is the P97 default (P96's treatment shards read
  `defaulted=false`).

## 6. The gates

| gate | reading |
| --- | --- |
| `scripts/190_twoline_gate.sh` on `accept_default` / `twoline_ref` | **PASS** both, against the re-recorded `1490b63e`, floor 0.60 |
| `scripts/accept.sh` end-to-end | **PASS** (`logs/p97/accept_final.log`: 6/10, 9.6 s/attempt, `fingerprint: matches`, `190: PASS`) |
| `scripts/selfcheck.sh` | **PASS, 0 failures, 1 skipped** (`logs/selfcheck.log`; the `253` leg reads the flipped default, 42 checks) |
| `scripts/211_bed_audit.py` | **ok (115 checks)** |
| `scripts/106_index_audit.py` | **OK** (every index matches its files) |
| `scripts/107_collect_merge_test.py` | **PASS (21 checks)** |
| `bash logs/p97/gates.sh` | **rc=0** - G1/G2/G3 identical, census 0 contacts, both references match, the fresh shard carries the three keys |

## 7. Pins, and the re-baseline

| file | md5 |
| --- | --- |
| `src/fruit_sorting/tasks.py` | **`e50872637afa1c4e63646a2f99c8a759`** |
| `src/fruit_sorting/rl_env.py` | **`eb545c8643d46ba2f384201c18def0de`** (`TASKS_MD5` follow) |
| `scripts/253_p96_prepose_selftest.py` | **`4c2ffcf2765cfd1c7d64d7e9f60da515`** |
| `scripts/selfcheck.sh` | **`bb1f5b53871714c0fe195920f03b23e6`** |
| `logs/p97/PREREG.md` | **`fecf1a28`** (pre-run) |
| `logs/p97/p97_report.py` / `census.py` | **`54eb9b2b`** / **`8a95a821`** |
| `logs/p97/run_p97.sh` / `gates.sh` / `manifest_probe.py` | **`f7211537`** / **`9143611b`** / **`e8e0b960`** |
| `configs/motion_reference.json` / `..._twoline.json` | **`1490b63e`** / **`1490b63e`** (pre-P97 `30fb99f8` archived) |
| `configs/motion_reference_single.json` | **`8952c320`** (untouched) |
| checkpoint | `moe_v13s` `61da390a` (untouched) |

**Re-baseline: every two-line rate, interval, acceptance and store recorded
before P97 is a pre-clearance-pre-pose number; `FRUIT_BIARM_PREPOSE_CLEAR=0`
restores it.** Compose with the earlier restores: `FRUIT_ARM_PARK=ready`
(pre-P43), `FRUIT_POLICY_TRIGGER_ACQ=0` (pre-P54), the P58 burst profile
(pre-P58), `FRUIT_SPEED_RELEASE=0` (pre-P87), `FRUIT_CARRY_OFFSET_MAX=0`
(pre-P94). The single arm, the shared station, the hybrid canary and the
direct/policy interface are **outside the two-line session** and cannot read the
knob (G2; `prepose_clear_resolution(two_line)` is `scope-off` without a session).
