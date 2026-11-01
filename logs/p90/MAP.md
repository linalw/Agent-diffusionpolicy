# P90 map - the output place-station sweep: **no station holds top-down, and the shipped point is already the best one there is**

VERDICT (first line): there is no place station - not one of 588 cells, over
+-0.15 m in `x` and `y`, at the place height and at the transfer height, on both
arms, in three attitude modes - where the left can hold the top-down attitude. The
top-down attitude **is not statically solvable to 6 mm anywhere in the envelope**
(0/98 per arm at both heights; the best joint margin at the transfer height is
**0.15 mrad**), and the attitude the arm *does* achieve where it solves is
**77.8-108.4 deg** off top-down - with the **shipped station the best of them
(77.75 deg)**. The station is also at the **reach boundary**: the arm's own
calibrated belt-aligned attitude does not solve there either (83-105 mm residual),
and its only solved cells sit **25-75 mm inboard of the slab's inner edge**, i.e.
off the belt. **The rotation is therefore not a siting choice**, and the workstation
path closes with it.

Written 2026-11-01. **Offline geometry only: no policy run, no `src/` edit, no
`configs/` edit, no default change, no commit, no re-recorded reference.**
Registration `logs/p90/METHOD.md` (md5 `42bec0f81b71a9f02412ced3bc2ab6b1`, mtime
**22:31:42**, i.e. **before** `station_map.py` was written at 22:32:17 and before the
sweep started at 22:33:39 - the criterion, the grid, the modes and the ranking rule
are the pre-run text, unedited).

---

## 1. What was swept, and the criterion (as pinned)

The probe is a **copy** of `logs/p66/ik_probe_sweep.py` retargeted from the pick
station to the place station (`logs/p90/station_map.py`), so the P62/P64/P66
artifacts stay byte-reproducible. The target is the pose the code actually
commands - `(x, y, output_place_z [+ the OpenArm 0.08])`:

| axis | values | why |
|---|---|---|
| `x` | 0.28, 0.33, **0.43**, 0.48, 0.53, 0.58 | +-0.15 m around `output_place_x`; 0.05 m step |
| `y` | +-0.35, 0.40, 0.45, **0.50**, 0.55, 0.60, 0.65 | +-0.15 m around `output_place_y`; the edge columns sit **inboard of the slab (0.425)** and 25 mm **inside its outer edge (0.675)** |
| `z` | **1.450** (`output_place_z`), **1.530** (the transfer) | the two heights the config produces |
| arm | left (`+y`), right (`-y`) | both, as the brief asks |
| mode | `T0`, `NAT`, `C0` | below |

**The criterion, unchanged from `METHOD.md` §3:**

```
T0 / C0 :  residual <= 6 mm  AND  qerr <= 2 deg  AND  margin >= 0.05 rad  AND  pad >= 2 mm
NAT     :  residual <= 6 mm  AND  tilt <= 5 deg  AND  margin >= 0.05 rad  AND  pad >= 2 mm
```

with `tilt = acos(-rot[2,2])` (`[attitude]`'s and P73's own expression; 0 deg = the
tool axis straight down), `margin` the smallest joint-limit margin, and `pad` the
pads' lowest point above the surface under them (`tasks._payload_clearance`'s own
`|y| = 0.40` switch). `NAT`'s `tilt <= 5 deg` is the `drift_end` scale, not an
invented number: P66's rung ladder reads **25.1 / 3.4 / 0.7 deg** at 0.36 / 0.24 /
0.20 m.

**The three modes are the point of the design, because the place leg has no attitude
hold** (`_carry` clears `hold_quaternion` for `name != "grasp_lift"`):

* **`T0`** - hold top-down. A survivor here needs a **code change** (a place-leg
  wrist hold), and that lever is already measured **0/16 held** (`logs/p68`).
* **`NAT`** - `hold_quaternion = None`, the position-only solve the shipped leg
  actually runs. A survivor here is shippable **by a station move alone**.
