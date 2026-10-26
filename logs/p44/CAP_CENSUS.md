# P44 phase 1 — CAP_CENSUS: every cap that limits how fast this cell moves

Measured **offline** 2026-10-27 (no simulator, no `src/` edit, no commit).
Tree: HEAD **`ca99148`** (P43 close), `tasks.py` **`a1b3d673`**, `control.py`
**`9384ff4f`**, `motion.py` **`7f2443c1`**, `scene.py` `27e3d64a`,
`kinematic_gripper.py` `e40b1ca2`, `actuated_gripper.py` `6345c7cb`,
`assets/openarm_flat/openarm_flat_deinst.usda` **`5018b31f`**;
`configs/motion_reference.json` `8a399626`, `..._twoline.json` `2246f83c`.

Reproduce every number below with

```bash
python3 logs/p44/cap_census.py --write     # ~1 s, reads the USD + logs only
```

`logs/p44/CAP_CENSUS_out.txt` is the run of record (289 lines). The script prints
(A) the drives and the cap register, (B) measured ticks vs the modelled profile
per leg, (C) the `[cycle]` decomposition, (D) the fixed clocks, (E) the headroom,
(F) the joint-limit margins, (G) the following error, (H) the candidate list.

**Four reading rules, the same ones the ledgers obey:**

1. **A leg's duration is its profile's tick count, not the servo's speed.** The
   motion model reproduces **every** measured leg within **±1.4 %** (§2.3), so a
   "faster" change means *changing a cap*, not tuning the drive.
2. **Two cap classes.** A *clock cap* (a profile length or a fixed tick budget)
   fixes the duration and the drive can only change how well the leg tracks
   inside it. A *convergence cap* (a `move_to` loop's tolerance under `tau`) sets
   the duration directly — only the hover and the return are in this class.
3. **A success count is one draw of an attractor.** No rate is compared across
   configurations here; the per-leg and per-phase numbers are.
4. **The two-line's `s/attempt` is not a cycle time** (it is a batch span over two
   concurrent arms). Compare `placed/min` or the per-arm phase means.

---

## 1. The arm servo

### 1.1 The authored drive (verified)

`assets/openarm_flat/openarm_flat_deinst.usda` authors the arm drives **per
degree**; Isaac reads them back **per radian** (`×57.29578`), verified at runtime
by `scripts/16_gains_probe.py` → `logs/164_gains_probe.log`
(`k=22918.312 c=4583.663` on all seven joints of both arms). **The P30-B comment
in `AGENTS.md` is correct.**

| joint | USD line | stiffness [deg-units] | **k [N·m/rad]** | **c [N·m·s/rad]** | **tau = c/k** | `maxForce` | sat. error | `maxJointVelocity` | range [deg] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| j1 | 3630 | 400 | 22918.3 | 4583.7 | **0.200 s** | 40 N·m | 1.75 mrad | 959.97 deg/s = **16.75 rad/s** | −200..80 (L) / −80..200 (R) |
| j2 | 3654 | 400 | 22918.3 | 4583.7 | 0.200 s | 40 N·m | 1.75 mrad | 16.75 rad/s | −190..10 / −10..190 |
| j3 | 3678 | 400 | 22918.3 | 4583.7 | 0.200 s | 27 N·m | 1.18 mrad | 311.99 deg/s = **5.45 rad/s** | ±90 |
| j4 | 3702 | 400 | 22918.3 | 4583.7 | 0.200 s | 27 N·m | 1.18 mrad | 5.45 rad/s | 0..140 |
| j5 | 3726 | 400 | 22918.3 | 4583.7 | 0.200 s | 7 N·m | 0.31 mrad | 1199.99 deg/s = **20.94 rad/s** | ±90 |
| j6 | 3750 | 400 | 22918.3 | 4583.7 | 0.200 s | 7 N·m | 0.31 mrad | 20.94 rad/s | ±45 |
| j7 | 3774 | 400 | 22918.3 | 4583.7 | 0.200 s | 7 N·m | 0.31 mrad | 20.94 rad/s | ±90 |
| finger j1 | 3798 | 1 000 000 N/m | — | 100 N·s/m | — | 10 N | 0.010 mm | 1.0 m/s | 0..44 mm |
| finger j2 | 3822 | (mimic) | — | — | — | **none** (drive-less) | — | — | −8.8..52.8 mm |

