# P36 phase 1 — the proprio spoof and the 2x2's implementation (the record)

Measured 2026-10-24. **Default off, no shipped default changed**; the phase's
files are uncommitted. The pre-registration is `logs/p36/PREREG.md` (written
before any 2x2 A/B). Tree pins after the phase
(`logs/p36/P1_tree_md5.txt`): `rl_env.py` **d6741d86**, `tasks.py` cdde6bd2
(unchanged), `configs/arm_parks.json` 42ab4fb7 (unchanged),
`configs/proprio_spoof.json` **374b88a7**, `scripts/218_proprio_spoof_check.py`
8ddbfdec, `scripts/219_p36_cells.sh` a21fa149, `scripts/220_p36_report.py`
3d9e9784, `logs/p36/smoke_check.py` 2591cc65, `scripts/selfcheck.sh` c5285288;
checkpoint `moe_v13s` `61da390a`.

## 1. The implementation

**`FRUIT_PROPRIO_SPOOF=<pose>`** (`src/fruit_sorting/rl_env.py`, direct
presentation only): when set, `proprio()` writes the **inactive** arm's 7 joint
values into the observation's joint block from `configs/proprio_spoof.json`
before the 25-D vector is assembled.

* **The indices** are the arm's own `ArmController.arm_dofs`, not an assumption:
  the robot's measured dof order is interleaved
  (`logs/33_dof.log`: `openarm_left_joint1, openarm_right_joint1, ...`), so
  **left = 0,2,4,6,8,10,12** and **right = 1,3,5,7,9,11,13**. The active arm, the
  four finger joints (14,15,17,18), the two hand joints (16,19) and the two TCP
  joints (20,21) are copied untouched.
* **The override** is the pure module-level `apply_proprio_spoof(dof, active,
  indices, vectors)`: it copies the joint row, writes one side's 7 values and
  returns `{"applied", "side", "indices", "before"}`. It never touches the
  simulation and never mutates its input. A side with no vector for the pose is
  left live and reported `applied=0` - `back` has **no right-arm vector**
  (`configs/arm_parks.json` has no right park: the P35 lever is left-only by
  measurement), so a left-active episode is a no-op in this channel and is the
  2x2's within-batch negative control.
* **The source of the vectors** is measured, not commanded:
  `configs/proprio_spoof.json` holds the `q_settled=` field of the P35 `[park]`
  rows - the pose the reset *achieved* (`teleport_joints` re-bases onto the
  measured state, so `back`'s command is 0.088 rad away, the shipped `ready`'s
  0.037). Each value string repeats identically across its whole population in
  `logs/p35/C_ab/` (left at ready n=51, left at back n=50, right at ready
  n=24), i.e. the reset settle is deterministic on the tree that batch pinned -
  the same tree as this one.
* **The diag** `FRUIT_SPOOF_DIAG=1` prints one `[spoof]` row per episode: the
  pose, `applied`, the side, the 7 indices, the live and written values, the md5
  of the assembled proprio **before/after**, the md5 of the same vector with the
  7 indices **zeroed** (`rest_same`=1 iff only those 7 changed), the call count
  and `drift = max|live - written|` over the episode. Pure reporting over the
  array `proprio()` already built; no extra sensor or articulation read.
* **Provenance**: the run manifest gains a `proprio_spoof` block beside the P35
  `arm_park` block (absent = off), and `configs/proprio_spoof.json` is pinned in
  `_MANIFEST_SOURCES` - a spoof run is identifiable from its npz manifest alone.
* **The image channel** is the existing `FRUIT_ARM_PARK=<name>` (P35), verified
  in this phase by the smoke's `[park]` M1/M2 rows: the park still moves the arm
  and still removes the band occlusion, and the proprio spoof does not touch it.

**Inertness (the shipped path).** With both knobs unset: `_spoof_vectors` is
empty, so `proprio()` runs one empty-dict test and never calls the helper (no
copy, no write); the diag is off, so nothing is hashed or printed; the assembled
25-D vector is byte-identical. `FRUIT_ARM_PARK` and the P35 diag are untouched.
The scripted line does not construct this env at all - its byte-identity is the
no-harm run below.

## 2. The offline check (`scripts/218_proprio_spoof_check.py`)

`logs/p36/offline_obs_diff.txt`, **failures=0 skipped=0**; `--self-test` ok (a
0.01 rad perturbation and a wrong index set are both detected). It asserts
against measured artefacts, not transcriptions:

| check | result |
| --- | --- |
| the three vectors == the P35 `q_settled` rows | yes (n=1 distinct value per pose) |
| the layout == `logs/33_dof.log`'s dof order | left `0,2,4,6,8,10,12`, right `1,3,5,7,9,11,13`, disjoint |
| one call changes **exactly** the inactive arm's 7 | 7 **written**, 6 read as changed (j7 = 1.559 in both poses), the other **15 bit-identical** |
| the caller's array is not mutated | md5 unchanged |
| the assembled 25-D: only the 7 joints move | the finger channel and both tactile channels unchanged; the hash with the 7 zeroed is equal before/after |
| the other arm / no vector / off | the right's 7 written when it is the inactive side; `applied=0` and a bit-identical no-op where the pose has no vector and with an empty vector dict |
| the substitution is not a no-op | `ready -> back` `|dq| = [0.448, 0.603, 0.015, 0.497, 0.002, 0.002, 0.000]` rad, max 0.603, sum 1.567 |

It is a `scripts/selfcheck.sh` leg (`proprio spoof check`, 0.08 s).

## 3. The smoke — one episode per cell (`logs/p36/run_smoke.sh`)

