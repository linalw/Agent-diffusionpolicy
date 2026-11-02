# P98 RESULTS - the P97 revert: the clearance pre-pose is opt-in again

Registration: `logs/p98/PREREG.md` (md5 `135b14f9cbca6b07dee5c3e94e9dc26b`),
pinned before any run. The package's commands are `logs/p98/run_p98.sh`; the
readouts `python3 logs/p98/p98_report.py` (-> `p98_report.txt`) and
`bash logs/p98/gates.sh` (-> `gates.out`).

**Verdict in one line: the owner's revert is shipped - the two-line session is
back on the pre-P96 pre-pose path (`PREPOSE_CLEAR_TWO_LINE_DEFAULT = False`,
unset resolves off), both two-line-side references are restored to
`30fb99f8`, the same-batch acceptance reads **8/10, 9.0 s/attempt,
`fingerprint: matches` + `190: PASS`** with **419/419** physics lines identical
to `logs/p94/accept_final.log`, and the `=1` A/B reproduces P97's shipped-default
arm (6/10, 457/457 on its physics stream with the two pre-pose rows dropped,
fingerprint DIFFERS by construction).**

## 0. What the revert is, and what it is not

P97 shipped P96's clearance pre-pose as the two-line default on the **invariant**
argument, with the count explicitly not claimed. P97's own record then read:

