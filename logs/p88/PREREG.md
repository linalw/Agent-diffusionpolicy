# P88 - the place raise as a two-line-scoped default (pre-registration)

Frozen before the first P88 run. The md5 of this file is pinned in
`logs/p88/PREREG.md5`; `logs/p88/header.txt` pins the tree the battery ran on.
Nothing here is amended after looking at an outcome - a deviation, if one is
needed, is recorded as a numbered amendment in `RESULTS.md` with the time it was
written and no verdict changes on it unless the amendment says so **and** was
pinned before the run it governs.

Phase: **P88**, the next acceleration lever on the shipped cell. **The shipped
cell is the two-line with P87's release trim** (`FRUIT_BIARM=1
FRUIT_BIARM_TWOLINE=1` by default, `FRUIT_SPEED_RELEASE` on inside a two-line
session; `logs/p87/RESULTS.md`, `docs/THROUGHPUT.md`). No commit is made by this
phase; a flip happens only if the gate below passes.

---

## 0. Why the place, and what changes

The per-arm attempt span decomposes into three profile blocks. Shipped (P87's
`[cycle]` record): **place 3.14-3.19 s / release 1.70 s (was 2.35) / lift 1.65 s**.
P85's union re-pricing put the caps at **place -0.84 s, release -0.72 s, lift
-0.13 s**; P87 has since spent the release. The place is therefore **the largest
remaining block and the only unspent one of the three**.

| | before P88 | after P88 (if the gate passes) |
| --- | --- | --- |
| `FRUIT_SPEED_PLACE` unset, **two-line session** | off (0.35 / 1.089) | **on (0.52 / 1.089)**, `origin=default` |
| unset, single arm / shared station / canary / direct / collector `single` | off | **off** (`origin=scope-off`) - unchanged |
| `=0` / `off` / `false` / `no` (explicit) | off | off, on **every** path including the two-line |
| a speed / `1` / `on` | that speed, globally | same, **globally** (wins over the scope) |
| `FRUIT_SPEED_ALL=1` | 0.52 globally | same; an explicit `=0` still beats the union |
| `FRUIT_SPEED_PLACE_AMAX` | pins `a_max` | same |

One resolver (`tasks.place_speed_resolution`), one scoped consumer per cell:
`speed_cell_defaults(self.two_line_enabled())` at `_grasp_carry_place_impl`
(P87's release site) and at `_carry_leg` (P88's place site). The row
`[biarm] place profile: FRUIT_SPEED_PLACE=0.52(default) scope=two-line v_max=...
a_max=... (244 ticks at 0.55 m; shipped 362, saved 118)` prints only inside
`run_bimanual`; the manifest's `physics.place={v_max,a_max,ticks,shipped_ticks,
saved_ticks,reference_distance_m,profile,origin,two_line,label}` is written by
both writers (`scene._place_provenance`). A manifest **without** the key
predates P88.

**The corrected value is P44's S1 cell, verbatim**: `v_max` 0.35 -> **0.52** at
the shipped **`a_max` 1.089** (a pure speed raise, inside the 0.61 m/s ceiling
where the acceleration term would start to bind; no cone margin is spent - the
place's cone budget is 4.273 m/s^2).

## 1. The arithmetic, before any run

The place transit is one `jerk_limited` profile per leg. At the read site the
chain is: `TrajectoryLimits.from_env` (j 25) -> the place cap -> `limited_by_cone`
keeps `j = min(25, max(10*a, 1)) = 10.89`, `v = min(v_max, 2a)`, `a = 1.089`.
`motion.jerk_limited` then takes `T = 1.02 * max(1.875 d/v, sqrt(5.774 d/a),
(60 d/j)^(1/3))`, rounds up to whole ticks and emits `T*120 + 1` samples, which
is the tick count `[motion] carry placeX` prints.

* **Long legs** (the acceleration term does not bind: `d >= 0.408 m` at 0.52):
  `T ∝ 1/v`, so the saving is `-214.4 * d` ticks. At the registered reference
  **d = 0.55 m**: **362 -> 244 ticks = -118 ticks = -0.983 s** (this is what
  `physics.place` records, at the named distance).
* **Short legs** (`d < 0.408 m` at 0.52, so `a` binds): the saving is smaller -
  at **d = 0.30 m**, **197 -> 155 ticks = -42 ticks** - because the raised cap
  cannot be used before the acceleration limit is reached.

The shipped record's legs are 0.48-0.62 m (`place0`, long) and 0.28-0.47 m
(`place1`, mixed), 16/13 placed attempts in `logs/p87/{T5,T6}.log`. Predicting
**per attempt** (each control attempt's own printed distance re-generated at
0.52, with its own `place low` remainder kept - the cell does not touch that
descent), from those two records:

| seed | control place block median | predicted treatment median | delta | mean delta |
| --- | --- | --- | --- | --- |
| 5 | 3.320 s | 2.416 s | **-0.904 s** | -0.776 s |
| 6 | 3.370 s | 2.478 s | **-0.892 s** | -0.801 s |

The prediction's own resolution is the printed centimetre: re-running the same
prediction at the shipped cap reproduces those medians to **-0.021 / +0.017 s**
and the means to **+0.003 / -0.005 s**, which is why P1's band is ±0.12 s (P87's
own tolerance) rather than ±0.03 s. `logs/p88/p88_report.py --predict` is the
pre-run read; it is re-run in `RESULTS.md` against the same-seed controls.

## 2. The battery

`ATTEMPTS=20`, **seeds 5 and 6**, the shipped scenario, one claim per run
(`scripts/154_claim_run.sh`), wall from `logs/p80/stamp.py`:

| cell | env | what it is |
| --- | --- | --- |
| **C5** | `FRUIT_SPEED_PLACE=0`, seed 5 | the shipped place cap (0.35), P87's clock |
| **T5** | unset, seed 5 | the scoped default (0.52) |
| **C6** | `FRUIT_SPEED_PLACE=0`, seed 6 | the shipped place cap |
| **T6** | unset, seed 6 | the scoped default |

The release cell is **unset on all four cells** (its own two-line default), so
the comparison is the place cell alone. Instrumentation is identical on both
arms - `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_PLACE_TRACE=1` - so a class or landing difference cannot be an instrument
difference (AGENTS §3b). No `src/`, `configs/`, `datasets/` or checkpoint write
happens inside a cell.

## 3. Endpoints, in the order the project requires

The read rules are `docs/THROUGHPUT.md`'s: quote both denominators and the wall;
a count difference is not the lever's; a per-seed attempt span is not
branch-free; the **block** is the mechanism.

* **P1 the `[cycle] place=` block (the mechanism).**
  * **P1a** the block **median** falls in **every arm-seed cell** (pooled per
    seed, as P87 read it) and lies within **±0.12 s** of the prediction of §1
    for that seed. The median is the registered statistic (P87's convention);
    the mean is reported beside it because the place's saving is
    distance-dependent.
  * **P1b** the cell **materialised on every treatment place leg**: the
    commanded peak `|v|cmd` on each treatment `place0/1` transit is
    **>= 0.48 m/s** (control 0.34-0.36), and the leg's tick count is within
    **3 ticks** (median over legs) of the profile re-generated at 0.52 from
    that leg's own printed distance. A cell that resolved but did not reach the
    cap fails here even if the block moved.
* **P2 the interval.** The **pooled** inter-placement interval falls at **both**
  seeds; the **per-arm** interval is reported for all four arm-seed cells (and
  is expected to fall on 4/4, but only the pooled direction is gated, because a
  20-attempt two-line arm's per-arm count is a branch draw).
* **P3 the landing.** Every payload present at the release
  (`release_bottom >= 0` in `FRUIT_PLACE_TRACE`) lands `on_belt`, in **both**
  arms, at both seeds. The upstream-lost rows (`release_bottom < 0`) are the
  known lost-payload class and are reported separately, never counted as a
  landing failure.
* **P4 the loaded-slide class - the phase's real guard.** Read from the
  `[fruit] [carry]` rows, per arm and per leg class, on **both** arms:
  `escaped` = `clean_slip_max > 100 mm` **with a pinch** (`fmax > 0`; P74's
  mechanism count - the `> 800 mm` threshold is not speed-invariant and is
  reported, never gated), `never-held` = `fmax == 0`, and the W8-B guard
  `force_min == 0`.
  * **P4a** no **new failure-reason key** in either treatment cell.
  * **P4b** **place-leg** escapes, pooled over both seeds, **<= 3** of ~32 place
    legs, and **left** place-leg escapes **<= 2** (control: 1 pooled, 0 left).
  * **P4c** the all-leg escaped count, pooled, does not rise by **>= 5** over
    the control's (8 -> < 13).
  * **A class regression - any of P4a/P4b/P4c - ends the phase regardless of
    the interval.** The cell is not adopted and the reason is published.
* **P5 throughput (reported, never gated).** `placed/min` on **both**
  denominators (placement window and batch span) and **`placed/min wall`**; the
  placement count itself. One draw of a rendered-frame loop: a count difference
  is a branch draw, not the lever's (P80's rule).
* **P6 the descent budgets, per leg.** Every descent leg is judged by `105`'s
  own per-leg budget (the shipped profile's 1.10x peak) and lurch bound; the
  budget is **not** re-tuned. Tiering, P87's precedent: **0 legs over** at both
  seeds = clean; **exactly one** leg over at one seed = **CONSIDERED TRADE**
  (documented as that branch's property, ship); **> 1 leg, or a leg at both
  seeds** = **FAIL** (a pattern, i.e. a cost).

## 4. Admissibility and the motion gate

* **G0 - the tree is unchanged, and the control is the shipped cell.** `C5` must
  be **byte-identical to `logs/p87/T5.log`** and `C6` to `logs/p87/T6.log` on
  the `[fruit]` stream with the diag rows **and the two profile rows** dropped
  (`logs/p88/p88_report.py --same`; the one line that moves is the new
  `[biarm] place profile:` row's label, `=0.35(explicit)`). This proves the
  resolver is inert when off, so any treatment difference is the cell's.
* **G1 - motion.** `scripts/190_twoline_gate.sh` on **C5/C6** against the same
  seed's 20-attempt two-line reference must **PASS** (they are the shipped
  clock): `logs/p80/motion_reference_twoline_p80_20.json` for seed 5,
  `logs/p86/motion_reference_twoline_C6_20.json` for seed 6. **T5/T6** are
  **DIFFERS by construction** (a profile change re-times every attempt boundary
  and the fingerprint carries each leg's duration) and are gated on **budgets
  only** (`105 --min-success-rate 0.0`).
* **G2 - the scope's inertness pair** (the P87 template, run after the battery):
  * **(a)** `FRUIT_BIARM=0 scripts/accept.sh` (ten attempts) must be **raw
    `[fruit]` 346/346 byte-identical** to `logs/p71/accept_rails_none.log` with
    `fingerprint: matches configs/motion_reference_single.json` - the single arm
    has no session, so the place cell is `scope-off` and the row does not print.
  * **(b)** the shared-station pair (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`, 4
    attempts, unset vs `FRUIT_SPEED_PLACE=0`) must be identical with `--same`
    and `--profile`: **the row's `origin` label may differ** (`0.35(scope-off)`
    vs `0.35(explicit)`), **the clock must not** (v_max 0.35, a_max 1.089, 362
    ticks in both).

