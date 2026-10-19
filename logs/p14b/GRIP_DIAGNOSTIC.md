# P14-B: the grip-margin diagnostic — the offline geometry mining + the trace pre-registration (Tier C offline)

Status: **offline, read-only** (branch `p-supply`, 2026-10-19; no simulator run — the P14-A canary
chain (`logs/p14/90_a_driver.log`, `logs/p13/76_accept_policy_revert.log`) was running on the same
machine throughout and was not touched; no `src/`, `scripts/`, `configs/`, `datasets/`, `Paper/`
write; no commit by the lane). All writes under `logs/p14b/`. Tree pins as read (the committed
files; the P14-A lane was mid-swap on `policy/model.py`/`finetune.py`/`111`, none of which this
lane reads): `tasks.py` `810658b802d22bbd63013726fc78af81` (the P11-C/P12-B.2 pin; unchanged by
P12/P13 — the last commit touching it is `30cde55`), `fruits.py` `d28546d26137d4540421caa7fa34a139`,
`scene.py` `ab85dca250cdd09cc7cbd9893c58fca3`, `meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`.

**The mandate.** The P12-B.2 scoping record (`logs/p12b/SCENE_OPTIONS.md`, "The strongest reason
any of them could fail") named the cheap diagnostic: *"the existing `FRUIT_DYNAMIC_TRACE=1`
per-tick rows on the base's B1 attempts — the per-tick pad–fruit geometry was never recorded, so
the no-grasp class's geometric driver is unidentified"*. This lane does the **offline half**: (1)
mine every existing log for the pad–fruit geometry signals that *do* exist; (2) design the exact
trace run (env + seeds + attempts + readouts + analysis) as a frozen pre-registration sketch;
(3) name the next-lever candidates the geometry would discriminate.

---

## 0. The answer in one screen

* **The strongest separator found offline is the per-tick hand-frame payload drift, and it is
  already visible in the existing trace corpus — not in any aggregate log row.** On the five
  W5-C trace runs of the dense two-line (50 attempts, `logs/w5/traces_dense` +
  `30_traces_{fs0,fs0sq0,track02,lockx}`): the ok attempts' cumulative payload drift in the hand
  frame spans **0.0–20.5 mm** and the failed attempts' **313.2–1992.0 mm** — disjoint, and the
  first-departure phase localizes every failure (hold 1, takeoff 4, takeoff-probe 4, carry 6).
  On the mass base's own (untraced) logs **nothing separates**: every continuous row overlaps
  (§1.2), the only disjoint quantities are outcome-consequent (`clean_slip_max`), and the
  pre-outcome signals are *associations* only (the regrasp incidence 5/8 vs 5/45, p = 0.0037;
  the force servo's `Fmin = 0` 6/8 vs 7/45, p = 0.0016) — and the P10-E B1 keep-gap arithmetic
  **fails as a discriminator** (§1.4: a success carries a full-chase re-seat, 49.3 mm kept on a
  65.2 mm fruit, clean_slip 0.1 mm).
* **The trace design's key env** (the mass base + the trace):
  `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
  FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_PHYSICS_REAL_MASS=1 ATTEMPTS=20
  FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1
  FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR=logs/p14b/traces_s<SEED>`
  at SEED 11 (primary) + 5/23 (controls); one or two runs (§2.3).
* **The top candidate lever, conditional on the trace's phase readout**: if the loss is
  bracketed to the **re-seat window** (the last probe row holds, the next row shows the payload
  gone) → **`FRUIT_DYNAMIC_REGRASP_FLOOR`** — the P11-A §5a keep-gap floor, named but **never
  built** (§3); if the loss is in the **close/hold** → the close-side family (R11-B C1
  `FRUIT_CLOSE_LOAD_RATE`, the squeeze-side knobs) revives; if in the **probe** → the W5-C probe
  screens' negatives stand and the probe's *shape* is the only probe-side lever left; if in the
  **belt-break** (the B2 sub-class, 3/8 of the mass-base class) → the takeoff/belt-break path.
  The trace's job is exactly this discrimination.

---

## 1. The offline geometry mining

### 1.1 The mass base at a glance (the corpus the trace run would instrument)

`logs/p12a2/{10_seed11,11_seed5,12_seed23}_mass.log`: the two-line patch battery
(`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`, balanced
A:B:C 0.375/0.375/0.25, `ATTEMPTS=20`, `FRUIT_PHYSICS_REAL_MASS=1`, motion/cycle/carry reports on;
wall 8 m 20 s / 8 m 50 s / 9 m 35 s per run).

| seed | ok | carried-not-placed | no-grasp | no-grasp classes (P10-E rules) |
| --- | --- | --- | --- | --- |
| 11 (primary) | 11 | 2 | **7** | B1 4 (all 3 regrasps: a01 orange, a06 tomato, a08 orange, a13 tomato; 3 fall to the floor, 1 blowup), B2 3 (a02 peach, a04 tomato, a07 tomato) |
| 5 | 17 | 3 | 0 | — |
| 23 | 17 | 2 | 1 | B1 1 (a02 strawberry, 3 regrasps, fell) |
| **pooled** | **45** | **7** | **8** | **B1 5 / B2 3; no A, no C** |

So the mass base's class is **B1 5 + B2 3** — the B1 (probe/regrasp) majority and a B2
(belt-break) minority — and **seed 11 alone carries 7 of the 8 NG attempts (4 of the 5 B1s)**. The B2 attempts (no regrasp row
at all, grip phase 1.77–1.95 s, the fruit gone by the carry start, left at belt level −2…−218 mm)
are the sub-class the re-seat lever cannot touch.

### 1.2 The P10-E §2.1 separator table, refreshed on the mass base

The full table (all continuous quantities, no-grasp vs ok vs carried) is in
`logs/p14b/mass_mining.txt`. The result: **every pre-outcome continuous row overlaps.**

| quantity | no-grasp (n=8) | ok (n=45) | verdict |
| --- | --- | --- | --- |
| close ticks | 20..38 (med 24) | 4..46 (med 20) | overlaps |
| close force [N] | 3.95..4.85 (med 4.30) | 3.55..10.40 (med 4.32) | overlaps |
| close span [mm] | 49.2..78.6 (med 71.3) | 42.6..81.2 (med 73.4) | overlaps |
| close freeze [mm] | 44.3..69.9 (med 59.8) | 30.2..89.2 (med 63.5) | overlaps |
| freeze − extent D [mm] | −3.3..+2.3 (med +1.1) | −3.8..+22.2 (med +2.6) | overlaps |
| grip G [mm] | 38.8..66.9 (med 59.4) | 29.0..68.7 (med 59.5) | overlaps |
| G − D [mm] | −4.6..−1.4 (med −2.1) | −6.2..+5.9 (med −0.8) | overlaps |
| catch-up residual [mm] | 5.8..6.0 (med 5.9) | 5.1..6.0 (med 5.9) | overlaps |
| moving-pick jump [mm] | 192..233 (med 210) | 189..231 (med 192) | overlaps |
| coherent pad err [mm] | 59.2..63.9 (med 59.8) | 57.9..63.5 (med 59.3) | overlaps |
| descent wait [ticks] | 73..86 (med 76) | 50..88 (med 67) | overlaps |
| servo Fmax [N] | 4.47..120.73 (med 48.27) | 2.16..81.76 (med 4.62) | overlaps |
| F@onset [N] | 0.00..77.95 (med 4.48) | 0.00..31.54 (med 4.19) | overlaps |
| sep@onset [mm] | 10.0..98.3 (med 58.8) | 69.4..81.1 (med 73.2) | overlaps |
| leg gap_start [mm] | 23.8..69.9 (med 59.3) | 29.0..68.7 (med 59.4) | overlaps |
| cycle grip phase [s] | 1.77..5.45 (med 5.38) | 1.72..5.24 (med 1.76) | overlaps |
| cycle total [s] | 8.83..14.35 (med 12.96) | 13.39..19.92 (med 15.70) | overlaps |
| carry cone [x] | 0.88..2.25 (med 1.10) | 0.88..2.21 (med 0.89) | overlaps |
| **clean_slip_max [mm]** | **123.2..95724.3** (med 312.3) | **0.0..40.5** (med 0.0) | **disjoint — outcome-consequent** |
| lowest payload [mm] | −55282..−2 (med −1352) | −4..+284 (med +48) | overlaps by 2 mm (one ok at −4) |

The same table on the P10-E corpus (7 runs, 30 NG / 84 ok / 26 carried) is in the same file; the
picture is identical (the only disjoint columns there are `clean_slip_max` and `lowest payload`).
**The P10-E §2.1 conclusion survives the base shift: the class is decided after the close, and no
single logged row sees it.**

### 1.3 The incidence associations (the strongest pre-outcome signals)

Because the continuous rows overlap, the honest question is whether any *incidence* separates.
Two-by-two tests on the mass base (8 NG vs 45 ok; Fisher exact, two-sided):

| predicate | no-grasp | ok | Fisher p |
| --- | --- | --- | --- |
| ≥ 1 `dynamic regrasp` row | 5/8 | 5/45 | **0.0037** |
| cycle grip phase ≥ 3.0 s (a failed probe) | 5/8 | 5/45 | **0.0037** |
| force-servo `Fmin == 0.00` (row present) | 6/8 | 7/45 | **0.0016** |
| force-servo `closed > 0.5 mm` | 6/8 | 8/45 | **0.0027** |
| first keep-gap − D < −10 mm | 3/8 | 1/45 | 0.0088 |
| `clean_slip_max > 60 mm` | 8/8 | 0/45 | < 1e−4 (consequent) |
| **among the regrasp-bearing attempts only**: first keep-gap − D < −10 mm | **3/5** | **1/5** | **0.52** |

**Reading.** The class is *associated* with the probe/regrasp cycle and the servo chase
(p ≈ 0.002–0.004) — but the association is a one-way condition: **5 of the 45 ok attempts run the
same cycle**, and **within the regrasp-bearing population the keep-gap depth does not
discriminate at all (p = 0.52)**. The only perfect separator is the consequence
(`clean_slip_max`), i.e. a measurement of the loss, not of its driver.

### 1.4 The regrasp keep-gap arithmetic refresh — the P10-E B1 arithmetic does not separate

P10-E §2.4 used the first keep-gap vs the extent as the B1 chain's actuator evidence ("15 of the
18 B1 attempts' first keep-gap is 1.7–17.5 mm narrower than the fruit"). Refreshed on the mass
base (`logs/p14b/keepgap_run.out`; every attempt with ≥ 1 regrasp row):

| run | att | fruit | outcome | close t/F/span/freeze | G / D | n_rg | first keep-gap | first − D | clean_slip | lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| seed 11 | a01 L | orange | **NG (B1)** | 20/4.44/73.7/69.9 | 66.9 / 68.3 | 3 | 51.9 | **−16.4** | 1683.0 | +0.007 |
| seed 11 | a06 L | tomato | **NG (B1)** | 24/4.85/74.8/64.3 | 61.6 / 63.0 | 3 | 60.2 | −2.8 | 95724.3 | +0.000 |
| seed 11 | a08 L | orange | **NG (B1)** | 38/4.32/78.6/65.8 | 65.8 / 68.3 | 3 | 50.8 | **−17.5** | 1689.4 | +0.000 |
| seed 11 | a13 R | tomato | **NG (B1)** | 20/4.01/64.9/59.3 | 55.4 / 57.0 | 3 | 44.2 | **−12.8** | 123.2 | +0.002 |
| seed 23 | a02 R | strawberry | **NG (B1)** | 24/4.28/49.2/44.3 | 38.8 / 43.4 | 3 | 41.8 | −1.6 | 323.8 | +0.000 |
| seed 11 | a03 R | peach | **OK** | 17/4.56/78.4/71.1 | 64.7 / 66.4 | 1 | 64.7 | −1.7 | 0.0 | +0.267 |
| seed 11 | a09 R | lychee | **OK** | 20/4.35/48.7/36.1 | 32.8 / 33.5 | 1 | 35.8 | +2.3 | 0.0 | +0.425 |
| seed 11 | a19 R | lychee | **OK** | 21/4.19/44.1/36.8 | 34.5 / 35.2 | 1 | 37.5 | +2.3 | 0.0 | +0.312 |
| seed 5 | a15 R | apple | **OK** | 17/4.32/77.6/70.4 | 64.3 / 65.2 | 1 | **49.3** | **−15.9** | **0.1** | +0.381 |
| seed 23 | a19 L | pear | **OK** | 16/4.82/77.7/67.8 | 59.5 / 60.3 | 3 | 59.5 | −0.8 | 0.0 | +0.303 |

**The load-bearing row is the seed-5 apple**: a success with a **full-chase re-seat** — the
keep-gap 49.3 mm is 15.9 mm inside the 65.2 mm fruit (49.3 = 64.3 − 15.0, the servo's whole
`RANGE`), and the attempt held (`clean_slip 0.1 mm`, lift +0.381). The row was verified against
the raw log (`logs/p12a2/11_seed5_mass.log` lines 1123–1150: close → grip → the single regrasp
row → the carry), with no other attempt's rows in the window. **A sub-extent re-seat is therefore
not sufficient for the ejection, and the keep-gap depth does not separate the class** (among the
regrasp-bearing attempts: 3/5 NG vs 1/5 ok, p = 0.52). The P10-E chain's *command* evidence is
real (the chase and the sub-extent keep-gaps exist) but it is a population overlap, not a
discriminator — exactly the gap the per-tick geometry must fill.

### 1.5 The per-tick geometry that *does* exist: the W5-C trace corpus (mined)

The only existing `FRUIT_DYNAMIC_TRACE=1` corpus on the **two-line scripted catch** is the W5
arc's: five 10-attempt runs of the dense W3 sheet at SEED 5 (`logs/w5/traces_dense` = cfg0 +
`logs/w5/30_traces_{fs0,fs0sq0,track02,lockx}` = the four W5-C screen configs; **50 attempts**).
Mined here with `logs/p14b/trace_mine.py` + `trace_corpus_summary.py` (the full table in
`logs/p14b/trace_corpus_summary.txt`); the metric is the payload's **cumulative displacement in
the hand frame** (`hand_rel`, the W8-B `clean_slip` frame) from the last `hold` row, per phase.

| config | attempts | ok drift [mm] | fail drift [mm] | first-departure phases |
| --- | --- | --- | --- | --- |
| cfg0 shipped | 8 ok / 2 fail | 0.0–4.6 | 379.1, 1092.5 | takeoff ×1, takeoff_probe ×1 |
| cfg1 servo-off | 6 / 4 | 0.1–0.5 | 1158.2–1508.3 | takeoff ×1, takeoff_probe ×2, carry ×1 |
| cfg2 fs0+sq0 | 8 / 2 | 0.1–0.8 | 379.1, 1050.3 | takeoff ×2 |
| cfg3 track0.2 | 6 / 4 | 0.7–20.3 | 313.2–1276.9 | takeoff_probe ×1, carry ×3 |
| cfg4 lock-x | 7 / 3 | 0.0–20.5 | 1068.3–1992.0 | takeoff_probe ×1, carry ×2 |
| **pooled** | **35 ok / 15 fail** | **0.0–20.5** (5 attempts > 2 mm) | **313.2–1992.0** | as computed: takeoff 4, takeoff_probe 5, carry 6 — with **cfg3 `t09`'s hold already reading `Fmin = 0.00 / cmin = 0`**, so its true onset is the hold: **hold 1, takeoff 4, probe 4, carry 6** |

**This is the decisive offline finding for the design.** The per-tick hand-frame drift is a
**pre-outcome, disjoint separator** (ok ≤ 20.5 mm vs fail ≥ 313.2 mm on these 50 attempts), and
the first-departure phase **localizes the mechanism**. The two cfg0 failures are exemplary:

* `trace_05_left_scripted_fail` — hold 0.0, probe 0.0 (force steady 4.17–4.58 N), **takeoff
  27.8 mm** (force still 3.94 N, the payload starting to walk during the belt-break), carry
  312 mm local, F → 0. A **belt-break onset** (the B2 shape).
* `trace_08_left_scripted_fail` — **hold 4.9 mm** (force down to 2.91 N), **probe 12.9 mm with
  F = 0 / contacts 0 from within the probe**, takeoff 10.7, carry 1099 mm. A **hold/probe onset**
  (the B1 shape).

The lane's own W5 analysis (`logs/w5/21_mech_summary.txt`, `20_mech_failures.txt`) reports the
same onsets (e.g. trace_05's slip onset t = 58.975, in the takeoff; trace_08's in-hand disp
12.9 mm in the probe) — two independent re-derivations agree.

Two further facts mined from this corpus, both needed by the design:

1. **The trace was run-neutral on the dense two-line.** `logs/w5/20_dense_mech_trace.log`
   (SEED 5, 10 attempts, `FRUIT_DYNAMIC_TRACE=1` + `TRACE_PLACE` + catch/biarm/park traces) vs
   the trace-off record `logs/w4/20_dense_repeat.log`: **0 `[fruit]` lines missing or changed**
   (the diff is 63 extra trace/banner rows only; both logs read `attempts=10 successes=8
   diverted=1 sim=112.3s`). So on this scenario the trace did *not* move the branch, and the
   AGENTS §2 "the trace moves the run" warning did not obtain here. **The mass-base trace run
   must re-test this** (its own A/B vs `logs/p12a2/10_seed11_mass.log`), but it is a measured
   possibility that the trace-on run replays the mass base.
2. **The ok attempts' per-tick drift is small but nonzero**: 4.6 mm (cfg0 trace_09, a marginal
   grip that still placed), 8.5/20.3/20.5 mm on the cfg3/cfg4 screen branches. The trace's
   ok-population drift is therefore not exactly zero — the analysis needs the *distributions*,
   not a zero threshold.

