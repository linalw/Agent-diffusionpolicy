#!/usr/bin/env bash
# P138 - the direct A/B (N=5 x 15, the WS-4.2 protocol): the init vs the
# fine-tune on the shipped direct interface. Interleaved A,B,A,B; the same
# policy seed; one simulator session per run.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
ARM_A="--ckpt checkpoints/moe_v13s/policy_best.pt" \
ARM_B="--ckpt checkpoints/p138_track/policy_best.pt" \
AB_DIR=logs/p138/ab RUNS=5 EPISODES=15 AB_POLICY_SEED=11 \
SKIP_SELFCHECK=1 bash scripts/112_rl_ab.sh 2>&1 | tail -40
