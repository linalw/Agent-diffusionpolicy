#!/usr/bin/env bash
# P100 battery: the park return's fixed clock (one claim per run).
#
#   bash logs/p100/run_p100.sh              # all cells, sequential
#   bash logs/p100/run_p100.sh C5 T5        # a subset
#
# PREREG: logs/p100/PREREG.md (md5 in logs/p100/PREREG.md5), pinned before any
# of these cells. The measured arm is the explicit pair
# `FRUIT_BIARM_PARK_BLEND=60 FRUIT_BIARM_PARK_SETTLE=75` (135 of the shipped
# 210 fixed ticks, -75 = -0.625 s); the controls are the unset tree.
#
# Cells (20 attempts, the shipped two-line default, one run each, interleaved
# control -> treatment per seed):
#   C5    seed 5     unset                          control  (== logs/p99/C5.log)
#   T5    seed 5     blend 60 / settle 75            the cell
#   C6    seed 6     unset                          control  (== logs/p99/C6.log)
#   T6    seed 6     blend 60 / settle 75
#   C101  seed 101   unset                          control  (fresh)
#   T101  seed 101   blend 60 / settle 75
#   C202  seed 202   unset                          control  (fresh)
#   T202  seed 202   blend 60 / settle 75
#   X5C   seed 5     unset          + clearance trace   report only, no rate
#   X5T   seed 5     blend 60 / settle 75 + trace
#
# The instrumentation is P99's verbatim (`FRUIT_MOTION_REPORT FRUIT_CYCLE_REPORT
# FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE FRUIT_BIARM_PARK_TRACE`) plus
# `FRUIT_READY_DIAG=1` (P9-A's pure-reporting `[ready]` row, which is where the
# block's own decomposition and the `q_step` posture bound are read). The two
# clearance cells add `FRUIT_BIARM_TRACE=1`, the invasive link read - quotes a
# clearance census and nothing else.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p100

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1
            FRUIT_BIARM_PARK_TRACE=1 FRUIT_READY_DIAG=1)
ENV_CELL=(FRUIT_BIARM_PARK_BLEND=60 FRUIT_BIARM_PARK_SETTLE=75)
ENV_TRACE=(FRUIT_BIARM_TRACE=1)

if [ ! -s logs/p100/header.txt ]; then
    {
        echo "# P100 header ($(date '+%F %T'))"
        echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
        md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
            src/fruit_sorting/bimanual.py src/fruit_sorting/fruits.py \
            src/fruit_sorting/scene.py src/fruit_sorting/assets.py \
            src/fruit_sorting/control.py src/fruit_sorting/conveyor.py \
            configs/motion_reference.json configs/motion_reference_single.json \
            configs/motion_reference_twoline.json \
            scripts/20_pick_place.py scripts/run.sh scripts/selfcheck.sh \
            scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
            scripts/154_claim_run.sh logs/p80/one_run.sh logs/p80/stamp.py \
            logs/p100/PREREG.md
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6|101|202> [${ENV_CELL[*]}]"
        echo "# the change: tasks.park_profile_resolution - the two-line park's"
        echo "#   _blend_to ramp (FRUIT_BIARM_PARK_BLEND) and settle"
        echo "#   (FRUIT_BIARM_PARK_SETTLE), shipped 90/120, cell 60/75"
    } | tee logs/p100/header.txt
fi

fail=0
note() { echo "[p100] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p100/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "logs/p100/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p100/${tag}.stamps"
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

trace_run() {  # trace_run <tag> <env...>
    local tag=$1; shift
    rm -f "logs/p100/${tag}.jsonl"
    run "$tag" "$@" "${ENV_TRACE[@]}" \
        "FRUIT_BIARM_TRACE_FILE=logs/p100/${tag}.jsonl"
}

run C5   "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run T5   "${ENV_COMMON[@]}" "${ENV_CELL[@]}" ATTEMPTS=20 SEED=5
run C6   "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6
run T6   "${ENV_COMMON[@]}" "${ENV_CELL[@]}" ATTEMPTS=20 SEED=6
run C101 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=101
run T101 "${ENV_COMMON[@]}" "${ENV_CELL[@]}" ATTEMPTS=20 SEED=101
run C202 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=202
run T202 "${ENV_COMMON[@]}" "${ENV_CELL[@]}" ATTEMPTS=20 SEED=202
trace_run X5C "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
trace_run X5T "${ENV_COMMON[@]}" "${ENV_CELL[@]}" ATTEMPTS=20 SEED=5

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
