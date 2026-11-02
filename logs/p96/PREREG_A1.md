# PREREG A1 - extension E1: the pre-pose **attitude**, and a static pad witness

Pinned before the extension probe ran. `logs/p96/PREREG.md` (md5
`bb057405aa020378739b4b8e21f5cdcb`) is unchanged; this file **adds** a mode and a
readout, and changes no criterion.

## Why the extension exists

The registered phase-0 grid (PREREG §2) answered its own question - **both**
stations admit a clearance pre-pose at `jaw_z >= belt_top + 0.155`
(`logs/p96/prepose_map.driver`, 74 rows) - but it also showed that the answer
depends on *which attitude* the pose is solved with, in a way the registration
did not pin:

| form | left station, `z = +0.165` | reading |
| --- | --- | --- |
| `T0` (top-down hold) | res 5.9 mm, **margin +0.006 rad @ j3**, qerr 0.7 deg | solves, but sits 6 mrad from the j3 limit - the pose the *shipped* right-station solve already uses at 0.095, and P66's map's own "margin +0.000 on 25/25 cells" |
| `NAT` (position-only) | res 6.0 mm, **margin +0.309 rad @ j2**, jaw +159.0 mm | comfortable, but the achieved attitude is not read by that grid |
| `CFG` (the shipped left pre-pose, teleported) | jaw +102.6 mm, **pad +22.1 mm = 36.4 mm below the tallest fruit's top** | the defect, measured offline for the first time |

The static `CFG` row is the new fact: the shipped left pre-pose's **pad plane**
is 36.4 mm *below* the fruit's top at the calibrated configuration (P95's live
value at the blend's end, `belt_top + 0.029`, is the same structure one blend-lag
above it). The extension therefore has to answer two things before the build:

1. **Which attitude** does the shipped pre-pose actually hold, and which
   attitude should the clearance solve pin? P62's `C0` candidate
   (`configs/waypoints_oriented.json`'s `grasp_quaternion`) reads a tool axis of
   `(+0.8543, -0.5132, -0.0819)` - nearly horizontal - while P95's live geometry
   says the pad plane hangs **80.5 mm** below the jaw at the pre-pose, i.e. a
   **vertical** tool axis. Those cannot both be the pre-pose, so the extension
   measures the achieved attitude of the *calibrated grasp configuration* (the
   actual shipped left pre-pose, i.e. `CFG`) and of each solve mode, and pins the
   mode the build uses.
2. **A static pad witness**: the lowest world point of the two authored finger
   pads (P66's own `pad_lowest_z` against `configs/finger_pads.json`) at the
   candidate pose, so "the pads clear the band" is a static geometry reading and
   not only a live census statistic.

## E1: the grid, the readouts, the criterion

* Modes: **`CFG`** (the calibrated `grasp` configuration, teleported to, settled -
  the shipped pre-pose), **`C0`** (hold the arm's own
  `waypoints_oriented.grasp_quaternion`, solved - "the same attitude, only
  higher"), **`NAT`** (position-only), **`T0`** (top-down, the shipped *right*
  station's hold).
* Grid: each arm at its own station y, `x = cfg.pick_x` (`0.34`), `z =
  0.155, 0.165, 0.18` above the belt top. `restarts = 3` (the robustness form;
  phase 0 used 1).
* New readouts, per row: the **achieved tilt** (`acos(-rot[2,2])`, P73's
  expression, 0 deg = tool axis straight down), the **lowest finger-pad point**
  above the belt top, and the joint margin/joint. Everything phase 0 read is kept.
* **Criterion (unchanged from PREREG §2):** `residual <= 6 mm` AND achieved jaw
  `>= belt_top + z - 6 mm` AND `margin >= 0.02 rad` AND the achieved pad plane
  `>= belt_top + 0.0745` (`jaw >= belt_top + 0.155`).
* **The build's mode** is then: among the modes that pass at `z = 0.165` on
  **both** arms, the one with the **largest minimum joint margin**; ties (within
  0.05 rad) go to the mode whose achieved tilt is **closest to `CFG`'s** - i.e.
  the smallest attitude change from the shipped pre-pose. That rule is fixed
  here, before the run.
* If **no** mode passes on both arms at 0.165, the build uses the next
  registered height (0.155) and, failing that, **F1 fires** exactly as PREREG §2
  writes it (no battery; the transit/park bias is the answer).
