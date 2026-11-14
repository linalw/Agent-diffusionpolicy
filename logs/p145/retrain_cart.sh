#!/usr/bin/env bash
# P145d.1: 4-D cartesian policy on the commanded-target store, then one honest cell.
set -u
cd "$(dirname "$0")/../.." || exit 1
LINGBOT=/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python
STORE=${STORE:-datasets/p145_tcp2}
SEED=${SEED:-checkpoints/p145_cart2_seed}
OUT=${OUT:-checkpoints/p145_cart2}
if [ ! -f "$SEED/policy_best.pt" ]; then
    env P145_STORE="$STORE" "$LINGBOT" logs/p145/make_cart_seed.py
    # the seed writer's OUT is fixed; move it
    mv checkpoints/p145_cart_seed "$SEED" 2>/dev/null || true
fi
if [ ! -f "$OUT/policy_best.pt" ]; then
    env FRUIT_ACTION=tcp "$LINGBOT" scripts/111_rl_finetune.py \
        --ckpt "$SEED/policy_best.pt" --rollouts "$STORE" --base "" \
        --action-horizon 4 --first-steps 4 --out "$OUT" --epochs 40 \
        --lr 5e-5 --weight-mode ones --batch-size 64 --seed 0
fi
echo "[p145] eval $(date +%H:%M)"
rm -rf logs/p145_cart2_t1
env FRUIT_ACTION=tcp FRUIT_DIRECT_START=wait FRUIT_GOAL_SOURCE=perception \
    FRUIT_POLICY_HANDOVER=0 FRUIT_POLICY_ACTION_HOLD=4 FRUIT_POLICY_TRACE=1 \
    FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 SKIP_SELFCHECK=1 scripts/run.sh \
    scripts/110_rl_rollout.py --ckpt "$OUT/policy_best.pt" --presentation direct \
    --episodes 2 --seeds 77 --execute-steps 4 --horizon 520 --out logs/p145_cart2_t1