### 1.6 What is simply unavailable without the trace

| signal | availability on the mass-base logs | where it lives |
| --- | --- | --- |
| per-tick tip–fruit offset / hand-frame payload pose | **not present** (`FRUIT_DYNAMIC_TRACE` off) | the trace rows' `offset`, `hand_rel` |
| per-tick measured span vs commanded gap (the blocking-span geometry) | not present | the trace rows' `sep` / `gap_cmd` |
| per-tick payload velocity / spin, tactile per-sensor split | not present | `fruit_vel`, `fruit_omega`, `ft` |
| the close's per-tick trajectory (two-phase shape, freeze) | only the summary row (ticks/force/span/freeze) | the `close` rows |
| the probe's per-tick trajectory | only the cycle grip-phase seconds + the `[carry]` leg summary | the `takeoff_probe` rows |
| **the re-seat descent's per-tick geometry** | **not present — and not emitted by the trace either** (§2.2.4) | would need a new trace call site |
| the force-servo's per-step chase walk | only the per-attempt summary (`closed`, `trips`, `F[min,max]`) | not emitted anywhere |
| `FRUIT_ACQ_DIAG`'s per-attempt acquisition report | **a no-op on the scripted line** (`acq_diag = bool(self._acq_diag and direct_capture)`, `tasks.py:6622`) | direct/policy path only |
| the `[diag] carry-assist` first-3-tick rows | present (with `FRUIT_CARRY_DIAG=1`): `cmd_centre`, `offset` (the stored pad-centre offset the arm target is corrected by, 12–57 mm on seed 11), `jaw_target`, `jaw`, `coherent` | `tasks.py:2797-2807` |
| the `[monitor] fire` row | present on fired legs: `tick, z, asym@fire, hot, blocked, min_contacts, clean_slip_max` | the carry monitor |

