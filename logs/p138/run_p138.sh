#!/usr/bin/env bash
# P138 - the fine-tune on the flipped tree's recollection.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
LINGBOT=${LINGBOT:-/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python}
INIT=${INIT:-checkpoints/moe_v13s/policy_best.pt}
STORE=${STORE:-datasets/p138_track}
BASE=${BASE:-datasets/demos_v11}
OUT=${OUT:-checkpoints/p138_track}
if [ -f "$OUT/policy_best.pt" ]; then echo "[p138] $OUT exists - keeping"; exit 0; fi
echo "[p138] fine-tune $INIT + $STORE + $BASE -> $OUT ($(date +%H:%M:%S))"
"$LINGBOT" scripts/111_rl_finetune.py \
    --ckpt "$INIT" --rollouts "$STORE" --base "$BASE" --out "$OUT" \
    --epochs 6 --lr 5e-5 --weight-mode ones --base-weight 1.0 \
    --batch-size 32 --seed 0 2>&1 | tail -20
