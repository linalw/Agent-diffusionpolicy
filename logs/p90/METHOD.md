# P90 method - the output place-station map (the criterion is pinned here, before the run)

**Status: registration only, written before `station_map.txt` exists.** Nothing below
is a result. The pass clause, the grid, the modes and the ranking rule are fixed
here and the pin is recorded at the end; the run follows (`station_map.py`).

The owner's choice for this phase is the **workstation / station-layout path**, and
the question it has to answer is geometric and offline-answerable:

> **Is there an output place station where the LEFT arm can hold the top-down
> attitude through the place leg - and what does moving the line there cost?**

The precedent is `logs/p66/STATION_SWEEP.md`: a 150-cell static IK sweep over the
**pick** band which found **no** point where the top-down `T0` holds with
`qerr <= 2 deg AND margin >= 0.05 rad AND pad >= 2 mm` (`T0` 0/75 of its own cells;
`margin >= 0.01 rad` on **1/75**), and no point at all at the height the lift ends.
The same instrument is built here for the **place** station.

---

## 0. What the phase is for, stated with the prior that governs it

The brief's premise is the chain `logs/LEFT_ARM.md` records: the left's remaining
losses are **place-leg** loaded slides (`logs/p66/P2_RESULTS.md` §"the residual is
not the lift": `cnp`s with `tilt` 75-91 deg and `tool_y +0.65..+0.70`), the escape
is 25.2 deg off the **tool axis** (`logs/p61/P2_RESULTS.md`), and the azimuth of
the carry tilt is the **belt axis on the left** (`logs/p63/P2_RESULTS.md`) - i.e.
to reach the output line the left must rotate ~90 deg.

**Two measurements already bound what a positive map could mean, and they are
quoted here so the map is not read as more than it is:**

1. **The rotation is not the measured actuator of the class.** `logs/p73/P1_RESULTS.md`
   moved the transfer height (`FRUIT_OPENARM_TRANSFER_LIFT` 0.08/0.14/0.20) and the
   achieved place-leg rotation went **the wrong way** (`tilt_end` 78.7 -> 93.8 ->
   105.2 deg) while the class stayed **flat (1 / 1 / 1)**; **all 8** payload losses
   started **before** the leg's 45 deg crossing, at a tilt below 45 deg, and the
   **right arm reaches 107.3 deg and slips 0.0-0.1 mm on 10/10** place legs. So a
   *cessation of the rotation* is not the actuator this interface measures.
2. **The place leg has no attitude hold.** `_carry` clears `hold_quaternion` for
   `name != "grasp_lift"` (`tasks.py`), so the place leg is a **position-only** 3-DoF
   solve. A cell where the arm can hold `T0` *only when commanded* therefore needs a
   code change (a place-leg wrist hold) - and that lever is **already measured
   catastrophic**: `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=1.0` reads **0/16** held
   (`logs/p68/RESULTS.md`). A cell where the arm's **natural** (no-hold) solve is
   already top-down needs **no code change at all**.

That distinction is the spine of the ranking (§4): **`NAT` survivors are shippable
by a station move; `T0`-only survivors are not shippable without re-opening a lever
the record has closed.**

---

## 1. The pose under test (read from the code, not assumed)

The place leg's commanded target is `tasks.jaw_target(side, "placeN")`:

```
px, py = cfg.output_belt_drop_points[N]      = (output_place_x, +-output_place_y)
z      = cfg.output_place_z                  = output_belt_top_z + output_place_clearance
       + FRUIT_OPENARM_TRANSFER_LIFT (0.08)  [OpenArm hand only]
```

with the shipped values (`assets.py`):

| quantity | value | site |
|---|---|---|
| `output_belt_top_z` | **1.350** | `assets.py` (P70 knob, default) |
| `output_place_clearance` | 0.100 | `assets.py` |
| `output_place_z` | **1.450** | `assets.py` `output_place_z` |
| `output_place_x` / `output_place_y` | **0.43** / **0.50** | `assets.py` |
| the **transfer** z (place target) | **1.530** = 1.450 + 0.08 | `tasks.py` `jaw_target` |
| `output_belt_y` / `size` | 0.55 / (1.10, 0.25, 0.05) | `assets.py` |
| slab inner edge `|y|` | **0.425** = 0.55 - 0.125 | `tasks._output_belt_edge_y` |
| slab outer edge `|y|` / x range | 0.675 / 0.10..1.20 | `assets.py` |
| `output_rail_proud` | 0.035 (rails **removed** since P71) | `assets.py` |
| lift end (place leg's start) | 1.530 (scripted) / **1.370** (direct default) | `tasks.jaw_target("grasp_lift")` |
| main belt top | 1.170 | `assets.belt_center/size` |

**Two heights are swept, and they are the two the config actually produces:**

* **z = 1.450** - `output_place_z`, the place *height* (`_place_low`'s descent runs
  from here down to the payload at 1.375);
* **z = 1.530** - the **transfer** the place leg ends at (the shipped pose).

---

## 2. The grid

Around the shipped place point `(0.43, +-0.50)`, **+-0.15 m in each axis**:

```
x  in {0.28, 0.33, 0.38, 0.43, 0.48, 0.53, 0.58}               (7, step 0.05)
y  in +-{0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65}             (7, step 0.05)
z  in {1.450, 1.530}                                           (2)
arm in {left (+y lane), right (-y lane)}                       (2)
```

**7 x 7 x 2 x 2 = 196 points per attitude mode.** The 0.05 m step is the P66
sweep's own cell size ("fine enough to see the cliff"), and the edge columns sit
exactly at the two surfaces the cost map cares about (`y = 0.35` is inboard of the
slab's 0.425 edge; `y = 0.65` is 25 mm inside the slab's 0.675 outer edge).

## 3. The modes, and the criterion - **pinned before the run**

Three modes, all solved from the **same seed**: the arm's own `grasp_lift`
configuration (`configs/waypoints_oriented.json`), because that is the
configuration the place leg actually starts from.

| mode | `hold_quaternion` | what it asks |
|---|---|---|
| **`T0`** | the top-down attitude: `logs/p62/candidates.json`'s `T0` for the left, `mirror_across_xz(T0)` for the right | **the brief's question**: can the arm hold top-down at this station? |
| **`NAT`** | `None` (position-only, as the shipped place leg runs) | **what the place leg would actually achieve** at this station, with no code change |
| **`C0`** | the arm's `configs/waypoints_oriented.json` `grasp_quaternion` | the P66 continuity control: is the *belt-aligned* attitude trivially holdable here (the arm's fall-back) |

Solve: `ArmController.solve_to(target, iterations=400, tolerance=6 mm,
restarts=1)` - the P66/P62 recipe, unchanged. Reads per cell: residual,
`qerr` (achieved vs the **commanded** attitude, deg), the achieved **tilt**
`acos(-rot[2,2])` (0 deg = tool axis straight down = `T0`; this is `[attitude]
tilt`'s and P73's own expression), the smallest joint-limit margin and its joint,
the pads' lowest point above the surface under them (the existing clearance model:
`configs/finger_pads.json` capsules composed with the live finger-link poses, the
surface switching at `|y| = 0.40` exactly as `tasks._payload_clearance` does), and
the jaw-opening axis' z.