* **`C0`** - the arm's own calibrated belt-aligned `grasp_quaternion`: the P66
  continuity control ("which attitude does the workspace offer").

---

## 2. The answer: **0 of 588 cells pass, in every mode, at both heights, on both arms**

`station_map.txt` has all 588 rows; `cost_map.txt` §5 the tables. Per arm:

| arm | mode | z | **pass** | solved (<= 6 mm) | best **solved** tilt | max margin (any cell) |
|---|---|---|---|---|---|---|
| left | **T0** | 1.450 | **0/49** | **0/49** | **none** | +0.383 @ j4 but **res 290 mm** |
| left | **T0** | 1.530 | **0/49** | **0/49** | **none** | **+0.000153 @ j3** |
| left | **NAT** | 1.450 | **0/49** | 7/49 | **77.75** (the shipped cell) | +0.785 @ j4 (res 15) |
| left | **NAT** | 1.530 | **0/49** | 7/49 | **86.13** | +0.759 @ j6 (res 108) |
| left | **C0** | 1.450 | **0/49** | 2/49 | 82.47 | **+0.037 @ j6** |
| left | **C0** | 1.530 | **0/49** | 3/49 | 81.20 | **+0.041 @ j7** |
| right | T0 | 1.450 / 1.530 | 0/49 / 0/49 | 0/49 / 0/49 | none / none | +0.347 (res 307) / **+0.000137** @ j3 |
| right | NAT | 1.450 / 1.530 | 0/49 / 0/49 | 8/49 / 7/49 | **77.78** / 86.18 | +0.785 (res 14) / +0.758 (res 109) |
| right | C0 | 1.450 / 1.530 | 0/49 / 0/49 | 2/49 / 3/49 | 82.42 / 81.26 | +0.037 @ j6 / +0.041 @ j7 |

**Three readings, and each one alone closes the question:**

1. **`T0` is not a station property at all.** 0/98 per arm at both heights, and at
   the **transfer height the best margin over the whole 49-cell grid is
   `+0.000153 rad` (0.15 mrad)** -
   i.e. not one cell has a single milliradian of headroom. The cells with the
   smallest tilt (7.5 deg at z=1.450, 15.2 at z=1.530) pay **172-192 mm** of
   position for it. This is `logs/p66/STATION_SWEEP.md`'s finding reproduced exactly
   at the other end of the cell - and P66's criterion is the reason both are
   readable the same way.
2. **`NAT` never goes below 77.75 deg where it solves, and the shipped station is
   that best point.** The 6-mm-solvable set is **7-8 of 49 cells**, the box
   `x 0.38..0.48`, `|y| 0.35..0.55`; the shipped `(0.43, 0.50)` is its **outer
   corner**. Every solved cell's tilt is 77.8-108.4 deg - the tool axis is
   essentially horizontal wherever the arm can be.
3. **`C0` fails too, and that is the sharpest statement of all**: the arm's **own
   calibrated** attitude holds at the place station with a best margin of
   **+0.037 rad** (z=1.450) / **+0.041 rad** (z=1.530) against the 0.05 bar, and it
   does not solve to 6 mm at the shipped cell at all (**res 83-105 mm, qerr 45.6 deg,
   margin -0.000 @ j3**). The distinction that matters: `T0` and `C0` are **6-DoF**
   solves (position + orientation) and **both fail to solve at the shipped cell**,
   while `NAT` is the **3-DoF position-only** solve the leg actually runs and it
   arrives with 5.9 mm - i.e. **the station is at the reach boundary and the leg buys
   position with attitude**.

---

## 3. The shipped cell, row by row (the static-vs-live cross-check)

`x = 0.43, |y| = 0.50` - the shipped place point:

