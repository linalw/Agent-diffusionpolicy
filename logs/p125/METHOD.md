# P125 method - the store, the fine-tune, the canary

The question is P124's: the third lane (`FRUIT_OUTPUT_LANES=3`) is a working
physical destination and the scripted line takes it, but the **hybrid policy
canary** falls 8/10 -> 4/10 because no checkpoint on this tree has seen the
three-lane scene (a body in the head camera's view + a different collider set).
The owner's decision is the recollection. This file records **how** the three
steps were run; `PREREG.md` (md5 `6b236694d8aeb900b2aa927c89169afb`, pinned
09:20:03 before any cell) records the verdict rule.

## 1. The store: `datasets/p125_three_lane`

Driver: `logs/p125/run_p125_collect.sh` (the `logs/p33/run_p33c_collect.sh`
shape: sequential shards, a fresh directory per retry, a per-run success cap,
the collector's own stall guard left at its defaults).

Scenario, and **only** the first line differs from the shipped collector:

```
FRUIT_OUTPUT_LANES=3                     # the third body (P123); never a target
FRUIT_CAMERA_RES=240,424                 # the collection/training/eval view
FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1      # the shipped two-line
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_WAVE=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
```

Note what the collector's own routing does: grade A -> left/lane 0, grade B ->
right/lane 1, grade C **skipped**. The third lane is therefore never a place
target in the store - it is geometry, a collider and a **camera-visible body**,
which is exactly the input change the policy has to learn to ignore.

Protocol: 3 shards x a 54-success quota, **17 successes per collector process**
(the last chunk overshoots by design - `collect_two_line` stops after the chunk
that crosses the target - so a run records ~28 and two runs a shard land at
~56), seeds `501 / 601 / 701` with an in-driver uniqueness guard and
`seed + attempt - 1` per retry, merge with `scripts/41_merge_demos.py`.

**The smoke, before the spend** (2026-11-07 09:22, `logs/p125/smoke.log`,
`datasets/p125_smoke`): `FRUIT_EPISODES=2`, seed 499. Six attempts, five
successes, 200 s wall; the manifest reads
`scene.output_lanes` **3 entries** (`lane 2`: `/World/OutputBelt2`, belt centre
`(0.84, -0.3375, 1.325)`, place `(0.48, -0.30)`, tray `(1.65, -0.33)`), supply
`schedule=wave`, `grades A:0.375 B:0.375 C:0.25`, `camera_res=240,424`,
`biarm_twoline_resolved=1`. That is the provenance the phase turns on; the smoke
is **not** merged into the store.

The hard stall guard is the collector's (`FRUIT_COLLECT_STALL_S=600`): a
`RenderingManager.render()` wedge exits the shard with a stack dump and the
shard loop starts a new directory with the next seed. A wedge is evidence, not
a silent retry.

## 2. The fine-tune: `checkpoints/p125_three_lane`

Driver: `logs/p125/run_p125_finetune.sh`.

```
scripts/111_rl_finetune.py \
    --ckpt checkpoints/moe_v12/policy_best.pt \
    --rollouts datasets/p125_three_lane \
    --base datasets/demos_v11 \
    --out checkpoints/p125_three_lane \
    --epochs 6 --lr 5e-5 --batch-size 32 --weight-mode ones \
    --base-weight 1.0 --seed 0
```

Why `moe_v12` and not `moe_v13s`: `scripts/accept_policy.sh` defaults to
`moe_v12` (the canary of record), and the A/B must differ by the **store**
alone. The recipe is the record's (`logs/p33/run_p33c_finetune.sh`,
`scripts/222_p37_finetune.sh`): `ones` (the lineage mode; `success`/`awr` carry
measured negatives), last epoch saved, `datasets/demos_v11` as the single-arm
anchor (the W4 wrong-anchor lesson: a two-line store must not also be the direct
anchor).

Recorded before the canary: `logs/p125/ckpt_md5.txt`,
`logs/p125/finetune_history.json`, and the summary
(`logs/p125/finetune_summary.txt`: final weighted loss, router accuracy, the
per-epoch history).

## 3. The canary A/B

Driver: `logs/p125/run_p125_canary.sh`; report: `logs/p125/p125_report.py`.

```
FRUIT_OUTPUT_LANES=3 FRUIT_CKPT=<arm> SKIP_SELFCHECK=1 \
    ACCEPT_POLICY_LOG=logs/p125/canary_<arm>_<i>.log scripts/accept_policy.sh
```

Both arms are the **same scene** (three lanes), the same evaluator defaults
(`FRUIT_SUPPLY_SCATTER=0`, the fixed pre-v9 supply, `FRUIT_CAMERA_RES=240,424`,
`SEED=77`, 10 episodes), interleaved `A B A B A B`. `A` = `moe_v12`, `B` =
`p125_three_lane`. P124's two three-lane A samples are context; this batch's A
arm is measured on the same tree.

The report classifies each episode with the **gate's own rule** (`scripts/
accept_policy.sh`): placed / `fruit did not follow the gripper` / `grasped=True
placed=False notes=[]` / `unexpected`. `--check` exits 0 only on the
pre-registered verdict (pooled B >= 24/30, pooled B > pooled A, no unexpected
reason in B, N=3 per arm).

Read rules (the record's): the loop is non-reproducible (rendered frames), so
quote per-sample rates, the median, the range and the classes - never one
number as "the rate"; a reason outside the gate's baseline pair is a **finding**
and blocks the flip; no motion budget is re-tuned.
