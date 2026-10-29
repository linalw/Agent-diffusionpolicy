# P62 phase 1 — the left grasp-attitude candidates, and what the left arm can actually do with them

**Status: measurement only.** No `src/`/`configs/` edit, no default change, no policy
run. The candidates live here until phase 2. Written 2026-10-29 on HEAD `21690c3` +
the P61 instrument (`tasks.py` `9a5e0459`).

**The question (owner, 2026-10-29).** "左臂需要换姿势就尝试换；单纯右臂镜像可能不适合这个
动态场景；为左臂选择更适合左臂的抓取姿势" — try a pose change for the left arm; a plain
mirror of the right may not suit this dynamic scenario.

**The measured asymmetry it starts from (P61).** The left's payload leaves **out
along the finger axis**: leg-frame mean unit `(-0.351, +0.240, +0.905)`, **25.2°**
from the tool axis vs **48.9°** from the belt. The two arms' tool axes have
**opposite** belt projections (**+0.513** left / **−0.513** right,
`logs/p61/P2_RESULTS.md` §2), so on the left the belt's drag has a **positive**
component along the axis the payload escapes along, and on the right it is
negative. On a never-stop catch that is the only arm-differential mechanism the
direction data supports.

**The answer in one line.** The **world-z yaw family is infeasible** at the left's
station (it removes the projection *and* the reach, monotonically, measured); the
only attitude that reaches projection **0.000** *and* solves is the reach
harness's own **top-down** attitude (fingers straight down, jaws exactly across
the belt, projection 0.000 by construction) — at the cost of a **0.007 rad** joint
margin at j3 and a worse `+x` cliff.

---

## 1. The shipped attitude, verified

`configs/waypoints_oriented.json` → `grasp_quaternion.left`
`[w, x, y, z] = (+0.184162, +0.709672, −0.193123, +0.652038)` (unit norm 1.0).

The order is `[w, x, y, z]`, and it is load-bearing: `tasks.py::_grasp_quat` returns
this array straight into `ArmController.hold_quaternion`, `control.py::ik_step` feeds
it to `quaternion_error` ("quaternions are (w, x, y, z)"), and `capture_hold_pose`
writes `tcp_pose()`'s orientation back in the same order. A `[x, y, z, w]` reading
would be a different attitude entirely — `candidates.py` and the probe both use
`(w, x, y, z)` throughout.

