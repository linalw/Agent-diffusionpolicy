# P87 - the release trim ships as a two-line-scoped default: -0.64 s of pure dwell at both seeds, the scope proved bit-for-bit, and one descent leg on one seed makes it a considered trade

Measured 2026-11-01. **One shipped change** - `FRUIT_SPEED_RELEASE` now resolves
**on for a two-line session** and off everywhere else - plus the `physics.release`
provenance and two re-recorded references. PREREG `logs/p87/PREREG.md`
(**`738c1b54`**, pinned before any run, unamended; `PREREG.md5`). Cells
`logs/p87/{C5,T5,C6,T6}.{log,stamps,driver}` (one claim each), the inertness runs
`single_accept.*` / `shared_{unset,zero}.*`, the acceptance `accept10.*` /
`accept_final.*`; read with `logs/p87/p87_report.py` -> `p87_report.txt`, gated by
`logs/p87/gates.sh` -> `gates.out`.

## 0. The change

| | before P87 | after |
| --- | --- | --- |
| `FRUIT_SPEED_RELEASE` unset, **two-line session** | off (20/3/3) | **on (0/2/2)**, `origin=default` |
| unset, single arm / shared station / canary / direct / collector `single` | off | **off** (`origin=scope-off`) - unchanged |
| `=0` (explicit) | off | off, on **every** path including the two-line |
| `=1` / `FRUIT_SPEED_ALL=1` | on | on, **globally** (an explicit `=0` beats the union) |
| `FRUIT_SPEED_RELEASE_SETTLE` | moves the settle | same, read only when the cell is on |

The clock: `dwell` 20 -> 0, the pad ramp 40 x (3 -> 2), the finger ramp
16 x (3 -> 2) = **-76 ticks = -0.633 s** at 120 Hz. **One arithmetic correction
to P86's PREREG**, recorded rather than propagated: its table printed the totals
as `208 / 132` ticks; the three holds sum to **188 / 112** (20 + 40x3 + 16x3 and
0 + 40x2 + 16x2). Both P86 rows carried the same +20, so the registered **delta
(-76 ticks, -0.633 s) and every band are unaffected** - which the measurements
confirm to two ticks.

The scope is `Task.two_line_enabled()` (the `CoopSession` predicate, False
outside a session), and one resolver (`tasks.release_speed_resolution`) feeds the
per-attempt holds, the log row and the manifest block. Sites: `tasks.py`
(`release_speed_resolution`, `speed_cell_defaults(two_line)`,
`_grasp_carry_place_impl`, the `[biarm] release profile:` row in
`run_bimanual`), `scene.py` (`_release_provenance` inside
`finger_physics_provenance`), `scripts/40_collect_demos.py` (`two_line=TWO_LINE`
on both calls), `rl_env.py` (`two_line=False` + the metadata `TASKS_MD5` follow),
`scripts/247_p87_release_scope_selftest.py` (the new selfcheck leg).

## 1. The row, and what it says

Both modes print it once per session, so a log names its own clock (the
`[biarm] scheduler:` / `[drive] finger cap scope:` convention):

```
two-line       [fruit] [biarm] release profile: FRUIT_SPEED_RELEASE=1(default) scope=two-line
               dwell=0 pad_hold=2 finger_hold=2 (112 ticks; shipped 188, saved 76)
shared station [fruit] [biarm] release profile: FRUIT_SPEED_RELEASE=0(scope-off) scope=shared-station
               dwell=20 pad_hold=3 finger_hold=3 (188 ticks; shipped 188, saved 0)
```

It prints **only** inside `run_bimanual`, exactly as `[drive] finger cap scope:`
prints only when the cap is armed - so the single arm, the hybrid canary and the
direct env print nothing, and **their byte identity is the proof** rather than a
line in a log (which would make the comparison "identical modulo a row").

## 2. G0 - the flip is resolution-only, proved by replay (PASS 4/4)

| cell | env | reference | result |
| --- | --- | --- | --- |
| **C5** | `FRUIT_SPEED_RELEASE=0`, seed 5 | `logs/p86/C5.log` | **865/865 identical** |
| **T5** | unset, seed 5 | `logs/p86/R5.log` | **868/868 identical** |
| **C6** | `=0`, seed 6 | `logs/p86/C6.log` | **814/814 identical** |
| **T6** | unset, seed 6 | `logs/p86/R6.log` | **821/821 identical** |