| mode | z | res | qerr | **tilt** | margin |
|---|---|---|---|---|---|
| T0 | 1.450 | 109.8 mm | 13.14 deg | 10.02 deg | **-0.000047 @ j3** |
| T0 | 1.530 | **312.1 mm** | **178.07 deg** | 174.6 deg | +0.000011 @ j7 |
| **NAT** | **1.450** | **5.9 mm** | - | **77.75 deg** | **+0.185 @ j4** |
| NAT | 1.530 | 14.9 mm | - | 91.84 deg | -0.000 @ j4 |
| C0 | 1.450 | 83.2 mm | 45.65 deg | 82.4 deg | -0.000 @ j3 |
| C0 | 1.530 | 105.3 mm | 45.86 deg | 71.3 deg | -0.000 @ j3 |

**The instrument reproduces the live record, statically, to 1 deg**: `NAT` at the
place height reads **77.75 deg**, against P73's live `tilt_end` **78.7 deg** at the
same station (`logs/p73/P1_RESULTS.md`) and the release-time payload offset's
implied **87.9 / 91.1 deg** (`COST.md` §2, n = 43 held releases). The three numbers
are one regime: **the tool axis is horizontal at the place station**. And the same
`NAT` row prints `tool_y = +0.628`, which is P66's measured `tool_y +0.65..+0.70`
on the failing place legs - the azimuth included, not just the magnitude.

Two more live-vs-static agreements: `NAT` at the transfer does **not** solve to
6 mm (**14.9 mm**), which is the live leg's own `res_end` **13.3-34 mm**; and `C0`'s
static failure at the shipped cell (**83-105 mm**) is why the live leg arrives
holding position and orientation against each other rather than at a pose.

---

## 4. The cliff: **one 10 mm step, and the shipped point is on it**

`station_map_refine.log` - the shipped column `x = 0.43`, **0.01 m** in `|y|`, both
modes, both heights (104 cells; `station_rows_refine.json`):

| `\|y\|` | NAT z=1.450 res / tilt / margin | NAT z=1.530 res / tilt / margin | C0 z=1.450 res / margin |
|---|---|---|---|
| 0.46 | 6 / 84 / +0.493 | 6 / 90 / +0.469 | 76 / -0.0003 |
| 0.47 | 6 / 82 / +0.525 | 6 / 88 / +0.501 | 78 / -0.0003 |
| 0.48 | 6 / 80 / +0.467 | 6 / 86 / +0.462 | 79 / -0.0003 |
| 0.49 | 6 / 78 / +0.349 | 6 / 85 / +0.342 | 81 / -0.0003 |
| **0.50** | **6 / 77.8 / +0.185** | **15 / 91.8 / -0.0000** | **83 / -0.0003** |
| 0.51 | **19 / 83 / -0.0000** | 19 / 92 / -0.0000 | 86 / -0.0003 |
| 0.52 | 23 / 83 / -0.0000 | 23 / 92 / -0.0000 | 88 / -0.0003 |
| 0.55 | 40 / 83 / -0.0000 | 40 / 91 / -0.0000 | 98 / -0.0003 |
| 0.58 | 59 / 84 / +0.0000 | 59 / 91 / +0.0000 | 112 / -0.0003 |

**The cliff is a single 10 mm step at |y| = 0.50 -> 0.51** (residual 6 -> 19 mm,
margin +0.185 -> -0.0000) at the place height, and between **0.49 and 0.50** at the
transfer height - so at the transfer the shipped station is **already one step past
the cliff**, which is exactly the live `res_end` 13-34 mm. The `x` cliff is the same
kind: along `|y| = 0.50`, `x` 0.43 -> 6 mm, **0.48 -> 46 mm**, 0.53 -> 86 mm. **The
shipped point is the corner of a 0.10 x 0.20 m solvable box and it sits at the
limit in both axes.** And **both** directions make the tilt *worse*, not better:
inboard to `|y| = 0.46` it is **84 deg** (against 77.8 at 0.50), and inboard in `x`
to 0.28 it is **102 deg** - so the shipped point is a **local optimum of the tilt in
both axes**, not a point that happens to be convenient.

---

## 5. Robustness - the negative is not a seed, a tolerance, or a bad starting pose

