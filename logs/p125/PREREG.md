# P125 - recollect the policy on the three-lane scene, then let the canary decide

P124 (`logs/p124/RESULTS.md`) reverted the third lane because the **hybrid policy
canary collapses from 8/10 on two lanes to 4/10 twice on three**: the new body is
in the head camera's view and changes the stage's collider set, and every
checkpoint on this tree was trained on the two-lane scene. The owner's decision
is the recollection: **collect on the three-lane scene, fine-tune, and put the
same canary at or above the 2-lane control** before `SceneConfig.output_lanes`
may default to 3.

This file pins the **store, the fine-tune, the A/B and the decision rule before
any canary sample runs**. The spend is the store and the checkpoint; the canary
is the verdict.

## 1. What is already measured (inputs, not claims)

* **The scripted line takes the flip** (P124): three-lane acceptance 7/10
  (bit-identical repeat), `190: PASS` after re-recording, single arm 6/10 (its
  standing rate-only branch). The third lane is a **working physical
  destination** (P123: 25/25 tray agreements).
* **The policy does not** (P124): `accept_policy.sh` (`moe_v12`, the interface of
  record) reads **4/10 twice** on three lanes against **8/10** on two. The
  failures are the pick-station grip class (`fruit did not follow the gripper`,
  5-6 per sample) plus one `fruit left the pick station during the close
  (118 mm)` - all **upstream** of the new lane, so the collapse is an
  **input** change (image + collider set), not a new task.
* **The store that trained the canary** is a **two-lane** scene. No store on
  this tree carries `scene.output_lanes == 3`; every shard manifest with the key
  reads 2.

## 2. Store protocol (`datasets/p125_three_lane`)

The record's own recollection recipe (`logs/p33/run_p33c_collect.sh`, the W7-C
`demos_v13p` shape), on the shipped tree, **sequential shards** (the 2026-10-12
W7-C lesson: three parallel shards hit the known `RenderingManager.render()`
wedge together; the sequential resume collected cleanly):

* **scene**: `FRUIT_OUTPUT_LANES=3` - the only change from the shipped collector
  scenario. Every shard's `manifest.json` must carry
  `scene.output_lanes` with **3** entries (`assets.scene_provenance`); a shard
  without the key is inadmissible (it predates P123), and a shard with 2 is a
  two-lane store;
* **scheduler**: `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1` (the shipped two-line);
* **supply**: the shipped two-line package, pinned explicitly for
  reproducibility: `FRUIT_SUPPLY_SCATTER=1`, `FRUIT_SUPPLY_WAVE=1`,
  `FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25` (the dense sheet + balanced mix
  the grade-pure routing needs);
* **view**: `FRUIT_CAMERA_RES=240,424` (the collection/training/eval view);
* **protocol**: 3 shards (`s0`, `s1`, `s2`) x a **54-success quota** (162 target;
  the dense store was 158, P33 180), **24 successes per collector process**, a
  distinct 30-seed block per shard (`501`, `601`, `701`; `seed + attempt - 1`
  with an in-driver uniqueness guard), a fresh directory per retry
  (`_r2`, `_r3`, ...), merge only the directories that produced episodes with
  `scripts/41_merge_demos.py` into `datasets/p125_three_lane`;
* **stall guard**: the collector's own defaults, untouched
  (`FRUIT_COLLECT_EPISODE_S=600`, `FRUIT_COLLECT_STALL_S=600`). A wedge is
  **recorded, not hidden**: the soft watchdog skips the attempt and the shard
  loop advances the seed; a hard wedge exits that shard and the driver starts a
  new directory;
* **index**: `scripts/106_index_audit.py --root datasets` must pass on the
  merged store; `scripts/107_collect_merge_test.py` must pass.

**No supply, skill or task parameter moves.** The store's only difference from a
two-lane one is the scene: the scripted two-line routes grade A left / grade B
right / grade C skipped, so the third lane is **never a target** - it is
geometry, a collider and a camera-visible body. That is exactly what the
recollection has to teach.

## 3. Fine-tune protocol (`checkpoints/p125_three_lane`)

* **init**: `checkpoints/moe_v12/policy_best.pt` - the checkpoint
  `scripts/accept_policy.sh` defaults to (**the canary of record**; md5
  `3a9ccfc0df49ae1d006cec62e9960d84`). The candidate stays on the canary's own
  lineage so the A/B differs by the store alone;
