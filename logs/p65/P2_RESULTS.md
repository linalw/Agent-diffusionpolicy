# P65 phase 1 — **the drift does not coincide with a joint limit: every leg of both
# arms already sits on one, and the drift starts ~41 ticks before the limit's own
# minimum; `max_step` never binds (0.030 of 0.5 rad)**

Written 2026-10-29 on HEAD `1079b82` + this tree's uncommitted P65 instrument.
**No shipped default changed** (`FRUIT_CARRY_DIAG` stays default off), **no
controller change** (`control.py` untouched), **no `configs/` byte moved**, **no
commit**.

## Verdict

* **The two named suspects are refuted, and for different reasons.**
  **`max_step`** (`control.py:423`) is refuted **by measurement**: the largest
  per-tick command step on any leg of the cell is **0.0300 rad** against the
  **0.5 rad** `FRUIT_IK_MAX_STEP` cap — **6 % of it**, so the bound is never
  reached (`q_step_max` on 44/44 `grasp_lift` legs).
  **The joint-limit clip** (`control.py:494`) is refuted **by discrimination**:
  the measured margin is **0.000 rad on 86/86 legs** — the left's 20 lifts, the
  right's 24 lifts **and all 42 place legs** — so "a joint at its limit" is a
  **standing condition of this workspace**, not a lift-specific cause; and on the
  left's 18 failing (`cnp`) legs the drift's onset (`drift_on`, median tick 106 of
  ~160 = **65 %** of the leg) **precedes** the tick the leg's smallest margin was
  taken (median **-41 ticks**, inside the registered +-20 on **3/18**).
* **So the registered P2 clause reads SUPPORTED and the causal reading reads
  REFUTED — both are reported.** The rule's *refutation* clause needed a healthy
  margin (>= 0.15 rad) and it does not obtain (the minimum over all 44 lifts is
  **-0.001 rad**); the rule's *support* clause ("a joint at/near its limit")
  obtains on 18/18 failing legs. What separates them is that the same is true of
  every successful leg, which is what the phase adds.
* **The pads' line (P3) does not separate either, and it points the other way.**
  At the lift's **first** tick both arms are flat (`|jaw_z|` median **0.0084**
  left / **0.0104** right, i.e. 0.8-1.0 mm of pad height difference across the
  98 mm jaw). Over the leg both develop a twist and the **right's is larger**:
  median max **0.239** (left, 23.4 mm) vs **0.371** (right, 36.4 mm), worst leg
  0.361 / 0.565. So the left does **not** tip its pads more; the arm that places
  23/24 tips them more.
* **The class counts are the P63 shape at a moved branch** (left cnp-majority,
  right placed-majority): pooled **24/45 placed**, left **1/18 cnp/1**, right
  **23/0/2** against P63's control **31/45**, left 2/11/2, right 29/0/1. The
  attempt split moved (left 20 / right 25 vs 15 / 30), so per the registered F3
  clause this is **instrumentation-or-branch** and **no delta is quoted**. One
  reason key is absent from P63's control (`fruit fell off the line` x1) and it is
  a **recorded** key (P35's `logs/p35/B_ab/A_4.log`), not a novel one.
* **The instrument is clean**: 44/44 `grasp_lift` rows carry **all five** fields,
  **0** `(no-hold)`, and `p2_report.py --check` passes 12/12 structural
  assertions including P60's parser still reading every row.

## 1. P1 — the instrument (reporting only, `FRUIT_CARRY_DIAG`)

Five fields on the existing `[carry]` row, immediately after `hold_drift=`:

| field | object | how |
| --- | --- | --- |
| `q_margin=<rad>@jN/tI` | the **measured** joint-limit margin `min(q-lo, hi-q)` over the 7 arm joints, its **minimum over the leg**, the 1-based binding joint `N` and the tick `I` it was taken | `arm.joint_positions()` / `arm.arm_lo` / `arm.arm_hi` (the accessors the `[acq]` diag already uses, `tasks.py:10431-10434`) |
| `q_cmd_margin=<rad>@jN` | the same for the controller's **post-clip command** `arm._q_cmd` — the direct operand of `control.py:494` | a numpy attribute: **no sensor read** |
| `q_step_max=<rad>` | the leg's largest per-tick `max abs(dq_cmd)` — the `control.py:423` operand | the same attribute |
| `jaw_z=<first>/<max abs>` | the **jaw-opening axis' world z** (`rot_now[:, 1]`, the axis P64's probe re-settled) at the leg's first tick and its max abs | a column of the rotation the slip frame already builds: **no pose read** |
| `drift_on=<tick>` | the first tick `hold_drift` passes 10 deg (`None` if never) | the existing dot product |

