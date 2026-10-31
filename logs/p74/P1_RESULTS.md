# P74 phase 1 results — the place-profile **speed** does not move the left arm's place-leg slide, and the `> 800 mm` threshold turns out not to be speed-invariant

Registration: `logs/p74/PREREG.md`, md5 **`1c3546de`**, written and pinned
**before any simulator run of this phase** (`logs/p74/PREREG.md5`,
2026-10-31T04:30:48Z; the first simulator run starts 12:32:41 local, the batch's
`header.txt` records `prereg: 1c3546de…`). Tree at registration = tree at
measurement (see the provenance note below), `tasks.py` **`adcfd348`**,
`rl_env.py` **`157e6d`**, `configs/motion_reference.json` **`8952c320`**,
`configs/motion_reference_twoline.json` **`eb697f23`**, checkpoint `moe_v13s`
**`61da390a`**. **This phase changed no source file, no config, no default.**

**Provenance note (a commit landed between the two batches).** The seed-77 batch
ran on HEAD `75e980a`; the expansion batch (seeds 101/202) ran on HEAD
`90f31a6`, which another lane committed at 12:5x while the batch was running.
`git diff 75e980a 90f31a6` is **two files, both under `logs/`**
(`logs/p36/offline_obs_diff.txt` one line, `logs/p73/P1_RESULTS.md` a doc
edit) — **no `src/`, `configs/` or `scripts/` change**, and every md5 in the
batch's `header.txt` (behaviour files, `configs/`, checkpoint, selfcheck scripts)
is the value this phase registered against, so the two halves of the batch are
the same scenario. The committed P73 doc edit is not mine; `logs/` is gitignored
and nothing in it is a control input.

---

## 0. Verdict

**Falsifier F1 fires: slides are flat in S once the walk's own speed bias is
removed. The dwell is not the actuator either, and the place-leg loaded slide is
stochastic given the pinch.**

