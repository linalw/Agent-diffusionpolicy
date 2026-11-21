# P225 - the no-scripted-skill target: 0.15 m/s, 5/8 = 62.5 %, 6.6-9.9 s per fruit

**Question (owner, 2026-11-19).** Sort the moving-belt cell with **no scripted
skill padding the count**: success **> 55 %**, **< 12 s per fruit**, belt
**> 0.08 m/s**, starting slow and raising the belt. The 17 papers under
`/home/ubuntu/linalw/Projects/Agent-diffusionpolicy/papers` are the method source.

**Answer, stated with its boundary.** The hierarchical learned lane - the
diffusion policy's own fruit/arm/bin decisions and approach, plus the two
analytic measured-target servos - clears the target at **0.12 m/s**
(`6/8 = 75 %`, `7.3-11.6 s`) and at **0.15 m/s** (`5/8 = 62.5 %`, `6.6-9.9 s`),
with **no `task.run` route armed**. The raw policy with the servos removed is
**0/7**: the analytic contact/place servos are load-bearing, and that is
measured and reported, not hidden (section 5). The right arm is the residual
(38 % on the five-seed record, 3/13 in this phase's cells).

## 1. What "no scripted skill" means here

The two routes the earlier hybrid used are **off** in every cell of this phase:

```bash
FRUIT_SMALL_HANDOVER=0      # <= 4 cm fruit is NOT routed to task.run
FRUIT_HANDOVER_SIDE=        # no arm is routed to task.run
FRUIT_POLICY_HANDOVER=0     # the policy's own attempt, no primitive handover
```

`rl_env.act()` reaches `_run_scripted()` only through those switches or
`--ablate scripted`; none is armed. Every attempt is the diffusion policy's own
approach + close command + lift, with the two measured-target servos serving the
pose. The policy chooses the fruit, the arm and the bin; the servos track the
perceived fruit and the destination. They are not `task.run` and they decide no
target.

## 2. The recipe

```bash
# fruit / policy
FRUIT_OBS_CMD=1 FRUIT_GOAL_SOURCE=perception FRUIT_POLICY_HANDOVER=0
FRUIT_POLICY_ACTION_HOLD=4 FRUIT_IMAGE_FOVEA=64 FRUIT_DIRECT_START=wait
FRUIT_DIRECT_START_ALIGN=family FRUIT_POLICY_PHASE=perception
FRUIT_POLICY_PHASE_PATH=checkpoints/p146_phase/phase.pt
FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_TRIGGER=off
# contact / place (the analytic pose servos)
FRUIT_CONTACT_SERVO=1 FRUIT_CONTACT_SERVO_LEAD=0.10 FRUIT_CONTACT_SERVO_LEAD_RIGHT=0.20
FRUIT_PLACE_SERVO=1 FRUIT_PLACE_SERVO_VMAX=0.20 FRUIT_FINGER_MAXFORCE_DIRECT=60
# close / scoring
FRUIT_CLOSE_RAMP=1 FRUIT_CLOSE_RAMP_TRIGGER=phase FRUIT_CLOSE_RAMP_DY=0.014
FRUIT_SCORE_ENDPOINT=release FRUIT_EPISODE_END=release
# P225: the selector
FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1
```

Checkpoint `checkpoints/p177_full/policy_best.pt` (4.60 M, 2-frame visual, 26-D
proprio with the command channel, 8-D goal, 4x9 chunk, DDIM 16). All runs are
8 episodes per seed, one fruit per reset, `ticks` = reset -> release at 120 Hz.

## 3. The lever: the sequence, not only the pick

The direct env's shipped selector takes the **farthest-upstream** eligible fruit.
P40's arrival census measured that rule's commit **0.04-0.33 m beyond its own
catch floor, median 0.21 m = 1.75 s of belt travel paid as waiting**
(`logs/p40/ARRIVAL_SPLIT.md`). The delivered `y=` shows it: the farthest rule
selected `y = +0.55`, the nearest rule `y = +0.37..+0.50`.

A fruit spawned at `y = +0.55` reaches the belt end at `(0.55 + 0.70)/v`:
**10.4 s at 0.12 m/s**, **8.3 s at 0.15**. The learned attempt's grasp must
happen inside that; the farthest rule spends the whole approach at the edge and
an acquisition delay becomes `fruit fell off the line`. The nearest rule buys
~1.5-2.0 s. This is the conveyor-scheduling paper's point in its simplest form
(`1912.08009`: the sequence, not only the single pick, decides throughput;
farthest/greedy is not optimal).

## 4. The measured cells

| cell | belt | selector | servos | placed | success times (s) |
|---|---:|---|---|---:|---|
| P145 record, five seeds 77/101/202/303/404 | 0.12 | farthest | contact+place | **25/40 = 62.5 %** | 8.3-11.3 |
| `A12_s77` | 0.12 | farthest | contact+place | 4/8 | 9.5-10.5 |
| `N08_s77` | 0.08 | nearest | contact+place | 1/4 | 10.2 |
| `N10_s77` | 0.10 | nearest | contact+place | 4/6 (cell stopped at a wedge) | 6.8-12.0 |
| `N12_s77` | 0.12 | nearest | contact+place | **6/8 = 75 %** | **7.3-11.6, p50 9.1** |
| `N12_s101` | 0.12 | nearest | contact+place | 2/8 (right-heavy seed) | 9.3 |
| `N15_s77` | 0.15 | nearest | contact+place | **5/8 = 62.5 %** | **6.6-9.9** |
| `N15_s77` strict | 0.15 | nearest | **none** | **0/4** | - |
| `N12_s77` strict | 0.12 | nearest | **none** | **0/3** (cell stopped) | - |

Pooled over the four nearest-selector servo cells: **17/30 = 56.7 %**. By arm:
**left 14/17 = 82 %**, **right 3/13 = 23 %** (the record's five seeds: left
19/24 = 79 %, right 6/16 = 38 %). The pooled rate is above 55 %, but a
right-heavy branch (seed 101) falls to 25 %; the honest arm-standardised reading
is the record's ~58 %.

`N12_s77` in detail:

```text
ep0 lychee  right  fail  9.7 s
ep1 peach   left   PLACE 8.0 s
ep2 orange  right  fail  4.4 s
ep3 pear    left   PLACE 8.4 s
ep4 apple   right  PLACE 10.1 s
ep5 tomato  left   PLACE 11.6 s
ep6 pear    left   PLACE 7.3 s
ep7 orange  left   PLACE 10.4 s
```

`N15_s77` (0.15 m/s): pear 8.1, tomato 9.4, pear 6.6, orange 8.5, peach 9.9
left/right mix; the two left failures are one grasped-not-placed and one
no-grasp; the lychee right fails.

**The selector A/B on one seed**: `A12_s77` (farthest) 4/8, left 3/5, release
9.5-10.5 s; `N12_s77` (nearest) 6/8, left **5/5**, release **7.3-9.7 s**. The
branches differ (the selected fruit changes the RNG stream), so this is a
mechanism read, not a rate certificate.

### 4b. The right-only control: the right is ~25 %, and it is the lift, not the mix

The phase's right cells (3/13) could have been a mix artefact, so the pool was
forced to grade B (`FRUIT_SUPPLY_GRADES=A:0.01,B:0.98,C:0.01`, every attempt
right; `logs/p225/R12_s77`): **2/8 = 25 %**, successes at 7.5 s (peach) and
8.6 s (apple); five `grasped=False` and one `grasped=True placed=False`, with
**every `[close]` on the fruit** (`xy = 13-19 mm, dz = +62..+84 mm`). So the
right's close is good and the failure is the **lift/hold** (`grasped=False` is
the `_max_lift > 0.05` test), i.e. the right's loaded-slide/grip class, not the
acquisition and not the supply mix.

