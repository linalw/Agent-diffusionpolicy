# P110 pre-registration - the presentation/centring lane (P108 route 1 + route 2's gate)

Pinned **before any simulator run of this phase**.  Everything below is either a
number from the record (`logs/p108/CENSUS.md`, `logs/p109/RESULTS.md`) or an
arithmetic read of the shipped code (`assets.py`, `conveyor.py`, `tasks.py`,
`cage_hand.py`), and the census that produces the rest is offline
(`logs/p110/census.py` -> `census.txt`, no simulator).

## 0. The question, and what it is allowed to touch

P109 closed the descent-margin route (the margin sets the *sign* of the arrival:
`past_aim` 0/76 -> 79/79, placed 64.5 -> 51.9 %).  P108 closed the aperture
(`clr < 0` 32/51 -> 4/57) and the spacing (starves the single arm).  The term
both phases left named is the **presentation**: the payload is ~56 mm upstream
of the tool axis when the cage's plates are beside it and ~3 mm lateral at that
instant (P108: 55.8 mm along-belt; the lateral is 2.6 mm at the entry and
11.8 mm as a max over the window).  Two forms, and this phase prices both:

* **(a) a passive lateral centring guide** at the picks station;
* **(b) a metering gate / retarder** that holds the fruit's **along-belt**
  position while the belt slips under it - the only form that touches the
  dominant term.

The kill criterion the phase registers up front is the owner's own, from the
brief: **if the gate holds the fruit but the cage still fails to enclose, the
term is not the presentation either** - the end-effector lane closes.

## 1. The census, and the arithmetic that decides each form

### 1.1 The along-belt term is a descent property, not an error

| quantity | value | source |
|---|---|---|
| `fruit dy` (the descent-start gap) | **83.0 mm** p50 (p90 84, max 92) | the printed `[task] dynamic descent` row, 114 descents on this tree's `p108/S_s*` + `p109/M0_s*` cells |
| `deadline` (the hover's exit distance) | 101 mm p50 | the same row |
| `t_desc` / `steps` | 0.69 s / 89 ticks | the same row / `[motion] approach` |
| the entry offset (the pads beside the payload) | **55.8 mm** p50 | P108's trace window; a re-read of the same traces at the last crossing gives 49.8 mm, so the number is a 50-56 mm band |
| the lateral at the entry | **2.6 mm** p50 (max over the window 11.8) | the same traces |

`fruit dy = speed * t_desc` and the margin cancels inside it (P109 section 1),
so **the along-belt term is `speed x the descent's own clock`** - the belt
travels 83 mm while the hand descends 56-60 mm.  The entry offset is the same
quantity minus the part of the leg before the plate's distal face is level with
the payload's top (`s_enter = 0.095 + 0.060 - (0.0805 + 2r)` = 4.5-38.5 mm of
the leg by radius), i.e. **29.7-76.6 mm predicted across the pool** (the
census's table).  The measured 50-56 mm sits below the 63 mm a 6 cm fruit
predicts because the plates **arrest the payload**: 25 % of the band window's
ticks run below half the belt speed (p90 58 %), so the belt is already slipping
under the payload for part of the window.

**Consequence registered here:** the term cannot be reduced by re-timing
(P109 killed the only knob), and it is *not* an error to minimise - it is the
horizontal mouth the ring must present, `A_y = 2 (dy_entry + r)`.

### 1.2 Form (a), the lateral guide: dropped, with its price

A pad face at `A/2` clears a sphere at offset `o` by `A/2 - (o + r)`, so the
aperture need is **per axis**:

| hypothesis | `A_y` (p50) | `A_x` |
|---|---|---|
| shipped (dy 56, dx 12) | **182 mm** | 94 mm |
| a perfect lateral guide (dx -> 0) | **182 mm** | 70 mm |
| a perfect along-belt hold (dy -> 0) | 70 mm | 94 mm |

**A perfect lateral guide removes 0 % of the binding axis.**  It also removes at
most 39 % of the *close-time* radial offset (8.8 of 22.7 mm, P108's cage cell).
The tree already carries lateral guides - `conveyor.containment_parts`' side
fences at x = 0.130/0.430 m, a **0.300 m channel against a 0.160 m delivered
band** - so they never touch a fruit and cannot centre one; a guide that did
would have to be narrower than the band while leaving the open hand its
0.132 m.  **Registered: (a) is not built and not measured.  Its only live
purchase is the close-time lateral, and section 1.4 shows that is not the
binding term either.**

### 1.3 Form (b), the metering gate: what it would have to be

A stationary fruit makes the entry offset the **parking** offset,
`y_park = y_gate_face + r`, so it spans one radius across the pool
(18-35 mm) and `A_y` falls to **70 mm** - the 120 mm cage clears and the 200 mm
hand is not needed.  Three couplings, all read off the code:

1. **The selector cannot see a parked fruit.**  The moving catch's floor is
   `lead 179 + speed*1.5 180 + margin 30 = 389 mm` (`_dynamic_select_floor`);
   the indexed (station-first) window's lower edge is
   `pick_y - 0.02 + prepose_lead = 0.10` m.  A fruit parked at `pick_y` is
   outside both.  So the gate is **a collider + a selection rule + a different
   pick mode** (`FRUIT_DYNAMIC_PICK=0`, the P1 primitive) - not a scene prop.
2. **The rate.**  The belt delivers one fruit per **0.83-2.92 s** (0.10-0.35 m
   at 0.12 m/s); the pick's cycle is **15.1 s/attempt**.  A hold-and-release
   gate queues **8.1 fruit = 1.81 m of belt** per cycle against a **1.60 m**
   belt: a passive gate jams the line within one cycle, and the load on the
   parked fruit is ~10 N of accumulated belt drag.  A real cell answers with a
   magazine (a throttled or stopped infeed), which the tree's directive (the
   belt never stops) forbids.
3. **The release.**  The belt presses the parked fruit into the wall with
   ~1.3 N, so the lift pays `mu_pair * 1.3 ~ 2 N` of extra drag = ~16 % of the
   grip's 12.7 N capacity; and the gate must be at most
   `jaw_at_grip - 0.0805 - belt_top = 14.5 mm` tall or the hand's own tips hit
   it.  Whether a <= 14.5 mm kerb holds a 30-70 mm fruit is the fixture's job.

### 1.4 The enclosure, re-censused (the phase's correction to P107/P108)

`[cage]` rows joined to the descent's own `end=` (74 attempts, the P108 `E`
cells).  The registered endpoint "enclosure at >= 3 pads" is **11/74 = 14.9 %
raw**, but split by *what the row is*:

