# P63 phase 2 — pre-registration: **where the 26–29 deg goes** (hold/IK vs command path)

Written **before any simulator run** of this phase (2026-10-29; no
`logs/p63/p2/*.log` exists yet). The brief is `.slim/deepwork/p63-attitude-hold.md`;
the context is P62 (`logs/p62/P2_RESULTS.md`, the achieved-vs-commanded gap),
P61 (`logs/p61/P2_RESULTS.md`, the slip's direction) and P60
(`logs/p60/P3_RESULTS.md`, the class).

## 1. The question

P62 measured that the direct line's left arm is **commanded** the pure top-down
attitude (`configs/waypoints.json`'s left `grasp_quaternion` = the catch's own
installed hold = T0, `[w,x,y,z] = (+0, −0.707107, +0.707107, +0)`, belt
projection **0.000**; `[grasp] ... file_same=1 hold_same=1`) and still
**achieves 26.3–28.7 deg of tilt** (belt projection **+0.32…+0.36**) at the end
of its `grasp_lift`. That tilt *is* the +0.513 projection the slip runs along
(P61). So the residual is one of two things, and they have different fixes:

* **(a) hold/IK** — the command is right and the arm **cannot hold** it: the
  achieved wrist drifts away from `arm.hold_quaternion` during the leg. The fix
  family is the hold's weight in `ik_step` / the re-solved grasp seed (P62 §5
  items 1–2), i.e. the tracking loop.
* **(b) command path** — the achieved attitude *is* the commanded one, and the
  `hold_quaternion` **during the lift** is not T0 (e.g. the *pre-pose's* attitude
  captured at `tasks.py:3488`, whose caller is the carry loop). Then the fix is
  the command path, and it is cheaper.

The instrument is already in the tree (P63 phase 1, `tasks.py` **`1d27566c`**,
pinned by `scripts/233_p63_attitude_selftest.py` **`1146173e`**, selfcheck PASS):
every `[carry]` row now prints

```
hold_drift=<deg>[ (no-hold)]
```

`hold_drift` = `max over the leg's guarded ticks of 2*acos(|dot(hold_quaternion,
tcp_quat)|)`, i.e. the **commanded-vs-achieved** wrist attitude, in degrees, both
quaternions read post-step in the same `(w,x,y,z)` convention (`tasks.py:4066-4095`).
`(no-hold)` is printed when `hold_quaternion` was `None` on **every** guarded tick
of the leg (`guard_hold_seen = 0`). Reporting only: one dot product per guarded
tick, no control input, `FRUIT_CARRY_DIAG` default **off**.

**No `src/`, `configs/` or `scripts/` edit is made by this phase.**

## 2. The cell (one claim per run, 3 seeds × 15 picks, the shipped profile)

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_ACQ_DIAG=1
HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1
scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
  --presentation direct --episodes 15 --seeds <77|101|202> --out logs/p63/p2/rollouts
