# P81 — the two-line's scheduler on the single arm's supply: the clock is the scheduler's, the feed and the overlap strength are the package's

Registered in `logs/p81/PREREG.md` (**md5 `461e170964fe343b20a3f0f52580031e`**, pinned
before any run, unchanged since). **Measurement only: nothing adopted, no default
changed, no commit, `configs/` untouched.** Owner's cell: separate the two-line's
**scheduler** from its **supply package**.

## 0. The answer

**The 1.88x clock is the scheduler's own; the package is what feeds the right arm and
keeps the overlap strong — and the delivered interval/rate needs it.** Measured on the
single arm's shipped scattered supply (`FRUIT_SUPPLY_WAVE=0`, the 50/30/20 mix from the
code default, pure routing unchanged), 20 attempts, seeds 5 and 6:

| | seed 5: S / Tp / T | seed 6: S / Tp / T |
| --- | --- | --- |
| placed | 12/19 / **10/20** / 16/20 | 13/19 / **13/20** / 10/20 |
| `s/attempt` | 15.10 / **10.10** / 9.70 | 15.00 / **9.90** / 9.70 |
| clock (batch sim s / attempt) | 18.19 / **10.13** / 9.67 | 18.06 / **9.94** / 9.66 |
| **clock ratio S/Tp (S/control)** | **1.80x (1.88x)** | **1.82x (1.87x)** |
| interval mean / p90 | 26.72/36.9 / **19.47/47.0** / 10.77/18.0 | 26.12/38.5 / **14.43/23.9** / 19.34/35.6 |
| placed/min **window** | 2.25 / **3.08** / 5.57 | 2.30 / **4.16** / 3.10 |
| placed/min **batch** | 2.08 / **2.96** / 4.96 | 2.27 / **3.92** / 3.11 |
| **starved polls** (L+R) | 0 / **126 (14+112)** / 44 (25+19) | 0 / **67 (26+41)** / 33 (16+17) |
| right slot no-eligible | — / **93.3 %** / 65.5 % | — / **82.0 %** / 63.0 % |
| idle left / right | 17 % / **21 % / 43 %** / 18 % / 21 % | 17 % / **26 % / 28 %** / 19 % / 30 % |
| wall/pick, wall/sim | 25.2, 1.38 / **25.1, 2.48** / 24.9, 2.57 | 25.2, 1.40 / **24.9, 2.51** / 23.8, 2.47 |
| wall placed/min | 1.51 / **1.20** / 1.93 | 1.63 / **1.57** / 1.26 |

* **The clock survives without the package.** The two-line still overlaps attempts at
  **1.80x / 1.82x** the single arm's batch sim seconds per executed attempt (pooled
  **1.81x**), against **1.88x / 1.87x** with its own package — **96 % / 97 %** of the
  package-on clock, inside the pre-registered [1.75, 2.00] band at **both** seeds. The
  net clock does not need the package.
* **The overlap strength and the feed do.** The mean number of arms inside an attempt
  falls **1.58 -> 1.30** at seed 5 (seed 6: 1.44 -> 1.42, unchanged), the right arm's
  slots report no eligible fruit on **93.3 % / 82.0 %** of polls (package-on
  **65.5 % / 63.0 %**), its idle is **43 %** (seed 5) and its lock-on **11.24 s**
  (p90 23.10, 103 polls). The starvation rise is robust at **2.86x / 2.03x** the
  package-on polls per attempt.
* **But the package's *count* is a seed draw, not a stable gain.** Package-off vs
  package-on: **10 vs 16** at seed 5, **13 vs 10** at seed 6; pooled **23/40 vs 26/40**
  (and vs the single arm **10 vs 12**, **13 vs 13**). P80's 1.27x / 0.73x count factor
  is the same draw, now read from the other side.
* **The registered rule returns D2 — package required** — on its *interval and
  starvation* clauses (seed 5: interval 19.47 s, S-poll, S-idle; seed 6: S-poll), while
  its four clock/count clauses pass at seed 6 and three of four at seed 5. **Read the
  two halves separately: the net clock is scheduler-only; the delivered interval/rate
  is package-required.** Both are in §3-§4; neither is softened.
