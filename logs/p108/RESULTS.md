# P108 results - the widened cage (aperture + supply spacing), option 2

**VERDICT (first line).**  **Option 2 is refuted as stated.**  Widening the cage
from **120 to 200 mm** (`FRUIT_CAGE_OPEN_FACE_R=0.100`) is a **robust actuator for
exactly one class - the approach collision** - and a **draw for everything the
phase registered as an outcome**: the **enclosure at >= 3 pads** (P107's real
endpoint) reads **5/51 = 9.8 % -> 10/57 = 17.5 %**, Fisher **p = 0.28** (it
doubles, but the registered **+30 point** bar is not met), and the **placed count
10/51 = 19.6 % -> 16/57 = 28.1 %**, **p = 0.37**, better at seeds 5 and 6 and
**worse at the fresh seed 101** (3/18 -> 7/19, 3/14 -> 6/18, **4/19 -> 3/20**).
What *is* decisive is the approach: **`clr < 0` 32/51 -> 4/57, Fisher p = 1.4e-8**.
**The spacing half fails its density guard** (`GAP_MIN` 0.10 -> 0.15 costs
**5 starved slots of 20 against 1** at seed 5, 3 vs 2 at seed 6) **and the
placements fall to 6/35 = 17.1 %**.  **The enclosure does not move because it is a
centring term, not an aperture one** - the histogram is bimodal (**4 pads or 1-2,
never 3**) and the closure depth is not its actuator either (a post-hoc 6 %
interference cell reads **1/17**).  So **the cheaper route is option 1 (a passive
centring guide) plus a control retiming**, not a bigger hand and not a sparser
belt: the guide addresses the enclosure, and `FRUIT_DYNAMIC_DESCEND_MARGIN` 0.15 ->
0 (an existing knob, 18 of the 83 mm lead) shrinks the aperture the guide would
have to live behind.  Neither alone is sufficient - the arrival is 56 mm
along-belt and no lateral guide can remove it.

**A correction to this phase's own first close-out.**  An interim commit
(`c35dc48`, 14:16) recorded the battery at **two seeds** (5, 6) and read the
aperture as "a measured actuator ... the placements double at both seeds".  The
two **fresh seed-101** cells were then re-run to completion (an earlier attempt's
`.tmp` files had been dropped as aborted, `a7133e3`; these are complete -
`attempts=19` / `20`, `[stats]` present) and they **reverse the placement read at
that seed** (4/19 -> 3/20).  Everything below is the **three-seed** record: the
enclosure doubling (**+7.7 points, p = 0.28**) stays under the registered
**+30 point** bar, and the placement movement becomes a **draw** (**p = 0.37**).
That reversal is the phase's own lesson - P93's fresh-seed rule, applied to its
own battery - and it is why the verdict reads *refuted as stated* rather than
*half vindicated*.

# 0. What was measured, and against what

