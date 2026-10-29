# P64 — **the pre-compensated command is live and its response is inverted: the left's tilt grows, the class does not convert**

Written 2026-10-29 on HEAD `4954d09` + this lane's uncommitted P64 edit (the
phase was later committed by the orchestrator as `789c3ea` + `dbb5fc3`; the
numbers below are the final-tree ones). **No shipped default changed** (the knob
is default **off**), **no `configs/` byte moved, no commit from this lane**. Tree:
`tasks.py` **`7a8a163a`**, `rl_env.py` **`7c137553`** (the `TASKS_MD5`
metadata-only follow), `scripts/234_p64_precomp_selftest.py` **`14cb3553`**
(a new selfcheck leg), `scripts/selfcheck.sh` **`caabfcbf`**.

## Verdict

* **Phase 1's question is answered, and it is the phase's real result: the site
  that can set the achieved attitude exists and it is `arm.hold_quaternion`, not
  `_grasp_quat`.** P62 was right that the `grasp_quat_override` channel is inert
  on the lift; the command `ik_step` tracks during `grasp_lift` is the top-down
  hold the never-stop catch installs before the hover/descent/close,
  **inherited** by the lift (`_carry`'s clear is `name != "grasp_lift"`). Writing
  a pre-compensated hold there **does** move the achieved attitude - the smoke's
  two left legs read 42.4 / 49.3 deg of tilt against the control's 25-29, and the
  cell's median is 47.0 against 26.8 - so the channel is live and the brief's "if
  no path can set it, stop" branch does not apply.
* **Phase 2 measures the response, and it is inverted.** Commanding the
  **inverse** of the measured drift (`q_cmd = q_drift^-1 (x) q_T0`, command belt
  projection **-0.3410**, i.e. tilted upstream by 26.8 deg) moves the left's
  `grasp_lift` achieved belt projection from **+0.32..+0.37 to a median +0.673
  (range +0.042..+0.830)** and the achieved tilt from **25-29 deg to a median
  47.0 (32.5..57.9)** - the wrong way, and by more than the drift it was meant to
  cancel. **E1 FAILS by sign**: the residual is **not** a constant rotation that
  can be inverted at the command.
* **Mechanically:** the achieved wrist attitude is not tracking the attitude
  command; it is **traded against the position target** by the `ik_step` 6-DoF
  solve at a station whose grasp seed already sits at the reach edge
  (`logs/p62/CANDIDATES.md` section 5.1). The left's fixed point moves with the
  command, and it moves *opposite*: at `q_cmd = T0` it settles 25-29 deg
  downstream, at `q_cmd = T0 - 26.8 deg` it settles 33-58 deg downstream. The
  achieved attitude is a function of the whole 6-DoF task, not of the orientation
  target, so no command-level constant can set it.
* **The class is not converted**: the left's `cnp` count **rises 11 -> 13**
  (treatment **1 placed / 13 cnp / 2 never-held of 16** against the control's
  **2 / 11 / 2 of 15**). The held-slide starts **earlier**: onset-row median
  **60** (range 1-102) against the control's **104.5** (1-136), and the one leg
  that placed did so at **48.4 deg** of achieved tilt - i.e. the larger tilt is
  not a post-loss artifact and does not help the pinch, consistent with
  `logs/p42/SIM_LIMIT.md`.
* **The right arm is unchanged in shape** (**28/0/1 of 29** against 29/0/1 of 30),
  and its own `hold_drift` stays at **24.0 (20.7-45.6) deg** - the knob names only
  `left`.
* **E4:** no new reason *on the treated arm*; one **new key in the cell** -
  `fruit fell off the line` - on a **right-arm** episode (the untreated arm), the
  P38/P54 supply-tail class, recorded in earlier corpora, not a P64 object. The
  knob-off acceptance is **377/377 `[fruit]` lines identical** to
  `logs/p41/p2/accept_profile.log` with **`fingerprint: matches`**
  (`8a399626`); the gate FAILs **on the rate only** (6/10 = 60 % - this tree's
  recorded count, P41-P43).

## 1. Phase 1 - the derived drift (median over the measured legs)

`logs/p64/p1/derive.py` -> `derive_out.txt` reads the `[attitude] ... tool_axis=`
rows of **seven** left `grasp_lift` legs in this scenario/checkpoint (P63's
`A1_77` addendum, 3 legs; P62's `P0{A,B}` / `P0b{A,B}` pairs, 1 each) and takes
the **median** achieved tool axis and tilt. The commanded attitude is T0
(`[w,x,y,z] = [0, -0.707107, +0.707107, 0]`, tool axis `(0,0,-1)`, belt
projection **0.0000**), so the drift is the minimal rotation
`axis = (0,0,-1) x t = (t_y, -t_x, 0)`, `angle = acos(-t_z)`:

| read | value |
|---|---|
| median achieved tool axis | `(+0.303490, -0.350929, -0.885857)`, belt projection **+0.3509** |
| per-leg tilt | **25.1, 26.3, 26.3, 26.8, 28.6, 28.7, 28.7** deg (median **26.798**) |
| per-leg azimuth (from +y) | -127.2 ... -133.6 deg (spread **+-3.2**) |
| per-leg belt projection | +0.3210 ... +0.3658 |
| `q_drift` | axis **(-0.756380, -0.654132, 0.000000)**, angle **26.798198 deg** |
| `q_cmd = q_drift^-1 (x) q_T0` | `[+0.016754, -0.687859, +0.687859, +0.231126]` (unit) |
| command tool axis | `(-0.294915, +0.341014, -0.892600)`, belt projection **-0.3410** |
| predicted achieved proj | **+0.0000** (`q_drift (x) q_cmd = q_T0`, checked to 1e-12) |

The spread is small (+\-1.8 deg in magnitude, +\-3 deg in azimuth), so the
phase's negative is not a "the constant was too crude" story: the response to a
26.8 deg command moves the achieved tilt's median by **+20.2 deg** (26.8 -> 47.0)
and its belt projection by **+0.32** (0.354 -> 0.673), an order of magnitude above
the estimate's +\-3 deg spread.
An A1-only derivation (n=3) gives `axis (-0.7960, -0.6053, 0)`, `angle 26.80`,
`q_cmd` within `dot = 0.99989` of the pooled one - the constant does not depend on
which half of the corpus is used.

## 2. Phase 1 - which code site can actually set the achieved attitude

| candidate | verdict |
|---|---|
| `_grasp_quat` / `grasp_quat_override` (`tasks.py`, P62's channel) | **dead for the lift** - the never-stop catch releases it before the descent and installs its own top-down hold; P62 measured the override at -0.0018 / +0.0001 belt projection |
| `FRUIT_CARRY_HOLD_QUAT` (`tasks.py:3488`) | **live but not a pre-compensation**: it writes the **grip** quaternion (the attitude the pads froze at) and is off on this line - a different object |
| the hold the dynamic catch installs (`tasks._run_impl`, hover + coherent block) | **the command the lift inherits** - `_carry`'s clear is `name != "grasp_lift"`, so `grasp_lift` keeps it and every place leg clears it |
| **the leg's own hold** (`_carry`, at the `grasp_lift` leg's start) | **the site this phase writes** - and it is **live**: the treated legs read 42.4-57.9 deg (smoke + cell) against the control's 25.1-28.7 |

The implementation is the default-off knob `FRUIT_GRASP_LEFT_PRECOMP=1`
(`rl_env.resolve_carry_hold_override`, **direct + left only**): it passes
`carry_hold_override={"left": GRASP_LEFT_PRECOMP}` as a caller-owned kwarg (the
P58/P62 pattern; the environment is never written, `configs/` never edited) and
`tasks.carry_hold_override_for` writes `arm.hold_quaternion` for the
`grasp_lift` leg only. The **grip is still taken at the shipped attitude** (the
descent and close are untouched), so the P42/P61 seat geometry is unchanged; the
treatment is exactly one leg's attitude command. The armed run prints
`[grasp] left precomp: q_cmd=... axis=(-0.756380,-0.654132,+0.000000)
angle=26.798deg cmd_belt_proj=-0.3410 predicted_proj=+0.0000 ...`, and the
manifest records a `carry_hold_precomp` block (null = off).

`None` = the shipped path is **executed**, not asserted: `234` runs the real
`carry_hold_override_for` (extracted with `ast`, so no `pxr`/Isaac import) -
`None`, an empty dict, an unnamed side and every leg but `grasp_lift` return
`None` (no write at all), the armed one returns a copy; the same leg pins the
resolver's scope, the composition `q_drift^-1 (x) q_T0`, the row, the manifest
key and the untouched `configs/`. `scripts/selfcheck.sh` -> **PASS, 0 failures,
1 skipped** with the new leg.

## 3. Phase 1's gate smoke (not an arm of the cell)

`logs/p64/p2/S_77.log`, 4 episodes, seed 77, knob on, 183 s. **2 left legs, both
moved the wrong way**: achieved tool axis `(+0.3491, -0.5768, -0.7385)` and
`(+0.2905, -0.7008, -0.6515)` -> belt projection **+0.577 / +0.701** (tilt 42.4 /
49.3 deg) against the control's +0.32..+0.37; `hold_drift` **59.0 / 62.8 deg**
*from the new command*, so the command really was installed (had the hold been
T0 the drift would equal the tilt, 42.4 / 49.3). Both left legs cnp'd, with the
loaded slide starting at onset rows **37/39** (the control's sample: 97-127). The
smoke's own first line says `predicted_proj=+0.0000`; it measured **+0.58/+0.70**.
That gap is the phase's finding, and it was registered before the cell
(`logs/p64/PREREG_P2.md` section 4).

## 4. Phase 2 - the cell

3 seeds x 15 picks, both arms, one claim per run (`logs/p64/p2/P_{77,101,202}.log`,
`run_p2.sh`, 3/3 exit 0, no wedge, tree md5s identical before/after), the shipped
direct profile, `FRUIT_GRASP_LEFT_PRECOMP=1 FRUIT_CARRY_DIAG=1 FRUIT_ACQ_DIAG=1
FRUIT_CARRY_ATTITUDE=1`. Control = P63's cell (`logs/p63/p2/D_*.log`, same
scenario / checkpoint / seeds, knob unset; its `D_77.log` is byte-unchanged,
`b7e64e96`). All three runs carry the armed row once.

**E1 (mechanism) - FAIL.** The left `grasp_lift` achieved belt projection
(`[attitude] ... tool_axis`, end of leg):

| | n | achieved belt projection | achieved tilt |
|---|---|---|---|
| **treatment** | **16** | **median +0.673**, range **+0.042 .. +0.830** | median **47.0**, 32.5 .. 57.9 |
| control, tool-axis legs (P63 A1 + P62 pairs) | 7 | 0.354 [0.321 .. 0.366] | 26.8 [25.1 .. 28.7] |
| control, all 15 legs (`hold_drift` = the per-leg **max** tilt from T0, so an upper bound on the end-of-leg tilt) | 15 | - | 25.4 [22.4 .. 116.2] (116.2 = the never-held flail) |

**1 of 16** treated legs sits inside the `<= +0.10` bar - the never-held kiwi
(`P_202` ep 7), whose 41.0 deg tilt points **across** the belt (tool
`(+0.6545, -0.0417, -0.7549)`), i.e. a post-ejection flail and not a top-down
attitude. The `hold_drift` against the new command is **65.8 deg median
(50.5-107.4)**, against the control's 22.4-36.1 on its graded legs: the arm is
51-107 deg away from the attitude it is asked for.

**E1b - the post-loss confound, read and bounded.** The `[attitude]` line is one
read at the leg's end (P39), so on a leg that lost the payload the wrist is
already unloaded. That window is longer under the treatment (44-69 ticks, median
~61, against the control's 12-58) and the tilt correlates with it weakly
(**Spearman +0.37** over the 13 cnp legs). It is **not** the explanation: the one
left leg that **placed** - a clean under-load read at slip 2.9 mm - reads **tilt
48.4 deg / proj +0.701**, inside the treatment's distribution and far outside the
control's 25-29 deg. The unconfounded pre-loss read agrees: the loaded slide
starts at median onset row **60** (1-102) against the control's **104.5**
(1-136), so the payload starts walking **earlier** in the lift, not only after it
is gone.

**E2 (class) - not converted.** Exact counts (no rate claim, `AGENTS.md` 3b):

| arm | treatment | control |
|---|---|---|
| left | **1 placed / 13 cnp / 2 never-held (n=16)** | 2 / 11 / 2 (n=15) |
| right | **28 / 0 / 1 (n=29)** | 29 / 0 / 1 (n=30) |

Per seed, left placed/cnp/never-held: P_77 **0/3/1** (n=4), P_101 **0/5/0**
(n=5), P_202 **1/5/1** (n=7). The left's placement count falls 2 -> 1 while its
attempt count rises 15 -> 16; the cnp count rises 11 -> 13.

**E3 (scope) - unchanged in shape**: right 28/0/1 against 29/0/1, and the
right's own `hold_drift` median **24.0** (20.7-45.6) - the control's band.

**E4 (no-harm)**: the note keys are `intercept trigger` (both arms) plus
**`fruit fell off the line`** in the treatment, on one **right-arm** episode
(`P_77` ep 3, kiwi, x-tail class: the same key is in the P35/P38/P54 corpora,
not a P64 object and on the arm the knob does not touch). The knob-off acceptance
(`run_accept.sh`, every P64/P62/P43/P54/P58 knob unset): **377/377 `[fruit]`
lines identical** to `logs/p41/p2/accept_profile.log`, **`fingerprint: matches
configs/motion_reference.json`** (`8a399626`), `[stats]` 6/10, 15.0 s/attempt,
`diverted=0`; the gate FAILs on the rate only (60 % < the 75 % dynamic floor -
this tree's recorded count). This is the P38-M4/P43-style **import guard** and is
stated as such.

## 5. What this settles, and what it does not

**Settled.**

1. **The live site is `arm.hold_quaternion`** (the catch's inherited hold), and a
   pre-compensated hold written at the lift's start moves the achieved attitude.
   P62's dead channel is now separated from the live one by construction and by
   measurement.
2. **The inverse-response model is falsified.** Commanding the inverse of the
   measured drift does not land the achieved attitude at T0; it lands it
   **further downstream** (median projection +0.673 against +0.354), the arm
   settling 33-58 deg off vertical. E1 fails at the mechanism, the registered
   primary.
3. **A larger tilt does not convert the class** - and the held-slide starts
   earlier, the opposite of what a "more suitable pose" would buy.
4. The measured drift itself is a **tight constant** in direction and magnitude
   (7 legs, +\-3 deg azimuth), so the negative is about the *response*, not the
   estimate.
5. **The pose family is exhausted in the forms measured**: the world-z yaw family
   is IK-infeasible at the station and T0 is the one attitude that reaches
   projection 0 *and* solves (P62); the command is already T0 (P62); the
   residual's magnitude is arm-common and only its azimuth is left-specific
   (P63); and inverting it at the command is measured inverted (here). What is
   left is **structural**: the station's reach, or the arm/gripper hardware.

**Not shown.**

* **Any rate** (3 seeds of a rendered-frame loop; the counts are exact, the rates
  are not quotable, `AGENTS.md` section 3b).
* **Whether another sign or magnitude would work.** The two measured points
  (command 0 -> achieved +0.35; command -0.341 -> achieved +0.673) span a
  response whose slope is **negative** (~-0.76 by a two-point fit, not measured);
  a command in the **opposite** (downstream) direction is the only remaining
  candidate of this family. It needs its own pre-registration, and it is not
  obviously desirable: it would ask the wrist for a pose *further* from vertical,
  and the extrapolated zero-crossing sits at ~+35 deg of command tilt.
* **Whether the block hold responds the same way** (this cell writes the leg's
  hold only, so the grip is the shipped attitude).
* **Why** the achieved attitude moves opposite: the position/attitude trade is
  read from the numbers, not from a per-tick instrument. `ik_step`'s trace is the
  `AGENTS.md` section 2 instrumentation class (it changes the run) and needs its
  own pre-registration; the joint-limit margin at the lift's end is the named
  readout.
* Anything about the **right** arm's response: the knob is left-only by
  construction.

## 6. Reproduce / provenance

```bash
python3 logs/p64/p1/derive.py                       # -> logs/p64/p1/derive_out.txt
python3 scripts/234_p64_precomp_selftest.py         # the new selfcheck leg
bash logs/p64/p2/run_smoke.sh                       # phase-1 gate, 4 episodes, 183 s
bash logs/p64/p2/run_p2.sh                          # the cell, 3 claims, 3/3 exit 0
bash logs/p64/p2/run_accept.sh                      # E4: knob-off acceptance + gate
python3 logs/p64/p2_report.py --check               # -> logs/p64/p2_report.txt, 14/14 PASS
```

Pins: `tasks.py` **`7a8a163a`**, `rl_env.py` **`7c137553`**,
`scripts/234_p64_precomp_selftest.py` **`14cb3553`**, `scripts/selfcheck.sh`
**`caabfcbf`**, `logs/p64/PREREG_P2.md` **`281d6c40`**, `run_smoke.sh`
`c9944551`, `run_p2.sh` `c8674e39`, `run_accept.sh` `ad55178d`, `header.txt`
`b662e25b`, `S_77.log` `40cd9123`, `P_77.log` `dc5c01eb`, `P_101.log`
`d97262ef`, `P_202.log` `a98dc820`, `logs/p64/p2_report.py` `086109c3`,
`p2_report.txt` `956da8a9`, `accept_wall.log` `7fbf0186`, `motion_gate.txt`
`886e2c60`, `logs/p64/p1/derive.py` `6abfa271`, `derive_out.txt` `841a74dd`;
checkpoint `moe_v13s` `61da390a`; `configs/*` untouched (`waypoints.json`
`d81c6f1c`, `waypoints_oriented.json` `0ea08ebb`, `motion_reference.json`
`8a399626`, `motion_reference_twoline.json` `2246f83c`), **no reference
re-recorded**. `FRUIT_GRASP_LEFT_PRECOMP` is **default off** and `FRUIT_CARRY_DIAG`
/ `FRUIT_CARRY_ATTITUDE` / `FRUIT_ACQ_DIAG` stay default off.
**`logs/` is gitignored**, so `logs/p64/p2/{P_*,S_77}.log` are in the tree via
`git add -f` (`dbb5fc3`); this file, the `p2_report.py` close-out edits and the
post-commit `accept_wall.log` / `motion_gate.txt` / `p2_report.txt` still need
`git add -f`.
