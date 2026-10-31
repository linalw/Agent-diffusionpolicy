# P69 G0 — the rail-crossing contact calibration: where the payload actually touches

Oracle item **G0** of `logs/p69/B_PREREG.md` §"what would make it not worth it" / §9,
prompted by `logs/p69/A_PREREG.md` §0's last row. Scripted runs only: no `src/` or
`configs/` edit, no default change, no commit. Tree: `tasks.py` **`e5168578`**,
`rl_env.py` `d88c3729`, `conveyor.py` `b0d95a08`, `assets.py` `61baf52b`,
`configs/motion_reference.json` `8a399626` — all as `B_PREREG.md` §10 pins them.

---

## 0. Verdict

**The boundary is measured, it is not where either side of the argument assumed, and
`-1 mm` is inside the contact band.**

1. **The bracket.** On the floor's own instrument (the `clr` crossing sample) the
   payload touches at **`clr <= +7 mm`** and does not at **`clr >= +14 mm`** — so the
   boundary lies in **`(+7, +14] mm`**. On the footprint minimum (`clr_win`, the same
   quantity as `logs/p30a`'s leg-minimum column) it is **`(0, +12] mm`**, and the
   scripted record's own A4 contact at -7 (`logs/p30a`, 18.22 m/s^2) brackets the
   same way from the other side. The mechanism is the obvious one and the instrument
   is calibrated by it: the payload touches when its lowest point reaches the rail's
   **top face** (`clr_win = 0`), which is a 25 mm-wide ledge at 1.385 m.
2. **`-1 mm` is a contact, not a graze.** Five held place legs at `clr` = -2/-1/-1/+0/+7
   (`clr_win` -39..-0) read **14.9-32.7 m/s^2** hand reaction with **27-76 mm** of
   payload displacement, `res_end` 118-136 mm on four of them (the arm stopped short
   of the pose it was sent to) and `sep_end` 97.5-98.3 mm on four (the pads driven to
   their open stop). The 15 held legs at `clr >= +14` read **2.6-5.7 m/s^2**, 0.0-0.1 mm
   of slip, `res_end` 23-44 mm, `sep_end` 41-78 mm. **The two populations do not
   overlap** (5.71 vs 14.85 m/s^2 = a 2.6x gap).
3. **So the low lift's own population is *not* inside the safe region — it straddles
   the boundary.** P67's in-place population reads `clr` +3..+17 / `clr_win` -1..+13:
   three of its five legs sit in the contact band or the unmeasured gap between the two
   instruments (`clr` **+3 / +7 / +8**, `clr_win` **-1 / +4 / -21**) and two are clear
   (`clr` **+16 / +17**, `clr_win` **+12 / +13**). Its own rows corroborate it —
   the `clr_win <= 0` legs carry 15.9 and 94.3 mm of `clean_slip` with `loss_row` set
   on the same tick as the window minimum, while the `+12/+13` legs read 0.1/0.0 with
   no loss. **P66 §5's "measured, non-contacting geometric graze" is falsified as a
   *non-contacting* claim**; it is a measured contact on the population's tail.
4. **But the 7 h is answering the wrong question, and its dose is ~2.6-3x the measured
   one.** Contact-freedom for the low lift's worst valid leg needs **~+11-13 mm** of
   crossing clearance (from `clr` +3 / `clr_win` -1 to the lowest measured clean +14 /
   +12), not the registered 34-35 mm: `FRUIT_OUTPUT_RAIL_HEIGHT` **0.05 -> 0.037-0.039**
   keeps 22-24 of the 35 mm of lip and still leaves F1's ledge class a 22 mm face
   instead of a flush shelf. What the 7 h actually prices is the **blast radius, which is
   binary**: any rail value moves the scene branch, both motion references and every
   store (`B_PREREG.md` §6.2/§6.5). Shrinking 34 -> 13 mm does not shrink it.
5. **The honest package is therefore the low lift + a signed floor at the measured
   boundary — 0 h, 0 references, 0 stores — but it must be signed as an accepted
   *contact* on ~40 % of the low lift's crossing legs, not as a "graze".** What that
   contact costs, measured: the grip (27-76 mm of payload displacement, pads at the
   98 mm stop, up to 109.9 N tactile) and 15-33 m/s^2 of hand reaction; what it does
   **not** cost, measured: the placement — **5/5 of the contacting legs placed**, and
   `logs/p30a`'s A4 read 6/9 with three contacts against 6/9 with none. The reason is
   geometric: the collision happens at the output belt's inner fence, so a payload
   that is pried out there lands on the belt. **The rail change is not needed for
   placements; it is needed only to keep the +33 convention, which the measurement
   places ~20-25 mm above contact.**

---

## 1. The cell

`scripts/20_pick_place.py` (the acceptance-shaped scripted line), `ATTEMPTS=10`,
`HEADLESS=1`, `FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1`, one
`scripts/154_claim_run.sh` claim per run (~4.6 min wall each, 23 min total):

| run | `FRUIT_OPENARM_TRANSFER_LIFT` | placed | place legs (held / escape / no-read) | `[stats]` |
|---|---|---|---|---|
| `t080` | **0.080** (the shipped value, set explicitly) | 6/10 | 6 / 4 / 0 | 150.5 s, 15.0 s/attempt |
| `t050` | 0.050 | 3/10 | 3 / 5 / 2 | 149.2 s, 14.9 s/attempt |
| `t045` | 0.045 | 3/10 | 3 / 5 / 2 | 149.2 s, 14.9 s/attempt |
| `t035` | 0.035 *(extension)* | 5/10 | 5 / 3 / 2 | 143.9 s, 14.4 s/attempt |
| `t025` | 0.025 *(extension)* | 3/10 | 3 / 6 / 1 | 145.7 s, 14.6 s/attempt |

**The control is valid.** `t080`'s non-diagnostic `[fruit]` stream is **337/337 lines
identical** to the recorded acceptance `logs/p66/p2/accept_noharm.log` (the extra 80
rows are the `[carry]`/`[motion] carry`/`[diag]` rows this cell switches on), so the
two diagnostics are branch-neutral here and the batch is the shipped line.

**Recorded deviation from the registered cell.** `B_PREREG.md`'s G0 did not exist as a
registered cell — this document was asked for the calibration, with 0.045/0.050 and the
0.08 control. Those three runs **reached no jolt** (lowest held `clr` +22, see §2), so
the bracket could not be closed; `t035` and `t025` were added as a downward extension
of the same ladder, same env, one claim each. Everything below is reported for all five.

**What the knob does, and what it does not.** `FRUIT_OPENARM_TRANSFER_LIFT` is read at
**two** sites (`tasks.py:3269` the lift end, `:3308` the transfer), so the scripted
transit stays **horizontal** and `clr` moves 1:1 with it. Two facts about this tree
limit how far the ladder reaches, both measured here:

* **The left lane has no usable crossing population.** It places **1/29** place legs
  across the five runs (the closed `cnp` class of `logs/p42/SIM_LIMIT.md`); its other
  28 legs read `clr` -215..-220 mm (the escaped-payload class — a fruit on the *main*
  belt, `logs/p30a/RESULTS.md` §5) or never latch a rail reading at all. The one held
  left leg (control, kiwi) reads **`clr` +30 / `clr_win` +29** — within 3 mm of the
  record's +33 floor. **The calibration curve is measured on lane 1 (the right arm's
  `place1`).**
