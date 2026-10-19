# P17-B: the capture-lever design — the actuator inventory, the pick, and the pre-registration sketch (Tier C offline)

Status: **offline design lane, read-only on the tree** (branch `p-supply`, 2026-10-19). No
simulator run, no `src/`/`scripts/`/`configs/`/`datasets/`/`Paper/` write, no commit; all writes
under `logs/p17/`. Tree pins as read: `tasks.py` `54f70584b07fa249418f1efe30f30af0` (the P16-I
tree — the arrival knobs are present and default-off), `fruits.py`
`d28546d26137d4540421caa7fa34a139`, `meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`, `rl_env.py`
`be0248e0c3b88b28b0ec47ff28e1b68c`; HEAD `4a9f665` (the P17-C corrections commit).

**The mission.** Design the **bounded capture-side lever** from the P14-B/P15/P16 findings. The
three measured facts that frame it: (1) the no-grasp loss localizes to the **HOLD + probe-1** — a
loaded capture transient where the payload slides at ~belt speed during the hold (32–55 mm, the
force still 3.4–15 N) while the hand's own motion is small (`logs/p14b/TRACE_RESULTS.md`;
`logs/p15/SCREEN_RESULTS.md`; the world decomposition in `logs/p16/BOUNDARY_DESIGN.md` §1.3);
(2) the **failure mass is conserved** across the tested close/carry actuators (the P15's M2
traded the no-grasp for the carried: pooled 45 → 38; `logs/p15/OUTCOME_RESULTS.md`); (3) the
descent's shortfall does **not** feed the capture (the P16's K1; `logs/p16i/SCREEN_RESULTS.md`).
The untested root is therefore the capture transient itself: **the fruit sliding relative to the
jaws at belt speed during the arrest**.

**The inputs read** (all read-only): `logs/p14b/TRACE_RESULTS.md` + `master_table.md` +
`trace_p14b_tables.txt`; `logs/p15/CLOSE_HOLD_DESIGN.md` + `SCREEN_RESULTS.md` +
`OUTCOME_RESULTS.md` + `trace_p15_tables.txt`; `logs/p16/BOUNDARY_DESIGN.md` §1.3 + `logs/p16i/`
`SCREEN_RESULTS.md`; `logs/w8/R3_RESULTS.md` §4 (the belt-speed screen); `logs/w8/B_RESULTS.md`
(the `clean_slip` metric + the guard), `logs/r6/B_RESULTS.md` (the drive-saturated pinch + the
retuned guard), `logs/r8/A_RESULTS.md` (the D screen), `logs/r9/RESULTS.md` (the RWR lane);
`logs/r11/B_RESULTS.md` + `PREREGISTRATION_LOADPATH.md` (C1/C2/C3); `logs/p11c/C_RESULTS.md` (the
first conserved-mass instance); `logs/p3face` (the friction/face screens); the close/hold/probe/
freeze code in `tasks.py` (read-only); `AGENTS.md` §2. The sibling lane's KB refresh
(`logs/p17/C_EVIDENCE.md`, `docs/papers/UPDATE_2026_10.md` §3 "L1") is the same subject and its
NO-GO is addressed in §5.6.

---

## 0. The answer in one screen

* **The target** (the P14-B/P15/P16 numbers, §1): the **hold walk** — the payload's hand-frame
  drift across the 0.4 s hold from the freeze — ok **−0.6…12.8 mm (median 0.2, n=45)** vs the
  three hold-walk B1s **31.9 / 38.1 / 54.8 mm**, walking at **0.083–0.143 m/s ≈ belt speed** with
  the force still present; the **probe-1** first departures (4/8 no-grasp cross in probe block 1;
  the B1s' probe-1 lift dz −1.2…+0.9 mm — the fruit never rises); and the world decomposition:
  the B1s' **rel_dy −51.1…−1.0 mm (median −28.5)** while the hand's own y moves **−1.6…+3.4 mm**,
  the fruit's |vy| peak **0.109–0.251 m/s (median 0.205)** vs the oks' median **0.078**, and the
  fruit's |vx| (the squeeze-out) **0.185 vs 0.071 m/s** — a **3D escape** (belt shear + closing-axis
  extrusion + the z sag), not a pure y slide.
* **The actuator inventory** (the capture-side, §2): **(a)** the belt speed (env-only, the
  scenario constant 0.12; the R3 screen measured 0.12/0.15/0.18 — **only upward**); **(b)** the
  hold's tracking compensation (the lead `FRUIT_CLOSE_CONTACT_LEAD`/`FRUIT_DYNAMIC_TRACK_LEAD`;
  **measured** by the P15's M2: the walk collapse + the conserved-mass trade); **(c)** a
  slide-tolerant capture criterion (the freeze's force/stall + the probe's lift thresholds vs the
  measured slide; the P15's #3 straddle + a new hold-side form); **(d)** the other bounded
  candidates — the pad friction (env-only, measured negative on the ancestor class by the P3-faces
  screens), the hold length, the probe's shape, and the closed families (the servo/chase, the
  x-seek, the hand-vmax, the squeeze/depth, the re-seat floor, the arrival family, the verify
  dwell).
* **The ranking** (§3): **1. (c) the slide-tolerant capture criterion** (the only candidate whose
  mechanism acts on the *measured* transient's own signal — the slide with the force present —
  and whose recovery window is measured to exist: the re-seat windows re-grab partial payloads,
  while every failure's payload is already 22–55 mm out before the existing recovery fires);
  **2. (b) the hold's tracking compensation** (measured: the mechanism win + the outcome trade;
  its untested residuals are thin); **3. (a) the belt speed** (untested downward, env-only, but a
  *rate* change, not a stick/slip change — the expected census movement is low and the supply cost
  is real); **4. (d) the others** (closed or re-draw).
* **The pick** (§4): **(c), in the arrest-verified form** — the **hold/probe-1 slide gate + the
  bounded in-place re-seat** (a scripted-side, default-off, dynamic-capture-scoped change: when
  the payload's hand-frame drift rate exceeds the ok band during the hold, the arm's command
  re-centres on the payload's measured centre at a bounded step, keeping the frozen gap and
  orientation, at most N times per attempt; the mechanism rows record the trigger rate, the step
  and the post-response drift rate), **plus the same screen's alternative form**: the
  freeze-side **two-sided-load gate** (the P15's #3 straddle: the freeze commits only on a
  two-sided, load-sustained contact, with the shipped criterion as the bounded fallback). ONE
  promoted arm runs the outcome battery; the optional third arm is the belt-speed probe.