* **recipe**: the record's (`scripts/222_p37_finetune.sh` / the P33 shape):
  `scripts/111_rl_finetune.py --epochs 6 --lr 5e-5 --weight-mode ones
  --base-weight 1.0 --batch-size 32 --seed 0`, base
  `datasets/demos_v11` (the single-arm anchor the two-line stores use);
* **recorded before the canary**: the checkpoint md5, `finetune_history.json`,
  the final weighted loss and the router accuracy; a non-finite loss or a
  missing history is a **failed phase**, not a candidate.

## 4. Canary A/B - the verdict

**Same scene, same seed, same view, interleaved.** Both arms run
`scripts/accept_policy.sh` with `FRUIT_OUTPUT_LANES=3`, the shipped defaults
(`FRUIT_SUPPLY_SCATTER=0`, the pre-v9 fixed supply, `FRUIT_CAMERA_RES=240,424`,
`SEED` 77, 10 episodes), and differ **only** in `FRUIT_CKPT`:

* **arm A** = `checkpoints/moe_v12/policy_best.pt` (the base, three lanes);
* **arm B** = `checkpoints/p125_three_lane/policy_best.pt` (the recollection,
  three lanes).

**N = 3 samples per arm** (the loop is not reproducible - the record's 2-lane
spread is 5-8/10 - so one sample is not a rate). Order `A B A B A B` so drift is
shared; logs `logs/p125/canary_{A,B}_{1,2,3}.log`. P124's two three-lane A
samples are **prior context, not this batch's data**.

### Decision rule (pinned before the first sample)

* **P1 (rate)**: pooled success over the 30 episodes of arm B is
  **>= 24/30 = 0.80** (the 2-lane control's 8/10) **and** pooled B > pooled A.
  Mean/median per-sample rates and the range are reported beside it.
* **P2 (reasons)**: no failure in any B sample is outside the
  `accept_policy.sh` baseline pair - `fruit did not follow the gripper` (grip
  loss) and `grasped=True placed=False notes=[]` (grasped, not placed). The
  gate's own `unexpected` class is a **FAIL**; the reason multisets of A and B
  are reported.
* **P3 (provenance)**: every merged shard's manifest carries
  `scene.output_lanes` with 3 entries, the merged store's index audit passes,
  and the fine-tune history exists with a finite loss.
* **P4 (no-harm, if P1-P3 pass)**: with the flipped default, the scripted
  acceptance must be **bit-identical on a repeat**, `190` must pass on the
  re-recorded references, and the single-arm restore path must still run.

**The flip happens iff P1 AND P2 AND P3.** P4 is the flip's own no-harm, not the
adoption test. If any of P1/P2/P3 fails, **the default stays 2**, `=3` stays
opt-in, and the negative is published with the same detail.

Read rules carried from the record:

* the canary is a **sample**, so quote per-sample rates and classes, never one
  number as "the rate";
* **same-scene comparisons only** - the 8/10 two-lane control is a fixed bar,
  never a cross-scene delta;
* **no motion budget is re-tuned**; a descent leg over its own budget is
  recorded (P93: a stochastic branch property at ~2.5 % of legs), never
  re-baselined;
* a new failure key is a **finding**, not a nuisance - it blocks the flip.

## 5. If the flip passes: what it owes

The P124/P123 recipe: change `SceneConfig.output_lanes`'s default 2 -> 3 behind
a named constant (so `FRUIT_OUTPUT_LANES=2` restores), update the pins/tests
(`264` the lane table, `234` the reference arrangement, `259`/`260` the
descriptor), re-record **both** two-line references and the **single-arm**
reference from same-batch runs with `105 --write-fingerprint`, archive the
pre-flip files under `logs/p125/`, and write the re-baseline note: **every store
recorded before P125 is a pre-three-lane store; its manifest's
`scene.output_lanes` (2 entries) identifies it.** The canary's own checkpoint
`checkpoints/p125_three_lane` becomes the deployment candidate only if the owner
ships it - this phase flips the **scene**, and `accept_policy.sh` keeps
`moe_v12` unless a separate decision moves it.

## 6. Deviations

Any deviation from this file is written as a dated `PREREG_A<n>.md` with its own
md5 **before** the run it governs, and the verdict clause it touches is named.