## 5. Verdict rule

The gate **passes** iff, at **both** seeds: **P1a**, **P2**, **P3**, **P4a/b/c**
all pass, **P1b** passes, and **P6** is clean or a single-leg CONSIDERED TRADE
(never a pattern). P5 is reported and is **not** a clause.

* **If it passes**: ship the scoped default (it is the code as written - the
  unset resolution), re-record `configs/motion_reference.json` and
  `configs/motion_reference_twoline.json` from the same-batch shipped-scenario
  runs, archive both pre-P88 files under `logs/p88/`, leave
  `configs/motion_reference_single.json` untouched, and update `AGENTS.md`
  (§1 supersede note + a P88 paragraph), `README.md`, `docs/THROUGHPUT.md` and
  `WORKLOG.md` with the re-baseline.
* **If it fails**: say which clause, do not flip, and publish the measurement.
  A class regression (P4) ends the phase; a budget pattern (P6) ends it; a
  mechanism miss (P1) means the cell did not do what it is priced to do.

## 6. The honest risk, stated up front

Unlike the release (a pure dwell), the place is a **transit**: it moves the
payload faster over the same path, so the two places it can bite are **P4** (the
loaded slide the leg can create) and **P6** (a descent's per-leg budget, via the
re-timed attempt boundary). Both are registered as hard clauses. P74 measured on
the **direct** line that speeding the place does not move the class (escapes
8/19 -> 7/14, p = 0.733) and that the class's rate is flat over a 2.6x dwell
range - so the prediction is *no change*; this phase re-measures it on the
**shipped** cell, where the class's rows are currently dominated by `grasp_lift`
(the control's place legs are 1 escape in 32) and the cell's own contribution is
therefore small but is exactly what must not grow.

## 7. Not measured / out of scope

A third seed; a two-line **collection** shard under the cell (the collector
inherits it and would record `physics.place`); the hybrid canary (it never
builds a `CoopSession`, so the cell has no path there); a saturated machine; the
`place low` descent's own clock (the cell does not touch it - if the block
changes by more than the transit arithmetic, that is the finding).
