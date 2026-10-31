# P80 — the cell's throughput on the shipped tree, and what the two measured levers are worth on it

Registered in `logs/p80/PREREG.md` (**md5 `b57e979a50766e3f2f8c2155ec8840e4`**, pinned
before any run, unchanged since). Read-only phase: **nothing adopted, no default
changed, no commit, `configs/` untouched**. Owner directive: the left-arm lane is
closed; the work moves to throughput.

## 0. The answer in one table (seed 5, `ATTEMPTS=20`, shipped scenario)

| arm | placed | s/attempt | interval mean / p90 | placed/min **window** | placed/min **batch** | wall/pick | wall/sim | **placed/min wall** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **S** shipped single arm | 12/19 (63.2 %) | **15.10** | **26.72 / 36.90 s** | **2.25** | **2.08** | 25.2 s | 1.38 | **1.51** |
| **T** two-line (opt-in) | 16/20 (80.0 %) | **9.70** | **10.77 / 18.00 s** | **5.57** | **4.96** | 24.9 s | 2.57 | **1.93** |
| **U** single + `FRUIT_SPEED_ALL=1` | 10/20 (50.0 %) | **13.40** | **28.04 / 50.30 s** | **2.14** | **1.82** | 22.1 s | 1.34 | **1.35** |
| **V** two-line + union | 13/20 (65.0 %) | **8.70** | **11.19 / 17.40 s** | **5.36** | **4.48** | 21.9 s | 2.52 | **1.78** |
| *G-S10* acceptance, 10 att. (gate arm) | 6/9 (66.7 %) | 14.80 | 21.64 / 35.60 s | 2.77 | 2.25 | — | — | — |
| *G-T10* two-line, 10 att. (gate arm) | 7/10 (70.0 %) | 9.20 | 10.12 / 17.80 s | 5.93 | 4.54 | 24.2 s | 2.62 | 1.74 |

* **Today's cell** (shipped single arm): **2.25 placed/min by the placement window,
  2.08 by the batch span, 26.7 s mean interval, 25.2 s of wall per pick.** The
  single arm's throughput *is* its failure rate: 12 placements over 19 attempts,
  and every one of the 7 failures was `grasped, not placed` (the closed class).
* **The two-line meets the standing 1.25x bar on the *sim clock* — at both seeds**
  (**2.48x** window at seed 5, **1.35x** at seed 6; interval 2.48x / 1.35x shorter).
  But its **clock factor is 1.87-1.88x at both seeds** while its **count factor
  swings 1.27x -> 0.73x**: the count advantage (16 vs 12) did **not** replicate
  (10 vs 13 at seed 6; pooled 26/40 vs 25/38 — equal). Pooled over the two seeds:
  **sim placed/min 1.86x, wall placed/min 1.02x** (§7b).
* **Its sim-time win is not a wall-time win on this harness**: wall/sim rises
  1.38 -> 2.57 (**1.86x**), so wall/pick is flat (25.2 -> 24.9 s at seed 5, 25.2 ->
  23.8 s at seed 6; pooled 1.03x) and the wall placed rate is 1.28x / 0.77x by seed
  (**1.02x pooled**). The 1.86x is the scheduler's own per-tick cost, not the
  supply's (§6, discriminated on the W6 pair). **If the harness cost were the single
  arm's, the 1.88x clock would be a 1.89x wall gain** — that is the number a real
  cell would see, and it is not what this machine pays.
* **The speed union pays on the clock, not on throughput**: -1.70 s/attempt
  (single) and -1.00 s (two-line), -12 % wall per pick in both — but the
  **interval/placed-per-minute do not improve** (+5 % interval on the single arm,
  +4 % on the two-line) because the placed count falls (§4). Its cost class is the
  one P51 named (acquisition), not the carry.

## 1. What was measured, and the two branch identities