**A. Re-seeded from the arm's calibrated place pose** (`bin0_above` / `bin1_above`,
`restarts = 3`, 28 cells; `station_rows_seed_{left,right}.json`). P66's
robustness-B test, and its answer is the same:

| arm | mode | result |
|---|---|---|
| left | **T0** | **0/14 pass, `\|margin\| <= 0.060 mrad` on every cell**, residual 42-216 mm |
| right | **T0** | **0/14 pass, `\|margin\| <= 0.003 mrad` on every cell**, residual 32-215 mm |
| **left** | NAT | the re-seed **does** find a lower tilt: **28 deg** at `\|y\| = 0.35` (z=1.450) / **36 deg** (z=1.530), res 11-12 mm, margin +0.24/+0.23 |
| right | NAT | **no** - 87 / 101 deg at `\|y\| = 0.35`, i.e. the left's low-tilt branch is not even arm-general |

So the **only** sub-40 deg attitude the whole phase can produce is the **left's
28 deg at |y| = 0.35** - **5.6x** the 5 deg bar, **1.2x** the 25 deg the shipped
0.36 m rung already carries (P66: `drift_end` 23.8-25.7 deg, range 20.8-28.3) and
**40x** the shipped 0.20 m rung's **0.7 deg** - at a station **75 mm inboard of the slab's
0.425 edge**, i.e. a release into the void (P70 §4: that band has **no surface**
since the rails went). It is not a station; it is a demonstration that the arm
prefers to be off the belt to be upright.

**B. Tolerance.** Relaxing `residual <= 6 mm` to the live leg's own 13-34 mm would
admit cells whose **tilts are 96-120 deg** (x = 0.28-0.33 at z=1.450) - i.e. it
buys *worse* attitudes, not better. The `pad >= 2 mm` clause is **never the binding
term on a solved cell** (the shipped cell reads **+46.3 mm**; the clause fires on
**10 of 588** cells, all of them non-solving, with the pads **-81.0 .. +2.0 mm** from
the surface as the *consequence* of a failed solve).

**C. The `y` direction.** `METHOD.md` §5 said the `y` sweep bounds a capability
because the shipped aim is a fixed `station_y`. That holds here in the strongest
form: **the `y` sweep is the axis that fails fastest** (10 mm), so there is no
unspent `y` freedom to spend.

---

## 6. What this settles, and what it does not

**Settled, with the counts and the cliff:**

* **The place station has no top-down configuration in +-0.15 m** (0/98 `T0` per arm
  at both heights; best margin `+0.000153 rad` at the transfer height; 0/28 re-seeded
  from the place pose).
* **The arm's natural attitude at the place station is 78-108 deg** wherever it
  solves, and **the shipped point is the best of them** (77.75 deg). The station is
  therefore **not improvable by moving it** - the mediator P66 fixes on the lift is
  a **height** effect, and P66 already closed it that way.
* **Even the calibrated belt-aligned attitude has no margin there** (best
  +0.037/+0.041 rad; no 6 mm solve at the shipped cell). The place station is at the
  **reach boundary**, which is what `assets.py`'s own note says ("the reach boundary
  at this height sits at about `y_off = 0.41` from the shoulder, i.e. `|y| = 0.50`").
* **The cost of a move is not the constraint - the gain is** (`COST.md`): the
  crossing is **exactly neutral** on the shipped horizontal transit and **0.30 mm/mm**
  on the direct low lift; the discharge is absolute; the two-line's stations, the
  park gate and the supply are untouched by construction. There is simply **nothing
  to buy**.

**Not shown / named residuals:**

* It is a **static, kinematic** solve - no payload, no controller, no profile, and
  **no output-slab geometry in the scene** (the P66 build), so a residual is
  kinematic and not a contact (`METHOD.md` §5). The `NAT` row is path-dependent in
  the live leg; the 1-deg agreement with P73 and the 3-deg agreement with the
  release-time offset are the cross-checks, not a proof of path equivalence.
