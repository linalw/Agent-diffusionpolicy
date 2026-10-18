#!/usr/bin/env bash
# P13-B: the ev1 (event heads) vs moe_v13s A/B, the W7-B boundary pin, N=3x15.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
export RUNS=3
export EPISODES=15
export AB_SEEDS="77 101 202"
export AB_POLICY_SEED=11
export AB_DIR=logs/p13/B_ab
export ARM_A="--ckpt checkpoints/moe_v13s/policy_best.pt"
export ARM_B="--ckpt checkpoints/ev1/policy_best.pt"
export AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=0 FRUIT_POLICY_TRIGGER_LATERAL=0.06 FRUIT_ACQ_DIAG=1"
echo "[p13b] start $(date +%H:%M:%S)"
bash scripts/112_rl_ab.sh
echo "[p13b] 112 exit=$? $(date +%H:%M:%S)"
python3 logs/w7/B_ab_report.py --dir logs/p13/B_ab --a A --b B > logs/p13/B_mech.txt 2>&1
python3 scripts/113_rl_report.py logs/p13/B_ab --a A --b B > logs/p13/B_outcome.txt 2>&1
echo "[p13b] reports exit=$? $(date +%H:%M:%S)"
echo "[p13b] DONE $(date +%H:%M:%S)"
