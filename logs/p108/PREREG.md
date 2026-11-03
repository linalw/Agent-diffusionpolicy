# P108 pre-registration - the widened cage (aperture + supply spacing), option 2

Pinned **before any battery cell** was run.  The only cells that exist at pin
time are the **census** ones: `logs/p108/tr_cage_s5p` (15 traced attempts, seed
5, the P107 cage at 120 mm) and the offline scans (`logs/p108/census.py`,
`close_aim.py`).  Nothing else.  The md5 of this file is `PREREG.md5`.

## 1. What the owner chose, and what the census changed

The owner's choice after P107's fork is **option 2**: widen the cage's aperture
**and** the supply's along-belt spacing, rather than add a passive centring step
(option 1).  This registration tests exactly that.  It does **not** substitute a
different lever; the two findings below are recorded because they move the
*numbers* the owner's two knobs must take, and one of them (the split) decides
the *shape*.

* **The binding window is the arrival, not the grasp.**  The close-time aim is
  **|dx| p50 3.4 mm / |dy| 1.1 mm / radial 4.5 mm** over the 726 traced attempts
  already on disk (`close_aim.py`), and 5.8 / 20.2 mm on the cage cell.  P107's
  "**24 mm off the cage's axis**" is therefore **not** a close-time figure and
  **not** a lateral one.  The pads are *deliberately* beside the payload for the
  whole descent (the plate spans 20.5-80.5 mm below the jaw and a 60-70 mm
  payload's sphere overlaps that band over ~130 mm of `dz`, i.e. almost the
  entire 55-60 mm descent), and the payload is still **83 mm upstream**
  (`[task] dynamic descent: fruit dy`, **3963 attempts**, p5 82 / p90 85 mm)
  when that descent starts.  Measured per tick in the cage cell: the payload is
  **52.3 mm (p50, max 58.1) upstream** and only **6.7 mm (p50) lateral** when
  the pads' band opens.  **The split is ~89 % along-belt.**
* **So the aperture that matters is along-belt.**  `A = 2 (offset + r + 4 mm)`:
  **A_y = 194 mm** at the census's max with the pool's `r_max` 35 mm, **A_x =
  73 mm** at p50 lateral.  The literal option 2 is a single scalar
  (`FRUIT_CAGE_OPEN_FACE_R`, one knob, no code change), so the cell runs a
  **round 200 mm** aperture; the oblong variant the split licenses
  (86 x 210) is scored in `CENSUS.md` and priced in `RESULTS.md`, not built.
* **The spacing is the aperture's shadow.**  A pad reaches `A/2 + 10 mm` (plate)
  from the axis, so an upstream neighbour is fouled when the along gap is below
  `100 + 10 + 35 + 4 = 149 mm`.  The shipped scatter plans 0.10-0.35 m; in the
  census's own arrival windows **no neighbour was inside 150 mm** (0/6), so the
  requirement is met on the delivered line but the planned minimum is not.

## 2. The cell

The **scripted single arm** (`FRUIT_BIARM=0`) - the two-line scheduler refuses a
non-`openarm` hand by construction, so this is the cage's only home.  Every cell
carries the *same* instrumentation: `FRUIT_CAGE_PROBE=1` (a no-op on the shipped
hand), `FRUIT_MOTION_REPORT=1`, `FRUIT_CARRY_DIAG=1`, `FRUIT_PLACE_TRACE=1`.
`ATTEMPTS=20`, one claim per run.

| arm | hand | aperture | along gap | seeds | purpose |
|---|---|---|---|---|---|
| **S** | shipped `openarm` | - | 0.10-0.35 (shipped) | 5, 6, 101, 202 | the reference: placed count, starved slots |
| **B** | `cage4` | **120 mm** (P107) | shipped | 5, 6, 101, 202 | the aperture control |
| **E** | `cage4` | **200 mm** | shipped | 5, 6, 101, 202 | **the aperture alone** |
| **C** | `cage4` | **200 mm** | **0.15-0.35** | 5, 6 | the owner's full option 2 |