* **The endpoints** (§4): the mechanism — the **hold walk** + the **probe-1** (the trace's own
  rules, `logs/p14b/trace_p14b_analysis.py` verbatim); the outcome — the **TOTAL failure mass**
  (the no-grasp + the carried together; the P15's lesson) **+ the falls**; the mandatory
  co-report — the interval and the per-leg motion.
* **The strongest reason the pick could fail** (§5.5): **the response re-centres the contact but
  does not change the friction margin** — if the payload's slide is a kinetic slip set by the
  pad-fruit friction and the contact geometry (the P3-faces friction screens left the ancestor
  class unchanged; the R6-B's drive-saturated pinch says the commanded interference is inert),
  then the re-seat keeps the *geometry* while the payload keeps sliding (now with the arm chasing
  it), the hold walk does not fall, and **K1 closes at Stage M**. The second mode is the
  conserved mass itself: the walk falls but the converted captures are marginal and the carried
  class absorbs them (the M2 signature; the W8-B/R6-B guard's two N=5 near-misses are the prior).

---

## 1. The target: the measured capture transient (refreshed from the records)

Everything in this section is a record number (M) or a re-quoted re-derivation (P) from the
committed traces/tables; the class rules are the P10-E/P14-B ones (B1 = 3 probe blocks, B2 = 1).

### 1.1 The hold walk (the P14-B/P15 metric)

| class | n | hold walk mm (min/med/max) | probe-1 lift dz mm | total drift mm |
| --- | --- | --- | --- | --- |
| ok | 45 | −0.6 / **0.2** / 12.8 | −0.4 / 8.4 / 67.5 | 0.0–27.2 |
| carried | 7 | 2.6 / 4.3 / 5.8 | 8.8 / 15.6 / 17.8 | 3.4–1 407.3 |
| **B1** | **5** | 0.1 / **31.9** / 54.8 | **−1.2 / −0.5 / 0.9** | 1 458.1–95 403.7 |
| B2 | 3 | 0.0 / 0.7 / 1.8 | 5.2 / 7.1 / 7.8 | 294.8–344.8 |

* The three hold-walk B1s are s11 attempts 1/6/8 (left orange / left tomato / left orange; the
  P15 screen's re-derivation reads 38.1 / 31.9 / 54.8); the walk speeds are **0.083–0.143 m/s**
  (the design's 0.08–0.14 band ≈ the belt 0.12).
* The **release** (sustained `F < 0.5 N ∧ contacts == 0`) completes: hold 2 / probe-1 2 /
  re-seat window 2 (both already 22.4/25.8 mm out at the window's near edge) / takeoff→carry gap
  1 / carry 1 (no-grasp, n=8). **Every no-grasp release completes at or after the hold**; the
  existing recovery (the probe's failed lift → the W1 re-seat window, 101 ticks) fires after the
  payload is already out on 5/8.
* The **F1 test** (the re-seat floor): **no re-seat window ever released a held payload**; the
  windows re-grab (a13's w1 re-seated a 4.3 → 3.0 mm payload at F = 19.97 N). So the recovery
  *works when it fires early enough* — it never fires early enough today.

### 1.2 The world decomposition (the P16 §1.3 re-derivation; the K1 refutation)

| attempt | walk mm | rel_dy | rel_dx | rel_dz | hand dy | hand dx | hand dz | fruit \|vy\| peak | fruit \|vx\| peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a01 orange | 38.9 | −34.0 | −9.2 | +10.1 | −1.6 | +29.8 | −8.5 | 0.25 m/s | (B1 med 0.185) |
| a07 tomato | 32.8 | −28.5 | −2.7 | +9.9 | −13.2 | +22.5 | −9.4 | 0.21 | |
| a09 orange | 55.6 | −51.1 | −6.3 | +11.4 | +3.4 | +34.0 | −10.5 | 0.20 | |

* The **hand's own y motion is not the walk** (−1.6…+3.4 mm vs the fruit's 34–51 mm); the x is
  the bounded x-seek following the fruit's own squeeze-out; the z sag grows *with* the slide
  (z_err −1.9 mm at the freeze → −11.0 at the hold's end; the oks −3.3 → −4.3) — it is the pads
  slipping down the escaping payload, not a pre-existing settling.
* **The B1 payload accelerates past the belt speed while the pads hold it** (|vy| peak median
  0.205 vs the oks' 0.078): the closing-axis extrusion is a co-driver of the escape (|vx| 0.185
  vs 0.071). The mechanism is the W8-B/R6-B **loaded slide**, in 3D.
* The **arm-tracking asymmetry** (from the P15 decomposition table): on the right-arm attempts
  the hand's dy ≈ the fruit's dy (it moves with the fruit at ~belt speed; e.g. hand −45.6 vs
  fruit −45.5; 8/10 right attempts within ~2 mm); on the left the hand's dy is small
  (−15.7…+4.2 across the 10 attempts) while the fruit's dy runs to −46 — on the larger-motion
  attempts the hand lags the fruit by 20–35 mm (a01: hand −0.8 vs fruit −34.0; a08: +4.2 vs
  −46.1). The left hand does **not** follow the fruit's y motion during the hold, so on the left
  the full belt travel must be absorbed by the pad-fruit friction. The hold-walk class is
  left-arm only at this n (3/3) — not a measured arm effect, but consistent with this asymmetry.
* The **P16's K1**: the descent's `end=` shortfall (median 9.4 mm) does not feed the capture —
  the completed descent (H1: settled 5.6–7.0, median 5.9) left the walk unmoved (B1 median 36.1
  vs 35.0) and the no-grasp grew 7 → 9 on its branch. The shortfall family is closed.

### 1.3 What the P15 already measured (the family that is no longer "untested")

* **The mass base (the control, the scenario of record):** pooled **45/60** ok (s11 11 / s5 17 /
  s23 17), the no-grasp **7/0/1** [**CORRECTED 2026-10-19**: this document first read 7/3/3], the
  carried **2/3/2** [**CORRECTED**: first read 2/0/2] — verified from the on-disk logs
  `logs/p12a2/{10_seed11,11_seed5,12_seed23}_mass.log` (the unique `[run] attempt` rows; see the
  CORRECTION in `logs/p15/OUTCOME_RESULTS.md`; the same error is corrected there), the falls
  **6 regular rows** (s11 3 + s23 3) **+ 1 partial + 1 blowup** (the F6/P16 recount; the P15's own
  table reads the falls as 10 → 6 rows under its three-seed reporting convention); the pooled
  interval 14.29 s. **Note (the corrected census):** the mass base's failures are **8 no-grasp +
  7 carried** — the carried class is nearly half the failure mass, and the P15's M2 battery read
  nc 8 → 10, carried 7 → 12 (a pooled loss on every class, not a conserved trade).
* **M2 = `FRUIT_CLOSE_CONTACT_LEAD=0.10`** (the hold-window lead; the contact window = the close's
  load phase + the hold): the walk **collapsed** (ok band 0.0–0.2; the control's three hold-walk
  attempts' fruit read 0.0–2.5 mm; the no-grasp walk 0.0–31.6), the actuation read is the
  R11-B C2 direction (the fruit's |v_y| at the close-end/hold braked ~97 → ~39 mm/s; the M2's
  left hand then *followed* the fruit, hand dy ≈ fruit dy, and the fruit's world dy fell to
  −9…−14 mm), the no-grasp fell **7 → 4** and the falls 3 → 1 at seed 11 — **but the outcome
  battery traded**: pooled **45 → 38**, the carried **2 → 4** (s11) and **0 → 6** (s5), the
  interval +8 %. **The mechanism is movable; the mass is conserved.**
* **M1 = `FRUIT_CLOSE_LOAD_RATE=0.04`** (C1): the freeze moved later (median 20.5 → 47.0; 3/20
  never froze; two span-negative jam freezes at 190–232 N), the no-grasp **grew 7 → 12** and the
  walk *rose* (9/12 walkers 27.8–85.8 mm) — the stage-P trade reproduced on the two-line.
* The conserved-mass instances (the P15's count): the P11-C from-open (pooled 39 → 35; the seed-11
  branch +3 but the controls moved against), the P11-C.2 (35/31/30), the P15's M2 (45 → 38).
  **Three instances, the same shape: a mechanism win, a class re-draw, a pooled loss.**

---

## 2. The actuator inventory (the capture-side, untested)

Each entry: the knob/site + the shipped value → the mechanism (why the failure mass would
*reduce* rather than trade) → the evidence FOR → the evidence AGAINST → the expected movement →
the cost → the falsifier. "Reachable" = env-only (the knob exists and is default-off) unless
marked **unbuilt** (a control change with no form in the tree).

### 2.1 (a) The belt speed — the slide's speed itself (`FRUIT_BELT_SPEED`, the scenario constant 0.12 m/s)

* **Site.** `assets.py:212-215` (`belt_speed = -abs(FRUIT_BELT_SPEED, default 0.12)`); the belt is
  one kinematic body with one surface velocity — **there is no station-local slowdown**; the
  bounded env-only form is the global scenario constant.
* **Mechanism (reduction?).** The hold walk is the loaded slide at ~belt speed (§1.1); a slower
  belt slows the walk's *rate* linearly (the walk per hold = v·0.4 s; at 0.06 m/s the 31.9/38.1/
  54.8 mm walkers become ~16/19/27 mm) and lowers the fruit's momentum at the arrest. **But**:
  the arrest is a stick/slip condition (the pad friction vs the belt drag — a Coulomb balance
  that is speed-independent), the escape is geometric (the fruit leaves the finger span once the
  relative walk exceeds the pad extent; the capture window is ~190 ticks = 1.6 s, long enough for
  the escape to complete at any of the plausible speeds), and the B1 fruit's |vy| peak *exceeds*
  the belt speed (the squeeze-out is a co-driver, untouched by the belt). So the expected
  movement is the **walk's magnitude**, not the class census — a mechanism probe, not a
  reduction lever.
* **Evidence FOR.** The walk speed ≈ belt speed (0.083–0.143 m/s, §1.1); the walk's dominant
  component is the fruit's belt slide (the world decomposition, §1.2); the belt-speed screen
  shows the *catch* is speed-robust (below), so a speed change is cleanly attributable.
* **Evidence AGAINST (the R3 screen, quoted).** The W6-B battery (two-line patch, ATTEMPTS=20,
  SEED=5, Tier A solo; `logs/w8/R3_RESULTS.md` §4), one branch per point:
  | belt [m/s] | success (L/R) | window placed/min | pooled interval (mean/p50/p90) | attempt span | idle L/R | starved slots L/R | catch leg |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | 0.12 | 12/20 (4/8) | 3.63 | 16.53 / 17.30 / 19.90 s | 15.08 s | 18 %/24 % | 19/22 | `|v|max` 0.107–0.116, `end` 8.2–11.3 mm |
  | 0.15 | 14/20 (7/7) | **4.69** | **12.80 / 16.00 / 20.40** | 14.33 s | 18 %/23 % | 17/25 | 0.108–0.116, 8.2–12.2 mm |
  | 0.18 | 14/20 (4/10) | **3.82** | 15.71 / 17.30 / 21.90 | 13.73 s | **39 %/32 %** | **115/38** | 0.106–0.111, 8.2–10.4 mm |
  The screen's own mechanism: the arrival structure speeds up monotonically (the descent block
  3.19 → 2.40 → 1.88 s), the catch is **not the limit at any of the three speeds**, and at 0.18
  the supply/schedule limit bites (the starved-slot explosion). The two-line is
  **arrival/supply-limited, not servo-limited**, up to ≥ 0.15 m/s. The screen tested **only
  upward** — a slower belt is untested — but its mechanism (the arrival structure) and the
  fixed 1.5 s floor (`v·1.5` = 0.18 → 0.27 m; slower *widens* the usable upstream band) say the
  slower direction buys schedule room and pays arrival rate.
* **Expected movement.** The walk scales with v (the mechanism read); the no-grasp/carried
  census: low expected movement (the stick/slip + the geometric escape); the throughput: down
  roughly proportionally (the line is arrival-bound; at 0.15 the window rate gains +29 % — the
  same mechanism in reverse).
* **Cost.** Env-only, ~10 min/run, **but a scenario change**: its own reference/fingerprint
  (`configs/*` are 0.12-calibrated), and any rate claim is cross-scenario (AGENTS §2).
* **Falsifier.** The walk scales with v but the class census does not move — the slide's *rate*
  is not the failure's actuator (the escape is stick/slip + geometric).

### 2.2 (b) The hold's tracking compensation — the hand following the fruit during the arrest (`FRUIT_CLOSE_CONTACT_LEAD` (C2), `FRUIT_DYNAMIC_TRACK_LEAD` 0.18, `FRUIT_DYNAMIC_TRACK` 0, the x-seek)

* **Site.** The hold loop (`tasks.py` 8229–8277): the arm is commanded to `fruit + v·lead_hold`
  every tick (C2 replaces the lead in the contact window; unset = `FRUIT_DYNAMIC_TRACK_LEAD`
  0.18); the close's load phase uses the same lead; the x-seek (`FRUIT_DYNAMIC_X_TRACK_VMAX`
  0.12 / `_VX_MAX` 0.05 / `_LATCH` 1) is the bounded cross-belt follow. The OpenArm hand's
  fingers are the contact bodies (the shipped `FRUIT_GRIPPER_KIND=openarm`; the drive-limited
  pinch — R6-B), so the *arm's* achieved motion **is** the fingers' motion: this knob is the
  hand-following-the-slide lever.
* **What the P15's M2 did.** The lead 0.10 → the left hand followed (the world decomposition
  above), the walk collapsed, the no-grasp 7 → 4, the falls 3 → 1 — **and the total traded**
  (pooled 45 → 38; the carried 2 → 4 / 0 → 6; the interval +8 %).
* **What M2 did NOT do.** (i) It did not separate the hold's lead from the close's load-phase
  lead (one knob for the whole contact window; the load-phase part was inert on the freeze
  timing — 21.0 vs 20.5 — so the hold part carried the effect); (ii) it did not test the
  *reactive* form — the shipped lead is a *static* feed-forward applied to **every** attempt, so
  the whole branch moved with it (the seed-5 ok count 17 → 10, the fruit set changed); a
  *triggered* response that acts only on the sliding attempts is untested; (iii) it did not test
  the lead's other end (R11-B: lead 0.26 punts the fruit downstream at 129/291 mm/s; the optimum
  between 0.10 and 0.26 is unmapped); (iv) the *cause* of the left hand's non-following under
  the shipped lead is unmeasured (candidates: the commanded offset `v·0.18` = 21.6 mm pushing
  the IK target past the left's reachable band, saturating the y axis; or the drive/IK tracking
  itself) — the M2's evidence (a smaller offset made the hand follow) is consistent with the
  first, not proof of it.
* **Mechanism (reduction?).** The measured mechanism: when the hand follows the fruit, the
  relative walk collapses (the friction only has to hold the residual, not the full belt
  travel). The measured trade: the converted captures are **marginal** (they escape the carry).
  So the family's reduction case is weak — it *is* the family that produced the conserved-mass
  lesson. A *reactive* variant (the pick's form, §2.3) is the only untested slice.
* **Cost.** Env-only; the expected movement is a re-draw (measured).
* **Falsifier.** The walk collapses but the total mass does not fall — already measured by the
  M2's own outcome battery.

### 2.3 (c) A slide-tolerant capture criterion — the freeze/probe thresholds vs the measured slide

* **The shipped criterion (the site).** The freeze (`tasks.py` 7971–8020): the first **sustained
  contact + span stall** (`FRUIT_DYNAMIC_CONTACT_FORCE` 0.5 N, `_TICKS` 3, `_STALL` 0.15 mm/tick)
  pins the depth (`freeze_cmd`) and the grip; it is **never re-evaluated**. The probe's grip
  test (`tasks.py` 8655–8748): a 6 mm z-ramp over 60 ticks with the aim tracking the fruit
  (`FRUIT_DYNAMIC_PROBE`/`_TICKS`/`_TEST_STEP` = 0.006/60/0.01 on the two-line); a failed lift
  triggers the W1 re-seat (the 101-tick windows). The criterion is **static**: it commits the
  capture on the first sustained contact and never checks whether the payload has actually been
  **arrested** — the measured slide (32–55 mm with the force present) is invisible to it.
* **The mechanism (reduction?).** The failures are *detectable while still in the span*: the
  walk accumulates over tens of ticks (32–55 mm at 0.08–0.14 m/s ≈ 0.25–0.5 s) and the payload
  is 4–20 mm out through the first half of the hold, whereas the existing recovery fires at the
  probe's failed lift, by which time the payload is 22–55 mm out or gone. A slide-aware response
  — re-seat the contact toward the payload while it is still between the pads (the W8-B guard's
  bounded re-seat form — built and measured, directional only; the F1 re-grabs measured to *work*
  when the payload is still in the span) — can convert the marginal captures into *re-centred*
  ones, which is the
  one conversion the M2's *static* centring did not test: the response fires only on the sliding
  attempts, so the oks are untouched (the M2's branch moved because its lead changed *every*
  attempt). If the re-centred grip is a *good* grip (two-sided, centred), the total mass can fall;
  if it is still marginal, the mass re-draws (the pre-registered risk).
* **The alternative form (the freeze-side straddle, the P15's #3).** Require a **two-sided,
  load-sustained contact** before the freeze commits (both tactile sensors loaded; the trace's
  `ft` split exists — the P10-E "tip/edge contact" root: the span at detection +3.7…+35.1 mm
  wider than the fruit). On the mass base the hold-walk attempts' freeze depths are already at
  the live extent (+1.6/+1.3/−2.5 mm), so the *depth* is not the defect; the *load split* is
  untested. The bounded fallback: if the two-sided condition never obtains within the close's
  horizon, the shipped criterion applies (no new failure mode).
* **Evidence FOR.** The measured transient (§1); the **F1 re-grabs** (the recovery works when
  early); the failures' timing (§1.1: the walk accumulates over tens of ticks); the **W8-B
  guard** precedent (the in-hand displacement trigger + the bounded re-seat: the paired carried
  class 5–1 and carried-not-placed 50 → 42, though p = 0.1094 and +5.4 % cycle — not adopted);
  the **R6-B retune** (3 B-only / 1 A-only, carried 46 → 44, p = 0.3125 — not adopted); the M2's
  own mechanism (the arrest is achievable in this window).
* **Evidence AGAINST.** The guard family's **two N=5 near-misses** (the re-seat's outcome
  movement is ~0; the 100–400 mm band converts 0/37); the R6-B finding that the earliest
  measurable escape signal (one-sided contact) carries **no warning over the 2 mm crossing**
  (median 29 vs 25 ticks to contact loss) — the carry-phase escape is late-signalled; the
  P11-C from-open's class re-draw (a re-seat that does not press in cannot restore a lost grip);
  the deeper-freeze ejection prior (the corrected P11-B plow: tomato ≥ 10 mm 2/3, apple ≥ 2 mm
  3/3) for the freeze-side depth coupling; the P3-faces friction screens (below) saying the
  contact *geometry/load* is not the friction margin; the P15's §2.2 "unbuilt" flag.
* **Expected movement.** The converted attempts' hold walk falls (the re-centring) **if** the
  arrest follows; the probe-1 dz improves; the no-grasp falls; **or** the walk falls and the
  carried absorbs it (the conserved mass). The trigger's specificity is measurable in advance
  (the ok walk rate ≈ 0.000–0.01 m/s vs the B1s' 0.08–0.14 — a 3–10× gap).
* **Cost.** **Unbuilt**: a bounded, default-off, dynamic-capture-scoped `src/` change (the
  freeze-side gate in the freeze block; the hold/probe slide gate + the re-seat in the hold/probe
  loops) + its own pre-registration + a stub + ~2 runs at Stage M. The alternative form is the
  same cost; the thresholds-only approximation (e.g. `FRUIT_DYNAMIC_CONTACT_TICKS=8`,
  `FRUIT_DYNAMIC_CONTACT_FORCE=1.5`) is env-only and cheap but its prior is adverse (the C1
  lesson: a later/deeper freeze lets the fruit ride and *raises* the walk).
* **Falsifier.** The walk does not fall (the re-seat keeps the geometry but not the friction —
  K1); or the walk falls and the total mass does not (the M2 signature — K2); or the trigger
  fires on the oks' universal small walk and the phase degrades.

### 2.4 (d) The other bounded candidates (and the closed families)

* **The pad-fruit friction (`FRUIT_FINGER_FRICTION_COMBINE` empty → the schema default; the
  combine semantics are flagged unverified by the P11 audit G5; `FRUIT_FINGER_MU` 2.0;
  `FRUIT_GRIPPER_MU` 2.0 for the kinematic hand).** The loaded slide is a friction-limit
  phenomenon, so this is the first-principles candidate — **but it is measured negative on the
  ancestor class**: the P3-faces lane (the old dynamic line, 0.12 m/s, 10 attempts) raised the
  effective friction and the A2/A8 carry-slide class did **not** improve (`combine=max` 6/10,
  A2/A4/A6/A8; `k30+combine=max` 6/10; `k30+mu=8` 6/10 — "friction breaks A4"; the compliant
  fix re-ejected). The prior is negative; a cheap re-test is *available* (env-only) but is not
  the pick.
* **The hold length (`FRUIT_DYNAMIC_HOLD` 48).** The walk's rate is constant at ~belt speed, so
  more time = more walk (the P15's "not a lever"). The shorter direction reduces the accumulated
  walk but the escape completes later (the probe/window — the release histogram migrates); and
  the ok arrests happen *within* the hold, so a shorter hold risks the marginal oks. A re-draw,
  not a reduction.
* **The probe's shape (`FRUIT_DYNAMIC_PROBE`/`_TICKS`/`_TEST_STEP`).** The two-line already runs
  the W1 gentler profile (0.006/60/0.01); the specificity is weak (5 ok first probes also read
  ≤ 2.5 mm and recovered via the re-seat; 3/5 B1s' losses precede the probe); the W5-C probe
  screens (the takeoff squeeze, TRACK 0.2, LOCK_X) are closed negatives. It acts on the
  *completion* of an already-marginal grip.
* **The closed families (do not re-run as-is).** The force servo/chase (`FRUIT_DYNAMIC_FORCE_*`):
  the trace's F1 confirmed the chase is a *symptom* (no window ever released a held payload);
  P7-2a (chase 5 → 0, carried 5 → 5), the W5-C cfg1, the P11-C.2 (stopping the chase *hurts*:
  39 → 31/60). The x-seek (`FRUIT_DYNAMIC_TRACK_WALK`, LOCK_X): cross-belt; following the
  squeeze-out was measured worse; W5-C cfg4 negative. The hand-vmax rate limiter
  (`FRUIT_HAND_VMAX`): measured negative (the pads can't catch a leaving payload; `logs/150`).
  The squeeze/depth (`FRUIT_DYNAMIC_CLOSE_DEEP`/`FRUIT_GRIPPER_SQUEEZE`/`_MIN_INTERFERENCE`):
  closed by mechanism — R6-B's drive-saturated pinch (the command sits 11.9 mm inside the span,
  the force 4.1–4.5 N; the relief to 0.5 mm leaves the force 4.15–4.47 N); R8-A's D2a/D2b/D3 all
  fail. The re-seat floor (`FRUIT_DYNAMIC_REGRASP_FLOOR`): dead as the initiator (F1). The
  arrival family (`FRUIT_DYNAMIC_REGRASP_FROM_OPEN` ± the chase stop): pooled 35/31/30 vs the
  anchor 39/60; kill 2 fired on all (P11-C). The verify dwell (`FRUIT_DYNAMIC_VERIFY_*`): a
  *detection* lever (fail early), not a capture lever — it would convert the no-grasp into an
  early fail (the same mass). The grip-face geometry (the arrest window along the belt): on the
  *kinematic* hand it is `PAD_WIDTH` = 40 mm — a module constant, **not** env; on the mass base's
  shipped OpenArm hand (`FRUIT_GRIPPER_KIND=openarm`, the contact bodies) it is the asset's
  finger-face extent, also not env. A wider face extends the arrest window but is an asset
  change with the P3-faces entry-envelope risk (the additive faces batted the catch-up/close).

---

## 3. The ranking and the pick

The ranking criterion (the P15/P16 convention): **the expected movement per the trace's
localization × the cost × the risk**, with the evidence quality as the tiebreak.

| # | candidate | the trace endpoint it can move | the expected movement | the cost | the risk | the decisive evidence |
| --- | --- | --- | --- | --- | --- | --- |
| **1** | **(c) the slide-tolerant capture criterion** (the hold/probe-1 slide gate + the bounded in-place re-seat; the freeze-side two-sided gate as the alternative form) | the hold walk (the sliding attempts), the probe-1 dz, the release bracket | moderate; the mechanism is the only one that acts on the *measured* transient's own signal and its recovery window is measured to exist (4–20 mm in-span vs the existing 22–55 mm) | **unbuilt** (`src/`, default-off, scoped) + the pre-registration + a stub | the guard family's two near-misses; the conserved mass (a re-draw) | the F1 re-grabs (4.3 → 3.0 mm at 19.97 N); the walk's 3D structure (|vy| 0.205 / |vx| 0.185 on the B1s); the M2's mechanism (the arrest is achievable) |
| **2** | **(b) the hold's tracking compensation** (the lead) | the hold walk (measured: the collapse) | measured: a mechanism win + a conserved-mass trade | env-only | measured (the M2's own battery) | the M2: 0.0–2.5 mm on the tracked fruit, the no-grasp 7 → 4, the pooled 45 → 38, the carried 0 → 6 (s5) |
| **3** | **(a) the belt speed** (slower) | the walk's *magnitude* (the y shear) | the walk scales ~linearly; the census likely flat (stick/slip + the geometric escape) — a mechanism probe | env-only, but a scenario change (its own reference) | the supply-rate coupling (the line is arrival-bound); the R3 negatives | the walk speed ≈ belt (0.083–0.143); the R3's arrival structure; the B1s' |vy| peak 0.205 > the belt 0.12 |
| **4** | **(d) the others** | — | closed or a re-draw | — | — | the friction (P3-faces), the servo (F1), the x-seek (W5-C), the depth (R6-B), the arrival (P11-C) |

**The pick: (c) — the arrest-verified (slide-tolerant) capture criterion**, in two bounded
forms screened in one battery:

1. **The primary form (the hold-side slide gate + the bounded in-place re-seat).** A default-off,
   dynamic-capture-scoped change: during the hold and the first probe block, when the payload's
   hand-frame drift **rate** exceeds the ok band (`FRUIT_CAPTURE_SLIDE_RATE`, calibrated between
   the ok's ≈ 0.01 and the B1s' 0.08–0.14 m/s) for `FRUIT_CAPTURE_SLIDE_TICKS` consecutive
   samples, the arm's command **drops the feed-forward lead and re-centres on the payload's
   measured centre at a bounded step** (`FRUIT_CAPTURE_RESEAT_STEP`/`_MAX`, the W8-B guard's
   bounded-re-seat form), keeping the frozen gap and orientation; at most `FRUIT_CAPTURE_RESEATS`
   (1–2) per attempt; if the payload is already beyond the recovery window (the drift >
   `_MAX`), the attempt proceeds as shipped. The mechanism rows record the trigger rate, the
   step, and the **post-response drift rate** (the arrest check).
2. **The alternative form (the freeze-side two-sided gate).** The freeze commits only on a
   **two-sided, load-sustained contact** (both tactile sensors ≥ `FRUIT_CAPTURE_SIDED_FORCE` for
   `_SIDED_TICKS`), with the shipped criterion as the bounded fallback if the condition never
   obtains within the close's horizon. This is the P15's #3 / the P17-C KB's "the freeze
   criterion" arm — the *pre-hold* construction; its risk (the depth coupling) is why it is the
   second arm.

The two forms are the two mechanistically distinct hypotheses for the same endpoint — the
**recovery** of a sliding capture (the hold-side) vs the **commitment** of the capture (the
freeze-side) — which is exactly the choice the trace cannot make. The optional third arm
(budget permitting) is the **(a) belt-speed probe at 0.08 m/s** (the distinct *rate* hypothesis;
its control read is the mechanism + the within-run class structure only, per the R3 pattern).

---

## 4. The pre-registration sketch (to be frozen before any run)

**One paragraph.** On the mass base — `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1
FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_PHYSICS_REAL_MASS=1
ATTEMPTS=20 HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_CARRY_MONITOR_DIAG=1 FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR=logs/p17/traces_<arm>_s<SEED>`,
`scripts/run.sh scripts/20_pick_place.py`, Tier A solo through `scripts/154_claim_run.sh` — run the
**Stage-M mechanism screen at SEED 11**: **M0 the control** (already on disk, `logs/p14b/traces_s11`
+ `logs/p12a2/10_seed11_mass.log`; no run), **M1 the primary form** (the hold-side slide gate + the
bounded in-place re-seat), **M2 the alternative form** (the freeze-side two-sided gate), and — if
the budget allows — **M3 the belt-speed probe** (`FRUIT_BELT_SPEED=0.08`); promote **at most ONE**
arm to **Stage P** iff (a) its **hold walk** falls — per the P14-B tooling
(`logs/p14b/trace_p14b_analysis.py` verbatim: the drift change across the hold from the last close
row; the control's own bands: ok ≤ 12.8 mm, the three hold-walk B1s 31.9/38.1/54.8 mm) — so that
the no-grasp attempts' walks land in/below the ok ceiling **or** the seed-11 no-grasp count falls
≥ 2, **and** its **post-response arrest** read confirms the mechanism (on ≥ 1 converted attempt
the post-response drift rate falls below the ok band; a response that does not arrest is a
re-draw in advance), **and** (b) its **probe-1 first departures** do not rise (the 2 mm rule,
phase-bracketed) and the probe-1 dz does not worsen, **and** (c) no new failure reason, no
growth of the never-grasped/no-grasp class, and the re-seat budget is respected on every attempt;
the promoted arm then runs the **outcome battery at SEED 11/5/23** (the same env, one run per
seed, each with a bit-identical double): the **TOTAL failure mass** — the no-grasp (the P10-E
B1/B2 rules) **+ the carried (grasped-not-placed) together**, per seed and pooled (the P15's
lesson: the no-grasp alone can trade into the carried) — **plus the falls** (the `lowest payload
point` ≤ −1000 mm; the partials −100…−1000 mm reported separately; the blowups excluded, the A2
convention), the pooled outcome, the interval (reported, not the endpoint), and the mechanism
read (the hold walk, the probe-1 departures/dz, the response events, the release brackets); the
**kills** are **K1** (the mechanism gate: no arm's walk moves in the predicted direction, or the
post-response drift does not arrest — close the phase at M, publish the mechanism negative, do
not spend P), **K2** (the class re-draw: the total failure mass does not fall, or the carried
grows ≥ 2, or the no-grasp grows ≥ 2 — negative, not adopted), **K3** (any run's double is not
bit-identical — the scripted line is deterministic; the measurement is invalid), **K4** (the
no-harm fails), **K5** (a concurrent Tier-A job or a wedge corrupts a run); the **no-harm** half
runs with the knobs unset: `scripts/accept.sh` 9/10 + `fingerprint: matches
configs/motion_reference.json`, the two-line dense re-record + `scripts/190_twoline_gate.sh` PASS,
`scripts/selfcheck.sh` PASS, and the knob-off seed-11 control replaying
`logs/p12a2/10_seed11_mass.log` byte-identically (the `[fruit]` lines) — the new knobs are
env-only/default-off by construction; the `src/` diff must be byte-inert at the defaults (the
P16-I stub pattern: an offline identity check before any run).

### The structured form

**Scenario.** The mass base verbatim (`logs/p12a2/run_battery.sh`): `FRUIT_BIARM=1
FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_PHYSICS_REAL_MASS=1 ATTEMPTS=20`, plus
`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1
FRUIT_DYNAMIC_TRACE=1`. Seeds: **11 primary** (7 no-grasp: 4 B1 + 3 B2 — the only seed with B1
mass), **5 / 23 controls** (0 and 1 no-grasp). The trace is run-neutral on this scenario
(measured: the three P14-B trace runs replay the mass base byte-identically, 950/1047/1084
`[fruit]` lines), so the mechanism and the outcome come off the same runs.

**Arms.** Stage M (SEED 11, traced): M0 = the on-disk control; M1 = the primary form
(`FRUIT_CAPTURE_SLIDE_RATE`/`_TICKS`/`_RESEAT_*`, default-off); M2 = the alternative form
(`FRUIT_CAPTURE_SIDED_*`, default-off); M3 (optional, budget) = `FRUIT_BELT_SPEED=0.08` (its
read = the mechanism + the within-run class structure; a scenario arm). Stage P (the promoted arm
only): SEED 11/5/23 + the doubles.

**Mechanism endpoints** (the trace's own rules, re-derived by `trace_p14b_analysis.py`):
(i) the **hold walk** per attempt (mm) — the class distributions vs the control's own (the ok
≤ 12.8, the three hold-walk B1s 31.9/38.1/54.8); (ii) the **probe-1 first departures** (the count
per class + the phase bracket) and the **probe-1 lift dz**; (iii) the **response/actuation
reads**: M1 the trigger's drift rate, the re-seat's step and the **post-response drift rate**
(the arrest check), the re-seat count per attempt; M2 the freeze's load split (`ft`), the freeze
tick/depth/span, the two-sided condition's attainment; M3 the walk's scaling vs the control's
bands; (iv) the **release bracket** histogram per attempt as the descriptive read.

**Outcome endpoints** (Stage P): the **TOTAL failure mass** = the no-grasp + the carried
(grasped-not-placed) — per seed and pooled — **plus the falls** (the F6 convention: the `lowest
payload point` rows −1…−20 m, blowups excluded; rows and attempts reported; one payload can emit
two rows); the pooled outcome; the interval (reported); the mechanism read on the Stage-P runs.
The **rate is not the endpoint** (the outcome is quantized per AGENTS §2 — quote the class census
and the per-leg motion, not cross-configuration deltas).

**Promotion rule (M → P).** An arm is promoted iff (a) its no-grasp hold walk falls into/below
the ok band (≤ 20 mm, inside the 12.8 → 31.9 gap) on ≥ 2 of the control's three hold-walk
attempts (tracked by fruit identity; the branch may move), **or** the seed-11 no-grasp count
falls ≥ 2 with the hold-walk attempts converting; **and** the post-response arrest read confirms
the mechanism (≥ 1 converted attempt's post-response drift rate ≤ the ok band); **and** (b) the
probe-1 departure count does not rise and the probe-1 dz does not worsen; **and** (c) no new
failure reason, no never-grasped growth, the re-seat budget respected. If two arms qualify,
promote the larger hold-walk movement (the tie to the stronger actuation read). If none
qualifies, the phase closes at M.

**Kills.** K1 the mechanism gate (above) — the bounded negative. K2 the class re-draw: the
**total** failure mass does not fall (the no-grasp → the carried re-draw), or the carried grows
≥ 2, or the no-grasp grows ≥ 2 → negative, not adopted. K3 a non-bit-identical double → the run
is invalid. K4 the no-harm item fails. K5 a protocol interference (a concurrent Tier-A job, a
broken claim, a wedge) invalidates the block.

**No-harm (knobs unset).** `scripts/selfcheck.sh` PASS; the acceptance **9/10 + `fingerprint:
matches`** with its `[fruit]` stream compared to the pre-phase control; the two-line dense
re-record + `scripts/190_twoline_gate.sh` PASS; the knob-off mass-base control replay (the
`[fruit]` byte-identity vs `logs/p12a2/10_seed11_mass.log`); the offline stub: the `src/` diff is
byte-inert at the defaults (the executed-identity check pattern, `logs/p16i/IMPLEMENTATION.md`).

**Budget.** Stage M: M1 + M2 (2 traced runs, ~10 min each; M0 free; M3 optional +1 run) ≈ 20–30
min; Stage P: the promoted arm at SEED 11/5/23, each with its bit-identical double (6 runs ≈
60 min; the doubles are required by K3); the no-harm ~15 min. Tier A solo throughout; ~1.5–2 h
(excluding the `src/` implementation + the stub).

**Pins.** `tasks.py` `54f70584b07fa249418f1efe30f30af0`, `fruits.py`
`d28546d26137d4540421caa7fa34a139`, `meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`; the tooling
`logs/p14b/trace_p14b_analysis.py` + `logs/p10e/census.py`/`classify.py` (the class rules);
`configs/*` untouched.

---

## 5. The honest constraints

### 5.1 The R3 screen's negatives (they bound any belt-speed claim)

The R3 §4 screen is **one branch per point** and its own verdict is that the two-line is
**arrival/supply-limited, not servo-limited, up to ≥ 0.15 m/s**: the catch legs are in-band and
stable at 0.12/0.15/0.18 (`|v|max` 0.106–0.116 m/s, `end` 8.2–12.2 mm, zero catch-miss notes,
`gate_open=0.0 s`, zero `indexed:`), the arrival structure speeds up monotonically, and at 0.18
the **starvation** explodes (left 115 vs 19 slots). So: the belt speed changes **when the fruit
arrive**, not whether they are caught — and a slower belt therefore buys the walk's rate at the
price of the arrival rate. The fixed 1.5 s selection floor (`v·1.5`) *widens* the usable upstream
band as the belt slows (the R3's own 0.45 → 0.27 m shrink as the belt speeds 0.12 → 0.18, in
reverse), which is the one positive schedule effect; the arrival-rate loss is the cost. No rate
claim may be read across the speeds (the AGENTS §2 rule), and the scenario's calibration (the
acceptance at 0.12, the R10 reach bands) is 0.12-specific.

### 5.2 The supply-rate coupling (the slower-belt cost, priced)

The line's idle at 0.12 is 18 %/24 % and the window rate is 3.63 placed/min; the R3's 0.15 point
converts the speed into +29 % (4.69) — the same mechanism in reverse says a slower belt eats the
idle and then the throughput. A 0.08 m/s probe would roughly halve the arrival rate; the two-line
worker parks and waits (the single arm's selector gives up — the P1c starvation lesson: 10 "no
eligible fruit" vs 0 at D=1.5), so the *attempts* still complete but the batch span grows and the
placed/min falls. The *class census* remains readable (the within-run ok-vs-fail comparison
survives a moved branch), but any cross-speed census delta is a cross-scenario statement.

### 5.3 The R6-B / R8-A / R9 closures (do not re-run as-is)

* **R6-B**: the direct carry/grip class is a **drive-saturated pinch** — the command sits a
  median 11.9 mm inside the payload's measured span, the contact force reads 4.1–4.5 N (the
  drives' limit), and releasing the command to 0.5 mm of interference leaves the force unchanged
  (4.15–4.47 N): **more or less interference does not set the normal force**. The retuned carry
  guard: pooled 24/75 vs 25/75, carried 46 → 44, paired 3 B-only / 1 A-only (p = 0.3125), cycle
  +4.5 % — not adopted; the 100–400 mm band converts 0/37; the earliest escape signal
  (one-sided contact) carries no warning over the 2 mm crossing.
* **R8-A**: the D screen's three forms all fail (D2a the lower grip plane: the escape signature
  persists, the population moves up the band, flails 1 → 14, the battery 12/20 → 5/20 x2; D2b the
  cradle/scoop: the ledges bat the payload, no-contact 2 → 9, 12/20 → 6/20 x2; D3 the raised
  station: `recirculated` 0 → 13, 12/20 → 1/20 x2, a new "fruit never settled" note). The
  bounded grip-geometry lever space is measured closed around the carry class.
* **R9**: the AWR-clipped RWR iteration (the only lane that weights the policy's own outcomes)
  closed negative: A 25/75 vs B 18/75, the paired carried-class conversion 5 B-only / 4 A-only
  (p = 0.500), the carry window branch-invariant (74/74 `grasp_lift` legs per arm; force@onset
  4.93/5.38 N) — **the scripted primitive owns the pre-onset facet**; the post-training moved the
  handover state instead (6 reach-cliff flails vs 1).

### 5.4 The conserved-mass lesson (the endpoint discipline)

Three instances of the same shape: the P11-C from-open (pooled 39 → 35; the seed-11 branch +3,
the controls against), the P11-C.2 (35/31/30), the P15's M2 (45 → 38; the carried 0 → 6 at seed
5). The lesson the sketch encodes: **read the TOTAL failure mass (the no-grasp + the carried
together), never the no-grasp alone**, and treat a walk movement without a total movement as a
negative. The pick's own mechanism gate is built to detect the re-draw *before* the outcome
battery: the post-response arrest read (a response that keeps the geometry but not the friction
is a re-draw in advance).

### 5.5 The trace's own limits (they bound the design)

The corpus is 8 no-grasp (5 B1 + 3 B2, heterogeneous — 3 hold-walk B1s + 2 probe-walk B1s + 3
B2s; the hold-walk class is left-arm-only at this n — not a measured arm effect); the untraced
windows (the re-seat 101 ticks, the takeoff→carry gap 0.78–1.01 s) bracket rather than explain;
the metric is a displacement, not a force decomposition; the 2 mm threshold is not a separator by
itself; and it is one scenario, one tree (the within-run ok-vs-fail comparison survives a moved
branch; a cross-run rate does not). **The strongest reason the pick could fail**: the response
re-centres the contact but does not change the friction margin — the payload keeps sliding (now
with the arm chasing it), the walk does not fall, and K1 closes at Stage M; the second mode is
the conserved mass itself (the walk falls, the carried absorbs). Both are cheap and informative:
K1 stops the phase before the outcome battery, and the two forms discriminate the recovery
hypothesis from the commitment hypothesis with one traced battery.

### 5.6 The sibling lane's NO-GO (the in-window reaction family)

The P17-C KB refresh (`docs/papers/UPDATE_2026_10.md` §3/§5) closes "the in-window reaction
family" — force/stiffness/shear actuation *inside* the **0–2 tick** slide has no actuator or
window (the W5/R11-B/R6-B measurements + the external arguments), and the **policy-side** repair
of the capture window is unreachable (the scripted primitive owns the window's actions; R9's
wrong-channel degradation). This design's pick is **not** in that family, and the distinction is
precise: (i) the pick's window is the **hold + probe-1** — a *slow* process of tens of ticks
(the walk 32–55 mm at 0.08–0.14 m/s ≈ 0.25–0.5 s), not the few-ms impact; (ii) the actuator is
the **scripted primitive's own arm command** (a kinematic re-centring), not a force/stiffness/
shear actuation; (iii) the *scripted* side owns the window — the pick changes the scripted
profile, which is exactly the P17-C's survivor ("the pre-window construction of the scripted
profile"), applied to the pre-lift window the trace localized. The freeze-side alternative form
is a *pre-hold* construction (the commit at the close's end). What remains closed from that NO-GO
is the *in-impact* reaction — the pick does not touch it.

---

## 6. The reads and reproduction (read-only; this design's provenance)

```bash
# the target (the trace's numbers; all committed)
sed -n '1,60p' logs/p14b/TRACE_RESULTS.md                 # §0 the answer + the master table
sed -n '276,370p' logs/p14b/TRACE_RESULTS.md              # §3.4 the mechanism / §3.5 the F1 test
sed -n '134,184p' logs/p16/BOUNDARY_DESIGN.md             # the world decomposition (the K1 refutation)
# the P15 screen/outcome (the measured family + the conserved mass)
sed -n '1,60p;107,205p' logs/p15/SCREEN_RESULTS.md
cat logs/p15/OUTCOME_RESULTS.md
# the belt-speed screen (the R3 §4 table)
sed -n '263,305p' logs/w8/R3_RESULTS.md
# the close/hold/probe/freeze code (the inventory's sites)
sed -n '7940,8060p;8210,8280p;8650,8760p' src/fruit_sorting/tasks.py
sed -n '4032,4066p;4126,4148p' src/fruit_sorting/tasks.py   # the select floor / the pick lead (the belt coupling)
# the closed families
sed -n '1,60p' logs/r6/B_RESULTS.md; sed -n '1,60p' logs/r8/A_RESULTS.md; sed -n '1,60p' logs/r9/RESULTS.md
```

**What this lane did NOT do**: no simulator run, no `src/`/`scripts/`/`configs/`/`datasets/`/
`Paper/` edit, no default changed, no branch operation, no commit; all writes under `logs/p17/`.
