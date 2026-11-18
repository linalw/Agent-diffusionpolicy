#!/bin/bash
# P200: the selector's floor, control vs 3.0 s, in one batch.
set -u
cd "$(dirname "$0")/.."
COMMON="FRUIT_IMAGE_FOVEA=64 FRUIT_DIRECT_START_ALIGN=family FRUIT_SKILL_LIFT_RAMP=1
 FRUIT_CLOSE_RAMP_DY=0.014 FRUIT_POLICY_PHASE=perception
 FRUIT_POLICY_PHASE_PATH=checkpoints/p146_phase/phase.pt FRUIT_CLOSE_RAMP=1
 FRUIT_CLOSE_RAMP_TRIGGER=phase FRUIT_OBS_CMD=1 FRUIT_DIRECT_START=wait
 FRUIT_GOAL_SOURCE=perception FRUIT_POLICY_HANDOVER=0 FRUIT_POLICY_ACTION_HOLD=4
 FRUIT_POLICY_TRACE=1 FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1
 FRUIT_CONTACT_SERVO=1 FRUIT_CONTACT_SERVO_LEAD=0.10
 FRUIT_CONTACT_SERVO_LEAD_RIGHT=0.20 FRUIT_PLACE_SERVO=1
 FRUIT_PLACE_SERVO_VMAX=0.20 FRUIT_SCORE_ENDPOINT=release
 FRUIT_FINGER_MAXFORCE_DIRECT=60 FRUIT_FIRE_DIAG=1 SKIP_SELFCHECK=1"
for spec in "c808 1.5 808" "t808 3.0 808" "c303 1.5 303" "t303 3.0 303"; do
  set -- $spec
  rm -rf "logs/p200_$1"
  timeout 2400 env $COMMON FRUIT_DYNAMIC_SELECT_S=$2 scripts/run.sh scripts/110_rl_rollout.py \
    --ckpt checkpoints/p177_full/policy_best.pt --presentation direct \
    --episodes 6 --seeds $3 --execute-steps 4 --horizon 2600 \
    --out "logs/p200_$1" > "logs/p200_$1.log" 2>&1
  echo "done $1"
done
