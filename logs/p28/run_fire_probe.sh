#!/bin/bash
# P28-G2: the fire-timing probe (the Gate-D rank-1): the trigger-off cells + the ACQ diag, so the
# model-side gate's fire ticks / residuals / edges are logged (the autonomy gap's 20-min probe).
cd "$(dirname "$0")/../.." || exit 1
base="FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_BELT_SPEED=0.12"
run_arm() {
    local tag=$1 ckpt=$2 obs=$3
    echo "[probe] START $(date +%H:%M:%S) $tag"
    RUN_LIMIT=3600 scripts/154_claim_run.sh logs/p28/probe_${tag}.log $base FRUIT_OBS_SPEED=$obs \
        HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 \
        FRUIT_NO_SLEEP=1 scripts/run.sh scripts/110_rl_rollout.py --ckpt "$ckpt" \
        --presentation direct --episodes 15 --seeds 77 --out logs/p28/raw_probe_${tag} \
        > logs/p28/probe_${tag}_driver.log 2>&1
    echo "[probe] exit=$? $(date +%H:%M:%S) $tag"
}
run_arm A checkpoints/moe_v13s/policy_best.pt 0
run_arm B checkpoints/spd_v1/policy_best.pt 1
echo "[probe] DONE $(date +%H:%M:%S)"