`FRUIT_GRIPPER_KIND=cage4 FRUIT_CAGE_OPEN_FACE_R=0.100` is E; C adds
`FRUIT_SUPPLY_GAP_MIN=0.150`.  Seeds 101 and 202 are **fresh** (P93's rule: two
seeds reuse the same control branches).

## 3. Endpoints

**Primary (the mechanism).**  The **enclosure rate at >= 3 pads**
(`[cage] pads=k/4`, P107's real endpoint, `k >= 3` of 4 pads loaded at 0.5 N):
**E must beat B**, and C must not lose it.  Read per arm over the four seeds,
pooled, with the per-seed table quoted.

**Primary (the no-contact / ejection class).**  `no_contact=1` count and the
`bat_rel` distribution (the payload's displacement **minus the belt's own
travel** over the close).  P107: **1/15 no-contact, 7/15 displaced 15-107 mm,
`clr` negative on 7/15**.  E must move both.

**Secondary (delivered).**  The **placed count** per arm (and per seed), the
interval is not estimable at these counts and is not read; `s/attempt` is
reported as the clock.

**Guards (all must pass).**

* **G1 the landing**: `FRUIT_PLACE_TRACE`'s `on_belt=True` on **every**
  payload-present release (`release_bottom >= 0`; the upstream-lost rows are
  reported separately, P86/P87's rule).  P107's M3 cells had no trace - this
  phase owes it.
* **G2 the budgets**: the descent `|v|max` against the per-leg budget (1.10x the
  profile peak).  P107's cage cells carry 1-2 legs at 1.1x; a *new* class or a
  leg above 1.5x fails.
* **G3 the density**: **starved slots** (`ATTEMPTS - attempts`, the single arm's
  own counter) and the `[bed-sel]` window.  **Kill rule: if C's starved slots
  exceed E's by more than 2 of 20 at either seed, the spacing change has starved
  the line and the route is killed** (P1c's prior: density changes are paid at
  the selector, and the single arm is the one that starves).
* **G4 no-harm**: `scripts/accept.sh` with `FRUIT_GRIPPER_KIND` unset and no
  supply knob must read **421/421 `[fruit]` lines byte-identical** to
  `logs/p107/accept_noharm.log` (the record), `fingerprint: matches`, `190:
  PASS`; `scripts/selfcheck.sh` PASS; `scripts/211_bed_audit.py` ok.
* **G5 the same-tree control**: the S arm at each seed, this batch.

## 4. The kill / the reading rule

* **If E's enclosure rate at >= 3 pads does not rise by >= 30 points over B**,
  the aperture is not the actuator and option 2 is refuted as stated.
* **If E's placed count is below S's by more than 2 of 20 pooled**, the cage is
  still not shippable (P107's M3 kill stands) - the phase then reports the
  geometry as measured, not as adopted.
* **If G3 fires**, the density prior is confirmed on this route and the verdict
  is "the aperture works, the spacing is unaffordable" - which re-opens option 1
  (the passive centring guide) with a measured price.
* **No count is a rate**: every cell is one draw of a rendered-frame loop, and
  the cage's own branch is not bit-identical (P107).  Quote the enclosure class
  and the landed count with n, never a per-mille rate.
* **Nothing is adopted** unless the owner signs off: `configs/` is untouched,
  no motion reference is re-recorded (the cage is default-off and the shipped
  two-line acceptance cannot reach it), and the supply knob is unset by default.

## 5. What this registration does *not* claim

* It does not re-derive P107's 24 mm; it re-reads it as the *arrival* offset.
* It does not test the **oblong** form (86 x 210) - scored offline only.
* It does not test option 1.  `RESULTS.md` prices it.
* It does not measure the two-line (the cage cannot run there, `tasks.py`).
