#!/usr/bin/env bash
# P92 battery: the supplied lateral band's top as a scenario lever (one claim/run).
#
#   bash logs/p92/run_p92.sh              # all four cells, sequential
#   bash logs/p92/run_p92.sh C5 T5        # a subset (the admissibility pair first)
#
# PREREG: logs/p92/PREREG.md (md5 in logs/p92/PREREG.md5), pinned before any run.
#
# Cells (20 attempts, the shipped two-line default, one run each):
#   C5  seed 5, unset                      the tree check == logs/p91/C5.log
#   T5  seed 5, FRUIT_SUPPLY_X_MAX=0.33    the treatment
#   C6  seed 6, unset                      the tree check == logs/p91/C6.log
#   T6  seed 6, FRUIT_SUPPLY_X_MAX=0.33    the treatment
#
# The instrumentation is P91's four cells verbatim (`FRUIT_MOTION_REPORT
# FRUIT_CYCLE_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`) so the control replay
# and the class census are read on the same rows. Wall via logs/p80/stamp.py,
# one claim via scripts/154_claim_run.sh. Nothing here writes src/, configs/,
# datasets/ or a checkpoint; the only difference between a C and a T cell is
# the supply env, which the `[supply] ... lateral x=` row prints.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p92

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)

if [ ! -s logs/p92/header.txt ]; then
    {
        echo "# P92 header ($(date '+%F %T'))"
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
            logs/p91/C5.log logs/p91/C6.log logs/p91/N5.log \
            logs/p92/PREREG.md logs/p92/census.py logs/p92/p92_report.py
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6> [FRUIT_SUPPLY_X_MAX=0.33]"
        echo "# the change: fruits.SupplyPlan x band 0.20-0.36 -> 0.20-0.33 (env only)"
    } | tee logs/p92/header.txt
fi

fail=0
note() { echo "[p92] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p92/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=2400 scripts/154_claim_run.sh "logs/p92/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p92/${tag}.stamps"
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

run C5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run T5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5 FRUIT_SUPPLY_X_MAX=0.33
run C6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6
run T6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6 FRUIT_SUPPLY_X_MAX=0.33

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
