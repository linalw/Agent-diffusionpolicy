#!/usr/bin/env bash
# P283: one-species cells at both ends of the pool, on the best truth-free config.
#   pear   - the census's worst species (3/25 in the mixed pool)
#   lychee - the smallest (2.8-3.8 cm), which the mixed pool almost never presents
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT="${OUT:-logs/p283}"
TF=(
  FRUIT_GOAL_SOURCE=perception FRUIT_PRIMITIVE_ESTIMATE=1 FRUIT_PRIMITIVE_PERCEPT=1
  FRUIT_GRASP_JUDGE=force FRUIT_GRASP_JUDGE_TICKS=10
  FRUIT_START_ALIGN_FROM=percept FRUIT_SELECT_FROM=percept
  FRUIT_WRIST_MOUNT=pad FRUIT_WRIST=colour
  FRUIT_LIGHT_DOME=2.0 FRUIT_LIGHT_WRIST=600
  FRUIT_TRUTH_AUDIT=1
)
run() {
  local sp="$1" seed="$2"; shift 2
  echo "=== ${sp} seed=${seed} ==="
  env "$@" SKIP_SELFCHECK=1 FRUIT_SUPPLY_SPECIES="${sp}" \
    CONTINUOUS_LOG="${OUT}/${sp}_s${seed}.log" CONTINUOUS_LOG_DIR="${OUT}" \
    scripts/290_single_arm_continuous.sh 10 "${seed}" 0.08 2>&1 \
    | grep -E "deployment cell" | sed "s/^/${sp} /"
}
for sp in pear lychee; do run "${sp}" 913 "${TF[@]}"; done
