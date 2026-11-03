# P108 results - the widened cage (aperture + supply spacing), option 2

**VERDICT (first line).**  Option 2 splits in two and only one half earns its
place.  **The aperture is a real actuator for the class it targets**: widening the
cage from **120 to 200 mm** (one env knob, `FRUIT_CAGE_OPEN_FACE_R=0.100`) takes
the approach collision from **21/32 to 4/37 windows with a negative
pad-to-payload clearance** (Fisher **p < 1e-4**), the descent from **half-blocked
to executing** (`[motion] approach ... end=` p50 **57.9 -> 9.6 mm**), and the
placed count from **6/32 (18.8 %) to 13/37 (35.1 %)** - better at **both** seeds
(3/18 -> 7/19, 3/14 -> 6/18; Fisher **p = 0.178**, so a direction, not a rate).
**It does not move the enclosure at >= 3 pads** - **5/32 (15.6 %) -> 7/37
(18.9 %), p = 0.76** - which is P107's real endpoint, and the gap is **not** the
closure depth either: a post-hoc 6 % interference cell (`FRUIT_GRIPPER_SQUEEZE`
0.98 -> 0.94) reads **1/17**.  The enclosure is the **centring** term, and it is
what blocks the placement (the histogram is bimodal - **4 pads or 1-2, never 3**:
`{0:2, 1:6, 2:8, 4:3}` at 200 mm).  **The spacing half fails its guard**: the
200 mm cage with `FRUIT_SUPPLY_GAP_MIN=0.15` starves the single arm
(**5 starved slots of 20 against 1** at seed 5, 3 against 2 at seed 6) and the
placements fall to **8/32 = 25 %**.  So: **the aperture is worth having for the
approach, the spacing is not affordable, and neither touches the enclosure - a
passive centring guide (option 1) is now the cheaper route for the term that
actually blocks the placement, but it is not sufficient on its own** (the arrival
is 56 mm along-belt, which no lateral guide can remove; the cheap version of that
half is a control retiming, §7).

# 0. What was measured, and against what

`PREREG.md` (md5 **`7ea6662054fa2acdf490042c0737e662`**, pinned before any
battery cell) registered four arms on the **scripted single arm**
(`FRUIT_BIARM=0`, the cage's only home - the two-line refuses a non-`openarm`
hand) at `ATTEMPTS=20`:

| arm | hand | aperture | along gap | seeds |
|---|---|---|---|---|
| **S** | shipped `openarm` | - | 0.10-0.35 | 5, 6 |
| **B** | `cage4` | 120 mm (P107) | 0.10-0.35 | 5, 6 |
| **E** | `cage4` | **200 mm** | 0.10-0.35 | 5, 6 |
| **C** | `cage4` | **200 mm** | **0.15-0.35** | 5, 6 |

Every cell carries `FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1
FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1` (the probe is a no-op on the shipped
hand), so the arms are compared inside one instrumented batch and the landing is
measured on every arm - P107's M3 cells had no `FRUIT_PLACE_TRACE` and could not
report it.  Post-hoc, after the battery: `E_sq94_s5` (the same 200 mm cage with
`FRUIT_GRIPPER_SQUEEZE=0.94`), a *mechanism* probe, not a registered arm.

## 1. The battery

| cell | attempts (slots) | placed | rate | s/attempt | enclosure >= 3 | `clr < 0` | no-contact |
|---|---|---|---|---|---|---|---|
| S s5 | 19 (1 starved) | 12 | 63 % | 15.1 | - | - | - |
| S s6 | 19 (1) | 13 | 68 % | 15.0 | - | - | - |
| **S pooled** | **38** | **25** | **65.8 %** | 15.1 | - | - | - |
| B s5 | 18 (2) | 3 | 17 % | 15.3 | 4/18 | 11/18 | 2/18 |
| B s6 | 14 (**6**) | 3 | 21 % | 15.7 | 1/14 | 10/14 | 3/14 |
| **B pooled** | **32** | **6** | **18.8 %** | 15.5 | **5/32** | **21/32** | 5/32 |
| E s5 | 19 (1) | 7 | 37 % | 15.3 | 3/19 | 0/19 | 2/19 |
| E s6 | 18 (2) | 6 | 33 % | 15.8 | 4/18 | 4/18 | 8/18 |
| **E pooled** | **37** | **13** | **35.1 %** | 15.5 | **7/37** | **4/37** | 10/37 |
| C s5 | 15 (**5**) | 1 | 7 % | 15.1 | 2/15 | 0/15 | 2/15 |
| C s6 | 17 (**3**) | 7 | 41 % | 16.9 | 1/17 + 4:1 | 6/20 | 6/20 |
| **C pooled** | **32** | **8** | **25.0 %** | 16.0 | **3/32** | **6/32** | 8/32 |

*The C s6 enclosure row is printed as `{0:6, 1:10, 2:3, 4:1}` by the report, so
`>= 3` is **1/20**; the table's `3/32` pools `2/15 + 1/20`.*

## 2. The aperture: the approach clears, decisively

