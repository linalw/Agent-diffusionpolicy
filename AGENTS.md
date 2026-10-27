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

**On this tree (P32, 2026-10-22) the acceptance reads 6/10 with the pear and
7/10 with only the pear profile reverted - both below the 75 % dynamic floor -
and the fingerprint reference was re-recorded from the pear-on run**
(`configs/motion_reference.json` md5 406745c5 -> 25ade92b; the pre-pear file is
`logs/p32/motion_reference_pre_pear.json`). **The 7/10 is not this tree's
rating of the pear**: it predates P32 - it is the pre-session acceptance's own
count on the pre-pear tree (`logs/p30a/05_accept_rails_outer_lift040.log`, which
the pear-off run `logs/p32/92` reproduces on its 381/381 `[fruit]` lines byte-identically) - and the pear-on
run is a *different attractor with a different fruit sequence*, so the two
counts differ by one attempt in one sample and no per-class pear cost is
measured; the pear's own grasp/place is 1/1 with the new pear in the pear-on run (0.312 m, 4.43 N) plus 2/2 old-profile pears in the pear-off control, and the
pear-on losses are the peach/kiwi/orange carry class. Do not read 7 -> 6 as a
pear regression. Because the pear changes the per-instance RNG draw count, a
pear-reverted tree is a *different scenario* and reads `fingerprint: DIFFERS`
against the shipped reference - gate it against the archive with
`python3 scripts/105_motion_regression.py <log> --fingerprint
logs/p32/motion_reference_pre_pear.json`. Evidence WORKLOG "P32 phase B",
`logs/p32/92..94`. The final-tree re-run `logs/p32/D1_accept_pear.log` (P32
phase D) reproduces the pear-on record: **6/10 + `fingerprint: matches`**, its
376 `[fruit]` lines identical to `93_accept_raw_pear_on.log` except the two
print-only output-belt clearance message lines (the Gate-B R5/R6 read).

**P32 phase C (2026-10-22) measured the bed on the two-line (still opt-in) and
found the prepared-next lever a zero-actuation null.** The 20-attempt bed
battery (SEED=5) reads **12/20 = 60 %**, 4.19 batch / 4.22 window placed/min,
pooled interval **14.23/15.50/19.00 s**, idle 15 %/15 %, lock-on 2.77/2.92 s,
with its **own** per-scenario reference
`configs/motion_reference_twoline_bed.json` (md5 dcd19758;
`scripts/190_twoline_gate.sh -m 0.5` PASS; any different bed battery needs its
own re-record). **The bed's cost and delivered density are measured, not
implied:** the phase-A same-sim-seconds pair reads **+24 % wall (285 ->
352-356 s)**, the physics of 21 vs 6.6 live bodies plus the pump's
2.71 ms/sim-s; and on the two-line battery the delivered approach band is
**2-8/10 at the 20 pump instants** with `late_dropped=139.6 s` (the
once-per-boundary pump re-bases the backlog instead of delivering below the
catch floor) - quote those, not the lattice's 19.1 fruit/m. The prepared arm
(`FRUIT_PREPARED_NEXT=1`, default off) is
**byte-identical to the control** (`built=0 empty=19`): the build->consume gaps
are **left 7.5-15.1 s / right 2.7-11.1 s**, while a row released at the maximum
along 0.668 m can drift only `(0.668-0.389)/0.12 = 2.3 s` before the
consumption re-check drops it - so even a stocked belt would build rows it
drops. **The two-line's dispatch cost is the pre-pose transit (lock-on
2.77/2.92 s = the 15 % idle), not the selection; the prepared set has no room
on this line at the shipped cadence.** The bed stays default off. Evidence
WORKLOG "P32 phase C", `logs/p32/A0..A3` + `A_phase_c_metrics.txt`.

**P33 phase 1 (2026-10-23) measured the two-line mid-attempt pump: the band
fills, the catchable window does not, and the wall cost stands.**
`FRUIT_FEED_CADENCE=1` now arms on the two-line scheduler: the same
`_feed_tick` is installed as `CoopSession.feed_pump` and `TickRelay.schedule`
calls it on the main thread once per **shared physics tick** (stride 4 = 4 mm
of belt travel, `advance_furniture=False`); default off, and the shipped /
F2 / single-arm paths are byte-unchanged (the two-line control replays A0
**826/826** `[fruit]` lines after its 20 new census rows and the two static
scene prints; the single-arm control replays `87` **436/436**). The A/B (A0's
scenario, 20 attempts, pump vs control): the delivered band at the pump
instants **4.2 -> 8.3 / 10** (2-8 -> 2-11, 14/157 at the cap) and
`late_dropped` **139.6 -> 7.9 s** (the batch-start prime residual; rebased
16 -> 1, holds 0 -> 14) - but quote the **same-instant census, 5.5/6.9 ->
8.4/8.8** (left/right means at the selection instant; 4.2 -> 8.3 puts 20
boundary samples against 157 continuous ones). The catchable per-arm window at
the selection instant **does not rise** (left 1.5 -> 0.9, right 2.4 -> 2.2)
because the aperture is a **stock-depth ceiling**: the bed caps at 10 bodies
over a 0.58 m stocked depth (4.1 rows x 2.4) and only **0.28 m ~= 2 rows ~= 4.8
bodies ~= 1.8 per grade-pure lane** sits above the ~0.40 m catch floor - so
8.3/10 = 83 % of the band's capacity is already delivered, the right's 2.2 is
about the ceiling and the left's 0.9 is the grade-mix shortfall.
**Starvation is worse per slot, not flat**: left **0/10 -> 5/15 = 33.3 %**
steady-state (37.5 % of all slots vs 9.1 %; Fisher two-sided ~0.057 on the
steady-state pair, 5/15 vs 0/10), right 0/10 -> 2/12, and the census names a
**grade drought, not a stock shortage** - at every
starved instant the band is full (7-10/10) with nothing admitted (`admitted=0`;
6 of the 8 starve episodes are `admitted=0`, 1 is `admitted=2 window=0` at the
floor, 1 the empty-belt prime). The interval reads 14.23 -> 13.68 s pooled mean
on a **different branch** (13/20 left 9/right 4 vs 12/20 6/6; right idle
15 -> 22 %, lock-on 2.92 -> 4.14 s, three retry episodes), and the wall is
**+20.9 % (484 -> 585 s) = +4.4 % sim span (171.8 -> 179.4 s) x +15.7 % per
sim-second (2.82 -> 3.26 s)** with a supply burn of **432 releases / 348 bed
placements for 13 arm placements** (444 draws, `reached_end=320`) against the
control's 126/107 for 12. The single-arm pair reproduces the phase-A read -
selector window **4.6 -> 3.9**, live 6.6 -> 20.4, band 2.6 -> 7.9, **+30.1 %
wall at equal sim span (149.7 vs 148.7 s)**; the recorded phase-A pair +24 % -
so the knob stays default off: **the density is a physics lever, not a free
win**, and more stock is not the lever (a lower floor is closed by R3/R11-A; a
higher station is bounded at <= 0.10 m by the R10-A intercept map; the row
composition is a drought/variance lever with the mean ~1.8 eligible/lane
unchanged, needing its own pre-registration, reference and clearance report).
Evidence WORKLOG "P33 phase 1", `logs/p33/`.

## 2. Two constraints that decide how to measure

**The outcome is quantized; do not compare success rates across configurations.**
The *scripted* line is deterministic per configuration **per mode** - nine runs of
the shipped **v1 (stop-and-wait)** configuration are bit-identical in every
statistic and every per-leg metric, and every other arm in this file that has a
same-configuration pair reproduced bit-identically *within its mode* - but it
lands in one of a small number of discrete *attractors*, and which one depends on
instrumentation as much as on physics. **A configuration can also be multi-modal
run-to-run: P39's `F1` is the first measured arm that is** (five
same-configuration runs on the acceptance scenario land in two bit-identical
modes - 348 filtered `[fruit]` lines / 8-of-9 and 382 / 7-of-10, first-attempt
settle 0.88 vs 0.87 s - so a byte-identity test cannot be run *on* it and its
counts are one draw; AGENTS §2's P39 paragraph). Two configurations in different
attractors are different
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
- the two-line rework (V2) owns that. The reference is per-scenario and has been
re-recorded since: **the v9/V1 file was re-recorded from the identical
`logs/v1/30_accept_supply.log`** (the re-verified
`logs/v1/31_accept_supply_verified.log` read PASS against it at the time; 30's
own gate read FAIL only because that reference did not exist yet), **and since
P32 phase B the shipped `configs/motion_reference.json` is the pear-on 6/10
branch's re-record from `logs/p32/93_accept_pear_on.log`** (md5 25ade92b; the
pre-P32 file is archived at `logs/p32/motion_reference_pre_pear.json`, md5
406745c5, and the pre-v9 one at `logs/v1/motion_reference_pre_supply.json`).
So the v9/V1 run matches **no** current file - a re-run of that scenario needs
its own re-record. The policy path is **OOD** on this
supply (the demos carry one candidate per attempt, and the trigger's
`|dx| <= 0.06` gate (pre-W4; now 0.16) refuses the outer half of the new band); do not quote the
71.1 % direct number as the current-scenario rate - one hybrid canary on the
new supply scored **1/10** (8 grip losses + 1 handoff miss,
`logs/v1/80_accept_policy.log`), an OOD warning the V3 phase owns.

**P32 phase D (2026-10-22): the pear OOD closure.** The hybrid canary's
shipped scenario is the pre-v9 *fixed* supply (`scripts/accept_policy.sh`
defaults `FRUIT_SUPPLY_SCATTER=0`), so it isolates the pear from the v9 supply
change: one sample on this tree reads **5/10 = 50 %**
(`logs/p32/D0_accept_policy_pear.log`; 5 grip losses, 0 grasped-not-placed, the
gate FAILs on the rate only) against the **recorded pre-pear spread 5-8/10**
(floor 0.60). One canary is one sample of a non-bit-identical loop, so it is
recorded as a **smoke**, not a rate. Every checkpoint and rollout store on this
tree is **pre-pear** (the pear changes the per-instance RNG draw count and every
authored mesh); the `meshes.py` md5 pins are in the collector manifest and
`rl_env._MANIFEST_SOURCES`, so a post-pear store is identifiable. The
**owner-accepted OOD note is the closure**: a policy rate measured before P32
is not this tree's rate.

**P33 phase 3 (2026-10-23) added the first post-pear store and checkpoint, and
the direct A/B reads no measured improvement (not adopted).** `datasets/p33_pear`
(180 episodes, left 92 / right 88, 32,670 windows, `index_md5 01626590`, every
shard pinning `meshes.py` `41efc522`) and `checkpoints/p33_pear` (md5
`31751eaa`, fine-tuned from `moe_v13s`) exist, so the sentence above now means
*every other* store/checkpoint. On the direct interface (**W8-A protocol,
`FRUIT_POLICY_TRIGGER_ACQ=1`, a sample**) the new checkpoint reads **8/45 vs
`moe_v13s`'s 16/45 overall; the deficit is the same class (cnp 33 vs 26 of
45)** - pooled p = 0.094, A better in 2/3 seeds at run level (exact permutation
~0.20), the class-matched paired carry 3-1 B (the 2 exact-instance pairs 2-0 -
*inferred*: run + episode + species + diameter + arm, no stored instance id),
29/45 unpairable; no new failure reason, cycle flat. **Store-transfer vs
overwrite is unseparated**, and the attribution gaps keep this to *this
checkpoint on this interface*: the store's right station is `y = -0.10` (the
direct env's is `0.00`) with its own station-specific pre-pose - the right is
the arm where B lost, 14/29 -> 7/24; the store is **successes-only** (52
carried-not-placed + 56 no-grasp attempts discarded - no example of the class
the deficit is in); and the 6-epoch/lr 5e-5 schedule cannot be separated from an
overwrite. The hybrid canary smoke (fixed supply) reads **5/10**, matching the
shipped checkpoint's post-pear P32 D0 count - not broken, not discriminating (a
sample, not a rate). Nothing was adopted (`accept_policy.sh` still defaults to
`moe_v12`). **The two-line has no policy eval harness** (`60_eval_policy.py` /
`accept_policy.sh` drive the single-arm presentation), so `p33_pear` is not
evaluated on the two-line interface - out of scope for the direct OOD closure.

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
semantics (`logs/v2/PREREGISTRATION.md` "Routing semantics"); the
**2026-10-13 R5 decision kept it opt-in** (flip: **no**; the 1.25x placed/min
bar unchanged - the park-on 3.63/2.17 = 1.67x is a cross-branch reference
only). Measured on the
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
unchanged (`logs/w2/RESULT.md`). No attempt failed by arm-arm contact; the
**2026-10-13 R5 decision accepted the clearance as a documented per-config
report** (the F2 45 mm / zero-under-30 convention is unmet and not re-imposed
as a gate; no arm-arm contact is possible in this build). A
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
byte-unchanged (its acceptance still reads 9/10 + fingerprint matches);
**R5-decisions (2026-10-13): this stays two-line-only** - the single arm keeps
selecting C -> lane 1 (byte-unchanged), and the two-line accounts C as
`reached_end`/recycled.
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
(`logs/w3/62_accept_single_dense_tree.log`). **The W3-supply hybrid canary is
closed by R5-open (2026-10-13): FAIL 1/10 = 10 % (floor 60 %)** on the W3
hand-off command (`moe_v13s`, `FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_WAVE=1`, the
balanced A:B:C 0.375/0.375/0.25 mix, current tree `tasks.py` `0c51cfa5`) - 8
grip losses + 1 non-hybrid scoring row (**row 7, ep7 pear: it lies outside the
failure-reason parser and counts in the rate only - the FAIL is rate-only, no
new reason**; the gate's parsed reasons are all baseline), 17.5 min for the ten
episodes (~1.7 min/episode; the old ~15-20 min/episode does not reproduce on
the dense sheet, and this run does not diagnose that old slowness). The hybrid
interface is inert by construction, so this is
scenario coverage; the checkpoint's direct dense measurement is 7/45 = 15.6 %
(`logs/r5/RESULTS.md` section 1).

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
**R3 measured L2/L3: neither is adopted** - the adaptive lead is bit-identical
(the shipped 1.5 s floor *is* the measured setup), the tight override binds but
its branch is worse, and the interval is arrival-bound (see the R3 paragraph
below and `logs/w8/R3_RESULTS.md`). Clearance is unchanged by both levers: **1.9 mm min, 4.7 %
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
`configs/motion_reference_twoline.json`; references are per-scenario - the
multi-scenario battery would need its own. **That file was `181c9151`, written
from `logs/w7/10` and matched by `11`, until P39: a pre-pear W7-A record that no
post-P32 tree can reproduce (the first physics difference is `target peach` vs
`target pear` at attempt 0), so P39 archived it to
`logs/p39/motion_reference_twoline_pre_p39.json` and re-recorded the shipped
file from its own same-batch control `logs/p39/p3/twoline_C.log` (**d0326030**,
6/10 at the 0.60 floor, `190` PASS). A W7-A-era two-line log now matches **no**
current file - re-record it from its own control, and never gate a post-P32
two-line log against `181c9151`.** The single-arm
`configs/motion_reference.json`
is byte-untouched by W7-A (`b9e72ca7` is the W7-A-era value; since P32 phase B
the shipped file is **25ade92b**, §1). No-harm: the single-arm patch run is 643/643
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
patch battery takes `-m 0.5` and its own reference, and so does the P32 bed
two-line battery with `configs/motion_reference_twoline_bed.json`). 105's own
floor stays the single-arm 0.75, and `--write-fingerprint` now refuses a
motion-budget-failing run (a rate-only failure still writes). The chain's
compares are assertions now (`scripts/189_w7a_chain.sh`, `W7A_OFFLINE=1`
re-asserts them offline).

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
stall term** (fast setup, 28-181 mm residuals; the R2.1 re-derivation in
`logs/w8/R2_flail_analysis.txt` / `R2_probe_report.txt`). Neither knob is adopted; both
are default off and direct-path-only. Do not read a catch-up timeout as a
fire-time miss: the fire-time dx spans -4.1..+8.3 cm across the class.

