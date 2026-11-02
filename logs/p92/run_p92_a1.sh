#!/usr/bin/env bash
# P92 amendment A1: the force servo's contact gate (one claim per run).
#
#   bash logs/p92/run_p92_a1.sh            # both cells, sequential
#   bash logs/p92/run_p92_a1.sh R5         # a subset
#
# PREREG: logs/p92/PREREG_A1.md (md5 in logs/p92/PREREG_A1.md5), pinned before
# these runs. The census that names the lever is logs/p92/chase.txt.
#
# Cells (20 attempts, the shipped two-line default, one run each):
#   R5  seed 5, FRUIT_FORCE_REENTRY=1 (+ its diag)   the gate
#   R6  seed 6, FRUIT_FORCE_REENTRY=1 (+ its diag)   the gate
#
# Controls are C5/C6 from run_p92.sh (same tree, same instrumentation, one run
# each). The knob is dynamic-capture-scoped and default off, so the only
# difference between a C and an R cell is the servo's gate.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p92

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1
            FRUIT_FORCE_REENTRY=1 FRUIT_FORCE_REENTRY_DIAG=1)

if [ ! -s logs/p92/header_r.txt ]; then
    {
        echo "# P92/A1 header ($(date '+%F %T'))"
        echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
        md5sum src/fruit_sorting/tasks.py src/fruit_sorting/bimanual.py \
            src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
            src/fruit_sorting/control.py src/fruit_sorting/conveyor.py \
            src/fruit_sorting/assets.py src/fruit_sorting/rl_env.py \
            configs/motion_reference.json configs/motion_reference_single.json \
            configs/motion_reference_twoline.json \
            scripts/20_pick_place.py scripts/accept.sh scripts/selfcheck.sh \
            scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
            scripts/154_claim_run.sh logs/p80/one_run.sh logs/p80/stamp.py \
            logs/p80/p80lib.py logs/p80/motion_reference_twoline_p80_20.json \
            logs/p86/motion_reference_twoline_C6_20.json \
            logs/p91/C5.log logs/p91/C6.log \
            logs/p92/PREREG.md logs/p92/PREREG_A1.md logs/p92/census.py \
            logs/p92/chase.py logs/p92/p92_report.py logs/p92/p92_a1_report.py
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6>"
        echo "# the change: FRUIT_FORCE_REENTRY=1 (default 0) - hold the gap out of force mode"
    } | tee logs/p92/header_r.txt
fi

fail=0
note() { echo "[p92a1] $*"; }

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
run() {
    local tag=$1; shift
    if [ "${#sel[@]}" -eq 0 ] || [[ " ${sel[*]} " == *" $tag "* ]]; then
        claim_run "$tag" "$@"
    fi
}

run R5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run R6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6

note "A1 battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