Six one-episode runs at seed 77, one `154_claim_run.sh` claim (18:49-18:54, the
P35 C batch's scenario verbatim + all four diags on every cell), checked by
`logs/p36/smoke_check.py` -> **`logs/p36/P1_smoke.txt`, failures=0**. The four
cells plus two source-vector controls (`s1b` writes the ready vector onto a ready
arm, `s2b` the back vector onto a parked arm):

| run | the cell | arm | outcome | spoof | drift | park | arm_px | pre_md5 / obs_md5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s1 | ready / ready | right | carried | - | - | ready | 234 | 68e0e753 / 68e0e753 |
| s2 | park / park | right | ok | - | - | back | 0 | 98b0df03 / 98b0df03 |
| s3 | park / ready-proprio | right | ok | ready | +0.6035 | back | 0 | 98b0df03 / 8a814e9b |
| s4 | ready / park-proprio | right | no-grasp | back | +0.6036 | ready | 234 | 68e0e753 / ea53dff4 |
| s1b | ready / ready (written) | right | no-grasp | ready | **+0.0059** | ready | 234 | 68e0e753 / 2445ef92 |
| s2b | park / park (written) | right | ok | back | **+0.0141** | back | 0 | 98b0df03 / 391a4c52 |

* **S1**: the written values are the file's vectors exactly; the no-op cells'
  drift is **0.0059 rad** (ready) and **0.0141 rad** (back) - inside the
  pre-registered 0.02 rad bar, i.e. the file reproduces the physical cell's
  proprio to 1 %/2.3 % of the 0.603 rad ready->back shift; the probe cells'
  drift is 0.6035/0.6036, the substitution is real.
* **S2**: `rest_same=1` in all six cells.
* **S3**: the `[park]` M1 read holds each cell's pose (`m1_hold` 0.002 ready /
  0.004 back).
* **S4**: the inactive arm is in the target's disc bbox in the three *ready*
  cells (`arm_px` = 234, band frac 4.5) and absent in the three *parked* cells
  (`arm_px` = 0, frac 0.000) - the image follows the arm, never the spoof. This
  reproduces P35's A/B ep0 rows exactly (`q_settled` identical, `band_px`
  52 vs 184).
* **The cross-cell identity (the strongest part)**: the **pre-spoof proprio
  hash is bit-identical inside each physical pair** - cells 1 and 4 share
  `68e0e753`, cells 2 and 3 share `98b0df03`. So at the first call the two cells
  of a pair differ in **nothing but the 7 spoofed values** and the image; the
  reset, the arm, the fruit and the other 18 channels are the same state.
* **The outcome divergence is NOT a result**: the six single episodes already
  disagree (s1 carried, s4 no-grasp, s1b no-grasp - the last differing from s1
  by <= 0.006 rad in 7 channels). That is the documented non-reproducibility of
  the policy loop (AGENTS section 3b), and it is why the 2x2 needs 3 runs x 15
  per cell, not one episode. Nothing in this section is a rate.

## 4. No-harm

* **The scripted acceptance** (`scripts/accept.sh`, 10 attempts, one claim
  18:57-19:02): **`fingerprint: matches configs/motion_reference.json`**, 6/10,
  `diverted=0`, `gate_open=0.0 s`, and its **376 `[fruit]` lines are IDENTICAL**
  to the P35 record (`logs/p35/C_accept_no_harm.log`) -
  `logs/p36/P1_accept_stream.log`, `logs/p36/P1_accept_identity.txt`. The 6/10
  is the pre-existing P32 pear-on branch (rate-only FAIL against the 75 %
  dynamic floor, AGENTS section 1), so the driver's `exit=1` is expected.
* **`scripts/selfcheck.sh`**: **PASS, 0 failures, 1 skipped** (the motion-budget
  leg, which the acceptance above supplies); `logs/p36/P1_selfcheck.log`. The
  new `proprio spoof check` leg passes.
* The tree md5s are unchanged before/after the phase except the files listed in
  the header (`logs/p36/P1_tree_md5.txt`).

## 5. The phase-2 tooling (written, self-tested, not yet run)

* `scripts/219_p36_cells.sh` - the 4-cell interleaved driver with the rotated
  cell order (run i starts at cell i), the P35 scenario verbatim, all four diags
  on every cell, one claim, then the report. Run as
  `scripts/154_claim_run.sh logs/p36/A_driver.log scripts/219_p36_cells.sh`.
* `scripts/220_p36_report.py` - the pre-registered analysis (the cell table,
  Wilson intervals, the two exact Fisher main effects, the interaction with its
  within-stratum permutation, the effect fractions and bands, the
  class-standardised rates, the failure reasons, the cycle, the run-level signs,
  the decision matrix). `--self-test` ok: the image / proprio / both /
  conjunction / non-replication tables each produce their pre-registered reading,
  and the arithmetic (Wilson 0/30 = [0, 0.114]; Fisher saturated p < 1e-9) is
  pinned.

## 6. The risks, carried into phase 2

(a) Cells 3/4 are **OOD input pairs** - a positive names the channel and does
not ship; a null is weak evidence and, for the conjunction pattern, ambiguous
(PREREG section 8). (b) The spoof is a **constant** vector while the live arm
drifts <= 0.014 rad inside an episode, so the "same proprio" claim is a
<= 0.02 rad substitution, not an identity. (c) The probe cells' outcomes are
**new behaviour** from an input the checkpoint never saw; a new failure reason is
expected to be possible and is reported, not treated as a defect. (d) The
inference population is the **right-arm episodes** (~30 per cell at 45), so the
main-effect tables are ~60/60 - the power statement in the PREREG holds only for
a channel carrying >= ~72 % of the P35 conversion (80 % power). (e) The policy loop is not
reproducible run to run, so the two null probe cells can look flat for reasons
unrelated to the channel - the left-arm episodes (a no-op in all four cells)
are quoted as the batch's noise scale beside every right-arm number.
