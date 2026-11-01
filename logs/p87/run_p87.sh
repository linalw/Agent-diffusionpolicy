#!/usr/bin/env bash
# P87 battery: the release trim as a two-line-scoped default (one claim per run).
#
#   bash logs/p87/run_p87.sh                 # all four cells, sequential
#   bash logs/p87/run_p87.sh C5 T5           # a subset (the admissibility pair first)
#
# PREREG: logs/p87/PREREG.md (md5 in logs/p87/PREREG.md5), pinned before any run.
#
# Cells (20 attempts, the shipped two-line default, one run each):
#   C5  seed 5, FRUIT_SPEED_RELEASE=0   the shipped 20/3/3 clock == P86's C5
#   T5  seed 5, unset                   the scoped default == P86's R5
#   C6  seed 6, FRUIT_SPEED_RELEASE=0   == P86's C6
#   T6  seed 6, unset                   == P86's R6
#
# The instrumentation is P86's four cells verbatim (`FRUIT_MOTION_REPORT
# FRUIT_CYCLE_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`) - identical on both
# arms - which is what makes G0 (`--same` against P86's logs, the new
# `[biarm] release profile:` row dropped) admissible. T5+T6 are the 40-attempt
# budget sample PREREG section 2 asks for. Wall via logs/p80/stamp.py, one claim
# via scripts/154_claim_run.sh. Nothing here writes src/, configs/, datasets/ or
# a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p87

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)

if [ ! -s logs/p87/header.txt ]; then
    {
        echo "# P87 header ($(date '+%F %T'))"
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
            scripts/247_p87_release_scope_selftest.py \
            logs/p80/one_run.sh logs/p80/stamp.py logs/p80/p80lib.py \
            logs/p80/motion_reference_twoline_p80_20.json \
            logs/p86/C5.log logs/p86/R5.log logs/p86/C6.log logs/p86/R6.log \
            logs/p86/motion_reference_twoline_C6_20.json \
            logs/p87/PREREG.md logs/p87/p87_report.py
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6> [FRUIT_SPEED_RELEASE=0]"
    } | tee logs/p87/header.txt
fi

fail=0
note() { echo "[p87] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p87/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=2400 scripts/154_claim_run.sh "logs/p87/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p87/${tag}.stamps"
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

run C5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5 FRUIT_SPEED_RELEASE=0
run T5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run C6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6 FRUIT_SPEED_RELEASE=0
run T6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
