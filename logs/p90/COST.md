# P90 cost map - what a place-station move buys, and what it costs

Companion to `logs/p90/MAP.md` (the sweep) and `logs/p90/METHOD.md` (the criterion,
pinned before the run). Every number here is either **the code's own expression**
(with the site) or **a measurement already in `logs/`**; `cost_map.py --check`
re-derives the arithmetic and asserts the invariants (`cost_map.txt`).

The question this file answers: **for a cell that passes the map, what moves?** The
columns are `logs/p69/B_PREREG.md`'s - gain, crossing, release, discharge, stations,
blast radius - ranked by gain per cost.

---

## 0. The geometry the whole file is computed from

| quantity | value | site |
|---|---|---|
| main belt top | 1.170 | `assets.belt_center` + `belt_size`/2 |
| output slab top | **1.350** | `assets.output_belt_top_z` |
| output slab `\|y\|` / `x` | **0.425 .. 0.675** / 0.10 .. 1.20 | `output_belt_y` +- `size/2` |
| place point | (0.430, **+-0.500**) | `assets.output_place_x/y` |
| `output_place_z` | **1.450** = 1.350 + 0.100 | `assets.output_place_z` |
| place **transfer** z (the leg's end) | **1.530** = 1.450 + 0.08 | `tasks.jaw_target` + `FRUIT_OPENARM_TRANSFER_LIFT` |
| lift end (the place leg's start) | (0.34, **+-0.05**, 1.530 scripted / **1.370** direct-low) | `tasks.jaw_target("grasp_lift")`, `FRUIT_LIFT_DZ` |
| side rails | **removed** (P71) - the crossing's surface is the slab's top plane | `assets.output_rails = none` |
| chute | x 1.200 -> 1.361, z 1.344 -> 1.120 | `assets.output_chute_top/bottom` |
| tray | x 1.350 .. 1.950, `\|y\|` 0.380 .. 0.720, floor **0.92**, rim 1.06 | `assets.output_tray_*` |
| `on_output_belt`'s score test | `\|y\|` 0.365..0.735, x 0.04..1.26, `z >= 1.29` | `assets.on_output_belt(margin 0.06)` |
| two-line pick stations | left (0.34, **0.00**), right (0.34, **-0.10**) | `assets.pick_x/y`, `bimanual` V2/V3 |

---

## 1. The crossing column: **a `y` move is crossing-neutral on the shipped line**

The place leg is a straight line from the lift end to the place target, so

```
t(y)      = (|y| - 0.05) / (|y_place| - 0.05)          [0.05 = the lift end's |y|]
z_cross   = z_lift + t(0.425) * (z_transfer - z_lift)   [the slab's inboard edge]
```

and `d clr = d z_cross` (the payload's lowest point is a fixed offset below the pads,
so only the trajectory's z matters - `d clr/d z = 1`). Computed (`cost_map.txt` §1):

| `\|y_place\|` | t | scripted (lift end 1.530) | direct-low (lift end 1.370) |
|---|---|---|---|
| 0.35 / 0.40 | - | **no crossing** (the leg ends inboard of the slab) | **no crossing** |
| 0.45 | 0.938 | **+0.0 mm** | **+16.7 mm** |
| 0.50 (shipped) | 0.833 | 0 | 0 |
| 0.55 | 0.750 | +0.0 mm | **-13.3 mm** |
| 0.60 | 0.682 | +0.0 mm | **-24.2 mm** |
| 0.65 | 0.625 | +0.0 mm | **-33.3 mm** |

**Two clean facts, and they are the reason this column cannot decide the ranking:**

1. **The shipped scripted transit is horizontal** (`lift end 1.530 == transfer 1.530`),
   so `z_crossing` is **the transfer height for every `y_place`** - moving the station
   along `y` changes the crossing by **exactly 0 mm**. The two-line and the scripted
   acceptance are therefore *crossing-neutral* to a `y` move.
2. **The direct low lift is not**: its transit climbs 0.160 m over ~0.45 m of `y`, so
   `d z_cross/d y_place = -0.30` at the shipped cell - **inboard gains 0.30 mm/mm,
   outboard loses it**. That is the same order as P70's belt-height lever (0.175:1)
   and 3x smaller than the rail (1:1, P71). It is a *sign*, not a budget: no admissible
   move inside the release band (§2) buys more than **+5 mm**.
3. **`x` does not enter the crossing at all** - `_payload_clearance` reads `|y|` and
   `z`, and the trajectory's `z` is a function of `y` alone. An `x` move is
   geometrically free and moves only the leg's length.

---

## 2. The release column: the band is **+-0.12 m** wide, and the offset is the pads, not the arm

Two surfaces have to be separated: `on_output_belt` is a **score** test with 60 mm of
tolerance, while the **slab** is what a payload can actually land on.

| test | `\|y\|` | x |
|---|---|---|
| the slab's own surface | **0.425 .. 0.675** | 0.10 .. 1.20 |
| `on_output_belt` (scores `placed`) | 0.365 .. 0.735 | 0.04 .. 1.26 |

Between 0.400 and 0.425 there is **no authored surface at all** since P71 removed the
inner rail (the main belt is 180 mm below): a release there is a fall scored
`placed=False`, which is the P70 §4 finding.

**The measured delivered point is not the commanded point, and the cause is the pad
standoff - not the arm.** A census of the record's own `[task] over the output belt`
rows (the `jaw=` and `fruit=` fields, every held release, **n = 43 across 7 logs**:
`logs/p70/{C,A,B}.log`, `logs/p71/{both,none}.log`, the acceptance logs):

| read | left (n = 12) | right (n = 31) |
|---|---|---|
| **jaw - target** | x **-1.0 mm**, `\|y\|` **-6.5 mm** | x **-4.0 mm**, `\|y\|` **+1.0 mm** |
| payload - jaw (median) | (+52.0, **+43.0**, -5.5) mm | (+52.0, **-42.0**, +5.0) mm |
| payload - jaw (mean) | (+56.3, +45.7, -2.7) mm, `\|.\|` **72.6 mm** | (+51.8, -41.6, +1.3) mm, `\|.\|` **66.4 mm** |
| implied direction | (+0.775, **+0.631**, -0.037) | (+0.779, **-0.626**, +0.019) |
| implied **tilt** | **87.9 deg** | **91.1 deg** |

So the **jaw lands on the commanded point to 1-6 mm** (P70 §4 attributed the 45 mm to
"the arm's outward overshoot at its reach boundary" - that attribution is **wrong**),
and the payload hangs **~70 mm from the jaw centre along the tool axis**, which at the
place pose is **horizontal** (`tilt 88-91 deg`). The magnitude is the gripper's own
constant: `_pad_standoff` = `FRUIT_FINGER_LEN` 0.060 + `PAD_LIFT` 0.010 = **0.070 m**
(`tasks._pad_standoff`), measured here at 66.4-72.6 mm.

```
delivered = commanded + 0.070 * tool_axis
shipped:  0.070 * (+0.777, +-0.629, -0.01) = (+54, +-44, -1) mm     [measured +52, +-42..46]
```

**Three consequences the ranking uses:**

1. The commanded band that lands the payload on the slab at the shipped attitude is
   **`|y|` 0.378 .. 0.633** (0.425 - 0.047 .. 0.675 - 0.042) - i.e. **+-0.12 m** around
   the shipped 0.50, and the sweep's `y = 0.35 / 0.40` columns are **release-dead**
   along with `y = 0.65` at the delivered point.
2. **A top-down cell removes the offset for free**: `0.070 * tool_axis` with the tool
   axis vertical has **no horizontal term**, so the delivered point becomes the
   commanded point. A rank-1 cell therefore buys ~44 mm of release accuracy *in
   addition* to the tilt, and it loosens the outer bound by exactly that much.
3. The offset grows with the tilt, so an **outboard** move at the shipped attitude
   (tilt ~90 deg) pushes the delivered point past the slab's 0.675 edge 25 mm earlier
   than the commanded number suggests.

---

## 3. The discharge column: **absolute, downstream, cannot move**

The chute and the tray are functions of the **belt**, not of the place point:

```
chute:  x 1.200 -> 1.361   z 1.344 -> 1.120   (angle 55 deg, lower edge 1.12)
tray :  x 1.350 -> 1.950   |y| 0.380 -> 0.720  floor 0.92, rim 1.06
```

`on_output_discharge`'s x band **starts at `output_belt_end_x - 0.05` = 1.15**, i.e.
strictly downstream of the belt's +X end. A place-station move inside
`x 0.28..0.58 / |y| 0.43..0.62` is 0.6-0.9 m upstream of every discharge surface, and
the belt carries the payload there at `output_belt_speed` 0.10 m/s regardless. **The
tray floor 0.92 and the chute end 1.12 do not move** - they are not derived from
`output_place_*` at all.

The one way a station move can reach the discharge is *indirect*: a release that
misses the slab (§2) never gets carried. That is the release column, not this one.

---

## 4. The stations and the blast radius

**The two-line's stations do not move.** `jaw_target`'s place branch reads
`cfg.output_belt_drop_points` and `cfg.output_place_z` and **no `pick_*` field**; the
two-line's stations are `pick_y = 0.00` (left) and `y = -0.10` (right) on the **main**
belt, and its per-arm pre-poses are solved from the pick station. A place-station move
is therefore orthogonal to the scheduler, the supply, the catch and the calibration.
It does move **both arms'** place legs at once (one `+Y` lane, one `-Y` lane, one
`output_place_y`).

**The bimanual park gate cannot be affected either.** `_biarm_payload_clear`
releases the station when the carried payload is `|y - station_y| > 0.28` **or**
`x > 0.52`; on the left's lane (`station_y = 0.00`) the `y` term fires at `|y| = 0.28`
during the *transit*, long before any admissible place point (`|y| >= 0.43`), so the
gate's tick is fixed by the transit and not by the station.

**Blast radius** (the P69-B cost column), all of it shared:

| consumer | what moves |
|---|---|
| `tasks.jaw_target("placeN")` | the commanded place pose |
| `tasks` (`:13596`, `:13680`) | the release target and `_place_low`'s start |
| `rl_env.carry_and_release` (`:1491`) | the direct path's fallback goal (note: it uses `output_place_z` **without** the hand's 0.08 - pre-existing) |
| `rl_env._lift_climb_row` (`:3277-3281`) | the reported crossing fraction (the `f = y_rail/y_place` form) |
| `assets.on_output_belt` / `output_place_z` | the `placed` score and the release height |
| `assets.scene_provenance` (P72) | **has no `output_place_*` field** - a store would not be identifiable by field (a provenance gap, named below) |
| `scripts/20_pick_place.py` (`:168`, `:256`) | print-only (`lane_xy`) |
| every path | scripted, two-line, direct, collector, hybrid canary all share `SceneConfig` |

Two **pre-existing** quirks worth naming because a station move makes them visible:
`rl_env.carry_and_release` omits the hand's 0.08 (it is a fallback helper, not the
shipped path), and `assets.scene_provenance` carries `scene` (rails, belt top, lift)
but **not** the place point - so a post-move store would be indistinguishable from a
pre-move one by field. Any adoption owes that field first (the P41/P58/P72 rule).

