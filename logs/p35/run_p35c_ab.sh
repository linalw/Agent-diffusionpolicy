#!/usr/bin/env bash
# P35 phase 2 RECORD OF RECORD: the arm-park A/B under the Gate-1 P0 check
# (the fixed `FRUIT_PARK_DIAG`: M1 vs the achieved settled pose, M2 at the
# +0.30..+0.40 band's worst call, the projected-disc bbox, the stale first call
# skipped). The pre-P0 batch is `logs/p35/B_ab` (superseded, kept as provenance).
# The P33/W8-A direct protocol:
#
#   A = the shipped direct env            (`FRUIT_ARM_PARK=ready`, explicit - A2)
#   B = `FRUIT_ARM_PARK=back`             (the inactive LEFT arm only)
#   N = 5 runs/arm x 15 episodes, seeds 77/101/202/303/404, sampler seed 11,
#   interleaved A,B,A,B... in one `scripts/154_claim_run.sh` claim.
#   Scenario = the P33/W8-A patch sheet verbatim + the check on BOTH arms
#   (`FRUIT_RESET_ALIGN_DIAG=1` for the pfc/pcm counters, `FRUIT_PARK_DIAG=1`
#   for the per-call park census, `FRUIT_ACQ_DIAG=1`).
#
#   nohup bash logs/p35/run_p35c_ab.sh > logs/p35/C_outer.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p35/C_ab

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"

if [ ! -f "$CKPT" ]; then echo "[p35c-ab] FAIL: no checkpoint at $CKPT"; exit 1; fi
md5sum "$CKPT" > logs/p35/C_ab/C_ckpt_md5.txt
md5sum src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
    src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
    src/fruit_sorting/meshes.py configs/arm_parks.json \
    > logs/p35/C_ab/C_tree_md5_before.txt
git rev-parse HEAD > logs/p35/C_ab/C_head.txt

export RUNS=5
export EPISODES=15
export AB_SEEDS="77 101 202 303 404"
export AB_POLICY_SEED=11
export AB_DIR=logs/p35/C_ab
export ARM_A="--ckpt $CKPT"
export ARM_B="--ckpt $CKPT"
# P43 phase 4 (A2): A is the *pre-park* arm, so it must say so. Since the P43
# flip the direct presentation's default is `back`, and an unset
# `FRUIT_ARM_PARK` would silently make A == B (the P35/P43 numbers would then
# be a park-vs-park null). `ready` restores the shipped pose exactly.
export ARM_A_ENV="FRUIT_ARM_PARK=ready"
export ARM_B_ENV="FRUIT_ARM_PARK=back"
export AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 $PATCH_ENV FRUIT_ACQ_DIAG=1 FRUIT_RESET_ALIGN_DIAG=1 FRUIT_PARK_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1"

echo "[p35c-ab] start $(date +%H:%M:%S)"
RUN_LIMIT=25200 scripts/154_claim_run.sh logs/p35/C_ab/C_driver.log \
    bash -c 'bash scripts/112_rl_ab.sh'
echo "[p35c-ab] batch exit=$? $(date +%H:%M:%S)"

python3 logs/p35/park_ab_report.py --dir logs/p35/C_ab --a A --b B \
    > logs/p35/C_ab/C_report.txt 2>&1
echo "[p35c-ab] park report exit=$?"
python3 logs/w7/C_class_split.py --dir logs/p35/C_ab --a A --b B \
    > logs/p35/C_ab/C_class_split.txt 2>&1
echo "[p35c-ab] class split exit=$?"
python3 logs/w8/A_pairs.py --dir logs/p35/C_ab --a A --b B \
    > logs/p35/C_ab/C_pairs.txt 2>&1
echo "[p35c-ab] pairs exit=$?"

md5sum src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
    src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
    src/fruit_sorting/meshes.py configs/arm_parks.json \
    > logs/p35/C_ab/C_tree_md5_after.txt
echo "[p35c-ab] done $(date +%H:%M:%S)"
