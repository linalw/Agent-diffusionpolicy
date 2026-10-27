# P48 phase 1 — the hand-over timing census

Offline phase: **no simulator, no `src/` edit, no commit.** Tree read clean at HEAD
`2eec1a4`; `tasks.py` **`b6de439c`**, `fruits.py` `dff684b1`, `rl_env.py`
`93e35ef7`, `configs/motion_reference.json` **`8a399626`**,
`..._twoline.json` **`2246f83c`** (the P44/P45/P46 battery pins, unchanged). The
files written are this one, `PREREG.md` and the read-only reader
(`handover_census.py` -> `handover_census_out.txt`).

The question: **P47's `dynamic catch-up: residual` above its 6 mm tolerance reads
8/8 no-grasp and its failing values are 219-481 mm — what produces them, does the
"2.4x the reach budget" reading hold, and is the hand-over timing the lever?**

The answers, in order: the residual's inputs are **the fruit's delivered lateral
x**, not the hand-over distance; **no** (2.40x is the maximum, 1.10-1.26x the other
three); and **no** — the hand-over lead is 0.189 m on every attempt in the corpus,
including all eight failing rows, and it is *coupled by construction* to the
selector floor, so raising it starves the belt before it shortens a catch.

---

## 1. The residual population, re-derived (P47 reproduced exactly)

`handover_census.py` re-parses the four corpora and reproduces P47's counts
(317 closes, 8 rows > 6 mm, 11 converged no-grasp, 207/91/19), then adds each
attempt's *inputs*.

| corpus | measured logs | attempts | closes (residual rows) | rows > 6 mm | those attempts | residual min / p50 / p90 / max (mm) | `\|x\|` >= 0.38 | placed / cnp / nograsp / skip |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| shipped (`p41/p2/accept_profile`, `p39/p3/pear_C`) | 2 | 20 | **19** | **0** | — | 5.6 / 5.9 / 5.9 / 6.0 | 0 | 12 / 7 / 0 / 1 |
| P44 speed (`p44/p2/*`, 16 measured; `amend_driver.log` is a 12-line stub) | 16 | 160 | **159** | **4** | 4 nograsp | 5.4 / 5.9 / 6.0 / **251.0** | 6 | 104 / 44 / 11 / 1 |
| P45 mass (`p45/p2/*`) | 10 | 100 | **99** | **0** | — | 5.6 / 5.9 / 6.0 / 6.0 | 0 | 59 / 40 / 0 / 1 |
| P46 two-line (`p46/p1/*`) | 4 | 40 | **40** | **4** | 4 nograsp | 5.4 / 5.9 / 6.0 / **480.6** | 2 | 32 / 0 / 8 / 0 |
| **pooled** | 32 | 320 | **317** | **8** | **8 nograsp** (0 placed, 0 cnp) | **5.4 / 5.9 / 6.0 / 480.6** | **8** | 207 / 91 / 19 / 3 |

Every close prints a residual (317/317); the 3 non-rows are the `no eligible
fruit` skips, which never close. The 2x2 is P47's: **> 6 mm -> 8/8 no-grasp vs
<= 6 mm -> 11/309 = 3.6 %**, Fisher exact **p = 3.27e-11**. The distribution is
**bimodal with an empty band**: the values are 5.4-6.0 mm then a gap to
**219.6 / 245.8 / 251.0 / 480.6** — nothing between 6.0 and 219.6 in 317 rows.

**The 8 rows are 4 distinct attempt-events**; each reproduces bit-identically
across its scenario's cells or arms, so the row count is not the event count:

| event | residual | rows | where |
| --- | --- | --- | --- |
| **E1** | 219.6 mm | 1 | `p44/p2/accept_s5_S2.log` attempt 1 |
| **E2** | 245.8 mm | 1 | `p44/p2/amend_F_S2.log` attempt 1 (the S2 cell re-run) |
| **E3** | 251.0 mm | 4 | `p44/p2/twoline_s5_{C,S13}`, `p46/p1/twoline_s5_{C,U}` (one attempt, four logs) |
| **E4** | 480.6 mm | 2 | `p46/p1/twoline_s6_{C,U}` (one attempt, two logs) |

