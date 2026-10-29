# P60 phase 2 — the right arm at `ready` does **not** occlude a fruit at the left's station

**Verdict.** Measured with P35's own scorer, its own rendered masks and the band
the direct line actually delivers, the **inactive right arm at `ready` covers
0.000 of a 58 mm fruit's disc anywhere in the delivered band** — the fire band
(along +0.209…+0.304, `decide` mean/max **0.000/0.000**), the approach
(+0.31…+0.45) and the delivered selection positions (+0.511…+0.680, **0/45**
points ≥ 0.10). Its silhouette hangs over the belt's **downstream** tail
(y −0.196…−0.025, i.e. *after* the pick), so the ≥ 50 % region is
**along −0.42…−0.04** and the cell nearest the station sits 4 cm *past* it. **No
right-arm park lever exists, and none is needed**: the right is already at the
floor of the 53-pose set (the only poses that cover *more* of the decision band
are folds, ≤ 0.118). The mechanism is **closed**. What the same instrument does
leave standing is a *different* occluder: the **left's own hand at its reset
`grasp` pose** covers its own fruit for the last **0.8 s** before the fire
(+0.18…+0.28, station 0.40, decide mean 0.592), while the right's own hand
covers nothing upstream. That is an adjacent finding, not this phase's question;
§7 is explicit about what it can and cannot mean.

---

## 1. Why P35's number did not answer this

P35 swept the **inactive** arm and scored it against a fruit at the pick station
(`scripts/217_arm_park_map.py`). Its `right` rows read 0.00 — and that was read as
"the right arm does not cover *the stream*", i.e. the right-active case, where the
**left** is the parked arm and the left is the one that was measured covering
(0.382 stream, 0.98 at along +0.35). The **left-active** case — fruit at the left's
station, inactive arm = the **right** at `ready` — was never separated, because
the same grid serves both arms in the single-arm presentation
(`pick_x, pick_y = 0.34, 0.00`; the reset teleports the **active** arm to its
`grasp` waypoint at that point, `rl_env.py:2575`, and the two-line's right station
`y = −0.10` is a different scenario). This file separates it, and extends the grid
past P35's `along ≤ 0.55` to the delivered band.

Three independent things also close the loop on the *record*: `configs/arm_parks.json`
has no `right` vector for any name, so on a left-active episode the right arm is at
its shipped `ready` (`_park_poses_label` prints `left:back,right:ready`); P43's left
guard read **1/21 → 0/19** carried-not-placed, i.e. the park move changed nothing on
the left; and P60 phase 1's census (`logs/p60/LEFT_CENSUS.md`) finds the left's
failures are **58/62 carry/hold, not acquisition**. The shared station is measured,
not assumed: phase 1's implied jaw x at the fire tick is **0.340** (left) and
**0.333** (right) — 7 mm apart, both at `pick_x`.

## 2. The delivered band that was scored (from the logs, not assumed)

`logs/p59/p3/C_{77,101,202}.log`, the P59 phase-3 control on the shipped profile:

| read | source row | n | min | p50 | max |
|---|---|---|---|---|---|
| selection `along` | `[bed-sel] … -> chosen` | 45 | +0.511 | +0.586 | +0.680 |
| selection `x` | same | 45 | **+0.201** | +0.287 | **+0.359** |
| fruit `d` | same | 45 | 0.030 | 0.058 | 0.070 |
| **fire** `dy` (along at the decision) | `[rl] episode … intercept trigger` | 45 | **+0.209** | +0.258 | **+0.304** |
| **fire** `dx` (x − station_x) | same | 45 | −0.139 | −0.066 | +0.020 |

Arm split at the fire: left n = 20 (dy +0.209…+0.298), right n = 25
(+0.214…+0.304) — the two arms decide at the same place, so this grid is the right
one for both. **The selection instant is not a perception event**: the +Y output
belt already hides the fruit there (`212` belt-only p50 **0.00** at the 45 chosen
points; ≥ 0.50 visible only up to along +0.48). The **fire** is the instant that
matters, and it is inside the belt-transparent window (belt-only 1.00).

## 3. The map: `right:ready` vs a 58 mm fruit at the left's station

`logs/p60/right_occlusion.txt` §A prints the full **along × x** matrix (the printed
window is x 0.14…0.42 × along −0.30…+0.72; the whole tensor, 15 x × 66 along, is
in `right_occlusion.json` → `parks[*].cover`, flat in `(x, along)`).

Cover is **0.000 at every cell with along ≥ 0.00**, at every x from 0.14 to 0.42 —
that is the whole station, the whole fire band, the whole approach and the whole
delivered selection range. The non-zero cells are all **downstream** of the
station (the first ones going downstream are at along −0.02, max 0.23, reaching
0.66 by along −0.04):

