# The end-effector decision

**A book for the hardware partner.** Written 2026-11-04 (P113) as the close-out of
the end-effector lane (P104-P112). It is a **decision document, not a
measurement**: every number below was measured in a phase whose record is in
`logs/`, and every claim carries that record. Nothing here is new data, and no
bench number is invented.

**The question it answers.** The cell's grasp loses **75 % of its failures** to one
class (the *loaded slide*); nine end-effector routes have been measured and each
one's verdict is in `logs/`; **what should the hardware be, and what must be
measured on the bench before it is bought?**

**The short answer.** Buy nothing yet. The class is a **creep at the operating
load**, not a force deficit, and the geometry that fixes the creep is known and
priced (4 contacts = **1.87-2.05x** static, **9-15x** in creep). Every radial form
built so far fails **not on the pad but on the delivery**: the line presents a
*moving*, off-axis fruit, and a ring needs **0.6 mm** of centring while the line's
best is **1.8 mm**. Three bench measurements - **a pad with `mu_pair < 1`, a
three-jaw on a *moving* presentation, and a stationary nest** - decide whether a
purchase is possible at all. Each has a kill criterion in §4. Nothing else in this
lane is unspent.

**Citation convention.** `[P104 §3]` = `logs/p104/RESULTS.md` §3; `[P92 CENSUS §3]`
= `logs/p92/CENSUS.md` §3; `[P42 SIM_LIMIT §1]` = `logs/p42/SIM_LIMIT.md` §1;
`[SURVEY §5.1]` = `docs/PLATFORM_SURVEY.md` §5.1. The full map is §6. Prices
marked **[V]** were printed by a vendor page on 2026-11-03 (`SURVEY §6`); **[U]**
means unverified/unpriced. Anything with no source is **unpriced**, never guessed.

---

## 0. Terms, so the rest is readable

You have not read this repo. These are the words the document uses, defined in the
sense the measurements used.