Rotation matrix `R` (columns = the TCP frame's axes in the world):

| | x | y | z |
|---|---|---|---|
| **col 0** | +0.0751 | −0.0339 | **+0.9966** |
| **col 1** | −0.5143 | −0.8576 | +0.0095 |
| **col 2** | **+0.8543** | **−0.5132** | −0.0819 |

* **Tool axis** (`col 2`) = `(+0.8543, −0.5132, −0.0819)`.
* **World-belt projection** = `tool · (0, −1, 0)` = **+0.5132**. The belt runs toward
  **−y**: `fruits.py:1429` sets the conveyor's surface velocity to
  `[0, cfg.belt_speed, 0]` with a negative `belt_speed` (the build prints
  `surface velocity -0.12 m/s`).
* **Slip share on the tool axis** = `P61's mean world unit slip · tool` =
  `(+0.623, −0.658, −0.422) · tool` = **+0.9045**, against P61's published
  **0.905**. That equality is the check that this file and P61's decomposition are
  the same frame (the probe re-asserts it, `IK_PROBE.txt` P3).

**The frame, measured rather than assumed** (`IK_PROBE.txt`, checks P2a/P2b — the
left arm at the calibrated seed):

* `approach_axis` (`tcp − jaw_centre`, 78.0 mm) = `(+0.854, −0.512, −0.095)`;
  `|dot|` with cols 0/1/2 = **0.000 / 0.000 / 1.000** → **col 2 is the finger long
  axis**, exactly as P61 assumed.
* `jaw_axis` (right pad − left pad, 98.0 mm apart) = `(+0.513, +0.858, −0.020)`;
  `|dot|` with cols 0/1/2 = **0.000 / 1.000 / 0.000** → **col 1 is the jaw-opening
  axis** (its own belt projection is **0.858**, i.e. the jaws sit 31.0° off the
  belt, not the 90° the `_grasp_quat` comment aspires to).
* col 0 is 4.7° off world **+Z**: the frame's "up".

So the shipped grasp holds the fingers **nearly horizontal** (5.4° below the
horizontal), reaching out across the belt and downstream, with the pads 31° off
the belt line and the jaw centre 102.6 mm above the belt at the calibrated seed.
The belt's push therefore has a **+0.513** component **along the finger axis** —
toward the fingertip side, which is the direction P61 measured the payload leaving
in (25.2° from that axis).

## 2. Which family can change that projection at all

Three families were computed exactly (`logs/p62/candidates.py`, output in
`logs/p62/candidates.json`). The discriminating fact is elementary but it decides
the brief's question:

| family | definition | projection | verticality |
|---|---|---|---|
| **F1 yaw about world z** (the brief's "yaw") | `q' = q_z(θ) ⊗ q` (world-frame pre-multiplication) | **changes**, +0.5132 → 0.0000 at θ = **30.9951°** → −0.5132 at θ = **61.9901°** | **exactly preserved**: a world-z rotation leaves every column's z-component unchanged (verified to 1e-12), so the finger's droop, the pads' relation to the vertical and the jaw axis' levelling cannot change (jaw_z stays **0.010**, i.e. 0.5° out of horizontal, for every θ). It is a rotation about the **palm's up axis** (col 0, 4.7° off world z), so it sweeps the finger's *azimuth* while every axis keeps its height. |
| **F2 roll about the frame's z column** (the brief's "roll") | `q' = q ⊗ q_z(φ)` (body-frame post-multiplication) | **cannot change**: measured deltas `0.0e+00` and `−1.1e−16` at φ = 45°/90° — a rotation about an axis fixes that axis, so its projection is invariant by construction | the fingers stay put but the **jaw axis tips out of the horizontal plane**: col 1's height goes 0.5° → **44.3°** (φ = 45°) → **85.3°** (φ = 90°), i.e. *one pad above the other* — exactly the v1 failure `configs/waypoints_oriented.json`'s `note` records ("jaws opened along [0.35,0.33,0.88] (one finger above the other), so it could never close on a fruit resting on the belt"). Not a usable knob, and **it cannot be the lever for this mechanism** regardless. |
| **F3 rotation about world y** (the belt axis) | `q' = q_y(φ) ⊗ q` | **cannot change**: the projection *is* the y component and a rotation preserves its own axis (delta exactly 0 at 15°, 60°) | 15° already tilts col 0 to 19.4° off vertical |
| (for completeness) rotation about **world x** | `q_x(φ) ⊗ q` | zero only at **+80.94°**, and there the finger axis ends **31.5° below horizontal**, still 0.854 across the belt — not a top-down attitude | unusable |
| (for completeness) roll about the **jaw axis** (col 1) | `q ⊗ q_y(φ)` | changes it (+0.3869 at φ = 45°) | but col 0 goes to **40.3°** off vertical — the same "tilt the fingers" class, excluded on the top-down ground, not on invariance |

**So: the yaw about world z is the only family that changes the projection while
preserving the attitude's relation to the vertical** — which is exactly what makes
it the right *shape* of lever, and the reason the next section's negative is about
the arm, not about the attitude's geometry.

## 3. The candidate table

`q` is normalised and printed in the file's `[w, x, y, z]` order; `proj` is the new
tool axis' world-belt projection; `slip.sh` is the **predicted** share of P61's
measured slip along the new tool axis (`u · t'`, `u` = the mean world unit slip);
`drag` is the full frame's belt triple `(col0·b, col1·b, col2·b)` — C0's
`(+0.034, +0.858, +0.513)` reproduces P61's published drag reference exactly.

| cand | family | dθ | quaternion `[w,x,y,z]` | tool axis (col 2) | proj | slip.sh | drag |
|---|---|---|---|---|---|---|---|
| **C0** | shipped (control) | 0 | `+0.184162, +0.709672, −0.193123, +0.652038` | `+0.8543, −0.5132, −0.0819` | **+0.5132** | **0.9045** | +0.034, +0.858, +0.513 |
| **Y15** | F1 | +15.50° | `+0.094566, +0.729230, −0.095675, +0.670915` | `+0.9604, −0.2663, −0.0819` | +0.2663 | 0.8081 | +0.013, +0.964, +0.266 |
| **Y21** | F1 | +21.70° | `+0.058151, +0.733337, −0.056105, +0.675047` | `+0.9835, −0.1610, −0.0819` | +0.1610 | 0.7533 | +0.004, +0.987, +0.161 |
| **Y31** | F1 | +31.00° | `+0.003243, +0.735471, +0.003521, +0.677539` | `+0.9966, 0.0000, −0.0819` | **0.0000** | 0.6555 | −0.010, 1.000, 0.000 |
| **Y46** | F1 | +46.49° | `−0.088138, +0.728281, +0.102652, +0.671789` | `+0.9604, +0.2663, −0.0819` | −0.2663 | 0.4577 | −0.031, 0.963, −0.266 |
| **Y62** | F1 | +61.99° | `−0.177911, +0.707790, +0.199908, +0.653772` | `+0.8543, +0.5132, −0.0819` | **−0.5132** | 0.2291 | −0.050, 0.857, −0.513 |
| **T0** | harness top-down | 0 | `+0.000000, −0.707107, +0.707107, +0.000000` | `0.0000, 0.0000, −1.0000` | **0.0000** | 0.4220 | +1.000, 0.000, 0.000 |
| Z45 | F2 | 0 | `−0.079381, +0.581746, −0.450002, +0.672880` | `+0.8543, −0.5132, −0.0819` | +0.5132 | 0.9045 | +0.630, +0.582, +0.513 |
| Z90 | F2 | 0 | `−0.330839, +0.365255, −0.638372, +0.591283` | `+0.8543, −0.5132, −0.0819` | +0.5132 | 0.9045 | +0.858, −0.034, +0.513 |
| J45 | jaw-axis roll | 0 | `+0.244048, +0.406127, −0.107947, +0.873984` | `+0.6572, −0.3869, +0.6468` | +0.3869 | 0.3911 | −0.339, +0.858, +0.387 |

**Derivation.** Let `t = R[:, 2]`, `b = (0, −1, 0)`. Then `proj(θ) = −(t_x sin θ +
t_y cos θ)`; setting it to zero gives `tan θ = −t_y / t_x = 0.5132 / 0.8543`, i.e.
**θ = 30.9951°** (Newton-polished; the projection there is **4.9e−17**), and
projecting to `−proj(0)` doubles it: **θ = 61.9901°** (projection **−0.5132357**,
the shipped one to 7 dp), whose tool axis is the right arm's own to **0.00°** (and
whose jaw axis is within **1.10°** of the right's — the residual 1.1° is the
z-component, which a rotation cannot mirror). Two consequences follow: (a) the
mirror-sign regime is literally "the left adopts the right's TCP attitude", and
(b) the two roots sit **31.0°** and **62.0°** from the shipped attitude — i.e.
**any** yaw that removes the projection is a ≥31° wrist re-orientation.

**What the prediction means, and its limit.** `slip.sh` uses P61's *measured* world
direction (n = 14 in-hand slides) and re-projects it onto the candidate's tool axis;
C0 reproduces 0.9045 vs P61's 0.905, so the arithmetic is the same decomposition.
The limit: the world direction was measured **at the shipped attitude**, and the
prediction assumes an attitude change does not move where the payload goes. That is
the hypothesis phase 2 tests; the *mechanical* half of the prediction (the belt's
drag projection `proj`, which is what pushes the payload toward the fingertip side)
is exact and assumption-free.

## 4. The IK/reach verdict (`IK_PROBE.txt`, 13/13 checks PASS)

Harness: the `scripts/174_station_reach.py` recipe (same scene parts, same left arm,
same `teleport_joints(grasp)` + `hold_quaternion` + `solve_to(jaw centre at
(x, pick_y, belt_top + 0.09), iterations=400, tolerance=6 mm)`), x at the left's
**delivered** band (`logs/p60/LEFT_CENSUS.md`: p50 0.274, station 0.340, max 0.398;
the never-held band is x 0.347-0.398). Claim `logs/p62/ik_probe.log`, cross-check
`logs/p62/ik_probe_restarts.log` (4 restarts).

**Control validated first.** The shipped quaternion reproduces the documented
station band: **5.9 / 5.7 mm** at x = 0.274 / 0.340 (inside the 6 mm catch-up
tolerance) and **8.3 mm** at 0.398 (the +x cliff), with a 1.5-2.0° attitude error and
a **+0.204..+0.377 rad** j2 margin. The descent baseline this is compared against is
`logs/161_accept_endmetric.log`'s **`end=` 42.1-88.1 mm** shortfall (the documented
40-90 mm): the pads' static belt clearance at the shipped attitude is
**+30.2..+49.0 mm**.