```

Logs `logs/p63/p2/D_{77,101,202}.log`; driver `logs/p63/p2/run_p2.sh`; one claim
per run through `scripts/154_claim_run.sh` (`RUN_LIMIT=2700`).

Deliberately **not** set — the shipped `direct` defaults: `FRUIT_DIRECT_CONTINUOUS`
(P56), `FRUIT_POLICY_TRIGGER_ACQ` (P54 resolves on for `direct`),
`FRUIT_ARM_PARK` (P43 resolves `back` for `direct`), `FRUIT_GRASP_LEFT_TOPDOWN`
(P62, default off), `FRUIT_CARRY_GUARD` / `FRUIT_CARRY_RELIEF` /
`FRUIT_CARRY_MONITOR` (the diag must not actuate), `FRUIT_CARRY_ATTITUDE` and
`FRUIT_MOTION_REPORT` (not needed: the drift is the endpoint).

**The F3 comparator is P61's own cell** (`logs/p61/p2/S_{77,101,202}.log`): the
same scenario, the same checkpoint, the same seeds, the only tree difference being
the reporting-only `hold_drift=` field (`tasks.py` `9a5e0459` → `1d27566c`).

## 3. The code read that fixes the interpretation (done before the run)

`arm.hold_quaternion` is the IK's orientation target (`control.py:378-383`: when
it is not `None`, `ik_step` solves the full 6-DoF error `[position, rotation]`
against `j_full`; when it is `None` it solves position only, `j_full[0:3]`).
Writes on the direct dynamic line:

| site | what | live on `grasp_lift`? |
|---|---|---|
| `tasks.py:8476` (the `dynamic_pick` hover) and `:9294` (the coherent block) | `hold = top_down_quaternion("x")`, mirrored across xz for the left — **T0** | **yes** (installed before the hover) |
| `tasks.py:8409` → `:8439` | `_grasp_quat(arm)` (the pre-pose) then `None` ("the carry and the place poses are position-only") | no (cleared before the descent) |
| `tasks.py:3466` | `arm.hold_quaternion = None` for the OpenArm hand when `name != "grasp_lift"` | **no — `grasp_lift` is exempt** (that is the leg the top-down hold exists for) |
| `tasks.py:3488` | `arm.hold_quaternion = quat` **only if `FRUIT_CARRY_HOLD_QUAT=1`** (`quat` = the stored grip quaternion, else the leg-start TCP) — *unset in this cell* | no |
| `tasks.py:3927` | the place-start wrist hold's release (`place_hold_active`) | no (place legs) |
| `tasks.py:4386` | `if hold_wrist: arm.hold_quaternion = None` at the leg's end | no (`hold_wrist` False) |
| `tasks.py:2218` | the post-place lift (`hold_quaternion = None`) | no (post-place lift, not `grasp_lift`) |

So **on `grasp_lift` the command during this cell is expected to be T0**, and the
`(no-hold)` count is the check on that read. The line numbers the brief quotes
(`2218/3466/3918/4366`) are this tree's `2218/3466/3927/4386` — +9 lines after
3918 from P61's own `slip_xyz` block; the sites are the same code.

## 4. Endpoints (registered)

**P1 — the instrument.** Every `[carry]` row carries `hold_drift=`; report the
`(no-hold)` count with the code sites above. F2 fires if the field is absent
anywhere (the knob did not arm).

**P2 — the split (primary).** Per arm, the `hold_drift` distribution on the
**`grasp_lift`** legs, split by the **attempt's** outcome (`placed` vs `cnp` vs
`never-held`; `cnp` = grasped and not placed, `never-held` = never grasped —
`logs/p60/p3/report.py`'s `outcome()`). Report n, median, range, p10/p90.

**Decision rule (registered):**

| observed | verdict |
|---|---|
| drift **>= 20 deg** on the failing (`cnp`) legs of **both arms** — or of the **left alone** — with the hold live | **(a) hold/IK**: the command is right, the arm cannot hold it |
| drift **< 10 deg** while the achieved belt projection is still **+0.32…+0.36** (P62's measurement on this same scenario) | **(b) command path**: the `hold_quaternion` set during the lift *is* the achieved attitude and is not T0 (`tasks.py:3488` + its caller) |
| neither (drift 10–20 deg, or the two arms disagree in a way the numbers do not resolve) | **report both ways, no verdict forced** — the brief's instruction |

**P3 — does the drift predict the slip?** Per arm, `hold_drift` vs
`clean_slip_max` on the same `grasp_lift` legs: n and the **sign** of the trend
(Spearman rank correlation, printed as a number; the brief asks for a scatter
summary, not a fitted model). Escapes are `clean_slip_max > 50 mm` (P61's
convention); the count of legs above that on each arm is reported too.

**P4 — the split and the reasons (report only).** Per-arm placed / cnp /
never-held, pooled placed/45, and the `113_rl_report.py` note keys vs P61's cell.
No rate claim: the direct loop conditions on rendered frames (`AGENTS.md` §3b).

## 5. Pre-run predictions (recorded before the run, so they can be wrong)

* **Pa** — `(no-hold)` rows: **0 on every `grasp_lift` leg** (the hold is installed
  before the hover and `grasp_lift` is exempt from the `:3466` clear). Any
  `(no-hold)` on a `grasp_lift` leg is a **finding** against §3's read.
* **Pb** — left `grasp_lift` drift: median **>= 20 deg** (predicted 24–30, P62's
  achieved tilt 26.3–28.7 deg), range up to ~35 on escape legs.
* **Pc** — right `grasp_lift` drift: **nonzero but smaller** than the left's
  (predicted median 8–25 deg), because P62 measured the right's achieved
  projections smaller in magnitude (−0.069 / −0.295 / −0.278) — the right also
  solves a 6-DoF target away from the command, just less.
* **Pd** — drift does **not** linearly predict the slip: the expected Spearman
  |rho| < 0.6 pooled. The prediction is that the drift is an arm/posture property
  and the escapes are loaded slides that keep the pads on the payload for tens of
  ticks (W8-B / P61), so a *larger* drift need not mean a *larger* slip.
* **Pe** — the class split reproduces P61's shape (left cnp the majority of its
  attempts, right placed the majority), so F3 will read a count difference; the
  direct loop is not reproducible, so it is instrumentation-or-branch.

**If Pb holds and Pc holds with the right placing most of its attempts**, the
honest verdict is: the mechanism of the 26–29 deg is **(a) hold/IK**, and the
drift is **necessary but not sufficient** for the cnp class — which is a
statement the phase can make and a rate claim it cannot.

## 6. Falsifiers

* **F1** — a wedge (no `[rl] rollout` summary / non-zero exit) → **retry that seed
  once**; two failures on one seed = report it and continue with the others.
* **F2** — no `hold_drift=` field on any `[carry]` row → **stop** (the knob did not
  arm) and report the tree read.
* **F3** — the shipped stream moved vs the P61 cell (class counts) → report as
  **instrumentation-or-branch**, no delta, and keep P1–P3 (which read rows, not
  counts).

## 7. Analysis

`logs/p63/p2_report.py` (new, offline, reads only the three logs + P61's for the
F3 foot) → `logs/p63/p2_report.txt`; `--check` re-asserts the structural
invariants. It imports `logs/p60/p3/report.py`'s `parse_leg` / `parse_direct` /
`outcome` as-is, so P61 §6's "the row format still parses" check continues to
hold against the new field, and adds one `hold_drift` regex of its own.

## 8. What this phase will not show

* Any **rate** (3 × 15 on a rendered-frame loop is one branch per seed).
* **Which** of the 6-DoF solve's terms loses the attitude — that is the
  hold-weight / seed family of P62 §5, each needing its own pre-registration.
* The **right**-arm mechanism beyond its drift: its escapes are 1–2 per cell, so
  its "placed" legs are a distribution of *successful* carries, not of failures.
* Whether a left attitude the arm **can hold** would convert the cnp class.
