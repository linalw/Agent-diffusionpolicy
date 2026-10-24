# P36 phase 1 pre-registration — the P35 mediator: the park's image vs the proprio

Written 2026-10-24 **before any 2x2 A/B of this design**. The only runs that
exist under this phase are the offline check (`scripts/218_proprio_spoof_check.py`,
`logs/p36/offline_obs_diff.txt`) and the six one-episode observation smokes
(`logs/p36/smoke/`), which are instrumentation and carry **no outcome claim**.
**Default off, no shipped default changed**: the new lever is
`FRUIT_PROPRIO_SPOOF=<pose>` in `rl_env.py`, read from
`configs/proprio_spoof.json`; unset it is one empty-dict test in `proprio()`.
This phase's files are committed with the phase-2 record.

## 0. What is measured, and what is not

**Measured (P35, `logs/p35/C_RESULTS.md`)**: with the *inactive* left arm at
`back` instead of the shipped `ready`, the direct policy's right-arm
carried-not-placed class goes **25/51 -> 0/50** and its success **23/51
(45 %) -> 47/50 (94 %)**, run-level **B > A in 5/5** (one-sided p = 0.031),
pooled 24/75 -> 49/75. The check shows the park **removes the fruit's band
occlusion**: fully-hidden band calls **856/1257 (68.1 %) -> 0/1236 (0 %)**,
inactive-arm pixels inside the target's disc bbox **100 % -> 0 %**.

**Not identified**: the park is a static scene change on **two input
channels**, and that A/B does not separate them:

* **the image**: the arm's silhouette 3497 -> 4155 px in every frame, and the
  band occlusion above;
* **the proprio**: the **7 inactive-arm joints** of the 25-D observation move by
  `[0.448, 0.603, 0.015, 0.497, 0.002, 0.002, 0.000]` rad from `ready` to
  `back` (max 0.603, sum 1.567; 6 of the 7 joints move).

**What argues against a simple perception bottleneck**: the control **succeeds
with the fruit invisible** - 9 of its 23 right-arm successes read `px = 0` at
every band call, and the successes' median fully-hidden share is 0.84 against
the failures' 0.60. So "the policy could not see the fruit" is not established,
and the proprio channel is a live alternative - which is what this phase tests.

## 1. The question

**Which channel carries the park's win - the image, the 7 proprio channels, or
the conjunction?** One question, two interventions, a 2x2.

## 2. The design (the cells)

| cell | the inactive arm (the image) | the 7 joints in the obs | the role |
|---|---|---|---|
| **1** | `ready` | live (`ready`) | the control (the shipped direct env) |
| **2** | `back` (`FRUIT_ARM_PARK=back`) | live (`back`) | the lever - the P35 reproduction |
| **3** | `back` | `ready` (`FRUIT_PROPRIO_SPOOF=ready`) | the **image-only** probe |
| **4** | `ready` | `back` (`FRUIT_PROPRIO_SPOOF=back`) | the **proprio-only** probe |

The exact per-cell environment (everything else identical):

```
1:  (neither knob)
2:  FRUIT_ARM_PARK=back
3:  FRUIT_ARM_PARK=back   FRUIT_PROPRIO_SPOOF=ready
4:                         FRUIT_PROPRIO_SPOOF=back
```

**The manipulation.** `FRUIT_ARM_PARK` teleports only the *inactive* arm at the
reset (P35 phase 1). `FRUIT_PROPRIO_SPOOF` writes only the *inactive* arm's 7
joint values into the observation's proprio (`apply_proprio_spoof`;
`configs/proprio_spoof.json` holds the pose the reset **achieved** for that
pose - the `q_settled` rows of the P35 batch, not the commanded vector, because
`teleport_joints` re-bases onto the measured state). The image, the active arm,
the fingers, the hand/TCP joints and the tactile channels are untouched, and no
simulation state is written by the spoof.

