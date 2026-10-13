# Working on this repository

Bimanual fruit sorting: a scripted sorting cell in Isaac Sim, a skill-routed
diffusion policy trained on demonstrations from it, and the measurement code that
keeps both honest. Read this before changing anything - the second section is not
style advice, it is what makes the numbers in the documents mean what they say.

## 1. Run before you finish

```bash
scripts/selfcheck.sh        # offline: motion kinematics, dataset index, collect/merge, ~7 s
scripts/accept.sh           # ten pick-and-place attempts + the motion gate + the baseline fingerprint
scripts/accept_policy.sh    # ten hybrid policy episodes + the policy floor and failure-reason gate
scripts/demo_2min.sh        # a few picks, a video clip, then the motion gate
```

`selfcheck.sh`, `accept.sh` and `accept_policy.sh` need no arguments;
`demo_2min.sh` takes `HEADLESS=0` to open the Isaac window. The three simulator
scripts call `selfcheck.sh` themselves, so a broken tree fails in seconds instead
of after a simulator run; `SKIP_SELFCHECK=1` bypasses that gate when you are
iterating on the simulator scripts. Every script with a simulator runs through `scripts/run.sh`,
which raises the file-descriptor limit - this Isaac build dies about 40 s into the
first camera read without it (`dup failed ... Too many open files`, then a wedged
crash reporter, so the window looks frozen rather than crashing). The four entry
scripts (`20_pick_place`, `40_collect_demos`, `60_eval_policy`, `70_record_video`)
also call `fruit_sorting.fdlimit.raise_fd_limit()` before creating `SimulationApp`,
so invoking `$ISAAC_SIM_DIR/python.sh` directly no longer dies that way; the wrapper
is still the supported path.

## 2. Two constraints that decide how to measure

**The outcome is quantized; do not compare success rates across configurations.**
The *scripted* line is deterministic per configuration - nine runs of the shipped
**v1 (stop-and-wait)** configuration are bit-identical in every statistic and every
per-leg metric - but it lands in one of
a small number of discrete *attractors*, and which one depends on instrumentation
as much as on physics. Two configurations in different attractors are different
scenarios, so a success-rate delta between them measures the attractor. Compare
per-leg motion metrics instead - for a descent, peak speed against the reference plus
the single-tick lurch bound; for a carry, the friction cone; `a_win5` on a descent is
a reported roughness warning, not a budget, because it is a *carrying* number being
applied to a leg that carries nothing - and state which attractor a run is in.

**Since the v7/F1 directive (2026-10-06) the shipped scripted default is the
dynamic never-stop line; the Gate-19 place sweep (2026-10-07) raised the place
profile to 0.35/1.089; the v9/V1 supply change (2026-10-08) replaced the
fixed-spacing feed with the scattered one (the supply paragraph below).**
With `FRUIT_DYNAMIC_PICK` unset the OpenArm scripted line takes the fruit on the
fly (on the pre-v9 fixed supply measured **9/10, 15.8 s/attempt**, the one
failure the A6 kiwi catch-window miss; on the shipped scattered supply measured
**9/10 x5 bit-identical, 15.2 s/attempt**, the one failure a left-arm
place/carry escape, `logs/v1/20_rate_supply_1..5.log`);
`FRUIT_DYNAMIC_PICK=0` restores the indexed *pick* (the P1 primitive - note the
scenario defaults are now the v7 ones: 0.12 m/s belt, the compliant finger
material, and the shared `FRUIT_APPROACH_AMAX` 0.4 -> 0.8 that the indexed
`_approach` reads too, so it is not bit-identical to the P1 logs; its v7-default
acceptance is `logs/fast/16_accept_indexed_v7.log`). The OpenArm policy
handover runs the P1 primitive by default and the **dynamic never-stop catch
with `FRUIT_DYNAMIC_PICK=1`** (v8/P1 directive). At belt 0.12 the dynamic
handover measured **27/45 = 60 %** before the P2b left-handover fix and
**32/45 = 71.1 %** after it (`moe_v12`, left 0/17 -> 6/17, one attempt short of
the scripted ceiling 33/45 = 73.3 %), against the indexed handover's
**16/45 = 36 %** (`logs/p1/`, `logs/p2b/ab012/`). The 0.15 ladder is a wash
(`moe_v12` 31/45 unfine-tuned, fine-tuned `moe_v13` 30/45) and 0.18 was not
run. **The policy's dynamic handover stays opt-in** - with the env unset the
handover keeps the P1 indexed primitive; `scripts/130_policy_demo.sh` enables
it for the visible demo (`FRUIT_DYNAMIC_PICK=0` there restores the indexed
handover). The motion gate derives the descent speed
budget from the shipped profile (per-leg distance; the budget is 1.10x the
*profile peak*, and the fast-profile clean legs achieve ~0.75 of that peak
because the conveyor boundary ends every descent 40-90 mm short, so the
effective slack is ~1.47x, not 1.10x), the
dynamic line's carry cone is *reported* rather than gated (its escapes are the
failure mechanism; `--strict-cone` re-imposes the old rule), and the dynamic
success floor is 0.75 of ten attempts while the indexed floor stays 0.9. Treat a
dynamic rate the way the v2 paragraph below says: one configuration is one
sample of a deterministic branch, so quote the per-leg cone/slip and the
mechanism, not cross-configuration rate deltas.

**The supply is scattered and mixed (v9/V1, 2026-10-08).** `FRUIT_SUPPLY_SCATTER=1`
(shipped) builds a 16-fruit pool with the designed mix (8 A / 5 B / 3 C grades -
the lane rule splits A vs the rest, so 50/30/20 keeps both lanes fed - and two
of each class), a seeded shuffle of the arrival order, gaps sampled in
0.10-0.35 m of belt travel, and a lateral band x = 0.20-0.36 m (not the belt
width: the top-down catch's measured reach band is x = 0.18-0.39 with a hard
cliff at 0.42 - `scripts/174_station_reach.py`,
`logs/v1/61_station_reach_seeded.log`). The feeder keeps an absolute schedule
and releases the backlog at the positions the fruit would have reached when the
drivers' sparse `update` calls leave it behind, so the approach segment is
stocked ("several at once") instead of the old one-fruit-per-attempt
(`queue_peak=0`) line. `FRUIT_SUPPLY_SCATTER=0` restores the fixed line
**line-identical** (`logs/v1/00_accept_scatter_off.log` matches
`logs/g/40_accept_default.log` on every line). The moving catch's selector
refuses candidates inside `_dynamic_select_floor()` (~0.40 m at 0.12 m/s: the
selection-to-handover setup consumes ~1.5 s of belt travel) and takes the
farthest-upstream eligible fruit (a lane takes the nearest usable one); without
that floor the stocked belt hands the catch a 0.10-0.18 m fruit and the rate
collapses to 1/10 (`logs/v1/pre_fix/`). Delivered on the shipped scenario:
single-arm **9/10 x5 bit-identical, 15.2 s/attempt**; the bimanual (opt-in)
stays structurally starved (74 % of its station slots report no eligible fruit)
- the two-line rework (V2) owns that. The reference is
`configs/motion_reference.json`, re-recorded from the identical
`logs/v1/30_accept_supply.log` (old at
`logs/v1/motion_reference_pre_supply.json`); the green *acceptance* run is the
re-verified `logs/v1/31_accept_supply_verified.log` (30's own gate read FAIL
only because the reference it was re-recorded from did not exist yet). The policy path is **OOD** on this
supply (the demos carry one candidate per attempt, and the trigger's
`|dx| <= 0.06` gate (pre-W4; now 0.16) refuses the outer half of the new band); do not quote the
71.1 % direct number as the current-scenario rate - one hybrid canary on the
new supply scored **1/10** (8 grip losses + 1 handoff miss,
`logs/v1/80_accept_policy.log`), an OOD warning the V3 phase owns.

