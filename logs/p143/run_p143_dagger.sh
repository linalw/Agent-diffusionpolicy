#!/usr/bin/env bash
# P143 / A: the DAgger round the record's four nulls never had a number for.
#
# 1. collect  - policy drives, the scripted expert's command is the *label*
#               (`--dagger`: expert runs env-side, the recorded `action` is the
#               label, the policy's own action is kept as `policy_action`).
# 2. fine-tune- behaviour cloning on those labels + demos_v11 as the anchor.
# 3. evaluate - the same direct loop with the handover gate, reading `gap_min`
#               (128-155 mm before; the gate needs 60).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
LINGBOT=${LINGBOT:-/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python}
INIT=${INIT:-checkpoints/moe_v13s/policy_best.pt}
STORE=${STORE:-datasets/p143_dagger/direct_none_seed77}
OUT=${OUT:-checkpoints/p143_dagger}
EPISODES=${EPISODES:-12}
SEEDS=${SEEDS:-77,101}

if [ "${1:-all}" = "collect" ] || [ "${1:-all}" = "all" ]; then
    if [ ! -f "$STORE/index.json" ]; then
        echo "[p143] collect $EPISODES x seeds $SEEDS -> $STORE ($(date +%H:%M:%S))"
        env FRUIT_CAMERA_RES=240,424 SKIP_SELFCHECK=1 scripts/run.sh \
            scripts/110_rl_rollout.py --ckpt "$INIT" --presentation direct \
            --dagger --record --episodes "$EPISODES" --seeds "$SEEDS" --out "$STORE"
    fi
fi

if [ "${1:-all}" = "train" ] || [ "${1:-all}" = "all" ]; then
    if [ ! -f "$OUT/policy_best.pt" ]; then
        echo "[p143] fine-tune $INIT + $STORE + demos_v11 -> $OUT ($(date +%H:%M:%S))"
        env FRUIT_CKPT="$INIT" "$LINGBOT" scripts/111_rl_finetune.py \
            --ckpt "$INIT" --rollouts "$STORE" --base datasets/demos_v11 \
            --out "$OUT" --epochs 6 --lr 5e-5 --weight-mode ones \
            --base-weight 1.0 --batch-size 32 --seed 0 2>&1 | tail -20
    fi
fi

if [ "${1:-all}" = "eval" ] || [ "${1:-all}" = "all" ]; then
    echo "[p143] eval $OUT on the direct loop, handover gate on ($(date +%H:%M:%S))"
    env FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 SKIP_SELFCHECK=1 scripts/run.sh \
        scripts/110_rl_rollout.py --ckpt "$OUT/policy_best.pt" --presentation direct \
        --episodes 6 --seeds 77,101 --out logs/p143/eval_dagger 2>&1 \
        | grep -aE "episode [0-9]+: .*success=|rollout success|gap_min"
fi
