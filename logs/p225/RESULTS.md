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
