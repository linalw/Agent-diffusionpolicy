# P87 - the release trim as a **two-line-scoped shipped default**

**Status: pinned before any run** (md5 in `logs/p87/PREREG.md5`). This phase **may
change a shipped default**: it ships P86's measured-positive release trim
**scoped to the two-line session**, and it must prove the scope with byte
identity on every other path. If a clause below fails, nothing flips.

Parent: `logs/p86/RESULTS.md` (+ `§9`'s adoption plan) and `logs/p86/PREREG.md`.
Throughput read rules: `docs/THROUGHPUT.md`, P80/P83/P84/P86. Inertness rules:
AGENTS §2 (`§3b`'s byte-identity convention, P85's own flip proof).

## 0. Tree (before the change)

HEAD `bd99237` with P86's docs uncommitted (`AGENTS.md`, `WORKLOG.md`,
`docs/THROUGHPUT.md`; +197 lines, no `src/` change). Pins before the P87 edit:
`tasks.py` **`f07a865a`**, `bimanual.py` `9b7fc33f`, `fruits.py` `dcabe16b`,
`scene.py` `07d6fdad`, `control.py` `9384ff4f`, `conveyor.py` `fb2c58c6`,
`assets.py` `540406fa`, `rl_env.py` `4d042cbe`;
`configs/motion_reference.json` **`eb697f23`**, `..._single.json`
**`8952c320`**, `..._twoline.json` **`eb697f23`**.

## 1. What changes, and what must not

The **only** behaviour change is the release clock's default, and only inside a
two-line session:

| path | `FRUIT_SPEED_RELEASE` unset resolves | holds |
| --- | --- | --- |
| two-line session (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, shipped) | **on** (`origin=default`) | 0 / 2 / 2 |
| single arm (`FRUIT_BIARM=0`), shared station (`FRUIT_BIARM_TWOLINE=0`) | off (`origin=scope-off`) | 20 / 3 / 3 |
| hybrid canary (`60_eval_policy.py`), direct/policy (`SortingRLEnv`), collector `mode=single` | off (`origin=scope-off`) | 20 / 3 / 3 |

Overrides: `FRUIT_SPEED_RELEASE=0` restores on the two-line too; an explicit
`=1` (or `FRUIT_SPEED_ALL=1`, the S13 union) still wins **globally**.
`FRUIT_SPEED_RELEASE_SETTLE` still moves the settle and is read only when the
cell is on. The scope is `Task.two_line_enabled()` — `session.twoline`, i.e.
False outside a `CoopSession` — so it cannot leak into a path that has no
session. One resolver (`tasks.release_speed_resolution`) feeds the per-attempt
holds, the new `[biarm] release profile:` row and the store manifest's
`physics.release` block.

## 2. The arms and the cells

| cell | seed | env | role |
| --- | --- | --- | --- |
| **C5** | 5 | `ATTEMPTS=20 FRUIT_SPEED_RELEASE=0` | the shipped clock (the control) |
| **T5** | 5 | `ATTEMPTS=20` (unset = scoped default) | the treatment |
| **C6** | 6 | `ATTEMPTS=20 FRUIT_SPEED_RELEASE=0` | control |
| **T6** | 6 | `ATTEMPTS=20` (unset) | treatment |

Every cell carries the **same instrumentation as P86's four cells**
(`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_PLACE_TRACE=1`), wall-stamped through `logs/p80/stamp.py` /
`logs/p80/one_run.sh`, one claim per run (`scripts/154_claim_run.sh`,
`RUN_LIMIT=2400`). Identical instrumentation is what makes G0 (below) possible
and keeps the contrast inside one instrumented batch (AGENTS §3b).

The **budget run** the adoption plan owes (`RESULTS.md` §9 item 4) is `T5`+`T6`
themselves: **2 seeds x 20 attempts = 40 attempts on the scoped default**, with
`FRUIT_MOTION_REPORT=1` printing every descent leg's `|v|max` and lurch. No
extra cells.

## 3. Endpoints

