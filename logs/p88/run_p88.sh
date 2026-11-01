#!/usr/bin/env bash
# P88 battery: the place raise as a two-line-scoped default (one claim per run).
#
#   bash logs/p88/run_p88.sh                 # all four cells, sequential
#   bash logs/p88/run_p88.sh C5 T5           # a subset (the admissibility pair first)
#
# PREREG: logs/p88/PREREG.md (md5 in logs/p88/PREREG.md5), pinned before any run.
#
# Cells (20 attempts, the shipped two-line default, one run each):
#   C5  seed 5, FRUIT_SPEED_PLACE=0   the shipped 0.35 cap == P87's T5
#   T5  seed 5, unset                 the scoped default (0.52)
#   C6  seed 6, FRUIT_SPEED_PLACE=0   == P87's T6
#   T6  seed 6, unset
#
# The instrumentation is P87's four cells verbatim (`FRUIT_MOTION_REPORT
# FRUIT_CYCLE_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`) - identical on both
# arms - which is what makes G0 (`--same` against P87's logs, the new
# `[biarm] place profile:` row dropped) admissible. The release cell is unset
# everywhere (its own two-line default), so the comparison is the place alone.
# Wall via logs/p80/stamp.py, one claim via scripts/154_claim_run.sh. Nothing
# here writes src/, configs/, datasets/ or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p88

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)

if [ ! -s logs/p88/header.txt ]; then
    {
        echo "# P88 header ($(date '+%F %T'))"
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
            scripts/248_p88_place_scope_selftest.py \
            logs/p80/one_run.sh logs/p80/stamp.py logs/p80/p80lib.py \
            logs/p80/motion_reference_twoline_p80_20.json \
            logs/p86/motion_reference_twoline_C6_20.json \
            logs/p87/T5.log logs/p87/T6.log \
            logs/p88/PREREG.md logs/p88/p88_report.py
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6> [FRUIT_SPEED_PLACE=0]"
    } | tee logs/p88/header.txt
fi

fail=0
note() { echo "[p88] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p88/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=2400 scripts/154_claim_run.sh "logs/p88/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p88/${tag}.stamps"
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

run C5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5 FRUIT_SPEED_PLACE=0
run T5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run C6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6 FRUIT_SPEED_PLACE=0
run T6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