**R3 (2026-10-13, branch `w8-speed`, `logs/w8/R3_RESULTS.md`): no WS-3 speed
lever is adopted, and the reason is measured, not assumed - the two-line patch
interval is arrival-bound (revised by the P1/P2 paragraph below: the cadence is
flat across the density ladder, so the wait is not where the time goes).** The L2 plumbing is delivered
(`_dynamic_select_floor` takes a `lead_override_s` that *replaces* the shipped
1.5 s setup, so `FRUIT_BIARM_SELECT_LEAD_S` is no longer inert on the two-line
path (the shared-station worker keeps it max'd under the 1.5 s floor), the
adaptive form (`FRUIT_BIARM_SELECT_LEAD_ADAPT=1`, a per-arm EWMA of the measured
selection -> wait-loop-entry setup, clamped 0.9/1.5 s) is **bit-identical to
the control (821/821 physics lines)** because the shipped floor *is* the
measured setup (**left 1.467 s, right 1.516 s**) and **0/20 selections are
floor-bound** (38-316 mm of slack). The explicit tight probe
(`FRUIT_BIARM_SELECT_LEAD_S=1.0`, floor 0.339 m) **binds** (1/10 per arm) and
moves the branch (first divergence: the left slot-10 peach-vs-lychee) with
**zero new failure reasons** - the v9 under-lead miss does not appear - but the
pooled interval/rate on that branch are worse (8/20, window 2.59 vs 3.63
placed/min, pooled 23.16 vs 16.53 s; the shared placed-False class 11 vs 7).
The L3 hot-arm residency (`FRUIT_BIARM_HOT_ARM=1`: the park decision deferred
to after the attempt-boundary feed, a station-side hold when a target is
imminent and the other arm grips nothing, the next attempt's pre-pose blend
skipped behind a 0.08 rad guard; the hover move stays - it is the calibrated
descent entry) fires **4/18 non-final turns** (starvation 7, clearance 7, 2
survive to the next attempt, 1 of 4 jams at 1.55 rad and recovers through the
park) and does **not** move the interval: the hold's measured-convergence blend
(140+80 ticks) costs the same order as the park return (2.4/2.9 s), the pooled
attempt span is identical (15.08 s), the window rate is 3.41 vs 3.63, the
idle/starvation rise (27 %/27 %, starved slots 51/37 vs 19/22), and the
clearance convention moves per config (min **1.9 -> 4.7 mm**, < 30 mm
**4.7 -> 5.6 %**, the W2/W3 carry-past class; no contact possible). L4
(place/return re-timing) is **not run** - the control's return block is 0.59/
0.64 s per attempt (~4 %), not dominant, and W1/W2's place/carry negatives
stand. The belt-speed screen (0.12/0.15/0.18 m/s) is in R3 section 4. All R3
knobs default off and two-line-scoped; the single-arm acceptance is
byte-unchanged (385/385 identical to `logs/w8/R2_accept.log`), selfcheck PASS.
Pins: `tasks.py` `0c51cfa5`, `rl_env.py` `TASKS_MD5` follow, `176` selftest
extended with the plumbing pins.

**R5-decisions (2026-10-13, branch `r5-open`; `.slim/deepwork/sorting-pipeline-v3.md`
"R5-DECISIONS"): the owner closed the register per the recommendation - no
shipped default changes.** (1) The two-line flip stays **no**
(`FRUIT_BIARM_TWOLINE=1` opt-in; the 1.25x placed/min bar unchanged; the
park-on 3.63/2.17 = 1.67x is a cross-branch reference only). (2) The clearance
stays a **per-config report** (the F2 45 mm / zero-under-30 convention is unmet
and not re-imposed as a gate; no arm-arm contact is possible in this build).
(3) The pure C routing stays **two-line-only** (the single arm keeps C ->
lane 1). (4) `FRUIT_POLICY_TRIGGER_ACQ` is **not shipped** - it stays default
off, a measurement interface (the ACQ=0 mirror is mechanism-only). (5) The
**hybrid pinned canary stays the interface of record**; the direct loop stays
the mechanism-research interface, and the WS-4.2 N=5 protocol governs any
direct claim. The non-blocked R5 items (the W3-supply canary FAIL 1/10, the
patch scenario's own reference) are in `logs/r5/RESULTS.md`.

**R6-B (2026-10-13/14, branch `r6-carry`, `logs/r6/B_RESULTS.md` + WORKLOG
"R6-B"/"R6-B.1"): the WS-4.7 combination screen and the carry-class lever are
both measured and NOT adopted; the direct grip is a drive-saturated pinch.**
On the forced edge band (x = 0.36-0.42, N = 1x15 per config) the combination
(`FRUIT_DIRECT_RESEED=1` + `FRUIT_POLICY_TRIGGER_X_MAX=0.39`) **roughly
halves** the no-lever control's flails (5/15 vs 10/15; the reseed-only P3/P4
controls pool 13/30; C1's 4/15 sits inside the same spread) but does not zero
the class: the three premove caps are exactly the three attempted-anyway
refusals (premove targets x = 0.4086/0.4201/0.4212, err 34-41 mm, while the
fired targets 0.329-0.386 converge in 12-21 mm) - the cap is the WS-4.6
policy-gate bypass's mechanism - and every attempted-anyway refusal flails
(3/3). The two new hover knobs (`FRUIT_DIRECT_HOVER_TOL`/`_STEPS`, default
off, direct-path only) are measured and rejected: the tolerance is inert at
the edge (the hand cannot hold 20 mm either; 4/15) and the step bound trades
the term (6/15: 5 fast-stall + 1 premove-cap; the fast-stall residuals
23-331 mm). The direct carry mechanism is a **drive-saturated pinch**: the
`grasp_lift` command sits a median 11.9 mm inside the payload's measured span
at the leg start (n = 46 contact legs) while the contact force reads 4.1-4.5 N,
and the new default-off `FRUIT_CARRY_RELIEF` cap releases the command to
0.5 mm of allowed interference with the force **unchanged** (Fmin 4.15-4.47 N)
- the squeeze-side family is closed by measurement. The retuned guard
(`HOLD_TICKS=8`, `RESEAT_MAX=0.060`, `DERATE=0.8`; trigger and the 72-tick
budget fixed), N = 5 paired x 15 episodes: pooled **24/75 vs 25/75**, carried
46 -> 44, paired same-fruit **3 B-only / 1 A-only** (sign p = 0.3125), cycle
+4.5 %, no new reasons - **not adopted**; the W8-B 5-1 directional read
(carried 50 -> 42) did not reproduce (46 -> 44, 3-1) and the 100-400 mm band
converts 0/37. No-harm: acceptance **9/10 + motion gate PASS +
`fingerprint: matches`** and 385/385 `[fruit]` identical; the two-line dense
re-record 442/442 identical + `190` PASS. Pins: batch tree `tasks.py`
`1d6e9662` (final `b2c79938`, comment-only - unverifiable now), `rl_env.py`
`5940a7c8`, checkpoint `moe_v13s` `61da390a`.

**R8-A (2026-10-14, branch `r8-dscreen`, `logs/r8/A_RESULTS.md` + WORKLOG
"R8-A"/"R8-A.1"): the pre-registered D screen - the lower grip plane, the
cradle/scoop and the raised station all FAIL; the bounded grip-geometry lever
space is measured closed around the carry class.** The screen (Tier A solo;
the candidates and the conversion criterion fixed in `logs/r7/FRONTIER_R7.md`
section 4 before any asset was touched) ran the patch battery x2 per config
(four double-run pairs, all IDENTICAL) plus the direct probe (patch sheet,
ACQ=1, seed 77, 15 episodes, checkpoint `moe_v13s` `61da390a`). **D2a**
(`FRUIT_GRIP_PLANE_DROP=0.008`, default-off): the escape signature persists
and the lift-leg population moves up into the >400 mm band (11 -> 2 vs
2 -> 10), flails 1 -> 14, battery 5/20 x2 with a new station-close note, and
one descent leaves the speed budget (`|v|max` 0.172 vs 0.161) - and the reach
reading is the **leading hypothesis, not isolated**: the drop moves the
*commanded* catch target (`catch_target` uses `_pad_standoff`,
`tasks.py:6112-6114`) but not the catch-up break test (`desired_tip` uses
`_dynamic_pad_lift`, `tasks.py:6094`), so the -8 mm caps are expected even
with a reachable target (the missing control: the drop + a drop-adjusted
break test + a -2 mm magnitude; the -4 mm sample also fails). **D2b**
(`FRUIT_FINGER_SCOOP=1`): the ledges **bat the payload** (the P3/D
additive-face class the pre-registration warned about; 7 `grasp_lift` rows
with onset in the first 1-2 ticks and `sep@onset` <= 22 mm) - no-contact
2 -> 9, battery 6/20 x2 (the 12 gripper-loss notes are the control's class).
**D3** (`FRUIT_NEST=0.02 FRUIT_NEST_WIDTH=0.05`, the bounded proxy): the
platform's 100 mm x-span is narrower than the supplied band, so its side
faces obstruct the moving supply - battery 1/20 x2, `recirculated` 0 -> 13,
a new "fruit never settled at the pick point" note; the full D3 form (station
+ self-centring feeder + boundary-respecting descent) stays the named
scenario redesign, out of scope for the next phase. **No shipped default
changed**: acceptance **9/10 + motion gate PASS + `fingerprint: matches`**,
385/385 `[fruit]` identical to `logs/r7/A_accept.log`, and the screen's own
control battery replays the W7-A record **861/861 bit-identical**; both new
levers are default-off env knobs. Pins: `tasks.py` `27d0fabd`, `scene.py`
`ab85dca2`, `rl_env.py` `72d55574` (metadata-only `TASKS_MD5` follow),
`trigger.py` `d7ec85fc`, `runtime.py` `ffb76bfd`, checkpoint `moe_v13s`
`61da390a`. **No R8-B is triggered** (all three forms fail); the **fallback
is direction B, the RL/DAgger lane, pre-registered as the next phase**
(ACQ=1 + R7-A pinned; the N=5 paired carried-class endpoint with the cycle
non-inferiority margin and the kill criteria; the no-harm + adoption gates;
D3-proper out of scope - `.slim/deepwork/sorting-pipeline-v3.md` "R9 PLAN",
`logs/r8/A_RESULTS.md` section 7).

**R9 (2026-10-14, branch `r9-rl`, `logs/r9/RESULTS.md` + WORKLOG "R9"): the
bounded RL/DAgger lane (direction B) was executed as the pre-registered
AWR-clipped RWR iteration 2 and closes negative and published - the carry class
does not convert, and the lane degrades the one channel it can touch.** The
lane is not the two behaviour-cloning nulls (W7-C/W8-A are off-policy
`weight_mode=ones` on scripted recollection stores; this one weights the
policy's **own** fresh direct-interface rollouts by the terminal outcome) and
it is the RWR-2 fresh-rollout design: `w = clip(exp(4*(R-Vbar)), 0.05, 4)`,
`Vbar = 0.3103`, fine-tuning `moe_v13s` (`61da390a`) on 56 fresh on-policy
rollouts (`datasets/rl_rollouts/r9_awr`, 18 successes; the pre-registration's
`demos_v12` rollout-store pin is the success-only *scripted* store and would
have been a behaviour-cloning replay). The N=5 interleaved endpoint
(`logs/r9/A_direct_ab/`): **A `moe_v13s` 25/75 = 33 % vs B `rl_awr1` 18/75 =
24 %**; the primary **paired carried-class conversion 5 B-only / 4 A-only,
p = 0.500** (6-0 is the p <= 0.05 edge at N=5); strawberry **1/9 vs 6/10**;
**no new failure reasons**; cycle **+1.5 %** -> primary FAIL, secondary FAIL,
no adoption and no shipped default change. The mechanism: the `[carry]` window
is **branch-invariant** (74/74 `grasp_lift` legs per arm; onset-row median
94/94; `force@onset` 4.93/5.38 N; onset -> loss 29/26 ticks; single-sided
contact) - the scripted primitive owns the pre-onset facet - while the
**handover state degraded** (B **6 reach-cliff flails** vs A's 1, five of them
with the premove `move_to` at its 3.33 s cap; the fidelity readout
`0.087 -> 0.174 rad` away from its own rollouts predicts exactly this), so the
post-training moved the wrong channel. No-harm: acceptance **9/10 + motion gate
PASS + `fingerprint: matches`** with 385/385 `[fruit]` identical; two-line
dense 442/442 identical + `190` PASS; selfcheck PASS; env-only (no `src/`
change, no shipped default). Pins: `tasks.py` `27d0fabd`, `rl_env.py`
`72d55574`, `trigger.py` `d7ec85fc`, `runtime.py` `ffb76bfd`, candidate
`checkpoints/rl_awr1/policy_best.pt` `a1766ecd`, base store `demos_v11`
`922ca995`. The named next items are the **primitive-side pre-onset load
path** (a `tasks.py` item with its own pre-registration), **D3-proper**
(owner-gated), and the **WS-7.1 sim-to-real prep**; another post-training pass
on this interface re-measures the null.

**R10-A (2026-10-15, branch `r10-reach`, `logs/r10/A_RESULTS.md` +
`PREREGISTRATION.md` + WORKLOG "R10-A"): the reach-anywhere dynamic catch
delivers the coverage and the per-attempt interval, but the success and
no-new-class criteria fail and `FRUIT_REACH_ANYWHERE` stays default off.** The
owner correction (binding) removed the station-fixed limitation: the moving
catch must meet fruit at any reachable (x, y). The measured reachable-intercept
map (`scripts/183_reach_intercept.py`, extends `174` to the y dimension; raw
rows `logs/r10/reach_intercept_{left,right}.json`): clean grip bands left
x=0.20 `-0.10..+0.15`, x=0.28 `-0.05..+0.10`, x=0.36 `0.00..+0.10`; right
x=0.20 `-0.10..+0.10`, x=0.28 `-0.10..+0.05`, x=0.36 `-0.10..0.00` (6 mm
tolerance; the cliffs are sharp; the ranges nest, so a fruit between measured
columns takes the next column's band - the first read of +0.20 at the left
x=0.28 cell came off the 6.5 mm row and was corrected in place by the A1
pass). The hover move costs 0.57-0.78 s (68-94
ticks) at every reachable offset (the R2 cap class outside). The design
(`tasks.py` `7e20255c`): `_reach_predict` = the interception point (a bounded
fixed point, `y_f + vy*(t_setup(y) + t_desc + margin)`, clipped into the arm's
x-columned band); `_reach_prepare_aim` caches it at the pre-pose end and
`_dynamic_aim` returns it (the hover move, both wait loops and `_approach`
are unchanged); `_reach_anywhere_select` replaces the station floor with the
band-relative floor and takes the minimum fruit travel to the clipped
intercept (ties to the nearest); the shipped station-fixed rule is the
fallback (it never fired - a strict subset on the measured bands). Scoped to
the scripted OpenArm moving-catch line; the two-line and direct/policy paths
keep their rules (a `FRUIT_BIARM=1` shared-station session runs the same
scripted catch and would inherit the knob - opt-in; only the two-line
scheduler is excluded, its stations are its clearance mechanism); off =
byte-unchanged. Measured (W6-A patch sheet, single
arm, 20 attempts, seed 5; `logs/r10/30_control.log` vs `31_reach.log`):
coverage **73 vs 45 candidate-fruit across the same 20 selection instants
(+62 %)**, 20/20 vs 19/20 instants with a catchable candidate, 20 vs 18
attempts; per-attempt span **15.24 -> 13.98 s (-8 %;** the wait segment 3.06 ->
1.68 s) but the inter-placement interval 27.62 -> 45.14 s and throughput
2.17 -> 1.33 placed/min; success **13/18 = 72 % -> 8/20 = 40 %**; the carry
class **"fruit did not follow the gripper" 0/18 -> 5/20** (3 carry escapes
after contact + 2 timing chases); one descent over
budget (0.165 vs 0.162, the attempt-15 fallback leg; the attempt-19 chase
leg itself is inside budget; the re-seat count is 13 vs 0). The mechanism:
intercepts p50 +0.011 m
(early), the descent-end error p50 +3.4 mm, catch-up p50 14 ticks, and **the
descent wait is 0 ticks in 16/20 treatment attempts vs 59-89 in the control**
- the just-in-time handover removes the shipped line's hover settling (the
leading hypothesis; its named test is the default-off `FRUIT_REACH_HOVER_SETTLE`
A/B) and the
grip phase grows 1.60 -> 2.52 s. Named residuals: the hover settling (its
measured test is `logs/r10/A1_RESULTS.md`), the band cap + the capped-hover
fallback (the old +0.20 cap, the 661 mm chase; the R2 knobs are
direct/trigger-scoped and do not apply to the scripted catch), the setup
model's missing x-term (its own pre-registration), and setup-time variance
breaking the just-in-time feasibility (one fallback chase). No-harm: the control patch run
is **643/643 physics lines identical** to the W6-B single-arm record; the
acceptance **9/10 + motion gate PASS + `fingerprint: matches`** with 365/365
physics lines identical to the R9 acceptance; the two-line dense re-record
**442/442 identical** to the W7-A record + `190` PASS; both double-runs
bit-identical up to a wedge (run 32 through 288 lines, run 33 through 297 -
each then wedged, a known renderer freeze); selfcheck PASS. Pins: `tasks.py`
`7e20255cd32e4d438cfa9ffc5f4dc5e7`, `rl_env.py` `TASKS_MD5` metadata-only
follow; branch `r10-reach` from `7f9eb34`.

**R10-A.1 (2026-10-15, branch `r10-reach`, `logs/r10/A1_RESULTS.md`): the
gate-ordered fixes land, the corrected band removes the band-cap chase, and
the hover-settle A/B reads its pre-registered primary positive with the knob
still default-off.** The fixes: the left x=0.28 band cell corrects to
`-0.05..+0.10` (the +0.15/+0.20 rows are 8.2/6.5 mm, outside the 6 mm
tolerance; also the "at least as narrow" wording and the left `else` inset
cell `[+0.02,+0.08]`), the over-budget descent is the **attempt-15 fallback**
(M4), the coverage recounts to **73 / +62 %** (`43_r10_report.txt`; the
31-vs-32 288-line identity is `40_compare_treatment.txt`), and the mechanism
wording carries the 3-carry-escape + 2-timing-chase split, the 13-vs-0
re-seat and 3.48x/1.22x cone contrasts, the R2-knobs-are-direct-scoped
correction and the `FRUIT_BIARM=1` shared-station scope note. The
corrected-band re-measure (34; the same battery, behaviorally identical to
R10-A through attempt 15 - first divergence attempt 16's handover, aim +0.141
-> +0.08): **9/20, carry 4, re-seats 10, coverage 74 vs 46 (+61 %), span
13.55 s** - the band-cap chase is gone, the attempt-15 fallback leg the only
motion over-budget. The **hover-settle A/B** (35;
`FRUIT_REACH_HOVER_SETTLE=60`, priced into `t_setup` as
`vy*S/(1-vy/v_hover)`): **carry 4 -> 2 and re-seats 10 -> 7 (both
pre-registered endpoints fall), success 13/20 >= 9-1, span 13.55 s (identical;
the park priced), window 2.18 vs 1.43 placed/min (the control's 2.17), the
park actuated in 19/20 (60-78 ticks; A read 0 in 14/20)**, the motion gate
failing on the rate only (all descents inside; worst cone 1.84x vs A's
reported 6.02x), with the **branch caveat** (the settle moves `t_c`, so the
runs diverge from attempt 0 - quote the park's actuation and the within-B
non-parked escape (attempt 18), not a rate delta) and the residual the two
W8-B loaded-slide escapes (both re-seated 3x; one with the park). The knob
stays default-off (a pass is not adoption) - **and by the R11-A adoption
attempt below it stays default-off for the shipped tree too**: the flip is
exactly this arm B (bit-for-bit), but the shipped acceptance collapses
9/10 -> 4/10 under it, so the enable path is the explicit
`FRUIT_REACH_ANYWHERE=1 FRUIT_REACH_HOVER_SETTLE=60`; the escalation stays
R10-C. The
default-off capped-hover fallback (`FRUIT_REACH_HOVER_FALLBACK` +
`FRUIT_REACH_DELIVER_MARGIN`) is a measured no-op on the corrected band
(**run 36 byte-identical to 34, 651/651 physics lines, 0 fires** - no reach
hover caps exist there); the setup model's x-term is a named design item
with its own pre-registration. No-harm: the knob-off acceptance 9/10 + motion
gate PASS + `fingerprint: matches`, byte-identical to the R10-A acceptance
(385/385), and `scripts/selfcheck.sh` PASS with the extended `198` leg.

**R11-A (2026-10-15, branch `r11-adopt`, `logs/r11/A_RESULTS.md` + WORKLOG
"R11-A"): the adoption attempt - the flipped default is exactly the measured
R10-A.1 arm B (bit-for-bit on the patch battery), but the shipped scattered
acceptance collapses 9/10 -> 4/10 (deterministic) and the R11-A gate's
acceptance-floor item FAILS; the shipped default stays the pre-adoption
`0`/`0` and the re-baseline + the mechanism are published.** The candidate =
`FRUIT_REACH_ANYWHERE=1 FRUIT_REACH_HOVER_SETTLE=60`: the patch battery
replays `logs/r10/35_reach_settle60.log` **685/685 physics lines identical**
(13/20 = 65 %, 13.5 s/attempt; the `199` section identical; the no-diag rerun
606/606 identical modulo the diag rows - `FRUIT_REACH_DIAG` itself is
run-neutral). The acceptance (`accept.sh`'s scenario): **4/10, 14.6 s/attempt,
1.17 placed/min, 10 re-seats, cone 6.74x** against the pre-adoption **9/10,
15.2 s/attempt, 2.90 placed/min, 0 re-seats** - the candidate double is
bit-identical (343/343) and the knob-off control replays the pre-adoption
record **byte-identically** (385/385; the patch control 643/643), so the
regression is the default, not the tree. **Mechanism:** the reach rule's
band-relative floor (~0.20 m) removes the shipped 0.40 m window - exactly the
v9 pre-fix collapse condition on the *stocked* scattered belt ("a 0.10-0.18 m
fruit ... 1/10", `logs/v1/pre_fix/`), which the shipped floor was calibrated
for; the patch sheet's clip-to-`up` slack masked it. Failures: two catch-up
chases (236.2 mm after the 2.02 s pre-pose recovery; 167.7 mm nominal) + four
carry/place escapes; the W8-B escape signature (re-seats 0 -> 10). No-harm
byte-for-byte on every untouched path: two-line dense **442/442** + `190`
PASS; two-line patch **821/821** + `190 -m 0.5`; the direct/policy selection
pinned by the new `select_target(reach_anywhere=False)` (`rl_env.py`; closes a
latent R10-A leak - with the knob on, the direct env's episode-reset
selection would have taken the reach branch); `configs/*` untouched; selfcheck
PASS (`198`/`199`). Also fixed here: main's `rl_env.py` `TASKS_MD5` did not
match the R10-A.1 `tasks.py` (the A1 follow was missed, so the RL env refused
to start) - the pin now follows the final tree. Named next: a **floored reach
variant** (`max(band-relative, shipped lead)`) with its own pre-registration,
or the **owner exception** on the documented numbers; the flip's re-entry is
one line + the acceptance + the reference re-record.

**R11-A.1 (2026-10-15, branch `r11-adopt`, `logs/r11/A1_RESULTS.md` + WORKLOG
"R11-A.1"): the floored reach variant - the floor closes the candidate-set gap
(gain +0 on both scenarios, no chosen fruit inside it) and the shipped
acceptance still collapses 9/10 -> 4/9 = 44 %, so the floor was necessary but
not sufficient; the defaults stay `0`/`0`.** The variant (one term): the reach
selector's candidate floor becomes `max(band-relative, the shipped lead)`
(`_dynamic_select_floor()`; new `FRUIT_REACH_SHIPPED_FLOOR`, default `1` in
the reach branch, `=0` restores the R10-A.1 rule - so **the R10-A.1/R11-A
enable-path pair above now resolves to the floored selector; the measured arm
B replays as that pair plus `FRUIT_REACH_SHIPPED_FLOOR=0`**); read only under
`_reach_anywhere_active()`, so the knob-off tree is byte-unchanged (proven by
the controls). The battery (Tier A solo, `logs/r11/A1_00_battery_driver.log`):
acceptance **4/9 = 44 %** (deterministic 329/329; the pre-adoption record
9/10 = 90 %; the control replays it **byte-identically**, 385/385, the patch
control 643/643) against the same-battery control 9/10, with **all five
lane-0/left attempts lost and the right 4/4**; the motion gate is **rate-only**
(all 9 descents inside the budgets; worst cone 1.22x reported). Patch battery
**10/17 = 59 %** vs the control 13/18 and arm B 13/20. **The floor invariant:**
`eligible == shipped` (12/12 and 40/40; `feasible` 16/58) and **0 chosen
inside the floor** (arm B 13/20) - the R11-A coverage mechanism (the below-
0.40 m window) is fully closed, and with it the reach rule's whole candidate
gain on both scenarios; what remains different from the shipped rule is *which*
floored fruit is chosen (min-travel vs farthest-upstream) and *where* the
catch aims (intercepts +0.03..+0.13 on the acceptance vs the station).
**Mechanism:** the interception is clean (`aims=9 feasible=9 fallback=0`; the
descent ends with the fruit +10.9..+14.4 mm short of the aim and the catch-up
closes it at the 6 mm tolerance in 11-53 ticks; **zero re-seats, zero chases -
the R11-A chase/re-seat signature does not reproduce**; the `SETTLE=0` probe
reads the same 4/9). The failures are the **post-catch hold**: every left
failure carries the force-servo signature `F_min = 0.00 N` / `gap == sep` /
`closed = 15.00 mm` / 38 trips (the servo chased the payload down its full
range onto air; the right's successes: `F_min` 3.4-3.8 N, 0 trips), the left's
lift carries 0.42-1.95 m/s of relative motion (the right's <= 0.18) and the
place0 legs slip 859-1582 mm - the **W8-B loaded-slide / carried-not-placed
class** the control carries once (its attempt-0 kiwi). The patch cross-check:
**lane 0 is 1/6 in the floored run and 1/6 in the control (arm B 1/5)** - the
patch's left is at its grip limit in every configuration - so the floored
patch delta sits on lane 1 (12/12 -> 9/11; arm B 12/15); the loss tracks the
scenario's fragile lane. **The sub-lever (choice vs aim) is not separated by
this battery**; the named discriminators are a choice-pinned pair (the shipped
farthest-upstream with the reach aim on, and vice versa) and
`FRUIT_CARRY_DIAG=1` (`clean_slip`) on the same battery. **Verdict:** the
pre-registered gate item FAILS; **no shipped default change** (`0`/`0`; the
floored selector is the reach branch's default, `=0` the arm-B reproduction);
the **owner exception** on the documented numbers remains the only shipping
path, and R11-B (the pre-onset load path) is unaffected. No-harm: the controls
byte-identical, `configs/*` untouched, `selfcheck.sh` PASS (extended `198`),
`199 --self-test` PASS, `96` PASS; a post-battery **print-only** fix corrected
the `199` met-error annotation (the sign is the wait loop's own: positive =
the fruit still upstream; `199` md5 `00fd74df` -> `26fb9be6`; committed
evidence files are not rewritten). Pins: `tasks.py`
`c2c7a626c4443592e7533eb92eea5bfe`, `rl_env.py` `48944d9c...` (unchanged),
`198` `fb4a2f7a...`, `199` `26fb9be6...` (battery-time `00fd74df...`);
`fruits.py` `a0ea1f54` unchanged.

**R11-B (2026-10-15, branch `r11-loadpath`, local, not pushed; the R11-C
close-out is `docs/CLOSEOUT.md`): the pre-onset load path is not the
discriminator - the payload is held to 0.5 mm through the window and the
escape is a mid-lift one-sided loaded slide; the screen's C1 (the close's
face speed capped at 0.04 m/s) converts on the direct interface (carried
48 -> 27, class-stratified exact p = 0.0026, `logs/p18b/B_RESULTS.md` section 4)
while the stage-P scripted battery is a bounded-attempt negative and the
scripted two-line does not transfer, so the phase closes not adopted:
scripted negative, direct positive, the class-matched direct re-run open
(`logs/p18b/B_RESULTS.md` section 5).** The three default-off,
dynamic-capture-scoped knobs (`FRUIT_CLOSE_LOAD_RATE`,
`FRUIT_CLOSE_CONTACT_LEAD`, `FRUIT_PLUCK_DWELL`) are byte-inert at default;
the M screen (direct, N=1x15) promoted C1 on the strongest readout of the
three - freeze row 18.0 -> 55.5, freeze-zone face speed 188.7 -> 39.9 mm/s,
cnp -6/-6 - while C2's lead does not move the contact-window geometry (the
close is entered with the fruit already arrested; lead 0.26 *punts* it
downstream up to 582 mm/s: the longitudinal variable is a velocity/shear one)
and M2 fails (a). The stage-P read is **12/20 = 60 % vs the control's
13/18 = 72 %**: the cnp item clears only exactly at the bar (3 = 5-2) and the
never-grasped class 0 -> 5 (late-freeze 40 mm/s closes; the fruit rides the
faces >1 s and the marginal grip slips at the pluck) fails the same-battery
item (iii) - the honest stage-P read is not positive. The stage-N direct
battery stopped incomplete on the day (A run 1 = 6/15; B run 1 partial;
`logs/r11/B_N/STOPPED.md`) and was **completed as the P18b N=5 batch; its
Oracle Gate-3 re-analysis is the verdict above** - A ok 22 / nc 5 / carried
**48** against B ok 39 / nc 9 / carried **27**, class-stratified exact
**p = 0.0026** (MH OR 1.79, CMH chi2 8.68) with **all 5 B runs beating all 5 A
runs**, and the pooled 22/75-vs-39/74 sign test **p = 0.500** reduced to the
*episode-pairing* endpoint (58/74 unpairable - a protocol weakness, not the
lever's read; `logs/p20/ORACLE_GATE3.md`). So C1 is **not "unconfirmed" on the
direct interface**: it moves the carried class there, and it is **negative on
all three scripted measurements** (this stage-P and the two-line **28/60 vs
45/60**, nc 8 -> 25 in `logs/p21/RESULTS.md` - the slow close is incompatible
with the never-stop dynamic catch). The knob stays **default off and not
shipped**; the one open item is the class-matched direct re-run.
No-harm: acceptance **9/10 + motion gate
PASS + `fingerprint: matches`**, 385/385 `[fruit]` identical to the pre-phase
control; the scripted control 681/681 == `A1_25_patch_control.log`; the
two-line dense re-record **442/442 byte-identical to the W7-A record + `190`
PASS** (the branch probe reads 6.0 cm / 95 samples as before);
`selfcheck.sh` PASS. Pins: `tasks.py`
`3b15f3ff59e8923fea2b245adc7824b4`, `rl_env.py`
`874349039e16ef75e68f75eeffa8b850` (the `TASKS_MD5` follow also repairs the
stale pin inherited from `fd2e39e`: main's `rl_env.py` pin `b7d6f849...` did
not match its own `tasks.py` `c2c7a626...`, so the direct env refused to
start), checkpoint `moe_v13s` `61da390a85fa209496b54477a8255d23`.

**P1/P2/P1c/P3 (2026-10-15/16, owner directive "为什么会要等那么长时间的果？你增加流水
线上果蔬数量不行吗", branch `p-supply`): the supply-density knob exists and is
sound, its adoption recommendation is WITHDRAWN, and the place leg is closed by
geometry.** `FRUIT_SUPPLY_PATCH_DENSITY` (D, default 1.0, `fruits.py`) divides
the patch sheet's along-slice gaps by D (floor 0.085 m) and raises the abreast
probability toward 1; P2 extended it to the wave schedule's two gap bands. Raw
ladder on the two-line patch battery (ATTEMPTS=20, SEED=5): success
60/55/80/75/**90**/75/25 % and placed/min 3.64/3.36/4.48/4.48/**5.27**/4.20/1.53
for D = 1.00/1.25/1.40/1.50/1.60/1.75/2.00.

**Do not quote the ladder as a throughput result.** Two independent checks say why
(`logs/p3/ORACLE_REVIEW.md`, re-derived by `scripts/200_composition_audit.py` ->
`logs/p2d/82_standardised.txt`): (1) `186`'s two headline endpoints are **one
statistic** - the placement-window throughput *is* `60 / pooled_interval_mean` -
and the batch throughput is `success / s_per_attempt`, so with a fixed attempt
count and a flat cadence every headline is a monotone transform of the success
count; (2) **the density changes which fruit each arm is presented** (it changes
the release geometry) and the placement rate is class-dominated (0.44-1.00 per
arm/species), so **class-standardised the ladder is flat** (13.89/13.92/14.05/
14.68/14.43/15.12 adjusted vs 12/15/11/16/18/15 observed). The decisive test is
pre-registered at `logs/p1c/PREREGISTRATION.md`: a **single-grade supply** holds
the mix fixed by construction, so D is the only variable.

**What does hold, and it revises the R3 "arrival-bound" language in this file:**
the per-attempt **cadence is flat (~15 s)** and the **lock-on does not fall**
across the whole ladder, so the density does not shorten the wait or the cycle -
and the **binding term is the per-attempt span**, not the supply. Two other
measured facts: **D=2.0's collapse is a real density effect** (crowding breaks the
acquisition; -7.3 slots class-adjusted), and the single arm is **not** a
like-for-like transfer (at D=1.5 it starved on half its slots: 10 "no eligible
fruit" vs the control's 0, 10 picks in 19 slots vs 20 in 20 - the two-line's
worker parks and waits, the single arm's selector polls and gives up).

**P1c (2026-10-16) CLOSES the density as a positive lever: on a composition-free
single-species pool it is strongly NEGATIVE on the single-arm line** (65 % -> 17-30 % per
attempt, **0/20 -> 14/20 (and 30/40) empty slots**, 2.54 -> 0.63 placed/min; the D=1.60 double is
physics-identical). Mechanism: the denser sheet delivers the pool as **one burst** that drains
below the selection floor while the single arm's 15.4 s cycle is slower - at attempt 3 the
most-upstream live fruit is at y = +0.375 against a ~+0.40 m floor. **The two-line hides it**
(its worker parks and waits, two arms drain the pool), which is why the ladder looked positive
there. So: the knob stays default-off and is a **measurement instrument**, not a candidate
default; the surviving density effects are both negative (D=2.0's crowding collapse, and the
D>=1.5 single-arm starvation). `FRUIT_SUPPLY_SPECIES` (default off) was added for this test -
`_mix_env` rejects a zero weight, so a one-species pool was otherwise inexpressible.

**P3: the place leg is closed by geometry.** `FRUIT_PLACE_INNER_SHIFT` (default
off) shortens the place carry as designed (45.1 -> 36.1 cm, 297 -> 237 ticks,
~1.0 s) and the success rate **collapses 90 % -> 30 %**, because the payload
releases at |y| 0.21-0.41 while the belt's inner edge is at 0.375. The control's
release already sits ~35 mm inside the belt, so the maximum safe shift is ~30 mm
= **~0.2 s, 1.3 % of the span**, against a 4 % bar. The next span target is the
**descent's documented boundary shortfall** (40-90 mm short on every leg), not
the place. No default is flipped in either phase; if P1c confirms, adoption needs
both `motion_reference_patch.json` **and** `motion_reference_twoline.json`
re-recorded plus a `collection.patch_density` manifest field.

**P35 (2026-10-24, `logs/p35/`, default off, not adopted): the park is a measured
interface lever, its mediator is not identified, and the check is a separate object
from the outcome.** `FRUIT_ARM_PARK=<name>` (`rl_env.py`, direct presentation only;
`configs/arm_parks.json`, only the left arm has a park) teleports the **inactive**
arm to a named pose at reset instead of the shipped `ready`; unset it is one dict
lookup per arm and byte-inert. Phase 1 measured the geometric lever offline: the
inactive left arm at `ready` covers **98 %** of a 58 mm fruit's disc at along
+0.35 / 57 % at +0.40 (mean 0.382 of the stream), and `back` takes the marginal
cover to **0.002** with the hand 0.287 m above the belt (the right arm covers 0.00
and its park does not hold, so the lever is left-only and its population is the
**right-arm** episodes - the direct env sets the arm from the grade). The record
A/B (`logs/p35/C_ab/`, the Gate-1 P0-revised check, N = 5 runs x 15 episodes per
arm, seeds 77/101/202/303/404, interleaved, `moe_v13s` `61da390a` on both arms,
P33/W8-A scenario verbatim): **right 23/51 (45 %) -> 47/50 (94 %)** with the
**carried-not-placed class 25 -> 0** (composite 28 -> 3, no-grasp 3 -> 3), the
**left** no-op guard flat 1/24 -> 2/25, pooled **24/75 -> 49/75**, **B > A in 5/5
runs, all strict (one-sided p = 0.031)**. **The design-valid leg is the run level
plus the standardised counts** (right 94.9 % class- / 94.1 % size-standardised
against 52.3 %/45.2 %; the per-class deltas carry different denominators); the
**exact-instance pairing is conditioned on a post-treatment variable** - the streams
diverge with the outcomes, so only 22 of 75 slots stay pairable - and it reads
8 B-only / 0 A-only (p = 0.0039), carried 7-0; `C_pairs.txt` is the looser
same-species set (24 pairs, 8/1, the extra A-only being a different fruit). **The
check** (Gate-1 P0): M1 the pose held vs the pose the reset **achieved** (50/50;
the achieved-vs-commanded residual is reported, 0.088 rad - the shipped `ready` sits
0.037 from its own command, so a command bar cannot be the gate), M2a the arm term
at the +0.30..+0.40 band's **worst** call (50/50; control 0/51), and the census:
the band's **fully-hidden target calls 856/1257 = 68.1 % -> 0/1236 = 0 %**, calls
with any inactive-arm pixel inside the fruit's **projected-disc bbox** **100 % ->
0 %**. **The gate of record is M1 + M2a**; M2b (the episode-relative `rel >= 0.85`)
is a **recorded report at 36/50 = 72 %**, not the gate, and its misses are
`arm_px = 0` on 22-47 px masks (the running `px*d^2` normalisation + raster drift,
the belt as the largest instance). **What it does not show:** the park is a static
scene change on the image (3497 -> 4155 px of silhouette) *and* the **7
inactive-arm joints of the 25-D proprio**, and this A/B does not separate them;
the control **succeeds with the fruit invisible** (9 of its 23 right successes read
`px=0` at every band call; successes' median fully-hidden share 0.84 vs the
failures' 0.60), which argues against a simple perception bottleneck. So: **the
park is a measured interface lever; the check shows it removes the fruit's band
occlusion; the mediator (image vs the 7 proprio channels) is not identified.** It
ships **default off** (no shipped default changed) - the adoption gate is a
**recollection's own A/B**, which fixes both channels at once and can erase a
checkpoint-specific input-shift win, so it should not be the first spend on the
mechanism; the named discriminator is a small-N 2x2 **proprio-spoof x
image-spoof** (the park's joints in the obs with the arm unmoved, and the arm moved
with the `ready` proprio). `PREREG.md` section 5's literal arm-pose block
(> 0.02 rad) is **failed** by the 0.088 command residual (a `teleport_joints`
settle property); not adopted either way. No-harm: selfcheck PASS; acceptance with
both knobs unset **6/10 + `fingerprint: matches`** (the exit=1 is the expected
rate-only result) with **376/376 `[fruit]` lines identical** to
`logs/p34/73_accept_no_harm.log`; tree md5s identical before/after. Pins:
`rl_env.py` `fd18bb1b` (+424/-1), `arm_parks.json` `42ab4fb7`,
`scripts/217_arm_park_map.py` `d73618f9`, `logs/p35/park_ab_report.py`
`a796db0b`, `logs/p35/C_attribution.py` `b3311523` (batch-time
`cce04b95`/`c15c03ca`, Gate-2 docs/`frac` fixed).

**P36 (2026-10-24, `logs/p36/`, default off, not adopted): the park's mediator,
tested 2x2 - the image channel carries the win, the 7 proprio channels do not,
the probes are inconsistent input pairs and do not ship.** `FRUIT_ARM_PARK` moves
the arm (the image); the new default-off **`FRUIT_PROPRIO_SPOOF=<pose>`**
(`rl_env.py`, direct presentation only, vectors from `configs/proprio_spoof.json`
- the P35 measured `q_settled` poses, *not* the commanded ones) writes only the
**inactive** arm's 7 joints into the observation, leaving the active arm, the
image, the fingers and the tactile channels live, so the park's two channels can
be crossed. The batch (**4 cells x 3 runs x 15 = 180 episodes**, seeds
77/101/202, policy seed 11, one claim `RUN_LIMIT=25200`, wall 5146 s, randomised
cell rotation) passes its manipulation check from its own rows - the image
follows the **arm**, not the spoof: 670/670 and 724/724 band calls with
inactive-arm pixels in the ready cells vs 0/741 and 0/680 in the parked ones,
`rest_same=1` 180/180, the written vector within 0.0020/0.0040 rad of the
physical counterpart's live pose. Right-arm **carried-not-placed** (the primary):
cell 1 control **18/27 = 0.667**, cell 2 park/park **0/30**, **cell 3
park-image/ready-proprio 0/28**, cell 4 ready-image/park-proprio **17/30 =
0.567**; **image 0/58 vs 35/57, p = 8.8e-15**, **proprio 17/60 vs 18/55, p =
0.687**, interaction +0.100 (permutation p = 0.581 - the pre-registered
**descriptor only**: "adds nothing measurable under the ceiling", since the image
cell is already at 0/28). **The reading is the image channel** - *which* image
statistic carries it is **not separated**, with the fruit's **sightline** (the
P35 68.1 % -> 0 % occlusion census) the leading **unseparated** candidate (the
probe moves the parked silhouette as well as the fruit's pixels). **The probes do
not ship**: they are input pairs the checkpoint never saw, so the shipping path
stays a **recollection's own A/B** - which this read is *consistent with* - run at
the **WS-4.2 N = 5** convention (this 2x2 is a probe at N = 3), with the park
collected in. The cell-4 null is the **weaker** read (the parked proprio's j2 =
-0.978 rad is outside both reference stores' observed ranges - the only channel
that is; the 4-5 sigma summary is a mixed-population statistic) and it also sits
inside the batch's own left-arm no-op noise (0.050 vs 0.119), so the honest
statement is "no proprio contribution measurable at this n". A recording rollout
under the spoof is **refused** (a spoofed store would carry a pose the arm never
held); the park is not. No-harm: selfcheck PASS; acceptance **6/10 +
`fingerprint: matches`** with **376/376 `[fruit]` lines identical** to the P35
record. Pins: `rl_env.py` `aa54b022`, `configs/proprio_spoof.json` `374b88a7`,
`scripts/218_proprio_spoof_check.py` `95a3fe28`, `scripts/219_p36_cells.sh`
`2fe202d7` (batch `e19fa36d`), `scripts/220_p36_report.py` `42dd8339` (batch
`72f22dd5`).

**P37 (2026-10-25, `logs/p37/`, default off, not adopted): the park-collected
recollection preserves the park's win and the pre-registered S3 gate fails on a
scenario tail; the checkpoint adds no gain over the shipped `moe_v13s` + park.**
The question P36 left: a fine-tune on rollouts **collected under the park** (both
channels fixed) - the shipping path, since the spoof probes do not ship. The
store is the **direct-rollout** store (`110_rl_rollout --record` under
`FRUIT_ARM_PARK=back`; the collector parks through `tasks.go_ready` and has no
park): **90 episodes / 3,698 windows**, right 54/58 ok / **0 carried**, left 3/32
ok (`datasets/rl_rollouts/p37_park`, gitignored); fine-tune `moe_v13s`
`61da390a` -> `checkpoints/p37_park` `3fa45c96` (`ones`, 6 epochs, lr 5e-5, base
`demos_v11`, **28.3 % rollout window share** - the declared confound). The
adoption A/B (**N = 5 x 15 per arm**, seeds 77/101/202/303/404, one claim, **both
arms parked**, the W6-A patch sheet + the ACQ interface, A then B): the H2
manipulation gate PASSES 100 % per arm (44/44, 49/49); right-arm placed **A 43/44
= 0.977 vs B 47/49 = 0.959** (delta **-0.018** against the -0.10 margin),
**carried 0 vs 0**, S2 consistent, S4 -0.8 % (PASS), and **S3 FAIL** on one novel
`timeout: no grasp within 1500 ticks` (1/92 right). **The S3 fail is a scenario
tail, not a candidate result**: the trigger's lateral gate is a pure function of
the fruit's x (`dx = x - 0.333`, gate 0.16 -> only `x >= 0.173 m` is admitted)
and the delivered supply's x is **0.148-0.364 m**
(`logs/v1/12b_supply_after_free.log` line 409), so ~2.5 cm of the stream is
systematically unfirable; the event (x = **+0.159**, **below the band's 0.20 m
floor**) runs at ~1 %/episode, so at n ~ 45 per arm which arm sees it is ~a coin
flip. The formal rule fires (not an adoption candidate) but **the preservation
read stands and the event carries essentially no evidence about the checkpoint**;
**do not widen the gate** (the reach residual at x = 0.16 is **8.3 mm** -
marginal, not a flail - and a wider gate trades a no-fire for a grip-quality
failure). The **adoption recommendation is the no-gain**: the base sits at ~0.98
of its ceiling and the shipped `moe_v13s` already delivers the park's P35 **94 %**,
so a park-trained checkpoint adds nothing and is **not needed to ship the park**.
The pooled rate is an **arm-mix artifact** (right -1.8 / left +0.6 points;
standardised ~ -1; the right share moves 58.7 -> 65.3 %) - the right-arm primary
is the read - and the interval has **~no power** (-0.0885 at 47/50 equality,
-0.1045 one margin-step in), so the pre-registered **point rule** is the only
gate that passes (realized n 44/49 = the power table's n = 40 row, 98.2 %). The
fidelity direction is a **diagnostic, not a measurement**. No-harm: selfcheck
PASS; acceptance **6/10 + `fingerprint: matches`** with **376/376 `[fruit]` lines
identical** to the P36 record; no `src/`/`configs/` change, no shipped default.
The checkpoint and the store are **gitignored** (provenance in `logs/p37/`); the
next spend is the **supply/transport drift tail** and the **harness's
no-re-selection on a lateral refusal** (the 1500-tick timeout class), each with
its own pre-registration. Pins: `logs/p37/p37_report.py` `50dae91d` (batch
`e17aef37`), `scripts/221_p37_collect.sh` `115f2e25`,
`scripts/222_p37_finetune.sh` `c0509407`, `scripts/223_p37_ab.sh` `49febf5a`.

**P38 phase 1 (2026-10-25, `logs/p38/`, default off, not adopted): the
delivered-x drift is the *release*, not the transport - the transport
contributes exactly 0.000 mm - and the S3 class is too rare (2/3103 = 0.06 %)
for any A/B at this project's N, so phase 2 pre-registers a forced-band
mechanism endpoint.** No `src/` or `configs/` change (pins `rl_env.py`
`aa54b022`, `trigger.py` `d7ec85fc`, `tasks.py` `cdde6bd2`, HEAD `dd53d15`;
`logs/p38/MD5.txt`). The measurement (`P1_RESULTS.md`, `drift_census.py` ->
`drift_census.txt`, `probe_drift.py` + five claimed runs):

* **The delivered x per scenario** (deduped: a bit-identical replay reproduces
  an attempt's `(x, along)` to 4 dp, and the scripted buckets carry 3-6x more
  raw rows than unique attempts): scripted single scatter n=209 p50 0.272, min
  0.177, **0 below 0.173**, 3.8 % below the spawn floor 0.20; single patch
  n=272 p50 0.270, **min 0.158**, 0.37 % below 0.173, 6.6 % below 0.20;
  two-line wave n=682 p50 0.276, 0.29 % below 0.173; two-line patch n=2016 p50
  0.280, **min 0.143**, 0.45 % below 0.173; two-line bed n=38 (15.8 % below
  0.20, the 0.36 column drifting up). The **direct** population (the P35/P36/P37
  `[park] call ... x=` band census, n=653 episodes) reads p1 0.187, p50 0.264,
  p90 0.341, **min 0.159**, max 0.376, **2/653 = 0.31 % below 0.173**, 0.77 %
  below 0.180, 3.5 % below 0.20 (kiwi 8, orange 7, strawberry 5, lychee 2,
  apple 1), 1.7 % above 0.36. The on-belt design reading is `v1/12b`'s min
  0.148 / p50 0.279 / max 0.364 and the **pre-v9 fixed line** is the control:
  0.308-0.365 with no low tail. Within an episode the band census's `along`
  spans a median 0.096 m while x does not move.
* **The mechanism, measured**: over **475 full transits in five
  configurations** the transport's lateral contribution is **exactly 0.000 mm**
  (`probe_drift.py`; a sphere rolling on a plane whose surface velocity is
  along -y has no lateral force term, and the cleats are off by default) - the
  belt/cleat/friction/rolling drift hypothesis is **falsified**. The only
  stage that moves x is the release/settle, and its displacement is a **fixed
  per-instance offset** (same to 0.2 mm across the schedule and the arm pose at
  a fixed seed; -20.20/+15.04 for the seed-77 kiwis, -35.89 for a seed-5
  strawberry, up to +69.2 for a seed-77 kiwi drawn at 0.343 and delivered at
  0.413). So **delivered x = spawn x + offset(instance)**, the low tail is the
  negative offsets meeting a draw near the 0.20 floor, and the §1 class order
  (kiwi, orange) is the offset order. The corollary names the real supply
  lever: the offset is measurable once and **compensable at `respawn`**. The
  **open residual** is 5-20 mm: the attempt loop's deepest low-side x
  (0.143-0.159 = -41..-57 mm) exceeds the probe's worst instance offset
  (-35.9 mm), with the active arm's fly-by sweep, a re-release under a moving
  arm and a pair depenetration as the named candidates.
* **The S3 census** (549 direct-loop logs, grouped by each log's own
  `[rl] trigger=... lateral=...` + the guard flag): the **shipped interface
  (gate 0.16, guard off) is 3103 episodes with 2 never-fired = 0.06 %** -
  `logs/p37/B_ab/B_1.log` ep 6 (kiwi, right, **x=+0.159**) and
  `logs/w7/C_eval/direct_ab/B_3.log` ep 12 (peach, left, x unrecorded) - and a
  third low-x episode ended as `fruit fell off the line`
  (`logs/p35/B_ab/A_4.log` ep 14, orange, right, **x=+0.162**, tick 1298). The
  opt-in reach-cliff guard's 2/120 never-fired are **high-x** refusals
  (x=0.398/0.412) and are not this class; the pre-W4 gate 0.06 is 180/3195 =
  5.6 % (the documented W4 class) and the pre-trigger logs are 414/864 =
  47.9 %. **The admission floor is per arm**: right station x 0.3330 (n=431)
  -> **x >= 0.1730**, left 0.3400 (n=219) -> **x >= 0.1800** (the P37 text's
  0.173 is the right arm's number). At 0.06 %/episode a 75-episode arm expects
  0.05 events, so **no A/B at this N can measure the class** - the P37 batch's
  1/150 is batch clustering, not a rate.
* **The harness path**: the candidate is chosen **once per episode**
  (`rl_env.py:1538-1560`) and `should_fire`'s `|dx| > lateral` refusal returns
  `False` **with no marker**, so nothing re-selects and the attempt burns the
  whole 1500-tick *policy* horizon (`rl_env.py:2668-2674`; the primitive's own
  steps are after the cap) with the note `timeout: no grasp within 1500 ticks`.
  The phase-2 options are (a) a bounded re-selection in the same grade lane at
  the *provable* refusal, (b) an explicit `no firable fruit` terminal class,
  (c) both; and because `113_rl_report.py`'s `reasons()` digit-normalises every
  note, **any new note is a new failure reason** - so the attribution note is a
  run-neutral diagnostic ON in every arm and only the terminal behaviour
  differs.
* **The supply lever is a margin purchase**: to hold the delivered x above
  0.180 against the worst -0.057 m excursion the release floor must be
  **>= 0.237**, and the pair rule then needs the ceiling at >= 0.38 (a
  0.24-0.36 band degenerates `x0 ~ U(x_min, x_max - sep)`). Cost: three motion
  references + the scripted acceptance + both two-line gates + every store ->
  registered as **P38b**, not phase 2. `PREREG.md` instead registers four
  default-off direct-only knobs (`FRUIT_POLICY_REFUSE_DIAG`,
  `FRUIT_POLICY_REFUSE_END`, `FRUIT_POLICY_RESEED`, `..._MAX` = 2), three arms
  (control / END / RESEED+END) and four scenarios: **M1 the forced band**
  (0.10-0.17, 100 % refused), **M2 the mixed band** (0.10-0.36, 28 % refused,
  the conversion endpoint), **M3 the shipped patch band** (five supply seeds,
  the right-arm placed non-inferiority > -0.10, the no-new-reason set after
  mapping the notes to `lateral-refuse`, the fired-only cycle <= +5 %) and
  **M4 the scripted no-harm** (byte-identical `[fruit]` stream +
  `fingerprint: matches`), with six falsifiers and the rule that
  `no firable fruit` is still a failure in the rate denominator - the endpoint
  is *attribution*, never "the failure is fixed".

**P38 phase 2 (2026-10-25, `logs/p38/`, default off, **not adopted**): the
lateral-refusal harness names the class and halves its cycle, but the
re-selection cannot act in this harness, and on the shipped band the single
refusal landed in the control arm.** Four knobs, all default off and
`presentation == "direct"` only (`policy/trigger.py` `b09d3cb2`, `rl_env.py`
`f25f6b61`; `tasks.py` untouched): `FRUIT_POLICY_REFUSE_DIAG` (one
`lateral refuse: fruit x=... |dx|=... > lateral ...` note at the first
*provable* refusal - every other trigger gate passed, only the lateral one
failed, marked just before `x_edge_refusal` so the shipped fire decision is
identical), `..._END` (ends at the fruit's **departure** with
`no firable fruit: the trigger refuses (...) and the learned close never fired
(...)`, `outcome="no_firable"`), `..._RESEED` + `..._MAX` = 2 (bounded
same-lane re-selection, 4 scans/refusal, 1 per 60 ticks). **The Gate-1
condition H1 is the reason the END is defined this way**: the lateral gate has
never bound the learned close (`direct_fire = intercept or (policy_close and
gate_refuse is None)`; `gate_refuse` is only the opt-in `X_MAX` guard), so a
refused candidate can be picked anyway - on the forced band **5/15 (B) and 6/15
(C) episodes closed and 3 placed**. The class is therefore a *measured joint
closure* (trigger refuses + `x` frozen + no close through the fruit's
departure), and the END declines exactly those episodes (10/15, 9/15).
**H2 dissolved the registered supply bands**: a 4 cm lane is not a band - the
delivered x at 0.13-0.17 spans **0.117-0.191 (12 % above** the 0.173 floor) and
the free-cadence envelope 0.080-0.529 (depenetration kicks push fruit off the
**low** belt edge only - 0.080 against the 0.110 edge; the 0.529 maximum is
inside the 0.570 edge), so M1/M2 force the refusal with the **gate** on the
shipped supply (`TRIGGER_LATERAL=0` and `0.06`, the P2b-era gate). **H3** made
P4/P6 run-level unanimity gates (all five seed pairs negative **and** pooled
<= -0.10; the mirror for +5 %), because 47 right-arm episodes/arm at a ~40 %
base is a 1-sd ~0.10 point rule that false-fails ~1 in 6. **Measured**: M1
**15/15 refused in A, B and C** (P1 deterministic), **0 timeouts** and the named
class at median **562/510 ticks against A's 1335** (P3), A's terminals
`fell off the line` 12/15 + close 3/15 - **a registered deviation recorded as a
finding** (A1 predicted "ends at the horizon"; a refused fruit rides off the
belt end first), and the END's strength is that it collapses *both* terminals
(the horizon timeout and the lost episode) into one named class at the
departure; M2 refused **62 % (A) / 47 % (C)** with **83 scans and 0
candidates** - the re-selection is **structurally inert** because the direct env
calls `spawner.update` only in the reset's feed loop, so no fruit enters during
an episode (the amendment's "46 % lane starvation" is superseded: that number is
the free/driver cadence); M3 (the patch band, the shipped gate) had **1 refused
episode in 150 (0.67 %**, the phase-1 0.31-0.77 %, **not** the pooled 0.06 %),
and it landed in **A** (x = 0.157 - the drift tail, named by the diag where the
shipped note reads only `fruit fell off the line`), so C executed nothing: P4
right-arm placed **A 20/51 vs C 25/58, delta +0.039 [-0.138, +0.220]** with
per-pair +0.050/-0.111/-0.292/+0.179/+0.269 (PASS), P6 fired-only cycle **-2.0 %**
(PASS), **P5 FAIL** on both A-only keys coming from that one episode - the
pre-registered rule therefore reads **not adopted**, and that verdict carries no
harm evidence. **P5 is structurally a false-fail**: an arm-only key with a
0.5-1.2 event expectation per 150 is *necessarily* arm-unique, and the DIAG's
own `lateral-refuse` key is what fires it; a power-controlled form belongs in
the next registration (the literal read stands). The A/C arm-mix differs because
**the direct loop is not reproducible** (rendered frames; ep 0 is the same fruit
in both arms, ep 1 already differs, C executed zero actions), and the un-parked
**right-arm** base is **39.2 %** (20/51), not 45 % - the P35 mechanism is the
inactive left occluding the right arm's fruit, so the un-parked right rate is
the depressed one; the left's own 2/24 drags the *pooled* total, not that base.
M4: the scripted acceptance pair is **6/10 + `fingerprint: matches` in both arms
with the 376 `[fruit]` lines byte-identical** (md5 `bc7ca8f0`) and selfcheck
PASS - but the knobs are **unset by default and the scripted line never reads
them**, so that is near-tautological for this change; the `trigger.py` edit is
pinned by `811`'s lateral truth table + the analytic reorder equivalence, and
`accept_policy.sh` was **not** run (the knobs raise on any presentation but
`direct`, so the hybrid canary cannot read them). The DIAG's neutrality is read
by a same-batch **DIAG=0/1 pair** (`logs/p38/G2/`, 15 episodes each, one seed):
it agrees on **9/15** outcome classes (6/15 fruit) against the DIAG=1 repeat's
**14/15** (12/15), so the pair cannot carry neutrality at n=15 - the claim rests
on the construction argument (with `END`/`RESEED` off the harness writes notes,
bookkeeping and one fruit-pose read per refusal; none of it is a control input).
**The END's closure is scoped to "no close fired before the fruit's departure",
and the scope is a measured limit: `PREREG_A1` falsifier #1 FIRED** - 1 of 3
closes latched at `dy = -0.074 m` (7.4 cm past the station), so C3 is **not** a
total closure, `no firable fruit` over-claims on 1/15 of the forced band (a
failure either way: close-chase -> `no firable fruit`), and any flip needs a
re-registered definition (the post-departure rate quoted with the name) or a
post-departure grace window; the shipped-band readout of the close tick is owed
in the B-arm batch's report. **Recommendation**:
DIAG as the direct loop's diagnostic (owner sign-off), END as the measurement
interface with that B-arm shipped-band safety batch as its precondition, RESEED
not adopted (137 scans, 0 candidates) until the feeder is live inside an episode
(its own phase). Three **latent defects** are recorded as follow-ups, not fixed
(all direct-only, inert at the shipped defaults): `_reseed_step`'s
`spawner.protect` leaks into `protected_indices` (no unprotect; the
scripted/bimanual callers read that set); the END's `dy` is station-framed while
`should_fire`'s is `TRIGGER_FRAME`-framed; and the END runs before the fire
decision, ignoring `intercept`/`present`, with a per-episode `_policy_best_gap`.
Record `logs/p38/P2_RESULTS.md`; evidence `logs/p38/P2`, `P3`, `G2`, `M4`,
`P2_report.txt`, WORKLOG "P38 phase 2".

**P39 (2026-10-25, `logs/p39/`, default off, **not adopted**): the finger-tip
lane closes negative - the left's composite does not move at -4 mm in any
**evaluable** comparison, the
registered primary is not evaluable, the `47` probe's jam leaves the
belt-clearance claim untested, and `F1` is the tree's first **bimodal** arm, so
the lane has no arm it can certify.** Two levers were registered and only one
ran: **L1** `FRUIT_FINGER_TIP_DELTA` (`scene.py`, signed, **presence-gated** -
unset = the shipped mesh colliders byte-identically, `=0` re-authors the plate as
an AABB of the same mesh (arm **S**, the control), `=-0.004` shortens it (arm
**F1**)); **L2** the lift-only wrist hold closed as a **code fact before any
run** (the shipped `grasp_lift` already holds the commanded attitude - `_carry`
clears `arm.hold_quaternion` only for `name != "grasp_lift"` - so the knob only
swaps the hold *target*; `logs/444`'s negative is the place leg), and no W arm
exists. The batch is one claim with the arms **interleaved C -> S -> F1**
(same-tree control C; `scene.py` **988985ef**, `tasks.py` **112d2cb1**,
`rl_env.py` **238e90a4** - the `TASKS_MD5` metadata-only follow,
`configs/motion_reference.json` **25ade92b** untouched): C is a valid control
(pear **345/345** physics lines identical to `logs/p32/90_pear_battery_new.log`,
acceptance **374/374** to `D1_accept_pear.log` modulo the two print-only belt
messages; acceptance **6/10 + `fingerprint: matches`**). **The primary (the
species-locked pear battery) is not evaluable** - the left takes **2** attempts
in S and **4** in F1, so A1.3's count invariance fails - and **no arm improves**
in it (left placed/composite C **1/3**, S **0/2**, F1 **1/3**). **The acceptance
is inadmissible for the arm**: C's left takes 5 attempts and S/F1 take 6, the
left's fruit diverge from the third left attempt, and **inside S the same 5.4 cm
kiwi at the same read interference (grip-dia `+5.60` mm, close 22 ticks) cnp's
at attempt 3 and places at attempt 9** - so the acceptance's 5/6 left is not
evidence for the arm, and the matched-count "no fall" statement holds for F1's
**mode A only** (mode B: left 1 placed / 3 cnp). **The secondary band does not
fall** (pear left carry legs > 0.34 m/s: S 4 -> F1 5; acceptance 3 -> 3), there
is **no new failure reason** in any arm, and **F-1 is not adjudicable on F1** (a
byte-identity falsifier cannot be run on an arm that is not self-identical), so
the "contact-neutral" algebra is untested - **not** confirmed. **F1 is bimodal**:
five same-configuration acceptance runs land in two **bit-identical** modes -
**348 filtered `[fruit]` lines / 8-of-9** (x2) and **382 / 7-of-10** (x3), whose
first-attempt settle differs by one tick (0.88 vs 0.87 s); C (3 pairs) and S (1)
are single-mode, so the shipped line's determinism is not contradicted, but
**configuration vs harness is not separated** (the separators are more C/S
repeats and a fixed-pose contact read) and F1's numbers are **one draw**. **The
`47` probe does not measure belt clearance**: registered as a `-0.35 m` z
descent, it **jams laterally** - the jaw travels 0.13-0.17 m in x and 0.16-0.18 m
in y for 0.03-0.06 m of z, and C ends 90 deg rotated against S/F1 - and it prints
**no tool axis**, so N4 is **not computable as registered**; the belt-clearance
claim is therefore **untested, not measured-zero**, and PREREG **A3** withdraws
§6's "adoptable as a hardware/clearance change". What *is* proven: the box is
**authored** (build print long `84.9 -> 80.9 mm`, distal `80.5 -> 76.5 mm` at
`delta = -4 mm`), and the valid instrument for the clearance bit, if it is ever
wanted, is a **static-pose read of the authored collider prims** (`S - F1` must
differ by `4*cos(theta)`). **The pre-pose lever does not exist**: the station
pre-pose this tree's earlier record treats as a lane-0 mechanism
(`logs/p33/51_phase2_read.md` §3.1) is solved for the two-line's **right**
station only - the left station *is* the calibrated pick point
(`y = 0.00 = cfg.pick_y`), so `_prepare_two_line_stations` **skips its solve** and
the two-line left runs the same `grasp` config as the single arm
(`logs/p39/03_prepose_audit.txt`, whose annotation in the P33 read supersedes the
phrase). **The two-line reference is re-recorded**: `181c9151` was a pre-pear
W7-A record no post-P32 tree can reproduce (first physics difference `target
peach` vs `target pear` at attempt 0), archived to
`logs/p39/motion_reference_twoline_pre_p39.json`; the shipped
`configs/motion_reference_twoline.json` is now **d0326030** from the same-batch
control `logs/p39/p3/twoline_C.log` (6/10 at the 0.60 floor, `190` **PASS**),
while a W7-A-era two-line log now matches **no** current file - and
`scripts/189_w7a_chain.sh` re-writes the file from `logs/w7/10` before gating, so
it must not be run casually. Nothing was adopted: both knobs are **default off**
(`FRUIT_FINGER_TIP_DELTA`, `FRUIT_CARRY_ATTITUDE` - the latter a reporting-only
`[attitude]` line, one TCP-pose read per carry leg, whose `lip`/`tip=` constant
`FINGER_TIP_BELOW_JAW` is **80.5 mm** geometry, not the `logs/166` 76.8 mm
contact stop), F2 (the +4 mm extension) stays withheld/owner-gated (it is not the
authorized form), and the authorized P30-C hardware magnitude (24-45 mm) is not
tested here. Evidence `logs/p39/P1_READ.md`, `PREREG.md` (+A1/A2/**A3**),
`p2/NOTES.md`, `p3/RESULT.md` (§10 = the gate-3 close-out), `p3/P3_report.txt`,
`selfcheck.log`; WORKLOG "P39".

**P40 (2026-10-26, `logs/p40/`; **one** shipped change - the regrasp cap becomes
path-scoped - and nothing else adopted): the grip chain is measured end to end,
the carry class is **not** converted, and the only free rate on the tree was one
probe.** The default-off `FRUIT_GRIP_EFFORT=1` readout (reporting only: one
5-tick median per event, the finger drive's own numbers beside the tactile `N`)
ran two claimed acceptances (`logs/p40/p2/`, `effort_table.txt`): **the tactile
is not a scaled read** - the same-tick projected joint reaction agrees to
0.1 % / 0.5 % in both runs, so `GRIP_CENSUS` §3/§4's capacities and margins stand
and **nothing is multiplied by 2.2**; **the *command* is at its 10 N/joint cap on
40/40 contact rows** (the authored `k*err` is 4-8 kN, so `Fsat` clips every
time) **while the *delivered reaction* is 22 % of it** (2.21 N/joint = 4.42 N per
pinch) - the "2.2x discrepancy" compared the tactile to a cap the drive never
reaches, and the `F/err` ratio (**377 N/m at 120 Hz, 1045 N/m at 480 Hz**) is an
**operating-point timestep signature, not a stiffness** (the law is
unidentified). **`FRUIT_SUBSTEPS=4` doubles the force** - 4.42 -> 9.95 N
(**2.25x**, verified by both instruments) - at **3.08x wall** (266 -> 819 s) and
**+0.66 s/attempt** of span (`[stats]` 150.2 -> 156.8 over 10; *not* "+0.90 s",
*not* "+4 %"), which puts the **worst-case fruit's friction margin at
1.20x -> 2.70x** (`mu_eff` 0.45 against the 1.66 N following-error transient;
`mu_eff` 1.20 reads 3.20x -> 7.19x). Its **8/10 is a different attractor, not a
class gain**, and the left still carries-not-places **2/7** (orange attempt 3,
tomato attempt 9), so the class is **not deleted**. It ships as a **finding, not
a setting**: a store's **`write_manifest` `substeps` field is the unconditional
precondition** (the controller stays 120 Hz, `common.py:13-20`, so
*consumability* is not the issue) and a **real-jaw clamp-force anchor** gates
only a *fidelity* claim; the 2.25x-force / 3.08x-wall pair is **one pair** and
the scaling law is unidentified.

**The one adoption: `FRUIT_REGRASPS` is path-scoped** - **2 when
`_dynamic_capture_active`, 3 otherwise**, with an explicit env value winning on
both (`tasks.py`, `regrasp_cap`; the `FRUIT_REGRASP_REOPEN` slot reads the same
resolved value). Over 109 attempts a **third probe has produced nothing**: the
**17/17** attempts that burned all three never closed on the fruit at all
(`grasped 0/17`, `lift <= 0.004 m`), while the only conversion in the corpus came
on the **second** probe (`k=1`: 2/3 grasped, 1/3 placed) - which `=2` keeps - at
1.24 s (two-line) / 1.50 s (single arm) per failed probe. Measured with the knob
**unset** (the flip *is* the arm under test): the acceptance reads **5/9,
133.0 s, 14.8 s/attempt, 2 re-seat rows** against the control's **6/10, 150.2 s,
15.0 s/attempt, 3 rows**, and the two-line **7/10, 88.2 s, 8.8 s/attempt, 5 rows**
against **6/10, 90.2 s, 9.0 s, 13 rows**; the same-attempt read is the **k=3 tax
5.45 -> 3.93 s and 5.42 -> 4.00 s** with otherwise identical terminals, and both
runs are **byte-identical to the phase-3 `FRUIT_REGRASPS=2` battery** (339/339 and
430/430 filtered `[fruit]` lines), so the flip is exactly the measured arm. Both
counts are in **moved attractors** (`diverted` 0 -> 1; `no eligible fruit` from
attempt 4 on the single arm) and are therefore **not rate claims** - the
two-line throughput columns in `logs/p40/P3_RESULTS.md` are captioned as such and
stay out of this file. The indexed / policy-handover path keeps **3** by
construction: every re-seat row is `dynamic_capture`-and-`verbose`-gated and
`DirectSortEnv` is neither, so **no published number covers that retry** (and
`grasp.py`'s separate `GraspPrimitive` loop is untouched). **Both references were
re-recorded from these same-batch runs** because the flip moves both:
`configs/motion_reference.json` `25ade92b` -> **`adef05c9`** (pre-P40 file
archived to `logs/p40/motion_reference_single_pre_p40.json`) and
`configs/motion_reference_twoline.json` `d0326030` -> **`d87c3cdf`** (archived to
`logs/p40/motion_reference_twoline_pre_p40.json`); the gates then read
**`fingerprint: matches`** (rate-only FAIL, 5/9 < the 75 % single-arm floor) and
**`190` PASS** (7/10 at the 0.60 two-line floor). `scripts/189_w7a_chain.sh` was
**not** run.

**Two opt-ins, no flip.** `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` stays **off**: its
single-arm rule is also the **direct loop's** episode rule
(`select_target(..., reach_anywhere=False)` with no lane, `rl_env.py:1656`), so a
flip would silently move every direct baseline that has been measured, and the
measured gain is the arrival wait **1.41 -> 0.97 s** mean (1.20 -> 0.63 median) =
**0.4 s of a 15.0 s attempt (2.7 %)** on one branch, with +1 discharge; its
commit still sits **~0.15 / ~0.10 m above** the selector floor once the ~0.76 s
hover (0.09 m) is counted - the naive 0.463 -> 0.411 m read is a **lower bound**,
not a commit distance - so it does **not** spend the floor's margin.
`FRUIT_SUBSTEPS` keeps its shipped value (above). Pins: `tasks.py`
**`ec991e5c`**, `rl_env.py` **`8ebb8d87`** (the `TASKS_MD5` metadata-only
follow; HEAD `1790b87`), `scene.py` `988985ef`. Evidence
`logs/p40/{GRIP_CENSUS,RATE_CENSUS,LIT_REVIEW,PREREG,EFFORT_READ,REGRASP_YIELD,ARRIVAL_SPLIT,P3_RESULTS,P4_RESULTS}.md`,
`p2/`, `p3/`, `p4/`, `selfcheck.log`; WORKLOG "P40".

**P41 (2026-10-26, `logs/p41/`; **one** shipped change - the finger-drive
profile becomes the shipped default - and one **recorded deviation** from the
pre-registered F2): the grip force was a parameterization defect, the force
family is closed with a mechanism, and the carried-not-placed class does not
convert.** `control.finger_drive_profile()` ships **`finger_damp02`** —
**k = 1e5 N/m, c = 2000 Ns/m, pinned explicitly** (`c` is *not* derived from
`k`: the **ratio c/k = 0.02** is the mechanism) — with
`FRUIT_FINGER_STIFFNESS=0` as the pre-P41 path (the asset's own k = 1e6 /
c = 100, the 22 % delivery) and both env knobs still winning.
**Caption:** the delivered pinch goes **4.38-4.42 → 9.75-9.9 N (2.2x)** at
**1.00-1.01x wall per attempt** (14.8 → 15.0 s; the totals differ because the
branches take 9 vs 10 attempts), and 9.8 N is **50 % of the per-face cap** — 5.0 N
per face of the `Fsat` 10.0 N per joint (the tactile pinch sums both faces, i.e.
9.8-9.9 N of the 20 N the two caps could apply) — **the same ceiling
`FRUIT_SUBSTEPS=4` reaches at 480 Hz (9.95 N, P40)** for a third of the wall. The
plateau is reached at **c/k >= ~3e-3** (bracketed 0.002 → 7.2 N, 0.0033 →
10.0 N); the mechanism behind the ratio is **not identified**, so no threshold
number travels into the documents. **The pre-registered F2 fired**
(`logs/p41/DEVIATION.md`): the force rises and the class does not move, and the
profile ships *anyway* because the shipped 4.4 N is **44 % of what the same drive
delivers at 480 Hz** — the 120 Hz setting contradicts the asset's own authored
drive, i.e. a **parameterization defect, not a lever** — so the default flips and
**both references are re-recorded** although F2's clause says neither happens.
**Mechanism-positive, class-negative.**

The **census that decides it** (`logs/p41/P2_RESULTS.md` §4; `sep_max` from the
trace twins, which are byte-identical to the claimed runs, against the
`0.010 + 2·0.044 = 98 mm` mechanical stop): on the profile's escape legs
`sep_max` reads **98.5 / 76.0 / 77.4 / 64.2 mm** against the control's
**98.3 / 98.2 / 77.9**, so the pads **still reach their own open stop** while the
payload walks out along the tool axis (contact loss 12-63 ticks after the onset,
single-sided contact, `F → 0.00 N`, 38-54 servo trips) — **the pads hold and the
payload slides**, the W8-B loaded-slide class. The carried class is **not
force-starved** on this scenario. **`FRUIT_FINGER_MAXFORCE`** (default **off**,
**not adopted**) then takes the force family to its top end: the **cap** deletes
the pry — `sep_max` **98.5 → 43.5 → 31.2 mm** at **10 → 30 → 60 N** (that ladder
is why the default-off `[carry]` row carries `sep@loss`/`sep_end`) — and the
class does not convert: the acceptance **6/10 → 8/9 → 9/10** are **three
attractors** (not a rate), the pear **6/10 → 4/10**, the two-line **8/10 →
6/10**, and **60 N crushes a 3.7 cm strawberry** out of the hand (`clean_slip`
641 mm at `F@onset` 62.3 N). The pear control is **P41's same-tree 6/10**, *not*
P39's 6/9 (a different tree). **The sim's hold limit is geometry/hardware, not
force** — nothing here says the sim now holds the fruit (the acceptance still
reads 6/10 and the pear 6/10 under the profile).

**Provenance was the other half, and it is now unconditional.** `control.py` and
`common.py` were **absent from the collector's `sources`**, so no manifest could
tell a pre-profile shard from a post-profile one; both are pinned, and one
builder (`scene.finger_physics_provenance`) now writes the **`physics` block**
for **both** the collector's shards and the direct env's rollout manifests:
`profile`, `substeps`, `control_dt`, `dt`, `c_over_k`, the intent level
`FRUIT_FINGER_MAXFORCE` (null when unset), the contact pair, and the **per-joint
runtime read-back of k / c / `maxForce`** (`joint2`'s 0.0 N is the drive-less
mimic; `readback_matches` compares the **caps too**, so a `nan`/absent cap cannot
read like an `mf10` shard). The build print names the drive
(`profile=finger_damp02 k=100000 N/m c=2000 Ns/m maxForce=10.0/0.0N`), and the
drive-cap readers read the raw attribute **`drive:linear:physics:maxForce`**
instead of `UsdPhysics.DriveAPI.Get` (the call that constructs a schema object on
the mimic it describes; measured **inert** on this USD/lib, so the pre-fix builds
were sound, and the post-fix one-attempt run is **65/65 physics lines identical**
to the pre-fix control, `logs/p41/p4/a4_*`). Both references moved and were
re-recorded from the same-batch profile runs: `configs/motion_reference.json`
`adef05c9` → **`8a399626`** (the control arm matches the archive, so the move is
the flip's; gate `fingerprint: matches`, rate-only FAIL at 6/10 < the 0.75 floor)
and `configs/motion_reference_twoline.json` `d87c3cdf` → **`2246f83c`** (`190`
**PASS**, 8/10 at the 0.60 floor); the pre-P41 archives are
`logs/p41/motion_reference_{single,twoline}_pre_p41.json` and
`scripts/189_w7a_chain.sh` was **not** run. Pins: `control.py` **`9384ff4f`**,
`scene.py` **`27e3d64a`**, `tasks.py` **`54644916`** (the `[carry]
sep@loss`/`sep_end` diag), `rl_env.py` **`afe2c49b`**,
`scripts/40_collect_demos.py` **`cfcc6394`** (measurement-time
`8fae708f` / `6f9eba0b` / `1542ab4d`, before the phase-4 read-path and
manifest-sharing edits). Evidence `logs/p41/{FIDELITY_SWEEP,P2_RESULTS,P3_RESULTS,DEVIATION}.md`,
`p2/`, `p3/`, `p4/`, `selfcheck.log`; WORKLOG "P41".

**The phase-4 canary is a smoke, and it is inside the recorded spread.** The
hybrid policy canary (`SKIP_SELFCHECK=1 scripts/accept_policy.sh`, the shipped
`moe_v12`, the fixed pre-v9 supply, ten episodes,
`logs/p41/p4/accept_policy_profile.log`) reads **7/10 = 70 %** at the 0.60 floor
with **2 grip losses + 1 pick-station escape**
(`fruit left the pick station during the close (1416 mm)`, after the close had
already drifted the apple 283 mm - the policy's hand, not the drive: on the
preceding kiwi the fingertips were **575 mm** from the fruit when the close
started). The gate **FAILs on its reason clause only** (that note is outside the
recorded baseline set `logs/336_hybrid_v3all.log`; the verdict is printed in
`logs/p41/p4/accept_policy_claim.log`). This interface's recorded history is
**5-8/10** (`moe_v11` 8, `moe_v12` 6, P2b 5 and 6, P32 D0 5), so 7/10 is a
sample of the *p33-era* grip/station class, **not a rate** and not a profile
effect in either direction; the **direct** interface (where the profile is the
default presentation's drive) stays **unmeasured under it** and is the named
residual. No wedge, so no retry (the single retry was registered for a wedge
only); `189_w7a_chain.sh` not run.

**P42 (2026-10-26, `logs/p42/`; default off, **not adopted**): the seat is
centred and the seat family is closed in this parameter space - the pads are on
the payload at the close freeze and the payload leaves anyway.** The default-off
seat instrument (`FRUIT_SEAT_DIAG=1`, `[seat]` rows, 5 samples per grip) reads, on
two corpora (the acceptance and the species-locked pear battery, 10 grips each):
the pads' midpoint is **1.36-4.65 mm** from the fruit's centre in x/y on **20/20
grips** (median 1.7-2.4), **two-sided on 20/20** (per-pad `asym` 0.01-0.35, median
0.06-0.17), and the escapes are **not** the off-centre ones - on the pear the four
escapes are the *tightest* cluster (1.36-2.06 mm) while the corpus's largest
offset (4.65 mm) **placed**. That rank inversion is **noise at n = 4/6**; the
claim is carried by the **magnitude**: the entire available correction is ~3-4.6 mm
against a **104-276 mm** mid-lift walk - a factor of **30-60**. The only systematic
axis is **z** (+69.3..+71.7 mm = `_pad_standoff(True, sample)`, the *commanded*
standoff, i.e. the grip-plane question whose D2a form is measured negative),
not an error. What separates the classes is the **walk**, and it separates late:
the payload's hand-frame displacement by the lift's 99 % sample is **104-276 mm on
escapes vs 28-58 mm on placed legs**, with one pad out of contact on **18/32 escape
carry samples vs 0/48 placed** (at the first lift sample both classes read the
same 2.8-9.9 mm). **The bounded centring lever
(`FRUIT_SEAT_CENTRE=0.010`) acted and was absorbed**: it issued one `ik_step` per
grip (**|c| median 2.99 mm**, the 10 mm clamp never binding) and the freeze seat
was back at the control's value to **+0.00 mm** (pear, n = 6 pairs) / **+0.01 mm**
(acceptance, n = 10), because **the close owns the pose** - its own `coherent` flag
is **True on 20/20** grip closes and it issues an **absolute** `ik_step` every close
tick (`aim = [frozen_x, fruit_y + vy*lead, z = _pad_standoff]`; x **pinned** at the
first close tick by the shipped P2b x-lock, **y live**, **z commanded**), so a
one-shot pre-close correction cannot persist and the residual 1.4-4.6 mm is **servo
following error, not seating error**. The pre-registration's premise was a
**variable confusion** (`self._coherent[side]`, the carry bookkeeping's flag, False
60/60 - not the close's), so P1/P2/P3 are **not evaluable** and F2 fired by its
letter, not its named mechanism (`logs/p42/PREREG.md` amendment A1); the docstring
that repeated the false premise was corrected in **comment only**. **No count here
is a rate and there is no bare 6/10 -> 7/10**: the pear's moved branch changes the
**left attempt count 6 -> 4** (F5), and the acceptance is 6/10 in both arms on two
**different attractors** (the lever arm's fingerprint DIFFERS at leg 3,
0.109 vs 0.108 m/s). Verdict: the seat family is **closed in this parameter space** -
**reopen only via a new pad asset or a real-jaw clamp-force anchor**, never by
re-running "seat it better", and never read this as "the sim cannot hold the fruit"
or as "unfixable": `logs/p42/SIM_LIMIT.md` is **the canonical record** of the
loaded-slide limit (the mechanism, the closed force family, the reading rules - any
rate on this tree carries the `cnp` class). Scope: the **scripted single arm**; the
close is shared code but the two-line and direct paths were not run with the
instrument. Pins: `tasks.py` **`e2d0f12a`** (the measured tree was `3e6ea4cf`; the
close-out edit is the docstring only), `rl_env.py` **`50980bf5`** (`TASKS_MD5`
follow), **no `configs/` file moved** (`8a399626` / `2246f83c`). Evidence
`logs/p42/{SEAT_CENSUS,PREREG,P2_RESULTS,SIM_LIMIT}.md`, `p2/`, `p3/`,
`selfcheck.log`; WORKLOG "P42".

**P43 (2026-10-26, `logs/p43/`; **one shipped change - the arm park becomes the
direct env's default** - plus the phase-2 selector machinery at "0"): the park's
win reproduces at the P41 grip profile and it ships, scoped to the direct
presentation.** `FRUIT_ARM_PARK=back` is now the `direct` presentation's default
(`_park_default = "back" if presentation == "direct" else ""`, resolution owned
by `resolve_arm_park`): **`FRUIT_ARM_PARK=ready` restores the shipped pose** and
an explicit value wins everywhere; `handoff` resolves to no park, so it does not
raise. The phase-3 A/B (N = 5 runs x 15 episodes per arm, seeds 77/101/202/303/404,
policy seed 11, interleaved, one claim, `moe_v13s` `61da390a` on **both** arms,
the P35/P36/P37 patch scenario verbatim, four diagnostics on both arms) reads
right-arm carried **20/54 = 0.370 -> 0/56 = 0.000** (Fisher **7.31e-08**),
right placed **32/54 = 0.593 -> 53/56 = 0.946** (**+0.354**, Fisher 7.75e-06,
Newcombe one-sided 95 % lower **+0.228**), run level **5/5** (sign p = 0.031),
pooled **33/75 = 44.0 % -> 53/75 = 70.7 %** (**report only**; the
arm-standardised read is **0.320 -> 0.473** at 50/50 and 0.440 -> 0.707 at A's
mix), left **1/21 -> 0/19**, cycle **+0.2 %**. **Read it as one count, not five
legs**: **P1 and P2 are one 3-way outcome counted twice** (`placed = n - carried
- no-grasp`), so "+0.354 placed, p = 7e-8 carried" is a single contrast - the
independent legs are **P7 (the run level), P8 (the check), P5 (reasons), P6
(the cycle)**, and because 5/5 at five runs has **p = 0.031 as its minimum
attainable**, **P7 is the design's ceiling**, not a strong result on its own.
The left guard is **"not failed", not "PASS"**: 1/21 -> 0/19 clears the -0.05 bar
by **0.0024 = one episode**, and the informative read is its **carried 20 -> 18**
(the built-in no-op - `configs/arm_parks.json` lists a left-only vector, so the
left-arm episodes never move). **"0 carried" is 0/56, i.e. <= ~5 % at 95 % by the
rule of three, and 2 residual `force_min = 0` legs survive** (16 -> 2, roughly
8x reduced, **not deleted**); **"94.6 %" is one draw of a non-reproducible loop**
(rendered frames, CI ~0.85-0.99), not a rate. **The check** (read before any
outcome): the park arm holds the pose the reset **achieved** 56/56 on both reads
(M1-held/M1-applied), M2a 56/56, and the band census **0/1364 fully hidden** -
which is **"0 in 56 episodes"**, since those 1364 calls are ~56 clustered
episodes - against the control's 903/1340 = **67.4 %**; the 0.088 rad
achieved-vs-commanded residual is the `teleport_joints` settle property (the
shipped `ready` reset sits 0.037 from *its* command), which is why the gate is
written against the achieved pose. **The mechanism** is the W8-B loaded slide on
the right: `force_min = 0` **16/53 -> 2/55**, `clean_slip > 50 mm` **15/53 ->
2/55**, the retained pinch **9.31 N (A) / 9.74 N (B)** against the pre-P41 direct
corpus's **3.57 N**, and the left (no vector) unchanged (16/21 -> 15/19 lost legs,
`clean_slip` median 268.5 -> 253.8 mm) - the image channel, which P36's 2x2
separated (`which` image statistic remains unseparated). **Scope and the
re-baseline rule**: the flip is **direct-presentation only** (the canary
`60_eval_policy.py` never constructs `SortingRLEnv`, so `moe_v12` + park is
**untested** and has no deployment path), it **re-baselines the direct
interface** - every direct/policy number before P43 is a **pre-park** number, so
**to reproduce any of them set `FRUIT_ARM_PARK=ready`**, and park/no-park stores
must not be mixed (P37's transfer confound) - and **no motion reference was
re-recorded**: the scripted gate never imports `rl_env`, so `fingerprint:
matches` is an **import guard** on this change (the P38-M4-style near-tautology,
stated as such). `121`/`136`/`127`/`130`/`195` and the `110`-driven workflows
**silently re-baseline** to park-default. The A1 naming makes every log say it:
`[rl] env ready: ... park=back(default)` (`ready(explicit)` when set), the
`[park]` row `park=back(default)[left:back,right:ready]` (name, origin **and the
per-arm resolution** - the P43 B logs read `park=back` while the right arm sat at
`ready`), and the manifest's `arm_park.defaulted` (`true` = the default,
`false` = explicit, absent = pre-P43). The pinned pre-flip reproductions are
`logs/p43/p3/run_batch.sh`, `logs/p35/run_p35{b,c}_ab.sh` and
`scripts/219_p36_cells.sh` cells 1/4, whose A arms now pass
`FRUIT_ARM_PARK=ready` **explicitly**. **Two measured negatives ride the same
commit.** (1) **L1**: the nearest-above-floor selector is scoped
(`direct=True` -> always "0"; the scripted constant `NEAREST_ABOVE_FLOOR_SCRIPTED`
ships **"0"**) - the wait fell **0.32-0.73 s** in 4/4 pairs with a 2 ms mechanism
(1.958 s predicted vs 1.960 s measured on the seeded attempt), but `placed` fell
on **3/4** pairs, both treatment acceptance runs lost a slot to `no eligible
fruit`, and the mechanism's **prevalence is 20 %** of attempts against the 50 %
bar, so E3/E5 fail and the flip is **not** adopted - the machinery ships, so
`FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1` reproduces it with no code change. (2)
**L2**: the loop's pause is **10.7 %** of the episode wall (model 47.4 ms,
render 20.0 ms, camera 3.6 ms per decision) and **84 %** is the scripted primitive
plus physics stepping, so F4 fired and **no RTC/VLASH cell was run** - there is
no loop lever here. Pins: `tasks.py` **`a1b3d673`**, `rl_env.py`
**`0cefb13d`**, `control.py` `9384ff4f`, `scene.py` `27e3d64a`,
`policy/trigger.py` `b09d3cb2`, `policy/runtime.py` `379ac706`,
`scripts/224_p43_selftest.py` **`2edd81de`** (selfcheck: the selector scope + the
park default/scope), `configs/arm_parks.json` `42ab4fb7`,
`motion_reference.json` **`8a399626`** and `..._twoline.json` **`2246f83c`**
both untouched, checkpoint `moe_v13s` `61da390a`. Evidence
`logs/p43/{RATE_LEDGER,PARK_STATUS,POLICY_STATUS,PREREG,P2_RESULTS,P3_RESULTS}.md`,
`p2/`, `p3/`, `p4/`; WORKLOG "P43".

**P44 (2026-10-27, `logs/p44/`; default off, **nothing adopted**): the "don't cap
the arm" question is answered by arithmetic, and the speed cells buy 7-14 % at a
branch-dependent class cost.** The census (`logs/p44/CAP_CENSUS.md`) measures
every cap: **the joint velocity limits carry 2.1x** (`maxJointVelocity`
312 deg/s = 5.45 rad/s against the fastest reference), **the effort limits 2.4x**
(`maxForce` 7 N·m), and **the drive gains cannot change duration** - every leg is
**tick-clocked by its profile** (the model reproduces each leg to +-1.4 %, and
the gains were already measured null on the descent, `logs/165`). **The friction
cone does not bind on `lift` (a = 1.0 of 1.962) or `place` (1.089 of 4.273)** -
so what looks like a speed lock is a **profile choice**, and **48 % of the
15.05 s cycle sits in three blocks**: `place` **3.35 -> 2.49 s** (one
jerk-limited profile at `v_max` 0.35), `release` **2.04 -> 1.48 s** (1.57 s of
three open-loop holds), `lift` **1.82 -> 1.59 s** (the profile at `v_max` 0.30).
Three default-off cells (`FRUIT_SPEED_PLACE=0.52`, `FRUIT_SPEED_RELEASE=1`,
`FRUIT_SPEED_LIFT=0.36`) and their union (`FRUIT_SPEED_ALL=1`) are implemented
**on the existing per-leg overrides** (the `_SPEED_SHIPPED` block, `tasks.py`),
with a byte-identical unset path and a new selfcheck leg
(`scripts/225_p44_speed_selftest.py`) pinning the resolver and the seven caps /
ten read sites. **The union is real**: **-1.45 s/attempt** (median of two seeds:
15.00 -> 13.50, 14.60 -> 13.20), **-1.90 s** on the pear, **-1.10 s** on the
two-line (**+12 % placed/min, 4.90 -> 5.49, same 8/10**). **Nothing is adopted.**
S1/S2/S3 each fail the registered E4 **on the letter** (one new
`fruit did not follow the gripper` row apiece), and that class is the
**pre-contact acquisition** signature - the **pad span at onset** is 59-63 mm
(`sep@onset`; the *miss* is **219-481 mm**, `dynamic catch-up: residual` - P47's
correction), so the payload never sits between the pads; **the
control draws the same signature on seed 6 (59.4 mm) and 3/147 = 2.0 % of the
shipped single-arm corpus does**. The union passes E4 on all four batteries but
**fails E2 on the acceptance seed 6 - 5/10 vs 8/10** (Fisher **p = 0.30**; the
shipped line's own two seeds read 4 and 1 load losses), so the branch, not a
cell, decides. **On the held legs the cells read *lower* in-hand motion
(0.08-0.13 vs 0.07-0.18 m/s) and a *lower* place cone (median 0.87-0.88x vs
0.97/0.89x)**, i.e. the carried class is not implicated; the E4 failures are
acquisition. **The one positive worth a follow-up is the two-line**, where the
union is class-identical to the control and **11 % faster** - a two-line-only
adoption needs its own pre-registration and reference re-record. **A real defect
was found and fixed**: `FRUIT_DYNAMIC_PLACE_VMAX` was `min()`'d against the base
`FRUIT_CARRY_VMAX` (0.38), so a 0.52 cell silently resolved to **0.38** (-0.42 s,
not -1.09 s); the place branch now **assigns** its own cap, with byte-identity
proven on every recorded configuration (the shipped 0.35 is already below 0.38
and nothing sets `FRUIT_CARRY_VMAX`). **The ForceDelta half is scoped out with a
reason, not skipped**: it corrects a force/pose residual on a contact-rich
segment, and this tree's only such segment is the carry, whose class is closed
(`SIM_LIMIT.md`) with the cone not binding - and the guard family already
measured negative (`FRUIT_CARRY_GUARD` +5.4 % cycle, R6-B +4.5 %). The S13/E2
finding **justifies it as the named remedy** if the speed is ever adopted; it
would need its own pre-registration. **The 2026 frontier survey could not be
fetched** (a TLS `UNKNOWN_CERTIFICATE_VERIFICATION_ERROR`, then an `ECONNRESET`),
so `logs/p44/FRONTIER.md` records only what the local record already fixes and
says so. Pins: `tasks.py` **`b6de439c`**, `rl_env.py` **`93e35ef7`**,
`scripts/225_p44_speed_selftest.py` **`6b2e1945`**, `scripts/selfcheck.sh`
**`d82aa3af`**; `configs/motion_reference.json` **`8a399626`** and
`..._twoline.json` **`2246f83c`** untouched; `scripts/189_w7a_chain.sh` not run.
Evidence `logs/p44/{CAP_CENSUS,FRONTIER,PREREG,P2_RESULTS}.md`, `p2/`; WORKLOG
"P44".

**P44 amend (2026-10-27, `logs/p44/P2_RESULTS.md` §9) - the per-leg attribution,
with the existing knobs only (no `src/` edit) and the diagnostics proven
row-identical.** **S1** (`place` 0.52) moves `place0` **-135.4 ticks** and
`place1` **-64.2** (-1.13/-0.53 s) to **14.20 s/attempt, 6/10**, and is clean at
**both seeds** (the seed-6 pair 6/10 at 14.20 vs the control's 15.00).
**S3-v** (`lift` 0.37, `a` kept at **1.0**) moves the lift **-29.4 ticks
(-0.245 s)** with **no new failure row** and drops the `force_min == 0` legs
**5 vs the control's 7** - **the cleanest single cell**. **S2** at the clock floor
(dwell 0/pad 1/finger 1) takes the release block **2.04 -> 1.08 s** (130 ticks;
this confirms the **132-tick / 1.10 s** floor to two ticks, so the census's
"3 -> 1 = -1.02 s" was optimistic), reads **-0.96 s, 7/10**, and the release
landing is verified on every payload that reached it (**C 6/6, S2 7/7**; the
off-belt traces are lost *upstream*, never at the release). **The acceleration
half is not the lever**: the `a` 1.9 cell reads 1.59 s against S3-v's 1.57 s -
**0.00 s bought** - while spending transient (cone 1.42x vs 1.19x). `--strict-cone`
fails on the **control** too, so it is a relative report (C 5 legs/1.53x,
S1 3/1.53x, S3-v 7/1.19x, S2 4). **The pre-registered decision stands: nothing is
adopted.** The named adoption candidates, each needing its own pre-registration
and the two reference re-records, are **S1** (the largest clean single cell,
5.3 %) and the **two-line union** (class-identical, 11 %); the union's seed-6
5/10 stands as the reason it is not shipped as-is. Pins: `tasks.py` `b6de439c`,
`rl_env.py` `93e35ef7` (unchanged by the amend), the evidence as above.

**P45 (2026-10-27, `logs/p45/`; **default off, nothing adopted**): a lighter fruit
does not make the cell fast - it makes the walk worse and leaves the fling
alone.** The knob `FRUIT_MASS_SCALE=<x>` (a **physics change**, named as one;
`meshes.mass_scale()` parsed once at import, hard-erroring on `0`/negative/`inf`/
`nan`; applied at the **two** mass sites in `fruits.py` - the pool build and the
recycle `rescale`, which is the site that silently returns a respawned fruit to
full mass if missed - behind `if scale != 1.0`, so unset skips the multiply; the
inertia needs no second attribute because no fruit authors `diagonalInertia` and
PhysX derives the tensor at the authored mass; the sizes/meshes/colliders are
untouched; one build banner). The battery (5 arms x the acceptance + the pear,
every arm with `CARRY_DIAG`/`RELEASE_DEBUG`/`CYCLE_REPORT`): acceptance **C 6,
M50 6/9, M25 4/10, M50S 5, M25S 5**; pear **C 6, M50 7, M25 7, M50S 7, M25S 6**
- and the **speed is entirely the P44 cells** (15.0 -> 13.4-13.5 s/attempt with
the mass contributing **0.0-0.1 s**), so the mass buys nothing. **The census's
fling prediction was wrong and the measurement says why**: the release is a
**displacement-controlled pad ramp** (the exit speed is set by the pad-face
motion and the 47-68 mm drop), not a fixed impulse, so `v = J/m` never applies -
the in-hand release peak is **0.93-1.08x** of the control at 0.25x mass. What
*worsens* is the **walk**, on the mixed pool only: at 0.25x the acceptance's
escape legs go **7/20 -> 12/20**, its zero-force (loaded-slide) legs **7/20 ->
13/20**, and `clean_slip_max` p50 **0.1 mm -> 228 mm** - the loaded slide is not
mass-starved (it holds 4-5 N on one face while the payload walks), so taking mass
away gives the contact **less to resist**; on the single-class pear the same cell
reads *better* than a control that lost 8/20 legs, which is the branch, not the
mass. **At a fixed size 0.25x is 205-225 kg/m^3 (cork), so the cell can never
ship**; a physical equivalent would be a **smaller real fruit** - a new scenario
with new pinch spans, not a density change. **The frontier is in
`logs/p45/FRONTIER.md`** (the live survey succeeded on the third attempt, done
directly after the tool failed twice): **ForceDelta-VLA verified against the
abstract** - a *correction-distillation* from a frozen teacher's paired
force-conditioned/force-agnostic predictions, a separate **delay-correction**
target, asynchronous schedule replay with cached context, and a lightweight
policy that adjusts the reference from recent force history **without
regenerating chunks**: **82.2 % vs 54.4 %**, the Stage-1 teacher alone 70.6 %,
**~26 % lower peak contact force**; the ICLR 2026 *time-optimal execution of
action-chunk policies* (beyond demonstration speed) is the policy-loop pointer;
the delta robots' >100-200 picks/min are vendor **claims** on a different
kinematics; and **no measured study of a light payload being flung out of a
parallel jaw** was found. The transferable shape is the **bounded force-derived
pose residual between reference updates** (the named remedy for the P44 speed
cells), **not** the distillation (it needs a paired-teacher retrain, and this
project's three recollections read no-gain). Pins: `fruits.py` `b6de...`-era tree
+ the P45 faces (`meshes.py`, `fruits.py`), the cells default off, `configs/`
untouched.

**P46 (2026-10-27, `logs/p46/`; nothing adopted): the two-line union's +12 %
did not replicate at a fresh seed, and the class that moves is the pre-contact
acquisition, not the grip.** The P44 two-line positive was one seed; P46
pre-registered a **2-seed** confirmation **before** the run (`logs/p46/PREREG.md`)
and ran it with the existing knobs only (`FRUIT_SPEED_ALL=1`, no `src/`, no
`configs/`; the C arm is **453/453 rows identical** to P44's
`twoline_s5_C.log` and the U arm **446/446** to its S13 arm, so the instruments
are neutral and the default-off path is proven). **Seed 5 (a P44 replay)**:
placed **8 -> 8**, `s/attempt` **9.80 -> 8.75 (-1.05)**, interval 9.13 -> 8.27,
**4.90 -> 5.49 placed/min**. **Seed 6 (the fresh draw)**: placed **9 -> 7 (-2)**,
`s/attempt` 9.98 -> 9.51 (-0.47), interval 10.09 -> 10.88, **5.41 -> 4.42
placed/min**. **The guard is clean**: 0 held-then-lost rows in all four logs, the
held legs' >50 mm slip 0/0, `clean_slip` p50 0.00-0.05 mm; the s6 `force_min==0`
legs (1 -> 3) are **never-held** (contacts@onset 0, force@onset 0.00 N, the pads
closing on air; **52-65 mm is the pad span at onset, not the miss** - the miss
is 219-481 mm, P47's correction) - the **acquisition** class, not the loaded
slide. The
landing is clean too (**32/32 release-reached traces `on_belt=True`**). E1/E2
fail on seed 6, E3 fails by its letter only, E4/E6 pass; **F2 fires -> no flip,
no Phase 2** - the union stays **opt-in** and the single-arm cells stay opt-in.
**The lesson, stated for the next lane**: the speed is **real and reproducible**
(-10.7 % `s/attempt` on the seed-5 branch; the blocks move by the profile
arithmetic), but the **placement count is not stable across branches**, and what
moves is the **acquisition** class (a faster leg re-times which fruit is offered
at the close), **not** the grip - so a speed adoption must be gated on an
acquisition-class fix (a supply/station change) and not on the carried class.
Pins: no `src/` or `configs/` change (refs `8a399626` / `2246f83c` untouched);
evidence `logs/p46/{PREREG,P1_RESULTS}.md`, `p1/`.

**P47 (2026-10-27, `logs/p47/`; **not run - the census refuted the lever before
it was built**, nothing adopted): the "close on air" row is a standing property,
not an event, and the real pre-close discriminator is the catch-up residual.** A
census of 317 closes across the shipped / P44 / P45 / P46 corpora settles it: the
`... mm from the fruit; closing anyway` row fires on **317/317** closes with a
**7 mm-wide band** that is the **hover clearance** (70 mm nominal = `hover +
pad_lift`) measured **against the station, before the hover and the descent** -
its value carries **no** outcome information (Fisher **p = 0.61**), and the axis
sibling is **dead** (0/317). The fallback the row names is **unreachable**:
`pad_error > 20 mm` is always true, so `self._coherent[arm]` is **never set**
(0/317) - a dead code path, the P42 note's mechanism generalised. **The live
pre-close error is what separates the classes, and it is already printed**:
`[task] dynamic catch-up: residual` above its 6 mm tolerance reads **8/8
no-grasp** against **11/309 = 3.6 %** below it (**p = 3.3e-11**) - but it
explains only **42 %** of the no-grasp class, and its failing values are
**220-481 mm**, i.e. a **hand-over-timing** failure, not a distance-to-close. The
registered `35 mm / 40 tick` guard was therefore **predicted to fire on 8/317 =
2.5 % of closes and convert ~0** (the convertible 35-75 mm band is empty in the
corpus), so the battery was **not spent** - the PREREG is kept with its own
pre-run prediction as the record (`logs/p47/PREREG.md` §prediction). **The named
next lever is the hand-over timing/selection** (a target **2.4x** the catch-up's
reach budget away) plus the **11 converged close losses**, not a distance wait.
Pins: no `src/` or `configs/` change; evidence `logs/p47/{ACQ_CENSUS,PREREG}.md`,
`census.py`/`census_out.txt`.

**P48 (2026-10-27, `logs/p48/`; **not run - the census refuted both registered
levers**, nothing adopted): the acquisition misses are the **delivered-x tail**,
not the hand-over timing.** Across 317 closes the catch-up residual's >6 mm band
is **8/8 no-grasp** against 3.6 % below (Fisher **p = 3.3e-11**), and the band
6.0 -> 219.6 mm is **empty** - so the split is categorical. **The four events
share the x tail, not a timing**: **|x| >= 0.390 is 6/6 failed** (p = 2.1e-11
against 2/311), `>= 0.38` is 8 rows with **0 placed**, and within kiwi 8/8 vs
2/27 (p = 1.9e-06) - 3/4 are kiwis at **x 0.391-0.397**, i.e. **0.8-6.9 mm past
the 0.39 m clean lateral band**, while the arm recovered only 20-51 mm of the
200 mm the fruit moved; the fourth (480.6 mm) is the corpus's **only cross-belt
displacement** (a 379 mm drift, a 58.15 N / 99.1 mm-span close in 5 ticks) - a
supply event, not a timing miss. **The hand-over lead is a constant 0.189 m on
all 317 attempts**, so it cannot discriminate, and `dy0` ranks mid-population.
The reach budget is 200 ticks x 1.0 mm/tick = **200 mm**, and the residuals are
**1.10 / 1.23 / 1.26 / 2.40x** it - P47's "2.4x" was the **maximum and belongs
to the non-timing event**. **Both registered levers catch 0/4**: the lead
(`FRUIT_DYNAMIC_LEAD_MARGIN` 0.03 -> 0.20) moves the lead to 0.359 m but the
selector floor to **0.569 m** (against a measured dy0 max 0.570) for **+1.42 s
per attempt**, and the longer catch-up (200 -> 400 ticks) helps only the
displaced fruit while making the other three **~200 mm worse** - so the battery
was **not spent** (the PREREG keeps both predictions). The **11 converged close
losses** are the closed **grip/hold** class (the W8-B loaded slide: `contacts@
onset = 0`, `force_min = 0.00 N`, 2 re-seat rows on every single-arm one), not
acquisition. **The named next lever is a scripted selector x-ceiling** (refuse or
re-select fruit with x > 0.39 - the P38-style refusal on the scripted line, whose
selector polls, unlike the direct env's frozen feeder) plus the **supply
displacement** event. Pins: no `src/` or `configs/` change; evidence
`logs/p48/{HANDOVER_CENSUS,PREREG}.md`, `handover_census.py`/`_out.txt`.

**P49 (2026-10-27, `logs/p49/`; **not run - the ceiling refuses nothing**, nothing
adopted): the selector's x is always inside the band, and the failing x is the
**post-selection drift**.** The census (`logs/p49/SELECT_CENSUS.md`) reads the
`[bed-sel]` selection census across the shipped / P44 / P46 corpora: the **chosen
fruit's x never exceeds 0.38** (max **0.3653-0.3802**), so a ceiling at 0.39,
0.40 or 0.42 refuses **0 of 40** selections at every threshold - the lever is
**inert by construction**, because the P48 failures' x (0.391-0.397) is the
**drifted x at the close**, measured **after** the selection. The drift is P38's
**per-instance release offset** (delivered x = spawn x + offset(instance)), not a
selection error. A binding ceiling would also be expensive: a usable set of **1**
in **25/40** selections means a **skip** (no substitute), and the 14/40 with two
would substitute at **+1.08 to +2.08 s** (the next fruit arrives sooner). **The
named next lever is therefore P38b's per-instance release-offset compensation at
`respawn`** - the one thing that puts the *delivered* x back inside the band - and
not a selection rule. Pins: no `src/` or `configs/` change; evidence
`logs/p49/{SELECT_CENSUS,PREREG}.md`, `select_census.py`/`_out.txt`.

## 3. What changed -> what to run

| you changed | run |
| --- | --- |
| docs, or a number's provenance/data size | `python3 scripts/106_index_audit.py` and `python3 scripts/107_collect_merge_test.py` |
| motion, control, `trajectory` limits, IK | `python3 scripts/96_motion_check.py`, then `scripts/accept.sh` |
| collection (`40_collect_demos.py`) or merging (`41_merge_demos.py`) | `scripts/107_collect_merge_test.py`, then `python3 scripts/106_index_audit.py` |
| simulator behaviour, scene, gripper, conveyor | `scripts/accept.sh`, then `scripts/demo_2min.sh` |
| the supply schedule (`fruits.py`, `bed.py`) | `python3 scripts/211_bed_audit.py`, then `scripts/selfcheck.sh` |
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
backlog grouped into WS-1..WS-7, the phases R0-R9, the resource budget and the
owner-decision register); the periodic ops self-check and its anti-stall
playbook are in `docs/OPS.md` - run `scripts/191_ops_selfcheck.sh` (verdicts
OK / STALLED / ACTION), at the start and end of every work block and every
30-60 min while a simulator phase is active.
