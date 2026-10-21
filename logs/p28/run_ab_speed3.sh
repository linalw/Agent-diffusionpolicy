#!/bin/bash
# P28-E v3: the speed-aware vs blind A/B on the SHIPPED interface (the trigger on + ACQ).
cd "$(dirname "$0")/../.." || exit 1
base="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1"
run_speed() {
    local tag=$1 sp=$2
    echo "[p28e3] START $(date +%H:%M:%S) $tag @ $sp"
    RUNS=1 EPISODES=15 AB_SEEDS=77 AB_POLICY_SEED=11 \
    ARM_A="--ckpt checkpoints/moe_v13s/policy_best.pt" \
    ARM_B="--ckpt checkpoints/spd_v1/policy_best.pt" \
    ARM_A_ENV="FRUIT_OBS_SPEED=0" ARM_B_ENV="FRUIT_OBS_SPEED=1" \
    AB_EXTRA_ENV="$base FRUIT_BELT_SPEED=$sp" \
    AB_DIR=logs/p28e/${tag}v3 scripts/112_rl_ab.sh > logs/p28e/${tag}v3_driver.log 2>&1
    echo "[p28e3] exit=$? $(date +%H:%M:%S) $tag"
}
run_speed spd012_n1 0.12
run_speed spd008_n1 0.08
run_speed spd015_n1 0.15
echo "[p28e3] DONE $(date +%H:%M:%S)"