| term | meaning |
|---|---|
| **the cell** | two 7-DoF OpenArm arms over one 0.12 m/s belt, two pick stations 0.10 m apart, an output belt with two bins. The shipped scripted scenario is the **two-line** scheduler (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, `[P85 §1]`). |
| **the catch** (moving catch) | the hand makes a **static, profiled descent** at a fixed station while the belt carries the fruit underneath; the descent is timed so the fruit arrives as the pads close. **The belt never stops during a pick** (`[P110 §2]`: encoder -0.120 m/s in every gate cell). |
| **the loaded slide** (`cnp`, "carried not placed") | the payload **was in the pinch and left it** before the release: the pads are still closed and loaded when it goes. Not a missed grasp, not a force shortage, not a seating error (`[P42 SIM_LIMIT §0]`). |
| **a never-held / acquisition failure** | the pads closed on air, or the catch-up did not converge; the payload was never in a pinch (`[P92 CENSUS §2]`). |
| **the seat** | where the pads sit on the payload at the moment the close freezes - the pads' midpoint relative to the fruit's centre (`[P42 SEAT_CENSUS §0]`). |
| **the band entry** | the moment in the descent when the plates' axial band first overlaps the payload's sphere (the plates become level with the top of the fruit). Before it the pads cannot touch; after it they can (`[P110 §1]`). |
| **`s`** | the commanded radial squeeze **per pad** = 1 % of the payload's diameter (the close targets `0.98 x` the width, i.e. 2 % total). At `d` = 60 mm, `s` = 0.6 mm. |
| **`mu_pair`** | the effective friction coefficient of the **pad-fruit pair**. In this sim the two materials are combined by **averaging** (measured, `[P104 §7a]`), so `mu_pair = (2.0 + mu_fruit)/2` = **1.25-1.46** with the pad's authored 2.0 and the pool's 0.52-0.81. The break-away implies the same 1.05-1.45 (`[P104 §7a]`). |
| **the lead** | the along-belt distance between the fruit and the aim when the descent starts. `fruit dy` = **83 mm** p50 = `speed x t_desc` (the belt's travel during the ~0.7 s leg, invariant to the margin, `[P109 §1.1]`); the operative gap `g0` = **100.1 mm** includes the 0.15 s descent margin (**18 mm**, `[P109 §1.2]`). |
| **`clean_slip`** | the payload's displacement **in the carrying leg's own frame** since the leg's first tick. `> 2 mm` is the escape threshold; `> 100 mm` means the payload is gone (`[W8-B]`). The legacy `[motion] slip_max` **must not** be used for this hand (frame-contaminated, `[P42 SIM_LIMIT §0.6]`). |
| **acceptance** | `scripts/accept.sh`: ten attempts on the shipped scenario, gated by a motion fingerprint and a rate floor (0.60 for the two-line, `[P85 §1]`). |

---

## 1. The problem, in one page

### 1.1 What the cell is

Two arms, one belt, one head camera (240x424), a 120 Hz control loop. Left arm owns
station `y = +0.00` (grade A), right arm owns `y = -0.10` (grade B); a main-thread
arbiter runs **one shared physics tick per round** so both loops stay at 120 Hz in
simulated time (`[P82 §1]`, `[P85 §1]`). The pick is the never-stop catch. The
fruit pool is 16 instances, **29.6-69.6 mm**, 9.5-122.8 g, `mu` 0.51-0.92
(`[P110 §2]`).

**The arm is not in question.** The platform is a **$6,500** complete bimanual
OpenArm (Apache-2.0 software, CERN-OHL-S-2.0 hardware, an Isaac Sim USD and a
LeRobot bimanual driver) [V, 2026-11-03], and every family this repo has closed -
force, seat, pad geometry, station height, place profile, workstation - is an
**end-effector or workstation** object, not an arm object (`SURVEY §1.1`, `§1.4`).
So this book is about the hand and the presentation, and nothing in it argues for
a different arm.

### 1.2 The shipped numbers

| metric | value | source |
|---|---|---|
| acceptance (shipped two-line, 10 attempts) | **8/10, 9.0 s/attempt**, `fingerprint: matches` | `[P98]`, re-read in `[P102]`-`[P112]` |
| placed, one 40-attempt block (seeds 5+6) | **28/40 = 70 %** | `[P92 CENSUS §3]` |
| placed, same scenario, a second 40-attempt block | **29/40 = 72.5 %** | `[P102 §2]` |
| placed, four seeds (80 attempts) | **58/80 = 72.5 %** | `[P93]`, read off in `[HAND_STAGE_PLAN §5.0]` |
| inter-placement interval | **10.59 / 11.08 s** at seeds 5/6; **10.59-12.16 s** over four seeds | `[P87 §3]`, `[P93]` |
| `s/attempt` | **9.50 / 9.10 s** (seeds 5/6) | `[P93]`, quoted in `[HAND_STAGE_PLAN §5.0]` |
| wall rate | **2.37-2.91 placed/min** | `[P93]` |

Chapter and verse, with the arithmetic that closes: 58 placed + 17 `cnp` + 5
never-held = 80 (`[HAND_STAGE_PLAN §5.0]`, which corrects `SURVEY §5.0`'s
"25 failures" - that count was three too many; the class share was also computed
on the wrong denominator).

### 1.3 The failure classes, and why the grasp is the term

On the 40-attempt census (`[P92 CENSUS §3]`), **12 failures**:

| class | n | share of failures | share of attempts |
|---|---|---|---|
| **`cnp` / loaded slide** | **9** | **75.0 %** | 22.5 % |
| never-held (pads on air) | 3 | 25.0 % | 7.5 % |
| `fell off the line` | 0 | - | - |
| starvation (lost slot) | 0 | - | - |

The same split on the four-seed pool is **17 `cnp` of 22 failures (77 %) + 5
never-held (23 %)** (`[HAND_STAGE_PLAN §5.0]`). The two samples agree on the class;
quote the range 75-77 %, not one number.

**Why the grasp is the term** - five measured statements, in the order they bind:

1. **It is three quarters of the failures** (above), and it is **one-directional**:
   **0 of 29 placed attempts** in P102's block carry a seated escape
   (`[P102 §2]`). When the payload stays, it never slides.
2. **It is not the force.** The shipped pinch delivers **9.75-9.9 N** (2.2x the
   pre-P41 4.4 N, `[P41 P3 §2]`); raising the cap to 30 and 60 N **deletes the pad
   pry** and the class does not convert (at 30 N the pear reads 6/10 -> 4/10 and
   the two-line 8/10 -> 6/10, with the left *worse* on both - the two batteries
   whose attempt counts are identical across arms; at 60 N a 3.7 cm strawberry is
   crushed *out* of the hand with `clean_slip` 641 mm at `F@onset` 62.3 N,
   `[P41 P3 §2, §5]`). The acceptance's own 6/10 -> 8/10-9/10 at 30-60 N is a
   **moved attractor, not a rate** (`[P41 P3 §5]`). At 60 N the left's placed count
   rises (`[P77 §4]`) and the escape class **shrinks but does not close** (7 -> 3
   left legs; the residue moves to a 3.4-7.9 mm **axial** opening).
3. **It is not the seat.** At the close freeze the pads' midpoint is **1.36-4.65
   mm** from the fruit's centre on **20/20** grips, and the escape legs are the
   **tightest** seats; the whole available correction is ~3-4.6 mm against a
   **104-276 mm** mid-lift walk - a factor of **30-60** (`[P42 SIM_LIMIT §2]`).
4. **It is a creep at the operating load.** On the fixture, under the payload's
   own weight only (`m(g+a)` = 0.17 / 0.91 / 1.20 N), the shipped pinch slides
   **3.20 / 0.85 / 2.68 mm** in a 0.75 s settle on pear / orange / strawberry
   (`[P104 §5]`) - on the pear that is **1.6-1.9x the 2 mm escape threshold**,
   before any disturbance. The static capacity is **10-20x** the demand, so the
   break-away is not the binding number.
5. **It is a geometry/envelopment problem, and the size of the win is measured.**
   Four contacts at the same per-face force give **21.81 / 26.59 / 25.97 N =
   1.87-2.05x** sustained and creep **0.11-0.25 mm** (`[P104 §3, §5]`,
   `[P106 §3]`). That is the mechanism a hand attacks, and it is a *friction
   count*, not a force.

**And it is bounded.** P102's attempt join makes the ceiling exact: **6 of its 11
failures** are a seated slide a contact-count change could reach; the 4 no-grasp
failures are **unreachable by any pad** - that class's failing catch-up residuals
are **220-481 mm** (a hand-over timing failure, `[P47]`, `[P48]`), and P102's own
worst reads a **318 mm** pad-to-payload offset under a 21.8 mm span. So a perfect
contact fix is worth at
most **+6 of 40 = +15 points** (29 -> 35 of 40 = 72.5 -> 87.5 %, `[P102 §2]`). On
the four-seed pool, every `cnp` converting is **75/80 = 93.8 %**, and the
`+8 point` bar is **8 of the 17 conversions = 47 % of the class**
(`[HAND_STAGE_PLAN §5.0]`).

### 1.4 The two constraints that make it hard

**(a) The belt never stops.** Every attempt is a moving catch (§0). The hand
cannot wait for the fruit to settle, and the fruit cannot be clamped at the
station: the station's job is to be *empty* when the next fruit arrives. P110's
gate fixture ran with the belt at -0.120 m/s in every cell and never stopped it
(`[P110 §2]`).

**(b) The fruit is handed over moving, and the lead is load-bearing.** The descent
starts with the fruit **100.1 mm upstream** of the aim (p50 `g0`), of which
**83 mm** is the belt's travel during the leg and **18 mm** is
`FRUIT_DYNAMIC_DESCEND_MARGIN`'s 0.15 s (`[P109 §1.2]`). P109 removed the 18 mm
and **every** arrival flipped from upstream of the aim to past it (`past_aim`
**0/76 -> 79/79**); the catch-up then has a bistable failure (converge to its
6 mm tolerance, or run away to **233-269 mm**) on **5 of 79** attempts against
**0 of 76**, and the placed count fell **64.5 % -> 51.9 %** at 4/4 seeds
(acceptance **8/10 -> 4/10**). The margin is **not a cushion**: it is the term
that makes the catch-up's residual positive (`[P109 §5]`).

### 1.5 Scope: what this sim can and cannot say about your hardware

Read this before quoting any number to a customer.

* The sim's pads are **rigid and adhesion-free** (`[P42 SIM_LIMIT §3]`). There is
  **no visuotactile renderer** in the loop, and **no bruise model** (`[P77 §0]`).
* The pad's authored friction is **2.0** and PhysX **averages** the pair
  (`[P104 §7a]`); a real elastomer pad on a real fruit is a **different number**
  and must be measured, not assumed.
* The pinch is a **force-capped position drive**, force-saturated at the cap
  (`[P40 EFFORT_READ]`, `[P41 P2 §2]`); a real jaw's delivered force and compliance
  are **unanchored** - that is the "real-jaw clamp-force anchor" still owed
  (`[P42 SIM_LIMIT §4.2]`).
* Therefore the class is **expected to be sim-specific**, and the record says so
  explicitly: *do not cite it as a predictor of field failures, and do not cite
  "the sim can hold the fruit"* (`[P42 SIM_LIMIT §3.3]`).

**What does transfer**: the *duration and magnitude* of the relative motion
(the patch sees the slide **0.17-0.94 s** before the pinch is lost, `[P102 §3]`),
the friction-count arithmetic (`n/2`, `[P104 §1]`), and the two geometric
constraints in §2. Those are physics. The absolute friction and force are not.

---

## 2. The mechanism: two figures and their algebra

### Figure 1 - the contact algebra

Looking down the tool axis; the fingers close in this plane.

```
      (a) shipped pinch              (b) three pads             (c) four pads
          n = 2                          n = 3                      n = 4

           [P]                            [P]                        [P]
            |                              |  \                       |  \
            | N                            |   \ N                    |   \
         (  o  )                         (  o  )                    (  o  )
            |                              |   /                      |   /
            |                              |  /                       |  /
           [P]                            [P] [P]                   [P]   [P]

   F_crit = 2 mu N                 F_crit = 3 mu N            F_crit = 4 mu N
   analytic 1.00x                  analytic 1.50x             analytic 2.00x
   measured 11.0 / 14.2 / 12.7 N   measured 1.33-1.64x        measured 1.87-2.05x
```

`F_crit = n * mu * N_c` is Coulomb with independent point contacts and no peel;
the seat puts every normal **perpendicular to the pull**, so an axial pull is pure
friction and the ratio is **`n/2`, mu-free** (`[P104 §1]`, `analytic.py`). The
fixture reproduces it to **within 10 %** in every cell (`[P104 §3]`).

**The centring algebra.** A ring closes on **one scalar**; the four penetrations
at an offset `delta` are

```
   near pad:  s + delta        far pad:  s - delta       perpendicular pair:  s - roundness

   the payload moves NORMAL to near/far (no friction there)
   and TANGENTIAL to the perpendicular pair (friction mu N), so

       drive = (near - far)          fric = 2 mu * perp + mu_belt * m * g

   four pads   delta_inf = (2 mu - 1) * min(s, cap / (2 mu k))        [P111 §1]
               delta_inf = mu * s                                    [P112 §1, 2-D solver]
   three pads  delta_inf = sqrt(3) mu s / (1.5 + (sqrt(3)/2) mu)      [P112 §1]
                         = 0.84 - 0.92 s  at the measured mu
```

The thresholds are the whole point:

| form | centres when | at the measured `mu_pair` 1.25-1.46 |
|---|---|---|
| **four pads** | **`mu < 1`** | **no**: residual is `mu s` = 1.00-1.46 s, i.e. more than the whole squeeze; the far pad stays short by `(2mu - 2) s` = 0.2-0.6 mm **forever, at any stiffness and any cap** (`[P111 §6.3]`) |
| **three pads** | **`mu < sqrt(3)` = 1.73** | **yes**, 0.84-0.92 s, worst case 0.915 s (`[P112 §1]`) |

**The stiffness is a window, not a slope.** The cap saturates the near pad first,
which removes drive without removing friction: the admissible `k` is
**`[2.9e3, 3.8e3]` N/m** over the pool (the build takes 3300); above
`k* = cap/(2 mu s)` ~ **2.2e3 N/m** the perpendicular pair sits at the cap and
nothing slides at all - which is the shipped ring at `k = 1e5`
(elastic allowance `cap/k` = **0.049 mm**, `[P111 §1]`, `[P112 §1]`).

### Figure 2 - the arrival geometry

The fruit rides the belt while the hand descends. Two timelines, both measured.

```
  (a) the descent, as one bar

   t = 0  descent starts                          t ~ 0.74 s  pads reach the station
   |                                                            |
   v                                                            v
   *============================================================*  fruit, on the belt
   |<--------------- 83 mm of belt travel --------------------->|
                     (speed 0.12 m/s x 0.74 s = fruit dy)

   the aim sits 100.1 mm downstream of the fruit at t = 0
        (83 mm clock + the 18 mm descent margin, P109)
   by the time the pads stop the fruit is +10.6 mm UPSTREAM of the aim
        (0 of 76 attempts past it, P109 - and that sign is load-bearing)

  (b) the band entry, inside the same leg

   t = 0        t ~ 0.12 s (14.5 mm into the leg)              t ~ 0.74 s
   |            |                                                |
   v            v                                                v
   *------------*================================================*
                ^ the plates first overlap the payload's sphere
                  the payload is still 55.8 mm upstream,
                  max 61.7 mm, and only 2.6 mm lateral   (p50, P110)
                  -> 92.5 % of the arrival error is ALONG THE BELT
```

**The numbers that decide every verdict below.**

| quantity | value | source |
|---|---|---|
| belt travel during the leg (`fruit dy` = `speed x t_desc`) | **83.0 mm** p50 (3963 attempts) | `[P108 §5]`, `[P109 §1.1]` |
| descent-start gap `g0` (what the deadline commands) | **100.1 mm** p50 (82.3 with the margin removed) | `[P109 §1.2]` |
| split at the band entry | **55.8 mm along-belt / 2.6 mm lateral** (p50); along-belt share **92.5 %** | `[P110 §1]` |
| aperture that implies, `A_y = 2(dy + r)` | **181.6 mm** p50 / 216.6 p90 (r_max 35 mm) | `[P108 §5]` |
| where the descent ends (the aim's own quality) | `end` p50 **9.0-9.2 mm** short | `[P109 §2]` |
| the catch-up's convergence tolerance | **6 mm** (`FRUIT_DYNAMIC_CATCH_TOL` 0.006) | `tasks.py:13360` |
| the close-time offset (aim, 726 attempts) | **3.4 mm lateral / 1.1 mm along / 4.5 mm radial** | `[P108 §5]` |
| the ring's centring requirement | **0.6 mm** = `0.01 d` (elastic allowance 0.049 mm) | `[P110 §3.2]` |

### 2.3 The two figures together

Figure 1 is a **requirement on the contact set**: 4 contacts at the measured
friction give 2x static and 9-15x creep, but the same `mu > 1` denies a four-jaw
the last millimetre of centring; 3 jaws centre (0.84-0.92 s) but are only 1.5x and
lose the win to a moment (1.15-1.47x, `[P104 §6]`), and they **fail** the survey's
2 mm criterion at **0.86-1.53x** because a 3+ contact grasp **re-seats** after
2 mm while the pinch's 2 mm is terminal (`[P104 §3]`); `mu < 1` would let a
four-jaw centre.

Figure 2 is a **requirement on the presentation**: a ring needs to be placed
around the payload to **0.6 mm**, while the line delivers **6 mm** of catch
tolerance, **3.4-4.5 mm** of close offset, **1.8 mm** within a fruit and
**17.5 mm** across the pool from the best passive element measured - i.e. the
ring asks **3-29x** tighter than anything on the line delivers (`[P110 §3.2]`).
And **92.5 %** of that error is **along the belt**, which no lateral guide can
remove.

**So the nine routes below are all one of two verdicts**: a *closure* change that
the algebra says is worth 2x but that the delivery denies, or a *delivery* change
that the arithmetic says is the binding term but that no passive element reaches.
That tension is the entire lane.

---

## 3. The nine routes, and what each one cost

### 3.1 The table

Route 0 is the baseline. Routes 1-9 are the nine measured routes.

| # | route | what was measured | the number | verdict | cost |
|---|---|---|---|---|---|
| 0 | **shipped parallel jaw** (baseline) | P104's fixture at 4.90 N/face: axial break, 2 mm break, creep | **11.03 / 14.21 / 12.69 N**; 2 mm 10.62 / 13.83 / 12.19; creep **3.20 / 0.85 / 2.68 mm** | the thing to beat | in service |
| 1 | **tactile pad** | P102's patch channel + P103's perfect-detector re-grip | sees the slide **0.17-0.94 s** early; converts **0 of 5** same-instance `cnp`; destroys **2 of 2** placements; interval **+15.3 %** | **detected, not convertible** | $1,020 + printing (`SURVEY §2.2` [V]) |
| 2 | **anthropomorphic 3+1 hand** | P106: Allegro 16-DoF mounted on the OpenArm flange | 38 DOF merged, **2.135 kg**, tool offset **170.7 mm**; fingertip span **116-123 mm** -> at most **3 of 4** touch a 37-66 mm payload; close+lift **1/4** | **wrong topology** | ~$15k class [U] |
| 3 | **radial 4-pad** (the shape) | P104/P106 fixture; P107 on the line | **1.87-2.05x** axial, 2 mm **1.80-2.10x**, creep **0.11-0.25 mm**; on the line **3/17 = 17.6 %** vs 13/18 = 72.2 % | **the shape is worth 2x; the line cannot place it** | machined assembly, unpriced |
| 4 | **wide aperture** | P108: 120 -> 200 mm | `clr < 0` **32/51 -> 4/57** (p = 1.4e-8); placed **10/51 -> 16/57** (p = 0.37) | **a precondition, not a rate** | the same ring, wider |
| 5 | **wider supply spacing** | P108: `GAP_MIN` 0.10 -> 0.15 m | starved slots **1 -> 5 of 20** (seed 5); placed **16/57 -> 6/35** | **unaffordable** | supply change |
| 6 | **descent margin** | P109: 0.15 -> 0 | `g0` **100.1 -> 82.3 mm**; `past_aim` **0/76 -> 79/79**; placed **64.5 -> 51.9 %**; acceptance **8/10 -> 4/10** | **load-bearing; never spend it** | $0 (a knob) |
| 7 | **metering gate** | P110: all 16 pool fruits, belt running | **16/16 held** at every height 8-45 mm; hold **0.85-1.83 mm**; queue 1.8 -> **4.9 mm**, **1/16 expelled** | **works; 3-29x too coarse** | one kerb, unpriced |
| 8 | **compliant closure** | P111: six arms, three stiffness windows | force at the freeze **4.90 -> 0.6-1.8 N**; clean enclosure **0-3 rows** per arm; count **16.4-23.4 %** vs 25.0 % (n.s.) | **a gentler jam** | printed/machined pads + springs, unpriced |
| 9 | **three-jaw ring** | P112: 390-closure fixture + four-seed battery | centres **0-20 mm -> 0.5-1.9 mm**; loads its pads **18/30** vs 4-pad **2/30**; battery **18.4 %** vs **72.2 %** | **centres, does not convert** | machined assembly, unpriced |

### 3.2 Each route, in one paragraph

**0. The shipped parallel jaw - the baseline.** Two flat plates, 61.0 x 84.9 mm,
on replaceable fingers, a 10.5 mm distal lip, a force-capped position drive.
At the measured 4.90 N per face the pinch's sustained axial capacity is
**11.03 / 14.21 / 12.69 N** on a 60.6 mm pear / 65.8 mm orange / 37.2 mm
strawberry (`[P104 §3]`), and it reaches that capacity only after it has already
slid: under the payload's own weight it creeps **3.20 / 0.85 / 2.68 mm**
(`[P104 §5]`). That is the number the whole lane is about - the pinch *holds* and
the *payload walks*, one-sided contact on **18 of 32** escape samples
(`[P42 SIM_LIMIT §0.4]`). The static capacity is **10-20x** the demand
(0.17-1.20 N), so a bigger number on the same quantity cannot fix it: the cell
loses **17 of 80** attempts with a 10-20x margin in its pocket
(`[P104 §1]`).

**1. The tactile pad - detected, not convertible.** The patch channel sees the
payload's in-hand displacement reach 2 mm **21-113 ticks before the pinch is
lost** - median **60 ticks = 0.50 s**, min 0.17 s - and the threshold barely
matters (1 / 2.12 / 4.25 / 8.49 / 10 mm all lead by 44-61 ticks median, 6/6
escapes each; `[P102 §3]`). So the *sensing* case is real and the survey's
"30 Hz is too slow" was wrong: that 0-3 tick number belongs to the 2-scalar
force channel, not to the slip. But a **perfect detector** was then given for
free: a re-grip at 2.12 mm converted **0 of 5** same-instance `cnp`s, **destroyed
2 of 2** placements it touched, moved placed **59/80 -> 54/80 (-6.2 points,
p = 0.49)** and the interval **+15.3 %** (`[P103 §4]`). The reason is a hard
ceiling: the two-line's own carry monitor truncates an attempt whose lift leg
reads `clean_slip >= 8.0 mm`, so a reaction that cannot hold under 8 mm cannot
convert however well it holds the pinch (`[P103 §6]`). **Verdict: a
labelling/fault-log channel, not a reflex; the sensor is not justified by this
class.** Cost: two GelSight Mini at **$510 each = $1,020** [V, 2026-11-03]
(`SURVEY §2.2`, `§5.1`) plus printing and about a week.

**2. The anthropomorphic 3+1 hand - wrong topology.** The Allegro 16-DoF mounts
cleanly (38 DOF merged, articulation proved, limits pinned by name and order) and
weighs **2.135 kg** with a tool offset that replaces the 70 mm standoff by
**170.7 mm** (100-216 mm across a posture sweep) - so the mount is not the
blocker (`[P106 §1]`). Two things are. First, **the fingers are further apart than
the fruit**: the three fingers alone span **116-123 mm**, so **at most 3 of its 4**
fingertips can touch one 37-66 mm payload at any posture in a 4 x 4 sweep - 2 for
the pear at most postures (`[P106 §2]`). Second, **the drive is a step function**:
at the asset's `k = 1e7`, 0.46 N.m gives no contact and 0.48 N.m gives **10.5 N**
per contact, so the per-contact force the plan asked for is not settable
(`[P106 §1]`, `[HAND_STAGE_PLAN §1.4]`). Close+lift held **1 of 4** draws, and the
one that held had already crept **39.75 mm** under 0.82 N - 12x the pinch and 40x
the plan's 1.0 mm bar (`[P106 §1]`). **Verdict: buy radial/enveloping, not
anthropomorphic.** That is a *which vendor* answer, not a *whether to buy* one.
Cost: an Allegro is a ~$15k-class commercial hand [U]; the phase mounted it as an
asset, not a purchase.

**3. The radial 4-pad - the aim.** On the fixture, four independent force-capped
pads at the same 4.80-4.90 N per contact give **21.81 / 26.59 / 25.97 N =
1.87-2.05x** sustained, **1.80-2.10x** at 2 mm, and creep **0.11-0.25 mm** - a
**9-24x** improvement on the class's own quantity - and the pads do **not** pry
(0.30-0.75 mm of radial travel against an 80 mm stroke; `[P104 §3, §5]`,
`[P106 §3]`). The shape was then **built exactly**: aperture **120.0 -> 26.0 mm**
measured = commanded on both axes, four pads on **one scalar**, tool offset
**70.00 mm with 0.00 mm spread** over nine apertures, a 26 x 60 mm plate, the
shipped lip and distal plane intact, a 4.90 N/pad cap delivered at its median
(`[P107 §0]`). And on the line it places **3 of 17 = 17.6 %** against the
same-tree shipped-hand controls' **13 of 18 = 72.2 %**, with **29 of 43** carry
legs reading `force_min == 0` - the cage never had the payload, so it cannot even
reach the closed loaded slide it was bought for (`[P107 §2]`). The blocker is the
**aim**, quantified: the fruit can enter the descent tens of millimetres off the
cage's axis (P107 read 24 mm; P108's census corrected it to **55.8 mm along-belt /
2.6 mm lateral at the band entry**), so the open cage must swallow it - **>= 118
mm** by P107's estimate, and the 200 mm cell is what actually cleared the approach
- while the supply's along-belt spacing is **85-120 mm**, so a wider cage fouls
its neighbours (`[P107 §4]`, `[P108 §5]`). **Verdict: the shape is
worth 2x static and 9-15x creep; the shape on this line does not enclose.**
Cost: the fixture was $0; a hardware ring is a **machined assembly, unpriced**
(there is no buyable product with these apertures).

**4. The wide aperture - a precondition.** Widening 120 -> 200 mm is a **robust
actuator for exactly one class**: the approach collision, `clr < 0` (a pad face
inside the payload's sphere during the approach) falls **32/51 -> 4/57**, Fisher
**p = 1.4e-8** - decisive (`[P108 §2]`). The descent's own shortfall falls
**57.9 -> 9.3-10.5 mm**. Everything the phase registered as an *outcome* is a
draw: the enclosure at >= 3 pads **5/51 -> 10/57 (p = 0.28**, under the +30-point
bar), and placed **10/51 -> 16/57 (p = 0.37**, better at seeds 5 and 6 and **worse
at the fresh seed 101**). **Verdict: buy the aperture only if the ring is bought,
and gate it on the enclosure, not on the count.** Cost: the same ring with wider
plates - and the plate width is bounded by `pad width <= aperture`, so widening
the ring widens the plates, which then cannot close on a 37 mm strawberry
(`[P107 §4]`).

> **The lip, which is not a route but a warning.** A distal ledge wins the fixture
> **unboundedly** (>40 N, "no break inside the ramp", `[P104 §3]`) - and the tree
> has **already measured that geometry as a pipeline negative**: the ledges **bat
> the payload**, no-contact **2 -> 9 of 15**, flails 1 -> 7, battery 6/20 x2
> (`[R8-A §3]`). A static win is not a pipeline win. Do not put a shelf on the pad
> without an approach test.

**5. The wider supply spacing - unaffordable.** The 200 mm aperture demands
`A/2 + plate + r_max + clearance` ~ **149 mm** of spacing against the scatter's
planned 0.10-0.35 m, so the phase widened `GAP_MIN` to 0.15 m: **starved slots
1 -> 5 of 20** at seed 5 (2 -> 3 at seed 6) and placed **16/57 -> 6/35 = 17.1 %**,
with `s/attempt` flat (15.6 -> 16.1 s) - the cost is **slots**, not clock
(`[P108 §4]`). And the census had already said it buys nothing measured: the
delivered scatter met the 149 mm requirement in **every** arrival window it saw
(**0** neighbours inside the 0.15 m filter, 0/8). It is a margin purchase against
a collision never observed. **Verdict: do not spend slots on it.**

**6. The descent margin - load-bearing.** `FRUIT_DYNAMIC_DESCEND_MARGIN` 0.15 ->
0 moves `g0` **100.1 -> 82.3 mm** (+17.6 / +18.3 / +17.6 / +17.7 mm at four
seeds, so the actuator is clean and graded), and it moves **every** attempt's
end-of-descent arrival from the correct side to the wrong one (`past_aim` **0/76
-> 79/79**). The catch-up then enters a **bistable** failure - converge to 6 mm or
run away to **233-269 mm**, nothing in between - on **5 of 79** attempts against
**0 of 76** (all five at seed 5, p = 0.047; pooled with the acceptance 8/89 =
9.0 % vs 1/86 = 1.2 %, p = 0.035), and placed falls **64.5 -> 51.9 %** at 4/4
seeds, the acceptance **8/10 -> 4/10** (`[P109 §1-§4]`). The half rung (0.075)
keeps the sign (+1.3 mm, 0 runaways in 75) and **buys nothing** (a count draw).
**Verdict: the margin is not a cushion - it is what makes the catch a catch-up
from the correct side. Never spend it, and do not read `fruit dy` as the gap**
(it is algebraically invariant to the knob; `g0` is the gap; `[P109 §1.1]`).

**7. The metering gate - works, too coarse.** A kinematic kerb across the belt is
a **real, cheap, non-crushing mechanism**: **16/16** pool fruits held at **every**
height tried (8, 10, 12, 14, 20, 30, 45 mm), **0 escaped**, no climb, the belt at
**-0.120 m/s in every cell**, steady drag **0.49-1.15 N** (p50 over the height
ladder), hold span **0.85-1.83 mm** p50 (max 3.7-6.6), and a taller gate parks a
fruit *further upstream*, i.e. more accurately (`[P110 §2]`). Two things break it
as a ring partner. **The queue**: the next fruit arrives inside the same 15.1 s
attempt, and the hold costs **1.8 -> 4.3 mm** with one behind, **4.9 mm**
(max 30.8) with three, and **1 of 16 is expelled** past the gate. **The
centring**: the ring's closure needs **0.6 mm**, and the gate's own best case is
**1.8 mm** within a fruit and **17.5 mm** across the pool - **3-29x** too coarse.
It removes the *arrival* term (`A_y` 182 -> 70 mm) and not the *centring* term
(`[P110 §3.2]`). **Verdict: a
real mechanism, the wrong accuracy; it is the first half of a nest, not a
solution.**

**8. The compliant closure - a gentler jam.** Three windows on the pad drive
(approach / close / hold, one knob each, the hold being a **hard stop** so a soft
close re-loads at the aperture it found) were measured across six arms
(`[P111 §2-§3]`). What compliance buys is real and exactly what it says: the
force at the close's flush falls **4.90 -> 0.6-1.8 N** (`[P111 §4.5]`). What it
does **not** buy is centring: the offset at the close's end **grows** (median
`off - off0` **+0.2 mm** rigid, **+1.9 / +0.7 / +2.0 / +1.3 mm** compliant), the
clean enclosure stays **0-3 rows per arm** (0/73 at `k = 1e3` against the rigid
ring's 3/76), and the count does not rise (**16.4 / 23.4 / 17.3 %** against
**25.0 %**, all n.s. at n = 75). The reason is the algebra's own: the aperture is
`0.98 x` the **widest** extent, so the perpendicular pair is 1-6 mm short on most
of the pool, the ring is a **two-pad V-block at every stiffness** (modal pad
count **2** in all six arms, the rigid one included), and at `mu > 1` even a
loaded pair jams (`[P111 §6]`). **Verdict: a gentler contact, not a self-centring
chuck. The lever is the contact count and the friction, not the stiffness.**
Cost: a printed or machined pad with a die spring and a shoulder - **unpriced**;
P111's §8 also prices the *force-controlled finger* form (a load cell and a
current loop, the only form that can be stiff during the approach and compliant
only inside the closure) as **unpriced**.