* **`x` beyond +-0.15 m was not swept**, and it cannot help: `x` does not enter the
  crossing at all (`_payload_clearance` reads `|y|` and `z`) and the `x` cliff is at
  0.48 - moving `x` outboard is dead in 50 mm and inboard buys nothing.
* The **right arm** was swept as a capability control (it mirrors the left to
  0.05 deg in every mode: 77.75 vs 77.78 deg, 86.13 vs 86.18), so "the right does not need this" is **not** a measurement
  here; the right already places 29/30 at 25.8 deg carry drift (P63), which is the
  record's reason the class is left-only.
* **`z` below 1.450 was not swept.** P70 measured the belt-height lever at
  **0.175:1** with a 40 mm audit ceiling (+7 mm), so the height direction is not a
  place-station lever either; it is a different phase's closed one.

---

## 7. What it changes downstream: **the workstation path closes**

`docs/LEFT_ARM.md` lists three things that can still touch the left's remaining
place-leg loaded slide: **a new pad asset**, **a real-jaw clamp-force anchor**, or
**a workstation move**. This phase is the third one's answer, and it is **negative
with a mechanism**:

* the move cannot deliver a top-down place leg (§2, §3), and
* **even if it could, the rotation is not the measured actuator**: all 8 payload
  losses start **before** the leg's 45 deg crossing at a tilt **below 45 deg**
  (P73), and the **right reaches 107.3 deg and slips 0.0-0.1 mm on 10/10** place legs
  (P73/P74). A station that removed the rotation would remove a mediator the class
  does not read.

So the two sanctions that remain are the **pad asset** and the **force anchor**, and
`logs/p42/SIM_LIMIT.md` is unchanged by this phase. **No registration is written**
(`PREREG.md` is not created): `METHOD.md` §4's rank 1 requires a `NAT` survivor and
there is none; rank 3 - *no cell* - is the outcome, and a measurement cell on an
empty candidate set would be a spend with no hypothesis.

---

## 8. Reproduce, pins

```bash
bash logs/p90/run_p90.sh          # the 588-cell grid (~47 min) + the report
bash logs/p90/run_p90_robust.sh   # the 0.01 m cliff + the re-seed (~15 min)
python3 logs/p90/cost_map.py --check > logs/p90/cost_map.txt   # 7/7 checks PASS
grep -a '\[p90\]' logs/p90/station_map.log | sed 's/^\[fruit\] //' > logs/p90/station_map.txt
```

**Pins** (HEAD `2bd9f9a`; `logs/` is gitignored, `git add -f` at the close-out):
`logs/p90/METHOD.md` **`42bec0f8`** (mtime 22:31:42, pre-run), `station_map.py`
**`edf6f3e8`** (22:32:17), `cost_map.py` **`194880a2`**, `run_p90.sh` **`00a4a498`**,
`run_p90_robust.sh` **`bc55473f`**; `station_map.txt` **`6a36e51c`**, `cost_map.txt`
**`86bbea96`** (this file and `COST.md` are the prose record and are pinned by the
commit, not here); `station_rows.json` **`bb666852`** (588 rows),
`station_rows_refine.json` **`ec20d89b`** (104), `station_rows_seed_left.json`
**`540d0cb7`** (28), `station_rows_seed_right.json` **`6094d7d1`** (28),
`smoke_rows.json` **`49928268`** (2); logs `station_map.log`, `station_map_refine.log`,
`station_map_seed_{left,right}.log`. Tree: `assets.py` **`540406fa`**, `tasks.py`
**`32efa98c`**, `control.py` `9384ff4f`, `motion.py` `7f2443c1`;
`configs/waypoints_oriented.json` `0ea08ebb`, `configs/finger_pads.json` `8d50fdeb`,
`configs/motion_reference.json` **`423896f7`** / `..._twoline.json` **`423896f7`** /
`..._single.json` **`8952c320`** - **all untouched**. `scripts/selfcheck.sh` **PASS,
0 failures**.
