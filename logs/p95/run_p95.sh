#!/usr/bin/env bash
# P95 battery: the selected fruit's per-tick trace (one claim per run).
#
#   bash logs/p95/run_p95.sh            # both cells, sequential
#   bash logs/p95/run_p95.sh F6         # just the fruit-only cell
#
# METHOD: logs/p95/METHOD.md (md5 in logs/p95/METHOD.md5), pinned before any run.
#
# Cells (20 attempts, the shipped two-line default, one run each):
#   F6  seed 6, FRUIT_FRUIT_TRACE=1                 fruit reads only -> branch check
#   A6  seed 6, FRUIT_FRUIT_TRACE=1 + ..._ARM=1     DECLARED branch-moving: geometry
#
# The instrumentation is P94's `T6` cell verbatim (`FRUIT_MOTION_REPORT
# FRUIT_CYCLE_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`) so the replay target is
# the recorded post-P94 run of the same seed. Nothing here writes src/, configs/,
# datasets/ or a checkpoint beyond the phase's own default-off instrument.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p95

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)

if [ ! -s logs/p95/header.txt ]; then
    {
        echo "# P95 header ($(date '+%F %T'))"
        echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
        md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
            src/fruit_sorting/bimanual.py src/fruit_sorting/fruits.py \
            configs/motion_reference.json configs/motion_reference_single.json \
            configs/motion_reference_twoline.json \
            scripts/20_pick_place.py scripts/run.sh scripts/selfcheck.sh \
            scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
            scripts/154_claim_run.sh logs/p80/one_run.sh logs/p80/stamp.py \
            logs/p95/METHOD.md logs/p95/run_p95.sh
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=6 [FRUIT_FRUIT_TRACE[_ARM]]"
        echo "# the change: tasks._fruit_trace_tick/_fruit_trace_flush + the"
        echo "#   _step_sim hook (default off; fruit reads only unless _ARM=1)"
    } | tee logs/p95/header.txt
fi

fail=0
note() { echo "[p95] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p95/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=2400 scripts/154_claim_run.sh "logs/p95/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p95/${tag}.stamps"
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $tag"
    if [ "$rc" -ne 0 ] || [ ! -s "$log" ]; then
        note "FAIL $tag (rc=$rc)"; fail=$((fail + 1))
    fi
}

sel=("$@")
run() {  # run <tag> <env...>
    local tag=$1; shift
    if [ "${#sel[@]}" -eq 0 ] || [[ " ${sel[*]} " == *" $tag "* ]]; then
        claim_run "$tag" "$@"
    fi
}

run F6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6 FRUIT_FRUIT_TRACE=2500 \
       FRUIT_FRUIT_TRACE_DIR=logs/p95/tr6
run A6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6 FRUIT_FRUIT_TRACE=2500 \
       FRUIT_FRUIT_TRACE_DIR=logs/p95/tr6 FRUIT_FRUIT_TRACE_ARM=1
run A5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5 FRUIT_FRUIT_TRACE=2500 \
       FRUIT_FRUIT_TRACE_DIR=logs/p95/tr5 FRUIT_FRUIT_TRACE_ARM=1

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
