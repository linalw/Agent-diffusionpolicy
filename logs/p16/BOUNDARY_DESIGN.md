# P16: the descent-boundary design — the diagnosis refresh, the bounded options, the pick, and the pre-registration sketch (Tier C offline)

Status: **offline design lane, read-only on the tree** (branch `p-supply`, 2026-10-19). No
simulator run, no `src/`/`scripts/`/`configs/`/`datasets/`/`Paper/` write, no commit; all writes
under `logs/p16/`. Tree pins as read: `tasks.py` `810658b802d22bbd63013726fc78af81`, `fruits.py`
`d28546d26137d4540421caa7fa34a139`, `meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`.

**The mission.** Design the **descent-boundary lever** — the named next after the P15's
conserved-mass finding (`logs/p15/OUTCOME_RESULTS.md`: the M2 hold-window lead moved the
mechanism, the outcome traded; "the failure mass is a conserved quantity across the tested
close/carry actuators"). The K1 branch it executes (`logs/p15/CLOSE_HOLD_DESIGN.md` §K1): the
hold walk may be the hand's own descent-settling motion, in which case no close/hold actuator
moves it and the next named item is the descent-boundary/scene family.

**The inputs read.** `logs/p15/OUTCOME_RESULTS.md`, `SCREEN_RESULTS.md`, `CLOSE_HOLD_DESIGN.md`,
`logs/p14b/TRACE_RESULTS.md` + `master_table.md` + `trace_p14b_tables.txt`, `logs/p12a2/`
(the mass base: `A2_RESULTS.md`, the three `*_mass.log` runs), `logs/p12b/SCENE_OPTIONS.md` +
`S3_RESULTS.md`, `logs/r8/A_RESULTS.md`, `logs/r10/A_RESULTS.md` + `A1_RESULTS.md` +
`reach_intercept_{left,right}.json`, `logs/r11/A_RESULTS.md` + `A1_RESULTS.md`,
`logs/w8/B_RESULTS.md`, `logs/r6/B_RESULTS.md`, `logs/p11c/{C,C2,C3}_RESULTS.md`, `logs/p11b/`
(the plow/probe), `logs/160_endgap028.log` … `logs/167_collision_noconveyor.log` (the boundary
arc), `WORKLOG.md` ("the descent is blocked by the conveyor", "the descent's shortfall is a hard
boundary"), `AGENTS.md` §2, and the descent/aim/catch-up code in `tasks.py` (read-only).

**This lane's own measurements** (all re-derivable offline):
`logs/p16/descent_boundary_analysis.py` → `logs/p16/descent_boundary_tables.txt` +
`descent_boundary_summary.json` (the `end=` rows per seed; the per-attempt hold-walk
decomposition from the 60 P14-B traces; the ejection/tracking/handoff reads; the R10 map
re-derivation). The class labels come from the P14-B `master_table.md` (the P10-E rules), so the
per-class tables below are directly comparable to the P14-B/P15 records.

---

## 0. The answer in one screen

* **The diagnosis (new numbers, §1).** On the mass base the descent's shortfall is
  **8.1–15.3 mm (median 9.2, n=60)** — five times smaller than the v1 line's 40–90 mm — and the
  post-descent solver (the catch-up loop) closes it to **5.1–6.0 mm** in 8–98 ticks (median 12). The aim
  (`station + 0.0170…0.0180`) is **inside** the R10 clean bands; the belt-collision stop
  (jaw z 1.247) is **10–38 mm below** the grip aim (`fruit_z + 0.070`); the standoff axis is
  measured **closed on both sides** (S3 +20 mm negative at every seed; D2a −8 mm negative; −10 mm
  a belt jam). **The boundary is not the binding constraint on this scenario.**
* **The K1 branch (the walk is the hand's settling) is refuted on the mass base (§1.3).** On the
  three hold-walk B1s the hand's own y motion is **−1.6 / −13.2 / +3.4 mm** while the fruit
  slides **−35.6 / −41.7 / −47.6 mm**; the hand's x (+22.5…+34.0) is the bounded x-seek following
  the fruit's own squeeze-out (the fruit's |vx| peak 0.185 m/s) and the hand's z (−8.5…−10.5) is
  a sag that **grows with the slide** (z_err −1.9 mm at the freeze → −11.0 mm at the hold's end;
  the oks: −3.3 → −4.3). The B1 failures' handoffs are **cleaner** than the oks' (the
  post-descent residual 13.2–14.4 vs 11.1–61.7 mm; the handoff relative velocity −27.7 mm/s
  "matched" vs the oks' +90.5 median "at-rest"). The walk is the **loaded slide**; the hand's
  motion is its **response**, not its cause.
* **The three bounded options (§2):** **(a) the completed descent** — the arrival closed-loop at
  the aim (a bounded settle) + the per-attempt boundary verification; **(b) the pick station clear
  of the belt** — the scene (catch-null by the P12-B.2 derivation; the bounded proxies D2a/D2b/D3/S3
  all measured negative; the full D3 form owner-gated; the S4 containment is the *falls-only*
  companion); **(c) the boundary-aware post-descent handoff** — the settled/verified acquisition
  (a sustained residual + the `[handoff]` state row).
* **The ranking (§3): 1. (a); 2. (c); 3. (b).** (a) is the only option that moves the mission's
  *first* mechanism endpoint — the descent's `end=` shortfall, **a quantity no prior lever has
  ever moved** (the gains `logs/165`, the integral bias `logs/163`, the speed budget — all failed)
  — and it is **upstream of the capture**, so a conversion is not a trade by construction: unlike
  the close/carry actuators (which disturb the carry they hand the payload to), a descent-side
  change hands the *shipped* carry its payload. (c)'s mechanism is directly refuted by the
  handoff read (the B1s *are* the matched-handoff class). (b) is owner-gated and catch-null.
* **The pick (§4): (a)** — `FRUIT_DYNAMIC_ARRIVE_TOL=0.006` + `FRUIT_DYNAMIC_ARRIVE_MAX=24`
  (a `src/` change, default-off, dynamic-capture-scoped) with the `[arrive]`/`[boundary]`
  diagnostics; a Stage-M mechanism screen at SEED 11 against the on-disk traced control, ONE
  promoted arm → the outcome battery at SEED 11/5/23.
* **The strongest reason it could fail (§5):** the premise is already partially refuted — the B1
  failures' handoffs are *cleaner* than the oks', so the most likely read is **the `end=` falls
  but the hold walk does not move**: K1 closes the descent-boundary family with the measured
  negative (the shortfall does not feed the capture), which is the design's primary value.

---

## 1. The diagnosis refresh (the mass base + the P14-B/P15 traces)

Everything in this section is either (M) a record number or (P) this lane's re-derivation from
the committed logs/traces (`logs/p16/descent_boundary_analysis.py`; the class labels from the
P14-B `master_table.md`).

### 1.1 The descent shortfall (the `end=` rows)

The mass base (`logs/p12a2/{10_seed11,11_seed5,12_seed23}_mass.log`, 60 descents):

| seed | `end=` mm (n=20) | distance cm | \|v\|max m/s | samples |
| --- | --- | --- | --- | --- |
| 11 | 8.3–15.3, med 9.4 | 5.5–5.8 | 0.107–0.118 | 86–92 |
| 5 | 8.2–12.9, med 8.9 | 5.5–5.9 | 0.105–0.112 | 86–94 |
| 23 | 8.1–11.9, med 8.9 | 5.5–5.8 | 0.108–0.110 | 86–91 |
| **pooled** | **8.1–15.3, med 9.2** | 5.5–5.9 | 0.105–0.118 | 86–94 |

The dynamic catch's descent is a **5.5–5.9 cm hover→grip leg** (the hover 0.06 m), the aim is
`station + 0.0170…0.0180` (the intercept clip `FRUIT_DYNAMIC_INTERCEPT_MAX` 0.03), the hover
wait 50–88 ticks (0.42–0.73 s), the deadline 0.100–0.104 m, `t_desc` 0.68–0.72 s.

**The v1/static-line record for contrast** (the AGENTS §2 numbers, all committed):
`logs/161` (shipped) 42,88,46,45,43,48,80,45,59,47 mm (median 47); `logs/160` (carry cap)
42,90,40,43,50,77,62,54,72,50 (median 51); `logs/163` (integral bias on the drive target)
median 53 mm and `|v|max` doubled — withdrawn; `logs/165` (soft gains, τ 0.2 → 0.04 s)
unchanged. The collision probe: with the belt the jaw stops at **z = 1.247** after 3.8 cm of
commanded travel (`logs/166`), without it 23 cm (`logs/167`); the left finger's bounding box
then spans z = [1.146, 1.215] — below the belt top 1.170. **On the v1 line the pick pose was
outside the reachable band; on the mass base it is not.**

**The aim vs the boundary (P).** The dynamic grip's jaw target is
`(fruit_x, station + lead, fruit_z + 0.070)`; with the observed fruit centres
(z 1.187–1.215) the aim's jaw z is **1.257–1.285** — i.e. **10–38 mm above** the measured
collision stop (1.247), and the +20 mm standoff (S3) and −10 mm standoff (the jam) are the
measured closures of the axis. The R10 map's grip solves read jaw z 1.247–1.305 with the 6 mm
residual — the grip pose is *at* the boundary's edge, not beyond it.

### 1.2 The post-descent solver's role (the catch-up)

The catch-up loop (the "post-descent solver") runs after the descent and closes the residual to
its 6 mm tolerance:

* **What it inherits (P, the first catch-up row):** the tip–fruit offset is **dz +15.1…+22.0 mm**
  (median +17.3; the desired tip is fruit_z + 10 mm, so the descent ends **5–12 mm high**) and
  **dy −4.7…−56.2 mm** (median −11.9; the tip downstream of the fruit — the designed timing
  margin, ~12–18 mm of late arrival at 0.12 m/s). The residual against the desired tip:
  **11.1–61.7 mm (median 14.6)**.
* **What it delivers:** the loop exits at **5.1–6.0 mm** (the `dynamic catch-up: residual=` rows,
  60/60) after 8–98 ticks (median 12; one outlier at the 98-tick tail); the R8-A note stands:
  **the floor is the loop's threshold-crossing value, not a measured reach margin**.
* **What the close inherits (P):** the hand picks up the belt speed over the close's first ~8
  rows (the jaw's y velocity −0.105 m/s vs the fruit's −0.12); the hand's z sits **3.3 mm below**
  its command at the freeze (the oks; B1 −1.9, carried −3.5, B2 −4.4) and sags through the hold.

So on this scenario the solver's job is **small** (a ~15 mm acquisition), and it completes it
*before* the close starts. The v1 line's "the post-descent solver finishes the approach" (the
40–90 mm shortfall) does **not** reproduce on the mass base.

### 1.3 The hold walk decomposed (the K1 branch's test)

The walk per the P14-B rule (the drift change across the hold from the freeze) reproduces to
≤ 1 mm on all 60 attempts. This lane's additional decomposition (the world-frame relative
displacement fruit − jaw across the freeze → last hold row, plus the hand's own motion):

| class | n | walk mm (freeze rule) | rel_dy (belt axis) | rel_dx | rel_dz | jaw_dy | jaw_dx | jaw_dz | z_err @freeze→@hold_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ok | 45 | 0.1–13.7, med 1.1 | −10.6…+1.9, med −0.1 | −2.2…+7.8 | −0.2…+7.5 | −57.7…+43.1 | −27.0…+43.8 | −6.1…+11.1 | −3.3 → −4.3 |
| carried | 7 | 3.6–6.8, med 5.2 | −2.8…+0.5 | −3.0…+4.6 | +2.7…+5.9 | −51.5…−2.0 | −36.1…+16.2 | −6.7…+1.1 | −3.5 → −7.2 |
| **B1** | **5** | **1.1–55.6, med 32.8** | **−51.1…−1.0, med −28.5** | **−9.2…+1.1** | **+0.3…+11.4, med +9.9** | **−46.9…+3.4** | **−16.8…+34.0** | **−10.5…−0.3** | **−1.9 → −11.0** |
| B2 | 3 | 0.3–2.8, med 1.2 | −1.5…+0.4 | −0.6…−0.1 | +0.1…+2.4 | −42.6…−7.1 | −17.8…−0.3 | −2.4…+1.0 | −4.4 → −4.8 |

**The three hold-walk attempts in detail** (the P15's targets, s11 attempts 1/7/9, all left):

| attempt | walk mm | rel_dy | rel_dx | rel_dz | hand dy | hand dx | hand dz | fruit \|vy\| peak | handoff relv_y |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a01 orange | 38.9 | −34.0 | −9.2 | +10.1 | −1.6 | +29.8 | −8.5 | 0.25 m/s | −25 mm/s |
| a07 tomato | 32.8 | −28.5 | −2.7 | +9.9 | −13.2 | +22.5 | −9.4 | 0.21 | −28 |
| a09 orange | 55.6 | −51.1 | −6.3 | +11.4 | +3.4 | +34.0 | −10.5 | 0.20 | −24 |

**The reading (the K1 refutation):**

1. **The hand's own y motion is not the walk.** On the three hold-walk attempts the hand moves
   −1.6…+3.4 mm in y across the whole 0.4 s hold while the fruit slides 34–51 mm. The hand is
   *not* settling along the belt; the fruit is *leaving*.
2. **The hand's x motion (+22.5…+34.0) is the x-seek following the fruit's own squeeze-out.**
   The fruit's |vx| peak during the hold reads 0.185 m/s (B1 median; the ok 0.071) — the payload
   is extruded out along the closing axis, and the bounded x-seek (`FRUIT_DYNAMIC_X_TRACK_VMAX`
   0.12) follows it. The hand's x and the fruit's x move together (a01: hand +29.8, fruit +20.6).
3. **The hand's z sag (−8.5…−10.5) grows with the slide, it does not precede it.** The z_err at
   the freeze is **−1.9 mm on the B1s** vs −3.3 on the oks — the failing attempts enter the hold
   *closer* to their z command; the −11 mm is reached at the hold's end, i.e. it is the pads
   slipping down the escaping payload (the W8-B `+z` walk-out class), not a pre-existing settling.
4. **The ejection separates the B1s**: the fruit's |vy| peak during the hold is
   0.109–0.251 m/s (median 0.205) vs the oks' median 0.078 (max 0.204) — the B1 payload
   *accelerates* past the belt speed while the pads hold it; the oks' fruit is *arrested*
   (0.078). The mechanism is the loaded slide the W8-B/R6-B records describe.
5. **The handoff state does not separate the classes — it is inverted.** The post-descent residual
   (B1 13.2–14.4 mm) and the freeze z_err (−1.9) are *better* than the oks' (14.6 / −3.3); the
   handoff's relative tip–fruit velocity puts **all 5 B1s in the "matched" band
   (−24…−30 mm/s)**, and the at-rest band (≥ +50 mm/s) holds **23 oks and only 3 fails** (the
   2×2: matched 9/15 fails vs 18/45 oks; at-rest 3/15 vs 23/45). A "settled/matched" handoff is
   *not* the success signature on this scenario — the converse is (weakly) true.

**Verdict on the K1 branch:** the hold walk on the mass base is **the loaded slide** (the belt
shear + the squeeze-out), and the hand's own motion is the **response**. The "the walk is the
hand's descent-settling motion" hypothesis is refuted at the level the traces can measure: the
settling term is secondary (10–35 mm of hand motion vs 28–51 mm of fruit slide on the B1s),
it is *downstream* of the slide in time (the z sag grows with it), and the failures' handoff
states are cleaner, not worse. **This is the single most important input to the design.**

### 1.4 The reach-band geometry (the aim vs the R10 map)

The R10 `183_reach_intercept` map re-derived (`logs/r10/reach_intercept_{left,right}.json`;
`grip_residual` mm per (x, dy), 6 mm tolerance; the two-line stations left y=0.00, right y=−0.10):

| arm | x=0.20 | x=0.28 | x=0.36 |
| --- | --- | --- | --- |
| left (station-relative) | −0.10…+0.15 | −0.05…+0.10 | 0.00…+0.10 |
| right (station-relative) | 0.00…+0.20 | 0.00…+0.15 | 0.00…+0.10 |

* **The catch aim is inside every band**: the intercept is `station + 0.0170…0.0180`, and the
  supply band is x = 0.20–0.36 (plus the drift tail to 0.148). A reach query at the aim is a
  **no-op on this scenario** (the R10-A/R11-A aim family is excluded from the two-line by design
  and measured negative on the single arm anyway: the acceptance 9/10 → 4/10 (R11-A), the floored
  variant 4/9 (R11-A.1), whose left failures were the *post-catch hold* class).
* **The capture sweep leaves the band on almost every attempt — including the successes.** The
  fruit's position at the hold's end is 20–147 mm downstream of the applicable band edge: the ok
  class median −53 mm, the B1 median −124 mm, the carried −78 mm, the B2 −78 — **overlapping
  ranges, no class separation**. (The arm tracks the fruit anyway; the clean band is a 6 mm-tolerance
  solve band, not a hard stop.) A "keep the sweep inside the band" aim shift therefore has no
  measured target on this scenario.
* The cliff: x = 0.42 (55 mm residual). The fruit's x across the capture spans **0.121–0.449**;
  the 5 attempts whose fruit ends the hold past x = 0.39 are **all oks** at this n — the x-cliff
  is not the failure driver either.

### 1.5 The belt collision's role (the boundary's other side)

* The measured stop: jaw z 1.247 with the belt (`logs/166`), 23 cm without (`logs/167`).
* The dynamic grip aim: jaw z 1.257–1.285 (10–38 mm above the stop); the achieved grip is
  ~5–12 mm *higher* still (the descent's shortfall) — so the descent is **not pressing into the
  belt** on this scenario.
* The standoff axis is closed on both sides: **+20 mm (S3) negative at every seed** (45/60 → 32/60;
  the falls up at every seed; `logs/p12b/S3_RESULTS.md`), **−8 mm (D2a) negative** with its
  implementation confound named (`logs/r8/A_RESULTS.md`), **−10 mm a belt jam** (the fingertips
  0.6 mm inside the slab, 27–89 N, `logs/p11b`). The belt collision's practical role on the mass
  base is the **low-side bound of the standoff axis** and the small-fruit margin (the smallest
  fruit's aim sits ~10 mm above the stop).

---

## 2. The bounded fix options (scene-side and command-side)

Each option: the exact change → the mechanism (why the failure mass would reduce rather than
trade) → the expected movement → the cost → the risks → the falsifier.

### 2.1 (a) The completed descent — the arrival closed-loop at the aim, + the boundary verification

* **The exact change (default-off, dynamic-capture-scoped, `src/fruit_sorting/tasks.py`).**
  After the jerk-limited descent profile completes (the cartesian branch of `_approach`,
  `tasks.py:10241-10261`, reached from the moving catch at `tasks.py:7272-7274`), continue
  commanding the aim (`arm.ik_step(target)` + `self._step_sim(1)`) until the measured TCP error
  ≤ `FRUIT_DYNAMIC_ARRIVE_TOL` (new knob, test value 0.006 m) or `FRUIT_DYNAMIC_ARRIVE_MAX`
  (new knob, test value 24 ticks) have run. `MAX=0` = the shipped behavior (byte-unchanged).
  The catch-up then starts from the *arrived* pose; its own 6 mm tolerance and budget are
  unchanged. Add a pure-reporting `[arrive]` row per dynamic descent (the initial `end=` gap, the
  settled gap, the ticks, the direction) and a `[boundary]` row per attempt (the aim's reach
  margin from the R10 columns + the finger–belt margin: the aim's jaw z − (belt_top + the finger
  drop)) — the mission's "the pick pose vs the reachable band" made explicit per attempt.
* **The mechanism (why the mass would reduce rather than trade).** The capture starts from the
  *commanded* pose: the residual convergence that currently happens *inside* the close/hold
  (the close's first ~8 rows, the z_err's growth) is moved *upstream* of the load. The
  "reduce-not-trade" argument is structural: the descent is **upstream of the capture**, so a
  converted no-grasp hands the *shipped* carry its payload — unlike the close/carry actuators
  (M2's lead, C1's rate), which disturb the carry they hand the payload to and therefore re-draw
  the class instead of reducing it. The P15's three instances all traded because they acted
  *inside* the capture window; (a) acts *before* it.
* **The expected movement.** The mechanism: the `end=` median 9.2 → ≤ 6 mm; the catch-up's
  first-row residual median 14.6 → ≤ 8 mm; the close's early z_err moves toward 0. The outcome:
  the no-grasp class (B1/B2) down *if* the marginal arrest's slip budget is consumed by the
  transient; the carried class unchanged (the carry geometry is untouched); the falls down with
  the no-grasp (fewer escapes → fewer belt-end drops; the mass base's falls are 6 rows/5
  attempts, s11 3 + 1 partial, s23 3, s5 0, plus 1 blowup row).
* **The cost.** A `src/` change (~15–25 lines + the stub/executed-identity check, the P12/P13
  pattern) + the Stage-M screen (~10 min, traced) + Stage P (6 runs ~60 min) + the no-harm
  (~15 min). Env-only once built. Tier A solo.
* **The risks.** (i) **The belt collision for small fruit**: the arrival lowers the *achieved*
  pose by up to ~10 mm toward the aim; the smallest fruit's aim sits ~10 mm above the stop, and
  the −10 mm standoff is a measured jam (0.6 mm inside the slab, 27–89 N) — the screen must read
  the finger–belt contact/jam class and the `[boundary]` margin. (ii) **The D2a direction**: the
  effective contact plane moves ~2–4 mm lower on the fruit (the probe's 6.9 mm/20 mm mapping) —
  the *clean* version of the D2a axis (no break-test shift), so a D2a-like class movement here is
  a measurement, not a confound. (iii) **The span**: 10–24 extra ticks per descent = 10–24 mm of
  belt travel at 0.12 m/s (~1–2 % of the 14.3 s cycle, but 10–25 % of the ~96 mm close+hold
  capture window) — the capture window shrinks correspondingly. (iv) **The
  class re-draw** (the K2 kill: the never-grasped/no-grasp grows ≥ 2 — the C1 signature). (v) The
  P11-C/P12 negative families do not apply (no control-side arrival change, no physics/scene
  change, no supply/clearance interaction).
* **The falsifier.** The `end=` falls (the arrival works) but the **hold walk does not move**
  (the mechanism gate K1) → the shortfall does not feed the capture; the descent-boundary family
  closes with the measured negative. Or the `end=` does not fall within the cap → the drive
  cannot converge to the aim in a bounded window on this cell (the AGENTS §2 "the pose the arm
  cannot hold" refined: on this scenario the pose is holdable, the *servo settling* is the wall).

### 2.2 (b) The pick station clear of the belt — the scene

* **The exact change.** The D3-proper form: a pick station the hand reaches clear of the belt +
  a self-centring feeder + the boundary-respecting descent (the R8-A D3's second half, never
  implemented). The bounded proxies in the record: the D3 nest proxy (`FRUIT_NEST=0.02
  FRUIT_NEST_WIDTH=0.05`) 1/20 with `recirculated` 0 → 13; D2a/D2b; S1 (a raised deck);
  S3 (+20 mm) — all measured negative or catch-null.
* **The mechanism — measured against the derivation.** The P12-B.2 derivation: the catch is
  **fruit-relative** (the aim = the fruit's measured x/z + the station + the standoff; the
  catch-up's break test and the re-seat use the same fruit-relative targets), so **a station that
  raises the fruit and its support together moves every target and the collision together — the
  catch is invariant**. Only a *narrow* cradle (the fingers straddle; the fruit rises relative to
  the surface under the fingers) changes the fruit-relative geometry, and its static form is
  unstable (46+ mm drifts) and gates (a stopped fruit = the v2 stop semantics); the driven form is
  a new build with the D3 supply risk. On the mass base the belt is **not the binding constraint**
  anyway (10–38 mm of margin; the standoff axis closed both ways). **There is no measured
  mass-reducing mechanism in this option**; the only certain movement available in the scene
  family is the S4 containment (a belt-end keeper + side fences), which is **grip-null** and
  moves the **falls** only.
* **The expected movement.** The no-grasp/carried: ~0 by derivation; the falls: down with S4
  (the measured exit path: the ejected B1 fruit rides the belt to the end and drops within the
  attempt).
* **The cost.** The highest (a scene build + the feeder/IK work + the battery x2 + the supply
  re-measure at `scripts/170_transport_probe.py`); owner-gated (the R8-A close-out; the AGENTS §2
  "settle what the criterion should mean with the owner").
* **The risks.** The D3 obstruction class (any device in the moving supply's path); the supply's
  selection-floor interaction (a slowed/deflected fruit inherits the R11-A collapse: the shipped
  acceptance 9/10 → 4/10); the two-line clearance (the hand's dwell sweep, ±0.066 m span); the
  two-line semantics (a gate at either station starves the downstream one).
* **The falsifier.** The supply moves (`recirculated` up / a "never settled" note / a rate
  collapse — the D3 replay) or, with the supply intact, the class/falls read flat → the
  containment's recovery mechanism is refuted.

### 2.3 (c) The boundary-aware post-descent handoff — the settled/verified acquisition

* **The exact change (default-off, dynamic-capture-scoped, `src/`).** In the catch-up loop's exit
  (`tasks.py:7555-7565`): require the residual < `FRUIT_DYNAMIC_CATCH_TOL` for
  `FRUIT_HANDOFF_ACQUIRE_TICKS` consecutive ticks (default 1 = shipped) instead of the single-tick
  crossing; optionally hold the arrived pose for `FRUIT_HANDOFF_SETTLE_TICKS` before the close;
  add the `[handoff]` state row (the residual, the relative tip–fruit velocity, the tip–fruit
  offset, the band margin at the fruit's x) — the solver's completion made explicit.
* **The mechanism (claimed).** The close starts from a *verified* acquisition: the fruit is
  between the pads, the hand has converged, and the close's first load tick is not spent on a
  transient. Same reduce-not-trade structure as (a) (upstream of the capture).
* **The measured refutation (state it plainly).** The control's handoff state **does not
  separate** the classes — and it is **inverted**: the B1 failures are the *matched* handoff
  class (all 5 at −24…−30 mm/s; the oks' median +90.5 "at-rest"), the B1s' post-descent residual
  (13.2–14.4) and freeze z_err (−1.9) are *cleaner* than the oks' (14.6 / −3.3). The
  "at-rest" handoffs (the fruit sliding through a stationary tip) hold 23 oks and 3 fails. So
  the acquisition-quality hypothesis has no support on this scenario; the most likely read is
  flat.
* **The expected movement.** The mechanism: the handoff's |relv| distribution compresses; the
  walk: ~0 expected (the refutation). The outcome: ~0. The falls: ~0.
* **The cost.** Low (`src/` ~15–25 lines + the stub + the same screen shape as (a)).
* **The risks.** The span (the settle's travel, 6–24 ticks); the class re-draw; and the P15's own
  M2 lesson — the *lead* (the only measured variable in this window) traded the outcome, so a
  re-test of the same window's dynamics is the least informative use of a run.
* **The falsifier.** The walk does not move (expected) → the "the capture starts from an
  unsettled hand" hypothesis closes; or the walk moves but the class re-draws (the M2 pattern).

---

## 3. The ranking and the pick

The ranking criterion (the P15 design's): **the expected movement per the trace's localization ×
the cost × the risk**, with the evidence quality as the tiebreak.

| # | option | the endpoint it can move | the expected movement | the cost | the risk | the decisive evidence |
| --- | --- | --- | --- | --- | --- | --- |
| **1** | **(a) the completed descent** | the **descent's `end=`** (never moved by any prior lever) + the catch-up's inheritance | the mechanism: certain (the `end=` read); the outcome: small-to-moderate, direction **positive by construction** (upstream of the capture) | `src/` ~20 lines + 1 screen + Stage P | the small-fruit belt margin; the span; the class re-draw | the AGENTS §2 named fix; the `end=` is the *unmoved* quantity (the gains/bias/budget all failed); the boundary is otherwise measured-closed |
| **2** | (c) the handoff completion | the handoff's state + the walk | ~0; the premise **refuted** (the B1s are the matched class) | `src/` ~20 lines + the same screen | the span; the class re-draw; the M2 window re-tested | the control's handoff read (the inversion) |
| **3** | (b) the scene | the falls (S4 only) | the class ~0 (catch-null); the falls down | the highest; owner-gated | the D3 supply class; the selection-floor collapse; the clearance | the P12-B.2 derivation + the measured proxies (D2a/D2b/D3/S3) |

**The pick: (a).** Why, in order:

1. **It is the only option that moves the mission's first mechanism endpoint.** The descent's
   `end=` shortfall is the one quantity in this arc that **no lever has ever moved** (the drive
   gains `logs/165`, the integral bias `logs/163` — withdrawn, the speed budget — owner-gated
   and forbidden to re-tune). If the arrival completion does not move it, that is itself a hard
   measured statement about the cell; if it does, the walk/mass question is answered next.
2. **It is upstream of the capture, so it cannot trade by construction.** The P15's conserved
   mass came from actuators *inside* the capture window; a descent-side change hands the shipped
   carry its payload. This is the only mechanism in the three options with that structure.
3. **It is the AGENTS §2 / WORKLOG named fix** ("a descent command that respects the boundary by
   construction — a calibrated clearance, or a reach query") in its bounded, env-only-after-build
   form — the family's own next item, not a new hypothesis class.
4. **Its negative is high-value and cheap**: the K1 gate (the `end=` falls, the walk flat) closes
   the descent-boundary family with the measured statement that the shortfall does not feed the
   capture — the last open branch of the K1 question — and redirects the program to the
   outcome-side residual (the carried class) or the owner-gated D3-proper.
5. (c) ranks below because its premise is *directly* refuted by the control's own handoff read
   (§1.3.5), and the one measured variable in its window (the lead) already traded at the outcome
   (M2). (b) ranks third: catch-null by derivation, the bounded proxies negative, owner-gated —
   and its only certain movement (the S4 containment) is a falls lever, not the failure mass.

**The companion (budget permitting, not the pick): (c)'s `[handoff]` diagnostic + the sustained
acquisition** can ride the same Stage-M block as the second arm (one more traced run at SEED 11);
it is the *same screen shape* and its flat read is the K1 companion. The S4 containment is *not*
in this screen (it is a scene change with its own battery per the P12-B.2 pre-registration).

---

## 4. The pre-registration sketch (to be frozen before any run)

**One paragraph.** On the mass base — `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1
FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_PHYSICS_REAL_MASS=1
ATTEMPTS=20 HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_CARRY_MONITOR_DIAG=1 FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR=logs/p16/traces_<arm>_s<SEED>`,
`scripts/run.sh scripts/20_pick_place.py`, Tier A solo through `scripts/154_claim_run.sh` — run the
**Stage-M mechanism screen at SEED 11**: **M0 the control** (already on disk:
`logs/p14b/traces_s11/` + `logs/p12a2/10_seed11_mass.log`; no run), **H1 (the pick)
`FRUIT_DYNAMIC_ARRIVE_TOL=0.006 FRUIT_DYNAMIC_ARRIVE_MAX=24`** (the completed descent + the
`[arrive]`/`[boundary]` rows), and the optional **H2 (the budget companion)
`FRUIT_HANDOFF_ACQUIRE_TICKS=12`** (the settled handoff + the `[handoff]` row); promote **at most
ONE** arm to **Stage P** iff (a) its mechanism endpoint moves — H1: the `end=` median falls
**≤ 6 mm** (from 9.2) and the catch-up's first-row residual median falls ≤ 8 mm (from 14.6); H2:
the sustained acquisition holds on **≥ 18/20 attempts** (the residual < tol for `ACQUIRE` ticks;
the control's exit is the single-tick crossing) — **and** the
**hold walk** falls into/below the ok ceiling (≤ 20 mm, inside the 12.8 → 31.9 gap) on ≥ 2 of the
control's three hold-walk attempts **or** the seed-11 no-grasp count falls ≥ 2 with the hold-walk
attempts converting; **and** (b) the probe-1 first departures do not rise and the probe-1 dz does
not worsen; **and** (c) no new failure reason (in particular no finger–belt jam / no new gripper
note) and no never-grasped/no-grasp growth ≥ 2; the promoted arm then runs the **outcome battery
at SEED 11/5/23** (the same env, one run per seed, each with a bit-identical double): the
**no-grasp class** (the P10-E rules), the **carried-not-placed**, the **falls** (the `lowest
payload point` ≤ −1000 mm rows; the partials −100…−1000 reported separately; the control: 6 rows
/ 5 attempts + 1 partial + 1 blowup), the **pooled outcome** (the total failure mass), and the
mechanism read (`end=`, the catch-up residual, the hold walk, the `[arrive]` convergence, the
`[boundary]` margin); the **kills** are K1 (the mechanism gate: H1's `end=` moves but the walk
does not — close the phase at M, publish the mechanism negative, do not spend P), K2 (the class
re-draw: the never-grasped/no-grasp grows ≥ 2 at seed 11 or ≥ 2 pooled), K3 (a non-bit-identical
double — the scripted line is deterministic), K4 (the no-harm fails), K5 (a concurrent Tier-A job
or a wedge corrupts a run); the **no-harm** half runs with the knobs unset: `scripts/accept.sh`
9/10 + `fingerprint: matches configs/motion_reference.json`, the two-line dense re-record +
`scripts/190_twoline_gate.sh` PASS, `scripts/selfcheck.sh` PASS, and the knob-off seed-11 control
replaying `logs/p12a2/10_seed11_mass.log` byte-identically (the `[fruit]` lines) — the new knobs
are env-only and default-off, so the shipped single-arm and two-line defaults are byte-unchanged
by construction.

### The structured form

**Scenario.** The mass base verbatim (`logs/p12a2/run_battery.sh`): the two-line patch env +
`FRUIT_PHYSICS_REAL_MASS=1`, `ATTEMPTS=20`, plus the reporting env
(`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1
FRUIT_DYNAMIC_TRACE=1`). Seeds: **11 primary** (11 ok / 2 carried / 7 no-grasp; the only seed
with hold-walk B1 mass), **5 / 23 controls** (17/3/0 and 17/2/1). The trace is run-neutral on
this scenario (measured: the three P14-B runs replay the mass base byte-identically), so the
mechanism and the outcome come off the same runs.

**Arms.** Stage M (SEED 11, traced): M0 = the on-disk control (no run); H1 = the pick (the
arrival completion); H2 (optional, budget) = the handoff completion. Stage P (the promoted arm
only): SEED 11/5/23 + the seed-11 double (K3).

**Mechanism endpoints** (the trace's own rules, re-derived by `logs/p14b/trace_p14b_analysis.py`
verbatim + this lane's `descent_boundary_analysis.py`):
(i) **the descent's `end=`** per attempt (the control 8.3–15.3, med 9.4 at seed 11) and the
`[arrive]` convergence (the settled gap, the ticks); (ii) **the hold walk** per attempt (the
P14-B rule; the control's ok ≤ 12.8, the three hold-walk B1s 31.9/38.1/54.8); (iii) the
**post-descent state** (the first catch-up row's residual and the tip–fruit offset — the
inheritance H1 shrinks); (iv) the **`[boundary]` margins** (the aim's reach margin + the
finger–belt margin) as the boundary check (H1 must not drive the small-fruit margin negative);
(v) the **probe-1 first departures + dz** (the grip test, the gate's item b); (vi) H2's
`[handoff]` state row (the residual dwell, the relative velocity).

**Outcome endpoints** (Stage P): the **no-grasp class** (the P10-E rules; the control 7/0/1), the
**carried-not-placed** (2/3/2), the **falls** (the `lowest payload point` ≤ −1000 mm; the control
6 rows / 5 attempts + 1 partial + 1 blowup), the **pooled outcome** (45/60) — the total failure
mass — at SEED 11/5/23, plus the interval/cycle and the motion budgets (reported, not gated; the
outcome is quantized per AGENTS §2 — quote the class census and the per-leg motion, not
cross-config rate deltas).

**Promotion rule (M → P).** An arm is promoted iff (a) its mechanism endpoint moves as above
**and** the hold walk falls into/below the ok band (≤ 20 mm) on ≥ 2 of the control's three
hold-walk attempts **or** the seed-11 no-grasp count falls ≥ 2 with the hold-walk attempts
converting; **and** (b) the probe-1 departures do not rise and the probe-1 dz does not worsen;
**and** (c) no new failure reason (incl. the finger–belt jam class) and no never-grasped growth.
If both arms qualify, promote the larger walk movement (the tie to the stronger mechanism read).
If none qualifies, the phase closes at M.

**Kills.** K1 the mechanism gate (above) — the bounded negative. K2 the class re-draw: the
never-grasped/no-grasp grows ≥ 2 at seed 11 or ≥ 2 pooled → negative, not adopted. K3 a
non-bit-identical double → the run is invalid. K4 the no-harm item fails. K5 a protocol
interference (a concurrent Tier-A job, a broken claim, a wedge) invalidates the block.

**No-harm (knobs unset).** `scripts/selfcheck.sh` PASS; the acceptance **9/10 + `fingerprint:
matches`**; the two-line dense re-record + `scripts/190_twoline_gate.sh` PASS; the knob-off
mass-base control replay (the `[fruit]` byte-identity vs `logs/p12a2/10_seed11_mass.log`). The
new knobs are env-only, default-off, dynamic-capture-scoped: the shipped single-arm default and
the two-line opt-in are byte-unchanged by construction (re-verified, not assumed).

**Budget.** The `src/` stub + the executed identity ~20 min; Stage M 1–2 traced runs
(~10 min each; M0 free) ≈ 20 min; Stage P 6 runs ≈ 60 min; the no-harm ~15 min. Tier A solo;
~1.5–2 h.

**Pins.** `tasks.py` `810658b802d22bbd63013726fc78af81`, `fruits.py`
`d28546d26137d4540421caa7fa34a139`, `meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`; the tooling
`logs/p14b/trace_p14b_analysis.py` + `logs/p16/descent_boundary_analysis.py` (the class rules
from `logs/p14b/master_table.md`); `configs/*` untouched.

---

## 5. The honest constraints

### 5.1 What the records already rule out (do not repeat)

* **The standoff / grip-plane axis is closed both ways**: S3 (+20 mm, clean via
  `FRUIT_DYNAMIC_PAD_LIFT`) negative at every seed (45/60 → 32/60, the falls up 6 → 16 rows);
  D2a (−8 mm) negative with its break-test confound named; the −10 mm belt jam. (a)'s *achieved*
  motion is a ≤ ~10 mm change in the same direction as D2a but without the confound — that is
  the one *clean* residual of the axis, and the screen must read it as such.
* **The reach/aim family** (R10-A/R11-A/R11-A.1): the reach-anywhere rule is excluded from the
  two-line by design; on the single arm the flip collapsed the shipped acceptance 9/10 → 4/10,
  and the floored variant still read 4/9 with the left **post-catch hold** failures. Any
  aim/schedule change inherits this collapse risk.
* **The W2 catch lead** (the clearance redesign): the best clearance state (38.9 mm / zero < 30)
  read 6/10 at 9.8 s/attempt — the clearance levers trade the rate ~1:1.
* **The scene proxies**: D2a/D2b/D3 all fail; S1 catch-null by derivation; S5
  infeasible/incompatible with the two-line; S2's cradle is the highest cost with the D3 supply
  risk; **S4 (the containment) is the only certain movement and it is grip-null** (the falls).
* **The close/carry actuators are saturated** (the P15's conserved mass): C1's stage-P trade
  (the never-grasped 0 → 5) reproduced on the two-line (7 → 12); the hold-window lead (M2) moved
  the walk and traded the outcome (45/60 → 38/60, the carried 2/0/2 → 4/6/2); the squeeze side is
  closed by mechanism (R6-B's drive-saturated pinch); the reaction/guard family (W8-B 5-1
  p = 0.1094; R6-B 3-1 p = 0.3125); the control-side ejection space (P11-C: 35/31/30 vs 39/60);
  the re-seat floor dead as the initiator (the trace's F1); the takeoff screens (W5-C); the pluck
  dwell (C3); the physics lane (the mass base is the winner; the compliance negative; the
  restitution neutral).
* **The P15's screen already answered the K1 question once**: the walk is movable (M2 collapsed
  it), so it is (at least in part) a close/hold quantity — and the P15's outcome traded. This
  lane's §1.3 adds the complementary statement: the walk is *not* the hand's settling, and the
  handoff state does not separate the classes.

### 5.2 The boundary's owner-gated history

* **The R10-A "do not re-tune the budget" note** (AGENTS §2): the descent's `|v|max` budget
  cannot tell a boundary strain from a real push; the ratio has no clean gap; the fix is the
  boundary, not the budget. (a) does not touch the budget — it changes *where the leg ends*, not
  how fast it moves.
* **The D3-proper gate**: the full form (a pick station + a self-centring feeder + a
  boundary-respecting descent) is the named scenario redesign, owner-gated since R8-A; the AGENTS
  §2 "settle what the criterion should mean with the owner" is still open (the options are in
  the WORKLOG entry "the descent is blocked by the conveyor"). This design does not pre-empt it.
* **The P12-B.2 derivation** (the catch is fruit-relative) is the analysis that makes the naive
  "raise the station" catch-null; it stands as the scene family's own closure.
* **The P1c/P3 supply findings** (the density is not a throughput lever; the place leg is closed
  by geometry) bound any scene change that touches the supply's timing.

### 5.3 The strongest reason the pick could fail (stated once, plainly)

**The premise is already partially refuted by the pick's own control.** The B1 failures enter the
hold *closer* to their commands than the oks (the freeze z_err −1.9 vs −3.3; the post-descent
residual 13.2–14.4 vs 11.1–61.7), and their handoffs are the *matched* class that the oks share.
So the most likely Stage-M read is: **the `end=` falls (the arrival works) while the hold walk
does not move** — K1 fires, the descent-boundary family closes with the measured statement that
the shortfall does not feed the capture, and the program's next candidates are the outcome-side
residual (the carried class) or the owner-gated D3-proper. The design is built so that this
failure is cheap and definitive: the `[arrive]` row shows the convergence directly, the K1 gate
stops before the outcome battery, and the control costs no run.

A second, narrower fail mode: **the arrival cannot be completed within the cap** — the drive
settling (τ = 0.2 s, `logs/164`) leaves a floor above the 6 mm tolerance even with 24 extra
ticks. That is also a *positive* result for the record: it measures the boundary's true edge on
this scenario (the pose is holdable; the servo settling is the wall) and closes the "the
post-descent solver finishes the approach" question for the mass base.

---

## 6. The reads and reproduction (read-only; the design's provenance)

```bash
# this lane's re-derivation (writes only under logs/p16/)
python3 -B logs/p16/descent_boundary_analysis.py > logs/p16/descent_boundary_tables.txt
# the descent shortfall (the end= rows) + the aim/timing lines
grep -h 'approach(cartesian)' logs/p12a2/1*_mass.log | grep -oE 'end=[0-9.]+ mm'
grep -h 'dynamic descent:' logs/p12a2/1*_mass.log | head -5
grep -h 'dynamic catch-up' logs/p12a2/1*_mass.log | grep -oE 'residual=[0-9.]+ mm'
# the boundary arc (the v1 record)
grep -h 'end=' logs/161_accept_endmetric.log logs/160_endgap028.log logs/163_droop_k05.log
grep -E 'jaw|finger' logs/166_collision_probe.log | head -5
# the reach map (the R10-A bands)
python3 -c "import json;[print(r['x'],r['dy'],round(r['grip_residual']*1000,1)) for r in json.load(open('logs/r10/reach_intercept_left.json'))]"
# the hold walk (the P14-B tooling, verbatim)
python3 -B logs/p14b/trace_p14b_analysis.py > /dev/null   # (writes under logs/p14b/ - do not re-run; read the committed tables)
sed -n '1,60p' logs/p14b/TRACE_RESULTS.md
# the P15's screen/outcome (the K1 and the conserved mass)
sed -n '1,60p' logs/p15/SCREEN_RESULTS.md; sed -n '1,28p' logs/p15/OUTCOME_RESULTS.md
# the scene closure (the catch is fruit-relative)
sed -n '77,163p' logs/p12b/SCENE_OPTIONS.md
```

**What this lane did NOT do**: no simulator run, no `src/`/`scripts/`/`configs/`/`datasets/`/
`Paper/` edit, no default changed, no branch operation, no commit; all writes under `logs/p16/`.
