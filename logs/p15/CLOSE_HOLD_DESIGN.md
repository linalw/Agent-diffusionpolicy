# P15: the close/hold grip-margin design — the actuator inventory, the pick, and the pre-registration sketch (Tier C offline)

Status: **offline design lane, read-only on the tree** (branch `p-supply`, 2026-10-19). No
simulator run, no `src/`/`scripts/`/`configs/`/`datasets/`/`Paper/` write, no commit; all writes
under `logs/p15/`. Tree pins as read: `tasks.py`
`810658b802d22bbd63013726fc78af81`, `fruits.py` `d28546d26137d4540421caa7fa34a139`,
`meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f` (the P12-A.2/P11-C.3 revision the P14-B trace
lane read; unchanged by P13/P14). The design executes the P14-B branch selection
(`logs/p14b/TRACE_RESULTS.md` §0/§4: the loss localizes to the **HOLD + probe-1**, the loaded
capture transient; the selected family is the **close/hold grip-margin family, R11-B C1 first**;
the trace cannot choose among the close-side actuators).

The inputs read: `logs/p14b/TRACE_RESULTS.md` + `master_table.md` +
`trace_p14b_tables.txt` + `GRIP_DIAGNOSTIC.md` (§2/§3 the trace pre-registration and the
lever mapping), `logs/r11/B_RESULTS.md` + `PREREGISTRATION_LOADPATH.md` (C1's record),
`logs/p11/A_PHYSICS_AUDIT.md` (the close's 2.5 mm design clamp, the finger material, the
drive), `logs/p12a2/A2_RESULTS.md` + `IMPLEMENTATION.md` (the mass base), the close/hold/probe
code in `tasks.py` (read-only), and the close-side screens `logs/p10e/NOGRASP_DIAGNOSIS.md`,
`logs/p11c/{C,C2,C3}_RESULTS.md`, `logs/p11b` (the plow), `logs/r6/B_RESULTS.md` (the squeeze
closure), `logs/w8/B_RESULTS.md`, `logs/w5` (the takeoff screens), `logs/p12{,a2,b}` (the
physics/property lane).

---

## 0. The answer in one screen

* **The target the design must move** (the trace's measured transient): the **hold walk** —
  the payload's hand-frame drift across the 0.4 s hold, measured from the freeze. Control
  bands: the ok attempts ≤ 12.8 mm (median 0.2); the three hold-walk B1s **31.9 / 38.1 /
  54.8 mm**, walking at **0.08–0.14 m/s ≈ belt speed with the force still 3.4–15 N**; and the
  **probe-1 first departures** (4/8 no-grasp cross in probe block 1; the no-grasp B1s' probe-1
  lift dz −1.2…+0.9 mm — the fruit never rises).
* **The actuator inventory** (close/hold-side, reachable from the current knobs/code; §2):
  **(A)** the C1 load rate `FRUIT_CLOSE_LOAD_RATE` (0 = off); **(B)** the freeze criterion
  `FRUIT_DYNAMIC_CONTACT_FORCE/TICKS/STALL` (0.5 N / 3 ticks / 0.15 mm-tick; the threshold knobs
  exist — the *straddle criterion* is the part with no built form); **(C)** the squeeze/close depth
  `FRUIT_DYNAMIC_CLOSE_DEEP` 0.97,
  `FRUIT_GRIPPER_SQUEEZE` 0.98, `FRUIT_DYNAMIC_MIN_INTERFERENCE` 2.5 mm, `FRUIT_DYNAMIC_CLOSE_LIVE`
  0.97; **(D)** the hold compensation for the belt motion — `FRUIT_DYNAMIC_HOLD` 48,
  `FRUIT_CLOSE_CONTACT_LEAD` (C2, unset → `FRUIT_DYNAMIC_TRACK_LEAD` 0.18), the x pin/seek; and the
  untraced descent-settling term (the AGENTS §2 boundary item); **(E)** the probe's shape
  `FRUIT_DYNAMIC_PROBE` 0.006 / `_PROBE_TICKS` 60 / `_TEST_STEP` 0.01 (two-line profile) + the
  force servo. The closed families are §2.6.
* **The ranking** (§3): **1. C1** (the mapping's first; the only close-side actuator with a
  *measured* actuation signature on the dynamic-capture path; env-only; its failure mode is
  pre-registered); **2. the hold-window lead** (C2 at 0.10 — the best fit to the trace's own
  window and variable class, the arrest/shear; env-only; a null class read at N=1×15);
  **3. the freeze criterion** (the best fit to the "tip/edge contact" root; unbuilt, `src/`;
  the deeper-freeze ejection prior); **4. the squeeze/close depth** (closed by mechanism on the
  direct interface; low expected movement); **5. the probe's shape** (the completion, not the
  origin; weak specificity).
* **The pick** (§4): **a bounded two-arm Stage-M mechanism screen at SEED 11 — M1
  `FRUIT_CLOSE_LOAD_RATE=0.04` (primary) and M2 `FRUIT_CLOSE_CONTACT_LEAD=0.10` (the
  hold-window arm) — read against the already-on-disk traced control (`logs/p14b/traces_s11`),
  with the trace's own hold-walk/probe-1 rules as the promotion gate; ONE promoted arm then
  runs the outcome battery (the no-grasp class + the falls) at SEED 11/5/23.** The two arms are
  the two mechanistically distinct hypotheses for the hold walk — the *freeze state entering*
  the hold (C1) vs the *hold-window arrest itself* (the lead) — which is exactly the choice the
  trace cannot make; both are env-only and the control costs no run.
* **The strongest reason it could fail** (two modes, both pre-registered): **K1 — the hold walk
  does not fall (or rises) under either arm**: the trace's metric is a displacement, not a force
  decomposition, and it **cannot split the walk between the belt drag and the hand's own ~30 mm
  descent-settling motion** (its limit #6; the AGENTS §2 boundary shortfall) — if the walk is the
  hand's settling, no close/hold actuator moves it, the mechanism gate closes the phase before
  the outcome battery, and the next named item is the descent-boundary/scene family. **K2 — the
  C1-specific prior**: the slow close lets the fruit ride the faces > 1 s and produces a *new*
  never-grasped class (the measured stage-P trade, 0 → 5) — i.e. C1 raises the hold walk instead
  of lowering it. See §3 and §5.3.

---

## 1. The target: what the trace measured (the endpoints the design must move)

Everything here is the P14-B analysis's own numbers on the **mass base** (`logs/p12a2/*_mass.log`
+ the three trace runs, `logs/p14b/traces_s{11,5,23}`; 45 ok / 7 carried / 8 no-grasp, B1 5 / B2 3).
The trace-on runs replay the mass base **byte-identically** (950/1047/1084 `[fruit]` lines, exact),
so the corpus is the mass base itself, and the design can read both the mechanism and the
outcome off the same runs.

### 1.1 The two candidate pre-outcome signals

| class | n | hold walk mm (min/med/max) | probe-1 lift dz mm (min/med/max) | total drift mm |
| --- | --- | --- | --- | --- |
| ok | 45 | −0.6 / **0.2** / 12.8 | −0.4 / 8.4 / 67.5 | 0.0–27.2 |
| carried | 7 | 2.6 / 4.3 / 5.8 | 8.8 / 15.6 / 17.8 | 3.4–1407.3 |
| B1 | 5 | 0.1 / **31.9** / 54.8 | −1.2 / −0.5 / 0.9 | 1458.1–95 403.7 |
| B2 | 3 | 0.0 / 0.7 / 1.8 | 5.2 / 7.1 / 7.8 | 294.8–344.8 |

* **The hold walk** = the drift change across the hold segment, measured from the last close row
  (the freeze). It separates **3 of 8** no-grasp attempts at a **>2.5× margin** (12.8 → 31.9) and
  is the B1 majority's initiation. The ok walk is universal-but-small (21/45 exceed 2 mm); its
  *magnitude* and its *fate* are the signals.
* **The probe-1 lift dz** = the fruit's z rise over the first probe block — a **grip test**, not
  the 6 mm command (the probe's aim tracks the fruit's live position + a 6 mm ramp, so a gripped
  fruit rides the feedback up: ok up to 67.5 mm). The no-grasp B1s read −1.2…+0.9 (never rises).
  **But 5 ok attempts' first probes also read ≤ 2.5 mm and recovered via a re-seat** — a failed
  first probe is not specific to the losses.

### 1.2 The first departure and the release (the phase localization)

* **First departure** (the 2 mm rule, the pre-probe cases labelled per the W5-C convention):
  hold 2 (a06, a08 — the payload already out at the probe's first sample), **probe block 1 4**
  (a01, a07, a13, strawberry), takeoff 1, takeoff→carry gap 1 (the no-grasp); the carried class
  4 probe-1 / 1 takeoff / 2 carry.
* **Release** (sustained `F < 0.5 N ∧ contacts == 0`): hold 2, probe-1 2, re-seat window 2 (both
  with the payload already 22.4/25.8 mm out at the window's near edge), gap 1, carry 1.

### 1.3 The mechanism (the three shapes)

* **At the freeze every attempt's payload moves at ~0.10 m/s — the belt speed** (a01 −0.099,
  a10 −0.101, a06 −0.102 m/s in y). **The hold is where the pads must arrest that motion;
  whether they do is the ok/fail line.**
* **Shape A — the hold walk (3/5 B1: a01 orange, a06 tomato, a08 orange)**: the payload walks
  32–55 mm during the 0.4 s hold with the force still 3.4–15 N (a **loaded slide**); the hand
  also translates ~30 mm as the post-descent solver finishes the approach; the force servo
  chases its whole range (`closed = 18.0–19.2 mm`, `trips = 54–60`); the contact collapses inside
  the hold (a06 t=64.18, a08 t=84.03) or at the probe's first ticks (a01: F 2.90→0.52→0.00 in
  2 ticks). The three probe cycles then run with nothing (the drift grows 288→477→648 mm).
* **Shape B — the probe's lift (2/5 B1: a13 tomato, s23 a02 strawberry)**: a clean hold, the
  fruit does **not** rise with the probe (dz 0.0/−0.8), the pads **pry to their 98–99 mm limit**
  with force spikes (33–88 N), the payload walks out and releases across the next re-seat window.
* **The B2s (3)**: clean holds, the fruit rises (+5.2…+7.8), the loss is later (a02 takeoff walk →
  carry release; a04 the takeoff→carry gap; a07 the probe's end).
* **The carried class (7)**: clean holds, the fruit rises (+8.8…+17.8), the loss is the
  carry/place escape (5 in the carry, 2 at the place).

### 1.4 The trace's own limits (they bound any design built on it)

1. **n = 8 no-grasp** (5 B1 + 3 B2), all but one at seed 11; heterogeneous; the hold-walk class is
   left-arm-only (3/3) while the probe-walk B1s are right-arm (2/2) — not a measured arm effect.
2. The trace's `outcome` field = `placed`, so "fail" mixes the no-grasp and the carried classes.
3. **The untraced windows bracket, they do not explain**: the re-seat windows (101 ticks) and the
   takeoff→carry gap (0.78–1.01 s) have no per-tick rows; 2 no-grasp releases complete inside the
   former (with the payload already out) and 1 in the latter.
4. The reference choice (`ref` = the last hold row) understates the pre-reference walk; the 2 mm
   threshold is not a separator by itself (it fires on 12 ok attempts and 5 carried).
5. **One scenario, one tree** (the patch sheet + real-mass + the shipped tree incl. the W7-A park
   gate); the within-run ok-vs-fail comparison is valid, no cross-run rate is quoted.
6. **The metric is a displacement, not a force decomposition** — the trace **cannot split the walk
   between the belt drag and the hand's own settling motion** (the ~30 mm descent-solver term).
7. No simulator run by the analysis lane; the three runs were the run lane's.

---

## 2. The actuator inventory (close/hold-side, reachable from the current knobs/code)

Each entry: the knob/site + the shipped value → the mechanism against the trace's measured
transient → the evidence FOR → the evidence AGAINST → the falsifier. "Reachable" = env-only
(the knob exists and is default-off) unless marked **unbuilt** (a control change with no form in
the tree).

### 2.1 (A) The C1 load rate — `FRUIT_CLOSE_LOAD_RATE` (m/s), default 0 = off

* **Site**: `tasks.py` `__init__` 1022–1023, the close ramp 7423–7452 (the whole-close face-speed
  cap, the horizon grown until `deep`, capped 240 ticks), the delivered-command rate limit
  7867–7873 (the A.1 amendment). Scoped to `_dynamic_capture_active` — the scripted moving catch
  **and** the direct/policy handover with `FRUIT_DYNAMIC_PICK=1`; the indexed/static path never
  reads it.
* **Mechanism vs the trace's transient**: the shipped two-phase close meets the fruit inside the
  24-tick fast phase (the trace's freeze rows 16–38) at up to ~350 mm/s of face speed; C1 caps the
  delivered face speed (test value **0.04 m/s**), so the **freeze moves later and the load arrives
  slower** — it changes the *state entering the hold* (where/how the pads are loaded when the
  arrest begins). It does **not** touch the hold window itself.
* **Evidence FOR**: the only close-side actuator with a **measured actuation signature on the
  shipped dynamic-capture path** (R11-B M1, direct: the freeze row 18.0 → **55.5**, the
  freeze-zone face speed 188.7 → **39.9 mm/s**); the two-line is **unmeasured** for it; env-only;
  the P14-B mapping's pre-registered first choice.
* **Evidence AGAINST**: the R11-B **stage-P scripted battery is negative in substance** — 12/20 =
  60 % vs the control 13/18 = 72 %, the never-grasped class **0 → 5** (all late-freeze 142–157
  ticks; "the fruit rides between the slowly closing faces for >1 s; the grip that forms is
  marginal and slips at the pluck"), the cnp gain (−2) exactly at the bar, `diverted` 1 → 2. The
  stage-N direct A/B was **stopped incomplete** (A run 1 = 6/15), so C1 is unconfirmed on the
  direct interface. The trace's **F2** says the close-phase *summary* geometry overlaps (the freeze
  `sep−gap_cmd` 4.5–13.3 vs ok −0.0–14.7; the close-start offset 10.7–14.8 vs 8.8–15.5) — the
  separation is *dynamic*, which is why a dynamic close-side change is the right instrument class,
  but its linkage to the hold walk is **indirect**.
* **Falsifier**: the hold walk does not fall under C1 (or rises) — the arrival rate is not the
  capture transient's actuator on this line; and/or the never-grasped class grows (the stage-P
  signature reproduces).

### 2.2 (B) The freeze criterion — `FRUIT_DYNAMIC_CONTACT_FORCE` / `_TICKS` / `_STALL` (+ the unbuilt straddle form)

* **Site / value**: 0.5 N, 3 consecutive ticks, |Δsep| ≤ 0.15 mm/tick (tasks.py 7668–7672, the
  detection 7875–7924). The freeze fires on the **first sustained contact + span stall**, sets
  `freeze_cmd = cmd` (the *delivered* depth), and is never re-evaluated. The span at detection on
  the P10-E corpus is **+3.7…+35.1 mm wider than the fruit** (a tip/edge contact, not a centred
  pinch — inferred, not measured).
* **Mechanism vs the trace's transient**: the criterion decides *when and at what geometry* the
  capture freezes — i.e. the contact the hold inherits. A **straddle criterion** (require the span
  to reach the extent / a deeper stall / a two-sided contact before freezing) is the only close-side
  lever aimed at the **"tip/edge contact" root** the trace's F2 leaves open.
* **Evidence FOR**: the root is named (P10-E §2.5) and untested; the trace's F2 is *partial* — the
  summary geometry overlaps but the first-departure phases differ, so a **dynamic** contact-geometry
  change is not excluded; nothing in the record has ever changed the *criterion* itself.
* **Evidence AGAINST**: **unbuilt** (an `src/` change with its own pre-registration + stub, cost
  above the env-only family); the freeze depth feeds the whole downstream chain (the hold, the
  probe, the carry re-command `_closed_gap`); and the **deeper-freeze ejection prior** — the
  corrected P11-B plow measured the true descend-onto-the-fruit ejecting at the deeper
  interferences (**tomato ≥ 10 mm: 2/3; apple ≥ 2 mm: 3/3**), while the shallow ones stayed.
* **Falsifier**: the freeze geometry (the span − extent) is unchanged by the criterion change, or
  the class re-draws worse (the deeper freeze reproduces the plow signature).

### 2.3 (C) The squeeze / close depth — `FRUIT_DYNAMIC_CLOSE_DEEP` 0.97, `FRUIT_GRIPPER_SQUEEZE` 0.98, `FRUIT_DYNAMIC_CLOSE_LIVE` 0.97, `FRUIT_DYNAMIC_MIN_INTERFERENCE` 0.0025 m, `FRUIT_GRIPPER_PRELOAD` 0, `FRUIT_MIN_INTERFERENCE` 0

* **Mechanism vs the trace's transient**: the freeze depths on the mass base sit **at/near the
  live extent** (the hold-walk attempts: freeze 69.9/64.3/65.8 vs the extents 68.3/63.0/68.3 = +1.6/
  +1.3/−2.5 mm; the class distributions overlap: NG −3.3…+2.3 vs ok −3.8…+22.2). A deeper freeze
  adds commanded interference, which on this hand **does not add force** (see AGAINST).
* **Evidence FOR**: the squeeze side is **unmeasured on the two-line** (all the closures are on the
  direct interface); the trace's hold-walk attempts' freeze depths are at the extent, so a deeper
  straddle is not excluded by the trace itself.
* **Evidence AGAINST (the mechanism closure)**: **R6-B — the direct carry is a drive-saturated
  pinch**: the command sits a median **11.9 mm inside** the measured span (45/46 legs ≥ 5 mm) while
  the force reads **4.1–4.5 N**; releasing the command to **0.5 mm of interference** (via
  `FRUIT_CARRY_RELIEF`) leaves the force **unchanged** (the same 4.15–4.47 N band). The commanded
  interference beyond the contact does not set the normal force. Plus W8-B's squeeze-side closure, the W5-C
  takeoff-squeeze screen (negative), the P10-E §3.3 prior ("expected movement small; the historical
  `FRUIT_GRIPPER_PRELOAD`/`FRUIT_MIN_INTERFERENCE` tests changed nothing"), and the P11-B deeper
  interference ejection prior (2.2).
* **Falsifier** (P10-E §3.3's own): with +1–2 mm of interference the clean legs' force must stay
  ≤ 4.9 N and their `clean_slip` ≤ 1.43 mm; if the no-grasp/hold walk does not move, the capture
  transient is a *geometry/kinematics* problem, not a depth problem.

### 2.4 (D) The hold compensation for the belt motion — `FRUIT_DYNAMIC_HOLD` 48, `FRUIT_CLOSE_CONTACT_LEAD` (C2, unset → `FRUIT_DYNAMIC_TRACK_LEAD` 0.18), the x pin/seek (`FRUIT_DYNAMIC_CLOSE_LOCK_X` 1, `FRUIT_DYNAMIC_X_TRACK_VMAX` 0.12, `_VX_MAX` 0.05, `_LATCH` 1)

* **Mechanism vs the trace's transient**: this is **the trace's own window**. The hold (48 ticks,
  0.4 s; trace rows every 2nd tick) tracks the fruit's live centre + `v·lead`, so the commanded
  relationship to the moving fruit is the **lead**; the fruit is held only by pad friction, so the
  arrest is a **shear/velocity** event. The trace's walk is a slip accumulated at ~belt speed
  (0.08–0.14 m/s) with the force present; the ok attempts arrest it (≤ 12.8 mm) — the difference
  is *whether the pads kill the relative motion*.
* **Evidence FOR (measured)**: R11-B's C2 screen measured exactly this variable class: lead 0.10
  **brakes the fruit harder** (the close-end |v_y| 33–41 → **8–19 mm/s**), lead 0.26 **punts it
  downstream** (129/291 mm/s; the fastest trace 582 mm/s ≈ 4.9× belt) — "the load path's
  longitudinal variable is a velocity/shear one, not a position one". The lead applies to the close's
  load phase **and the hold** (the same knob), i.e. the trace's localized window. Env-only.
* **Evidence AGAINST**: on the direct interface the lead's **class movement was null** at N=1×15
  (M2: cnp −1, escapes ±0; M3's 11 ok/3 cnp was not promoted because the *position* readout
  failed — the wrong instrument, per R11-B §4.4); it is a **kinematic** lever (the landing-floor
  premise is falsified); the two-line is unmeasured; and the trace's limit #6 says the walk may be
  the **hand's own descent-settling motion** (~30 mm), which no contact-window lead can move.
* **The hold length (`FRUIT_DYNAMIC_HOLD`)**: **not a lever** — the walk's rate is constant at
  ~belt speed (a01's ramp ≈ 0.08–0.14 m/s through the whole hold), so more time = more walk, not an
  arrest. **The x pin/seek**: cross-belt (x), not the belt axis (y) — no expected movement on the
  y walk.
* **Falsifier**: the hold walk does not fall under the lead 0.10 → the hold-window arrest is not
  the walk's actuator (then the walk is the descent-settling term; §5).

### 2.5 (E) The probe's shape — `FRUIT_DYNAMIC_PROBE` 0.006 m / `_PROBE_TICKS` 60 / `_TEST_STEP` 0.01 (the two-line `_dynamic_profile` values; the single arm 0.010/40/0.02), `FRUIT_DYNAMIC_TAKEOFF_SQUEEZE` 0.001, the force servo

* **Mechanism vs the trace's transient**: the probe-1 lift is the **grip test** (the aim tracks the
  fruit + a 6 mm ramp); the no-grasp B1s' fruit never rises (−1.2…+0.9 mm) and 4/8 no-grasp
  attempts' first departure is in probe block 1; the 2 probe-walk B1s pry the pads to 98–99 mm with
  33–88 N spikes. A gentler/shorter probe targets the **completion** of an already-marginal grip.
* **Evidence FOR**: unmeasured on the two-line; the trace's F3 is *partial* (3/8 no-grasp complete
  at the probe's lift/end).
* **Evidence AGAINST**: **the specificity is weak** — 5 ok attempts' first probes also read ≤ 2.5 mm
  and recovered via the W1 re-seat; **3/5 B1s' losses precede the probe** (shape A); the W5-C probe
  screens (the takeoff squeeze, TRACK 0.2, LOCK_X) are closed negatives; and the probe acts on a
  grip that is already marginal when it starts.
* **Falsifier**: a gentler/shorter probe does not raise the re-seat recoveries or lower the probe-1
  departure count (or it converts nothing while re-drawing the class).

### 2.6 The closed families (the record — do not re-run as-is)

* **The force servo / the chase** (`FRUIT_DYNAMIC_FORCE_*`, `FRUIT_FORCE_REENTRY`): the trace's
  **F1 is confirmed** — no re-seat window ever released a held payload; the chase is a *symptom*
  (it fires after the force collapses). Priors: P7-2a (chase 5 → 0, carried 5 → 5, zero
  conversions), the W5-C cfg1 (the servo's removal leaves the class alive), P11-C.2 (the chase stop
  *hurts*: the pooled 39 → 31/60, the seed-11 branch 13 → 6).
* **The re-seat floor** (`FRUIT_DYNAMIC_REGRASP_FLOOR`, never built): dead as the initiator (F1);
  the keep-gap arithmetic does not separate (the seed-5 apple: a **success** with a full-chase
  re-seat, keep-gap 49.3 on a 65.2 mm fruit, `clean_slip` 0.1 mm).
* **The arrival family** (`FRUIT_DYNAMIC_REGRASP_FROM_OPEN` ± the chase stop / the range cut):
  pooled 35 / 31 / 30 vs the anchor 39/60; kill 2 fired on all; the control-side ejection space is
  measured closed (P11-C).
* **The takeoff screens** (W5-C cfg1–4): every config leaves the left class alive.
* **The pluck dwell** (C3): actuated (30 rows) but inert on the escape class — the failures are
  decided *before* it.
* **The physics / shape / scene**: the **mass base is the winner** (45/60, the falls 14 → 6 rows,
  the double bit-identical); the compliance is negative (−9), the restitution neutral; S3 (the
  approach height) negative at every seed; S4 (the containment) removes the falls but re-draws
  −13; the D3-proper scene redesign is owner-gated.

---

## 3. The ranking and the pick

The ranking criterion the mission fixes: **the expected movement per the trace's localization /
the cost / the risk**, with the evidence quality as the tiebreak.

| # | actuator | current | the trace's endpoint it can move | the expected movement | the cost | the risk | the decisive evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **1** | **C1** `FRUIT_CLOSE_LOAD_RATE` | 0 (off) | the hold walk (via the freeze state entering the hold) + the probe-1 dz | moderate; **direction uncertain** (the stage-P mechanism reads adverse) | **env-only** (~10 min/run) | the never-grasped growth (measured once, 0 → 5) | the mapping's first; the only **measured actuation** on this path (the freeze row 18 → 55.5, the speed 189 → 40 mm/s); the two-line unmeasured |
| **2** | **the hold-window lead** (C2 `FRUIT_CLOSE_CONTACT_LEAD`) | unset (0.18) | **the hold walk itself** (its own window; a shear variable) | moderate-high; direction **measured** at the close end (braking) | env-only | a null class read (N=1×15); a kinematic lever; the walk may be the hand's settling | R11-B §4.4: the lead moved the **velocity** (33–41 → 8–19 mm/s) and not the position — the trace's variable class |
| **3** | **the freeze criterion** | 0.5 N / 3 / 0.15 mm | the freeze geometry the hold inherits (the tip/edge root) | moderate-high in principle; **unbuilt** | `src/` + a pre-registration + a stub | the deeper-freeze ejection prior (the plow: tomato ≥10 mm 2/3, apple ≥2 mm 3/3) + the depth coupling | the trace's F2 partial; the root named (P10-E §2.5) but never tested |
| **4** | **the squeeze / close depth** | 0.97 / 0.98 / 2.5 mm | the freeze depth | low | env-only | the clean-leg force/geometry side effects | R6-B: the drive-saturated pinch (the relief to 0.5 mm leaves the force 4.15 → 4.47 N) |
| **5** | **the probe's shape** | 0.006 / 60 / 0.01 | the probe-1 completion | low-moderate | env-only | the weak specificity (5 ok first probes also fail) | the trace's F3 partial; 3/5 B1s' losses precede the probe |

**The pick.** Two arms, one battery — the trace's own conclusion is that the choice among the
close-side actuators **is an A/B** (`TRACE_RESULTS.md` §4: "the trace localizes; it cannot pick
among the close-side actuators"), and the two top-ranked arms are the two mechanistically
distinct hypotheses for the hold walk:

1. **C1 (`FRUIT_CLOSE_LOAD_RATE=0.04`) — the primary**, per the P14-B mapping's pre-registered
   order ("the R11-B C1 first") and because it is the only close-side actuator whose **actuation
   is measured** on this code path (the screen can verify actuation before reading the outcome).
2. **The hold-window lead (`FRUIT_CLOSE_CONTACT_LEAD=0.10`) — the second arm**, because it is the
   only actuator whose **own window is the trace's localized window** and whose measured variable
   class (the arrest/shear) is the trace's metric class. It ranks below C1 on the composite only
   because its single class read is a null (N=1×15, direct) while C1's failure mode is measured and
   pre-registered; on pure mechanism fit to the trace it ranks **first**.

The squeeze-side and the freeze criterion are **not** in the first battery: the squeeze is closed
by mechanism (R6-B) with a flat prior (P10-E §3.3), and the freeze criterion is unbuilt. The
squeeze-side arm can be appended to the same Stage-M block as a **third arm** (the trace's own
named alternative, "unmeasured on the two-line") if the Tier-A budget allows; the freeze criterion
is the **named fallback** if both screen arms fail on the mechanism gate (its own pre-registration,
per §2.2).

**The strongest reason the pick could fail** (the design's K1): the hold walk may be **neither** the
close's arrival rate **nor** the hold-window lead — the trace's own limit #6 says the metric cannot
split the walk between the belt drag and the **hand's own ~30 mm descent-settling motion** (the
AGENTS §2 boundary shortfall: every descent ends 40–90 mm short of the pick pose and the
post-descent solver finishes the approach). If the walk is the hand's settling, **no close/hold
actuator moves it**, both arms read flat, and the named next is the descent-boundary/scene family —
which is exactly why the design's mechanism gate (K1) is pre-registered to stop before the outcome
battery rather than to spend it on a flat mechanism.

---

## 4. The pre-registration sketch (to be frozen before any run)

**One paragraph.** On the mass base — `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_PHYSICS_REAL_MASS=1 ATTEMPTS=20 HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1 FRUIT_DYNAMIC_TRACE=1
FRUIT_DYNAMIC_TRACE_DIR=logs/p15/traces_<arm>_s<SEED>`, `scripts/run.sh scripts/20_pick_place.py`,
Tier A solo through `scripts/154_claim_run.sh` — run the **Stage-M mechanism screen at SEED 11**:
**M0 the control** (already on disk, `logs/p14b/traces_s11` + `logs/p12a2/10_seed11_mass.log`; no
run), **M1 `FRUIT_CLOSE_LOAD_RATE=0.04`**, **M2 `FRUIT_CLOSE_CONTACT_LEAD=0.10`** (the optional
**M3 `FRUIT_DYNAMIC_CLOSE_DEEP=0.95`** squeeze-side arm appended if the budget allows), and promote
**at most ONE** arm to **Stage P** iff (a) its **hold walk** falls — per the P14-B tooling
(`logs/p14b/trace_p14b_analysis.py` verbatim: the drift change across the hold from the last close
row; the control's own bands: ok ≤ 12.8 mm, the three hold-walk B1s 31.9/38.1/54.8 mm) so that the
no-grasp attempts' walks land in/below the ok ceiling or the seed-11 no-grasp count falls ≥ 2 —
**and** (b) its **probe-1 first departures** do not rise (the 2 mm rule, phase-bracketed, the count
per class) and the probe-1 dz distribution does not worsen — **and** (c) no new failure reason and
**no growth of the never-grasped/no-contact class** (the R11-B stage-P kill); the promoted arm then
runs the **outcome battery at SEED 11/5/23** (the same env, one run per seed, each with a
bit-identical double): the **no-grasp class** by the P10-E rules (B1/B2), the **falls** (the
`clearance` row's lowest payload point ≤ −1000 mm; partials −100…−1000 reported separately), the
carried-not-placed, the pooled outcome, and the mechanism read (the hold walk, the probe-1
departures, the freeze row/speed as the actuation check); the **kills** are K1 (the mechanism gate:
no arm's hold walk moves in the predicted direction — close the phase at M, publish the mechanism
negative, do not spend P), K2 (the never-grasped/no-grasp class grows ≥ 2 at seed 11 or ≥ 2 pooled
— negative, not adopted), K3 (any run's double is not bit-identical — the scripted line is
deterministic; the measurement is invalid), K4 (the no-harm fails), K5 (a concurrent Tier-A job or
a wedge corrupts a run); the **no-harm** half runs with the knobs unset: `scripts/accept.sh`
9/10 + `fingerprint: matches configs/motion_reference.json`, the two-line dense re-record +
`scripts/190_twoline_gate.sh` PASS, `scripts/selfcheck.sh` PASS, and the knob-off seed-11 control
replaying `logs/p12a2/10_seed11_mass.log` byte-identically (the `[fruit]` lines) — the new knobs
are env-only and default-off, so the shipped single-arm and two-line defaults are byte-unchanged by
construction.

### The structured form

**Scenario.** The mass base verbatim (`logs/p12a2/run_battery.sh`): `FRUIT_BIARM=1
FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_PHYSICS_REAL_MASS=1 ATTEMPTS=20`, plus
`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1
FRUIT_DYNAMIC_TRACE=1`. Seeds: **11 primary** (7 no-grasp: 4 B1 + 3 B2 — the only seed with B1
mass), **5 / 23 controls** (0 and 1 no-grasp: the ok-population shape + the class re-draw check).
The trace is run-neutral on this scenario (measured: the three runs replay the mass base
byte-identically), so the mechanism and the outcome come off the same runs.

**Arms.** Stage M (SEED 11, traced): M0 = the on-disk control; M1 = `FRUIT_CLOSE_LOAD_RATE=0.04`;
M2 = `FRUIT_CLOSE_CONTACT_LEAD=0.10`; M3 (optional, budget) = `FRUIT_DYNAMIC_CLOSE_DEEP=0.95`.
Stage P (the promoted arm only): SEED 11/5/23 + the doubles.

**Mechanism endpoints** (the trace's own rules, re-derived by `trace_p14b_analysis.py`):
(i) the **hold walk** per attempt (mm) — the class distributions vs the control's own (the ok
≤ 12.8, the three hold-walk B1s 31.9/38.1/54.8); (ii) the **probe-1 first departures** (the count
per class + the phase bracket) and the **probe-1 lift dz** (the grip test); (iii) the **actuation
checks**: M1 the freeze row / the contact-zone face speed (the R11-B signature: the freeze row
later, the speed ≤ 60 mm/s), M2 the hold-window shear (the close-end/hold |v_y| — the lead's
measured direction), M3 the freeze depth/span. (iv) the release bracket per attempt (the hold /
probe-1 / window / gap / carry histogram) as the descriptive read.

**Outcome endpoints** (Stage P): the **no-grasp class** (P10-E rules) and the **falls** (the
`lowest payload point` ≤ −1000 mm; the partials −100…−1000 mm reported separately) at SEED 11/5/23,
plus the carried-not-placed and the pooled outcome; the **rate is not the endpoint** (the outcome
is quantized per AGENTS §2 — quote the class census and the per-leg motion, not cross-config
deltas).

**Promotion rule (M → P).** An arm is promoted iff (a) its no-grasp hold walk falls into/below the
ok band (≤ 20 mm, inside the 12.8 → 31.9 gap) on ≥ 2 of the control's three hold-walk attempts,
**or** the seed-11 no-grasp count falls ≥ 2 with the hold-walk attempts converting; **and** (b) the
probe-1 departure count does not rise and the probe-1 dz does not worsen; **and** (c) no new
failure reason and no never-grasped growth. If two arms qualify, promote the larger hold-walk
movement (the tie to the stronger actuation read). If none qualifies, the phase closes at M.

**Kills.** K1 the mechanism gate (above) — the bounded negative. K2 the class re-draw: the
never-grasped/no-grasp class grows ≥ 2 at seed 11 or ≥ 2 pooled → negative, not adopted. K3 a
non-bit-identical double → the run is invalid. K4 the no-harm item fails. K5 a protocol
interference (a concurrent Tier-A job, a broken claim, a wedge) invalidates the block.

**No-harm (knobs unset).** `scripts/selfcheck.sh` PASS; the acceptance **9/10 + `fingerprint:
matches`** with its `[fruit]` stream compared to the pre-phase control; the two-line dense
re-record + `scripts/190_twoline_gate.sh` PASS; the knob-off mass-base control replay (the
`[fruit]` byte-identity vs `logs/p12a2/10_seed11_mass.log`). The new knobs are env-only,
default-off, dynamic-capture-scoped: the shipped single-arm default and the two-line opt-in are
byte-unchanged by construction (re-verified, not assumed).

**Budget.** Stage M 1–2 traced runs (~10 min each; M0 is free) ≈ 20 min; Stage P the promoted arm
at SEED 11/5/23, each with its bit-identical double (6 runs ≈ 60 min; the doubles are required by
K3, the scripted line is deterministic); the no-harm ~15 min. Tier A solo throughout; ~1.5 h.

**Pins.** `tasks.py` `810658b802d22bbd63013726fc78af81`, `fruits.py`
`d28546d26137d4540421caa7fa34a139`, `meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`; the tooling
`logs/p14b/trace_p14b_analysis.py` + `logs/p10e/census.py`/`classify.py` (the class rules);
`configs/*` untouched.

---

## 5. The honest constraints

### 5.1 What the records already rule out (do not repeat)

* **The R11-B negative is the pick's own prior**: C1's scripted stage-P battery read 12/20 = 60 %
  vs the control 13/18 = 72 %, with the never-grasped class 0 → 5 — the cnp gain (−2) exactly at
  the bar and the same-battery "no new failure reason" item failed; the honest stage-P read is
  **not positive**, and the stage-N direct A/B stopped incomplete. C1 is **unconfirmed**, not
  adopted. The design's K2 re-imposes exactly this failure mode as a kill.
* **The pre-onset load path is closed** (R11-B §4.5): the payload is held to trace resolution
  through the belt-break/probe; no pre-onset scalar separates held from escape; the screen's three
  dimensions (the arrival rate C1, the longitudinal seat C2, the pluck transient C3) either actuate
  without eliminating the class or do not actuate on the pre-registered variable.
* **The squeeze-side family is closed by mechanism** (R6-B §2: the drive-saturated pinch — the
  command sits 11.9 mm inside the span, the force 4.1–4.5 N, the relief to 0.5 mm leaves the force
  4.15 → 4.47 N; W8-B's squeeze closure; the W5-C takeoff-squeeze screen; the P10-E §3.3 prior).
* **The reaction/guard family is closed** (W8-B 5-1 p=0.1094; R6-B 3-1 p=0.3125; the 100–400 mm
  band converts 0/37–0/34; the reaction has 0–2 ticks of warning).
* **The control-side ejection space is closed** (P11-C: the arrival family 35/31/30 vs 39/60, kill
  2 fired on every arm).
* **The re-seat floor is dead as the initiator** (the trace's F1) and the keep-gap arithmetic does
  not separate (the seed-5 apple counterexample).
* **The physics/shape/scene families**: the compliance negative, the restitution neutral, S3
  negative, S4 a re-draw, D3-proper owner-gated; the mass base is the winner and the iteration
  reference (no shipped-default flip).
* **The takeoff screens** (W5-C cfg1–4) and **the pluck dwell** (C3) are recorded negatives.

### 5.2 The trace's own limits (they bound the design)

The seven limits of §1.4, restated as design constraints: the corpus is **8 no-grasp** (heterogeneous
— the hold-walk class is 3/5 B1 and left-arm-only at this n); the **untraced windows** (the re-seat
101 ticks, the takeoff→carry 0.78–1.01 s) bracket rather than explain; the metric is a
**displacement**, not a force decomposition — **it cannot split the belt drag from the hand's own
settling motion**; the 2 mm threshold is not a separator by itself; and it is **one scenario, one
tree** (the within-run ok-vs-fail comparison survives a moved branch; a cross-run rate does not).

### 5.3 The strongest reason the pick could fail (stated once, plainly)

**The hold walk may not be a close/hold-chain quantity at all.** The trace measures a relative
displacement between the payload and the hand frame; the hand is itself translating (~30 mm) while
the post-descent solver finishes the approach, and the descent's documented boundary shortfall
(every descent ends 40–90 mm short of the pick pose; the arm runs to its reachable boundary and
stays there) is a *known* end-of-leg transient on this cell. If the 32–55 mm walk is dominated by
that hand motion, then neither the close's arrival rate (C1) nor the hold-window lead moves it,
both arms read flat on the mechanism gate, and the design's honest output is the **K1 negative
plus a measured branch to the descent-boundary/scene family** (the AGENTS §2 item; D3-proper is
owner-gated). The design is built so that this failure is *cheap and informative*: the mechanism
gate stops the phase before the outcome battery, the two arms discriminate the freeze-state
hypothesis from the hold-window hypothesis, and the trace's own tooling produces the read.

A second, narrower fail mode (the pick's own prior): **C1 reproduces its stage-P trade on the
two-line** — the slow close lets the fruit ride the faces > 1 s and the never-grasped class grows
(0 → ≥ 2), i.e. the hold walk rises rather than falls. The design's K2 catches this at seed 11
before the outcome battery is spent.

---

## 6. The reads and reproduction (read-only; the design's provenance)

```bash
# the target (the trace's numbers; all committed)
sed -n '1,60p' logs/p14b/TRACE_RESULTS.md                 # §0 the answer + the master table
sed -n '276,370p' logs/p14b/TRACE_RESULTS.md              # §3.4 the mechanism / §3.5 the F1 test
sed -n '533,610p' logs/p14b/trace_p14b_tables.txt         # the per-attempt walk/dz/release table + §H
# the close/hold/probe code (the inventory's sites)
sed -n '1000,1030p;7410,7460p;7640,7675p;7860,7930p;8120,8185p;8560,8660p' src/fruit_sorting/tasks.py
# the R11-B record (C1's mechanism + the stage-P trade + the stopped stage N)
sed -n '1,60p;123,230p;314,410p' logs/r11/B_RESULTS.md
# the squeeze closure / the carry mechanism
sed -n '147,196p' logs/r6/B_RESULTS.md
# the class census and the levers (P10-E)
sed -n '170,335p' logs/p10e/NOGRASP_DIAGNOSIS.md
# the plow (the deeper-interference ejection prior)
grep -h "case=plow" logs/p11b/90_plow_fix_tomato.log logs/p11b/91_plow_fix_apple.log | grep -E 'outcome=(escaped|stayed)'
# the mass base (the scenario of record)
sed -n '1,42p' logs/p12a2/A2_RESULTS.md; sed -n '1,20p' logs/p14b/run_trace.sh
```

**What this lane did NOT do**: no simulator run, no `src/`/`scripts/`/`configs/`/`datasets/`/`Paper/`
edit, no default changed, no branch operation, no commit; all writes under `logs/p15/`.
