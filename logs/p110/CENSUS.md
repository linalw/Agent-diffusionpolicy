# P110 census - the presentation/centring term, measured before anything is built

Written 2026-11-03.  **Offline**: no simulator in this document's numbers except
the two fixtures the phase runs afterwards (which this census *licenses*, not
the other way round).  Re-runnable with `python3 logs/p110/census.py` (its own
`census.txt`), which reads this tree's records:

| input | corpus |
|---|---|
| the printed `[task] dynamic descent` row | **114** descents in `logs/p108/S_s*` + `logs/p109/M0_s*` |
| the `[motion] approach ... steps=` row | the same cells |
| per-tick `FRUIT_FRUIT_TRACE` cells (`FRUIT_FRUIT_TRACE_ARM=1`) | `logs/p108/tr_cage_s5` (15 attempts, 11 executed arrivals) |
| the `[cage]` rows joined to their attempt's `end=` | **74** cage attempts, the P108 `E` cells |
| the supplied band and gaps | `[fruit] [supply] scatter ... gaps=0.10-0.35 m lateral x=0.20-0.36 m` |

The task's premise, restated so the numbers can be checked against it: the
payload is **~56 mm upstream** of the tool axis when the cage's plates are
beside it, **and only a few mm lateral** - an 83-95 % along-belt split.

## 1. The split, and the sign the catch needs

At the tick the pads' axial band opens (P108's window: from the payload's 0.25 m
crossing, with `dz` inside the plate's span, up to the close):

| quantity | p50 | p90 | max |
|---|---|---|---|
| `dy` along the belt, **positive = upstream** | **+55.8 mm** | +59.4 | +61.7 |
| `dx` lateral, at that tick | **+2.6 mm** | +4.1 | +5.0 |
| `dx` lateral, **max over the window** | +11.8 mm | +63.3 | +70.4 |
| along-belt share of `|dy|+|dx|` at the entry | **92.5 %** | 95.5 % | - |

