# P46 phase 1 — the P44 speed union on the two-line, two seeds: the +12 % does not
# reproduce, F2 fires, the flip is **not** implemented

Measured 2026-10-27. **No commit, no `src/` edit, no `configs/` change.** The
battery is the P44 union as an env arm (`FRUIT_SPEED_ALL=1`) on the two-line
scenario; the two-line-scoped **default** (the item of `logs/p46/PREREG.md` §1)
was **not** implemented, because the pre-registered falsifier fired.

Tree: HEAD **`5ed38d6`**, clean; `tasks.py` **`b6de439c`**, `motion.py`
**`7f2443c1`**, `control.py` `9384ff4f`, `scene.py` `27e3d64a`, `fruits.py`
`dff684b1` (P45), `rl_env.py` `93e35ef7`; `configs/motion_reference.json`
**`8a399626`** and `configs/motion_reference_twoline.json` **`2246f83c`** both
**untouched** (the battery's own `batch_header.txt` pins them).
Evidence: `logs/p46/PREREG.md` (written before the run), `logs/p46/p1/`
(`twoline_s{5,6}_{C,U}.log`, `batch_header.txt`, `driver.log`, `run_batch.sh`,
`run_arms.sh`, `p46_report.py` -> `P1_report.txt`, `gates.sh` -> `gates.txt`).

**The headline.** One claim, four runs, **C -> U interleaved inside each seed**
(1133 s wall, 18.9 min). **Seed 5 reproduces P44 bit-for-bit** (C 453/453 and U
446/446 core rows identical to `logs/p44/p2/twoline_s5_{C,S13}.log`): 8/10 ->
8/10, 9.80 -> 8.75 s/attempt, 4.90 -> 5.49 placed/min. **Seed 6, the new draw,
fails E1 and E2**: the control lands a **9/10** branch, the union
**7/10** (-2, **F2**), and its placement rate falls **5.41 -> 4.42 placed/min**;
`s/attempt` falls by only **0.47 s** (bar 0.50). The **grip guard's substance
holds** — **zero** held-then-lost rows and **zero** held legs over 50 mm of slip
in all four logs, clean-leg slip p50 0.00-0.05 mm — and the two seed-6 losses
beyond the control's own kiwi are the **pre-contact acquisition** class
(`contacts@onset=0`, `force@onset 0.00 N`, pads closing on air 52-65 mm apart).
**Nothing is adopted; the union stays opt-in; no Phase 2.**

---

## 1. What ran

| | |
| --- | --- |
| scenario | `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, the dense wave sheet, balanced A:B:C, pure grade routing, the W7-A park gate auto — P44 battery D verbatim |
| attempts | 10 per arm per seed (`HEADLESS=1`) |
| arms | **C** = unset (the shipped tree); **U** = `FRUIT_SPEED_ALL=1` (place 0.52 / lift 0.36+1.9 / release dwell 0 + 3->2 settle) |
| order | one `154_claim_run.sh` claim over all four: **s5 C, s5 U, s6 C, s6 U** |
| instruments (both arms) | `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1` + `FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1` |
| claim | claimed 10:44:08, returned 11:02:41, exit 0; walls 289 / 263 / 293 / 268 s |

**The instruments are provably run-neutral on this scenario, and the default-off
tree is unchanged** (PREREG §2's check, which was a condition on judging any
endpoint): with the two added-instrument tags (`[carry]`, `place trace`, `[diag]`,
`release trace`) removed from its `[fruit]` stream, this battery's C seed 5 is
**453/453 rows identical** to `logs/p44/p2/twoline_s5_C.log` (a log with none of
them); the union arm is **446/446 identical** to `logs/p44/p2/twoline_s5_S13.log`.
So no re-run without the instruments was needed, and **seed 5 is a reproduction
of P44, not new evidence** — the phase's new draw is seed 6.

## 2. The per-arm table

`placed/min` = 186's batch rate; the window rate and the pooled inter-placement
interval are the throughput companions (CAP_CENSUS rule 4: the two-line's
`s/attempt` is a batch span over two concurrent arms, not a cycle time).

| seed | arm | placed | left + right | span | `s/attempt` | placed/min | window/min | interval mean/p50 | notes (no-grasp / held-lost) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | **C** | 8/10 | 4/5 + 4/5 | 98.0 s | **9.80** | 4.90 | 6.57 | 9.13 / 8.10 s | 2 (2 / **0**) |
| 5 | **U** | 8/10 | 4/5 + 4/5 | 87.5 s | **8.75** | **5.49** | 7.25 | 8.27 / 4.90 s | 2 (2 / **0**) |
| 6 | **C** | **9/10** | 5/5 + 4/5 | 99.8 s | **9.98** | **5.41** | 5.95 | 10.09 / 10.85 s | 1 (1 / **0**) |
| 6 | **U** | **7/10** | 4/5 + 3/5 | 95.1 s | **9.51** | **4.42** | 5.51 | 10.88 / 9.40 s | 3 (3 / **0**) |

**Pooled** (2 seeds, 20 attempts per arm): placed **17/20 (85 %)** C vs **15/20
(75 %)** U; mean `s/attempt` **9.89 -> 9.13 (-0.76 s, -7.6 %)**; pooled placement
rate (17/197.8 s vs 15/182.6 s) **5.16 -> 4.93 placed/min (-4.4 %)**.

**The cells did their job — the speed is real and its block is identified**
(per-leg `[motion]` means; the commanded peak reaches 0.98 of each new cap). These
per-leg numbers are **not additive** — `place0` and `place1` are different
attempts, so the additive per-attempt read is the `[cycle]` block means quoted
below the table:

| leg | seed 5 C -> U | seed 6 C -> U | the block |
| --- | --- | --- | --- |
| `grasp_lift` | 166.6 -> **120.1 t** (-0.39 s) | 173.1 -> **134.7 t** (-0.32 s) | `[v]cmd` 0.294 -> 0.353 |
| `place0` | 370.5 -> **235.2 t** (-1.13 s) | 350.0 -> **251.0 t** (-0.83 s) | `[v]cmd` 0.343 -> **0.510** |
| `place1` | 259.5 -> **175.2 t** (-0.70 s) | 264.5 -> **173.3 t** (-0.76 s) | `[v]cmd` 0.343 -> 0.509 |
| `release` block | 2.30 -> **1.66 s** | 2.37 -> **1.76 s** | the three open-loop holds |

So the three union blocks lose **-1.96 s (seed 5) / -1.71 s (seed 6)** of
per-attempt time (cycle block means: place 3.21 -> 2.29 and 3.18 -> 2.40, release
-0.65/-0.60, lift -0.39/-0.32); the *batch* gains only **-10.5 s / -4.7 s**,
because the rest of the cycle re-draws with the moved branch (seed 6: descent
-0.13, close +0.03, **grip +0.25**) and because the seed-6 right arm ends at
**3/5 placed with 27.0 s idle (28 %)** against the control's 4/5 and 19.4 s
(20 %).

**Seed 6 is the whole finding.** The control's 9/10 is the strongest branch in
the battery (the shipped seed-5 branch is 8/10), and the union's 7/10 is a
**two-placement fall against a same-seed, same-supply control**.

## 3. E1 and E2 (per seed, then pooled)

| endpoint | seed 5 | seed 6 | verdict |
| --- | --- | --- | --- |
| **E1** placed (bar: >= C in both seeds; -1 = report, -2 = F2) | 8 = 8 | **9 -> 7 (-2)** | **FAIL / F2 FIRES** |
| **E2** `s/attempt` (bar: >= 0.50 s in both seeds) | **-1.05 s** (9.80 -> 8.75) PASS | **-0.47 s** (9.98 -> 9.51) | **FAIL by 0.03 s** |

**The E2 edge, stated exactly.** The registered definition is the `[stats]` span /
attempts: 99.8/10 = **9.98** and 95.1/10 = **9.51**, a **-0.47 s** delta. The
printed 1-dp fields ("10.0 s/attempt", "9.5 s/attempt") round to a **-0.50 s**
delta, i.e. exactly at the bar. Either way it is *at best* a boundary pass, and
**the phase's decision does not rest on it** — F2 fired on the count in the same
seed.

## 4. E3 — the guard (`FRUIT_CARRY_DIAG=1` on both arms)

`held` legs are the legs of attempts whose `[biarm] result` row reads
`grasped=True` (the linkage the report builds; the live slip accumulator is
contact-agnostic and reads hundreds of mm on never-held legs — W8-B's caveat).

| seed | arm | carry legs | `force_min==0` legs | held legs > 50 mm | clean-leg slip p50 / max | held max | held-then-lost rows |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | C | 18 | 2 | **0** | 0.00 / 0.10 mm | 0.10 mm | **0** |
| 5 | U | 18 | 2 | **0** | 0.05 / 0.20 mm | 0.20 mm | **0** |
| 6 | C | 19 | **1** | **0** | 0.00 / 0.30 mm | 0.30 mm | **0** |
| 6 | U | 17 | **3** | **0** | 0.00 / 0.30 mm | 0.30 mm | **0** |

* **E3a (a new grip row) — PASS.** No arm of any seed draws a
  `fruit did not follow the gripper` row on a **held** attempt. Every row is
  `grasped=False`: the pre-contact acquisition class (the shipped line's own
  2.0 %/attempt corpus rate, and the two-line's own 2/10 at seed 5). The count
  rises 1 -> 3 at seed 6 and is **F2's own events**.
* **E3b-ii (the walk) — PASS.** Zero held legs over 50 mm in all four logs, and
  the clean-leg slip is **0.00-0.30 mm** (W8-B's clean band is 0.02-1.43 mm).
  The held payloads are *not* walking.
* **E3b-i (`force_min == 0` leg count) — PASS at seed 5 (2 = 2), FAIL at seed 6
  (1 -> 3).** **The counter is not class-specific on this scenario** and this is
  the one place the registered gate and the physics disagree: all three seed-6 U
  legs read **`contacts@onset=0`, `force@onset=0.00 N`, `min_contacts=0`,
  `sep@onset` 52.2-64.7 mm** — the pads never touched the fruit, so the leg
  reads zero force for the same reason a never-held leg does, not because a held
  payload slid out. So **F1 fires by the letter of E3b-i and its named mechanism
  (a loaded slide / a worse walk) is absent**; the firing is the acquisition
  class counted a second time.

## 5. E4 — the motion gate, per leg

**PASS on all four logs**: every descent is inside its own profile's speed and
lurch bound (`105`'s per-leg verdict, and `190`'s summary).

| seed | arm | worst `|v|max` (budget 0.160-0.161) | worst lurch (budget 0.2911) | worst held-grip cone | legs over 1x | hand > 0.45 m/s |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | C | 0.110 | 0.019 | **2.49x** | 3 | 2/18 |
| 5 | U | 0.110 | 0.018 | **3.12x** | 7 | 9/18 |
| 6 | C | 0.110 | 0.019 | **1.38x** | 4 | 2/19 |
| 6 | U | 0.117 | 0.023 | **1.71x** | 6 | 10/17 |

The cone and the hand-speed count are **reports** on this line (AGENTS §2; P44
§9.3 - `--strict-cone` fails on the control too). They are **worse in both
seeds** (cone 2.49 -> 3.12 and 1.38 -> 1.71; legs over 1x 3 -> 7 and 4 -> 6), and
the `>= 0.45 m/s` hand convention is spent by the faster place (2 -> 9 and 2 ->
10 legs) at its own commanded 0.51 m/s — the same convention P44 already
recorded as knowingly breached by the place cell. Neither is a budget failure.

## 6. E6 — the release landing (`FRUIT_PLACE_TRACE=1` on both arms)

| seed | arm | place traces | reached the release (`release_bottom > 0`) | `on_belt=True` | landing misses | lost upstream |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | C | 8 | 8 | **8** | 0 | 0 |
| 5 | U | 8 | 8 | **8** | 0 | 0 |
| 6 | C | 9 | 9 | **9** | 0 | 0 |
| 6 | U | 7 | 7 | **7** | 0 | 0 |

**E6 PASS.** Every payload that reached the shortened release landed on the
output belt (`release_bottom` 46-68 mm, the control's own landing band), and
there are **no** upstream losses at all in this battery (the four arms' 32 traces
are all release-reached). **F4 does not fire.**

## 7. E5 — the fingerprint verdicts (phase-1 record only)

| log | `190` (ref `configs/motion_reference_twoline.json`, floor 0.60) |
| --- | --- |
| s5 C | **PASS** — `fingerprint: matches`, 8/10 |
| s5 U | rate PASS (8/10), **fingerprint DIFFERS** — the moved profile, by construction |
| s6 C | rate PASS (9/10), **fingerprint DIFFERS** — a **different supply draw** (the reference is the seed-5 branch: the fruit sequence differs from attempt 0) |
| s6 U | rate PASS (7/10), **fingerprint DIFFERS** — moved profile |

Only the seed-5 control can match the reference file, and it does. The other
three are *different scenarios* (AGENTS §2: references are per-scenario), which
is why the same-seed **C vs U pair** is the comparison of record and the
`190` exit code is not the rate gate here. No `configs/` file was written.

## 8. The mechanism of the two seed-6 losses (both acquisition, neither carry)

Seed 6, U arm — all three `fruit did not follow the gripper` attempts (the
`[cycle] attempt N` labels are the log's own, 1-based):

| `[cycle]` attempt | arm / fruit | `grasped` | lift | `[carry]` signature | reading |
| --- | --- | --- | --- | --- | --- |
| 1 | right kiwi 7 | False | +0.000 m | `contacts@onset=0`, `force@onset=0.00 N`, `sep 29.8 -> 29.8 mm`, `min_contacts=0`, slip 370.9 mm, 38 servo trips | **shared with the control**: C's attempt 1 is the same instance with a *row-identical* signature (slip 371.2 mm, sep 29.8, 0 contacts, 38 trips) — this loss is the scenario's, not the union's |
| 3 | left peach 0 | False | +0.040 m | `contacts@onset=0`, `force@onset=0.00 N`, `sep 64.7 -> 49.8 mm`, `min_contacts=0`, 38 servo trips | **the control placed this same pool instance** (C's attempt 2: `grasped=True`, lift +0.348 m, 7.26 N, 14.9 s) — the arms met it at different times, so it is a same-instance pair, not a controlled one |
| 10 | right peach 13 | False | +0.002 m | two `dynamic regrasp: re-seated in place` rows, then `contacts@onset=0`, `force@onset=0.00 N`, `sep 52.2 -> 52.3 mm`, `min_contacts=0` | the pads closed and stayed open around air; the fruit was never between them (the same instance had been *placed* at attempt 6, lift +0.501 m, so the pool recycled it) |

Every row is the **pre-contact acquisition** class (fingertip-to-fruit 52-65 mm
at the close, payload never between the pads) — the class W7-B/ACQ and R2 named,
and the class the shipped line draws at 2.0 %/attempt. **No row is a grip-loss or
a hold failure**: no held-then-lost attempt exists in this battery, and the held
legs' slip is 0.0-0.3 mm.

## 9. Verdicts and the decision

| | |
| --- | --- |
| **E1** placed | **FAIL** — seed 5 equal, **seed 6 -2** |
| **E2** `s/attempt` >= 0.50 s both seeds | **FAIL** — seed 5 -1.05 PASS, seed 6 **-0.47** |
| **E3a** new held-then-lost row | **PASS** (0 in all four logs) |
| **E3b-i** `force_min==0` legs | **PASS** s5 (2=2), **FAIL** s6 (1 -> 3) — never-held legs, not loaded slides |
| **E3b-ii** the walk (held > 50 mm) | **PASS** (0/0 in all four; clean slip <= 0.30 mm) |
| **E4** motion budgets | **PASS** (all descents inside; cone and hand-speed **reported worse** in both seeds) |
| **E5** gate of record | record only: s5 C `matches`; the other three differ (moved profile / different draw) |
| **E6** release landing | **PASS** — 32/32 release-reached traces on the belt, 0 misses |
| **F1** new grip row / worse walk | **fires by the E3b-i letter; its mechanism (loaded slide / walk) is absent** |
| **F2** placed falls by >= 2 | **FIRES** (seed 6: 9 -> 7) |
| **F3** a motion budget fails | does not fire |
| **F4** the release throws a payload | does not fire |
| **F5** single-arm stream not byte-identical | not evaluable (phase 2 only) |

**Decision (per PREREG §5): no Phase 2. The two-line-scoped speed default is not
implemented.** The union stays opt-in (`FRUIT_SPEED_ALL=1`), the two-line keeps
the shipped speeds, and `configs/motion_reference_twoline.json` stays
`2246f83c` (no re-record was owed because nothing ships).

**What the phase nonetheless establishes** (the honest positive, quoted so it is
not lost):

1. **The speed is real and reproducible**: -10.7 % `s/attempt` on the seed-5
   branch (bit-identical to P44's -1.10 s) and -4.7 % at seed 6, with the three
   union blocks moving by their own arithmetic (`place0` -0.83..-1.13 s,
   `place1` -0.70..-0.76 s, lift -0.32..-0.39 s, release -0.60..-0.65 s) and the
   commanded peaks at 0.98 of the new caps.
2. **The grip guard is clean**: the union does not walk the payload (0 held legs
   over 50 mm; clean slip 0.00-0.30 mm vs the control's 0.00-0.30 mm), and every
   loss in the battery is pre-contact.
3. **Its cost is the count, at one of two seeds, in the acquisition class** - and
   at seed 6 that cost is larger than the speed gain (rate 5.41 -> 4.42
   placed/min). The faster cycle also leaves the right arm **idle 28 %** on that
   branch, so the speed does not convert into placements.

## 10. Deviations, and what this does not claim

* **No protocol deviation.** Everything ran as registered: one claim, C -> U
  inside each seed, both instruments on both arms, the neutrality check passed,
  so no instrument-free re-run was triggered. Two *reading* notes are appended to
  `PREREG.md` §7 (the seed-5 reproduction, and E3b-i's non-specificity).
* **Seed 5 carries no new evidence**: it is row-identical to P44 (453/453 and
  446/446). The two-seed design is therefore **one reproduction plus one new
  draw**, and the new draw fails. That is a *weaker* confirmation than two fresh
  seeds would have been — it is the strongest that the same scenario can give,
  and it is stated as such.
* **The outcome is quantized** (AGENTS §2): each arm's count is one draw of an
  attractor and the union moves the branch, so "9 -> 7" is **not** a rate
  estimate. What is measured is that the *moved branch at this seed* puts two
  fewer payloads on the belt, in the acquisition class, with a clean grip.
* **Not measured**: the single-arm cells (they stay opt-in, P44's verdict), the
  policy/direct interface, the collector's stores, and the shared-station biarm.
  No clearance claim is made (a per-config report in this project).
* **Two seeds are not five** (WS-4.2): a "no fall" read at 2/2 would have been
  non-inferiority-flavoured evidence; a "-2 at 1/2" read is enough to stop, and
  is not by itself a quantified regression.
