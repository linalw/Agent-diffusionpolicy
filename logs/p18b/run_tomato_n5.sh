#!/bin/bash
# P18-B.1: the class-matched L3 re-run (the pre-registration logs/p18b/PREREG_TOMATO.md).
# Single-species tomato supply (FRUIT_SUPPLY_SPECIES=tomato, the P1c tool) + the stage-N env;
# A = moe_v13s, B = moe_v13s + FRUIT_CLOSE_LOAD_RATE=0.04; N=5 x 15, interleaved.
cd "$(dirname "$0")/../.." || exit 1
export RUNS=5 EPISODES=15 AB_POLICY_SEED=11
export AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_SPECIES=tomato FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1"
export ARM_A="--ckpt checkpoints/moe_v13s/policy_best.pt"
export ARM_B="--ckpt checkpoints/moe_v13s/policy_best.pt"
export ARM_B_ENV="FRUIT_CLOSE_LOAD_RATE=0.04"
export AB_DIR=logs/p18b/N5_tomato
echo "[p18b1] START $(date +%H:%M:%S)"
scripts/112_rl_ab.sh &
AB_PID=$!
for i in $(seq 1 300); do
    if grep -qa 'rollout success' logs/p18b/N5_tomato/A_1.log 2>/dev/null; then break; fi
    sleep 20
done
sleep 5
python3 logs/p18b/check_preconditions.py logs/p18b/N5_tomato/A_1.log
rc=$?
if [ $rc -ne 0 ]; then
    echo "[p18b1] PRECONDITION FAIL (rc=$rc) - killing the battery"
    kill $AB_PID 2>/dev/null
    sleep 3
    pkill -P $AB_PID 2>/dev/null
    exit 3
fi
echo "[p18b1] preconditions OK - battery continues"
wait $AB_PID
echo "[p18b1] exit=$? $(date +%H:%M:%S)"
