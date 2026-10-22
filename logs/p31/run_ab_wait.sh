#!/bin/bash
# P31-B: the N=5 paired direct A/B (the wait gate off vs on) at the shipped 0.12.
cd "$(dirname "$0")/../.." || exit 1
base="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_BELT_SPEED=0.12"
RUNS=5 EPISODES=15 AB_POLICY_SEED=11 \
ARM_A="--ckpt checkpoints/moe_v13s/policy_best.pt" ARM_B="--ckpt checkpoints/moe_v13s/policy_best.pt" \
ARM_A_ENV="FRUIT_WAIT_GATE=0" ARM_B_ENV="FRUIT_WAIT_GATE=1" \
AB_EXTRA_ENV="$base" AB_DIR=logs/p31/ab scripts/112_rl_ab.sh > logs/p31/90_driver_ab.log 2>&1
echo "[p31b] exit=$? $(date +%H:%M:%S)"