**W4 (Gate 30, 2026-10-10, `logs/w4/`): the dense direct collapse is the
trigger's lateral gate, and the two-line recollection is the wrong anchor for
the single-arm direct interface.** Direct 2x2 + gate cell (N=3x15, seeds
77/101/202): `moe_v13s` dense 0.06 **7/45** (left 0/20, 21/45 no-fire);
`moe_v12` dense 0.06 **14/45**; `moe_v13s` pinned 0.06 **28/45** (left 2/18,
45/45 fires); **`moe_v12` pinned 0.06 33/45 (left 8/18)** - reproducing the
P2b 32/45 / left 6/17 on the current tree, so the single-arm direct path is
unchanged by W1/W2/W3 (their additions are two-line-scoped); `moe_v13s` dense
0.16 **19/45** and the shipped-default re-run **17/45** (1/45 then 0/45
no-fire). The `|dx| <= 0.06` gate was calibrated to the fixed line's ~5 mm
spread and refuses the outer half of the x = 0.20-0.36 band (debug: no-fire
fruit x = 0.20-0.24 vs the ~0.34 station line, |dx| ~ 0.10-0.14), so
**`FRUIT_POLICY_TRIGGER_LATERAL` defaults to 0.16 now** (still inside the
measured reach band x = 0.18-0.39; `=0.06` reproduces the old gate). The
residual left-arm failures are the carry/grip class on every supply. Pinned
canary samples with `moe_v13s`: 7/10 (one novel reason, unattributed), 6/10
PASS (gate of record), 8/10 PASS; the hybrid loop never runs the direct
trigger, so the gate of record does not depend on 0.06 vs 0.16. The
final-tree acceptance `logs/w4/70_accept_w4_tree.log` (9/10, fingerprint
matches) ran with `SKIP_SELFCHECK=1`; the final-tree selfcheck is
`logs/selfcheck.log` (failed=0).

**The v2 dynamic line is weaker than that.** It takes the fruit *on the fly*, so
the tick the tracking window opens on depends on the fruit's continuously evolving
position; two runs of the identical default scored **10/10 and 9/10** with all ten
legs' `samples` and `|v|max` identical (v2 evidence: `logs/370` and the preserved
gate output `logs/accept_v2.out`; `logs/461_posture_transit.log` is a v2-era trace
and `logs/accept.log` is now the v3 run). Read a v2
scripted count as one sample too - five runs, quote the distribution - and note that
the per-leg *fingerprint* now uses `[samples, |v|max]` only, because the old third
field was the jitter-sensitive `a_max` and produced false "different attractor"
verdicts. The
*policy* loop is
weaker still: two runs at the same spawn seed pick the same ten fruits in the same
order but do not agree on the outcomes (10/10 vs 9/10, see the WORKLOG), so a
single policy run is one sample and any published rate needs several. Five runs
span 70-100 % (mean 88 %) and the failures concentrate on the 3.4 cm strawberry -
read the per-episode table the gate prints, not just the rate.

**A conveyor's collider has to belong to a body.** The belt slab was a static
collider, so `PhysxSurfaceVelocityAPI` did not drag the fruit: they travelled at 18 %
of the commanded speed and spun (measured, `logs/170/171`), which is what
`transport_efficiency = 0.40` was hiding. As a kinematic rigid body they ride at
1.01-1.14x (`logs/173`). `scripts/170_transport_probe.py` is the regression check: it
reports the encoder (cleat travel), the fruit/belt speed ratio, the spin ratio and the
stalled ticks. Any change to the belt or the fruit has to be re-measured there.

**The descent's speed excursions are the workspace boundary, not a push.** Every
approach line reports `end=` - where the leg ended against the point it was sent to -
and on both shipped and candidate configurations *every* descent ends **40-90 mm
short** (`logs/160/161`): the pick pose is outside the arm's reachable band (see the
README's "Known limit"), so the arm runs to its boundary and stays there while the
profile carries on, and the post-descent solver finishes the approach. In an isolated
cell with no fruit the achieved/commanded speed ratio is 0.92-0.96 on 16/16 descents
(`logs/155`), and the anomaly trace shows nothing near the arm at the jitter ticks
(nearest fruit 95-134 mm, lowest link 36 mm above the belt, `logs/158`). The stop is a
**collision with the conveyor**: `scripts/47_robot_collision.py` drives the jaw 23 cm
when the belt is removed and 3.8 cm - stopping 8 cm above the belt top, with the finger
geometry inside the belt - when it is there (`logs/166` vs `logs/167`). Gains
(`logs/165`) and integral action on the drive target (`logs/163`, which also doubled
`|v|max`) both leave the shortfall unchanged. Do not re-tune the descent's `|v|max`
budget to admit a configuration - the ratio has no clean gap and the budget cannot tell
a boundary strain from a real push - and do not "fix" it by capping the hand. Fix the
boundary (a pick station clear of the belt, or a descent command that respects it), or
settle what the criterion should mean with the owner (the options are listed in the
WORKLOG entry "the descent is blocked by the conveyor").

**A carry leg's `|v|max` is the hand, not the payload.** Every `[motion] carry` line
reports the kinematic pads' own speed right after `recoveries=`; `in-hand |v|max` is
the payload's *relative* motion and on a rescued leg the two are the same number to
three digits, because the reaction re-seats the pads 25-40 mm in one tick. Clean legs
sit at the commanded 0.176-0.371 m/s. The checker prints this and how many legs exceed
0.45 m/s as a report; do not "fix" it by capping the hand (`FRUIT_HAND_VMAX`) - that
was measured and makes the escape worse (`logs/150`).

**Instrumentation that runs in the control loop changes the result, so it must be
off by default.** Reading the articulation's link world poses every tick shifts
the run by 3-14 s of simulated time and one or two picks; so does adding per-tick
work *inside* `ik_step`, even two small array copies. Fruit-pose reads, camera
reads and pure reporting do not. Hence every diagnostic knob defaults to off,
`ik_step` carries a comment saying so, and traces are used for mechanism rather
than for the numbers quoted in the documents.