---

## 5. The ranking: **there is nothing to rank, and that is the result**

METHOD §4 fixed the ranking rule before the run: **rank 1** = a `NAT` survivor (a
station move alone, no code change), **rank 2** = a `T0`-only survivor (needs a
place-leg hold, measured 0/16 by P68), **rank 3** = no cell. The map's answer
(`MAP.md` §2, `cost_map.txt` §5):

| mode | what it needed | result |
|---|---|---|
| **`NAT`** (rank 1) | `res <= 6 mm`, `tilt <= 5 deg`, `margin >= 0.05`, `pad >= 2 mm` | **0/98 per arm**; best **solved** tilt **77.75 deg** (left) / **77.78** (right), both at the **shipped** cell |
| **`T0`** (rank 2) | `res <= 6 mm`, `qerr <= 2 deg`, `margin >= 0.05`, `pad >= 2 mm` | **0/98 per arm**; at the transfer height the **best margin over 49 cells is `+0.000 rad`** |
| `C0` (control) | same as `T0` | **0/98 per arm**; best margin **+0.037 / +0.041 rad** - the arm's own attitude has no headroom here either |

**So the outcome is rank 3, and the cost columns are not what decides it - the gain
is zero.** That is worth stating explicitly, because the four cost columns all came
back *cheap*:

| column | verdict |
|---|---|
| **crossing** (§1) | **exactly 0 mm** on the shipped (horizontal) transit for any `y`; **+0.30 mm/mm** inboard on the direct low lift, bounded by the release band to **+5 mm** |
| **release** (§2) | the binding column, but it *constrains* rather than costs: commanded `\|y\|` **0.378 .. 0.633**, which the shipped 0.500 sits inside |
| **discharge** (§3) | **cannot move** - chute and tray are downstream in `+x` and absolute (0.92 / 1.12 / 1.35) |
| **stations** (§4) | **untouched** - the place target reads no `pick_*`; the park gate fires at `\|y\| = 0.28` mid-transit; the two-line's pre-poses are solved at the pick station |
| **blast radius** (§4) | the whole `SceneConfig` - but there is no candidate to pay it for |

**Gain per cost = 0 / (small) = 0.** A move is not expensive; it is **empty**.

**The one cell that comes closest, and why it is not a candidate.** The left's
re-seed from the calibrated place pose finds **28 deg** at `(x 0.43, |y| 0.35,
z 1.450)` (`MAP.md` §5). It fails on three counts simultaneously and each is
independently fatal:

1. **28 deg is 5.6x the 5 deg bar**, **inside** the pre-P66 0.36 m rung's own
   carry-drift range (20.8-28.3 deg) and **40x** the shipped 0.20 m rung's
   `drift_end` (0.7 deg) - i.e. it is not a top-down attitude by the record's own
   scale, and it is not even better than the lift the tree already rejected;