**Cost: one added sensor read per guarded tick** (`get_dof_positions()`, the same
PhysX reader `ik_step` calls every tick at `control.py:387`; `joint_positions()`
is its arm-slice `.copy()`), **zero new pose reads** — the P39 one-read rule is
honoured on the pose side. Everything sits inside `if guard_armed:` whose first
condition is `self._carry_guard_active or self._carry_diag`, so `None`/off is
byte-inert: the scripted acceptance's `[fruit]` stream is **377/377 identical** to
`logs/p41/p2/accept_profile.log` (excluding that file's own `[carry]`/`[diag]`
rows, which exist because it was recorded with the diag on) with
**`fingerprint: matches configs/motion_reference.json`** (§8).

The leg is pinned by `scripts/235_p65_lift_selftest.py` (a selfcheck leg): the
field set and order, the `guard_armed` containment, the margin/argmin/min-over-leg
arithmetic (including negative margins), the `rot[:,1]` jaw axis on a known
rotation, the first-crossing onset semantics, and the row parsing back.

## 2. The cell

`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1`, the shipped `direct`
profile with no supply/trigger/park override, `--episodes 15 --seeds <77|101|202>`,
one claim per run (`logs/p65/p2/run_p2.sh`). Batch 20:51:13 → 21:18:59, **27 min
46 s** (9:07 / 9:35 / 9:04 per seed), **3/3 exit 0, no wedge** (F1 unused). **86 `[carry]` rows** = 44 `grasp_lift`
+ 42 place legs over **45 attempts**. Per seed placed: **10 / 5 / 9 of 15**.

## 3. P2 — the test

### the left's failing legs, one row each (all 18)

| seed | ep | ticks | drift deg | q_margin rad | j | t_min | drift_on | dt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 77 | 0 | 156 | 25.2 | -0.000 | j2 | 127 | 101 | -26 |
| 77 | 3 | 164 | 21.6 | 0.000 | j7 | 163 | 116 | -47 |
| 77 | 6 | 156 | 20.9 | 0.000 | j7 | 155 | 112 | -43 |
| 77 | 8 | 154 | 27.4 | -0.000 | j2 | 121 | 89 | -32 |
| 77 | 13 | 153 | 26.4 | -0.000 | j5 | 130 | 96 | -34 |
| 101 | 0 | 153 | 26.8 | -0.000 | j7 | 101 | 96 | **-5** |
| 101 | 2 | 156 | 21.9 | 0.000 | j7 | 155 | 104 | -51 |
| 101 | 4 | 158 | 22.3 | 0.000 | j7 | 157 | 105 | -52 |
| 101 | 5 | 165 | 22.8 | 0.000 | j2 | 137 | 118 | **-19** |
| 101 | 10 | 163 | 23.8 | 0.000 | j7 | 162 | 107 | -55 |
| 101 | 11 | 157 | 29.6 | -0.000 | j5 | 116 | 96 | **-20** |
| 101 | 14 | 161 | 22.3 | 0.000 | j2 | 157 | 111 | -46 |
| 202 | 1 | 162 | 24.1 | 0.000 | j7 | 161 | 106 | -55 |
| 202 | 3 | 167 | 25.4 | -0.000 | j7 | 35 | 108 | +73 |
| 202 | 4 | 174 | 20.4 | 0.000 | j7 | 173 | 125 | -48 |
| 202 | 5 | 159 | 24.1 | -0.000 | j7 | 83 | 104 | +21 |
| 202 | 6 | 163 | 22.0 | -0.000 | j5 | 162 | 116 | -46 |
| 202 | 7 | 161 | 25.2 | -0.000 | j2 | 138 | 105 | -33 |

Reading: the margin is **0.000** everywhere (the *measured* joint is at or a
hair past its limit), the binding joint is **j7 x10, j2 x5, j5 x3**, and the
minimum is taken at **t = 35..173 of 153..174** (i.e. at the leg's end on 16 of
18, early on two - `202/3` at t=35 is the leg whose drifts starts at 108, and
`202/5` at t=83). The drift's onset is at **65 % of the leg** (median
`drift_on/ticks = 0.65`, p10/p90 0.58/0.72), i.e. **before** the limit contact on
15/18.

`dt = drift_on - t_min`: median **-41 ticks**, range -99..+73, negative on
**42/44** legs and inside the registered +-20 on **5/44** (3/18 of the failing
ones).
**The registered coincidence does not obtain.**

### P2b — the margin does not discriminate

