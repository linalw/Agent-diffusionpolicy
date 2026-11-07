# P125 - the three-lane recollection is a **null**, and it corrects P124's reading: the canary has no measurable scene cost

The owner's decision was to recollect the policy on the three-lane scene so the
third destination could ship: collect ~150 episodes with `FRUIT_OUTPUT_LANES=3`,
fine-tune from the canary's checkpoint, then require the same canary at or above
the 2-lane control (8/10). The store and the checkpoint were built; the canary
**does not reach the bar**, so the default stays **2** and `=3` stays opt-in.
The phase's important result is what the same-batch two-lane control shows:
**the three-lane "collapse" P124 measured does not reproduce** - the canary's
own spread dominates, and the recollection had no scene cost to recover.

## 1. The store (`datasets/p125_three_lane`, local, gitignored)

196 successful episodes from 8 shard directories, 288 attempts
(`logs/p125/collect_driver.log`), the shipped two-line collector with
`FRUIT_OUTPUT_LANES=3` as the only scene change:

| shard | seeds | episodes |
| --- | --- | --- |
| `s0` / `_r2` / `_r3` | 501 / 502 / 503 | 19 / 30 / 28 |
| `s1` / `_r2` | 601 / 602 | 20 / 35 |
| `s2` / `_r2` / `_r3` | 701 / 702 / 703 | 28 / 17 / 19 |

`index_md5` **`38ec3a125a57e029b8cf08383592e281`**; 96 left / 100 right, grade A
96 / B 100 (grade C is skipped by the pure routing, as designed), **36,414
training windows**. **No wedge and no soft-watchdog skip** - all 8 runs exited 0
with `gate_open=0.0 s`.

**The provenance is the manifest's `scene` block, and all 8 read 3 lanes**
(`logs/p125/shards_scene.txt`, `p125_report.py --store`): every shard carries
`scene.output_lanes` **3 entries** with lane 2 = `/World/OutputBelt2`, belt
centre `(0.84, -0.3375, 1.325)`, place `(0.48, -0.30)`, tray `(1.65, -0.33)`;
`camera_res=240,424`, `biarm_twoline_resolved=1`, `supply.band.schedule=wave`,
grades `A:0.375 B:0.375 C:0.25`. A store without `scene.output_lanes` predates
P123; one with 2 entries is a two-lane store. **Every store recorded before
P125 is a pre-three-lane store.**

The 3-lane smoke (`datasets/p125_smoke`, 5 episodes, seed 499) proved the
manifest before the spend; it is not merged.

## 2. The fine-tune (`checkpoints/p125_three_lane`, local)

`moe_v12` (`3a9ccfc0`) -> **`p125_three_lane`** (`policy_best.pt`
**`69a468d0ea3872cea5d924019549a25b`**), the record's recipe: 6 epochs, lr 5e-5,
`weight-mode ones`, base `datasets/demos_v11` (50 episodes / 9,378 windows),
batch 32, seed 0 (`logs/p125/finetune_history.json`,
`logs/p125/finetune_summary.txt`).

| epoch | mse | router acc | demo val |
| --- | --- | --- | --- |
| 0 | 0.058005 | 0.8234 | 0.025255 |
| 1 | 0.036310 | 0.9257 | 0.028057 |
| 2 | 0.031175 | 0.9558 | 0.027638 |
| 3 | 0.028599 | 0.9708 | 0.012222 |
| 4 | 0.026556 | 0.9784 | 0.015491 |
| 5 | **0.025210** | **0.9833** | 0.018226 |

The loss falls to the record's range (P33's 0.0245 on a 180-episode store), so
the checkpoint **learned the store** - the canary null below is not an
undertrained candidate.

## 3. The canary A/B (three-lane scene, `accept_policy.sh`, 10 episodes/sample)

Same scene, same evaluator defaults (`FRUIT_SUPPLY_SCATTER=0`, camera 240,424,
`SEED=77`), interleaved `A B A B A B`; A = `moe_v12`, B = `p125_three_lane`
(`PREREG.md` `6b236694`, section 4).

| arm | sample 1 | sample 2 | sample 3 | pooled | classes (30) |
| --- | --- | --- | --- | --- | --- |
| **A** `moe_v12` | 6/10 | 6/10 | 5/10 | **17/30 = 56.7 %** | 12 grip loss, 1 station escape |
| **B** `p125_three_lane` | 7/10 | 5/10 | 6/10 | **18/30 = 60.0 %** | 10 grip loss, 2 station escapes |
| **C** (report only) `moe_v12`, **2 lanes** | 5/10 | 6/10 | - | **11/20 = 55.0 %** | 8 grip loss, 1 grasped-not-placed |

