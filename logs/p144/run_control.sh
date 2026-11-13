#!/usr/bin/env bash
# P144 control: the SAME recipe as the down_x_160 arm, on the SHIPPED camera.
#   collect 45 single-arm episodes through the top-down pose
#   fine-tune from moe_v13s with --base "" (no old-view anchor)
#   evaluate 12 episodes on the same camera
# Only the camera differs from the treatment arm, so this isolates the view from
# the store's distribution and the missing anchor.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
LINGBOT=${LINGBOT:-/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python}
STORE=${STORE:-datasets/p144_up}
OUT=${OUT:-checkpoints/p144_up}
EPISODES=${EPISODES:-45}
if [ ! -f "$STORE/index.json" ] && [ ! -d "$STORE" ]; then
    echo "[p144] collect $EPISODES through the shipped camera ($(date +%H:%M:%S))"
    env FRUIT_BIARM=0 FRUIT_CAMERA_RES=240,424 FRUIT_EPISODES="$EPISODES" \
        FRUIT_DEMO_DIR="$STORE" SKIP_SELFCHECK=1 \
        scripts/run.sh scripts/40_collect_demos.py
fi
S=$(dirname "$(find "$STORE" -maxdepth 2 -name index.json | head -1)")
if [ ! -f "$OUT/policy_best.pt" ]; then
    echo "[p144] fine-tune $S -> $OUT ($(date +%H:%M:%S))"
    env "$LINGBOT" scripts/111_rl_finetune.py \
        --ckpt checkpoints/moe_v13s/policy_best.pt --rollouts "$S" --base "" \
        --out "$OUT" --epochs 8 --lr 5e-5 --weight-mode ones --batch-size 32 --seed 0
fi
echo "[p144] eval $OUT ($(date +%H:%M:%S))"
env FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 SKIP_SELFCHECK=1 scripts/run.sh \
    scripts/110_rl_rollout.py --ckpt "$OUT/policy_best.pt" --presentation direct \
    --episodes 4 --seeds 77,101,202 --out logs/p144_eval_up