**9. The three-jaw ring - centres, does not convert.** The algebra clears (worst
`delta_inf/s` = **0.915**): three pads stay loaded to `delta = 2s` where a
four-jaw's far pad leaves at `delta = s`, and at the measured `mu` the fixed point
is **0.84-0.92 s** against the four-jaw's **1.00-1.46 s** (`[P112 §1]`). The build
is a third hand kind: 3 pads at 120 deg, a 20 x 60 mm plate, one scalar closure,
and one structural change - the aperture law must close on the **narrowest of its
own three pad axes** (`[P112 §2]`). The fixture (**390 closures**) is decisive:
**both** rings centre a 0-20 mm arrival to **0.5-1.9 mm**, and **only the 3-jaw
loads its own pads** (`pads == 3` on **18/30** cells against the four-pad's
**2/30**; `[P112 §3]`). On the line it reads `off0` p50 **3.2 mm** with `off -
off0` **+0.50 mm** - **no centring** - the clean enclosure is **0 of 38** (the
three `pads == 3` rows are all jams), placed is **7/38 = 18.4 %** against
**13/18 = 72.2 %**, and the 60 mm plates **block the descent** (`|v|max` **0.437**
against the 0.160-0.161 budget; `[P112 §4]`). The difference between fixture and
line is the **delivery**: a known *static* offset in the fixture, a *moving* one on
the line and a close that **freezes at first contact**. **Verdict: the jaw count
is right and it is not enough; the delivery defeats it.** Cost: a **one-off
machined assembly** - plate, scroll disc (or three links from one linear actuator),
three 120 deg carriages, three 20 x 60 mm pads - **unpriced**, and no buyable
three-jaw chuck has the 26 mm closed / 200 mm open apertures (`[P112 §6]`).