Two code facts the design must respect (both verified in the tree):

1. **The re-seat is untraced.** The two re-seat loops — the shipped descend-at-`keep_gap`
   (`tasks.py:8721-8742`) and the from-open horizontal close (`tasks.py:8756-8781`) — call no
   `_dynamic_trace_sample`. Every other phase does (§2.2). The re-seat window is therefore only
   *bracketed*: the last `takeoff_probe` row of cycle N and the first row of cycle N+1 (or the
   first `carry` row) straddle it.
2. **The `grip` row's `hand_rel` is junk** — its call site passes `fruit=rest`, a pre-close
   snapshot (`tasks.py:8263`), so the row reads ~190–320 mm while every neighbouring row reads
   the true ~67 mm. The analysis must use the last `hold` row as the reference (this lane's
   tooling does).

---

## 2. The trace run design (a pre-registration sketch, to be frozen before any run)

### 2.1 The env

The mass base battery verbatim (`logs/p12a2/run_battery.sh`) + the trace knobs, one run per seed:

```bash
RUN_LIMIT=5400 scripts/154_claim_run.sh logs/p14b/10_seed11_trace.log \
    HEADLESS=1 ATTEMPTS=20 SEED=11 \
    FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 \
    FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 \
    FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 \
    FRUIT_PHYSICS_REAL_MASS=1 \
    FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 \
    FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1 \
    FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR=logs/p14b/traces_s11 \
    scripts/run.sh scripts/20_pick_place.py
```

