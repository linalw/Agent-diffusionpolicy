# P60 phase 1 — the left-arm failure census

**Verdict.** The left's deficit is a **carry/hold object, not an acquisition one.**
Of the left's 62 failures in the four post-profile corpora, **58 (93.5 %) are
`carried-not-placed`**: contact was made, the probe lift carried the fruit, the
bin-transfer leg started — and the payload was **no longer in the hand when the
place descent began** (0/58 cnps printed the `place low` row that **110/110**
placed episodes print, Fisher **p = 6.7e-13**). Five of those 58 carry the only
positional evidence in the logs, a `[bed-fall] … held=True` row, and it puts the
fruit **beside the source belt** (x ≈ 0.00 ± 0.05, y = −0.15…−0.42, z ≈ 0.77–0.86),
not at the bin — i.e. a drop **at the take-off, on the pick side of the station** (lane 0's
release is `(0.43, +0.55)` and the left carries toward **+y**, while the falls read
y < 0; the coordinate is a feed-tick snapshot, so quote the **direction**, not the point), in the window between
the grasp and the release. The other **4/62 (6.5 %) are `never-held`** and those
are the **+x reach cliff** (selection x 0.347–0.398 m, trigger dx +14…+58 mm), not
a close-quality problem. The right fails in the **opposite** classes: 103/111
placed, **2 cnp (1.8 %)** and **6 never-held (5.4 %)**.

The census cannot name the *cause* of the left's carry loss (a left-hand grip
asymmetry vs a degraded seat — the mirror of P35's occlusion, which also presents
as `cnp`), and it cannot separate "left arm" from "lane 0" or "grade A" at all,
because the direct env derives the arm from the grade (`rl_env.py:2516-2517`).
Those are the (iii) items, with the discriminating diagnostics named in §7.

**The three-way answer, explicitly.**

| option | verdict | counts |
|---|---|---|
| (i) acquisition / pre-contact | **refuted for 93.5 %** of the left's failures; holds only for a minority | 4/62 = 6.5 % `never-held` (contact never took), all at the +x reach cliff |
| (ii) carry / hold | **supported — this is the class** | 58/62 = 93.5 % `carried-not-placed`; 58/58 started the transfer leg, 0/58 had the payload at the carried height at the release, 5/58 have a proven mid-carry drop beside the source belt |
| (iii) the logs cannot separate | **only for the *cause* and for the arm/lane confound**, not for the class | cause: no slip/force row exists in 180 episodes; confound: arm ≡ bin ≡ grade by construction |

Corpora (all `moe_v13s` `61da390a`, W6-A patch sheet, `park=back(default)`,
`acq=on`, `lead=0.90 lateral=0.160 frame=station` in every one of the twelve logs):
the P59-p3 control `C_*` (shipped profile, shipped cap 4), the P58-p3b cell A″
`A2_*` (cap 4, pre-profile-row tree), and the P59-p2 arms `A_*` (cap 5) and
`B_*` (`target_from=0.40`), 3 seeds each, 15 picks each — **180 episodes**.

---

## 1. arm × class

| corpus | arm | placed | carried-not-placed | never-held | n |
|---|---|---|---|---|---|
| p59 p3 (control) | left | **2** | **17** | 1 | 20 |
| p59 p3 (control) | right | 24 | 0 | 1 | 25 |
| p58 p3b (A″) | left | 4 | 15 | 0 | 19 |
| p58 p3b (A″) | right | 24 | 1 | 1 | 26 |
| p59 p2 A (cap 5) | left | 0 | 13 | 1 | 14 |
| p59 p2 A (cap 5) | right | 27 | 0 | 4 | 31 |
| p59 p2 B (0.40) | left | 1 | 13 | 2 | 16 |
| p59 p2 B (0.40) | right | 28 | 1 | 0 | 29 |
| **pooled** | **left** | **7** | **58** | **4** | **69** |
| **pooled** | **right** | **103** | **2** | **6** | **111** |

