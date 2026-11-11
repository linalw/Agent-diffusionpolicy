#!/usr/bin/env bash
# P141 - the fine-tune that gives the policy the belt channels.
#
# The widened input is the point: goal 8 -> 10 (v_belt, a_belt), proprio 25 -> 26
# (per-frame trace), horizon 2 -> 4. Every widening is a warm start (zero columns
# / a doubled kernel), so the checkpoint starts from the shipped function.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
LINGBOT=${LINGBOT:-/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python}
INIT=${INIT:-checkpoints/moe_v13s/policy_best.pt}
STORE=${STORE:-datasets/p141_wave}
BASE=${BASE:-datasets/demos_v11}
OUT=${OUT:-checkpoints/p141_wave}
EPOCHS=${EPOCHS:-6}
if [ -f "$OUT/policy_best.pt" ]; then echo "[p141] $OUT exists - keeping"; exit 0; fi
echo "[p141] fine-tune $INIT + $STORE + $BASE -> $OUT ($(date +%H:%M:%S))"
env FRUIT_OBS_SPEED=1 FRUIT_OBS_GOAL_AUX=1 "$LINGBOT" scripts/111_rl_finetune.py \
    --ckpt "$INIT" --rollouts "$STORE" --base "$BASE" --out "$OUT" \
    --epochs "$EPOCHS" --lr 5e-5 --weight-mode ones --base-weight 1.0 \
    --batch-size 32 --seed 0 --goal-aux --obs-horizon 4 2>&1 | tail -30