Deliberately **not** set: `FRUIT_DYNAMIC_TRACE_PLACE=1` (the place legs are the
carried-not-placed class, a different failure; it doubles the volume for nothing here — set it
only if the place-escape is ever in scope), `FRUIT_ACQ_DIAG` (a scripted no-op), and any screen
knob. `FRUIT_HANDOVER_DIAG=1` is optional (one `[diag] premove/hover/wait/catchup` row per
attempt — the per-attempt approach geometry; phase-boundary reads only, low risk, but the trace
already moves the branch if it moves at all).

### 2.2 The per-tick rows the code actually emits (the exact list, current tree)

`FRUIT_DYNAMIC_TRACE=1` turns on `_dynamic_trace_sample` (`tasks.py:3358-3448`). Every row
carries: `phase, t` (sim s), `fruit[x,y,z], jaw[x,y,z], tip[x,y,z]` (tip = jaw + R·[0,0,0.06]),
`offset` (= tip − fruit), `sep` (measured jaw separation), `gap_cmd` (the commanded separation),
`force` (tactile sum), `contacts`, `ft{side_i: N}` (per-sensor split), `belt` (encoder speed),
`hand_rel` (= Rᵀ(fruit − jaw), the payload in the hand frame), `fruit_vel`, `fruit_omega`,
`quat[w,x,y,z]`, `finger_left/right[x,y,z]`; plus `cmd[x,y,z]` on the `catchup`/`carry` rows and
`soft_pad` only with `FRUIT_FINGER_SOFT_PAD=1`.

