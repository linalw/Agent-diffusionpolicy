#!/usr/bin/env bash
# P276: the contact phase on the estimate. Same batch, same instrumentation.
#
#   C    shipped            - goal/trigger/select/grasp all truth, contact truth
#   TFs  truth-free bundle  - decision layer measured AND the 18 pre-grasp
#                             contact reads on the estimate (P276 routing)
#
# 0.08 m/s, 10 continuous picks, seeds 913/914, `FRUIT_TRUTH_AUDIT=1` on BOTH arms
# (P83's G2 rule: the instrumentation must be identical or the A/B is the
# instrumentation).
set -euo pipefail
cd "$(dirname "$0")/../.."

SPEED="${SPEED:-0.08}"
PICKS="${PICKS:-10}"
SEEDS="${SEEDS:-913 914}"
OUT="${OUT:-logs/p276b}"
mkdir -p "${OUT}"

run() {  # run <tag> <seed> [env...]
  local tag="$1" seed="$2"; shift 2
  echo "=== ${tag} seed=${seed} speed=${SPEED} picks=${PICKS} ==="
  env "$@" \
    SKIP_SELFCHECK=1 \
    CONTINUOUS_LOG="${OUT}/${tag}_s${seed}.log" \
    CONTINUOUS_LOG_DIR="${OUT}" \
    scripts/290_single_arm_continuous.sh "${PICKS}" "${seed}" "${SPEED}" 2>&1 \
    | grep -E "deployment cell" | sed "s/^/${tag} /"
}

TF_BUNDLE=(
  FRUIT_GOAL_SOURCE=perception
  FRUIT_PRIMITIVE_ESTIMATE=1
  FRUIT_PRIMITIVE_PERCEPT=1
  FRUIT_GRASP_JUDGE=force
  FRUIT_GRASP_JUDGE_TICKS=10
  FRUIT_START_ALIGN_FROM=percept
  FRUIT_SELECT_FROM=percept
)

for seed in ${SEEDS}; do
  run C   "${seed}" FRUIT_TRUTH_AUDIT=1
  run TFs "${seed}" FRUIT_TRUTH_AUDIT=1 "${TF_BUNDLE[@]}"
done

python3 logs/p275/p275_report.py "${OUT}"/*.log
