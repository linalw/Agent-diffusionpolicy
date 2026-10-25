# P40 phase 1 — RATE_CENSUS: where the seconds go, and the retention tax

Measured **offline** 2026-10-25/26 (no simulator, no `src/` change, no commit).
Tree: HEAD `1790b87` + the phase-1 working files (`logs/p40/` only).

Reproduce every number below with:

```bash
python3 logs/p40/rate_census.py > logs/p40/rate_census_out.txt   # ~4 s
python3 logs/p40/rate_census.py --log logs/p39/p3/accept_C.log   # one battery, per attempt
```

`logs/p40/rate_census_out.txt` is the run of record. The script prints, per battery, the
`[cycle]` decomposition (three columns: all / placed only / not placed), the sub-blocks
of the descent segment, the retention table and the per-arm split.

**Two integrity checks that make the tables trustworthy, both printed by the script:**

1. every `[cycle]` row is paired positionally with its outcome row (the two-line logs
   **interleave both arms**, so a "block between two attempt headers" is not one
   attempt), and the pairing is *verified* by comparing the `[cycle]` total with the
   attempt's own `sim=` span — the worst disagreement over all batteries is **0.05 s**;
2. the two-line rate computed here reproduces the log's own `fruits/min` line exactly
   (3.99 / 4.19 / 4.60 placed/min), which only holds if the denominator is the
   **batch** sim span, not the sum of the per-attempt spans (the two arms run
   concurrently, so the two differ by ~1.6-1.7x).

---

## 1. The two-line and bed cycles — the `[cycle]` decomposition

`FRUIT_CYCLE_REPORT=1` prints one row per attempt with the marks placed by
`tasks.py::_cycle_mark` (`:4096-4120`; call sites `:7653`, `:7710`, `:8965`, `:9971`,
`:10873`, `:10881`, `:10988`, `:11178`, `:11242`). **Trap:** the `descent` segment is
`hover mark → descent mark`, i.e. **wait + descent**, and it is split below with the
`[task] dynamic descent: waited N ticks` row.

### 1.1 P39 two-line control, `logs/p39/p3/twoline_C.log` (10 attempts, 6/10)

| phase | all (s) | share | placed only (s) | not placed (s) |
| --- | --- | --- | --- | --- |
| prepose | 0.71 | 4.8 % | 0.71 | 0.71 |
| hover | 0.78 | 5.2 % | 0.77 | 0.80 |
| wait (handover) | 0.62 | 4.2 % | 0.62 | 0.62 |
| descent (net of wait) | 2.81 | 18.8 % | 2.56 | 3.17 |
| close | 1.37 | 9.2 % | 1.20 | 1.62 |
| grip (probe/regrasp) | 3.39 | **22.7 %** | **2.02** | **5.44** |
| lift | 1.71 | 11.4 % | 1.54 | 1.95 |
| place | 2.79 | 18.7 % | 2.79 | - |
| release | 2.39 | 16.0 % | 2.39 | - |
| return | 0.64 | 4.3 % | 0.64 | - |
| end | 0.05 | 0.3 % | 0.00 | 0.13 |
| **total** | **14.92** | 100 % | **15.24** | **14.45** |

### 1.2 P32 bed two-line, `logs/p32/A0_bed_twoline_1.log` (20 attempts, 12/20)

| phase | all | placed only | not placed |
| --- | --- | --- | --- |
| prepose | 0.71 | 0.71 | 0.71 |
| hover | 0.79 | 0.77 | 0.82 |
| wait | 0.64 | 0.64 | 0.64 |
| descent (net) | 2.41 | 2.30 | 2.56 |
| close | 1.29 | 1.22 | 1.41 |
| **grip** | **3.13** | **1.79** | **5.14** |
| lift | 1.96 | 1.69 | 2.36 |
| place | 2.94 | 2.94 | - |
| release | 2.36 | 2.36 | - |
| return | 0.66 | 0.66 | - |
| **total** | **14.51** | **15.07** | **13.68** |