| reading | P97 shipped default | pre-P97 / P94 |
| --- | --- | --- |
| `scripts/accept.sh` (10 attempts) | **6/10 at the 0.60 floor** | **8/10** |
| seed-5 sanity cell (20 attempts) | **12/20 = 60 %** | 17/20 |
| inter-placement interval (seed 5) | **16.02 s** | 10.59 s |
| contact census `<= 6 mm` | 1/20 (the proxy's own floor) | 4/40 pre-P96 |

The invariant is real (P96's census: contact 1/40 -> 0/40) and stays available;
what cannot stand is the **shipped acceptance sitting on its rate floor** - a
zero-margin gate cannot separate the shipped line from a regression, and the
gain was never a rate (P96's draw 29/40 -> 27/40). So P98 reverts the flip and
keeps the fix as the opt-in `FRUIT_BIARM_PREPOSE_CLEAR=1`.

**Not claimed:** any rate, any new census, any change to P96's measurement. The
revert says the shipped gate had no margin, not that the invariant is small.

## 1. The flip back, and the machinery that stays

`tasks.PREPOSE_CLEAR_TWO_LINE_DEFAULT = True -> False`. The resolver table is
P96's again:

| `FRUIT_BIARM_PREPOSE_CLEAR` | two-line session | resolves |
| --- | --- | --- |
| unset / empty | yes | **off** (`explicit`, the pre-P96 label; the constant is False since P98) |
| unset / empty | no | off (`scope-off`) - no two-line station exists |
| `0`/`off`/`false`/`no` | any | off (`explicit`) - the pre-P96 path, bit for bit |
| `1`/`on`/`true`/`yes` | any | **on** (`explicit`) - P96's measured pose |

Everything P96/P97 built is untouched: the solve height `belt_top + 0.165`, the
`hold=calib` attitude, the band `[0.155, 0.25]`, the height arithmetic
(`jaw_achieved = target - residual`), the one `prepose_clear_resolution(two_line)`
solve site (P97's integration fix - it is inert with the cell off and it is what
makes `=1` correct on the first batch), the gated `[biarm] pre-pose` row and the
collector's `collection.prepose_clear*` keys. The `253` selfcheck leg's table is
re-pinned to the reverted default (unset + two-line -> off, label
`FRUIT_BIARM_PREPOSE_CLEAR=0(explicit)`; `=1` still on at 0.165/calib).

## 2. The reference restore

P97 archived both pre-flip files; P98 copies them back byte-for-byte:

| file | P97 value | restored | source |
| --- | --- | --- | --- |
| `configs/motion_reference.json` | `1490b63e` | **`30fb99f8`** | `logs/p97/motion_reference_pre_p97.json` |
| `configs/motion_reference_twoline.json` | `1490b63e` | **`30fb99f8`** | `logs/p97/motion_reference_twoline_pre_p97.json` |
| `configs/motion_reference_single.json` | `8952c320` | **`8952c320`** (untouched) | - |

Both restored files equal their archive **and** the recorded `30fb99f8`
(`md5sum` verified before any run; G2).

## 3. The reverted default (P1)

`logs/p98/accept_revert.log`, `scripts/accept.sh`, 10 attempts, no env:

| reading | value |
| --- | --- |
| placed | **8/10 = 80 %**, `diverted=0` |
| per attempt | **9.0 s** (sim 89.9 s) |
| gate | **`fingerprint: matches configs/motion_reference.json` = `30fb99f8`**, **`190: PASS`**, floor 0.60 |
| physics identity | **419/419** `[fruit]` lines byte-identical to `logs/p94/accept_final.log` |
| motion | 10/10 descents inside budget (worst `|v|max` 0.112 vs 0.160-0.161; lurch 0.018 vs 0.291) |

The 419/419 identity is the same-batch proof the revert is **resolution-only**:
the P97 phase had already measured this exact path in its `=0` A/B, and the
restored constant lands on it bit for bit. The acceptance is no longer at its
floor: 8/10 against the 0.60 floor.

## 4. The `=1` A/B (P3) - budgets only, fingerprint differs by construction

`logs/p98/accept_clear1.log`, `FRUIT_BIARM_PREPOSE_CLEAR=1`, 10 attempts:

| reading | value |
| --- | --- |
| placed | **6/10 = 60 %**, `diverted=1` - P97's shipped-default count |
| per attempt | **9.6 s** (sim 95.7 s) |
| rate floor | 60 % >= the 0.60 two-line floor |
| budgets | **PASS** - 10/10 descents inside (worst `|v|max` 0.110), lurch 0.017 vs 0.291 |
| fingerprint | **DIFFERS** from `30fb99f8` - expected: the restored reference is the pre-P97 branch and the clearance pose moves every attempt; the arm is gated on budgets only |
| P97 identity | **457/457** physics lines identical to `logs/p97/accept_final.log` once the two `[fruit] [biarm] pre-pose` rows are dropped - their only text change is the registered origin label (`1(default)` -> `1(explicit)`); same target, achieved jaw/pad, tilt, margin and residual |

So the opt-in cell on this tree **is** P97's arm, and the revert costs the
invariant nothing it had; it only stops being the default. This is a
**descriptive** identity, not a rate: 6/10 vs 8/10 between two different
branches is the attractor, exactly as P97 recorded.

## 5. What is not run, and why

* **The single arm** (`FRUIT_BIARM=0`): the knob is `scope-off` without a
  `CoopSession` (G4), `configs/motion_reference_single.json` was never written,
  and P97's own single-arm run is 346/346 identical to the P71 record. No new
  run is owed by a constant the path cannot read.
* **A fresh shard**: the collector writes `prepose_clear=0` /
  `prepose_clear_defaulted=false` / `prepose_clear_z=0.0` with the env unset -
  the pre-clearance path, which is what this tree now ships. P97's shard
  (`prepose_clear=1`, `defaulted=true`) remains the record of its phase; a store
  with `prepose_clear=1` is P97's arm (or an explicit `=1`), a store with
  `prepose_clear=0` is this tree's default, and the P96-era default reads the
  same `0` (P97 §5's reading rule stands).
* **No new lever, no other default, no store, no checkpoint, no direct/policy
  run.** `rl_env.TASKS_MD5` follows the `tasks.py` docstring/constant edit
  (`6ce29b56`), metadata only.

## 6. The gates

| gate | reading |
| --- | --- |
| `scripts/accept.sh` (reverted default) | **PASS**: 8/10, 9.0 s/attempt, `matches 30fb99f8`, `190: PASS` |
| `scripts/190_twoline_gate.sh` on it | **PASS** (G1) |
| `scripts/accept.sh` with `=1` | **6/10, 9.6 s/attempt**; the gate's only failure is the fingerprint (`DIFFERS`) - by construction |
| `scripts/selfcheck.sh` | **PASS, 0 failures, 1 skipped** (`logs/p98/selfcheck.log`; the `253` leg reads the reverted table) |
| `scripts/211_bed_audit.py` | **ok (115 checks)** |
| `scripts/106_index_audit.py` | **OK** (every index matches its files) |
| `scripts/107_collect_merge_test.py` | **PASS (21 checks)** |
| `bash logs/p98/gates.sh` | **rc=0** - G1 419/419 + matches + 190 PASS; G2 both refs `30fb99f8` and the single `8952c320`; G3 457/457 + 6/10 + fingerprint DIFFERS asserted; G4 the `253` scope; G5 one constant |

## 7. Pins, and the re-baseline

| file | md5 |
| --- | --- |
| `src/fruit_sorting/tasks.py` | **`6ce29b56dbc0e55ee657dc862d750d7d`** |
| `src/fruit_sorting/rl_env.py` | **`82a120fc792a422da9dcd16f9853c7cd`** (`TASKS_MD5` follow) |
| `scripts/253_p96_prepose_selftest.py` | **`a6d4add1ae92007325a102cf3ec64a6d`** |
| `scripts/selfcheck.sh` | **`5937b46132ad8f3ecad3dc738c62544d`** |
| `logs/p98/PREREG.md` | **`135b14f9`** (pre-run) |
| `logs/p98/p98_report.py` / `gates.sh` / `run_p98.sh` | **`b6862252`** / **`a48e30f5`** / **`7131101d`** |
| `configs/motion_reference.json` / `..._twoline.json` | **`30fb99f8`** / **`30fb99f8`** (restored from the P97 archives) |
| `configs/motion_reference_single.json` | **`8952c320`** (untouched) |
| checkpoint | `moe_v13s` `61da390a` (untouched) |

**Re-baseline: the two-line numbers are back on P97's pre-clearance values** -
`configs/motion_reference.json` is `30fb99f8` and the shipped acceptance is
`8/10`. The P97 paragraph and its stores stand as that phase's record; a store
carrying `collection.prepose_clear=1 / prepose_clear_defaulted=true` is P97's
arm, not this tree's default. `FRUIT_BIARM_PREPOSE_CLEAR=1` restores the arm
P96 measured (contact census 1/40 -> 0/40, achieved jaw `+0.160/+0.155`,
pad points `+0.079/+0.075`, margins `+0.020/+0.013 rad`), and nothing else in
the P43/P54/P58/P87/P94 restore chain changes.
