#!/usr/bin/env bash
# P275: how much of the shipped cell is simulator ground truth, and what a
# truth-free cell costs.
#
# Three arms, one recipe, one seed per cell (P93: a count is a branch draw):
#
#   C   shipped                 - goal/trigger/primitive/grasp all read the simulator
#   J   sensor grasp judge      - only the grasp decision moves to tactile force + pad span
#   TFs truth-free bundle       - goal + trigger + pre-grasp primitive reads + grasp
#                                 judgement + start-pose x all from measurement
#
# `FRUIT_TRUTH_AUDIT=1` counts every remaining `spawner.position/velocity` read by
# call site, so the debt is listed instead of argued. Off in the shipped path.
set -euo pipefail
cd "$(dirname "$0")/../.."

SPEED="${SPEED:-0.08}"
PICKS="${PICKS:-10}"
SEEDS="${SEEDS:-913 914}"
OUT="${OUT:-logs/p275b}"

run() {  # run <tag> <seed> [extra env...]
  local tag="$1" seed="$2"; shift 2
  echo "=== ${tag} seed=${seed} speed=${SPEED} ==="
  env "$@" \
    SKIP_SELFCHECK=1 \
    CONTINUOUS_LOG="${OUT}/${tag}_s${seed}.log" \
    CONTINUOUS_LOG_DIR="${OUT}" \
    scripts/290_single_arm_continuous.sh "${PICKS}" "${seed}" "${SPEED}" 2>&1 \
    | grep -E "deployment cell" | sed "s/^/${tag} /"
}

mkdir -p "${OUT}"
for seed in ${SEEDS}; do
  run C "${seed}"  FRUIT_TRUTH_AUDIT=1
  run J "${seed}"  FRUIT_TRUTH_AUDIT=1 FRUIT_GRASP_JUDGE=force \
                   FRUIT_GRASP_JUDGE_TICKS=10
  run TFs "${seed}" FRUIT_TRUTH_AUDIT=1 \
                    FRUIT_GOAL_SOURCE=perception \
                    FRUIT_PRIMITIVE_ESTIMATE=1 \
                    FRUIT_PRIMITIVE_PERCEPT=1 \
                    FRUIT_GRASP_JUDGE=force FRUIT_GRASP_JUDGE_TICKS=10 \
                    FRUIT_START_ALIGN_FROM=percept
done

python3 logs/p275/p275_report.py "${OUT}"/*.log