| phase | cadence (call site) | what it holds |
| --- | --- | --- |
| `descent` | 1 row at the descent start (`7257`) | the pre-close aim |
| `catchup` | every tick of the catch-up loop (`7597`) | `gap_cmd=gap_open`, `cmd=catch_target` |
| `close` | every tick of the two-phase close (`7929`) | the close's trajectory, `gap_cmd=cmd` |
| `hold` | every 2nd tick of the post-close hold (`8178`) | the settle before the probe |
| `dwell` | only with `FRUIT_DYNAMIC_VERIFY_DWELL=1` (`2077`) | off by default |
| `grip` | 1 row (`8263`) | **its `hand_rel` is junk (fruit=rest)** |
| `takeoff_probe` | every tick of each probe cycle (`8649`) | the 60-tick probe per cycle; `gap_cmd=squeeze_gap` |
| `takeoff` | every tick of the belt-break ramp (`9031`) | `gap_cmd=hold_gap` |
| `pluck_dwell` | only with `FRUIT_PLUCK_DWELL>0` (`9063`) | off by default |
| `carry` | every tick of the `grasp_lift` leg (`2818`) | `cmd=centre_ref`; the ejection window |
| `handover` | 1 row, direct path only (`6465`) | not on the scripted line |

**The re-seat window has no rows** (the gap in §1.6): a failed-probe cycle's trace is
`takeoff_probe × 60` → (untraced re-seat: 40-tick descent + optional 105-tick from-open close +
60-tick ratchet) → `takeoff_probe × 60` → … So a B1 attempt's file shows 3 probe blocks and 2
untraced windows; a B2 attempt's 1 block and none.

**Where the files go (verified on the current tree).** The scripted path calls
`_dynamic_trace_dump` in `grasp_carry_place`'s `finally` (`tasks.py:6485`) — the same dump the
direct path uses — so each attempt writes a **labelled** file
`$FRUIT_DYNAMIC_TRACE_DIR/trace_NN_{arm}_{scripted|direct}_{ok|fail}.json`
(`{arm, scripted, outcome, rows}`). `note_result`'s `_dynamic_trace_flush` then finds the rows
already drained and writes an **empty** `logs/dynamic_trace_NN.json` + prints
`[trace] dynamic attempt N: rows=0`. (This is why the W5-C logs show `rows=0` flush lines and the
real data in `logs/w5/traces_dense/`.) So the design's readout dir is
`FRUIT_DYNAMIC_TRACE_DIR`, and the run also leaves ~20 empty `logs/dynamic_trace_*.json` files to
relocate or ignore.

### 2.3 The seeds, the attempts, the run count

* **SEED 11 — the primary** (7 NG: 4 B1 + 3 B2; the only seed with enough B1 mass). `ATTEMPTS=20`.
* **SEED 5 / SEED 23 — the controls** (0 NG and 1 NG respectively): their role is the
  ok-population's per-tick shape under the same instrumentation (and, if the trace moves the
  branch, a second branch read).
* **Run count: 1 primary (seed 11) + 1 repeat (seed 11)** is the recommendation: the repeat tests
  whether the trace-on branch is itself deterministic (the dense W5-A evidence says the trace was
  run-neutral; the mass base must re-test it), and doubles the NG corpus if the branch re-draws.
  A **seed-5 or seed-23 trace run is the alternative second run** (a control-seed mechanism read;
  seed 23 carries 1 B1 + 17 ok, seed 5 0 NG) — prefer it if the question is "is the ok shape
  seed-stable" rather than "is the trace branch deterministic". Budget permitting, the full
  3-seed battery is the clean form; the pre-registration must pick one and freeze it.

### 2.4 The readouts (per attempt, from the rows above)

1. **The freeze geometry** — the last `close` row: `sep` vs `gap_cmd` (the achieved-vs-commanded
   stop; e.g. the mass-base a01 read `span 73.7 / freeze 69.9` = +3.8 mm), `offset` (where the
   fruit sits relative to the fingertip), `hand_rel_z` (where it sits along the tool axis), and
   the close-start `offset` from the first close row (the "close is late" test).
2. **The per-tick pad–fruit distance and angle** — `|offset|` and the angle of `hand_rel` from
   the tool axis, per tick, per phase (both derivable from the rows; no new code).