* **At 0.025 a second obstacle appears.** One right leg is blocked before the rail
  (`clr_min` +144 mm *to the main belt*, i.e. it never reached `|y| >= 0.40`),
  `res_end` 180.3 mm, `force@onset` 80.15 N: the payload is 36 mm below the output
  belt's top face, so it meets the **slab** first. That is the `lift=0` class of
  `logs/p30a` §7, not the rail, and it is the reason the ladder stops here.

## 2. The calibration curve (all 20 held place legs)

`|a|max` is the `[motion] carry placeN` hand reaction; `slip` is `clean_slip_max`;
`res_end` is the leg's achieved-vs-target TCP residual; `sep_end` the jaw separation at
the release (`98 mm` = the pads' mechanical open stop).

| run | `clr` | `clr_win` | fruit | lane | `a_max` | slip | res_end | sep_end | placed |
|---|---|---|---|---|---|---|---|---|---|
| t035 | **-2** | -30 | apple | 1 | **26.93** | 76.3 | 117.6 | 98.3 | True |
| t035 | **-1** | -31 | pear | 1 | **26.37** | 52.1 | 136.0 | 98.0 | True |
| t025 | **-1** | -38 | lychee | 1 | **29.82** | 62.1 | 121.9 | 97.5 | True |
| t025 | **+0** | -39 | strawberry | 1 | **14.85** | 63.6 | 127.9 | 97.8 | True |
| t025 | **+7** | **-0** | strawberry | 1 | **32.71** | 27.4 | 37.0 | 40.5 | True |
| t035 | +14 | **+12** | lychee | 1 | 4.21 | 0.0 | 34.6 | 44.3 | True |
| t035 | +21 | +18 | strawberry | 1 | 4.10 | 0.0 | 35.2 | 40.7 | True |
| t045 | +22 | +17 | pear | 1 | 3.95 | 0.0 | 36.2 | 74.5 | True |
| t045 | +24 | +22 | lychee | 1 | 5.71 | 0.0 | 37.9 | 44.4 | True |
| t035 | +26 | +22 | strawberry | 1 | 5.43 | 0.1 | 43.8 | 44.7 | True |
| t080 | +30 | +29 | kiwi | **0** | 2.63 | 0.0 | 23.1 | 67.3 | True |
| t045 | +32 | +28 | strawberry | 1 | 4.08 | 0.0 | 33.7 | 40.8 | True |
| t050 | +37 | +29 | pear | 1 | 4.05 | 0.0 | 35.5 | 74.5 | True |
| t050 | +44 | +38 | lychee | 1 | 4.94 | 0.1 | 36.8 | 44.2 | True |
| t050 | +46 | +40 | strawberry | 1 | 3.96 | 0.0 | 33.4 | 48.2 | True |
| t080 | +90 | +75 | apple | 1 | 4.90 | 0.0 | 38.2 | 77.9 | True |
| t080 | +99 | +84 | lychee | 1 | 4.89 | 0.0 | 31.6 | 44.4 | True |
| t080 | +109 | +95 | strawberry | 1 | 5.28 | 0.0 | 40.2 | 44.8 | True |
| t080 | +112 | +95 | strawberry | 1 | 4.43 | 0.0 | 31.0 | 48.3 | True |
| t080 | +120 | +96 | pear | 1 | 4.62 | 0.0 | 36.3 | 74.5 | True |

| class | n | `clr` | `clr_win` | `a_max` | slip | res_end | sep_end |
|---|---|---|---|---|---|---|---|
| **clean** | 15 | +14 .. +120 | +12 .. +96 | **2.63-5.71** (med 4.53) | 0.0-0.1 | 23-44 (med 36) | 41-78 |
| **jolt** | 5 | **-2 .. +7** | **-39 .. -0** | **14.85-32.71** (med 26.93) | **27.4-76.3** | 37 / 118-136 | 40.5 / 97.5-98.3 (4) |

**The bracket.** Lowest `clr` that placed **without** a jolt: **+14 mm** (t035 lychee,
4.21 m/s^2). Highest `clr` **with** a jolt: **+7 mm** (t025 strawberry, 32.71 m/s^2).
On the window instrument: no contact at `clr_win` **+12**, contact at **-0**. So

> **contact at `clr` <= +7 mm / `clr_win` <= 0 mm; no contact at `clr` >= +14 mm /
> `clr_win` >= +12 mm.** Boundary in **(+7, +14] mm** (`clr`) or **(0, +12] mm**
> (`clr_win`), and the physical zero is the rail's top face.

**The displacement is a *cause* sweep, not one leg.** The three right fruits recur in
every run (lychee / strawberry / pear at attempts 4/5/6), so the curve is the same
fruits at five transfer heights: lychee `clr` +99 (0.08) -> +44 (0.050) -> +24 (0.045);
strawberry +112 -> +46 -> +32; pear +120 -> +37 -> +22 — monotone, ~-55..-83 mm for a
-30 mm command, i.e. the per-leg `clr` is not a clean 1:1 function of the command
(the grasp point and the payload's seat in the jaws move with it). **That is why the
curve must be read leg-by-leg and not extrapolated from the command** — which is the
reason the two extension rungs were needed at all.

## 3. The mechanism, and why this is a contact and not a metric artifact

`_payload_clearance` reports against the rail's **nominal** top for `0.400 < |y| <= 0.46`
(`tasks.py:3336-3343`), so a negative reading alone proves nothing — `logs/p30a`'s A5
arm reads -9/-7/-4 mm with the rail **removed** and 4.7-7.6 m/s^2. Four independent
channels separate the classes on *this* corpus, where the rail is present:

1. **hand reaction**: 14.9-32.7 vs 2.6-5.7 m/s^2, no overlap;
2. **reach**: `res_end` 118-136 mm on four of five jolt legs (the arm is stopped short
   of the pose it was sent) against 23-44 mm on all fifteen clean ones;
3. **the pads**: `sep_end` 97.5-98.3 mm (the open stop) on four jolt legs;
4. **tactile**: `force@onset` **71.4 / 86.3 / 109.9 N** on the three whose payload was
   pried hardest, against `force_min` 8.8-10.0 N on every clean one, and 27-76 mm of
   `clean_slip` (0.0-0.1 mm clean).

The slip onset lands on the crossing: `onset_row` 138-173 vs the crossing ticks
151-190, and the `loss_row`/window minimum coincide to a few ticks. The **one**
exception to the severity monotonicity is the `clr` +7 / `clr_win` -0 leg: the highest
hand reaction of the corpus (32.71 m/s^2) **and** the highest tactile (109.94 N) with a
*normal* reach residual (37.0 mm) and an unremarkable pad opening (40.5 mm) — a tangent
strike is a hard impact with little mechanical displacement. It lost the grip outright
(`loss_row` 165, `force_min` 0.00 N) **and still placed** (the payload landed on the
output belt), so **`|a|max` is the sensitive channel and the mechanical fields grade the
severity, not the existence, of the contact.**

**Cross-check from the record, on the same instrument** (`logs/p30a/RESULTS.md` §5,
A4 at `FRUIT_OPENARM_TRANSFER_LIFT=0.04`, leg-minimum column): contacts at **-7/-23/-35**
with **18.22/19.83/17.79** m/s^2, and **no** contact at **+8/+22/+26** with
**4.43/4.26/4.81**. That is the same bracket read from the record's own arm: contact at
`<= 0` (ours) or `>= -7` (theirs), no contact at `+8` (theirs) or `+12` (ours). **Joint
bracket on the window/leg-minimum instrument: contact at 0 mm, no contact at +8 mm.**

**And from the low lift's own rows** (`logs/p67/A2_77.log`, `FRUIT_LIFT_DZ=-0.08`,
5 in-place left legs): `clr_win` **-1 / +4 / -21 / +12 / +13** with `clean_slip`
**15.9 / 21.3 / 94.3 / 0.1 / 0.0** and `loss_row` set on exactly the three at or below
+4. P67 read these as the closed carry class; at least the `-1` and `-21` legs are also
rail contacts (their loss ticks coincide with the window minima), and the `+12/+13`
legs are clean — which is this document's boundary applied blind to another corpus.

## 4. What this does to the +33 floor

The floor of record is the shipped configuration's own minimum over 42 place legs
(`logs/p30a/RAILS_DESIGN.md:133`). This batch reproduces it: the shipped control's one
held left leg reads `clr` **+30 / clr_win +29**, and its five right legs read
**+90..+120**. So

* **the shipped line's real crossing margin is ~20-23 mm, not 33** — the +33 is the
  shipped *population minimum* (a convention), and it sits 19-26 mm above the measured
  contact (+7..+14);
* **the convention is therefore conservative, not arbitrary**, and it is *not*
  the contact threshold — `B_PREREG.md` §10's caveat is confirmed;
* **the low lift spends the whole margin and then some**: its tail legs (`clr` +3,
  `+7`, `+8`) are 4-11 mm below the lowest measured clean crossing, and its `clr_win`
  -1 leg is past the boundary.

## 5. The dose, if a contact-free low lift is wanted

Using the low lift's worst *valid* leg (`clr` +3 / `clr_win` -1; the `clr_win` -21 leg
is a payload that had already slid 94 mm and no rail height fixes it):

