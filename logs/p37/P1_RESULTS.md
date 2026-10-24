# P37 phase 1 — the pre-registration and the park-collected store (the record)

Measured 2026-10-24, Tier A solo. Phase 1 of
`.slim/deepwork/p37-park-recollection.md`. **No shipped default changed**
(`FRUIT_ARM_PARK` stays default off, `FRUIT_PROPRIO_SPOOF` unused), **no
`src/` change**, **no commit**; the tree md5s before the collection are in
`logs/p37/tree_md5_before.txt` and are the current tree's
(`tasks.py` `cdde6bd2`, `rl_env.py` `aa54b022`, `trigger.py` `d7ec85fc`,
`runtime.py` `379ac706`, `meshes.py` `41efc522`, `arm_parks.json` `42ab4fb7`,
`motion_reference.json` `25ade92b`, `moe_v13s` `61da390a`, `demos_v11`
`922ca995`, HEAD `8d6bca5`).

**The one-line answer.** The park-collected direct-rollout store exists at the
pre-registered target: **`datasets/rl_rollouts/p37_park`, 90 episodes from six
seeds, 57 ok / 26 carried-not-placed / 7 no-grasp (63.3 % ok), 5,228 frames,
3,698 training windows, 1.3 GB**, index md5 **`1ece5f9f`**, merge md5
**`5d462183`**, every shard's manifest naming **`arm_park = back` (left)**,
`moe_v13s` `61da390a`, `tasks.py` `cdde6bd2`, belt 0.12, camera 240,424,
trigger `arrival/lead=0.9/lat=0.16/acq/frame=station`, `proprio_spoof: null`.
**The parked branch is legible in the store itself**: the right arm (the park's
population) reads **54/58 ok with 0 carried-not-placed** — P35's B-arm signature
(0/50 carried) — while the left (the park's no-op side) reads 3/32 ok with 26
carried.

## 1. The pre-registration (`logs/p37/PREREG.md`)

Written **before** the first run of this phase. It fixes: the scenario (the
direct env, the patch sheet, the arrival trigger + ACQ, `moe_v13s`, the park
`back` on); the store recipe (six shards x 15, seeds 505/606/707/808/909/1010,
target 90 / floor 60, no diagnostics, merge by `197`); the fine-tune
(`weight_mode=ones`, 6 epochs, lr 5e-5, base `demos_v11` at 1.0, anchor
`moe_v13s`); the A/B (**N = 5 x 15, both arms parked**, seeds
77/101/202/303/404, sampler 11, interleaved, one claim, the same
instrumentation on both arms); the endpoints, the decision rule, the
falsifiers and the confounds.

**Why `ones` and not the R9 AWR** (fixed in the pre-registration, not after the
data): `ones` is the mode every lineage checkpoint was trained with
(`moe_v13s`, `moe_v13p`: 6 epochs, lr 5e-5, base `demos_v11`), and the two
alternatives carry **measured negatives on this interface** — `success`
weighting *is* RWR iteration 1 (49 % vs 63 %), `awr` is R9 (`rl_awr1` 18/75 vs
25/75, carried 5-4 p = 0.500, fidelity 0.087 -> 0.174 rad away from its own
rollouts). The store's failures are also not the recorded phase's failures (the
policy phase is the pre-trigger approach; R9 measured the carry window
branch-invariant), so weighting approaches by outcome selects on a label their
phase does not own.

**The primary's power** (`logs/p37/power_check.py`, design-only, no outcome
data): the pre-registered non-inferiority bar (`B right ok rate >= A - 0.10`,
n ~ 50 right-arm episodes/arm, base 0.94) **passes a preserved candidate in
99.1 %** of batches (0.9 % false-erasure), **passes the erasure state (p ~ 0.45)
in 0.0 %**, and reads an in-between candidate (p = 0.85) at 60.8 % — reported as
ambiguous. The run-level direction is reported, not gated.