3. **The blocking-span check** — `sep − gap_cmd` per tick through close/hold/probe (does the
   measured span stop at the fruit's surface while the command walks below it — the P11-B
   geometry, now on the two-line's own attempts).
4. **The first departure** — the first post-hold row whose `hand_rel` has moved > 2 mm from the
   last-hold reference (the W8-B crossing scale), with its phase, tick and tactile state.
5. **The per-phase cumulative drift** — `max |hand_rel − ref|` per phase (hold, probe cycles,
   takeoff, carry) — the W5-C-style table (§1.5).
6. **The re-seat bracket** — for every failed-probe cycle: the last `takeoff_probe` row of cycle
   N (fruit world position, `hand_rel`, `force`, `contacts`) vs the first row of cycle N+1 (or
   the first `carry` row): the displacement across the untraced window, and whether the payload
   was still held at the window's near edge. Plus the per-cycle `[task] dynamic regrasp:
   re-seated in place (gap X mm kept)` rows and the servo row (`closed`, `trips`) for the
   command context.
7. **The carry** — the `carry` rows' drift and the `[carry]` leg summary (`clean_slip_max`,
   `onset_row`, `loss_row`) as the cross-check.

### 2.5 The analysis (offline; a new read-only tool under `logs/p14b/`)

* **Attempt pairing.** Pair each trace file to an attempt by **arm (from the filename) × the
  `[run] attempt N (side): … sim=X–Y s` window containing the file's row `t` range** (the rows
  carry absolute sim time; two arms run concurrently but each arm has one attempt at a time), and
  cross-check with the `[biarm] result side index=K species … lift=…` row (the dump order equals
  the completion order; `lift` to 3 decimals is the tiebreak). The `[trace] dynamic attempt`
  flush lines read `rows=0` on this path and cannot be used.
* **Segmentation.** Per attempt: `segments(rows)` by `phase`; reference = the last `hold` row
  (never the `grip` row).
* **The paired distributions.** For the primary corpus: the NG attempts (seed 11: 4 B1 + 3 B2)
  vs the ok attempts (11) — per phase, the per-tick distributions (median/p90) of the drift, the
  `sep − gap_cmd`, the force, the contacts; and the first-departure phase histogram. The controls
  (seeds 5/23) give the ok shape's seed stability. **The NG-vs-ok comparison is within-run** (the
  same instrumentation on both), so a moved branch does not invalidate it.
* **The phase-localized verdict.** One line per attempt: `outcome | probes | first-departure
  phase (t) | per-phase drift | the bracket displacement | the freeze geometry`. This is the
  table the P12-B.2 diagnostic asked for.
* **The thresholds, pre-registered**: the 2 mm crossing for the first departure (the W8-B scale);
  the drift's "clean" reference band from the ok population (the W5-C corpus reads 0.0–20.5 mm —
  quote the run's own ok range, not that number, since the scenario differs); the force-collapse
  condition `force < 0.5 N ∧ contacts == 0`; the bracket's displacement reported in mm with the
  window's duration.

### 2.6 The expected movement

* **The phase readout moves.** On the W5-C corpus the same analysis localizes 15/15 failures and
  separates them from the 35 oks (313–1992 mm vs 0–20.5 mm). On the mass base, the P10-E chain
  predicts the **B1 attempts' first departure inside the re-seat bracket or the probe**, and the
  **B2 attempts' in the takeoff** (their log rows already show the fruit gone by the carry start
  with the probe passed); the **ok attempts' drift should stay at the W5-C scale (tens of mm at
  most)**.
* **The close geometry moves** from a single summary row to a per-tick trajectory: the freeze's
  `sep − gap_cmd`, the fruit's position in the span, and the close-start offset become readable
  per attempt — the "tip/edge contact vs centred pinch" question (P10-E §2.5) becomes a measured
  distribution instead of an inference.
* **The re-seat bracket moves** from "unknown" to "the payload was still held at the window's
  near edge / already gone": the P10-E chain's decisive test, one bit per cycle, without any code
  change. (The within-window mechanism — the descent's own `sep`/`gap_cmd` per tick — does not
  move without the §2.9 code addition.)
* **The rate does not move**: the trace run is one or two branches, and (per the W5-A evidence)
  may replay the mass base exactly; either way the mechanism read is the endpoint, not the rate.

### 2.7 The falsifiers (pre-registered)

* **F1 — the re-seat is not the ejector (the P10-E §3.1 falsifier, now measured).** For every NG
  attempt whose loss completes before the carry: the last `takeoff_probe` row of the final failed
  cycle already reads the payload gone (`force < 0.5 N ∧ contacts == 0` or a `hand_rel` jump
  > 2 mm), and the bracket across the re-seat window shows no further displacement. If so, the
  loss precedes the re-seat and the re-seat-floor lever is dead before it is built.
* **F2 — the marginal close is not a geometry these rows can see.** The close/hold per-tick
  distributions (offset, drift, `sep − gap_cmd`, force) of the NG and ok attempts overlap
  completely **and** the first-departure phases are the same; then the class is not a close-phase
  geometry event on this interface.
* **F3 — the probe owns it.** The first departure is inside `takeoff_probe` (cycle 1) on the NG
  attempts while the ok attempts depart later (or not at all): the probe-shear reading, and the
  W5-C probe-screen negatives become the operative constraint.
* **F4 — the belt-break owns the B2 sub-class.** The B2 attempts' first departure is in the
  `takeoff` rows with the probe clean.
* **F5 — the analysis itself fails**: the ok population's drift is not small (no separation), or
  the trace-on run's outcome set is so moved that the NG population is empty at seed 11 (then the
  corpus is the seed-23/seed-5 control read or the anchor scenario, §2.9).

### 2.8 The cost

| item | estimate | basis |
| --- | --- | --- |
| one trace-off 20-attempt two-line battery | ~9 min wall | the mass drivers 8 m 20 s–9 m 35 s |
| one trace-on 20-attempt two-line battery | ~10–20 min wall | the W5-A 10-attempt trace-on dense run: 5 m 8 s; the per-tick readback adds the AGENTS §2 class of work |
| the trace files | ~20 × 233–521 KB ≈ **8 MB** per run (+ ~20 empty `logs/dynamic_trace_*.json`) | the W5-C files: 395–872 rows, 233–521 KB |
| the offline analysis | minutes (one pass) | this lane's tooling |
| the no-harm | none for the shipped line (env-only; the single-arm default is untouched) | — |

### 2.9 The design's honest caveats

1. **The re-seat window is untraced** (§2.2). The bracket answers *whether* the loss is inside it,
   not *what* inside it. If the bracket shows the loss is inside, the next run needs the
   trace-only addition — a `_dynamic_trace_sample("reseat", …)` call inside the two loops
   (`tasks.py:8721-8742` and `8756-8781`), ~4 lines, default-off, `src/`-scoped work outside this
   lane. The staged form (bracket first, patch only if needed) is the cheap order.
2. **The `grip` row's `hand_rel` is junk** (§1.6) — the analysis uses the last `hold` row.
3. **The scripted flush is misleading** (`rows=0`, empty `logs/dynamic_trace_NN.json`); the data
   is in `FRUIT_DYNAMIC_TRACE_DIR` with the dump filenames (§2.2).
4. **A moved branch is possible.** The W5-A evidence says the trace was run-neutral on the dense
   two-line (0 `[fruit]` diffs vs the W4 record), but the mass base must re-test it; the analysis
   is within-run so it survives either way, but any *cross-run* rate comparison is forbidden
   (AGENTS §2).
5. **The NG population is thin on the mass base**: 4 B1 + 3 B2 at seed 11. If a richer corpus is
   wanted, the **anchor scenario** (no `FRUIT_PHYSICS_REAL_MASS`) at seed 11 carries 8–10 NG
   (`logs/p10c/50_seed11_A.log` = 10), and its trace run would directly re-measure the P10-E
   chain on the population it was derived from — a named alternative (1 extra run) with the
   base-shift caveat.
6. **The density/scenario differs from the W5-C corpus**: the 0–20.5 mm ok band is *that*
   scenario's; the design quotes the run's own ok range.

---

## 3. The next-lever candidates the geometry would discriminate

The P11/P12 closed lists (all `tasks.py`, all default-off, all two-line-scopeable through
`_dynamic_profile`): the levers below are what remains *open* under each trace outcome. The
"closed" status is cited so no measurement is repeated.

| trace outcome | the mechanism | the surviving levers (ranked) | the closed ones (do not re-run as-is) |
| --- | --- | --- | --- |
| **the loss is bracketed to the re-seat window** (last probe row holds, next row gone) | the re-seat arrival at the chased keep-gap ejects | **(1) `FRUIT_DYNAMIC_REGRASP_FLOOR`** — the P11-A §5a floor `keep_gap = max(squeeze_gap, live_extent − margin)` + the ratchet floor; **named but never built**; the probe's blocking span (extent + ~11 mm of link span) says the floor's margin must be decided (a floor at the extent still commands 11 mm below the blocking span, so the floor may need the from-open arrival too). **(2)** the force-based re-seat gate (`FRUIT_FORCE_REENTRY` hysteresis) — as a *companion* to the floor, not alone. **(3)** the from-open arrival + floor compound (the from-open alone is measured negative: 35/60 pooled vs 39/60) | the arrival family as-is (from-open 35/60, +chase-stop 31/60, +range-cut 30/60 — P11-C, kill 2 fired); the `FRUIT_REGRASPS` bound (diagnostic only) |
| **the loss is in the close/hold** (drift starts before the probe) | the marginal close is the actuator | **(1) the close-load-rate** (`FRUIT_CLOSE_LOAD_RATE`, R11-B C1: the freeze row 18 → 55.5, the freeze-zone face speed 189 → 40 mm/s — but its stage-P scripted battery read 12/20 vs 13/18 with the never-grasped class 0 → 5, and its direct A/B stopped incomplete: **unconfirmed, not adopted**). **(2)** the squeeze-side family (`FRUIT_DYNAMIC_CLOSE_DEEP`/`FRUIT_GRIPPER_SQUEEZE`/`FRUIT_MIN_INTERFERENCE`; closed on the *direct* interface by R6-B/W8-B, not on the two-line). **(3)** the freeze criterion itself (the close freezes on the first sustained contact + span stall — a tip contact; requiring the span to reach the extent is an unbuilt control change) | the squeeze-side on the direct interface (R6-B/W8-B); the approach-height family (S3: negative at every seed, 32/60 vs 45/60) |
| **the loss is inside the probe (cycle 1)** | the 6 mm test lift shears the marginal grip | **(1)** the probe's shape (`FRUIT_DYNAMIC_PROBE` 0.006 two-line, `FRUIT_DYNAMIC_PROBE_TICKS` 60) — a gentler/shorter probe is unmeasured on the two-line; **(2)** `FRUIT_REGRASPS` bound (moves the mass toward B2/C, diagnostic); the W5-C screens (squeeze/TRACK/LOCK_X) are **closed negatives** | the W5-C screens (every config leaves the left class alive; LOCK_X destroys the signature's specificity; the servo's removal inert on the replicated attempt) |
| **the loss is in the belt-break/takeoff (the B2 shape)** | the velocity-matched belt-break's own shear | **(1)** the takeoff/belt-break timing knobs (`FRUIT_DYNAMIC_TAKEOFF_*`, the P3 take-off fix's own family) and the opt-in `FRUIT_DYNAMIC_LIFT_SETTLE=1`; **(2)** the belt-break's lead (`FRUIT_DYNAMIC_TRACK_LEAD` 0.18) — unmeasured as a grip lever | the takeoff squeeze screens (W5-C negatives) |
| **the loss is in the carry (the C / carried-not-placed shape)** | the mid-lift loaded slide | **(1)** the W8-B carry-window metric says the mechanism is a **loaded slide** (force at carry level, single-sided contact, jaws pried to their limit) and every bounded guard lever is measured negative; **(2)** the R11-B pre-onset load path is closed; **(3)** the physics lane (the mass base is the measured winner; compliance/restitution closed) | the carry guard (W8-B: 5-1 pairing, p = 0.109, not adopted; R6-B: 3-1, p = 0.31), the pre-onset knobs (R11-B C1/C2/M2), the relief cap (R6-B: force unchanged) |
| **no phase separation** (F2) | the class is not a geometry event on this interface | the named lanes: the physics (mass base + a *new* property direction), the containment (S4: falls 6 → 0 rows but the branch re-draws −13), and the supply/branch re-draw | the whole hand-side geometry family (S1/S2/S3 by derivation + measurement), the control-side ejection family (P11-C) |

**The top candidate, stated conditionally** (the honest form): **`FRUIT_DYNAMIC_REGRASP_FLOOR`**
(the keep-gap floor + the ratchet floor, the P11-A §5a recommendation) **if and only if the trace
brackets the B1 losses to the re-seat window**; the close-side family if the hold/close owns
them; the probe/takeoff families if those phases own them. The trace run's whole point is that
this condition is currently *unknown* — the offline mining's strongest statement is that no
aggregate row can settle it (§1.2–1.4), while the per-tick analysis demonstrably can (§1.5).

---

## 4. Honest limits of this lane

1. **No simulator run.** Everything here is a re-derivation from the existing logs plus the tree
   read. The trace design is a sketch to be frozen by the lane that runs it (the P12-B.2
   precedent: the S3/S4 batteries ran on a sketch and recorded the deviation — do not repeat
   that; freeze first).
2. **The W5-C trace corpus is a different scenario** (the dense W3 sheet, SEED 5, 10 attempts,
   the W5-C screen branches) — its 0–20.5 vs 313–1992 mm separation is evidence that the
   *analysis* works, not a prediction of the mass base's numbers.
3. **The keep-gap arithmetic's counterexample is one attempt** (the seed-5 apple). It is enough
   to falsify "a sub-extent first keep-gap implies the ejection" (a universal claim), not to
   estimate a rate. The census.py pairing for that row was verified against the raw log window.
4. **The incidence tests are small-n** (8 NG vs 45 ok; the regrasp-bearing subset 5 vs 5): the
   p-values are association strengths, not effect sizes; the pre-registration should treat them
   as priors, not endpoints.
5. **The mass base's NG class split (B1 5 / B2 3) uses the P10-E classify rules** re-implemented
   here from `logs/p10e/classify.py` (grip-phase and onset-row fingerprints); the pairing is
   `logs/p10e/census.py` copied verbatim (`logs/p14b/census.py`, md5 `3345de7c`).
6. **The `grip`-row junk and the untraced re-seat are tree facts** verified by reading
   `tasks.py` at the pinned md5; if the tree moves, re-verify both before running.
7. **The lane did not touch the simulator, the tree, or the running canaries.** All writes are
   under `logs/p14b/`.

---

## Appendix A: the tooling and the raw outputs (all under `logs/p14b/`)

| file | what it is |
| --- | --- |
| `census.py` | the P10-E pairing tool, copied verbatim (md5 `3345de7c2ed73c2902149540b2b35e3b`) |
| `mine_mass.py` → `mass_mining.txt` | the mass-base per-attempt census + the two separator tables |
| `keepgap_table.py` → `keepgap_run.out` | the regrasp keep-gap arithmetic per attempt (mass base + P10-E) |
| `trace_mine.py` → `trace_mine_*.txt` | the per-phase first-departure analysis of one trace dir |
| `trace_corpus_summary.py` → `trace_corpus_summary.txt` | the five-corpus combined table + the ok/fail drift split |

Reproduction (all read-only; `-B` avoids writing bytecode anywhere outside this directory):

```bash
cd logs/p14b
python3 -B mine_mass.py            # writes mass_mining.txt itself (and prints it)
python3 -B keepgap_table.py > keepgap_run.out
python3 -B trace_corpus_summary.py > trace_corpus_summary.txt
python3 -B trace_mine.py ../w5/traces_dense > trace_mine_traces_dense.txt
```

The raw rows behind §1.4 (the counterexample): `logs/p12a2/11_seed5_mass.log` lines 1123–1150
(close → grip 6.43 cm around a 6.52 cm fruit → `re-seated in place (gap 49.3 mm kept)` → the
`[carry]` row with `clean_slip_max=0.1mm`).

## Appendix B: the reads behind the design's tree facts

```bash
grep -n "_dynamic_trace_sample(" src/fruit_sorting/tasks.py        # the 11 call sites / phases
sed -n '8721,8742p;8756,8781p' src/fruit_sorting/tasks.py          # the two untraced re-seat loops
sed -n '6447,6486p;3505,3543p' src/fruit_sorting/tasks.py          # the dump (labelled files) + the wrapper
sed -n '8263p;8263,8270p' src/fruit_sorting/tasks.py               # the grip row (fruit=rest)
sed -n '6622p' src/fruit_sorting/tasks.py                          # FRUIT_ACQ_DIAG is direct-only
diff <(grep "\[fruit\]" logs/w5/20_dense_mech_trace.log) <(grep "\[fruit\]" logs/w4/20_dense_repeat.log) | grep -c '^>'
# -> 0: the trace-on dense two-line run is a superset of the trace-off record
```
