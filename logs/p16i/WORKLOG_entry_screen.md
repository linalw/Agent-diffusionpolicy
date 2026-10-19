### P16-I Stage-M screen (2026-10-19, branch `p-supply`, offline read): H1 (the completed descent) at SEED 11 vs the on-disk traced control — the `end=` falls, the hold walk does not move, K1 fires and the descent-boundary family closes; the outcome read worse on the branch (ok 11 -> 8, no-grasp +2, falls 4 -> 7 rows) with no new reason

**Scope.** Offline analysis of the finished screen run (`logs/p16i/20_h1_trace.log` +
`logs/p16i/traces_h1/`, 20 traces; the H1 env = the mass base + `FRUIT_DYNAMIC_ARRIVE_TOL=0.006
FRUIT_DYNAMIC_ARRIVE_MAX=24 FRUIT_DYNAMIC_ARRIVE_DIAG=1`, `logs/p16i/run_screen.sh`) against the
**on-disk** traced control (`logs/p14b/10_seed11_trace.log` + `traces_s11/`; byte-identical to
`logs/p12a2/10_seed11_mass.log` per P14-B). The design under test is `logs/p16/BOUNDARY_DESIGN.md`
section 2.1/4 (pick (a)); the implementation is `logs/p16i/IMPLEMENTATION.md`. No simulator run,
no `src/`/`scripts/`/`configs/`/`datasets/`/`Paper/` write, no default changed, no branch
operation, no commit; all writes under `logs/p16i/`. Deliverable: `logs/p16i/SCREEN_RESULTS.md`;
the tooling is the adapted `logs/p16i/trace_p16i_analysis.py` (the P14-B metric definitions
verbatim; the P14-B file was read, not edited) -> `31_tables_h1.txt` + `curves_h1/`, plus
`scripts/186_w6_report.py` -> `32_interval_186.txt` and the descriptive
`33_close_start_read.py` -> `33_close_start_read.txt`. **Note:** `logs/p16i/30_walk_h1.txt` is a
byte-copy of `logs/p14b/trace_p14b_tables.txt` (the control's tables) left by the first pass —
it is not the H1 analysis; the H1's own tables are `31_tables_h1.txt`.

**Pins as run.** The H1 run was made on the P16-I tree: `tasks.py`
`54f70584b07fa249418f1efe30f30af0`, `rl_env.py` `be0248e0c3b88b28b0ec47ff28e1b68c`,
`fruits.py` `d28546d26137d4540421caa7fa34a139`, `meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`
(md5-verified at read time). The control was run pre-diff on `tasks.py`
`810658b802d22bbd63013726fc78af81`; the knobs are default-off/byte-inert, so the control is a
valid like-for-like baseline by construction.

**The mechanism endpoints both moved.** The descent's `end=` (the settled gap; the motion row's
`end=` equals the `[arrive] settled=` 20/20 in order): **5.6-7.0 mm, median 5.9** against the
control's **8.3-15.3, median 9.4** (the pre-registration's bar <= 6 mm met); the `[arrive]
start=` (the pre-arrival shortfall, the like-for-like control quantity) reads 8.2-17.7, median
9.4 — the arrival is the only change. The arrival converged in **7-24 ticks (median 9.5)** on
20/20, 19/20 inside the 6 mm tolerance; one cap-bound attempt (att 13 left apple, 24 ticks, 7.0
mm). The settled residual is a small systematic offset (**dz +3.1..+6.5, dx -5.1..+2.2, dy
-2.5..+0.4 mm** — the hand ends ~3-6 mm above the aim). The catch-up's inherited first-row
residual (vs the desired tip fruit_z + 10 mm) is **5.9-47.6, median 6.7** against the control's
**12.7-61.7, median 14.0** (bar <= 8 mm); the catch-up's own tracking ticks collapse **8-98
(med 11.5) -> 1-30 (med 5)**; both exit at 5.1-6.0 mm. The `[boundary]` risk check: `belt_margin`
**+25.0..+43.1 mm, all positive** (no finger-belt jam, the small-fruit margin clear); the reach
margins read the *grip target* (the station, catch lead 0.0) against the inset R10 band —
10/20 inside on both edges, 10/20 at -20 mm on one edge at x >= 0.36 — a scenario constant (the
design's "the aim is inside the band" refers to the fruit's intercept, station + 0.0170..0.0180),
not an H1 effect. The profile speeds read 0.108-0.147 m/s (control 0.107-0.118; the single 0.147
is the moved branch's att-3 right-peach leg); the descent's hover wait is unchanged (50-88,
median 74.5 vs 52-87, median 74.5).

**The hold walk did not move — K1 fires.** The P14-B walk by class (H1 vs the control's s11 vs
the P14-B pooled record): ok **-0.0..0.6, med 0.0** (n=8) vs -0.0..12.8, med 0.0 (n=11) vs
0.1-13.7, med 1.1; carried 0.0..2.5, med 2.1 (n=3) vs 2.6..5.8 (n=2) vs 3.6-6.8, med 5.2; **B1
0.2..83.5, med 36.1 (n=6)** vs **1.6..54.8, med 35.0 (n=4)** vs 1.1-55.6, med 32.8; B2 0.7..15.8,
med 5.1 (n=3) vs 0.0..1.8 (n=3) vs 0.3-2.8, med 1.2. The same class structure to the median, the
top end *higher* (54.8 -> 83.5) — the walk is not fed by the descent's shortfall; what moved is
the **count** (B1 4 -> 6). The first-departure localization keeps the control's shape (probe
block 1 6/12 vs 5/9; no-predecessor 3 vs 2; takeoff 1 vs 1; carry 1 vs 1; gap 1 vs 0); the
probe-1 dz does not worsen (median 6.9 vs 7.4 mm).

