# P15 Stage-M screen results: M1 (`FRUIT_CLOSE_LOAD_RATE=0.04`) and M2 (`FRUIT_CLOSE_CONTACT_LEAD=0.10`) vs the on-disk traced control — the hold-walk read, the probe-1 departures, and the promotion verdict

Status: **offline, read-only analysis** (branch `p-supply`, 2026-10-19). The two screen runs were
executed by the P15 run lane (`logs/p15/run_screen.sh`, `logs/p15/90_driver.log`); this lane ran
**no simulator**, wrote nothing outside `logs/p15/`, and did not touch `src/`, `scripts/`,
`configs/`, `datasets/`, `Paper/`, or any default. Tree pins as read: `tasks.py`
`810658b802d22bbd63013726fc78af81`, `fruits.py` `d28546d26137d4540421caa7fa34a139`, `meshes.py`
`0e32b1ad1830b04dc0a4bddadfc84a5f` (identical to the design's pins — the runs and this read are on
the same tree).

Inputs: `logs/p15/10_m1_trace.log` + `logs/p15/traces_m1/` (M1, 20 files),
`logs/p15/11_m2_trace.log` + `logs/p15/traces_m2/` (M2, 20 files), both `SEED=11`, 20 attempts,
the mass-base two-line patch scenario verbatim (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_PHYSICS_REAL_MASS=1`, `FRUIT_DYNAMIC_TRACE=1`); the control is the on-disk traced run
`logs/p14b/10_seed11_trace.log` + `logs/p14b/traces_s11/` (`logs/p14b/TRACE_RESULTS.md` +
`master_table.md`). The metric implementation is `logs/p14b/trace_p14b_analysis.py` reused
verbatim; the R11-B close readouts are `logs/r11/b_readout.py`'s rules; the analysis is
`logs/p15/trace_p15_analysis.py` → `logs/p15/trace_p15_tables.txt` (this report's full tables).

Both runs completed cleanly: `[fruit] DONE`, 20/20 `[biarm] result` lines, `exit=0`
(13:23:38→13:31:48 and 13:32:08→13:40:30; Tier A solo via `scripts/154_claim_run.sh`); no wedge,
no timeout, no protocol interference (K5 clean). Trace files pair 1:1 with the results on all three
corpora (0 mismatches; the completion-counter pairing of `trace_p14b_analysis.py`).

---

## 0. The answer in one screen

* **The verdict: M2 (`FRUIT_CLOSE_CONTACT_LEAD=0.10`) passes the mechanism gate and is promoted to
  the outcome battery (SEED 11/5/23); M1 (`FRUIT_CLOSE_LOAD_RATE=0.04`) fails (a) and K2 fires.**
  M2's hold walk **collapses**: the ok band reads 0.0–0.2 mm (the control 0.0–12.8), the control's
  three hold-walk attempts' fruit read **0.0–2.5 mm** against the control's **31.9/38.1/54.8 mm**,
  the no-grasp count falls **7 → 4**, and the only residual walk is one 31.6 mm B1. Its actuation
  readout is the pre-registered one: the fruit's |v_y| at the close-end/hold is braked from
  **~97 to ~39 mm/s** (all attempts; per class: ok −54.5 → −29.5, carried −118.8 → −79.7,
  no-grasp −98.5 → −55.8 — the R11-B C2 direction). M1 reproduces the C1 stage-P trade on the
  two-line: the freeze moves later (true freeze tick median **20.5 → 47.0**, 3/20 never freeze),
  the no-grasp class **grows 7 → 12 (+5)** with **9/12 no-grasp attempts walking 27.8–85.8 mm**
  (walk speeds 0.073–0.224 m/s) — i.e. C1 **raises** the hold walk instead of lowering it, exactly
  K2's pre-registered prior.
* **The mechanism is movable, so K1 does not close.** The walk is (at least in part) a close/hold
  quantity: the hold-window lead collapses it, and the control's own B1 walks decompose (world
  frame) into the fruit's belt slide (relative y −50…−78 mm) plus the hand's own settling motion
  in x/z (10–35 mm). The named next of K1's closure (the descent-boundary/scene family) is **not**
  triggered; the next step is Stage P with M2.
* **The probe-1 first departures do not rise for either arm** (no-grasp: control 3/7, M1 2/12,
  M2 1/4; pooled control 4/8). But M1's first-departure class moves *earlier*: 10/12 no-grasp
  attempts are already >2 mm out at the probe's first sample (the W5-C "hold (walk pre-probe)"
  label) against the control's 2/7. M2's 4 no-grasp attempts depart in probe-1 1 / probe-2+ 1 /
  takeoff 1 / gap 1 — the later-phase shapes, not the hold-walk shape.
* **The honest bounds**: N = 1×20 per arm, one seed, one scenario/tree; the branch moved between
  the arms (different fruit picked — the cross-arm attempt pairing is by fruit identity, stated
  where used); the metric is a relative displacement, not a force decomposition; the outcome
  numbers are a single-sample census (the outcome battery is where the outcome question is
  answered).

---

## 1. The gate (stated explicitly from the design)

`logs/p15/CLOSE_HOLD_DESIGN.md` §4, "Promotion rule (M → P)":

> An arm is promoted iff **(a)** its no-grasp hold walk falls into/below the ok band (≤ 20 mm,
> inside the 12.8 → 31.9 gap) on ≥ 2 of the control's three hold-walk attempts, **or** the seed-11
> no-grasp count falls ≥ 2 with the hold-walk attempts converting; **and (b)** the probe-1
> departure count does not rise and the probe-1 dz does not worsen; **and (c)** no new failure
> reason and no never-grasped growth. If two arms qualify, promote the larger hold-walk movement
> (the tie to the stronger actuation read). If none qualifies, the phase closes at M.

The control's three hold-walk attempts (§1.1): **31.9 / 38.1 / 54.8 mm** — at SEED 11 those are
`[run]` attempt 1 (left orange, index 0), attempt 6 (left tomato, index 6) and attempt 8 (left
orange, index 0); the ok band is ≤ 12.8 mm (median 0.2, n=45 pooled). Kills: **K1** the mechanism
gate (no arm's hold walk moves in the predicted direction → close the phase, publish, do not spend
P; the named next is the descent-boundary/scene family); **K2** the never-grasped/no-grasp class
grows ≥ 2 at seed 11 or ≥ 2 pooled → negative, not adopted.

**The metric, as re-derived** (validated against `logs/p14b/master_table.md` on the control: all 20
hold walks, probe-1 dz and first departures reproduce to the printed digits): the hold walk = the
payload's hand-frame drift change across the hold segment, measured from the freeze (the last close
row; `trace_p14b_analysis.py` verbatim); the probe-1 first departure = the first post-freeze row
with drift > 2 mm, phase-bracketed, with the W5-C convention (a payload already out at the probe's
first sample is labelled "hold (walk pre-probe)"); the probe-1 dz = the fruit's z rise over the
first probe block (a grip test).

---

## 2. The corpus and the outcome census

| arm | env | ok | carried-not-placed | no-grasp | B1 | B2 | notes on failures |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **M0** control | shipped (on disk) | 11 | 2 | **7** | 4 | 3 | all no-grasp carry the baseline note (`fruit did not follow the gripper`); the 2 carried are note-free |
| **M1** C1 | `FRUIT_CLOSE_LOAD_RATE=0.04` | 7 | 1 | **12** | 11 | 1 | same note class only (24 note lines = 12 no-grasp × 2); no new reason |
| **M2** lead | `FRUIT_CLOSE_CONTACT_LEAD=0.10` | 12 | 4 | **4** | 2 | 2 | same note class only (8 note lines = 4 no-grasp × 2); no new reason |

Per-attempt spans are comparable (median 14.2–14.4 s; batch span 183.1–190.1 s), so the arms are
not a wall-clock artifact. The two new runs' `[fruit]` streams are their own branches (the knobs
move the timing, so the fruit picked differ from the control and from each other — the
cross-arm attempt pairing below is by fruit identity, stated where used).

The control's own numbers re-derive from its trace (`logs/p14b/traces_s11`): ok 11 / carried 2 /
no-grasp 7 (B1 4 + B2 3), the three hold-walk B1s 38.1/31.9/54.8 mm, the probe-1 departures 3/7
at seed 11 (4/8 pooled with s23's strawberry) — every number matches the p14b record.

---

## 3. Task 1 — the hold walk (the payload's hand-frame drift across the hold, from the freeze)

### 3.1 The distributions

| corpus | class | n | hold walk mm (min/med/max) | > 12.8 | > 20 | > 31.9 |
| --- | --- | --- | --- | --- | --- | --- |
| M0 | ok | 11 | −0.0 / 0.0 / 12.8 | 1 | 0 | 0 |
| M0 | carried | 2 | 2.6 / 4.2 / 5.8 | 0 | 0 | 0 |
| M0 | **B1** | 4 | 1.6 / **35.0** / **54.8** | 3 | 3 | 2 |
| M0 | B2 | 3 | 0.0 / 0.7 / 1.8 | 0 | 0 | 0 |
| M0 | **no-grasp (B1+B2)** | 7 | 0.0 / 1.8 / 54.8 | 3 | 3 | 2 |
| M0 | all | 20 | −0.0 / 0.8 / 54.8 | 4 | 3 | 2 |
| M1 | ok | 7 | 0.0 / 2.1 / 14.8 | 1 | 0 | 0 |
| M1 | carried | 1 | 5.5 | 0 | 0 | 0 |
| M1 | **B1** | 11 | −0.0 / **52.1** / **85.8** | **9** | **9** | **8** |
| M1 | B2 | 1 | 1.3 | 0 | 0 | 0 |
| M1 | **no-grasp (B1+B2)** | 12 | 0.0 / 50.1 / 85.8 | **9** | **9** | **8** |
| M1 | all | 20 | −0.0 / 12.2 / 85.8 | 10 | 9 | 8 |
| M2 | ok | 12 | −0.0 / **0.0** / **0.2** | **0** | 0 | 0 |
| M2 | carried | 4 | 0.0 / 3.2 / 4.1 | 0 | 0 | 0 |
| M2 | **B1** | 2 | 0.1 / 15.8 / **31.6** | 1 | 1 | 0 |
| M2 | B2 | 2 | 0.0 / 1.3 / 2.5 | 0 | 0 | 0 |
| M2 | **no-grasp (B1+B2)** | 4 | 0.0 / 1.3 / 31.6 | **1** | **1** | **0** |
| M2 | all | 20 | −0.0 / 0.0 / 31.6 | 1 | 1 | 0 |

**The change vs the control.** M2's walk collapses: the ok band's max falls 12.8 → 0.2 mm (0/12
attempts > 2 mm against the control's 2/11), the no-grasp class's median falls 1.8 → 1.3 with its
top 54.8 → 31.6, and 1 attempt (vs 3) sits in the gap zone > 20 mm. M1's walk **rises**: the B1
median 35.0 → 52.1, the max 54.8 → 85.8, 8 no-grasp attempts above the control's B1 floor
(31.9 mm), and 9/12 above the ok ceiling.

### 3.2 The control's three hold-walk attempts, tracked

The branch moved (different fruit picked per arm), so the honest tracking is by fruit + arm at the
same seed; the strict attempt-index reading is stated too.

| control attempt | fruit | control walk | M1 | M2 |
| --- | --- | --- | --- | --- |
| att 1 | left orange (index 0) | **38.1** | att 1 → **59.5** (B1); same fruit again att 5 4.3, att 8 55.2, att 12 52.1 | att 1 → **0.0** (**ok**); same fruit att 13 0.1 (B1), att 16 2.5 (B2) |
| att 6 | left tomato (index 6) | **31.9** | the branch moved (M1 att 6 = right peach); the left tomato index 6 was picked at att 7 → 0.8 (ok) | att 5 → 0.0 (carried), att 14 → 0.0 (B2) |
| att 8 | left orange (index 0) | **54.8** | att 8 → **55.2** (B1) | same fruit as att 1: 0.0–2.5 |

Readings: **M2 — every trackable instance of the control's hold-walk fruit reads 0.0–2.5 mm**
(3/3 by fruit identity; 1/3 strictly by attempt index, the other two attempts being different
fruit after the branch moved). **M1 — the two oranges' walks rise** (59.5/55.2 against 38.1/54.8),
the tomato instance reads 0.8 mm.

### 3.3 The walk speeds

Control B1 walkers: **0.083–0.143 m/s** (≈ belt speed 0.12; the design's 0.08–0.14 band ✓). M1
walkers: **0.073–0.224 m/s** (median ≈ 0.14; the top walkers exceed the belt speed, consistent
with the hand's own opposite-direction motion, §5). M2: one walker at 0.082 m/s (the 31.6 mm B1);
the ok class ≈ 0.000–0.001 m/s.

### 3.4 The actuation check for M1 (the freeze state entering the hold)

The primitive's own freeze lines (the true freeze tick; `[task] dynamic close: sustained contact
after N ticks`):

| corpus | freeze lines (of 20) | freeze tick min/med/max | ticks ≥ 40 | force at freeze (N) min/med/max | pathological (span < 0) |
| --- | --- | --- | --- | --- | --- |
| M0 | 20 | 16 / **20.5** / 38 | 0 | 3.81 / 4.38 / 5.92 | 0 |
| **M1** | **17** | 4 / **47.0** / 131 | **12** | 4.51 / 8.12 / **232.43** | **2** (232 N @ 4 ticks, 190 N @ 28 ticks) |
| M2 | 20 | 7 / 21.0 / 39 | 0 | 2.71 / 4.39 / 43.70 | 0 |

M1's actuation is confirmed on the two-line: the freeze moves later (median 20.5 → 47.0; the
R11-B direct-interface signature was 18.0 → 55.5), 3/20 attempts never detect sustained contact,
and the freeze force median doubles (4.38 → 8.12 N) with two flat-faced jam freezes (span < 0,
190–232 N). M2's freeze timing is unchanged (21.0 vs 20.5) — expected: the lead acts on the
close's load phase and the hold, not on the freeze criterion. The trace-side proxy (the
first commanded-gap stall) validates against the true lines (med 19.5/46.5/20.0 vs
20.5/47.0/21.0).

---

## 4. Task 2 — the probe-1 first departures (the 2 mm rule, phase-bracketed)

| corpus | class | n | hold (pre-probe) | probe-1 | probe-2+ | takeoff | gap | carry | none |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M0 | no-grasp | 7 | 2 | **3** | 0 | 1 | 1 | 0 | 0 |
| M0 | all | 20 | 2 | 7 | 1 | 1 | 3 | 0 | 6 |
| M1 | no-grasp | 12 | **10** | **2** | 0 | 0 | 0 | 0 | 0 |
| M1 | all | 20 | 10 | 5 | 0 | 0 | 0 | 0 | 5 |
| M2 | no-grasp | 4 | **0** | **1** | 1 | 1 | 1 | 0 | 0 |
| M2 | all | 20 | 1 | 3 | 2 | 1 | 1 | 1 | 11 |

The pooled control's pre-registered 4/8 = the s11 3/7 (a01 orange, a07 tomato, a13 tomato —
probe block 1) plus s23's strawberry. **Neither arm raises the probe-1 count** (no-grasp 3 → 2 for
M1, 3 → 1 for M2; all-attempt 7 → 5 / 7 → 3). But the *composition* moves: M1's first departures
move **earlier** — 10/12 no-grasp attempts are already out at the probe's first sample (the W5-C
"hold (walk pre-probe)" label; the walk consumed them during the hold), against the control's
2/7; M2's 4 no-grasp attempts depart in the later phases (probe-1 1, probe-2+ 1, takeoff 1, the
untraced gap 1) — the hold-walk shape is absent.

The probe-1 dz (the grip test): the no-grasp B1s' never-rise signature (−1.2…+0.9 mm on the
control) reads 0.0 mm for eight of M1's nine walkers (the ninth, the attempt-12 blow-up, reads a
garbage dz while the fruit flies off) and 0.0 for M2's B1 #18; the M2 ok class's low tail
*improves* (the class min moves 0.0 -> -1.4 mm (att 9, recovered via the re-seat; 6.1 mm is the one-block oks' min); the control's 5 ok attempts ≤ 2.5 mm — pooled —
recovered via the re-seat). Recorded, not gating at this n.

---

## 5. The K1 check — is the walk a close/hold quantity?

**K1 does not close: the walk is movable.** The design's K1: "the hold walk does not fall (or
rises) under either arm … if the walk is the hand's settling, no close/hold actuator moves it."
M2 moved it (the distributions and the tracked fruit above), so the walk is (at least in part) a
close/hold-chain quantity and the K1 closure's named next (the descent-boundary/scene family) is
not triggered.

The trace's own limit #6 still bounds the claim, and the world-frame decomposition (new here)
measures it: over the hold segment the relative walk decomposes into the fruit's own motion and
the hand's motion. On the control's B1s the dominant component is the **fruit's belt slide**
(relative y −50…−78 mm; e.g. a01: fruit dy −34.0 vs hand dy −0.8; a08: −46.1 vs +4.2) with a
secondary **hand settling** term in x/z (hand dx +22…+34 mm, dz −8…−10 mm) — so the walk is mostly
slip-along-the-belt with the hand still finishing the approach, and M2's collapse (relative
velocity ~0.0 mm/s through the whole hold; the fruit braked to ~−30 mm/s and followed exactly)
shows the arrest is achievable in the hold window. One caveat in the same read: M1's top walkers
add large hand-motion components (e.g. a18 (trace #19): hand dy +31.9 vs fruit dy −46.0; a04 (trace #5): hand dx −54.0,
dz −31.2) — under the rate-limited close the hand itself travels upstream/downstream while the
fruit rides, i.e. the late freeze leaves a transient the hold inherits.

---

## 6. Task 4 — the K2 check (the C1 late-freeze trade), per arm

| corpus | no-grasp census | R11-B "never held from the leg's first tick" signature (onset ≤ 3, force@onset = 0, contacts@onset = 0) | late freeze (tick ≥ 40) | freeze force > 15 N |
| --- | --- | --- | --- | --- |
| M0 | 7 | 3 | 0/20 | 0 |
| **M1** | **12 (+5)** | **5 (+2)** | **12/17** | 4 |
| M2 | 4 (−3) | 2 (−1) | 0/20 | 1 |

**K2 fires for M1.** The design's K2: "the slow close lets the fruit ride the faces > 1 s and
produces a *new* never-grasped class (the measured stage-P trade, 0 → 5) — i.e. C1 raises the
hold walk instead of lowering it." Measured on the two-line: the no-grasp class grows **7 → 12
(+5 ≥ 2)**, the never-held signature grows **3 → 5 (+2)**, 12/17 freezes are late (tick ≥ 40) with
the freeze force median doubled and two span-negative jam freezes, and the hold walk rises (9/12
no-grasp attempts walk 27.8–85.8 mm). The trace-side freeze row (the proxy) reads late (≥ 37) on 6
of the 12 no-grasp attempts, absent on 4 (no sustained contact / the commanded gap never stalls)
and early on 2 — the per-attempt freeze-line pairing is not resolvable on M1 (the second close
ramps break the depth match), so this correlate is stated at corpus level. The stage-P trade
reproduces on the two-line at this seed; **M1 is negative, not adopted**.

**K2 does not fire for M2**: the no-grasp class falls 7 → 4 (−3), the never-held signature falls
3 → 2, no new failure reason (all failure notes are the baseline pluck-lift note or empty), and
no late freeze. One fact recorded for Stage P: M2's **carried-not-placed rises 2 → 4** — not a
gate item (the carried class is a baseline failure class of this interface and the control shows
2), but the outcome battery must watch it.

---

## 7. Task 3 — the promotion verdict

**The gate arithmetic, item by item:**

| item | M1 (`FRUIT_CLOSE_LOAD_RATE=0.04`) | M2 (`FRUIT_CLOSE_CONTACT_LEAD=0.10`) |
| --- | --- | --- |
| (a) the hold walk ≤ 20 mm on ≥ 2 of the control's 3 hold-walk attempts, **or** the no-grasp count −2 with the hold-walk attempts converting | **FAIL** — the walk *rises* on the two oranges (59.5/55.2 vs 38.1/54.8); the count *rises* 7 → 12 | **PASS** — every trackable instance of the three attempts' fruit reads 0.0–2.5 mm (the orange converts at att 1; the tomato reads 0.0 but does not convert — carried/B2); the count falls 7 → 4 (−3) |
| (b) the probe-1 departures do not rise; the probe-1 dz does not worsen | count: PASS (3 → 2; all 7 → 5), but the class moves earlier (hold pre-probe 2 → 10); dz: PASS (no new never-rise) | **PASS** — 3 → 1 (all 7 → 3); dz not worsened (the ok class's low tail improves; the 4 residual no-grasp dz 0.0–11.0 recorded at n=4) |
| (c) no new failure reason; no never-grasped growth | FAIL — **K2 fires** (+5 census, +2 signature) | **PASS** — no new reason; the no-grasp class falls (the carried +2 recorded for Stage P) |
| **verdict** | **not promoted (K2)** | **PROMOTED → the outcome battery at SEED 11/5/23** |

**Promoted arm: M2 (`FRUIT_CLOSE_CONTACT_LEAD=0.10`).** Per the rule's tie clause it is the only
qualifying arm (the larger — the only — hold-walk movement). The promotion is to the **outcome
battery**: SEED 11/5/23, one run per seed, each with a bit-identical double (K3), reading the
no-grasp class (the P10-E B1/B2 rules), the falls (`lowest payload point` ≤ −1000 mm; partials
−100…−1000 reported separately), the carried-not-placed, the pooled outcome, and the mechanism
(the hold walk, the probe-1 departures, the freeze/shear actuation checks). The rate is not the
endpoint (the outcome is quantized; quote the class census and the per-leg motion).

**K1's closure is NOT the outcome**: the walk moved, so the phase does not close at M and the
descent-boundary/scene family is not the named next. The two hypotheses the screen was built to
discriminate resolve cleanly: the **hold-window arrest (the lead)** moves the walk; the
**freeze-state (C1)** moves the freeze but raises the walk and the class. One caveat to carry into
Stage P: the mechanism gate moved on a *moved branch*, and the outcome conversion at the attempt
level is partial (the orange converted at att 1 but failed at att 13/16; the tomato did not
convert) — Stage P's census is what settles the outcome.

---

## 8. The honest limits

1. **N = 1×20 per arm, one seed (11), one scenario/tree** (the mass-base two-line patch battery).
   The class counts are single-sample couplings of a deterministic branch; no rate is quoted and
   no cross-config delta is a rate. Stage M carries no doubles (K3 applies to Stage P).
2. **The branch moved between the arms.** The knobs change the close/hold timing, so the fruit
   picked differ (control/M1/M2 pick different mixes); the cross-arm tracking of "the control's
   three hold-walk attempts" is by fruit identity + arm (stated in §3.2), and the strict
   attempt-index reading is only 1/3 trackable. The within-run reads (the ok band, the
   ok-vs-fail separation, the actuation) survive a moved branch; the cross-run census does not.
3. **The metric is a displacement, not a force decomposition** (the trace's limit #6). The hold
   walk is the payload-vs-hand relative drift; the §5 world-frame decomposition attributes it, but
   the attribution is measured displacement, not a force split. The "actuation" readings (the
   freeze tick from the primitive's own lines, the fruit |v_y|) are direct measurements; their
   causal chain to the walk is inferred.
4. **The freeze-tick readout** uses the primitive's own freeze lines (20/17/20 for M0/M1/M2); the
   per-attempt trace-side freeze row is a proxy (the first commanded-gap stall) and validates
   against the true lines to ~1 tick (med 19.5/46.5/20.0 vs 20.5/47.0/21.0). Three M1 attempts
   never froze (no line).
5. **The K2 "never-grasped" signature is not zero-baseline on this scripted path** (the control
   shows 3): the primary K2 read is the design's own no-grasp census (7 → 12 / 7 → 4), the
   signature (3 → 5 / 3 → 2) is the secondary.
6. **One read is unmatched to the design's stage-P shape**: the R11-B stage-P was the single-arm
   scripted battery; this screen is the two-line patch battery. The comparison is the design's own
   pre-registration (same knobs, same scenario family), not a like-for-like transfer of the
   stage-P rate.
7. **No simulator run by this lane**; the two runs were executed by the P15 run lane (their
   drivers/logs are the provenance; `logs/p15/90_driver.log`). This lane wrote only under
   `logs/p15/`.

---

## 9. Reproduction and artifacts (all under `logs/p15/`)

```bash
python3 -B logs/p15/trace_p15_analysis.py > logs/p15/trace_p15_tables.txt   # the full tables
```

| file | what it is |
| --- | --- |
| `trace_p15_analysis.py` | the analysis (the p14b metric reused verbatim + the R11-B close readouts + the freeze lines + the shear/decomposition + the K2 signature) |
| `trace_p15_tables.txt` | the full output (the pairing, the per-attempt tables, the distributions, the probe-1 brackets, the actuation readouts, the K2 check, the census) |
| `SCREEN_RESULTS.md` | this report |
| `WORKLOG_entry_screen.md` | the WORKLOG entry |
| (inputs) `10_m1_trace.log` + `traces_m1/`, `11_m2_trace.log` + `traces_m2/` | the two screen runs (by the run lane; `run_screen.sh`, `90_driver.log`) |
| (inputs) `../p14b/10_seed11_trace.log` + `traces_s11/`, `../p14b/TRACE_RESULTS.md`, `../p14b/master_table.md` | the on-disk control |
| (design) `CLOSE_HOLD_DESIGN.md` | the pre-registration (the gate + the kills) |


## Amendments (2026-10-19, the Oracle gate's F4-F7; frozen before the outcome read)

- **F4 (the trace deviation)**: the outcome battery launched WITHOUT the trace env. The applied
  read: **the seed-11 mechanism comes from the byte-identical Stage-M M2 run** (the run-20
  `[fruit]` stream is 965/965 identical to `logs/p15/10_m1_trace.log`'s sibling M2 run); the
  freeze lines come from all runs' logs; the hold walk / probe-1 / shear read is available at
  **seed 11 only**.
- **F5 (the doubles)**: K3 is applied **at seed 11 only** (the scripted line's determinism is
  established across the project; the seed-11 double is the block's witness).
- **F6 (the falls convention)**: falls = the `lowest payload point` rows -1..-20 m, **blowups
  excluded**; report rows and attempts (one payload can emit two rows). At seed 11: the control
  3 falls + 1 partial (+1 blowup row) vs the M2 1 fall + 2 partials - a census, not a rate.
- **F7 (the adoption path, pre-registered before the read)**: a positive outcome branch means
  the **two-line-scoped default** (the `_dynamic_profile`/session-flag resolution - the knob is
  a bare `os.environ` read today and would otherwise move the shipped single-arm dynamic line)
  + the two-line reference re-record + the acceptance no-harm (the `logs/p12b2/C_DECISION.md`
  pattern). A mechanism-moved/outcome-flat read does NOT trigger the K1 next
  (descent-boundary/scene); the flat branch is: the M2 stays opt-in, the record published, and
  the next candidate is the **outcome-side residual** (the carried class 2 -> 4 the screen
  recorded) - or the decision is owner-gated.
