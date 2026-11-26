#!/usr/bin/env bash
# P282: the pad-view segmenter against the colour gate, **under the same light**.
#
#   A  colour   - no retraining, the P281 baseline for this view
#   B  learned  - the net trained on this view + this light (IoU 0.993)
#
# Cross-light counts are not comparable (the light changes the render, hence the
# branch), so both arms carry `FRUIT_LIGHT_DOME=2 FRUIT_LIGHT_WRIST=600`.
set -euo pipefail
cd "$(dirname "$0")/../.."

SPEED="${SPEED:-0.08}"
PICKS="${PICKS:-10}"
SEEDS="${SEEDS:-913 914}"
OUT="${OUT:-logs/p282}"
SEG="${SEG:-checkpoints/wrist_seg_pad.pt}"

TF=(
  FRUIT_GOAL_SOURCE=perception
  FRUIT_PRIMITIVE_ESTIMATE=1
  FRUIT_PRIMITIVE_PERCEPT=1
  FRUIT_GRASP_JUDGE=force
  FRUIT_GRASP_JUDGE_TICKS=10
  FRUIT_START_ALIGN_FROM=percept
  FRUIT_SELECT_FROM=percept
  FRUIT_WRIST_MOUNT=pad
  FRUIT_LIGHT_DOME=2.0
  FRUIT_LIGHT_WRIST=600
  FRUIT_WRIST_DIAG=1
)

run() {
  local tag="$1" seed="$2"; shift 2
  echo "=== ${tag} seed=${seed} ==="
  env "$@" SKIP_SELFCHECK=1 \
    CONTINUOUS_LOG="${OUT}/${tag}_s${seed}.log" CONTINUOUS_LOG_DIR="${OUT}" \
    scripts/290_single_arm_continuous.sh "${PICKS}" "${seed}" "${SPEED}" 2>&1 \
    | grep -E "deployment cell" | sed "s/^/${tag} /"
}

for seed in ${SEEDS}; do
  run A "${seed}" "${TF[@]}" FRUIT_WRIST=colour
  run B "${seed}" "${TF[@]}" FRUIT_WRIST=learned FRUIT_WRIST_SEG="${SEG}"
done
