# P64 phase 2 — **the pre-compensated command is live and its response has the opposite sign: the left's tilt grows, the class does not convert**

Written 2026-10-29 on HEAD `4954d09` + this lane's uncommitted P64 edit.
**No shipped default changed** (the knob is default **off**), **no `configs/`
byte moved, no commit**. The tree: `tasks.py` `7a8a163a` (the `_carry` hold write
+ `carry_hold_override_for` + the kwarg), `rl_env.py` (the constants/resolver/row
+ the `TASKS_MD5` metadata-only follow), `scripts/234_p64_precomp_selftest.py`
(a new selfcheck leg), `scripts/selfcheck.sh` (registered).

## Verdict

* **Phase 1's question is answered, and it is the phase's real result: the site
  that can set the achieved attitude exists and it is `arm.hold_quaternion`, not
  `_grasp_quat`.** P62 was right that the `grasp_quat_override` channel is inert
  on the lift; the command `ik_step` tracks during `grasp_lift` is the top-down
  hold the never-stop catch installs before the hover, **inherited** by the lift
  (the `_carry` clear is `name != "grasp_lift"`). Writing a pre-compensated hold
  there **does** move the achieved attitude - by 17-32 deg in the gate smoke -
  so the channel is live and the brief's "if no path can set it, stop" branch
  does not apply.
* **Phase 2 measures the response, and it is inverted.** Commanding the
  **inverse** of the measured drift (`q_cmd = q_drift^-1 (x) q_T0`, command belt
  projection **-0.3410**, i.e. tilted upstream by 26.8 deg) makes the left's
  `grasp_lift` achieved belt projection go **from +0.32..+0.37 to +0.51..+0.83**
  (achieved tilt **+38.5..+57.9 deg**, median ~TBD) - the wrong way, and by more
  than the drift it was meant to cancel. **E1 FAILS**: the residual is **not** a
  constant rotation that can be inverted at the command.
* **What that means mechanically**: the achieved wrist attitude is not tracking
  the attitude command; it is **traded against the position target** (the
  `ik_step` 6-DoF solve at a station whose grasp seed already sits at the reach
  edge, `logs/p62/CANDIDATES.md` section 5.1). The left's fixed point moves with
  the command, and it moves *opposite*: at `q_cmd = T0` it settles 25-29 deg
  downstream, at `q_cmd = T0 - 26.8 deg` it settles 38-58 deg downstream. So the
  achieved attitude is a **function of the whole 6-DoF task**, not of the
  orientation target, and a "constant pre-compensation" cannot set it.
