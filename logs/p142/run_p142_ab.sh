#!/usr/bin/env bash
# P142 - the direct-lane A/B the phase names: the moving catch the trigger assumes.
#
# One arm, five seeds, five episodes each (the WS-4.2 shape reduced to a smoke
# with a denominator). Every episode is `success` on the **declared** endpoint
# (`FRUIT_SCORE_ENDPOINT=release`), so the count is comparable only within it.
#
#   ARM=dynamic  -> FRUIT_DYNAMIC_PICK=1  (the catch the intercept implies)
#   ARM=indexed  -> FRUIT_DYNAMIC_PICK=0  (the shipped direct primitive)
#
# Wall time is ~4-5 min per episode on this box (the camera render dominates), so
# one arm of 25 episodes is ~2 h. Run the two arms in separate blocks; the tree
# must not move between them.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
ARM=${ARM:-dynamic}
SEEDS=${SEEDS:-"77 101 202 303 404"}
EPISODES=${EPISODES:-5}
CKPT=${CKPT:-checkpoints/p141_wave/policy_best.pt}
OUT=${OUT:-logs/p142/ab}
mkdir -p "$OUT"
if [ "$ARM" = "dynamic" ]; then DYN=1; else DYN=0; fi
for seed in $SEEDS; do
    log="$OUT/${ARM}_s${seed}.log"
    if [ -s "$log" ]; then echo "[p142] $log exists - keeping"; continue; fi
    echo "[p142] $ARM seed $seed ($(date +%H:%M:%S))"
    env FRUIT_CAMERA_RES=240,424 FRUIT_OBS_SPEED=1 FRUIT_OBS_GOAL_AUX=1 \
        FRUIT_POLICY_TRIGGER=arrival FRUIT_DYNAMIC_PICK="$DYN" \
        FRUIT_SCORE_ENDPOINT=release FRUIT_BELT_WAVE_AMP=0.04 \
        FRUIT_BELT_WAVE_HZ=0.5 SKIP_SELFCHECK=1 \
        scripts/run.sh scripts/110_rl_rollout.py \
        --ckpt "$CKPT" --presentation direct \
        --episodes "$EPISODES" --seeds "$seed" --out "$OUT/rollout_${ARM}_s${seed}" \
        > "$log" 2>&1
    grep -aE "episode [0-9]+: .*success=|rollout success" "$log" | tail -2
done
echo "== $ARM: $(grep -ah 'rollout success' "$OUT"/${ARM}_s*.log | sed 's/.*rollout success //')"
