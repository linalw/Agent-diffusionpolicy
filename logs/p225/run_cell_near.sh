#!/usr/bin/env bash
# P225: pure learned cell, the P184 recipe + the nearest-above-floor selector.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
BELT=${BELT:?set BELT}
SEED=${SEED:?set SEED}
EP=${EP:-8}
OUT=${OUT:?set OUT}
env FRUIT_BELT_SPEED="$BELT" \
    FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1 \
    FRUIT_CONTACT_SERVO=1 FRUIT_CONTACT_SERVO_LEAD=0.10 FRUIT_CONTACT_SERVO_LEAD_RIGHT=0.20 \
    FRUIT_PLACE_SERVO=1 FRUIT_PLACE_SERVO_VMAX=0.20 \
    FRUIT_IMAGE_FOVEA=64 FRUIT_DIRECT_START_ALIGN=family FRUIT_SKILL_LIFT_RAMP=1 \
    FRUIT_CLOSE_RAMP_DY=0.014 FRUIT_POLICY_PHASE=perception \
    FRUIT_POLICY_PHASE_PATH=checkpoints/p146_phase/phase.pt FRUIT_CLOSE_RAMP=1 \
    FRUIT_CLOSE_RAMP_TRIGGER=phase FRUIT_OBS_CMD=1 FRUIT_DIRECT_START=wait \
    FRUIT_GOAL_SOURCE=perception FRUIT_POLICY_HANDOVER=0 FRUIT_POLICY_ACTION_HOLD=4 \
    FRUIT_POLICY_TRACE=1 FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 \
    FRUIT_FINGER_MAXFORCE_DIRECT=60 \
    FRUIT_SCORE_ENDPOINT=release FRUIT_EPISODE_END=release \
    FRUIT_SMALL_HANDOVER=0 FRUIT_HANDOVER_SIDE= \
    FRUIT_POLICY_TRIGGER=off SKIP_SELFCHECK=1 \
    scripts/run.sh scripts/110_rl_rollout.py \
    --ckpt checkpoints/p177_full/policy_best.pt --presentation direct \
    --episodes "$EP" --seeds "$SEED" --horizon 2600 --out "$OUT" 2>&1
