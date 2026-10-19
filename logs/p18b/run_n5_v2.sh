#!/bin/bash
# P18-B v2: the L3 stage-N battery with the FULL stage-N env (the R11-B's B_N_driver.log line 5)
# + a precondition check after A run 1 (the Oracle Gate-2 fix; the v1 battery was invalid:
# it omitted FRUIT_DYNAMIC_PICK=1 + the trigger pair + the supply triple, so arm B was inert).
cd "$(dirname "$0")/../.." || exit 1
export RUNS=5 EPISODES=15 AB_POLICY_SEED=11
export AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1"
export ARM_A="--ckpt checkpoints/moe_v13s/policy_best.pt"
export ARM_B="--ckpt checkpoints/moe_v13s/policy_best.pt"
export ARM_B_ENV="FRUIT_CLOSE_LOAD_RATE=0.04"
export AB_DIR=logs/p18b/N5_fix
echo "[p18b] START $(date +%H:%M:%S)"
scripts/112_rl_ab.sh &
AB_PID=$!
# the precondition check after A run 1 completes
for i in $(seq 1 300); do
    if grep -qa 'rollout success' logs/p18b/N5_fix/A_1.log 2>/dev/null; then break; fi
    sleep 20
done
sleep 5
python3 logs/p18b/check_preconditions.py logs/p18b/N5_fix/A_1.log
rc=$?
if [ $rc -ne 0 ]; then
    echo "[p18b] PRECONDITION FAIL (rc=$rc) - killing the battery"
    kill $AB_PID 2>/dev/null
    sleep 3
    pkill -P $AB_PID 2>/dev/null
    exit 3
fi
echo "[p18b] preconditions OK - battery continues"
wait $AB_PID
echo "[p18b] exit=$? $(date +%H:%M:%S)"
