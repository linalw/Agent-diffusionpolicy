# P61 phase 2 — pre-registration: the **direction** of the left arm's slip

Written **before any simulator run** of this phase (2026-10-29, ~10:40 CST; no
`logs/p61/p2/*.log` exists yet). The brief is
`.slim/deepwork/p61-slip-direction.md`; the context is P60
(`logs/p60/P3_RESULTS.md`, `logs/p60/LEFT_CENSUS.md`).

## 1. The question and why it is answerable now

P60 established that the direct left's carry loss is the **loaded slide**
(`seated_then_slid` 19/19, `force@onset` p50 10.06 N, `clean_slip` p50 171 mm,
never-seated 0/19) at **47x** the right's rate on the same hand — and could not
say *where the payload goes*, because `clean_slip_max` is a **norm**. The working
tree now prints `slip_xyz=(x,y,z)mm` on every `[carry]` row: the displacement at
the moment the running maximum is set, in the same leg frame the norm uses
(`rel_frame - guard_ref`; pinned by `scripts/231_p61_slip_selftest.py`). This
phase reads that field. **No `src/`, `configs/` or `scripts/` edit is made by this
phase; the instrument is already in the tree and is reporting-only.**

## 2. The cell (one claim per run, 3 seeds × 15 picks, the shipped profile)

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_MOTION_REPORT=1
HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1
scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
  --presentation direct --episodes 15 --seeds <77|101|202> --out logs/p61/p2/rollouts
