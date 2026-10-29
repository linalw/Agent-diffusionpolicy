# P63 phase 2 — **the 26–29 deg is in the hold/IK, not in the command — and it is not what splits the class**

Written 2026-10-29 on HEAD `4d35449` + this tree's uncommitted P63 phase-1
instrument. **No shipped default changed** (the instrument is reporting-only and
`FRUIT_CARRY_DIAG` stays default off), **no `src/` byte edited by this phase, no
`configs/` byte moved, no commit**.

## Verdict

* **The registered decision reads (a) hold/IK.** On the `grasp_lift` legs the
  left's failing (`cnp`) attempts carry a **median `hold_drift` of 24.6 deg**
  (n = 11, range 22.4–29.4, p10/p90 22.4/29.1) — past the rule's 20 deg bar on
  all 11 legs — while the command they are failing to track is **T0**
  (belt projection **0.0000**, verified three independent ways below). The
  message is exactly P62's: **the command is right, the arm cannot hold it.**
* **The command path is not the mechanism, and the brief's (b) branch is closed
  by construction.** `tasks.py:3488` — the only line that would re-point the hold
  at an achieved attitude — is gated on `FRUIT_CARRY_HOLD_QUAT`, which is
  **unset** in this cell (and even armed it would write the *grip* quaternion,
  `self._grip_quat[side]`, i.e. the attitude the pads froze at, not the
  pre-pose's). The identity check reads the two candidate commands equal:
  `mirror_across_xz(top_down_quaternion("x"))` = `configs/waypoints.json`'s left
  grasp = `[+0, −0.707107, +0.707107, +0]`, **bit-identical**, projection 0.0000.
  And because the commanded attitude is vertical, `hold_drift` *is* the achieved
  tilt from vertical — the addendum's independent `[attitude] tilt` agrees with it
  to **≤ 4.6 deg** on 9/9 legs (a per-leg max vs an end-of-leg read).
* **The second finding decides how the phase may be read: the drift does not
  split placed from cnp.** The right places **29/30** of its `grasp_lift` legs at
  a **median drift of 25.8 deg** (range 20.9–52.3), i.e. the same distribution as
  the left's *failing* legs (24.6, 22.4–29.4); the left's own two placed legs read
  23.7 and **36.1** deg — the 36.1 sits at the **top** of the left's in-hand range
  (22.4–36.1). So
  the tilt is an **arm-common attitude-tracking residual**, and the cnp class is
  **not** a function of its magnitude (P3: in-hand Spearman −0.36 left / +0.20
  right / −0.15 pooled — no consistent sign).
* **What is arm-specific is the tilt's azimuth, and it is sign-consistent.** At
  the same magnitude the left's achieved tool axis is **downstream on 3/3** legs
  (tool_y −0.326…−0.366, 77 % of the tilt on the belt axis) while the right's is
  **downstream on 0/6** (3 upstream, 3 across; median share 0.23) — and P62's two
  seed pairs read the same way (left +0.321/+0.355, right −0.069/−0.278 in that
  file's sign convention = tool_y +0.069/+0.278). That is the residual this phase
  hands to phase 3; it is **not** a mechanism claim (§6 says why).
* **The instrument is clean**: **87/87** `[carry]` rows carry `hold_drift=`,
  **0/45** `grasp_lift` legs are `(no-hold)`, the 42 `(no-hold)` rows are exactly
  the **place** legs (13 left `place0` + 29 right `place1`), and the two angle
  instruments agree. F2 did not fire; F1 was not used (3/3 exit 0).

## 1. P1 — the instrument, and where the hold is cleared

Cell: **3 seeds × 15 picks**, one claim per run, the shipped direct profile
(`logs/p63/PREREG.md` §2 verbatim), logs `logs/p63/p2/D_{77,101,202}.log`,
driver `logs/p63/p2/run_p2.sh`, batch 15:51:35–16:30:08 (38 min 33 s),
**3/3 exit 0, no wedge**.

| read | value |
|---|---|
| episodes / `[carry]` rows | **45 / 87** (left 15 legs, right 30 legs on `grasp_lift`; 42 place legs) |
| rows carrying `hold_drift=` | **87/87** |
| `(no-hold)` rows | **42** = left `place0` ×13 + right `place1` ×29 (**all place legs**, 0 on `grasp_lift`) |
| `grasp_lift` legs with the hold live | **45/45** |
| `tasks.py` `arm.hold_quaternion = None` sites | **2218, 3466, 3927, 4386, 6732, 8439, 12465** |
| scenario echo | `trigger=arrival lead=0.90 lateral=0.160 acq=on(...)`, `park=back(default)`, `[supply] direct profile: cadence=on band=on(4) feed=on` |
| the diag actuated? | `guard=0 events=0 holds=0 reseat=0.0mm relief=0` on **87/87** |

The brief's four sites are this tree's **2218 / 3466 / 3927 / 4386** (the +9
offset after 3918 is P61's own `slip_xyz` block); **6732 / 8439 / 12465** are the
same statement's other three: the two-line station solve's temporary hold
(`6732`, cleared immediately), the pre-pose hold's clear before the descent
(`8439`, "the carry and the place poses are position-only"), and the re-lift
clear (`12465`). The one clear that could reach a `grasp_lift` leg is `:3466`
and it is **explicitly exempt for `grasp_lift`** (`name != "grasp_lift"`), which
is why the count is 0/45 — the mechanism read is confirmed by the field itself,
not assumed from the code.

## 2. The command, verified three ways — and the corollary that makes `hold_drift` the tilt

| way | read |
|---|---|
| offline identity (this report, pure python) | `mirror_across_xz(top_down_quaternion("x"))` = `[0, −0.707107, +0.707107, 0]` = `configs/waypoints.json`'s `grasp_quaternion.left` — **IDENTICAL** (dot = 1 − 1e-9); right = `top_down_quaternion("x")` = `[0, +0.707107, +0.707107, 0]` — **IDENTICAL**; both belt projection **0.0000** |
| the code (PREREG §3) | the dynamic catch installs it at `tasks.py:8476` (hover) / `:9294` (coherent block) and nothing clears it on `grasp_lift`; `FRUIT_CARRY_HOLD_QUAT` unset → `:3488` not taken |
| the runs (P62 §2) | the *armed* arm's `[grasp]` row reads `file_same=1 hold_same=1` — the override, the file's value and the installed hold are one array (and the override is the file's own value, so the identity holds armed or not) |
| **the measurement (this cell)** | `hold_drift` = the angle from T0, and `[attitude] tilt` (an independent read of the angle from world −Z) equals it to **≤ 4.6 deg** on 9/9 legs |

Consequence: **`hold_drift` on a live `grasp_lift` leg is the achieved tilt**, so
the numbers below are directly comparable to P62's belt projections (a 26.8–28.7
deg tilt is exactly what `[attitude]` prints, and the 0.32–0.37 belt component is
its projection).

## 3. P2 — the drift per arm and per outcome (primary)

Per `grasp_lift` leg, split by the **attempt's** outcome (`logs/p60/p3/report.py`'s
`outcome()`); the numbers are degrees:

| arm | outcome | n | median | range | p10 / p90 |
|---|---|---|---|---|---|
| **left** | **placed** | 2 | **29.9** | 23.7 – 36.1 | 24.9 / 34.9 |
| **left** | **cnp** | **11** | **24.6** | **22.4 – 29.4** | 22.4 / 29.1 |
| left | never-held | 2 | 82.0 | 47.8 – 116.2 | 54.6 / 109.4 |
| **right** | **placed** | **29** | **25.8** | **20.9 – 52.3** | 22.7 / 32.7 |
| right | cnp | 0 | — | — | — |
| right | never-held | 1 | 133.7 | — | — |

**The decision (registered rule).** The failing legs' median drift is **24.6 deg
on the left**, far past the 20 deg bar, with the hold live on all 11 → **(a)
hold/IK**. The rule's other branch is empty by construction (it needs drift
< 10 deg, which would mean the command *is* the achieved attitude; the command is
0.0000 and the achieved is 22–29 deg, a gap of 22–29 deg). **No verdict was
forced**: the right contributes **no cnp legs** in this cell (29/30 placed), so
the "both arms" clause is satisfied vacuously by the left-alone clause.

**The never-held legs are excluded from that reading, with their reason.** Their
drift (47.8 / 116.2 / 133.7 deg) is a **post-ejection flail**: all three read
`onset_row=1` and `clean_slip_max` 64 568–263 038 mm, i.e. the payload was gone on
the leg's first tick and the "drift" is the arm recovering from the ejection
(one of them, `S`-style, `force@onset=0.00 N`). They are printed in full in
`logs/p63/p2_report.txt` and are **not** evidence about tracking.

**The overlap is the finding.** Left-cnp 22.4–29.4 and right-placed 20.9–52.3
are the *same* band; the left's own placed legs bracket the cnp median from both
sides (23.7 below, 36.1 above). So on this cell the achieved-attitude error is
**necessary to be a problem at all** (it is present on every leg of both arms) but
**not sufficient** to produce a cnp: 29 of 30 right legs hold the payload at the
same 21–52 deg error. That is consistent with `logs/p42/SIM_LIMIT.md`'s closure
(the escape is a loaded slide of a drive-saturated pinch) and it means the
remaining lever is *which way* the error points, not *how big* it is (§5).

## 4. P3 — does the drift predict the slip?

`clean_slip_max` per leg vs its drift, Spearman rank correlation (a scatter
summary, not a fitted model). Escapes are `> 50 mm`; the **in-hand** subset
(`≤ 1000 mm`) drops the ejections, P61 amendment A3's convention.

| arm | n | Spearman (all) | n in-hand | Spearman (in-hand) | escapes |
|---|---|---|---|---|---|
| left | 15 | **+0.117** | 13 | **−0.360** | 11/15 |
| right | 30 | **+0.293** | 29 | **+0.201** | 1/30 |
| pooled | 45 | **+0.076** | 42 | **−0.147** | 12/45 |

**Sign is not even consistent across arms** (left −, right +, pooled −), and the
magnitudes are all far from 1: **the drift does not predict the slip**. The
sharpest single row is the left's **largest in-hand drift (36.1 deg) placing with
`clean_slip = 0.0 mm`** while its 22.4 deg leg escaped with 296.4 mm. So the
answer to the brief's P3 is: **no trend, n = 42 in-hand legs, sign unstable**.

## 5. P4 — the split, and the F3 comparison (report only)

| arm | placed | cnp | never-held | n |
|---|---|---|---|---|
| left | **2** | **11** | 2 | 15 |
| right | **29** | 0 | 1 | 30 |
| pooled | **31/45** | 11 | 3 | 45 |

Per seed: **77 → 12/15**, 101 → 9/15, 202 → 10/15. **No rate claim** (3 seeds of
a rendered-frame loop, `AGENTS.md` §3b); this is a branch, and the left/right mix
is the mechanism read (P60's 47× left rate reproduced: left 2/15 = 13 % vs right
29/30 = 97 %).

**F3 vs P61's cell** (same scenario, checkpoint, seeds; the tree differs only by
this reporting field):