**The pass clause (P66's, plus the residual tolerance the brief asks for), for
`T0` and `C0`:**

```
PASS  <=>  residual <= 6 mm  AND  qerr <= 2 deg  AND  margin >= 0.05 rad  AND  pad >= 2 mm
```

**For `NAT` the `qerr` clause is undefined** (there is no commanded attitude), so
its clause is the same clause with the achieved attitude standing in:

```
PASS_NAT <=> residual <= 6 mm AND tilt <= 5 deg AND margin >= 0.05 rad AND pad >= 2 mm
```

`tilt <= 5 deg` is chosen as the top-down tolerance because it is the scale
`drift_end` is read on (`logs/p66/P3_RESULTS.md`: the shipped 0.36 rung reads
**25.1 deg**, the 0.24 rung **3.4 deg**, the 0.20 rung **0.7 deg**) - a cell
either delivers a `drift_end`-grade attitude or it does not.

**Robustness (a second run, on survivors and near-survivors only):** re-solve `T0`
from `bin0_above` / `bin1_above` (the calibrated place seed) with `restarts=3`, and
bisect the cliff at 0.01 m along the best row. A survivor that does not reproduce
from the place seed is a seed artefact, not a station.

## 4. The ranking rule (fixed here, applied in `COST.md`)

For every passing point, the cost columns are the ones `logs/p69/B_PREREG.md` used,
and the ranking is **gain per cost**:

| column | how it is computed | why it is the right measure |
|---|---|---|
| **the tilt gain** | `tilt_NAT(shipped)` - `tilt_NAT(cell)` (deg), or for a `T0`-only cell, `tilt(C0 fall-back) - 0` | the mediator P66/P73 read |
| **the crossing** | `d(z_cross)/d(y_place)` from the straight-line leg at the slab's edge `|y| = 0.425`, relative to the shipped cell - **payload-free**, so it needs no body model | P70/P72's measured surface |
| **the release** | whether the release lands on the slab (`|y| in [0.425, 0.675]`, `x in [0.10, 1.20]`), including the **measured +42..47 mm outward overshoot** at the shipped station (`logs/p70/RESULTS.md` §4) | `on_output_belt` is the `placed` score |
| **the discharge** | the chute (x 1.20 -> 1.36) and the tray (x 1.35..1.95, `|y|` 0.38..0.72, floor 0.92) are **downstream in x** and **absolute** - a place-station move must not touch them | the brief asks explicitly |
| **the two-line stations** | the pick points are `(0.34, 0.00)` left / `(0.34, -0.10)` right; the place station is a different pose entirely | a place move must be orthogonal |
| **the blast radius** | `assets.SceneConfig` -> every path (scripted, two-line, direct, collector, canary) + `on_output_belt`/`output_place_z` -> `placed` | the P69-B cost column |

**Rank 1** = a cell whose `NAT` solve is top-down (no code change); **rank 2** = a
`T0`-only cell (needs a place-leg hold, which P68 measured 0/16); **rank 3** = no
cell. Tie-break on the smallest blast radius, then on the largest crossing gain.

---

## 5. What this map is not

* It is a **static, kinematic** solve: no payload, no controller loop, no profile,
  **and no output-slab geometry in the scene** (the P66 build, so the residual is a
  pure kinematic residual and not a contact). The pad clearance is the analytic
  read, exactly as P66's; it is therefore *reported*, not gated by physics.
* The `NAT` row is **path-dependent in the real leg** (the IK null space follows the
  configuration the leg arrived with). A static solve from the lift's own
  configuration is the closest static analogue of that, and it is what P66's
  robustness B used; the live cross-check is P73's `tilt_end` 78.7-105.2 deg at the
  shipped station, which the `NAT` row must land near or the instrument is wrong.
* A site is a **necessary** condition, not a sufficient one. §0 says why: the
  rotation is not the measured actuator of the class, so even a rank-1 survivor must
  be argued against P73's falsifier B - which is why the deliverable is a map plus,
  at most, **one** registered measurement cell, and why a negative map closes the
  path rather than the class.
* `x` does not enter the crossing's height at all (`_payload_clearance` reads `|y|`
  and `z`), so an x move buys nothing geometrically; it is swept because it moves
  the leg's length and the arm's reach.

## 6. Pins at registration

Tree HEAD `2bd9f9a`. The probe is a **copy** of `logs/p66/ik_probe_sweep.py`
(itself a copy of `logs/p62/ik_probe.py`), so the P62/P64/P66 artifacts stay
byte-reproducible. No `src/` edit, no `configs/` edit, no default change, no
commit.