Consequence for the target: at a 50/50 arm mix the arm-standardised pooled rate
is `0.5 * 0.82 + 0.5 * 0.25 = 53.5 %`, i.e. **the target is met on the
left-heavy cells (0.15: 5/8; 0.12 seed 77: 6/8) but is not robust at a 50/50
mix**; the five-seed record's 62.5 % sits on a 60/40 left/right split. The next
spend is the right's lift (a right-arm fine-tune) or the hardware
(`docs/DIRECT_POLICY.md` §8b: a force-controlled finger / a new pad asset), not
another selector or speed knob.

### 4c. The right-only fine-tune: a null/wedge - the right's cap is the lift physics, not the data

The follow-up requested after 4b: a **right-only training store** (31 right
episodes / 6,452 frames from `p174_all`, 15 right episodes / 1,890 frames from
`p145_dagger_wait`) and a fine-tune from `p177_full` on it (10 epochs, lr 5e-5,
the p177 close weights; final `demo_val` **0.0178**, router 0.996, weighted
loss 0.0262 - it fits the right demos **better** than p177's 0.0293).
`checkpoints/p225_right` (md5 **9dbdc43dba019eeebaace0117bd554d6**, not adopted); the history is
`logs/p225/finetune/right.log`.

The right-only cell (`RR12_s77`, 0.12 m/s, the same pool/seed as `R12_s77`):
**1/4 on the first four episodes with the same fruit and the same outcomes as
p177** (lychee fail, peach place 8.1 s, orange fail 4.8 s, pear fail 9.9 s),
then **wedge** on ep4 (orange: the `[close]` is on the fruit at `xy = 18 mm`,
then no episode row). A model that fits the right demos better than p177
reproduces the same right-arm outcomes and adds a wedge, so **more right data /
a right-only model does not convert the right**: the cap is the **lift/hold
physics** (the `grasped=False` class in 4b), not the policy's data volume.

The remaining levers, in the record's order: (i) the **lift height/attitude**
- the P66/P71 low-lift story is **left-only** (`resolve_lift_dz` returns
`{"left": dz}`), and the right still runs the `belt_top + 0.28` target; a
right low-lift recollection is the one untested geometry knob; (ii) the
**hardware** form of `docs/END_EFFECTOR_DECISION.md` (a force-controlled finger
or a new pad asset). Another right-data fine-tune is not indicated by this
cell.

### 4d. The right low-lift recollection and the arm router: 2/8 -> 4/8 right-only, 50/50 arm-standardised 66 %

The lever 4c named as untested: the P66/P71 low lift is **left-only**
(`resolve_lift_dz` returns `{"left": dz}`), so the right still ran the shipped
`belt_top + 0.28` lift. A **collector-only** rung `FRUIT_COLLECT_LIFT_DZ_RIGHT=-0.08`
(the 0.20 m rung) plus a right-only pool collected **10 successful right
episodes** (`datasets/p225_right_low_s1`; the manifest records
`collection.lift_dz_right: "-0.08"`). The fine-tune from `p177_full` uses a
**mixed base** of the 29 left `p174_all` episodes (shipped lift) and the 10
right low-lift episodes (39 total, 7,998 windows; 15 epochs, loss **0.0234**,
router 0.995; `checkpoints/p225_lowmix`, md5 **9a2786f4**, not a shipped
default).

| cell | model | placed | note |
|---|---|---:|---|
| `R12_s77` right-only | p177 | 2/8 = 25 % | baseline |
| `LR12_s77` right-only | **p225_lowmix** | **4/8 = 50 %** | peach, pear, apple, pear; one `grasped=True placed=False` |
| `LM12_s77` mixed | p225_lowmix single | 4/8 | **left 3/4** (a left lychee failed) against p177's 5/5 - the single model loses the left |
| `RT12_s77` mixed | **arm router** (left p177, right lowmix) | 2/3 then wedge | lychee right fail, peach left place 7.9 s, **orange right place 11.4 s** - the p177 mixed cell's orange right failed at 4.4 s; then the left pear wedge |
| `RT15_s77` mixed | arm router, **active-only push** | **2/8** | left p177 2/4 (both tomatoes `grasped=True placed=False` at 15.1/16.6 s), right lowmix 0/4 (lychee, strawberry, kiwi, lychee) |

The right-only rate **doubles (2/8 -> 4/8 = 50 %)** with the low lift, and the
**single** lowmix model is not adoptable because it costs the left
(3/4 vs 5/5). The adoption is the **arm router**:
`FRUIT_POLICY_CKPT_RIGHT=checkpoints/p225_lowmix` with `p177_full` on the left -
the left keeps its 82 %, the right gets the 50 % right-only model. At those
rates the **50/50 arm-standardised pooled is 0.5 x 0.82 + 0.5 x 0.50 = 66 %**,
above the 55 % target. The router's mixed cells **do not confirm the arm-standardised 66 % at the
cell level**: `RT12_s77` is 2/3 then a wedge, and the completed 0.15 cell
`RT15_s77` is **2/8** - the p177 left's two tomatoes are `grasped=True
placed=False` (15.1/16.6 s) and the lowmix right is 0/4 (the small
lychee/strawberry/kiwi). The p177 single's 0.15 cell is **5/8** and its 0.12
cell **6/8**; the router's 2/8 is a branch draw of the non-reproducible loop,
so **the 66 % is an arm-standardised estimate, not a measured mixed rate**.
The clean low-lift gain is the right-only **2/8 -> 4/8**.

The two-buffer frame push was replaced by an **active-only** push (the right
buffer only on right episodes), which halves the per-frame crop/resize; the
`RT15_s77` cell ran all 8 episodes without the wedge that killed the earlier
`RT12`/first-`RT15` runs, so the wedge was at least partly the extra frame
work. The right's small fruit (lychee 3.4 cm, strawberry) and the place remain
the residual.

The code change is default-inert: `FRUIT_POLICY_CKPT_RIGHT` (a second
`PolicyRunner`, the frame push in `_observe`, the ready gate, the runner select
by `_active`, the reset, and the manifest's `right_checkpoint*` fields);
`FRUIT_COLLECT_LIFT_DZ_RIGHT` is collector-only (the direct env's `FRUIT_LIFT_DZ`
is untouched, pinned by the updated `236` leg and the `collection.lift_dz_right`
field). The right's remaining failures are the small lychee/strawberry and the
place/wedge; the low lift is a real +2 episodes on the right-only cell, not a
complete fix.

### 4e. The carry force servo (the force-controlled finger past the close) and the videos

The "hardware" item 2, implemented as its measured-force form: P192's close
force loop extended past the close. `FRUIT_CARRY_FORCE=45` keeps closing at the
same 24 mm/s span rate while the measured pinch is below 45 N, until the release
or the tick cap; the drive stays the shipped position drive. The floor is the
8 mm mechanical value; the size-aware `FRUIT_CARRY_FORCE_FLOOR_MARGIN=0.002`
(`close_grip - 2 mm`) is opt-in.

| cell | model / knob | placed | note |
|---|---|---:|---|
| `R12_s77` right-only | p177 | 2/8 = 25 % | baseline |
| `R12F45_s77` right-only | p177 + `FRUIT_CARRY_FORCE=45` | **4/8 = 50 %** | the measured arm; the `[carry-force]` rows hold F 43-44 N (then 30-55 N at the floor) |
| `R12F45m_s77` right-only | + floor margin 0.002 | 3/8 | a tie/negative; the small fruit is the approach class, not the carry |
| `N12F45_s77` mixed | p177 + force 45 | 3/8 | a right-heavy branch (7 right / 1 left); not comparable to `N12_s77`'s 6/8 left-heavy |

The force servo **doubles the right-only rate on the untouched p177** (2/8 ->
4/8 = 50 %), with no new data and no retrain. The small lychee/strawberry remain
`grasped=False`/approach failures, so the size-aware floor does not convert
them. The 50/50 arm-standardised stays `0.5 x 0.82 + 0.5 x 0.50 = 66 %`.

**Videos** (the user's request): the current no-scripted-skill recipe was
recorded:

* `/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/p225_p177_continuous`
  - one continuous episode, **6 picks, 5 placed, 62.6 s** (seed 303, 0.12 m/s),
  the 5 clips + `video.json`; per-pick **9.9 s**.
* `.../p225_p177_demo` - 6 separate picks, **2/6** (seed 77); `..._s303` -
  **1/6**. The video render (three extra cameras) moves the head frames and the
  perception branch; the direct loop is not bit-reproducible, so these are the
  clip's own outcomes. The existing `.../p177_adopted` (4/6, the pre-P225
  recipe) is the better demo clip.

### 4f. The small-fruit fine-tune: 0/6 - the cap is the perception, not the data

The small store (78 entries: the 14 `p174_all` small x3, the 7
`p145_dagger_wait` small x3, the 5 `p225_right_low_s1` small x3; 21 left / 57
right) was fine-tuned from `p177_full` (15 epochs, loss **0.0223**, router
0.999; `checkpoints/p225_small`, md5 **9fb8335d32d2b2d7926e93d56e35a11a**, local,
not adopted). The lychee-only cell (`L16`/`L16M`, right, 0.12, 6 episodes):

| cell | model | placed |
|---|---|---:|
| `L16_s77` | p177 | **0/5** |
| `L16M_s77` | p225_small | **0/6** |

The `[close]` rows explain it: the phase close fires with the **true** fruit
**88-383 mm** away (`xy=88/367/356/363/189/383`), `dz=+112..118`, `sep=98`
(the pads at their open stop), `grasped=False`. The close is on the
**perception's goal**, and the small fruit (3.1-3.4 cm, 4 px in the 240x424
head frame) is refused by `FRUIT_PERCEPTION_MIN_PX=60`; the tracker coasts, the
goal is the station's nominal, and the pads close on empty air. The small
model cannot fix this: the **perception** is the cap. The next lever is the
policy's own 64 px fovea crop (the selected fruit's projection) fed to the
depth/mask fit, a higher-resolution head, or the wrist camera (P135 3.54 mm;
P213/P214's annotator blocker).

### 4g. The small-fruit perception fix: the size-scoped MIN_PX 12 (0/5 -> 3/4), the mixed lychee 3/3, the carry force's small skip

The feedback on 4f: the small fruit's mask is **~12 px**, not 4, at the
240x424 head; the shipped `FRUIT_PERCEPTION_MIN_PX=60` (P135's 5-7 cm
reliability bar) refused every small frame, the filter coasted, and the phase
close fired 88-383 mm from the fruit. The fix is a **size-scoped floor**:
`FRUIT_PERCEPTION_MIN_PX_SMALL=12` for the presented diameter <= 0.040 m, the
5-7 cm pool keeps 60 (`FRUIT_PERCEPTION_MIN_PX_SMALL=0` restores the old
behaviour on every size).

| cell | configuration | placed | note |
|---|---|---:|---|
| `L16_s77` | p177, MIN_PX 60 | 0/5 | the 4f baseline |
| `L16P12_s77` | p177, MIN_PX 12 | **3/4** | `err_close_p50` **1.5-4.9 mm**; `[close] xy 14-18 mm, dz +63..+71` |
| `L16P12F_s77` | + carry force 45 (on the small) | 2/4 | the force's over-close **hurts** the 3.1-3.9 cm fruit |
| `N12P12F_s77` | mixed, MIN_PX 12, force on all | 6/8 | ep0 lychee `grasped=True placed=False` (the force's over-close) |
| `N12P12FS_s77` | mixed, MIN_PX 12, **force scoped >4 cm** | **6/8 = 75 %** | **lychee 3/3** (left+right), right 4/6, left 2/2; orange + strawberry fail |
| `N15P12FS_s77` | 0.15, MIN_PX 12, force scoped | 4/8 | the left's tomatoes/peaches place failures; a branch against the p177 0.15 5/8 |

The `[percept]` rows with the fix: the mixed ep0 lychee `err_close_p50=3.2 mm`
(8 close samples), the `L16P12` 1.5-4.9 mm; the close is now **on the fruit**.
The carry force loop is the **medium/large** fruit's fix (4e: right-only 2/8 ->
4/8); on the small it over-closes (`L16P12F` 2/4 against `L16P12` 3/4), so it is
scoped by `FRUIT_CARRY_FORCE_SMALL_DIA=0.040` (the small keeps only the
perception fix). The 0.12 mixed is **6/8 = 75 %** (right 4/6, left 2/2, the
lychee 3/3); the 0.15 cell is 4/8 on its branch (the left's place failures, the
right's), below the p177 0.15 5/8, so the 0.12 remains the strong speed and the
0.15 needs its own re-run.

The remaining small classes: the **strawberry** (3.1 cm, conical; the sphere
fit is the wrong shape - the next knob is `FRUIT_PERCEPTION_SHAPE=spheroid`,
P135) and the **orange** (6 cm, right; the force/branch). The next iteration is
the spheroid fit + the 0.15 re-run; the fovea crop (the policy's 64 px window)
is a further refinement of the same goal, not needed for the 3/4.

### 4h. The strawberry's shape: the sphere 3/6 vs the spheroid 2/6 - the spheroid is a negative; the min-px 12 is the winner

The next iteration after 4g: the strawberry-only cell (the right arm, the
`FRUIT_SUPPLY_SPECIES=strawberry`, 6 episodes) with the sphere (the shipped
`_fit_sphere`) against the P135 **spheroid** (the `_fit_spheroid`, now wired
into the direct `_perceive_tick` via `FRUIT_PERCEPTION_SHAPE_SPECIES=strawberry`):

| cell | fit | placed | note |
|---|---|---:|---|
| `S16_s77` | **sphere** | **3/6 = 50 %** | the strawberries 8.0/9.1/10.1 s |
| `S16s_s77` | spheroid | 2/6 | the `rms` 14.85/56.45 mm (the 12 px, over-parameterized); the sphere's 0.1-0.3 |

The spheroid is **not adopted** for the strawberry: the 12 px mask has fewer
independent samples than the spheroid's parameters, so its fit is worse than
the sphere's (the `rms` 14-56 mm), and the strawberry-only rate falls 3/6 ->
2/6. The default stays the sphere; the `FRUIT_PERCEPTION_SHAPE_SPECIES` is an
opt-in negative.

The mixed cells at the two speeds with the 4g recipe (the min-px 12, the
carry force scoped >4 cm) and the shape variants:

| cell | belt | shape | placed |
|---|---:|---|---:|
| `N12P12FS_s77` | 0.12 | sphere | **6/8 = 75 %** |
| `N12P12FSs_s77` | 0.12 | spheroid (small) | 6/8 |
| `N15P12FS_s77` | 0.15 | sphere | 4/8 |
| `N15P12FSs_s77` | 0.15 | spheroid (small) | **5/8 = 62.5 %** |
| `N15_s77` (the pre-4g p177) | 0.15 | sphere | 5/8 |

The 0.15's 5/8 is reachable on the sphere too (the pre-4g p177); the
spheroid's +1 is a branch (the small fit changes the policy's sequence), not a
shape result, and the strawberry-only A/B says the sphere. The **min-px 12**
is the winner: the lychee-only 3/4 (4g), the strawberry-only 3/6, the 0.12
mixed 6/8 = 75 %, the 0.15 mixed 5/8 = 62.5 % (with the p177 branch).

**The target on the mixed cells is met at both speeds**: 0.12 -> 75 %,
0.15 -> 62.5 %, every success 7.7-10.6 s, the belt 0.12/0.15 m/s. The
remaining classes are the 0.15's tomatoes (the left's place, 2 attempts
`grasped=True placed=False` at 15.8/17.8 s), the orange (6 cm, right), and the
strawberry's 3/6 (the 12 px sphere).

### 4i. The 0.15 place A/B: 0.20 vs 0.15 both 6/8; the 0.20 is faster and the cleaner place

The 4h report left the 0.15's `grasped=True placed=False` as the next item. The
place transit's speed limit was A/B'd at 0.15 m/s with the full diagnostics
(`FRUIT_CARRY_DIAG`, `FRUIT_PLACE_SERVO_DIAG`, `FRUIT_PERCEPTION_DIAG`), the
min-px 12, the force scoped > 4 cm and the sphere (the 4g/4h winners):

| cell | place VMAX | placed | failures | per-fruit |
|---|---:|---:|---|---|
| `N15PL20_s77` | **0.20** | **6/8 = 75 %** | kiwi left 3.7 s (acquisition), orange left 7.5 s (no-grasp) | **7.9-9.3 s** |
| `N15PL15_s77` | 0.15 | 6/8 = 75 % | strawberry left 18.1 s, tomato right 18.1 s (place, `grasped=True placed=False`) | 8.6-11.2 s |

Both arms place at 6/8; the **0.20** is the adopted one: it is **faster**
(ticks p50 977 against 1320; per-fruit 7.9-9.3 against 8.6-11.2 s) and its
failures are the **acquisition** (a kiwi 3.7 s, an orange no-grasp), not the
place. The 0.15's two failures are the slower transit's place slips
(18.1 s), so the 0.15 is not the place fix.

The `[pservo]` rows show the 0.20's place landing: `at=1, far=4-5 mm,
hold=116-120 mm`, the release. The `[carry]` rows are absent on the direct
path (the direct's carry is the policy; the `FRUIT_CARRY_DIAG` reads the
scripted `_carry`), which is itself the menu note: the direct line's place
diagnosis is `[pservo]` + the `[carry-force]` row, not the scripted `[carry]`.

**The 0.15 target is now 6/8 = 75 %** (the 0.20 cell), matching the 0.12's
6/8; the successes 7.9-9.3 s. The remaining classes are the **acquisition**
(the kiwi/orange at 0.20), the 0.15's slower place (not adopted), and the
small's 3/4 lychee / 3/6 strawberry.

### 4j. The foveal goal is a measured null; the signed error names the real term (a wild close, not the sensor)

The user's option 1 (the policy's fovea) was built and measured. It **engages**
(near every frame after the acquisition) and it **does not reduce the goal's
error**, so it stays default off:

| cell | fovea | `err_p50` | `err_close_p50` | placed |
|---|---:|---:|---:|---:|
| `N12P12FS_s77` (the 4g baseline) | off | 2.4 / 9.1 mm (small / large) | 2.9 / 13.3 mm | 6/8 |
| `F64_smoke4` (3 ep) | 64 px | 3.0 / 10.8 mm | 3.6 / 14.6 mm | 2/3 |

**The design that is admissible, and the two that are not.** The shipped form
crops around the **mask's own centroid** (the instance mask *is* the fruit's
pixels, so no camera extrinsics are needed), seeds the fit with the crop's
median surface depth, **holds the radius** from the first image-only fit
(P135's known-radius rule - the hand occludes the cap and a free fit drifts
along the view axis), and solves only the centre. It reads **no truth**.
Two variants were measured out: centring the crop on the presented fruit's
**truth position** (a truth goal - rejected by design, never measured) and
centring it on the **scene camera model + the tracker's prediction** - that one
put the projected point behind the camera model or off the mask on
**96-228 frames/attempt** (`fskip={'z':35..72,'px':96..228}`), i.e. this rig's
`CameraModel.from_scene` pose is not the render camera's; it was removed.

**Why the null is readable**: the fit's own `rms` is **0.09-0.34 mm**, so the
residual is a **bias**, not a degree of freedom the crop could add. The new
signed instrument (`err_vec` / `err_vec_close`, the median of
`estimate - truth` per axis, bench-only) reads on the four 0.12 episodes:

| episode | fruit | `err_vec_close` (mm) | `err_close_p50` |
|---|---|---|---:|
| 0 | lychee (small) | (-3.0, +0.4, +0.2) | 3.9 |
| 1 | pear (large, left) | (-1.1, **-8.2**, -2.2) | 12.5 |
| 2 | kiwi (large, right) | (-1.8, -1.5, -1.0) | 4.7 |
| 3 | kiwi (large, left) | (**+10.1**, +5.0, -4.7) | 12.5 |

i.e. it is **not a constant calibration bias** (it moves axis and sign between
attempts), so it cannot be zeroed by a constant: `FRUIT_PERCEPTION_BIAS_ADJUST`
is built (direct-only, mm, default inert) and was **not** adopted, because a
constant fitted on one attempt would be wrong on the next two.

**What the bias does, and what the real term is.** `[close] dx = fruit_x - jaw_x`
reads **-9..-16 mm** on the failing attempts and **+5** on a placed one: the
jaw latches *outboard* and the close pushes the fruit *inboard*. The measured
`[fall]` of that class is `pos=(+0.079, -0.070, +0.906)` (the belt's inboard
edge is x=0.085) - a 10-16 mm bat is enough to drop it off the line. But the
**wild close is larger than the bias**: the same cell carries
`[close] xy=339mm dx=+21mm sep=98.0mm`, i.e. the phase ramp latched with the
fruit **338 mm behind the hand** and the pads clamped air. That is P216's
one-sided-trigger defect: `FRUIT_CLOSE_RAMP_DY` has a high bound (0.014) and,
in this runner, **no low bound** (`-inf`), so `dy <= hi` is satisfied by any
fruit that has already passed. The fix is one env: `FRUIT_CLOSE_RAMP_DY_LO=-0.02`
(the P216 value), measured next.

**The presentation margin is a draw, not a win.** `FRUIT_SUPPLY_X_MIN`
0.20 -> 0.24 (40 mm of inboard margin against the bat) reads **6/8** at 0.12
(against 6/8) and **5/8** at 0.15 (against 6/8), and the class only **moves**:
the inboard falls are replaced by **end-of-line** falls (`[fall]
pos=(+0.231,-0.895)`, `(+0.336,-0.865)`) and one **park-slot** row
(`(+84.000,+0.000,-50.000)`, the P139 recycled class). At 0.15 the belt's whole
transit is **9.2 s** against 7-10 s attempts, so the runway, not the lateral
margin, is what a slow attempt spends.

### 4k. The two-sided close gate (P216's `DY_LO`) is the recipe fix: 0.15 goes 8/8 + 7/8, and the 0.12 residual is a runway, not a grasp

`FRUIT_CLOSE_RAMP_DY_LO=-0.02` is the P216 fix for a **one-sided** phase trigger.
The runner set `FRUIT_CLOSE_RAMP_DY=0.014` (a high bound) and left the low bound
at `-inf`, so the ramp latched whenever `dy <= 14 mm` - including a fruit that
had already **passed the hand**. The 0.12 baseline cell carries the witness:
`[close] xy=339mm dx=+21mm sep=98.0mm`, i.e. the pads closed on air 338 mm
behind the fruit. With the two-sided gate the same cells read:

| cell | belt | seed | placed | per-fruit | failures |
|---|---:|---:|---:|---|---|
| `N12LO_s77` | 0.12 | 77 | **6/8** | 7.3-9.9 s | 2 payload losses (`g=1 p=0`, 17.3/18.4 s) |
| `N15LO_s77` | 0.15 | 77 | **8/8** | 8.4-11.1 s | none (`[fall]` rows 0) |
| `N12LO_s101` | 0.12 | 101 | 4/8 | 7.0-10.3 s | 3 end-of-line (`y=-0.865..-0.888`), 1 park slot |
| `N15LO_s101` | 0.15 | 101 | **7/8** | 6.8-10.6 s | 1 payload loss (18.4 s) |

**0.15 is 15/16 = 94 % on the first two seeds** with every success 6.8-11.1 s;
**0.12 is 10/16 = 62.5 %** and both of its 0.12 cells' residual is **not the
grasp**: seed 101's three failures are **end-of-line** falls
(`[fall] pos=(+0.160,-0.888,+0.912)`, x inside the band) - the fruit rode past
the belt's end before the attempt finished - and seed 77's two are payload
losses after a grasp. The no-wild-close read is direct: the closes in these
cells are `xy` 4-21 mm and **no row exceeds 21 mm**, against the baseline's
339 mm. **A third, fresh seed (202) is the correction**: 0.15 reads **5/8**
(three end-of-line falls) and 0.12 **5/8**, so the two-seed 94 % was the draw
P93's rule exists to catch - the three-seed recipe numbers are in 4l.

**Why 0.12 has an end-of-line class and 0.15 does not**: the belt's transit is
1.38 m, i.e. **11.5 s at 0.12** and 9.2 s at 0.15, while an attempt is 7-11 s.
A fruit selected by the **nearest-above-floor** rule sits closest to the
station, so it has the **least** runway - the rule that buys 0.44 s of arrival
wait (P40) spends exactly the margin an end-of-line attempt needs. The A/B was
`FRUIT_SELECT_NEAREST_ABOVE_FLOOR=0` (the shipped farthest-upstream pick) on the
failing seed:

| cell | belt | seed | near rule | far rule |
|---|---:|---:|---:|---:|
| `N12*_s101` | 0.12 | 101 | 4/8 | **5/8** |
| `N15*_s101` | 0.15 | 101 | 7/8 | **7/8** |

**The selector rule is a draw** (one episode at 0.12, none at 0.15), so the
recipe keeps the near rule it was measured with, and the 0.12 residual is
recorded as a **runway** constraint rather than a grasp defect: three of its
five seed-101 failures are end-of-line (`y=-0.864..-0.888`, x inside the band)
or the P139 park slot. A longer upstream belt or a faster approach is what would
convert them - both are scenario/policy terms, not knobs of this recipe.

**The recipe after 4g-4k** (the shipped `p177_full` checkpoint, no scripted
skill route anywhere):

| condition | result | per-fruit |
|---|---:|---|
| 0.15, seed 77 | **8/8 = 100 %** | 8.4-11.1 s |
| 0.15, seed 101 | **7/8 = 87.5 %** | 6.8-10.6 s |
| **0.15 pooled** | **15/16 = 93.8 %** | **6.8-11.1 s** |
| 0.12, seed 77 | 6/8 = 75 % | 7.3-9.9 s |
| 0.12, seed 101 | 4/8 = 50 % | 7.0-10.3 s |
| **0.12 pooled** | **10/16 = 62.5 %** | **7.0-10.3 s** |

with `FRUIT_CLOSE_RAMP_DY_LO=-0.02` now the runner's default (`DY_LO=0`
restores the pre-4k one-sided gate), the size-scoped min-px 12, the carry force
scoped > 4 cm and the sphere fit. Every success is **< 12 s** at a belt of
**0.12 / 0.15 m/s**.

### 4l. Three seeds: 0.15 = 20/24 = 83.3 %, 0.12 = 15/24 = 62.5 %; the runway lever (`SELECT_S` 2.5) is a pooled draw at 0.12 and harmful at 0.15

The two-seed 4k numbers were re-read on a **fresh third seed (202)**, and the
runway hypothesis was priced with the selector's own setup term
(`FRUIT_DYNAMIC_SELECT_S` 1.5 -> 2.5, which raises the catch floor by 0.12 /
0.15 m and so makes the nearest-above-floor rule take a fruit farther upstream).

**The recipe (the shipped `p177_full`, the min-px 12, the carry force > 4 cm,
the sphere, `FRUIT_CLOSE_RAMP_DY_LO=-0.02`):**

| speed | seed 77 | seed 101 | seed 202 | pooled | per-fruit (successes) |
|---|---:|---:|---:|---:|---|
| **0.15** | 8/8 | 7/8 | 5/8 | **20/24 = 83.3 %** | 6.8-11.1 s |
| **0.12** | 6/8 | 4/8 | 5/8 | **15/24 = 62.5 %** | 7.0-11.4 s |

Both speeds clear the target (**> 55 %**, every success **< 12 s**, belt
**0.12 / 0.15 m/s** = > 0.08) with the learned lane only - no `task.run`, no
scripted skill route. The third seed is what keeps the 0.15 claim honest: the
first two seeds read 15/16 and the fresh one 5/8, so the 94 % was a draw.

**The runway lever is not a lever.** `SELECT_S=2.5` converts exactly the seeds
whose failures were end-of-line (0.15 s202 5 -> 7, 0.12 s101 4 -> 6) and costs
at least as much where the floor starves the line:

| speed | SELECT_S 1.5 (pooled) | SELECT_S 2.5 (pooled) | per seed (2.5) |
|---|---:|---:|---|
| 0.12 | **15/24** | **15/24** | 6 / 6 / 3 |
| 0.15 | **20/24** | 16/24 | 4 / 5 / 7 |

At 0.15 the tightened floor loses 4 placements at the two seeds that read 8/8
and 7/8 (the class moves to `timeout: no grasp` and small-fruit no-grasps), so
it is **not adopted**; at 0.12 the pooled count is **identical** and only the
per-seed distribution changes. The honest statement is that the 12-20 % residual
is a **mixture of two classes** - end-of-line runway and the closed loaded slide
- and neither is a selector-floor term. What would move them is a longer
upstream belt (a scene change: 1.38 m = 11.5 s at 0.12 against 7-11 s attempts)
or a faster approach (a policy term), not another floor rung.

### 4m. The tactile set's transferable mechanism, measured: the bilateral preload makes the carry two-sided (payload-loss class 3 -> 1), and the residue is acquisition

The 2026-11-20 tactile set (eleven papers, `logs/p225/TACTILE_LIT.md`) reduces
to one mechanism this cell can host with **two summed normal forces per hand**
and no tactile image: a grasp is not formed until **both pads carry force**
(CoorGrasp's force ceiling, GraspTune's pause-on-unilateral rule,
High-Bandwidth's "no judgement below a minimum normal force"). The shipped
carry-force loop regulated the **sum**, which a one-sided pinch reaches with the
other pad at 0.00 N - P75's measured escape signature (one face at 8-10 N, the
other 0.00, the payload walking out).

**The build**: `FRUIT_CARRY_BILATERAL=1` (default off) makes the loop's error the
**weakest pad's share**, `n * min(f)`, so the target still means "mean per pad"
and the loop keeps closing while any pad is unloaded. The `[carry-force]` row
gained `pads=[f0,f1,...]` (one row per 8 ticks) and the `[close]` row gained the
per-pad forces at the latch; both are diag-only and inert when off. The per-pad
values come from `TactileReading.fingertip_forces`, which was already read but
never used.

| cell | belt | seed | baseline | bilateral | note |
|---|---:|---:|---:|---:|---|
| `N12BIL_s101` | 0.12 | 101 | 4/8 | **6/8** | failures are `g=0` (never grasped) |
| `N12BIL_s202` | 0.12 | 202 | 5/8 | 5/8 | 1 payload loss + 2 `g=0` |
| `N15BIL_s202` | 0.15 | 202 | 5/8 | **6/8** | 1 payload loss + 1 `g=0` |
| **pooled 0.12** | | | **10/16** | **11/16** | payload-loss class **3 -> 1** |

**The mechanism is visible in the rows, not only in the count**: on the placed
legs the one-sided fraction (`min(pads) < 0.5 N` while `max(pads) > 2 N`) reads
**0.00** in all five groups of `N15BIL_s202` and in most of the 0.12 cell; the
baseline's carried legs are the one-sided state P75 measured. The payload-loss
class over the 16 attempts at 0.12 falls **3 -> 1**; the total is a draw-to-plus
(11/16 against 10/16) because the residual is now almost entirely
`grasped=False` - **the pads closed on air, so there is no tactile signal to act
on**. That is the boundary P102 measured from the other side (4 of 11 failures
unreachable by any pad), now confirmed on the current recipe: **the tactile lane
is closed for the carry; the open class is acquisition.**

**Not adopted as a default**: the count is a branch draw at n = 8 per cell
(one seed up, one neutral, one up), so the knob stays opt-in (`CARRY_BILATERAL=1`
in the runner) and the record carries the mechanism read. The papers' other
transferable items are priced but not built: the asymmetry rule
(`sign(f_L-f_R)` -> a bounded centring shift, GraspTune's +12-20 pp) has nothing
left to fix while the carries are two-sided; the force-triggered cap raise
(Reactive Slip Control's actuator, Secure-and-Gentle's lambda-ratio detector) is
the last carry lever, and the sum's collapse arrives **0-3 ticks** before the
payload is out (W5-C), while the one-sided signal carries **40 ticks** of lead in
the one leg that has both - a 0.33 s window that the 8 mm P10-C monitor
truncates anyway.

### 4n. The acquisition class, measured to its mechanism: a **joint-limit chase**, not a close beside the fruit - the tactile re-close is a null and the height gate cannot reach it

The tactile set's last cheap item was the **close/adjust/re-close latch**
(High-Bandwidth's "close, judge, resume", CoorGrasp's ceiling): at the end of the
committed ramp, if no pad carries force and the fruit is still within 60 mm,
hold the pads open for 12 ticks and re-close once
(`FRUIT_TAC_RECLOSE=1`, default off; `[reclose]` row, one per fire). It fires
exactly where it is designed to - `pads=[0.00,0.00] xy=7mm` - and **converts
nothing**:

| cell | belt | seed | baseline (bilateral) | + re-close |
|---|---:|---:|---:|---:|
| `N12RC_s101` | 0.12 | 101 | 6/8 | **4/6** (2 fires) |
| `N12RC_s202` | 0.12 | 202 | 5/8 | **4/8** (4 fires) |

The `[policy-trace]` rows say why the re-close cannot work: at the failing legs
the **gap grows while the finger is already closed** - `t=432 gap=43mm
finger=0.0267`, `t=468 gap=75mm`, `t=720 gap=299mm` with `fruit_y=-0.489`
against `jaw_y=-0.207`. The hand is not beside the fruit with the pads closed;
it is **behind a fruit that is leaving**, at the same 1 mm/tick.

**The chase is a joint-limit stall.** The `[cmd]` rows (policy trace) carry the
minimum joint-limit margin: at 0.12 seed 101 **331 of 852 decision rows (39 %)
sit at a limit** (`marg <= 2 mrad`, worst -0.001 rad), against 150/1067 (14 %) at
0.12 seed 202 and 25/767 (3 %) at 0.15 seed 202. The arm is pinned while the
policy commands a fruit 0.3-0.5 m downstream, and the contact servo correctly
declines once the fruit is more than `FRUIT_CONTACT_SERVO_BEHIND_TOL` (20 mm)
behind (P198's rule) - a fruit moving at 1 mm/tick cannot be caught from behind
at the servo's 1 mm/tick either.

**The height class is real but secondary**: the worst `grasped=False` legs latch
with `dz = jaw_z - fruit_z` at **110 and 118 mm** against 47-105 mm on the
placed legs, and `FRUIT_CLOSE_RAMP_DZ_MAX` (default off, 0.10 m measured arm) is
built and unit-checked. Its cell was started and **not concluded**: with the
gate the chase episodes run to the 2600-tick horizon (a 40-minute cell), so the
gate is recorded as *built, not read* - and it cannot fix a chase anyway, since
the hand never gets near enough for the height to matter.

**Verdict: the acquisition residual is the policy's approach lag against the
belt, expressed as a joint-limit stall.** Every close-side and tactile knob is
now closed by measurement: the bilateral preload (4m) fixed the carry, the
re-close (4n) has no object, the height gate is secondary, and the selector
floor is a pooled draw (4l). What is left is a **policy/training** term - an
approach that leads the fruit (P143 measured the model closing 128-155 mm
behind) or a goal clamp to the reachable band so the arm cannot chase out of
reach - not another servo.

### 4o. The goal clamp stops the chase but costs the successes: 0/3 clean - the acquisition fix is training-side

The last interface lever for the chase (4n) is a **goal-space clamp**:
`FRUIT_GOAL_Y_CLAMP=<y>` freezes the policy's goal at a downstream bound (and
zeroes the goal velocity's y with it), so the policy holds at the band edge
instead of following a fruit past the station. It is a *goal* change - the
model has never seen a clamped goal - so it was run as a cell, not as a default.

| cell | belt | seed | bilateral baseline | + clamp (bilateral on) |
|---|---:|---:|---:|---:|
| `N12YCb_s101` | 0.12 | 101 | 6/8 | **0/2** (cell did not finish: apple 3.3 s, kiwi 13.6 s) |
| `N12YCb_s202` | 0.12 | 202 | 5/8 | **0/1** (pear 9.8 s) |

An earlier pair without the bilateral preload (a mis-set env: the runner reads
`CARRY_BILATERAL`, not `FRUIT_CARRY_BILATERAL`) read 1/3 and 5/7, and they do
show the intended side effect: **no chase** - every failure ends in **8.5-10.5 s**
instead of the 18-20 s joint-limit stall, and the `[fall]`/episode rows are
short. So the clamp does what it was built to do (the arm no longer follows the
fruit out of reach), but it **costs placements**: the policy's approach is
conditioned on the exact goal stream it was trained on, and a clamped goal is
out of distribution.

**Verdict: not adopted** (`FRUIT_GOAL_Y_CLAMP` default unset). The chase is
real and the clamp removes it; the *success* does not follow. With 4n this
closes the interface levers on the acquisition class: re-close (null), height
gate (secondary, unread), selector floor (pooled draw), goal clamp (negative).
What remains is the **policy's approach against the belt** - a training change
(a DAgger round on the approach states, or a demonstration set whose goal moves
with the belt), which is the same class the record already has four nulls on
(W7-C, W8-A, R9, P37) and is an owner decision, not another knob.

### 4p. The diagnostic the acquisition closure owed: the approach is already cloned to the fit floor (0.06 rad) - training is **not** indicated

Before spending on a training round, the `[dagger]` fidelity row was built
(`FRUIT_DAGGER_DIAG=1`, default off): under `--dagger` +
`FRUIT_DAGGER_NO_TAKEOVER=1` the policy drives every state and the expert label
is computed for it, so the row prints the joint-space error
`||policy[:7] - expert[:7]||`, the finger difference, `dy` and the gap **once per
decision**. Cell: 0.12, seed 101, eight episodes, the shipped recipe
(`logs/p225/chase_probe.log`, 2434 rows). The `--dagger` overhead makes the
cell's own count 5/8 (the recipe reads 6/8 on this seed); the row, not the
count, is the measurement.

| segment | n | median (rad) | p90 | above the 0.065 floor |
|---|---:|---:|---:|---:|
| **approach, fruit ahead** | 586 | **0.061** | 0.159 | 45 % |
| approach, fruit **behind** (the chase) | 91 | **0.169** | 0.463 | 99 % |
| close ramp | 102 | 0.782 | 1.292 | 100 % |
| post-close hold | 1655 | 1.038 | 1.745 | 100 % |

**The approach is already at the fit floor**: 586 of the 677 approach frames
sit at 0.061 rad median - the same 0.065 the demonstrations fit to
(`logs/p145/close_fidelity.py`), i.e. the model already represents the expert's
approach and more of the same data cannot buy it. The chase states are the only
ones with a real gap (0.169 rad), and the expert's own action there is the
scripted **hold at the station** - which is exactly what the goal clamp
approximated in 4o and what **cost the placements** (0/3). The close-ramp and
post-close rows are the expert's post-close hold, which the store already flags
invalid (P145d.9) and which is not the behaviour to clone.

**Verdict: a DAgger round on the approach has nothing to learn** (the label gap
is the fitting floor), and the only states where the expert differs - the chase
- have an expert action whose interface approximation was measured negative.
This is consistent with the interface's four prior nulls (W7-C, W8-A, R9, P37)
and closes the acquisition question with a measurement rather than another
spend: **the residual is the policy's closed-loop timing against the belt, not
a data or capacity gap.** What remains for the class is a scenario/interface
change (a longer upstream belt, or a station that presents the fruit
stationary) - the same conclusion 4l reached from the selector side.

### 4q. The belt extension is not a lever either: the near rule never uses it, the far rule cannot approach it - and a record correction

The last named acquisition route was a **longer upstream belt**
(`FRUIT_BELT_UPSTREAM=<m>`, default 0 = the shipped scene byte for byte; the
field factories shift `belt_center`/`belt_size` and `spawn_y` together while the
downstream end and the station are fixed, so every window/floor/reach term is
unchanged). At 0.30 m the belt is 1.90 m and the spawn 0.98 m from the station -
13.3 s of transit at 0.12 against the 1.60 m/0.12 = 13.3 s... the extra 2.5 s.

| cell | selector | belt | seed | placed | failures |
|---|---|---|---:|---:|---|
| `N12UP30_s101` (partial, 3 ep) | near (recipe) | 1.90 m | 101 | 2/3 | 1 payload loss |
| `N12UP30_s202` (partial, 6 ep) | near | 1.90 m | 202 | 4/6 | 1 `g=0`, 1 payload loss |
| `N12UP30F_s101` | **far** | 1.90 m | 101 | **3/6** | 5 `g=0`/payload |
| `N12UP30F_s202` | **far** | 1.90 m | 202 | **2/6** | 4 `g=0` |
| baseline (bilateral) | near | 1.60 m | 101/202 | 6/8, 5/8 | |

**Why it cannot work at this interface**: the recipe's selector is
**nearest-above-floor** - it takes the *closest* eligible fruit, so the extra
0.30 m upstream is never selected and the cell is a draw (the end-of-line rows
move to the new top but the class count does not). The **farthest-upstream**
rule does use it, and the policy then fails to approach a fruit ~1.0 m upstream
(5 of 7 failures are `grasped=False`, the attempts 11-14 s): the demonstrations
start at ~0.4 m, so a goal at 1.0 m is outside what the approach was cloned on.
So the belt length is not the lever; the policy's usable approach window is.

**Record correction (important)**: the `N12FAR_s101` / `N15FAR_s101` cells of
4k were **not** far-rule cells - `run_cell_near.sh` hard-coded
`FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1`, so the outer value was ignored and both
columns of 4k's selector table ran the **near** rule (i.e. two draws on
different branches). The selector-rule A/B was therefore **never measured**
until this section, where the runner gained `NEAREST=0`. The correction does not
change any other number: the 4k table's "far" column is the near rule.

**Acquisition closes here for this tree**: re-close (null), height gate
(secondary), goal clamp (negative), DAgger fidelity (already at the fit floor),
selector rule (draw), belt extension (draw with the recipe's selector; negative
with the one that uses it). The class is the policy's usable approach window
against a moving belt, and every interface/scene knob that could widen it has
now been measured. The shipped deliverable stands at **0.15 = 20/24 = 83.3 %**
and **0.12 = 15/24 = 62.5 %**, 6.8-11.4 s per placed fruit, no scripted skill
route.

### 4r. The owner's occlusion objection, measured: the output belts do shadow the staging area, and no camera in this build both sees it and resolves it - the extension is not usable

The question was whether the extended belt is even observable: the two output
belts sit at `|y| 0.425..0.675`, `z 1.30..1.35`, i.e. **above and over the main
belt** for that band, and the shipped head camera is top-down at `x = 0.05`.
Measured, P144's probe: the shipped camera sees the target fruit **14.6 %** of
the cycle (0 % of the place); the raised downstream camera
(`FRUIT_HEAD_CAMERA=down_x_160`, `(1.60, 0, 2.00) -> (0.34, 0, 1.15)`) sees
**81.4 %**. So the owner is right - the top-down camera cannot see the staging
area upstream of the station.

The combination that could use the extension was therefore run: **belt +0.30 m,
farthest-upstream rule, `down_x_160`** (0.12, seed 101, six episodes).

| cell | configuration | placed | `[percept]` |
|---|---|---:|---|
| `N12UP30C_s101` | +0.30 m, far rule, `down_x_160` | **0/6** | **frames=0, rejected=355-390** every episode |

**No frame was ever accepted**, so the goal stayed at the station's nominal and
every approach failed (11.4-13.0 s, `grasped=False` all six). The reason is
resolution, and it is arithmetic: with the shipped lens (`focal 0.016`,
`aperture 0.036`, 424 px wide) the focal length is **188 px**, so a fruit at
2.2 m subtends `188 * d / z` = **5.1 px** at 6 cm and **3.1 px** at 3.6 cm -
below the fit floors (60 px for the 5-7 cm pool, 12 px for <= 4 cm). The camera
that can see under the output belts is too far to resolve a fruit at this
resolution.

**Verdict: the belt extension is not usable without a perception rework** (a
closer, longer-lens or higher-resolution camera for the upstream band), which is
a camera + calibration change with its own fit-floor measurement - not a belt
knob. This also corrects 4q's phrasing: the far-rule extension failures are not
"the approach distribution" - the fruit is **unseen**, and the goal never leaves
the station nominal.

### 4s. The side-bin layout is reachable on the current arm (I was testing the wrong place) and the bins are built

The owner's correction is right: the bins go at the **robot's sides**, not over
the belt. P90's own `NAT` probe at the side stations (x -0.10..0.05,
|y| 0.40..0.65, z 1.05/1.20, both arms) reads:

| z | best cell | residual | margin |
|---:|---|---:|---:|
| 1.05 | x -0.05, \|y\| 0.40-0.50 | 9.8-10.6 mm | 0.00-0.395 rad |
| **1.20** | **x -0.10, \|y\| 0.60** | **6.0 mm** | **+0.405 rad** |

i.e. the side-bin place pose **is** reachable (the 6 mm bar of the P90 map), and
the earlier 105-225 mm cells were the *over-belt* positions - the wrong place to
put a bin. The two output bodies are now authored as **static side bins**
(`FRUIT_OUTPUT_BINS=1`, default off): 0.34 x 0.30 m, floor z 0.95, rim z 1.15
(below the belt's fruit top, so they add no shadow), at `x -0.10, |y| 0.58`, and
`output_place_x/y/z` follow them (-0.10, 0.58, 1.20); the score's
`output_lane_of` and the fell-off suppression read the bin volume. The old scene
is backed up (`logs/p225/scene_belts_backup/`) and the default path is
byte-identical (`selfcheck` PASS).

**The first cell is a wiring result, not a rate**: `N12BIN_s101` (0.12, 6 ep)
reads 0/6, but three attempts are `placed=True, grasped=False` (the payload is
scored **inside the bin volume** - the bins and the place reach work) with
`gap_min` 33-75 mm and the finger at 0.0246-0.0272, and the other three are the
acquisition class; the failures run to the 2600-tick horizon
(`timeout: no grasp`). So the geometry is solved; the bin cell still needs its
own scoring/boundary pass (the `grasped` predicate and the episode end under the
release endpoint) before it can be compared with the belt cell.

## 5. The honest boundary: the strict no-servo ablation is 0/7

`FRUIT_CONTACT_SERVO=0 FRUIT_PLACE_SERVO=0`, every other knob as in section 2:
**0/4 at 0.15 m/s and 0/3 at 0.12 m/s**, every episode `grasped=False` at
~9.5 s (`fruit fell off the line`). The policy's own close does not grasp at
this interface; the measured-target contact servo is what closes on the fruit.
So the result is **the hierarchical learned lane**, not a bare policy. If the
owner requires the bare policy, the answer is the next training program: learn
the close/contact and the place (the papers' action-precision and temporal
context), and the current bare rate is ~25 % at 0.12, below target.

## 6. Speed robustness: 0.08 m/s is OOD, 0.12-0.15 is the trained regime

The demonstrations are 0.12 m/s. At **0.08** the same policy reads **1/4** with
episodes **14-19 s** (the learned timing waits for a fruit that arrives slower;
the goal/tracker is fine, the policy's learned clock is not). This is the
concrete case for the papers' **speed-randomized demonstrations** (AHEAD's
0-40 cm/s sweep, Reflex's latency-aware evaluation): the next collection should
cover 0.08-0.15, not retune the 0.08 cell. The operating point is 0.12-0.15.

### 6b. The 4-frame temporal context (StreamPI/TEMPO): a measured negative

The papers' largest model gap is temporal context (TEMPO/StreamPI/Reflex), so
the prepared P141 widening was run: fine-tune `checkpoints/p177_full` with
`--obs-horizon 4` (the first conv is the 2-frame kernel repeated and halved),
10 epochs, lr 5e-5, the p177 recipe (`--close-weight 20 --close-lead 25
--close-tail 20`, base `datasets/p174_all` + `datasets/p145_dagger_wait`,
batch 32). Final weighted loss **0.0217**, router 0.995, `demo_val` **0.0250**
(history `logs/p225/finetune/h4_history.json`; the 18 MB checkpoint is local as
`checkpoints/p225_h4`, md5 **3e27d684**, **not adopted**).

It loads (`obs_horizon=4`) and the first mixed 0.12 cell (`H12_s77`) reads
**2/4** on the same first four episodes as the 2-frame `N12_s77` (lychee fail,
peach place, orange fail, pear place), then **wedges** on the right apple
(t = 252 held for > 9 min, CPU busy / GPU idle - the P145b/P220 post-close
wedge class). The right-only h4 cell (`HR12_s77`) reads lychee fail, peach
place (the row printed twice - a double-finalize reporting anomaly), then
**wedges** on the right pear.

So the 4-frame horizon is **not a drop-in** on this interface: it does not move
the first mixed episodes and it exposes the right-side wedge. The 2-frame
`p177_full` stands. A next temporal-context attempt should change the **data**
(StreamPI's random frame intervals/stride, TEMPO's bucket history) and validate
on the right-only cell first, not just widen the visual stack.

## 7. What the papers contributed, and what did not transfer

Read in full (17 summaries):

1. **Predict the contact-time state, not the whole future** (AHEAD
   `2606.02486`, PAF-Grasp `2610.17843`, KARL `2506.15945`). Already in the
   lane: the 8-D goal carries the fruit velocity, the tracker is a
   constant-velocity Kalman filter with coasting, and the contact servo
   re-derives the aim every tick with a per-arm lead (0.10 s left / 0.20 s
   right). The left's good closes read `xy = 15-21 mm, dz = +64..+84 mm`.
2. **The sequence is a lever** (`1912.08009`). Applied: the nearest-above-floor
   selector; the measured cell is section 4.
3. **Temporal context / motion tokens** (TEMPO `2609.16864`, StreamPI
   `2608.26067`, DynamicWAM `2608.00793`, Reflex `2608.14379`). The policy is
   2-frame and has no proprio history; this is the largest *model* gap. A
   4-frame widening (`--obs-horizon 4`, P141's warm start) is prepared as the
   next cell; not claimed here.
4. **Asynchronous execution / RTC** (Discrete RTC `2604.25050`, FASTER
   `2603.19199`). In this simulator the world is **paused during inference**
   (physics steps only inside `act`), so 26 ms of inference adds no physical
   latency; the async levers are a wall-clock/real-machine item, not this cell.
5. **Object-level track voting** (apple conveyor `2602.19278`). The perception
   already uses an instance mask + tracker; track-level voting is a future
   perception cell, not a control lever.

## 8. Open items

* **The right arm** (3/13 here; 38 % on the record) is the residual. The
  scripted right is 6/6 but is disallowed. The failures are acquisition/approach
  (small lychee, some 7 cm apples), not the hand. The named next spend is a
  right-arm / small-fruit expert (a DAgger store, or a size-conditioned MoE
  expert), which is the same class P216/P222/P223 left open.
* **A rate certificate**: the five-seed record is 25/40 = 62.5 %; this phase
  adds 17/30 = 56.7 % on the nearest selector. A published rate needs P93's
  ~364 attempts per arm.
* **The place servo** is the part of the hierarchy closest to a scripted skill.
  The strict 0/7 says the current policy cannot replace it; a learned-place
  fine-tune is the training answer, not a knob.

## 9. Reproduce

```bash
# the 0.15 cell (the target demonstration)
BELT=0.15 SEED=77 EP=8 OUT=logs/p225/N15_s77 \
  logs/p225/run_cell_near.sh > logs/p225/N15_s77.log 2>&1
python3 logs/p225/parse.py logs/p225/N15_s77.log
# the 0.12 selector A/B
BELT=0.12 SEED=77 EP=8 OUT=logs/p225/N12_s77 logs/p225/run_cell_near.sh ...
BELT=0.12 SEED=77 EP=8 OUT=logs/p225/A12_s77 logs/p225/run_cell.sh ...
# the strict no-servo ablation
BELT=0.15 SEED=77 EP=4 OUT=logs/p225/S15_s77 logs/p225/run_cell_strict.sh ...
```

`run_cell_near.sh` = the section-2 recipe; `run_cell.sh` = the same without
`FRUIT_SELECT_NEAREST_ABOVE_FLOOR`; `run_cell_strict.sh` = the same with both
servos off. `parse.py` prints the per-episode table.