Filter = P86's (`[fruit] [carry]`, `[biarm] scheduler:`, `[diag] carry-assist`, the
park rows, `[task]   place trace`) **plus this phase's own row**. That is the
whole point of the phase: P86's treatment cells ran `FRUIT_SPEED_RELEASE=1`
(*explicit*); T5/T6 run it **unset** and resolve to the same clock, so **the
shipped default is the measured arm bit for bit** and P86's mechanism, landing
and ledger measurements transfer rather than being re-derived. The one line that
does move is the new row, and only in its `origin` field
(`=1(explicit)` -> `=1(default)`).

## 3. The gate (PREREG §5), seed by seed

`ATTEMPTS=20`, seeds 5/6, controls at `FRUIT_SPEED_RELEASE=0`, treatments unset,
P86's instrumentation on all four cells.

| clause | seed 5 | seed 6 | verdict |
| --- | --- | --- | --- |
| **P1a** `[cycle] release=` **median** | 2.325 -> **1.680 s** = **-0.645 s (77 ticks)** | 2.320 -> **1.680 s** = **-0.640 s (77 ticks)** | **PASS** both (band -0.633 +- 0.03) |
| P1a per arm | left -0.640, right -0.640 | left -0.635, right -0.615 | all four inside the band |
| **P2** pooled interval | 10.77 -> **10.59 s** | 19.34 -> **11.08 s** | **PASS** both |
| P2 per arm | left 19.64 -> 19.30, right 26.52 -> 26.02 | left 31.76 -> 24.38, right 50.30 -> 18.26 | down on **4/4** |
| **P3** landing | 16/16 payload-present `on_belt` | 12/12 | **PASS** (28/28) |
| **P4** ledger | no new key | no new key | **PASS**, `force_min==0` 4 -> 4 / 11 -> 7 |
| **P5** (report only) | 16/20 -> 16/20; window 5.57 -> 5.66; batch 4.96 -> 5.05; wall 328.4 -> 325.4 s; **placed/min wall 2.92 -> 2.95** | 10/20 -> 12/20; 3.10 -> 5.41; 3.11 -> 3.94; 308.2 -> 306.3 s; **1.95 -> 2.35** | one draw, never gated |
| **P6** descent budgets | **0/20 legs over** (worst 0.111) | **1/20 over** - leg 12, 5.9 cm, **0.164 vs 0.160** (lurch 0.036 of 0.291) | **FAIL the clean-pass form** |

**The mechanism is exact and branch-free.** The median falls by 77 ticks in
**all four arm-seed cells** against the arithmetic's 76, and the attempt-span
residual (the report line, not a clause) is `+0.16 / -0.03 s` - the acquisition
re-draw P86 §3 measured, which is why a per-seed span is not a gate here.

**The delivered side follows where the supply has stock.** Seed 5 is the clean
read: the count (16/20) and the whole arm split (9/10 + 7/10) are identical, so
its -0.18 s pooled interval is the lever's own. Seed 6's -8.26 s also carries a
+2 count draw (`interval = attempts/placement x span + idle`), so it is quoted
with that caveat.

