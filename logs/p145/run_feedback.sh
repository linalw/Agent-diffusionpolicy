#!/usr/bin/env bash
# P145 step 2 (fallback): a feedback-shaped action - action horizon 4, re-plan
# every 4 ticks. The denoiser is fully convolutional over time, so this is a
# fine-tune flag, not a new architecture.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
LINGBOT=/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python
STORE=${STORE:-datasets/p145_dagger150_all}
OUT=${OUT:-checkpoints/p145_fb4}
if [ ! -f "$OUT/policy_best.pt" ]; then
    echo "[p145] train feedback h=4 ($(date +%H:%M:%S))"
    env FRUIT_TRAIN_GOAL=moving FRUIT_DAGGER_FOCUS=20 "$LINGBOT" \
        scripts/111_rl_finetune.py \
        --ckpt checkpoints/moe_v13s/policy_best.pt \
        --rollouts "$STORE" --base "" \
        --close-weight 10 --close-lead 12 --close-tail 15 \
        --action-horizon 4 --first-steps 4 \
        --out "$OUT" --epochs 60 --lr 5e-5 --weight-mode ones \
        --batch-size 64 --seed 0
fi
echo "[p145] fidelity ($(date +%H:%M:%S))"
FRUIT_DAGGER_FOCUS=20 P145_WINDOWS=120 "$LINGBOT" logs/p145/close_fidelity.py \
    "$OUT/policy_best.pt" "$STORE" 2>&1 | grep -a '\[close\]'
echo "[p145] done ($(date +%H:%M:%S))"
