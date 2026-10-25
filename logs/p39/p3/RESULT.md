# P39 phase 3 — the measurement batch (C / S / F1)

2026-10-25, tree `e061d94` + the phase-2 working-tree diff, **uncommitted, no
`configs/` change, no `src/` edit** (`scene.py` **988985ef**, `tasks.py`
**112d2cb1**, `rl_env.py` **238e90a4**; `configs/motion_reference.json`
**25ade92b**, `configs/motion_reference_twoline.json` **181c9151** —
`tree_md5_before.txt`, re-checked in `tree_md5_after.txt`). Both knobs default
off. Pre-registration: `logs/p39/PREREG.md` + **A1** + **A2** (binding).

**Phase 4 (the Oracle gate-3 close-out, 2026-10-25) corrected this record and
made the one `configs/` change the phase-3 report had declined:** the two-line
reference was **re-recorded from `twoline_C.log`** (`181c9151` -> **d0326030**;
the pre-P39 file archived at
`logs/p39/motion_reference_twoline_pre_p39.json`, and `190` on `twoline_C.log`
now reads **PASS** - §10). The phase-3 measurements are unchanged; the
*readings* below are the corrected ones, with the withdrawal of §6's
hardware-clearance recommendation in `PREREG.md` **A3**.

Arms: **C** = both knobs unset; **S** = `FRUIT_FINGER_TIP_DELTA=0` (the
re-authored-AABB control); **F1** = `FRUIT_FINGER_TIP_DELTA=-0.004`.
Every battery is **one `154_claim_run.sh` claim** whose payload is a driver that
runs the arms **interleaved C -> S -> F1** inside that claim; the exact commands,
env, `SEED`, `ATTEMPTS` and `RUN_LIMIT` per battery are in `COMMANDS.md` and
repeated per battery below.

---

## 0. The one-screen verdict

**F-6 (batch validity): PASS.** C's pear battery is **345/345 physics lines
byte-identical** to `logs/p32/90_pear_battery_new.log`, and C's acceptance is
**374/374** identical to `logs/p32/D1_accept_pear.log`; the only differing rows
are the **two print-only `output belt` clearance message lines** (the documented
P32 phase-D read, AGENTS §2). C's acceptance also reads **6/10 +
`fingerprint: matches`**, i.e. the shipped 6/10 pear-on branch of record.
`C` is therefore the same-batch control it is supposed to be, and every
comparison below is against it (and S) inside this one tree.

