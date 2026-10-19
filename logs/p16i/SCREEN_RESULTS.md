# P16-I Stage-M screen results — H1 (the completed descent) at SEED 11 vs the on-disk traced control

Status: **offline analysis of the completed screen run** (branch `p-supply`, 2026-10-19). No
simulator run, no `src/`/`scripts/`/`configs/`/`datasets/`/`Paper/` edit, no commit; every write
of this lane is under `logs/p16i/`. The screen run itself is `logs/p16i/20_h1_trace.log` +
`logs/p16i/traces_h1/` (20 traces); the control is the **on-disk** traced mass base
(`logs/p14b/10_seed11_trace.log` + `logs/p14b/traces_s11/`, byte-identical to
`logs/p12a2/10_seed11_mass.log` per the P14-B record). The design under test is
`logs/p16/BOUNDARY_DESIGN.md` section 2.1 (pick (a)) / the pre-registration in section 4; the
implementation is `logs/p16i/IMPLEMENTATION.md`.

**Tree pins as run.** The H1 run was made on the P16-I tree: `tasks.py`
`54f70584b07fa249418f1efe30f30af0`, `rl_env.py` `be0248e0c3b88b28b0ec47ff28e1b68c`,
`fruits.py` `d28546d26137d4540421caa7fa34a139`, `meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`
(verified by md5 at read time). The control was run pre-diff on `tasks.py`
`810658b802d22bbd63013726fc78af81`; the new knobs are default-off and byte-inert, so the control
is valid as the like-for-like baseline by construction.

**This lane's tooling** (all under `logs/p16i/`, adapted from `logs/p14b/trace_p14b_analysis.py`
verbatim for the metric definitions - the P14-B file was read, not edited):
`trace_p16i_analysis.py` -> `31_tables_h1.txt` (the pairing check, the per-attempt tables, the
class distributions, the `[arrive]`/`[boundary]` tables, the falls) + `curves_h1/` (20 drift
curves); `scripts/186_w6_report.py` -> `32_interval_186.txt` (the interval/lock-on read);
`33_close_start_read.py` -> `33_close_start_read.txt` (a descriptive follow-up: the close-start
velocity state). `30_walk_h1.txt` is a byte-copy of the control's P14-B tables and is **not**
the H1 analysis (see section 7, note 1).

---

## 0. The answer in one screen

* **The mechanism endpoints moved, both of them.** The descent's `end=` shortfall (the settled
  gap) is **5.6-7.0 mm, median 5.9** against the control's **8.3-15.3 mm, median 9.4** (seed 11;
  the pre-registration's bar was median <= 6 mm) - the first quantity in this arc that any lever
  has moved. The catch-up's inherited first-row residual is **5.9-47.6 mm, median 6.7** against
  the control's **12.7-61.7, median 14.0** (bar <= 8 mm). The arrival converged in **7-24 ticks
  (median 9.5)** on 20/20 attempts, 19/20 inside the 6 mm tolerance, one cap-bound (7.0 mm).
* **The hold walk did not move (K1 fires).** The P14-B walk by class: H1 **B1 0.2-83.5 mm,
  median 36.1** vs the control's **1.6-54.8, median 35.0** (s11; the P14-B pooled record
  1.1-55.6, median 32.8); ok **-0.0-0.6, median 0.0** vs the control's **-0.0-12.8, median 0.0**.
  The same class structure, the same B1 magnitudes - the walk is *not* fed by the descent's
  shortfall. The failure's own mechanism is unchanged.
* **The outcome read worse on this one branch: ok 11 -> 8, no-grasp 7 -> 9, carried 2 -> 3.**
  The falls (<= -1000 mm) 4 rows / 4 attempts -> **7 rows / 7 attempts**; the B1 (3-probe)
  class 4 -> 6 and every fall is a B1 (plus one carried at H1). No new failure reason; no
  finger-belt jam (the belt margin stayed +25.0 mm or better); the probe-1 dz did not worsen.
* **Verdict: K1 - the descent-boundary family closes with the measured negative.** The
  pre-registration's own falsifier obtained: *the `end=` falls (the arrival works) while the hold
  walk does not move* -> the shortfall does not feed the capture. The promotion rule fails twice
  over (the walk did not enter the ok band; the no-grasp count rose +2 instead of falling), so
  **no Stage P, no adoption; both new knobs stay default-off**.