| target | required gain (from the low lift's worst valid leg, `clr` +3 / `clr_win` -1) | rail dose (1:1) | what it keeps |
|---|---|---|---|
| the lowest measured **contact-free** reading on the **crossing sample** (`clr` +14) | **+11 mm** | `FRUIT_OUTPUT_RAIL_HEIGHT` 0.05 -> **0.039** | 24 of the 35 mm of lip |
| the same on the **footprint window** (`clr_win` +12) — the binding one, since `clr_win <= clr` always | **+13 mm** | 0.05 -> **0.037** | 22 of the 35 mm of lip |
| the record's **+33** convention (window: -1 -> +33) | **+34 mm** | 0.05 -> **0.016** | 1 mm of lip |
| the registered `B_PREREG.md` setting (flush) | +35 mm | 0.05 -> **0.015** | 0 (a flush shelf) |

The transfer lever is the alternative at 0.825:1 (**+16 mm**, 1.530 -> 1.546) and the
lift-end lever at 0.175:1 (**+74 mm**, i.e. 0.274 — just under the 0.28 rung whose
`drift_end` is 3.4 deg). **The registered 34-35 mm is the +33-convention dose, not the
contact-freedom dose**: contact-freedom is **~+11-13 mm** (the two instruments' ends),
i.e. **2.6-3.1x smaller**.

**Shrinking the dose does not shrink the bill.** Every option above is a *rail value*,
and a rail value is binary in blast radius: one scene branch, `configs/motion_reference.json`
**and** `..._twoline.json` re-recorded from their own same-batch controls, every store
re-baselined (`B_PREREG.md` §6.2/§6.5), plus G2's ledge fixture. That is the ~7 h. The
only 0 h route is to accept the contact.

## 6. Verdict on the package

**Not "the low lift + a documented graze + a signed floor" — the first two words are
wrong.** What the measurement supports, stated plainly:

1. **`-1 mm` is a measured contact** (26.4 m/s^2, 52.1 mm slip, pads to 98.0 mm). Any
   floor signed at `-1`, or described as non-contacting, would be signing a value that
   five legs in this batch demonstrably collide at.
2. **A floor signed at the measured boundary is available** — `clr` `>= +14` /
   `clr_win >= +12` contact-free, `+7..+14` the unmeasured band, `<= +7` in contact —
   and the low lift's population straddles it (3 of 5 legs in the contact band or the
   unmeasured gap, 2 clear).
   Signing it means **accepting a contact on ~40-60 % of the low lift's crossing legs**,
   with the measured cost in §3 (grip displacement, 98 mm pads, 15-33 m/s^2) and the
   measured non-cost (**5/5 placed here, 6/9 = 6/9 in A4**).
3. **The 7 h rail change is not justified by the placements and its registered dose is
   ~2.6-3x the measured one.** If the owner wants a contact-free low lift, the dose is
   **~11-13 mm**, not 34-35; if the owner wants the +33 convention back, only then is the
   registered flush (or its 34 mm equivalent) the right dose — and it is a *convention*
   purchase, exactly as `B_PREREG.md` §10 says, now with the number behind it.
4. **The recommendation, in one line**: ship the low lift with a floor at the *measured*
   boundary and the contact documented as a contact (0 h, 0 references, 0 stores), and
   treat the rail change as a **convention** purchase that is available at 11-13 mm if
   the +33 floor is to be honoured — not as a repair.

**What would change this verdict**: a corpus in which a `clr` <= +7 leg places without
`|a|max` above 10 (the class gap is 2.6x, so one leg would not overturn it — five
would), or an owner rule that a crossing contact is unacceptable regardless of the
placement outcome, which makes the +33 convention binding and the 11-13 mm dose the
cheapest route to it.

## 7. Scope and what this does not measure

* **Lane 1 only.** The left lane gives one held leg per 29 place legs on this tree, so
  the calibration is the right arm's. The boundary is a property of the
  payload-vs-rail pair and of the `clr`/`clr_win` instrument, not of the arm; the arms
  sit at very different clearances (left `clr` +30, right +90..+120 at the same
  lift), so an arm-specific *population* claim is not made.
* **The scripted line's horizontal transit.** The low lift is a *direct*-line setting
  whose transit climbs (lift end 1.370 -> transfer 1.530), which puts its window
  minimum 4-5 mm *below* its crossing sample (P67's own rows: +3/-1, +7/+4). Applying
  this bracket there is therefore conservative in the "more contact" direction — and it
  is what P67's slip rows already show.
* **No motion report on the record's direct corpora** (`logs/p67/A2_77.log`,
  `logs/p66/p4/L2_77.log` have no `|a|max`), so the low lift's own legs cannot be
  re-scored on the primary channel; their `clean_slip`/`loss_row` is the proxy used in
  §3, and it agrees.
* **Not a rate.** The contact legs are 5 samples and every one placed; 5/5 bounds the
  loss rate at <= ~45 % (rule of three) — it does **not** say the contact is free, only
  that placements were not lost in this batch or in A4's.
* **0.025 is not usable as a rail cell** (§1): the slab becomes the binding surface.

## 8. Pins and reproduce

```bash
for L in 0.080 0.050 0.045 0.035 0.025; do
  RUN_LIMIT=1200 HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10 FRUIT_CARRY_DIAG=1 \
    FRUIT_OPENARM_TRANSFER_LIFT=$L scripts/154_claim_run.sh \
    logs/p69/g0/t${L/0./}.log scripts/run.sh scripts/20_pick_place.py
done
python3 logs/p69/g0/g0_report.py logs/p69/g0/t*.log > logs/p69/g0/g0_report.txt
```

**Pins** (md5 first 8; `logs/` is gitignored — `git add -f` at the close-out):
`g0/t080.log` **`81a14aa7`**, `t050` `7ac61ead`, `t045` `64d609cd`, `t035` `f464dc0b`,
`t025` `ebc0776f`; `logs/p69/g0/g0_report.py` **`19c7ef6c`**, `g0_report.txt`
`bd888fc2`. **Unchanged**: `tasks.py` `e5168578`, `rl_env.py` `d88c3729`,
`conveyor.py` `b0d95a08`, `assets.py` `61baf52b`, `configs/motion_reference.json`
`8a399626`, `configs/motion_reference_twoline.json` `2246f83c`; `git status` clean on
`src/` and `configs/`. **Nothing adopted, no default moved, no reference re-recorded,
no commit.**
