#!/bin/bash
# P204: a continuous-operation demo - ONE episode, N picks back to back (no reset
# between picks: the arm goes pick -> place -> next pick). FRUIT_DIRECT_CONTINUOUS
# implies the feeder (P56). The release boundary advances the pick rather than
# ending the episode (P203's detector feeds _finalize, whose `cont` path calls
# _begin_next_pick).
set -u
cd "$(dirname "$0")/.."
export FRUIT_IMAGE_FOVEA=64 FRUIT_DIRECT_START_ALIGN=family FRUIT_SKILL_LIFT_RAMP=1
export FRUIT_CLOSE_RAMP_DY=0.014 FRUIT_POLICY_PHASE=perception
export FRUIT_POLICY_PHASE_PATH=checkpoints/p146_phase/phase.pt FRUIT_CLOSE_RAMP=1
export FRUIT_CLOSE_RAMP_TRIGGER=phase FRUIT_OBS_CMD=1 FRUIT_DIRECT_START=wait
export FRUIT_GOAL_SOURCE=perception FRUIT_POLICY_HANDOVER=0 FRUIT_POLICY_ACTION_HOLD=4
export FRUIT_POLICY_TRACE=1 FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1
export FRUIT_CONTACT_SERVO=1 FRUIT_CONTACT_SERVO_LEAD=0.10
export FRUIT_CONTACT_SERVO_LEAD_RIGHT=0.20 FRUIT_PLACE_SERVO=1
export FRUIT_PLACE_SERVO_VMAX=0.20 FRUIT_SCORE_ENDPOINT=release
export FRUIT_FINGER_MAXFORCE_DIRECT=60 FRUIT_POLICY_JOINT_CLAMP=1 FRUIT_POLICY_TARGET_RATE=5.45 FRUIT_DIRECT_FEED=1
export SKIP_SELFCHECK=1
rm -rf logs/video_p207
scripts/run.sh scripts/121_policy_video.py --ckpt checkpoints/p177_full/policy_best.pt \
  --episodes 6 --seed 303 --execute-steps 4 --horizon 2600 \
  --out-dir logs/video_p207 > logs/p207_video.log 2>&1
echo "done video207"