**The inference population is the RIGHT-arm episodes.** A fruit of grade B or C
is presented to the right arm (the direct env sets the arm from the grade), and
the park is left-only by measurement (the right arm's `back` does not hold - the
park file's note), so `back` has **no right-arm vector**: for a left-active
episode the image is the shipped one in every cell and the `ready` spoof writes
what is already there. **The left-arm episodes are therefore a no-op control in
all four cells**, and their spread is the batch's noise scale, not a treatment
effect. The right share was 51/75 = 68 % in P35 -> ~30 right-arm episodes per
cell at 45.

**Cells 3 and 4 are synthetic (OOD) input pairs** - the policy has never seen the
park's image with the ready proprio, nor the reverse. They are probes, not
deployable configurations; see section 8.

## 3. The manipulation check (gates the outcome read)

Read per episode from the batch's own rows (no separate instrumented run). Each
check is an assertion **per episode**; the report prints the passing count and
the denominator, and the gate is the count. **S4 is restricted to right-active
episodes** - the inference population: a left-active episode's inactive arm is
the *right* one, which has no park vector and stands at `ready` in all four
cells, so it cannot test the image channel the cells move.

* **S1 - the proprio substitution**, four assertions:
  * (a) cells 3/4, right-active: `applied=1`, `side=left`,
    `idx=0,2,4,6,8,10,12`, the `obs=` values equal the file's vector at the
    row's 3 decimals (the row's own precision), and `drift = max|live-written|`
    **> 0.30 rad** - the substitution really bites (the ready->back maximum is
    0.603 rad).
  * (b) the counterfactual rows are **not** substituted: cells 1/2 (both arms)
    and cell 4's left-active rows report `applied=0` with `pre_md5 == obs_md5`
    (the pose has no vector for that side).
  * (c) cell 3's left-active rows write the right arm's `ready` vector - a
    no-op the arm already stands in - with `drift <= 0.02 rad`.
  * (d) **the counterpart reproduction** (the aggregation, defined per
    episode): for each right-active episode of cell 3, `max_j |written_j -
    median_j(q of cell 1's right-active episodes)| <= 0.02 rad`, and the same
    for cell 4 against cell 2, where `q` is the counterpart's **live**
    inactive-arm pose at its first non-stale model call (so the bar covers the
    reset's settle *plus* the in-episode drift). The counterpart's own reset
    spread and the deviation distribution (median / max) are printed beside it.
    Bar 0.02 rad = 3 % of the ready->back shift's 0.603 rad maximum.
* **S2 - the rest of the observation.** `rest_same=1` on every episode: the md5
  of the 25-D proprio **with the 7 spoofed indices zeroed** is equal before and
  after the substitution, i.e. nothing else in the vector moved.
* **S3 - the arm is where the cell says.** The `[park]` M1 read on the
  right-active episodes (the parked arm): cells 2/3 hold `back` (0.02 rad vs the
  achieved pose), cells 1/4 hold `ready`, `m1_hold_ok=1` everywhere. The
  left-active rows are reported beside it: their inactive right arm stands at
  `ready` in every cell (the row's `park=` field names the *request*, which the
  right arm has no vector for - not a pose claim).
* **S4 - the image is the arm's physical pose.** The `[park]` band census on the
  **right-active** episodes that reach the band (`band_calls >= 1`; an episode
  that never reaches it is excluded and counted): the inactive left arm
  contributes **pixels inside the target's disc bbox** in cells 1/4 and **none**
  in cells 2/3 (P35's A: 1257/1257 calls, frac 1.9-333; B: 0/1236). Reported as
  the class (`arm_px > 0` vs `= 0`), not the magnitude, because RTX frames are
  not bit-comparable across runs. The gate: cells 2/3 **exactly 0** in every
  right-active episode (a geometric fact - the parked arm is behind the belt),
  cells 1/4 **>= 90 %** of episodes (one stale or band-edge frame is not an
  implementation failure; the exceptions are listed), plus the per-call census
  printed for both.

**A failed S1-S4 is an implementation failure: no outcome claim, and the reason
(the vector, the index set, the pose, the frame) is diagnosed before a re-run.**
The report refuses (exit 2) on a failure and prints the cell table as
*descriptive only*.

## 4. The endpoints

Per cell, **right-arm episodes only** unless stated; denominators printed
(exact counts, not percentages alone).

**Primary**: the **carried-not-placed** class (grasped and not placed) - the
interface's characteristic failure, the class P35 converted 25 -> 0.
Episodes are exactly one of `ok` (placed), `carried` (grasped, not placed),
`no-grasp` (not grasped).

**Primary-secondary**: the right's `ok` count; the right's **composite**
failure mass (`carried + no-grasp`, so a class *relocation* cannot pass); the
**pooled** `ok` count.

**Guard**: the **left-arm** counts per cell (`ok`, `carried`, `no-grasp`) - the
no-op population, quoted as the batch's noise scale.

**Secondary**: **no new failure reason** (the `notes` set vs cell 1's, numbers
normalised as `113` does); the **cycle** - median ticks, all episodes **and
`ok`-only** (the outcome mixes differ by construction, so the crude median is
not a like-for-like speed read); model calls per attempt.

**The composition read**: the per-class table (right arm) per cell, plus the
**class-standardised** right-arm `ok` rate - direct standardisation to cell 1's
right-arm species mix (the P1/P2 lesson: a raw per-cell delta across different
fruit mixes measures the mix).

## 5. The analysis (fixed before the data)

Let `r_c` = the right-arm carried rate in cell `c`, and `n_c` its denominator.

**Completeness gate (H2).** A run is complete only with all four cells present
and **exactly 15 episodes in each cell-run**; the report **refuses** (exit 2) on
fewer than **3** complete runs - a partial batch is re-run
(`P36_ONLY="<cell>_<run>"`), not read. It also refuses when the four cells are
not the same run set. (The phase-2 tooling's first version would have read a
partial batch.)

* **The cell table**: `n`, `ok`, `carried`, `no-grasp` per cell, with a Wilson
  95 % interval on `r_c`.
* **The image main effect** `((r2 + r3) - (r1 + r4)) / 2`, tested as the 2x2
  table **cells {2,3} vs {1,4}** on the carried class - a two-sided **Fisher
  exact** test (hypergeometric, computed exactly; no scipy).
* **The proprio main effect** `((r2 + r4) - (r1 + r3)) / 2`, tested as the 2x2
  table **cells {2,4} vs {1,3}**, same test.
* **The interaction** `(r2 - r3) - (r4 - r1)`: the point estimate plus a
  **within-stratum permutation** p-value - permute the proprio labels inside
  each image stratum (cell 2 <-> 3, and cell 4 <-> 1), 5 000 draws, fixed seed
  20261024, two-sided criterion **`|T*| >= |did|`**, p = `(1 + count) / (1 +
  B)`. (The first version compared `|T* - did| >= |did|`, which is centred on
  the observed value and reads >= 0.5 on every table; the exact enumeration is
  printed beside the sampled p as a cross-check.) Reported as
  **descriptive/secondary**: the two main-effect tests are the pre-registered
  alpha, and the interaction is 1 of 3 contrasts.
  Its reading is **redundancy vs synergy, not the channel test**: with the
  (parked image, parked proprio) factor coding the contrast is
  `r1 + r2 - r3 - r4`, so **0 = additive** (either channel alone suffices),
  **negative = the both-parked cell beats the additive prediction** (neither
  channel alone suffices - or the inconsistent pair is what breaks the response;
  the two are not separable here), **positive = the single-channel cells beat
  it**. Because cell 2 enters *both* main-effect tables, a converting cell 2
  with two unconverted probe cells moves each table by **half** the conversion:
  read the cells, not the table alone.
* **The effect fraction** `f_c = (r1 - r_c) / (r1 - r2)` - how much of the P35
  conversion the channel's cell reproduces - **and the same fraction from the
  class-standardised carried rate** (section 4's standardisation is on the `ok`
  rate; the primary endpoint is the carried class, so the fraction needs the
  standardised *carried* rate; both are printed with their coverage). If
  `r1 - r2 <= 0.05` (no replication) the fraction is **undefined** and the read
  falls back to the absolute contrast `r_c` vs `r1`, reported as a
  **non-replication**, not as a channel result.
* **The run level**: per run, the sign of each contrast (2x2 pairs are computed
  within the run). 3 runs -> 3/3 is the ceiling; it is reported as
  **consistency**, never as a p-value (3/3 = 0.125, which cannot reach 0.05).
* **The pre-registered bands** on the primary rate `r_c` (a channel's cell):
  **full** if `r_c <= 0.10` (the Wilson upper bound at 0/30 is 0.114), **partial**
  if `0.10 < r_c < 0.35`, **none** if `r_c >= 0.35`. These are descriptive
  bands, not tests: at this n an exact p-value cannot separate "the channel
  carries 70 % of the effect" from "carries all of it", which is the
  decision-relevant question.
* **The secondary endpoints are read on the right arm only** (the inference
  population): the failure-reason set vs cell 1's (numbers normalised as `113`
  does), the cycle (median ticks, all and `ok`-only), and the **model calls per
  attempt** (the `[park]` row's `calls=`, median per cell). The pooled counts
  and the left-arm table are printed as context, not as endpoints.
* **The noise floor** is the **left arm**, a no-op in all four cells: its
  carried rate per cell, its spread, and the same image / proprio / interaction
  contrasts computed on it are printed beside the right-arm numbers.

**Multiplicity, stated**: two pre-registered Fisher tests (image, proprio) at
alpha 0.05 each, over 4 cells; the interaction and the per-class table are
secondary. Nothing else is tested.

## 6. The N and the power

**N = 3 runs x 15 episodes per cell = 45 episodes per cell, 180 total**, seeds
**77 / 101 / 202**, policy sampler `FRUIT_POLICY_SEED=11`, checkpoint
`moe_v13s` `61da390a`, **interleaved within each run** with a **randomised
rotation** of the four cells (`P36_ORDER_SEED=20261024`: one seeded permutation
drawn before the batch, rotated by one position per run, so every cell takes
three *distinct* positions across the three runs), all inside **one
`scripts/154_claim_run.sh` claim** with **`RUN_LIMIT=25200`** on the claim's env
(`scripts/219_p36_cells.sh`).

*Why the order is a randomised rotation and not the plain `1,2,3,4 / 2,3,4,1 /
3,4,1,2`.* The plain rotation balances positions but aliases *cell* with
*position within run* completely (cell 1 is always first in run 1, cell 4 always
last in run 1), so a first-position or end-of-run effect is a fixed per-cell
offset that no amount of pooling can remove. Rotating a random base keeps the
Latin property (each cell sees three distinct positions) and removes the fixed
alias. The drawn order is printed in the batch header and by the report; the
residual confound is that three runs cannot separate a position effect from a
run effect at all - the run level is a consistency read, never a test.

*Why `RUN_LIMIT=25200` is part of the invocation.* The claim's watchdog defaults
to 1800 s; the batch is ~1.5 h (12 runs x 15 episodes at the P35 measured rate),
so the default kills it after ~4 runs. The limit belongs to the claim's env (not
exported inside the driver) and the driver refuses to start below 7200 s.

**Power, computed exactly** (`logs/p36/power_check.py`; two-sided Fisher,
alpha 0.05, p1 = 0.49 = the P35 control's right-arm carried rate). The correct n
is the **main-effect arm**: the design is 3 x 15 = 45 per *cell*, the inference
population is the right-arm episodes (the P35 right share 51/75 = 68 %), so a
main-effect table pools **two cells = ~30 right-arm episodes per cell, ~60 per
arm** - not 30 and not 45. At **n = 60 per arm** a probe cell at **0.10 / 0.15 /
0.20 / 0.25** (the 80 / 69 / 59 / 49 % carriers of the 0.49 -> 0 conversion) is
detected with **0.998 / 0.977 / 0.894 / 0.724** power (exactly 0.9978 / 0.9767 /
0.8945 / 0.7237); at 80 % power the design sees a probe cell at **r <= ~0.18**
(a >= ~63 % carrier), a 50 % carrier reads 0.74, a 30 % carrier 0.31 and a 10 %
carrier 0.06. That is why the primary readout is the **effect fraction with its
band**, not the p-value alone. **Caveat (binding): the 60 episodes are 3 runs of
15 and the policy loop is not reproducible across runs, so the effective n is
below 60 and these powers are an upper bound.**

**Cost**: P35's batch ran 10 runs x 15 episodes in **71 min** (12:59-14:10);
this one is 12 runs x 15 = 180 episodes, so **~1.5-2.5 h** projected from that
measured rate (the design note's 3-4 h is the conservative upper bound).

## 7. The falsifiers and the decision matrix

A **positive** in a probe cell is informative; a **null** is not by itself
(because the cell is an inconsistent input pair the policy never saw). The
pre-registered reading is therefore one-directional:

| cell 3 (image) | cell 4 (proprio) | reading | the named next step |
|---|---|---|---|
| full / partial | none | **image-borne** | the park's win travels the **image channel** (the fruit's sightline - the P35 occlusion census - is the leading **unseparated** candidate); the shipping path is a **recollection's own A/B** (the park fixes both channels), and the occlusion instrument already exists (`212`/`217`) |
| none | full / partial | **proprio-borne** | the win is the 7-joint input shift, not the pixels; a recollection that fixes only the image would **not** recover it, and the proprio must be part of the retrain's input plan |
| full / partial | full / partial | **both / redundant** | each channel suffices alone; the interaction says whether the conjunction adds anything; the recollection must fix both |
| none | none | **not identified** | a null probe is ambiguous: either the channel is not the mediator, or the single-channel inconsistency destroys the response (the checkpoint's OOD). The design cannot separate those; the named discriminators are a **within-cell dose** (`FRUIT_ARM_PARK=side_deep` for the image; a partial joint substitution for the proprio) - a new phase, not this one's read |

**The conjunction pattern** - cell 2 converts while cells 3 and 4 both sit at
the control level - *must* move both main-effect tables by **half** the
conversion (cell 2 is in both), so it reads as two half-size main effects and a
**negative** interaction; it is **not** a null result. It is the last row of the
matrix above: reported as **not identified**, with the synergy noted, because
"neither channel suffices" and "the inconsistent pair is what the checkpoint
cannot read" are not separable here.

**Blocks on any claim**: a failed S1-S4 (implementation); a new failure reason
is **reported** (it is an OOD response in a probe cell, not a defect) but blocks
any *adoption* sentence drawn from that cell; the left-arm counts are quoted
beside every right-arm number.

## 8. The OOD caveat (binding)

Cells 3 and 4 present the policy with **input pairs it has never seen**: the
parked image with a ready proprio, and the shipped image with a parked
proprio. The park's own win (cell 2) is itself measured **on shifted frames**
(P35 section 6), so:

* **a positive names the channel** and does not ship: the configuration is not
  deployable (it is an inconsistent observation);
* **a null is weak evidence** - it can be the shift, not the channel;
* **no cell of this design licenses a recollection replacement**: the shipping
  path remains a recollection's own A/B (`logs/p35/C_RESULTS.md` section 3).

### 8a. The per-channel asymmetry (measured, `logs/p36/ood_proprio.txt`)

The two probes are **not** symmetric in how far their manipulated channel sits
from the population the policy conditions on (z against the 7 left-arm channels
of the direct interface's own stored rollouts, `datasets/rl_rollouts/r9_awr`,
56 episodes / 3261 steps, and of the training base `datasets/demos_v11`, 50
episodes / 10228 steps):

| vector | max |z| over the 7 | the worst channel | channels beyond 1.7 sigma |
|---|---|---|---|
| `ready` (cell 3 writes it) | 0.59 (direct) / 0.37 (training) | j2 -0.59 | 0 |
| `back` (cell 4 writes it) | **4.26** (direct) / **5.13** (training) | **j2 -0.978 rad at -4.26 sigma** | 3 of 7 (j1 -1.79, j2 -4.26, j4 -2.40) |

**The z summary is a mixture statistic; the range is the support claim.** The
table also prints each store's **observed range** per channel, and by that read
**j2 is the one channel outside it**: `back`'s j2 = **-0.978 rad** against
`[-0.777, +0.175]` (`r9_awr`) and `[-0.792, +0.175]` (`demos_v11`). The two
other >1.7-sigma channels are inside their observed ranges (j1 -1.912 against
`[-2.049, +0.459]` / `[-1.999, -1.215]`; j4 0.818 against `[+0.451, +1.612]` /
`[+0.054, +1.440]`), so "3 of 7 beyond 1.7 sigma" is not "3 of 7 out of
support".

So:

* **cell 3** holds the **in-support** ready proprio under the parked image: its
  proprio channel carries no out-of-distribution load, its image channel is the
  treatment - a positive is attributable to the image, and a null is weak only
  for the usual inconsistent-pair reason;
* **cell 4** holds the **out-of-support** parked proprio under the shipped
  image: its image channel is the shipped one (no shift at all), its proprio
  channel carries the park's own vector, whose **j2 is outside both stores'
  observed ranges** - the only channel that is. **A cell-4 positive is the
  stronger read** of the two probes (the park's proprio alone, on an in-support
  image, moves the outcome); **a cell-4 null is the weaker one** (an
  out-of-range input may simply be ignored, or the network may have no path for
  it - the null then says nothing about the shipped park, where the image and
  the proprio shift *together*).

Both z values are pooled-population reads: in a left-active episode the left arm
moves, so the pooled sd is wider than the inactive arm's own and the |z| above
are lower bounds - and the 4-5 sigma summary is a **mixture statistic**, not a
support claim. The claim the read rests on is the narrower one: **j2 is outside
the observed range in both stores** (direct and training), and the sigma summary
and the range violation point the same way - the cell-4 null is the weaker read
- so the direction is **conservative** and nothing downstream changes.

## 9. No-harm, provenance, files

* **No-harm**: with both knobs unset the scripted acceptance is re-run and its
  **`[fruit]` stream must be byte-identical** to the P35 record
  (`logs/p35/C_accept_no_harm.log`, 376 lines; the acceptance reads 6/10 +
  `fingerprint: matches` on the pre-existing P32 pear-on branch, so its
  rate-only `exit=1` is expected). `scripts/selfcheck.sh` before and after; the
  new leg `proprio spoof check` pins the vectors, the index set, the observation
  diff and the store guard offline.
* **The store guard**: a **recording** rollout (`--record`) under
  `FRUIT_PROPRIO_SPOOF` is **refused** by the env (a spoofed store would carry a
  proprio the arm never held); the predicate is `store_guard_reason` and is
  pinned by the offline check. `FRUIT_ARM_PARK` is not refused - a parked store
  is a real post-park dataset and is named in the manifest.
* **Provenance**: the batch's `[spoof]` and `[park]` rows, the manifest's
  `proprio_spoof` + `arm_park` blocks, the tree md5s before/after, the
  checkpoint md5, the claim's `RUN_LIMIT`, the drawn cell order, and the cell
  driver's header (`scripts/219_p36_cells.sh`).
* **Files**: `logs/p36/PREREG.md` (this), `P1_IMPL.md` (phase 1: the
  implementation, the offline check, the smoke, the no-harm), `A_RESULTS.md`
  (phase 2), `offline_obs_diff.txt`, `ood_proprio.txt` (+ `.py`),
  `power_check.txt` (+ `.py`), `smoke/`, `A_ab/` (the batch), `A_report.txt`
  (the analysis), `A_driver.log`, `A_tree_md5_*.txt`.
* **No commit; no shipped default changed.**

## 10. The phase-2 Gate-1 amendments

Recorded so the edit history is legible; the batch's header carries the tree
md5s and the drawn order, and `logs/p36/A_RESULTS.md` references this block.
**Items 1-7 were made before the batch ran** (the tooling was fixed and the
power/OOD text corrected on the pre-data tree); **item 8 is a post-batch
correctness fix** whose effect on the published numbers is recorded in
`A_RESULTS.md` section 7.

1. **H1 - the claim's `RUN_LIMIT`.** The phase-1 tooling's recorded invocation
   omitted it, so the claim's 1800 s default would have killed the 12-run batch
   after ~4 runs. The invocation is now
   `RUN_LIMIT=25200 scripts/154_claim_run.sh logs/p36/A_driver.log scripts/219_p36_cells.sh`,
   the limit is *not* exported inside the driver, and the driver **refuses to
   start** below 7200 s.
2. **H2 - the completeness gate.** The report refuses to read fewer than **3
   complete runs** (all four cells, exactly 15 episodes per cell-run) instead of
   silently pooling whatever `C*_*.log` exist.
3. **M1 - the interaction permutation criterion.** `|T* - did| >= |did|` (which
   is centred on the observed value and reads >= 0.5 on every table) is replaced
   by **`|T*| >= |did|`**, with p = `(1 + count)/(1 + B)` and an exact-
   enumeration cross-check; the self-test pins both the fixed value and the old
   form's >= 0.5 behaviour.
4. **M2 - the manipulation check is implemented from the batch rows.** S1-S4
   are parsed from the per-episode `[spoof]`/`[park]` rows (section 3's
   operational definitions), **S4 filtered to right-active episodes**, the 0.02
   rad aggregation is defined per episode, and the outcome read is **gated** on
   it (a failure refuses and prints the cell table as descriptive only).
5. **M3 - the power text.** Section 6 now uses the design's real n (the
   main-effect arm = 2 cells ~ 60 right-arm episodes) and the computed quartet
   `0.998 / 0.977 / 0.894 / 0.724`, with the run-clustering caveat.
6. **M5 - the per-channel OOD asymmetry.** Section 8a: cell 3's ready proprio is
   in-support (max |z| 0.59), cell 4's parked proprio is not (j2 at -4.26 sigma,
   3 of 7 channels beyond 1.7 sigma) - a cell-4 positive is the stronger read, a
   cell-4 null the weaker one.
7. **L-items.** Cell 1 is described as the **P35 C-batch scenario + the four
   diags**, not "the shipped env" (the shipped default has `TRIGGER_ACQ` off, and
   instrumentation is part of the measurement); the class-standardised
   **carried** fraction and the **model calls per attempt** are added to the
   report; the failure reasons and the cycle are **right-arm only**; the cell
   order is a **randomised rotation** (the fixed rotation's cell-position alias
   is removed, section 6); and a **recording** rollout under the spoof is
   refused by the env (section 9), so a probe cell cannot poison a store.
8. **The Fisher tolerance.** The report's exact test now uses a *relative*
   tolerance for "no more likely than observed": the inherited absolute
   `+1e-12` counted every table below 1e-12 as at least as extreme (it read
   8.1e-13 where the exact tail is 8.8e-15). A correctness fix, made after the
   batch and recorded in `A_RESULTS.md` section 7; the decision is unchanged.
9. **The Gate-2 record fixes (post-batch, no decision change).** The review's
   conditions land as: (a) the reading names the **image channel**, with the
   fruit's **sightline** (the P35 68.1 % -> 0 % occlusion census) the leading
   **unseparated** candidate - the probe moves the parked arm's silhouette as
   well as the fruit's pixels, so the mechanism is not identified; (b) the OOD
   summary rests on **j2's range violation** (the only channel outside either
   store's observed range), not on the 4-5 sigma mixture statistic, and the
   direction is conservative; (c) the interaction is reported as the
   pre-registered **descriptor only**, reading "adds nothing measurable under
   the ceiling" (the image cell is at 0/28 carried, so the descriptor cannot
   exclude a contribution above it); (d) the manipulation gate gains a
   **count invariance** - `len(records) == 4 x 15 x n_runs`, at least one
   `[park]` row per cell-run - and a self-test that deletes one `[park]` row and
   expects exit 2, so a silently dropped row cannot shrink the gate's
   population; (e) this design is a **probe at N = 3 runs**, and the **WS-4.2
   N = 5** convention governs the recollection's own A/B; (f) the 219 driver
   header pins its own md5 for future batches. Nothing in this list changes a
   number or the decision.
