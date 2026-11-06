# P122 - the destination-separation spec, and the sentence it forces: a destination is a physical output body

Owner's pick: **(1) 目的地间距规范** - how far apart destinations must be, which
axis, and what fits. This is offline: **no simulator run, no `src/` change**, and
it is built from **133 measured releases** across P114/P115/P116/P121
(`logs/p122/spacing.py` -> `spacing.txt`).

The result has two halves, and the second one corrects the record:

1. **Attribution** (the ledger deciding "this payload landed in the destination
   the instruction named") has a measured, simple law: the release offset is a
   **systematic** `(+48, +-35..37) mm` (the payload hangs from the jaw along the
   tool axis) plus a **random** part of sd **6-9 mm in x** and **6-17 mm in y**;
   calibrate the systematic, then **50 mm along x** is enough, and a **diagonal
   (50, 50) is the worst shape** (2.1 % bootstrap, observed 1/23).
2. **A destination is a physical output body.** The descriptor can name any
   number of targets, but two targets on one belt feed the **same tray**: the
   P114/P121 "third destination" is `(0.38, +0.55)` on the **+y belt**, i.e. the
   *same* belt and the *same* tray as lane 0. It is an **attribution demo, not a
   physical third destination**. Physically the cell has **two** destinations -
   the two belts and their own trays (`conveyor._build_discharge`: one tray per
   belt, `center=(tx, by, ...)`).

## 1. The measured offset (release - commanded jaw target), mm

| dest | n | dx mean | dx sd | dy mean | dy sd |
| --- | --- | --- | --- | --- | --- |
| 0 (+y lane) | 44 | **+48** | 8 | **+35** | 6 |
| 1 (-y lane) | 74 | **+48** | 6 | **-36** | 8 |
| 2 (P114/P121 zone) | 15 | +46 | 9 | +37 | **17** |

The systematic is **deterministic** (the tool axis, P90's `payload - jaw =
(+52, +-42..46)`), and it is the same for two zones served by the same leg, so
it cancels **only if the comparison is calibrated**. Compared raw - which is what
the ledger does today - a payload commanded to a zone 50 mm upstream lands
**2 mm from its downstream neighbour's target**.

## 2. The separation curve (bootstrap, 20 000 draws, lane 0's own pool)

| separation | axis | calibrated | raw |
| --- | --- | --- | --- |
| 30 mm | x | 1.47 % | 32.9 % |
| 40 mm | x | 1.47 % | 32.9 % |
| **50 mm** | **x** | **0.00 %** | 32.9 % |
| 60 mm | x | 0.00 % | 32.9 % |
| 100 mm | x | 0.00 % | 3.7 % |
| 150 mm | x | 0.00 % | 0.00 % |
| 50 mm | y | 0.00 % | 32.9 % |
| 75 mm | y | 0.00 % | 15.5 % |
| 100 mm | y | 0.00 % | 2.3 % |

The x axis is the good one (sd 6-9 mm); the y axis is not (the third zone's
sd is 17 mm, and the systematic is 35 mm).

## 3. The layouts, measured against the same pools

| layout | calibrated | raw |
| --- | --- | --- |
| shipped: two lanes, 1.0 m apart in y | 0.00 % | 0.00 % |
| **P114/P121: `(0.38,+0.55)` = a (-50,+50) diagonal, 71 mm** | **2.11 %** | 2.11 % |
| three zones, x-only 50 mm, same lane | 0.00 % | **32.9 %** |
| three zones, x-only 100 mm, same lane | 0.00 % | 3.7 % |
| four zones, x-only 50 mm across the two lanes | 0.00 % | 50.2 % |

The P121 cell read **1/23 = 4.3 %** on its one mis-sort; the bootstrap on the
same pools reads **2.1 %** - the same event at n = 23.

## 4. The spec

**R0 - what a destination is.** A destination is an **output body**: a belt +
chute + tray. Today there are **two** (y = +0.55 and -0.55, each with its own
tray). The descriptor's `destinations[]` names *targets*; a target on an existing
body is the **same physical destination**. A third destination therefore needs
a **third output body**, not a third target - and that is a scene build (which
the owner's constraint allows, because a third belt downstream does not stop,
divert or limit the pick line).

**R1 - attribution spacing.** If two targets ever do share an output body (an
attribution-only zone, e.g. a data label), then:
* **calibrate the systematic** (`+48 x`, `+-35..37 y`) per arm/leg before
  comparing, or compare the release to `target + offset`; uncalibrated zones at
  50 mm are 33 % wrong;
* separate **along x**, not y: **>= 50 mm calibrated** is 0/20 000, **>= 100 mm**
  is 3.7 % raw, and a **(50, 50) diagonal is the worst shape** (2.1 % even
  calibrated, because the y axis carries the 17 mm spread).
* The current ledger is **uncalibrated**: its `nearest` rule compares the
  payload to the **jaw** target, so every release reads ~48/35 mm off. The
  three-destination demo's one mis-sort is exactly that bias.

**R2 - the physical capacity of the current cell.** The place reach is the
binding term, not the spacing: P90's 588-cell map solves `NAT` only in
**x 0.38-0.48, |y| 0.35-0.55**, and the output slab is `|y| 0.425-0.675`. A
third belt at `|y| ~ 0.75` is **outside** that box, so the third destination
needs either a new station (a different x/y with its own solve) or a wider /
dual-lane output body - a station phase, not a spacing number.

**R3 - what "N destinations" costs.** The software side is done (P114-P121: N
targets, the capability map, the ledger, the instruction); the physical side is
**one output body per destination**. Adding the third is a scene build (a belt,
chute, tray, and a station solve); adding a **fourth** on the same side would
need a second place point, which the reach map does not have today.

**R4 - what the ledger should do about it.** Report the **calibrated** offset
(`release - target - mean`) in the `[sort]` row and classify against
`target + mean`, so a zone's drift is visible and a neighbour is not blamed.
That is a small, default-off change to the ledger - the software half of this
spec, and it is what makes P121's third destination read 0 % instead of 2 %.

## 5. Files

`logs/p122/spacing.py`, `logs/p122/spacing.txt` (the tables above), this file.
No `src/`, `configs/` or reference change; no store re-baselined.