| class | rule | n | `end` p50 | `aper` p50 | `F` p50 |
|---|---|---|---|---|---|
| blocked-descent **jam** | `end > 15 mm` | **5** | 79.8 mm | 88.1 mm | **1074 N** |
| over-closure **crush** | `aper < dia - 4 mm` or `F > 4*cap*1.5` | **4** | 9.4 mm | 32.5 mm | **119 N** |
| **clean enclosure** | the rest | **2** | 10.2 mm | 63.9 mm | 13.0 N |

**The clean enclosure rate is 2/74 = 2.7 %**, and the two clean rows read
`clr` **-9.5 mm** and **+31.7 mm** - i.e. they do not sit in the large-clearance
class the jams do, so the approach clearance does not order them.  The modal
grasp is **2 pads at the cap** (22/74, `F` p50 9.74 N): a V-block with `n = 2`,
the **same** axial capacity as the shipped two-jaw pinch (P104: `F_crit` is
count-based).

**The closure arithmetic** (one radial synergy, four force-capped position
pads, `a = 0.49 d`, cap 4.90 N, `k = 1e5 N/m`): the elastic allowance is
`cap/k = 0.049 mm`.  A payload offset by `delta` has its near pad commanded
`delta + 0.01 d` **inside** its surface and its far pad `0.01 d - delta`
**short** of contact, so **the far pads reach only when `delta < 0.01 d =
0.6 mm`**; above 0.049 mm the near pads are past their elastic allowance and
push at the cap - the measured `bat_rel` (9-330 mm of payload displacement
during the close) is that launch, not a centring.

**And the line cannot deliver 0.6 mm:** the catch-up's own convergence
tolerance is **6 mm** (`FRUIT_DYNAMIC_CATCH_TOL`), the measured close-time
offset is **8.8 mm lateral / 20.2 mm along** (P108), and a gate's parking
spread is a **0-17 mm radius-dependent** band.  The ring asks for 10-34x
tighter positioning than the line's best.

## 2. What is built and measured, and what is not

**Registered as measured (the fixture, `logs/p110/fixture_gate.py`, no arm, no
`src/` change, a `logs/` probe):** the gate's *physics* on a real belt with a
real pool fruit - the hold, the height that holds, the drag, the crush, the
queue and the release.  Cells (each a fresh fruit from the pool, the belt at
0.12 m/s, the gate authored with mu 2.0 so the pair averages to ~1.65, P104):