`sat. err` = `maxForce / k`: the joint error at which the drive stops being a
spring. **The measured 8.1–10.4 mm tool lag is ~30 mrad at a ~0.3 m lever, i.e.
17–97× past saturation — so on every real leg the arm drive is a *torque source*,
not a stiffness.** That is why `sat. err` is not a speed number and why the gains
(§1.2) are not a rate lever.

The finger pair matters for the grip but not for speed: authored 1e6/100 delivers
**~2.2 N per face** at 120 Hz; the shipped P41 profile is **k=1e5, c=2000**
(`c/k = 0.02`) and delivers **9.75–9.9 N**, i.e. 50 % of the two-face 20 N the
caps could apply (`control.py:234-236`, `logs/p41/P2_RESULTS.md`).

### 1.2 The gain knobs

| knob | default | site | what it does |
| --- | --- | --- | --- |
| `FRUIT_TUNE_GAINS` | **`"0"`** | `control.py:214` | `=1` → `set_dof_gains(k, c, dof_indices=arm_dofs)` |
| `FRUIT_ARM_STIFFNESS` | **1500** | `control.py:215` | only read when `TUNE_GAINS=1` |
| `FRUIT_ARM_DAMPING` | **60** | `control.py:216` | only read when `TUNE_GAINS=1`; tau = 0.040 s |
| finger profile | k=1e5, c=2000 | `control.py:234-236` | `FRUIT_FINGER_STIFFNESS=0` restores the asset's 1e6/100 |
| `FRUIT_FINGER_MAXFORCE` | unset | `control.py:242-256` | raises the 10 N cap; **not adopted** (P41) |

`set_dof_gains` is called in exactly two places: `control.py:217` (arm, opt-in)
and `control.py:236` (fingers, always). **No script or shell driver in the tree
sets `FRUIT_TUNE_GAINS`**, so the *shipped* arm drive is the asset's own
k=22918 / c=4583 (tau 0.200 s) and the tuned pair is an experiment.

Measured: the tuned pair is **null on the descent's arrival** — `logs/165` (soft
gains) reads 36–98 mm against the control corpus's 42–88 mm (`logs/161`) — and
its earlier A/B was judged on the approach's *acceleration* (`logs/375/376`),
which is inconclusive. Its only untested effect is on the two *convergence*
blocks (§5).

### 1.3 Do the joint velocity / effort limits bind? No.