The control row reproduces P59 phase 3's published split exactly (`left 2/20`,
`17/19` failures cnp), so the parser agrees with the record's own report.

**Class shares.** left: 58/62 = **93.5 %** of failures are cnp, 4/62 = 6.5 %
never-held. right: 2/8 = **25 %** cnp, 6/8 = **75 %** never-held. Fisher (pooled,
two-sided): cnp among attempts **p = 1.06e-12**, placed among attempts
**p = 6.92e-13**, never-held among attempts **p = 1.00** (4/69 vs 6/111 — the two
arms are *equally* bad at making first contact).

**The left is not failing on one fruit.** Placed/attempts by species — left kiwi
4/25, pear 1/14, apple 1/9, peach 0/9, lychee 1/7, orange 0/5; right strawberry
24/27, lychee 18/19, orange 16/18, apple 12/13, tomato 11/11, peach 10/10, pear
8/9, kiwi 4/4. Within kiwi alone the left is 4/25 and the right 4/4, so the class
is an arm/lane object, not a species object.

## 2. What separates the two arms (and what does not)

| readout (median [min–max]) | left cnp (58) | left placed (7) | right placed (103) |
|---|---|---|---|
| pre-close pad error, `fingertips NN mm` | 52 [25–69] | 45 [26–48] | **55 [40–115]** |
| fire-tick \|dx\| | **82 [7–156]** | 9 [0–66] | 47 [0–155] |
| `grasp_lift` stored-centre drift | 128 [121–162] | 126 [122–133] | 127 [121–276] |
| `place<bin>` stored-centre drift | 91 [69–107] | 96 [81–101] | 90 [35–191] |
| fire-tick dy | 246 [205–329] | 237 [216–268] | 257 [182–314] |
| effective reach / lead / t_arrive | 300 / 2.06 / 2.05 | 290 / 1.98 / 1.98 | 310 / 2.14 / 2.14 |
| **`place low` row printed** | **0/58** | **7/7** | **103/103** |

