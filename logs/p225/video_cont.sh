#!/usr/bin/env bash
# P225 video: one continuous p177 episode, N picks back to back (no scripted routes).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
OUT_DIR=${OUT_DIR:-/media/ubuntu/66A27065A2703B9D/project/Agent-diffusionpolicy/log/video/p225_p177_continuous}
BELT=${BELT:-0.12}
SEED=${SEED:-303}
PICKS=${PICKS:-6}
export FRUIT_BELT_SPEED="$BELT"
export FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1
export FRUIT_CONTACT_SERVO=1 FRUIT_CONTACT_SERVO_LEAD=0.10 FRUIT_CONTACT_SERVO_LEAD_RIGHT=0.20
export FRUIT_PLACE_SERVO=1 FRUIT_PLACE_SERVO_VMAX=0.20
export FRUIT_IMAGE_FOVEA=64 FRUIT_DIRECT_START_ALIGN=family FRUIT_SKILL_LIFT_RAMP=1
export FRUIT_CLOSE_RAMP_DY=0.014 FRUIT_CLOSE_RAMP_DY_LO="${DY_LO:--0.02}" FRUIT_POLICY_PHASE=perception
export FRUIT_POLICY_PHASE_PATH=checkpoints/p146_phase/phase.pt FRUIT_CLOSE_RAMP=1
export FRUIT_CLOSE_RAMP_TRIGGER=phase FRUIT_OBS_CMD=1 FRUIT_DIRECT_START=wait
export FRUIT_GOAL_SOURCE=perception FRUIT_POLICY_HANDOVER=0 FRUIT_POLICY_ACTION_HOLD=4
export FRUIT_POLICY_TRACE=1 FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1
export FRUIT_FINGER_MAXFORCE_DIRECT=60
# P225 4g-4l: the small-fruit perception floor (<=4 cm), the carry force
# scoped >4 cm, and the two-sided close gate are the measured recipe.
export FRUIT_PERCEPTION_MIN_PX_SMALL=12 FRUIT_PERCEPTION_SMALL_DIA=0.040
export FRUIT_CARRY_FORCE="${CARRY_FORCE:-45}" FRUIT_CARRY_FORCE_DIAG=1 \
       FRUIT_CARRY_FORCE_SMALL_DIA=0.040
export FRUIT_SCORE_ENDPOINT=release FRUIT_DIRECT_FEED=1
export FRUIT_SMALL_HANDOVER=0 FRUIT_HANDOVER_SIDE=
export FRUIT_POLICY_TRIGGER=off SKIP_SELFCHECK=1
rm -rf "$OUT_DIR"
scripts/run.sh scripts/121_policy_video.py --ckpt checkpoints/p177_full/policy_best.pt \
  --episodes 1 --continuous "$PICKS" --seed "$SEED" --execute-steps 4 --horizon 2600 \
  --out-dir "$OUT_DIR"
