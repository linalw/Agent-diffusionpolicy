# P91 RESULTS — the take-off validation ramp (measured, **NOT shipped**)

The cell, the prediction and the decision rule were registered in
`logs/p91/PREREG.md` (md5 `922c0b93…`, pinned before any run) and the audit that
chose it is `logs/p91/AUDIT.md`. Battery: `logs/p91/run_p91.sh`, four 20-attempt
two-line cells (seed 5 C5/T5, seed 6 C6/T6), one claim per run, ~6 min/run
(`logs/p91/header.txt` pins the tree and the battery form). Readout:
`logs/p91/p91_report.py` → `logs/p91/p91_report.txt`.

**Verdict: NOT ADOPTED.** `PROBE_TWO_LINE_DEFAULT` is **False**, so unset
resolves the shipped 60-tick probe on every path and the tree is inert. Two
registered falsifiers fired: **F2** (the class worsens at both seeds, and the
delivered pinch drops below the P41 plateau on seed 6) and **F4** (the interval
rises at both seeds while the clean cycle falls exactly as the tick count prices
it). The *mechanism* passed: the 1:1 lever is confirmed to one tick.

## 1. What the audit left to test, and what the run found

| | registered | measured seed 5 | measured seed 6 |
| --- | --- | --- | --- |
| **P1b the clean probe** (the branch-free instance) | `−0.300 ± 0.02 s` | **1.75 → 1.44 s** = −0.31 s (**−37 ticks**) | **1.75 → 1.44 s** = −0.31 s (−37) |
| **P1a the block mean / median** | both `−0.30 ± 0.04` | 2.36 → **2.58** / 1.75 → **2.60** | 1.98 → **2.37** / 1.75 → **2.48** |
| **P2 the pooled interval** | `−0.4 ± 0.8` (flat expected) | 10.59 → **13.01 (+2.42)** | 11.08 → **12.20 (+1.12)** |
| **P5 the catch window** | residual +<= 1.0 mm, `end=` <= 25 mm, grasp >= 14/20 | 5.9 mm / 9.2 max 12.2 / **14/20** | 5.9 mm / 9.1 max 10.6 / 16/20 |
| **P7 the delivered pinch** | `force_min` median >= 9.0 N | 9.43 → 9.36 | 9.65 → **7.77 (FAIL)** |

