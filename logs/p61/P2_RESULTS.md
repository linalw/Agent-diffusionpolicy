# P61 phase 2 — the left arm's slip in **world** terms: belt-leaning mixed, on a tool-axis slide; the lift motion does not differ

**Why the world frame is the primary read.** `slip_xyz` is the payload's
displacement in the **leg (TCP) frame** at the tick of the maximum, and that frame
is **arm-specific**: `R_right = M R_left Mᵀ`, `M = diag(−1,+1,−1)` (max element
error **0.0**), so the left's hand +y and the right's hand +y are **61.9° apart in
the world** — both sit 0.858 on world −y, but their x/z components are negated. A
per-arm leg-frame "+y" comparison is therefore invalid; every row below is mapped
to the world with `R_arm = quaternion_matrix(grasp_quaternion[side])`, and the
arms are compared there (**belt = world −y**).

*This supersedes the first version of this file, which led with the leg-frame
components and called the belt hypothesis "refuted" on a leg-frame share that
actually measures the **jaw-opening** axis, not the belt. §3.2 states the
correction.*

## Verdict

* **P1 (instrument) — valid.** 88/88 `[carry]` rows carry `slip_xyz`; max
  `||slip_xyz| − clean_slip_max|` = **0.072 mm**, **0** rows above 0.1 mm and
  **0** above the 0.15 mm print bound → no F1.
* **P2 (the direction, left, n = 14 in-hand slides) — belt-leaning, but not
  belt-dominant, and the closest single direction is the tool axis.**
  **World dominant axis: y 4 / x 2 / z 0 / mixed 8 (of 14)**;
  **signed mean world-y −150.9 mm** (median −160.2, range −341.3…−38.9,
  **negative on 14/14**); mean world vector **(+123.2, −150.9, −81.7) mm**; mean
  unit direction **(+0.623, −0.658, −0.422)** → **belt −y 0.658** is the largest
  single world component, then **+x 0.623** (across the belt), then **−z 0.422**
  (down). In the leg frame the same mean is (−0.351, +0.240, **+0.905**), i.e.
  **25.2° from the tool axis** (the finger length), 48.9° from the belt −y, 51.5°
  from +x, 65.0° from −z and **76.1° from the jaw-opening axis**. So: the payload
  leaves **out along the pads' length toward the distal end**, sagging down, and
  the belt direction is the largest *world projection* because that same tool
  axis points 59° downstream.
  *A pure belt drag would print leg-frame shares (+0.034, **+0.858**, +0.513);
  observed: (−0.351, **+0.240**, **+0.905**).*
* **The right arm cannot be contrasted on this cell (registered contingency).**
  27 attempts, **1** escaping leg: world **(+112.1, +224.8, −213.2) mm**, i.e.
  **world-y +224.8 mm — upstream, the opposite sign** to the left's 14/14. One
  leg is not a distribution; it is quoted as an anecdote.
* **P3 (lift motion) — no difference.** Both arms run the same commanded profile
  (`|v|cmd` 0.293) and the achieved `|v|max` is **0.987x** the right's (0.312 vs
  0.316 m/s). The `|a|max` **1.637x** is the **escape tick**: on the *placed*
  lifts the left reads 3.170 m/s² against 2.196, and the left's all-legs maximum
  (15.98) sits on a cnp attempt. **The IK/dynamics-asymmetry candidate is not
  supported.**
* **P4 — one new note key** (`fruit left the pick station during the close
  (25 279 mm)`, a right-arm depenetration kick, `S_77` ep2): "no new failure
  reason" fails on the letter; not a carry/grip object. Split **27/45**
  (left 2/16/0, right 25/1/1).
* **P5 — the row format still parses**: 88/88 rows through
  `logs/p60/p3/report.py`'s `parse_leg`, `clean_slip` equal on all 88;
  `logs/w8/B_metric.py` reads trace JSON, untouched.

## 1. The cell (P1)