| cand | proj | solved ≤6 mm | res p50 | res stn | res 0.398 | attitude err | joint margin | pads above belt |
|---|---|---|---|---|---|---|---|---|
| **C0** | +0.513 | 2/3 | 5.9 | 5.7 | 8.3 | 1.5° | **+0.299 rad** (j2) | **+30.2 mm** |
| Y15 | +0.266 | **0/3** | 10.6 | 9.2 | 9.2 | 8.3° | +0.182 (j2) | +20.2 |
| Y21 | +0.161 | **0/3** | 13.6 | 11.9 | 11.7 | 10.3° | +0.129 (j2) | +14.5 |
| Y31 | 0.000 | **0/3** | 19.2 | 19.8 | 19.9 | 13.9° | +0.087 (j2) | **+3.0** |
| Y46 | −0.266 | **0/3** | 41.7 | 45.4 | 48.9 | 12.2° | +0.001 (j2, limit) | **−13.1** |
| Y62 | −0.513 | **0/3** | 56.3 | 118.0 | 104.9 | 55.4° | −0.000 (j2, limit) | **−14.2** |
| **T0** | **0.000** | **2/3** | **6.0** | **5.8** | 32.8 | **0.8°** | **+0.007 rad** (j3) | **+59.6** |

* The **yaw family never solves**: the residual grows monotonically with θ
  (10.6 → 13.6 → 19.9 → 48.9 → 118.0 mm), the wrist attitude error with it
  (8.3 → 55.4°), the binding j2 margin collapses (0.182 → 0.087 → 0.001 → 0.000),
  and the pads fall toward and then **through** the belt top (+20.2 → +3.0 →
  −14.2 mm). At 31° — the first yaw that removes the projection — the pads are
  **3 mm** above the belt and the solve is 3x the tolerance. **The left's station
  reach is azimuth-limited**, which is the same constraint `motion.py` already
  records from the other side: the *un-mirrored* top-down made the left's solver
  drift into a near-horizontal tool, so the left is the arm that must be given the
  mirrored attitude — and T0 below is exactly that mirrored attitude, solved here
  from the shipped seed.