**A design fact the phase fixes in advance**: the P33 paired carried-class
endpoint (the repo's default since P33) is **degenerate under the park** — the
park's own arm read 0/50 carried (P35) and the store's right arm 0/58
(below) — so it is a report, and the primary is the right-arm placed-rate
non-inferiority.

## 2. The collection

`scripts/221_p37_collect.sh`, one `scripts/154_claim_run.sh` claim per shard,
22:37:28 -> 23:24:06 (**46.6 min**, merge included); no wedge, no retry, no
spare seed, every shard complete on the first pass:

| shard (seed) | episodes | ok | carried | no-grasp | left / right | index md5 |
| --- | --- | --- | --- | --- | --- | --- |
| 505 | 15 | 9 | 4 | 2 | 5 / 10 | `e7e38b6f` |
| 606 | 15 | 11 | 4 | 0 | 5 / 10 | `735852d1` |
| 707 | 15 | 9 | 5 | 1 | 6 / 9 | `7a7704df` |
| 808 | 15 | 9 | 5 | 1 | 5 / 10 | `d57d887b` |
| 909 | 15 | 9 | 3 | 3 | 6 / 9 | `03916e64` |
| 1010 | 15 | 10 | 5 | 0 | 5 / 10 | `49653ed6` |
| **store** | **90** | **57** | **26** | **7** | **32 / 58** | **`1ece5f9f`** |

The scenario is the PREREG section 2 block verbatim (`FRUIT_ARM_PARK=back`, the
patch sheet, `arrival`/0.9/ACQ, `moe_v13s`, `--record`, `--execute-steps 4
--ddim 16`, camera 240,424, `FRUIT_POLICY_SEED=11`), **no diagnostics** in the
store. `logs/p37/collect_seed*.log`, `logs/p37/merge.log`,
`logs/p37/collect_driver.log`.

**Expected vs measured composition** (the PREREG quoted P35's expectations; a
deviation is reported, not smoothed):

| | PREREG expectation (P35) | measured |
| --- | --- | --- |
| right share | ~68 % | **58/90 = 64.4 %** (P36's cell 1 read 64 %) |
| right ok | ~94 % | **54/58 = 93.1 %** |
| right carried | ~0 | **0/58** |
| left ok | ~8 % | **3/32 = 9.4 %** |
| pooled ok | ~65 % | **57/90 = 63.3 %** |

Grades A 32 / B 32 / C 26 (the 0.375/0.375/0.25 mix's expected 34/34/22, inside
the seeded spread); 8 species (tomato 18, orange 14, peach 11, kiwi 11, pear 11,
apple 10, strawberry 9, lychee 6); diameter 2.91-6.96 cm (median 6.22); reward
mean 0.613 with 33 zero-reward episodes; frames/episode 23/57/103.

## 3. The store audit (`logs/p37/store_audit.txt`, `store_audit_106.txt`)

**`logs/p37/store_audit.py`** (the `106`-style bookkeeping **plus** the RL
fields) reads **OK**: 90 entries / 90 files, `index_frames == file_frames ==
5,228`, no duplicate entry, no missing file, no unlisted file, no stale
`frames`, **90 unique contents**; the merge manifest's `episodes=90 /
successes=57` agree with the index; all six shard manifests agree on every
provenance field, and `arm_park` is `{"name":"back","sides":["left"],"source":
"logs/p35/park_sweep.json"}` in all six.

`python3 scripts/106_index_audit.py --root datasets/rl_rollouts --fast` reports
`p37_park entries=90 files=90 index_frames=5228 file_frames=5228 windows=3698
unique_content=90 OK` (captured whole in `store_audit_106.txt`; it also audits
the older rollout stores — those readings are not part of this phase).

**The format** is the training schema `EpisodeStore` reads (`image_rgb`,
`image_distance_to_image_plane`, `target_mask`, `joint_positions`,
`finger_opening`, `tactile`, `goal`, `fruit_position`, `action`), verified
end-to-end offline: `EpisodeStore(datasets/rl_rollouts/p37_park,
only_successful=False)` loads 90 episodes / 3,698 windows and yields
`image (2,5,128,128), proprio (25,), goal (8,), action (16,9)` — the same
loader `scripts/111_rl_finetune.py` uses (`only_successful=False` for the
rollout store, `True` for the base), so `weight_mode=ones` really does weight
all 90 episodes.

**Provenance** (`logs/p37/store_provenance.txt`): the pins, the exact env block
and command, the six shard rows with their index md5s, the store's own
`index.json` / `merge_manifest.json` md5s, the manifest chain per shard, and
the recorded limitations. The one that matters for phase 2: the rollout
manifest has **no supply block**, so the patch sheet is pinned by the recorded
command + shard logs, not by the manifest (adding it moves the `rl_env.py`
pin — its own change).

## 4. The phase-2 contract (unchanged from the PREREG)

```
scripts/111_rl_finetune.py --ckpt checkpoints/moe_v13s/policy_best.pt \
    --rollouts datasets/rl_rollouts/p37_park --base datasets/demos_v11 \
    --out checkpoints/p37_park --epochs 6 --lr 5e-5 --weight-mode ones \
    --base-weight 1.0 --batch-size 32 --seed 0
```

At the measured store: **3,698 rollout windows + 9,378 base windows = 13,076**
(~409 steps/epoch at batch 32; ~2,450 steps over 6 epochs), i.e. a **28.3 %
rollout window share** against the recollection precedent's 77 %
(`demos_v13p` 32,284 vs 9,378) — the pre-registered confound, now with its
number.

The A/B: `scripts/112_rl_ab.sh` under one `154_claim_run.sh` claim,
`RUNS=5 EPISODES=15 AB_SEEDS="77 101 202 303 404" AB_POLICY_SEED=11`,
`ARM_A="--ckpt checkpoints/moe_v13s/policy_best.pt"`,
`ARM_B="--ckpt checkpoints/p37_park/policy_best.pt"`, and
`AB_EXTRA_ENV` = the PREREG section-2 block + `FRUIT_ARM_PARK=back` +
`FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_PARK_DIAG=1` (**both** arms parked,
same instrumentation). The candidate's md5 and `finetune_history.json` are
recorded **before** the batch, one-way.

## 5. No-harm

* `scripts/selfcheck.sh`: **PASS, 0 failures, 1 skipped** (the motion-budget leg,
  supplied by the acceptance) — before and after.
* The scripted acceptance with both knobs **unset** (`logs/p37/accept_no_harm.log`
  + `accept_no_harm.out`): **6/10 + `fingerprint: matches
  configs/motion_reference.json`**, the pre-existing P32 pear-on branch (the
  rate-only `exit=1` is expected), and its **376 `[fruit]` lines are IDENTICAL**
  to the P36 record (`logs/p37/accept_identity.txt`: 376/376, `diff` empty).
* The tree is unchanged (`logs/p37/tree_md5_before.txt`; no `src/`, `configs/`
  or checkpoint write). `git status` shows only the new
  `scripts/221_p37_collect.sh`; `logs/` and `datasets/` are gitignored
  (committing the evidence needs `git add -f`, the P35/P36 convention).

## 6. What this phase does not show, and the risks it hands to phase 2

* **Nothing about the win yet.** The store is data; whether a fine-tune on it
  preserves the park's 94 % is the A/B's question (phase 2). The store's own
  class split confirms *what was collected*, not what will be learned.
* **The collected distribution is the deployment mixture, not a designed
  balance**: 58 right-active episodes carry the parked image and 32 left-active
  ones carry the shipped inactive-arm distribution (the park file has no right
  vector). Under `ones` the left's 26 carry failures sit at weight 1.0 — the
  pre-registered confound #1, now quantified.
* **The base:rollout window ratio is 72:28 in the base's favour**, so the
  `ready`-distribution base can dominate the update — the named mechanism for
  an erasure. The fidelity readout (phase 2, not a gate) is the pre-batch
  diagnostic.
* **The outcome is quantized and the policy loop is not reproducible**; the A/B
  is N = 5 x 15 with its own arm A as baseline, one run = one sample, and the
  A-then-B order inside each run is a recorded confound.
* **The park's population is the right arm only** (~58 of 90 store episodes,
  ~50 of 75 A/B episodes): the primary's n is ~50 per arm, which is what the
  power table above assumes. If the A/B's right share lands lower than 60 %,
  the bar reads a smaller n and the ambiguous band widens — report, not re-run.

## 7. Files

`logs/p37/`: `PREREG.md` (sections 1-10; §10 deviations), `P1_RESULTS.md` (this),
`power_check.py` / `power_check.txt`, `store_audit.py` / `store_audit.txt` /
`store_audit_106.txt`, `store_provenance.txt`, `collect_driver.log`,
`collect_seed505|606|707|808|909|1010.log`, `merge.log`, `collect_outer.log`
(the six `[claim_run] claimed/exit` lines; the driver's own log is
`collect_driver.log`), `smoke.log` + `smoke_store_audit.txt` (the 2-episode
instrumented path check; **not** part of the store), `tree_md5_before.txt`,
`accept_no_harm.log` / `.out` / `accept_no_harm_stream.log` /
`accept_identity.txt`, `accept_claim.log` (empty **by construction**: the
acceptance's own output was redirected inside the claim wrapper, so the claim's
`claimed 23:26:57 / exit=1 23:31:23` lines went to the driving terminal and the
run is `accept_no_harm.log` + the gate in `accept_no_harm.out`),
`selfcheck_after.log`.
Driver: `scripts/221_p37_collect.sh`. Store: `datasets/rl_rollouts/p37_park`
(parts: `datasets/rl_rollouts/p37_parts`; the smoke: `p37_smoke`).