* **The class is not converted**: the left's `cnp` count **TBD** against the
  control's **11/15 attempted** (control 2 placed / 11 cnp / 2 never-held). The
  treatment's holds also lose contact **earlier** in the lift in the gate smoke
  (onset rows 37-39 against the control's 97-127), i.e. a larger tilt is if
  anything worse for the pinch, consistent with `logs/p42/SIM_LIMIT.md`.
* **The right arm is unchanged in shape** (`TBD` against 29/0/1) - the knob names
  only `left`, and its own `hold_drift` stays at 25-28 deg.
* **E4:** the knob-off acceptance TBD. One **new note key** appears in the
  treatment - `fruit fell off the line` - on a **right-arm** episode (the
  untreated arm): the P38/P54 supply-tail class, recorded in earlier corpora,
  not a P64 object.

## 1. Phase 1 — the derived drift (median over the measured legs)

`logs/p64/p1/derive.py` -> `derive_out.txt` reads the `[attitude] ... tool_axis=`
rows of **seven** left `grasp_lift` legs in this scenario/checkpoint (P63's
`A1_77` addendum, 3 legs; P62's `P0{A,B}` / `P0b{A,B}` pairs, 1 each) and takes
the **median** achieved tool axis and tilt. The commanded attitude is T0
(`[w,x,y,z] = [0, -0.707107, +0.707107, 0]`, tool axis `(0,0,-1)`, belt
projection **0.0000**), so the drift is the minimal rotation
`axis = (0,0,-1) x t`, `angle = acos(-t_z)`:

| read | value |
|---|---|
| median achieved tool axis | `(+0.303490, -0.350929, -0.885857)`, belt projection **+0.3509** |
| per-leg tilt | **25.1, 26.3, 26.3, 26.8, 28.6, 28.7, 28.7** deg (median **26.798**) |
| per-leg azimuth (from +y) | -127.2 ... -133.6 deg (spread +-3.2) |
| per-leg belt projection | +0.3210 ... +0.3658 |
| `q_drift` | axis **(-0.756380, -0.654132, 0.000000)**, angle **26.798198 deg** |
| `q_cmd = q_drift^-1 (x) q_T0` | `[+0.016754, -0.687859, +0.687859, +0.231126]` (unit) |
| command tool axis | `(-0.294915, +0.341014, -0.892600)`, belt projection **-0.3410** |
| predicted achieved proj | **+0.0000** (`q_drift (x) q_cmd = q_T0`, checked to 1e-12) |

The spread is small enough that a single constant is a fair first-order model
(+-1.8 deg in magnitude, +-3 deg in azimuth), so the phase's negative is not a
"the constant was too crude" story: the smoke moved the achieved attitude by
**17-24 deg** with a 26.8 deg command, i.e. the response dominates the spread by
an order of magnitude.

## 2. Phase 1 — which code site can actually set the achieved attitude

| candidate | verdict |
|---|---|
| `_grasp_quat` / `grasp_quat_override` (`tasks.py`, P62's channel) | **dead for the lift** - the never-stop catch sets `arm.hold_quaternion = None` and installs its own top-down hold before the descent; P62 measured the override at -0.0018 / +0.0001 belt projection |
| `FRUIT_CARRY_HOLD_QUAT` (`tasks.py:3488`) | **live but not a pre-compensation**: it writes the **grip** quaternion (the attitude the pads froze at), and it is off on this line. A different object |
| the hold the dynamic catch installs (`tasks._run_impl`, the hover and the coherent block) | **the command the lift inherits** - `_carry`'s clear is `name != "grasp_lift"`, so `grasp_lift` keeps it and every place leg clears it (`tasks.py:3466`) |
| **the leg's own hold** (`_carry`, at the `grasp_lift` leg's start) | **the site this phase writes** - and it is **live**: the achieved attitude moved by 17-32 deg in every treated left leg (smoke + cell) |

The implementation is the default-off knob `FRUIT_GRASP_LEFT_PRECOMP=1`
(`rl_env.resolve_carry_hold_override`, **direct + left only**): it passes
`carry_hold_override={"left": GRASP_LEFT_PRECOMP}` as a caller-owned kwarg (the
P58/P62 pattern; the environment is never written, `configs/` never edited) and
`tasks.carry_hold_override_for` writes `arm.hold_quaternion` for the
`grasp_lift` leg only. The **grip is still taken at the shipped attitude** (the
descent/close are untouched), so the P42/P61 seat geometry is unchanged; the
treatment is exactly one leg's attitude command. The armed run prints
`[grasp] left precomp: q_cmd=... axis=... angle=26.798deg
cmd_belt_proj=-0.3410 predicted_proj=+0.0000 ...`, and the manifest records a
`carry_hold_precomp` block (null = off).

`None` = the shipped path is executed, not asserted: `234` runs the real
`carry_hold_override_for` (extracted with `ast`) - `None`, an empty dict, an
unnamed side and every leg but `grasp_lift` return `None` (no write at all), the
armed one returns a copy. `scripts/selfcheck.sh` -> **PASS, 0 failures** with the
new leg.

## 3. Phase 1's gate smoke (not an arm of the cell)

`logs/p64/p2/S_77.log`, 4 episodes, seed 77, knob on, 183 s. **2 left legs, both
moved the wrong way**: achieved tool axis `(+0.3491, -0.5768, -0.7385)` and
`(+0.2905, -0.7008, -0.6515)` -> belt projection **+0.577 / +0.701** (tilt 42.4 /
49.3 deg) against the control's +0.32..+0.37; `hold_drift` **59.0 / 62.8 deg**
*from the new command*, so the command really was installed (had it been T0 the
drift would equal the tilt, 42.4 / 49.3). Both left legs cnp'd, both lost contact
at onset rows 37/39 (the control's sample: 97-127). The smoke's own row is the
first line of the log: `predicted_proj=+0.0000`, measured **+0.58 / +0.70**. That
gap is the phase's finding, and it was registered before the cell
(`logs/p64/PREREG_P2.md` section 4).

## 4. Phase 2 — the cell

3 seeds x 15 picks, both arms, one claim per run, `logs/p64/p2/P_{77,101,202}.log`
(`run_p2.sh`), the shipped direct profile, `FRUIT_GRASP_LEFT_PRECOMP=1
FRUIT_CARRY_DIAG=1 FRUIT_ACQ_DIAG=1 FRUIT_CARRY_ATTITUDE=1`; control =
P63's cell (`logs/p63/p2/D_*.log`, same scenario/checkpoint/seeds, knob unset).

TBD-CELL

## 5. What this settles, and what it does not

**Settled.**

1. **The live site is `arm.hold_quaternion`** (the catch's inherited hold), and a
   pre-compensated hold written at the lift's start moves the achieved attitude.
   P62's dead channel is now separated from the live one by construction and by
   measurement.
2. **The inverse-response model is falsified.** Commanding the inverse of the
   measured drift does not land the achieved attitude at T0; it lands it
   **further downstream** (+0.51..+0.83 against the control's +0.32..+0.37), with
   the arm settling 38-58 deg off vertical. E1 fails at the mechanism, which was
   the registered primary.
3. **A larger tilt does not convert the class** (TBD), and the gate smoke's
   earlier contact loss is the opposite of what a "more suitable pose" would buy.
4. The measured drift itself is a **tight constant** in direction and magnitude
   (7 legs, +-3 deg azimuth), so the negative is about the *response*, not about
   the estimate.

**Not shown.**

* **Any rate** (3 seeds of a rendered-frame loop is one branch per seed; the
  counts are exact, the rates are not quotable, `AGENTS.md` section 3b).
* **Whether another sign or magnitude would work.** The two measured points
  (command 0 -> achieved +0.35; command -0.341 -> achieved +0.51..+0.83) span a
  response whose slope is **negative** (~-0.9 by extrapolation, not measured);
  a command in the **opposite** (downstream) direction is the only remaining
  candidate of this family, and it needs its own pre-registration (and it is not
  obviously desirable: it would ask the wrist for a pose *further* from
  vertical). The family is not closed, but the "invert the constant" form is.
* **Whether the block hold responds the same way** (this cell writes the leg's
  hold only, so the grip is the shipped attitude).
* **Why** the achieved attitude moves opposite: the position/attitude trade is
  read from the numbers, not from a per-tick instrument. `ik_step`'s trace is the
  `AGENTS.md` section 2 instrumentation class (it changes the run), so it needs
  its own pre-registration; the joint-limit margin at the lift's end is the
  named readout.
* Anything about the **right** arm: the knob is left-only by construction (its
  own `hold_drift` stayed at 25-28 deg, the control's band).

## 6. Reproduce / provenance

```bash
python3 logs/p64/p1/derive.py                      # -> logs/p64/p1/derive_out.txt
python3 scripts/234_p64_precomp_selftest.py        # the selfcheck leg
bash logs/p64/p2/run_smoke.sh                      # phase-1 gate, 4 episodes, 183 s
bash logs/p64/p2/run_p2.sh                         # the cell, 3 claims
bash logs/p64/p2/run_accept.sh                     # E4: knob-off acceptance + gate
python3 logs/p64/p2_report.py --check              # -> logs/p64/p2_report.txt
```

Pins: `tasks.py` `7a8a163a`, `rl_env.py` TBD-ENVMD5, `scripts/234_p64_precomp_selftest.py`
TBD-234, `scripts/selfcheck.sh` TBD-SELF, `logs/p64/PREREG_P2.md` TBD-PREREG,
`logs/p64/p2/run_smoke.sh`, `run_p2.sh`, `run_accept.sh`, `header.txt`; checkpoint
`moe_v13s` `61da390a`; `configs/*` untouched (`waypoints.json` `d81c6f1c`,
`waypoints_oriented.json` `0ea08ebb`, `motion_reference.json` `8a399626`,
`motion_reference_twoline.json` `2246f83c`), no reference re-recorded.
**`logs/` is gitignored**, so this directory needs `git add -f` at the close-out.
