#!/usr/bin/env bash
# P34 phase 2: the reset-alignment A/B (`logs/p34/PREREG.md`).
#
#   A = control      : the shipped direct env (FRUIT_RESET_ALIGN unset)
#   B = aligned      : FRUIT_RESET_ALIGN=1 (first model call at along ~0.399)
#   both             : moe_v13s (61da390a), the P33 W8-A patch scenario,
#                      arrival trigger + ACQ, N=5 x 15, seeds 77/101/202/303/404,
#                      sampler seed 11, interleaved A,B,A,B...
#   one 154_claim_run.sh claim covers the whole batch (Tier A solo), then the
#   read-only reports.
#
#   SMOKE=1 bash logs/p34/run_p34_ab.sh   # 1 run x 2 episodes per arm, the
#                                         # `[align]` rows only (the smoke)
#   bash logs/p34/run_p34_ab.sh           # the pre-registered batch (~1-1.5 h)
#
# Env for the run: HEADLESS=1, camera 240,424, FRUIT_NO_ATTACH=1, FRUIT_NO_SLEEP=1.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCENARIO="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 $PATCH_ENV FRUIT_ACQ_DIAG=1 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_RESET_ALIGN_DIAG=1"
COMMON="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"

if [ ! -f "$CKPT" ]; then echo "[p34-ab] FAIL: no checkpoint at $CKPT"; exit 1; fi
md5sum "$CKPT" > logs/p34/70_ckpt_md5.txt
md5sum src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
    src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
    src/fruit_sorting/meshes.py > logs/p34/71_tree_md5_before_ab.txt

if [ "${SMOKE:-0}" = "1" ]; then
    echo "[p34-ab] SMOKE: 2 episodes/arm, the [align] rows $(date +%H:%M:%S)"
    RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p34/S0_control.log \
        env $COMMON $SCENARIO scripts/run.sh scripts/110_rl_rollout.py \
        --ckpt "$CKPT" --presentation direct --episodes 2 --seeds 77 \
        --out logs/p34/S0_raw
    echo "[p34-ab] smoke A exit=$? $(date +%H:%M:%S)"
    RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p34/S1_align.log \
        env $COMMON $SCENARIO FRUIT_RESET_ALIGN=1 scripts/run.sh scripts/110_rl_rollout.py \
        --ckpt "$CKPT" --presentation direct --episodes 2 --seeds 77 \
        --out logs/p34/S1_raw
    echo "[p34-ab] smoke B exit=$? $(date +%H:%M:%S)"
    grep -h "\[align\]" logs/p34/S0_control.log logs/p34/S1_align.log \
        > logs/p34/S2_align_rows.txt
    cat logs/p34/S2_align_rows.txt
    exit 0
fi

export RUNS=5
export EPISODES=15
export AB_SEEDS="77 101 202 303 404"
export AB_POLICY_SEED=11
export AB_DIR=logs/p34/A_ab
export ARM_A="--ckpt $CKPT"
export ARM_B="--ckpt $CKPT"
export AB_EXTRA_ENV="$SCENARIO"
export ARM_B_ENV="FRUIT_RESET_ALIGN=1"

mkdir -p logs/p34/A_ab
echo "[p34-ab] start $(date +%H:%M:%S)"
RUN_LIMIT=18000 scripts/154_claim_run.sh logs/p34/A_driver.log \
    bash -c 'bash scripts/112_rl_ab.sh'
echo "[p34-ab] batch exit=$? $(date +%H:%M:%S)"

python3 logs/p34/align_report.py --dir logs/p34/A_ab --a A --b B \
    > logs/p34/A_align.txt 2>&1
echo "[p34-ab] align report exit=$?"
python3 scripts/113_rl_report.py logs/p34/A_ab --a A --b B \
    > logs/p34/A_verdict.txt 2>&1
echo "[p34-ab] verdict exit=$?"
python3 logs/w7/C_class_split.py --dir logs/p34/A_ab --a A --b B \
    > logs/p34/A_class_split.txt 2>&1
echo "[p34-ab] class split exit=$?"
python3 logs/w7/B_ab_report.py --dir logs/p34/A_ab --a A --b B \
    > logs/p34/A_mech.txt 2>&1
echo "[p34-ab] mech exit=$?"
python3 logs/w8/A_pairs.py --dir logs/p34/A_ab --a A --b B \
    > logs/p34/A_pairs.txt 2>&1
echo "[p34-ab] pairs exit=$?"

md5sum src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
    src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
    src/fruit_sorting/meshes.py > logs/p34/72_tree_md5_after_ab.txt
echo "[p34-ab] done $(date +%H:%M:%S)"