**The outcome read worse on this branch.** Classes (P14-B/P10-E rules; the H1 pairing 20/20 ok,
the control 20/20): **ok 8 / carried 3 / B1 6 / B2 3** (no-grasp 9) vs **ok 11 / carried 2 / B1 4
/ B2 3** (no-grasp 7) — the no-grasp growth of +2 is exactly the K2 kill threshold. The falls
(`lowest payload point` <= -1000 mm): **7 rows / 7 attempts** (att 1, 5, 9, 10, 13, 15, 16; 5
regular ~-1.35..-1.39 m + 2 blowups -52.5/-22.1 m) vs **4 rows / 4 attempts** (att 1, 6, 8, 13;
3 regular + 1 blowup -55.3 m; +1 partial -218 mm at att 7); pooled control recount 6 regular
rows/6 attempts + 1 partial + 1 blowup (s11 3 rows/3 attempts + s23 3 rows/3 attempts; the
design's pooled line reads the same rows with 5 attempts, a one-attempt merge convention).
Structural read: **every fall is a B1 attempt on both configurations** (H1: 6 B1 + 1 carried
att 10) — the falls rose with the
B1 census, not by a new path. The interval (186): pooled mean/p50/p90 **22.67/21.40/34.00 s**
(n=7) vs 17.51/14.15/52.40 (n=10); batch 2.76 vs 3.47 placed/min; window 2.65 vs 3.43; per arm
left 0.69 vs 1.71, right 2.18 vs 1.89 placed/min (the right arm's placement count is unchanged
6/10); starved slots left 41/right 0 vs 19/6 (the same seeded supply on a different timeline —
descriptive). No new failure reason: the notes are the same two classes (`[]` and `['fruit did
not follow the gripper']`), `diverted=3` on both, no jam, no timeout/watchdog line.

**The verdict per the design.** The promotion rule fails on its own items: (a) the mechanism
endpoints moved **but** the walk did not enter the ok band on >= 2 of the control's three
hold-walk attempts **and** the no-grasp count rose +2 instead of falling; (b) the probe-1 read is
a borderline pass (dz 6.9 vs 7.4, departures the same shape); (c) no new reason but the
never-grasped growth +2 -> K2 fires. **K1 fires: the `end=` falls while the walk does not move ->
the shortfall does not feed the capture; the descent-boundary family closes with the measured
negative.** No Stage P, no adoption; `FRUIT_DYNAMIC_ARRIVE_TOL`/`_MAX`/`_DIAG` stay default-off,
dynamic-capture-scoped. **The outcome reading:** the design's "upstream so it cannot trade by
construction" is refuted in the outcome reading — the mechanism improved, the class census
re-drew worse. The arrival's own measured cost is bounded (7-24 extra ticks = 6-24 mm of extra
belt travel before the close, median 9.5; a settled pose ~3-6 mm above the aim) and the
close-start velocity state is **unchanged** (the descriptive follow-up: tip-fruit relv_y median
+22 mm/s ok / +13 B1 on H1 vs +28/+15 on the control; the hand at belt speed on both), so the
delta is a moved-branch class re-draw at N = 1 x 20 (the outcome is quantized per AGENTS section
2 — quote the census and the mechanism, not a cross-configuration rate delta).

**Honest limits.** N = 1 run x 20 attempts, one seed (11); the control is the on-disk traced run
on a pre-diff tree; the trace's run-neutrality is assumed for H1 (no trace-off H1 double); the
`[boundary]` reach margins read the grip target, not the intercept; the close-start velocity read
is a descriptive follow-up, not a pre-registered endpoint.

**The next** (the design's flat/negative branch): the outcome-side residual — **the carried
class** (the single failure mode of the direct/policy interface; the named open item is the
R11-B pre-onset load path, whose stage-N direct A/B stopped incomplete, `logs/r11/B_N/STOPPED.md`)
— or the **owner-gated D3-proper** (the pick station clear of the belt + a self-centring feeder +
a boundary-respecting descent, R8-A's close-out; AGENTS section 2's owner item). The arrival knob
is a working, bounded instrument for future mechanism questions; it does not re-enter as a
default.