| group | n | margin <= 0.05 | margin >= 0.15 | median | min |
| --- | --- | --- | --- | --- | --- |
| left `grasp_lift` | 20 | **20/20** | 0/20 | 0.000 | -0.000 |
| right `grasp_lift` | 24 | **24/24** | 0/24 | -0.000 | -0.001 |
| left place | 19 | **19/19** | 0/19 | -0.000 | -0.000 |
| right place | 23 | **23/23** | 0/23 | -0.000 | -0.000 |

**86/86 legs at the limit.** The clip is reached on the arm that *places* 23 of
24 lifts at the same 0.000 margin, so no reading of "the clip explains the drift"
can be separated from "this arm is always at a limit in these poses".

### the command side (the clip's own operand) and the step cap

* `q_cmd_margin`: median **0.000 rad**, min **0.000** on the same 18 legs - the
  **commanded** vector is clipped too, i.e. `np.clip(q_cmd + dq, arm_lo, arm_hi)`
  is active. (The binding joint differs from the measured one on some legs - e.g.
  measured `j2`, commanded `j3` - which is itself a hint that the *measured*
  minimum is the trailing side of a saturated command, not a separate event.)
* `q_step_max`: **0.0300 rad** max over the cell against the **0.5** cap = **6 %**.
  `FRUIT_IK_MAX_STEP` is unset in the cell, so the shipped default is the read.

**Consequence for phase 2:** a `max_step` lever has nothing to move (it never
binds), and a joint-limit lever cannot be aimed at the lift because the limit is
already the workspace's standing condition. What is left is *which* pose the lift
asks for - a static feasibility question at the lift's top, not a controller gain.

## 4. P3 — the pads' line

| arm | n | `|jaw_z|` first (med) | `|jaw_z|` max (med) | worst leg | pad dz at that max |
| --- | --- | --- | --- | --- | --- |
| **left** | 20 | 0.0084 | **0.2392** | 0.3610 | 35.4 mm |
| **right** | 24 | 0.0104 | **0.3705** | 0.5653 | 55.4 mm |

Both arms start flat (0.8/1.0 mm of pad height difference across the 98 mm jaw)
and develop the twist **during** the lift; the **right's is the larger one**. The
left does **not** tip its pads. For reference P64's rejected `QPREC` command is
`|jaw_z| = 0.2949` (28.9 mm) - a *commanded* one-pad-first attitude; the shipped
line commands `0.0095` and achieves 0.24/0.37 mid-lift, i.e. the twist is part of
the same arm-common attitude residual P63 measured, not a station command.

## 5. P4 — the class counts (report only)

| arm | placed | cnp | never-held | attempts | `grasp_lift` legs |
| --- | --- | --- | --- | --- | --- |
| left | 1 | **18** | 1 | 20 | 20 |
| right | **23** | 0 | 2 | 25 | 24 |
| pooled | **24/45** | 18 | 3 | 45 | 44 |

**No rate claim** (3 seeds of a rendered-frame loop, AGENTS.md §3b).

**F3 vs P63's control** (`logs/p63/p2/D_{77,101,202}.log`, same scenario /
checkpoint / seeds; the tree differs only by these five fields):

| read | this cell | P63 control |
| --- | --- | --- |
| left placed / cnp / never-held | 1 / **18** / 1 (n=20) | 2 / **11** / 2 (n=15) |
| right placed / cnp / never-held | **23** / 0 / 2 (n=25) | **29** / 0 / 1 (n=30) |
| pooled placed | **24/45** | **31/45** |

The attempt split moved **before** any outcome was read (left 20/right 25 vs
15/30), so this is **instrumentation-or-branch** and **no delta is quoted** - the
same call P63 made on its own cell. Reason keys: `fruit did not follow the
gripper` x2 (recorded; P60/P63 print it) and `fruit fell off the line` x1
(recorded; `logs/p35/B_ab/A_4.log`) - **no novel reason key**.

## 6. Pre-run predictions, scored (PREREG §5; A1 adds no rule)

| id | prediction (PREREG §5) | outcome |
| --- | --- | --- |
| **Pa** | 0 `(no-hold)`, 5/5 fields on every `grasp_lift` | **✓** 0/44 and 44/44 |
| **Pb** | left cnp `q_margin >= 0.15` -> both suspects refuted | **✗ the margin is 0.000** (18/18 at the limit) - the refutation arrives from **discrimination** (86/86 legs) instead, and `max_step` from `q_step_max` |
| **Pc** | `q_step_max <= 0.10 rad/tick` | **✓** 0.0300 = 6 % of the 0.5 cap |
| **Pd** | `drift_on` early (< 0.35 of the leg), the margin's min late | **half** - the min is late as predicted (t/ticks 0.95-1.00 on 16/18) but the onset is **0.65**, not < 0.35 |
| **Pe** | `|jaw_z|` max <= 0.06 on both arms | **✗ 0.239 / 0.371** - both arms twist; the right more |
| **Pf** | the class split reproduces P63's shape | **✓** left cnp-majority / right placed-majority (counts moved, F3) |