and at the close the payload is within a few mm of the axis (`dy` p50 **-4.7 mm**,
`dx` p50 **-6.0 mm** on this tree's traces - i.e. exactly the catch-up's own
6 mm tolerance; P108's aim census over 726 attempts reads 3.4 mm lateral /
1.1 mm along at the close's *first* tick).  **So the 56 mm is an *arrival* number, not
a grasp number** - the catch-up has already closed it by the time the pads close.

**The sign (P109's guard, which this phase must not break):** the descent must end
with the payload **upstream** of the aim, because the catch-up's first command is
`fruit + v * 0.25 s` = **30 mm further downstream**; a payload 5-8 mm *past* the
aim turns the catch-up into a race it loses (P109: `past_aim` 0/76 -> 79/79,
runaways 0/76 -> 5/79, placed 64.5 -> 51.9 %).  Measured on this tree: the descent
ends with the payload **+10.6 mm upstream** (P109's derived column; the per-tick
traces read ~0 to -5 mm by the *close*, i.e. the catch-up has spent it).

## 2. The 56 mm is `belt speed x the descent's clock`, not an error

`[task] dynamic descent` prints the descent's start gap as `fruit dy` and its
exit distance as `deadline`:

| | p50 | p90 | max |
|---|---|---|---|
| `fruit dy` | **83.0 mm** | 84.0 | 92.0 |
| `deadline` | 101.0 mm | 102.0 | 110.0 |
| `t_desc` / `steps` | 0.69 s / 89 ticks | 0.70 / 91 | 0.80 / 99 |

`intercept = fruit - speed * t_desc`, so `fruit dy = speed * t_desc` and both the
margin and the intercept shift cancel inside it (P109 section 1, confirmed live
there: 83.0 / 82.0 / 83.0 mm at margins 0.15 / 0.075 / 0).  **The belt travels
83 mm while the hand descends 56-60 mm** - the one-way traffic of a moving catch.

The *entry* offset is the same quantity minus the part of the leg before the
plate's distal face is level with the payload's top.  With
`s_enter = 0.095 + 0.060 - (0.0805 + 2r)` (the hover is `FRUIT_DYNAMIC_HOVER`
60 mm above the grip, the jaw at the grip is `belt_top + 0.095`, the plate's
distal face `0.0805` below the jaw):

| `r` | `s_enter` of a 60 mm leg | `dy_entry = speed (t_desc - t_enter)` | `A_y = 2 (dy + r)` |
|---|---|---|---|
| 18 mm | 38.5 mm | 29.7 mm | 95 mm |
| 24 mm | 26.5 mm | 46.2 mm | 141 mm |
| 30 mm | 14.5 mm | 62.8 mm | 186 mm |
| 35 mm | 4.5 mm | 76.6 mm | 223 mm |

The measured 55.8 mm for the pool's mid-size fruit sits **below** the 62.8 mm a
6 cm fruit predicts, and the reason is measured too: **the plates arrest the
payload**.  Inside the band window the payload's own speed is not the belt's -
**25 % of the window's ticks run below half the belt speed** (p90 58 %) - so the
belt is already slipping under the payload for part of the descent.  The
"moving fruit" part of the term is partly spent by the very plates that will
grasp it.

**Consequence, and the phase's first read rule.**  The term is a **descent**
property (its clock) times a **line** property (the belt speed).  Neither is a
presentation element's to change, and it is not an error to minimise: it is the
horizontal mouth the ring must present (`A_y`).  Only *stopping the payload*
removes it - which is form (b).

## 3. Form (a), a passive lateral guide: dead by arithmetic

A pad face at `A/2` clears a sphere at offset `o` by `A/2 - (o + r)`, so the
aperture need is **per axis**:

| hypothesis | `A_y` (p50) | `A_x` |
|---|---|---|
| shipped (dy 56, dx 12) | **182 mm** | 94 mm |
| a perfect lateral guide (dx -> 0) | **182 mm** | 70 mm |
| a perfect along-belt hold (dy -> 0) | 70 mm | 94 mm |

**A perfect lateral guide removes 0 % of the binding axis.**  P108's aperture
screen is unaffected (120 mm passes 0/8 windows, 160 mm 5/8, 210 mm 7/8 - all
computed on `A_y`).  The guide's only purchase is the *close-time* lateral
(8.8 mm p50 on the cage cell) out of a 22.7 mm radial offset: **39 % of a term
that section 5 shows is not the binding one.**

**The tree already carries lateral guides and they prove the point:**
`conveyor.containment_parts`' side fences sit at x = 0.130 / 0.430 m - a
**0.300 m channel against a 0.160 m delivered band** (x 0.20-0.36).  They never
touch a fruit inside the band, so they cannot centre one.  A guide that *did*
centre the band would have to be narrower than 0.160 m, and the open hand
(`±0.066 m` at the band's edges) already needs 0.132 m of it.  **Registered as
not built and not measured.**

## 4. Form (b), a metering gate: what it would do, and what it costs

A fruit held stationary at the station has its entry offset equal to the
**parking** offset `y_park = y_gate_face + (its along-belt half extent)`, so
`A_y` falls to **~70 mm** - the 120 mm cage clears and the 200 mm hand is not
needed.  Three couplings, all read off the code before any build:

### 4.1 The selector cannot see a parked fruit

* **moving catch**: `floor = _dynamic_pick_lead() + speed * FRUIT_DYNAMIC_SELECT_S + margin`
  = 179 + 180 + 30 = **389 mm**.  A fruit at the station is **1/20** of it.
* **indexed (station-first)**: the `station` window's lower edge is
  `pick_y - 0.02 + prepose_lead` = **0.10 m**, so a fruit parked at `pick_y` is
  admitted only with `FRUIT_SMOOTH_TRANSIT_PREPOSE=0`.

The gate is therefore **a collider + a selection rule + a different pick mode**
(`FRUIT_DYNAMIC_PICK=0`, the P1 primitive) - not a scene prop.  The code's own
comment on `FRUIT_STATION_FIRST` ("the gate presents one fruit at a time") is the
pre-v9 line remembering its gate; the dynamic rework left the branch inert.

### 4.2 The rate: the gate queues 8 fruits into a 5-fruit belt

| | value |
|---|---|
| delivered inter-arrival | 0.10-0.35 m at 0.12 m/s = **0.83-2.92 s** (mean 1.87 s) |
| the pick's cycle | **15.1 s/attempt** (P80/P108: 15.0-15.6) |
| fruit queued per cycle | **8.1** = **1.81 m** of belt |
| the belt | **1.60 m** long; the gate's upstream side holds **~5** fruits |

A passive gate jams the line within one cycle.  A real cell answers with a
**magazine** (a throttled or stopped infeed), i.e. the gate *replaces* the
belt's transport - which the tree's directive (the belt never stops) forbids.
The load on the parked fruit is the sum of every queued fruit's belt drag
(~0.1-0.9 N each from the pool's own masses, section 6).

### 4.3 The release

The belt presses the parked fruit into the wall with the drag measured in the
fixture (**0.36-3.36 N peak, p50 1.79; 0.11-1.05 N steady, p50 0.55**), so the
lift pays `mu_pair * F` ≈ **0.16-1.32 N** of extra upward drag - **1.3-10.4 %
of the pinch's 12.7 N capacity**, median **6 %**.  The harder constraint is the *height*:
the hand's lowest solid part at the grip is `jaw - 0.0805` =
**belt_top + 14.5 mm**, so a gate at the station is **<= 14.5 mm tall** against a
pool that spans **29.6-69.6 mm**.

## 5. The enclosure, re-censused - and it is not an aperture or a centring term

This is the phase's correction to P107/P108.  The registered endpoint
"enclosure at >= 3 pads" is **11/74 = 14.9 %** raw.  Joined to each attempt's own
descent `end=` and the ring's own aperture, that bucket is three different
things:

| class | rule | n | `end` p50 | `aper` p50 | `F` p50 |
|---|---|---|---|---|---|
| blocked-descent **jam** | `end > 15 mm` (the plates pressed on the payload) | **5** | 79.8 mm | 88.1 mm | **1074 N** |
| over-closure **crush** | `aper < dia - 4 mm` or `F > 4 cap 1.5` | **4** | 9.4 mm | 32.5 mm | **119 N** |
| **clean enclosure** | the rest | **2** | 10.2 mm | 63.9 mm | 13.0 N |

**The clean enclosure rate is 2/74 = 2.7 %**, and the two clean rows read `clr`
**-9.5 mm** and **+31.7 mm** - i.e. they are not in the large-clearance class the
jams occupy (jams: `clr` p50 +32.9 mm, `F` up to 2920 N).  **The approach
clearance does not order the enclosure.**  The modal grasp is **2 pads at the
cap** (22/74, `F` p50 9.74 N = 1.99 cap-pairs): a V-block with `n = 2`, the same
axial capacity as the shipped two-jaw pinch (P104: `F_crit = n mu N`).

**The closure arithmetic.**  One radial synergy, four force-capped position
pads, command `a = 0.49 d` (the 2 % squeeze), cap 4.90 N, `k = 1e5 N/m`:

* the elastic allowance is `cap / k = **0.049 mm**`;
* a payload offset by `delta` along an axis has its near pad commanded
  `delta + 0.01 d` **inside** its surface and its far pad `0.01 d - delta`
  **short** of contact:

| `delta` | near pad | far pad |
|---|---|---|
| 1.0 mm | 1.6 mm inside | 0.4 mm short |
| 5.0 mm | 5.6 mm inside | 4.4 mm short |
| 10.0 mm | 10.6 mm inside | 9.4 mm short |

**The far pads reach only when `delta < 0.01 d = 0.6 mm`.**  Above 0.049 mm the
near pads are past their elastic allowance and push at the cap; the payload
sticks to the near faces and is *launched* - the measured `bat` (27-82 mm of
payload displacement during the close) and `bat_rel` (0-330 mm relative to the
belt) are that launch, not a centring.

**And the line cannot deliver 0.6 mm.**  The catch-up's convergence tolerance is
**6 mm** (`FRUIT_DYNAMIC_CATCH_TOL`), the measured close-time offset is
**8.8 mm lateral / 20.2 mm along** (P108), and a gate's parking position varies
by **13-22 mm across the pool** (the fixture, measured).  The ring asks for
**10-34x** tighter positioning than the line's best.  **So no presentation
element can enclose this ring**; the term is the closure's architecture (a
single rigid synergy) plus the catch's tolerance, and both are control/hand
properties.

## 6. What each form can remove - the summary the registration reads

| form | band-entry `dy` | `A_y` need | close radial | what it costs |
|---|---|---|---|---|
| none (shipped) | 56 mm | 182 mm | 22.7 mm | - |
| **lateral guide (perfect)** | 56 mm | **182 mm** | 20.2 mm | one funnel; **0 %** of the binding axis |
| **metering gate (perfect)** | <= 35 mm (pool) | **70 mm** | <= 17 mm | selector + pick mode + magazine (8x rate) |

**The guide is dead by arithmetic; the gate works as a mechanism (the fixture
holds 16/16 at 8 mm) and still cannot enclose the ring (0.6 mm vs 13-22 mm).**
The end-effector lane's remaining levers are therefore `docs/LEFT_ARM.md`'s two
sanctions - a **new pad asset** and a **real-jaw clamp-force anchor** - plus a
**compliant closure** and a **sub-millimetre catch tolerance**, none of which is
a presentation element.

## 7. Files

`census.py` (this document's instrument, `census.txt` its output),
`fixture_gate.py` + `run_p110.sh` + `p110_report.py` (`fixture.txt`), the cell
logs `fix_*.log`, `PREREG.md` + `PREREG.md5`.
