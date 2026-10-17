#!/usr/bin/env bash
# P10-D.1 stage 1: the GDP A/B (the W7-B direct-boundary pin, interleaved through `112`).
#
# Arm A = the shipped sampling (moe_v13s); Arm B = + FRUIT_POLICY_GDP=1 K=2.
# The boundary envs are the W7-B/W4-pinned form so the mechanism readouts
# (close-start |dx|, no-fire, the class split) compare directly to the W7-B record.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
export RUNS=3
export EPISODES=15
export AB_SEEDS="77 101 202"
export AB_POLICY_SEED=11
export AB_DIR=logs/p10d1/stage1
export ARM_A="--ckpt checkpoints/moe_v13s/policy_best.pt"
export ARM_B="--ckpt checkpoints/moe_v13s/policy_best.pt"
export AB_EXTRA_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=0 FRUIT_POLICY_TRIGGER_LATERAL=0.06 FRUIT_ACQ_DIAG=1"
export ARM_B_ENV="FRUIT_POLICY_GDP=1 FRUIT_POLICY_GDP_K=2"
echo "[p10d1] start $(date +%H:%M:%S)"
bash scripts/112_rl_ab.sh
echo "[p10d1] 112 exit=$? $(date +%H:%M:%S)"
python3 logs/w7/B_ab_report.py --dir logs/p10d1/stage1 --a A --b B > logs/p10d1/stage1_mech.txt 2>&1
echo "[p10d1] report exit=$? $(date +%H:%M:%S)"
echo "[p10d1] done $(date +%H:%M:%S)"