---

## 2. The four events, and what they share

Every field below is a row of the attempt itself; `ordinal` marks the two-line
rows, where the arm is recovered from the `dynamic descent` row's own
`station` field and the catch-up row is paired to it in print order (the
per-arm row counts validate 5/5/5/5/5 for every two-line log; the species of
each `[biarm] result` matches its arm's `target` row).

| | **E1** | **E2** | **E3** | **E4** |
| --- | --- | --- | --- | --- |
| log / attempt | `accept_s5_S2` 1 | `amend_F_S2` 1 | `twoline_s5` 13 (ordinal) | `twoline_s6` 7 (ordinal) |
| arm / species / diameter | left / kiwi / 5.6 cm | left / kiwi / 5.6 cm | left / kiwi / 5.4 cm | **right** / kiwi / 6.2 cm |
| **delivered x at the wait loop** (`fruit_x`) | **+0.3969** | **+0.3966** | **+0.3908** | +0.2730 |
| selection distance `dy0` | +0.3849 | +0.4420 | +0.4486 | +0.3902 |
| lead (`intercept handover dy` / `lead`) | 0.1889 / **0.189 m** | 0.1890 / **0.189 m** | 0.1883 / **0.189 m** | 0.1888 / **0.189 m** |
| `queue` at handover | 2 | 2 | 5 | 4 |
| `arrived after N steps` | 196 | 253 | 382 | 202 |
| descent `waited N ticks` | 65 | 68 | 59 | 53 |
| descent shift (aim - station) | +0.0172 | +0.0178 | +0.0179 | +0.0172 |
| `closing anyway` fingertip number | 61 mm | 61 mm | 59 mm | 59 mm |
| **`[motion] approach ... end=`** | **15.3 mm** | **14.8 mm** | **10.1 mm** | **10.6 mm** |
| **catch-up residual** | **219.6** | **245.8** | **251.0** | **480.6** |
| **residual - 200 mm** (the loop's belt travel) | **+19.6** | **+45.8** | **+51.0** | **+280.6** |
| close row | no contact row; `kinematic grip closed to 5.41 cm around 5.58` | none; `5.38 around 5.58` | none; `5.22 around 5.38` | **`sustained contact after 5 ticks (force=58.15 N, span=99.1 mm)`** |
| re-seats | 2 | 2 | 2 (gap 37.2 mm, twice) | 0 in this attempt; the `[carry]` row is `contacts@onset=0`, `force_min=0.00 N`, 38 trips |
| `close: fruit drifted N mm off the pick centre` | — | — | — | **379 mm (cross-belt)** |
| outcome / lift | nograsp / +0.000 | nograsp / +0.000 | nograsp / +0.000 | nograsp / +0.000 |

### 2.1 What they share

**(a) The lateral tail: 3 of the 4 events (one instance drawn twice, plus one).**
The delivered x of E1/E2/E3 is the **99th-100th percentile** of the 317-close
population; E4's is the 46th.
Band table (all 317 closes):

| `\|x\|` band | rows | > 6 mm | placed | cnp | nograsp |
| --- | --- | --- | --- | --- | --- |
| <= 0.25 | 106 | 0 | 55 | 45 | 6 |
| 0.25-0.30 | 86 | **2** | 74 | 10 | 2 |
| 0.30-0.35 | 78 | 0 | 58 | 17 | 3 |
| 0.35-0.38 | 39 | 0 | 20 | 19 | 0 |
| **0.38-0.39** | **2** | 0 | 0 | 0 | **2** |
| **>= 0.390** | **6** | **6** | 0 | 0 | **6** |

`|x| >= 0.390`: **6 of 6 rows fail**, Fisher **p = 2.08e-11** against 2/311 below.
`|x| >= 0.38`: **8 rows, 0 placed, 0 cnp, 8 no-grasp** — the corpus never places
a fruit delivered past 0.38 m. The clean reach band measured for the top-down
catch is **x = 0.18-0.39 with a hard cliff at 0.42** (`scripts/174`, AGENTS §2),
and the spawn band is only x = 0.20-0.36: the tail is **P38's per-instance
release offset** (measured to +69.2 mm), not a supply-design value.

**Kiwi is a proxy, not an independent cause.** All 4 events are kiwi, and the
`|x| >= 0.38` set is *only* kiwi (0 peach, 0 pear, 0 strawberry rows reach it) —
the same confound P38 already named (the offsets rank kiwi > orange). Within
kiwi the test is decisive: **`|x| >= 0.38` -> 8/8 no-grasp vs 2/27 below,
Fisher p = 1.91e-06.** Nothing in this corpus separates "kiwi" from "the lateral
tail", and the tail is the measurable variable.

**(b) The selection distance, the lead, the queue, the hover: none of them.**
`dy0` ranks 49-74 %, `wait_ticks` 3-31 %, the `closing anyway` number 32-65 %;
the `queue` at handover spans **1-5 over the whole corpus** (277 x 1, 361 x 2,
73 x 3, 19 x 4, 15 x 5 handover rows), so the events' 2-5 is mid-population.
**The lead is a constant 0.189 m on all 317 attempts**
(189 ticks of belt travel), so it cannot be a discriminator at all.

**(c) The descent ends further short — on the single-arm events only.**
`approach ... end=` is the descent's own last commanded-vs-achieved gap, printed on
every attempt (attributable on all 317 rows: the row is printed once per attempt in
the same order as the descent, so the two-line's k-th approach belongs to its k-th
attempt): the successful population reads **8.1-10.6 mm** (207 placed p50 9.2 /
max 10.4; 91 cnp p50 9.5 / max 10.6; the 11 converged losses 8.5-10.0), and **the
only two values above 10.6 mm in 317 closes are E1 (15.3) and E2 (14.8)**. The
two-line events read **10.1 (E3) and 10.6 (E4)** — inside the successful range, so
the shortfall tracks the **x tail** (E1/E2 at 0.3966-0.3969) rather than the
catch-up's outcome. At x ~ 0.397 the left arm's descent is already 4-5 mm further
from its aim: the same lateral cause, one stage earlier.

`end=` as a pre-close signal, measured: `>= 11.0 mm` fires on **2/317 rows, both
E1/E2, 0 false positives**; `>= 10.1 mm` fires on 53 rows (25 placed, 20 cnp, 8
failing) and is **not specific**. So it is sensitive to the lateral tail only.

### 2.2 The mechanism the arithmetic gives

The loop runs up to 200 ticks (`FRUIT_DYNAMIC_CATCH_TICKS`, `tasks.py:9930`) and in
that time the belt delivers **200 x 1.0 mm = 200 mm**. That is the *maximum* gap
the fruit can open, so the residual is a **bound on the tip's net progress**:

| | E1 | E2 | E3 | E4 |
| --- | --- | --- | --- | --- |
| fruit travel during the loop | 200 mm | 200 mm | 200 mm | 200 mm |
| residual | 219.6 | 245.8 | 251.0 | **480.6** |
| implied net tip progress (200 - residual) | **+19.6** | **+45.8** | **+51.0** | **-280.6** |

For E1-E3 the tip recovered **at most 20-51 mm of the 200 mm** the fruit moved, i.e.
**<= 25 % of the belt's own rate** for the whole loop, and the residual is the belt
travel plus a 20-51 mm entry gap. E1's entry gap has an independent check: the
descent's `end=` is **15.3 mm** (the population's highest) and the aim carries
`shift = +0.0172 m`, so a 19.6 mm entry gap is what the descent leaves behind. The
descent is arrival-synchronised; when it ends short the fruit is already
**downstream** of the tip, where the loop's direction-aware lead takes the branch
that commands the fruit itself with no feed-forward (`tasks.py:9975-9984`) and the
drive can at best follow at the belt's speed. The gap then cannot close.

E4 is **not that mechanism**: 480.6 with a 200 mm maximum means the residual cannot
be belt travel at all, and the log carries the matching evidence - `close: fruit
drifted **379 mm** off the pick centre (cross-belt); re-closing on it where it is`,
the corpus's **only** cross-belt drift row, in both s6 arms, and a **58.15 N /
99.1 mm-span** close after 5 ticks (the placed population's close force is
4.3-16.6 N). 0.2730 + 0.379 = 0.652 m and 0.2730 - 0.379 = -0.106 m: the fruit was
displaced **off the belt's inner edge (0.110 m)**. So E4 is a **target
displacement** mid-approach, not a timing miss; the `[carry]` row of that attempt
(380 ticks, `clean_slip 371.2 mm`, `contacts@onset=0`, `force_min=0.00 N`, 38 servo
trips) is the never-held signature, and the P46 §8 table already shows the same
instance lost identically in the C arm - it is the **scenario's** event, not a
cell's, and the union arm merely draws it too.

**Which is a candidate cause for the displacement, not a measured one:** the
two-line's other arm (the left) was descending on its own pear in the same
interleaved window, and the right station's fruit passes *through* the left
station's corridor 0.10 m upstream; a neighbour depenetration kick in the dense
wave cluster (0.09-0.12 m separation) is the second candidate. **Not separated
here** (see §6).

---

## 3. The reach budget in numbers — and the P47 correction

Per-tick geometry, unchanged from the record: belt **0.12 m/s**
(`assets.py:215`, `FRUIT_BELT_SPEED`) / control **120 Hz** (`tasks.py:53`,
`CONTROL_DT`) = **1.0 mm per tick**.

| quantity | value | source |
| --- | --- | --- |
| catch-up horizon | **200 ticks = 1.667 s** | `FRUIT_DYNAMIC_CATCH_TICKS` `tasks.py:9930` |
| catch-up tolerance | **6 mm** | `FRUIT_DYNAMIC_CATCH_TOL` `tasks.py:9931`, break at `:9967` |
| belt travel inside one horizon | **200 mm** | 200 x 1.0 mm |
| close ramp | 24 + 60 = **84 ticks (0.70 s)**, up to 2 attempts | `tasks.py:9824-9825`, `FRUIT_CLOSE_ATTEMPTS` `:9889` |
| residual -> ticks / seconds of belt travel | 219.6 -> 219.6 / 1.83 s; 245.8 -> 2.05 s; 251.0 -> 2.09 s; 480.6 -> 4.01 s | this census |
| residual / horizon | **1.10 / 1.23 / 1.26 / 2.40x** | this census |

**The 2.4x claim holds for E4 only.** P47's sentence ("a target 2.4x the
catch-up's reach budget away") is the *maximum*, and it is the one event that is
**not** a timing miss: the three timing-shaped events are **1.10-1.26x** — inside
one extra horizon of belt travel, which is exactly the §2.2 bound (belt travel
during the loop + a 20-51 mm entry gap). Two further corrections:

* **"reach budget" is a misnomer.** 200 mm is not a reach limit of the arm; it is
  how far the *belt* delivers the fruit while the loop runs. The arm's own limit is
  the lateral band (§2.1), and the failing instances sit **0.8-6.9 mm past its
  0.39 m clean edge** (E3 0.3908, E1/E2 0.3966-0.3969) - so the margin the events
  exceed is a *few millimetres of lateral reach*, not 200 mm of travel.
* **A threshold guard still cannot be built from it.** The convertible band for a
  distance-triggered wait is empty (nothing between 6.0 and 219.6 mm), so any
  threshold in (6, 220) mm fires on 0/309 converged closes and on all 8 failing
  rows — where closing (or waiting) on a fruit 20-51 mm away is a bat, not a
  grasp. P47 §4's prediction stands on this corpus.

---

## 4. The candidate levers, their sites, and which event each would catch

All five exist as shipped env knobs; **unset = the shipped tree**, so a battery of
them needs no `src/` edit.

### 4.1 The hand-over lead — caught by the census, not by a run

| | |
| --- | --- |
| site | `_dynamic_pick_lead()`, `tasks.py:6053`; formula `:6062-6078` (`FRUIT_DYNAMIC_OVERHEAD_S` 0.4, `FRUIT_DYNAMIC_APPROACH_VMAX` 0.15 -> `t_desc` 0.775 s, `FRUIT_DYNAMIC_DESCEND_MARGIN` 0.15, `FRUIT_DYNAMIC_LEAD_MARGIN` 0.03) |
| value | 0.12 x (0.4 + 0.775 + 0.15) + 0.03 = **0.189 m** — exactly the printed `lead=0.189` on every attempt |
| what it moves | **how long the hand hovers before the descent starts** (the descent is arrival-synchronised on `deadline`), and - through `_dynamic_select_floor()`, `tasks.py:5959` - **the selector's upstream floor** |
| why it cannot be the lever | the failing events are **post-handover**: the lead is identical (0.189 m) on all 8 failing rows and on all 309 converged ones, and the catch-up's entry gap is produced *after* the hand-over, by the descent's shortfall and the lateral aim |
| arithmetic of a strong form | +170 mm of lead (`FRUIT_DYNAMIC_LEAD_MARGIN=0.20`) -> the floor rises **0.399 -> 0.569 m** (0.359 + 0.12 x 1.5 + 0.03) against a measured `dy0` max of 0.570 m, i.e. it consumes the whole selector window, and it adds **1.42 s (9 %)** of hover to every attempt |
| events it would catch | **0 of 4** |
| risk | the never-stop invariant holds (the hover is free of collision risk), but the floor coupling is the P1c starvation lever, and the cost is paid on every attempt |

### 4.2 The catch-up budget (`FRUIT_DYNAMIC_CATCH_TICKS` 200 -> 400)

| | |
| --- | --- |
| site | `tasks.py:9930` (read per attempt, inside the close), break test `:9967` |
| what it moves | how long the loop chases a target it is not converging on |
| which events | **E4 only if the displaced fruit re-settles**; **strictly worse on E1-E3**: the residual is the belt travel (200 mm per 200 ticks) plus a 20-51 mm entry gap, so +200 ticks add **~+200 mm** (219.6 -> ~420, 251.0 -> ~450) and the close is then 400 mm behind |
| risk | +1.67 s on 2.5 % of attempts (the pool cost is 0.04 s/attempt); a longer ride beside a moving fruit is a dirty-contact risk; zero effect on 309/317 closes (they break at <= 6 mm) |

### 4.3 The selection floor (`_dynamic_select_floor`, `tasks.py:5959`)

Along-track **only**: `lead + v * FRUIT_DYNAMIC_SELECT_S(1.5) + margin(0.03)` =
**0.399 m**. It admits or refuses candidates by their *arrival* time; the failing
events were admitted at `dy0` 0.385-0.449 (E1 sits *below* the shipped floor
because it is read at the wait loop, after the pre-pose). Raising it cannot move
a fruit sideways, so **0 of 4**; lowering it is the v9 pre-fix collapse.

### 4.4 The approach speed (`FRUIT_DYNAMIC_APPROACH_VMAX`, `tasks.py:6066`, `:9484`)

0.15 m/s; the measured descent peaks are 0.108-0.117 m/s and the `end=` shortfall
is the workspace boundary, which gains were measured **not** to move (`logs/165`,
AGENTS §2). It changes `t_desc` -> the lead -> the floor (the same coupling as
4.1) and cannot buy back the lateral boundary: **0 of 4**, and it is the only
knob in this list that touches the entry gap at all (through the descent's
settling time), which is why it is the *named* residual rather than a lever.

### 4.5 The early close (raise the tolerance / break early)

There is **no knob**; the site is the break at `tasks.py:9967`. A threshold in
(6, 219.6) mm converts nothing (§3: the band is empty) and closes on air 20-51 mm
from the fruit, which is the P47/P44 bat class. **0 of 4.**

### 4.6 The two levers §4's list does not contain (and why the plane moves there)

1. **A lateral gate / re-aim**: `FRUIT_POLICY_TRIGGER_X_MAX=0.39` exists but is
   **direct-path only** (W4/R2); the scripted catch has no x refusal, and the
   `FRUIT_REACH_ANYWHERE` family is measured negative on the shipped cadence
   (R11-A 9/10 -> 4/10; R11-A.1's floored form 4/9).
2. **The supply**: compensate the per-instance release offset at `respawn`
   (P38's registered P38b). It removes the **3 of 4** events **by construction**
   (2.1: no fruit is delivered past 0.38 m) and costs three motion references,
   the scripted acceptance, both two-line gates and every store. It is the only
   lever that converts events, and it is **not a §4 lever** - it is the next item,
   not this phase's.

**Correction to the brief's code map.** `tasks.py:2081 _catch_up_drive` is the
**drive-target ramp** (20 ticks, joint space, before a new leg) and has nothing
to do with the pre-close catch-up, which is the inline loop at
`:9958-10037`. `_reach_catchup_used` (`:874`, set `:10011`, printed `:10014`)
exists **only** under `FRUIT_REACH_DIAG` and is never consumed: a reporting
no-op whose `self.` storage is shared by the two-line's two arms (a latent
cross-attempt write, harmless today because nothing reads it).

---

## 5. The 11 converged close losses (residual <= 6 mm, no-grasp)

11 rows, **6 distinct events** (the two-line logs reproduce an attempt on both
arms/across arms; the S1/amend pair is one event).

| event (rows) | species / dia | x0 | residual | close row | grip echo | re-seats | carry onset |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `accept_s5_S1` 1 + `amend_E_S1` 1 | kiwi 5.6 | 0.3802 | 5.5 | 22 t, **9.24 N**, span 70.1 | 61.7 around 55.8 (**+5.9**) | 2 | `contacts@onset=0`, `sep 31.7`, `gap_start 46.7`, `force_min 0.00`, `loss_row 1`, slip 736.5 |
| `accept_s5_S3` 3 | lychee 3.0 | 0.2239 | 6.0 | **60 t**, 8.6 N, span 42.5 | 27.1 around 29.6 (-2.5) | 2 | — |
| `accept_s6_C` 0 + `s6_S13` 0 | strawberry 3.1 | 0.3162 | 5.8 | 50 t, **35.85 N**, span 39.2 | 26.3 around 31.4 (-5.1) | 2 | — |
| `twoline_s5` 12 (4 logs) | peach 6.9 | 0.2395 | 5.9 | 21 t, 9.54 N, span 76.0 (diameter-matched) | 67.3 around 68.9 | (arm-blind) | — |
| `twoline_s6_U` 0 | peach 6.6 | 0.3343 | 6.0 | not attributable | — | — | lift +0.040 |
| `twoline_s6_U` 13 | peach 6.6 | 0.2306 | 6.0 | not attributable | — | — | lift +0.002 |

The close row **is not printed on every attempt** (9 closes for 10 attempts in the
s5 log), so the two-line members are paired by their diameter echo instead of by
order - the s5 peach resolves (`21 ticks, 9.54 N, span 76.0` for the 6.9 cm peach)
and reads **inside** the placed population: the *through* sub-class, not the bat.

**What distinguishes them is the *aftermath*, not any pre-close field.**

* **Pre-close: nothing.** The residual (5.4-6.0), `x0` (0.22-0.38), `dy0`
  (0.27-0.57) and the close's span all sit inside the placed population. The
  `grip_closed - diameter` echo (the tempting discriminator) **does not
  separate**: losses -5.10..+5.90 mm (n = 5) against placed -9.70..+5.90 mm
  (n = 159, p50 -1.40) — the +5.90 mm "blocked short" value also occurs on
  placements. It is a *commanded* echo of the ramp, not evidence of contact.
* **The aftermath is 100 % specific on the single-arm rows.** Every single-arm
  converged loss prints **2 `dynamic regrasp: re-seated` rows**; **0 of the 159
  single-arm placed attempts** print any (the flag is set only by this branch).
  (The two-line logs' re-seat rows are arm-blind in this reader - and there a
  *placed* pear also re-seats twice in `twoline_s6` - so the specificity is
  claimed **single-arm only**, and the two-line members of this class rest on
  their `[carry]` rows.) Where `FRUIT_CARRY_DIAG` was on: `contacts@onset=0`,
  `min_contacts=0`, `force_min=0.00 N`, `sep@onset` 29.8-64.7 mm - the pads are
  closed on air or through the payload.
* **Two force sub-signatures sit outside the placed range** (close force 4.3-16.6
  N, p50 10.0): the s6 strawberry at **35.85 N**, and E4's own attempt at
  **58.15 N** (a > 6 mm event, not one of these 11 - quoted for the shared bat
  signature); the S3 lychee's close takes **60 ticks** against the placed maximum
  of 49. So the close either completes its ramp around air
  (span 27-42 mm, no contact) or meets the payload too hard and too early (a bat).

**The mechanism is the closed grip/hold class, not the acquisition class** — the
same W8-B loaded-slide / P41-P42 "the pads hold and the payload leaves" family
that `logs/p42/SIM_LIMIT.md` records as geometry/hardware. A "converged" residual
means the fingertip is within 6 mm of `fruit + pad_lift`; it does not mean the
payload is retained through the close. **No hand-over-timing lever reaches
these**, and phase 2 must not target them.

---

## 6. What this settles, the instrumentation gap, and what it does not claim

**Settled.**

1. The residual's discriminating input across 317 closes is the **fruit's
   delivered lateral x**, not the hand-over distance: `|x| >= 0.38` is 8/8
   no-grasp (0 placed) against 2/309 below, and within kiwi 8/8 vs 2/27
   (p = 1.91e-06). The lead is a **constant** in the whole corpus.
2. **3 of the 4 events are that tail** (E1/E2 one instance drawn twice, E3 a
   second instance at 0.3908); **E4 is a target displacement** (379 mm cross-belt,
   the corpus's only drift row, and 2.40x the horizon). No single mechanism covers
   all four.
3. P47's "**2.4x the reach budget**" is the **maximum, and it belongs to the one
   event that is not a timing miss**: the timing-shaped three are **1.10-1.26x**.
   "Reach budget" should read "**belt travel inside the 200-tick horizon**".
4. The **11 converged losses are the grip class** (re-seat rows, `contacts@onset=0`,
   the 35.85/58.15 N closes), with no pre-close surface: they are out of this
   item's scope.

**The instrumentation gap phase 2 must close.** The catch-up's *tick count* and
the residual's *components* are not in these logs: `FRUIT_REACH_DIAG` /
`FRUIT_ACQ_DIAG` are off, and the one line that carries the components -
`[diag] catchup <arm>: residual=... jaw=[...] fruit=[...] tip_y-fruit_y=...`
(`tasks.py:10040-10052`, `FRUIT_HANDOVER_DIAG=1`) - was never enabled. The
`end=` proxy (§2.1c) is printed on every attempt and separates 15.3/14.8 from
8.1-10.6, so it carries the mechanism read for the battery; the `[diag]` row is
what turns "200 + 19.6 mm" from arithmetic into a measured vector. Instrumentation
is part of the measurement (AGENTS §2/§3b), so `PREREG.md` carries the
neutrality proof as a condition.

**Corrections to the record carried here.** (i) `tasks.py:2081 _catch_up_drive`
is the drive-target ramp, not the pre-close catch-up (the two are different
objects and the brief's pointer conflates them). (ii) "2.4x the reach budget"
(§3). (iii) `_reach_catchup_used` is diag-only and unconsumed (§4 note).

**What this does not claim.** No rate: every count here is a deterministic
branch's count (AGENTS §2), the two-line rows are ordinal-paired, and the events
are **instance-bound and branch-bound** - 3 of the 4 are kiwi instances at the
release-offset tail, so a battery on a leg whose fruit draw does not contain them
**cannot** re-measure them (the shipped acceptance/pear arms hold 0 of 8 rows).
No claim about the hybrid/policy/direct interfaces (out of scope), none about the
displacement's cause in E4 (two candidates, unseparated), and none that the x
tail is the *only* acquisition mechanism - it is the only one visible in 317
closes of this tree.

Evidence: `logs/p48/handover_census.py` (the reader) and
`logs/p48/handover_census_out.txt` (its full output: per-corpus tables, the band
table, the per-event percentile ranks, the tick decomposition, the 11 losses, the
two-line arm-count validation). Every log cited is an existing artefact of
P39/P41/P44/P45/P46/P47.