* **The honest outcome reading.** The mechanism improved and the outcome did not: the class
  census re-drew (B1 4 -> 6, falls 4 -> 7 rows) with the capture's own mechanism unchanged. The
  arrival's own cost is bounded and measured (7-24 extra ticks = 6-24 mm of extra belt travel
  before the close, median 9.5; a settled pose ~3-6 mm above the aim) and the close-start
  velocity state is unchanged (tip-fruit relv_y median +22 vs +28 mm/s; the hand is at belt
  speed on both) - so the delta is a moved-branch class re-draw at N = 1 x 20, not a measured
  capture-side degradation. Per AGENTS section 2 the outcome is quantized: quote the class
  census and the mechanism, not a cross-configuration rate delta.

---

## 1. The run and the pairing

| | H1 | CTRL (on disk) |
| --- | --- | --- |
| log | `logs/p16i/20_h1_trace.log` | `logs/p14b/10_seed11_trace.log` |
| traces | `logs/p16i/traces_h1/` (20) | `logs/p14b/traces_s11/` (20) |
| env (the design's reporting env + the H1 knobs) | the mass base + `FRUIT_DYNAMIC_ARRIVE_TOL=0.006 FRUIT_DYNAMIC_ARRIVE_MAX=24 FRUIT_DYNAMIC_ARRIVE_DIAG=1` | the mass base, no arrival knobs |
| attempts / successes | 20 / **8** | 20 / **11** |
| sim span / s per attempt / placed per min | 173.8 s / 8.7 / 2.76 | 190.0 s / 9.5 / 3.47 |
| per arm (placed) | left 2/10, right 6/10 | left 5/10, right 6/10 |
| `gate_open` / `queue_peak` / `recirculated` / `diverted` | 0.0 s / 0 / 0 / 3 | 0.0 s / 0 / 0 / 3 |

**Pairing verification (the P14-B rules, re-derived):** H1 **20/20** (file `arm` = result side;
file `outcome` = placed; the `[run]` window contains the trace's t-range; species agree) after one
tiebreak: the H1 log has two byte-similar left-apple no-grasp `[run]` lines (lift +0.000,
force 0.00), so the matcher uses the exact `sim=` span as the tiebreak (the tool's diff carries
the change; the control needed none). Control 20/20. The `[carry]` rows pair per arm by rank
(the k-th `grasp_lift` row of a side = that side's k-th attempt in start order); the
`clean_slip_max` values cross-check.

**The H1 class census (the P14-B/P10-E rules: B1 = 3 probe blocks, B2 = 1):**
**ok 8 / carried 3 / B1 6 / B2 3** (no-grasp 9). Control s11: **ok 11 / carried 2 / B1 4 / B2 3**
(no-grasp 7) - the P14-B record exactly.

---

## 2. The mechanism endpoint (i): the descent's `end=` (the completed descent)

The `[arrive]` rows (20/20, one per dynamic descent; `logs/p16i/31_tables_h1.txt` section I), with
the like-for-like control baseline:

| statistic | CTRL `end=` (motion rows) | H1 `start=` (pre-arrival) | H1 `settled=` (= the motion row's `end=`) |
| --- | --- | --- | --- |
| n | 20 | 20 | 20 |
| range | 8.3-15.3 mm | 8.2-17.7 mm | **5.6-7.0 mm** |
| median | 9.4 mm | 9.4 mm | **5.9 mm** |
| <= 6 mm | 0/20 | 0/20 | **19/20** |

* The pre-registration's endpoint moved: median 9.4 -> **5.9** (bar <= 6 mm met). The `start=`
  column reproduces the control's distribution (median 9.4), so the arrival is the only change.
* Arrival ticks: **7-24, median 9.5** (0-tick cases: none). The one cap-bound attempt is
  attempt 14 (left apple): 24 ticks, settled 7.0 mm - the only settled value above the
  tolerance. The loop is bounded and used, not saturated (20/20 ran, 1/20 hit the cap).
* The settled residual's direction (dx/dy/dz of `[arrive]`): **dx -5.1..+2.2, dy -2.5..+0.4,
  dz +3.1..+6.5 mm** - i.e. the completed descent now holds a small *systematic* offset (the
  hand ends ~3-6 mm above the aim, ~3-5 mm upstream in x) instead of handing the larger 3D
  residual to the fruit-tracking solver.
* The motion monitor's `steps`/`|v|max`/`a_*` still describe the profile leg only (by
  construction, `logs/p16i/IMPLEMENTATION.md` section 7): the profile speeds read 0.108-0.147
  m/s (control 0.107-0.118 - attempt 3's 0.147, right peach, is the one leg whose profile
  differs because the branch moved), and the arrival ticks are the `ticks=` column, not the
  monitor.
* The descent's hover wait is unchanged: 50-88 ticks (median 74.5) vs 52-87 (median 74.5).

### 2.2 The `[boundary]` margins (the H1 risk check)

* **`belt_margin` (the fingertip height above the belt top at the aim): +25.0..+43.1 mm, all
  positive, min +25.0** - the arrival never drove the small-fruit margin negative; no
  finger-belt jam class exists in the run. The design's risk (i) is measured clear.
* **Reach margins** (`reach_dn` = aim_y - band_dn, `reach_up` = band_up - aim_y; positive =
  inside that edge): 10/20 rows read inside on both edges (+30/+80 or +80/+30); 10/20 read
  **-20.0 mm on one edge** - the rows at x >= 0.36, where the *grip target* (the station +
  the 0.0 catch lead, `_two_line_catch_lead` default 0.0) sits 20 mm outside the
  `FRUIT_REACH_Y_INSET`-inset R10 clean band. The design's section 1.4 statement ("the aim is
  inside every band") refers to the *intercept* (the fruit's predicted position,
  station + 0.0170..0.0180), which is inside; the row measures the grip target. This is a
  scenario constant (the control would read identically with the diag on) and **not an H1
  effect** - the H1 knobs do not touch the aim or the band. Recorded here for completeness.

### 2.3 The mechanism endpoint (ii): the catch-up's inheritance

| statistic | CTRL | H1 |
| --- | --- | --- |
| first catch-up row residual vs the desired tip (fruit_z + 10 mm) | 12.7-61.7 mm, **median 14.0** | 5.9-47.6 mm, **median 6.7** |
| catch-up row count (its own tracking ticks) | 8-98, median 11.5 | **1-30, median 5** |
| catch-up exit residual (the log's `dynamic catch-up:` lines) | 5.1-6.0 mm | 5.6-6.0 mm |

The bar (median <= 8 mm) is met; the catch-up's own work collapses because the arrival hands it an
almost-converged hand. The largest H1 inheritance (47.6 mm, attempt 3 - right peach, the 4th
completion) is the attempt with the largest pre-arrival shortfall (17.7 mm) and 19 arrival
ticks - the fruit advanced during the arrival and the catch-up still had to chase it.

---

## 3. The hold walk (the K1 crux)

The P14-B metric, re-derived verbatim (the drift from the last `hold` row; the walk = its change
across the hold from the freeze), on the H1 traces and the control traces with the same code:

| class | H1 (n) | H1 walk mm | CTRL s11 (n) | CTRL s11 walk mm | P14-B pooled CTRL (design section 1.3) |
| --- | --- | --- | --- | --- | --- |
| ok | 8 | **-0.0 .. 0.6, med 0.0** | 11 | -0.0 .. 12.8, med 0.0 | 0.1-13.7, med 1.1 |
| carried | 3 | 0.0 .. 2.5, med 2.1 | 2 | 2.6 .. 5.8 | 3.6-6.8, med 5.2 |
| **B1** | **6** | **0.2 .. 83.5, med 36.1** | **4** | **1.6 .. 54.8, med 35.0** | **1.1-55.6, med 32.8** |
| B2 | 3 | 0.7 .. 15.8, med 5.1 | 3 | 0.0 .. 1.8, med 0.7 | 0.3-2.8, med 1.2 |

Per-attempt (H1, B1): 41.6 (att 1 left orange), 54.8 (att 5 left orange), 30.5 (att 9 left
apple), **83.5** (att 13 left apple), 10.4 (att 15 left pear), 0.2 (att 16 right lychee).
Control s11 B1: 38.1 (att 1), 31.9 (att 6), 54.8 (att 8), 1.6 (att 13).

**Did the walk move? No.** The B1 distribution is the same to the median (35.0 -> 36.1) and its
top end is *higher* (54.8 -> 83.5); the ok ceiling is unchanged (median 0.0; max 12.8 -> 0.6);
the class *structure* (ok quiet, B1 walking, B2 quiet, carried small) is identical. What moved is
the **count**: the B1 class is 4 -> 6, and every B1 is a fall attempt (the fall set is the six
B1s plus one carried, section 4.2). The design's K1 branch is measured: the hold walk is not fed
by the descent's shortfall; the walk remains the loaded slide of the capture itself (the
P14-B/P16 diagnosis).

The first-departure localization reproduces the same shape as the control: probe block 1 6/12
failures (CTRL 5/9), probe rows with no in-phase predecessor 3 (CTRL 2), takeoff 1 (1), carry 1
(1), the takeoff->carry gap 1 (0). The probe-1 dz: H1 median 6.9 mm vs CTRL 7.4 mm - the grip
test does not worsen.

---

## 4. The outcome

### 4.1 The classes and the census

| class | H1 | CTRL s11 | delta |
| --- | --- | --- | --- |
| ok | 8 | 11 | -3 |
| carried (grasped, not placed) | 3 | 2 | +1 |
| no-grasp (B1 + B2) | **9** (B1 6, B2 3) | **7** (B1 4, B2 3) | **+2** |
| placed (successes) | 8/20 | 11/20 | -3 |

The no-grasp growth of +2 is exactly the K2 kill threshold ("the never-grasped/no-grasp grows >= 2
at seed 11 -> negative, not adopted") and fails the promotion item (c).

### 4.2 The falls (the `lowest payload point` rows, the design's rule)

| | H1 | CTRL s11 |
| --- | --- | --- |
| rows <= -1000 mm | **7 rows / 7 attempts** | 4 rows / 4 attempts |
| regular falls (~-1.35..-1.39 m) | 5 (att 1, 9, 10, 13, 15) | 3 (att 1, 8, 13) |
| blowup rows (tens of metres) | 2 (att 5 -52.5 m, att 16 -22.1 m) | 1 (att 6 -55.3 m) |
| partials -100..-1000 | 0 | 1 (-218 mm) |
| class of the falling attempts | 6 B1 + 1 carried | 4 B1 (all four) |
| pooled control (3 seeds, for the record) | - | 6 regular rows / 6 attempts + 1 partial + 1 blowup (recount: s11 3 rows/3 attempts + s23 3 rows/3 attempts; the design's pooled line reads the same 6 regular rows + 1 partial + 1 blowup but 5 attempts - a one-attempt merge convention, immaterial to the seed-11 comparison) |

**Structural read: the falls track the B1 class.** On both configurations every B1 fell (the
ejected payload rides the belt to its end within the attempt) and no B2/ok did; the H1's extra
falls are its two extra B1s plus one carried attempt (att 10, right tomato, the `[carry]`
slip 192.0 mm class). The falls rose because the B1 census rose, not because a new failure path
appeared.

### 4.3 The interval / lock-on (the 186 tool)

| statistic (pooled) | H1 | CTRL s11 |
| --- | --- | --- |
| inter-placement interval, mean / p50 / p90 | 22.67 / 21.40 / 34.00 s (n=7) | 17.51 / 14.15 / 52.40 s (n=10) |
| batch throughput | 2.76 placed/min | 3.47 placed/min |
| placement-window throughput | 2.65 placed/min | 3.43 placed/min |
| per-arm placed/min | left 0.69, right 2.18 | left 1.71, right 1.89 |
| starved slots | left 41, right 0 | left 19, right 6 |
| left lock-on latency (mean / p50) | 5.13 / 4.60 s | 4.30 / 2.80 s |

Read the interval with the census, not against it: the H1's batch is *shorter* (173.8 vs 190.0 s,
8.7 vs 9.5 s/attempt) because five of its failed attempts end early (no place/release), and the
pooled interval is computed over 7 vs 10 placements. The right arm - the arm whose placement
count is unchanged (6/10) - holds 2.18 vs 1.89 placed/min, i.e. the H1's right-arm cadence is
not degraded; the left arm's 2/10 is the census. The starvation count (41 vs 19 on the left) is
the two-line worker polling the same seeded supply on a different timeline - descriptive, not a
lever effect (the arrival is downstream of the selection).

### 4.4 The failure reasons

* The notes are the **same two classes** as the control: `[]` (the carried/ok attempts) and
  `['fruit did not follow the gripper']` (all 9 no-grasp attempts). No new gripper note, no
  timeout/watchdog line, no `[collect]`-style stall, `diverted=3` on both.
* No finger-belt jam: the `[boundary]` belt margins are all >= +25.0 mm (section 2.3).
* The left force-servo trips (the known post-catch hold signature, `F_min = 0.00`, gap == sep)
  appear on both runs; the H1's right-arm servo trips once at the end (attempt 16).

---

## 5. The verdict (the design's K1 + the promotion rule)

**The promotion rule, item by item:**

* **(a) the mechanism endpoints moved - YES.** `end=` median 5.9 (bar <= 6); the catch-up's
  first-row residual median 6.7 (bar <= 8). **But the walk condition FAILED**: the walk did not
  fall into/below the ok ceiling (<= 20 mm) on >= 2 of the control's three hold-walk attempts -
  the H1's B1 population is 0.2-83.5 mm with 4 of 6 above 20 mm (under the literal
  attempt-index reading, 0 of the three corresponding attempts are <= 20 mm) - and **the seed-11
  no-grasp count did not fall >= 2 with the hold-walk attempts converting; it rose 7 -> 9**.
* **(b) the probe-1 read - borderline pass.** The probe-1 dz does not worsen (median 6.9 vs
  7.4 mm); the probe-1 first departures keep the same shape (6/12 vs 5/9 of the failures), with
  the count rise proportional to the failure count.
* **(c) no new failure reason - PASS on the reason, FAIL on the growth.** No new reason, no jam;
  but the never-grasped/no-grasp growth is +2 -> the item fails and K2 fires.

**K1 fires.** The pre-registration's own falsifier obtained: *the `end=` falls (the arrival
works) while the hold walk does not move* -> **the shortfall does not feed the capture**. The
descent-boundary family (the P16 lane's option (a)) closes with this measured negative; the
phase closes at Stage M; **no Stage P, no default change** (`FRUIT_DYNAMIC_ARRIVE_TOL` /
`_MAX` / `_DIAG` remain default-off, dynamic-capture-scoped).

**The outcome reading (the design's "upstream so it cannot trade by construction").** The
argument is refuted in the outcome reading: the mechanism improved, the outcome moved the wrong
way on this branch (ok 11 -> 8, no-grasp +2, falls 4 -> 7 rows), and the capture's own mechanism
(the walk) is unchanged. What is *measured* about the arrival's own motion:

* **The added ticks are bounded and real**: 7-24 ticks (median 9.5) = 6-24 mm of extra belt
  travel between the descent's end and the close's start (10-25 % of the ~96 mm close+hold
  capture window, the design's risk (iii)).
* **The settled pose is a small systematic offset**: ~3-6 mm above the aim, ~3-5 mm upstream
  (section 2.1) - the completed descent now *holds* that offset instead of leaving it to the
  fruit-tracking solver.
* **The close-start velocity state did NOT change** (a descriptive follow-up, not a
  pre-registered endpoint): the tip-fruit relative y velocity at the close start reads median
  +22 mm/s (ok) / +13 (B1) on H1 vs +28 (ok) / +15 (B1) on the control, and the hand is at belt
  speed (~-100 mm/s) on both - the "the arrival parks the hand on a static aim" hypothesis has
  no measured signature at the close start.
* Therefore the outcome delta cannot be attributed to a measured capture-side change on this
  data: it is a moved-branch class re-draw at N = 1 x 20 (the arrival changes the trajectory, so
  the run is a different branch by construction; the outcome is quantized per AGENTS section 2).

The honest one-line verdict: **the completed descent works as designed, the capture does not
care - and on this branch the failure mass re-drew (more B1s, more falls) rather than
reducing.**

---

## 6. The honest limits

1. **N = 1 run x 20 attempts, one seed (11).** The H1-vs-control deltas are single-sample branch
   readings; per AGENTS section 2, quote the class census and the per-leg mechanism, not a
   cross-configuration rate delta. A Stage-P battery (SEED 11/5/23) was not run (K1 closed the
   phase at M).
2. **The control is the on-disk traced run**, not a fresh same-session control. The knobs are
   default-off/byte-inert so the baseline is valid by construction, but the two runs were made
   on different tree revisions (`810658b8` vs `54f70584`) and at different wall times.
3. **The trace's run-neutrality is assumed, not re-verified, for H1**: the P14-B trace-on runs
   were measured byte-identical to the mass base; the H1 run has no trace-off double, so the
   trace's own effect on the H1 branch is unmeasured (the trace is pure reporting at call
   sites, by construction).
4. **The walk metric is the P14-B rule** (the drift change across the hold from the freeze),
   and the classes are the P14-B/P10-E rules; the `[arrive]`-settled / motion-`end=` identity
   was verified 20/20 in order.
5. **The `[boundary]` reach margins read the grip target** (the station, catch lead 0.0) against
   the inset R10 band, not the fruit's intercept; the -20 mm readings at x >= 0.36 are a
   scenario constant (section 2.3), not an H1 effect. The belt margin is the risk-relevant
   column and it is clear.
6. **The close-start velocity read (section 5) is a descriptive follow-up** of this lane, not a
   pre-registered endpoint; it is reported to bound the "the arrival's own motion" hypothesis,
   not to decide anything.
7. **`30_walk_h1.txt` in this directory is a byte-copy of `logs/p14b/trace_p14b_tables.txt`**
   (the control's tables), not the H1 analysis - a leftover of the first pass. The H1's own
   tables are `31_tables_h1.txt` (and this document).

---

## 7. The next

Per the design's flat/negative branch (its section 5.3 and the ranking's item 4), with the K1
negative published:

1. **The outcome-side residual - the carried class.** The B1/fall class tracks the scripted
   capture (the P14-B/P15 conserved mass); the *carried* (grasped-not-placed) class is the
   single failure mode of the direct/policy interface (W7-C: 32 of 33 failures; R9/R10/R11
   lanes) and the two-line's residual (W6-C section 5). The named candidate lanes already on
   the register: the R11-B pre-onset load path (its stage-N direct A/B stopped incomplete -
   `logs/r11/B_N/STOPPED.md` - the N=5 re-run is the open item if the owner wants it).
2. **The owner-gated D3-proper** (the pick station clear of the belt + a self-centring feeder +
   a boundary-respecting descent, R8-A's close-out; AGENTS section 2's "settle what the
   criterion should mean with the owner"). The P12-B.2 derivation (the catch is fruit-relative)
   still makes the naive scene change catch-null; the full form is the named scenario redesign.
3. **No re-entry of the arrival as a default.** The knob is a working, bounded instrument (the
   `end=` moved, the catch-up inheritance collapsed, no belt-margin risk) - keep it default-off
   for future mechanism questions (e.g. a scenario whose descent genuinely ends outside the
   reachable band, which is the v1 line, not this one).

---

## 8. Reproduction (read-only)

```bash
# the H1 tables (this lane's adapted tool; writes only under logs/p16i/)
python3 -B logs/p16i/trace_p16i_analysis.py > logs/p16i/31_tables_h1.txt
# the interval / lock-on
python3 scripts/186_w6_report.py logs/p16i/20_h1_trace.log logs/p14b/10_seed11_trace.log \
    > logs/p16i/32_interval_186.txt
# the close-start velocity follow-up
python3 -B logs/p16i/33_close_start_read.py > logs/p16i/33_close_start_read.txt
# the key rows directly
grep -hE '\[arrive\]|\[boundary\]' logs/p16i/20_h1_trace.log
grep -hE 'approach\(cartesian\)' logs/p14b/10_seed11_trace.log | grep -oE 'end=[0-9.]+ mm'
grep -hE 'lowest payload point' logs/p16i/20_h1_trace.log logs/p14b/10_seed11_trace.log
```

**What this lane did NOT do**: no simulator run, no `src/`/`scripts/`/`configs/`/`datasets/`/
`Paper/` write, no default changed, no branch operation, no commit; all writes under
`logs/p16i/`.