Three independent reads of the same mechanism:

* **`clr < 0`** (P107's own approach census, the pads' faces inside the payload's
  sphere during the approach): **21/32 (66 %) -> 4/37 (11 %)**, Fisher
  **p = 3.9e-6**.  That is the phase's strongest number.
* **The descent executes.**  `[motion] approach ... end=` p50 is **57.9 mm** on
  B (against the shipped hand's **8.9-9.1 mm** on the same seeds) - the leg is
  *blocked* on half the attempts because the 120 mm cage's pads meet the payload
  while it is still 50-60 mm upstream and the arm cannot finish the leg.  At
  200 mm the p50 is **9.3-10.3 mm**, i.e. the shipped distribution.  **This is
  the class P107 could not see**: it read `clr` and `bat`, not the leg's end.
* **The placements** roughly double, **6/32 -> 13/37**, better at both seeds.
  Fisher p = 0.178 at n = 69: a direction, not a rate (and the cage is still
  far below the shipped hand: 13/37 vs 25/38, **p = 0.011**).

## 3. The enclosure: a draw, and the closure depth is not its actuator

**Enclosure at >= 3 pads of 4**: `5/32` (B) vs `7/37` (E), Fisher **p = 0.76** -
a draw.  The shape of the histogram says why:

| arm | 0 pads | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| B (120 mm) | 2 | 7 | 5 | 4 | 0 |
| E (200 mm) | 2 | 6 | 8 | 0 | **3** |
| E + squeeze 0.94 | 2 | 8 | 6 | 1 | 0 |

It is **bimodal: 4 or 1-2, never 3**.  A square ring closing on an off-centre
payload loads the pads on the near side and leaves the far side clear; when the
payload is centred all four land at once.  And the post-hoc **deeper squeeze does
not fix it** (`FRUIT_GRIPPER_SQUEEZE=0.94`, i.e. 6 % of the widest extent instead
of 2 %: **1/17** `>=3`, 7/20 placed) - because the closure *is* at its target and
the far pads are clear by more than the extra interference.  The shipped close is
`grip_gap = pinch_width * 0.98` and `pinch_width`'s radial branch is the payload's
**widest horizontal extent** (P107 iteration 7), so the two pads on that axis
touch at the cap and the two on the narrow axis stand off by
`(widest - narrow)/2 + 2 %`.  **So the enclosure is a centring term, and the
wider cage makes it no better: it makes it worse in principle** (a longer close
over an off-centre payload is more travel for the payload to be pushed).

## 4. The spacing: the density prior holds, and the guard fires

`FRUIT_SUPPLY_GAP_MIN` 0.10 -> **0.15** m on the 200 mm cage:

* **Starved slots** (`ATTEMPTS - attempts`): **E 1 / 2** per seed against
  **C 5 / 3** - **+4 of 20 at seed 5, +1 at seed 6**.  The registered G3 kill
  clause is *"> 2 of 20 at either seed"*, so **it fires at seed 5**.
* **Placed**: **13/37 (35 %) -> 8/32 (25 %)**, and the seed-5 cell collapses to
  **1/15** (four `fruit did not follow the gripper` notes plus four lost slots).
* The interval is not estimable at these counts; `s/attempt` is flat
  (15.5 -> 16.0 s), so the cost is the *slots*, not the clock.

**This is P1c's prior on the same axis**: the single arm is the line that starves
when the supply thins (the two-line hides it because its worker parks and waits -
and the cage cannot run there anyway).  The mechanism is visible in the cells:
the delivered supply is the scatter sheet, whose 0.10-0.35 m gaps the census
found *satisfied* the 149 mm requirement at every arrival window it saw
(**0 neighbours inside 0.15 m**), so the spacing change buys margin against a
collision **that was never observed** and pays for it in slots.

## 5. The census, in one paragraph

`CENSUS.md` is the phase's first half and it is what chose the numbers.  The
split: the **close-time** aim is **3.4 mm lateral / 1.1 mm along / 4.5 mm
radial** (p50, 726 traced attempts on disk), so P107's "**24 mm off the cage's
axis**" is **not** a grasp-time figure; it is the **arrival** offset, and its
size is the line's own lead (`[task] dynamic descent: fruit dy` = **83 mm** p50,
**3963 attempts**, of which **18 mm is `FRUIT_DYNAMIC_DESCEND_MARGIN`'s 0.15 s**
at 0.12 m/s).  Inside the pads' axial band - the plate, 60 mm long, spans
20.5-80.5 mm below the jaw and a payload's sphere overlaps it over ~130 mm of
`dz`, i.e. almost the whole descent - the payload sits **55.8 mm upstream (p50,
max 61.7) and 11.8 mm lateral (p50)**; the along-belt share is **83-89 %**, and
the lateral tail is 60-70 mm on the attempts whose x-tracking lagged.  The
aperture that implies is **`A_y` = 181.6 (p50) / 216.6 (p90) mm** with the pool's
35 mm `r_max`, and the offline screen reproduces P107 exactly: **120 mm passes
0/8 windows, 160 5/8, 210 7/8**.  The **oblong does not pay** - an 86 mm lateral
axis fails the 60-70 mm tail, so it needs ~190 mm lateral anyway and stops being
an oblong (`oblong 86x210` 5/8 against `round210` 7/8).  The registered 200 mm
sits at the census's p90.