Every 20-attempt arm carries the **same** instrumentation set
(`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`), one `scripts/154_claim_run.sh`
claim per run, `SEED=5` (then 6), shipped scenario (no supply/grade/knob env; the
P71 rails are `none`, and the P43 park / P58 supply profile / P71 direct lift are
`SortingRLEnv`-only and cannot reach this battery — PREREG §0).

The two 10-attempt gate arms carry exactly the shipped instrumentation, and both
reproduced their record **bit-identically**, so this battery sits on the same
branch the documents already describe:

* **G-S10** — `fingerprint: matches configs/motion_reference.json` (`8952c320`),
  **346/346 `[fruit]` lines byte-identical** to `logs/p71/accept_rails_none.log`
  (6/9, the standing rate-only FAIL at the 0.75 floor). The scripted line has not
  moved since P71.
* **G-T10** — `190_twoline_gate.sh` **PASS** with
  `fingerprint: matches configs/motion_reference_twoline.json` (`eb697f23`), and
  **423/423 non-camera `[fruit]` lines byte-identical** to
  `logs/p71/twoline/none.log` (7/10, 9.2 s/attempt). The two-line record was one
  draw; today's tree reproduces it exactly, so the 20-attempt arm is a clean
  extension of that branch rather than a new attractor. (The one textual
  difference is the `head camera ... res=` print: P71's two-line ran the harness
  camera 240x424, this battery the shipped 480x848. It does not touch the physics
  or the fingerprint; it does scale the wall — §6.)
* The shipped `configs/motion_reference_twoline.json` is a 10-attempt record, so
  the **20-attempt** two-line arm got its **own** reference,
  `logs/p80/motion_reference_twoline_p80_20.json` (written by
  `105 … --write-fingerprint`, budgets clean); the shipped file was not touched.