* **P1a - the mechanism (branch-free, the only gated mechanism clause).** The
  `[cycle] release=` block, **median** over the attempts that carry one, falls
  by **-0.633 s (the profile arithmetic: 20 + 40 + 16 = 76 ticks)** within
  **+-0.03 s**, at **both** seeds, and in **all four** arm-seed cells. Median,
  not mean: P86 measured the mean contaminated by one 1.63 s control leg and one
  1.92 s treatment leg (both `place low` descents inside the block) while the
  median was exact (-0.645 pooled). The attempt **span** is a **report**, never
  a clause: P86 measured it is *not* branch-free (P86 §3, the acquisition blocks
  re-draw with the shifted attempt boundary; residual sign-flips +0.17 / -0.12).
* **P2 - the delivered side.** The pooled inter-placement interval falls at
  **both** seeds; the per-arm intervals, `s/attempt`, both denominators and the
  wall column are reported.
* **P3 - the landing guard.** From `FRUIT_PLACE_TRACE`, **every** trace whose
  payload was present at the release (`release_bottom >= 0`; an upstream-lost
  payload reads -184 mm) must read `on_belt=True`, and its release height /
  impact / bounce must stay inside the control's band.
* **P4 - the failure ledger.** A treatment cell's reason **keys** (`113`'s
  parser via `p80lib`) must be a **subset** of its same-seed control's. The
  class split and the `[carry]` `force_min == 0.00` count are reported.
* **P5 - the rate, reported, never gated.** `placed`, both denominators
  (`window` and `batch`) and **`placed/min wall`** (P83's rule: never
  `wall/pick` alone). A count is a branch draw (P84's own control swung 16 -> 10
  between seeds).
* **P6 - the motion budgets.** `scripts/105_motion_regression.py
  --min-success-rate 0.0` per cell: every descent leg's `|v|max` against the
  shipped **0.160/0.161** budget and the lurch bound **0.291**, reported **per
  seed** with the worst leg named.

## 4. Guards

* **G0 - the flip is resolution-only (hard).** The four cells must replay
  **P86's own four cells** on the `[fruit]` stream, dropping only the phase's
  instrumentation rows (`[fruit] [carry]`, `[biarm] scheduler:`,
  `[diag] carry-assist`, the park rows, `[task]   place trace`) **plus P87's new
  `[fruit] [biarm] release profile:` row** - which is the one row that *must*
  differ, because `T5`/`T6` read `FRUIT_SPEED_RELEASE=1(default)` where P86's
  `R5`/`R6` read `=1(explicit)`:
  `C5` -> `logs/p86/C5.log` **865/865**, `T5` -> `logs/p86/R5.log` **865/865**,
  `C6` -> `logs/p86/C6.log` **814/814**, `T6` -> `logs/p86/R6.log` **814/814**.
  That makes the scoped default **bit-for-bit the arm P86 measured** - the
  treatment cells *are* P86's treatment cells - so the whole P86 measurement
  transfers, including its budget read.