* **T0 is the exception**, and it is not a yaw: it reaches projection **0.000** by
  pointing the fingers straight down (col 2 = `(0,0,−1)`) with the jaws **exactly
  across** the belt (90.0° vs the shipped 31.0°). It solves at the control's own
  residual (6.0 / 5.8 mm), with a **0.8°** attitude error and pads **+14.7..+25.7 mm
  higher** than the control's — so the descent's documented shortfall is **not
  worsened** by its pad geometry, it is given margin.
* **T0's two costs are measured and must travel with any cell.** (i) The binding
  margin is **+0.007 rad at j3** — the arm is at its *configuration* limit (a
  different joint from the yaw family's j2), and it reads the same with
  `FRUIT_P62_RESTARTS=4`, so it is the attitude at this station and **not** a seed
  artefact. (ii) At the +x cliff (0.398) it reads **32.8 mm / 17.0°** against the
  control's 8.3 / 2.0, i.e. it makes the `never-held` tail **worse**, and that tail
  is 4/62 of the left's failures (P60 §5).

**Two caveats on the harness.** `scripts/174`/`183` load `configs/waypoints.json`
whose left `grasp` seed is **1.21 rad** away from `waypoints_oriented.json`'s (a
different calibration), so their published 2.1 mm is a different seed *and* the
top-down attitude; this probe uses the **shipped** seed (the one the catch's reset
teleports to, `rl_env.py:2575`) with the shipped quaternion as its control. And
`solve_to` is a position solve holding an attitude target, so "solved" here means
*the arm can present the pads at the station in that attitude*, not that the
dynamic catch with that attitude has been run — phase 2's job.