| cell | what it answers |
|---|---|
| height sweep `h` in {10, 12, 14, 20, 30, 45} mm x r in {the pool's 8 classes} | **hold or climb**: the parked offset, the climb (`z` rise), and the height where a 30-70 mm fruit is held |
| the drag | the gate's normal force (the belt's drag) and the belt slip at the parked state |
| the crush | the peak contact force on the fruit (there is no bruise model; the number is reported) |
| the queue `N` in {1, 2, 4, 8} at 0.15 m gaps | whether the queue stacks, the load on the front fruit, and whether it buckles off the belt |
| the release | the gate's normal force `N` -> the lift's extra drag `mu_pair * N`, reported against the pinch's 12.7 N |

**Registered as NOT measured, and why:** the **four-seed arm battery**
(seeds 5, 6, 101, 202; arms shipped hand / cage200 / cage200+gate) is *not*
spent, because the kill criterion is met **before** it by an inequality: the
ring needs `delta < 0.6 mm` and the gate's best case is a **0-17 mm**
radius-dependent parking spread on top of a **6 mm** servo tolerance; the
clean enclosure is already **2/74** with the pads *already arresting the
payload* (25 % of the band window below half belt speed).  No arrangement of a
passive element in this cell changes that inequality - the terms live in the
catch's tolerance and the hand's closure, not in the scene.  P47/P48/P49/P51
and P108's own PREREG are the precedent: a census that refutes the lever does
not spend the battery.

**Registered kill criteria (any one closes the lane):**

* **K1** - the guide's `A_y` gain is 0 (measured by construction, section 1.2).
* **K2** - the gate's parking spread (0-17 mm) cannot satisfy the ring's
  0.6 mm closure requirement (section 1.4).
* **K3** - the queue exceeds the belt (8.1 fruit = 1.81 m > 1.60 m).
* **K4** - the fixture finds that a <= 14.5 mm kerb does **not** hold a
  30-70 mm fruit at 0.12 m/s (the fruit climbs), which removes form (b) even
  as a mechanism.

`K1`/`K2`/`K3` are arithmetic and are already met.  **The fixture is spent
anyway**, because it is the only *measurement* the phase can contribute to the
form's price (the brief's "price it: the drag, the range, the release, the
cadence"), and because `K4` is the one clause that a measurement can still
overturn.

## 3. Guards

* **G1** the fixture is a `logs/` probe: no `src/` file changes, so the
  scripted line cannot move.  `scripts/accept.sh` with every knob unset must
  read **8/10, `fingerprint: matches configs/motion_reference.json`,
  `190: PASS`** with its `[fruit]` stream byte-identical to
  `logs/p109/accept_final.log`.
* **G2** `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**;
  `python3 scripts/211_bed_audit.py` **ok (115 checks)**.
* **G3** `configs/` untouched (`30fb99f8` / `30fb99f8` / `8952c320`); no
  reference re-recorded and none owed (nothing ships).
* **G4** the fixture must not perturb the pool: it builds its own scene
  (`SortingScene(cfg)`) and its own spawner, and its fruits are never used by a
  cell, so a fixture run cannot move a record.

## 4. The decision rule

1. If the fixture holds the fruit at `h <= 14.5 mm` across the pool (`K4` does
   not fire), the gate is a **working mechanism** and its price is the queue
   (`K3`, measured) plus the selection rule and pick mode - i.e. a
   **workstation with a magazine**.  Report it as priced-not-shipped, with the
   recommendation being the magazine, not the hand.
2. If it climbs (`K4` fires), the gate cannot exist inside the hand's own
   clearance, and form (b) joins (a).
3. Either way `K1`-`K3` stand, so **the end-effector lane closes**: the
   remaining levers are `docs/LEFT_ARM.md`'s two sanctions (a **new pad asset**
   and a **real-jaw clamp-force anchor**) plus a **compliant closure** (a hand
   change: per-pad compliance so the ring can absorb a 10 mm offset), and the
   owner's decision is which of the three to buy.

## 5. Files this phase will write

`logs/p110/{CENSUS.md,PREREG.md,PREREG.md5,RESULTS.md,census.py,census.txt,
fixture_gate.py,fixture.txt,run_p110.sh,gates.sh}`, plus the AGENTS/WORKLOG
paragraphs and the one-line entries in `docs/HAND_STAGE_PLAN.md` and
`docs/PLATFORM_SURVEY.md`.  `configs/` untouched.
