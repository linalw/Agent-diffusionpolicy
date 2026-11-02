# P97 PREREG - the clearance pre-pose ships as a two-line invariant fix

**Pinned before any run of this phase.** The md5 of this file is written to
`logs/p97/PREREG.md5` immediately after it is frozen; no P97 run starts before
that file exists. Amendments (if a measurement forces one) go to
`logs/p97/PREREG_A<N>.md` with their own pin, never into this file.

---

## 0. The owner's decision, and what it is not

P96 built and measured the clearance pre-pose (`logs/p96/RESULTS.md`) and did not
ship it because its registered "no lost placement" clause failed by its letter at
seed 5. **The owner has decided: ship it as an invariant fix.** The argument is
P96 §0/P95 §2-§6, not the count:

* The shipped two-line pre-pose is the **calibrated grasp configuration** at the
  arm's own station: its pads end **29 mm below a fruit's top** (statically:
  the pad point is **46 mm below the tallest fruit's top** and the pose sits on
  the **j3 limit, +0.000 rad**), and the pre-pose blend dives there on **every**
  attempt. The stations are `left y=+0.000` (upstream) / `right y=-0.100` on a
  `-y` belt, so a **right**-arm fruit must cross the **left** station while the
  left hand does exactly that blend. P95 measured **1 pad contact in 40
  attempts** (the jaw span knocked 98.0 -> 59.8 mm and springing back, 21.6 rad/s
  of spin) and 5/19 right-arm attempts inside 6.4 mm. **A hand whose pads are
  inside another lane's fruit band is a defect regardless of its rate** - P94's
  precedent.
* P96's fix removes the geometry: both stations' pre-poses are solved at
  `belt_top + 0.165` with the arm's own **measured** calibrated attitude
  (`hold=calib`), achieving jaw **+0.160 left / +0.155 right** (pad points
  **+0.079 / +0.075**) at **+0.020 / +0.013 rad** of joint margin - better
  conditioned than the shipped pose's own `+0.000 @ j3`. The census goes
  **min 0.0 -> +5.9 mm, `<= 6 mm` 4/40 -> 1/40, contacts 1/40 -> 0/40**.
* **No rate is claimed.** P96's two-seed count is a draw: **29/40 -> 27/40**
  (seed 5 **-5**, seed 6 **+3**, per arm **-1 / -1**), and a 5-point count
  difference at this n cannot be measured (P93: 364 attempts/arm for 8.75
  points). The P97 report states the invariant and the draw; it does not convert
  one into the other.

## 1. What ships, and the resolution table

One shipped change: `tasks.PREPOSE_CLEAR_TWO_LINE_DEFAULT = False -> True`. The
resolver keeps P96's shape (one resolution, one `[biarm] pre-pose` row, three
collector manifest keys):

| `FRUIT_BIARM_PREPOSE_CLEAR` | two-line session | resolves |
| --- | --- | --- |
| unset / empty | yes | **on** (`default`) - the P96 measured arm |
| unset / empty | no | off (`scope-off`) - no two-line station exists |
| `0`/`off`/`false`/`no` | any | off (`explicit`) - the pre-P96 path, bit for bit |
| `1`/`on`/`true`/`yes` | any | **on** (`explicit`) |

The measured arm's parameters do **not** move: `FRUIT_BIARM_PREPOSE_CLEAR_Z`
default **0.165 m** above the belt top, band **`[0.155, 0.25]`** (a clearance
target below the invariant raises), `FRUIT_BIARM_PREPOSE_CLEAR_HOLD` default
**`calib`**. Nothing else moves: the descent, the hover, the close, the carry, the
place, the release clock, the feeder, the station selection and the pre-pose
blend's **45 + 20 ticks** are untouched.

## 2. The flip must be resolution-only - the three proofs, registered up front

* **G1 - the `=0` A/B.** `FRUIT_BIARM_PREPOSE_CLEAR=0 scripts/accept.sh` at the
  shipped 10 attempts must read **8/10** and
  **`fingerprint: matches configs/motion_reference.json` = `30fb99f8`**, and its
  **`[fruit]` stream must be byte-identical to `logs/p94/accept_final.log`**
  (419/419 physics lines). The print is gated inside `if clear["on"]:`, so the
  pre-P96 path adds no row.