### 3.3 What the nine routes say together

| the term | measured | source |
|---|---|---|
| the shape is worth | 2x static, 9-15x creep | `[P104 §3, §5]` |
| the shape on this line | 17.6-28.1 % placed against 65.8-72.2 % | `[P107 §2]`, `[P108 §1]` |
| the closure material | a gentler jam, no centring | `[P111 §4-§6]` |
| the closure geometry | centres in a fixture, not on a moving fruit | `[P112 §4.5]` |
| the delivery | 6 mm / 3.4-4.5 mm / 1.8 mm / 17.5 mm against the ring's 0.6 mm | `[P110 §3.2]` |

**The one-sentence reading**: the pad geometry has been solved on a bench and the
*fruit presentation* has not, so every purchase order placed today would buy the
half that already works.

---

## 4. The three nails that are left

Each nail is a bench measurement that can be run **without this simulator and
without a cell**. Each has a kill criterion, so a "no" costs an afternoon, not a
purchase. Costs are the three classes the record supports: a **printed part**, a
**machined assembly**, a **station change**.

### 4.1 Nail (i) - a pad with `mu_pair < 1`

**Why it is the first nail.** It is the only term the algebra leaves standing
(§2). The four-jaw's terminal offset is `mu s` and the three-jaw's is `0.84-0.92 s`
against a requirement of `< s` - so at the measured pair friction **1.25-1.46**
the four-jaw needs more than the whole squeeze, the far pad stays short by
`(2mu - 2) s` = **0.2-0.6 mm** at any stiffness and any cap, and the three-jaw
clears the bar by only **8.5 %** (`[P111 §6.3]`, `[P112 §1]`). A pad material
below 1 would let **four** jaws centre, which is the form that carries the 2x
capacity (`[P111 §8]` item 1, `[P112 §1]`).

