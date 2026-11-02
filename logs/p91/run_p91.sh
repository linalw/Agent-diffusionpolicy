#!/usr/bin/env bash
# P91 battery: the take-off validation ramp as a two-line-scoped tick cell.
#
#   bash logs/p91/run_p91.sh                 # all four cells, sequential
#   bash logs/p91/run_p91.sh C5 T5           # a subset (the admissibility pair first)
#
# PREREG: logs/p91/PREREG.md (md5 in logs/p91/PREREG.md5), pinned before any run.
#
# Cells (20 attempts, the shipped two-line default, one run each):
#   C5  seed 5, FRUIT_DYNAMIC_PROBE_TICKS=60   the shipped 60-tick probe (explicit)
#   T5  seed 5, unset                          the cell (24) - BATTERY FORM constant on
#   C6  seed 6, FRUIT_DYNAMIC_PROBE_TICKS=60   the same control, second seed
#   T6  seed 6, unset                          the cell, second seed
#
# The instrumentation is P89's four cells verbatim (`FRUIT_MOTION_REPORT
# FRUIT_CYCLE_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`) - identical on both
# arms - and the release/place/lift cells are unset everywhere (P87's scoped
# default on, P88/P89 off), so the comparison is the probe alone. Wall via
# logs/p80/stamp.py, one claim via scripts/154_claim_run.sh. Nothing here writes
# src/, configs/, datasets/ or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p91

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)

if [ ! -s logs/p91/header.txt ]; then
    {
        echo "# P91 header ($(date '+%F %T'))"
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
            scripts/250_p91_probe_scope_selftest.py \
            logs/p80/one_run.sh logs/p80/stamp.py logs/p80/p80lib.py \
            logs/p80/motion_reference_twoline_p80_20.json \
            logs/p86/motion_reference_twoline_C6_20.json \
            logs/p89/T5.log logs/p89/T6.log logs/p71/accept_rails_none.log \
            logs/p91/AUDIT.md logs/p91/PREREG.md logs/p91/PREREG.md5 \
            logs/p91/audit.py logs/p91/p91_report.py
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6> [FRUIT_DYNAMIC_PROBE_TICKS=60]"
        echo "# PROBE_TWO_LINE_DEFAULT (battery form): $(grep -m1 '^PROBE_TWO_LINE_DEFAULT = ' src/fruit_sorting/tasks.py)"
    } | tee logs/p91/header.txt
fi

fail=0
note() { echo "[p91] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p91/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=2400 scripts/154_claim_run.sh "logs/p91/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p91/${tag}.stamps"
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

run C5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5 FRUIT_DYNAMIC_PROBE_TICKS=60
run T5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run C6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6 FRUIT_DYNAMIC_PROBE_TICKS=60
run T6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
