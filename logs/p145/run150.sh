#!/usr/bin/env bash
# P145 step 1: the >=150-episode DAgger store, merged, trained, and scored on the
# offline close-fidelity endpoint. Waits for the collector to exit first.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
PID=${1:-}
if [ -n "$PID" ]; then
    while kill -0 "$PID" 2>/dev/null; do sleep 30; done
fi
N=$(ls datasets/p145_dagger150/*/*.npz 2>/dev/null | wc -l)
echo "[p145] collector done: $N episodes ($(date +%H:%M:%S))"
python3 logs/p145/merge_shards.py datasets/p145_dagger150 datasets/p145_dagger150_all
LINGBOT=/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python
if [ ! -f checkpoints/p145_a150/policy_best.pt ]; then
    echo "[p145] train a150 ($(date +%H:%M:%S))"
    env FRUIT_TRAIN_GOAL=moving FRUIT_DAGGER_FOCUS=20 "$LINGBOT" \
        scripts/111_rl_finetune.py \
        --ckpt checkpoints/moe_v13s/policy_best.pt \
        --rollouts datasets/p145_dagger150_all --base "" \
        --close-weight 10 --close-lead 12 --close-tail 15 \
        --out checkpoints/p145_a150 --epochs 60 --lr 5e-5 --weight-mode ones \
        --batch-size 64 --seed 0
fi
echo "[p145] fidelity ($(date +%H:%M:%S))"
FRUIT_DAGGER_FOCUS=20 P145_WINDOWS=120 "$LINGBOT" logs/p145/close_fidelity.py \
    checkpoints/p145_a150/policy_best.pt datasets/p145_dagger150_all \
    2>&1 | grep -a '\[close\]'
echo "[p145] done ($(date +%H:%M:%S))"