**The bimanual line is opt-in and shares one station.** `FRUIT_BIARM=1` runs the
pipelined two-arm scheduler (`src/fruit_sorting/bimanual.py`): one arm owns the
pick station from its pre-pose until its carried payload clears a box around it,
the other pre-poses while the first carries and places, and a **main-thread
arbiter** executes one *shared* physics tick per round (so both control loops
stay at 120 Hz in simulated time - one tick per arm per round doubles every
phase and breaks the catch calibration) and grants a single run permit (exactly
one attempt thread executes at a time). Measured on the frozen F2 tree: 9/10 x5
bit-identical (left 4/4, right 5/6), 16.0 s/attempt, 3.38 placed fruit/min
against the then-shipped single-arm 8/10, 18.4 s/attempt, 2.61 placed/min - a
1.30x placed-fruit rate (`logs/biarm/`, WORKLOG "F2"). **G re-derived it on the
Gate-19 place-0.35 default (2026-10-07, `logs/g/`): the bimanual is 9/10 x5
bit-identical, 15.0 s/attempt, 3.59 placed/min (left 3/4, right 6/6; the failure
is a left apple first-lift escape) against the single arm 9/10, 15.8 s/attempt,
3.42 placed/min - 1.05x, because the faster place shortened the single arm's
cycle more than the pipeline's.** Per the pre-registered reading (non-inferior
rate and placed/min clearly higher) the default was **not** flipped:
`FRUIT_BIARM=1` stays opt-in, `FRUIT_BIARM=0` is explicit, and the shipped
default remains the single-arm dynamic line. The new default's clearance trace
reads **6.2 mm** minimum inter-arm link-origin separation with 257/15024 samples
under 30 mm (the F2 45 mm / zero-under-30 figure is pre-Gate-19 timing; no
attempt failed by arm-arm contact) - quote the clearance per configuration.
A bimanual log is a *different scenario*: compare its budgets
and rate, and give it its own fingerprint via `105_motion_regression.py
--write-fingerprint` (preserve the single-arm reference) - do not read a
fingerprint mismatch as a break. Its scheduler invariants are pinned offline by
`scripts/152_biarm_selftest.py` (a selfcheck leg); rates come from
`scripts/153_biarm_rates.sh` (the F2 shape; it skips existing logs) or
`logs/g/run_g_rates.sh` (the Gate-19-default batch, interleaved with the single
arm), the per-attempt table from `scripts/151_biarm_report.py`.