**The lever is exact.** The clean grip block is a deterministic constant (§4 of
the audit: the probe's loop count plus a fixed 150-tick remainder), and it falls
by the probe's own 36 ticks — 210 → 173 ticks = **−0.31 s** at both seeds, one
tick off the registered −0.30. It also falls by −0.30 s in the *other* mode
(seed 6's cheap re-seat: 1.95 → 1.65). So `FRUIT_DYNAMIC_PROBE_TICKS` is a
**1:1** lever on the block, as the single-arm/two-line cross-check predicted
(190 vs 210 ticks at probes 40 vs 60).

**And the block still gets longer**, because the *mode mix* moves. The grip block
is bimodal at the shipped clock and the treatment puts far more attempts into the
tax modes:

| cell | clean (1 probe) | clean + cheap re-seat (+0.21) | one failed probe | the cap / an expensive re-seat |
| --- | --- | --- | --- | --- |
| C5 | **14** (1.72-1.79) | 0 | 2 (3.28) | 4 (3.99-4.12) |
| T5 | **4** (1.38-1.44) | 1 (1.64) | 8 (2.47-2.68) | 7 (3.31-3.52) |
| C6 | **12** (1.72-1.76) | 5 (1.95) | 1 (3.28) | 1 (3.90) |
| T6 | **4** (1.43-1.45) | 5 (1.65) | 5 (2.48-2.68) | 6 (3.30-3.52) |

First-probe success **14/20 → 5/20** (seed 5) and **18/20 → 9/20** (seed 6).

## 2. The mechanism of the failure — the ramp's duration *is* the detection margin

The probe is a **validation** lift, not transport: 6 mm up along the tool axis,
and the grasp test that follows is a displacement threshold
(`fruit_z − z_before > 4 mm`, `tasks.py:13059`). At 60 ticks the payload is
carried 6 mm at 0.1 mm/tick with **2 mm of slack** over the 4 mm bar; at 24 ticks
the pads drive 0.25 mm/tick and the payload must reach 4 mm within the same 24
ticks of drag — the margin narrows by the same 2.5x, and on half the presented
fruit it is gone. That is why the clean mode gets *shorter* while the block gets
*longer*: the saving is 0.30 s per success, and a failure costs **+0.21 to
+2.1 s**.

The *class* moves with it, at both seeds and in the direction the registered
falsifier named:

* `never-grasped` **4 → 6** (seed 5) and **1 → 4** (seed 6);
* a new `carried-not-placed` bucket at seed 5 (**0 → 3**);
* the loaded-slide guard (`force_min == 0.00 N` carry legs) **4 → 9** and
  **7 → 11**;
* the **delivered pinch** — the number P41 fixed at the 9.7-9.9 N plateau —
  reads `force_min` median **9.43 → 9.36 N** (seed 5) but **9.65 → 7.77 N**
  (seed 6), with 10/18 held legs under the 9.0 N floor against 8/19. The
  force servo converges *inside* the probe
  (`FRUIT_DYNAMIC_TAKEOFF_SQUEEZE_S = 0.10` = 12 ticks of the probe's own
  ticks), so a shorter ramp is also a shorter squeeze: **the ramp's duration is
  coupled to the force that the carry inherits**.

## 3. The delivered side — F4, the fourth register of the same lesson

| | C5 | T5 | C6 | T6 |
| --- | --- | --- | --- | --- |
| placed | 16/20 | **11/20** | 12/20 | 12/20 |
| interval (pooled) | 10.59 | **13.01** | 11.08 | **12.20** |
| window placed/min | 5.66 | 4.61 | 5.41 | 4.92 |
| batch placed/min | 5.05 | 3.93 | 3.94 | 3.90 |
| `placed/min wall` | 2.95 | 2.32 | 2.34 | 2.33 |
| wall (s) | 325.7 | 284.1 | 307.7 | 309.6 |

The interval **rises at both seeds** while the clean cycle falls by the predicted
0.31 s. The arithmetic is the register's: the interval is
`attempts/placement × span + idle`, and at seed 5 `attempts/placement` goes
1.25 → 1.82 (16 → 11 placed) with idle 18.7/22.0 % → 22.5/17.2 %. This is
P88/P89/the speed union/the fail-fast for the fourth time: **a block delta of
0.30 s is not deliverable on this cell**, because the acquisition re-draws at
those ticks and the count is a branch.

The attempt span is quoted from the cycle's own `total`, never from the driver's
window pairing: in `T5` that pairing slips on 6 adjacent rows (the arms'
attempts completed out of print order, |`total − window`| up to 6.79 s, the arm
labels swapping in pairs) while the other three cells are clean (worst 0.08-0.09
s). A **recorded report deviation**, not a physics effect — and the reason the
span column is read from the instrumentation.

## 4. The guards that passed (they are what makes the negative readable)

* **P3 the landing** — every payload present at the release lands on the belt:
  **16/16, 11/11, 12/12, 12/12** `on_belt`, `release_bottom` 36.8-77.1 mm,
  impact −0.08..−0.93 m/s, bounce <= 5.8 mm. The trim is not a release defect.
* **P5 the catch window** (the descent's own guard) — the `dynamic catch-up`
  residual median is **5.9 mm in all four cells**, the `[motion] approach end=`
  median 8.9-9.2 mm with max 10.6-12.7 mm (the bar is 25), and the grasp rate
  16/14/19/16 with the 14/20 bar met at both seeds. The two 251/481 mm residuals
  are the standing acquisition tail present in **both** arms (P47/P48's class).
* **P6 the motion budgets** — all descents inside `105`'s per-leg budget in all
  four cells; nothing re-tuned (`gates.sh`).
* **P8 the inertness — all three halves pass** (`logs/p91/gates.sh`, exit 0):
  * **G0** the two controls replay the **shipped cell's** record byte for byte —
    `C5` = `logs/p87/T5.log` **868/868** and `C6` = `logs/p87/T6.log`
    **821/821** on the `[fruit]` stream with only the phase's own rows dropped,
    and the same against `logs/p88/C5.log` and `logs/p89/C6.log` (all three
    pre-P91 records of the shipped cell are identical to each other);
  * **the single arm** is **raw 346/346** identical to
    `logs/p71/accept_rails_none.log` with `fingerprint: matches
    configs/motion_reference_single.json`, and **no take-off row printed**
    (0 occurrences of all four profile rows);
  * **the shared station is not a two-line session**: unset resolves
    `FRUIT_DYNAMIC_PROBE_TICKS=40(single)` — the shipped single-arm probe, never
    the cell — and is sealed-identical to an explicit `=40` (the raw difference
    is the row's `origin` field only); the `=60` arm is the diagnostic that the
    env still wins over the scope;
  * **the final tree's default is the shipped clock**: `N5` (unset, 20 attempts,
    after the revert) replays `logs/p87/T5.log` **and** `C5` identically.
* **P9 the provenance** — `physics.takeoff` in both manifest writers, the
  `[biarm] take-off profile:` row naming the resolution, the `250` selfcheck leg.

**PREREG A1 (report deviation).** P8's clause named `logs/p89/T5.log` as the
"pre-change record". That file is P89's **lift-raise** arm (its battery ran
`LIFT_TWO_LINE_DEFAULT = True`), so the clause named the wrong file — P89's own
G0 compares against P88's **C** cells for exactly this reason. The target used is
`logs/p87/T5.log`, the record of the shipped cell, and the three pre-P91
equivalents (`p87/T5`, `p88/C5`, `p89/C5`) are byte-identical to each other and
to `C5`, so the substance is unchanged. A second, smaller deviation: the raw
shared-station pair cannot be IDENTICAL (the new row's `origin` field differs by
construction), so the gate asserts the raw difference is **only** that row.<br>
**The `190` fingerprints DIFFER on all four cells**, against the P80/P86
20-attempt references: they are pre-P87-clock records, the registered
"recorded, not gated" read (P87/P88/P89's own gates read the same way, and
`C5`'s `190` output is line-for-line identical to
`logs/p88/C5.gate`).

## 5. What this phase actually delivered

1. **The audit** (`logs/p91/AUDIT.md`), which is the phase's real product: the
   five never-profiled blocks were **8.82 s = 57 %** of the span, and their
   decomposition is **4.09 s of wait, 0.76 s of failure tax, 3.63 s of arm
   motion** — of which the descent's 0.74 s is **schedule-invariant** (the block
   equals `lead/speed − margin`, so a faster leg just waits longer) and the
   hover's 0.58 s has **no profile** (an IK step cap). **The genuinely speedable
   pool is 1.08 s = 7.0 % of the 15.34 s**, spread over five blocks, and the
   largest single item is the 60-tick probe ramp — 0.50 s, of which this
   experiment delivers 0.31 s on a clean attempt and *gives back* 0.21-2.1 s on
   each of the attempts whose validation now fails.
2. **The measurement** that the ramp cannot be trimmed: its duration is the
   detection margin *and* the force servo's squeeze window. That closes the
   take-off family the way P41/P42/P75 closed the contact family — and it is a
   *different* reason from the ones above it (schedule invariance for the
   descent, a contested direction for the close, no profile for the hover).
3. **The machinery**, default off: `probe_ticks_resolution` (the fourth
   two-line-scoped resolver), the `[biarm] take-off profile:` row,
   `physics.takeoff` provenance, and the `250` selfcheck leg. The measured arm is
   reproducible as `FRUIT_DYNAMIC_PROBE_TICKS=24`; the re-entry is one literal.

## 6. What is NOT claimed

* **The mode-mix change is not attributed.** The treatment's `descent` block is
  0.6-0.8 s shorter (3.64 → 3.01 / 2.80 s), i.e. the selection cadence — hence
  the presented fruit — differs, so "the shorter ramp failed the validation more
  often" and "the re-timed presentation drew harder fruit" are **not separated at
  this N**. The verdict does not need the separation: **P2, P4 and P7 fail on the
  delivered side on their own** (the interval rises at both seeds, the class
  worsens at both, the pinch falls below its own floor at seed 6).
* **No rate.** 20 attempts per arm is one draw; the counts are branch draws and
  are quoted as such. The branch-free numbers are the **clean-mode tick count**
  (210 → 173) and the per-leg pinch/loaded-slide reads.
* **No reference was re-recorded and none is owed.** The flip was not shipped;
  `configs/motion_reference{,_single,_twoline}.json` are untouched at
  `423896f7` / `8952c320` / `423896f7`.

## 7. The shipped tree after the phase

The gate failed, so nothing was flipped and the tree is the pre-P91 one plus a
default-off resolver. On the final tree:

* `scripts/accept.sh` (the shipped two-line scenario, ten attempts) reads
  **7/10 = 70 %, 9.4 s/attempt, `fingerprint: matches configs/motion_reference.json`,
  `190: PASS`** — the standing branch P87/P88/P89 recorded, unchanged
  (`logs/p91/accept_final.log`).
* `scripts/selfcheck.sh` is **PASS, 0 failures** with the new
  **`P91 probe scope`** leg (`logs/selfcheck.log`).
* `logs/p91/gates.sh` exits **0**: G0 (the controls replay the shipped cell
  868/868 and 821/821), the single arm **346/346 raw** + `fingerprint: matches`,
  the shared-station pair (unset = 40, the shipped single-arm probe; raw differs
  only on the row's `origin`), and `N5` (the final tree, unset) replaying
  `logs/p87/T5.log` and `C5`.
* **No reference was re-recorded** and none is owed: `configs/motion_reference.json`
  `423896f7`, `..._single.json` `8952c320`, `..._twoline.json` `423896f7` — all
  three untouched.

**The re-baseline rule this phase adds: none.** Nothing shipped; the only new
knob is default-off (`PROBE_TWO_LINE_DEFAULT = False`) and the only new printed
row is inside a bimanual session.