| along | −0.30 | −0.20 | −0.12 | −0.04 | 0.00 | +0.20 | +0.30 | +0.44 | +0.52 |
|---|---|---|---|---|---|---|---|---|---|
| cover (x 0.14…0.42) | 0.45–1.00 | 0.00–1.00 | 0.00–0.95 | 0.00–0.66 | **0.00** | **0.00** | **0.00** | **0.00** | **0.00** |
| belt-only visible | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 |

The geometry is unambiguous and is *why*: the right arm's `ready` silhouette
unprojects to **x 0.050…0.347, y −0.196…−0.025, z 1.316…1.630** — entirely on the
**−y** side of the station line (`y = 0.00`), hanging over the belt's tail. The
camera sits at `y = 0.00`, so a ray to a fruit upstream of the station never passes
through it.

The weaker "does any arm pixel share the fruit's bbox?" form (P34-B's measure,
which cannot tell occlusion from a shared bbox but *can* rule an occluder out
absolutely) agrees at the fire band — `§B3`, arm pixels inside the disc's projected
bbox:

| fruit cell | disc px | bbox | `right:ready` | `left@grasp` | `right@grasp` |
|---|---|---|---|---|---|
| x=0.20, along=+0.30 | 131 | 13×13 | **0** | 72 | 0 |
| x=0.28, along=+0.25 | 127 | 13×13 | **0** | 167 | 0 |
| x=0.28, along=+0.20 | 128 | 13×12 | **0** | 156 | 0 |
| x=0.34, along=+0.30 | 118 | 12×12 | **0** | 0 | 0 |

So `right:ready` is not merely behind the fruit — it is not in the fruit's
neighbourhood at all, at any x, on either measure.

**The ≥ 50 % region and its nearest cell:** along **−0.42…−0.04** (142 grid cells).
The cell nearest the station is **along −0.04 at x 0.38 (cover 0.60)**; the
farthest is along −0.42 at x 0.32 (belt-only 1.00 — a fruit 0.42 m downstream of
the station, past any pick). There is **no** along/x in the delivered band where
the right's `ready` reaches even 10 %.

## 4. All 53 right-arm poses, and the pose comparison

`logs/p60/right_occlusion.txt` §B (each row: hold, px, inter-arm gap, belt
footprint, then the mean cover over the three bands):

| pose | hold (rad) | decide 0.20–0.31 | approach 0.31–0.45 | selection 0.45–0.68 |
|---|---|---|---|---|
| **`ready`** (shipped) | 0.0125 | **0.000** | **0.000** | **0.000** |
| `back` | **0.1741** (fails) | 0.000 | 0.000 | 0.000 |
| `side` | 0.0068 | 0.106 | 0.000 | 0.000 |
| `side_deep` | 0.0051 | 0.023 | 0.000 | 0.000 |
| `fold_70` | 0.0058 | **0.118** (max) | 0.000 | 0.000 |
| `fold_55` / `fold_85` / `fold_hi` | ≤ 0.0067 | 0.070 / 0.057 / 0.053 | 0.000 | 0.000 |
| `low` / `high` / `j*` / `fold_40` | — | ≤ 0.010 | 0.000 | 0.000 |

**The ordered conclusion is the opposite of a lever candidate:** `ready` is at the
*floor* of the achievable set. Nothing in the 53-pose sweep reaches the delivered
band; the poses that reach *most* of it (`fold_70`, `side`, `fold_55`) are poses
that would **add** occlusion (up to 0.118) — a park chosen from this table must not
be one of those. `back`, the left's park, does not exist for the right: it fails
the hold test (0.1741 rad) and puts the fingertip inside the belt footprint
(`ee_tcp`), which is exactly what `configs/arm_parks.json`'s note records.

## 5. The instrument check (why a 0.000 is a measurement)

`logs/p60/right_occlusion.txt` §F re-scores three poses on P35's own grid and
compares with `logs/p35/20_map.json`:

| pose | P35 `stream` | this | P35 `first` | this | P35 +0.35 | this | P35 +0.50 | this |
|---|---|---|---|---|---|---|---|---|
| `left:ready` | 0.382 | **0.382** | 0.144 | **0.144** | 0.98 | **0.98** | 0.00 | **0.00** |
| `left:back` | 0.080 | **0.080** | 0.160 | **0.160** | 0.00 | **0.00** | 0.10 | **0.10** |
| `right:ready` | 0.000 | **0.000** | 0.000 | **0.000** | 0.00 | **0.00** | 0.00 | **0.00** |

Every published statistic reproduces to the rounding on the same masks, so the
0.000 rows are geometry, not a broken scorer. P35's text ("98 % at along +0.35,
57 % at +0.40, `back` → 0.002") is reproduced by the same code path.

## 6. The lever: none, and what it would have needed

* **`configs/arm_parks.json`** (md5 `42ab4fb7`) carries `parks.{back, ready,
  side_deep}` and **every `right` entry is null**.
* **`rl_env.py` needs no change** to accept a right vector: the loader loops
  `for name in ("left", "right")` and stores `entry[name]` when non-null
  (`:1371-1374`), the reset applies `self._arm_park_poses.get(name)` (`:2569`), the
  P35 census reads `self._arm_park_poses.get(inactive)` (`:3414`), and
  `_park_poses_label` already prints the resolved per-arm pose
  (`left:back,right:ready`). A right park would be a **config-only** addition.