3 seeds × 15 picks, one claim per run, the shipped direct profile, `moe_v13s`
`61da390a`, `FRUIT_CARRY_DIAG=1` + `FRUIT_MOTION_REPORT=1` only. Logs
`logs/p61/p2/S_{77,101,202}.log`; driver `logs/p61/p2/run_p2.sh`; batch
**10:38:27–11:06:43** (28 min 16 s), **3/3 exit 0, no wedge** (F2 unused). The
scenario is P60 phase 3's cell verbatim, so `logs/p60/p3/D_*` is the F3 foot.

| read | value |
|---|---|
| episodes / `[carry]` rows | 45 / **88** (left 36, right 52) |
| rows carrying `slip_xyz` | **88/88** |
| **P1** max `abs(|slip_xyz| − clean_slip_max)` | **0.072 mm** (worst `S_202` ep7 place0, 1386.1 mm) |
| rows > 0.1 mm (the letter) / > 0.15 mm (the bound) | **0 / 0** → no F1 |
| the diag actuated? | no — `guard=0 events=0 holds=0 reseat=0.0mm relief=0` on 88/88 |
| scenario echo | `trigger=arrival lead=0.90 lateral=0.160 acq=on`, `park=back(default)`, `[supply] direct profile: cadence=on(default) band=on(4)(default) feed=on(default)` |

The three-component print allows a worst case of `√3·0.05 + 0.05 = 0.137 mm`;
the observed maximum is 0.072.

## 2. The mapping, and its approximation

`slip_xyz` is `R(t)ᵀ(fruit − pads)` differenced against the leg's own first tick
(`rel_frame − guard_ref`), so it is a **leg-frame** vector. World:

```
v_world = R_arm @ slip_xyz        R_arm = quaternion_matrix(grasp_quaternion[side])
                                  (configs/waypoints_oriented.json)
```

`R_arm` is orthonormal, so the **magnitude is unchanged** by the mapping and only
the axis labels move.

**This is an approximation, and it is stated as one.** `grasp_quaternion` is the
calibrated **grasp** attitude; the carry releases the attitude hold
(`tasks.py:8398`, "the carry and the place poses are position-only") and the
**achieved** attitude is not logged in this cell (`FRUIT_CARRY_ATTITUDE` is not in
the env). Two things bound the error: the leg of interest is `grasp_lift`, which
starts from the calibrated grasp pose; and the concentration statistic (mean
pairwise cosine of the 14 unit vectors) is **+0.872** (per seed 0.888 / 0.918 /
0.780), i.e. the vectors are coherent in one frame rather than smeared — so a
large attitude drift, which would scatter them, is not present. What cannot be
excluded is a *systematic* few-degree offset; every direction below is therefore
quoted with its angle to the nearest candidate, and the conclusion only uses
separations of 25° or more.

The arms' relation, and why the leg frame is not comparable across them:

| | left (world) | right (world) | note |
|---|---|---|---|
| hand x | (+0.075, −0.034, +0.997) | (+0.075, +0.034, +0.997) | ≈ world **+Z** (up) |
| **hand y** | (−0.514, −0.858, +0.010) | (+0.514, −0.858, −0.010) | **61.9° apart**; both 0.858 on world −y |
| hand z (tool axis) | (+0.854, −0.513, −0.082) | (+0.854, +0.513, −0.082) | ≈ across the belt, 59° off world −y |

World → leg-frame map (what each world direction would print):

| world direction | left leg frame | right leg frame |
|---|---|---|
| belt **−y** | (+0.034, **+0.858**, +0.513) | (−0.034, **+0.858**, −0.513) |
| down **−z** | (**−0.997**, −0.010, +0.082) | (**−0.997**, +0.010, +0.082) |
| across belt **+x** | (+0.075, −0.514, **+0.854**) | (+0.075, +0.514, **+0.854**) |

## 3. P2 — the direction

Escape = `clean_slip_max > 50 mm`; unit = the attempt's first `grasp_lift` leg in
`(50, 1000] mm` (amendment A3, §3.4). **Every left escape is
`seated_then_slid` (14/14)**, `force@onset` 6.6–15.0 N (median 10.0),
`contacts@onset` 1 on 8 / 2 on 6, `force_min = 0` **14/14** — P60's signature
reproduced on a third corpus.

