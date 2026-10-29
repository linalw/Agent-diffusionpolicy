# P64 phase 2 PRE-REGISTRATION — the pre-compensated left carry attitude, cell

Written 2026-10-29 **before** the cell's runs. Tree: HEAD `4954d09` + the
uncommitted P64 phase-1 change (default-off knob; no `configs/` edit, no commit).
`tasks.py` `7a8a163a`, `rl_env.py` `7c137553` (the `TASKS_MD5` metadata follow),
`scripts/234_p64_precomp_selftest.py`, `scripts/selfcheck.sh`; checkpoint
`moe_v13s` `61da390a`, `configs/*` untouched (`8a399626` / `2246f83c`).

## 1. The lever (phase 1, built and gated)

The left is **commanded** T0 and **achieves** a 25-29 deg tilt whose azimuth is
the belt axis (P61-P63). Phase 1 derives the **minimal** rotation from the
commanded tool axis `(0,0,-1)` to the measured **median** achieved axis
`(+0.303490, -0.350929, -0.885857)` over **7** left `grasp_lift` legs (P63
`A1_77` 3 + P62 `P0{A,B}` / `P0b{A,B}` 1 each; per-leg tilt 25.1-28.7 deg,
azimuth spread +-3.2 deg, belt projection +0.3210..+0.3658):

```
q_drift : axis (-0.756380, -0.654132, 0.000000), angle 26.798198 deg
q_cmd   = q_drift^-1 (x) q_T0 = [+0.016754, -0.687859, +0.687859, +0.231126]
          command tool axis (-0.294915, +0.341014, -0.892600), belt proj -0.3410
```

**The live site.** Not P62's `grasp_quat_override` (that feeds `_grasp_quat`,
which the never-stop catch releases before the descent - P62 measured it inert on
the achieved attitude). The command `ik_step` actually tracks during the lift is
`arm.hold_quaternion`, installed by the catch before the hover
(`tasks._run_impl`) and **inherited** by `grasp_lift` (the `_carry` clear is
`name != "grasp_lift"`; every place leg clears it). Phase 1 therefore writes the
pre-compensated hold at the **start of the `grasp_lift` leg only**
(`tasks.carry_hold_override_for` + the one guarded `arm.hold_quaternion` write in
`_carry`), passed as the caller-owned kwarg `carry_hold_override` from
`rl_env.resolve_carry_hold_override` (`FRUIT_GRASP_LEFT_PRECOMP=1`, direct +
left only, default off). The grip is still taken at the shipped attitude, so the
P42/P61 seat geometry is untouched.

## 2. The cell

3 seeds x 15 picks, both arms, **one claim per run**, `logs/p64/p2/P_{77,101,202}.log`,
driver `logs/p64/p2/run_p2.sh`:

```
FRUIT_GRASP_LEFT_PRECOMP=1  FRUIT_CARRY_DIAG=1  FRUIT_ACQ_DIAG=1
FRUIT_CARRY_ATTITUDE=1      # reporting-only, one TCP read per carry leg (P39)
+ the shipped direct profile and the P63 scenario verbatim
```

`FRUIT_CARRY_ATTITUDE=1` is added because E1 needs the **achieved tool axis** per
leg; it is P39's reporting-only read (one TCP pose per leg, no per-tick work) and
P63's own A1 addendum already used it on the control's scenario.

**Control = P63's cell** (`logs/p63/p2/D_{77,101,202}.log`, same scenario,
checkpoint and seeds; left 2 placed / 11 cnp / 2 never-held of 15, right 29 / 0 /
1 of 30). The tree differs only by the P64 plumbing, which is inert with the knob
unset (`234` executes the real `carry_hold_override_for`: `None`/empty/unnamed
side/every leg but `grasp_lift` -> no write).

## 3. Endpoints (registered; no post-hoc additions)

* **E1 (mechanism).** The left's `grasp_lift` achieved belt projection moves from
  the control's **+0.32..+0.37** to **<= +0.10**, read per leg as
  `[attitude] ... tool_axis=(x,y,z)` -> `-y` (end-of-leg read), with the
  treatment's `[grasp] left precomp:` row naming the command actually installed.
  Report the per-leg distribution and the median; a *sign flip* (projection
  becoming more positive) is an E1 failure **and** the finding.
* **E2 (class).** The left's `cnp` count against the control's **11/15 attempted**
  (control: 2 placed / 11 cnp / 2 never-held). **Exact counts, no rate claim**
  (rendered-frame loop, `AGENTS.md` section 3b).
* **E3 (scope).** The right arm unchanged vs the control's **29 / 0 / 1** (the
  knob names only `left`; the right is a branch check, not a rate).
* **E4 (no-harm).** No new failure-reason key vs the control's set, and
  `scripts/accept.sh` with **every knob unset**: **377/377** `[fruit]` lines
  identical to `logs/p41/p2/accept_profile.log` + `fingerprint: matches`
  `configs/motion_reference.json` (`8a399626`).

## 4. Pre-run prediction (recorded before the runs, with its reason)

Phase 1's **gate smoke** (`logs/p64/p2/S_77.log`, 4 episodes, seed 77, knob on;
NOT an arm of the cell) produced **2 left legs**, and both moved the **wrong
way**: achieved tool axis `(+0.3491, -0.5768, -0.7385)` and
`(+0.2905, -0.7008, -0.6515)`, i.e. belt projection **+0.577 / +0.701** (tilt
42.4 / 49.3 deg) against the control's +0.32..+0.37, with `hold_drift` 59.0 /
62.8 deg *from the new command* (so the command really was installed). Both left
legs cnp'd, with the contact loss earlier than the control's (onset rows 37/39
vs 97-127). The channel is therefore **live** (the achieved attitude responds to
the hold) and the response has the **opposite sign** to the registered model.

Prediction for the cell: **E1 fails** - the treatment's left median projection
lands in **+0.45..+0.75** (not <= +0.10), i.e. the "constant residual, invert it"
model is falsified and the arm's achieved attitude is **position-led** (the
orientation command is traded against the position target at this marginal
station reach, `logs/p62/CANDIDATES.md` section 5). E2: the left's cnp count does
**not** fall below 11 (predicted 11-15 of 15); the class is not converted by a
*larger* tilt either (P63: the right places 29/30 at 25.8 deg). E3: the right's
counts are unchanged in shape (29/0/1 +-1). E4 passes (the knob is unset in the
acceptance and the scripted path never constructs this env).

## 5. Decision rule

* E1 fails -> **no default change**, no `configs/` edit, and the phase reports
  the **response function** (commanded projection vs achieved projection) as the
  result: it is the measurement the owner's "choose a pose the left can hold"
  question needs, whichever sign it has.
* E1 passes and E2 falls -> still **no default change** in this phase (a pass is
  not adoption; a single cell on a non-reproducible loop is one branch), but the
  lever is named as an adoption candidate with its own pre-registration.
* F1 (wedge / non-zero exit): one retry per seed, as P63's cell.

## 6. What is **not** measured here

* Any rate: 3 seeds of a rendered-frame loop is one branch per seed.
* Whether a **smaller** pre-compensation or the **opposite** (downstream) command
  would land the achieved projection near zero - the smoke gives two points on a
  response whose slope is not yet identifiable; that is a new registration.
* Whether the *block* hold (hover/descent/close) responds the same way as the
  leg hold (this cell commands the leg only, so the grip is the shipped attitude).
* The right arm's response (the knob is left-only by construction).