* **On this harness's wall the package-off two-line is below the single arm**:
  1.20 vs 1.51 (0.79x) at seed 5, 1.57 vs 1.63 (0.96x) at seed 6, **1.38 vs 1.57 pooled
  (0.88x)** — because wall/sim is 2.48-2.51 for the two-line against 1.38-1.40 for the
  single arm (P80 §6). On sim it is above the single arm (window 1.37x / 1.81x; pooled
  batch 3.44 vs 2.18 = 1.58x); on wall it is not.

## 1. The arms, and the package-off proof

Every run is `HEADLESS=1 ATTEMPTS=20`, one `scripts/154_claim_run.sh` claim,
`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1` on both arms, wall stamped per line with
`logs/p81/stamp.py` (the byte copy of P80's instrument, md5 `fae805cd…`).

* **Tp5 / Tp6** = `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_WAVE=0` at seeds
  5 / 6. **No `FRUIT_SUPPLY_GRADES`** is set: the 50/30/20 comes from the shipped code
  default, so it cannot be a typed-in mix.
* **Controls are P80's records**, not re-runs (the code md5s are identical; PREREG §0):
  `logs/p80/{S20,T20,S6,T6}.log` — the single arm and the two-line **with** its package.

**The proof the package is off** (PREREG F1; the full rows in
`logs/p81/supply_proof.txt` and `p81_report.txt` §1). There is no A:B:C *file* in the
tree — the balanced mix is code, selected by
`fruits.py:629` `balanced = (wave or patch or bed) and FRUIT_BIARM_TWOLINE == "1"`;
with `wave=0` (and no patch/bed) that is `False`, so `SUPPLY_GRADES` (50/30/20,
`fruits.py:261`) is used. The runtime row is the proof:

```
[fruit] [supply] scatter pool=16 seed=5 gaps=0.10-0.35 m lateral x=0.20-0.36 m
stream=on target=0 wave=off grades=A:0.5,B:0.3,C:0.2 classes=strawberry:2,...
```

`wave=off` and `grades=A:0.5,B:0.3,C:0.2` on **both** seeds, and **0 rows** contain
`A:0.375` in either log (the two-line's balanced mix). The two-line banner and the
routing are unchanged: `left station y=+0.000, right station y=-0.100`, and
`left A=12 B=0 C=0; right A=0 B=8 C=0; C picked=0; pure=on` (Tp5; Tp6 is 11/9) — the
cell separates the **supply schedule/mix**, not the routing.

## 2. The clock: 1.80x / 1.82x, and what that number contains

The registered clock is P80's identity, **batch sim span / executed attempt** (not
`s/attempt`, which is the within-attempt clock): `18.19 / 10.13 = 1.80x` (seed 5),
`18.06 / 9.94 = 1.82x` (seed 6), pooled `1.81x`; the package-on controls read
`1.88x / 1.87x` (pooled 1.88x).

The decomposition the rule was written to expose (`p81_report.txt` §2):

| seed | mean attempt span S / Tp / T | concurrency S / Tp / T | clock S/Tp (S/T) |
| --- | --- | --- | --- |
| 5 | 15.09 / **13.21** / 15.30 s | 0.83 / **1.30** / 1.58 arms | 1.80x (1.88x) |
| 6 | 14.96 / **14.07** / 13.87 s | 0.83 / **1.42** / 1.44 arms | 1.82x (1.87x) |

* **The successful attempt is not shortened**: placed-only mean spans are **15.64 /
  16.15 s** (Tp5 / Tp6) against the package-on **15.78 / 15.51** and the single arm's
  **15.05 / 15.15** — P80's "the two-line overlaps attempts, it does not make one
  faster" holds at seed 5, and the seed-6 package-off mean is 1.0 s *longer* than the
  single arm's (not a shortening; both arms' left placements run ~16 s there).