**What to build.** Four pads (or three) whose *face material* is chosen for its
pair friction with the fruit - the tree's pad is authored `mu = 2.0` and the sim
**averages** the pair, so the sim's 1.25-1.46 is an authored coincidence, not a
hardware fact (`[P104 §7a]`).

**What to measure** (three numbers, one rig):

1. **`mu_pair` at the working normal force** (the sim's is 4.90 N per face; the
   real jaw's is the *unanchored* number - measure it, `[P42 SIM_LIMIT §4.2]`) and
   at the working **sliding** speed (the shipped leg caps are 0.35 m/s for
   `place`, 0.37 for `lift`, 0.38 for `carry`, against a 0.12 m/s belt;
   `[P44 CAP_CENSUS]`, `[P109]`). Report the pair, not the pad alone.
2. **Creep at the operating load** - hang the fruit from the grasp, settle
   **0.75 s**, measure displacement in the grasp frame. This is the endpoint that
   matters: the pinch reads **3.20 / 0.85 / 2.68 mm** and the multi-contact forms
   **0.11-0.42 mm** (`[P104 §5]`). A 5 N/s ramp is *not* this test: its
   break-away is 10-20x the demand and does not predict the class (`[P104 §8.1]`).
3. **The axial break**, reported beside `mu` because `F_crit = n mu N` says a
   low-friction pad costs capacity. The loss is affordable: at `mu = 0.9`, four
   contacts and 4.9 N/face still give **17.6 N**, i.e. **15-100x** the 0.17-1.20 N
   the cell actually applies (`[P104 §1]`).

**Kill.** `mu_pair >= 1.0` at the working force (the four-jaw cannot centre - stop,
no material tuning rescues the inequality), **or** creep `> 1.0 mm` at the
operating load (the plan's M2a bar: 3.2x better than the pinch's 3.20-3.84 mm;
`[HAND_STAGE_PLAN §5.2]`). If `mu < 1` but the axial break falls below the
demand's 10x margin, report it - the material has traded the wrong way.

**Cost class: a printed part.** The OpenArm 2.0 fingers are explicitly
replaceable (`SURVEY §2.3` [V]), so a pad coupon is a reprinted finger plus the
fruit. **Unpriced**; the sensor version of the same bench is **~$1,020** (two
GelSight Minis, `[P104 §8]`) but this test needs **no sensor**.

### 4.2 Nail (ii) - the three-jaw on a *moving* presentation

**Why it is the second nail.** The three-jaw is the only ring measured to do both
things the closure needs - **centre** a 0-20 mm arrival to 0.5-1.9 mm and **load
all three pads** (18/30 against 2/30) - and its failure on the line is fully
separated: `off - off0` **+0.50 mm** with the payload *moving*, and a close that
**freezes at its first contact** so the delivered pinch reads **0.00 N** at its
weakest moment on 33 seated legs (`[P112 §4.3, §4.5]`). The fixture gave the same
closure a **static** offset and it centred; the line gave it a **moving** one and
it did not.

**What to build.** A 3-pad ring at 120 deg, one scalar closure, 20 x 60 mm plates,
70 mm tool offset, **200 mm open / 26 mm closed**, the aperture law closing on the
narrowest of its own three pad axes (`[P112 §2, §6]`).

**What to measure** (two cells, in this order):

1. **Static centring** - 0 / 2 / 5 / 10 / 20 mm offsets, close, read the residual
   `off_end`; the fixture's own protocol, target **<= 2 mm** (`[P112 §3]`). This
   is a *sanity* cell; it has already passed in sim and should pass on a bench.
2. **Moving presentation at 0.12 m/s** - the fruit rides a belt (or a linear stage)
   under the ring while the ring closes on the task's clock. Read three things:
   **`off - off0`** (must be **<= 0**: it must centre or at least not drift
   outward), the **aperture at the freeze against `2 delta`** (a first-contact
   freeze leaves the ring `2 delta` too wide and loads the opposite pads at zero),
   and the **descent clearance** (the plates must not meet the payload before the
   arm is at the seat; the line read `|v|max` **0.437** against the budget
   **0.160-0.161**).

**Kill.** Any of: (a) moving `off - off0 > 0` (no centring on a moving arrival);
(b) the all-three-pads-loaded state on **fewer than ~60 %** of the moving closes
(the fixture gives **18/30**; a first-contact freeze holds the aperture it touched,
`2 delta` too wide, and loads the opposite pads at zero); (c) `abs(v)max > 0.160`
(the plates block the descent). Any one means **the three-jaw is not the purchase
and the term to fix is the delivery, not the jaw count** - which is nail (iii).

**Cost class: a machined assembly.** Plate, scroll disc or three links, three
120 deg carriages, three pads; **unpriced**, and not buyable (`[P112 §6]`).

### 4.3 Nail (iii) - a stationary presentation

**Why it is the third nail and the binding one.** The ring needs **0.6 mm**
(`delta < 0.01 d`, with an elastic allowance `cap/k` of **0.049 mm**); the line
delivers the **6 mm** catch tolerance, the **3.4-4.5 mm** close offset, the gate's
**1.8 mm** within a fruit and **17.5 mm** across the pool - a **3-29x** gap, and
**92.5 %** of it **along the belt**, where no lateral guide can act (`[P110 §1,
§3.2]`). This is the only form that can reach 0.6 mm, and it is a **station**
object, not a hand.

**What to build.** The gate (a kerb at 8-14 mm, the cheapest height that both
holds and clears the hand's 14.5 mm lowest solid part; `[P110 §2]`) **plus a
magazine/nest** that takes the parked fruit and re-presents it to the ring at a
known pose. A nest must be **either per-size** (the pool is 16 classes,
29.6-69.6 mm) **or compliant** (a self-centring pocket); that is a design
requirement, not a measurement.

**What to measure:**

1. **The gate's hold under a queue**, at the shipped cadence (the next fruit
   arrives inside the same attempt): a sole occupant **1.8 mm**, one behind
   **4.3 mm**, three behind **4.9 mm** (max 30.8), **1 of 16 expelled**
   (`[P110 §2.1]`). The number to beat is **0.6 mm**, so this cell is expected to
   *fail* and it is there to size the magazine, not to pass.
2. **The magazine's re-handover**: pick from the gate, place in the nest, read the
   **residual pose error** (position + the ring's axis) over 20 trials. The target
   is **0.6 mm**. The fixture centres even a 20 mm arrival to **0.5-1.9 mm**, so a
   re-handover that lands at 1.9 mm already spends the closure's whole centring
   margin (`[P112 §3]`).

**Kill.** Re-handover residual **> 0.6 mm on more than 1 of 20** trials, **or**
the gate expels **> 1 of 16** under a 3-deep queue. Then the presentation cannot
be paired with the ring, and the honest options are: a **per-size nest** (a
machined pocket per fruit class - a workstation change), or **drop the ring** and
keep the pinch. The fallback the record names is a **sub-mm catch tolerance**
(`FRUIT_DYNAMIC_CATCH_TOL` 6 -> 0.5 mm), which is meaningful *only* with a
stationary fruit: a moving one cannot be tracked to 0.5 mm at 1 mm/tick
(`[P110 §4]` item 2).

**Cost class: a station change.** A new collider set, a selection rule (the
station window's lower edge), a pick mode, a magazine, **both motion references
re-recorded and every store re-baselined** (`[P110 §6]`). **Unpriced**; it is the
most expensive of the three by a wide margin, and it is the one the arithmetic
says is necessary.

### 4.4 The three nails in one order

The order is by cost, not by importance: (i) is a **printed part**, (ii) a
**machined assembly**, (iii) a **station change**. Each stage's pass condition is
the next stage's precondition, and no stage is skipped by argument. The tree that
ties them to the recommendation is §5.1.

---

## 5. The recommendation

### 5.1 What the partner should do first

```
                    +------------------------------------------+
                    | 0. is the END EFFECTOR the rate lever?   |-- no --> the rate
                    |    75 % of failures, 22.5 % of attempts  |          needs the
                    +---------------------+--------------------+          workstation
                                          | yes (the grasp is the goal)
                    +---------------------v--------------------+
                    | 1. BENCH  pad mu_pair + creep            |-- fail --> no ring;
                    |    mu < 1.0  AND  creep <= 1.0 mm        |            keep the pinch
                    +---------------------+--------------------+
                                          | pass
                    +---------------------v--------------------+
                    | 2. BENCH  3-jaw on a MOVING arrival      |-- fail --> the delivery
                    |    off-off0 <= 0, 3-pad >= 60 %,         |            is the term,
                    |    abs(v)max <= 0.160                    |            not the jaw
                    +---------------------+--------------------+
                                          | pass
                    +---------------------v--------------------+
                    | 3. BENCH  a nest that holds <= 0.6 mm    |-- fail --> per-size nest
                    |    after a 3-deep queue                  |            or nothing
                    +---------------------+--------------------+
                                          | pass
                    +---------------------v--------------------+
                    | BUILD  4-pad ring + nest; re-run M3      |
                    |        >= 150 episodes, all references   |
                    +------------------------------------------+
```

1. **Do nail (i) this week.** It is one reprinted pad, one fruit, a luggage scale
   and a linear stage. It answers the only question the algebra leaves open, and
   it has a hard kill (`mu >= 1` -> no ring geometry works; `creep > 1.0 mm` -> the
   material does not buy the class). Nothing else in the lane is worth spending
   before it.
2. **Do nail (ii) next, on the same bench**, with a moving fruit. It is the only
   test that separates "the jaw count is wrong" from "the delivery is wrong", and
   the record already says it is the delivery (`[P112 §4.5]`). If (ii) fails and
   (i) passed, the answer is a ring *plus* a stationary presentation, not a
   different ring.
3. **Do nail (iii) only if (i) and (ii) pass.** It is a station change and it
   costs a re-baseline of every number in this repo; do not start it on a
   maybe.
4. **Do not buy a hand, a tactile pad, or a ring before (i).** No purchase order
   in this lane has a positive measured case: the tactile is detected-not-
   convertible, the 3+1 topology is geometrically wrong, the four-pad cage runs
   17.6 % and the three-jaw 18.4 % (n = 40 blocks) - all against the shipped
   pinch's 72.2 %.

### 5.2 What would make the cell ship a better rate

* **The ceiling is measured and it is not 100 %.** If every `cnp` converted, the
  four-seed pool would read **75/80 = 93.8 %**; the survey's `+8 points` bar is
  **8 of 17 conversions = 47 % of the class** (`[HAND_STAGE_PLAN §5.0]`). The
  acquisition class (5 of 22 failures) is **unreachable by any pad** - it is a
  hand-over timing failure whose failing residuals are **220-481 mm**
  (`[P47]`, `[P48]`).
* **No end-effector route measured so far ships a better rate alone.** The best
  measured *on the line* at n = 40 is the shipped pinch's **72.2 %** (its 8/10
  acceptance is a 10-attempt sample of the same branch); the cage family reads
  17.6-28.1 % and the three-jaw 18.4 % (`[P107 §2]`, `[P108 §1]`, `[P112 §4.1]`).
  What would ship the rate is the **pair**: a ring that is *placed* around the
  fruit (nail iii) and *centres* (nail i or ii). That is a workstation + an end
  effector, and its price is a station change **plus** a recollection - both
  motion references re-recorded and every store re-baselined (`SURVEY §4.3`).
* **The alternative is legitimate**: keep the pinch, keep 72.5 %, and accept that
  75-77 % of the failures sit in a class this line's presentation cannot let any
  hand reach. A partner should hear that as an option, not as a failure of the
  analysis.

### 5.3 What must never be re-tried

One line each, with the number that closes it. These are not opinions; each has a
measured number behind it.

| never re-try | why (the number) | source |
|---|---|---|
| **the force family** (cap, squeeze, interference, relief, load rate) | 2.2x delivered pinch (4.4 -> 9.8 N) does not convert; 30 N and 60 N delete the pry and the class remains (7 -> 3 escape legs at 60 N); 60 N crushes a 3.7 cm strawberry out of the hand | `[P41 P3 §2]`, `[P76 §3]`, `[P77 §4]`, `[P42 SIM_LIMIT §1]` |
| **the seat** (pre-close centring, grip plane, x/y aim) | the pads are centred to **1.36-4.65 mm on 20/20** grips, the escapes are the *tightest* seats, and the available correction is **30-60x** smaller than the walk | `[P42 SIM_LIMIT §2]`, `[P42 P2_RESULTS]` |
| **the clearance pre-pose** | shipped by P97 and **reverted by P98**: acceptance **6/10 against 8/10**, seed-5 cell **12/20 against 17/20**, interval **16.02 against 10.59 s** | `[P96]`, `[P97]`, `[P98]` |
| **the place-station move** | **0 of 588** IK cells pass over +-0.15 m at the place height and the transfer, both arms, three attitude modes; the best solved attitude anywhere is **77.75 deg at the shipped station** | `[P90 §2-§3]` |
| **the profile blocks** (release / place / lift / take-off probe) | release **shipped** (-0.64 s, real); place **negative** (interval 10.59 -> 13.23, 11.08 -> 12.11); lift **negative** (10.59 -> 13.43, 11.08 -> 12.38); the probe **negative** (clean grip -0.31 s exact, first-probe success 14/20 -> 5/20) | `[P87]`, `[P88]`, `[P89]`, `[P91]` |
| **the candidate planning** | the convertible wait is **18.2 % of the interval and all of it is cross-lane**, i.e. a sort error; priced with grade-pure routing off, the interval rises **+6.8 % / +5.3 %** and **17 of 40** fruit are mis-sorted | `[P99]` |
| **the park return** | **-0.62 s per slot** of park motion buys a pooled interval of **+0.5 %** at four seeds; the arm that returns earlier simply waits | `[P100]` |
| **the fail-fast abort** | **-5.14 s** on the failed attempt and the throughput does not follow: interval **26.72 -> 35.26 s**, count **12 -> 6** at seed 5 | `[P83]`, `[P84]` |
| **the tactile reflex** | a **perfect** detector converted **0 of 5** same-instance `cnp`s, destroyed **2 of 2** placements, interval **+15.3 %**; the 8 mm carry-monitor gate is the hard ceiling | `[P102 §2]`, `[P103 §4-§6]` |
| **the closure depth** | a 6 % interference (instead of 2 %) reads **1 of 17**: the ring is off-centre, so a deeper close pushes the payload further off | `[P108 §3]` |
| **the aperture / spacing as a rate lever** | aperture: placed **p = 0.37**, the fresh seed **reverses** it; spacing: **1 -> 5 starved slots of 20** and placed **16/57 -> 6/35** | `[P108 §2-§4]` |

**Also closed, if the partner asks** - the pad face shapes `v/h/x/c` (2-6/10
against flat 6-8/10; the additive wings bat the catch, `[P42 SIM_LIMIT §1]`), the
scoop/cradle (no-contact 2 -> 9 of 15, `[R8-A §3]`), the finger-tip shortening
(no arm improves in any evaluable comparison, `[P39]`), and the supply band's top
(the two-seed **28 -> 36** becomes **58/80 -> 65/80** at four seeds with the gain
all from one seed, `[P92]`, `[P93]`).

### 5.4 What this book does not price

* **A real jaw's delivered pinch and compliance.** The sim's 9.8 N is a
  force-saturated position drive; a real jaw needs a bench anchor before any
  fidelity claim (`[P42 SIM_LIMIT §4.2]`, `[P41 DEVIATION]`). Until then, the
  absolute forces are the sim's, and the ratio `n/2` is the transferable part.
* **Bruising.** The sim has **no bruise model**; "60 N works" is a geometry and
  retention statement, never a fruit-quality one (`[P77 §0]`).
* **The 3-jaw, the 4-pad ring and the magazine.** All three are **unpriced**;
  none is a catalogue product at these apertures (`[P112 §6]`).
* **The recollection.** A hand or a station change invalidates every store; the
  measured anchor is **158 episodes in 2 h 6 min** on this machine, plus a full
  re-baseline of all three motion references (`SURVEY §4.3`, `[P85 §1]`).
* **The wall clock of a two-line session.** The scheduler pays **1.69x wall/sim**
  after P82's wake fix (2.57-2.59x before it); a wall-throughput claim must quote
  that factor, not just the simulated clock (`[P82 §4]`).

---

## 6. Sources

Every `[Pnnn]` above expands to the file below; `§` in a citation means that
file's section (or the section of the named companion file).

| tag | file | what it is |
|---|---|---|
| `[P42 SIM_LIMIT]` | `logs/p42/SIM_LIMIT.md` | the class's **canonical record**: the mechanism, the closed families, the two sanctions |
| `[P42 SEAT_CENSUS]` | `logs/p42/SEAT_CENSUS.md` | the seat census (1.4-4.7 mm on 20/20 grips) |
| `[P41]` | `logs/p41/P3_RESULTS.md`, `DEVIATION.md` | the drive-profile flip and the force cap |
| `[P40]` | `logs/p40/EFFORT_READ.md` | the command is at its cap, the delivered reaction is 22 % of it |
| `[P44]` | `logs/p44/CAP_CENSUS.md`, `P2_RESULTS.md` | the caps (2.1x velocity, 2.4x effort) and the speed cells |
| `[P47]` `[P48]` | `logs/p47/ACQ_CENSUS.md`, `logs/p48/HANDOVER_CENSUS.md` | the catch-up residual, 8/8 no-grasp above 6 mm; the x tail |
| `[P61]` `[P74]` `[P75]` `[P76]` `[P77]` | `logs/p61/P2_RESULTS.md`, `p74/P1_RESULTS.md`, `p75/RESULTS.md`, `p76/RESULTS.md`, `p77/RESULTS.md` | the escape direction, the place-leg class, the wedge, the force ladder, 60 N |
| `[P83]` `[P84]` | `logs/p83/RESULTS.md`, `logs/p84/RESULTS.md` | the fail-fast abort (single arm, two-line) |
| `[P85]` | `logs/p85/RESULTS.md` | the shipped cell (two-line default) |
| `[P87]`-`[P91]` | `logs/p87/RESULTS.md`, `logs/p88/RESULTS.md`, `logs/p89/RESULTS.md`, `logs/p91/RESULTS.md` | the profile blocks: release, place, lift, take-off probe |
| `[P90]` | `logs/p90/MAP.md`, `COST.md` | the place-station map (0/588) |
| `[P92 CENSUS]` | `logs/p92/CENSUS.md` | the failure-class census (9 + 3 of 40) |
| `[P93]` | `logs/p93/RESULTS.md` | the four-seed count (58/80, intervals) |
| `[P96]`-`[P98]` | `logs/p96/RESULTS.md`, `logs/p97/RESULTS.md`, `logs/p98/RESULTS.md` | the clearance pre-pose, its flip, its revert |
| `[P99]` | `logs/p99/RESULTS.md` | the candidate-planning census |
| `[P100]` | `logs/p100/RESULTS.md` | the park return |
| `[P102]` | `logs/p102/RESULTS.md` | the tactile **signal** (patch channel, 0.17-0.94 s) |
| `[P103]` | `logs/p103/RESULTS.md` | the tactile **reaction** (0/5 converted, 2/2 destroyed) |
| `[P104]` | `logs/p104/RESULTS.md`, `analytic.py`, `analytic.txt` | the critical-wrench fixture and the analytic frame |
| `[P106]` | `logs/p106/RESULTS.md`, `mount_census.txt` | the Allegro mount (M1) and the 4-pad surrogate (M2a) |
| `[P107]` | `logs/p107/RESULTS.md`, `m1_cage.txt` | the radial 4-pad cage built and run (M2b/M3) |
| `[P108]` | `logs/p108/RESULTS.md`, `CENSUS.md` | the aperture, the spacing, the arrival census |
| `[P109]` | `logs/p109/RESULTS.md`, `PREREG.md` | the descent margin (load-bearing) |
| `[P110]` | `logs/p110/RESULTS.md`, `CENSUS.md` | the metering gate and the enclosure re-census |
| `[P111]` | `logs/p111/RESULTS.md`, `algebra.txt` | the compliant closure and the `mu > 1` algebra |
| `[P112]` | `logs/p112/RESULTS.md`, `algebra.txt`, `fixture_report.txt` | the three-jaw ring (fixture + battery) |
| `[R8-A]` | `logs/r8/A_RESULTS.md` | the D screen: the scoop's ledges bat the payload |
| `[W8-B]` | `logs/w8/B_RESULTS.md` | `clean_slip`, the escape metric |
| `[SURVEY]` | `docs/PLATFORM_SURVEY.md` | the platform/tactile/hand selection and prices |
| `[HAND_STAGE_PLAN]` | `docs/HAND_STAGE_PLAN.md` | the milestones M1-M3 and the ceiling arithmetic |

**Tree state at writing** (P113): no `src/` or `configs/` change. The shipped
defaults are the P85 two-line cell with P87's release trim, P71's low lift and
rail removal, P41's drive profile, and P43/P54/P58's direct-presentation defaults.
`configs/motion_reference.json` = `..._twoline.json` = **`30fb99f8`** and
`..._single.json` = **`8952c320`** - untouched by this phase (P113 reads them, does
not write them; `scripts/selfcheck.sh` is the authority). Every phase record above
carries its own pins.