* **G1 - motion.** `190` on `C5` against
  `logs/p80/motion_reference_twoline_p80_20.json` (should PASS: the pre-flip
  clock on the seed-5 scenario) and on `C6` against
  `logs/p86/motion_reference_twoline_C6_20.json` (P86's seed-6 record;
  should PASS for the same reason). `T5`/`T6` are **recorded** against those
  references (DIFFERS by construction - a release-profile change re-times every
  attempt boundary and the fingerprint carries each leg's duration) and gated on
  budgets only.
* **G2 - inertness of every other path (hard).**
  (a) `FRUIT_BIARM=0 scripts/accept.sh` (ten attempts) must be **byte-identical
  on the raw `[fruit]` stream to `logs/p71/accept_rails_none.log` (346/346)** and
  read `fingerprint: matches` `configs/motion_reference_single.json`. This is
  the single arm end to end - the strongest form, since the new row is *not*
  printed there at all.
  (b) The **shared station** (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`, 4 attempts)
  with the env unset must be **byte-identical, whole `[fruit]` stream**, to the
  same run with `FRUIT_SPEED_RELEASE=0`, and both must print
  `release profile: FRUIT_SPEED_RELEASE=0(scope-off) ... dwell=20 pad_hold=3
  finger_hold=3`.
  (c) The **hybrid canary** and the **direct env** are pinned **structurally**
  (they never construct a `CoopSession`, so `two_line_enabled()` is False) plus
  the resolver table in `scripts/247_p87_release_scope_selftest.py` - the
  canary's own smoke is not re-run for a knob it cannot reach (P58's "no path"
  convention).
* **G3 - blast radius.** `configs/motion_reference_single.json` **untouched**;
  the two two-line-side references re-recorded **only after P1a-P6 pass**, from
  the same batch's accepted acceptance run.
* **G4 - `scripts/selfcheck.sh` PASS** (including the new `247` leg) at the end,
  plus `scripts/106_index_audit.py` and `scripts/107_collect_merge_test.py`.
* **G5 - provenance.** `physics.release={dwell, pad_hold, finger_hold, ticks,
  origin, profile, two_line}` in **both** manifest writers (the collector's
  shard, the direct env's rollout), built by one function; a manifest **without**
  the key predates P87.

## 5. The decision rule, stated before the runs

> **A clean pass = WIN** iff, at **both** seeds: **P1a** (the release block's
> median falls by -0.633 +- 0.03 s), **P2** (the pooled interval falls),
> **P3** (every payload present at the release lands on the belt), **P4** (no
> new failure-reason key), **P6** (no seed has a descent leg over the 0.160/0.161
> budget), **and** G0/G2 hold. Then the scope ships (it already is the default),
> the two-line-side references are re-recorded and the documents are re-baselined.
>
> **A considered trade = SHIP, documented** iff P1a/P2/P3/P4 and G0/G2 hold and
> **P6 shows exactly the one documented leg** - at most **one** over-budget
> descent in the 40-attempt treatment sample, at one seed, **<= 2.5 % over**
> (0.164 against 0.160), i.e. the P86 `R6` leg and nothing new. The flip then
> ships with the excursion named as the branch's cost in `AGENTS.md`, and P6 is
> reported as a **failed clean-pass clause**, not as a pass.
>
> **FAIL = do not flip** if **any** of: P1a misses its band at either seed, P2
> rises at either seed, P3/P4 are dirty, G0 or G2 breaks, or P6 shows **more
> than one** over-budget leg **or** any over-budget leg at the other seed.
> The knob stays opt-in (`FRUIT_SPEED_RELEASE=1`), the two-line default reverts
> to the shipped clock, and nothing is re-recorded.

Falsifiers, named in advance:
* **F1** the block does not fall by -0.633 +- 0.03 (median) -> the saving is not
  the profile arithmetic and the flip is not the arm P86 measured;
* **F2** a payload present at the release lands off the belt, or the release
  height/impact leaves the control's band -> the dwell is load-bearing;
* **F3** the pooled interval rises at either seed -> the span saving does not
  reach the delivered side;
* **F4** a new reason key appears -> the class cost is named and not adopted;
* **F5** the treatment cells do not replay P86's `R5`/`R6` -> the scope resolved
  to something other than the measured arm (a resolution defect, not a physics
  result), and **nothing** below is admissible;
* **F6** any non-two-line path moves (the single-arm acceptance or the
  shared-station pair) -> the scope leaked.

## 6. If a WIN: the adoption cost (spent only after the gate)

1. The default is already the shipped resolution; no further `src/` change.
2. **Re-record the two-line-side references from the same batch**:
   `configs/motion_reference.json` (the acceptance's two-line reference) and
   `configs/motion_reference_twoline.json`; archive both pre-flip under
   `logs/p87/`. **`configs/motion_reference_single.json` stays untouched** - the
   single-arm record is the inertness proof and does not move.
3. `AGENTS.md` (§1's supersede note + a P87 paragraph), `README.md`,
   `docs/THROUGHPUT.md` (the lever list + the read rules), `WORKLOG.md`, and the
   re-baseline sentence: **every two-line rate before P87 is a 2.35 s-release
   number; `FRUIT_SPEED_RELEASE=0` restores it.**
4. The remaining spends that are **not** taken here because no measurement asks
   for them: a third seed of the budget run (a follow-up if the owner wants the
   excursion priced further).

## 7. Scope and known limits

* One scenario (the shipped two-line: dense wave sheet + balanced A:B:C), two
  seeds, 20 attempts each - the cells P86 measured, replayed.
* The **count** is a draw and is never the claim; the mechanism is the block,
  the delivered claim is the interval, and the budget read is per leg.
* The 40-attempt treatment sample is two seeds of one configuration; P84's
  lesson (a seed is a scenario) means an over-budget leg is quoted **with its
  seed and its own numbers**, never as a rate.
* Nothing here measures a saturated machine, the collector's two-line shard, or
  the direct env under the trim.