| read | this cell | P61 |
|---|---|---|
| left placed / cnp / never-held | 2 / **11** / 2 (n=15) | 2 / **16** / 0 (n=18) |
| right placed / cnp / never-held | **29** / 0 / 1 (n=30) | **25** / 1 / 1 (n=27) |
| pooled placed | **31/45** | **27/45** |

The counts moved (the attempt counts themselves moved 18/27 → 15/30, so the
branches differ before any outcome is read) and one note key appears that P61's
cell lacks — `fruit did not follow the gripper` ×3. That key is a **recorded**
reason, not a novel one: P60's own cell prints it twice (`logs/p60/p3/D_77`,
`D_202`), it is the never-held class, and this cell has 3 never-held attempts.
Per the registered F3 clause this is **instrumentation-or-branch**: the diag adds
one `tcp_pose()` + one dot product per guarded tick (the `AGENTS.md` §2 class that
is outcome-moving at link-read granularity), the loop is not reproducible, and
**no delta is quoted from it** — P1–P3 read rows, not counts.

## 6. Addendum A1 — the azimuth of the same error (reporting only, one 10-episode run)

Not an arm of the cell: **one** 10-episode run, seed 77, with
`FRUIT_CARRY_ATTITUDE=1` added (one TCP-pose read per carry leg,
`tasks.py:3162-3225`, no per-tick work), log `logs/p63/p2/A1_77.log`, driver
`run_a1.sh`, same tree (md5s identical before/after, `tree_md5_after_a1.txt`).
It exists because `hold_drift` is the **total** angle: it cannot say whether the
error points along the belt, and the belt component is the one P61/P62 tie to the
slip. 18 `[attitude]` rows, 9 on `grasp_lift` legs:

| arm | n (cnp) | drift median | `[attitude] tilt` median | `\|tool_y\|` median | belt share of the tilt | azimuth |
|---|---|---|---|---|---|---|
| **left** | 3 (2) | 22.7 | 26.8 | **0.359** | **0.77** | **downstream 3/3** (−0.326…−0.366) |
| **right** | 6 (0) | 26.0 | 29.4 | 0.135 | 0.23 | downstream **0/6** (upstream 3, across 3) |

Per leg the left reads `tool_axis = (+0.27…+0.31, −0.33…−0.37, −0.88…−0.89)`, the
right `(+0.32…+0.51, −0.00…+0.35, −0.79…−0.89)`. **The magnitudes are the same
(26.8–29.4 vs 26.9–35.1 deg); the azimuth is not**: at 27–29 deg of tilt the
gravity component along the finger axis is `cos(27…29°) = 0.88–0.89` for *both*
arms, so a "more tilt" story cannot separate them, while the belt-pointed share
(0.77 vs 0.23) and its **sign** (downstream 3/3 vs 0/6, and P62's pairs agree)
do — and the left is the arm whose payload leaves downstream (P61: world −y on
14/14, the largest single component at 0.658).

**This is a consistency, not a mechanism.** Three left legs and six right legs is
a sample; the causal step from "the left's residual is belt-pointed" to "the
pinch loses the payload" is **not** measured here, and the pinch family is the
one `logs/p42/SIM_LIMIT.md` closes on force/seat grounds. What A1 buys is a
**specific, testable** phase-3 target: the left's residual direction, not its
size.

## 7. Pre-run predictions, scored

| id | prediction (PREREG §5) | outcome |
|---|---|---|
| **Pa** | 0 `(no-hold)` on `grasp_lift` | **✓ 0/45** (42 place legs only) |
| **Pb** | left drift median ≥ 20 (predicted 24–30) | **✓ 24.6** (cnp) / 29.9 (placed) |
| **Pc** | right median **8–25**, smaller than the left's | **✗ 25.8** (20.9–52.3) — my premise was wrong: the right's *belt projection* is smaller, its **total** tilt is not. This is the phase's most useful correction to P62's framing |
| **Pd** | no linear drift→slip prediction (\|rho\| < 0.6 pooled) | **✓ 0.076 pooled, −0.147 in-hand, sign unstable across arms** |
| **Pe** | the class split reproduces P61's shape | **✓** left cnp-majority / right placed-majority; counts moved (F3) |

## 8. What this settles, and what it does not

**Settled.** (a) The 26–29 deg **is** the hold/IK: the command is T0 (0.0000 belt
projection, three independent confirmations), the hold is live on every
`grasp_lift` leg, and the achieved wrist sits **20.9–52.3 deg** away from it — on
**both** arms and on **placing** legs as much as failing ones. (b) The
`FRUIT_CARRY_HOLD_QUAT` channel (`tasks.py:3488`) is **not** what sets the lift's
attitude, and even armed it writes the grip quaternion, not the pre-pose's — the
brief's "command path" branch does not exist on this line. (c) The drift
**magnitude is not the class discriminator** (29/30 right legs place at the same
error), so any adoption argument built on "stiffen the hold and the cnp falls"
must first explain why the right already places at 21–52 deg. (d) The tilt's
**azimuth** is arm-specific and sign-consistent (left downstream 3/3 + P62 2/2;
right downstream 0/6 + P62 0/2). (e) `hold_drift` agrees with the independent
`[attitude]` read to ≤ 4.6 deg, so the instrument is trustworthy for phase 3.

**Not shown.** (i) Whether a **stiffer hold or a re-solved grasp seed** (P62 §5
items 1–2) would reduce either arm's residual — untested; that family costs a
`configs/` change (both motion references re-recorded, P41's rule) or a per-tick
`ik_step` change (the `AGENTS.md` §2 instrumentation class), each needing its own
pre-registration. (ii) Whether the **downstream azimuth is causal** for the cnp —
A1 is n = 3 left legs and the mechanism step is exactly what `SIM_LIMIT.md`
closes on other grounds. (iii) Any **rate**: 3 × 15 on a rendered-frame loop is
one branch per seed, and the counts moved between this cell and P61's (§5). (iv)
The right's cnp behaviour — it produced **no** cnp legs, so its "failure"
distribution is unmeasured here. (v) `hold_drift` is a **per-leg max**, so it
does not say *when* the peak occurs within the lift (the `[attitude]` agreement
suggests late, within ~5 deg, but the timing is not resolved).

## 9. Reproduce / provenance

```bash
bash logs/p63/p2/run_p2.sh            # the registered cell, 3 claims, 38 min 33 s, 3/3 exit 0
bash logs/p63/p2/run_a1.sh            # addendum A1 (reporting only), 1 claim, 11 min 20 s
python3 logs/p63/p2_report.py --check # -> logs/p63/p2_report.txt, 15/15 checks PASS (exit 0)
```

`p2_report.py` prints P1 (field presence, the code sites, the scenario echo), the
command identity, P2 (per-arm × outcome + every leg), the decision, P3 (Spearman
+ escapes), P4 (split, note keys, F3), and A1 (per-leg azimuth); `--check`
re-asserts 15 invariants — every `[carry]` row carrying the field, every drift a
finite angle, every leg's side matching its episode's arm, P60's `parse_leg`
reading all 87 rows, the T0 identity, **0 `(no-hold)` on `grasp_lift`**, every
`(no-hold)` row being a place leg, the two angle instruments agreeing ≤ 6 deg,
the tree md5s identical before/after the batch, and every log carrying its
rollout summary.

**No-harm:** the scripted line is untouched by construction (this phase edited no
`src/` file, no `configs/` file and no `scripts/` file; `tasks.py` `1d27566c` and
`rl_env.py` `6ec023c7` are phase 1's, and the batch's own `tree_md5_before.txt`
== `tree_md5_after.txt` == `tree_md5_after_a1.txt`).

Pins: `logs/p63/PREREG.md` **e09e8250**, `logs/p63/p2/run_p2.sh` **27fc0c1b**,
`run_a1.sh` **80e27c64**, `header.txt` **205f2922**, `D_77.log` **b7e64e96**,
`D_101.log` **e302c361**, `D_202.log` **251ee648**, `A1_77.log` **446d2ef1**,
`logs/p63/p2_report.py` **a1ee28f0**, `logs/p63/p2_report.txt` **3646e070**;
`tasks.py` **1d27566c** (phase 1's instrument), `rl_env.py` **6ec023c7**
(`TASKS_MD5` follow), `fruits.py` `c7461d41`, `control.py` `9384ff4f`,
`scene.py` `27e3d64a`, `policy/trigger.py` `b09d3cb2`,
`scripts/233_p63_attitude_selftest.py` **1146173e**; checkpoint `moe_v13s`
**61da390a**; `configs/*` untouched (`waypoints.json` `d81c6f1c`,
`arm_parks.json` `42ab4fb7`, `motion_reference.json` `8a399626`,
`motion_reference_twoline.json` `2246f83c`).
`FRUIT_CARRY_DIAG` / `FRUIT_CARRY_ATTITUDE` stay default **off**, no new knob was
added, and no default was flipped.
**`logs/` is gitignored**, so this directory needs `git add -f` at the close-out.