* **At seed 5 the overlap itself weakens**: 1.30 arms busy against the package-on 1.58
  (and the single arm's 0.83) — a **1.57x** concurrency ratio against **1.90x**. The net
  clock stays at 1.80x because the package-off arm's **failed attempts are shorter**
  (10.79 s mean vs the control's 13.35 and the single arm's 15.16): with the control's
  attempt-length factor held fixed, the seed-5 clock would read **~1.55x**, not 1.80x.
  So the net figure at seed 5 carries a class-mix tailwind, not a scheduler gain.
* **At seed 6 the overlap is unchanged** (1.42 vs 1.44 arms) and the net clock differs
  only by attempt length (14.07 vs 13.87, both arms' failures) — 1.82x vs 1.87x.
* **The answer to the question as asked**: the **net clock is the scheduler's** (it
  reproduces at 96-97 % of the package-on value on a supply that is not its package);
  the **overlap strength** is what the package protects, and at seed 5 it is 18 %
  weaker without it.

## 3. The delivered side: starvation, both denominators, and the wall

**Starvation is the robust package effect, and it is the right arm's B lane.** The
two-line worker re-polls every ~0.5 s and parks, so the package-on arm already carries
44 / 33 starved polls; the package-off arms carry **126 / 67** (per attempt **6.30 vs
2.20**, **3.35 vs 1.65**). The 175 read localises it:

| arm | left no-eligible / slots | right no-eligible / slots |
| --- | --- | --- |
| T20 (package) | 25/35 = 71.4 % | 19/29 = 65.5 % |
| **Tp5 (package off)** | **14/26 = 53.8 %** | **112/120 = 93.3 %** |
| T6 (package) | 16/26 = 61.5 % | 17/27 = 63.0 % |
| **Tp6 (package off)** | **26/37 = 70.3 %** | **41/50 = 82.0 %** |

The left is fed A (50 % of the sparse pool) and its slot-starvation is mixed (53.8 % vs
the control's 71.4 % at seed 5, 70.3 % vs 61.5 % at seed 6); the right is fed B only
(30 % of the pool, and the mean gap is
1.8x wider than the wave sheet), so its B arrival rate falls **2.25x** (3/m -> 1.33/m)
— exactly the pre-registered prediction. The v9-era "bimanual on the shipped scattered
supply is structurally starved" (74 % of station slots) reproduces here as **93.3 % /
82.0 % of the right's polls**, and the mechanism is the mix+routing, not the scheduler.

**Both denominators and the wall** (per seed, and pooled over the two seeds):

| rate | S | Tp | T (package) |
| --- | --- | --- | --- |
| **window** placed/min (seed 5 / 6) | 2.25 / 2.30 | **3.08 / 4.16** | 5.57 / 3.10 |
| **batch** placed/min (seed 5 / 6) | 2.08 / 2.27 | **2.96 / 3.92** | 4.96 / 3.11 |
| **wall** placed/min (seed 5 / 6) | 1.51 / 1.63 | **1.20 / 1.57** | 1.93 / 1.26 |
| pooled batch (sim) | 2.18 | **3.44** | 4.04 |
| pooled window (sim, mean of seeds) | 2.27 | **3.62** | 4.34 |
| pooled wall | 1.57 | **1.38** | 1.60 |

* On **sim** the package-off line stays above the single arm (**1.37x / 1.81x** window;
  pooled batch **1.58x**), because its clock is intact even with the count draw.
* On **wall** it is **below** the single arm at both seeds (0.79x / 0.96x; pooled
  **0.88x**): the two-line pays 2.48-2.51x of wall per simulated second here, the
  single arm 1.38-1.40x (P80 §6). The sim advantage is real; this machine's harness
  cancels it.
* The **count** is not a package gain at either seed in the same direction: **10 vs 16**
  (package-on) and **13 vs 10**, pooled **23/40 vs 26/40**; against the single arm it is
  **10 vs 12** and **13 vs 13**. The interval follows the count by construction
  (`interval = 60 / window rate`), which is why the 12 s interval clause is a *delivered*
  clause, not a clock clause.

Class split (reported, not gated): Tp5 **10 placed / 6 cnp / 4 never-grasped** (left
7/4/1, right 3/2/3); Tp6 **13 / 4 / 3** (left 6/3/2, right 7/1/1). The controls are
T20 **16 / 0 / 4** and T6 **10 / 5 / 5**; the single arm S20 **12 / 7 / 0**, S6
**13 / 5 / 1**. No new failure reason appears: the notes are the recorded
`grasped, not placed (no note)` and `fruit did not follow the gripper` classes.

## 4. The decision rule, clause by clause

Fixed in PREREG §4 before the runs: D1 = s/attempt <= 11 s, interval <= 12 s (or <= the
same-seed control), clock ratio in [1.75, 2.00], window rate > the single arm's — all at
both seeds; D2 = any D1 failure, or starvation per attempt >= 1.25x the control, or
either arm's idle >= 1.5x the control.

| clause | seed 5 | seed 6 |
| --- | --- | --- |
| D1.1 `s/attempt` <= 11 | **PASS** (10.10) | **PASS** (9.90) |
| D1.2 interval <= 12 s or <= control | **FAIL** (19.47 vs 12 / 10.77) | **PASS** (14.43 <= 19.34) |
| D1.3 clock ratio in [1.75, 2.00] | **PASS** (1.80) | **PASS** (1.82) |
| D1.4 window rate > single | **PASS** (3.08 > 2.25) | **PASS** (4.16 > 2.30) |
| D2.S-poll >= 1.25x control | **FIRES** (6.30 vs 2.20) | **FIRES** (3.35 vs 1.65) |
| D2.S-idle >= 1.5x control | **FIRES** (right 43 % vs 21 %) | no (26/19, 28/30) |

**VERDICT: D2 — the package is required** (seed 5: interval, S-poll, S-idle; seed 6:
S-poll). **The clock clauses are not what fails**: at seed 6 all four D1 clauses pass,
and at seed 5 three of four do. What fails is the **delivered** side — the interval
(which is the count), the right arm's feed (starvation) and, at seed 5, the overlap
strength (right idle). The pre-registered mixed reading therefore obtains, and it is
the whole answer:

> **The clock does not need the package. The delivered throughput does.** The scheduler
> overlaps on any supply (1.30-1.42 arms busy vs the single arm's 0.83); its overlap is
> strongest with the package (1.58 arms at seed 5) and weakest when the right arm has
> nothing to pick (1.30, 43 % idle, 93 % of its polls empty). The package's own count
> is a seed draw (P80's 1.27x / 0.73x), so its stable value is the feed and the interval,
> not a guaranteed +count.

## 5. Motion gates and the branch probe

* **`105` budgets, no fingerprint, no rate floor** (`--min-success-rate 0.0`): **PASS
  on both arms**. Worst descent `|v|max` **0.1370 / 0.1210 m/s** against budgets
  0.160-0.161, lurch **0.050 / 0.028 m/s per tick** against 0.291, `a_win5` 3.69 / 1.61
  (the reported, non-gated payload-free roughness), carry cone reported under the
  dynamic convention: worst held **1.89x / 1.62x** (P80's controls 1.48-1.62x), hand
  speed 0/31 and 5/33 legs > 0.45 m/s (reported).
* **`190` against P80's 20-attempt reference** (`logs/p80/motion_reference_twoline_p80_20.json`,
  the only same-attempt-count file): **recorded DIFFERS** on both logs from **leg 1**
  (Tp5 leg 1 `[89, 0.108]` vs `[89, 0.109]`; Tp6 `[89, 0.110]` vs `[89, 0.109]`).
  **Expected and not a break**: the reference is the package-on scenario, and changing
  the supply changes the fruit sequence, hence every descent's `(samples, |v|max)`.
  The reference was not overwritten, no new one was written (there is no second
  same-scenario arm to gate), and `configs/` is untouched (`8952c320` / `eb697f23`).
* **Branch probe**: `SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p81/accept_noharm.log scripts/accept.sh`
  reads **6/9, `fingerprint: matches configs/motion_reference.json` (`8952c320`)**,
  worst descent 0.1100 vs 0.160-0.161, lurch 0.017 — the standing rate-only FAIL at
  6/9, identical in shape to P80's G-S10. The tree did not move.
* **`scripts/selfcheck.sh`: PASS, 0 failures** (`logs/p81/selfcheck.log`).

## 6. What this does not claim (residuals)

* **One supply, two seeds.** The clock result is measured on the single arm's shipped
  scattered line (gaps 0.10-0.35 m, 50/30/20) and at seeds 5/6. "Any supply" is not
  tested; a supply so sparse that only one arm ever works would collapse the overlap to
  1.0x. What is measured is a **supply that is not the package**.
* **The count is not a rate.** Package-off vs package-on counts are 10 vs 16 and 13 vs
  10 — a draw in both directions, as P80 found. Only the clock, interval and starvation
  are the claim; the count is reported with the class split.
* **The package's two parts are not separated.** The cell removes the **dense-sheet
  schedule + balanced mix** together (routing stays on). The B-lane arithmetic
  (0.375 -> 0.30 share, 0.125 -> 0.225 m mean gap) predicts the right's starvation, and
  the measurement agrees, but **density vs mix** is not isolated. A single-grade supply
  (P1c's `FRUIT_SUPPLY_SPECIES`) would be the next cell if that split is ever needed.
* **The wall column is harness cost, not physics.** 2.48-2.51x wall per sim-second on
  the two-line against 1.38-1.40x on the single arm; the sim rate is the transferable
  number, the wall rate is this machine's. Neither is gated.
* **The seed-5 clock carries a class-mix tailwind** (failed attempts 10.8 s vs the
  control's 13.4). The overlap-only decomposition is in §2 and is the number to quote
  for the scheduler's own strength (1.57x vs 1.90x concurrency).
* **No collector/store consequence.** Nothing was recorded; no store, checkpoint or
  `configs/` file changed.

## 7. Evidence and pins

* PREREG `logs/p81/PREREG.md` (**`461e1709…`**, `PREREG.md5`), header
  `logs/p81/header.txt`, driver `logs/p81/battery_driver.log`, report
  `logs/p81/p81_report.txt` (+ `p81_report.py`), supply proof
  `logs/p81/supply_proof.txt`, wall stamps `logs/p81/{Tp5,Tp6}.stamps` (stamp instrument
  `logs/p81/stamp.py`, the byte copy of `logs/p80/stamp.py`).
* Logs: `logs/p81/{Tp5,Tp6}.log`; budgets `{Tp5,Tp6}.budgets`; recorded 190 gates
  `{Tp5,Tp6}.gate`; branch probe `accept_noharm.log` + `accept.gate`; selfcheck
  `logs/p81/selfcheck.log`. Controls: `logs/p80/{S20,T20,S6,T6}.log`.
* **A post-run reporting fix, named**: `p81_report.py` was edited after the runs
  (header pin `1a7e31f0…` -> final **`c7bae670…`**) for three reporting-only defects:
  the seed-5 S/control lookup, the pooled `wall` key, and the concurrency/attempt-span
  decomposition added in §2. The simulator logs, the stamps and the gates are
  untouched by it; the plain logs are the measurement.
* Pins: `tasks.py` `e8dfa6d8`, `bimanual.py` `980923a6`, `assets.py` `540406fa`,
  `conveyor.py` `fb2c58c6`, `scene.py` `07d6fdad`, `rl_env.py` `7d26eb5b`,
  `fruits.py` `c7461d41`, `control.py` `9384ff4f`;
  `configs/motion_reference.json` **`8952c320`** and
  `configs/motion_reference_twoline.json` **`eb697f23`** both **untouched**.