2. **`|y| = 0.35` is 75 mm inboard of the slab's 0.425 edge**, in the band that has
   **no authored surface** since P71 removed the inner rail: a release there falls to
   the main belt (`on_output_belt` needs `z >= 1.29`; the main belt is 1.17);
3. **the right arm does not reproduce it** (87 / 101 deg at the same `|y|`), so it is
   one arm's local branch, not a station.

## 6. What an adoption would have owed (priced, not paid)

Recorded so a future lane does not have to re-derive it, and to be explicit that
this is the **cost of a hypothetical**, not a plan:

1. **a `scene` provenance field for the place point** - `assets.scene_provenance`
   carries `output_rails`/`rail_*`/`output_belt.*`/`lift` but **no `output_place_*`**,
   so a store taken after a move would be indistinguishable by field from one taken
   before (§4). That is the P41/P58/P72 rule and it is a precondition, not a cost;
2. **both motion references re-recorded** from same-batch controls
   (`configs/motion_reference.json` / `..._twoline.json`, currently `423896f7`, plus
   `..._single.json` `8952c320` for the `FRUIT_BIARM=0` restore path);
3. **`scripts/accept.sh`** control-vs-move pair on the scripted cell and one two-line
   run through `scripts/190_twoline_gate.sh` - the branch moves by construction (the
   release point changes, and P30-A's precedent is that a geometry change moves the
   solver's ordering);
4. **every store re-baselined** (`demos_v11`, `demos_v12`, `demos_v13p`, `p33_pear`,
   `rl_rollouts/p37_park`) - the release point is in the camera's frame.

None of it is paid, because step 0 - a candidate that buys anything - does not exist.
