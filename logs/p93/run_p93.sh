#!/usr/bin/env bash
# P93 battery: the two diagnostics, then the fresh seeds, one claim per run.
#
#   bash logs/p93/run_p93.sh                 # all six cells, sequential
#   bash logs/p93/run_p93.sh D6C D6T         # the diagnostics first
#   bash logs/p93/run_p93.sh C101 T101       # one seed pair
#
# PREREG: logs/p93/PREREG.md (md5 in logs/p93/PREREG.md5), pinned before any run.
#
# Cells:
#   D6C  seed 6, unset        + FRUIT_DYNAMIC_TRACE=1 FRUIT_OPENARM_TRACE=6   mechanism, control
#   D6T  seed 6, X_MAX=0.33   + FRUIT_DYNAMIC_TRACE=1 FRUIT_OPENARM_TRACE=6   mechanism, treatment
#   C101 seed 101, unset      the fresh-seed control (its own cell; no record exists)
#   T101 seed 101, X_MAX=0.33 the treatment
#   C202 seed 202, unset      the second fresh seed
#   T202 seed 202, X_MAX=0.33 the treatment
#
# The four seed cells carry P92's instrumentation verbatim so
# `logs/p92/census.py` reads them unchanged. Wall via logs/p80/stamp.py, one
# claim via scripts/154_claim_run.sh. Nothing here writes src/, configs/,
# datasets/ or a checkpoint; the only difference between a C and a T cell is the
# supply env, which the `[supply] ... lateral x=` row prints.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p93

ENV_SEED=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
          FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)
ENV_DIAG=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1
          FRUIT_DYNAMIC_TRACE=1 FRUIT_OPENARM_TRACE=6)

if [ ! -s logs/p93/header.txt ]; then
    {
        echo "# P93 header ($(date '+%F %T'))"
        echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
        md5sum src/fruit_sorting/tasks.py src/fruit_sorting/bimanual.py \
            src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
            src/fruit_sorting/control.py src/fruit_sorting/conveyor.py \
            src/fruit_sorting/assets.py src/fruit_sorting/rl_env.py \
            configs/motion_reference.json configs/motion_reference_single.json \
            configs/motion_reference_twoline.json \
            scripts/20_pick_place.py scripts/accept.sh \
            scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
            scripts/selfcheck.sh scripts/154_claim_run.sh \
            logs/p80/one_run.sh logs/p80/stamp.py logs/p80/p80lib.py \
            logs/p80/motion_reference_twoline_p80_20.json \
            logs/p86/motion_reference_twoline_C6_20.json \
            logs/p91/C5.log logs/p91/C6.log \
            logs/p92/PREREG.md logs/p92/census.py logs/p92/p92_report.py \
            logs/p93/PREREG.md
        echo "# seed cells: ${ENV_SEED[*]} ATTEMPTS=20 SEED=<101|202> [FRUIT_SUPPLY_X_MAX=0.33]"
        echo "# diag cells: ${ENV_DIAG[*]} ATTEMPTS=4 SEED=6 [FRUIT_SUPPLY_X_MAX=0.33]"
        echo "# the change: fruits.SupplyPlan x band 0.20-0.36 -> 0.20-0.33 (env only)"
    } | tee logs/p93/header.txt
fi

fail=0
note() { echo "[p93] $*"; }

claim_run() {  # claim_run <tag> <limit> <env...>
    local tag=$1; shift
    local limit=$1; shift
    local log="logs/p93/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "logs/p93/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p93/${tag}.stamps"
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $tag"
    if [ "$rc" -ne 0 ] || [ ! -s "$log" ]; then
        note "FAIL $tag (rc=$rc)"; fail=$((fail + 1))
    fi
}

sel=("$@")
run() {  # run <tag> <limit> <env...>
    local tag=$1; shift
    local limit=$1; shift
    if [ "${#sel[@]}" -eq 0 ] || [[ " ${sel[*]} " == *" $tag "* ]]; then
        claim_run "$tag" "$limit" "$@"
    fi
}

# ---- the diagnostics (PREREG section 1) ------------------------------------ #
# `FRUIT_DYNAMIC_TRACE_DIR` only redirects the trace *files* (no stream effect):
# without it the two cells overwrite each other's `logs/dynamic_trace/` names,
# which cost this phase one wasted pair on the first pass (RESULTS deviation D1).
run D6C 900 "${ENV_DIAG[@]}" ATTEMPTS=4 SEED=6 \
    FRUIT_DYNAMIC_TRACE_DIR=logs/p93/p1/D6C/trace
run D6T 900 "${ENV_DIAG[@]}" ATTEMPTS=4 SEED=6 FRUIT_SUPPLY_X_MAX=0.33 \
    FRUIT_DYNAMIC_TRACE_DIR=logs/p93/p1/D6T/trace

# ---- the fresh seeds (PREREG section 2) ------------------------------------ #
run C101 2400 "${ENV_SEED[@]}" ATTEMPTS=20 SEED=101
run T101 2400 "${ENV_SEED[@]}" ATTEMPTS=20 SEED=101 FRUIT_SUPPLY_X_MAX=0.33
run C202 2400 "${ENV_SEED[@]}" ATTEMPTS=20 SEED=202
run T202 2400 "${ENV_SEED[@]}" ATTEMPTS=20 SEED=202 FRUIT_SUPPLY_X_MAX=0.33

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