**Motion budgets on the 20-attempt arms** (`105`, no fingerprint — a 20-attempt log
cannot match a 10-attempt reference): **every arm passes the descent speed and lurch
bounds** — worst `|v|max` 0.113 (S20) / 0.114 (U20) / 0.122 (S6) / 0.123 (V20) against
budgets 0.160-0.161, lurch 0.017-0.022 against 0.291 — and the carry cone is reported
under the dynamic line's convention (worst 1.48-1.62x, not gated). The only FAILs are
the **0.75 single-arm rate floor** (63-68 %, the standing P71/P72 branch) and, for
**V20**, `fingerprint: DIFFERS` from T20's own 20-attempt reference: the union re-times
the attempt, so the fruit sequence diverges — **a different attractor by design, not a
motion-budget failure** (V20's worst descent 0.123 vs 0.160-0.161 is inside budget).
V20 also doubles the report-only hand-speed excursions (13/34 legs > 0.45 m/s against
T20's 3/17), the P44/P41 convention that the hand's `|v|max` is not the payload's.

## 2. Today's number, and why it is where it is (the shipped single arm)

19 executed attempts of 20 slots (**one slot starved: `no eligible fruit`**), 12
placed, **7 failures, all `grasped, not placed`** — no `fruit did not follow the
gripper`, no crash, no timeout.

The inter-placement interval is **bimodal**, and that is the whole story:

| gap class | n | range |
| --- | --- | --- |
| two consecutive placements | 5 | 17.5-19.6 s |
| one failed attempt between | 6 | 35.6-38.2 s |

186's own decomposition says the same arithmetically: **26.7 s = 4.8 s idle (18 %)
+ 21.9 s of attempts = 1.45 attempts per placement**, i.e. the interval equals
`1.45 x 15.1 s` plus the feed gap. **A single `cnp` costs the cell ~15 s**, which
is why the rate sits at 2.25 rather than ~3.3 placed/min.

The per-arm split is the closed class, and the arm is set by the fruit's grade:

| arm | single arm (S20) | two-line (T20) |
| --- | --- | --- |
| left (grade A) | **1/7 = 14.3 %** | **9/10 = 90 %** |
| right (B/C) | 11/12 = 91.7 % | 7/10 = 70 % |
| standardised to S's mix | 63.2 % | 77.4 % |

The left's 6-of-7 is **not** the lateral tail and **not** the station: the
attempts that failed were delivered at `fruit_x` 0.215 / 0.223 / 0.234 / 0.358 /
0.360 / 0.365 m and the one that placed at 0.305 m (overlapping ranges), the
pick-pose jaw is identical on every left attempt (`x=0.342`, residual 43.1 mm),
and the same nominal fruit is involved on both lines (peach A 6.5 cm etc.). The
wait-start `dy` does not separate the classes either (placed median 0.300 vs
failed 0.360, ranges overlap 0.230-0.473). So: **the single arm's left fails
across the band; the two-line's left places across the band** (0.199-0.367 m, its
one failure at 0.391 m — the P48 tail). *Which* of the supply/presentation
differences does it is **not attributable from these logs** (§8).

Cycle decomposition (mean s per attempt, `[cycle]`):

| arm | prepose | hover | descent | close | grip | lift | place | release | return | span |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S20 single | 0.88 | 0.77 | 2.92 | 1.19 | 1.60 | **1.82** | **3.19** | **2.11** | 0.63 | **15.09** |
| U20 single+union | 0.88 | 0.78 | 2.87 | 1.19 | 1.72 | **1.58** | **2.44** | **1.27** | 0.64 | **13.38** |
| T20 left | 0.71 | 0.75 | 3.04 | 1.35 | 1.98 | 1.77 | 3.29 | 2.09 | 0.59 | **15.59** |
| T20 right | 0.71 | 0.77 | 3.75 | 1.40 | 2.91 | 1.52 | 1.81 | 1.66 | 0.47 | **15.00** |

**The two-line's per-arm attempt is the single arm's attempt** (15.0-15.6 vs
15.09 s). Nothing in the pipelined line makes a pick faster — it overlaps two.

## 3. The two-line: 2.48x, and what the 2.48x is made of

The registered endpoints (seed 5):

| endpoint | S | T | ratio |
| --- | --- | --- | --- |
| pooled interval mean / p90 | 26.72 / 36.90 s | 10.77 / 18.00 s | **2.48x shorter** |
| placed/min, **placement window** | 2.25 | 5.57 | **2.48x** |
| placed/min, **batch span** | 2.08 | 4.96 | **2.38x** |
| batch sim span / pick | 345.7/19 = 18.2 s | 193.4/20 = 9.7 s | **1.88x** |
| placed per attempt | 63.2 % | 80.0 % | **1.27x** |
| wall per pick / wall/sim | 25.2 s / 1.38 | 24.9 s / 2.57 | 1.01x / **1.86x** |
| placed/min, **wall** (60·placed/wall) | 1.51 | 1.93 | **1.28x** |

**The clock half is the scheduler; the count half is the package.** `1.88x x 1.27x
= 2.38x` — the batch ratio is exactly those two factors, and the second one is not
the scheduler's:

* the two-line runs **its own supply**: `[supply] ... wave=on size=5 gap=0.10-0.16
  sep=0.09-0.12 grades=A:0.375,B:0.375,C:0.25` vs the single arm's `wave=off
  grades=A:0.5,B:0.3,C:0.2` (the W3 dense sheet + balanced mix, on by default when
  `FRUIT_BIARM_TWOLINE=1`);
* it runs **its own routing** (W3 pure: left = A, right = B, C recycled), so the
  arms are fed different streams;
* and the count difference is **mostly the left arm** (1/7 -> 9/10) — the same arm,
  same station pose, same nominal fruit (§2).

So the measured 2.48x is what a **default flip would deliver** (supply and routing
included, since both follow the two-line default) — it is **not** "the scheduler
doubles throughput". The scheduler's own share is the 1.88x clock factor, and even
that is 1.88x of *sim* time, which is 1.01x of wall on this harness (§6). And the
count factor is **not** stable: §7b's seed-6 pair keeps the clock at 1.87x but turns
the count factor into **0.73x**, so the pooled ratio is 1.86x (sim) / 1.02x (wall).

Lock-on and starvation, on the two-line: **left 3.83 s (p90 6.80), right 4.54 s
(p90 9.60)**, 19 retry polls each; idle **18 % / 21 %**; **44 starved
half-second polls** across the batch (left 25, right 19) and **zero lost slots** —
the worker parks and re-polls, which is the design and why the two-line's count is
not starved the way the single arm's slot 7 was.

## 4. The speed union: the clock pays, the throughput does not (seed 5)

`FRUIT_SPEED_ALL=1` = place v_max 0.35 -> 0.52, release holds -> the clock floor,
lift 0.30 -> 0.36 (P44's S1+S2+S3).

| endpoint | S (single) | U (single+union) | delta |
| --- | --- | --- | --- |
| s/attempt | 15.10 | **13.40** | **-1.70 s** (bar 1.0: PASS) |
| cycle: place / release / lift | 3.19 / 2.11 / 1.82 | 2.44 / 1.27 / 1.58 | -0.75 / -0.84 / -0.24 |
| pooled interval mean / p90 | 26.72 / 36.90 | **28.04 / 50.30** | **+4.9 % / +36 %** |
| placed/min window | 2.25 | 2.14 | -4.9 % |
| placed/min batch | 2.08 | 1.82 | -12.5 % |
| wall/pick / wall/sim | 25.2 s / 1.38 | 22.1 s / 1.34 | **-12 %** |
| placed per attempt (pooled / arm-standardised) | 63.2 % / 63.2 % | 50.0 % / **69.3 %** | -13 pt / **+6 pt** |

| endpoint | T (two-line) | V (+ union) | delta |
| --- | --- | --- | --- |
| s/attempt | 9.70 | **8.70** | **-1.00 s** |
| pooled interval mean / p90 | 10.77 / 18.00 | 11.19 / 17.40 | +3.9 % / -3 % |
| placed/min window / batch | 5.57 / 4.96 | 5.36 / 4.48 | -3.8 % / -10 % |
| wall/pick | 24.9 s | 21.9 s | **-12 %** |
| placed (pooled / arm-standardised) | 80.0 % / 77.4 % | 65.0 % / 66.3 % | -15 pt / -11 pt |

Read it as the registration says (PREREG R1): **the union's claim is the clock, and
it holds in both lines** (-11 % and -10 % of the attempt, exactly the three blocks
P44 identified: -0.75 -0.84 -0.24 = -1.83 predicted, -1.71 measured). **The
throughput claim does not**: the interval and placed/min do not improve, because
the placed count falls — pooled by 13 and 15 points.

That count fall is **not** a new grip class. On the single arm it is 9 `cnp` + 1
`fruit did not follow the gripper` (the acquisition class P44/P46/P51 already
priced); on the two-line it is **5 never-grasped + 2 cnp** — i.e. the *acquisition*
class, exactly what P51 mapped ("the speed's cost is the acquisition/tail side and
the closed grip class, and there is no class-fix lever left"). The pooled number
also moves with the grade draw: the single arm's left share went 37 % -> 60 %, and
arm-standardised the union is **69.3 % vs 63.2 %** — better, not worse. So the
honest statement is: **at one seed the union buys 10-11 % of the clock and 12 % of
the wall per pick, and its placed-per-minute is flat-to-worse with the reason
visible in the class split.**

## 5. The interval is the failure rate — the mechanism the metric hides

Both lines put the same arithmetic on the table:

* single: `26.7 s = 4.8 s idle + 1.45 attempts x 15.1 s`;
* two-line: `10.77 s` pooled = two arms at ~50 % duty over 15.0-15.6 s attempts.

So the interval moves only through three levers: **the attempt length** (P44's
cells), **the number of attempts per placement** (the failure rate), and **the idle
between attempts** (17-24 % here: feed, park, selection, and on the two-line the
lock-on polls). P80 measures all three and shows why the two throughput levers
land where they do: the union moves the first (and not the second), the two-line
moves the weighting of the first across two arms plus the second (through its
supply).

## 6. Wall vs sim: the harness doubles under the two-line, and that is measured

`wall` is `[run] attempt 0` -> `[fruit] DONE` on a per-line wall stamp
(`logs/p80/stamp.py`, the plain log untouched via `tee`); `sim` is the batch span
over the same interval.

| arm | wall | wall/pick | sim/pick | **wall/sim** |
| --- | --- | --- | --- | --- |
| S20 single | 478.0 s | 25.2 s | 18.2 s | **1.38x** |
| T20 two-line | 497.2 s | 24.9 s | 9.7 s | **2.57x** |
| U20 single+union | 442.9 s | 22.1 s | 16.5 s | 1.34x |
| V20 two-line+union | 438.4 s | 21.9 s | 8.7 s | 2.52x |
| S6 single, seed 6 | 478.8 s | 25.2 s | 18.1 s | 1.40x |
| T6 two-line, seed 6 | 476.8 s | 23.8 s | 9.7 s | 2.47x |
| G-S10 acceptance | (no stamps) | — | 17.8 s | 1.27x (app clock - 45 s boot) |
| G-T10 two-line | 242.0 s | 24.2 s | 9.3 s | 2.62x |

**The 1.86x is the scheduler's, not the supply's.** Discriminated on the W6-B
battery, which ran both lines on the *same* dense patch sheet: single arm 1.25x,
two-line 2.32x (app-clock method, boot 45 s; those logs predate the stamp
instrument). Today's pair, at the shipped camera: 1.38 vs 2.57 = **1.86x** — the
same multiplier, two trees, two supplies. The named mechanism is the shared-tick
arbiter running **both** arms' control work every physics tick; the number of live
bodies is *not* it (the single arm on the 20-body sheet reads 1.25x, the same as on
the 6.6-body scattered line). Not isolated further than that: the supply and the
camera resolution also differ between the two lines' runs, but not between the W6
pair.

**Consequence, and the sentence to carry forward:** a sim-time ratio `r` is a wall
ratio `r / 1.86` on this harness for the two-line, and `r` for the single arm. So
the two-line's 1.88x clock becomes 1.01x wall per pick, and whatever is left of its
throughput gain is the count factor — which pooled is **zero** (1.27x then 0.73x).
A real deployment would not pay this harness, so the *physics* number (1.87x) is the
transferable one and the wall number is the honest one for this machine.

## 7. The decisions

**(a) What is the cell's throughput today?** Shipped single arm, shipped scenario,
20 slots, seed 5: **2.25 placed/min on the placement window, 2.08 on the batch
span, inter-placement interval 26.72 s mean / 36.90 s p90, 25.2 s of wall per
pick.** Its 63 % count is the left arm's `cnp` (1/7), and each of those costs ~15 s
of interval.

**(b) Is the two-line worth defaulting now?** **On the sim clock, yes — 1.87-1.88x
reproducible at both seeds** (window 2.48x / 1.35x; batch 2.38x / 1.37x; interval
2.48x / 1.35x shorter; the clock factor 1.88x / 1.87x). **On this harness's wall,
no — 1.02-1.03x over the pair** (wall/pick 25.2 -> 24.9 s then 25.2 -> 23.8 s;
placed/min wall 1.28x then 0.77x), because the scheduler's wall cost per simulated
second is 1.86x (§6). And **the count is not a gain**: +4 at seed 5, -3 at seed 6,
pooled 26/40 vs 25/38 — equal. The 2.48x/1.35x figures are the *package*'s
(scheduler 1.87x of clock, times a seed-dependent count factor of 1.27x / 0.73x;
the count half comes from the two-line's own dense-sheet supply and pure grade
routing, not the scheduler — §3). **Recommendation: keep it opt-in unless the
objective is simulated-time throughput; the 1.87x clock is real and would be a
1.89x wall gain on a cell that did not pay this harness, but on this machine the
wall rate is flat.** The registered rule's letter (bar at both seeds + seed-5
count non-inferiority) is met; its intent ("placed/min clearly higher" in the
operator's terms) is not, and the two readings are both printed so the owner's
decision is not hidden behind one of them.

**(c) Does the speed union still pay with the rails gone and the lift at 0.20?**
**It pays on the clock and not on throughput.** -1.70 s/attempt (-11 %) on the single
arm and -1.00 s (-10 %) on the two-line, -12 % wall per pick in both; the interval
and placed/min are flat-to-worse (+5 % / -5 % window on the single arm) because the
count falls by 13-15 points, and that fall is the acquisition class P51 already
closed, with the pooled number also moving with the grade draw (arm-standardised
the single arm is +6 pt). **Verdict: not a throughput lever at this seed; it is a
cycle-time lever whose cost is a count the closed class owns.** (Note: the scripted
lift is still 0.36 m — the P71 lift flip is direct-only, so nothing here tests the
"lift at 0.20" variant; PREREG §0 says so up front.)

**(d) Wall vs sim**: reported in §6; the short version is that **28 % of the
single-arm wall and 61 % of the two-line wall are harness** on this box
(`1 - 1/1.38` and `1 - 1/2.57`).

## 7b. The seed-6 pair (the mover was the two-line) — the clock replicates, the count does not

`logs/p80/pick_mover.py` picked the arm whose pooled interval moved most against
S20 — **T (-59.7 %)**, far ahead of V (-58.1 %) and U (+5.0 %) — so the registered
seed-6 pair is **S6 + T6**.

| endpoint | seed 5: S / T | seed 6: S6 / T6 | ratio s5 / s6 | **pooled** |
| --- | --- | --- | --- | --- |
| placed | 12/19 / 16/20 | 13/19 / 10/20 | — | **25/38 / 26/40** |
| s/attempt | 15.10 / 9.70 | 15.00 / 9.70 | 1.56x / 1.55x | 15.05 / 9.70 |
| batch sim span / pick | 18.2 / 9.67 | 18.1 / 9.66 | **1.88x / 1.87x** | 1.87x |
| pooled interval mean | 26.72 / 10.77 | 26.12 / 19.34 | 2.48x / 1.35x | **26.40 / 13.99 = 1.89x** |
| placed/min window | 2.25 / 5.57 | 2.30 / 3.10 | **2.48x / 1.35x** | 1.89x |
| placed/min batch | 2.08 / 4.96 | 2.27 / 3.11 | **2.38x / 1.37x** | **1.86x** |
| wall/pick | 25.2 / 24.9 | 25.2 / 23.8 | 1.01x / 1.06x | **1.03x** |
| placed/min **wall** | 1.51 / 1.93 | 1.63 / 1.26 | **1.28x / 0.77x** | **1.02x** |
| wall/sim | 1.38 / 2.57 | 1.40 / 2.47 | 1.86x / 1.76x | 1.81x |
| starved polls (single / two-line L+R) | 1 slot / 25+19 | 1 slot / 16+17 | — | — |
| lock-on L / R | 3.83 / 4.54 | — / — | — | — |

**What replicates and what does not.** The **clock** is the scheduler's arithmetic
and it does not move: 1.88x at seed 5, 1.87x at seed 6. The **count** does move, in
both directions: the two-line placed **+4** at seed 5 and **-3** at seed 6, and
pooled the two are **equal** (26/40 = 65.0 % vs 25/38 = 65.8 %). So the seed-5
`2.38x = 1.88x clock x 1.27x count` is not the two-line's shape in general — at
seed 6 the same 1.87x clock is multiplied by **0.73x** count and gives 1.37x.

Its class split at seed 6 is the same one P51 named: **5 never-grasped + 5 cnp**
(vs 4 never-grasped at seed 5), the right arm losing 6 of 10 with a **50.3 s mean
interval** and **30 % idle** — the two-line's own supply (dense sheet, B-only
routing for the right) starving on that seed, not a new mechanism.

**Consequence for the decision.** The registered rule's two measurable clauses hold
at **both** seeds on the sim denominator (1.25x bar: 2.48x, 1.35x; count
non-inferior at seed 5: 16 >= 11). But the *other* two clauses the phase reports do
not: **the count advantage does not replicate**, and **on wall the placed rate is
1.28x then 0.77x — 1.02x pooled**. So the honest answer to (b) is:

> the two-line is a **reproducible 1.87x sim-time** lever and a **wash (1.02-1.03x)
> on this harness's wall**, with a count that is a seed draw rather than a gain.
> It should be defaulted only on a **simulated-time** objective; for wall-time
> throughput on this machine it buys nothing, and on a cell that did not pay this
> harness it would buy the 1.87x clock (and the count draw's ± swing).

## 8. What this phase does not claim (residuals)

* **No flip, no default, no commit.** Every arm is env-only; `configs/` untouched
  (`8952c320` / `eb697f23`); the two-line's 20-attempt reference lives in
  `logs/p80/` by design.
* **The two-line's count gain is not attributed to the scheduler.** Its supply
  (dense sheet, balanced mix) and its pure grade routing come with the default, and
  the left arm's 1/7 -> 9/10 is measured on the *same* station pose and overlapping
  delivered-x range with no separating variable in these logs. A scheduler-only
  control would need `FRUIT_SUPPLY_WAVE=0` + the single arm's mix on the two-line,
  which is a *different scenario* with its own reference — not spent here.
* **One seed for U/V.** R3 spends the seed-6 pair on the largest interval mover
  (the two-line). The union's -1.70 s is a per-leg arithmetic fact (the three
  profile blocks, matching P44's census), but its *throughput* verdict is a seed-5
  read and says so.
* **The P43 park / P58 supply / P71 lift flips are out of scope** — they are
  `SortingRLEnv`-only and cannot reach the scripted battery (PREREG §0). The direct
  line's throughput on today's tree is **not measured here**; the last direct
  numbers are P59's 26/45 = 57.8 % with ~35 s/pick wall, which is the same
  harness-dominated wall this phase measures on the scripted line.
* **Two of the two-line's 10-attempt legs report a recycled-payload slip artifact**
  (`slip=112673.2 mm` on one `grasp_lift`), the P76-A3 class (no contact);
  reported, not gated, no new failure reason.
* **The interval's p90 is unstable at this n** (11 and 15 gaps). Quote the mean and
  the bimodality, not the p90 difference.

## 9. Evidence and pins

* PREREG `logs/p80/PREREG.md` (**`b57e979a…`**, `PREREG.md5`), battery driver
  `logs/p80/battery_driver.log`, header `logs/p80/header.txt`, report
  `logs/p80/p80_report.txt` (+ `p80_report.py`, `p80lib.py`), licence
  `logs/p80/licence.txt`, mover `logs/p80/mover.txt`, gates `S10.gate` / `T10.gate`,
  T20 reference `logs/p80/motion_reference_twoline_p80_20.json`, `V20.gate` (the union's own
  budget read).
* Logs + wall stamps: `logs/p80/{S20,T20,U20,V20,S6,T6,S10,T10}.log` and `.stamps`
  (S10 has none — `accept.sh` owns its redirect).
* Pins: `tasks.py` `e8dfa6d8`, `bimanual.py` `980923a6`, `assets.py` `540406fa`,
  `conveyor.py` `fb2c58c6`, `scene.py` `07d6fdad`, `rl_env.py` `7d26eb5b`,
  `fruits.py` `c7461d41`, `control.py` `9384ff4f`;
  `configs/motion_reference.json` **`8952c320`** and
  `configs/motion_reference_twoline.json` **`eb697f23`** both **untouched**.
