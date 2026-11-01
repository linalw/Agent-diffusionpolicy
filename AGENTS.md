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

**P87 (2026-11-01) re-baselines the acceptance again: the shipped two-line cell
now runs the release trim** (P86's S2 cell, `FRUIT_SPEED_RELEASE`, as a
**two-line-scoped** default), so the acceptance reads **7/10, 9.4 s/attempt**
with `configs/motion_reference.json` = **`423896f7`** (re-recorded from
`logs/p87/accept10.log`; the pre-P87 file `eb697f23` is archived at
`logs/p87/motion_reference_pre_p87.json`, and `configs/motion_reference_single.json`
`8952c320` is **untouched**). **Every two-line rate, span or interval recorded
before P87 is a 2.35 s-release number; `FRUIT_SPEED_RELEASE=0` restores it.**
**P88 (2026-11-01) measured the next lever - the `place` cap - and shipped
nothing**, so every acceptance, reference and store above stands unchanged:
`FRUIT_SPEED_PLACE` stays **off by default** (`PLACE_TWO_LINE_DEFAULT = False`)
because, although the block's mechanism was exact at **-0.77 / -0.92 s** per
placed attempt, the delivered interval rose at **both** seeds
(`logs/p88/RESULTS.md`).

**P85 (2026-11-01) superseded every acceptance number below in this section: the
shipped scripted cell became the bimanual two-line**, so `scripts/accept.sh` runs
a *different scenario* (7/10, `configs/motion_reference.json` = `eb697f23` at the
time, the two-line floor 0.60) and `FRUIT_BIARM=0` restores the single-arm record
archived at `logs/p85/motion_reference_single_pre_p85.json` (`8952c320`, 6/9).
Read §2's "P85" and "P87" paragraphs before quoting any acceptance, rate or store
from here.

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
shipped**. **P60 re-read that batch by arm and the "one open item" is answered:
it is not a left lever** - joining each episode's opening `arm=` to its closing
triple, the 48 -> 27 carried conversion is the **right's 28/51 -> 5/48** (Fisher
~2e-6) with the **left flat at 20/24 -> 22/27** (placed 2/24 vs 2/27, p = 1.0);
pre-P41 and pre-park, i.e. exactly the arm P43's park already fixed, so **no
direct carried-class lever for the left remains unspent**.
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
adopted): there are **two x populations**, and the ceiling only sees the first.**
The census (`logs/p49/SELECT_CENSUS.md`) separates them: the **selection-time x**
(the `[bed-sel]` live set, 40 selections) has max **0.369**, so a ceiling at 0.39,
0.40 or 0.42 refuses **0 of 40**; the **delivered x** (174 unique attempts of 346
raw rows) reads p50 **0.276**, p90 **0.347**, max **0.3969**, with **> 0.39 =
3 (1.7 %)** - shipped 0/33, P44 2/73, P45 0/33, two-line 1/35. **The post-selection
x is not an identity**: 34/39 selections agree to <= 2.7 mm but **5/39 move
outward 5.3-19.2 mm** (P38's depenetration residual), so the failing x is bounded
to **[0.378, 0.397]** and the ceiling cannot catch it - the lever is **inert for
this class** (an earlier draft of this paragraph overstated it as "never exceeds
0.38" by reading one arm's range). A binding ceiling would also be expensive: a
usable set of **1** in **25/40** selections means a **skip** (no substitute), and
the 14/40 with two would substitute at **+0.9 to +2.1 s** (the next fruit arrives
sooner). **The named next lever is therefore P38b's per-instance release-offset
compensation at `respawn`** (P50) - the one thing that puts the *delivered* x back
inside the band - not a selection rule. Pins: no `src/` or `configs/` change;
evidence `logs/p49/{SELECT_CENSUS,PREREG}.md`, `select_census.py`/`_out.txt`.

**P50 (2026-10-27, `logs/p50/`; **the mechanism lands, the count gate fails, not
adopted**; the compensation ships **opt-in** with its per-pool tables).** The
per-instance release offset P38 left as a corollary is now measured: it is a
**per-instance constant to 0.00 mm** (two passes over 48 cells **bit-identical**, a
3-repeat cell `-2.90 x3`, settle -> station **0.09 mm** over 215-224 ticks,
cross-process <= 0.15 mm), **13/16 are x-independent** and the three rollers are
**1-3 discrete modes 11-20 mm apart** (not a slope), and a **(species, diameter)
table cannot carry it** - two strawberries **0.9 mm** apart in diameter differ
**44.3 mm** (pooled fit R^2 0.74, residual sd 10.2, max 31.0) - so the table is
**per pool**. `FRUIT_RELEASE_OFFSET=1` + `FRUIT_RELEASE_OFFSET_TABLE=<path>` shift
the already-drawn spawn x by `-offset(instance)` at `respawn` (no band clamp; the
measured excursion **0.155-0.389 m** stays inside the belt 0.11-0.57), default
**off**, and the tables are `configs/release_offsets_{accept_s5,pear_s5}.json`
(16 instances each, the two rollers at the pre-registered **minimax midpoint**,
the pear **identity**). **The mechanism is proven**: the isolated table goes
**8/96 -> 0/96** cells outside `[0.180, 0.390]` (0.1730-0.4131 -> 0.1932-0.3785,
pass spread 0.00 mm) and the live line's residual collapses **-35.73..+54.63 ->
-9.84..+9.83 mm** with the **planned draws untouched (65/65)**; the pear is
**inert** (378/378 physics lines identical, 6/10 both) and the no-harm arm is
**377/377 identical** to the reference with `fingerprint: matches`. **The
pre-registered count gate fails**: the acceptance reads **6/10 -> 4/10** on a
**moved branch** (the fruit sequence diverges at attempt 1; attempts 5/7 are apples
in O vs strawberries in C; every failure is `cnp`, the closed grip class), while
**both arms read 0/10 outside the registered band** - the PREREG's own power
statement says a 10-attempt count **cannot resolve** a 1.5-3 % tail. **Verdict:
P1/P2/P4/P5/P6 pass, P3 fails -> not adopted** (PREREG §5); the mechanism and its
tables stay opt-in for a scenario whose endpoint is the tail (the powered M1b form)
rather than a count. Named residuals: the mode rule is a **bound, not a
prediction** (the strawberry collapsed to one mode, the tomato became bimodal - both
inside the 20 mm margin); the **patch/bed** schedules are scope-gated and
unmeasured; the **direct/policy** interface reads the *delivered* x, so it would
benefit for free, but its A/B is its own pre-registration. Pins: `fruits.py`
**`e81051c1`** (+188/-0), `tasks.py` `b6de439c` unchanged, the two existing refs
untouched (`8a399626` / `2246f83c`); evidence
`logs/p50/{OFFSET_TABLE,PREREG,P2_RESULTS}.md`, `p1/`, `p2/`.

**P51 (2026-10-27, `logs/p51/`; **not run - the map refuted the hypothesis**,
nothing adopted): the speed cells' cost is the closed grip class, not the
release-x tail - and the speed arc closes.** The hypothesis was that the P44/P46
speed cells' only cost was the **pre-contact acquisition** and that P48's x tail
is that class, so `O + U` (P50's compensation + the speed) would be class-clean.
The offline map (`logs/p51/COMBO_MAP.md`) says **F1 fires**: of the **5
cell-attributable events, 1 is tail and 4 are mid-band** (x 0.22-0.38) **with a
converged close** (`dynamic catch-up: residual` 5.5-6.0 mm, i.e. **inside** the
6 mm tolerance) - the **closed grip/hold class**, not a supply-x object. So
`O + U` **cannot** be class-clean and the phase-2 battery was **not spent** (the
PREREG keeps its pre-run prediction). **The speed gain stands separately** (P44's
union -1.45 s/attempt; P46's two-line -0.76 pooled, -10.7 % on the seed-5 branch),
and its count cost is measured as **branch-draw `cnp`** on the single arm and
**converged closes** on the two-line - the same class `logs/p42/SIM_LIMIT.md`
documents as closed. This does **not** say the P50 tables are wrong (their object,
the release x, is simply not this corpus's cost), and it claims no rate (the same
cell draws 0 rows at seed 5 and the shared strawberry at seed 6 - one branch's
count). **What closes with it**: there is no remaining lever on the
acquisition/tail side of the speed question - the acquisition family is exhausted
(the distance guard, the hand-over timing, the x-ceiling and now the combination
all refuted by measurement), the speed is real, and **its cost is the closed grip
class**. A future speed adoption therefore has to be argued on the **time**
(-1.45 s/attempt at 10-14 %) with the placement cost named as the documented
class, not on a class fix. Pins: no `src/` or `configs/` change; evidence
`logs/p51/{COMBO_MAP,PREREG}.md`, `combo_map.py`/`_out.txt`.

**P52 (2026-10-28, `logs/p52/`; the model lane: **the policy-side speed has a
structural ceiling**, the two success hypotheses die offline; nothing adopted).**
The frontier's gate is RoboPace's ladder (arXiv 2610.09696, on a **dual-arm
OpenArm**): the same chunks at 10/30/50 Hz read **22/50 / ref / 4/50**, the
kinematic-only RACE-style retiming **1/50**, and the **contact-gated 32/50** at
half the slow arm's time - **the trade-off is speed *at contact***, and 1.67x
uniform costs 84 % of the success. This tree's policy does not own the cycle, so
the frontier's "beat the demo speed" framing does not transfer: the **policy phase
is 14.2 % of a placed episode** (256 of 1800 ticks, `logs/p52/P2A_RESULTS.md`), a
1.5x re-timing of the whole phase is worth at most **4.8 %**, and with the contact
gate firing on **44.1 % of the decisions** (4492 of 10202 ticks; peak force
216.4 N - RoboPace's "mostly free space" premise does **not** hold here, since
touch alone is 21.8 %) the measured gain is **-2.9 %** (median 1800 -> 1748 ticks;
paired -48.1, n = 23, 17/23 negative; **-5.0 % on the clean tree**) against a
**<= 4.8 % ceiling** - the registered -8 % bar was **unreachable by construction**,
and the paired/tick coincidence is **partly an unmatched initial condition** (the
treatment's fruit starts 21 mm closer at the reset, a feedback from shorter
episodes), so it is **not** a validation of the arithmetic. **The right arm - the
one the lever acts on - is unchanged**: 30/31 -> 28/29 placed (**delta -0.002**,
P2 PASS), and the pooled 32/45 -> 28/45 is entirely the **left's closed-`cnp`
draw**; no new failure reason (P3). `FRUIT_POLICY_TIME_SCALE` /
`FRUIT_POLICY_RETIME_GATE` stay **default off** (the 85 % scripted primitive is
untouchable by any policy-side execution lever). **Two success hypotheses died
offline** (`logs/p52/P2B_FEASIBILITY.md`): (1) the **reached-state supervision**
is not a defect - the labels are **0/581 455** out-of-range and the HOLD-frame
residual is 0.84/0.01 mm; the real defect is the **policy's own emissions**
(**13.1 % of joint steps out-of-range on 74.3 % of ticks**, 3-9 deg overshoot, no
clamp, a **19.3 mm p50 task-space dither**); (2) **PACE** (NeurIPS 2026, the
phase-aware execution horizon) dies structurally - the policy's chunks are **noise,
not a trajectory** (within-chunk min p50 2.44 rad/s, 0/60 below 0.30 rad/s,
|2nd|/|1st| 1.16), so the horizon rule returns h = 16 everywhere (64 -> 16
decisions, wall -12 %, **sim and placements unchanged**), and the policy's "phase"
is the belt-arrival wait, which the floor already covers. **Corrections the lane
made to its own census**: the decisions/episode is **53-84** (not 246-259 - that
was a tick count), the latency bound is **h <= 7** (71 ms = 8.5 actions, not 13),
and the intra-chunk rates were **4x understated** (the p99 headroom 2.35x/3.34x ->
**0.83x**). The named next lever is the **opposite** direction: an **action-hold**
(more ticks per action, to fix the dither/overshoot) plus a **joint clamp** on the
emissions - a success-first cell with the ticks as a reported cost. Pins: no
`src/`/`configs/` change shipped (both knobs default off); evidence
`logs/p52/{FRONTIER,MODEL_CENSUS,P2A_RESULTS,P2B_FEASIBILITY}.md`, `p2/`.

**P53 (2026-10-28, `logs/p53/`; nothing adopted): the policy's own emission defect
is not the success bottleneck.** The direct path emits **10.9-11.0 % of its joint
steps out of range** (8341 of 76587 ticks; 65.0 % of ticks carry one; 3-9 deg
overshoot, no clamp) - the earlier "4.8 %" was **one episode**, not the corpus.
Two default-off cells on the P43 protocol (N = 3 x 15, seeds 77/101/202): **C1 the
joint clamp** (the targets clipped to the arm's own `get_dof_limits()`, a copy,
after the shapers) removes the defect **completely** (`out 11.0 % -> 0/70938`, zero
time cost) yet reads **30/45 -> 29/45 placed** (per seed +1/-1/-1; the right arm
**29/30 vs 28/28**) - a **null** on the class, so the overshoot was **not** the
binding term; **C2 the action hold** (`action_hold=2`, 8 ticks/decision, 60 Hz of
decisions) reads **26/45** (0/-1/-3) - but that is a **pooled/arm-mix** statement:
the right arm is **26/26 = 100 %** and arm-standardised at T0's mix it is **30.0 vs
30.0**, the pooled drop being the left's closed-`cnp` draw, while the hold's real
win is the **wall** (**-7.1 %**, decisions **61 -> 29**, the 32 fewer model calls at
71 ms; the sim time is flat). **The dither story is corrected too**: the
same-tick dither falls 21.8 -> 17.1 mm but the **achieved arm rate falls 0.87 ->
0.73 rad/s** (-16 % of real motion), so the dither was buying motion, not waste. So
the policy's own emission path is exhausted as a success lever: the right arm's
remaining ~5 % sits in the **scripted close/handover/grip** class (P35-P43), not in
the policy's targets. With
P52 this closes the **model lane**: the policy owns **14.2 %** of the episode (its
speed lever is bounded at 4.8 %, measured -2.9 %/-5.0 %), its supervision is
sound, its chunks carry no phase structure, and clamping its emissions is free
but gains nothing. The model-side levers that remain are the **interface** ones
already measured (the park default; `FRUIT_POLICY_EVENT=1` at +6.7 pt on N = 3,
never at N = 5; the ACQ question that the shipped direct config leaves untested).
Pins: `rl_env.py` **`a1ae217a`** (both knobs default off), a new selfcheck leg
`scripts/229_p53_emit_selftest.py`; no `configs/` change; evidence
`logs/p53/{PREREG,P53_RESULTS}.md`, `p3/`.

**P54 (2026-10-28, `logs/p54/`; **one shipped change, a recorded deviation from
R5: the adaptive acquisition lead is now the direct presentation's default**): the
shipped direct config was **not** the configuration on record.** Every "direct
94.6 % / 4.8 %" number in this file was measured at `FRUIT_POLICY_TRIGGER_ACQ=1`,
while the shipped default left `acq` **off** (W7-B/R5 kept the knob a *measurement
interface*). P54 ran the A/B the record never did (N = 3 x 15, seeds 77/101/202,
the P43 protocol, the park default, `moe_v13s` `61da390a`): **A (shipped, ACQ
unset) 16/45 = 35.6 %** - right **15/28 = 53.6 %**, the **never-held class 26/45 =
57.8 %**, the catch-up residual p50 **90.6 mm** (p90 391.6, max 1212.6; 24/45 over
the 6 mm tolerance) - against **B (ACQ=1) 34/45 = 75.6 %**, right **34/35 =
97.1 %**, never-held **2/45 = 4.4 %** (Fisher **p = 3.2e-8**; right 12/28 -> 1/35,
left 14/17 -> 1/10), the residual p50 **5.7 mm**. **The mechanism is the fire
budget**: the fixed 0.90 s lead fires at `t_arrive` 0.89-0.90 s on 45/45 against
the handover's own **1.17 s** `wait` setup, so the close happens **72-566 mm past
the fruit**; the ACQ lead (p50 2.11 s, cap 4.50) holds 0.75 s and closes at
**3.6-3.9 mm**. **The left arm does not move** (1/17 -> 0/10; its class shifts
14 never-held -> 9 cnp but not its rate - the closed grip class, not an ACQ
effect). One B-only `fruit fell off the line` (a left kiwi at x = 0.176, below the
left's 0.180 m floor - the P38 x-tail, not the knob). **The change**:
`FRUIT_POLICY_TRIGGER_ACQ` resolves **on when `presentation == "direct"`**, an
explicit `=0` restores, and the scripted / hybrid / two-line paths are untouched
(the env-only knob is read in `rl_env.__init__`, verified by a 2-episode smoke
that prints `acq=on` with the env unset). **The re-baseline rule**: every direct
number from here is **ACQ-on**; the pre-P54 direct corpus is **ACQ-off** (35.6 %
pooled / 53.6 % right) and must be labelled so. The root-cause alternative is
named: a default lead **>= 1.17 s** would fix the timing without the ACQ formula
(the lead is a plain env default) - its own pre-registration. Pins: `rl_env.py`
**`5bc084d3`**, `policy/trigger.py` `b09d3cb2` unchanged; no `configs/` change;
evidence `logs/p54/{PREREG,P54_RESULTS}.md`, `p1/`, `flip_smoke.log`.

**P55/P56 (2026-10-28, `logs/p54/`, `logs/p56/`; both **default off**, nothing
adopted): the direct line's supply is continuous **once fed**, and the multi-pick
episode buys 2.7 % of a pick - because the 30-tick feed round it removes is
**load-bearing for the supply**. The owner's "the fruit comes in waves" is
structural: the direct env's only `spawner.update` site was the reset's
selection loop, so the supply was built at `reset` and frozen - the belt is
**not** rebuilt (`create_pool`/`prime` are `__init__`-only) and it is **already
stocked** at selection (farthest-upstream `y` = **0.491-0.675 m against
`spawn_y` 0.68 = 72-99 %**), so the wave is the **episode boundary**. `FRUIT_DIRECT_FEED=1`
(P55, `rl_env.py`) runs the spawner's schedule every `advance` (+11.1 % wall,
belt stock +11 mm median - it does not buy supply); `FRUIT_DIRECT_CONTINUOUS=<n>`
(P56) is the multi-pick episode (one reset, n picks, the recorder's npz index
increments, the reward/outcome accumulated, `[cont]` rows, `[bed-sel]`/`[grasp]`
now wired into the direct env), raising unless `presentation == "direct"` and
`ablate == "none"`, and **implying** the feeder. The census: the inter-attempt
gap is **exactly 140 ticks = 1.167 s** (30 feed + 3x30 teleport + 20 settle) =
**6.4-6.7 %** of the span, starvation 0/11, and the mode's sim ceiling is
**2.97-4.45 %** of a pick (arm switch 55-64 %); the larger wait is the
**arrival** (2.07-2.13 s = 13.5-14.4 %), which continuity does not touch. The
measured battery (seed 77, A 15 single-pick episodes vs B one 15-pick episode):
gap A **140x14** vs B **[50, 80x9, 110x4] (med 80, max 110)** = **-53.6 ticks
(-0.45 s, 2.7 %)** with **8/14 transitions starved** - the removed feed round is
**supply-load-bearing**: the catch floor **0.399 m** against the queue interlock's
edge `pick_y+0.45` with `FRUIT_QUEUE_MAX=6` leaves a **5 cm** catchable sliver,
so a 15 s pick drains it and the next selection reads `window=0` with
`on_belt=8` (P33's aperture class, direct line). Placed **A 11/15 (2.67/min) vs
B 8/15 (2.00/min)** is a **different branch** (right 10/10 vs 8/9, left 1/5 vs
0/6) and carries no rate claim; P1 FAIL on its max (median at the 80 bar),
P3 FAIL (73.3 % < 90 %, the control itself 80 %), **P6 FAIL as registered** but
the **shipped** line's own start pose is outside the same 0.011 rad bar on
14/15, so the bar - not the mode - is the finding; P4/P5 PASS (no new reason;
15 distinct indices/npz in both stores, `ticks_total == sum`). No-harm:
`--ablate scripted` **44/44 lines byte-identical** across the pre-edit, measured
and final trees; selfcheck PASS. Pins: measured `rl_env.py` **`cfbce71d`**,
final **`1845c2c4`** (docstring-only close-out, reconstructed-and-matched);
`tasks.py` `b6de439c`, `fruits.py` `e81051c1`, `policy/trigger.py` `b09d3cb2`
unchanged; `configs/*` untouched; checkpoint `moe_v13s` `61da390a`. Evidence
`logs/p56/{DESIGN,PREREG,PREREG_A1,CENSUS,P56_RESULTS}.md`, `p0/`, `p2/`.

**P58 (2026-10-28, `logs/p58/`; **one shipped change** - the direct presentation's
supply profile - and nothing else flipped): the shipped direct supply was a
per-episode burst with a timed refresh, and the profile that replaces it is the
**clock pair plus the band interlock at `FRUIT_SUPPLY_BAND_MAX=4`**, all resolved
on for `presentation == "direct"` only, an explicit environment value winning.
Four arms, 3 seeds x 15 picks, the shipped per-pick interface
(`FRUIT_DIRECT_CONTINUOUS` never set): **control** `window` **2.60** (2.57 on the
pooled-with-abort read), `==1` **4/45**, `on_belt` 5, `skipped` **104/107/105**,
starves **0/42** (bought by the reset's re-stock), wall **29.66** s/pick;
**A' (cap 3)** 2.02, 12/45, 9, 41/36/39, **1/42**, 34.07; **A'' (cap 4)**
**2.38**, **9/45**, **11**, **8/4/9**, **0/42**, **35.40**; **A''' (interlock
off)** 2.20, 12/45, 11, **2/0/2**, **5/42 (169/380/170/289/291 - 11.9 %)**,
35.43. The registrations' branches read: **B1 does not fire** (A''' fails E1
*and* E3), **B2 fires** (A''' starves 5/42 against A' 's 1/42 and A''s 0/42),
**B3 is unreached** - so the unit is the triple at **cap 4**, and **cap 3 is a
measured regression** (its cap binds and refuses ~2.5 patch partners per pick).
**Read the two counters together:** `supply_skipped` is *not* the slot-loss
counter on the non-bed path - a depth-capped release re-bases `_next_release` in
`_pump_supply` without incrementing it, so the loss appears as a **starved feed
round** (`sel_gap >= 169`), not a skip; that is exactly A'''s 2/0/2-with-5/42,
its pacing counting the station window `[-0.05,+0.45]` at `queue_max=6` (mostly
past-station bodies, P56's aperture) while A'' paces on the approach band at 4.
**`on_belt` is not a catch metric:** the identity `on_belt = admitted +
below_window` holds on all 45 blocks, and at cap 4 the below-station share is
**6.24/block = 54 % of candidate rows** (control 0.20 = 3.4 %), so `on_belt` 11
must never be read as "11 fruit available"; the catchable read is the `window`
distribution. The control's 2.60 is a **post-reset-burst** instant (one feed per
episode, ~7 stale slots dropped per reset - the timed refresh the owner
rejected), so it is quoted as the rejected baseline, never as the composition
bar. **Wall:** +19.3 % (29.66 -> 35.40 s/pick) at a **flat sim span** (1827 ->
1824 ticks/pick), i.e. 0.01623 -> 0.01941 s/tick with 6 -> 12 live bodies - a
harness cost, reported, never gated and never attributed to the policy (P55
measured the feeder alone at +11.1 %; P33 phase A the body physics at +24 % for
21 vs 6.6). **`FRUIT_DIRECT_CONTINUOUS` must not be defaulted:** it is a
run-length parameter (it rescales `--episodes` in `110/121/136`) and it
corrupted the printed summary (`[rl] rollout success 0/1` on a 10-placed run -
parsed by `113_rl_report.py:41` and `129_rtc_report.py:34`); it is
`--continuous N`, opt-in, and the summary is pick-level in that mode.
**Re-baseline:** every direct number before P58 is a **pre-profile (burst)
number** - `FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0
FRUIT_DIRECT_FEED=0` restores it, composed with `FRUIT_ARM_PARK=ready`
(pre-P43) and `FRUIT_POLICY_TRIGGER_ACQ=0` (pre-P54). No motion reference moved
and none is re-recorded: the scripted path never constructs `SortingRLEnv`, so
`accept.sh`'s `fingerprint: matches` is an **import guard** (its `[fruit]`
stream is 377/377 identical to `logs/p41/p2/accept_profile.log`), and the hybrid
canary is **out of reach of** this profile, not untested on it:
`_resolve_supply_profile` is `SortingRLEnv`-only (`rl_env.py:2259`) and
`60_eval_policy.py` builds its own `FruitSpawner` (`:142`) and
`PickAndPlaceTask` (`:238`) with no profile kwargs, so they fall back to the raw
reads whose defaults are interlock `0` / cap `3` (`fruits.py:951-960`) and
`FRUIT_FEED_CADENCE=0` (`tasks.py:1150-1154`); `FRUIT_DIRECT_FEED` has **no
fallback outside `rl_env`**, and `accept_policy.sh:80` fixes
`FRUIT_SUPPLY_SCATTER=0`. Every canary number, before and after P58, is the
**pre-v9 fixed supply** - the re-baseline statement owed for `moe_v12` is
**"no path"**. Not covered: `BAND_MAX` 6 (`5` and
`FRUIT_SUPPLY_TARGET_FROM=0.40` are measured and rejected, P59 P2/P3), the
two-line (its own `feed_pump`; `_feed_scope`
excludes it), the handoff presentation, and any store recorded under the
profile. Pins: `rl_env.py` **`6d7cb329`** (*the file P58 shipped*; P59 gate 1
then moved it to **`1b1e5cdf`** with a provenance-only edit, `be5e41c` - row
provenance + `target_from` in the manifest, the shipped path byte-unchanged),
`tasks.py` **`8ad8ddc8`**,
`fruits.py` **`c7461d41`**, `scripts/230_p58_supply_selftest.py`; `configs/*`
untouched (`8a399626` / `2246f83c` both stand); checkpoint `moe_v13s`
`61da390a`. Evidence
`logs/p58/{PREREG,PREREG_A_APRIME,PREREG_A_APRIME2,PREREG_A_APRIME3,A_RESULTS,A_APRIME_RESULTS,A_APRIME2_RESULTS,A_APRIME3_RESULTS,P58_RESULTS}.md`,
`A{2,3}_report.txt`, `p1/`, `p3a/`, `p3b/`, `p3c/`, `v_*.log`; WORKLOG "P58".

**P59 phase 2 (2026-10-28, `logs/p59/p2/`; **no shipped change** - the
catch-margin arms both fail E1 and the bar is not adjudicable, so the lane closes
as **non-binding** rather than as a loss).** With the shipped profile as the
control (`window` **2.378**, `==1` 9/45), **A (`FRUIT_SUPPLY_BAND_MAX=5`)** reads
**2.533**, `==1` **4/45** (**non-worse in 3/3 seeds against the cross-tree P58 phase-3b cell A2, 2/3 against P59 phase 3's same-tree control** - on seed 101 the control draws **0/15** `window==1` to cap 5's 2/15; per-seed sums 39/39/36 vs A2's 36/39/32, ties-dropped p = 0.25, pooled p = 0.50) and
**B (`FRUIT_SUPPLY_TARGET_FROM=0.40`)** 2.267, 10/45; both have **0/42 starved
rounds**. E1's `2.57` bar is the **pre-P58 burst** cell pooled over **51** blocks
- it includes the 5-pick aborted run while every other cell is 45 (same foot:
**2.600**) - so it matches no row, and A's mean 95 % CI is **[2.282, 2.784]**
(two arms need |delta| >= 0.50 to separate at n=45): **no depth mean ranks the
arms**. What decides it is that **no behavioural invariant moves** - `window==0` 0/45
and starves 0/42 in all four cells, `sel_gap` the **same support and total**
(`{139,140,141}` x 42 - one ~140-tick gap split by the 1-tick print rounding; the
*multiset* equality {139x8, 140x25, 141x9} holds only against the cross-tree A2
cell) - and that **the counters which do move sit at the same-configuration
cell-to-cell spread, so none is attributable to the cap**: `skipped` **21 = 21
against A2 but 24 vs 21 against the same-tree control**, exactly the 3 the two
cap-4 cells differ by; `placed` 26 vs 27, *less* than the cap-4 cells' own 26 vs
28; wall 34.49 vs 35.35 s/pick (inside the live-body confound). **cap 4 stays.** **`TARGET_FROM=0.40` is rejected mechanically**: `window` counts
only `usable`/`chosen` (`tasks.py:5515`), so its "dead sliver" rationale targeted
a re-derived occupancy, and on the real counter it reads 2.244 vs 2.711 while
`below catch floor` **rises 2.31 -> 2.82/block** - it feeds the sliver it meant
to delete (its `skipped` 8 vs 21 at zero starvation is the recorded trade).
**Reopening** needs a **same-tree 45-block control** (this registration's named
control does not exist - phase 1 never ran one; the substitute was the cross-tree
P58 phase-3b cell, `rl_env` `ddcb7816` vs `1b1e5cdf`) **and a behavioural
endpoint**, not a depth mean; cap 6 is predicted flat by the saturated
dose-response and the 0.399 m catch floor. Artifact: `logs/p59/p2_report.py`
exits **0** (the arm check matches the `[supply] direct profile` row) ->
`p2_report.txt`. Pins unchanged (`rl_env.py` `1b1e5cdf` / `tasks.py` `8ad8ddc8` /
`fruits.py` `c7461d41`); no `configs/` change. Evidence
`logs/p59/{PREREG_P2,P2_RESULTS}.md`, `p2/`, `p2_report.{py,txt}`; WORKLOG
"P59 P2".

**P59 phase 3 (2026-10-29, `logs/p59/p3/`; **no shipped default change** - and the
same-tree control this paragraph's P2 section names does **not** reopen the cap).**
The control now exists **on cap 5's own tree** (`logs/p59/p3/header.txt` matches
`logs/p59/p2/header.txt` on **14/14** pins, `git diff ee522c1..HEAD -- src configs
scripts` empty): 45 `[bed-sel]` blocks, `window` mean **2.311** (2.07/2.40/2.47),
`==1` **8/45**, `==0` **0/45**, starved **0/42**, `skipped` **24** (7/6/11),
`on_belt` 11.24, wall **34.49 s/pick**, placed **26/45 = 57.8 %** (right
**24/25**, left **2/20**; **17 of the 19 failures are the left `cnp`** class of
`logs/p42/SIM_LIMIT.md`, which the P43 park removes on the right and cannot touch
on the left). On that foot **cap 5 reads 2.533** - **+0.222 against the 0.371 a
95 % separation of two 45-block arms needs** (overlapping CIs [2.041, 2.581] /
[2.280, 2.787]), so it **does not separate**; `==1` 4/45 (Fisher p = 0.353),
0/42 starves. The two cap-4 cells' own spread is **0.067** (2.311 same-tree vs
2.378 cross-tree - the same configuration, **four pins apart**) = **30 % of the
arm effect: a corroborating floor, not the reason the delta fails** (the
threshold is). **The behavioural endpoint still does not differ, and now cannot**:
`window==0` 0/45 = 0/45, `window>=1` 45/45 = 45/45, starved 0/42 = 0/42 and
`sel_gap` the **same support and total** (`{139,140,141}` x 42, max 141 < the
169-tick starve threshold) are all **saturated**, so **no cap 3-6 can satisfy the
reopening criterion** - **cap 6 is retired, not "predicted flat"**. The counters
that do move sit at the same-configuration cell-to-cell spread and attribute to
nothing: `skipped` **24 vs 21** is the same 3 the two cap-4 cells differ by,
`placed` **26 vs 27** is *less* than the cap-4 cells' own 26 vs 28, and `on_belt`
11.24 vs 11.82 is a body count, not a catch metric. **Two phase-2 readings are
downgraded**: "non-worse in 3/3 seeds" is **2/3** against this control (seed 101
draws 0/15 `window==1` to cap 5's 2/15) and "`sel_gap` the identical multiset"
held only against A2 (this control reads `{139:4, 140:32, 141:6}` vs cap 5's
`{139:8, 140:25, 141:9}` - the same **support**, not the same counts). **The
post-profile direct number is 26/45 = 57.8 %** (11/6/9 per seed - a **branch, not
a rate**: the loop conditions on rendered frames) and it is the **post-profile
"pre"** every later direct comparison starts from. Phase 1's four checks are PASS
(`logs/p59/DEMO.md`) and its film **stands** (no cap default moved, so
`PREREG_P2` rule 5 was not triggered). Artifact: `logs/p59/p3_report.py` exits
**0** - it asserts every arm's `[supply] direct profile` row before reading and
the `on_belt` identity on 45/45 blocks -> `p3_report.txt`. Pins: `rl_env.py`
**`1b1e5cdf`**, `tasks.py` `8ad8ddc8`, `fruits.py` `c7461d41`; `configs/*`
untouched, **no reference re-recorded**; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p59/{P3_RESULTS.md,p3/,p3_report.{py,txt},run_p3.sh}`; WORKLOG "P59 P3".

**P60 (2026-10-29, `logs/p60/`; offline + one measurement cell, **no shipped change,
no new lever**): the left-arm deficit is the **closed loaded-slide class at a higher
rate** - not a seat, an occlusion, a trigger object or the lateral offset.** 180
episodes across four post-P58 corpora (two are P59 supply arms, one sits four pins
apart; the class share reproduces in each, left cnp 79-93 % of attempts vs right
0-4 %) read **left 7 placed / 58 carried-not-placed / 4 never-held (n=69)** against
**right 103 / 2 / 6 (n=111)**, and it is not one species (left kiwi 4/25 vs right
kiwi 4/4). The payload-absence proxy is sound: the `place low` row (printed only
when the fingertip floor binds, `tasks.py:12346`; `need` read 82-144 mm on all 110
placed) is present on **0/58 cnps vs 110/110 placed**, p = 6.7e-13; only **5/58**
cnps carry positional evidence (`[bed-fall] held=True`: x ~ 0.00 +- 0.05,
y = -0.15..-0.42, the source-belt side, not the +y bin at `(0.43, +0.50)` - a
feed-tick snapshot, so quote the direction). **The `FRUIT_CARRY_DIAG=1` cell
settles what the census could not**: **19/19** of the left's cnps are
**`seated_then_slid`** on their first escaping leg (always `grasp_lift`) -
`onset_row` p50 **104/160**, `force@onset` p50 **10.06 N [2.44-22.58]** (a one-tick
sample), `contacts@onset` 1 (14) / 2 (5), `clean_slip` p50 **171 mm**,
`force_min = 0.00` + `loss_row` on **17/19**, **`never_seated` 0/19**, and
threshold-insensitive (19/19 at 1 and 2 N, 18/19 at 3 and 5). It is not the offset:
**4 of the 19 sit inside 66 mm**, and the cell's one left placement is at
**|dx| = 117 mm** - outside the "ceiling" the census's n = 7 suggested. The
scripted left reads the same (24/24 lift rows `seated_then_slid`, 4/4 escapes at
onset 93-149, 7.68-18.19 N; its one placement a 20 mm transient, left lane 1/5)
and P43's direct left is 38/38 (context: different supply profile) - so
**`logs/p42/SIM_LIMIT.md`'s closure transfers and "seat it better" stays closed**.
**Read `[carry]` rows by leg**: a `place0` row's `contacts@onset = 0` is the
downstream view of a payload already gone (18/19 here), never the seat. **The
right-arm occluder is closed at 0.000** (the inactive right at `ready` covers 0.000
of a 58 mm disc across the delivered band, sits at the floor of the 53-pose sweep,
and the scorer reproduces P35 to the rounding), so no right park vector exists or is
wanted (`configs/arm_parks.json` untouched). **The delivered x overlaps** (p50
0.274 vs 0.295 m; `x >= 0.30` 28/69 vs 51/111, p = 0.54; the fire-time jaw
reference agrees to 7 mm), so the arm is not at a different part of the band.
**Nothing decouples arm from lane from grade** (`rl_env.py:2516`: grade A -> bin 0
-> left) and **the direct left's signature is the scripted left's**, so the class is
not an interface artefact; why the left reaches it at **47x** the right's rate on the
same pad asset is **not attributable on this interface** (`rl_env.py:2516`:
arm = grade = lane); P61 measures *where* the payload goes - out along the finger
axis, off the distal lip (`logs/p61/P2_RESULTS.md`). **No lever is left unspent**: the record's one
direct carried-class lever, `FRUIT_CLOSE_LOAD_RATE` (R11-B, default off), re-read
**by arm** in its own batch converts the **right** (cnps 28 -> 5) and not the left
(**20 -> 22**, placed 2/24 vs 2/27, p = 1.0) - pre-P41 and pre-park, i.e. exactly
the arm P43's park already fixed. The left's own `grasp` reset pose covers a 58 mm
disc on the decision band (mean **0.592**; fully hidden over along +0.18..+0.28, the
last ~0.8 s of belt travel before the fire) while the right's covers 0.000 -
recorded **open, no measured pathway** (the trigger is geometry-only, the close is
scripted, and the left's pre-close pad error is *better* centred). F3 fired formally
(a 1-2 episode difference against the P59-p3 control, recorded as
instrumentation-or-branch; P4's note keys are the control's) and the diag's own
`guard/events/holds/reseat/relief` counters are 0 on **88/88** rows. Pins:
`rl_env.py` `1b1e5cdf`, `tasks.py` `8ad8ddc8`, `fruits.py` `c7461d41`; `configs/*`
untouched; ckpt `moe_v13s` `61da390a`; `FRUIT_CARRY_DIAG` default off. Evidence
`logs/p60/**`; WORKLOG "P60".

**P61 (2026-10-29, `logs/p61/`; default off, **nothing adopted**): the left's
payload leaves **out along the finger axis, off the pads' distal lip** - not along
the belt - and the follow-up the brief named is a **commanded constant**. The
default-off `[carry]` field `slip_xyz=(x,y,z)mm` (`tasks.py` **`9a5e0459`**, the
payload-minus-pads displacement **at the running maximum**, leg (TCP) frame,
reporting-only under `FRUIT_CARRY_DIAG`, pinned by `scripts/231_p61_slip_selftest.py`
`202b40c7`) holds its identity on **88/88** rows, max `abs(|slip_xyz| -
clean_slip_max)` **0.072 mm** against the print's **0.137 mm** bound; the *frame*
is carried **not** by that identity (a rotation preserves the norm) but by the
held-payload corpus - **right `grasp_lift` 25/26 legs <= 2.3 mm** against the
code's measured 34-88 mm pre/post-step artifact - and by P42's attitude-free
`[seat] drift`, which agrees with the mapped world vector on all three signs. The
cell (3 seeds x 15 picks, `moe_v13s` `61da390a`, the shipped direct profile, no
wedge) reads **left n = 14 in-hand slides**: leg-frame mean unit **(-0.351,
+0.240, +0.905)** = **25.2 deg from the tool axis**, 76.1 deg from the
jaw-opening axis, **48.9 deg from belt -y** (a pure drag's triple is (+0.034,
+0.858, +0.513)); world mean **(+0.623, -0.658, -0.422)** with **belt -y the
largest single component (0.658), y < 0 on 14/14**, but **+x 0.623 and -z 0.422
are predicted by no registered hypothesis** - a **downward, distal, cross-belt
walk**, and only the tool-axis half is **frame-free** (leg z *is* the finger axis
by construction; the world split is a `grasp_quaternion` approximation whose
threat is measured - P42's `tilt` reaches **38.2 deg** on an escape leg against
the 25.2 deg the reading uses). **The motion candidate is refuted** (achieved
`|v|max` **0.987x**, the 1.637x `|a|max` entirely on the loss tick). **The 47x is
not attributable on this interface**: `rl_env.py:2516` makes `active = left if
grade == "A"`, so **arm = grade = lane**; the contrast is unmeasurable on
*escapes* (**right 1 in 27**) but complete on *magnitudes* (**left 18/18 legs >=
11.3 mm vs right 25/26 <= 2.3 mm, zero overlap**), and that one right leg is
**sign-opposite** (world-y **+224.8** upstream, leg y **-0.404**) to what a belt
drag (+0.858) requires - the observation a belt-drag mechanism cannot produce.
**The named next instrument is already measured and is a constant**: the
along-tool seat is `_pad_standoff(True)` = `FRUIT_FINGER_LEN` 0.060 + `PAD_LIFT`
0.010 = **70.0 mm for both arms and every fruit**, P42's `[seat] tool=` reads
**-69.3..-71.7 mm** without separating escape from placed, and both levers that
move it (`FRUIT_GRIP_PLANE_DROP` D2a 4/8 mm; `..._PAD_LIFT_FRAC` 0.15) are
**measured negative** - so the seat family closes on the direction side too and
**no batch was spent on it**. The tactile carries no contact geometry
(`normal_force`/`contact_count`/per-link scalars only), so a contact-patch read is
not buildable. Refs untouched (`8a399626` / `2246f83c`), `configs/*` untouched,
`selfcheck.sh` PASS. Evidence `logs/p61/{PREREG,PREREG_AMENDMENTS,P2_RESULTS}.md`,
`p2_report.{py,txt}`, `p2/`; WORKLOG "P61".

**P62 (2026-10-29, `logs/p62/`; default off, **nothing adopted**): the left is
**already commanded the top-down attitude** - the gap is that it cannot **hold**
it, and the resulting 26-29 deg tilt *is* the belt-aligned projection that feeds
the slip.** Phase 1 computed the attitude family from
`configs/waypoints_oriented.json` (`q[w,x,y,z]` order verified through
`_grasp_quat` -> `hold_quaternion` -> `quaternion_error`): the tool axis is
**(+0.8543, -0.5132, -0.0819)** with a **belt (-y) projection of +0.5132**, and
re-projecting P61's measured slip gives **0.9045** against its published
**0.905** - the same frame. **The world-z yaw family is infeasible, monotonically
measured**: yaw +15.5/21/31/46.5/62 deg gives projections 0.266/0.161/**0.000**/
-0.266/-0.513 against IK residuals **10.6/13.6/19.9/48.9/118.0 mm**, j2 margins
0.182 -> 0.001 rad, and pad-to-belt clearance **+20.2 -> +3.0 -> -14.2 mm** - i.e.
the left's station reach is **azimuth-limited**, so no yaw removes the projection
without removing the station (the same constraint `motion.py` records from the
other side). **Rolls about the tool axis cannot change it** (a rotation fixes its
own axis: delta 0.0e+00). The one attitude that reaches projection **0.000** *and*
solves is the harness **T0** (`[+0.0, -0.7071, +0.7071, +0.0]`, fingers straight
down, jaws 90 deg across the belt): **2/3** solves at the control's own residual
(**6.0/5.8** vs 5.9/5.7 mm), a **0.8 deg** attitude error, **+15..26 mm more** pad
clearance, and **100.7 deg away from the right's** attitude - but with a j3 margin
of **+0.007 rad** and **32.8 mm** at the x = 0.398 cliff (control 8.3).
**Phase 2 then found the knob is a no-op: `configs/waypoints.json`'s left grasp is
already `mirror_across_xz(top_down_quaternion("x"))` - bit-identical to T0 - and
`_run_impl` discards `_grasp_quat` before the descent (the OpenArm hand skips the
only `solve_to` that reads it)**, so the armed override prints `file_same=1
hold_same=1` and moves the achieved belt projection by **-0.0018 / +0.0001**
against the pre-registered 0.05 gate (the right's own noise floor is **0.0675 /
0.0174**, 37x/174x larger). **The finding that matters**: the left is *commanded*
T0 but **achieves 26.3-28.7 deg of tilt (+0.32..+0.36 belt projection)** on every
carry leg, so the residual is **the attitude the arm can hold at this station, not
the attitude it is told to hold** - which is the mechanism P61 measured and the
owner's hypothesis confirmed. The remaining levers are the **re-solved grasp seed**
(T0 solves from the shipped seed, j3 +0.007 rad) and the **hold stiffness**, each
needing its own pre-registration; the commanded-attitude family is exhausted. The
scripted line is untouched by construction and **proven**: `accept.sh` with all
knobs unset is **377/377 identical** to `logs/p41/p2/accept_profile.log` +
`fingerprint: matches` (6/10, the recorded branch). Pins: `tasks.py` **`fe11910a`**,
`rl_env.py` **`921972a3`**, `scripts/232_p62_grasp_selftest.py` **`e1f86725`**;
`configs/*` untouched (`8a399626` / `2246f83c` / `0ea08ebb` / `d81c6f1c`), no
reference re-recorded; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p62/{CANDIDATES.md,IK_PROBE.txt,PREREG_P2.md,P2_RESULTS.md,p2/}`; WORKLOG
"P62".

**P63 (2026-10-29, `logs/p63/`; default off, **nothing adopted**): the 26-29 deg is
an **arm-common hold/IK residual**, and the **arm-specific part is its azimuth -
along the belt on the left, across it on the right.** The default-off `[carry]`
field `hold_drift=<deg>` (`tasks.py` **`1d27566c`**, `2*acos(|dot(hold_quaternion,
tcp_quat)|)`, pinned by `scripts/233_p63_attitude_selftest.py`) reads on **87/87**
rows (0/45 `grasp_lift` legs are `(no-hold)`; the 42 `(no-hold)` rows are exactly
the **place** legs). The cell (3 seeds x 15, both arms): the left's **failing** legs
carry a median drift of **24.6 deg** (n = 11, 22.4-29.4) while the command is T0
(projection **0.0000**, verified three ways, the independent `[attitude] tilt`
agreeing to <= 4.6 deg on 9/9 legs), so **the command is right and the arm cannot
hold it**; the command path is **closed by construction** (`tasks.py:3488` is gated
on `FRUIT_CARRY_HOLD_QUAT`, unset here). **But the magnitude does not split the
class**: the right places **29/30** `grasp_lift` legs at a median drift of **25.8
deg** (20.9-52.3), the same distribution as the left's failing legs (Spearman
-0.36 left / +0.20 right / -0.15 pooled). **What is arm-specific is the azimuth,
and it is sign-consistent**: the left's achieved tool axis is **downstream on 3/3**
legs (tool_y -0.326..-0.366, **77 % of the tilt on the belt axis**) against the
right's **0/6** (3 upstream, 3 across; median share 0.23) - so the ~25 deg lands
**along** the belt on the left, which is the +/-0.513 the P61 slip was projected
onto. **The chain is closed at every link**: command T0 -> an arm-common ~25 deg
tracking residual -> belt-aligned azimuth on the left -> the drag walks the payload
out along the tool axis (P61) -> the `cnp` class at 47x. **The lever this hands on
is a pre-compensated command** (command T0 rotated by the residual's inverse so the
*achieved* attitude sits at projection ~0, with no arm/kinematics change), and it
needs its own pre-registration. Pins: `tasks.py` **`1d27566c`**, `rl_env.py`
(metadata-only `TASKS_MD5` follow), `scripts/233_p63_attitude_selftest.py`;
`configs/*` untouched, no reference re-recorded. Evidence
`logs/p63/{PREREG.md,P2_RESULTS.md,p2_report.{py,txt},p2/}`; WORKLOG "P63".

**P64 (2026-10-29, `logs/p64/`; default off, **nothing adopted**; **its own
headline was retracted by its screen**): the pre-compensated command was
**inadmissible**, and the corrected finding is that **the lift - not the station -
creates the drift.** The live site is real and it is **`arm.hold_quaternion`**
(not P62's inert `_grasp_quat`): the never-stop catch installs the top-down hold
before the hover and `grasp_lift` **inherits** it (the `_carry` clear is `name !=
"grasp_lift"`), so writing it at the lift's start moves the achieved attitude. The
drift derived from 7 left `grasp_lift` legs is `axis (-0.7564, -0.6541, 0)`,
`angle 26.798 deg`; commanding its inverse (`q_cmd = [+0.01675, -0.68786,
+0.68786, +0.23113]`, command projection **-0.3410**) moved the achieved projection
the wrong way (+0.35 -> **+0.673 median, tilt 47.0 deg**, `hold_drift` 54.9-107.4,
the loaded slide starting **60 ticks vs the control's 104.5**, left **1/16** vs
2/15). **The screen then showed the command was never admissible**: P62's own probe
reads `q_cmd` at **0/3 solves, residual 42.6-72.9 mm (7-12x tolerance), joint
margin 0.000/-0.000 at j6-j7** and a **28.9 mm pad-height difference across the 98 mm
jaw** (`jaw_z = +0.2949`) - so *"the response is inverted"* is an **inadmissible
command, not a mechanism**, and that reading is withdrawn. The two reachable
directions were screened instead: **`q_drift (x) q_T0` (+0.341) solves 3/3**
(better conditioned than T0's 2/3 at `+0.007 @j3`) but carries the same 28.2-28.6 mm
jaw twist and **is the attitude already achieved**; the `waypoints_oriented` left
quaternion (+0.513) is **exactly the shipped control**. **The new by-product is the
finding that matters**: at the station the static solve tracks its command to
**<= 1 deg at both projection 0 (T0: 0.77 deg) and +0.35 (`q_drift`: 0.78-0.93
deg)**, while the failing **carry** legs read **24.6 deg** - so **the drift is
created in the lift**, not by the station's reach, and `hold_quaternion`
pre-compensation has **no station-level target in either sign**. The two-point
"never" claim is withdrawn with it (the slope was not identifiable, P64's own
prereg §6). What is *not* yet measured: why the lift drifts when the station
tracks (`control.py:423` `max_step` and `:494`'s hard joint clip are the named
suspects), and the pads' line (the jaw axis was never printed; `tasks.py:3237`'s
`rot[:,1]` is free). Prior citations corrected: `logs/p58/GEOMETRY.md` prices the
**station y** for the *catchable-segment* question (R10), **not** a general station
NO-GO. Pins: `tasks.py` **`7a8a163a`**, `rl_env.py` **`7c137553`**,
`scripts/234_p64_precomp_selftest.py`; `configs/*` untouched, no reference
re-recorded. Evidence `logs/p64/{SCREEN.md,ik_screen.*,PREREG_P2.md,P2_RESULTS.md,p1/,p2/}`;
WORKLOG "P64".

**P65 (2026-10-29, `logs/p65/`; default off, **nothing adopted**): the two IK
suspects for the lift's ~25 deg drift are **measured out**, and the drift's cause
is **still open**. The instrument (`q_margin=<rad>@jN/t<tick>`,
`q_cmd_margin=`, `q_step_max=`, `jaw_z=`, `drift_on=` on the `[carry]` row,
reporting-only under `FRUIT_CARRY_DIAG`, 44/44 `grasp_lift` legs carrying all five
fields, pinned by `scripts/235_p65_lift_selftest.py`). **`max_step` is refuted by
measurement**: the largest per-tick command step on any leg is **0.0300 rad**
against the **0.5 rad** `FRUIT_IK_MAX_STEP` cap (**6 %**, never binding). **The
joint-limit clip is refuted by discrimination**: the measured margin is **0.000 rad
on 86/86 legs** (the left's 20 lifts, the right's 24 lifts **and all 42 place
legs**), so "a joint at its limit" is a **standing condition of this workspace**,
not a lift-specific cause - and on the left's 18 failing legs the drift's onset
(median tick **106 of ~160, 65 %** of the leg) **precedes** the tick of the leg's
smallest margin by a median of **-41 ticks** (inside the registered +-20 on only
3/18). **The pads' line points the other way**: at the lift's first tick both arms
are flat (|jaw_z| 0.0084 left / 0.0104 right) and over the leg the **right** twists
more (max 0.371 vs the left's 0.239) yet places **23/24** - so the left does not
tip its pads more. **What the phase adds is a discrimination, not a cause**: the
joint saturation is real but arm-common and pre-dates the drift, so the ~25 deg
remains **unexplained** at the code level measured so far. The class counts are the
P63 shape at a moved branch (left 1/18/1, right 23/0/2 against P63's 2/11/2 and
29/0/1; attempt split 20/25 vs 15/30, so F3 = instrumentation-or-branch). Named and
**not** measured: the payload-induced wrist deflection (a load path, not a command),
`ik_step`'s `gain` term, and how often the hold is re-applied. Pins:
`tasks.py` **`309e5a38`**, `rl_env.py` **`a10e753a`** (`TASKS_MD5` follow),
`scripts/235_p65_lift_selftest.py`; `control.py`
**untouched**, `configs/*` untouched, no reference re-recorded. Evidence
`logs/p65/{PREREG.md,P2_RESULTS.md,p2_report.{py,txt},p2/}`; WORKLOG "P65".

**P66 (2026-10-30, `logs/p66/`; **nothing adopted - and a flip that the phase-3
lane made early was REVERTED** when its gate failed): the left's 25 deg carry
rotation is a **height** problem, and lowering the lift's end fixes most of the
left.** `FRUIT_LIFT_DZ` (`direct` + `left` only; it shifts the `grasp_lift`
target height above the shipped `belt_top + 0.28` base, `+0.08` = the shipped
0.36) **defaults to `+0.08`, i.e. the shipped lift**: the phase-3 lane had flipped
the default to the 0.20 rung (`-0.08`) as part of its adoption package, and P66 P4
**reverted it** (`LIFT_DZ_DIRECT_DEFAULT` back to `+0.08`, the `236` pins updated)
because gate (a) below **failed** - the rung is opt-in. Measured (explicit rungs,
so the table is unaffected by the flip) moves the left's `drift_end` **23.8-25.7 -> 9.7 ->
0.7 deg** over the ladder 0.36/0.28/0.20 and the left's placed count
**1/34 -> 1/18 -> 10/16** (phase 2, 3 seeds interleaved); the **N=5** rung batch
(`logs/p66/p3/`, seeds 77/101/202/303/404) reads **control 0/25 (0 %), C24 12/30
(40.0 %), C20 14/25 (56.0 %)** with `drift_end` **25.1 / 3.4 / 0.7** - the control
is **0 in every seed** and each treatment beats it in **5/5** (the run-level sign
test's ceiling, p = 0.031; Fisher ~2e-4 for C24), while **the two rungs are not
separable** (40.0 vs 56.0 %, Fisher p ~ 0.28) so **0.24 is the economical one**
(same class, half the place cost) and 0.20 reads the deeper mediator.
**The mechanism is settled by three independent instruments**: the mediator has
zero overlap; the achieved position error collapses with it (`res_end` 80.6 ->
33.7 -> 13.3 mm); and the **static sweep** (`logs/p66/STATION_SWEEP.md`) predicts
it with no payload, no controller and no profile - `T0` at `belt_top + 0.36` is
**24.27-60.00 deg off with `margin +0.000` on 25/25 cells** (0/75 of the delivered
band passes the 0.05 rad margin clause at any x/y/depth, while the shipped `C0`
passes 31/75), so P63's live 24.6 deg **is** the static number and the drift was
never a controller defect. **Gate (a) is measured and FAILED; gate (b) is structural but not flat**:
(a) the **place-transit clearance: MEASURED AND FAILED at the +33 mm floor.**
With the reduction fixed to the rail-crossing form (`clr_x` at the crossing,
`clr_win` over the transfer window; `logs/p66/P4_RESULTS.md`, one seed, 2 runs,
`p4_report.py --check` PASS), the **0.20 m rung enters the rail's footprint level
with the rail top (window minimum `+0 mm`, tick 333) and crosses the centreline at
`+5 mm`** against the shipped rung's own left leg at **`+30 / +29 mm`** - **no held
leg goes negative in either arm (0/16)**, so there is **no contact**, but the rung
**spends 25 of the 30 mm** the shipped lift had. **The rung ladder cannot buy it
back**: the crossing sits at 82.5 % of the place leg's `y` span, so
`dz_crossing = 0.175 x dz_lift` and the 0.24 rung buys **+7 mm**, not +40 - only
the **transfer height** is 1:1 with the crossing, and the lift lever does not touch
it. **The re-shape is therefore named, not guessed**: keep the low lift (the
attitude holds) and re-establish the crossing height on the place leg's first
segment (a transfer-height change, 1:1 with the crossing, its own registration); (b) the **right-arm no-op** is structural (`resolve_lift_dz` emits only
`{"left": dz}`; `lift_dz_for` returns `None` for the right) but reads
**100 / 97.8 / 88.0 %** across the arms, i.e. inside its own branch spread
(88.9-95.8 % in phase 2) rather than cleanly flat. **The residual is not the
lift**: the remaining left `cnp`s are **place-leg** losses (P66 phase 2: 6/16 at
0.20, `clean_slip` 833-931 mm, tilt 75-91 deg, `tool_y +0.65..+0.70`) - the place
leg reinstates the belt-aligned attitude by reach and the lift's height cannot
touch it, and the **control has no loaded left place legs at all**
(`contacts@onset = 0`), so that class's baseline is the right arm's. **Nothing was
re-recorded** (the knob is direct-scoped; the scripted line never constructs
`SortingRLEnv`, so `configs/motion_reference*.json` `8a399626`/`2246f83c` stand);
**every pre-P66 direct number is a 0.36-lift number and the default IS that
height again** (the rungs are opt-in; compose with `FRUIT_ARM_PARK=ready` for the
pre-P43, `FRUIT_POLICY_TRIGGER_ACQ=0` for the pre-P54 and the P58 burst profile for
the pre-P58 baselines); the hybrid canary has **no path** to the knob. Also
recorded: the **finger-tip identity holds** (`S` 84.902 -> `F1` 80.902 mm =
`4*cos(0)` on all four links, <0.001 mm) but at the descent's vertical fingers it
buys **4.00 mm** of clearance, i.e. 4.4-10 % of the 40-90 mm descent shortfall -
the pad lane stays closed on P39's measurement and on scale; P30-C's 24-45 mm
stays owner-gated. Pins: `tasks.py` **`40e196e8`**, `rl_env.py` **`3fab4733`**,
`scripts/236_p66_lift_selftest.py`; `configs/*` untouched. Evidence
`logs/p66/{STATION_SWEEP.md,COLLIDER_READ.md,P2_RESULTS.md,DEVIATION.md,P3_RESULTS.md,p2/,p3/}`;
WORKLOG "P66".

**P66 P4/P67/P68 (2026-10-30, `logs/p66/p4/`, `logs/p67/`, `logs/p68/`; **nothing
adopted**): the lift-height lever fixes the *carry* class, and **every shippable
form trades it for the place leg's closed class - the two meet, and no net gain
ships today.** The rail-crossing gate is **measured and failed** by the lift-only
form: the 0.20 rung enters the output rail's footprint level with its top
(window min `+0 mm`, t333) and crosses the centreline at **+5 mm** against the
**+33 mm** floor (shipped `+30/+29`; no contact, 0/16 legs negative, but 25 of the
30 mm spent), and **the rung ladder cannot buy it back** (`dz_cross = 0.175 x
dz_lift`; only the transfer height is 1:1). The re-shape (`FRUIT_LIFT_CLIMB`, a
prepended vertical waypoint at the place leg's start; derived `0.18 m` from
`z_cross = transfer - 0.175*(transfer - lift_end - climb)` and re-derived by
`scripts/237_p67_climb_selftest.py`) **clears the crossing** (`+51/+50, +37/+37,
+33/+33, +54/+53, +36/+35`, median +37, worst +33) with the attitude held
(`drift_end` 1.1 deg) - **but drops the payload on 3 of 8 climbed place legs**
(`clean_slip` 0.92-1.00 m, onset 113-152 = the climb's exit; the W8-B loaded
slide, the leg runs with no wrist hold), and `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=1.0`
makes it **worse** (**0/18** against the pair's 3/18; the payload is gone before the
crossing, `clr -216..-218`). The full trade: shipped **0/25** / low lift **14/25**
(crossing +5 mm) / low lift + climb **3/18** (crossing +33..+54) / + the hold
**0/18**. **So the lift's height explains and fixes the carry rotation, and the
place transfer - `SIM_LIMIT.md`'s loaded slide - is what charges for it.** The
remaining levers are the two `SIM_LIMIT.md` sanctions (**a new pad asset** -
P30-C's 24-45 mm stays owner-gated - or **a real-jaw clamp-force anchor**) or a
**workstation/transfer change** (a lower output rail or a shorter transit, both
references re-recorded); **a recollection/retrain is not indicated** (the policy is
not where the loss is). **Nothing was re-recorded** and **nothing is flipped**:
`FRUIT_LIFT_DZ` defaults to `+0.08` (the shipped 0.36; the phase-3 lane's premature
flip to `-0.08` was **reverted** at P4 when gate (a) failed, the `236` pins updated
and a smoke confirming `dz=+0.0800(default) -> belt_top + 0.3600`), and
`FRUIT_LIFT_CLIMB` is default off. Selfcheck PASS; the acceptance is
**6/10 + `fingerprint: matches`** with **377/377** `[fruit]` lines identical to
`logs/p66/p2/accept_noharm.log`. Pins: `tasks.py` **`e5168578`**, `rl_env.py` **`d88c3729`**
(the `TASKS_MD5` follow), `scripts/237_p67_climb_selftest.py`; `configs/*`
untouched. Evidence
`logs/p66/P4_RESULTS.md`, `logs/p67/{RESULTS.md,p67_report.*,A,B,A2,B2_77.log}`,
`logs/p68/{RESULTS.md,pop2/}`; WORKLOG "P66"/"P67"/"P68".

**P69 (2026-10-30/31, `logs/p69/`, default off, **nothing adopted**): the pad-asset
lane closes **by contact geometry**, and the rail-crossing floor - the project's
+33 mm convention - is **measured at `(+7, +14] mm`, so the low lift's crossing is a
real contact on ~40 % of its legs but does not cost the placement (5/5).** Phase A
(the pad asset): the authored boxes go **84.902 -> 80.902 / 60.902 / 49.902 / 39.902
mm** at `0 / -4 / -24 / -35 / -45 mm`, the distal plane rises by
`|delta|*cos(theta)` (identity to **9.7e-7 mm**) and the proximal plane does not
move; **the authorized magnitude cannot grip** - at the shipped aim
(standoff 0.070 m) the plates at -24/-35/-45 sit **+13.5/+24.5/+34.5 mm above the
fruit's equator** and close **without touching any of the 8 pool classes** (closest
+2.6 mm; +0.3 mm even under D2a's -8 mm seat), so the admissible band is
**+3.5..-7.9 mm** (patch intact) / **-13.1 mm** (any contact) and the authorized
magnitudes are **1.8-3.4x past the last that touches**; what a cut would buy is
**descent +24/35/45 mm unconsumed** (the tip already clears by 3.5-24.5 mm and the
residual is a **jaw-plane** 8.1-10.3 mm), **carry +21.8/31.8/40.9 mm = the lip lost
1:1**, and **rail +0.0 mm** (`clr` is a payload clearance), so the whole band is
**4.1-10.9 %** (intact) / **6.0-16.0 %** (any contact) of the 104-276 mm walk; the
one probe is categorical (`C` grasped, lift +0.2894, force 10.00 N; `-24 mm`
lift 0.0000, force 0.00, `sep_end` 32.3 vs 70.6 mm, with `end=8.1 mm` and
`belt_margin=+37.4 mm` identical in both arms) and the **matched pair is a null**
(shorten by `d` and lower the aim by `d` leaves the lip *and* the belt clearance
unchanged, 4/4). Reopen = a **real-jaw clamp-force anchor** or a **new pad asset**,
not another magnitude. Phase B (the workstation) ranks the levers by
crossing-gain: **the inner rail 1.00** (the obstacle moves 1:1), a **place-only
transfer raise 0.825**, a **place `y` shift 0.264**, and **the shipped transfer
lift excluded** (read at both sites, `tasks.py:3269`/`:3308`). **G0 then measured
the floor** (scripted runs, no code): the payload touches at **`clr <= +7 mm`** and
not at **`>= +14`** (15 legs at `>= +14` read **2.6-5.7 m/s2** and 0.0-0.1 mm slip;
5 legs at `-2..+7` read **14.9-32.7 m/s2**, **27-76 mm** of displacement, `sep_end`
97.5-98.3 = the pads at their open stop - **the populations do not overlap, a 2.6x
gap**), so `-1 mm` is a **contact, not a graze** and P66's "non-contacting graze" is
falsified; **the low lift straddles the boundary** (+3..+17 crossing: 3 of 5 legs at
or below the band) - **but 5/5 of its contacting legs still placed.** So the
**cheapest honest package is the low lift + a floor re-signed at the measured
boundary** (0 h, 0 references, 0 stores, the contact accepted and documented on
~40 % of the crossing legs), while a contact-free crossing needs **~+11 mm** of dose
(`FRUIT_OUTPUT_RAIL_HEIGHT 0.05 -> 0.039`, 24 of the 35 mm of lip kept) at a
**binary** blast radius (any rail value moves the scene branch, **both** references
and **every** store) - the 34 mm flush is over-dosed and its flush shelf is the
ledge class's worst case. Nothing adopted; the low lift, the climb and the rail are
all opt-in/default. Pins: `tasks.py` `e5168578`, `conveyor.py` `b0d95a08`, `assets.py`
`61baf52b`, `rl_env.py` `d88c3729`; `configs/motion_reference.json` `8a399626`,
`..._twoline.json` `2246f83c`, `..._patch.json` `7b028049`, `..._twoline_bed.json`
`dcd19758`; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p69/{A_PREREG,B_PREREG,G0_RESULTS}.md`, `tip_geometry.{py,txt}`,
`collider_*.log` + JSONs, `probe_{C,T}.log`, `g0/t0{25,35,45,50,80}.log`; the
delivery page `docs/LEFT_ARM.md` + the README block + the `项目总结报告.md` section.

**P71 (2026-10-31, `logs/p71/`): the adoption package - the output belts' side
rails are gone and the low direct lift is the shipped default; the left's carry
class converts, and the crossing clears the surface that remains (median +35 mm)
while failing the +33 clause *at the rail top* on 0/10 legs, as it must, because
that surface no longer exists.** Two flips, both the measured values:
**`FRUIT_OUTPUT_RAILS` default `both` -> `none`** (`assets.py`; `=both`
restores) and **`FRUIT_LIFT_DZ`'s direct default `+0.08` -> `-0.08`**
(`rl_env.LIFT_DZ_DIRECT_DEFAULT`, i.e. 0.20 m; `=+0.08` restores the 0.36 m):
the rail is **1:1** with the crossing and the height only **0.175:1** and it
costs placements (`logs/p70/RESULTS.md`), while the height is the only measured
fix for the left's 25 deg carry rotation (`logs/p66/P3_RESULTS.md`) - so P66 P4's
reverted rung ships now that its gate's *obstacle* is gone (P67/P68 measured the
re-shape lane closed: the climb clears the crossing and drops 8/16 payloads).
`236`/`238` re-pinned (the rung is the default; the rails' env-read
`default_factory` reads `none`, `=both` restores, an unset config reads exactly
like an explicit `none`), selfcheck PASS.

**The scripted line.** The two arms are same-batch and same-tree and the
**control restores the pre-P71 geometry explicitly** (`RAILS=both`): acceptance
**6/10, 377 `[fruit]` lines, `fingerprint: matches`, and 377/377 byte-identical
to the pre-P71 archive `logs/p66/p2/accept_noharm.log`** - so the tree is inert
with the old scene, and the treatment's move is the flip's. The treatment (the
new default) reads **6/9 = 67 % (one slot starved), 346 `[fruit]` lines** (344 +
two new `output belt rails ... authors 0/2` build prints) with the fingerprint
**moved**: first difference is the print, then a **release y 0.595 -> 0.603 (8
mm)** at stripped line 121, 171/326 lines identical at the same index - the
scene's collider set moving the solver ordering (P30-A's precedent), and every
report-only clearance row shifts by exactly the rail's **+35 mm**. Motion is
identical in both arms (worst `|v|max` 0.1100 against 0.160-0.161, lurch 0.017
against 0.291), the FAIL is the standing rate floor. The **two-line** reads
**8/10 (left 4/5, right 4/5, 9.8 s/attempt) with `190` PASS + `matches`** as the
control, **7/10 (4/5, 3/5, 9.2 s/attempt) with `190` PASS after its re-record**
(the reference moved on legs 3/4/5/7/8/10 by 1-3 ticks); the two are different
attractors (no rate claim) and the ctrl's own tightest place leg reads
**`+32 mm output rail`** against the treat's `+63..+101 mm output belt`.

**The direct line** (the P66 phase-3 cell verbatim, seeds 77/101/202 x 15,
interleaved, `moe_v13s` `61da390a`, `FRUIT_MOTION_REPORT=1` on both arms): the
flip is proven in-log (`dz=-0.0800(default) -> 1.3700 m` vs `+0.0800(explicit) ->
1.5300 m`). **Left placed 4/20 -> 10/17** (one-sided Fisher p = 0.018), **left
loaded-slide legs 15 -> 7** (p = 0.039), overall 26/45 -> 32/45 (p = 0.135);
per seed 2/8->4/5, 2/6->2/6, 0/6->4/6 (2/3 improved, 1 tie). **The right's
placed count is unchanged (22 in both)**, its 3 extra attempts in the treat arm
all `fruit fell off the line` (kiwi 6.3 x2, strawberry 4.0 - never grasped, the
recorded supply tail, already in `logs/p66/p3/C20_77.log`), i.e. a cadence
artefact of the left's extra placements, not a new class. The treat's surviving
6 loaded slides sit at `loss_row` 103-150 (held through the transit, lost in the
place leg) against the control's mostly `loss_row` 1-4 (never seated). **The
crossing, against the surface that remains** (belt top; `logs/p71/p71_report.txt`):
held **left `clr` +14..+50, median +35, 8/10 >= +33** (`clr_win` +10..+45,
median +30.5, 4/10) against the ctrl's **+24..+45, 2/4** at *its* rail top; the **right is
22/22 in both** (+69..+138 vs +36..+58). At the rail top the package reads
**0/10** - the payload passes 35 mm *below* where the rail top was, which is
exactly P66 P4's `+5 / +0` and P70 D0's `+7..+17`, so **the clause as written can
never be met by a lower lift; only the obstacle's removal makes the crossing
physically safe**, and it is: held-leg `|a|max` **0.31-8.69** against G0's
measured contact population **14.9-32.7 m/s²** (max held slip 20.3 mm). The
P70 D0/D1 pair - the **rails isolated** at the low lift, all-A, seed 77 -
reads **6/15 -> 10/15 left placed** and **6 -> 3 loaded slides**. Both motion
references were **re-recorded from this batch's shipped-scenario runs**:
`configs/motion_reference.json` `8a399626` -> **`8952c320`** (from the 6/9
treatment; 9 legs now, so a pre-P71 10-attempt log needs the archive
`logs/p71/motion_reference_single_pre_p71.json`) and
`..._twoline.json` `2246f83c` -> **`eb697f23`** (from the 7/10 run; archive
`logs/p71/motion_reference_twoline_pre_p71.json`); `189_w7a_chain.sh` not run.
**Re-baseline: every pre-P71 number is a `both`-rails + 0.36 m-lift number** -
restore with `FRUIT_OUTPUT_RAILS=both` (all paths) **and** `FRUIT_LIFT_DZ=+0.08`
(direct only), composed with the pre-P43/P54/P58 restores. The **hybrid canary
inherits the rail flip** (it builds its own `SceneConfig`) and **not** the lift
flip (it never constructs `SortingRLEnv`): it was **not re-run** - a smoke owed,
not a measurement made. Residuals: the +33 clause has **no contact boundary in
the new frame** (G0's is at the rail top; the named instrument is a
`clr_edge` sample at `|y| = 0.425`); the ledge class stays **untested, not
zero** (the G2 fixture was again not run, no release in either batch lands in
`0.400-0.425`); the belt height stays 1.35 by P70; the scenes' collider set has
**no manifest field** (the direct lift does), so stores must not be mixed
across P71. Pins: `assets.py` **`e9fd74`**, `rl_env.py` **`cb686f5`**,
`tasks.py` `7c00e5`, `conveyor.py` `fb2c58`; `236` **`e6547e`**, `238`
**`2ccceb`**; ckpt `moe_v13s` `61da390a`. Evidence `logs/p71/RESULTS.md`,
`{header,twoline/,direct/,p71_report.txt,run_p71.sh,accept_diff.py}`; WORKLOG
"P71".

**P72 (2026-10-31, `logs/p72/`; **one** shipped change - the `scene` manifest
block - plus the corner instrument and the canary's owed smoke; no default
moved): the canary is inside its spread, the crossing is
measured at the surface that remains, and the new-frame floor is a
**bracket**.** (1) **The hybrid canary smoke** (`SKIP_SELFCHECK=1
scripts/accept_policy.sh`, the interface of record, `moe_v12`, the pre-v9 fixed
supply) reads **8/10 = 80 % PASS** with **2 grip losses** (`fruit did not follow
the gripper`), 0 grasped-not-placed and **no reason outside the recorded
baseline** - the **top of the 5-8/10 spread**, so one draw, not a rate. It
**does** inherit the rail flip (its build print reads `FRUIT_OUTPUT_RAILS=none
authors 0/2 (inner y=+0.4125 REMOVED)`) and **cannot** see the lift flip (no
`[grasp] lift_dz:`/`[rl] env ready` row); both failures are pick-side grip
losses, upstream of the output line, so **the rail flip is not implicated**.
(2) **`clr_edge`/`clr_edge_min`** on the `[carry]` row (reporting only, same
`FRUIT_CARRY_DIAG` gate, inside `if guard_armed:`, **no new read** - the
`(clearance, where, i)` triple the leg already has): the **first** tick the
payload's `|y|` reaches the output slab's **own** inboard edge and the minimum
over that band, through the existing `_clearance_field`. **The threshold is
0.425 m, not the 0.400 m surface switch**: `_payload_clearance` switches at the
literal 0.40, which is the **removed inner rail's inner face** - the rail box
spanned 0.400..0.425 with its outer face flush with the slab (`assets
output_rail_keep`'s own docstring), so the band 0.400-0.425 is **inboard of the
surface** and the plane charge there is conservative (the `clr_win = -6 mm` leg
that placed with 0.4 mm slip). Derived in `tasks._output_belt_edge_y` =
`|output_belt_y| - size[1]/2`, pinned by the new **`239`** leg (which also
executes the body on stub configs and asserts no rail constant in it) and run by
`selfcheck.sh` as "P72 clr_edge + scene". **Read on one direct run** (seed 77,
15 episodes, the P66/P71 cell verbatim): **`clr_edge` n=10, min +26, median
+77.5, max +109 mm; `clr_edge_min` min +26, median +77.5, max +104; `<= 0` on
0/10**, every value `@obelt`, every held leg's `|a|max` **<= 4.49** (G0's
contact floor is 14.9) and no slip above 0.1 mm. The draw is right-heavy (8
held right / **2 left**, the left being the arm the package targets), the
left's corner sits **+4..+5 mm above its centreline sample** while the right's
is flat, and on the leg P70 and P72 share (ep0: same `clr=+33@t329`, 430 ticks)
P70's hand estimate `edge~+37` reads **+38** measured. (3) **The boundary:
`clr_edge > 0`, and it is a bracket, not a calibrated floor.** With
`output_rail_keep = (False, False)` the rail branch of `_payload_clearance` is
never entered, so the only surface a transit can clip is the slab - its top
plane (1.35) **and** its inboard edge (0.425) - and contact requires the
payload's lowest point below the plane **while over the slab**, i.e.
`clr_edge <= 0`. The record's only sub-zero *plane* sample is P70 D1 ep8's
**`clr = -1 mm @obelt / t247`**, taken 25 mm inboard of the surface, with **no
contact signature** (`|a|max` 0.98, `sep_end` 69.9 mm, slip 0.4 mm) against
G0's measured contact population of **14.9-32.7 m/s²**; the **+33 convention was
calibrated against a raised rail top and has no counterpart surface now**. **No
dose ladder was spent and none can close a gap**: `z_cross = f*z_transfer +
(1-f)*z_lift_end` with `f = 0.825` (0.85 at the edge), the transfer follows the
belt **1:1** while the lift end is anchored to the **main** belt, so
`d clr/d(lift) = +0.175` and `d clr/d(belt top) = -0.175` (0.15 at the edge) -
the lift lever buys 17.5 % of its travel at the crossing and the belt-height
lever spends the 40 mm under-slab audit for +7 mm (P66 P4 / P70, both negative
on the count). (4) **The `scene` provenance block** - `assets.scene_provenance(
cfg, lift_dz=None, lift_dz_defaulted=False)`, pure config arithmetic, the one
builder **both** manifest writers call (the P41 `physics` rule):
`output_rails` + the resolved `rail_keep` pair, `rail_height` / `rail_proud` /
`rail_inset`, `output_belt.{top_z,y,size,inboard_edge_y}`, and
`lift = {dz, defaulted}` on the direct env / **`null`** on a scripted shard (no
lift rung there). Shipped: `none`, proud 0.035, inset 0.015, top 1.35, edge
0.425, `dz.left -0.08 defaulted`. **Metadata only** (nothing reads it; both
callers wrap it in `try/except`); a store **without** the key predates P72
(`arm_park.defaulted`'s convention), and the collector's `write_manifest` was
exercised end-to-end under the simulator python (`manifest_probe.log`:
`none` → both false, `=both` → both true, `lift` null in both), while the direct
env's own manifest from the phase's run carries the block live. **Re-pins the
work forced** (each test's meaning kept): `236`'s tracker-init list / its
`inf` assertions (the line grew `edge_y`), its print-containment check (a
character budget → the file's own `indented_body_contains`), its "one
construction site" count (now scoped to the `PickAndPlaceTask(` call, because
the `scene` call also passes `lift_dz=`), and `238`'s read census, which
**declared** the new consumer `assets.py:scene_provenance`. `rl_env.py`'s
`TASKS_MD5` follows (`7c00e555` -> **`f61323f2`**, metadata only). No `configs/`
edit, no default change, both references untouched (`8952c320` / `eb697f23`),
`selfcheck.sh` PASS. Pins: `tasks.py` **`f61323f2`**, `assets.py`
**`540406fa`**, `rl_env.py` **`92a25c8e`**, `scripts/40_collect_demos.py`
**`86b3d6ba`**, `scripts/239_p72_clr_edge_selftest.py` **`c3027c4f`**; ckpt
`moe_v13s` `61da390a`. Evidence `logs/p72/{RESULTS.md,p72_report.py,
p72_report.txt,p72_scope.py,p72_scope.txt,manifest_probe.py,
manifest_probe.log,canary_rails_none.log,direct/treat_77.log}`; WORKLOG "P72".

**P73 (2026-10-31, `logs/p73/`; default off, **nothing adopted**): the place
transfer's **height is not a lever** on the left's place-leg loaded slide, and the
rotation is **not the actuator** - the hypothesis fails on its own second link and
its first link has the **wrong sign**.** The registered screen
(`PREREG.md` md5 **`81b70bb3`**, pinned before any run) raised
`FRUIT_OPENARM_TRANSFER_LIFT` 0.08 -> 0.14 -> 0.20 (**C / T1 / T2**, the
P66-phase-3 cell verbatim, seed 77, 15 picks, `moe_v13s` `61da390a`, one claim
each; the conditional `SLOW` arm was run because the registered rule B trigger
fired). **On the direct line the knob is place-only on the left**: P71's
`FRUIT_LIFT_DZ` override takes the `grasp_lift` site (`tasks.py:3261-3263`
bypasses the env read), so only `jaw_target("place*")` moves - but the **right's
lift end moves with it** (its `lift_dz_for` is `None`), so the right is read as
"no new class", never as "unchanged". **The class is flat to the leg: 1 / 1 / 1**
loaded slides (1 of 5, 1 of 4, 1 of 5 left place legs; 995 / 983 / 887 mm), with
**`cnp` 2 / 1 / 1** and the acquisition class 2 / 0 / 0. **The mechanism moves
monotonically the other way**: the achieved place-leg rotation `tilt_end`
**78.7 -> 93.8 -> 105.2 deg** (+26.5) and `t45` **313 -> 303 -> 299** ticks, so a
higher transfer *demands more* wrist rotation, not less (falsifier **A does not
fire**); with the rotation moving 26.5 deg and the count flat, falsifier **B
fires**. **The causal order is visibly wrong**: in **8 of 8** payload losses the
onset row is **before** the leg's 45-deg crossing (onsets 4, 133, 103, 136, 3, 4,
157, 265 against `t45` 313-561) - the payload leaves at **1-41 %** of the leg at a
tilt **below 45 deg**, while the 90-105 deg sweep happens at **73-79 %**, i.e.
*after* the failure. **Not inertial either**: the slowed place leg
(`FRUIT_SPEED_PLACE=0.20`) reads **4 slides in 8 legs** against C's 1 in 5, with
the rotation starting at the *same fraction* of the leg (73-78 % vs 73-79 %) but
**+211 ticks = +1.76 s of absolute dwell at near-top-down** - so the class tracks
**time spent hanging in a top-down pinch under lateral load**, and the P44
speed-up is the direction with a measured contrast (its cost stays the closed grip
class, P44/P46). **The escape's signature**: `contacts@onset` **1**, `force@onset`
7.9-11.2 N (the pinch's own 9.8 N), then `fmin 0.00` and the jaws end **closed**
at 42-53 mm (the lift-leg form ends at the **98 mm** open stop) - a **clean
single-sided exit**, neither a force deficit nor a pry. **What the lever does
buy, as predicted**: `clr` **34 -> 88 -> 142.5 mm** and `clr_edge` **38 -> 94 ->
151.5** (+54 / +108.5 against PREREG P1's +49 / +99, so P69-B's 0.825:1 is
confirmed on a second axis; no leg negative), at **+4.5 / +7.0 % episode ticks**
(the descent +41 / +90 ticks; the *leg* total only +22 / +17 because the transit
shrank - **P2 partially missed, P3 missed informatively**: the endpoint was
predicted to stay 85-95 deg and went to 105.2, which is *why* A does not fire).
**The right reaches a median 107.3 deg (max 109.7) and slips 0.0-0.1 mm on 10 of
10 legs** - the strongest single argument that the rotation is not the cause;
right placed 7/8 -> 10/11 -> 10/10, no new class (P5). **No landing regression**:
1 `did not land` per T arm vs C's 2, no `fell off` row, `need` 248 mm against the
300 mm `FRUIT_PLACE_LOW_MAX_DROP` ceiling. **The instrument is the reason the
negative is readable**: the pre-existing per-leg read (`[attitude]`) is printed
once at the leg's end and reads 80.8-94.6 deg on **both** the lost and the placed
legs of the shipped corpus, so a screen using it alone would have concluded "the
height does not move the rotation" - and been **wrong**. The default-off
`[carry]` fields `tilt0`/`tilt_end`/`tilt_max`/`t45`/`t75`/`tilt_rate`
(`tasks.py` **`adcfd348`**, inside the existing `if guard_armed:` block,
**pure arithmetic on `rot_now`** - no new articulation read) make the schedule
visible; pinned by `scripts/240_p73_tilt_selftest.py`, `235` re-pinned for the
inserted fields. **Named consequence**: do not spend another transfer rung,
another rotation lever (`FRUIT_GRASP_LEFT_TOPDOWN`/P64's pre-compensation act on a
link measured off the failure's path), or a *slower* place leg; the residual is
the closed `SIM_LIMIT.md` loaded slide on a leg that carries the payload top-down
for ~0.5 m, so the levers that touch it are the ones `SIM_LIMIT.md` sanctions (a
new pad asset, a real-jaw clamp-force anchor) or a workstation move that shortens
that transit at top-down (`FRUIT_PLACE_INNER_SHIFT` is already measured negative,
P3). **Provenance gap named, not fixed**: the manifest records `lift_dz`,
`lift_climb`, `scene`, `physics` but **not** the transfer height - a store under a
different value would be indistinguishable, so the field must go into
`assets.scene_provenance` before any recollection uses the knob. No-harm:
`accept.sh` **6/9 + `fingerprint: matches`** with its **346/346 `[fruit]` lines
byte-identical** to `logs/p71/accept_rails_none.log` (the instrument is inert on
the scripted path), `configs/` untouched (`8952c320` / `eb697f23`, no re-record),
`selfcheck.sh` PASS (the new leg included). Pins: `tasks.py` **`adcfd348`**,
`rl_env.py` **`157e6d`** (the `TASKS_MD5` metadata-only follow),
`scripts/235_p65_lift_selftest.py` **`bdcbb4`**, `scripts/240_p73_tilt_selftest.py`
**`28cd1f`**; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p73/{PREREG.md,PREREG.md5,P1_RESULTS.md,header.txt,p0_census.py,
p0_census.txt,p1_report.py,p1_report.txt,run_p73.sh,batch_s77.out,
batch_slow.out,direct/,smoke_T1.log,accept_noharm.log,accept_noharm.driver}`;
WORKLOG "P73".

**P74 (2026-10-31, `logs/p74/`; nothing adopted, no default change, **no `src/`
or `configs/` edit**): the place profile's **speed does not move the left's
place-leg loaded slide**, and the **`clean_slip_max > 800 mm` threshold is not
speed-invariant** — so the class's rate is flat over a **2.6x** dwell range and
is **stochastic given the pinch**. The knob is **`FRUIT_SPEED_PLACE=0.52`** (the
P44 **S1** cell, the mirror of the `=0.20` arm P73 inferred the mechanism from;
it supplies the **default** of `FRUIT_DYNAMIC_PLACE_VMAX` read at
`tasks.py:3853` inside `elif self._dynamic_capture_active:`, which the direct
presentation arms — and it is **not direct-scoped**, the same site runs on the
scripted dynamic line, which is why P44 could measure it there). The manipulation
gate (`logs/p74/p1_report.py --check`) passes **every clause on all three seeds**:
`|v|cmd` **0.343 -> 0.509** on the left place legs, the per-leg tick count
matching `motion.jerk_limited` at the printed distance to **<= 1 % on 33/33
legs**, **S/C ticks 0.676-0.678** on the distance-matched pairs (predicted 0.673),
and the `place low` descent in its ±20 % band. Cell: the P66-phase-3 / P73
scenario verbatim, `moe_v13s` `61da390a`, 15 picks, one claim per run, **seeds
77/101/202** — and the expansion is what saved the phase: **seed 77 read 2/4 ->
1/6 in the predicted direction and fired the registered rule, seed 101 read 4/7
-> 4/5 and seed 202 2/8 -> 2/3**, the opposite way at both. Pooled left place
legs: the registered primary **`> 800 mm` 7/19 = 37 % -> 3/14 = 21 %**
(Fisher **p = 0.455**) while the **mechanism count** (`clean_slip_max > 100 mm`,
a payload that left the pinch) is **8/19 = 42 % -> 7/14 = 50 %** (**p = 0.733**),
left placed 11/20 -> 6/15 (p = 0.5), the **failure ledger identical in count**
(left `cnp` 8 vs 8, left `never-grasped` 1 vs 1, right 2 vs 2, `did not land`
8 vs 8, `fell off` 0 vs 0, blow-ups 0 vs 0) and the **right flat** (23/25 vs
28/30 placed, **0 loaded slides in both**, its place legs also shorten, 356 ->
258 ticks). **The primary fell for a measurement reason, and that is the
phase's transferable finding**: after the escape the reported slip is
`rate x (ticks - loss_row)`, the rate rises **3.13-3.25 -> 3.93-4.00 mm/tick
(+25 %)** with the pads' speed and the remaining leg falls **-38 %**, so events
migrate from the `> 800` band into `100-800` (S draws **4 near-misses at 659.6 /
740.9 / 798.8 / 799.1 mm** against C's one at 617.1). **Quote the escape count,
not the threshold, for any speed change**; the threshold stays usable for
height/rotation/retiming, where the remaining leg is constant (P73's own
793.3 mm "held" leg was already named a payload loss). **The dwell is not the
actuator**: with P73's slow arm the rate is **50 % (680-tick legs) / 42 %
(405) / 50 % (262)** across a 2.6x range, so P73's `4/8` is a draw of the same
~45 % rate and its "time-accumulating loaded creep" reading is **withdrawn** —
what survives is its positive half (the escape's **onset precedes the wrist's
45-deg crossing on 15/15** losses here too, `loss_row/ticks` 0.01-0.44 against
`t45/ticks` 0.71-0.86; the right reaches the same attitude and slips 0.0-0.1 mm
on 28/28 place legs). The escape's **signature is speed-invariant** (both arms
`force_min = 0.00 N` on every loss, `contacts@onset` 1 on 6/8 and 6/7, jaws
ending at the **17.3-53.7 mm** closed form, never the 98 mm open stop; one S leg
is a `27.09 N` / `sep@onset 98.2 mm` squeeze-out at the open stop rather than a
slip, and both arms carry exactly one `0.00 N / contacts 0` never-held leg). `clr`/`clr_edge`
are **leg-determined, not profile-determined**: on distance-matched legs they
read **-1 / -3 / -9 mm** (65/61 cm), and the arm-median drop is leg mix (S drew a
53 cm leg at +4 mm; C's own four 58 cm legs span 18-49 mm); the **achieved**
rotation lags ~4 % of the leg later at 0.46 m/s (`t45/ticks` 0.75-0.86 vs
0.71-0.81, `tilt_end` 61-79 vs 68-88 deg) while the commanded path is identical.
The speed's **time** saving is real and reproducible (left place leg **405 ->
262 ticks = -35 %**, episode median **-5..-7 %**, `|a|cmd` 0.30 -> 0.72 with the
`place` cone still **0.84-0.90x** of budget) but it is a **throughput** candidate,
not a class fix, and P44/P46 already priced that direction's placement cost; the
`place low` descent also loses **5 %** because the faster leg ends **12 mm** lower
in achieved z (the release re-measures its clearance, so the landing class is
unchanged). One S `cnp` is **not** the class — a **place-reach/landing shortfall**
with the payload held (`clean_slip 0.0`, `clr +23 mm`, `res_end 50.2 mm` against
29-31 on healthy legs) — and one note text is new to the batch on a
**`grasped=False`** leg (`fruit left the pick station during the close
(27454 mm)`, a recycle artifact upstream of any carry leg). **Verdict: falsifier
F1 fires -> no adoption, no phase 2**; the named consequence is that **this
class needs >= 3 seeds before a direction is called** (a 15-pick single-seed cell
produced a 15-point false positive), and that with P73 the place-leg lever space
is exhausted for **pose, rotation and clock** — what remains is
`logs/p42/SIM_LIMIT.md`'s two sanctions (a new pad asset, a real-jaw clamp-force
anchor) or a workstation change that shortens the lateral transit at top-down.
No motion reference moved (`8952c320` / `eb697f23` stand — nothing was flipped,
so no re-record was owed). Provenance: the batch spans two commits
(`75e980a` seed 77, `90f31a6` seeds 101/202) whose diff is **two `logs/` files**
and **no `src/`/`configs/`/`scripts/` change**. Pins: `tasks.py` `adcfd348`,
`rl_env.py` `157e6d85`, the batch's `header.txt` `0d246950`,
`PREREG.md` **`1c3546de`**, ckpt `moe_v13s` `61da390a`; evidence
`logs/p74/{PREREG.md,PREREG.md5,P1_RESULTS.md,header.txt,p1_report.py,
p1_report.txt,p1_aggregate.py,p1_aggregate.txt,run_p74.sh,batch_s77.out,
batch_s101_202.out,direct/}`; WORKLOG "P74".

**P75 (2026-10-31, `logs/p75/`; **one default-off diagnostic, nothing adopted, no
default moved, `configs/*` untouched**): the place leg's escape is an
**expulsion - a wedge/pry runaway**, not a slide at constant `sep` and not a
command transient, and the trace settles it at one tick.** The instrument is
`FRUIT_PLACE_ONSET_TRACE=<ticks>` (`tasks.py`, **0 = off = the shipped path**;
`place*` legs only, one `[place-trace]` row per tick, post-step, inside the
existing W8-B carry block **which it also arms** so it is self-sufficient):
`t`, `|d|` and `d=(x,y,z)` (the hand-frame displacement and its components, P61's
axis), `sep` (measured) beside `gap` (commanded), `f=(f0,f1)`, `n`, `tcp_err`,
`v_cmd`, `v_ach` and this tick's `q_margin=…@jN`. **No articulation read is
added** (`rot_now`/`pads`/`_tcp_pos`/`_marg`/`gap_command` are the block's own;
the two additions are `jaw_separation()` and one tactile set per traced tick);
pinned by `scripts/241_p75_place_trace_selftest.py` (selfcheck leg) and read by
`scripts/242_p75_classify.py`, whose **rule was pinned before the runs**
(`logs/p75/METHOD.md`, `PREREG.md5` **`479bb896`**): `t_d` = the first `|d| >= 2 mm`
(the diag's own trigger), `t_sep`/`t_f` = the first measured-separation drop
`>= 1 mm` / the strong face below half its leg-start value, `t_err` = the first
`tcp_err` 20 mm above the leg's **own steady state** (median of the last third),
`t_cmd` = `t_err` or a `|Δv_cmd| >= 0.10 m/s` step; **(c)** if `t_cmd <= t_d - 2`,
else **(a)** if `t_sep`/`t_f <= t_d`, else **(b)**. Two registered cells
(`A_77`, `A_101`: 15 picks, seed 77/101, `moe_v13s` `61da390a`, the
P66-phase-3/P71-phase-2/P73/P74 cell verbatim, `FRUIT_CARRY_DIAG=1` +
`FRUIT_MOTION_REPORT=1`) trace **26 place legs** (12 left) at 60 ticks and draw
**6 left place-leg escapes** (832.5/833.6/806.8 mm in s77, 895.7/844.8/851.9 in
s101; **all `cnp`**, and `escape <=> cnp` on **12/12** left legs), plus one
**declared extension** (`B_101_t200`, 8 of 15 episodes, `=200` ticks) that
resolves one of them end-to-end. **The finding is the ordering**: that leg holds
the payload with `|d| = 0.0 mm for 110 ticks` and `sep` constant to the print;
at **t=111** `|d|` reads 0.3 mm while `f` falls 5.03 → 4.11 N and `sep` starts
**rising**; at **t=112** `f = 0.00 N`, `n = 0`, `sep +1.0 mm`; at **t=121** the
pads sit at their **98.1 mm mechanical open stop** with `|d| = 12.6 mm` **while
the force servo closes the command 68.7 → 66.7 mm** - i.e. the payload is pried
out through a widening gap, so **(b) is refuted** (`sep` does not hold) and the
`SIM_LIMIT.md` sentence "the pads hold and the payload slides" is *not* this
interface's mechanism (**it refines, not contradicts, the class**: the pry is
force-sensitive - P41's ladder deleted `sep_max` 98.5 → 43.5 → 31.2 at 10/30/60 N
- while the class did not convert, so the residue is pad **face geometry**, the
`SIM_LIMIT` new-pad-asset sanction, not more force). **(c) is refuted by
measurement**: **0 of 26** traced legs show a `|Δv_cmd| >= 0.10 m/s` step, and at
the escape tick every commanded quantity is smooth (`v_cmd` 0.202 → 0.205 → 0.207
→ 0.210 over t = 110..113; `tcp_err` on a straight +0.6 mm/tick ramp) while a
**held** leg carries the same ramp (25.1 → 46+ mm) and holds - so **there is no
profile-continuity lever at the leg boundary** and none is registered. **The
wedge fires at two sites, one mechanism**: 2 of 6 escapes at the **end of the
lift** (the place leg then *starts* with `n = 1`, one face at **0.00 N**, and
`sep - gap` **+25.3/+28.5 mm** against **+8.5..+14.7** on the 23 normal legs - no
overlap - and their preceding lift legs are the three that slipped 7.9-11.3 mm,
though that second separator is **not clean** (eight of the other nine left lifts
read 0.0-3.2 mm and the ninth 7.5 mm, and *its* place leg still started normal -
so the first-tick pinch state is the discriminator, not the lift's slip), and 4 of 6 **inside** the place leg at
`onset_row` **105 / 140 / 142 / 159** with the leg starting clean (`n=2`,
4.28-4.95 / 4.89-5.07 N) and **`|d| = 0.0 mm for the whole 60-tick window** -
which is itself the answer to "the first ~40 ticks": for that family the payload
does not begin to go there. **Named next (post-hoc, not a result)**:
the 4 late escapes' *preceding lift* ended **27.6-58.9 mm behind its command**
(`res_end`) against **8.6-14.6 mm** on the 8 held-or-pried legs (no overlap,
n = 12 left legs, 4-vs-8) - "does the lift leg's tracking deficit predict the
place leg's escape?" is a phase that needs its own PREREG, and it does **not**
fit a "the catch-up feeds the slip" story (`|d|` is 0.0 mm through the fastest
part of the catch-up, t = 1-60, and the wedge fires at t = 111 with `v_cmd`
already 0.20 m/s). Deviations, all recorded in `METHOD.md`: **A1** withdrew a
`v_ach >= 1.5*v_cmd + 0.05` clause (it fires on every *clean* leg - `v_ach`
0.095-0.099 m/s while `v_cmd` is 0.000, the arm closing the previous leg's
19.4 mm residual); **A2** took the force reference from the **stronger** face at
t = 0; **A3** labels a leg that is **already** single-sided with
`sep - gap >= 20 mm` at t = 0 **`a0`** (inherited expulsion) because on such a
leg `sep` *cannot* fall further - it is at the stop - so the literal in-window
test would fall through to (b) (pre-A3 seed 77 read `a=2 b=1`, the b being that
artefact; the **mechanism** verdict is unchanged); **A4** marks the 200-tick cell
as an extension, not a registered cell, and no rate comes from any of them (the
trace arms the carry block and adds two reads per traced tick - the 60-tick
cells ran at **35.5/35.3 s/pick**, inside the untraced P74 range 29.7-35.4, and
at 200 ticks the cost is **~3.5 min/episode**, so 200 is a batch-lane setting).
No-harm: `scripts/accept.sh` with the knob unset reads **6/9,
`fingerprint: matches`, and its 346 `[fruit]` lines are byte-identical to
`logs/p73/accept_noharm.log`** (both streams md5 **`d0079a23`**; the exit=1 is
the standing rate floor, this tree's branch since P32); `scripts/selfcheck.sh`
**PASS, 0 failures**. Pins: `tasks.py` **`303d025d`**, `rl_env.py` (the
`TASKS_MD5` metadata-only follow), `scripts/241_p75_place_trace_selftest.py`
**`14be55ea`**, `scripts/242_p75_classify.py` **`4f41d983`**,
`logs/p75/p75_report.py`; `configs/*` untouched (`8952c320` / `eb697f23`), no
reference re-recorded, ckpt `moe_v13s` `61da390a`. Evidence
`logs/p75/{METHOD.md,PREREG.md5,RESULTS.md,header.txt,p75_report.py,
p75_report.txt,direct/,smoke.log,accept_noharm.log}`; WORKLOG "P75".

**P76 (2026-10-31, `logs/p76/`; **nothing adopted, no default changed, `configs/*`
untouched**): the pad pry needs **> 30 N**, the payload **> 45 N**, and the
smallest fruit is **not crushed at 60 N** on the direct line - so P76's two
numbers are `60 N` (pry deleted) and "no crush at 60 N", and P41's "60 N crushes
a 3.7 cm strawberry" is a **seating** event, not a force threshold.** One
default-off `[carry]` field group (`dia=`, `sep_max=…@t<tick>`, `gap@sep_max=`,
`sep_min=`, `fmax=`, reporting only inside the existing `if guard_armed:` block,
`FRUIT_CARRY_DIAG`-gated) exists because `sep@loss` is sampled at the loss while
P75 measured the pads reaching their **98.1 mm stop 9 ticks later**. The ladder is
`FRUIT_FINGER_MAXFORCE` **10 (unset) / 15 / 20 / 30 N**, seeds **77 and 101**, one
claim per cell, the P66-phase-3/P71-phase-2/P73/P74/P75 scenario verbatim, plus
**two declared extension cells** (45 and 60 N) registered before they ran
(`PREREG.md` `62567d8b` → A1 `0397a929` → A2 `5e51d95b` → A3 `af7da4e5` → A4
`1991c5fa`). **The manipulation check is two independent confirmations per rung**
(the build print's `maxForce=<cap>/0.0N` and the **live articulation** read-back
`[drive] … joint1/joint2=15.00/0.00 N`) with the behavioural third leg the held-leg
`force_min` median **9.6-9.7 / 14.2-14.7 / 18.2-19.3 / 25.3-29.2 / 39.9 / 53.9 N**
(85-99 % of the cap) - the rung *is* the
delivered force (P41's law), and `F10` is evaluable as the unset path (no
`[drive]` row by construction). **The pry does not stop in 10-30 N**: the pads
reach their stop on **5 / 1 / 2 / 2** legs of 55/54/55/54, and the **same 6.8 cm
pear** (left, seed 77, the phase's cleanest control - only the cap differs) reads
`place0 sep_max` **98.1 / 98.1 / 98.1 / 98.3 mm at 10/15/20/30 N** with
`gap@sep_max` 66.9-69.9 mm, i.e. the pads are **25.7-31.2 mm wider than the
command** at every low rung, exactly P75's wedge - so **30 N does not relieve the
travel limit here**, which is where this interface departs from P41's scripted
ladder (98.5 → 43.5 → 31.2 there). The two thresholds are **separated**:
**the pads' stop is relieved between 30 and 45 N** (45 N: **0/26** legs past
95 mm, corpus max **90.4 mm**) **and the payload is not saved by it** (the same
pear still leaves, **829.5 mm**, force 0.00 N) - only **60 N** gives **0/26 pried**
(corpus max **76.7 mm**) and **0/26 escapes**, with the pear at 75.2-75.8 mm and
**0.0 mm** slip. Retention is **not monotone** (20 N keeps it at 11.0/13.6 mm,
30 N ejects it 96.8 m, 45 N loses it) and every cell is **one draw** - those rows
are a per-instance dose-response, **not a rate**; what is monotone is the pad
travel, which is what the phase asked. **The crush guard reads 0 legs at the
registered C1/C2 in all six cells**: C1 was sharpened **before the extensions** to
the **loss tick** (`sep@loss - dia`, the only tick the payload is provably between
the pads, because a loaded `sep_min` also catches the pads pressing **each
other** after a small fruit has gone - two 3.9 cm strawberry legs at seed 101
read a 148 m / 223 m `clean_slip`, i.e. recycled payloads, with the pads at their
10.0 mm closed limit). The **strawberry** (3.6 cm, the binding class) reads
`sep@loss - dia` **+0.5 mm** at a **36.1 mm** span under a **60.16 N** pinch,
`force_min` 55.40 N, **placed** - and the closest low-rung number is **-14.8 mm**
(one 3.9 cm instance at 15 N, `fmax` 24.26 N, 496 mm) which sits **0.2 mm inside**
the -15 mm rule, so the rule does not fire: that is a **seating** event (the close
landed 24.7 mm inside the fruit) whose depth the cap amplifies, which is why P41's
scripted 60 N crush (pads to 10.0 mm around 37 mm) does **not** reproduce here.
**Counts are reported, never gated** (20/30, 23/30, 24/30, 24/30, 12/15, 13/15
placed; left 6/14 → 6/9 → 7/10 → 7/10 → 4/5 → 6/6; held `force_min` medians
9.58-9.66 / 14.19-14.67 / 18.22-19.27 / 25.32-29.19 / 39.9 / 53.9 N) - a count across rungs **compares attractors**, and the only rate-shaped
claim is per-leg (**0/26 pried at 60 N vs 5/55 at 10 N**). **Deviations, all
pinned before the runs they govern**: **A1** `sep_min` is the **loaded** span (the
unconditional minimum fires on every escape leg - a lost payload lets the servo
close the pads onto nothing, `sep_end` 51.9 mm inside a 68.3 mm fruit; the
discarded pre-A1 cell is kept as `DISCARDED_F10_pre_a1.log`); **A2** the 45/60 N
cells are **declared extensions, not rungs** (P75's A4 convention); **A3** an
escape leg must have had a **pinch** (`fmax > 0` - one leg's `clean_slip_max` is
**308 215 mm** with `fmax = 0.00 N`, a recycled payload, listed separately as
never-held); **A4** the bisection ran because F60 came back clean on **both**
endpoints. **No phase-2 cell is run**: the §5.1 condition is met only at a
**declared extension** (F60), so it licenses a plan - **3 seeds x 15** at 60 N
with the paired carried-class endpoint, the **two-line and scripted no-harm**
(three references and every store re-recorded, the expensive item), and the
**sanction**: the cap is not physical until a real jaw is anchored to it, i.e.
"the sim needs 60 N; a real jaw would have to deliver 60 N" - the owner decides.
No-harm: `accept.sh` **6/9 + `fingerprint: matches`** with its **346 `[fruit]`
lines byte-identical** (stream md5 `d0079a23`) to `logs/p73/accept_noharm.log`
(`logs/p76/accept_noharm_full.log`; the new fields need
`FRUIT_CARRY_DIAG=1`, so they cannot run on the scripted path), `selfcheck.sh`
**PASS, 0 failures** (the new leg). Pins: `tasks.py` **`9d5824ef`**, `rl_env.py`
(the `TASKS_MD5` metadata-only follow), `scripts/243_p76_sep_selftest.py`
**`fc0e738e`**, `scripts/selfcheck.sh` **`84f77dcb`**, `logs/p76/p76_report.py` **`544fc6f2`**;
references **`8952c320` / `eb697f23`** both untouched, no reference re-recorded,
ckpt `moe_v13s` `61da390a`. Evidence
`logs/p76/{PREREG.md,PREREG.md5,RESULTS.md,header.txt,run_p76.sh,p76_report.py,
p76_report.txt,direct/,smoke_a1.log,accept_noharm.log,accept_noharm_full.log}`;
WORKLOG "P76".

**P77 (2026-10-31, `logs/p77/`; **evidence only - nothing adopted, no default
changed, no `src/` or `configs/` edit**): the owner's 3-seed cell at 60 N -
**the count converts, the escape class does not.** The honesty frame first: 60 N
per joint is **jaw-feasible** (a 2F-85-class jaw covers 20-235 N) but it **would
bruise a 3.6 cm berry in reality** and **this sim has no bruise model**, so a
clean read here is about **geometry and retention**, never fruit quality. Arms
**C** = the shipped 10 N (`FRUIT_FINGER_MAXFORCE` unset) and **T** = `=60`,
interleaved by seed (77 C->T, 101 T->C, 202 C->T), **seeds 77/101/202 x 15**, one
claim per cell, the P66-phase-3/P71-phase-2/P73/P74/P75/P76 scenario verbatim,
`moe_v13s` `61da390a`, `PREREG.md` **`d31c3e4a`** pinned before any run. **The
primary: left placed 11/21 -> 17/20** (Fisher **p = 0.043**; **3/3 seeds**
improve by +3/+1/+2, so the run level's one-sided sign p = 0.125 **is its
minimum attainable at N=3 and is quoted as a ceiling**; class-standardised
**0.524 -> 0.927** at C's species mix), **left `cnp` 7 -> 3**, left never-held
3 -> 0, and the **right is not worse** (21/24 -> 22/25, 0 cnp, 0 escapes, no new
reason). The **pairing** is `(seed, arm=left, species, diameter to 0.1 cm)`,
greedy 1:1: only **11 of 21** pair (10 **unpairable** - a fruit the other arm
never drew), both placed 5 / C-only 0 / T-only 6, McNemar **p = 0.031**, and it
is a **descriptor, not the primary**, because the fruit presented is a
post-treatment variable - a same-configuration replay (C_77 against P76's F10_77)
agrees on **2 of 15 episodes and diverges at episode 2**, so no instance-level
pairing exists on this interface. **The pre-registered mechanism bar fails**:
left escape legs (`clean_slip_max > 100 mm`, pinched) fall **7 -> 3** = 43 %, not
<= 1/3 (M1 FAIL), while the pries fall **4/38 -> 1/40** (M2 PASS, 25 %) and the
crush guard stays **0/6 cells** (M3). **The residue is a different mode**:
**2 of the 3** T escapes leave through a **3.4 / 7.9 mm** pad opening (the pads
essentially closed on the fruit - P61's **axial** walk off the distal lip)
against the control's **13.5-39.9 mm** radial pry, and **1 of 40** T legs still
**pries fully** to the 98.1 mm stop (peach 6.2 cm, `fmax` **64.52 N**, 782.9 mm).
Every escape and every pry in **both** arms is a left `place0` leg: the site is
invariant, the mode is not. **P76's single draw does not reproduce**: its
**0/26 pried, 0/26 escaped** at seed 77 becomes **1 pried / 3 escaped of 40 left
legs**, and the same 6.8 cm pear P76 saw held (`place0 sep_max` 75.2, slip 0.0)
**escapes here** (76.2, 834.7 mm) - so 60 N **reduces the class by more than half
and changes its mode; it does not delete it.** **The strawberry** (the binding
class) is held in both arms - C **5/5**, T **6/6 real legs**, `sep_max - dia`
**-0.7..+6.2 mm**, the 3.6 cm fruit at a **36.7 mm** span under **52.6-54.2 N** -
and **no crush leg fires**; the one T_101 strawberry "loss" is the **recycled
payload** artifact (`fmax` **0.00 N**, `clean_slip_max` **160 769 mm**), excluded
by P76 A3 and named, not hidden. **The manipulation check is three-fold per
cell**: build print `maxForce=10.0/60.0`, env derev, **live `[drive]` read-back
60.00/0.00 on both arms**, the manifest's `physics.finger_maxforce` + the
drive-`readback_matches`, and the behavioural **held `force_min` median 9.72 ->
53.41 N** (per seed 9.72/9.96/9.71 against 56.31/53.41/52.08). **The price
(report only, nothing re-recorded)**: at 60 N the scripted acceptance reads
**6/10** against the archive's **6/9**, with the **branch moving at attempt 0**
(60 N places it: lift +0.411 m / 60.05 N; 10 N fails it: +0.138 / 9.98 N),
**378 vs 346 `[fruit]` lines** (md5 `4d89c743` vs `d0079a23`, 57 identical with
the print rows dropped) and **`fingerprint: DIFFERS`** from `8952c320`; the
two-line reads **8/10** at its own 0.60 floor with all ten descents inside budget
and **`190` FAIL on the fingerprint alone** against `eb697f23` - and 2/18 carry
legs still slip >400 mm, of which the shipped-cap P71 two-line has **three of its
own**, so that is not a cap effect. A flip therefore owes **both motion
references, a scripted re-baseline and every store's provenance** - for a class
that shrinks rather than closes. Pins unchanged (env-only phase): `tasks.py`
**`9d5824ef`**, `rl_env.py` `7ca5aa70`, refs **`8952c320` / `eb697f23`**, ckpt
`61da390a`; `scripts/selfcheck.sh` **PASS, 0 failures**. Evidence
`logs/p77/{PREREG.md,PREREG.md5,RESULTS.md,header.txt,run_p77.sh,p77_report.py,
p77_report.txt,direct/,rollouts/,p1_accept_mf60.log,p1_accept_mf60.driver,
p2_twoline_mf60.log,p2_twoline_mf60.gate,selfcheck.log}`; WORKLOG "P77".

**P78 (2026-10-31, `logs/p78/`; **default off, nothing adopted** - one new knob
and its runtime write): the clamp can be **scoped to the site**, the runtime
write works, the containment is total - and the dose reproduces P77's
mechanism without the grasp half, at a count that is a direction, not a rate.**
P77's win was measured on a **global** cap, which is a per-joint drive property
written at build time on **both arms of every presentation** - so a flip moves
the scripted acceptance at attempt 0 and the two-line's fingerprint, and owes
both motion references, a scripted re-baseline and every store. But P77 §2 also
measured the class's **site**: every escape and every pry, in both arms, is a
left `place0` leg. So the lever is a **runtime** cap on one arm's `place*` legs:
`FRUIT_FINGER_MAXFORCE_SCOPE=place-left` (+ `..._SCOPED=<N>`, default 60), the
only token at P78 - **the P79 paragraph below adds `grasp-left` for the pick half,
and the scope dict is now keyed `"<side>:<legs>"` so the two classes cannot
overlap**; an **explicit `FRUIT_FINGER_MAXFORCE` still wins** (the global path
keeps its meaning, the two cannot stack) and **every non-`direct` presentation
resolves `(None, None)` before reading a value** (`rl_env.resolve_finger_cap_scope`,
strict: unknown token / non-number / non-finite / `<= 0` raise). The task takes
it as a caller-owned kwarg and `tasks.finger_cap_scope_for` is the **only** site
resolver (one carry-leg class per key, per side; from P79 one key is `place*` and
the other `grasp_lift`, so neither can arm the other's legs); `_carry`
is now a **wrapper** that raises the left drive's `joint1` cap via
`set_dof_max_efforts` and restores **the cap the leg found** in a **`finally`**
(the leg body is `_carry_leg`; `237`'s locator follows it, assertions unchanged).
**The runtime write is real and proven three ways**: the API is the tensor
backend's `set_dof_max_forces` -> live `joint_effort_limit` + a
`JOINT_DOF_PROPERTIES` notify (the one `scene.apply_finger_maxforce`'s docstring
names as acting on a live view); the per-leg `[drive]` read-back follows
(`10.00 -> 60.00`, readback `60.00`, restore `-> 10.00`); and the **physics**
follows - `place*` **peak** force **29.75 / 44.99 / 56.08 N at caps 30 / 45 / 60**
(99 / 100 / 93 %) against a control of 10.69 N, while **`grasp_lift` stays at
9.10-9.97 N in the same runs** (the pick is untouched by construction *and* by
measurement). **The blast radius with the scope armed is zero**: the scripted
acceptance is **346/346 `[fruit]` lines, md5 `d0079a23` - byte-identical** to
`logs/p76/accept_noharm_full.log` - with `fingerprint: matches` (the only failing
clause is the standing 6/9 rate), the two-line is **7/10 + `190: PASS`** against
`eb697f23`, neither prints a scope row, and **no reference was re-recorded**;
B1/B2 are **import/structure guards** (the scripted entries never construct
`SortingRLEnv`) and the substantive proof is the direct line's own read-back.
**The dose** (seed 77 screen, then three seeds): the screen passed S30 and S60
and the economical rule sent **S30** to seeds 101/202 - where its 6-leg "0
escapes" became 4/32, **P74's lesson again**. Three-seed pooled **C / S30 / S60**:
left placed **10/18 · 12/17 (p = 0.49) · 11/16 (p = 0.50)**, left escapes
**8/36 · 4/32 · 4/31 (both 50 % of C, not <= 1/3)**, left pried **3/36 · 0/32 ·
1/31**, right **25/27 · 22/28 · 25/29**, cycle **1774 · 1804 · 1789**. **No rung
meets its bar** (S30 fails D2 and D4; S60 fails D2 and the per-cell crush guard),
so nothing is adopted - but the **mechanism is P77's without the grasp half**
(pries essentially deleted, escapes halved rather than closed - P77's T was
4/38 -> 1/40 and 7 -> 3 = 43 %) and the **mode migrates**: the control's escapes
are **0/8 axial**, both doses are **2/4 axial** (`sep_max - dia` +2.7 .. +9.9),
i.e. **force removes the radial pry and leaves the axial walk**
(`logs/p42/SIM_LIMIT.md`, P61). The extension's **P5 did not fire**: a
place-leg-only cap that cannot touch the pick still moves the left count in
P77's direction, so the **place leg carries the direction** and only the
magnitude is unresolved. Two negatives are recorded, not smoothed: **S45's
6.8 cm pear pries at a delivered 46.05 N** (`sep_max` 95.6 mm - force reduces,
does not delete), and **the one crush-guard leg is a RIGHT `grasp_lift` at the
shipped 10 N cap** (S60/101, a 3.88 cm strawberry, `sep@loss - dia` **-15.9 mm**,
`grasped=False` - the shipped close's squeeze-out, one event in ten cells, **not
dose-attributable**; it fails the registered per-cell D3/G7 as written). **A
recorded PREREG correction**: `force_min` is a leg *minimum* (a contact
transient), not a clamp read under a leg-scoped cap - it reads 80 / 78 % at
45 / 60 N while the leg *maximum* tracks the cap at 99 / 100 / 93 %; the report
prints both and gates on `fmin >= 75 % AND fmax <= 110 %`. No-harm:
`scripts/selfcheck.sh` **PASS, 0 failures** (new leg `scripts/244_p78_scope_selftest.py`
`aadea2d3`, 45 checks), `TASKS_MD5` metadata-only follow `9d5824ef ->
b1464c43`, `logs/p36/offline_obs_diff.txt` regenerated by the `218` leg (a
generated index, not a claim). Pins: `tasks.py` **`b1464c43`**, `rl_env.py`
**`5c7322d2`**, `scene.py` **`fbd7e2bb`**, `control.py` `9384ff4f`,
`assets.py` `540406fa`, `fruits.py` `c7461d41`, `policy/trigger.py` `b09d3cb2`,
`scripts/selfcheck.sh` `ce338611`, `scripts/237_p67_climb_selftest.py`
`6a6b18bf`, `configs/motion_reference.json` **`8952c320`**, `..._twoline.json`
**`eb697f23`** (both untouched), ckpt `moe_v13s` `61da390a`. Evidence
`logs/p78/{PREREG.md,PREREG.md5,PREREG_EXT.md,PREREG_EXT.md5,RESULTS.md,
header.txt,run_p78.sh,p78_report.py,p78_report.txt,direct/,rollouts/,smoke_60.log,
b1_accept_armed.log,b1_accept_armed.driver,b2_twoline_armed.log,
b2_twoline_armed.gate,p1_driver.log,p32_driver.log,p4_ext_driver.log,
selfcheck.log}`; WORKLOG "P78".

**P79 (2026-10-31, `logs/p79/`, default off, **nothing adopted**): the pick half of
the clamp - `grasp-left` - is a measured **null on the count** and a measured **win on
the leg state**, and neither scoped 60 N arm reproduces P77's global count.** The token
`FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left` arms P78's runtime cap on the left arm's single
`grasp_lift` leg only (keyed `"<side>:<legs>"` -> `{"left:grasp"}`, disjoint from
`{"left:place"}`, so neither token can arm the other's legs), default off, `direct`
only, an explicit `FRUIT_FINGER_MAXFORCE` wins, strict parsing, `_carry`'s `try`/`finally`
restore. **The site proof is exact**: one raise+restore per left lift leg (15/15 at
30 N, 17/17 at 60 N), **zero** rows on any `place*` leg or the right arm across six
armed cells, delivered lift pinch **10.02 -> 30.09 -> 57.48 N** (`fmax` medians; `fmin`
9.75 -> 29.43 -> 49.14) while the **place stays at 10.02/10.05 N** against the control's
10.07, and the manifest's `sites`/`readback_matches` agree in every cell. **The count is
flat at the recorded dose**: left placed **C 11/20 = 0.550 -> G60 9/17 = 0.529**
(Fisher **p = 1.0000**, per-seed **0/-4/+2**), `cnp` **7 = 7**, `never-held` 1 vs 2 (one
episode). **What does move is the lift leg's pinch integrity**: legs that **lose a pad**
**6/20 -> 2/15 (30 N) -> 1/17 (60 N)** (p = 0.0975), `sep_end - gap_start` 10.5 -> 9.2 mm -
i.e. P75's inherited-state mechanism works and the class it should feed does not
convert. **30 N is where the direction is and it is a dose, not a result**: **12/15 =
0.800** (p = 0.163, +3/-1/+1), `cnp` 2, lost-a-face 2, place escapes 2/14, but it misses
the registered `+3` bar and sits **below** P77's dose - and P78's place arm at 30 N read
the same shape (0.706). **The dose is not monotone** (30 N 0.706/0.800 vs 60 N 0.688/0.529),
so at n ~ 15-20 per arm no force above the control's own 10 N is identified as the
actuator. **The register's answer**: the three controls agree tightly (0.524/0.556/0.550,
pooled 32/59 = 0.542) and the two scoped 60 N arms bracket them (pooled 20/33 = 0.606),
while the global arm alone reads 0.85 - and the one leg class the global cap touched that
**no `_carry` token can reach is the close** (`_carry` is only ever called with `place{i}`
and `grasp_lift`), which is also where P77's `never-held` 3 -> 0 must have happened (a
never-held carry leg has `fmax == 0`; no lift-phase force can create contact the close did
not make). **The named next spend is a `close-left` scope at the close's own site** (not a
carry leg, its own registration), not another lift or place dose. **Guards**: right
**21/25 -> 26/30 -> 25/28** (p = 0.69), cycle **1751/1773/1772** ticks, crush guards 0 in
nine cells, and **every one of the batch's 30 strawberry legs was presented to the right
arm** (all grade B/C - the direct env sets arm from grade), so a 60 N pick on a berry is
**not exposed here, not measured safe**. **Blast radius re-proved with the scope armed**:
`accept.sh` **346/346 `[fruit]` lines byte-identical** to `logs/p76/accept_noharm_full.log`
(md5 **`d0079a23`**) + `fingerprint: matches` + **0** scope rows, and the two-line **7/10 +
`190` PASS** against `eb697f23`; no reference re-recorded. One **recorded deviation**
(`PREREG.md` §9 **A1**, pin `0cdfd227` pre-run / `afde5127` amended): the registered
per-cell `place* fmax <= 11.25 N` band is a **transient** test - it fired in 1/6 cells on
an **escaping** leg (12.13 N, `force_min` 0.00, slip 940 mm) at the shipped cap, and `fmax`
exceeds the cap on single legs even at 10 N (this batch's control reads 35.53 N; P78's
79.43/134.29/155.12) - so P3 is gated on the **structural** rows + the pooled force and
the band is reported; **no verdict moves** (P1 fails independently). Pins: `tasks.py`
**`e8dfa6d8`**, `rl_env.py` **`7d26eb5b`** (`TASKS_MD5` metadata-only follow),
`scene.py` **`07d6fdad`**, `scripts/244_p78_scope_selftest.py` **`50fde0fa`** (72 checks),
`scripts/selfcheck.sh` **`dd4bf41a`**; `configs/*` untouched (`8952c320` / `eb697f23`),
ckpt `moe_v13s` `61da390a`. Evidence `logs/p79/{PREREG.md,PREREG.md5,RESULTS.md,
header.txt,header_phase3.txt,batch_driver.log,run_p79.sh,p79_report.py,p79_report.txt,direct/,rollouts/,
smoke_grasp_left_60.log,smoke_site_proof.txt,b1_accept_armed.log,
b1_accept_armed.driver,b2_twoline_armed.log,b2_twoline_armed.gate,selfcheck.log}`;
WORKLOG "P79".

**P80 (2026-11-01, `logs/p80/`; measurement only - nothing adopted, no default changed,
no commit, `configs/` untouched): the cell's throughput on the shipped tree, and the two
levers priced against it - the two-line is a **1.87x sim clock and a 1.02x wall wash**,
the speed union a **cycle-time lever**. Today's cell (shipped single arm, 20
slots, seed 5): **12/19, 15.10 s/attempt, inter-placement interval 26.72 s mean / 36.90 s
p90, 2.25 placed/min on the placement window and 2.08 on the batch span, 25.2 s
wall/pick**; the interval is **bimodal** (17.5-19.6 s between two placements, 35.6-38.2 s
across a failure, i.e. `26.7 = 4.8 idle + 1.45 x 15.1 s attempts`) and **all seven
failures are `cnp`**, left 1/7 vs right 11/12 (not the lateral tail: the failed
`fruit_x` span 0.215-0.365 around a 0.305 placement, and the pick-pose jaw is identical
on every left attempt). Two 10-attempt gate arms prove the branch: **G-S10
`fingerprint: matches` `8952c320` with 346/346 `[fruit]` lines byte-identical to
`logs/p71/accept_rails_none.log`**, and **G-T10 `190: PASS` + `matches` `eb697f23` with
423/423 non-camera lines byte-identical to `logs/p71/twoline/none.log`** (so the P71
two-line record was one draw and today's tree reproduces it). **The two-line, first
measured on the shipped tree**: 16/20, 9.70 s/attempt, interval 10.77 / 18.00 s, **5.57
window / 4.96 batch = 2.48x / 2.38x**, lock-on 3.83 s left / 4.54 s right (19 retry polls
each), idle 18 %/21 %, 44 starved polls and **zero lost slots** - and its per-arm attempt
span **15.0-15.6 s is the single arm's 15.09**, so it *overlaps* attempts rather than
shortening one: **2.38x = 1.88x clock x 1.27x count**, the count half being the
*package* (its own W3 dense-sheet supply `wave=on grades A:0.375,B:0.375,C:0.25` + pure
grade routing) and the left arm's 1/7 -> 9/10. **The seed-6 pair (`S6` + `T6`) keeps the
clock and reverses the count**: 1.88x / **1.87x** clock, count 16 vs 12 then 10 vs 13,
**pooled 26/40 vs 25/38 - equal**, so pooled **sim 1.86x**. **Wall is measured, not
inferred** (`logs/p80/stamp.py` stamps every line through a `tee`): wall/sim **1.38 (S)
vs 2.57 (T) = 1.86x**, so **wall/pick is flat** (1.01x / 1.06x, pooled 1.03x) and the
**wall placed rate is 1.28x then 0.77x = 1.02x pooled**; the 1.86x is the *scheduler's*
per-tick cost, discriminated on the W6-B pair (both lines on the same dense sheet: single
1.25x, two-line 2.32x), not the supply's. **The union** (`FRUIT_SPEED_ALL=1`) **pays on
the clock** (-1.70 s single / -1.00 s two-line, -12 % wall/pick, exactly P44's place
-0.75 / release -0.84 / lift -0.24) **and not on throughput** (interval +4.9 %, window
-4.9 %, batch -12.6 %), its count fall being P51's acquisition class plus the grade draw
(arm-standardised it is +6 pt better, 69.3 % vs 63.2 %). So **a two-line default is a
simulated-time decision (1.87x) and a wash on this machine's wall (1.02x)**, and the union
is a cycle-time lever rather than a throughput lever. **Read rules for this tree from
here: quote both denominators (window and batch) and the wall column; never read a count
difference as the lever's (the closed `cnp` class owns it); and any throughput claim
needs >= 2 seeds** - the two-line's count advantage reversed at seed 6. No `src/` or
`configs/` change; the 20-attempt two-line reference is
`logs/p80/motion_reference_twoline_p80_20.json` and never `configs/`.

**P81 (2026-11-01, `logs/p81/`; measurement only - nothing adopted, no default changed,
no commit, `configs/` untouched).** The two-line's **scheduler** is separated from its
**supply package**: the **net 1.88x clock is the scheduler's own** (1.80x / 1.82x on
the single arm's shipped scattered supply, **96-97 %** of the package-on clock, at both
seeds), while the **feed and the overlap strength are the package's**: without it the
right arm reports no eligible fruit on **93.3 % / 82.0 %** of its polls (package-on
65.5 % / 63.0 %), the mean concurrency falls **1.58 -> 1.30 arms** at seed 5 (1.44 ->
1.42 at seed 6), and the delivered sim window rate falls 5.57 -> 3.08 at seed 5 while
the **count stays a seed draw** (10 vs 16 then 13 vs 10; pooled **23/40 vs 26/40**). The
cell is `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_WAVE=0` at `ATTEMPTS=20`,
seeds 5/6, with the 50/30/20 mix from the **code default** (`balanced = (wave or patch
or bed) and FRUIT_BIARM_TWOLINE == "1"` is False; runtime row `wave=off
grades=A:0.5,B:0.3,C:0.2`, **0** `A:0.375` rows) and **pure routing unchanged**; the
controls are P80's `S20/T20/S6/T6` on the identical tree md5s (no re-runs). **The
registered rule returns D2 (package required)** on its *delivered* clauses - seed 5
interval **19.47 s** vs 12 / 10.77, S-poll **6.30 vs 2.20** polls/attempt, S-idle right
**43 % vs 21 %**; seed 6 S-poll **3.35 vs 1.65** - while its four clock/count clauses
pass at seed 6 and three of four at seed 5: **the net clock is scheduler-only, the
delivered interval/rate is package-required.** Per-seed `s/attempt` 10.10 / 9.90 vs the
single arm's 15.10 / 15.00; clock ratio **1.80x / 1.82x** (control 1.88x / 1.87x);
interval **19.47 / 14.43 s**; sim window **3.08 / 4.16** and batch **2.96 / 3.92**
placed/min vs the single arm's 2.25/2.30 and 2.08/2.27; **wall 1.20 / 1.57 vs 1.51 /
1.63 (pooled 1.38 vs 1.57 = 0.88x)** - on this machine the package-off line is *below*
the single arm on the wall because the two-line pays 2.48-2.51x wall/sim (P80 section 6),
so the sim rate (pooled batch 3.44 vs 2.18 = **1.58x**) is the transferable number.
**The overlap-only read**: mean arms busy 1.30 / 1.42 vs the single arm's 0.83 and the
package-on 1.58 / 1.44; the seed-5 clock keeps 1.80x partly because its failed attempts
are shorter (10.79 s vs the control's 13.35) - holding that fixed the seed-5 clock would
be **~1.55x**. Tp5/Tp6 motion budgets **PASS** (worst `|v|max` 0.137 / 0.121 vs
0.160-0.161, lurch 0.050 / 0.028 vs 0.291, carry cone reported 1.89x / 1.62x);
`190` against P80's 20-attempt reference records **DIFFERS by construction** (the
supply changes the fruit sequence; no reference written, `configs/` untouched
`8952c320` / `eb697f23`); the accept probe is **6/9 + `fingerprint: matches`**; selfcheck
PASS. Pins unchanged from P80's tree: `tasks.py` **`e8dfa6d8`**, `bimanual.py`
`980923a6`, `fruits.py` `c7461d41`, `rl_env.py` `7d26eb5b`, `scene.py` `07d6fdad`,
`assets.py` `540406fa`, `control.py` `9384ff4f`, `conveyor.py` `fb2c58c6`. Evidence
`logs/p81/{PREREG.md,PREREG.md5,RESULTS.md,header.txt,battery_driver.log,
p81_report.py,p81_report.txt,supply_proof.txt,stamp.py,one_run.sh,run_p81.sh,
Tp5.log,Tp5.stamps,Tp5.budgets,Tp5.gate,Tp6.log,Tp6.stamps,Tp6.budgets,Tp6.gate,
accept_noharm.log,accept.gate,selfcheck.log}`; WORKLOG "P81".

**P82 (2026-11-01, `logs/p82/`; one behaviour-neutral optimization behind a
default-off knob, **nothing adopted, no default change, no commit**): the two-line's
61 % harness wall is 51 % physics and **32 % a 5 ms poll timeout** - the poll is
removable, and removing it turns P80's 1.02x wall wash into **1.55x**.** The
question was P80/P81's own: the two-line pays wall/sim **2.57** against the single
arm's 1.38, so its 1.88x simulated clock was 1.02x of wall. The split was measured,
not guessed, with two instruments on **separate profile builds whose `[fruit]` streams
are byte-identical to the record** (that is the admissibility test: a profile that
moves the branch is not a profile of the branch): **I2** = per-round timers at the
arbiter boundary only, never inside `ik_step` (`logs/p82/timers.py` +
`profile_20.py`, 47,795 rounds; R1 = 865/865 vs `logs/p80/T20.log`), and **I1** =
py-spy at 100 Hz with `--idle` (56,473 main-thread samples; R3 = 865/865). Both cost
wall (+1.0 % / +5.9 %) and neither moved a line. **The four hypotheses:**
**H1 holds, and as a *wait*, not as Python** - `TickRelay.schedule`'s own cost is
**0.024 ms/round = 0.2 % of wall**, while `MainBridge.pump`'s fixed 5 ms timeout is
**5.03 ms/round, 99.2 % of them timeouts, ~2.03 rounds per shared tick** (`CoopSession.run`
drives `schedule()` then `pump(0.005)`, and `pump`'s queue only receives *bridged
main-thread jobs* - the tick requests `TickRelay.request` files never reach it);
**H2 (render) is 0.0 %** - `_tick_frame` is 21,544 calls costing **0.059 s** on the
whole batch, because the scripted battery has no `frame_callback` and no recorder
(the *single* arm does pay a render: `update_app(steps=20)` in its pre-pose/feed, **12.7 %
of its wall**, py-spy); its stack inside `step` is **71.3 %** of its wall (and py-spy's
52.5 % vs I2's 51.0 % agree on the two-line's share); **H3 (physics) is the largest
single term and is not removable** - one shared `SimulationManager.step` = one PhysX `simulate(dt)` per
tick, **10.87 ms = 51.0 %**; **H4 (the second arm) is 15.7 %** (the arms' segments,
1.70 ms each, 1.97 per tick, serialized by the single permit). The dead wall is the
same number three ways: `pump` total 240.5 s minus the 78.9 s of segments it covers =
**161.6 s = 32.2 %**, the residual, and a wait histogram that is **one spike at
5.07-5.08 ms**. **The one optimization** (`logs/p82/apply_wake_patch.py`, 12 asserted
anchors; `bimanual.py` `980923a6` -> **`146e6252`**, +87/-10): `MainBridge` gains
`wake_on_request` + a `threading.Event`, `pump` waits on the event instead of the
timeout (the timeout stays as the safety net: a lost wake costs latency, never a
stall), and `TickRelay.register/enter/request/pause/resume/release` call `_notify()` =
`_cv.notify_all()` + `bridge.wake()`. **`schedule`'s own notify is deliberately left
alone** - waking from inside `schedule` makes the next `pump` return without waiting
and spins the driver loop. The knob is **`FRUIT_BIARM_WAKE_ON_REQUEST`, default ON since this phase**
(`=0` restores the pre-P82 timeout), read once per `CoopSession` - the flip is a
**latency fix, not a physics change**, and it shipped on the phase's own evidence
plus a post-flip check: two 4-attempt two-line cells, env unset vs `=0`, read
**85.9 s against 119.0 s of `[fruit]` span (-27.8 %)** with their 179-line
streams **byte-identical** (`p82_report.py --same`), so every recorded wall number
before this phase is a **timeout-path** number and `=0` restores it. **The proof is bit-identity at two seeds
and in four profile configurations**: W1/W2/W3 (seed 5, knob on, with and without the
timers) are **865/865** identical to `T20`, W4 (seed 6) **814/814** to `T6`, the
single-arm cells **710/710** to `S20` and the accept cell **346/346** to
`logs/p71/accept_rails_none.log`; the shared-station scheduler (`bimanual.py`'s other
consumer) **499/499** off-vs-on. **The numbers**: wall **497.2 / 501.1 -> 327.1 /
327.8 s** at seed 5 and **476.8 -> 312.9 s** at seed 6 (**-34.5 %**), wall/sim **2.59
-> 1.69**, wall/pick **25.1 -> 16.4 s**, placed/min wall **1.92 -> 2.93**, with the
count (16/20, 10/20), the sim span (193.3 s) and every per-leg metric unchanged; the
shared-station pair reads **317.6 -> 201.8 s** (2.22 -> 1.41). **The arithmetic**, to
quote in this order: the sim clock is **1.88x** and the lever cannot move it; the
harness factor (wall/sim) was **1.81x** the single arm's, so the wall gain was
`1.88 / 1.81 = 1.03x`; the lever takes it to **1.19x**, so the wall gain is `1.88 /
1.19 = **1.57x**` per pick; the placed **rate** multiplies that by the count, which is
a seed draw and **not** the lever's (pooled placed per attempt **0.650 vs 0.658**),
giving **1.55x pooled** (1.95x at seed 5, 1.18x at seed 6) - **so the two-line now
meets P80's disowned 1.02x bar and the standing 1.25x bar on the wall denominator,
not only on the sim denominator.** What is left (1.19x) is measured and is **not** a
poll: the two arms' control plus the permit handoff, with the shared physics step
(10.65 ms/tick = **75 % of the remaining wall**) the floor no arbiter change can
move. **Read it as a latency win, not a cheaper run**: the idle wall is denser, the
CPU *work* is unchanged (physics 51 -> 75 %, segments 15.7 -> 23.0 % of a shorter
wall) and the loop rate is unchanged (48,021 vs 47,795 rounds - **no spin**); this box
runs the cell at ~3 of 32 cores, so a saturated machine would show much less.
**P80/P81's two-line wall column (1.93 placed/min, 24.9 s/pick) is the *shipped*
behaviour and stays valid for the tree as it stands** - the knob is off - and the
knob-on numbers are the same scenario with the wait removed. **No motion reference is
re-recorded and none is owed** (`8952c320` / `eb697f23` stand: the physics cannot
move), the two-line gate `190` **PASSes** on the knob-on log against P80's own
20-attempt reference, `accept.sh` with the knob **set** reads **6/9 + `fingerprint:
matches`** (the standing rate-only FAIL), and `selfcheck.sh` is **PASS, 0 failures**.
Not measured: a saturated machine, the collector's `run_bimanual` path (it inherits
the knob), a concurrent-arm scheduler (a different design - the single permit exists
because PhysX reads are not thread-safe). Pins: `tasks.py` `e8dfa6d8`,
`bimanual.py` **`146e6252`**, `configs/*` untouched; ckpt `moe_v13s` `61da390a`.
Evidence `logs/p82/{METHOD.md,RESULTS.md,header.txt,timers.py,profile_20.py,
run_pyspy.sh,ps_agg.py,one_run.sh,run_p82.sh,run_p82_stage2.sh,apply_wake_patch.py,
p82_report.py,p82_ab.py}`, the cells `{R1,R2,R3,R4,W0,W1,W2,W3,W4,F0,F1,A1}` with
`.stamps`/`.driver`, `R3/R4.speedscope.json.gz` + `.profile.txt`, `W1.gate`,
`selfcheck.log`; WORKLOG "P82".

**P83 (2026-11-01, `logs/p83/`; default off, **nothing adopted**, no default
change, no commit, `configs/` untouched): the cell pays a full attempt for every
failure, and ending it the tick the payload is provably gone **halves the failed
attempt - by exactly 5.14 s / 617 ticks at both seeds - and the throughput does
not follow**, because the interval's other two terms absorb it.** The knob is
`FRUIT_FAIL_FAST=<mm>` (`tasks.py` `parse_fail_fast`, **unset/0 = off**): one
compare per guarded tick on the W8-B tracker's own `clean_slip_max` (the payload's
displacement in the leg's frame, the number the `[carry]` row already prints)
against the threshold, and on a trip the leg **breaks at that tick** plus the
**two early-exit sites the P7-2b monitor already uses** (the lift boundary, and
the place boundary which is *before* the release/retreat block) through one
predicate `_attempt_ended_early() = _carry_monitor_skip or _fail_fast_trip`. It
adds **no `notes` entry**, so the class is unchanged (`grasped` still comes from
the shipped peak-lift predicate, `placed` stays False → `cnp`); the payload is
recycled by `run()`'s own `finally`; the next pre-pose is the driver's
`go_ready` → `_goto` teleport, the path every shipped failure takes; **no new
exception type**, so the entry script, the collector and the two-line worker
handle it as a `not grasped` return; and the scope is **`scripted` only**
(`_fail_fast_active = threshold > 0 and scripted`), so the direct/policy handover
and the hybrid canary cannot reach it (they keep the P10-C *leg-boundary*
classifier skip, which cannot save the leg's remainder). **The floor is 100 mm and
anything `0 < mm < 100` raises at task construction**: the pre-run corpus census
(`logs/p83/census.py`, 43 scripted logs that already print `[carry]` rows, **249
placed / 165 failed** attempts joined to their own outcome rows) reads the worst
**placed** leg at **76.3 mm** (p99 62.1) and **164/165 failed** at `>= 150 mm`, so
the registered arm is **150 mm** - a 1.97x margin over the worst placed leg - and
**0/249** placed attempts ever reach it. **The A/B** (`ATTEMPTS=20`, shipped
scenario, `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`, one claim per run;
**C5** control replay, **D5/D6** tracker-only, **F5/F6** `=150` + the tracker):
**G1** C5 is **710/710 `[fruit]` lines byte-identical to P80's `S20.log`** (the
off path is inert), **G2** D5 = C5 and D6 = **S6** on **710/710** and **708/708**
physics lines - **the W8-B tracker is run-neutral on the scripted line**, so
`F` vs `C` differs by the abort alone (unlike the link-world-pose reads AGENTS
§2 forbids: `tcp_pose`, `jaw_separation`, `joint_positions` and one tactile set
per tick do not move the branch), **G3** F5/F6's first 57/59 physics lines equal
the control's with the first trip exactly at the boundary, **G4** **15/15 trips**
fire with `force = 0.00 N` *and* `contacts = 0` (and `force_min = 0.00 N`) - the
pads are empty when the displacement reaches 1.97x the worst placed leg - **G5**
**34/34 carry legs of the 17 placed attempts read `ticks = X/X`** (not one
shortened; worst placed-leg `clean_slip` 0.1 / 19.8 mm), **G7** the 20-attempt
motion budgets pass (worst descent `|v|max` 0.110-0.120 against 0.160-0.161, lurch
0.017-0.027 against 0.291; the only `105` FAIL is the standing 0.75 *rate* floor),
**G8** every run accounts and no slot is lost to the abort, and **G6 fails by its
letter only**: one new reason text (`fruit did not follow the gripper`) in each
treatment arm, from **one never-held attempt** (`sep = gap = 22.2 mm` on a 53.8 mm
fruit, `onset_row = 1`, `stored pad centre 415 mm from the measured pads`,
`force servo: gap=22.2 sep=22.2 closed=15.00 trips=38` = the R11-A.1 left
acquisition signature) whose `grasped = False` the **shipped** predicate decides -
and **the seed-6 control carries the same text** (S6/D6 1/19). **The numbers:
the failed attempt's mean span falls 15.157 → 10.013 s (seed 5) and 14.567 →
9.422 s (seed 6) = the same -5.144 s = -617 ticks**, `s/attempt` -2.80 / -2.20 s,
wall/pick -14.6 / -11.5 %; and **the interval gets worse, 26.72 → 35.26 s
(+32.0 %) and 26.12 → 27.38 s (+4.8 %)**, placed/min falls on **both**
denominators (window 2.25 → 1.70 / 2.30 → 2.19; batch 2.08 → 1.68 / 2.27 → 2.08),
`placed/min wall` 1.50 → 1.19 / 1.61 → 1.48, and the count 12 → 6 / 13 → 11.
**The decomposition is the finding**: `interval = attempts/placement × attempt
span + idle`; the span term fell and **attempts/placement rose 1.583 → 2.333
(seed 5) and 1.462 → 1.818 (seed 6)**, with idle 2.81 → 6.56 s at seed 5 (**6
starved slots**) against 4.19 → 4.11 s at seed 6 (**0 starved**) - so the abort
**is** worth -16 / -12 % of the interval *at the control's own failure rate* and
it cannot set that rate. **The seed-5 starvation is a pool state, not a trip
effect**: the post-hoc probe (`logs/p83/probe_bed.sh`, `FRUIT_BED_DIAG=1`,
reproducing F5 exactly - 14 attempts, 6 placed, 7 trips, `sim = 172.8 s`) names
every refusal at those six slots - the only body above the **0.399 m** catch floor
(the peach at 0.626) is **`diverted (max_retries)`**, the apple (0.105) and pear
(0.339) are **inside** the floor and only creep downstream 0.06 m per starved slot,
a strawberry sits on the output conveyor (`x = 1.08`), and the feeder has nothing
to release (`admitted 2 → 0`, `skipped = 85`, `pump_next` within 0.01 s of `t`) -
while the seed-6 arm starves **0/20** with the same saving. The 43 `[bed-fall]`
rows are all at `y = -0.63..-1.41, z ≈ 0.02, held = False`, i.e. P32's
unattended-belt-loss cadence artifact, **not** payloads dropped by the abort.
**Read rules from here**: quote **`placed/min wall`, not `wall/pick`** (a run that
places less divides a much smaller wall by a smaller count: 25.33 → 21.62 s/pick
with 1.50 → 1.19 placed/min); **quote the pair `clean_slip >= 150 mm` *and*
`force = 0.00 N / contacts = 0`** for a trip (the slip alone is a norm); read the
cut off the leg's own row (`[carry] ticks=<trip>/<total>`, `[motion] steps=<trip+1>`);
and treat a count difference as a **branch draw** (pooled 25/38 vs 17/34: two seeds
cannot separate "the re-timed presentation is harder" from "the branch is
harder"). **Verdict: M1/M2 PASS, M3 fails on G6's letter, T1/T2/T3 fail at both
seeds → not adopted; `FRUIT_FAIL_FAST` stays default off.** The named re-entry is a
scenario where the presentation is not the binding term - the **two-line**, whose
scheduler parks an arm on the *other arm* rather than on the belt (P80/P81), where
5.14 s per failure is a duty-cycle gain rather than re-drawn fruit. No motion
reference is re-recorded and none is owed (`8952c320` / `eb697f23` stand: C5 proves
the scripted line does not move); `scripts/selfcheck.sh` **PASS, 0 failures** with
the new leg `scripts/245_p83_failfast_selftest.py` (65 checks: the resolver table,
the 100 mm floor, the single trip site, the attempt-local latch, the `scripted`
scope, the `guard_armed` arming clause, the one-predicate early exit, no `notes`
entry, the restored step cap, the one call site). Pins: `tasks.py` `f1e44af6`,
`rl_env.py` `d786279c` (the metadata-only `TASKS_MD5` follow),
`scripts/245_p83_failfast_selftest.py` `086c6022`, `scripts/selfcheck.sh`
`39b8916f`; `configs/motion_reference.json` `8952c320` and
`..._twoline.json` `eb697f23` both **untouched**; ckpt `moe_v13s` `61da390a`.
Evidence `logs/p83/{PREREG.md,PREREG.md5,RESULTS.md,census.py,census.txt,
p83_report.py,p83_report.txt,run_p83.sh,one_run.sh,probe_bed.sh,battery_driver.log}`,
the cells `{C5,D5,F5,D6,F6}.{log,stamps,driver.log}`, `{C5,F5,F6}.gate`, the probe
`probe_bed.log`, `accept_noharm.log`; WORKLOG "P83".

**P84 (2026-11-01, `logs/p84/`; measurement only - nothing adopted, no default
change, no commit, no `src/` edit, `configs/` untouched): P83's re-entry on the
two-line. The abort is clean there, the line had already spent most of the saving,
and whether the overlap absorbs it flips sign between the two registered seeds.**
P83's named re-entry was a scenario where the presentation is not the binding term -
the two-line, whose scheduler parks an arm on the *other arm*. Cells
(`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, 20 attempts, seeds 5/6, the P80
instrumentation plus **`FRUIT_CARRY_DIAG=1 FRUIT_BIARM_PARK_TRACE=1` on both arms**,
`FRUIT_FAIL_FAST=150` on the treatment only, one claim per run): **D5 16/20,
interval 10.77 s, 2.85 placed/min wall; F5 10/20, 14.39 s, 2.01; D6 10/20, 19.34 s,
1.92; F6 15/20, 12.21 s, 2.83**. **Both controls are the P80 records again**:
`D5` = `logs/p80/T20.log` **865/865** and `D6` = `logs/p80/T6.log` **814/814**
physics `[fruit]` lines, the phase's diag rows dropped - so **the tracker and the
park trace are neutral on this line** and the A/B is the abort alone (P83 had only
proved the tracker neutral on the single arm). **The mechanism transfers, the
arithmetic does not**: 12 trips, **11/12** at `force = 0.00 N` *and* `contacts = 0`
(the 12th is F5's never-held payload, `clean_slip 354.4 mm` on tick 1, and F5's one
letter-failure is `force 9.33 N / contacts 1` at a **measured `sep 9.9 mm` with
`gap = -2.2 mm`** - the pads pressing each other, the payload **138.8 mm above**
them), **45/45 carry legs of the 25 placed attempts read `ticks = X/X`**, and a
placement is not slower (`15.51 -> 15.62 s`). The saving is **-1.48 / -1.20 s on a
never-grasped attempt** and **-3.34 s on a `cnp`** (seed 6, whose control is the
only one that drew `cnp`), against P83's **-5.14 s**: the shipped two-line **already
truncates a lost attempt twice** - `tasks.py` returns right after the lift when the
peak lift is absent (`if not result.grasped: … return result`) and the **P10-C carry
monitor is armed by default in a two-line session** (`_resolve_carry_monitor_knobs`,
confirm 8.0 mm, floor 3.5), which ends the *next* leg at its boundary (measured: **3
of D6's 5 `cnp` attempts have no `place` segment**, 9.1-10.3 s). So the fail-fast's
increment is only the rest of the tripping leg (mean remainder + 50-tick tail
**1.70 s / 1.52 s**). **The delivered side is a seed flip**: interval **+33.6 %** at
seed 5 and **-36.9 %** at seed 6 (pooled **-11.7 %**), count **26/40 -> 25/40**
(equal), and the three waiting terms move the same way as the interval - idle
19.8 -> **23.5 %** (s5, rises) but 24.4 -> **21.7 %** (s6, falls), lock-on 4.19 ->
**4.58** / 5.04 -> **4.39 s**, the right arm's **park-gate wait** 7.1 -> **9.1** /
21.8 -> **13.6 s**, starved polls 44 -> **53** / 33 -> 33. **Verdict: NOT ADOPTED** -
M1 fails on G4's letter (11/12), M2 fails at both seeds (-1.77 / -2.62 s against
P83's 3.0 s bar, because the class mix and the monitor differ), T1 and T2 fail at
seed 5, T3 passes (window 4.34 -> 4.54, batch 4.03 -> 4.05, wall 2.39 -> 2.42);
G1/G2/G5/G6/G7/G8 pass and G3 passes pooled but fails its seed-5 letter (the
`grasped, not placed` label is a class **D5 drew zero of**). **Read rules from here:**
quote the fail-fast's increment **by class** on a line with the monitor on (never
~1.2-1.5 s, `cnp` ~3.3 s), never P83's 5.14 s; a **seed is a scenario**, so a
20-attempt two-line arm needs its own reference (P80's file is seed 5 - `D6`'s is
written from P80's own `T6.log` into `logs/p84/`, never `configs/`) and the treatment
is a **DIFFERS-by-construction** arm gated on **budgets only**; and a 20-attempt
two-line A/B whose **own control swings 16 -> 10 placed between seeds** cannot
attribute a count - the branch-free read is the per-class failed-attempt span. No
motion reference moved (`8952c320` / `eb697f23` stand), no reference re-recorded,
`scripts/selfcheck.sh` **PASS, 0 failures** (no new leg: the phase adds no `src/`
code). Pins: `tasks.py` `f1e44af6`, `bimanual.py` `7e2b7d7e`, `rl_env.py`
`d786279c`, `fruits.py` `c7461d41`; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p84/{PREREG.md,PREREG.md5,RESULTS.md,p84_report.py,p84_report.txt,timeline.py,
run_p84.sh,gates.sh,one_run.sh,stamp.py,battery_driver.log}`, the cells
`{D5,F5,D6,F6}.{log,stamps,driver.log}`, `{D5,D6,F5,F6}.gate` + `D6.gate_t6`,
`{D5,D6,F5,F6}.budgets`, `motion_reference_twoline_T6_20.json`; WORKLOG "P84".

**P85 (2026-11-01, `logs/p85/`; **the shipped default changes: the scripted cell
is the bimanual two-line**) - the owner signed off the grade-pure routing
semantics the W3/R5 register held back, so `FRUIT_BIARM` and
`FRUIT_BIARM_TWOLINE` both default **1**.** Resolvers are single-sited
(`bimanual.resolve_biarm` / `resolve_twoline` / `biarm_resolution`, one per knob,
with the P43 `defaulted` origin flag) and the log names the cell:
`[biarm] scheduler: FRUIT_BIARM=1(default) FRUIT_BIARM_TWOLINE=1(default)`. The
restores are **`FRUIT_BIARM=0`** (the pre-P85 single arm) and
**`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`** (the unchanged F2 shared-station
pipeline); `tasks.two_line_enabled()` became the **session** predicate
(`session.twoline`, False outside a session) and `two_line_resolved()` is the
ambient form `run_bimanual` reads, so the single-arm and shared-station paths
cannot move. The two-line's supply package (`fruits.SupplyPlan.from_env(cfg,
two_line=...)`: dense wave sheet + balanced A:B:C) follows the same resolution
and is passed by the three scripted entries only - `SortingRLEnv` and
`scripts/60_eval_policy.py` pin `two_line=False` (neither is the scripted cell),
so no direct/policy number moves, and `scripts/accept_policy.sh` has **no path**
to the flip (it builds its own `FruitSpawner`/`PickAndPlaceTask`, never a
`CoopSession`).

**The flip is resolution-only, proved three ways.** The default 20-attempt runs
replay the pre-flip *explicit* two-line records line for line modulo the phase's
instrumentation rows: seed 5 **865/865** vs `logs/p80/T20.log`, seed 6
**814/814** vs `T6.log`, and the accel treatment **799/799** vs `V20.log` (the
union's opt-in two-line arm). Delivered (seed 5): **16/20, 9.70 s/attempt,
interval 10.77 s, 5.57 / 4.96 placed/min, wall/pick 16.57 s, 2.90 placed/min
wall** - P80's numbers with P82's wall (331.4 s against T20's 497.2 s). The
single-arm control (`FRUIT_BIARM=0`, same batch) is **346/346 identical to
`logs/p71/accept_rails_none.log`** with `fingerprint: matches` the archive, so
the restore is byte-exact; its rate-only FAIL (6/9 < 0.75) is this tree's
standing branch, not a P85 effect.

**The acceptance moves scenario and its gate becomes honest.** `scripts/accept.sh`
now reads the session from its own log: a two-line session is gated by
`scripts/190_twoline_gate.sh -r configs/motion_reference.json -m 0.60` (the
scenario pin, the two-line floor and the per-scenario reference - one definition
of "a two-line gate", never a second floor inside 105), anything else by 105 with
`configs/motion_reference_single.json`; `selfcheck.sh`'s optional motion leg takes
the same branch. The acceptance reads **7/10, 9.2 s/attempt**, is **424/424
identical to `logs/p80/T10.log`** and **matches `configs/motion_reference_twoline.json`**
- i.e. the flip's acceptance scenario *is* the two-line dense scenario the repo
already had a reference for. Re-recorded: `configs/motion_reference.json`
`8952c320` -> **`eb697f23`** from `logs/p85/accept10.log` (archive
`logs/p85/motion_reference_single_pre_p85.json`, also shipped as
`configs/motion_reference_single.json` for the restore path);
`configs/motion_reference_twoline.json` is **untouched** (same scenario, same
bytes). The collector inherits the flip and its shard manifest gains
`collection.{biarm_resolved,biarm_twoline_resolved,biarm_defaulted,biarm_twoline_defaulted}`
next to the raw strings (which read `"0"` when unset) - **a manifest without
those four keys predates P85** - and `scripts/153_biarm_rates.sh` now names its
modes explicitly (`two-line` = shipped, `shared` = the pre-P85 `FRUIT_BIARM=1`,
`single`), while `scripts/126_branch_probe.sh` pins `FRUIT_BIARM=0` (it probes
the legacy single-arm branch it was written for). `scripts/demo_2min.sh` runs the
shipped cell (3-pick smoke **1/3**, clip `logs/video_demo/` 1705 frames / 56.8 s,
motion gate **PASS** with the scenario's own 0.33 three-pick floor).

**The acceleration cell (P85-ACC, `logs/p85/ACCEL.md`)**: the P44 speed union
re-priced on the now-default line (the park/lock-on family is the larger wall
term - 18-21 % per-arm idle, a 7.1-21.8 s park-gate wait, 4.19-5.04 s lock-on -
but every lever on it is already spent or measured negative, so the union is the
only unspent knob). **The mechanism transfers exactly** - `place` 3.19 -> 2.35,
`release` 2.35 -> 1.63, `lift` 1.65 -> 1.52, **-1.00 s/attempt at both seeds** -
and **the delivered side is a branch draw whose sign flips**: seed 5 16 -> 13
placed (window -3.7 %, 2 new `grasped, not placed`, zero-force legs 4 -> 7),
seed 6 10 -> 14 (window +60 %, guard better), pooled 26 -> 27 of 40. Not adopted
(E2/E3 fail at seed 5); the count moved less than one interval in both
directions, and the class that moves is `logs/p42/SIM_LIMIT.md`'s closed one.
No default changed. Pins: `tasks.py` `f07a865a`, `bimanual.py` `9b7fc33f`,
`fruits.py` `dcabe16b`, `rl_env.py` `TASKS_MD5` follow, `scripts/246_p85_selftest.py`
(new selfcheck leg), `scripts/accept.sh`, `scripts/selfcheck.sh`; references
`8952c320` (single) / `eb697f23` (two-line, and now also the shipped acceptance
reference). **Re-baseline: every rate, acceptance, collector shard and store
recorded before P85 is a single-arm (or explicitly opt-in two-line) number.**

**P86 (2026-11-01, `logs/p86/`; measurement only - **nothing adopted, no default
changed, no commit, `configs/` untouched**): the release block is `-0.64 s` of
pure dwell and it is **exact at both seeds**, but the phase's own pinned span
clause and one motion leg keep it out of the tree.** The cell is P44's S2 knob
(`FRUIT_SPEED_RELEASE=1`: dwell **20 -> 0**, pad ramp **40 x (3 -> 2)**, finger
ramp **16 x (3 -> 2)** = **-76 ticks = -0.633 s** at 120 Hz,
`FRUIT_RELEASE_RESYNC` off), run on the **shipped two-line** at `ATTEMPTS=20`,
seeds 5/6, with the same instrumentation on all four cells (`FRUIT_PLACE_TRACE`
included). **Admissibility: both controls replay P85's records line for line
(C5 **865/865** = `logs/p85/base20_s5.log`, C6 **814/814** = `base20_s6`), so the
tree is unchanged *and* the per-place landing trace is inert.** **The mechanism
(P1a, PASS):** the `[cycle] release=` segment - 2.33 s of a 15.78 s per-arm span,
the second of the three profile blocks - falls **-0.615..-0.640 s = 74-77 ticks
in all four arm-seed cells** by median (means -0.65 / -0.56; pooled mean
2.324 -> 1.714 = -0.611 s, median 2.325 -> 1.680 = -0.645 s), against the
arithmetic's -0.633 s. The two extreme means are one 1.63 s control leg (C6) and
one 1.92 s treatment leg (R6), both `place low` descents inside the segment.
**The delivered side (P2, PASS):** the pooled interval falls at **both** seeds
(10.77 -> **10.59** and 19.34 -> **11.08** s) and on **both arms at both seeds**;
the seed-5 pair is the clean one (identical 16/20 and identical 9/10 + 7/10 arm
split, so -0.18 s pooled / -0.48 s arm span is the lever alone) while seed 6's
-8.26 s is **confounded with a +2 count draw** (`interval = attempts/placement x
span + idle`). `s/attempt` 9.70 -> 9.50 / 9.10; window 5.57 -> 5.66 and 3.10 ->
5.41 placed/min; batch 4.96 -> 5.05 and 3.11 -> 3.94; `placed/min wall`
**2.88 -> 2.95** and **1.91 -> 2.34** (wall -2.2 % / -1.9 % - the arbiter's
per-tick cost is flat, so the wall follows the sim clock). **The landing is clean
(P3, PASS)** - **28/28** payload-present releases land `on_belt` (16/16, 16/16,
10/10, 12/12) in the control's own height/impact/bounce band
(31.8-64.3 mm, -0.93..-0.45 m/s, bounce <= 5.6 mm), the upstream-lost traces read
`release_bottom = -184 mm` and are reported separately (C6 has one, the control's
own `SIM_LIMIT` class) - i.e. P44 §9.4 reproduced on the two-line and P45's
displacement-controlled ramp confirmed. **The ledger gains no class (P4, PASS)**
at either seed; the counts shift at seed 6 (never-grasped 5 -> 1, `cnp` 5 -> 7),
the re-timed presentation drawing a different fruit, and the `force_min == 0.00`
loaded-slide guard is flat at seed 5 (4 -> 4) and **better** at seed 6 (11 -> 7).
**What fails, and why it matters:** **(1) P1b, the attempt-span instance of the
same claim** - registered at `-0.633 +- 0.12 s` per seed and per arm, it reads
**-0.41 / -0.57** (seed 5) and **-0.27 / -0.96** (seed 6) and fails its band at
both seeds. **The miss is not the lever**: the residual ("span - block") is
**+0.17 / -0.12 s**, sign-flipping - the acquisition blocks re-draw with the
shifted attempt boundary (`descent` +0.24 at seed 5, `grip` -0.35 and `place`
-0.17 at seed 6) - and over two seeds the span saving (-0.575) tracks the block
to 0.04-0.07 s. **A per-seed attempt span is not branch-free**, so it is not a
valid second leg for a profile cell (P44 §3's caveat, which this phase's PREREG
§7 wrongly denied); the branch-free instance is the block itself and it passes
exactly. The named re-entry registers the block + the interval and reads the span
as a report. **(2) G2, the motion guard, FAILS at R6 on one leg** - the log's
12th descent (cycle attempt 12: **right** arm, kiwi, **placed**, lift +0.559 m)
reads `|v|max` **0.164** against the 0.160/0.161 budget (**2.5 % over**,
`a_med` 0.57 peaking at 0.68 of the leg, `end = 12.6 mm` short, lurch 0.036 of
the 0.291 bound); C5 0.112, R5 0.111, C6 0.132. The descent profile is **not
touched by this cell** and AGENTS §2 forbids re-tuning the budget to admit a
configuration, so it is recorded as a failed guard: the trim shifts the attempt
boundary, the catch is presented a different fruit at a different belt offset,
and one leg of one seed pays it. **Gates:** C5 `190` **PASS** vs
`logs/p80/motion_reference_twoline_p80_20.json`; C6 `190` **PASS** vs the seed-6
reference written **from C6 itself** into `logs/p86/` (a seed is a scenario -
never `configs/`); R5/R6 recorded **DIFFERS by construction** (the fingerprint
carries each leg's duration) and gated on budgets only. **Verdict: PREREG §5's
letter = NOT a win (no default change); the sponsor's four-clause rule (block,
interval, landing, ledger) passes at both seeds**, so the cell is a measured
positive whose adoption package is **priced and not executed** (RESULTS §9): a
**two-line scope first** (the knob is read at a shared site, so a global default
would also move the single arm, the hybrid canary and the scripted collector),
three references re-recorded from same-batch runs if the flip is global,
`physics.release={dwell,pad_hold,finger_hold}` in both manifests **before** any
recollection, and a 2-seed 40-attempt budget run of the trimmed branch. Pins:
`tasks.py` `f07a865a`, `bimanual.py` `9b7fc33f`, refs `eb697f23` / `8952c320` /
`eb697f23` **untouched**, ckpt `moe_v13s` `61da390a`; no new selfcheck leg (env
only). Evidence `logs/p86/{PREREG.md,PREREG.md5,RESULTS.md,p86_report.py,
p86_report.txt,run_p86.sh,gates.sh,header.txt,battery_driver.log}`,
`{C5,R5,C6,R6}.{log,stamps,driver}`, `{C5,C6}.gate`, `{R5,R6}.gate`,
`{C5,R5,C6,R6}.budgets`, `motion_reference_twoline_C6_20.json`; WORKLOG "P86".

**P87 (2026-11-01, `logs/p87/`; **one shipped change: the release trim is the
two-line session's default** - scoped, not global - and nothing else moved): the
gap displays **-0.64 s of pure dwell at both seeds**, the scope is proven
**bit-for-bit**, and one descent leg on one seed keeps the flip in the
"considered trade" tier rather than a clean pass.** P86 measured the S2 cell and
priced it; the blocker to shipping it was that the release block is read at a
site **every** presentation shares (`_grasp_carry_place_impl`), so a *global*
default would also move the single arm, the shared-station pipeline, the hybrid
canary (`60_eval_policy.py` builds its own `PickAndPlaceTask`) and the scripted
collector - none of which P86 measured. P87 ships it **two-line-scoped**, the
`_dynamic_profile` pattern: **`FRUIT_SPEED_RELEASE` now resolves ON for a
two-line session** (`dwell` **20 -> 0**, the pad/finger settles **3 -> 2** =
**-76 ticks = -0.633 s** at 120 Hz, `origin=default`) and **off everywhere else**
(`origin=scope-off`, the shipped 20/3/3). **`FRUIT_SPEED_RELEASE=0` restores** on
the two-line too, an explicit **`=1` still wins globally** (as does
`FRUIT_SPEED_ALL=1`, the S13 union; an explicit `=0` beats the union), and
`FRUIT_SPEED_RELEASE_SETTLE` still moves the settle, read only when the cell is
on. One resolver (`tasks.release_speed_resolution`) feeds the per-attempt holds,
the new **`[fruit] [biarm] release profile:`** row and the store manifest's
**`physics.release`** block; the scope argument is
**`Task.two_line_enabled()`** (the `CoopSession` predicate), so a path with no
session cannot arm it. **The gate (PREREG `738c1b54`, pinned before the runs;
`ATTEMPTS=20`, seeds 5/6, arms = `FRUIT_SPEED_RELEASE=0` vs unset, P86's
instrumentation on both):** **G0 - the flip is resolution-only, proved by
replay**: the four cells are **byte-identical to P86's own four** on the
`[fruit]` stream (`C5` **865/865** = `logs/p86/C5.log`, `T5` **868/868** =
`R5`, `C6` **814/814** = `C6`, `T6` **821/821** = `R6`, dropping the diag rows
**and the one new row**, which reads `=1(default)` where P86's treatment read
`=1(explicit)`) - **so the shipped default *is* the measured arm, bit for bit**,
and P86's whole measurement transfers. **P1a PASS both seeds**: the `[cycle]
release=` **median** falls **-0.645 / -0.640 s** (**77 / 77 ticks**) against the
registered -0.633 +- 0.03, and in **all four arm-seed cells** (-0.640/-0.640 at
seed 5, -0.635/-0.615 at seed 6). **P2 PASS both seeds** - the pooled interval
**10.77 -> 10.59** and **19.34 -> 11.08 s**, and on **both arms at both seeds**;
the seed-5 pair is the clean read (16/20 identical, same 9/10 + 7/10 split, so
the -0.18 s is the lever), seed 6's -8.26 s carries a +2 count draw. **P3 PASS**
(**28/28** payload-present releases `on_belt`, in the control's own
height/impact/bounce band: 32.1-64.3 mm, -0.93..-0.61 m/s, bounce <= 4.9 mm);
**P4 PASS** (no new reason key at either seed; the `force_min == 0` loaded-slide
guard flat at seed 5 (4 -> 4) and better at seed 6 (11 -> 7)); **P5 (reported,
never gated)** window **5.57 -> 5.66 / 3.10 -> 5.41** placed/min, batch **4.96 ->
5.05 / 3.11 -> 3.94**, wall **328.4 -> 325.4 / 308.2 -> 306.3 s**,
**`placed/min wall` 2.92 -> 2.95 / 1.95 -> 2.35**. **P6 is the one clause that
misses its clean-pass form**: **seed 5 is clean (0/20 legs)** and **seed 6 has
exactly one leg over budget** - leg 12, a 5.9 cm descent, `|v|max` **0.164**
against its **0.160** per-leg budget (2.5 % over, lurch 0.036 of 0.291) - which
is **the same leg P86's R6 recorded**, so the 40-attempt sample answers P86's
open question the only way it could: the excursion is a **deterministic property
of that seed's branch**, not a random draw and not a systematic cost (T5's worst
is 0.111). By PREREG §5's pre-registered tier that is a **CONSIDERED TRADE -
ship, P6 documented**, not a clean pass; the budget was **not** re-tuned (AGENTS
§2) and the named next spend is a third seed if the owner wants it priced
further. **The inertness is proven, not argued**: `FRUIT_BIARM=0
scripts/accept.sh` is **346/346 raw byte-identical** to
`logs/p71/accept_rails_none.log` (**the new row does not print on the single
arm at all** - 0 occurrences) with `fingerprint: matches
configs/motion_reference_single.json`, and the shared-station pair (`=1
FRUIT_BIARM_TWOLINE=0`, 4 attempts, unset vs `=0`) is **identical on all 218
other `[fruit]` lines** with the **same resolved clock** (20/3/3, 188 ticks) -
the one difference is the row's `origin` field (`scope-off` vs `explicit`),
which is what the label is for; that is **PREREG deviation A1**, recorded in
`logs/p87/RESULTS.md`. **`190`**: C5 **PASS** vs P80's seed-5
20-attempt reference, C6 **PASS** vs P86's seed-6 record; T5/T6 **DIFFER by
construction** and were gated on budgets only. **Re-recorded, two-line side
only**: `configs/motion_reference.json` `eb697f23` -> **`423896f7`** and
`configs/motion_reference_twoline.json` `eb697f23` -> **`423896f7`** (both from
`logs/p87/accept10.log`; the pre-flip pair is archived at
`logs/p87/motion_reference_pre_p87.json` /
`..._twoline_pre_p87.json`); **`configs/motion_reference_single.json`
`8952c320` is untouched**. `scripts/234` (P64) pinned the P85 *value*; it now
pins the *arrangement* (acceptance == two-line record, single-arm = `8952c320`),
which is the invariant that can break. **Provenance before any recollection**:
`scene._release_provenance` writes `physics.release={dwell, pad_hold,
finger_hold, ticks, shipped_ticks, saved_ticks, profile, origin, two_line,
label}` in **both** manifest writers (the collector passes its own `TWO_LINE`,
the direct env `False`), so a store **without** the key predates P87. The
acceptance on the final tree reads **7/10 = 70 %, 9.4 s/attempt,
`fingerprint: matches`, `190: PASS`** (`logs/p87/accept_final.log`, byte-identical
to the reference-source run); selfcheck **PASS (0 failures)** with the new `247`
leg. **Re-baseline: every two-line rate, span or interval recorded before P87 is
a 2.35 s-release number; `FRUIT_SPEED_RELEASE=0` restores it** (compose with
`FRUIT_ARM_PARK=ready` for pre-P43, `FRUIT_POLICY_TRIGGER_ACQ=0` for pre-P54 and
`FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=0` for the
pre-P58 **direct** profile - which this flip never reaches). Pins: `tasks.py`
**`6b267ecc`**, `scene.py` **`047d9e7b`**, `rl_env.py` **`96076c8b`**
(metadata-only `TASKS_MD5` follow), `scripts/40_collect_demos.py` **`77e0331f`**,
`scripts/247_p87_release_scope_selftest.py` **`a4aa4756`**, `scripts/225`
**`395d3cd3`** (the scoped-call census), `scripts/234` **`ec1118be`**;
`configs/motion_reference.json` `423896f7` / `..._twoline.json` `423896f7` /
`..._single.json` `8952c320`; ckpt `moe_v13s` `61da390a`. Evidence
`logs/p87/{PREREG.md,PREREG.md5,RESULTS.md,p87_report.py,p87_report.txt,
run_p87.sh,run_p87_extra.sh,gates.sh,gates.out,header.txt}`, `{C5,T5,C6,T6}.{log,
stamps,driver}`, `{C5,T5,C6,T6}.gate`, `{C5,T5,C6,T6}.budgets`,
`single_accept.*`, `shared_{unset,zero}.*`, `accept10.*`, `accept_final.*`;
WORKLOG "P87".

**P88 (2026-11-01, `logs/p88/`, default off, **nothing adopted**): the place
block is the largest remaining one and the cell's mechanism is exact - but the
delivered interval rises at both seeds, so `FRUIT_SPEED_PLACE` stays off.** The
shipped cell (two-line + P87's release trim) has `place` as its largest block
(**3.14-3.19 s** against `release` 1.70 and `lift` 1.65), and P44's S1
(`v_max` 0.35 -> **0.52** at the shipped `a_max` 1.089, inside the 0.61 m/s
ceiling) is the only unspent one of the three. The phase built the same
**two-line-scoped** form as P87 - one resolver (`tasks.place_speed_resolution`),
the consumer `speed_cell_defaults(self.two_line_enabled())` at `_carry_leg`, the
`[biarm] place profile:` row and the manifest's `physics.place` - and measured
it with the controls at `FRUIT_SPEED_PLACE=0` and the treatments unset:
**P1b is exact on every leg** (the per-leg tick count against the profile
re-generated at 0.52 from that leg's own printed distance: median **0.0 / +0.5
ticks, max |2|**; `|v|cmd` equals the profile's own peak to **<= 0.009 m/s**;
median leg **0.508 m/s** against the control's 0.341-0.343), and **the block is
exactly `transit(0.52, d) + 0.583 s`** - the `place low` rest is **0.583 s
(0.578-0.588) in all four cells**, so the treatment's own median is predicted
from its own legs to **-0.008 / +0.014 s**. **The registered gate fails
anyway**: **P1a** at seed 5 (**-0.770 s** against the predicted -0.904 = **0.134 s**
against a +-0.12 band - the miss is the **leg mix**, because the block is
distance-dependent and a median is not branch-free for a transit; the mean
matches to **0.002 s**), **P2 at both seeds** (10.59 -> **13.23** and 11.08 ->
**12.11 s**), and **P4a at seed 5** (one `grasped, not placed (no note)` row, a
ledger bucket present in **3 of the 4** cells). **The class guard's substance is
negative**: place-leg escapes **0/27** in the treatment against **1/29** in the
control, all-leg escapes **5 vs 8**, `force_min == 0` **6 vs 8**; the landing is
clean (**16/16, 11/11, 12/12, 15/15**); both treatments' descent budgets are
clean (0/20 each; the control's seed-6 leg 12 at **0.164 vs 0.160** is
P86/P87's standing branch leg). The delivered read: seed 5 places **16 -> 11**
(the left's never-held **1 -> 4**, `force@onset = 0.00 N`, `sep@onset` 59-63 mm -
the pre-contact acquisition class, not the place transfer), seed 6 places
**12 -> 15** over a **wider** window, so **pooled 28 -> 26 of 40** and
**`placed/min wall` 2.65 -> 2.61 (-1.6 %)** while the wall itself falls 5.6 %.
**Nothing moved**: `configs/motion_reference.json` / `..._twoline.json` =
`423896f7` and `..._single.json` = `8952c320` are untouched, the final
acceptance reads **7/10, 9.4 s/attempt, `fingerprint: matches`, `190: PASS`**,
and the shipped tree is inert three ways - C5/C6 replay P87's T5/T6 **868/868**
and **821/821** on the `[fruit]` stream, a fresh unset 20-attempt run (`N5`)
replays C5 **868/868**, and the single arm is **346/346 raw** identical with the
profile rows absent (the shared station's clock is unchanged, `--profile`). The
measured arm is reproducible as `FRUIT_SPEED_PLACE=0.52`; the re-entry is a
scenario where the place block **binds** the interval (not the count) or a
class-first registration argued on the wall alone. Pins: `tasks.py`
**`23430d50`** (`PLACE_TWO_LINE_DEFAULT = False`), `scene.py` **`1ec3b8f8`**,
`rl_env.py` **`3ac60be8`** (the `TASKS_MD5` follow),
`scripts/248_p88_place_scope_selftest.py` (new selfcheck leg),
`scripts/225`/`247` re-pinned for the second scoped consumer. Evidence
`logs/p88/{PREREG.md,PREREG_A1.md,PREREG_A2.md,RESULTS.md,p88_report.py,
p88_report.txt,gates.out,accept_final.*}`, `{C5,T5,C6,T6}.log`, `N5.log`,
`single_accept.*`, `shared_*`; WORKLOG "P88".

## 3. What changed -> what to run

| you changed | run |
| --- | --- |
| a **throughput or rate** claim (a speed profile, a scheduler/supply change, a wall number) | `scripts/186_w6_report.py` on **>= 2 seeds** with **both denominators** (placement window and batch span) **and the wall column** (`logs/p80/p80_report.py` is the template: wall from per-line stamps, never inferred), that scenario's own motion gate (single arm: `105 --fingerprint configs/motion_reference.json`; two-line: `scripts/190_twoline_gate.sh` against a reference of the **same attempt count**), then `scripts/accept.sh` |
| a **per-leg profile or dwell** change (`FRUIT_SPEED_RELEASE/PLACE/LIFT`, a `[cycle]` block that moves) | `FRUIT_CYCLE_REPORT=1 FRUIT_PLACE_TRACE=1` on **both** arms, **>= 2 seeds**, then the `[cycle]` per-leg block table **by median** (`logs/p86/p86_report.py --blocks`): the **block** is the mechanism, **never the attempt span** - the span carries the supply-phase acquisition legs and re-draws with the shifted attempt boundary (`logs/p86/RESULTS.md` §3, P44 §3). Delivered: the interval (pooled **and** per arm), both denominators, the wall and `placed/min wall`. Landing: `FRUIT_PLACE_TRACE`'s `on_belt` on **every payload present at the release** (`release_bottom >= 0`; the -184 mm rows are the upstream-lost class, reported separately). Then the scenario's own motion gate - a profile change **moves the fingerprint by construction**, so budgets-only for the treatment and a same-seed reference for its control |
| the **release clock's scoped default** (`tasks.release_speed_resolution`, `speed_cell_defaults(two_line)`, the `[biarm] release profile:` row, `scene._release_provenance`, the manifest's `physics.release`) | `scripts/selfcheck.sh` (the `247` leg: the resolver table - unset/no-scope **is** `_SPEED_SHIPPED` exactly, unset/two-line is the trim, `=0` restores, `=1`/`FRUIT_SPEED_ALL` win globally, `=0` beats the union, the settle is read only when on - the clock arithmetic, the single scoped call site, the row printing only inside `run_bimanual`, and `physics.release` in both writers), then **the replay first**: the same-seed cells must be **byte-identical to the pre-flip record** on the `[fruit]` stream with the phase's rows dropped (`logs/p87/p87_report.py --same`; P87's four cells are 865/865 / 868/868 / 814/814 / 821/821 against P86's), then **the inertness pair** - `FRUIT_BIARM=0 scripts/accept.sh` **raw 346/346** against `logs/p71/accept_rails_none.log` (+ `fingerprint: matches configs/motion_reference_single.json`) and a shared-station `=1 FRUIT_BIARM_TWOLINE=0` pair unset-vs-`=0` compared with `--same` **and** `--profile` (the row's `origin` field legitimately differs; the **clock** must not) - then a 10-attempt shipped acceptance to re-record the two-line references, then `scripts/accept.sh` |
| the **place cap's scoped cell** (`tasks.place_speed_resolution`, `PLACE_TWO_LINE_DEFAULT`, the `[biarm] place profile:` row, `scene._place_provenance`, the manifest's `physics.place`) | `scripts/selfcheck.sh` (the `248` leg: unset/no-scope **is** `_SPEED_SHIPPED` exactly, unset/two-line is **also** the shipped pair because the default is off, the explicit `=0.52` is the measured arm with its **362 -> 244-tick** clock at the named **0.55 m** reference, the override table, the profile clock reproducing `motion.jerk_limited` in **both** the speed- and acceleration/jerk-limited regimes, both consumers on the session predicate, the row printing only inside `run_bimanual`, and `physics.place` in both writers), then the same replay/inertness shape as the release row (`--same` against the pre-change record, `FRUIT_BIARM=0 scripts/accept.sh` **raw 346/346**, the shared-station `--profile` pair), and read the delivered side on **both denominators**: the interval **is** `window/(n-1)`, so the window rate and the interval are **one statistic** - a place cell that lengthens the placement window reads as a worse interval even with more placements (`logs/p88/RESULTS.md` §3) |
| docs, or a number's provenance/data size | `python3 scripts/106_index_audit.py` and `python3 scripts/107_collect_merge_test.py` |
| motion, control, `trajectory` limits, IK | `python3 scripts/96_motion_check.py`, then `scripts/accept.sh` |
| collection (`40_collect_demos.py`) or merging (`41_merge_demos.py`) | `scripts/107_collect_merge_test.py`, then `python3 scripts/106_index_audit.py` |
| simulator behaviour, scene, gripper, conveyor | `scripts/accept.sh`, then `scripts/demo_2min.sh` |
| the supply schedule (`fruits.py`, `bed.py`) | `python3 scripts/211_bed_audit.py`, then `scripts/selfcheck.sh` |
| the bimanual scheduler (`bimanual.py`, or the task loop under `FRUIT_BIARM=1`) | `scripts/selfcheck.sh` (the 152 leg), the rate batch (`scripts/153_biarm_rates.sh two-line 5`; `shared` and `single` are the other two modes), then `scripts/accept.sh` (it gates whatever session it ran) |
| the **shipped scheduler default** (`bimanual.resolve_biarm`/`resolve_twoline`, `tasks.bimanual_enabled`/`two_line_enabled`, the supply package's `two_line=` scope, `scripts/accept.sh`'s gate branch) | `scripts/selfcheck.sh` (the `246` leg: the resolver table, the session scope, the entry wiring, the manifest keys, the accept branch), then **both restores** - `FRUIT_BIARM=0` at ten attempts against `configs/motion_reference_single.json` and a `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0` smoke - then a 20-attempt default rate run compared line-for-line with the pre-flip record (drop only `[fruit] [carry]`, `[fruit] [diag] carry-assist` and the `[biarm] scheduler:` banner; `logs/p85/p85_report.py --same-with-diag`, template `logs/p85/RESULTS.md`), then `scripts/accept.sh` and `scripts/demo_2min.sh` |
| the arbiter / main-thread bridge (`bimanual.py` `TickRelay`, `MainBridge`, `CoopSession`), or anything that claims a **wall** speedup on the two-line | `scripts/selfcheck.sh` (the 152 leg), then **the same cell twice** (knob unset vs set) with `logs/p80/stamp.py` and require the `[fruit]` stream to be **byte-identical** (`python3 logs/p82/p82_report.py --same <control.log> <cell.log>`) - a scheduler change must not move the physics - plus `scripts/190_twoline_gate.sh` on the cell (its own reference for its own attempt count) and one `FRUIT_BIARM=1` pair for the shared-station consumer; read the wall with `logs/p82/p82_ab.py` and quote **wall/sim**, `wall/pick` and `placed/min wall` against the single arm at **>= 2 seeds** (`logs/p82/RESULTS.md` §4-§6). The arbiter's idle is measured by `logs/p82/timers.py`; do not add per-tick timers to `ik_step` (AGENTS §2) |
| the policy, training or the dataset schema | `scripts/selfcheck.sh`, `scripts/accept.sh` (scripted baseline), `scripts/accept_policy.sh` (policy loop) |
| the direct supply profile (`rl_env.py` `_resolve_supply_profile`, the `fruits.py`/`tasks.py` kwargs) | `scripts/selfcheck.sh` (the `230` leg), `scripts/accept.sh` (import guard: 377/377 + `fingerprint: matches`), one two-line run + `scripts/190_twoline_gate.sh`, `python3 scripts/211_bed_audit.py` |
| the output station (`assets.py` `output_rails` / `output_belt_top_z`, `conveyor.OutputBelt`) | `scripts/selfcheck.sh` (the `238` leg), `scripts/accept.sh`, one two-line run + `scripts/190_twoline_gate.sh`, then the direct cell with `FRUIT_CARRY_DIAG=1` (the crossing `clr`/`clr_win` **and the P72 corner `clr_edge`/`clr_edge_min`** per held place leg, read with `logs/p72/p72_report.py --check`) - and re-record both references if the flip is shipped (`logs/p71/RESULTS.md` §5) |
| the scene's collider set or a store's provenance (`assets.scene_provenance`, the manifests) | `scripts/selfcheck.sh` (the `239` leg), then one collection or direct run and check its `manifest.json` carries the `scene` block (`logs/p72/manifest_probe.py` does it without a simulator app) |
| a new default-off diagnostic field on the `[carry]` row (or a new `[place]`/`[seat]` line, or a new `[place-trace]` per-tick print) | `scripts/selfcheck.sh` (the field's own leg - `235`/`239`/`240`/`241` are the pattern), then **one direct run with `FRUIT_CARRY_DIAG=1`** to read it, then `scripts/accept.sh` and require its **346/346 `[fruit]` lines** to be byte-identical to the pre-change record - a diag-only change must be inert on the scripted path (`logs/p73/P1_RESULTS.md` §5, `logs/p75/RESULTS.md` §5) |
| the finger drive's force cap, or a leg-scoped drive write (`FRUIT_FINGER_MAXFORCE`, `FRUIT_FINGER_MAXFORCE_SCOPE=place-left|grasp-left`/`..._SCOPED`, `tasks.finger_cap_scope_for`, `_carry`'s wrapper) | `scripts/selfcheck.sh` (the `244` leg), then **one direct run with `FRUIT_CARRY_DIAG=1`** and read the `[drive] ... finger cap raise/restore` rows **and** the delivered force by leg class - **the site proof is the pair**: `place-left` -> `place*` at the scoped cap with `grasp_lift` at ~9.7 N (`logs/p78/RESULTS.md` §0), `grasp-left` -> `grasp_lift` at the scoped cap with `place*` at ~10 N (`logs/p79/RESULTS.md` §1); then `scripts/accept.sh` + one two-line run + `scripts/190_twoline_gate.sh` **with the knob armed** and require **346/346 `[fruit]` lines + both fingerprints** to be unmoved (`logs/p78/RESULTS.md` §7, `logs/p79/RESULTS.md` §6) - the scoped form must move no reference; a **global** `FRUIT_FINGER_MAXFORCE` instead owes both references and every store. Read `fmax` as a **peak transient** that exceeds the cap on single legs even at 10 N, and `force_min` as the leg's weakest moment - neither is a `place*`-was-re-clamped test on one cell (`logs/p79/PREREG.md` §9 A1); the structural rows are |
| an **early end of a carry leg** (a new skip/trip on `_carry_monitor_skip`/`_fail_fast_trip`, a new threshold, `_attempt_ended_early`, or a new failure path out of `_grasp_carry_place_impl`) | `scripts/selfcheck.sh` (the `245` leg is the pattern: the resolver table, the refuse-below floor, **one** trip site, the attempt-local latch, the scope, the arming clause, and that the trip adds **no `result.notes` entry**), then **the tracker-only control first**: `FRUIT_CARRY_DIAG=1` alone on the same seed must be **byte-identical** to the shipped run (`--same`, diag rows dropped) - otherwise the treatment differs by instrumentation and no time claim is admissible (`logs/p83/RESULTS.md` §6 G2) - then the A/B against **that** control on **>= 2 seeds**, reading **the failed attempt's own span** as the mechanism number (branch-free) and the interval/count as the claim, plus `scripts/accept.sh` and require its `[fruit]` stream to be byte-identical to the pre-change record |
| a **two-line A/B** (a per-attempt knob on the scripted primitive reaching `run_bimanual`, e.g. `FRUIT_FAIL_FAST`) | the same protocol, with four two-line differences: (a) the control must replay **that scenario's own** record modulo the phase's diag rows (`logs/p82/p82_report.py --same`, dropping `[fruit] [carry]`, `[diag] carry-assist` and `[biarm] … park`) - P84's `D5`/`D6` are `logs/p80/{T20,T6}.log` at **865/865** and **814/814**; (b) **each seed is its own scenario**, so every seed needs its **own** 20-attempt reference (P80's file is seed 5; write another seed's from its own record into `logs/`, **never** `configs/`), and the treatment is a **DIFFERS-by-construction** arm gated on **budgets only** (`105 --min-success-rate 0.0`); (c) the interval is split over two overlapping arms, so quote the pooled **and** per-arm interval, both denominators, the wall and the **park-gate wait / lock-on / idle** triple - the "the overlap absorbs the abort" read; (d) the saving must be quoted **by class**: the shipped two-line already truncates a lost attempt twice (the `not result.grasped` return after the lift and the **P10-C monitor**, armed by default in a two-line session), so the fail-fast increment is ~1.2-1.5 s on a never-grasped attempt and ~3.3 s on a `cnp`, not P83's 5.14 s - and a 20-attempt two-line count is a branch draw whose **own control swings 16 -> 10** between seeds (`logs/p84/RESULTS.md` §2/§4) |

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