### 3.1 The world read (primary)

| read (left, n = 14) | value |
|---|---|
| **world dominant axis** | **y 4**, x 2, z 0, **mixed 8** (mixed(x>y) 3, mixed(x>z) 2, mixed(y>x) 2, mixed(z>x) 1) |
| **signed mean world-y** | **−150.9 mm** (median −160.2, range −341.3…−38.9); **y<0 on 14/14** |
| mean world vector | **(+123.2, −150.9, −81.7) mm** (magnitude ≈ 211 mm) |
| mean world unit direction | **(+0.623, −0.658, −0.422)** |
| axis shares | **belt −y +0.658** · +x +0.623 · −z +0.422 |
| per-leg sign | x>0 **13/14**, y<0 **14/14**, z<0 **14/14** |
| concentration | +0.872 |

**Per leg** (leg-frame vector, then the world vector in mm and the world unit):

| seed | ep | arm | fruit | slip mm | leg frame (mm) | world (mm) | world dom | world unit |
|---|---|---|---|---|---|---|---|---|
| 77 | 0 | L | pear | 105.5 | (−71.8, +2.0, +77.2) | (+59.5, −38.9, −77.9) | mixed(z>x) | (+0.565, −0.369, −0.738) |
| 77 | 8 | L | kiwi | 257.4 | (−70.8, +110.5, +221.5) | (+127.1, −206.0, −87.6) | **y** | (+0.494, −0.800, −0.340) |
| 77 | 10 | L | peach | 142.2 | (−83.2, −3.1, +115.3) | (+93.9, −53.7, −92.4) | mixed(x>z) | (+0.660, −0.378, −0.650) |
| 77 | 11 | L | pear | 267.7 | (−46.4, +20.6, +262.8) | (+210.4, −151.0, −67.6) | mixed(x>y) | (+0.786, −0.564, −0.252) |
| 101 | 0 | L | apple | 266.1 | (−77.6, +51.4, +249.3) | (+180.7, −169.4, −97.3) | mixed(x>y) | (+0.679, −0.637, −0.365) |
| 101 | 2 | **R** | tomato | 329.5 | (−196.4, −133.1, +228.6) | (+112.1, **+224.8**, −213.2) | mixed(y>z) | (+0.340, +0.682, −0.647) |
| 101 | 5 | L | kiwi | 200.6 | (−7.0, −18.6, +199.6) | (+179.6, −86.3, −23.5) | **x** | (+0.895, −0.430, −0.117) |
| 101 | 6 | L | kiwi | 278.3 | (−12.8, +92.3, +262.3) | (+175.7, −213.3, −33.3) | mixed(y>x) | (+0.631, −0.766, −0.120) |
| 101 | 7 | L | kiwi | 271.8 | (−47.2, +82.5, +254.6) | (+171.5, −199.8, −67.1) | mixed(y>x) | (+0.631, −0.735, −0.247) |
| 101 | 10 | L | pear | 245.2 | (−112.0, +115.2, +185.3) | (+90.7, −190.1, −125.7) | **y** | (+0.370, −0.775, −0.512) |
| 101 | 14 | L | apple | 264.1 | (−60.5, +136.5, +217.9) | (+111.4, −226.8, −76.8) | **y** | (+0.422, −0.859, −0.291) |
| 202 | 4 | L | peach | 189.3 | (−78.9, −9.4, +171.8) | (+145.7, −77.4, −92.8) | **x** | (+0.770, −0.409, −0.490) |
| 202 | 7 | L | peach | 179.2 | (−63.5, +22.7, +166.0) | (+125.4, −102.5, −76.7) | mixed(x>y) | (+0.700, −0.572, −0.428) |
| 202 | 8 | L | pear | 126.3 | (−66.2, +4.1, +107.5) | (+84.8, −56.4, −74.7) | mixed(x>z) | (+0.671, −0.447, −0.592) |
| 202 | 12 | L | apple | 374.1 | (−140.4, +307.2, +160.9) | (−31.1, −341.3, −150.2) | **y** | (−0.083, −0.912, −0.401) |

