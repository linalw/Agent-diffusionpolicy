# P108 census - where the "24 mm" actually is, and the aperture it implies

Written 2026-11-03, **before the battery** and after the census cells.  Three
instruments, all re-runnable:

| what | instrument | corpus |
|---|---|---|
| the **close-time** aim (the pads on the payload) | `python3 logs/p108/close_aim.py` | **726** `FRUIT_DYNAMIC_TRACE` attempts already on disk |
| the **arrival** offset at the descent's start | `[task] dynamic descent: fruit dy=`, `grep` | **3963** attempts in `logs/p8*/`, `p9*/`, `p10*/` |
| the per-tick split **inside the pads' axial band** | `python3 logs/p108/census.py logs/p108/tr_cage_s5` | **15** traced cage attempts, seed 5 (`tr_cage_s5/`, `census.txt`) |

The traced cell is the P107 cage at 120 mm with `FRUIT_FRUIT_TRACE=2000
FRUIT_FRUIT_TRACE_ARM=1 FRUIT_CYCLE_REPORT=1`.  **It is inert**: its 502
`[fruit]` lines are **502/502 byte-identical** to P107's own `m2b_s5.log` (the
trace, the cycle rows and the `[cage]` rows dropped), and its `[stats]` read
`attempts=15 successes=2 sim=232.0s` - the record's own numbers.  So the
per-tick read did not move the branch it describes (the third time this tree has
measured that for a 3-prim-per-arm read, after P95's 970/970 and 974/974).

## 1. The aim at the grasp is 3-5 mm, and it is *lateral*, not along-belt

`close_aim.py`, 726 attempts, the offset of the payload's centre from the tool
axis at the close's **first** tick:

| quantity | p50 | p95 | max |
|---|---|---|---|
| `|dx|` across the belt | **3.4 mm** | 18.9 | 278 |
| `|dy|` along the belt | **1.1 mm** | 164.7 | 578 |
| radial | **4.5 mm** | - | 2262 |

The p95/max tails are the record's known failure branches (a lost payload, a
chased fruit), not the aim.  **On the cage's own cell the same read is `|dx|`
p50 8.8 mm, `|dy|` p50 20.2 mm** - larger, but still an order of magnitude below
P107's "24 mm off the cage's axis", and with the *lateral* the bigger of the two.

**So P107's 24 mm is not a close-time figure and not a lateral one.**  It is the
**arrival** offset, and its size is the line's own lead, not an error: the
scripted catch hands the fruit over one descent early and the aim is
station-relative by design (`_dynamic_aim` returns the station's `y`, not the
fruit's).

## 2. The arrival offset is 83 mm, and it is ~89 % along-belt

`[task] dynamic descent` prints `fruit dy` at the tick the descent starts, over
**3963 attempts**: **p5 82.0 / p50 83.0 / p90 85.0 / max 99.0 mm** (one outlier
at -1289 mm is a fruit already past).  The row also prints the crossings that
make it what it is: the intercept is shifted **+17.5 mm upstream** of the
station, `t_desc` is 0.68-0.72 s, and the deadline is
`speed * (t_desc + FRUIT_DYNAMIC_DESCEND_MARGIN)` with the margin at its
**0.15 s** default - i.e. **18 mm of the 83 is the descend margin alone**.

The band, which is why the arrival and not the grasp is the binding window: the
cage's plate spans **20.5-80.5 mm below the jaw centre** (`cage_hand`:
`DISTAL_Z` 80.5 - the shipped lip; the plate is 60 mm long) and the payload's
equator sits at 70.0 mm, so a 60-70 mm payload's sphere overlaps the plate's
axial band over **~130 mm of `dz`** - almost the whole 55-60 mm descent.  From
the moment the pads enter that band the horizontal offset is what decides
contact, and the pads enter it **14.5 mm into the descent** (the hover is
`FRUIT_DYNAMIC_HOVER` 60 mm above the grip, so `dz` at the hover is -130 mm
against a band floor of -110 to -115).

Per tick, measured (`census.txt`, the 8 attempts whose descent executed):

| | p50 | p90 | max |
|---|---|---|---|
| `dy` at the band's first tick | **55.8 mm** | 59.4 | 61.7 |
| `dy` max over the window | 55.8 | 73.3 | 108.0 |
| `|dx|` max over the window | 11.8 | **63.3** | 70.4 |
| along-belt share of `|dy|+|dx|` | **83.2 %** | 93.1 % | - |