**The verdict is DO NOT FLIP by the registered rule**: P1 fails (60.0 % < 80.0 %;
+1 episode of 30 over A), and P2 fails its letter (2 `accept_policy.sh`
`unexpected` reasons in B - the `fruit left the pick station during the close`
class, at 105 and 1184 mm). **Protocol note, recorded not re-read** (P100 A4 /
P103 G5 precedent): the same class fires in **A** too (A2, 957 mm), so P2's
"outside the gate's baseline pair" is narrower than the brief's "same failure
reasons as the control"; P1 fails independently, so the narrowing cannot move
the verdict. Every failure in every arm is the **pick-station grip class**
(`fruit did not follow the gripper` / the station escape), upstream of the
output line; **no failure is at the third lane**, and the place targets are
unchanged (`bin_index` 0/1 on lanes 0/1).

## 4. What the same-batch two-lane control corrects

P124 reverted the third lane because the canary read **4/10 twice on three lanes
against 8/10 on two**, and called it "not a draw". This batch reads
**A (3 lanes, same checkpoint) 56.7 %** and **C (2 lanes, same checkpoint)
55.0 %** - a **+1.7-point scene effect**, inside the loop's recorded 5-8/10
spread (`accept_policy.sh`'s own header: 5-8/10 on this path). The correct
reading is:

* the **8/10 two-lane sample was a high draw** and the **4/10 three-lane
  samples were low draws** of the same ~55-60 % loop; a non-reproducible loop
  cannot carry a scene decision at N=1 or N=2 (P124's own read rule said two
  samples is the minimum - this batch shows two is not enough either);
* the recollection is then a **null with a small positive point estimate**
  (B +1 episode over A, median 60 % vs 60 %), which is what a behaviour-cloning
  pass on the scene's appearance should do when the failures are the **closed
  grip class** (`logs/p42/SIM_LIMIT.md`) rather than an input-shift class - the
  same shape as W7-C, W8-A, P33 and R9.

**So the third lane is not blocked by the policy interface**; it is blocked by
the same ~40 %-of-episodes pick-station grip class the two-lane cell has always
had. The registered bar (B >= 8/10) is a *scene-decision* bar that this loop
cannot meet on either scene at N=3; the negative is published and `=3` stays
opt-in.

## 5. What was not flipped, and the no-harm

* `SceneConfig.output_lanes` stays **2**; **no `src/` or `configs/` change** in
  this phase (`logs/p125/tree_md5_before.txt`; the reference md5s are still
  **`30fb99f8` / `30fb99f8` / `8952c320`**), and **no reference was
  re-recorded** - a reference is per scenario and nothing shipped;
* `scripts/accept_policy.sh` keeps `moe_v12` as its default (amendment A1
  becomes moot on a DO NOT FLIP);
* guards: `scripts/accept.sh` **8/10 + `fingerprint: matches` + `190: PASS`**
  with its `[fruit]` stream byte-identical to the P124 record; `selfcheck.sh`
  **PASS**; `106`/`107` pass; no motion budget touched (the canary's own
  per-episode table carries no motion gate).

## 6. Named next steps

1. **The canary is not a scene-decision instrument at N=3.** Any future scene
   flip should be decided on the **scripted** line + the P123 **tray census**
   (the destination is the product), with the canary reported - or the canary's
   N raised to the direct-loop's WS-4.2 scale (the P93 power lesson: at an
   8-10-point difference the two-sided 0.05 / 80 % sample is hundreds of
   episodes per arm).
2. **The binding success term is the pick-station grip class** (12/30, 10/30,
   8/20 across the three arms here), i.e. `logs/p42/SIM_LIMIT.md`'s closed
   loaded slide and the P41 station escape - not the scene. The hardware
   sanctions in `docs/END_EFFECTOR_DECISION.md` are the levers that remain.
3. The recollected checkpoint is **kept** (`checkpoints/p125_three_lane`) as the
   three-lane candidate for a future larger-N evaluation; it is not deployed.

Evidence: `logs/p125/` (`PREREG.md`, `PREREG_A1.md`, `PREREG_A2.md`,
`METHOD.md`, `p125_report.py`, the collector driver and logs, the fine-tune
history/summary, `canary_{A,B,C}_*` + `.gate`, `p125_report.txt`).