**Stable across seeds** (world mean unit direction): 77 (+0.626, −0.528, −0.495) ·
101 (+0.605, −0.700, −0.275) · 202 (+0.514, −0.585, −0.478); 14/14 legs
downstream-sign in each. The **larger the slip the more downstream it points**
(Spearman **−0.73** between `clean_slip_max` and the world-y of the unit vector,
n = 14); the largest slip (374 mm) is the most belt-aligned leg (−0.912).

### 3.2 The mechanism decomposition (leg frame; arm-specific, so mechanism only)

| read (left, n = 14) | value |
|---|---|
| leg-frame dominant axis | **z 11**, mixed(z>x) 2, y 1 |
| components (mm) | x **−68.5** [−140.4, −7.0] · y **+37.0** [−18.6, +307.2] · z **+192.4** [+77.2, +262.8] |
| mean unit direction | **(−0.351, +0.240, +0.905)** |
| shares | **tool axis +0.905** · jaw opening axis +0.240 · hand x (down) −0.351 |

Angle from the mean to each candidate: **tool axis 25.2°** · belt −y 48.9° ·
across +x 51.5° · down −z 65.0° · **jaw opening axis 76.1°**. So the payload is
**not** moving through the pinch (where friction would resist); it moves **out
along the pads' length, toward the distal end** (positive leg-z; the wrist sits
at `−down·wrist_back`, so +z is the fingertip side), with a consistent downward
sag (hand x negative on 14/14) and a real downstream drift.

**The correction this file carries.** The first version argued "the belt-aligned
axis carries only 0.240 where a drag would put 0.858". **That conflated two
different axes**: 0.240 is the share along the **jaw-opening** axis, which is
only 30° from the belt; the belt direction itself is **world −y** and its share is
**0.658**. The correct drag test is the leg-frame triple a pure belt drag would
print, (+0.034, **+0.858**, +0.513), against the observed (−0.351, **+0.240**,
**+0.905**): the pinch axis is far *below* a drag's share and the tool axis far
*above* it. So the belt contributes (0.658 of the world projection, unanimous
sign) but it is **not** the mechanism.

### 3.3 The right arm — no measurable contrast