```

Logs `logs/p61/p2/S_{77,101,202}.log`, driver `logs/p61/p2/run_p2.sh`, one claim
per run via `scripts/154_claim_run.sh` (`RUN_LIMIT=2700`).

Deliberately **not** set (the shipped `direct` defaults): `FRUIT_DIRECT_CONTINUOUS`
(P55/P56), `FRUIT_POLICY_TRIGGER_ACQ` (P54 resolves on for `direct`),
`FRUIT_ARM_PARK` (P43 resolves `back` for `direct`), `FRUIT_CARRY_GUARD`,
`FRUIT_CARRY_RELIEF`, `FRUIT_CARRY_MONITOR` (the diag must not actuate).

**The comparator is P60 phase 3's own cell** (`logs/p60/p3/D_{77,101,202}.log`):
the same scenario, the same checkpoint, the same tree except the `slip_xyz`
addition (`tasks.py` `8ad8ddc8` → the measured tree) — so F3 has a same-scenario
foot and the class counts are directly comparable.

## 3. The frame map (offline, computed **before** the run; the interpretation key)

`slip_xyz` is in the **TCP frame** at the tick of the maximum: `Rᵀ·v` with `R`
from `arm.tcp_pose()[1]` and the `(w,x,y,z)` convention (`tasks.py:213`). The two
calibrated grasp attitudes (`configs/waypoints_oriented.json`) are related by
`R_right = M·R_left·Mᵀ` with `M = diag(-1,+1,-1)` (a 180° rotation about the world
**y** = belt axis; max element error **0.0**). So each candidate world direction
maps to a **different, pre-computable** hand-frame signature:

| candidate (world) | L hand frame (x,y,z) | R hand frame (x,y,z) |
|---|---|---|
| **belt travel −y** (the drag) | ( +0.034, **+0.858**, +0.513) | ( −0.034, **+0.858**, −0.513) |
| **payload falls −z** (lift axis) | ( **−0.997**, −0.010, +0.082) | ( **−0.997**, +0.010, +0.082) |
| **payload rises +z** | ( **+0.997**, +0.010, −0.082) | ( **+0.997**, −0.010, −0.082) |
| **pried out ±x** (jaw axis) | ( ±0.075, ∓0.514, **±0.854**) | ( ±0.075, ±0.514, **±0.854**) |

(World axes: Z up, belt travel along **−Y**, "jaws close along **X**" —
`_carry_attitude`'s own docstring. Hand-frame axes are TCP columns: hand x ≈
world **+Z**, hand y ≈ world **−Y**, hand z ≈ world **+X**.)

**Decision table (registered):**

| observed | implies |
|---|---|
| left **y** dominant and **y > 0** (and the right, if it has escapes, the same **sign** in y) | **belt-directional** — the drag |
| **x** dominant, **negative** | **lift-directional** — the payload falls relative to the hand |
| **z** dominant, with **opposite** z signs between arms | **jaw-axis** — pried out of the pinch |
| runner-up ≥ 0.70 × the largest component | **mixed** (name the top two) |

Two consequences worth registering as independent checks:
(1) a **belt**-direction slip has a **z cross-term of ±0.513**, so the left's and
the right's z signs must be **opposite** under the same hypothesis — a mirror
signature the map predicts and no other candidate produces;
(2) a **lift**-direction slip is **y ≈ 0** (±0.010) — so a y-dominant read rules
the lift axis out, and vice versa.

**Limit of the map (registered).** The map is the **grasp attitude**; the
`grasp_lift` leg's tool attitude is not pinned during the carry (`tasks.py:8398`
clears `hold_quaternion`; the P39 L2 code fact). The achieved attitude is not
logged in this cell (that is `FRUIT_CARRY_ATTITUDE=1`, not in the env). The
attitude drift smears the components by up to the drift angle; the read is
therefore reported together with a **concentration check** (the mean pairwise
cosine of the escaping vectors within arm), and only the *separation the map
predicts* (0.858 vs 0.513 vs 0.997) is claimed, never a degrees-level direction.

## 4. Endpoints

**P1 — instrument validity.** On **every** `[carry]` row:
`|slip_xyz|` vs `clean_slip_max`, both as printed (0.1 mm).
*Operative rule (registered now, because the print rounds twice):* three
components rounded to 0.1 mm plus a norm rounded to 0.1 mm give an arithmetic
bound of `√3·0.05 + 0.05 = 0.137 mm`. So (a) the **letter** is
`discrepancy ≤ 0.1 mm` on every row; (b) a row in `(0.1, 0.15] mm` is a
**print-rounding** row, reported and **not** an F1 stop; (c) a row `> 0.15 mm`
**is** F1 → stop the analysis, quote the row, do not interpret. A leg that never
slips must print `(0.0,0.0,0.0)`, i.e. the same rule covers `clean_slip_max = 0`.

**P2 — the direction (primary).**
*Definitions (fixed now).* An **escaping leg** is a `[carry]` row with
`clean_slip_max > 50 mm` (the brief's threshold, the W8-B escape band). A
**transient leg** is `5 < clean_slip_max ≤ 50 mm` (the right's own band in P60
§2 — reported separately, never pooled into the escape distribution).
**Primary unit = the attempt's first escaping leg** (P60 §3.4's convention: a
payload lost in `grasp_lift` necessarily starts `place0` out of the hand, so
counting all legs double-counts one payload). **Secondary = all escaping legs.**
**Dominant axis** = `argmax |component|`; **mixed** per the decision table's 0.70
rule.

Reported per arm: the dominant-axis counts (x/y/z/mixed), the **signed mean and
median of the y component** (mm), the fraction with `y > 0`, the sign triple
`(sgn x, sgn y, sgn z)` counts, the component means with the map's prediction
beside them, and the concentration check. **Contingency registered in advance:**
P60's right arm had **0 cnps** (only 4/23 transients of 2.6–11.3 mm), so the
arm *contrast* may be **unmeasurable on this cell**. If the right has `< 3`
escaping legs, the primary read is the **left's own direction against the map**
(the right reported as n, no contrast claimed), and the transients are reported
as the only right-arm evidence — stated as such, never as a contrast.

**P3 — the motion contrast.** From the `[motion] carry grasp_lift: …` rows
(attributed to an arm by the enclosing episode's `arm=`, cross-checked against the
`[carry] <side>` row sequence): the **achieved** `|v|max` and `|a|max` (the ones
after `recoveries=`, not the payload's `in-hand |v|max`), plus `|v|cmd`/`|a|cmd`
(which must be identical across arms — the same profile) and the `recoveries`
count. Reported per arm as median [min–max]. **A difference is an IK/dynamics
asymmetry**, not a payload property (`AGENTS.md` §2: a carry leg's `|v|max` is the
hand). The legacy `slip_max` in those rows is **excluded** (frame-contaminated,
W8-B).

**P4 — the split (report only).** placed / cnp / never-held per arm, and the
`113_rl_report.py` note keys vs the P60 cell's — no new failure reason. No rate
claim (the direct loop conditions on rendered frames).

**P5 — the row format still parses (read-only).** Import `logs/p60/p3/report.py`
and run its `parse_leg` on the new rows: every field it names must resolve, with
`clean_slip` equal to the printed `clean_slip_max`, and `slip_xyz` parsed by this
phase's own parser; and confirm `logs/w8/B_metric.py`'s trace-row keys are
untouched by the change (its `clean_slip` is the same framed quantity, computed
from trace JSON, which this phase does not modify).

## 5. Falsifiers

- **F1** a row outside the P1 printing bound → **stop**, quote it, no
  interpretation.
- **F2** a wedge (the known renderer freeze) → retry that seed **once**; if it
  repeats, report the cell as incomplete for that seed.
- **F3** the class counts differ from P60's cell → **instrumentation-or-branch**
  (the diag adds one `tcp_pose()` + one tactile read per carry tick, the
  per-tick-link-read class `AGENTS.md` §2 records as outcome-moving; the loop is
  also not reproducible). Reported, never used as a rate or as a P2 input — P2
  reads rows, not counts.

## 6. What this phase cannot show (registered up front)

- **Arm vs lane vs grade** stays confounded (`rl_env.py:2516`: grade A → bin 0 →
  left). A direction *difference* between arms is therefore a difference between
  **arm+lane+grade**, not proof about the hand.
- The `force@onset` remains a single-tick sample (P60 §6b).
- The direction is read **at the maximum only** (one vector per leg) — a payload
  that first walks one way then another prints only the path's endpoint at the
  max. No trajectory claim.
- Nothing here flips a default or opens a lever; the deliverable is the
  mechanism read P60's residue asked for.

## 7. Provenance to be recorded with the results

Tree HEAD `ab2fe7c` **plus the uncommitted P61 instrument** (`tasks.py`
`9a5e0459…`, `rl_env.py` `TASKS_MD5` follow, `scripts/231_p61_slip_selftest.py`,
`scripts/selfcheck.sh` leg) — the working tree **is** the measured tree and its
md5s are pinned in `logs/p61/p2/header.txt` + `tree_md5_{before,after}.txt`.
Checkpoint `moe_v13s` `61da390a`. **No commit.**
