#!/usr/bin/env bash
# P275b: the tick-matched judge A/B, then the truth-free bundle.
#
# Group 1 (0.12, seed 909, 20 picks) - attribute the judge's count:
#   Cm  truth judge + SETTLE=10   (the matched tick budget)
#   J   sensor judge, TICKS=10
# Group 2 (0.08, seeds 913/914, 10 picks) - what truth-free costs:
#   C   shipped, census armed
#   TFs truth-free bundle, census armed
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT="${OUT:-logs/p275b}"
mkdir -p "${OUT}"

run() {  # run <tag> <seed> <picks> <speed> [env...]
  local tag="$1" seed="$2" picks="$3" speed="$4"; shift 4
  echo "=== ${tag} seed=${seed} picks=${picks} speed=${speed} ==="
  env "$@" \
    SKIP_SELFCHECK=1 \
    CONTINUOUS_LOG="${OUT}/${tag}_s${seed}.log" \
    CONTINUOUS_LOG_DIR="${OUT}" \
    scripts/290_single_arm_continuous.sh "${picks}" "${seed}" "${speed}" 2>&1 \
    | grep -E "deployment cell" | sed "s/^/${tag} /"
}

TF_BUNDLE=(
  FRUIT_GOAL_SOURCE=perception
  FRUIT_PRIMITIVE_ESTIMATE=1
  FRUIT_PRIMITIVE_PERCEPT=1
  FRUIT_GRASP_JUDGE=force
  FRUIT_GRASP_JUDGE_TICKS=10
  FRUIT_START_ALIGN_FROM=percept
)

# --- group 1: is the judge's count its own, or the settle's? --------------
run Cm 909 20 0.12 FRUIT_TRUTH_AUDIT=1 FRUIT_GRASP_JUDGE_SETTLE=10
run J  909 20 0.12 FRUIT_TRUTH_AUDIT=1 FRUIT_GRASP_JUDGE=force FRUIT_GRASP_JUDGE_TICKS=10

# --- group 2: the truth-free bundle, with its debt table -----------------
for seed in 913 914; do
  run C   "${seed}" 10 0.08 FRUIT_TRUTH_AUDIT=1
  run TFs "${seed}" 10 0.08 FRUIT_TRUTH_AUDIT=1 "${TF_BUNDLE[@]}"
done

python3 logs/p275/p275_report.py "${OUT}"/*.log
