# P66 phase 1a - the left station feasibility sweep over (x, y, depth)

**VERDICT (first line): there is no station point - none of 150 cells, over the whole
delivered band, five along-belt offsets and three depths - where the top-down attitude
`T0` holds with the registered quality (`qerr <= 2 deg` AND `margin >= 0.05 rad` AND
`pad >= 2 mm`). `T0` passes 0/75 of its own cells; its best margin is `+0.010 rad @ j3`
at the one point `(x = 0.320, y = -0.05, z = 0.090)`. The shipped control `C0` passes
31/75 in the same grid. And the sweep finds the thing P65 left open: **at the height
the lift ends (`belt_top + 0.36`), `T0` is not holdable at all** - `qerr` 24.3-60.0 deg,
residual 45.8-203.9 mm, margin `0.000` - which is P63's measured 24.6 deg carry drift
without a payload, without a controller and without a transient.**

Written 2026-10-30 on HEAD `2331733`. **Offline geometry only: no policy run, no
`src/` edit, no `configs/` edit, no default change, no commit.** The probe is a
**copy** of `logs/p62/ik_probe.py` (`logs/p66/ik_probe_sweep.py`), so the P62/P64
artifacts stay byte-reproducible.

---

## 1. Method

The P62 recipe, unchanged: build `("environment", "pedestal", "robot", "conveyor")`,
`scene.start()`, teleport the **left** arm to `configs/waypoints_oriented.json`'s
`arms.left.grasp` seed, pin `ArmController.hold_quaternion` to the candidate, solve
the catch's own position IK (`solve_to(..., iterations=400, tolerance=6 mm,
restarts=1)`) with the jaw centre at `(x, y, belt_top + z)`, then read `res` /
`qerr` / `margin@joint` / pads-above-belt / jaw axis.

Three additions, all default-off in the copy:

| addition | what it adds | why |
| --- | --- | --- |
| `FRUIT_P66_Y` | an **along-belt y sweep**: `-0.10, -0.05, 0.00, +0.05, +0.10` | `_dynamic_aim` aims at `[fruit.x, station_y + lead, fruit.z]` (`tasks.py:6629`) and the single arm's lead is **0.0** (`_two_line_catch_lead`, two-line-scoped), so the shipped aim is `y = pick_y = 0.0` for every attempt. The y sweep is therefore a **capability** map: *would a different along-belt aim help?* |
| `FRUIT_P66_Z` | a **depth sweep** in metres above the belt top: `0.090`, `0.250`, `0.360` | `0.090` is the grip depth P62 used; `0.250 = 0.090 + LIFT_HEIGHT` with `LIFT_HEIGHT = 0.16` (`tasks.py:615`); `0.360` is where the lift actually **ends** - `jaw_target("grasp_lift")` = `belt_top + 0.28` plus the OpenArm `FRUIT_OPENARM_TRANSFER_LIFT` 0.08 (`tasks.py:3120-3130`), and `_carry` keeps the catch's own x/y (`goal = [pad.x, pad.y, goal.z]`), so the grid cells at `z = 0.360` **are** the lift's end pose |
| `FRUIT_P66_SEED` | solve from `grasp` (default) or from `grasp_lift` | robustness B: does *any* configuration hold the attitude at that height |

`x` = `0.188, 0.240, 0.274, 0.320, 0.398` - the delivered band's min, p50 and max plus
two interior columns (P60: x 0.188-0.398, p50 0.274). Grid: **5 x 5 x 3 x 2 = 150
cells**.

**The control is the file's own quaternion, measured:** `|dot(C0,
configs/waypoints_oriented.json's grasp_quaternion.left)| = 1.000000000`, so `C0` (P62's
name) and `QFILE` (P64's name) are the same attitude and there is no second control to
run. The probe also reproduces P62 row for row at the shared cell - `T0` at
`x = 0.274, y = 0, z = 0.090` reads `res 6.0 mm, qerr 0.77 deg, margin +0.007 @ j3`
against P62's `6.0 / 0.77 / +0.007`.

---

## 2. The answer

Criterion: `qerr <= 2 deg` AND `margin >= 0.05 rad` AND `pad >= 2 mm`.

| attitude | depth (m ab. belt) | pass | best margin | qerr range | pad range | solved <= 6 mm |
| --- | --- | --- | --- | --- | --- | --- |
| **T0** | 0.090 (grip) | **0/25** | **+0.010 rad @ j3** | 0.63-22.56 deg | +56.1..+66.1 mm | 17/25 |
| **T0** | 0.250 (+LIFT_HEIGHT) | **0/25** | +0.000 rad @ j5/j7 | 6.03-26.18 deg | +208.7..+218.8 mm | 0/25 |
| **T0** | 0.360 (grasp_lift target) | **0/25** | +0.000 rad @ j5/j7 | **24.27-60.00 deg** | +328.8..+487.2 mm | 0/25 |
| **T0** | **all** | **0/75** | **+0.010 rad @ j3** | 0.63-60.00 deg | +56.1..+487.2 mm | 17/75 |
| C0 | 0.090 | 12/25 | +0.677 rad @ j2 | 0.70-8.66 deg | +17.2..+44.2 mm | 10/25 |
| C0 | 0.250 | 9/25 | +0.508 rad @ j2 | 0.62-12.03 deg | +136.5..+198.7 mm | 15/25 |
| C0 | 0.360 | 10/25 | +0.451 rad @ j2 | 0.64-22.78 deg | +267.9..+363.8 mm | 16/25 |
| C0 | all | 31/75 | +0.677 rad @ j2 | 0.62-22.78 deg | +17.2..+363.8 mm | 41/75 |

**T0's margin distribution: `>= 0.05 rad` 0/75, `>= 0.02 rad` 0/75, `>= 0.01 rad`
1/75.** The clause that fails is **always the margin** - the pads are never the
binding term (`>= 2 mm` on **75/75**, min `+56.1 mm`) and `qerr` is inside 2 deg on
**19/75** of T0's cells (all 19 at the grip depth).

**The best T0 point** (highest margin over the whole grid):

```
x = 0.320  y = -0.05  z = 0.090 m above belt_top
res = 5.9 mm   qerr = 1.27 deg   margin = +0.010 rad @ j3
pad above belt = +64.7 mm   jaw_z = +0.0007   achieved belt projection = +0.0136
```

That is **5x short of the 0.05 rad bar** and it sits at `j3` (the arm's configuration
limit), not at a wrist joint - P62's `+0.007 rad @ j3` reproduced across y.

---

## 3. The grid, T0 (res mm / qerr deg / margin rad @ joint)

### grip depth, z = 0.090

| y \\ x | 0.188 | 0.240 | 0.274 | 0.320 | 0.398 |
| --- | --- | --- | --- | --- | --- |
| **-0.10** | 5.9 / 1.00 / +0.003 j3 | 8.6 / 1.59 / +0.000 j3 | 25.6 / 1.95 / +0.000 j3 | 65.3 / 7.06 / -0.000 j2 | 152.7 / 22.56 / +0.002 j2 |
| **-0.05** | 5.8 / 0.64 / +0.003 j3 | 5.9 / 0.74 / +0.005 j3 | 5.9 / 0.82 / +0.007 j3 | **5.9 / 1.27 / +0.010 j3** | 94.4 / 20.02 / +0.002 j2 |
| **0.00** | 5.8 / 0.63 / +0.004 j3 | 5.9 / 0.72 / +0.006 j3 | 6.0 / 0.77 / +0.007 j3 | 5.9 / 0.79 / +0.008 j3 | 32.8 / 16.98 / -0.000 j6 |
| **+0.05** | 5.9 / 0.66 / +0.005 j3 | 5.9 / 0.73 / +0.006 j3 | 5.9 / 0.75 / +0.007 j3 | 5.9 / 0.75 / +0.008 j3 | 15.1 / 15.48 / -0.000 j6 |
| **+0.10** | 5.9 / 0.77 / +0.006 j3 | 5.9 / 0.79 / +0.007 j3 | 6.0 / 0.79 / +0.007 j3 | 6.0 / 0.75 / +0.007 j3 | 24.6 / 18.51 / -0.000 j6 |

`T0` reaches the grip at 5.8-6.0 mm across `x = 0.188-0.320` for `y >= -0.05`, with the
attitude inside 1.3 deg - **and `j3` at its limit everywhere it works**. `y = -0.10`
is outside (margin 0.000, residual 25.6-152.7 mm) and `x = 0.398` is the documented +x
reach cliff (15.1-152.7 mm, 15-23 deg).

### the lift's end pose, z = 0.360

| y \\ x | 0.188 | 0.240 | 0.274 | 0.320 | 0.398 |
| --- | --- | --- | --- | --- | --- |
| **-0.10** | 123.0 / 32.94 | 122.0 / 32.04 | 132.4 / 34.74 | 144.2 / 39.65 | 124.6 / 39.52 |
| **-0.05** | 105.4 / 31.03 | 93.8 / 27.99 | 91.4 / 28.51 | 111.8 / 39.54 | 74.8 / 40.45 |
| **0.00** | 119.1 / 35.03 | 100.3 / 29.34 | 90.8 / 26.43 | 94.2 / 32.60 | 45.8 / 42.00 |
| **+0.05** | 143.6 / 42.36 | 121.5 / 35.75 | 106.3 / 31.25 | **81.8 / 24.27** | 76.5 / 44.57 |
| **+0.10** | 203.9 / 60.00 | 149.5 / 43.62 | 115.5 / 34.33 | 84.5 / 27.85 | 116.1 / 50.54 |

(`res mm / qerr deg`; **every** cell's margin is `+0.000`/`-0.000`.) No cell solves
within 6 mm, the best attitude error over the 25 cells is **24.27 deg**, and the
achieved belt projection runs **+0.000..+0.635** against a commanded `0.000` - i.e.
when the arm cannot hold `T0` it falls back to the **shipped attitude's** projection
(`C0` commands `+0.513`, and its own achieved values here are `+0.352..+0.538`).

### the dose-response in height (x = 0.274, y = 0.00, margin clause aside)

| z above belt | T0 `qerr` | T0 `res` | C0 `qerr` | C0 `margin` |
| --- | --- | --- | --- | --- |
| 0.090 | **0.77 deg** | 6.0 mm | 1.48 deg | +0.377 rad |
| 0.250 | **6.86 deg** | 24.8 mm | 1.01 deg | +0.303 rad |
| 0.360 | **26.43 deg** | 90.8 mm | 1.38 deg | +0.212 rad |

`T0` degrades monotonically with height while the shipped attitude does not.

---

## 4. Delivered-band coverage (P60: x 0.188-0.398, p50 0.274)

| attitude | depth | x columns covered (any y) | passing y per x |
| --- | --- | --- | --- |
| **T0** | 0.090 | **0/5** | none |
| **T0** | 0.250 | **0/5** | none |
| **T0** | 0.360 | **0/5** | none |
| C0 | 0.090 | **5/5** | 0.188: +0.05,+0.10 · 0.240: 0.00,+0.05,+0.10 · 0.274: 0.00,+0.05,+0.10 · 0.320: 0.00,+0.05,+0.10 · 0.398: 0.00 |
| C0 | 0.250 | 3/5 | 0.188: none · 0.240: none · 0.274: +0.05,+0.10 · 0.320: 0.00,+0.05,+0.10 · 0.398: -0.05..+0.10 |
| C0 | 0.360 | 4/5 | 0.188: none · 0.240: 0.00 · 0.274/0.320: 0.00,+0.05,+0.10 · 0.398: 0.00,+0.05,+0.10 |

So the band is **covered by the shipped attitude and not by `T0`**, and for `C0` the
passing `y` moves upstream as the height rises (at the grip, `x = 0.188` needs
`y >= +0.05`; at the lift's end `x = 0.240` needs `y = 0.00` exactly).

---

## 5. Robustness - the negative is not a seed or a starting-pose artefact

**A. `restarts = 4`** (P62 ran this at `y = 0` only; here over `y`), T0, z = 0.090,
`x in {0.274, 0.320}`, 6 cells, 47.0 s: **0/6 pass, best margin `+0.008 rad @ j3`**.
Re-seeding does not help; the `y = -0.10` cells get *worse* (23.6 / 61.2 mm residual,
4.4 / 7.8 deg).

**B. solved from `grasp_lift`'s own seed**, `restarts = 3`, z = 0.360, `y = 0`, 8 cells,
68.4 s:

| attitude | pass | qerr | res | margin |
| --- | --- | --- | --- | --- |
| **T0** | **0/4** | **22.90-47.73 deg** | 45.8-119.1 mm | -0.000..+0.000 |
| C0 | 3/4 | 0.85-6.36 deg | 5.8-18.1 mm | +0.001..+0.189 |

Starting from the lift pose itself does not rescue `T0` (3 restarts from a
configuration that was *authored for that height*), while the shipped attitude holds
0.85-0.90 deg there. `x = 0.188` fails for both (18.1 mm / 6.36 deg).

---

## 6. What this reads as, and what it changes downstream

* **The station is not the problem, and `T0` is not a station lever.** At the grip
  depth `T0` zeroes the belt projection (`|proj_ach| <= 0.014` on the 17 cells that
  solve) at the control's own residual, but it does so with `j3` **on its limit**
  (`+0.003..+0.010 rad`), and no `y` and no re-seed buys headroom. P62's
  recommendation to run `T0` at the station was always scoped "at the station"; this
  sweep measures the cost of that scope.
* **The 25 deg is created where the lift ends, and it is static.** `T0` at
  `belt_top + 0.36` is not holdable: the best static solve over 25 cells is **24.27
  deg** off, and the achieved projection sits at `+0.00..+0.64` (toward the shipped
  `+0.513`). P63 measured **24.6 deg median** on the left's failing carry legs *with*
  the payload, *inside* the control loop and *during* a profile - the static,
  unloaded, converged solve lands on the same number. So:
  * P65 phase 2's discriminator **(i) the payload-induced wrist deflection** now has a
    prediction: removing the payload should **not** move the drift (it is already 24
    deg with no payload and no load);
  * **(ii) `ik_step`'s `gain`** and **(iii) the hold's re-application rate** are
    controller terms acting on a pose the arm cannot hold - their prior is "no
    effect";
  * the surviving shape is a **pose** lever: the lift's end height/attitude, not the
    controller. A lower lift, or a re-orientation *during* the lift (the fingers are
    vertical is what costs the reach), has a measured mechanism to attack.
* **`C0` is the attitude the workspace offers.** Everywhere `T0` fails at height, some
  nearby `C0`-style solve succeeds with margin `+0.10..+0.45` and `qerr < 2 deg`. That
  is the "only feasible attitudes near here are belt-aligned" statement, stated as a
  measurement rather than an inference from the drift.
* **The +x cliff is unchanged**: `x = 0.398` fails for both attitudes at the grip
  depth (`T0` 15.1-152.7 mm / 15-23 deg, `C0` 8.3 mm / 1.98 deg), P62's and P49's
  documented edge. `x = 0.188` fails at height for both (48.7 / 16.4 mm for `C0`).

---

## 7. Cost

| arm | cells | wall | per cell |
| --- | --- | --- | --- |
| the 150-cell grid (T0 + C0) | 150 | **458.7 s sweep, 469.2 s process** | 3.06 s |
| robustness A (`restarts = 4`) | 6 | 47.0 s | 6.07 s |
| robustness B (from `grasp_lift`) | 8 | 68.4 s | 7.23 s |
| **total (incl. a 19 s smoke)** | 164 | **~9.8 min** | - |

The per-cell cost is dominated by the cells that never converge (a failing cell burns
the full 400 iterations). One claim per run, no overlap (`pgrep -f python.sh` empty
before each).

## 8. What this does not show

* It is the **static pre-grasp solve** from a calibrated seed, not the live catch: no
  payload, no belt drag, no profile, no controller loop. It says a pose is
  *statically* feasible; it does not re-measure a carry leg. The agreement with P63's
  measured 24.6 deg is the cross-check, not a replacement.
* `y` is **not** a free variable in the shipped line: `_dynamic_aim` returns
  `station_y` for the single arm, so an along-belt offset would need its own aim rule
  (the reach-anywhere intercept is default off and was measured negative, R11-A/R11-A.1).
  The y sweep bounds a *capability*, and its answer is that y does not help T0.
* `restarts = 1` on the main grid (the P62 convention); A/B cover the re-seed question
  on a subset, not on all 150 cells.
* Only the **left** arm and only the single-arm presentation's aim geometry; the
  two-line's right station (`y = -0.10`) and its pre-pose were not swept.

## 9. Reproduce

```bash
# the 150-cell grid (one claim, 7 min 57 s)
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p66/sweep.log \
  env FRUIT_P66_JSON=logs/p66/sweep_rows.json scripts/run.sh logs/p66/ik_probe_sweep.py

# robustness A: restarts=4 over y
FRUIT_P66_CANDIDATES=T0 FRUIT_P66_X=0.274,0.320 FRUIT_P66_Y=-0.10,0.00,0.10 \
  FRUIT_P66_Z=0.09 FRUIT_P66_RESTARTS=4 FRUIT_P66_JSON=logs/p66/restart_rows.json \
  scripts/run.sh logs/p66/ik_probe_sweep.py

# robustness B: solved from the grasp_lift seed at the lift height
FRUIT_P66_CANDIDATES=T0,C0 FRUIT_P66_X=0.188,0.274,0.320,0.398 FRUIT_P66_Y=0.00 \
  FRUIT_P66_Z=0.36 FRUIT_P66_RESTARTS=3 FRUIT_P66_SEED=grasp_lift \
  FRUIT_P66_JSON=logs/p66/liftseed_rows.json scripts/run.sh logs/p66/ik_probe_sweep.py

python3 logs/p66/sweep_report.py          # -> logs/p66/sweep_report.txt, 12/12 checks
```

**Pins:** `logs/p66/ik_probe_sweep.py` **bba0fbf0**, `logs/p66/sweep_report.py`
**f6292e00**, `sweep_rows.json` **174d2a34**, `restart_rows.json` **6f6f5c5e**,
`liftseed_rows.json` **9fdf9b64**, `sweep.log` **23b941e9**, `sweep_report.txt`
**e3e2d33f**, and the 1-cell P62-reproduction smoke (`smoke.log` **030a9ec3**,
`smoke_rows.json` **c02a68b3**); HEAD **2331733**; `src/fruit_sorting/tasks.py` `309e5a38`, `control.py`
`9384ff4f`, `scene.py` `27e3d64a`; `configs/*` untouched (`waypoints_oriented.json`
`0ea08ebb`, `waypoints.json` `d81c6f1c`). **`logs/` is gitignored**, so this directory
needs `git add -f` at the close-out.