## 6. Guards

* **Landing (G1)**: `FRUIT_PLACE_TRACE` on every arm.  Payload-present releases
  land `on_belt`: **S 25/37, B 6/13, E 13/17, C 8/15**.  The misses are the
  upstream-lost class (`release_bottom = -184 mm`, P86/P87's own rows), not the
  release.
* **Budgets (G2)**: the descent `|v|max` is inside budget on **S**, and the cage
  arms carry the P107 class - a handful of legs at **1.1x** and a worst
  `end/len` of 1.02-1.27 (the blocked-descent class, which is a *position* miss,
  not a speed excursion).  Nothing is above 1.5x; not re-tuned (AGENTS §2).
* **Density (G3)**: **fires** at seed 5 (§4).
* **No-harm (G4)**: §8.
* **Same-tree control (G5)**: the S arm, this batch, 65.8 %.

## 7. The price of each remaining route

The phase's own numbers price three cheaper routes, in ascending cost:

1. **`FRUIT_DYNAMIC_DESCEND_MARGIN` 0.15 -> 0 (an existing env knob, no code).**
   It is **18 mm of the 83 mm** lead and therefore ~**18 mm of the 56 mm** the
   pads must swallow: the census's `A_y` p50 falls **181.6 -> 145.6 mm**, which
   the **160 mm** cage already half-passes (5/8).  Cost: the descent starts
   later, so the catch-up closes ~18 mm more (its residual is 5-6 mm today,
   P47's 6 mm tolerance).  **This is the cheapest test in the record** and it is
   the named next spend.
2. **A centring guide at the pick station (option 1).**  It would remove the
   **close-time lateral** term (`|dx|` p50 **8.8 mm** on the cage cell) and
   therefore the bimodal enclosure (§3) - the class that actually blocks the
   placement.  It does **not** remove the along-belt arrival (56 mm), so it is
   **complementary to the aperture, not a substitute**: it needs a cage that has
   already cleared the arrival (200 mm, or 160 + route 1).  Cost: one funnel
   collider at the station in `assets.py`/`scene.py`; **if it is opt-in like the
   cage the shipped scene is untouched and no reference moves**, but the cell
   that measures it must then run cage + guide together, and the guide's own
   contact with the payload is a new class (P95's pre-leg contact census is the
   instrument).
3. **The 200 mm hand + the spacing (the literal option 2).**  **Built, measured,
   not adopted**: it buys the approach and half of the placements, it does not
   buy the enclosure, and the spacing costs 4 slots of 20.  A 220 mm-wide hand
   is also the largest thing this cell can carry without touching its own
   neighbours.

**So option 1 is *not* cheaper for the whole problem - it cannot touch the axis
the census says is binding (along-belt) - but it is cheaper *for the enclosure*,
and the enclosure is what keeps the placed count at 35 %.**  The cheapest
*complete* pair is route 1 (the margin knob) + a 160 mm cage + a centring guide;
that is a registration of its own.

## 8. No-harm

* `scripts/accept.sh` with `FRUIT_GRIPPER_KIND` unset and no supply knob: see
  `accept_noharm.log` / `accept_noharm.driver` - the shipped two-line
  acceptance, whose `[fruit]` stream is compared line-for-line with
  `logs/p107/accept_noharm.log`.
* `scripts/selfcheck.sh` **PASS** (no new default, no new manifest field: the
  phase adds **no `src/` code** - both knobs already exist).
* `scripts/211_bed_audit.py` ok.
* **Nothing is adopted**: `FRUIT_CAGE_OPEN_FACE_R`, `FRUIT_SUPPLY_GAP_MIN` and
  `FRUIT_GRIPPER_SQUEEZE` are unset by default; `configs/` is untouched
  (`30fb99f8` / `30fb99f8` / `8952c320`); no reference is re-recorded and none is
  owed (the cage is opt-in and the shipped two-line cannot reach it).

## 9. Pins and files

Tree: `tasks.py`, `cage_hand.py`, `scene.py`, `fruits.py` **unchanged by this
phase** (P107's pins stand: `tasks.py` **`9e3e657b`**, `cage_hand.py` P107's
final, `scene.py` `472bfb6c`, `assets.py` `540406fa`, `fruits.py` `dcabe16b`);
checkpoint `moe_v13s` `61da390a`.  Phase artefacts:
`PREREG.md` **`7ea66620`** (`PREREG.md5`), `CENSUS.md`, `census.py`,
`close_aim.py`, `census.txt`, `p108_report.py`, `run_p108.sh`, `cells.sh`,
`p108_report.txt`, the cells `{S,B,E}_{5,6}.log`, `{C}_{5,6}.log`,
`E_sq94_s5.log`, the census traces `tr_cage_s5/`, `cage_s5_traced.log`.
