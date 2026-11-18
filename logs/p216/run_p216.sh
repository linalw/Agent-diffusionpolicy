#!/bin/bash
# P216: the phase close's two-sided along window on the lychee-only pool.
# Usage: run_p216.sh <seed> <episodes>
set -u
cd "$(dirname "$0")/../.."
SEED="${1:-808}"; EP="${2:-6}"
export FRUIT_IMAGE_FOVEA=64 FRUIT_DIRECT_START_ALIGN=family FRUIT_SKILL_LIFT_RAMP=1
export FRUIT_CLOSE_RAMP_DY=0.014 FRUIT_CLOSE_RAMP_DY_LO=-0.02
export FRUIT_POLICY_PHASE=perception FRUIT_POLICY_PHASE_PATH=checkpoints/p146_phase/phase.pt
export FRUIT_CLOSE_RAMP=1 FRUIT_CLOSE_RAMP_TRIGGER=phase FRUIT_OBS_CMD=1 FRUIT_DIRECT_START=wait
export FRUIT_GOAL_SOURCE=perception FRUIT_POLICY_HANDOVER=0 FRUIT_POLICY_ACTION_HOLD=4
export FRUIT_POLICY_TRACE=1 FRUIT_CAMERA_RES=240,424 FRUIT_HANDOVER_DIAG=1 FRUIT_FIRE_DIAG=1
export FRUIT_PERCEPTION_DIAG=1
export FRUIT_CONTACT_SERVO=1 FRUIT_CONTACT_SERVO_LEAD=0.10
export FRUIT_CONTACT_SERVO_LEAD_RIGHT=0.20 FRUIT_PLACE_SERVO=1
export FRUIT_PLACE_SERVO_VMAX=0.20 FRUIT_SCORE_ENDPOINT=release
export FRUIT_FINGER_MAXFORCE_DIRECT=60 FRUIT_POLICY_JOINT_CLAMP=1
export FRUIT_POLICY_TARGET_RATE=5.45 FRUIT_EMIT_DIAG=1
export FRUIT_SUPPLY_SPECIES=lychee
export SKIP_SELFCHECK=1
OUT="logs/p216/LO_s${SEED}.log"
scripts/run.sh scripts/110_rl_rollout.py --ckpt checkpoints/p177_full/policy_best.pt \
  --presentation direct --episodes "$EP" --seeds "$SEED" \
  --out "datasets/rl_rollouts/p216_LO_s${SEED}" \
  --execute-steps 4 --ddim 16 --horizon 2600 > "$OUT" 2>&1
echo "done LO $SEED $EP"