* **G2 - the single arm.** `FRUIT_BIARM=0 scripts/accept.sh` must be **346/346
  raw** identical to `logs/p71/accept_rails_none.log` with
  **`fingerprint: matches configs/motion_reference_single.json`** - the pre-pose
  is two-line-only by construction (`prepose_clear_resolution(two_line)` is
  `scope-off` without a session).
* **G3 - the default is the measured arm.** The shipped default's 20-attempt
  seed-5 cell (the sanity cell below) must have its **`[fruit]` stream identical
  to P96's `T5.log`** (`FRUIT_BIARM_PREPOSE_CLEAR=1`, same seed, same
  instrumentation), with only the `[biarm] pre-pose` row's origin label
  (`default` vs `explicit`) differing. If this does not hold, the default is not
  P96's measured configuration and the package stops.

## 3. The re-record, and the archives

The default moves **every** two-line attempt, so both two-line-side references
are re-recorded **from same-batch runs of the new default**, at the attempt count
each is gated at (**10**, `scripts/accept.sh` / `scripts/190_twoline_gate.sh`):

* `configs/motion_reference.json` - the acceptance's reference - from the
  acceptance run of record.
* `configs/motion_reference_twoline.json` - from its own second 10-attempt run
  of the same scenario.
* `configs/motion_reference_single.json` (`8952c320`) is **untouched** - the
  single arm cannot reach the knob (G2).
* Pre-P97 archives: `logs/p97/motion_reference_pre_p97.json` and
  `logs/p97/motion_reference_twoline_pre_p97.json` (both `30fb99f8` today).

## 4. The gates

1. `scripts/190_twoline_gate.sh` on the new default's acceptance, against the
   re-recorded reference (10 attempts, floor 0.60).
2. `scripts/accept.sh` end to end **PASS** (selfcheck + the gate on the
   re-recorded reference).
3. `scripts/selfcheck.sh` **PASS**, with the `253` leg's resolver table reading
   the flipped default (`PREPOSE_CLEAR_TWO_LINE_DEFAULT is True`; unset +
   two-line -> on, origin `default`; `=0` -> off `explicit`; no session ->
   `scope-off`).
4. `scripts/211_bed_audit.py`, `scripts/106_index_audit.py`,
   `scripts/107_collect_merge_test.py`.

## 5. The sanity rate cell (report only)

One 20-attempt cell at **seed 5**, `FRUIT_BIARM_PREPOSE_CLEAR` **unset** (the
shipped default), with P96's census instrumentation
(`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_PLACE_TRACE=1 FRUIT_FRUIT_TRACE=2500 FRUIT_FRUIT_TRACE_ARM=1`). It is the
cell that carries the shipped tree's own **contact census** (0 contacts is the
endpoint) and reports placed, interval (both denominators + wall), landing and
the `[cycle]` blocks. It is **not** a rate claim and no gate reads its count.

## 6. Provenance, and the one QA question this phase answers

* `collection.prepose_clear` / `prepose_clear_defaulted` / `prepose_clear_z`
  already exist (P96). A **fresh shard** under the shipped default must read
  `1 / true / 0.165`; a store **without** the key predates P96 and is a
  pre-clearance-pre-pose number.
* The acceptance is a **scripted run, not a store** (`20_pick_place.py` writes no
  manifest), so its witness is the `[biarm] pre-pose` row: achieved jaw
  `belt_top + 0.160 / +0.155`, both stations `CLEARS`. The shipped scenario's
  shard manifest is exercised directly (`write_manifest` under the shipped
  config) so the collector keys are verified without a second simulator run.
* **The `scene` block does not gain a pre-pose field.** `assets.scene_provenance`
  is the scene's **collider set** (the rail pair, the output slab, the lift
  rung); the pre-pose is a control pose, and the collector's `collection` block
  is its one owner. Duplicating it into `scene` would create a second source of
  truth for the same fact - the exact drift P72/P93's "one builder, one owner"
  rule forbids. No field is invented.

## 7. The report

`logs/p97/{PREREG.md,PREREG.md5,RESULTS.md}`, the report script/table, the
acceptance cells, the sanity cell + census, the shard manifest probe, the gates,
and the re-baseline paragraphs in `AGENTS.md`, `README.md`,
`docs/THROUGHPUT.md`, `docs/LEFT_ARM.md`, `项目总结报告.md` and `WORKLOG.md`.