**The v9/V2 two-line scheduler is the explicit opt-in `FRUIT_BIARM_TWOLINE=1`;
`FRUIT_BIARM=1` keeps the shared-station meaning above.** The V2
pre-registration's decision rule (`logs/v2/PREREGISTRATION.md`) kept the
shared-station pipeline because the two-line's placed/min gain missed the 1.25x
replacement bar; the shipped code briefly defaulted it on, and the V3
integration reverted that to 0 (`logs/v3/`, WORKLOG "V3 integration"). Each arm
owns a station on the shared belt: left y = 0.00 (the shipped pick point),
right y = -0.10 (the deepest station the right arm's top-down reach holds <= 6 mm
across the supplied band; the left cannot cross the body), solved from the same
calibrated grasp seed with a station-specific pre-pose configuration so the two
approaches stay on their own sides. Selection is **grade-preferring with an
any-grade fallback** - eligibility is not grade-filtered (that was the V1
starvation), the +Y lane carries the left arm's stream (mostly A) and the -Y
lane the right's (mostly B/C), and the fallback produces measured crossovers
(3/10 on the frozen tree, 5/10 in the V2 sample). Replacing the meaning of
`FRUIT_BIARM=1` would need the owner's sign-off on that grade-biased output
semantics (`logs/v2/PREREGISTRATION.md` "Routing semantics"). Measured on the
frozen tree (`logs/v3/10_rate_twoline_1.log` + the bit-identical double-run,
`15_rate_twoline_1b.log`): **6/10 placed, 9.8 s/attempt, 3.66 placed/min
(left 3/5, right 3/5, `gate_open=0.0 s`, zero `indexed:`)** against the
single-arm 9/10, 15.2 s, 3.55 placed/min - **1.55x per attempt but 1.03x
placed/min** (the contact-grip class costs it the placements, so the named path
to a dual-arm default is the grip class, not more supply). **W1 (2026-10-09,
`logs/w1/`) shipped the grip profile on the two-line path: after a failed
probe lift the regrasp re-seats in place (no open phase around a walking
fruit) and the probe is gentler (6 mm/60 ticks, step 0.01); scoped to the
two-line by `_dynamic_profile` because the same values as global defaults
drop the single arm 9/10 -> 6/10.** On the shipped profile: **7/10 x5
bit-identical plus a bit-identical no-env double-run, 9.2 s/attempt, 4.59
placed/min = 1.29x** against the single arm 3.55 (1.25x bar met); the
single-arm default is byte-unchanged and its acceptance fingerprint matches
(`logs/w1/50_accept_single.log`). Per-tick
availability on the free-cadence scattered supply is **left 3.06 % / right
0.00 % None** (the old lane filter on the same line: 38.5/42.4 %); the
delivered per-slot starvation is **4/9 left but all four are the batch-start
belt-prime at t = 13.4-14.9 s, steady-state 0/5 for both arms** (the report
prints both; `scripts/175_twoline_report.py`); per-arm idle between turns
**42 % -> 17 %/18 %**. The W1 branch's clearance (re-measured in W2,
`logs/w2/10_trace_before.log`; that run is bit-identical to the trace-off W1
rate run) reads **min 13.9 mm** (`openarm_left_left_finger` vs
`openarm_right_hand`, t=95.8-96.3 s, left=grip/right=close), **62/10672
samples < 30 mm** - the pre-W1 **6.8 mm** figure (`left_link7` vs
`right_link6`, t=106.4 s) was the old 6/10 branch's 10 s post-attempt freeze,
which the W1 profile removed. The W2 park/handover redesign could **not** meet
the F2 **45 mm / zero-under-30 mm** convention at the rate floor: the moving
catch rides the belt ~0.22 m through its dwell (longer than the reachable
station separation; the left's upstream catch is reach-clean only to +0.10 and
the right's downstream to about -0.13), the best measured clearance state
(38.9 mm, zero<30) landed 6/10 at 9.8 s/attempt, and time-separating the
dwells (a start gap) costs the span ~1:1 (4 s gap -> 11.2 s/attempt). All W2
levers are default-off; the two-line stays opt-in and the shipped W1 branch is
unchanged (`logs/w2/RESULT.md`). No attempt failed by arm-arm contact. A
two-line log is a different scenario: compare its budgets and rate, and give it
its own fingerprint.

**W3 (2026-10-10, owner): the grade routing is per-arm and pure, the supply is
a continuous dense sheet, and the two-line collects.** With the **W3 pure
routing** (`FRUIT_GRADE_ROUTING`, default pure on the two-line selector) the
left arm takes **grade A only**, the right **grade B only**, and **grade C is
never selected** - it rides past both stations to the main belt's end
(`despawn_y = -0.70`), is counted `reached_end` and recycled by the feeder;
`FRUIT_GRADE_ROUTING=0` restores the V2 grade-preference-with-fallback. The
single-arm selector passes no `prefer_lane`, so the shipped line is
byte-unchanged (its acceptance still reads 9/10 + fingerprint matches).
The **dense-sheet supply** (`FRUIT_SUPPLY_WAVE`, default on when
`FRUIT_BIARM_TWOLINE=1`, off otherwise; owner correction 2026-10-10: the first
pass's spaced bursts with 0.70-1.00 m empty gaps are superseded) releases
clusters of `SIZE=5` at 0.10-0.16 m with cluster-boundary gaps of only
0.09-0.12 m, so the clusters run **back-to-back as one continuous sheet - no
empty stretch anywhere**; the same seeded RNG stream drives it. The
two-line scenario defaults the pool mix to balanced **A:B:C 0.375/0.375/0.25**
because pure routing starves the B arm under the shipped 50/30/20. Measured on
the dense sheet (`logs/w3/30_dense_trace.log`, trace on): **8/10, 11.2
s/attempt, 4.27 placed/min, per arm left 4/6 right 4/4, `gate_open=0.0 s`,
zero `indexed:`** (the pick is the never-stop dynamic catch); clearance
**min 2.6 mm / 618 samples <30 mm** - the W1/W2 belt-riding-dwell + idle-hand
classes. **W4 (2026-10-10)**: the trace-off repeat is **bit-identical** to the
trace-on run on all 476 physics `[fruit]` lines (`logs/w4/20_dense_repeat.log`:
8/10, `diverted=1` orange index 10, 11.2 s/attempt, 4.27 placed/min); the
same-scenario single-arm baseline (dense sheet + balanced mix) is **9/10,
15.1 s/attempt, 3.59 placed/min** -> the W1 1.29x does **not** carry to the
dense supply (**1.19x** < the 1.25x bar), so the default-flip recommendation
is **no**. **No arm-arm contact is possible in this build**
(`openarm_flat_deinst.usda` `enabledSelfCollisions=0`) and no attempt has ever
failed by contact. Every measured no-overlap lever trades the rate away (start
gap, station widening, catch lead + park bias, the opt-in capture token
`FRUIT_BIARM_CAPTURE_TOKEN=1`); the full screen table is in `logs/w3/` and the
WORKLOG W3 entry. All W2/W3 levers stay default-off. The **collector** runs
the two-line branch (`40_collect_demos.py` chunks through `run_bimanual`),
records both arms with a per-episode `station_y` label (new,
backwards-compatible index field; the recorder is thread-local and allocates
unique indices itself) and its **stall guard is a per-episode watchdog, never
a belt stop**: `FRUIT_COLLECT_EPISODE_S` (default 600 s) arms
`task.episode_timeout_s`, `_step_sim` raises `AttemptTimeout` on an
over-budget attempt, and the collector **skips and retries** it (partial
recording discarded, fruit recycled, line still running; verified with a 6 s
budget smoke where 6/6 attempts were skipped and `gate_open` stayed 0.0,
`logs/w3/100_timeout_smoke.log`). A hard progress window
(`FRUIT_COLLECT_STALL_S`, 600 s) remains only for a fully blocked C++ call the
soft deadline cannot interrupt (the wedges were a blocking
`RenderingManager.render()` under the bimanual bridge); it exits the shard
with a stack dump and the shard loop advances the seed. The spaced-burst
recollection is archived (`datasets/demos_v12_spaced`, `checkpoints/moe_v13s_spaced`
with its own 8/10 pinned canary); the corrected dense-sheet recollection
finished as **158 episodes in one shard with no wedge** (`datasets/v12d_s02`,
2 h 6 min; merged to `datasets/demos_v12`, arms 80/78) and fine-tuned
`moe_v12` -> `checkpoints/moe_v13s` (6 epochs, loss 0.0261, router 0.981;
anchor `demos_v11` because the v12+v10 stores exceed this 125 GB machine).
The dense checkpoint's **pinned canary is 6/10 PASS** on the gate of record
(`logs/w3/81b_canary_v13s_pinned_dense.log`; a first sample read 7/10 but
carried one novel reason, recorded in the WORKLOG), and its direct eval on the
dense supply is **7/45 = 15.6 %** (single-arm presentation, no-trigger
fruit-off-line; `logs/w3/70_direct_v13s_dense.log`). The corrected tree's
acceptance is **9/10 + fingerprint matches** with `gate_open=0.0 s`
(`logs/w3/62_accept_single_dense_tree.log`). The W3-supply hybrid canary is
the remaining hand-off item (`logs/w3/HANDOFF.md`).

**W5 (Gate W5-C, 2026-10-10, `logs/w5/`): the existing-knob mechanism screens
are all negative - H1 is falsified as the cause, not repaired; the watcher is
not built; the policy's left deficit is acquisition, not takeoff.** On the
dense two-line (SEED=5, `ATTEMPTS=10`, Tier A solo, `logs/w5/run_screens.sh`)
five configurations were screened - cfg0 shipped, cfg1
`FRUIT_DYNAMIC_FORCE_SERVO=0`, cfg2 `+FRUIT_DYNAMIC_TAKEOFF_SQUEEZE=0`, cfg3
`FRUIT_DYNAMIC_TAKEOFF_TRACK=0.2`, cfg4 `FRUIT_DYNAMIC_TAKEOFF_LOCK_X=1` -
each a trace-off double-run plus one trace-on run; every config is
bit-identical within itself (cfg1 476, cfg2 474, cfg3 453, cfg4 484 physics
`[fruit]` lines) and cfg0 is a byte-no-harm replay of the W4 record
(`logs/w4/20_dense_repeat.log`, 476 lines). **Every screened configuration
leaves the left class alive** (cfg1 6/10, 3/5+3/5; cfg2 8/10, 3/5+5/5; cfg3
6/10, 2/5+4/5; cfg4 7/10, 3/5+4/5). **H1 (takeoff squeeze-out as the cause)
is not supported**: cfg2's `trace_05` attempt 4 is byte-identical through the
loss with the squeeze and the servo off (first difference carry row 2,
t=59.925), so the named actuators are not its actuator; removing them (cfg2
attempt 7) or pinning x (cfg4) only moves the loss to carry with the same
failed outcome. **H2 is closed as a recovery lever** - the pre-registered
"inert" closure did not obtain (the failure set changes: 4 failures, both
arms) and the "amplifier" reading is equally unsupported (the servo's removal
is inert on the replicated attempt 4, bit-identical, and recovers nothing on
its own branch, 6/10). **TRACK and LOCK_X are negative**: cfg3 destroys the
signature's specificity (the composite fires on a success), and cfg4's own
branch is not a controlled replay (it first diverges inside attempt 1's
probe, row 120, t=18.64) - on it the probe/takeoff stays clean and the loss
moves to carry, consistent with, not proof of, the x-tracking hosting the
escape. **The watcher is not built**: with the sanctioned both-finger force
AND relative-pose key there is no detection/react window (carry losses keep
2-8 N on one finger, cfg1's right pear 32-46 N; where force collapses the
payload is out within 0-3 ticks), a pose-only key fires on successes, and
there is no drop-at-output phenomenon to contain. **H5, scoped to the
W4-pinned `0.06` branch: the policy's left failures differ from the scripted
takeoff squeeze-out** - one direct-path trace (`moe_v13s`, pinned supply,
`FRUIT_POLICY_TRIGGER_LATERAL=0.06`, seed 77; 11 complete + 1 started of 15,
7 success, left 0/3) shows 2/3 traced left failures never make contact
(pre-contact acquisition; one catch-up diverges at the +5.2 cm lateral
trigger edge; ep8's automated `takeoff`/`span_open` label is a no-contact
pad-clamp artifact) and the third is a healthy close/probe lost ~1 s into
carry (the carry-escape class shared with the scripted line); do not quote it
as the current-scenario mechanism outside that branch. The surviving
directions: the **policy acquisition knob first**, then the
**second-seed/size-pinned scripted control**, then the **scripted grip-margin
lever only if the wedge recurs**. No-harm (knobs off, single arm):
`scripts/selfcheck.sh` PASS 0 failures; acceptance **9/10, 15.2 s/attempt,
`diverted=0`**, motion gate PASS and `fingerprint: matches
configs/motion_reference.json`; the acceptance's **385/385** physics
`[fruit]` lines are IDENTICAL to the W4 record. Final tree: `tasks.py
69823dc1` (the whole diff is the default-off `FRUIT_DYNAMIC_TAKEOFF_LOCK_X`
knob + comments) and the metadata-only `rl_env.py` `TASKS_MD5` pin 280d0951
-> 69823dc1.

**W6 (Gates W6-A/B/C, 2026-10-10/11, `logs/w6/`): the throughput metrics are
the inter-placement interval and the lock-on; the supply is the designed 2D
patch sheet; the park-gate lever is the measured win and L1 prefetch is a
measured null.** The tree pin: `tasks.py` **fa9594fb** (the two default-off,
two-line-only knobs `FRUIT_BIARM_PARK_EARLY` and `FRUIT_BIARM_PREFETCH` + the
prefetch-gated handover line), `fruits.py` **a0ea1f54** (`FRUIT_SUPPLY_PATCH=1`
- 0.14-0.22 m along-slices of 1-2 fruit abreast, pair probability 0.6,
0.085-0.12 m separation, shipped x band; default off and every pre-patch supply
stays byte-reproducible), `scripts/186_w6_report.py` **49242875** (the
interval/lock-on/idle/park-split report - the `41`/`45` artifacts are from this
pin), `scripts/188_w6c_levers.sh` **b4308c66** (the lever driver), `rl_env.py`
`TASKS_MD5` metadata-only follow `69823dc1` -> `fa9594fb`. The battery is the
two-line (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) on the patch sheet,
`ATTEMPTS=20`, SEED=5, balanced mix, Tier A solo, plus the same-scenario
single-arm run; the metrics are the per-arm + pooled **inter-placement
interval** (t1 of consecutive placements), the **lock-on** latency (previous
attempt end -> station acquired = selection time), the idle fraction and the
`[cycle]`-mark decomposition (SPEC section 2). **Baseline** (`BASELINE.md`):
two-line **10/20**, batch 2.78 / placement-window **2.70 placed/min**, pooled
interval **22.20 s mean / 45.50 s p90**, idle 26 %/29 %; single arm **13/18**,
2.12/2.17 placed/min -> the same-scenario **window ratio 1.24x** (1.31x by
batch span is the boundary-inclusive variant; do not mix the two
denominators). The delivered 2D-ness is the worker-cadence per-selection read
**7/9 = 77.8 %** of selection instants facing an abreast slice; the free-
cadence design number (93.5 %) must never be quoted as delivered. **W6-C
(`C_RESULTS.md`)**: the **park-gate lever** (`FRUIT_BIARM_PARK_EARLY=1`, opens
the park gate as soon as the other arm's payload clears its station box)
moves the pre-registered pair - pooled interval **22.20 -> 16.53 s** mean,
**45.50 -> 19.90 s** p90, left gate-blocked idle **25.2 -> 0.2 s**, placement
window **2.70 -> 3.63 placed/min** - but it is a **different branch** (12/20
vs 10/20; 7 placed-False + 1 takeoff vs 6 + 4), so quote the timing-only
**+10 %** and the residual **x1.22** factor, not the raw +34 %.
**L1 prefetch (`FRUIT_BIARM_PREFETCH=1`) is a measured null: 0/40
attempt-ends reserved** (0 reservations in each of the two prefetch runs; the
combined pair 1/40, which went stale at slot start - 0.22 m past the right
station, below the +0.30 m floor): the feeder's release cadence runs at the
attempt boundary **after** the park and `state()` reads live positions, so the
attempt-end lane is empty; the consume path was never exercised. L1 stays a
default-off **hook** (re-fire gate: reservations > 0 AND a consumption) and
**L2 (adaptive lead) is next**, with the measured wait-to-handover inputs left
mean 2.93 s / p90 3.7, right 3.39 / 4.4 and the SPEC 7.3 floor-override
prerequisite. Clearance is unchanged by both levers: **1.9 mm min, 4.7 %
< 30 mm** (`37`/`38`/`39` JSONLs - the two scripted hover poses; no arm-arm
contact is possible in this build, `enabledSelfCollisions=0`). **No-harm:**
every config pair bit-identical (821/850/843 physics lines), knobs-off
two-line 830/830 vs the W6-B record and single-arm 643/643 vs the W5-C record,
`selfcheck.sh` PASS, acceptance **9/10 + `fingerprint: matches`**
(`logs/w6/60_accept_w6c.log`) - the single-arm default is byte-unchanged. Both
W6-C knobs were default **OFF** and two-line-only; the owner decision then
promoted the park-gate lever (**W7-A below**), while `FRUIT_BIARM_PREFETCH`
stays a default-off hook; the
placed-False and takeoff grip failure classes are W6-E's recollection +
fine-tune territory (`logs/w6/C_RESULTS.md` section 5).

**W7-A (2026-10-12, `logs/w7/`): the park-gate lever is the two-line default
(the W6-D owner decision).** `FRUIT_BIARM_PARK_EARLY` now resolves through
`_dynamic_profile("FRUIT_BIARM_PARK_EARLY", "0", "1")` at both gate sites, so a
two-line session opens the gate at payload-clear with the env unset and an
explicit `=0` restores the pre-W7 rule; `FRUIT_BIARM_PARK_GATE` stays off and
`FRUIT_BIARM_PREFETCH` stays the default-off hook. Pins: `tasks.py`
**bf822c09**, `rl_env.py` `TASKS_MD5` metadata-only follow `fa9594fb ->
bf822c09`. The W6-B patch battery with the default on replays the W6-C park
pair **bit-identically** (861/861 physics lines vs `logs/w6/31` and `32`):
**12/20, 3.64 batch / 3.63 window placed/min, pooled interval 16.53 / 17.30 /
19.90 s, idle 18 %/24 %** - the W6-C numbers and the timing-only **+10 %** /
residual **x1.22** reading stand. The dense W3/W4 wave-sheet re-record is a
**moved branch** (the pair is bit-identical 442/442): **7/10, 9.1 s/attempt,
4.60 placed/min** (left 2/5, right 5/5, `diverted=0`, first divergence at the
left station acquisition t=30.4 vs 31.4) against the pre-flip 8/10, 11.2 s,
4.27/min - a quantized-outcome count, so quote the fingerprint and the per-leg
motion (all 10 descents inside budget; worst `|v|max` 0.111/0.161, lurch
0.023/0.291), not the delta. The **dense 10-attempt** two-line fingerprint is
now `configs/motion_reference_twoline.json` (**181c9151**, written from
`logs/w7/10`, matched by `11`; references are per-scenario - the multi-scenario
battery would need its own); the single-arm `configs/motion_reference.json`
is byte-untouched (`b9e72ca7`). No-harm: the single-arm patch run is 643/643
identical to the W6-C record (681/681 on the full stream), the acceptance
stream is 385/385 identical to `logs/w6/60_accept_w6c.log`, `accept.sh` reads
**9/10 + `fingerprint: matches`**, `selfcheck.sh` PASS, `172` 52 checks. The
W7-A.1 attribution control - the same dense run with `FRUIT_BIARM_PARK_EARLY=0`
(`logs/w7/15_dense_control_park_off.log`) - replays the W4 record
**bit-for-bit** (476/476 full, 456/456 physics-only; 8/10, 11.2 s/attempt,
`diverted=1`), so the flip is the only cause of the moved branch; the moved
branch's clearance (its trace run is bit-identical to the pair) reads
min **2.59 mm**, 863/10042 = 8.6 % of samples < 30 mm - the W1/W2/W3 carry-past
class, no arm-arm contact possible in this build.
Tooling note: gating a two-line log with `105_motion_regression.py` directly
trips its *single-arm* 0.75 success floor even when the motion budgets pass -
use `scripts/190_twoline_gate.sh`: it pins the two-line scenario (the
`[biarm] two-line scheduler:` banner), the per-scenario reference (default the
dense 10-attempt `configs/motion_reference_twoline.json`) and an explicit
two-line floor (default 0.60 - the 7/10 branch of record; the 20-attempt W6-B
patch battery takes `-m 0.5` and its own reference). 105's own floor stays the
single-arm 0.75, and `--write-fingerprint` now refuses a motion-budget-failing
run (a rate-only failure still writes). The chain's compares are assertions
now (`scripts/189_w7a_chain.sh`, `W7A_OFFLINE=1` re-asserts them offline).

**W7-B guardrail (the flip's other consumers).** The two-line *collector*
(`40_collect_demos.py` with `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) drives the
same `run_bimanual` session, so a post-W7-A two-line collection gets the
park-gate lever with no env set - the flip silently changes that path too.
`datasets/demos_v12` (shard `v12d_s02`; its manifest pins `tasks.py`
`c8854d6c`) is **pre-flip**, so a post-W7-A two-line recollection is a **new
branch**: the shard manifest's `src/fruit_sorting/tasks.py` md5 pin
(`e98d9836` on the W7-B/W7-C tree; `bf822c09` after W7-A) identifies it, and
since W7-C the manifest's `collection.park_early` field names the lever
(`"auto"` = the flip's on-for-two-line default). Do not mix the two; gate a
re-collected two-line arm with `scripts/190_twoline_gate.sh` (its own reference
if the supply differs) plus the scenario's floor.

**W7-B (2026-10-12, `logs/w7/`): the policy's left deficit is pre-contact
acquisition, not the lateral off-band; the adaptive trigger lead is the
default-off acquisition knob.** The direct-path mechanism run on the W4-pinned
branch (`moe_v13s`, pinned supply, `FRUIT_POLICY_TRIGGER_LATERAL=0.06`, lead
0.9 s, seed 77, `FRUIT_DYNAMIC_TRACE=1`) reads left 0/6 as 3 no-contact + 3
carry escapes (right 9/9), and the W4 pinned population is left 2/18 with 13
`grasped=False` + 3 carried: the no-contact acquisition class is the left's
majority failure. Its measured actuator is the scripted handover's setup
(0.60-0.93 s on successes/carry escapes, **1.36-7.68 s on every traced
no-contact failure**) against the fixed 0.9 s lead - the fruit is 171-2119 mm
downstream of the fingertips when the close starts, past the left's ~4.5 cm
downstream reach, so the 200-tick catch-up expires and the pads clamp each
other at take-off. The off-band reading is refuted on the population (the
close-start offset is a downstream overshoot - the fruit sits `+171...+501 mm`
past the fingertips against `<= 5.7 mm` on the successes/carry escapes; W4's 13
left no-contact split 10 trigger-path + 3 policy-gate, and the trigger-path
`|dx|` no-contact median 0.8 cm vs ok 2.5 cm sits inside the 0.06 gate; every
first-close-tick `vx0` ~ 0, `latch=centring`; no probe/takeoff squeeze-out
signature), so the W5 FRONTIER Lever 1's close-phase x-seek / ramp-start form
is not built. The shipped knob is `FRUIT_POLICY_TRIGGER_ACQ`
(default off, direct-path trigger only): `lead_eff = lead + 0.6 s +
|jaw-station| / 0.20 m/s` (cap 4.5 s) with the reach gate raised with it
(`..._ACQ_SPEED/MARGIN/CAP/REACH` override); `FRUIT_ACQ_DIAG=1` adds one
`[acq]` line per direct attempt (setup stage times, close-start tip-fruit
offset, walk latch, first contact, freeze, joint-limit margin). The A/B
(`scripts/112_rl_ab.sh`, N=3x15, seeds 77/101/202, interleaved, both arms
instrumented, `logs/w7/B_ab/`): **left no-contact 9 -> 1** (of A's 9, 8 are
trigger-path - the knob's reach, 8 -> 1 - and 1 is policy-gate; B has zero gate
attempts; the residual 1 is the measured **trigger-fired** arm flail, both
`move_to` caps 3.33+4.17 s with the joint at its limit), left close-start median
**88.8 -> 1.4 mm**, 10/18 left episodes improve class with zero left
regressions; pooled
**26/45 (58 %) -> 31/45 (69 %)**, left **2/18 -> 8/18**, paired 7 B-only / 2
A-only (both right-arm carry escapes - the branch shift), sign p = 0.0898
(N=3; the P4 p<=0.05 criterion was for 5 runs/arm - the W7-B pre-registered
endpoint is the mechanism readout); strawberry 3/6 -> 5/6; median cycle
1851 -> 1826 ticks (successes +1.8 %); no new failure reason once the note
suffix is normalized out. The knob **stays default off** (W7-B spec, no
shipped-default change). No-harm: selfcheck PASS, acceptance **9/10 + gate
PASS + fingerprint matches**, stream **385/385 identical** to the W7-A
acceptance; pins `tasks.py` **e98d9836**, `rl_env.py` **9318fe3e**,
`policy/trigger.py` **d35fba2c** (the A/B manifests pin all three per run).
W7-C implication: the remaining left deficit is the carry/grip-margin class
(7 -> 9 carried) plus the reach-cliff flail and the policy-gate fire path
(`finger < 0.030 and |jaw-fruit|xy < 0.06`, 4/18 of the W4 left attempts,
which bypasses the trigger); the collector is unaffected (the scripted
primitive never uses the trigger), so the W7-C recollection targets the carry
class. W7-C (above) ran it: at N=3 the fine-tune converted right-arm carry escapes
(carried 32 -> 29, carried-class 3-0 paired; **not confirmed - the W8-A N=5
batch below reads 0 B-only / 2 A-only**) and left the left carry class
untouched (3/16 -> 3/18) - the recollection *did* target the carry class, but
the left residue needs a lever aimed at the scripted branch's own open item,
not another behaviour-cloning pass.

**W7-C (2026-10-12, `logs/w7/`, `logs/w7/C_RESULTS.md`): the patch-sheet
direct interface - the acquisition knob is pinned in-scenario, the
recollection moves the carry class, the rate verdict is underpowered and
`moe_v13p` is not adopted; the two-line collector's manifest and stall-guard
gaps are closed.** The `collection.park_early` field above is operative
(every W7-C shard manifest records `"auto"`); the W7-C.1 additions are the
`supply.patch` block and the guard's stats flush. The scenario is the W6-A 2D
patch sheet
(`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`, balanced A:B:C
0.375/0.375/0.25, lateral 0.16, lead 0.9); the two-line collection
(`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, camera 240,424, post-W7-A branch with
the park-gate lever on) records **173 episodes** into `datasets/demos_v13p`
(nine shard dirs, left 89 / right 84, `106_index_audit` OK; **nine renderer
wedges across the nine shard-runs** with **14 soft-watchdog attempt skips** -
the union is the store, the shard dirs are the provenance unit, and
`gate_open=0.0 s` / zero `indexed:` hold as the collector's *enforced*
never-stop invariant). Fine-tune `moe_v12 -> moe_v13p`
(`checkpoints/moe_v13p/policy_best.pt` md5 **fed54993b4aebdaf2c779bf09a18698e**;
`demos_v13p` rollouts + the single-arm base `demos_v11`, the `moe_v13s` recipe;
both checkpoints sit on the single-arm lineage - v13s also used the `demos_v11`
base). **Pins.** The W7-C direct evaluation runs with
`FRUIT_POLICY_TRIGGER_ACQ=1` in-scenario because the A/B on this supply
measures the knob's mechanism endpoint (left no-contact 15 -> 0, close-start
median 120.1 -> 2.5 mm) while the recollection targets the carry class; the
knob stays default **off** and the shipped hybrid canary never runs the trigger
(the canary of record reads **8/10 PASS** and matches the v13s sample). The
class split (C_ab): with the knob on **32 of 45 attempts (32 of 33 failures)
are carried-not-placed** - the single failure mode of this interface - and the
per-arm n shifts with the fire timing, so compare per-arm *classes*, not
per-arm rates (the direct env sets the arm from the fruit grade). **The
evaluation:** paired direct A/B `moe_v13s` vs `moe_v13p` (both ACQ=1, N=3x15,
interleaved): 10/45 (22 %) -> 13/45 (29 %), **carried-class 3 B-only / 0
A-only** (the overall rate pairing is 1 B-only / 2 A-only), carried 32 -> 29,
right ok 7/29 -> 10/27, left unchanged 3/16 -> 3/18, sign **p = 0.125** at
N=3; the one new reason (`timeout: no grasp within 1500 ticks`, one episode) is
a no-fire/horizon timeout, *not* the policy-gate class (B has zero gate fires).
**Verdict: no measured improvement by the P4 criteria - no adoption**
(`accept_policy.sh` keeps the shipped default `moe_v12`). **W8-A superseded
the N=3 read with the confirmatory N=5 batch** (`logs/w8/A_RESULTS.md`):
pooled **21/75 (28 %) vs 22/75 (29 %)**, sign **p = 1.0000**, carried-class
pairing **0 B-only / 2 A-only** (carried 49 -> 47, right ok flat
20/52 -> 19/49) - the 3-0 pairing and the 32 -> 29 movement did **not**
confirm, so only the negative is published. The two-line rollout-store ->
direct-interface transfer stays an open W4 risk the W7-C A/B tested only
weakly. **Collector (W7-C.1, `scripts/40_collect_demos.py`):** the shard
manifest now records the patch sheet (`supply.patch` + slice/pair/sep), and
`_stall_dump` flushes a `[collect] stats:` line before its `os._exit(3)`, so a
wedged shard carries the gate-open invariant instead of implying it; existing
shard manifests are not rewritten (their md5 pins are the provenance record).
Tooling: `logs/w7/C_class_split.py` / `C_acq_forces.py` are the read-only
re-derivations; `logs/w7/C_acq_forces.py` is what withdrew the first pass's
Fmax force split (close-phase `Fmax` does not separate the classes - the
grip-margin reading is a hypothesis, not a measured force split).

**W8-B (2026-10-13, branch `w8-carry`, `logs/w8/`): the carry-window metric
exists and separates; the one bounded guard lever is measured and NOT adopted;
the legacy `[motion] carry slip_max` must not be quoted for the OpenArm hand.**
The metric is the frame-free `clean_slip` (payload displacement in the leg's own
frame, reference = the leg's first tick): over four trace corpora (55 attempts)
the clean leg-outs read **0.02-1.43 mm** (median 0.04, n=33) and the carry
escapes **17.9-957 mm** (median 278, n=31) with **no overlap**; 25 never-held
legs (reach-cliff class) are excluded. It is live in the default-off
`FRUIT_CARRY_DIAG=1` `[carry]` line and offline in `logs/w8/B_metric.py`
(agreement <= 0.06 mm on 29/29 legs; the live onset bookkeeping is
contact-agnostic and includes no-contact legs - onset rows 1-3, `F=0` - unlike
the offline classes). The mechanism is a **loaded slide** (force at its carry
level at onset, median 4.90 N; single-sided contact; jaws pried to their
98-99 mm limit in 17/31 escapes; contact loss 2-132 ticks after the 2 mm
crossing, median 25). The lever `FRUIT_CARRY_GUARD` stays **default off**
(direct-scoped: `_carry_guard_active` needs `direct_capture`, so a scripted call
never reaches it; `FRUIT_CARRY_GUARD_LEGS` is an exact per-leg-name match, so a
place scope reads `place0,place1`): it moved the paired carried class 5-1 and
carried-not-placed 50 -> 42, but sign p = 0.1094 and +5.4 % cycle -> **not
adopted**; the R1 lever slot is closed with the named residuals
(`logs/w8/B_RESULTS.md`). No-harm: acceptance **9/10 + motion gate PASS +
`fingerprint: matches`**, its 385/385 `[fruit]` lines byte-identical to
`logs/w7/50_accept_w7a.log`; the two-line half is gated by
`scripts/190_twoline_gate.sh` (PASS on the frozen-tree re-record
`logs/w8/70_w8b1_twoline.log`, whose 442/442 `[fruit]` lines are identical to
the W7-A dense record). **Do not quote the
legacy `slip_max` for the OpenArm hand**: it is frame-contaminated
(25.6-104.7 mm of ghost slip on the acceptance's placed carries) - use
`clean_slip`; `README.md`'s grip-quality paragraph carries the same correction.

**R2 (2026-10-13, branch `w8-residuals`, `logs/w8/R2_RESULTS.md`): the C note,
the cross-lane label is real, and the flail class has three terms.** The
two-line patch store's zero-C is by construction (W3 pure routing never
selects C); the direct interface presents C and measures it as its best grade
(W8-A 43 %, W8-B 46 %; confounded with the arm - A->left, B/C->right), and the
C windows train from the single-arm base `demos_v11` (C 21/50). A top-up, if a
C-specific need ever appears, is a single-arm collection
(`FRUIT_SUPPLY_GRADES=C:1`), never a two-line store. The patch canary's
`cross-lane station fruit ... placed on lane M` note is **a real event emitted
by the primitive** when the station-presented fruit (patch pair / queue)
belongs to the other lane: the arm takes it onto its own lane and records the
sort error (`canary_patch` 6/10 - the W7-C text's 5/10 is corrected - and the
reproduction 4/10; not failure-specific). The direct path's **flail** class
(18/390 `[acq]` attempts, close starting 0.17-0.92 m downstream, joint at its
limit) decomposes into a **premove/configuration term** (the policy's incoming
pose; removed by the default-off `FRUIT_DIRECT_RESEED=1` re-seed: capped
premoves 9/15 -> 0/15, median error 43 -> 21 mm, flails 10/15 -> 13/30 pooled),
a **hover/reach-edge term** (the 8 mm hover tolerance is unattainable at
x >~ 0.39; the default-off `FRUIT_POLICY_TRIGGER_X_MAX=0.39` refuses those
would-fire ticks - 7 recorded refusals, 0 refusals/0 flails on the shipped band
- but sub-cap fires still flail and the **policy-gate path bypasses the
trigger**: 4 of 7 refusals were attempted anyway, WS-4.6), and a **catch-up
stall term** (fast setup, 28-212 mm residuals). Neither knob is adopted; both
are default off and direct-path-only. Do not read a catch-up timeout as a
fire-time miss: the fire-time dx spans -4.1..+8.3 cm across the class.

## 3. What changed -> what to run

| you changed | run |
| --- | --- |
| docs, or a number's provenance/data size | `python3 scripts/106_index_audit.py` and `python3 scripts/107_collect_merge_test.py` |
| motion, control, `trajectory` limits, IK | `python3 scripts/96_motion_check.py`, then `scripts/accept.sh` |
| collection (`40_collect_demos.py`) or merging (`41_merge_demos.py`) | `scripts/107_collect_merge_test.py`, then `python3 scripts/106_index_audit.py` |
| simulator behaviour, scene, gripper, conveyor | `scripts/accept.sh`, then `scripts/demo_2min.sh` |
| the bimanual scheduler (`bimanual.py`, or the task loop under `FRUIT_BIARM=1`) | `scripts/selfcheck.sh` (the 152 leg), the `logs/biarm/` rate batch (`scripts/153_biarm_rates.sh biarm 5`), then `FRUIT_BIARM=1 scripts/accept.sh` |
| the policy, training or the dataset schema | `scripts/selfcheck.sh`, `scripts/accept.sh` (scripted baseline), `scripts/accept_policy.sh` (policy loop) |

To compare two **policy** arms, use the harness rather than two runs:

```bash
EPISODES=12 RUNS=3 scripts/140_policy_ab.sh          # ARM_A / ARM_B are env assignments
```

It runs each arm N times back to back in one session with a seeded sampler, then
reports the per-episode outcomes per arm, the per-class rates, and whether the arms'
ranges overlap (`scripts/141_policy_ab_report.py`). Aggregate the *outcome* per
episode; a continuous quantity such as peak lift varies run to run even when every
episode succeeds.

Two cautions from its first uses. **Instrumentation is part of the measurement**: the
closure diagnostic changes the outcome (arm A scored 92 % with it off and 67 % with it
on), so compare arms inside one instrumented batch and quote a rate together with how
it was measured. And `AB_EXTRA_ENV="FRUIT_CLOSURE_DEBUG=1"` is the way to get the
mechanism (the grip geometry) from the same runs that give the rates - which is how the
extent-close question was settled.

## 3b. How to run a comparison that means something

**A single run is a measurement again, but only because of a fix - keep it.** The
same command used to land its fruit at 8.5 cm from the pick point on one run and
8.7 cm on the next, because `app_utils.update_app(steps=N)` is not a fixed step (sixty
calls advanced 118 ticks on one run and 120 on the next). `FRUIT_FIXED_STEPPING`
(default on) routes every scripted advance through `SimulationManager.step`, and with
it five probes and three acceptance runs came out bit-identical
(WORKLOG: "found it: `update_app` is not a fixed step"). Two rules follow:

* **never add a new `app_utils.update_app(steps=...)` to a scripted path** - it
  silently reintroduces the non-determinism; step the physics explicitly instead;
* **but do not drop the pump either.** `update_app` also services the camera and
  sensor callbacks, so `SimulationManager.step` alone starves them (it crashed the
  evaluator with an empty frame). `advance()` in the two entry scripts does
  `SimulationManager.step(steps)` and then `app_utils.update_app(steps=0)`, and the
  evaluator calls `RenderingManager.render()` before reading the camera;
* **the policy loop is still not reproducible** even with all of that: seeding
  `FRUIT_POLICY_SEED` removes the unseeded `torch.randn` in DDIM sampling, and two
  runs still differed (6/6 vs 5/6). The remaining candidate is the rendered frames
  the policy conditions on - since confirmed: with constant frames three runs are
  bit-identical, with real frames they are not, and disabling TAA/DLSS does not help
  (the variance is in RTX rendering itself). So **a policy A/B needs N per arm**, and
  aggregate the *outcome* per episode rather than a continuous quantity like peak
  lift, which varies even when every episode succeeds;
* anything measured **before** that fix was measured on an arbitrary branch, so for
  old data compare distributions rather than single runs. For new data:

1. **Probe the branch first**, then run both arms in the same stretch and probe
   again afterwards; discard the comparison if the branch changed:

   ```bash
   ATTEMPTS=1 FRUIT_MOTION_REPORT=1 scripts/run.sh scripts/20_pick_place.py \
     | grep -oE 'approach\(cartesian\): [0-9.]+ cm, [0-9]+ samples' | head -1
   # 8.5 cm / 328 ticks and 8.7 cm / 334 ticks are two different branches;
   # a run of the other branch is a different scenario, not a repeat.
   ```

2. **Or compare distributions**, at least five runs per arm, quoting median and
   range rather than a pair of numbers (`scripts/108_fruit_size_probe.py --contrast`
   rank-sums one log; run it per arm and compare the summaries).
3. **Prefer per-leg motion metrics and direct mechanism measurements** over success
   counts. The closure interference and the IK push signature are read off the
   grasp or the leg itself and do not depend on which branch a run took.

## 4. Where the reasoning lives

`WORKLOG.md` is append-only, and every claim above has an entry there. Section
headings, quoted verbatim so they can be grepped:

* **the two constraints of section 2:**
  `### The outcome is quantized, and that changes how the A/Bs must be read`
  `### Correction: it is the arm-link readback, not reads in general`
* **what the motion work found, negatives included:**
  `### The descent's "roughness" is one IK command, not the trajectory`
  `### Catching the lurch: a kinematic hand collider inside the arm`
* **the collector/merge bugs:**
  `### The dataset index did not match the dataset`
  `### Both fixes now have a regression test that fails on purpose`
* **which figures are re-checkable and which are history:**
  `### Documentation audit: every motion number, and whether it can be re-checked`
  `### Same audit, policy and data side`

Report-ready summaries are in `项目总结报告.md` (Chinese) and `README.md`; route
trade-offs are in `决策与交付.md`; design-intent vs actual is in
`实现方案总结.md`. When a number changes, update those *and* the log entry that
justifies it.

The long-form plan is `docs/ROADMAP.md` (the current state in one screen, the
backlog grouped into WS-1..WS-7, the phases R0-R6, the resource budget and the
owner-decision register); the periodic ops self-check and its anti-stall
playbook are in `docs/OPS.md` - run `scripts/191_ops_selfcheck.sh` (verdicts
OK / STALLED / ACTION), at the start and end of every work block and every
30-60 min while a simulator phase is active.
