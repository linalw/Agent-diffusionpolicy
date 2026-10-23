#!/usr/bin/env bash
# P33 phase 3 step 3: the post-pear direct A/B + the hybrid canary smoke.
#
#   ARM A = checkpoints/moe_v13s/policy_best.pt   (the pre-pear direct anchor)
#   ARM B = checkpoints/p33_pear/policy_best.pt   (the post-pear recollection)
#   N = 3 runs/arm x 15 episodes, seeds 77/101/202, sampler seed 11,
#   interleaved A,B,A,B... (`scripts/112_rl_ab.sh`); the W8-A scenario env
#   verbatim: patch sheet (scatter+patch, balanced A:B:C 0.375/0.375/0.25),
#   arrival trigger lead 0.9 s, the 0.16 m lateral gate default, dynamic
#   never-stop, `FRUIT_ACQ_DIAG=1` + `FRUIT_POLICY_TRIGGER_ACQ=1` on BOTH arms.
#
# One `154_claim_run.sh` claim covers the batch (Tier A solo), then the read-only
# reports, then the hybrid canary (a **smoke**: one sample, the pre-pear spread
# 5-8/10, never a rate).
#
#   nohup bash logs/p33/run_p33c_ab.sh > logs/p33/E_outer.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p33/E_ab

CKPT_A=checkpoints/moe_v13s/policy_best.pt
CKPT_B=checkpoints/p33_pear/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"

if [ ! -f "$CKPT_B" ]; then echo "[p33c-ab] FAIL: no candidate at $CKPT_B"; exit 1; fi
md5sum "$CKPT_A" "$CKPT_B" > logs/p33/E_ab/E_ckpt_md5.txt
md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
    src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
    src/fruit_sorting/meshes.py > logs/p33/E_ab/E_tree_md5_before.txt
git rev-parse HEAD > logs/p33/E_ab/E_head.txt

export RUNS=3
export EPISODES=15
export AB_SEEDS="77 101 202"
export AB_POLICY_SEED=11
export AB_DIR=logs/p33/E_ab
export ARM_A="--ckpt $CKPT_A"
export ARM_B="--ckpt $CKPT_B"
export AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 $PATCH_ENV FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1"

echo "[p33c-ab] start $(date +%H:%M:%S)"
RUN_LIMIT=18000 scripts/154_claim_run.sh logs/p33/E_ab/E_driver.log \
    bash -c 'bash scripts/112_rl_ab.sh'
echo "[p33c-ab] batch exit=$? $(date +%H:%M:%S)"

python3 logs/w7/B_ab_report.py --dir logs/p33/E_ab --a A --b B \
    > logs/p33/E_ab/E_mech.txt 2>&1
echo "[p33c-ab] mech exit=$?"
python3 logs/w7/C_class_split.py --dir logs/p33/E_ab --a A --b B \
    > logs/p33/E_ab/E_class_split.txt 2>&1
echo "[p33c-ab] class split exit=$?"
python3 scripts/113_rl_report.py logs/p33/E_ab --a A --b B \
    > logs/p33/E_ab/E_verdict.txt 2>&1
echo "[p33c-ab] verdict exit=$?"
python3 logs/w8/A_pairs.py --dir logs/p33/E_ab --a A --b B \
    > logs/p33/E_ab/E_pairs.txt 2>&1
echo "[p33c-ab] pairs exit=$?"

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
    src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
    src/fruit_sorting/meshes.py > logs/p33/E_ab/E_tree_md5_after.txt

# The hybrid canary: `accept_policy.sh`'s gate scenario (the pre-v9 FIXED
# supply, `FRUIT_SUPPLY_SCATTER=0` - its pin). One sample = a smoke.
echo "[p33c-ab] hybrid canary smoke (fixed-supply pin) $(date +%H:%M:%S)"
RUN_LIMIT=7200 scripts/154_claim_run.sh logs/p33/E_canary.driver.log \
    FRUIT_CKPT="$CKPT_B" FRUIT_EPISODES=10 \
    ACCEPT_POLICY_LOG=logs/p33/E_canary.log \
    SKIP_SELFCHECK=1 scripts/accept_policy.sh
echo "[p33c-ab] canary exit=$? $(date +%H:%M:%S)"
echo "[p33c-ab] done $(date +%H:%M:%S)"