So: the pre-close pad error is **worse on the right** and it places (P47's "no
outcome information" holds here too), the internal re-anchor drifts are identical
to the millimetre, and the fire geometry (dy/reach/lead/t_arrive) overlaps
completely. The only rows that separate are the **place-descent row** (the
payload's height at the release) and the **lateral offset**.

### 2b. The per-pick note carries no class

`113_rl_report.py`'s `reasons()` digit-normalises the note list; on these 180
episodes that produces **exactly two keys**, and they are 1:1 with the outcome
triple: `never-held` → the trigger note **plus** `fruit did not follow the
gripper` (all 10 of the 70 failures in that class), `cnp` → the trigger note only
(all 60 of them, 58 left + 2 right). So the note adds nothing beyond `grasped`,
and a "no new failure reason" gate on this corpus is satisfied by construction for
the `cnp` class — the class split has to come from the `success/grasped/placed`
triple, which is what §1 uses.

## 3. Why "the payload was not in the hand" is a measurement, not a guess

`_place_low` (`tasks.py:12303`) returns immediately, printing nothing, when
`need = bottom − floor − clearance <= 0` — with `floor = output_belt_top_z =
1.35 m` (`assets.py:309`) and `clearance = 0.025 m`, that is `bottom <= 1.375 m`.
When the payload *is* held, `bottom` reads **1.457–1.519 m** across all 110 placed
episodes (`left placed 1464 [1457–1481]`, `right placed 1478 [1460–1519]`), so
`need` reads 82–144 mm, and every one of those 110 rows printed — i.e. on this
hand the fingertip floor bound (`finger_budget < drop`, the row's own condition,
satisfied in 110/110). An absent row therefore means `need <= 0`: the payload was
**at least 82 mm below the lowest carried height observed**, on the belt or the
floor, not between the pads. The one residual hole: a held payload whose finger
budget happened to exceed its need would also print nothing — not observed in 110,
but not excluded by construction, which is why §7's release-pose trace is named.

The five `held=True` falls (the only ones in 34 fall rows) are all left cnps:

| log | line | ep | fruit | x | y | z |
|---|---|---|---|---|---|---|
| `p59/p3/C_101.log` | 405 | 0 | apple idx 13, d 7.0 | +0.022 | −0.195 | 0.824 |
| `p59/p3/C_101.log` | 564 | 8 | pear idx 14, d 6.6 | +0.000 | −0.187 | 0.857 |
| `p59/p3/C_202.log` | 640 | 11 | apple idx 7, d 6.7 | −0.044 | −0.424 | 0.770 |
| `p58/p3b/A2_202.log` | 674 | 13 | apple idx 7, d 6.7 | +0.025 | −0.160 | 0.824 |
| `p59/p2/A_202.log` | 612 | 10 | apple idx 7, d 6.7 | −0.048 | −0.153 | 0.823 |

`sample.held` is set at the grasp (`tasks.py:11014`) and cleared by the release's
`spawner.detach` (`tasks.py:11831`), so `held=True` is exactly the grasp→release
window: **the payload left the line during the transfer**, 0.15–0.42 m downstream
of the pick station and 0.085–0.16 m outside the source belt's low-x edge
(`x = 0.11…0.57`, `assets.py:201,205`) — the pick side, not the bin. Zero of the
right's 111 episodes produces one.

## 4. The lateral band check (D)

| readout | left (69) | right (111) | test |
|---|---|---|---|
| selection-instant x (`[bed-sel] -> chosen`) | 0.274 m [0.188–0.398] | 0.295 m [0.177–0.365] | x ≥ 0.30: 28/69 vs 51/111, **p = 0.54** |
| implied jaw x at fire (`x_sel − dx`, ±19 mm of selection→fire drift) | 0.340 [0.332–0.376] | 0.333 [0.320–0.373] | ≈ 7 mm apart |
| fire-tick dx (signed) | −71 [−156, +58] | −39 [−155, +39] | — |

**The left does not sit at a different part of the band** (same distribution, same
range, p = 0.54; the jaw references agree to 7 mm). What differs is the
*outcome as a function of* the offset — a **left-only ceiling**:

| \|dx\| at the fire tick | left placed | right placed | Fisher |
|---|---|---|---|
| ≤ 66 mm | 7/33 | 54/62 | p = 2.2e-10 |
| > 66 mm | **0/36** | **49/49** | p = 8.0e-13 |

66 mm is the left's own placed maximum (its 7 placements read dx = −66, −61, −18,
−9, −6, −0, +8 mm; the right's 103 read up to 155 mm, median 47). Note the left
fails at *small* offsets too (26 of its 62 failures are inside 66 mm), so a
narrower gate is not the lever; the ceiling is a *co-symptom*, and it is quoted as
a band split, never as a gate (n = 7).

## 5. The two left failure mechanisms, kept apart

1. **`never-held` — 4/62, the +x reach cliff.** Selection x **0.355 [0.347–0.398]**,
   signed dx **+16 [+14, +58]**, `lift` leg only (no place leg, no release). That is
   P48's `|x| >= 0.39` class and R2.3's `FRUIT_POLICY_TRIGGER_X_MAX=0.39` window.
   These are the only genuinely *pre-contact* left failures.
2. **`carried-not-placed` — 58/62, the carry/hold loss.** Details in §2–§3.

The two are disjoint on dx (never-held dx > 0, cnp median −82 mm), so a single
"left is worse" statement conflates them.

## 6. What this census does **not** show, and why

* **No slip/force signature exists in these logs.** `FRUIT_CARRY_DIAG`,
  `FRUIT_SEAT_DIAG`, `FRUIT_ACQ_DIAG` and the `verbose` rows were not set by any of
  the four batteries, so there is **no `[carry]` `clean_slip` / `force_min` /
  `sep@loss` / `onset_row`** and no `[acq]` setup/close-start offset anywhere in the
  180 episodes. The P42/W8-B onset comparison ("does the left's escape look like
  the right's loaded slide?") therefore **cannot be made from this corpus** — it is
  the first thing the next run must buy (§7). Note `acq=on` (the P54 default) *is*
  active in all twelve logs; only its diagnostic row is missing.
* **The cause of the carry loss is not identified.** A left-hand grip asymmetry and
  a degraded seat (the mirror of P35's inactive-arm occlusion at the left's
  station — never measured, P35 scored the right's station only) *both* present as
  `cnp`. The census cannot choose. What it does say is that the left's close is
  **better** centred than the right's (`fingertips` 45–52 mm vs 55 mm), so a
  seat-*offset* story is not supported; a seat-*timing* story is not excluded.
* **Arm ≡ lane ≡ grade by construction** (`rl_env.py:2516-2517`:
  `bin_index = 0 if grade == "A" else 1; active = "left" if bin_index == 0`). Every
  left episode is a grade-A fruit placed on lane 0 (`[task] carry place0`), every
  right episode a B/C fruit on lane 1. No existing knob decouples them, so "the
  left arm" cannot be separated from "the bin-0 transfer" or "grade A" here. The
  species table (§1) rules out the *fruit* as the carrier of the effect and §4
  rules out the *band*; the arm/lane confound stands.
* **The five `held=True` falls are 5 of 58.** They prove the class exists but they
  do not localise the other 53 — a payload dropped *onto* the source belt stays
  above the fall threshold (`z < belt_center_z − 0.25 = 0.89 m`, `fruits.py:1753`)
  and rides to the end unremarked.

## 7. The discriminating diagnostic, if phase 2 or 3 wants the cause

1. **`FRUIT_CARRY_DIAG=1`** on this exact scenario (one arm × 15 picks × 3 seeds),
   reading `[carry] clean_slip_max / force_min / sep@loss / onset_row` per carry
   leg. This is the only instrument that separates "the pads lost the payload"
   from "the payload never sat between the pads" and gives the left a like-for-like
   onset against P42's `SIM_LIMIT.md` census and P43's right-arm 16 → 2
   `force_min = 0` result.
2. **`FRUIT_PLACE_TRACE=1` + `FRUIT_RELEASE_DEBUG=1`** (which prints
   `[task] released at [x,y,z], placed=…`): one run places every payload's release
   pose in the log, which is exactly the missing `where` for the 53 without a fall.
3. To break **arm vs lane/grade**, nothing in the tree can: the arm is a function
   of the grade. The separators are a code change (an explicit active-arm override
   for a diagnostic battery) or the two-line scheduler's right station
   (`y = −0.10`, the only measured same-arm/other-station configuration).

## 8. Checkable numbers

`python3 logs/p60/left_census.py` prints every row above with its `file:line`;
`--check` re-asserts eleven parser/corpus invariants (all PASS), including the two
structural ones this census leans on: *every cnp episode printed its place leg*
and *a `[feed]` release row exists iff the place leg ran*. Output archived as
`logs/p60/left_census.txt`.

Pins: `logs/p60/left_census.py` md5 **94ee8ca9**, tree HEAD `725b3c4`, **no
`src/`/`configs/`/`scripts/` edit** (`git status` clean there), checkpoint
`moe_v13s` `61da390a`. Corpus: `logs/p59/p3/C_{77,101,202}.log`,
`logs/p58/p3b/A2_{77,101,202}.log`,
`logs/p59/p2/{A,B}_{77,101,202}.log` (headers pin `rl_env.py` `1b1e5cdf` /
`8ad8ddc8` for the p59 logs and `ddcb7816` / `c7eef701` for the p58 cell).
