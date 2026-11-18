#!/bin/bash
# P215: size-dependent direct clamp on a lychee-only supply.
# Usage: run_p215.sh <small_cap_N> <seed> <episodes>
set -u
cd "$(dirname "$0")/../.."
SMALL="${1:-20}"; SEED="${2:-808}"; EP="${3:-6}"
export FRUIT_IMAGE_FOVEA=64 FRUIT_DIRECT_START_ALIGN=family FRUIT_SKILL_LIFT_RAMP=1
export FRUIT_CLOSE_RAMP_DY=0.014 FRUIT_POLICY_PHASE=perception
export FRUIT_POLICY_PHASE_PATH=checkpoints/p146_phase/phase.pt FRUIT_CLOSE_RAMP=1
export FRUIT_CLOSE_RAMP_TRIGGER=phase FRUIT_OBS_CMD=1 FRUIT_DIRECT_START=wait
export FRUIT_GOAL_SOURCE=perception FRUIT_POLICY_HANDOVER=0 FRUIT_POLICY_ACTION_HOLD=4
export FRUIT_POLICY_TRACE=1 FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 FRUIT_FIRE_DIAG=1
export FRUIT_PERCEPTION_DIAG=1
export FRUIT_CONTACT_SERVO=1 FRUIT_CONTACT_SERVO_LEAD=0.10
export FRUIT_CONTACT_SERVO_LEAD_RIGHT=0.20 FRUIT_PLACE_SERVO=1
export FRUIT_PLACE_SERVO_VMAX=0.20 FRUIT_SCORE_ENDPOINT=release
export FRUIT_FINGER_MAXFORCE_DIRECT=60
export FRUIT_FINGER_MAXFORCE_DIRECT_SMALL="$SMALL"
export FRUIT_FINGER_MAXFORCE_DIRECT_SMALL_DIA=0.040
export FRUIT_POLICY_JOINT_CLAMP=1 FRUIT_POLICY_TARGET_RATE=5.45 FRUIT_EMIT_DIAG=1
export FRUIT_SUPPLY_SPECIES=lychee
export SKIP_SELFCHECK=1
TAG="${SMALL}N"
OUT="logs/p215/SM${TAG}_s${SEED}.log"
scripts/run.sh scripts/110_rl_rollout.py --ckpt checkpoints/p177_full/policy_best.pt \
  --presentation direct --episodes "$EP" --seeds "$SEED" \
  --out "datasets/rl_rollouts/p215_SM${TAG}_s${SEED}" \
  --execute-steps 4 --ddim 16 --horizon 2600 > "$OUT" 2>&1
echo "done SM${SMALL} $SEED $EP"
