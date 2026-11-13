#!/usr/bin/env bash
# P144: was the 0/12 the recipe (no anchor) or the data? Same 45 episodes, but with
# `demos_v11` as the anchor at weight 1.0 - the recipe `moe_v13s` was built with.
#   arm up    : shipped camera + 45 episodes + anchor   -> eval on the shipped camera
#   arm down  : down_x_160   + 45 episodes + anchor     -> eval on down_x_160
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
LINGBOT=${LINGBOT:-/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python}
run_arm() {
    local name=$1 store=$2 out=$3 camera=$4 log=$5
    if [ ! -f "$out/policy_best.pt" ]; then
        echo "[p144] train $name ($(date +%H:%M:%S))"
        env "$LINGBOT" scripts/111_rl_finetune.py \
            --ckpt checkpoints/moe_v13s/policy_best.pt --rollouts "$store" \
            --base datasets/demos_v11 --out "$out" --epochs 8 --lr 5e-5 \
            --weight-mode ones --base-weight 1.0 --batch-size 32 --seed 0
    fi
    echo "[p144] eval $name ($(date +%H:%M:%S))"
    env ${camera:+FRUIT_HEAD_CAMERA=$camera} FRUIT_CAMERA_RES=240,424 \
        FRUIT_HANDOVER_DIAG=1 SKIP_SELFCHECK=1 scripts/run.sh \
        scripts/110_rl_rollout.py --ckpt "$out/policy_best.pt" --presentation direct \
        --episodes 4 --seeds 77,101,202 --out "$log"
}
run_arm up   datasets/p144_up   checkpoints/p144_up_anchor   ""           logs/p144_eval_up_anchor
run_arm down datasets/p144_down checkpoints/p144_down_anchor down_x_160   logs/p144_eval_down_anchor