`PREREG.md` (md5 **`7ea6662054fa2acdf490042c0737e662`**, pinned before any battery
cell) registered four arms on the **scripted single arm** (`FRUIT_BIARM=0` - the
two-line refuses a non-`openarm` hand, so this is the cage's only home) at
`ATTEMPTS=20`:

| arm | hand | aperture | along gap | seeds |
|---|---|---|---|---|
| **S** | shipped `openarm` | - | 0.10-0.35 | 5, 6 |
| **B** | `cage4` | 120 mm (P107) | 0.10-0.35 | 5, 6, 101 |
| **E** | `cage4` | **200 mm** | 0.10-0.35 | 5, 6, 101 |
| **C** | `cage4` | **200 mm** | **0.15-0.35** | 5, 6 |

Every cell carries `FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1
FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1` (the probe is a no-op on the shipped
hand), so all arms sit inside one instrumented batch and the **landing is measured
on every arm** - P107's M3 cells had no `FRUIT_PLACE_TRACE` and could not report
it.  Seed **101 is fresh** (P93's rule).  Post-hoc, after the battery:
`E_sq94_s5`, the 200 mm cage at `FRUIT_GRIPPER_SQUEEZE=0.94` - a *mechanism*
probe, not a registered arm.

## 1. The battery

| cell | attempts (starved) | placed | rate | s/attempt | encl >= 3 | `clr < 0` | no-contact |
|---|---|---|---|---|---|---|---|
| S s5 | 19 (1) | 12 | 63 % | 15.1 | - | - | - |
| S s6 | 19 (1) | 13 | 68 % | 15.0 | - | - | - |
| **S pooled** | **38** | **25** | **65.8 %** | 15.1 | - | - | - |
| B s5 | 18 (2) | 3 | 17 % | 15.3 | 4/18 | 11/18 | 2/18 |
| B s6 | 14 (6) | 3 | 21 % | 15.7 | 1/14 | 10/14 | 3/14 |
| B s101 | 19 (1) | 4 | 21 % | 15.3 | 0/19 | 11/19 | 7/19 |
| **B pooled** | **51** | **10** | **19.6 %** | 15.4 | **5/51** | **32/51** | 12/51 |
| E s5 | 19 (1) | 7 | 37 % | 15.3 | 3/19 | 0/19 | 2/19 |
| E s6 | 18 (2) | 6 | 33 % | 15.8 | 4/18 | 4/18 | 8/18 |
| E s101 | 20 (0) | 3 | 15 % | 15.7 | 3/20 | 0/20 | 1/20 |
| **E pooled** | **57** | **16** | **28.1 %** | 15.6 | **10/57** | **4/57** | 11/57 |
| C s5 | 15 (**5**) | 1 | 7 % | 15.1 | 2/15 | 0/15 | 2/15 |
| C s6 | 20 (3) | 5 | 25 % | 16.9 | 1/20 | 6/20 | 6/20 |
| **C pooled** | **35** | **6** | **17.1 %** | 16.1 | **3/35** | 6/35 | 8/35 |
| E_sq94 s5 (post-hoc) | 17 (3) | 7 | 41 % | 15.8 | **1/17** | 1/17 | 2/17 |

## 2. The aperture: one robust effect, and it is the approach

* **`clr < 0`** (P107's own approach census: a pad face inside the payload's
  sphere during the approach): **32/51 (63 %) -> 4/57 (7 %)**, Fisher
  **p = 1.4e-8**.  This is the phase's only decisive number, and it is the class
  the census said the aperture targets.
* **The descent's `end=`** - the number P107 did not read - is **57.9 mm (p50) at
  B s5** against the shipped hand's **8.9-9.1 mm**, i.e. the 120 mm cage's pads
  **block the leg** on half of that seed's attempts; at 200 mm it is **9.3-10.5 mm
  at all three seeds**.  But B s6/s101 already read **10.1/10.3 mm**, so the
  blocked-descent class is a **seed-5 branch property**, not a general cost of the
  120 mm aperture.  Reported as such.
* **Placements**: 10/51 -> 16/57 (p = 0.37), **2 of 3 seeds better and the fresh
  seed worse**.  This is why P93's fresh-seed rule exists: the two-seed reading
  (6/32 -> 13/37, "better at both") becomes a **draw** at the third.
* The cage is still far below the shipped hand: 16/57 vs **25/38**, **p = 0.0003**.

## 3. The enclosure: a doubling that is not a movement, and its actuator is not the aperture

**Enclosure at >= 3 pads of 4**: **5/51 (9.8 %) -> 10/57 (17.5 %)**, Fisher
**p = 0.28**.  It doubles, and the pre-registered bar was **+30 points**, so
**"the aperture is not the actuator" fires** by the registration's own letter.
The shape of the histogram says what the class is:

| arm | 0 pads | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| B (120 mm), s5 / s6 / s101 | 2 / 3 / 7 | 7 / 8 / 7 | 5 / 2 / 5 | 4 / 1 / 0 | 0 / 0 / 0 |
| E (200 mm), s5 / s6 / s101 | 2 / 8 / 1 | 6 / 3 / 11 | 8 / 3 / 5 | 0 / 1 / 3 | **3 / 3 / 0** |
| E + squeeze 0.94 | 2 | 8 | 6 | 1 | 0 |

**It is bimodal: 4 pads or 1-2, never 3.**  A square ring closing on an off-centre
payload loads the near pads and leaves the far side clear; when the payload is
centred all four land together.  And the **closure depth is not its actuator
either**: the post-hoc cell at `FRUIT_GRIPPER_SQUEEZE=0.94` (a 6 % interference on
the widest extent instead of 2 %) reads **1/17**.  The shipped target is
`grip_gap = pinch_width * 0.98` and `pinch_width`'s radial branch is the payload's
**widest horizontal extent** (P107's iteration 7), so the two pads on that axis
touch at the 4.9 N cap while the two on the narrow axis stand off by
`(widest - narrow)/2 + 2 %`; a deeper command does not bring them in because the
ring is **off-centre** - the near pads simply push the payload further off.  The
measured close-time lateral offset is **`|dx|` p50 8.8 mm** on the cage cell
(§5), the same order as the stand-off.

## 4. The spacing: the density prior holds and the guard fires

`FRUIT_SUPPLY_GAP_MIN` 0.10 -> **0.15** m on the 200 mm cage (the 149 mm the
aperture demands):

* **Starved slots** (`ATTEMPTS - attempts`): **C 5 / 3** per seed against **E
  1 / 2** - **+4 of 20 at seed 5**, +1 at seed 6.  The registered G3 clause is
  *"> 2 of 20 at either seed"*: **it fires at seed 5**.
* **Placed**: **16/57 (28.1 %) -> 6/35 (17.1 %)**, the seed-5 cell collapsing to
  **1/15** (four lost slots and four `fruit did not follow the gripper` notes).
* `s/attempt` is flat (15.6 -> 16.1 s), so the cost is **slots**, not clock.
* The mechanism is the one P1c measured: the **single arm** starves when the
  supply thins; the two-line hides it (its worker parks and waits) and the cage
  cannot run there.  Note the 120 mm cage also starves (**9 of 60 slots**) - the
  narrow cage disturbs the line - so the spacing's +4 is read against **E**, its
  own hand.

**And the census had already said the spacing buys nothing measured**: the
delivered scatter met the 149 mm requirement in **every** arrival window it saw
(**0** neighbours inside the 0.15 m filter, 0/8).  The spacing is a margin
purchase against a collision that was never observed, paid in slots.

## 5. The census, in one paragraph

`CENSUS.md` is the phase's first half and it is what chose the numbers.  The
split: the **close-time** aim is **3.4 mm lateral / 1.1 mm along / 4.5 mm radial**
(p50, **726** traced attempts already on disk, `close_aim.py`), so P107's "**24 mm
off the cage's axis**" is **not** a grasp-time figure and **not** a lateral one; it
is the **arrival** offset, and its size is the line's own lead
(`[task] dynamic descent: fruit dy` = **83 mm** p50 over **3963 attempts**, of
which **18 mm is `FRUIT_DYNAMIC_DESCEND_MARGIN`'s 0.15 s** at 0.12 m/s).  Inside
the pads' axial band - the plate, 60 mm long, spans 20.5-80.5 mm below the jaw, so
a payload's sphere overlaps it over **~130 mm of `dz`**, i.e. almost the whole
descent - the payload is **55.8 mm upstream (p50, max 61.7) and 11.8 mm lateral
(p50)**, an **83-89 % along-belt** split whose lateral tail (60-70 mm) belongs to
the attempts whose x-tracking lagged.  The aperture that implies is **`A_y`
181.6 (p50) / 216.6 (p90) mm** with the pool's 35 mm `r_max`; the offline screen
reproduces P107 exactly (**120 mm passes 0/8 windows, 160 5/8, 210 7/8**), and the
**oblong does not pay** (`86x210` 5/8 against `round210` 7/8: the 86 mm lateral
axis fails the tail), so a genuinely narrow lateral needs a centring step first.
The census cell is **inert**: its **502 `[fruit]` lines are 502/502
byte-identical** to P107's own `m2b_s5.log` with the trace/cycle/`[cage]` rows
dropped.

## 6. Guards

* **Landing (G1)**: payload-present releases land `on_belt` on **S 25/37, B 10/21,
  E 16/28, C 6/15**.  The misses are the upstream-lost class
  (`release_bottom = -184 mm`, P86/P87's own rows), not the release.
* **Budgets (G2)**: the shipped hand is clean; the cage arms carry P107's
  ~2.5 %-of-legs 1.1x descents plus the blocked-descent class (a **position** miss,
  `end/len` up to 1.27, not a speed excursion).  Nothing above 1.5x; **not
  re-tuned** (AGENTS §2).
* **Density (G3)**: **fires** at seed 5 (§4).
* **No-harm (G4)**: §8.
* **Same-tree control (G5)**: the S arm, this batch, **65.8 %**.

## 7. The price of each remaining route

In ascending cost, from this phase's own numbers:

1. **`FRUIT_DYNAMIC_DESCEND_MARGIN` 0.15 -> 0 (an existing env knob, no code, no
   scene change).**  It is **18 mm of the 83 mm** lead and therefore ~18 mm of the
   56 mm the pads must swallow: the census's `A_y` p50 falls **181.6 -> 145.6 mm**,
   which the **160 mm** cage already half-passes (5/8 windows).  Cost: the descent
   starts later, so the catch-up closes ~18 mm more (its residual is 5-6 mm today
   against P47's 6 mm tolerance).  **This is the cheapest untested lever in the
   record.**
2. **A passive centring guide at the pick station (option 1).**  It removes the
   **close-time lateral** term (`|dx|` p50 **8.8 mm** on the cage cell) and with it
   the bimodal enclosure - the class that actually holds the placed count at 28 %.
   It does **not** remove the along-belt arrival (56 mm), so it is **complementary
   to the aperture, not a substitute**: it needs a cage that has cleared the
   arrival (200 mm, or 160 mm + route 1).  Cost: one funnel collider at the station
   in `assets.py`/`scene.py`; **opt-in like the cage, the shipped scene and every
   reference are untouched**, but the cell that measures it must run cage + guide,
   and the guide's own contact with the payload is a new class (P95's pre-leg
   contact census is the instrument).
3. **The 200 mm hand + the spacing (the literal option 2).**  **Built, measured,
   not adopted**: it buys the approach and a doubling of the enclosure that the
   registration's bar does not accept, and the spacing costs four slots of twenty
   at one seed and the placements at both.

**Is option 1 now the cheaper route?**  **Yes for the enclosure** - the term that
blocks the placement - and **no for the approach**: the census says the binding
axis is along-belt (56 mm), which a passive lateral guide cannot touch.  So the
honest answer to the owner's question is that the two options are **halves of one
fix**, and the cheaper *complete* package is **route 1 + a 160 mm cage + a
centring guide**, which is a registration of its own.

## 8. No-harm

* `scripts/accept.sh` with `FRUIT_GRIPPER_KIND` unset and no supply knob:
  **8/10, 9.0 s/attempt, `fingerprint: matches configs/motion_reference.json`,
  `190: PASS`**, and its **421 `[fruit]` lines are 421/421 byte-identical** to
  `logs/p107/accept_noharm.log` (`accept_noharm.log`, `accept_noharm.driver`).
* `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** - the phase adds **no
  `src/` code** (both knobs already existed) and no selfcheck leg.
* `python3 scripts/211_bed_audit.py` **ok (115 checks)**.
* **Nothing is adopted**: `FRUIT_CAGE_OPEN_FACE_R`, `FRUIT_SUPPLY_GAP_MIN` and
  `FRUIT_GRIPPER_SQUEEZE` are unset by default, `configs/` is untouched
  (`30fb99f8` / `30fb99f8` / `8952c320`), and no reference is re-recorded or owed.

## 9. Pins and files

**No `src/` or `configs/` change in this phase**; P107's pins stand:
`tasks.py` **`9e3e657b`**, `cage_hand.py` (P107's final), `scene.py` `472bfb6c`,
`assets.py` `540406fa`, `fruits.py` `dcabe16b`; checkpoint `moe_v13s`
`61da390a`.  Phase artefacts: `PREREG.md` **`7ea66620`** (`PREREG.md5`),
`CENSUS.md`, `census.py`, `close_aim.py`, `census.txt`, `p108_report.py`,
`p108_report.txt`, `run_p108.sh`, `cells.sh`, the cells `{S,B,E}_{5,6,101}`,
`{C}_{5,6}`, `E_sq94_s5.log`, the census traces `tr_cage_s5/`,
`cage_s5_traced.log`, `accept_noharm.{log,driver}`.