* **It is not wanted.** There is nothing to remove: the right's `ready` is 0.000
  across the delivered band and is the *minimum* of the sweep. Adding a right
  vector would move a silhouette that is not in the fruit's sightline; the honest
  close is that this mechanism is empty. (Nothing was edited: no `configs/`, no
  `src/`.)

## 7. What the same instrument leaves standing (adjacent — clearly scoped)

The probe rendered the *non-swept* arm at its `grasp` waypoint in every frame, so
the **active** arm's silhouette is recoverable from the `__active` mask with no new
render. Scoring it on the same grid (`§B2`, `§C`, `§G`):

| pose | silhouette (y) | station (0.00) | decide 0.20–0.31 | clean / hidden runs, belt-visible |
|---|---|---|---|---|
| right@ready (inactive) | −0.196…−0.025 | **0.00** | **0.000** | clean −0.24…+0.44 (5.7 s); hidden −0.38…−0.26 (1.0 s, *past* the pick) |
| **left@grasp** (active) | −0.027…**+0.199** | **0.40** | **0.592** | clean +0.30…+0.44 (1.2 s); **hidden +0.18…+0.28 (0.8 s, right before the fire)** |
| **right@grasp** (active) | −0.173…+0.017 | 0.38 | **0.000** | clean −0.18…+0.44 (5.2 s); hidden −0.28…−0.20 (0.7 s) |

The mirror is exact: each arm's own hand covers the belt on its own approach side
(the left comes from +y, the right from −y), and the decision band is on the **+y**
side for both. At along +0.20…+0.25 the left's own hand reads 1.00 at two of the
three columns (x 0.28/0.34 at +0.20, x 0.22/0.28 at +0.25, ≥ 0.55 at all three);
the right's reaches 0.00 everywhere upstream of +0.05.

**Why this is not this phase's verdict, and not a cause:** these are the poses the
episodes **open** in (`grasp` at reset), not the pose at the fire tick — the policy
drives the arm for the whole 2 s wait, and no run in the record logs the active
arm's pixel share. And the path from occlusion to the left's measured failure is
two steps that the record does not support: the trigger is **encoder/geometry-only**
(`policy/trigger.py`: `dx`/`dy` from the spawner's position, no image), and the
close is the **scripted** primitive run at the fire (`_run_primitive`), so
occlusion cannot move the fire or the close — only the policy's *pre-fire* actions.
P60 phase 1 then finds the left's failures are **carry/hold** (58/62 cnp) and its
close **better** centred than the right's (fingertips 45–52 mm vs 55 mm), which
argues against a perception→seat story. The phase-3 instrument, if this is ever
pursued, is one extra census row: `_park_bbox_census(bbox, side)` already accepts
any arm name, so recording the **active** arm's pixel share at the band calls is a
one-line, default-off diagnostic — it would measure the live wait pose this map
cannot.

## 8. Limits (stated, not implied)

* The map measures **silhouette overlap**, not the policy's attention. A 0.000
  cover rules occlusion **out** of the decision band; it does not establish that
  the policy sees the fruit. P35's own control succeeded with the fruit fully
  invisible in **9 of its 23** right-arm successes, and P36's 2×2 found the
  **image** channel carries the park's win while *which* image statistic remains
  unseparated. Nothing here contradicts either.
* One camera (the shipped head pose), one scene, one rendered frame per pose per
  side (the P35 probe required two identical consecutive frames), fruit modelled
  as a sphere on the belt at `pick_y = 0.00`.
* d = 58 mm is the reference; the 45 mm control moves nothing (the right's `ready`
  stays 0.000, `§C`).
* Counts versus branches: this file contains **no** rate and no outcome claim. Its
  inputs are geometry and log rows.

## 9. Reproduce / provenance

```bash
python3 logs/p60/right_occlusion.py | tee logs/p60/right_occlusion.txt   # ~40 s, numpy only
python3 logs/p60/right_occlusion.py --json logs/p60/right_occlusion.json
```

Pins (`right_occlusion.py` md5 **4d63a226**, `.txt` **6f6d4fa3**, `.json`
**4110a6ba**): `logs/p35/park_sweep.json` 4d15513f, `logs/p35/park_masks.npz`
565e66c8, `scripts/212_occlusion_map.py` 8ca8c97e, `scripts/217_arm_park_map.py`
d73618f9, `configs/arm_parks.json` 42ab4fb7, `configs/waypoints.json` d81c6f1c,
`src/fruit_sorting/tasks.py` 8ad8ddc8, `src/fruit_sorting/rl_env.py` 1b1e5cdf,
`logs/p59/p3/C_{77,101,202}.log` e578abf4 / e01766ed / a7fbdfc8. No `src/`,
`configs/` or `scripts/` edit; no commit.