## 7. What this settles, and what it does not

**Settled.** (a) `max_step` never binds on the carry (0.030 of 0.5 rad, 44/44
legs). (b) The joint-limit clip **is** active - measured and commanded margins are
0.000 - but it is active on **every** leg of both arms and on every place leg, so
it cannot be the lift's discriminator. (c) The drift's onset is at **~65 % of the
leg**, ~41 ticks before the leg's smallest margin is taken, so the drift is mostly
accumulated before the limit is reached. (d) The pads' line is **not** the left's
problem: both arms twist, the right more, and both start flat. (e) The class
shape reproduces P63 (left cnp-majority, right placed-majority) at a moved
branch.

**Not shown - the named residual.** The row carries the leg's **minimum** margin
only, so the margin **at the onset tick** is not measured: the statement "the
drift starts before the limit is reached" rests on the *tick ordering*
(`drift_on < t_min`), not on a margin time series. The clean follow-up is two
more numbers on the same row (the margin at `drift_on`, and the margin at the
leg's first tick), which is an instrument change with no new lever. The
**static feasibility of the lift's end pose** (the top-down attitude at z + the
lift height, solved the way `logs/p62/ik_probe.py` solves the station) is the
phase-2 candidate the data points at: if that pose is infeasible with the same
signature P64's `QPREC` showed (`qerr` 20-33 deg at a 43-73 mm residual), the
25 deg is a **workspace** fact of the lift, not a controller one.

## 8. No-harm, pins, reproduce

**No-harm:** `scripts/selfcheck.sh` **PASS 0 failures** (including the new
`235` leg), and `scripts/accept.sh` with every knob unset
(`ACCEPT_LOG=logs/p65/accept_noharm_final.log`) reads **6/10**,
**`fingerprint: matches configs/motion_reference.json`**, with the physics
`[fruit]` stream **377/377 identical** to `logs/p41/p2/accept_profile.log`
(that record was taken with `FRUIT_CARRY_DIAG=1`, so its own 20 `[carry]` + 60
`[diag]` rows are excluded from the comparison; the FAIL is the documented
rate-only branch, 6/10 < the 0.75 floor). No two-line run was needed: the
instrument cannot reach the two-line (it needs `_dynamic_capture_active` **and**
the diag knob), and no `src/` path outside that branch changed.

**Reproduce:**

```bash
bash logs/p65/p2/run_p2.sh                      # the cell, 3 claims, 27 min 46 s
python3 logs/p65/p2_report.py --check           # -> logs/p65/p2_report.txt, 12/12
python3 scripts/235_p65_lift_selftest.py        # the instrument's selfcheck leg
```

**Pins:** `logs/p65/PREREG.md` **c233c956** (includes amendment A1), `logs/p65/p2/run_p2.sh`
**c5db7aa7**, `header.txt` **e0b6ca7e**, `C_77.log` **8132deb0**, `C_101.log`
**672fe56b**, `C_202.log` **fdae1cc8**, `logs/p65/p2_report.py`
**b681bcb7**, `logs/p65/p2_report.txt` **385698f1**; `tasks.py`
**309e5a38d66e5ac5c1892102506a2908** (the instrument), `rl_env.py`
**a10e753a9abfe8312a960565d78b24c9** (`TASKS_MD5` metadata-only follow),
`control.py` `9384ff4f` (**untouched**), `scene.py` `27e3d64a`,
`fruits.py` `c7461d41`, `policy/trigger.py` `b09d3cb2`,
`scripts/235_p65_lift_selftest.py` **5be0210d**, `scripts/selfcheck.sh`
**de674c84**; checkpoint `moe_v13s` **61da390a**; `configs/*` untouched
(`waypoints.json` `d81c6f1c`, `waypoints_oriented.json` `0ea08ebb`,
`arm_parks.json` `42ab4fb7`, `motion_reference.json` `8a399626`,
`motion_reference_twoline.json` `2246f83c`).
`FRUIT_CARRY_DIAG` stays default **off**, `FRUIT_IK_MAX_STEP` / `FRUIT_IK_RATE`
were neither set nor moved, and no new knob was added.
**`logs/` is gitignored**, so this directory needs `git add -f` at the close-out.