**The split is along-belt on the typical attempt (56 vs 12 mm) and the tail is
lateral** (60-70 mm of `|dx|` on the attempts whose x-tracking lagged).  That
tail is the fact that decides the *shape*: an oblong aperture is only safe if its
**narrow** axis is still >= 2*(60 + 35) = 190 mm, i.e. if it is not narrow.

## 3. The aperture the census implies

`A = 2 (offset + r + 4 mm margin)`, `r` = the payload's radius (the pool's
`r_max` is 35 mm, the 6.9 cm pear; the cage cell drew 30 mm):

| | p50 | p90 | max |
|---|---|---|---|
| `A_y` along-belt (r = 30) | 171.6 | 206.6 | 275.9 |
| `A_y` with the pool's `r_max` 35 | **181.6** | **216.6** | 285.9 |
| `A_x` lateral (r = 30) | 83.7 | 186.5 | 200.9 |

**Built and scored** (`census.py` §3, every tick of every window, the P107 plate
26 x 60 mm, the pad faces normal to x / y):

| candidate | aperture | pass (>= +4 mm) | min | p50 |
|---|---|---|---|---|
| `cage120` (P107, shipped) | 120 round | **0/8** | -32.7 | -7.8 |
| `round160` | 160 round | 5/8 (62.5 %) | -14.1 | +6.1 |
| `round210` | 210 round | **7/8 (87.5 %)** | +2.7 | +25.3 |
| `oblong 86x210` | 86 x 210 | 5/8 (62.5 %) | -12.2 | +7.5 |
| `oblong 86x160` | 86 x 160 | 4/8 (50.0 %) | -14.1 | +1.3 |
| `asym 86x120/60` | 86, 120 up / 60 dn | 0/8 | -34.2 | -8.7 |

**The oblong does not pay.**  Its narrow lateral axis fails exactly the attempts
the wide one was bought for (the 60-70 mm `|dx|` tail), so it needs a ~190 mm
lateral anyway and stops being an oblong.  The 120 mm cage fails **0/8** - every
attempt is inside the payload's band while the payload is 50-60 mm upstream -
which is P107's 7/15 `clr < 0` reproduced as geometry.

## 4. The neighbours, and the spacing the aperture demands

A pad reaches `A/2 + 10 mm` (plate thickness) from the axis, so an upstream
neighbour of radius `r_nb` is fouled when the along gap is below
`A/2 + 10 + r_nb + 4 mm`:

| aperture | 120 | 160 | **200 (registered)** | 210 |
|---|---|---|---|---|
| required along gap (r_nb 35 mm) | 109 mm | 129 mm | **149 mm** | 154 mm |

The shipped scatter plans **0.10-0.35 m** (`fruits.SUPPLY_GAP_MIN/MAX`), so the
*planned* minimum is 39 mm short of the 200 mm cage's requirement.  **On the
delivered line, in the census's arrival windows, the trace found no neighbour
inside its 0.15 m filter at all (0/8)** - so the delivered gaps met the
requirement in every window that was measured, and the spacing half of option 2
is a *margin purchase on the planned minimum*, not a repair of an observed
collision.  The battery's arms E (200 mm, shipped spacing) and C (200 mm,
`FRUIT_SUPPLY_GAP_MIN=0.15`) measure whether it was needed.

**The registered values** (`PREREG.md`, md5 `7ea66620...`): a **200 mm round**
aperture (`FRUIT_CAGE_OPEN_FACE_R=0.100` - the smallest 10 mm multiple above the
census's need with `r_max`) and `FRUIT_SUPPLY_GAP_MIN=0.150`.  The 200 sits
between the census's p50 (181.6) and p90 (216.6) of the arrival need; the
registration pinned it on the 6-attempt preview, the finished 15-attempt census
reads p90 196.8 mm with `r_max`, so the value is unchanged and now sits at the
p90.

## 5. One thing the census did not explain, named

Seven of the 15 cage attempts stop the descent **30-45 mm above the grasp
depth** (`end=` 57.9-86.1 mm against the shipped hand's 8.1-10.3 mm on the same
seeds, and `z_end` -102 to -77 mm - the pads never got beside the payload).
That is not an aperture datum (the pads are *above* the band), it is the
`descent` leg not executing, and P107 met it too.  It is reported here as a
separate class, and the battery's `[motion] approach ... end=` rows carry it per
cell so the phase can say whether the wider aperture changes it.

## 6. Files

`census.py` (`census.txt`), `close_aim.py`, `tr_cage_s5/` (15 ftrace JSONs),
`cage_s5_traced.log`, `run_p108.sh census`.