* **The mechanism count is flat** over a **2.6x** range of place-leg dwell:
  `loss` (a payload that left the pinch, `clean_slip_max > 100 mm`) is
  **4/8 = 50 %** at 680-tick legs (P73's `0.20` arm), **8/19 = 42 %** at 405
  (this phase's C), **7/14 = 50 %** at 262 (this phase's S) — Fisher S vs C
  **p = 0.733**.
* **The registered primary does fall** — `clean_slip_max > 800 mm` reads
  **7/19 = 37 % (C) vs 3/14 = 21 % (S)** — **and that fall is a measurement
  artefact, not a mechanism**: the walk after the escape is
  `rate x (ticks - loss_row)`, the rate rises **3.2 -> 4.0 mm/tick (+25 %)** with
  the pads' speed and the remaining ticks fall **-38 %**, so events migrate from
  the `> 800` band into the `100-800` one while the escape rate does not move.
  S draws **4 near-misses at 659.6-799.1 mm** against C's **1 at 617.1 mm**.
* **The seed-77 read was a false positive, and the pre-registered expansion is
  what caught it**: seed 77 read 2/4 -> 1/6 (the predicted direction, and the
  expansion rule fired on it), seed 101 read **4/7 -> 4/5** and seed 202
  **2/8 -> 2/3** — the opposite direction at both. One seed would have published
  a win.
* **Nothing else regressed**: the failure ledger is **identical in count**
  between the arms (left `cnp` 8 vs 8, left `never-grasped` 1 vs 1, right 2 vs 2,
  `did-not-land` 8 vs 8, `fell off` 0 vs 0, blow-ups 0 vs 0), the right is
  23/25 vs 28/30 placed with **0 loaded slides in both**, `clr`/`clr_edge` do not
  move on distance-matched legs (**-1 / -3 / -9 mm**), and the release geometry
  is preserved.

**Nothing is adopted, no default moved, `configs/` untouched, no commit.** There
is no phase 2: the cell measured what it was registered to measure and the
answer is negative.

---

## 1. The knob, and the proof that it reached the DIRECT place leg

**`FRUIT_SPEED_PLACE=0.52`** — the P44 **S1** registered cell, which is the exact
mirror of the `=0.20` arm P73 inferred the mechanism from. It changes no
behaviour by itself: it supplies the **default** of `FRUIT_DYNAMIC_PLACE_VMAX`
read at `tasks.py:3853` inside `elif self._dynamic_capture_active:`, which the
direct presentation arms (`PREREG` §1.1). `FRUIT_DYNAMIC_PLACE_VMAX=0.52` is
limit-identical (`v_max` 0.52, `a_max` 1.089 either way), and the direct path
resolves the explicit env var first — the cell is what supplies the value when
only it is set, which is the S arm.

**The manipulation gate (`logs/p74/p1_report.py --check`, PREREG §1.3) passes on
every clause and every seed** — the leg is the arm's own profile, not a lookalike:

| seed | arm | left place legs | `|v|cmd` median | per-leg vs `jerk_limited` | S/C ticks, distance-matched | `place low` descent |
|---|---|---|---|---|---|---|
| 77 | C | 4 | **0.343** | 4/4 within 4 % | **0.676** (2 pairs) | 78 t |
| 77 | S | 6 | **0.509** | 6/6 within 4 % | (predicted 0.673 ± 0.06) | 74 t (-5 %) |
| 101 | C | 7 | 0.343 | 7/7 | **0.677** (3 pairs) | 79 t |
| 101 | S | 5 | 0.509 | 5/5 | | 74.5 t (-6 %) |
| 202 | C | 8 | 0.343 | 8/8 | **0.678** (1 pair) | 77 t |
| 202 | S | 3 | 0.508 | 3/3 | | 73 t (-5 %) |

`|v|cmd` tracks the cap through the profile's 2 % duration margin
(`0.35/1.02 = 0.343`, `0.52/1.02 = 0.510`), and the per-leg tick count matches
`motion.jerk_limited` at the printed distance to **≤ 1 %** on **33/33** legs.
The knob is **not side-scoped**: the right's place legs shorten by the same
factor (median **356 -> 258 ticks**), which the PREREG registered up front.

---

## 2. The primary — the class ledger, pooled over the three seeds

Cell: the P66-phase-3 / P71-phase-2 / P73 scenario verbatim, `moe_v13s`
`61da390a`, 15 picks, `FRUIT_CARRY_DIAG=1 FRUIT_MOTION_REPORT=1
FRUIT_CARRY_ATTITUDE=1` in both arms, one claim per run. Seeds **77, 101, 202**
(the expansion was triggered at seed 77, see §3).

| seed | arm | left place legs | **>`800` (the primary)** | near `100-800` | micro | held | **loss** | left placed |
|---|---|---|---|---|---|---|---|---|
| 77 | C | 4 | **2** | 0 | 0 | 2 | **2** | 2/5 |
| 77 | S | 6 | **0** | 1 (799.1) | 0 | 5 | **1** | 4/7 |
| 101 | C | 7 | **3** | 1 (617.1) | 0 | 3 | **4** | 3/7 |
| 101 | S | 5 | **3** | 1 (798.8) | 0 | 1 | **4** | 1/5 |
| 202 | C | 8 | **2** | 0 | 1 (6.3) | 5 | **2** | 6/8 |
| 202 | S | 3 | **0** | 2 (659.6, 740.9) | 0 | 1 | **2** | 1/3 |
| **pooled** | **C** | **19** | **7 (37 %)** | 1 | 1 | 10 | **8 (42 %)** | **11/20** |
| **pooled** | **S** | **14** | **3 (21 %)** | 4 | 0 | 7 | **7 (50 %)** | **6/15** |

`micro` = crossed the 2 mm relative-slip crossing but recoiled inside 100 mm (one
leg, C_202); `held` = no crossing at all; `loss` = `slide + near`, a payload that
left the pinch. No arm drew a blow-up (the registered `> 10 m` / `> 5 m/s`
exclusion caught nothing).

**The two registered contrasts:**

| endpoint | C | S | Fisher two-sided |
|---|---|---|---|
| **`> 800 mm` (PREREG primary)** | 7/19 = **36.8 %** | 3/14 = **21.4 %** | **p = 0.455** |
| **`loss` (the mechanism)** | 8/19 = **42.1 %** | 7/14 = **50.0 %** | **p = 0.733** |
| left placed | 11/20 = 55 % | 6/15 = 40 % | p = 0.500 |
| right placed | 23/25 = 92 % | 28/30 = 93.3 % | p = 1.000 |

So the primary "falls" by 15 points and the mechanism is **+8 points the other
way**, neither anywhere near significance at n = 14-19 legs.

---

## 3. Why the primary fell and the mechanism did not — the walk, not the escape

This is the phase's second finding and it is a **measurement** result that will
outlive the negative: **`clean_slip_max > 800 mm` is not a speed-invariant
classifier.**

The escape is the same event at both speeds — one pad in contact at the pinch's
own force, then contact lost (`force_min 0.00 N`, `min_contacts 0`), the jaws
ending **closed to 17-54 mm** (never the 98 mm open stop), the payload then
free-falling while the pads continue. So the reported `clean_slip_max` is
essentially `rate x remaining ticks`:

| arm | walk rate `slip/(ticks-loss)` [mm/tick] | leg ticks (median) | product |
|---|---|---|---|
| C (all 3 seeds) | **3.13 / 3.21 / 3.25** | 405-430 | ~800-1000 mm |
| S (all 3 seeds) | **3.93 / 3.98 / 4.00** | 262-278 | ~660-1090 mm |

The rate rises **+25 %** (the pads run at 0.46 m/s against 0.32) and the
remaining leg falls **-38 %**, so the product straddles the 800 mm line: S's four
near-misses sit at **659.6 / 740.9 / 798.8 / 799.1 mm** — that is exactly the
band the shorter walk lands in. **The correct count for any speed change is the
escape (`loss`), not the threshold**; for a *height*, *rotation* or *retiming*
change the threshold is fine, which is why P73 could use it.

**Corollary correction to P73 §2.1**: its C arm's 793.3 mm "held by the 800 mm
rule" leg was already named a payload loss in that text; P74 shows the whole
`700-800` band is where a **faster** leg's escapes land, so a phase that had only
counted `> 800` would have reported a 15-point win for a mechanism with a flat
rate.

---

## 4. The dwell hypothesis, scored against both directions

| arm | place `v_max` | median leg ticks | relative dwell | `loss` / legs | rate |
|---|---|---|---|---|---|
| P73 SLOW (`FRUIT_SPEED_PLACE=0.20`) | 0.20 | **680** | **1.68x** | **4/8** | 50 % |
| P74 C (shipped) | 0.35 | **405** | **1.00x** | **8/19** | 42 % |
| P74 S (`FRUIT_SPEED_PLACE=0.52`) | 0.52 | **262** | **0.65x** | **7/14** | 50 % |

**The response is flat across a 2.6x dwell range** (P73's slow leg to this
phase's fast one). P73's `4/8` is therefore a draw of the same ~45 % rate, **not
a dose response** — the "time-accumulating loaded creep" reading that P73 offered
as its directional mechanism is **withdrawn**, exactly as its own caveat said it
should be if the fast direction came back empty ("the *speed-up* direction is the
one with a measured contrast"). It does not.

What survives is P73's positive half: the escape's **onset precedes the wrist's
45-deg crossing on 15/15 payload losses across this batch too** (`loss_row/ticks`
0.01-0.44 against `t45/ticks` 0.71-0.86), the right reaches the same attitude and
slips 0.0-0.1 mm on 28/28 place legs, and the escape's signature is unchanged
(§6.3). So the class is **stochastic given the pinch**, and the driver is neither
the pose nor the clock.

---

## 5. The guards

### 5.1 The acquisition guard is clean (P4, the leg the brief named)

| | C | S |
|---|---|---|
| left `never-grasped` (`grasped=False`) | **1** | **1** |
| right `never-grasped` | **2** | **2** |
| left `cnp` (`grasped=True, placed=False`) | **8** | **8** |
| right `cnp` | 0 | 0 |
| `did not land` rows | **8** | **8** |
| `fell off the line` rows | 0 | 0 |

**The failure ledger is identical in count**; only which legs they land on
differs. One note text is new to this batch — **S_77 ep5, a left kiwi, `fruit
left the pick station during the close (27454 mm)`** — and it is on a
`grasped=False` leg, i.e. **upstream of any carry or place leg** (the place
profile is read only inside `_carry` for a `place*` leg), with a 27.5 m
cross-belt figure that is a recycle/teleport artifact. It is the P41-recorded
non-baseline note for this interface, not a place-profile effect; its C-arm
counterpart (C_77 ep14, left orange) reads `fruit did not follow the gripper`.

### 5.2 One S `cnp` is not the class

S_77 ep10 (orange) is `cnp` with `clean_slip_max = 0.0`, `clr = +23 mm`,
`force_min = 10.02 N`, and it fails the landing check with the **payload still
held**: `place low: bottom 1461 -> 42 mm, drop 70/86 mm, FINGER FLOOR budget
70 mm`, and `res_end = 50.2 mm` against 29-31 mm on the healthy legs. That is a
**place-reach / landing shortfall**, not a loaded slide. C draws no such leg (all
8 of its `cnp`s are payload losses). Stated because it is the one place the S
arm is *not* class-identical: 8 `cnp` in both arms, but S's = 7 losses + 1
reach miss. (The `FINGER FLOOR` budget binds on **every** `place low` row in both
arms — 100 % of 68 descents — so the floor is a standing condition, not the
cause.)

### 5.3 The right (P5)

| | C | S |
|---|---|---|
| right placed | 23/25 = 92 % | 28/30 = 93.3 % |
| right place legs | 23 | 28 |
| right loaded slides (`> 100 mm`) | **0** | **0** |
| right place-leg ticks (median) | 356 | **258** |

No new class, no placed regression, and its legs shorten by the same factor as
registered (§1). Its own `|v|cmd` reads 0.509 on the S arm.

---

## 6. Secondary — space, schedule, signature, cost

### 6.1 `clr` / `clr_edge` (P3: predicted unchanged): **HIT**

The profile changes **when** the pads are where, not **where** they go, and the
matched-distance pairs confirm it. Comparing only legs with the same printed
transit length (13 held pairs, all three seeds):

| distance | `clr` C -> S | `clr_edge` C -> S |
|---|---|---|
| 65 cm | +34 -> **+33** | +38 -> **+37** |
| 61 cm | +45 -> **+36**, +39 -> **+36** | +49 -> +40, +43 -> +40 |
| 58 cm | +18..+49 (4 C legs, 31 mm of within-arm spread) -> +23, +33 | +23..+53 -> +27, +38 |

The **arm medians do fall** (C +36 -> S +24 held legs) but that is **leg mix**, not
the profile: the S arm drew a **53 cm** leg whose transit passes **+4 mm** over the
belt, and the C arm's own four 58 cm legs span 18-49 mm. No held leg goes
negative; the two `-184 mm` readings are the fallen payload's own fall, not the
crossing.

### 6.2 The rotation schedule: commanded identical, achieved ~4 % later

`t45/ticks` reads **0.71-0.81 (C)** against **0.75-0.86 (S)**, i.e. the rotation
happens at the same *fraction* of the leg, ~4 points later, and the absolute tick
scales with the leg (319 -> 223 on matched 65 cm legs, ratio 0.70). `tilt_end`
reads **68-88 deg (C)** against **61-79 (S)**: the achieved attitude lags more at
0.46 m/s, so the wrist has not quite finished its sweep when the shorter leg
ends. The **commanded** pose is unchanged and the path is the same; this is a
*tracking* (achieved) difference at a higher speed and it does not touch the
class — which is the P73 conclusion reproduced.

### 6.3 The escape's signature: unchanged

| arm | `force@onset` | `force_min` | `contacts@onset` | `sep@onset` | `sep_end` |
|---|---|---|---|---|---|
| C (8 losses) | 5.48-11.41 N (7), 0.00 N (1) | **0.00 N (8/8)** | 1 (6), 2 (1), 0 (1) | 59.4-80.5 mm | **41.8-53.7 mm** |
| S (7 losses) | 8.35-10.02 N (5), 27.09 N (1), 0.00 N (1) | **0.00 N (7/7)** | 1 (6), 0 (1) | 54.9-98.2 mm | **17.3-53.7 mm** |

Single-sided clean exit at the pinch's own force, then contact lost and the jaws
closing to 17-54 mm (never the 98 mm open stop) — the W8-B loaded-slide class,
unchanged by the speed. **Both arms carry exactly one `0.00 N / contacts 0` leg**
(the never-held variant: the pads began the leg empty — C_202's has
`onset = loss = 103`, S_101's `clr = -184 mm`), and **S carries one `27.09 N`
leg** whose `sep@onset` is **98.2 mm**, the pads' open stop: a squeeze-out at
force rather than a slip. One leg each; neither changes the class count.

### 6.4 Cost

| | C | S |
|---|---|---|
| left place-leg ticks | 405 (median of 19) | **262 (median of 14)** = **0.65x** |
| `place low` descent ticks | 78 / 79 / 77 | **74 / 74.5 / 73** (-5 %) |
| the descent's start `bottom` | **1472** (1461-1520) | **1460** (1448-1483) → **-12 mm** |
| episode ticks (median) | 1766 / 1808 / 1795 | **1682 / 1674 / 1687** (-84 / -134 / -108, **-5..-7 %**) |

The place leg really is **-143 ticks (-35 %)** and the **episode median falls
~100 ticks (-6 %)**. The `place low` descent is **transit-only by code** and its
ticks fall 5 % anyway, because the faster leg's **achieved** z at the leg's end
is **12 mm** lower (median), so there is 12 mm less to descend — the descent still ends on
the same measured clearance (`bottom -> 38-54 mm`, the shipped release band) and
**the landing class is unchanged** (`did not land` 8 vs 8, `fell off` 0 vs 0).
That is a small real side effect of the tracking lag of §6.2, not of the knob.

---

## 7. The pre-registered predictions, scored

| # | prediction | outcome |
|---|---|---|
| **P1** | the left's loaded-slide legs fall in S | **MISS on the mechanism** (42 -> 50 %, p = 0.73) and an artefact-level hit on the threshold (37 -> 21 %, p = 0.46). **F1 fires** |
| **P2** | place-leg ticks 0.673x, `|v|cmd` 0.342 -> 0.509, `|a|cmd` 0.64-1.04, descent unchanged | **HIT**: 0.65-0.68x, `|v|cmd` **0.343 -> 0.509**, `|a|cmd` **0.30 -> 0.72**; descent -5 % (inside the ±20 % band, cause named in §6.4) |
| **P3** | `clr`/`clr_edge` unchanged ±5 mm, no negative, schedule unchanged | **HIT on matched legs** (-1 / -3 / -9 mm); the arm-median drop is leg mix (§6.1); the schedule's *fraction* is unchanged, the achieved value lags ~4 % (§6.2) |
| **P4** | no new acquisition/`cnp` class, no new reason, no blow-up | **HIT in count** (1/1 left `never-grasped`, 8/8 `cnp`, 8/8 `did not land`, 0 blow-ups); **one note text is new to the batch** and it is on a `grasped=False` leg (§5.1); one S `cnp` is a reach miss, not the class (§5.2) |
| **P5** | the right flat, no right slide | **HIT**: 23/25 vs 28/30, **0 loaded slides in both**, legs 356 -> 258 |

The registered **expansion rule** (seed 77 only if the mechanism read is
consistent, `Δ slides <= -1` and `Δ placed >= 0` and a clean acquisition guard)
**did fire** on seed 77's `2 -> 1` / `2 -> 4`, and seeds 101/202 are what turned
the win into a negative. **That is the phase's methodological point**: this class
needs ≥ 3 seeds before *any* direction is called, and a single-seed 15-pick cell
(the project's usual mechanism cell) can produce a 15-point false positive.

---

## 8. What the phase establishes, and what it closes

**Established:**

1. The place profile's **speed is not a lever** on the left's place-leg loaded
   slide: `loss` **8/19 (42 %) -> 7/14 (50 %)** over a **1.55x** dwell change, and
   **flat against P73's 1.68x-slower arm (50 %)** — a 2.6x range, no trend.
2. **The dwell is not the actuator**, so P73's "time-accumulating loaded creep"
   reading is withdrawn and the sign that produced it does not reproduce in the
   fast direction.
3. **`clean_slip_max > 800 mm` is speed-biased** (§3). The escape count is the
   speed-invariant endpoint, the threshold is not, and the band where a faster
   leg's escapes land is **~660-800 mm**.
4. The escape's **signature is speed-invariant** (§6.3): the same single-sided,
   pinch-force, jaws-closing exit at both dwells.
5. The knob is **clean**: identical failure counts, clean acquisition, flat
   right, no blow-up, `clr` unchanged on matched legs, release geometry
   preserved — at **-35 % of the place leg and -6 % of the episode median**.

**Closes:**

* **The place-profile speed direction** on the place-leg class. Both directions
  are now measured (`0.20` P73, `0.35` P74 C, `0.52` P74 S) and the class is flat
  to all three.
* **The `> 800 mm` threshold as a comparator across speed changes** (it may keep
  being used for height/rotation/retiming, where the remaining-leg length is
  constant).
* With P73, the **place-leg lever space is exhausted for the pose, the rotation
  and the clock** — what remains is `logs/p42/SIM_LIMIT.md`'s two sanctions (**a
  new pad asset**, or **a real-jaw clamp-force anchor**) and a **workstation
  change that shortens the lateral transit at top-down**.

**No adoption, no phase 2.** The speed's *time* saving is real and reproducible
(-143 ticks per left place leg at the same class rate); it is a **throughput**
candidate, not a class fix, and P44/P46 already priced the throughput direction's
cost. If it is ever wanted, it must be argued on **time** with the placement cost
named, and it must be gated on the **escape** count, not the threshold.

**The reference question.** `configs/motion_reference.json` **does not move** —
but not because the knob is direct-scoped: it is **not** (the same
`elif self._dynamic_capture_active:` site runs on the scripted dynamic line,
which is how P44 measured `place0 -135.4 ticks` there). The reference is safe
because **nothing is flipped** and the knob is an `os.environ` read whose shipped
default is unchanged. This phase edits no source and no config, so there is no
re-record to make; verified with `scripts/selfcheck.sh` (§10).

---

## 9. Limits

* **3 seeds, one claim each, 14-19 left place legs per arm.** The pooled
  contrasts cannot exclude a ±25-point effect at this n (Fisher p = 0.73 is
  "no evidence", not "no effect"); what the phase does establish is that the
  **direction is not stable across seeds** (seed 77 says down, 101/202 say up),
  which is what F1 needed.
* **The near-miss band is a reporting boundary, not a mechanism**: the
  `100-800 mm` split is used so a payload loss cannot hide under a threshold, and
  the walk's own speed scaling (§3) is why the primary moved.
* **The C arm is a different draw from P73's C** (the direct loop is not
  reproducible): only the **first** left place leg reproduces (`65 cm, 431 ticks,
  clr +34, clr_edge +38`), then the fruit sequences diverge. All comparisons are
  therefore within this batch, never against P73's counts.
* **The right is a guard, not an endpoint** — 23-28 place legs and 0 losses on
  this branch; a right-arm rate is not measurable here.
* **`|a|cmd` tripled** (0.30 -> 0.72) and the `place` cone stayed at **0.84-0.90x
  of budget** on every left held leg, so the acceleration raise spent no measured
  cone margin — but one **short** right leg (13 cm, velocity term not binding)
  read `cone = 1.61x`; `--strict-cone` is a report on this scenario (it fails on
  the control too, P44 §9.3).
* **Provenance gap (named, not fixed, P73's)**: the manifest still does not record
  `FRUIT_SPEED_PLACE` / `FRUIT_DYNAMIC_PLACE_VMAX`. No store was recorded here, so
  no manifest is contaminated; if the speed is ever used in a recollection, the
  field must go into `assets.scene_provenance` first (the P41/P72 rule).

---

## 10. Reproduce

```bash
bash logs/p74/run_p74.sh                              # C, S at seed 77
SEEDS="101 202" bash logs/p74/run_p74.sh              # the registered expansion
python3 logs/p74/p1_report.py --check logs/p74/direct/{C,S}_77.log   # the gate
python3 logs/p74/p1_aggregate.py logs/p74/direct/{C,S}_{77,101,202}.log
scripts/selfcheck.sh
```

**Pins** (md5 first 6; `logs/` is gitignored - `git add -f` at a close-out):
`logs/p74/PREREG.md` **`1c3546de`**, `PREREG.md5` **`ecdf77e5`**, `header.txt`
**`0d246950`** (the **expansion batch's** copy: the script re-writes the file, so
the seed-77 batch's own header is not on disk - the tree pin set is identical and
is recorded here); `direct/C_77.log` **`b5170c7e`**, `S_77.log` **`4365f202`**,
`C_101.log` **`8eebc3f4`**, `S_101.log` **`b0563207`**, `C_202.log` **`3542bc21`**,
`S_202.log` **`bee13107`**; `p1_report.py` **`14ba847e`**, `p1_report.txt`
**`1503edcc`**, `p1_aggregate.py` **`8f0c584f`**, `p1_aggregate.txt`
**`c44d5b95`**, `run_p74.sh` **`b1254817`**, `logs/selfcheck.log` **`e581667b`**;
`src/fruit_sorting/tasks.py` **`adcfd348`** and `rl_env.py` **`157e6d85`**
**unchanged by this phase**, `configs/motion_reference.json` `8952c320` and
`..._twoline.json` `eb697f23` **untouched**, checkpoint `moe_v13s` `61da390a`.