**F1 vs S (the decision, A2.6): no evaluable class effect, and F1 is not a
self-identical arm.** The **primary battery (pear) is not evaluable**: the
left-attempt count is **S 2 vs F1 4** (A1.3's invariance condition fails), so the
class census is a snapshot only - and no arm improves in it (left
placed/composite: C **1/3**, S **0/2**, F1 **1/3**), with S's **n = 2** a
snapshot that fails to *show* a win rather than a result that overrides the
acceptance. The **acceptance is inadmissible for the arm** too (§1 (b)): C's
left takes **5** attempts and S/F1 take **6**, the left's fruit diverge from the
third left attempt, and **inside S** a kiwi of identical size and interference
(5.4 cm, grip-dia `+5.60` mm, close 22 ticks) **cnp's at attempt 3 and places at
attempt 9** - the per-slot class is not a stable function of the fruit, so **the
acceptance's 5/6 left is not evidence for the arm** (AGENTS §2). The
matched-count "no fall" statement (S 6, F1 6, census 5 placed / 1 cnp / 0
no-grasp both) therefore holds for **F1's mode A only**; mode B's left is
**1 placed / 3 cnp** (composite 3 against S's 1, §6). **F-1 is not adjudicable
on F1**: it is a byte-identity test, and an arm that is not self-identical cannot
run it, so the "contact-neutral" algebra is **neither confirmed nor refuted**
here. The pre-registered secondary band does **not** fall (pear left legs
> 0.34 m/s: S 4 -> F1 5; acceptance 3 -> 3), and there is **no new failure
reason** in any arm. The one legitimate residual belongs to the **mesh-to-box
step**: it moves the branch (S is single-mode here, so that is measured) **with
no evaluable class effect either way**.

**The belt-clearance claim is untested, not measured-zero (§3).** The `47`
probe never reaches a distal-plane seat: it is a **lateral jam** - against a pure
-0.35 m z command the jaw ends at `[0.210, -0.161, 1.229]` (C) /
`[0.183, -0.179, 1.207]` (S) / `[0.176, -0.181, 1.208]` (F1) from
`[0.341, 0.003, 1.262]`, i.e. **0.13-0.17 m of x** and **0.16-0.18 m of y**
displacement for only 0.03-0.06 m of z - and **C's hand ends 90 deg rotated**
against S/F1's (finger long axes along world X vs Y). `47` prints **no tool
axis**, so **N4 is not computable as registered**, and the `+1.00 mm` F1-vs-S
floor difference is a configuration outcome, not a tip-plane shift. **The box
itself is authored** - the build print reads long `84.9 -> 80.9 mm` and distal
`80.5 -> 76.5 mm` at `delta = -4 mm` - so the geometry change is proven and only
its **belt-clearance consequence** is unmeasured. If that bit is ever wanted,
the valid instrument is a **static-pose read of the authored collider prims**
(`S - F1` must differ by `4*cos(theta)`); nothing in this batch reads the distal
plane against the belt.

**F1 is bimodal on the acceptance scenario (§6).** Five same-configuration runs
land in two **bit-identical** modes - **348 filtered `[fruit]` lines / 8-of-9**
(x2) and **382 / 7-of-10** (x3) - whose first-attempt settle differs by **one
tick** (0.88 vs 0.87 s). C (3 pairs) and S (1) are single-mode here, so the
shipped line's per-configuration determinism is **not contradicted**; one
configuration is multi-modal run-to-run, so **its numbers are one draw** - and
**configuration vs harness is not separated**: the separators are more C/S
repeats (does the mode rate depend on the arm?) and a fixed-pose contact read
(does the mode come from contact geometry at all?).

**S vs C (the mesh-to-box step, reported not harm per A2.6): the AABB box is not
behaviourally equivalent to the shipped convex hull.**
Both batteries move their branch (acceptance `fingerprint: DIFFERS`, pear 9
attempts -> 10 with no starvation), the first divergence is the **pick-pose
read** (pear: settle 0.87 -> 0.88 s at an identical residual and jaw;
acceptance: residual 0.0431 -> 0.0437 m and jaw 0.2-1.1 mm), and the `47` probe
ends in a *different hand configuration* (C: finger long axes along world X;
S/F1: along Y) with a **-22.0 mm** jaw floor. The acceptance's left census reads
1 placed/3 cnp/1 no-grasp (C) against 5/1/0 (S and F1) - **not evidence for the
arm** (§1 (b), AGENTS §2); what the mesh-to-box step *does* establish is the
**branch move**, with no evaluable class effect either way.

**Nothing is adopted; no shipped default changed.** The two levers that remain
open are unchanged by this batch: F2 stays withheld/owner-gated (A1.7, A2.4) and
the authorized P30-C hardware form's 24-45 mm magnitude is not tested here.

---

## 1. Pear battery (PRIMARY)

```
# one claim; arms interleaved C -> S -> F1
RUN_LIMIT=5400 bash scripts/154_claim_run.sh logs/p39/p3/claim_pear.log \
    bash logs/p39/p3/run_pear.sh
# per arm:
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_SUPPLY_SPECIES=pear ATTEMPTS=10 SEED=5 \
    FRUIT_FINGER_TIP_DELTA=<0 | -0.004, omitted for C> \
    scripts/run.sh scripts/20_pick_place.py
```

| arm | attempts | starved slot | left attempts | left placed | left cnp | left no-grasp | left composite | right placed | `[stats]` |
|---|---|---|---|---|---|---|---|---|---|
| C | 9 | 7 | 4 | 1 | 3 | 0 | **3** | 5/5 | 6/9, 137.0 s sim, 15.2 s/attempt |
| S | 10 | none | 2 | 0 | 2 | 0 | **2** | 8/8 | 8/10, 151.6 s sim, 15.2 s/attempt |
| F1 | 10 | none | 4 | 1 | 3 | 0 | **3** | 6/6 | 7/10, 149.8 s sim, 15.0 s/attempt |

**F-6.** `filtered (A2.2)`: C **347**, S **382**, F1 **380**; raw = filtered in
every arm (0 `[attitude]`, 0 build-print rows; the build print is a plain
`[p39]` row, A2.2).

```
python3 logs/p39/p3/filter_stream.py --diff logs/p39/p3/pear_C.log logs/p32/90_pear_battery_new.log
  -> DIFFERENT: 2 lines, both `output belt P (0)` / `output belt N (1)` clearance messages
python3 logs/p39/p3/filter_stream.py --diff --drop-belt logs/p39/p3/pear_C.log logs/p32/90_pear_battery_new.log
  -> IDENTICAL: 345/345   <-- F-6
```

The two differing rows are print-only: the P32-era text says
`tallest fruit by 0.060 m` and this tree's carries the added stem-bound clause
(the Gate-B R5/R6 read AGENTS §2 records for the `93`/`D1` pair). No physics row
differs.

**Per-attempt (the parser in `logs/p39/left_corpus.py`; full tables in
`P3_report.txt`):**

| arm | # | side | fruit | dia cm | grip-dia mm | close F N | close t | lift | in-hand lift | in-hand place | clear(place) | class |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C | 1 | left | pear A | 6.1 | -1.20 | 4.62 | 20 | +0.214 | 1.108 | 0.452 | -217 output rail | cnp |
| C | 4 | left | pear A | 6.0 | -1.20 | 4.05 | 20 | +0.074 | 1.416 | 0.448 | -217 output rail | cnp |
| C | 5 | left | pear A | 5.9 | -1.20 | 4.25 | 17 | +0.156 | 1.964 | 0.447 | -217 output rail | cnp |
| C | 6 | left | pear A | 6.1 | -1.20 | 4.51 | 22 | +0.287 | 0.228 | 0.077 | +24 output rail | placed |
| S | 1 | left | pear A | 6.1 | -1.20 | 6.41 | 20 | +0.222 | 1.107 | 0.449 | -217 output rail | cnp |
| S | 6 | left | pear A | 6.1 | -1.20 | 4.62 | 18 | +0.052 | 1.182 | 0.449 | -217 output rail | cnp |
| F1 | 1 | left | pear A | 6.1 | -2.50 | 6.47 | 25 | +0.219 | 1.534 | 0.450 | -218 output rail | cnp |
| F1 | 6 | left | pear A | 7.0 | -1.50 | 4.57 | 20 | +0.282 | 0.146 | 2.050 | -15 main belt | cnp |
| F1 | 7 | left | pear A | 6.7 | -1.40 | 4.49 | 17 | +0.282 | 0.153 | 0.172 | +28 output rail | placed |
| F1 | 9 | left | pear A | 6.2 | -1.30 | 5.54 | 23 | +0.218 | 1.095 | 0.452 | -217 output rail | cnp |

Motion budgets (F-5): **all three arms PASS** the descent speed/lurch budgets
(`105_motion_regression.py --min-success-rate 0`: worst `|v|max` **0.1100** m/s
against 0.160-0.161, lurch **0.017** against 0.291; the carry cone is reported,
1.19x/1.21x/1.20x).

**Verdict fields (a)-(d) on the primary.**

* **(a) left-attempt count invariant S vs F1? NO — S 2, F1 4.** The verdict is
  not evaluable (A1.3/A2.6). The arms share attempts 0-5 fruit-for-fruit (pear C
  5.9 / pear A 6.1 / pear C 5.9 / pear B 6.2 / pear C 6.0 / pear B 6.1) and then
  diverge at attempt 6, where S takes pear A **6.1 cm** and F1 pear A **7.0 cm**.
  The named mechanism is attempt 1's differing close (S 20 ticks / grip-dia
  -1.20 mm vs F1 25 / -2.50) leaving the escaped pear in a different place on an
  absolute-schedule feed; that the attempt-6 change follows from it is
  **inferred** from the shared prefix, not measured.
* **(b) does F1's left composite fall / does `placed` rise by at least the
  fall?** Not evaluable on the primary (different attempt counts: composite
  S 2/2 vs F1 3/4, placed 0 vs 1). The pear battery shows **no arm improving**
  (left placed/composite: C 1/3, S 0/2, F1 1/3) - but S's **n = 2** is a
  snapshot that fails to *show* a win, not a result that overrides the
  acceptance. **The acceptance is not admissible for the arm either**: C's left
  takes **5** attempts and S/F1 take **6**, and the left's fruit diverge from
  the third left attempt - C `peach 6.5 / peach 6.9 / kiwi 5.6 / orange 6.4 /
  lychee 3.0` against S and F1 `peach 6.5 / peach 6.9 / kiwi 5.4 / tomato 6.6 /
  tomato 6.2` plus a sixth (S a second **5.4 cm kiwi**, F1 an **orange 6.4**) -
  and **inside S** a kiwi of identical size and interference (5.4 cm, grip-dia
  `+5.60` mm, close 22 ticks) **cnp's at attempt 3 and places at attempt 9**, so
  the per-slot class is not a stable function of the fruit and the acceptance's
  5/6 left is **not evidence for the arm** (AGENTS §2). What the acceptance
  *does* carry is the **matched-count "no fall"** statement (S 6 / F1 6, census
  5 placed / 1 cnp / 0 no-grasp both), and it holds for **F1's mode A only**
  (§6) - mode B's left is 1 placed / 3 cnp, composite 3 against S's 1. The
  legitimate residual is the **mesh-to-box step**: it moves the branch (S is
  single-mode, so that is measured) with **no evaluable class effect either
  way**.
* **(c) new failure reason vs C?** **None in any arm.** The pear-battery note
  sets are empty in C, S and F1. The acceptance's only note is C's own
  `fruit did not follow the gripper`; S and F1 carry none, so nothing is new.
* **(d) the secondary band — left carry legs with in-hand `|v|max` > 0.34 m/s:**

  | battery | C | S | F1 | bar (fall >= 2 vs S) |
  |---|---|---|---|---|
  | pear (lift + place) | 6 (3+3) | **4 (2+2)** | **5 (2+3)** | not met (it rises by 1) |
  | acceptance | 7 (4+3) | **3 (2+1)** | **3 (2+1)** | not met (flat) |

  The band does not fall; the arms' counts are dominated by which attempts the
  branch gives the left at all.

---

## 2. Acceptance (report + N1)

```
RUN_LIMIT=5400 bash scripts/154_claim_run.sh logs/p39/p3/claim_accept.log \
    bash logs/p39/p3/run_accept.sh
# per arm:
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p39/p3/accept_<arm>.log \
    FRUIT_FINGER_TIP_DELTA=<0 | -0.004, omitted for C> scripts/accept.sh
#   (accept.sh supplies HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10, SEED default 5)
```

| arm | placed | starved slot | left attempts | left census (p/cnp/ng) | right placed | `[fruit]` raw/filtered | gate | fingerprint |
|---|---|---|---|---|---|---|---|---|
| C | **6/10** | none | 5 | 1 / 3 / 1 | 5/5 | 376 / **376** | worst `\|v\|max` 0.110, lurch 0.017 — **budgets PASS**; FAILs the 75 % rate floor only | **matches** `configs/motion_reference.json` |
| S | **8/9** | 2 | 6 | 5 / 1 / 0 | 3/3 | 347 / **347** | budgets PASS | **DIFFERS** |
| F1 | **8/9** | 2 | 6 | 5 / 1 / 0 | 3/3 | 348 / **348** | budgets PASS | **DIFFERS** |

* **N1 margin:** F1 placed **8** >= C 6 - 1 = **5** -> **PASS** (and 89 % clears
  the 75 % dynamic floor) - **in F1's mode A**; mode B reads 7/10, also above the
  bar (>= 6 - 1). Same for S.
* **N2 (right lane non-inferior):** pear 5/5, 8/8, 6/6; acceptance 5/5, 3/3, 3/3
  -> non-inferior in both batteries, every arm.
* **F-6 on the acceptance:** C is **374/374** identical to
  `logs/p32/D1_accept_pear.log` once the two print-only `output belt` rows are
  dropped (376 `[fruit]` lines each).
* The fingerprint DIFFERS for S **and** F1. For **S** (single-mode) that reads as
  the box step moving the branch (A2.6); for **F1** it is **not attributable** -
  the arm is bimodal, so its divergence may be the box, the 4 mm or the mode
  (§6), and the two modes differ in their own filtered counts (348 vs 382).

---

## 3. The `47` probe (N4 / N4b) - the probe jams, so the clearance claim is untested

```
RUN_LIMIT=2400 bash scripts/154_claim_run.sh logs/p39/p3/claim_probe47.log \
    bash logs/p39/p3/run_probe47.sh
# per arm:
HEADLESS=1 FRUIT_FINGER_TIP_DELTA=<0 | -0.004, omitted for C> \
    scripts/run.sh scripts/47_robot_collision.py
```

| arm | jaw end (m) | displacement x / y (m) | jaw floor z (m) | left finger AABB z | right finger AABB z | finger long axis | sep (m) |
|---|---|---|---|---|---|---|---|
| C | [0.210, -0.161, 1.229] | **-0.131 / -0.164** | **1.2290** | 1.2070-1.2873 | 1.1833-1.2637 | **along world X** | 0.0980 |
| S | [0.183, -0.179, 1.207] | **-0.158 / -0.182** | **1.2070** | 1.1810-1.2456 | 1.1688-1.2334 | along world Y | 0.0980 |
| F1 | [0.176, -0.181, 1.208] | **-0.165 / -0.184** | **1.2080** | 1.1818-1.2463 | 1.1690-1.2335 | along world Y | 0.0973 |

The command is a **pure -0.35 m z drive** (`start jaw [0.341, 0.003, 1.262]`,
`target [0.341, 0.003, 0.912]`, belt top 1.170), so what the probe measures is a
**lateral jam, not a descent onto the belt**: every arm ends 0.13-0.17 m
displaced in x and 0.16-0.18 m in y with only 0.03-0.06 m of z travel, and C
ends in a **different hand configuration** (its finger boxes are 8.1 cm wide in
x and 9.3 cm in y; S/F1 are the transpose) - the "floor" is a configuration
outcome, not a distal-plane seat.

The probe's own `parts=` line reads
`('environment', 'pedestal', 'robot', 'conveyor')` in all three runs - the
conveyor is **on**, as N4 requires (the no-conveyor control is `FRUIT_PARTS`).

* **N4 is not computable as registered, and its number is not a tip-plane
  read.** `47` prints **no tool axis** (A1.4 asked for the tilt to be reported),
  so `delta*cos(theta)` cannot be evaluated at all; and the `+1.00 mm` F1-vs-S
  jaw-floor difference is the separation of two differently-rotated jam
  configurations, not a shift of a distal plane.
* **N4b's -22.0 mm is the same rotation**, not an unauthored box: the re-author
  is proven by the **build print** - long `84.9 -> 80.9 mm`, distal
  `80.5 -> 76.5 mm` at `delta = -4 mm` (`p2/b2_delta0_final.log` vs
  `p2/c_delta-4mm_attitude.log`).
* **The finger-link AABB column is not an independent read.** That bound is the
  union of the link's **visual mesh** and the **authored box**, so it bounds the
  pair rather than the authored distal plane; it is reported for provenance
  only.
* **Reading: the belt-clearance claim is untested (no valid distal-plane
  instrument), not measured-zero.** N5's consequence stands in effect - no
  clearance claim, no grip claim, no adoption - but its *reason* changes: not
  "the distal plane is not the contacting part" (that is **unmeasured**, not
  measured false) but "the instrument never reaches the distal plane". If the
  bit is ever wanted, the valid instrument is a **static-pose read of the
  authored collider prims** (`S - F1` must differ by `4*cos(theta)`), with no
  attempt loop and no jam.

---

## 4. Mechanism batch (A2.7)

```
RUN_LIMIT=5400 bash scripts/154_claim_run.sh logs/p39/p3/claim_mech.log \
    bash logs/p39/p3/run_mech.sh
# per arm:
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_ATTITUDE=1 ATTEMPTS=10 SEED=5 \
    FRUIT_FINGER_TIP_DELTA=<0 | -0.004, omitted for C> \
    scripts/run.sh scripts/20_pick_place.py
```

`[attitude]` rows: C 19, S 18, F1 20; raw/filtered = 395/**376**, 365/**347**,
402/**382**.

Census here (the acceptance scenario, print on): C left 5 = **1 / 3 / 1**
(placed/cnp/no-grasp), right 5/5; S left 6 = **5 / 1 / 0**, right 3/3; F1 left
4 = **1 / 3 / 0**, right 6/6. C and S reproduce their print-off censuses
exactly; **F1's print-on census is mode B** (§6), not the `accept_F1` mode A
census — the print is not the selector, the arm's own bimodality is.

**Print neutrality (measured).** C **376/376** and S **347/347** filtered
identical to their print-off acceptance runs; F1's print-on run equals its
print-off repeat **382/382** (§6). So the print is run-neutral in all three arms.

| arm | side/leg | n | tilt (deg) | dz (mm, model-free) | lip (mm, model-derived) | rows with dz > 100 mm (payload gone) |
|---|---|---|---|---|---|---|
| C | left grasp_lift | 5 | 25.9-29.7 | +58.6 .. +1516.8 | -1445.6 .. +13.6 | 3 |
| C | left place0 | 4 | 80.7-95.8 | -8.8 .. +319.4 | -325.5 .. +0.6 | 3 |
| C | right grasp_lift | 5 | 34.0-52.2 | +40.8 .. +55.8 | +8.0 .. +13.7 | 0 |
| C | right place1 | 5 | 87.2-95.4 | -5.3 .. +4.8 | -2.3 .. +1.2 | 0 |
| S | left grasp_lift | 6 | 25.6-31.0 | +51.3 .. +364.2 | -291.8 .. +19.7 | 1 |
| S | left place0 | 6 | 89.4-96.4 | -21.5 .. +319.9 | -328.7 .. +17.8 | 1 |
| S | right grasp_lift | 3 | 38.0-53.9 | +39.6 .. +52.7 | +7.9 .. +10.8 | 0 |
| S | right place1 | 3 | 95.5-97.3 | -6.5 .. -5.6 | -4.6 .. -2.0 | 0 |
| F1 | left grasp_lift | 4 | 26.6-31.6 | +51.0 .. +384.5 | -316.7 .. +14.2 | 3 |
| F1 | left place0 | 4 | 77.6-96.2 | -17.5 .. +316.1 | -317.7 .. +9.2 | 3 |
| F1 | right grasp_lift | 6 | 30.9-49.2 | +43.5 .. +56.7 | +6.3 .. +9.0 | 0 |
| F1 | right place1 | 6 | 87.3-94.8 | -5.4 .. +4.5 | -1.7 .. +0.8 | 0 |

* **Tilt / tool axis:** the left's lift legs sit at **25.6-31.6 deg** in every
  arm, the right's at **30.9-53.9 deg**; the tool-axis components are the same
  family in all three arms (`left ~(+0.29,-0.33,-0.89)`, `right
  ~(+0.72,-0.00,-0.69)`), i.e. the delta does not change the wrist attitude the
  arm achieves.
* **Lips:** `lip` carries `tip = 80.5 + delta` (A2.3), so S's and F1's lips are
  **not comparable as measured** — the 3.4 mm gap at equal tilt is the model.
  The model-free pair is `dz` at equal tilt: S attempt 0 left grasp_lift
  **+51.3 mm** (tilt 31.0), F1 attempt 0 +51.0 mm (tilt 31.6) — **0.3 mm**.
  **`dz` is a pad-fruit contact height** (pad centre minus fruit centre), so it
  is insensitive **by construction** to a shorter distal extent: the 0.3 mm says
  the *aim* did not move, not that the plate's distal plane did not. It is not a
  `delta`-footprint read.
* **The escape signature** is identical in all three arms: the left's cnp legs
  are already out of the grip at the leg's end (`dz` **+300..+1517 mm**, i.e. the
  payload is on the belt), the right never is (`dz` +40..+57 on the lift,
  -6.5..+4.8 on the place). The left's *held* lifts achieve the larger lip.
* **Corner drops** (`16.65*sin tilt` / `30.5*sin tilt`): 7.3-13.2 / 13.3-24.6 mm
  on the lifts — larger than the whole 4 mm budget, the A2.3/A2.4 reading.

---

## 5. Two-line gate (N3)

```
RUN_LIMIT=5400 bash scripts/154_claim_run.sh logs/p39/p3/claim_twoline.log \
    bash logs/p39/p3/run_twoline.sh C S F1
# per arm:
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_BIARM=1 \
    FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10 SEED=5 \
    FRUIT_FINGER_TIP_DELTA=<arm> scripts/run.sh scripts/20_pick_place.py
bash scripts/190_twoline_gate.sh logs/p39/p3/twoline_{C,S,F1}.log   # -> twoline_gate.txt
```

The two-line census below comes from the log's own `[biarm] result ...` rows and the
scheduler's final `[biarm] ... per arm left=/right=` line, **not** from
`left_corpus.py` (the two-line scheduler does not print the single-arm
`[run] attempt` format that parser reads).

**Deviation (A2.7).** The battery was **not shortened**: S and F1 both moved
their pear/acceptance streams, and C was kept because N3's identity prediction
needs the same-batch control. That is a deviation from "only the arms that
moved" in the direction of *more* evidence, recorded here as A2.7 requires.

| arm | filtered `[fruit]` | placed | per arm (left/right) | diverted | span | `190` |
|---|---|---|---|---|---|---|
| C | 427 | **6/10** | 3/5 + 3/5 | 0 | 90.2 s, 9.0 s/attempt | **FAIL** (fingerprint; **PASS** after the phase-4 re-record, §10) |
| S | 437 | **5/10** | 3/5 + 2/5 | 1 | 90.2 s, 9.0 s/attempt | **FAIL** (fingerprint + 50 % < 60 % floor) |
| F1 | 419 | **6/10** | 3/5 + 3/5 | 1 | 88.2 s, 8.8 s/attempt | **FAIL** (fingerprint) |

**At the time of the phase-3 batch N3 failed for every arm including C, and the
reason was not the finger - the reference was stale.** *Phase 4 re-recorded it:
the shipped reference is now `d0326030` from this very `twoline_C.log`, and `190`
on C reads **PASS** (§10). The history below is the phase-3 read and stands as
the reason the old file was unusable; N3's byte-identity prediction itself stays
**untestable for F1 and S** (their streams are not byte-identical to C's - 437
and 419 filtered lines against 427 - and, for F1, an arm that is not
self-identical cannot be submitted to a byte-identity test at all, §6).*

```
python3 logs/p39/p3/filter_stream.py --diff --drop-belt logs/p39/p3/twoline_C.log logs/w7/10_dense_twoline_1.log
  -> DIFFERENT: 425 vs 440; first difference
     A: [task] target peach (grade B, 6.9 cm) with right arm
     B: [task] target pear  (grade B, 6.8 cm) with right arm
```

The two-line scenario of record (`configs/motion_reference_twoline.json`,
181c9151, W7-A) **cannot be reproduced on this tree with both knobs unset**: the
supply's species stream differs at the *first* attempt (peach vs pear). That is
the P32 pear's per-instance RNG-draw change (AGENTS §2), not a finger effect, so
the 190 verdict is a **stale-reference** verdict for C as well and N3's
byte-identity prediction is **untestable on this tree**. The in-batch read:

* C -> S first difference is the same **pick-pose read** class as the single-arm
  step (line 60: residual 0.0421 vs 0.0419, jaw 0.3/1.1 mm), i.e. the box
  reaches the two-line path too;
* F1 -> C/S first difference is **line 48**, a **2 mm along-belt offset of the
  same fruit instance** at the first wait read (`fruit_y=0.4715` vs `0.4695`,
  x and z identical) — before any grasp. The knob reaches only the collider
  authoring and the `[attitude]` print (verified: `grep -rn
  FRUIT_FINGER_TIP_DELTA src/fruit_sorting/` -> `scene.py` + `tasks.py:2770`,
  the print), so this is a supply-cadence/settle effect, **mechanism not
  identified**;
* no new failure reason in any arm (the only note anywhere is
  `fruit did not follow the gripper`); motion budgets pass in all three
  (worst `|v|max` 0.110-0.111, lurch 0.019).

---

## 6. Determinism check (added; not a registered battery)

PREREG §3 makes the second run of an arm a **determinism check**. C and S each
reproduced bit-identically on every same-configuration pair available:

| arm | same-config pairs | result |
|---|---|---|
| C | `accept_C` vs `mech_C`; `accept_C` vs `logs/p32/D1_accept_pear.log`; `pear_C` vs `logs/p32/90_pear_battery_new.log` | **376/376, 374/374, 345/345** identical |
| S | `accept_S` vs `mech_S` | **347/347** identical |
| F1 | `accept_F1` vs `claim_f1_repeat` | **DIFFERENT** (348 vs 382) |

Two extra F1 repeats (`RUN_LIMIT=2400 ... run_f1_det.sh`, print off, identical
env) settle it — **F1 is bimodal, each mode bit-identical:**

| mode | lines | outcome | first-attempt pick pose | runs |
|---|---|---|---|---|
| **A** | **348** | 8/9 | settle 0.88 s, residual 0.0431 m | `accept_F1`, `f1_repeat2` (348/348 identical) |
| **B** | **382** | 7/10 | settle 0.87 s, residual 0.0432 m | `claim_f1_repeat`, `mech_F1`, `f1_repeat3` (382/382 identical) |

The same read in the other arms: C `0.87 s / 0.0431`, S `0.87 s / 0.0437`. F1
mode B is therefore *between* them in residual, so the mode is **not** a simple
function of the residual and the selector is not identified; what is measured is
that F1's settle lands one tick later (0.88 s = ~1.2 ticks at 120 Hz) in mode A, and that one tick decides the whole branch. The
`[attitude]` print is **not** the selector (mode B contains both a print-on and
two print-off runs). Consequence: **the pear-battery F1 row is one draw of a
bimodal arm** — a repeat may land in the other mode — while C and S are
single-mode on this tree (C 3 same-config pairs, S 1; F1 1 of 2 pairs differs).
The mode also moves the acceptance census (mode A: left 6, 5 placed/1 cnp; mode
B: left 4, 1 placed/3 cnp), so an F1 acceptance number is only meaningful with
its mode.

**Configuration vs harness is not separated.** C (3 pairs) and S (1) are
single-mode *on this tree*; F1 is not. Nothing in this batch says whether the
mode is a property of the arm's authored geometry or of the harness (a settle
tick, a step/render race) - the registered separators are (i) **more C/S
repeats** (does a single-mode arm ever flip, and at what rate?) and (ii) a
**fixed-pose contact read** (author the pose, read the pad/fruit contact with no
attempt loop). Until one of them runs, the honest statement is: one
configuration is multi-modal run-to-run, **its numbers are one draw**, and the
shipped line's per-configuration determinism is **not contradicted** (C and S
each reproduced bit-identically on every available same-configuration pair).

**F-1 is not adjudicable on F1.** The falsifier is a byte-identity test ("F1's
`[fruit]` stream is not byte-identical to C although `delta = -4 mm` is inside
the free bound"), and an arm that is **not self-identical** cannot run it: F1's
two modes differ by 34 filtered lines before any lever is considered. So the
"contact-neutral" algebra is **neither confirmed nor refuted** by this batch - it
is **untested** - and the "no fall" census agreement with S holds for **mode A
only** (mode B: left 1 placed / 3 cnp, composite 3 against S's 1).

---

## 7. What could not be run, and why

* **N3's byte-identity prediction** (§5): the **W7-A** reference scenario no
  longer exists on this tree (peach vs pear at attempt 0 with both knobs unset),
  so the prediction is untestable *as registered* and §5 reports the in-batch
  comparison instead. **Phase 4 did the re-record** (`d0326030` from
  `twoline_C.log`; the W7-A `181c9151` archived at
  `logs/p39/motion_reference_twoline_pre_p39.json`; `190` PASS on C) - §10. That
  certifies the **shipped-tree C branch**, not the W7-A one.
* **N4 in its registered form** (§3): `47` prints no tool axis, so
  `delta*cos(theta)` cannot be evaluated - and the probe jams laterally (0.13-
  0.17 m of x displacement for 0.03-0.06 m of z), so **no jaw-floor number from
  it is a distal-plane read**. The belt-clearance claim stays **untested**.
* **The pear battery's class verdict** (§1): not evaluable (left-attempt count
  2 vs 4). No snapshot was promoted to a verdict.
* **F2 / W**: not run — W is withdrawn by A1.1 (a code fact) and F2 is
  owner-gated (A1.7, A2.4).
* **`configs/`, `src/`, commits**: untouched, as instructed.

## 8. Wall time

| battery | claim window | per-arm wall |
|---|---|---|
| pear | 21:07:32 -> 21:19:57 (744 s) | 243 / 253 / 249 s |
| acceptance | 21:23:29 -> 21:35:42 (733 s) | 266 / 234 / 233 s |
| `47` probe | 21:40:00 -> 21:41:11 (71 s) | 22 / 25 / 24 s |
| mechanism | 21:43:30 -> 21:56:05 (755 s) | 266 / 234 / 255 s |
| two-line | 22:01:51 -> 22:14:19 (748 s) | 261 / 246 / 241 s |
| F1 determinism (added) | 22:17:45 -> 22:33:03 (743 s) | 255 / 234 / 254 s |

**Simulator wall 63.2 min in claims, 86.4 min start-to-finish** (21:06:40 ->
22:33:03). No claim wedged; no overlap abort; one claim (the first pear launch)
was relaunched after a driver path bug that never started the simulator, and one
driver (`run_f1_det.sh`) was relaunched after a shell quoting bug — both are
recorded here, neither consumed simulator time.

## 9. Evidence index

| file | what |
|---|---|
| `claim_pear.log`, `claim_accept.log`, `claim_probe47.log`, `claim_mech.log`, `claim_twoline.log` | the claim windows + per-arm wall |
| `pear_{C,S,F1}.log`, `accept_{C,S,F1}.log`, `probe47_{C,S,F1}.log`, `mech_{C,S,F1}.log`, `twoline_{C,S,F1}.log` | the runs |
| `claim_f1_repeat.log`, `f1_repeat2.log`, `f1_repeat3.log`, `claim_f1_det.log` | the determinism check (§6) |
| `P3_report.txt` | `p3_report.py` on all five batteries (tables + verdict fields) |
| `twoline_gate.txt` | the `190` output (phase 3, against the stale reference) |
| `twoline_gate_after.txt` | the `190` output after the phase-4 re-record (`PASS` on C) |
| `../motion_reference_twoline_pre_p39.json` | the archived W7-A reference (`181c9151`) |
| `filter_stream.py` | the A2.2 filter + the filtered identity test |
| `p3_report.py` | the per-arm/per-battery report (parser = `logs/p39/left_corpus.py`) |
| `run_*.sh`, `COMMANDS.md` | the drivers and the exact commands |
| `tree_md5_before.txt`, `tree_md5_after.txt` | the tree pins before/after |

---

## 10. Phase 4 - the Oracle gate-3 close-out (2026-10-25)

The gate returned **ACCEPT THE CLOSE** with text corrections. This section is
the record of what changed; §§0-7 above already carry the corrected readings.

**10.1 The corrections.**

1. **The acceptance's 5/6 left is not evidence for the arm** (replaces the
   earlier "matched-count, no fall" reading and any fruit-mix attribution): C's
   left takes 5 attempts and S/F1 take 6, the left's fruit diverge from the third
   left attempt (C `peach/peach/kiwi 5.6/orange/lychee` vs S,F1
   `peach/peach/kiwi 5.4/tomato/tomato/...`), and inside S the same 5.4 cm kiwi
   at the same read interference cnp's at attempt 3 and places at attempt 9 - so
   the acceptance cannot adjudicate the arm (AGENTS §2). The species-locked pear
   battery shows no arm improving (C 1/3, S 0/2, F1 1/3), with S's n=2 a
   snapshot. The **retained residual** is the mesh-to-box step: it moves the
   branch (S is single-mode, so that is measured) with **no evaluable class
   effect either way**.
2. **F1's bimodality is stated as measured** (§0, §6) with configuration-vs-
   harness **not separated** and the two separators named; the "matched-count,
   no fall" statement is scoped to **mode A**; and **F-1 is declared not
   adjudicable on F1** (an arm that is not self-identical cannot run a
   byte-identity test), so the contact-neutral algebra is **not** recorded as
   confirmed.
3. **The `47` probe's clearance bit is withdrawn to "untested"** (§3): the probe
   is a lateral jam, `47` prints no tool axis, the `<= 1 mm` "footprint" reading
   and the "AABB bottoms are a second independent read" sentence are **deleted**
   (the first is a pad-fruit contact height, insensitive by construction to a
   shorter distal extent; the second is the union of the visual mesh and the
   authored box). What is recorded instead: the **box is authored** (build
   print: long 84.9 -> 80.9 mm, distal 80.5 -> 76.5 mm at `delta = -4 mm`), and
   the valid instrument, if the bit is ever wanted, is a static-pose read of the
   authored collider prims (`S - F1` must differ by `4*cos(theta)`).
4. **Two deviations are registered** (§10.2).

**10.2 The deviations.**

* **The pear primary is N = 1 per arm.** PREREG §3 asks N = 2 runs per arm; the
  pear battery has one run per arm and **no determinism pair** exists for it, so
  its census is a single draw on top of the count mismatch. (The acceptance's
  second runs exist and are the §6 pairs; the pear ones do not.)
* **The `47` probe's lateral deflection.** The probe was registered as a
  straight descent (`-0.35 m` in z) that would seat the distal plane on the
  belt; it instead translates 0.13-0.17 m in x and 0.16-0.18 m in y. That is a
  **probe failure**, not a lever result, and it is why N4/N4b are reported as
  uncomputable rather than as a failed shift.

**10.3 Amendment A3 - the §6 hardware-clearance recommendation is withdrawn.**
Appended to `PREREG.md` as **A3**: §6 called L1-F1 "still adoptable as a
hardware/clearance change" on a null class verdict. With the clearance claim
untested, that sentence is withdrawn; F1 has **no** adoptable form on this
evidence.

**10.4 The two-line reference: archive + re-record.** The shipped
`configs/motion_reference_twoline.json` (`181c9151`) is a **pre-pear W7-A
record** that no post-P32 tree can reproduce (the first physics difference is
`target peach` vs `target pear` at attempt 0, §5). Phase 4 archived it to
`logs/p39/motion_reference_twoline_pre_p39.json` (`181c9151`, byte-identical)
and re-recorded the shipped file from the same-batch control:

```
python3 scripts/105_motion_regression.py logs/p39/p3/twoline_C.log \
    --write-fingerprint configs/motion_reference_twoline.json
  -> wrote fingerprint -> configs/motion_reference_twoline.json
     FAIL: 1 problem(s)
       - success 6/10 below 75%        <-- 105's single-arm floor, rate-only;
                                          the write is allowed (no motion budget fails)
  new md5: **d032603048e7ead4e3533256e9838c83** (was `181c9151d65cf2c1f5be16b4c37c8f1e`)
  fingerprints: [[89,0.109],[89,0.107],[86,0.11],[89,0.108],[89,0.109],
                 [89,0.107],[89,0.11],[91,0.11],[87,0.11],[93,0.111]]
```

`bash scripts/190_twoline_gate.sh logs/p39/p3/twoline_C.log` (`twoline_gate_after.txt`):

```
190: two-line gate: reference=configs/motion_reference_twoline.json floor=0.60
  success: 6/10 = 60% (floor 60% - override)
  fingerprint: matches configs/motion_reference_twoline.json
PASS: every descent is inside its profile's speed and lurch bound, the carry
      cone/slip is reported, and the success rate is at or above the dynamic
      line's floor
190: PASS logs/p39/p3/twoline_C.log
190: every log matches configs/motion_reference_twoline.json and is at or above
     the two-line floor 0.60
```

(`190` on `twoline_S.log` / `twoline_F1.log` still FAILs - 5/10 below the floor
for S and a different attractor for both. That is expected: the reference is
**one scenario's** record, and neither arm is adopted.)

**10.5 Reference consequences (documentation debt, not changed here).**
`README.md`, `docs/ROADMAP.md`, `决策与交付.md` and `项目总结报告.md` still quote
`181c9151` as the shipped two-line reference; `AGENTS.md` §2 carries the new
value and the archive. Two scripts also touch the file and must not be run
casually: `scripts/189_w7a_chain.sh` **re-writes** it from `logs/w7/10` before
gating (so running it restores the W7-A record), and `scripts/195_r9_chain.sh`
gates a freshly run R9 two-line log against whatever the file holds (now the
P39-C branch). Neither is a selfcheck leg.