**P6 is the one clause that misses, and it misses the way P86 predicted.** The
40-attempt treatment sample (T5 + T6) contains **exactly one** over-budget
descent - **seed 6's leg 12**, 2.5 % over - which is **the same leg P86's R6
recorded**. That answers P86's open question as far as two seeds can: the
excursion is a **deterministic property of that seed's branch**, not one draw's
accident (seed 5's worst leg is 0.111, half the budget) and not a systematic cost
of the trim (the descent profile is untouched and the fingerprint carries each
leg's duration, which is why the treatment is its own attractor). Per PREREG §5
this is the pre-registered **CONSIDERED TRADE** tier: the flip ships with the
excursion named as the branch's cost. **The budget was not re-tuned** (AGENTS §2)
and the named next spend is a third seed if the owner wants it priced further.

## 4. The scope's inertness (G2, both halves PASS)

**(a) The single arm, end to end.** `FRUIT_BIARM=0 scripts/accept.sh` (ten
attempts) reads **`fingerprint: matches` `configs/motion_reference_single.json`**
and its **raw `[fruit]` stream is 346/346 byte-identical to
`logs/p71/accept_rails_none.log`** - with **0** release-profile rows in it (the
row prints only in a bimanual session). The run's exit=1 is the standing
`6/9 < 0.75` rate clause this tree has carried since P32/P71 (`logs/p71`,
`logs/p76`, `logs/p77`), not a P87 effect.

**(b) The shared station.** `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`, 4 attempts,
unset vs `FRUIT_SPEED_RELEASE=0`: identical on **all 218 other `[fruit]` lines**,
and both resolve `dwell=20 pad_hold=3 finger_hold=3 (188 ticks)`.

**Recorded deviation A1 from PREREG G2b's letter.** The clause said "byte-identical,
whole `[fruit]` stream". The two runs differ on **exactly one line**: the new
row's `origin` field (`=0(scope-off)` vs `=0(explicit)`) - which is what the
label exists for (P43's `defaulted` convention: it records *how* the value was
decided). The substantive claim is therefore stated as: **identical on every
other line, and the same clock** - both asserted by `p87_report.py --same` and
`--profile`, and the raw diff is kept in `shared_raw_same.txt`. Nothing else in
the pair moved.

**(c) The paths pinned structurally** (no run, no path): the hybrid canary
(`60_eval_policy.py` builds its own `PickAndPlaceTask`, never a `CoopSession`) and
the direct env (`two_line=False` on its manifest) cannot satisfy
`two_line_enabled()`, so the resolver returns the shipped clock there; the
`247` leg pins the table. The collector's `mode=single` shard is the same scope
(`TWO_LINE` false).

## 5. The gate's motion guards (G1)

| cell | `190` against | result |
| --- | --- | --- |
| C5 | `logs/p80/motion_reference_twoline_p80_20.json` | **PASS** |
| C6 | `logs/p86/motion_reference_twoline_C6_20.json` | **PASS** |
| T5 | the seed-5 reference | DIFFERS by construction - budgets only |
| T6 | the seed-6 reference | DIFFERS by construction - budgets only |

A release-profile change re-times every attempt boundary and the fingerprint
carries each leg's duration (P44 §6), so a treatment cell is its own attractor by
design; `105 --min-success-rate 0.0` on T5/T6 is clean apart from T6's one leg.

## 6. Provenance before any recollection (G5)

`scene._release_provenance` (pure, no simulator) writes into the `physics` block
both manifest writers already share:

```json
"release": {"dwell": 0, "pad_hold": 2, "finger_hold": 2, "ticks": 112,
            "shipped_ticks": 188, "saved_ticks": 76, "profile": "trim",
            "origin": "default", "two_line": true, "label": "FRUIT_SPEED_RELEASE=1(default)"}
```

The collector passes its own `TWO_LINE` and the direct env `False`, so a shard
says which clock it ran. **A manifest without the key predates P87** (the
`arm_park.defaulted` convention). The trim moves the attempt timing without
moving one trajectory endpoint, which is exactly the class P41's `physics` and
P72's `scene` blocks exist for; park/trim mixing is not allowed either.

## 7. What shipped, and the re-baseline

**Shipped:** `FRUIT_SPEED_RELEASE` resolves on for a two-line session (it already
is the default in the tree); the `physics.release` block; the `247` selfcheck leg;
`scripts/225`'s scoped-call census; `scripts/234` pins the reference *arrangement*
instead of one phase's hash.

**References, two-line side only, from this batch:**
`configs/motion_reference.json` **`eb697f23` -> `423896f7`** and
`configs/motion_reference_twoline.json` **`eb697f23` -> `423896f7`** (both from
`logs/p87/accept10.log`, a 10-attempt run whose motion budgets are clean; the
acceptance re-run on the final tree is **byte-identical** to it and reads
**7/10 = 70 %, 9.4 s/attempt, `fingerprint: matches`, `190: PASS`**). Pre-P87
archives: `logs/p87/motion_reference_pre_p87.json` and
`logs/p87/motion_reference_twoline_pre_p87.json`.
**`configs/motion_reference_single.json` `8952c320` is untouched** - the
single-arm record is the inertness proof and did not move.

**Re-baseline: every two-line rate, span or interval recorded before P87 is a
2.35 s-release number; `FRUIT_SPEED_RELEASE=0` restores it.** Compose with the
older restores as usual (`FRUIT_ARM_PARK=ready` for pre-P43,
`FRUIT_POLICY_TRIGGER_ACQ=0` for pre-P54, and the P58 burst profile for the
**direct** interface, which this flip never reaches).

**Not measured, named:** a third budget seed; a two-line **collection** shard
under the trim (the collector inherits it and would record `physics.release`);
the hybrid canary (out of reach - it never builds a `CoopSession`, so it has no
path); a saturated machine.

## 8. Pins and evidence

`tasks.py` **`6b267ecc`**, `scene.py` **`047d9e7b`**, `rl_env.py` **`96076c8b`**
(metadata-only `TASKS_MD5` follow), `scripts/40_collect_demos.py` **`77e0331f`**,
`scripts/247_p87_release_scope_selftest.py` **`a4aa4756`**, `scripts/225`
**`395d3cd3`**, `scripts/234` **`ec1118be`**, `scripts/selfcheck.sh`
**`b4bf53b4`**; `configs/motion_reference.json` **`423896f7`**,
`..._twoline.json` **`423896f7`**, `..._single.json` **`8952c320`**; checkpoint
`moe_v13s` `61da390a`. `scripts/189_w7a_chain.sh` was **not** run. (The
battery's `header.txt` records `rl_env.py` `b5b31919`, the **pre-follow** pin: the
`TASKS_MD5` follow to `6b267ecc` landed after the four cells and before the
acceptance runs. `TASKS_MD5` is read only by `SortingRLEnv`'s own guard - the
scripted line never reads it - so the battery is unaffected; the shipped file is
`96076c8b`.)

Evidence: `logs/p87/{PREREG.md,PREREG.md5,RESULTS.md,p87_report.py,p87_report.txt,
run_p87.sh,run_p87_extra.sh,gates.sh,gates.out,header.txt,smoke.log}`,
`{C5,T5,C6,T6}.{log,stamps,driver,gate,budgets}`, `single_accept.{log,gate,same}`,
`shared_{unset,zero}.{log,stamps,driver}`, `shared_raw_same.txt`,
`accept10.{log,gate,stamps,driver}`, `accept_final.{log,gate,out}`,
`selfcheck_archive.log`, `motion_reference_pre_p87.json`,
`motion_reference_twoline_pre_p87.json`.

Report script `logs/p87/p87_report.py`: **`44bb70ad` at the runs**, `1d85bb13`
at the close-out - the edits are the `--profile` mode (the shared-station pair's
clock/`origin` split, deviation A1) and `descent_legs` moving P6 onto `105`'s own
parser and per-leg budget instead of a hard-coded 0.161; every endpoint above
comes from `cell()`/`blocks()`, whose `p80lib` reads and `[cycle]` pairing are
unchanged.

**Verdicts are quoted at the tree they were measured on.** Every run in this
phase finished by **17:19:56** with `tasks.py` = **`6b267ecc`** (the file this
commit ships); the tree has since moved (the next phase edits `tasks.py` /
`scene.py`), so
* `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** - re-verified on an
  **archive of the committed P87 tree** (`git archive 5de9b51`, with
  `checkpoints/` and `datasets/` linked in; `selfcheck.log` there);
* `scripts/106_index_audit.py` **OK** and `scripts/107_collect_merge_test.py`
  **PASS (21 checks)** on the same archive;
* `scripts/accept.sh` on the final tree (**17:19**) reads **7/10 = 70 %,
  9.4 s/attempt, `fingerprint: matches`, `190: PASS`**, and that log still gates
  `190: PASS` against `configs/motion_reference.json` on the archive.

A stale `rl_env.TASKS_MD5` on the *working* tree afterwards is the next phase's
metadata follow (the repo's standard `tasks.py`-pin follow), not a P87 result.