## 5. Recommendation for the cell

**Run T0** (`+0.000000, −0.707107, +0.707107, +0.000000`, fingers straight down,
jaws across the belt) as the left-only, direct-scoped attitude, because it is the
only candidate that (a) zeroes the mechanism variable exactly, (b) solves at the
left's p50 and station with the control's own residual and a 10x smaller attitude
error, (c) *increases* the pads' belt clearance by 15-26 mm (the descent's 40-90 mm
shortfall cannot worsen from the pad geometry), (d) puts the jaws **exactly** across
the belt instead of 31° off it, and (e) is not the right's mirror — it is a
genuinely different attitude from the right arm's (100.7° away; the right keeps the
shipped one).

Its roll about the finger axis is a **free parameter for phase 2**: with col 2
vertical every roll preserves `proj == 0` exactly, so the pads' azimuth can be
placed without touching the mechanism variable — the one degree of freedom the yaw
family never had.

What phase 2 must carry, all measured here:

1. **The j3 margin (+0.007 rad)** is a standing risk at the station: a joint that is
   0.4° from its limit has no headroom for the catch's downstream sweep. Phase 2
   should record `FRUIT_ACQ_DIAG`'s joint-limit margin and the never-held count, and
   treat a `never-held` rise as this, not as the attitude's mechanism.
2. **The +x cliff** (32.8 mm at 0.398) is the acquisition cost: the never-held class
   (4/62) will move before the carry class does. Pre-register the split.
3. **A new seed** for the attitude (the shipped `arms.left.grasp` was calibrated for
   the shipped quaternion; the probe solved *from* it, so a feasible configuration
   exists, but the config's seed should be re-solved and pinned).
4. **Scope**: direct only, left only — the scripted line and the two-line must stay
   byte-identical, so the quaternion has to be selected per presentation, not edited
   in the file (no `configs/` change in this phase).
5. **References**: if the scripted line is untouched by construction, no motion
   reference moves; prove it rather than assume it (the P38-M4 / P43 pattern).

**If the mechanism is the target and not the count**, Y15 (projection +0.266, a 48 %
reduction) is the nearest *feasible-ish* yaw on the residual scale (10.6 mm, 1.8x
tolerance) — but it is outside the 6 mm catch-up tolerance that P47/P48 measured as
the acquisition line (8/8 no-grasp above it), so it is **not** recommended for a
cell; it is listed only so the next reader does not re-derive it.

## 6. Reproduce

```bash
python3 logs/p62/candidates.py                  # the exact table + candidates.json
scripts/180_claim_slot.sh logs/p62/ik_probe.log \
  FRUIT_P62_CANDIDATES=C0,Y15,Y21,Y31,Y46,Y62,T0 \
  scripts/run.sh logs/p62/ik_probe.py           # 36 lines, ~1 min 50 s wall
python3 logs/p62/ik_report.py                   # -> logs/p62/IK_PROBE.txt, 13/13 PASS
```

Provenance: `candidates.py` `2df434b6`, `candidates.json` `2ddcb9a9`, `ik_probe.py`
`abf0b00b`, `ik_probe_rows.json` `c41688c7`, `ik_probe.log` `2f199afa`,
`ik_probe_restarts.log` `eeb2d9e8`, `ik_report.py` (this run's md5 in
`IK_PROBE.txt`); intermediate runs kept for provenance: `ik_probe_far.log` /
`ik_probe_rows_far.json` (Y46/Y62 alone) and `ik_probe_rows_near.json` (the
restarts=4 cross-check). Inputs: `configs/waypoints_oriented.json`,
`configs/finger_pads.json`, `logs/p61/P2_RESULTS.md`, `logs/p60/LEFT_CENSUS.md`,
`logs/161_accept_endmetric.log`. No `src/`/`configs/` change; `git status` is clean
apart from this directory (and the pre-existing `logs/p36/offline_obs_diff.txt`).
**`logs/` is gitignored** (`.gitignore:7`), so these files need `git add -f` at the
close-out, like every other phase's evidence.
