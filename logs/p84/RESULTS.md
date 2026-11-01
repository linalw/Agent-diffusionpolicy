# P84 — fail fast on the two-line: the abort is clean, the line already truncates, and whether the overlap absorbs it is a seed flip

Registered in `logs/p84/PREREG.md` (**md5 `62c94cdcef07bf3f8a7aa61ebde0049d`**, pinned
before the phase's first run, unchanged since). **Measurement only: nothing
adopted, no default changed, no commit, no `src/` edit, `configs/` untouched**
(`8952c320` / `eb697f23` both stand). This is P83's **registered re-entry**
(`logs/p83/RESULTS.md` §8): the same knob, on the scenario where an arm parks on
the *other arm* instead of on the belt.

Owner directive: *P83's mechanism lost on the single arm because the abort
re-times the presentation; measure it where the scheduler overlaps two arms.*

## 0. The answer in one table

The shipped two-line scenario (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`), 20
attempts, the P80 instrumentation set **plus the tracker and the park trace on
both arms** (`FRUIT_CARRY_DIAG=1 FRUIT_BIARM_PARK_TRACE=1`), one claim per run:

| arm | seed | placed | s/att | interval mean / p90 | **failed attempt** | placed/min **window** | placed/min **batch** | wall/pick | wall/sim | placed/min **wall** | trips | starved polls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **D5** control | 5 | **16/20** | 9.70 | **10.77 / 18.00 s** | **13.35 s** (n=4) | **5.57** | **4.96** | 16.83 s | 1.74 | **2.85** | 0 | 44 |
| **F5** fail-fast | 5 | **10/20** | **8.90** | **14.39 / 21.60 s** | **11.58 s** (n=10) | **4.17** | **3.36** | 14.92 s | 1.67 | **2.01** | **8** | **53** |
| **D6** control | 6 | **10/20** | 9.70 | **19.34 / 35.60 s** | **12.22 s** (n=10) | **3.10** | **3.11** | 15.59 s | 1.61 | **1.92** | 0 | 33 |
| **F6** fail-fast | 6 | **15/20** | **9.50** | **12.21 / 17.10 s** | **9.60 s** (n=5) | **4.92** | **4.74** | 15.88 s | 1.67 | **2.83** | **4** | 33 |

* **The abort works on the two-line exactly as it did on the single arm.**
  12 trips (8 + 4), every one on a payload that was already gone, **45 carry legs
  of the 25 placed attempts read `ticks = X/X`** — not one placed leg shortened —
  and a placement is not slower (`15.51 -> 15.62 s` at seed 6; the seed-5
  `15.78 -> 15.17` is the leg mix, §2). §3.
* **It buys less time than on the single arm, and the reason is measured**: the
  shipped two-line **already truncates a lost attempt twice** — the
  `not result.grasped` return right after the lift, and the **P10-C carry
  monitor** (armed by default in a two-line session), which ends the *next* leg
  at its boundary. The fail-fast's increment is therefore only the rest of the
  tripping leg: **-1.48 / -1.20 s on a never-grasped attempt** and **-3.34 s on a
  `cnp`** (seed 6, the only seed whose control drew `cnp`), against P83's
  **-5.14 s** on a control that had no monitor. §2.
* **The delivered interval is a seed flip**: **+33.6 %** at seed 5 and
  **-36.9 %** at seed 6 (pooled **-11.7 %**), and the pooled count is a **wash**
  (26/40 -> 25/40). The **idle, the lock-on and the right arm's park-gate wait
  fall at seed 6 and rise at seed 5** — the "the overlap absorbs the abort"
  hypothesis is **supported at one seed and refuted at the other**. §4.
* **The registered rule's verdict is NOT ADOPTED**: M1 fails on G4's letter
  (11/12 trips), M2 fails at both seeds (-1.77 / -2.62 s against a 3.0 s bar),
  M3 fails on G3's seed-5 letter and on the same G4 letter, and T1 and T2 fail
  at seed 5 (§7).

## 1. The arms, and the branch identity (G1)

Every arm: `HEADLESS=1 ATTEMPTS=20`, `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`,
`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_BIARM_PARK_TRACE=1`; seeds 5 and 6; the two-line's own supply package (dense
wave sheet, balanced A:B:C, pure routing) left at its shipped default; the P71
rails at `none`. The treatment adds `FRUIT_FAIL_FAST=150` and nothing else.
Interleaved **D5, F5, D6, F6**, one `scripts/154_claim_run.sh` claim each, wall
stamped per line (`logs/p84/stamp.py`, a byte copy of P80's; md5 `fae805cd`).

**Both arms carry the tracker and the park trace**, so the A/B is
*tracker + park trace* vs *tracker + park trace + abort*. That the instrument is
neutral is **re-proved here on this line**, not borrowed from P83's single arm:

| check | result |
| --- | --- |
| **D5** vs P80's `T20` (seed 5) | **IDENTICAL**, 865/865 physics `[fruit]` lines |
| **D6** vs P80's `T6` (seed 6) | **IDENTICAL**, 814/814 physics `[fruit]` lines |
| rows dropped by the identity test | `[fruit] [carry]` 36/32, `[diag] carry-assist` 108/96, `[biarm] … park` 60/60 |

So the two-line's physics is byte-identical to P80's with both instruments on,
and the control reproduces P80's published numbers exactly — interval
`10.77 / p90 18.00`, window `5.57`, batch `4.96`, idle `18 %/21 %`, lock-on
`3.83 / 4.54 s` with 19 retries each, starved polls `25 + 19` at seed 5, and
`19.34 / 3.10 / 3.11` at seed 6. **P80's T20/T6 are re-derived, not re-quoted.**

The tree is P83-final (HEAD `1a2eec2`); the only difference from P80's records is
P82's `bimanual.py` wake-on-request, which these two identities show does not
move this scenario.

## 2. The mechanism: -5.14 s did not transfer, and the line says why

### 2a. The saving by failure class (E9, `[cycle]` + `[run]` spans)

| seed | class | control | treatment | delta |
| --- | --- | --- | --- | --- |
| 5 | placed | 15.78 s (n=16) | 15.17 s (n=10) | -0.61 (leg mix) |
| 5 | `cnp` | **n=0** | 11.15 s (n=4) | not comparable |
| 5 | never-grasped | 13.35 s (n=4) | 11.87 s (n=6) | **-1.48 s** |
| 6 | placed | 15.51 s (n=10) | 15.62 s (n=15) | **+0.11 s** |
| 6 | `cnp` | 11.54 s (n=5) | 8.20 s (n=3) | **-3.34 s** |
| 6 | never-grasped | 12.90 s (n=5) | 11.70 s (n=2) | **-1.20 s** |

### 2b. Why a never-grasped attempt only gives back 1.2-1.5 s

`tasks.py` returns right after the lift when the peak lift is below 0.05 m
(`if not result.grasped: … return result`) — so the **shipped** line never runs
the place leg, the release or the return on that class, and the abort can only
recover the tripping leg's remainder plus its 50-tick tail. The `[cycle]` rows
say it in the log's own terms: every never-grasped attempt, control and
treatment, has **no `place`/`release`/`return` segment** (4/4 and 5/5 in the
controls), and the treatment's failed attempts total **12.25 s (F5)** against a
shipped **13.34 s (D5)**.

### 2c. Why a `cnp` gives back 3.3 s and not 5.1 s

There are exactly **two** early returns between `result.grasped` and the place
leg (`_attempt_ended_early()` and `not result.grasped`), so a control attempt
with `grasped=True, placed=False` and **no `place` segment must have been ended
by the P10-C carry monitor** — which `_resolve_carry_monitor_knobs` resolves
**on for a two-line session with the env unset** (monitor `1`, two-line scope
`1`, confirm `8.0 mm`, floor `3.5`). Measured: **3 of D6's 5 `cnp` attempts have
no place leg** (9.1-10.3 s attempts) and one more stops at the place boundary,
so the shipped line had *already* removed most of what the fail-fast targets.
P83's control — the single arm — has the monitor at its shipped `0`, which is
exactly why the same knob was worth **5.14 s** there and **1.2-3.3 s** here.

**This is the re-entry's answer, and it is a property of the scenario, not of the
lever**: the two-line does not "hold the abort's savings in reserve" — it has
already spent them.

## 3. The abort audit (E9 / G4 / G5)

**12 trips** (F5 8, F6 4). Every trip's `clean_slip` is just over the threshold
(150.8-161.1 mm; the one exception is F5's never-held payload, which trips at
**354.4 mm on the very first tick**), and **11 of 12** read the registered pair
exactly — `force = 0.00 N` **and** `contacts = 0` at the trip tick, with
`force_min = 0.00 N` over the leg:

| arm | trip | leg | tick / length | clean_slip | sep / gap | force / force_min | contacts | onset / loss | d (mm) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F5 | 1 | grasp_lift | t97/154 | 151.4 | 39.5 / 39.5 | 0.00 / 0.00 | 0 | 2 / 72 | (-65.0, -52.3, +126.4) |
| F5 | 2 | grasp_lift | t1/169 | 354.4 | 17.0 / 17.0 | 0.00 / 0.00 | 0 | 1 / 1 | (-278.4, -144.6, +165.0) |
| F5 | 3 | **place0** | t147/396 | 159.4 | 57.1 / 56.3 | 0.00 / 0.00 | 0 | 103 / 132 | (+29.1, +88.5, +129.4) |
| F5 | 4 | grasp_lift | t21/193 | 156.7 | 37.4 / 37.3 | 0.00 / 0.00 | 0 | 1 / 1 | (-80.2, -16.0, +133.6) |
| F5 | 5 | grasp_lift | t73/153 | 161.1 | 10.0 / 9.0 | 0.00 / 0.00 | 0 | 2 / 69 | (-104.2, -35.0, +117.7) |
| F5 | 6 | grasp_lift | t52/163 | 155.5 | **9.9 / -2.2** | **9.33** / 0.00 | **1** | 1 / 1 | (-63.6, -29.1, +138.8) |
| F5 | 7 | grasp_lift | t30/114 | 152.5 | 23.8 / 23.8 | 0.00 / 0.00 | 0 | 1 / 1 | (+13.2, -150.3, +22.1) |
| F5 | 8 | **place0** | t59/374 | 156.4 | 52.8 / 52.1 | 0.00 / 0.00 | 0 | 3 / 41 | (-2.4, +54.3, +146.7) |
| F6 | 1 | grasp_lift | t46/380 | 155.4 | 29.8 / 29.8 | 0.00 / 0.00 | 0 | 4 / 4 | (+152.4, +30.3, +2.9) |
| F6 | 2 | grasp_lift | t26/112 | 152.0 | 47.8 / 47.8 | 0.00 / 0.00 | 0 | 1 / 1 | (+27.9, -147.6, +23.5) |
| F6 | 3 | grasp_lift | t106/171 | 150.8 | 28.4 / 27.6 | 0.00 / 0.00 | 0 | 78 / 87 | (-13.2, +10.3, +149.8) |
| F6 | 4 | grasp_lift | t116/161 | 151.2 | 63.8 / 63.0 | 0.00 / 0.00 | 0 | 54 / 103 | (-35.8, +68.4, +130.0) |

* **G5 PASSES**: 45 carry legs on 25 placed attempts, all `ticks = X/X`; the
  worst placed-leg `clean_slip` is **0.1 mm (F5) / 0.4 mm (F6)** against the
  150 mm threshold, and the controls' is 1.8 / 0.2 mm.
* **G4 FAILS by its letter on F5 trip 6** (`force = 9.33 N`, `contacts = 1` at
  the trip tick). The audit says what it is: the payload is **138.8 mm above the
  pads** (`d` z = +138.8), the tracker's `loss_row = onset_row = 1` and
  `force_min = 0.00 N`, and the pads are at a **measured 9.9 mm separation with
  a `gap = -2.2 mm` command** — i.e. the servo drove them into each other and
  the 9.33 N is the **pads pressing each other**, not a held fruit. No 36 mm
  fruit fits in a 9.9 mm gap. The registry keeps the letter as a failure; the
  mechanism is not "a live pinch tripped".
* Two trip families, both real losses: **10 of 12** in the `grasp_lift` (the
  W8-B loaded slide and the never-held payloads) and **2 of 12** inside
  `place0` — the ones that save the most, because the release (2.36 s) and the
  return (0.64 s) blocks also do not run.
* **The trip is a clean leg cut, visible in the log's own rows**: the leg reads
  `[carry] … ticks=<trip+1>/<total>` and the `[fail-fast]` row records the
  remainder (`107-365` ticks at F5, mean 204 = **1.70 s**; `95-384` at F6, mean
  182 = **1.52 s**).

## 4. Where the freed time went — and why the answer flips with the seed

The two-line's interval is *not* `attempts/placement x span + idle`; two arms
overlap. The measured decomposition (E1-E6) is:

| seed | arm | interval | attempts/placement | mean span | arms busy | mean idle | lock-on | starved polls | right park-gate wait |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | **D5** | **10.77 s** | 1.25 | 15.30 s | 1.58 | **19.8 %** | **4.19 s** | 44 | **7.1 s** |
| 5 | **F5** | **14.39 s** | 2.00 | 13.38 s | 1.50 | **23.5 %** | **4.58 s** | **53** | **9.1 s** |
| 6 | **D6** | **19.34 s** | 2.00 | 13.87 s | 1.44 | **24.4 %** | **5.04 s** | 33 | **21.8 s** |
| 6 | **F6** | **12.21 s** | 1.33 | 14.12 s | 1.49 | **21.7 %** | **4.39 s** | 33 | **13.6 s** |

* **Seed 6 is the hypothesis**: the interval falls **-36.9 %**, both sim
  denominators rise (`3.10 -> 4.92` window, `3.11 -> 4.74` batch), the placed
  count rises 10 -> 15, and every *waiting* term falls — idle **-2.7 pt**,
  lock-on **-0.65 s**, the right arm's park-gate wait **21.8 -> 13.6 s** (the
  parked arm is released earlier because the other arm's attempt ends earlier),
  starved polls flat at 33. The freed 1.7 s per failure became **occupancy**.
* **Seed 5 is the refutation**: the interval rises **+33.6 %**, both sim
  denominators fall (`5.57 -> 4.17`, `4.96 -> 3.36`), the placed count falls
  16 -> 10, and every waiting term rises — idle **+3.7 pt**, lock-on **+0.39 s**,
  starved polls **44 -> 53**, the right arm's park-gate wait **7.1 -> 9.1 s**.
  The freed time became **waiting for the belt**, and the right arm's own
  interval went 26.52 -> 47.80 s on 3/10 placed against 7/10.
* **The pooled read is a wash on the count and a fall on the interval**:
  placed **26/40 (65.0 %) -> 25/40 (62.5 %)**, interval mean **-11.7 %**,
  window **4.34 -> 4.54**, batch **4.03 -> 4.05**, wall **2.39 -> 2.42**.

**Which seed is the lever's?** Neither, and the registration says so (R0/R1/R5).
The cell's **own control** swings 16 -> 10 placed between the two seeds (P80 §7b
measured the same 1.27x / 0.73x count swing for T20/T6), so a 20-attempt A/B
whose treatment also re-times the presentation cannot separate "the abort's
branch is harder/easier" from "the branch is harder/easier". What *does* hold at
both seeds is the per-attempt mechanism (§2a) and the trip audit (§3) — and they
are small on this line for a measured reason (§2b/§2c).

## 5. The wall (E11) — reported, within this batch only

| arm | wall | wall/pick | sim/pick | wall/sim | placed/min wall |
| --- | --- | --- | --- | --- | --- |
| D5 | 336.7 s | 16.83 s | 12.08 s | 1.74 | **2.85** |
| F5 | 298.3 s | **14.92 s** | 17.87 s | 1.67 | **2.01** |
| D6 | 311.8 s | 15.59 s | 19.32 s | 1.61 | **1.92** |
| F6 | 317.7 s | 15.88 s | 12.67 s | 1.67 | **2.83** |

**`wall/pick` falls at seed 5 (16.83 -> 14.92 s) and the wall rate falls too
(2.85 -> 2.01 placed/min)** — P83's read rule, unchanged: a run that places less
divides a smaller wall by a smaller count. At seed 6 both rise. **P82's
wake-on-request ships default on**, so the wall/sim here is **1.61-1.74**
against P80's recorded 2.57; P80's wall column is a different harness and is not
compared.

## 6. The guards (PREREG §5) — every one measured

| # | guard | verdict | evidence |
| --- | --- | --- | --- |
| **G1** | tracker + park trace neutral on this line | **PASS at both seeds** | `D5` = `T20` **865/865**, `D6` = `T6` **814/814** physics `[fruit]` lines, diag rows dropped (§1) |
| **G2** | in-batch prefix identity | **PASS at both seeds** | the treatment's **first new line is the `[fail-fast]` trip row itself** (`F5` at line 95, `F6` at line 101; 865/858 and 814/835 lines) |
| **G3** | no new failure reason | **PASS pooled; FAIL by its letter at seed 5** | pooled over the two seeds the treatment's set is a subset of the control's; at seed 5 alone the label `grasped, not placed (no note)` appears in F5 and not in D5 — because **D5 drew zero `cnp`** (4/4 never-grasped) while D6 drew 5, so it is a class this seed's control never produced, not a new text |
| **G4** | trips only on a lost payload | **FAIL by its letter (11/12)** | §3: F5 trip 6 reads `force 9.33 N / contacts 1` with the payload 138.8 mm above the pads and the pads jammed at `sep 9.9 mm / gap -2.2 mm` |
| **G5** | no placed leg shortened | **PASS** | 45/45 carry legs of 25 placed attempts `ticks = X/X`; worst placed `clean_slip` 0.1 / 0.4 mm |
| **G6** | the two-line motion gate, same attempt count | **PASS** | `D5` -> `190` **PASS** against `logs/p80/motion_reference_twoline_p80_20.json` (20 attempts, floor 0.5, fingerprint **matches**, 16/20); `D6` -> **PASS** against its own seed's reference written from P80's own `T6` (`logs/p84/motion_reference_twoline_T6_20.json`, md5 `d4c9f1e4`, fingerprint **matches**, 10/20 at the floor); the treatments are **DIFFERS by construction** (the abort re-times the presentation) and are gated on **motion budgets only** — `105 --min-success-rate 0.0` **exit 0** on both, worst descent `|v|max` **0.110-0.132** against the 0.160-0.161 budgets and lurch **0.019-0.036** against 0.291 for all four arms, with `a_win5` 1.09-2.37 reported as the dynamic line's roughness warning (never gated) |
| **G7** | no wedge, nothing lost | **PASS** | four runs, exit 0, no `TIMEOUT`, `attempts = placed + failed` on every arm (20 = 16+4, 10+10, 10+10, 15+5), `diverted` **1 / 3 / 2 / 1** |
| **G8** | the worker's abort path is the one it already handles | **PASS** | every tripped attempt prints its normal `[biarm] result …` row, is parked afterwards (`[biarm] … park` rows, 10 per arm per run), and the same arm's next attempt is a normal attempt: **after a trip, that arm's next attempt placed 3/4 (F6) and 4/7 (F5)**, with 2 of F5's 3 non-placements being themselves trips (`logs/p84/timeline.py`) |

## 7. The registered decision (PREREG §6)

**Mechanism gate**
* **M1 = G4 + G5 → FAIL** on G4's letter (§3); G5 passes 45/45.
* **M2 = the failed attempt's own span falls >= 3.0 s at both seeds → FAIL**:
  `13.35 -> 11.58 s` (**-1.77 s**) and `12.22 -> 9.60 s` (**-2.62 s**). The
  direction replicates; the bar is P83's, and §2 measures why it does not
  transfer (the class mix and the monitor).
* **M3 = G1, G2, G3, G6, G7, G8 → FAIL** on the two registered *letters*:
  **G3 at seed 5** (§6) and **G4's trip pair** (which also carries M1, §3) —
  `G1, G2, G5, G6, G7, G8` all pass, and G3 passes **pooled** over the two seeds.

**Throughput gate**

| | seed 5 | seed 6 | pooled | bar |
| --- | --- | --- | --- | --- |
| **T1** interval | 10.77 -> **14.39 s (+33.6 %)** | 19.34 -> **12.21 s (-36.9 %)** | **-11.7 %** | per-seed <= -3 % at both, pooled <= -8 % → **FAIL** (seed 5) |
| **T2** mean per-arm idle | 19.8 -> **23.5 % (+3.7 pt)** | 24.4 -> **21.7 % (-2.7 pt)** | — | falls at both → **FAIL** (seed 5) |
| **T3** placed/min | — | — | window **4.34 -> 4.54**, batch **4.03 -> 4.05**, wall **2.39 -> 2.42 (+1.4 %)** | both sim denominators up, wall >= -5 % → **PASS** |

> **Verdict: NOT ADOPTED.** The lever does exactly what it was built to do —
> every trip is on a payload that is already gone (11/12 read the registered pair
> exactly; the 12th is the pads pressing **each other** with the payload 138.8 mm
> above them, §3), no placed leg is shortened, and the failed attempt **always**
> gets shorter (-1.20 to -3.34 s by class) — and on this scenario the delivered
> interval **flips sign between the two registered seeds** while the pooled count
> is unchanged. `FRUIT_FAIL_FAST` stays **default off**; no default changes, no
> `src/` edit, no commit.

**What would reopen it.** A design whose control does not swing 10-16/20: a
**third seed** (the registered next spend), or a **count-matched / paired**
cell, or the **class-matched** endpoint the P83 census already licenses
(`cnp` only, where the saving is -3.34 s). None of those is spent here.

## 8. What this phase does not claim (residuals)

* **No default change, no adoption, no commit, no `src/` edit, `configs/`
  untouched.**
* **The count is not a rate.** 26/40 vs 25/40 pooled, with the per-seed pair
  moving in opposite directions; and the cell's own control moves 16 -> 10
  between seeds (P80 §7b's 1.27x / 0.73x swing).
* **The two-line's P10-C monitor is inferred from the code path, not from its
  own diag**: a `grasped=True` attempt with no `place` segment can only be
  `_attempt_ended_early()`, and the fail-fast is off in the control — the
  "which legs" read would need one `FRUIT_CARRY_MONITOR_DIAG=1` run, which was
  not spent.
* **The 3.0 s M2 bar is P83's**, calibrated on a class mix the two-line does not
  draw (and on a line whose monitor is off). It is reported as failed; the
  per-class numbers are the transferable read.
* **Seed 5's control drew zero `cnp`**, so the class that pays the most is
  measured at seed 6 only.
* **The wall is a harness number**, and P82's flip moved it; it is quoted
  within-batch only.
* **P80/P81's two-line rate claims are untouched** — this phase re-derived their
  seed-5/6 controls bit-identically and changed nothing.

## 9. Evidence and pins

* PREREG `logs/p84/PREREG.md` (**`62c94cdc…`**) + `PREREG.md5`; the battery
  `logs/p84/run_p84.sh` + `battery_driver.log`; the one-run/wall contract
  `logs/p84/one_run.sh` + `stamp.py` (byte copy of P80's, `fae805cd`); the gates
  `logs/p84/gates.sh`.
* Report `logs/p84/p84_report.py` -> `p84_report.txt` (sections 0-10; every
  registered guard is computed there, and `--check` would exit 1 on this
  verdict by design). Post-hoc reads: `logs/p84/timeline.py` (the per-attempt
  timeline and the after-a-trip cascade).
* Logs + stamps: `logs/p84/{D5,F5,D6,F6}.{log,stamps,driver.log}`; gates
  `{D5,D6,F5,F6}.gate`, `D6.gate_t6`, `{D5,D6,F5,F6}.budgets`.
* References: `logs/p80/motion_reference_twoline_p80_20.json` (P80's, untouched)
  and **`logs/p84/motion_reference_twoline_T6_20.json`** (`d4c9f1e4`, written
  from P80's own `T6.log` — a per-seed reference, in `logs/`, **not**
  `configs/`).
* `scripts/selfcheck.sh` **PASS, 0 failures** (1 skip: the motion-budget leg
  needs a fresh log). No new selfcheck leg: this phase adds no `src/` code.
* Pins: `tasks.py` **`f1e44af6`**, `bimanual.py` **`7e2b7d7e`**, `rl_env.py`
  `d786279c`, `fruits.py` `c7461d41`, `configs/motion_reference.json`
  **`8952c320`** and `configs/motion_reference_twoline.json` **`eb697f23`**
  both untouched, ckpt `moe_v13s` `61da390a`.