### 1.3 W7-A dense two-line, `logs/w7/10_dense_twoline_1.log` (10 attempts, 7/10)

| phase | all | placed only | not placed |
| --- | --- | --- | --- |
| prepose | 0.71 | 0.71 | 0.71 |
| hover | 0.77 | 0.75 | 0.82 |
| wait | 0.60 | 0.60 | 0.60 |
| descent (net of wait) | 2.46 | **2.80** | 1.67 |
| close | 1.21 | 1.21 | 1.20 |
| **grip** | **1.89** | **1.77** | **2.19** |
| lift | 1.75 | 1.77 | 1.71 |
| place | 2.80 | 2.64 | 3.95 |
| release | 2.25 | 2.34 | 1.63 |
| return | 0.63 | 0.65 | 0.50 |
| end | 0.03 | 0.00 | 0.11 |
| **total** | **13.96** | **15.22** | **11.04** |

**Reading the three tables.** A **successful** two-line attempt is **15.07-15.24 s** of
simulated arm time — the same on all three branches, which is the strongest evidence
that the healthy cycle is a stable quantity. The batch figure of **8.6-9.1 s/attempt**
(`[stats]`) is that span divided by two arms working concurrently (90.2 s / 10
attempts). The cycle is **flat**: place (2.6-2.9 s), descent (2.3-2.8 s) and release
(2.3-2.4 s) are the three biggest blocks and no phase owns more than ~20 % of a healthy
cycle.

A **failed** attempt is *not* consistently longer: the bed's are 13.68 s and the P39
control's 14.45 s (both a grip that held and then lost the payload, so the retries land
in `grip`: **5.14-5.44 s** against 1.72-2.02 s on the placed ones, **+3.3 s**), while
the dense battery's failures are **11.04 s** — those are no-grasps that end before the
lift, so the same attempt costs *less* than a success. So the retention tax is a mix of
"spend the whole cycle and lose it at the end" (cnp) and "spend 11 s and lose it at the
grip" (no-grasp), and the two want different levers.

---

## 2. The single-arm cycle — the current tree and the `[cycle]` reference

`logs/p39/p3/accept_C.log` and `pear_C.log` carry **no** `[cycle]` marks, so their phases
are derived from the leg rows (exact, per attempt) and their span from the log's own
`sim=` range:

| phase | source row | accept_C (10 att.) | pear_C (9 att.) |
| --- | --- | --- | --- |
| prepose | `at pick pose after X s` | 0.88 s (5.9 %) | 0.88 s (5.8 %) |
| wait (handover) | `dynamic descent: waited N ticks` | 0.64 s (4.3 %) | 0.58 s (3.8 %) |
| descent motion | `approach(cartesian) N samples` | 0.75 s (5.0 %) | 0.74 s (4.9 %) |
| close ramp | `dynamic close: N ticks` | 0.19 s (1.3 %) | 0.17 s (1.1 %) |
| lift | `carry grasp_lift N ticks` | 1.44 s (9.6 %) | 1.37 s (9.0 %) |
| place | `carry placeN N ticks` | 2.46 s (16.4 %) | 2.44 s (16.0 %) |
| release | `place low: N ticks` | 0.68 s (4.5 %) | 0.67 s (4.4 %) |
| **not separated by any row** | span − the row above | **7.97 s (53.1 %)** | **8.40 s (55.1 %)** |
| **total** | `[run] … sim=A-Bs` | **15.01 s** | **15.24 s** |

The 53-55 % bucket is not a mystery, it is the `[cycle]` segments the leg rows do not
print (hover, the catch-up, the `close → grip` probe, the release fall, the return). The
**`[cycle]`-instrumented single-arm reference** on the same line splits it exactly —
`logs/g/20_rate_single_1.log`, 10 attempts, 15.81 s/attempt:

| phase | sim s | share |
| --- | --- | --- |
| prepose | 0.88 | 5.6 % |
| hover | 0.74 | 4.7 % |
| wait | 0.54 | 3.4 % |
| descent (net) | 2.92 | 18.5 % |
| close | 1.34 | 8.5 % |
| grip | 2.03 | 12.8 % |
| lift | 1.88 | 11.9 % |
| place | 3.09 | **19.6 %** |
| release | 2.31 | 14.6 % |
| return | 0.65 | 4.1 % |
| **total** | **15.81** | 100 % |

and its pre-Gate-19 predecessor (`logs/biarm/rate_single_1.log`, 18.42 s/attempt) is the
same cycle with `place = 6.18 s` — the place profile was the last big block that moved
(6.18 → 3.09 s, the Gate-19 0.35/1.089 place). **Quote 15.8 s for the structure of a
single-arm cycle and 15.0-15.2 s for the current tree's span**; they are the same shape.

---

## 3. Inside the `descent` segment: 71-74 % of it is waiting

The segment is `hover → descent` and contains an **arrival wait**, a **handover wait**
and only 0.74 s of motion (`logs/p40/rate_census_out.txt`, "inside the `descent`
segment"):

| sub-block | source row | P39 two-line | bed | dense | single arm (Gate-19) |
| --- | --- | --- | --- | --- | --- |
| **arrival wait** | `fruit at pick point … after N steps` | **1.93 s (56 %)** | **1.55 s (51 %)** | **1.57 s (51 %)** | **2.00 s (58 %)** |
| handover wait | `dynamic descent: waited N ticks` | 0.62 s (18 %) | 0.64 s (21 %) | 0.60 s (20 %) | 0.54 s (16 %) |
| approach motion | `approach(cartesian) N samples` | 0.74 s (22 %) | 0.75 s (25 %) | 0.74 s (24 %) | 0.73 s (21 %) |
| track/axis/settle | remainder | 0.13 s (4 %) | 0.11 s (4 %) | 0.14 s (5 %) | 0.18 s (5 %) |
| **segment** | `[cycle] descent=` | **3.43 s** | **3.04 s** | **3.06 s** | **3.46 s** |

The arrival wait is **51-58 %** of the segment and the handover wait another **16-21 %**,
so **71-74 % of the `descent` block is waiting**; the remaining 26-29 % is the
0.73-0.75 s approach plus the 0.11-0.18 s track/axis/settle residual.

The mean arrival wait over the batteries is **169-240 ticks (1.4-2.0 s)** per attempt
(`fruit at pick point … after N steps`: 231.6 ticks P39 two-line, 185.4 bed, 188.9 dense,
**169.3 accept_C**, 191.8 pear_C, 240.3 the Gate-19 single-arm reference). Note that the
*current tree*'s single arm waits **1.41 s**, not the reference's 2.00 s — the table's
last column is the `[cycle]`-instrumented reference, and accept_C has no `[cycle]` marks;
quote 1.4 s for the current single-arm arrival wait and 1.9-2.0 s for the two-line's.
**This is the largest single named block in the cycle after place+release, and it is pure
waiting for the belt** — it is the arm-side face of the "arrival-bound" reading, now with
a number.

---

## 4. The retention tax

| battery | attempts | placed | cnp | no-grasp | sim span | placed/min | retention-free ceiling | share of the per-arm attempt time that placed nothing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P39 two-line control | 10 | 6 (60 %) | 0 | 4 | 90.2 s (batch) | **3.99** | **6.65** (+2.66) | **38.7 %** |
| P32 bed two-line | 20 | 12 (60 %) | 1 | 7 | 171.8 s (batch) | **4.19** | **6.98** (+2.79) | **37.7 %** |
| W7-A dense two-line | 10 | 7 (70 %) | 1 | 2 | 91.3 s (batch) | **4.60** | **6.57** (+1.97) | **23.7 %** |
| P39 single arm, acceptance | 10 | 6 (60 %) | **3** | 1 | 150.2 s | **2.40** | **3.99** (+1.60) | **39.2 %** |
| P39 single arm, pear battery | 9 | 6 (67 %) | **3** | 0 | 137.0 s | **2.62** | **3.94** (+1.31) | 32.6 % |
| Gate-19 single-arm reference | 10 | 9 (90 %) | 0 | 1 | 158.1 s | **3.42** | 3.80 (+0.38) | 10 % |

The ceilings are **"every attempt converts, same span"**, so they are the retention-free
cost of the same motion: **+1.3 to +2.8 placed/min** on the two-line and **+1.6** on the
current single arm. The lost attempts are not cheap — a cnp costs **14.9 s** (acceptance)
and a no-grasp **14.4 s** — so retention is not a partial-credit question: the arm spends
the whole cycle and delivers nothing.

**The two-line's own numbers, in the units its log uses:** 6 placed in 90.2 s = 3.99
placed/min, against 10/90.2 = 6.65 if nothing were lost. On the acceptance, 6/150.2 =
2.40 against 10/150.2 = 3.99.

**Which class the tax is.** It is *not* uniform across arms on the single-arm line: the
P33 census (five single-arm branches, 28 log files) reads the **left lane 14/60 placed with 33 cnp**, the right lane
**48/48 placed** (`logs/p33/51_phase2_read.md` §1.2) — so the single-arm retention tax is
essentially one lane. On the P39 two-line control both arms read 3/5, and on the dense
two-line the left is 2/5 with 1 cnp while the right is 5/5: the two-line spreads the same
class over both arms.

---

## 5. The action loop: what the policy's cadence and latency actually are

**Code-read (the pipeline), all in `src/fruit_sorting/rl_env.py`:**

| item | value | site |
| --- | --- | --- |
| control / physics tick | **1/120 s**, `FRUIT_SUBSTEPS` default **1** | `control.py:30`, `common.py:18-25` |
| observation + model call | **every 4th control tick** (`if self._step % 4 == 0: self._observe()`) → **30 Hz of sim time** | `rl_env.py:2732-2733` |
| observations per second of sim time | 30, and **each one renders** (`RenderingManager.render()` before the camera read) | `rl_env.py:1921-1931` |
| chunk execution | one action per control tick, `execute_steps = 4` (`act`) | `rl_env.py:819`, `:2711-2718` |
| action horizon | **16** (`action_horizon`, from the checkpoint's config; 16 is the fallback) | `rl_env.py:1284`, `:1312` |
| obs horizon | **2** frames | `rl_env.py:2330` |
| denoising | `ddim_steps` 16 per chunk | `rl_env.py:2751` |
| episode reward horizon | **1500 policy control steps** = 12.5 s of sim time; the scripted primitive then runs ~3 000 more ticks | `rl_env.py:457-481` |
| scripted stepping | `_step_sim(n)` → `SimulationManager.step` (fixed step) + the entry scripts' `advance()` adds `update_app(steps=0)` to service the camera | `tasks.py:2138-2170`, `rl_env.py:1568-1577` |

**Measured (wall clock, from the RTC batches — `logs/rtc/`):**

| row | policy call | control step |
| --- | --- | --- |
| `logs/rtc/diag_e2/E2_rtc1_timing.log` summary | `policy_ms` med **25.0**, p90 34.7, max 344 | `control_ms` med **32.7**, p90 42.9 |
| `logs/rtc/smoke_rtc_E2.log` | `policy_ms` med **23.6**, p90 33.3 | `control_ms` med **31.2**, p90 41.6 |
| `logs/rtc/diag_e2/E2_rtc0_timing.log` (no RTC) | `policy_ms` med **52.2**, p90 61.2 | `control_ms` med **9.2** |
| `logs/rtc/ab_v1/E1_rtc1_timing.log` | `policy_ms` med **100.0**, p90 115.7 | `control_ms` med **111.4** |

and the render side, measured across seven video runs (`[video] capture cadence`):
**render med 9.4-16.8 ms per frame**, camera reads med 4.3-9.0 ms.

**What that means.** One control tick is **8.33 ms of simulated time**; one policy
decision costs **24-100 ms of wall time**. The action loop is therefore *not* a
real-time loop and cannot be made one by shortening the chunk: at `execute_steps = 4`
the loop already spends 3-12 physics ticks' worth of wall time per decision, and the
render is 30-50 % of it (9.4-16.8 ms of a 31-33 ms control step). **Every latency number in this section is measured except the
"per decision" pairing**, which is a code-read (the RTC rows time the `act` call, the
`[rl] episode` rows count decisions):

* `[rl] episode … ticks=1915 decision=316` (`logs/p37/B_ab/B_1.log`) → **6.1 control
  ticks per decision on average** over the whole episode, i.e. the model is called
  ~50 ms of sim time apart once the primitive's scripted ticks are averaged in;
* the same rows over the whole direct corpus give **1 826-2 195 ticks per episode**
  (15.2-18.3 s of sim time) with **199-345 decisions**.

**The scripted line's structure is different and simpler:** one `_step_sim(1)` per
control tick with a pure-Python IK step, no render, no model. That is why the scripted
acceptance runs ~15 s of sim time in a few minutes of wall clock while the policy's
15 s episode costs ~3 000 renders.

---

## 6. The known-closed items, with their numbers (do not re-run these)

| item | measured | source |
| --- | --- | --- |
| **the place geometry** | shortening the place carry by 45.1 → 36.1 cm (297 → 237 ticks, ~1.0 s saved) collapses the rate **90 % → 30 %** — the payload releases at `abs(y)` 0.21-0.41 m while the belt's inner edge is at 0.375 m. The control's release already sits ~35 mm inside the belt; the **maximum safe shift is ~30 mm = ~0.2 s = 1.3 % of the span** against a 4 % bar | `FRUIT_PLACE_INNER_SHIFT`, P3 (`AGENTS.md`: "the place leg is closed by geometry") |
| **the place profile is already tuned** | the Gate-19 sweep 0.20 / 0.25 / 0.30 / 0.35 m/s → **7 / 7 / 8 / 9** of 10 attempts; the place block fell 5.64 → 2.85 s (and the cycle's `place` is 3.09 s in `logs/g/20_rate_single_1.log`) | `tasks.py:2925-2939`, `logs/fast/sweep_iso_p035*` |
| **the lift profile** | 0.20 / 0.25 / 0.30 → **8 / 8 / 9** of 10 | `tasks.py:2907-2909` |
| **the descent ends 40-90 mm short** | every approach line reports `end=` 40-90 mm on both shipped and candidate configurations, because the pick pose is outside the reachable band; isolated-cell achieved/commanded speed ratio 0.92-0.96 on 16/16 descents | `AGENTS.md` "the descent's speed excursions are the workspace boundary"; `logs/160/161`, `logs/155` |
| **the wait is arrival-bound** | the cadence is **flat (~15 s)** and the lock-on does **not** fall across the whole supply-density ladder (D = 1.00…2.00); the density changes *which fruit* is presented, and class-standardised the ladder is flat | P1/P2/P1c (`AGENTS.md`), `logs/p3/ORACLE_REVIEW.md`, `scripts/200_composition_audit.py` → `logs/p2d/82_standardised.txt` |
| **the density knob** | two-line patch battery D = 1.00/1.25/1.40/1.50/1.60/1.75/2.00 → 60/55/80/75/**90**/75/25 % success, 3.64/3.36/4.48/4.48/**5.27**/4.20/1.53 placed/min — **but** class-standardised it is flat, and on a single-species pool the same knob is **strongly negative** on the single arm (65 % → 17-30 %, 0/20 → 14/20 empty slots) | `FRUIT_SUPPLY_PATCH_DENSITY`, P1c `logs/p1c/PREREGISTRATION.md` |
| **the park / hot-arm / lead probes** | the park gate (`FRUIT_BIARM_PARK_EARLY=1`) is the two-line default and moved the pooled interval 22.20 → 16.53 s (timing-only **+10 %**, different branch); `FRUIT_BIARM_PREFETCH` is a measured **null** (0/40 attempt-ends reserved); the adaptive lead is **bit-identical** (the shipped 1.5 s floor *is* the measured setup); the hot-arm residency read worse (3.41 vs 3.63 placed/min) | `logs/w6/C_RESULTS.md`, `logs/w8/R3_RESULTS.md`, W7-A in `AGENTS.md` |
| **the arm-park occlusion (policy manifold)** | parking the inactive left arm moves the right-arm carried class **25 → 0** (right 23/51 → 47/50) and the *image channel* carries it; the checkpoint adds nothing on top | P35/P36/P37, `logs/p35`, `logs/p36`, `logs/p37` |
| **the lateral-refusal tail** | 2 of 3 103 episodes (0.06 %) below the trigger's admission floor, so no A/B at this N can measure the class; the END/reseed harness is default off | P38, `logs/p38/P2_RESULTS.md` |

---

## 7. What this implies for the lever set

* **The largest block on a healthy cycle is place + release: 5.2 s of 15.0 s (34 %) on
  the two-line and 5.4 s of 15.8 s (34 %) on the single arm** — and both are already
  swept (place 0.35/1.089 is the Gate-19 winner; the *distance* is geometry-closed at
  ~30 mm of safe shift = 0.2 s). Do not spend a phase re-opening them.
* **The largest block on a *failed* cycle is `grip` = 5.14-5.44 s** (probe + regrasp
  retries), 2.5-3.0x the healthy 1.72-2.02 s. Retention and rate are the same lever:
  the +3.3 s of retries is measured *inside* the attempt that then loses the fruit.
* **The second-largest controllable block is pure waiting**: the arrival wait is
  **1.4-2.0 s per attempt (51-56 % of the whole descent segment)**, the handover wait
  0.54-0.64 s. Combined **2.2-2.6 s of 15 s (14-17 %)**. It is belt-bound per P1c, so
  the only levers that touch it are supply/timing ones — which P1c already closed on
  the single arm.
* **The retention tax is 1.3-2.8 placed/min** (two-line) and **+1.6** (current single
  arm), i.e. **37-39 % of the arm's attempt time places nothing** on the P39 / bed /
  acceptance batteries (23.7 % on the dense one, which converts better). A retention lever that converts even the cnp half of it is worth more
  placed/min than any motion-profile change still available.
* **Do not chase the action loop's cadence.** A decision already costs 24-100 ms of
  wall time against an 8.3 ms tick; the loop is 30 Hz of sim time by construction
  (`_step % 4`), and the chunk is 4 ticks of a 16-action prediction. Shortening the
  chunk buys wall time, not sim time.
* **A per-decision sim-time budget cannot be bought with a higher control rate** — the
  physics is already fixed at 120 Hz and `FRUIT_SUBSTEPS` 1. The measured lever on this
  axis is the render (9.4-16.8 ms of the 24-100 ms), i.e. wall clock, not the cycle.
* **The two-line's 9 s/attempt is not a cycle time.** It is 15 s of arm time divided by
  two arms. Any comparison against the single arm must use placed/min (3.99-4.60 vs
  2.40-3.42) or the per-arm span (15.07-15.24 vs 15.0-15.8), never "s/attempt" across the two.

### The single largest remaining unknown (rate)

**Whether the arrival wait is *supply* or *arm-side.** The measured 1.4-2.0 s
(`fruit at pick point … after N steps`) is the loop waiting for a *selected* fruit to
reach the station; the P1c reading says a denser sheet delivers the whole pool as one
burst that then drains below the selection floor, and the two-line hides it because its
worker parks and waits. So the number is "waiting for the *next* fruit to come to the
selector's floor" on a sparse line and "waiting for the sheet" on a dense one — and
**no existing log separates the two**, because the arrival loop starts *after* the
selection. The discriminator is a two-column read of the same battery: the tick the
selector *commits* (the `[biarm] station acquired at t=` / the single-arm selector
step) against the tick the fruit arrives, which is already printed on both lines but has
never been tabulated together. Until it is, "shorten the wait" has no actuator: the
candidates are a lower selection floor (closed by R3/R11-A), a faster belt (screened,
0.15/0.18 flat), or a supply change (P1c negative on the single arm).