At the shipped levers (nominal open-arm link offsets — an order-of-magnitude
check, not a kinematic solve) the fastest reference the profile ever asks for is
**0.373 m/s** (an *indexed* `place1` under the 0.38 m/s `FRUIT_CARRY_VMAX`; the
shipped **dynamic** line's fastest is **0.343 m/s**, a place `|v|cmd`):

| joint | `vlim` [rad/s] | lever [m] | tip speed at `vlim` | × the 0.38 m/s cap | `Fmax` [N·m] | `I` [kg·m²] | `F/I` [rad/s²] | needed by 2.31 m/s² |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| j1 | 16.75 | 0.500 | 8.38 m/s | 22.0× | 40 | 0.6143 | 65 | 4.6 |
| j2 | 16.75 | 0.440 | 7.37 | 19.4× | 40 | 0.5508 | 73 | 5.3 |
| j3 | 5.45 | 0.300 | 1.63 | 4.3× | 27 | 0.5397 | 50 | 7.7 |
| j4 | 5.45 | 0.154 | 0.84 | **2.2×** | 27 | 0.3559 | 76 | 15.0 |
| j5 | 20.94 | 0.0955 | 2.00 | 5.3× | 7 | 0.1182 | 59 | 24.2 |
| j6 | 20.94 | 0.1205 | 2.52 | 6.6× | 7 | 0.0413 | 169 | 19.2 |
| j7 | 20.94 | 0.0375 | 0.79 | **2.1×** | 7 | 0.0070 | 1001 | 61.6 |

**Tightest velocity margin 2.1×; tightest effort margin 2.4× (j5, the thin
wrist).** No joint velocity or effort limit is reachable at the shipped caps — the
"lock" the owner asked about is **not** in the joint limits.

---

## 2. The motion profile

### 2.1 The reference

`motion.py::TrajectoryLimits` + `jerk_limited()`: a time-scaled minimum-jerk
quintic whose duration is the largest of three implied durations, ×1.02, rounded
up to whole ticks (`motion.py:192-242`):

```
duration = max( 1.875·d/v_max ,  sqrt(5.774·d/a_max) ,  (60·d/j_max)^(1/3) ) × 1.02
```

so the profile is C2, reaches `d` exactly, and respects all three bounds by
construction. Shipped defaults (`motion.py:174-176`): **`v_max = 0.38 m/s`
(`FRUIT_CARRY_VMAX`), `a_max = 2.0 m/s²` (`FRUIT_CARRY_AMAX`), `j_max = 25 m/s³`
(`FRUIT_CARRY_JMAX`)**, `dt = 1/120 s`.

### 2.2 The per-leg caps, with their sites

| leg | speed cap | accel cap | jerk cap | site | which term binds |
| --- | --- | --- | --- | --- | --- |
| **dynamic `grasp_lift`** (shipped line) | **0.30** (`FRUIT_DYNAMIC_LIFT_VMAX`) | **1.0** | min(25, 10) = 10 | `tasks.py:3399,3402` + cone | **v_max** (t_v 1.33 s vs t_a 1.11 vs t_j 1.05) |
| indexed/policy `grasp_lift` | 0.18 (`FRUIT_LIFT_VMAX`) | 1.0 | 10 | `tasks.py:3379,3380` | **v_max** (2.85 s) |
| **dynamic `place0/1`** | **0.35** (`FRUIT_DYNAMIC_PLACE_VMAX`) | **1.089** (`..._AMAX`) | min(25, 10.89) = 10.89 | `tasks.py:3424,3427` | **v_max** (3.0 s) |
| indexed `place0/1` | 0.38 (from `FRUIT_CARRY_VMAX`) | 2.0 | min(25, 20) = 20 | `motion.py:174-176` (no per-leg cap) | v_max (2.43 s) |
| **release drop** (`place low`) | **0.30** (`FRUIT_PLACE_LOW_VMAX`) | **1.962** (`..._AMAX` 2.0, cone-clipped) | 19.62 | `tasks.py:12191-12193` | *the only leg the cone clips* (−2 %) |
| **dynamic descent** (`approach`) | **0.15** (`FRUIT_DYNAMIC_APPROACH_VMAX`) | **0.8** (`FRUIT_APPROACH_AMAX`) | 25 (no cone: it carries nothing) | `tasks.py:5937,9352-9354` | **v_max** (0.71 s) |
| indexed handover descent | 0.03 (`FRUIT_APPROACH_VMAX`) | 0.8 | 25 | `tasks.py:13083,13107` | **v_max** (3.56 s) |

The lift and the place are **not** min()'d against the indexed caps — the dynamic
values are authoritative (`tasks.py:3382-3402`), which is why the `v×1.25` column
in §4.3 moves at all.

### 2.3 The cap *is* the leg: measured vs modelled

Ticks = the number of times the leg steps the sim, and the leg steps once per
profile sample. `CAP_CENSUS_out.txt` §B, per log and leg:

| leg (shipped single arm, `accept_profile.log`) | n | d [cm] | ticks | model | Δ |
| --- | --- | --- | --- | --- | --- |
| `grasp_lift` | 10 | 21.6 | 168.0 | 166.5 | **+0.9 %** |
| `place0` | 5 | 57.6 | 378.4 | 379.0 | −0.2 % |
| `place1` | 5 | 37.4 | 245.8 | 246.6 | −0.3 % |
| `approach` | 10 | 5.7 | 89.9 | 89.0 | +1.0 % |
| indexed `grasp_lift` (`16_accept_indexed_v7`) | 10 | 27.4 | 350.8 | 351.1 | −0.1 % |
| indexed `approach` | 10 | 5.6 | 427.9 | 429.2 | −0.3 % |

Worst error over the whole corpus: **±1.4 %** (`twoline_profile.log` approach).
`ref/cap` = the profile's own peak ÷ the cap it was given = **0.96–0.98** on every
leg: the cap, not the servo, sets the length.

### 2.4 The friction cone — and what it actually caps

While a payload is held, `tasks.py:3429-3430` (and `:12193-12196` for the release
drop) clips the acceleration to

```
a_max(u) = g · ( sqrt(u_z² + mu_eff² − 1) − u_z )      [m/s²],   mu_eff = FRUIT_MU_SAFETY × gripper.mu
mu_eff   = 0.6 × 2.0 = 1.2      (FRUIT_MU_SAFETY × FRUIT_GRIPPER_MU, both shipped)
then:    a_max = min(a_max, budget);  j_max = min(j_max, max(10·a_max, 1));  v_max = min(v_max, 2·a_max)
```

(`motion.py:125-140`, `:180-189` — `accel_budget` / `limited_by_cone`.)

| direction | `accel_budget` at `mu_eff` 1.2 | at 0.45 | the leg's own `a_max` | cone binds? |
| --- | --- | --- | --- | --- |
| lift, +z | **1.962** | 0.000 | 1.0 | no — 51 % of the budget |
| place, horizontal+rise | **4.273** | 0.000 | 1.089 | no — 25 % |
| descent / drop, −z | 21.58 | 9.81 | 0.30 / 2.0 | only `place low`, by 2 % |

**Two things to read carefully.** (i) The cone's `mu_eff 0.45` column is *zero* for
any +z move **by construction** (the model assumes `N = m g`, no squeeze), so that
column is the model leaving its own validity — the physical worst-fruit margin is
the **measured 1.20×** of P40 (a 4.42 N pinch against a 1.66 N following-error
transient at `mu` 0.45), 2.70× at the shipped 9.95 N. (ii) Because the cone only
rewrites `a_max` (and derives `j`, `v` from it), **raising a leg's `v_max` alone
spends no cone margin at all** — the cone is an acceleration budget.

---

## 3. The IK / servo loop

| item | value | site |
| --- | --- | --- |
| `ik_step` per-tick clamp | **`FRUIT_IK_MAX_STEP = 0.5 rad`** on the joint step (`dq`, after `gain`; joint space) | `control.py:147, 423` |
| IK gain | `FRUIT_IK_GAIN = 1.0` (no cap) | `control.py:146, 423` |
| damping | `FRUIT_IK_DAMPING = 0.05` (λ = 2.5e-3, regularisation only) | `control.py:145, 421-422` |
| command rate cap | `FRUIT_IK_RATE = 0.0` (**off**; would only slow the hand) | `control.py:479-483` |
| warn threshold | `FRUIT_IK_WARN = 0.0` (reporting only) | `control.py:486` |
| joint-limit clamp | `np.clip(q_cmd + dq, arm_lo, arm_hi)` | `control.py:494` |
| **Cartesian step cap** | **there is none** — the clamp is joint-space; the effective Cartesian step is `J·dq`, ≈ 3.1 mm/tick at the fastest leg | — |
| wrist limits | j5 ±90°, j6 ±45°, j7 ±90° (USD `physics:lowerLimit/upperLimit`); plus `arm.hold_quaternion` during the close/grip; `FRUIT_CARRY_HOLD_QUAT=1` (off) would hold it through the carry | USD 3726-3795; `tasks.py:3344` |
| hand-pad speed | `FRUIT_HAND_VMAX = 0.0` (uncapped; capping it was measured **worse**, `logs/150`) | `kinematic_gripper.py:219` |
| actuated-hand wrist | `FRUIT_WRIST_VMAX = 0.15` — **not the shipped jaw** (`FRUIT_GRIPPER_KIND` defaults to `openarm`) | `actuated_gripper.py:263`; `tasks.py:582` |

**The `FRUIT_IK_MAX_STEP` clamp never binds.** The fastest leg's peak is
0.373 m/s → **3.1 mm/tick**; at a 0.2–0.5 m lever that is **6–16 mrad = 1.2–3.1 %
of the 0.5 rad clamp** (36–80× headroom). `FRUIT_IK_GAIN` is already 1.0.

### 3.1 The measured following error

Two different numbers are called "err" in the record; do not mix them:

| what | measured | where |
| --- | --- | --- |
| **the arm at the end of a descent** (`end=` = measured pad centre vs the pose the leg was sent to) | **8.1–10.4 mm** (median 8.7–9.6) on all four shipped logs; **1.9–5.2 mm** on the indexed line | out §G |
| the same, historical corpus (`logs/161`, the indexed descent *commanded into the belt*) | **42–88 mm** with `v_end` 0.002–0.013 m/s | out §G |
| **the finger drive at the close** (`err` = `drive_target − position`) | **3.95–7.57 mm** (median 5.59) at k=1e6 → `k·err` = 4–8 kN, clipped to the 10 N cap | `logs/p40/EFFORT_READ.md:153` |

The current `end=` is a **lag**, not a boundary: `v_end` reads 0.060 m/s and the
first-order bound `v_end·tau = 0.060 × 0.200 = 12.0 mm` brackets the measured
8.1–10.4 mm. The historical 42–88 mm had `v_end` 0.002–0.013 m/s (mean 0.007, i.e. 5–30× below the current 0.060) — that gap was the hand
**stopped by the conveyor** (`logs/166` vs `/167`), which is why
`FRUIT_TUNE_GAINS=1` left it unchanged (`logs/165`: 36–98 mm) and why the descent
is the one leg whose **achieved peak is 0.75 of its own reference** (`ach/ref`) while
its `ref/cap` still reads 0.96 — the profile is the designed length, but the drive
does not fill it.

**The descent is the only leg the servo, not the cap, sets** — so raising its
`v_max` does *not* raise its achieved speed, which is exactly what `ach/ref 0.75`
measures.

---

## 4. The measured cost per cap

### 4.1 The cycle, in sim seconds per attempt

| phase | single arm (shipped, `d0_accept_A_s5`, 10 att.) | share | two-line (`p41/p2/twoline_profile`, 10 att.) | share |
| --- | --- | --- | --- | --- |
| prepose | 0.88 | 5.8 % | 0.71 | 4.6 % |
| hover | 0.77 | 5.1 % | 0.76 | 5.0 % |
| **descent** (= arrival wait + handover wait + 0.74 s motion) | 2.75 | 18.3 % | 3.42 | 22.3 % |
| close | 1.19 | 7.9 % | 1.36 | 8.9 % |
| grip (probe + regrasp) | 1.61 | 10.7 % | 2.29 | 15.0 % |
| **lift** | **1.82** | 12.1 % | 1.80 | 11.8 % |
| **place** (one leg: `place0` *or* `place1`) | **3.35** | **22.3 %** | 3.21 | 21.0 % |
| **release** | **2.04** | 13.6 % | 2.30 | 15.1 % |
| return | 0.64 | 4.2 % | 0.67 | 4.4 % |
| end | 0.00 | 0.0 % | 0.02 | 0.1 % |
| **total** | **15.05** | 100 % | 15.29 | 100 % |

`d0_accept_A_s5` is the shipped branch: its **387 non-`[bed]` `[fruit]` lines are
byte-identical to `post_revert_accept_unset.log`** (md5 `8ed1def4`), i.e. the
registered acceptance stream, and the P43 phase-2 report's table reproduces these
means to 0.01 s. The two-line's `descent` includes the belt wait; subtracting it
(0.54 s handover + 0.74 s motion) leaves 2.1 s of *arrival* waiting.

### 4.2 Which cap bounds which block

| block | seconds | bounded by | the cap's own seconds |
| --- | --- | --- | --- |
| **place** | 3.35 / 3.21 | `FRUIT_DYNAMIC_PLACE_VMAX` 0.35 — `v_max` binds: t_v 3.00 s vs t_a 1.72 s, ×1.02 → **379 ticks = 3.16 s** | **3.16 s of 3.35 (94 %)** |
| **release** | 2.04 / 2.30 | three open-loop clocks: dwell 20 + pad 120 + finger 48 ticks | **1.57 s (77 % / 68 %)** |
| **lift** | 1.82 / 1.80 | `FRUIT_DYNAMIC_LIFT_VMAX` 0.30 (v_max binds; 164 ticks = 1.37 s) | **1.37 s (75 %)** |
| **descent** | 2.75 / 3.42 | `FRUIT_DYNAMIC_APPROACH_VMAX` 0.15 → **0.74 s of motion**; the other 1.9–2.5 s is the **belt** (`fruit at pick point … after N steps`, 1.28–1.96 s) + the handover wait (0.54–0.65 s) | **0.74 s (27 % / 22 %)** |
| hover | 0.77 | a **convergence** loop: `move_to(max_steps=300, tol 0.008 m)` + 20-tick settle | 0.17 s clock, ~0.6 s tau |
| prepose | 0.88 | a **clock**: 20-tick catch-up + 45-tick blend + 20 app steps = 85 ticks = 0.71 s | 0.71 s (81 %) |
| close | 1.19 | clocks: 24 + 60 + 48 = 132 ticks = 1.10 s | **1.10 s (92 %)** |
| grip | 1.61 / 2.29 | the **probe** clock (40 ticks single-arm / 60 two-line) + the retry class (grip, closed) | 0.33 s (21 %) / 0.50 s (22 %) |
| return | 0.64 | the same convergence loop to `ready` | — |

**The empty-hand transit is 1.65 s (prepose 0.88 + hover 0.77), and only 0.71 s of
it is a clock.** The rest is the drive's 0.2 s time constant under an 8 mm
tolerance — the *only* block in the cycle whose duration a gain could shorten.
`FRUIT_HOVER_STEP` (0.04 rad/tick) is **not** what bounds it: 0.04 rad at a 0.3 m
lever is 12 mm/tick, so the ~6 cm hover is ~5 ticks of travel against the 82–103
measured.

### 4.3 What the headroom model says (out §E)

Measured mean leg lengths, seconds saved against the shipped profile:

| leg | d [cm] | now | v×1.25 | v×1.5 | v×2 | a×2 | both×2 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `grasp_lift` | 22.6 | 175 ticks | 141 (**−0.28 s**) | 141 (−0.28) | 141 (−0.28) | 175 (0.00) | 109 (−0.55 s) |
| `place0` | 56.1 | 370 | 296 (**−0.62 s**) | 247 (−1.02) | 213 (−1.31) | 370 (0.00) | 186 (−1.53) |
| `approach` | 5.7 | 88 | 80 (−0.07) | 80 (−0.07) | 80 (−0.07) | 88 (0.00) | 57 (−0.26) |

**A v-only raise stops paying at the `a_max` ceiling**: lift **0.371 m/s (1.24×)**,
place0 **0.610 m/s (1.74×)**, approach **0.166 m/s (1.11×)**. An *a-only* raise
buys exactly **0.00 s** on all three — the caps that bind are the **speed** caps,
not the acceleration caps. That is the single most useful line in this census.

---

## 5. The ranked "raise the cap" candidates

| # | (a) cap | (b) site | (c) what it speeds up | (d) measured risk | (e) knob exists? |
| --- | --- | --- | --- | --- | --- |
| **1** | `FRUIT_DYNAMIC_PLACE_VMAX` **0.35 → 0.52** (0.61 = the `a_max` ceiling) | `tasks.py:3424` | `place0/1`: **−1.09 s** at 0.52, −1.38 s at 0.61, on a 3.35 s (single) / 3.21 s (two-line) block | the place is **loaded for its whole length**, and the place is where the cnp class lands. The Gate-19 isolation sweep (`tasks.py:3413-3423`) reads 0.20/0.25/0.30/0.35 → **7/7/8/9 of 10** — monotone, and the winner sits at the top of the swept range, so >0.35 is **unswept, not refuted**. A v-only raise spends **no** cone margin (§2.4) | **yes** — a shipped default with an env override (`=0` removes the cap) |
| **2** | `FRUIT_RELEASE_PAD_HOLD` 3→2 + `..._FINGER_HOLD` 3→2 + `..._DWELL` 20→0 | `tasks.py:11805, 11818, 11799` | the release block: **−0.63 s** (3→1 is −1.02 s) on 2.04 s (single) / 2.30 s (two-line) | the ramp is what makes the payload settle onto the belt; the release-induced ejection is the phenomenon `FRUIT_RELEASE_DEBUG` was built to explain, and the AGENTS line is "20/3/3 and **already reduced**". Untested below 3 in the record | **yes** — three shipped defaults with env overrides |
| **3** | `FRUIT_DYNAMIC_LIFT_AMAX` **1.0 → 1.9** + `..._VMAX` 0.30 → 0.36 | `tasks.py:3402, 3399` | the lift: **−0.23 s** (v alone, a then binds at 1.24×) / **−0.56 s** (both) on 1.82 s | the grip-critical leg: the Gate-19 lift sweep is 0.20/0.25/0.30 → **8/8/9 of 10**, and the 3 cm strawberry slipped mid-lift at 27 N tactile in P2. The vertical cone budget is **1.962 m/s²**, so **a ≤ 1.9 is the hard ceiling** and `limited_by_cone` would clip 2.0 → 1.962 anyway | **yes** — two shipped defaults |
| 4 | `FRUIT_DYNAMIC_APPROACH_VMAX` 0.15 → 0.25 | `tasks.py:5937, 9352` | 0.74 s of descent motion **plus the handover lead it sets** (`t_desc` enters `lead = v·(overhead + t_desc + margin)`): ~−0.2 s motion, ~−0.1 s wait | **the worst value/risk ratio**: `ach/ref` is 0.75, so the drive cannot track 0.15 in 0.74 s and will not track 0.25; the historical corpus ended 42–88 mm short by *boundary* (`logs/161`) and the current descents already end 8.1–10.4 mm short; AGENTS says do not re-tune this budget | yes (shipped default) |
| 5 | `FRUIT_TUNE_GAINS=1` (k 1500 / c 60, tau 0.04 s) | `control.py:214-217` | **not a rate lever**: every leg is clocked, so it can only shorten the two *convergence* blocks (hover 0.77, return 0.64 → ~0.2 s each by the `tau·ln(0.06/0.008)` model) and the 8–10 mm end-gap (→ ~2–3 mm predicted) | the **measured** record is null on the descent (`logs/165`) and inconclusive on the approach's acceleration (`logs/375/376`); the convergence prediction is **untested** — and the model above says a 2.4× faster loop should be visible | yes — opt-in, and it is the only knob in the *convergence* class |

**Why the order is this order.** (1) is the largest measured block whose cap binds
and whose only evidence is monotone in the safe direction. (2) is the largest
*clock* block with no motion model behind it at all. (3) is the grip-critical
leg — the highest risk per second recovered. (4) is worth ~0.3 s and carries the
boundary and the documented "do not re-tune" instruction. (5) recovers no leg
time and is a **tracking** change, not a speed change.

---

## 6. The three biggest time blocks a cap could actually move

1. **`place` — 3.35 s (single arm, 22.3 % of the cycle) / 3.21 s (two-line,
   21.0 %)**, of which **3.16 s (379 ticks) is one jerk-limited profile at
   `v_max` 0.35**. Recoverable: **1.09 s** at 0.52, **1.38 s** at the 0.61
   `a_max` ceiling.
2. **`release` — 2.04 s (13.6 %) / 2.30 s (15.1 %)**, of which **1.57 s is three
   open-loop holds** (20 + 120 + 48 ticks). Recoverable: **0.63 s** at
   PAD/FINGER 3→2 + DWELL 20→0, **1.02 s** at 3→1.
3. **`lift` — 1.82 s (12.1 %) / 1.80 s (11.8 %)**, of which **1.37 s is the
   profile at `v_max` 0.30**. Recoverable: **0.23 s** (v alone) / **0.56 s**
   (v 0.36 + a 1.9).

Those three are **7.21 s of a 15.05 s attempt = 48 %**, and the caps inside them
account for **6.10 s** (3.16 + 1.57 + 1.37). The next block down is the empty-hand transit (1.65 s),
but only **~0.6 s** of it is a convergence term and the rest is a clock with a
measured feed-time reason.

---

## 7. The caps that cannot help (and why)

| cap | why it cannot move time |
| --- | --- |
| **joint velocity limits** (`maxJointVelocity` 312/960/1200 deg/s = 5.45/16.75/20.94 rad/s) | the tightest is **2.1×** the fastest reference (j4/j7 at their levers carry 0.79–0.84 m/s against 0.38 m/s); unreachable |
| **joint effort limits** (`maxForce` 40/27/7 N·m) | the tightest `F/I ÷ need` is **2.4×** (j5); and at the measured ~30 mrad the drive is already saturated, i.e. it is a torque source, not a speed cap |
| **the arm drive gains** (`FRUIT_TUNE_GAINS`, k 22918/c 4583, k 1500/c 60) | every leg is **tick-clocked** by its profile (§2.3 reproduces all legs to ±1.4 %), so bandwidth changes tracking, never duration; measured null on the descent (`logs/165`) |
| `FRUIT_IK_MAX_STEP` 0.5 rad, `FRUIT_IK_GAIN` 1.0, `FRUIT_IK_DAMPING` | the clamp is **36–80×** the per-tick demand (3.1 mm/tick ⇒ 6–16 mrad); gain is already 1.0; damping is regularisation |
| `FRUIT_IK_RATE` | default **0 = off**, and it can only *slow* the hand |
| `FRUIT_HAND_VMAX` | default **0 = uncapped**; and capping it was measured **worse** (`logs/150`: a capped hand makes an escape worse) |
| **the friction cone** on lift/place | it never binds — a = 1.0 of 1.962 (lift), 1.089 of 4.273 (place); the only clip is the release drop, 2.0 → 1.962 (−2 %); and a cone lever is an *acceleration* budget, which buys **0.00 s** (§4.3) |
| `FRUIT_HOVER_STEP` 0.04 rad/tick | the hover is 82–103 ticks against ~5 ticks of travel: the binder is the 8 mm tolerance under tau, not the step |
| the close clocks (24 + 60 + 48) and `FRUIT_DYNAMIC_HOLD` | they are the **grip class** (the load ramp + hold is where the 9.8 N pinch is built) — closed by P40/P41/P42; a shorter hold trades the grip |
| the belt speed (0.12 → 0.15/0.18) | screened flat (R3 §4); the arrival wait is belt/graded-supply bound, not speed bound |
| the supply density (`FRUIT_SUPPLY_PATCH_DENSITY`) | class-standardised flat; **negative** on a single-species pool (P1c) |
| the descent's `FRUIT_DYNAMIC_APPROACH_VMAX` as a *rate* lever | the block is 71–74 % belt wait (1.28–1.96 s of arrival + 0.54–0.65 s of handover against 0.74 s of motion); `ach/ref` 0.75 says the drive cannot track the current cap, let alone a higher one, and the historical corpus's 42–88 mm gap was a boundary stop (`logs/161`) |
| `FRUIT_PLACE_LOW_*` | the drop is 80–86 ticks (0.67–0.72 s) and already inside `release`'s clocks; its `a_max` is cone-clipped by 2 % |

**Not proposed here, per the phase's scope:** the grip/retention class
(`SIM_LIMIT.md`) and the arm park (P43). Nothing in this census touches either.

---

## 8. What this document does not claim

* **No rate.** Every `[cycle]` number is one branch of one configuration; 15.05 s
  and 15.29 s are two different scenarios (single arm vs two-line) and are not a
  speed comparison.
* **No claim that the tuned gains would help** — §5.5 states a *prediction* for the
  two convergence blocks and names the measurement that would settle it.
* **No claim about the place's success rate above 0.35 m/s.** The Gate-19 sweep is
  the only speed evidence and it stops at the shipped value; a faster place is
  *unswept*, which is not the same as safe.
* **The `end=` numbers here are the current tree's.** The 40–90 mm figure in
  `AGENTS.md` §2 is the `logs/160/161` corpus (the indexed descent commanded into
  the belt); the current dynamic descents read **8.1–10.4 mm** because their aim
  stops above the belt, so the two must not be quoted interchangeably.
