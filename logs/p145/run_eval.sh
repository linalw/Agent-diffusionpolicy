#!/usr/bin/env bash
# P145: one honest-interface evaluation cell (12 episodes) with ablations.
#   CKPT=checkpoints/... OUT=logs/... EXEC=4 [EXTRA="FRUIT_TACTILE_ZERO=1"]
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
CKPT=${CKPT:?set CKPT}
OUT=${OUT:?set OUT}
EXEC=${EXEC:-4}
EXTRA=${EXTRA:-}
rm -rf "$OUT"
env $EXTRA FRUIT_GOAL_SOURCE=perception FRUIT_PERCEPTION_DIAG=1 \
    FRUIT_POLICY_HANDOVER=0 FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 \
    SKIP_SELFCHECK=1 scripts/run.sh scripts/110_rl_rollout.py \
    --ckpt "$CKPT" --presentation direct --episodes 4 --seeds 77,101,202 \
    --execute-steps "$EXEC" --out "$OUT"