27 attempts, **1** escaping attempt (tomato, 329.5 mm), **mixed(y>z)**, world
**(+112.1, +224.8, −213.2) mm** — signed world-y **+224.8 mm**, i.e. **upstream**,
the opposite of the left's 14/14. With n = 1 this is an anecdote, not a
difference; the arm contrast the brief asked for is **unmeasurable on this cell**
(PREREG §4's registered contingency), because the right arm places 25/27 and
therefore has almost no escapes to read.

### 3.4 What the distribution contains (amendment A3)

The registered rule ("first escaping leg > 50 mm") selects **16** left attempts;
**14** are in-hand slides. Dropped, and printed in full in `logs/p61/p2_report.txt`:

* **`S_202` ep3, `grasp_lift`, 49 596.8 mm** — `onset_row=1`, `sep@onset=98.3 mm`
  (pads already at their open stop), `force@onset=27.73 N`,
  `in-hand_vmax=9.208 m/s`: a **close-time ejection**, not a slide (its `place0`
  reads 126 532.6 mm — a teleport);
* **`S_101` ep12, `place0`, 696.2 mm** — held through the lift, lost in the
  transfer, so the vector mixes the arm's travel with the slip.

Because the ejection is 49.6 m, the **registered set's** leg-frame mean y is
**−2 446.5 mm** against the slide set's **+65.3 mm**: the raw mean is one
ejection's artefact, and both are printed. The **13** further left `place0` rows
at **1 095–1 444 mm** (all `contacts@onset = 0`), the two place0 teleports and
the right's one `place1` (158.7 mm) are the downstream view of a payload already
gone — the metric then measures the hand's own 0.5–0.6 m transfer.

## 4. P3 — the motion contrast

From the `[motion] carry grasp_lift:` rows, attributed by the enclosing episode's
`arm=` (the achieved numbers are those after `recoveries=`, **not** the payload's
`in-hand |v|max`; the legacy `slip_max` is excluded as frame-contaminated):

| arm | legs | `|v|max` m/s | `|a|max` m/s² | `|v|cmd` | `|a|cmd` | re-seats |
|---|---|---|---|---|---|---|
| left, all | 18 | **0.312** [0.288–0.593] | **3.676** [1.492–15.977] | 0.293 | 0.683 | 0 |
| left, placed | 2 | 0.311 [0.307–0.315] | 3.170 [2.567–3.773] | 0.293 | 0.677 | 0 |
| right, all | 26 | **0.316** [0.289–0.416] | **2.245** [1.071–9.286] | 0.293 | 0.665 | 0 |
| right, placed | 25 | 0.316 [0.289–0.416] | 2.196 [1.071–9.286] | 0.293 | 0.665 | 0 |

Median ratios L/R: **`|v|max` 0.987x**, **`|a|max` 1.637x**. The a-ratio is the
escape tick, not the carry (the left's three largest `|a|max` legs — 15.98, 14.29,
11.85 — are all cnp attempts, and the 0.593 m/s speed too). **No IK/dynamics
asymmetry is measurable** — with the caveat that only 2 left lifts placed here.

## 5. P4 — the split (report only) and a new note key

| arm | placed | cnp | never-held | n |
|---|---|---|---|---|
| left | **2** | **16** | 0 | 18 |
| right | **25** | 1 | 1 | 27 |
| pooled | **27/45** | 17 | 1 | 45 |

Per seed, pooled placed: **10/15** (77), **7/15** (101), **10/15** (202); the left
delivered 2, 0, 0 of its 6, 7, 5 attempts. P60's cell read **24/45**
(left 1/19/1, right 23/0/1).

**"No new failure reason" fails on the letter, by one episode.**
`113_rl_report.py`'s digit-normalised keys gain
`fruit left the pick station during the close (# mm)` — **`S_77` ep2**, a
right-arm apple, **25 279 mm cross-belt**: a depenetration kick at the close (the
`logs/p41` canary's class), the attempt never grasped, and 25 m is not a
carry/grip object. The cell also lacks P60's `fruit did not follow the gripper`
(2 rows, the never-held class). No rate claim: the direct loop conditions on
rendered frames.

## 6. P5 — the row format still parses

`logs/p60/p3/report.py`'s `parse_leg` reads **88/88** new rows with every field it
names, `clean_slip` equal to the printed value on all 88, and `slip_xyz` ignored
by it (no `_RE_FIELD` key can match inside the new token; it sits between
`clean_slip_max=` and `in-hand_vmax=`, so both bracketing patterns still anchor).
`logs/w8/B_metric.py` reads **trace-JSON** rows (`hand_rel` …), which this change
does not touch; its `clean_slip` is the quantity the new vector gives the
direction of.

## 7. F3 — the counts vs P60's cell (instrumentation-or-branch)

left **2/16/0 (18)** vs **1/19/1 (21)**; right **25/1/1 (27)** vs **23/0/1 (24)**;
pooled **27/45** vs **24/45**; one new note key (§5). The diag adds one
`tcp_pose()` + one tactile read per carry tick — the per-tick-link-read class
`AGENTS.md` §2 records as outcome-moving — and the direct loop is not
reproducible, so this is **instrumentation-or-branch**, used for no delta. It
does not touch P1/P2/P3, which read rows, not counts.

## 8. What this settles, and what it does not

**Settled.** In **world** terms the left's escape is a **diagonal with a real
belt component**: world −y is the largest single component (0.658) with its sign
on **14/14** legs and a mean of **−150.9 mm**, +x is next (0.623) and −z third
(0.422) — but **no axis dominates per leg** (8/14 mixed, y-dominant only 4/14,
x 2/14). In the **leg frame** the same displacement is 25.2° from the **tool
axis** and 76.1° from the jaw-opening axis, i.e. the payload **slides out along
the pads' length toward the distal end** (with a downward sag), and the belt
direction is large in world terms *because that axis points 59° downstream*. The
**IK/dynamics-asymmetry** candidate is refuted: identical commands, 0.987x
achieved speed, a-excess only on the loss ticks. P60's class is reproduced on a
third corpus (14/14 `seated_then_slid`, `force_min = 0` 14/14).

**The one structural fact worth handing on (not a lever).** The axis the payload
leaves along **is** the finger's long axis: leg-frame z is the finger link's local
+Z toward the fingertip (`scene.py:544-547`, `e_long`), the `84.9 mm` "long/down"
extent whose **distal plane** P39's `FRUIT_FINGER_TIP_DELTA` moves
(`distal 80.5 → 76.5 mm` at `−4 mm`). The direction is therefore *consistent with*
a distal-engagement story, but the only measured form is **−4 mm** against
**126–374 mm** of slip (1–3 % of the slip scale) and it measured **negative**;
the authorized **24–45 mm** hardware magnitude (P30-C) has never been tested and
stays **owner-gated** (P39 A1.7). This phase names the axis; it reopens nothing.

**Not shown.** (a) **Arm vs lane vs grade** stays confounded (`grade A → bin 0 →
left`) — this is the direction of *left+bin0+grade-A* escapes; and the **right
arm has 1 escape**, so the requested cross-arm contrast is unmeasurable here
rather than negative. (b) The **world mapping is a grasp-frame approximation**
(§2): the achieved carry attitude is not logged, no systematic-offset bound
exists, and the reading is quoted with its angles so only ≥25° separations carry
the conclusion. (c) The direction is read **at the maximum only** — one vector
per leg, no trajectory. (d) `force@onset` remains a single-tick sample. (e) The
belt and the jaw-opening axis are 30° apart, so "dragged by the belt" and "slid
through the pinch" differ mainly in *share*; both are quantified here.

## 9. Reproduce / provenance

```bash
bash logs/p61/p2/run_p2.sh            # 3 claims, 28 min 16 s, no wedge
python3 logs/p61/p2_report.py --check # -> logs/p61/p2_report.txt, 14/14 checks PASS
```

`p2_report.py` prints, per arm, the **world** block first (dominant axis, signed
mean world-y, mean world vector, axis shares) and the leg-frame **mechanism**
block second, with the belt-drag reference triple; then the per-leg exclusions,
the motion table, the split, the note keys and the format check. `--check`
re-asserts 14 invariants, including every `[carry]` row carrying `slip_xyz`, no
row beyond the 0.15 mm print bound, the P60 parser reading every new row, and the
tree md5s identical before and after the batch.

**No-harm:** `scripts/selfcheck.sh` **PASS, 0 failures** (incl. the
`P61 slip direction` leg, `scripts/231_p61_slip_selftest.py` **202b40c7**);
`logs/p61/p2/tree_md5_before.txt` == `tree_md5_after.txt`.

Pins: `logs/p61/PREREG.md` **f0771339**, `logs/p61/PREREG_AMENDMENTS.md`
**3fc15dc7** (A1 frame names, A3 in-hand-slide scope), `logs/p61/p2/run_p2.sh`
**43318260**, `logs/p61/p2_report.py` **b01aec3a**, `logs/p61/p2_report.txt`
**c548993e**; `S_77.log` **0b80e475**, `S_101.log` **a0e902fa**, `S_202.log`
**4d4a4e9f**, `header.txt` **52265e35**; tree HEAD **ab2fe7c** + the uncommitted
instrument (`tasks.py` **9a5e0459**, `rl_env.py` **e19295f5** = the `TASKS_MD5`
follow, `scripts/231_p61_slip_selftest.py` **202b40c7**, `scripts/selfcheck.sh`
**ebbceab0**); checkpoint `moe_v13s` **61da390a**; `configs/*` untouched
(`8a399626` / `2246f83c` / `0ea08ebb`). **No default change, no `src/`/`configs/`
edit by this phase, no commit.** `FRUIT_CARRY_DIAG` and `FRUIT_MOTION_REPORT` stay
default **off**.
