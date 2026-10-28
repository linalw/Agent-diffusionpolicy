# P56 PREREG amendment A1 — the implementation's two deviations and P6's bar

Written **after** the implementation's smoke and **before** the claimed battery
(`logs/p56/p2/P2_header.txt`: `rl_env.py` `cfbce71d` is the tree every recorded
run used). The endpoints, arms, N and pass bars of `PREREG.md` are **unchanged**;
this file records where the implementation had to leave the design's literal
wording, and what the measurement then showed about one bar's calibration.

## A1.1 The reduced per-pick setup (DESIGN §1 A.1 row 7, "partly")

`PREREG` P1's ladder (same-arm **50** ticks, arm-switch **80**) is only reachable
if the continuation also drops the *redundant* teleports, and DESIGN A.1 row 7
says exactly that ("the active arm to `grasp` is mandatory; the inactive-arm park
only when the arm switches"). DESIGN §3.2 step 2 phrases `_begin_pick` as "rows 4
and 6-17", which keeps row 7 in full.

**Both were implemented and measured, in that order:**

| form | gap | where |
|---|---|---|
| the literal split (full 3 x `teleport_joints` + settle) | **110 ticks** = 3x30 + 20, on both a same-arm and a switch transition | `logs/p56/p0/C3_literal_split.log` (a temporary build with only the two skips reverted; the shipped file was restored, `rl_env.py` `1845c2c4`) |
| row 7's "partly": active arm straight to `grasp`, inactive parked only on a switch | **50 / 80** | `logs/p56/p0/C5.log`, `logs/p56/p2/B_1.log` |

The reduced form is **continuation-only**; the shipped per-episode reset is
byte-identical (the deterministic `--ablate scripted` pair is 44/44 lines
identical, `logs/p56/p0/base_{before,after}.sh`). It is the form the battery ran.

## A1.2 The starvation contract (DESIGN §3.2 step 3)

The design says: on `select_target() is None`, append a note and end the episode.
Implemented literally, a 3-pick smoke ended at **pick 3** with the belt holding
fruit (`logs/p56/p0/C3_norec.log`: `no candidate on the belt; ending the episode`,
and its recorder certificate holds 2 rows / 2 npz, not 3), because the direct selector's floor (~0.399 m) leaves a 5 cm
catchable sliver inside the line-full interlock's queue window
(`[pick_y-0.05, pick_y+0.45]`, `FRUIT_QUEUE_MAX=6`).

Replaced by **the reset's own bound**: a failed round is 30 ticks of belt travel,
the reset allows 40 of them, and the same bound ends the episode mid-episode.
Each round is printed (`[cont] pick k/n: waiting for a candidate (round r/40)`),
so F4's quantity (the starved share of picks) is counted rather than inferred, and
a starved round shows up in P1's gap (it is +30 ticks). This is the only change
that makes the *scenario* measurable; it is not a change to an endpoint.

## A1.3 P6's bar is below what the shipped line attains (measured, not amended)

P6's bar is `|q - grasp|_max <= 0.011 rad` on >= 95 % of picks, taken from the
demonstrations' frame-0 statistic (`rl_env.py:2303-2306`). The **shipped**
per-episode reset attains it on **1/15 picks** (`logs/p56/p2/A_1.log`: median
0.0114, max 0.0147), because `teleport_joints(settle=30)` re-bases the drive onto
the measured state and lands a few mrad short of its command (the P35 phase-2
Gate-1 P0 note: the shipped `ready` reset sits 0.027-0.038 rad from *its* command).

So the bar measures the *teleport's settle residual*, not the continuation's
distribution, and it cannot pass on any arm. The verdict is nevertheless taken
**as registered** (P6 FAIL), and the registered *purpose* - "the continuation
reproduced the per-episode loop's start state" - is read as the A-vs-B contrast on
the same arm. A re-registration would set the bar on the shipped residual
(>= 95 % within the A-arm maximum, with the outliers named), and add the per-joint
dump the 0.0330 rad event needs.
