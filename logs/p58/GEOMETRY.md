# P58 phase 2 (offline): the catchable segment's geometry feasibility map

**Scope.** Offline only - no simulator run, no `src/`/`configs/` edit, no commit,
no rate claim. Every number below is either a **code site** evaluated by
`logs/p58/lever_table.py` or a **log line** parsed by
`logs/p58/segment_census.py`. Raw outputs: `lever_table.txt`,
`segment_census.txt`, `segment_census.json`.

**The question.** The catchable segment is 0.281 m while a pick consumes 1.8 m of
belt. Can geometry make the segment long enough that a selection never finds it
empty, and at what cost?

---

## 1. The arithmetic, from the code

### 1.1 The selector's floor (0.399 m) and its terms

```
tasks.py:5971-6004   _dynamic_select_floor() = lead + v * setup + margin
tasks.py:6065-6086   _dynamic_pick_lead()    = min(v*(0.4 + t_desc + 0.15) + 0.03, 0.80)
tasks.py:6097-6106   t_desc = jerk_limited(FRUIT_DYNAMIC_HOVER=0.06 m, v_max 0.15) = 93 ticks = 0.775 s
assets.py:214-218    belt_speed      = -0.12 m/s
assets.py:236/240/244 spawn_y 0.68 | despawn_y -0.70 | pick_y 0.00
```

At the shipped values: `lead = 0.12*(0.4 + 0.775 + 0.15) + 0.03 = 0.189 m`,
`floor = 0.189 + 0.12*1.5 + 0.03 = 0.399 m` (the value the logs print:
`below catch floor 0.168 < 0.399`, `logs/p57/band_s77.log:412`).

The floor's decomposition (`lever_table.txt`) - this is the decisive table,
because it says *which* part could ever be slack:

| term | metres | % of the floor | knob | slack? |
|---|---|---|---|---|
| selection setup `v*1.5` | 0.1800 | **45 %** | `FRUIT_DYNAMIC_SELECT_S` | **no** - measured 1.467 s (left) / 1.516 s (right), R3 |
| descent `v*0.775` | 0.0930 | 23 % | `FRUIT_DYNAMIC_APPROACH_VMAX` | partly (capped: `j_max` 25 binds at 0.55 s) |
| overhead `v*0.4` | 0.0480 | 12 % | `FRUIT_DYNAMIC_OVERHEAD_S` | no (the arm's settle) |
| lead margin | 0.0300 | 8 % | `FRUIT_DYNAMIC_LEAD_MARGIN` | is the error budget |
| select margin | 0.0300 | 8 % | `FRUIT_DYNAMIC_SELECT_MARGIN` | is the error budget |
| descend margin `v*0.15` | 0.0180 | 5 % | `FRUIT_DYNAMIC_DESCEND_MARGIN` | is the error budget |
| **floor** | **0.399** | | | **80 % of it is measured setup + descent** |

So the segment is short **because the arm takes 1.5 s of pre-pose/transit before
it can take a handover, not because a margin is padded.**

### 1.2 The segment, the residence time, and the required release interval

```
segment   = spawn_y - (pick_y + floor) = 0.68 - 0.399 = 0.281 m
residence = 0.281 / 0.12 = 2.34 s
a pick consumes 15 s * 0.12 m/s = 1.80 m  (the segment is 0.16 of one pick)
```

A body is released **at** `spawn_y` and travels downstream, so it is selectable
for exactly `residence` seconds after its release. **Therefore the segment is
empty at a selection instant iff the last release is older than 2.34 s** - i.e.
the whole occupancy question reduces to one scalar:

> **required release interval ≤ L/v = 2.34 s  (spacing ≤ 0.281 m).**

| supply | design spacing | interval at 0.12 m/s | vs 2.34 s | cover = L/spacing |
|---|---|---|---|---|
| patch sheet (`fruits.py:302-306`) - **the supply every direct number is measured on** (`logs/p58/PREREG.md:27`; the P43/P54 protocol) | slice 0.14-0.22 m | 1.17-1.83 s | **inside** | **1.28** (worst slice) |
| plain scatter (`fruits.py:225-226`) - the **bare code default**, `FRUIT_SUPPLY_PATCH` defaults to `"0"` (`fruits.py:499`) | gaps 0.10-0.35 m | 0.83-2.92 s | **the 0.35 m end is 0.069 m OVER** | **0.80** |
| interlock cap `_BAND_MAX=3` over `[0.35,0.73]` = 0.38 m (`fruits.py:2504-2523`) | 0.127 m | 1.06 s | inside | 2.22 bodies |

**So the answer splits by supply, and that is the first real finding.** Under the
patch sheet - the scenario of record - the design spacing is already **1.28x
inside** the segment: geometry cannot be the thing that empties it. Under the bare
scatter default the segment **is** short by design (a 0.35 m gap leaves it empty
`1 - L/g = 19.7 %` of each interval, ~3 % averaged over `U(0.10,0.35)`), and the
cheapest cure is the **supply** knob that is already measured (`FRUIT_SUPPLY_PATCH=1`,
a spacing of 0.14-0.22 m), not a longer segment: the same 0.069 m costs one
reference re-record from the belt and nothing from the supply sheet.

### 1.3 The approach depth the P57 interlock keeps, and the `_BAND_MAX` ceiling

`_approach_depth()` (`fruits.py:2504-2523`) counts main-belt bodies between
`pick_y + FRUIT_SUPPLY_TARGET_FROM` (**0.35**, `fruits.py:661`) and
`spawn_y + 0.05` (**0.73**), laterally within 0.30 m of the belt centre. So

* the counted window is **0.38 m**, of which **0.049 m sits below the 0.399 m
  floor** (**12.9 %** of the counted window, 17.4 % of the segment: a body there
  counts toward the cap and cannot be selected);
* `_BAND_MAX = 3` (`fruits.py:941`) is therefore a ceiling of **7.9 bodies/m**
  over the window the code actually counts. The P57 note and the code comment
  (`fruits.py:928-941`, `logs/p57/RESULT.md:91`) state "3 / 0.58 m = 5.2/m" -
  **0.58 m is not the window `_approach_depth` counts** (it is the bed's band);
  the correct figure is 7.9/m, against the patch design's 8.9/m, i.e. the cap
  **does bind** at the shipped density.
* Steady state at the cap: spacing `0.38/3 = 0.127 m` -> **2.22 bodies in the
  segment**, well above the 1 needed. Measured: p50 **2** (section 2).
* **The cap binds, and the non-bed interlock DROPS the due slot** (`fruits.py`
  `_next_release = max(_next_release, sim_time + period)`, ~2377-2393) where the
  bed **holds** it (`bed_holds`). **That branch does not touch
  `supply_skipped`**, so the counter is not its evidence (Oracle 2 re-review; the
  counted sites are the clear refusals ~2225/2428 and the patch's **partner-half**
  refusal ~2237-2241). What the log shows (`logs/p57/band_s77.log`): the run's
  first `skipped` reading is **2**, the final **37**; the `[feed]` rows read
  `skipped=+2/+3` on 12 of 14 attempt windows (**29 in-attempt**, ~2 lost
  **bodies** per pick = **~16.3 %** of due slots, mostly **partner halves**), and
  the realised interval at the starved selection is **2.42 s** - above even the
  design period ceiling (0.22 m / 0.12 = 1.83 s), so a due slot was consumed
  without a body: the drop tail is real, **proved by the gap arithmetic, not by
  `skipped`**. Two **free, unmeasured, substitute** knobs act on the same cap and
  are the first response, **one per arm**: `FRUIT_SUPPLY_BAND_MAX` 3 -> 4
  (4/0.38 = 10.5/m) **or** `FRUIT_SUPPLY_TARGET_FROM` 0.35 -> 0.40 (3/0.33 =
  9.1/m, and it deletes the 0.049 m dead sliver). Do not stack them (18/m).

### 1.4 What the catch-up reach budget actually is

`FRUIT_DYNAMIC_CATCH_TICKS` default **200** (`tasks.py:9952`) at 120 Hz = 1.667 s;
the measured closing rate is ~1.0 mm/tick (P48), so the loop erases a residual of
about **0.20 m**. It is **not a term of the floor** - it is the tolerance
downstream of it: `dL/d(budget) = 0`. Resetting it to 100 or 400 ticks changes no
segment length; it changes how far a mis-timed selection can still be rescued
(P48 measured 220-481 mm failures against a 200 mm budget, 3.6-6 mm successes).

---

## 2. The corpus: occupancy at every selection instant

`logs/p58/segment_census.py` over the `[bed-sel]` blocks (`FRUIT_BED_DIAG=1`; each
block lists **every** live body's `along`). `band` = the interlock's 0.38 m
window; `SEG` = `[0.399, 0.68]`; all bodies off the belt excluded
(`bed_diag_report`'s own gate).

| run | selections | band bodies | **SEG bodies** | starved (`window=0`) | band at the starve |
|---|---|---|---|---|---|
| `p57/band_s77` (cadence + interlock) | 16 | 1-3, p50 **3** (dist 1:2, 2:6, 3:8) | **0-3, p50 2** (dist 0:1, 1:2, 2:9, 3:4) | **1/16 = 6.3 %** | **2** |
| `p57/cad_s77` (cadence only) | 17 | 0-4, p50 3 | 0-4, p50 2 (dist 0:2,1:3,2:5,3:5,4:2) | 2/17 = 11.8 % (P57 quotes 2/16 - its transition convention) | 0, 1 |
| `p56/p2/B_1` (continuous, no cadence) | 23 | 0-4, p50 2 | 0-3, p50 1 (dist 0:**8**,1:4,2:8,3:3) | 8/23 = 34.8 % | **0 every time** |
| `p56/p3/Q12_s77` (QUEUE_MAX=12) | 24 | 0-4, p50 2 | 0-4, p50 1 (dist 0:**9**) | 9/24 = 37.5 % | **0 every time** |
| `p56/p2/A_1` (per-pick reset) | 15 | 2-4, p50 3 | 1-4, p50 2 | 0/15 | - |
| `p57/video_band` | 0 | `bed_diag=0` in that run (`video_band.log:390`) - no rows, not usable | | | |

**The split is categorical and it is the answer to part B.** Every starve in the
two *un-interlocked* arms has the band at **<= 1 body** (`cad_s77` attempt 7:
**1**, at +0.383 = 16 mm below the floor; `B_1`/`Q12`: 0) - a genuine supply
miss. The interlocked arm's single starve has **2 bodies in the band, both
below the floor** - a phase miss. Detail (`band_s77.log:549-569`):

* t = 123.06, `on_belt=8`, `admitted=3`, `window=0`; the three upstream bodies
  are peach **+0.221**, tomato **+0.368**, strawberry **+0.390** - i.e. 178 mm,
  31 mm and **9 mm below the 0.399 m floor**, all leaving;
* `pump_next` was 0.21 s ahead (`lag=-0.21`), so the feeder was *early*, not late;
* 0.25 s later (`t=123.31`, one 30-tick wait round, `[cont] pick 9/15: waiting for
  a candidate (round 1/40)`) the retry selected a **freshly released**
  strawberry at **+0.675** - a release lands inside the segment by construction;
* the realised release interval at the miss was `(0.68-0.390)/0.12 = 2.42 s`
  against the 2.34 s budget: **0.08 s = 9.6 mm of spacing over** (delivered
  0.290 m vs the 0.281 m segment = **9 mm over**, not 4) - and at n = 1 the two
  candidate causes are **not separated**: the counted band held 2 bodies (below
  the cap of 3, so no cap-block at that instant) and `lag=-0.21` says the feeder
  was early, yet the delivered spacing was 9 mm over.

So the interlock's residual class is *not* "the belt is out of fruit"; it is "the
last release is 2.4 s old and the next is 0.2 s away", and it costs one 0.25 s
wait round (bounded: the next release is always immediately selectable).

---

## 3. The lever table

`dL` from `lever_table.py` (exact, `_dynamic_select_floor` re-evaluated per row);
`cover` = L / the worst design spacing it must span. `T = L/v`.

| # | lever | one step | dL | L | T | cover (patch 0.22 / scatter 0.35) | measured cost in this repo |
|---|---|---|---|---|---|---|---|
| 1 | **`spawn_y` 0.68 -> 0.749** | +0.069 | **+0.069** | 0.350 | 2.92 s | **1.59 / 1.00** | 1:1, touches neither the floor nor the arm. Bound: the belt's upstream edge is y=+0.80 (`assets.py:201/205`), where 4 of 6 releases fell off (`logs/362_pick_v2.log:402` `released: 6, fell_off: 4`, cited by `assets.py:236-238`). +0.069 leaves 0.051 m to that measured edge -> needs its own fall-off check. Scenario moves -> **both references + acceptance re-record**. |
| 2 | **belt 0.12 -> 0.09 m/s** | -0.03 | **+0.085** | 0.366 | 4.06 s | 1.66 / 1.05 | the catch is v-parameterised, so no constant needs retuning, but the transport must be re-measured (`scripts/170_transport_probe.py`, `logs/173`: 1.01-1.14x at 0.12) and 0.09 is unmeasured (R3 screened 0.12/0.15/0.18 only). Also re-times every arrival -> references + acceptance. |
| 3 | `pick_y` 0.00 -> -0.10 | -0.10 | +0.100 | 0.381 | 3.18 s | 1.73 / 1.09 | **reach-map conflict, see below.** |
| 4 | `FRUIT_DYNAMIC_SELECT_S` 1.5 -> 1.0 | -0.5 | +0.060 | 0.341 | 2.84 s | 1.55 / 0.97 | not slack: the setup is measured at 1.467/1.516 s, and R3's 1.0 s probe binds (1/10 per arm), moves the branch and reads *worse* (8/20, window 2.59 vs 3.63 placed/min). |
| 5 | margins 0.03 -> 0 | -0.03 | +0.060 | 0.341 | 2.84 s | 1.55 / 0.97 | the floor's error budget - exactly what R11-A lost when it deleted the floor: shipped scattered acceptance **9/10 -> 4/10** at a 0.20 m floor, plus the chase/re-seat signature. |
| 6 | descent `v_max` 0.15 -> 0.22 | -0.225 s of `t_desc` | **+0.027** | 0.308 | 2.57 s | 1.40 / 0.88 | capped by `j_max` 25 (0.55 s floor), and the descent is already at the conveyor-collision boundary: 40-90 mm short every leg (`logs/160`, `logs/161`), 23 cm of travel without the belt vs 3.8 cm with it (`logs/166` vs `logs/167`). |
| 7 | **catch-up budget 200 -> 400 ticks** | +1.67 s | **0.000** | 0.281 | 2.34 s | 1.28 / 0.80 | **not a floor term.** Worsens the failure class (P48: it helps the displaced fruit and makes the other three ~200 mm worse). |
| 8 | interlock `_BAND_MAX` 3 -> 6 | +3 bodies | **0.000** (not geometry) | 0.281 | 2.34 s | occupancy 2.2 -> up to 4.4 | cannot accelerate releases past the schedule's own clock; it fills the band and the belt is already saturated (10 releases per 15 s pick against 1 consumed). P56's `queue_max=12` null is the same wall. |

### The `pick_y` conflict, named

The R10-A reach map (`logs/r10/reach_intercept_{left,right}.json`, 6 mm tolerance,
in code at `tasks.py:759-774` with a further 0.02 m `FRUIT_REACH_Y_INSET`) gives,
**relative to the arm's own station**, the grip-clean dy band per lateral column:

| x | left clean dy | right clean dy |
|---|---|---|
| 0.20 | -0.10 .. +0.15 | -0.10 .. +0.10 |
| 0.28 | -0.05 .. +0.10 | -0.10 .. +0.05 |
| 0.36 | **0.00** .. +0.10 | -0.10 .. 0.00 |

A station at `pick_y = -0.10` asks the arm to meet fruit at dy = **-0.10**, which
the **left** holds only at x = 0.20 (x=0.28 floors at -0.05, x=0.36 at 0.00), and
the delivered stream's x is p50 **0.264**, p90 **0.347** (P38; P49's selection-time
max 0.369). So the station move buys 0.10 m of segment by **deleting the outer
half of the delivered lateral band** - and the two-line already pays exactly this
price for its right station at **y = -0.10** (`tasks.py:6718/6731`), which is why
that station is the *right's* and why the left keeps y = 0.00.

---

## 4. Ranking and the single candidate

Ranked by segment gained per unit of cost, with "cost" = what the repo has
already measured for that term:

1. **`spawn_y` +0.069 m** - the only term with `dL/dterm = +1` that touches
   nothing else: not the floor, not the catch, not the arm, not the reach map.
   It is also the only one that converts the measured miss (the strawberry at
   +0.390 would have been at +0.459, selectable).
2. **belt -> 0.09** - the largest gain (+0.085 m, +1.7 s of residence) at a much
   larger blast radius (transport + arrival structure + every timing), and it
   contradicts the direction R3 measured (0.15 was the good point, 0.18 starved).
3. `pick_y` - biggest nominal gain, **vetoed by the reach map**.
4. setup / margins - "gains" are the safety terms; R3 and R11-A both measured the
   cost of taking them.
5. descent - 0.027 m, at the collision boundary.
6. catch-up budget / `_BAND_MAX` - no segment gain at all; one is not a floor
   term, the other cannot outrun the release clock.

**The single lever worth naming is `spawn_y` 0.68 -> 0.749 (+0.069 m, L = 0.350 m,
T = 2.92 s, cover 1.00 on the scatter's worst gap / 1.59 on the patch's).**

---

## 5. The recommendation: **no-go on a geometry probe, pending A's numbers**

> **Oracle 2 remediation (gate 2, attempts 1-2 -> REVISE, text only):** the
> reopen trigger is keyed on the **already-printed census**, never on `skipped`
> (that counter cannot see the interlock's whole-row drop - `fruits.py:2391-2393`
> sets `_next_release`/`queue_hit` and breaks without touching it - and it does
> increment on a partner-half refusal, so it fails in both directions). The key,
> per `window=0` event:
>
> 1. **the `[bed-sel]` block**: the nearest live body's `along` against the
>    0.399 m floor and the `window=` count - `window` **<= 1** = a supply miss;
>    `window` **>= 2** = a phase/margin miss;
> 2. **`lag` / `pump_next`** for the clock (early vs late);
> 3. where a whole-row drop count is wanted, run with **`FRUIT_SUPPLY_DIAG=1`**
>    and read `[supply-diag] ... queue= rel= past= stale= clear= pool=` -
>    `queue=1` **is** the interlock drop (`clear=` the clear refusal). The battery
>    did not enable it, so today's drop split is **unmeasured**.
>
> A geometry probe reopens **only** on a **`window >= 2` miss with `lag <= 0`**
> (a body in the band, the feeder on time, still nothing usable). Any
> **`window <= 1`** miss reopens the **supply** knobs in section 1.3, **one arm at
> a time**.

**The arithmetic of the no-go.** The residual the geometry would remove is one
starved selection in 16, and it costs **one 30-tick wait round = 0.25 s**, because
the next release is always immediately selectable. On the measured **15.1 s** per-pick span
(`[cont]` ticks 27 158 / 15 = 1811 ticks = 15.09 s) that is
`(1/16)*0.25 = 0.016 s/pick = **0.11 %**` of the span. The cheapest lever that
reaches the scatter's design spacing costs **both motion references**
(`8a399626` / `2246f83c`) **+ a scripted acceptance + the two-line gate + a
re-baseline of every direct number** (all of P54/P58-A's corpus becomes
pre-geometry), for a benefit **one order of magnitude** below the 2.7 % the *supply*
fixes already deliver (P56's inter-attempt gap). On the scenario of record the
patch sheet's **design** worst slice (0.22 m) is 1.28x inside the segment - but
the **delivered** spacing at the starved selection measured **0.29 m = 1.03x**
(4 mm over), and its cause is the pump's dropped slots (section 1.3), not the
segment: **the geometry is not the binding term; the delivered tail is a supply
defect.** The one place it *is* short - the bare
scatter default - is owned by a supply knob (`FRUIT_SUPPLY_PATCH=1`) that is free
and already measured, so moving the belt or the release point to cover it would be
paying a geometry price for a supply defect.

**The gate that would flip it,** stated so the decision is not a judgement call:
geometry is worth a probe **iff** P58-A's 3-seed battery leaves the `window=0`
share at **>= 5 %** (i.e. >= 15/16 does not reproduce), or if the `window=0`
events are ever seen with `band >= 1` at a spacing <= 0.28 m (a genuine geometry
margin failure rather than a late release). Otherwise the segment is adequate and
the release clock is the object.

**If the gate opens, the smallest honest probe** (to be registered, not run here):

* **lever**: one constant, `spawn_y` 0.68 -> 0.749 (needs an env hook, e.g.
  `FRUIT_SPAWN_Y`, since the field has none today);
* **knobs held fixed**: the P58-A stack exactly (so the probe measures geometry
  on top of the adopted supply, not instead of it);
* **seeds**: 77 / 101 / 202 (the P54/P58-A convention), one claim, interleaved
  A = shipped `spawn_y` vs B = 0.749, N = 3 x 15-pick episodes;
* **endpoints**: (i) the **band occupancy** - `window>=1` share and the segment
  body count per selection, from `[bed-sel]` (this census is the instrument);
  (ii) a **release-quality check** at the new point - `fell_off`/`respawn` counts
  over the first 16 releases (the only unmeasured risk: 0.051 m to the edge where
  4/6 fell off); (iii) the **placed count reported only**, as a branch;
* **no-harm**: `accept.sh` fingerprint `matches` on re-recorded references,
  `190_twoline_gate.sh` PASS, selfcheck PASS;
* **cost**: one simulator claim of ~3 x 15 picks (~1 h with the episode span at
  9-15 s plus the reset), plus 2 reference re-records, plus the acceptance and the
  two-line gate (~2 x 3 min of sim).
* **kill criterion**: if the `window=0` share does not fall below 5 % on >= 2 of 3
  seeds, the geometry lane closes with the arithmetic above.

---

## 6. Oracle 2 remediation record (gate 2, 2026-10-28)

**Verdict of attempt 1: REVISE** (the NO-GO itself accepted). The material finding
was the drop mechanism above (F1) and the gate key (F2); both are now in
sections 1.3 and 5. The remaining fixes: the dead-sliver fraction (12.9 % of the
counted window, F4), the value arithmetic on the measured 15.1 s span (0.11 %,
not 0.17 %; "one order", not "two"), the design-vs-delivered 1.28x / 1.03x
distinction (F3), the section-2 split restated as **band <= 1 vs band = 2** (F4:
`cad_s77` attempt 7 has band = 1, 16 mm under the floor), and the `logs/p57/
RESULT.md` `skipped` erratum (**37**, not 3) which is now recorded there. Oracle
also verified the arithmetic and both scripts (byte-identical re-derivation) and
confirmed the 0.25 s cost model (same-arm gaps 50, switch 80, the starved pick
110 = 80 + 30) and the 0.775 s descent as a genuine floor term.

**The single reopen trigger (final):** a `window=0` event whose nearest live body
crossed the floor **and for which no release slot was dropped in the preceding
2.34 s**; any `window=0` accompanied by a `skipped` increment reopens the supply
clock (the free knobs), not geometry. A >= 5 % `window=0` rate over P58-A's 3
seeds is the entry condition for *that* A/B.

**Attempt 2 (re-review) -> REVISE, narrow, text-only.** Material corrections
applied: (i) `skipped` is **not** the interlock drop's counter (the branch does
not touch it) - the drop is proved by the gap arithmetic (2.42 s > the 1.83 s
design ceiling), the 37 is mostly **partner-half** refusals (~16.3 % of due
slots), and the run's own first reading is **2**; (ii) the trigger is re-keyed on
the `[bed-sel]` census + `[FRUIT_SUPPLY_DIAG]` `queue=`/`clear=`, **dropping
`skipped`**; (iii) the margin shortfall is **9 mm** (delivered 0.290 vs 0.281),
not 4 - two places; (iv) the "0 bodies in the whole band" sentence is replaced by
"band <= 1" (its own table says `cad_s77` = 1); (v) the two free knobs are
**substitutes** (10.5/m vs 9.1/m against the design's 8.9/m), measured **one per
arm**. Oracle verified the remaining numbers (12.9 % / 17.4 % / 1.28x / 1.03x /
0.11 % / one order) as correct. The last re-review (attempt 3) is held in reserve:
the verdict is unchanged (NO-GO), so it is not spent.
